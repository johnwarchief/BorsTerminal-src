package codal

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func setupRecalcTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "recalc_test.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("failed to open test sqlite db: %v", err)
	}
	t.Cleanup(func() {
		_ = db.Close()
	})

	if err := EnsureValidationSchema(db); err != nil {
		t.Fatalf("failed to ensure validation schema: %v", err)
	}
	if err := EnsureRecalcSchema(db); err != nil {
		t.Fatalf("failed to ensure recalc schema: %v", err)
	}

	additionalDDL := `
	CREATE TABLE IF NOT EXISTS instruments (
		ins_code TEXT PRIMARY KEY,
		l_val18 TEXT,
		l_val30 TEXT,
		sector_name TEXT,
		updated_at TEXT,
		paper_type INTEGER,
		total_shares REAL
	);
	CREATE TABLE IF NOT EXISTS market_watch (
		ins_code TEXT,
		d_even INTEGER,
		market_cap REAL,
		market_cap_src TEXT
	);
	CREATE TABLE IF NOT EXISTS daily_prices (
		ins_code TEXT,
		d_even INTEGER,
		q_tot_cap REAL,
		market_cap REAL,
		market_cap_src TEXT
	);
	CREATE TABLE IF NOT EXISTS codal_notices (
		tracing_no INTEGER,
		symbol TEXT,
		publish_date TEXT
	);
	CREATE TABLE IF NOT EXISTS price_history (
		symbol TEXT
	);
	CREATE TABLE IF NOT EXISTS user_watchlists (
		symbol TEXT
	);
	`
	if _, err := db.Exec(additionalDDL); err != nil {
		t.Fatalf("failed to execute additional DDL: %v", err)
	}

	return db
}

func TestDirtySymbols_Lifecycle(t *testing.T) {
	db := setupRecalcTestDB(t)
	ctx := context.Background()

	// ۱) در ابتدا جدول خالی است
	symbols, err := GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("unexpected error getting dirty symbols: %v", err)
	}
	if len(symbols) != 0 {
		t.Fatalf("expected 0 dirty symbols, got %d", len(symbols))
	}

	// ۲) درج نمادها با منابع مختلف
	if err := MarkDirty(ctx, db, "فولاد", "monthly_sales"); err != nil {
		t.Fatalf("mark dirty failed: %v", err)
	}
	// همان نماد با منبع دیگر (کلید اصلی دوگانه است)
	if err := MarkDirty(ctx, db, "فولاد", "financial_statement"); err != nil {
		t.Fatalf("mark dirty 2 failed: %v", err)
	}
	// نماد دوم با فاصله و حروف عربی جهت آزمون نرمال‌سازی
	if err := MarkDirty(ctx, db, "  فملي  ", "monthly_sales"); err != nil {
		t.Fatalf("mark dirty with norm failed: %v", err)
	}

	// ۳) واکشی نمادها: باید ۲ نماد یکتا و مرتب بازگردد
	symbols, err = GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("get dirty symbols failed: %v", err)
	}
	if len(symbols) != 2 {
		t.Fatalf("expected 2 distinct dirty symbols, got %d: %v", len(symbols), symbols)
	}
	if symbols[0] != "فملی" || symbols[1] != "فولاد" {
		t.Fatalf("expected ['فملی', 'فولاد'], got %v", symbols)
	}

	// ۴) پاکسازی نماد فولاد (باید هر دو سطر آن پاک شود)
	if err := ClearDirtySymbols(ctx, db, []string{"فولاد"}); err != nil {
		t.Fatalf("clear dirty symbols failed: %v", err)
	}
	symbols, err = GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("get dirty symbols after clear failed: %v", err)
	}
	if len(symbols) != 1 || symbols[0] != "فملی" {
		t.Fatalf("expected ['فملی'] left, got %v", symbols)
	}

	// ۵) پاکسازی نماد باقی‌مانده با حروف عربی/فاصله
	if err := ClearDirtySymbols(ctx, db, []string{"  فملي  "}); err != nil {
		t.Fatalf("clear dirty symbols with norm failed: %v", err)
	}
	symbols, err = GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("get dirty symbols after clear all failed: %v", err)
	}
	if len(symbols) != 0 {
		t.Fatalf("expected 0 symbols left, got %d: %v", len(symbols), symbols)
	}

	// ۶) پاکسازی بدون نماد نباید خطا بدهد
	if err := ClearDirtySymbols(ctx, db, nil); err != nil {
		t.Fatalf("clear dirty symbols with nil slice failed: %v", err)
	}
	if err := ClearDirtySymbols(ctx, db, []string{}); err != nil {
		t.Fatalf("clear dirty symbols with empty slice failed: %v", err)
	}

	// ۷) تست نماد خالی برای MarkDirty باید خطا بدهد
	if err := MarkDirty(ctx, db, "   ", "source"); err == nil {
		t.Fatalf("expected error marking empty symbol, got nil")
	}
}

