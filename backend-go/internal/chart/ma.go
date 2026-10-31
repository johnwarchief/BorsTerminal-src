package chart

import (
	"context"
	"database/sql"
	"fmt"

	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/pyround"
)

var maWindows = []int{5, 20, 50, 120}

func clampMaDays(days int) int {
	if days == 0 {
		days = 730
	}
	if days < 120 {
		days = 120
	}
	if days > 2000 {
		days = 2000
	}
	return days
}

func (s *Service) maPriceRows(ctx context.Context, symbol string, days int) ([]map[string]any, error) {
	pred, params := s.pred(ctx, "symbol", symbol)
	q := fmt.Sprintf("SELECT date, close, volume, last FROM price_history WHERE %s "+
		"ORDER BY date DESC, volume DESC LIMIT ?", pred)
	rs, err := s.market.QueryContext(ctx, q, append(params, days)...)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	seen := map[string]bool{}
	rows := []map[string]any{}
	for rs.Next() {
		var date string
		var closeP, volume, last sql.NullFloat64
		if err := rs.Scan(&date, &closeP, &volume, &last); err != nil {
			return nil, err
		}
		if seen[date] {
			continue
		}
		seen[date] = true
		rows = append(rows, map[string]any{"date": date, "close": numOrNil(closeP),
			"volume": numOrNil(volume), "last": numOrNil(last)})
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	reverseRows(rows)
	return rows, nil
}

func (s *Service) maBody(ctx context.Context, symbol string, days int) map[string]any {
	days = clampMaDays(days)
	basis := s.basis.Current()
	ck := fmt.Sprintf("%s|%d|%s", symbol, days, basis)
	if body, ok := s.cacheGet(s.ma, ck, maTTL); ok {
		return body
	}
	rows, err := s.maPriceRows(ctx, symbol, days)
	if err != nil {
		return map[string]any{"status": "error", "message": err.Error()}
	}
	maRows := make([]map[string]any, len(rows))
	for i, r := range rows {
		maRows[i] = map[string]any{"time": r["date"], "close": r["close"], "last": r["last"]}
	}
	pricebasis.ApplyBasis(maRows, false, basis)
	type point struct {
		day   string
		close float64
	}
	closes := []point{}
	for _, c := range maRows {
		if v, ok := c["close"].(float64); ok {
			closes = append(closes, point{c["time"].(string), v})
		}
	}
	ma := map[string]any{}
	for _, w := range maWindows {
		ser := make([]any, 0, len(closes))
		acc := 0.0
		for i, p := range closes {
			acc += p.close
			if i >= w {
				acc -= closes[i-w].close
			}
			if i >= w-1 {
				ser = append(ser, []any{p.day, pyround.Round(acc/float64(w), 2)})
			} else {
				ser = append(ser, []any{p.day, nil})
			}
		}
		ma[fmt.Sprintf("ma%d", w)] = ser
	}
	out := map[string]any{"status": "ok", "symbol": symbol,
		"periods": append([]int(nil), maWindows...), "ma": ma,
		"events": s.calEventsFor(symbol), "bars": len(closes)}
	s.cachePut(s.ma, ck, out)
	return out
}
