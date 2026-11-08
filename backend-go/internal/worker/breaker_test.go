package worker

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestCircuitBreaker_InitialState(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{})

	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected initial state StateClosed, got %v", state)
	}
	if !cb.Allow() {
		t.Fatalf("expected Allow to be true in initial StateClosed")
	}
	if rem := cb.RemainingCooldown(); rem != 0 {
		t.Fatalf("expected remaining cooldown 0 in StateClosed, got %v", rem)
	}
}

func TestCircuitBreaker_ClosedToOpen_Threshold(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 3,
		Cooldown:         100 * time.Millisecond,
	})

	errDummy := errors.New("temporary network error")

	// Failure 1
	cb.RecordFailure(errDummy, 0)
	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected StateClosed after 1 failure, got %v", state)
	}
	if !cb.Allow() {
		t.Fatalf("expected Allow to remain true after 1 failure")
	}

	// Failure 2
	cb.RecordFailure(errDummy, 0)
	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected StateClosed after 2 failures, got %v", state)
	}

	// Intermittent success resets failure counter
	cb.RecordSuccess()
	cb.RecordFailure(errDummy, 0) // Failure 1 again
	cb.RecordFailure(errDummy, 0) // Failure 2 again
	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected StateClosed after reset, got %v", state)
	}

	// Failure 3 -> trips threshold!
	cb.RecordFailure(errDummy, 0)
	if state := cb.State(); state != StateOpen {
		t.Fatalf("expected StateOpen after reaching FailureThreshold of 3, got %v", state)
	}
	if cb.Allow() {
		t.Fatalf("expected Allow to return false when StateOpen")
	}
}

func TestCircuitBreaker_OpenRejectsWithErrCircuitOpen(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         200 * time.Millisecond,
	})

	cb.RecordFailure(errors.New("fail"), 0)
	if cb.State() != StateOpen {
		t.Fatalf("expected StateOpen")
	}

	fnCalled := false
	err := cb.Execute(context.Background(), func() error {
		fnCalled = true
		return nil
	})

	if fnCalled {
		t.Fatalf("fn should not be executed when circuit is open")
	}
	if !errors.Is(err, ErrCircuitOpen) {
		t.Fatalf("expected ErrCircuitOpen, got: %v", err)
	}

	rem := cb.RemainingCooldown()
	if rem <= 0 || rem > 200*time.Millisecond {
		t.Fatalf("expected remaining cooldown between 0 and 200ms, got %v", rem)
	}
}

func TestCircuitBreaker_OpenToHalfOpen_CooldownElapsed(t *testing.T) {
	cooldown := 50 * time.Millisecond
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         cooldown,
	})

	cb.RecordFailure(errors.New("trip"), 0)
	if cb.State() != StateOpen {
		t.Fatalf("expected StateOpen")
	}

	// Wait for cooldown to expire
	time.Sleep(70 * time.Millisecond)

	// State() should now reflect StateHalfOpen
	if state := cb.State(); state != StateHalfOpen {
		t.Fatalf("expected StateHalfOpen after cooldown, got %v", state)
	}

	// Allow() should permit the probe request
	if !cb.Allow() {
		t.Fatalf("expected Allow() to return true for probing request in StateHalfOpen")
	}
}

func TestCircuitBreaker_HalfOpenToClosed_OnSuccess(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold:    1,
		Cooldown:            20 * time.Millisecond,
		HalfOpenMaxRequests: 1,
		SuccessThreshold:    1,
	})

	cb.RecordFailure(errors.New("trip"), 0)
	time.Sleep(30 * time.Millisecond)

	if !cb.Allow() {
		t.Fatalf("expected probe request to be allowed")
	}

	// Probe succeeds
	cb.RecordSuccess()

	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected StateClosed after probe success, got %v", state)
	}
	if !cb.Allow() {
		t.Fatalf("expected Allow() to return true after closing")
	}
}

