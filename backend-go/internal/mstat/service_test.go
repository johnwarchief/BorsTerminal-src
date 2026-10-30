package mstat

import (
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

type fakeClock struct {
	mu sync.Mutex
	t  time.Time
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.t
}

func (c *fakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	c.t = c.t.Add(d)
	c.mu.Unlock()
}

// newTestService یک بانکِ درون‌حافظه‌ای با جدولِ mstat_snap می‌سازد؛ بی‌آن،
// نشانهٔ کش وجود ندارد و پایتون هم (و حالا Go هم) کش را کامل دور می‌زند.
func newTestService(t *testing.T) (*Service, *fakeClock, string) {
	t.Helper()
	raw, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	raw.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = raw.Close() })
	if _, err := raw.Exec("CREATE TABLE mstat_snap (d_even INTEGER, h_even INTEGER)"); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	s := New(raw, dir, nil)
	clk := &fakeClock{t: time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)}
	s.clock = clk.Now
	return s, clk, dir
}

func waitCount(t *testing.T, n *int32, want int32) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for atomic.LoadInt32(n) < want && time.Now().Before(deadline) {
		time.Sleep(2 * time.Millisecond)
	}
	if got := atomic.LoadInt32(n); got != want {
		t.Fatalf("computes = %d, want %d", got, want)
	}
}

func TestCallCachesWithinTTL(t *testing.T) {
	s, clk, _ := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	s.Call("p", fn, Options{})
	if n != 1 {
		t.Fatalf("computes = %d, want 1", n)
	}
	clk.Advance(DefaultTTL + time.Second)
	stale := s.Call("p", fn, Options{StaleOK: true})
	if stale["status"] != "ok" {
		t.Fatalf("stale body = %v", stale)
	}
	waitCount(t, &n, 2)
	s.Call("p", fn, Options{StaleOK: true})
	if n != 2 {
		t.Fatalf("computes after rebuild = %d, want 2", n)
	}
}

// TestCallServesStaleWhileRebuilding شکلِ کاملِ STALE را قفل می‌کند: پاسخِ کهنه
// فوراً می‌رود (بی‌بلوکه‌شدنِ فراخوان)، بازسازی در پس‌زمینه یک‌بار اجرا می‌شود،
// و فراخوانِ بعدی بدنهٔ تازه را می‌بیند.
func TestCallServesStaleWhileRebuilding(t *testing.T) {
	s, clk, _ := newTestService(t)
	var n int32
	version := int64(1)
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok", "v": atomic.LoadInt64(&version)}, nil
	}
	if got := s.Call("p", fn, Options{StaleOK: true}); got["v"] != int64(1) {
		t.Fatalf("cold body = %v", got)
	}
	atomic.StoreInt64(&version, 2)
	clk.Advance(DefaultTTL + time.Second)
	if got := s.Call("p", fn, Options{StaleOK: true}); got["v"] != int64(1) {
		t.Fatalf("stale body = %v, want the cached v=1", got)
	}
	waitCount(t, &n, 2)
	// StaleOK=false بعد از انقضا منتظرِ همان تک‌پرواز می‌ماند و بدنهٔ تازه را
	// می‌گیرد؛ این هم سروِ کهنه را رد می‌کند و هم بازسازیِ دوباره نمی‌سازد.
	if got := s.Call("p", fn, Options{}); got["v"] != int64(2) {
		t.Fatalf("rebuilt body = %v, want v=2", got)
	}
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}

func TestCallNoStaleWhenDisallowed(t *testing.T) {
	s, clk, _ := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	clk.Advance(DefaultTTL + time.Second)
	s.Call("p", fn, Options{}) // StaleOK=false ⇒ محاسبهٔ درون‌خطی
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}

// TestCallColdMiss بلیتِ MISS را می‌سنجد: اولین درخواست درون‌خطی ساخته و همان
// بدنه را می‌دهد (بی‌این‌که منتظرِ کسی بماند).
func TestCallColdMiss(t *testing.T) {
	s, _, _ := newTestService(t)
	var n int32
	out := s.Call("p", func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}, Options{StaleOK: true})
	if out["status"] != "ok" || n != 1 {
		t.Fatalf("cold miss: status=%v computes=%d", out["status"], n)
	}
}

func TestCallDoesNotCacheErrors(t *testing.T) {
	s, _, _ := newTestService(t)
	var n int32
	failing := true
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		if failing {
			return nil, errors.New("boom")
		}
		return map[string]any{"status": "ok"}, nil
	}
	out := s.Call("p", fn, Options{})
	if out["status"] != "error" || out["message"] != "boom" {
		t.Fatalf("error body = %v", out)
	}
	if out["source"] != "local:market.db" {
		t.Fatalf("source = %v", out["source"])
	}
	failing = false
	out2 := s.Call("p", fn, Options{})
	if out2["status"] != "ok" || n != 2 {
		t.Fatalf("after recovery: status=%v computes=%d", out2["status"], n)
	}
}

func TestCallSingleFlight(t *testing.T) {
	s, _, _ := newTestService(t)
	release := make(chan struct{})
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		<-release
		return map[string]any{"status": "ok"}, nil
	}
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); s.Call("p", fn, Options{}) }()
	}
	waitCount(t, &n, 1)
	close(release)
	wg.Wait()
	if n != 1 {
		t.Fatalf("computes = %d, want 1", n)
	}
}

