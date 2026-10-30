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

// Mstat یازده مسیرِ GETِ تبِ وضعیت بازار؛ nil یعنی هیچ‌کدام پورت نشده.
type Mstat interface {
	Summary(http.ResponseWriter, *http.Request)
	Histogram(http.ResponseWriter, *http.Request)
	Thermometer(http.ResponseWriter, *http.Request)
	Depth(http.ResponseWriter, *http.Request)
	ClientSplit(http.ResponseWriter, *http.Request)
	MarketSnapshot(http.ResponseWriter, *http.Request)
	Phase(http.ResponseWriter, *http.Request)
	Mainwatch(http.ResponseWriter, *http.Request)
	Industries(http.ResponseWriter, *http.Request)
	Timeline(http.ResponseWriter, *http.Request)
	Phases(http.ResponseWriter, *http.Request)
}

func New(cfg config.Config, h *db.Handles, m Market, ms Mstat) http.Handler {
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
	if ms != nil {
		mux.HandleFunc("GET /api/mstat/summary", ms.Summary)
		mux.HandleFunc("GET /api/mstat/histogram", ms.Histogram)
		mux.HandleFunc("GET /api/mstat/thermometer", ms.Thermometer)
		mux.HandleFunc("GET /api/mstat/depth", ms.Depth)
		mux.HandleFunc("GET /api/mstat/clientsplit", ms.ClientSplit)
		mux.HandleFunc("GET /api/mstat/market-snapshot", ms.MarketSnapshot)
		mux.HandleFunc("GET /api/mstat/phase", ms.Phase)
		mux.HandleFunc("GET /api/mstat/mainwatch", ms.Mainwatch)
		mux.HandleFunc("GET /api/mstat/industries", ms.Industries)
		mux.HandleFunc("GET /api/mstat/timeline", ms.Timeline)
		mux.HandleFunc("GET /api/mstat/phases", ms.Phases)
	}
	mux.HandleFunc("/", s.apiGate)
	return noCache(mux)
}

// noCache پورتِ no_cache_middlewareِ app.py است: رویِ همهٔ پاسخ‌ها جز دارایی‌هایِ
// هش‌دار، Cache-Control را به no-store بازنویسی و Pragma می‌گذارد. این لایه
// برگ‌های نیست: خودِ هندلرها هم max-age می‌گذارند (`/api/market`)، ولی پایتون
// پس از هندلر بازنویسی می‌کند و آن‌چه به مشتری می‌رسد همین no-store است. در
// net/http هدرِ پس از WriteHeader اثری ندارد، پس تزریق همان لحظهٔ نوشتنِ هدر
// انجام می‌شود تا پاسخِ Go رویِ سیم عینِ پاسخِ پایتون باشد.
//
// دو پیشوندِ /assets/ و /vendor/ این‌جا استثنا شده‌اند چون پایتون آن‌ها را
// میدل‌ورِ ایستایِ خودش با «public, max-age=31536000, immutable» سرو می‌کند
// (داراییِ هش‌دار). این دو مسیر بیرونِ سطحِ پورت‌شده‌اند و B0 همان ۴۰۴ را به
// ارث گذاشت؛ TestNoStoreHeaders عمداً همین رفتارِ واگرا را پین می‌کند تا روزی
// که میدل‌ورِ ایستا پورت شد، تفاوت دیده شود نه اینکه بی‌صدا عوض شود.
func noCache(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if strings.HasPrefix(p, "/assets/") || strings.HasPrefix(p, "/vendor/") {
			next.ServeHTTP(w, r)
			return
		}
		next.ServeHTTP(&noCacheWriter{ResponseWriter: w}, r)
	})
}

type noCacheWriter struct {
	http.ResponseWriter
}

func (w *noCacheWriter) SetNoCache() {
	h := w.Header()
	h.Set("Cache-Control", "no-cache, no-store, must-revalidate")
	h.Set("Pragma", "no-cache")
}

func (w *noCacheWriter) WriteHeader(code int) {
	w.SetNoCache()
	w.ResponseWriter.WriteHeader(code)
}

func (w *noCacheWriter) Write(body []byte) (int, error) {
	// هندلری که WriteHeader را صدا نزده باشد، همین‌جا هدرِ 200 می‌نویسد.
	w.SetNoCache()
	return w.ResponseWriter.Write(body)
}

// Unwrap درِ ResponseController است تا Flush/ReadFromِ لایه‌هایِ بعدی (مثلِ
// SSEِ آینده) از میانِ این پوشش هم برسد.
func (w *noCacheWriter) Unwrap() http.ResponseWriter { return w.ResponseWriter }

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
