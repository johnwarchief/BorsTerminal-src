package mstat

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"
	"sync"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

// این فایل پورتِ «حکمِ امروز» (mstat_engine.day_verdict) و «وضعیتِ مرحله‌مند»
// (_market_state) است. هیچ آستانه‌ای این‌جا ساخته نمی‌شود: HEMAT_GOOD/BAD،
// ۸۰٪ فرصتِ ورود، ۳ نشستِ تداوم، ۳۰ دقیقه شکل‌گیری و ۳ ارزیابیِ متوالی همان
// اعدادِ جزوه‌اند که در mstat_engine نشسته‌اند.

const (
	hematGood             = 20.0
	hematBad              = 10.0
	entryOpportunityNeg   = 80.0
	liqContinuityMin      = 3
	liqBackfillMinSymbols = 1200
	formationMinutes      = 30
	verdictConfirmCount   = 3
)

// ── حافظهٔ درون‌سرویسِ حکم ────────────────────────────────────────────────
// معادلِ _ASSESS و _STATE_MEMOِ پایتون: هر دو dictِ ماژول‌اند و فقط با فرایندِ
// تازه صفر می‌شوند. این‌جا در Service می‌نشینند تا تست نمونهٔ تازه بسازد و
// درخواست‌هایِ یک فرایند همان رفتارِ «مشاهدهٔ تازه» را ببینند.

type assessState struct {
	h   int64
	neg int
}

type verdictMemo struct {
	mu     sync.Mutex
	assess map[string]*assessState
	state  map[string]string
}

func newVerdictMemo() *verdictMemo {
	return &verdictMemo{assess: map[string]*assessState{}, state: map[string]string{}}
}

func memoKey(day *int64) string {
	if day == nil {
		return "None"
	}
	return strconv.FormatInt(*day, 10)
}

// negStreak همان _neg_streak: فقط دادهٔ با h_evenِ تازه‌تر ارزیابیِ مستقل است.
func (m *verdictMemo) negStreak(day *int64, hEven any, negativeNow, positiveNow bool) int {
	if m == nil {
		return 0
	}
	key := memoKey(day)
	h := int64(f0(toF(hEven)))
	m.mu.Lock()
	defer m.mu.Unlock()
	st := m.assess[key]
	if st == nil {
		st = &assessState{h: -1}
		m.assess[key] = st
	}
	if h > st.h {
		st.h = h
		if negativeNow {
			st.neg++
		} else if positiveNow {
			st.neg = 0
		}
	}
	return st.neg
}

// previousAndRemember همان _STATE_MEMO: حکمِ ارزیابیِ پیش برایِ «تغییر وضعیت».
func (m *verdictMemo) previousAndRemember(day *int64, verdict string) any {
	if m == nil {
		return nil
	}
	key := memoKey(day)
	m.mu.Lock()
	defer m.mu.Unlock()
	prev, ok := m.state[key]
	m.state[key] = verdict
	if ok && prev != "" && prev != verdict {
		return prev
	}
	return nil
}

// ── دسترسیِ امن به mapهایِ بدنه ────────────────────────────────────────────

func mnum(m map[string]any, k string) (float64, bool) {
	v, ok := m[k]
	if !ok || v == nil {
		return 0, false
	}
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	case json.Number:
		f, err := n.Float64()
		return f, err == nil
	}
	return 0, false
}

func mbool(m map[string]any, k string) bool {
	b, _ := m[k].(bool)
	return b
}

// ── عدد و متنِ فارسی ──────────────────────────────────────────────────────

// faDigits همان _FA_DIGITS: هر رقمِ ASCII در متن به رقمِ فارسی.
func faDigits(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(0x06F0 + (r - '0'))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// faNum همان _fa_num: «%.2f» و ریختنِ صفرهایِ زائد، بعد رقمِ فارسی.
func faNum(v any) string {
	if v == nil {
		return "—"
	}
	var f float64
	switch n := v.(type) {
	case float64:
		f = n
	case float32:
		f = float64(n)
	case int:
		f = float64(n)
	case int64:
		f = float64(n)
	case string:
		return faDigits(n)
	default:
		return faDigits(fmt.Sprint(v))
	}
	s := strconv.FormatFloat(f, 'f', 2, 64)
	s = strings.TrimRight(s, "0")
	s = strings.TrimRight(s, ".")
	return faDigits(s)
}

// faSigned همان _fa_signed: علامتِ صریح و U+2212 برایِ منفی.
func faSigned(v any) string {
	if v == nil {
		return "بدون داده"
	}
	f, ok := toNumber(v)
	if !ok {
		return faNum(v)
	}
	sign := ""
	if f > 0 {
		sign = "+"
	} else if f < 0 {
		sign = "−"
	}
	return sign + faNum(math.Abs(f))
}

func toNumber(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	}
	return 0, false
}

