package store

import (
	"database/sql"
	"errors"
	"fmt"
	"log"
	"strings"
	"sync"
)

// Frame قابِ ستون‌محور است: هر ستون یک []any به ترتیبِ ردیف‌هایِ تابلو.
type Frame struct {
	Codes []string
	Cols  map[string][]any
}

func (f *Frame) N() int { return len(f.Codes) }

// LoadBoard همان کوئریِ پایتون را رویِ market.dbِ فقط‌خواندنی اجرا می‌کند.
func LoadBoard(db *sql.DB) (*Frame, error) {
	text, err := boardSQL(db)
	if err != nil {
		return nil, err
	}
	rows, err := db.Query(text)
	if err != nil {
		return nil, fmt.Errorf("board query: %w", err)
	}
	defer rows.Close()
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	idx := -1
	for i, c := range cols {
		if c == "ins_code" {
			idx = i
		}
	}
	if idx < 0 {
		return nil, fmt.Errorf("board query returned no ins_code column")
	}
	vals := make([]any, len(cols))
	ptrs := make([]any, len(cols))
	for i := range vals {
		ptrs[i] = &vals[i]
	}
	fr := &Frame{Cols: make(map[string][]any, len(cols))}
	seen := make(map[string]bool, 6000)
	for rows.Next() {
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		var code string
		switch v := vals[idx].(type) {
		case nil:
			// NULL: همانطور که پایتون این ردیف را نمی‌آورد (WHERE ins_code IS NOT
			// NULL)، اینجا هم ردیف کنار گذاشته می‌شود.
			continue
		case string:
			code = v
		case []byte:
			code = string(v)
		default:
			return nil, fmt.Errorf("board query: ins_code has Go type %T", v)
		}
		// رشتهٔ خالی مثلِ هر کدِ دیگری در بررسیِ تکرار می‌آید؛ پایتون هم با
		// drop_duplicates آن را نگه می‌دارد.
		if seen[code] { // drop_duplicates(ins_code, keep="first")
			continue
		}
		seen[code] = true
		fr.Codes = append(fr.Codes, code)
		for i, c := range cols {
			fr.Cols[c] = append(fr.Cols[c], vals[i])
		}
	}
	return fr, rows.Err()
}

// BoardSQLForTest فقط برایِ تست: متنِ نهاییِ کوئری را برمی‌گرداند.
func BoardSQLForTest(db *sql.DB) (string, error) { return boardSQL(db) }

func boardSQL(db *sql.DB) (string, error) {
	mcap := "CAST(NULL AS REAL)"
	src := "CAST(NULL AS REAL)"
	if hasColumn(db, "market_watch", "market_cap") {
		gate := "(1=0)"
		if hasColumn(db, "market_watch", "allowed_min") && hasColumn(db, "market_watch", "allowed_max") {
			gate = mcapDeadBand("m")
		}
		mcap = mcapBulkExpr(db, "i", "m")
		src = "CASE WHEN NOT " + gate + " THEN m.market_cap_src END"
	}
	text := BoardSQLBase
	if !tableExists(db, "board_hist_v") || !tableExists(db, "board_hist_fv") {
		fv := HistFvSQL
		if ok, rows := tapeSlotProbe(db); ok {
			fv = HistFvSlotSQL
		} else {
			warnSlotFallback(rows)
		}
		// متنِ پایه هر دو پنجره را در پرانتزِ خودش دارد
		// (`v AS MATERIALIZED (SELECT * FROM board_hist_v)`)؛ CTE بی‌پرانتزِ
		// اضافه درجا می‌نشیند، وگرنه `((WITH ...))` در SQLite خطای نحوی است.
		text = strings.Replace(text, "SELECT * FROM board_hist_v", HistVSQL, 1)
		text = strings.Replace(text, "SELECT * FROM board_hist_fv", fv, 1)
	}
	text = strings.Replace(text, "CAST(NULL AS REAL) AS mcap,", mcap+" AS mcap,", 1)
	text = strings.Replace(text, "CAST(NULL AS REAL) AS mcap_src", src+" AS mcap_src", 1)
	return text, nil
}

func tableExists(db *sql.DB, name string) bool {
	var n int
	err := db.QueryRow("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", name).Scan(&n)
	return err == nil && n > 0
}

func hasColumn(db *sql.DB, table, col string) bool {
	rows, err := db.Query("PRAGMA table_info(" + table + ")")
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			return false
		}
		if strings.EqualFold(name, col) {
			return true
		}
	}
	return false
}

var slotWarnOnce sync.Once

// tapeSlotProbe می‌پرسد آیا پنجرۀ اسلات‌محور نشسته است، با هزینۀ O(1): وجودِ
// یک ردیف کافی است و COUNT(*) لازم نیست. rows عینِ پایتون است
// (api/market.py:_has_tape_slots): 0 = جدولِ خالی، -1 = خطا (جدول نیست)؛
// مقدارِ مثبت هرگز گزارش نمی‌شود.
func tapeSlotProbe(db *sql.DB) (bool, int) {
	var one int
	err := db.QueryRow("SELECT 1 FROM tape_ih_slot LIMIT 1").Scan(&one)
	switch {
	case err == nil:
		return true, 1
	case errors.Is(err, sql.ErrNoRows):
		return false, 0
	default:
		return false, -1
	}
}

// warnSlotFallback همان گزارشِ یک‌باردرهرپروسۀ پایتون است (api/market.py:486-491):
// افتادن به پنجرۀ ردیف‌محور باید دیده شود، وگرنه «صفر اختلاف» رویِ پنجرۀ غایب
// بی‌صدا می‌ماند. sync.Once این را از مسیرِ داغ بیرون نگه می‌دارد.
func warnSlotFallback(rows int) {
	slotWarnOnce.Do(func() {
		log.Printf("[market] پنجرۀ اسلات‌محورِ [ih] در دسترس نیست (rows=%d)"+
			" — پنج فیلتر روی پنجرۀ ردیف‌محورِ کهنه حساب می‌شوند", rows)
	})
}

// mcapDeadBand عینِ fts_engine.mcap_dead_band_sql — بانِ مرده = بی‌اعتبار.
func mcapDeadBand(board string) string {
	return fmt.Sprintf(
		"(COALESCE(%[1]s.allowed_min, 0) > 0 AND COALESCE(%[1]s.allowed_max, 0) > 0"+
			" AND %[1]s.allowed_max <= %[1]s.allowed_min)", board)
}

// mcapBulkExpr عینِ fts_engine.mcap_bulk_expr: ستونِ رسمی، وگرنه آخرین
// daily_prices.market_capِ معتبر، پشتِ همان دروازهٔ بانِ مرده.
func mcapBulkExpr(db *sql.DB, alias, board string) string {
	if !hasColumn(db, "market_watch", "market_cap") {
		return "NULL"
	}
	expr := fmt.Sprintf("CASE WHEN %[1]s.market_cap > 0 THEN %[1]s.market_cap END", board)
	if hasColumn(db, "daily_prices", "market_cap") {
		expr = fmt.Sprintf("COALESCE(%s, (SELECT d.market_cap FROM daily_prices d"+
			" WHERE d.ins_code = %s.ins_code AND d.market_cap > 0"+
			" ORDER BY d.d_even DESC LIMIT 1))", expr, alias)
	}
	if hasColumn(db, "market_watch", "allowed_max") && hasColumn(db, "market_watch", "allowed_min") {
		expr = fmt.Sprintf("CASE WHEN NOT %s THEN %s END", mcapDeadBand(board), expr)
	}
	return expr
}
