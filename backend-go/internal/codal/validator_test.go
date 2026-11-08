package codal

import (
	"context"
	"database/sql"
	"encoding/json"
	"math"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open in-memory sqlite db: %v", err)
	}
	t.Cleanup(func() {
		_ = db.Close()
	})
	if err := EnsureValidationSchema(db); err != nil {
		t.Fatalf("failed to ensure validation schema: %v", err)
	}
	return db
}

func TestValidateAndIngestStatement_HappyPath(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	data := &FinancialStatementData{
		TracingNo:        1001,
		Symbol:           "فولاد",
		PeriodEnd:        "1403/09/30",
		Months:           9,
		Revenue:          50000.0,
		GrossProfit:      15000.0,
		OperatingProfit:  12000.0,
		NetProfit:        10000.0,
		Assets:           80000.0,
		Liabilities:      30000.0,
		Equity:           50000.0,
		Capital:          20000.0,
		RetainedEarnings: 25000.0,
		EPS:              500.0,
		IsAudited:        true,
		IsConsolidated:   false,
		UnitNorm:         1000000.0,
	}

	notice := NoticeSummary{
		TracingNo:   1001,
		Symbol:      "فولاد",
		Title:       "اطلاعات و صورت‌های مالی میاندوره‌ای ۹ ماهه منتهی به ۱۴۰۳/۰۹/۳۰ (حسابرسی نشده)",
		LetterCode:  "ن-۳۰",
		PublishDate: "1403/10/15 14:30:00",
		CompanyName: "فولاد مبارکه اصفهان",
		URL:         "https://codal.ir/Reports/Decision.aspx?LetterSerial=1001",
	}

	err := ValidateAndIngestStatement(ctx, db, data, notice)
	if err != nil {
		t.Fatalf("unexpected error on valid statement: %v", err)
	}

	// بررسی درج دقیق داده در financial_statements
	var (
		symbol, companyName, title, reportKind, periodEnd, publishDate, fiscalYear, unit, url, fetchedAt, unitNorm string
		periodMonths, hasOpSales, isAudited, isConsol                                                               int
		rev, gp, op, np, assets, liab, eq, cap, re, eps                                                             float64
	)

	query := `
	SELECT symbol, company_name, title, report_kind, period_months, period_end, publish_date,
	       revenue, gross_profit, operating_profit, net_profit, total_assets, total_liabilities,
	       total_equity, capital, retained_earnings, basic_eps, unit, url, fetched_at,
	       has_operating_sales, is_audited, is_consolidated, fiscal_year, unit_norm
	FROM financial_statements WHERE tracing_no = ?
	`
	err = db.QueryRow(query, 1001).Scan(
		&symbol, &companyName, &title, &reportKind, &periodMonths, &periodEnd, &publishDate,
		&rev, &gp, &op, &np, &assets, &liab, &eq, &cap, &re, &eps, &unit, &url, &fetchedAt,
		&hasOpSales, &isAudited, &isConsol, &fiscalYear, &unitNorm,
	)
	if err != nil {
		t.Fatalf("failed to query financial_statements row: %v", err)
	}

	if symbol != "فولاد" {
		t.Errorf("symbol = %q, want 'فولاد'", symbol)
	}
	if companyName != "فولاد مبارکه اصفهان" {
		t.Errorf("companyName = %q, want 'فولاد مبارکه اصفهان'", companyName)
	}
	if periodEnd != "1403/09/30" {
		t.Errorf("periodEnd = %q, want '1403/09/30'", periodEnd)
	}
	if fiscalYear != "1403" {
		t.Errorf("fiscalYear = %q, want '1403'", fiscalYear)
	}
	if periodMonths != 9 {
		t.Errorf("periodMonths = %d, want 9", periodMonths)
	}
	if math.Abs(rev-50000.0) > 1e-6 {
		t.Errorf("rev = %f, want 50000.0", rev)
	}
	if math.Abs(assets-80000.0) > 1e-6 {
		t.Errorf("assets = %f, want 80000.0", assets)
	}
	if unitNorm != "mrl" {
		t.Errorf("unitNorm = %q, want 'mrl'", unitNorm)
	}
	if hasOpSales != 1 {
		t.Errorf("hasOpSales = %d, want 1", hasOpSales)
	}
	if isAudited != 1 {
		t.Errorf("isAudited = %d, want 1", isAudited)
	}
	if isConsol != 0 {
		t.Errorf("isConsolidated = %d, want 0", isConsol)
	}

	// اطمینان از عدم وجود در جدول قرنطینه
	var qCount int
	_ = db.QueryRow("SELECT count(*) FROM codal_quarantine WHERE tracing_no = 1001").Scan(&qCount)
	if qCount != 0 {
		t.Errorf("codal_quarantine count = %d, want 0", qCount)
	}
}