// hmFromHEven همان _hm_from_h_even: دقایقِ پس از نیمه‌شب از h_even؛ -1 یعنی نرسیده.
func hmFromHEven(v any) int {
	s := fmt.Sprintf("%06d", int64(f0(toF(v))))
	if s == "000000" {
		return -1
	}
	a, _ := strconv.Atoi(s[0:2])
	b, _ := strconv.Atoi(s[2:4])
	return a*60 + b
}

func hmToClock(minutes *int) any {
	if minutes == nil {
		return nil
	}
	h, m := *minutes/60, *minutes%60
	return faDigits(fmt.Sprintf("%02d:%02d", h, m))
}

// ── پنجرهٔ ساعت، نقدینگی و تاریخچه ────────────────────────────────────────

// clockWindow همان _clock_window: ساعت از h_evenِ خودِ داده، نه دیوار.
func clockWindow(hEven any) map[string]any {
	s := fmt.Sprintf("%06d", int64(f0(toF(hEven))))
	hm, hhmm := -1, ""
	if s != "000000" {
		a, _ := strconv.Atoi(s[0:2])
		b, _ := strconv.Atoi(s[2:4])
		hm = a*60 + b
		hhmm = s[0:2] + ":" + s[2:4]
	}
	if hm < 0 {
		return map[string]any{"state": "nodata", "label": "بدون داده", "detail": nil}
	}
	hhmm = faDigits(hhmm)
	if 540 <= hm && hm < 570 {
		return map[string]any{"state": "ok", "label": "پنجرهٔ درآمد ثابت باز است",
			"detail": "۰۹:۰۰–۰۹:۳۰ (ساعتِ داده " + hhmm + ") — صندوق‌های درآمد ثابت در این" +
				" نیم‌ساعت خرید می‌کنند"}
	}
	if 735 <= hm && hm <= 750 {
		return map[string]any{"state": "ok", "label": "پنجرهٔ شفافیتِ طلا",
			"detail": "۱۲:۱۵–۱۲:۳۰ (ساعتِ داده " + hhmm + ") — جریانِ صندوقِ طلا در این" +
				" بازه روشن می‌شود"}
	}
	return map[string]any{"state": "mid", "label": "خارجِ پنجره‌ها",
		"detail": "ساعتِ داده " + hhmm + " · پنجره‌های جزوه ۰۹:۰۰–۰۹:۳۰ و ۱۲:۱۵–۱۲:۳۰‌اند"}
}

// liqSide همان _liq_side: تنها جایِ داوریِ عددِ همت.
func liqSide(hemat float64, has bool) string {
	if !has {
		return "nodata"
	}
	v := f0(hemat)
	if v <= 0 {
		return "nodata"
	}
	if v >= hematGood {
		return "good"
	}
	if v <= hematBad {
		return "bad"
	}
	return "mid"
}

// liquidityHistory همان liquidity_history: اتحادِ market_liquidity (نشستِ باز)
// و daily_prices (عددِ نهاییِ نشستِ بسته)، تازه‌ترین اول، حداکثر limit ردیف.
func liquidityHistory(db *sql.DB, limit int) []map[string]any {
	stored := map[int64]float64{}
	if rows, err := db.Query(`SELECT d_even, value_hemat FROM market_liquidity
	    ORDER BY d_even DESC LIMIT ?`, limit); err == nil {
		for rows.Next() {
			var d, v sql.NullFloat64
			if rows.Scan(&d, &v) != nil {
				continue
			}
			if x := f0(v.Float64); x > 0 {
				stored[int64(f0(d.Float64))] = pyround.Round(x, 2)
			}
		}
		rows.Close()
	}
	var days []int
	if rows, err := db.Query(`SELECT DISTINCT d_even FROM daily_prices
	    ORDER BY d_even DESC LIMIT ?`, limit*3); err == nil {
		for rows.Next() {
			var d sql.NullFloat64
			if rows.Scan(&d) == nil {
				days = append(days, int(f0(d.Float64)))
			}
		}
		rows.Close()
	}
	final := map[int]float64{}
	for _, h := range liquidityFromPriceHistory(db, days, liqBackfillMinSymbols) {
		if v, ok := h["value_hemat"].(float64); ok && v != 0 {
			final[h["d_even"].(int)] = v
		}
	}
	seen := map[int]bool{}
	keys := []int{}
	for _, d := range days {
		if !seen[d] {
			seen[d] = true
			keys = append(keys, d)
		}
	}
	for d := range stored {
		k := int(d)
		if !seen[k] {
			seen[k] = true
			keys = append(keys, k)
		}
	}
	sort.Sort(sort.Reverse(sort.IntSlice(keys)))
	out := []map[string]any{}
	for _, d := range keys {
		var val float64
		if v, ok := final[d]; ok && v != 0 {
			val = v
		} else if v, ok := stored[int64(d)]; ok {
			val = v
		}
		if val == 0 {
			continue
		}
		out = append(out, map[string]any{"d_even": d, "value_hemat": val})
		if len(out) >= limit {
			break
		}
	}
	return out
}

