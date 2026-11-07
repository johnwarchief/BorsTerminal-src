package main

import (
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestGracefulShutdownSuccess(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	mux := http.NewServeMux()
	mux.HandleFunc("/test", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	srv := &http.Server{Handler: tracker.Wrap(mux)}

	rootCtx, cancel := context.WithCancel(context.Background())
	var closed atomic.Bool
	closeResources := func() {
		closed.Store(true)
	}

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    1 * time.Second,
			HardKillTimeout: 1 * time.Second,
		}, closeResources)
	}()

	addr := ln.Addr().String()
	resp, err := http.Get("http://" + addr + "/test")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	body, _ := io.ReadAll(resp.Body)
	_ = resp.Body.Close()
	if string(body) != "ok" {
		t.Fatalf("unexpected body: %s", body)
	}

	// ارسال لغو
	cancel()

	select {
	case err := <-serverDone:
		if err != nil {
			t.Fatalf("unexpected server error: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server failed to shut down in time")
	}

	if !closed.Load() {
		t.Fatal("resources were not closed after server shutdown")
	}
}

func TestGracefulShutdownInFlightWaited(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	mux := http.NewServeMux()

	inFlightStarted := make(chan struct{})
	var handlerCompleted atomic.Bool
	var closedBeforeHandler atomic.Bool
	var closedResources atomic.Bool

	mux.HandleFunc("/slow", func(w http.ResponseWriter, r *http.Request) {
		close(inFlightStarted)
		time.Sleep(60 * time.Millisecond)
		if closedResources.Load() {
			closedBeforeHandler.Store(true)
		}
		handlerCompleted.Store(true)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("completed"))
	})

	srv := &http.Server{Handler: tracker.Wrap(mux)}
	rootCtx, cancel := context.WithCancel(context.Background())

	closeResources := func() {
		closedResources.Store(true)
	}

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    1 * time.Second,
			HardKillTimeout: 1 * time.Second,
		}, closeResources)
	}()

	addr := ln.Addr().String()

	// شروع درخواست کند در پس‌زمینه
	clientDone := make(chan error, 1)
	go func() {
		resp, err := http.Get("http://" + addr + "/slow")
		if err != nil {
			clientDone <- err
			return
		}
		defer resp.Body.Close()
		clientDone <- nil
	}()

	// صبر تا درخواست وارد Handler شود
	<-inFlightStarted

	// آغاز Shutdown همزمان با باز بودن درخواست
	cancel()

	// درخواست جدید بلافاصله پس از آغاز خاموشی باید با ۵۰۳ پس زده شود
	respAfterShutdown, err := http.Get("http://" + addr + "/slow")
	if err == nil {
		defer respAfterShutdown.Body.Close()
		if respAfterShutdown.StatusCode != http.StatusServiceUnavailable {
			t.Fatalf("expected 503 after shutdown started, got %d", respAfterShutdown.StatusCode)
		}
	}

	if err := <-clientDone; err != nil {
		t.Fatalf("in-flight request failed: %v", err)
	}

	if err := <-serverDone; err != nil {
		t.Fatalf("server shutdown error: %v", err)
	}

	if !handlerCompleted.Load() {
		t.Fatal("handler was not allowed to finish")
	}

	if closedBeforeHandler.Load() {
		t.Fatal("resources were closed BEFORE the handler finished!")
	}

	if !closedResources.Load() {
		t.Fatal("resources were never closed")
	}
}

func TestShutdownDeadlineExpiryTriggersClose(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	mux := http.NewServeMux()

	handlerRunning := make(chan struct{})
	var contextCancelled atomic.Bool

	mux.HandleFunc("/stuck", func(w http.ResponseWriter, r *http.Request) {
		close(handlerRunning)
		// این Handler منتظر می‌ماند تا context درخواست منقضی یا لغو شود
		<-r.Context().Done()
		contextCancelled.Store(true)
	})

	srv := &http.Server{Handler: tracker.Wrap(mux)}
	rootCtx, cancel := context.WithCancel(context.Background())

	var closedResources atomic.Bool
	closeResources := func() {
		closedResources.Store(true)
	}

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    30 * time.Millisecond, // مهلت تخلیه بسیار کوتاه تا srv.Shutdown خطا دهد
			HardKillTimeout: 200 * time.Millisecond,
		}, closeResources)
	}()

	addr := ln.Addr().String()
	go func() {
		_, _ = http.Get("http://" + addr + "/stuck")
	}()

	<-handlerRunning

	// لغو rootCtx برای شروع Shutdown
	cancel()

	select {
	case err := <-serverDone:
		if err != nil {
			t.Fatalf("server returned error: %v", err)
		}
	case <-time.After(1 * time.Second):
		t.Fatal("server timed out during forced close")
	}

	if !contextCancelled.Load() {
		t.Fatal("request context was not cancelled on forced shutdown")
	}

	if !closedResources.Load() {
		t.Fatal("resources were not closed after forced shutdown")
	}
}

