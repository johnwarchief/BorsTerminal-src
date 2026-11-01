package fundamental

// لایۀ ۳ — حاشیۀ سود ناخالص (پورتِ `ind3_gross_margin` درِ api/fundamental.py:900-959).
// عدد و منبع از `GrossMargin` (fts_engine.gross_margin) می‌آید؛ این لایه فقط
// «باند» را شفاف می‌کند و برایِ طبقاتی که بهای تمام‌شدہ ندارند حالتِ
// not_applicable می‌دهد — نه صفرِ کاذب. هیچ آستانۀ تازه‌ای اینجا ساخته نشده
// است: margin_min/margin_ideal از همان پنلِ کانفیگ می‌خواند.

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

// Ind3GrossMargin عینِ ind3_gross_margin. دو قیدِ باگیِ پایتون که **عمداً**
// حفظ شده‌اند:
//   - `margin = _f(gm.get("margin_pct"))` هرگز None نیست (_f برایِ همه‌چیزِ
//     غیرعدد صفر می‌دهد)، پس شرطِ `margin is not None` درِ انتخابِ باند همیشه
//     راست است؛ Go هم همان‌جا toF می‌زند و شاخۀ None نمی‌سازد.
//   - `if not gm` درِ پایتون None و {} هر دو را می‌گیرد، پس ردیفِ حاشیۀ
//     تهی هم به شاخۀ N/A می‌افتد (به‌همین‌دلیل برگشتِ GrossMargin با len==0
//     اینجا «بی‌جواب» خوانده می‌شود).
func (s *Service) Ind3GrossMargin(ctx context.Context, symbol string,
	th, ref, profile map[string]any) (map[string]any, error) {
	if len(th) == 0 {
		th = V10Thresholds(nil)
	}
	minMargin := toF(th["margin_min"])
	optimal := toF(th["margin_ideal"])

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
		case strOr(ax1ProfileOr(profile)["kind"]) == "fund":
			// رأیِ ۱۵: صندوق «رد شده» نمی‌گیرد؛ علت را هم باید همان‌طور گفت.
			reason = "این نماد صندوق است؛ صندوق «فروش» و «بهای تمام‌شده» ندارد که " +
				"حاشیهٔ ناخالص از آن‌ها ساخته شود. نبودِ این عدد نقص نیست."
			fix = "برای صندوق‌ها شاخص ۳ سنجیده نمی‌شود؛ کارتِ بنیادیِ صندوق را ببینید."
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
			"data_gap":        dataGap,
			"reason":          reason,
			"remediation":     fix,
		}, nil
	}

	// حاشیۀ منفیِ واقعی (ثتران −۱۸۴٫۶، دامین −۱۴۲٫۵) «N/A» نیست: عدد است و
	// طبیعی به «زیرِ باند» می‌رسد. `_sane(-99, 200)` همین را None می‌کرد؛ اینجا
	// فقط NaN/inf دور ریخته می‌شود — همان کاری که `_f` می‌کند.
	margin := toF(gm["margin_pct"])
	switch {
	case margin >= optimal:
		gm["band"] = "ideal"
	case margin >= minMargin:
		gm["band"] = "acceptable"
	default:
		gm["band"] = "below"
	}
	gm["ideal"] = truthy(gm["optimal"])
	gm["ideal_threshold"] = optimal
	gm["na"] = false
	if _, ok := gm["reason"]; !ok {
		gm["reason"] = ""
	}
	return gm, nil
}
