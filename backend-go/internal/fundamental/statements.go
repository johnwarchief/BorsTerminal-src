package fundamental

// پورتِ لایۀ «صورت‌های مالی» از fts_engine.py: `annual_statements` (:801-873)،
// `pick_reference` (:943-1000)، `reference_annual` (:1002-1024)،
// `normalize_mrl_to_btom` (:1027-1035)، `row_conflicts` (:570-600)،
// `_is_audited`/`_is_amendment` (:548/:566)، `margin_reference` (:1531-1546)،
// `gross_margin` (:1569-1621) و `company_name_of` (:1868-1884)، به‌همراهِ
// همان تکه‌هایِ `codal_units` که این لایه می‌خواند (`is_valid`/`label`/`SCALES`/
// `RIAL_PER_BTM`).
//
// معماری: داورِ این فایل وکتورهایِ پایتون‌ساختِ `testdata/vectors/statements.json`
// است (اوراکل رویِ همان فیکسچرِ یخ‌زدۀ تسکِ ۱ نوشته، کپیِ فقط‌خواندنی). هیچ
// expectation دستی درِ آزمون نیست؛ هیچ شاخه‌ای هم برایِ سبز شدن «خاص» نمی‌شود —
// «سالانہ ندارد» و «سود ناخالص ندارد» دو شاخۀ واقعیِ همان فیکسچرند.
//
// قیدهایِ شکست‌پذیرِ همین لایه (بندِ ۲.۳ و P-2/P-4 سیاست):
//   * «سالانہ بودن» داوریِ Python است (`period.EffectiveMonths`)، نه ستونِ خام؛
//     SQL فقط پیش‌فیلترِ «حداکثرِ ممکن» است و پنجره عمداً بزرگ خوانده می‌شود.
//   * یکِ سالِ مالی = یکِ صورتِ مالی؛ برنده با `statementRank` است، نه با ترتیبِ
//     پیشآمدِ SQLite (لایۀ انتخاب درِ reference.go نشسته و اینجا مصرف می‌شود).
//   * مقیاسِ پول از خودِ `unit_norm`ِ ردیف می‌آید؛ «بی‌واحد» با صفر یا «مثلِ بقیه
//     میلیون ریال است» جایگزین نمی‌شود.
//   * برچسبِ `basis` از پرچم‌ها ساخته می‌شود، نه از بریدنِ عنوان.
//   * هیچ آستانه‌ای اینجا وضع نشده: `threshold`/`optimal` فقط همان ورودی‌هایِ
//     فراخوان‌اند و `pass`/`optimal` با حاشیۀ **گردنشده** سنجیده می‌شوند.
//
// نام‌ها: توابعِ لایه exported‌اند (همان نام‌هایِ پایتون) و هر کمکیِ تازه
// `stmt`-پیشوند دارد تا با شش فایلِ دیگرِ همین پکیج هیچ‌وقت به هم نخورد
// (`contains` نمونهٔ زندهٔ همان برخورد است).

