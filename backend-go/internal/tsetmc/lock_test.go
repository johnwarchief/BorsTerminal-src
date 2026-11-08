package tsetmc

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLock_AcquireAndRelease(t *testing.T) {
	dir := t.TempDir()

	lock, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("AcquireWriterLock failed: %v", err)
	}
	if lock == nil {
		t.Fatalf("expected non-nil lock")
	}

	lockFilePath := filepath.Join(dir, LockFileName)
	if _, err := os.Stat(lockFilePath); os.IsNotExist(err) {
		t.Fatalf("lock file %s does not exist on disk", lockFilePath)
	}

	data, err := os.ReadFile(lockFilePath)
	if err != nil {
		// On Windows byte 0 might be locked; fallback reader handles it
		data = readLockedFileFallback(lockFilePath)
	}
	if len(data) == 0 {
		t.Fatalf("lock file is empty")
	}

	var meta LockMetadata
	if err := json.Unmarshal(data, &meta); err != nil {
		t.Fatalf("failed to parse lock metadata: %v (raw=%s)", err, string(data))
	}

	if meta.PID != os.Getpid() {
		t.Errorf("expected PID %d, got %d", os.Getpid(), meta.PID)
	}
	if lock.PID() != os.Getpid() {
		t.Errorf("expected lock.PID() %d, got %d", os.Getpid(), lock.PID())
	}
	if meta.AcquiredAt == "" {
		t.Errorf("expected non-empty acquired_at")
	}
	if lock.AcquiredAt() != meta.AcquiredAt {
		t.Errorf("expected lock.AcquiredAt() %s, got %s", meta.AcquiredAt, lock.AcquiredAt())
	}

	// Release lock
	if err := lock.Release(); err != nil {
		t.Fatalf("lock.Release() failed: %v", err)
	}

	// Verify idempotency
	if err := lock.Release(); err != nil {
		t.Fatalf("second lock.Release() should be no-op, got %v", err)
	}
}

func TestLock_MutualExclusion_SameProcess(t *testing.T) {
	dir := t.TempDir()

	lock1, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("lock1 acquisition failed: %v", err)
	}
	defer lock1.Release()

	// Attempt acquire lock 2 on same dir
	lock2, err := AcquireWriterLock(dir)
	if err == nil {
		_ = lock2.Release()
		t.Fatalf("expected second acquire to fail, but succeeded")
	}

	if !errors.Is(err, ErrWriterLockHeld) {
		t.Fatalf("expected ErrWriterLockHeld, got %v", err)
	}
	if !strings.Contains(err.Error(), "writer lock already held") {
		t.Fatalf("expected error string to contain 'writer lock already held', got %v", err)
	}

	// Release lock 1
	if err := lock1.Release(); err != nil {
		t.Fatalf("lock1 release failed: %v", err)
	}

	// Now acquire lock 2 should succeed
	lock2, err = AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("expected lock2 acquisition to succeed after release, got %v", err)
	}
	if err := lock2.Release(); err != nil {
		t.Fatalf("lock2 release failed: %v", err)
	}
}

func TestLock_MutualExclusion_Subprocess(t *testing.T) {
	if os.Getenv("TEST_LOCK_SUBPROCESS") == "1" {
		dir := os.Getenv("TEST_LOCK_DIR")
		lock, err := AcquireWriterLock(dir)
		if err != nil {
			fmt.Fprintf(os.Stderr, "subprocess acquire failed: %v\n", err)
			os.Exit(1)
		}
		// Signal to parent that lock is acquired
		fmt.Println("READY")

		// Wait for parent signal to exit
		buf := make([]byte, 1)
		_, _ = os.Stdin.Read(buf)

		_ = lock.Release()
		os.Exit(0)
	}

	dir := t.TempDir()

	cmd := exec.Command(os.Args[0], "-test.run=^TestLock_MutualExclusion_Subprocess$")
	cmd.Env = append(os.Environ(), "TEST_LOCK_SUBPROCESS=1", "TEST_LOCK_DIR="+dir)

	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatalf("failed to create stdin pipe: %v", err)
	}
	defer stdin.Close()

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatalf("failed to create stdout pipe: %v", err)
	}

	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start subprocess: %v", err)
	}

	scanner := bufio.NewScanner(stdout)
	if !scanner.Scan() || scanner.Text() != "READY" {
		t.Fatalf("expected READY from subprocess, got %q (err=%v)", scanner.Text(), scanner.Err())
	}

	// Subprocess holds lock: attempt to acquire must fail
	lock2, err := AcquireWriterLock(dir)
	if err == nil {
		_ = lock2.Release()
		t.Fatalf("expected AcquireWriterLock to fail while subprocess holds lock, but succeeded")
	}
	if !errors.Is(err, ErrWriterLockHeld) {
		t.Fatalf("expected ErrWriterLockHeld, got %v", err)
	}
	if !strings.Contains(err.Error(), "writer lock already held") {
		t.Fatalf("expected error string to contain 'writer lock already held', got %v", err)
	}

	// Tell subprocess to release and exit
	_ = stdin.Close()
	if err := cmd.Wait(); err != nil {
		t.Fatalf("subprocess finished with error: %v", err)
	}

	// Parent can now acquire lock
	lock3, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("failed to acquire lock after subprocess exited: %v", err)
	}
	if err := lock3.Release(); err != nil {
		t.Fatalf("failed to release lock3: %v", err)
	}
}

