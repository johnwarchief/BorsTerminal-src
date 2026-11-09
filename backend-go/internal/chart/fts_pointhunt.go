package chart

// pointHunt معادلِ _fts_point_hunt: کفِ دایامتریکِ کانال با ≥۳ لمس + ریباندِ
// سبزِ همان کندل (تریگرِ ورود رویِ کندلِ امروز).
func pointHunt(candles []candle, sw []swing) map[string]any {
	highs := highsOf(sw)
	lows := lowsOf(sw)
	out := map[string]any{
		"touches": nil, "floor_price": nil, "active": nil, "bounced": nil,
		"floor_idx": nil, "floor_date": nil, "trigger_idx": nil,
		"trigger_date": nil, "reason": nil,
	}
	// P0 #3: سه علتِ متمایز، سه پیام با تعداد — «سقف کم است» با «سابقه کم است»
	// با «سقف‌ها چسبیده‌اند» یکی نیست.
	if len(highs) < 2 {
		out["reason"] = "سقفِ مستقلِ کافی نیست (" + ftsFa(len(highs)) +
			" از ۲ لازم) — کانال سنجیده نشد"
		return out
	}
	if len(lows) == 0 {
		out["reason"] = "هیچ کفِ تأییدشده‌ای نیست — کانال سنجیده نشد"
		return out
	}
	if len(candles) < 10 {
		out["reason"] = "سابقه کم است (" + ftsFa(len(candles)) +
			" کندل، حداقل ۱۰ لازم) — کانال سنجیده نشد"
		return out
	}
	h2, h1 := highs[len(highs)-2], highs[len(highs)-1]
	if h1.Idx-h2.Idx < 3 {
		out["reason"] = "دو سقفِ آخر چسبیده‌اند (فاصله " + ftsFa(h1.Idx-h2.Idx) +
			" کندل، حداقل ۳ لازم) — الگو در حال تشکیل"
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
