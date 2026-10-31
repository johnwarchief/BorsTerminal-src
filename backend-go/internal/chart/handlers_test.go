package chart

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"
)

func TestIntQueryValidation422(t *testing.T) {
	s := openService(t, "s1")
	for _, c := range []struct {
		name string
		fn   func(w http.ResponseWriter, r *http.Request)
		url  string
	}{
		{"ma", s.MA, "/api/ma/عادی01?days=abc"},
		{"calendar", s.CalendarUpcoming, "/api/calendar/upcoming?days=1.5"},
	} {
		rec := httptest.NewRecorder()
		c.fn(rec, httptest.NewRequest("GET", c.url, nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("%s: status=%d body=%s", c.name, rec.Code, rec.Body.String())
		}
		var body struct {
			Detail []struct {
				Type string   `json:"type"`
				Loc  []string `json:"loc"`
			} `json:"detail"`
		}
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if len(body.Detail) != 1 || body.Detail[0].Type != "int_parsing" ||
			len(body.Detail[0].Loc) != 2 || body.Detail[0].Loc[1] != "days" {
			t.Fatalf("%s: detail=%+v", c.name, body.Detail)
		}
	}
}

// کنترلِ منفیِ R4: «امروز» باید از ساعتِ تزریقی بیاید، نه از ساعتِ دیواری.
// با جابه‌جا‌کردنِ ساعت به بعد از افق، همان تقویم باید خالی شود.
func TestCalendarUpcomingUsesInjectedClock(t *testing.T) {
	s := openService(t, "s1")
	if got := s.calendarUpcomingBody(14); got["count"].(int) == 0 {
		t.Fatalf("pinned 2026-10-28 must see the fixture events: %v", got)
	}
	s.clock = func() time.Time { return time.Date(2026, 12, 20, 10, 0, 0, 0, time.Local) }
	got := s.calendarUpcomingBody(14)
	if got["count"].(int) != 0 || got["capital_count"].(int) != 0 {
		t.Fatalf("after the horizon the list must be empty: %v", got)
	}
	if events := s.calendarSymbolBody(goldUp)["events"].([]map[string]any); len(events) != 5 {
		t.Fatalf("symbol route must stay horizon-free: %d", len(events))
	}
}

func TestCalendarMissingFileIsEmptyNotError(t *testing.T) {
	s := openService(t, "s1")
	s.calendarPath = filepath.Join(t.TempDir(), "nope.json")
	if got := s.calendarUpcomingBody(14); got["status"] != "ok" || got["count"].(int) != 0 {
		t.Fatalf("missing calendar must be an empty ok: %v", got)
	}
	if got := s.calendarSymbolBody(goldUp); got["status"] != "ok" || got["count"].(int) != 0 {
		t.Fatalf("missing calendar must be an empty ok: %v", got)
	}
}

// کنترلِ مثبتِ کش+مبنا: مبنا در کلیدِ کش است، و عوض‌شدنِ فایل واقعاً عدد را
// عوض می‌کند — نه اینکه تا TTL همان پاسخِ مبنایِ قبلی سرو شود.
func TestCacheKeyFollowsBasis(t *testing.T) {
	ctx := t.Context()
	s := openService(t, "s4") // basis=closing
	s.keyLevelsBody(ctx, goldDown)
	s.maBody(ctx, goldDown, 730)
	firstMA := s.maBody(ctx, goldDown, 730)
	writeJSON(t, filepath.Join(s.dataDir, "price_basis.json"), map[string]any{"basis": "last"})
	s.keyLevelsBody(ctx, goldDown)
	secondMA := s.maBody(ctx, goldDown, 730)
	if _, ok := s.keyLevels[goldDown+"|last"]; !ok {
		t.Fatalf("key-levels cache key does not carry the basis: %v", s.keyLevels)
	}
	if _, ok := s.keyLevels[goldDown+"|closing"]; !ok {
		t.Fatalf("the previous basis entry vanished: %v", s.keyLevels)
	}
	if equalJSON(t, firstMA["ma"], secondMA["ma"]) {
		t.Fatalf("MA values did not follow the basis change")
	}
	writeJSON(t, filepath.Join(s.dataDir, "price_basis.json"), map[string]any{"basis": "closing"})
	if third := s.maBody(ctx, goldDown, 730); !equalJSON(t, firstMA, third) {
		t.Fatalf("returning to the same basis must reuse the same body")
	}
}

func equalJSON(t *testing.T, a, b any) bool {
	t.Helper()
	ra, err := json.Marshal(a)
	if err != nil {
		t.Fatal(err)
	}
	rb, err := json.Marshal(b)
	if err != nil {
		t.Fatal(err)
	}
	return string(ra) == string(rb)
}

// دو مسیرِ تازهٔ B3: chart-db با اعتبارسنجیِ adjustment و fts با برشِ as_of.
func TestChartDBAndFTSHandlers(t *testing.T) {
	s := openService(t, "s1")
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/chart-db/{symbol}", s.ChartDB)
	mux.HandleFunc("GET /api/fts/{symbol}", s.FTS)

	decode := func(rec *httptest.ResponseRecorder) map[string]any {
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		return body
	}

	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart-db/عادی01", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("chart-db status = %d", rec.Code)
	}
	body := decode(rec)
	if body["status"] != "success" || body["adjustment"] != float64(3) ||
		body["count"].(float64) < 300 {
		t.Fatalf("chart-db body = %v / %v / %v", body["status"], body["adjustment"], body["count"])
	}
	if _, ok := body["fts"]; !ok {
		t.Fatal("chart-db must carry the fts block")
	}

	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart-db/عادی01?adjustment=abc", nil))
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("adjustment=abc status = %d", rec.Code)
	}
	var detail struct {
		Detail []struct {
			Type string   `json:"type"`
			Loc  []string `json:"loc"`
		} `json:"detail"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &detail); err != nil {
		t.Fatal(err)
	}
	if len(detail.Detail) != 1 || detail.Detail[0].Type != "int_parsing" ||
		detail.Detail[0].Loc[1] != "adjustment" {
		t.Fatalf("detail = %+v", detail.Detail)
	}

	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/fts/عادی01?as_of=2026-09-01", nil))
	body = decode(rec)
	if body["status"] != "success" || body["as_of"] != "2026-09-01" ||
		body["bars"] != float64(280) {
		t.Fatalf("fts as_of body = %v / %v / %v", body["status"], body["as_of"], body["bars"])
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/fts/عادی01", nil))
	if body := decode(rec); body["as_of"] != nil {
		t.Fatalf("live fts must not carry as_of: %v", body["as_of"])
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/fts/"+goldNo, nil))
	if body := decode(rec); body["status"] != "empty" {
		t.Fatalf("no-history symbol = %v", body["status"])
	}
}
