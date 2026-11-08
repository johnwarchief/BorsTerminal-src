package codal

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"borsterminal/backend/internal/period"
)

// ErrQuarantined خطای استاندارد جهت تفکیک گزارش‌های منتقل‌شده به جدول قرنطینه.
var ErrQuarantined = errors.New("report quarantined")

// QuarantineError خطای نوع‌دار با جزئیات دلیل قرنطینه شدن گزارش.
type QuarantineError struct {
	TracingNo  int64  `json:"tracing_no"`
	Symbol     string `json:"symbol"`
	ReportType string `json:"report_type"`
	Reason     string `json:"reason"`
}

func (e *QuarantineError) Error() string {
	return fmt.Sprintf("report quarantined: tracing_no=%d symbol=%q type=%s reason=%s", e.TracingNo, e.Symbol, e.ReportType, e.Reason)
}

func (e *QuarantineError) Is(target error) bool {
	return target == ErrQuarantined
}

// IsQuarantined آیا این خطا ناشی از قرنطینه شدن گزارش است؟
func IsQuarantined(err error) bool {
	var qErr *QuarantineError
	return errors.As(err, &qErr)
}

// QuarantineReason بازگرداندن دلیل قرنطینه از خطا در صورت وجود.
func QuarantineReason(err error) string {
	var qErr *QuarantineError
	if errors.As(err, &qErr) {
		return qErr.Reason
	}
	return ""
}

// EnsureValidationSchema تضمین وجود جداول financial_statements, monthly_sales و codal_quarantine در دیتابیس.
func EnsureValidationSchema(db *sql.DB) error {
	ddl := `
	CREATE TABLE IF NOT EXISTS codal_quarantine (
		tracing_no INTEGER PRIMARY KEY,
		symbol TEXT,
		report_type TEXT,
		reason TEXT,
		raw_payload TEXT,
		created_at_utc TEXT
	);
	CREATE INDEX IF NOT EXISTS ix_quarantine_symbol ON codal_quarantine(symbol);

	CREATE TABLE IF NOT EXISTS financial_statements (
		tracing_no INTEGER PRIMARY KEY,
		symbol TEXT,
		company_name TEXT,
		title TEXT,
		report_kind TEXT,
		period_months INTEGER,
		period_end TEXT,
		publish_date TEXT,
		revenue REAL,
		gross_profit REAL,
		operating_profit REAL,
		net_profit REAL,
		total_assets REAL,
		total_liabilities REAL,
		total_equity REAL,
		capital REAL,
		retained_earnings REAL,
		basic_eps REAL,
		unit TEXT,
		url TEXT,
		fetched_at TEXT,
		has_operating_sales INTEGER,
		is_audited INTEGER,
		is_consolidated INTEGER,
		fiscal_year TEXT,
		unit_norm TEXT
	);
	CREATE INDEX IF NOT EXISTS ix_fs_symbol ON financial_statements(symbol);

	CREATE TABLE IF NOT EXISTS monthly_sales (
		tracing_no INTEGER PRIMARY KEY,
		symbol TEXT,
		title TEXT,
		period_end TEXT,
		year INTEGER,
		month INTEGER,
		monthly_revenue REAL,
		ytd_revenue REAL,
		monthly_revenue_prev REAL,
		ytd_revenue_prev REAL,
		pdf_url TEXT,
		excel_url TEXT,
		monthly_volume REAL,
		ytd_volume REAL,
		volume_unit TEXT
	);
	CREATE INDEX IF NOT EXISTS ix_ms_symbol ON monthly_sales(symbol);
	`
	_, err := db.Exec(ddl)
	return err
}

// QuarantineReport درج یا بروزرسانی رکورد در جدول codal_quarantine.
func QuarantineReport(ctx context.Context, db *sql.DB, tracingNo int64, symbol, reportType, reason, rawPayload string) error {
	if err := EnsureValidationSchema(db); err != nil {
		return fmt.Errorf("ensure schema: %w", err)
	}

	createdAt := time.Now().UTC().Format(time.RFC3339)
	query := `
	INSERT INTO codal_quarantine (tracing_no, symbol, report_type, reason, raw_payload, created_at_utc)
	VALUES (?, ?, ?, ?, ?, ?)
	ON CONFLICT(tracing_no) DO UPDATE SET
		symbol = excluded.symbol,
		report_type = excluded.report_type,
		reason = excluded.reason,
		raw_payload = excluded.raw_payload,
		created_at_utc = excluded.created_at_utc
	`
	_, err := db.ExecContext(ctx, query, tracingNo, symbol, reportType, reason, rawPayload, createdAt)
	if err != nil {
		return fmt.Errorf("quarantine report exec: %w", err)
	}
	return nil
}

func quarantineStatement(ctx context.Context, db *sql.DB, tracingNo int64, symbol, reason string, data *FinancialStatementData, notice NoticeSummary) error {
	var payload any = data
	if data == nil {
		payload = notice
	}
	rawBytes, _ := json.Marshal(payload)
	_ = QuarantineReport(ctx, db, tracingNo, symbol, "statement", reason, string(rawBytes))
	_, _ = db.ExecContext(ctx, "DELETE FROM financial_statements WHERE tracing_no = ?", tracingNo)
	return &QuarantineError{
		TracingNo:  tracingNo,
		Symbol:     symbol,
		ReportType: "statement",
		Reason:     reason,
	}
}