// eqAllCodes همان _eq_all_codes: سهام + حق‌تقدم + ص.سهامی/مختلط، از خودِ
// classify — همان تابعی که عددِ امروز را دسته‌بندی می‌کند، تا تاریخچه هم‌مبنا باشد.
func eqAllCodes(db *sql.DB) map[string]bool {
	codes := map[string]bool{}
	rows, err := db.Query(`SELECT ins_code, paper_type, l_val30, l_val18, sector_name
	    FROM instruments`)
	if err != nil {
		return codes
	}
	defer rows.Close()
	for rows.Next() {
		var code string
		var pt sql.NullInt64
		var name, sym, sector sql.NullString
		if rows.Scan(&code, &pt, &name, &sym, &sector) != nil {
			continue
		}
		var ptp *int64
		if pt.Valid {
			v := pt.Int64
			ptp = &v
		}
		cls, kind := classify(ptp, name.String, sym.String, sector.String)
		if cls == paperStock || cls == paperRight ||
			(cls == paperFund && (kind == "equity" || kind == "fof")) {
			codes[code] = true
		}
	}
	return codes
}

// liquidityFromPriceHistory همان _liquidity_from_price_history: گردشِ روزانۀ
// eq_all در همت؛ روزی که کمتر از minSymbols نمادِ گردش‌دار دارد نصفه است و
// دور ریخته می‌شود (عددِ نصفه «تداومِ نامساعد» نمی‌سازد).
func liquidityFromPriceHistory(db *sql.DB, dates []int, minSymbols int) []map[string]any {
	if len(dates) == 0 {
		return nil
	}
	codes := eqAllCodes(db)
	if len(codes) == 0 {
		return nil
	}
	marks := strings.TrimSuffix(strings.Repeat("?,", len(dates)), ",")
	args := make([]any, len(dates))
	for i, d := range dates {
		args[i] = d
	}
	rows, err := db.Query(`SELECT d_even, ins_code, q_tot_cap FROM daily_prices
	    WHERE q_tot_cap > 0 AND d_even IN (`+marks+`)`, args...)
	if err != nil {
		return nil
	}
	defer rows.Close()
	tot, cnt := map[int]float64{}, map[int]int{}
	for rows.Next() {
		var d, val sql.NullFloat64
		var code string
		if rows.Scan(&d, &code, &val) != nil {
			continue
		}
		if !codes[code] {
			continue
		}
		k := int(f0(d.Float64))
		tot[k] += f0(val.Float64)
		cnt[k]++
	}
	out := []map[string]any{}
	for _, d := range dates {
		if cnt[d] < minSymbols {
			continue
		}
		out = append(out, map[string]any{"d_even": d,
			"value_hemat": pyround.Round(tot[d]/1e13, 2)})
	}
	return out
}

// sessionStartHM همان _session_start_hm: نخستین دقیقۀ امروز با ارزشِ غیرصفر.
func sessionStartHM(db *sql.DB, day *int64) *int {
	if day == nil || *day == 0 {
		return nil
	}
	rows, err := db.Query(`SELECT h_even, agg FROM mstat_snap
	    WHERE d_even=? AND h_even>=? ORDER BY h_even`, *day, 85500)
	if err != nil {
		return nil
	}
	defer rows.Close()
	for rows.Next() {
		var h sql.NullInt64
		var agg []byte
		if rows.Scan(&h, &agg) != nil {
			continue
		}
		var j map[string]any
		if json.Unmarshal(agg, &j) != nil {
			continue
		}
		if v, ok := mnum(j, "val_bt"); ok && v > 0 {
			hm := hmFromHEven(h.Int64)
			return &hm
		}
	}
	return nil
}

// flowTrend همان _flow_trend: جهتِ تغییرِ جریانِ تجمعی در آخرین نقاطِ نشست.
func flowTrend(db *sql.DB, day *int64, hEven any) (string, int) {
	if day == nil || *day == 0 || hEven == nil || f0(toF(hEven)) == 0 {
		return "nodata", 0
	}
	h := int64(f0(toF(hEven)))
	rows, err := db.Query(`SELECT agg FROM mstat_snap WHERE d_even=?
	    AND h_even<=? AND h_even>=? ORDER BY h_even DESC LIMIT ?`,
		*day, h, 85500, verdictConfirmCount+1)
	if err != nil {
		return "nodata", 0
	}
	defer rows.Close()
	vals := []float64{}
	for rows.Next() {
		var b []byte
		if rows.Scan(&b) != nil {
			continue
		}
		var j map[string]any
		if json.Unmarshal(b, &j) != nil {
			continue
		}
		if v, ok := mnum(j, "flow_eq_bt"); ok {
			vals = append(vals, v)
		}
	}
	for i, j := 0, len(vals)-1; i < j; i, j = i+1, j-1 {
		vals[i], vals[j] = vals[j], vals[i]
	}
	if len(vals) < 2 {
		n := len(vals) - 1
		if n < 0 {
			n = 0
		}
		return "nodata", n
	}
	worsening, improving := true, true
	for i := 1; i < len(vals); i++ {
		d := vals[i] - vals[i-1]
		if d > 0 {
			worsening = false
		}
		if d < 0 {
			improving = false
		}
	}
	n := len(vals) - 1
	if worsening {
		return "worsening", n
	}
	if improving {
		return "improving", n
	}
	return "mixed", n
}