import (
	"context"
	"errors"
	"math"
	"sort"
	"strings"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// ── codal_units: تنها تکه‌هایی که این لایه می‌خواند ─────────────────────────
// عینِ `codal_units.SCALES`/`RIAL_PER_BTM` (چند ریال در هر یکِ عددِ ذخیره‌شده).
// مقیاسِ تازه‌ای که روزی به جدولِ پایتون بیافزاید، اینجا هم یکِ سطر است — هیچ
// consumer دومِ ضریب نمی‌نویسد (بندِ ۱ و ۳ سرِ codal_units.py).
var stmtUnitScales = map[string]float64{"mrl": 1_000_000.0, "btl": 10_000_000_000.0}

const stmtRialPerBtm = 1e10 // یک میلیارد تومان = 1e10 ریال (قاعدهٔ جزوه)

// stmtMrlToBtmFactor عینِ `MRL_TO_BTM_FACTOR = SCALES["mrl"] / RIAL_PER_BTM`
// = 1e-4. همین‌جا تقسیم می‌شود نه ثابتِ «0.0001»، تا اگر مقیاس عوض شد دو زبان
// یکی بمانند (و همان دودوییِ پایتون بنشیند).
var stmtMrlToBtmFactor = stmtUnitScales["mrl"] / stmtRialPerBtm

// stmtUnitLabels عینِ `codal_units._LABEL`؛ بی‌واحد → «واحد نامعلوم» (هیچ حدسی
// درِ رابط ساخته نمی‌شود، بندِ ۵ سرِ codal_units.py).
var stmtUnitLabels = map[string]string{"mrl": "میلیون ریال", "btl": "میلیارد تومان"}

const stmtUnknownUnitLabel = "واحد نامعلوم"

// stmtUnitValid عینِ `CU.is_valid(unit_norm)` — نقیضِ `PRESENT_SQL` درِ Python.
// کلیدهایِ SCALES رشته‌اند، پس هر مقدارِ غیررشته‌ای (None، عدد) بی‌واحد است.
func stmtUnitValid(v any) bool {
	s, ok := v.(string)
	if !ok {
		return false
	}
	_, known := stmtUnitScales[s]
	return known
}

// stmtUnitLabel عینِ `CU.label(unit_norm)` — `dict.get` با پیش‌فرض.
func stmtUnitLabel(v any) string {
	if s, ok := v.(string); ok {
		if lab, known := stmtUnitLabels[s]; known {
			return lab
		}
	}
	return stmtUnknownUnitLabel
}

// stmtNormMrlToBtom عینِ `normalize_mrl_to_btom` (:1027): ورودی **باید** میلیون
// ریال باشد؛ تبدیلِ خودِ ردیف از `fs_amount_mrl` می‌گذرد (که این لایه درِ همین
// وکتورها مصرف نمی‌کند).
func stmtNormMrlToBtom(v any) float64 { return toF(v) * stmtMrlToBtmFactor }

// ── پرچم‌هایِ عنوان (fts_engine:548 و :566) ─────────────────────────────────
// `_is_consolidated` درِ reference.go هست و اینجا مصرف می‌شود؛ این دو نبودند.

// stmtIsAudited عینِ `_is_audited`: «حسابرسی شده» با فاصلهٔ معمولی دارد و «نشده»
// ندارد. جست‌وجو رویِ `normFa` است، پس نوشتارِ عربی/فارسی و نیم‌فاصله رأیِ دوم
// نمی‌سازد — ولی خودِ الگویِ جست‌وجو «حسابرسی شده» است، پس عنوانِ
// «حسابرسی‌شده» (با نیم‌فاصله) بعدِ حذفِ نیم‌فاصله «حسابرسیشده» می‌شود و
// مطابقِ اوراکل **نه** خوانده می‌شود؛ این رفتارِ پایتون است، نه باگِ این فایل.
func stmtIsAudited(title string) bool {
	t := normFa(title)
	return strings.Contains(t, "حسابرسی شده") && !strings.Contains(t, "نشده")
}

// stmtIsAmendment عینِ `_is_amendment`.
func stmtIsAmendment(title string) bool {
	return strings.Contains(normFa(title), "اصلاحیه")
}

// ── row_conflicts (fts_engine:570-600) ──────────────────────────────────────
// هیچ آستانه‌ای وضع نمی‌شود و هیچ ردیفی کنار نمی‌رود: فقط برچسبِ تناقض رویِ ردیف
// می‌نشیند و درِ `reference_identity` (لایۀ بعدی) خوانده می‌شود.

// stmtRowConflicts عینِ `row_conflicts(period_end, title, period_months)`.
// درِ `annual_statements` آرگومانِ سوم `effective_months` است، نه ستونِ خام —
// همان چیزی که ردیفِ «۶ ماهه با period_months=12» را دیده‌بان می‌کند.
func stmtRowConflicts(periodEnd any, title string, periodMonths any) []any {
	out := []any{}
	tp := period.FromTitle(title)
	pe := period.Canonicalize(periodEnd)
	if tp != nil && *tp != "" && pe != nil && *pe != "" && *tp != *pe {
		out = append(out, "title_period")
	}
	tm := period.MonthsFromTitle(title)
	var pm *int
	if periodMonths != nil && trimSpace(pyStr(periodMonths)) != "" {
		// `int(x)` درِ try/except (TypeError, ValueError): رشتهٔ «۵٫۵» و None
		// هیچ‌کدام عدد نمی‌شوند و pm تهی می‌ماند، درست مثلِ `toI` بی‌ok.
		if n, ok := toI(periodMonths); ok {
			v := int(n)
			pm = &v
		}
	}
	if tm != nil && *tm != 0 && pm != nil && *pm != 0 && *tm != *pm {
		out = append(out, "title_months")
	}
	return out
}

// stmtMarginNeed عینِ `MARGIN_NEED` (:929): آنچه شاخص ۳ برایِ ساختنِ یکِ عدد
// لازم دارد. نبودِ هر دو ⇒ «قابل محاسبه نبود»، نه صفر.
var stmtMarginNeed = []string{"gross_profit", "revenue"}

// stmtRowCarries عینِ `row_carries(row, need)` (:933). `revenue` تنها ستونی است
// که «بودن»ش یعنی «> ۰» — مخرجِ کسر صفر حاشیه نمی‌سازد.
func stmtRowCarries(row map[string]any, need []string) bool {
	for _, k := range need {
		v := row[k]
		if v == nil {
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

// ── annual_statements (fts_engine:801-873) ──────────────────────────────────

// stmtFsColumns عینِ `FS_COLS` + `tracing_no` درِ همان کوئری — ترتیبِ ستون‌ها
// درِ پایتون محلِ unpack است؛ اینجا خواندنِ به‌نام است، ولی فهرست و همان
// «فقط‌خواندنی» بودن دست‌نخورده می‌ماند.
const stmtFsColumns = "period_end, period_months, title, revenue, gross_profit," +
	" operating_profit, net_profit, basic_eps, company_name, unit_norm, tracing_no"

// AnnualStatements عینِ `annual_statements`: صورت‌های مالیِ سالانۀ (۱۲ماهه) همان
// نماد، جدیدترین درِ ابتدا، یکی به ازای هر سالِ مالی.
//
// پنجره عمداً بزرگ است (`max(limit,1)*12+48`): پیش‌تر `limit*4` باعث می‌شد
// سالانۀ حسابرسی‌شدۀ کهنه‌تر هرگز دیده نشود و `reference_annual` به تنزل
// (تلفیقی/حسابرسی‌نشده) می‌غلتید. سقف از خودِ کوئری می‌آید، پس هزینه تقریباً
// صفر است. داوریِ «سالانہ بودن» با `period.EffectiveMonths` درِ Go است، چون
// ستونِ تهی از عنوان پر می‌شود و دورۀ گذار با ستونِ ۱۲ رد می‌شود.
func (s *Service) AnnualStatements(ctx context.Context, symbol string,
	requireAudit, excludeConsolidated bool, limit int) ([]map[string]any, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		// همان برگشتی که لایۀ چارت و `QuartersBody` زده‌اند (routes.go:49-56):
		// خطایِ *واقعیِ* بانک درِ کوئریِ بعدی خودش بالا می‌رود، پس این «بی‌داده»
		// جعلی نمی‌سازد.
		pred, args = "symbol = ?", []any{symbol}
	}
	// پنجره عمداً بزرگ است: `max(int(limit),1)*12+48` — عینِ
	// `fts_engine.annual_statements` (fts_engine.py:814). سقفِ ۱۲ (خودِ limit)
	// باعث می‌شد صورتِ مالیِ حسابرسی‌شدۀ کهنه‌تر از ردیفِ دوازدهم هرگز
	// دیده نشود و `reference_annual` به تنزل (تلفیقی/حسابرسی‌نشده) بغلتد.
	window := limit
	if window < 1 {
		window = 1
	}
	window = window*12 + 48
	query := "SELECT " + stmtFsColumns + " FROM financial_statements WHERE " +
		pred + " AND " + period.DatedSQL("") +
		// پیش‌فیلترِ SQL فقط «حداکثرِ ممکن» را نگه می‌دارد (بندِ ۲.۳ سیاست).
		" AND (period_months>=12 OR period_months IS NULL)" +
		" ORDER BY period_end DESC LIMIT ?"
	rows, err := s.rows(ctx, query, append(args, window))
	if err != nil {
		return nil, err
	}
	// یکِ سالِ مالی = یکِ صورتِ مالی؛ برنده با `statementRank` (لایۀ صفرِ دامنۀ
	// شرکت ← مبنا ← کامل‌بودن ← newest tracing_no)، نه ترتیبِ پیشآمدِ SQLite.
	type stmtYearEntry struct {
		rank rankTuple
		row  map[string]any
	}
	byYear := map[string]stmtYearEntry{}
	years := make([]string, 0, len(rows))
	for _, r := range rows {
		t := strOr(r["title"])
		months, monthsSrc := period.EffectiveMonths(r["period_end"], r["period_months"], t)
		if months == nil || *months < 12 {
			continue
		}
		if excludeConsolidated && isConsolidated(t) {
			continue
		}
		if requireAudit && !stmtIsAudited(t) {
			continue
		}
		yr := period.FiscalYear(r["period_end"])
		if yr == nil || *yr == "" {
			continue
		}
		other := titleEntitySuffix(t) != ""
		consolidated := isConsolidated(t)
		tn, _ := toI(orZero(r["tracing_no"]))
		cand := map[string]any{
			"period_end": r["period_end"], "fiscal_year": *yr,
			"period_months": *months, "months_source": monthsSrc, "title": t,
			"audited": stmtIsAudited(t), "consolidated": consolidated,
			"other_entity": other,
			"conflicts":    stmtRowConflicts(r["period_end"], t, *months),
			// مقیاسِ همین ردیف، از خودِ ردیف؛ `unit_valid` نقیضِ `PRESENT_SQL` است.
			"unit_norm": r["unit_norm"], "unit_valid": stmtUnitValid(r["unit_norm"]),
			"tracing_no":       r["tracing_no"],
			"company_name":     strOr(r["company_name"]),
			"amended":          stmtIsAmendment(t),
			"revenue":          stmtFloatOrNull(r["revenue"]),
			"gross_profit":     stmtFloatOrNull(r["gross_profit"]),
			"operating_profit": stmtFloatOrNull(r["operating_profit"]),
			"net_profit":       stmtFloatOrNull(r["net_profit"]),
			"basic_eps":        stmtFloatOrNull(r["basic_eps"]),
		}
		rank := statementRank(other, consolidated, rowCompleteness(cand), tn)
		cur, seen := byYear[*yr]
		if !seen || rank.cmp(cur.rank) < 0 {
			byYear[*yr] = stmtYearEntry{rank: rank, row: cand}
			if !seen {
				years = append(years, *yr)
			}
		}
	}
	// `sorted(by_year, reverse=True)`: سالِ مالی نزولی، و برش با `limit`ِ خام
	sort.Slice(years, func(i, j int) bool { return years[i] > years[j] })
	out := make([]map[string]any, 0, len(years))
	for _, yr := range years {
		out = append(out, byYear[yr].row)
		if len(out) >= limit {
			break
		}
	}
	return out, nil
}

// stmtFloatOrNull عینِ `_fn` (:1055) — «قابل‌سکوت»: None واقعی حفظ می‌شود، چون
// «درج نشده» بودنِ سودِ ناخالصِ بانک/صندوق معنا دارد و صفر کردنش شاخص ۳ را از
// «نامفهوم» به «۰٪» می‌برد. NaN هم None است (`x == x` درِ پایتون).
//
// تبدیل از تعریفِ یکتایِ `float()` می‌آید (`asFloat` درِ config.go): رقمِ یونیکد
// و زیرخط هم پذیرفته می‌شوند، پس EPSِ متنیِ «۱۲۵» مثلِ پایتون ۱۲۵ است و نه
// «بی‌داده» — وگرنه ردیف از نردبانِ EPS و از رتبه‌بندیِ ردیفِ مرجع می‌افتاد.
func stmtFloatOrNull(v any) any {
	f, ok := asFloat(v)
	if !ok || math.IsNaN(f) {
		return nil
	}
	return f
}

// ── pick_reference / reference_annual (fts_engine:943-1024) ─────────────────

// PickReference عینِ `pick_reference(rows, need)` — خالص روی هر فهرست ردیف، بی‌
// هیچ کوئری (همان تابعی که `bulk_scan` روی ردیف‌های ازپیش‌خوانده می‌زند).
//
// سلسلۀ‌مراتب: سالانۀ حسابرسی‌شدۀ غیرتلفیقی ← سالانۀ غیرتلفیقی ← سالانۀ اخیر.
// دو گذر، نه دو قاعده: با `need` اول هر سه پلّه با شرطِ «این عدد را دارد»
// جست‌وجو می‌شود و فقط اگر هیچ‌کدام نداشت همان پلّه‌ها بی‌آن شرط — بی‌این ترتیب
// پلۀ اول با یکِ ردیفِ تهی برنده می‌شد و گذرِ دوم هرگز دیده نمی‌شد (`وكادو`).
// قاعدۀ «هرگز» برای ردیفِ شرکتِ دیگر درِ هر سه پلّه هست: عددِ آن ردیف صورتِ
// مالیِ آن شرکت است، نه این نماد.
func PickReference(rows []map[string]any, need []string) map[string]any {
	type stmtCand struct {
		rank rankTuple
		fy   string
		row  map[string]any
	}
	byYear := map[string]stmtCand{}
	order := make([]string, 0, len(rows))
	for _, r := range rows {
		// `int(_f(x)) < 12`: بی‌عدد صفر می‌شود و رد می‌گردد؛ ۱۲٫۷ به ۱۲ می‌چسد.
		if stmtTruncInt(toF(r["period_months"])) < 12 {
			continue
		}
		yr := strOr(r["fiscal_year"])
		if yr == "" {
			continue
		}
		tn, _ := toI(orZero(r["tracing_no"]))
		rank := statementRank(stmtTruthy(r["other_entity"]), stmtTruthy(r["consolidated"]),
			rowCompleteness(r), tn)
		cur, seen := byYear[yr]
		if !seen || rank.cmp(cur.rank) < 0 {
			byYear[yr] = stmtCand{rank: rank, fy: yr, row: r}
			if !seen {
				order = append(order, yr)
			}
		}
	}
	cand := make([]stmtCand, 0, len(order))
	for _, yr := range order {
		cand = append(cand, byYear[yr])
	}
	// `sorted(..., key=fiscal_year, reverse=True)`ِ پایتون پایدار است: تساویِ سال
	// با ترتیبِ دیدنِ نخستین سال می‌ماند، پس SliceStable + کلیدِ یک‌جزئی.
	sort.SliceStable(cand, func(i, j int) bool { return cand[i].fy > cand[j].fy })

	tiers := []func(audited, consolidated bool) bool{
		func(a, c bool) bool { return a && !c }, // حسابرسی‌شدۀ غیرتلفیقی
		func(a, c bool) bool { return !c },      // غیرتلفیقی
		func(a, c bool) bool { return true },    // هر سالانۀ اخیر
	}
	// `if need` درِ پایتون یعنی فهرستِ پُر؛ `need=nil` و `need=[]` یکی‌اند
	// (هر دو falsy) و فقط یک گذر می‌سازند.
	passes := []bool{false}
	if len(need) > 0 {
		passes = []bool{true, false}
	}
	for _, requireNumbers := range passes {
		for _, want := range tiers {
			for _, c := range cand {
				r := c.row
				if stmtTruthy(r["other_entity"]) {
					continue
				}
				if !want(stmtTruthy(r["audited"]), stmtTruthy(r["consolidated"])) {
					continue
				}
				if requireNumbers && !stmtRowCarries(r, need) {
					continue
				}
				return r
			}
		}
	}
	return nil
}

func stmtTruthy(v any) bool { return !isFalsy(v) }

// stmtTruncInt مثلِ `int(x)` رویِ مقداری که قبلاً float شده (`_f`): درِ `pick_reference`
// بی‌عدد ⇒ ۰، پس ردیفِ بی‌دورۀ «سالانہ» نیست.
func stmtTruncInt(f float64) int64 {
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return 0
	}
	return int64(f)
}

// ReferenceAnnual عینِ `reference_annual(conn, symbol, need)`: یک پنجرۀ ۱۲ماهه
// خوانده می‌شود (بی‌ شرطِ حسابرسی و بی‌ شرطِ غیرتلفیقی — انتخابِ پلّه‌ها مالِ
// `PickReference` است) و داوری درِ همان تابعِ مشترک با `bulk_scan` انجام می‌شود.
func (s *Service) ReferenceAnnual(ctx context.Context, symbol string,
	need []string) (map[string]any, error) {
	rows, err := s.AnnualStatements(ctx, symbol, false, false, 12)
	if err != nil {
		return nil, err
	}
	return PickReference(rows, need), nil
}

// ── margin_reference / gross_margin (fts_engine:1531-1546 و :1569-1621) ─────

// MarginReference عینِ `margin_reference(conn, symbol, ref, rows)`: همان پلکان،
// با اولویتِ عددِ موجود. شرطِ «غیرتلفیقی» مالِ شاخص ۲ است، نه حاشیۀ سود.
//
// `rows` دو حال دارد و آن را حفظ کنید: nil یعنی «کوئری بزن» و برشِ خالیِ غیرnil
// یعنی «رویِ این ردیف‌های ازپیش‌خوانده بگرد» (`bulk_scan`) — درِ پایتون
// `if rows is not None` دقیقاً همین تفکیک است.
func (s *Service) MarginReference(ctx context.Context, symbol string,
	ref map[string]any, rows []map[string]any) (map[string]any, error) {
	if stmtRowCarries(ref, stmtMarginNeed) {
		return ref, nil
	}
	if rows != nil {
		if picked := PickReference(rows, stmtMarginNeed); len(picked) > 0 {
			return picked, nil
		}
		return ref, nil
	}
	picked, err := s.ReferenceAnnual(ctx, symbol, stmtMarginNeed)
	if err != nil {
		return nil, err
	}
	if len(picked) > 0 {
		return picked, nil
	}
	return ref, nil
}

// GrossMargin عینِ `gross_margin`: حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × ۱۰۰.
// `net_profit` و `operating_profit` درِ این شاخص هیچ نقشی ندارند (تأییدِ ممیزی
// v8: فرمول درست بود، **منبع** غلط). `minMargin`/`optimal` فقط می‌رسند و `pass`
// با حاشیۀ **گردنشده** سنجیده می‌شود، در حالی‌که `margin_pct` گردِ یک‌دهم است —
// اگر هر دو را با عددِ گردنشده می‌دادیم یکِ ردیفِ ۱۹٫۹۶ درِ آستانۀ ۲۰ رد می‌شد.
func (s *Service) GrossMargin(ctx context.Context, symbol string,
	minMargin, optimal float64, ref map[string]any,
	rows []map[string]any) (map[string]any, error) {
	row, err := s.MarginReference(ctx, symbol, ref, rows)
	if err != nil {
		return nil, err
	}
	if len(row) == 0 { // `if not row` درِ پایتون: None و {} هر دو بی‌جواب‌اند
		return nil, nil
	}
	rev := toF(row["revenue"])
	gp := row["gross_profit"]
	if rev <= 0 || gp == nil {
		return nil, nil // بانکی/مالی/صندوق — بهای تمام‌شده ندارد، نه صفر
	}
	gpF := toF(gp)
	margin := (gpF / rev) * 100.0
	audited := stmtTruthy(row["audited"])
	consolidated := stmtTruthy(row["consolidated"])
	parentOnly := audited && !consolidated
	// برچسبِ منبع از خودِ پرچم‌ها ساخته می‌شود، نه از بریدنِ عنوانِ کدال:
	// `title[:60]` جمله را وسطِ کلمه می‌برید و کاربر متنِ ناقص را دلیلِ داوری دید.
	src := "سالانهٔ حسابرسی‌شدهٔ شرکت اصلی"
	if !parentOnly {
		src = "تنزل منبع: "
		if consolidated {
			src += "تلفیقی"
		} else {
			src += "شرکت اصلی"
		}
		if audited {
			src += "ِ حسابرسی‌شده"
		} else {
			src += "ِ حسابرسی‌نشده"
		}
	}
	fy := trimSpace(strOr(row["fiscal_year"]))
	if fy != "" {
		src += " — سال مالی " + fy
	}
	return map[string]any{
		"margin_pct":        pyround.Round(margin, 1),
		"gross_profit_bt":   pyround.Round(stmtNormMrlToBtom(gpF), 1),
		"revenue_bt":        pyround.Round(stmtNormMrlToBtom(rev), 1),
		"period_end":        stmtFirstRunes(pyStr(row["period_end"]), 10),
		"basis":             src,
		"ref_tracing_no":    row["tracing_no"],
		"ref_company":       strOr(row["company_name"]),
		"fiscal_year":       stmtStrOrNil(fy),
		"unit":              row["unit_norm"],
		"unit_label":        stmtUnitLabel(row["unit_norm"]),
		"unit_valid":        stmtUnitValid(row["unit_norm"]),
		"source":            "کدال — صورت سود و زیان سالانه",
		"pass":              margin >= minMargin,
		"optimal":           margin >= optimal,
		"threshold":         minMargin,
		"optimal_threshold": optimal,
		// برچسبِ نمایشیِ طبقه از همان عددِ خامِ حکم (نه گردشده) — عینِ
		// `fts_engine.margin_tier` (1797-1812): ۵۰٪ دروازه نیست، فقط نام است.
		"margin_tier": stmtMarginTier(margin),
		// رقمِ فارسیِ «۱۰۰» از `faDigits` می‌آید (قیدِ گارد: ویرایشِ مستقیمِ رقم
		// درِ متن رقم را می‌دزدد) — خروجی عینِ رشتهٔ پایتون است.
		"formula": "(سود ناخالص ÷ درآمدهای عملیاتی) × " + faDigits("100"),
	}, nil
}

// stmtMarginTier عینِ `fts_engine.margin_tier`: نامِ نمایشیِ طبقه، نه دروازه.
func stmtMarginTier(pct float64) string {
	switch {
	case pct < 20:
		return "below_floor"
	case pct < 30:
		return "floor"
	case pct < 50:
		return "standard"
	default:
		return "good"
	}
}

// stmtFirstRunes برشِ `[:10]`ِ پایتون است: ده *نویسه*، نه ده بایت — یکِ تاریخِ
// با رقمِ فارسی ده نویسه دارد و بیست‌وچهار بایت.
func stmtFirstRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}

// stmtStrOrNil مثلِ `fy or None` درِ پایتون.
func stmtStrOrNil(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// ── company_name_of (fts_engine:1868-1884) ──────────────────────────────────

// CompanyNameOf عینِ `company_name_of(conn, symbol)`: نامِ شرکت از خودِ دیتابیس،
// از همان ردیفی که `company_name_map` برایِ کل بازار می‌دهد — «آخرین» دقیقاً
// `period.LatestOrderSQL` (دورۀ canonical اول، بی‌دوره آخر) و بعدِ `tracing_no DESC`،
// چون `ORDER BY period_end DESC`ِ خام ترتیبِ بی‌دوره را به SQLite واگذار می‌کرد.
//
// برخلافِ `QuartersBody` اینجا خطایِ بانک بلعیده می‌شود و رشتهٔ خالی برمی‌گردد:
// اوراکل صریحاً `except sqlite3.Error: return ""` دارد (:1881). خطایِ context
// (لغو/مهلت) همان‌طور بالا می‌رود، چون درِ پایتون SQLite error نیست و بلعیدنش
// «این نماد شرکت ندارد» جعلی می‌سازد.
func (s *Service) CompanyNameOf(ctx context.Context, symbol string) (string, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		if stmtIsCtxErr(err) {
			return "", err
		}
		return "", nil
	}
	query := "SELECT company_name FROM financial_statements WHERE " + pred +
		" AND company_name IS NOT NULL " +
		period.LatestOrderSQL("") + ", tracing_no DESC LIMIT 1"
	rows, err := s.rows(ctx, query, args)
	if err != nil {
		if stmtIsCtxErr(err) {
			return "", err
		}
		return "", nil // همان `except sqlite3.Error`
	}
	if len(rows) == 0 {
		return "", nil
	}
	// `(row[0] if row else "") or ""` — NULL درِ `IS NOT NULL` نمی‌آید، ولی تهیِ
	// واقعی هم رشتهٔ خالی است نه «None».
	return strOr(rows[0]["company_name"]), nil
}

func stmtIsCtxErr(err error) bool {
	return errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded)
}
