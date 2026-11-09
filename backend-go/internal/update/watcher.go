package update

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// watchRequest is written next to the watcher copy and passed on its command
// line. It contains no secrets; the installer password is read at install time
// from the same gitignored file the Python updater used.
type watchRequest struct {
	Mode         string   `json:"mode"`
	ParentPID    int      `json:"parent_pid"`
	InstallDir   string   `json:"install_dir"`
	DataDir      string   `json:"data_dir"`
	Port         int      `json:"port"`
	OldVersion   string   `json:"old_version"`
	NewVersion   string   `json:"new_version"`
	BackupDir    string   `json:"backup_dir,omitempty"`
	Installer    string   `json:"installer,omitempty"`
	Signature    string   `json:"signature,omitempty"`
	SHA256       string   `json:"sha256,omitempty"`
	RelaunchArgs []string `json:"relaunch_args"`
	LogPath      string   `json:"log_path"`
}

// Install verifies the downloaded installer again, snapshots the program
// files, then hands the install to a detached watcher and shuts this process
// down. The watcher installs, starts the new version, health-checks it and
// restores the snapshot if anything fails.
func (s *Service) Install(ctx context.Context) error {
	st := s.Progress()
	if st.Status != StatusReady || strings.TrimSpace(st.Path) == "" {
		return errors.New("بستهٔ آماده‌ای نیست؛ ابتدا دانلود را کامل کنید")
	}
	if s.VersionInfo().Mode == "portable" {
		return errors.New("نسخهٔ Portable با نصاب به‌روزرسانی نمی‌شود؛ ZIPِ تازه را دانلود کنید")
	}
	if !s.beginInstall() {
		return errors.New("نصبِ دیگری در جریان است")
	}
	if err := verifyArtifact(st.Path, st.Signature); err != nil {
		s.fail("راستی‌آزماییِ دوبارهٔ امضا ناموفق: "+err.Error(), st.Path)
		return err
	}
	sum, size, err := hashFile(st.Path)
	if err != nil {
		return fmt.Errorf("خواندنِ نصب‌کننده ناموفق: %w", err)
	}
	if st.SHA256 != "" && !strings.EqualFold(st.SHA256, sum) {
		s.fail("فایلِ نصب پس از دانلود تغییر کرده است", st.Path)
		return errors.New("فایلِ نصب پس از دانلود تغییر کرده است")
	}
	if st.Total > 0 && size != st.Total {
		s.fail("اندازهٔ فایلِ نصب پس از دانلود تغییر کرده است", st.Path)
		return errors.New("اندازهٔ فایلِ نصب پس از دانلود تغییر کرده است")
	}

	backupDir, err := backupProgramFiles(s.cfg.InstallDir, s.cfg.DataDir, s.CurrentVersion())
	if err != nil {
		s.fail("پشتیبان‌گیری از فایل‌های برنامه ناموفق: "+err.Error(), st.Path)
		return fmt.Errorf("پشتیبان‌گیری از فایل‌های برنامه ناموفق: %w", err)
	}
	req := watchRequest{
		Mode:         "install",
		ParentPID:    os.Getpid(),
		InstallDir:   s.cfg.InstallDir,
		DataDir:      s.cfg.DataDir,
		Port:         s.cfg.Port,
		OldVersion:   s.CurrentVersion(),
		NewVersion:   st.Version,
		BackupDir:    backupDir,
		Installer:    st.Path,
		Signature:    st.Signature,
		SHA256:       sum,
		RelaunchArgs: s.cfg.Args,
	}
	writeLastUpdate(s.cfg.DataDir, LastUpdate{Status: "installing", From: req.OldVersion, To: req.NewVersion,
		At: s.cfg.Now().UTC().Format(time.RFC3339), Message: "در حال نصبِ نسخهٔ تازه"})
	if err := startWatcher(req, s.log); err != nil {
		s.fail("اجرای نگهبانِ نصب ناموفق: "+err.Error(), st.Path)
		return fmt.Errorf("اجرای نگهبانِ نصب ناموفق: %w", err)
	}
	s.setState(func(st *State) {
		st.Status = StatusInstalling
		st.Message = "در حال نصب و راه‌اندازیِ دوباره"
	})
	if s.cfg.Shutdown != nil {
		go func() {
			time.Sleep(1200 * time.Millisecond)
			s.cfg.Shutdown()
		}()
	}
	return nil
}

