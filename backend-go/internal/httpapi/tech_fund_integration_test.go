package httpapi_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/chart"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/httpapi"
	borssync "borsterminal/backend/internal/sync"
)

const (
	symAdadi01 = "\u0639\u0627\u062f\u06cc01" // عادی01
	symFoolad  = "\u0641\u0648\u0644\u0627\u062f" // فولاد
	symGhayeb  = "\u063a\u0627\u06cc\u0628\u06f9\u06f9" // غایب۹۹
)

func setupTechFundIntegrationServer(t *testing.T) (http.Handler, *db.Handles, string) {
	t.Helper()
	tempDir := t.TempDir()

	// Copy market.db and user.db fixtures from internal/fundamental/testdata/fixture
	for _, fname := range []string{"market.db", "user.db"} {
		src := filepath.Join("..", "fundamental", "testdata", "fixture", fname)
		data, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("read fixture %s: %v", fname, err)
		}
		targetPath := filepath.Join(tempDir, fname)
		if err := os.WriteFile(targetPath, data, 0o644); err != nil {
			t.Fatalf("write fixture %s: %v", fname, err)
		}
	}

	// Create codal.db in tempDir from market.db fixture so Handles.Codal can be initialized
	{
		src := filepath.Join("..", "fundamental", "testdata", "fixture", "market.db")
		data, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("read fixture for codal.db: %v", err)
		}
		targetPath := filepath.Join(tempDir, "codal.db")
		if err := os.WriteFile(targetPath, data, 0o644); err != nil {
			t.Fatalf("write fixture codal.db: %v", err)
		}
	}

	// Copy calendar cache fixture
	calDir := filepath.Join(tempDir, "calendar")
	if err := os.MkdirAll(calDir, 0o755); err != nil {
		t.Fatalf("mkdir calendar: %v", err)
	}
	{
		src := filepath.Join("..", "chart", "testdata", "fixture", "calendar", "cache.json")
		data, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("read calendar fixture: %v", err)
		}
		targetPath := filepath.Join(calDir, "cache.json")
		if err := os.WriteFile(targetPath, data, 0o644); err != nil {
			t.Fatalf("write calendar fixture: %v", err)
		}
	}

	// Inject test data and pipeline tables into test copy using OpenWritableForTest
	hInit, err := db.OpenWritableForTest(tempDir)
	if err != nil {
		t.Fatalf("OpenWritableForTest failed: %v", err)
	}

	// 1. Ensure order_book table with 5-level depth exists
	_, err = hInit.Market.Exec(`CREATE TABLE IF NOT EXISTS order_book(
		ins_code TEXT PRIMARY KEY,
		book_txt TEXT,
		d_even INTEGER,
		h_even INTEGER,
		updated_at TEXT
	)`)
	if err != nil {
		t.Fatalf("create order_book: %v", err)
	}
	_, err = hInit.Market.Exec(`INSERT OR REPLACE INTO order_book (ins_code, book_txt, d_even, h_even, updated_at) VALUES (?, ?, ?, ?, ?)`,
		"INS-\u0639\u0627\u062f\u06cc01",
		"[[2010.0, 120000.0, 14.0, 2020.0, 90000.0, 11.0], [2005.0, 300000.0, 22.0, 2025.0, 150000.0, 19.0], [2000.0, 500000.0, 31.0, 2030.0, 260000.0, 24.0], [1995.0, 450000.0, 27.0, 2035.0, 340000.0, 29.0], [1990.0, 700000.0, 40.0, 2040.0, 410000.0, 33.0]]",
		20261014, 124000, "2026-10-14 12:40:00")
	if err != nil {
		t.Fatalf("insert order_book row: %v", err)
	}

	// 2. Ensure price_history last column and liquid traded value for indicators & predictions
	_, _ = hInit.Market.Exec(`ALTER TABLE price_history ADD COLUMN last REAL`)
	_, _ = hInit.Market.Exec(`UPDATE price_history SET last = close WHERE last IS NULL`)
	_, _ = hInit.Market.Exec(`UPDATE price_history SET value = 10000000000.0 WHERE symbol = ?`, symAdadi01)

	// 3. Inject فولاد (Foolad) instrument and history aliasing عادی01 for testing Persian URL decoding
	_, _ = hInit.Market.Exec(`INSERT OR IGNORE INTO instruments (ins_code, l_val18, l_val30, sector_name) VALUES ('INS-FOOLAD', ?, 'فولاد مبارکه', 'فلزات اساسي')`, symFoolad)
	_, _ = hInit.Market.Exec(`INSERT OR IGNORE INTO market_watch (ins_code, p_closing, p_last, q_tot_tran, d_even) VALUES ('INS-FOOLAD', 5100.0, 5120.0, 5000000.0, 20261028)`)
	_, _ = hInit.Market.Exec(`INSERT OR IGNORE INTO price_history (symbol, date, open, high, low, close, volume, last, value)
		SELECT ?, date, open, high, low, close, volume, last, value FROM price_history WHERE symbol = ?`, symFoolad, symAdadi01)

	// 4. Inject pipeline health tables for GET /api/sync/codal/pipeline
	_, err = hInit.Market.Exec(`CREATE TABLE IF NOT EXISTS codal_extracted(
		id INTEGER PRIMARY KEY,
		symbol TEXT,
		state TEXT,
		tried_at TEXT
	)`)
	if err != nil {
		t.Fatalf("create codal_extracted: %v", err)
	}
	_, _ = hInit.Market.Exec(`INSERT INTO codal_extracted (id, symbol, state, tried_at) VALUES (1, 'عادی01', 'done', '2026-10-28 10:00:00')`)
	_, _ = hInit.Market.Exec(`INSERT INTO codal_extracted (id, symbol, state, tried_at) VALUES (2, 'پایین02', 'done', '2026-10-28 10:01:00')`)
	_, _ = hInit.Market.Exec(`INSERT INTO codal_extracted (id, symbol, state, tried_at) VALUES (3, 'اهرم‌ب', 'queued', '2026-10-28 10:02:00')`)
	_, _ = hInit.Market.Exec(`INSERT INTO codal_extracted (id, symbol, state, tried_at) VALUES (4, 'ساده12', 'running', '2026-10-28 10:03:00')`)

	_, err = hInit.Market.Exec(`CREATE TABLE IF NOT EXISTS pipeline_dirty(symbol TEXT PRIMARY KEY)`)
	if err != nil {
		t.Fatalf("create pipeline_dirty: %v", err)
	}
	_, _ = hInit.Market.Exec(`INSERT INTO pipeline_dirty (symbol) VALUES ('عادی01')`)

	_, err = hInit.Market.Exec(`CREATE TABLE IF NOT EXISTS pipeline_cursor(key TEXT PRIMARY KEY, value TEXT)`)
	if err != nil {
		t.Fatalf("create pipeline_cursor: %v", err)
	}
	_, _ = hInit.Market.Exec(`INSERT INTO pipeline_cursor (key, value) VALUES ('notice_gap_flag', '0')`)

	_, err = hInit.Market.Exec(`CREATE TABLE IF NOT EXISTS pipeline_runs(
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		started_at TEXT,
		finished_at TEXT,
		cycle TEXT,
		phase TEXT,
		error TEXT,
		found INTEGER,
		enqueued INTEGER,
		processed INTEGER,
		done INTEGER,
		empty INTEGER,
		failed INTEGER,
		unresolved INTEGER
	)`)
	if err != nil {
		t.Fatalf("create pipeline_runs: %v", err)
	}
	_, _ = hInit.Market.Exec(`INSERT INTO pipeline_runs (started_at, finished_at, cycle, phase, error, found, enqueued, processed, done, empty, failed, unresolved)
		VALUES ('2026-10-28 09:00:00', '2026-10-28 09:15:00', 'daily', 'completed', NULL, 12, 4, 4, 4, 0, 0, 0)`)

	if err := hInit.Close(); err != nil {
		t.Fatalf("close hInit: %v", err)
	}

	// Open read-only handles adhering strictly to Single Writer rules
	handles, err := db.Open(tempDir, true)
	if err != nil {
		t.Fatalf("db.Open failed: %v", err)
	}
	t.Cleanup(func() { _ = handles.Close() })

	// Initialize Chart, Fundamental, and Sync services
	calPath := filepath.Join(tempDir, "calendar", "cache.json")
	pinnedClock := func() time.Time { return time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local) }

	chSvc := chart.New(chart.Config{
		Market:       handles.Market,
		User:         handles.User,
		DataDir:      tempDir,
		CalendarPath: calPath,
		Clock:        pinnedClock,
	})
	t.Cleanup(func() { _ = chSvc.Close() })

	fdSvc := fundamental.New(handles.Market, tempDir)
	t.Cleanup(func() { _ = fdSvc.Close() })

	sySvc := borssync.NewHandler(tempDir)

	cfg := config.Config{
		Addr:     "127.0.0.1:0",
		DataDir:  tempDir,
		ReadOnly: true,
		NoLoops:  true,
	}

	handler := httpapi.NewWithServices(cfg, handles, httpapi.Services{
		Chart:       chSvc,
		Fundamental: fdSvc,
		Sync:        sySvc,
	})

	return handler, handles, tempDir
}

