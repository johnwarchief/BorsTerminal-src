package main

import (
	"context"
	"database/sql"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
)

func runCodal(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		printCodalHelp(stderr)
		return 1
	}

	sub := args[0]
	rest := args[1:]

	switch sub {
	case "run":
		return runCodalRun(ctx, rest, stdout, stderr)
	case "backfill":
		return runCodalBackfill(ctx, rest, stdout, stderr)
	case "snapshot":
		return runCodalSnapshot(ctx, rest, stdout, stderr)
	case "publish":
		return runCodalPublish(ctx, rest, stdout, stderr)
	case "help", "-h", "--help":
		printCodalHelp(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown codal subcommand %q\nRun 'bors-producer codal help' for usage.\n", sub)
		return 1
	}
}

func printCodalHelp(w io.Writer) {
	help := `Usage: bors-producer codal <subcommand> [flags]

Subcommands:
  run       Discover feed, extract, validate & ingest notices, recalc FTS
  backfill  Ingest pending/unprocessed notices from codal_notices
  snapshot  Create compressed LZMA snapshots and signed manifest
  publish   Upload and publish snapshot set to GitHub Release

Flags for 'run':
  --mode=update|full  Run mode (default: update)
  --category=N        CODAL category: 0 = both 1 & 3, 1 = statements, 3 = monthly (default: 0)
  --data-dir=PATH     Directory containing database files (default: .)
  --limit=N           Max notices to process (default: 0 = unlimited)

Flags for 'backfill':
  --limit=N           Max pending notices to backfill (default: 0 = all)
  --data-dir=PATH     Directory containing database files (default: .)

Flags for 'snapshot':
  --data-dir=PATH     Directory containing database files (default: .)
  --db=NAME           Specific database file to snapshot (e.g. codal.db or market.db)
  --out=PATH          Output directory for snapshots (default: dist/snapshots)
  --tag=TAG           Snapshot set ID / Release tag

Flags for 'publish':
  --tag=TAG           Release tag to publish assets to (required)
  --manifest=PATH     Path to manifest.json (default: dist/snapshots/manifest.json)
  --repo=owner/repo   Target GitHub repository (default: johnwarchief/BorsTerminal)
  NOTE: GITHUB_TOKEN must be provided via environment variable GITHUB_TOKEN.
`
	fmt.Fprint(w, help)
}

func runCodalRun(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("codal run", flag.ContinueOnError)
	fs.SetOutput(stderr)
	modeFlag := fs.String("mode", "update", "Ingestion mode: update or full")
	categoryFlag := fs.Int("category", 0, "CODAL category filter: 0 = both Category 1 & 3, 1 = Financial Statements, 3 = Monthly Activity Reports")
	dataDirFlag := fs.String("data-dir", ".", "Directory holding market.db")
	limitFlag := fs.Int("limit", 0, "Max notices to process (0 for unlimited)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	mode := strings.ToLower(strings.TrimSpace(*modeFlag))
	if mode != "update" && mode != "full" {
		fmt.Fprintf(stderr, "invalid mode %q: must be 'update' or 'full'\n", mode)
		return 1
	}

	var categories []int
	switch *categoryFlag {
	case 0:
		categories = []int{1, 3}
	case 1, 3:
		categories = []int{*categoryFlag}
	default:
		fmt.Fprintf(stderr, "invalid category %d: must be 0 (both Category 1 & 3), 1, or 3\n", *categoryFlag)
		return 1
	}

	dataDir := *dataDirFlag
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		fmt.Fprintf(stderr, "failed to create data-dir %s: %v\n", dataDir, err)
		return 1
	}

	marketPath := filepath.Join(dataDir, "market.db")
	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		fmt.Fprintf(stderr, "failed to open database %s: %v\n", marketPath, err)
		return 1
	}
	defer dbConn.Close()

	if err := codal.EnsureSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure codal schema: %v\n", err)
		return 1
	}
	if err := codal.EnsureValidationSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure validation schema: %v\n", err)
		return 1
	}
	if err := codal.EnsureRecalcSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure recalc schema: %v\n", err)
		return 1
	}

	client := codal.NewPoliteClient()

	if mode == "full" {
		if *categoryFlag == 0 {
			_, _ = dbConn.ExecContext(ctx, "DELETE FROM pipeline_cursor WHERE key LIKE 'notice_scan_tn_cat%'")
		} else {
			_, _ = dbConn.ExecContext(ctx, "DELETE FROM pipeline_cursor WHERE key = ?", fmt.Sprintf("notice_scan_tn_cat%d", *categoryFlag))
		}
	}

	var notices []codal.NoticeSummary
	seen := make(map[int64]bool)
	for _, cat := range categories {
		catNotices, err := codal.DiscoverFeed(ctx, client, dbConn, cat)
		if err != nil {
			fmt.Fprintf(stderr, "feed discovery failed for category %d: %v\n", cat, err)
			return 1
		}
		for _, n := range catNotices {
			if !seen[n.TracingNo] {
				seen[n.TracingNo] = true
				notices = append(notices, n)
			}
		}
	}
	fmt.Fprintf(stdout, "Discovered %d notices from feed\n", len(notices))

	processed := processNotices(ctx, dbConn, client, notices, *limitFlag, stdout, stderr)
	fmt.Fprintf(stdout, "Processed %d notices\n", processed)

	recalcCount, err := codal.RecalculateDirtyFTS(ctx, dbConn, nil)
	if err != nil {
		fmt.Fprintf(stderr, "warning: recalc dirty FTS failed: %v\n", err)
	} else {
		fmt.Fprintf(stdout, "Recalculated FTS for %d dirty symbols\n", recalcCount)
	}

	return 0
}

