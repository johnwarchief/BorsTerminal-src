package fundamental

// لایۀ ۳ — حاشیۀ سود ناخالص (پورتِ `ind3_gross_margin` درِ api/fundamental.py:1064-1118).
// عدد و منبع از `GrossMargin` (fts_engine.gross_margin) می‌آید؛ این لایه فقط
// «باند» و «طبقه» را شفاف می‌کند و برایِ طبقاتی که بهای تمام‌شدہ ندارند حالتِ
// not_applicable می‌دهد — نه صفرِ کاذب. هیچ آستانۀ تازه‌ای اینجا ساخته نشده
// است: margin_min/margin_ideal از همان پنلِ کانفیگ می‌خواند.
//
// سه تفکیکِ رأی‌دار (Task 10B2a1) عیناً از اوراکل می‌آید:
//   - «N/Aِ طبقه» (مالی/بانک/هلدینگ/صندوق) پیش از هر محاسبه/استنتاج از `ref`
//     حکم می‌دهد: `na_kind="class"`، `data_gap=false`، `margin_tier=null` —
//     عددِ سود ناخالصِ ثبت‌شده هم برایِ این طبقات حکم نمی‌سازد (بندِ ۴٫۴ سند).
//   - «شکافِ داده» (`na_kind="data"`) با «حاشیه نیست» یکی نیست و با دکمهٔ
//     «دیتابیس کدال» بسته می‌شود.
//   - «N/A نیست» درِ ردیفِ عدددار کلیدِ صریحِ `na_kind=null` می‌گیرد تا مصرف‌کننده
//     بینِ «کلید نیست» و «N/A نیست» فرق بگذارد.

import (
	"context"

	"borsterminal/backend/internal/period"
)

// ax3FaDate عینِ `_fa_date`: نمونۀ دورۀ یکِ ردیف برایِ متنِ کاربر، از
// `codal_periods.canonicalize` — پس خط تیره و رقمِ فارسی به همان شکلِ
// canonical درمی‌آید و ردیفِ بی‌دوره «—» می‌شود.
func ax3FaDate(periodEnd any) string {
	if c := period.Canonicalize(periodEnd); c != nil {
		return *c
	}
	return "—"
}

// ax3MarginNaKinds عینِ `MARGIN_NA_KINDS` (fts_engine.py:1820): طبقه‌هایی که
// «سود ناخالص» برایشان تعریف نشده است.
var ax3MarginNaKinds = []string{"financial", "holding", "fund", "bank"}

// ax3MarginNaReasons عینِ `_MARGIN_NA_REASONS` (fts_engine.py:1822-1835) — دلیل
// از `margin_class`ِ همان پروفایل می‌آید تا بانک «بانک» خوانده شود، نه «هلدینگ».
var ax3MarginNaReasons = map[string]string{
	"bank": "این نماد بانک/مؤسسهٔ اعتباری است؛ «سود ناخالص» برای این طبقه " +
		"تعریف نشده است (درآمد از تسهیلات، سپرده و کارمزد است، نه فروش " +
		"کالا). شاخص ۳ برای این طبقه سنجیده نمی‌شود.",
	"financial": "این نماد در طبقهٔ مالی/اعتباری است؛ «سود ناخالص» برای این " +
		"طبقه تعریف نشده است (درآمد از خدمات مالی و کارمزد است، نه " +
		"فروش کالا). شاخص ۳ برای این طبقه سنجیده نمی‌شود.",
	"holding": "این نماد هلدینگ/سرمایه‌گذاری است؛ «سود ناخالص» برای این طبقه " +
		"تعریف نشده است (درآمد از پرتفوی است، نه فروش عملیاتی). " +
		"شاخص ۳ برای این طبقه سنجیده نمی‌شود.",
	"fund": "این نماد صندوق است؛ صندوق «فروش» و «بهای تمام‌شده» ندارد که " +
		"حاشیهٔ ناخالص از آن‌ها ساخته شود. شاخص ۳ برای صندوق سنجیده " +
		"نمی‌شود.",
}

// ax3MarginNaRemediation عینِ `_MARGIN_NA_REMEDIATION` (fts_engine.py:1837-1846).
var ax3MarginNaRemediation = map[string]string{
	"bank": "این N/A به ماهیتِ طبقه (بانک/اعتباری) برمی‌گردد، نه شکافِ داده؛ " +
		"شاخص ۳ برای طبقه‌های بانکی سنجیده نمی‌شود.",
	"financial": "این N/A به ماهیتِ طبقه (مالی/اعتباری) برمی‌گردد، نه شکافِ " +
		"داده؛ شاخص ۳ برای طبقه‌های مالی سنجیده نمی‌شود.",
	"holding": "این N/A به ماهیتِ طبقه (هلدینگ/سرمایه‌گذاری) برمی‌گردد، نه " +
		"شکافِ داده؛ شاخص ۳ برای هلدینگ سنجیده نمی‌شود.",
	"fund": "این N/A به ماهیتِ طبقه (صندوق) برمی‌گردد، نه شکافِ داده؛ شاخص ۳ " +
		"برای صندوق سنجیده نمی‌شود.",
}

