// Package chart پورتِ مسیرهایِ محلیِ api/chart.py: چارت، سطوح، تقویم، MA،
// الگوها، عمقِ سفارش و موتورِ FTS.
//
// در فازِ A این پکیج نه شبکه می‌زند نه در market.db می‌نویسد. مسیرِ CDN تا B6
// در پایتون می‌ماند؛ همهٔ پاسخ‌ها از همان بانکِ محلی ساخته می‌شوند که مسیرِ
// فال‌بکِ پایتون می‌خواند.
package chart

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/symbolid"
)

const (
	keyLevelsTTL = 300 * time.Second
	maTTL        = 900 * time.Second
	patternsTTL  = 300 * time.Second
	ftsTTL       = 900 * time.Second
	ftsCacheMax  = 3000
)

type Config struct {
	Market       *sql.DB
	User         *sql.DB
	DataDir      string
	CalendarPath string
	Clock        func() time.Time
}

type cacheEntry struct {
	at   time.Time
	body map[string]any
}

type Service struct {
	market       *sql.DB
	user         *sql.DB
	dataDir      string
	calendarPath string
	clock        func() time.Time
	sid          *symbolid.Resolver
	basis        *pricebasis.Resolver
	ftsPath      string
	engine       string

	mu        sync.Mutex
	keyLevels map[string]cacheEntry
	ma        map[string]cacheEntry
	patterns  map[string]cacheEntry
	fts       map[string]cacheEntry
	cal       calendarCache
}

func New(cfg Config) *Service {
	clock := cfg.Clock
	if clock == nil {
		clock = time.Now
	}
	s := &Service{
		market: cfg.Market, user: cfg.User, dataDir: cfg.DataDir,
		calendarPath: cfg.CalendarPath, clock: clock,
		sid:       symbolid.New(cfg.Market),
		basis:     pricebasis.New(filepath.Join(cfg.DataDir, "price_basis.json")),
		ftsPath:   filepath.Join(cfg.DataDir, "fts_thresholds.json"),
		engine:    trendEngine(),
		keyLevels: map[string]cacheEntry{}, ma: map[string]cacheEntry{},
		patterns: map[string]cacheEntry{}, fts: map[string]cacheEntry{},
	}
	return s
}

func (s *Service) Close() error { return s.sid.Close() }

// trendEngine معادلِ TREND_ENGINE درِ api/chart.py: خواندنِ env یک‌بار درِ
// ساختِ سرویس؛ مقدارِ ناشناخته فقط «legacy» نیست، بلکه درِ کلیدِ کش وِ fieldِ
// پاسخ هم نوشته می‌شود (پایتون همین را می‌کند).
func trendEngine() string {
	raw, ok := os.LookupEnv("BORS_TREND_ENGINE")
	if !ok {
		return "legacy"
	}
	raw = strings.ToLower(strings.TrimSpace(raw))
	if raw == "" {
		return "legacy"
	}
	return raw
}

func (s *Service) now() time.Time { return s.clock() }

// pred معادلِ sym_pred: خطایِ لایهٔ هویت ⇒ همان برابریِ سادهٔ پایتون.
func (s *Service) pred(ctx context.Context, col, symbol string) (string, []any) {
	p, params, err := s.sid.Pred(ctx, col, symbol, symbolid.Board)
	if err != nil {
		return col + " = ?", []any{symbol}
	}
	return p, params
}

func (s *Service) cacheGet(store map[string]cacheEntry, key string, ttl time.Duration) (map[string]any, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	e, ok := store[key]
	if !ok || s.now().Sub(e.at) >= ttl {
		return nil, false
	}
	return e.body, true
}

func (s *Service) cachePut(store map[string]cacheEntry, key string, body map[string]any) {
	s.mu.Lock()
	defer s.mu.Unlock()
	store[key] = cacheEntry{at: s.now(), body: body}
}
