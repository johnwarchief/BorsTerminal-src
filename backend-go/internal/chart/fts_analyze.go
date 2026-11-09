package chart

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
)

// hourglassSettings معادلِ _fts_hourglass_settings: defaults، سپس فایلِ
// fts_thresholds.json با اعتبارسنجیِ همان بازه‌ها. (هر فراخوانی فایل را
// می‌خواند؛ پایتون با امضایِ mtime/size کش می‌کند و پاسخ یکی است.)
func (s *Service) hourglassSettings() map[string]any {
	vals := map[string]any{
		"hourglass_rsi_period":    7,
		"hourglass_rsi_oversold":  30.0,
		"hourglass_ma52_position": "below",
	}
	raw, err := os.ReadFile(s.ftsPath)
	if err != nil {
		return vals
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil || doc == nil {
		return vals
	}
	// پایتون هر سه field را در یک try می‌خواند: `float(None)` که بترکد، هیچ‌کدام
	// از سه field عوض نمی‌شود. field‌به‌field ادامه دادن، تنظیمی نصفه می‌ساخت
	// که درِ پایتون هرگز دیده نمی‌شود.
	// `raw.get(key, default)` یعنی نبودِ کلید خطا نیست، پیش‌فرض است؛ فقط
	// مقدارِ بی‌اعتبار `float()` را می‌شکند و آن‌وقت هیچ‌کدام از سه field
	// عوض نمی‌شود.
	period, okP := hgNum(doc, "hourglass_rsi_period", 7)
	oversold, okO := hgNum(doc, "hourglass_rsi_oversold", 30.0)
	if !okP || !okO {
		return vals
	}
	mode, _ := doc["hourglass_ma52_position"].(string)
	if period == math.Trunc(period) && period >= 2 && period <= 100 {
		vals["hourglass_rsi_period"] = int(period)
	}
	if oversold >= 5.0 && oversold <= 50.0 {
		vals["hourglass_rsi_oversold"] = oversold
	}
	if mode == "below" || mode == "above" || mode == "either" {
		vals["hourglass_ma52_position"] = mode
	}
	return vals
}

func hgNum(doc map[string]any, key string, def float64) (float64, bool) {
	v, ok := doc[key]
	if !ok {
		return def, true
	}
	return toFloat(v)
}

func toFloat(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	case json.Number:
		f, err := x.Float64()
		return f, err == nil
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(x), 64)
		return f, err == nil
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	}
	return 0, false
}

