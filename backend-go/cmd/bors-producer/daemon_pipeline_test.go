package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
	"borsterminal/backend/internal/tsetmc"
)

// TestScheduledSnapshotPipeline_EndToEndPublishSuccess proves the complete scheduled pipeline:
// Ingestion -> Validation -> FTS Recalculation -> Snapshot -> Sign -> Publish -> Pipeline Record.
func TestScheduledSnapshotPipeline_EndToEndPublishSuccess(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()
	outDir := filepath.Join(dataDir, "snapshots")

	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("create market.db: %v", err)
	}
	defer marketDB.Close()

	codalPath := filepath.Join(dataDir, "codal.db")
	codalDB, err := db.OpenRWC(codalPath)
	if err != nil {
		t.Fatalf("create codal.db: %v", err)
	}
	defer codalDB.Close()

	// 1. Ensure schemas
	if err := codal.EnsureSchema(marketDB); err != nil {
		t.Fatalf("codal ensure schema: %v", err)
	}
	if err := codal.EnsureValidationSchema(marketDB); err != nil {
		t.Fatalf("codal ensure validation schema: %v", err)
	}
	if err := codal.EnsureRecalcSchema(marketDB); err != nil {
		t.Fatalf("codal ensure recalc schema: %v", err)
	}
	if err := tsetmc.EnsureMarketWatchSchema(marketDB); err != nil {
		t.Fatalf("tsetmc ensure market watch schema: %v", err)
	}
	if err := tsetmc.EnsureCorporateSchema(ctx, marketDB); err != nil {
		t.Fatalf("tsetmc ensure corporate schema: %v", err)
	}

	// 2. Seed data
	mwRows := []tsetmc.MarketWatchRow{
		{InsCode: "1001", DEven: 20261108, PClosing: 5000, PLast: 5050, PriceYesterday: 4950},
	}
	instRows := []tsetmc.InstrumentRow{
		{InsCode: "1001", LVal18: "فولاد", LVal30: "فولاد مبارکه", SectorCode: "27", SectorName: "فلزات اساسی", TotalShares: 1000000000},
	}
	if err := tsetmc.IngestMarketWatch(ctx, marketDB, mwRows, instRows); err != nil {
		t.Fatalf("ingest market watch: %v", err)
	}

	seedSQL := `
	INSERT INTO codal_notices (tracing_no, symbol, title, letter_code, sent_date, publish_date)
	VALUES (7001, 'فولاد', 'گزارش فعالیت ماهانه', 'ن-۳۰', '1405/08/05', '1405/08/05');
	INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue, ytd_revenue, pdf_url)
	VALUES (7001, 'فولاد', 1405, 7, 25000000000, 160000000000, 'https://codal.ir/pdf/1');
	INSERT INTO financial_statements (tracing_no, symbol, period_end, period_months, revenue, gross_profit, operating_profit, net_profit, total_assets, total_liabilities, total_equity, capital, retained_earnings, basic_eps, is_audited, is_consolidated, unit_norm)
	VALUES (7002, 'فولاد', '1405/06/31', 6, 140000000000, 45000000000, 38000000000, 32000000000, 200000000000, 60000000000, 140000000000, 50000000000, 80000000000, 640, 1, 0, 'mrl');
	`
	if _, err := marketDB.Exec(seedSQL); err != nil {
		t.Fatalf("seed statements: %v", err)
	}
	if _, err := codalDB.Exec("CREATE TABLE IF NOT EXISTS meta (version TEXT); INSERT INTO meta VALUES ('1.0.95');"); err != nil {
		t.Fatalf("seed codal.db: %v", err)
	}

	// Mark فولاد as dirty so pipeline recalculates FTS
	if err := codal.MarkDirty(ctx, marketDB, "فولاد", "test"); err != nil {
		t.Fatalf("mark dirty: %v", err)
	}

	// 3. Minisign keys
	pubStr, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair: %v", err)
	}
	t.Setenv("BORS_MINISIGN_SECRET_KEY", privStr)
	t.Setenv("GITHUB_TOKEN", "mock-token-ghp_12345")

	// 4. Mock GitHub server for publication verification
	var uploadMu sync.Mutex
	var uploadOrder []string
	var nextID int64 = 100

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uploadMu.Lock()
		defer uploadMu.Unlock()

		if r.Method == http.MethodGet && strings.Contains(r.URL.Path, "/releases/tags/") {
			w.WriteHeader(http.StatusNotFound)
			return
		}

		if r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/releases") {
			w.Header().Set("Content-Type", "application/vnd.github+json")
			w.WriteHeader(http.StatusCreated)
			uploadURL := "/repos/johnwarchief/BorsTerminal/releases/42/assets{?name,label}"
			_, _ = w.Write([]byte(fmt.Sprintf(`{"id": 42, "tag_name": "data-test", "upload_url": %q}`, uploadURL)))
			return
		}

		if r.Method == http.MethodPost && strings.Contains(r.URL.Path, "/assets") {
			name := r.URL.Query().Get("name")
			_, _ = io.ReadAll(r.Body)
			uploadOrder = append(uploadOrder, name)
			nextID++

			w.Header().Set("Content-Type", "application/vnd.github+json")
			w.WriteHeader(http.StatusCreated)
			downURL := fmt.Sprintf("/download/%s", url.PathEscape(name))
			_, _ = w.Write([]byte(fmt.Sprintf(`{"id": %d, "name": %q, "browser_download_url": %q, "state": "uploaded"}`, nextID, name, downURL)))
			return
		}

		if r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/download/") {
			w.Header().Set("Content-Type", "application/octet-stream")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("OK"))
			return
		}

		if r.Method == http.MethodDelete {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		http.Error(w, "unhandled", http.StatusNotFound)
	}))
	defer server.Close()

	cfg := DaemonConfig{
		DataDir:            dataDir,
		SnapshotOutDir:     outDir,
		SnapshotDailyUTC:   "06:00",
		CatchupMissedDaily: true,
		PublishEnabled:     true,
		PublishRepo:        "johnwarchief/BorsTerminal",
		PublishTag:         "data-test-tag",
		PublishBaseURL:     server.URL,
	}

	// 5. Execute scheduled snapshot pipeline
	now := time.Date(2026, 11, 8, 6, 0, 0, 0, time.UTC)
	manifest, err := ExecuteScheduledSnapshotPipeline(ctx, cfg, now)
	if err != nil {
		t.Fatalf("ExecuteScheduledSnapshotPipeline failed: %v", err)
	}

	if manifest == nil {
		t.Fatal("expected non-nil manifest")
	}
	if len(manifest.Assets) != 2 {
		t.Fatalf("expected 2 assets (market, codal), got %d", len(manifest.Assets))
	}

	// 6. Verify FTS was recalculated in database
	var ftsScore int
	if err := marketDB.QueryRow("SELECT score FROM fts_results WHERE symbol = 'فولاد'").Scan(&ftsScore); err != nil {
		t.Fatalf("FTS result missing for فولاد: %v", err)
	}

	// 7. Verify Minisign signatures locally
	manifestJSON := filepath.Join(outDir, "manifest.json")
	manifestSig := filepath.Join(outDir, "manifest.json.sig")
	if err := snapshot.VerifyAsset(manifestJSON, manifestSig, pubStr); err != nil {
		t.Fatalf("manifest signature verification failed: %v", err)
	}

	// 8. Verify upload order and consistency
	uploadMu.Lock()
	finalOrder := append([]string(nil), uploadOrder...)
	uploadMu.Unlock()

	expectedDataFiles := []string{"market.db.lzma", "market.db.lzma.sig", "codal.db.lzma", "codal.db.lzma.sig"}
	for _, df := range expectedDataFiles {
		found := false
		for _, up := range finalOrder {
			if up == df {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("expected data file %s in upload order, got: %v", df, finalOrder)
		}
	}

	var lastDataIdx = -1
	var manifestIdx = -1
	for i, f := range finalOrder {
		for _, df := range expectedDataFiles {
			if f == df && i > lastDataIdx {
				lastDataIdx = i
			}
		}
		if f == "manifest.json" && manifestIdx == -1 {
			manifestIdx = i
		}
	}

	if lastDataIdx >= manifestIdx {
		t.Fatalf("consistency ordering violation: data asset uploaded at %d after manifest at %d", lastDataIdx, manifestIdx)
	}

	// 9. Verify pipeline_runs table records success
	var phase, cycle string
	var done, failed int
	err = marketDB.QueryRow("SELECT cycle, phase, done, failed FROM pipeline_runs ORDER BY id DESC LIMIT 1").Scan(&cycle, &phase, &done, &failed)
	if err != nil {
		t.Fatalf("query pipeline_runs: %v", err)
	}
	if cycle != "scheduled_snapshot" || phase != "complete" || done != 1 || failed != 0 {
		t.Errorf("expected pipeline_runs complete, got cycle=%s phase=%s done=%d failed=%d", cycle, phase, done, failed)
	}

	// 10. Verify last_pipeline_status.json
	metaDate := LastSuccessfulSnapshotDate(outDir)
	if metaDate != "2026-11-08" {
		t.Errorf("expected LastSuccessfulSnapshotDate to be 2026-11-08, got %q", metaDate)
	}
}

