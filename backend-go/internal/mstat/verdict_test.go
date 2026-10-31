package mstat

import (
	"math"
	"strings"
	"testing"

	"borsterminal/backend/internal/marketphase"
)

func gateByKey(v map[string]any, key string) map[string]any {
	for _, g := range v["gates"].([]map[string]any) {
		if g["key"] == key {
			return g
		}
	}
	return nil
}

// verdictInputs بدنهٔ مصنوعیِ smart_money برایِ سنجشِ درهایِ حکم؛ هیچ عددی از
// بانک نمی‌آید جز تاریخچه/نقطه‌هایی که خودِ تست لازم دارد.
func verdictInputs(valueHemat any, bearPct any, active bool, eq, fx float64,
	gold any, partial bool) (macro, entry, flow map[string]any) {
	macro = map[string]any{
		"value_hemat": valueHemat, "state": "bad", "label": "نامساعد",
		"basis": "eq_all", "excellent": false, "good_min": 20.0, "bad_max": 10.0,
		"partial_session": partial, "trade_value_all_market_hemat": 1.13,
		"market_value_hemat": 6.9,
	}
	entry = map[string]any{"active": active, "bearish_pct": bearPct,
		"rule_pct": 80.0, "bearish": 4, "known": 10}
	flow = map[string]any{"eq_flow_b_toman": eq, "fixed_flow_b_toman": fx,
		"eq_inflow": eq > 0, "fixed_outflow": fx < 0,
		"gold_flow_b_toman": gold, "gold_outflow": nil}
	if gold != nil {
		flow["gold_outflow"] = gold.(float64) < 0
	}
	return macro, entry, flow
}

func asofAt(h int64) map[string]any {
	return map[string]any{"h_even": h, "d_even": int64(20261014),
		"client_d_even": int64(20261014), "client_lag_days": false,
		"depth": true, "top50": 2, "n": 38}
}

func continuousPhase(day int64) marketphase.Phase {
	return marketphase.Phase{
		Phase: marketphase.Continuous, Label: "معاملات جاری",
		PhaseSource: "tsetmc_marketState", Official: true,
		SessionDay: &day, IsLive: true, VerdictAllowed: true,
		Computable: map[string]bool{"realized_flow": true, "order_pressure": true,
			"session_vs_threshold": true, "close_price_final": false},
		WhyNot: map[string]string{},
	}
}

// TestDayVerdictConfirmStreak: حکمِ منفی فقط پس از سه ارزیابیِ معتبرِ متوالی
// رویِ دادهٔ تازه قاطع می‌شود؛ تکرارِ همان h_even مشاهدهٔ تازه نیست.
func TestDayVerdictConfirmStreak(t *testing.T) {
	h := openFixture(t)
	ph := marketphase.FromDB(h.Market, pinnedNow)
	macro, entry, flow := verdictInputs(5.0, 40.0, false, -5.0, 1.0, nil, false)
	memo := newVerdictMemo()

	call := func(hEven int64) map[string]any {
		return dayVerdict(h.Market, macro, entry, flow, asofAt(hEven), ph, memo)
	}
	v1 := call(124000)
	if v1["verdict"] != "nodata" || v1["label"] != "شواهدِ اولیهٔ منفی — هنوز تأیید نشده" {
		t.Fatalf("first = %v / %v", v1["verdict"], v1["label"])
	}
	if s := v1["market_state"].(map[string]any)["confirm_streak"]; s != 1 {
		t.Fatalf("streak after first = %v, want 1", s)
	}
	if !strings.Contains(v1["reason"].(string), "ارزیابیِ معتبرِ متوالی: ۱ از ۳") {
		t.Fatalf("reason = %q", v1["reason"])
	}
	// همان ساعت دوباره: نه شمارش، نه حکمِ تازه.
	v1b := call(124000)
	if s := v1b["market_state"].(map[string]any)["confirm_streak"]; s != 1 {
		t.Fatalf("same h_even incremented streak to %v", s)
	}
	v2 := call(125000)
	if s := v2["market_state"].(map[string]any)["confirm_streak"]; s != 2 {
		t.Fatalf("streak after second fresh point = %v, want 2", s)
	}
	v3 := call(126000)
	if v3["verdict"] != "avoid" || v3["label"] != "امروز وارد نشو" {
		t.Fatalf("third = %v / %v, want avoid", v3["verdict"], v3["label"])
	}
	ms := v3["market_state"].(map[string]any)
	if ms["confirm_streak"] != 3 || ms["evidence_strength"] != "قابل‌اتکا (جمعِ نهایی)" {
		t.Fatalf("market_state = streak %v strength %v", ms["confirm_streak"], ms["evidence_strength"])
	}
	if ms["changed_from"] != "nodata" {
		t.Fatalf("changed_from = %v, want nodata", ms["changed_from"])
	}
	if len(ms["against"].([]string)) != 2 {
		t.Fatalf("against = %v, want liquidity+flow", ms["against"])
	}
}