// Rollback restores the program files snapshotted before the last update and
// restarts the previous version through the same detached watcher.
func (s *Service) Rollback(ctx context.Context) error {
	if !s.beginInstall() {
		return errors.New("نصب یا بازگشتی از قبل در جریان است")
	}
	backupDir := filepath.Join(s.cfg.DataDir, "backups", backupDirName)
	manifest, err := readBackupManifest(backupDir)
	if err != nil {
		s.abortInstall("پشتیبانِ نسخهٔ قبلی در دسترس نیست: " + err.Error())
		return fmt.Errorf("پشتیبانِ نسخهٔ قبلی در دسترس نیست: %w", err)
	}
	req := watchRequest{
		Mode:         "rollback",
		ParentPID:    os.Getpid(),
		InstallDir:   s.cfg.InstallDir,
		DataDir:      s.cfg.DataDir,
		Port:         s.cfg.Port,
		OldVersion:   manifest.Version,
		NewVersion:   s.CurrentVersion(),
		BackupDir:    backupDir,
		RelaunchArgs: s.cfg.Args,
	}
	writeLastUpdate(s.cfg.DataDir, LastUpdate{Status: "rolling_back", From: req.NewVersion, To: req.OldVersion,
		At: s.cfg.Now().UTC().Format(time.RFC3339), Message: "در حال بازگشت به نسخهٔ قبلی"})
	if err := startWatcher(req, s.log); err != nil {
		s.abortInstall("اجرای نگهبانِ بازگشت ناموفق: " + err.Error())
		return fmt.Errorf("اجرای نگهبانِ بازگشت ناموفق: %w", err)
	}
	s.setState(func(st *State) {
		st.Status = StatusInstalling
		st.Message = "در حال بازگشت به نسخهٔ قبلی"
	})
	if s.cfg.Shutdown != nil {
		go func() {
			time.Sleep(1200 * time.Millisecond)
			s.cfg.Shutdown()
		}()
	}
	return nil
}

func (s *Service) beginInstall() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.installing {
		return false
	}
	s.installing = true
	return true
}

func (s *Service) abortInstall(message string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.installing = false
	s.state.Status = StatusError
	s.state.Message = message
	s.state.UpdatedAt = s.cfg.Now().UTC().Format(time.RFC3339)
}

