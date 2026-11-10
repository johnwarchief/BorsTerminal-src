// Command runtimecheck proves a borsd process tree contains no Python runtime.
//
// It starts the given borsd executable against a throwaway copy of the caller's
// data dir, waits for GET /healthz, enumerates every descendant process and
// fails when any of them is a Python/Uvicorn/FastAPI image. The command only
// ever terminates the tree it started: the child PID is re-verified (parent and
// image name) before the kill, so a recycled PID is never signalled.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	healthPollInterval = 200 * time.Millisecond
	healthRequestLimit = 2 * time.Second
	childStopTimeout   = 10 * time.Second
	childOutputLimit   = 4 << 10
)

// proc is one row of the OS process table. Parent is the ppid that the
// platform enumerator reports (Toolhelp on Windows, /proc/<pid>/stat on Linux).
type proc struct {
	PID    int    `json:"pid"`
	Parent int    `json:"ppid"`
	Name   string `json:"name"`
}

// report is the JSON artifact CI uploads. ok/pid/health/processes/
// python_processes/duration_ms are the contract; the rest is diagnostics.
type report struct {
	Borsd           string `json:"borsd"`
	SourceDataDir   string `json:"source_data_dir"`
	DataDir         string `json:"data_dir"`
	Port            int    `json:"port"`
	PID             int    `json:"pid"`
	Health          string `json:"health"`
	MarketDB        bool   `json:"market_db"`
	Processes       []proc `json:"processes"`
	PythonProcesses []proc `json:"python_processes"`
	OK              bool   `json:"ok"`
	Error           string `json:"error,omitempty"`
	ChildOutput     string `json:"child_output,omitempty"`
	DurationMS      int64  `json:"duration_ms"`
}

// bannedName reports whether an executable name is a Python runtime, its
// launcher, or one of the Python-only frameworks. The check is against the
// exact basename (extension stripped), never a raw substring, so ordinary
// names such as "copy.exe" or "application.exe" stay allowed while every
// python*/libpython*/uvicorn*/fastapi* image is rejected.
func bannedName(name string) bool {
	b := strings.ToLower(filepath.Base(name))
	b = strings.TrimSuffix(b, ".exe")
	b = strings.TrimSuffix(b, ".dll")
	switch b {
	case "python", "python3", "pythonw", "py", "uvicorn", "fastapi":
		return true
	}
	return strings.HasPrefix(b, "python") || strings.HasPrefix(b, "libpython") ||
		strings.HasPrefix(b, "uvicorn") || strings.HasPrefix(b, "fastapi")
}

// descendants returns every process below root (breadth first, cycle safe).
func descendants(root int, all []proc) []proc {
	byParent := map[int][]proc{}
	for _, p := range all {
		byParent[p.Parent] = append(byParent[p.Parent], p)
	}
	out := []proc{}
	queue := []int{root}
	seen := map[int]bool{root: true}
	for len(queue) > 0 {
		pid := queue[0]
		queue = queue[1:]
		for _, c := range byParent[pid] {
			if seen[c.PID] {
				continue
			}
			seen[c.PID] = true
			out = append(out, c)
			queue = append(queue, c.PID)
		}
	}
	return out
}

// sameImage reports whether a process-table name identifies the executable at
// exePath. Linux derives /proc/<pid>/stat comm from the executable basename
// truncated to 15 bytes (extension included), hence the prefix comparison.
func sameImage(name, exePath string) bool {
	a := strings.ToLower(filepath.Base(name))
	b := strings.ToLower(filepath.Base(exePath))
	if a == "" || b == "" {
		return false
	}
	if a == b {
		return true
	}
	if len(a) == 15 && strings.HasPrefix(b, a) {
		return true
	}
	if len(b) == 15 && strings.HasPrefix(a, b) {
		return true
	}
	return false
}

func findProc(all []proc, pid int) (proc, bool) {
	for _, p := range all {
		if p.PID == pid {
			return p, true
		}
	}
	return proc{}, false
}

// stopTree terminates exactly the tree rooted at pid, and only after proving
// that pid is still the process we started: same parent and a matching image
// name. If the proof fails nothing is signalled.
func stopTree(pid int, wantExe string) bool {
	all, err := processTree()
	if err != nil {
		return false
	}
	p, ok := findProc(all, pid)
	if !ok || p.Parent != os.Getpid() || !sameImage(p.Name, wantExe) {
		return false
	}
	killTree(pid)
	return true
}

