package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"
)

// The tests are hermetic: instead of the real borsd (which needs market.db and
// a free port for minutes) they re-exec this test binary. The basename of the
// copy picks the helper role, so no environment leaks from `go test` itself:
//
//	helper-healthz.exe  stand-in borsd: records its flags, optionally spawns a
//	                    python-named child and serves GET /healthz
//	helper-exit.exe     exits immediately with status 3
//	RUNTIMECHECK_HELPER=sleep  a sleeping process used as child/unrelated peer
const helperModeEnv = "RUNTIMECHECK_HELPER"

func TestMain(m *testing.M) {
	base := strings.ToLower(filepath.Base(os.Args[0]))
	switch {
	case strings.HasPrefix(base, "helper-exit"):
		os.Exit(3)
	case os.Getenv(helperModeEnv) == "sleep", strings.HasPrefix(base, "helper-sleep"):
		time.Sleep(2 * time.Minute)
		return
	case strings.HasPrefix(base, "helper-healthz"):
		serveFakeBorsd()
		return
	}
	os.Exit(m.Run())
}

// serveFakeBorsd accepts the same flags runtimecheck passes to borsd, records
// what it saw (so a test can prove the throwaway data dir was used), spawns an
// optional banned-name child and serves /healthz until it is killed.
func serveFakeBorsd() {
	fs := flag.NewFlagSet("fakeborsd", flag.ContinueOnError)
	port := fs.Int("port", 0, "")
	dataDir := fs.String("db-dir", "", "")
	noShell := fs.Bool("no-shell", false, "")
	noLoops := fs.Bool("no-loops", false, "")
	if err := fs.Parse(os.Args[1:]); err != nil || *port <= 0 || *dataDir == "" {
		os.Exit(2)
	}
	seen := map[string]any{
		"pid":      os.Getpid(),
		"port":     *port,
		"db_dir":   *dataDir,
		"no_shell": *noShell,
		"no_loops": *noLoops,
	}
	if fi, err := os.Stat(filepath.Join(*dataDir, "market.db")); err == nil {
		seen["market_db"] = true
		seen["market_db_size"] = fi.Size()
	} else {
		seen["market_db"] = false
	}
	if child := os.Getenv("RUNTIMECHECK_HELPER_CHILD"); child != "" {
		c := exec.Command(child)
		c.Env = append(os.Environ(), helperModeEnv+"=sleep")
		c.Stdout, c.Stderr = io.Discard, io.Discard
		if err := c.Start(); err != nil {
			seen["child_error"] = err.Error()
		} else {
			seen["child_pid"] = c.Process.Pid
			go func() { _ = c.Wait() }()
		}
	}
	if path := os.Getenv("RUNTIMECHECK_HELPER_REPORT"); path != "" {
		b, _ := json.Marshal(seen)
		_ = os.WriteFile(path, b, 0o644)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"status":"ok"}`)
	})
	_ = http.ListenAndServe("127.0.0.1:"+strconv.Itoa(*port), mux)
}

func TestBannedName(t *testing.T) {
	for _, n := range []string{"python.exe", "python3", "python3.12.exe",
		"pythonw.exe", "libpython3.12.dll", "uvicorn.exe", "fastapi.exe"} {
		if !bannedName(n) {
			t.Errorf("%s must be banned", n)
		}
	}
	for _, n := range []string{"borsd.exe", "BorsTerminal_Ultimate.exe", "node.exe"} {
		if bannedName(n) {
			t.Errorf("%s must not be banned", n)
		}
	}
}

// TestBannedNameNoFalsePositives pins the "exact basename" requirement: ordinary
// names that merely contain the letters must pass.
func TestBannedNameNoFalsePositives(t *testing.T) {
	for _, n := range []string{"copy.exe", "happy.exe", "application.exe",
		"pypi-proxy.exe", "pyramid.exe", "typescript.exe"} {
		if bannedName(n) {
			t.Errorf("%s must not be banned", n)
		}
	}
}

func TestDescendants(t *testing.T) {
	all := []proc{{PID: 1, Parent: 0, Name: "root"}, {PID: 2, Parent: 1, Name: "a"},
		{PID: 3, Parent: 2, Name: "python.exe"}, {PID: 4, Parent: 1, Name: "b"}}
	d := descendants(1, all)
	if len(d) != 3 {
		t.Fatalf("descendants = %d, want 3", len(d))
	}
	found := false
	for _, p := range d {
		if p.Name == "python.exe" {
			found = true
		}
	}
	if !found {
		t.Fatalf("python descendant missing: %+v", d)
	}
}

func TestSameImage(t *testing.T) {
	cases := []struct {
		name string
		exe  string
		want bool
	}{
		{"borsd.exe", "borsd.exe", true},
		{"BORSD.EXE", "/app/borsd.exe", true},
		{"borsd", "/opt/app/borsd", true},
		// Linux truncates /proc/<pid>/stat comm to 15 bytes.
		{"helper-healthz.", "helper-healthz.exe", true},
		{"helper-healthz.exe", "helper-healthz.exe", true},
		{"borsd.exe", "other.exe", false},
		{"", "borsd.exe", false},
	}
	for _, c := range cases {
		if got := sameImage(c.name, c.exe); got != c.want {
			t.Errorf("sameImage(%q, %q) = %v, want %v", c.name, c.exe, got, c.want)
		}
	}
}

// TestRunReportsCleanTree drives the whole command against the fake borsd: the
// throwaway data dir, the health probe, the process tree and the report shape.
func TestRunReportsCleanTree(t *testing.T) {
	dir := t.TempDir()
	helper := copyHelper(t, dir, "helper-healthz.exe")
	src := filepath.Join(dir, "src")
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}
	payload := []byte("fake-market-db")
	if err := os.WriteFile(filepath.Join(src, "market.db"), payload, 0o644); err != nil {
		t.Fatal(err)
	}
	seenPath := filepath.Join(dir, "seen.json")
	t.Setenv("RUNTIMECHECK_HELPER_REPORT", seenPath)
	outPath := filepath.Join(dir, "report.json")

	var stdout, stderr bytes.Buffer
	code := run([]string{"--borsd", helper, "--data-dir", src,
		"--port", strconv.Itoa(freePort(t)), "--timeout", "20s", "--out", outPath},
		&stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit = %d, want 0\nstdout: %s\nstderr: %s", code, stdout.String(), stderr.String())
	}

	rep := decodeReport(t, stdout.Bytes())
	if !rep.OK {
		t.Fatalf("ok = false, want true (%+v)", rep)
	}
	if rep.Health != "ok" {
		t.Fatalf("health = %q, want ok", rep.Health)
	}
	if rep.PID <= 0 {
		t.Fatalf("pid = %d, want the borsd child pid", rep.PID)
	}
	if len(rep.Processes) == 0 {
		t.Fatalf("processes is empty")
	}
	if !sameImage(rep.Processes[0].Name, helper) {
		t.Fatalf("first process = %q, want the started borsd %q", rep.Processes[0].Name, helper)
	}
	if len(rep.PythonProcesses) != 0 {
		t.Fatalf("python_processes = %+v, want none", rep.PythonProcesses)
	}

	// The keys the controllers depend on must always be present, and
	// python_processes must serialise as [] (not null).
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(stdout.Bytes(), &raw); err != nil {
		t.Fatalf("report is not JSON: %v", err)
	}
	for _, key := range []string{"ok", "pid", "health", "processes", "python_processes", "duration_ms"} {
		if _, ok := raw[key]; !ok {
			t.Fatalf("report is missing %q: %s", key, stdout.String())
		}
	}
	if got := strings.TrimSpace(string(raw["python_processes"])); got != "[]" {
		t.Fatalf("python_processes = %s, want []", got)
	}

	written, err := os.ReadFile(outPath)
	if err != nil {
		t.Fatalf("report file: %v", err)
	}
	if !bytes.Equal(written, stdout.Bytes()) {
		t.Fatalf("report file differs from stdout")
	}

	// borsd must have received a throwaway copy of market.db, never the source.
	var seen struct {
		PID          int    `json:"pid"`
		Port         int    `json:"port"`
		DBDir        string `json:"db_dir"`
		NoShell      bool   `json:"no_shell"`
		NoLoops      bool   `json:"no_loops"`
		MarketDB     bool   `json:"market_db"`
		MarketDBSize int64  `json:"market_db_size"`
	}
	if err := json.Unmarshal(mustReadFile(t, seenPath), &seen); err != nil {
		t.Fatalf("helper report: %v", err)
	}
	if seen.PID != rep.PID {
		t.Fatalf("helper pid = %d, report pid = %d", seen.PID, rep.PID)
	}
	if !seen.MarketDB || seen.MarketDBSize != int64(len(payload)) {
		t.Fatalf("helper saw market_db=%v size=%d, want true/%d", seen.MarketDB, seen.MarketDBSize, len(payload))
	}
	if samePath(seen.DBDir, src) {
		t.Fatalf("borsd ran against the source data dir %s", src)
	}
	if !seen.NoShell || !seen.NoLoops {
		t.Fatalf("headless flags missing: no_shell=%v no_loops=%v", seen.NoShell, seen.NoLoops)
	}

	waitGone(t, rep.PID, 15*time.Second)
}

// TestRunDetectsPythonChild plants a python-named process below the fake borsd
// and checks that the command fails, names it, and kills only that tree.
func TestRunDetectsPythonChild(t *testing.T) {
	dir := t.TempDir()
	helper := copyHelper(t, dir, "helper-healthz.exe")
	py := copyHelper(t, dir, "python3.exe")
	unrelated := startSleepHelper(t, copyHelper(t, dir, "keepalive.exe"))
	src := filepath.Join(dir, "src")
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(src, "market.db"), []byte("db"), 0o644); err != nil {
		t.Fatal(err)
	}
	seenPath := filepath.Join(dir, "seen.json")
	t.Setenv("RUNTIMECHECK_HELPER_REPORT", seenPath)
	t.Setenv("RUNTIMECHECK_HELPER_CHILD", py)

	var stdout, stderr bytes.Buffer
	code := run([]string{"--borsd", helper, "--data-dir", src,
		"--port", strconv.Itoa(freePort(t)), "--timeout", "20s"}, &stdout, &stderr)
	if code == 0 {
		t.Fatalf("exit = 0, want a violation\nstdout: %s", stdout.String())
	}

	rep := decodeReport(t, stdout.Bytes())
	if rep.OK {
		t.Fatalf("ok = true, want false")
	}
	if len(rep.PythonProcesses) != 1 {
		t.Fatalf("python_processes = %+v, want exactly the planted child", rep.PythonProcesses)
	}
	planted := rep.PythonProcesses[0]
	if !strings.EqualFold(filepath.Base(planted.Name), "python3.exe") {
		t.Fatalf("banned process = %q, want python3.exe", planted.Name)
	}
	if !containsPID(rep.Processes, planted.PID) {
		t.Fatalf("processes does not list the banned pid %d: %+v", planted.PID, rep.Processes)
	}

	var seen struct {
		PID      int `json:"pid"`
		ChildPID int `json:"child_pid"`
	}
	if err := json.Unmarshal(mustReadFile(t, seenPath), &seen); err != nil {
		t.Fatalf("helper report: %v", err)
	}
	if seen.ChildPID != planted.PID {
		t.Fatalf("planted pid = %d, report names %d", seen.ChildPID, planted.PID)
	}

	// The command must clean up the tree it started ...
	waitGone(t, rep.PID, 15*time.Second)
	waitGone(t, planted.PID, 15*time.Second)
	// ... and never touch a process outside that tree.
	if !processAlive(unrelated) {
		t.Fatalf("unrelated pid %d was killed", unrelated)
	}
}

// TestRunReportsEarlyExit proves a borsd that dies at startup is reported
// immediately instead of being waited out to the health timeout.
func TestRunReportsEarlyExit(t *testing.T) {
	dir := t.TempDir()
	exe := copyHelper(t, dir, "helper-exit.exe")
	src := filepath.Join(dir, "src")
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	started := time.Now()
	code := run([]string{"--borsd", exe, "--data-dir", src,
		"--port", strconv.Itoa(freePort(t)), "--timeout", "60s"}, &stdout, &stderr)
	elapsed := time.Since(started)
	if code == 0 {
		t.Fatalf("exit = 0, want failure\nstdout: %s", stdout.String())
	}
	if elapsed > 20*time.Second {
		t.Fatalf("took %s; an early exit must short-circuit the health timeout", elapsed)
	}
	rep := decodeReport(t, stdout.Bytes())
	if rep.OK {
		t.Fatalf("ok = true, want false")
	}
	if !strings.Contains(strings.ToLower(rep.Error), "exited") {
		t.Fatalf("error = %q, want an early-exit message", rep.Error)
	}
	if rep.Health != "" {
		t.Fatalf("health = %q, want empty", rep.Health)
	}
}

// TestRunTimesOutAndKillsChild covers the health-timeout branch: borsd never
// answers, the command fails fast and still tears its child down.
func TestRunTimesOutAndKillsChild(t *testing.T) {
	dir := t.TempDir()
	exe := copyHelper(t, dir, "helper-sleep.exe")
	src := filepath.Join(dir, "src")
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	started := time.Now()
	code := run([]string{"--borsd", exe, "--data-dir", src,
		"--port", strconv.Itoa(freePort(t)), "--timeout", "1500ms"}, &stdout, &stderr)
	if code == 0 {
		t.Fatalf("exit = 0, want a timeout failure\nstdout: %s", stdout.String())
	}
	if elapsed := time.Since(started); elapsed > 20*time.Second {
		t.Fatalf("took %s for a 1.5s timeout", elapsed)
	}
	rep := decodeReport(t, stdout.Bytes())
	if rep.OK {
		t.Fatalf("ok = true, want false")
	}
	if !strings.Contains(rep.Error, "did not return 200") {
		t.Fatalf("error = %q, want a health-timeout message", rep.Error)
	}
	if rep.PID <= 0 {
		t.Fatalf("pid = %d, the started child must always be reported", rep.PID)
	}
	waitGone(t, rep.PID, 15*time.Second)
}

// TestStopTreeRefusesMismatchedImage pins the kill-safety rule: a PID whose
// image does not match the one we started is never terminated.
func TestStopTreeRefusesMismatchedImage(t *testing.T) {
	dir := t.TempDir()
	helper := copyHelper(t, dir, "keepalive.exe")
	pid := startSleepHelper(t, helper)

	if stopTree(pid, filepath.Join(dir, "not-our-child.exe")) {
		t.Fatalf("stopTree killed a PID whose image does not match")
	}
	if !processAlive(pid) {
		t.Fatalf("pid %d must still be alive", pid)
	}
	if !stopTree(pid, helper) {
		t.Fatalf("stopTree refused the verified child")
	}
	waitGone(t, pid, 15*time.Second)
}

// TestProcessTreeFindsBannedDescendant is the hermetic enumeration test: a
// python-named copy of this binary becomes a real descendant of the test
// process and must be found by processTree + descendants + bannedName.
func TestProcessTreeFindsBannedDescendant(t *testing.T) {
	dir := t.TempDir()
	py := copyHelper(t, dir, "python3.exe")
	pid := startSleepHelper(t, py)

	var found proc
	deadline := time.Now().Add(15 * time.Second)
	for time.Now().Before(deadline) {
		all, err := processTree()
		if err != nil {
			t.Fatalf("processTree: %v", err)
		}
		for _, p := range descendants(os.Getpid(), all) {
			if p.PID == pid {
				found = p
				break
			}
		}
		if found.PID != 0 {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if found.PID == 0 {
		t.Fatalf("python-named child %d not found in the descendant tree", pid)
	}
	if !bannedName(found.Name) {
		t.Fatalf("bannedName(%q) = false for the planted child", found.Name)
	}
	if found.Parent != os.Getpid() {
		t.Fatalf("parent = %d, want %d", found.Parent, os.Getpid())
	}
}

func TestWindowsProcessNames(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("windows-only process-name check")
	}
	all, err := processTree()
	if err != nil {
		t.Fatalf("processTree: %v", err)
	}
	self, ok := findProc(all, os.Getpid())
	if !ok {
		t.Fatalf("processTree does not list pid %d", os.Getpid())
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	if !sameImage(self.Name, exe) {
		t.Fatalf("Toolhelp name %q does not match %q", self.Name, exe)
	}
}

func TestLinuxProcFS(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("linux-only /proc check")
	}
	all, err := processTree()
	if err != nil {
		t.Fatalf("processTree: %v", err)
	}
	self, ok := findProc(all, os.Getpid())
	if !ok {
		t.Fatalf("processTree does not list pid %d", os.Getpid())
	}
	if self.Name == "" {
		t.Fatalf("empty comm for pid %d", os.Getpid())
	}
	if self.Parent != os.Getppid() {
		t.Fatalf("ppid = %d, want %d", self.Parent, os.Getppid())
	}
}

// --- helpers ---------------------------------------------------------------

func copyHelper(t *testing.T, dir, name string) string {
	t.Helper()
	self, err := os.Executable()
	if err != nil {
		t.Fatalf("os.Executable: %v", err)
	}
	dst := filepath.Join(dir, name)
	if err := copyFile(self, dst); err != nil {
		t.Fatalf("copy helper %s: %v", name, err)
	}
	if runtime.GOOS != "windows" {
		if err := os.Chmod(dst, 0o755); err != nil {
			t.Fatalf("chmod helper: %v", err)
		}
	}
	return dst
}

func startSleepHelper(t *testing.T, exe string) int {
	t.Helper()
	cmd := exec.Command(exe)
	cmd.Env = append(os.Environ(), helperModeEnv+"=sleep")
	cmd.Stdout, cmd.Stderr = io.Discard, io.Discard
	if err := cmd.Start(); err != nil {
		t.Fatalf("start helper %s: %v", exe, err)
	}
	t.Cleanup(func() {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	})
	return cmd.Process.Pid
}

func freePort(t *testing.T) int {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("pick port: %v", err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	if err := ln.Close(); err != nil {
		t.Fatalf("release port: %v", err)
	}
	return port
}

func decodeReport(t *testing.T, b []byte) report {
	t.Helper()
	var rep report
	if err := json.Unmarshal(b, &rep); err != nil {
		t.Fatalf("decode report: %v\n%s", err, b)
	}
	return rep
}

func mustReadFile(t *testing.T, path string) []byte {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return b
}

func samePath(a, b string) bool {
	a, b = filepath.Clean(a), filepath.Clean(b)
	if runtime.GOOS == "windows" {
		return strings.EqualFold(a, b)
	}
	return a == b
}

func containsPID(procs []proc, pid int) bool {
	for _, p := range procs {
		if p.PID == pid {
			return true
		}
	}
	return false
}

// processAlive uses the same enumeration as the command. A killed orphan can
// linger as a zombie in /proc until PID 1 reaps it, so zombies count as gone.
func processAlive(pid int) bool {
	all, err := processTree()
	if err != nil {
		return false
	}
	for _, p := range all {
		if p.PID != pid {
			continue
		}
		if runtime.GOOS == "linux" && linuxZombie(pid) {
			return false
		}
		return true
	}
	return false
}

func linuxZombie(pid int) bool {
	if runtime.GOOS != "linux" {
		return false
	}
	b, err := os.ReadFile(filepath.Join("/proc", strconv.Itoa(pid), "stat"))
	if err != nil {
		return false
	}
	s := string(b)
	i := strings.LastIndex(s, ")")
	if i < 0 || i+2 >= len(s) {
		return false
	}
	return s[i+2] == 'Z'
}

func waitGone(t *testing.T, pid int, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if !processAlive(pid) {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("pid %d is still alive after %s", pid, timeout)
}