// TestDayVerdictPositiveResetsStreak: شاهدِ مخالفِ تازه شمارشِ تأیید را صفر می‌کند.
func TestDayVerdictPositiveResetsStreak(t *testing.T) {
	h := openFixture(t)
	ph := marketphase.FromDB(h.Market, pinnedNow)
	memo := newVerdictMemo()
	badMacro, badEntry, badFlow := verdictInputs(5.0, 40.0, false, -5.0, 1.0, nil, false)
	if v := dayVerdict(h.Market, badMacro, badEntry, badFlow, asofAt(124000), ph, memo); v["verdict"] != "nodata" {
		t.Fatalf("avoid seed = %v", v["verdict"])
	}
	goodMacro, goodEntry, goodFlow := verdictInputs(25.0, 40.0, false, 5.0, -2.0, -1.0, false)
	goodMacro["excellent"] = false
	if v := dayVerdict(h.Market, goodMacro, goodEntry, goodFlow, asofAt(125000), ph, memo); v["verdict"] != "go" {
		t.Fatalf("positive verdict = %v (%v)", v["verdict"], v["label"])
	}
	v := dayVerdict(h.Market, badMacro, badEntry, badFlow, asofAt(126000), ph, memo)
	if s := v["market_state"].(map[string]any)["confirm_streak"]; s != 1 {
		t.Fatalf("streak after positive reset = %v, want 1", s)
	}
}

// TestDayVerdictForming: در نشستِ جاری، بی‌نقطهٔ معتبرِ امروز، حکمِ منفی صادر
// نمی‌شود و مرحل «forming» است — نه risky.
func TestDayVerdictForming(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec("DELETE FROM mstat_snap"); err != nil {
		t.Fatal(err)
	}
	ph := continuousPhase(20261014)
	macro, entry, flow := verdictInputs(5.0, 40.0, false, -5.0, 1.0, nil, true)
	v := dayVerdict(h.Market, macro, entry, flow, asofAt(124000), ph, newVerdictMemo())
	ms := v["market_state"].(map[string]any)
	if ms["stage"] != "forming" || v["verdict"] != "nodata" {
		t.Fatalf("stage=%v verdict=%v", ms["stage"], v["verdict"])
	}
	if !strings.Contains(v["reason"].(string), "بازار در دورۀ شکل‌گیریِ داده است") {
		t.Fatalf("reason = %q", v["reason"])
	}
	if ms["session_start_clock"] != nil || ms["minutes_since_open"] != nil {
		t.Fatalf("forming start/since = %v / %v, want nil", ms["session_start_clock"], ms["minutes_since_open"])
	}
	// جمعِ تا-لحظه: قرمزِ نقدینگی هنوز «نامساعد» نیست.
	if g := gateByKey(v, "liquidity"); g["state"] != "mid" || g["label_state"] != "هنوز نه‌شده" {
		t.Fatalf("liquidity gate = %v / %v", g["state"], g["label_state"])
	}
}