func TestRecalculateDirtyFTS_Empty(t *testing.T) {
	db := setupRecalcTestDB(t)
	ctx := context.Background()

	// وقتی صفی وجود ندارد و نمادی ارسال نشده، باید ۰ برگردد بدون خطا
	count, err := RecalculateDirtyFTS(ctx, db, nil)
	if err != nil {
		t.Fatalf("recalculate dirty fts empty failed: %v", err)
	}
	if count != 0 {
		t.Fatalf("expected 0 recalculated symbols, got %d", count)
	}

	count, err = RecalculateDirtyFTS(ctx, db, []string{})
	if err != nil {
		t.Fatalf("recalculate dirty fts empty slice failed: %v", err)
	}
	if count != 0 {
		t.Fatalf("expected 0 recalculated symbols, got %d", count)
	}
}

func TestRecalculateDirtyFTS_Pipeline(t *testing.T) {
	db := setupRecalcTestDB(t)
	ctx := context.Background()

	// درج داده‌های پایه ابزار
	_, err := db.Exec(`
		INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name, updated_at, paper_type, total_shares)
		VALUES ('IRO1FOLD0001', 'فولاد', 'فولاد مبارکه', 'فلزات اساسی', '2026-11-01 12:00:00', 1, 100000000000);
	`)
	if err != nil {
		t.Fatalf("insert instrument failed: %v", err)
	}

	// درج سطر تابلو و ارزش بازار رسمی
	_, err = db.Exec(`
		INSERT INTO market_watch (ins_code, d_even, market_cap, market_cap_src)
		VALUES ('IRO1FOLD0001', 20261101, 500000000000000, 'tse_board');
	`)
	if err != nil {
		t.Fatalf("insert market_watch failed: %v", err)
	}

	// درج صورت‌های مالی سالانه ۱۲ ماهه
	_, err = db.Exec(`
		INSERT INTO financial_statements (
			tracing_no, symbol, company_name, title, report_kind,
			period_months, period_end, publish_date, revenue, gross_profit,
			operating_profit, net_profit, total_assets, total_liabilities,
			total_equity, capital, retained_earnings, basic_eps, is_audited, is_consolidated, fiscal_year, unit_norm
		) VALUES (
			1001, 'فولاد', 'فولاد مبارکه اصفهان', 'صورت‌های مالی سالانه ۱۲ ماهه', 'annual',
			12, '1402/12/29', '1403/04/10 10:00:00', 200000.0, 70000.0,
			60000.0, 50000.0, 300000.0, 100000.0,
			200000.0, 100000.0, 80000.0, 500.0, 1, 0, '1402', 'mrl'
		);
	`)
	if err != nil {
		t.Fatalf("insert financial_statements failed: %v", err)
	}

	// درج گزارش فروش ماهانه با رشد فروش نسبت به سال قبل
	_, err = db.Exec(`
		INSERT INTO monthly_sales (
			tracing_no, symbol, year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, period_end, title
		) VALUES (
			2001, 'فولاد', 1403, 6, 25000.0, 120000.0, 80000.0, '1403/06/31', 'گزارش فعالیت ماهانه شهریور ۱۴۰۳'
		);
	`)
	if err != nil {
		t.Fatalf("insert monthly_sales failed: %v", err)
	}

	// ۱) نشانه‌گذاری نماد به عنوان dirty
	if err := MarkDirty(ctx, db, "فولاد", "monthly_sales"); err != nil {
		t.Fatalf("mark dirty failed: %v", err)
	}

	dirtySyms, err := GetDirtySymbols(ctx, db)
	if err != nil || len(dirtySyms) != 1 || dirtySyms[0] != "فولاد" {
		t.Fatalf("expected ['فولاد'] in dirty, got %v (err=%v)", dirtySyms, err)
	}

	// ۲) اجرای خط لوله بازمحاسبه
	count, err := RecalculateDirtyFTS(ctx, db, nil)
	if err != nil {
		t.Fatalf("recalculate dirty fts failed: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 recalculated symbol, got %d", count)
	}

	// ۳) بررسی پاک شدن نماد از pipeline_dirty
	dirtySymsAfter, err := GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("get dirty symbols after recalc failed: %v", err)
	}
	if len(dirtySymsAfter) != 0 {
		t.Fatalf("expected 0 dirty symbols after recalc, got %v", dirtySymsAfter)
	}

	// ۴) بررسی جدول fts_results
	var sym, verdict, computedAt, cfgHash string
	var score, excluded int
	var f01Growth, f03Margin, grossMargin, revGrowth sql.NullFloat64
	var f01Pass, f03Pass, i1aPass sql.NullInt64

	row := db.QueryRowContext(ctx, `
		SELECT symbol, score, verdict, excluded, computed_at, cfg_hash,
		       f01_growth_pct, f01_pass, f03_margin_pct, f03_pass, i1a_pass,
		       rev_growth, gross_margin
		FROM fts_results WHERE symbol = 'فولاد'
	`)
	if err := row.Scan(&sym, &score, &verdict, &excluded, &computedAt, &cfgHash,
		&f01Growth, &f01Pass, &f03Margin, &f03Pass, &i1aPass, &revGrowth, &grossMargin); err != nil {
		t.Fatalf("scan fts_results failed: %v", err)
	}

	if sym != "فولاد" {
		t.Errorf("expected symbol 'فولاد', got %q", sym)
	}
	if verdict == "" {
		t.Errorf("expected non-empty verdict, got %q", verdict)
	}
	if computedAt == "" {
		t.Errorf("expected non-empty computed_at, got %q", computedAt)
	}
	if cfgHash != "{}" {
		t.Errorf("expected cfg_hash '{}', got %q", cfgHash)
	}
	if !f01Growth.Valid || f01Growth.Float64 <= 0 {
		t.Errorf("expected positive f01_growth_pct, got %v", f01Growth)
	}
	if !f03Margin.Valid || f03Margin.Float64 <= 0 {
		t.Errorf("expected positive f03_margin_pct, got %v", f03Margin)
	}
	if !i1aPass.Valid || i1aPass.Int64 != 1 {
		t.Errorf("expected i1a_pass=1, got %v", i1aPass)
	}
	if !f01Pass.Valid {
		t.Errorf("expected valid f01_pass, got %v", f01Pass)
	}
	if !f03Pass.Valid || f03Pass.Int64 != 1 {
		t.Errorf("expected f03_pass=1, got %v", f03Pass)
	}
	if score < 1 {
		t.Errorf("expected positive score, got %d", score)
	}
}

