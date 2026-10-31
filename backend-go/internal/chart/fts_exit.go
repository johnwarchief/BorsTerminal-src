package chart

import "math"

// ftsMa معادلِ _fts_ma: SMA ساده؛ هم‌طول ورودی و تا period-1 تهی.
func ftsMa(closes []float64, period int) []*float64 {
	out := make([]*float64, 0, len(closes))
	acc := 0.0
	for i, c := range closes {
		acc += c
		if i >= period {
			acc -= closes[i-period]
		}
		if i >= period-1 {
			v := round2(acc / float64(period))
			out = append(out, &v)
		} else {
			out = append(out, nil)
		}
	}
	return out
}

// ftsRsi معادلِ _fts_rsi: RSI وایلدر با warmupِ بذرِ دقیق (نخستین عدد در
// index=period و بی‌گامِ اضافی).
func ftsRsi(closes []float64, period int) []*float64 {
	if len(closes) < period+2 {
		out := make([]*float64, len(closes))
		return out
	}
	gains, losses := 0.0, 0.0
	for i := 1; i <= period; i++ {
		ch := closes[i] - closes[i-1]
		if ch > 0 {
			gains += ch
		} else {
			losses += -ch
		}
	}
	ag, al := gains/float64(period), losses/float64(period)
	val := func(a, b float64) float64 {
		if b > 0 {
			return round1(100.0 - 100.0/(1.0+a/b))
		}
		return 100.0
	}
	out := make([]*float64, 0, len(closes))
	for i := 0; i < period; i++ {
		out = append(out, nil)
	}
	v := val(ag, al)
	out = append(out, &v)
	for i := period + 1; i < len(closes); i++ {
		ch := closes[i] - closes[i-1]
		g := 0.0
		l := 0.0
		if ch > 0 {
			g = ch
		} else {
			l = -ch
		}
		ag = (ag*float64(period-1) + g) / float64(period)
		al = (al*float64(period-1) + l) / float64(period)
		v := val(ag, al)
		out = append(out, &v)
	}
	return out
}

// exitLayer1: حد ضرر سخت + خروج تعقیبیِ MA14.
func exitLayer1(candles []candle, entryHint *float64) map[string]any {
	out := map[string]any{
		"hard_stop": nil, "stop_basis": nil, "stop_hit": nil,
		"ma14_exit": nil, "ma14_exit_pending": nil,
		"ma14": nil, "close": nil,
	}
	if len(candles) == 0 {
		return out
	}
	last := candles[len(candles)-1]
	closeP := last.Close
	out["close"] = round2(closeP)
	closed := candles
	if len(candles) > 1 {
		closed = candles[:len(candles)-1]
	}
	start := len(closed) - 20
	if start < 0 {
		start = 0
	}
	majorLow := closed[start].Low
	for _, c := range closed[start:] {
		if c.Low < majorLow {
			majorLow = c.Low
		}
	}
	type cand struct {
		px   float64
		name string
	}
	cands := []cand{}
	if entryHint != nil && *entryHint > 0 {
		cands = append(cands, cand{*entryHint * 0.95, "entry"})
	}
	cands = append(cands, cand{majorLow * 0.95, "swing_low"})
	// max(cand, key=lambda x: x[0])ِ پایتون در تساوی نخستین را برمی‌دارد، یعنی
	// «entry» بر «swing_low» می‌چربد حتی وقتی عدد یکی است (خرید روی کفِ ساختاری).
	stopPx, basis := cands[0].px, cands[0].name
	for _, c := range cands[1:] {
		if c.px > stopPx {
			stopPx, basis = c.px, c.name
		}
	}
	out["hard_stop"] = round2(stopPx)
	out["stop_basis"] = basis
	out["stop_hit"] = closeP < stopPx

	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}
	ma14 := ftsMa(closes, 14)
	var maLast *float64
	if len(ma14) > 0 {
		maLast = ma14[len(ma14)-1]
	}
	if maLast == nil {
		return out
	}
	out["ma14"] = *maLast
	bodyTop := math.Max(last.Open, closeP)
	bodyBelow := bodyTop < *maLast
	prevBelow := false
	if len(candles) >= 2 && ma14[len(ma14)-2] != nil {
		p := candles[len(candles)-2]
		prevBelow = math.Max(p.Open, p.Close) < *ma14[len(ma14)-2]
	}
	out["ma14_exit"] = bodyBelow && prevBelow
	out["ma14_exit_pending"] = bodyBelow && !prevBelow
	return out
}

