package notifications

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestNotificationHandlers(t *testing.T) {
	db := newTestDB(t)
	initTestSchema(t, db)

	_, err := db.Exec(`INSERT INTO codal_notices(tracing_no, symbol, company_name, title, letter_code, publish_date, fetched_at)
VALUES(1001, 'رمپنا', 'مپنا', 'گزارش فعالیت ماهانه', 'ن-۱', '1404/07/30 18:00:00', '2026-10-22 10:00:00')`)
	if err != nil {
		t.Fatalf("insert notice: %v", err)
	}

	svc := NewService(db)
	t.Cleanup(func() { svc.Close() })

	h := NewHandler(svc)
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/notifications/sources", h.Sources)
	mux.HandleFunc("GET /api/notifications/feed", h.Feed)

	// ۱. GET /api/notifications/sources
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/notifications/sources", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var srcResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &srcResp); err != nil {
		t.Fatalf("unmarshal sources: %v", err)
	}
	if srcResp["status"] != "ok" {
		t.Errorf("unexpected sources status: %v", srcResp)
	}

	// ۲. GET /api/notifications/feed?symbol=رمپنا&limit=5
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/notifications/feed?symbol=رمپنا&limit=5", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var feedResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &feedResp); err != nil {
		t.Fatalf("unmarshal feed: %v", err)
	}
	if feedResp["status"] != "ok" || feedResp["count"].(float64) != 1 {
		t.Errorf("unexpected feed response: %+v", feedResp)
	}
	if feedResp["symbol"] != "رمپنا" {
		t.Errorf("expected symbol=رمپنا, got %v", feedResp["symbol"])
	}

	// ۳. Invalid limit -> 422
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/notifications/feed?limit=abc", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("expected 422 for limit=abc, got %d", rec.Code)
	}
}