func TestRecalculateDirtyFTS_ExplicitSymbols(t *testing.T) {
	db := setupRecalcTestDB(t)
	ctx := context.Background()

	// درج داده‌های اولیه ابزار
	_, err := db.Exec(`
		INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name, updated_at, paper_type, total_shares)
		VALUES ('IRO1FOLD0001', 'فولاد', 'فولاد مبارکه', 'فلزات اساسی', '2026-11-01 12:00:00', 1, 100000000000);
	`)
	if err != nil {
		t.Fatalf("insert instrument failed: %v", err)
	}

	// علامت‌گذاری نماد دیگر در dirty
	if err := MarkDirty(ctx, db, "خساپا", "monthly_sales"); err != nil {
		t.Fatalf("mark dirty khodro failed: %v", err)
	}

	// اجرای مستقیم فقط برای 'فولاد' با لیست صریح
	count, err := RecalculateDirtyFTS(ctx, db, []string{"فولاد"})
	if err != nil {
		t.Fatalf("recalculate dirty fts with explicit symbol failed: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 recalculated symbol, got %d", count)
	}

	// خساپا باید همچنان در dirty بماند چون پردازش نشد
	dirtySyms, err := GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("get dirty symbols failed: %v", err)
	}
	if len(dirtySyms) != 1 || dirtySyms[0] != "خساپا" {
		t.Fatalf("expected ['خساپا'] to remain dirty, got %v", dirtySyms)
	}

	// فولاد باید در fts_results ذخیره شده باشد
	var storedSym string
	err = db.QueryRowContext(ctx, "SELECT symbol FROM fts_results WHERE symbol = 'فولاد'").Scan(&storedSym)
	if err != nil {
		t.Fatalf("query fts_results for explicit symbol failed: %v", err)
	}
	if storedSym != "فولاد" {
		t.Errorf("expected symbol 'فولاد', got %q", storedSym)
	}
}

