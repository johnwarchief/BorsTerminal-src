package worker

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

// OrchestratorStatus represents the operational state of the Orchestrator.
type OrchestratorStatus int

const (
	// StatusStopped indicates the orchestrator is not running.
	StatusStopped OrchestratorStatus = iota
	// StatusRunning indicates the orchestrator is active and scheduling tasks.
	StatusRunning
	// StatusPaused indicates scheduling and execution are paused.
	StatusPaused
	// StatusDraining indicates the orchestrator is waiting for in-flight tasks to complete before stopping.
	StatusDraining
)

// String returns the string representation of OrchestratorStatus.
func (s OrchestratorStatus) String() string {
	switch s {
	case StatusStopped:
		return "STOPPED"
	case StatusRunning:
		return "RUNNING"
	case StatusPaused:
		return "PAUSED"
	case StatusDraining:
		return "DRAINING"
	default:
		return fmt.Sprintf("STATUS(%d)", int(s))
	}
}

var (
	// ErrTaskAlreadyExists is returned when registering a task with an already registered name.
	ErrTaskAlreadyExists = errors.New("task already exists")
	// ErrTaskNotFound is returned when operating on a non-existent task name.
	ErrTaskNotFound = errors.New("task not found")
	// ErrOrchestratorNotRunning is returned when triggering or modifying an orchestrator that is not running.
	ErrOrchestratorNotRunning = errors.New("orchestrator is not running")
	// ErrOrchestratorAlreadyRunning is returned when Start is called on an already running orchestrator.
	ErrOrchestratorAlreadyRunning = errors.New("orchestrator is already running")
	// ErrDrainTimeout is returned when Drain times out before all in-flight tasks finish.
	ErrDrainTimeout = errors.New("drain timeout exceeded")
)

// WorkerTask defines a background scheduled task.
type WorkerTask struct {
	Name           string
	Fn             func(ctx context.Context) error
	Cadence        func(now time.Time) time.Duration
	Interval       time.Duration // constant fallback interval if Cadence is nil
	RateLimiter    *RateLimiter
	CircuitBreaker *CircuitBreaker
}

// TaskHealthInfo records execution metrics and health status for a registered task.
type TaskHealthInfo struct {
	LastRun             time.Time `json:"last_run"`
	LastSuccess         time.Time `json:"last_success"`
	LastError           error     `json:"last_error"`
	ConsecutiveFailures int       `json:"consecutive_failures"`
	RunCount            int64     `json:"run_count"`
	IsHealthy           bool      `json:"is_healthy"`
}

type registeredTask struct {
	task      WorkerTask
	health    TaskHealthInfo
	triggerCh chan struct{}
}

// Orchestrator manages the lifecycle and scheduling of background worker tasks.
type Orchestrator struct {
	mu         sync.RWMutex
	status     OrchestratorStatus
	tasks      map[string]*registeredTask
	ctx        context.Context
	cancel     context.CancelFunc
	resumeCh   chan struct{}
	inFlightWg sync.WaitGroup
	workersWg  sync.WaitGroup
}

// NewOrchestrator constructs a new Orchestrator instance.
func NewOrchestrator() *Orchestrator {
	return &Orchestrator{
		status: StatusStopped,
		tasks:  make(map[string]*registeredTask),
	}
}

// Register adds a new WorkerTask to the orchestrator.
// Returns an error if the task name is empty, Fn is nil, interval/cadence is missing,
// or a task with the same name is already registered.
func (o *Orchestrator) Register(task WorkerTask) error {
	if task.Name == "" {
		return errors.New("task name cannot be empty")
	}
	if task.Fn == nil {
		return errors.New("task function cannot be nil")
	}
	if task.Cadence == nil {
		if task.Interval <= 0 {
			return errors.New("task cadence function or interval must be specified")
		}
		interval := task.Interval
		task.Cadence = func(time.Time) time.Duration { return interval }
	}

	o.mu.Lock()
	defer o.mu.Unlock()

	if _, exists := o.tasks[task.Name]; exists {
		return fmt.Errorf("task %q already registered: %w", task.Name, ErrTaskAlreadyExists)
	}

	rt := &registeredTask{
		task:      task,
		triggerCh: make(chan struct{}, 1),
		health: TaskHealthInfo{
			IsHealthy: true,
		},
	}
	o.tasks[task.Name] = rt

	// If orchestrator is already running or paused, spawn the worker loop for this newly registered task
	if (o.status == StatusRunning || o.status == StatusPaused) && o.ctx != nil {
		o.workersWg.Add(1)
		go o.runWorkerLoop(o.ctx, rt)
	}

	return nil
}

