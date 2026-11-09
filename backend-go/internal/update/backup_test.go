package update

import (
	"os"
	"path/filepath"
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

func readFile(t *testing.T, path string) string {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(raw)
}

func TestBackupAndRestoreProgramFiles(t *testing.T) {
	install := t.TempDir()
	data := t.TempDir()
	writeFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe"), "old-exe")
	writeFile(t, filepath.Join(install, "BorsTerminal_Shell.exe"), "old-shell")
	writeFile(t, filepath.Join(install, "frontend", "index.html"), "old-index")
	writeFile(t, filepath.Join(install, "frontend", "assets", "app.js"), "old-js")
	writeFile(t, filepath.Join(install, "market.db"), "MARKET-USER-DATA")
	writeFile(t, filepath.Join(install, "market.db-wal"), "WAL")
	writeFile(t, filepath.Join(install, "user.db"), "USER-DB")
	writeFile(t, filepath.Join(install, "oc_client.db"), "OC-DB")
	writeFile(t, filepath.Join(install, ".screener_cache.json"), "CACHE")
	writeFile(t, filepath.Join(install, "market.db.gz"), "SEED")
	writeFile(t, filepath.Join(install, "Version.txt"), "app_version=1.0.95\n")

	backupDir, err := backupProgramFiles(install, data, "1.0.95")
	if err != nil {
		t.Fatalf("backup: %v", err)
	}
	if _, err := os.Stat(filepath.Join(backupDir, "BorsTerminal_Ultimate.exe")); err != nil {
		t.Fatalf("backup missing exe: %v", err)
	}
	for _, name := range []string{"market.db", "market.db-wal", "user.db", "oc_client.db", ".screener_cache.json", "market.db.gz"} {
		if _, err := os.Stat(filepath.Join(backupDir, name)); err == nil {
			t.Fatalf("user data %s must not be in the rollback backup", name)
		}
	}

	// Simulate a half-applied new version.
	writeFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe"), "new-exe-broken")
	writeFile(t, filepath.Join(install, "BorsTerminal_Shell.exe"), "new-shell")
	writeFile(t, filepath.Join(install, "frontend", "index.html"), "new-index")
	writeFile(t, filepath.Join(install, "frontend", "assets", "new-chunk.js"), "new-js")
	writeFile(t, filepath.Join(install, "Version.txt"), "app_version=1.0.96\n")
	writeFile(t, filepath.Join(install, "user.db"), "USER-DB-CHANGED-AFTER-UPDATE")

	if err := restoreBackup(install, backupDir); err != nil {
		t.Fatalf("restore: %v", err)
	}
	if got := readFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe")); got != "old-exe" {
		t.Fatalf("exe = %q", got)
	}
	if got := readFile(t, filepath.Join(install, "BorsTerminal_Shell.exe")); got != "old-shell" {
		t.Fatalf("shell = %q", got)
	}
	if got := readFile(t, filepath.Join(install, "frontend", "index.html")); got != "old-index" {
		t.Fatalf("index = %q", got)
	}
	if _, err := os.Stat(filepath.Join(install, "frontend", "assets", "new-chunk.js")); err == nil {
		t.Fatal("rollback left a new-version frontend file behind")
	}
	if got := readFile(t, filepath.Join(install, "user.db")); got != "USER-DB-CHANGED-AFTER-UPDATE" {
		t.Fatalf("rollback must not touch user.db, got %q", got)
	}
	if got := readFile(t, filepath.Join(install, "market.db")); got != "MARKET-USER-DATA" {
		t.Fatalf("rollback must not touch market.db, got %q", got)
	}
	if got := readFile(t, filepath.Join(install, "Version.txt")); got != "app_version=1.0.95\n" {
		t.Fatalf("version file = %q", got)
	}
}

func TestRestoreRejectsCorruptBackup(t *testing.T) {
	install := t.TempDir()
	data := t.TempDir()
	writeFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe"), "old-exe")
	writeFile(t, filepath.Join(install, "user.db"), "USER")
	backupDir, err := backupProgramFiles(install, data, "1.0.95")
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(backupDir, "BorsTerminal_Ultimate.exe"), "corrupted-backup")
	if err := restoreBackup(install, backupDir); err == nil {
		t.Fatal("corrupt backup must be rejected before overwriting the install")
	}
	if got := readFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe")); got != "old-exe" {
		t.Fatalf("install changed despite rejected backup: %q", got)
	}
}

func TestBackupVersionReadsManifest(t *testing.T) {
	data := t.TempDir()
	install := t.TempDir()
	writeFile(t, filepath.Join(install, "BorsTerminal_Ultimate.exe"), "exe")
	if _, err := backupProgramFiles(install, data, "1.0.95"); err != nil {
		t.Fatal(err)
	}
	svc := New(Config{DataDir: data, InstallDir: install, CurrentVersion: "1.0.96"})
	info := svc.VersionInfo()
	if !info.RollbackAvailable || info.RollbackVersion != "1.0.95" {
		t.Fatalf("info = %+v", info)
	}
}
