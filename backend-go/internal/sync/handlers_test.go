package sync

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSyncHandlers(t *testing.T) {
	tmp := t.TempDir()
	h := NewHandler(tmp)

	// 1. GET /api/sync/status
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/sync/status", nil)
	h.SyncStatus(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncStatus code = %d", rec.Code)
	}

	// 2. GET /api/sync/codal/db-status
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/sync/codal/db-status", nil)
	h.CodalDBStatus(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("CodalDBStatus code = %d", rec.Code)
	}

	// 3. GET /api/sync/diagnose
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/sync/diagnose", nil)
	h.Diagnose(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("Diagnose code = %d", rec.Code)
	}

	// 4. POST /api/sync/market
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/market", nil)
	h.SyncMarket(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncMarket code = %d", rec.Code)
	}

	// 5. POST /api/sync/codal
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal?mode=optimized", nil)
	h.SyncCodal(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncCodal code = %d", rec.Code)
	}
	var res map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["mode"] != "optimized" {
		t.Errorf("expected mode=optimized, got %v", res["mode"])
	}

	// 6. POST /api/sync/codal/fts-refresh
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal/fts-refresh?mode=full", nil)
	h.SyncCodalFTSRefresh(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncCodalFTSRefresh code = %d", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["mode"] != "full" {
		t.Errorf("expected mode=full, got %v", res["mode"])
	}

	// 7. POST /api/sync/codal/db-download
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal/db-download", nil)
	h.SyncCodalDBDownload(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncCodalDBDownload code = %d", rec.Code)
	}

	// 8. POST /api/codal/control (invalid body)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString("not-json"))
	h.CodalControl(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("CodalControl invalid json code = %d", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "error" {
		t.Errorf("expected status=error, got %v", res["status"])
	}

	// 9. POST /api/codal/control (unknown cmd)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString(`{"cmd":"invalid"}`))
	h.CodalControl(rec, req)
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "error" {
		t.Errorf("expected status=error for unknown cmd, got %v", res["status"])
	}

	// 10. POST /api/codal/control (valid pause)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString(`{"cmd":"pause"}`))
	h.CodalControl(rec, req)
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "success" || res["cmd"] != "pause" {
		t.Errorf("expected status=success cmd=pause, got %v", res)
	}
}
