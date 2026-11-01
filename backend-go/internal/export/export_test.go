package export

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

func setupMarketDB(t *testing.T) *sql.DB {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open sqlite: %v", err)
	}

	_, err = db.Exec(`
		CREATE TABLE instruments (
			ins_code TEXT PRIMARY KEY,
			l_val18 TEXT,
			l_val30 TEXT,
			sector_name TEXT
		);
		CREATE TABLE market_watch (
			ins_code TEXT,
			p_closing REAL,
			p_last REAL,
			price_change REAL,
			q_tot_tran REAL,
			q_tot_cap REAL,
			pe REAL,
			eps REAL,
			z_tot_tran REAL
		);

		INSERT INTO instruments VALUES ('1001', 'فولاد', 'فولاد مبارکه', 'فلزات اساسی');
		INSERT INTO market_watch VALUES ('1001', 5500.0, 5600.0, 100.0, 1000000.0, 5500000000.0, 6.5, 850.0, 1500.0);
	`)
	if err != nil {
		t.Fatalf("failed to init db: %v", err)
	}

	return db
}

func TestBuildCSVAndDisposition(t *testing.T) {
	rows := [][]any{
		{"نماد", "قیمت", "حجم"},
		{"فولاد", 5500, 1000000},
	}
	meta := [][2]string{
		{"منبع", "بورس تهران"},
		{"تاریخ", "1405-08-10"},
	}

	csvBytes, disposition, filename := BuildCSV("دیده‌بان", rows, meta)

	// ۱. بررسی UTF-8 BOM
	if !bytes.HasPrefix(csvBytes, []byte("\xef\xbb\xbf")) {
		t.Errorf("expected UTF-8 BOM prefix")
	}

	// ۲. بررسی متن CSV
	strContent := string(csvBytes)
	if !strings.Contains(strContent, "فولاد") {
		t.Errorf("expected فولاد in csv content")
	}
	if !strings.Contains(strContent, "# منبع,بورس تهران") {
		t.Errorf("expected meta in csv content: %s", strContent)
	}

	// ۳. بررسی Content-Disposition
	if !strings.Contains(disposition, "attachment; filename=") {
		t.Errorf("invalid disposition: %s", disposition)
	}
	if !strings.Contains(disposition, "filename*=UTF-8''") {
		t.Errorf("expected RFC 5987 filename* in disposition: %s", disposition)
	}
	if filename == "" {
		t.Errorf("expected non-empty filename")
	}
}

func TestPostExportLimits(t *testing.T) {
	svc := NewService(nil)

	// بدنه خالی
	reqEmpty := httptest.NewRequest("POST", "/api/export", nil)
	wEmpty := httptest.NewRecorder()
	svc.Post(wEmpty, reqEmpty)
	if wEmpty.Code != http.StatusOK {
		t.Errorf("expected 200 with status error for empty body, got %d", wEmpty.Code)
	}

	// فرمت نامعتبر rows (عدد به جای لیست)
	bodyBadRows, _ := json.Marshal(map[string]any{"rows": 123})
	reqBad := httptest.NewRequest("POST", "/api/export", bytes.NewReader(bodyBadRows))
	wBad := httptest.NewRecorder()
	svc.Post(wBad, reqBad)
	if wBad.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 for invalid rows type, got %d", wBad.Code)
	}

	// بیش از 200 ستون -> 413
	rowTooWide := make([]any, 205)
	bodyTooWide, _ := json.Marshal(map[string]any{
		"rows": [][]any{rowTooWide},
	})
	reqWide := httptest.NewRequest("POST", "/api/export", bytes.NewReader(bodyTooWide))
	wWide := httptest.NewRecorder()
	svc.Post(wWide, reqWide)
	if wWide.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("expected 413 for too many columns, got %d", wWide.Code)
	}
}

func TestGetMarketExport(t *testing.T) {
	db := setupMarketDB(t)
	defer db.Close()

	svc := NewService(db)

	req := httptest.NewRequest("GET", "/api/export?view=market", nil)
	w := httptest.NewRecorder()
	svc.Get(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	contentType := w.Header().Get("Content-Type")
	if !strings.Contains(contentType, "text/csv") {
		t.Errorf("expected text/csv content type, got %s", contentType)
	}

	body := w.Body.String()
	if !strings.Contains(body, "symbol,name,sector") {
		t.Errorf("missing headers in export: %s", body)
	}
	if !strings.Contains(body, "فولاد,فولاد مبارکه,فلزات اساسی") {
		t.Errorf("missing row data in export: %s", body)
	}
}
