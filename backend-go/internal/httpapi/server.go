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
	// TapeHistory از B4: سابقۀ هفت فیلتر در user.db (مسیرِ api/market.py).
	TapeHistory(http.ResponseWriter, *http.Request)
}

// Chart هشت مسیرِ محلیِ api/chart.py در B3 (مسیرِ CDNِ /api/chart و
// POSTها در B6 می‌مانند)؛ nil یعنی هیچ‌کدام پورت نشده.
type Chart interface {
	ChartDB(http.ResponseWriter, *http.Request)
	FTS(http.ResponseWriter, *http.Request)
	OrderBook(http.ResponseWriter, *http.Request)
	KeyLevels(http.ResponseWriter, *http.Request)
	CalendarUpcoming(http.ResponseWriter, *http.Request)
	CalendarSymbol(http.ResponseWriter, *http.Request)
	MA(http.ResponseWriter, *http.Request)
	Patterns(http.ResponseWriter, *http.Request)
}

// Mstat سیزده مسیرِ GETِ تبِ وضعیت بازار؛ nil یعنی هیچ‌کدام پورت نشده.
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
	SmartMoney(http.ResponseWriter, *http.Request)
	Board(http.ResponseWriter, *http.Request)
	SnapshotNow(http.ResponseWriter, *http.Request)
}

// Fundamental دو مسیرِ خواندنیِ api/fundamental.py که درِ B4 پورت شده‌اند؛
// nil یعنی هیچ‌کدام پورت نشده. کارتِ پنج‌محور (`{symbol}`)، `screen` و
// `/api/sync/codal/*` هنوز درِ فهرست می‌مانند و apiGate همان‌ها را 501 می‌کند.
type Fundamental interface {
	Sectors(http.ResponseWriter, *http.Request)
	Quarters(http.ResponseWriter, *http.Request)
	Card(http.ResponseWriter, *http.Request)
}

// Watchlist سه مسیرِ CRUD واچ‌لیست در B5؛ nil یعنی پورت نشده.
// مسیرِ GET /api/watchlist/matrix تا فاز B7 روی 501 (notPortedRoute) می‌ماند.
type Watchlist interface {
	Get(http.ResponseWriter, *http.Request)
	Post(http.ResponseWriter, *http.Request)
	Delete(http.ResponseWriter, *http.Request)
}

// Notifications دو مسیرِ خواندنیِ مرکز اعلان در B5؛ nil یعنی پورت نشده.
type Notifications interface {
	Sources(http.ResponseWriter, *http.Request)
	Feed(http.ResponseWriter, *http.Request)
}

// Sync مسیرهای همگام‌سازی، وضعیت و کنترل در B6؛ nil یعنی پورت نشده.
type Sync interface {
	SyncStatus(http.ResponseWriter, *http.Request)
	CodalDBStatus(http.ResponseWriter, *http.Request)
	Diagnose(http.ResponseWriter, *http.Request)
	SyncMarket(http.ResponseWriter, *http.Request)
	SyncCodal(http.ResponseWriter, *http.Request)
	SyncCodalFTSRefresh(http.ResponseWriter, *http.Request)
	SyncCodalDBDownload(http.ResponseWriter, *http.Request)
	CodalControl(http.ResponseWriter, *http.Request)
}

// Selection چهار مسیر سبد دارایی و تصمیمات در B7؛ nil یعنی پورت نشده.
type Selection interface {
	Symbols(http.ResponseWriter, *http.Request)
	Portfolio(http.ResponseWriter, *http.Request)
	PostDecision(http.ResponseWriter, *http.Request)
	DeleteDecision(http.ResponseWriter, *http.Request)
}

// MarketIndex مسیر شاخص کل در B7؛ nil یعنی پورت نشده.
type MarketIndex interface {
	TEDPIX(http.ResponseWriter, *http.Request)
}

// Export مسیرهای صدور داده CSV در B7؛ nil یعنی پورت نشده.
type Export interface {
	Post(http.ResponseWriter, *http.Request)
	Get(http.ResponseWriter, *http.Request)
}

// Screener مسیرهای تاریخچه و اسکرینر FTS در B7؛ nil یعنی پورت نشده.
type Screener interface {
	History(http.ResponseWriter, *http.Request)
	Screener(http.ResponseWriter, *http.Request)
}

