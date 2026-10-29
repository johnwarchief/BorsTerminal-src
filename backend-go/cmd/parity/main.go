package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
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
	ms     float64
}

func fetch(base string, c testCase) (fetched, error) {
	req, err := http.NewRequest(c.Method, base+c.Path, nil)
	if err != nil {
		return fetched{}, err
	}
	start := time.Now()
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fetched{}, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fetched{}, err
	}
	out := fetched{status: resp.StatusCode, body: body, ms: float64(time.Since(start).Microseconds()) / 1000.0}
	if err := json.Unmarshal(body, &out.value); err != nil {
		return fetched{}, fmt.Errorf("%s: body is not JSON: %w", c.Path, err)
	}
	return out, nil
}

func main() {
	py := flag.String("py", "http://127.0.0.1:8299", "python base URL")
	goURL := flag.String("go", "http://127.0.0.1:8298", "go base URL")
	cases := flag.String("cases", "", "cases JSON")
	out := flag.String("out", "_audit/parity/run.json", "report path")
	commit := flag.String("commit", "unknown", "git commit being measured")
	flag.Parse()
	if *cases == "" {
		fmt.Fprintln(os.Stderr, "--cases is required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*cases)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	var cf caseFile
	if err := json.Unmarshal(raw, &cf); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	report := parity.Report{Commit: *commit, PyURL: *py, GoURL: *goURL, DBHash: cf.DBHash}
	for _, c := range cf.Cases {
		row, err := compareCase(*py, *goURL, c)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if row.Pass {
			report.Passed++
		} else {
			report.Failed++
		}
		report.Cases = append(report.Cases, row)
	}
	report.Finished = time.Now().UTC().Format(time.RFC3339)
	blob, _ := json.MarshalIndent(report, "", " ")
	if err := os.MkdirAll(dirOf(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := os.WriteFile(*out, append(blob, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	fmt.Printf("parity: %d passed / %d failed -> %s\n", report.Passed, report.Failed, *out)
	if report.Failed > 0 {
		os.Exit(1)
	}
}

func compareCase(pyBase, goBase string, c testCase) (parity.CaseReport, error) {
	a, err := fetch(pyBase, c)
	if err != nil {
		return parity.CaseReport{}, fmt.Errorf("py %s: %w", c.Path, err)
	}
	b, err := fetch(goBase, c)
	if err != nil {
		return parity.CaseReport{}, fmt.Errorf("go %s: %w", c.Path, err)
	}
	row := parity.CaseReport{
		Name: c.Name, Method: c.Method, Path: c.Path,
		StatusPy: a.status, StatusGo: b.status,
		BytesPy: len(a.body), BytesGo: len(b.body),
	}
	if a.status != b.status {
		row.Diffs = []string{fmt.Sprintf("status: %d != %d", a.status, b.status)}
		return row, nil
	}
	res := parity.Compare(a.value, b.value, parity.Options{Exclude: c.Exclude})
	row.Pass, row.Diffs, row.MaxDelta, row.Excluded = res.Pass, res.Diffs, res.MaxDelta, res.Excluded
	return row, nil
}

func dirOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' || path[i] == '\\' {
			return path[:i]
		}
	}
	return "."
}
