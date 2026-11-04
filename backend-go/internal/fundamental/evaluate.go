package fundamental

// ستونِ فقراتِ کارت — پورتِ `evaluate_v10` درِ api/fundamental.py:1226-1342.
//
// چهار قیدِ روش‌شناسی که درِ این فایل رعایت شده و نباید شل شوند:
//   1. یکِ کوئریِ سری ماهانه و یکِ صورتِ مالیِ مرجع خوانده می‌شود و به همهٔ
//      لایه‌ها پاس داده می‌شود (ضدِ N+1 خودِ fts_engine)؛ هر لایه نباید دوباره
//      همان ۶۰ ردیف را بخواند.
//   2. فیلترِ صنعت، استثنای دارو/بانک و حکمِ «معافیت از فروش» هر سه از
//      تک‌مرجع‌هایِ `axis45.go` می‌آیند — همان توابعی که مسیرِ اسکرینر می‌زند،
//      وگرنه یکِ نماد در کارت «خنثی» و در قیف «دستوری» می‌شود (واگراییِ
//      سنجیده‌شدۀ ۱۴۰۵-۰۷-۲۳ رویِ ۴۷ نماد).
//   3. آستانه‌ها از پنلِ کانفیگ می‌آیند (`V10Thresholds`)؛ هیچ عددِ تازه‌ای
//      اینجا اختراع نمی‌شود.
//   4. امتیازِ بی‌عدد هرگز None نمی‌شود (اسکرینر رویش sort می‌کند)؛ فقط
//      مسیرِ جزئیات درِ `card.go` آن را خالی نشان می‌دهد.

