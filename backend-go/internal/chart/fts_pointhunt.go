package chart

// pointHunt معادلِ _fts_point_hunt: کفِ دایامتریکِ کانال با ≥۳ لمس + ریباندِ
// سبزِ همان کندل (تریگرِ ورود رویِ کندلِ امروز).
func pointHunt(candles []candle, sw []swing) map[string]any {
	highs := highsOf(sw)
	lows := lowsOf(sw)
	out := map[string]any{
		"touches": nil, "floor_price": nil, "active": nil, "bounced": nil,
		"floor_idx": nil, "floor_date": nil, "trigger_idx": nil,
		"trigger_date": nil,
		"reason":       "دو سقفِ جدا یا ده کندل سابقه نیست — کانال سنجیده نشد",
	}
	if len(highs) < 2 || len(lows) == 0 || len(candles) < 10 {
		return out
	}
	h2, h1 := highs[len(highs)-2], highs[len(highs)-1]
	if h1.Idx-h2.Idx < 3 {
		return out
	}
	out["reason"] = nil
	slope := (h1.Price - h2.Price) / float64(h1.Idx-h2.Idx)
	var anchor *swing
	for i := range lows {
		l := &lows[i]
		if l.Idx > h2.Idx && l.Idx <= h1.Idx {
			if anchor == nil || l.Price < anchor.Price {
				anchor = l
			}
		}
	}
	if anchor == nil {
		anchor = &lows[0]
		for i := range lows {
			if lows[i].Price < anchor.Price {
				anchor = &lows[i]
			}
		}
	}
	floorAt := func(i int) float64 {
		return anchor.Price + slope*float64(i-anchor.Idx)
	}
	const tol = 0.005
	touches := 0
	for i := anchor.Idx; i < len(candles); i++ {
		if candles[i].Low <= floorAt(i)*(1+tol) {
			touches++
		}
	}
	lvl := floorAt(len(candles) - 1)
	last := candles[len(candles)-1]
	bounced := last.Low <= lvl*(1+tol) && last.Close > last.Open && last.Close > lvl
	active := touches >= 3 && bounced
	out["touches"] = touches
	out["floor_price"] = round2(lvl)
	out["active"] = active
	out["bounced"] = bounced
	out["floor_idx"] = anchor.Idx
	out["floor_date"] = trim10(candles[anchor.Idx].Time)
	if active {
		out["trigger_idx"] = len(candles) - 1
		out["trigger_date"] = trim10(last.Time)
	}
	return out
}
