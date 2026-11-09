package chart

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/parity"
)

// vectors حلقهٔ اوراکلِ Task 4/5: خروجیِ خودِ پایتون رویِ سری‌هایِ ساختگی که هر
// شاخهٔ موتور را نام‌دار می‌زنند. فایل با tools/parity/gen_fts_vectors.py ساخته
// و تازگی‌اش در گاردِ B3 سنجیده می‌شود.
func loadVectors(t *testing.T) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "fts_vectors.json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func candlesFrom(v any) []candle {
	arr, _ := v.([]any)
	out := make([]candle, 0, len(arr))
	for _, item := range arr {
		m, _ := item.(map[string]any)
		o, _ := numOf(m["open"])
		h, _ := numOf(m["high"])
		l, _ := numOf(m["low"])
		c, _ := numOf(m["close"])
		vol, _ := numOf(m["volume"])
		tm, _ := m["time"].(string)
		lf, _ := m["live_forming"].(bool)
		out = append(out, candle{Time: tm, Open: o, High: h, Low: l, Close: c,
			Volume: vol, LiveForming: lf})
	}
	return out
}

// candlesToAnyFields همان تبدیلِ candlesToAny است و نشانهٔ «تکمیل‌نشده» را هم
// نگه می‌دارد؛ ورودیِ analyzeCandles باید همان چیزی باشد که پایتون دید.
func candlesToAnyFields(cs []candle) []map[string]any {
	out := candlesToAny(cs)
	for i, c := range cs {
		if c.LiveForming {
			out[i]["live_forming"] = true
		}
	}
	return out
}

func swingsToAny(sw []swing) []map[string]any {
	out := make([]map[string]any, 0, len(sw))
	for _, s := range sw {
		out = append(out, map[string]any{
			"idx": s.Idx, "price": s.Price, "kind": s.Kind, "time": s.Time,
			"confirm_idx": s.ConfirmIdx, "confirm_time": s.ConfirmTime,
		})
	}
	return out
}

func gradedToAny(gs []gradedSwing) []map[string]any {
	out := make([]map[string]any, 0, len(gs))
	for _, g := range gs {
		var major, leg, legIn, legOut, legAtr, ma100 any
		if g.Major != nil {
			major = *g.Major
		}
		if g.LegPct != nil {
			leg = *g.LegPct
		}
		if g.LegPctIn != nil {
			legIn = *g.LegPctIn
		}
		if g.LegPctOut != nil {
			legOut = *g.LegPctOut
		}
		if g.LegAtrX != nil {
			legAtr = *g.LegAtrX
		}
		if g.MA100Ctx != nil {
			ma100 = *g.MA100Ctx
		}
		out = append(out, map[string]any{
			"idx": g.Idx, "price": g.Price, "kind": g.Kind, "time": g.Time,
			"confirm_idx": g.ConfirmIdx, "confirm_time": g.ConfirmTime,
			"major": major, "leg_pct": leg, "leg_pct_in": legIn,
			"leg_pct_out": legOut, "out_pending": g.OutPending,
			"leg_atr_x": legAtr, "recent": g.Recent,
			"confirm_age_bars": g.ConfirmAgeBars, "ma100_ctx": ma100,
		})
	}
	return out
}

type tfPackTest struct {
	graded  []gradedSwing
	majors  []gradedSwing
	info    map[string]any
	series  []candle
	verdict map[string]any
}

func buildPack(series []candle, k int) tfPackTest {
	graded := majorGrade(swingsOf(series, k), series)
	majors, info := majorSummarize(graded)
	return tfPackTest{graded: graded, majors: majors, info: info, series: series,
		verdict: classifyTrend(majorSwingsOf(majors), ftsEqualTol, series, ftsStaleBars)}
}

func candlesToAny(cs []candle) []map[string]any {
	out := make([]map[string]any, 0, len(cs))
	for _, c := range cs {
		out = append(out, map[string]any{
			"time": c.Time, "open": c.Open, "high": c.High, "low": c.Low,
			"close": c.Close, "volume": c.Volume,
		})
	}
	return out
}