func quarantineMonthly(ctx context.Context, db *sql.DB, tracingNo int64, symbol, reason string, data *MonthlyReportData, notice NoticeSummary) error {
	var payload any = data
	if data == nil {
		payload = notice
	}
	rawBytes, _ := json.Marshal(payload)
	_ = QuarantineReport(ctx, db, tracingNo, symbol, "monthly", reason, string(rawBytes))
	_, _ = db.ExecContext(ctx, "DELETE FROM monthly_sales WHERE tracing_no = ?", tracingNo)
	return &QuarantineError{
		TracingNo:  tracingNo,
		Symbol:     symbol,
		ReportType: "monthly",
		Reason:     reason,
	}
}

// ValidateAndIngestStatement اعتبارسنجی صورت‌های مالی، ارزیابی دوره زمانی با period.Canonicalize،
// بررسی خطاهای ساختاری (دارایی منفی، نماد خالی) و درج در financial_statements یا codal_quarantine.
func ValidateAndIngestStatement(ctx context.Context, db *sql.DB, data *FinancialStatementData, notice NoticeSummary) error {
	if err := EnsureValidationSchema(db); err != nil {
		return fmt.Errorf("ensure schema: %w", err)
	}

	tracingNo := int64(0)
	if data != nil && data.TracingNo != 0 {
		tracingNo = data.TracingNo
	} else {
		tracingNo = notice.TracingNo
	}

	if data == nil {
		return quarantineStatement(ctx, db, tracingNo, notice.Symbol, "nil_data", nil, notice)
	}

	symbol := strings.TrimSpace(data.Symbol)
	if symbol == "" {
		symbol = strings.TrimSpace(notice.Symbol)
	}
	if symbol == "" {
		return quarantineStatement(ctx, db, tracingNo, "", "empty_symbol", data, notice)
	}

	rawPeriod := strings.TrimSpace(data.PeriodEnd)
	if rawPeriod == "" {
		if t := period.FromTitle(notice.Title); t != nil {
			rawPeriod = *t
		}
	}

	canon := period.Canonicalize(rawPeriod)
	if canon == nil {
		return quarantineStatement(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	parts := strings.Split(*canon, "/")
	if len(parts) != 3 {
		return quarantineStatement(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	year, errY := strconv.Atoi(parts[0])
	month, errM := strconv.Atoi(parts[1])
	day, errD := strconv.Atoi(parts[2])
	if errY != nil || errM != nil || errD != nil || year < 1370 || year > 1430 || month < 1 || month > 12 || day < 1 || day > 31 {
		return quarantineStatement(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	// بررسی خطای ساختاری و ارقام مخدوش (دارایی منفی)
	if data.Assets < 0 {
		return quarantineStatement(ctx, db, tracingNo, symbol, "negative_assets", data, notice)
	}

	reportKind := notice.LetterCode
	if reportKind == "" {
		if data.IsConsolidated {
			reportKind = "تلفیقی"
		} else {
			reportKind = "اصلی"
		}
	}

	unitNorm := data.UnitNorm
	if unitNorm <= 0 {
		unitNorm = NormalizeUnit(notice.Title)
	}
	if unitNorm <= 0 {
		unitNorm = 1000000.0
	}

	hasOperatingSales := 0
	if data.Revenue != 0 {
		hasOperatingSales = 1
	}

	isAudited := 0
	if data.IsAudited {
		isAudited = 1
	}

	isConsolidated := 0
	if data.IsConsolidated {
		isConsolidated = 1
	}

	fiscalYear := fmt.Sprintf("%04d", year)
	fetchedAt := time.Now().UTC().Format(time.RFC3339)
	unitStr := "میلیون ریال"
	if unitNorm == 1000.0 {
		unitStr = "هزار ریال"
	} else if unitNorm == 1000000000.0 {
		unitStr = "میلیارد ریال"
	} else if unitNorm == 1.0 {
		unitStr = "ریال"
	}

	var unitNormToken *string
	if tok := ClassifyUnitToken(unitStr); tok != nil {
		unitNormToken = tok
	} else if tok := ClassifyUnitToken(notice.Title); tok != nil {
		unitNormToken = tok
	} else if unitNorm == 1000000.0 {
		mrl := "mrl"
		unitNormToken = &mrl
	}

	query := `
	INSERT INTO financial_statements (
		tracing_no, symbol, company_name, title, report_kind,
		period_months, period_end, publish_date, revenue, gross_profit,
		operating_profit, net_profit, total_assets, total_liabilities, total_equity,
		capital, retained_earnings, basic_eps, unit, url,
		fetched_at, has_operating_sales, is_audited, is_consolidated, fiscal_year,
		unit_norm
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	ON CONFLICT(tracing_no) DO UPDATE SET
		symbol = excluded.symbol,
		company_name = excluded.company_name,
		title = excluded.title,
		report_kind = excluded.report_kind,
		period_months = excluded.period_months,
		period_end = excluded.period_end,
		publish_date = excluded.publish_date,
		revenue = excluded.revenue,
		gross_profit = excluded.gross_profit,
		operating_profit = excluded.operating_profit,
		net_profit = excluded.net_profit,
		total_assets = excluded.total_assets,
		total_liabilities = excluded.total_liabilities,
		total_equity = excluded.total_equity,
		capital = excluded.capital,
		retained_earnings = excluded.retained_earnings,
		basic_eps = excluded.basic_eps,
		unit = excluded.unit,
		url = excluded.url,
		fetched_at = excluded.fetched_at,
		has_operating_sales = excluded.has_operating_sales,
		is_audited = excluded.is_audited,
		is_consolidated = excluded.is_consolidated,
		fiscal_year = excluded.fiscal_year,
		unit_norm = excluded.unit_norm
	`
	_, err := db.ExecContext(ctx, query,
		tracingNo, symbol, notice.CompanyName, notice.Title, reportKind,
		data.Months, *canon, notice.PublishDate, data.Revenue, data.GrossProfit,
		data.OperatingProfit, data.NetProfit, data.Assets, data.Liabilities, data.Equity,
		data.Capital, data.RetainedEarnings, data.EPS, unitStr, notice.URL,
		fetchedAt, hasOperatingSales, isAudited, isConsolidated, fiscalYear,
		unitNormToken,
	)
	if err != nil {
		return fmt.Errorf("insert financial_statement: %w", err)
	}

	// حذف احتمالی از قرنطینه در صورت تصحیح داده
	_, _ = db.ExecContext(ctx, "DELETE FROM codal_quarantine WHERE tracing_no = ?", tracingNo)

	return nil
}

// ValidateAndIngestMonthly اعتبارسنجی گزارش فعالیت ماهانه و درج در جدول monthly_sales یا codal_quarantine.
func ValidateAndIngestMonthly(ctx context.Context, db *sql.DB, data *MonthlyReportData, notice NoticeSummary) error {
	if err := EnsureValidationSchema(db); err != nil {
		return fmt.Errorf("ensure schema: %w", err)
	}

	tracingNo := int64(0)
	if data != nil && data.TracingNo != 0 {
		tracingNo = data.TracingNo
	} else {
		tracingNo = notice.TracingNo
	}

	if data == nil {
		return quarantineMonthly(ctx, db, tracingNo, notice.Symbol, "nil_data", nil, notice)
	}

	symbol := strings.TrimSpace(data.Symbol)
	if symbol == "" {
		symbol = strings.TrimSpace(notice.Symbol)
	}
	if symbol == "" {
		return quarantineMonthly(ctx, db, tracingNo, "", "empty_symbol", data, notice)
	}

	rawPeriod := strings.TrimSpace(data.PeriodEnd)
	if rawPeriod == "" {
		if t := period.FromTitle(notice.Title); t != nil {
			rawPeriod = *t
		}
	}

	canon := period.Canonicalize(rawPeriod)
	if canon == nil {
		return quarantineMonthly(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	parts := strings.Split(*canon, "/")
	if len(parts) != 3 {
		return quarantineMonthly(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	year, errY := strconv.Atoi(parts[0])
	month, errM := strconv.Atoi(parts[1])
	day, errD := strconv.Atoi(parts[2])
	if errY != nil || errM != nil || errD != nil || year < 1370 || year > 1430 || month < 1 || month > 12 || day < 1 || day > 31 {
		return quarantineMonthly(ctx, db, tracingNo, symbol, "invalid_period", data, notice)
	}

	query := `
	INSERT INTO monthly_sales (
		tracing_no, symbol, title, period_end, year, month,
		monthly_revenue, ytd_revenue, monthly_revenue_prev, ytd_revenue_prev,
		monthly_volume, ytd_volume, volume_unit, pdf_url
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	ON CONFLICT(tracing_no) DO UPDATE SET
		symbol = excluded.symbol,
		title = excluded.title,
		period_end = excluded.period_end,
		year = excluded.year,
		month = excluded.month,
		monthly_revenue = excluded.monthly_revenue,
		ytd_revenue = excluded.ytd_revenue,
		monthly_revenue_prev = excluded.monthly_revenue_prev,
		ytd_revenue_prev = excluded.ytd_revenue_prev,
		monthly_volume = excluded.monthly_volume,
		ytd_volume = excluded.ytd_volume,
		volume_unit = excluded.volume_unit,
		pdf_url = excluded.pdf_url
	`
	_, err := db.ExecContext(ctx, query,
		tracingNo, symbol, notice.Title, *canon, year, month,
		data.Revenue, data.YTDRevenue, data.PrevRevenue, data.PrevYTD,
		data.Volume, data.YTDVolume, data.Unit, notice.URL,
	)
	if err != nil {
		return fmt.Errorf("insert monthly_sales: %w", err)
	}

	// حذف احتمالی از قرنطینه در صورت تصحیح داده
	_, _ = db.ExecContext(ctx, "DELETE FROM codal_quarantine WHERE tracing_no = ?", tracingNo)

	return nil
}
