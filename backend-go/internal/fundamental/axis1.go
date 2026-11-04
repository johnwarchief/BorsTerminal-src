package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). What changes: لایۀ ۱
// از api/fundamental.py به Go می‌آید — ۱الف رشدِ ریالی (542-607)، ۱ب رشدِ تولیدی
// (618-695) با سه سطحِ شاهد، جفتِ فیزیکیِ `_physical_pair` (477-514)، رأیِ لایۀ ۱
// `axis1_pass` (732-751) و سه‌حالۀ پنج‌محوره `v10_axis_states` (701-729)، به‌علاوۀ
// تبدیل‌هایِ `_bt`/`_pct`/`_real_growth`/`_num_or_none` (156-236). Invariants: هیچ
// داوریِ دومی ساخته نمی‌شود؛ «بی‌داده ≠ رد» با `data_gap` اعلام می‌شود و `passes`
// عمداً bool می‌ماند (امتیاز شمارشِ Trueهاست) ولی حالت‌هایِ بی‌نظر درِ
// `v10_axis_states` nil می‌شوند. پهنای رشد **دادهٔ نمایشی** است، نه دروازۀ امتیاز
// (رأیِ مالک ۱۴۰۵-۰۷-۱۱). Lockstep: رشته‌هایِ کاربر-دیدنی این فایل عینِ اوراکل‌اند
// (با گاردِ هجنگ/رقم راستی‌آزمایی شده‌اند)؛ `ax1MrlToBtmFactor` ←
// fts_engine.MRL_TO_BTM_FACTOR ← codal_units SCALES['mrl']/RIAL_PER_BTM = 1e-4.
// Guard: axis1_test.go رویِ testdata/vectors/indicators.json که اوراکلِ پایتون
// ساخته (ind1a/ind1b/axis1/states/profile) و فیکسچرِ کامیت‌شدۀ testdata/fixture.
// Rollback: revertِ همین کامیت.
//
// تابع‌هایِ لایۀ series را از فایلِ همسایه می‌خوانم، نه از نسخۀ دومِ خودم:
// `SeriesYtdDenominator` و `SeriesGrowthBreadth` و `(*Service).MonthlySeries` و
// `(*Service).msQuery` (series.go). تنها تکرارِ من `ax1MsSeries` است: امروز روی
// دادهٔ واقعی هم‌ارزِ `SeriesMsRows` است (هر دو صفرِ واقعی را نگه می‌دارند —
// `seriesNumOrNull` دیگر صفر را nil نمی‌کند، پس آن ادعایِ قدیمی دیگر نیست)،
// ولی برای سال/ماهِ رشته‌ای یکی نیستند: `ax1IntOf` مثلِ `int(float(v))` درِ
// پایتون سرِ اعشار می‌اندازد و `seriesInt` (از راهِ `toI`) فقط رشتهٔ «عددِ
// صحیح» را می‌پذیرد. نشانۀ `TODO(unify)` پایینِ همان تابع است.

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strings"

	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// ax1MrlToBtmFactor عینِ fts_engine.MRL_TO_BTM_FACTOR (fts_engine.py:1024) =
// CU.SCALES["mrl"] / CU.RIAL_PER_BTM = 1e6/1e10 = 1e-4 — قاعدۀ جزوه: حذفِ ۴ رقمِ
// سمتِ راست (میلیونِ ریال → میلیاردِ تومان). `api/fundamental.py:94` همین را
// BT_FACTOR می‌نامد.
const ax1MrlToBtmFactor = 1e-4

// ── رشته‌هایِ کاربر-دیدنی (verbatim؛ هیچ‌کدام جایِ دومِ ترجمه ندارند) ──────────
const (
	// ax1SourceMs: بندِ ۵ مأموریت — منبعِ هر شاخص درِ خروجی می‌نشیند.
	ax1SourceMs = "کدال — گزارش فعالیت ماهانه"

	// ax1MsGapHint عینِ _MS_GAP_HINT (api/fundamental.py:538-539).
	ax1MsGapHint = "با گرفتنِ دیتابیس تازهٔ کدال (دکمهٔ «دیتابیس کدال» در جدول غربالگری) " +
		"گزارش‌های ماهانهٔ جاافتاده اضافه می‌شود."

	ax1ReasonNoSeries = "هیچ گزارش فعالیت ماهانه‌ای با فروش تجمیعی ثبت نشده است."
	ax1ReasonBadYtd   = "تجمیعیِ آخرین گزارش ماهانه صفر یا نامعتبر است."
	ax1ReasonNoPrev   = "فروش تجمیعیِ همان دورۀ سال قبل در کدال ثبت نشده؛ " +
		"مقایسهٔ سال‌به‌سال ممکن نیست."

	// جدولِ `monthly_sales` ستونِ واحدِ پول **ندارد**؛ این صراحتاً اعلام می‌شود،
	// نه اینکه میلیون‌ریال فرض شود.
	ax1UnitNoteGap = "جدولِ فروشِ ماهانه ستونِ واحدِ پول ندارد؛ مقیاسش تنها " +
		"با فروشِ سالانۀ کدال (گیتِ واحدِ مشکوک) سنجیده می‌شود"
	ax1UnitNoteOk = "تجمیعیِ میلیونِ ریال از جدولِ بدونِ ستونِ واحد؛ مخرج هم از " +
		"همان جدول یا ستون «مقایسهٔ دورهٔ مشابه» می‌آید"

	ax1ReasonNoMonetary = "رشد ریالی محاسبه نشد؛ رشد تولیدی هم قابل بررسی نیست."
	ax1ReasonQtyFail    = "فروش تولیدی کم شده یا ثابت مانده؛ رشد ریالی فقط از افزایش نرخ آمده است."
	ax1ReasonNoBench    = "شاخص مرجع افزایش نرخ موجود نیست."

	// `%+.1f` و `%.0f` رقمِ ASCII می‌سازند (همان چیزی که اوراکل می‌نویسد) و `٪`
	// همان U+066A است، نه پرسانِ لاتین.
	ax1DetailQty      = "ستون %s در گزارش فعالیت ماهانهٔ کدال"
	ax1DetailBench    = "تعدیل رشد اسمی با شاخص افزایش نرخ %.0f٪ و پهنای رشد ماهانه"
	ax1ReasonRealFail = "رشد اسمی %+.1f٪ کمتر از مبنای افزایش نرخ %.0f٪ است؛ " +
		"رشد واقعی منفی است (فقط قیمت بالا رفته)."
	ax1NoteBreadthFmt = "فقط %d از %d ماهِ سپری‌شده بهتر شده — رشد حجم فراگیر نیست."
)

