package chart

// choch معادلِ _fts_choch: شکستِ قطعیِ آخرین پیوتِ مخالف — حاشیۀ ۱٪ و
// تثبیتِ دو بستهٔ متوالی (جزوه ص ۹).
func choch(candles []candle, sw []swing, confirmDays int, margin float64) map[string]any {
	highs := highsOf(sw)
	lows := lowsOf(sw)
	out := map[string]any{
		"bearish": nil, "bullish": nil, "level": nil, "label": nil,
		"confirm_days": confirmDays, "margin": margin,
		"reason": "پیوتِ کاملِ سقف و کف موجود نیست — ساختار سنجیده نشد",
	}
	if len(highs) == 0 || len(lows) == 0 || len(candles) == 0 {
		return out
	}
	out["reason"] = nil
	lastHigh := highs[len(highs)-1].Price
	lastLow := lows[len(lows)-1].Price
	trendUp := lows[len(lows)-1].Idx > highs[len(highs)-1].Idx
	n := len(candles)
	need := confirmDays
	if need < 1 {
		need = 1
	}
	if n < need {
		out["reason"] = "تعداد کندل برای تأییدِ چندروزه کم است — سنجیده نشد"
		out["bearish"] = nil
		out["bullish"] = nil
		return out
	}
	settled := func(level float64, above bool) bool {
		for j := 0; j < need; j++ {
			c := candles[n-1-j].Close
			if above && c <= level*(1+margin) {
				return false
			}
			if !above && c >= level*(1-margin) {
				return false
			}
		}
		return true
	}
	if trendUp {
		if settled(lastLow, false) {
			out["bearish"] = true
			out["bullish"] = false
			out["level"] = round2(lastLow)
			out["label"] = "choch_bear"
		} else {
			out["bearish"] = false
			out["bullish"] = false
		}
	} else {
		if settled(lastHigh, true) {
			out["bullish"] = true
			out["bearish"] = false
			out["level"] = round2(lastHigh)
			out["label"] = "choch_bull"
		} else {
			out["bullish"] = false
			out["bearish"] = false
		}
	}
	return out
}
