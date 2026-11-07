package main

import (
	"context"
	"errors"
	"log"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	"borsterminal/backend/internal/chart"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/export"
	"borsterminal/backend/internal/ftsconfig"
	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/funnel"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/live"
	"borsterminal/backend/internal/market"
	"borsterminal/backend/internal/marketindex"
	"borsterminal/backend/internal/mstat"
	"borsterminal/backend/internal/notifications"
	"borsterminal/backend/internal/screener"
	"borsterminal/backend/internal/selection"
	borssync "borsterminal/backend/internal/sync"
	"borsterminal/backend/internal/watchlist"
)

func main() {
	cfg, err := config.Load(os.Args[1:], os.Getenv)
	if err != nil {
		log.Fatal(err)
	}

	// بررسی اتصال پورت پیش از باز کردن دیتابیس‌ها تا در صورت اشغال بودن، خطای فوری با کد ۱ داده شود
	ln, err := net.Listen("tcp", cfg.Addr)
	if err != nil {
		slog.Error("bind failed", "addr", cfg.Addr, "err", err)
		os.Exit(1)
	}

	handles, err := db.Open(cfg.DataDir, cfg.ReadOnly)
	if err != nil {
		slog.Error("db open failed", "err", err)
		_ = ln.Close()
		os.Exit(1)
	}

	rootCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	mkt := market.NewWithOptions(handles, cfg.DataDir, cfg.ReadOnly, cfg.NoLoops)
	var liveFeed *live.Feed
	// Only one TSE live loop may exist at a time (owner decision §9). The Go
	// feed is opt-in so a Python live loop can stay the sole owner until the
	// operator flips BORS_GO_LIVE=1 and stops it.
	// In addition, if cfg.NoLoops is active, no background loop may start.
	// And if cfg.ReadOnly is active, live persistence to market.db is strictly forbidden.
	if !cfg.NoLoops && (os.Getenv("BORS_GO_LIVE") == "1" || os.Getenv("BORS_GO_LIVE") == "true" || os.Getenv("BORS_GO_LIVE") == "yes") {
		interval := 1500 * time.Millisecond
		if ms, err := strconv.Atoi(os.Getenv("BORS_GO_LIVE_MS")); err == nil && ms >= 500 {
			interval = time.Duration(ms) * time.Millisecond
		}
		feed := live.New(interval)
		if !cfg.ReadOnly && (os.Getenv("BORS_GO_LIVE_PERSIST") != "0" && os.Getenv("BORS_GO_LIVE_PERSIST") != "false" && os.Getenv("BORS_GO_LIVE_PERSIST") != "no") {
			feed.EnablePersistence(filepath.Join(cfg.DataDir, "market.db"), 5*time.Second)
		}
		mkt.Live = feed
		liveFeed = feed
		feed.Start(rootCtx)
		slog.Info("live TSE feed enabled", "interval", interval.String())
	}
	ms := mstat.NewWithOptions(handles.Market, cfg.DataDir, mkt, cfg.NoLoops)
	ch := chart.New(chart.Config{Market: handles.Market, User: handles.User,
		DataDir: cfg.DataDir, CalendarPath: cfg.CalendarPath})
	fd := fundamental.New(handles.Market, cfg.DataDir)

	wlStore, err := watchlist.NewStore(handles.User, cfg.DataDir)
	if err != nil {
		slog.Error("watchlist store init failed", "err", err)
		if liveFeed != nil {
			_ = liveFeed.Close()
		}
		_ = ch.Close()
		_ = fd.Close()
		_ = handles.Close()
		_ = ln.Close()
		os.Exit(1)
	}
	wl := watchlist.NewHandler(wlStore, cfg.ReadOnly)

	ntSvc := notifications.NewService(handles.Market)
	nt := notifications.NewHandler(ntSvc)

	sy := borssync.NewHandler(cfg.DataDir)
	sel := selection.NewService(handles.Market, handles.User)
	mi := marketindex.NewService(cfg.DataDir, nil)
	exp := export.NewService(handles.Market)
	scr := screener.NewService(handles.Market, cfg.DataDir)
	fn := funnel.NewService(handles.Market, cfg.DataDir)

	ftsCfgStore, err := ftsconfig.NewStore(handles.User)
	if err != nil {
		slog.Error("fts config store init failed", "err", err)
	}
	ftsCfg := ftsconfig.NewHandler(ftsCfgStore, cfg.ReadOnly)

	apiHandler := httpapi.NewWithServices(cfg, handles, httpapi.Services{
		Market:        mkt,
		Mstat:         ms,
		Chart:         ch,
		Fundamental:   fd,
		Watchlist:     wl,
		Notifications: nt,
		Sync:          sy,
		Selection:     sel,
		MarketIndex:   mi,
		Export:        exp,
		Screener:      scr,
		Funnel:        fn,
		FtsConfig:     ftsCfg,
	})

	tracker := NewRequestTracker()
	srv := &http.Server{
		Addr:    cfg.Addr,
		Handler: tracker.Wrap(apiHandler),
	}

	closeAll := func() {
		if liveFeed != nil {
			_ = liveFeed.Close()
		}
		_ = ch.Close()
		_ = fd.Close()
		_ = ntSvc.Close()
		_ = handles.Close()
		slog.Info("all database handles and background resources closed")
	}

	slog.Info("listening", "addr", cfg.Addr, "data", cfg.DataDir, "static", cfg.StaticDir, "version", httpapi.Version())

	if !cfg.NoShell {
		shellExe := findShellExe()
		if shellExe != "" {
			appURL := "http://" + ln.Addr().String()
			slog.Info("launching desktop shell", "exe", shellExe, "url", appURL)
			shellCmd := exec.Command(shellExe, "--url", appURL, "--parent-pid", strconv.Itoa(os.Getpid()))
			shellCmd.Stdout = os.Stdout
			shellCmd.Stderr = os.Stderr
			if err := shellCmd.Start(); err != nil {
				slog.Warn("failed to start desktop shell", "err", err)
			} else {
				go func() {
					_ = shellCmd.Wait()
					slog.Info("desktop shell window closed; initiating shutdown")
					stop()
				}()
			}
		}
	}

	shutdownCfg := ShutdownConfig{
		DrainTimeout:    5 * time.Second,
		HardKillTimeout: 5 * time.Second,
	}

	if err := RunServer(rootCtx, srv, ln, tracker, shutdownCfg, closeAll); err != nil {
		if errors.Is(err, ErrShutdownTimeout) {
			slog.Error("server forced exit: active in-flight requests did not drain in time", "err", err)
			os.Exit(1)
		}
		slog.Error("server error", "err", err)
		os.Exit(1)
	}
}

func findShellExe() string {
	var candidates []string
	if self, err := os.Executable(); err == nil {
		candidates = append(candidates, filepath.Join(filepath.Dir(self), "BorsTerminal_Shell.exe"))
	}
	candidates = append(candidates,
		filepath.Join(".", "BorsTerminal_Shell.exe"),
		filepath.Join(".", "dist", "BorsTerminal_Ultimate", "BorsTerminal_Shell.exe"),
	)
	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil && !fi.IsDir() {
			if abs, err := filepath.Abs(c); err == nil {
				return abs
			}
			return c
		}
	}
	return ""
}
