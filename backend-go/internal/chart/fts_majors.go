package chart

import (
	"math"
	"sort"
	"strconv"
	"time"

	"borsterminal/backend/internal/pyround"
)

func parseISODate(s string) (time.Time, error) {
	return time.Parse("2006-01-02", s)
}

// پورتِ major_swings.py — درجه‌بندیِ سقف/کفِ «ماژور» پیش از داوریِ جهت.
//
// قاعدهٔ جزوه مقدم است (هفتگی وتو، روزانه شاخه)؛ این فایل داورِ جهت نمی‌سازد،
// فقط فهرستِ پیوت‌ها را به ماژور/غیرماژور درجه‌بندی می‌کند تا `classifyTrend`
// دو Extreme را از بینِ پیوت‌هایِ معتبرِ ماژور بردارد. آستانه‌ها پارامترِ اجرا
// هستند نه قانونِ جزوه (سندِ شاهد: _audit/MAJOR-SWING-EVIDENCE.json پایتون).
const (
	majorLegAtrX   = 2.0
	majorLegFloor  = 0.005
	majorAtrWindow = 52
	majorRecent    = 3
)

type gradedSwing struct {
	swing
	Major          *bool
	LegPct         *float64
	LegPctIn       *float64
	LegPctOut      *float64
	OutPending     bool
	LegAtrX        *float64
	Recent         bool
	ConfirmAgeBars int
	MA100Ctx       *string
}

type legMove struct {
	dir  string
	rel  float64
	abs  float64
	base float64
}

func majF(v float64) *float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 {
		return nil
	}
	return &v
}

func spanOf(base, here float64) (rel, abs float64, ok bool) {
	b, h := majF(base), majF(here)
	if b == nil || h == nil {
		return 0, 0, false
	}
	return math.Abs(*h-*b) / *b, math.Abs(*h - *b), true
}

// atrSeries معادلِ structure_engine3.atr_series: ATRِ Wilder؛ warm-up ⇒ nil.
func atrSeries(series []candle, period int) []*float64 {
	n := len(series)
	out := make([]*float64, n)
	if n < period {
		return out
	}
	tr := make([]*float64, n)
	for i := 0; i < n; i++ {
		h, l := series[i].High, series[i].Low
		base := h - l
		if i > 0 {
			prev := series[i-1].Close
			if a := math.Abs(h - prev); a > base {
				base = a
			}
			if a := math.Abs(l - prev); a > base {
				base = a
			}
		}
		v := base
		tr[i] = &v
	}
	sum := 0.0
	for i := 0; i < period; i++ {
		if tr[i] == nil {
			return out
		}
		sum += *tr[i]
	}
	atr := sum / float64(period)
	v := atr
	out[period-1] = &v
	for i := period; i < n; i++ {
		if tr[i] != nil {
			atr = (atr*float64(period-1) + *tr[i]) / float64(period)
		}
		x := atr
		out[i] = &x
	}
	return out
}

func legMoves(swings []swing, i int) []legMove {
	s := swings[i]
	moves := []legMove{}
	for j := i - 1; j >= 0; j-- {
		if swings[j].Kind != s.Kind {
			rel, mv, ok := spanOf(swings[j].Price, s.Price)
			if ok {
				moves = append(moves, legMove{"in", rel, mv, swings[j].Price})
			}
			break
		}
	}
	for j := i + 1; j < len(swings); j++ {
		if swings[j].Kind != s.Kind {
			rel, mv, ok := spanOf(s.Price, swings[j].Price)
			if ok {
				moves = append(moves, legMove{"out", rel, mv, s.Price})
			}
			break
		}
	}
	return moves
}