func runCodalBackfill(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("codal backfill", flag.ContinueOnError)
	fs.SetOutput(stderr)
	limitFlag := fs.Int("limit", 0, "Max notices to backfill (0 for unlimited)")
	dataDirFlag := fs.String("data-dir", ".", "Directory holding market.db")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	dataDir := *dataDirFlag
	marketPath := filepath.Join(dataDir, "market.db")
	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		fmt.Fprintf(stderr, "failed to open database %s: %v\n", marketPath, err)
		return 1
	}
	defer dbConn.Close()

	if err := codal.EnsureSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure codal schema: %v\n", err)
		return 1
	}
	if err := codal.EnsureValidationSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure validation schema: %v\n", err)
		return 1
	}
	if err := codal.EnsureRecalcSchema(dbConn); err != nil {
		fmt.Fprintf(stderr, "failed to ensure recalc schema: %v\n", err)
		return 1
	}

	query := `SELECT tracing_no, symbol, COALESCE(company_name, ''), title, COALESCE(letter_code, ''),
	                 COALESCE(publish_date, ''), COALESCE(sent_date, ''), COALESCE(url, '')
	          FROM codal_notices
	          WHERE processed_at IS NULL
	          ORDER BY tracing_no DESC`
	if *limitFlag > 0 {
		query += fmt.Sprintf(" LIMIT %d", *limitFlag)
	}

	rows, err := dbConn.QueryContext(ctx, query)
	if err != nil {
		fmt.Fprintf(stderr, "query pending notices failed: %v\n", err)
		return 1
	}
	defer rows.Close()

	var pending []codal.NoticeSummary
	for rows.Next() {
		var n codal.NoticeSummary
		if err := rows.Scan(&n.TracingNo, &n.Symbol, &n.CompanyName, &n.Title, &n.LetterCode, &n.PublishDate, &n.SentDate, &n.URL); err != nil {
			fmt.Fprintf(stderr, "scan notice row failed: %v\n", err)
			return 1
		}
		pending = append(pending, n)
	}
	_ = rows.Close()

	fmt.Fprintf(stdout, "Found %d pending notices to backfill\n", len(pending))
	if len(pending) == 0 {
		return 0
	}

	client := codal.NewPoliteClient()
	processed := processNotices(ctx, dbConn, client, pending, *limitFlag, stdout, stderr)
	fmt.Fprintf(stdout, "Backfilled %d notices\n", processed)

	recalcCount, err := codal.RecalculateDirtyFTS(ctx, dbConn, nil)
	if err != nil {
		fmt.Fprintf(stderr, "warning: recalc dirty FTS failed: %v\n", err)
	} else {
		fmt.Fprintf(stdout, "Recalculated FTS for %d dirty symbols\n", recalcCount)
	}

	return 0
}

