package codal

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/symbolid"
)

// EnsureRecalcSchema تضمین وجود جدول‌های pipeline_dirty و fts_results در دیتابیس مارکت.
func EnsureRecalcSchema(db *sql.DB) error {
	if db == nil {
		return errors.New("nil database connection")
	}
	ddl := `
	CREATE TABLE IF NOT EXISTS pipeline_dirty (
		symbol TEXT,
		source TEXT,
		created_at_utc TEXT,
		PRIMARY KEY (symbol, source)
	);
	CREATE TABLE IF NOT EXISTS fts_results (
		symbol TEXT PRIMARY KEY,
		f01_growth_pct REAL,
		f01_pass INTEGER,
		f02_eps_series TEXT,
		f02_pass INTEGER,
		f03_margin_pct REAL,
		f03_pass INTEGER,
		f04_ratio REAL,
		f04_pass INTEGER,
		f05_verdict TEXT,
		f05_pass INTEGER,
		score INTEGER,
		verdict TEXT,
		excluded INTEGER,
		exclusion_reasons TEXT,
		i1a_pass INTEGER,
		i1b_pass INTEGER,
		i4a_pass INTEGER,
		i4b_pass INTEGER,
		rev_growth REAL,
		gross_margin REAL,
		sales_to_mcap REAL,
		profit_potential_pct REAL,
		annual_sales_bt REAL,
		annualize_months INTEGER,
		cfg_hash TEXT,
		computed_at TEXT
	);
	`
	_, err := db.Exec(ddl)
	return err
}

// MarkDirty نماد را به عنوان نیازمند بازمحاسبه در جدول pipeline_dirty ثبت می‌کند.
func MarkDirty(ctx context.Context, db *sql.DB, symbol string, source string) error {
	if db == nil {
		return errors.New("nil database connection")
	}
	sym := strings.TrimSpace(symbolid.Norm(symbol))
	if sym == "" {
		return errors.New("symbol cannot be empty")
	}
	if err := EnsureRecalcSchema(db); err != nil {
		return fmt.Errorf("ensure recalc schema: %w", err)
	}
	src := strings.TrimSpace(source)
	if src == "" {
		src = "unknown"
	}
	now := time.Now().UTC().Format(time.RFC3339)

	query := `INSERT OR REPLACE INTO pipeline_dirty (symbol, source, created_at_utc) VALUES (?, ?, ?)`
	_, err := db.ExecContext(ctx, query, sym, src, now)
	if err != nil {
		return fmt.Errorf("mark dirty: %w", err)
	}
	return nil
}

// GetDirtySymbols لیست نمادهای یکتای نیازمند بازمحاسبه را از جدول pipeline_dirty واکشی می‌کند.
func GetDirtySymbols(ctx context.Context, db *sql.DB) ([]string, error) {
	if db == nil {
		return nil, errors.New("nil database connection")
	}
	if err := EnsureRecalcSchema(db); err != nil {
		return nil, fmt.Errorf("ensure recalc schema: %w", err)
	}
	rows, err := db.QueryContext(ctx, `SELECT DISTINCT symbol FROM pipeline_dirty WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol`)
	if err != nil {
		return nil, fmt.Errorf("get dirty symbols: %w", err)
	}
	defer rows.Close()

	var symbols []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, fmt.Errorf("scan dirty symbol: %w", err)
		}
		if s = strings.TrimSpace(s); s != "" {
			symbols = append(symbols, s)
		}
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows dirty symbols: %w", err)
	}
	if symbols == nil {
		symbols = []string{}
	}
	return symbols, nil
}

