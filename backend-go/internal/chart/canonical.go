package chart

// canonical.go — پورتِ زنجیرهٔ کانونیکِ تعدیلِ پایتون (api/chart.py) به Go.
//
// چرا این فایل: `chartdb` پیش از این کندل را دستی می‌ساخت و ستون‌های
// `candle_contract` را نداشت، رویدادها را بی‌تاریخِ مؤثر و بی‌`source` می‌داد،
// `adjustCapability` را با استابِ ثابت پر می‌کرد، و `adjustRejected`/پوششِ دفتر/
// بستهٔ تصحیح را اصلاً محاسبه نمی‌کرد. گلدن‌هایِ B3 همین را نشان می‌دادند.
//
// قواعدِ پورت: عددِ تازه ساخته نمی‌شود؛ هر فیلدی که منبع نداد صفر/تهی می‌ماند و
// همان‌جا که پایتون استثنا می‌دهد، خطا در `coverage.error` می‌نشیند (نمونهٔ فیکسچرِ
// قدیمی که ستونِ `corporate_type_code` ندارد). هیچ کوئریِ نوشتنی در این فایل نیست.

import (
	"context"
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	candlecontract "borsterminal/backend/internal/candle"
)

const (
	ledgerAgreeTol = 0.001
	ledgerWindow   = 10
	corpSize       = 500
	shareGapTol    = 0.005
	dpsDupTol      = 0.01
)

type canonEvent struct {
	Date   string
	Source string
	Ratio  float64
	Extra  map[string]any
}

func (e canonEvent) Map() map[string]any {
	m := map[string]any{"date": e.Date, "ratio": e.Ratio}
	if e.Source != "" {
		m["source"] = e.Source
	}
	for k, v := range e.Extra {
		// کلیدهایِ «_» فقط برایِ تصمیمِ درونی‌اند (کلیدِ دفتر/نسبتِ مبدأ/DPS)؛
		// پایتون پیش از `_engine_events` همان‌ها را حذف می‌کند.
		if strings.HasPrefix(k, "_") {
			continue
		}
		m[k] = v
	}
	return m
}

type chainEvent struct {
	Date  string
	Ratio float64
	Kind  string
}

type canonResult struct {
	Applied   []canonEvent
	Rejected  []map[string]any
	Factors   []float64
	Chain     map[string]any
	Coverage  map[string]any
	Sharpened int
	Ambiguous int
	Source    string
}

func date10(s string) string {
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

func daysBetween(a, b string) (int, bool) {
	da, err1 := time.Parse("2006-01-02", date10(a))
	db, err2 := time.Parse("2006-01-02", date10(b))
	if err1 != nil || err2 != nil {
		return 0, false
	}
	d := int(da.Sub(db).Hours() / 24)
	if d < 0 {
		d = -d
	}
	return d, true
}

func firstDateAtOrAfter(dates []string, d string) string {
	d = date10(d)
	for _, x := range dates {
		if date10(x) >= d {
			return date10(x)
		}
	}
	return d
}

// effectiveEventDates معادلِ _effective_event_dates: هر رویداد به اولین کندلِ
// هم‌روز یا پس از آن می‌رود؛ تاریخِ خام دست‌نخورده نمی‌ماند (شاهد: 2026-09-10 ← 09-12).
func effectiveEventDates(events []canonEvent, times []string) []canonEvent {
	dates := make([]string, 0, len(times))
	seen := map[string]bool{}
	for _, t := range times {
		d := date10(t)
		if d != "" && !seen[d] {
			seen[d] = true
			dates = append(dates, d)
		}
	}
	sort.Strings(dates)
	out := make([]canonEvent, 0, len(events))
	for _, e := range events {
		if e.Date != "" && len(dates) > 0 {
			e.Date = firstDateAtOrAfter(dates, e.Date)
		}
		out = append(out, e)
	}
	return out
}

// ---------- دفترِ رسمی: خواندن و تیزکردن ----------

type ledgerEvent struct {
	Date  string
	Ratio float64
	Kind  string
}

func (s *Service) resolveInsCode(ctx context.Context, symbol string) string {
	pred, params := s.pred(ctx, "l_val18", symbol)
	var ins sql.NullString
	q := fmt.Sprintf("SELECT ins_code FROM instruments WHERE %s "+
		"ORDER BY updated_at DESC LIMIT 1", pred)
	if err := s.market.QueryRowContext(ctx, q, params...).Scan(&ins); err == nil && ins.Valid {
		return ins.String
	}
	return ""
}

func (s *Service) ledgerEventsFor(ctx context.Context, symbol string) []ledgerEvent {
	ins := s.resolveInsCode(ctx, symbol)
	if ins == "" {
		return nil
	}
	out := []ledgerEvent{}
	add := func(q, kind string) {
		rs, err := s.market.QueryContext(ctx, q, ins)
		if err != nil {
			return
		}
		defer rs.Close()
		for rs.Next() {
			var d any
			var ratio sql.NullFloat64
			if err := rs.Scan(&d, &ratio); err != nil {
				continue
			}
			dt := dEvenToDate(d)
			if dt == "" || !ratio.Valid {
				continue
			}
			r := ratio.Float64
			if r <= 0 || math.Abs(r-1.0) <= ledgerAgreeTol {
				continue
			}
			out = append(out, ledgerEvent{Date: dt, Ratio: r, Kind: kind})
		}
	}
	add("SELECT d_even, ratio FROM price_adjust_events WHERE ins_code=?", "priceAdjust")
	add("SELECT d_even, ratio FROM share_change_events WHERE ins_code=?", "shareChange")
	sort.SliceStable(out, func(i, j int) bool { return out[i].Date < out[j].Date })
	return out
}

// sharpenWithLedger معادلِ _sharpen_events_with_ledger: عددِ رویداد از دفترِ
// مبدأ، تاریخ دیده‌شده دست‌نخورده؛ ردیفِ مشترکِ دو رویداد = ambiguous، نه حذف.
func sharpenWithLedger(events []canonEvent, ledger []ledgerEvent) ([]canonEvent, int, int) {
	ev := make([]canonEvent, len(events))
	copy(ev, events)
	if len(ev) == 0 || len(ledger) == 0 {
		return ev, 0, 0
	}
	type claim struct {
		idx  int
		lr   ledgerEvent
		key  string
		rank int
	}
	claims := map[int]ledgerEvent{}
	for i, e := range ev {
		if e.Ratio <= 0 {
			continue
		}
		var best *ledgerEvent
		bestKey := 99
		bestKind := 9
		for _, lr := range ledger {
			dd, ok := daysBetween(lr.Date, e.Date)
			if !ok || dd > ledgerWindow {
				continue
			}
			if math.Abs(lr.Ratio/e.Ratio-1.0) > ledgerAgreeTol {
				continue
			}
			rank := 0
			if lr.Kind != "priceAdjust" {
				rank = 1
			}
			if dd < bestKey || (dd == bestKey && rank < bestKind) {
				lrCopy := lr
				best = &lrCopy
				bestKey, bestKind = dd, rank
			}
		}
		if best != nil {
			claims[i] = *best
		}
	}
	owners := map[string][]int{}
	for i, lr := range claims {
		key := lr.Date + "|" + lr.Kind
		owners[key] = append(owners[key], i)
	}
	sharpened, ambiguous := 0, 0
	out := make([]canonEvent, len(ev))
	copy(out, ev)
	for i := range ev {
		lr, ok := claims[i]
		if ok && len(owners[lr.Date+"|"+lr.Kind]) == 1 {
			out[i].Ratio = math.Round(lr.Ratio*1e8) / 1e8
			out[i].Source = lr.Kind
			if out[i].Extra == nil {
				out[i].Extra = map[string]any{}
			}
			out[i].Extra["_ledger_key"] = lr.Date + "|" + lr.Kind
			sharpened++
		} else {
			if ok {
				ambiguous++
			}
			out[i].Source = "base-price-discontinuity"
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].Date < out[j].Date })
	return out, sharpened, ambiguous
}

func (s *Service) storedCanonicalEvents(ctx context.Context, symbol string) ([]canonEvent, int, int) {
	rows, err := s.market.QueryContext(ctx,
		"SELECT date, ratio, source FROM adjust_events WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		rows, err = s.market.QueryContext(ctx,
			"SELECT date, ratio, NULL FROM adjust_events WHERE symbol=? ORDER BY date", symbol)
	}
	if err != nil {
		return nil, 0, 0
	}
	defer rows.Close()
	out := []canonEvent{}
	for rows.Next() {
		var d, src sql.NullString
		var ratio sql.NullFloat64
		if err := rows.Scan(&d, &ratio, &src); err != nil {
			break
		}
		if !ratio.Valid || ratio.Float64 == 0 {
			continue
		}
		e := canonEvent{Ratio: ratio.Float64}
		if d.Valid {
			e.Date = date10(d.String)
		}
		if src.Valid && src.String != "" {
			e.Source = src.String
		}
		out = append(out, e)
	}
	ledger := s.ledgerEventsFor(ctx, symbol)
	return sharpenWithLedger(out, ledger)
}