// TestDayVerdictNotAllowed: مرحلِ ناشناخته هیچ حکمی نمی‌دهد، حتی با شاهدِ منفی.
func TestDayVerdictNotAllowed(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`UPDATE market_index SET market_state=NULL,
		market_state_title=NULL`); err != nil {
		t.Fatal(err)
	}
	ph := marketphase.FromDB(h.Market, pinnedNow)
	if ph.Phase != marketphase.Unknown || ph.VerdictAllowed {
		t.Fatalf("phase = %v allowed=%v", ph.Phase, ph.VerdictAllowed)
	}
	macro, entry, flow := verdictInputs(5.0, 90.0, true, -5.0, 1.0, nil, false)
	v := dayVerdict(h.Market, macro, entry, flow, asofAt(124000), ph, newVerdictMemo())
	if v["verdict"] != "nodata" || v["label"] != "بدونِ حکم — مرحل نامشخص" {
		t.Fatalf("verdict = %v / %v", v["verdict"], v["label"])
	}
	ms := v["market_state"].(map[string]any)
	if ms["stage"] != "data_limited" || ms["confirm_streak"] != 0 {
		t.Fatalf("market_state = %v / streak %v", ms["stage"], ms["confirm_streak"])
	}
	if len(ms["limitations"].([]string)) != len(ph.NotComputable) {
		t.Fatalf("limitations = %v", ms["limitations"])
	}
}

// TestDayVerdictMixedGates: یک درِ مثبت و دو درِ منفی ⇒ «صبر»؛ پنجرهٔ ساعت هم
// از h_even خوانده می‌شود (۰۹:۰۰ پنجرهٔ درآمد ثابت)، نه از ساعتِ دیوار.
func TestDayVerdictMixedGates(t *testing.T) {
	h := openFixture(t)
	ph := marketphase.FromDB(h.Market, pinnedNow)
	macro, entry, flow := verdictInputs(5.0, 85.0, true, -5.0, 1.0, nil, false)
	v := dayVerdict(h.Market, macro, entry, flow, asofAt(90000), ph, newVerdictMemo())
	if v["verdict"] != "wait" || v["label"] != "صبر — نشانه‌ها مخالف‌اند" {
		t.Fatalf("verdict = %v / %v", v["verdict"], v["label"])
	}
	if g := gateByKey(v, "breadth"); g["vote"] != 1 || g["state"] != "ok" {
		t.Fatalf("breadth = %v", g)
	}
	if g := gateByKey(v, "window"); g["state"] != "ok" || g["vote"] != 0 {
		t.Fatalf("window = %v", g)
	}
	if !strings.Contains(v["reason"].(string), "موافقِ ورود — پهنایِ بازار: فرصتِ ورود") {
		t.Fatalf("reason = %q", v["reason"])
	}
}

// TestDayVerdictBlockedFlow: بی‌تفکیکِ به‌روزِ حقیقی، درِ پول «بدون داده» است
// و متنِ علت از phase می‌آید — «خروج» از نبودِ داده ساخته نمی‌شود.
func TestDayVerdictBlockedFlow(t *testing.T) {
	h := openFixture(t)
	ph := marketphase.FromDB(h.Market, pinnedNow)
	ph.Computable["realized_flow"] = false
	ph.WhyNot["realized_flow"] = "هنوز معامله‌ای ثبت نشده"
	macro, entry, flow := verdictInputs(5.0, 40.0, false, -5.0, 1.0, nil, false)
	v := dayVerdict(h.Market, macro, entry, flow, asofAt(124000), ph, newVerdictMemo())
	g := gateByKey(v, "flow")
	if g["state"] != "nodata" || g["vote"] != 0 {
		t.Fatalf("flow gate = %v", g)
	}
	if g["detail"] != "هنوز معامله‌ای ثبت نشده" {
		t.Fatalf("flow detail = %v", g["detail"])
	}
}

// TestDayVerdictContinuity: سه نشستِ یک‌جهت، درِ تداوم را می‌بندد؛ و عددِ
// نهاییِ daily_prices فقط با آستانهٔ نمادها معتبر است (اینجا زیرِ آستانه).
func TestDayVerdictContinuity(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`DELETE FROM market_liquidity`); err != nil {
		t.Fatal(err)
	}
	for _, row := range []struct {
		day int64
		v   float64
	}{{20261014, 25}, {20261013, 25}, {20261012, 25}} {
		if _, err := h.Market.Exec(`INSERT INTO market_liquidity (d_even, value_hemat)
			VALUES (?, ?)`, row.day, row.v); err != nil {
			t.Fatal(err)
		}
	}
	ph := marketphase.FromDB(h.Market, pinnedNow)
	macro, entry, flow := verdictInputs(25.0, 40.0, false, 5.0, -2.0, -1.0, false)
	v := dayVerdict(h.Market, macro, entry, flow, asofAt(124000), ph, newVerdictMemo())
	g := gateByKey(v, "continuity")
	if g["state"] != "ok" || g["vote"] != 1 || g["label_state"] != "تداومِ مساعد" {
		t.Fatalf("continuity = %v", g)
	}
	if v["verdict"] != "go" {
		t.Fatalf("verdict = %v (%v)", v["verdict"], v["label"])
	}
}