// ax1VolNowKeys / ax1VolPrevKeys عینِ _VOL_NOW_KEYS و _VOL_PREV_KEYS
// (api/fundamental.py:471-474). ترتیبِ فهرست اولویتِ ستون است، پس دست‌نخورده
// می‌ماند (next()ِ پایتون نخستینِ تطبیق را می‌گیرد).
var (
	ax1VolNowKeys = []string{"ytd_volume", "ytd_quantity", "ytd_tonnage", "ytd_qty",
		"ytd_weight", "ytd_production", "ytd_sales_qty"}
	ax1VolPrevKeys = []string{"ytd_volume_prev", "ytd_quantity_prev", "ytd_tonnage_prev",
		"ytd_qty_prev"}
)

// ── تبدیل‌هایِ عددی (api/fundamental.py:156-220) ─────────────────────────────

// ax1Bt مثلِ `_bt`: میلیونِ ریال → میلیاردِ تومان با round(x*BT_FACTOR, 1). گرد
// از pyround می‌خواند (نیم‌به‌زوجِ CPython)، نه از math.Roundِ نیم‌به‌بالا.
func ax1Bt(valueMillionRials any) float64 {
	return pyround.Round(toF(valueMillionRials)*ax1MrlToBtmFactor, 1)
}

// ax1Pct مثلِ `_pct` (199-204): رشد٪ با محافظِ مخرجِ صفر. nil یعنی «محاسبه نشد»،
// نه «صفر درصد» — پس نوعِ بازگشتی any است تا شاخهٔ nilِ پایتون حفظ شود.
func ax1Pct(new, old any) any {
	o := toF(old)
	if o <= 0 {
		return nil
	}
	return pyround.Round((toF(new)/o-1.0)*100.0, 1)
}

// ax1RealGrowth مثلِ `_real_growth` (207-211): حذفِ اثرِ قیمت از رشدِ اسمی
// (فیشرِ فشرده). بی‌رشدِ اسمی ⇒ nil.
func ax1RealGrowth(nominalPct, pricePct any) any {
	if nominalPct == nil {
		return nil
	}
	return pyround.Round(((1.0+toF(nominalPct)/100.0)/(1.0+toF(pricePct)/100.0)-1.0)*100.0, 1)
}

// ax1NumOrNull عینِ `_num_or_none` (214-220): عدد یا nil — «داده نیست» هیچ‌وقت
// صفر نمی‌شود (برخلافِ toF)، ولی صفرِ واقعی هم صفر می‌ماند (همان قاعدۀ
// `seriesNumOrNull` درِ series.go؛ آن هم امروز صفر را nil نمی‌کند).
func ax1NumOrNull(v any) any {
	if f, ok := asFloat(v); ok {
		return f
	}
	return nil
}

// ax1IntOf مثلِ `int(_f(v))` درِ خطوطِ 189/465/504/507: اعشار سرِ اعشار چیده
// می‌شود و بی‌عدد ⇒ ۰ (همان صفرِ فالتِ toF). تبدیلِ Go هم مثلِ int()ِ پایتون به
// سمتِ صفر قرب می‌کند، پس عددِ منفی یکی می‌ماند.
func ax1IntOf(v any) int64 {
	f := toF(v)
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return 0
	}
	return int64(f)
}

// ax1Cell مثلِ r[i] برایِ ردیف‌هایِ کوتاهِ بی‌کرشِ پایتون (شرطِ len(r) > i درِ
// خطوطِ 191-194 و 504).
func ax1Cell(r []any, i int) any {
	if i < 0 || i >= len(r) {
		return nil
	}
	return r[i]
}