// atrRef معادلِ _atr_ref: میانهٔ ATRِ ۵۲ دورهٔ اخیر تا لحظهٔ upto.
func atrRef(atr []*float64, upto int) *float64 {
	lo := upto - majorAtrWindow + 1
	if lo < 0 {
		lo = 0
	}
	hi := upto + 1
	if hi > len(atr) {
		hi = len(atr)
	}
	seg := []float64{}
	for _, a := range atr[lo:hi] {
		if a != nil && *a != 0 {
			seg = append(seg, *a)
		}
	}
	if len(seg) == 0 {
		end := upto + 1
		if end < 1 {
			end = 1
		}
		if end > len(atr) {
			end = len(atr)
		}
		for _, a := range atr[:end] {
			if a != nil && *a != 0 {
				seg = append(seg, *a)
			}
		}
	}
	if len(seg) == 0 {
		return nil
	}
	sort.Float64s(seg)
	m := len(seg) / 2
	var med float64
	if len(seg)%2 == 1 {
		med = seg[m]
	} else {
		med = 0.5 * (seg[m-1] + seg[m])
	}
	return &med
}

// majorGrade معادلِ major_swings.grade — بدونِ نگاه‌به‌آینده: فقط تا confirm_idx.
func majorGrade(swings []swing, series []candle) []gradedSwing {
	n := len(series)
	if len(swings) == 0 || n == 0 {
		return []gradedSwing{}
	}
	atr := atrSeries(series, 14)
	ma := make([]*float64, n)
	run := 0.0
	const win = 100
	for i, c := range series {
		cl := c.Close
		if cl <= 0 || math.IsNaN(cl) {
			cl = 0
		}
		run += cl
		if i >= win {
			prev := series[i-win].Close
			if prev <= 0 || math.IsNaN(prev) {
				prev = 0
			}
			run -= prev
		}
		if i+1 >= win {
			v := run / float64(win)
			ma[i] = &v
		}
	}
	out := make([]gradedSwing, 0, len(swings))
	for i, s := range swings {
		moves := legMoves(swings, i)
		var ampIn, ampOut *float64
		rels := []float64{}
		for _, m := range moves {
			rels = append(rels, m.rel)
			v := m.rel
			if m.dir == "in" && ampIn == nil {
				ampIn = &v
			}
			if m.dir == "out" && ampOut == nil {
				ampOut = &v
			}
		}
		var amp *float64
		if len(rels) > 0 {
			m := rels[0]
			for _, r := range rels[1:] {
				if r > m {
					m = r
				}
			}
			amp = &m
		}
		ci := s.ConfirmIdx
		av := atrRef(atr, ci)
		var major *bool
		var legAtrX *float64
		if len(moves) > 0 {
			if av != nil && *av > 0 {
				any := false
				for _, m := range moves {
					thr := majorLegAtrX * *av
					if fl := majorLegFloor * m.base; fl > thr {
						thr = fl
					}
					if m.abs >= thr {
						any = true
					}
				}
				best := moves[0]
				for _, m := range moves[1:] {
					if m.abs > best.abs {
						best = m
					}
				}
				x := pyround.Round(best.abs / *av, 4)
				legAtrX = &x
				b := any
				major = &b
			} else {
				any := false
				for _, m := range moves {
					if m.rel >= majorLegFloor {
						any = true
					}
				}
				b := any
				major = &b
			}
		}
		age := n - 1 - ci
		var m100 *float64
		if s.Idx >= 0 && s.Idx < n {
			m100 = ma[s.Idx]
		}
		var ctx *string
		if m100 != nil && s.Price > 0 {
			t := "mid-ma100"
			if s.Kind == "low" && s.Price <= *m100 {
				t = "below-ma100"
			} else if s.Kind == "high" && s.Price >= *m100 {
				t = "above-ma100"
			}
			ctx = &t
		}
		var legPct, legPctIn, legPctOut *float64
		if amp != nil {
			v := pyround.Round(*amp, 6)
			legPct = &v
		}
		if ampIn != nil {
			v := pyround.Round(*ampIn, 6)
			legPctIn = &v
		}
		if ampOut != nil {
			v := pyround.Round(*ampOut, 6)
			legPctOut = &v
		}
		out = append(out, gradedSwing{
			swing: s, Major: major, LegPct: legPct, LegPctIn: legPctIn,
			LegPctOut: legPctOut, OutPending: ampOut == nil, LegAtrX: legAtrX,
			Recent: age < majorRecent, ConfirmAgeBars: age, MA100Ctx: ctx,
		})
	}
	return out
}