func TestRecalculateAllUniverseFTS(t *testing.T) {
	db := setupRecalcTestDB(t)
	ctx := context.Background()

	// درج داده‌های نمادهای نمونه
	_, err := db.Exec(`
		INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name, updated_at, paper_type, total_shares)
		VALUES ('IRO1FOLD0001', 'فولاد', 'فولاد مبارکه', 'فلزات اساسی', '2026-11-01 12:00:00', 1, 100000000000);
		INSERT INTO instruments (ins_code, l_val18, l_val30, sector_name, updated_at, paper_type, total_shares)
		VALUES ('IRO1MSMS0001', 'فملی', 'ملی مس', 'فلزات اساسی', '2026-11-01 12:00:00', 1, 100000000000);

		INSERT INTO financial_statements (tracing_no, symbol, period_end, revenue, period_months, basic_eps)
		VALUES (1001, 'فولاد', '1403/06/31', 1000000000, 6, 120);

		INSERT INTO monthly_sales (tracing_no, symbol, period_end, year, month, monthly_revenue)
		VALUES (2001, 'فملی', '1403/05/31', 1403, 5, 200000000);
	`)
	if err != nil {
		t.Fatalf("setup universe tables failed: %v", err)
	}

	count, err := RecalculateAllUniverseFTS(ctx, db)
	if err != nil {
		t.Fatalf("RecalculateAllUniverseFTS failed: %v", err)
	}
	if count != 2 {
		t.Fatalf("expected 2 recalculated symbols, got %d", count)
	}

	// بررسی درج هر دو نماد در fts_results
	var c int
	if err := db.QueryRowContext(ctx, "SELECT count(*) FROM fts_results WHERE symbol IN ('فولاد', 'فملی')").Scan(&c); err != nil {
		t.Fatalf("query fts_results count failed: %v", err)
	}
	if c != 2 {
		t.Errorf("fts_results count = %d, want 2", c)
	}

	// pipeline_dirty باید پاک شده باشد
	dirty, err := GetDirtySymbols(ctx, db)
	if err != nil {
		t.Fatalf("GetDirtySymbols failed: %v", err)
	}
	if len(dirty) != 0 {
		t.Errorf("expected 0 dirty symbols, got %v", dirty)
	}
}

