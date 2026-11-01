package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"borsterminal/backend/internal/config"
)

type fakeWatchlist struct {
	mu     sync.Mutex
	called []string
}

func (f *fakeWatchlist) hit(name string, w http.ResponseWriter) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.called = append(f.called, name)
	w.WriteHeader(http.StatusOK)
}

func (f *fakeWatchlist) Get(w http.ResponseWriter, _ *http.Request)    { f.hit("get", w) }
func (f *fakeWatchlist) Post(w http.ResponseWriter, _ *http.Request)   { f.hit("post", w) }
func (f *fakeWatchlist) Delete(w http.ResponseWriter, _ *http.Request) { f.hit("delete", w) }

type fakeNotifications struct {
	mu     sync.Mutex
	called []string
}

func (f *fakeNotifications) hit(name string, w http.ResponseWriter) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.called = append(f.called, name)
	w.WriteHeader(http.StatusOK)
}

func (f *fakeNotifications) Sources(w http.ResponseWriter, _ *http.Request) { f.hit("sources", w) }
func (f *fakeNotifications) Feed(w http.ResponseWriter, _ *http.Request)    { f.hit("feed", w) }

func newUserSrv(t *testing.T, wl Watchlist, nt Notifications) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(),
		ReadOnly: true, NoLoops: true}, nil, nil, nil, nil, nil, wl, nt, nil)
}

func TestWatchlistAndNotificationRoutesReachHandlers(t *testing.T) {
	fakeWl := &fakeWatchlist{}
	fakeNt := &fakeNotifications{}
	srv := newUserSrv(t, fakeWl, fakeNt)

	// ۱. GET /api/watchlist
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("GET", "/api/watchlist", nil))
	if rec.Code != http.StatusOK || len(fakeWl.called) != 1 || fakeWl.called[0] != "get" {
		t.Fatalf("GET /api/watchlist failed: code=%d called=%v", rec.Code, fakeWl.called)
	}

	// ۲. POST /api/watchlist
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("POST", "/api/watchlist", nil))
	if rec.Code != http.StatusOK || len(fakeWl.called) != 2 || fakeWl.called[1] != "post" {
		t.Fatalf("POST /api/watchlist failed: code=%d called=%v", rec.Code, fakeWl.called)
	}

	// ۳. DELETE /api/watchlist/رمپنا
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("DELETE", "/api/watchlist/رمپنا", nil))
	if rec.Code != http.StatusOK || len(fakeWl.called) != 3 || fakeWl.called[2] != "delete" {
		t.Fatalf("DELETE /api/watchlist/رمپنا failed: code=%d called=%v", rec.Code, fakeWl.called)
	}

	// ۴. GET /api/notifications/sources
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("GET", "/api/notifications/sources", nil))
	if rec.Code != http.StatusOK || len(fakeNt.called) != 1 || fakeNt.called[0] != "sources" {
		t.Fatalf("GET /api/notifications/sources failed: code=%d called=%v", rec.Code, fakeNt.called)
	}

	// ۵. GET /api/notifications/feed
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("GET", "/api/notifications/feed", nil))
	if rec.Code != http.StatusOK || len(fakeNt.called) != 2 || fakeNt.called[1] != "feed" {
		t.Fatalf("GET /api/notifications/feed failed: code=%d called=%v", rec.Code, fakeNt.called)
	}

	// ۶. GET /api/watchlist/matrix باید 501 NOT_PORTED باشد
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("GET", "/api/watchlist/matrix", nil))
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("expected 501 for matrix, got %d", rec.Code)
	}
	var notPortedResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &notPortedResp); err != nil {
		t.Fatalf("unmarshal 501 response: %v", err)
	}
	if notPortedResp["code"] != "NOT_PORTED" || notPortedResp["route"] != "GET /api/watchlist/matrix" {
		t.Errorf("unexpected notPorted response: %+v", notPortedResp)
	}
}