// ax1MsSeries عینِ `_ms_series` (177-196): هیچ داوریِ تازه‌ای اینجا ساخته نمی‌شود،
// فقط همان شش ستون با همان تبدیل‌ها.
//
// TODO(unify): شاخۀ series — این تابع و `SeriesMsRows` (series.go:144) امروز روی
// دادهٔ واقعی یکی می‌دهند: صفرِ واقعی درِ هر دو می‌ماند (نه nil) و سال/ماه از
// SQLite عددِ صحیح می‌آید. تفاوتِ باقی‌مانده فقط رشتهٔ سال/ماه است: `ax1IntOf`
// مثلِ `int(float(v))` درِ پایتون سرِ اعشار می‌اندازد، `seriesInt` (از راهِ `toI`)
// فقط رشتهٔ «عددِ صحیح» را می‌پذیرد. یکی کردنشان یعنی یکی کردنِ قاعدۀ سال/ماه.
func ax1MsSeries(series [][]any) []map[string]any {
	out := make([]map[string]any, 0, len(series))
	for _, r := range series {
		out = append(out, map[string]any{
			"year":             ax1IntOf(ax1Cell(r, 0)),
			"month":            ax1IntOf(ax1Cell(r, 1)),
			"monthly_revenue":  ax1CellOrNull(r, 2),
			"ytd_revenue":      ax1CellOrNull(r, 3),
			"ytd_revenue_prev": ax1CellOrNull(r, 4),
			"period_end":       ax1Cell(r, 5),
		})
	}
	return out
}

// ax1CellOrNull مثلِ `_num_or_none(r[i]) if len(r) > i else None`.
func ax1CellOrNull(r []any, i int) any {
	if i >= len(r) {
		return nil
	}
	return ax1NumOrNull(r[i])
}

// ax1Dict مثلِ `(x or {})` وقتی قرار است رویِ آن `.get()` زده شود: بی‌نقشه یا
// نقشۀ تهی ⇒ نقشۀ تهی (خواندنِ کلیدِ نبود ⇒ nil، همان Noneِ پایتون).
func ax1Dict(v any) map[string]any {
	if m, ok := v.(map[string]any); ok && len(m) > 0 {
		return m
	}
	return nil
}

// ax1Period مثلِ `"%02d/%d" % (month, year)` — جداکننده U+002F است و رقمِ ASCII
// می‌آید (اوراکل همین را درِ `period` می‌نویسد؛ رابطِ کاربر بعداً فارسی می‌کند).
func ax1Period(month, year int64) string {
	return fmt.Sprintf("%02d/%d", month, year)
}

// ax1DefaultProfile عینِ `company_profile()`ِ بی‌آرگومان (fts_engine.py:1650) —
// یعنی صنعتِ خالی و نامِ خالی که به طبقۀ «تولیدی/عمرانی» می‌رسد.
//
// TODO(unify): شاخۀ profile — این فقط شاخۀ «پیش‌فرضِ بی‌آرگومان»ِ همان تابع است؛
// طبقه‌بندیِ کامل (توکن‌های صندوق/مالی/خدمات/هلدینگ) درِ فایلِ همسایۀ
// classification زندگی می‌کند و باید تنها همان یک پیاده‌سازی بماند. سنجش:
// فیکسچرِ اوراکل برایِ نمادِ بی‌صنعت دقیقاً همین شش فیلد را می‌دهد.
func ax1DefaultProfile() map[string]any {
	return map[string]any{
		"kind":              "production",
		"label":             "تولیدی / صادراتی",
		"pricing_note":      "درآمد به دلار/بورس کالا گره خورده (صادراتی).",
		"revenue_basis":     "تولیدی/عمرانی — جمع فروش داخلی + صادراتی (ردیف «جمع» جدول فروش)",
		"volume_applicable": true,
		"volume_note": "تناژ/تعداد محصول در گزارش فعالیت ماهانه معنادار است؛ " +
			"رشد ریالی بدون رشد تناژ = افزایش قیمت.",
	}
}

// ax1ProfileOr مثلِ `profile or company_profile()`.
func ax1ProfileOr(profile map[string]any) map[string]any {
	if len(profile) == 0 {
		return ax1DefaultProfile()
	}
	return profile
}

// ax1Thresholds مثلِ `th or v10_thresholds()` — بی‌آستانه از پنلِ پیش‌فرض
// (nil ⇒ mapِ تهی ⇒ همان پیش‌فرض‌هایِ جزوه).
func ax1Thresholds(th map[string]any) map[string]any {
	if len(th) == 0 {
		return V10Thresholds(nil)
	}
	return th
}

// ═══════════════════════════════════════════════════════════════════════════
//  لایۀ ۱الف — رشدِ ریالی (تجمیعی ÷ همان دورۀ سالِ قبل)
// ═══════════════════════════════════════════════════════════════════════════

