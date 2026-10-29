package parity

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
)

type Options struct {
	// Exclude مسیرهایِ دقیقِ JSON است (مثلِ "meta.generated_at")؛ الگویِ عام ممنوع.
	Exclude []string
}

type Result struct {
	Pass     bool     `json:"pass"`
	Diffs    []string `json:"diffs"`
	MaxDelta float64  `json:"max_delta"`
	Excluded []string `json:"excluded"`
}

type CaseReport struct {
	Name     string   `json:"name"`
	Method   string   `json:"method"`
	Path     string   `json:"path"`
	StatusPy int      `json:"status_py"`
	StatusGo int      `json:"status_go"`
	BytesPy  int      `json:"bytes_py"`
	BytesGo  int      `json:"bytes_go"`
	MsPy     float64  `json:"ms_py"`
	MsGo     float64  `json:"ms_go"`
	Pass     bool     `json:"pass"`
	MaxDelta float64  `json:"max_delta"`
	Diffs    []string `json:"diffs,omitempty"`
	Excluded []string `json:"excluded,omitempty"`
}

type Report struct {
	Commit    string       `json:"commit"`
	PyURL     string       `json:"py_url"`
	GoURL     string       `json:"go_url"`
	DBHash    string       `json:"db_sha256"`
	DBMtimeNS int64        `json:"db_mtime_ns"`
	DBChanged bool         `json:"db_changed"`
	Passed    int          `json:"passed"`
	Failed    int          `json:"failed"`
	P50Py     float64      `json:"p50_py"`
	P95Py     float64      `json:"p95_py"`
	P50Go     float64      `json:"p50_go"`
	P95Go     float64      `json:"p95_go"`
	Cases     []CaseReport `json:"cases"`
	Finished  string       `json:"finished_at"`
}

type walker struct {
	excluded  map[string]struct{}
	diffs     []string
	maxDelta  float64
	used      map[string]struct{}
	truncated bool
}

const diffLimit = 40

func Compare(want, got any, opts Options) Result {
	w := &walker{excluded: map[string]struct{}{}, used: map[string]struct{}{}}
	for _, p := range opts.Exclude {
		if strings.TrimSpace(p) == "" {
			continue
		}
		w.excluded[p] = struct{}{}
	}
	w.walk("", want, got)
	if w.truncated {
		w.diffs = append(w.diffs, "… (diffs truncated)")
	}
	out := Result{Pass: len(w.diffs) == 0, Diffs: w.diffs, MaxDelta: w.maxDelta}
	for p := range w.used {
		out.Excluded = append(out.Excluded, p)
	}
	sort.Strings(out.Excluded)
	return out
}

func (w *walker) isExcluded(path string) bool {
	_, ok := w.excluded[path]
	if ok {
		w.used[path] = struct{}{}
	}
	return ok
}

