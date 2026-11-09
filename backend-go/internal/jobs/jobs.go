// Package jobs مدیرِ کارهایِ پس‌زمینهٔ کوتاه‌عمر است. هر کار شناسهٔ واقعی،
// وضعیت و خطای خودش را دارد؛ پاسخِ «۲۰۰ = شروع شد» بدونِ Job ممنوع است.
package jobs

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"sort"
	"sync"
	"time"

	"borsterminal/backend/internal/httpapi"
)

type State string

const (
	Queued    State = "queued"
	Running   State = "running"
	Succeeded State = "succeeded"
	Failed    State = "failed"
)

type Job struct {
	ID         string
	Kind       string
	State      State
	Error      string
	StartedAt  string
	FinishedAt string
}

type Manager struct {
	mu   sync.Mutex
	jobs map[string]*Job
	now  func() time.Time
	max  int
}

func NewManager() *Manager {
	return &Manager{jobs: map[string]*Job{}, now: time.Now, max: 100}
}

func NewManagerWithClock(now func() time.Time, max int) *Manager {
	if max < 1 {
		max = 100
	}
	return &Manager{jobs: map[string]*Job{}, now: now, max: max}
}

func newID() (string, error) {
	buf := make([]byte, 12)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

// Start کار را در goroutine اجرا می‌کند و بلافاصله Job با شناسهٔ واقعی می‌دهد.
// fn باید ctx را رعایت کند؛ لغو/پایانِ عمر سرویس مسئولیتِ فراخوان است.
func (m *Manager) Start(ctx context.Context, kind string, fn func(context.Context) error) (*Job, error) {
	job, _, err := m.StartExclusive(ctx, kind, false, fn)
	return job, err
}

// StartExclusive در حالت exclusive، اگر کاری از همان kind در جریان باشد
// دیگری را شروع نمی‌کند و همان Job را برمی‌گرداند (برای 409 بدونِ مسابقه).
func (m *Manager) StartExclusive(ctx context.Context, kind string, exclusive bool, fn func(context.Context) error) (*Job, *Job, error) {
	id, err := newID()
	if err != nil {
		return nil, nil, err
	}
	job := &Job{ID: id, Kind: kind, State: Queued, StartedAt: m.now().UTC().Format(time.RFC3339Nano)}

	m.mu.Lock()
	if exclusive {
		for _, j := range m.jobs {
			if j.Kind == kind && (j.State == Queued || j.State == Running) {
				existing := *j
				m.mu.Unlock()
				return nil, &existing, nil
			}
		}
	}
	m.jobs[id] = job
	m.pruneLocked()
	m.mu.Unlock()

	go func() {
		m.mu.Lock()
		job.State = Running
		m.mu.Unlock()

		runErr := fn(ctx)

		m.mu.Lock()
		job.FinishedAt = m.now().UTC().Format(time.RFC3339Nano)
		if runErr != nil {
			job.State = Failed
			job.Error = runErr.Error()
		} else {
			job.State = Succeeded
		}
		m.mu.Unlock()
	}()
	return job, nil, nil
}

func (m *Manager) pruneLocked() {
	if len(m.jobs) <= m.max {
		return
	}
	finished := make([]*Job, 0, len(m.jobs))
	for _, j := range m.jobs {
		if j.State == Succeeded || j.State == Failed {
			finished = append(finished, j)
		}
	}
	sort.Slice(finished, func(i, j int) bool { return finished[i].FinishedAt < finished[j].FinishedAt })
	for _, j := range finished {
		if len(m.jobs) <= m.max {
			break
		}
		delete(m.jobs, j.ID)
	}
}

func (m *Manager) Get(id string) (Job, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	j, ok := m.jobs[id]
	if !ok {
		return Job{}, false
	}
	return *j, true
}

// Running identifies an in-flight job of a kind; callers use it to return a
// 409 with the existing id instead of starting a duplicate.
func (m *Manager) Running(kind string) (Job, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, j := range m.jobs {
		if j.Kind == kind && (j.State == Queued || j.State == Running) {
			return *j, true
		}
	}
	return Job{}, false
}

func (j Job) JSON() map[string]any {
	out := map[string]any{
		"job_id": j.ID, "kind": j.Kind, "state": string(j.State), "started_at": j.StartedAt,
	}
	if j.FinishedAt != "" {
		out["finished_at"] = j.FinishedAt
	}
	if j.Error != "" {
		out["error"] = j.Error
	}
	return out
}

// StatusHTTP پورتِ GET /api/jobs/{id}. شناسهٔ ناشناخته ۴۰۴ می‌دهد، نه ۲۰۰ِ خالی.
func (m *Manager) StatusHTTP(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	job, ok := m.Get(id)
	if !ok {
		httpapi.WriteJSON(w, http.StatusNotFound, map[string]any{
			"status": "error", "code": "JOB_NOT_FOUND", "job_id": id, "retryable": false,
		})
		return
	}
	body := job.JSON()
	body["status"] = "ok"
	httpapi.WriteJSON(w, http.StatusOK, body)
}