// Ind1aMonetaryGrowth پورتِ api/fundamental.ind1a_monetary_growth (542-607).
//
// مخرجِ کسر هرگز «ماهِ قبل» نیست (قاعدۀ جزوه) و از تک‌قاعدۀ
// `SeriesYtdDenominator` (fts_engine.ytd_denominator) می‌آید: ستونِ رسمیِ
// «مقایسه با دورۀ مشابه سالِ قبل» ← ردیفِ (سال−۱، همان ماه). هر دو نبود ⇒
// `data_gap`: شاخص «رد» محاسبه نمی‌شود، «قابل محاسبه نبود».
//
// `series == nil` یعنی اوراکلِ `series=None` ⇒ همان `monthly_series(conn, symbol)`
// (سقفِ پیش‌فرضِ تابع، نه LIMITِ ۶۰ یا ۳۰ِ تاریخیِ کارت/موتور).
func (s *Service) Ind1aMonetaryGrowth(ctx context.Context, symbol string,
	series [][]any, th, profile map[string]any) (map[string]any, error) {
	th = ax1Thresholds(th)
	if series == nil {
		got, err := s.MonthlySeries(ctx, symbol, 0)
		if err != nil {
			return nil, err
		}
		series = got
	}
	prof := ax1ProfileOr(profile)

	// _nodata درِ اوراکل: یکِ شکلِ ثابت + هر کلیدِ اضافه‌ای که شاخه می‌خواهد.
	// `unit: nil` عمدی است — این جدول ستونِ واحدِ پول ندارد.
	nodata := func(reason string, extra map[string]any) map[string]any {
		gap := map[string]any{
			"monetary_pct":  nil,
			"basis":         nil,
			"pass":          false,
			"data_gap":      true,
			"threshold":     th["monetary_growth_min"],
			"revenue_basis": prof["revenue_basis"],
			"reason":        reason,
			"remediation":   ax1MsGapHint,
			"source":        ax1SourceMs,
			"unit":          nil,
			"unit_note":     ax1UnitNoteGap,
		}
		for k, v := range extra {
			gap[k] = v
		}
		return gap
	}

	if len(series) == 0 {
		return nodata(ax1ReasonNoSeries, nil), nil
	}
	d := SeriesYtdDenominator(series)
	if d == nil {
		return nodata(ax1ReasonBadYtd, map[string]any{
			"months": ax1IntOf(ax1Cell(series[0], 1)),
			"year":   ax1IntOf(ax1Cell(series[0], 0)),
		}), nil
	}
	year, _ := toI(d["year"])
	month, _ := toI(d["month"])
	ytdNow := toF(d["ytd_now"])
	basis := d["denominator_basis"]
	if d["ytd_prev"] == nil {
		return nodata(ax1ReasonNoPrev, map[string]any{
			"months":            month,
			"year":              year,
			"ytd_now_bt":        ax1Bt(ytdNow),
			"ytd_prev_bt":       nil,
			"period":            ax1Period(month, year),
			"denominator_basis": basis,
		}), nil
	}
	ytdPrev := toF(d["ytd_prev"])
	growth := ax1Pct(ytdNow, ytdPrev)
	return map[string]any{
		"monetary_pct": growth,
		// `basis` عینِ اوراکل است (`ind1a_monetary_growth`ِ 542-607): این شاخص
		// مبنایِ دومی ندارد، پس کلیدِ صریحِ nil می‌ماند — نه حذف‌شده — تا شکلِ
		// موفق و `_nodata` یک کلیدِ یکسان داشته باشند (رأیِ Task 1، ۱۴۰۵-۰۷-۲۳).
		"basis":      nil,
		"series":     ax1MsSeries(series),
		"ytd_now_bt": ax1Bt(ytdNow), "ytd_prev_bt": ax1Bt(ytdPrev),
		"ytd_now_mrl": ytdNow, "ytd_prev_mrl": ytdPrev,
		"period":            ax1Period(month, year),
		"months":            month,
		"year":              year,
		"denominator_basis": basis,
		"revenue_basis":     prof["revenue_basis"],
		"threshold":         th["monetary_growth_min"],
		"target_threshold":  th["monetary_growth_target"],
		// «رشد قوی» یعنی به هدفِ پوششِ تورم رسیده؛ رأیِ قبولی به کف است، پس این
		// فقط برچسب است و امتیازِ اضافه نمی‌سازد (جزوه ص ۳ + بند ۳).
		"strong":         growth != nil && toF(growth) >= toF(th["monetary_growth_target"]),
		"pass":           growth != nil && toF(growth) >= toF(th["monetary_growth_min"]),
		"data_gap":       false,
		"reason":         "",
		"source":         ax1SourceMs,
		"unit":           nil,
		"unit_note":      ax1UnitNoteOk,
		"ref_period_end": ax1Cell(series[0], 5),
	}, nil
}

// ═══════════════════════════════════════════════════════════════════════════
//  لایۀ ۱ب — رشدِ تولیدی/تناژ (ردِ سودِ صرفاً تورمی)
// ═══════════════════════════════════════════════════════════════════════════

const (
	ax1FSGrowthNoRows  = "هیچ صورت مالی غیرتلفیقی با درآمد ثبت نشده است."
	ax1FSGrowthNoPrior = "دورهٔ مشابهٔ سال قبل برای جدیدترین صورت مالی موجود نیست؛ " +
		"از دورهٔ قدیمی‌تر استفاده نمی‌شود."
)

