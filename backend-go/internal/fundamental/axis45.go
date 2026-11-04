package fundamental

// لایۀ ۴ (فروش سالانه ÷ ارزش بازار) و لایۀ ۵ (رژیمِ قیمت‌گذاری صنعت) + دروازۀ
// صنایعِ دستی — پورتِ `fts_engine.annualized_sales`/`ind4_exempt`/`sector_filter`
// و `api/fundamental.ind4_valuation`/`ind5_industry`/`norm_industry_list`/
// `industry_gate`/`v10_data_gaps`.
//
// هیچ داوریِ دومی اینجا ساخته نمی‌شود؛ هر رشته، هر ضریب و هر گیت عیناً از
// اوراکلِ پایتون آمده و داورِ آن وکتورهایِ کامیت‌شده درِ `testdata/vectors/` است
// (valuation/sector/annualize/statements/indicators). کمک‌تابع‌هایِ این فایل
// `a45`-پیشوند دارند تا با تعریف‌هایِ canonicalِ شاخه‌هایِ دیگر نخورند؛ هرکدام
// نشانِ `TODO(unify)` دارد.

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// ── یکاها (تنها تعریف درِ `codal_units`) ────────────────────────────────────
const (
	a45ScaleMrl     = 1_000_000.0      // CU.SCALES["mrl"] — میلیون ریال
	a45ScaleBtl     = 10_000_000_000.0 // CU.SCALES["btl"] — میلیارد تومان
	a45RialPerBtm   = 1e10             // CU.RIAL_PER_BTM
	a45MrlToRial    = a45ScaleMrl      // fts_engine.MRL_TO_RIAL
	a45MrlToBtmFact = a45ScaleMrl / a45RialPerBtm
)

// a45AnnualizationScale / a45OpBasisKinds عینِ ANNUALIZATION_SCALE و
// _OP_BASIS_KINDS درِ fts_engine.
var (
	a45AnnualizationScale = []int{3, 4, 5, 6, 9, 12}
	a45OpBasisKinds       = []string{"financial", "service", "fund", "holding"}
)

// ── codal_units ─────────────────────────────────────────────────────────────
// TODO(unify): به internal/units منتقل شود — `CU.is_valid`/`CU.label`/`CU.to_mrl`
// تنها تعریفِ «واحدِ پول»اند و هر consumer تازه باید همان را بخواند؛ نسخهٔ محلیِ
// `a45` فقط تا ساخته‌شدنِ آن لایه دوام می‌آورد.

var (
	a45UnitScales = map[string]float64{"mrl": a45ScaleMrl, "btl": a45ScaleBtl}
	a45UnitLabels = map[string]string{"mrl": "میلیون ریال", "btl": "میلیارد تومان"}
)

const a45UnitUnknownLabel = "واحد نامعلوم"

// a45UnitScale عینِ `CU.scale`: بی‌واحد ⇒ nil (هیچ ضریبی حدس نمی‌شود).
func a45UnitScale(v any) *float64 {
	s, ok := v.(string)
	if !ok {
		return nil
	}
	f, has := a45UnitScales[s]
	if !has {
		return nil
	}
	return &f
}

// a45UnitIsValid عینِ `CU.is_valid` — نقیضِ `PRESENT_SQL`، شرطِ خواندنِ پایتون.
func a45UnitIsValid(v any) bool { return a45UnitScale(v) != nil }

// a45UnitLabel عینِ `CU.label` — «واحد نامعلوم» برایِ هر چیزِ شناخته‌نشده.
func a45UnitLabel(v any) string {
	if s, ok := v.(string); ok {
		if l, has := a45UnitLabels[s]; has {
			return l
		}
	}
	return a45UnitUnknownLabel
}

// a45FloatValue عینِ `float(v)` با exceptِ TypeError/ValueError ⇒ بی‌مقدار.
func a45FloatValue(v any) (float64, bool) {
	switch x := v.(type) {
	case nil:
		return 0, false
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	case string:
		f, err := strconv.ParseFloat(trimSpace(x), 64)
		if err != nil {
			return 0, false
		}
		return f, true
	}
	return toF(v), true
}

// a45ToMrl عینِ `CU.to_mrl`: هر مقیاسِ شناخته‌شده ← میلیون ریال؛ بی‌واحد یا
// مقدارِ None ⇒ nil (نه صفر).
func a45ToMrl(value, unitNorm any) *float64 {
	s := a45UnitScale(unitNorm)
	if s == nil || value == nil {
		return nil
	}
	f, ok := a45FloatValue(value)
	if !ok {
		return nil
	}
	out := f * (*s) / a45ScaleMrl
	return &out
}

// a45FsAmountMrl عینِ `fts_engine.fs_amount_mrl(row, key)` — پولِ یکِ ردیفِ صورتِ
// مالی ← مبنایِ داخلیِ موتور، با مقیاسِ خودِ `unit_norm`ِ همان ردیف.
func a45FsAmountMrl(row map[string]any, key string) *float64 {
	if len(row) == 0 {
		return nil
	}
	return a45ToMrl(row[key], row["unit_norm"])
}

// a45NormalizeMrlToBtom عینِ `normalize_mrl_to_btom` — ورودی **باید** میلیون ریال
// باشد (تبدیلِ خودِ ردیف از `a45FsAmountMrl` می‌گذرد).
func a45NormalizeMrlToBtom(valueMrl any) float64 {
	return toF(valueMrl) * a45MrlToBtmFact
}

// a45Bt عینِ `api/fundamental._bt`: میلیون ریال → میلیارد تومان با گردِ پایتون.
func a45Bt(valueMrl any) float64 {
	return pyround.Round(toF(valueMrl)*a45MrlToBtmFact, 1)
}

// ── متن‌هایِ سالانه‌سازی (کاربر می‌بیند؛ یکِ کدپوینت هم نباید جابه‌جا شود) ────
const (
	a45BasisOpRevenue      = "درآمد عملیاتیِ صورت مالی سالانه — جایگزینِ «فروش» برایِ طبقه"
	a45BasisTplPartial     = "تجمیعی %02d/%d × ۱۲÷%d (=×%.2f)"
	a45BasisTplFull        = "تجمیعی ۱۲ ماهِ کاملِ سال مالی %d (×۱٫۰)"
	a45BasisNoMonthly      = "مراجعه به فروش صورت مالی سالانه (بی‌گزارش ماهانه)"
	a45BasisBadUnit        = "ضریب پویا مردود شد (واحد مشکوک) → فروش سالانهٔ کدال"
	a45BasisSalesNa        = "N/A — هلدینگ/سرمایه‌گذاری/واسطۀ مالی (سند v2.1 F-04)"
)

