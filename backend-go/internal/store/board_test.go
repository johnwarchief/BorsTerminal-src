package store

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
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

// TestLoadBoardKeepsNewestDuplicate قراردادِ keep="first" را رویِ خودِ داده
// می‌سنجد: پس از ORDER BY d_even DESC, l_val18 ASC ردیفِ تازه‌تر اول می‌آید،
// پس ردیفِ کهنه‌ترِ همان ins_code باید کنار گذاشته شود (drop_duplicatesِ پایتون).
func TestLoadBoardKeepsNewestDuplicate(t *testing.T) {
	dir := copyFixture(t)
	setup := openCopy(t, dir, false)
	// market_watch کلیدِ اصلیِ ins_code دارد و ردیفِ دوم را نمی‌پذیرد؛ مثلِ
	// بازبینی: تغییرِ نام و بازسازیِ بی‌قید با CREATE TABLE AS.
	for _, q := range []string{
		"ALTER TABLE market_watch RENAME TO market_watch_scratch",
		"CREATE TABLE market_watch AS SELECT * FROM market_watch_scratch",
	} {
		if _, err := setup.Market.Exec(q); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
	}
	var (
		code  string
		newer int64
	)
	if err := setup.Market.QueryRow(
		"SELECT ins_code, d_even FROM market_watch ORDER BY d_even DESC LIMIT 1",
	).Scan(&code, &newer); err != nil {
		t.Fatal(err)
	}
	const older = int64(20261001)
	if _, err := setup.Market.Exec(
		"INSERT INTO market_watch SELECT * FROM market_watch WHERE ins_code = ?", code); err != nil {
		t.Fatal(err)
	}
	// بقیهٔ ستون‌ها همان کپی‌اند؛ فقط d_even ردیفِ تازه‌درج‌شده کهنه می‌شود.
	if _, err := setup.Market.Exec(
		"UPDATE market_watch SET d_even = ? WHERE rowid = last_insert_rowid()", older); err != nil {
		t.Fatal(err)
	}
	var raw int
	if err := setup.Market.QueryRow("SELECT COUNT(*) FROM market_watch").Scan(&raw); err != nil {
		t.Fatal(err)
	}
	if raw != 31 {
		t.Fatalf("market_watch rows = %d, want 31 before dedup", raw)
	}
	if err := setup.Close(); err != nil {
		t.Fatal(err)
	}

	h := openCopy(t, dir, true)
	fr, err := LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30 after dropping the duplicate", fr.N())
	}
	pos := -1
	for i, c := range fr.Codes {
		if c == code {
			pos = i
		}
	}
	if pos < 0 {
		t.Fatalf("ins_code %q is missing from the frame", code)
	}
	got, ok := fr.Cols["d_even"][pos].(int64)
	if !ok {
		t.Fatalf("d_even type = %T, want int64", fr.Cols["d_even"][pos])
	}
	if got != newer {
		t.Fatalf("kept d_even = %d, want the newer %d (keep=first after ORDER BY d_even DESC)", got, newer)
	}
	for i, v := range fr.Cols["d_even"] {
		if v == older {
			t.Fatalf("older duplicate d_even %d survived at row %d (%q)", older, i, fr.Codes[i])
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
	// `spine AS MATERIALIZED` فقط در HistVSQL (ثابتِ _HIST_V_SQLِ api/market.py)
	// هست؛ BoardSQLBase خودش فقط `v AS MATERIALIZED` دارد و این رشته را ندارد.
	if !strings.Contains(text, "spine AS MATERIALIZED") {
		t.Fatal("fallback does not inline HistVSQL (_HIST_V_SQL)")
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

// TestWindowTablesMatchInlinePath دو مسیر را سلول‌به‌سلول مقایسه می‌کند:
// ساختِ board_hist_* از همان ثابت‌هایِ SQL (مسیرِ پنجره) در برابر همان CTEِ
// درجا. فیکسچر tape_ih_slot دارد، پس پنجرهٔ [ih] همان HistFvSlotSQL است.
func TestWindowTablesMatchInlinePath(t *testing.T) {
	dir := copyFixture(t)
	setup := openCopy(t, dir, false)
	for _, q := range []string{
		"CREATE TABLE board_hist_v AS " + HistVSQL,
		"CREATE TABLE board_hist_fv AS " + HistFvSlotSQL,
	} {
		if _, err := setup.Market.Exec(q); err != nil {
			t.Fatalf("create window table: %v", err)
		}
	}
	if err := setup.Close(); err != nil {
		t.Fatal(err)
	}

	windowed, err := LoadBoard(openCopy(t, dir, true).Market)
	if err != nil {
		t.Fatalf("windowed path: %v", err)
	}
	inline, err := LoadBoard(openFixture(t).Market)
	if err != nil {
		t.Fatalf("inline path: %v", err)
	}
	if windowed.N() != 30 || inline.N() != 30 {
		t.Fatalf("rows = windowed %d, inline %d; want 30 both", windowed.N(), inline.N())
	}
	if diff := firstFrameDiff(inline, windowed); diff != "" {
		t.Fatal(diff)
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

// firstFrameDiff نامِ اولین اختلافِ سلول‌به‌سلولِ دو قاب را برمی‌گرداند؛
// رشتهٔ خالی یعنی هر ردیف و هر ستون یکسان است. ستون‌ها مرتب می‌شوند تا پیامِ
// اختلاف از اجرا به اجرا یکی باشد.
func firstFrameDiff(want, got *Frame) string {
	if len(want.Codes) != len(got.Codes) {
		return fmt.Sprintf("row count %d != %d", len(want.Codes), len(got.Codes))
	}
	cols := make([]string, 0, len(want.Cols))
	for c := range want.Cols {
		cols = append(cols, c)
	}
	sort.Strings(cols)
	for c := range got.Cols {
		if _, ok := want.Cols[c]; !ok {
			return fmt.Sprintf("column %q only in the windowed frame", c)
		}
	}
	for i, code := range want.Codes {
		if got.Codes[i] != code {
			return fmt.Sprintf("row %d code %q != %q", i, code, got.Codes[i])
		}
	}
	for _, c := range cols {
		wv := want.Cols[c]
		gv, ok := got.Cols[c]
		if !ok {
			return fmt.Sprintf("column %q missing from the windowed frame", c)
		}
		if len(gv) != len(wv) {
			return fmt.Sprintf("column %q has %d values, want %d", c, len(gv), len(wv))
		}
		for i := range wv {
			if !reflect.DeepEqual(wv[i], gv[i]) {
				return fmt.Sprintf("row %d (%s), column %q: %v (%T) != %v (%T)",
					i, want.Codes[i], c, wv[i], wv[i], gv[i], gv[i])
			}
		}
	}
	return ""
}