// ---------- فیلترِ گسستِ بی‌شاهد ----------

func isOptionName(name string) bool {
	return strings.Contains(name, "اختيار") || strings.Contains(name, "اختیار")
}

func isBondName(name string) bool {
	if name == "" || strings.Contains(name, "صندوق") || strings.Contains(name, "بورس اوراق بهادار") {
		return false
	}
	for _, k := range []string{"مرابحه", "اسناد", "مشاركت", "مشارکت", "اجاره",
		"صكوک", "صکوک", "سلف موازي", "سلف موازی", "اخزا", "اوراق"} {
		if strings.Contains(name, k) {
			return true
		}
	}
	return strings.HasPrefix(name, "گام") || strings.HasPrefix(name, "گواهي اعتبار") ||
		strings.HasPrefix(name, "گواهی اعتبار")
}

func isRightName(name string, paperType any) bool {
	return paperTypeInt(paperType) == 4 || strings.HasPrefix(name, "ح ") ||
		strings.HasPrefix(name, "ح.") || strings.Contains(name, "حق تقدم")
}

func isFutureName(name string) bool {
	if name == "" {
		return false
	}
	if strings.HasPrefix(name, "آتي ") || strings.HasPrefix(name, "آتی ") ||
		strings.HasPrefix(name, "بار پايه") || strings.HasPrefix(name, "بار پایه") {
		return true
	}
	return strings.Contains(name, "ماهه") &&
		(strings.Contains(name, "فروش") || strings.Contains(name, "خرید") ||
			strings.Contains(name, "تحویل"))
}

func paperTypeInt(v any) int {
	switch x := v.(type) {
	case int64:
		return int(x)
	case int:
		return x
	case float64:
		return int(x)
	}
	return -1
}

func (s *Service) instrumentInfo(ctx context.Context, symbol string) (name string, paperType any, sector string, ok bool) {
	pred, params := s.pred(ctx, "l_val18", symbol)
	q := fmt.Sprintf("SELECT l_val30, paper_type, sector_name FROM instruments WHERE %s "+
		"ORDER BY updated_at DESC LIMIT 1", pred)
	var n, sec sql.NullString
	var pt sql.NullInt64
	if err := s.market.QueryRowContext(ctx, q, params...).Scan(&n, &pt, &sec); err != nil {
		return "", nil, "", false
	}
	name = strings.ReplaceAll(n.String, "\u200c", " ")
	if pt.Valid {
		paperType = pt.Int64
	}
	return name, paperType, sec.String, true
}

func (s *Service) instrumentKind(ctx context.Context, symbol string) string {
	name, paperType, sector, ok := s.instrumentInfo(ctx, symbol)
	if !ok {
		return "unknown"
	}
	switch {
	case isOptionName(name):
		return "option"
	case isBondName(name):
		return "bond"
	case isRightName(name, paperType):
		return "right"
	case isFutureName(name):
		return "future"
	case paperTypeInt(paperType) == 8 || strings.Contains(sector, "صندوق") ||
		strings.Contains(name, "صندوق"):
		return "fund"
	}
	return "stock"
}

func (s *Service) filterUnproven(ctx context.Context, symbol string, events []canonEvent, times []string) ([]canonEvent, []map[string]any) {
	if len(events) == 0 {
		return events, []map[string]any{}
	}
	name, paperType, _, _ := s.instrumentInfo(ctx, symbol)
	ins := s.resolveInsCode(ctx, symbol)
	official := map[string]bool{}
	anomalies := map[string]bool{}
	if ins != "" {
		rs, err := s.market.QueryContext(ctx,
			"SELECT d_even FROM price_adjust_events WHERE ins_code=? "+
				"UNION SELECT d_even FROM share_change_events WHERE ins_code=?", ins, ins)
		if err == nil {
			for rs.Next() {
				var d any
				if rs.Scan(&d) == nil {
					if iso := dEvenToDate(d); iso != "" {
						official[iso] = true
					}
				}
			}
			rs.Close()
		}
	}
	if rs, err := s.market.QueryContext(ctx, "SELECT d_even, cause FROM session_anomalies"); err == nil {
		for rs.Next() {
			var d any
			var cause sql.NullString
			if rs.Scan(&d, &cause) == nil && cause.String == "MARKET_WIDE_SESSION_DIFFERENCE" {
				if iso := dEvenToDate(d); iso != "" {
					anomalies[iso] = true
				}
			}
		}
		rs.Close()
	}
	isOpt, isRight, isBond := isOptionName(name), isRightName(name, paperType), isBondName(name)
	isFund := paperTypeInt(paperType) == 8 || strings.Contains(name, "صندوق")
	dates := make([]string, 0, len(times))
	seen := map[string]bool{}
	for _, t := range times {
		d := date10(t)
		if d != "" && !seen[d] {
			seen[d] = true
			dates = append(dates, d)
		}
	}
	sort.Strings(dates)
	eff := func(d string) string {
		if len(dates) == 0 {
			return d
		}
		return firstDateAtOrAfter(dates, d)
	}
	dateCounts := map[string]int{}
	bigDates := []string{}
	for _, e := range events {
		src := e.Source
		if src == "" {
			src = "base-price-discontinuity"
		}
		if src != "base-price-discontinuity" {
			continue
		}
		dateCounts[eff(e.Date)]++
		if e.Ratio > 0 && e.Ratio < 0.985 {
			bigDates = append(bigDates, date10(e.Date))
		}
	}
	kept := []canonEvent{}
	rejected := []map[string]any{}
	for _, e := range events {
		src := e.Source
		if src == "" {
			src = "base-price-discontinuity"
		}
		status := ""
		if src == "base-price-discontinuity" {
			switch {
			case anomalies[date10(e.Date)]:
				status = "session-wide-base-gap"
			case isOpt:
				status = "option-base-gap"
			case isBond:
				status = "bond-base-gap"
			case isRight:
				status = "right-base-gap"
			case e.Ratio > 1.0:
				status = "unproven-positive-base-gap"
			case !isFund && e.Ratio > 0.985 && e.Ratio < 1.0 && dateCounts[eff(e.Date)] == 1 &&
				!nearAny(e.Date, bigDates, 3) && !nearAnyDateSet(e.Date, official, 30):
				status = "unproven-small-base-gap"
			}
		}
		if status != "" {
			rejected = append(rejected, map[string]any{
				"date": e.Date, "ratio": e.Ratio, "factor_status": status})
		} else {
			kept = append(kept, e)
		}
	}
	return kept, rejected
}

func nearAny(d string, list []string, maxDays int) bool {
	for _, x := range list {
		if dd, ok := daysBetween(d, x); ok && dd <= maxDays {
			return true
		}
	}
	return false
}

func nearAnyDateSet(d string, set map[string]bool, maxDays int) bool {
	for x := range set {
		if dd, ok := daysBetween(d, x); ok && dd <= maxDays {
			return true
		}
	}
	return false
}

// ---------- بستهٔ تصحیح ----------

// correctionsCapability شکلِ AC.capability(symbol) است؛ Python این را فقط با
// نامِ نمایشی می‌خواند (نه ins_code)، پس کلیدِ آن هم همان است.
func (s *Service) correctionsCapability(ctx context.Context, symbol string) map[string]any {
	pack := LoadPack(s.dataDir)
	return pack.Capability("", symbol)
}

