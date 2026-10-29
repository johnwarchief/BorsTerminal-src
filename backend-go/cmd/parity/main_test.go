package main

import (
	"crypto/sha256"
	"encoding/hex"
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
	return serverCT("application/json", body)
}

func serverCT(contentType, body string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", contentType)
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

func TestCompareCaseContentTypeMismatchFails(t *testing.T) {
	py := serverCT("application/json; charset=utf-8", `{"a":1}`)
	gs := serverCT("text/html; charset=utf-8", `{"a":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "ct", Method: "GET", Path: "/p"})
	if err != nil {
		t.Fatal(err)
	}
	if row.Pass || len(row.Diffs) == 0 || !strings.HasPrefix(row.Diffs[0], "content-type:") {
		t.Fatalf("row=%+v", row)
	}
}

func TestCompareCaseContentTypeCharsetIgnored(t *testing.T) {
	py := serverCT("Application/JSON; charset=utf-8", `{"a":1}`)
	gs := serverCT("application/json", `{"a":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "ct-ok", Method: "GET", Path: "/p"})
	if err != nil || !row.Pass {
		t.Fatalf("err=%v row=%+v", err, row)
	}
}

func writeDB(t *testing.T, dir string) string {
	t.Helper()
	path := filepath.Join(dir, "market.db")
	if err := os.WriteFile(path, []byte("frozen-db-bytes"), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

func shaOf(t *testing.T, path string) string {
	t.Helper()
	blob, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(blob)
	return hex.EncodeToString(sum[:])
}

func TestRunDeclaredHashMismatchExits2(t *testing.T) {
	dir := t.TempDir()
	db := writeDB(t, dir)
	var hits int
	py := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		_, _ = w.Write([]byte(`{"a":1}`))
	}))
	defer py.Close()
	cases := filepath.Join(dir, "cases.json")
	blob := `{"db_sha256":"` + strings.Repeat("0", 64) + `","cases":[{"name":"h","method":"GET","path":"/p"}]}`
	if err := os.WriteFile(cases, []byte(blob), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "report.json")
	code := run([]string{"--py", py.URL, "--go", py.URL, "--cases", cases, "--db", db, "--out", out})
	if code != 2 {
		t.Fatalf("exit = %d, want 2", code)
	}
	if hits != 0 {
		t.Fatalf("no case may run on a hash mismatch, hits=%d", hits)
	}
	if _, err := os.Stat(out); !os.IsNotExist(err) {
		t.Fatalf("report must not be written: %v", err)
	}
}

