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
		out = append(out, candle{Time: tm, Open: o, High: h, Low: l, Close: c, Volume: vol})
	}
	return out
}

func swingsToAny(sw []swing) []map[string]any {
	out := make([]map[string]any, 0, len(sw))
	for _, s := range sw {
		out = append(out, map[string]any{
			"idx": s.Idx, "price": s.Price, "kind": s.Kind, "time": s.Time,
		})
	}
	return out
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
		label := func(k string) string { return kind + "/" + k }
		compareJSON(t, label("swings"), c["swings"], swingsToAny(sw))
		compareJSON(t, label("weekly"), c["weekly"], candlesToAny(w))
		compareJSON(t, label("monthly"), c["monthly"], candlesToAny(m))
		compareJSON(t, label("trend_d"), c["trend_d"],
			classifyTrend(sw, ftsEqualTol, candles, ftsStaleBars))
		compareJSON(t, label("trend_w"), c["trend_w"],
			classifyTrend(swingsOf(w, 2), ftsEqualTol, w, ftsStaleBars))
		compareJSON(t, label("trend_m"), c["trend_m"],
			classifyTrend(swingsOf(m, 2), ftsEqualTol, m, ftsStaleBars))
		compareJSON(t, label("recent"), c["recent"], recentWindowTrend(candles, ftsStaleWindow))
		compareJSON(t, label("reason_d"), c["reason_d"],
			trendReason(classifyTrend(sw, ftsEqualTol, candles, ftsStaleBars)))
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
		closes := make([]float64, len(candles))
		for i, cc := range candles {
			closes[i] = cc.Close
		}
		compareJSON(t, label("ma14"), c["ma14"], ptrsToAny(ftsMa(closes, 14)))
		compareJSON(t, label("rsi14"), c["rsi14"], ptrsToAny(ftsRsi(closes, 14)))
		compareJSON(t, label("hybrid_d"), c["hybrid_d"], classifyTrendHybrid(sw, candles))
	}
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
