package chart

import "math"

// سطوحِ فعالِ فیبو، عینِ جزوه: ۰، ۰.۳۳، ۰.۴، ۰.۵، ۰.۶۱۸، ۰.۷، ۱ و دو کمربندِ
// ورودِ ۳۳–۴۰ و ۶۱.۸–۷۰ (api/chart.py).
var fibLevels = []float64{0.0, 0.33, 0.40, 0.50, 0.618, 0.70, 1.00}

var fibBelts = []struct {
	key    string
	p1, p2 float64
}{
	{"zone_33_40", 0.33, 0.40},
	{"zone_618_70", 0.618, 0.70},
}

// fibLeg معادلِ _fts_fib_leg: موجِ اخیرِ نشکسته (زنجیرهٔ HL یا LH).
func fibLeg(candles []candle, sw []swing) map[string]any {
	n := len(candles)
	if n < 2 {
		return nil
	}
	highs := highsOf(sw)
	lows := lowsOf(sw)
	if len(highs) == 0 && len(lows) == 0 {
		hiIdx := 0
		for i := 1; i < n; i++ {
			if candles[i].High > candles[hiIdx].High {
				hiIdx = i
			}
		}
		lo := candles[0].Low
		for _, c := range candles[1:] {
			if c.Low < lo {
				lo = c.Low
			}
		}
		return map[string]any{"direction": "up", "start_idx": 0, "end_idx": n - 1,
			"high": candles[hiIdx].High, "low": lo}
	}
	closeP := make([]float64, n)
	for i, c := range candles {
		closeP[i] = c.Close
	}
	sufMin := make([]float64, n+1)
	sufMax := make([]float64, n+1)
	sufMin[n] = math.Inf(1)
	sufMax[n] = math.Inf(-1)
	for i := n - 1; i >= 0; i-- {
		sufMin[i] = math.Min(closeP[i], sufMin[i+1])
		sufMax[i] = math.Max(closeP[i], sufMax[i+1])
	}

	var up bool
	switch {
	case len(lows) == 0:
		up = false
	case len(highs) == 0:
		up = true
	default:
		t := classifyTrend(sw, ftsEqualTol, candles, ftsStaleBars)["trend"]
		if t == "up" {
			up = true
		} else if t == "down" {
			up = false
		} else {
			up = lows[len(lows)-1].Idx >= highs[len(highs)-1].Idx
		}
	}

	if up {
		i := len(lows) - 1
		for i > 0 && lows[i-1].Price < lows[i].Price &&
			sufMin[lows[i-1].Idx] >= lows[i-1].Price {
			i--
		}
		base := lows[i]
		hi := candles[base.Idx].High
		for _, c := range candles[base.Idx+1:] {
			if c.High > hi {
				hi = c.High
			}
		}
		return map[string]any{"direction": "up", "start_idx": base.Idx, "end_idx": n - 1,
			"high": hi, "low": base.Price}
	}
	i := len(highs) - 1
	for i > 0 && highs[i-1].Price > highs[i].Price &&
		sufMax[highs[i-1].Idx] <= highs[i-1].Price {
		i--
	}
	top := highs[i]
	lo := candles[top.Idx].Low
	for _, c := range candles[top.Idx+1:] {
		if c.Low < lo {
			lo = c.Low
		}
	}
	return map[string]any{"direction": "down", "start_idx": top.Idx, "end_idx": n - 1,
		"high": top.Price, "low": lo}
}

// fibPrice: قیمتِ سطحِ p روی مقیاسِ لگاریتمی، از سقف به پایین.
func fibPrice(top, bot, ratio float64) float64 {
	return math.Exp(math.Log(top) + (math.Log(bot)-math.Log(top))*ratio)
}

// fibRetrace: سطحِ اصلاح در جهتِ موج (نزولی از کف به بالا سنجیده می‌شود).
func fibRetrace(top, bot, ratio float64, direction string) float64 {
	if direction == "down" {
		return math.Exp(math.Log(bot) + (math.Log(top)-math.Log(bot))*ratio)
	}
	return fibPrice(top, bot, ratio)
}

// fibZones معادلِ _fts_fib_zones.
func fibZones(candles []candle, sw []swing) map[string]any {
	leg := fibLeg(candles, sw)
	if leg == nil {
		return nil
	}
	top, _ := numOf(leg["high"])
	bot, _ := numOf(leg["low"])
	if top <= 0 || bot <= 0 || top <= bot {
		return nil
	}
	zones := map[string]any{}
	direction, _ := leg["direction"].(string)
	if direction == "" {
		direction = "up"
	}
	for _, belt := range fibBelts {
		a := fibRetrace(top, bot, belt.p1, direction)
		b := fibRetrace(top, bot, belt.p2, direction)
		hiP, loP := math.Max(a, b), math.Min(a, b)
		last := 0.0
		if len(candles) > 0 {
			last = candles[len(candles)-1].Close
		}
		zones[belt.key] = map[string]any{
			"lo": round2(loP), "hi": round2(hiP),
			"in_zone": loP <= last && last <= hiP,
		}
	}
	levels := make([]map[string]any, 0, len(fibLevels))
	for _, r := range fibLevels {
		levels = append(levels, map[string]any{
			"ratio": r, "price": round2(fibRetrace(top, bot, r, direction)),
		})
	}
	startIdx, _ := leg["start_idx"].(int)
	endIdx, _ := leg["end_idx"].(int)
	return map[string]any{
		"retrace_base_high": round2(top), "retrace_base_low": round2(bot),
		"zone_33_40":  zones["zone_33_40"],
		"zone_618_70": zones["zone_618_70"],
		"levels":      levels,
		"leg": map[string]any{
			"direction": leg["direction"],
			"start":     candles[startIdx].Time[:10],
			"end":       candles[endIdx].Time[:10],
			"high":      round2(top), "low": round2(bot),
		},
	}
}