// officialPriceAdjustEvents معادلِ _official_price_adjust_events. جدولِ قدیمیِ
// بی‌ستون (فیکسچر) مانندِ استثنایِ پایتون ⇒ []، نه خطا.
func (s *Service) officialPriceAdjustEvents(ctx context.Context, symbol string, times []string, closings map[string]float64) []canonEvent {
	ins := s.resolveInsCode(ctx, symbol)
	if ins == "" || !tableHasColumn(ctx, s.market, "price_adjust_events", "ratio") ||
		!tableHasColumn(ctx, s.market, "price_adjust_events", "corporate_type_code") {
		return nil
	}
	share := s.shareChangeEvents(ctx, symbol)
	candleDates := make([]string, 0, len(times))
	for _, t := range times {
		if d := date10(t); d != "" {
			candleDates = append(candleDates, d)
		}
	}
	sort.Strings(candleDates)
	type row struct {
		dEven  any
		ratio  float64
		source string
		pcl    float64
		pna    float64
		hasPcl bool
		hasPna bool
		ctype  sql.NullFloat64
	}
	rs, err := s.market.QueryContext(ctx,
		"SELECT d_even, ratio, source, p_closing, p_closing_not_adjusted, corporate_type_code "+
			"FROM price_adjust_events WHERE ins_code=? ORDER BY d_even", ins)
	if err != nil {
		return nil
	}
	rows := []row{}
	for rs.Next() {
		var r row
		var src sql.NullString
		var pcl, pna, ratio sql.NullFloat64
		if err := rs.Scan(&r.dEven, &ratio, &src, &pcl, &pna, &r.ctype); err != nil {
			continue
		}
		if !ratio.Valid {
			continue
		}
		r.ratio = ratio.Float64
		r.source = src.String
		r.pcl, r.hasPcl = pcl.Float64, pcl.Valid
		r.pna, r.hasPna = pna.Float64, pna.Valid
		rows = append(rows, r)
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return nil
	}
	out := []canonEvent{}
	for _, r := range rows {
		dt := dEvenToDate(r.dEven)
		if dt == "" || !(r.ratio >= 1e-4 && r.ratio <= 1e4) || math.Abs(r.ratio-1.0) < 1e-7 {
			continue
		}
		orig := dt
		if len(candleDates) > 0 {
			nxt := ""
			for _, t := range candleDates {
				if t >= dt {
					nxt = t
					break
				}
			}
			if nxt == "" {
				continue
			}
			dt = nxt
		}
		var dps float64
		hasDPS := false
		if r.hasPcl && r.hasPna && r.pna > r.pcl && r.pcl > 0 {
			dps = r.pna - r.pcl
			hasDPS = true
		}
		cl, hasCl := closings[dt]
		if !hasCl {
			cl = 0
		}
		ratio, isDPS, _ := classifyPaEvent(r.ratio, dps, hasDPS, cl, orig, share)
		src := r.source
		if src == "" {
			src = "priceAdjust"
		}
		rec := canonEvent{Date: dt, Ratio: ratio, Source: src,
			Extra: map[string]any{
				"_source_ratio": r.ratio,
				"_ledger_key":   orig + "|priceAdjust",
			}}
		if isDPS {
			rec.Extra["_dps"] = true
			rec.Extra["dividend_per_share"] = dps
			if o := combinedDPSOfficialRatio(ratio, r.ratio, dt, share); o != nil {
				rec.Ratio = *o
			}
		}
		out = append(out, rec)
	}
	return out
}

