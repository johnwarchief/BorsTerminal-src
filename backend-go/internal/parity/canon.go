package parity

import (
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
	Pass     bool     `json:"pass"`
	MaxDelta float64  `json:"max_delta"`
	Diffs    []string `json:"diffs,omitempty"`
	Excluded []string `json:"excluded,omitempty"`
}

type Report struct {
	Commit   string       `json:"commit"`
	PyURL    string       `json:"py_url"`
	GoURL    string       `json:"go_url"`
	DBHash   string       `json:"db_sha256"`
	Passed   int          `json:"passed"`
	Failed   int          `json:"failed"`
	Cases    []CaseReport `json:"cases"`
	Finished string       `json:"finished_at"`
}

type walker struct {
	opts     Options
	excluded map[string]struct{}
	diffs    []string
	maxDelta float64
	used     map[string]struct{}
}

func Compare(want, got any, opts Options) Result {
	w := &walker{opts: opts, excluded: map[string]struct{}{}, used: map[string]struct{}{}}
	for _, p := range opts.Exclude {
		w.excluded[p] = struct{}{}
	}
	w.walk("", want, got)
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
	switch wantV := want.(type) {
	case map[string]any:
		gotV, ok := got.(map[string]any)
		if !ok {
			w.diff(path, "type", "object", kind(got))
			return
		}
		for k, v := range wantV {
			g, exists := gotV[k]
			if !exists {
				w.diff(path+"."+k, "missing in go", "present", "absent")
				continue
			}
			w.walk(join(path, k), v, g)
		}
		for k := range gotV {
			if _, exists := wantV[k]; !exists {
				w.diff(path+"."+k, "extra in go", "absent", "present")
			}
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
	case float64:
		gotV, ok := got.(float64)
		if !ok {
			w.diff(path, "type", "number", kind(got))
			return
		}
		if wantV == gotV {
			return
		}
		if math.IsNaN(wantV) || math.IsNaN(gotV) || math.IsInf(wantV, 0) || math.IsInf(gotV, 0) {
			w.diff(path, "non-finite", fmt.Sprint(wantV), fmt.Sprint(gotV))
			return
		}
		den := math.Max(math.Abs(wantV), 1e-12)
		delta := math.Abs(gotV-wantV) / den
		if delta > w.maxDelta {
			w.maxDelta = delta
		}
		if delta > 1e-9 {
			w.diff(path, "number", fmt.Sprintf("%v", wantV), fmt.Sprintf("%v", gotV))
		}
	default:
		if fmt.Sprint(want) != fmt.Sprint(got) {
			w.diff(path, "value", fmt.Sprint(want), fmt.Sprint(got))
		}
	}
}

func (w *walker) diff(path, what, want, got string) {
	if len(w.diffs) >= 40 {
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