// a45AnnualizeRows عینِ `fts_engine.annualize_rows` — خالصِ سالانه‌سازی، **یک**
// قاعده برایِ مسیرِ SQL و مسیرِ کل‌بازار:
//
//	۰) طبقۀ مالی/خدماتی/صندوق/هلدینگ ⇒ درآمدِ صورتِ مالیِ سالانه با ضریبِ ۱٫۰
//	۱) تجمیعیِ YTDِ بلندترینِ ماهِ دارایِ گزارش × ۱۲÷م  (م = همان ماه، نه تقویم)
//	۲) دوازده‌ماهۀ کامل ⇒ خودِ YTD (×۱٫۰)
//	۳) بی‌گزارشِ ماهانه ⇒ فروشِ صورتِ مالیِ سالانۀ کدال
//	۴) گیتِ «واحدِ مشکوک»: >۴× یا <۰٫۲۵× فروشِ سالانه ⇒ مبنایِ کدال با
//	   `reconciled=False`
//
// نقشۀ تهی یعنی «قابل محاسبه نبود» (هیچ‌وقت صفرِ ساختگی نه). `fsRev` باید با
// مقیاسِ خودِ ردیف به میلیون‌ریال رسیده باشد و `fsUnitKnown` بگوید آن تبدیل
// شاهدِ واحد داشته یا نه؛ بی‌شاهدِ واحد هیچ‌یک از سه قاعدۀ وابسته به مقیاس
// (۰، ۳، ۴) اجرا نمی‌شود — این «بی‌رأی» است، نه رأیِ منفی.
func a45AnnualizeRows(rows [][]any, fsRev *float64, opBasis, fsUnitKnown bool) map[string]any {
	if opBasis {
		if fsRev == nil || !fsUnitKnown || *fsRev <= 0 {
			return map[string]any{}
		}
		return map[string]any{
			"annual_sales_mrl": *fsRev, "months_used": int64(12), "reconciled": true,
			"operational_revenue_basis": true, "basis": a45BasisOpRevenue,
		}
	}
	annual, months := 0.0, int64(0)
	basis := ""
	reconciled := true
	if len(rows) > 0 {
		year := seriesInt(rows[0], 0)
		cur := make([][]any, 0, len(rows))
		for _, r := range rows {
			if seriesInt(r, 0) == year {
				cur = append(cur, r)
			}
		}
		// `sorted(key=lambda r: -int(r[1] or 0))` — پایدار، پس تساویِ ماه
		// ترتیبِ ورودی را نگه می‌دارد.
		sort.SliceStable(cur, func(i, j int) bool {
			return seriesInt(cur[i], 1) > seriesInt(cur[j], 1)
		})
		if len(cur) > 0 {
			months = seriesInt(cur[0], 1)
			ytd := toF(seriesCell(cur[0], 3))
			if months >= 1 && ytd > 0 {
				if months >= 12 {
					annual = ytd
					basis = fmt.Sprintf(a45BasisTplFull, year)
				} else {
					annual = ytd * 12.0 / float64(months)
					basis = fmt.Sprintf(a45BasisTplPartial, months, year, months,
						12.0/float64(months))
				}
			}
		}
	}
	// هر دو شاخۀ وابسته به مقیاسِ صورتِ مالی از `fsr` می‌گذرند: ردیفی که واحدش
	// اعلام نشده نه صفرِ واقعی است و نه مبنایِ محاسبه.
	fsr := 0.0
	if fsUnitKnown && fsRev != nil {
		fsr = *fsRev
	}
	if annual <= 0 && fsr > 0 {
		annual, months = fsr, 12
		basis = a45BasisNoMonthly
	}
	if annual <= 0 {
		return map[string]any{}
	}
	// گیتِ «واحدِ مشکوک» فقط برایِ سالانه‌سازیِ واقعی (۰ < م < ۱۲) معنا دارد؛
	// گزارشی که خودش ۱۲ ماهِ کامل را پوشش می‌دهد مستقیم پذیرفته می‌شود.
	witness := true
	if fsr > 0 && months > 0 && months < 12 && (annual > fsr*4.0 || annual < fsr*0.25) {
		reconciled = false
		annual, months = fsr, 12
		basis = a45BasisBadUnit
	} else {
		// ردیفِ مرجعِ بی‌واحد تنها شاهدِ مقیاسِ `monthly_sales` را از کار می‌اندازد
		// (آن جدول ستونِ واحدِ پول ندارد): عدد **راستی‌آزمایی‌نشده** می‌ماند.
		witness = fsUnitKnown
	}
	return map[string]any{
		"annual_sales_mrl": annual, "months_used": months, "basis": basis,
		"reconciled":                reconciled && witness,
		"unit_unverified":           !witness,
		"operational_revenue_basis": false,
	}
}

// ── انتخابِ ردیفِ مرجع ──────────────────────────────────────────────────────
// TODO(unify): `annual_statements` + `pick_reference` + `reference_annual`
// متعلقِ شاخۀ «صورتِ مالی مرجع» است؛ این‌ها نسخهٔ محلی‌اند، ساخته‌شده از همان SQL
// و همان رتبه‌بندی، چون `AnnualizedSales` بی‌`refِ` تزریق‌شده به «آخرینِ سالانۀ
// هر نماد» نیاز دارد. داورشان آرایۀ `reference` درِ statements.json (۵ نمادِ
// فیکسچر) و آرایۀ `annual` درِ همان فایل (۱۵ کیسِ limit=6/3/1) است.

// a45FsCols عینِ `fts_engine.FS_COLS` (`tracing_no` درِ اوراکل جدا افزوده می‌شود).
const a45FsCols = "period_end, period_months, title, revenue, gross_profit, " +
	"operating_profit, net_profit, basic_eps, company_name, unit_norm"

// a45IsAudited عینِ `fts_engine._is_audited`: «حسابرسی شده» دارد و «نشده» ندارد.
func a45IsAudited(title string) bool {
	t := normFa(title)
	return strings.Contains(t, "حسابرسی شده") && !strings.Contains(t, "نشده")
}

// a45IsAmendment عینِ `fts_engine._is_amendment`.
func a45IsAmendment(title string) bool {
	return strings.Contains(normFa(title), "اصلاحیه")
}

// a45Fn عینِ `fts_engine._fn`: floatِ امن که Noneِ واقعی را حفظ می‌کند (ستون‌هایی
// که «درج نشده» بودنشان معنا دارد — بی‌آن، شاخص ۳ به‌جای «نامفهوم» ۰٪ می‌داد).
func a45Fn(v any) any {
	f, ok := a45FloatValue(v)
	if !ok || math.IsNaN(f) {
		return nil
	}
	return f
}

// a45RowConflicts عینِ `fts_engine.row_conflicts`: تناقض‌هایِ اعلامیِ یکِ ردیف
// (دورۀ متن ≠ دورۀ ستون، شمارِ ماهِ متن ≠ ستون). هیچ ردیفی کنارِ این نمی‌رود و
// هیچ آستانه‌ای اینجا نیست.
func a45RowConflicts(periodEnd any, title string, periodMonths any) []string {
	out := []string{}
	tp := period.FromTitle(title)
	pe := period.Canonicalize(periodEnd)
	if tp != nil && pe != nil && *tp != "" && *pe != "" && *tp != *pe {
		out = append(out, "title_period")
	}
	tm := period.MonthsFromTitle(title)
	var pm *int
	if periodMonths != nil {
		raw := trimSpace(pyStr(periodMonths))
		if raw != "" {
			if i, err := strconv.Atoi(raw); err == nil {
				v := i
				pm = &v
			} else if f, err := strconv.ParseFloat(raw, 64); err == nil {
				v := int(f)
				pm = &v
			}
		}
	}
	if tm != nil && pm != nil && *tm != 0 && *pm != 0 && *tm != *pm {
		out = append(out, "title_months")
	}
	return out
}

// a45AnnualStatements عینِ `fts_engine.annual_statements` با همان پنجرۀ بزرگ
// (`limit*12+48`) و همان غربالِ Python: «سالانہ بودن» از `effective_months`
// خوانده می‌شود، نه از ستونِ خام، و برندۀ هر سالِ مالی با `statement_rank`
// انتخاب می‌شود (نه با ترتیبِ پیشآمدِ SQLite) تا پوستۀ بی‌عددِ تازه‌تر ردیفِ
// عدددار را از دیدِ کلِ لایه‌ها پنهان نکند.
func (s *Service) a45AnnualStatements(ctx context.Context, symbol string,
	requireAudit, excludeConsolidated bool, limit int) ([]map[string]any, error) {
	pred, args := s.a45Pred(ctx, "symbol", symbol)
	window := max(limit, 1)*12 + 48
	rows, err := s.rows(ctx, "SELECT "+a45FsCols+", tracing_no FROM financial_statements "+
		"WHERE "+pred+" AND "+period.DatedSQL("")+
		" AND (period_months>=12 OR period_months IS NULL) "+
		"ORDER BY period_end DESC LIMIT ?", append(args, int64(window)))
	if err != nil {
		return nil, err
	}
	type ranked struct {
		rank rankTuple
		row  map[string]any
	}
	byYear := map[string]ranked{}
	years := []string{}
	for _, r := range rows {
		t := strOr(r["title"])
		months, monthsSrc := period.EffectiveMonths(r["period_end"], r["period_months"], t)
		if months == nil || *months < 12 {
			continue
		}
		consolidated := isConsolidated(t)
		if excludeConsolidated && consolidated {
			continue
		}
		if requireAudit && !a45IsAudited(t) {
			continue
		}
		yrv := period.FiscalYear(r["period_end"])
		if yrv == nil || *yrv == "" {
			continue
		}
		yr := *yrv
		tracingNo, _ := toI(orZero(r["tracing_no"]))
		audited := a45IsAudited(t)
		otherEntity := titleEntitySuffix(t) != ""
		cand := map[string]any{
			"period_end":     r["period_end"],
			"fiscal_year":    yr,
			"period_months":  int64(*months),
			"months_source":  monthsSrc,
			"title":          t,
			"audited":        audited,
			"consolidated":   consolidated,
			"other_entity":   otherEntity,
			"conflicts":      a45RowConflicts(r["period_end"], t, int64(*months)),
			"unit_norm":      r["unit_norm"],
			"unit_valid":     a45UnitIsValid(r["unit_norm"]),
			"tracing_no":     tracingNo,
			"company_name":   strOr(r["company_name"]),
			"amended":        a45IsAmendment(t),
			"revenue":        a45Fn(r["revenue"]),
			"gross_profit":   a45Fn(r["gross_profit"]),
			"operating_profit": a45Fn(r["operating_profit"]),
			"net_profit":     a45Fn(r["net_profit"]),
			"basic_eps":      a45Fn(r["basic_eps"]),
		}
		rank := statementRank(otherEntity, consolidated, rowCompleteness(cand), tracingNo)
		cur, has := byYear[yr]
		if !has {
			years = append(years, yr)
			byYear[yr] = ranked{rank, cand}
			continue
		}
		if rank.cmp(cur.rank) < 0 { // `rank < cur[0]` درِ پایتون (ascending)
			byYear[yr] = ranked{rank, cand}
		}
	}
	sort.Strings(years)
	out := make([]map[string]any, 0, len(years))
	for i := len(years) - 1; i >= 0; i-- { // `sorted(by_year, reverse=True)`
		out = append(out, byYear[years[i]].row)
		if len(out) >= limit {
			break
		}
	}
	return out, nil
}

