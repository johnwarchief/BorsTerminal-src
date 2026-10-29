package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/parity"
)

func server(body string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
}

func TestCompareCasePassesOnKeyOrder(t *testing.T) {
	py, gs := server(`{"a":1,"b":"x"}`), server(`{"b":"x","a":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "k", Method: "GET", Path: "/p"})
	if err != nil || !row.Pass {
		t.Fatalf("err=%v row=%+v", err, row)
	}
}

func TestCompareCaseFailsOnValue(t *testing.T) {
	py, gs := server(`{"a":1}`), server(`{"a":2}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "v", Method: "GET", Path: "/p"})
	if err != nil {
		t.Fatal(err)
	}
	if row.Pass || len(row.Diffs) == 0 {
		t.Fatalf("row=%+v", row)
	}
}

func TestCompareCaseExclusion(t *testing.T) {
	py, gs := server(`{"meta":{"t":"a"},"n":1}`), server(`{"meta":{"t":"b"},"n":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{
		Name: "e", Method: "GET", Path: "/p", Exclude: []string{"meta.t"},
	})
	if err != nil || !row.Pass || len(row.Excluded) != 1 {
		t.Fatalf("err=%v row=%+v", err, row)
	}
}

func TestCompareCaseNonJSONIsFailedRow(t *testing.T) {
	py := server(`{"a":1}`)
	gs := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("not json"))
	}))
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "nj", Method: "GET", Path: "/p"})
	if err != nil {
		t.Fatalf("non-JSON body must not abort the run: %v", err)
	}
	if row.Pass || len(row.Diffs) == 0 || !strings.HasPrefix(row.Diffs[0], "go fetch:") {
		t.Fatalf("row=%+v", row)
	}
	if row.StatusGo != 0 || row.StatusPy != 200 {
		t.Fatalf("status_py=%d status_go=%d", row.StatusPy, row.StatusGo)
	}
}

func TestRunZeroCasesWritesNoReport(t *testing.T) {
	dir := t.TempDir()
	cases := filepath.Join(dir, "cases.json")
	if err := os.WriteFile(cases, []byte(`{"cases":[]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "report.json")
	if code := run([]string{"--cases", cases, "--out", out}); code != 2 {
		t.Fatalf("exit = %d, want 2", code)
	}
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		t.Fatalf("report must not be written: %v", err)
	}
}

func TestRunPassingCaseWritesReport(t *testing.T) {
	py, gs := server(`{"a":1}`), server(`{"a":1}`)
	defer py.Close()
	defer gs.Close()
	dir := t.TempDir()
	cases := filepath.Join(dir, "cases.json")
	if err := os.WriteFile(cases, []byte(`{"cases":[{"name":"ok","method":"GET","path":"/p"}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "report.json")
	if code := run([]string{"--py", py.URL, "--go", gs.URL, "--cases", cases, "--out", out}); code != 0 {
		t.Fatalf("exit = %d, want 0", code)
	}
	blob, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	var rep parity.Report
	if err := json.Unmarshal(blob, &rep); err != nil {
		t.Fatal(err)
	}
	if rep.Passed != 1 || rep.Failed != 0 || len(rep.Cases) != 1 || !rep.Cases[0].Pass {
		t.Fatalf("report=%+v", rep)
	}
}
