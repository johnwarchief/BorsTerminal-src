package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
	"borsterminal/backend/internal/tsetmc"
)

func TestCLIRouting(t *testing.T) {
	ctx := context.Background()

	t.Run("NoArgs_ShowsHelp", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{}, &stdout, &stderr)
		if code != 0 {
			t.Fatalf("expected code 0, got %d", code)
		}
		if !strings.Contains(stdout.String(), "bors-producer - High-performance data producer CLI") {
			t.Errorf("stdout does not contain usage header: %s", stdout.String())
		}
	})

	t.Run("HelpFlag_ShowsHelp", func(t *testing.T) {
		for _, flag := range []string{"help", "-h", "--help"} {
			var stdout, stderr bytes.Buffer
			code := Run(ctx, []string{flag}, &stdout, &stderr)
			if code != 0 {
				t.Fatalf("flag %s: expected code 0, got %d", flag, code)
			}
			if !strings.Contains(stdout.String(), "Available Commands:") {
				t.Errorf("flag %s: stdout does not contain usage: %s", flag, stdout.String())
			}
		}
	})

	t.Run("VersionFlag_ShowsVersion", func(t *testing.T) {
		for _, flag := range []string{"version", "-v", "--version"} {
			var stdout, stderr bytes.Buffer
			code := Run(ctx, []string{flag}, &stdout, &stderr)
			if code != 0 {
				t.Fatalf("flag %s: expected code 0, got %d", flag, code)
			}
			expected := fmt.Sprintf("bors-producer version %s\n", Version())
			if stdout.String() != expected {
				t.Errorf("flag %s: expected %q, got %q", flag, expected, stdout.String())
			}
		}
	})

	t.Run("UnknownCommand_ReturnsError", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"nonexistent-command"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "unknown command") {
			t.Errorf("stderr does not mention unknown command: %s", stderr.String())
		}
	})

	t.Run("CodalNoArgs_ReturnsErrorWithHelp", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"codal"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "Usage: bors-producer codal") {
			t.Errorf("stderr does not show codal help: %s", stderr.String())
		}
	})

	t.Run("CodalUnknownSubcommand", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"codal", "invalid-sub"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "unknown codal subcommand") {
			t.Errorf("stderr does not mention unknown subcommand: %s", stderr.String())
		}
	})

	t.Run("MarketNoArgs_ReturnsErrorWithHelp", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"market"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "Usage: bors-producer market") {
			t.Errorf("stderr does not show market help: %s", stderr.String())
		}
	})

	t.Run("MarketUnknownSubcommand", func(t *testing.T) {
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"market", "invalid-sub"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "unknown market subcommand") {
			t.Errorf("stderr does not mention unknown subcommand: %s", stderr.String())
		}
	})
}