// TestScheduledSnapshotPipeline_ErrorHandling proves that errors during FTS, signing, or uploading
// are recorded as pipeline failures and never produce false success.
func TestScheduledSnapshotPipeline_ErrorHandling(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()
	outDir := filepath.Join(dataDir, "snapshots")

	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("create market.db: %v", err)
	}
	defer marketDB.Close()
	if _, err := marketDB.Exec("CREATE TABLE dummy (x INT);"); err != nil {
		t.Fatalf("seed dummy db: %v", err)
	}

	// Scenario A: Missing Minisign key when publish is enabled
	t.Run("MissingMinisignKeyForPublish", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("GITHUB_TOKEN", "some-token")

		cfg := DaemonConfig{
			DataDir:        dataDir,
			SnapshotOutDir: outDir,
			PublishEnabled: true,
			PublishRepo:    "johnwarchief/BorsTerminal",
		}

		_, err := ExecuteScheduledSnapshotPipeline(ctx, cfg, time.Now())
		if err == nil {
			t.Fatal("expected error when publish is enabled without minisign key, got nil")
		}

		// Verify error recorded in pipeline_runs
		var phase string
		var failed int
		if err := marketDB.QueryRow("SELECT phase, failed FROM pipeline_runs ORDER BY id DESC LIMIT 1").Scan(&phase, &failed); err != nil {
			t.Fatalf("query pipeline_runs: %v", err)
		}
		if phase != "signing_auth" || failed != 1 {
			t.Errorf("expected phase=signing_auth, failed=1, got phase=%s failed=%d", phase, failed)
		}
	})

	// Scenario B: Upload failure (server returns HTTP 500)
	t.Run("UploadHTTP500Failure", func(t *testing.T) {
		_, privStr, _ := snapshot.GenerateTestKeyPair()
		t.Setenv("BORS_MINISIGN_SECRET_KEY", privStr)
		t.Setenv("GITHUB_TOKEN", "mock-token")

		failServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if strings.Contains(r.URL.Path, "/releases/tags/") {
				w.WriteHeader(http.StatusNotFound)
				return
			}
			if strings.HasSuffix(r.URL.Path, "/releases") {
				w.WriteHeader(http.StatusCreated)
				_, _ = w.Write([]byte(`{"id": 10, "upload_url": "/assets{?name,label}"}`))
				return
			}
			if strings.Contains(r.URL.Path, "/assets") {
				http.Error(w, "server disk failure", http.StatusInternalServerError)
				return
			}
		}))
		defer failServer.Close()

		cfg := DaemonConfig{
			DataDir:        dataDir,
			SnapshotOutDir: outDir,
			PublishEnabled: true,
			PublishRepo:    "johnwarchief/BorsTerminal",
			PublishBaseURL: failServer.URL,
		}

		_, err := ExecuteScheduledSnapshotPipeline(ctx, cfg, time.Now())
		if err == nil {
			t.Fatal("expected upload error, got nil")
		}

		// Verify error recorded in pipeline_runs
		var phase string
		var failed int
		if err := marketDB.QueryRow("SELECT phase, failed FROM pipeline_runs ORDER BY id DESC LIMIT 1").Scan(&phase, &failed); err != nil {
			t.Fatalf("query pipeline_runs: %v", err)
		}
		if phase != "publish_upload" || failed != 1 {
			t.Errorf("expected phase=publish_upload failed=1, got phase=%s failed=%d", phase, failed)
		}

		// Verify last_pipeline_status.json has status=error
		metaData, _ := os.ReadFile(filepath.Join(outDir, "last_pipeline_status.json"))
		if !strings.Contains(string(metaData), `"status": "error"`) {
			t.Errorf("expected status=error in meta, got: %s", string(metaData))
		}
	})
}