func TestValidateAndIngestMonthly_HappyPath(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	data := &MonthlyReportData{
		TracingNo:   2001,
		Symbol:      "فملی",
		PeriodEnd:   "1403/08/30",
		Year:        1403,
		Month:       8,
		Revenue:     12000.0,
		YTDRevenue:  85000.0,
		Volume:      1500.0,
		YTDVolume:   11000.0,
		Unit:        "تن",
	}

	notice := NoticeSummary{
		TracingNo:   2001,
		Symbol:      "فملی",
		Title:       "گزارش فعالیت ماهانه ۱ ماهه منتهی به ۱۴۰۳/۰۸/۳۰",
		PublishDate: "1403/09/05 10:00:00",
		URL:         "https://codal.ir/Reports/Decision.aspx?LetterSerial=2001",
	}

	err := ValidateAndIngestMonthly(ctx, db, data, notice)
	if err != nil {
		t.Fatalf("unexpected error on valid monthly report: %v", err)
	}

	var (
		symbol, title, periodEnd, pdfURL, volumeUnit string
		year, month                                 int
		monthlyRev, ytdRev, monthlyVol, ytdVol       float64
	)
	query := `
	SELECT symbol, title, period_end, year, month, monthly_revenue, ytd_revenue, monthly_volume, ytd_volume, volume_unit, pdf_url
	FROM monthly_sales WHERE tracing_no = ?
	`
	err = db.QueryRow(query, 2001).Scan(&symbol, &title, &periodEnd, &year, &month, &monthlyRev, &ytdRev, &monthlyVol, &ytdVol, &volumeUnit, &pdfURL)
	if err != nil {
		t.Fatalf("failed to query monthly_sales row: %v", err)
	}

	if symbol != "فملی" {
		t.Errorf("symbol = %q, want 'فملی'", symbol)
	}
	if periodEnd != "1403/08/30" {
		t.Errorf("periodEnd = %q, want '1403/08/30'", periodEnd)
	}
	if year != 1403 {
		t.Errorf("year = %d, want 1403", year)
	}
	if month != 8 {
		t.Errorf("month = %d, want 8", month)
	}
	if math.Abs(monthlyRev-12000.0) > 1e-6 {
		t.Errorf("monthlyRev = %f, want 12000.0", monthlyRev)
	}
	if math.Abs(ytdRev-85000.0) > 1e-6 {
		t.Errorf("ytdRev = %f, want 85000.0", ytdRev)
	}
	if volumeUnit != "تن" {
		t.Errorf("volumeUnit = %q, want 'تن'", volumeUnit)
	}
	if pdfURL != notice.URL {
		t.Errorf("pdfURL = %q, want %q", pdfURL, notice.URL)
	}

	var qCount int
	_ = db.QueryRow("SELECT count(*) FROM codal_quarantine WHERE tracing_no = 2001").Scan(&qCount)
	if qCount != 0 {
		t.Errorf("codal_quarantine count = %d, want 0", qCount)
	}
}

