package pyround

import (
	"math"
	"testing"
)

// برداشت‌ها مستقیم از CPython 3.14 گرفته شده‌اند (نه دست‌حساب): گردکردنِ
// round(x, n) رویِ همان دودوییِ float است، نه رویِ نمایشِ اعشاری.
func TestRoundMatchesCPython(t *testing.T) {
	cases := []struct {
		x    float64
		n    int
		want float64
	}{
		{2.675, 0, 3}, {2.675, 1, 2.7}, {2.675, 2, 2.67},
		{0.35, 1, 0.3}, {0.45, 1, 0.5}, {1.15, 1, 1.1}, {1.05, 1, 1.1}, {0.15, 1, 0.1},
		{2.5, 0, 2}, {3.5, 0, 4}, {-2.5, 0, -2},
		{1234.5675, 2, 1234.57}, {1234.5675, 3, 1234.568},
		{1e13 / 1e9, 3, 10000}, {0.0000005, 6, 0},
	}
	for _, c := range cases {
		if got := Round(c.x, c.n); got != c.want {
			t.Errorf("Round(%v,%d) = %v, want %v", c.x, c.n, got, c.want)
		}
	}
}

func TestRoundLeavesNonFinite(t *testing.T) {
	if !math.IsNaN(Round(math.NaN(), 2)) {
		t.Fatal("NaN must stay NaN")
	}
	if !math.IsInf(Round(math.Inf(1), 2), 1) {
		t.Fatal("Inf must stay Inf")
	}
}