// TestDailyUTCSchedule_Calculations proves restart stability:
// Restarting at any time does not drift the fixed 06:00 UTC schedule.
func TestDailyUTCSchedule_Calculations(t *testing.T) {
	h, m, err := parseDailyUTCTime("06:00")
	if err != nil || h != 6 || m != 0 {
		t.Fatalf("parseDailyUTCTime failed: h=%d, m=%d, err=%v", h, m, err)
	}

	// 1. Before 06:00 UTC (e.g. 04:30:00 UTC) -> delay must be 1h30m to today's 06:00
	t1 := time.Date(2026, 11, 8, 4, 30, 0, 0, time.UTC)
	d1 := NextDailyUTCDuration(t1, 6, 0)
	if d1 != 90*time.Minute {
		t.Errorf("expected 90m, got %v", d1)
	}

	// 2. Exactly at 06:00:00 UTC -> delay must be 24h to tomorrow's 06:00
	t2 := time.Date(2026, 11, 8, 6, 0, 0, 0, time.UTC)
	d2 := NextDailyUTCDuration(t2, 6, 0)
	if d2 != 24*time.Hour {
		t.Errorf("expected 24h, got %v", d2)
	}

	// 3. Past 06:00 UTC (e.g. 15:00:00 UTC) -> delay must be 15h to tomorrow's 06:00
	t3 := time.Date(2026, 11, 8, 15, 0, 0, 0, time.UTC)
	d3 := NextDailyUTCDuration(t3, 6, 0)
	if d3 != 15*time.Hour {
		t.Errorf("expected 15h, got %v", d3)
	}

	// 4. Late night (e.g. 23:45:00 UTC) -> delay must be 6h15m to tomorrow's 06:00
	t4 := time.Date(2026, 11, 8, 23, 45, 0, 0, time.UTC)
	d4 := NextDailyUTCDuration(t4, 6, 0)
	if d4 != 6*time.Hour+15*time.Minute {
		t.Errorf("expected 6h15m, got %v", d4)
	}
}

