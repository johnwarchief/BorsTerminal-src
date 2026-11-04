package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestOrderbookWatchSubscribes(t *testing.T) {
	orderbookWatchMu.Lock()
	orderbookWatched = map[string]time.Time{}
	orderbookWatchMu.Unlock()

	req := httptest.NewRequest(http.MethodPost, "/api/orderbook/watch",
		strings.NewReader(`{"ins_code":"46348559193224090"}`))
	rec := httptest.NewRecorder()
	orderbookWatchHandler(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("code=%d body=%s", rec.Code, rec.Body)
	}
	var out struct {
		Status     string   `json:"status"`
		Subscribed []string `json:"subscribed"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Status != "success" || len(out.Subscribed) != 1 || out.Subscribed[0] != "46348559193224090" {
		t.Fatalf("out=%+v", out)
	}
}

func TestOrderbookWatchPrunesStale(t *testing.T) {
	orderbookWatchMu.Lock()
	orderbookWatched = map[string]time.Time{
		"stale": time.Now().Add(-orderbookSubTTL - time.Minute),
	}
	orderbookWatchMu.Unlock()

	req := httptest.NewRequest(http.MethodPost, "/api/orderbook/watch",
		strings.NewReader(`{"ins_code":"fresh"}`))
	rec := httptest.NewRecorder()
	orderbookWatchHandler(rec, req)
	var out struct {
		Subscribed []string `json:"subscribed"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if len(out.Subscribed) != 1 || out.Subscribed[0] != "fresh" {
		t.Fatalf("stale subscription survived: %+v", out)
	}
}

func TestOrderbookWatchRejectsEmpty(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/api/orderbook/watch", strings.NewReader(`{}`))
	rec := httptest.NewRecorder()
	orderbookWatchHandler(rec, req)
	var out map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out["status"] != "error" {
		t.Fatalf("out=%v", out)
	}
}