// majorSummarize معادلِ major_swings.summarize: فهرستِ ماژورها + شمارش‌ها.
// وقتی enough صادق نیست فراخوان نباید جهتِ پیش‌فرض بسازد.
func majorSummarize(graded []gradedSwing) ([]gradedSwing, map[string]any) {
	majors := []gradedSwing{}
	majorHighs, majorLows := 0, 0
	minorHighs, minorLows, undecided := 0, 0, 0
	for _, g := range graded {
		switch {
		case g.Major == nil:
			undecided++
		case *g.Major:
			majors = append(majors, g)
			if g.Kind == "high" {
				majorHighs++
			} else {
				majorLows++
			}
		default:
			if g.Kind == "high" {
				minorHighs++
			} else {
				minorLows++
			}
		}
	}
	enough := majorHighs >= 2 && majorLows >= 2
	var reason any
	if len(graded) > 0 && !enough {
		reason = "تنها " + strconv.Itoa(majorHighs) + " سقف و " +
			strconv.Itoa(majorLows) + " کفِ ماژور از " + strconv.Itoa(len(graded)) +
			" پیوت (آستانه " + pyFloatStr(majorLegAtrX) + "×ATR)"
	}
	info := map[string]any{
		"graded": len(graded), "major_highs": majorHighs, "major_lows": majorLows,
		"minor_highs": minorHighs, "minor_lows": minorLows,
		"undecided": undecided, "dropped_minor": len(graded) - len(majors),
		"enough": enough, "reason": reason,
		"atr_x": majorLegAtrX, "floor_pct": majorLegFloor,
	}
	return majors, info
}

func majorSwingsOf(majors []gradedSwing) []swing {
	out := make([]swing, 0, len(majors))
	for _, m := range majors {
		out = append(out, m.swing)
	}
	return out
}

// majorForming معادلِ major_swings.forming: سقف/کفِ در حالِ شکل‌گیری —
// اطلاعِ موقتِ جدا از پیوت‌هایِ قطعی (پنجرهٔ تأییدش کامل نشده).
func majorForming(series []candle, graded []gradedSwing, k int) map[string]any {
	n := len(series)
	if n == 0 {
		return nil
	}
	dates := make([]string, n)
	for i, c := range series {
		dates[i] = trim10(c.Time)
	}
	since := ""
	for _, g := range graded {
		d := trim10(g.Time)
		if d > since {
			since = d
		}
	}
	start := 0
	if since != "" {
		start = 0
		for _, d := range dates {
			if d <= since {
				start++
			}
		}
	}
	if start >= n {
		return nil
	}
	if k < 0 {
		k = 0
	}
	hiI, loI := start, start
	for j := start; j < n; j++ {
		if series[j].High > series[hiI].High {
			hiI = j
		}
		if series[j].Low < series[loI].Low {
			loI = j
		}
	}
	// تصمیمِ high/low با همان ترتیبِ پایتون است: قیمتِ leg تنها وقتی high است که
	// اندیسش با hi_i یکی باشد. اگر hi_i و lo_i رویِ یک کندل بیفتند (سایه‌هایِ
	// هم‌زمانِ سقف/کف)، هر دو leg قیمتِ high را گزارش می‌کنند — رفتارِ مرجع.
	leg := func(idx int) map[string]any {
		gap := n - 1 - idx
		price := series[idx].Low
		if idx == hiI {
			price = series[idx].High
		}
		toConfirm := k - gap
		if toConfirm < 0 {
			toConfirm = 0
		}
		return map[string]any{
			"idx": idx, "time": dates[idx], "price": price,
			"provisional": true, "confirmed": false,
			"bars_since": gap, "bars_to_confirm": toConfirm,
		}
	}
	var sinceOut any
	if since != "" {
		sinceOut = since
	}
	return map[string]any{
		"since_pivot_time": sinceOut, "bars_since_last_pivot": n - start,
		"high": leg(hiI), "low": leg(loI),
		"note": "پنجرۀ تأیید این دو کامل نشده؛ رأیِ قطعی روی آن‌ها ساخته نمی‌شود",
	}
}