func startWatcher(req watchRequest, log *slog.Logger) error {
	req.LogPath = filepath.Join(req.DataDir, "updates", fmt.Sprintf("update-%d.log", time.Now().Unix()))
	if err := os.MkdirAll(filepath.Dir(req.LogPath), 0o755); err != nil {
		return err
	}
	workDir := filepath.Join(os.TempDir(), "bors_update",
		fmt.Sprintf("watch-%d-%08x", os.Getpid(), crc32.ChecksumIEEE([]byte(req.LogPath))))
	if err := os.MkdirAll(workDir, 0o755); err != nil {
		return err
	}
	self, err := os.Executable()
	if err != nil {
		return err
	}
	watchExe := filepath.Join(workDir, "borsd_update_watch.exe")
	if runtime.GOOS != "windows" {
		watchExe = filepath.Join(workDir, "borsd_update_watch")
	}
	if _, _, err := copyFileHashed(self, watchExe); err != nil {
		return fmt.Errorf("copy watcher: %w", err)
	}
	reqPath := filepath.Join(workDir, "request.json")
	raw, err := json.MarshalIndent(req, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(reqPath, raw, 0o644); err != nil {
		return err
	}
	cmd := exec.Command(watchExe, "--update-watch", reqPath)
	cmd.Dir = workDir
	detachProcess(cmd)
	if err := cmd.Start(); err != nil {
		return err
	}
	log.Info("update watcher started", "pid", cmd.Process.Pid, "mode", req.Mode,
		"from", req.OldVersion, "to", req.NewVersion)
	return nil
}

// RunWatcher is the detached process entry point ("borsd --update-watch
// <request.json>"). It waits for the app to exit, applies the change, starts
// the app again and rolls back when the new version cannot prove it is alive.
func RunWatcher(requestPath string) error {
	raw, err := os.ReadFile(requestPath)
	if err != nil {
		return err
	}
	var req watchRequest
	if err := json.Unmarshal(raw, &req); err != nil {
		return err
	}
	logger, closeLog := watcherLogger(req.LogPath)
	defer closeLog()
	req = normalizeRequest(req)
	logger.Info("watcher start", "mode", req.Mode, "parent", req.ParentPID,
		"install", req.InstallDir, "data", req.DataDir, "port", req.Port,
		"from", req.OldVersion, "to", req.NewVersion)

	if req.ParentPID > 0 {
		if err := waitForProcessExit(req.ParentPID, 180*time.Second); err != nil {
			logger.Error("parent did not exit; refusing to install over a running app", "err", err)
			writeLastUpdate(req.DataDir, LastUpdate{Status: "failed", From: req.OldVersion, To: req.NewVersion,
				At: time.Now().UTC().Format(time.RFC3339), Message: "برنامهٔ در حال اجرا بسته نشد؛ نصب انجام نشد"})
			return err
		}
	}
	time.Sleep(2 * time.Second)

	switch req.Mode {
	case "install":
		return runInstall(req, logger)
	case "rollback":
		return runRollback(req, logger)
	default:
		return fmt.Errorf("unknown watcher mode %q", req.Mode)
	}
}

func normalizeRequest(req watchRequest) watchRequest {
	if req.InstallDir == "" {
		req.InstallDir = "."
	}
	if req.DataDir == "" {
		req.DataDir = req.InstallDir
	}
	return req
}

func runInstall(req watchRequest, logger *slog.Logger) error {
	// Defense in depth: the artifact is verified again immediately before it
	// is executed, even though the download already verified it.
	if err := verifyArtifact(req.Installer, req.Signature); err != nil {
		return failAndRestore(req, logger, "راستی‌آزماییِ نصب‌کننده پیش از اجرا ناموفق: "+err.Error())
	}
	if sum, _, err := hashFile(req.Installer); err != nil || (req.SHA256 != "" && !strings.EqualFold(sum, req.SHA256)) {
		return failAndRestore(req, logger, "هشِ نصب‌کننده پیش از اجرا نمی‌خواند")
	}

	logPath := strings.TrimSuffix(req.LogPath, ".log") + "-installer.log"
	cmd := exec.Command(req.Installer, installerFlags(req.InstallDir, logPath)...)
	cmd.Dir = req.InstallDir
	out, err := cmd.CombinedOutput()
	logger.Info("installer finished", "err", err, "output_tail", tail(string(out), 400))
	if err != nil {
		return failAndRestore(req, logger, "نصب‌کننده با خطا تمام شد: "+err.Error())
	}
	installedVersion := versionFromFile(req.InstallDir)
	if installedVersion == "" || !strings.EqualFold(installedVersion, req.NewVersion) {
		return failAndRestore(req, logger,
			fmt.Sprintf("پس از نصب، Version.txt نسخهٔ %q را نشان می‌دهد نه %q", installedVersion, req.NewVersion))
	}

	proc, err := launchApp(req, logger)
	if err != nil {
		return failAndRestore(req, logger, "اجرای نسخهٔ تازه ناموفق: "+err.Error())
	}
	if err := waitHealthy(req.Port, req.NewVersion, healthTimeout(120*time.Second)); err != nil {
		stopProcess(proc)
		time.Sleep(2 * time.Second)
		return failAndRestore(req, logger, "نسخهٔ تازه سالم بالا نیامد: "+err.Error())
	}
	writeLastUpdate(req.DataDir, LastUpdate{Status: "applied", From: req.OldVersion, To: req.NewVersion,
		At: time.Now().UTC().Format(time.RFC3339), Message: "به‌روزرسانی با موفقیت اعمال شد"})
	logger.Info("update applied", "version", req.NewVersion)
	return nil
}

func runRollback(req watchRequest, logger *slog.Logger) error {
	if err := restoreBackup(req.InstallDir, req.BackupDir); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.NewVersion, To: req.OldVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: "بازگشت ناموفق: " + err.Error()})
		return err
	}
	if _, err := launchApp(req, logger); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.NewVersion, To: req.OldVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: "اجرای نسخهٔ قبلی ناموفق: " + err.Error()})
		return err
	}
	if err := waitHealthy(req.Port, req.OldVersion, healthTimeout(90*time.Second)); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.NewVersion, To: req.OldVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: "نسخهٔ قبلی سالم بالا نیامد: " + err.Error()})
		return err
	}
	removeBackup(req.DataDir)
	writeLastUpdate(req.DataDir, LastUpdate{Status: "rolled_back", From: req.NewVersion, To: req.OldVersion,
		At: time.Now().UTC().Format(time.RFC3339), Message: "به نسخهٔ قبلی بازگشت"})
	logger.Info("rollback applied", "version", req.OldVersion)
	return nil
}