func ptrsToAny(v []*float64) []any {
	out := make([]any, len(v))
	for i, p := range v {
		if p != nil {
			out[i] = *p
		}
	}
	return out
}

func compareJSON(t *testing.T, label string, want, got any) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal: %v", label, err)
	}
	var norm any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal: %v", label, err)
	}
	res := parity.Compare(want, norm, parity.Options{})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", label, d)
		}
	}
}

func TestFTSVectors(t *testing.T) {
	v := loadVectors(t)
	seriesMap, _ := v["series"].(map[string]any)
	cases, _ := v["cases"].(map[string]any)
	for kind, seriesAny := range seriesMap {
		candles := candlesFrom(seriesAny)
		c, _ := cases[kind].(map[string]any)
		if c == nil {
			t.Fatalf("%s: missing case", kind)
		}
		sw := swingsOf(candles, ftsSwingK)
		w := resample(candles, "W")
		m := resample(candles, "M")
		structD := closedOnly(candles)
		wStruct := resample(structD, "W")
		mStruct := resample(structD, "M")
		packs := map[string]tfPackTest{
			"D": buildPack(structD, ftsSwingK),
			"W": buildPack(wStruct, 2),
			"M": buildPack(mStruct, 2),
		}
		label := func(k string) string { return kind + "/" + k }
		compareJSON(t, label("swings"), c["swings"], swingsToAny(sw))
		compareJSON(t, label("weekly"), c["weekly"], candlesToAny(w))
		compareJSON(t, label("monthly"), c["monthly"], candlesToAny(m))
		compareJSON(t, label("trend_d"), c["trend_d"], packs["D"].verdict)
		compareJSON(t, label("trend_w"), c["trend_w"], packs["W"].verdict)
		compareJSON(t, label("trend_m"), c["trend_m"], packs["M"].verdict)
		compareJSON(t, label("swings_w"), c["swings_w"], swingsToAny(swingsOf(wStruct, 2)))
		compareJSON(t, label("swings_m"), c["swings_m"], swingsToAny(swingsOf(mStruct, 2)))
		compareJSON(t, label("majors_d"), c["majors_d"], gradedToAny(packs["D"].graded))
		compareJSON(t, label("majors_w"), c["majors_w"], gradedToAny(packs["W"].graded))
		compareJSON(t, label("majors_m"), c["majors_m"], gradedToAny(packs["M"].graded))
		compareJSON(t, label("info_d"), c["info_d"], packs["D"].info)
		compareJSON(t, label("info_w"), c["info_w"], packs["W"].info)
		compareJSON(t, label("info_m"), c["info_m"], packs["M"].info)
		full := map[string][]candle{"D": candles, "W": w, "M": m}
		kFor := map[string]int{"D": ftsSwingK, "W": 2, "M": 2}
		ctx := map[string]map[string]any{}
		for _, tf := range []string{"D", "W", "M"} {
			p := packs[tf]
			ctx[tf] = majorContext(tf, p.graded, p.majors, p.info, p.series,
				structD, full[tf], p.verdict, kFor[tf])
		}
		compareJSON(t, label("context_d"), c["major_context_d"], ctx["D"])
		compareJSON(t, label("context_w"), c["major_context_w"], ctx["W"])
		compareJSON(t, label("context_m"), c["major_context_m"], ctx["M"])
		compareJSON(t, label("structure_d"), c["structure_points_d"],
			structurePoints(majorSwingsOf(packs["D"].majors), 14))
		compareJSON(t, label("structure_w"), c["structure_points_w"],
			structurePoints(majorSwingsOf(packs["W"].majors), 14))
		compareJSON(t, label("recent"), c["recent"], recentWindowTrend(candles, ftsStaleWindow))
		compareJSON(t, label("reason_d"), c["reason_d"],
			trendReasonCtx(packs["D"].verdict, ctx["D"]))
		compareJSON(t, label("fib"), c["fib"], fibZones(candles, sw))
		compareJSON(t, label("jet"), c["jet"], jetSetup(candles, 250, 6, 3))
		compareJSON(t, label("choch"), c["choch"], choch(candles, sw, ftsCHochDays, ftsCHochMargin))
		compareJSON(t, label("point_hunt"), c["point_hunt"], pointHunt(candles, sw))
		dbl := doubleBottom(candles, sw)
		compareJSON(t, label("double_bottom"), c["double_bottom"], dbl["double_bottom"])
		compareJSON(t, label("range_box"), c["range_box"], dbl["range_box"])
		compareJSON(t, label("setups"), c["setups"], setupHistory(candles, sw, 40))
		var hint *float64
		if kind == "up" || kind == "stop" {
			h := 1400.0
			hint = &h
		}
		compareJSON(t, label("exit"), c["exit"], exitEngine(candles, hint))
		if kind == "up" {
			// تساویِ حدِ ضرر رویِ کفِ ساختاری: پایتون «entry» را برمی‌دارد.
			low, _ := c["exit_tie_low"].(float64)
			l1 := asMap(exitEngine(candles, &low))["l1"].(map[string]any)
			compareJSON(t, label("exit_tie"), c["exit_tie"], l1["stop_basis"])
		}
		closes := make([]float64, len(candles))
		for i, cc := range candles {
			closes[i] = cc.Close
		}
		compareJSON(t, label("ma14"), c["ma14"], ptrsToAny(ftsMa(closes, 14)))
		compareJSON(t, label("rsi14"), c["rsi14"], ptrsToAny(ftsRsi(closes, 14)))
		compareJSON(t, label("hybrid_d"), c["hybrid_d"], classifyTrendHybrid(sw, candles))
		// کلِ خروجیِ موتور رویِ همان ورودی — قراردادِ /api/fts؛ ماژورها،
		// structure_points، pullback و setups_state هم اینجا سنجیده می‌شوند.
		svc := &Service{engine: "legacy"}
		compareJSON(t, label("analyze"), c["analyze"],
			svc.analyzeCandles(candlesToAny(candles), "TEST", nil))
	}
}

