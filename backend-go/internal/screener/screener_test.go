package screener

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open sqlite: %v", err)
	}

	_, err = db.Exec(`
		CREATE TABLE price_history (
			symbol TEXT,
			date TEXT,
			open REAL,
			high REAL,
			low REAL,
			close REAL,
			volume REAL,
			last REAL
		);

		CREATE TABLE fts_results (
			symbol TEXT PRIMARY KEY,
			score INTEGER,
			verdict TEXT,
			excluded INTEGER,
			exclusion_reasons TEXT,
			f01_growth_pct REAL,
			f01_pass INTEGER,
			f02_pass INTEGER,
			f03_margin_pct REAL,
			f03_pass INTEGER,
			f04_ratio REAL,
			f04_pass INTEGER,
			f05_verdict TEXT,
			f05_pass INTEGER
		);

		CREATE TABLE instruments (
			l_val18 TEXT PRIMARY KEY,
			l_val30 TEXT,
			sector_name TEXT
		);

		CREATE TABLE market_watch (
			ins_code TEXT,
			d_even INTEGER
		);
		INSERT INTO market_watch VALUES ('A', 20261102);
		INSERT INTO market_watch VALUES ('B', 20261103);

		-- درج داده‌های تستی تاریخچه قیمت
		INSERT INTO price_history VALUES ('فولاد', '2026-10-28', 5000, 5100, 4950, 5050, 1000000, 5060);
		-- روز تکراری با حجم کمتر (باید حذف شود)
		INSERT INTO price_history VALUES ('فولاد', '2026-10-29', 5050, 5200, 5000, 5150, 500000, 5140);
		-- روز تکراری با حجم بیشتر (باید باقی بماند)
		INSERT INTO price_history VALUES ('فولاد', '2026-10-29', 5050, 5200, 5000, 5150, 2000000, 5160);
		-- کندل نامعتبر با قیمت صفر (باید حذف شود)
		INSERT INTO price_history VALUES ('فولاد', '2026-10-30', 0, 0, 0, 0, 0, 0);

		-- درج داده‌های اسکرینر
		INSERT INTO instruments VALUES ('فولاد', 'فولاد مبارکه', 'فلزات اساسی');
		INSERT INTO instruments VALUES ('فملی', 'ملی مس', 'فلزات اساسی');

		INSERT INTO fts_results VALUES ('فولاد', 5, 'تایید کامل', 0, '', 45.5, 1, 1, 28.0, 1, 1.2, 1, 'سودآور', 1);
		INSERT INTO fts_results VALUES ('فملی', 4, 'تایید نسبی', 0, '', 30.0, 1, 1, 20.0, 1, 0.8, 0, 'سودآور', 1);
	`)
	if err != nil {
		t.Fatalf("failed to init test db: %v", err)
	}

	return db
}

func TestGetHistory(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	svc := NewService(db, t.TempDir())

	ctx := context.Background()
	res, err := svc.GetHistory(ctx, "فولاد")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if res["status"] != "success" {
		t.Errorf("expected success, got %v", res["status"])
	}

	candles, ok := res["candles"].([]map[string]any)
	if !ok || len(candles) != 2 {
		t.Fatalf("expected 2 candles after deduplication and cleanup, got %d", len(candles))
	}

	if candles[0]["time"] != "2026-10-28" || candles[1]["time"] != "2026-10-29" {
		t.Errorf("unexpected dates: %v, %v", candles[0]["time"], candles[1]["time"])
	}

	volumes, ok := res["volumes"].([]map[string]any)
	if !ok || len(volumes) != 2 {
		t.Fatalf("expected 2 volumes, got %d", len(volumes))
	}
	// حجم روز دوم باید حجم بزرگتر (2000000) باشد
	if volumes[1]["value"] != 2000000.0 {
		t.Errorf("expected volume 2000000, got %v", volumes[1]["value"])
	}

	// تست نماد ناموجود
	emptyRes, err := svc.GetHistory(ctx, "ناموجود")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if emptyRes["status"] != "empty" {
		t.Errorf("expected status empty, got %v", emptyRes["status"])
	}
}

func TestGetScreener(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	svc := NewService(db, t.TempDir())
	ctx := context.Background()

	// دریافت تمام اسکرینر
	resAll, err := svc.GetScreener(ctx, "", "trend", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resAll["count"] != 2 {
		t.Errorf("expected count 2, got %v", resAll["count"])
	}

	// فیلتر تک‌نماد با symbols=فولاد
	resFiltered, err := svc.GetScreener(ctx, "فولاد", "trend", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if resFiltered["count"] != 1 {
		t.Errorf("expected count 1, got %v", resFiltered["count"])
	}
	if resFiltered["requested_symbols"] != 1 {
		t.Errorf("expected requested_symbols 1, got %v", resFiltered["requested_symbols"])
	}
}

func TestScreenerHTTPHandlers(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	svc := NewService(db, t.TempDir())

	// تست GET /api/history/فولاد
	reqHist := httptest.NewRequest("GET", "/api/history/فولاد", nil)
	wHist := httptest.NewRecorder()
	svc.History(wHist, reqHist)

	if wHist.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wHist.Code)
	}

	var histResp map[string]any
	if err := json.Unmarshal(wHist.Body.Bytes(), &histResp); err != nil {
		t.Fatalf("failed to decode json: %v", err)
	}
	if histResp["status"] != "success" {
		t.Errorf("expected success, got %v", histResp["status"])
	}

	// تست GET /api/screener?symbols=فملی
	reqScr := httptest.NewRequest("GET", "/api/screener?symbols=فملی", nil)
	wScr := httptest.NewRecorder()
	svc.Screener(wScr, reqScr)

	if wScr.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wScr.Code)
	}
}

func TestGetScreenerAsOf(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()
	svc := NewService(db, t.TempDir())
	res, err := svc.GetScreener(context.Background(), "", "trend", "")
	if err != nil {
		t.Fatal(err)
	}
	if res["as_of"] != "2026-11-03" {
		t.Fatalf("as_of=%v want 2026-11-03", res["as_of"])
	}
}