// a45RowCarries عینِ `fts_engine.row_carries`: آیا ردیف هر دو عددِ لازم را دارد؟
// (برایِ `need` — بندِ P-2 سیاست؛ بی‌`need` هرگز خوانده نمی‌شود.)
func a45RowCarries(row map[string]any, need []string) bool {
	for _, k := range need {
		v, ok := row[k]
		if !ok || v == nil {
			return false
		}
		if s, isStr := v.(string); isStr && trimSpace(s) == "" {
			return false
		}
		if k == "revenue" && toF(v) <= 0 {
			return false
		}
	}
	return true
}

// a45PickReference عینِ `fts_engine.pick_reference`: سلسلۀ‌مراتبِ سالانۀ
// حسابرسی‌شدۀ غیرتلفیقی ← سالانۀ غیرتلفیقی ← سالانۀ اخیر، با قاعدۀ «هرگز» برایِ
// ردیفِ شرکتِ دیگر (پلۀ سوم هم آن را بیرون می‌گذارد) و «دو گذر» وقتی `need`
// داده شده باشد (اول ردیفِ دارایِ عدد، وگرنه همان پلکان بی‌آن شرط).
func a45PickReference(rows []map[string]any, need []string) map[string]any {
	type ranked struct {
		rank rankTuple
		row  map[string]any
	}
	byYear := map[string]ranked{}
	years := []string{}
	for _, r := range rows {
		if toF(r["period_months"]) < 12 {
			continue
		}
		yr := strOr(r["fiscal_year"])
		if yr == "" {
			continue
		}
		tracingNo, _ := toI(orZero(r["tracing_no"]))
		otherEntity := truthy(r["other_entity"])
		rank := statementRank(otherEntity, truthy(r["consolidated"]), rowCompleteness(r), tracingNo)
		cur, has := byYear[yr]
		if !has {
			years = append(years, yr)
			byYear[yr] = ranked{rank, r}
			continue
		}
		if rank.cmp(cur.rank) < 0 {
			byYear[yr] = ranked{rank, r}
		}
	}
	// `sorted(..., key=lambda t: str(t[1]["fiscal_year"]), reverse=True)` —
	// ترتیبِ واژگانیِ نزولیِ سال؛ سال‌ها یکتااند، پس تساویِ پایدار معنا ندارد.
	sort.Strings(years)
	cand := make([]map[string]any, 0, len(years))
	for i := len(years) - 1; i >= 0; i-- {
		cand = append(cand, byYear[years[i]].row)
	}
	tiers := []func(audited, consolidated bool) bool{
		func(a, c bool) bool { return a && !c }, // حسابرسی‌شدۀ غیرتلفیقی
		func(_, c bool) bool { return !c },      // غیرتلفیقی
		func(_, _ bool) bool { return true },    // هر سالانۀ اخیر
	}
	passes := []bool{false}
	if len(need) > 0 {
		passes = []bool{true, false}
	}
	for _, requireNumbers := range passes {
		for _, want := range tiers {
			for _, r := range cand {
				if truthy(r["other_entity"]) {
					continue
				}
				if !want(truthy(r["audited"]), truthy(r["consolidated"])) {
					continue
				}
				if requireNumbers && !a45RowCarries(r, need) {
					continue
				}
				return r
			}
		}
	}
	return nil
}

// a45ReferenceAnnual عینِ `fts_engine.reference_annual` — آخرین صورتِ مالی
// سالانۀ این نماد با همان پلکانِ تنزل (منبعِ قطعیِ شاخص‌های ۳ و ۴).
func (s *Service) a45ReferenceAnnual(ctx context.Context, symbol string) (map[string]any, error) {
	rows, err := s.a45AnnualStatements(ctx, symbol, false, false, 12)
	if err != nil {
		return nil, err
	}
	return a45PickReference(rows, nil), nil
}

// ── طبقۀ شرکت ──────────────────────────────────────────────────────────────
// TODO(unify): `fts_engine.company_profile` متعلقِ شاخۀ «طبقه/پروفایل» است
// (وکتورهایش indicators.json → profile). این نسخهٔ محلی تا یکپارچه‌سازی.

var (
	// a45HoldingSectorKeys عینِ _HOLDING_SECTOR_KEYS — اشتراکِ دو فهرستِ پیشین،
	// تا اسکرینر و کارت برایِ یکِ نماد دو جواب متفاوت ندهند.
	a45HoldingSectorKeys = []string{"سرمایه گذاری", "سرمایه‌گذاری", "چندرشته", "هلدینگ",
		"بانک", "واسطه گری", "واسطه‌گری", "نهادهای مالی واسط"}
	a45FinTokensSrc = []string{"اعتباري", "اعتباری", "بيمه", "بیمه",
		"ليزينگ", "لیزینگ", "کارگزاري", "کارگزاری", "اوراق"}
	a45HoldTokensSrc = []string{"بانک", "سرمایه گذاری", "سرمایه‌گذاری", "هلدینگ",
		"واسطه گری", "واسطه‌گری", "نهادهای مالی واسط"}
	a45SvcTokensSrc = []string{"خدمات", "حمل", "ترابری", "فناوري", "فناوری", "مخابرات",
		"بازرگاني", "بازرگانی", "پخش", "رستوران", "گردش"}
	// a45NonCompanyTokensSrc عینِ `fts_engine.NON_COMPANY_TOKENS`: نشانه‌هایِ
	// غیرشرکتِ عملیاتی — صندوق/اوراق/حق تقدم و نهادهایِ عمومی. بیمه در
	// classifyIdentity پیش از این فهرست وتو می‌شود (صنعتش «صندوق» دارد).
	a45NonCompanyTokensSrc = []string{"صندوق", "اوراق", "اختيار", "اختیار",
		"حق تقدم", "حق‌تقدم", "خیریه", "شهرداری", "فدراسیون", "موسسه",
		"پرورشگاه", "وقف", "بنیاد"}
)

// a45HoldNorm عینِ `fts_engine._hold_norm`: norm_fa + حذفِ فاصله. بی‌این‌گام
// توکن‌هایِ «سرمایه‌گذاری»/«چندرشته» هرگز به دادهٔ «سرمايه گذاري»/«چند رشته اي»
// نمی‌خوردند (توکنِ مرده) و نوشتارِ هر نماد جواب را عوض می‌کرد.
func a45HoldNorm(text any) string {
	return strings.ReplaceAll(normFa(strOr(text)), " ", "")
}

func a45NormList(src []string, f func(string) string) []string {
	out := make([]string, 0, len(src))
	for _, s := range src {
		out = append(out, f(s))
	}
	return out
}

var (
	a45HoldingSectorTokens = a45NormList(a45HoldingSectorKeys, a45HoldNormStr)
	a45FundToken           = a45HoldNormStr("صندوق")
	a45FinTokens           = a45NormList(a45FinTokensSrc, normFa)
	a45HoldTokens          = a45NormList(a45HoldTokensSrc, normFa)
	a45SvcTokens           = a45NormList(a45SvcTokensSrc, normFa)
	a45NonCompanyTokens    = a45NormList(a45NonCompanyTokensSrc, normFa)
)

func a45HoldNormStr(s string) string { return strings.ReplaceAll(normFa(s), " ", "") }

// a45HoldingClassMatch عینِ `fts_engine.holding_class_match`.
func a45HoldingClassMatch(sectorNorm any, companyName ...string) bool {
	co := ""
	if len(companyName) > 0 {
		co = companyName[0]
	}
	s := a45HoldNorm(sectorNorm) + " " + a45HoldNorm(co)
	return a45AnyTokenIn(a45HoldingSectorTokens, s)
}

// a45FundClassMatch عینِ `fts_engine.fund_class_match` — با استثنای بیمه/
// بازنشستگی (رأیِ ۱: بیمه «وتو/هشدار» است نه معافیت؛ رأیِ ۱۵: صندوق FTS ندارد).
func a45FundClassMatch(sector any, companyName ...string) bool {
	co := ""
	if len(companyName) > 0 {
		co = companyName[0]
	}
	if IsInsuranceSector(strOr(sector)) {
		return false
	}
	return strings.Contains(a45HoldNorm(sector)+" "+a45HoldNorm(co), a45FundToken)
}

