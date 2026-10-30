package mstat

import (
	"database/sql"
	"math"

	"borsterminal/backend/internal/pyround"
)

// hit همان _hit: بازه‌هایِ (lo, hi] — یک مقدارِ مرزی فقط در یکی از دو سطلِ
// همسایه می‌نشیند، وگرنه جمعِ میله‌ها از تعدادِ نمادها بیشتر می‌شود. دو دُمِ
// باز با ±1e9 نشانه‌گذاری شده‌اند.
func hit(v, lo, hi float64) bool {
	if lo == -1e9 {
		return v <= hi
	}
	if hi == 1e9 {
		return v > lo
	}
	return lo < v && v <= hi
}

// tally همان _tally: خروجی همیشه کلِ spec است (۱۲ یا ۷ میله) — نبودِ داده
// یعنی میلهٔ صفر، نه ناپدیدشدنِ ستون. nil (پایتون None) هیچ سطلی را نمی‌شمارد
// و هر مقدار پس از نخستین تطبیق متوقف می‌شود تا دوبار شمرده نشود.
func tally(pcts []*float64, spec []histoSpec) []map[string]any {
	counts := make([]int, len(spec))
	for _, p := range pcts {
		if p == nil {
			continue
		}
		for i, b := range spec {
			if hit(*p, b.Lo, b.Hi) {
				counts[i]++
				break
			}
		}
	}
	out := make([]map[string]any, len(spec))
	for i, b := range spec {
		out[i] = map[string]any{"key": b.Key, "label": b.Label,
			"color": b.Color, "count": counts[i]}
	}
	return out
}

// histogramPanel همان mstat_engine.histogram: توزیعِ بازدهیِ پایانی، فقط
// نمادهایِ معامله‌شده. not_traded اما رویِ همهٔ ردیف‌هایِ گروه شمرده می‌شود —
// نمادی که حجمش صفر است ممکن است بازدهیِ محاسبه‌شدنی داشته باشد و نباید در
// مخرج/میله‌ها بیاید، ولی «معامله‌نشده» بودنش باید دیده شود.
func histogramPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	sel := []*Row{}
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol > 0 {
			sel = append(sel, r)
		}
	}
	pcts := make([]*float64, 0, len(sel))
	known := 0
	for _, r := range sel {
		pcts = append(pcts, r.Pct)
		if r.Pct != nil {
			known++
		}
	}
	notTraded := 0
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol <= 0 {
			notTraded++
		}
	}
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "basis": "closing_vs_yesterday", "traded_only": true,
		"histo12": tally(pcts, histo12), "histo7": tally(pcts, histo7),
		"known": known, "nodata": len(pcts) - known, "total": len(sel),
		"not_traded": notTraded,
	}, nil
}

