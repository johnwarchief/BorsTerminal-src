package codal

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func setupAuditTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open in-memory db: %v", err)
	}

	ddls := []string{
		`CREATE TABLE instruments (
			ins_code TEXT PRIMARY KEY,
			l_val18 TEXT,
			l_val30 TEXT,
			sector_code TEXT,
			sector_name TEXT
		);`,
		`CREATE TABLE market_watch (
			ins_code TEXT PRIMARY KEY,
			p_closing REAL,
			p_last REAL
		);`,
		`CREATE TABLE client_type (
			ins_code TEXT,
			d_even INTEGER,
			buy_i_vol REAL,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE TABLE client_type_value (
			ins_code TEXT,
			d_even INTEGER,
			buy_i_val REAL,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE TABLE price_adjust_events (
			ins_code TEXT,
			d_even INTEGER,
			symbol TEXT,
			p_closing REAL,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE TABLE share_change_events (
			ins_code TEXT,
			d_even INTEGER,
			symbol TEXT,
			shares_new REAL,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE TABLE codal_notices (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			tracing_no INTEGER,
			symbol TEXT,
			title TEXT
		);`,
		`CREATE TABLE financial_statements (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			tracing_no INTEGER,
			symbol TEXT,
			period_end TEXT,
			revenue REAL
		);`,
		`CREATE TABLE monthly_sales (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			tracing_no INTEGER,
			symbol TEXT,
			year INTEGER,
			month INTEGER,
			monthly_revenue REAL
		);`,
		`CREATE TABLE codal_quarantine (
			tracing_no INTEGER PRIMARY KEY,
			symbol TEXT,
			reason TEXT
		);`,
		`CREATE TABLE fts_results (
			symbol TEXT PRIMARY KEY,
			score INTEGER,
			verdict TEXT
		);`,
	}

	for _, ddl := range ddls {
		if _, err := db.Exec(ddl); err != nil {
			t.Fatalf("setup ddl failed %s: %v", ddl, err)
		}
	}

	return db
}