// ax1FSGrowthKind عینِ `prof["kind"] in fts_engine.FS_GROWTH_KINDS`.
func ax1FSGrowthKind(kind string) bool {
	return kind == "service" || kind == "financial" || kind == "holding"
}

// ax1IsConsolidatedTitle عینِ `_is_consolidated_title` (fts_engine.py): عنوانی
// که «تلفیقی» دارد و «غیرتلفیقی» ندارد، تلفیقی است.
func ax1IsConsolidatedTitle(title string) bool {
	t := normFa(title)
	return strings.Contains(t, "تلفیقی") && !strings.Contains(t, "غیرتلفیقی")
}

// ax1FSGrowthGap عینِ `fts_engine._fs_growth_gap` — شکلِ ثابتِ «قابل محاسبه نبود».
func ax1FSGrowthGap(reason, revenueBasis string, threshold any) map[string]any {
	return map[string]any{
		"monetary_pct": nil, "basis": "fs_unavailable", "period": "",
		"months": int64(0), "year": nil, "pass": false, "data_gap": true,
		"reason": reason, "revenue_basis": revenueBasis, "threshold": threshold,
	}
}

type ax1FSKey struct {
	periodEnd string
	months    int64
}

// Ind1aFSGrowth پورتِ `api.fundamental.ind1a_fs_growth` + `fts_engine.fs_growth_from_rows`:
// رشد درآمد برایِ خدماتی/مالی/هلدینگ که سریِ ماهانه ندارند — میاندوره ÷ همان
// دورهٔ سال قبل، و در نبودِ جفتِ میاندوره سالانه ÷ سالانه. فقط جدیدترین دورهٔ
// هر مبنا داوری می‌شود؛ عددِ دورهٔ قدیمی‌تر جای «امسال» نمی‌نشیند.
func (s *Service) Ind1aFSGrowth(ctx context.Context, symbol string,
	th, profile map[string]any) (map[string]any, error) {
	th = ax1Thresholds(th)
	prof := ax1ProfileOr(profile)
	floor := th["monetary_growth_min"]
	revenueBasis := strOr(prof["revenue_basis"])

	pred, args := s.a45Pred(ctx, "symbol", symbol)
	consFilter := ""
	if cols, err := s.msQuery(ctx, "PRAGMA table_info(financial_statements)", nil); err == nil {
		for _, r := range cols {
			if len(r) > 1 && strOr(r[1]) == "is_consolidated" {
				consFilter = " AND is_consolidated=0"
				break
			}
		}
	}
	rows, err := s.msQuery(ctx, "SELECT period_end, period_months, revenue, title "+
		"FROM financial_statements WHERE "+pred+" AND revenue>0 AND period_months>0"+
		consFilter+" ORDER BY period_end DESC", args)
	if err != nil {
		return nil, err
	}
	byKey := map[ax1FSKey]float64{}
	for _, r := range rows {
		if len(r) < 4 {
			continue
		}
		if ax1IsConsolidatedTitle(strOr(r[3])) {
			continue
		}
		pe := evalCanonicalOrEmpty(r[0])
		m, _ := toI(r[1])
		rev := toF(r[2])
		if pe == "" || m <= 0 || rev <= 0 {
			continue
		}
		k := ax1FSKey{periodEnd: pe, months: m}
		if _, exists := byKey[k]; !exists {
			byKey[k] = rev
		}
	}
	if len(byKey) == 0 {
		return ax1FSGrowthGap(ax1FSGrowthNoRows, revenueBasis, floor), nil
	}
	interims := make([]ax1FSKey, 0, len(byKey))
	annuals := make([]ax1FSKey, 0, len(byKey))
	for k := range byKey {
		if k.months > 0 && k.months < 12 {
			interims = append(interims, k)
		} else if k.months >= 12 {
			annuals = append(annuals, k)
		}
	}
	sort.Slice(interims, func(i, j int) bool { return interims[i].periodEnd > interims[j].periodEnd })
	sort.Slice(annuals, func(i, j int) bool { return annuals[i].periodEnd > annuals[j].periodEnd })

	if len(interims) > 0 {
		k := interims[0]
		parts := strings.Split(k.periodEnd, "/")
		if len(parts) >= 3 {
			if y, ok := parseIntStrict(parts[0]); ok {
				prev := ax1FSKey{periodEnd: fmt.Sprintf("%d/%s/%s", y-1, parts[1], parts[2]),
					months: k.months}
				if prevVal, has := byKey[prev]; has {
					growth := (byKey[k]/prevVal - 1.0) * 100.0
					return map[string]any{
						"monetary_pct": growth, "basis": "fs_interim",
						"period": k.periodEnd, "months": k.months, "year": y,
						"pass": growth >= toF(floor), "data_gap": false, "reason": "",
						"revenue_basis": revenueBasis, "threshold": floor,
					}, nil
				}
			}
		}
	}
	if len(annuals) > 0 {
		k := annuals[0]
		parts := strings.Split(k.periodEnd, "/")
		if len(parts) >= 3 {
			if y, ok := parseIntStrict(parts[0]); ok {
				var prevVal float64
				found := false
				for _, ak := range annuals {
					ap := strings.Split(ak.periodEnd, "/")
					if len(ap) < 3 || ak.months != k.months || ap[1] != parts[1] {
						continue
					}
					if ay, ok := parseIntStrict(ap[0]); ok && ay == y-1 {
						prevVal, found = byKey[ak], true
						break
					}
				}
				if found {
					growth := (byKey[k]/prevVal - 1.0) * 100.0
					return map[string]any{
						"monetary_pct": growth, "basis": "fs_annual",
						"period": k.periodEnd, "months": k.months, "year": y,
						"pass": growth >= toF(floor), "data_gap": false, "reason": "",
						"revenue_basis": revenueBasis, "threshold": floor,
					}, nil
				}
			}
		}
	}
	return ax1FSGrowthGap(ax1FSGrowthNoPrior, revenueBasis, floor), nil
}

