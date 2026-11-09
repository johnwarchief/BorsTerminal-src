package main

// تست‌هایِ قطعیِ هم‌زمانیِ Generation Runtime. این فایل ترتیبِ خطرناکِ
// «Load اشاره‌گر ← Reload ← acquire» را با کانال کنترل می‌کند؛ بدونِ hook
// فقط احتمالاً بازتولید می‌شد.

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"borsterminal/backend/internal/generation"
)

func newRaceRuntime(t *testing.T) (*runtime, string) {
	t.Helper()
	t.Setenv("BORS_GO_LIVE", "0")
	dataDir := t.TempDir()
	writeMarkerMarket(t, filepath.Join(dataDir, "gens", "gen_one", "market.db"), "one")
	writeMarkerMarket(t, filepath.Join(dataDir, "gens", "gen_two", "market.db"), "two")
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "one", GenerationDir: "gens/gen_one", SchemaVersion: 1,
		AppliedAtUTC: "2026-11-09T00:00:00Z",
	})
	rt, err := newRuntime(context.Background(), testConfig(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	return rt, dataDir
}

func switchToTwo(t *testing.T, dataDir string) {
	t.Helper()
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "two", GenerationDir: "gens/gen_two", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:10:00Z",
		PreviousSnapshotSetID: "one", PreviousGenerationDir: "gens/gen_one",
	})
}

func markerHandler(inst *appInstance) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var v string
		if err := inst.handles.Market.QueryRow("SELECT value FROM generation_marker").Scan(&v); err != nil {
			http.Error(w, "db unavailable: "+err.Error(), http.StatusInternalServerError)
			return
		}
		_, _ = w.Write([]byte(v))
	})
}

// TestReloadNeverClosesAdmittedRequest: درخواستی که وارد ServeHTTP شده باید
// حتی اگر Reload همان لحظه نسل را عوض کند، دیتابیسِ باز داشته باشد.
func TestReloadNeverClosesAdmittedRequest(t *testing.T) {
	rt, dataDir := newRaceRuntime(t)
	t.Cleanup(rt.Close)

	old := rt.current()
	old.handler = markerHandler(old)

	admitted := make(chan struct{})
	gate := make(chan struct{})
	rt.testHook = func(inst *appInstance) {
		if inst == old {
			close(admitted)
			<-gate
		}
	}

	type result struct {
		code int
		body string
	}
	res := make(chan result, 1)
	go func() {
		rec := httptest.NewRecorder()
		rt.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/probe", nil))
		res <- result{code: rec.Code, body: rec.Body.String()}
	}()

	<-admitted
	switchToTwo(t, dataDir)
	if err := rt.Reload(); err != nil {
		t.Fatal(err)
	}
	select {
	case <-old.closed:
		t.Fatal("retired instance closed while an admitted request was in flight")
	default:
	}

	close(gate)
	got := <-res
	if got.code != http.StatusOK || got.body != "one" {
		t.Fatalf("in-flight request reached a closed generation: code=%d body=%q", got.code, got.body)
	}
	select {
	case <-old.closed:
	case <-time.After(2 * time.Second):
		t.Fatal("old instance was not closed after its last request finished")
	}

	cur := rt.current()
	if cur == nil || cur == old {
		t.Fatal("pointer was not swapped to the new generation")
	}
	var v string
	if err := cur.handles.Market.QueryRow("SELECT value FROM generation_marker").Scan(&v); err != nil || v != "two" {
		t.Fatalf("new generation data = %q err=%v", v, err)
	}
}