func TestSecurityGatePublish(t *testing.T) {
	ctx := context.Background()

	t.Run("RejectSensitiveCLIArgs", func(t *testing.T) {
		forbiddenArgs := [][]string{
			{"codal", "publish", "--token=secret-token", "--tag=v1.0.0"},
			{"codal", "publish", "--github-token=secret-token", "--tag=v1.0.0"},
			{"codal", "publish", "-token", "secret-token", "--tag=v1.0.0"},
			{"codal", "publish", "-github-token", "secret-token", "--tag=v1.0.0"},
			{"codal", "snapshot", "--key=my-private-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "-key", "my-private-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "--secret-key=my-secret-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "-secret-key", "my-secret-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "--private-key=my-private-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "-private-key", "my-private-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "--minisign-key=my-minisign-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "-minisign-key", "my-minisign-key", "--tag=v1.0.0"},
			{"codal", "snapshot", "--password=my-password", "--tag=v1.0.0"},
			{"codal", "snapshot", "-password", "my-password", "--tag=v1.0.0"},
			{"market", "run", "--password=my-password"},
			{"daemon", "--key=sensitive-key"},
		}

		for _, args := range forbiddenArgs {
			var stdout, stderr bytes.Buffer
			code := Run(ctx, args, &stdout, &stderr)
			if code != 1 {
				t.Errorf("args %v: expected exit code 1, got %d", args, code)
			}
			expectedMsg := "security error: passing sensitive credentials (tokens, private keys, passwords) via CLI arguments is strictly prohibited; use environment variables instead"
			if !strings.Contains(stderr.String(), expectedMsg) {
				t.Errorf("args %v: expected %q in stderr, got: %s", args, expectedMsg, stderr.String())
			}
		}
	})

	t.Run("MissingGithubTokenEnvVar", func(t *testing.T) {
		t.Setenv("GITHUB_TOKEN", "")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"codal", "publish", "--tag=v1.0.0"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected exit code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "GITHUB_TOKEN environment variable is required") {
			t.Errorf("expected GITHUB_TOKEN requirement message, got: %s", stderr.String())
		}
	})

	t.Run("MissingTagFlag", func(t *testing.T) {
		t.Setenv("GITHUB_TOKEN", "valid-test-token")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"codal", "publish"}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected exit code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "--tag is required") {
			t.Errorf("expected tag required error, got: %s", stderr.String())
		}
	})

	t.Run("MissingMinisignKey", func(t *testing.T) {
		t.Setenv("GITHUB_TOKEN", "valid-test-token")
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_KEY_FILE", "")

		tmpDir := t.TempDir()
		manifestPath := filepath.Join(tmpDir, "manifest.json")
		mf := snapshot.NewManifest("set-123", 1)
		if err := mf.Save(manifestPath); err != nil {
			t.Fatalf("save manifest: %v", err)
		}

		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{"codal", "publish", "--tag=v1.0.0", "--manifest=" + manifestPath}, &stdout, &stderr)
		if code != 1 {
			t.Fatalf("expected exit code 1, got %d", code)
		}
		if !strings.Contains(stderr.String(), "MINISIGN_SECRET_KEY or MINISIGN_KEY_FILE") {
			t.Errorf("expected minisign key requirement error, got: %s", stderr.String())
		}
	})
}