func TestAuditMarketUniverse_Normal(t *testing.T) {
	ctx := context.Background()
	db := setupAuditTestDB(t)
	defer db.Close()

	// درج داده‌های عادی
	_, _ = db.Exec("INSERT INTO instruments VALUES ('INS1', 'فولاد', 'فولاد مبارکه', '27', 'فلزات اساسی')")
	_, _ = db.Exec("INSERT INTO instruments VALUES ('INS2', 'فملی', 'ملی مس', '27', 'فلزات اساسی')")
	_, _ = db.Exec("INSERT INTO instruments VALUES ('INS3', 'شپنا', 'پالایش نفت اصفهان', '23', 'فرآورده‌های نفتی')")

	_, _ = db.Exec("INSERT INTO market_watch VALUES ('INS1', 5000, 5050)")
	_, _ = db.Exec("INSERT INTO market_watch VALUES ('INS2', 7000, 7100)")

	_, _ = db.Exec("INSERT INTO client_type VALUES ('INS1', 14030801, 100000)")
	_, _ = db.Exec("INSERT INTO client_type_value VALUES ('INS1', 14030801, 500000000)")

	_, _ = db.Exec("INSERT INTO price_adjust_events VALUES ('INS1', 14030501, 'فولاد', 4800)")
	_, _ = db.Exec("INSERT INTO share_change_events VALUES ('INS2', 14030601, 'فملی', 1000000000)")

	_, _ = db.Exec("INSERT INTO codal_notices (tracing_no, symbol, title) VALUES (101, 'فولاد', 'گزارش ماهانه')")
	_, _ = db.Exec("INSERT INTO codal_notices (tracing_no, symbol, title) VALUES (102, 'فملی', 'صورت مالی ۶ ماهه')")

	_, _ = db.Exec("INSERT INTO financial_statements (tracing_no, symbol, period_end, revenue) VALUES (201, 'فولاد', '1403/06/31', 1000)")
	_, _ = db.Exec("INSERT INTO financial_statements (tracing_no, symbol, period_end, revenue) VALUES (202, 'فملی', '1403/06/31', 2000)")

	_, _ = db.Exec("INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue) VALUES (301, 'فولاد', 1403, 1, 500)")
	_, _ = db.Exec("INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue) VALUES (302, 'فولاد', 1403, 2, 550)")
	_, _ = db.Exec("INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue) VALUES (303, 'فولاد', 1403, 3, 600)")

	_, _ = db.Exec("INSERT INTO fts_results VALUES ('فولاد', 5, 'STRONG')")
	_, _ = db.Exec("INSERT INTO fts_results VALUES ('فملی', 4, 'WATCH')")
	_, _ = db.Exec("INSERT INTO fts_results VALUES ('شپنا', 2, 'REJECT')")

	rep, err := AuditMarketUniverse(ctx, db)
	if err != nil {
		t.Fatalf("AuditMarketUniverse failed: %v", err)
	}

	if rep.InstrumentCount != 3 {
		t.Errorf("InstrumentCount = %d, want 3", rep.InstrumentCount)
	}
	if rep.ActiveInstruments != 2 {
		t.Errorf("ActiveInstruments = %d, want 2", rep.ActiveInstruments)
	}
	if rep.SectorCount != 2 {
		t.Errorf("SectorCount = %d, want 2", rep.SectorCount)
	}
	if rep.MarketWatchCount != 2 {
		t.Errorf("MarketWatchCount = %d, want 2", rep.MarketWatchCount)
	}
	if rep.ClientTypeCount != 1 {
		t.Errorf("ClientTypeCount = %d, want 1", rep.ClientTypeCount)
	}
	if rep.ClientTypeValueCount != 1 {
		t.Errorf("ClientTypeValueCount = %d, want 1", rep.ClientTypeValueCount)
	}
	if rep.PriceAdjustEventsCount != 1 {
		t.Errorf("PriceAdjustEventsCount = %d, want 1", rep.PriceAdjustEventsCount)
	}
	if rep.ShareChangeEventsCount != 1 {
		t.Errorf("ShareChangeEventsCount = %d, want 1", rep.ShareChangeEventsCount)
	}
	if rep.CorporateSymbolsCovered != 2 {
		t.Errorf("CorporateSymbolsCovered = %d, want 2", rep.CorporateSymbolsCovered)
	}
	if rep.CodalNoticesTotal != 2 {
		t.Errorf("CodalNoticesTotal = %d, want 2", rep.CodalNoticesTotal)
	}
	if rep.CodalStatementsTotal != 2 {
		t.Errorf("CodalStatementsTotal = %d, want 2", rep.CodalStatementsTotal)
	}
	if rep.CodalMonthlyTotal != 3 {
		t.Errorf("CodalMonthlyTotal = %d, want 3", rep.CodalMonthlyTotal)
	}
	if rep.QuarantineCount != 0 {
		t.Errorf("QuarantineCount = %d, want 0", rep.QuarantineCount)
	}
	if rep.DuplicateNoticesCount != 0 {
		t.Errorf("DuplicateNoticesCount = %d, want 0", rep.DuplicateNoticesCount)
	}
	if len(rep.DuplicateTracingNos) != 0 {
		t.Errorf("DuplicateTracingNos len = %d, want 0", len(rep.DuplicateTracingNos))
	}
	if rep.FTSResultsCount != 3 {
		t.Errorf("FTSResultsCount = %d, want 3", rep.FTSResultsCount)
	}
	if rep.FTSPassCount != 1 {
		t.Errorf("FTSPassCount = %d, want 1", rep.FTSPassCount)
	}
	if rep.FTSMarginalCount != 1 {
		t.Errorf("FTSMarginalCount = %d, want 1", rep.FTSMarginalCount)
	}
	if rep.FTSFailCount != 1 {
		t.Errorf("FTSFailCount = %d, want 1", rep.FTSFailCount)
	}
	if len(rep.DataAnomalies) != 0 {
		t.Errorf("DataAnomalies len = %d, want 0 (got %v)", len(rep.DataAnomalies), rep.DataAnomalies)
	}
}