// depthPanel همان mstat_engine.depth: ارزشِ ۵ خطِ اولِ دفتر + تفکیکِ سه‌گانهٔ
// صف. «بی‌داده» (همگام‌نشده) از «صفر» جدا می‌شود؛ هر ردیف فقط وقتی در
// symbols_with_depth می‌آید که bq_val خودش NULL نباشد.
func depthPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	have := []*Row{}
	for _, r := range rows {
		if inCategory(r, group, nil) && !isNaN(r.M.BQVal) {
			have = append(have, r)
		}
	}
	buyVal, sellVal := 0.0, 0.0
	for _, r := range have {
		buyVal += zeroIfNaN(r.M.BQVal)
		sellVal += zeroIfNaN(r.M.SQVal)
	}
	// one تفکیکِ یک‌طرفه را می‌سنجد: یک‌طرفه‌بودنِ دفتر شرطِ صف است («کمتر از
	// مبنا» فقط وقتی معنا دارد که طرفِ مقابل خالی باشد). «بدونِ معامله» پیش از
	// مقایسهٔ مبنا می‌آید؛ مبنایِ نامعلوم (NaN) سطلِ خودش را دارد.
	one := func(side string) map[string]any {
		normal, below, noTrade, unknown := 0, 0, 0, 0
		for _, r := range have {
			qv, opp := r.M.BQVal, r.M.SQVal
			if side == "sell" {
				qv, opp = r.M.SQVal, r.M.BQVal
			}
			if isEmpty(qv) || !isEmpty(opp) {
				continue
			}
			if r.M.Vol <= 0 {
				noTrade++
				continue
			}
			qvol := r.M.BQVol
			if side == "sell" {
				qvol = r.M.SQVol
			}
			base := r.M.Base
			if isNaN(base) || isNaN(qvol) {
				unknown++
			} else if qvol < base {
				below++
			} else {
				normal++
			}
		}
		return map[string]any{"normal": normal, "below_base": below,
			"no_trade": noTrade, "base_unknown": unknown}
	}
	bqCnt, sqCnt := 0, 0
	for _, r := range have {
		if r.M.QState == "b" {
			bqCnt++
		}
		if r.M.QState == "s" {
			sqCnt++
		}
	}
	var ratio any
	if sellVal != 0 {
		ratio = pyround.Round(buyVal/sellVal, 2)
	}
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "depth_available": len(have) > 0,
		"symbols_with_depth": len(have),
		"buy_queue_b_toman":  pyround.Round(buyVal/1e10, 1),
		"sell_queue_b_toman": pyround.Round(sellVal/1e10, 1),
		"ratio":              ratio, "buy_queue_count": bqCnt, "sell_queue_count": sqCnt,
		"buy": one("buy"), "sell": one("sell"),
	}, nil
}

// entryOpportunityNegPct همان ENTRY_OPPORTUNITY_NEG_PCTِ mstat_engine است.
const entryOpportunityNegPct = 80.0

// entryOpportunity همان قاعدهٔ «فرصتِ ورود»: سهمِ منفی‌هایِ *نگردشده* باید
// به ۸۰٪ برسد. پایتون `neg_pct >= ENTRY_OPPORTUNITY_NEG_PCT` را پیش از round
// می‌سنجد؛ با نسبتِ گردشده گروهی با ۷۹٫۹۹٪ پس از گردکردن ۸۰٫۰ می‌شد و قانون
// بی‌آنکه سزاوار باشد روشن می‌شد. مخرجِ صفر یعنی نسبت نامعلوم، نه ۰٪.
func entryOpportunity(neg, known int) bool {
	if known == 0 {
		return false
	}
	return 100.0*float64(neg)/float64(known) >= entryOpportunityNegPct
}

// thermometerPanel همان mstat_engine.thermometer: نوارِ دو‌رنگِ مثبت/منفی +
// قانونِ «فرصتِ ورود» (منفی‌ها ≥ ۸۰٪، رویِ نسبتِ نگردشده — entryOpportunity).
//
// مانند هیستوگرام فقط نمادهایِ معامله‌شده شمرده می‌شوند؛ قانون رویِ فهرستِ
// معامله‌نشده‌ها همیشه «فرصتِ ورود»ِ جعلی می‌سازد. درصدها با مخرجِ صفر None
// می‌مانند، نه ۰.
func thermometerPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	sel := []*Row{}
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol > 0 {
			sel = append(sel, r)
		}
	}
	pos, neg, flat := 0, 0, 0
	for _, r := range sel {
		switch {
		case r.Pct != nil && *r.Pct > 0:
			pos++
		case r.Pct != nil && *r.Pct < 0:
			neg++
		case r.Pct != nil && *r.Pct == 0:
			flat++
		}
	}
	known := pos + neg + flat
	var posPct, negPct any
	if known > 0 {
		posPct = pyround.Round(100.0*float64(pos)/float64(known), 1)
		negPct = pyround.Round(100.0*float64(neg)/float64(known), 1)
	}
	entry := entryOpportunity(neg, known)
	notTraded := 0
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol <= 0 {
			notTraded++
		}
	}
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "positive": pos, "negative": neg, "zero": flat,
		"nodata": len(sel) - known, "not_traded": notTraded,
		"positive_pct": posPct, "negative_pct": negPct,
		"entry_opportunity": entry, "entry_rule_pct": entryOpportunityNegPct,
	}, nil
}

