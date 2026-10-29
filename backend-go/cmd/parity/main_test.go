package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
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