func TestCircuitBreaker_HalfOpen_MultipleSuccessThreshold(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold:    1,
		Cooldown:            20 * time.Millisecond,
		HalfOpenMaxRequests: 1,
		SuccessThreshold:    3,
	})

	cb.RecordFailure(errors.New("trip"), 0)
	time.Sleep(30 * time.Millisecond)

	if cb.State() != StateHalfOpen {
		t.Fatalf("expected StateHalfOpen after cooldown, got %v", cb.State())
	}

	// 1st probe
	if !cb.Allow() {
		t.Fatalf("expected 1st probe to be allowed")
	}
	cb.RecordSuccess()
	if cb.State() != StateHalfOpen {
		t.Fatalf("expected StateHalfOpen after 1st success (threshold=3), got %v", cb.State())
	}

	// 2nd probe: previously blocked if halfOpenRequests was not decremented!
	if !cb.Allow() {
		t.Fatalf("expected 2nd probe to be allowed after 1st success")
	}
	cb.RecordSuccess()
	if cb.State() != StateHalfOpen {
		t.Fatalf("expected StateHalfOpen after 2nd success (threshold=3), got %v", cb.State())
	}

	// 3rd probe
	if !cb.Allow() {
		t.Fatalf("expected 3rd probe to be allowed")
	}
	cb.RecordSuccess()
	if cb.State() != StateClosed {
		t.Fatalf("expected StateClosed after 3rd success, got %v", cb.State())
	}

	// Breaker is now closed, requests should proceed freely
	if !cb.Allow() {
		t.Fatalf("expected Allow() to return true when closed")
	}
}

func TestCircuitBreaker_HalfOpenToOpen_OnFailure(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold:    1,
		Cooldown:            40 * time.Millisecond,
		HalfOpenMaxRequests: 1,
	})

	cb.RecordFailure(errors.New("trip"), 0)
	time.Sleep(50 * time.Millisecond)

	if !cb.Allow() {
		t.Fatalf("expected probe to be allowed in half-open")
	}

	// Probe fails!
	cb.RecordFailure(errors.New("probe failed"), 0)

	if state := cb.State(); state != StateOpen {
		t.Fatalf("expected StateOpen immediately after probe failure, got %v", state)
	}
	if cb.Allow() {
		t.Fatalf("expected Allow() to return false when re-tripped to StateOpen")
	}
	if rem := cb.RemainingCooldown(); rem <= 0 {
		t.Fatalf("expected cooldown timer to restart after probe failure, got %v", rem)
	}
}

func TestCircuitBreaker_HalfOpen_MaxRequests(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold:    1,
		Cooldown:            20 * time.Millisecond,
		HalfOpenMaxRequests: 1,
	})

	cb.RecordFailure(errors.New("trip"), 0)
	time.Sleep(30 * time.Millisecond)

	// First probe request allowed
	if !cb.Allow() {
		t.Fatalf("expected 1st request to be allowed in half-open")
	}

	// Second probe request while first is still inflight should be denied
	if cb.Allow() {
		t.Fatalf("expected 2nd concurrent probe to be blocked when HalfOpenMaxRequests=1")
	}
}

func TestCircuitBreaker_RetryAfter_Precedence(t *testing.T) {
	defaultCooldown := 50 * time.Millisecond
	retryAfter := 300 * time.Millisecond

	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 3,
		Cooldown:         defaultCooldown,
	})

	// Server returns 429 with explicit Retry-After
	cb.RecordFailure(errors.New("HTTP 429"), retryAfter)

	if state := cb.State(); state != StateOpen {
		t.Fatalf("expected StateOpen upon 429 Retry-After, got %v", state)
	}

	rem := cb.RemainingCooldown()
	// Should be roughly ~300ms, definitely larger than defaultCooldown of 50ms
	if rem <= defaultCooldown {
		t.Fatalf("expected remaining cooldown to exceed default cooldown (%v), got %v", defaultCooldown, rem)
	}

	// Wait past default cooldown (70ms)
	time.Sleep(70 * time.Millisecond)

	// Circuit should STILL be open because retryAfter takes precedence!
	if state := cb.State(); state != StateOpen {
		t.Fatalf("expected breaker to remain StateOpen past default cooldown due to Retry-After, got %v", state)
	}
	if cb.Allow() {
		t.Fatalf("expected Allow to be false while under Retry-After window")
	}
}

func TestCircuitBreaker_RetryAfter_SmallerThanCooldown(t *testing.T) {
	defaultCooldown := 150 * time.Millisecond
	smallRetryAfter := 20 * time.Millisecond

	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         defaultCooldown,
	})

	// Retry-After is smaller than default cooldown; server precedence specifies max(retryAfter, config.Cooldown)
	cb.RecordFailure(errors.New("HTTP 429"), smallRetryAfter)

	rem := cb.RemainingCooldown()
	if rem < 80*time.Millisecond {
		t.Fatalf("expected cooldown to be at least config.Cooldown (%v), got %v", defaultCooldown, rem)
	}
}