func (w *walker) walk(path string, want, got any) {
	if w.isExcluded(path) {
		return
	}
	if wantN, ok := num(want); ok {
		gotN, ok := num(got)
		if !ok {
			w.diff(path, "type", "number", kind(got))
			return
		}
		if wantN == gotN {
			return
		}
		if math.IsNaN(wantN) || math.IsNaN(gotN) || math.IsInf(wantN, 0) || math.IsInf(gotN, 0) {
			w.diff(path, "non-finite", fmt.Sprint(wantN), fmt.Sprint(gotN))
			return
		}
		// قراردادِ §۱۰: اگر هر دو صحیحِ ریاضی باشند فقط برابریِ عددی می‌پذیریم
		// (۱ و ۱٫۰ یکی‌اند). تلورانسِ نسبی اجازه می‌داد 1e9 و 1e9+1 بگذرند.
		if isIntegral(wantN) && isIntegral(gotN) {
			w.diff(path, "number", fmt.Sprintf("%v", wantN), fmt.Sprintf("%v", gotN))
			return
		}
		den := math.Max(math.Abs(wantN), 1e-12)
		delta := math.Abs(gotN-wantN) / den
		if delta > w.maxDelta {
			w.maxDelta = delta
		}
		if delta > 1e-9 {
			w.diff(path, "number", fmt.Sprintf("%v", wantN), fmt.Sprintf("%v", gotN))
		}
		return
	}
	switch wantV := want.(type) {
	case map[string]any:
		gotV, ok := got.(map[string]any)
		if !ok {
			w.diff(path, "type", "object", kind(got))
			return
		}
		wantKeys := make([]string, 0, len(wantV))
		for k := range wantV {
			wantKeys = append(wantKeys, k)
		}
		sort.Strings(wantKeys)
		for _, k := range wantKeys {
			p := join(path, k)
			g, exists := gotV[k]
			if !exists {
				if w.isExcluded(p) {
					continue
				}
				w.diff(p, "missing in go", "present", "absent")
				continue
			}
			w.walk(p, wantV[k], g)
		}
		gotKeys := make([]string, 0, len(gotV))
		for k := range gotV {
			gotKeys = append(gotKeys, k)
		}
		sort.Strings(gotKeys)
		for _, k := range gotKeys {
			if _, exists := wantV[k]; exists {
				continue
			}
			p := join(path, k)
			if w.isExcluded(p) {
				continue
			}
			w.diff(p, "extra in go", "absent", "present")
		}
	case []any:
		gotV, ok := got.([]any)
		if !ok {
			w.diff(path, "type", "array", kind(got))
			return
		}
		if len(wantV) != len(gotV) {
			w.diff(path, "array length", fmt.Sprint(len(wantV)), fmt.Sprint(len(gotV)))
			return
		}
		for i := range wantV {
			w.walk(fmt.Sprintf("%s[%d]", path, i), wantV[i], gotV[i])
		}
	case nil:
		if got != nil {
			w.diff(path, "type", "null", kind(got))
		}
	case string:
		gotV, ok := got.(string)
		if !ok {
			w.diff(path, "type", "string", kind(got))
			return
		}
		if wantV != gotV {
			w.diff(path, "value", wantV, gotV)
		}
	case bool:
		gotV, ok := got.(bool)
		if !ok {
			w.diff(path, "type", "bool", kind(got))
			return
		}
		if wantV != gotV {
			w.diff(path, "value", fmt.Sprint(wantV), fmt.Sprint(gotV))
		}
	default:
		w.diff(path, "type", kind(want), kind(got))
	}
}

func (w *walker) diff(path, what, want, got string) {
	if len(w.diffs) >= diffLimit {
		w.truncated = true
		return
	}
	w.diffs = append(w.diffs, fmt.Sprintf("%s: %s (%s != %s)", path, what, want, got))
}

func join(path, key string) string {
	if path == "" {
		return key
	}
	return path + "." + key
}

// isIntegral یعنی عدد صحیحِ ریاضی است (۱ و ۱٫۰ هر دو). NaN/Inf پیش از این
// بررسی حذف شده‌اند، پس Truncِ امن است.
func isIntegral(v float64) bool { return v == math.Trunc(v) }

func kind(v any) string {
	switch v.(type) {
	case nil:
		return "null"
	case map[string]any:
		return "object"
	case []any:
		return "array"
	case float64:
		return "number"
	case string:
		return "string"
	case bool:
		return "bool"
	default:
		return strings.TrimSpace(fmt.Sprintf("%T", v))
	}
}

// num هر نوعِ عددیِ Go را به float64 نرمال می‌کند تا عددِ صحیح با عددِ اعشاری
// برابرِ عددی شمرده شود (قراردادِ API: 1 == 1.0).
func num(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int8:
		return float64(x), true
	case int16:
		return float64(x), true
	case int32:
		return float64(x), true
	case int64:
		return float64(x), true
	case uint:
		return float64(x), true
	case uint8:
		return float64(x), true
	case uint16:
		return float64(x), true
	case uint32:
		return float64(x), true
	case uint64:
		return float64(x), true
	case json.Number:
		f, err := x.Float64()
		return f, err == nil
	default:
		return 0, false
	}
}