// ax3MarginTier عینِ `fts_engine.margin_tier` (1797-1813): برچسبِ نمایشیِ طبقهٔ
// حاشیه — **نه** دروازهٔ تازه. کفِ ۲۰٪ و استانداردِ ۳۰٪ همان حکمِ جزواند و ۵۰٪
// فقط نامِ «خوب» است، پس هیچ pass/optimalی از این تابع ساخته نمی‌شود. nil یعنی
// «حاشیه ساخته نشد» (N/A مالی/هلدینگ/صندوق/بی‌سطر)، نه صفر.
//
// TODO(axis3): اوراکل این را از حاشیۀ **خام** می‌سازد (`gross_margin`: margin)،
// ولی `Service.GrossMargin` (statements.go) فقط `margin_pct`ِ گردشده را
// برمی‌گرداند؛ مرزهایِ ۲۰/۳۰/۵۰ با عددِ گرد می‌توانند یک‌دهم جابه‌جا شوند
// (۱۹٫۹۶ ⇒ «۲۰٫۰»). طلایی‌ها رویِ ۲۵ و ۱۱ هیچ مرزی را لمس نمی‌کنند؛ اصلاحِ کامل
// یک فیلدِ خام در statements.go می‌خواهد (خارج از دامنۀ این تسک).
func ax3MarginTier(pct any) any {
	f, ok := asFloat(pct)
	if !ok {
		return nil
	}
	switch {
	case f < 20:
		return "below_floor"
	case f < 30:
		return "floor"
	case f < 50:
		return "standard"
	default:
		return "good"
	}
}

// ax3MarginClassNA عینِ `fts_engine.margin_class_na` (1849-1878): N/Aِ طبقهٔ
// شاخص ۳ — مالی/بانکی/هلدینگ/صندوق، حتی با سود ناخالصِ ثبت‌شده. خروجی برایِ
// طبقهٔ دیگر nil است تا گیت روی ۲۰/۳۰ِ تولیدی/خدماتی اثری نگذارد.
//
// `margin_class` همان کلیدِ پروفایل است (بانک زیرِ kind=holding می‌افتد ولی
// «سرمایه‌گذاری/هلدینگ» خواندنش غلط است) و فقط متنِ دلیل را دقیق می‌کند.
func ax3MarginClassNA(profile map[string]any, minMargin, optimal float64) map[string]any {
	kind := strOr(profile["kind"])
	if !contains(ax3MarginNaKinds, kind) {
		return nil
	}
	naClass := strOr(profile["margin_class"])
	if naClass == "" {
		naClass = kind
	}
	if _, ok := ax3MarginNaReasons[naClass]; !ok {
		naClass = kind
	}
	return map[string]any{
		"margin_pct": nil, "pass": false, "optimal": false, "ideal": false,
		"na": true, "band": "not_applicable",
		// تفکیکِ «N/Aِ طبقه» از «شکافِ داده» برایِ مصرف‌کننده‌ها: `ind3_na`
		// فقط `"class"` را N/Aِ ماهیت می‌شمارد.
		"na_kind":         "class",
		"threshold":       minMargin,
		"ideal_threshold": optimal,
		// برچسبِ طبقه هنگامِ N/A تهی است، نه «below_floor»: حاشیه‌ای که ساخته
		// نشد صفر نیست و برچسبِ نمایشی هم نمی‌گیرد (Task 6).
		"margin_tier":  nil,
		"data_gap":     false,
		"margin_class": naClass,
		"reason":       ax3MarginNaReasons[naClass],
		"remediation":  ax3MarginNaRemediation[naClass],
	}
}

