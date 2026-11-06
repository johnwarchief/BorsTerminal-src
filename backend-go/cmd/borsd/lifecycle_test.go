package main

import (
	"context"
	"io"
	"net"
	"net/http"
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
