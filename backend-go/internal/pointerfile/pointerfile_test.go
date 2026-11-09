package pointerfile

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReplaceMovesContent(t *testing.T) {
	dir := t.TempDir()
	tmp := filepath.Join(dir, "active_generation.json.tmp")
	dst := filepath.Join(dir, "active_generation.json")
	if err := os.WriteFile(tmp, []byte(`{"v":2}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(dst, []byte(`{"v":1}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := Replace(tmp, dst); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != `{"v":2}` {
		t.Fatalf("content = %q", got)
	}
	if _, err := os.Stat(tmp); !os.IsNotExist(err) {
		t.Fatalf("temp file still exists: %v", err)
	}
}
