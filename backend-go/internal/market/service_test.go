package market

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
)

func fixtureCopy(t *testing.T) (*db.Handles, string) {
	t.Helper()
	src, _ := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
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
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h, dst
}

func fixtureService(t *testing.T) *Service {
	t.Helper()
	h, dst := fixtureCopy(t)
	return New(h, dst)
}

func golden(t *testing.T, name string) any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "board", "testdata", "golden", name))
	if err != nil {
		t.Fatal(err)
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func getJSON(t *testing.T, s *Service, target string, hdr map[string]string) (int, any, []byte, string) {
	t.Helper()
	req := httptest.NewRequest("GET", target, nil)
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	switch {
	case strings.HasPrefix(target, "/api/market/delta"):
		s.Delta(rec, req)
	case strings.HasPrefix(target, "/api/market/sync-state"):
		s.SyncState(rec, req)
	default:
		s.Board(rec, req)
	}
	var v any
	if rec.Body.Len() > 0 {
		if err := json.Unmarshal(rec.Body.Bytes(), &v); err != nil {
			t.Fatalf("%s: %v", target, err)
		}
	}
	return rec.Code, v, rec.Body.Bytes(), rec.Header().Get("ETag")
}

func TestBoardMatchesPythonGolden(t *testing.T) {
	s := fixtureService(t)
	_, got, body, _ := getJSON(t, s, "/api/market", nil)
	res := parity.Compare(golden(t, "market.json"), got, parity.Options{})
	if !res.Pass {
		t.Fatalf("default board differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	_, gotAll, bodyAll, _ := getJSON(t, s, "/api/market?fields=all", nil)
	if res := parity.Compare(golden(t, "market_all.json"), gotAll, parity.Options{}); !res.Pass {
		t.Fatalf("fields=all differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	// اندازۀ دو بدنه رویِ fixture؛ فقط با -v دیده می‌شود (شاهدِ گزارشِ تسک).
	t.Logf("body bytes: market=%d market_all=%d", len(body), len(bodyAll))
	_, sync, _, _ := getJSON(t, s, "/api/market/sync-state", nil)
	// `running` از شمارشِ زندۀ پروسۀ سینکر می‌آید، نه از داده؛ رویِ ماشینی که
	// سینکرِ پایتون زنده است true می‌شود. شکلش اینجا سنجیده می‌شود، مقدارش را
	// گیتِ دو‌سروری (Task 8) هم‌زمان رویِ هر دو طرف می‌سنجد.
	if res := parity.Compare(golden(t, "sync_state.json"), sync, parity.Options{Exclude: []string{"running"}}); !res.Pass {
		t.Fatalf("sync-state differs: %v", res.Diffs)
	}
}

func TestDeltaContract(t *testing.T) {
	s := fixtureService(t)
	// اول بدنه ساخته می‌شود، بعد دلتا؛ عینِ ترتیبِ ثبتِ golden و بی‌مسیرِ
	// بازسازیِ ناهمگام.
	if _, _, _, etag := getJSON(t, s, "/api/market", nil); etag == "" {
		t.Fatal("board response has no ETag")
	}
	_, full, _, _ := getJSON(t, s, "/api/market/delta?since=-1", nil)
	if res := parity.Compare(golden(t, "delta_negative.json"), full, parity.Options{}); !res.Pass {
		t.Fatalf("delta(-1) differs: %v", res.Diffs)
	}
	// پس از یک ساختِ کش‌شده، «همان ویرایش» یعنی unchanged — نه یک بدنهٔ تازه.
	_, same, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	if res := parity.Compare(golden(t, "delta_mirror.json"), same, parity.Options{}); !res.Pass {
		t.Fatalf("delta(0) differs: %v", res.Diffs)
	}
}

func TestETag304(t *testing.T) {
	s := fixtureService(t)
	_, _, _, etag := getJSON(t, s, "/api/market", nil)
	code, _, body, _ := getJSON(t, s, "/api/market", map[string]string{"If-None-Match": etag})
	if code != 304 || len(body) != 0 {
		t.Fatalf("304 expected, got %d (%d bytes)", code, len(body))
	}
}

// TestDeltaJournalAfterChange مسیرِ آینه را می‌سنجد که goldenها فقط دو حالتِ
// «سرد» و «همان ویرایش» را دارند: یک تغییرِ واقعی در کپیِ fixture باید ویرایش
// را یک پله جلو ببرد و دقیقاً همان نماد را در دلتا بدهد — نه بدنۀ کامل.
func TestDeltaJournalAfterChange(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	w, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	var code string
	if err := w.Market.QueryRow("SELECT ins_code FROM market_watch WHERE ins_code IS NOT NULL LIMIT 1").Scan(&code); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if _, err := w.Market.Exec("UPDATE market_watch SET p_last = p_last + 1 WHERE ins_code = ?", code); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}

	_, got, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	m, _ := got.(map[string]any)
	if m["status"] != "delta" || m["rev"] != float64(1) {
		t.Fatalf("delta(0) = %v, want delta/rev 1", m["status"])
	}
	rows, _ := m["rows"].([]any)
	if len(rows) != 1 {
		t.Fatalf("delta rows = %d, want 1", len(rows))
	}
	if row, _ := rows[0].(map[string]any); row["ins_code"] != code {
		t.Fatalf("delta row = %v, want %q", rows[0], code)
	}
	for _, k := range []string{"count", "live_count", "fossil_count", "meta"} {
		if _, ok := m[k]; !ok {
			t.Fatalf("delta is missing %q: %v", k, m)
		}
	}
	// مشتریِ جلوتر از آینه: بدنۀ کامل می‌گیرد، نه دلتا.
	_, ahead, _, _ := getJSON(t, s, "/api/market/delta?since=9", nil)
	if am, _ := ahead.(map[string]any); am["status"] != "full" || am["reason"] != "stale-client" {
		t.Fatalf("delta(9) = %v", ahead)
	}
	// و «همان ویرایش» دیگر unchanged است، نه delta.
	_, same, _, _ := getJSON(t, s, "/api/market/delta?since=1", nil)
	if sm, _ := same.(map[string]any); sm["status"] != "unchanged" {
		t.Fatalf("delta(1) = %v", same)
	}
}