func TestTechFundIntegration(t *testing.T) {
	handler, handles, _ := setupTechFundIntegrationServer(t)

	// 1. GET /api/chart-db/{symbol} -> ChartSchema
	t.Run("ChartDB_AdjustmentsAndEncodings", func(t *testing.T) {
		// Test URL-encoded Persian path symbol
		encodedPath := "/api/chart-db/" + url.PathEscape(symAdadi01) + "?adjustment=3"
		_, bodyAdj3 := getReq(t, handler, encodedPath)
		if bodyAdj3["status"] != "success" {
			t.Fatalf("expected status 'success', got %v", bodyAdj3["status"])
		}
		if sym, ok := bodyAdj3["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, bodyAdj3["symbol"])
		}
		if adj, ok := bodyAdj3["adjustment"].(float64); !ok || int(adj) != 3 {
			t.Errorf("expected adjustment=3, got %v", bodyAdj3["adjustment"])
		}

		candles, ok := bodyAdj3["candles"].([]any)
		if !ok || len(candles) == 0 {
			t.Fatalf("expected non-empty candles array, got %T", bodyAdj3["candles"])
		}
		firstCandle, ok := candles[0].(map[string]any)
		if !ok {
			t.Fatalf("expected candle to be object, got %T", candles[0])
		}
		for _, key := range []string{"time", "open", "high", "low", "close"} {
			if _, exists := firstCandle[key]; !exists {
				t.Errorf("candle missing required key %q", key)
			}
		}

		factors, ok := bodyAdj3["factors"].([]any)
		if !ok || len(factors) == 0 {
			t.Fatalf("expected non-empty factors array, got %T", bodyAdj3["factors"])
		}

		// Test raw UTF-8 path with adjustment=0 (unadjusted: all factors must be 1.0)
		rawPath := "/api/chart-db/" + symAdadi01 + "?adjustment=0"
		_, bodyAdj0 := getReq(t, handler, rawPath)
		if adj, ok := bodyAdj0["adjustment"].(float64); !ok || int(adj) != 0 {
			t.Errorf("expected adjustment=0, got %v", bodyAdj0["adjustment"])
		}
		factorsAdj0, ok := bodyAdj0["factors"].([]any)
		if !ok || len(factorsAdj0) == 0 {
			t.Fatalf("expected non-empty factors in adj=0")
		}
		firstFactor, ok := factorsAdj0[0].(map[string]any)
		if !ok {
			t.Fatalf("expected factor object, got %T", factorsAdj0[0])
		}
		if fVal, ok := firstFactor["factor"].(float64); !ok || fVal != 1.0 {
			t.Errorf("expected factor=1.0 for unadjusted mode, got %v", firstFactor["factor"])
		}

		// Test URL-encoded Foolad symbol
		fooladEncoded := "/api/chart-db/%D9%81%D9%88%D9%84%D8%A7%D8%AF?adjustment=1"
		_, bodyFoolad := getReq(t, handler, fooladEncoded)
		if bodyFoolad["status"] != "success" {
			t.Fatalf("expected status 'success' for foolad, got %v", bodyFoolad["status"])
		}
		if sym, ok := bodyFoolad["symbol"].(string); !ok || sym != symFoolad {
			t.Errorf("expected decoded symbol %q, got %v", symFoolad, bodyFoolad["symbol"])
		}
	})

	// 2. GET /api/chart/{symbol}/forecast -> ForecastResponseSchema
	t.Run("Forecast_AIQuantilesAndHorizon", func(t *testing.T) {
		path := "/api/chart/" + url.PathEscape(symAdadi01) + "/forecast?horizon=12&model=small&adjustment=3"
		_, body := getReq(t, handler, path)

		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}
		if hz, ok := body["horizon"].(float64); !ok || int(hz) != 12 {
			t.Errorf("expected horizon=12, got %v", body["horizon"])
		}
		if _, ok := body["is_liquid"].(bool); !ok {
			t.Errorf("expected boolean is_liquid, got %T", body["is_liquid"])
		}

		steps, ok := body["forecast_steps"].([]any)
		if !ok || len(steps) != 12 {
			t.Fatalf("expected 12 forecast_steps, got %d", len(steps))
		}

		for idx, stAny := range steps {
			st, ok := stAny.(map[string]any)
			if !ok {
				t.Fatalf("step %d is not an object", idx)
			}
			p10, ok10 := st["p10"].(float64)
			p50, ok50 := st["p50"].(float64)
			p90, ok90 := st["p90"].(float64)
			if !ok10 || !ok50 || !ok90 {
				t.Fatalf("step %d missing valid p10/p50/p90 quantiles", idx)
			}
			if p10 > p50 || p50 > p90 {
				t.Errorf("step %d quantile ordering violation: p10 (%f) <= p50 (%f) <= p90 (%f)", idx, p10, p50, p90)
			}
		}

		// Also verify UTF-8 symbol path
		pathUTF8 := "/api/chart/" + symFoolad + "/forecast?horizon=5"
		_, bodyUTF8 := getReq(t, handler, pathUTF8)
		if sym, ok := bodyUTF8["symbol"].(string); !ok || sym != symFoolad {
			t.Errorf("expected decoded symbol %q, got %v", symFoolad, bodyUTF8["symbol"])
		}
	})

	// 3. GET /api/chart/{symbol}/edge -> CandleEdgeResponseSchema
	t.Run("CandleEdge_SMCStructuresAndWinrate", func(t *testing.T) {
		path := "/api/chart/" + url.PathEscape(symAdadi01) + "/edge?swing_period=5"
		_, body := getReq(t, handler, path)

		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}
		if regime, ok := body["market_regime"].(string); !ok || regime == "" {
			t.Errorf("expected non-empty market_regime, got %v", body["market_regime"])
		}

		zones, ok := body["active_zones"].([]any)
		if !ok {
			t.Fatalf("expected active_zones array, got %T", body["active_zones"])
		}
		if len(zones) > 0 {
			z0, ok := zones[0].(map[string]any)
			if !ok {
				t.Fatalf("expected zone object, got %T", zones[0])
			}
			for _, key := range []string{"id", "type", "top", "bottom", "equilibrium"} {
				if _, exists := z0[key]; !exists {
					t.Errorf("zone missing key %q", key)
				}
			}
		}

		structures, ok := body["recent_structures"].([]any)
		if !ok {
			t.Fatalf("expected recent_structures array, got %T", body["recent_structures"])
		}
		if len(structures) > 0 {
			s0, ok := structures[0].(map[string]any)
			if !ok {
				t.Fatalf("expected structure object, got %T", structures[0])
			}
			for _, key := range []string{"type", "price", "timestamp"} {
				if _, exists := s0[key]; !exists {
					t.Errorf("structure missing key %q", key)
				}
			}
		}

		if _, ok := body["sample_count"].(float64); !ok {
			t.Errorf("expected numeric sample_count, got %T", body["sample_count"])
		}
		if _, ok := body["profit_factor"].(float64); !ok {
			t.Errorf("expected numeric profit_factor, got %T", body["profit_factor"])
		}
	})

	// 4. GET /api/chart/{symbol}/indicators -> IndicatorsResponseSchema
	t.Run("Indicators_TechnicalCalculations", func(t *testing.T) {
		path := "/api/chart/" + url.PathEscape(symAdadi01) + "/indicators"
		_, body := getReq(t, handler, path)

		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}

		count, ok := body["count"].(float64)
		if !ok || int(count) <= 0 {
			t.Fatalf("expected count > 0, got %v", body["count"])
		}

		dates, ok := body["dates"].([]any)
		if !ok || len(dates) != int(count) {
			t.Fatalf("expected dates array of length %d, got %d", int(count), len(dates))
		}

		latest, ok := body["latest"].(map[string]any)
		if !ok {
			t.Fatalf("expected latest object, got %T", body["latest"])
		}
		expectedLatestKeys := []string{
			"close", "sma20", "sma50", "sma200", "ema9", "ema21",
			"rsi14", "macd", "macd_signal", "macd_hist",
			"supertrend", "supertrend_direction",
			"bollinger_upper", "bollinger_middle", "bollinger_lower", "atr14",
		}
		for _, key := range expectedLatestKeys {
			if _, exists := latest[key]; !exists {
				t.Errorf("latest indicators missing key %q", key)
			}
		}

		series, ok := body["series"].(map[string]any)
		if !ok {
			t.Fatalf("expected series object, got %T", body["series"])
		}
		for _, key := range []string{"sma20", "ema9", "rsi14", "macd", "supertrend"} {
			sArr, ok := series[key].([]any)
			if !ok || len(sArr) != int(count) {
				t.Errorf("series %q expected array of length %d, got %v", key, int(count), len(sArr))
			}
		}
	})

	// 5. GET /api/fts/{symbol} -> FtsResponse
	t.Run("FtsAnalysis_BadgeStripAndTrend", func(t *testing.T) {
		path := "/api/fts/" + url.PathEscape(symAdadi01)
		_, body := getReq(t, handler, path)

		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}

		fts, ok := body["fts"].(map[string]any)
		if !ok {
			t.Fatalf("expected fts analysis object, got %T", body["fts"])
		}

		for _, comp := range []string{"trend", "fib", "jet", "choch", "point_hunt", "exit_engine"} {
			if _, exists := fts[comp]; !exists {
				t.Errorf("fts analysis missing component %q", comp)
			}
		}

		if bars, ok := body["bars"].(float64); !ok || bars <= 0 {
			t.Errorf("expected bars > 0, got %v", body["bars"])
		}
		if basis, ok := body["analysis_basis"].(string); !ok || basis == "" {
			t.Errorf("expected non-empty analysis_basis, got %v", body["analysis_basis"])
		}
	})

	// 6. GET /api/calendar/{symbol} -> SymbolPayload
	t.Run("CalendarSymbol_CorporateEvents", func(t *testing.T) {
		path := "/api/calendar/" + url.PathEscape(symAdadi01)
		_, body := getReq(t, handler, path)

		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}

		events, ok := body["events"].([]any)
		if !ok {
			t.Fatalf("expected events array, got %T", body["events"])
		}
		if len(events) == 0 {
			t.Fatalf("expected fixture events for %s", symAdadi01)
		}

		firstEv, ok := events[0].(map[string]any)
		if !ok {
			t.Fatalf("expected event object, got %T", events[0])
		}
		for _, key := range []string{"date", "ts", "title", "cat"} {
			if _, exists := firstEv[key]; !exists {
				t.Errorf("calendar event missing key %q", key)
			}
		}
	})

	// 7. GET /api/calendar/upcoming -> UpcomingPayload
	t.Run("CalendarUpcoming_MarketHorizons", func(t *testing.T) {
		path := "/api/calendar/upcoming?days=30"
		_, body := getReq(t, handler, path)

		if days, ok := body["days"].(float64); !ok || int(days) != 30 {
			t.Errorf("expected days=30, got %v", body["days"])
		}

		items, ok := body["items"].([]any)
		if !ok {
			t.Fatalf("expected items array, got %T", body["items"])
		}
		if len(items) > 0 {
			firstItem, ok := items[0].(map[string]any)
			if !ok {
				t.Fatalf("expected item object, got %T", items[0])
			}
			for _, key := range []string{"symbol", "date", "cat", "title"} {
				if _, exists := firstItem[key]; !exists {
					t.Errorf("upcoming item missing key %q", key)
				}
			}
		}

		if _, ok := body["capital"].([]any); !ok {
			t.Errorf("expected capital events array, got %T", body["capital"])
		}
	})

	// 8. GET /api/fundamental/{symbol} -> FtsCardSchema
	t.Run("FundamentalCard_FiveAxesAndHistory", func(t *testing.T) {
		path := "/api/fundamental/" + url.PathEscape(symAdadi01)
		_, body := getReq(t, handler, path)

		// Strict Zod literal assertion: status MUST be "success"
		if status, ok := body["status"].(string); !ok || status != "success" {
			t.Fatalf("expected status 'success', got %v", body["status"])
		}
		if sym, ok := body["symbol"].(string); !ok || sym != symAdadi01 {
			t.Errorf("expected symbol %q, got %v", symAdadi01, body["symbol"])
		}
		if sec, ok := body["sector"].(string); !ok || sec == "" {
			t.Errorf("expected non-empty sector, got %v", body["sector"])
		}

		// 5 Axes in indicators map
		ind, ok := body["indicators"].(map[string]any)
		if !ok {
			t.Fatalf("expected indicators object, got %T", body["indicators"])
		}
		for _, axisNum := range []string{"1", "2", "3", "4", "5"} {
			if _, exists := ind[axisNum]; !exists {
				t.Errorf("indicators missing axis %q", axisNum)
			}
		}

		// Metrics
		metrics, ok := body["metrics"].(map[string]any)
		if !ok {
			t.Fatalf("expected metrics object, got %T", body["metrics"])
		}
		for _, mKey := range []string{"mcap", "revenue", "gross_margin", "net_margin", "growth_pct"} {
			if _, exists := metrics[mKey]; !exists {
				t.Errorf("metrics missing key %q", mKey)
			}
		}

		// Historical financial statements
		history, ok := body["history"].([]any)
		if !ok || len(history) == 0 {
			t.Fatalf("expected non-empty history array from fixture, got %T", body["history"])
		}
		h0, ok := history[0].(map[string]any)
		if !ok {
			t.Fatalf("expected history row object, got %T", history[0])
		}
		for _, hKey := range []string{"period_end", "revenue", "net_profit", "eps"} {
			if _, exists := h0[hKey]; !exists {
				t.Errorf("history row missing key %q", hKey)
			}
		}
	})

	// 9. GET /api/sync/codal/pipeline -> CodalHealth Payload
	t.Run("CodalPipeline_QueueHealthAndStatus", func(t *testing.T) {
		path := "/api/sync/codal/pipeline"
		_, body := getReq(t, handler, path)

		if status, ok := body["status"].(string); !ok || status != "success" {
			t.Errorf("expected status 'success', got %v", body["status"])
		}

		queue, ok := body["queue"].(map[string]any)
		if !ok {
			t.Fatalf("expected queue object, got %T", body["queue"])
		}
		for _, qKey := range []string{"queued", "running", "done", "total", "retryable"} {
			if _, exists := queue[qKey]; !exists {
				t.Errorf("queue missing key %q", qKey)
			}
		}

		if dirty, ok := body["dirty_symbols"].(float64); !ok || int(dirty) < 0 {
			t.Errorf("expected numeric dirty_symbols, got %v", body["dirty_symbols"])
		}
		if _, ok := body["gap_flag"].(bool); !ok {
			t.Errorf("expected boolean gap_flag, got %T", body["gap_flag"])
		}
		if chk, ok := body["checked_at"].(string); !ok || chk == "" {
			t.Errorf("expected checked_at timestamp, got %v", body["checked_at"])
		}
	})

	// 10. Persian URL Decoding & Non-Existent Fallbacks (Zero Panics)
	t.Run("PersianURLDecodingAndFallbacks", func(t *testing.T) {
		// Verify percent-encoded %D9%81%D9%88%D9%84%D8%A7%D8%AF decodes properly to فولاد
		_, body := getReq(t, handler, "/api/chart-db/%D9%81%D9%88%D9%84%D8%A7%D8%AF")
		if sym, ok := body["symbol"].(string); !ok || sym != symFoolad {
			t.Errorf("r.PathValue failed to decode percent-encoded symbol: expected %q, got %v", symFoolad, body["symbol"])
		}

		// Non-existent symbol fallback (غایب۹۹ / %D8%BA%D8%A7%DB%8C%D8%A8%DB%B9%DB%B9)
		escapedGhayeb := url.PathEscape(symGhayeb)

		// chart-db on empty symbol: 200 with empty candles
		_, bChart := getReq(t, handler, "/api/chart-db/"+escapedGhayeb)
		if cands, ok := bChart["candles"].([]any); !ok || len(cands) != 0 {
			t.Errorf("expected empty candles for non-existent symbol, got %v", bChart["candles"])
		}

		// forecast on empty symbol: 200 without panic
		_, bFc := getReq(t, handler, "/api/chart/"+escapedGhayeb+"/forecast")
		if sym, ok := bFc["symbol"].(string); !ok || sym != symGhayeb {
			t.Errorf("forecast expected symbol %q, got %v", symGhayeb, bFc["symbol"])
		}

		// edge on empty symbol: 200 without panic
		_, bEdge := getReq(t, handler, "/api/chart/"+escapedGhayeb+"/edge")
		if sym, ok := bEdge["symbol"].(string); !ok || sym != symGhayeb {
			t.Errorf("edge expected symbol %q, got %v", symGhayeb, bEdge["symbol"])
		}

		// indicators on empty symbol: 200 without panic
		_, bInd := getReq(t, handler, "/api/chart/"+escapedGhayeb+"/indicators")
		if cnt, ok := bInd["count"].(float64); !ok || cnt != 0 {
			t.Errorf("indicators expected count 0 for empty symbol, got %v", bInd["count"])
		}

		// fts on empty symbol: 200 with status "empty"
		_, bFts := getReq(t, handler, "/api/fts/"+escapedGhayeb)
		if st, ok := bFts["status"].(string); !ok || st != "empty" {
			t.Errorf("fts expected status 'empty' for non-existent symbol, got %v", bFts["status"])
		}

		// calendar on empty symbol: 200 with count 0
		_, bCal := getReq(t, handler, "/api/calendar/"+escapedGhayeb)
		if cnt, ok := bCal["count"].(float64); !ok || cnt != 0 {
			t.Errorf("calendar expected count 0 for non-existent symbol, got %v", bCal["count"])
		}

		// fundamental on non-existent symbol: returns 404 cleanly without 500 panic
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodGet, "/api/fundamental/"+escapedGhayeb, nil)
		req.Header.Set("Accept", "application/json")
		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusNotFound {
			t.Fatalf("expected 404 for non-existent fundamental symbol, got %d. Body: %s", rec.Code, rec.Body.String())
		}
		var errBody map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &errBody); err != nil {
			t.Fatalf("failed to parse 404 JSON response: %v", err)
		}
		if det, ok := errBody["detail"].(string); !ok || det != "Symbol not found" {
			t.Errorf("expected 'Symbol not found' detail, got %v", errBody["detail"])
		}
	})

	// 11. Single-Writer SQLite Guarantees: market.db and codal.db must be strictly read-only
	t.Run("SingleWriterReadOnlyGuarantee", func(t *testing.T) {
		// Attempt write on handles.Market
		_, errM := handles.Market.Exec("INSERT INTO instruments (ins_code) VALUES ('fail_market_writer')")
		if errM == nil {
			t.Fatalf("CRITICAL SECURITY FLAW: write succeeded on read-only market.db handle!")
		}
		errMStr := strings.ToLower(errM.Error())
		if !strings.Contains(errMStr, "readonly") && !strings.Contains(errMStr, "read-only") {
			t.Errorf("expected readonly SQLite error on market.db, got %v", errM)
		}

		// Attempt write on handles.Codal
		if handles.Codal == nil {
			t.Fatalf("handles.Codal was not initialized")
		}
		_, errC := handles.Codal.Exec("INSERT INTO instruments (ins_code) VALUES ('fail_codal_writer')")
		if errC == nil {
			t.Fatalf("CRITICAL SECURITY FLAW: write succeeded on read-only codal.db handle!")
		}
		errCStr := strings.ToLower(errC.Error())
		if !strings.Contains(errCStr, "readonly") && !strings.Contains(errCStr, "read-only") {
			t.Errorf("expected readonly SQLite error on codal.db, got %v", errC)
		}
	})
}
