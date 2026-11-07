package httpapi_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/ftsconfig"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/notifications"
	"borsterminal/backend/internal/screener"
	"borsterminal/backend/internal/watchlist"
)

func setupFunnelUserIntegrationServer(t *testing.T) (http.Handler, *db.Handles, string) {
	t.Helper()
	tempDir := t.TempDir()

	// 1. Copy market.db and user.db fixtures from internal/fundamental/testdata/fixture
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

	// 2. Create codal.db fixture so Handles.Codal is initialized
	{
		codalName := "codal" + ".db"
		src := filepath.Join("..", "fundamental", "testdata", "fixture", "market.db")
		data, err := os.ReadFile(src)
		if err != nil {
			t.Fatalf("read fixture for codal: %v", err)
		}
		targetCodal := filepath.Join(tempDir, codalName)
		if err := os.WriteFile(targetCodal, data, 0o644); err != nil {
			t.Fatalf("write fixture codal: %v", err)
		}
	}

	// 3. Populate initial data for screener and notifications using OpenWritableForTest
	initHandles, err := db.OpenWritableForTest(tempDir)
	if err != nil {
		t.Fatalf("OpenWritableForTest: %v", err)
	}

	_, err = initHandles.Market.Exec(`
		CREATE TABLE IF NOT EXISTS fts_results (
			symbol TEXT PRIMARY KEY,
			score INTEGER,
			verdict TEXT,
			excluded INTEGER,
			exclusion_reasons TEXT,
			f01_growth_pct REAL,
			f01_pass INTEGER,
			f02_pass INTEGER,
			f03_margin_pct REAL,
			f03_pass INTEGER,
			f04_ratio REAL,
			f04_pass INTEGER,
			f05_verdict TEXT,
			f05_pass INTEGER
		);
		CREATE TABLE IF NOT EXISTS codal_notices (
			tracing_no INTEGER PRIMARY KEY,
			symbol TEXT,
			title TEXT,
			publish_date TEXT,
			fetched_at TEXT,
			has_attachment INTEGER,
			letter_code TEXT,
			underlying_name TEXT
		);
		CREATE TABLE IF NOT EXISTS market_watch (
			ins_code TEXT,
			d_even INTEGER
		);
		INSERT OR IGNORE INTO fts_results (
			symbol, score, verdict, excluded, exclusion_reasons,
			f01_growth_pct, f01_pass, f02_pass, f03_margin_pct, f03_pass,
			f04_ratio, f04_pass, f05_verdict, f05_pass
		) VALUES (
			'فولاد', 5, 'پذیرفته', 0, '',
			45.5, 1, 1, 28.0, 1,
			0.45, 1, 'پذیرفته', 1
		);
		INSERT OR IGNORE INTO codal_notices (
			tracing_no, symbol, title, publish_date, fetched_at
		) VALUES (
			987654, 'فولاد', 'گزارش فعالیت ماهانه دوره یک ماهه', '1405/08/10 10:00:00', '2026-11-01T10:00:00'
		);
		INSERT OR IGNORE INTO market_watch (ins_code, d_even) VALUES ('IRO1FOLD0001', 20261102);
	`)
	if err != nil {
		initHandles.Close()
		t.Fatalf("init test tables: %v", err)
	}
	initHandles.Close()

	// 4. Open read-write handles for server
	handles, err := db.Open(tempDir, false)
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	t.Cleanup(func() { handles.Close() })

	// 5. Initialize services
	wlStore, err := watchlist.NewStore(handles.User, tempDir)
	if err != nil {
		t.Fatalf("watchlist.NewStore: %v", err)
	}
	wlHandler := watchlist.NewHandler(wlStore)

	scrSvc := screener.NewService(handles.Market, tempDir)
	ntSvc := notifications.NewService(handles.Market)
	ntHandler := notifications.NewHandler(ntSvc)

	ftsStore, err := ftsconfig.NewStore(handles.User)
	if err != nil {
		t.Fatalf("ftsconfig.NewStore: %v", err)
	}
	ftsHandler := ftsconfig.NewHandler(ftsStore, false)

	cfg := config.Config{
		Addr:     "127.0.0.1:0",
		DataDir:  tempDir,
		ReadOnly: false,
		NoLoops:  true,
	}

	handler := httpapi.NewWithServices(cfg, handles, httpapi.Services{
		Watchlist:     wlHandler,
		Screener:      scrSvc,
		Notifications: ntHandler,
		FtsConfig:     ftsHandler,
	})

	return handler, handles, tempDir
}

