package main

import (
	"context"
	"database/sql"
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

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
	"borsterminal/backend/internal/tsetmc"
)

func TestE2ESnapshotPipeline(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()
	outDir := filepath.Join(dataDir, "dist", "snapshots")
	if err := os.MkdirAll(outDir, 0755); err != nil {
		t.Fatalf("mkdir outDir: %v", err)
	}

	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	defer marketDB.Close()

	codalPath := filepath.Join(dataDir, "codal.db")
	codalDB, err := db.OpenRWC(codalPath)
	if err != nil {
		t.Fatalf("open codal.db: %v", err)
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
	if err := tsetmc.EnsureClientTypeSchema(marketDB); err != nil {
		t.Fatalf("tsetmc ensure client type schema: %v", err)
	}
	if err := tsetmc.EnsureCorporateSchema(ctx, marketDB); err != nil {
		t.Fatalf("tsetmc ensure corporate schema: %v", err)
	}

	// 2. Seed data: Instruments, Market Watch, Corporate Actions
	mwRows := []tsetmc.MarketWatchRow{
		{InsCode: "1001", DEven: 20261108, PClosing: 5000, PLast: 5050, PriceYesterday: 4950},
		{InsCode: "1002", DEven: 20261108, PClosing: 1200, PLast: 1210, PriceYesterday: 1190},
	}
	instRows := []tsetmc.InstrumentRow{
		{InsCode: "1001", LVal18: "فولاد", LVal30: "فولاد مبارکه", SectorCode: "27", SectorName: "فلزات اساسی", TotalShares: 1000000000},
		{InsCode: "1002", LVal18: "شستا", LVal30: "سرمایه گذاری تامین اجتماعی", SectorCode: "39", SectorName: "سرمایه گذاری", TotalShares: 2000000000},
	}
	if err := tsetmc.IngestMarketWatch(ctx, marketDB, mwRows, instRows); err != nil {
		t.Fatalf("ingest market watch: %v", err)
	}

	paEvents := []tsetmc.PriceAdjustEvent{
		{InsCode: "1001", DEven: 20261015, Symbol: "فولاد", PClosing: 4800, PClosingNotAdjusted: 5000, Ratio: 0.96, Source: "tsetmc"},
	}
	if err := tsetmc.IngestPriceAdjustEvents(ctx, marketDB, paEvents); err != nil {
		t.Fatalf("ingest price adjust: %v", err)
	}

	scEvents := []tsetmc.ShareChangeEvent{
		{InsCode: "1001", DEven: 20260901, Symbol: "فولاد", SharesOld: 800000000, SharesNew: 1000000000, Ratio: 0.8, Source: "tsetmc"},
	}
	if err := tsetmc.IngestShareChangeEvents(ctx, marketDB, scEvents); err != nil {
		t.Fatalf("ingest share change: %v", err)
	}

	// 3. Seed CODAL notices, monthly sales, and financial statements
	seedSQL := `
	INSERT INTO codal_notices (tracing_no, symbol, title, letter_code, sent_date, publish_date)
	VALUES (7001, 'فولاد', 'گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۷/۳۰', 'ن-۳۰', '1405/08/05', '1405/08/05');
	INSERT INTO codal_notices (tracing_no, symbol, title, letter_code, sent_date, publish_date)
	VALUES (7002, 'فولاد', 'اطلاعات و صورت‌های مالی میاندوره‌ای دوره ۶ ماهه منتهی به ۱۴۰۵/۰۶/۳۱', 'ن-۱۰', '1405/07/28', '1405/07/28');

	INSERT INTO monthly_sales (tracing_no, symbol, year, month, monthly_revenue, ytd_revenue, pdf_url)
	VALUES (7001, 'فولاد', 1405, 7, 25000000000, 160000000000, 'https://codal.ir/pdf/1');

	INSERT INTO financial_statements (tracing_no, symbol, period_end, period_months, revenue, gross_profit, operating_profit, net_profit, total_assets, total_liabilities, total_equity, capital, retained_earnings, basic_eps, is_audited, is_consolidated, unit_norm)
	VALUES (7002, 'فولاد', '1405/06/31', 6, 140000000000, 45000000000, 38000000000, 32000000000, 200000000000, 60000000000, 140000000000, 50000000000, 80000000000, 640, 1, 0, 'mrl');
	`
	if _, err := marketDB.Exec(seedSQL); err != nil {
		t.Fatalf("seed codal statements: %v", err)
	}

	// Seed companion codal.db with archive copy
	if _, err := codalDB.Exec(`CREATE TABLE IF NOT EXISTS archive_meta (version TEXT); INSERT INTO archive_meta VALUES ('1.0.95');`); err != nil {
		t.Fatalf("seed codal.db: %v", err)
	}

	// 4. Run FTS Recalculation across the universe
	recalcCount, err := codal.RecalculateAllUniverseFTS(ctx, marketDB)
	if err != nil {
		t.Fatalf("RecalculateAllUniverseFTS failed: %v", err)
	}
	if recalcCount < 1 {
		t.Fatalf("expected at least 1 recalculated FTS result, got %d", recalcCount)
	}

	// Verify FTS result in database
	var ftsScore int
	var ftsVerdict string
	err = marketDB.QueryRow("SELECT score, verdict FROM fts_results WHERE symbol = 'فولاد'").Scan(&ftsScore, &ftsVerdict)
	if err != nil {
		t.Fatalf("query fts_results for فولاد: %v", err)
	}
	if ftsVerdict == "" {
		t.Errorf("expected non-empty verdict for فولاد, score=%d", ftsScore)
	}

	// 5. Build Snapshot Set
	snapshotSetID := "20261108T120000Z-e2eprod01"
	dbMap := map[string]*sql.DB{
		"market": marketDB,
		"codal":  codalDB,
	}
	manifest, err := snapshot.BuildSnapshotSet(ctx, dbMap, outDir, snapshotSetID)
	if err != nil {
		t.Fatalf("BuildSnapshotSet failed: %v", err)
	}
	if manifest.SnapshotSetID != snapshotSetID {
		t.Fatalf("expected SnapshotSetID %s, got %s", snapshotSetID, manifest.SnapshotSetID)
	}
	if len(manifest.Assets) != 2 {
		t.Fatalf("expected 2 assets (market and codal), got %d", len(manifest.Assets))
	}

	// Verify compressed files exist
	marketLZMA := filepath.Join(outDir, "market.db.lzma")
	codalLZMA := filepath.Join(outDir, "codal.db.lzma")
	manifestJSON := filepath.Join(outDir, "manifest.json")
	for _, p := range []string{marketLZMA, codalLZMA, manifestJSON} {
		if fi, err := os.Stat(p); err != nil || fi.Size() == 0 {
			t.Fatalf("expected non-empty snapshot file at %s: %v", p, err)
		}
	}

	// 6. Generate Minisign Key Pair & Sign Assets and Manifest
	pubStr, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	manifestSig, err := snapshot.SignAsset(manifestJSON, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset manifest failed: %v", err)
	}
	if _, err := os.Stat(manifestSig); err != nil {
		t.Fatalf("manifest sig missing: %v", err)
	}

	marketSig, err := snapshot.SignAsset(marketLZMA, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset market failed: %v", err)
	}
	codalSig, err := snapshot.SignAsset(codalLZMA, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset codal failed: %v", err)
	}

	// Verify Minisign signatures locally
	for _, pair := range [][2]string{
		{manifestJSON, manifestSig},
		{marketLZMA, marketSig},
		{codalLZMA, codalSig},
	} {
		if err := snapshot.VerifyAsset(pair[0], pair[1], pubStr); err != nil {
			t.Fatalf("VerifyAsset failed for %s: %v", pair[0], err)
		}
	}

	// 7. Mock GitHub Release Publisher & Verify Strict Publication Order
	var uploadOrderMu sync.Mutex
	var uploadOrder []string
	var nextAssetID int64 = 100

	releaseServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uploadOrderMu.Lock()
		defer uploadOrderMu.Unlock()

		// 1. GET /repos/{owner}/{repo}/releases/tags/{tag}
		if r.Method == http.MethodGet && strings.Contains(r.URL.Path, "/releases/tags/") {
			w.Header().Set("Content-Type", "application/vnd.github+json")
			w.WriteHeader(http.StatusNotFound)
			_, _ = w.Write([]byte(`{"message": "Not Found"}`))
			return
		}

		// 2. POST /repos/{owner}/{repo}/releases
		if r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/releases") {
			w.Header().Set("Content-Type", "application/vnd.github+json")
			w.WriteHeader(http.StatusCreated)
			uploadBase := fmt.Sprintf("/repos/johnwarchief/BorsTerminal/releases/42/assets{?name,label}")
			_, _ = w.Write([]byte(fmt.Sprintf(`{"id": 42, "tag_name": "data-snapshot", "upload_url": %q, "assets": []}`, uploadBase)))
			return
		}

		// 3. POST upload asset: /repos/.../assets?name={name}
		if r.Method == http.MethodPost && strings.Contains(r.URL.Path, "/assets") {
			name := r.URL.Query().Get("name")
			if name == "" {
				http.Error(w, `{"message": "missing name query parameter"}`, http.StatusBadRequest)
				return
			}
			_, _ = io.ReadAll(r.Body)
			nextAssetID++
			assetID := nextAssetID
			uploadOrder = append(uploadOrder, name)

			w.Header().Set("Content-Type", "application/vnd.github+json")
			w.WriteHeader(http.StatusCreated)
			downloadURL := fmt.Sprintf("/download/%s", url.PathEscape(name))
			_, _ = w.Write([]byte(fmt.Sprintf(`{"id": %d, "name": %q, "browser_download_url": %q, "state": "uploaded"}`, assetID, name, downloadURL)))
			return
		}

		// 4. GET /download/{name} or GET /repos/.../releases/assets/{id} (asset verification)
		if r.Method == http.MethodGet && (strings.HasPrefix(r.URL.Path, "/download/") || strings.Contains(r.URL.Path, "/releases/assets/")) {
			w.Header().Set("Content-Type", "application/octet-stream")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("OK"))
			return
		}

		// 5. DELETE asset
		if r.Method == http.MethodDelete && strings.Contains(r.URL.Path, "/releases/assets/") {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		http.Error(w, fmt.Sprintf("unhandled request: %s %s", r.Method, r.URL.Path), http.StatusNotFound)
	}))
	defer releaseServer.Close()

	// Verify publication ordering principle:
	// All data assets (.db.lzma, .db.lzma.sig) MUST be uploaded and verified before manifest.json
	uploadOrderMu.Lock()
	uploadOrder = nil
	uploadOrderMu.Unlock()

	err = snapshot.PublishSnapshotSet(ctx, releaseServer.Client(), "mock-token", "johnwarchief", "BorsTerminal", "data-snapshot", outDir, manifest, privStr, "", releaseServer.URL)
	if err != nil {
		t.Fatalf("PublishSnapshotSet failed: %v", err)
	}

	uploadOrderMu.Lock()
	finalOrder := append([]string(nil), uploadOrder...)
	uploadOrderMu.Unlock()

	expectedDataFiles := []string{"market.db.lzma", "market.db.lzma.sig", "codal.db.lzma", "codal.db.lzma.sig"}
	manifestFiles := []string{"manifest.json", "manifest.json.sig"}

	// Verify all expected data files were uploaded
	for _, df := range expectedDataFiles {
		found := false
		for _, up := range finalOrder {
			if up == df {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("expected data asset %s in uploadOrder, got: %v", df, finalOrder)
		}
	}

	// Verify manifest files were uploaded
	for _, mf := range manifestFiles {
		found := false
		for _, up := range finalOrder {
			if up == mf {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("expected manifest asset %s in uploadOrder, got: %v", mf, finalOrder)
		}
	}

	// Strict publication consistency: all data assets and signatures must appear BEFORE manifest.json and manifest.json.sig
	var lastDataIdx = -1
	var firstManifestIdx = len(finalOrder)

	for i, f := range finalOrder {
		for _, df := range expectedDataFiles {
			if f == df && i > lastDataIdx {
				lastDataIdx = i
			}
		}
		for _, mf := range manifestFiles {
			if f == mf && i < firstManifestIdx {
				firstManifestIdx = i
			}
		}
	}

	if lastDataIdx >= firstManifestIdx {
		t.Fatalf("consistency ordering violation: data asset uploaded at index %d after manifest at %d (order: %v)", lastDataIdx, firstManifestIdx, finalOrder)
	}

	// 8. Test Idempotency: re-running snapshot generation on same DB produces consistent set
	manifest2, err := snapshot.BuildSnapshotSet(ctx, dbMap, outDir, snapshotSetID)
	if err != nil {
		t.Fatalf("second BuildSnapshotSet failed: %v", err)
	}
	if manifest2.SnapshotSetID != manifest.SnapshotSetID {
		t.Errorf("expected matching snapshot set IDs, got %s vs %s", manifest.SnapshotSetID, manifest2.SnapshotSetID)
	}
	if len(manifest2.Assets) != len(manifest.Assets) {
		t.Errorf("asset count mismatch on second run: %d vs %d", len(manifest2.Assets), len(manifest.Assets))
	}

	// Verify that loading manifest matches expected JSON
	loadedManifest, err := snapshot.LoadManifest(manifestJSON)
	if err != nil {
		t.Fatalf("LoadManifest failed: %v", err)
	}
	if loadedManifest.SnapshotSetID != snapshotSetID {
		t.Errorf("loaded manifest ID mismatch: %s", loadedManifest.SnapshotSetID)
	}
}

// TestE2ESnapshotPipeline_FailureScenarios systematically tests publication failures:
// asset upload error, manifest upload error, API failure, corrupt keys, and context cancellation.
func TestE2ESnapshotPipeline_FailureScenarios(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()
	outDir := filepath.Join(dataDir, "dist", "snapshots")
	if err := os.MkdirAll(outDir, 0755); err != nil {
		t.Fatalf("mkdir outDir: %v", err)
	}

	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	defer marketDB.Close()
	if _, err := marketDB.Exec("CREATE TABLE t (id INT); INSERT INTO t VALUES (1);"); err != nil {
		t.Fatalf("seed dummy db: %v", err)
	}

	dbMap := map[string]*sql.DB{"market": marketDB}
	manifest, err := snapshot.BuildSnapshotSet(ctx, dbMap, outDir, "fail-test-gen")
	if err != nil {
		t.Fatalf("BuildSnapshotSet failed: %v", err)
	}

	_, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	// 1. Failure Scenario: Asset Upload Failure (HTTP 500)
	t.Run("AssetUploadFailure", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if strings.Contains(r.URL.Path, "/releases/tags/") {
				w.WriteHeader(http.StatusNotFound)
				return
			}
			if strings.HasSuffix(r.URL.Path, "/releases") {
				w.WriteHeader(http.StatusCreated)
				_, _ = w.Write([]byte(`{"id": 1, "upload_url": "/assets{?name,label}"}`))
				return
			}
			if strings.Contains(r.URL.Path, "/assets") {
				// Inject 500 error on asset upload
				http.Error(w, "internal server error during asset upload", http.StatusInternalServerError)
				return
			}
		}))
		defer server.Close()

		err := snapshot.PublishSnapshotSet(ctx, server.Client(), "tok", "owner", "repo", "v1", outDir, manifest, privStr, "", server.URL)
		if err == nil {
			t.Fatal("expected PublishSnapshotSet to fail on asset upload error, got nil")
		}
		if !strings.Contains(err.Error(), "upload") {
			t.Logf("expected upload error message, got: %v", err)
		}
	})

	// 2. Failure Scenario: Manifest Upload Failure (HTTP 500 on manifest.json)
	t.Run("ManifestUploadFailure", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if strings.Contains(r.URL.Path, "/releases/tags/") {
				w.WriteHeader(http.StatusNotFound)
				return
			}
			if strings.HasSuffix(r.URL.Path, "/releases") {
				w.WriteHeader(http.StatusCreated)
				_, _ = w.Write([]byte(`{"id": 2, "upload_url": "/assets{?name,label}"}`))
				return
			}
			if strings.Contains(r.URL.Path, "/assets") {
				name := r.URL.Query().Get("name")
				if strings.HasPrefix(name, "manifest.json") {
					http.Error(w, "manifest upload failed disk full", http.StatusInternalServerError)
					return
				}
				w.WriteHeader(http.StatusCreated)
				_, _ = w.Write([]byte(fmt.Sprintf(`{"id": 10, "name": %q, "browser_download_url": "/download/%s"}`, name, name)))
				return
			}
			if strings.HasPrefix(r.URL.Path, "/download/") {
				w.WriteHeader(http.StatusOK)
				return
			}
		}))
		defer server.Close()

		err := snapshot.PublishSnapshotSet(ctx, server.Client(), "tok", "owner", "repo", "v1", outDir, manifest, privStr, "", server.URL)
		if err == nil {
			t.Fatal("expected PublishSnapshotSet to fail on manifest upload error, got nil")
		}
	})

	// 3. Failure Scenario: Invalid API Response (HTTP 502 Bad Gateway on Release creation)
	t.Run("InvalidAPIResponse", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			http.Error(w, "Bad Gateway from upstream", http.StatusBadGateway)
		}))
		defer server.Close()

		err := snapshot.PublishSnapshotSet(ctx, server.Client(), "tok", "owner", "repo", "v1", outDir, manifest, privStr, "", server.URL)
		if err == nil {
			t.Fatal("expected PublishSnapshotSet to fail on invalid API response, got nil")
		}
	})

	// 4. Failure Scenario: Corrupt Signing Key
	t.Run("CorruptSigningKey", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
		defer server.Close()

		err := snapshot.PublishSnapshotSet(ctx, server.Client(), "tok", "owner", "repo", "v1", outDir, manifest, "invalid-private-key-string", "", server.URL)
		if err == nil {
			t.Fatal("expected PublishSnapshotSet to fail with invalid signing key, got nil")
		}
	})

	// 5. Failure Scenario: Context Cancellation
	t.Run("ContextCancelled", func(t *testing.T) {
		cancelCtx, cancel := context.WithCancel(ctx)
		cancel() // Cancel immediately

		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
		defer server.Close()

		err := snapshot.PublishSnapshotSet(cancelCtx, server.Client(), "tok", "owner", "repo", "v1", outDir, manifest, privStr, "", server.URL)
		if err == nil {
			t.Fatal("expected PublishSnapshotSet to fail on cancelled context, got nil")
		}
	})
}