func TestLiquidityFromPriceHistory(t *testing.T) {
	h := openWritableFixture(t)
	got := liquidityFromPriceHistory(h.Market, []int{20261013, 20261012}, 1)
	if len(got) != 2 || got[0]["d_even"] != 20261013 || got[1]["d_even"] != 20261012 {
		t.Fatalf("rows = %v", got)
	}
	// 750e9/1e13 = 0.075 و round(0.075,2)ِ پایتون 0.07 است (دودویی).
	if v := got[0]["value_hemat"].(float64); v != 0.07 {
		t.Fatalf("20261013 = %v, want 0.07 (750e9/1e13)", v)
	}
	if got := liquidityFromPriceHistory(h.Market, []int{20261013}, 2); len(got) != 0 {
		t.Fatalf("under-threshold day kept: %v", got)
	}
}

func TestLiquidityHistoryOrderAndLimit(t *testing.T) {
	h := openFixture(t)
	got := liquidityHistory(h.Market, 2)
	if len(got) != 2 || got[0]["d_even"] != 20261014 || got[1]["d_even"] != 20261013 {
		t.Fatalf("history = %v", got)
	}
	if got[0]["value_hemat"] != 18.0 || got[1]["value_hemat"] != 12.0 {
		t.Fatalf("values = %v / %v", got[0]["value_hemat"], got[1]["value_hemat"])
	}
}

func TestClockWindow(t *testing.T) {
	cases := []struct {
		h     any
		state string
		label string
	}{
		{int64(90000), "ok", "پنجرهٔ درآمد ثابت باز است"},
		// ۰۸:۵۵ آغازِ پنجرهٔ رسمیِ معاملات است، نه پنجرهٔ جزوه (۰۹:۰۰).
		{int64(85500), "mid", "خارجِ پنجره‌ها"},
		{int64(93000), "mid", "خارجِ پنجره‌ها"},
		{int64(100000), "mid", "خارجِ پنجره‌ها"},
		{int64(123000), "ok", "پنجرهٔ شفافیتِ طلا"},
		{nil, "nodata", "بدون داده"},
		{int64(0), "nodata", "بدون داده"},
	}
	for _, c := range cases {
		got := clockWindow(c.h)
		if got["state"] != c.state || got["label"] != c.label {
			t.Errorf("clockWindow(%v) = %v/%v, want %v/%v", c.h, got["state"], got["label"], c.state, c.label)
		}
	}
}

// TestFaNum و TestFaSigned: همان «%.2f»ِ پایتون با صفرهایِ زائد و ارقامِ فارسی؛
// نیم‌گردکردنِ دودویی (۰٫۱۲۵ ⇒ ۰٫۱۲) هم باید یکی بماند.
func TestFaNum(t *testing.T) {
	cases := []struct {
		in   any
		want string
	}{
		{0.125, "۰.۱۲"}, {0.135, "۰.۱۴"}, {2.675, "۲.۶۷"}, {2.665, "۲.۶۷"},
		{1.005, "۱"}, {33.3, "۳۳.۳"}, {1234.0, "۱۲۳۴"}, {0.0, "۰"},
		{math.Copysign(0, -1), "-۰"}, {-1.5, "-۱.۵"}, {99.995, "۱۰۰"}, {nil, "—"},
		{int64(3), "۳"}, {int(7), "۷"},
	}
	for _, c := range cases {
		if got := faNum(c.in); got != c.want {
			t.Errorf("faNum(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestFaSigned(t *testing.T) {
	cases := []struct {
		in   any
		want string
	}{
		{2.5, "+۲.۵"}, {-2.5, "−۲.۵"}, {0.0, "۰"}, {nil, "بدون داده"},
	}
	for _, c := range cases {
		if got := faSigned(c.in); got != c.want {
			t.Errorf("faSigned(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}
