package worker

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestRateLimiter_BurstCapacity(t *testing.T) {
	burst := 5
	rate := 1.0 // 1 token per second
	rl := NewRateLimiter(rate, burst)

	if got := rl.Burst(); got != burst {
		t.Fatalf("expected burst %d, got %d", burst, got)
	}
	if got := rl.Rate(); got != rate {
		t.Fatalf("expected rate %f, got %f", rate, got)
	}

	// Consume all burst tokens immediately
	for i := 0; i < burst; i++ {
		if !rl.Allow() {
			t.Fatalf("expected token %d to be allowed", i+1)
		}
	}

	// Next immediate call should be rejected
	if rl.Allow() {
		t.Fatalf("expected 6th call to be rejected after consuming burst of 5")
	}
}

func TestRateLimiter_TokenRegeneration(t *testing.T) {
	burst := 3
	rate := 20.0 // 20 tokens per second -> 1 token every 50ms
	rl := NewRateLimiter(rate, burst)

	// Drain the bucket
	for i := 0; i < burst; i++ {
		if !rl.Allow() {
			t.Fatalf("expected initial burst token %d", i+1)
		}
	}
	if rl.Allow() {
		t.Fatalf("bucket should be empty")
	}

	// Wait 60ms for at least 1 token to regenerate
	time.Sleep(65 * time.Millisecond)
	if !rl.Allow() {
		t.Fatalf("expected regenerated token to be available after 65ms")
	}
	if rl.Allow() {
		t.Fatalf("expected only 1 token to have regenerated")
	}

	// Wait 180ms for bucket to regenerate up to burst capacity (3)
	time.Sleep(180 * time.Millisecond)

	count := 0
	for rl.Allow() {
		count++
	}
	if count > burst {
		t.Fatalf("regenerated tokens exceeded burst capacity: got %d, burst %d", count, burst)
	}
	if count < 2 {
		t.Fatalf("expected at least 2 regenerated tokens, got %d", count)
	}
}

func TestRateLimiter_Wait_Success(t *testing.T) {
	burst := 1
	rate := 40.0 // 1 token every 25ms
	rl := NewRateLimiter(rate, burst)

	// Consume the initial token
	if !rl.Allow() {
		t.Fatalf("expected initial token to be allowed")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	start := time.Now()
	err := rl.Wait(ctx)
	elapsed := time.Since(start)

	if err != nil {
		t.Fatalf("expected Wait to succeed, got: %v", err)
	}

	// Should have waited roughly ~25ms
	if elapsed < 15*time.Millisecond {
		t.Fatalf("Wait returned too quickly: %v", elapsed)
	}
}

func TestRateLimiter_Wait_ContextCancellation(t *testing.T) {
	burst := 1
	rate := 0.2 // 1 token every 5 seconds
	rl := NewRateLimiter(rate, burst)

	// Consume initial token
	if !rl.Allow() {
		t.Fatalf("expected initial token to be allowed")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()

	start := time.Now()
	err := rl.Wait(ctx)
	elapsed := time.Since(start)

	if err == nil {
		t.Fatalf("expected context deadline error, got nil")
	}
	if err != context.DeadlineExceeded {
		t.Fatalf("expected context.DeadlineExceeded, got: %v", err)
	}
	if elapsed < 25*time.Millisecond || elapsed > 100*time.Millisecond {
		t.Fatalf("unexpected cancellation duration: %v", elapsed)
	}
}

func TestRateLimiter_Wait_AlreadyCancelled(t *testing.T) {
	rl := NewRateLimiter(10.0, 5)

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	err := rl.Wait(ctx)
	if err != context.Canceled {
		t.Fatalf("expected context.Canceled, got: %v", err)
	}
}

func TestRateLimiter_AllowN_And_WaitN(t *testing.T) {
	rl := NewRateLimiter(50.0, 5)

	// AllowN with 0 or negative
	if !rl.AllowN(0) || !rl.AllowN(-1) {
		t.Fatalf("AllowN with <=0 should return true")
	}

	// Consume 3 out of 5 tokens
	if !rl.AllowN(3) {
		t.Fatalf("expected 3 tokens to be allowed")
	}

	// Trying to consume 3 more should fail (only 2 left)
	if rl.AllowN(3) {
		t.Fatalf("expected AllowN(3) to fail when only 2 tokens remaining")
	}

	// Consume the remaining 2 tokens
	if !rl.AllowN(2) {
		t.Fatalf("expected AllowN(2) to consume remaining 2 tokens")
	}

	// WaitN for 0 should return immediately
	if err := rl.WaitN(context.Background(), 0); err != nil {
		t.Fatalf("WaitN with 0 returned error: %v", err)
	}
}

func TestRateLimiter_WaitN_ExceedsBurst(t *testing.T) {
	rl := NewRateLimiter(10.0, 5)

	err := rl.WaitN(context.Background(), 10)
	if err == nil {
		t.Fatalf("expected error when requesting tokens exceeding burst capacity, got nil")
	}
	if !errors.Is(err, ErrExceedsBurst) {
		t.Fatalf("expected ErrExceedsBurst, got: %v", err)
	}
}

func TestRateLimiter_ZeroOrNegativeParameters(t *testing.T) {
	rl := NewRateLimiter(-5.0, -10)
	if rl.Burst() != 1 {
		t.Fatalf("expected burst 1 for non-positive input, got %d", rl.Burst())
	}
	if rl.Rate() != 0 {
		t.Fatalf("expected rate 0 for negative input, got %f", rl.Rate())
	}

	// Can consume burst of 1
	if !rl.Allow() {
		t.Fatalf("expected initial burst token to be allowed")
	}
	// Once drained and rate=0, Allow fails
	if rl.Allow() {
		t.Fatalf("expected Allow to fail when empty and rate=0")
	}

	// Wait with rate=0 should respect context cancel
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()

	err := rl.Wait(ctx)
	if err != context.DeadlineExceeded {
		t.Fatalf("expected DeadlineExceeded for rate=0 wait, got: %v", err)
	}
}

func TestRateLimiter_ConcurrentSafety(t *testing.T) {
	rate := 1000.0
	burst := 50
	rl := NewRateLimiter(rate, burst)

	var wg sync.WaitGroup
	var allowedCount int64
	numWorkers := 20
	iterations := 100

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				if rl.Allow() {
					atomic.AddInt64(&allowedCount, 1)
				}
				// Also occasionally read properties
				_ = rl.Tokens()
				_ = rl.Burst()
				_ = rl.Rate()
			}
		}()
	}

	wg.Wait()

	if allowedCount <= 0 {
		t.Fatalf("expected at least some tokens to be allowed, got %d", allowedCount)
	}
}
