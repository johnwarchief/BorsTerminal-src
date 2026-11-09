//go:build windows

package pointerfile

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// TestReplaceRetriesWhileReaderIsOpen: os.Rename رویِ ویندوز تا وقتی دستهٔ
// خواننده باز است ACCESS_DENIED می‌دهد؛ Replace باید بعد از بسته‌شدنِ آن
// موفق شود، بدونِ حذفِ مقصد (اتمی بودن حفظ می‌شود).
func TestReplaceRetriesWhileReaderIsOpen(t *testing.T) {
	dir := t.TempDir()
	dst := filepath.Join(dir, "active_generation.json")
	tmp := filepath.Join(dir, "active_generation.json.tmp")
	if err := os.WriteFile(dst, []byte(`{"v":1}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(tmp, []byte(`{"v":2}`), 0o644); err != nil {
		t.Fatal(err)
	}

	reader, err := os.Open(dst)
	if err != nil {
		t.Fatal(err)
	}
	// کنترلِ منفی: بدونِ retry، همان لحظه شکست می‌خورد.
	if err := os.Rename(tmp, dst); err == nil {
		reader.Close()
		t.Fatal("os.Rename unexpectedly succeeded with an open reader; sensor is blind")
	}

	done := make(chan error, 1)
	go func() { done <- Replace(tmp, dst) }()
	select {
	case err := <-done:
		reader.Close()
		t.Fatalf("Replace returned before the reader closed: %v", err)
	case <-time.After(30 * time.Millisecond):
	}
	reader.Close()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Replace failed after the reader closed: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("Replace did not finish after the reader closed")
	}
	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != `{"v":2}` {
		t.Fatalf("content = %q", got)
	}
}