func containsString(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

// classifyPaEvent معادلِ _classify_pa_event.
func classifyPaEvent(paRatio, dps float64, hasDPS bool, closing float64, orig string, shareChanges [][2]float64) (float64, bool, string) {
	bestDD := 0
	var bestSR float64
	hasBest := false
	for _, sc := range shareChanges {
		dd, ok := daysBetween(dayNumberToDate(sc[0]), orig)
		if !ok {
			continue
		}
		if dd <= 10 && (!hasBest || dd < bestDD) {
			bestDD, bestSR, hasBest = dd, sc[1], true
		}
	}
	var dpsRatio float64
	hasDPSRatio := false
	if hasDPS && closing > 0 {
		dpsRatio = roundTo(closing/(closing+dps), 10)
		hasDPSRatio = true
	}
	if hasBest {
		sr := bestSR
		capErr := math.Abs(paRatio/sr - 1.0)
		combErr := 9.0
		if hasDPSRatio {
			combErr = math.Abs(paRatio/(sr*dpsRatio) - 1.0)
		}
		if combErr < capErr && combErr <= 0.02 {
			return paRatio, false, "combined"
		}
		if capErr <= 0.02 {
			return paRatio, false, "capital"
		}
	}
	if hasDPS {
		if hasDPSRatio {
			return dpsRatio, true, "dps"
		}
		return paRatio, true, "dps-unverified"
	}
	return paRatio, false, "unverified"
}

// combinedDPSOfficialRatio معادلِ _combined_dps_official_ratio.
func combinedDPSOfficialRatio(formulaRatio, officialRatio float64, date string, shareChanges [][2]float64) *float64 {
	if formulaRatio <= 0 || officialRatio <= 0 {
		return nil
	}
	if math.Abs(officialRatio/formulaRatio-1.0) < 0.015 {
		return nil
	}
	for _, sc := range shareChanges {
		sd := fmt.Sprintf("%.0f", sc[0])
		dd, ok := daysBetween(sd, date)
		if ok && dd <= 10 && sc[1] > 0 && math.Abs(officialRatio/sc[1]-1.0) <= 0.15 {
			v := officialRatio
			return &v
		}
	}
	return nil
}

// shareChangeEvents معادلِ _share_change_events + _filter_share_changes.
func (s *Service) shareChangeEvents(ctx context.Context, symbol string) [][2]float64 {
	ins := s.resolveInsCode(ctx, symbol)
	if ins == "" || !tableHasColumn(ctx, s.market, "share_change_events", "ratio") {
		return nil
	}
	rs, err := s.market.QueryContext(ctx,
		"SELECT d_even, ratio FROM share_change_events WHERE ins_code=? ORDER BY d_even", ins)
	if err != nil {
		return nil
	}
	defer rs.Close()
	rows := [][2]float64{}
	for rs.Next() {
		var d any
		var ratio sql.NullFloat64
		if rs.Scan(&d, &ratio) != nil || !ratio.Valid {
			continue
		}
		dt := dEvenToDate(d)
		if dt == "" || math.Abs(ratio.Float64-1.0) <= 1e-9 {
			continue
		}
		days, err := time.Parse("2006-01-02", dt)
		if err != nil {
			continue
		}
		rows = append(rows, [2]float64{float64(days.Unix() / 86400), ratio.Float64})
	}
	return filterShareChanges(rows)
}

// filterShareChanges معادلِ _filter_share_changes (تاریخ‌ها به روزِ مطلق).
func filterShareChanges(rows [][2]float64) [][2]float64 {
	sort.SliceStable(rows, func(i, j int) bool { return rows[i][0] < rows[j][0] })
	all := make([][2]float64, 0, len(rows))
	for _, r := range rows {
		if r[1] > 0 {
			all = append(all, r)
		}
	}
	hasInverse := func(d, r float64) bool {
		for _, x := range all {
			if math.Abs(x[1]*r-1.0) <= 1e-4 {
				dd := math.Abs(x[0] - d)
				if dd <= 180 {
					return true
				}
			}
		}
		return false
	}
	clean := [][2]float64{}
	for _, r := range all {
		if r[1] > 1 {
			if !hasInverse(r[0], r[1]) {
				clean = append(clean, r)
			}
			continue
		}
		dup := false
		for _, k := range clean {
			if k[1] >= 1 {
				continue
			}
			if math.Abs(k[1]/r[1]-1.0) <= 1e-6 && math.Abs(r[0]-k[0]) <= 180 && hasInverse(r[0], r[1]) {
				dup = true
				break
			}
		}
		if !dup {
			clean = append(clean, r)
		}
	}
	sort.SliceStable(clean, func(i, j int) bool { return clean[i][0] < clean[j][0] })
	return clean
}

func shareChangesAsPairs(ctx context.Context, s *Service, symbol string) [][2]float64 {
	return s.shareChangeEvents(ctx, symbol)
}

// applyLongGapShareChanges معادلِ _apply_long_gap_share_changes.
func applyLongGapShareChanges(events []canonEvent, shareChanges [][2]float64, times []string, closings map[string]float64) []canonEvent {
	if len(closings) == 0 || len(shareChanges) == 0 || len(times) == 0 {
		return events
	}
	out := append([]canonEvent(nil), events...)
	ts := uniqueSortedDates(times)
	owned := map[string]bool{}
	for _, e := range out {
		if e.Extra != nil {
			if k, ok := e.Extra["_ledger_share_date"].(string); ok && k != "" {
				owned[k] = true
			}
		}
	}
	for _, sc := range shareChanges {
		sr := sc[1]
		if !(sr > 0 && sr < 1) {
			continue
		}
		sdIso := dayNumberToDate(sc[0])
		if sdIso == "" || owned[sdIso] {
			continue
		}
		idx := -1
		for i, t := range ts {
			if t >= sdIso {
				idx = i
				break
			}
		}
		if idx <= 0 {
			continue
		}
		first, prev := ts[idx], ts[idx-1]
		gap, ok := daysBetween(prev, first)
		if !ok || gap <= 10 {
			continue
		}
		step := 1.0
		covered := false
		for _, e := range out {
			if date10(e.Date) != first {
				continue
			}
			er := e.Ratio
			if er > 0 {
				step /= er
			}
			if k, ok := e.Extra["_ledger_share_date"].(string); ok && k == sdIso {
				covered = true
			}
			if er > 0 && math.Abs(er/sr-1.0) <= 0.005 {
				covered = true
			}
		}
		if covered || (step != 0 && (1.0/step) <= sr*(1.0+0.005)) {
			continue
		}
		c0, ok0 := closings[prev]
		c1, ok1 := closings[first]
		if !ok0 || !ok1 || c0 == 0 || c1 == 0 {
			continue
		}
		if c1/c0 > sr*(1.0+0.005) {
			continue
		}
		out = append(out, canonEvent{Date: first, Ratio: roundTo(sr, 10),
			Source: "shareChange", Extra: map[string]any{"_ledger_share_date": sdIso, "long_gap": true}})
	}
	return out
}

func uniqueSortedDates(times []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, t := range times {
		d := date10(t)
		if d != "" && !seen[d] {
			seen[d] = true
			out = append(out, d)
		}
	}
	sort.Strings(out)
	return out
}

func dayNumberToDate(n float64) string {
	return time.Unix(int64(n*86400), 0).UTC().Format("2006-01-02")
}

// dropShareLegOfObservedGap معادلِ _drop_share_leg_of_observed_gap.
func dropShareLegOfObservedGap(events []canonEvent, shareChanges [][2]float64) ([]canonEvent, []map[string]any) {
	gaps := map[string][]float64{}
	for _, e := range events {
		if e.Source != "base-price-discontinuity" || e.Ratio <= 0 {
			continue
		}
		d := date10(e.Date)
		if d != "" {
			gaps[d] = append(gaps[d], e.Ratio)
		}
	}
	kept := []canonEvent{}
	dropped := []map[string]any{}
	for _, e := range events {
		src := e.Source
		isDPS := e.Extra != nil && flagged(e.Extra["_dps"], true)
		if (src == "shareChange" || src == "priceAdjust" || src == "tsetmc_price_adjust_by_flow") && !isDPS {
			d := date10(e.Date)
			hit := false
			if e.Ratio > 0 {
				for _, g := range gaps[d] {
					if !(math.Abs(e.Ratio/g-1.0) > 0.02 && math.Abs(e.Ratio/g-1.0) <= 0.06) {
						continue
					}
					for _, sc := range shareChanges {
						dd, ok := daysBetween(dayNumberToDate(sc[0]), d)
						if ok && dd <= 5 && sc[1] > 0 && math.Abs(sc[1]/e.Ratio-1.0) <= 0.001 {
							hit = true
							break
						}
					}
					if hit {
						break
					}
				}
			}
			if hit {
				dropped = append(dropped, map[string]any{"date": e.Date, "ratio": e.Ratio,
					"factor_status": "duplicate:share-leg-of-observed-gap"})
				continue
			}
		}
		kept = append(kept, e)
	}
	return kept, dropped
}

// mergeOfficialFundEvents معادلِ _merge_official_fund_events (پورتِ ساده).
func mergeOfficialFundEvents(events []canonEvent, official []canonEvent) []canonEvent {
	if len(official) == 0 {
		return events
	}
	byDate := map[string]canonEvent{}
	for _, o := range official {
		byDate[date10(o.Date)] = o
	}
	out := []canonEvent{}
	for _, e := range events {
		if o, ok := byDate[date10(e.Date)]; ok {
			out = append(out, o)
			delete(byDate, date10(e.Date))
			continue
		}
		out = append(out, e)
	}
	for _, o := range byDate {
		out = append(out, o)
	}
	sort.SliceStable(out, func(i, j int) bool { return date10(out[i].Date) < date10(out[j].Date) })
	return out
}

// canonicalFactors معادلِ مسیرِ چارت برایِ مسیرهایِ مشتق (MA/الگوها): همان
// مجموعهٔ رویدادِ انبار، همان فیلترِ اثبات‌نشده، همان داوریِ منبع و همان
// canonicalAdjustment. پیش‌تر MA/الگوها زنجیرهٔ ساده‌تری می‌زدند و رویدادِ رسمیِ
// تازه در آن‌ها جا می‌افتاد (شستا ۲۰۲۶-۱۰-۲۵: ۰٫۷۴۷۱ در برابر ۰٫۷۰۳۶ِ چارت).
func (s *Service) canonicalFactors(ctx context.Context, symbol string, times []string, closings map[string]float64) []float64 {
	evs, _, _ := s.storedCanonicalEvents(ctx, symbol)
	evs, _ = s.filterUnproven(ctx, symbol, evs, times)
	src := s.priceHistorySource(ctx, symbol, evs)
	if !adjKnownSources[src] {
		evs = nil
	}
	_, _, factors, _, _ := s.canonicalAdjustment(ctx, symbol, times, evs, closings)
	return factors
}

// canonicalAdjustment معادلِ _canonical_adjustment: یک قاعده، یک اعتبار.
func (s *Service) canonicalAdjustment(ctx context.Context, symbol string, times []string, events []canonEvent, closings map[string]float64) ([]canonEvent, []map[string]any, []float64, map[string]any, map[string]any) {
	t10 := make([]string, len(times))
	for i, t := range times {
		t10[i] = date10(t)
	}
	ins := s.resolveInsCode(ctx, symbol)
	events = effectiveEventDates(events, t10)
	officialPA := s.officialPriceAdjustEvents(ctx, symbol, t10, closings)
	share := s.shareChangeEvents(ctx, symbol)
	rejected := []map[string]any{}
	if officialPA != nil {
		events, rejected = mergeOfficialPriceAdjust(events, officialPA, share)
	}
	// مسیرِ محلیِ پایتون `gap_closings` نمی‌دهد (فقط CDN آن را پر می‌کند)؛
	// پس این گام درِ چارت هیچ رویدادِ share تازه نمی‌سازد.
	events = applyLongGapShareChanges(events, share, t10, nil)
	events, legRejected := dropShareLegOfObservedGap(events, share)
	pack := LoadPack(s.dataDir)
	events, suppressed, corrMeta := pack.ApplyFactorEvents(ins, symbol, events)
	corrRejected := make([]map[string]any, 0, len(suppressed))
	corrVersion := ""
	if corrMeta != nil {
		corrVersion = stringValue(corrMeta["version"])
	}
	for _, e := range suppressed {
		rej := map[string]any{
			"date": date10(e.Date), "ratio": e.Ratio,
			"factor_status":      "suppressed-by-rahavard-reference-correction",
			"correction_version": nilIfEmpty(corrVersion),
		}
		if e.Extra != nil {
			if dedupe, ok := e.Extra["dedupe"]; ok {
				rej["dedupe"] = dedupe
			}
		}
		corrRejected = append(corrRejected, rej)
	}
	applied, engineRejected, chainEvents, _ := engineEvents(events)
	// ترتیبِ پایتون: ردیف‌هایِ ردشدهٔ موتور نخست، سپس تکراری‌هایِ ادغام،
	// سپس پایِ share، سپس حذف‌شده‌هایِ بستهٔ تصحیح.
	allRejected := make([]map[string]any, 0,
		len(engineRejected)+len(rejected)+len(legRejected)+len(corrRejected))
	allRejected = append(allRejected, engineRejected...)
	allRejected = append(allRejected, rejected...)
	allRejected = append(allRejected, legRejected...)
	allRejected = append(allRejected, corrRejected...)
	factors, chain := chainFactors(t10, chainEvents)
	coverage := s.ledgerCoverage(ctx, symbol, t10, applied)
	return applied, allRejected, factors, chain, coverage
}

// mergeOfficialPriceAdjust پورتِ _merge_official_price_adjust برایِ مسیرِ
// محلی: ردیفِ رسمی وقتی افزوده می‌شود که کشفِ CSV همان اقدام را ندیده باشد؛
// ردیفِ تکراری با هویتِ دفتری یا هم‌اقدامیِ ≤۵روز رد می‌شود و نسبتِ DPSِ
// محاسبه‌شده بر نسبتِ مبدأ اولویت دارد.
func mergeOfficialPriceAdjust(events, official []canonEvent, shareChanges [][2]float64) ([]canonEvent, []map[string]any) {
	kept := append([]canonEvent(nil), events...)
	rejected := []map[string]any{}
	claimed := map[string]bool{}
	for _, e := range kept {
		if e.Extra != nil {
			if k, ok := e.Extra["_ledger_key"].(string); ok && k != "" {
				claimed[k] = true
			}
		}
	}
	sourceRatio := func(e canonEvent) float64 {
		if e.Extra == nil {
			return 0
		}
		if v, ok := e.Extra["_source_ratio"].(float64); ok && v > 0 {
			return v
		}
		return 0
	}
	shareDate := func(sc [2]float64) string { return dayNumberToDate(sc[0]) }
	nearestShare := func(ed string, maxDays int) (float64, bool) {
		bestDD := 1 << 30
		bestR := 0.0
		found := false
		for _, sc := range shareChanges {
			dd, ok := daysBetween(shareDate(sc), ed)
			if !ok || dd > maxDays {
				continue
			}
			if dd < bestDD {
				bestDD, bestR, found = dd, sc[1], true
			}
		}
		return bestR, found
	}
	ledgerOrig := func(e canonEvent) string {
		if e.Extra == nil {
			return ""
		}
		k, _ := e.Extra["_ledger_key"].(string)
		if i := strings.IndexByte(k, '|'); i >= 0 {
			return k[:i]
		}
		return k
	}
	// ۱) گسستِ پایهٔ هم‌تاریخ با ردیفِ DPS، پایِ قیمتیِ همان اقدام است؛ DPS
	// جداگانه نباید دوباره اعمال شود (قاعدهٔ observed_gap_skip).
	observedGapSkip := map[int]bool{}
	for i, o := range official {
		if !(isDPS(o) && o.Ratio != 0) {
			continue
		}
		od := date10(o.Date)
		for _, e := range kept {
			if e.Source != "base-price-discontinuity" || date10(e.Date) != od {
				continue
			}
			gr := e.Ratio
			if gr <= 0 {
				continue
			}
			sr, ok := nearestShare(od, 5)
			if !ok || sr <= 0 {
				continue
			}
			if math.Abs(sr/gr-1.0) <= 0.02 {
				continue // گسستِ فقط‌سهام: DPS اقدامِ مستقل است
			}
			shareApplied := false
			for _, k := range kept {
				if k.Ratio <= 0 {
					continue
				}
				if (k.Source == "shareChange" || k.Source == "base-price-discontinuity") &&
					math.Abs(k.Ratio/sr-1.0) <= 0.05 {
					shareApplied = true
					break
				}
			}
			if shareApplied {
				observedGapSkip[i] = true
				break
			}
			if src := sourceRatio(o); src > 0 && math.Abs(gr/src-1.0) <= ledgerAgreeTol {
				continue // گسست نسبتِ مبدأ است؛ DPS بازمحاسبه‌شده می‌ماند
			}
			observedGapSkip[i] = true
			break
		}
	}
	type dpsRatio struct {
		idx   int
		date  string
		ratio float64
		src   float64
	}
	dpsRatios := []dpsRatio{}
	for i, o := range official {
		if isDPS(o) && o.Ratio != 0 {
			dpsRatios = append(dpsRatios, dpsRatio{i, date10(o.Date), o.Ratio, sourceRatio(o)})
		}
	}
	filterDPS := func(skip map[int]bool) {
		filtered := make([]dpsRatio, 0, len(dpsRatios))
		for _, d := range dpsRatios {
			if !skip[d.idx] {
				filtered = append(filtered, d)
			}
		}
		dpsRatios = filtered
	}
	if len(observedGapSkip) > 0 {
		filterDPS(observedGapSkip)
	}
	// ۲) اقدامِ مرکب (سهام × پایِ قیمتی) که خود به‌صورتِ یک گسستِ پایه دیده
	// شده است؛ ردیف‌هایِ رسمیِ همان گسست دوباره اعمال نمی‌شوند.
	type claimInfo struct {
		mapped string
		sr     float64
		sdd    string
		inside bool
	}
	combinedBaseClaims := map[int][]int{}
	claimInfos := map[int]claimInfo{}
	for idx, o := range official {
		if observedGapSkip[idx] {
			continue
		}
		sr := sourceRatio(o)
		if sr <= 0 {
			continue
		}
		mapped := date10(o.Date)
		orig := ledgerOrig(o)
		for _, sc := range shareChanges {
			sdd := shareDate(sc)
			ccv := sc[1]
			if sdd == "" {
				continue
			}
			inside := orig != "" && orig < sdd && sdd <= mapped
			dd, ok := daysBetween(sdd, mapped)
			if !inside && (!ok || dd > 7) {
				continue
			}
			target := ccv * sr
			if target <= 0 {
				continue
			}
			hits := []int{}
			for j, e := range kept {
				if e.Source != "base-price-discontinuity" && e.Source != "priceAdjust" {
					continue
				}
				if e.Ratio > 0 && math.Abs(e.Ratio/target-1.0) <= shareGapTol {
					hits = append(hits, j)
				}
			}
			if len(hits) == 1 {
				combinedBaseClaims[hits[0]] = append(combinedBaseClaims[hits[0]], idx)
				claimInfos[idx] = claimInfo{mapped: mapped, sr: sr, sdd: sdd, inside: inside}
			}
		}
	}
	combinedBaseSkip := map[int]bool{}
	for _, idxs := range combinedBaseClaims {
		if len(idxs) == 1 {
			combinedBaseSkip[idxs[0]] = true
			continue
		}
		sameDay, insideAll := true, true
		vals, origs := make([]float64, 0, len(idxs)), make([]string, 0, len(idxs))
		first := claimInfos[idxs[0]].mapped
		for _, i := range idxs {
			ci := claimInfos[i]
			if ci.mapped != first {
				sameDay = false
			}
			if !ci.inside {
				insideAll = false
			}
			vals = append(vals, ci.sr)
			origs = append(origs, ledgerOrig(official[i]))
		}
		distinctOrig, seenOrig := true, map[string]bool{}
		for _, s := range origs {
			if s == "" || seenOrig[s] {
				distinctOrig = false
				break
			}
			seenOrig[s] = true
		}
		minV, maxV := vals[0], vals[0]
		for _, v := range vals {
			if v < minV {
				minV = v
			}
			if v > maxV {
				maxV = v
			}
		}
		if sameDay && insideAll && distinctOrig && minV > 0 && maxV/minV-1.0 <= 0.01 {
			for _, i := range idxs {
				combinedBaseSkip[i] = true
			}
		}
	}
	if len(combinedBaseSkip) > 0 {
		filterDPS(combinedBaseSkip)
	}
	// ۳) گسستِ پایه در پنجرهٔ DPS: همان اقدام با تقریبِ بدتر، یا سهام‌تنها
	// (هر دو می‌مانند) یا ترکیبِ DPS×سهام (گسست می‌ماند، DPS جدا حذف).
	combinedSkip := map[int]bool{}
	dropBase := func(e canonEvent) bool {
		r := e.Ratio
		if r == 0 {
			return false
		}
		ed := date10(e.Date)
		near := []dpsRatio{}
		for _, d := range dpsRatios {
			if dd, ok := daysBetween(d.date, ed); ok && dd <= 5 {
				near = append(near, d)
			}
		}
		if len(near) == 0 {
			return false
		}
		for _, d := range near {
			if math.Abs(r/d.ratio-1.0) <= dpsDupTol {
				return true
			}
		}
		for _, d := range near {
			if d.src > 0 && math.Abs(r/d.src-1.0) <= ledgerAgreeTol {
				return true
			}
		}
		if cc, ok := nearestShare(ed, 7); ok && cc != 0 {
			best := -1
			bestComb := 0.0
			for _, d := range near {
				sep := math.Abs(r/cc - 1.0)
				comb := math.Abs(r/(cc*d.ratio) - 1.0)
				if comb < sep && comb <= 0.02 && (best < 0 || comb < bestComb) {
					best, bestComb = d.idx, comb
				}
			}
			if best >= 0 {
				combinedSkip[best] = true
				return false
			}
			return false // سهام‌تنها: هر دو می‌مانند
		}
		return true
	}
	filteredKept := make([]canonEvent, 0, len(kept))
	for _, e := range kept {
		if e.Source == "base-price-discontinuity" && dropBase(e) {
			continue
		}
		filteredKept = append(filteredKept, e)
	}
	kept = filteredKept
	for idx, o := range official {
		od := date10(o.Date)
		key, _ := o.Extra["_ledger_key"].(string)
		if observedGapSkip[idx] {
			rejected = append(rejected, map[string]any{
				"date": o.Date, "ratio": o.Ratio,
				"factor_status": "included-in-observed-base-gap"})
			continue
		}
		if combinedBaseSkip[idx] {
			rejected = append(rejected, map[string]any{
				"date": o.Date, "ratio": o.Ratio,
				"factor_status": "included-in-combined-base-gap"})
			continue
		}
		if combinedSkip[idx] {
			rejected = append(rejected, map[string]any{
				"date": o.Date, "ratio": o.Ratio,
				"factor_status": "included-in-base-gap"})
			continue
		}
		if key != "" && claimed[key] {
			// نسبتِ DPS فرمولِ اثبات‌شده (close/(close+DPS)) بر نسبتِ
			// تیزکردهٔ مبدأ اولویت دارد؛ خودِ ردیف تکراری است.
			if isDPS(o) {
				for i := range kept {
					ek, _ := kept[i].Extra["_ledger_key"].(string)
					if ek != key {
						continue
					}
					if kept[i].Source != "priceAdjust" &&
						kept[i].Source != "tsetmc_price_adjust_by_flow" {
						continue
					}
					if kept[i].Ratio != 0 && o.Ratio != 0 &&
						math.Abs(kept[i].Ratio/o.Ratio-1.0) > 1e-6 {
						kept[i].Ratio = o.Ratio
						kept[i].Extra["_dps"] = true
						kept[i].Extra["dividend_per_share"] = o.Extra["dividend_per_share"]
						kept[i].Extra["_source_ratio"] = o.Extra["_source_ratio"]
						kept[i].Source = o.Source
					}
					break
				}
			}
			rejected = append(rejected, map[string]any{
				"date": o.Date, "ratio": o.Ratio, "factor_status": "duplicate-ledger-row"})
			continue
		}
		dupIdx := -1
		for i, e := range kept {
			ed := date10(e.Date)
			if ed == "" {
				continue
			}
			dd, ok := daysBetween(od, ed)
			if !ok || dd > 5 {
				continue
			}
			if e.Ratio == 0 || o.Ratio == 0 {
				continue
			}
			sameAmount := true
			if edps, eok := e.Extra["dividend_per_share"].(float64); eok {
				if odps, ook := o.Extra["dividend_per_share"].(float64); ook && odps > 0 {
					sameAmount = math.Abs(edps/odps-1.0) <= 0.02
				}
			}
			ratioMatch := math.Abs(e.Ratio/o.Ratio-1.0) <= 0.02
			sourceMatch := false
			if isDPS(o) {
				if sr := sourceRatio(o); sr > 0 && math.Abs(e.Ratio/sr-1.0) <= ledgerAgreeTol {
					sourceMatch = true
					for _, sc := range shareChanges {
						ds, ok := daysBetween(shareDate(sc), ed)
						if ok && ds <= 5 && sc[1] > 0 &&
							math.Abs(sc[1]/e.Ratio-1.0) <= 0.02 {
							sourceMatch = false
							break
						}
					}
				}
			}
			if sameAmount && (ratioMatch || sourceMatch) {
				dupIdx = i
				break
			}
		}
		if dupIdx >= 0 {
			e := kept[dupIdx]
			if e.Source == "base-price-discontinuity" || e.Source == "priceAdjust" ||
				e.Source == "tsetmc_price_adjust_by_flow" {
				kept = append(kept[:dupIdx], kept[dupIdx+1:]...)
				kept = append(kept, o)
			} else {
				rejected = append(rejected, map[string]any{
					"date": o.Date, "ratio": o.Ratio,
					"factor_status": "duplicate-same-action"})
				continue
			}
		} else {
			kept = append(kept, o)
		}
		if key != "" {
			claimed[key] = true
		}
	}
	sort.SliceStable(kept, func(i, j int) bool { return date10(kept[i].Date) < date10(kept[j].Date) })
	return kept, rejected
}

func isDPS(e canonEvent) bool {
	return e.Extra != nil && flagged(e.Extra["_dps"], true)
}

// priceHistorySource معادلِ source selection مسیرِ محلی: هرگاه رویداد هست
// local-cache، وگرنه داوریِ ذخیره‌شده یا local-db-unseen.
func (s *Service) priceHistorySource(ctx context.Context, symbol string, events []canonEvent) string {
	src := s.storedAdjustSource(ctx, symbol)
	if len(events) > 0 {
		return "local-cache"
	}
	if src == "" {
		return "local-db-unseen"
	}
	return src
}

func (s *Service) stampDataTime(payload map[string]any) map[string]any {
	cands, _ := payload["candles"].([]map[string]any)
	last := ""
	for _, c := range cands {
		if t := date10(stringValue(c["time"])); t > last {
			last = t
		}
	}
	if last == "" {
		payload["lastDataTime"] = nil
	} else {
		payload["lastDataTime"] = last
	}
	return payload
}

// ---------- موتور و زنجیره ----------

func engineEvents(events []canonEvent) ([]canonEvent, []map[string]any, []chainEvent, []map[string]any) {
	applied := []canonEvent{}
	rejected := []map[string]any{}
	chain := []chainEvent{}
	prov := []map[string]any{}
	for _, e := range events {
		d := date10(e.Date)
		if d == "" {
			continue
		}
		e.Date = d
		status := "ok"
		switch {
		case e.Ratio == 0:
			status = "incomplete:ratio"
		case e.Ratio < 0:
			status = "invalid:ratio_nonpositive"
		case e.Ratio < 1e-4 || e.Ratio > 1e4:
			status = "invalid:ratio_out_of_range"
		}
		ratio := any(roundTo(e.Ratio, 12))
		if status != "ok" {
			ratio = nil
			rejected = append(rejected, map[string]any{
				"date": e.Date, "ratio": e.Ratio, "factor_status": status})
		} else {
			applied = append(applied, e)
			chain = append(chain, chainEvent{Date: d, Ratio: e.Ratio, Kind: "source_ratio"})
		}
		prov = append(prov, map[string]any{"date": d, "kind": "source_ratio",
			"ratio": ratio, "status": status})
	}
	return applied, rejected, chain, prov
}

func roundTo(v float64, digits int) float64 {
	p := math.Pow10(digits)
	return math.Round(v*p) / p
}

// chainFactors معادلِ AE.chain_factors: factors[i] برایِ times[i]، لنگر = بزرگ‌ترین تاریخ.
func chainFactors(times []string, events []chainEvent) ([]float64, map[string]any) {
	ds := make([]string, len(times))
	for i, t := range times {
		ds[i] = date10(t)
	}
	valid := make([]chainEvent, 0, len(events))
	for _, e := range events {
		if e.Ratio > 0 && e.Ratio >= 1e-4 && e.Ratio <= 1e4 {
			valid = append(valid, e)
		}
	}
	sort.SliceStable(valid, func(i, j int) bool { return valid[i].Date < valid[j].Date })
	order := make([]int, len(ds))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(i, j int) bool { return ds[order[i]] < ds[order[j]] })
	factors := make([]float64, len(ds))
	for i := range factors {
		factors[i] = 1.0
	}
	f, j := 1.0, len(valid)-1
	for k := len(order) - 1; k >= 0; k-- {
		i := order[k]
		for j >= 0 && valid[j].Date > ds[i] {
			f *= valid[j].Ratio
			j--
		}
		factors[i] = f
	}
	anchored := true
	if len(ds) > 0 {
		maxD := ds[0]
		for _, d := range ds {
			if d > maxD {
				maxD = d
			}
		}
		for i, d := range ds {
			if d == maxD {
				anchored = factors[i] == 1.0
				break
			}
		}
	}
	// provenance/complete برایِ capability؛ payload فقط complete را می‌خواند.
	incomplete := 0
	if len(valid) != len(events) {
		incomplete = len(events) - len(valid)
	}
	return factors, map[string]any{"complete": incomplete == 0,
		"incomplete":        make([]any, incomplete),
		"anchored_last":     anchored,
		"incomplete_events": incomplete}
}

