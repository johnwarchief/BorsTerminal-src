package chart

import "borsterminal/backend/internal/tapeflags"

var ftsSetupLabels = map[string]string{"choch": "CHoCH", "dbl": "دابل‌باتم"}

// setupHistory معادلِ _fts_setup_history: مارکرهایِ گذشته با همان قاعدهٔ پنلِ
// امروز. جت عمداً مارکرِ تاریخی ندارد (رأیِ مالک، دورِ J).
func setupHistory(candles []candle, sw []swing, limit int) []map[string]any {
	need := 1
	for _, k := range tapeflags.JetLadder {
		if k > need {
			need = k
		}
	}
	need++
	n := len(candles)
	if n < need+1 {
		return []map[string]any{}
	}
	k := ftsSwingK
	hp := highsOf(sw)
	lp := lowsOf(sw)
	a, b := 0, 0
	var lastH, lastL, prevL *swing
	var neck *float64
	chochOn := ""
	haveChoch := false
	dblOn := false
	events := []map[string]any{}
	emit := func(i int, kind string, price float64, side string) {
		events = append(events, map[string]any{
			"date": trim10(candles[i].Time), "kind": kind,
			"label": ftsSetupLabels[kind], "price": round2(price), "side": side,
		})
	}
	for i := need - 1; i < n; i++ {
		for a < len(hp) && hp[a].Idx <= i-k {
			s := hp[a]
			lastH = &s
			a++
		}
		var newLow *swing
		for b < len(lp) && lp[b].Idx <= i-k {
			s := lp[b]
			newLow = &s
			b++
		}
		if newLow != nil {
			prevL, lastL = lastL, newLow
			neck = nil
			if prevL != nil && prevL.Price > 0 && lastL.Price > 0 {
				m := prevL.Price
				if lastL.Price > m {
					m = lastL.Price
				}
				if absF(prevL.Price-lastL.Price)/m <= 0.015 {
					var best *float64
					for i := range hp {
						if prevL.Idx < hp[i].Idx && hp[i].Idx < lastL.Idx {
							v := hp[i].Price
							if best == nil || v > *best {
								best = &v
							}
						}
					}
					neck = best
				}
			}
		}
		c := candles[i]
		cl := c.Close
		upLeg := lastL != nil && (lastH == nil || lastL.Idx >= lastH.Idx)
		if lastH != nil && lastL != nil {
			want := "bull"
			level := lastH.Price
			if upLeg {
				want = "bear"
				level = lastL.Price
			}
			settled := true
			for j := 0; j < ftsCHochDays; j++ {
				if i-j < 0 {
					settled = false
					break
				}
				cj := candles[i-j].Close
				if upLeg && cj >= level*(1-ftsCHochMargin) {
					settled = false
					break
				}
				if !upLeg && cj <= level*(1+ftsCHochMargin) {
					settled = false
					break
				}
			}
			if settled && (!haveChoch || chochOn != want) {
				side := "above"
				if upLeg {
					side = "below"
				}
				emit(i, "choch", level, side)
			}
			if settled {
				chochOn = want
				haveChoch = true
			} else {
				chochOn = ""
				haveChoch = false
			}
		}
		dbl := neck != nil && *neck != 0 && cl > *neck
		if dbl && !dblOn {
			emit(i, "dbl", *neck, "above")
		}
		dblOn = dbl
	}
	if limit > 0 && len(events) > limit {
		events = events[len(events)-limit:]
	}
	return events
}
