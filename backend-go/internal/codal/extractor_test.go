package codal

import (
	"os"
	"path/filepath"
	"testing"
)

func TestParseNumericValue(t *testing.T) {
	tests := []struct {
		input    string
		expected float64
		ok       bool
	}{
		{"۱,۲۵۰,۰۰۰", 1250000.0, true},
		{"(۷۵۰,۰۰۰)", -750000.0, true},
		{"( 750,000 )", -750000.0, true},
		{"-350,000", -350000.0, true},
		{"1291.5", 1291.5, true},
		{"—", 0, false},
		{"-", 0, false},
		{"", 0, false},
		{"نامعتبر", 0, false},
	}

	for _, tc := range tests {
		val, ok := parseNumericValue(tc.input)
		if ok != tc.ok {
			t.Errorf("input %s: expected ok=%v, got %v", tc.input, tc.ok, ok)
		}
		if ok && val != tc.expected {
			t.Errorf("input %s: expected val=%f, got %f", tc.input, tc.expected, val)
		}
	}
}

func TestCanonicalizePeriod(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"منتهی به ۱۴۰۳/۰۶/۳۱", "1403/06/31"},
		{"1404-9-30", "1404/09/30"},
		{"دوره ۱ ماهه منتهی به  ۱۴۰۴/۰۹/۳۰(اصلاحیه)", "1404/09/30"},
		{"۱۴۰۳/۱۳/۴۰", ""}, // تاریخ غیرمجاز
	}

	for _, tc := range tests {
		got := parsePeriodEndFromTitle(tc.input)
		if got != tc.expected {
			t.Errorf("input %s: expected %s, got %s", tc.input, tc.expected, got)
		}
	}
}

func TestParsePeriodMonthsFromTitle(t *testing.T) {
	tests := []struct {
		title    string
		expected int
	}{
		{"اطلاعات و صورت‌های مالی میاندوره‌ای دوره ۶ ماهه منتهی به ۱۴۰۳/۰۶/۳۱", 6},
		{"اطلاعات و صورت‌های مالی دوره ۳ ماهه منتهی به ۱۴۰۳/۰۳/۳۱", 3},
		{"گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۳/۰۱/۳۱", 1},
		{"صورت‌های مالی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹", 12},
	}

	for _, tc := range tests {
		got := parsePeriodMonthsFromTitle(tc.title)
		if got != tc.expected {
			t.Errorf("title %s: expected months=%d, got %d", tc.title, tc.expected, got)
		}
	}
}

func TestExtractMonthlySales_RealFoolad(t *testing.T) {
	fixturePath := filepath.Join("testdata", "foolad_monthly.html")
	content, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("failed to read fixture %s: %v", fixturePath, err)
	}

	notice := NoticeSummary{
		TracingNo: 1465497,
		Symbol:    "فولاد",
		Title:     "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۴/۰۹/۳۰(اصلاحیه)",
	}

	data, err := ExtractMonthlySales(content, notice)
	if err != nil {
		t.Fatalf("ExtractMonthlySales error: %v", err)
	}
	if data == nil {
		t.Fatal("expected non-nil MonthlyReportData")
	}

	if data.Symbol != "فولاد" {
		t.Errorf("expected symbol فولاد, got %s", data.Symbol)
	}
	if data.TracingNo != 1465497 {
		t.Errorf("expected tracing_no 1465497, got %d", data.TracingNo)
	}
	if data.PeriodEnd != "1404/09/30" {
		t.Errorf("expected period_end 1404/09/30, got %s", data.PeriodEnd)
	}
	if data.Year != 1404 || data.Month != 9 {
		t.Errorf("expected year=1404, month=9, got year=%d, month=%d", data.Year, data.Month)
	}
	if data.Revenue != 265273912.0 {
		t.Errorf("expected Revenue 265273912.0, got %f", data.Revenue)
	}
	if data.YTDRevenue != 2362294472.0 {
		t.Errorf("expected YTDRevenue 2362294472.0, got %f", data.YTDRevenue)
	}
	if data.PrevYTD != 2030219860.0 {
		t.Errorf("expected PrevYTD 2030219860.0, got %f", data.PrevYTD)
	}
	if data.Volume != 644.0 {
		t.Errorf("expected Volume 644.0, got %f", data.Volume)
	}
	if data.YTDVolume != 6374.0 {
		t.Errorf("expected YTDVolume 6374.0, got %f", data.YTDVolume)
	}
	if data.Unit != "هزارتن" {
		t.Errorf("expected Unit هزارتن, got %s", data.Unit)
	}
}