// ClearDirtySymbols نمادهای پردازش‌شده را از جدول pipeline_dirty پاک می‌کند.
func ClearDirtySymbols(ctx context.Context, db *sql.DB, symbols []string) error {
	if db == nil {
		return errors.New("nil database connection")
	}
	if len(symbols) == 0 {
		return nil
	}
	if err := EnsureRecalcSchema(db); err != nil {
		return fmt.Errorf("ensure recalc schema: %w", err)
	}

	normSymbols := make([]any, 0, len(symbols))
	seen := make(map[string]bool)
	for _, s := range symbols {
		norm := strings.TrimSpace(symbolid.Norm(s))
		if norm != "" && !seen[norm] {
			seen[norm] = true
			normSymbols = append(normSymbols, norm)
		}
	}
	if len(normSymbols) == 0 {
		return nil
	}

	const chunkSize = 500
	for i := 0; i < len(normSymbols); i += chunkSize {
		end := i + chunkSize
		if end > len(normSymbols) {
			end = len(normSymbols)
		}
		chunk := normSymbols[i:end]
		placeholders := strings.Repeat("?,", len(chunk))
		placeholders = placeholders[:len(placeholders)-1]

		query := fmt.Sprintf(`DELETE FROM pipeline_dirty WHERE symbol IN (%s)`, placeholders)
		if _, err := db.ExecContext(ctx, query, chunk...); err != nil {
			return fmt.Errorf("clear dirty symbols: %w", err)
		}
	}
	return nil
}

const upsertFTSSQL = `
INSERT OR REPLACE INTO fts_results (
	symbol, f01_growth_pct, f01_pass, f02_eps_series, f02_pass,
	f03_margin_pct, f03_pass, f04_ratio, f04_pass, f05_verdict, f05_pass,
	score, verdict, excluded, exclusion_reasons,
	i1a_pass, i1b_pass, i4a_pass, i4b_pass,
	rev_growth, gross_margin, sales_to_mcap, profit_potential_pct,
	annual_sales_bt, annualize_months, cfg_hash, computed_at
) VALUES (
	?, ?, ?, ?, ?,
	?, ?, ?, ?, ?, ?,
	?, ?, ?, ?,
	?, ?, ?, ?,
	?, ?, ?, ?,
	?, ?, ?, ?
)`

type ftsRow struct {
	symbol             string
	f01GrowthPct       any
	f01Pass            any
	f02EpsSeries       any
	f02Pass            any
	f03MarginPct       any
	f03Pass            any
	f04Ratio           any
	f04Pass            any
	f05Verdict         any
	f05Pass            any
	score              int
	verdict            string
	excluded           int
	exclusionReasons   string
	i1aPass            any
	i1bPass            any
	i4aPass            any
	i4bPass            any
	revGrowth          any
	grossMargin        any
	salesToMcap        any
	profitPotentialPct any
	annualSalesBt      any
	annualizeMonths    any
	cfgHash            string
	computedAt         string
}

