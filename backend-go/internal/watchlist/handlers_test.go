package watchlist

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWatchlistHandlers(t *testing.T) {
	db, dir := newTestDB(t)
	store, err := NewStore(db, dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	h := NewHandler(store)
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/watchlist", h.Get)
	mux.HandleFunc("POST /api/watchlist", h.Post)
	mux.HandleFunc("DELETE /api/watchlist/{symbol}", h.Delete)

	// ۱. GET اولیه -> count=0, data=[]
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/watchlist", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var getResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &getResp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if getResp["status"] != "success" || getResp["count"].(float64) != 0 {
		t.Errorf("unexpected getResp: %+v", getResp)
	}

	// ۲. POST بدنه خالی -> خطا
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/watchlist", strings.NewReader(""))
	mux.ServeHTTP(rec, req)
	var errResp map[string]any
	json.Unmarshal(rec.Body.Bytes(), &errResp)
	if errResp["status"] != "error" || !strings.Contains(errResp["message"].(string), "بدنهٔ درخواست خالی است") {
		t.Errorf("unexpected empty body response: %+v", errResp)
	}

	// ۳. POST نماد رمپنا
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/watchlist", strings.NewReader(`{"symbol":"رمپنا","name":"مپنا","note":"اولین نوت"}`))
	mux.ServeHTTP(rec, req)
	var postResp map[string]any
	json.Unmarshal(rec.Body.Bytes(), &postResp)
	if postResp["status"] != "success" || postResp["count"].(float64) != 1 {
		t.Errorf("unexpected post response: %+v", postResp)
	}
	if postResp["existed"] != false {
		t.Errorf("expected existed=false")
	}

	// ۴. DELETE رمپنا
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("DELETE", "/api/watchlist/رمپنا", nil)
	mux.ServeHTTP(rec, req)
	var delResp map[string]any
	json.Unmarshal(rec.Body.Bytes(), &delResp)
	if delResp["status"] != "success" || delResp["deleted"].(float64) != 1 {
		t.Errorf("unexpected delete response: %+v", delResp)
	}
}