func a45AnyTokenIn(tokens []string, s string) bool {
	for _, t := range tokens {
		if strings.Contains(s, t) {
			return true
		}
	}
	return false
}

// برچسب‌ها و مبناهایِ درآمد — عینِ `_PROFILE_LABEL` و متن‌هایِ `company_profile`.
var a45ProfileLabels = map[string]string{
	"production": "تولیدی / صادراتی", "financial": "مالی و بانکی",
	"service": "خدماتی", "fund": "صندوق", "holding": "هلدینگ / سرمایه‌گذاری",
}

const (
	a45BasisFund = "صندوق — درآمد پرتفوی و تغییرات خالص دارایی‌ها"
	a45BasisHolding = "هلدینگ/سرمایه‌گذاری/بانکی — درآمد عملیاتی از پرتفوی، سود " +
		"تسهیلات/سپرده و سرمایه‌گذاری‌ها (بدون «فروش کالا» و تناژ فیزیکی)"
	a45BasisFinancial = "مالی/بانکی — جمع درآمد تسهیلات اعطایی + سپرده‌گذاری + " +
		"سرمایه‌گذاری‌ها + اوراق بدهی + کارمزد (نه «فروش کالا»)"
	a45BasisService    = "خدماتی — کارمزد و درآمد عملیاتی (بدون تناژ فیزیکی)"
	a45BasisProduction = "تولیدی/عمرانی — جمع فروش داخلی + صادراتی (ردیف «جمع» جدول فروش)"
	a45VolumeNoteYes   = "تناژ/تعداد محصول در گزارش فعالیت ماهانه معنادار است؛ " +
		"رشد ریالی بدون رشد تناژ = افزایش قیمت."
	a45VolumeNoteNo = "این شرکت کالای وزن‌شدنی تولید نمی‌کند؛ چک فیزیکی روی " +
		"مبنای متناسبِ همان طبقه (درآمد واقعی پس از تورم) سنجیده میشود نه تن محصول."
	a45PricingNoteYes = "درآمد به دلار/بورس کالا گره خورده (صادراتی)."
	a45PricingNoteNo  = "درآمد ریالیِ نرخ‌گذاری‌شده — ریسک سرکوب نرخ وجود دارد."
)

// a45CompanyProfile عینِ `fts_engine.company_profile`: طبقۀ شرکت + مبنای درآمد
// + اینکه چکِ فیزیکی (تناژ) برایش معنا دارد یا نه.
func a45CompanyProfile(sector, companyName string) map[string]any {
	both := normFa(sector) + " " + normFa(companyName)
	kind, applicable, basis := "production", true, a45BasisProduction
	switch {
	case a45FundClassMatch(sector, companyName):
		kind, applicable, basis = "fund", false, a45BasisFund
	case a45AnyTokenIn(a45HoldTokens, both):
		kind, applicable, basis = "holding", false, a45BasisHolding
	case a45AnyTokenIn(a45FinTokens, both):
		kind, applicable, basis = "financial", false, a45BasisFinancial
	case a45AnyTokenIn(a45SvcTokens, both):
		kind, applicable, basis = "service", false, a45BasisService
	}
	note, pricing := a45VolumeNoteNo, a45PricingNoteNo
	if applicable {
		note, pricing = a45VolumeNoteYes, a45PricingNoteYes
	}
	return map[string]any{
		"kind": kind, "label": a45ProfileLabels[kind], "revenue_basis": basis,
		"volume_applicable": applicable, "volume_note": note, "pricing_note": pricing,
	}
}

// ── نماد ← شاهدِ نامی / شاهدِ صورتِ مالی ─────────────────────────────────────

// a45Pred عینِ `fts_engine.sym_in` (دامنۀ پیش‌فرضِ CODAL). خطایِ resolver مثلِ
// دیگرِ مسیرهایِ همین بسته به شرطِ خامِ `symbol = ?` می‌افتد، تا «بی‌داده» جعلی
// به ۵۰۰ نیفتد و خطایِ واقعیِ بانک درِ خودِ کوئری بالا برود.
func (s *Service) a45Pred(ctx context.Context, col, symbol string) (string, []any) {
	pred, args, err := s.sid.Pred(ctx, col, symbol, symbolid.Codal)
	if err != nil {
		return col + " = ?", []any{symbol}
	}
	return pred, args
}

// a45CompanyNameOf عینِ `fts_engine.company_name_of` — نامِ شرکت از خودِ دیتابیس
// (نه از رشته‌ای که فراخوان آورده)، با همان «تازۀترینِ دورۀ canonical اول،
// بی‌دوره آخر، سپس tracing_no DESC». خطایِ بانک رشتهٔ خالی می‌دهد.
func (s *Service) a45CompanyNameOf(ctx context.Context, symbol string) string {
	pred, args := s.a45Pred(ctx, "symbol", symbol)
	rows, err := s.msQuery(ctx, "SELECT company_name FROM financial_statements "+
		"WHERE "+pred+" AND company_name IS NOT NULL "+
		period.LatestOrderSQL("")+", tracing_no DESC LIMIT 1", args)
	if err != nil || len(rows) == 0 || len(rows[0]) == 0 {
		return ""
	}
	return strOr(rows[0][0])
}

// a45HasOperatingSales عینِ `fts_engine.has_operating_sales` — سه‌مقدار و از
// شواهدِ خودِ اسکرپ: 1 یعنی «جمع درآمدهای عملیاتی» مچ شد؛ 0 یعنی شیت خوانده شد
// ولی چنین سطری نداشت (صندوق/سبدگردانی که فقط «جمع درآمدها» را منتشر می‌کند)؛
// nil یعنی با پارسرِ جدید بازخوانی نشده یا ستون هنوز مهاجرت نشده.
func (s *Service) a45HasOperatingSales(ctx context.Context, symbol string) any {
	pred, args := s.a45Pred(ctx, "symbol", symbol)
	rows, err := s.msQuery(ctx, "SELECT has_operating_sales FROM financial_statements "+
		"WHERE "+pred+" ORDER BY tracing_no DESC LIMIT 1", args)
	if err != nil || len(rows) == 0 || len(rows[0]) == 0 {
		return nil // مثلِ `except sqlite3.OperationalError: return None`
	}
	return rows[0][0]
}

// Ind4Exempt عینِ `fts_engine.ind4_exempt` — تک‌مرجعِ «سندِ فروش ندارد»:
// (نامِ طبقه درِ صنعت یا نامِ شرکت) **یا** (شاهدِ صورتِ مالی:
// has_operating_sales == 0). شاهدِ nil («بازخوانی‌نشده») معافیت نمی‌آورد؛
// `holdingsNa=false` یعنی کاربر کلیدِ کانفیگِ معافیت را خاموش کرده؛
// `precomputed` نقشۀ no_sales_symbols است تا اسکنِ کلِ بازار به‌ازای هر نماد یک
// کوئری نزند — nil یعنی «نقشۀ داده‌نشده»، mapِ خالی یعنی «هیچ نمادی معاف نیست».
func (s *Service) Ind4Exempt(ctx context.Context, symbol, sectorNorm string,
	holdingsNa bool, precomputed map[string]bool) bool {
	if !holdingsNa {
		return false
	}
	// اولِ صنعت (بی‌کوئری)، بعدِ نامِ شرکت از DB.
	if a45HoldingClassMatch(sectorNorm) {
		return true
	}
	if a45HoldingClassMatch("", s.a45CompanyNameOf(ctx, symbol)) {
		return true
	}
	if precomputed != nil {
		return precomputed[symbolid.Key(symbol)]
	}
	if s.market == nil { // conn=None درِ اوراکل: فقط شاهدِ نامی سنجیده می‌شود
		return false
	}
	i, ok := toI(s.a45HasOperatingSales(ctx, symbol))
	return ok && i == 0
}

// ── لایۀ ۴: فروش سالانه ─────────────────────────────────────────────────────

