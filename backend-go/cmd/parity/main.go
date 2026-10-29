package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
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
	// media نوعِ رسانهٔ نرمال‌شده است (کوچک، بدونِ پارامتر، تریم‌شده).
	media string
}

// requestBuildError marks a case whose request could not even be constructed
// (bad base URL or method): a programmer error, not a parity failure.
type requestBuildError struct{ err error }

func (e *requestBuildError) Error() string { return e.err.Error() }
func (e *requestBuildError) Unwrap() error { return e.err }

var httpClient = &http.Client{Timeout: 60 * time.Second}

// afterCasesHook جایِ آزمونِ «DB در میانهٔ دسته عوض شد» است؛ در اجرایِ واقعی
// تهی است. بدونِ این درز، همان مسیر فقط با بازرسیِ کد اثبات‌شدنی بود.
var afterCasesHook = func() {}

// fetch پاسخ را می‌خواند و نوعِ رسانه را نرمال نگه می‌دارد: «Application/JSON;
// charset=utf-8» و «application/json» یک چیزند، ولی json و html نه.
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
	out := fetched{
		status: resp.StatusCode,
		body:   body,
		media:  normalizeMediaType(resp.Header.Get("Content-Type")),
	}
	if err := json.Unmarshal(body, &out.value); err != nil {
		return fetched{}, fmt.Errorf("%s: body is not JSON: %w", c.Path, err)
	}
	return out, nil
}

func normalizeMediaType(v string) string {
	if i := strings.IndexByte(v, ';'); i >= 0 {
		v = v[:i]
	}
	return strings.ToLower(strings.TrimSpace(v))
}

const hashChunk = 1 << 20

// fileFingerprint هشِ sha256 و mtime نانوثانیه‌ای را جریانی می‌خواند؛ DBِ
// عملیاتی هرگز نوشته نمی‌شود و در حافظه بار نمی‌شود.
func fileFingerprint(path string) (string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return "", 0, err
	}
	h := sha256.New()
	if _, err := io.CopyBuffer(h, f, make([]byte, hashChunk)); err != nil {
		return "", 0, err
	}
	return hex.EncodeToString(h.Sum(nil)), st.ModTime().UnixNano(), nil
}

// percentile رتبهٔ نزدیک‌ترین (nearest-rank) روی نمونه‌هایِ خام است؛ ورودی
// مرتب نمی‌شود، خودش کپیِ مرتب می‌سازد.
func percentile(samples []float64, p float64) float64 {
	if len(samples) == 0 {
		return 0
	}
	s := append([]float64(nil), samples...)
	sort.Float64s(s)
	rank := int(math.Ceil(p / 100 * float64(len(s))))
	if rank < 1 {
		rank = 1
	}
	if rank > len(s) {
		rank = len(s)
	}
	return s[rank-1]
}

func msSince(start time.Time) float64 {
	return float64(time.Since(start).Nanoseconds()) / 1e6
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	fs := flag.NewFlagSet("parity", flag.ContinueOnError)
	py := fs.String("py", "http://127.0.0.1:8299", "python base URL")
	goURL := fs.String("go", "http://127.0.0.1:8298", "go base URL")
	cases := fs.String("cases", "", "cases JSON")
	db := fs.String("db", "", "market.db both servers use (hashed before/after the batch)")
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
	// بانکِ یخ‌زده: هشِ اعلام‌شده باید با هشِ اندازه‌گیری‌شده یکی باشد، وگرنه
	// دسته از پایه بی‌معناست؛ پیش از هر کیس متوقف می‌شویم.
	if *db == "" {
		if cf.DBHash != "" {
			fmt.Fprintln(os.Stderr, "cases declare db_sha256 but --db is missing")
			return 2
		}
	}
	var dbHash string
	var dbMtime int64
	if *db != "" {
		dbHash, dbMtime, err = fileFingerprint(*db)
		if err != nil {
			fmt.Fprintf(os.Stderr, "--db %s: %v\n", *db, err)
			return 2
		}
		if cf.DBHash != "" && !strings.EqualFold(cf.DBHash, dbHash) {
			fmt.Fprintf(os.Stderr,
				"db_sha256 mismatch for %s: cases declare %s, measured %s\n",
				*db, cf.DBHash, dbHash)
			return 2
		}
	}
	report := parity.Report{
		Commit: *commit, PyURL: *py, GoURL: *goURL,
		DBHash: dbHash, DBMtimeNS: dbMtime,
	}
	pyMs := make([]float64, 0, len(cf.Cases))
	goMs := make([]float64, 0, len(cf.Cases))
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
		pyMs = append(pyMs, row.MsPy)
		goMs = append(goMs, row.MsGo)
		report.Cases = append(report.Cases, row)
	}
	afterCasesHook()
	report.P50Py, report.P95Py = percentile(pyMs, 50), percentile(pyMs, 95)
	report.P50Go, report.P95Go = percentile(goMs, 50), percentile(goMs, 95)
	if *db != "" {
		h2, m2, err := fileFingerprint(*db)
		if err != nil {
			fmt.Fprintf(os.Stderr, "db re-read failed: %v\n", err)
			report.DBChanged = true
		} else if h2 != dbHash || m2 != dbMtime {
			report.DBChanged = true
		}
	}
	if report.DBChanged {
		fmt.Println("db changed during the batch; batch invalid")
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
	if report.DBChanged {
		return 2
	}
	if report.Failed > 0 {
		return 1
	}
	return 0
}

func compareCase(pyBase, goBase string, c testCase) (parity.CaseReport, error) {
	row := parity.CaseReport{Name: c.Name, Method: c.Method, Path: c.Path}
	start := time.Now()
	a, err := fetch(pyBase, c)
	row.MsPy = msSince(start)
	if err != nil {
		var build *requestBuildError
		if errors.As(err, &build) {
			return parity.CaseReport{}, fmt.Errorf("py %s: %w", c.Path, err)
		}
		row.Diffs = []string{"py fetch: " + err.Error()}
		return row, nil
	}
	row.StatusPy, row.BytesPy = a.status, len(a.body)
	start = time.Now()
	b, err := fetch(goBase, c)
	row.MsGo = msSince(start)
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
	if a.media != b.media {
		row.Diffs = []string{fmt.Sprintf("content-type: %s != %s", a.media, b.media)}
		return row, nil
	}
	res := parity.Compare(a.value, b.value, parity.Options{Exclude: c.Exclude})
	row.Pass, row.Diffs, row.MaxDelta, row.Excluded = res.Pass, res.Diffs, res.MaxDelta, res.Excluded
	return row, nil
}