import (
	"context"
	"math"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// evalCanonicalOrEmpty مثلِ `CP.canonicalize(x) or ""` — دورۀ بی‌تاریخ رشتهٔ
// تهی می‌گیرد، نه «—» (این فیلد دادهٔ جدول است، نه متنِ کاربر).
func evalCanonicalOrEmpty(periodEnd any) string {
	if c := period.Canonicalize(periodEnd); c != nil {
		return *c
	}
	return ""
}

// evalOptFloat مثلِ مقداری که به `gpm`/`sales_growth` پاس داده می‌شود: عدد ⇒
// pointer، None/غایب ⇒ nil (nil با صفر یکی نیست؛ nil یعنی «این شاخص را نمی‌دانم»
// و شاخۀ استثنای دارو/بانک روی همین تفکیک سوار است).
func evalOptFloat(v any) *float64 {
	switch x := v.(type) {
	case nil:
		return nil
	case float64:
		if math.IsNaN(x) {
			return nil
		}
		return &x
	case float32:
		f := float64(x)
		return &f
	case int, int64:
		f := toF(v)
		return &f
	}
	if f, ok := asFloat(v); ok {
		return &f
	}
	return nil
}

// classifyIdentity عینِ `fts_engine.classify_identity` (1977-1998): دروازهٔ
// جهانِ FTS فقط شرکتِ عملیاتیِ دارایِ ابزار را می‌پذیرد. نمادِ بی‌ردیف در
// `instruments` حتی با نام/صنعتِ شرکت «غیرشرکت» است؛ صندوق/اوراق/حق تقدم و
// نهادهایِ عمومی هم داوری نمی‌گیرند. بیمه پیش از توکن‌ها است چون صنعتش
// («بيمه وصندوق بازنشستگي…») کلمهٔ «صندوق» را دارد ولی شرکتِ عملیاتی است.
func classifyIdentity(symbol, sector, companyName string, hasInstrument bool) (kind string, applicable bool, reason string) {
	_ = symbol
	sec := trimSpace(sector)
	name := trimSpace(companyName)
	if !hasInstrument {
		return "non_company", false, "no_instrument"
	}
	if IsInsuranceSector(sec) {
		return "company", true, ""
	}
	if a45FundClassMatch(sec, name) {
		return "fund", false, "fund"
	}
	text := normFa(sec) + " " + normFa(name)
	if a45AnyTokenIn(a45NonCompanyTokens, text) {
		return "non_company", false, "fund_or_non_operating"
	}
	if sec == "" && name == "" {
		return "non_company", false, "no_identity"
	}
	return "company", true, ""
}

// hasInstrument عینِ `bool(inst)` مسیرِ کارت: ردیفِ ابزار در `instruments` با
// همان رزولورِ تابلوی کارت (`l_val18`). خطایِ رزولور مثلِ بقیهٔ مسیرها به شرطِ
// خامِ `l_val18 = ?` می‌افتد؛ خطایِ کوئری ⇒ «ابزار نداریم» (کارت نه ۵۰۰).
func (s *Service) hasInstrument(ctx context.Context, symbol string) bool {
	pred, args, err := s.sid.Pred(ctx, "l_val18", symbol, symbolid.Board)
	if err != nil {
		pred, args = "l_val18 = ?", []any{symbol}
	}
	row, _ := s.queryRow(ctx, "SELECT 1 FROM instruments WHERE "+pred+" LIMIT 1", args)
	return row != nil
}

// EvaluateV10 خروجیِ یکپارچۀ v10: پنج لایه + پاس‌ها + امتیاز + دلایل حذف.
// `m141Map`/`liqMap` برایِ مسیرهایِ دسته‌ای (واچ‌لیست) تزریق می‌شوند تا نقشه‌های
// کل‌بازار یک‌بار ساخته شوند، نه به‌ازای هر نماد؛ nil یعنی «خودت بخوان».
func (s *Service) EvaluateV10(ctx context.Context, symbol string,
	marketCapRials, totalMarketCapRials any, sector string, cfg map[string]any,
	companyName string, m141Map map[string]bool, liqMap map[string]float64) (map[string]any, error) {
	if cfg == nil {
		cfg = map[string]any{}
	}
	th := V10Thresholds(cfg)
	prof := a45CompanyProfile(sector, companyName)
	// هویتِ جهان یک‌بار: پروفایل عینِ تولید می‌ماند (کارت باید طبقهٔ درآمد را
	// نشان دهد)، ولی «قابلِ داوری بودن» از classify_identity می‌آید نه از kind —
	// نمادِ فقط-کدال بی‌ابزار است، هرچند نامش شرکت باشد.
	_, identityApplicable, _ := classifyIdentity(symbol, sector, companyName,
		s.hasInstrument(ctx, symbol))

	series, err := s.MonthlySeries(ctx, symbol, 0)
	if err != nil {
		return nil, err
	}
	ref, err := s.ReferenceAnnual(ctx, symbol, nil)
	if err != nil {
		return nil, err
	}

	growth, err := s.Ind1aMonetaryGrowth(ctx, symbol, series, th, prof)
	if err != nil {
		return nil, err
	}
	volume, err := s.Ind1bVolumeGrowth(ctx, symbol, growth, series, th, prof)
	if err != nil {
		return nil, err
	}
	eps, err := s.Ind2EpsTrack(ctx, symbol, th, sector, nil)
	if err != nil {
		return nil, err
	}
	gm, err := s.Ind3GrossMargin(ctx, symbol, th, ref, prof)
	if err != nil {
		return nil, err
	}
	if truthy(gm["na"]) && len(ref) > 0 {
		rev, net := toF(ref["revenue"]), toF(ref["net_profit"])
		// حاشیۀ جایگزین فقط وقتی معنادار است: مخرج مثبت و نتیجه در بازۀ منطقی.
		// نمادهایی هست که فروشِ صورت‌مالی‌شان کوچک‌تر از سود خالص ثبت شده —
		// حاشیۀ >۱۰۰٪ یعنی واحد/سطرِ گزارش غلط است، نه سودآوری فراوان.
		if rev > 0 && net != 0 {
			mp := net / rev * 100.0
			if mp > 0 && mp <= 100.0 {
				gm["net_margin_pct"] = pyround.Round(mp, 1)
				gm["net_margin_period"] = evalCanonicalOrEmpty(ref["period_end"])
			} else {
				gm["net_margin_rejected_pct"] = pyround.Round(mp, 1)
			}
		}
	}

	// سند v2.1: گیتِ «عدم اعمال نسبت فروش بر هلدینگ‌ها» و حکمِ معافیت از
	// `Ind4Exempt` — همان تابعی که bulk_scan/scan_symbol می‌زنند، پس منطقِ
	// موازیِ دوم اینجا ساخته نمی‌شود.
	holdingsNa := true
	if v, ok := cfg["holdings_sales_na"]; ok {
		holdingsNa = truthy(v)
	}
	ind4Na := s.Ind4Exempt(ctx, symbol, sector, holdingsNa, nil)
	exemptFlag := ind4Na
	annual, err := s.AnnualizedSales(ctx, symbol, ref, series, prof, &exemptFlag)
	if err != nil {
		return nil, err
	}
	val := Ind4Valuation(annual, gm, marketCapRials, th, ind4Na)

	var gpm, salesGrowth *float64
	if gm != nil {
		gpm = evalOptFloat(gm["margin_pct"])
	}
	if growth != nil {
		salesGrowth = evalOptFloat(growth["monetary_pct"])
	}
	sec := Ind5Industry(sector, cfg, marketCapRials, totalMarketCapRials, gpm, salesGrowth)

	// ممیزی (سند v2.1): ارجاع قاعده روی هر شاخص بنیادی.
	growth["rule_ref"] = "F-01"
	volume["rule_ref"] = "F-01b"
	eps["rule_ref"] = "F-02"
	gm["rule_ref"] = "F-03"

	axis1 := Axis1Pass(growth, volume)
	axis2 := truthy(eps["pass"])
	axis3 := truthy(gm["pass"])
	axis4 := truthy(val["pass"])
	axis5 := truthy(sec["pass"])
	passes := map[string]any{
		"1_growth":         axis1,
		"2_eps_trend":      axis2,
		"3_gross_margin":   axis3,
		"4_sales_to_mcap":  axis4,
		"5_industry":       axis5,
		"1a_monetary_growth":  truthy(growth["pass"]),
		"1b_volume_growth":    truthy(volume["pass"]),
		"4a_sales_to_mcap":    truthy(val["sales_pass"]),
		"4b_profit_potential": truthy(val["potential_pass"]),
	}
	score := 0
	for _, k := range []string{"1_growth", "2_eps_trend", "3_gross_margin",
		"4_sales_to_mcap", "5_industry"} {
		if truthy(passes[k]) {
			score++
		}
	}
	// جزوه ص ۶: «سه آیتم اول مهم‌تر هستند» — F1-F3 بلاک‌اند، F4/F5 مرتب‌سازیِ دوم.
	primaryScore := 0
	for _, k := range []string{"1_growth", "2_eps_trend", "3_gross_margin"} {
		if truthy(passes[k]) {
			primaryScore++
		}
	}

	reasons := []string{}
	if strOr(sec["verdict"]) == "mandatory" && truthy(sec["exclusion_active"]) {
		reasons = append(reasons, "قیمت‌گذاری دستوری — حذف خودکار")
	}
	// v10: همهٔ حذف‌های خودکار در یک نقطه — بیمه / تعلیق / ماده ۱۴۱ / کف ارزش
	// بازار / نقدشوندگی / Include-Excludeِ صنایعِ پنل.
	gate := IndustryGate(sector, cfg)
	gateReasons, err := s.RiskGates(ctx, symbol, sector, marketCapRials, cfg, m141Map, liqMap, gate)
	if err != nil {
		return nil, err
	}
	reasons = append(reasons, gateReasons...)

	// رأیِ مالک (۱۴۰۵-۰۷-۰۳): FTS برای شرکت‌های عملیاتی است؛ صندوق و نمادِ
	// بی‌ابزار باید «FTS ندارد» بگیرند نه REJECT با جدولِ خالی.
	applicable := identityApplicable
	verdict := "REJECT"
	switch {
	case !applicable:
		verdict = "FTS ندارد"
	case len(reasons) > 0:
		verdict = "EXCLUDED"
	case score >= 4 && primaryScore == 3:
		verdict = "STRONG"
	case score >= 3:
		verdict = "WATCH"
	}

	valFull := make(map[string]any, len(val)+1)
	for k, v := range val {
		valFull[k] = v
	}
	valFull["annual"] = annual

	return map[string]any{
		"symbol": symbol, "sector": sector, "pricing_mode": sec["verdict"],
		"market_cap_rials": toF(marketCapRials), "score": score,
		"primary_score": primaryScore,
		"applicable":    applicable,
		"passes":        passes,
		// سه‌حالۀ مشترکِ کارت/اسکرینر/قیف (بندِ ۸ معیارهایِ بستنِ پرونده)
		"states": V10AxisStates(map[string]any{
			"1": map[string]any{"monetary": growth, "volume": volume},
			"2": eps, "3": gm, "4": val, "5": sec}, passes),
		"excluded":          len(reasons) > 0,
		"exclusion_reasons": reasons,
		"verdict":           verdict,
		"methodology": map[string]any{
			"version": "FTS-v10", "axes": 5,
			"layer_1_subchecks": []string{"1a_monetary", "1b_volume"},
			"annualization":     "sales_ytd * (12 / elapsed_months)",
			"thresholds":        th},
		"profile": prof, "series_months": len(series), "ref": ref,
		"indicators": map[string]any{
			"1": map[string]any{"monetary": growth, "volume": volume, "pass": axis1},
			"2": eps, "3": gm, "4": valFull, "5": sec},
	}, nil
}
