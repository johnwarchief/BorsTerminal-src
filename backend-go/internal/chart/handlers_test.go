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

func TestAdvancedChartHandlers(t *testing.T) {
	s := openService(t, "s1")
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/chart/{symbol}/forecast", s.Forecast)
	mux.HandleFunc("GET /api/chart/{symbol}/edge", s.Edge)
	mux.HandleFunc("GET /api/chart/{symbol}/indicators", s.Indicators)

	decode := func(rec *httptest.ResponseRecorder) map[string]any {
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("json unmarshal error: %v, raw body: %s", err, rec.Body.String())
		}
		return body
	}

	// 1. Forecast endpoint: status 200 and valid JSON
	{
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/forecast?horizon=12", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("forecast status = %d, body = %s", rec.Code, rec.Body.String())
		}
		body := decode(rec)
		if body["symbol"] != "عادی01" || body["horizon"] != float64(12) {
			t.Fatalf("forecast unexpected body: %+v", body)
		}

		// Test with liquid avg_daily_value override
		rec = httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/forecast?horizon=6&avg_daily_value=10000000000", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("forecast liquid status = %d, body = %s", rec.Code, rec.Body.String())
		}
		body = decode(rec)
		if body["is_liquid"] != true {
			t.Fatalf("forecast expected is_liquid=true, got %+v", body["is_liquid"])
		}
		steps, ok := body["forecast_steps"].([]any)
		if !ok || len(steps) != 6 {
			t.Fatalf("forecast expected 6 steps, got %v", body["forecast_steps"])
		}

		// Invalid horizon returns 422
		rec = httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/forecast?horizon=abc", nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("forecast invalid horizon status = %d", rec.Code)
		}

		// Valid adjustment modes (0, 1, 2, 3)
		for _, adj := range []string{"0", "1", "2", "3"} {
			rec = httptest.NewRecorder()
			mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/forecast?horizon=6&adjustment="+adj, nil))
			if rec.Code != http.StatusOK {
				t.Fatalf("forecast adjustment=%s status = %d", adj, rec.Code)
			}
		}

		// Invalid adjustment returns 422
		rec = httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/forecast?adjustment=xyz", nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("forecast invalid adjustment status = %d", rec.Code)
		}
	}

	// 2. Edge endpoint: status 200 and valid JSON
	{
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/edge?swing_period=5", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("edge status = %d, body = %s", rec.Code, rec.Body.String())
		}
		body := decode(rec)
		if body["symbol"] != "عادی01" {
			t.Fatalf("edge symbol = %v", body["symbol"])
		}
		if _, ok := body["market_regime"]; !ok {
			t.Fatalf("edge missing market_regime: %+v", body)
		}
		if _, ok := body["active_zones"]; !ok {
			t.Fatalf("edge missing active_zones: %+v", body)
		}

		// Invalid swing_period returns 422
		rec = httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/edge?swing_period=xyz", nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("edge invalid swing_period status = %d", rec.Code)
		}
	}

	// 3. Indicators endpoint: status 200 and core technical indicators
	{
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/عادی01/indicators", nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("indicators status = %d, body = %s", rec.Code, rec.Body.String())
		}
		body := decode(rec)
		if body["symbol"] != "عادی01" {
			t.Fatalf("indicators symbol = %v", body["symbol"])
		}
		latest, ok := body["latest"].(map[string]any)
		if !ok {
			t.Fatalf("indicators missing latest: %+v", body)
		}
		for _, key := range []string{"close", "sma20", "sma50", "sma200", "ema9", "ema21", "rsi14", "macd", "supertrend", "bollinger_upper", "atr14"} {
			if _, ok := latest[key]; !ok {
				t.Fatalf("indicators latest missing key %q: %+v", key, latest)
			}
		}
		series, ok := body["series"].(map[string]any)
		if !ok {
			t.Fatalf("indicators missing series: %+v", body)
		}
		for _, key := range []string{"sma20", "sma50", "sma200", "ema9", "ema21", "rsi14", "macd", "macd_signal", "macd_hist", "supertrend", "supertrend_direction", "bollinger_upper", "bollinger_middle", "bollinger_lower", "atr14"} {
			if _, ok := series[key]; !ok {
				t.Fatalf("indicators series missing key %q: %+v", key, series)
			}
		}
	}

	// 4. Zero panics on unknown / no-history symbol
	{
		for _, ep := range []string{"forecast", "edge", "indicators"} {
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart/"+goldNo+"/"+ep, nil))
			if rec.Code != http.StatusOK {
				t.Fatalf("%s on empty symbol status = %d, body = %s", ep, rec.Code, rec.Body.String())
			}
			body := decode(rec)
			if body["symbol"] != goldNo {
				t.Fatalf("%s on empty symbol expected symbol %q, got %q", ep, goldNo, body["symbol"])
			}
		}
	}
}