// cleanCandles معادلِ _fts_clean_candles: مرتب، یکتا بر تاریخ، بی‌مقدارِ تهی.
func cleanCandles(rows []map[string]any) []candle {
	if len(rows) == 0 {
		return nil
	}
	byTime := map[string]candle{}
	for _, c := range rows {
		o, okO := toFloat(c["open"])
		h, okH := toFloat(c["high"])
		l, okL := toFloat(c["low"])
		cl, okC := toFloat(c["close"])
		if !okO || !okH || !okL || !okC {
			continue
		}
		valid := true
		for _, x := range []float64{o, h, l, cl} {
			if math.IsNaN(x) || x <= 0 {
				valid = false
				break
			}
		}
		if !valid {
			continue
		}
		t, _ := c["time"].(string)
		if len(t) > 10 {
			t = t[:10]
		}
		if t == "" {
			continue
		}
		vol := 0.0
		if v, ok := toFloat(c["volume"]); ok {
			vol = v
		}
		byTime[t] = candle{Time: t, Open: o, High: h, Low: l, Close: cl, Volume: vol,
			LiveForming: pyTruthy(c["live_forming"])}
	}
	keys := make([]string, 0, len(byTime))
	for k := range byTime {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := make([]candle, 0, len(keys))
	for _, k := range keys {
		out = append(out, byTime[k])
	}
	return out
}

// entry_hint همان قیمتِ سبد است — حدِ ضررِ تفکیکی به آن وابسته است.
func (s *Service) analyzeCandles(rows []map[string]any, symbol string, entryHint *float64) (out map[string]any) {
	candles := cleanCandles(rows)
	swingsD := swingsOf(candles, ftsSwingK)
	// ساختارِ جهت کندلِ تکمیل‌نشده را نمی‌بیند؛ ستاپ‌ها (جت/خروج/ساعت‌شنی) مثلِ
	// پایتون خودِ جلسه را می‌بینند (api/chart.py:5621-5636).
	structD := closedOnly(candles)
	wStruct := s.resampleFor(structD, "W", symbol)
	mStruct := s.resampleFor(structD, "M", symbol)
	w := s.resampleFor(candles, "W", symbol)
	m := s.resampleFor(candles, "M", symbol)

	type tfPack struct {
		graded  []gradedSwing
		majors  []gradedSwing
		info    map[string]any
		series  []candle
		verdict map[string]any
	}
	makeTF := func(series []candle, sw []swing) tfPack {
		graded := majorGrade(sw, series)
		majors, info := majorSummarize(graded)
		ms := majorSwingsOf(majors)
		var verdict map[string]any
		if s.engine == "hybrid" {
			verdict = classifyTrendHybrid(ms, series)
		} else {
			verdict = classifyTrend(ms, ftsEqualTol, series, ftsStaleBars)
		}
		return tfPack{graded: graded, majors: majors, info: info,
			series: series, verdict: verdict}
	}
	packs := map[string]tfPack{
		"D": makeTF(structD, swingsOf(structD, ftsSwingK)),
		"W": makeTF(wStruct, swingsOf(wStruct, 2)),
		"M": makeTF(mStruct, swingsOf(mStruct, 2)),
	}
	trend := map[string]any{
		"D": packs["D"].verdict, "W": packs["W"].verdict, "M": packs["M"].verdict,
		"alignment": "na",
	}
	tD := trend["D"].(map[string]any)["trend"].(string)
	tW := trend["W"].(map[string]any)["trend"].(string)
	tM := trend["M"].(map[string]any)["trend"].(string)
	if tD != "na" && tD == tW && tW == tM && (tD == "up" || tD == "down") {
		trend["alignment"] = tD
	}

	// پروندهِٔ «چه چیزی رأی را ساخت» — کنارِ رأی، نه داخلِ آن. `provisional` از
	// سریِ کامل (با کندلِ جلسه) خوانده می‌شود و هرگز رأی نمی‌سازد.
	fullSeries := map[string][]candle{"D": candles, "W": w, "M": m}
	kFor := map[string]int{"D": ftsSwingK, "W": 2, "M": 2}
	majorCtx := map[string]map[string]any{}
	for _, tf := range []string{"D", "W", "M"} {
		p := packs[tf]
		majorCtx[tf] = majorContext(tf, p.graded, p.majors, p.info,
			p.series, structD, fullSeries[tf], p.verdict, kFor[tf])
	}
	trend["major_swings"] = map[string]any{
		"D": majorCtx["D"], "W": majorCtx["W"], "M": majorCtx["M"]}
	trend["as_of"] = majorCtx["D"]["as_of"]

	var matrix map[string]any
	switch tW {
	case "down":
		matrix = matrixOf("REJECT", "NONE",
			"تایم هفتگی نزولی — وتوی کامل و ممنوعیت ورود (طبق چارت درختی FTS)")
	case "range":
		matrix = matrixOf("REJECT", "NONE",
			"تایم هفتگی خنثی — عدم ورود طبق چارت درختی FTS")
	case "na":
		matrix = matrixOf("UNKNOWN", "NONE",
			"روند هفتگی قابل تشخیص نیست (کمتر از دو پیوت کامل) — نظر داده نمی‌شود")
	case "up":
		switch tD {
		case "up":
			matrix = matrixOf("PERMITTED", "JET_OR_PULLBACK_HOLD",
				"هفتگی صعودی + روزانه صعودی: ستاپ جت یا پولبک؛ نگهداری روندی بدون نوسان‌گیری")
		case "down":
			matrix = matrixOf("PERMITTED", "FIB_CHOCH_STEP_ENTRY",
				"هفتگی صعودی + روزانه نزولی: ستاپ فیبوناچی لگاریتمی و CHoCH؛ ورود پله‌ای")
		case "na":
			matrix = matrixOf("UNKNOWN", "NONE",
				"هفتگی صعودی + روزانه سنجیده نشده (کمتر از دو پیوت کامل) — نظر داده نمی‌شود")
		default:
			matrix = matrixOf("PERMITTED", "DOUBLE_BOTTOM_OR_LAST_STRUCTURE",
				"هفتگی صعودی + روزانه خنثی: کف دوقلو یا ورود در آخرین کف روند صعودی/آخرین سقف روند نزولی")
		}
	}
	if matrix != nil {
		wReason := trendReasonCtx(trend["W"].(map[string]any), majorCtx["W"])
		dReason := trendReasonCtx(trend["D"].(map[string]any), majorCtx["D"])
		matrix["basis"] = map[string]any{"weekly": wReason, "daily": dReason}
		decision := matrix["decision"].(string)
		if decision == "REJECT" || decision == "UNKNOWN" {
			why := dReason
			if tW == "down" || tW == "range" || tW == "na" {
				why = wReason
			}
			if why != "" {
				matrix["desc"] = matrix["desc"].(string) + " — " + why
			}
		}
		trend["matrix"] = matrix
	}

	hgCfg := s.hourglassSettings()
	rsiPeriod, _ := hgCfg["hourglass_rsi_period"].(int)
	rsiOversold, _ := hgCfg["hourglass_rsi_oversold"].(float64)
	ma52Mode, _ := hgCfg["hourglass_ma52_position"].(string)
	closesW := make([]float64, 0, len(w))
	for _, c := range w {
		closesW = append(closesW, c.Close)
	}
	weeklyRsi := ftsRsi(closesW, rsiPeriod)
	var lastCW *float64
	if len(closesW) > 0 {
		v := closesW[len(closesW)-1]
		lastCW = &v
	}
	var lastRsi *float64
	if len(weeklyRsi) > 0 {
		lastRsi = weeklyRsi[len(weeklyRsi)-1]
	}
	maOK := len(closesW) >= 52
	rsiOK := lastRsi != nil
	var lastMa52 *float64
	if maOK {
		ma52 := ftsMa(closesW, 52)
		if len(ma52) > 0 {
			lastMa52 = ma52[len(ma52)-1]
		}
	}
	var match any
	if maOK && lastMa52 != nil && lastCW != nil {
		switch ma52Mode {
		case "below":
			match = *lastCW < *lastMa52
		case "above":
			match = *lastCW > *lastMa52
		default:
			match = true
		}
	}
	enough := maOK && rsiOK
	active := enough && pyTruthy(match) && lastRsi != nil && *lastRsi <= rsiOversold
	var hgDesc string
	switch {
	case active:
		switch ma52Mode {
		case "below":
			hgDesc = "ساعت شنی فعال: قیمت هفتگی زیر MA52 و RSI هفتگی در آستانه اشباع فروش (افزایش خرید ۲ تا ۴ برابر)"
		case "above":
			hgDesc = "ساعت شنی فعال: قیمت هفتگی بالای MA52 و RSI هفتگی در آستانه اشباع فروش (افزایش خرید ۲ تا ۴ برابر)"
		default:
			hgDesc = "ساعت شنی فعال: RSI هفتگی در آستانه اشباع فروش؛ گیت جهت MA52 خاموش است (افزایش خرید ۲ تا ۴ برابر)"
		}
	case !maOK:
		// P0 #7: تعدادِ موجود درِ خودِ متن — نه فقط کناریِ payload.
		hgDesc = "MA52 سنجیده نشد (" + ftsFa(len(closesW)) +
			" کندل هفتگی، حداقل ۵۲ لازم) — ساعت شنی نظر نمی‌دهد"
	case !rsiOK:
		hgDesc = "RSI(" + ftsFa(rsiPeriod) + ") هفتگی سنجیده نشد — سابقه کافی نیست (" +
			ftsFa(len(closesW)) + " کندل هفتگی، حداقل " + ftsFa(rsiPeriod+2) + " لازم)"
	default:
		hgDesc = "شرایط ساعت شنی با تنظیمات فعلی برقرار نیست"
	}
	var hgActive any
	if enough {
		hgActive = active
	}
	var weeklyClose, ma52Out, weeklyRsiOut any
	if lastCW != nil {
		weeklyClose = round2(*lastCW)
	}
	if lastMa52 != nil {
		ma52Out = round2(*lastMa52)
	}
	if lastRsi != nil {
		weeklyRsiOut = round1(*lastRsi)
	}
	action := "UNKNOWN"
	if active {
		action = "ACCELERATE_BUY_2X_4X"
	} else if enough {
		action = "NORMAL"
	}
	hourglass := map[string]any{
		"active": hgActive, "weekly_close": weeklyClose, "ma52": ma52Out,
		"weekly_bars": len(closesW), "weekly_rsi": weeklyRsiOut,
		"rsi_period": rsiPeriod, "rsi_oversold": rsiOversold,
		"ma52_position_mode": ma52Mode, "ma52_position_match": match,
		// پهنای سایۀ MA52 — پارامترِ اجرایىِ سرور (B4)، نه ساختۀ رابط.
		"ma52_band_pct": 3.0,
		"action":        action, "desc": hgDesc,
	}

	out = map[string]any{
		"trend":       trend,
		"fib":         fibZones(candles, swingsD),
		"jet":         jetSetup(candles, 250, 6, 3),
		"choch":       choch(candles, swingsD, ftsCHochDays, ftsCHochMargin),
		"point_hunt":  pointHunt(candles, swingsD),
		"exit_engine": nil,
		"hourglass":   hourglass,
		// نقاطِ ساختاریِ HH/HL/LH/LL — فقط ماژورها، با confirm_time جدا از وقتِ
		// وقوع (anti-repaint). روزانه تحلیل اصلی است؛ هفتگی زمینه/فیلتر.
		"structure_points": map[string]any{
			"D": structurePoints(majorSwingsOf(packs["D"].majors), 14),
			"W": structurePoints(majorSwingsOf(packs["W"].majors), 14),
		},
	}
	box := doubleBottom(candles, swingsD)
	out["double_bottom"] = box["double_bottom"]
	out["range_box"] = box["range_box"]
	out["pullback"] = pullbackSetup(candles, swingsD, tD, tW)
	out["exit_engine"] = exitEngine(candles, entryHint)
	out["setups"] = setupHistory(candles, swingsD, 40)
	// P0 #11: فهرستِ خالیِ زیرِ کفِ تاریخچه «۰ ستاپ» نیست؛ «ستاپ‌ها سنجیده نشد».
	need := setupsRequiredBars()
	state := "insufficient_history"
	if len(candles) >= need {
		state = "ok"
	}
	out["setups_state"] = state
	out["setups_bars_available"] = len(candles)
	out["setups_bars_required"] = need
	out["status"] = statusBlock(candles, out)
	out["roles"] = rolesCopy()
	return out
}

func matrixOf(decision, setup, desc string) map[string]any {
	return map[string]any{"decision": decision, "setup": setup, "desc": desc}
}

// analyzeCandlesSafe همان دو try/exceptِ پایتون است: `_fts_analyze_symbol`
// خطا را به `{"status":"error"}` می‌بَرَد و `get_chart_db` کلیدِ `fts` را `null`
// می‌گذارد. موتورِ hybrid رویِ سریِ تهی (و هر اشکالِ دیگری که پایتون در آن
// IndexError می‌گیرد) panic می‌کند؛ اینجا همان نقطه‌ای است که باید مهار شود.
func (s *Service) analyzeCandlesSafe(rows []map[string]any, symbol string, entryHint *float64) (
	out map[string]any, failure string) {
	defer func() {
		if r := recover(); r != nil {
			out, failure = nil, fmt.Sprint(r)
		}
	}()
	return s.analyzeCandles(rows, symbol, entryHint), ""
}
