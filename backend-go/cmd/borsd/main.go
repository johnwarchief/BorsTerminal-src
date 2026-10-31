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
	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/market"
	"borsterminal/backend/internal/mstat"
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
	fd := fundamental.New(handles.Market)
	defer fd.Close()
	srv := &http.Server{Addr: cfg.Addr,
		Handler: httpapi.New(cfg, handles, mkt, ms, ch, fd)}
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
