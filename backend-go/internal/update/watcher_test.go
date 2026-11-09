package update

import (
	"encoding/json"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestInstallerFlagsPasswordAndRedaction(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, ".setup_password.iss"), "#define SetupPassword \"s3cret\"\n")
	flags := strings.Join(installerFlags(dir, `C:\tmp\install.log`), " ")
	if !strings.Contains(flags, "/PASSWORD=s3cret") {
		t.Fatalf("password flag missing: %s", flags)
	}
	if !strings.Contains(flags, "/VERYSILENT") || !strings.Contains(flags, "/CURRENTUSER") {
		t.Fatalf("silent/currentuser flags missing: %s", flags)
	}
	// exec.Command escapes quotes inside an argument, so a pre-quoted
	// /DIR="..." reaches Inno as /DIR=\"...\" and the installer exits 1 with
	// no log. Flags must carry the value unquoted and let exec do the quoting.
	for _, f := range installerFlags(dir, `C:\tmp\install.log`) {
		if strings.Contains(f, `"`) {
			t.Fatalf("installer flag must not embed quotes: %q", f)
		}
	}
	masked := strings.Join(MaskedInstallerFlags(dir), " ")
	if strings.Contains(masked, "s3cret") || !strings.Contains(masked, "/PASSWORD=<hidden>") {
		t.Fatalf("password leaked in masked flags: %s", masked)
	}
}

func TestInstallerFlagsWithoutPasswordDegradeToSilent(t *testing.T) {
	t.Setenv("BORS_SETUP_PASSWORD", "")
	flags := installerFlags(t.TempDir(), "log")
	if flags[0] != "/SILENT" {
		t.Fatalf("expected /SILENT fallback, got %v", flags)
	}
}

func TestHealthTimeoutEnv(t *testing.T) {
	t.Setenv("BORS_UPDATE_HEALTH_MS", "5000")
	if got := healthTimeout(time.Minute); got != 5*time.Second {
		t.Fatalf("healthTimeout = %v", got)
	}
	t.Setenv("BORS_UPDATE_HEALTH_MS", "")
	if got := healthTimeout(time.Minute); got != time.Minute {
		t.Fatalf("default healthTimeout = %v", got)
	}
}

func TestWaitHealthyMatchesVersion(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok", "version": "1.0.96"})
	}))
	defer srv.Close()
	port := srv.Listener.Addr().(*net.TCPAddr).Port
	if err := waitHealthy(port, "1.0.96", 2*time.Second); err != nil {
		t.Fatalf("matching version rejected: %v", err)
	}
	if err := waitHealthy(port, "1.0.97", 800*time.Millisecond); err == nil {
		t.Fatal("wrong version accepted")
	}
}

func TestPortOf(t *testing.T) {
	if got := portOf("127.0.0.1:8198"); got != 8198 {
		t.Fatalf("portOf = %d", got)
	}
	if got := portOf("127.0.0.1:0"); got != 0 {
		t.Fatalf("portOf zero = %d", got)
	}
	if got := portOf("bad"); got != 0 {
		t.Fatalf("portOf bad = %d", got)
	}
}

func TestBackupExcludesUpdateState(t *testing.T) {
	if !excludedFromBackup("update_last.json") || !excludedFromBackup("market.db") ||
		!excludedFromBackup("user.db-wal") || !excludedFromBackup(filepath.Join("oc", "oc_client.db")) {
		t.Fatal("user data/update state must be excluded from the rollback backup")
	}
	if excludedFromBackup("BorsTerminal_Ultimate.exe") || excludedFromBackup(filepath.Join("frontend", "index.html")) {
		t.Fatal("program files must be backed up")
	}
}

func TestWriteLastUpdateRoundTrip(t *testing.T) {
	dir := t.TempDir()
	writeLastUpdate(dir, LastUpdate{Status: "applied", From: "1.0.95", To: "1.0.96"})
	raw, err := os.ReadFile(filepath.Join(dir, "update_last.json"))
	if err != nil {
		t.Fatal(err)
	}
	var last LastUpdate
	if err := json.Unmarshal(raw, &last); err != nil || last.Status != "applied" || last.To != "1.0.96" {
		t.Fatalf("last update = %+v (%v)", last, err)
	}
}