func TestCodalSnapshot(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()

	// 1. Create market.db fixture
	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	_, err = marketDB.Exec(`
		CREATE TABLE instruments (id INTEGER PRIMARY KEY, symbol TEXT);
		INSERT INTO instruments (id, symbol) VALUES (1, 'فولاد'), (2, 'فملی');
	`)
	marketDB.Close()
	if err != nil {
		t.Fatalf("populate market.db: %v", err)
	}

	// 2. Create codal.db fixture
	codalPath := filepath.Join(dataDir, "codal.db")
	codalDB, err := db.OpenRWC(codalPath)
	if err != nil {
		t.Fatalf("open codal.db: %v", err)
	}
	_, err = codalDB.Exec(`
		CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT);
		INSERT INTO codal_notices (tracing_no, symbol) VALUES (1001, 'فولاد');
	`)
	codalDB.Close()
	if err != nil {
		t.Fatalf("populate codal.db: %v", err)
	}

	// 3. Generate test Minisign key
	pubStr, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate minisign key pair: %v", err)
	}
	t.Setenv("MINISIGN_SECRET_KEY", privStr)

	t.Run("SnapshotAllDBs", func(t *testing.T) {
		outDir := filepath.Join(t.TempDir(), "snapshots_all")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--out=" + outDir,
			"--tag=v1.0.95-all",
		}, &stdout, &stderr)

		if code != 0 {
			t.Fatalf("codal snapshot failed with code %d; stderr: %s", code, stderr.String())
		}

		manifestPath := filepath.Join(outDir, "manifest.json")
		manifest, err := snapshot.LoadManifest(manifestPath)
		if err != nil {
			t.Fatalf("failed to load generated manifest: %v", err)
		}

		if manifest.SnapshotSetID != "v1.0.95-all" {
			t.Errorf("expected snapshot_set_id 'v1.0.95-all', got %q", manifest.SnapshotSetID)
		}

		if len(manifest.Assets) != 2 {
			t.Fatalf("expected 2 assets (market, codal), got %d", len(manifest.Assets))
		}

		for _, name := range []string{"market", "codal"} {
			asset, exists := manifest.Assets[name]
			if !exists {
				t.Errorf("missing asset %q in manifest", name)
				continue
			}
			assetFile := filepath.Join(outDir, asset.Path)
			fi, err := os.Stat(assetFile)
			if err != nil {
				t.Errorf("asset file %s does not exist: %v", assetFile, err)
			} else if fi.Size() != asset.SizeBytes {
				t.Errorf("asset size mismatch for %s: got %d, manifest says %d", name, fi.Size(), asset.SizeBytes)
			}
		}

		sigPath := manifestPath + ".sig"
		if _, err := os.Stat(sigPath); err != nil {
			t.Fatalf("manifest signature file %s missing: %v", sigPath, err)
		}
		if err := snapshot.VerifyAsset(manifestPath, sigPath, pubStr); err != nil {
			t.Errorf("manifest signature verification failed: %v", err)
		}
	})

	t.Run("SnapshotSpecificDB_Market", func(t *testing.T) {
		outDir := filepath.Join(t.TempDir(), "snapshots_market")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--db=market.db",
			"--out=" + outDir,
			"--tag=v1.0.95-market",
		}, &stdout, &stderr)

		if code != 0 {
			t.Fatalf("codal snapshot failed with code %d; stderr: %s", code, stderr.String())
		}

		manifestPath := filepath.Join(outDir, "manifest.json")
		manifest, err := snapshot.LoadManifest(manifestPath)
		if err != nil {
			t.Fatalf("failed to load manifest: %v", err)
		}

		if len(manifest.Assets) != 1 {
			t.Fatalf("expected 1 asset, got %d", len(manifest.Assets))
		}
		if _, exists := manifest.Assets["market"]; !exists {
			t.Errorf("expected 'market' asset in manifest")
		}
		if _, exists := manifest.Assets["codal"]; exists {
			t.Errorf("did not expect 'codal' asset in market-only snapshot")
		}
	})

	t.Run("SnapshotSpecificDB_Codal", func(t *testing.T) {
		outDir := filepath.Join(t.TempDir(), "snapshots_codal")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--db=codal.db",
			"--out=" + outDir,
			"--tag=v1.0.95-codal",
		}, &stdout, &stderr)

		if code != 0 {
			t.Fatalf("codal snapshot failed with code %d; stderr: %s", code, stderr.String())
		}

		manifestPath := filepath.Join(outDir, "manifest.json")
		manifest, err := snapshot.LoadManifest(manifestPath)
		if err != nil {
			t.Fatalf("failed to load manifest: %v", err)
		}

		if len(manifest.Assets) != 1 {
			t.Fatalf("expected 1 asset, got %d", len(manifest.Assets))
		}
		if _, exists := manifest.Assets["codal"]; !exists {
			t.Errorf("expected 'codal' asset in manifest")
		}
	})

	t.Run("SnapshotNonexistentDB", func(t *testing.T) {
		outDir := filepath.Join(t.TempDir(), "snapshots_missing")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--db=nonexistent.db",
			"--out=" + outDir,
			"--tag=v1.0.95-missing",
		}, &stdout, &stderr)

		if code != 1 {
			t.Fatalf("expected exit code 1 for nonexistent db, got %d", code)
		}
		if !strings.Contains(stderr.String(), "error: specified database") {
			t.Errorf("expected error message about specified database, got: %s", stderr.String())
		}
	})

	t.Run("SnapshotWithBorsMinisignSecretKey", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", privStr)
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("BORS_MINISIGN_KEY_FILE", "")
		t.Setenv("MINISIGN_KEY_FILE", "")

		outDir := filepath.Join(t.TempDir(), "snapshots_bors_key")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--out=" + outDir,
			"--tag=v1.0.95-bors-key",
		}, &stdout, &stderr)

		if code != 0 {
			t.Fatalf("codal snapshot failed with code %d; stderr: %s", code, stderr.String())
		}
		sigPath := filepath.Join(outDir, "manifest.json.sig")
		if _, err := os.Stat(sigPath); err != nil {
			t.Fatalf("signature file missing: %v", err)
		}
		if err := snapshot.VerifyAsset(filepath.Join(outDir, "manifest.json"), sigPath, pubStr); err != nil {
			t.Errorf("signature verification failed: %v", err)
		}
	})

	t.Run("SnapshotWithBorsMinisignKeyFile", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_SECRET_KEY", "")
		keyPath := filepath.Join(t.TempDir(), "secret.key")
		if err := os.WriteFile(keyPath, []byte(privStr), 0600); err != nil {
			t.Fatalf("write secret key: %v", err)
		}
		t.Setenv("BORS_MINISIGN_KEY_FILE", keyPath)
		t.Setenv("MINISIGN_KEY_FILE", "")

		outDir := filepath.Join(t.TempDir(), "snapshots_bors_key_file")
		var stdout, stderr bytes.Buffer
		code := Run(ctx, []string{
			"codal", "snapshot",
			"--data-dir=" + dataDir,
			"--out=" + outDir,
			"--tag=v1.0.95-bors-file",
		}, &stdout, &stderr)

		if code != 0 {
			t.Fatalf("codal snapshot failed with code %d; stderr: %s", code, stderr.String())
		}
		sigPath := filepath.Join(outDir, "manifest.json.sig")
		if _, err := os.Stat(sigPath); err != nil {
			t.Fatalf("signature file missing: %v", err)
		}
		if err := snapshot.VerifyAsset(filepath.Join(outDir, "manifest.json"), sigPath, pubStr); err != nil {
			t.Errorf("signature verification failed: %v", err)
		}
	})
}

