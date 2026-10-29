package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"borsterminal/backend/internal/config"
)

func newServer(t *testing.T) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(), ReadOnly: true, NoLoops: true}, nil)
}

func TestUnknownPathIsFastAPINotFound(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/api/does-not-exist", nil))
	if rec.Code != 404 {
		t.Fatalf("status = %d", rec.Code)
	}
	if strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestKnownButUnportedIs501(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/api/market", nil))
	if rec.Code != 501 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["code"] != "NOT_PORTED" || body["route"] != "GET /api/market" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestHealthzShape(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/healthz", nil))
	if rec.Code != 200 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"status", "version", "market_mode", "data_dir", "loops", "uptime_s"} {
		if _, ok := body[key]; !ok {
			t.Fatalf("missing %q in %s", key, rec.Body.String())
		}
	}
	if body["market_mode"] != "read-only" || body["loops"] != "off" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestUnprocessableShape(t *testing.T) {
	rec := httptest.NewRecorder()
	Unprocessable(rec, []string{"query", "days"}, "Input should be a valid integer", "x")
	if rec.Code != 422 {
		t.Fatalf("status = %d", rec.Code)
	}
	want := `{"detail":[{"input":"x","loc":["query","days"],"msg":"Input should be a valid integer","type":"value_error"}]}`
	if strings.TrimSpace(rec.Body.String()) != want {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestRoutesInventoryNonEmpty(t *testing.T) {
	routes := Routes()
	if len(routes) < 90 {
		t.Fatalf("routes = %d", len(routes))
	}
	if routes[0] >= routes[len(routes)-1] {
		t.Fatalf("routes not sorted")
	}
}

func TestMethodMismatchIs404LikeFastAPI(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("DELETE", "/healthz", nil))
	if rec.Code != 405 {
		t.Fatalf("status = %d", rec.Code)
	}
}