// ---------- پوششِ دفتر ----------

func tableHasColumn(ctx context.Context, conn *sql.DB, table, column string) bool {
	rs, err := conn.QueryContext(ctx, "PRAGMA table_info("+table+")")
	if err != nil {
		return false
	}
	defer rs.Close()
	for rs.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rs.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err == nil && name == column {
			return true
		}
	}
	return false
}

func emptyCoverage(insCode, errText string) map[string]any {
	return map[string]any{
		"available": false, "ins_code": nilIfEmpty(insCode), "error": errText,
		"rows_total": 0, "rows_valid": 0, "rows_rejected": 0, "rows_unmatched": 0,
		"coverage_start": nil, "coverage_end": nil, "pre_coverage_candles": nil,
		"typed_events": 0, "unresolved_events": 0, "needs_offer_price_events": 0,
		"truncated_flow": false, "flow_cap": nil,
	}
}

func (s *Service) ledgerCoverage(ctx context.Context, symbol string, times []string, applied []canonEvent) map[string]any {
	ins := s.resolveInsCode(ctx, symbol)
	if ins == "" {
		return emptyCoverage("", "instrument-unresolved")
	}
	pred, params := s.pred(ctx, "l_val18", symbol)
	var resolved sql.NullString
	q := fmt.Sprintf("SELECT ins_code FROM instruments WHERE %s ORDER BY updated_at DESC LIMIT 1", pred)
	if err := s.market.QueryRowContext(ctx, q, params...).Scan(&resolved); err != nil || !resolved.Valid {
		return emptyCoverage(ins, "instrument-unresolved")
	}
	if !tableHasColumn(ctx, s.market, "price_adjust_events", "corporate_type_code") {
		// همان استثنایِ پایتون وقتی فیکسچرِ قدیمی ستون را ندارد.
		return emptyCoverage(ins, "no such column: corporate_type_code")
	}
	type official struct {
		date       string
		ratio      float64
		kind       string
		typeKnown  bool
		needsOffer bool
	}
	byDate := map[string]official{}
	rowsPA, err := s.market.QueryContext(ctx,
		"SELECT d_even,p_closing_not_adjusted,p_closing,corporate_type_code "+
			"FROM price_adjust_events WHERE ins_code=?", ins)
	if err != nil {
		return emptyCoverage(ins, err.Error())
	}
	for rowsPA.Next() {
		var d any
		var raw, adj, ctype sql.NullFloat64
		if rowsPA.Scan(&d, &raw, &adj, &ctype) != nil {
			continue
		}
		dt := dEvenToDate(d)
		if dt == "" || !raw.Valid || !adj.Valid || raw.Float64 <= 0 {
			continue
		}
		byDate[dt] = official{date: dt, ratio: math.Round(adj.Float64/raw.Float64*1e8) / 1e8, kind: "priceAdjust"}
	}
	rowsPA.Close()
	rowsSC, err := s.market.QueryContext(ctx,
		"SELECT d_even,shares_old,shares_new FROM share_change_events WHERE ins_code=?", ins)
	if err == nil {
		for rowsSC.Next() {
			var d any
			var oldV, newV sql.NullFloat64
			if rowsSC.Scan(&d, &oldV, &newV) != nil {
				continue
			}
			dt := dEvenToDate(d)
			if dt == "" || !oldV.Valid || !newV.Valid || oldV.Float64 <= 0 || newV.Float64 <= 0 {
				continue
			}
			if _, exists := byDate[dt]; !exists {
				byDate[dt] = official{date: dt, ratio: math.Round(oldV.Float64/newV.Float64*1e8) / 1e8, kind: "shareChange"}
			}
		}
		rowsSC.Close()
	}
	// نمادِ پیوندِ کدال: پایتون نخست از خودِ ردیفِ price_adjust_events و در
	// نبودش از instruments (با ins_code) می‌خواند و بعد ک/ی را یکسان می‌کند.
	codalSymbol := ""
	var paSym sql.NullString
	if err := s.market.QueryRowContext(ctx,
		"SELECT symbol FROM price_adjust_events WHERE ins_code=? AND symbol IS NOT NULL LIMIT 1",
		ins).Scan(&paSym); err == nil && paSym.Valid {
		codalSymbol = paSym.String
	}
	if codalSymbol == "" {
		var l18 sql.NullString
		if err := s.market.QueryRowContext(ctx,
			"SELECT l_val18 FROM instruments WHERE ins_code=? LIMIT 1", ins).Scan(&l18); err == nil && l18.Valid {
			codalSymbol = l18.String
		}
	}
	codalSymbol = normalizeSymbol(codalSymbol)
	// نوع از کدال: فقط وقتی یکتا است؛ نبودش «نامشخص» است، نه حدس.
	typeSet := map[string]bool{}
	if codalSymbol != "" {
		if rs, err := s.market.QueryContext(ctx,
			"SELECT title FROM codal_notices WHERE symbol=?", codalSymbol); err == nil {
			for rs.Next() {
				var title sql.NullString
				if rs.Scan(&title) == nil {
					if k := noticeType(title.String); k != "" {
						typeSet[k] = true
					}
				}
			}
			rs.Close()
		}
	}
	uniqueType := ""
	if len(typeSet) == 1 {
		for k := range typeSet {
			uniqueType = k
		}
	}
	dates := make([]string, 0, len(byDate))
	for d := range byDate {
		dates = append(dates, d)
	}
	sort.Strings(dates)
	valid := []official{}
	rejected := 0
	for _, d := range dates {
		o := byDate[d]
		if !(o.ratio > 0) || o.ratio < 1e-4 || o.ratio > 1e4 {
			rejected++
			continue
		}
		o.typeKnown = uniqueType != ""
		o.needsOffer = uniqueType == "capital_increase_contribution"
		valid = append(valid, o)
	}
	unmatched := 0
	for _, o := range valid {
		found := false
		for _, e := range applied {
			dd, ok := daysBetween(o.date, e.Date)
			if ok && dd <= ledgerWindow && e.Ratio > 0 &&
				math.Abs(o.ratio/e.Ratio-1.0) <= ledgerAgreeTol {
				found = true
				break
			}
		}
		if !found {
			unmatched++
		}
	}
	// نوعِ رویداد **برایِ رویدادهایی که ضرب می‌شوند** لازم است (سودِ نقدی از
	// افزایشِ سرمایه جدا نشود). تطبیق با همان پنجره/تلورانسِ تیزکردن است.
	// هر رویدادِ اعمال‌شده یک «همتا» در ردیف‌هایِ سالمِ دفتر می‌جوید.
	typed, unresolved, offer := 0, 0, 0
	for _, e := range applied {
		var mate *official
		if e.Ratio > 0 {
			for i := range valid {
				o := &valid[i]
				dd, ok := daysBetween(o.date, e.Date)
				if ok && dd <= ledgerWindow &&
					math.Abs(o.ratio/e.Ratio-1.0) <= ledgerAgreeTol {
					mate = o
					break
				}
			}
		}
		if mate != nil && mate.typeKnown {
			typed++
		} else {
			unresolved++
		}
		if mate != nil && mate.needsOffer {
			offer++
		}
	}
	coverageStart, coverageEnd := "", ""
	if len(valid) > 0 {
		coverageStart, coverageEnd = valid[0].date, valid[len(valid)-1].date
	}
	var pre any
	if coverageStart != "" {
		n := 0
		for _, t := range times {
			if date10(t) < coverageStart {
				n++
			}
		}
		pre = n
	}
	truncated := false
	var flowCap any
	if n := len(byDate); n >= corpSize {
		truncated = true
		flowCap = corpSize
	} else {
		flowCap = corpSize
	}
	return map[string]any{
		"available": true, "ins_code": ins, "error": nil,
		"rows_total": len(dates), "rows_valid": len(valid), "rows_rejected": rejected,
		"rows_unmatched": unmatched, "coverage_start": nilIfEmpty(coverageStart),
		"coverage_end": nilIfEmpty(coverageEnd), "pre_coverage_candles": pre,
		"typed_events": typed, "unresolved_events": unresolved,
		"needs_offer_price_events": offer, "truncated_flow": truncated,
		"flow_cap": flowCap,
	}
}

