package codal

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"borsterminal/backend/internal/symbolid"
)

// UniverseAuditReport ساختار گزارش ممیزی جامع پوشش و سلامت داده‌های کل جهان بازار.
type UniverseAuditReport struct {
	InstrumentCount         int            `json:"instrument_count"`
	ActiveInstruments       int            `json:"active_instruments"`
	SectorCount             int            `json:"sector_count"`
	MarketWatchCount        int            `json:"market_watch_count"`
	ClientTypeCount         int            `json:"client_type_count"`
	ClientTypeValueCount    int            `json:"client_type_value_count"`
	PriceAdjustEventsCount  int            `json:"price_adjust_events_count"`
	ShareChangeEventsCount  int            `json:"share_change_events_count"`
	CorporateSymbolsCovered int            `json:"corporate_symbols_covered"`
	CodalNoticesTotal       int            `json:"codal_notices_total"`
	CodalStatementsTotal    int            `json:"codal_statements_total"`
	CodalMonthlyTotal       int            `json:"codal_monthly_total"`
	QuarantineCount         int            `json:"quarantine_count"`
	QuarantineErrors        map[string]int `json:"quarantine_errors"`
	DuplicateNoticesCount   int            `json:"duplicate_notices_count"`
	DuplicateTracingNos     []int64        `json:"duplicate_tracing_nos"`
	FTSResultsCount         int            `json:"fts_results_count"`
	FTSPassCount            int            `json:"fts_pass_count"`
	FTSFailCount            int            `json:"fts_fail_count"`
	FTSMarginalCount        int            `json:"fts_marginal_count"`
	DataAnomalies           []string       `json:"data_anomalies"`
}

// tableExistsInMain بررسی می‌کند آیا جدول در شمای main وجود دارد یا خیر.
func tableExistsInMain(ctx context.Context, db *sql.DB, tableName string) bool {
	var count int
	query := "SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?"
	err := db.QueryRowContext(ctx, query, tableName).Scan(&count)
	return err == nil && count > 0
}

// tableExistsInAttached بررسی می‌کند آیا جدول در شمای متصل‌شده (مانند codal) وجود دارد یا خیر.
func tableExistsInAttached(ctx context.Context, db *sql.DB, schemaName, tableName string) bool {
	var attachedCount int
	_ = db.QueryRowContext(ctx, "SELECT count(*) FROM pragma_database_list WHERE name = ?", schemaName).Scan(&attachedCount)
	if attachedCount == 0 {
		return false
	}
	query := fmt.Sprintf("SELECT count(*) FROM %s.sqlite_master WHERE type IN ('table', 'view') AND name = ?", schemaName)
	var count int
	err := db.QueryRowContext(ctx, query, tableName).Scan(&count)
	return err == nil && count > 0
}

// ensureCodalAttached در صورت وجود فایل codal.db در کنار دیتابیس مارکت، آن را به عنوان شمای codal متصل می‌کند.
func ensureCodalAttached(ctx context.Context, db *sql.DB) {
	var attachedCount int
	_ = db.QueryRowContext(ctx, "SELECT count(*) FROM pragma_database_list WHERE name = 'codal'").Scan(&attachedCount)
	if attachedCount > 0 {
		return
	}
	var mainFile string
	_ = db.QueryRowContext(ctx, "SELECT file FROM pragma_database_list WHERE name = 'main'").Scan(&mainFile)
	if mainFile == "" {
		return
	}
	codalPath := filepath.Join(filepath.Dir(mainFile), "codal.db")
	if fi, err := os.Stat(codalPath); err == nil && !fi.IsDir() {
		slashPath := filepath.ToSlash(codalPath)
		_, _ = db.ExecContext(ctx, fmt.Sprintf("ATTACH DATABASE '%s' AS codal", strings.ReplaceAll(slashPath, "'", "''")))
	}
}

// findTable جستجوی جدول در شمای اصلی یا شمای codal.
func findTable(ctx context.Context, db *sql.DB, tableName string) string {
	if tableExistsInMain(ctx, db, tableName) {
		return tableName
	}
	ensureCodalAttached(ctx, db)
	if tableExistsInAttached(ctx, db, "codal", tableName) {
		return "codal." + tableName
	}
	return ""
}