func TestMarketRun(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()

	// 1. Mock TSETMC Server
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		w.Header().Set("Content-Type", "application/json")

		switch {
		case strings.Contains(path, "Sector"):
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sector": []map[string]any{
					{"id": 27, "name": "فلزات اساسی"},
				},
			})
		case strings.Contains(path, "MarketWatch") || strings.Contains(path, "ClosingPrice"):
			_ = json.NewEncoder(w).Encode(map[string]any{
				"marketwatch": []map[string]any{
					{
						"insCode":      "35700344742885862",
						"lVal18AFC":    "فولاد",
						"lVal30":       "فولاد مبارکه اصفهان",
						"priceFirst":   5000.0,
						"priceMax":     5100.0,
						"priceMin":     4950.0,
						"pClosing":     5050.0,
						"pDrCotVal":    5040.0,
						"qTotTran5J":   10000000.0,
						"qTotCap":      50500000000.0,
						"cs":           27,
						"zTotTran":     5000.0,
					},
				},
			})
		case strings.Contains(path, "ClientType"):
			_ = json.NewEncoder(w).Encode(map[string]any{
				"clientType": []map[string]any{
					{
						"insCode":    "35700344742885862",
						"buy_I_Vol":  4000000.0,
						"buy_N_Vol":  1000000.0,
						"sell_I_Vol": 3000000.0,
						"sell_N_Vol": 2000000.0,
					},
				},
			})
		default:
			_ = json.NewEncoder(w).Encode(map[string]any{})
		}
	}))
	defer ts.Close()

	t.Setenv("TSETMC_BASE_URL", ts.URL)

	// 2. Run market run
	var stdout, stderr bytes.Buffer
	code := Run(ctx, []string{
		"market", "run",
		"--data-dir=" + dataDir,
	}, &stdout, &stderr)

	if code != 0 {
		t.Fatalf("market run failed with code %d; stderr: %s", code, stderr.String())
	}

	if !strings.Contains(stdout.String(), "Ingested 1 market watch rows") {
		t.Errorf("stdout does not confirm market watch ingestion: %s", stdout.String())
	}

	// 3. Verify writer lock was cleanly released
	lockPath := filepath.Join(dataDir, tsetmc.LockFileName)
	if _, err := os.Stat(lockPath); err == nil {
		t.Errorf("lock file %s was not cleaned up upon completion", lockPath)
	}

	// Verify another lock can be acquired immediately
	lock2, err := tsetmc.AcquireWriterLock(dataDir)
	if err != nil {
		t.Fatalf("failed to re-acquire lock after run: %v", err)
	}
	_ = lock2.Release()

	// 4. Verify Mutual Exclusion: if lock is already held, market run must exit with code 1
	heldLock, err := tsetmc.AcquireWriterLock(dataDir)
	if err != nil {
		t.Fatalf("failed to acquire holding lock: %v", err)
	}
	defer heldLock.Release()

	var stdout2, stderr2 bytes.Buffer
	code2 := Run(ctx, []string{
		"market", "run",
		"--data-dir=" + dataDir,
	}, &stdout2, &stderr2)

	if code2 != 1 {
		t.Errorf("expected market run to fail with code 1 when lock is held, got %d", code2)
	}
	if !strings.Contains(stderr2.String(), "failed to acquire market writer lock") {
		t.Errorf("expected error message about writer lock, got: %s", stderr2.String())
	}
}

