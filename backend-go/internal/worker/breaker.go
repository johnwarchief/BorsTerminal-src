package worker

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

// State represents the lifecycle state of a CircuitBreaker.
type State int

const (
	// StateClosed allows requests to proceed normally.
	StateClosed State = iota
	// StateHalfOpen probes the downstream service with a restricted number of requests.
	StateHalfOpen
	// StateOpen fails requests immediately to prevent cascading failures or IP bans.
	StateOpen
)

// String returns the human-readable name of the State.
func (s State) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateHalfOpen:
		return "HALF-OPEN"
	case StateOpen:
		return "OPEN"
	default:
		return fmt.Sprintf("STATE(%d)", int(s))
	}
}

// ErrCircuitOpen is returned by Execute when the circuit breaker is open or probe slots are exhausted.
var ErrCircuitOpen = errors.New("circuit breaker is open")

// CircuitBreakerConfig defines configuration parameters for CircuitBreaker.
type CircuitBreakerConfig struct {
	// FailureThreshold is the number of consecutive failures before tripping to StateOpen. Default: 3.
	FailureThreshold int
	// Cooldown is the default duration to stay in StateOpen before transitioning to StateHalfOpen. Default: 30s.
	Cooldown time.Duration
	// HalfOpenMaxRequests is the maximum concurrent probe requests allowed in StateHalfOpen. Default: 1.
	HalfOpenMaxRequests int
	// SuccessThreshold is the number of consecutive successes required in StateHalfOpen to close the circuit. Default: 1.
	SuccessThreshold int
}

// CircuitBreaker guards downstream operations against repeated failures,
// supporting server-driven Retry-After header precedence.
type CircuitBreaker struct {
	mu               sync.Mutex
	config           CircuitBreakerConfig
	state            State
	failureCount     int
	successCount     int
	halfOpenRequests int
	openExpiry       time.Time
}

// NewCircuitBreaker creates and initializes a CircuitBreaker with sensible defaults.
func NewCircuitBreaker(config CircuitBreakerConfig) *CircuitBreaker {
	if config.FailureThreshold <= 0 {
		config.FailureThreshold = 3
	}
	if config.Cooldown <= 0 {
		config.Cooldown = 30 * time.Second
	}
	if config.HalfOpenMaxRequests <= 0 {
		config.HalfOpenMaxRequests = 1
	}
	if config.SuccessThreshold <= 0 {
		config.SuccessThreshold = 1
	}

	return &CircuitBreaker{
		config: config,
		state:  StateClosed,
	}
}

// State returns the current State of the CircuitBreaker.
// If the breaker is StateOpen and its cooldown has expired, it automatically transitions to StateHalfOpen.
func (cb *CircuitBreaker) State() State {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if cb.state == StateOpen && !time.Now().Before(cb.openExpiry) {
		cb.state = StateHalfOpen
		cb.halfOpenRequests = 0
		cb.successCount = 0
	}

	return cb.state
}

// Allow reports whether a request is permitted to proceed.
// If the breaker is StateOpen and the cooldown has expired, it transitions to StateHalfOpen.
// In StateHalfOpen, only up to HalfOpenMaxRequests are permitted.
func (cb *CircuitBreaker) Allow() bool {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	if cb.state == StateOpen {
		if !now.Before(cb.openExpiry) {
			cb.state = StateHalfOpen
			cb.halfOpenRequests = 0
			cb.successCount = 0
		} else {
			return false
		}
	}

	if cb.state == StateHalfOpen {
		if cb.halfOpenRequests < cb.config.HalfOpenMaxRequests {
			cb.halfOpenRequests++
			return true
		}
		return false
	}

	return true
}

// RecordSuccess records a successful call.
// In StateHalfOpen, consecutive successes are counted; once SuccessThreshold is reached,
// the circuit transitions to StateClosed and failure counters are reset.
// In StateClosed, consecutive failure count is reset to 0.
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if cb.state == StateHalfOpen {
		if cb.halfOpenRequests > 0 {
			cb.halfOpenRequests--
		}
		cb.successCount++
		if cb.successCount >= cb.config.SuccessThreshold {
			cb.state = StateClosed
			cb.failureCount = 0
			cb.successCount = 0
			cb.halfOpenRequests = 0
		}
		return
	}

	if cb.state == StateClosed {
		cb.failureCount = 0
		cb.successCount = 0
	}
}

