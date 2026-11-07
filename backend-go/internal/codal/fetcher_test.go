package codal_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"borsterminal/backend/internal/codal"
)

func TestPoliteClient_RetryAfter_Seconds(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att == 1 {
			w.Header().Set("Retry-After", "3")
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte("too many requests"))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient: server.Client(),
	})

	ctx := context.Background()
	start := time.Now()

	body, status, err := client.Get(ctx, server.URL)
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if status != http.StatusOK {
		t.Fatalf("expected status 200, got %d", status)
	}
	if string(body) != `{"status":"ok"}` {
		t.Fatalf("unexpected body: %s", string(body))
	}
	if atomic.LoadInt32(&attempts) != 2 {
		t.Fatalf("expected 2 attempts, got %d", atomic.LoadInt32(&attempts))
	}
	// Assert that client waited at least 3 seconds (allowing small timer jitter)
	if elapsed < 3*time.Second-50*time.Millisecond {
		t.Fatalf("expected client to wait at least 3 seconds for Retry-After, elapsed: %v", elapsed)
	}
}

func TestPoliteClient_RetryAfter_HTTPDate(t *testing.T) {
	var attempts int32
	// Target time 2 seconds in future, formatted as HTTP-date (RFC 1123)
	targetTime := time.Now().Add(2 * time.Second).Truncate(time.Second)
	httpDateStr := targetTime.UTC().Format(http.TimeFormat)
	parsedTarget, _ := http.ParseTime(httpDateStr)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att == 1 {
			w.Header().Set("Retry-After", httpDateStr)
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte("rate limited"))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("success date"))
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient: server.Client(),
	})

	ctx := context.Background()
	body, status, err := client.Get(ctx, server.URL)
	finish := time.Now()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if status != http.StatusOK {
		t.Fatalf("expected status 200, got %d", status)
	}
	if string(body) != "success date" {
		t.Fatalf("expected 'success date', got %s", string(body))
	}
	// Assert that client waited until or past the parsed HTTP-date
	if finish.Before(parsedTarget) {
		t.Fatalf("client finished at %v which is before target HTTP-date %v", finish, parsedTarget)
	}
}

func TestPoliteClient_ConcurrencyLimit(t *testing.T) {
	var activeReqs int32
	var maxActive int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		curr := atomic.AddInt32(&activeReqs, 1)
		defer atomic.AddInt32(&activeReqs, -1)

		for {
			oldMax := atomic.LoadInt32(&maxActive)
			if curr <= oldMax || atomic.CompareAndSwapInt32(&maxActive, oldMax, curr) {
				break
			}
		}

		time.Sleep(50 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	}))
	defer server.Close()

	// Concurrency cap = 2
	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		MaxConcurrency: 2,
		HTTPClient:     server.Client(),
	})

	var wg sync.WaitGroup
	ctx := context.Background()
	for i := 0; i < 6; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _, _ = client.Get(ctx, server.URL)
		}()
	}
	wg.Wait()

	if maxActive > 2 {
		t.Fatalf("concurrency limit breached: max concurrent requests was %d, expected <= 2", maxActive)
	}
}

func TestPoliteClient_ExponentialBackoff_5xx(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att < 3 {
			w.WriteHeader(http.StatusBadGateway)
			_, _ = w.Write([]byte("bad gateway"))
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("recovered"))
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		MaxRetries: 3,
		BaseDelay:  20 * time.Millisecond,
		MaxDelay:   200 * time.Millisecond,
		HTTPClient: server.Client(),
	})

	ctx := context.Background()
	body, status, err := client.Get(ctx, server.URL)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if status != http.StatusOK {
		t.Fatalf("expected status 200, got %d", status)
	}
	if string(body) != "recovered" {
		t.Fatalf("expected 'recovered', got %s", string(body))
	}
	if atomic.LoadInt32(&attempts) != 3 {
		t.Fatalf("expected 3 attempts, got %d", atomic.LoadInt32(&attempts))
	}
}

func TestPoliteClient_ContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "10")
		w.WriteHeader(http.StatusTooManyRequests)
		_, _ = w.Write([]byte("rate limited"))
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient: server.Client(),
	})

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	start := time.Now()
	_, _, err := client.Get(ctx, server.URL)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatalf("expected context cancellation error, got nil")
	}
	if elapsed > 1*time.Second {
		t.Fatalf("client did not abort quickly on context cancel, took %v", elapsed)
	}
}
