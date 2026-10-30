package mstat

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// handlerCase یکِ یازده مسیرِ GETِ تبِ وضعیت بازار.
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
// بی‌خطا می‌گذرد. بدنهٔ گروهِ تهی صفر ردیف می‌دهد ولی همچنان status=ok است.
func TestHandlerParamRules(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, t.TempDir(), nil)
	s.clock = func() time.Time { return pinnedNow }
	cases := []struct {
		target string
		fn     http.HandlerFunc
	}{
		{"/api/mstat/histogram", s.Histogram},
		{"/api/mstat/histogram?group=", s.Histogram},
		{"/api/mstat/depth?group=nope", s.Depth},
		{"/api/mstat/clientsplit?tab=", s.ClientSplit},
		{"/api/mstat/timeline?mode=wat", s.Timeline},
	}
	for _, c := range cases {
		rec := httptest.NewRecorder()
		c.fn(rec, httptest.NewRequest("GET", c.target, nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d (%s)", c.target, rec.Code, rec.Body.String())
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: %v", c.target, err)
		}
		if body["status"] != "ok" {
			t.Fatalf("%s: status = %v", c.target, body["status"])
		}
	}
}
