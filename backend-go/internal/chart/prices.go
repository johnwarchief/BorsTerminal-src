package chart

import (
	"context"
	"database/sql"
	"fmt"
)

func numOrNil(v sql.NullFloat64) any {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func intOrNil(v sql.NullInt64) any {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func strOrNil(v sql.NullString) any {
	if v.Valid {
		return v.String
	}
	return nil
}

// priceRows تاریخچهٔ یک نماد را با حذفِ تکرارِ روز (پرحجم‌تر می‌ماند) و
// ترتیبِ صعودی برمی‌گرداند — همان قراردادِ key-levels/patterns.
func (s *Service) priceRows(ctx context.Context, symbol string, limit int) ([]map[string]any, error) {
	pred, params := s.pred(ctx, "symbol", symbol)
	q := fmt.Sprintf("SELECT symbol, date, open, high, low, close, volume, last "+
		"FROM price_history WHERE %s ORDER BY date DESC, volume DESC", pred)
	if limit > 0 {
		q += " LIMIT ?"
		params = append(params, limit)
	}
	rs, err := s.market.QueryContext(ctx, q, params...)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	seen := map[string]bool{}
	rows := []map[string]any{}
	for rs.Next() {
		var sym, date string
		var open, high, low, closeP, volume, last sql.NullFloat64
		if err := rs.Scan(&sym, &date, &open, &high, &low, &closeP, &volume, &last); err != nil {
			return nil, err
		}
		if seen[date] {
			continue
		}
		seen[date] = true
		rows = append(rows, map[string]any{
			"symbol": sym, "date": date,
			"open": numOrNil(open), "high": numOrNil(high), "low": numOrNil(low),
			"close": numOrNil(closeP), "volume": numOrNil(volume), "last": numOrNil(last),
		})
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	reverseRows(rows)
	return rows, nil
}

func reverseRows(rows []map[string]any) {
	for i, j := 0, len(rows)-1; i < j; i, j = i+1, j-1 {
		rows[i], rows[j] = rows[j], rows[i]
	}
}