// AnnualizedSales عینِ `fts_engine.annualized_sales` — تک‌پیادۀ کارت، اسکرینر و
// bulk. `ref`/`series`/`profile`/`exempt` همان آرگومان‌هایِ اوراکل‌اند: nil یعنی
// «از بانک/طبقه بخوان». `exempt` سه‌مقدار است، چون `None` با «معاف نیست» یکی
// نیست — با nil حکم از `profile.kind == "holding"` می‌آید.
//
// خروجی ابرمجموعۀ کلیدهایِ هر دو مسیرِ پیشین است: annual_sales_mrl/bt،
// months_used، scale_factor، basis، reconciled، revenue_basis،
// operational_revenue_basis، na، ytd_sales_bt، scale_table (+ fs_unit/fs_unit_label/
// unit_unverified از خودِ سالانه‌سازی). برگشتِ nil یعنی «قابل محاسبه نبود».
func (s *Service) AnnualizedSales(ctx context.Context, symbol string,
	ref map[string]any, series [][]any, profile map[string]any,
	exempt *bool) (map[string]any, error) {
	if series == nil {
		pred, args := s.a45Pred(ctx, "symbol", symbol)
		raw, err := s.msQuery(ctx, "SELECT year, month, monthly_revenue, ytd_revenue, title "+
			"FROM monthly_sales WHERE "+pred+
			" AND ytd_revenue IS NOT NULL AND ytd_revenue>0 "+
			"ORDER BY year DESC, month DESC", args)
		if err != nil {
			return nil, err
		}
		kept := make([][]any, 0, len(raw))
		for _, r := range raw {
			// بندِ ۲.۱ سیاست: گزارشِ شرکتِ دیگر برای هیچ شاخصی قابل‌قبول نیست.
			if titleEntitySuffix(strOr(seriesCell(r, len(r)-1))) != "" {
				continue
			}
			kept = append(kept, r[:len(r)-1])
		}
		series = SeriesDedupeYm(kept, 3)
	} else {
		series = SeriesDedupeYm(series, 3)
	}
	refRow := ref
	var err error
	if refRow == nil {
		refRow, err = s.a45ReferenceAnnual(ctx, symbol)
		if err != nil {
			return nil, err
		}
	}
	var refUnit any
	if len(refRow) > 0 {
		refUnit = refRow["unit_norm"]
	}
	// مقیاس از خودِ ردیفِ مرجع، نه از ثابتِ ماژول (`fs_amount_mrl` بی‌واحد ⇒ nil).
	fsRev := a45FsAmountMrl(refRow, "revenue")
	fsUnitKnown := a45UnitIsValid(refUnit)
	prof := profile
	if len(prof) == 0 { // `profile or company_profile()` — dictِ خالی هم کاذب است
		prof = a45CompanyProfile("", "")
	}
	isNa := false
	if exempt == nil {
		isNa = strOr(prof["kind"]) == "holding"
	} else {
		isNa = *exempt
	}
	if isNa {
		return map[string]any{
			"annual_sales_mrl": 0.0, "annual_sales_bt": nil, "months_used": int64(0),
			"scale_factor":              0.0,
			"basis":                     a45BasisSalesNa,
			"reconciled":                true,
			"revenue_basis":             a45GetOrMissing(prof, "revenue_basis", ""),
			"operational_revenue_basis": false,
			"na":                        true,
		}, nil
	}
	kindIsOp := contains(a45OpBasisKinds, strOr(prof["kind"]))
	core := a45AnnualizeRows(series, fsRev,
		kindIsOp && fsRev != nil && *fsRev > 0 && fsUnitKnown, fsUnitKnown)
	if len(core) == 0 {
		return nil, nil
	}
	core["fs_unit"] = refUnit
	core["fs_unit_label"] = a45UnitLabel(refUnit)
	months, _ := toI(orZero(core["months_used"]))
	annual := toF(core["annual_sales_mrl"])
	scaleDenom := float64(max(months, 1))
	out := copyRow(core)
	out["annual_sales_bt"] = pyround.Round(a45NormalizeMrlToBtom(annual), 1)
	out["scale_factor"] = pyround.Round(12.0/scaleDenom, 4)
	out["revenue_basis"] = a45GetOrMissing(prof, "revenue_basis", "")
	out["na"] = false
	out["ytd_sales_bt"] = pyround.Round(a45NormalizeMrlToBtom(
		annual/max(12.0/scaleDenom, 1e-9)), 1)
	table := make([]any, 0, len(a45AnnualizationScale))
	for _, m := range a45AnnualizationScale {
		table = append(table, map[string]any{
			"months": int64(m), "factor": pyround.Round(12.0/float64(m), 2)})
	}
	out["scale_table"] = table
	return out, nil
}

// a45GetOrMissing عینِ `d.get(key, default)` — پیش‌فرض فقط برایِ **کلیدِ غایب**
// می‌نشیند؛ ارزشِ nilِ موجود همان nil می‌ماند (برخلافِ `or`).
func a45GetOrMissing(m map[string]any, key string, def any) any {
	if v, has := m[key]; has {
		return v
	}
	return def
}

// ── لایۀ ۴: داوری ───────────────────────────────────────────────────────────

const (
	a45ReasonNaExempt = "شرکت سرمایه‌گذاری/هلدینگ؛ نسبت فروش به ارزش بازار کاربرد ندارد (N/A)."
	a45ReasonNoMcap   = "دادهٔ ارزش بازار یا فروش سالانه برای محاسبه نسبت در دسترس نیست."
	a45ReasonNoSales  = "فروش سالانۀ راستی‌آزمایی‌شدۀ این نماد در دسترس نیست " +
		"(گزارش ماهانه یا صورت مالیِ واحددار نداریم)؛ نسبت فروش به " +
		"ارزش بازار سنجیده نمی‌شود — این «رد» نیست، «سنجیده نشد» است."
	a45MarginLabelGross = "حاشیهٔ سود ناخالص"
	a45MarginLabelNet   = "حاشیهٔ سود خالص (جایگزینِ مالی)"
	a45ReasonSalesWin   = "قبولی با نسبت فروش/ارزش‌بازار"
	a45ReasonPotWin     = "قبولی با پوشش پتانسیل سود"
	a45ReasonNeither    = "نه نسبت فروش و نه پوشش پتانسیل به حد نصاب نرسید."
	a45ReasonNoMargin   = "هیچ حاشیه‌ای (ناخالص یا جایگزین) برای این طبقه محاسبه نشد."
)

// Ind4Valuation عینِ `api/fundamental.ind4_valuation` — ۴الف فروش سالانه ÷ ارزش
// بازار (≥ آستانه) + ۴ب پتانسیل سود ناخالص ÷ ارزش بازار (≥ ۴۰٪)، با سه‌حالۀ
// exempt / no-sales / no-mcap و «مبنایِ جایگزین» (`net_margin_proxy`) برایِ
// طبقاتِ مالی که «سود ناخالص» ندارند.
//
// دو نکته که وکتورهایِ `valuation.json` (۲۸۰ کیس) ملاکشان‌اند:
//   * مقایسه با عددِ **خام** (`pot_raw`) است نه `potential_pct`ِ گرد شده (قاعدۀ
//     R4 درِ پلن) — با عددِ گرد شده پتانسیلِ ۳۹٫۹۶٪ «≥ ۴۰٪» می‌شد و کارت با
//     موتور نمی‌خواند؛
//   * حاشیۀ صفر `_f(...) or None` است ⇒ «حاشیه نداریم»، و
//     `_sane(sales_ratio, -1000, 1000)` بیرونِ بازه ⇒ null (بدون حذفِ بی‌صدا).
func Ind4Valuation(annual, gm map[string]any, marketCapRials any,
	th map[string]any, exempt bool) map[string]any {
	if len(th) == 0 {
		th = V10Thresholds(nil)
	}
	potentialMin := th["potential_min"]
	salesMin := th["sales_to_mcap_min"]
	if exempt {
		return map[string]any{
			"available": false, "na": true, "exempt": true, "pass": false,
			"potential_pass": false, "sales_pass": false, "rule_ref": "F-04",
			"reason": a45ReasonNaExempt,
		}
	}
	mcap := toF(marketCapRials)
	// سه‌حالۀ `ind4_vote` درِ fts_engine: «عددِ فروشِ سالانه نداریم» با «عدد
	// زیرِ آستانه است» یکی نیست — بی‌این، کارت نمادی را «رد» می‌شمرد که هیچ
	// شاهدِ مقیاس ندارد (شتهران، هلد لیان).
	noSales := len(annual) == 0 || toF(annual["annual_sales_mrl"]) <= 0
	if noSales || mcap <= 0 {
		gapCause := "market_cap"
		if noSales {
			gapCause = "annual_sales"
		}
		return map[string]any{
			"available": false, "na": true, "gap_cause": gapCause,
			"pass": nil, "potential_pass": false, "sales_pass": false,
			"mcap_ht": pyround.Round(mcap/1e13, 2),
			"potential_threshold": potentialMin, "sales_threshold": salesMin,
			"reason": a45ReasonNoMcap,
		}
	}
	annMrl := toF(annual["annual_sales_mrl"])
	annRial := annMrl * a45MrlToRial
	salesRatio := annRial / mcap
	var margin any // nil ⇒ «حاشیه‌ای محاسبه نشد» (کلیدِ صریح، نه حذف‌شده)
	marginBasis, marginLabel := "gross_margin", a45MarginLabelGross
	if len(gm) > 0 && !truthy(gm["na"]) {
		if f := toF(gm["margin_pct"]); f != 0 { // `_f(...) or None` ⇒ حاشیۀ صفر = «حاشیه نداریم»
			margin = f
		}
	} else if len(gm) > 0 && gm["net_margin_pct"] != nil {
		margin = toF(gm["net_margin_pct"])
		marginBasis, marginLabel = "net_margin_proxy", a45MarginLabelNet
	}
	var potRaw *float64
	if margin != nil {
		v := annRial * (toF(margin) / 100.0) / mcap * 100.0
		potRaw = &v
	}
	var potPct any
	if potRaw != nil {
		potPct = pyround.Round(*potRaw, 1)
	}
	salesPass := salesRatio >= toF(salesMin)
	potPass := potRaw != nil && *potRaw >= toF(potentialMin)
	var salesToMcap any
	if saneIn(salesRatio, -1000.0, 1000.0) {
		salesToMcap = pyround.Round(salesRatio, 2)
	}
	reason := a45ReasonNeither
	if margin != nil {
		switch {
		case salesPass:
			reason = a45ReasonSalesWin
		case potPass:
			reason = a45ReasonPotWin
		}
	} else {
		reason = a45ReasonNoMargin
	}
	var estGp any
	if margin != nil {
		estGp = a45Bt(annMrl * (toF(margin) / 100.0))
	}
	return map[string]any{
		"available": true, "mcap_ht": pyround.Round(mcap/1e13, 2),
		"annual_sales_bt":  annual["annual_sales_bt"],
		"months_used":      annual["months_used"],
		"scale_factor":     annual["scale_factor"],
		"annualize_basis":  annual["basis"],
		"reconciled":       annual["reconciled"],
		"fs_unit":          a45GetOrMissing(annual, "fs_unit", nil),
		"fs_unit_label":    a45GetOrMissing(annual, "fs_unit_label", nil),
		"unit_unverified":  truthy(annual["unit_unverified"]),
		"sales_to_mcap":    salesToMcap,
		"sales_threshold":  salesMin,
		"sales_pass":       salesPass,
		"margin_used_pct":  margin,
		"margin_basis":     marginBasis,
		"margin_label":     marginLabel,
		"est_gross_profit_bt": estGp,
		"potential_pct":    potPct,
		"potential_threshold": potentialMin,
		"potential_pass":   potPass,
		"rule_ref":         "F-04", "gate": "OR",
		"pass":             salesPass || potPass,
		"reason":           reason,
	}
}

