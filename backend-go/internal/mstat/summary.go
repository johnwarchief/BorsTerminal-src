package mstat

import (
	"database/sql"
	"time"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

// buyPowerUp همان رنگِ قدرت خرید: فقط یک نمایش است — >=۱ سبز، <۱ قرمز، و
// «بی‌داده» (NaN) هرگز سبز نمی‌شود.
func buyPowerUp(p float64) bool { return !isNaN(p) && p >= 1.0 }

// summaryPanel همان summary: ده سطرِ ثابتِ دسته‌ای با شش ستونِ محاسباتی و
// سلامتِ کلان. now تزریق می‌شود تا clock_nowِ طلایی قابلِ سنجش باشد.
func summaryPanel(db *sql.DB, now time.Time) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	buckets := categoryBuckets(rows)
	out := make([]map[string]any, 0, len(categoryRows))
	for _, c := range categoryRows {
		a := aggOf(buckets[c.Key])
		out = append(out, map[string]any{
			"key": c.Key, "label": c.Label,
			"symbols": a.N, "traded": a.NTraded,
			"volume_b_shares":    pyround.Round(a.VolBS, 3),
			"value_b_toman":      pyround.Round(a.ValBT, 1),
			"pc_buy_m_toman":     nilOrRound(a.PCBuymt, 1),
			"pc_sell_m_toman":    nilOrRound(a.PCSellmt, 1),
			"buy_power":          nilOrRound(a.Power, 2),
			"buy_power_up":       buyPowerUp(a.Power),
			"money_flow_b_toman": pyround.Round(a.FlowBT, 1),
		})
	}
	ph := marketphase.FromDB(db, now)
	total, source := marketTotalRials(db)
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"rows": out, "phase": ph,
		// db=nil عینِ فراخوانِ پایتون در summary است: fallbackِ market_liquidity
		// فقط در macro_health (که market_snapshot صدایش می‌زند) فعال است (R2).
		"health": macroHealthFrom(aggOf(buckets["eq_all"]), aggOf(buckets["all"]),
			total, source, &ph, nil),
	}, nil
}
