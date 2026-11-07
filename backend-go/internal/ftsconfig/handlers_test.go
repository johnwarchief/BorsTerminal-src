package ftsconfig

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHandler_GetAndPost(t *testing.T) {
	db := newTestDB(t)
	store, err := NewStore(db)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	h := NewHandler(store, false)

	// 1. GET returns status: success and config object
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/fts/config", nil)
	h.Get(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var getResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &getResp); err != nil {
		t.Fatalf("unmarshal GET response: %v", err)
	}
	if getResp["status"] != "success" {
		t.Fatalf("expected status=success, got %v", getResp["status"])
	}
	cfg, ok := getResp["config"].(map[string]any)
	if !ok || cfg["growth_min"].(float64) != 40.0 {
		t.Fatalf("expected default growth_min=40, got %+v", cfg)
	}

	// 2. POST updates config and persists
	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodPost, "/api/fts/config", strings.NewReader(`{"growth_min": 65, "margin_min": 35}`))
	h.Post(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var postResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &postResp); err != nil {
		t.Fatalf("unmarshal POST response: %v", err)
	}
	if postResp["status"] != "success" || postResp["message"] != "saved" {
		t.Fatalf("expected status=success, message=saved, got %+v", postResp)
	}
	savedCfg := postResp["config"].(map[string]any)
	if savedCfg["growth_min"].(float64) != 65.0 || savedCfg["margin_min"].(float64) != 35.0 {
		t.Fatalf("unexpected saved config: %+v", savedCfg)
	}

	// 3. GET verifies persistence
	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet, "/api/fts/config", nil)
	h.Get(rec, req)
	var verifyResp map[string]any
	json.Unmarshal(rec.Body.Bytes(), &verifyResp)
	verifyCfg := verifyResp["config"].(map[string]any)
	if verifyCfg["growth_min"].(float64) != 65.0 {
		t.Fatalf("expected growth_min=65, got %v", verifyCfg["growth_min"])
	}
}

func TestHandler_ReadOnlyForbidden(t *testing.T) {
	db := newTestDB(t)
	store, _ := NewStore(db)
	h := NewHandler(store, true) // readOnly = true

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/fts/config", strings.NewReader(`{"growth_min": 65}`))
	h.Post(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected 403 Forbidden, got %d", rec.Code)
	}
	var body map[string]any
	json.Unmarshal(rec.Body.Bytes(), &body)
	if body["status"] != "error" || body["message"] != "read-only mode" {
		t.Fatalf("expected error read-only mode, got %+v", body)
	}
}