// RecalculateDirtyFTS خط لوله بازمحاسبه افزایشی شاخص‌های بنیادی FTS را برای نمادهای داده‌شده
// (یا همه نمادهای موجود در pipeline_dirty) اجرا کرده و نتایج را در fts_results ذخیره می‌کند.
func RecalculateDirtyFTS(ctx context.Context, marketDB *sql.DB, symbols []string) (int, error) {
	if marketDB == nil {
		return 0, errors.New("nil database connection")
	}
	if err := EnsureRecalcSchema(marketDB); err != nil {
		return 0, fmt.Errorf("ensure recalc schema: %w", err)
	}

	if len(symbols) == 0 {
		var err error
		symbols, err = GetDirtySymbols(ctx, marketDB)
		if err != nil {
			return 0, fmt.Errorf("get dirty symbols: %w", err)
		}
		if len(symbols) == 0 {
			return 0, nil
		}
	}

	fundSvc := fundamental.New(marketDB)
	defer fundSvc.Close()

	totalMcap, _ := fundSvc.BoardTotalMarketCap(ctx)
	m141Map, _ := fundSvc.M141Map(ctx)
	liqMap, _ := fundSvc.AvgTradeValueHmt(ctx, 30)

	computedAt := time.Now().Format("2006-01-02 15:04:05")
	const cfgHash = "{}"

	var batch []ftsRow
	var processedSymbols []string

	for _, rawSym := range symbols {
		sym := strings.TrimSpace(symbolid.Norm(rawSym))
		if sym == "" {
			continue
		}

		mcapInfo := fundSvc.MarketCapInfo(ctx, sym)
		var mcapVal any = mcapInfo["mcap"]
		if mcapVal == nil {
			mcapVal = mcapInfo["rials"]
		}
		mcap := toF(mcapVal)

		sector := strOr(mcapInfo["sector"])
		if sector == "" {
			_ = marketDB.QueryRowContext(ctx,
				"SELECT sector_name FROM instruments WHERE (l_val18 = ? OR l_val30 = ?) AND sector_name IS NOT NULL AND sector_name != '' ORDER BY updated_at DESC LIMIT 1",
				sym, sym).Scan(&sector)
		}

		companyName, _ := fundSvc.CompanyNameOf(ctx, sym)

		res, err := fundSvc.EvaluateV10(ctx, sym, mcap, totalMcap, sector, nil, companyName, m141Map, liqMap)
		if err != nil {
			// در صورت بروز خطا در یک نماد، ثبت و ادامه پردازش سایر نمادها
			continue
		}

		ind, _ := res["indicators"].(map[string]any)
		var g1 map[string]any
		if ind != nil {
			if ind1, ok := ind["1"].(map[string]any); ok {
				if mon, ok := ind1["monetary"].(map[string]any); ok {
					g1 = mon
				}
			}
		}
		var i2, i3, i4 map[string]any
		if ind != nil {
			i2, _ = ind["2"].(map[string]any)
			i3, _ = ind["3"].(map[string]any)
			i4, _ = ind["4"].(map[string]any)
		}
		var an4 map[string]any
		if i4 != nil {
			if an, ok := i4["annual"].(map[string]any); ok {
				an4 = an
			}
		}
		passes, _ := res["passes"].(map[string]any)
		if passes == nil {
			passes = map[string]any{}
		}

		var f01GrowthPct any
		if g1 != nil {
			f01GrowthPct = toOptFloat(g1["monetary_pct"])
		}

		f01Pass := toPass(passes["1_growth"])
		if g1 != nil && (isTruthy(g1["data_gap"]) || g1["monetary_pct"] == nil) {
			f01Pass = nil
		}

		var f02EpsSeries any
		if i2 != nil {
			f02EpsSeries = formatEpsSeries(i2["eps_series"])
		}

		var f02Pass any
		if isNA(i2) {
			f02Pass = nil
		} else {
			f02Pass = toPass(passes["2_eps_trend"])
		}

		var f03MarginPct any
		if i3 != nil {
			f03MarginPct = toOptFloat(i3["margin_pct"])
		}

		var f03Pass any
		if isNA(i3) {
			f03Pass = nil
		} else {
			f03Pass = toPass(passes["3_gross_margin"])
		}

		var f04Ratio any
		if i4 != nil {
			f04Ratio = toOptFloat(i4["sales_to_mcap"])
		}

		var f04Pass any
		if isNA(i4) {
			f04Pass = nil
		} else {
			f04Pass = toPass(passes["4_sales_to_mcap"])
		}

		f05Verdict := strOr(res["pricing_mode"])
		f05Pass := toPass(passes["5_industry"])
		score := toInt(res["score"])
		verdict := strOr(res["verdict"])
		excludedInt := boolToInt(res["excluded"])
		exclusionReasons := formatExclusionReasons(res["exclusion_reasons"])

		i1aPass := toPass(passes["1a_monetary_growth"])
		i1bPass := toPass(passes["1b_volume_growth"])
		i4aPass := toPass(passes["4a_sales_to_mcap"])
		i4bPass := toPass(passes["4b_profit_potential"])

		revGrowth := f01GrowthPct
		grossMargin := f03MarginPct
		salesToMcap := f04Ratio

		var profitPotentialPct any
		if i4 != nil {
			profitPotentialPct = toOptFloat(i4["potential_pct"])
		}

		var annualSalesBt any
		if i4 != nil && i4["annual_sales_bt"] != nil {
			annualSalesBt = toOptFloat(i4["annual_sales_bt"])
		} else if an4 != nil && an4["annual_sales_bt"] != nil {
			annualSalesBt = toOptFloat(an4["annual_sales_bt"])
		}

		var annualizeMonths any
		if an4 != nil && an4["months_used"] != nil {
			annualizeMonths = toOptInt(an4["months_used"])
		} else if i4 != nil && i4["months_used"] != nil {
			annualizeMonths = toOptInt(i4["months_used"])
		}

		batch = append(batch, ftsRow{
			symbol:             sym,
			f01GrowthPct:       f01GrowthPct,
			f01Pass:            f01Pass,
			f02EpsSeries:       f02EpsSeries,
			f02Pass:            f02Pass,
			f03MarginPct:       f03MarginPct,
			f03Pass:            f03Pass,
			f04Ratio:           f04Ratio,
			f04Pass:            f04Pass,
			f05Verdict:         f05Verdict,
			f05Pass:            f05Pass,
			score:              score,
			verdict:            verdict,
			excluded:           excludedInt,
			exclusionReasons:   exclusionReasons,
			i1aPass:            i1aPass,
			i1bPass:            i1bPass,
			i4aPass:            i4aPass,
			i4bPass:            i4bPass,
			revGrowth:          revGrowth,
			grossMargin:        grossMargin,
			salesToMcap:        salesToMcap,
			profitPotentialPct: profitPotentialPct,
			annualSalesBt:      annualSalesBt,
			annualizeMonths:    annualizeMonths,
			cfgHash:            cfgHash,
			computedAt:         computedAt,
		})
		processedSymbols = append(processedSymbols, sym)
	}

	if len(batch) > 0 {
		tx, err := marketDB.BeginTx(ctx, nil)
		if err != nil {
			return 0, fmt.Errorf("begin tx: %w", err)
		}
		defer tx.Rollback()

		stmt, err := tx.PrepareContext(ctx, upsertFTSSQL)
		if err != nil {
			return 0, fmt.Errorf("prepare upsert fts_results: %w", err)
		}
		defer stmt.Close()

		for _, r := range batch {
			_, err = stmt.ExecContext(ctx,
				r.symbol,
				r.f01GrowthPct,
				r.f01Pass,
				r.f02EpsSeries,
				r.f02Pass,
				r.f03MarginPct,
				r.f03Pass,
				r.f04Ratio,
				r.f04Pass,
				r.f05Verdict,
				r.f05Pass,
				r.score,
				r.verdict,
				r.excluded,
				r.exclusionReasons,
				r.i1aPass,
				r.i1bPass,
				r.i4aPass,
				r.i4bPass,
				r.revGrowth,
				r.grossMargin,
				r.salesToMcap,
				r.profitPotentialPct,
				r.annualSalesBt,
				r.annualizeMonths,
				r.cfgHash,
				r.computedAt,
			)
			if err != nil {
				return 0, fmt.Errorf("exec upsert fts_results for %s: %w", r.symbol, err)
			}
		}
		stmt.Close()

		if err := tx.Commit(); err != nil {
			return 0, fmt.Errorf("commit fts_results: %w", err)
		}

		if err := ClearDirtySymbols(ctx, marketDB, processedSymbols); err != nil {
			return len(processedSymbols), fmt.Errorf("clear dirty symbols: %w", err)
		}
	}

	return len(processedSymbols), nil
}

