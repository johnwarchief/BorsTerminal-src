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

	"borsterminal/backend/internal/auth"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/instance"
	"borsterminal/backend/internal/seed"
)

func main() {
	cfg, err := config.Load(os.Args[1:], os.Getenv)
	if err != nil {
		log.Fatal(err)
	}

	// بررسی اتصال پورت پیش از باز کردن دیتابیس‌ها تا در صورت اشغال بودن، خطای فوری با کد ۱ داده شود
	ln, err := bindListener(cfg.Addr)
	if err != nil {
		slog.Error("bind failed", "addr", cfg.Addr, "err", err)
		os.Exit(1)
	}

	rootCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// یک borsd برایِ هر dataDir؛ دو نویسنده رویِ oc_client.db مجاز نیست.
	lock, err := instance.Acquire(cfg.DataDir)
	if err != nil {
		slog.Error("single-instance lock failed", "err", err, "data", cfg.DataDir)
		_ = ln.Close()
		os.Exit(1)
	}

	// نگه‌داشتنِ دادهٔ تاریخیِ بسته: نصاب یک market.dbِ تک‌روزه و یک
	// market.db.lzmaِ کامل کنارِ هم می‌گذارد. این مرحله پیش از باز شدنِ
	// دیتابیس (و پیش از هر نویسندهٔ دیگر، چون قفلِ تک‌نمونه گرفته شده) یا
	// seed را استخراج می‌کند یا ردیف‌هایش را در یک کپی ادغام می‌کند و فقط
	// پس از اعتبارسنجی، فایل را اتمیک جایگزین می‌کند.
	seedRes, seedErr := seed.Ensure(seed.Options{DataDir: cfg.DataDir, SeedPath: os.Getenv("BORS_SEED_PATH"), Logger: slog.Default()})
	if seedErr != nil {
		slog.Warn("market seed not applied; continuing with the existing database", "err", seedErr, "data", cfg.DataDir)
	} else if seedRes.Applied {
		slog.Info("market seed applied",
			"mode", seedRes.Mode,
			"price_rows", seedRes.State.PriceHistoryRows,
			"first_candle", seedRes.State.PriceHistoryFirst,
			"last_candle", seedRes.State.PriceHistoryLast,
			"backup", seedRes.State.Backup,
			"data", cfg.DataDir)
	} else {
		slog.Info("market seed skipped", "reason", seedRes.Reason, "data", cfg.DataDir)
	}

	rt, err := newRuntime(rootCtx, cfg)
	if err != nil {
		slog.Error("runtime init failed", "err", err)
		_ = lock.Release()
		_ = ln.Close()
		os.Exit(1)
	}

	tok, err := auth.NewToken(cfg.DataDir, os.Getenv)
	if err != nil {
		slog.Error("api token init failed", "err", err)
		rt.Close()
		_ = lock.Release()
		_ = ln.Close()
		os.Exit(1)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	hosts := auth.LoopbackHosts(port)
	guard := auth.NewGuard(auth.GuardConfig{
		Token:          tok.Value,
		AllowedHosts:   hosts,
		AllowedOrigins: auth.OriginsFor(hosts),
	})

	tracker := NewRequestTracker()
	srv := &http.Server{
		Addr:    cfg.Addr,
		Handler: tracker.Wrap(guard.Wrap(rt)),
	}

	slog.Info("listening", "addr", ln.Addr().String(), "data", cfg.DataDir, "static", cfg.StaticDir,
		"service_version", serviceVersion(), "generation", rt.DataStatus()["serving"],
		"token_file", tok.File)

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

	closeAll := func() {
		rt.Close()
		_ = lock.Release()
		slog.Info("all database handles and background resources closed")
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

func serviceVersion() string {
	// نسخهٔ کامل سرویس در httpapi.Version است؛ این فقط شناسهٔ لایهٔ P0 است.
	return "oc-p0"
}

// bindListener تنها درگاهِ ساختِ Listener است تا پورتِ اشغال در تست هم همان
// رفتارِ fail-fastِ اجرایِ واقعی را داشته باشد.
func bindListener(addr string) (net.Listener, error) {
	return net.Listen("tcp", addr)
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
