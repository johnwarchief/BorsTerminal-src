// Package fundamental پورتِ مسیرهایِ خواندنیِ api/fundamental.py رویِ Go.
//
// درِ فازِ A نه شبکه می‌زند نه چیزی می‌نویسد؛ همان market.db فقط‌خواندنی که
// پایتون می‌خواند، با همان ترتیبِ کوئری‌ها و همان قاعدهٔ «برنده». هیچ آستانه و
// هیچ داوریِ دومی اینجا ساخته نمی‌شود (تصمیمِ §۱۵ و رأی‌هایِ جزوه).
package fundamental

import (
	"context"
	"database/sql"

	"borsterminal/backend/internal/symbolid"
)

type Service struct {
	market *sql.DB
	sid    *symbolid.Resolver
}

func New(market *sql.DB) *Service {
	return &Service{market: market, sid: symbolid.New(market)}
}

func (s *Service) Close() error { return s.sid.Close() }

// fsPublicFields عینِ _public_fields درِ get_fundamental_quarters — و همان
// هشدارِ خودش: gross_profit هیچ‌وقت با net_profit جایگزین نمی‌شود و NULL هیچ‌وقت
// صفر نمی‌شود؛ نبودش درِ پاسخ حفظ می‌گردد.
var fsPublicFields = []string{"period_end", "period_months", "revenue", "gross_profit",
	"operating_profit", "net_profit", "basic_eps", "publish_date"}

// quartersQuery دقیقاً همان ستون‌ها و همان ترتیبِ کوئریِ پایتون است؛ ستون‌ها درِ
// map می‌نشینند ولی ترتیبِ ردیف‌ها از SQLite می‌آید.
const quartersColumns = "period_end, period_months, revenue, gross_profit," +
	" operating_profit, net_profit, basic_eps, publish_date," +
	" title, tracing_no, report_kind"

// rows ردیف‌هایِ یکِ کوئری را به نقشه‌هایِ پایتون‌شکل (کلیدِ ستون ← مقدارِ خام)
// تبدیل می‌کند؛ ترتیبِ ردیف‌ها همان چیزی است که SQLite برگردانده.
func (s *Service) rows(ctx context.Context, query string, args []any) ([]map[string]any, error) {
	rs, err := s.market.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	cols, err := rs.Columns()
	if err != nil {
		return nil, err
	}
	out := []map[string]any{}
	for rs.Next() {
		raw := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range raw {
			ptrs[i] = &raw[i]
		}
		if err := rs.Scan(ptrs...); err != nil {
			return nil, err
		}
		row := make(map[string]any, len(cols))
		for i, c := range cols {
			row[c] = normalizeValue(raw[i])
		}
		out = append(out, row)
	}
	return out, rs.Err()
}

// normalizeValue: modernc اعدادِ ستونِ INTEGER را int64 و REAL را float64 می‌دهد؛
// TEXT به‌صورتِ []byte هم می‌تواند برسد (ستونِ بی‌نوع). پایتون درِ این دو ستون
// str/float/int می‌بیند، پس بایت به رشته تبدیل می‌شود.
func normalizeValue(v any) any {
	if b, ok := v.([]byte); ok {
		return string(b)
	}
	return v
}
