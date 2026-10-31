package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). What changes: دو بدنهٔ
// خواندنیِ مسیر (`sectors`، `{symbol}/quarters`) از api/fundamental.py.
// Invariants: R3 (همان ترتیبِ کوئری و همان انتخابِ مرجع، بی‌parserِ دوم)،
// R7 (فقط‌خواندنی؛ هیچ نوشتنِ اسکима یا index)، R9 (`sectors` صریح و پیش از هر
// `{symbol}` ثبت می‌شود تا بلعیده نشود). Lockstep: هیچ درِ spec/ESLint؛ گاردِ B4
// و آزمونِ ترتیبِ مسیرها درِ internal/httpapi. Guard: طلایی‌هایِ s1 که اوراکلِ
// پایتون رویِ همان فیکسچر ساخته. Rollback: revertِ همین کامیت.

import (
	"context"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/symbolid"
)

// SectorsBody عینِ api_fundamental_sectors: یکِ SELECTِ ساده رویِ همان بانک، بی‌
// هیچ داوریِ تازه. نمادهایِ فقط-کدال (صندوق/حقِ تقدم) درِ instruments نیستند، پس
// درِ این فهرست هم نمی‌آیند — همان رفتارِ پایتون.
func (s *Service) SectorsBody(ctx context.Context) map[string]any {
	rows, err := s.rows(ctx, "SELECT DISTINCT sector_name FROM instruments"+
		" WHERE sector_name IS NOT NULL AND sector_name != '' ORDER BY sector_name", nil)
	secs := []any{}
	if err == nil {
		for _, r := range rows {
			secs = append(secs, r["sector_name"])
		}
	}
	return map[string]any{"status": "success", "count": len(secs), "sectors": secs}
}

// QuartersBody عینِ get_fundamental_quarters: همهٔ ردیف‌هایِ نامحدودِ همان نماد
// خوانده می‌شوند و لایۀ canonical برنده را می‌گزیند. LIMIT پیش از انتخابِ مرجع
// نمی‌نشیند، چون چند نسخهٔ یکِ دوره پنجره را پر می‌کردند و دوره‌هایِ یکتا حذف.
func (s *Service) QuartersBody(ctx context.Context, symbol string, limit int) map[string]any {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		// بانکِ بی‌ردیفِ هویت (نامعارف): پایتون درِ sym_in همان‌جا می‌خواند؛ Go با
		// matchingِ ساده ادامه می‌دهد تا پاسخِ بی‌داده به ۵۰۰ نیفتد.
		pred, args = "symbol = ?", []any{symbol}
	}
	// `%s AND %s` درِ پایتون: شرطِ هویت و بعد شرطِ «دوره دارد» از لایۀ canonical.
	query := "SELECT " + quartersColumns + " FROM financial_statements WHERE " +
		pred + " AND " + period.DatedSQL("")
	raw, err := s.rows(ctx, query, args)
	if err != nil {
		raw = nil
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
		"count": len(quarters), "quarters": quarters}
}
