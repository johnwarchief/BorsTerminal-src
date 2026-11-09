package chart

// pullbackSetup معادلِ _fts_pullback_setup (جزوه ص۸-۹ و ص۳۴؛ چارت مرجع ص۲:
// صعودی → جت یا پولبک). بازگشت شرطِ تعریف است، نه آستانهٔ افزوده: لمسِ تنها
// ستاپ نیست. سطح = آخرین سقفِ تأییدشده؛ tol همان ۰٫۵٪ لمسِ شکارِ نقطه است.
func pullbackSetup(candles []candle, swings []swing, trendD, weeklyTrend string) map[string]any {
	out := map[string]any{
		"active": nil, "touching": nil, "level": nil, "level_date": nil,
		"level_age_bars": nil, "weekly_confirms": nil, "gap_pct": nil,
		"reason": nil,
	}
	hp := highsOf(swings)
	if trendD == "" || trendD == "na" {
		out["reason"] = "روند روزانه سنجیده نشد (" + ftsFa(len(hp)) +
			" سقفِ تأییدشده) — پولبک ارزیابی نشد"
		return out
	}
	if trendD != "up" {
		out["active"] = false
		out["touching"] = false
		out["reason"] = "شاخۀ پولبک فقط در روند صعودی تعریف شده — روند روزانه صعودی نیست"
		return out
	}
	if len(hp) == 0 || len(candles) < 3 {
		out["reason"] = "سقفِ تأییدشده یا کندلِ کافی نیست (" + ftsFa(len(hp)) +
			" سقف، " + ftsFa(len(candles)) + " کندل)"
		return out
	}
	top := hp[len(hp)-1]
	if top.Idx >= len(candles)-1 {
		out["reason"] = "آخرین سقفِ تأییدشده خودِ کندلِ امروز است — پولبک بعد از سقف سنجیده می‌شود"
		return out
	}
	level := top.Price
	last := candles[len(candles)-1]
	tol := ftsPointTouchTol
	touching := last.Low <= level*(1.0+tol)
	bounced := touching && last.Close > level && last.Close > last.Open
	out["level"] = round2(level)
	out["level_date"] = trim10(candles[top.Idx].Time)
	out["level_age_bars"] = len(candles) - 1 - top.Idx
	out["touching"] = touching
	out["active"] = bounced
	out["weekly_confirms"] = weeklyTrend == "up"
	if !touching {
		gap := (last.Low/level - 1.0) * 100.0
		out["gap_pct"] = round2(gap)
		out["reason"] = "قیمت به آخرین سقف نرسیده (" + ftsFa(round2(gap)) +
			"٪ فاصلۀ کفِ امروز تا سطح " + ftsFa(out["level"]) + ")"
	} else if !bounced {
		out["reason"] = "لمسِ سطحِ پولبک رخ داده ولی بازگشت (پایانی بالای سطح با بدنهٔ صعودی) تأیید نشده — ستاپ در حال تشکیل"
	}
	return out
}
