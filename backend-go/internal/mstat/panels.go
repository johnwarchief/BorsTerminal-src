package mstat

import (
	"database/sql"

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