// Ind3GrossMargin عینِ ind3_gross_margin. سه قیدِ باگیِ پایتون که **عمداً**
// حفظ شده‌اند:
//   - `margin = _f(gm.get("margin_pct"))` هرگز None نیست (_f برایِ همه‌چیزِ
//     غیرعدد صفر می‌دهد)، پس شرطِ `margin is not None` درِ انتخابِ باند همیشه
//     راست است؛ Go هم همان‌جا toF می‌زند و شاخۀ None نمی‌سازد.
//   - `if not gm` درِ پایتون None و {} هر دو را می‌گیرد، پس ردیفِ حاشیۀ
//     تهی هم به شاخۀ N/A می‌افتد (به‌همین‌دلیل برگشتِ GrossMargin با len==0
//     اینجا «بی‌جواب» خوانده می‌شود).
//   - گیتِ طبقه **پیش از** هر محاسبه از `ref` می‌آید (1064-1080): صندوق یا
//     بانک حتی با سود ناخالصِ ثبت‌شده هم حکم/برچسبِ حاشیه نمی‌گیرد.
func (s *Service) Ind3GrossMargin(ctx context.Context, symbol string,
	th, ref, profile map[string]any) (map[string]any, error) {
	if len(th) == 0 {
		th = V10Thresholds(nil)
	}
	minMargin := toF(th["margin_min"])
	optimal := toF(th["margin_ideal"])

	prof := ax1ProfileOr(profile)
	if na := ax3MarginClassNA(prof, minMargin, optimal); na != nil {
		return na, nil
	}

	gm, err := s.GrossMargin(ctx, symbol, minMargin, optimal, ref, nil)
	if err != nil {
		return nil, err
	}
	if len(gm) == 0 {
		// «حاشیه نیست» با «داده نیست» یکی نیست — کاربر باید بداند کدام شکاف
		// با دکمهٔ «دیتابیس کدال» بسته می‌شود و کدام با انتشارِ گزارشِ بعدی.
		var reason, fix string
		dataGap := false
		switch {
		case ref == nil:
			reason = "صورت مالی سالانهٔ این نماد در پایگاه کدال ما نیست؛ " +
				"تا آن نیاید، سود ناخالص و در نتیجه حاشیه محاسبه نمی‌شود."
			fix = "با دکمهٔ «دیتابیس کدال» صورت‌های مالی این نماد را تازه کنید؛ " +
				"این شکاف با انتشار گزارش بعدی هم خودبه‌خود بسته می‌شود."
			dataGap = true
		case toF(ref["revenue"]) <= 0:
			reason = "درآمد عملیاتیِ سالِ مرجع (" + ax3FaDate(ref["period_end"]) +
				") در کدال خالی یا صفر ثبت شده، پس تقسیمِ سود ناخالص بر آن ممکن نیست."
			fix = "با گرفتنِ دیتابیس تازهٔ کدال یا انتشار صورت سود و زیان سالانه بسته می‌شود."
			dataGap = true
		default:
			// نامِ صنعت را دلیل نمی‌کنیم: آنچه قطعی است نبودِ خودِ سطر است.
			reason = "در صورت سود و زیانِ سالِ مرجع (" + ax3FaDate(ref["period_end"]) +
				") سطر «سود ناخالص» یا «بهای تمام‌شدهٔ کالای فروش‌رفته» ثبت نشده است؛ " +
				"بدونِ این سطر، حاشیهٔ ناخالص محاسبه نمی‌شود."
			fix = "نقص داده نیست — تا خودِ کدال این سطر را منتشر نکند، شاخص ۳ سنجیده نمی‌شود."
		}
		return map[string]any{
			"margin_pct":      nil,
			"pass":            false,
			"ideal":           false,
			"na":              true,
			"band":            "not_applicable",
			"threshold":       minMargin,
			"ideal_threshold": optimal,
			"optimal":         false,
			// شکافِ داده `na: true` است (حکمی ساخته نشد) ولی «N/Aِ طبقه» نیست؛
			// `na_kind` همین تفاوت را به اسکرینر/جدول می‌برد (Task 10B2a1 fix 1).
			"na_kind": "data",
			// برچسبِ طبقه هنگامِ شکاف تهی است، نه «below_floor»: حاشیه‌ای که
			// ساخته نشد صفر نیست و برچسبِ نمایشی هم نمی‌گیرد (Task 6).
			"margin_tier": nil,
			"data_gap":    dataGap,
			"reason":      reason,
			"remediation": fix,
		}, nil
	}

	// حاشیۀ منفیِ واقعی (ثتران −۱۸۴٫۶، دامین −۱۴۲٫۵) «N/A» نیست: عدد است و
	// طبیعی به «زیرِ باند» می‌رسد. `_sane(-99, 200)` همین را None می‌کرد؛ اینجا
	// فقط NaN/inf دور ریخته می‌شود — همان کاری که `_f` می‌کند.
	//
	// باند از **حکمِ خام** می‌آید (`optimal`/`pass`)، نه از `margin_pct`ِ گردشده:
	// ۲۹٫۹۶٪ که «۳۰٫۰» دیده می‌شود `optimal=False` است و نباید «ایده‌آل» خوانده
	// شود (Task 6 fix).
	switch {
	case truthy(gm["optimal"]):
		gm["band"] = "ideal"
	case truthy(gm["pass"]):
		gm["band"] = "acceptable"
	default:
		gm["band"] = "below"
	}
	// برچسبِ طبقه (Task 6) از خودِ عدد ساخته می‌شود؛ ۵۰٪ دروازه نیست.
	if _, ok := gm["margin_tier"]; !ok {
		gm["margin_tier"] = ax3MarginTier(gm["margin_pct"])
	}
	gm["ideal"] = truthy(gm["optimal"])
	gm["ideal_threshold"] = optimal
	gm["na"] = false
	// حاشیۀ عدددار نه N/Aِ طبقه است نه شکافِ داده؛ کلید صریح می‌ماند تا
	// مصرف‌کننده‌ها بینِ «کلید نیست» (payloadِ قدیمی) و «N/A نیست» فرق بگذارند.
	if _, ok := gm["na_kind"]; !ok {
		gm["na_kind"] = nil
	}
	if _, ok := gm["reason"]; !ok {
		gm["reason"] = ""
	}
	return gm, nil
}
