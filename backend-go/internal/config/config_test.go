package config

import (
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(nil, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Addr != "127.0.0.1:8198" {
		t.Fatalf("addr = %q", cfg.Addr)
	}
	// فاز A: خواندنِ فقط پیش‌فرض است، حتی وقتی هیچ پرچمی داده نشود.
	if !cfg.ReadOnly || cfg.NoLoops {
		t.Fatalf("defaults: read-only must be true, no-loops false: %+v", cfg)
	}
}

func TestPortFlagBeatsDefault(t *testing.T) {
	cfg, err := Load([]string{"--port", "8298"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Addr != "127.0.0.1:8298" {
		t.Fatalf("addr = %q", cfg.Addr)
	}
}

func TestDataDirPrecedence(t *testing.T) {
	dirA := "/data/a"
	dirB := "/data/b"
	if runtime.GOOS == "windows" {
		dirA = "C:/data/a"
		dirB = "C:/data/b"
	}
	expectedA, err := filepath.Abs(dirA)
	if err != nil {
		t.Fatal(err)
	}
	expectedB, err := filepath.Abs(dirB)
	if err != nil {
		t.Fatal(err)
	}

	cfg, err := Load(nil, env(map[string]string{"BORS_DATA_DIR": dirA}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != expectedA {
		t.Fatalf("env data dir = %q, want %q", cfg.DataDir, expectedA)
	}
	if runtime.GOOS == "windows" && cfg.DataDir != "C:\\data\\a" {
		t.Fatalf("env data dir on windows must be strictly C:\\data\\a, got %q", cfg.DataDir)
	}

	cfg, err = Load([]string{"--db-dir", dirB}, env(map[string]string{"BORS_DATA_DIR": dirA}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != expectedB {
		t.Fatalf("flag should win, got %q, want %q", cfg.DataDir, expectedB)
	}
	if runtime.GOOS == "windows" && cfg.DataDir != "C:\\data\\b" {
		t.Fatalf("flag data dir on windows must be strictly C:\\data\\b, got %q", cfg.DataDir)
	}

	expectedMarket := filepath.Join(expectedB, "market.db")
	if cfg.MarketDB() != expectedMarket {
		t.Fatalf("market path = %q, want %q", cfg.MarketDB(), expectedMarket)
	}
	if runtime.GOOS == "windows" && cfg.MarketDB() != "C:\\data\\b\\market.db" {
		t.Fatalf("market path on windows must be strictly C:\\data\\b\\market.db, got %q", cfg.MarketDB())
	}

	expectedUser := filepath.Join(expectedB, "user.db")
	if cfg.UserDB() != expectedUser {
		t.Fatalf("user path = %q, want %q", cfg.UserDB(), expectedUser)
	}
	if runtime.GOOS == "windows" && cfg.UserDB() != "C:\\data\\b\\user.db" {
		t.Fatalf("user path on windows must be strictly C:\\data\\b\\user.db, got %q", cfg.UserDB())
	}
}

func TestCalendarPath(t *testing.T) {
	cfg, err := Load(nil, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(cfg.CalendarPath, filepath.Join("static", "calendar", "cache.json")) {
		t.Fatalf("default calendar path = %q", cfg.CalendarPath)
	}

	calPath := "/cal/cache.json"
	if runtime.GOOS == "windows" {
		calPath = "C:/cal/cache.json"
	}
	expectedCal, err := filepath.Abs(calPath)
	if err != nil {
		t.Fatal(err)
	}

	cfg, err = Load(nil, env(map[string]string{"BORS_CALENDAR_PATH": calPath}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.CalendarPath != expectedCal {
		t.Fatalf("env calendar path = %q, want %q", cfg.CalendarPath, expectedCal)
	}
	if runtime.GOOS == "windows" && cfg.CalendarPath != "C:\\cal\\cache.json" {
		t.Fatalf("env calendar path on windows must be strictly C:\\cal\\cache.json, got %q", cfg.CalendarPath)
	}
}

func TestReadOnlyAndNoLoops(t *testing.T) {
	cfg, err := Load([]string{"--read-only", "--no-loops"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.ReadOnly || !cfg.NoLoops {
		t.Fatalf("flags not parsed: %+v", cfg)
	}
}

func TestReadWriteTurnsReadOnlyOff(t *testing.T) {
	cfg, err := Load([]string{"--read-write"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ReadOnly {
		t.Fatalf("--read-write must turn read-only off: %+v", cfg)
	}
	// صریح برنده است، حتی وقتی هر دو داده شوند.
	cfg, err = Load([]string{"--read-only", "--read-write"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ReadOnly {
		t.Fatalf("read-write wins over explicit read-only: %+v", cfg)
	}
	// خاموش‌کردنِ صریحِ read-only هم باید کار کند.
	cfg, err = Load([]string{"--read-only=false"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ReadOnly {
		t.Fatalf("--read-only=false must be false: %+v", cfg)
	}
}