// structurePoints معادلِ _fts_structure_points: برچسبِ HH/HL/LH/LL نسبت به
// ماژورِ هم‌جنسِ قبلی؛ فقط پیوتِ تأییدشده، با confirm_time جدا از time.
func structurePoints(swings []swing, limit int) []map[string]any {
	var lastH, lastL *swing
	pts := []map[string]any{}
	for i := range swings {
		s := swings[i]
		p := s.Price
		var ref *swing
		label := "H"
		if s.Kind == "high" {
			ref = lastH
			if ref != nil && ref.Price > 0 {
				if p > ref.Price*(1+ftsEqualTol) {
					label = "HH"
				} else if p < ref.Price*(1-ftsEqualTol) {
					label = "LH"
				} else {
					label = "HE"
				}
			}
			lastH = &s
		} else {
			ref = lastL
			label = "L"
			if ref != nil && ref.Price > 0 {
				if p > ref.Price*(1+ftsEqualTol) {
					label = "HL"
				} else if p < ref.Price*(1-ftsEqualTol) {
					label = "LL"
				} else {
					label = "LE"
				}
			}
			lastL = &s
		}
		var refTime, refPrice any
		if ref != nil {
			refTime = ref.Time
			refPrice = round2(ref.Price)
		}
		pts = append(pts, map[string]any{
			"idx": s.Idx, "time": s.Time,
			"confirm_idx": s.ConfirmIdx, "confirm_time": s.ConfirmTime,
			"price": round2(p), "kind": s.Kind, "label": label,
			"ref_time": refTime, "ref_price": refPrice,
		})
	}
	if len(pts) > limit {
		pts = pts[len(pts)-limit:]
	}
	return pts
}

// bucketForming معادلِ _fts_bucket_forming: آیا آخرین سبدِ هفتگی/ماهانه هنوز
// کندلِ روزانهٔ جدید می‌گیرد؟ اطلاع است، نه رأی.
func bucketForming(tf string, series, daily []candle) any {
	if tf == "D" || len(series) == 0 || len(daily) == 0 {
		return nil
	}
	dLast := trim10(daily[len(daily)-1].Time)
	if dLast == "" {
		return nil
	}
	last := trim10(series[len(series)-1].Time)
	if tf == "M" {
		return last != "" && len(dLast) >= 7 && len(last) >= 7 && dLast[:7] == last[:7]
	}
	d, err := parseISODate(last)
	if err != nil {
		return nil
	}
	wd := (int(d.Weekday()) + 6) % 7
	sat := d.AddDate(0, 0, -((wd + 2) % 7))
	return dLast < sat.AddDate(0, 0, 4).Format("2006-01-02")
}

