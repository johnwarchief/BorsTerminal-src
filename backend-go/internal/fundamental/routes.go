package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). What changes: دو بدنهٔ
// خواندنیِ مسیر (`sectors`، `{symbol}/quarters`) از api/fundamental.py.
// Invariants: R3 (همان ترتیبِ کوئری و همان انتخابِ مرجع، بی‌parserِ دوم)،
// R7 (فقط‌خواندنی؛ هیچ نوشتنِ اسکима یا index)، R9 (`sectors` صریح و پیش از هر
// `{symbol}` ثبت می‌شود تا بلعیده نشود). Lockstep: هیچ درِ spec/ESLint؛ گاردِ B4
// و آزمونِ ترتیبِ مسیرها درِ internal/httpapi. Guard: طلایی‌هایِ s1 که اوراکلِ
// پایتون رویِ همان فیکسچر ساخته. خطایِ بانک درِ هر دو بدنه بالا می‌رود، چون
// اوراکل هیچ `except` ندارد و فقط `finally: conn.close()` — بلعیدنش «بی‌داده»
// جعلی می‌سازد. Rollback: revertِ همین کامیت.

import (
	"context"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/symbolid"
)

// SectorsBody عینِ api_fundamental_sectors: یکِ SELECTِ ساده رویِ همان بانک، بی‌
// هیچ داوریِ تازه. نمادهایِ فقط-کدال (صندوق/حقِ تقدم) درِ instruments نیستند، پس
// درِ این فهرست هم نمی‌آیند — همان رفتارِ پایتون.
//
// خطایِ بانک پرتاب می‌شود، نه بلعیده: اوراکل `try: … finally: conn.close()` دارد
// و هیچ `except` ندارد (api/fundamental.py:1992-1999)، پس SQLite error درِ FastAPI
// به ۵۰۰ می‌رسد. `{"status":"success","count":0}` رویِ بانکِ خراب یا قفل‌شده
// دروغِ «این بازار صنعتی ندارد» است — بدترین شکلِ خرابی، چون صادق به‌نظر می‌رسد.
func (s *Service) SectorsBody(ctx context.Context) (map[string]any, error) {
	rows, err := s.rows(ctx, "SELECT DISTINCT sector_name FROM instruments"+
		" WHERE sector_name IS NOT NULL AND sector_name != '' ORDER BY sector_name", nil)
	if err != nil {
		return nil, err
	}
	secs := []any{}
	for _, r := range rows {
		secs = append(secs, r["sector_name"])
	}
	return map[string]any{"status": "success", "count": len(secs), "sectors": secs}, nil
}

// QuartersBody عینِ get_fundamental_quarters: همهٔ ردیف‌هایِ نامحدودِ همان نماد
// خوانده می‌شوند و لایۀ canonical برنده را می‌گزیند. LIMIT پیش از انتخابِ مرجع
// نمی‌نشیند، چون چند نسخهٔ یکِ دوره پنجره را پر می‌کردند و دوره‌هایِ یکتا حذف.
// خطایِ خواندن مثلِ اوراکل بالا می‌رود (`try/finally` بی‌`except`،
// api/fundamental.py:2251-2280): بانکِ قفل‌شده نباید به تریدر «این نماد گزارش
// فصلی ندارد» بگوید.
func (s *Service) QuartersBody(ctx context.Context, symbol string,
	limit int) (map[string]any, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		// بانکِ بی‌ردیفِ هویت (نامعارف): پایتون درِ sym_in همان‌جا می‌خواند؛ Go با
		// matchingِ ساده ادامه می‌دهد تا پاسخِ بی‌داده به ۵۰۰ نیفتد — همین برگشت
		// را لایۀ چارت هم زده است (internal/chart/chartdb.go:82-87: با خطایِ Pred
		// شرطِ خامِ `i.l_val18 = ?` می‌شود). خطایِ *واقعیِ* بانک درِ کوئریِ بعدی
		// خودش بالا می‌رود، پس این برگشت هیچ «بی‌داده» جعلی نمی‌سازد.
		pred, args = "symbol = ?", []any{symbol}
	}
	// `%s AND %s` درِ پایتون: شرطِ هویت و بعد شرطِ «دوره دارد» از لایۀ canonical.
	query := "SELECT " + quartersColumns + " FROM financial_statements WHERE " +
		pred + " AND " + period.DatedSQL("")
	raw, err := s.rows(ctx, query, args)
	if err != nil {
		return nil, err
	}
	selected := QuarterReferenceRows(raw, limit)
	quarters := make([]any, 0, len(selected))
	for _, row := range selected {
		q := make(map[string]any, len(fsPublicFields))
		for _, key := range fsPublicFields {
			q[key] = row[key]
		}
		quarters = append(quarters, q)
	}
	return map[string]any{"status": "success", "symbol": symbol,
		"count": len(quarters), "quarters": quarters}, nil
}
