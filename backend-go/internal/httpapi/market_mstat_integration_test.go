package httpapi_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"borsterminal/backend/internal/chart"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/market"
	"borsterminal/backend/internal/mstat"
)

func setupIntegrationServer(t *testing.T) (http.Handler, *db.Handles, string) {
	t.Helper()
	tempDir := t.TempDir()

	// Copy market.db and user.db fixtures from internal/mstat/testdata/fixture
	for _, fname := range []string{"market.db", "user.db"} {
		src := filepath.Join("..", "mstat", "testdata", "fixture", fname)
		data, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("read fixture %s: %v", fname, err)
		}
		targetPath := filepath.Join(tempDir, fname)
		if err := os.WriteFile(targetPath, data, 0o644); err != nil {
			t.Fatalf("write fixture %s: %v", fname, err)
		}
	}

	// Inject order_book table with 5-level depth into test copy using OpenWritableForTest
	hInit, err := db.OpenWritableForTest(tempDir)
	if err != nil {
		t.Fatalf("OpenWritableForTest failed: %v", err)
	}
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

	// Ensure price_history schema compatibility for MA calculations (last price column)
	_, _ = hInit.Market.Exec(`ALTER TABLE price_history ADD COLUMN last REAL`)
	_, _ = hInit.Market.Exec(`UPDATE price_history SET last = close WHERE last IS NULL`)
	if err := hInit.Close(); err != nil {
		t.Fatalf("close hInit: %v", err)
	}

	// Open read-only handles adhering strictly to Single Writer rules
	handles, err := db.Open(tempDir, true)
	if err != nil {
		t.Fatalf("db.Open failed: %v", err)
	}
	t.Cleanup(func() { handles.Close() })

	// Initialize Market, Mstat, and Chart services
	mSvc := market.NewWithOptions(handles, tempDir, true, true)
	msSvc := mstat.NewWithOptions(handles.Market, tempDir, mSvc, true)
	chSvc := chart.New(chart.Config{
		Market:  handles.Market,
		User:    handles.User,
		DataDir: tempDir,
	})
	t.Cleanup(func() { chSvc.Close() })

	cfg := config.Config{
		Addr:     "127.0.0.1:0",
		DataDir:  tempDir,
		ReadOnly: true,
		NoLoops:  true,
	}

	handler := httpapi.NewWithServices(cfg, handles, httpapi.Services{
		Market: mSvc,
		Mstat:  msSvc,
		Chart:  chSvc,
	})

	return handler, handles, tempDir
}

func getReq(t *testing.T, handler http.Handler, path string) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.Header.Set("Accept", "application/json")
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("%s: expected status 200, got %d. Body: %s", path, rec.Code, rec.Body.String())
	}

	ct := rec.Header().Get("Content-Type")
	if !strings.Contains(ct, "application/json") {
		t.Errorf("%s: expected application/json Content-Type, got %q", path, ct)
	}

	cc := rec.Header().Get("Cache-Control")
	if cc == "" {
		t.Errorf("%s: expected Cache-Control header to be present", path)
	}

	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("%s: failed to parse JSON: %v. Raw body: %s", path, err, rec.Body.String())
	}
	return rec, body
}

func postReq(t *testing.T, handler http.Handler, path string, payload any) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload for %s: %v", path, err)
	}

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("%s: expected status 200, got %d. Body: %s", path, rec.Code, rec.Body.String())
	}

	ct := rec.Header().Get("Content-Type")
	if !strings.Contains(ct, "application/json") {
		t.Errorf("%s: expected application/json Content-Type, got %q", path, ct)
	}

	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("%s: failed to parse JSON: %v. Raw body: %s", path, err, rec.Body.String())
	}
	return rec, body
}

