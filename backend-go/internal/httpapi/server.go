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
	cfg     config.Config
	db      *db.Handles
	started time.Time
	rssMB   func() float64
}

func New(cfg config.Config, h *db.Handles) http.Handler {
	s := &Server{cfg: cfg, db: h, started: time.Now(), rssMB: rssMB}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.healthz)
	mux.HandleFunc("/", s.apiGate)
	return mux
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
	route := r.Method + " " + r.URL.Path
	if _, known := routeSet[route]; known {
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
		"version":     version,
		"data_dir":    s.cfg.DataDir,
		"market_mode": mode,
		"loops":       loops,
		"go":          runtime.Version(),
		"uptime_s":    time.Since(s.started).Seconds(),
		"rss_mb":      s.rssMB(),
	})
}
