package instance

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"testing"
)

func TestSecondAcquireInSameProcessFails(t *testing.T) {
	dir := t.TempDir()
	first, err := Acquire(dir)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Acquire(dir); !errors.Is(err, ErrAlreadyRunning) {
		t.Fatalf("second acquire err = %v", err)
	}
	if err := first.Release(); err != nil {
		t.Fatal(err)
	}
	second, err := Acquire(dir)
	if err != nil {
		t.Fatalf("reacquire after release: %v", err)
	}
	_ = second.Release()
}

// Helper process برایِ اثباتِ قفل بین دو نمونهٔ واقعی. فقط در حالتِ env اجرا می‌شود.
func TestLockHelperProcess(t *testing.T) {
	if os.Getenv("BORS_LOCK_HELPER") != "1" {
		return
	}
	lock, err := Acquire(os.Getenv("BORS_LOCK_DIR"))
	if err != nil {
		fmt.Println("ERR", err)
		os.Exit(2)
	}
	fmt.Println("LOCKED")
	_, _ = io.Copy(io.Discard, os.Stdin)
	_ = lock.Release()
	os.Exit(0)
}

func TestSecondProcessIsRejected(t *testing.T) {
	dir := t.TempDir()
	cmd := exec.Command(os.Args[0], "-test.run=TestLockHelperProcess", "--")
	cmd.Env = append(os.Environ(), "BORS_LOCK_HELPER=1", "BORS_LOCK_DIR="+dir)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	line := make([]byte, 32)
	n, _ := stdout.Read(line)
	if got := string(line[:n]); got != "LOCKED\n" {
		_ = stdin.Close()
		_ = cmd.Wait()
		t.Fatalf("helper did not lock: %q", got)
	}
	if _, err := Acquire(dir); !errors.Is(err, ErrAlreadyRunning) {
		_ = stdin.Close()
		_ = cmd.Wait()
		t.Fatalf("parent acquired while child holds lock: %v", err)
	}
	_ = stdin.Close()
	if err := cmd.Wait(); err != nil {
		t.Fatalf("helper exit: %v", err)
	}
	lock, err := Acquire(dir)
	if err != nil {
		t.Fatalf("lock not released after child exit: %v", err)
	}
	_ = lock.Release()
}
