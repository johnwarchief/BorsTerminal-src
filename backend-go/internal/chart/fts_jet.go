package chart

import "strconv"

// jetSetup معادلِ _fts_jet_setup: شکست مقاومت استاتیک/سقف تاریخی + کندل
// تثبیت + پنجرهٔ ورودِ سه‌روزه. لدرِ تابلو در این تابع مصرف نمی‌شود (پارامترِ
// پایتون هم فقط برای سازگاری امضا مانده)؛ فقط تاریخچهٔ ۶۰ نشست شرط است.
func jetSetup(candles []candle, ceilingWin, ceilingSkip, entryWindowDays int) map[string]any {
	n := len(candles)
	if n < ftsJetMinBars {
		var closeV any
		if n >= 1 {
			closeV = round2(candles[n-1].Close)
		}
		return map[string]any{
			"active": nil, "resistance": nil, "resistance_date": nil,
			"resistance_type": nil, "ath": nil, "close": closeV,
			"pct_above_res": nil, "ceiling": nil, "ceiling_date": nil,
			"static_broke": nil, "breakout_date": nil,
			"entry_window_days": entryWindowDays, "days_remaining": nil,
			"tier": nil, "reason": "تاریخچه برای سنجش جت کافی نیست — سنجیده نشد",
		}
	}

	type levelInfo struct {
		price float64
		date  any
		kind  string
		ok    bool
	}
	levelBefore := func(idx int) levelInfo {
		eligibleEnd := idx - ceilingSkip
		if eligibleEnd < 0 {
			eligibleEnd = 0
		}
		eligible := candles[:eligibleEnd]
		if len(eligible) == 0 {
			return levelInfo{}
		}
		athI := 0
		for j := 1; j < len(eligible); j++ {
			if eligible[j].High > eligible[athI].High {
				athI = j
			}
		}
		ath := eligible[athI].High
		athDate := strOrNilStr(trim10(eligible[athI].Time))
		if len(eligible) >= ceilingWin {
			win := eligible[len(eligible)-ceilingWin:]
			wi := 0
			for j := 1; j < len(win); j++ {
				if win[j].High > win[wi].High {
					wi = j
				}
			}
			return levelInfo{price: win[wi].High, date: strOrNilStr(trim10(win[wi].Time)),
				kind: "static", ok: true}
		}
		return levelInfo{price: ath, date: athDate, kind: "historical_high", ok: true}
	}

	type found struct {
		idx   int
		level float64
		date  any
		kind  string
	}
	var hit *found
	start := n - entryWindowDays
	if entryWindowDays < 1 {
		start = n - 1
	}
	if start < 1 {
		start = 1
	}
	for i := n - 1; i >= start; i-- {
		lv := levelBefore(i)
		if !lv.ok || lv.price <= 0 {
			continue
		}
		c := candles[i]
		prev := candles[i-1]
		closeP := c.Close
		op := c.Open
		prevClose := prev.Close
		if closeP > lv.price && closeP >= op && prevClose <= lv.price {
			hit = &found{idx: i, level: lv.price, date: lv.date, kind: lv.kind}
			break
		}
	}

	last := candles[n-1]
	closeP := last.Close
	lastLevel := levelBefore(n - 1)
	if !lastLevel.ok {
		return map[string]any{
			"active": nil, "resistance": nil, "resistance_date": nil,
			"resistance_type": nil, "ath": nil, "close": round2(closeP),
			"pct_above_res": nil, "ceiling": nil, "ceiling_date": nil,
			"static_broke": nil, "breakout_date": nil,
			"entry_window_days": entryWindowDays, "days_remaining": nil,
			"tier": nil, "reason": "مقاومت قابل محاسبه نیست — سنجیده نشد",
		}
	}

	athRes := candles[0].High
	for _, c := range candles[:n-1] {
		if c.High > athRes {
			athRes = c.High
		}
	}
	athHit := athRes > 0 && closeP > athRes

	if hit != nil {
		age := (n - 1) - hit.idx
		daysRemaining := entryWindowDays - age
		if daysRemaining < 0 {
			daysRemaining = 0
		}
		active := age < entryWindowDays
		res := hit.level
		tier := "expired"
		if active {
			tier = "confirmed"
		}
		reason := "شکست و تثبیت جت ثبت شده ولی پنجرۀ ۳ روزه تمام شده"
		if active {
			reason = "شکست " + hit.kind + " + کندل تثبیت؛ " +
				strconv.Itoa(daysRemaining) + " روز از پنجرۀ ورود باقی است"
		}
		ath := false
		if athRes != 0 {
			ath = absF(res-athRes)/athRes < 0.002
		}
		var ceiling, ceilingDate, breakoutDate any
		if lastLevel.kind == "static" {
			ceiling = round2(lastLevel.price)
			ceilingDate = lastLevel.date
		}
		breakoutDate = strOrNilStr(trim10(candles[hit.idx].Time))
		var remain any = 0
		if active {
			remain = daysRemaining
		}
		return map[string]any{
			"active": active, "resistance": round2(res),
			"resistance_date": hit.date, "resistance_type": hit.kind,
			"ath": ath, "close": round2(closeP),
			"pct_above_res": round2((closeP - res) / res * 100.0),
			"ceiling":       ceiling, "ceiling_date": ceilingDate,
			"static_broke": true, "breakout_date": breakoutDate,
			"entry_window_days": entryWindowDays, "days_remaining": remain,
			"tier": tier, "reason": reason,
		}
	}

	var ceiling, ceilingDate any
	if lastLevel.kind == "static" {
		ceiling = round2(lastLevel.price)
		ceilingDate = lastLevel.date
	}
	return map[string]any{
		"active": false, "resistance": round2(lastLevel.price),
		"resistance_date": lastLevel.date, "resistance_type": lastLevel.kind,
		"ath": athHit, "close": round2(closeP),
		"pct_above_res": round2((closeP - lastLevel.price) / lastLevel.price * 100.0),
		"ceiling":       ceiling, "ceiling_date": ceilingDate,
		"static_broke": false, "breakout_date": nil,
		"entry_window_days": entryWindowDays, "days_remaining": 0,
		"tier": "none", "reason": "شکستِ جتِ تأییدشده در پنجرۀ ۳ روزه وجود ندارد",
	}
}

func trim10(s string) string {
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

func absF(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