func TestSubprocessCrashReleasesLock(t *testing.T) {
	if os.Getenv("TEST_LOCK_CRASH_SUBPROCESS") == "1" {
		dir := os.Getenv("TEST_LOCK_DIR")
		_, err := AcquireWriterLock(dir)
		if err != nil {
			os.Exit(1)
		}
		fmt.Println("READY")

		buf := make([]byte, 1)
		_, _ = os.Stdin.Read(buf)

		// Terminate immediately without calling Release()
		os.Exit(42)
	}

	dir := t.TempDir()

	cmd := exec.Command(os.Args[0], "-test.run=^TestSubprocessCrashReleasesLock$")
	cmd.Env = append(os.Environ(), "TEST_LOCK_CRASH_SUBPROCESS=1", "TEST_LOCK_DIR="+dir)

	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatalf("failed to create stdin pipe: %v", err)
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatalf("failed to create stdout pipe: %v", err)
	}

	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start subprocess: %v", err)
	}

	scanner := bufio.NewScanner(stdout)
	if !scanner.Scan() || scanner.Text() != "READY" {
		t.Fatalf("expected READY from subprocess, got %q", scanner.Text())
	}

	// Parent cannot acquire while subprocess is running
	_, err = AcquireWriterLock(dir)
	if !errors.Is(err, ErrWriterLockHeld) {
		t.Fatalf("expected ErrWriterLockHeld, got %v", err)
	}

	// Trigger crash
	_ = stdin.Close()
	_ = cmd.Wait()

	// OS kernel releases the lock; parent acquires cleanly
	lock, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("expected to acquire lock after subprocess crash, got %v", err)
	}
	if err := lock.Release(); err != nil {
		t.Fatalf("failed to release lock: %v", err)
	}
}

func TestAcquireWriterLockWithTimeout_Success(t *testing.T) {
	dir := t.TempDir()

	lock1, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("failed to acquire lock1: %v", err)
	}

	go func() {
		time.Sleep(100 * time.Millisecond)
		_ = lock1.Release()
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	lock2, err := AcquireWriterLockWithTimeout(ctx, dir, 20*time.Millisecond)
	if err != nil {
		t.Fatalf("AcquireWriterLockWithTimeout failed: %v", err)
	}
	defer lock2.Release()

	if lock2.PID() != os.Getpid() {
		t.Errorf("expected PID %d, got %d", os.Getpid(), lock2.PID())
	}
}

func TestAcquireWriterLockWithTimeout_ContextCanceled(t *testing.T) {
	dir := t.TempDir()

	lock1, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("failed to acquire lock1: %v", err)
	}
	defer lock1.Release()

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err = AcquireWriterLockWithTimeout(ctx, dir, 10*time.Millisecond)
	if err == nil {
		t.Fatalf("expected timeout error, got nil")
	}
	if !errors.Is(err, ErrWriterLockHeld) {
		t.Errorf("expected ErrWriterLockHeld in error chain, got %v", err)
	}
}

func TestInspectWriterLock_And_Liveness(t *testing.T) {
	dir := t.TempDir()

	// Initially no lock exists
	meta, alive, err := InspectWriterLock(dir)
	if err != nil {
		t.Fatalf("InspectWriterLock unexpected error: %v", err)
	}
	if meta != nil || alive {
		t.Errorf("expected nil meta and false alive, got meta=%+v alive=%v", meta, alive)
	}

	// Acquire lock
	lock, err := AcquireWriterLock(dir)
	if err != nil {
		t.Fatalf("AcquireWriterLock failed: %v", err)
	}
	defer lock.Release()

	meta, alive, err = InspectWriterLock(dir)
	if err != nil {
		t.Fatalf("InspectWriterLock failed: %v", err)
	}
	if meta == nil {
		t.Fatalf("expected non-nil meta")
	}
	if meta.PID != os.Getpid() {
		t.Errorf("expected PID %d, got %d", os.Getpid(), meta.PID)
	}
	if !alive {
		t.Errorf("expected current process to be alive")
	}

	// Check IsProcessAlive with current PID and an impossible PID
	if !IsProcessAlive(os.Getpid()) {
		t.Errorf("expected IsProcessAlive(os.Getpid()) to be true")
	}
	if IsProcessAlive(99999999) {
		t.Errorf("expected IsProcessAlive(99999999) to be false")
	}
}