// Start begins scheduling and executing all registered tasks.
func (o *Orchestrator) Start(ctx context.Context) error {
	o.mu.Lock()
	defer o.mu.Unlock()

	if o.status == StatusRunning {
		return ErrOrchestratorAlreadyRunning
	}
	if o.status == StatusDraining {
		return errors.New("cannot start orchestrator while draining")
	}

	o.status = StatusRunning
	o.ctx, o.cancel = context.WithCancel(ctx)

	for _, rt := range o.tasks {
		o.workersWg.Add(1)
		go o.runWorkerLoop(o.ctx, rt)
	}

	return nil
}

// runWorkerLoop handles the scheduling and timer loop for an individual registered task.
func (o *Orchestrator) runWorkerLoop(ctx context.Context, rt *registeredTask) {
	defer o.workersWg.Done()
	defer func() {
		if r := recover(); r != nil {
			o.mu.Lock()
			rt.health.LastError = fmt.Errorf("worker loop panicked: %v", r)
			rt.health.IsHealthy = false
			o.mu.Unlock()
		}
	}()

	for {
		interval := rt.task.Cadence(time.Now())
		if interval <= 0 {
			interval = 10 * time.Millisecond
		}

		timer := time.NewTimer(interval)

		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-rt.triggerCh:
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
		case <-timer.C:
		}

		if ctx.Err() != nil {
			return
		}

		o.mu.RLock()
		status := o.status
		resumeCh := o.resumeCh
		o.mu.RUnlock()

		if status == StatusStopped || status == StatusDraining {
			return
		}
		if status == StatusPaused {
			if resumeCh != nil {
				select {
				case <-ctx.Done():
					return
				case <-resumeCh:
				}
			}
			continue
		}

		o.executeTask(ctx, rt)
	}
}

// executeTask invokes the task function, applying rate limiting, circuit breaker,
// panic recovery, in-flight tracking, and health metrics recording.
func (o *Orchestrator) executeTask(ctx context.Context, rt *registeredTask) {
	o.mu.Lock()
	if o.status == StatusStopped || o.status == StatusDraining {
		o.mu.Unlock()
		return
	}
	o.inFlightWg.Add(1)
	o.mu.Unlock()

	defer o.inFlightWg.Done()

	// 1. RateLimiter wait if configured
	if rt.task.RateLimiter != nil {
		if err := rt.task.RateLimiter.Wait(ctx); err != nil {
			return
		}
	}

	now := time.Now()
	var runErr error

	taskFn := func() (err error) {
		defer func() {
			if r := recover(); r != nil {
				err = fmt.Errorf("task panicked: %v", r)
			}
		}()
		return rt.task.Fn(ctx)
	}

	if rt.task.CircuitBreaker != nil {
		runErr = rt.task.CircuitBreaker.Execute(ctx, taskFn)
	} else {
		runErr = taskFn()
	}

	// 2. Record health metrics
	o.mu.Lock()
	defer o.mu.Unlock()

	rt.health.LastRun = now
	rt.health.RunCount++

	if runErr != nil {
		rt.health.LastError = runErr
		rt.health.ConsecutiveFailures++
		rt.health.IsHealthy = false
	} else {
		rt.health.LastError = nil
		rt.health.LastSuccess = now
		rt.health.ConsecutiveFailures = 0
		rt.health.IsHealthy = true
	}
}

