package chart

import (
	"strings"
	"testing"
	"time"
)

// این فایل قواعدِ حیاتی را به منبعشان گره می‌زند؛ وکتورهایِ اوراکل (پایتون)
// رفتار را می‌سنجند و اینجا هر قاعده مستقل نام‌دار است تا پوشش قابلِ‌ردیابی باشد.

func boolPtr(v bool) *bool { return &v }

// قاعدهٔ اکیدِ پیوت (api/chart.py:3990-4011): دو طرفِ مساوی پیوت نمی‌سازد،
// ولی دو سرِ یک فلات می‌مانند؛ سریِ کاملاً تخت صفر پیوت دارد.
func TestRuleStrictPivot(t *testing.T) {
	flat := make([]candle, 40)
	for i := range flat {
		flat[i] = candle{Time: "2026-01-01", Open: 1000, High: 1000, Low: 1000, Close: 1000}
	}
	if got := swingsOf(flat, 3); len(got) != 0 {
		t.Fatalf("flat series must yield 0 pivots, got %d", len(got))
	}

	plateau := make([]candle, 60)
	for i := range plateau {
		plateau[i] = candle{Open: 1050, High: 1060, Low: 1040, Close: 1050}
	}
	for i := 20; i <= 30; i++ {
		plateau[i] = candle{Open: 1150, High: 1200, Low: 1150, Close: 1170}
	}
	highs := []int{}
	for _, s := range swingsOf(plateau, 3) {
		if s.Kind == "high" {
			highs = append(highs, s.Idx)
		}
	}
	if len(highs) != 2 || highs[0] != 20 || highs[1] != 30 {
		t.Fatalf("plateau highs=%v, want [20 30]", highs)
	}
}

// anti-repaint (major_swings.closed_only): کندلِ تکمیل‌نشده در ساختارِ جهت
// نمی‌نشیند، هرچند همان ردیف زیرِ provisional گزارش می‌شود.
func TestRuleClosedOnlyStructure(t *testing.T) {
	full := make([]candle, 29)
	for i := range full {
		full[i] = candle{Time: dayString(i), Open: 1000, High: 1010, Low: 990, Close: 1000}
	}
	full[25].High = 2000
	full[28].LiveForming = true
	swFull := swingsOf(full, 3)
	foundFull := false
	for _, s := range swFull {
		if s.Kind == "high" && s.Idx == 25 {
			foundFull = true
		}
	}
	if !foundFull {
		t.Fatalf("full series should confirm high@25 via bar 28; swings=%v", swFull)
	}
	structD := closedOnly(full)
	if len(structD) != 28 {
		t.Fatalf("closedOnly kept %d rows, want 28", len(structD))
	}
	for _, s := range swingsOf(structD, 3) {
		if s.Kind == "high" && s.Idx == 25 {
			t.Fatal("live candle must not confirm the pivot in the structure series")
		}
	}
}

// قاعدهٔ کفایتِ Extreme (major_swings.summarize + طبقه‌بند): با کمتر از دو سقف
// و دو کفِ ماژور، جهت اعلام نمی‌شود — «na»، نه حدس.
func TestRuleInsufficientMajorsYieldNA(t *testing.T) {
	graded := []gradedSwing{
		{swing: swing{Idx: 10, Kind: "high", Price: 120}, Major: boolPtr(true)},
		{swing: swing{Idx: 20, Kind: "low", Price: 80}, Major: boolPtr(true)},
		{swing: swing{Idx: 30, Kind: "high", Price: 130}, Major: boolPtr(true)},
	}
	majors, info := majorSummarize(graded)
	if pyTruthy(info["enough"]) {
		t.Fatalf("enough must be false with one major low: %v", info)
	}
	verdict := classifyTrend(majorSwingsOf(majors), ftsEqualTol, nil, ftsStaleBars)
	if verdict["trend"] != "na" {
		t.Fatalf("insufficient majors gave %q, want na", verdict["trend"])
	}
}

// وتویِ هفتگی و «ناشناخته وتو نیست» (OWNER_RULINGS ردیف‌های ۱/۱۲ و ۶۵-۶۹):
// هفتگیِ نزولی ⇒ REJECT؛ هفتگیِ na ⇒ UNKNOWN، نه REJECT.
func TestRuleWeeklyVetoAndUnknown(t *testing.T) {
	v := loadVectors(t)
	seriesMap, _ := v["series"].(map[string]any)
	svc := &Service{engine: "legacy"}
	down := svc.analyzeCandles(candlesToAny(candlesFrom(seriesMap["down"])), "down", nil)
	mx := subMap(down, "trend")["matrix"].(map[string]any)
	if mx["decision"] != "REJECT" {
		t.Fatalf("weekly down matrix=%v, want REJECT", mx)
	}
	short := svc.analyzeCandles(candlesToAny(candlesFrom(seriesMap["short"])), "short", nil)
	mxS := subMap(short, "trend")["matrix"].(map[string]any)
	if mxS["decision"] != "UNKNOWN" {
		t.Fatalf("weekly na matrix=%v, want UNKNOWN (not REJECT)", mxS)
	}
}