// exitLayer2: خرابی‌هایِ ساختاری (CHoCH نزولی + شکستِ کفِ کانال).
func exitLayer2(candles []candle, swingsD []swing) map[string]any {
	out := map[string]any{
		"choch_break": nil, "channel_break": nil, "level": nil, "touches": nil,
	}
	if len(candles) == 0 {
		return out
	}
	ch := choch(candles, swingsD, ftsCHochDays, ftsCHochMargin)
	out["choch_break"] = ch["bearish"]
	if b, ok := ch["bearish"].(bool); ok && b {
		out["level"] = ch["level"]
	}
	ph := pointHunt(candles, swingsD)
	out["touches"] = ph["touches"]
	floor, floorOK := numOf(ph["floor_price"])
	if ph["touches"] == nil {
		return out
	}
	touches, _ := ph["touches"].(int)
	if touches >= 3 && floorOK && floor != 0 {
		brk := candles[len(candles)-1].Close < floor*0.995
		out["channel_break"] = brk
		if brk {
			out["level"] = round2(floor)
		}
	} else {
		out["channel_break"] = false
	}
	return out
}

// exitLayer3: الگوهایِ برگشتیِ کلاسیک (سقف سوم، دابل‌تاپ، سر و شانه).
func exitLayer3(candles []candle, sw []swing) map[string]any {
	out := map[string]any{
		"third_peak": nil, "double_top": nil, "hs_break": nil,
		"neckline": nil, "level": nil, "third_peak_level": nil,
	}
	if len(candles) < 15 {
		return out
	}
	highs := highsOf(sw)
	lows := lowsOf(sw)
	last := candles[len(candles)-1].Close
	if len(highs) >= 3 {
		h1, h2, h3 := highs[len(highs)-3].Price, highs[len(highs)-2].Price, highs[len(highs)-1].Price
		m := math.Max(h1, math.Max(h2, h3))
		third := m > 0 && (m-math.Min(h1, math.Min(h2, h3)))/m <= 0.01
		out["third_peak"] = third
		if third {
			out["third_peak_level"] = round2(m)
		}
	}
	if len(highs) >= 2 {
		h1, h2 := highs[len(highs)-2].Price, highs[len(highs)-1].Price
		m := math.Max(h1, h2)
		twin := m > 0 && (m-math.Min(h1, h2))/m <= 0.01
		necks := []float64{}
		for _, l := range lows {
			if highs[len(highs)-2].Idx < l.Idx && l.Idx < highs[len(highs)-1].Idx {
				necks = append(necks, l.Price)
			}
		}
		dt := twin && len(necks) > 0 && last < minF(necks)
		out["double_top"] = dt
		if dt {
			neck := minF(necks)
			out["neckline"] = round2(neck)
			out["level"] = round2(neck)
		}
	}
	if len(highs) >= 3 && len(lows) >= 2 {
		s1 := highs[len(highs)-3]
		head := highs[len(highs)-2]
		s2 := highs[len(highs)-1]
		ls1 := lows[len(lows)-2]
		ls2 := lows[len(lows)-1]
		between1 := s1.Idx < ls1.Idx && ls1.Idx < head.Idx
		between2 := head.Idx < ls2.Idx && ls2.Idx < s2.Idx
		shoulders := absF(s1.Price-s2.Price)/math.Max(s1.Price, s2.Price) <= 0.03
		isHS := head.Price > s1.Price && head.Price > s2.Price &&
			between1 && between2 && shoulders &&
			ls1.Idx > s1.Idx && ls2.Idx < s2.Idx
		broke := false
		if isHS {
			span := ls2.Idx - ls1.Idx
			if span > 0 {
				slope := (ls2.Price - ls1.Price) / float64(span)
				neckNow := ls1.Price + slope*float64(len(candles)-1-ls1.Idx)
				broke = last < neckNow
				if broke {
					out["neckline"] = round2(neckNow)
					out["level"] = round2(neckNow)
				}
			}
		}
		out["hs_break"] = broke
	}
	return out
}