func TestCircuitBreaker_Execute_Success(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{})

	executed := false
	err := cb.Execute(context.Background(), func() error {
		executed = true
		return nil
	})

	if err != nil {
		t.Fatalf("expected nil error, got: %v", err)
	}
	if !executed {
		t.Fatalf("expected function to be executed")
	}
	if state := cb.State(); state != StateClosed {
		t.Fatalf("expected StateClosed, got %v", state)
	}
}

func TestCircuitBreaker_Execute_ContextCancelled(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{})

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Pre-cancelled

	err := cb.Execute(ctx, func() error {
		return nil
	})

	if err != context.Canceled {
		t.Fatalf("expected context.Canceled, got: %v", err)
	}
}

func TestCircuitBreaker_Execute_WithRateLimitError(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 3,
		Cooldown:         50 * time.Millisecond,
	})

	rateLimitErr := NewRateLimitError(200*time.Millisecond, "Too Many Requests")

	err := cb.Execute(context.Background(), func() error {
		return rateLimitErr
	})

	if !errors.Is(err, rateLimitErr) {
		t.Fatalf("expected rateLimitErr returned, got: %v", err)
	}
	if cb.State() != StateOpen {
		t.Fatalf("expected StateOpen after rate limit error")
	}

	rem := cb.RemainingCooldown()
	if rem < 100*time.Millisecond {
		t.Fatalf("expected Retry-After duration to be applied, got: %v", rem)
	}
}

func TestCircuitBreaker_Execute_StringPatternRetryAfter(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         50 * time.Millisecond,
	})

	stringErr := errors.New("upstream service error: Retry-After: 250")

	err := cb.Execute(context.Background(), func() error {
		return stringErr
	})

	if !errors.Is(err, stringErr) {
		t.Fatalf("expected stringErr, got: %v", err)
	}
	if cb.State() != StateOpen {
		t.Fatalf("expected StateOpen")
	}

	rem := cb.RemainingCooldown()
	// 250 seconds from pattern
	if rem < 200*time.Second {
		t.Fatalf("expected pattern parsed seconds (~250s), got: %v", rem)
	}
}

func TestCircuitBreaker_Execute_PanicRecovery(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         100 * time.Millisecond,
	})

	defer func() {
		r := recover()
		if r == nil {
			t.Fatalf("expected panic to propagate")
		}
		// Breaker should have recorded failure and tripped to Open
		if cb.State() != StateOpen {
			t.Fatalf("expected breaker to be StateOpen after panic, got %v", cb.State())
		}
	}()

	_ = cb.Execute(context.Background(), func() error {
		panic("unexpected nil pointer dereference")
	})
}

func TestCircuitBreaker_Reset(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 1,
		Cooldown:         10 * time.Second,
	})

	cb.RecordFailure(errors.New("fail"), 0)
	if cb.State() != StateOpen {
		t.Fatalf("expected StateOpen")
	}

	cb.Reset()
	if cb.State() != StateClosed {
		t.Fatalf("expected StateClosed after Reset, got %v", cb.State())
	}
	if !cb.Allow() {
		t.Fatalf("expected Allow to return true after Reset")
	}
}

func TestCircuitBreaker_ConcurrentAccess(t *testing.T) {
	cb := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold:    5,
		Cooldown:            20 * time.Millisecond,
		HalfOpenMaxRequests: 2,
		SuccessThreshold:    2,
	})

	var wg sync.WaitGroup
	var successCount int64
	var failureCount int64
	numWorkers := 30
	iterations := 100

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		workerID := i
		go func() {
			defer wg.Done()
			for j := 0; j < iterations; j++ {
				_ = cb.State()
				_ = cb.RemainingCooldown()

				if workerID%3 == 0 {
					cb.RecordFailure(errors.New("error"), 0)
					atomic.AddInt64(&failureCount, 1)
				} else {
					if cb.Allow() {
						cb.RecordSuccess()
						atomic.AddInt64(&successCount, 1)
					}
				}
			}
		}()
	}

	wg.Wait()

	if successCount+failureCount == 0 {
		t.Fatalf("expected concurrent operations to execute")
	}
}

func TestState_String(t *testing.T) {
	if StateClosed.String() != "CLOSED" {
		t.Fatalf("expected CLOSED, got %s", StateClosed.String())
	}
	if StateHalfOpen.String() != "HALF-OPEN" {
		t.Fatalf("expected HALF-OPEN, got %s", StateHalfOpen.String())
	}
	if StateOpen.String() != "OPEN" {
		t.Fatalf("expected OPEN, got %s", StateOpen.String())
	}
	if State(99).String() != "STATE(99)" {
		t.Fatalf("expected STATE(99), got %s", State(99).String())
	}
}