// TestCloseWaitsForActiveRequest: Close نباید برگردد (و نباید دیتابیس‌ها را
// ببندد) تا درخواستِ در جریان تمام شود.
func TestCloseWaitsForActiveRequest(t *testing.T) {
	rt, _ := newRaceRuntime(t)
	inst := rt.current()

	started := make(chan struct{})
	release := make(chan struct{})
	inst.handler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var v string
		if err := inst.handles.Market.QueryRow("SELECT value FROM generation_marker").Scan(&v); err != nil {
			http.Error(w, "db unavailable: "+err.Error(), http.StatusInternalServerError)
			return
		}
		close(started)
		<-release
		_, _ = w.Write([]byte(v))
	})

	done := make(chan int, 1)
	go func() {
		rec := httptest.NewRecorder()
		rt.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/probe", nil))
		done <- rec.Code
	}()
	<-started

	closed := make(chan struct{})
	go func() {
		rt.Close()
		close(closed)
	}()
	select {
	case <-closed:
		t.Fatal("runtime Close returned while a request was still active")
	case <-time.After(100 * time.Millisecond):
	}
	select {
	case <-inst.closed:
		t.Fatal("instance was closed under an active request")
	default:
	}

	close(release)
	if code := <-done; code != http.StatusOK {
		t.Fatalf("active request failed during Close: %d", code)
	}
	select {
	case <-closed:
	case <-time.After(2 * time.Second):
		t.Fatal("runtime Close did not finish after the active request drained")
	}
	select {
	case <-inst.closed:
	default:
		t.Fatal("instance was not closed after Close returned")
	}

	rec := httptest.NewRecorder()
	rt.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/probe", nil))
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("request after Close = %d, want 503", rec.Code)
	}
}

// TestConcurrentServeReloadRollback: بار هم‌زمان روی ServeHTTP با چرخشِ نسل.
// با -race اجرا می‌شود؛ هر پاسخِ غیرِ 200 یا پیش‌فرضِ 503 یعنی نقضِ قرارداد.
func TestConcurrentServeReloadRollback(t *testing.T) {
	rt, dataDir := newRaceRuntime(t)
	t.Cleanup(rt.Close)
	switchToTwo(t, dataDir)
	if err := rt.Reload(); err != nil {
		t.Fatal(err)
	}

	stop := make(chan struct{})
	errs := make(chan string, 32)
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-stop:
					return
				default:
				}
				rec := httptest.NewRecorder()
				rt.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/oc/data", nil))
				if rec.Code != http.StatusOK {
					select {
					case errs <- fmt.Sprintf("serve status=%d body=%s", rec.Code, rec.Body.String()):
					default:
					}
					return
				}
			}
		}()
	}

	one := generation.Pointer{
		SnapshotSetID: "one", GenerationDir: "gens/gen_one", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:20:00Z",
		PreviousSnapshotSetID: "two", PreviousGenerationDir: "gens/gen_two",
	}
	two := generation.Pointer{
		SnapshotSetID: "two", GenerationDir: "gens/gen_two", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:10:00Z",
		PreviousSnapshotSetID: "one", PreviousGenerationDir: "gens/gen_one",
	}
	for i := 0; i < 40; i++ {
		if i%5 == 4 {
			// Rollback خودش اشاره‌گر را اتمیک بازنویسی می‌کند؛ نوشتنِ
			// هم‌زمانِ تست با rename روی ویندوز Access denied می‌دهد.
			if err := rt.Rollback(); err != nil {
				t.Fatalf("rollback %d: %v", i, err)
			}
			continue
		}
		if i%2 == 0 {
			writeGenPointer(t, dataDir, one)
		} else {
			writeGenPointer(t, dataDir, two)
		}
		if err := rt.Reload(); err != nil {
			t.Fatalf("reload %d: %v", i, err)
		}
	}
	close(stop)
	wg.Wait()
	select {
	case msg := <-errs:
		t.Fatal(msg)
	default:
	}
}

// TestAcquireCurrentRefusesClosedRuntime: پس از Close مسیرِ رسمیِ گرفتنِ ref
// باید nil بدهد، نه نسخهٔ بازنشسته.
func TestAcquireCurrentRefusesClosedRuntime(t *testing.T) {
	rt, _ := newRaceRuntime(t)
	inst := rt.current()
	rt.Close()
	if got := rt.acquireCurrent(); got != nil {
		t.Fatalf("acquireCurrent after Close = %p, want nil", got)
	}
	if inst.refs.Load() != 0 {
		t.Fatalf("closed instance refs = %d, want 0", inst.refs.Load())
	}
	select {
	case <-inst.closed:
	default:
		t.Fatal("closed instance is not marked closed")
	}
	if err := rt.Reload(); err == nil {
		t.Fatal("Reload after Close must fail")
	}
}
