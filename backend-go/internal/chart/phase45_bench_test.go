//go:build phase45

package chart

// phase45_bench_test.go — S9 before/after measurement for the 30-symbol set.
//
// Runs the same loop against a copy of the lab DB; prints wall time, payload
// bytes and heap delta. Numbers are evidence, not a gate: `-run TestP45Bench`.

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
)

func TestP45Bench(t *testing.T) {
	dir := os.Getenv("P45_DB_DIR")
	symbolsFile := os.Getenv("P45_SYMBOLS")
	if dir == "" || symbolsFile == "" {
		t.Skip("P45_DB_DIR/P45_SYMBOLS not set")
	}
	raw, err := os.ReadFile(symbolsFile)
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	if err := json.Unmarshal(raw, &names); err != nil {
		t.Fatal(err)
	}
	passes := 3
	if v := os.Getenv("P45_PASSES"); v != "" {
		fmt.Sscanf(v, "%d", &passes)
	}
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	s := New(Config{Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: dir + "/calendar/cache.json",
		Clock:        func() time.Time { return time.Now() }})
	defer s.Close()
	ctx := context.Background()
	t0 := time.Now()
	for _, sym := range names { // warm-up
		body := s.chartDBBody(ctx, sym, 3)
		_, _ = json.Marshal(body)
	}
	warm := time.Since(t0)
	total := time.Duration(0)
	maxBytes, sumBytes := 0, 0
	runtime.GC()
	var m0, m1 runtime.MemStats
	runtime.ReadMemStats(&m0)
	for p := 0; p < passes; p++ {
		start := time.Now()
		for _, sym := range names {
			body := s.chartDBBody(ctx, sym, 3)
			buf, _ := json.Marshal(body)
			sumBytes += len(buf)
			if len(buf) > maxBytes {
				maxBytes = len(buf)
			}
		}
		total += time.Since(start)
	}
	runtime.ReadMemStats(&m1)
	n := passes * len(names)
	fmt.Printf("BENCH symbols=%d passes=%d warm=%s total=%s per_symbol=%s "+
		"max_payload_bytes=%d avg_payload_bytes=%d heap_delta_bytes=%d\n",
		len(names), passes, warm.Round(time.Millisecond), total.Round(time.Millisecond),
		(total / time.Duration(n)).Round(time.Microsecond), maxBytes, sumBytes/n,
		int64(m1.HeapAlloc)-int64(m0.HeapAlloc))
}