type healthResult struct {
	Health string
	Err    error
	Exited bool
}

// awaitHealth polls GET /healthz until it returns 200, the child exits, or the
// timeout expires. An early exit is reported at once instead of waiting out
// the whole timeout.
func awaitHealth(port int, timeout time.Duration, exitCh <-chan error) healthResult {
	deadline := time.Now().Add(timeout)
	url := fmt.Sprintf("http://127.0.0.1:%d/healthz", port)
	client := &http.Client{Timeout: healthRequestLimit}
	var last error
	for {
		select {
		case err := <-exitCh:
			return healthResult{
				Err:    fmt.Errorf("borsd exited before /healthz was ready: %s", exitText(err)),
				Exited: true,
			}
		default:
		}
		if !time.Now().Before(deadline) {
			break
		}
		resp, err := client.Get(url)
		if err == nil {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return healthResult{Health: "ok"}
			}
			last = fmt.Errorf("/healthz returned %d", resp.StatusCode)
		} else {
			last = err
		}
		time.Sleep(healthPollInterval)
	}
	if last == nil {
		last = errors.New("no response")
	}
	return healthResult{Err: fmt.Errorf("/healthz did not return 200 within %s: %w", timeout, last)}
}

func exitText(err error) string {
	if err == nil {
		return "exit status 0"
	}
	return err.Error()
}

// prepareDataDir makes a throwaway data dir and copies market.db (+ its WAL
// sidecars) into it, so the started borsd can neither write to nor lock the
// caller's data directory. A missing market.db is not fatal: borsd then starts
// with the databases it can create, exactly as on a fresh install.
func prepareDataDir(src string) (dir string, marketDB bool, err error) {
	abs, err := filepath.Abs(src)
	if err != nil {
		return "", false, err
	}
	if fi, statErr := os.Stat(abs); statErr != nil || !fi.IsDir() {
		return "", false, fmt.Errorf("data dir %s is not a directory", src)
	}
	dir, err = os.MkdirTemp("", "borsd-runtimecheck-")
	if err != nil {
		return "", false, err
	}
	for _, name := range []string{"market.db", "market.db-wal", "market.db-shm"} {
		srcPath := filepath.Join(abs, name)
		if _, statErr := os.Stat(srcPath); statErr != nil {
			continue
		}
		if err := copyFile(srcPath, filepath.Join(dir, name)); err != nil {
			_ = os.RemoveAll(dir)
			return "", false, err
		}
		if name == "market.db" {
			marketDB = true
		}
	}
	return dir, marketDB, nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		_ = out.Close()
		return err
	}
	return out.Close()
}

func readTail(path string, limit int64) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	fi, err := f.Stat()
	if err != nil {
		return ""
	}
	off := int64(0)
	if fi.Size() > limit {
		off = fi.Size() - limit
	}
	if _, err := f.Seek(off, io.SeekStart); err != nil {
		return ""
	}
	b, err := io.ReadAll(f)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(b))
}

type cliOptions struct {
	borsd   string
	dataDir string
	out     string
	port    int
	timeout time.Duration
}

