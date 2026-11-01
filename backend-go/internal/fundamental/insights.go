package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §\u06F3). What changes: پورتِ
// `build_insights` (api/fundamental.py:1434-1793) — متن‌سازِ کارتِ بنیادی:
// یک ورودی برای هر لایه (قراردادِ قدیمیِ CSV که app.js مصرف می‌کند) به‌علاوهٔ
// `details[step]["subchecks"]` (لایۀ جدیدِ v10 که کارت با آن «چک الف/ب» را
// جدا نشان می‌دهد).
//
// Invariants: هیچ رأیِ تازه‌ای ساخته نمی‌شود — هر متن از همان `res`ِ
// `EvaluateV10` خوانده می‌شود و هیچ آستانه/حکمی دوباره محاسبه نمی‌شود.
// قاعده‌ها از همان کمک‌تابع‌هایِ مشترکِ پکیج می‌آید تا «تعریفِ دومِ هم‌نام»
// ساخته نشود: `Axis1Pass` (رأیِ لایۀ \u06F1)، `state`/`n`/`pctText`/`fa`/`faInt`
// (شکلِ عدد و سه‌حالگی) و `pyround` (نیم‌به‌زوجِ پایتون).
//
// Lockstep: رشته‌هایِ کاربر-دیدنی عینِ پایتون‌اند. رقمِ فارسی با کدپوینت
// (‎\u06F1) می‌آید، نه رقمِ دستی — قیدِ AGENTS («ویرایشِ مستقیمِ رقم در متن،
// رقم را می‌دزدد»). جداکننده‌ها و نشانه‌ها (— ، ٪ ÷ × ≥ − ← ·) هم از خودِ
// اوراکل کپی شده‌اند.
//
// Guard: `testdata/golden/s*/fund_*.json` (بدنۀ کاملِ پایتون) + مقایسهٔ
// مستقیمِ `build_insights` با خروجیِ Go. Rollback: revertِ همین کامیت.

import (
	"fmt"
	"strconv"
	"strings"
)

// ── نقشه‌هایِ ثابتِ اوراکل (عینِ پایتون) ───────────────────────────────────

// insBasisFa عینِ `_BASIS_FA` — نامِ فارسیِ مبنایِ رشدِ تولیدی.
var insBasisFa = map[string]string{
	"price_effect_decomposition": "تعدیل اثر تورمی",
	"reported_quantity":          "تناژ گزارش‌شده",
	"direct_quantity":            "تناژ مستقیم",
	"quantity_verified":          "تناژ تأییدشده",
}

// insEvShort عینِ `_EV_SHORT` — برچسبِ کوتاهِ شاهدِ EPS در سطرِ جزئیات.
var insEvShort = map[string]string{
	"audited_year_end":          "حسابرسی‌شده",
	"unaudited_year_end":        "حسابرسی‌نشده",
	"consolidated_audited":      "تلفیقیِ حسابرسی‌شده",
	"consolidated_unaudited":    "تلفیقیِ حسابرسی‌نشده",
	"annualized_interim":        "میاندوره × \u06F1\u06F2÷م",
	"annualized_interim_short":  "میاندورهٔ کوتاه × \u06F1\u06F2÷م",
	"missing":                   "بدون داده",
}

// insEvFa عینِ `_EV_FA` — مبنایِ امروزیِ سابقهٔ EPS.
var insEvFa = map[string]string{
	"audited_year_end": "\u06F1\u06F2ماههٔ حسابرسی‌شدهٔ شرکت اصلی (غیرتلفیقی)",
	"year_end_unaudited": "سال‌پایانِ غیرتلفیقیِ حسابرسی‌نشده " +
		"(صورت حسابرسی‌شدهٔ آن سال‌ها در کدال نیست)",
	"consolidated_year_end": "شامل صورتِ تلفیقی " +
		"(آن سال‌ها صورت \u06F1\u06F2ماههٔ غیرتلفیقی منتشر نشده)",
	"year_end_plus_interim": "سال‌پایان + سال‌سازیِ میاندوره × \u06F1\u06F2÷م " +
		"برای تکمیلِ سه سال",
	"insufficient": "مبنای معتبری یافت نشد",
}

// insConfFa عینِ `{"high": "بالا", "medium": "متوسط", "low": "پایین"}`.
var insConfFa = map[string]string{"high": "بالا", "medium": "متوسط", "low": "پایین"}

// ── کمک‌تابع‌هایِ ترجمهٔ پایتون (همین فایل؛ اسم‌ها با `ins` تا برخورد
//    با فایل‌هایِ همسایه پیش نیاید) ────────────────────────────────────────

// insFalsy عینِ `bool(x)` درِ پایتون — شاملِ «فهرست/نقشۀ تهی» که درِ Go
// «truthy» شمرده می‌شود ولی درِ پایتون کاذب است.
//
// `isFalsy`ِ مشترکِ پکیج فقط نوع‌هایِ عددی/رشته‌ای/بولی را می‌شناسد؛ ولی
// `build_insights` چند جا `x or y` دارد که `x` می‌تواند فهرست یا نقشۀ باشد
// (`e.get("period_slots") or e.get("fiscal_years") or []`). اگر فهرستِ تهی
// «truthy» شمرده شود، منبعِ دوره‌ها عوض می‌شود و جدولِ شاخصِ ۲ با پایتون
// نمی‌خواند.
func insFalsy(v any) bool {
	switch x := v.(type) {
	case nil:
		return true
	case string:
		return x == ""
	case bool:
		return !x
	case []any:
		return len(x) == 0
	case []string:
		return len(x) == 0
	case []map[string]any:
		return len(x) == 0
	case map[string]any:
		return len(x) == 0
	case int:
		return x == 0
	case int64:
		return x == 0
	case int32:
		return x == 0
	case float64:
		return x == 0
	case float32:
		return x == 0
	case json.Number:
		f, ok := asFloat(x)
		return !ok || f == 0
	}
	return false
}

