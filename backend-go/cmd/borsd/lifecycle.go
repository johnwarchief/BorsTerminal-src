package main

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"sync"
	"time"
)

// RequestTracker ردگیری درخواست‌های در جریان و جلوگیری از پذیرش درخواست جدید پس از آغاز خاموشی را مدیریت می‌کند.
type RequestTracker struct {
	mu       sync.RWMutex
	stopping bool
	wg       sync.WaitGroup
}

func NewRequestTracker() *RequestTracker {
	return &RequestTracker{}
}

func (t *RequestTracker) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.mu.RLock()
		if t.stopping {
			t.mu.RUnlock()
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"status":"error","message":"server shutting down"}`))
			return
		}
		t.wg.Add(1)
		t.mu.RUnlock()
		defer t.wg.Done()
		next.ServeHTTP(w, r)
	})
}

// StopAccepting پذیرش درخواست‌های جدید را مسدود می‌کند. پس از این فراخوانی، هرگز wg.Add رخ نخواهد داد.
func (t *RequestTracker) StopAccepting() {
	t.mu.Lock()
	t.stopping = true
	t.mu.Unlock()
}

// WaitWithTimeout تا حداکثر مهلت داده‌شده برای تخلیهٔ Handlerهای فعال منتظر می‌ماند.
func (t *RequestTracker) WaitWithTimeout(d time.Duration) bool {
	done := make(chan struct{})
	go func() {
		t.wg.Wait()
		close(done)
	}()
	select {
	case <-done:
		return true
	case <-time.After(d):
		return false
	}
}

// ShutdownConfig پیکربندی مهلت‌های زمانی خاموشی سرور را مشخص می‌کند.
type ShutdownConfig struct {
	DrainTimeout    time.Duration
	HardKillTimeout time.Duration
}

// RunServer حلقه چرخه حیات سرور را اجرا می‌کند:
// ۱. گوش دادن روی Listener و لغو BaseContext با پایان rootCtx
// ۲. با دریافت سیگنال خروج: توقف پذیرش با tracker.StopAccepting()
// ۳. اجرای srv.Shutdown(drainCtx) با مهلت تعیین‌شده
// ۴. در صورت انقضای مهلت (مهلت ۵ ثانیه‌ای): اجرای srv.Close() برای بستن سوکت‌ها
// ۵. انتظار کنترل‌شده برای تخلیه Handlerها با tracker.WaitWithTimeout()
// ۶. فراخوانی closeResources دقیقاً پس از توقف کامل مسیرهای دسترسی
func RunServer(rootCtx context.Context, srv *http.Server, ln net.Listener, tracker *RequestTracker, cfg ShutdownConfig, closeResources func()) error {
	if cfg.DrainTimeout <= 0 {
		cfg.DrainTimeout = 5 * time.Second
	}
	if cfg.HardKillTimeout <= 0 {
		cfg.HardKillTimeout = 5 * time.Second
	}

	srv.BaseContext = func(net.Listener) context.Context {
		return rootCtx
	}

	serveErrCh := make(chan error, 1)
	go func() {
		if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
			serveErrCh <- err
		} else {
			serveErrCh <- nil
		}
	}()

	select {
	case err := <-serveErrCh:
		if closeResources != nil {
			closeResources()
		}
		return err
	case <-rootCtx.Done():
	}

	// ۱. توقف پذیرش جدید
	tracker.StopAccepting()

	// ۲. مهلت محترمانه
	drainCtx, cancelDrain := context.WithTimeout(context.Background(), cfg.DrainTimeout)
	defer cancelDrain()

	if err := srv.Shutdown(drainCtx); err != nil {
		slog.Warn("shutdown deadline exceeded; forcing close of active connections", "err", err)
		// ۳. بستن اجباری اتصالات باز
		_ = srv.Close()
	}

	// ۴. انتظار کنترل‌شده برای اتمام Handlerهای فعال
	drained := tracker.WaitWithTimeout(cfg.HardKillTimeout)
	if !drained {
		slog.Warn("some requests did not drain in time")
	}

	// ۵. بستن دیتابیس و سایر منابع فقط پس از توقف قطعی کلیه مسیرهای دسترسی
	if closeResources != nil {
		closeResources()
	}

	return nil
}
