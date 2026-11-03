package fundamental

// کارتِ بنیادی پنج‌محور — پورتِ `get_fundamental` (api/fundamental.py:2002-2212).
//
// پنج قیدِ شکست‌ناپذیرِ روش‌شناسی:
//   1. هویتِ نماد و کلاسِ تابلو از تک‌منبعِ symbolid می‌آید؛ هیچ الحاقِ رقمیِ
//      دستی در کار نیست.
//   2. ارزشِ بازار فقط از ستونِ رسمیِ تابلو (MarketCapInfo) خوانده می‌شود؛ ضربِ
//      «قیمت × سهام» عمداً در فازِ ۱۰ حذف شده و اینجا هم احیا نمی‌شود.
//   3. امتیازِ نهایی فقط در صورتی که applicable=true باشد عدد است؛ در صندوق‌ها
//      و قراردادهای اختیار nil (None) می‌ماند.
//   4. هر پنج محور از تک‌توابعِ همان بسته تغذیه می‌شوند تا حکمِ کارت با
//      اسکرینر و نبضِ بازار هرگز واگرا نشود.
//   5. پیامِ ۵۰۱ حذف و مسیر مستقیماً روی HTTP سرو می‌شود.

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strings"

	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

var ErrSymbolNotFound = errors.New("Symbol not found")

const instrSQLTmpl = "SELECT i.ins_code, i.sector_name, i.total_shares, m.p_closing, i.l_val18, i.l_val30" +
	" FROM instruments i" +
	" LEFT JOIN market_watch m ON i.ins_code = m.ins_code" +
	" WHERE %s" +
	" ORDER BY i.updated_at DESC LIMIT 1"

var optContractRe = regexp.MustCompile(`\S+\s+([^\s-]+)[\s-]?`)

func sectorFromCompany(companyName string) string {
	n := normFa(companyName)
	if strings.Contains(n, "صندوق") {
		return "صندوق سرمایه گذاری"
	}
	if strings.Contains(n, "بیمه") {
		return "بیمه"
	}
	if strings.Contains(n, "لیزینگ") {
		return "لیزینگ"
	}
	if strings.Contains(n, "بانك") || strings.Contains(n, "بانک") {
		return "بانك"
	}
	return "سایر"
}

func orDash(v any) string {
	if isFalsy(v) {
		return "—"
	}
	return pyStr(v)
}

// cardAcceptancePath عینِ `fts_engine.i4_acceptance_path` (2128-2142): فقط نامِ
// مسیری که حکم را ساخت — ۰٫۳۳× فروش÷ارزش بازار مقدم است و ۴۰٪ پتانسیل مسیرِ
// دوم. nil یعنی هیچ‌کدام (یا معاف/بی‌داده)؛ دروازهٔ تازه‌ای اینجا ساخته نمی‌شود.
func cardAcceptancePath(salesPass, potentialPass bool) any {
	if salesPass {
		return "sales_to_mcap"
	}
	if potentialPass {
		return "profit_potential"
	}
	return nil
}

// cardAnnualizeLabel عینِ `fts_engine.annualize_label` (2117-2125): صفر/None
// یعنی دوره‌ای برایِ سالانه‌سازی نیست ⇒ رشتهٔ خالی، نه «دورهٔ ۰ ماهه». «12» رقمِ
// لاتین است (همان `%d`ِ پایتون) و «سالانه‌شده» با نیم‌فاصله.
func cardAnnualizeLabel(months int64) string {
	if months == 0 {
		return ""
	}
	return fmt.Sprintf("سالانه‌شده از دورهٔ %d ماهه", months)
}