// saneIn عینِ `_sane(v, lo, hi) is not None` — بیرونِ بازه ⇒ «نامعتبر» (بی‌حذفِ
// بی‌صدا: فراخواننده خودش null می‌گذارد).
func saneIn(x, lo, hi float64) bool { return !(x < lo || x > hi) }

// ── لایۀ ۵: رژیمِ قیمت‌گذاری ────────────────────────────────────────────────

// دو فهرستِ اوراکل (MANDATORY_PRICING_TOKENS / FREE_PRICING_TOKENS).
var a45MandatoryPricingTokens = []string{
	"خودرو", "نقلیه موتور", "قند و شکر", "لاستیک",
	"شوینده", "نیروگاه", "عرضه برق", "تولید برق", "توزیع برق", "بیمه",
}
var a45FreePricingTokens = []string{
	"سیمان", "آهک", "شیمیایی", "پتروشیمی", "فلزات", "کانه", "کانی", "کاشی", "سرامیک", "شیشه",
	"فرآورده‌های نفتی", "نفت", "زغال سنگ", "معادن", "محصولات فلزی",
	"مس", "فولاد", "سرب و روی", "رایانه", "اطلاعات", "نرم افزار",
}

// a45SectorCuts عینِ سه پیشوندِ «به جز …» درِ `sector_core`.
var a45SectorCuts = []string{"به جز", "به استثنا", "به حذف"}

// a45BankTokens عینِ چهار نوشتارِ استثنایِ بانک درِ اوراکل (دو نوشتارِ ک/ك و دو
// نوشتارِ ی/ي — «بانك» با k عربی درِ نامِ صنعتِ تابلو نشسته است).
var a45BankTokens = []string{"بانک", "بانك", "اعتباری", "اعتباري"}

// a45SectorCore عینِ `fts_engine.sector_core`: تطبیق رویِ «هستۀ» برچسبِ صنعت، بی
// بندِ «به جز …» — وگرنه استثنایِ داخلِ نام، خودِ نام را دستوری می‌کند.
func a45SectorCore(sector string) string {
	s := normFa(sector)
	for _, cut := range a45SectorCuts {
		if i := strings.Index(s, cut); i > 0 {
			s = s[:i]
		}
	}
	return trimSpace(s)
}

// a45PricingMode عینِ `fts_engine.pricing_mode`: دستوری اولویت دارد، و اگر
// صنعتی در هر دو فهرست بیفتد احتیاطاً مردود است.
func a45PricingMode(sector string) string {
	s := a45SectorCore(sector)
	if s == "" {
		return "neutral"
	}
	for _, t := range a45MandatoryPricingTokens {
		if strings.Contains(s, normFa(t)) {
			return "mandatory"
		}
	}
	for _, t := range a45FreePricingTokens {
		if strings.Contains(s, normFa(t)) {
			return "free"
		}
	}
	return "neutral"
}

// a45DefaultTh عینِ DEFAULT_TH درِ fts_engine، به‌اندازۀ چیزی که این لایه
// می‌خواند. صفرِ `pharma_margin_exempt_min` یعنی استثنایِ دارو **خاموش** است
// (رأیِ مالکِ ۱۴۰۵-۰۷-۱۱: چنین آستانه‌ای درِ جزوه نیست).
var a45DefaultTh = map[string]float64{"pharma_margin_exempt_min": 0.0}

// a45Th عینِ `fts_engine._th`: آستانه از cfg، وگرنه پیش‌فرض؛ صفرِ عمدیِ کاربر
// («بدونِ گیت») حفظ می‌شود، برخلافِ `or DEFAULT` که صفر را بی‌صدا برمی‌گرداند.
func a45Th(cfg map[string]any, key string) float64 {
	raw, has := cfg[key]
	if !has {
		return a45DefaultTh[key]
	}
	f, ok := asFloat(raw)
	if !ok {
		return a45DefaultTh[key]
	}
	return f
}

const (
	a45LabelMandatory      = "قیمت‌گذاری دستوری"
	a45LabelFree           = "قیمت‌گذاری آزاد / بورس کالا"
	a45LabelNeutral        = "خنثی — نیازمند بررسی موردی"
	a45LabelOther          = "سایر"
	a45PharmaTpl           = "دارویی ممتاز (حاشیۀ ناخالص ≥ %.0f٪)"
	a45PharmaPlain         = "دارویی عادی (قیمت‌گذاری دستوری)"
	a45BankGrowthToken     = "بانک رشد درآمدی و ارزی"
	a45IndustryModeDefault = "Exclude_Mandatory_Pricing"
)

// a45CfgTokens عینِ `cfg.get(key) or DEFAULT` برایِ فهرست‌هایِ رشته‌ایِ کانفیگ
// (nil/فهرستِ خالی ⇒ فهرستِ جزوه).
func a45CfgTokens(cfg map[string]any, key string, def []string) []string {
	raw, has := cfg[key]
	if !has || isFalsy(raw) {
		return def
	}
	if lst := a45AsStringList(raw); len(lst) > 0 {
		return lst
	}
	return def
}

func a45AsStringList(v any) []string {
	switch x := v.(type) {
	case []string:
		out := make([]string, 0, len(x))
		return append(out, x...)
	case []any:
		out := make([]string, 0, len(x))
		for _, i := range x {
			out = append(out, strOr(i))
		}
		return out
	}
	return nil
}

