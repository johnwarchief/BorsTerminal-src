package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/tsetmc"
)

func runMarket(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		printMarketHelp(stderr)
		return 1
	}

	sub := args[0]
	rest := args[1:]

	switch sub {
	case "run":
		return runMarketRun(ctx, rest, stdout, stderr)
	case "help", "-h", "--help":
		printMarketHelp(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown market subcommand %q\nRun 'bors-producer market help' for usage.\n", sub)
		return 1
	}
}

func printMarketHelp(w io.Writer) {
	help := `Usage: bors-producer market <subcommand> [flags]

Subcommands:
  run   Ingest TSETMC market watch, client type, and corporate events

Flags for 'run':
  --data-dir=PATH  Directory holding market.db and writer lock (default: .)
  --history        Fetch and ingest client type history for instruments (default: false)
  --events         Sync corporate capital increases and dividend events (default: false)
`
	fmt.Fprint(w, help)
}

func runMarketRun(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("market run", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dataDirFlag := fs.String("data-dir", ".", "Directory holding market.db and writer lock")
	historyFlag := fs.Bool("history", false, "Fetch and ingest client type history")
	eventsFlag := fs.Bool("events", false, "Sync corporate events")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	dataDir := *dataDirFlag
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		fmt.Fprintf(stderr, "failed to create data-dir %s: %v\n", dataDir, err)
		return 1
	}

	// 1. Acquire single-writer file lock
	lock, err := tsetmc.AcquireWriterLock(dataDir)
	if err != nil {
		fmt.Fprintf(stderr, "error: failed to acquire market writer lock in %s: %v\n", dataDir, err)
		return 1
	}
	defer func() {
		if relErr := lock.Release(); relErr != nil {
			fmt.Fprintf(stderr, "warning: releasing writer lock error: %v\n", relErr)
		}
	}()

	// 2. Open market.db
	marketPath := filepath.Join(dataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		fmt.Fprintf(stderr, "failed to open %s: %v\n", marketPath, err)
		return 1
	}
	defer marketDB.Close()

	// 3. Ensure schemas
	if err := tsetmc.EnsureMarketWatchSchema(marketDB); err != nil {
		fmt.Fprintf(stderr, "failed to ensure market watch schema: %v\n", err)
		return 1
	}
	if err := tsetmc.EnsureClientTypeSchema(marketDB); err != nil {
		fmt.Fprintf(stderr, "failed to ensure client type schema: %v\n", err)
		return 1
	}
	if err := tsetmc.EnsureCorporateSchema(ctx, marketDB); err != nil {
		fmt.Fprintf(stderr, "failed to ensure corporate schema: %v\n", err)
		return 1
	}

	client := tsetmc.NewClient("", nil)

	// 4. Fetch and Ingest live market watch
	mwRows, instRows, err := client.FetchMarketWatch(ctx)
	if err != nil {
		fmt.Fprintf(stderr, "fetch market watch failed: %v\n", err)
		return 1
	}

	if err := tsetmc.IngestMarketWatch(ctx, marketDB, mwRows, instRows); err != nil {
		fmt.Fprintf(stderr, "ingest market watch failed: %v\n", err)
		return 1
	}
	fmt.Fprintf(stdout, "Ingested %d market watch rows and %d instruments\n", len(mwRows), len(instRows))

	// Ingest live client type board
	pts, err := client.FetchClientTypeAll(ctx)
	if err == nil && len(pts) > 0 {
		if ctErr := tsetmc.IngestClientType(ctx, marketDB, pts); ctErr == nil {
			fmt.Fprintf(stdout, "Ingested %d live client type points\n", len(pts))
		}
	}

	// 5. If --history, ingest client type history
	if *historyFlag {
		dEven := time.Now().Year()*10000 + int(time.Now().Month())*100 + time.Now().Day()
		historyCount := 0
		for _, inst := range instRows {
			if ctx.Err() != nil {
				break
			}
			if inst.InsCode == "" {
				continue
			}
			pt, err := client.FetchClientTypeHistory(ctx, inst.InsCode, dEven)
			if err == nil && pt != nil {
				if ingestErr := tsetmc.IngestClientTypeValue(ctx, marketDB, []tsetmc.ClientTypeValuePoint{*pt}); ingestErr == nil {
					historyCount++
				}
			}
		}
		fmt.Fprintf(stdout, "Ingested client type history for %d instruments\n", historyCount)
	}

	// 6. If --events, sync corporate actions
	if *eventsFlag {
		if err := tsetmc.SyncCorporateEvents(ctx, client.HTTPClient, marketDB, ""); err != nil {
			fmt.Fprintf(stderr, "sync corporate events failed: %v\n", err)
			return 1
		}
		fmt.Fprintf(stdout, "Synced corporate events\n")
	}

	return 0
}