// parseIntStrict معادلِ `int(y)` برایِ سالِ canonical؛ ورودیِ غیرعددی ⇒ false.
func parseIntStrict(s string) (int64, bool) {
	var v int64
	if s == "" {
		return 0, false
	}
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			return 0, false
		}
		v = v*10 + int64(ch-'0')
	}
	return v, true
}

// ax1PhysicalPair پورتِ `_physical_pair` (477-514): (کمیتِ تجمیعیِ دوره، کمیتِ
// تجمیعیِ همان دورۀ سالِ قبل، نامِ ستون).
//
// مخرجِ سالِ قبل ستونِ جدا ندارد، پس ردیفِ (سال−۱، همان ماه) از همان ستون خوانده
// می‌شود و تنها اگر آن هم نبود از ستونِ prevِ خودِ ردیف. هر دو استثنایِ اوراکل
// (`PRAGMA` و `SELECT`) بلعیده می‌شوند: بی‌جدول/بی‌ستون ⇒ (nil, nil, نامِ ستون).
// pred/params از ریزولورِ هویتِ نماد می‌آید و همان برگشتِ خامِ `symbol = ?` را دارد
// که series.go:227-230 گذاشته است؛ ردیف‌ها از همان `msQuery` (series.go:261)
// خوانده می‌شوند تا ترتیبِ ستون‌ها مثلِ tupleهایِ sqlite3.Row بماند.
func (s *Service) ax1PhysicalPair(ctx context.Context, symbol string,
	year, month any) (any, any, string) {
	rows, err := s.msQuery(ctx, "PRAGMA table_info(monthly_sales)", nil)
	if err != nil {
		return nil, nil, ""
	}
	present := map[string]bool{}
	for _, r := range rows {
		if len(r) > 1 {
			present[strOr(r[1])] = true
		}
	}
	colNow := ax1FirstPresentKey(ax1VolNowKeys, present)
	if colNow == "" {
		return nil, nil, ""
	}
	colPrev := ax1FirstPresentKey(ax1VolPrevKeys, present)

	sel := "year, month, MAX(" + colNow + ")"
	if colPrev != "" {
		sel += ", MAX(" + colPrev + ")"
	}
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		pred, args = "symbol = ?", []any{symbol}
	}
	got, err := s.msQuery(ctx, "SELECT "+sel+" FROM monthly_sales WHERE "+
		pred+" GROUP BY year, month", args)
	if err != nil {
		return nil, nil, colNow
	}

	table := map[[2]int64][2]any{}
	for _, r := range got {
		if len(r) < 3 {
			continue // IndexErrorِ پایتون درِ `(r[2], ...)` ⇒ همان `continue`
		}
		table[[2]int64{ax1IntOf(r[0]), ax1IntOf(r[1])}] = [2]any{r[2], ax1Cell(r, 3)}
	}
	m := ax1IntOf(month)
	hit, hasHit := table[[2]int64{ax1IntOf(year), m}]
	prev, hasPrev := table[[2]int64{ax1IntOf(year) - 1, m}]

	var now, back any
	if hasHit && hit[0] != nil {
		now = toF(hit[0])
	}
	switch {
	case hasPrev && prev[0] != nil:
		back = toF(prev[0])
	case hasHit && colPrev != "" && hit[1] != nil:
		back = toF(hit[1])
	}
	return now, back, colNow
}

// ax1FirstPresentKey مثلِ `next((c for c in keys if c in present), None)` —
// نخستینِ تطبیقِ ترتیب‌دار، وگرنه "".
func ax1FirstPresentKey(keys []string, present map[string]bool) string {
	for _, c := range keys {
		if present[c] {
			return c
		}
	}
	return ""
}