func TestCodalRunAndBackfill(t *testing.T) {
	ctx := context.Background()
	dataDir := t.TempDir()

	// 1. Mock CODAL Server distinguishing Category 1 and Category 3
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := strings.ToLower(r.URL.Path)
		w.Header().Set("Content-Type", "application/json")

		if strings.Contains(path, "search") {
			cat := r.URL.Query().Get("Category")
			if cat == "1" {
				_ = json.NewEncoder(w).Encode(map[string]any{
					"Page":  1,
					"Total": 1,
					"Letters": []map[string]any{
						{
							"TracingNo":       1001,
							"Symbol":          "فولاد",
							"CompanyName":     "فولاد مبارکه اصفهان",
							"Title":           "صورت‌های مالی سال مالی منتهی به ۱۴۰۲/۱۲/۲۹",
							"LetterCode":      "ن-۱۰",
							"PublishDateTime": "1402/12/29 18:00:00",
							"SentDateTime":    "1402/12/29 17:50:00",
							"Url":             "/Reports/Decision.aspx?LetterSerial=1001",
						},
					},
				})
			} else {
				_ = json.NewEncoder(w).Encode(map[string]any{
					"Page":  1,
					"Total": 1,
					"Letters": []map[string]any{
						{
							"TracingNo":       1005,
							"Symbol":          "فولاد",
							"CompanyName":     "فولاد مبارکه اصفهان",
							"Title":           "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۲/۱۲/۲۹",
							"LetterCode":      "ن-۳۰",
							"PublishDateTime": "1402/12/29 18:00:00",
							"SentDateTime":    "1402/12/29 17:50:00",
							"Url":             "/Reports/Decision.aspx?LetterSerial=1005",
						},
					},
				})
			}
			return
		}

		// Report HTML Content
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		html := `<html><body>
			<table id="tblMonthly">
				<tr><th>شرح</th><th>مبلغ فروش</th></tr>
				<tr><td>جمع کل فروش ماهانه</td><td>15,000,000</td></tr>
			</table>
		</body></html>`
		_, _ = w.Write([]byte(html))
	}))
	defer ts.Close()

	t.Setenv("CODAL_BASE_URL", ts.URL)

	// 2. Run codal run with default category (0 = both Category 1 & 3)
	var stdout, stderr bytes.Buffer
	code := Run(ctx, []string{
		"codal", "run",
		"--data-dir=" + dataDir,
		"--mode=update",
		"--limit=5",
	}, &stdout, &stderr)

	if code != 0 {
		t.Fatalf("codal run failed with code %d; stderr: %s", code, stderr.String())
	}

	if !strings.Contains(stdout.String(), "Discovered 2 notices from feed") {
		t.Errorf("stdout does not confirm feed discovery of 2 notices (cat 1 & 3): %s", stdout.String())
	}

	// 2b. Test invalid category
	var invStdout, invStderr bytes.Buffer
	invCode := Run(ctx, []string{
		"codal", "run",
		"--data-dir=" + dataDir,
		"--category=99",
	}, &invStdout, &invStderr)
	if invCode != 1 {
		t.Fatalf("expected code 1 for invalid category, got %d", invCode)
	}
	if !strings.Contains(invStderr.String(), "invalid category 99") {
		t.Errorf("expected invalid category error, got: %s", invStderr.String())
	}

	// 3. Insert an unprocessed notice directly into codal_notices to test backfill
	marketPath := filepath.Join(dataDir, "market.db")
	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	_, err = dbConn.Exec(`
		INSERT INTO codal_notices (tracing_no, symbol, title, letter_code, url, processed_at)
		VALUES (1006, 'فملی', 'گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۲/۱۲/۲۹', 'ن-۳۰', '/Reports/Decision.aspx?LetterSerial=1006', NULL);
	`)
	dbConn.Close()
	if err != nil {
		t.Fatalf("insert pending notice: %v", err)
	}

	// 4. Run codal backfill
	var bfStdout, bfStderr bytes.Buffer
	bfCode := Run(ctx, []string{
		"codal", "backfill",
		"--data-dir=" + dataDir,
		"--limit=5",
	}, &bfStdout, &bfStderr)

	if bfCode != 0 {
		t.Fatalf("codal backfill failed with code %d; stderr: %s", bfCode, bfStderr.String())
	}

	if !strings.Contains(bfStdout.String(), "Found 1 pending notices to backfill") {
		t.Errorf("backfill stdout does not report found notice: %s", bfStdout.String())
	}
}