// insSubMap عینِ `(parent.get(key) or {})` — نقشۀ تهی به‌جایِ nil، مثلِ پایتون.
func insSubMap(parent map[string]any, key string) map[string]any {
	if parent == nil {
		return map[string]any{}
	}
	sub, ok := parent[key].(map[string]any)
	if !ok || len(sub) == 0 {
		return map[string]any{}
	}
	return sub
}

// insOr عینِ `x or y` — ارزشِ کاذب (None/\u06F0/رشتهٔ خالی/false/فهرستِ تهی)
// به پیش‌فرض می‌رسد.
func insOr(v any, def any) any {
	if insFalsy(v) {
		return def
	}
	return v
}

// insOrStr عینِ `("%s" % (x or def))`.
func insOrStr(v any, def string) string {
	if insFalsy(v) {
		return def
	}
	return pyStr(v)
}

// insG عینِ `"%g" % v` — شش رقمِ معنادار، بدونِ صفرِ انتهایی (مثلِ پایتون).
func insG(v any) string {
	return strconv.FormatFloat(toF(v), 'g', 6, 64)
}

// insD عینِ `"%d" % v` — اعشار سرِ اعشار به سمتِ صفر چیده می‌شود (مثلِ `int()`).
func insD(v any) string {
	return strconv.FormatInt(int64(toF(v)), 10)
}

// insAnyList مثلِ `list(x)` برای فهرست‌هایِ رشته‌ای/مخلوط.
func insAnyList(v any) []any {
	switch x := v.(type) {
	case []any:
		return x
	case []string:
		out := make([]any, 0, len(x))
		for _, s := range x {
			out = append(out, s)
		}
		return out
	}
	return nil
}

// insJoinPy عینِ `"sep".join(items)` — با `str()` هر عضو (پایتون فقط رشته می‌پذیرد).
func insJoinPy(items []any, sep string) string {
	parts := make([]string, 0, len(items))
	for _, it := range items {
		parts = append(parts, pyStr(it))
	}
	return strings.Join(parts, sep)
}

// insJoinOr عینِ `"sep".join(items) or def` — رشتهٔ joinِ تهی ⇒ پیش‌فرض.
func insJoinOr(items []string, sep, def string) string {
	joined := strings.Join(items, sep)
	if joined == "" {
		return def
	}
	return joined
}

// insJoinAnyOr عینِ `"sep".join(items) or def` برایِ فهرستِ مخلوط.
func insJoinAnyOr(items []any, sep, def string) string {
	joined := insJoinPy(items, sep)
	if joined == "" {
		return def
	}
	return joined
}

// insVerdictFa عینِ `"پاس" if v else "مردود"` (حکمِ لایهٔ ۵ — «بله/خیر» نیست).
func insVerdictFa(v any) string {
	if truthy(v) {
		return "پاس"
	}
	return "مردود"
}

// insYesNo عینِ `"بله" if v else "خیر"`.
func insYesNo(v any) string {
	if truthy(v) {
		return "بله"
	}
	return "خیر"
}

// insN عینِ `_n(v, nd)` — نگهبانِ «نوعِ غیرعددی».
//
// پایتون `float(v)` را در `try` می‌گیرد: برایِ `None`/لیست/دیکشنری TypeError
// می‌دهد و `_n» «—» برمی‌گرداند (نه صفرِ گمراه‌کننده). `n` درِ پایتونِ Go
// برایِ آنِ ناشناخته صفر می‌دهد، پس این نگهبان لازم است تا «—» عینِ پایتون
// بماند؛ بقیهٔ مسیر (گِردکردنِ نیم‌به‌زوج و جداکنندهٔ هزارگان) از خودِ `n`
// می‌آید تا تعریفِ دومِ هم‌نام ساخته نشود.
func insN(v any, nd int) string {
	switch v.(type) {
	case []any, []string, []map[string]any, map[string]any:
		return "—"
	}
	return n(v, nd)
}

// insCountNonDash شمارِ سلول‌هایی که «-» نیستند (جایِ دورهٔ غایب).
func insCountNonDash(cells []string) int {
	n := 0
	for _, c := range cells {
		if c != "-" {
			n++
		}
	}
	return n
}

// insBasisStr عینِ `_BASIS_FA.get(str(v.get("basis")), str(v.get("basis") or "تعدیل تورمی"))`.
func insBasisStr(basis any) string {
	if s, ok := insBasisFa[pyStr(basis)]; ok {
		return s
	}
	if isFalsy(basis) {
		return "تعدیل تورمی"
	}
	return pyStr(basis)
}