func TestRequestTrackerRejectsNewRequestsAfterStop(t *testing.T) {
	tracker := NewRequestTracker()
	called := false
	handler := tracker.Wrap(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
	}))

	tracker.StopAccepting()

	// شبیه‌سازی درخواست
	rec := &fakeResponseWriter{header: make(http.Header)}
	req, _ := http.NewRequest("GET", "/test", nil)
	handler.ServeHTTP(rec, req)

	if called {
		t.Fatal("handler was called even after StopAccepting")
	}
	if rec.code != http.StatusServiceUnavailable {
		t.Fatalf("expected status 503, got %d", rec.code)
	}
}

type fakeResponseWriter struct {
	header http.Header
	code   int
	body   []byte
}

func (f *fakeResponseWriter) Header() http.Header { return f.header }
func (f *fakeResponseWriter) Write(b []byte) (int, error) {
	f.body = append(f.body, b...)
	return len(b), nil
}
func (f *fakeResponseWriter) WriteHeader(statusCode int) { f.code = statusCode }

func TestGracefulShutdownWorkerContextCancelled(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	mux := http.NewServeMux()
	mux.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("pong"))
	})

	srv := &http.Server{Handler: tracker.Wrap(mux)}
	rootCtx, cancel := context.WithCancel(context.Background())

	var workerCancelled atomic.Bool
	var closedResources atomic.Bool
	var workerClosedBeforeDB atomic.Bool

	workerDone := make(chan struct{})

	// شبیه‌سازی Worker پس‌زمینه که rootCtx دریافت می‌کند (مانند feed.Start(rootCtx))
	go func() {
		defer close(workerDone)
		select {
		case <-rootCtx.Done():
			workerCancelled.Store(true)
			// اطمینان از این‌که Worker پیش از بسته‌شدن دیتابیس لغو را دریافت می‌کند
			if !closedResources.Load() {
				workerClosedBeforeDB.Store(true)
			}
		case <-time.After(3 * time.Second):
		}
	}()

	closeResources := func() {
		closedResources.Store(true)
	}

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    100 * time.Millisecond,
			HardKillTimeout: 100 * time.Millisecond,
		}, closeResources)
	}()

	addr := ln.Addr().String()
	resp, err := http.Get("http://" + addr + "/ping")
	if err != nil {
		t.Fatalf("ping failed: %v", err)
	}
	_ = resp.Body.Close()

	// ارسال سیگنال خاموشی
	cancel()

	select {
	case <-workerDone:
	case <-time.After(1 * time.Second):
		t.Fatal("worker did not exit on rootCtx cancellation")
	}

	select {
	case err := <-serverDone:
		if err != nil {
			t.Fatalf("server returned error: %v", err)
		}
	case <-time.After(1 * time.Second):
		t.Fatal("server did not shut down in time")
	}

	if !workerCancelled.Load() {
		t.Fatal("worker did not receive context cancellation")
	}
	if !workerClosedBeforeDB.Load() {
		t.Fatal("worker observed resources already closed")
	}
	if !closedResources.Load() {
		t.Fatal("resources were not closed")
	}
}

func TestResourceCloseOrder(t *testing.T) {
	var order []string
	var mu sync.Mutex
	record := func(name string) {
		mu.Lock()
		defer mu.Unlock()
		order = append(order, name)
	}

	feedClosed := false
	dbClosed := false

	closeFeed := func() {
		record("feed")
		feedClosed = true
	}
	closeDB := func() {
		if !feedClosed {
			t.Error("DB closed before feed!")
		}
		record("db")
		dbClosed = true
	}

	closeAll := func() {
		closeFeed()
		closeDB()
	}

	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	srv := &http.Server{Handler: tracker.Wrap(http.NewServeMux())}
	rootCtx, cancel := context.WithCancel(context.Background())

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    50 * time.Millisecond,
			HardKillTimeout: 50 * time.Millisecond,
		}, closeAll)
	}()

	cancel()

	select {
	case err := <-serverDone:
		if err != nil {
			t.Fatalf("server returned error: %v", err)
		}
	case <-time.After(1 * time.Second):
		t.Fatal("server did not exit")
	}

	mu.Lock()
	defer mu.Unlock()
	if !feedClosed || !dbClosed {
		t.Fatalf("not all resources closed: %v", order)
	}
	if len(order) != 2 || order[0] != "feed" || order[1] != "db" {
		t.Fatalf("unexpected close order: %v", order)
	}
}