func TestValidate_NilData_Quarantined(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	notice := NoticeSummary{
		TracingNo:   8888,
		Symbol:      "شتران",
		Title:       "گزارش مخدوش آزمایشی",
		PublishDate: "1403/05/10 12:00:00",
		URL:         "https://codal.ir/Reports/Decision.aspx?LetterSerial=8888",
	}

	// ۱. ارسال داده nil برای صورت مالی
	err := ValidateAndIngestStatement(ctx, db, nil, notice)
	if err == nil || !IsQuarantined(err) {
		t.Fatalf("expected QuarantineError, got %v", err)
	}

	var rawPayload string
	err = db.QueryRow("SELECT raw_payload FROM codal_quarantine WHERE tracing_no = 8888").Scan(&rawPayload)
	if err != nil {
		t.Fatalf("failed to query quarantine row: %v", err)
	}
	if rawPayload == "null" || rawPayload == "" {
		t.Errorf("quarantine raw_payload should serialize notice, got %q", rawPayload)
	}
	if !strings.Contains(rawPayload, "گزارش مخدوش آزمایشی") {
		t.Errorf("quarantine raw_payload does not contain notice title: %s", rawPayload)
	}

	// ۲. ارسال داده nil برای گزارش ماهانه
	noticeMonthly := NoticeSummary{
		TracingNo:   9999,
		Symbol:      "شپنا",
		Title:       "گزارش ماهانه مخدوش",
		PublishDate: "1403/06/10 12:00:00",
		URL:         "https://codal.ir/Reports/Decision.aspx?LetterSerial=9999",
	}
	err = ValidateAndIngestMonthly(ctx, db, nil, noticeMonthly)
	if err == nil || !IsQuarantined(err) {
		t.Fatalf("expected QuarantineError for monthly, got %v", err)
	}

	var rawMonthlyPayload string
	err = db.QueryRow("SELECT raw_payload FROM codal_quarantine WHERE tracing_no = 9999").Scan(&rawMonthlyPayload)
	if err != nil {
		t.Fatalf("failed to query quarantine monthly row: %v", err)
	}
	if rawMonthlyPayload == "null" || rawMonthlyPayload == "" {
		t.Errorf("quarantine raw_payload should serialize notice, got %q", rawMonthlyPayload)
	}
	if !strings.Contains(rawMonthlyPayload, "گزارش ماهانه مخدوش") {
		t.Errorf("quarantine raw_payload does not contain notice title: %s", rawMonthlyPayload)
	}
}

func TestValidate_InvalidPeriod_Quarantined(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	invalidDates := []struct {
		desc string
		date string
	}{
		{"empty_date", ""},
		{"malformed_string", "not-a-date"},
		{"year_too_early", "1365/01/01"},
		{"year_too_late", "1435/01/01"},
		{"month_out_of_range", "1403/13/01"},
		{"day_out_of_range", "1403/06/32"},
	}

	for idx, tt := range invalidDates {
		tn := int64(3000 + idx)
		data := &FinancialStatementData{
			TracingNo: tn,
			Symbol:    "فولاد",
			PeriodEnd: tt.date,
			Months:    3,
			Revenue:   1000.0,
			Assets:    5000.0,
		}
		notice := NoticeSummary{
			TracingNo: tn,
			Symbol:    "فولاد",
			Title:     "گزارش صورت مالی بدون تاریخ معتبر",
		}

		err := ValidateAndIngestStatement(ctx, db, data, notice)
		if err == nil {
			t.Fatalf("[%s] expected quarantine error, got nil", tt.desc)
		}
		if !IsQuarantined(err) {
			t.Fatalf("[%s] expected error to be QuarantineError, got %v", tt.desc, err)
		}
		if QuarantineReason(err) != "invalid_period" {
			t.Errorf("[%s] QuarantineReason = %q, want 'invalid_period'", tt.desc, QuarantineReason(err))
		}

		// بررسی جدول codal_quarantine
		var qReason, rawPayload string
		qErr := db.QueryRow("SELECT reason, raw_payload FROM codal_quarantine WHERE tracing_no = ?", tn).Scan(&qReason, &rawPayload)
		if qErr != nil {
			t.Fatalf("[%s] row not found in codal_quarantine: %v", tt.desc, qErr)
		}
		if qReason != "invalid_period" {
			t.Errorf("[%s] db quarantine reason = %q, want 'invalid_period'", tt.desc, qReason)
		}

		// اطمینان از صحت ساختار JSON پی‌لود ذخیره‌شده
		var payloadCheck map[string]any
		if jsonErr := json.Unmarshal([]byte(rawPayload), &payloadCheck); jsonErr != nil {
			t.Errorf("[%s] raw_payload is not valid JSON: %v", tt.desc, jsonErr)
		}

		// اطمینان از عدم درج در financial_statements
		var fsCount int
		_ = db.QueryRow("SELECT count(*) FROM financial_statements WHERE tracing_no = ?", tn).Scan(&fsCount)
		if fsCount != 0 {
			t.Errorf("[%s] row found in financial_statements, count = %d", tt.desc, fsCount)
		}
	}
}