func parseArgs(args []string, stderr io.Writer) (cliOptions, error) {
	var o cliOptions
	fs := flag.NewFlagSet("runtimecheck", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.StringVar(&o.borsd, "borsd", "", "path to the borsd executable to launch")
	fs.StringVar(&o.dataDir, "data-dir", "", "directory whose market.db is copied into a throwaway data dir")
	fs.IntVar(&o.port, "port", 18081, "loopback port to launch borsd on")
	fs.DurationVar(&o.timeout, "timeout", 45*time.Second, "how long to wait for /healthz")
	fs.StringVar(&o.out, "out", "", "write the JSON report to this path")
	if err := fs.Parse(args); err != nil {
		return o, err
	}
	if fs.NArg() > 0 {
		return o, fmt.Errorf("unexpected arguments: %s", strings.Join(fs.Args(), " "))
	}
	if o.borsd == "" || o.dataDir == "" {
		return o, errors.New("--borsd and --data-dir are required")
	}
	abs, err := filepath.Abs(o.borsd)
	if err != nil {
		return o, fmt.Errorf("resolve --borsd: %w", err)
	}
	if fi, err := os.Stat(abs); err != nil || fi.IsDir() {
		return o, fmt.Errorf("--borsd %s is not a file", o.borsd)
	}
	o.borsd = abs
	if o.port <= 0 || o.port > 65535 {
		return o, fmt.Errorf("--port %d is out of range", o.port)
	}
	if o.timeout <= 0 {
		return o, fmt.Errorf("--timeout %s must be positive", o.timeout)
	}
	return o, nil
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	started := time.Now()
	rep := report{Processes: []proc{}, PythonProcesses: []proc{}}
	opts, err := parseArgs(args, stderr)
	rep.SourceDataDir = opts.dataDir
	rep.Port = opts.port
	if err != nil {
		rep.Error = err.Error()
		return finish(rep, started, opts.out, stdout, stderr, 2)
	}
	rep.Borsd = opts.borsd
	if abs, err := filepath.Abs(opts.dataDir); err == nil {
		rep.SourceDataDir = abs
	}
	code := runCheck(opts, &rep)
	return finish(rep, started, opts.out, stdout, stderr, code)
}

func finish(rep report, started time.Time, out string, stdout, stderr io.Writer, code int) int {
	rep.DurationMS = time.Since(started).Milliseconds()
	if err := writeReport(rep, out, stdout); err != nil {
		fmt.Fprintln(stderr, "runtimecheck:", err)
		if code == 0 {
			code = 1
		}
	}
	if code != 0 && rep.Error != "" {
		fmt.Fprintln(stderr, "runtimecheck:", rep.Error)
	}
	return code
}

func runCheck(opts cliOptions, rep *report) int {
	dataDir, marketDB, err := prepareDataDir(opts.dataDir)
	if err != nil {
		rep.Error = err.Error()
		return 1
	}
	rep.DataDir = dataDir
	rep.MarketDB = marketDB
	defer os.RemoveAll(dataDir)

	// --no-shell keeps the proof headless and deterministic (the desktop shell
	// is a separate artefact); --no-loops keeps CI off the network. Neither
	// changes which binary or process tree is being proven.
	cmd := exec.Command(opts.borsd, "--db-dir", dataDir, "--port", strconv.Itoa(opts.port), "--no-shell", "--no-loops")
	cmd.Env = append(os.Environ(), "BORS_DATA_DIR="+dataDir)
	logPath := filepath.Join(dataDir, "runtimecheck-child.log")
	if logFile, logErr := os.Create(logPath); logErr == nil {
		cmd.Stdout, cmd.Stderr = logFile, logFile
		defer logFile.Close()
	}
	setProcGroup(cmd)
	if err := cmd.Start(); err != nil {
		rep.Error = "start borsd: " + err.Error()
		rep.ChildOutput = readTail(logPath, childOutputLimit)
		return 1
	}
	rep.PID = cmd.Process.Pid
	exited := false
	exitCh := make(chan error, 1)
	go func() { exitCh <- cmd.Wait() }()
	defer func() {
		if exited {
			return
		}
		stopTree(cmd.Process.Pid, opts.borsd)
		select {
		case <-exitCh:
		case <-time.After(childStopTimeout):
		}
	}()

	res := awaitHealth(opts.port, opts.timeout, exitCh)
	if res.Exited {
		exited = true
	}
	if res.Err != nil {
		rep.Error = res.Err.Error()
		rep.ChildOutput = readTail(logPath, childOutputLimit)
		return 1
	}
	rep.Health = res.Health

	all, err := processTree()
	if err != nil {
		rep.Error = "enumerate processes: " + err.Error()
		rep.ChildOutput = readTail(logPath, childOutputLimit)
		return 1
	}
	root, ok := findProc(all, cmd.Process.Pid)
	if !ok {
		rep.Error = "borsd exited before the process tree could be read"
		rep.ChildOutput = readTail(logPath, childOutputLimit)
		return 1
	}
	rep.Processes = append([]proc{root}, descendants(cmd.Process.Pid, all)...)
	for _, p := range rep.Processes {
		if bannedName(p.Name) {
			rep.PythonProcesses = append(rep.PythonProcesses, p)
		}
	}
	rep.OK = len(rep.PythonProcesses) == 0
	if !rep.OK {
		rep.Error = fmt.Sprintf("%d banned process(es) in the borsd tree", len(rep.PythonProcesses))
		return 1
	}
	return 0
}

func writeReport(r report, path string, stdout io.Writer) error {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	_, _ = stdout.Write(b)
	if path == "" {
		return nil
	}
	if dir := filepath.Dir(path); dir != "" && dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	return os.WriteFile(path, b, 0o644)
}