// TestFTSRealSymbolParity مقایسهٔ موتور رویِ سریِ واقعیِ نمادهاست. فایلِ ورودی
// با tools/parity/gen_fts_real_vectors.py ساخته می‌شود و در گیت نیست؛ نبودش
// یعنی «اندازه‌گیری نشد»، نه پاس.
func TestFTSRealSymbolParity(t *testing.T) {
	path := os.Getenv("BORS_FTS_REAL_VECTORS")
	if path == "" {
		t.Skip("BORS_FTS_REAL_VECTORS not set — real-symbol parity NOT_MEASURED")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read real vectors: %v", err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("parse real vectors: %v", err)
	}
	cases, _ := v["cases"].([]any)
	if len(cases) == 0 {
		t.Fatal("real vectors contain no cases")
	}
	for _, item := range cases {
		m, _ := item.(map[string]any)
		name, _ := m["name"].(string)
		symbol, _ := m["symbol"].(string)
		candles := candlesFrom(m["candles"])
		got := (&Service{engine: "legacy"}).analyzeCandles(candlesToAnyFields(candles), symbol, nil)
		compareJSON(t, "real/"+name, m["analyze"], got)
	}
	t.Logf("real-symbol cases compared: %d", len(cases))
}

func TestFTSStatusVectors(t *testing.T) {
	v := loadVectors(t)
	seriesMap, _ := v["series"].(map[string]any)
	statusCases, _ := v["status"].(map[string]any)
	for name, sc := range statusCases {
		m, _ := sc.(map[string]any)
		seriesName, _ := m["series"].(string)
		ref := candlesFrom(seriesMap[seriesName])
		out, _ := m["out"].(map[string]any)
		block := statusBlock(ref, out)
		compareJSON(t, "status/"+name, m["block"], block)
	}
}
