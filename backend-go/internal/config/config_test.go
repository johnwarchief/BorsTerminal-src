package config

import (
	"path/filepath"
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
	cfg, err := Load(nil, env(map[string]string{"BORS_DATA_DIR": "C:/data/a"}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != "C:\\data\\a" {
		t.Fatalf("env data dir = %q", cfg.DataDir)
	}
	cfg, err = Load([]string{"--db-dir", "C:/data/b"}, env(map[string]string{"BORS_DATA_DIR": "C:/data/a"}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != "C:\\data\\b" {
		t.Fatalf("flag should win, got %q", cfg.DataDir)
	}
	if cfg.MarketDB() != "C:\\data\\b\\market.db" {
		t.Fatalf("market path = %q", cfg.MarketDB())
	}
	if cfg.UserDB() != "C:\\data\\b\\user.db" {
		t.Fatalf("user path = %q", cfg.UserDB())
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
	cfg, err = Load(nil, env(map[string]string{"BORS_CALENDAR_PATH": "C:/cal/cache.json"}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.CalendarPath != "C:\\cal\\cache.json" {
		t.Fatalf("env calendar path = %q", cfg.CalendarPath)
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