// sameClockRef همان _same_clock_ref: میانهٔ گردشِ «همین ساعت»ِ نشست‌هایِ پیش.
func sameClockRef(db *sql.DB, day *int64, hEven any, field string) (*float64, int) {
	if day == nil || *day == 0 || hEven == nil || f0(toF(hEven)) == 0 {
		return nil, 0
	}
	h := int64(f0(toF(hEven)))
	rows, err := db.Query(`SELECT DISTINCT d_even FROM mstat_snap WHERE d_even<?
	    ORDER BY d_even DESC LIMIT ?`, *day, 8)
	if err != nil {
		return nil, 0
	}
	days := []int64{}
	for rows.Next() {
		var d sql.NullInt64
		if rows.Scan(&d) == nil {
			days = append(days, d.Int64)
		}
	}
	rows.Close()
	vals := []float64{}
	for _, d := range days {
		var agg []byte
		err := db.QueryRow(`SELECT agg FROM mstat_snap WHERE d_even=? AND h_even<=?
		    AND h_even>=? ORDER BY h_even DESC LIMIT 1`, d, h, 85500).Scan(&agg)
		if err != nil {
			continue
		}
		var j map[string]any
		if json.Unmarshal(agg, &j) != nil {
			continue
		}
		if v, ok := mnum(j, field); ok {
			vals = append(vals, v)
		}
	}
	if len(vals) == 0 {
		return nil, 0
	}
	sort.Float64s(vals)
	var mid float64
	if len(vals)%2 == 1 {
		mid = vals[len(vals)/2]
	} else {
		mid = (vals[len(vals)/2-1] + vals[len(vals)/2]) / 2.0
	}
	r := pyround.Round(mid, 1)
	return &r, len(vals)
}

// ── درها و حکم ────────────────────────────────────────────────────────────

func gateBody(key, label, short, state, labelState string, vote int, detail any, rule, why string) map[string]any {
	return map[string]any{"key": key, "label": label, "short": short,
		"state": state, "label_state": labelState, "vote": vote,
		"detail": detail, "rule": rule, "why": why}
}

// flowTrio همان _flow_trio: (trio، gold_out) — تنها جایِ بستنِ سه‌شرطِ ص۱۴.
func flowTrio(flow map[string]any) (bool, any) {
	gd, hasGd := mnum(flow, "gold_flow_b_toman")
	goldOut := flow["gold_outflow"]
	if goldOut == nil && hasGd {
		goldOut = gd < 0
	}
	core := mbool(flow, "eq_inflow") && mbool(flow, "fixed_outflow")
	return core && goldOut != false, goldOut
}

func clause(gates []map[string]any, sep string) string {
	parts := make([]string, 0, len(gates))
	for _, g := range gates {
		parts = append(parts, fmt.Sprint(g["short"])+": "+fmt.Sprint(g["label_state"]))
	}
	return strings.Join(parts, sep)
}

func gateWhy(key, state string, macro, entry map[string]any) string {
	good := hematGood
	if v, ok := mnum(macro, "good_min"); ok {
		good = v
	}
	bad := hematBad
	if v, ok := mnum(macro, "bad_max"); ok {
		bad = v
	}
	bear, hasBear := mnum(entry, "bearish_pct")
	switch key {
	case "liquidity":
		switch state {
		case "ok":
			return "ارزش معاملات بازار سهام بالایِ کفِ جزوه (" + faNum(good) + " همت)"
		case "bad":
			return "ارزش معاملات بازار سهام زیرِ " + faNum(bad) + " همت — بازار راکد است"
		case "mid":
			return "ارزش معاملات بازار سهام میانِ " + faNum(bad) + " تا " + faNum(good) +
				" همت — نه روزِ ورود، نه رکود"
		default:
			return "ارزشِ معاملاتِ امروز هنوز نیامده — داوری در کار نیست"
		}
	case "continuity":
		n := faNum(liqContinuityMin)
		switch state {
		case "ok":
			return n + " نشستِ متوالی بالایِ " + faNum(good) + " همت — نقدینگیِ امروز تصادفی نیست"
		case "bad":
			return n + " نشستِ متوالی زیرِ " + faNum(bad) + " همت — رکودِ چند روزه"
		case "mid":
			return "جهتِ نقدینگی در " + n + " نشستِ اخیر یکی نبوده"
		default:
			return "تاریخچۀ " + n + " نشستِ اخیر کامل نشده"
		}
	case "breadth":
		thr := faNum(entryOpportunityNeg)
		switch state {
		case "ok":
			if hasBear {
				return faNum(bear) + "٪ از نمادها نزولی بودند — جزوه این را کفِ بازار می‌خواند، نه هشدار"
			}
			return "منفی‌ها از آستانۀ " + thr + "٪ گذشته‌اند — کفِ بازار، نه هشدار"
		case "mid":
			s := "منفی‌ها از آستانۀ " + thr + "٪ پایین‌تر بوده"
			if hasBear {
				s += " (همین حالا " + faNum(bear) + "٪)"
			}
			return s + " — نشانه‌ای برای ورود نیست"
		case "bad":
			return "بیشترِ نمادها نزولی‌اند — ریزشِ عمومی"
		default:
			return "شمارشِ مثبت و منفیِ امروز نیامده"
		}
	case "flow":
		switch state {
		case "ok":
			return "پولِ حقیقی هم‌زمان از درآمد ثابت و طلا به سهام آمده — وضعِ مطلوبِ جزوه"
		case "bad":
			return "پولِ حقیقی از سهام بیرون رفته — جهتِ مخالفِ ورود"
		case "mid":
			return "سه شرطِ وضعِ مطلوب یکجا برقرار نیست؛ جهتِ پول روشن نشده"
		default:
			return "تفکیکِ خرید و فروشِ حقیقی برای امروز نیست"
		}
	case "window":
		switch state {
		case "ok":
			return "ساعتِ داده روی یکی از پنجره‌هایِ جزوه نشسته (بازه در سطرِ پایین)"
		case "mid":
			return "بیرونِ پنجره‌هایِ جزوه — این شرط رأیی در حکم ندارد"
		case "bad":
			return "پنجرهٔ جزوه بسته است"
		default:
			return "ساعتِ داده همراه نیست"
		}
	}
	return ""
}

