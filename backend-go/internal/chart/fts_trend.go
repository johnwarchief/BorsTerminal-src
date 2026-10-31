package chart

import (
	"math"
	"strconv"
	"strings"
)

// recentWindowTrend معادلِ _fts_recent_window_trend: وقتی پیوتِ تازه‌ای تأیید
// نشده، جهت از شیبِ رگرسیونِ ۵۲ کندلِ اخیر و جایِ قیمت نسبت به میانگین خوانده
// می‌شود. کمتر از ۱۲ کندل ⇒ nil («سنجیده نشد»).
func recentWindowTrend(series []candle, window int) map[string]any {
	closes := make([]float64, 0, len(series))
	for _, c := range series {
		if pyIsFinite(c.Close) && c.Close > 0 {
			closes = append(closes, c.Close)
		}
	}
	n := len(closes)
	if n < ftsStaleMinBars {
		return nil
	}
	w := window
	if w > n {
		w = n
	}
	seg := closes[n-w:]
	meanY := 0.0
	for _, v := range seg {
		meanY += v
	}
	meanY /= float64(w)
	if meanY <= 0 {
		return nil
	}
	meanX := float64(w-1) / 2.0
	den, num := 0.0, 0.0
	for i := 0; i < w; i++ {
		dx := float64(i) - meanX
		den += dx * dx
		num += dx * (seg[i] - meanY)
	}
	slope := 0.0
	if den != 0 {
		slope = num / den
	}
	move := slope * float64(w-1) / meanY
	maN := window
	if maN > n {
		maN = n
	}
	maSum := 0.0
	for _, v := range closes[n-maN:] {
		maSum += v
	}
	ma := maSum / float64(maN)
	above := closes[n-1] >= ma
	var trend string
	switch {
	case move >= ftsStaleMoveMin && above:
		trend = "up"
	case move <= -ftsStaleMoveMin && !above:
		trend = "down"
	default:
		trend = "range"
	}
	return map[string]any{
		"trend": trend, "basis": "recent-window", "window": w,
		"move_pct": round1(move * 100.0), "ma": round2(ma),
		"last_close": round2(closes[n-1]), "above_ma": above,
	}
}

func baseTrend() map[string]any {
	return map[string]any{
		"trend": "na", "hh": nil, "hl": nil, "basis": "pivots",
		"last_high": nil, "prev_high": nil, "last_low": nil, "prev_low": nil,
		"last_high_time": nil, "prev_high_time": nil,
		"last_low_time": nil, "prev_low_time": nil,
		"stale_bars": nil, "window": nil,
	}
}

func copyMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m)+2)
	for k, v := range m {
		out[k] = v
	}
	return out
}