// SectorFilter عینِ `fts_engine.sector_filter`: تفکیکِ تگِ صنعت به «قیمت‌گذاری
// آزاد/بورس کالا» و «قیمت‌گذاری دستوری»، شاملِ استثنایِ دارویی با GPM ≥ آستانهٔ
// cfg (پیش‌فرضِ خاموش) و بانکِ با رشدِ مثبتِ درآمدهای تسهیلاتی. رأیِ ۱۶:
// بی‌داده = خنثی، نه رد.
func SectorFilter(sector string, cfg map[string]any, marketCapRials,
	totalMarketCapRials any, gpm, salesGrowth *float64) map[string]any {
	if cfg == nil {
		cfg = map[string]any{}
	}
	s := a45SectorCore(sector)
	mandatory := a45NormList(a45CfgTokens(cfg, "mandatory_sectors", a45MandatoryPricingTokens), normFa)
	free := a45NormList(a45CfgTokens(cfg, "free_sectors", a45FreePricingTokens), normFa)

	mode := "neutral"
	hitMand, hitFree := []string{}, []string{}
	pharmaMin := a45Th(cfg, "pharma_margin_exempt_min")
	switch {
	case strings.Contains(s, "دارو") && pharmaMin > 0:
		if gpm != nil && *gpm >= pharmaMin {
			mode = "free"
			hitFree = []string{fmt.Sprintf(a45PharmaTpl, pharmaMin)}
		} else if gpm != nil {
			mode = "mandatory"
			hitMand = []string{a45PharmaPlain}
		} // بی‌gpm ⇒ خنثی با دو فهرستِ خالی (رأیِ ۱۶)
	case a45AnyTokenIn(a45BankTokens, s):
		if salesGrowth != nil && *salesGrowth > 0 {
			mode = "free"
			hitFree = []string{a45BankGrowthToken}
		} // وگرنه خنثی — رشدِ منفی یا بی‌داده بانک را رد نمی‌کند
	default:
		for _, t := range mandatory {
			if t != "" && strings.Contains(s, t) {
				hitMand = append(hitMand, t)
			}
		}
		for _, t := range free {
			if t != "" && strings.Contains(s, t) {
				hitFree = append(hitFree, t)
			}
		}
		switch {
		case len(hitMand) > 0:
			mode = "mandatory"
		case len(hitFree) > 0:
			mode = "free"
		default:
			mode = a45PricingMode(sector)
		}
	}

	// `str(cfg.get("industry_mode", DEFAULT))` — کلیدِ موجودِ با ارزشِ nil هم
	// رشته‌سازی می‌شود («None»)، پس `pyStr` و نه `strOr`؛ پایتون درِ این‌جا
	// default را نمی‌گذارد.
	rawMode, hasMode := cfg["industry_mode"]
	modeStr := a45IndustryModeDefault
	if hasMode {
		modeStr = pyStr(rawMode)
	}
	exclude := modeStr != "Rank_Only"
	share := 0.0
	if truthy(totalMarketCapRials) {
		share = toF(marketCapRials) / toF(totalMarketCapRials) * 100.0
	}
	label := a45LabelOther
	switch mode {
	case "mandatory":
		label = a45LabelMandatory
	case "free":
		label = a45LabelFree
	case "neutral":
		label = a45LabelNeutral
	}
	matched := hitMand // `hit_mand or hit_free`
	if len(matched) == 0 {
		matched = hitFree
	}
	pass := true
	if exclude {
		pass = mode != "mandatory"
	}
	return map[string]any{
		"verdict": mode, "label": label, "sector": sector,
		"matched_tokens":   matched,
		"fts_top_industry": len(hitMand) > 0 || len(hitFree) > 0,
		"pass":             pass,
		"exclusion_active": exclude,
		"market_share_pct": pyround.Round(share, 3),
	}
}

// a45PricingOutlook عینِ `_PRICING_OUTLOOK` — توضیحِ رژیم برایِ کارت.
var a45PricingOutlook = map[string]string{
	"free": "قیمت‌گذاری آزاد / بورس کالا / صادرات‌محور — نرخ از بازار می‌آید، پس " +
		"رشد فروش قابلِ اتکا به تورم ریالی نیست و باید با حجم ثابت شود.",
	"mandatory": "قیمت‌گذاری دستوری — نرخ توسط شورای رقابت/دولت تعیین میشود؛ " +
		"رشد فروش بدون مجوز افزایش نرخ عملاً ممکن نیست و افزایش حاشیه " +
		"مشمول مجوز است. استراتژی FTS این گروه را از سبد بیرون می‌گذارد.",
	"neutral": "سایر صنایع (غیردستوری) — نیازمند بررسی موردیِ نرخ محصول و مجوز " +
		"افزایش قیمت.",
}

// a45RegimeLabels عینِ نقشۀ `regime_label` درِ `ind5_industry` (برچسبِ کوتاه؛
// `label`ِ کاملِ جزوه درِ SectorFilter می‌آید).
var a45RegimeLabels = map[string]string{
	"free": "آزاد / بورس کالا", "mandatory": "دستوری", "neutral": "سایر صنایع",
}

// Ind5Industry عینِ `api/fundamental.ind5_industry`: تگِ صنعتِ آزاد/دستوری از
// دیکشنریِ fts_engine (بدونِ موازی‌سازی) + چشم‌انداز + برچسبِ رژیم + `rule_ref`.
// `gpm`/`salesGrowth` مثلِ مسیرِ اسکرینر پاس داده می‌شوند، چون استثنایِ دارویی و
// بانک هر دو به آن‌ها نگاه می‌کنند.
func Ind5Industry(sector string, cfg map[string]any, marketCapRials,
	totalMarketCapRials any, gpm, salesGrowth *float64) map[string]any {
	sec := SectorFilter(sector, cfg, marketCapRials, totalMarketCapRials, gpm, salesGrowth)
	verdict := strOr(sec["verdict"])
	outlook, has := a45PricingOutlook[verdict]
	if !has {
		outlook = a45PricingOutlook["neutral"] // `.get(verdict, _PRICING_OUTLOOK["neutral"])`
	}
	sec["outlook"] = outlook
	// درِ اوراکل این یکِ ایندکسِ مستقیمِ dict است و برایِ داوریِ دیگری جز سه
	// رژیمِ ممکن هرگز نمی‌رسد؛ بی‌پرسشِ غایب رشتهٔ خالی می‌ماند (نه panic).
	sec["regime_label"] = a45RegimeLabels[verdict]
	sec["rule_ref"] = "F-05"
	return sec
}

// ── دروازۀ صنایعِ دستی (Include/Exclude) ─────────────────────────────────────

// NormIndustryList عینِ `api/fundamental.norm_industry_list`: فهرستِ صنایعِ
// پانل ← لیستِ نرمال‌شده. ویرگولِ لاتین و فارسی («،») هر دو جداکننده‌اند؛
// فاصله‌ها trimmed؛ و «ی/ک» عربی به فارسی برمی‌گردد تا «پتروشیمی» با
// «پتروشیمی» (ي عربی) یکی شود. ترتیبِ خروجی ترتیبِ نخستینِ رؤیت و تکراری حذف.
func NormIndustryList(value any) []string {
	if value == nil {
		return []string{}
	}
	parts := []any{}
	switch x := value.(type) {
	case string:
		for _, p := range strings.Split(strings.ReplaceAll(x, "\u060c", ","), ",") {
			parts = append(parts, p)
		}
	case []string:
		for _, p := range x {
			parts = append(parts, p)
		}
	case []any:
		if isFalsy(x) {
			return []string{}
		}
		parts = append(parts, x...)
	default:
		return []string{} // `list(value or [])` رویِ چیزِ غیرقابل‌تکرار TypeError است
	}
	out := []string{}
	seen := map[string]bool{}
	for _, p := range parts {
		t := normFa(trimSpace(strOr(p)))
		if t != "" && !seen[t] {
			seen[t] = true
			out = append(out, t)
		}
	}
	return out
}

// IndustryGate عینِ `api/fundamental.industry_gate`: حالتِ Include/Exclude رویِ
// فهرستِ دستیِ صنایع — جدا از رژیمِ قیمت‌گذاری. تطبیق «زیررشته» است چون
// sector_name کاملِ تابلو طولانی‌تر از برچسبِ پانل است («فلزات اساسی» ⊃ «فلزات»).
// آرگومانِ `sec` درِ اوراکل هرگز خوانده نمی‌شود، پس اینجا هم نمی‌آید.
func IndustryGate(sector string, cfg map[string]any) map[string]any {
	if cfg == nil {
		cfg = map[string]any{}
	}
	raw := cfg["industry_mode"]
	if isFalsy(raw) {
		raw = a45IndustryModeDefault
	}
	mode := trimSpace(pyStr(raw))
	s := normFa(sector)
	include := NormIndustryList(cfg["include_industries"])
	exclude := NormIndustryList(cfg["exclude_industries"])
	res := map[string]any{
		"active":  mode == "Exclude_Industries" || mode == "Include_Industries",
		"mode":    mode,
		"pass":    true,
		"matched": []string{},
		"reason":  "",
		"include": include,
		"exclude": exclude,
	}
	if !res["active"].(bool) {
		return res
	}
	if mode == "Include_Industries" {
		hits := a45SubstringHits(include, s)
		res["matched"] = hits
		res["pass"] = len(hits) > 0
		if len(hits) == 0 {
			res["reason"] = "صنعت «" + a45DashOrSector(sector) +
				"» در فهرستِ شاملِ پنل نیست — حذف خودکار"
		}
		return res
	}
	hits := a45SubstringHits(exclude, s)
	res["matched"] = hits
	if len(hits) > 0 {
		res["pass"] = false
		res["reason"] = "صنعت «" + a45DashOrSector(sector) +
			"» در فهرستِ مستثنیِ پنل است — حذف خودکار"
	}
	return res
}