func TestExtractFinancialStatements_RealFmeli(t *testing.T) {
	incContent, err := os.ReadFile(filepath.Join("testdata", "fmeli_income.html"))
	if err != nil {
		t.Fatalf("failed to read fmeli_income.html: %v", err)
	}
	balContent, err := os.ReadFile(filepath.Join("testdata", "fmeli_balance.html"))
	if err != nil {
		t.Fatalf("failed to read fmeli_balance.html: %v", err)
	}

	notice := NoticeSummary{
		TracingNo: 1617671,
		Symbol:    "فملی",
		Title:     "اطلاعات و صورت‌های مالی میاندوره‌ای تلفیقی دوره ۶ ماهه منتهی به  ۱۴۰۵/۰۶/۳۱ (حسابرسی نشده)",
	}

	sheets := map[string][]byte{
		"1": incContent,
		"0": balContent,
	}

	data, err := ExtractFinancialStatements(sheets, notice)
	if err != nil {
		t.Fatalf("ExtractFinancialStatements error: %v", err)
	}
	if data == nil {
		t.Fatal("expected non-nil FinancialStatementData")
	}

	if data.Symbol != "فملی" {
		t.Errorf("expected symbol فملی, got %s", data.Symbol)
	}
	if data.TracingNo != 1617671 {
		t.Errorf("expected tracing_no 1617671, got %d", data.TracingNo)
	}
	if data.PeriodEnd != "1405/06/31" {
		t.Errorf("expected period_end 1405/06/31, got %s", data.PeriodEnd)
	}
	if data.Months != 6 {
		t.Errorf("expected Months=6, got %d", data.Months)
	}
	if data.IsAudited != false {
		t.Errorf("expected IsAudited=false, got %v", data.IsAudited)
	}

	// تطبیق با مقادیر استخراج‌شده واقعی از کدال:
	if data.Revenue != 3298998075.0 {
		t.Errorf("expected Revenue 3298998075.0, got %f", data.Revenue)
	}
	if data.GrossProfit != 2388889134.0 {
		t.Errorf("expected GrossProfit 2388889134.0, got %f", data.GrossProfit)
	}
	if data.OperatingProfit != 2149882780.0 {
		t.Errorf("expected OperatingProfit 2149882780.0, got %f", data.OperatingProfit)
	}
	if data.NetProfit != 1858542129.0 {
		t.Errorf("expected NetProfit 1858542129.0, got %f", data.NetProfit)
	}
	if data.EPS != 1291.0 {
		t.Errorf("expected EPS 1291.0, got %f", data.EPS)
	}
	if data.Assets != 7982912937.0 {
		t.Errorf("expected Assets 7982912937.0, got %f", data.Assets)
	}
	if data.Liabilities != 3527254294.0 {
		t.Errorf("expected Liabilities 3527254294.0, got %f", data.Liabilities)
	}
	if data.Equity != 4455658643.0 {
		t.Errorf("expected Equity 4455658643.0, got %f", data.Equity)
	}
	if data.Capital != 1440000000.0 {
		t.Errorf("expected Capital 1440000000.0, got %f", data.Capital)
	}
	if data.RetainedEarnings != 2908023546.0 {
		t.Errorf("expected RetainedEarnings 2908023546.0, got %f", data.RetainedEarnings)
	}
}