// exitLayer4: مومنتوم (واگرایی و چرخشِ اشباعِ خرید).
func exitLayer4(candles []candle) map[string]any {
	out := map[string]any{
		"rsi_divergence": nil, "rsi_rollover": nil, "rsi": nil, "rsi_prev_peak": nil,
	}
	if len(candles) < 30 {
		return out
	}
	closes := make([]float64, len(candles))
	for i, c := range candles {
		closes[i] = c.Close
	}
	rsi := ftsRsi(closes, 14)
	if last := rsi[len(rsi)-1]; last != nil {
		out["rsi"] = *last
	}
	sw := swingsOf(candles, ftsSwingK)
	highs := highsOf(sw)
	if len(highs) >= 2 {
		h1, h2 := highs[len(highs)-2], highs[len(highs)-1]
		rsiPeak := func(sw swing) *float64 {
			lo := sw.Idx - 2
			if lo < 0 {
				lo = 0
			}
			hi := sw.Idx + 3
			if hi > len(rsi) {
				hi = len(rsi)
			}
			var best *float64
			for _, v := range rsi[lo:hi] {
				if v != nil && (best == nil || *v > *best) {
					best = v
				}
			}
			return best
		}
		r1, r2 := rsiPeak(h1), rsiPeak(h2)
		if r1 != nil {
			out["rsi_prev_peak"] = *r1
		}
		if r1 != nil && r2 != nil {
			out["rsi_divergence"] = h2.Price > h1.Price && *r2 < *r1-1.0
		}
	}
	recent := []float64{}
	start := len(rsi) - 10
	if start < 0 {
		start = 0
	}
	for _, v := range rsi[start:] {
		if v != nil {
			recent = append(recent, *v)
		}
	}
	cur, hasCur := out["rsi"].(float64)
	if len(recent) > 0 && hasCur {
		out["rsi_rollover"] = maxF(recent) >= 70.0 && cur <= 65.0
	}
	return out
}

func minF(v []float64) float64 {
	m := v[0]
	for _, x := range v[1:] {
		if x < m {
			m = x
		}
	}
	return m
}

func maxF(v []float64) float64 {
	m := v[0]
	for _, x := range v[1:] {
		if x > m {
			m = x
		}
	}
	return m
}

// exitEngine معادلِ _fts_exit_engine: داورِ چهارلایه و تفکیکِ «سنجیده شد»
// از «سنجیده نشد».
func exitEngine(candles []candle, entryHint *float64) map[string]any {
	l1 := exitLayer1(candles, entryHint)
	swingsD := swingsOf(candles, ftsSwingK)
	l2 := exitLayer2(candles, swingsD)
	l3 := exitLayer3(candles, swingsD)
	l4 := exitLayer4(candles)
	type flag struct {
		name string
		v    any
	}
	flags := []flag{
		{"stop_hard", l1["stop_hit"]},
		{"ma14_trail", l1["ma14_exit"]},
		{"ma14_watch", l1["ma14_exit_pending"]},
		{"choch_break", l2["choch_break"]},
		{"channel_break", l2["channel_break"]},
		{"third_peak", l3["third_peak"]},
		{"double_top", l3["double_top"]},
		{"hs_break", l3["hs_break"]},
		{"rsi_divergence", l4["rsi_divergence"]},
		{"rsi_rollover", l4["rsi_rollover"]},
	}
	signals := []string{}
	unmeasured := []string{}
	anyFalse := false
	for _, f := range flags {
		switch b := f.v.(type) {
		case bool:
			if b {
				signals = append(signals, f.name)
			} else {
				anyFalse = true
			}
		case nil:
			unmeasured = append(unmeasured, f.name)
		}
	}
	tr := func(name string) any {
		for _, f := range flags {
			if f.name == name {
				return f.v
			}
		}
		return nil
	}
	isTrue := func(v any) bool { b, ok := v.(bool); return ok && b }
	var verdict string
	switch {
	case isTrue(tr("stop_hard")):
		verdict = "stop"
	case isTrue(tr("ma14_trail")) || isTrue(tr("choch_break")) ||
		isTrue(tr("channel_break")) || isTrue(tr("double_top")) ||
		isTrue(tr("hs_break")):
		verdict = "exit"
	case isTrue(tr("ma14_watch")) || isTrue(tr("rsi_divergence")) ||
		isTrue(tr("rsi_rollover")) || isTrue(tr("third_peak")):
		verdict = "caution"
	case anyFalse:
		verdict = "hold"
	default:
		verdict = "unknown"
	}
	return map[string]any{
		"verdict": verdict, "signals": signals, "unmeasured": unmeasured,
		"l1": l1, "l2": l2, "l3": l3, "l4": l4,
	}
}
