// Package auth مرزِ محلیِ API است: Host/Origin سخت‌گیر، CORS بسته، توکنِ
// per-launch و CSRF برایِ درخواست‌هایِ نوشتاریِ کوکی‌محور.
package auth

import (
	"crypto/subtle"
	"encoding/json"
	"net"
	"net/http"
	"strconv"
	"strings"
)

const (
	CookieName  = "oc_session"
	TokenHeader = "X-OC-Token"
	CSRFHeader  = "X-OC-CSRF"
)

type GuardConfig struct {
	Token          string
	AllowedHosts   []string
	AllowedOrigins []string
}

type Guard struct {
	token   string
	hosts   map[string]struct{}
	origins map[string]struct{}
}

func NewGuard(cfg GuardConfig) *Guard {
	g := &Guard{
		token:   cfg.Token,
		hosts:   make(map[string]struct{}, len(cfg.AllowedHosts)),
		origins: make(map[string]struct{}, len(cfg.AllowedOrigins)+2),
	}
	for _, h := range cfg.AllowedHosts {
		g.hosts[strings.ToLower(strings.TrimSpace(h))] = struct{}{}
	}
	for _, o := range cfg.AllowedOrigins {
		g.origins[strings.ToLower(strings.TrimSpace(o))] = struct{}{}
	}
	// Originهایِ خودِ Tauri (ویندوز: http://tauri.localhost، بقیه: tauri://localhost)
	// فقط برایِ همان فراخوانِ بومیِ محلی مجازند؛ remote capability باز نمی‌شود.
	g.origins["tauri://localhost"] = struct{}{}
	g.origins["http://tauri.localhost"] = struct{}{}
	return g
}

// LoopbackHosts فهرستِ Hostهایِ مجازِ همان پورت است؛ هر نامِ دیگری که به
// 127.0.0.1 برسد (DNS rebinding) با Host: evil.com رد می‌شود.
func LoopbackHosts(port int) []string {
	p := strconv.Itoa(port)
	return []string{
		"127.0.0.1:" + p,
		"localhost:" + p,
		"[::1]:" + p,
	}
}

func OriginsFor(hosts []string) []string {
	out := make([]string, 0, len(hosts))
	for _, h := range hosts {
		out = append(out, "http://"+h)
	}
	return out
}

func PortOf(addr string) int {
	_, port, err := net.SplitHostPort(addr)
	if err != nil {
		return 0
	}
	n, _ := strconv.Atoi(port)
	return n
}

func (g *Guard) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if _, ok := g.hosts[strings.ToLower(r.Host)]; !ok {
			deny(w, http.StatusForbidden, "HOST_NOT_ALLOWED", "Host is not an allowed loopback address")
			return
		}
		if origin := strings.TrimSpace(r.Header.Get("Origin")); origin != "" {
			if _, ok := g.origins[strings.ToLower(origin)]; !ok {
				deny(w, http.StatusForbidden, "ORIGIN_NOT_ALLOWED", "Origin is not allowed")
				return
			}
		}
		if r.URL.Path == "/healthz" {
			next.ServeHTTP(w, r)
			return
		}
		if !strings.HasPrefix(r.URL.Path, "/api/") {
			if r.Method != http.MethodGet && r.Method != http.MethodHead {
				deny(w, http.StatusForbidden, "METHOD_NOT_ALLOWED", "static content is read-only")
				return
			}
			g.setCookie(w)
			next.ServeHTTP(w, r)
			return
		}
		if r.Method == http.MethodOptions {
			// هیچ CORSی باز نیست؛ preflight همان‌جا بسته می‌شود.
			deny(w, http.StatusForbidden, "CORS_CLOSED", "cross-origin API access is not allowed")
			return
		}
		got, source := g.tokenFrom(r)
		if got == "" || subtle.ConstantTimeCompare([]byte(got), []byte(g.token)) != 1 {
			w.Header().Set("WWW-Authenticate", `Bearer realm="borsd"`)
			deny(w, http.StatusUnauthorized, "UNAUTHORIZED", "a valid local API token is required")
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			if source == sourceCookie && r.Header.Get(CSRFHeader) != "1" {
				deny(w, http.StatusForbidden, "CSRF_REQUIRED", "cookie-authenticated writes require "+CSRFHeader+": 1")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

type tokenSource int

const (
	sourceNone tokenSource = iota
	sourceHeader
	sourceCookie
)

func (g *Guard) tokenFrom(r *http.Request) (string, tokenSource) {
	if v := strings.TrimSpace(r.Header.Get("Authorization")); v != "" {
		const prefix = "Bearer "
		if len(v) > len(prefix) && strings.EqualFold(v[:len(prefix)], prefix) {
			return strings.TrimSpace(v[len(prefix):]), sourceHeader
		}
	}
	if v := strings.TrimSpace(r.Header.Get(TokenHeader)); v != "" {
		return v, sourceHeader
	}
	if c, err := r.Cookie(CookieName); err == nil && c.Value != "" {
		return c.Value, sourceCookie
	}
	return "", sourceNone
}

func (g *Guard) setCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     CookieName,
		Value:    g.token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
	})
}

func deny(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"status": "error", "code": code, "message": message, "retryable": false,
	})
}