func TestCallStateChangeInvalidates(t *testing.T) {
	s, _, dir := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	if err := os.WriteFile(filepath.Join(dir, "market_sync.json"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	s.Call("p", fn, Options{})
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}

// TestCallMarkerChangeInvalidates نشانِ mstat_snap هم بخشی از کلید است: یک نقطهٔ
// تازه در همان جدول باید کش را بی‌اثر کند، حتی بی‌هیچ تغییرِ فایلی.
func TestCallMarkerChangeInvalidates(t *testing.T) {
	s, _, _ := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	if _, err := s.db.Exec("INSERT INTO mstat_snap (d_even, h_even) VALUES (20261014, 121000)"); err != nil {
		t.Fatal(err)
	}
	s.Call("p", fn, Options{})
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}

// TestCallKeysAreIsolated هر پنل/پارامتر کلیدِ خودش را دارد؛ بی‌این، پنل‌ها
// بدنهٔ هم را می‌خوردند و «Δ=۰» رویِ دادهٔ واقعی بی‌معنا می‌شد.
func TestCallKeysAreIsolated(t *testing.T) {
	s, _, _ := newTestService(t)
	var a, b int32
	fnA := func() (map[string]any, error) {
		atomic.AddInt32(&a, 1)
		return map[string]any{"status": "ok", "which": "a"}, nil
	}
	fnB := func() (map[string]any, error) {
		atomic.AddInt32(&b, 1)
		return map[string]any{"status": "ok", "which": "b"}, nil
	}
	gotA := s.Call("histogram|all", fnA, Options{})
	gotB := s.Call("histogram|stock", fnB, Options{})
	if gotA["which"] != "a" || gotB["which"] != "b" {
		t.Fatalf("cross-key body: a=%v b=%v", gotA, gotB)
	}
	if a != 1 || b != 1 {
		t.Fatalf("computes = %d/%d, want 1/1", a, b)
	}
	// همان تابع زیرِ کلیدِ دوم باید دوباره ساخته شود، نه از کشِ کلیدِ اول بخواند.
	s.Call("depth|all", fnA, Options{})
	if a != 2 {
		t.Fatalf("computes for second key = %d, want 2", a)
	}
}

// TestCallReturnsClone نگهبانِ کرنشِ کش است: دست‌کاریِ بدنهٔ برگشتی نباید کش را
// آلوده کند (پایتون هم dict() می‌دهد).
func TestCallReturnsClone(t *testing.T) {
	s, _, _ := newTestService(t)
	fn := func() (map[string]any, error) {
		return map[string]any{"status": "ok", "v": "clean"}, nil
	}
	out := s.Call("p", fn, Options{})
	out["status"] = "tampered"
	out["v"] = "dirty"
	out["extra"] = true
	again := s.Call("p", fn, Options{})
	if again["status"] != "ok" || again["v"] != "clean" {
		t.Fatalf("cache was mutated through the returned map: %v", again)
	}
	if _, ok := again["extra"]; ok {
		t.Fatalf("cache kept a key added to the returned map: %v", again)
	}
}

// TestCallBypassesWithoutSnapshotTable همان R8 است: نبودِ mstat_snap یعنی
// نشانه‌ای برایِ کلید نیست و پایتون همین‌جا کش را کامل دور می‌زند. اگر Go
// بکشد، رویِ بانکِ تازه (اولین بوت) بدنهٔ کهنه سرو می‌شود.
func TestCallBypassesWithoutSnapshotTable(t *testing.T) {
	raw, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	raw.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = raw.Close() })
	s := New(raw, t.TempDir(), nil)
	s.clock = time.Now
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	s.Call("p", fn, Options{})
	if n != 2 {
		t.Fatalf("computes without mstat_snap = %d, want 2 (cache must be bypassed)", n)
	}
	if _, ok := s.state(); ok {
		t.Fatal("state() reported a key while mstat_snap is missing")
	}
}

// TestCallInlineAndZeroTTLBypass دو اهرمِ بی‌کشیِ پایتون را می‌سنجد
// (refresh="inline" و ttl_s=0).
func TestCallInlineAndZeroTTLBypass(t *testing.T) {
	s, _, _ := newTestService(t)
	var inline, zero int32
	fnInline := func() (map[string]any, error) {
		atomic.AddInt32(&inline, 1)
		return map[string]any{"status": "ok"}, nil
	}
	fnZero := func() (map[string]any, error) {
		atomic.AddInt32(&zero, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("inline", fnInline, Options{Inline: true})
	s.Call("inline", fnInline, Options{Inline: true})
	s.Call("zero", fnZero, Options{TTL: -time.Second})
	s.Call("zero", fnZero, Options{TTL: -time.Second})
	if inline != 2 || zero != 2 {
		t.Fatalf("computes inline/zero = %d/%d, want 2/2", inline, zero)
	}
}

// TestMarkerNilDB مرزِ امنِ mstatMarker را نگه می‌دارد: سرویسِ بی‌بانک نباید
// پنیک کند، فقط کش را دور بزند.
func TestMarkerNilDB(t *testing.T) {
	if _, _, ok := mstatMarker(nil); ok {
		t.Fatal("mstatMarker(nil) reported a marker")
	}
}