func TestAuditMarketUniverse_Anomalies(t *testing.T) {
	ctx := context.Background()
	db := setupAuditTestDB(t)
	defer db.Close()

	// 1. Duplicate tracing_no in codal_notices
	_, _ = db.Exec("INSERT INTO codal_notices (tracing_no, symbol, title) VALUES (5001, 'فولاد', 'نخستین')")
	_, _ = db.Exec("INSERT INTO codal_notices (tracing_no, symbol, title) VALUES (5001, 'فولاد', 'تکراری')")

	// 2. Duplicate (symbol, period_end) in financial_statements
	_, _ = db.Exec("INSERT INTO financial_statements (tracing_no, symbol, period_end, revenue) VALUES (6001, 'فولاد', '1403/06/31', 1000)")
	_, _ = db.Exec("INSERT INTO financial_statements (tracing_no, symbol, period_end, revenue) VALUES (6002, 'فولاد', '1403/06/31', 1050)")

	// 3. Month sequence gap in monthly_sales: month 1 and month 4 (gap of 2 months)
	_, _ = db.Exec("INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue) VALUES (7001, 'فولاد', 1403, 1, 500)")
	_, _ = db.Exec("INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue) VALUES (7002, 'فولاد', 1403, 4, 700)")

	// 4. Quarantine record
	_, _ = db.Exec("INSERT INTO codal_quarantine (tracing_no, symbol, reason) VALUES (8001, 'خساپا', 'negative_equity')")

	rep, err := AuditMarketUniverse(ctx, db)
	if err != nil {
		t.Fatalf("AuditMarketUniverse failed: %v", err)
	}

	if rep.DuplicateNoticesCount != 1 {
		t.Errorf("DuplicateNoticesCount = %d, want 1", rep.DuplicateNoticesCount)
	}
	if len(rep.DuplicateTracingNos) != 1 || rep.DuplicateTracingNos[0] != 5001 {
		t.Errorf("DuplicateTracingNos = %v, want [5001]", rep.DuplicateTracingNos)
	}
	if rep.QuarantineCount != 1 {
		t.Errorf("QuarantineCount = %d, want 1", rep.QuarantineCount)
	}
	if rep.QuarantineErrors["negative_equity"] != 1 {
		t.Errorf("QuarantineErrors[negative_equity] = %d, want 1", rep.QuarantineErrors["negative_equity"])
	}

	if len(rep.DataAnomalies) != 4 {
		t.Errorf("expected 4 anomalies, got %d: %v", len(rep.DataAnomalies), rep.DataAnomalies)
	}
}

func TestAuditMarketUniverse_CompanionCodalDB(t *testing.T) {
	ctx := context.Background()
	tempDir := t.TempDir()

	marketPath := filepath.Join(tempDir, "market.db")
	codalPath := filepath.Join(tempDir, "codal.db")

	mDB, err := sql.Open("sqlite", marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	defer mDB.Close()

	cDB, err := sql.Open("sqlite", codalPath)
	if err != nil {
		t.Fatalf("open codal.db: %v", err)
	}
	defer cDB.Close()

	// Tables in market.db
	_, err = mDB.Exec(`
		CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT);
		CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY);
		INSERT INTO instruments VALUES ('INS1', 'فولاد', 'فولاد مبارکه', '27');
		INSERT INTO market_watch VALUES ('INS1');
	`)
	if err != nil {
		t.Fatalf("init market.db tables: %v", err)
	}

	// Tables in codal.db
	_, err = cDB.Exec(`
		CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT);
		CREATE TABLE financial_statements (tracing_no INTEGER PRIMARY KEY, symbol TEXT, period_end TEXT);
		INSERT INTO codal_notices VALUES (9001, 'فولاد');
		INSERT INTO financial_statements VALUES (9002, 'فولاد', '1403/06/31');
	`)
	if err != nil {
		t.Fatalf("init codal.db tables: %v", err)
	}

	rep, err := AuditMarketUniverse(ctx, mDB)
	if err != nil {
		t.Fatalf("AuditMarketUniverse with companion codal.db failed: %v", err)
	}

	if rep.InstrumentCount != 1 {
		t.Errorf("InstrumentCount = %d, want 1", rep.InstrumentCount)
	}
	if rep.CodalNoticesTotal != 1 {
		t.Errorf("CodalNoticesTotal = %d, want 1", rep.CodalNoticesTotal)
	}
	if rep.CodalStatementsTotal != 1 {
		t.Errorf("CodalStatementsTotal = %d, want 1", rep.CodalStatementsTotal)
	}
}
