package chart

import (
	"context"
	"path/filepath"

	"borsterminal/backend/internal/pricebasis"
	"strings"
	"testing"
	"time"
)

func TestDEvenToDate(t *testing.T) {
	cases := []struct {
		in   any
		want string
	}{
		{int64(20261028), "2026-10-28"},
		{"20261028", "2026-10-28"},
		{" 20261028 ", "2026-10-28"},
		{nil, ""},
		{"2026102", ""},
		{"2026102a", ""},
		{float64(20261028), "2026-10-28"},
	}
	for _, c := range cases {
		if got := dEvenToDate(c.in); got != c.want {
			t.Errorf("dEvenToDate(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestFactorsFromEvents(t *testing.T) {
	times := []string{"2025-01-01", "2025-06-01", "2025-06-16", "2025-09-11", "2025-10-01"}
	evs := []adjustEvent{
		{Date: "2025-09-10", Ratio: 0.95},
		{Date: "2025-06-15", Ratio: 0.90},
	}
	got := factorsFromEvents(times, evs)
	// رویداد «date > t» و روزِ خودِ رویداد خام: ۰۹-۱۰ دیگر رویِ ۰۹-۱۱ اثر ندارد.
	want := []float64{0.855, 0.855, 0.95, 1.0, 1.0}
	for i := range want {
		if diff := got[i] - want[i]; diff > 1e-12 || diff < -1e-12 {
			t.Errorf("factor[%d] = %v, want %v", i, got[i], want[i])
		}
	}
	if f := factorsFromEvents([]string{"2025-01-01"}, nil); f[0] != 1.0 {
		t.Errorf("no events must leave factor 1.0, got %v", f[0])
	}
}

// TestScaleCandlesFloors سه ستونِ جدا، سه ضریبِ جدا: closing لنگر است، last
// ستونِ خودش می‌ماند و close فقط از ریزالویِ مبنا می‌آید.
func TestScaleCandlesFloors(t *testing.T) {
	s := openService(t, "s1")
	rows := []map[string]any{
		{"time": "2025-08-06", "open": 1000.7, "high": 1010.4, "low": 990.2,
			"close": 1005.9, "last": 1006.3, "volume": 100.0},
	}
	facts := []map[string]any{{"time": "2025-08-06", "factor": 0.9}}
	vols := []map[string]any{{"time": "2025-08-06", "value": 250.0}}
	c := s.scaleCandles(rows, facts, vols, pricebasis.Last)[0]
	if c["open"] != 901.0 || c["high"] != 909.0 || c["low"] != 891.0 {
		t.Fatalf("geometry = %v/%v/%v, want 901/909/891", c["open"], c["high"], c["low"])
	}
	// closing و last هر کدام ×kِ مستقل‌اند (۱۰۰۵٫۹×۰٫۹=۹۰۵٫۳۱ ⇒ ۹۰۵؛ ۱۰۰۶٫۳×۰٫۹=۹۰۵٫۶۷ ⇒ ۹۰۶)
	if c["closing"] != 905.0 || c["last"] != 906.0 || c["close"] != 906.0 {
		t.Fatalf("price columns = closing %v last %v close %v, want 905/906/906",
			c["closing"], c["last"], c["close"])
	}
	if c["volume"] != 278.0 {
		t.Fatalf("volume = %v, want 278 (250÷0.9)", c["volume"])
	}
	one := s.scaleCandles(rows, []map[string]any{{"time": "2025-08-06", "factor": 0}}, nil, pricebasis.Last)
	if one[0]["closing"] != 1006.0 || one[0]["volume"] != 100.0 {
		t.Fatalf("factor<=0 must fall back to 1.0: %v", one[0])
	}
}

// TestAsOfIsARealCutoff دادهٔ بعد از T نه در رأیِ T اثر می‌کند و نه در کشِ آن.
func TestAsOfIsARealCutoff(t *testing.T) {
	ctx := context.Background()
	s := openService(t, "s1")
	live := s.analyzeSymbol(ctx, goldUp, "")
	cut := s.analyzeSymbol(ctx, goldUp, "2026-09-01")
	if live["status"] != "success" || cut["status"] != "success" {
		t.Fatalf("status = %v / %v", live["status"], cut["status"])
	}
	if live["bars"] == cut["bars"] {
		t.Fatalf("bars did not move: %v", live["bars"])
	}
	if cut["bars"] != 280 || live["bars"] != 321 {
		t.Fatalf("bars = %v (want 280) vs live %v (want 321)", cut["bars"], live["bars"])
	}
	if cut["as_of"] != "2026-09-01" {
		t.Fatalf("as_of = %v", cut["as_of"])
	}
	if _, ok := live["as_of"]; ok {
		t.Fatal("live payload must not carry as_of")
	}
	cutStatus := asMap(asMap(cut["fts"])["status"])["code"]
	liveStatus := asMap(asMap(live["fts"])["status"])["code"]
	cutJet := asMap(asMap(cut["fts"])["jet"])["tier"]
	liveJet := asMap(asMap(live["fts"])["jet"])["tier"]
	if cutStatus == liveStatus && cutJet == liveJet {
		t.Fatalf("the cutoff moved no verdict: %v/%v", cutStatus, cutJet)
	}
	older := s.analyzeSymbol(ctx, goldUp, "2026-08-01")
	if older["bars"] == cut["bars"] {
		t.Fatalf("two cutoffs served the same payload: %v", older["bars"])
	}
	keys := ftsCacheKeys(s)
	if len(keys) != 3 {
		t.Fatalf("cache keys = %v, want three separate cutoffs", keys)
	}
	for _, k := range keys {
		if !strings.Contains(k, "|asof=") {
			t.Fatalf("cache key lost the cutoff: %s", k)
		}
	}
}

// TestEntryHintDrivesHardStop حدِ ضرر «۵٪ زیرِ قیمتِ خرید» را از سبد می‌خواند —
// و فقط وقتی که واقعاً نزدیک‌تر از کفِ ساختاری باشد (هر کدام که بالاتر است).
func TestEntryHintDrivesHardStop(t *testing.T) {
	s := openService(t, "s1")
	if got := s.basketEntry(goldUp); got == nil || *got != 1500.0 {
		t.Fatalf("basket entry for the accept row = %v, want 1500", got)
	}
	if got := s.basketEntry(goldDown); got != nil {
		t.Fatalf("a rejected basket row must give no entry price, got %v", got)
	}
	if got := s.basketEntry(goldShort); got != nil {
		t.Fatalf("price 0 must give no entry price, got %v", got)
	}
	candles := cleanCandles(mustRows(t, s, goldUp))
	noHint := exitLayer1(candles, nil)
	lowStop, _ := noHint["hard_stop"].(float64)
	if noHint["stop_basis"] != "swing_low" {
		t.Fatalf("without a hint the stop must sit on the swing low: %v", noHint["stop_basis"])
	}
	high := 3000.0
	withHint := exitLayer1(candles, &high)
	if withHint["stop_basis"] != "entry" {
		t.Fatalf("stop_basis = %v, want entry", withHint["stop_basis"])
	}
	if got, _ := withHint["hard_stop"].(float64); got != 2850.0 {
		t.Fatalf("hard_stop = %v, want 2850 (3000×0.95)", got)
	}
	// خریدِ ارزان‌تر از کفِ ساختاری ⇒ موتور همان کف را نگه می‌دارد، نه عددِ سبد.
	cheap := 900.0
	below := exitLayer1(candles, &cheap)
	if below["stop_basis"] != "swing_low" || below["hard_stop"] != lowStop {
		t.Fatalf("a hint below the swing low must not move the stop: %v vs %v",
			below["hard_stop"], lowStop)
	}
}

func mustRows(t *testing.T, s *Service, symbol string) []map[string]any {
	t.Helper()
	rows, err := s.priceHistoryFull(context.Background(), symbol)
	if err != nil {
		t.Fatal(err)
	}
	return rows
}

// TestCachedAnalysisNeverCrossServesTheBasket کلیدِ کش entry_hint را حمل می‌کند؛
// بی‌سبد و سبددار دو داوریِ جدا می‌گیرند.
func TestCachedAnalysisNeverCrossServesTheBasket(t *testing.T) {
	ctx := context.Background()
	s := openService(t, "s1")
	withBasket := s.analyzeSymbol(ctx, goldUp, "")
	if asMap(asMap(withBasket["fts"])["exit_engine"])["l1"].(map[string]any)["stop_basis"] != "swing_low" {
		t.Fatal("the fixture basket price sits below the swing low, so the swing low must win")
	}
	if _, err := s.user.Exec("DELETE FROM selection_decisions WHERE symbol = ?", goldUp); err != nil {
		t.Fatal(err)
	}
	fresh := New(Config{
		Market: s.market, User: s.user, DataDir: s.dataDir,
		CalendarPath: s.calendarPath,
		Clock:        func() time.Time { return time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local) },
	})
	defer fresh.Close()
	fresh.analyzeSymbol(ctx, goldUp, "")
	s.analyzeSymbol(ctx, goldUp, "")
	keys := strings.Join(ftsCacheKeys(s), " ")
	if !strings.Contains(keys, "|1500.0|") || !strings.Contains(keys, "|None|") {
		t.Fatalf("cache keys must separate the two entry hints: %s", keys)
	}
}

// TestHourglassSettingMovesTheVerdict تنظیمِ تازه نباید پشتِ کشِ ۹۰۰ ثانیه‌ای بماند.
func TestHourglassSettingMovesTheVerdict(t *testing.T) {
	ctx := context.Background()
	s := openService(t, "s1")
	before := asMap(s.analyzeSymbol(ctx, goldUp, "")["fts"])["hourglass"].(map[string]any)
	if before["rsi_period"] != 7 || before["ma52_position_mode"] != "below" {
		t.Fatalf("defaults = %v", before)
	}
	writeJSON(t, filepath.Join(s.dataDir, "fts_thresholds.json"), map[string]any{
		"hourglass_rsi_period": 5, "hourglass_rsi_oversold": 40.0,
		"hourglass_ma52_position": "above"})
	after := asMap(s.analyzeSymbol(ctx, goldUp, "")["fts"])["hourglass"].(map[string]any)
	if after["rsi_period"] != 5 || after["rsi_oversold"] != 40.0 || after["ma52_position_mode"] != "above" {
		t.Fatalf("settings did not reach the payload: %v", after)
	}
	if after["weekly_rsi"] == before["weekly_rsi"] {
		t.Fatalf("RSI(5) must differ from RSI(7): %v", after["weekly_rsi"])
	}
	// آستانهٔ بیرونِ بازه ⇒ همان پیش‌فرض (قاعدۀ پایتون).
	writeJSON(t, filepath.Join(s.dataDir, "fts_thresholds.json"), map[string]any{
		"hourglass_rsi_period": 200, "hourglass_rsi_oversold": 90.0,
		"hourglass_ma52_position": "sideways"})
	back := asMap(s.analyzeSymbol(ctx, goldUp, "")["fts"])["hourglass"].(map[string]any)
	if back["rsi_period"] != 7 || back["rsi_oversold"] != 30.0 || back["ma52_position_mode"] != "below" {
		t.Fatalf("out-of-range settings must fall back: %v", back)
	}
}

// TestTrendEngineFlagIsHonored هر دو موتورِ روند پورت‌شده‌اند و درِ پاسخ اعلام
// می‌شوند؛ کلیدِ کش هم نامِ موتور را حمل می‌کند.
func TestTrendEngineFlagIsHonored(t *testing.T) {
	t.Setenv("BORS_TREND_ENGINE", "hybrid")
	s := openService(t, "s1")
	res := s.analyzeSymbol(context.Background(), goldUp, "")
	if res["trend_engine"] != "hybrid" {
		t.Fatalf("trend_engine = %v", res["trend_engine"])
	}
	trend := asMap(res["fts"])["trend"].(map[string]any)
	d := trend["D"].(map[string]any)
	if d["basis"] != "hybrid" {
		t.Fatalf("D basis = %v, want hybrid", d["basis"])
	}
	if _, ok := d["confidence"]; !ok {
		t.Fatal("hybrid must carry the audit keys")
	}
	for _, k := range ftsCacheKeys(s) {
		if !strings.Contains(k, "eng=hybrid") {
			t.Fatalf("cache key must carry the engine: %s", k)
		}
	}
	t.Setenv("BORS_TREND_ENGINE", "")
	legacy := New(Config{Market: s.market, User: s.user, DataDir: s.dataDir,
		CalendarPath: s.calendarPath})
	defer legacy.Close()
	if legacy.analyzeSymbol(context.Background(), goldUp, "")["trend_engine"] != "legacy" {
		t.Fatal("empty env must mean legacy")
	}
}