func toF(v any) float64 {
	switch x := v.(type) {
	case nil:
		return 0
	case float64:
		if math.IsNaN(x) {
			return 0
		}
		return x
	case float32:
		f := float64(x)
		if math.IsNaN(f) {
			return 0
		}
		return f
	case int:
		return float64(x)
	case int64:
		return float64(x)
	case json.Number:
		if f, err := x.Float64(); err == nil {
			return f
		}
		return 0
	case string:
		if f, err := strconv.ParseFloat(strings.TrimSpace(x), 64); err == nil {
			return f
		}
		return 0
	default:
		return 0
	}
}

func toOptFloat(v any) any {
	if v == nil {
		return nil
	}
	switch x := v.(type) {
	case float64:
		if math.IsNaN(x) {
			return nil
		}
		return x
	case float32:
		f := float64(x)
		if math.IsNaN(f) {
			return nil
		}
		return f
	case int:
		return float64(x)
	case int64:
		return float64(x)
	case json.Number:
		if f, err := x.Float64(); err == nil {
			return f
		}
		return nil
	case string:
		if f, err := strconv.ParseFloat(strings.TrimSpace(x), 64); err == nil {
			return f
		}
		return nil
	}
	return nil
}

func toOptInt(v any) any {
	if v == nil {
		return nil
	}
	switch n := v.(type) {
	case int:
		return int64(n)
	case int64:
		return n
	case float64:
		if math.IsNaN(n) {
			return nil
		}
		return int64(n)
	case json.Number:
		if i, err := n.Int64(); err == nil {
			return i
		}
		return nil
	case string:
		if i, err := strconv.ParseInt(strings.TrimSpace(n), 10, 64); err == nil {
			return i
		}
		return nil
	}
	return nil
}