// خروجِ تعقیبی (FTS.CHART_3 ص۳ / جزوه ص۲۲): «یک کندلِ کامل زیرِ MA14» —
// high < MA14 همان کندلِ بسته؛ کندلِ امروز فقط pending می‌سازد.
func TestRuleMA14OneClosedCandle(t *testing.T) {
	v := loadVectors(t)
	seriesMap, _ := v["series"].(map[string]any)
	one := exitEngine(candlesFrom(seriesMap["ma14one"]), nil)
	l1 := one["l1"].(map[string]any)
	if l1["ma14_exit"] != true {
		t.Fatalf("one closed candle under MA14 must exit: l1=%v", l1)
	}
	if l1["ma14_exit_pending"] != false {
		t.Fatalf("confirmed exit must not be pending: l1=%v", l1)
	}

	// امروز کاملاً زیرِ MA14 است ولی کندلِ بستهٔ قبلی نه ⇒ فقط هشدار.
	candles := make([]candle, 0, 41)
	for i := 0; i < 40; i++ {
		c := 1000 + 2.4*float64(i)
		candles = append(candles, candle{Time: dayString(i), Open: c - 3,
			High: c + 5, Low: c - 4, Close: c})
	}
	candles = append(candles, candle{Time: dayString(40), Open: 1070, High: 1078,
		Low: 1060, Close: 1065})
	pending := exitEngine(candles, nil)["l1"].(map[string]any)
	if pending["ma14_exit"] != false || pending["ma14_exit_pending"] != true {
		t.Fatalf("forming candle must be pending only: %v", pending)
	}
}

// P0 #5: کفِ ۲۰ کندلِ بسته با کمتر از ۲۰ ردیف «در حال تشکیل» است، نه رأیِ کامل.
func TestRuleSwingLowForming(t *testing.T) {
	candles := make([]candle, 10)
	for i := range candles {
		candles[i] = candle{Time: dayString(i), Open: 1000, High: 1010,
			Low: 990 - float64(i), Close: 1000}
	}
	l1 := exitLayer1(candles, nil)
	if l1["stop_basis"] != "swing_low_forming" {
		t.Fatalf("stop_basis=%v, want swing_low_forming", l1["stop_basis"])
	}
	reason, _ := l1["stop_reason"].(string)
	if !strings.Contains(reason, "۹ از ۲۰") {
		t.Fatalf("stop_reason=%q, want count ۹ از ۲۰", reason)
	}
	if l1["stop_hit"] == nil {
		t.Fatal("stop_hit must still be measured")
	}
	if l1["hard_stop"] == nil {
		t.Fatal("hard_stop must still be published")
	}
}

// ساختارِ HH/HL با زمانِ وقوع جدا از زمانِ تأیید (anti-repaint): هر نقطه
// confirm_idx = idx+k دارد و confirm_time از همان کندلِ تأیید است.
func TestRuleStructureConfirmTime(t *testing.T) {
	v := loadVectors(t)
	seriesMap, _ := v["series"].(map[string]any)
	candles := candlesFrom(seriesMap["up"])
	svc := &Service{engine: "legacy"}
	out := svc.analyzeCandles(candlesToAny(candles), "up", nil)
	sp := subMap(out, "structure_points")
	pts, _ := sp["D"].([]map[string]any)
	if len(pts) == 0 {
		t.Fatal("uptrend must publish D structure points")
	}
	for _, p := range pts {
		idx, _ := p["idx"].(int)
		ci, _ := p["confirm_idx"].(int)
		if ci != idx+ftsSwingK {
			t.Fatalf("point idx=%d confirm_idx=%d, want idx+%d", idx, ci, ftsSwingK)
		}
		ct, _ := p["confirm_time"].(string)
		if ct == "" {
			t.Fatalf("point idx=%d missing confirm_time", idx)
		}
		if ct != candles[ci].Time {
			t.Fatalf("confirm_time=%q, want %q", ct, candles[ci].Time)
		}
	}
	if asOf, _ := subMap(out, "trend")["as_of"].(string); asOf != candles[len(candles)-1].Time {
		t.Fatalf("trend.as_of=%q, want %q", asOf, candles[len(candles)-1].Time)
	}
}

// سبدِ هفتگی/ماهانهٔ ناتمام اطلاع است، نه رأی (major_swings._bucket_forming).
func TestRuleBucketForming(t *testing.T) {
	w := []candle{{Time: "2026-10-21"}}
	dailyWithin := []candle{{Time: "2026-10-20"}}
	dailyNextWeek := []candle{{Time: "2026-10-24"}}
	dailyNextMonth := []candle{{Time: "2026-11-01"}}
	if v := bucketForming("W", w, dailyWithin); v != true {
		t.Fatalf("same-week daily must be forming, got %v", v)
	}
	if v := bucketForming("W", w, dailyNextWeek); v != false {
		t.Fatalf("next-week daily must close the bucket, got %v", v)
	}
	if v := bucketForming("M", w, dailyWithin); v != true {
		t.Fatalf("same-month daily must be forming, got %v", v)
	}
	if v := bucketForming("M", w, dailyNextMonth); v != false {
		t.Fatalf("next-month daily must close the bucket, got %v", v)
	}
	if v := bucketForming("D", w, dailyWithin); v != nil {
		t.Fatalf("daily has no bucket forming, got %v", v)
	}
}

func dayString(i int) string {
	return time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC).
		AddDate(0, 0, i).Format("2006-01-02")
}