// dayVerdict همان day_verdict. sm (macro/entry/flow/asof) همان بدنهٔ smart_money
// است؛ phase تزریقی است تا smart_money یک‌بار از بانک بخواند.
func dayVerdict(db *sql.DB, macro, entry, flow, asof map[string]any,
	ph marketphase.Phase, memo *verdictMemo) map[string]any {
	partial := mbool(macro, "partial_session") || ph.Phase == marketphase.Continuous
	hm := hmFromHEven(asof["h_even"])

	// ۱) نقدینگی
	hemat, hasHemat := mnum(macro, "value_hemat")
	side := liqSide(hemat, hasHemat)
	var liqDetail any
	if hasHemat {
		liqDetail = faNum(hemat) + " همت"
	}
	var liqState, liqLabel string
	liqVote := 0
	if side == "bad" && partial {
		liqState, liqLabel, liqVote = "mid", "هنوز نه‌شده", 0
		liqDetail = faNum(hemat) + " همت تا این لحظه — آستانه رویِ جمعِ کاملِ نشست است"
	} else {
		switch side {
		case "good":
			liqState = "ok"
			if mbool(macro, "excellent") {
				liqLabel = "عالی"
			} else {
				liqLabel = "مساعد"
			}
			liqVote = 1
		case "bad":
			liqState, liqLabel, liqVote = "bad", "نامساعد", -1
		case "mid":
			liqState, liqLabel, liqVote = "mid", "متوسط", 0
		default:
			liqState, liqLabel, liqVote = "nodata", "بدون داده", 0
		}
	}
	gates := []map[string]any{gateBody("liquidity", "ارزش معاملات بازار سهام", "نقدینگی",
		liqState, liqLabel, liqVote, liqDetail,
		"بالایِ ۲۰ خوب · بالایِ ۵۰ عالی · زیرِ ۱۰ نامساعد (جزوه ص۱۳)", "")}

	// ۱ب) تداومِ ۳ تا ۴ نشست — ردیفِ نیمه‌کارِ امروز در «سه نشستِ اخیر» نمی‌نشیند.
	hist := liquidityHistory(db, liqContinuityMin+2)
	if partial && ph.SessionDay != nil {
		kept := hist[:0]
		for _, h := range hist {
			if d, ok := h["d_even"].(int); !ok || int64(d) != *ph.SessionDay {
				kept = append(kept, h)
			}
		}
		hist = kept
	}
	var contState, contLabel string
	contVote := 0
	var contDetail string
	known := len(hist)
	if known < liqContinuityMin {
		contState, contLabel = "nodata", "بدون داده"
		contDetail = "تاریخچه کامل نیست — " + faNum(known) + " نشست از " + faNum(liqContinuityMin)
	} else {
		n := liqContinuityMin
		allGood, allBad := true, true
		parts := make([]string, 0, n)
		for _, h := range hist[:n] {
			v, _ := mnum(h, "value_hemat")
			s := liqSide(v, true)
			if s != "good" {
				allGood = false
			}
			if s != "bad" {
				allBad = false
			}
			parts = append(parts, faNum(v)+" همت")
		}
		switch {
		case allGood:
			contState, contLabel, contVote = "ok", "تداومِ مساعد", 1
		case allBad:
			contState, contLabel, contVote = "bad", "تداومِ نامساعد", -1
		default:
			contState, contLabel, contVote = "mid", "بدونِ تداوم", 0
		}
		contDetail = faNum(n) + " نشستِ اخیر: " + strings.Join(parts, " · ")
	}
	gates = append(gates, gateBody("continuity", "روند ۳ تا ۴ نشستِ اخیر", "روندِ اخیر",
		contState, contLabel, contVote, contDetail,
		"همان جهتِ نقدینگی در ۳ تا ۴ نشستِ پیاپی (جزوه ص۱۳)", ""))

	// ۲) پهنایِ بازار
	bear, hasBear := mnum(entry, "bearish_pct")
	var breadthState, breadthLabel string
	breadthVote := 0
	var breadthDetail any
	if !hasBear {
		breadthState, breadthLabel = "nodata", "بدون داده"
		if k, ok := mnum(entry, "known"); ok && k != 0 {
			breadthDetail = faNum(k) + " نمادِ معامله‌شده شمرده شد"
		}
	} else if mbool(entry, "active") {
		breadthState, breadthLabel, breadthVote = "ok", "فرصتِ ورود", 1
		breadthDetail = faNum(bear) + "٪ از نمادهایِ معامله‌شده منفی یا در صفِ فروش"
	} else {
		breadthState, breadthLabel = "mid", "بدونِ فرصتِ کف"
		breadthDetail = faNum(bear) + "٪ منفی — آستانهٔ فرصت " + faNum(entryOpportunityNeg) + "٪"
	}
	gates = append(gates, gateBody("breadth", "درصدِ نمادهایِ نزولی", "پهنایِ بازار",
		breadthState, breadthLabel, breadthVote, breadthDetail,
		"۸۰٪ منفی = بازار فرصتِ ورود دارد، نه هشدار (جزوه ص۱۳)", ""))

	// ۳) پولِ حقیقی
	eqVal, hasEq := mnum(flow, "eq_flow_b_toman")
	_, hasFixed := mnum(flow, "fixed_flow_b_toman")
	trio, gdOut := flowTrio(flow)
	gd, hasGd := mnum(flow, "gold_flow_b_toman")
	realized := ph.Computable["realized_flow"]
	staleClients := mbool(asof, "client_lag_days")
	var flowState, flowLabel string
	flowVote := 0
	var flowDetail any
	if (!hasEq && !hasFixed) || !realized || staleClients {
		flowState, flowLabel, flowVote = "nodata", "بدون داده", 0
		if staleClients {
			flowDetail = "تفکیکِ حقیقی/حقوقی به روزِ نشست نرسیده (روزِ " +
				faNum(asof["client_d_even"]) + ")"
		} else if !realized {
			if w := ph.WhyNot["realized_flow"]; w != "" {
				flowDetail = w
			}
		}
	} else if trio {
		flowState, flowLabel, flowVote = "ok", "پولِ تازه واردِ سهام", 1
	} else if !mbool(flow, "eq_inflow") && hasEq && eqVal < 0 {
		flowState, flowLabel, flowVote = "bad", "خروجِ پول از سهام", -1
	} else if mbool(flow, "eq_inflow") && mbool(flow, "fixed_outflow") {
		flowState, flowLabel, flowVote = "mid", "ورودِ پولِ ناقص", 0
	} else {
		flowState, flowLabel, flowVote = "mid", "جهتِ پول روشن نیست", 0
	}
	if flowDetail == nil {
		// gold_outflow می‌تواند bool باشد حتی وقتی خودِ عدد نیامده؛ پایتون در
		// این حالت _fa_signed(None) ⇒ «بدون داده» می‌دهد، نه صفر.
		goldText := "بدون داده"
		if gdOut != nil && hasGd {
			goldText = faSigned(gd)
		}
		eqText, fxText := "بدون داده", "بدون داده"
		if hasEq {
			eqText = faSigned(eqVal)
		}
		if v, ok := mnum(flow, "fixed_flow_b_toman"); ok {
			fxText = faSigned(v)
		}
		flowDetail = "خرد " + eqText + " · درآمد ثابت " + fxText +
			" · طلا " + goldText + " (میلیارد تومان)"
	}
	gates = append(gates, gateBody("flow", "جهتِ پولِ حقیقی", "پولِ حقیقی",
		flowState, flowLabel, flowVote, flowDetail,
		"خروجِ طلا و درآمد ثابت ⇄ ورودِ سهام و حق تقدم (جزوه ص۱۴)", ""))

	// ۴) پنجرهٔ ساعت
	window := clockWindow(asof["h_even"])
	gates = append(gates, gateBody("window", "پنجرهٔ زمانیِ جزوه", "ساعت",
		window["state"].(string), window["label"].(string), 0, window["detail"],
		"درآمد ثابت در نیم‌ساعتِ اول · شفافیتِ طلا ۱۲:۱۵–۱۲:۳۰ (جزوه ص۱۴)", ""))

	for _, g := range gates {
		g["why"] = gateWhy(g["key"].(string), g["state"].(string), macro, entry)
	}

	var verdict, vlabel, reason string
	forming := false
	var startHM *int
	streak := 0
	if !ph.VerdictAllowed {
		label := ph.Label
		if label == "" {
			label = "مرحل نامشخص"
		}
		verdict, vlabel = "nodata", "بدونِ حکم — "+label
		whys := []string{}
		for _, k := range ph.NotComputable {
			if w := ph.WhyNot[k]; w != "" {
				whys = append(whys, w)
			}
		}
		reason = "در مرحلِ «" + ph.Label + "» حکمی صادر نمی‌شود"
		if len(whys) > 0 {
			reason += " — " + strings.Join(whys, " · ")
		}
	} else {
		decisive := []map[string]any{}
		negative := []map[string]any{}
		positive := []map[string]any{}
		for _, g := range gates {
			v := g["vote"].(int)
			if v == 0 {
				continue
			}
			decisive = append(decisive, g)
			if v < 0 {
				negative = append(negative, g)
			} else {
				positive = append(positive, g)
			}
		}
		switch {
		case len(decisive) == 0:
			verdict, vlabel = "nodata", "بدونِ حکم"
			reason = "هیچ‌یک از شرط‌هایِ جزوه دادهٔ قاطع ندارد — حکمی صادر نمی‌شود."
		case len(negative) > 0 && len(positive) == 0:
			verdict, vlabel = "avoid", "امروز وارد نشو"
			reason = clause(negative, " · ")
		case len(positive) > 0 && len(negative) == 0:
			hasLiq, hasFlow := false, false
			for _, g := range positive {
				switch g["key"] {
				case "liquidity":
					hasLiq = true
				case "flow":
					hasFlow = true
				}
			}
			if hasLiq && hasFlow {
				verdict, vlabel = "go", "روزِ ورود است"
			} else {
				verdict, vlabel = "watch", "پایِ بازار بمان"
			}
			reason = clause(positive, " · ")
		default:
			verdict, vlabel = "wait", "صبر — نشانه‌ها مخالف‌اند"
			reason = "موافقِ ورود — " + clause(positive, "، ") +
				" · مخالفِ ورود — " + clause(negative, "، ")
		}

		if partial {
			startHM = sessionStartHM(db, ph.SessionDay)
		}
		forming = partial && (hm < 0 || startHM == nil || hm < *startHM+formationMinutes)
		streak = memo.negStreak(ph.SessionDay, asof["h_even"], verdict == "avoid",
			verdict == "go" || verdict == "watch")
		if verdict == "avoid" && (forming || streak < verdictConfirmCount) {
			verdict, vlabel = "nodata", "شواهدِ اولیهٔ منفی — هنوز تأیید نشده"
			reason += " · ارزیابیِ معتبرِ متوالی: " + faNum(streak) + " از " + faNum(verdictConfirmCount)
			if forming {
				reason += " · بازار در دورۀ شکل‌گیریِ داده است"
			}
		}
	}

	trend, nDl := flowTrend(db, ph.SessionDay, asof["h_even"])
	return map[string]any{
		"status": "ok", "verdict": verdict, "label": vlabel, "reason": reason,
		"gates": gates, "basis": "fts_notes_p13_p14",
		"phase": map[string]any{
			"phase": ph.Phase, "label": ph.Label, "phase_source": ph.PhaseSource,
			"official": ph.Official, "session_day": ph.SessionDay,
			"is_live": ph.IsLive, "verdict_allowed": ph.VerdictAllowed,
		},
		"market_state": marketState(ph, asof, gates, verdict, hm, db, ph.SessionDay,
			forming, startHM, streak, trend, nDl, memo),
	}
}

