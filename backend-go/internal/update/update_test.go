package update

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCompareVersions(t *testing.T) {
	cases := []struct {
		a, b string
		want int
	}{
		{"1.0.95", "1.0.96", -1},
		{"1.0.96", "1.0.95", 1},
		{"1.0.96", "1.0.96", 0},
		{"1.0", "1.0.0", 0},
		{"1.0.9", "1.0.10", -1},
		{"2.0", "1.99.99", 1},
		{"dev", "1.0.0", -1},
	}
	for _, c := range cases {
		if got := compareVersions(c.a, c.b); got != c.want {
			t.Errorf("compareVersions(%q,%q)=%d want %d", c.a, c.b, got, c.want)
		}
	}
}

func TestManifestRequiresGoChannel(t *testing.T) {
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95"})
	legacy := Manifest{Version: "1.0.98", Platforms: map[string]Asset{
		PlatformKey: {URL: "https://example.com/setup.exe", Signature: "sig"},
	}}
	if err := svc.validateManifest(&legacy); err == nil {
		t.Fatal("legacy manifest without channel=go must be rejected")
	}
	legacy.Channel = "python"
	if err := svc.validateManifest(&legacy); err == nil {
		t.Fatal("channel=python must be rejected")
	}
	legacy.Channel = "go"
	legacy.Version = ""
	if err := svc.validateManifest(&legacy); err == nil {
		t.Fatal("empty version must be rejected")
	}
}

func TestCheckAvailableAndOlder(t *testing.T) {
	manifest := Manifest{
		Channel: "go",
		Version: "1.0.96",
		Notes:   "test",
		Platforms: map[string]Asset{
			PlatformKey: {URL: "http://127.0.0.1:1/setup.exe", Signature: "sig", Size: 10},
		},
	}
	path := filepath.Join(t.TempDir(), "latest-go.json")
	raw, _ := json.Marshal(manifest)
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: path})
	res, err := svc.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if !res.Available || res.LatestVersion != "1.0.96" {
		t.Fatalf("res = %+v", res)
	}
	svc.cfg.CurrentVersion = "1.0.96"
	res, err = svc.Check(context.Background())
	if err != nil {
		t.Fatalf("Check same: %v", err)
	}
	if res.Available {
		t.Fatalf("same version reported available: %+v", res)
	}
	svc.cfg.CurrentVersion = "1.0.97"
	res, err = svc.Check(context.Background())
	if err != nil {
		t.Fatalf("Check newer: %v", err)
	}
	if res.Available {
		t.Fatalf("older manifest reported available: %+v", res)
	}
}

func TestCheckRejectsInsecureRemoteURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(Manifest{
			Channel: "go", Version: "1.0.96",
			Platforms: map[string]Asset{
				PlatformKey: {URL: "http://evil.example.com/setup.exe", Signature: "sig", Size: 10},
			},
		})
	}))
	defer srv.Close()
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	if _, err := svc.Check(context.Background()); err == nil {
		t.Fatal("non-loopback http asset URL must be rejected")
	}
}

func TestCheckAllowsLoopbackHTTP(t *testing.T) {
	var base string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(Manifest{
			Channel: "go", Version: "1.0.96",
			Platforms: map[string]Asset{
				PlatformKey: {URL: base + "/setup.exe", Signature: "sig", Size: 10},
			},
		})
	}))
	defer srv.Close()
	base = srv.URL
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	res, err := svc.Check(context.Background())
	if err != nil {
		t.Fatalf("loopback http rejected: %v", err)
	}
	if !res.Available {
		t.Fatalf("res = %+v", res)
	}
}

func TestResolveVersionFromFile(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "Version.txt"), []byte("app_version=1.2.3\nsource=installer\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := versionFromFile(dir); got != "1.2.3" {
		t.Fatalf("versionFromFile = %q", got)
	}
	if got := versionFromFile(t.TempDir()); got != "" {
		t.Fatalf("missing version file = %q", got)
	}
}

func TestVersionInfoPortableAndRollback(t *testing.T) {
	data := t.TempDir()
	install := t.TempDir()
	if err := os.WriteFile(filepath.Join(install, "bors_portable.flag"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	backup := filepath.Join(data, "backups", "app-before-update")
	if err := os.MkdirAll(backup, 0o755); err != nil {
		t.Fatal(err)
	}
	_ = os.WriteFile(filepath.Join(backup, "backup.json"), []byte(`{"version":"1.0.95"}`), 0o644)
	svc := New(Config{DataDir: data, InstallDir: install, CurrentVersion: "1.0.96"})
	info := svc.VersionInfo()
	if info.Mode != "portable" || !info.RollbackAvailable || info.RollbackVersion != "1.0.95" {
		t.Fatalf("info = %+v", info)
	}
	if !strings.Contains(info.Version, "1.0.96") {
		t.Fatalf("version = %q", info.Version)
	}
}
