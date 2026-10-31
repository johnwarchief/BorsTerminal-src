package chart

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
)

const noDepthMessage = "عمقِ پنج‌سطحی این نماد ذخیره نشده — بعد از نخستین همگام‌سازیِ تابلو می‌آید"

func noDataBook(symbol string) map[string]any {
	return map[string]any{"status": "no_data", "symbol": symbol,
		"levels": []map[string]any{}, "message": noDepthMessage}
}

func (s *Service) orderBookBody(ctx context.Context, symbol string) map[string]any {
	pred, params := s.pred(ctx, "l_val18", symbol)
	var ins string
	err := s.market.QueryRowContext(ctx, fmt.Sprintf(
		"SELECT ins_code FROM instruments WHERE %s ORDER BY updated_at DESC LIMIT 1", pred),
		params...).Scan(&ins)
	if err == sql.ErrNoRows {
		return noDataBook(symbol)
	}
	if err != nil {
		return map[string]any{"status": "error", "symbol": symbol,
			"levels": []map[string]any{}, "message": err.Error()}
	}
	var bookTxt sql.NullString
	var dEven, hEven sql.NullInt64
	var updated sql.NullString
	var buyVol, buyCnt, sellVol, sellCnt sql.NullFloat64
	err = s.market.QueryRowContext(ctx,
		"SELECT b.book_txt, b.d_even, b.h_even, b.updated_at,"+
			" m.buy_q_vol, m.buy_q_cnt, m.sell_q_vol, m.sell_q_cnt"+
			" FROM order_book b LEFT JOIN market_watch m ON m.ins_code = b.ins_code"+
			" WHERE b.ins_code = ?", ins).Scan(&bookTxt, &dEven, &hEven, &updated,
		&buyVol, &buyCnt, &sellVol, &sellCnt)
	if err != nil && err != sql.ErrNoRows {
		// بانکی که جدولِ عمق ندارد ⇒ «بی‌داده»، نه خطا (همان OperationalErrorِ پایتون).
		return noDataBook(symbol)
	}
	if err == sql.ErrNoRows || !bookTxt.Valid || bookTxt.String == "" {
		return noDataBook(symbol)
	}
	var raw []any
	if err := json.Unmarshal([]byte(bookTxt.String), &raw); err != nil {
		return map[string]any{"status": "error", "symbol": symbol,
			"levels": []map[string]any{}, "message": err.Error()}
	}
	levels := []map[string]any{}
	for _, item := range raw {
		ln, ok := item.([]any)
		if !ok {
			continue
		}
		if len(ln) < 6 {
			return map[string]any{"status": "error", "symbol": symbol,
				"levels": []map[string]any{}, "message": "خطِ عمقِ ناقص"}
		}
		levels = append(levels, map[string]any{
			"buy_px": ln[0], "buy_vol": ln[1], "buy_cnt": ln[2],
			"sell_px": ln[3], "sell_vol": ln[4], "sell_cnt": ln[5],
		})
	}
	return map[string]any{
		"status": "ok", "symbol": symbol, "levels": levels,
		"session": map[string]any{
			"d_even": intOrNil(dEven), "h_even": intOrNil(hEven), "updated_at": strOrNil(updated),
		},
		"totals": map[string]any{
			"buy_vol": numOrNil(buyVol), "buy_cnt": numOrNil(buyCnt),
			"sell_vol": numOrNil(sellVol), "sell_cnt": numOrNil(sellCnt),
		},
	}
}