func noticeType(title string) string {
	t := strings.ReplaceAll(strings.ReplaceAll(strings.ReplaceAll(title, "\u0643", "\u06a9"),
		"\u064a", "\u06cc"), "\u200c", " ")
	groups := []struct {
		kind string
		keys []string
	}{
		{"capital_increase_contribution", []string{"حق تقدم", "پذیره‌نویسی", "پذیرهنویسی", "آورده"}},
		{"capital_increase_reserve", []string{"افزایش سرمایه"}},
		{"cash_dividend", []string{"پرداخت سود", "تقسیم سود", "سود نقدی", "سود دوره"}},
		{"stock_split", []string{"تجزیه سهم", "تقسیم سهام"}},
		{"stock_merge", []string{"تجمیع سهم", "تجمیع سهام"}},
	}
	for _, g := range groups {
		for _, k := range g.keys {
			if strings.Contains(t, k) {
				return g.kind
			}
		}
	}
	return ""
}

// ---------- توانایی ----------

var noEventKinds = map[string]bool{"option": true, "bond": true, "future": true, "right": true}

func functionalState(chain, coverage map[string]any, kind, source string, times []string, stale bool) (bool, []string, string, map[string]any) {
	times10 := make([]string, 0, len(times))
	for _, t := range times {
		times10 = append(times10, date10(t))
	}
	sort.Strings(times10)
	first, last := "", ""
	if len(times10) > 0 {
		first, last = times10[0], times10[len(times10)-1]
	}
	if chain == nil || coverage == nil {
		av := map[string]any{"status": "UNMEASURED", "source": source,
			"requested_start": nilIfEmpty(first), "requested_end": nilIfEmpty(last),
			"covered_start": nil, "covered_end": nil,
			"window_start": nilIfEmpty(first), "window_end": nilIfEmpty(last),
			"valid_points": 0, "incomplete_points": len(times10),
			"window_available": false, "stale": stale, "kind": kind}
		return false, []string{"unmeasured:زنجیره یا پوششِ این نماد سنجیده نشده است"},
			"UNMEASURED", av
	}
	reasons := []string{}
	if !flagged(coverage["available"], true) {
		errText := stringValue(coverage["error"])
		if errText == "" {
			errText = "no-rows"
		}
		reasons = append(reasons, "ledger-unavailable:"+errText)
	} else if intVal(coverage["rows_total"]) == 0 {
		reasons = append(reasons, "no-official-rows-for-instrument:هیچ ردیفِ رسمیِ این "+
			"ابزار درِ بانک نیست، پس «بی‌اثر‌بودنِ تاریخ» اثبات نمی‌شود")
	}
	if n := intVal(coverage["rows_rejected"]); n > 0 {
		reasons = append(reasons, fmt.Sprintf("ledger-rows-rejected:%d", n))
	}
	if !flagged(chain["complete"], true) {
		reasons = append(reasons, fmt.Sprintf("chain-incomplete:%d", intVal(chain["incomplete_events"])))
	}
	if n := intVal(coverage["unresolved_events"]); n > 0 {
		reasons = append(reasons, fmt.Sprintf("event-type-unresolved:%d", n))
	}
	if n := intVal(coverage["needs_offer_price_events"]); n > 0 {
		reasons = append(reasons, fmt.Sprintf("offer-price-missing:%d", n))
	}
	if n := intVal(coverage["rows_unmatched"]); n > 0 {
		reasons = append(reasons, fmt.Sprintf("ledger-rows-unmatched-by-price-series:%d", n))
	}
	if flagged(coverage["truncated_flow"], true) {
		reasons = append(reasons, fmt.Sprintf("ledger-flow-truncated-at-cap:%d", intVal(coverage["flow_cap"])))
	}
	if pc := intVal(coverage["pre_coverage_candles"]); pc > 0 {
		reasons = append(reasons, fmt.Sprintf("candles-before-ledger-coverage:%d", pc))
	}
	noEvent := noEventKinds[kind]
	preOnly := len(reasons) > 0
	for _, r := range reasons {
		if !strings.HasPrefix(r, "candles-before-ledger-coverage") {
			preOnly = false
			break
		}
	}
	noEventOK := noEvent
	for _, r := range reasons {
		if !(strings.HasPrefix(r, "no-official-rows-for-instrument") ||
			strings.HasPrefix(r, "candles-before-ledger-coverage")) {
			noEventOK = false
			break
		}
	}
	status := ""
	switch {
	case stale:
		status = "STALE"
	case !flagged(coverage["available"], true):
		if e := stringValue(coverage["error"]); e == "db-unopenable" || e == "instrument-unresolved" {
			status = "FAILED"
		} else {
			status = "SOURCE_GAP"
		}
	case noEventOK:
		status = "AVAILABLE_NO_EVENTS"
	case len(reasons) == 0:
		status = "AVAILABLE"
	case preOnly:
		status = "PARTIAL"
	default:
		hasNoOfficial := false
		for _, r := range reasons {
			if strings.HasPrefix(r, "no-official-rows") {
				hasNoOfficial = true
			}
		}
		if hasNoOfficial {
			status = "SOURCE_GAP"
		} else {
			status = "UNVERIFIED"
		}
	}
	available := status == "AVAILABLE" || status == "AVAILABLE_NO_EVENTS"
	covStart := coverage["coverage_start"]
	covEnd := coverage["coverage_end"]
	winStart, winAvail := first, available
	if noEvent {
		winStart, winAvail = first, true
	} else if covStart != nil && first != "" {
		cs := stringValue(covStart)
		if cs > first {
			winStart = cs
			winAvail = true
			for _, r := range reasons {
				if !strings.HasPrefix(r, "candles-before-ledger-coverage") {
					winAvail = false
				}
			}
		}
	}
	valid := 0
	for _, t := range times10 {
		if winStart == "" || t >= winStart {
			valid++
		}
	}
	avail := map[string]any{
		"status": status, "source": source,
		"requested_start": nilIfEmpty(first), "requested_end": nilIfEmpty(last),
		"covered_start": covStart, "covered_end": covEnd,
		"window_start": nilIfEmpty(winStart), "window_end": nilIfEmpty(last),
		"valid_points": valid, "incomplete_points": maxInt(0, len(times10)-valid),
		"window_available": winAvail && !stale, "stale": stale, "kind": kind,
	}
	return available, reasons, status, avail
}