func TestRunHashDeclaredWithoutDBExits2(t *testing.T) {
	dir := t.TempDir()
	cases := filepath.Join(dir, "cases.json")
	blob := `{"db_sha256":"` + strings.Repeat("a", 64) + `","cases":[{"name":"h","method":"GET","path":"/p"}]}`
	if err := os.WriteFile(cases, []byte(blob), 0o644); err != nil {
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

func TestRunWritesMeasuredHashAndPercentiles(t *testing.T) {
	dir := t.TempDir()
	db := writeDB(t, dir)
	want := shaOf(t, db)
	py, gs := server(`{"a":1}`), server(`{"a":1}`)
	defer py.Close()
	defer gs.Close()
	cases := filepath.Join(dir, "cases.json")
	if err := os.WriteFile(cases, []byte(`{"cases":[{"name":"ok","method":"GET","path":"/p"}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "report.json")
	if code := run([]string{"--py", py.URL, "--go", gs.URL, "--cases", cases, "--db", db, "--out", out}); code != 0 {
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
	if rep.DBHash != want {
		t.Fatalf("db_sha256 = %q, want measured %q", rep.DBHash, want)
	}
	if rep.DBMtimeNS == 0 || rep.DBChanged {
		t.Fatalf("db_mtime_ns=%d db_changed=%v", rep.DBMtimeNS, rep.DBChanged)
	}
	if len(rep.Cases) != 1 {
		t.Fatalf("cases = %d", len(rep.Cases))
	}
	if rep.P50Py < 0 || rep.P95Py < 0 || rep.P50Go < 0 || rep.P95Go < 0 {
		t.Fatalf("percentiles missing: %+v", rep)
	}
	// ساعتِ یکنواختِ ویندوز روی این ماشین درشت‌دانه است و یک درخواستِ سریع
	// می‌تواند صفر بخواند؛ صفر «اندازه‌گیری‌نشده» نیست، پس فقط علامت و بودنِ
	// کلید سنجیده می‌شود (درستیِ nearest-rank در TestPercentileNearestRank).
	if rep.Cases[0].MsPy < 0 || rep.Cases[0].MsGo < 0 {
		t.Fatalf("per-case ms missing: %+v", rep.Cases)
	}
	var keys map[string]any
	if err := json.Unmarshal(blob, &keys); err != nil {
		t.Fatal(err)
	}
	for _, k := range []string{"db_sha256", "db_mtime_ns", "db_changed", "p50_py", "p95_py", "p50_go", "p95_go"} {
		if _, ok := keys[k]; !ok {
			t.Fatalf("report JSON lacks %q", k)
		}
	}
	var rawCases []map[string]any
	list, ok := keys["cases"].([]any)
	if !ok || len(list) != 1 {
		t.Fatalf("cases JSON = %#v", keys["cases"])
	}
	for _, item := range list {
		m, ok := item.(map[string]any)
		if !ok {
			t.Fatalf("case JSON = %#v", item)
		}
		rawCases = append(rawCases, m)
	}
	for _, k := range []string{"ms_py", "ms_go"} {
		if _, ok := rawCases[0][k]; !ok {
			t.Fatalf("case JSON lacks %q", k)
		}
	}
}

func TestPercentileNearestRank(t *testing.T) {
	samples := []float64{10, 1, 9, 2, 8, 3, 7, 4, 6, 5}
	if got := percentile(samples, 50); got != 5 {
		t.Fatalf("p50 = %v, want 5", got)
	}
	if got := percentile(samples, 95); got != 10 {
		t.Fatalf("p95 = %v, want 10", got)
	}
	if got := percentile(samples[:3], 50); got != 9 {
		t.Fatalf("p50 of %v = %v, want 9", samples[:3], got)
	}
	if got := percentile(nil, 95); got != 0 {
		t.Fatalf("empty = %v, want 0", got)
	}
	if samples[0] != 10 {
		t.Fatal("percentile must not reorder the caller's slice")
	}
}

func TestRunDBChangedDuringBatchExits2(t *testing.T) {
	dir := t.TempDir()
	db := writeDB(t, dir)
	py, gs := server(`{"a":1}`), server(`{"a":1}`)
	defer py.Close()
	defer gs.Close()
	cases := filepath.Join(dir, "cases.json")
	if err := os.WriteFile(cases, []byte(`{"cases":[{"name":"ok","method":"GET","path":"/p"}]}`), 0o644); err != nil {
		t.Fatal(err)
	}
	out := filepath.Join(dir, "report.json")
	afterCasesHook = func() {
		f, err := os.OpenFile(db, os.O_APPEND|os.O_WRONLY, 0o644)
		if err != nil {
			t.Errorf("hook: %v", err)
			return
		}
		defer f.Close()
		_, _ = f.Write([]byte("+1"))
	}
	t.Cleanup(func() { afterCasesHook = func() {} })
	if code := run([]string{"--py", py.URL, "--go", gs.URL, "--cases", cases, "--db", db, "--out", out}); code != 2 {
		t.Fatalf("exit = %d, want 2", code)
	}
	blob, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("report must still be written: %v", err)
	}
	var rep parity.Report
	if err := json.Unmarshal(blob, &rep); err != nil {
		t.Fatal(err)
	}
	if !rep.DBChanged {
		t.Fatalf("db_changed must be true: %+v", rep)
	}
}