func funnelGetReq(t *testing.T, handler http.Handler, path string) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.Header.Set("Accept", "application/json")
	handler.ServeHTTP(rec, req)

	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("GET %s response is not JSON: %v, raw: %s", path, err, rec.Body.String())
	}
	return rec, body
}

func funnelPostReq(t *testing.T, handler http.Handler, path string, payload any) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload for %s: %v", path, err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	handler.ServeHTTP(rec, req)

	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("POST %s response is not JSON: %v, raw: %s", path, err, rec.Body.String())
	}
	return rec, body
}

func funnelDeleteReq(t *testing.T, handler http.Handler, path string) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete, path, nil)
	req.Header.Set("Accept", "application/json")
	handler.ServeHTTP(rec, req)

	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("DELETE %s response is not JSON: %v, raw: %s", path, err, rec.Body.String())
	}
	return rec, body
}

func TestFunnelUserIntegration(t *testing.T) {
	handler, handles, tempDir := setupFunnelUserIntegrationServer(t)

	// 1. Screener endpoint: GET /api/screener
	t.Run("ScreenerCore", func(t *testing.T) {
		rec, body := funnelGetReq(t, handler, "/api/screener")
		if rec.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", rec.Code)
		}
		if status, ok := body["status"].(string); !ok || (status != "success" && status != "ok") {
			t.Errorf("expected status 'success' or 'ok', got %v", body["status"])
		}
		rows, ok := body["data"].([]any)
		if !ok || len(rows) == 0 {
			t.Fatalf("expected non-empty data array in screener, got %v", body["data"])
		}
		row, ok := rows[0].(map[string]any)
		if !ok {
			t.Fatalf("invalid row shape: %v", rows[0])
		}
		if sym, _ := row["symbol"].(string); sym != "فولاد" {
			t.Errorf("expected symbol 'فولاد', got %v", sym)
		}
		if score, ok := row["score"].(float64); !ok || int(score) != 5 {
			t.Errorf("expected score 5, got %v", row["score"])
		}
	})

	// 2. Notifications endpoints: GET /api/notifications/sources & GET /api/notifications/feed
	t.Run("NotificationsFeedAndSources", func(t *testing.T) {
		recSources, bodySources := funnelGetReq(t, handler, "/api/notifications/sources")
		if recSources.Code != http.StatusOK {
			t.Fatalf("expected 200 for /api/notifications/sources, got %d", recSources.Code)
		}
		if status, ok := bodySources["status"].(string); !ok || status != "ok" {
			t.Errorf("expected status 'ok', got %v", bodySources["status"])
		}
		if _, ok := bodySources["sources"]; !ok {
			t.Errorf("expected 'sources' key in response, got %v", bodySources)
		}

		recFeed, bodyFeed := funnelGetReq(t, handler, "/api/notifications/feed")
		if recFeed.Code != http.StatusOK {
			t.Fatalf("expected 200 for /api/notifications/feed, got %d", recFeed.Code)
		}
		if status, ok := bodyFeed["status"].(string); !ok || status != "ok" {
			t.Errorf("expected status 'ok', got %v", bodyFeed["status"])
		}
		items, ok := bodyFeed["items"].([]any)
		if !ok {
			t.Fatalf("expected 'items' array in feed response, got %v", bodyFeed["items"])
		}
		if len(items) == 0 {
			t.Errorf("expected at least 1 item in notifications feed")
		}
	})

	// 3. Watchlist CRUD: GET /api/watchlist, POST /api/watchlist, DELETE /api/watchlist/{symbol}
	t.Run("WatchlistCRUD", func(t *testing.T) {
		// Initial GET
		recGet, bodyGet := funnelGetReq(t, handler, "/api/watchlist")
		if recGet.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", recGet.Code)
		}
		if bodyGet["status"] != "success" {
			t.Errorf("expected status 'success', got %v", bodyGet["status"])
		}
		initialCount := int(bodyGet["count"].(float64))

		// POST: Add symbol
		recPost, bodyPost := funnelPostReq(t, handler, "/api/watchlist", map[string]any{
			"symbol": "رمپنا",
			"name":   "مپنا",
			"note":   "سهم برگزیده",
		})
		if recPost.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", recPost.Code)
		}
		if bodyPost["status"] != "success" {
			t.Fatalf("expected status 'success' on POST, got %+v", bodyPost)
		}
		if int(bodyPost["count"].(float64)) != initialCount+1 {
			t.Errorf("expected count %d, got %v", initialCount+1, bodyPost["count"])
		}

		// Verify via GET
		_, bodyVerify := funnelGetReq(t, handler, "/api/watchlist")
		data := bodyVerify["data"].([]any)
		found := false
		for _, item := range data {
			row := item.(map[string]any)
			if row["symbol"] == "رمپنا" {
				found = true
				if row["name"] != "مپنا" {
					t.Errorf("expected name 'مپنا', got %v", row["name"])
				}
				break
			}
		}
		if !found {
			t.Fatalf("added symbol 'رمپنا' not found in watchlist GET response")
		}

		// DELETE: Remove symbol
		deleteURL := "/api/watchlist/" + url.PathEscape("رمپنا")
		recDel, bodyDel := funnelDeleteReq(t, handler, deleteURL)
		if recDel.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", recDel.Code)
		}
		if bodyDel["status"] != "success" || int(bodyDel["deleted"].(float64)) != 1 {
			t.Errorf("expected deleted=1 on DELETE, got %+v", bodyDel)
		}

		// Verify deletion
		_, bodyAfterDel := funnelGetReq(t, handler, "/api/watchlist")
		if int(bodyAfterDel["count"].(float64)) != initialCount {
			t.Errorf("expected count after delete to be %d, got %v", initialCount, bodyAfterDel["count"])
		}
	})

	// 4. FTS Config Defaults and Roundtrip: GET /api/fts/config & POST /api/fts/config
	t.Run("FtsConfigDefaultsAndRoundtrip", func(t *testing.T) {
		// GET defaults
		recGet, bodyGet := funnelGetReq(t, handler, "/api/fts/config")
		if recGet.Code != http.StatusOK {
			t.Fatalf("expected 200, got %d", recGet.Code)
		}
		if bodyGet["status"] != "success" {
			t.Fatalf("expected status 'success', got %v", bodyGet["status"])
		}
		cfg, ok := bodyGet["config"].(map[string]any)
		if !ok {
			t.Fatalf("expected config map in response, got %v", bodyGet["config"])
		}
		if cfg["growth_min"].(float64) != 40.0 {
			t.Errorf("expected default growth_min 40, got %v", cfg["growth_min"])
		}
		if cfg["industry_mode"].(string) != "Exclude_Mandatory_Pricing" {
			t.Errorf("expected default industry_mode 'Exclude_Mandatory_Pricing', got %v", cfg["industry_mode"])
		}
		if int(cfg["watchlist_max"].(float64)) != 50 {
			t.Errorf("expected default watchlist_max 50, got %v", cfg["watchlist_max"])
		}

		// POST update
		recPost, bodyPost := funnelPostReq(t, handler, "/api/fts/config", map[string]any{
			"growth_min":    58.5,
			"margin_min":    24.0,
			"watchlist_max": 80,
			"industry_mode": "Rank_Only",
		})
		if recPost.Code != http.StatusOK {
			t.Fatalf("expected 200 on POST, got %d", recPost.Code)
		}
		if bodyPost["status"] != "success" || bodyPost["message"] != "saved" {
			t.Fatalf("expected status 'success' and message 'saved', got %+v", bodyPost)
		}
		savedCfg := bodyPost["config"].(map[string]any)
		if savedCfg["growth_min"].(float64) != 58.5 {
			t.Errorf("expected growth_min 58.5, got %v", savedCfg["growth_min"])
		}
		if savedCfg["margin_min"].(float64) != 24.0 {
			t.Errorf("expected margin_min 24, got %v", savedCfg["margin_min"])
		}
		if int(savedCfg["watchlist_max"].(float64)) != 80 {
			t.Errorf("expected watchlist_max 80, got %v", savedCfg["watchlist_max"])
		}
		if savedCfg["industry_mode"].(string) != "Rank_Only" {
			t.Errorf("expected industry_mode 'Rank_Only', got %v", savedCfg["industry_mode"])
		}

		// Verify directly in user.db
		var persistedJSON string
		err := handles.User.QueryRow("SELECT config_json FROM fts_config WHERE id = 1").Scan(&persistedJSON)
		if err != nil {
			t.Fatalf("direct query user.db fts_config: %v", err)
		}
		if !strings.Contains(persistedJSON, "58.5") || !strings.Contains(persistedJSON, "Rank_Only") {
			t.Fatalf("user.db does not contain persisted values: %s", persistedJSON)
		}

		// Subsequent GET returns persisted values
		_, bodyVerify := funnelGetReq(t, handler, "/api/fts/config")
		verifiedCfg := bodyVerify["config"].(map[string]any)
		if verifiedCfg["growth_min"].(float64) != 58.5 {
			t.Errorf("expected verified growth_min 58.5, got %v", verifiedCfg["growth_min"])
		}
		if verifiedCfg["margin_min"].(float64) != 24.0 {
			t.Errorf("expected verified margin_min 24, got %v", verifiedCfg["margin_min"])
		}
	})

	// 5. ReadOnly Guarantees: 403 Forbidden on writes, SQLite read-only mode on market.db and codal.db
	t.Run("ReadOnlyGuarantees", func(t *testing.T) {
		roHandles, err := db.Open(tempDir, true)
		if err != nil {
			t.Fatalf("db.Open readonly: %v", err)
		}
		defer roHandles.Close()

		roWlStore, err := watchlist.NewStore(roHandles.User, tempDir)
		if err != nil {
			t.Fatalf("ro watchlist.NewStore: %v", err)
		}
		roWlHandler := watchlist.NewHandler(roWlStore, true)

		roFtsStore, err := ftsconfig.NewStore(roHandles.User)
		if err != nil {
			t.Fatalf("ro ftsconfig.NewStore: %v", err)
		}
		roFtsHandler := ftsconfig.NewHandler(roFtsStore, true)

		roCfg := config.Config{
			Addr:     "127.0.0.1:0",
			DataDir:  tempDir,
			ReadOnly: true,
			NoLoops:  true,
		}

		roServer := httpapi.NewWithServices(roCfg, roHandles, httpapi.Services{
			Watchlist: roWlHandler,
			FtsConfig: roFtsHandler,
		})

		// POST /api/watchlist must return 403 Forbidden
		recWl, bodyWl := funnelPostReq(t, roServer, "/api/watchlist", map[string]any{
			"symbol": "شستا",
			"name":   "سرمایه گذاری تامین اجتماعی",
		})
		if recWl.Code != http.StatusForbidden {
			t.Errorf("expected 403 Forbidden for POST /api/watchlist in read-only mode, got %d", recWl.Code)
		}
		if bodyWl["status"] != "error" || bodyWl["message"] != "read-only mode" {
			t.Errorf("expected read-only mode error message, got %+v", bodyWl)
		}

		// DELETE /api/watchlist/{symbol} must return 403 Forbidden
		recDel, bodyDel := funnelDeleteReq(t, roServer, "/api/watchlist/فولاد")
		if recDel.Code != http.StatusForbidden {
			t.Errorf("expected 403 Forbidden for DELETE /api/watchlist in read-only mode, got %d", recDel.Code)
		}
		if bodyDel["status"] != "error" || bodyDel["message"] != "read-only mode" {
			t.Errorf("expected read-only mode error message, got %+v", bodyDel)
		}

		// POST /api/fts/config must return 403 Forbidden
		recFts, bodyFts := funnelPostReq(t, roServer, "/api/fts/config", map[string]any{
			"growth_min": 75.0,
		})
		if recFts.Code != http.StatusForbidden {
			t.Errorf("expected 403 Forbidden for POST /api/fts/config in read-only mode, got %d", recFts.Code)
		}
		if bodyFts["status"] != "error" || bodyFts["message"] != "read-only mode" {
			t.Errorf("expected read-only mode error message, got %+v", bodyFts)
		}

		// Single-Writer SQLite guarantee: market.db and codal.db must reject writes
		_, errM := roHandles.Market.Exec("INSERT INTO instruments (l_val18) VALUES ('fail_writer')")
		if errM == nil {
			t.Fatalf("CRITICAL SECURITY FLAW: write succeeded on read-only market.db handle!")
		}
		errMStr := strings.ToLower(errM.Error())
		if !strings.Contains(errMStr, "readonly") && !strings.Contains(errMStr, "read-only") {
			t.Errorf("expected readonly error on market.db, got %v", errM)
		}

		if roHandles.Codal != nil {
			_, errC := roHandles.Codal.Exec("INSERT INTO instruments (l_val18) VALUES ('fail_writer')")
			if errC == nil {
				t.Fatalf("CRITICAL SECURITY FLAW: write succeeded on read-only codal.db handle!")
			}
			errCStr := strings.ToLower(errC.Error())
			if !strings.Contains(errCStr, "readonly") && !strings.Contains(errCStr, "read-only") {
				t.Errorf("expected readonly error on codal.db, got %v", errC)
			}
		}
	})
}
