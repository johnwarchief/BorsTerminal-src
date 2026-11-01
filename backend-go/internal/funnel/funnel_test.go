package funnel

import (
	"bytes"
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
		CREATE TABLE instruments (
			ins_code TEXT PRIMARY KEY,
			l_val18 TEXT,
			l_val30 TEXT
		);
		CREATE TABLE market_watch (
			ins_code TEXT,
			p_closing REAL
		);

		INSERT INTO instruments VALUES ('1001', 'فولاد', 'فولاد مبارکه');
		INSERT INTO market_watch VALUES ('1001', 5500.0);
	`)
	if err != nil {
		t.Fatalf("failed to init db: %v", err)
	}

	return db
}

func TestRegistry(t *testing.T) {
	payload, err := RegistryPayload()
	if err != nil {
		t.Fatalf("failed to get registry payload: %v", err)
	}

	if payload["registry_version"] != "1" {
		t.Errorf("expected registry_version 1, got %v", payload["registry_version"])
	}

	filters, ok := payload["filters"].([]any)
	if !ok || len(filters) == 0 {
		t.Fatalf("expected non-empty filters in registry")
	}

	presets, ok := payload["presets"].([]any)
	if !ok || len(presets) == 0 {
		t.Fatalf("expected non-empty presets in registry")
	}
}

func TestFunnelHTTPHandlers(t *testing.T) {
	db := setupTestDB(t)
	defer db.Close()

	svc := NewService(db, t.TempDir())

	// ۱. تست GET /api/funnel/registry
	reqReg := httptest.NewRequest("GET", "/api/funnel/registry", nil)
	wReg := httptest.NewRecorder()
	svc.Registry(wReg, reqReg)

	if wReg.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wReg.Code)
	}
	var regMap map[string]any
	if err := json.Unmarshal(wReg.Body.Bytes(), &regMap); err != nil {
		t.Fatalf("failed to parse registry json: %v", err)
	}
	if regMap["registry_version"] != "1" {
		t.Errorf("expected registry_version 1, got %v", regMap["registry_version"])
	}

	// ۲. تست GET /api/funnel
	reqFunnel := httptest.NewRequest("GET", "/api/funnel?preset=trend", nil)
	wFunnel := httptest.NewRecorder()
	svc.GetFunnel(wFunnel, reqFunnel)

	if wFunnel.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wFunnel.Code)
	}
	var fnResp map[string]any
	_ = json.Unmarshal(wFunnel.Body.Bytes(), &fnResp)
	if fnResp["status"] != "success" {
		t.Errorf("expected status success, got %v", fnResp["status"])
	}

	// ۳. تست POST /api/funnel
	body, _ := json.Marshal(map[string]any{
		"preset":    "trend",
		"fund_mode": "standard",
	})
	reqPost := httptest.NewRequest("POST", "/api/funnel", bytes.NewReader(body))
	wPost := httptest.NewRecorder()
	svc.PostFunnel(wPost, reqPost)

	if wPost.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wPost.Code)
	}

	// ۴. تست GET /api/funnel/trace?symbol=فولاد
	reqTrace := httptest.NewRequest("GET", "/api/funnel/trace?symbol=فولاد", nil)
	wTrace := httptest.NewRecorder()
	svc.Trace(wTrace, reqTrace)

	if wTrace.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wTrace.Code)
	}
	var trResp map[string]any
	_ = json.Unmarshal(wTrace.Body.Bytes(), &trResp)
	if trResp["status"] != "success" {
		t.Errorf("expected status success, got %v", trResp["status"])
	}
}
