package mstat

import (
	"net/http/httptest"
	"testing"
	"time"
)

// boardService همان سرویسِ واقعی با ساعتِ تزریقی؛ board پنل‌ها را از همین کش
// می‌خواند، پس clock باید طلایی (۲۰۲۶-۱۰-۲۸ ۱۰:۳۰) باشد.
func boardService(t *testing.T) (*Service, map[string]map[string]bool) {
	t.Helper()
	h := openFixture(t)
	flags, _ := marketFlags(h)
	s := New(h.Market, t.TempDir(), stubFlags{m: flags, ok: true})
	s.clock = func() time.Time { return pinnedNow }
	return s, flags
}

func TestBoardMatchesGolden(t *testing.T) {
	s, _ := boardService(t)
	got := s.boardBody("eq_all", 60)
	compareGolden(t, "board", loadGolden(t, "s1", "board"), got)
}

// TestBoardSharesPanelCache ثابت می‌کند board و مسیرِ تک‌پنلی یک کلیدِ کش
// دارند: بدنهٔ نشانه‌گذاری‌شده در کش، هم از board و هم از مسیرِ HTTP بیرون
// می‌آید. source فقط در سطحِ board می‌ماند (همان _panel).
func TestBoardSharesPanelCache(t *testing.T) {
	s, _ := boardService(t)
	state, ok := s.state()
	if !ok {
		t.Fatal("no cache state")
	}
	sentinel := map[string]any{"status": "ok", "source": "sentinel", "marker": true}
	now := s.clock()
	s.mu.Lock()
	s.cache["smart-money\x00"+state] = entry{at: now, body: sentinel}
	s.cache["summary\x00"+state] = entry{at: now, body: sentinel}
	s.mu.Unlock()

	board := s.boardBody("eq_all", 60)
	sm := board["smartmoney"].(map[string]any)
	if sm["marker"] != true {
		t.Fatalf("board did not read the smoke cache entry: %v", sm)
	}
	if _, ok := sm["source"]; ok {
		t.Fatalf("panel source leaked into board: %v", sm)
	}
	if board["source"] != mstatSource {
		t.Fatalf("board source = %v", board["source"])
	}
	rec := httptest.NewRecorder()
	s.Summary(rec, httptest.NewRequest("GET", "/api/mstat/summary", nil))
	fresh := s.summaryBody()
	if fresh["marker"] != true || fresh["source"] != "sentinel" {
		t.Fatalf("standalone route missed the shared key: %v", fresh)
	}
}

// TestBoardPanelErrorStaysLocal: خطایِ یک پنل، board را ۲۰۰ِ خراب نمی‌کند؛
// همان قانونِ _panel: بدنهٔ status=error بدونِ source داخلِ board می‌نشیند.
func TestBoardPanelErrorStaysLocal(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec("DROP TABLE market_watch"); err != nil {
		t.Fatal(err)
	}
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	board := s.boardBody("eq_all", 60)
	if board["status"] != "ok" {
		t.Fatalf("board status = %v", board["status"])
	}
	for _, name := range []string{"summary", "histogram", "depth", "smartmoney"} {
		p := board[name].(map[string]any)
		if p["status"] != "error" {
			t.Fatalf("%s status = %v, want error", name, p["status"])
		}
		if _, ok := p["source"]; ok {
			t.Fatalf("%s error body kept source: %v", name, p)
		}
		if _, ok := p["message"]; !ok {
			t.Fatalf("%s error body has no message: %v", name, p)
		}
	}
}