// a45SubstringHits عینِ `[t for t in lst if t in s]` — ترتیبِ فهرستِ پانل حفظ
// می‌شود، نه ترتیبِ وقوعِ درِ نامِ صنعت.
func a45SubstringHits(lst []string, s string) []string {
	hits := []string{}
	for _, t := range lst {
		if strings.Contains(s, t) {
			hits = append(hits, t)
		}
	}
	return hits
}

// a45DashOrSector عینِ `sector or "—"` درِ پیامِ علت (بی‌صنعت ⇒ خطِ em).
func a45DashOrSector(sector string) string {
	if sector == "" {
		return "—"
	}
	return sector
}

// ── شکاف‌هایِ داده (کمکِ evaluate_v10؛ خودِ ارزیاتور مالِ یکپارچه‌ساز است) ───

const (
	a45MsGapHint = "با گرفتنِ دیتابیس تازهٔ کدال (دکمهٔ «دیتابیس کدال» در جدول غربالگری) " +
		"گزارش‌های ماهانهٔ جاافتاده اضافه می‌شود."
	a45Gap1bWhy        = "رشد ریالی محاسبه نشد تا رشد تولیدی بررسی شود."
	a45Gap1bFix        = "با همگام‌سازیِ گزارش فعالیت ماهانه (مخرجِ همان دورهٔ سال قبل) " +
		"این محور ساخته می‌شود."
	a45Gap1bMissingFix = "گزارش ماهانهٔ سال قبل لازم است."
	a45Gap2NaWhy       = "مبنایِ غیرتلفیقیِ سه‌سالهٔ کامل موجود نیست."
	a45Gap2NaFix       = "این شکاف با گرفتنِ دیتابیسِ تازهٔ کدال بسته نمی‌شود: " +
		"صورتِ سود و زیانِ غیرتلفیقیِ آن سال‌ها منتشر نشده است."
	a45Gap2Fix         = "با گرفتنِ دیتابیس تازهٔ کدال، صورت‌های ۱۲ماههٔ سال‌های " +
		"قدیمی‌ترِ همین نماد اضافه می‌شود."
	a45Gap2SoftFix     = "با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود."
	a45Gap3Why         = "سود ناخالصِ سالِ مرجع در کدال نیست."
	a45Gap3Fix         = "با همگام‌سازی کدال بررسی مجدد می‌شود."
	a45Gap4UnitWhy     = "واحدِ پولِ ردیفِ مرجعِ کدال اعلام نشده، پس مقیاسِ این عدد " +
		"راستی‌آزمایی نشد (گیتِ واحد بی‌شاهد اجرا شد)."
	a45Gap4UnitFix     = "با همگام‌سازیِ تازهٔ کدال، ستونِ واحدِ همان صورتِ مالی " +
		"پر می‌شود و مقایسه برقرار می‌گردد."
	a45Gap4ReconcileWhy = "سالانه‌سازی ×۱۲÷م با گیتِ fts_engine سازگار نشد؛ " +
		"فروش سالانهٔ کدال جانشین شد."
	a45Gap4ReconcileFix = "گزارش‌های ماهانهٔ کاملِ همان سال مالی لازم است."
)

// V10DataGaps عینِ `api/fundamental.v10_data_gaps` (کمکِ `evaluate_v10`): هر
// لایه‌ای که «قابل محاسبه نبود» شد + راه‌حلِ عملیِ بستنِ شکاف، با هشت شاخه. این
// فهرست دلیلِ وجودِ «۰ امتیاز» را از «۰ امتیازِ واقعی» جدا می‌کند، تا کاربر نداند
// شاخص رد شده یا داده کم است. شاخه‌هایِ ۲ و ۳ و ۵ و ۶ بر `elif`هایِ اوراکل
// نشسته‌اند، پس یکِ داوریِ تازه درِ هر محور ساخته نمی‌شود.
func V10DataGaps(res map[string]any) []map[string]any {
	ind := a45SubMap(res, "indicators")
	l1 := a45SubMap(ind, "1")
	g := a45SubMap(l1, "monetary")
	v := a45SubMap(l1, "volume")
	e := a45SubMap(ind, "2")
	val := a45SubMap(ind, "4")
	m := a45SubMap(ind, "3")
	ann := a45SubMap(val, "annual")
	gaps := []map[string]any{}

	if truthy(g["data_gap"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۱الف", "axis": "1a_monetary_growth",
			"why": a45Or(g["reason"], ""),
			"fix": a45Or(g["remediation"], a45MsGapHint),
		})
	}
	if strOr(v["basis"]) == "unavailable" {
		// «unavailable» یعنی پایۀ ۱الف ساخته نشد تا ۱ب رویش سوار شود — نه اینکه
		// کدال اصلاً مقدارِ فیزیکی منتشر نمی‌کند؛ علتِ واقعی از v["reason"].
		gaps = append(gaps, map[string]any{
			"layer": "۱ب", "axis": "1b_physical_volume",
			"why": a45Or(v["reason"], a45Gap1bWhy), "fix": a45Gap1bFix,
		})
	} else if truthy(v["data_gap"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۱ب", "axis": "1b_physical_volume",
			"why": a45Or(v["reason"], ""), "fix": a45Gap1bMissingFix,
		})
	}
	if truthy(e["na"]) {
		// N/A با «شکافِ داده» یکی نیست: این شکاف با همگام‌سازی بسته نمی‌شود
		// (رأیِ ۱۳ + جزوۀ ص ۴) — یا صنعت بیمه است و لایه اصلاً اجرا نمی‌شود.
		gaps = append(gaps, map[string]any{
			"layer": "۲", "axis": "2_eps_trend", "na": true,
			"why": a45Or(e["reason"], a45Gap2NaWhy), "fix": a45Gap2NaFix,
		})
	} else if truthy(e["data_gap"]) {
		avail, _ := toI(a45Or(e["available_periods"], int64(0)))
		req, _ := toI(a45Or(e["years_required"], int64(3)))
		gaps = append(gaps, map[string]any{
			"layer":             "۲",
			"axis":              "2_eps_trend",
			"why":               a45Or(e["reason"], ""),
			"available_periods": avail,
			"required_periods":  req,
			"partial":           truthy(e["partial"]),
			"fix":               a45Gap2Fix,
		})
	} else if truthy(e["soft_gap"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۲", "axis": "2_eps_trend",
			"why": a45Or(e["reason"], ""), "fix": a45Gap2SoftFix,
		})
	}
	if truthy(m["na"]) {
		// شاخص ۳ هیچ‌وقت درِ این فهرست نبود؛ رایج‌ترین سلولِ خالیِ جدول (حاشیۀ
		// ناخالص) بی‌هیچ توضیحی می‌ماند. ind3 علت را در سه حالت جدا کرده است.
		gaps = append(gaps, map[string]any{
			"layer": "۳", "axis": "3_gross_margin",
			"why": a45Or(m["reason"], a45Gap3Why),
			"fix": a45Or(m["remediation"], a45Gap3Fix),
		})
	}
	if truthy(ann["unit_unverified"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۴", "axis": "4_sales_to_mcap",
			"why": a45Gap4UnitWhy, "fix": a45Gap4UnitFix,
		})
	} else if isStrictFalse(ann["reconciled"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۴", "axis": "4_sales_to_mcap",
			"why": a45Gap4ReconcileWhy, "fix": a45Gap4ReconcileFix,
		})
	}
	return gaps
}

// a45Or عینِ `x or y` — ارزشِ کاذب (از جمله '' و ۰ و None) به پیش‌فرض می‌رسد.
func a45Or(v any, def any) any {
	if isFalsy(v) {
		return def
	}
	return v
}

// isStrictFalse عینِ `x is False`: nil («سنجیده نشد») با false («سازگار نشد»)
// یکی نیست؛ شاخۀ سالانه‌سازی فقط با falseِ واقعی باز می‌شود.
func isStrictFalse(v any) bool {
	b, ok := v.(bool)
	return ok && !b
}

// a45SubMap عینِ `(parent.get(key) or {})` — نه صفرِ ساختگی، نه کرش رویِ nil.
func a45SubMap(m map[string]any, key string) map[string]any {
	if len(m) == 0 {
		return map[string]any{}
	}
	sub, ok := m[key].(map[string]any)
	if !ok || len(sub) == 0 {
		return map[string]any{}
	}
	return sub
}
