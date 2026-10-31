package candle

import "testing"

// وکتورها از قاعدهٔ candle_contract.widen گرفته شده‌اند (کامنتِ v8.7 FIX-1b و
// پروندهٔ «پالایش ۲۰۲۴-۱۰-۲۳»).
func TestWiden(t *testing.T) {
	cases := []struct {
		name            string
		open, high, low float64
		prices          []float64
		wantHi, wantLo  float64
	}{
		{"no body", 0, 110, 90, nil, 110, 90},
		{"inside", 100, 110, 90, []float64{95}, 110, 90},
		{"goesad body", 100, 0, 0, []float64{105, 95}, 105, 95},
		{"close cuts high", 100, 101, 90, []float64{103}, 103, 90},
		{"palahan: high is defect, low is empty", 1200, 1100, 0, []float64{1150}, 1200, 1150},
		{"high zero is a hole", 0, 0, 0, []float64{100}, 100, 100},
		{"negative prices are kept (not falsy in Go check)", -5, 10, -10, []float64{-7}, 10, -10},
	}
	for _, c := range cases {
		hi, lo := Widen(c.open, c.high, c.low, c.prices...)
		if hi != c.wantHi || lo != c.wantLo {
			t.Errorf("%s: Widen(%v,%v,%v,%v) = (%v,%v), want (%v,%v)",
				c.name, c.open, c.high, c.low, c.prices, hi, lo, c.wantHi, c.wantLo)
		}
	}
}

func TestWidenIsIdempotent(t *testing.T) {
	hi, lo := Widen(100, 90, 110, 0, 0)
	hi2, lo2 := Widen(100, hi, lo, 0, 0)
	if hi != hi2 || lo != lo2 {
		t.Fatalf("second call changed geometry: (%v,%v) -> (%v,%v)", hi, lo, hi2, lo2)
	}
}