// RecordFailure records an operation failure.
// If retryAfter > 0 (e.g. from an HTTP 429 response), open timeout takes server precedence:
// max(retryAfter, config.Cooldown).
// If consecutive failures reach FailureThreshold, or the breaker is already StateHalfOpen,
// or an explicit retryAfter is received, the breaker transitions to StateOpen.
func (cb *CircuitBreaker) RecordFailure(err error, retryAfter time.Duration) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.failureCount++

	timeout := cb.config.Cooldown
	if retryAfter > 0 && retryAfter > timeout {
		timeout = retryAfter
	}

	if cb.failureCount >= cb.config.FailureThreshold || cb.state == StateHalfOpen || retryAfter > 0 {
		cb.state = StateOpen
		cb.openExpiry = time.Now().Add(timeout)
		cb.halfOpenRequests = 0
		cb.successCount = 0
	}
}

// RemainingCooldown returns the remaining duration before the current StateOpen period expires.
// Returns 0 if the circuit is not in StateOpen or if cooldown has already expired.
func (cb *CircuitBreaker) RemainingCooldown() time.Duration {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	if cb.state != StateOpen {
		return 0
	}

	rem := time.Until(cb.openExpiry)
	if rem <= 0 {
		return 0
	}
	return rem
}

// Reset restores the CircuitBreaker to its initial StateClosed state.
func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.state = StateClosed
	cb.failureCount = 0
	cb.successCount = 0
	cb.halfOpenRequests = 0
	cb.openExpiry = time.Time{}
}

// Execute wraps a function call with circuit breaker protection:
// 1. Verifies context validity.
// 2. Checks Allow() - returning ErrCircuitOpen if denied.
// 3. Executes fn() with panic protection.
// 4. Records success on nil error, or failure (inspecting error for 429/RetryAfter) on error.
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) (err error) {
	if ctxErr := ctx.Err(); ctxErr != nil {
		return ctxErr
	}

	if !cb.Allow() {
		return ErrCircuitOpen
	}

	panicked := true
	defer func() {
		if panicked {
			cb.RecordFailure(errors.New("panic during execution"), 0)
		}
	}()

	err = fn()
	panicked = false

	if err != nil {
		retryAfter := extractRetryAfter(err)
		cb.RecordFailure(err, retryAfter)
		return err
	}

	cb.RecordSuccess()
	return nil
}

// RateLimitError represents a 429 rate limit error with an optional Retry-After duration.
type RateLimitError struct {
	RetryAfter time.Duration
	StatusCode int
	Message    string
	Err        error
}

// NewRateLimitError constructs a new RateLimitError.
func NewRateLimitError(retryAfter time.Duration, message string) *RateLimitError {
	return &RateLimitError{
		RetryAfter: retryAfter,
		StatusCode: 429,
		Message:    message,
	}
}

func (e *RateLimitError) Error() string {
	if e.Message != "" {
		return e.Message
	}
	if e.Err != nil {
		return e.Err.Error()
	}
	if e.RetryAfter > 0 {
		return fmt.Sprintf("rate limited (retry after %v)", e.RetryAfter)
	}
	return "rate limited (429 Too Many Requests)"
}

func (e *RateLimitError) Unwrap() error {
	return e.Err
}

// RetryAfterDuration returns the retry delay.
func (e *RateLimitError) RetryAfterDuration() time.Duration {
	return e.RetryAfter
}

var (
	retryAfterRegex = regexp.MustCompile(`(?i)retry[-_ ]after[:= ]+\s*(\d+)\s*(s|sec|seconds|m|min|minutes|ms)?`)
)

// extractRetryAfter inspects an error for Retry-After duration via:
// 1. Direct RateLimitError pointer
// 2. Interface method RetryAfter() time.Duration
// 3. Interface method RetryAfterDuration() time.Duration
// 4. String pattern matching in error text (e.g. "Retry-After: 45", "retry after 60s")
func extractRetryAfter(err error) time.Duration {
	if err == nil {
		return 0
	}

	var rle *RateLimitError
	if errors.As(err, &rle) {
		if rle.RetryAfter > 0 {
			return rle.RetryAfter
		}
	}

	type retryAfterProvider interface {
		RetryAfter() time.Duration
	}
	var rap retryAfterProvider
	if errors.As(err, &rap) {
		if d := rap.RetryAfter(); d > 0 {
			return d
		}
	}

	type retryAfterDurationProvider interface {
		RetryAfterDuration() time.Duration
	}
	var radp retryAfterDurationProvider
	if errors.As(err, &radp) {
		if d := radp.RetryAfterDuration(); d > 0 {
			return d
		}
	}

	// Try extracting from error message string
	msg := err.Error()
	matches := retryAfterRegex.FindStringSubmatch(msg)
	if len(matches) >= 2 {
		val, convErr := strconv.Atoi(matches[1])
		if convErr == nil && val > 0 {
			unit := strings.ToLower(matches[2])
			switch unit {
			case "ms":
				return time.Duration(val) * time.Millisecond
			case "m", "min", "minutes":
				return time.Duration(val) * time.Minute
			default:
				// Default to seconds (standard HTTP Retry-After integer format)
				return time.Duration(val) * time.Second
			}
		}
	}

	return 0
}
