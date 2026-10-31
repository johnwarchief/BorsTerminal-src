package chart

// doubleBottom معادلِ _fts_double_bottom: دابل‌باتم (یقهٔ بین دو کفِ مساوی) و
// جعبهٔ رنجِ ۲۱ کندلی.
func doubleBottom(candles []candle, sw []swing) map[string]any {
	lows := lowsOf(sw)
	highs := highsOf(sw)
	dbl := map[string]any{
		"active": nil, "neckline": nil, "pct_above_neck": nil,
		"reason": "دو کفِ پیوت موجود نیست — سنجیده نشد",
	}
	if len(lows) >= 2 {
		dbl["reason"] = nil
		l1, l2 := lows[len(lows)-2], lows[len(lows)-1]
		equal := false
		if l1.Price != 0 && l2.Price != 0 {
			m := l1.Price
			if l2.Price > m {
				m = l2.Price
			}
			equal = absF(l1.Price-l2.Price)/m <= 0.015
		}
		necks := []float64{}
		for _, h := range highs {
			if l1.Idx < h.Idx && h.Idx < l2.Idx {
				necks = append(necks, h.Price)
			}
		}
		if equal && len(necks) > 0 && len(candles) > 0 {
			neck := necks[0]
			for _, v := range necks[1:] {
				if v > neck {
					neck = v
				}
			}
			last := candles[len(candles)-1].Close
			hit := last > neck
			dbl["active"] = hit
			dbl["neckline"] = round2(neck)
			if hit {
				dbl["pct_above_neck"] = round2((last - neck) / neck * 100.0)
			} else {
				dbl["pct_above_neck"] = nil
			}
		}
	}
	box := map[string]any{
		"active": nil, "top": nil, "bottom": nil, "pct_above_top": nil,
		"reason": "۲۱ کندل سابقه بسته نیست — باکس رنج سنجیده نشد",
	}
	if len(candles) >= 21 {
		box["reason"] = nil
		win := candles[len(candles)-21 : len(candles)-1]
		top, bot := win[0].High, win[0].Low
		for _, c := range win[1:] {
			if c.High > top {
				top = c.High
			}
			if c.Low < bot {
				bot = c.Low
			}
		}
		last := candles[len(candles)-1]
		broke := last.Close > top && last.Close >= last.Open
		box["active"] = broke
		box["top"] = round2(top)
		box["bottom"] = round2(bot)
		if broke {
			box["pct_above_top"] = round2((last.Close - top) / top * 100.0)
		} else {
			box["pct_above_top"] = nil
		}
	}
	return map[string]any{"double_bottom": dbl, "range_box": box}
}
