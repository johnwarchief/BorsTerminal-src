package mstat

import (
	"database/sql"
	"time"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

// smartMoneyPanel همان mstat_engine.smart_money: بنرِ نقدینگیِ کلان، شرطِ
// هشدارِ ۸۰٪، جریانِ خردِ سهام ⇄ درآمد ثابت، و حکمِ امروز در همان یک بدنه.
//
// هیچ عددی این‌جا فرمولِ دوم نمی‌گیرد: macro از همان macroHealthFrom،
// watch_entry از همان قاعدهٔ ۸۰٪ِ thermometer، و verdict از dayVerdict.
// now فقط برایِ marketphase.FromDB است؛ ساعتِ داده از h_even می‌آید.
func smartMoneyPanel(db *sql.DB, now time.Time, memo *verdictMemo) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	ph := marketphase.FromDB(db, now)
	buckets := categoryBuckets(rows)
	eq := aggOf(buckets["eq_all"])
	sr := aggOf(buckets["stock_right"])
	fx := aggOf(buckets["fixed_fund"])
	allm := aggOf(buckets["all"])

	total, source := marketTotalRials(db)
	macro := macroHealthFrom(eq, allm, total, source, &ph, db)

	// شرطِ هشدارِ ۸۰٪ رویِ نمادهایِ معامله‌شدهٔ سهام/حق‌تقدم؛ «منفی» یا «صفِ فروش».
	known, bearish := 0, 0
	for _, r := range buckets["stock_right"] {
		if r.M.Vol <= 0 {
			continue
		}
		if r.Pct != nil {
			known++
		}
		if (r.Pct != nil && *r.Pct < 0) || r.M.QState == "s" {
			bearish++
		}
	}
	var bearPct any
	active := false
	if known != 0 {
		v := 100.0 * float64(bearish) / float64(known)
		active = v >= entryOpportunityNeg
		bearPct = pyround.Round(v, 1)
	}

	eqFlow := pyround.Round(eq.FlowBT, 1)
	fxFlow := pyround.Round(fx.FlowBT, 1)
	var gdFlow any
	if gold := aggOf(buckets["gold_fund"]); gold.N > 0 {
		gdFlow = pyround.Round(gold.FlowBT, 1)
	}
	flowOut := map[string]any{
		"eq_flow_b_toman": eqFlow, "fixed_flow_b_toman": fxFlow,
		"eq_inflow": eqFlow > 0, "fixed_outflow": fxFlow < 0,
		"ideal_fts":         eqFlow > 0 && fxFlow < 0,
		"gold_flow_b_toman": gdFlow, "gold_outflow": nil,
		"eq_value_b_toman":    pyround.Round(eq.ValBT, 1),
		"fixed_value_b_toman": pyround.Round(fx.ValBT, 1),
		"sr_flow_b_toman":     pyround.Round(sr.FlowBT, 1),
	}
	if gdFlow != nil {
		flowOut["gold_outflow"] = gdFlow.(float64) < 0
	}
	trio, _ := flowTrio(flowOut)
	flowOut["trio_fts"] = trio

	// مرحل درِ خودِ macro هم می‌نشیند تا خواننده بداند جمع «تا-لحظه» است یا نهایی.
	phaseID := ph.Phase
	if s, ok := macro["phase"].(string); ok && s != "" {
		phaseID = s
	}
	phaseLabel := ph.Label
	if s, ok := macro["phase_label"].(string); ok && s != "" {
		phaseLabel = s
	}
	sessionDay := ph.SessionDay
	if v, ok := macro["session_day"].(*int64); ok && v != nil {
		sessionDay = v
	}
	macroOut := map[string]any{
		"value_hemat": macro["value_hemat"], "state": macro["state"],
		"label": macro["label"], "basis": macro["basis"],
		"trade_value_all_market_hemat": macro["trade_value_all_market_hemat"],
		"market_value_hemat":           macro["market_value_hemat"],
		"market_value_source":          macro["market_value_source"],
		"excellent":                    macro["excellent"], "cause": macro["cause"],
		"index": marketIndex(db),
		"phase": phaseID, "phase_label": phaseLabel, "session_day": sessionDay,
		"session_is_live": ph.IsLive,
		"partial_session": ph.Phase == marketphase.Continuous,
		"good_min":        hematGood,
		"bad_max":         hematBad,
	}
	entryOut := map[string]any{
		"active": active, "bearish_pct": bearPct,
		"rule_pct": entryOpportunityNeg, "bearish": bearish, "known": known,
	}
	asof := asOfMap(snap, len(top50Codes(snap.Rows)), len(rows))
	out := map[string]any{
		"status": "ok", "asof": asof, "macro": macroOut,
		"watch_entry": entryOut, "flow": flowOut,
	}
	out["verdict"] = dayVerdict(db, macroOut, entryOut, flowOut, asof, ph, memo)
	return out, nil
}
