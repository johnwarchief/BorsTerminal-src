package mstat

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// handlerCase یکِ سیزده مسیرِ GETِ تبِ وضعیت بازار.
type handlerCase struct {
	name   string
	target string
	fn     http.HandlerFunc
}

func handlerCases(s *Service) []handlerCase {
	return []handlerCase{
		{"summary", "/api/mstat/summary", s.Summary},
		{"histogram", "/api/mstat/histogram?group=stock", s.Histogram},
		{"thermometer", "/api/mstat/thermometer", s.Thermometer},
		{"depth", "/api/mstat/depth?group=eq_funds", s.Depth},
		{"clientsplit", "/api/mstat/clientsplit?tab=stock", s.ClientSplit},
		{"market-snapshot", "/api/mstat/market-snapshot", s.MarketSnapshot},
		{"phase", "/api/mstat/phase", s.Phase},
		{"mainwatch", "/api/mstat/mainwatch?limit=5", s.Mainwatch},
		{"industries", "/api/mstat/industries", s.Industries},
		{"timeline", "/api/mstat/timeline?mode=inst", s.Timeline},
		{"phases", "/api/mstat/phases", s.Phases},
		{"smart-money", "/api/mstat/smart-money", s.SmartMoney},
		{"board", "/api/mstat/board?limit=5", s.Board},
	}
}