// TestGracefulShutdownUncooperativeHandler تضمین می‌کند که اگر یک Handler غیرهمکار و طولانی
// سیگنال لغو Context را نادیده بگیرد و پس از انقضای هر دو مهلت Drain و HardKill همچنان به کار
// ادامه دهد، دیتابیس هرگز زیر پای آن بسته نخواهد شد و به دیتابیس بسته دسترسی پیدا نمی‌کند.
func TestGracefulShutdownUncooperativeHandler(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}

	tracker := NewRequestTracker()
	mux := http.NewServeMux()

	handlerStarted := make(chan struct{})
	handlerFinished := make(chan struct{})

	var dbTouchedAfterHardTimeout atomic.Bool
	var dbClosedWhileHandlerActive atomic.Bool
	var dbWasClosed atomic.Bool
	var handlerSawClosedDB atomic.Bool

	// شبیه‌سازی عملیات دیتابیس
	queryDB := func() error {
		if dbWasClosed.Load() {
			handlerSawClosedDB.Store(true)
			return errors.New("sql: database is closed")
		}
		return nil
	}

	// یک Handler کاملاً غیرهمکار که Context.Done را نادیده می‌گیرد و به کار ادامه می‌دهد
	mux.HandleFunc("/uncooperative", func(w http.ResponseWriter, r *http.Request) {
		close(handlerStarted)

		// این هندلر عمداً لغو context را نادیده می‌گیرد و ۱۵۰ میلی‌ثانیه می‌خوابد
		// (بسیار بیشتر از مجموع DrainTimeout و HardKillTimeout)
		time.Sleep(150 * time.Millisecond)

		// هندلر پس از منقضی شدن مهلت‌های خاموشی، تلاش می‌کند دیتابیس را بخواند
		dbTouchedAfterHardTimeout.Store(true)
		if dbWasClosed.Load() {
			dbClosedWhileHandlerActive.Store(true)
		}
		if err := queryDB(); err != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("done"))
		close(handlerFinished)
	})

	srv := &http.Server{Handler: tracker.Wrap(mux)}
	rootCtx, cancel := context.WithCancel(context.Background())

	closeResources := func() {
		dbWasClosed.Store(true)
	}

	serverDone := make(chan error, 1)
	go func() {
		serverDone <- RunServer(rootCtx, srv, ln, tracker, ShutdownConfig{
			DrainTimeout:    30 * time.Millisecond,
			HardKillTimeout: 40 * time.Millisecond,
		}, closeResources)
	}()

	addr := ln.Addr().String()

	// ۱. شروع درخواست غیرهمکار در کلاینت
	go func() {
		resp, err := http.Get("http://" + addr + "/uncooperative")
		if err == nil {
			_ = resp.Body.Close()
		}
	}()

	// صبر تا هندلر آغاز شود
	<-handlerStarted

	// ۲. ارسال سیگنال خاموشی سرور
	cancel()

	// ۳. سرور باید پس از اتمام مهلت‌ها با ErrShutdownTimeout خارج شود
	//    و دیتابیس را نبندد چون هندلر هنوز فعال است
	select {
	case err := <-serverDone:
		if !errors.Is(err, ErrShutdownTimeout) {
			t.Fatalf("expected ErrShutdownTimeout, got %v", err)
		}
	case <-time.After(500 * time.Millisecond):
		t.Fatal("server failed to exit within hard timeout")
	}

	// درخواست‌های جدید بلافاصله پس از شروع خاموشی ۵۰۳ می‌گیرند
	respAfter, err := http.Get("http://" + addr + "/uncooperative")
	if err == nil {
		_ = respAfter.Body.Close()
		if respAfter.StatusCode != http.StatusServiceUnavailable {
			t.Fatalf("expected 503 after shutdown, got %d", respAfter.StatusCode)
		}
	}

	// ۴. صبر برای اتمام طبیعی هندلر غیرهمکار
	select {
	case <-handlerFinished:
	case <-time.After(1 * time.Second):
		t.Fatal("uncooperative handler did not finish")
	}

	// ۵. اعتبارسنجی قطعی:
	// الف) هندلر دیتابیس را لمس کرد
	if !dbTouchedAfterHardTimeout.Load() {
		t.Fatal("uncooperative handler did not attempt DB touch")
	}
	// ب) دیتابیس هرگز در حین فعالیت هندلر بسته نشد
	if dbClosedWhileHandlerActive.Load() {
		t.Fatal("CRITICAL: database was closed while uncooperative handler was still active!")
	}
	// ج) هندلر هرگز خطای بسته بودن دیتابیس ندید
	if handlerSawClosedDB.Load() {
		t.Fatal("CRITICAL: uncooperative handler observed closed database error!")
	}
	// د) closeResources در زمان فرار سرور فراخوانی نشد (جهت محافظت از هندلرهای فعال)
	if dbWasClosed.Load() {
		t.Fatal("resources were prematurely closed before handler finished")
	}

	// پس از اتمام کلیه هندلرها، منابع اکنون با ایمنی ۱۰۰٪ بسته می‌شوند
	closeResources()
	if !dbWasClosed.Load() {
		t.Fatal("resources were not closed after handler completed")
	}
}
