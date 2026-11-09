package generation

import (
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"testing"
)

func writeFile(t *testing.T, path, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writePointer(t *testing.T, dataDir string, p Pointer) {
	t.Helper()
	raw, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(dataDir, PointerFile), string(raw))
}

func makeGen(t *testing.T, dataDir, name string, withCodal bool) string {
	t.Helper()
	dir := filepath.Join(dataDir, "gens", name)
	writeFile(t, filepath.Join(dir, "market.db"), "not a real sqlite db")
	if withCodal {
		writeFile(t, filepath.Join(dir, "codal.db"), "codal")
	}
	return dir
}

func TestResolveLegacyWithoutPointer(t *testing.T) {
	dataDir := t.TempDir()
	info, err := New(dataDir).Resolve()
	if err != nil {
		t.Fatal(err)
	}
	if info.Active {
		t.Fatal("expected legacy mode without pointer")
	}
	if info.MarketPath != filepath.Join(dataDir, "market.db") {
		t.Fatalf("market path = %s", info.MarketPath)
	}
	if info.Identity() != "legacy" {
		t.Fatalf("identity = %s", info.Identity())
	}
}

func TestResolveActiveGeneration(t *testing.T) {
	dataDir := t.TempDir()
	gen := makeGen(t, dataDir, "gen_abc", true)
	writePointer(t, dataDir, Pointer{
		SnapshotSetID: "abc", GenerationDir: "gens/gen_abc", SchemaVersion: 1,
	})
	info, err := New(dataDir).Resolve()
	if err != nil {
		t.Fatal(err)
	}
	if !info.Active || info.Identity() != "gen:abc" {
		t.Fatalf("active=%v identity=%s", info.Active, info.Identity())
	}
	if info.MarketPath != filepath.Join(gen, "market.db") {
		t.Fatalf("market = %s", info.MarketPath)
	}
	if info.CodalPath != filepath.Join(gen, "codal.db") {
		t.Fatalf("codal = %s", info.CodalPath)
	}
	if info.UserDir != dataDir {
		t.Fatalf("user dir must stay dataDir, got %s", info.UserDir)
	}
}

func TestResolveMissingCodalDoesNotFallBack(t *testing.T) {
	dataDir := t.TempDir()
	makeGen(t, dataDir, "gen_nocodal", false)
	writePointer(t, dataDir, Pointer{SnapshotSetID: "nocodal", GenerationDir: "gens/gen_nocodal", SchemaVersion: 1})
	info, err := New(dataDir).Resolve()
	if err != nil {
		t.Fatal(err)
	}
	if info.CodalPath != "" {
		t.Fatalf("codal must be empty, not legacy path; got %s", info.CodalPath)
	}
}

func TestResolveRejectsBrokenPointers(t *testing.T) {
	cases := []struct {
		name  string
		setup func(t *testing.T, dataDir string)
	}{
		{"invalid json", func(t *testing.T, d string) {
			writeFile(t, filepath.Join(d, PointerFile), "{not json")
		}},
		{"empty set id", func(t *testing.T, d string) {
			writePointer(t, d, Pointer{GenerationDir: "gens/gen_x", SchemaVersion: 1})
		}},
		{"missing dir", func(t *testing.T, d string) {
			writePointer(t, d, Pointer{SnapshotSetID: "x", GenerationDir: "gens/gen_x", SchemaVersion: 1})
		}},
		{"missing market.db", func(t *testing.T, d string) {
			dir := filepath.Join(d, "gens", "gen_y")
			if err := os.MkdirAll(dir, 0o755); err != nil {
				t.Fatal(err)
			}
			writePointer(t, d, Pointer{SnapshotSetID: "y", GenerationDir: "gens/gen_y", SchemaVersion: 1})
		}},
		{"schema zero", func(t *testing.T, d string) {
			makeGen(t, d, "gen_z", false)
			writePointer(t, d, Pointer{SnapshotSetID: "z", GenerationDir: "gens/gen_z"})
		}},
		{"path escape", func(t *testing.T, d string) {
			outside := t.TempDir()
			writeFile(t, filepath.Join(outside, "market.db"), "x")
			writePointer(t, d, Pointer{SnapshotSetID: "e", GenerationDir: outside, SchemaVersion: 1})
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			dataDir := t.TempDir()
			tc.setup(t, dataDir)
			_, err := New(dataDir).Resolve()
			if !errors.Is(err, ErrInvalidPointer) {
				t.Fatalf("want ErrInvalidPointer, got %v", err)
			}
		})
	}
}

func TestCurrentPointer(t *testing.T) {
	dataDir := t.TempDir()
	writePointer(t, dataDir, Pointer{SnapshotSetID: "p1", GenerationDir: "gens/gen_p1", SchemaVersion: 1})
	p, err := New(dataDir).CurrentPointer()
	if err != nil || p == nil || p.SnapshotSetID != "p1" {
		t.Fatalf("pointer=%+v err=%v", p, err)
	}
}

// dirLink یک symlink (یا رویِ ویندوز junction که بدونِ ادمین ساخته می‌شود)
// می‌سازد؛ اگر محیط اجازه نداد تست skip می‌شود، نه پاس.
func dirLink(t *testing.T, target, link string) {
	t.Helper()
	if err := os.Symlink(target, link); err == nil {
		return
	}
	if runtime.GOOS == "windows" {
		if out, err := exec.Command("cmd", "/c", "mklink", "/J", link, target).CombinedOutput(); err == nil {
			return
		} else {
			t.Skipf("cannot create symlink or junction: %v (%s)", err, out)
		}
	}
	t.Skip("cannot create symlink in this environment")
}

func TestResolveRejectsSymlinkedGenerationEscape(t *testing.T) {
	dataDir := t.TempDir()
	outside := t.TempDir()
	writeFile(t, filepath.Join(outside, "market.db"), "outside")

	link := filepath.Join(dataDir, "gens", "link")
	if err := os.MkdirAll(filepath.Dir(link), 0o755); err != nil {
		t.Fatal(err)
	}
	dirLink(t, outside, link)
	writePointer(t, dataDir, Pointer{SnapshotSetID: "link", GenerationDir: "gens/link", SchemaVersion: 1})

	_, err := New(dataDir).Resolve()
	if !errors.Is(err, ErrInvalidPointer) {
		t.Fatalf("generation_dir via reparse point must be rejected, got %v", err)
	}
}

func TestResolveRejectsSymlinkedMarketDB(t *testing.T) {
	dataDir := t.TempDir()
	gen := filepath.Join(dataDir, "gens", "gen_linked_db")
	if err := os.MkdirAll(gen, 0o755); err != nil {
		t.Fatal(err)
	}
	outsideDB := filepath.Join(t.TempDir(), "outside.db")
	writeFile(t, outsideDB, "outside")
	if err := os.Symlink(outsideDB, filepath.Join(gen, "market.db")); err != nil {
		t.Skipf("cannot create file symlink: %v", err)
	}
	writePointer(t, dataDir, Pointer{SnapshotSetID: "linked_db", GenerationDir: "gens/gen_linked_db", SchemaVersion: 1})

	_, err := New(dataDir).Resolve()
	if !errors.Is(err, ErrInvalidPointer) {
		t.Fatalf("symlinked market.db must be rejected, got %v", err)
	}
}
