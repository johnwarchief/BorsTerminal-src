package chart

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
)

const (
	goldUp    = "عادی01"
	goldDown  = "پایین02"
	goldFund  = "اهرم‌ب"
	goldShort = "کم‌سابقه11"
	goldNo    = "بی‌معامله04"
	goldDual  = "عادی 01"
)

func copyFixture(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		raw, err := os.ReadFile(filepath.Join("testdata", "fixture", name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, name), raw, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func openService(t *testing.T, scenario string) *Service {
	t.Helper()
	dir := copyFixture(t)
	switch scenario {
	case "s2":
		h, err := db.Open(dir, false)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := h.Market.Exec("DROP TABLE order_book"); err != nil {
			t.Fatal(err)
		}
		h.Close()
	case "s3":
		writeJSON(t, filepath.Join(dir, "fts_thresholds.json"), map[string]any{
			"hourglass_rsi_period": 5, "hourglass_rsi_oversold": 40.0,
			"hourglass_ma52_position": "above"})
	case "s4":
		writeJSON(t, filepath.Join(dir, "price_basis.json"), map[string]any{"basis": "closing"})
	case "s5":
		writeJSON(t, filepath.Join(dir, "fts_thresholds.json"), map[string]any{
			"hourglass_rsi_period": 5, "hourglass_rsi_oversold": 40.0,
			"hourglass_ma52_position": "either"})
	}
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	if scenario == "s6" {
		// بازبینیِ B3: قیمتِ سبد باید از کلیدِ کش بیرون بیاید و به موتورِ خروج
		// برسد؛ این صحنه تنها جایی است که hint بر کفِ ساختاری می‌چربد.
		if _, err := h.User.Exec("UPDATE selection_decisions SET price = 3000 "+
			"WHERE symbol = ?", goldUp); err != nil {
			t.Fatal(err)
		}
	}
	s := New(Config{
		Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: filepath.Join("testdata", "fixture", "calendar", "cache.json"),
		Clock:        func() time.Time { return time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local) },
	})
	t.Cleanup(func() { s.Close(); h.Close() })
	return s
}

func writeJSON(t *testing.T, path string, v any) {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

func loadGolden(t *testing.T, scenario, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", scenario, name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func compareGolden(t *testing.T, label string, want map[string]any, got any) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal body: %v", label, err)
	}
	var norm map[string]any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal body: %v", label, err)
	}
	res := parity.Compare(want, norm, parity.Options{})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", label, d)
		}
	}
}

type goldenCase struct {
	scenario, name string
	run            func(s *Service) map[string]any
}

func TestChartGoldens(t *testing.T) {
	ctx := context.Background()
	cases := []goldenCase{
		{"s1", "keylevels_uptrend", func(s *Service) map[string]any { return s.keyLevelsBody(ctx, goldUp) }},
		{"s1", "keylevels_short", func(s *Service) map[string]any { return s.keyLevelsBody(ctx, goldShort) }},
		{"s1", "keylevels_nodata", func(s *Service) map[string]any { return s.keyLevelsBody(ctx, goldNo) }},
		{"s1", "ma_uptrend", func(s *Service) map[string]any { return s.maBody(ctx, goldUp, 730) }},
		{"s1", "ma_downtrend", func(s *Service) map[string]any { return s.maBody(ctx, goldDown, 730) }},
		{"s1", "ma_short", func(s *Service) map[string]any { return s.maBody(ctx, goldShort, 730) }},
		{"s1", "patterns_uptrend", func(s *Service) map[string]any { return s.patternsBody(ctx, goldUp) }},
		{"s1", "patterns_short", func(s *Service) map[string]any { return s.patternsBody(ctx, goldShort) }},
		{"s1", "orderbook_five", func(s *Service) map[string]any { return s.orderBookBody(ctx, goldUp) }},
		{"s1", "orderbook_null", func(s *Service) map[string]any { return s.orderBookBody(ctx, goldDown) }},
		{"s1", "orderbook_missing", func(s *Service) map[string]any { return s.orderBookBody(ctx, goldNo) }},
		{"s1", "calendar_symbol", func(s *Service) map[string]any { return s.calendarSymbolBody(goldUp) }},
		{"s1", "calendar_upcoming", func(s *Service) map[string]any { return s.calendarUpcomingBody(14) }},
		{"s1", "chartdb_uptrend", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldUp, 3) }},
		{"s1", "chartdb_downtrend", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldDown, 3) }},
		{"s1", "chartdb_fund", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldFund, 3) }},
		{"s1", "chartdb_short", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldShort, 3) }},
		{"s1", "chartdb_nodata", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldNo, 3) }},
		{"s1", "chartdb_dualspell", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldDual, 3) }},
		{"s1", "fts_uptrend", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldUp, "") }},
		{"s1", "fts_downtrend", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldDown, "") }},
		{"s1", "fts_short", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldShort, "") }},
		{"s1", "fts_nodata", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldNo, "") }},
		{"s1", "fts_asof", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldUp, "2026-09-01") }},
		{"s3", "fts_uptrend", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldUp, "") }},
		{"s3", "chartdb_uptrend", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldUp, 3) }},
		{"s4", "chartdb_uptrend", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldUp, 3) }},
		{"s5", "fts_uptrend", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldUp, "") }},
		{"s5", "fts_downtrend", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldDown, "") }},
		{"s5", "chartdb_uptrend", func(s *Service) map[string]any { return s.chartDBBody(ctx, goldUp, 3) }},
		{"s6", "fts_basket_high", func(s *Service) map[string]any { return s.analyzeSymbol(ctx, goldUp, "") }},
		{"s2", "orderbook_five", func(s *Service) map[string]any { return s.orderBookBody(ctx, goldUp) }},
		{"s2", "orderbook_null", func(s *Service) map[string]any { return s.orderBookBody(ctx, goldDown) }},
		{"s4", "keylevels_uptrend", func(s *Service) map[string]any { return s.keyLevelsBody(ctx, goldUp) }},
		{"s4", "ma_uptrend", func(s *Service) map[string]any { return s.maBody(ctx, goldUp, 730) }},
		{"s4", "patterns_uptrend", func(s *Service) map[string]any { return s.patternsBody(ctx, goldUp) }},
	}
	services := map[string]*Service{}
	for _, c := range cases {
		s := services[c.scenario]
		if s == nil {
			s = openService(t, c.scenario)
			services[c.scenario] = s
		}
		compareGolden(t, c.scenario+"/"+c.name, loadGolden(t, c.scenario, c.name), c.run(s))
	}
}