// TestBoardLimitValidation422: board فقط group/limit دارد؛ limitِ غیرعدد همان
// ۴۲۲ِ FastAPI را می‌دهد، نه ۵۰۰ یا بدنهٔ پیش‌فرض.
func TestBoardLimitValidation422(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	for _, target := range []string{"/api/mstat/board?limit=abc", "/api/mstat/board?limit="} {
		rec := httptest.NewRecorder()
		s.Board(rec, httptest.NewRequest("GET", target, nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("%s: status = %d", target, rec.Code)
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
			len(body.Detail[0].Loc) != 2 || body.Detail[0].Loc[1] != "limit" {
			t.Fatalf("%s: body = %s", target, rec.Body.String())
		}
	}
}

func TestHandlersReturnPanelsWithSource(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), stubFlags{map[string]map[string]bool{}, true})
	s.clock = func() time.Time { return pinnedNow }
	for _, c := range handlerCases(s) {
		rec := httptest.NewRecorder()
		c.fn(rec, httptest.NewRequest("GET", c.target, nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d (%s)", c.name, rec.Code, rec.Body.String())
		}
		if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
			t.Fatalf("%s: Content-Type = %q", c.name, ct)
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		if body["status"] != "ok" {
			t.Fatalf("%s: status field = %v", c.name, body["status"])
		}
		if body["source"] != "local:market.db" {
			t.Fatalf("%s: source = %v", c.name, body["source"])
		}
	}
}

// TestPhaseHandlerAddsStatus نگهبانِ یگانهٔ statusِ مسیرِ فاز است: Phaseِ
// marketphase عمداً Status ندارد (پایتون آن را در session_phase می‌گذارد)، پس
// اگر phasePanel آن را نیفزاید فقط همین تست قرمز می‌شود.
func TestPhaseHandlerAddsStatus(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	rec := httptest.NewRecorder()
	s.Phase(rec, httptest.NewRequest("GET", "/api/mstat/phase", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "ok" {
		t.Fatalf("phase status = %v, want ok", body["status"])
	}
	if body["phase"] != "closed" || body["clock_now"] != "2026-10-28 10:30:00" {
		t.Fatalf("phase body = %s", rec.Body.String())
	}
}

func TestMainwatchValidation422(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	for _, tc := range []struct {
		target, typ, field string
	}{
		{"/api/mstat/mainwatch?limit=abc", "int_parsing", "limit"},
		{"/api/mstat/mainwatch?desc=xx", "bool_parsing", "desc"},
		{"/api/mstat/mainwatch?limit=", "int_parsing", "limit"},
		{"/api/mstat/mainwatch?desc=%20true", "bool_parsing", "desc"},
	} {
		rec := httptest.NewRecorder()
		s.Mainwatch(rec, httptest.NewRequest("GET", tc.target, nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("%s: status = %d", tc.target, rec.Code)
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
		if len(body.Detail) != 1 || body.Detail[0].Type != tc.typ ||
			len(body.Detail[0].Loc) != 2 || body.Detail[0].Loc[1] != tc.field {
			t.Fatalf("%s: body = %s", tc.target, rec.Body.String())
		}
	}
}

// TestMainwatchHandlerPassesFlagSource سیم‌کشیِ FlagSource را از مسیرِ HTTP
// می‌سنجد، نه از پنل: پرچمِ واقعیِ فولاد۲ باید در بدنهٔ مسیر دیده شود. اگر
// هندلر s.flags را جا بیندازد (یا nil بدهد)، این تست قرمز می‌شود.
func TestMainwatchHandlerPassesFlagSource(t *testing.T) {
	h := openFixture(t)
	flags := map[string]map[string]bool{
		normSymbol("فولاد۲"): {"f_noqteh": true, "f_susp": true},
	}
	s := New(h.Market, t.TempDir(), stubFlags{flags, true})
	rec := httptest.NewRecorder()
	s.Mainwatch(rec, httptest.NewRequest("GET", "/api/mstat/mainwatch?group=eq_all&limit=10", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d (%s)", rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["tape_flags_source"] != "api/market" {
		t.Fatalf("tape_flags_source = %v", body["tape_flags_source"])
	}
	rows, ok := body["rows"].([]any)
	if !ok {
		t.Fatalf("body has no rows: %s", rec.Body.String())
	}
	found := false
	for _, raw := range rows {
		row := raw.(map[string]any)
		if row["symbol"] != "فولاد۲" {
			continue
		}
		found = true
		tf, ok := row["tape_flags"].(map[string]any)
		if !ok {
			t.Fatalf("فولاد۲ has no tape_flags: %v", row)
		}
		if tf["f_noqteh"] != true || tf["f_susp"] != true {
			t.Fatalf("فولاد۲ tape_flags = %v", tf)
		}
	}
	if !found {
		t.Fatalf("فولاد۲ is missing from the mainwatch body: %s", rec.Body.String())
	}
}

// TestHandlerParamRules قواعدِ Queryِ FastAPI را رویِ مسیرها می‌سنجد:
// پارامترِ غایب ⇒ پیش‌فرض، ?group= ⇒ تهی (نه پیش‌فرض)، و مقدارِ ناشناخته
// بی‌خطا می‌گذرد ولی اثرش در بدنه دیده می‌شود (echo و شمارشِ ردیف‌ها)، نه فقط 200.
func TestHandlerParamRules(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	num := func(t *testing.T, body map[string]any, key string) float64 {
		t.Helper()
		v, ok := body[key].(float64)
		if !ok {
			t.Fatalf("%s = %T, want a number", key, body[key])
		}
		return v
	}
	cases := []struct {
		name   string
		target string
		fn     http.HandlerFunc
		check  func(t *testing.T, body map[string]any)
	}{
		{"histogram default", "/api/mstat/histogram", s.Histogram, func(t *testing.T, b map[string]any) {
			if b["group"] != "all" || num(t, b, "total") != 5 {
				t.Fatalf("default body = %v", b)
			}
		}},
		{"histogram empty", "/api/mstat/histogram?group=", s.Histogram, func(t *testing.T, b map[string]any) {
			if b["group"] != "" || num(t, b, "total") != 0 {
				t.Fatalf("empty group body = %v", b)
			}
		}},
		{"histogram eq_all", "/api/mstat/histogram?group=eq_all", s.Histogram, func(t *testing.T, b map[string]any) {
			if b["group"] != "eq_all" || num(t, b, "total") != 4 {
				t.Fatalf("eq_all body = %v", b)
			}
		}},
		{"depth known", "/api/mstat/depth?group=eq_all", s.Depth, func(t *testing.T, b map[string]any) {
			if b["group"] != "eq_all" || num(t, b, "symbols_with_depth") != 4 {
				t.Fatalf("depth body = %v", b)
			}
		}},
		{"depth unknown", "/api/mstat/depth?group=nope", s.Depth, func(t *testing.T, b map[string]any) {
			if b["group"] != "nope" || num(t, b, "symbols_with_depth") != 0 {
				t.Fatalf("unknown group body = %v", b)
			}
		}},
		{"clientsplit empty", "/api/mstat/clientsplit?tab=", s.ClientSplit, func(t *testing.T, b map[string]any) {
			if b["tab"] != "" || num(t, b, "symbols") != 5 {
				t.Fatalf("empty tab body = %v", b)
			}
		}},
		{"clientsplit fixed", "/api/mstat/clientsplit?tab=fixed", s.ClientSplit, func(t *testing.T, b map[string]any) {
			if b["tab"] != "fixed" || num(t, b, "symbols") != 1 {
				t.Fatalf("fixed tab body = %v", b)
			}
		}},
		{"timeline unknown", "/api/mstat/timeline?mode=wat", s.Timeline, func(t *testing.T, b map[string]any) {
			if b["mode"] != "cum" || num(t, b, "points") != 3 {
				t.Fatalf("unknown mode body = %v", b)
			}
		}},
		{"timeline inst", "/api/mstat/timeline?mode=inst", s.Timeline, func(t *testing.T, b map[string]any) {
			series, ok := b["series"].(map[string]any)
			if !ok {
				t.Fatalf("series = %T", b["series"])
			}
			bt, ok := series["bq_bt"].([]any)
			if !ok || len(bt) != 3 || bt[0] != float64(2) || bt[1] != float64(1) {
				t.Fatalf("inst series = %v", series["bq_bt"])
			}
			if b["mode"] != "inst" {
				t.Fatalf("mode = %v", b["mode"])
			}
		}},
		{"mainwatch limit", "/api/mstat/mainwatch?limit=2", s.Mainwatch, func(t *testing.T, b map[string]any) {
			if num(t, b, "total") != 4 {
				t.Fatalf("total = %v", b["total"])
			}
			rows, ok := b["rows"].([]any)
			if !ok || len(rows) != 2 {
				t.Fatalf("rows = %v", b["rows"])
			}
			row, ok := rows[0].(map[string]any)
			if !ok {
				t.Fatalf("row = %T", rows[0])
			}
			for _, k := range []string{"symbol", "ins_code", "industry", "clock_ok"} {
				if _, ok := row[k]; !ok {
					t.Fatalf("row missing %q: %v", k, row)
				}
			}
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := httptest.NewRecorder()
			c.fn(rec, httptest.NewRequest("GET", c.target, nil))
			body := decodePanel(t, rec)
			if body["status"] != "ok" {
				t.Fatalf("%s: status = %v", c.target, body["status"])
			}
			c.check(t, body)
		})
	}
}

// decodePanel بدنهٔ 200 را با بررسیِ کد برمی‌گرداند تا تست‌هایِ پارامتر میانِ
// «شکلِ پاسخ» و «مقدارِ پاسخ» فرق بگذارند.
func decodePanel(t *testing.T, rec *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d (%s)", rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("body: %v (%s)", err, rec.Body.String())
	}
	return body
}

// TestDuplicateQueryParamsLastWins همان قاعدهٔ FastAPI/Starlette است: کلیدِ
// تکراری ⇒ آخرین مقدار. url.Values.Get اولین را برمی‌گرداند و این تست را قرمز
// می‌کند.
func TestDuplicateQueryParamsLastWins(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	get := func(target string, fn http.HandlerFunc) map[string]any {
		t.Helper()
		rec := httptest.NewRecorder()
		fn(rec, httptest.NewRequest("GET", target, nil))
		return decodePanel(t, rec)
	}
	b := get("/api/mstat/histogram?group=stock&group=all", s.Histogram)
	if b["group"] != "all" || b["total"] != float64(5) {
		t.Fatalf("duplicate group body = %v (first value won?)", b)
	}
	b = get("/api/mstat/mainwatch?desc=true&desc=0", s.Mainwatch)
	if b["desc"] != false {
		t.Fatalf("duplicate desc = %v, want false (last value)", b["desc"])
	}
	b = get("/api/mstat/mainwatch?limit=2&limit=5", s.Mainwatch)
	rows, ok := b["rows"].([]any)
	if !ok || len(rows) != 4 {
		t.Fatalf("duplicate limit rows = %v, want 4 (last limit 5, clamped)", b["rows"])
	}
}

// TestMainwatchKeyIsCollisionFree کلیدِ کش را با «|» در دو پارامتر می‌آزماید:
// joinِ سادهٔ pipe این دو تاپل را یکی می‌کرد و دومی بدنهٔ اول (group=a،
// industry=b|c) را از کش می‌خورد؛ echoها این را لو می‌دهند.
func TestMainwatchKeyIsCollisionFree(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	get := func(target string) map[string]any {
		t.Helper()
		rec := httptest.NewRecorder()
		s.Mainwatch(rec, httptest.NewRequest("GET", target, nil))
		return decodePanel(t, rec)
	}
	first := get("/api/mstat/mainwatch?group=a&industry=b%7Cc&sort=d")
	second := get("/api/mstat/mainwatch?group=a%7Cb&industry=c&sort=d")
	if first["group"] != "a" || first["industry"] != "b|c" {
		t.Fatalf("first body = %v", first)
	}
	if second["group"] != "a|b" || second["industry"] != "c" {
		t.Fatalf("second body = %v (cache hit on the first key?)", second)
	}
}

// TestMainwatchBoolSpellings مجموعهٔ مثبتِ Pydantic را می‌سنجد؛ نسخهٔ قبلی فقط
// ردشدنِ desc=xx را داشت و واژه‌هایِ true را هرگز لمس نمی‌کرد.
func TestMainwatchBoolSpellings(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	for _, tc := range []struct {
		raw  string
		want bool
	}{
		{"1", true}, {"yes", true}, {"on", true}, {"t", true},
		{"0", false}, {"no", false}, {"off", false}, {"f", false},
	} {
		rec := httptest.NewRecorder()
		s.Mainwatch(rec, httptest.NewRequest("GET", "/api/mstat/mainwatch?desc="+tc.raw, nil))
		body := decodePanel(t, rec)
		if body["desc"] != tc.want {
			t.Fatalf("desc=%s body desc = %v, want %v", tc.raw, body["desc"], tc.want)
		}
	}
}
