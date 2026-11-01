package export

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/csv"
	"fmt"
	"net/url"
	"strings"
	"time"
)

const (
	ExportMaxRows = 20000
	ExportMaxCols = 200
)

// Disposition تولید هدر Content-Disposition امن مطابق با RFC 5987.
// نام‌های فارسی هدر لاتین-۱ را نمی‌شکنند.
func Disposition(name string) string {
	var safeBuilder strings.Builder
	for _, c := range name {
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-' {
			safeBuilder.WriteRune(c)
		} else {
			safeBuilder.WriteRune('_')
		}
	}
	safe := strings.Trim(safeBuilder.String(), "_")
	if safe == "" {
		safe = "export"
	}
	if len(safe) > 120 {
		safe = safe[:120]
	}

	encodedName := url.PathEscape(name)
	return fmt.Sprintf("attachment; filename=\"%s\"; filename*=UTF-8''%s", safe, encodedName)
}

// BuildCSV تبدیل ردیف‌ها و متادیتا به خروجی CSV با هدر UTF-8 BOM.
func BuildCSV(title string, rows [][]any, meta [][2]string) ([]byte, string, string) {
	ts := time.Now().Format("20060102_1504")
	filename := fmt.Sprintf("borsagent_%s_%s.csv", title, ts)

	var buf bytes.Buffer
	// اضافه کردن UTF-8 BOM (\xef\xbb\xbf)
	buf.WriteString("\ufeff")

	w := csv.NewWriter(&buf)

	for _, r := range rows {
		strRow := make([]string, len(r))
		for i, c := range r {
			if c == nil {
				strRow[i] = ""
			} else {
				strRow[i] = fmt.Sprint(c)
			}
		}
		_ = w.Write(strRow)
	}

	if len(meta) > 0 {
		// خط خالی قبل از ردپای منشأ
		_ = w.Write([]string{})
		for _, pair := range meta {
			_ = w.Write([]string{"# " + pair[0], pair[1]})
		}
	}

	w.Flush()
	dispositionHeader := Disposition(filename)
	return buf.Bytes(), dispositionHeader, filename
}

// QueryMarketExportRows واکشی ردیف‌های نمای بازار برای GET /api/export?view=market.
func QueryMarketExportRows(ctx context.Context, marketDB *sql.DB) ([][]any, error) {
	query := `
		SELECT i.l_val18 AS symbol, COALESCE(i.l_val30, '') AS name,
		       COALESCE(NULLIF(i.sector_name, ''), 'سایر') AS sector,
		       m.p_closing AS closing, m.p_last AS last,
		       m.price_change AS change, m.q_tot_tran AS volume,
		       m.q_tot_cap AS value, m.pe, m.eps, m.z_tot_tran AS trades
		FROM market_watch m LEFT JOIN instruments i ON i.ins_code = m.ins_code
		WHERE i.l_val18 IS NOT NULL
		ORDER BY i.l_val18
	`
	rows, err := marketDB.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	headers := []any{"symbol", "name", "sector", "closing", "last", "change", "volume", "value", "pe", "eps", "trades"}
	result := [][]any{headers}

	for rows.Next() {
		var sym, name, sector string
		var closing, last, change, volume, value, pe, eps, trades sql.NullFloat64

		if err := rows.Scan(&sym, &name, &sector, &closing, &last, &change, &volume, &value, &pe, &eps, &trades); err != nil {
			continue
		}

		result = append(result, []any{
			sym,
			name,
			sector,
			nullToAny(closing),
			nullToAny(last),
			nullToAny(change),
			nullToAny(volume),
			nullToAny(value),
			nullToAny(pe),
			nullToAny(eps),
			nullToAny(trades),
		})
	}

	return result, nil
}

func nullToAny(v sql.NullFloat64) any {
	if !v.Valid {
		return ""
	}
	return v.Float64
}
