package store

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
)

// copyFixture فیکسچرِ مخزن را در t.TempDir() کپی می‌کند؛ بانکِ عملیاتیِ کاربر
// هرگز باز نمی‌شود و تست هیچ چیزی در مخزن نمی‌نویسد.
func copyFixture(t *testing.T) string {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
	if err != nil {
		t.Fatal(err)
	}
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dst
}

// openCopy کپیِ فیکسچر را مثلِ مسیرِ واقعی باز می‌کند: market.db فقط‌خواندنی.
func openCopy(t *testing.T, dir string, readOnly bool) *db.Handles {
	t.Helper()
	h, err := db.Open(dir, readOnly)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h
}

func openFixture(t *testing.T) *db.Handles {
	t.Helper()
	return openCopy(t, copyFixture(t), true)
}

func TestLoadBoardFixture(t *testing.T) {
	h := openFixture(t)
	fr, err := LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30", fr.N())
	}
	for _, col := range []string{"symbol", "name", "sector_name", "p_closing", "p_last", "q_tot_tran", "d_even", "mcap"} {
		if _, ok := fr.Cols[col]; !ok {
			t.Fatalf("missing column %q", col)
		}
	}
	for _, c := range fr.Codes {
		if c == "INS-غایب" {
			t.Fatal("instrument without a market_watch row leaked into the board")
		}
	}
}

func TestBoardSQLFallsBackWithoutWindowTables(t *testing.T) {
	h := openFixture(t)
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(text, "SELECT * FROM board_hist_v") {
		t.Fatal("missing-window fallback did not inline the history CTE")
	}
	if !strings.Contains(text, "WITH iso AS") {
		t.Fatal("fallback does not embed _HIST_V_SQL")
	}
	if !strings.Contains(text, "allowed_max <= ") {
		t.Fatal("mcap dead-band gate missing")
	}
}

func TestBoardSQLUsesWindowTablesWhenPresent(t *testing.T) {
	// جدول‌هایِ پنجره فقط با اتصالِ نوشتنی ساخته می‌شوند؛ کپیِ موقت، نه فیکسچر.
	h := openCopy(t, copyFixture(t), false)
	for _, q := range []string{
		"CREATE TABLE board_hist_v(x INTEGER)",
		"CREATE TABLE board_hist_fv(x INTEGER)",
	} {
		if _, err := h.Market.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "SELECT * FROM board_hist_v") {
		t.Fatal("window tables present but the query did not use them")
	}
}

func TestBoardSQLPrefersSlotWindow(t *testing.T) {
	h := openFixture(t)
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "tape_ih_slot") {
		t.Fatal("fixture has tape_ih_slot rows; the slot window must be used")
	}
	if strings.Contains(text, "ROW_NUMBER() OVER (PARTITION BY ins_code ORDER BY d_even DESC) AS srn") {
		t.Fatal("row-based [ih] window used although slots are available")
	}
}

// TestBoardSQLFallsBackToRowWindowWithoutSlots مدرکِ مسیرِ جایگزینِ ردیف‌محور
// است: بی tape_ih_slot، متن باید HistFvSQL را درجا ببرد نه HistFvSlotSQL را.
func TestBoardSQLFallsBackToRowWindowWithoutSlots(t *testing.T) {
	dir := copyFixture(t)
	setup := openCopy(t, dir, false)
	if _, err := setup.Market.Exec("DROP TABLE tape_ih_slot"); err != nil {
		t.Fatal(err)
	}
	if err := setup.Close(); err != nil {
		t.Fatal(err)
	}
	h := openCopy(t, dir, true)
	text, err := BoardSQLForTest(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	// این دو رشته در هر چهار متنِ پایتون یکتا هستند: `MAX(srn) AS hist_sessions`
	// فقط در HistFvSQL (ردیف‌محور) و `MAX(slot) + 1 AS hist_sessions` فقط در
	// HistFvSlotSQL (اسلات‌محور) آمده است.
	const rowFrag = "MAX(srn) AS hist_sessions"
	const slotFrag = "MAX(slot) + 1 AS hist_sessions"
	if !strings.Contains(text, rowFrag) {
		t.Fatal("row-based HistFvSQL is not embedded after tape_ih_slot is dropped")
	}
	if strings.Contains(text, slotFrag) {
		t.Fatal("slot-based HistFvSlotSQL embedded although tape_ih_slot is gone")
	}
	fr, err := LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30 on the row-window fallback", fr.N())
	}
}

// TestInlineBoardSQLStaysReadOnly تضمین می‌کند مسیرِ درجا رویِ بانکِ فقط‌خواندنی
// هیچ جدول/فایلِ جانبی نمی‌سازد: نه board_hist_*، نه -wal/-shm، و نه تغییرِ
// mtime/اندازهٔ فایل.
func TestInlineBoardSQLStaysReadOnly(t *testing.T) {
	dir := copyFixture(t)
	marketPath := filepath.Join(dir, "market.db")
	before, err := os.Stat(marketPath)
	if err != nil {
		t.Fatal(err)
	}
	h := openCopy(t, dir, true)
	fr, err := LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30", fr.N())
	}
	for _, name := range []string{"board_hist_v", "board_hist_fv"} {
		var n int
		if err := h.Market.QueryRow(
			"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", name).Scan(&n); err != nil {
			t.Fatal(err)
		}
		if n != 0 {
			t.Fatalf("%s was created on the inline read-only path", name)
		}
	}
	after, err := os.Stat(marketPath)
	if err != nil {
		t.Fatal(err)
	}
	if after.Size() != before.Size() {
		t.Fatalf("market.db size changed: %d -> %d", before.Size(), after.Size())
	}
	if !after.ModTime().Equal(before.ModTime()) {
		t.Fatalf("market.db mtime changed: %v -> %v", before.ModTime(), after.ModTime())
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), "-wal") || strings.HasSuffix(e.Name(), "-shm") {
			t.Fatalf("SQLite sidecar %q appeared next to the read-only copy", e.Name())
		}
	}
}