// insConfirmLabel عینِ `{True: "تأیید", False: "قطع", None: "نامعلوم"}[v]`.
//
// کلیدِ dict درِ پایتون با «hash و ==» خوانده می‌شود ⇒ ۱ مثلِ True و ۰ مثلِ
// False است. (برایِ عددهایِ دیگر یا رشته‌ها پایتون KeyError می‌دهد؛ آن‌جا
// «نامعلوم» داده می‌شود — خطایِ پایتون قابلِ بازتولید نیست.)
func insConfirmLabel(v any) string {
	switch x := v.(type) {
	case bool:
		if x {
			return "تأیید"
		}
		return "قطع"
	case nil:
		return "نامعلوم"
	}
	if f, ok := asFloat(v); ok {
		switch f {
		case 1:
			return "تأیید"
		case 0:
			return "قطع"
		}
		return "نامعلوم"
	}
	// پایتون کلیدِ dict را با «==» می‌خواند ⇒ صفر مثلِ False است.
	if isFalsy(v) {
		return "قطع"
	}
	return "نام.unknown"
}

// insReconciled عینِ `ann.get("reconciled", True)` — کلیدِ غایب ⇒ True.
func insReconciled(ann map[string]any) bool {
	raw, ok := ann["reconciled"]
	if !ok {
		return true
	}
	return truthy(raw)
}

// ── سطرِ جدولِ شاخص \u06F2 (`_eps_cells` / `_eps_row`) ───────────────────────────

// insEpsCells عینِ `_eps_cells` — سلول‌هایِ جدولِ شاخص \u06F2 (همیشه به بلندایِ
// دوره‌هایِ لازم؛ غایب ⇒ «-») به‌علاوهٔ برچسبِ دوره‌ها.
func insEpsCells(e map[string]any) ([]string, []string) {
	src := e["period_slots"]
	if insFalsy(src) {
		src = e["fiscal_years"]
	}
	if insFalsy(src) {
		src = []any{}
	}
	slots := insAnyList(src)
	vals := insAnyList(insOr(e["eps_series"], []any{}))

	need := 3
	switch {
	case truthy(e["years_required"]):
		need = int(toF(e["years_required"]))
	case len(slots) > 0:
		need = len(slots)
	case len(vals) > 0:
		need = len(vals)
	}
	if len(vals) < need {
		vals = append(make([]any, need-len(vals)), vals...)
	}
	// پایتون پیش از `str()` لبه را با رشتهٔ تهی پر می‌کند (نه با None) — پس
	// دورهٔ غایب «-» می‌شود، نه «None».
	slotStrs := make([]string, 0, len(slots))
	for _, s := range slots {
		slotStrs = append(slotStrs, pyStr(s))
	}
	if len(slotStrs) < need {
		slotStrs = append(make([]string, need-len(slotStrs)), slotStrs...)
	}
	if len(slotStrs) > need {
		slotStrs = slotStrs[:need]
	}
	if len(vals) > need {
		vals = vals[:need]
	}

	cells := make([]string, 0, need)
	for _, v := range vals {
		if v == nil {
			cells = append(cells, "-")
			continue
		}
		cells = append(cells, insN(v, 0))
	}
	return cells, slotStrs
}

// insEpsRow عینِ `_eps_row` — سطرِ آمادهٔ جدولِ شاخص \u06F2 (markdownِ قرمز در حالتِ
// ناقص). «سطر هرگز حذف نمی‌شود»: مقدارِ موجود می‌آید و جایِ دورهٔ غایب «-».
func insEpsRow(e map[string]any) map[string]any {
	cells, slots := insEpsCells(e)
	need := len(cells)

	avail, ok := toI(e["available_periods"])
	if !ok {
		avail = int64(insCountNonDash(cells))
	}
	if avail == 0 {
		avail = int64(insCountNonDash(cells))
	}
	partial := avail > 0 && int(avail) < need

	lbl := "شاخص \u06F2"
	if partial {
		lbl = fmt.Sprintf("شاخص \u06F2 (تنها %s دوره موجود است)", faInt(avail))
	}

	var md string
	if partial {
		sp := func(x string) string { return `<span style="color: red;">` + x + `</span>` }
		spCells := make([]string, 0, len(cells))
		for _, c := range cells {
			spCells = append(spCells, sp(c))
		}
		md = "|" + sp(lbl) + "| " + strings.Join(spCells, " | ") + "|"
	} else {
		md = "| " + lbl + " | " + strings.Join(cells, " | ") + " |"
	}

	periods := make([]map[string]any, 0, len(cells))
	for i, c := range cells {
		year := "—"
		if i < len(slots) && slots[i] != "" {
			year = slots[i]
		}
		periods = append(periods, map[string]any{
			"year": year, "value": c, "missing": c == "-",
		})
	}
	return map[string]any{
		"label": lbl, "cells": cells, "markdown": md, "red": partial,
		"available": avail, "required": need, "periods": periods,
	}
}

