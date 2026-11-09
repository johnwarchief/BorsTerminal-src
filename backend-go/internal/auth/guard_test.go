package auth

import (
	"io"
	"net"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

const testToken = "0123456789abcdef0123456789abcdef"

func newTestServer(t *testing.T) (*httptest.Server, string) {
	t.Helper()
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	ts := httptest.NewUnstartedServer(next)
	port := ts.Listener.Addr().(*net.TCPAddr).Port
	hosts := LoopbackHosts(port)
	guard := NewGuard(GuardConfig{
		Token:          testToken,
		AllowedHosts:   hosts,
		AllowedOrigins: OriginsFor(hosts),
	})
	ts.Config.Handler = guard.Wrap(next)
	ts.Start()
	t.Cleanup(ts.Close)
	return ts, hosts[0]
}

func do(t *testing.T, client *http.Client, method, url string, headers map[string]string) *http.Response {
	t.Helper()
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	return resp
}

func TestAPIRequiresToken(t *testing.T) {
	ts, _ := newTestServer(t)
	resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/market", nil)
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("no token status = %d", resp.StatusCode)
	}
	if resp.Header.Get("WWW-Authenticate") == "" {
		t.Fatal("missing WWW-Authenticate")
	}
	resp = do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/market",
		map[string]string{TokenHeader: "wrong-token"})
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("wrong token status = %d", resp.StatusCode)
	}
}

func TestBearerTokenAllowsGetAndWrite(t *testing.T) {
	ts, _ := newTestServer(t)
	authHeader := map[string]string{"Authorization": "Bearer " + testToken}
	if resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/oc/data", authHeader); resp.StatusCode != http.StatusOK {
		t.Fatalf("get status = %d", resp.StatusCode)
	}
	if resp := do(t, http.DefaultClient, http.MethodPost, ts.URL+"/api/oc/data/reload", authHeader); resp.StatusCode != http.StatusOK {
		t.Fatalf("post status = %d", resp.StatusCode)
	}
}

func TestOriginIsStrict(t *testing.T) {
	ts, host := newTestServer(t)
	headers := map[string]string{"Authorization": "Bearer " + testToken}

	for _, origin := range []string{"null", "http://evil.example", "https://127.0.0.1.evil.example"} {
		h := map[string]string{"Authorization": "Bearer " + testToken, "Origin": origin}
		if resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/oc/data", h); resp.StatusCode != http.StatusForbidden {
			t.Fatalf("origin %q status = %d, want 403", origin, resp.StatusCode)
		}
	}
	h := map[string]string{"Authorization": "Bearer " + testToken, "Origin": "http://" + host}
	if resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/oc/data", h); resp.StatusCode != http.StatusOK {
		t.Fatalf("allowed origin status = %d", resp.StatusCode)
	}
	if resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/oc/data", headers); resp.StatusCode != http.StatusOK {
		t.Fatalf("no origin status = %d", resp.StatusCode)
	}
}

func TestHostIsStrict(t *testing.T) {
	ts, _ := newTestServer(t)
	req, err := http.NewRequest(http.MethodGet, ts.URL+"/api/oc/data", nil)
	if err != nil {
		t.Fatal(err)
	}
	req.Host = "evil.example"
	req.Header.Set("Authorization", "Bearer "+testToken)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("foreign host status = %d", resp.StatusCode)
	}
}

func TestCookieSessionAndCSRF(t *testing.T) {
	ts, host := newTestServer(t)
	jar, err := cookiejar.New(nil)
	if err != nil {
		t.Fatal(err)
	}
	client := &http.Client{Jar: jar}

	resp := do(t, client, http.MethodGet, ts.URL+"/", nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("index status = %d", resp.StatusCode)
	}
	rawSetCookie := resp.Header.Get("Set-Cookie")
	if rawSetCookie == "" {
		t.Fatal("index did not set a session cookie")
	}
	lowerSetCookie := strings.ToLower(rawSetCookie)
	if !strings.Contains(lowerSetCookie, "httponly") {
		t.Fatalf("Set-Cookie is not HttpOnly: %s", rawSetCookie)
	}
	if !strings.Contains(lowerSetCookie, "samesite=strict") {
		t.Fatalf("Set-Cookie is not SameSite=Strict: %s", rawSetCookie)
	}
	if !strings.Contains(lowerSetCookie, "path=/") {
		t.Fatalf("Set-Cookie path is not /: %s", rawSetCookie)
	}
	var session *http.Cookie
	for _, c := range jar.Cookies(mustURL(t, ts.URL)) {
		if c.Name == CookieName {
			session = c
		}
	}
	if session == nil {
		t.Fatal("session cookie not stored by the jar")
	}

	// Same-site requests (no Origin or the allowed Origin) may read.
	if resp := do(t, client, http.MethodGet, ts.URL+"/api/oc/data", nil); resp.StatusCode != http.StatusOK {
		t.Fatalf("cookie get status = %d", resp.StatusCode)
	}
	// Cookie-authenticated writes need the CSRF header.
	if resp := do(t, client, http.MethodPost, ts.URL+"/api/oc/data/reload", nil); resp.StatusCode != http.StatusForbidden {
		t.Fatalf("cookie post without csrf status = %d", resp.StatusCode)
	}
	if resp := do(t, client, http.MethodPost, ts.URL+"/api/oc/data/reload",
		map[string]string{CSRFHeader: "1", "Origin": "http://" + host}); resp.StatusCode != http.StatusOK {
		t.Fatalf("cookie post with csrf status = %d", resp.StatusCode)
	}
}

func TestHealthzAndCORS(t *testing.T) {
	ts, _ := newTestServer(t)
	if resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/healthz", nil); resp.StatusCode != http.StatusOK {
		t.Fatalf("healthz status = %d", resp.StatusCode)
	}
	resp := do(t, http.DefaultClient, http.MethodOptions, ts.URL+"/api/oc/data", nil)
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("preflight status = %d", resp.StatusCode)
	}
	if v := resp.Header.Get("Access-Control-Allow-Origin"); v != "" {
		t.Fatalf("CORS header leaked: %q", v)
	}
	if resp := do(t, http.DefaultClient, http.MethodPost, ts.URL+"/index.html", nil); resp.StatusCode != http.StatusForbidden {
		t.Fatalf("static post status = %d", resp.StatusCode)
	}
}

func mustURL(t *testing.T, raw string) *url.URL {
	t.Helper()
	u, err := url.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	return u
}

func TestTokenNeverAppearsInResponses(t *testing.T) {
	ts, _ := newTestServer(t)
	resp := do(t, http.DefaultClient, http.MethodGet, ts.URL+"/api/market", nil)
	if strings.Contains(resp.Header.Get("WWW-Authenticate"), testToken) {
		t.Fatal("token leaked in WWW-Authenticate")
	}
}