// AuditMarketUniverse ممیزی جامع پوشش داده‌ها، شناسایی مغایرت‌ها، موارد تکراری و آمار FTS را انجام می‌دهد.
func AuditMarketUniverse(ctx context.Context, marketDB *sql.DB) (*UniverseAuditReport, error) {
	if marketDB == nil {
		return nil, errors.New("nil database connection")
	}

	report := &UniverseAuditReport{
		QuarantineErrors:    make(map[string]int),
		DuplicateTracingNos: make([]int64, 0),
		DataAnomalies:       make([]string, 0),
	}

	// شناسایی جدول‌های موجود
	instTbl := findTable(ctx, marketDB, "instruments")
	mwTbl := findTable(ctx, marketDB, "market_watch")
	ctTbl := findTable(ctx, marketDB, "client_type")
	ctvTbl := findTable(ctx, marketDB, "client_type_value")
	paTbl := findTable(ctx, marketDB, "price_adjust_events")
	scTbl := findTable(ctx, marketDB, "share_change_events")
	cnTbl := findTable(ctx, marketDB, "codal_notices")
	fsTbl := findTable(ctx, marketDB, "financial_statements")
	msTbl := findTable(ctx, marketDB, "monthly_sales")
	qTbl := findTable(ctx, marketDB, "codal_quarantine")
	ftsTbl := findTable(ctx, marketDB, "fts_results")

	// ۱. نمادها و دیدبان بازار
	if instTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", instTbl)).Scan(&report.InstrumentCount)
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(DISTINCT sector_code) FROM %s WHERE sector_code IS NOT NULL AND TRIM(sector_code) != ''", instTbl)).Scan(&report.SectorCount)
		if report.SectorCount == 0 {
			_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(DISTINCT sector_name) FROM %s WHERE sector_name IS NOT NULL AND TRIM(sector_name) != ''", instTbl)).Scan(&report.SectorCount)
		}
		if mwTbl != "" {
			_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(DISTINCT ins_code) FROM %s WHERE ins_code IN (SELECT ins_code FROM %s)", mwTbl, instTbl)).Scan(&report.ActiveInstruments)
		}
		if report.ActiveInstruments == 0 && report.InstrumentCount > 0 {
			_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s WHERE ins_code IS NOT NULL AND TRIM(ins_code) != ''", instTbl)).Scan(&report.ActiveInstruments)
		}
	} else if mwTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(DISTINCT ins_code) FROM %s", mwTbl)).Scan(&report.ActiveInstruments)
		report.InstrumentCount = report.ActiveInstruments
	}

	if mwTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", mwTbl)).Scan(&report.MarketWatchCount)
	}

	// ۲. حقیقی / حقوقی
	if ctTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", ctTbl)).Scan(&report.ClientTypeCount)
	}
	if ctvTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", ctvTbl)).Scan(&report.ClientTypeValueCount)
	}

	// ۳. رویدادهای شرکتی
	if paTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", paTbl)).Scan(&report.PriceAdjustEventsCount)
	}
	if scTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", scTbl)).Scan(&report.ShareChangeEventsCount)
	}
	if paTbl != "" && scTbl != "" {
		q := fmt.Sprintf("SELECT count(DISTINCT symbol) FROM (SELECT symbol FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != '' UNION SELECT symbol FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != '')", paTbl, scTbl)
		_ = marketDB.QueryRowContext(ctx, q).Scan(&report.CorporateSymbolsCovered)
	} else if paTbl != "" {
		q := fmt.Sprintf("SELECT count(DISTINCT symbol) FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != ''", paTbl)
		_ = marketDB.QueryRowContext(ctx, q).Scan(&report.CorporateSymbolsCovered)
	} else if scTbl != "" {
		q := fmt.Sprintf("SELECT count(DISTINCT symbol) FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != ''", scTbl)
		_ = marketDB.QueryRowContext(ctx, q).Scan(&report.CorporateSymbolsCovered)
	}

	// ۴. کدال
	if cnTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", cnTbl)).Scan(&report.CodalNoticesTotal)
	}
	if fsTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", fsTbl)).Scan(&report.CodalStatementsTotal)
	}
	if msTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", msTbl)).Scan(&report.CodalMonthlyTotal)
	}
	if qTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", qTbl)).Scan(&report.QuarantineCount)
		rows, err := marketDB.QueryContext(ctx, fmt.Sprintf("SELECT COALESCE(NULLIF(TRIM(reason), ''), 'unknown'), count(*) FROM %s GROUP BY 1", qTbl))
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var r string
				var c int
				if err := rows.Scan(&r, &c); err == nil {
					report.QuarantineErrors[r] = c
				}
			}
		}
	}

	// ۵. شناسایی تکراری‌ها در اطلاعیه‌های کدال (tracing_no)
	if cnTbl != "" {
		q := fmt.Sprintf("SELECT tracing_no, count(*) AS c FROM %s WHERE tracing_no IS NOT NULL GROUP BY tracing_no HAVING c > 1 ORDER BY tracing_no", cnTbl)
		rows, err := marketDB.QueryContext(ctx, q)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var tn int64
				var cnt int
				if err := rows.Scan(&tn, &cnt); err == nil {
					report.DuplicateTracingNos = append(report.DuplicateTracingNos, tn)
					report.DuplicateNoticesCount += (cnt - 1)
				}
			}
		}
		if len(report.DuplicateTracingNos) > 0 {
			report.DataAnomalies = append(report.DataAnomalies,
				fmt.Sprintf("duplicate tracing_no in %s: %d duplicate notice records across %d tracing numbers (%v)",
					cnTbl, report.DuplicateNoticesCount, len(report.DuplicateTracingNos), report.DuplicateTracingNos))
		}
	}

	// ۶. شناسایی تداخل تکراری (symbol, period_end) در صورت‌های مالی
	if fsTbl != "" {
		q := fmt.Sprintf("SELECT symbol, period_end, count(*) AS c FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != '' AND period_end IS NOT NULL AND TRIM(period_end) != '' GROUP BY symbol, period_end HAVING c > 1 ORDER BY symbol, period_end", fsTbl)
		rows, err := marketDB.QueryContext(ctx, q)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var sym, pe string
				var cnt int
				if err := rows.Scan(&sym, &pe, &cnt); err == nil {
					report.DataAnomalies = append(report.DataAnomalies,
						fmt.Sprintf("duplicate (symbol, period_end) in %s: symbol %s on period %s has %d records",
							fsTbl, sym, pe, cnt))
				}
			}
		}
	}

	// ۷. شناسایی وقفه‌ها و گپ‌های توالی ماه در فروش ماهانه (monthly_sales)
	if msTbl != "" {
		q := fmt.Sprintf("SELECT symbol, year, month FROM %s WHERE symbol IS NOT NULL AND TRIM(symbol) != '' AND year > 1300 AND month >= 1 AND month <= 12 ORDER BY symbol, year ASC, month ASC", msTbl)
		rows, err := marketDB.QueryContext(ctx, q)
		if err == nil {
			defer rows.Close()
			type symMonth struct {
				year  int
				month int
			}
			symRecords := make(map[string][]symMonth)
			for rows.Next() {
				var sym string
				var y, m int
				if err := rows.Scan(&sym, &y, &m); err == nil {
					normSym := strings.TrimSpace(symbolid.Norm(sym))
					symRecords[normSym] = append(symRecords[normSym], symMonth{year: y, month: m})
				}
			}

			var sortedSymbols []string
			for s := range symRecords {
				sortedSymbols = append(sortedSymbols, s)
			}
			sort.Strings(sortedSymbols)

			for _, sym := range sortedSymbols {
				records := symRecords[sym]
				if len(records) < 2 {
					continue
				}
				for i := 1; i < len(records); i++ {
					prev := records[i-1]
					curr := records[i]
					prevIdx := prev.year*12 + (prev.month - 1)
					currIdx := curr.year*12 + (curr.month - 1)

					if currIdx == prevIdx {
						report.DataAnomalies = append(report.DataAnomalies,
							fmt.Sprintf("duplicate monthly_sales for %s in period %04d/%02d", sym, curr.year, curr.month))
					} else if currIdx-prevIdx > 1 {
						missing := (currIdx - prevIdx) - 1
						report.DataAnomalies = append(report.DataAnomalies,
							fmt.Sprintf("month sequence gap in monthly_sales for %s: missing %d month(s) between %04d/%02d and %04d/%02d",
								sym, missing, prev.year, prev.month, curr.year, curr.month))
					}
				}
			}
		}
	}

	// ۸. خطاهای قرنطینه
	if report.QuarantineCount > 0 {
		report.DataAnomalies = append(report.DataAnomalies,
			fmt.Sprintf("codal_quarantine contains %d quarantined records across %d failure types",
				report.QuarantineCount, len(report.QuarantineErrors)))
	}

	// ۹. شاخص‌های بنیادی FTS
	if ftsTbl != "" {
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", ftsTbl)).Scan(&report.FTSResultsCount)
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s WHERE score >= 5 OR verdict IN ('STRONG', 'PASS', 'تایید کامل')", ftsTbl)).Scan(&report.FTSPassCount)
		_ = marketDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s WHERE (score = 4 OR verdict IN ('WATCH', 'MARGINAL', 'تایید نسبی')) AND NOT (score >= 5 OR verdict IN ('STRONG', 'PASS', 'تایید کامل'))", ftsTbl)).Scan(&report.FTSMarginalCount)
		report.FTSFailCount = report.FTSResultsCount - report.FTSPassCount - report.FTSMarginalCount
		if report.FTSFailCount < 0 {
			report.FTSFailCount = 0
		}
	}

	return report, nil
}