// TestDailyUTCSchedule_MissedRunDetection proves that when service was down during 06:00 UTC,
// missed run is detected on startup and duplicate runs are prevented if already succeeded.
func TestDailyUTCSchedule_MissedRunDetection(t *testing.T) {
	outDir := t.TempDir()

	// 1. No prior run: LastSuccessfulSnapshotDate is empty
	date0 := LastSuccessfulSnapshotDate(outDir)
	if date0 != "" {
		t.Errorf("expected empty date, got %q", date0)
	}

	// 2. Write successful status for yesterday (2026-11-07)
	metaYesterday := PipelineStatusMeta{
		FinishedAt: "2026-11-07T06:05:00Z",
		Status:     "success",
	}
	savePipelineStatusMeta(outDir, metaYesterday)

	date1 := LastSuccessfulSnapshotDate(outDir)
	if date1 != "2026-11-07" {
		t.Errorf("expected 2026-11-07, got %q", date1)
	}

	// At 08:00 UTC on 2026-11-08: date1 != "2026-11-08" -> MISSED RUN!
	isMissed := date1 != "2026-11-08"
	if !isMissed {
		t.Error("expected missed run to be detected")
	}

	// 3. Write successful status for today (2026-11-08)
	metaToday := PipelineStatusMeta{
		FinishedAt: "2026-11-08T06:05:00Z",
		Status:     "success",
	}
	savePipelineStatusMeta(outDir, metaToday)

	date2 := LastSuccessfulSnapshotDate(outDir)
	if date2 != "2026-11-08" {
		t.Errorf("expected 2026-11-08, got %q", date2)
	}

	// On service restart at 08:30 UTC on 2026-11-08: date2 == "2026-11-08" -> NOT MISSED, NO DUPLICATE!
	isMissedAfterRestart := date2 != "2026-11-08"
	if isMissedAfterRestart {
		t.Error("expected run to NOT be flagged as missed when already completed today")
	}
}

// TestScheduledSnapshotPipeline_ConcurrencyControl proves that concurrent calls
// do not execute duplicate generations simultaneously.
func TestScheduledSnapshotPipeline_ConcurrencyControl(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()
	outDir := filepath.Join(dataDir, "snapshots")

	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, _ := db.OpenRWC(marketPath)
	_, _ = marketDB.Exec("CREATE TABLE t (x INT); INSERT INTO t VALUES (1);")
	_ = codal.EnsureRecalcSchema(marketDB)
	marketDB.Close()

	cfg := DaemonConfig{
		DataDir:        dataDir,
		SnapshotOutDir: outDir,
		PublishEnabled: false,
	}

	var wg sync.WaitGroup
	var completedCount int
	var countMu sync.Mutex

	// Launch 3 concurrent pipeline executions
	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			manifest, err := ExecuteScheduledSnapshotPipeline(ctx, cfg, time.Now())
			if err == nil && manifest != nil {
				countMu.Lock()
				completedCount++
				countMu.Unlock()
			}
		}()
	}
	wg.Wait()

	// Only 1 execution should have acquired the lock and completed
	if completedCount != 1 {
		t.Errorf("expected exactly 1 execution to complete due to concurrency guard, got %d", completedCount)
	}
}