func TestMarketMstatIntegration(t *testing.T) {
	handler, handles, _ := setupIntegrationServer(t)

	// 1. GET /api/market -> MarketFeedSchema
	var boardRev float64
	t.Run("MarketBoard", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/market")
		status, ok := body["status"].(string)
		if !ok || status == "" {
			t.Fatalf("expected string status, got %v", body["status"])
		}

		rawRows, ok := body["data"].([]any)
		if !ok {
			t.Fatalf("expected data array, got %T", body["data"])
		}
		if len(rawRows) == 0 {
			t.Fatalf("expected non-empty data array from fixture")
		}

		firstRow, ok := rawRows[0].(map[string]any)
		if !ok {
			t.Fatalf("expected row to be object, got %T", rawRows[0])
		}
		if sym, ok := firstRow["symbol"].(string); !ok || sym == "" {
			t.Errorf("expected string symbol in row, got %v", firstRow["symbol"])
		}
		if code, ok := firstRow["ins_code"].(string); !ok || code == "" {
			t.Errorf("expected string ins_code in row, got %v", firstRow["ins_code"])
		}

		if revVal, ok := body["rev"].(float64); ok {
			boardRev = revVal
		}
	})

	// 2. GET /api/market/delta -> MarketDeltaSchema (discriminated union)
	t.Run("MarketDelta", func(t *testing.T) {
		// Delta with since=0 (forces full or delta)
		_, bodyZero := getReq(t, handler, "/api/market/delta?since=0")
		statusZero, ok := bodyZero["status"].(string)
		if !ok || (statusZero != "delta" && statusZero != "full" && statusZero != "unchanged") {
			t.Fatalf("expected valid MarketDeltaSchema status union, got %v", bodyZero["status"])
		}

		// Delta with since=current rev (forces unchanged)
		if boardRev >= 0 {
			_, bodyUnchanged := getReq(t, handler, "/api/market/delta?since="+strconv.FormatInt(int64(boardRev), 10))
			statusUnchanged, ok := bodyUnchanged["status"].(string)
			if !ok || (statusUnchanged != "unchanged" && statusUnchanged != "delta" && statusUnchanged != "full") {
				t.Fatalf("expected valid MarketDeltaSchema status, got %v", bodyUnchanged["status"])
			}
			if statusUnchanged != "unchanged" {
				t.Errorf("expected status 'unchanged' when since matches board rev %v, got %s", boardRev, statusUnchanged)
			}
		}
	})

	// 3. GET /api/market/sync-state -> SyncStatePayload
	t.Run("MarketSyncState", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/market/sync-state")
		if body["status"] != "success" {
			t.Errorf("expected status 'success', got %v", body["status"])
		}
		if _, ok := body["running"].(bool); !ok {
			t.Errorf("expected boolean running field, got %T", body["running"])
		}
		if _, ok := body["last"].(map[string]any); !ok {
			t.Errorf("expected last object field, got %T", body["last"])
		}
	})

	// 4. GET /api/tape-history -> TapeHistorySchema
	t.Run("TapeHistory", func(t *testing.T) {
		path := "/api/tape-history?codes=" + url.QueryEscape("INS-\u0639\u0627\u062f\u06cc01") + "&days=6"
		_, body := getReq(t, handler, path)
		if body["status"] != "success" {
			t.Errorf("expected status 'success', got %v", body["status"])
		}
		if _, ok := body["days"].([]any); !ok {
			t.Errorf("expected days array, got %T", body["days"])
		}
		if _, ok := body["flags"].([]any); !ok {
			t.Errorf("expected flags array, got %T", body["flags"])
		}
		if _, ok := body["by_symbol"].(map[string]any); !ok {
			t.Errorf("expected by_symbol map, got %T", body["by_symbol"])
		}
	})

	// 5. GET /api/mstat/market-snapshot -> MarketSnapshotSchema
	t.Run("MstatMarketSnapshot", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/market-snapshot")
		if body["status"] != "ok" {
			t.Fatalf("expected status 'ok', got %v (message: %v)", body["status"], body["message"])
		}
		if idx, ok := body["index"].(map[string]any); ok && idx != nil {
			if _, ok := idx["d_even"].(float64); !ok {
				t.Errorf("expected numeric d_even in index, got %v", idx["d_even"])
			}
		}
	})

	// 6. GET /api/mstat/phase -> PhaseSchema
	t.Run("MstatPhase", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/phase")
		if _, ok := body["status"].(string); !ok {
			t.Errorf("expected status string, got %T", body["status"])
		}
		if _, ok := body["phase"].(string); !ok && body["phase"] != nil {
			t.Errorf("expected phase string or nil, got %T", body["phase"])
		}
		if _, ok := body["label"].(string); !ok && body["label"] != nil {
			t.Errorf("expected label string or nil, got %T", body["label"])
		}
	})

	// 7. GET /api/mstat/industries -> IndustriesSchema
	t.Run("MstatIndustries", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/industries")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
		rows, ok := body["rows"].([]any)
		if !ok {
			t.Fatalf("expected rows array, got %T", body["rows"])
		}
		if len(rows) > 0 {
			firstRow, ok := rows[0].(map[string]any)
			if !ok {
				t.Fatalf("expected row map, got %T", rows[0])
			}
			if _, ok := firstRow["industry"].(string); !ok {
				t.Errorf("expected industry string, got %v", firstRow["industry"])
			}
		}
	})

	// 8. GET /api/mstat/summary
	t.Run("MstatSummary", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/summary")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
	})

	// 9. GET /api/mstat/depth
	t.Run("MstatDepth", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/depth")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
	})

	// 10. GET /api/mstat/clientsplit
	t.Run("MstatClientSplit", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/clientsplit")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
	})

	// 11. GET /api/mstat/smart-money
	t.Run("MstatSmartMoney", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/smart-money")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
		if _, ok := body["macro"].(map[string]any); !ok {
			t.Errorf("expected macro object, got %T", body["macro"])
		}
		if _, ok := body["flow"].(map[string]any); !ok {
			t.Errorf("expected flow object, got %T", body["flow"])
		}
	})

	// 12. GET /api/mstat/phases
	t.Run("MstatPhases", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/phases")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
	})

	// 13. GET /api/mstat/board
	t.Run("MstatBoard", func(t *testing.T) {
		_, body := getReq(t, handler, "/api/mstat/board")
		if body["status"] != "ok" {
			t.Errorf("expected status 'ok', got %v", body["status"])
		}
		for _, key := range []string{"summary", "thermometer", "histogram", "depth", "clientsplit", "mainwatch", "industries"} {
			if _, ok := body[key].(map[string]any); !ok {
				t.Errorf("expected panel %s in board, got %T", key, body[key])
			}
		}
	})

	// 14. GET /api/order-book/{symbol} -> BookSchema (both 5-level and non-existent fallback)
	t.Run("OrderBook_5Levels", func(t *testing.T) {
		path := "/api/order-book/" + url.PathEscape("\u0639\u0627\u062f\u06cc01")
		_, body := getReq(t, handler, path)
		if body["status"] != "ok" {
			t.Fatalf("expected status 'ok', got %v (message: %v)", body["status"], body["message"])
		}
		levels, ok := body["levels"].([]any)
		if !ok || len(levels) != 5 {
			t.Fatalf("expected 5-level order book, got %v levels", len(levels))
		}
		firstLevel, ok := levels[0].(map[string]any)
		if !ok {
			t.Fatalf("expected level object, got %T", levels[0])
		}
		for _, field := range []string{"buy_px", "buy_vol", "buy_cnt", "sell_px", "sell_vol", "sell_cnt"} {
			if _, ok := firstLevel[field].(float64); !ok {
				t.Errorf("expected numeric %s in order book level, got %v", field, firstLevel[field])
			}
		}
	})

	t.Run("OrderBook_NonExistent", func(t *testing.T) {
		path := "/api/order-book/" + url.PathEscape("\u063a\u0627\u06cc\u0628\u06f9\u06f9")
		_, body := getReq(t, handler, path)
		if body["status"] != "no_data" {
			t.Errorf("expected status 'no_data' for non-existent symbol, got %v", body["status"])
		}
		levels, ok := body["levels"].([]any)
		if !ok || len(levels) != 0 {
			t.Errorf("expected empty levels for non-existent symbol, got %v", levels)
		}
	})

	// 15. POST /api/orderbook/watch -> WatchSchema
	t.Run("OrderBookWatch", func(t *testing.T) {
		_, body := postReq(t, handler, "/api/orderbook/watch", map[string]string{
			"ins_code": "INS-\u0639\u0627\u062f\u06cc01",
		})
		if body["status"] != "success" {
			t.Fatalf("expected status 'success', got %v", body["status"])
		}
		subs, ok := body["subscribed"].([]any)
		if !ok || len(subs) == 0 {
			t.Fatalf("expected subscribed list, got %v", body["subscribed"])
		}
	})

	// 16. GET /api/ma/{symbol} -> MaSchema (both existing series and non-existent fallback)
	t.Run("MovingAverages_Existing", func(t *testing.T) {
		path := "/api/ma/" + url.PathEscape("\u0639\u0627\u062f\u06cc01")
		_, body := getReq(t, handler, path)
		if body["status"] != "ok" {
			t.Fatalf("expected status 'ok', got %v (message: %v)", body["status"], body["message"])
		}
		maObj, ok := body["ma"].(map[string]any)
		if !ok {
			t.Fatalf("expected ma object, got %T", body["ma"])
		}
		for _, key := range []string{"ma5", "ma20", "ma50", "ma120"} {
			if _, ok := maObj[key]; !ok {
				t.Errorf("expected %s series in ma object", key)
			}
		}
		if bars, ok := body["bars"].(float64); !ok || bars <= 0 {
			t.Errorf("expected bars > 0, got %v", body["bars"])
		}
	})

	t.Run("MovingAverages_NonExistent", func(t *testing.T) {
		path := "/api/ma/" + url.PathEscape("\u063a\u0627\u06cc\u0628\u06f9\u06f9")
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.Header.Set("Accept", "application/json")
		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("expected status 200 for non-existent symbol, got %d", rec.Code)
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("unmarshal error: %v", err)
		}
		// According to MaSchema: union of ok or error
		if body["status"] != "ok" && body["status"] != "error" {
			t.Errorf("expected status 'ok' or 'error' conforming to MaSchema, got %v", body["status"])
		}
	})

	// Single-Writer SQLite Guarantee: market.db must be strictly read-only
	t.Run("SingleWriterReadOnlyGuarantee", func(t *testing.T) {
		_, err := handles.Market.Exec("INSERT INTO instruments (ins_code) VALUES ('fail_writer')")
		if err == nil {
			t.Fatalf("CRITICAL SECURITY FLAW: write succeeded on read-only market.db handle!")
		}
		errStr := strings.ToLower(err.Error())
		if !strings.Contains(errStr, "readonly") && !strings.Contains(errStr, "read-only") {
			t.Errorf("expected readonly SQLite error, got %v", err)
		}
	})
}
