package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
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
	SnapshotIntervalSec  int    `json:"snapshot_interval_sec"`
	SnapshotDailyUTC     string `json:"snapshot_daily_utc"`
	CatchupMissedDaily   bool   `json:"catchup_missed_daily"`
	SnapshotOutDir       string `json:"snapshot_out_dir"`
	PublishEnabled       bool   `json:"publish_enabled"`
	PublishRepo          string `json:"publish_repo"`
	PublishTag           string `json:"publish_tag"`
	PublishBaseURL       string `json:"publish_base_url"`
	DrainTimeoutSec      int    `json:"drain_timeout_sec"`
	LogLevel             string `json:"log_level"`
	LogFormat            string `json:"log_format"`
}

func defaultDaemonConfig() DaemonConfig {
	return DaemonConfig{
		DataDir:              ".",
		PeakIntervalSec:      600,   // 10 minutes
		OffPeakIntervalSec:   7200,  // 2 hours
		MarketIntervalSec:    60,    // 1 minute
		CorporateIntervalSec: 7200,  // 2 hours
		SnapshotIntervalSec:  0,     // legacy relative interval (0 = use SnapshotDailyUTC)
		SnapshotDailyUTC:     "06:00", // fixed 06:00 UTC daily schedule
		CatchupMissedDaily:   true,  // catchup on startup if today's 06:00 UTC run was missed
		SnapshotOutDir:       "",
		PublishEnabled:       false,
		PublishRepo:          "johnwarchief/BorsTerminal",
		PublishTag:           "",
		PublishBaseURL:       "",
		DrainTimeoutSec:      10,    // 10 seconds
		LogLevel:             "info",
		LogFormat:            "text",
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
	publishFlag := fs.Bool("publish", false, "Enable automated snapshot publishing to repository")
	dailyUTCFlag := fs.String("daily-utc", "", "Daily snapshot schedule in HH:MM UTC (overrides config)")

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
	if *publishFlag {
		cfg.PublishEnabled = true
	} else if envPub := os.Getenv("BORS_PUBLISH_ENABLED"); envPub == "1" || strings.EqualFold(envPub, "true") {
		cfg.PublishEnabled = true
	}

	if *dailyUTCFlag != "" {
		cfg.SnapshotDailyUTC = *dailyUTCFlag
	} else if envDaily := os.Getenv("SNAPSHOT_DAILY_UTC"); envDaily != "" {
		cfg.SnapshotDailyUTC = envDaily
	}

	if envRepo := os.Getenv("BORS_GITHUB_REPO"); envRepo != "" {
		cfg.PublishRepo = envRepo
	}
	if envBase := os.Getenv("GITHUB_API_BASE_URL"); envBase != "" && cfg.PublishBaseURL == "" {
		cfg.PublishBaseURL = envBase
	}

	if cfg.SnapshotOutDir == "" {
		cfg.SnapshotOutDir = filepath.Join(cfg.DataDir, "snapshots")
	}

	initLogging(cfg.LogLevel, cfg.LogFormat)

	if err := os.MkdirAll(cfg.DataDir, 0755); err != nil {
		slog.Error("failed to create data dir", "dir", cfg.DataDir, "err", err)
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

	slog.Info("initializing bors-producer daemon",
		"data_dir", cfg.DataDir,
		"peak_interval", peakInterval,
		"off_peak_interval", offPeakInterval,
		"market_interval", marketInterval,
		"corporate_interval", corporateInterval,
		"snapshot_interval_sec", cfg.SnapshotIntervalSec,
		"snapshot_out_dir", cfg.SnapshotOutDir,
	)

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
			slog.Info("codal_poll: task executing")
			marketPath := filepath.Join(cfg.DataDir, "market.db")
			dbConn, err := db.OpenRWC(marketPath)
			if err != nil {
				slog.Error("codal_poll: open market.db failed", "err", err)
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
					slog.Error("codal_poll: feed discovery failed", "category", cat, "err", err)
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
			recalcCount, err := codal.RecalculateDirtyFTS(taskCtx, dbConn, nil)
			if err != nil {
				slog.Error("codal_poll: recalc dirty FTS failed", "err", err)
				return err
			}
			slog.Info("codal_poll: task completed", "discovered", len(notices), "recalculated_fts", recalcCount)
			return nil
		},
	})
	if err != nil {
		slog.Error("failed to register codal_poll task", "err", err)
		fmt.Fprintf(stderr, "failed to register codal_poll task: %v\n", err)
		return 1
	}

	// 2. Task: TSETMC Market Sync
	err = orchestrator.Register(worker.WorkerTask{
		Name:     "market_sync",
		Interval: marketInterval,
		Fn: func(taskCtx context.Context) error {
			slog.Info("market_sync: task started")
			lock, err := tsetmc.AcquireWriterLockWithTimeout(taskCtx, cfg.DataDir, 100*time.Millisecond)
			if err != nil {
				slog.Warn("market_sync: writer lock acquisition timed out", "err", err)
				return err
			}
			defer lock.Release()

			marketPath := filepath.Join(cfg.DataDir, "market.db")
			marketDB, err := db.OpenRWC(marketPath)
			if err != nil {
				slog.Error("market_sync: open market.db failed", "err", err)
				return err
			}
			defer marketDB.Close()

			_ = tsetmc.EnsureMarketWatchSchema(marketDB)
			_ = tsetmc.EnsureClientTypeSchema(marketDB)

			client := tsetmc.NewClient("", nil)
			mwRows, instRows, err := client.FetchMarketWatch(taskCtx)
			if err != nil {
				slog.Error("market_sync: fetch market watch failed", "err", err)
				return err
			}
			if err := tsetmc.IngestMarketWatch(taskCtx, marketDB, mwRows, instRows); err != nil {
				slog.Error("market_sync: ingest market watch failed", "err", err)
				return err
			}
			pts, err := client.FetchClientTypeAll(taskCtx)
			if err == nil && len(pts) > 0 {
				_ = tsetmc.IngestClientType(taskCtx, marketDB, pts)
			}
			slog.Info("market_sync: completed", "market_watch_rows", len(mwRows))
			return nil
		},
	})
	if err != nil {
		slog.Error("failed to register market_sync task", "err", err)
		fmt.Fprintf(stderr, "failed to register market_sync task: %v\n", err)
		return 1
	}

	// 3. Task: Corporate Actions
	err = orchestrator.Register(worker.WorkerTask{
		Name:     "corporate_actions",
		Interval: corporateInterval,
		Fn: func(taskCtx context.Context) error {
			slog.Info("corporate_actions: task started")
			lock, err := tsetmc.AcquireWriterLockWithTimeout(taskCtx, cfg.DataDir, 100*time.Millisecond)
			if err != nil {
				slog.Warn("corporate_actions: writer lock acquisition timed out", "err", err)
				return err
			}
			defer lock.Release()

			marketPath := filepath.Join(cfg.DataDir, "market.db")
			marketDB, err := db.OpenRWC(marketPath)
			if err != nil {
				slog.Error("corporate_actions: open market.db failed", "err", err)
				return err
			}
			defer marketDB.Close()

			_ = tsetmc.EnsureCorporateSchema(taskCtx, marketDB)
			client := tsetmc.NewClient("", nil)
			if err := tsetmc.SyncCorporateEvents(taskCtx, client.HTTPClient, marketDB, ""); err != nil {
				slog.Error("corporate_actions: sync failed", "err", err)
				return err
			}
			slog.Info("corporate_actions: completed successfully")
			return nil
		},
	})
	if err != nil {
		slog.Error("failed to register corporate_actions task", "err", err)
		fmt.Fprintf(stderr, "failed to register corporate_actions task: %v\n", err)
		return 1
	}

	// 4. Task: Scheduled Snapshot Creation & Publishing
	var snapshotCadence func(time.Time) time.Duration
	var snapshotHour, snapshotMinute int
	var isDailySchedule bool

	if cfg.SnapshotDailyUTC != "" {
		h, m, err := parseDailyUTCTime(cfg.SnapshotDailyUTC)
		if err != nil {
			slog.Warn("invalid snapshot_daily_utc, falling back to 06:00 UTC", "val", cfg.SnapshotDailyUTC, "err", err)
			h, m = 6, 0
		}
		snapshotHour, snapshotMinute = h, m
		isDailySchedule = true
		snapshotCadence = func(now time.Time) time.Duration {
			return NextDailyUTCDuration(now, snapshotHour, snapshotMinute)
		}
		slog.Info("configured daily snapshot schedule", "time_utc", fmt.Sprintf("%02d:%02d", snapshotHour, snapshotMinute), "publish_enabled", cfg.PublishEnabled)
	} else if cfg.SnapshotIntervalSec > 0 {
		interval := time.Duration(cfg.SnapshotIntervalSec) * time.Second
		snapshotCadence = func(time.Time) time.Duration { return interval }
		slog.Info("configured interval snapshot schedule", "interval", interval, "publish_enabled", cfg.PublishEnabled)
	}

	if snapshotCadence != nil {
		err = orchestrator.Register(worker.WorkerTask{
			Name:    "snapshot_builder",
			Cadence: snapshotCadence,
			Fn: func(taskCtx context.Context) error {
				slog.Info("snapshot_builder: executing scheduled snapshot pipeline",
					"publish_enabled", cfg.PublishEnabled,
					"out_dir", cfg.SnapshotOutDir,
				)
				_, err := ExecuteScheduledSnapshotPipeline(taskCtx, cfg, time.Now())
				if err != nil {
					slog.Error("snapshot_builder: pipeline failed", "err", err)
					return err
				}
				return nil
			},
		})
		if err != nil {
			slog.Error("failed to register snapshot_builder task", "err", err)
			fmt.Fprintf(stderr, "failed to register snapshot_builder task: %v\n", err)
			return 1
		}
	}

	// Start orchestrator
	if err := orchestrator.Start(ctx); err != nil {
		slog.Error("failed to start orchestrator", "err", err)
		fmt.Fprintf(stderr, "failed to start orchestrator: %v\n", err)
		return 1
	}

	// Startup catchup check: if daily schedule is configured and catchup is enabled,
	// check if today's run has already passed and was missed due to service downtime.
	if isDailySchedule && cfg.CatchupMissedDaily {
		nowUTC := time.Now().UTC()
		todayStr := nowUTC.Format("2006-01-02")
		if nowUTC.Hour() > snapshotHour || (nowUTC.Hour() == snapshotHour && nowUTC.Minute() >= snapshotMinute) {
			lastSuccessDate := LastSuccessfulSnapshotDate(cfg.SnapshotOutDir)
			if lastSuccessDate != todayStr {
				slog.Info("snapshot_builder: missed daily snapshot run detected on startup; queuing catchup run",
					"today", todayStr,
					"last_success", lastSuccessDate,
				)
				if err := orchestrator.Trigger("snapshot_builder"); err != nil {
					slog.Warn("failed to trigger catchup snapshot run", "err", err)
				}
			} else {
				slog.Info("snapshot_builder: daily snapshot for today already completed, next run scheduled at 06:00 UTC",
					"today", todayStr,
				)
			}
		}
	}

	slog.Info("bors-producer orchestrator started")
	fmt.Fprintf(stdout, "BorsTerminal Producer Daemon started (data: %s, peak: %v, off-peak: %v, market: %v). Press Ctrl+C to terminate.\n",
		cfg.DataDir, peakInterval, offPeakInterval, marketInterval)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigCh)

	select {
	case <-ctx.Done():
		slog.Info("daemon context cancelled; draining tasks...")
		fmt.Fprintln(stdout, "Context cancelled; draining daemon tasks...")
	case sig := <-sigCh:
		slog.Info("daemon received signal; draining tasks...", "signal", sig.String())
		fmt.Fprintf(stdout, "Received signal %v; draining daemon tasks...\n", sig)
	}

	if drainErr := orchestrator.Drain(drainTimeout); drainErr != nil {
		slog.Warn("daemon drain timeout exceeded", "err", drainErr)
		fmt.Fprintf(stderr, "warning: drain timeout exceeded: %v\n", drainErr)
	}
	_ = orchestrator.Stop()

	slog.Info("producer daemon stopped cleanly")
	fmt.Fprintln(stdout, "Producer daemon stopped cleanly.")
	return 0
}