func TestValidate_EmptySymbol_Quarantined(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	data := &FinancialStatementData{
		TracingNo: 4001,
		Symbol:    "   ",
		PeriodEnd: "1403/09/30",
		Assets:    10000.0,
	}
	notice := NoticeSummary{
		TracingNo: 4001,
		Symbol:    "",
		Title:     "گزارش منتهی به ۱۴۰۳/۰۹/۳۰",
	}

	err := ValidateAndIngestStatement(ctx, db, data, notice)
	if err == nil {
		t.Fatal("expected quarantine error for empty symbol, got nil")
	}
	if !IsQuarantined(err) {
		t.Fatalf("expected QuarantineError, got %v", err)
	}
	if QuarantineReason(err) != "empty_symbol" {
		t.Errorf("QuarantineReason = %q, want 'empty_symbol'", QuarantineReason(err))
	}

	var reason string
	err = db.QueryRow("SELECT reason FROM codal_quarantine WHERE tracing_no = 4001").Scan(&reason)
	if err != nil {
		t.Fatalf("quarantine row not found: %v", err)
	}
	if reason != "empty_symbol" {
		t.Errorf("quarantine reason in db = %q, want 'empty_symbol'", reason)
	}

	var count int
	_ = db.QueryRow("SELECT count(*) FROM financial_statements WHERE tracing_no = 4001").Scan(&count)
	if count != 0 {
		t.Errorf("financial_statements count = %d, want 0", count)
	}
}

func TestValidate_CorruptNumbers_Quarantined(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	// جمع دارایی‌ها منفی (خرابی شدید داده)
	data := &FinancialStatementData{
		TracingNo: 5001,
		Symbol:    "خودرو",
		PeriodEnd: "1403/06/31",
		Months:    6,
		Revenue:   20000.0,
		Assets:    -150000.0, // منفی!
	}
	notice := NoticeSummary{
		TracingNo: 5001,
		Symbol:    "خودرو",
		Title:     "اطلاعات ۶ ماهه منتهی به ۱۴۰۳/۰۶/۳۱",
	}

	err := ValidateAndIngestStatement(ctx, db, data, notice)
	if err == nil {
		t.Fatal("expected quarantine error for negative assets, got nil")
	}
	if !IsQuarantined(err) {
		t.Fatalf("expected QuarantineError, got %v", err)
	}
	if QuarantineReason(err) != "negative_assets" {
		t.Errorf("QuarantineReason = %q, want 'negative_assets'", QuarantineReason(err))
	}

	var reason string
	err = db.QueryRow("SELECT reason FROM codal_quarantine WHERE tracing_no = 5001").Scan(&reason)
	if err != nil {
		t.Fatalf("quarantine row not found: %v", err)
	}
	if reason != "negative_assets" {
		t.Errorf("quarantine reason in db = %q, want 'negative_assets'", reason)
	}

	var count int
	_ = db.QueryRow("SELECT count(*) FROM financial_statements WHERE tracing_no = 5001").Scan(&count)
	if count != 0 {
		t.Errorf("financial_statements count = %d, want 0", count)
	}
}

