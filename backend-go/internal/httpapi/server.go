package httpapi

import (
	"net/http"
	"runtime"
	"strings"
	"time"

	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
)

type Server struct {
	cfg      config.Config
	db       *db.Handles
	started  time.Time
	rssMB    func() float64
	patterns []routePattern
}

// routePattern یک مسیرِ فهرست است که به قطعه‌هایش شکسته شده. قطعهٔ {name}
// عینِ Starlette فقط یک قطعهٔ غیرخالی را جور می‌کند؛ پس /api/chart/فولاد
// به الگوی «GET /api/chart/{symbol}» می‌خورد و 501 می‌گیرد، نه 404.
type routePattern struct {
	method string
	segs   []segment
}

type segment struct {
	literal string
	param   bool
}

// Market سه مسیرِ پورت‌شدهٔ تابلو را می‌گیرد؛ nil یعنی هیچ مسیری پورت نشده.
type Market interface {
	Board(http.ResponseWriter, *http.Request)
	Delta(http.ResponseWriter, *http.Request)
	SyncState(http.ResponseWriter, *http.Request)
}

func New(cfg config.Config, h *db.Handles, m Market) http.Handler {
	s := &Server{
		cfg:      cfg,
		db:       h,
		started:  time.Now(),
		rssMB:    rssMB,
		patterns: compileRoutes(Routes()),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.healthz)
	if m != nil {
		mux.HandleFunc("GET /api/market", m.Board)
		mux.HandleFunc("GET /api/market/delta", m.Delta)
		mux.HandleFunc("GET /api/market/sync-state", m.SyncState)
	}
	mux.HandleFunc("/", s.apiGate)
	return mux
}

// compileRoutes رشته‌هایِ «METHOD /api/...» را یک‌بار به الگوهایِ قطعه‌ای تبدیل می‌کند.
func compileRoutes(routes []string) []routePattern {
	patterns := make([]routePattern, 0, len(routes))
	for _, route := range routes {
		method, path, ok := strings.Cut(route, " ")
		if !ok {
			continue
		}
		patterns = append(patterns, routePattern{method: method, segs: splitPath(path)})
	}
	return patterns
}

func splitPath(path string) []segment {
	parts := strings.Split(strings.TrimPrefix(path, "/"), "/")
	segs := make([]segment, len(parts))
	for i, part := range parts {
		if len(part) > 2 && strings.HasPrefix(part, "{") && strings.HasSuffix(part, "}") {
			segs[i] = segment{param: true}
			continue
		}
		segs[i] = segment{literal: part}
	}
	return segs
}

func (p routePattern) matches(method, path string) bool {
	if p.method != method || !strings.HasPrefix(path, "/") {
		return false
	}
	parts := strings.Split(path[1:], "/")
	if len(parts) != len(p.segs) {
		return false
	}
	for i, seg := range p.segs {
		if seg.param {
			if parts[i] == "" {
				return false
			}
			continue
		}
		if parts[i] != seg.literal {
			return false
		}
	}
	return true
}

func (s *Server) knownRoute(method, path string) bool {
	for _, p := range s.patterns {
		if p.matches(method, path) {
			return true
		}
	}
	return false
}

func (s *Server) apiGate(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/healthz" {
		w.Header().Set("Allow", "GET")
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	if !strings.HasPrefix(r.URL.Path, "/api/") {
		NotFound(w)
		return
	}
	// route عمداً مسیرِ واقعیِ درخواست است، نه قالبِ routes.json؛ کلاینت باید
	// ببیند دقیقاً چه مسیری صدا زده شده و هنوز پورت نشده است.
	route := r.Method + " " + r.URL.Path
	if s.knownRoute(r.Method, r.URL.Path) {
		NotPorted(w, route)
		return
	}
	NotFound(w)
}

func (s *Server) healthz(w http.ResponseWriter, r *http.Request) {
	mode := "read-write"
	if s.cfg.ReadOnly {
		mode = "read-only"
	}
	loops := "on"
	if s.cfg.NoLoops {
		loops = "off"
	}
	status := "ok"
	if s.db != nil {
		ctx, cancel := contextWithTimeout(r, 2*time.Second)
		defer cancel()
		if err := s.db.Ping(ctx); err != nil {
			status = "degraded"
		}
	}
	WriteJSON(w, http.StatusOK, map[string]any{
		"status":      status,
		"version":     Version(),
		"data_dir":    s.cfg.DataDir,
		"market_mode": mode,
		"loops":       loops,
		"go":          runtime.Version(),
		"uptime_s":    time.Since(s.started).Seconds(),
		"rss_mb":      s.rssMB(),
	})
}