// failAndRestore is the automatic rollback after a failed update: restore the
// program files, start the previous version, and record the outcome.
func failAndRestore(req watchRequest, logger *slog.Logger, reason string) error {
	logger.Error("update failed; rolling back", "reason", reason)
	if err := restoreBackup(req.InstallDir, req.BackupDir); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.OldVersion, To: req.NewVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: reason + "؛ بازگشت هم ناموفق: " + err.Error()})
		return fmt.Errorf("%s; rollback failed: %w", reason, err)
	}
	if _, err := launchApp(req, logger); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.OldVersion, To: req.NewVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: reason + "؛ اجرای نسخهٔ قبلی ناموفق: " + err.Error()})
		return err
	}
	if err := waitHealthy(req.Port, req.OldVersion, healthTimeout(90*time.Second)); err != nil {
		writeLastUpdate(req.DataDir, LastUpdate{Status: "rollback_failed", From: req.OldVersion, To: req.NewVersion,
			At: time.Now().UTC().Format(time.RFC3339), Message: reason + "؛ نسخهٔ قبلی سالم بالا نیامد"})
		return err
	}
	removeBackup(req.DataDir)
	writeLastUpdate(req.DataDir, LastUpdate{Status: "rolled_back", From: req.NewVersion, To: req.OldVersion,
		At: time.Now().UTC().Format(time.RFC3339), Message: reason + "؛ نسخهٔ قبلی بازگردانده شد"})
	logger.Info("rolled back after failure", "version", req.OldVersion)
	return fmt.Errorf("%s (rolled back)", reason)
}

func launchApp(req watchRequest, logger *slog.Logger) (*exec.Cmd, error) {
	exe := filepath.Join(req.InstallDir, "BorsTerminal_Ultimate.exe")
	if _, err := os.Stat(exe); err != nil {
		return nil, err
	}
	args := make([]string, 0, len(req.RelaunchArgs))
	for _, a := range req.RelaunchArgs {
		if a == "--update-watch" {
			continue
		}
		args = append(args, a)
	}
	cmd := exec.Command(exe, args...)
	cmd.Dir = req.InstallDir
	detachProcess(cmd)
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	logger.Info("app started", "pid", cmd.Process.Pid, "exe", exe)
	return cmd, nil
}

func stopProcess(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	_ = cmd.Process.Kill()
	_, _ = cmd.Process.Wait()
}

var healthHTTP = &http.Client{
	Timeout:   3 * time.Second,
	Transport: &http.Transport{Proxy: nil},
}

