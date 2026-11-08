package worker

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

// ErrExceedsBurst is returned when the number of requested tokens exceeds the burst capacity.
var ErrExceedsBurst = errors.New("requested tokens exceed burst capacity")

// RateLimiter implements a thread-safe Token Bucket rate limiter.
// It supports non-blocking checks (Allow) and blocking waits (Wait)
// with context cancellation support.
type RateLimiter struct {
	mu         sync.Mutex
	rate       float64   // tokens replenished per second
	burst      int       // maximum burst capacity
	tokens     float64   // currently available tokens
	lastUpdate time.Time // timestamp of last token replenishment
}

// NewRateLimiter creates a new Token Bucket rate limiter with the given rate
// (tokens per second) and burst capacity.
// If burst <= 0, it defaults to 1. If rate < 0, it defaults to 0.
func NewRateLimiter(rate float64, burst int) *RateLimiter {
	if burst <= 0 {
		burst = 1
	}
	if rate < 0 {
		rate = 0
	}

	return &RateLimiter{
		rate:       rate,
		burst:      burst,
		tokens:     float64(burst),
		lastUpdate: time.Now(),
	}
}

// refillLocked updates the available token count based on elapsed time.
// Must be called with rl.mu held.
func (rl *RateLimiter) refillLocked(now time.Time) {
	elapsed := now.Sub(rl.lastUpdate).Seconds()
	if elapsed <= 0 {
		return
	}

	rl.tokens += elapsed * rl.rate
	if rl.tokens > float64(rl.burst) {
		rl.tokens = float64(rl.burst)
	}
	rl.lastUpdate = now
}

// Allow reports whether a single token can be consumed immediately.
// It is non-blocking. If a token is available, it consumes it and returns true.
func (rl *RateLimiter) Allow() bool {
	return rl.AllowN(1)
}

// AllowN reports whether n tokens can be consumed immediately.
// If available, it consumes them and returns true; otherwise false.
func (rl *RateLimiter) AllowN(n int) bool {
	if n <= 0 {
		return true
	}

	rl.mu.Lock()
	defer rl.mu.Unlock()

	rl.refillLocked(time.Now())

	cost := float64(n)
	if rl.tokens >= cost {
		rl.tokens -= cost
		return true
	}

	return false
}

// Wait blocks until a token is available to consume or until ctx is cancelled.
// Returns nil if a token was acquired, or ctx.Err() if context was cancelled.
func (rl *RateLimiter) Wait(ctx context.Context) error {
	return rl.WaitN(ctx, 1)
}

// WaitN blocks until n tokens are available to consume or until ctx is cancelled.
// Returns nil if n tokens were acquired, or ctx.Err() if context was cancelled.
// If n exceeds the burst capacity, it returns an error wrapping ErrExceedsBurst.
func (rl *RateLimiter) WaitN(ctx context.Context, n int) error {
	if n <= 0 {
		return nil
	}
	if n > rl.burst {
		return fmt.Errorf("rate: WaitN(n=%d) exceeds burst capacity %d: %w", n, rl.burst, ErrExceedsBurst)
	}

	cost := float64(n)

	for {
		if err := ctx.Err(); err != nil {
			return err
		}

		rl.mu.Lock()
		now := time.Now()
		rl.refillLocked(now)

		if rl.tokens >= cost {
			rl.tokens -= cost
			rl.mu.Unlock()
			return nil
		}

		if rl.rate <= 0 {
			// Zero rate cannot replenish tokens; wait strictly for context cancellation
			rl.mu.Unlock()
			<-ctx.Done()
			return ctx.Err()
		}

		needed := cost - rl.tokens
		delaySeconds := needed / rl.rate
		rl.mu.Unlock()

		delay := time.Duration(delaySeconds * float64(time.Second))
		if delay <= 0 {
			delay = 100 * time.Microsecond
		}

		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
			// Loop to re-evaluate tokens
		}
	}
}

// Tokens returns the currently available tokens (fractional), refilled to the current time.
func (rl *RateLimiter) Tokens() float64 {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	rl.refillLocked(time.Now())
	return rl.tokens
}

// Rate returns the token replenishment rate per second.
func (rl *RateLimiter) Rate() float64 {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	return rl.rate
}

// Burst returns the maximum capacity of the rate limiter.
func (rl *RateLimiter) Burst() int {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	return rl.burst
}