func toInt(v any) int {
	if v == nil {
		return 0
	}
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	case float32:
		return int(n)
	case json.Number:
		if i, err := n.Int64(); err == nil {
			return int(i)
		}
		return 0
	case string:
		if i, err := strconv.Atoi(strings.TrimSpace(n)); err == nil {
			return i
		}
		return 0
	}
	return 0
}

func boolToInt(v any) int {
	if v == nil {
		return 0
	}
	switch b := v.(type) {
	case bool:
		if b {
			return 1
		}
		return 0
	case int:
		if b > 0 {
			return 1
		}
		return 0
	case int64:
		if b > 0 {
			return 1
		}
		return 0
	default:
		return 0
	}
}

func toPass(v any) any {
	if v == nil {
		return nil
	}
	switch b := v.(type) {
	case bool:
		if b {
			return 1
		}
		return 0
	case int:
		if b == 1 {
			return 1
		} else if b == 0 {
			return 0
		}
		return nil
	case int64:
		if b == 1 {
			return 1
		} else if b == 0 {
			return 0
		}
		return nil
	default:
		return nil
	}
}

func isNA(m map[string]any) bool {
	if m == nil {
		return false
	}
	if v, ok := m["na"].(bool); ok && v {
		return true
	}
	if v, ok := m["exempt"].(bool); ok && v {
		return true
	}
	return false
}

func isTruthy(v any) bool {
	if v == nil {
		return false
	}
	switch b := v.(type) {
	case bool:
		return b
	case int:
		return b != 0
	case int64:
		return b != 0
	case float64:
		return b != 0 && !math.IsNaN(b)
	case string:
		s := strings.ToLower(strings.TrimSpace(b))
		return s != "" && s != "0" && s != "false" && s != "null"
	}
	return false
}

func strOr(v any, def ...string) string {
	fallback := ""
	if len(def) > 0 {
		fallback = def[0]
	}
	if v == nil {
		return fallback
	}
	switch s := v.(type) {
	case string:
		t := strings.TrimSpace(s)
		if t == "" {
			return fallback
		}
		return t
	default:
		str := strings.TrimSpace(fmt.Sprint(v))
		if str == "" || str == "<nil>" {
			return fallback
		}
		return str
	}
}

func formatEpsSeries(ser any) any {
	if ser == nil {
		return nil
	}
	switch s := ser.(type) {
	case string:
		trimmed := strings.TrimSpace(s)
		if trimmed == "" || trimmed == "null" || trimmed == "[]" {
			return nil
		}
		return trimmed
	default:
		b, err := json.Marshal(ser)
		if err != nil {
			return nil
		}
		str := string(b)
		if str == "null" || str == "[]" || str == "{}" || str == `""` {
			return nil
		}
		return str
	}
}

func formatExclusionReasons(v any) string {
	if v == nil {
		return ""
	}
	switch r := v.(type) {
	case []string:
		return strings.Join(r, " · ")
	case []any:
		var strs []string
		for _, item := range r {
			if s := strings.TrimSpace(fmt.Sprint(item)); s != "" && s != "<nil>" {
				strs = append(strs, s)
			}
		}
		return strings.Join(strs, " · ")
	case string:
		return strings.TrimSpace(r)
	default:
		return ""
	}
}