func processNotices(ctx context.Context, dbConn *sql.DB, client *codal.PoliteClient, notices []codal.NoticeSummary, limit int, stdout, stderr io.Writer) int {
	processed := 0
	for _, notice := range notices {
		if limit > 0 && processed >= limit {
			break
		}

		targetURL := notice.URL
		if targetURL == "" {
			targetURL = fmt.Sprintf("https://codal.ir/Reports/Decision.aspx?LetterSerial=%d", notice.TracingNo)
		} else if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") {
			targetURL = client.BaseURL() + "/" + strings.TrimPrefix(targetURL, "/")
		}

		body, statusCode, err := client.Get(ctx, targetURL)
		if err != nil || statusCode != 200 {
			// Record quarantine if URL fetch fails or non-200
			reason := fmt.Sprintf("fetch error: status %d, err: %v", statusCode, err)
			_ = codal.QuarantineReport(ctx, dbConn, notice.TracingNo, notice.Symbol, notice.LetterCode, reason, string(body))
			_, _ = dbConn.ExecContext(ctx, "UPDATE codal_notices SET processed_at = CURRENT_TIMESTAMP WHERE tracing_no = ?", notice.TracingNo)
			processed++
			continue
		}

		if isMonthlyNotice(notice.Title, notice.LetterCode) {
			data, extErr := codal.ExtractMonthlySales(body, notice)
			if extErr != nil {
				_ = codal.QuarantineReport(ctx, dbConn, notice.TracingNo, notice.Symbol, "monthly", extErr.Error(), string(body))
			} else if data != nil {
				if valErr := codal.ValidateAndIngestMonthly(ctx, dbConn, data, notice); valErr == nil {
					_ = codal.MarkDirty(ctx, dbConn, notice.Symbol, "codal_monthly")
				}
			}
		} else if isFinancialStatementNotice(notice.Title, notice.LetterCode) {
			sheets := map[string][]byte{"main": body}
			data, extErr := codal.ExtractFinancialStatements(sheets, notice)
			if extErr != nil {
				_ = codal.QuarantineReport(ctx, dbConn, notice.TracingNo, notice.Symbol, "statement", extErr.Error(), string(body))
			} else if data != nil {
				if valErr := codal.ValidateAndIngestStatement(ctx, dbConn, data, notice); valErr == nil {
					_ = codal.MarkDirty(ctx, dbConn, notice.Symbol, "codal_statement")
				}
			}
		}

		_, _ = dbConn.ExecContext(ctx, "UPDATE codal_notices SET processed_at = CURRENT_TIMESTAMP WHERE tracing_no = ?", notice.TracingNo)
		processed++
	}
	return processed
}

func isMonthlyNotice(title, letterCode string) bool {
	t := strings.ToLower(title)
	lc := strings.TrimSpace(letterCode)
	return strings.Contains(t, "ماهانه") || strings.Contains(t, "فعالیت ماهانه") ||
		strings.HasPrefix(lc, "ن-۳") || strings.HasPrefix(lc, "ن۳")
}

func isFinancialStatementNotice(title, letterCode string) bool {
	t := strings.ToLower(title)
	lc := strings.TrimSpace(letterCode)
	return strings.Contains(t, "صورت") || strings.Contains(t, "مالی") ||
		strings.HasPrefix(lc, "ن-۱") || strings.HasPrefix(lc, "ن۱") ||
		strings.HasPrefix(lc, "ن-۲") || strings.HasPrefix(lc, "ن۲")
}