// waitHealthy polls /healthz (the only unauthenticated endpoint) until the
// new process reports status ok and the expected version.
func waitHealthy(port int, wantVersion string, timeout time.Duration) error {
	if port <= 0 {
		return errors.New("پورتِ سرویس برای بررسیِ سلامت معلوم نیست")
	}
	url := fmt.Sprintf("http://127.0.0.1:%d/healthz", port)
	deadline := time.Now().Add(timeout)
	var last string
	for time.Now().Before(deadline) {
		body, err := healthGet(url)
		if err == nil {
			var health struct {
				Status  string `json:"status"`
				Version string `json:"version"`
			}
			if json.Unmarshal(body, &health) == nil {
				if health.Status == "ok" && (wantVersion == "" || strings.EqualFold(health.Version, wantVersion)) {
					return nil
				}
				last = fmt.Sprintf("status=%s version=%s (expected %s)", health.Status, health.Version, wantVersion)
			} else {
				last = "پاسخِ سلامت خوانا نیست"
			}
		} else {
			last = err.Error()
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("بررسیِ سلامت در %s ناموفق ماند (آخرین وضعیت: %s)", timeout, last)
}

func healthGet(url string) ([]byte, error) {
	resp, err := healthHTTP.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	return io.ReadAll(io.LimitReader(resp.Body, 64<<10))
}

// healthTimeout is 120s in production; the isolated test channel shortens it
// so a deliberately broken build rolls back without a long stall.
func healthTimeout(def time.Duration) time.Duration {
	if ms, err := strconv.Atoi(strings.TrimSpace(os.Getenv("BORS_UPDATE_HEALTH_MS"))); err == nil && ms >= 1000 {
		return time.Duration(ms) * time.Millisecond
	}
	return def
}

var setupPasswordRE = regexp.MustCompile(`#define\s+SetupPassword\s+"([^"]*)"`)

// setupPassword mirrors the Python updater: env first, then the gitignored
// password files shipped or placed beside the app. Empty means the installer
// must prompt, so silent upgrade degrades to /SILENT.
func setupPassword(installDir string) string {
	if pw := strings.TrimSpace(os.Getenv("BORS_SETUP_PASSWORD")); pw != "" {
		return pw
	}
	for _, name := range []string{"setup.pw", ".setup_password.iss", "installer/.setup_password.iss", ".setup_password"} {
		raw, err := os.ReadFile(filepath.Join(installDir, filepath.FromSlash(name)))
		if err != nil {
			continue
		}
		text := string(raw)
		if m := setupPasswordRE.FindStringSubmatch(text); len(m) == 2 && m[1] != "" {
			return m[1]
		}
		line := strings.TrimSpace(text)
		if line != "" && !strings.Contains(line, "\n") && !strings.Contains(line, "#") {
			return line
		}
	}
	return ""
}

func installerFlags(installDir, logPath string) []string {
	flags := []string{"/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"}
	if pw := setupPassword(installDir); pw != "" {
		flags = append(flags, "/PASSWORD="+pw)
	} else {
		flags[0] = "/SILENT"
	}
	flags = append(flags, "/DIR="+installDir)
	if underProgramFiles(installDir) {
		flags = append(flags, "/ALLUSERS")
	} else {
		flags = append(flags, "/CURRENTUSER")
	}
	flags = append(flags, "/LOG="+logPath)
	return flags
}

func underProgramFiles(dir string) bool {
	clean := strings.ToLower(filepath.Clean(dir))
	for _, env := range []string{"ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"} {
		root := strings.ToLower(strings.TrimSpace(os.Getenv(env)))
		if root != "" && strings.HasPrefix(clean, root+string(filepath.Separator)) {
			return true
		}
	}
	return false
}

// MaskedInstallerFlags is exported for tests and logs: it never contains the
// installer password.
func MaskedInstallerFlags(installDir string) []string {
	flags := installerFlags(installDir, "<log>")
	out := make([]string, 0, len(flags))
	for _, f := range flags {
		if strings.HasPrefix(f, "/PASSWORD=") {
			out = append(out, "/PASSWORD=<hidden>")
			continue
		}
		out = append(out, f)
	}
	return out
}

func writeLastUpdate(dataDir string, last LastUpdate) {
	path := filepath.Join(dataDir, "update_last.json")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		return
	}
	raw, err := json.MarshalIndent(last, "", "  ")
	if err != nil {
		return
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o644); err != nil {
		return
	}
	_ = os.Rename(tmp, path)
}

func watcherLogger(path string) (*slog.Logger, func()) {
	if path == "" {
		return slog.Default(), func() {}
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return slog.Default(), func() {}
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return slog.Default(), func() {}
	}
	return slog.New(slog.NewTextHandler(f, &slog.HandlerOptions{Level: slog.LevelInfo})), func() { _ = f.Close() }
}

func tail(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[len(s)-n:]
}

func portOf(addr string) int {
	_, portText, err := net.SplitHostPort(addr)
	if err != nil {
		return 0
	}
	port := 0
	for _, r := range portText {
		if r < '0' || r > '9' {
			return 0
		}
		port = port*10 + int(r-'0')
	}
	return port
}
