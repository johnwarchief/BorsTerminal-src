package config

import "testing"

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
	if cfg.ReadOnly || cfg.NoLoops {
		t.Fatalf("flags should default false")
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

func TestReadOnlyAndNoLoops(t *testing.T) {
	cfg, err := Load([]string{"--read-only", "--no-loops"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.ReadOnly || !cfg.NoLoops {
		t.Fatalf("flags not parsed: %+v", cfg)
	}
}