// BuildInsights عینِ `build_insights`.
//
// ورودی: خروجیِ `EvaluateV10` (نقشۀ `res` درِ پایتون). خروجی: فهرستِ
// ورودی‌هایِ لایه‌ها (`insights`) + نقشۀ جزئیاتِ لایه‌ها (`details`).
func BuildInsights(res map[string]any) ([]map[string]any, map[string]any) {
	ind := insSubMap(res, "indicators")
	th := insSubMap(insSubMap(res, "methodology"), "thresholds")
	prof := insSubMap(res, "profile")
	l1 := insSubMap(ind, "1")
	g := insSubMap(l1, "monetary")
	v := insSubMap(l1, "volume")

	insights := []map[string]any{}
	details := map[string]any{}

	// ── لایهٔ \u06F1: درآمد/فروش (\u06F1الف ریالی + \u06F1ب فیزیکی) ─────────────────────
	axis1 := Axis1Pass(g, v)

	var txt1 string
	switch {
	case truthy(g["data_gap"]):
		txt1 = fmt.Sprintf("⚠️ \u06F1الف رشد ریالی: داده موجود نیست (%s)",
			insOrStr(g["reason"], "مخرج YoY غایب"))
	case truthy(g["pass"]):
		strong := ""
		if truthy(g["strong"]) {
			strong = fmt.Sprintf(" · هدف %s٪ هم پوشش شد", insG(th["monetary_growth_target"]))
		}
		txt1 = fmt.Sprintf("✅ \u06F1الف رشد ریالی: %s (کف %s٪ احراز شد%s)",
			pctText(g["monetary_pct"], true), insG(th["monetary_growth_min"]), strong)
	default:
		txt1 = fmt.Sprintf("⚠️ \u06F1الف رشد ریالی: %s (زیر کف %s٪)",
			pctText(g["monetary_pct"], true), insG(th["monetary_growth_min"]))
	}

	basisStr := insBasisStr(v["basis"])

	var txt1b string
	switch {
	case truthy(v["data_gap"]):
		if isFalsy(v["reason"]) {
			txt1b = "⚠️ \u06F1ب رشد تولیدی: عدم دسترسی به داده"
		} else {
			txt1b = fmt.Sprintf("⚠️ \u06F1ب رشد تولیدی: %s", pyStr(v["reason"]))
		}
	case truthy(v["pass"]):
		txt1b = fmt.Sprintf("✅ \u06F1ب رشد تولیدی: تأیید شد (%s)", basisStr)
	default:
		vReason := "رشد صرفاً از افزایش نرخ است (فاقد رشد حجم)"
		if truthy(v["reason"]) {
			vReason = pyStr(v["reason"])
		}
		txt1b = fmt.Sprintf("🚫 \u06F1ب رشد تولیدی: %s", vReason)
	}

	insights = append(insights, map[string]any{
		"step":  "\u06F1",
		"title": "لایهٔ \u06F1 — درآمد/فروش (رشد ریالی + تأیید حجم)",
		"type":  insType(axis1, "success", "warning"),
		"text":  txt1 + "<br>" + txt1b,
	})

	breadth := insSubMap(v, "breadth")
	breadthPart := ""
	if truthy(breadth["compared_months"]) {
		breadthPart = fmt.Sprintf(" — پهنای رشد: %s/%s ماه",
			insD(breadth["improved_months"]), insD(breadth["compared_months"]))
	}
	confRaw := v["confidence"]
	confFa, ok := insConfFa[pyStr(confRaw)]
	if !ok {
		confFa = "—"
		if truthy(confRaw) {
			confFa = pyStr(confRaw)
		}
	}
	volValue := v["real_pct"]
	if truthy(v["quantity_verified"]) {
		volValue = v["volume_pct"]
	}

	details["\u06F1"] = map[string]any{
		"title": "درآمد/فروش — رشد ریالی (\u06F1الف) + تأیید حجم (\u06F1ب)",
		"formula": fmt.Sprintf(
			"\u06F1الف = (تجمیعی دوره ÷ تجمیعی همان دورهٔ سال قبل) × \u06F1\u06F0\u06F0 − \u06F1\u06F0\u06F0 · "+
				"پاس ≥ %s٪ · \u06F1ب = رشد کمیت ≥ %s٪ یا رشد واقعیِ پس از تورم ≥ %s٪ · "+
				"پهنای رشد (%s/%s ماه) فقط نمایشی است، دروازۀ امتیاز نیست",
			insG(th["monetary_growth_min"]), insG(th["volume_growth_min"]),
			insG(th["volume_growth_min"]),
			insD(insOr(breadth["improved_months"], int64(0))),
			insD(insOr(breadth["compared_months"], int64(0)))),
		"source": fmt.Sprintf(
			"کدال — گزارش فعالیت ماهانهٔ منتهی به %s | مخرج: %s | طبقهٔ شرکت: %s",
			insOrStr(g["period"], "—"), insOrStr(g["denominator_basis"], "—"),
			pyStr(prof["label"])),
		"calc": fmt.Sprintf(
			"%s ÷ %s میلیارد تومان = %s | \u06F1ب: مبنای %s → رشد واقعی %s (مبنای نرخ %s٪)",
			insN(g["ytd_now_bt"], 0), insN(g["ytd_prev_bt"], 0),
			pctText(g["monetary_pct"], true), insOrStr(v["basis"], "—"),
			pctText(v["real_pct"], true), insN(v["price_benchmark_pct"], 0)),
		"what": fmt.Sprintf("%s<br>%s<br>شواهد حجم: %s%s",
			pyStr(prof["revenue_basis"]), pyStr(prof["volume_note"]),
			insOrStr(v["source_detail"], "—"), breadthPart),
		"subchecks": []map[string]any{
			{
				"key": "1a", "label": "رشد ریالی",
				"state":     state(truthy(g["pass"]), false, truthy(g["data_gap"])),
				"value":     pctText(g["monetary_pct"], true),
				"threshold": fmt.Sprintf("≥ %s٪", insG(th["monetary_growth_min"])),
				"detail": fmt.Sprintf("تجمیعی %s ÷ %s میلیارد تومان (%s)",
					insN(g["ytd_now_bt"], 0), insN(g["ytd_prev_bt"], 0),
					insOrStr(g["period"], "—")),
			},
			{
				"key": "1b", "label": "رشد تولیدی / تناژ",
				"state":     state(truthy(v["pass"]), false, truthy(v["data_gap"])),
				"value":     pctText(volValue, true),
				"threshold": fmt.Sprintf("≥ %s٪", insG(th["volume_growth_min"])),
				"verified":  truthy(v["quantity_verified"]),
				"confidence": confRaw,
				"detail": fmt.Sprintf("%s (اطمینان %s)", basisStr, confFa),
			},
		},
	}

	// ── لایهٔ \u06F2: سابقهٔ \u06F3 سالهٔ سودسازی ───────────────────────────────────
	e := insSubMap(ind, "2")
	itm := insSubMap(e, "interim")
	evList := insAnyList(insOr(e["evidence"], []any{}))
	cells, slots := insEpsCells(e)
	row := insEpsRow(e)
	partial := truthy(row["red"])
	avail, _ := toI(row["available"])

	evDetail := "—"
	if len(cells) > 0 {
		parts := make([]string, 0, len(cells))
		for i, c := range cells {
			y := "—"
			if i < len(slots) && slots[i] != "" {
				y = slots[i]
			}
			tw := ""
			if i < len(evList) {
				tw = pyStr(evList[i])
			}
			suffix := ""
			if c != "-" {
				short, found := insEvShort[tw]
				if !found {
					short = ""
				}
				suffix = fmt.Sprintf(" (%s)", short)
			}
			parts = append(parts, fmt.Sprintf("%s %s%s", y, c, suffix))
		}
		evDetail = strings.Join(parts, " | ")
	}

	tierKey := ""
	if t, isStr := e["evidence_tier"].(string); isStr && t != "" {
		tierKey = t
	}
	evFa := insEvFa[tierKey]

	evTag := ""
	switch {
	case truthy(e["consolidated_used"]):
		evTag = "تلفیقی"
	case truthy(e["low_quality_track"]):
		evTag = "میاندوره"
	case truthy(e["relaxed_evidence"]):
		evTag = "حسابرسی‌نشده"
	}
	evBadge := ""
	if !truthy(e["strict_evidence"]) && evTag != "" {
		evBadge = fmt.Sprintf(" (%s)", evTag)
	}

	const title2 = "لایهٔ \u06F2 — سابقهٔ \u06F3 سالهٔ سودسازی (EPS)"
	switch {
	case truthy(e["data_gap"]) && partial:
		// قاعدهٔ جدول: سطر هرگز حذف نمی‌شود — مقادیرِ موجود + «-» برایِ دورهٔ
		// غایب، و عنوان/سلول‌ها قرمز با ذکرِ تعدادِ دوره‌های موجود.
		insights = append(insights, map[string]any{
			"step": "\u06F2", "title": title2, "type": "danger", "partial": true,
			"row":  row["markdown"],
			"text": fmt.Sprintf(
				"🚫 شاخص \u06F2 (تنها %s دوره موجود است) — سابقه EPS: %s ریال · %s",
				faInt(avail), strings.Join(cells, " ← "),
				insOrStr(e["reason"], "کمبود صورت مالی")),
		})
	case truthy(e["na"]):
		// رأیِ \u06F1\u06F3 + جزوۀ ص \u06F4 و رأیِ \u06F1 (بیمه پیش‌گیت): این شاخص داوری **نشده**
		// است — نه مردود و نه سبز (N/A ≠ Reject).
		insights = append(insights, map[string]any{
			"step": "\u06F2", "title": title2, "type": "info", "na": true,
			"row":  row["markdown"],
			"text": fmt.Sprintf("ℹ️ شاخص \u06F2 داوری نمی‌شود (N/A) — %s",
				insOrStr(e["reason"], "مبنایِ غیرتلفیقیِ سه‌سالهٔ کامل موجود نیست")),
		})
	case truthy(e["data_gap"]):
		insights = append(insights, map[string]any{
			"step": "\u06F2", "title": title2, "type": "warning",
			"text": fmt.Sprintf("⚠️ سابقه EPS در دسترس نیست — %s",
				insOrStr(e["reason"], "کمبود صورت مالی")),
		})
	case truthy(e["pass"]):
		interimNote := ""
		if isStrictFalse(e["interim_confirms"]) {
			interimNote = " — ⚠️ عدم تأیید در میاندوره"
		}
		insights = append(insights, map[string]any{
			"step": "\u06F2", "title": title2, "type": "success",
			"text": fmt.Sprintf("✅ روند سودسازی صعودی — EPS: %s ریال (%s)%s%s",
				strings.Join(cells, " ← "),
				insJoinPy(insAnyList(insOr(e["fiscal_years"], []any{})), " ← "),
				evBadge, interimNote),
		})
	default:
		vals := strings.Join(cells, " ← ")
		body := insOrStr(e["reason"], "روند صعودی سه‌ساله برقرار نیست")
		if vals != "" && truthy(e["reason"]) {
			body = fmt.Sprintf("%s | سابقه EPS: %s ریال", pyStr(e["reason"]), vals)
		}
		insights = append(insights, map[string]any{
			"step": "\u06F2", "title": title2,
			"type": insType(truthy(e["soft_gap"]), "warning", "danger"),
			"text": insType(truthy(e["soft_gap"]), "⚠️ ", "🚫 ") + body + evBadge,
		})
	}

	state2a := "pass"
	switch {
	case truthy(e["na"]):
		state2a = "na"
	case partial:
		state2a = "fail" // ناقص = قرمز، نه خاکستری
	case truthy(e["soft_gap"]):
		state2a = "warn"
	case truthy(e["data_gap"]):
		state2a = "nodata"
	default:
		state2a = state(truthy(e["pass"]), false, false)
	}
	label2a := "سابقهٔ \u06F3 سالهٔ EPS"
	if partial {
		label2a += fmt.Sprintf(" (تنها %s دوره موجود است)", faInt(avail))
	}
	allDash := true
	for _, c := range cells {
		if c != "-" {
			allDash = false
			break
		}
	}
	state2b := "warn"
	switch {
	case !truthy(itm["available"]) || allDash:
		state2b = "na"
	case truthy(e["interim_confirms"]):
		state2b = "pass"
	}

	details["\u06F2"] = map[string]any{
		"title": "سابقهٔ سودسازی (EPS سه سال + تداوم میاندوره)",
		"formula": fmt.Sprintf(
			"EPSy > EPSy−1 > EPSy−2 · %s سال مالیِ متوالی · مبنای امروزی: %s · "+
				"تداوم: EPS میاندوره × \u06F1\u06F2÷م ≥ آخرین EPS سال‌پایان",
			insD(th["eps_years"]), insOrStr(evFa, "—")),
		"source": insOrStr(e["source"], "کدال — صورت سود و زیان"),
		"calc": fmt.Sprintf(
			"EPS: %s | متوالی: %s | مثبت: %s | میاندوره %s → برآورد سال %s (تعداد %s)",
			insJoinOr(cells, " | ", "—"),
			insYesNo(e["consecutive_years"]), insYesNo(e["all_profitable"]),
			insOrStr(itm["period_end"], "—"), insN(itm["eps_projected_year"], 2),
			insConfirmLabel(e["interim_confirms"])),
		// سطرِ آمادهٔ جدول (سلول‌ها + markdownِ قرمز در حالتِ ناقص) — برای UI و خروجی
		"period_row": row,
		"what": "لایهٔ سختِ v8 (فقط \u06F1\u06F2ماههٔ حسابرسی‌شدهٔ غیرتلفیقی) روی این دیتابیس " +
			"برای نمادهای زیادی صفر رکورد می‌دهد؛ نسخهٔ \u06F1\u06F0 همان مسیر را با " +
			"سال‌پایان و میاندوره می‌سنجد ولی هر تنزلِ شاهد را صریح برچسب میزند " +
			"تا کاربر بداند EPS از کدالِ غیرتلفیقیِ حسابرسی‌شده آمده یا از " +
			"جایگزین‌های ضعیف‌تر. تداومِ سال جاری هشدارِ نرم است، وتوی سخت نه. " +
			"در کمبودِ دوره هم سطر حذف نمیشود: مقدارِ موجود می‌آید و جایِ " +
			"دورهٔ غایب «-» با سطرِ قرمز. هر اسلاتِ **تلفیقی** رأیِ \u06F1\u06F3 را " +
			"می‌گیرد: شاخص داوری نمی‌شود (N/A)، چون جزوه (ص \u06F4) صورتِ " +
			"تلفیقی را مبنایِ سابقۀ سودسازی نمی‌داند.",
		"subchecks": []map[string]any{
			{
				"key": "2a", "label": label2a, "state": state2a,
				"value":     insJoinOr(cells, " ← ", "—"),
				"threshold": fmt.Sprintf("%s سال صعودی", insD(th["eps_years"])),
				"partial":   partial, "available_periods": avail,
				"periods": row["periods"], "row": row["markdown"],
				"detail": insOrStr(evDetail, "—"),
			},
			{
				"key": "2b", "label": "تداوم در دورهٔ میاندوره‌ای",
				"state":     state2b,
				"value":     pctText(itm["interim_yoy_pct"], true),
				"threshold": "برآورد ≥ آخرین EPS سال‌پایان",
				"detail": fmt.Sprintf("%s · دوره %s",
					insOrStr(itm["annualize_label"], "—"),
					insOrStr(itm["period_end"], "—")),
			},
		},
	}

	// ── لایهٔ \u06F3: حاشیهٔ سود ناخالص ────────────────────────────────────────
	gm := insSubMap(ind, "3")
	const title3 = "لایهٔ \u06F3 — حاشیهٔ سود ناخالص"
	switch {
	case truthy(gm["na"]):
		insights = append(insights, map[string]any{
			"step": "\u06F3", "title": title3, "type": "info",
			"text": fmt.Sprintf("ℹ️ %s", pyStr(gm["reason"])),
		})
	case gm["band"] == "ideal":
		insights = append(insights, map[string]any{
			"step": "\u06F3", "title": title3, "type": "success",
			"text": fmt.Sprintf("✅ حاشیهٔ ناخالص: %s (ایده‌آل ≥ %s٪)",
				pctUnsigned(gm["margin_pct"]), insG(th["margin_ideal"])),
		})
	case truthy(gm["pass"]):
		insights = append(insights, map[string]any{
			"step": "\u06F3", "title": title3, "type": "info",
			"text": fmt.Sprintf("✅ حاشیهٔ ناخالص: %s (قابل‌قبول ≥ %s٪)",
				pctUnsigned(gm["margin_pct"]), insG(th["margin_min"])),
		})
	default:
		insights = append(insights, map[string]any{
			"step": "\u06F3", "title": title3, "type": "warning",
			"text": fmt.Sprintf("⚠️ حاشیهٔ ناخالص: %s (زیر کف %s٪)",
				pctUnsigned(gm["margin_pct"]), insG(th["margin_min"])),
		})
	}

	state3 := "fail"
	if truthy(gm["na"]) {
		state3 = "na"
	} else if truthy(gm["pass"]) {
		state3 = "pass"
	}
	details["\u06F3"] = map[string]any{
		"title": "حاشیهٔ سود ناخالص",
		"formula": fmt.Sprintf(
			"حاشیه = (سود ناخالص ÷ درآمدهای عملیاتی) × \u06F1\u06F0\u06F0 · ایده‌آل ≥ %s٪ · "+
				"قابل‌قبول ≥ %s٪",
			insG(th["margin_ideal"]), insG(th["margin_min"])),
		"source": fmt.Sprintf("کدال — صورت سود و زیان سالانهٔ %s (%s)",
			insOrStr(gm["period_end"], "—"), insOrStr(gm["basis"], "—")),
		"calc": fmt.Sprintf(
			"سود ناخالص %s ÷ درآمدهای عملیاتی %s × \u06F1\u06F0\u06F0 = %s (باند: %s)",
			insN(gm["gross_profit_bt"], 0), insN(gm["revenue_bt"], 0),
			pctUnsigned(gm["margin_pct"]), insOrStr(gm["band"], "—")),
		"what": "سود ناخالص = درآمدهای عملیاتی − بهای تمام‌شدهٔ کالای فروش‌رفته؛ " +
			"سود عملیاتی و سود خالص در این لایه نقشی ندارند.",
		"subchecks": []map[string]any{
			{
				"key": "3", "label": "حاشیهٔ ناخالص", "state": state3,
				"value":     pctUnsigned(gm["margin_pct"]),
				"threshold": fmt.Sprintf("≥ %s٪ (ایده‌آل %s٪)",
					insG(th["margin_min"]), insG(th["margin_ideal"])),
				"detail": fmt.Sprintf("باند: %s", insOrStr(gm["band"], "—")),
			},
		},
	}

	// ── لایهٔ \u06F4: سالانه‌سازیِ پویا + پتانسیل سود به ارزش بازار ────────────
	val := insSubMap(ind, "4")
	ann := insSubMap(val, "annual")
	const title4 = "لایهٔ \u06F4 — پتانسیل سود سالانه به ارزش بازار"
	monthsUsed := insD(ann["months_used"])
	if !truthy(val["available"]) {
		insights = append(insights, map[string]any{
			"step": "\u06F4", "title": title4, "type": "warning",
			"text": fmt.Sprintf("⚠️ %s", insOrStr(val["reason"], "قابل محاسبه نیست")),
		})
	} else {
		potOK := "⚠️"
		if truthy(val["potential_pass"]) {
			potOK = "✅"
		}
		sOK := "⚠️"
		if truthy(val["sales_pass"]) {
			sOK = "✅"
		}
		potTxt := "نامشخص"
		if val["potential_pct"] != nil {
			potTxt = fmt.Sprintf("%s ارزش بازار (کف %s٪)",
				pctUnsigned(val["potential_pct"]),
				insG(insOr(val["potential_threshold"], int64(0))))
		}
		sTxt := "نامشخص"
		if val["sales_to_mcap"] != nil {
			sTxt = fmt.Sprintf("%s× (کف %s×)", insG(val["sales_to_mcap"]),
				insG(insOr(val["sales_threshold"], int64(0))))
		}
		insights = append(insights, map[string]any{
			"step": "\u06F4", "title": title4,
			"type": insType(truthy(val["pass"]), "success", "warning"),
			"text": fmt.Sprintf(
				"%s پتانسیل سود: %s · %s فروش به ارزش بازار: %s (سالانه‌سازی %s ماهه)",
				potOK, potTxt, sOK, sTxt, monthsUsed),
		})
	}

	annualNote := ""
	if truthy(ann["unit_unverified"]) {
		annualNote = " | ⚠️ واحدِ ردیفِ مرجع اعلام نشده — مقیاس راستی‌آزمایی نشد"
	} else if !insReconciled(ann) {
		annualNote = " | ⚠️ Annualized مردود شد → فروش سالانهٔ کدال"
	}
	salesToMcapValue := "—"
	if val["sales_to_mcap"] != nil {
		salesToMcapValue = fmt.Sprintf("%s×", insG(val["sales_to_mcap"]))
	}

	details["\u06F4"] = map[string]any{
		"title": "پتانسیل سود با سالانه‌سازیِ پویا",
		"formula": fmt.Sprintf(
			"م = ماه‌های سپری‌شده از گزارش ماهانه (\u06F1…\u06F1\u06F2) · فروش سالانه = تجمیعی × "+
				"(\u06F1\u06F2 ÷ م) · سود ناخالص پتانسیل = فروش سالانه × حاشیهٔ ناخالص · "+
				"نسبت پتانسیل = سود پتانسیل ÷ ارزش بازار ≥ %s٪ · فروش ÷ ارزش بازار ≥ %s×",
			insG(th["potential_min"]), insG(th["sales_to_mcap_min"])),
		"source": fmt.Sprintf(
			"ارزش بازار: TSETMC (تعداد سهام × قیمت پایانی = %s همت) | فروش و حاشیه: "+
				"کدال — گزارش فعالیت ماهانه + صورت مالی سالانه",
			insN(val["mcap_ht"], 2)),
		"calc": fmt.Sprintf(
			"م = %s → ضریب × %s | %s | سود ناخالص پتانسیل %s میلیارد تومان ÷ ارزش بازار "+
				"%s همت = %s | مبنای حاشیه: %s%s",
			monthsUsed, insN(ann["scale_factor"], 2), insOrStr(ann["basis"], "—"),
			insN(val["est_gross_profit_bt"], 0), insN(val["mcap_ht"], 2),
			pctUnsigned(val["potential_pct"]), insOrStr(val["margin_label"], "—"),
			annualNote),
		"what": "ضریب سالانه‌سازی ثابت نیست: \u06F3 ماه ×\u06F4، \u06F4 ماه ×\u06F3، \u06F5 ماه ×\u06F2٫\u06F4، \u06F6 ماه ×\u06F2 … — " +
			"تا نمادی که \u06F5 ماه از سال مالی‌اش گذشته با فروشِ \u06F5 ماه قضاوت نشود. " +
			"پتانسیل سود روی «سود ناخالص» است نه سود خالص، تا اوراق‌بهادار و " +
			"مواردِ مالیِ یک‌باره در آن راه نیابد.",
		"subchecks": []map[string]any{
			{
				"key": "4a", "label": "فروش سالانه ÷ ارزش بازار",
				"state":     state(truthy(val["sales_pass"]), false, !truthy(val["available"])),
				"value":     salesToMcapValue,
				"threshold": fmt.Sprintf("≥ %s×", insG(insOr(val["sales_threshold"], int64(0)))),
				"detail": fmt.Sprintf("فروش سالانه %s میلیارد تومان (× %s برای %s ماه)",
					insN(val["annual_sales_bt"], 0), insN(ann["scale_factor"], 2), monthsUsed),
			},
			{
				"key": "4b", "label": "پتانسیل سود ناخالص ÷ ارزش بازار",
				"state": state(truthy(val["potential_pass"]), false, val["potential_pct"] == nil),
				"value": pctUnsigned(val["potential_pct"]),
				"threshold": fmt.Sprintf("≥ %s٪",
					insG(insOr(val["potential_threshold"], int64(0)))),
				"detail": fmt.Sprintf("%s × %s = %s میلیارد تومان",
					insN(val["annual_sales_bt"], 0), pctUnsigned(val["margin_used_pct"]),
					insN(val["est_gross_profit_bt"], 0)),
			},
		},
	}

	// ── لایهٔ \u06F5: رژیم قیمت‌گذاری صنعت ─────────────────────────────────────
	sec := insSubMap(ind, "5")
	verdict5 := sec["verdict"]
	sectorName := trimSpace(insOrStr(res["sector"], ""))
	hasSector := sectorName != "" && sectorName != "—"
	secDisplay := "صنعت نامشخص"
	if hasSector {
		secDisplay = sectorName
	}
	matched := insAnyList(insOr(sec["matched_tokens"], []any{}))
	tagline := ""
	if len(matched) > 0 {
		tagline = fmt.Sprintf(" · تگ: %s", insJoinPy(matched, "، "))
	}
	const title5 = "لایهٔ \u06F5 — رژیم قیمت‌گذاری صنعت و چشم‌انداز"
	switch {
	case verdict5 == "mandatory":
		insights = append(insights, map[string]any{
			"step": "\u06F5", "title": title5, "type": "danger",
			"text": fmt.Sprintf(
				"🚫 قیمت‌گذاری دستوری: گروه «%s» مشمول نرخ‌گذاری دستوری است%s",
				secDisplay, tagline),
		})
	case verdict5 == "free":
		insights = append(insights, map[string]any{
			"step": "\u06F5", "title": title5, "type": "success",
			"text": fmt.Sprintf(
				"✅ صنعت آزاد: گروه «%s» آزاد / بورس‌کالایی است%s",
				secDisplay, tagline),
		})
	default:
		text := "ℹ️ صنعت نامشخص در تابلو؛ بررسی موردی"
		if hasSector {
			text = fmt.Sprintf(
				"ℹ️ وضعیت صنعت: گروه «%s» غیردستوری (بررسی تکمیلی)%s",
				secDisplay, tagline)
		}
		insights = append(insights, map[string]any{
			"step": "\u06F5", "title": title5, "type": "info", "text": text,
		})
	}

	panelMode := "Rank_Only"
	if truthy(sec["exclusion_active"]) {
		panelMode = "Exclude_Mandatory_Pricing"
	}
	details["\u06F5"] = map[string]any{
		"title": "رژیم قیمت‌گذاری صنعت",
		"formula": fmt.Sprintf(
			"حالتِ پنل: %s · «دستوری» مردود است مگر حالت Rank_Only انتخاب شود",
			panelMode),
		"source": "گروه صنعت: TSETMC (sector_name) | فهرست صنایع: پنل تنظیمات کدال",
		"calc": fmt.Sprintf(
			"طبقه: %s | تگ خورده: %s | حکم: %s | سهم از کل بازار: %s٪ (تکمیلی)",
			pyStr(verdict5),
			insJoinAnyOr(matched, "، ", "—"),
			insVerdictFa(sec["pass"]), insN(sec["market_share_pct"], 3)),
		"what": sec["outlook"],
		"subchecks": []map[string]any{
			{
				"key": "5", "label": "رژیم قیمت‌گذاری",
				"state":     insType(truthy(sec["pass"]), "pass", "fail"),
				"value":     insOrStr(sec["regime_label"], "—"),
				"threshold": "غیردستوری",
				"detail":    insJoinAnyOr(matched, "، ", "بدون تگ"),
			},
		},
	}

	return insights, details
}

// insType انتخابِ دوگانه‌یِ متن/حالت: اگر شرط برقرار است مقدارِ اول، وگرنه دومی.
func insType(cond bool, yes, no string) string {
	if cond {
		return yes
	}
	return no
}
