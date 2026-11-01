package httpapi

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"borsterminal/backend/internal/config"
)

type fakeSync struct {
	mu     sync.Mutex
	called []string
}

func (f *fakeSync) hit(name string, w http.ResponseWriter) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.called = append(f.called, name)
	w.WriteHeader(http.StatusOK)
}

func (f *fakeSync) SyncStatus(w http.ResponseWriter, _ *http.Request)          { f.hit("sync-status", w) }
func (f *fakeSync) CodalDBStatus(w http.ResponseWriter, _ *http.Request)       { f.hit("codal-db-status", w) }
func (f *fakeSync) Diagnose(w http.ResponseWriter, _ *http.Request)            { f.hit("diagnose", w) }
func (f *fakeSync) SyncMarket(w http.ResponseWriter, _ *http.Request)          { f.hit("sync-market", w) }
func (f *fakeSync) SyncCodal(w http.ResponseWriter, _ *http.Request)           { f.hit("sync-codal", w) }
func (f *fakeSync) SyncCodalFTSRefresh(w http.ResponseWriter, _ *http.Request) { f.hit("sync-fts-refresh", w) }
func (f *fakeSync) SyncCodalDBDownload(w http.ResponseWriter, _ *http.Request) { f.hit("sync-db-download", w) }
func (f *fakeSync) CodalControl(w http.ResponseWriter, _ *http.Request)        { f.hit("codal-control", w) }

func newSyncSrv(t *testing.T, sy Sync) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(),
		ReadOnly: true, NoLoops: true}, nil, nil, nil, nil, nil, nil, nil, sy)
}

func TestSyncRoutesReachHandlers(t *testing.T) {
	fakeSy := &fakeSync{}
	srv := newSyncSrv(t, fakeSy)

	cases := []struct {
		method string
		path   string
		want   string
		body   string
	}{
		{"GET", "/api/sync/status", "sync-status", ""},
		{"GET", "/api/sync/codal/db-status", "codal-db-status", ""},
		{"GET", "/api/sync/diagnose", "diagnose", ""},
		{"POST", "/api/sync/market", "sync-market", ""},
		{"POST", "/api/sync/codal", "sync-codal", ""},
		{"POST", "/api/sync/codal/fts-refresh", "sync-fts-refresh", ""},
		{"POST", "/api/sync/codal/db-download", "sync-db-download", ""},
		{"POST", "/api/codal/control", "codal-control", `{"cmd":"pause"}`},
	}

	for _, c := range cases {
		rec := httptest.NewRecorder()
		var req *http.Request
		if c.body != "" {
			req = httptest.NewRequest(c.method, c.path, bytes.NewBufferString(c.body))
		} else {
			req = httptest.NewRequest(c.method, c.path, nil)
		}
		srv.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s %s failed: code=%d", c.method, c.path, rec.Code)
		}
	}

	if len(fakeSy.called) != len(cases) {
		t.Fatalf("expected %d calls, got %d: %v", len(cases), len(fakeSy.called), fakeSy.called)
	}
}