// marketState همان _market_state: مرحل، شدتِ شواهد، محدودیتِ داده و جهت.
// هیچ درصدِ احتمال یا «امتیازِ اطمینان»ی این‌جا ساخته نمی‌شود.
func marketState(ph marketphase.Phase, asof map[string]any, gates []map[string]any,
	verdict string, hm int, db *sql.DB, sessDay *int64, forming bool,
	startHM *int, streak int, trend string, nDl int, memo *verdictMemo) map[string]any {
	p := ph.Phase
	staleClients := mbool(asof, "client_lag_days")
	var dataClock any
	if hm >= 0 {
		if s := faDigits(hhmm(asof["h_even"])); s != "" {
			dataClock = s
		}
	}
	limitations := []string{}
	for _, k := range ph.NotComputable {
		if w := ph.WhyNot[k]; w != "" {
			limitations = append(limitations, w)
		}
	}
	if staleClients {
		limitations = append(limitations, "تفکیکِ حقیقی/حقوقی هنوز به روزِ نشست نرسیده")
	}
	var sinceOpen *int
	if p == marketphase.Continuous && startHM != nil && hm >= *startHM {
		v := hm - *startHM
		sinceOpen = &v
	}
	strongNeg := []map[string]any{}
	strongPos := []map[string]any{}
	for _, g := range gates {
		if v := g["vote"].(int); v < 0 {
			strongNeg = append(strongNeg, g)
		} else if v > 0 {
			strongPos = append(strongPos, g)
		}
	}
	var stage, stageLabel string
	switch {
	case p == marketphase.PreOpen:
		stage, stageLabel = "pre_open", "پیش از آغازِ معاملات — هنوز مبنایِ تصمیم نیست"
	case p == marketphase.Holiday:
		stage, stageLabel = "holiday", "تعطیلِ رسمی — عددِ آخرینِ نشست با تاریخِ خودش"
	case p == marketphase.Closed:
		stage, stageLabel = "after_close", "پایانِ نشست — حکم رویِ جمعِ نهایی"
	case p == marketphase.Unknown:
		stage, stageLabel = "data_limited", "مرحلِ رسمیِ بازار خوانده نشده — ارزیابیِ قابل‌اعتماد نیست"
	case forming:
		stage = "forming"
		stageLabel = "بازار تازه باز شده — دورۀ شکل‌گیریِ داده"
		if startHM != nil {
			end := *startHM + formationMinutes
			stageLabel += " (تا " + hmToClock(&end).(string) + ")"
		} else {
			stageLabel += " (۳۰ دقیقۀ پس از آغازِ واقعی)"
		}
	case verdict == "avoid" || staleClients:
		if verdict == "avoid" {
			stage, stageLabel = "risky", "فشارِ فروش در چند شاهدِ مستقل تأیید شده — ریسکِ بازار بالا رفته"
		} else {
			stage, stageLabel = "data_limited", "دادهٔ کافی یا معتبر نیست"
		}
	case len(strongNeg) > 0 && len(strongPos) == 0:
		stage = "risky_pending"
		stageLabel = "فشارِ فروش در حالِ مشاهده است — برایِ حکمِ قطعی " +
			faNum(verdictConfirmCount) + " ارزیابیِ معتبرِ متوالی لازم است (" +
			faNum(streak) + " از " + faNum(verdictConfirmCount) + ")"
	case len(strongPos) > 0 && len(strongNeg) == 0:
		if verdict == "go" {
			stage, stageLabel = "confirmed", "جریانِ ورودِ پول تأیید شده و مشارکت در حال گسترش است"
		} else {
			stage, stageLabel = "establishing", "نشانه‌هایِ اولیهٔ ورودِ پول دیده می‌شود، هنوز تأیید نشده"
		}
	default:
		stage, stageLabel = "mixed", "نشانه‌ها مخالف‌اند — پایشِ فعال"
	}
	direction := "بی‌جهت"
	if len(strongPos) > 0 && len(strongNeg) == 0 {
		direction = "مثبت"
	} else if len(strongNeg) > 0 && len(strongPos) == 0 {
		direction = "منفی"
	} else if len(strongPos) > 0 && len(strongNeg) > 0 {
		direction = "ترکیبی"
	}
	strength := "کافی نیست"
	switch {
	case p == marketphase.Closed || p == marketphase.Holiday:
		strength = "قابل‌اتکا (جمعِ نهایی)"
	case stage == "forming" || stage == "risky_pending":
		strength = "شواهدِ اولیه"
	case len(strongNeg) > 0 || len(strongPos) > 0:
		strength = "پایدار"
	}
	trendText := ""
	switch trend {
	case "worsening":
		trendText = "در حالِ تضعیف"
	case "improving":
		trendText = "در حالِ تقویت"
	case "mixed":
		trendText = "مختلط"
	}
	var flowTrendNote any
	if trendText != "" && nDl > 0 {
		flowTrendNote = "روندِ جریانِ امروز: " + trendText + " (" + faNum(nDl) + " تغییرِ متوالی)"
	}
	var pace any
	if p == marketphase.Continuous {
		ref, n := sameClockRef(db, sessDay, asof["h_even"], "val_bt")
		if ref != nil && *ref != 0 && n >= 2 {
			pace = "میانهٔ گردشِ کلِ بازار در همین ساعتِ " + faNum(n) +
				" نشستِ پیش: " + faNum(*ref) + " میلیارد تومان"
		}
	}
	var sinceText, sinceOpenAny any
	if sinceOpen != nil {
		sinceOpenAny = *sinceOpen
		sinceText = faNum(*sinceOpen) + " دقیقه از آغازِ واقعی"
	}
	forList := []string{}
	for _, g := range strongPos {
		forList = append(forList, fmt.Sprint(g["short"])+": "+fmt.Sprint(g["label_state"]))
	}
	againstList := []string{}
	for _, g := range strongNeg {
		againstList = append(againstList, fmt.Sprint(g["short"])+": "+fmt.Sprint(g["label_state"]))
	}
	return map[string]any{
		"stage": stage, "stage_label": stageLabel,
		"minutes_since_open": sinceOpenAny, "since_open_text": sinceText,
		"session_start_clock": hmToClock(startHM),
		"confirm_streak":      streak, "confirm_required": verdictConfirmCount,
		"data_clock": dataClock, "data_h_even": asof["h_even"],
		"client_day": asof["client_d_even"], "stale_clients": staleClients,
		"evidence_direction": direction, "evidence_strength": strength,
		"flow_trend": flowTrendNote,
		"for":        forList, "against": againstList,
		"changed_from": memo.previousAndRemember(sessDay, verdict),
		"limitations":  limitations, "pace_note": pace,
	}
}
