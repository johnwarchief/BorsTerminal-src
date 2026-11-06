package main

import (
	"context"
	"log"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"borsterminal/backend/internal/chart"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/export"
	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/funnel"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/market"
	"borsterminal/backend/internal/marketindex"
	"borsterminal/backend/internal/mstat"
	"borsterminal/backend/internal/notifications"
	borssync "borsterminal/backend/internal/sync"
	"borsterminal/backend/internal/screener"
	"borsterminal/backend/internal/selection"
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

	mkt := market.NewWithOptions(handles, cfg.DataDir, cfg.ReadOnly, cfg.NoLoops)
	ms := mstat.NewWithOptions(handles.Market, cfg.DataDir, mkt, cfg.NoLoops)
	ch := chart.New(chart.Config{Market: handles.Market, User: handles.User,
		DataDir: cfg.DataDir, CalendarPath: cfg.CalendarPath})
	fd := fundamental.New(handles.Market, cfg.DataDir)

	wlStore, err := watchlist.NewStore(handles.User, cfg.DataDir)
	if err != nil {
		slog.Error("watchlist store init failed", "err", err)
		_ = ch.Close()
		_ = fd.Close()
		_ = handles.Close()
		_ = ln.Close()
		os.Exit(1)
	}
	wl := watchlist.NewHandler(wlStore)

	ntSvc := notifications.NewService(handles.Market)
	nt := notifications.NewHandler(ntSvc)

	sy := borssync.NewHandler(cfg.DataDir)
	sel := selection.NewService(handles.Market, handles.User)
	mi := marketindex.NewService(cfg.DataDir, nil)
	exp := export.NewService(handles.Market)
	scr := screener.NewService(handles.Market, cfg.DataDir)
	fn := funnel.NewService(handles.Market, cfg.DataDir)

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
	})

	tracker := NewRequestTracker()
	srv := &http.Server{
		Addr:    cfg.Addr,
		Handler: tracker.Wrap(apiHandler),
	}

	rootCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	closeAll := func() {
		_ = ch.Close()
		_ = fd.Close()
		_ = ntSvc.Close()
		_ = handles.Close()
		slog.Info("all database handles and background resources closed")
	}

	slog.Info("listening", "addr", cfg.Addr, "data", cfg.DataDir, "version", httpapi.Version())

	shutdownCfg := ShutdownConfig{
		DrainTimeout:    5 * time.Second,
		HardKillTimeout: 2 * time.Second,
	}

	if err := RunServer(rootCtx, srv, ln, tracker, shutdownCfg, closeAll); err != nil {
		slog.Error("server error", "err", err)
		os.Exit(1)
	}
}
