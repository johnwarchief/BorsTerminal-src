package mstat

import (
	"database/sql"
	"time"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

// optZero همان _opt در market_index_series: _f (NaN/Inf ⇒ 0) و بعد صفر ⇒
// null. «صفر» عددِ باورپذیرِ شاخص نیست و نباید به‌جایِ «غایب» بنشیند.
func optZero(v float64) any {
	v = f0(v)
	if v == 0 {
		return nil
	}
	return v
}

// marketIndexSeries همان market_index_series؛ جدولِ نبود/خطا ⇒ nil.
// ستون‌هایِ گردش در بانکِ کهنه نیستند؛ آن‌جا null برمی‌گردند، نه صفر.
// ترتیب: تازه‌ترین اول. خطایِ میانِ جریان کلِ سری را دور می‌ریزد (fetchall).
func marketIndexSeries(db *sql.DB, limit int) []map[string]any {
	n := limit
	if n < 1 {
		n = 1
	}
	if n > 60 {
		n = 60
	}
	wide := `SELECT d_even, idx_last, idx_change, idx_pct, ew_last, ew_change,
	    ew_pct, z_tot_tran, q_tot_cap, q_tot_tran FROM market_index
	    ORDER BY d_even DESC LIMIT ?`
	rows, err := db.Query(wide, n)
	hasTotals := true
	if err != nil {
		rows, err = db.Query(`SELECT d_even, idx_last, idx_change, idx_pct,
		    ew_last, ew_change, ew_pct FROM market_index
		    ORDER BY d_even DESC LIMIT ?`, n)
		hasTotals = false
	}
	if err != nil {
		return nil
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var d sql.NullInt64
		vals := make([]sql.NullFloat64, 9)
		ptrs := []any{&d}
		for i := range vals {
			ptrs = append(ptrs, &vals[i])
		}
		if hasTotals {
			if err := rows.Scan(ptrs...); err != nil {
				return nil
			}
		} else {
			// پایتون در بانکِ کهنه فقط هفت ستون می‌خواند: d_even + شش عدد.
			if err := rows.Scan(ptrs[:7]...); err != nil {
				return nil
			}
		}
		o := func(v sql.NullFloat64) any {
			if !v.Valid {
				return nil
			}
			return optZero(v.Float64)
		}
		m := map[string]any{
			"d_even": d.Int64,
			"last":   o(vals[0]), "change": o(vals[1]), "pct": o(vals[2]),
			"ew_last": o(vals[3]), "ew_change": o(vals[4]), "ew_pct": o(vals[5]),
			"z_tot_tran": nil, "q_tot_cap": nil, "q_tot_tran": nil,
		}
		if hasTotals {
			m["z_tot_tran"] = o(vals[6])
			m["q_tot_cap"] = o(vals[7])
			m["q_tot_tran"] = o(vals[8])
		}
		out = append(out, m)
	}
	if err := rows.Err(); err != nil {
		return nil
	}
	return out
}

// marketIndex همان market_index: فقط هفت کلیدِ شاخص، بدونِ ستون‌هایِ گردش.
func marketIndex(db *sql.DB) map[string]any {
	series := marketIndexSeries(db, 1)
	if len(series) == 0 {
		return nil
	}
	s := series[0]
	return map[string]any{
		"d_even": s["d_even"], "last": s["last"], "change": s["change"],
		"pct": s["pct"], "ew_last": s["ew_last"], "ew_change": s["ew_change"],
		"ew_pct": s["ew_pct"],
	}
}

// boardRialsEstimate همان board_estimate: جمعِ dedupedِ market_capِ آخرین
// نشست با حذفِ ردیف‌هایِ هم‌تعدادِ سهام (یک شرکت در چند بازار).
func boardRialsEstimate(db *sql.DB) float64 {
	var sum sql.NullFloat64
	err := db.QueryRow(`SELECT SUM(mc) FROM (SELECT MAX(market_cap) AS mc
	    FROM market_watch WHERE market_cap > 0
	    AND d_even = (SELECT MAX(d_even) FROM market_watch)
	    GROUP BY total_shares)`).Scan(&sum)
	if err != nil || !sum.Valid {
		return 0
	}
	return f0(sum.Float64)
}

// marketTotalRials همان market_total_rials: عددِ رسمی اگر باورپذیر باشد،
// وگرنه جمعِ dedupedِ تابلو، وگرنه صفر با منبعِ unavailable.
//
// ردیفِ نصفه باورپذیر نیست: سینکِ ناقص عدد را کوچک می‌کند، پس فقط پایین‌تر از
// نصفِ مرجع (جمعِ تابلو، یا بزرگ‌ترین ردیفِ موجود) رد می‌شود. بزرگ‌تر بودنِ
// عددِ رسمی خطا نیست (تابلو همهٔ بازارها را ندارد).
func marketTotalRials(db *sql.DB) (float64, string) {
	est := boardRialsEstimate(db)
	vals := []float64{}
	rows, err := db.Query(`SELECT d_even, market_value FROM market_totals
	    ORDER BY d_even DESC LIMIT 5`)
	if err == nil {
		ok := true
		for rows.Next() {
			var d sql.NullInt64
			var v sql.NullFloat64
			if rows.Scan(&d, &v) != nil {
				ok = false
				break
			}
			if v.Valid {
				if x := f0(v.Float64); x > 0 {
					vals = append(vals, x)
				}
			}
		}
		if rows.Err() != nil {
			ok = false
		}
		rows.Close()
		if !ok {
			vals = nil
		}
	}
	if len(vals) > 0 {
		lo := est
		if lo <= 0 {
			lo = vals[0]
			for _, v := range vals {
				if v > lo {
					lo = v
				}
			}
		}
		lo *= 0.5
		for _, v := range vals { // تازه‌ترینِ باورپذیر
			if v >= lo {
				return v, "tse_market_overview"
			}
		}
	}
	if est > 0 {
		return est, "board_sum_deduped"
	}
	return 0, "unavailable"
}

// macroHealthFrom همان macro_health_from. مرحلِ بی‌اجازه «بدون داده» می‌دهد نه
// «نامساعد»؛ eqِ بی‌معامله هم عددِ صفر نیست. db فقط برایِ fallbackِ
// market_liquidity است و فقط market_snapshot آن را می‌دهد (R2).
func macroHealthFrom(eq, all *Agg, totalRials float64, totalSource string,
	ph *marketphase.Phase, db *sql.DB) map[string]any {
	var marketValue any
	if totalRials > 0 {
		marketValue = pyround.Round(totalRials/1e13, 1)
	}
	if ph != nil && !ph.VerdictAllowed {
		why := []string{}
		for _, k := range ph.NotComputable {
			if k == "order_pressure" {
				continue
			}
			why = append(why, ph.WhyNot[k])
		}
		label := ph.Label
		if label == "" {
			label = "بدون داده"
		}
		return map[string]any{
			"value_hemat": nil, "state": "nodata", "label": label,
			"basis": "eq_all", "phase": ph.Phase, "phase_source": ph.PhaseSource,
			"phase_official": ph.Official, "session_day": ph.SessionDay,
			"why": why, "trade_value_all_market_hemat": nil,
			"market_value_hemat":  marketValue,
			"market_value_source": nilIfEmpty(totalSource),
			"excellent":           false, "good_min": 20.0, "bad_max": 10.0,
		}
	}
	if eq == nil || eq.NTraded == 0 {
		var lastSess, lastVal any
		if db != nil {
			var d sql.NullInt64
			var v sql.NullFloat64
			if db.QueryRow(`SELECT d_even, value_hemat FROM market_liquidity
			    WHERE value_hemat > 0 ORDER BY d_even DESC LIMIT 1`).
				Scan(&d, &v) == nil {
				lastSess = d.Int64
				lastVal = pyround.Round(f0(v.Float64), 2)
			}
		}
		cause := "unknown"
		if ph != nil && ph.IsLive {
			cause = "no_trades_yet"
		}
		var phase, src, day any
		if ph != nil {
			phase, src, day = ph.Phase, ph.PhaseSource, ph.SessionDay
		}
		return map[string]any{
			"value_hemat": nil, "state": "nodata", "label": "بدون داده",
			"basis": "eq_all", "cause": cause, "session_day": day,
			"phase": phase, "phase_source": src,
			"last_traded_session": lastSess, "last_value_hemat": lastVal,
			"trade_value_all_market_hemat": nil,
			"market_value_hemat":           marketValue,
			"market_value_source":          nilIfEmpty(totalSource),
			"excellent":                    false, "good_min": 20.0, "bad_max": 10.0,
		}
	}
	hemat := eq.ValHemat
	state, label := "mid", "متوسط"
	if hemat >= 20.0 {
		state, label = "good", "مساعد"
	} else if hemat <= 10.0 {
		state, label = "bad", "نامساعد"
	}
	out := map[string]any{
		"value_hemat": pyround.Round(hemat, 2), "state": state, "label": label,
		"basis": "eq_all", "excellent": hemat >= 50.0,
		"good_min": 20.0, "bad_max": 10.0, "excellent_min": 50.0,
		"trade_value_all_market_hemat": nil, "market_value_hemat": marketValue,
		"market_value_source": nilIfEmpty(totalSource),
	}
	if all != nil {
		out["trade_value_all_market_hemat"] = pyround.Round(all.ValHemat, 2)
	}
	if ph != nil {
		out["phase"] = ph.Phase
		out["phase_label"] = ph.Label
		out["phase_source"] = ph.PhaseSource
		out["phase_official"] = ph.Official
		out["session_day"] = ph.SessionDay
		out["session_is_live"] = ph.IsLive
	}
	return out
}

// macroHealth همان macro_health: eq_all داور است و کلِ بازار فقط گزارش می‌شود.
func macroHealth(db *sql.DB, now time.Time) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	ph := marketphase.FromDB(db, now)
	total, source := marketTotalRials(db)
	return macroHealthFrom(aggOf(selectRows(rows, "eq_all")), aggOf(selectRows(rows, "all")),
		total, source, &ph, db), nil
}