// v10DataGaps هر لایه‌ای که «قابل محاسبه نبود» شد + راه‌حلِ عملیِ بستنِ شکاف
// (عینِ v10_data_gaps در api/fundamental.py:1796-1863).
func v10DataGaps(res map[string]any) []map[string]any {
	ind, _ := res["indicators"].(map[string]any)
	if ind == nil {
		ind = map[string]any{}
	}
	l1, _ := ind["1"].(map[string]any)
	if l1 == nil {
		l1 = map[string]any{}
	}
	g, _ := l1["monetary"].(map[string]any)
	if g == nil {
		g = map[string]any{}
	}
	v, _ := l1["volume"].(map[string]any)
	if v == nil {
		v = map[string]any{}
	}
	e, _ := ind["2"].(map[string]any)
	if e == nil {
		e = map[string]any{}
	}
	m, _ := ind["3"].(map[string]any)
	if m == nil {
		m = map[string]any{}
	}
	val, _ := ind["4"].(map[string]any)
	if val == nil {
		val = map[string]any{}
	}
	ann, _ := val["annual"].(map[string]any)
	if ann == nil {
		ann = map[string]any{}
	}

	gaps := make([]map[string]any, 0)
	if truthy(g["data_gap"]) {
		why := strOr(g["reason"])
		fix := strOr(g["remediation"])
		if fix == "" {
			fix = ax1MsGapHint
		}
		gaps = append(gaps, map[string]any{
			"layer": "۱الف", "axis": "1a_monetary_growth",
			"why": why, "fix": fix,
		})
	}
	if strOr(v["basis"]) == "unavailable" {
		why := strOr(v["reason"])
		if why == "" {
			why = "رشد ریالی محاسبه نشد تا رشد تولیدی بررسی شود."
		}
		gaps = append(gaps, map[string]any{
			"layer": "۱ب", "axis": "1b_physical_volume",
			"why": why,
			"fix": "با همگام‌سازیِ گزارش فعالیت ماهانه (مخرجِ همان دورهٔ سال قبل) این محور ساخته می‌شود.",
		})
	} else if truthy(v["data_gap"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۱ب", "axis": "1b_physical_volume",
			"why": strOr(v["reason"]), "fix": "گزارش ماهانهٔ سال قبل لازم است.",
		})
	}
	if truthy(e["na"]) {
		why := strOr(e["reason"])
		if why == "" {
			why = "مبنایِ غیرتلفیقیِ سه‌سالهٔ کامل موجود نیست."
		}
		gaps = append(gaps, map[string]any{
			"layer": "۲", "axis": "2_eps_trend", "na": true,
			"why": why,
			"fix": "این شکاف با گرفتنِ دیتابیسِ تازهٔ کدال بسته نمی‌شود: صورتِ سود و زیانِ غیرتلفیقیِ آن سال‌ها منتشر نشده است.",
		})
	} else if truthy(e["data_gap"]) {
		avail := 0
		if v, ok := asInt(e["available_periods"]); ok {
			avail = v
		}
		req := 3
		if v, ok := asInt(e["years_required"]); ok {
			req = v
		}
		gaps = append(gaps, map[string]any{
			"layer": "۲", "axis": "2_eps_trend", "why": strOr(e["reason"]),
			"available_periods": avail,
			"required_periods":  req,
			"partial":           truthy(e["partial"]),
			"fix": "با گرفتنِ دیتابیس تازهٔ کدال، صورت‌های ۱۲ماههٔ سال‌های قدیمی‌ترِ همین نماد اضافه می‌شود.",
		})
	} else if truthy(e["soft_gap"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۲", "axis": "2_eps_trend", "why": strOr(e["reason"]),
			"fix": "با انتشار صورت ۱۲ماههٔ سال مالی جاری، داوری قطعی میشود.",
		})
	}
	if truthy(m["na"]) {
		why := strOr(m["reason"])
		if why == "" {
			why = "سود ناخالصِ سالِ مرجع در کدال نیست."
		}
		fix := strOr(m["remediation"])
		if fix == "" {
			fix = "با همگام‌سازی کدال بررسی مجدد می‌شود."
		}
		gaps = append(gaps, map[string]any{
			"layer": "۳", "axis": "3_gross_margin",
			"why": why, "fix": fix,
		})
	}
	if truthy(ann["unit_unverified"]) {
		gaps = append(gaps, map[string]any{
			"layer": "۴", "axis": "4_sales_to_mcap",
			"why": "واحدِ پولِ ردیفِ مرجعِ کدال اعلام نشده، پس مقیاسِ این عدد راستی‌آزمایی نشد (گیتِ واحد بی‌شاهد اجرا شد).",
			"fix": "با همگام‌سازیِ تازهٔ کدال، ستونِ واحدِ همان صورتِ مالی پر می‌شود و مقایسه برقرار می‌گردد.",
		})
	} else if r, ok := ann["reconciled"].(bool); ok && !r {
		gaps = append(gaps, map[string]any{
			"layer": "۴", "axis": "4_sales_to_mcap",
			"why": "سالانه‌سازی ×۱۲÷م با گیتِ fts_engine سازگار نشد؛ فروش سالانهٔ کدال جانشین شد.",
			"fix": "گزارش‌های ماهانهٔ کاملِ همان سال مالی لازم است.",
		})
	}
	return gaps
}

