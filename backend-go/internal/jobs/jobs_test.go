package jobs

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func waitState(t *testing.T, m *Manager, id string, want State) Job {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		job, ok := m.Get(id)
		if ok && job.State == want {
			return job
		}
		time.Sleep(10 * time.Millisecond)
	}
	job, _ := m.Get(id)
	t.Fatalf("job %s did not reach %s; last=%+v", id, want, job)
	return job
}

func TestJobLifecycle(t *testing.T) {
	m := NewManager()
	job, err := m.Start(context.Background(), "demo", func(ctx context.Context) error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	if job.ID == "" {
		t.Fatal("job has no id")
	}
	done := waitState(t, m, job.ID, Succeeded)
	if done.FinishedAt == "" || done.Error != "" {
		t.Fatalf("job = %+v", done)
	}
}

func TestJobFailureKeepsError(t *testing.T) {
	m := NewManager()
	job, err := m.Start(context.Background(), "demo", func(ctx context.Context) error {
		return errors.New("snapshot download failed: 500")
	})
	if err != nil {
		t.Fatal(err)
	}
	done := waitState(t, m, job.ID, Failed)
	if done.Error != "snapshot download failed: 500" {
		t.Fatalf("error = %q", done.Error)
	}
	if _, ok := m.Get("missing"); ok {
		t.Fatal("unknown job must not resolve")
	}
}

func TestExclusiveJob(t *testing.T) {
	m := NewManager()
	ctx, cancel := context.WithCancel(context.Background())
	first, existing, err := m.StartExclusive(ctx, "download", true,
		func(ctx context.Context) error { <-ctx.Done(); return ctx.Err() })
	if err != nil || existing != nil {
		t.Fatalf("first start: job=%+v existing=%+v err=%v", first, existing, err)
	}
	second, existing, err := m.StartExclusive(context.Background(), "download", true,
		func(ctx context.Context) error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	if second != nil {
		t.Fatal("exclusive start must not create a second job")
	}
	if existing == nil || existing.ID != first.ID {
		t.Fatalf("existing = %+v, want %s", existing, first.ID)
	}
	cancel()
	waitState(t, m, first.ID, Failed)

	// After completion a new job of the same kind is allowed.
	third, existing, err := m.StartExclusive(context.Background(), "download", true,
		func(ctx context.Context) error { return nil })
	if err != nil || existing != nil || third == nil {
		t.Fatalf("third start: job=%+v existing=%+v err=%v", third, existing, err)
	}
	waitState(t, m, third.ID, Succeeded)
}

func TestPruningKeepsNewest(t *testing.T) {
	m := NewManagerWithClock(time.Now, 2)
	var ids []string
	for i := 0; i < 3; i++ {
		job, err := m.Start(context.Background(), "demo", func(ctx context.Context) error { return nil })
		if err != nil {
			t.Fatal(err)
		}
		ids = append(ids, job.ID)
		waitState(t, m, job.ID, Succeeded)
		time.Sleep(2 * time.Millisecond)
	}
	if _, ok := m.Get(ids[0]); ok {
		t.Fatal("oldest finished job should be pruned")
	}
	if _, ok := m.Get(ids[2]); !ok {
		t.Fatal("newest job must remain")
	}
}

func TestStatusHTTP(t *testing.T) {
	m := NewManager()
	job, err := m.Start(context.Background(), "demo", func(ctx context.Context) error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	waitState(t, m, job.ID, Succeeded)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/jobs/{id}", m.StatusHTTP)

	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/jobs/"+job.ID, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status code = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["job_id"] != job.ID || body["state"] != string(Succeeded) {
		t.Fatalf("body = %v", body)
	}

	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/jobs/does-not-exist", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("unknown job code = %d", rec.Code)
	}
}