func intVal(v any) int {
	switch x := v.(type) {
	case int:
		return x
	case int64:
		return int(x)
	case float64:
		return int(x)
	}
	return 0
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func (s *Service) adjustCapabilityFull(ctx context.Context, applied []canonEvent, chain, coverage map[string]any, symbol, source string, times []string, stale bool) map[string]any {
	kind := s.instrumentKind(ctx, symbol)
	available, blockers, status, availability := functionalState(chain, coverage, kind, source, times, stale)
	reason := ""
	switch {
	case available && status == "AVAILABLE_NO_EVENTS":
		reason = "این ابزار در قراردادِ عملکردیِ فعلی رویدادِ تعدیلِ رسمی ندارد؛ سریِ عملکردی همان خام است."
	case available:
		reason = "الزاماتِ تعدیلِ عملکردی از دادهٔ همین نماد اثبات شد."
	case status == "PARTIAL":
		reason = "بخشی از تاریخچه پیش از پوششِ دفتر است؛ بازهٔ پس از پوشش قابل استفاده است."
	case status == "STALE":
		reason = "دادهٔ این نماد از پایگاه محلی و کهنه است؛ تعدیلِ عملکردی تأیید نشد."
	case status == "SOURCE_GAP":
		reason = "دادهٔ رسمیِ رویداد برای این نماد ناقص است؛ تعدیلِ عملکردی تأیید نشد."
	case status == "UNMEASURED":
		reason = "زنجیره/پوششِ این نماد سنجیده نشده است."
	default:
		reason = adjFunctionalReason
	}
	corr := s.correctionsCapability(ctx, symbol)
	combined := adjKnownSources[source] || strings.HasPrefix(source, "fund-portal") ||
		strings.HasPrefix(source, "rahavard-reference-correction")
	if flagged(corr["covered"], true) && stringValue(corr["mode"]) == "authoritative" &&
		flagged(chain["complete"], true) {
		combined = true
		available = true
		status = "AVAILABLE_REFERENCE_CORRECTION"
		reason = "زنجیرهٔ تعدیل از بستهٔ تصحیحِ نسخه‌دارِ مرجع ساخته شده است؛ " +
			"گام‌های رسمیِ کنارگذاشته‌شده در adjustRejected با وضعیت ثبت شده‌اند."
		blockers = []string{}
	}
	var chainComplete any
	if chain != nil {
		chainComplete = flagged(chain["complete"], true)
	}
	return map[string]any{
		"source": source, "combined_available": combined,
		"functional_available": available, "functional_status": status,
		"functional_reason": reason, "functional_blockers": blockers,
		"availability": availability, "event_count": len(applied),
		"ledger_sharpened": nil, "ledger_ambiguous": nil,
		"chain_complete":          chainComplete,
		"chain_incomplete_events": intVal(chain["incomplete_events"]),
		"coverage":                coverage, "corrections": corr,
	}
}

// ---------- کندل ----------

func (s *Service) canonicalPriceHistory(ctx context.Context, symbol string) ([]map[string]any, int, int, int, error) {
	pred, params := s.pred(ctx, "symbol", symbol)
	q := fmt.Sprintf("SELECT symbol,date,open,high,low,close,volume,last,value,src "+
		"FROM price_history WHERE %s ORDER BY date DESC, volume DESC", pred)
	rs, err := s.market.QueryContext(ctx, q, params...)
	if err != nil {
		return nil, 0, 0, 0, err
	}
	defer rs.Close()
	seen := map[string]bool{}
	dbRows, noTrade, invalid := 0, 0, 0
	rows := []map[string]any{}
	for rs.Next() {
		var sym, date, src sql.NullString
		var open, high, low, closeP, volume, last, value sql.NullFloat64
		if err := rs.Scan(&sym, &date, &open, &high, &low, &closeP, &volume, &last, &value, &src); err != nil {
			return nil, 0, 0, 0, err
		}
		if !date.Valid || date.String == "" || seen[date.String] {
			continue
		}
		seen[date.String] = true
		dbRows++
		closeF := 0.0
		if closeP.Valid {
			closeF = closeP.Float64
		}
		if closeF <= 0 {
			// قراردادِ کندل: پایانیِ نامعتبر ⇒ ردیف کندل نمی‌شود. علت هم همان
			// قاعدۀ پایتون است: حجمِ صفر = روزِ بی‌معامله، بقیه = ردیفِ خراب.
			if !volume.Valid || volume.Float64 <= 0 {
				noTrade++
			} else {
				invalid++
			}
			continue
		}
		o := 0.0
		if open.Valid {
			o = open.Float64
		}
		if o <= 0 {
			o = closeF
		}
		v := 0.0
		if volume.Valid {
			v = volume.Float64
		}
		if v <= 0 {
			noTrade++
			continue
		}
		hRaw, lRaw := 0.0, 0.0
		if high.Valid {
			hRaw = high.Float64
		}
		if low.Valid {
			lRaw = low.Float64
		}
		var lastV any
		if last.Valid && last.Float64 != 0 {
			lastV = last.Float64
		}
		lastF := 0.0
		if lastV != nil {
			lastF = lastV.(float64)
		}
		h, l := candlecontract.Widen(o, hRaw, lRaw, closeF, lastF)
		// تهی/NULL یعنی «منشأ نامعلوم» (ردیف‌های پیش از ستونِ src)، نه «published».
		// همان قراردادِ candle_contract.from_db_row: برچسبِ منبع حدس زده نمی‌شود.
		srcText := "legacy-unknown"
		if src.Valid && src.String != "" {
			srcText = src.String
		}
		row := map[string]any{
			"symbol": sym.String, "time": date.String, "date": date.String,
			"open": o, "high": h, "low": l, "high_raw": hRaw, "low_raw": lRaw,
			"close": closeF, "last": lastV, "value": nilOrFloat(value),
			"volume": v, "src": srcText,
		}
		rows = append(rows, row)
	}
	if err := rs.Err(); err != nil {
		return nil, 0, 0, 0, err
	}
	reverseRows(rows)
	return rows, dbRows, noTrade, invalid, nil
}

func nilOrFloat(v sql.NullFloat64) any {
	if v.Valid && v.Float64 != 0 {
		return v.Float64
	}
	return nil
}

func candlesStale(rows []map[string]any, now time.Time) bool {
	if len(rows) == 0 {
		return false
	}
	last := ""
	for _, r := range rows {
		if t := stringValue(r["time"]); t > last {
			last = t
		}
	}
	last = date10(last)
	d, err := time.Parse("2006-01-02", last)
	if err != nil {
		return false
	}
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	return today.Sub(time.Date(d.Year(), d.Month(), d.Day(), 0, 0, 0, 0, time.UTC)) > 7*24*time.Hour
}