func TestDaemonWriterLockWithTimeout(t *testing.T) {
	dataDir := t.TempDir()

	// Acquire lock initially
	heldLock, err := tsetmc.AcquireWriterLock(dataDir)
	if err != nil {
		t.Fatalf("initial lock acquire failed: %v", err)
	}

	// Release lock after 50ms in goroutine
	go func() {
		time.Sleep(50 * time.Millisecond)
		_ = heldLock.Release()
	}()

	// AcquireWriterLockWithTimeout should wait and succeed within 500ms
	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	lock2, err := tsetmc.AcquireWriterLockWithTimeout(ctx, dataDir, 20*time.Millisecond)
	if err != nil {
		t.Fatalf("AcquireWriterLockWithTimeout failed: %v", err)
	}
	defer lock2.Release()
}

func TestDaemonGracefulShutdown(t *testing.T) {
	dataDir := t.TempDir()
	configFile := filepath.Join(t.TempDir(), "test_daemon_config.json")

	cfg := DaemonConfig{
		DataDir:              dataDir,
		PeakIntervalSec:      1,
		OffPeakIntervalSec:   2,
		MarketIntervalSec:    1,
		CorporateIntervalSec: 2,
		DrainTimeoutSec:      1,
	}
	cfgBytes, err := json.Marshal(cfg)
	if err != nil {
		t.Fatalf("marshal daemon config: %v", err)
	}
	if err := os.WriteFile(configFile, cfgBytes, 0644); err != nil {
		t.Fatalf("write daemon config: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan int, 1)
	var stdout, stderr bytes.Buffer

	go func() {
		code := Run(ctx, []string{
			"daemon",
			"--config=" + configFile,
			"--data-dir=" + dataDir,
		}, &stdout, &stderr)
		done <- code
	}()

	// Wait briefly for daemon to initialize and start worker tasks
	time.Sleep(100 * time.Millisecond)

	// Trigger cancellation
	cancel()

	select {
	case code := <-done:
		if code != 0 {
			t.Fatalf("daemon exited with error code %d; stderr: %s", code, stderr.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("daemon did not stop within timeout")
	}

	outStr := stdout.String()
	if !strings.Contains(outStr, "BorsTerminal Producer Daemon started") {
		t.Errorf("stdout does not confirm daemon start: %s", outStr)
	}
	if !strings.Contains(outStr, "Producer daemon stopped cleanly.") {
		t.Errorf("stdout does not confirm clean shutdown: %s", outStr)
	}
}

func TestMinisignSecretKeyAliases(t *testing.T) {
	_, privKey1, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate key 1: %v", err)
	}
	_, privKey2, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate key 2: %v", err)
	}

	t.Run("DirectEnvBorsMinisignSecretKey", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", privKey1)
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("BORS_MINISIGN_KEY_FILE", "")
		t.Setenv("MINISIGN_KEY_FILE", "")

		got := getMinisignSecretKey()
		if got != privKey1 {
			t.Errorf("expected %s, got %s", privKey1, got)
		}
	})

	t.Run("PrecedenceBorsOverMinisign", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", privKey1)
		t.Setenv("MINISIGN_SECRET_KEY", privKey2)
		t.Setenv("BORS_MINISIGN_KEY_FILE", "")
		t.Setenv("MINISIGN_KEY_FILE", "")

		got := getMinisignSecretKey()
		if got != privKey1 {
			t.Errorf("expected BORS_MINISIGN_SECRET_KEY precedence (%s), got %s", privKey1, got)
		}
	})

	t.Run("FallbackToMinisignSecretKey", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_SECRET_KEY", privKey2)
		t.Setenv("BORS_MINISIGN_KEY_FILE", "")
		t.Setenv("MINISIGN_KEY_FILE", "")

		got := getMinisignSecretKey()
		if got != privKey2 {
			t.Errorf("expected fallback to MINISIGN_SECRET_KEY (%s), got %s", privKey2, got)
		}
	})

	t.Run("KeyFileBorsMinisignKeyFile", func(t *testing.T) {
		tmpKeyFile := filepath.Join(t.TempDir(), "minisign_bors.key")
		if err := os.WriteFile(tmpKeyFile, []byte(privKey1), 0600); err != nil {
			t.Fatalf("write key file: %v", err)
		}
		t.Setenv("BORS_MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("BORS_MINISIGN_KEY_FILE", tmpKeyFile)
		t.Setenv("MINISIGN_KEY_FILE", "")

		got := getMinisignSecretKey()
		if got != privKey1 {
			t.Errorf("expected key from BORS_MINISIGN_KEY_FILE (%s), got %s", privKey1, got)
		}
	})

	t.Run("KeyFileFallbackMinisignKeyFile", func(t *testing.T) {
		tmpKeyFile := filepath.Join(t.TempDir(), "minisign_std.key")
		if err := os.WriteFile(tmpKeyFile, []byte(privKey2), 0600); err != nil {
			t.Fatalf("write key file: %v", err)
		}
		t.Setenv("BORS_MINISIGN_SECRET_KEY", "")
		t.Setenv("MINISIGN_SECRET_KEY", "")
		t.Setenv("BORS_MINISIGN_KEY_FILE", "")
		t.Setenv("MINISIGN_KEY_FILE", tmpKeyFile)

		got := getMinisignSecretKey()
		if got != privKey2 {
			t.Errorf("expected key from MINISIGN_KEY_FILE (%s), got %s", privKey2, got)
		}
	})

	t.Run("PasswordAliases", func(t *testing.T) {
		t.Setenv("BORS_MINISIGN_PASSWORD", "pass1")
		t.Setenv("MINISIGN_PASSWORD", "pass2")
		if got := getMinisignPassword(); got != "pass1" {
			t.Errorf("expected pass1 from BORS_MINISIGN_PASSWORD, got %s", got)
		}

		t.Setenv("BORS_MINISIGN_PASSWORD", "")
		t.Setenv("MINISIGN_PASSWORD", "pass2")
		if got := getMinisignPassword(); got != "pass2" {
			t.Errorf("expected pass2 from MINISIGN_PASSWORD, got %s", got)
		}
	})
}

