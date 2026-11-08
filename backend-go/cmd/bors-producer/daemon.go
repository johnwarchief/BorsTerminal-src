package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/tsetmc"
	"borsterminal/backend/internal/worker"
)

// DaemonConfig holds configuration options for the background producer daemon.
type DaemonConfig struct {
	DataDir              string `json:"data_dir"`
	PeakIntervalSec      int    `json:"peak_interval_sec"`
	OffPeakIntervalSec   int    `json:"off_peak_interval_sec"`
	MarketIntervalSec    int    `json:"market_interval_sec"`
	CorporateIntervalSec int    `json:"corporate_interval_sec"`
	DrainTimeoutSec      int    `json:"drain_timeout_sec"`
}

func defaultDaemonConfig() DaemonConfig {
	return DaemonConfig{
		DataDir:              ".",
		PeakIntervalSec:      600,   // 10 minutes
		OffPeakIntervalSec:   7200,  // 2 hours
		MarketIntervalSec:    60,    // 1 minute
		CorporateIntervalSec: 7200,  // 2 hours
		DrainTimeoutSec:      10,    // 10 seconds
	}
}

func runDaemon(ctx context.Context, args []string, stdout, stderr io.Writer) int {
	if err := checkSensitiveCLIArgs(args, stderr); err != nil {
		return 1
	}

	fs := flag.NewFlagSet("daemon", flag.ContinueOnError)
	fs.SetOutput(stderr)
	configFlag := fs.String("config", "producer_config.json", "Path to producer JSON configuration file")
	dataDirFlag := fs.String("data-dir", "", "Directory holding database files (overrides config)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	cfg := defaultDaemonConfig()
	if *configFlag != "" {
		if data, err := os.ReadFile(*configFlag); err == nil {
			if err := json.Unmarshal(data, &cfg); err != nil {
				fmt.Fprintf(stderr, "warning: invalid config file %s: %v, using defaults\n", *configFlag, err)
			}
		}
	}

	if *dataDirFlag != "" {
		cfg.DataDir = *dataDirFlag
	}

	if err := os.MkdirAll(cfg.DataDir, 0755); err != nil {
		fmt.Fprintf(stderr, "failed to create data dir %s: %v\n", cfg.DataDir, err)
		return 1
	}

	peakInterval := time.Duration(cfg.PeakIntervalSec) * time.Second
	if peakInterval <= 0 {
		peakInterval = 10 * time.Minute
	}
	offPeakInterval := time.Duration(cfg.OffPeakIntervalSec) * time.Second
	if offPeakInterval <= 0 {
		offPeakInterval = 2 * time.Hour
	}
	marketInterval := time.Duration(cfg.MarketIntervalSec) * time.Second
	if marketInterval <= 0 {
		marketInterval = 1 * time.Minute
	}
	corporateInterval := time.Duration(cfg.CorporateIntervalSec) * time.Second
	if corporateInterval <= 0 {
		corporateInterval = 2 * time.Hour
	}
	drainTimeout := time.Duration(cfg.DrainTimeoutSec) * time.Second
	if drainTimeout <= 0 {
		drainTimeout = 10 * time.Second
	}

	cadenceMgr := worker.NewCadenceManager(worker.CadenceConfig{
		PeakInterval:    peakInterval,
		OffPeakInterval: offPeakInterval,
	})

	orchestrator := worker.NewOrchestrator()

	// 1. Task: CODAL Adaptive Polling
	err := orchestrator.Register(worker.WorkerTask{
		Name:    "codal_poll",
		Cadence: cadenceMgr.Interval,
		Fn: func(taskCtx context.Context) error {
			marketPath := filepath.Join(cfg.DataDir, "market.db")
			dbConn, err := db.OpenRWC(marketPath)
			if err != nil {
				return err
			}
			defer dbConn.Close()

			_ = codal.EnsureSchema(dbConn)
			_ = codal.EnsureValidationSchema(dbConn)
			_ = codal.EnsureRecalcSchema(dbConn)

			client := codal.NewPoliteClient()
			var notices []codal.NoticeSummary
			seen := make(map[int64]bool)
			for _, cat := range []int{1, 3} {
				catNotices, err := codal.DiscoverFeed(taskCtx, client, dbConn, cat)
				if err != nil {
					return err
				}
				for _, n := range catNotices {
					if !seen[n.TracingNo] {
						seen[n.TracingNo] = true
						notices = append(notices, n)
					}
				}
			}
			_ = processNotices(taskCtx, dbConn, client, notices, 0, io.Discard, stderr)
			_, err = codal.RecalculateDirtyFTS(taskCtx, dbConn, nil)
			return err
		},
	})
	if err != nil {
		fmt.Fprintf(stderr, "failed to register codal_poll task: %v\n", err)
		return 1
	}

	// 2. Task: TSETMC Market Sync
	err = orchestrator.Register(worker.WorkerTask{
		Name:     "market_sync",
		Interval: marketInterval,
		Fn: func(taskCtx context.Context) error {
			lock, err := tsetmc.AcquireWriterLockWithTimeout(taskCtx, cfg.DataDir, 100*time.Millisecond)
			if err != nil {
				return err
			}
			defer lock.Release()

			marketPath := filepath.Join(cfg.DataDir, "market.db")
			marketDB, err := db.OpenRWC(marketPath)
			if err != nil {
				return err
			}
			defer marketDB.Close()

			_ = tsetmc.EnsureMarketWatchSchema(marketDB)
			_ = tsetmc.EnsureClientTypeSchema(marketDB)

			client := tsetmc.NewClient("", nil)
			mwRows, instRows, err := client.FetchMarketWatch(taskCtx)
			if err != nil {
				return err
			}
			if err := tsetmc.IngestMarketWatch(taskCtx, marketDB, mwRows, instRows); err != nil {
				return err
			}
			pts, err := client.FetchClientTypeAll(taskCtx)
			if err == nil && len(pts) > 0 {
				_ = tsetmc.IngestClientType(taskCtx, marketDB, pts)
			}
			return nil
		},
	})
	if err != nil {
		fmt.Fprintf(stderr, "failed to register market_sync task: %v\n", err)
		return 1
	}

	// 3. Task: Corporate Actions
	err = orchestrator.Register(worker.WorkerTask{
		Name:     "corporate_actions",
		Interval: corporateInterval,
		Fn: func(taskCtx context.Context) error {
			lock, err := tsetmc.AcquireWriterLockWithTimeout(taskCtx, cfg.DataDir, 100*time.Millisecond)
			if err != nil {
				return err
			}
			defer lock.Release()

			marketPath := filepath.Join(cfg.DataDir, "market.db")
			marketDB, err := db.OpenRWC(marketPath)
			if err != nil {
				return err
			}
			defer marketDB.Close()

			_ = tsetmc.EnsureCorporateSchema(taskCtx, marketDB)
			client := tsetmc.NewClient("", nil)
			return tsetmc.SyncCorporateEvents(taskCtx, client.HTTPClient, marketDB, "")
		},
	})
	if err != nil {
		fmt.Fprintf(stderr, "failed to register corporate_actions task: %v\n", err)
		return 1
	}

	// Start orchestrator
	if err := orchestrator.Start(ctx); err != nil {
		fmt.Fprintf(stderr, "failed to start orchestrator: %v\n", err)
		return 1
	}

	fmt.Fprintf(stdout, "BorsTerminal Producer Daemon started (data: %s, peak: %v, off-peak: %v, market: %v). Press Ctrl+C to terminate.\n",
		cfg.DataDir, peakInterval, offPeakInterval, marketInterval)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigCh)

	select {
	case <-ctx.Done():
		fmt.Fprintln(stdout, "Context cancelled; draining daemon tasks...")
	case sig := <-sigCh:
		fmt.Fprintf(stdout, "Received signal %v; draining daemon tasks...\n", sig)
	}

	if drainErr := orchestrator.Drain(drainTimeout); drainErr != nil {
		fmt.Fprintf(stderr, "warning: drain timeout exceeded: %v\n", drainErr)
	}
	_ = orchestrator.Stop()

	fmt.Fprintln(stdout, "Producer daemon stopped cleanly.")
	return 0
}
