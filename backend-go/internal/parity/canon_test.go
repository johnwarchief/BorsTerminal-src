package parity

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
)

func decode(t *testing.T, s string) any {
	t.Helper()
	var v any
	if err := json.Unmarshal([]byte(s), &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func TestKeyOrderIrrelevant(t *testing.T) {
	r := Compare(decode(t, `{"a":1,"b":"x"}`), decode(t, `{"b":"x","a":1}`), Options{})
	if !r.Pass {
		t.Fatalf("diffs=%v", r.Diffs)
	}
}

func TestNumberForms(t *testing.T) {
	r := Compare(decode(t, `{"a":1.0}`), decode(t, `{"a":1}`), Options{})
	if !r.Pass {
		t.Fatalf("1 and 1.0 must match: %v", r.Diffs)
	}
	r = Compare(decode(t, `{"a":1.0}`), decode(t, `{"a":1.0000000001}`), Options{})
	if !r.Pass || r.MaxDelta == 0 {
		t.Fatalf("1e-9 tolerance failed: %+v", r)
	}
	r = Compare(decode(t, `{"a":1}`), decode(t, `{"a":1.01}`), Options{})
	if r.Pass {
		t.Fatal("1.01 must differ")
	}
}

func TestStringExactAndArrayOrder(t *testing.T) {
	r := Compare(decode(t, `{"s":"بیداده"}`), decode(t, `{"s":"بی داده"}`), Options{})
	if r.Pass {
		t.Fatal("strings must match exactly")
	}
	r = Compare(decode(t, `[1,2]`), decode(t, `[2,1]`), Options{})
	if r.Pass {
		t.Fatal("array order matters")
	}
	r = Compare(decode(t, `[1,2]`), decode(t, `[1,2,3]`), Options{})
	if r.Pass {
		t.Fatal("length matters")
	}
}

func TestExclusionsAreExplicitPaths(t *testing.T) {
	want := decode(t, `{"meta":{"generated_at":"a","n":2}}`)
	got := decode(t, `{"meta":{"generated_at":"b","n":2}}`)
	if Compare(want, got, Options{}).Pass {
		t.Fatal("without exclusion it must differ")
	}
	r := Compare(want, got, Options{Exclude: []string{"meta.generated_at"}})
	if !r.Pass {
		t.Fatalf("excluded path still differs: %v", r.Diffs)
	}
	if len(r.Excluded) != 1 || r.Excluded[0] != "meta.generated_at" {
		t.Fatalf("excluded = %v", r.Excluded)
	}
}

func TestNullVsMissingKey(t *testing.T) {
	r := Compare(decode(t, `{"a":null}`), decode(t, `{}`), Options{})
	if r.Pass {
		t.Fatal("missing key is not null")
	}
}

func TestTypeStrictLeaves(t *testing.T) {
	cases := []struct{ name, want, got string }{
		{"string-vs-number", `{"a":"1"}`, `{"a":1}`},
		{"string-vs-bool", `{"a":"true"}`, `{"a":true}`},
		{"string-nil-vs-null", `{"a":"<nil>"}`, `{"a":null}`},
		{"bool-vs-number", `{"a":false}`, `{"a":0}`},
		{"number-vs-string", `{"a":1}`, `{"a":"1"}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r := Compare(decode(t, tc.want), decode(t, tc.got), Options{})
			if r.Pass {
				t.Fatalf("%s vs %s must fail", tc.want, tc.got)
			}
			if len(r.Diffs) == 0 || !strings.Contains(r.Diffs[0], "type") {
				t.Fatalf("want a type diff, got %v", r.Diffs)
			}
		})
	}
}

func TestNumberToleranceBoundary(t *testing.T) {
	r := Compare(decode(t, `{"a":1}`), decode(t, `{"a":1.0000000001}`), Options{})
	if !r.Pass {
		t.Fatalf("1e-10 delta must pass: %v", r.Diffs)
	}
	r = Compare(decode(t, `{"a":1}`), decode(t, `{"a":1.000000002}`), Options{})
	if r.Pass {
		t.Fatal("2e-9 delta must fail")
	}
	r = Compare(decode(t, `[1,2]`), decode(t, `[2,1]`), Options{})
	if r.Pass {
		t.Fatal("array order still matters")
	}
}

func TestExcludedMissingKeyPasses(t *testing.T) {
	want := decode(t, `{"meta":{"t":"a","n":2}}`)
	got := decode(t, `{"meta":{"n":2}}`)
	r := Compare(want, got, Options{Exclude: []string{"meta.t"}})
	if !r.Pass {
		t.Fatalf("excluded missing key must pass: %v", r.Diffs)
	}
	if len(r.Excluded) != 1 || r.Excluded[0] != "meta.t" {
		t.Fatalf("excluded = %v", r.Excluded)
	}
	r = Compare(got, want, Options{Exclude: []string{"meta.t"}})
	if !r.Pass {
		t.Fatalf("excluded extra key must pass: %v", r.Diffs)
	}
	if len(r.Excluded) != 1 || r.Excluded[0] != "meta.t" {
		t.Fatalf("excluded = %v", r.Excluded)
	}
}

func TestEmptyExclusionDoesNotSuppress(t *testing.T) {
	r := Compare(decode(t, `{"a":1}`), decode(t, `{"a":2}`), Options{Exclude: []string{""}})
	if r.Pass {
		t.Fatal("empty exclusion must not suppress the document")
	}
	r = Compare(decode(t, `{"a":1}`), decode(t, `{"a":2}`), Options{Exclude: []string{"   "}})
	if r.Pass {
		t.Fatal("blank exclusion must not suppress the document")
	}
}

func TestDiffOrderDeterministic(t *testing.T) {
	want := decode(t, `{"a":1,"b":2}`)
	got := decode(t, `{}`)
	for i := 0; i < 25; i++ {
		r := Compare(want, got, Options{})
		if len(r.Diffs) != 2 {
			t.Fatalf("diffs = %v", r.Diffs)
		}
		if !strings.HasPrefix(r.Diffs[0], "a: ") || !strings.HasPrefix(r.Diffs[1], "b: ") {
			t.Fatalf("nondeterministic order: %v", r.Diffs)
		}
	}
}

func TestDiffTruncationMarker(t *testing.T) {
	var sb strings.Builder
	sb.WriteString("{")
	for i := 0; i < 45; i++ {
		if i > 0 {
			sb.WriteString(",")
		}
		fmt.Fprintf(&sb, `"k%02d":0`, i)
	}
	sb.WriteString("}")
	want := decode(t, sb.String())
	r := Compare(want, decode(t, `{}`), Options{})
	if r.Pass {
		t.Fatal("missing keys must differ")
	}
	if len(r.Diffs) != 41 {
		t.Fatalf("want 40 diffs plus marker, got %d", len(r.Diffs))
	}
	if r.Diffs[40] != "… (diffs truncated)" {
		t.Fatalf("last diff = %q", r.Diffs[40])
	}
}
