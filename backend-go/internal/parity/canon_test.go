package parity

import (
	"encoding/json"
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