// tabCat همان _TAB_CAT: نامِ تبِ رابط → دستهٔ in_category.
var tabCat = map[string]string{
	"all": "all", "eq_funds": "eq_all", "stock": "stock_right", "eq_fund": "eq_fund",
	"fixed": "fixed_fund", "top50": "top50", "lev": "lev_fund",
	"gold": "gold_fund", "silver": "silver_fund",
}

// sideShare همان client_split.side_share: سهمِ حقیقی از ارزشِ یک سمت (۰ تا ۱۰۰)
// یا nil یعنی نامشخص. منفی، NaN/±Inf و مخرجِ صفر «نامشخص»اند، نه صفر؛ منفی
// بودنِ ارزشِ یک گروه معنایِ فنی ندارد. پایتون همین‌ها را در money() رد می‌کند.
func sideShare(retail, legal float64) any {
	if isNaN(retail) || isNaN(legal) || math.IsInf(retail, 0) || math.IsInf(legal, 0) ||
		retail < 0 || legal < 0 {
		return nil
	}
	den := retail + legal
	if den <= 0 {
		return nil
	}
	return pyround.Round(100.0*retail/den, 1)
}

// complement سهمِ حقوقیِ همان سمت: مکملِ سهمِ حقیقیِ *گردشده*. سمتِ نصفه‌نیمه
// درصد ندارد (nil می‌ماند). محاسبهٔ مستقلِ 100*legal/den یک گردکردنِ دوم
// می‌سازد که با سهمِ حقیقی به ۱۰۰ نمی‌رسد (مثلاً ۰٫۱ + ۹۹٫۸).
func complement(share any) any {
	if share == nil {
		return nil
	}
	return pyround.Round(100.0-share.(float64), 1)
}

// nilOrRound قراردادِ «NaN یعنی NULL» برایِ ارقامِ گردشده: NaN ⇒ nil، وگرنه
// roundِ پایتون. این تابع مالِ واحدِ ۵B است؛ Task 6 نباید دوباره تعریفش کند.
func nilOrRound(v float64, n int) any {
	if isNaN(v) {
		return nil
	}
	return pyround.Round(v, n)
}

// clientSplitPanel همان mstat_engine.client_split: تعداد/ارزش/درصدِ خرید و
// فروشِ حقیقی در برابر حقوقی، به تفکیکِ تب.
//
// درصدها از همان کسرِ تک‌تعریفِ client_split می‌آیند: سهمِ حقوقی مکملِ سهمِ
// حقیقیِ همان سمت است، نه یک گردکردنِ مستقل. تبِ ناشناخته به دستهٔ all برمی‌گردد
// ولی نامِ خامِ tab در پاسخ می‌ماند.
func clientSplitPanel(db *sql.DB, tab string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	cat, ok := tabCat[tab]
	if !ok {
		cat = "all"
	}
	a := aggOf(selectRows(rows, cat))
	rbuy := sideShare(a.RB, a.IB)
	rsell := sideShare(a.RS, a.IS)
	bt := func(v float64) float64 { return pyround.Round(v/1e10, 1) }
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"tab": tab, "symbols": a.N,
		"retail": map[string]any{
			"buy_count": a.NBI, "buy_b_toman": bt(a.RB), "buy_pct": rbuy,
			"sell_count": a.NSI, "sell_b_toman": bt(a.RS), "sell_pct": rsell,
		},
		"institutional": map[string]any{
			"buy_count": a.NBN, "buy_b_toman": bt(a.IB), "buy_pct": complement(rbuy),
			"sell_count": a.NSN, "sell_b_toman": bt(a.IS), "sell_pct": complement(rsell),
		},
		"pc_buy_m_toman":     nilOrRound(a.PCBuymt, 1),
		"pc_sell_m_toman":    nilOrRound(a.PCSellmt, 1),
		"power":              nilOrRound(a.Power, 2),
		"money_flow_b_toman": pyround.Round(a.FlowBT, 1),
	}, nil
}