func runCodalSnapshot(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("codal snapshot", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dataDirFlag := fs.String("data-dir", ".", "Directory holding database files")
	outFlag := fs.String("out", "dist/snapshots", "Output directory for snapshots")
	tagFlag := fs.String("tag", "", "Release tag / snapshot set ID")
	dbFlag := fs.String("db", "", "Specific database file to snapshot (e.g. codal.db or market.db)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	dataDir := *dataDirFlag
	outDir := *outFlag
	tag := *tagFlag
	targetDB := strings.TrimSpace(*dbFlag)

	dbs := make(map[string]*sql.DB)
	defer func() {
		for _, dbConn := range dbs {
			if dbConn != nil {
				_ = dbConn.Close()
			}
		}
	}()

	if targetDB != "" {
		var dbPath string
		if filepath.IsAbs(targetDB) {
			dbPath = targetDB
		} else {
			candidate := filepath.Join(dataDir, targetDB)
			if _, err := os.Stat(candidate); err == nil {
				dbPath = candidate
			} else if _, err := os.Stat(candidate + ".db"); err == nil {
				dbPath = candidate + ".db"
			} else if _, err := os.Stat(targetDB); err == nil {
				dbPath = targetDB
			} else {
				dbPath = candidate
			}
		}

		fi, err := os.Stat(dbPath)
		if err != nil || fi.IsDir() {
			fmt.Fprintf(stderr, "error: specified database %s not found\n", dbPath)
			return 1
		}

		conn, err := db.OpenRW(dbPath)
		if err != nil {
			fmt.Fprintf(stderr, "failed to open %s: %v\n", dbPath, err)
			return 1
		}
		key := strings.TrimSuffix(filepath.Base(dbPath), filepath.Ext(dbPath))
		dbs[key] = conn
	} else {
		entries, err := os.ReadDir(dataDir)
		if err != nil {
			fmt.Fprintf(stderr, "failed to read data-dir %s: %v\n", dataDir, err)
			return 1
		}

		for _, entry := range entries {
			if entry.IsDir() {
				continue
			}
			name := entry.Name()
			if strings.EqualFold(filepath.Ext(name), ".db") {
				dbPath := filepath.Join(dataDir, name)
				conn, err := db.OpenRW(dbPath)
				if err != nil {
					fmt.Fprintf(stderr, "failed to open %s: %v\n", dbPath, err)
					return 1
				}
				key := strings.TrimSuffix(name, filepath.Ext(name))
				dbs[key] = conn
			}
		}
	}

	if len(dbs) == 0 {
		fmt.Fprintf(stderr, "error: no database found in %s\n", dataDir)
		return 1
	}

	manifest, err := snapshot.BuildSnapshotSet(ctx, dbs, outDir, tag)
	if err != nil {
		fmt.Fprintf(stderr, "error building snapshot set: %v\n", err)
		return 1
	}

	fmt.Fprintf(stdout, "Created snapshot set %s with %d assets in %s\n", manifest.SnapshotSetID, len(manifest.Assets), outDir)

	privKey := os.Getenv("MINISIGN_SECRET_KEY")
	if privKey == "" {
		if keyFile := os.Getenv("MINISIGN_KEY_FILE"); keyFile != "" {
			b, err := os.ReadFile(keyFile)
			if err == nil {
				privKey = string(b)
			}
		}
	}

	password := os.Getenv("MINISIGN_PASSWORD")
	if privKey != "" {
		manifestPath := filepath.Join(outDir, "manifest.json")
		sigPath, err := snapshot.SignAsset(manifestPath, privKey, password)
		if err != nil {
			fmt.Fprintf(stderr, "error signing manifest: %v\n", err)
			return 1
		}
		fmt.Fprintf(stdout, "Manifest signature generated: %s\n", sigPath)
	}

	return 0
}

func runCodalPublish(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	token := os.Getenv("GITHUB_TOKEN")
	if strings.TrimSpace(token) == "" {
		fmt.Fprintf(stderr, "error: GITHUB_TOKEN environment variable is required for publish\n")
		return 1
	}

	fs := flag.NewFlagSet("codal publish", flag.ContinueOnError)
	fs.SetOutput(stderr)
	tagFlag := fs.String("tag", "", "Release tag to publish assets to (required)")
	manifestFlag := fs.String("manifest", "dist/snapshots/manifest.json", "Path to manifest.json")
	repoFlag := fs.String("repo", "johnwarchief/BorsTerminal", "Target GitHub repository (owner/repo)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	tag := strings.TrimSpace(*tagFlag)
	if tag == "" {
		fmt.Fprintf(stderr, "error: --tag is required for publish\n")
		return 1
	}

	parts := strings.Split(*repoFlag, "/")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		fmt.Fprintf(stderr, "error: invalid repo %q, expected 'owner/repo'\n", *repoFlag)
		return 1
	}
	owner, repoName := parts[0], parts[1]

	manifest, err := snapshot.LoadManifest(*manifestFlag)
	if err != nil {
		fmt.Fprintf(stderr, "error loading manifest %s: %v\n", *manifestFlag, err)
		return 1
	}

	privKey := os.Getenv("MINISIGN_SECRET_KEY")
	if privKey == "" {
		if keyFile := os.Getenv("MINISIGN_KEY_FILE"); keyFile != "" {
			b, err := os.ReadFile(keyFile)
			if err == nil {
				privKey = string(b)
			}
		}
	}
	if strings.TrimSpace(privKey) == "" {
		fmt.Fprintf(stderr, "error: MINISIGN_SECRET_KEY or MINISIGN_KEY_FILE environment variable is required to sign release assets for publishing\n")
		return 1
	}
	password := os.Getenv("MINISIGN_PASSWORD")

	manifestDir := filepath.Dir(*manifestFlag)
	err = snapshot.PublishSnapshotSet(ctx, http.DefaultClient, token, owner, repoName, tag, manifestDir, manifest, privKey, password)
	if err != nil {
		fmt.Fprintf(stderr, "error publishing snapshot set: %v\n", err)
		return 1
	}

	fmt.Fprintf(stdout, "Successfully published snapshot set %s to %s/%s at tag %s\n", manifest.SnapshotSetID, owner, repoName, tag)
	return 0
}