func TestExtractMonthlySales_HTMLTable(t *testing.T) {
	fixturePath := filepath.Join("testdata", "table_sample_monthly.html")
	content, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("failed to read fixture %s: %v", fixturePath, err)
	}

	notice := NoticeSummary{
		TracingNo: 999901,
		Symbol:    "تست",
		Title:     "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۳/۰۵/۳۱ نماد تست",
	}

	data, err := ExtractMonthlySales(content, notice)
	if err != nil {
		t.Fatalf("ExtractMonthlySales error: %v", err)
	}
	if data == nil {
		t.Fatal("expected non-nil MonthlyReportData")
	}

	if data.Symbol != "تست" {
		t.Errorf("expected symbol تست, got %s", data.Symbol)
	}
	if data.PeriodEnd != "1403/05/31" {
		t.Errorf("expected period_end 1403/05/31, got %s", data.PeriodEnd)
	}
	if data.Year != 1403 || data.Month != 5 {
		t.Errorf("expected year=1403, month=5, got year=%d, month=%d", data.Year, data.Month)
	}
	if data.Revenue != 60000.0 {
		t.Errorf("expected Revenue 60000.0, got %f", data.Revenue)
	}
	if data.YTDRevenue != 300000.0 {
		t.Errorf("expected YTDRevenue 300000.0, got %f", data.YTDRevenue)
	}
	if data.PrevRevenue != 49000.0 {
		t.Errorf("expected PrevRevenue 49000.0, got %f", data.PrevRevenue)
	}
	if data.PrevYTD != 245000.0 {
		t.Errorf("expected PrevYTD 245000.0, got %f", data.PrevYTD)
	}
	if data.Volume != 2000.0 {
		t.Errorf("expected Volume 2000.0, got %f", data.Volume)
	}
	if data.YTDVolume != 10000.0 {
		t.Errorf("expected YTDVolume 10000.0, got %f", data.YTDVolume)
	}
	if data.Unit != "تن" {
		t.Errorf("expected Unit تن, got %s", data.Unit)
	}
}

func TestExtractFinancialStatements_HTMLTable(t *testing.T) {
	incContent, err := os.ReadFile(filepath.Join("testdata", "table_sample_fs_income.html"))
	if err != nil {
		t.Fatalf("failed to read table_sample_fs_income.html: %v", err)
	}
	balContent, err := os.ReadFile(filepath.Join("testdata", "table_sample_fs_balance.html"))
	if err != nil {
		t.Fatalf("failed to read table_sample_fs_balance.html: %v", err)
	}

	notice := NoticeSummary{
		TracingNo: 999902,
		Symbol:    "تست",
		Title:     "صورت‌های مالی دوره ۶ ماهه منتهی به ۱۴۰۳/۰۶/۳۱ (حسابرسی شده)",
	}

	sheets := map[string][]byte{
		"صورت سود و زیان":   incContent,
		"صورت وضعیت مالی": balContent,
	}

	data, err := ExtractFinancialStatements(sheets, notice)
	if err != nil {
		t.Fatalf("ExtractFinancialStatements error: %v", err)
	}
	if data == nil {
		t.Fatal("expected non-nil FinancialStatementData")
	}

	if data.Symbol != "تست" {
		t.Errorf("expected symbol تست, got %s", data.Symbol)
	}
	if data.PeriodEnd != "1403/06/31" {
		t.Errorf("expected period_end 1403/06/31, got %s", data.PeriodEnd)
	}
	if data.Months != 6 {
		t.Errorf("expected Months=6, got %d", data.Months)
	}
	if data.IsAudited != true {
		t.Errorf("expected IsAudited=true, got %v", data.IsAudited)
	}
	if data.Revenue != 1250000.0 {
		t.Errorf("expected Revenue 1250000.0, got %f", data.Revenue)
	}
	if data.GrossProfit != 500000.0 {
		t.Errorf("expected GrossProfit 500000.0, got %f", data.GrossProfit)
	}
	if data.OperatingProfit != 400000.0 {
		t.Errorf("expected OperatingProfit 400000.0, got %f", data.OperatingProfit)
	}
	if data.NetProfit != 350000.0 {
		t.Errorf("expected NetProfit 350000.0, got %f", data.NetProfit)
	}
	if data.EPS != 350.0 {
		t.Errorf("expected EPS 350.0, got %f", data.EPS)
	}
	if data.Assets != 4000000.0 {
		t.Errorf("expected Assets 4000000.0, got %f", data.Assets)
	}
	if data.Liabilities != 1200000.0 {
		t.Errorf("expected Liabilities 1200000.0, got %f", data.Liabilities)
	}
	if data.Equity != 2800000.0 {
		t.Errorf("expected Equity 2800000.0, got %f", data.Equity)
	}
	if data.Capital != 1000000.0 {
		t.Errorf("expected Capital 1000000.0, got %f", data.Capital)
	}
	if data.RetainedEarnings != 1800000.0 {
		t.Errorf("expected RetainedEarnings 1800000.0, got %f", data.RetainedEarnings)
	}
}