// Ind1bVolumeGrowth پورتِ api/fundamental.ind1b_volume_growth (618-695): چکِ
// دومِ لایۀ ۱ — آیا «مقدار» واقعاً زیاد شده یا فقط «نرخ» بالا رفته؟
//
// سه سطح به ترتیبِ قدرتِ شاهد: `reported_quantity` (ستونِ فیزیکیِ تناژ/تعداد)،
// `price_effect_decomposition` (تعدیلِ رشدِ اسمی با مبنایِ تورم + پهنایِ رشد)،
// `unavailable` (نه مخرج هست نه شاخصِ مرجع ⇒ چک «رد» محاسبه نمی‌شود، پاس هم نه).
//
// پهنای رشد هیچ‌وقت دروازۀ امتیاز نیست؛ فقط درِ `note_breadth` نمایش داده می‌شود
// (رأیِ مالک ۱۴۰۵-۰۷-۱۱ — جزوه برایِ breadth فرمولی ندارد).
func (s *Service) Ind1bVolumeGrowth(ctx context.Context, symbol string,
	monetary map[string]any, series [][]any, th, profile map[string]any) (map[string]any, error) {
	th = ax1Thresholds(th)
	prof := ax1ProfileOr(profile)
	g := monetary
	if g == nil {
		built, err := s.Ind1aMonetaryGrowth(ctx, symbol, series, th, prof)
		if err != nil {
			return nil, err
		}
		g = built
	}
	out := map[string]any{
		"quantity_verified":   false,
		"basis":               "unavailable",
		"confidence":          "none",
		"volume_pct":          nil,
		"real_pct":            nil,
		"implied_price_pct":   nil,
		"price_benchmark_pct": th["inflation_benchmark"],
		"breadth":             nil,
		"threshold":           th["volume_growth_min"],
		"applicable":          prof["volume_applicable"],
		"pass":                false,
		"data_gap":            true,
		"revenue_basis":       prof["revenue_basis"],
		"note":                prof["volume_note"],
	}
	if !isFalsy(g["data_gap"]) || g["monetary_pct"] == nil {
		out["reason"] = ax1ReasonNoMonetary
		return out, nil
	}
	year, month, monetaryPct := g["year"], g["months"], g["monetary_pct"]
	if series == nil {
		got, err := s.MonthlySeries(ctx, symbol, 0)
		if err != nil {
			return nil, err
		}
		series = got
	}

	// ── سطح A: کمیتِ گزارش‌شده (تناژ/تعداد) ────────────────────────────────
	qtyNow, qtyPrev, col := s.ax1PhysicalPair(ctx, symbol, year, month)
	if col != "" && !isFalsy(qtyNow) && !isFalsy(qtyPrev) && toF(qtyPrev) > 0 {
		vol := ax1Pct(qtyNow, qtyPrev)
		var implied any
		if vol != nil {
			implied = pyround.Round(((1.0+toF(monetaryPct)/100.0)/
				(1.0+toF(vol)/100.0)-1.0)*100.0, 1)
		}
		out["basis"] = "reported_quantity"
		out["quantity_verified"] = true
		out["confidence"] = "high"
		out["volume_pct"] = vol
		out["real_pct"] = vol
		out["implied_price_pct"] = implied
		out["data_gap"] = false
		out["quantity_column"] = col
		out["source_detail"] = fmt.Sprintf(ax1DetailQty, col)
		pass := vol != nil && toF(vol) >= toF(th["volume_growth_min"])
		out["pass"] = pass
		if pass {
			out["reason"] = ""
		} else {
			out["reason"] = ax1ReasonQtyFail
		}
		return out, nil
	}

	// ── سطح B: تجزیهٔ اثرِ قیمت + پهنایِ رشد ────────────────────────────────
	real := ax1RealGrowth(monetaryPct, th["inflation_benchmark"])
	improved, compared := SeriesGrowthBreadth(series, year, month)
	var ratio any
	if compared != 0 {
		ratio = pyround.Round(float64(improved)/float64(compared), 3)
	}
	out["basis"] = "price_effect_decomposition"
	if ratio != nil {
		out["confidence"] = "medium"
	} else {
		out["confidence"] = "low"
	}
	out["real_pct"] = real
	out["data_gap"] = real == nil
	out["implied_price_pct"] = th["inflation_benchmark"]
	out["breadth"] = map[string]any{
		"improved_months": improved, "compared_months": compared,
		"ratio": ratio, "min": th["volume_breadth_min"],
	}
	out["source_detail"] = fmt.Sprintf(ax1DetailBench, toF(th["inflation_benchmark"]))
	if real == nil {
		out["reason"] = ax1ReasonNoBench
		return out, nil
	}
	// پهنای رشد **دادهٔ نمایشی** است، نه دروازۀ امتیاز؛ رأیِ ۱ب همان تعدیلِ رشدِ
	// اسمی با مبنایِ تورم است. بی‌این، کارت و موتورِ اسکرینر دو داوریِ متفاوت
	// برایِ یکِ نماد داشتند.
	pass := toF(real) >= toF(th["volume_growth_min"])
	out["pass"] = pass
	if pass {
		out["reason"] = ""
	} else {
		out["reason"] = fmt.Sprintf(ax1ReasonRealFail, toF(monetaryPct),
			toF(th["inflation_benchmark"]))
	}
	if ratio != nil && improved < compared {
		out["note_breadth"] = fmt.Sprintf(ax1NoteBreadthFmt, improved, compared)
	}
	return out, nil
}

