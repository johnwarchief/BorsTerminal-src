package worker

import (
	"context"
	"errors"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestOrchestrator_Registration(t *testing.T) {
	orch := NewOrchestrator()

	// Initial status
	if orch.Status() != StatusStopped {
		t.Fatalf("expected initial status STOPPED, got %v", orch.Status())
	}
	if orch.Status().String() != "STOPPED" {
		t.Fatalf("expected status string STOPPED, got %s", orch.Status().String())
	}

	// Register valid task
	err := orch.Register(WorkerTask{
		Name:     "task1",
		Interval: 10 * time.Millisecond,
		Fn: func(ctx context.Context) error {
			return nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register valid task: %v", err)
	}

	// Register duplicate
	err = orch.Register(WorkerTask{
		Name:     "task1",
		Interval: 20 * time.Millisecond,
		Fn: func(ctx context.Context) error {
			return nil
		},
	})
	if !errors.Is(err, ErrTaskAlreadyExists) {
		t.Fatalf("expected ErrTaskAlreadyExists, got %v", err)
	}

	// Register empty name
	err = orch.Register(WorkerTask{
		Name:     "",
		Interval: 10 * time.Millisecond,
		Fn:       func(ctx context.Context) error { return nil },
	})
	if err == nil {
		t.Fatal("expected error registering task with empty name")
	}

	// Register nil Fn
	err = orch.Register(WorkerTask{
		Name:     "task_nil_fn",
		Interval: 10 * time.Millisecond,
		Fn:       nil,
	})
	if err == nil {
		t.Fatal("expected error registering task with nil function")
	}

	// Register missing interval and cadence
	err = orch.Register(WorkerTask{
		Name: "task_no_cadence",
		Fn:   func(ctx context.Context) error { return nil },
	})
	if err == nil {
		t.Fatal("expected error registering task with zero cadence/interval")
	}
}

func TestOrchestrator_Lifecycle(t *testing.T) {
	orch := NewOrchestrator()

	var runs int64
	err := orch.Register(WorkerTask{
		Name:     "ping",
		Interval: 15 * time.Millisecond,
		Fn: func(ctx context.Context) error {
			atomic.AddInt64(&runs, 1)
			return nil
		},
	})
	if err != nil {
		t.Fatalf("registration failed: %v", err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	if orch.Status() != StatusRunning {
		t.Fatalf("expected RUNNING status, got %v", orch.Status())
	}

	// Cannot Start again
	if err := orch.Start(ctx); !errors.Is(err, ErrOrchestratorAlreadyRunning) {
		t.Fatalf("expected ErrOrchestratorAlreadyRunning, got %v", err)
	}

	// Wait for task to run at least once
	startWait := time.Now()
	for atomic.LoadInt64(&runs) < 1 && time.Since(startWait) < 500*time.Millisecond {
		time.Sleep(10 * time.Millisecond)
	}
	countAfterStart := atomic.LoadInt64(&runs)
	if countAfterStart < 1 {
		t.Fatalf("expected task to have run, got count %d", countAfterStart)
	}

	// Pause
	if err := orch.Pause(); err != nil {
		t.Fatalf("Pause failed: %v", err)
	}
	if orch.Status() != StatusPaused {
		t.Fatalf("expected PAUSED status, got %v", orch.Status())
	}
	if orch.Status().String() != "PAUSED" {
		t.Fatalf("expected PAUSED string, got %s", orch.Status().String())
	}

	countAtPause := atomic.LoadInt64(&runs)
	time.Sleep(50 * time.Millisecond)
	countAfterWait := atomic.LoadInt64(&runs)
	if countAfterWait > countAtPause+1 { // at most one in-flight tick might have completed
		t.Fatalf("expected no new executions while paused: was %d, now %d", countAtPause, countAfterWait)
	}

	// Resume
	if err := orch.Resume(); err != nil {
		t.Fatalf("Resume failed: %v", err)
	}
	if orch.Status() != StatusRunning {
		t.Fatalf("expected RUNNING status, got %v", orch.Status())
	}

	startResume := time.Now()
	for atomic.LoadInt64(&runs) <= countAfterWait && time.Since(startResume) < 500*time.Millisecond {
		time.Sleep(10 * time.Millisecond)
	}
	if atomic.LoadInt64(&runs) <= countAfterWait {
		t.Fatalf("expected task to resume execution: before %d, after %d", countAfterWait, atomic.LoadInt64(&runs))
	}

	// Stop
	if err := orch.Stop(); err != nil {
		t.Fatalf("Stop failed: %v", err)
	}
	if orch.Status() != StatusStopped {
		t.Fatalf("expected STOPPED status, got %v", orch.Status())
	}
}

func TestOrchestrator_ScheduledTaskHealth(t *testing.T) {
	orch := NewOrchestrator()

	cadenceCalls := int64(0)
	cadenceFn := func(now time.Time) time.Duration {
		atomic.AddInt64(&cadenceCalls, 1)
		return 15 * time.Millisecond
	}

	err := orch.Register(WorkerTask{
		Name:    "health_test",
		Cadence: cadenceFn,
		Fn: func(ctx context.Context) error {
			return nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register task: %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	defer orch.Stop()

	// Wait for runs
	startWaitHealth := time.Now()
	for time.Since(startWaitHealth) < 500*time.Millisecond {
		if h, exists := orch.TaskHealth("health_test"); exists && h.RunCount >= 2 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	health, exists := orch.TaskHealth("health_test")
	if !exists {
		t.Fatal("expected task to exist in TaskHealth")
	}

	if health.RunCount < 2 {
		t.Fatalf("expected at least 2 runs, got %d", health.RunCount)
	}
	if !health.IsHealthy {
		t.Fatal("expected task to be healthy")
	}
	if health.LastError != nil {
		t.Fatalf("expected LastError to be nil, got %v", health.LastError)
	}
	if health.LastRun.IsZero() {
		t.Fatal("expected non-zero LastRun")
	}
	if health.LastSuccess.IsZero() {
		t.Fatal("expected non-zero LastSuccess")
	}
	if health.ConsecutiveFailures != 0 {
		t.Fatalf("expected 0 consecutive failures, got %d", health.ConsecutiveFailures)
	}

	// Verify AllHealth
	all := orch.AllHealth()
	if len(all) != 1 {
		t.Fatalf("expected 1 task in AllHealth, got %d", len(all))
	}
	if all["health_test"].RunCount != health.RunCount {
		t.Fatalf("mismatched health info in AllHealth")
	}

	// Non-existent task health
	_, exists = orch.TaskHealth("non_existent")
	if exists {
		t.Fatal("expected non_existent task to not exist")
	}
}

func TestOrchestrator_ManualTrigger(t *testing.T) {
	orch := NewOrchestrator()

	var count int64
	err := orch.Register(WorkerTask{
		Name:     "long_interval_task",
		Interval: 24 * time.Hour, // very long, will not fire on timer
		Fn: func(ctx context.Context) error {
			atomic.AddInt64(&count, 1)
			return nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register: %v", err)
	}

	// Trigger before start should return ErrOrchestratorNotRunning
	if err := orch.Trigger("long_interval_task"); !errors.Is(err, ErrOrchestratorNotRunning) {
		t.Fatalf("expected ErrOrchestratorNotRunning, got %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	defer orch.Stop()

	// Initial count should be 0
	if atomic.LoadInt64(&count) != 0 {
		t.Fatalf("expected count 0 before trigger, got %d", atomic.LoadInt64(&count))
	}

	// Trigger unknown task
	if err := orch.Trigger("unknown"); !errors.Is(err, ErrTaskNotFound) {
		t.Fatalf("expected ErrTaskNotFound, got %v", err)
	}

	// Trigger registered task
	if err := orch.Trigger("long_interval_task"); err != nil {
		t.Fatalf("Trigger failed: %v", err)
	}

	// Wait for execution
	time.Sleep(50 * time.Millisecond)

	if atomic.LoadInt64(&count) != 1 {
		t.Fatalf("expected count 1 after manual trigger, got %d", atomic.LoadInt64(&count))
	}

	health, _ := orch.TaskHealth("long_interval_task")
	if health.RunCount != 1 {
		t.Fatalf("expected RunCount 1, got %d", health.RunCount)
	}
	if !health.IsHealthy {
		t.Fatal("expected task to be healthy")
	}
}

func TestOrchestrator_PanicRecovery(t *testing.T) {
	orch := NewOrchestrator()

	err := orch.Register(WorkerTask{
		Name:     "panicking_task",
		Interval: 24 * time.Hour,
		Fn: func(ctx context.Context) error {
			panic("catastrophic failure simulated")
		},
	})
	if err != nil {
		t.Fatalf("failed to register: %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	defer orch.Stop()

	// Trigger the panicking task
	if err := orch.Trigger("panicking_task"); err != nil {
		t.Fatalf("Trigger failed: %v", err)
	}

	time.Sleep(50 * time.Millisecond)

	// Orchestrator must still be running (not killed by panic)
	if orch.Status() != StatusRunning {
		t.Fatalf("orchestrator status died after panic: %v", orch.Status())
	}

	health, ok := orch.TaskHealth("panicking_task")
	if !ok {
		t.Fatal("task health missing")
	}

	if health.RunCount != 1 {
		t.Fatalf("expected RunCount 1, got %d", health.RunCount)
	}
	if health.IsHealthy {
		t.Fatal("expected task to be marked unhealthy after panic")
	}
	if health.LastError == nil {
		t.Fatal("expected non-nil LastError")
	}
	if !strings.Contains(health.LastError.Error(), "catastrophic failure simulated") {
		t.Fatalf("expected panic message in LastError, got: %v", health.LastError)
	}
	if health.ConsecutiveFailures != 1 {
		t.Fatalf("expected 1 consecutive failure, got %d", health.ConsecutiveFailures)
	}
}

func TestOrchestrator_Drain(t *testing.T) {
	orch := NewOrchestrator()

	inFlightStarted := make(chan struct{})
	inFlightRelease := make(chan struct{})
	var inFlightFinished int64

	err := orch.Register(WorkerTask{
		Name:     "slow_task",
		Interval: 24 * time.Hour,
		Fn: func(ctx context.Context) error {
			close(inFlightStarted)
			<-inFlightRelease
			atomic.StoreInt64(&inFlightFinished, 1)
			return nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register: %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	// Trigger slow task
	if err := orch.Trigger("slow_task"); err != nil {
		t.Fatalf("trigger failed: %v", err)
	}

	// Wait until task starts executing
	<-inFlightStarted

	// Call Drain in a separate goroutine
	drainDone := make(chan error, 1)
	go func() {
		drainDone <- orch.Drain(500 * time.Millisecond)
	}()

	// Status should be StatusDraining
	time.Sleep(10 * time.Millisecond)
	if orch.Status() != StatusDraining && orch.Status() != StatusStopped {
		t.Fatalf("expected DRAINING status, got %v", orch.Status())
	}

	// Release in-flight task so it can complete
	close(inFlightRelease)

	// Drain should return nil
	select {
	case err := <-drainDone:
		if err != nil {
			t.Fatalf("Drain returned unexpected error: %v", err)
		}
	case <-time.After(1 * time.Second):
		t.Fatal("Drain timed out waiting for in-flight task")
	}

	if atomic.LoadInt64(&inFlightFinished) != 1 {
		t.Fatal("expected in-flight task to have completed")
	}
	if orch.Status() != StatusStopped {
		t.Fatalf("expected STOPPED status after Drain, got %v", orch.Status())
	}
}

func TestOrchestrator_DrainTimeout(t *testing.T) {
	orch := NewOrchestrator()

	inFlightStarted := make(chan struct{})
	releaseHang := make(chan struct{})
	defer close(releaseHang)

	err := orch.Register(WorkerTask{
		Name:     "hanging_task",
		Interval: 24 * time.Hour,
		Fn: func(ctx context.Context) error {
			close(inFlightStarted)
			select {
			case <-releaseHang:
			case <-ctx.Done():
			}
			return nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register: %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	_ = orch.Trigger("hanging_task")
	<-inFlightStarted

	// Drain with very short timeout
	err = orch.Drain(20 * time.Millisecond)
	if !errors.Is(err, ErrDrainTimeout) {
		t.Fatalf("expected ErrDrainTimeout, got %v", err)
	}
}

func TestOrchestrator_WithRateLimiterAndCircuitBreaker(t *testing.T) {
	orch := NewOrchestrator()

	limiter := NewRateLimiter(100.0, 10) // generous rate and burst for test
	breaker := NewCircuitBreaker(CircuitBreakerConfig{
		FailureThreshold: 2,
		Cooldown:         500 * time.Millisecond,
	})

	var attempts int64
	err := orch.Register(WorkerTask{
		Name:           "guarded_task",
		Interval:       24 * time.Hour,
		RateLimiter:    limiter,
		CircuitBreaker: breaker,
		Fn: func(ctx context.Context) error {
			atomic.AddInt64(&attempts, 1)
			return errors.New("upstream 503 service unavailable")
		},
	})
	if err != nil {
		t.Fatalf("failed to register: %v", err)
	}

	ctx := context.Background()
	if err := orch.Start(ctx); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	defer orch.Stop()

	// Trigger 1st failure
	_ = orch.Trigger("guarded_task")
	time.Sleep(30 * time.Millisecond)

	// Trigger 2nd failure -> trips circuit breaker
	_ = orch.Trigger("guarded_task")
	time.Sleep(30 * time.Millisecond)

	if breaker.State() != StateOpen {
		t.Fatalf("expected circuit breaker to be OPEN, got %v", breaker.State())
	}

	health, _ := orch.TaskHealth("guarded_task")
	if health.IsHealthy {
		t.Fatal("expected task to be marked unhealthy when circuit breaker is open")
	}
	if health.ConsecutiveFailures < 2 {
		t.Fatalf("expected at least 2 consecutive failures, got %d", health.ConsecutiveFailures)
	}
}

func TestOrchestrator_RapidStartStop(t *testing.T) {
	for i := 0; i < 20; i++ {
		orch := NewOrchestrator()
		_ = orch.Register(WorkerTask{
			Name:     "t",
			Interval: 10 * time.Millisecond,
			Fn:       func(ctx context.Context) error { return nil },
		})
		if err := orch.Start(context.Background()); err != nil {
			t.Fatalf("start failed on iter %d: %v", i, err)
		}
		if err := orch.Stop(); err != nil {
			t.Fatalf("stop failed on iter %d: %v", i, err)
		}
	}
}

func TestOrchestrator_RegisterWhilePaused(t *testing.T) {
	orch := NewOrchestrator()
	if err := orch.Start(context.Background()); err != nil {
		t.Fatalf("start failed: %v", err)
	}
	defer orch.Stop()

	if err := orch.Pause(); err != nil {
		t.Fatalf("pause failed: %v", err)
	}

	var runs int64
	err := orch.Register(WorkerTask{
		Name:     "paused_reg_task",
		Interval: 10 * time.Millisecond,
		Fn: func(ctx context.Context) error {
			atomic.AddInt64(&runs, 1)
			return nil
		},
	})
	if err != nil {
		t.Fatalf("register while paused failed: %v", err)
	}

	time.Sleep(30 * time.Millisecond)
	if atomic.LoadInt64(&runs) != 0 {
		t.Fatalf("expected 0 runs while paused, got %d", atomic.LoadInt64(&runs))
	}

	if err := orch.Resume(); err != nil {
		t.Fatalf("resume failed: %v", err)
	}

	startResumeWait := time.Now()
	for atomic.LoadInt64(&runs) == 0 && time.Since(startResumeWait) < 500*time.Millisecond {
		time.Sleep(10 * time.Millisecond)
	}
	if atomic.LoadInt64(&runs) == 0 {
		t.Fatal("expected task to execute after resume")
	}
}

func TestOrchestrator_ConcurrentDrainAndExecute(t *testing.T) {
	orch := NewOrchestrator()
	for i := 0; i < 5; i++ {
		name := string(rune('a' + i))
		_ = orch.Register(WorkerTask{
			Name:     name,
			Interval: 1 * time.Millisecond,
			Fn: func(ctx context.Context) error {
				time.Sleep(5 * time.Millisecond)
				return nil
			},
		})
	}

	if err := orch.Start(context.Background()); err != nil {
		t.Fatalf("start failed: %v", err)
	}

	time.Sleep(10 * time.Millisecond)
	if err := orch.Drain(200 * time.Millisecond); err != nil {
		t.Fatalf("drain failed: %v", err)
	}

	if orch.Status() != StatusStopped {
		t.Fatalf("expected STOPPED after drain, got %v", orch.Status())
	}
}