// CardBody عینِ get_fundamental: کارتِ پنج‌لایهٔ FTS v10.
func (s *Service) CardBody(ctx context.Context, symbol string, months int) (map[string]any, int, error) {
	pk, pa, err := s.sid.Pred(ctx, "i.l_val18", symbol, symbolid.Board)
	if err != nil {
		pk, pa = "i.l_val18 = ?", []any{symbol}
	}
	instRows, err := s.rows(ctx, fmt.Sprintf(instrSQLTmpl, pk), pa)
	if err != nil {
		return nil, 500, err
	}
	var inst map[string]any
	if len(instRows) > 0 {
		inst = instRows[0]
	}

	companyName, _ := s.CompanyNameOf(ctx, symbol)
	var sector string
	if inst == nil {
		if companyName == "" {
			return nil, 404, ErrSymbolNotFound
		}
		sector = sectorFromCompany(companyName)
	} else {
		sector = strOr(inst["sector_name"])
	}

	normSymbol := symbol
	var refReason any = nil
	optionContract := false
	if inst == nil {
		cands, ev, _ := s.sid.ClassSiblings(ctx, symbol)
		if len(cands) > 0 {
			ck, ca, err := s.sid.Pred(ctx, "i.l_val18", cands[0], symbolid.Board)
			if err != nil {
				ck, ca = "i.l_val18 = ?", []any{cands[0]}
			}
			i2Rows, err := s.rows(ctx, fmt.Sprintf(instrSQLTmpl, ck), ca)
			if err != nil {
				return nil, 500, err
			}
			if len(i2Rows) > 0 {
				inst = i2Rows[0]
				sector = strOr(inst["sector_name"])
				normSymbol = cands[0]
				refReason = fmt.Sprintf("نمادِ پایه درِ کدال؛ خطِ کلاسِ تابلو «%s» — شاهد: %s", cands[0], ev)
			}
		}
	}

	mcapInfo := s.MarketCapInfo(ctx, normSymbol)
	totalMcap, _ := s.BoardTotalMarketCap(ctx)
	mcap := mcapInfo["rials"]

	cfg := LoadFtsConfig(s.dataDir)
	res, err := s.EvaluateV10(ctx, normSymbol, mcap, totalMcap, sector, cfg, companyName, nil, nil)
	if err != nil {
		return nil, 500, err
	}

	ind := res["indicators"].(map[string]any)
	val4 := ind["4"].(map[string]any)
	val4["market_cap_source"] = mcapInfo["source"]
	val4["market_cap_error"] = mcapInfo["error"]
	val4["market_cap_asof"] = mcapInfo["asof"]
	val4["market_cap_stale"] = truthy(mcapInfo["stale"])
	if mcapInfo["rials"] == nil {
		val4["available"] = false
		val4["data_gap"] = true
		errCode := strOr(mcapInfo["error"])
		if errCode == "" {
			errCode = "بدون کد خطا"
		}
		val4["reason"] = fmt.Sprintf(
			"ارزش بازار از اسنپ‌شاتِ رسمیِ TSETMC خوانده نشد (%s)؛ فروش÷ارزش و "+
				"پتانسیل سود محاسبه نمیشوند — پیش از «گزارش ماهانه»، تابلوخوانیِ این "+
				"نماد باید تازه شود.", errCode)
	}

	insights, details := BuildInsights(res)
	g := ind["1"].(map[string]any)["monetary"].(map[string]any)
	v := ind["1"].(map[string]any)["volume"].(map[string]any)
	e := ind["2"].(map[string]any)
	gm := ind["3"].(map[string]any)
	val := ind["4"].(map[string]any)
	sec := ind["5"].(map[string]any)
	annual, _ := val["annual"].(map[string]any)
	if annual == nil {
		annual = map[string]any{}
	}

	// شکلِ کارتِ شاخص ۱ عینِ `evaluate_v10` (1547-1548): {monetary, volume,
	// pass, reason} — `series`ِ خامِ سری ماهانه درِ اندیکاتور نمی‌نشیند (دادهٔ
	// خامِ جدول است، نه حکم) و `pass` همان سه‌حالِ `axis1_state` است، پس برایِ
	// شکافِ داده null می‌ماند نه false (طلاییِ card_thin). `passes.1_growth`
	// هم از همان سه‌حال می‌آید تا کارت و `states` یک حرف بزنند.
	delete(g, "series")
	axis1State, axis1Reason := Axis1State(g, v)
	ind1 := ind["1"].(map[string]any)
	ind1["pass"] = axis1State
	ind1["reason"] = axis1Reason
	if p, ok := res["passes"].(map[string]any); ok {
		p["1_growth"] = axis1State
	}

	// سه فیلدِ نمایشیِ شاخص ۴ (Task 7) — از خودِ حکمِ موجود ساخته می‌شوند، نه
	// دروازهٔ تازه: مسیرِ پذیرش، تعدادِ ماهِ سالانه‌سازی و برچسبش. کارت پیش از
	// این آن‌ها را نداشت ولی طلایی/اوراکل دارند (`ind4_valuation` 1230-1234).
	annualizeMonths := ax1IntOf(annual["months_used"])
	val["acceptance_path"] = cardAcceptancePath(truthy(val["sales_pass"]),
		truthy(val["potential_pass"]))
	val["annualize_months"] = annualizeMonths
	val["annualize_label"] = cardAnnualizeLabel(annualizeMonths)

	var refSymbol any = nil
	if normSymbol != symbol {
		refSymbol = normSymbol
	}
	if inst != nil && strings.HasPrefix(strOr(inst["l_val18"]), "ض") && strOr(inst["l_val30"]) != "" {
		if sub := optContractRe.FindStringSubmatch(strOr(inst["l_val30"])); len(sub) > 1 && sub[1] != "" {
			underlying := sub[1]
			pProbe, aProbe, err := s.sid.Pred(ctx, "l_val18", underlying, symbolid.Board)
			if err != nil {
				pProbe, aProbe = "l_val18 = ?", []any{underlying}
			}
			probeRow, _ := s.queryRow(ctx, "SELECT 1 FROM instruments WHERE "+pProbe+" LIMIT 1", aProbe)
			if probeRow != nil {
				refSymbol = underlying
				refReason = "قرارداد اختیار معامله — تحلیل به نماد اصلی آن"
				optionContract = true
			}
		}
	}
	if optionContract {
		res["applicable"] = false
		res["verdict"] = "FTS ندارد"
	}

	if truthy(res["excluded"]) {
		reasons := []string{}
		if list, ok := res["exclusion_reasons"].([]string); ok {
			reasons = list
		} else if list, ok := res["exclusion_reasons"].([]any); ok {
			for _, item := range list {
				reasons = append(reasons, pyStr(item))
			}
		}
		joined := "⚠️ " + strings.Join(reasons, " · ")
		item := map[string]any{
			"step":  "۰",
			"title": "حذف خودکار از غربالگری FTS",
			"type":  "danger",
			"text":  joined,
		}
		insights = append([]map[string]any{item}, insights...)
	}

	var ps any = nil
	if stm := toF(val["sales_to_mcap"]); stm != 0 {
		ps = pyround.Round(1.0/stm, 3)
	}
	epsSlots := e["period_slots"]
	if epsSlots == nil {
		epsSlots = []any{}
	}
	epsAvail := 0
	if a, ok := asInt(e["available_periods"]); ok {
		epsAvail = a
	}
	thMap := V10Thresholds(cfg)
	epsReq := 3
	if r, ok := asInt(e["years_required"]); ok {
		epsReq = r
	} else if r, ok := asInt(thMap["eps_years"]); ok {
		epsReq = r
	}
	var epsProjYear any = nil
	if interim, ok := e["interim"].(map[string]any); ok {
		epsProjYear = interim["eps_projected_year"]
	}

	var roePct any = nil
	prof := res["profile"].(map[string]any)
	// `margin_class` (fts_engine.company_profile:2014-2024) فقط متنِ N/Aِ شاخص ۳
	// را دقیق می‌کند: بانک زیرِ kind=holding می‌افتد ولی «هلدینگ/سرمایه‌گذاری»
	// خواندنش غلط است. پروفایلِ موتور این کلید را ندارد (axis45.go)، پس کارت
	// همان کلید را با همان قاعده کنارِ label می‌گذارد — حکم/امتیاز دست‌نخورده.
	if _, ok := prof["margin_class"]; !ok {
		marginClass := strOr(prof["kind"])
		if marginClass == "holding" &&
			a45AnyTokenIn(a45BankTokens, normFa(sector)+" "+normFa(companyName)) {
			marginClass = "bank"
			prof["label"] = "بانک / مؤسسهٔ اعتباری"
		}
		prof["margin_class"] = marginClass
	}
	qtyVerifiedStr := "خیر — کمیتِ گزارش‌شدۀ همان دوره در دسترس نبود؛ تعدیل تورمی مصرف شد"
	if truthy(v["quantity_verified"]) {
		qtyVerifiedStr = "بله"
	}

	var annualMonthsUsed any = "None"
	if annual["months_used"] != nil {
		annualMonthsUsed = annual["months_used"]
	}

	secondary := map[string]any{
		"طبقهٔ شرکت": fmt.Sprintf("%s — %s", prof["label"], prof["revenue_basis"]),
		"مبنای حجم (لایهٔ ۱ب)": fmt.Sprintf("%s · اطمینان %s · تناژ گزارش‌شده: %s",
			orDash(v["basis"]), orDash(v["confidence"]), qtyVerifiedStr),
		"سالانه‌سازی (لایهٔ ۴)": fmt.Sprintf("م = %v ماه × ۱۲÷م = ×%s — %s",
			annualMonthsUsed, insN(annual["scale_factor"], 2), orDash(annual["basis"])),
	}

	if mcapInfo["rials"] != nil {
		src := pyStr(mcapInfo["source"])
		srcFa := src
		switch src {
		case "tse_raw":
			srcFa = "فیلدِ خامِ تابلوی TSETMC"
		case "tse_board_calc":
			srcFa = "اسنپ‌شاتِ تابلوی TSETMC (pcl×ztd در زمانِ سینک)"
		case "tse_board_calc_backfill":
			srcFa = "اسنپ‌شاتِ ذخیره‌شدهٔ TSETMC (مهاجرت v10)"
		case "unknown":
			srcFa = "اسنپ‌شاتِ تابلوی TSETMC"
		}
		staleNote := ""
		if truthy(mcapInfo["stale"]) {
			staleNote = " · تاریخچهٔ اسنپ‌شات (نماد امروز بی‌عدد)"
		}
		secondary["ارزش بازار"] = fmt.Sprintf("%s همت — منبع: %s%s", insN(mcapInfo["hmt"], 2), srcFa, staleNote)
		if mcapInfo["asof"] != nil {
			secondary["تاریخ ارزش بازار"] = pyStr(mcapInfo["asof"])
		}
	} else {
		errStr := pyStr(mcapInfo["error"])
		errFa := errStr
		if errFa == "" || errFa == "None" {
			errFa = "دلیل نامشخص"
		}
		switch errStr {
		case "symbol_not_on_board":
			errFa = "نماد در اسنپ‌شاتِ تابلو نیست (فقط-کدال)"
		case "market_cap_column_missing":
			errFa = "ستون ارزش بازار هنوز در market.db ساخته نشده"
		case "market_cap_missing_value":
			errFa = "تابلو برای این نماد ارزش بازارِ معتبر ندارد"
		case "market_cap_invalid_value":
			errFa = "مقدار ذخیره‌شده نامعتبر است"
		}
		secondary["ارزش بازار"] = "موجود نیست — " + errFa
	}
	secondary["سهم بازار"] = fmt.Sprintf("%s٪ از کل بازار (تکمیلی)", insN(toF(sec["market_share_pct"]), 3))

	if refRow, ok := res["ref"].(map[string]any); ok && len(refRow) > 0 {
		fp, fa, err := s.sid.Pred(ctx, "symbol", normSymbol, symbolid.Codal)
		if err != nil {
			fp, fa = "symbol = ?", []any{normSymbol}
		}
		qArgs := append(append([]any{}, fa...), refRow["period_end"])
		teRow, err := s.queryRow(ctx, "SELECT total_equity FROM financial_statements WHERE "+fp+
			" AND period_end=? ORDER BY tracing_no DESC LIMIT 1", qArgs)
		if err == nil && teRow != nil {
			te := toF(teRow[0])
			np := toF(refRow["net_profit"])
			if te > 0 && np != 0 {
				r := pyround.Round(np/te*100.0, 1)
				roePct = r
				secondary["ROE"] = fmt.Sprintf("%s٪ (تکمیلی)", insN(r, 1))
			}
		}
	}

	metrics := map[string]any{
		"mcap":                 toF(mcap),
		"mcap_source":          mcapInfo["source"],
		"mcap_asof":            mcapInfo["asof"],
		"mcap_stale":           truthy(mcapInfo["stale"]),
		"mcap_error":           mcapInfo["error"],
		"mcap_hmt":             mcapInfo["hmt"],
		"annual_sales_bt":      annual["annual_sales_bt"],
		"revenue":              annual["annual_sales_mrl"],
		"sales_to_mcap":        val["sales_to_mcap"],
		"ps":                   ps,
		"gross_margin":         gm["margin_pct"],
		"net_margin":           gm["net_margin_pct"],
		"growth_pct":           g["monetary_pct"],
		"monetary_growth_pct":  g["monetary_pct"],
		"volume_growth_pct":    v["volume_pct"],
		"real_growth_pct":      v["real_pct"],
		"volume_basis":         v["basis"],
		"quantity_verified":    truthy(v["quantity_verified"]),
		"eps_series":           e["eps_series"],
		"eps_slots":            epsSlots,
		"eps_partial":          truthy(e["partial"]),
		"eps_available":        epsAvail,
		"eps_required":         epsReq,
		"eps_projected_year":   epsProjYear,
		"profit_potential_pct": val["potential_pct"],
		"potential_pct":        val["potential_pct"],
		"months_used":          annual["months_used"],
		"scale_factor":         annual["scale_factor"],
		"roe":                  roePct,
	}

	rawHistory, err := s.AnnualStatements(ctx, normSymbol, true, true, 6)
	if err != nil {
		return nil, 500, err
	}
	history := make([]map[string]any, 0, len(rawHistory))
	for _, r := range rawHistory {
		history = append(history, map[string]any{
			"period_end":   evalCanonicalOrEmpty(r["period_end"]),
			"fiscal_year":  r["fiscal_year"],
			"revenue":      r["revenue"],
			"gross_profit": r["gross_profit"],
			"net_profit":   r["net_profit"],
			"eps":          r["basic_eps"],
			"audited":      r["audited"],
			"consolidated": r["consolidated"],
		})
	}

	applicable := true
	if a, ok := res["applicable"].(bool); ok {
		applicable = a
	}
	var score any = nil
	if applicable {
		score = res["score"]
	}

	return map[string]any{
		"status":            "success",
		"symbol":            symbol,
		"sector":            sector,
		"pricing_mode":      res["pricing_mode"],
		"score":             score,
		"verdict":           res["verdict"],
		"applicable":        applicable,
		"excluded":          res["excluded"],
		"exclusion_reasons": res["exclusion_reasons"],
		"passes":            res["passes"],
		"states":            res["states"],
		"methodology":       res["methodology"],
		"profile":           res["profile"],
		"indicators":        ind,
		"metrics":           metrics,
		"insights":          insights,
		"details":           details,
		"data_gaps":         v10DataGaps(res),
		"secondary":         secondary,
		"history":           history,
		"thresholds":        cardThresholds(cfg),
		"ref_symbol":        refSymbol,
		"ref_reason":        refReason,
		"fs_count":          len(history),
	}, 200, nil
}