// Funnel مسیرهای قیف FTS در B7؛ nil یعنی پورت نشده.
type Funnel interface {
	Registry(http.ResponseWriter, *http.Request)
	GetFunnel(http.ResponseWriter, *http.Request)
	PostFunnel(http.ResponseWriter, *http.Request)
	Trace(http.ResponseWriter, *http.Request)
}

// Services مجموعه‌ی کلیه سرویس‌های HTTP بورس‌ترمینال.
type Services struct {
	Market        Market
	Mstat         Mstat
	Chart         Chart
	Fundamental   Fundamental
	Watchlist     Watchlist
	Notifications Notifications
	Sync          Sync
	Selection     Selection
	MarketIndex   MarketIndex
	Export        Export
	Screener      Screener
	Funnel        Funnel
}

func New(cfg config.Config, h *db.Handles, m Market, ms Mstat, ch Chart, fd Fundamental, wl Watchlist, nt Notifications, sy Sync) http.Handler {
	return NewWithServices(cfg, h, Services{
		Market:        m,
		Mstat:         ms,
		Chart:         ch,
		Fundamental:   fd,
		Watchlist:     wl,
		Notifications: nt,
		Sync:          sy,
	})
}

func NewWithServices(cfg config.Config, h *db.Handles, srv Services) http.Handler {
	s := &Server{
		cfg:      cfg,
		db:       h,
		started:  time.Now(),
		rssMB:    rssMB,
		patterns: compileRoutes(Routes()),
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.healthz)
	if srv.Market != nil {
		mux.HandleFunc("GET /api/market", srv.Market.Board)
		mux.HandleFunc("GET /api/market/delta", srv.Market.Delta)
		mux.HandleFunc("GET /api/market/sync-state", srv.Market.SyncState)
		mux.HandleFunc("GET /api/tape-history", srv.Market.TapeHistory)
	}
	if srv.Mstat != nil {
		mux.HandleFunc("GET /api/mstat/summary", srv.Mstat.Summary)
		mux.HandleFunc("GET /api/mstat/histogram", srv.Mstat.Histogram)
		mux.HandleFunc("GET /api/mstat/thermometer", srv.Mstat.Thermometer)
		mux.HandleFunc("GET /api/mstat/depth", srv.Mstat.Depth)
		mux.HandleFunc("GET /api/mstat/clientsplit", srv.Mstat.ClientSplit)
		mux.HandleFunc("GET /api/mstat/market-snapshot", srv.Mstat.MarketSnapshot)
		mux.HandleFunc("GET /api/mstat/phase", srv.Mstat.Phase)
		mux.HandleFunc("GET /api/mstat/mainwatch", srv.Mstat.Mainwatch)
		mux.HandleFunc("GET /api/mstat/industries", srv.Mstat.Industries)
		mux.HandleFunc("GET /api/mstat/timeline", srv.Mstat.Timeline)
		mux.HandleFunc("GET /api/mstat/phases", srv.Mstat.Phases)
		mux.HandleFunc("GET /api/mstat/smart-money", srv.Mstat.SmartMoney)
		mux.HandleFunc("GET /api/mstat/board", srv.Mstat.Board)
		mux.HandleFunc("POST /api/mstat/snapshot", srv.Mstat.SnapshotNow)
	}
	if srv.Chart != nil {
		mux.HandleFunc("GET /api/chart/{symbol}/key-levels", srv.Chart.KeyLevels)
		mux.HandleFunc("GET /api/order-book/{symbol}", srv.Chart.OrderBook)
		mux.HandleFunc("GET /api/calendar/upcoming", srv.Chart.CalendarUpcoming)
		mux.HandleFunc("GET /api/calendar/{symbol}", srv.Chart.CalendarSymbol)
		mux.HandleFunc("GET /api/ma/{symbol}", srv.Chart.MA)
		mux.HandleFunc("GET /api/patterns/{symbol}", srv.Chart.Patterns)
		mux.HandleFunc("GET /api/chart-db/{symbol}", srv.Chart.ChartDB)
		mux.HandleFunc("GET /api/fts/{symbol}", srv.Chart.FTS)
		// `/api/fts/config` درِ پایتون متعلق به api/market.py است و *پیش از*
		// `/api/fts/{symbol}` ثبت می‌شود، پس «config» هیچ‌وقت نماد نیست. Go با
		// الگویِ عام آن را می‌بلعید؛ این ثبتِ صریح همان ترتیب را بازمی‌گرداند.
		mux.HandleFunc("GET /api/fts/config", s.notPortedRoute)
	}
	if srv.Fundamental != nil {
		// `sectors` صریح و پیش از هر `{symbol}` ثبت می‌شود (R9 از پلنِ B4): درِ
		// پایتون هم متنیِ `/api/fundamental/sectors` پیش از `/api/fundamental/{symbol}`
		// تعریف شده است.
		mux.HandleFunc("GET /api/fundamental/sectors", srv.Fundamental.Sectors)
		mux.HandleFunc("GET /api/fundamental/screen", s.notPortedRoute)
		mux.HandleFunc("GET /api/fundamental/{symbol}/quarters", srv.Fundamental.Quarters)
		mux.HandleFunc("GET /api/fundamental/{symbol}", srv.Fundamental.Card)
	}
	if srv.Watchlist != nil {
		mux.HandleFunc("GET /api/watchlist", srv.Watchlist.Get)
		mux.HandleFunc("POST /api/watchlist", srv.Watchlist.Post)
		mux.HandleFunc("DELETE /api/watchlist/{symbol}", srv.Watchlist.Delete)
		mux.HandleFunc("GET /api/watchlist/matrix", s.notPortedRoute)
	}
	if srv.Notifications != nil {
		mux.HandleFunc("GET /api/notifications/sources", srv.Notifications.Sources)
		mux.HandleFunc("GET /api/notifications/feed", srv.Notifications.Feed)
	}
	if srv.Sync != nil {
		mux.HandleFunc("GET /api/sync/status", srv.Sync.SyncStatus)
		mux.HandleFunc("GET /api/sync/codal/db-status", srv.Sync.CodalDBStatus)
		mux.HandleFunc("GET /api/sync/diagnose", srv.Sync.Diagnose)
		mux.HandleFunc("POST /api/sync/market", srv.Sync.SyncMarket)
		mux.HandleFunc("POST /api/sync/codal", srv.Sync.SyncCodal)
		mux.HandleFunc("POST /api/sync/codal/fts-refresh", srv.Sync.SyncCodalFTSRefresh)
		mux.HandleFunc("POST /api/sync/codal/db-download", srv.Sync.SyncCodalDBDownload)
		mux.HandleFunc("POST /api/codal/control", srv.Sync.CodalControl)
	}
	if srv.Selection != nil {
		mux.HandleFunc("GET /api/selection/symbols", srv.Selection.Symbols)
		mux.HandleFunc("GET /api/selection/portfolio", srv.Selection.Portfolio)
		mux.HandleFunc("POST /api/selection/decision", srv.Selection.PostDecision)
		mux.HandleFunc("DELETE /api/selection/decision/{symbol}", srv.Selection.DeleteDecision)
	}
	if srv.MarketIndex != nil {
		mux.HandleFunc("GET /api/index/tedpix", srv.MarketIndex.TEDPIX)
	}
	if srv.Export != nil {
		mux.HandleFunc("POST /api/export", srv.Export.Post)
		mux.HandleFunc("GET /api/export", srv.Export.Get)
	}
	if srv.Screener != nil {
		mux.HandleFunc("GET /api/history/{symbol}", srv.Screener.History)
		mux.HandleFunc("GET /api/screener", srv.Screener.Screener)
	}
	if srv.Funnel != nil {
		mux.HandleFunc("GET /api/funnel", srv.Funnel.GetFunnel)
		mux.HandleFunc("POST /api/funnel", srv.Funnel.PostFunnel)
		mux.HandleFunc("GET /api/funnel/registry", srv.Funnel.Registry)
		mux.HandleFunc("GET /api/funnel/trace", srv.Funnel.Trace)
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

// notPortedRoute مسیرِ فهرستِ پایتون است اما هنوز پورت نشده — همان ۵۰۱ِ apiGate،
// بی‌اینکه الگویِ عامِ هم‌خانوادۀ آن را ببلعید.
func (s *Server) notPortedRoute(w http.ResponseWriter, r *http.Request) {
	NotPorted(w, r.Method+" "+r.URL.Path)
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