// marketSnapshotPanel همان market_snapshot: شاخص، نشستِ قبل، بازار و خرد.
// prev خودِ ردیفِ دومِ سری است (نه زیرمجموعه)؛ نبودش null است، نه صفر.
func marketSnapshotPanel(db *sql.DB, now time.Time) (map[string]any, error) {
	series := marketIndexSeries(db, 2)
	var cur map[string]any
	var prev any
	if len(series) > 0 {
		cur = series[0]
	}
	if len(series) > 1 {
		prev = series[1]
	}
	macro, err := macroHealth(db, now)
	if err != nil {
		return nil, err
	}
	var index any
	// پایتون همیشه asof را شیء می‌دهد: {"d_even": None} وقتی سری خالی است.
	asof := map[string]any{"d_even": nil}
	var tradeValue, volume, trades any
	if cur != nil {
		index = map[string]any{
			"d_even": cur["d_even"], "last": cur["last"], "change": cur["change"],
			"pct": cur["pct"], "ew_last": cur["ew_last"],
			"ew_change": cur["ew_change"], "ew_pct": cur["ew_pct"],
		}
		asof["d_even"] = cur["d_even"]
		if v, ok := cur["q_tot_cap"].(float64); ok && v != 0 {
			tradeValue = pyround.Round(v/1e13, 2)
		}
		volume = cur["q_tot_tran"]
		trades = cur["z_tot_tran"]
	}
	// retail فقط همان هشت کلیدِ پایتون را دارد؛ cause/excellent_min در شاخهٔ
	// عادی غایب‌اند و دسترسیِ map در Go همان null را می‌دهد.
	retail := map[string]any{
		"value_hemat": macro["value_hemat"], "state": macro["state"],
		"label": macro["label"], "basis": macro["basis"],
		"cause": macro["cause"], "good_min": macro["good_min"],
		"bad_max": macro["bad_max"], "excellent_min": macro["excellent_min"],
	}
	return map[string]any{
		"status": "ok", "asof": asof, "index": index, "prev": prev,
		"market": map[string]any{
			"trade_value_hemat": tradeValue, "volume": volume, "trades": trades,
			"market_value_hemat": macro["market_value_hemat"],
		},
		"retail": retail,
	}, nil
}