// classifyTrend معادلِ _fts_classify_trend: ساختارِ سقف/کف + رجوع به
// recent-window وقتی پیوت‌ها کهنه‌اند. `series == nil` یعنی فقط رأیِ پیوت.
func classifyTrend(sw []swing, tol float64, series []candle, staleBars int) map[string]any {
	highs := highsOf(sw)
	lows := lowsOf(sw)
	var piv map[string]any
	if len(highs) >= 2 && len(lows) >= 2 {
		structTrend := "na"
		var structuralHigh, structuralLow *float64
		var lastH, lastL *float64
		for _, s := range sw {
			p := s.Price
			if s.Kind == "high" {
				if lastH != nil && p > *lastH*(1+tol) {
					if structTrend != "up" {
						if structuralHigh == nil || p > *structuralHigh*(1+tol) {
							if lastL != nil {
								structTrend = "up"
								v := *lastL
								structuralLow = &v
							}
						}
					} else if lastL != nil && (structuralLow == nil || *lastL > *structuralLow) {
						v := *lastL
						structuralLow = &v
					}
				}
				v := p
				lastH = &v
			} else {
				if lastL != nil && p < *lastL*(1-tol) {
					if structTrend != "down" {
						if structuralLow == nil || p < *structuralLow*(1-tol) {
							if lastH != nil {
								structTrend = "down"
								v := *lastH
								structuralHigh = &v
							}
						}
					} else if lastH != nil && (structuralHigh == nil || *lastH < *structuralHigh) {
						v := *lastH
						structuralHigh = &v
					}
				}
				v := p
				lastL = &v
			}
		}
		h2, h1 := highs[len(highs)-2].Price, highs[len(highs)-1].Price
		l2, l1 := lows[len(lows)-2].Price, lows[len(lows)-1].Price
		hh := h1 > h2*(1+tol)
		hl := l1 > l2*(1+tol)
		lh := h1 < h2*(1-tol)
		ll := l1 < l2*(1-tol)
		var trend string
		switch {
		case hh && hl:
			trend = "up"
		case lh && ll:
			trend = "down"
		default:
			if structTrend == "up" || structTrend == "down" {
				trend = structTrend
			} else {
				trend = "range"
			}
		}
		piv = map[string]any{
			"trend": trend, "hh": hh, "hl": hl, "basis": "pivots",
			"last_high": round2(h1), "prev_high": round2(h2),
			"last_low": round2(l1), "prev_low": round2(l2),
			"last_high_time": strOrNilStr(highs[len(highs)-1].Time),
			"prev_high_time": strOrNilStr(highs[len(highs)-2].Time),
			"last_low_time":  strOrNilStr(lows[len(lows)-1].Time),
			"prev_low_time":  strOrNilStr(lows[len(lows)-2].Time),
			"stale_bars":     nil, "window": nil,
		}
		if series != nil && len(series) > 0 {
			lastClose := series[len(series)-1].Close
			hi2 := math.Max(h1, h2)
			lo2 := math.Min(l1, l2)
			if lastClose > hi2*(1+tol) {
				piv["price_confirm"] = "new-high-above-recent-pivots"
			} else if lastClose > 0 && lastClose < lo2*(1-tol) {
				piv["price_confirm"] = "new-low-below-recent-pivots"
			}
		}
	}
	withConfirm := func(p map[string]any) map[string]any {
		pc, _ := p["price_confirm"].(string)
		if pc == "" {
			return p
		}
		q := copyMap(p)
		if pc == "new-high-above-recent-pivots" {
			q["trend"] = "up"
		} else {
			q["trend"] = "down"
		}
		return q
	}
	if series == nil {
		if piv != nil {
			return piv
		}
		return baseTrend()
	}
	n := len(series)
	newest := -1
	for _, s := range sw {
		if s.Idx > newest {
			newest = s.Idx
		}
	}
	gap := n - 1 - newest
	if piv != nil && gap <= staleBars {
		return withConfirm(piv)
	}
	win := recentWindowTrend(series, ftsStaleWindow)
	if win == nil {
		if piv != nil {
			return piv
		}
		return baseTrend()
	}
	out := copyMap(win)
	out["stale_bars"] = gap
	if newest >= 0 && newest < n {
		out["last_pivot_time"] = strOrNilStr(series[newest].Time)
	} else {
		out["last_pivot_time"] = nil
	}
	out["hh"] = nil
	out["hl"] = nil
	out["last_high"] = nil
	out["prev_high"] = nil
	out["last_low"] = nil
	out["prev_low"] = nil
	if piv != nil {
		out["pivots"] = piv
	}
	return out
}

func strOrNilStr(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// pyFloatStr معادلِ str(float)ِ پایتون برای مقادیری که این موتور می‌سازد.
func pyFloatStr(x float64) string {
	if math.IsNaN(x) {
		return "nan"
	}
	if math.IsInf(x, 1) {
		return "inf"
	}
	if math.IsInf(x, -1) {
		return "-inf"
	}
	s := strconv.FormatFloat(x, 'f', -1, 64)
	if !strings.ContainsAny(s, ".eE") {
		s += ".0"
	}
	return s
}

// pyStr معادلِ str()ِ پایتون برای انواعِ خروجیِ موتور.
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case string:
		return x
	case bool:
		if x {
			return "True"
		}
		return "False"
	case float64:
		return pyFloatStr(x)
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	}
	return ""
}

// ftsFa معادلِ _fts_fa: ارقام به فارسی؛ None → «—».
func ftsFa(v any) string {
	if v == nil {
		return "—"
	}
	return faDigits(pyStr(v))
}

func faDigits(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(rune(0x06F0 + (r - '0')))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// trendReason معادلِ _fts_trend_reason.
func trendReason(t map[string]any) string {
	if t == nil {
		return ""
	}
	if b, _ := t["basis"].(string); b == "recent-window" {
		pos := "زیر"
		if pyTruthy(t["above_ma"]) {
			pos = "بالای"
		}
		txt := "مبنا: " + ftsFa(t["window"]) + " کندلِ اخیر، " +
			ftsFa(t["move_pct"]) + "٪ جابه‌جایی، قیمت " + pos + " میانگینِ ۵۲ دوره"
		if t["stale_bars"] != nil {
			txt += " (تازه‌ترین پیوتِ تأییدشده " + ftsFa(t["stale_bars"]) + " کندل عقب است)"
		}
		return txt
	}
	if tr, _ := t["trend"].(string); tr == "na" {
		return "مبنا: کمتر از دو پیوتِ کامل"
	}
	return "مبنا: سقف‌ها " + ftsFa(t["prev_high_time"]) + " (" + ftsFa(t["prev_high"]) +
		") ← " + ftsFa(t["last_high_time"]) + " (" + ftsFa(t["last_high"]) +
		")، کف‌ها " + ftsFa(t["prev_low_time"]) + " (" + ftsFa(t["prev_low"]) +
		") ← " + ftsFa(t["last_low_time"]) + " (" + ftsFa(t["last_low"]) + ")"
}
