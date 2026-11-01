package mstat

import (
	"bytes"
	"compress/zlib"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"math"
	"time"
)

// InTradingSession بررسی می‌کند که آیا ساعت بازار و زمان مشخص در بازه معاملات است یا خیر.
// بازه ساعت: 08:55:00 الی 13:00:05. پنجشنبه و جمعه خارج از بازار محسوب می‌شوند.
func InTradingSession(hEven int64, now time.Time) bool {
	if hEven < 85500 || hEven > 130005 {
		return false
	}
	wd := now.Weekday()
	if wd == time.Thursday || wd == time.Friday {
		return false
	}
	return true
}

func encStates(states map[string]string) (string, error) {
	data, err := json.Marshal(states)
	if err != nil {
		return "", err
	}
	var buf bytes.Buffer
	zw, err := zlib.NewWriterLevel(&buf, 6)
	if err != nil {
		return "", err
	}
	if _, err := zw.Write(data); err != nil {
		_ = zw.Close()
		return "", err
	}
	if err := zw.Close(); err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(buf.Bytes()), nil
}

// SnapshotAgg معادل snapshot_agg در mstat_engine.py است و مقادیر اسکالر تجمیعی بازار را محاسبه می‌کند.
func SnapshotAgg(db *sql.DB) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	snap.Rows = enrich(snap)
	allr := aggOf(snap.Rows)

	var eqRows []*Row
	var fxRows []*Row
	var have []*Row
	pos := 0
	neg := 0
	zero := 0
	st := make(map[string]string)

	for _, r := range snap.Rows {
		if inCategory(r, "eq_all", nil) {
			eqRows = append(eqRows, r)
		}
		if inCategory(r, "fixed_fund", nil) {
			fxRows = append(fxRows, r)
		}
		if r.Pct != nil {
			if *r.Pct > 0 {
				pos++
			} else if *r.Pct < 0 {
				neg++
			} else if *r.Pct == 0 {
				zero++
			}
		}
		if !isNaN(r.M.BQVal) {
			have = append(have, r)
		}
		if r.M.QState != "" && r.M.QState != "none" {
			st[r.Code] = r.M.QState
		}
	}

	eq := aggOf(eqRows)
	fx := aggOf(fxRows)

	blob, err := encStates(st)
	if err != nil {
		return nil, err
	}

	var sumBQ, sumSQ float64
	bqN := 0
	sqN := 0
	for _, r := range have {
		if !isNaN(r.M.BQVal) {
			sumBQ += r.M.BQVal
		}
		if !isNaN(r.M.SQVal) {
			sumSQ += r.M.SQVal
		}
		if r.M.QState == "b" {
			bqN++
		} else if r.M.QState == "s" {
			sqN++
		}
	}

	var day any
	if snap.AsOf.DEven != nil {
		day = *snap.AsOf.DEven
	}

	res := map[string]any{
		"d_even":        day,
		"h_even":        snap.AsOf.HEven,
		"val_bt":        math.Round(allr.ValBT*10) / 10,
		"flow_eq_bt":    math.Round(eq.FlowBT*10) / 10,
		"flow_fixed_bt": math.Round(fx.FlowBT*10) / 10,
		"pos":           pos,
		"neg":           neg,
		"zero":          zero,
		"bq_bt":         math.Round((sumBQ/1e10)*10) / 10,
		"sq_bt":         math.Round((sumSQ/1e10)*10) / 10,
		"bq_n":          bqN,
		"sq_n":          sqN,
		"st":            blob,
	}
	if !isNaN(eq.PCBuymt) {
		res["pc_buy"] = math.Round(eq.PCBuymt*10) / 10
	} else {
		res["pc_buy"] = nil
	}
	if !isNaN(eq.PCSellmt) {
		res["pc_sell"] = math.Round(eq.PCSellmt*10) / 10
	} else {
		res["pc_sell"] = nil
	}

	return res, nil
}

// SaveSnapshot ذخیره نقطه در mstat_snap را شبیه save_mstat_snapshot در پایتون انجام می‌دهد.
func (s *Service) SaveSnapshot(now time.Time) (map[string]any, error) {
	agg, err := SnapshotAgg(s.db)
	if err != nil {
		return nil, err
	}
	var hEven int64
	if h, ok := agg["h_even"].(int64); ok {
		hEven = h
	}
	if !InTradingSession(hEven, now) {
		return map[string]any{
			"status": "ok",
			"saved":  false,
			"reason": "outside_trading_session",
			"d_even": agg["d_even"],
			"h_even": agg["h_even"],
		}, nil
	}
	aggJSON, err := json.Marshal(agg)
	if err != nil {
		return nil, err
	}
	nowStr := now.Format("2006-01-02 15:04:05")
	_, err = s.db.Exec(`INSERT OR REPLACE INTO mstat_snap (d_even, h_even, ts, agg) VALUES (?,?,?,?)`,
		agg["d_even"], agg["h_even"], nowStr, string(aggJSON))
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"status": "ok",
		"saved":  true,
		"d_even": agg["d_even"],
		"h_even": agg["h_even"],
	}, nil
}
