package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sort"
	"strings"
	"testing"

	"borsterminal/backend/internal/config"
)

func newServer(t *testing.T) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(), ReadOnly: true, NoLoops: true}, nil, nil)
}

func serve(t *testing.T, method, target string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest(method, target, nil))
	return rec
}

func TestUnknownAPIPathIsFastAPINotFound(t *testing.T) {
	rec := serve(t, "GET", "/api/does-not-exist")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d", rec.Code)
	}
	if strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestNonAPIPathIsFastAPINotFound(t *testing.T) {
	for _, target := range []string{"/", "/index.html", "/healthz/x"} {
		rec := serve(t, "GET", target)
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s: status = %d", target, rec.Code)
		}
		if strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
			t.Fatalf("%s: body = %s", target, rec.Body.String())
		}
	}
}

func TestKnownButUnportedIs501(t *testing.T) {
	rec := serve(t, "GET", "/api/fts/config")
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "error" || body["code"] != "NOT_PORTED" || body["route"] != "GET /api/fts/config" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

// TestMarketRoutesAreNotPortedWhenServiceMissing قفلِ قراردادِ پیشین است: بی
// سرویسِ تابلو (nil)، سه مسیرِ پورت‌شده هنوز 501ِ NOT_PORTED می‌دهند، نه 404.
func TestMarketRoutesAreNotPortedWhenServiceMissing(t *testing.T) {
	for _, target := range []string{"/api/market", "/api/market/delta?since=0", "/api/market/sync-state"} {
		rec := serve(t, "GET", target)
		if rec.Code != http.StatusNotImplemented {
			t.Fatalf("%s: status = %d", target, rec.Code)
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		path, _, _ := strings.Cut(target, "?")
		if body["code"] != "NOT_PORTED" || body["route"] != "GET "+path {
			t.Fatalf("%s: body = %s", target, rec.Body.String())
		}
	}
}

// TestTemplateRouteIs501WithRequestPath قفلِ finding ۱ است: مسیرِ واقعیِ
// پارامتردار باید 501 بدهد و route همان مسیرِ درخواست باشد، نه قالبِ routes.json.
func TestTemplateRouteIs501WithRequestPath(t *testing.T) {
	cases := []struct {
		name   string
		method string
		target string
		route  string
	}{
		{"Persian symbol escaped", "GET", "/api/chart/" + url.PathEscape("فولاد"), "GET /api/chart/فولاد"},
		{"Persian symbol raw", "GET", "/api/chart/فولاد", "GET /api/chart/فولاد"},
		{"Numeric id", "GET", "/api/execution/queue/42", "GET /api/execution/queue/42"},
		{"Param then literal", "GET", "/api/chart/" + url.PathEscape("فولاد") + "/key-levels", "GET /api/chart/فولاد/key-levels"},
		{"Param on DELETE", "DELETE", "/api/watchlist/" + url.PathEscape("فولاد"), "DELETE /api/watchlist/فولاد"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rec := serve(t, tc.method, tc.target)
			if rec.Code != http.StatusNotImplemented {
				t.Fatalf("status = %d", rec.Code)
			}
			var body map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
				t.Fatal(err)
			}
			if body["code"] != "NOT_PORTED" {
				t.Fatalf("code = %v, body = %s", body["code"], rec.Body.String())
			}
			if body["route"] != tc.route {
				t.Fatalf("route = %v, want %q", body["route"], tc.route)
			}
		})
	}
}

// TestEveryParameterizedRouteIs501 تمامِ مسیرهایِ {param} دارِ فهرست را با
// یک مقدارِ واقعی صدا می‌زند؛ هیچ‌کدام نباید 404 بگیرد.
func TestEveryParameterizedRouteIs501(t *testing.T) {
	srv := newServer(t)
	total := 0
	for _, route := range Routes() {
		if !strings.Contains(route, "{") {
			continue
		}
		total++
		method, path, ok := strings.Cut(route, " ")
		if !ok {
			t.Fatalf("malformed route %q", route)
		}
		concrete := strings.NewReplacer(
			"{symbol}", url.PathEscape("فولاد"),
			"{execution_id}", "42",
		).Replace(path)
		rec := httptest.NewRecorder()
		srv.ServeHTTP(rec, httptest.NewRequest(method, concrete, nil))
		if rec.Code != http.StatusNotImplemented {
			t.Errorf("%s %s: status = %d, want 501", method, concrete, rec.Code)
			continue
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: %v", route, err)
		}
		want := method + " " + strings.NewReplacer("{symbol}", "فولاد", "{execution_id}", "42").Replace(path)
		if body["route"] != want {
			t.Errorf("route = %v, want %q", body["route"], want)
		}
	}
	if total != 16 {
		t.Fatalf("parameterized routes = %d, want 16", total)
	}
}