func TestDaemonScheduledSnapshot(t *testing.T) {
	dataDir := t.TempDir()
	snapshotOutDir := filepath.Join(t.TempDir(), "scheduled_snapshots")
	configFile := filepath.Join(t.TempDir(), "test_daemon_snapshot_config.json")

	// 1. Create a dummy sqlite database in dataDir
	dbPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(dbPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}
	_, err = marketDB.Exec(`
		CREATE TABLE instruments (id INTEGER PRIMARY KEY, symbol TEXT);
		INSERT INTO instruments (id, symbol) VALUES (1, 'فولاد');
	`)
	marketDB.Close()
	if err != nil {
		t.Fatalf("populate market.db: %v", err)
	}

	// 2. Setup Minisign key for signing
	pubStr, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate minisign key: %v", err)
	}
	t.Setenv("BORS_MINISIGN_SECRET_KEY", privStr)

	// 3. Write daemon config with SnapshotIntervalSec = 1
	cfg := DaemonConfig{
		DataDir:              dataDir,
		PeakIntervalSec:      10,
		OffPeakIntervalSec:   20,
		MarketIntervalSec:    10,
		CorporateIntervalSec: 20,
		SnapshotIntervalSec:  1, // 1 second interval
		SnapshotOutDir:       snapshotOutDir,
		DrainTimeoutSec:      2,
		LogLevel:             "debug",
		LogFormat:            "json",
	}
	cfgBytes, err := json.Marshal(cfg)
	if err != nil {
		t.Fatalf("marshal daemon config: %v", err)
	}
	if err := os.WriteFile(configFile, cfgBytes, 0644); err != nil {
		t.Fatalf("write daemon config: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan int, 1)
	var stdout, stderr bytes.Buffer

	go func() {
		code := Run(ctx, []string{
			"daemon",
			"--config=" + configFile,
			"--data-dir=" + dataDir,
		}, &stdout, &stderr)
		done <- code
	}()

	manifestFile := filepath.Join(snapshotOutDir, "manifest.json")
	sigFile := manifestFile + ".sig"

	deadline := time.Now().Add(4 * time.Second)
	found := false
	for time.Now().Before(deadline) {
		if _, err := os.Stat(manifestFile); err == nil {
			if _, err := os.Stat(sigFile); err == nil {
				found = true
				break
			}
		}
		time.Sleep(100 * time.Millisecond)
	}

	cancel()

	select {
	case code := <-done:
		if code != 0 {
			t.Fatalf("daemon exited with code %d; stderr: %s", code, stderr.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("daemon did not stop within timeout")
	}

	if !found {
		t.Fatalf("snapshot manifest or signature was not created in %s within deadline; stdout: %s; stderr: %s",
			snapshotOutDir, stdout.String(), stderr.String())
	}

	// Verify manifest and signature
	manifest, err := snapshot.LoadManifest(manifestFile)
	if err != nil {
		t.Fatalf("load manifest failed: %v", err)
	}
	if _, ok := manifest.Assets["market"]; !ok {
		t.Errorf("expected asset 'market' in manifest, got: %v", manifest.Assets)
	}
	if err := snapshot.VerifyAsset(manifestFile, sigFile, pubStr); err != nil {
		t.Fatalf("signature verification failed: %v", err)
	}
}
