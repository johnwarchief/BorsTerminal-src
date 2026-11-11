package chart

import (
	"context"
	"database/sql"

	candlecontract "borsterminal/backend/internal/candle"
)

// measuredFactorEvents returns the reference-measured adjustment factors when
// the independent candle DB carries them (Phase 4.9.2). A missing table or a
// symbol without rows is not an error: older DBs keep the pack/official path.
func (s *Service) measuredFactorEvents(ctx context.Context, symbol string) ([]canonEvent, string, bool) {
	rows, err := s.market.QueryContext(ctx,
		"SELECT date, ratio, kind, revision FROM adjustment_factors "+
			"WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		return nil, "", false
	}
	defer rows.Close()
	out := []canonEvent{}
	revision := ""
	for rows.Next() {
		var d, kind, rev sql.NullString
		var ratio sql.NullFloat64
		if err := rows.Scan(&d, &ratio, &kind, &rev); err != nil {
			return nil, "", false
		}
		if !d.Valid || !ratio.Valid || ratio.Float64 <= 0 {
			continue
		}
		e := canonEvent{Date: date10(d.String), Ratio: ratio.Float64,
			Source: "rahavard-type7-type0"}
		if kind.Valid && kind.String != "" {
			e.Extra = map[string]any{"kind": kind.String}
		}
		out = append(out, e)
		if rev.Valid && rev.String != "" {
			revision = rev.String
		}
	}
	if len(out) == 0 {
		return nil, "", false
	}
	return out, revision, true
}

// referenceRawHistory returns the captured Rahavard type0 raw candles for a
// symbol covered by the independent DB. The Seed's price_history is never
// modified; this is a separate, provenance-carrying raw series.
func (s *Service) referenceRawHistory(ctx context.Context, symbol string) ([]map[string]any, bool, error) {
	rows, err := s.market.QueryContext(ctx,
		"SELECT date, open, high, low, close, volume FROM reference_raw "+
			"WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		return nil, false, nil
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var date sql.NullString
		var open, high, low, closeP, volume sql.NullFloat64
		if err := rows.Scan(&date, &open, &high, &low, &closeP, &volume); err != nil {
			return nil, false, err
		}
		if !date.Valid || date.String == "" || !closeP.Valid || closeP.Float64 <= 0 {
			continue
		}
		v := 0.0
		if volume.Valid {
			v = volume.Float64
		}
		if v <= 0 {
			continue
		}
		o := 0.0
		if open.Valid {
			o = open.Float64
		}
		if o <= 0 {
			o = closeP.Float64
		}
		hRaw, lRaw := 0.0, 0.0
		if high.Valid {
			hRaw = high.Float64
		}
		if low.Valid {
			lRaw = low.Float64
		}
		h, l := candlecontract.Widen(o, hRaw, lRaw, closeP.Float64, 0)
		out = append(out, map[string]any{
			"symbol": symbol, "time": date.String, "date": date.String,
			"open": o, "high": h, "low": l, "high_raw": hRaw, "low_raw": lRaw,
			"close": closeP.Float64, "last": nil, "value": nil,
			"volume": v, "src": "rahavard-type0",
		})
	}
	if err := rows.Err(); err != nil {
		return nil, false, err
	}
	return out, len(out) > 0, nil
}

// ChainFactors exposes the canonical backward factor chain for the DB builder.
// The anchor is the largest candle date; an event with date > t multiplies the
// factor for every bar at or before its own date.
func ChainFactors(times []string, dates []string, ratios []float64) []float64 {
	events := make([]chainEvent, 0, len(dates))
	for i := range dates {
		if i < len(ratios) {
			events = append(events, chainEvent{Date: dates[i], Ratio: ratios[i],
				Kind: "source_ratio"})
		}
	}
	factors, _ := chainFactors(times, events)
	return factors
}
