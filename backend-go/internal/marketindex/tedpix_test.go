package marketindex

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func sampleIndexB2Response() rawResponse {
	return rawResponse{
		IndexB2: []rawIndexItem{
			{
				InsCode:          "32097828799138957",
				DEven:            20261028,
				XNivInuClMresIbs: 2100000.5,
				XNivInuPhMresIbs: 2110000.0,
				XNivInuPbMresIbs: 2095000.0,
			},
			{
				InsCode:          "32097828799138957",
				DEven:            20261029,
				XNivInuClMresIbs: 2125000.0,
				XNivInuPhMresIbs: 2130000.0,
				XNivInuPbMresIbs: 2110000.0,
			},
			{
				InsCode:          "32097828799138957",
				DEven:            20261101,
				XNivInuClMresIbs: 2150000.0,
				XNivInuPhMresIbs: 2160000.0,
				XNivInuPbMresIbs: 2140000.0,
			},
		},
	}
}

func TestBuildTedpixPayloadSuccess(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(sampleIndexB2Response())
	}))
	defer ts.Close()

	svc := NewService(t.TempDir(), ts.Client())
	svc.SetBaseURL(ts.URL)

	ctx := context.Background()
	payload, code, err := svc.BuildTedpixPayload(ctx, TedpixInsCode, 0, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d", code)
	}

	if payload["status"] != "success" {
		t.Errorf("expected status success, got %v", payload["status"])
	}
	if payload["count"] != 3 {
		t.Errorf("expected count 3, got %v", payload["count"])
	}
	if payload["unit"] != "index_point" {
		t.Errorf("expected unit index_point, got %v", payload["unit"])
	}

	candles, ok := payload["candles"].([]map[string]any)
	if !ok || len(candles) != 3 {
		t.Fatalf("invalid candles: %+v", candles)
	}

	// بررسی روز اول: time=2026-10-28, open=close (روز اول)، close=2100000.5
	if candles[0]["time"] != "2026-10-28" {
		t.Errorf("expected time 2026-10-28, got %v", candles[0]["time"])
	}
	if candles[0]["close"] != 2100000.5 {
		t.Errorf("expected close 2100000.5, got %v", candles[0]["close"])
	}

	// بررسی روز دوم: open باید برابر با close روز قبل باشد
	if candles[1]["open"] != 2100000.5 {
		t.Errorf("expected open 2100000.5 for second day, got %v", candles[1]["open"])
	}

	// تست پارامتر limit: درخواست با limit=2
	limPayload, _, err := svc.BuildTedpixPayload(ctx, TedpixInsCode, 2, false)
	if err != nil {
		t.Fatalf("unexpected error on limit: %v", err)
	}
	if limPayload["count"] != 2 {
		t.Errorf("expected limit count 2, got %v", limPayload["count"])
	}
}

func TestBuildTedpixPayloadError502(t *testing.T) {
	// سروری که کد ۵۰۰ می‌دهد
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer ts.Close()

	svc := NewService(t.TempDir(), ts.Client())
	svc.SetBaseURL(ts.URL)

	ctx := context.Background()
	_, code, err := svc.BuildTedpixPayload(ctx, TedpixInsCode, 0, false)
	if err == nil {
		t.Fatalf("expected error on 500 server, got nil")
	}
	if code != http.StatusBadGateway {
		t.Errorf("expected 502 Bad Gateway, got %d", code)
	}
}

func TestHTTPHandlerTEDPIX(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(sampleIndexB2Response())
	}))
	defer ts.Close()

	svc := NewService(t.TempDir(), ts.Client())
	svc.SetBaseURL(ts.URL)

	req := httptest.NewRequest("GET", "/api/index/tedpix?limit=1", nil)
	w := httptest.NewRecorder()
	svc.TEDPIX(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	var resp map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode json: %v", err)
	}
	if resp["count"].(float64) != 1 {
		t.Errorf("expected count 1, got %v", resp["count"])
	}
}
