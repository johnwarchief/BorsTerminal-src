package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"borsterminal/backend/internal/parity"
)

type testCase struct {
	Name    string   `json:"name"`
	Method  string   `json:"method"`
	Path    string   `json:"path"`
	Exclude []string `json:"exclude"`
}

type caseFile struct {
	DBHash string     `json:"db_sha256"`
	Cases  []testCase `json:"cases"`
}

type fetched struct {
	status int
	body   []byte
	value  any
}

// requestBuildError marks a case whose request could not even be constructed
// (bad base URL or method): a programmer error, not a parity failure.
type requestBuildError struct{ err error }

func (e *requestBuildError) Error() string { return e.err.Error() }
func (e *requestBuildError) Unwrap() error { return e.err }

var httpClient = &http.Client{Timeout: 60 * time.Second}

func fetch(base string, c testCase) (fetched, error) {
	req, err := http.NewRequest(c.Method, base+c.Path, nil)
	if err != nil {
		return fetched{}, &requestBuildError{err: err}
	}
	resp, err := httpClient.Do(req)
	if err != nil {
		return fetched{}, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fetched{}, err
	}
	out := fetched{status: resp.StatusCode, body: body}
	if err := json.Unmarshal(body, &out.value); err != nil {
		return fetched{}, fmt.Errorf("%s: body is not JSON: %w", c.Path, err)
	}
	return out, nil
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("parity", flag.ContinueOnError)
	py := fs.String("py", "http://127.0.0.1:8299", "python base URL")
	goURL := fs.String("go", "http://127.0.0.1:8298", "go base URL")
	cases := fs.String("cases", "", "cases JSON")
	out := fs.String("out", "_audit/parity/run.json", "report path")
	commit := fs.String("commit", "unknown", "git commit being measured")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *cases == "" {
		fmt.Fprintln(os.Stderr, "--cases is required")
		return 2
	}
	raw, err := os.ReadFile(*cases)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	var cf caseFile
	if err := json.Unmarshal(raw, &cf); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if len(cf.Cases) == 0 {
		fmt.Fprintf(os.Stderr, "no cases in %s\n", *cases)
		return 2
	}
	report := parity.Report{Commit: *commit, PyURL: *py, GoURL: *goURL, DBHash: cf.DBHash}
	for _, c := range cf.Cases {
		row, err := compareCase(*py, *goURL, c)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 2
		}
		if row.Pass {
			report.Passed++
		} else {
			report.Failed++
		}
		report.Cases = append(report.Cases, row)
	}
	report.Finished = time.Now().UTC().Format(time.RFC3339)
	blob, err := json.MarshalIndent(report, "", " ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if err := os.WriteFile(*out, append(blob, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	fmt.Printf("parity: %d passed / %d failed -> %s\n", report.Passed, report.Failed, *out)
	if report.Failed > 0 {
		return 1
	}
	return 0
}

func compareCase(pyBase, goBase string, c testCase) (parity.CaseReport, error) {
	row := parity.CaseReport{Name: c.Name, Method: c.Method, Path: c.Path}
	a, err := fetch(pyBase, c)
	if err != nil {
		var build *requestBuildError
		if errors.As(err, &build) {
			return parity.CaseReport{}, fmt.Errorf("py %s: %w", c.Path, err)
		}
		row.Diffs = []string{"py fetch: " + err.Error()}
		return row, nil
	}
	row.StatusPy, row.BytesPy = a.status, len(a.body)
	b, err := fetch(goBase, c)
	if err != nil {
		var build *requestBuildError
		if errors.As(err, &build) {
			return parity.CaseReport{}, fmt.Errorf("go %s: %w", c.Path, err)
		}
		row.Diffs = []string{"go fetch: " + err.Error()}
		return row, nil
	}
	row.StatusGo, row.BytesGo = b.status, len(b.body)
	if a.status != b.status {
		row.Diffs = []string{fmt.Sprintf("status: %d != %d", a.status, b.status)}
		return row, nil
	}
	res := parity.Compare(a.value, b.value, parity.Options{Exclude: c.Exclude})
	row.Pass, row.Diffs, row.MaxDelta, row.Excluded = res.Pass, res.Diffs, res.MaxDelta, res.Excluded
	return row, nil
}
