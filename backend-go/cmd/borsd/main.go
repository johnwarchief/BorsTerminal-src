package main

import (
	"context"
	"log"
	"log/slog"
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
	handles, err := db.Open(cfg.DataDir, cfg.ReadOnly)
	if err != nil {
		slog.Error("db open failed", "err", err)
		os.Exit(1)
	}
	defer handles.Close()

	mkt := market.New(handles, cfg.DataDir)
	ms := mstat.New(handles.Market, cfg.DataDir, mkt)
	ch := chart.New(chart.Config{Market: handles.Market, User: handles.User,
		DataDir: cfg.DataDir, CalendarPath: cfg.CalendarPath})
	defer ch.Close()
	fd := fundamental.New(handles.Market, cfg.DataDir)
	defer fd.Close()

	wlStore, err := watchlist.NewStore(handles.User, cfg.DataDir)
	if err != nil {
		slog.Error("watchlist store init failed", "err", err)
		os.Exit(1)
	}
	wl := watchlist.NewHandler(wlStore)

	ntSvc := notifications.NewService(handles.Market)
	defer ntSvc.Close()
	nt := notifications.NewHandler(ntSvc)

	sy := borssync.NewHandler(cfg.DataDir)
	sel := selection.NewService(handles.Market, handles.User)
	mi := marketindex.NewService(cfg.DataDir, nil)
	exp := export.NewService(handles.Market)
	scr := screener.NewService(handles.Market, cfg.DataDir)
	fn := funnel.NewService(handles.Market, cfg.DataDir)

	srv := &http.Server{Addr: cfg.Addr,
		Handler: httpapi.NewWithServices(cfg, handles, httpapi.Services{
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
		})}
	go func() {
		slog.Info("listening", "addr", cfg.Addr, "data", cfg.DataDir, "version", httpapi.Version())
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("serve failed", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}