// Stop gracefully stops the orchestrator and cancels all tasks.
func (o *Orchestrator) Stop() error {
	o.mu.Lock()
	if o.status == StatusStopped {
		o.mu.Unlock()
		return nil
	}

	o.status = StatusStopped
	if o.resumeCh != nil {
		close(o.resumeCh)
		o.resumeCh = nil
	}
	if o.cancel != nil {
		o.cancel()
	}
	o.mu.Unlock()

	o.workersWg.Wait()
	o.inFlightWg.Wait()
	return nil
}

// Pause pauses task scheduling. In-flight tasks complete, but future scheduled executions wait.
func (o *Orchestrator) Pause() error {
	o.mu.Lock()
	defer o.mu.Unlock()

	if o.status == StatusPaused {
		return nil
	}
	if o.status != StatusRunning {
		return ErrOrchestratorNotRunning
	}

	o.status = StatusPaused
	o.resumeCh = make(chan struct{})
	return nil
}

// Resume resumes a paused orchestrator.
func (o *Orchestrator) Resume() error {
	o.mu.Lock()
	defer o.mu.Unlock()

	if o.status == StatusRunning {
		return nil
	}
	if o.status != StatusPaused {
		return errors.New("orchestrator is not paused")
	}

	o.status = StatusRunning
	if o.resumeCh != nil {
		close(o.resumeCh)
		o.resumeCh = nil
	}
	return nil
}

// Drain transitions the orchestrator into StatusDraining, stops starting new executions,
// and waits for in-flight tasks to complete up to the provided timeout.
func (o *Orchestrator) Drain(timeout time.Duration) error {
	o.mu.Lock()
	if o.status != StatusRunning && o.status != StatusPaused {
		o.mu.Unlock()
		return nil
	}

	o.status = StatusDraining
	if o.resumeCh != nil {
		close(o.resumeCh)
		o.resumeCh = nil
	}
	o.mu.Unlock()

	done := make(chan struct{})
	go func() {
		o.inFlightWg.Wait()
		close(done)
	}()

	var drainErr error
	select {
	case <-done:
		drainErr = nil
	case <-time.After(timeout):
		drainErr = ErrDrainTimeout
	}

	o.mu.Lock()
	if o.cancel != nil {
		o.cancel()
	}
	o.status = StatusStopped
	o.mu.Unlock()

	if drainErr == nil {
		o.workersWg.Wait()
	}
	return drainErr
}

// Trigger immediately queues an execution for the specified task name.
func (o *Orchestrator) Trigger(name string) error {
	o.mu.RLock()
	defer o.mu.RUnlock()

	if o.status != StatusRunning {
		return ErrOrchestratorNotRunning
	}

	rt, exists := o.tasks[name]
	if !exists {
		return fmt.Errorf("task %q not found: %w", name, ErrTaskNotFound)
	}

	select {
	case rt.triggerCh <- struct{}{}:
		return nil
	default:
		return nil
	}
}

// Status returns the current operational status of the orchestrator.
func (o *Orchestrator) Status() OrchestratorStatus {
	o.mu.RLock()
	defer o.mu.RUnlock()
	return o.status
}

// TaskHealth returns health information for the named task.
func (o *Orchestrator) TaskHealth(name string) (TaskHealthInfo, bool) {
	o.mu.RLock()
	defer o.mu.RUnlock()

	rt, exists := o.tasks[name]
	if !exists {
		return TaskHealthInfo{}, false
	}
	health := rt.health
	if rt.task.CircuitBreaker != nil && rt.task.CircuitBreaker.State() == StateOpen {
		health.IsHealthy = false
	}
	return health, true
}

// AllHealth returns a snapshot copy of health information for all registered tasks.
func (o *Orchestrator) AllHealth() map[string]TaskHealthInfo {
	o.mu.RLock()
	defer o.mu.RUnlock()

	out := make(map[string]TaskHealthInfo, len(o.tasks))
	for name, rt := range o.tasks {
		h := rt.health
		if rt.task.CircuitBreaker != nil && rt.task.CircuitBreaker.State() == StateOpen {
			h.IsHealthy = false
		}
		out[name] = h
	}
	return out
}