// ═══════════════════════════════════════════════════════════════════════════
//  لایۀ ۱ — رأیِ مجموعِ «الف» و «ب»، و سه‌حالۀ پنجِ محور
// ═══════════════════════════════════════════════════════════════════════════

// Axis1State پورتِ api/fundamental.axis1_state (841-866): رأیِ لایۀ ۱ به‌صورتِ
// سه‌حال + دلیل — تک‌مرجعِ کارت، `scan_symbol` و `bulk_scan`.
//
// (true, "") پاس؛ (false, دلیل) رد؛ (nil, دلیل) «قابل محاسبه نبود» (شکافِ داده).
// شکافِ داده در ۱الف بر همه‌چیز مقدم است: اگر رشدِ ریالی ساخته نشود، ۱ب هم
// داوری نمی‌شود و رأی nil است (نه false — «رد» و «نسنجیده» یکی نیستند). محورِ
// «ب» فقط وقتی وتو می‌شمارد که برایِ ماهیتِ شرکت **قابل‌اعمال** باشد؛
// `applicable is False` (و نه `None`) ⇒ پاس (رأیِ ۱۶).
//
// کلیدِ `pass`ِ کارت عیناً همین سه‌حال است (طلاییِ card_thin برایِ شکافِ ۱الف
// `pass: null` دارد)؛ `Axis1Pass` همان boolِ مصرف‌کننده‌هایِ قدیمی است.
func Axis1State(monetary, volume map[string]any) (any, string) {
	m := monetary
	if m == nil {
		m = map[string]any{}
	}
	if truthy(m["data_gap"]) || m["monetary_pct"] == nil {
		reason := strOr(m["reason"])
		if reason == "" {
			reason = "رشد ریالی قابل محاسبه نیست."
		}
		return nil, reason
	}
	if isFalsy(m["pass"]) {
		return false, "رشد ریالی زیر کف است."
	}
	v := volume
	if v == nil {
		v = map[string]any{}
	}
	// `v.get("applicable") is False` — کلیدِ غایب/None پاسِ ۱ب را وتو نمی‌کند.
	if applicable, ok := v["applicable"]; ok && applicable == false {
		return true, ""
	}
	if truthy(v["pass"]) {
		return true, ""
	}
	reason := strOr(v["reason"])
	if reason == "" {
		reason = "رشد تولیدی/تناژ تأیید نشد."
	}
	return false, reason
}

// Axis1Pass پورتِ api/fundamental.axis1_pass (869-872): پوششِ مصرف‌کننده‌هایِ
// دوحالهِ قدیمی رویِ همان `Axis1State` (`bool(state)`) — تصمیمِ دوم اینجا ساخته
// نمی‌شود. «بی‌داده ≠ رد» را مصرف‌کننده از `data_gap`/`states` می‌پرسد.
func Axis1Pass(monetary, volume map[string]any) bool {
	state, _ := Axis1State(monetary, volume)
	return truthy(state)
}

// V10AxisStates پورتِ api/fundamental.v10_axis_states (701-729): سه‌حالۀ هر پنجِ
// محور از **یک** جایِ تعریف — تنها منبعِ «بی‌نظر».
//
// مقدارِ هر کلید یا bool است یا nil (هیچ‌وقت رشتهٔ "na"): `passes` درِ پایتون
// bool می‌ماند و اینجا هم همان boolها از ورودی می‌آیند، ولی `data_gap`،
// `na`/`available: False` و نبودِ خودِ عدد همه nil می‌شوند. اسکرینر روزی فقط na
// را می‌پرسید ⇒ ۱۱ ردیفِ «بی‌نظرِ کارت» درِ `/api/screener` «مردود» می‌شد.
func V10AxisStates(indicators, passes map[string]any) map[string]any {
	ind := indicators
	i1 := ax1Dict(ax1Dict(ind["1"])["monetary"])
	i2 := ax1Dict(ind["2"])
	i3 := ax1Dict(ind["3"])
	i4 := ax1Dict(ind["4"])

	st := map[string]any{
		"1_growth":        passes["1_growth"],
		"2_eps_trend":     passes["2_eps_trend"],
		"3_gross_margin":  passes["3_gross_margin"],
		"4_sales_to_mcap": passes["4_sales_to_mcap"],
		"5_industry":      passes["5_industry"],
	}
	if !isFalsy(i1["data_gap"]) || i1["monetary_pct"] == nil {
		st["1_growth"] = nil
	}
	if !isFalsy(i2["na"]) || !isFalsy(i2["data_gap"]) || i2["pass"] == nil {
		st["2_eps_trend"] = nil
	}
	if !isFalsy(i3["na"]) || i3["band"] == "not_applicable" || i3["margin_pct"] == nil {
		st["3_gross_margin"] = nil
	}
	// `not i4.get("available", True)` — کلیدِ غایب ⇒ True، ولی کلیدِ حاضرِ بی‌مقدار
	// (None) همان None است و `not None` ⇒ بی‌نظر.
	available := any(true)
	if v, ok := i4["available"]; ok {
		available = v
	}
	if !isFalsy(i4["na"]) || !isFalsy(i4["exempt"]) || isFalsy(available) {
		st["4_sales_to_mcap"] = nil
	}
	return st
}