// TestUnmatchedAPIPathIs404 مرزِ تطبیق را نگه می‌دارد: پارامترِ گم‌شده،
// قطعهٔ اضافه و متدِ نادرست در فهرست هنوز 404 می‌گیرند.
func TestUnmatchedAPIPathIs404(t *testing.T) {
	cases := []struct {
		method string
		target string
	}{
		{"GET", "/api/chart"},
		{"GET", "/api/chart/" + url.PathEscape("فولاد") + "/extra"},
		{"GET", "/api/execution/queue/42/extra"},
		{"POST", "/api/chart/" + url.PathEscape("فولاد")},
	}
	for _, tc := range cases {
		rec := serve(t, tc.method, tc.target)
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s %s: status = %d", tc.method, tc.target, rec.Code)
		}
		if strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
			t.Fatalf("%s %s: body = %s", tc.method, tc.target, rec.Body.String())
		}
	}
}

func TestHealthzShape(t *testing.T) {
	rec := serve(t, "GET", "/healthz")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"status", "version", "market_mode", "data_dir", "loops", "uptime_s", "go", "rss_mb"} {
		if _, ok := body[key]; !ok {
			t.Fatalf("missing %q in %s", key, rec.Body.String())
		}
	}
	if body["status"] != "ok" {
		t.Fatalf("status = %v, body = %s", body["status"], rec.Body.String())
	}
	if body["market_mode"] != "read-only" || body["loops"] != "off" {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if goVer, ok := body["go"].(string); !ok || !strings.HasPrefix(goVer, "go") {
		t.Fatalf("go = %v", body["go"])
	}
	if rss, ok := body["rss_mb"].(float64); !ok || rss <= 0 {
		t.Fatalf("rss_mb = %v", body["rss_mb"])
	}
	if dir, ok := body["data_dir"].(string); !ok || dir == "" {
		t.Fatalf("data_dir = %v", body["data_dir"])
	}
	if up, ok := body["uptime_s"].(float64); !ok || up < 0 {
		t.Fatalf("uptime_s = %v", body["uptime_s"])
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

func TestRoutesInventoryIsExactAndSorted(t *testing.T) {
	routes := Routes()
	if len(routes) != 103 {
		t.Fatalf("routes = %d, want 103 (tools/parity/gen_routes.py must print routes: 103)", len(routes))
	}
	if !sort.StringsAreSorted(routes) {
		for i := 1; i < len(routes); i++ {
			if routes[i] < routes[i-1] {
				t.Fatalf("routes not sorted at %d: %q before %q", i, routes[i-1], routes[i])
			}
		}
	}
}

func TestHealthzMethodMismatchIs405WithAllow(t *testing.T) {
	rec := serve(t, "DELETE", "/healthz")
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d", rec.Code)
	}
	if allow := rec.Header().Get("Allow"); allow != "GET" {
		t.Fatalf("Allow = %q", allow)
	}
}

// TestNoStoreHeaders رویِ سیم همان قراردادِ no_cache_middlewareِ app.py را
// می‌سنجد: پاسخ‌هایِ API و healthz «no-cache, no-store, must-revalidate» و
// «Pragma: no-cache» می‌گیرند، ولی داراییِ هش‌دار دست‌نخورده می‌ماند.
func TestNoStoreHeaders(t *testing.T) {
	for _, target := range []string{"/api/does-not-exist", "/api/fts/config", "/healthz"} {
		rec := serve(t, "GET", target)
		if got := rec.Header().Get("Cache-Control"); got != "no-cache, no-store, must-revalidate" {
			t.Fatalf("%s: Cache-Control = %q", target, got)
		}
		if got := rec.Header().Get("Pragma"); got != "no-cache" {
			t.Fatalf("%s: Pragma = %q", target, got)
		}
	}
	rec := serve(t, "GET", "/assets/app.js")
	if got := rec.Header().Get("Cache-Control"); got != "" {
		t.Fatalf("assets: Cache-Control = %q, want unset", got)
	}
}

// TestNoStoreOverridesRouteValue همان بازنویسیِ پس‌از‌هندلرِ Starlette را ثابت
// می‌کند: هندلری که خودش max-age گذاشته باشد، رویِ سیم no-store می‌بیند.
func TestNoStoreOverridesRouteValue(t *testing.T) {
	srv := noCache(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "max-age=15")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	}))
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, httptest.NewRequest("GET", "/api/market", nil))
	if got := rec.Header().Get("Cache-Control"); got != "no-cache, no-store, must-revalidate" {
		t.Fatalf("Cache-Control = %q", got)
	}
}