// majorContext معادلِ _fts_major_context: پروندهٔ «چه چیزی رأی را ساخت».
func majorContext(tf string, graded []gradedSwing, majors []gradedSwing,
	info map[string]any, series, daily, fullSeries []candle,
	verdict map[string]any, k int) map[string]any {
	pt := func(g gradedSwing) map[string]any {
		var legPct, legIn, legOut, legAtr, ma100 any
		if g.LegPct != nil {
			legPct = *g.LegPct
		}
		if g.LegPctIn != nil {
			legIn = *g.LegPctIn
		}
		if g.LegPctOut != nil {
			legOut = *g.LegPctOut
		}
		if g.LegAtrX != nil {
			legAtr = *g.LegAtrX
		}
		if g.MA100Ctx != nil {
			ma100 = *g.MA100Ctx
		}
		return map[string]any{
			"idx": g.Idx, "time": g.Time, "kind": g.Kind,
			"price":       round2(g.Price),
			"confirm_idx": g.ConfirmIdx, "confirm_time": g.ConfirmTime,
			"confirm_age_bars": g.ConfirmAgeBars,
			"leg_pct":          legPct, "leg_pct_in": legIn, "leg_pct_out": legOut,
			"out_pending": g.OutPending, "leg_atr_x": legAtr,
			"recent": g.Recent, "ma100_ctx": ma100,
		}
	}
	points := []map[string]any{}
	start := len(majors) - 12
	if start < 0 {
		start = 0
	}
	for _, g := range majors[start:] {
		points = append(points, pt(g))
	}
	var asOf, dailyAsOf any
	if len(series) > 0 {
		asOf = trim10(series[len(series)-1].Time)
	}
	if len(daily) > 0 {
		dailyAsOf = trim10(daily[len(daily)-1].Time)
	}
	var provisional any
	if p := majorForming(fullSeries, graded, k); p != nil {
		provisional = p
	}
	var reason any
	if r, ok := info["reason"].(string); ok {
		reason = ftsFa(r)
	}
	td := verdict["trend"]
	var basis any
	if b, ok := verdict["basis"]; ok {
		basis = b
	}
	return map[string]any{
		"timeframe": tf, "confirmed_trend": td, "verdict_basis": basis,
		"as_of": asOf, "daily_as_of": dailyAsOf, "bars": len(series),
		"bucket_forming": bucketForming(tf, series, daily),
		"major_swings":   points,
		"counts": map[string]any{
			"pivots": info["graded"], "majors": len(majors),
			"major_highs": info["major_highs"], "major_lows": info["major_lows"],
			"minor_highs": info["minor_highs"], "minor_lows": info["minor_lows"],
			"undecided": info["undecided"], "dropped_minor": info["dropped_minor"],
		},
		"threshold":       map[string]any{"atr_x": info["atr_x"], "floor_pct": info["floor_pct"]},
		"enough_extremes": info["enough"],
		"provisional":     provisional,
		"reason":          reason,
	}
}

// trendReasonCtx معادلِ _fts_trend_reason(t, ctx): ctx فقط متن را دقیق‌تر
// می‌کند و هیچ دروازه‌ای به آن وابسته نیست.
func trendReasonCtx(t map[string]any, ctx map[string]any) string {
	if t == nil {
		return ""
	}
	hasCtx := false
	ctxEnough := false
	ctxReason := ""
	if ctx != nil {
		if _, ok := ctx["enough_extremes"]; ok {
			hasCtx = true
			ctxEnough = pyTruthy(ctx["enough_extremes"])
			if s, ok := ctx["reason"].(string); ok {
				ctxReason = s
			}
		}
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
		if hasCtx && !ctxEnough && ctxReason != "" {
			txt += " — ساختارِ ماژور کافی نبود: " + ftsFa(ctxReason)
		}
		return txt
	}
	if tr, _ := t["trend"].(string); tr == "na" {
		if hasCtx && ctxReason != "" {
			return "مبنا: " + ftsFa(ctxReason) + " — دو Extreme ماژور نیست، جهت اعلام نمی‌شود"
		}
		return "مبنا: کمتر از دو پیوتِ کامل (کمبود داده)"
	}
	head := "مبنا"
	if hasCtx && ctxEnough {
		head = "مبنایِ ماژور"
	}
	return head + ": سقف‌ها " + ftsFa(t["prev_high_time"]) + " (" + ftsFa(t["prev_high"]) +
		") ← " + ftsFa(t["last_high_time"]) + " (" + ftsFa(t["last_high"]) +
		")، کف‌ها " + ftsFa(t["prev_low_time"]) + " (" + ftsFa(t["prev_low"]) +
		") ← " + ftsFa(t["last_low_time"]) + " (" + ftsFa(t["last_low"]) + ")"
}

// trendReason بدونِ ctx — همان امضایِ مصرف‌کننده‌هایِ قبلی.
func trendReason(t map[string]any) string { return trendReasonCtx(t, nil) }