func TestValidate_Idempotency(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	// ۱. تست عدم تکرار در صورت‌های مالی (Financial Statements)
	fsData := &FinancialStatementData{
		TracingNo: 6001,
		Symbol:    "شپنا",
		PeriodEnd: "1403/09/30",
		Months:    9,
		Revenue:   10000.0,
		Assets:    50000.0,
	}
	fsNotice := NoticeSummary{
		TracingNo: 6001,
		Symbol:    "شپنا",
		Title:     "صورت‌های مالی ۹ ماهه منتهی به ۱۴۰۳/۰۹/۳۰",
	}

	// درج اول
	if err := ValidateAndIngestStatement(ctx, db, fsData, fsNotice); err != nil {
		t.Fatalf("first statement ingestion failed: %v", err)
	}

	// بروزرسانی درآمد و درج مجدد با همان شماره پیگیری (TracingNo)
	fsData.Revenue = 25000.0
	if err := ValidateAndIngestStatement(ctx, db, fsData, fsNotice); err != nil {
		t.Fatalf("second statement ingestion (idempotent upsert) failed: %v", err)
	}

	var fsCount int
	var fsRev float64
	_ = db.QueryRow("SELECT count(*), revenue FROM financial_statements WHERE tracing_no = 6001").Scan(&fsCount, &fsRev)
	if fsCount != 1 {
		t.Errorf("financial_statements row count = %d, want exactly 1", fsCount)
	}
	if math.Abs(fsRev-25000.0) > 1e-6 {
		t.Errorf("revenue after upsert = %f, want 25000.0", fsRev)
	}

	// ۲. تست عدم تکرار در فروش ماهانه (Monthly Sales)
	msData := &MonthlyReportData{
		TracingNo:  6002,
		Symbol:     "شتران",
		PeriodEnd:  "1403/08/30",
		Revenue:    3000.0,
		YTDRevenue: 20000.0,
	}
	msNotice := NoticeSummary{
		TracingNo: 6002,
		Symbol:    "شتران",
		Title:     "گزارش فعالیت ماهانه ۱ ماهه منتهی به ۱۴۰۳/۰۸/۳۰",
	}

	// درج اول
	if err := ValidateAndIngestMonthly(ctx, db, msData, msNotice); err != nil {
		t.Fatalf("first monthly ingestion failed: %v", err)
	}

	// بروزرسانی و درج مجدد
	msData.Revenue = 4500.0
	if err := ValidateAndIngestMonthly(ctx, db, msData, msNotice); err != nil {
		t.Fatalf("second monthly ingestion failed: %v", err)
	}

	var msCount int
	var msRev float64
	qErr := db.QueryRow("SELECT count(*), monthly_revenue FROM monthly_sales WHERE tracing_no = 6002").Scan(&msCount, &msRev)
	if qErr != nil {
		t.Fatalf("failed to query monthly_sales: %v", qErr)
	}
	if msCount != 1 {
		t.Errorf("monthly_sales row count = %d, want exactly 1", msCount)
	}
	if math.Abs(msRev-4500.0) > 1e-6 {
		t.Errorf("monthly revenue after upsert = %f, want 4500.0", msRev)
	}
}

func TestQuarantineReport_Direct(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	payload := `{"test":"custom_corrupt_data"}`
	err := QuarantineReport(ctx, db, 7001, "وبملت", "bank_statement", "manual_audit_flag", payload)
	if err != nil {
		t.Fatalf("unexpected error calling QuarantineReport: %v", err)
	}

	var sym, repType, reason, raw string
	err = db.QueryRow("SELECT symbol, report_type, reason, raw_payload FROM codal_quarantine WHERE tracing_no = 7001").Scan(
		&sym, &repType, &reason, &raw,
	)
	if err != nil {
		t.Fatalf("failed to query codal_quarantine: %v", err)
	}
	if sym != "وبملت" || repType != "bank_statement" || reason != "manual_audit_flag" || raw != payload {
		t.Errorf("unexpected quarantine fields: sym=%s, repType=%s, reason=%s, raw=%s", sym, repType, reason, raw)
	}
}
