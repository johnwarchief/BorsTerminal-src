package indicators

import (
	"math"
	"testing"
)

func floatEquals(a, b, epsilon float64) bool {
	return math.Abs(a-b) <= epsilon
}

func TestCalculateSMA(t *testing.T) {
	prices := []float64{10, 11, 12, 13, 14, 15, 16, 17, 18, 19}
	sma := CalculateSMA(prices, 5)

	if len(sma) != 10 {
		t.Fatalf("expected len 10, got %d", len(sma))
	}
	if sma[3] != 0.0 {
		t.Errorf("expected sma[3] == 0, got %f", sma[3])
	}
	if !floatEquals(sma[4], 12.0, 1e-6) {
		t.Errorf("expected sma[4] == 12.0, got %f", sma[4])
	}
	if !floatEquals(sma[9], 17.0, 1e-6) {
		t.Errorf("expected sma[9] == 17.0, got %f", sma[9])
	}

	// Edge cases
	emptySMA := CalculateSMA([]float64{}, 5)
	if len(emptySMA) != 0 {
		t.Errorf("expected empty result for empty slice, got len %d", len(emptySMA))
	}

	shortSMA := CalculateSMA([]float64{10, 20}, 5)
	if len(shortSMA) != 2 || shortSMA[0] != 0 || shortSMA[1] != 0 {
		t.Errorf("expected zeroed slice for short input, got %v", shortSMA)
	}

	zeroPeriodSMA := CalculateSMA(prices, 0)
	if len(zeroPeriodSMA) != 10 || zeroPeriodSMA[4] != 0 {
		t.Errorf("expected zeroed slice for period <= 0, got %v", zeroPeriodSMA)
	}

	negPeriodSMA := CalculateSMA(prices, -3)
	if len(negPeriodSMA) != 10 || negPeriodSMA[4] != 0 {
		t.Errorf("expected zeroed slice for negative period, got %v", negPeriodSMA)
	}
}

func TestCalculateEMA(t *testing.T) {
	prices := []float64{10, 11, 12, 13, 14, 15, 16, 17, 18, 19}
	ema := CalculateEMA(prices, 5)

	if len(ema) != 10 {
		t.Fatalf("expected len 10, got %d", len(ema))
	}
	if ema[3] != 0.0 {
		t.Errorf("expected ema[3] == 0, got %f", ema[3])
	}
	// Initial EMA at index 4 is SMA(first 5) = 12.0
	if !floatEquals(ema[4], 12.0, 1e-6) {
		t.Errorf("expected ema[4] == 12.0, got %f", ema[4])
	}
	// Multiplier k = 2 / (5 + 1) = 1/3
	// ema[5] = 15 * (1/3) + 12 * (2/3) = 5 + 8 = 13.0
	if !floatEquals(ema[5], 13.0, 1e-6) {
		t.Errorf("expected ema[5] == 13.0, got %f", ema[5])
	}

	// Edge cases
	if len(CalculateEMA([]float64{}, 5)) != 0 {
		t.Errorf("expected empty result for empty slice")
	}
	if len(CalculateEMA(prices, 0)) != 10 {
		t.Errorf("expected slice of length 10 for period 0")
	}
	if len(CalculateEMA([]float64{1, 2}, 5)) != 2 {
		t.Errorf("expected slice of length 2 for short slice")
	}
}

func TestCalculateRSI(t *testing.T) {
	prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115}
	rsi := CalculateRSI(prices, 14)

	if len(rsi) != len(prices) {
		t.Fatalf("expected len %d, got %d", len(prices), len(rsi))
	}
	if rsi[13] != 0.0 {
		t.Errorf("expected rsi[13] == 0, got %f", rsi[13])
	}
	// At index 14, 14 price changes have been observed
	if rsi[14] <= 50.0 || rsi[14] >= 100.0 {
		t.Errorf("expected rsi[14] between 50 and 100, got %f", rsi[14])
	}
	if rsi[15] <= 50.0 || rsi[15] >= 100.0 {
		t.Errorf("expected rsi[15] between 50 and 100, got %f", rsi[15])
	}

	// Monotonic increasing: RSI should be 100
	inc := []float64{10, 11, 12, 13, 14, 15}
	rsiInc := CalculateRSI(inc, 3)
	if !floatEquals(rsiInc[3], 100.0, 1e-6) {
		t.Errorf("expected 100.0 for all gains, got %f", rsiInc[3])
	}

	// Monotonic decreasing: RSI should be 0
	dec := []float64{15, 14, 13, 12, 11, 10}
	rsiDec := CalculateRSI(dec, 3)
	if !floatEquals(rsiDec[3], 0.0, 1e-6) {
		t.Errorf("expected 0.0 for all losses, got %f", rsiDec[3])
	}

	// Flat prices: RSI should be 50
	flat := []float64{10, 10, 10, 10, 10}
	rsiFlat := CalculateRSI(flat, 3)
	if !floatEquals(rsiFlat[3], 50.0, 1e-6) {
		t.Errorf("expected 50.0 for flat prices, got %f", rsiFlat[3])
	}

	// Edge cases
	if len(CalculateRSI([]float64{}, 14)) != 0 {
		t.Errorf("expected empty result for empty slice")
	}
	if len(CalculateRSI([]float64{1, 2, 3}, 14)) != 3 {
		t.Errorf("expected slice of length 3 for short slice")
	}
	if len(CalculateRSI(prices, 0)) != len(prices) {
		t.Errorf("expected slice of length %d for period 0", len(prices))
	}
}

func TestCalculateMACD(t *testing.T) {
	// Construct 40 prices
	prices := make([]float64, 40)
	for i := range prices {
		prices[i] = float64(100 + i)
	}

	macdLine, signalLine, histogram := CalculateMACD(prices, 12, 26, 9)

	if len(macdLine) != 40 || len(signalLine) != 40 || len(histogram) != 40 {
		t.Fatalf("expected all output slices to have length 40")
	}

	// MACD should start at index 25 (26-1)
	if macdLine[24] != 0.0 {
		t.Errorf("expected macdLine[24] == 0, got %f", macdLine[24])
	}
	if macdLine[25] == 0.0 {
		t.Errorf("expected macdLine[25] != 0")
	}

	// Signal line starts at index 25 + 9 - 1 = 33
	if signalLine[32] != 0.0 {
		t.Errorf("expected signalLine[32] == 0, got %f", signalLine[32])
	}
	if signalLine[33] == 0.0 {
		t.Errorf("expected signalLine[33] != 0")
	}

	// Histogram = macdLine - signalLine for i >= 33
	expectedHist33 := macdLine[33] - signalLine[33]
	if !floatEquals(histogram[33], expectedHist33, 1e-6) {
		t.Errorf("expected histogram[33] == %f, got %f", expectedHist33, histogram[33])
	}

	// Edge cases: short inputs, zero periods
	m, s, h := CalculateMACD([]float64{1, 2, 3}, 12, 26, 9)
	if len(m) != 3 || len(s) != 3 || len(h) != 3 {
		t.Errorf("expected len 3 for short input")
	}
	m0, _, _ := CalculateMACD(prices, 0, 26, 9)
	if len(m0) != 40 || m0[25] != 0 {
		t.Errorf("expected zeroed slices for invalid period")
	}
}

func TestCalculateBollingerBands(t *testing.T) {
	prices := []float64{20, 22, 24, 26, 28}
	upper, middle, lower := CalculateBollingerBands(prices, 5, 2.0)

	if len(upper) != 5 || len(middle) != 5 || len(lower) != 5 {
		t.Fatalf("expected len 5 for all slices")
	}

	// Prior to index 4, should be 0
	if middle[3] != 0.0 || upper[3] != 0.0 || lower[3] != 0.0 {
		t.Errorf("expected zeros before period-1")
	}

	// Mean of [20, 22, 24, 26, 28] = 120 / 5 = 24.0
	if !floatEquals(middle[4], 24.0, 1e-6) {
		t.Errorf("expected middle[4] == 24.0, got %f", middle[4])
	}

	// Variance = (16 + 4 + 0 + 4 + 16) / 5 = 40 / 5 = 8.0
	// StdDev = sqrt(8.0) ≈ 2.828427
	expectedStd := math.Sqrt(8.0)
	expectedUpper := 24.0 + 2.0*expectedStd
	expectedLower := 24.0 - 2.0*expectedStd

	if !floatEquals(upper[4], expectedUpper, 1e-6) {
		t.Errorf("expected upper[4] == %f, got %f", expectedUpper, upper[4])
	}
	if !floatEquals(lower[4], expectedLower, 1e-6) {
		t.Errorf("expected lower[4] == %f, got %f", expectedLower, lower[4])
	}

	// Edge cases
	u, m, l := CalculateBollingerBands([]float64{}, 5, 2.0)
	if len(u) != 0 || len(m) != 0 || len(l) != 0 {
		t.Errorf("expected empty slices for empty input")
	}
	uShort, _, _ := CalculateBollingerBands([]float64{10, 20}, 5, 2.0)
	if len(uShort) != 2 || uShort[1] != 0 {
		t.Errorf("expected zeroed slice for short input")
	}
}

func TestCalculateATR(t *testing.T) {
	highs := []float64{48.70, 48.72, 48.90, 48.87, 48.82, 49.05, 49.20, 49.35, 49.92, 50.19, 50.12, 49.66, 49.88, 50.19, 50.36}
	lows := []float64{47.79, 48.14, 48.39, 48.37, 48.24, 48.64, 48.94, 48.86, 49.50, 49.87, 49.20, 48.98, 49.43, 49.73, 49.26}
	closes := []float64{48.16, 48.61, 48.75, 48.63, 48.74, 49.03, 49.07, 49.32, 49.91, 50.13, 49.53, 49.50, 49.75, 50.03, 50.31}

	atr := CalculateATR(highs, lows, closes, 14)
	if len(atr) != len(highs) {
		t.Fatalf("expected len %d, got %d", len(highs), len(atr))
	}

	// Prior to index 13, atr is 0
	if atr[12] != 0.0 {
		t.Errorf("expected atr[12] == 0, got %f", atr[12])
	}
	// Index 13 should be valid ATR > 0
	if atr[13] <= 0.0 {
		t.Errorf("expected atr[13] > 0, got %f", atr[13])
	}
	// Index 14 smoothed
	if atr[14] <= 0.0 {
		t.Errorf("expected atr[14] > 0, got %f", atr[14])
	}

	// Edge cases
	emptyATR := CalculateATR([]float64{}, []float64{}, []float64{}, 14)
	if len(emptyATR) != 0 {
		t.Errorf("expected empty result for empty inputs")
	}
	mismatchedATR := CalculateATR([]float64{1, 2}, []float64{1}, []float64{1, 2}, 14)
	if len(mismatchedATR) != 2 || mismatchedATR[0] != 0 {
		t.Errorf("expected zeroed result for mismatched slices")
	}
}

func TestCalculateSuperTrend(t *testing.T) {
	// 20 bars in an uptrend
	n := 20
	highs := make([]float64, n)
	lows := make([]float64, n)
	closes := make([]float64, n)

	for i := 0; i < n; i++ {
		base := 100.0 + float64(i)*2.0
		lows[i] = base - 1.0
		highs[i] = base + 3.0
		closes[i] = base + 2.0
	}

	period := 5
	multiplier := 2.0
	st, dir := CalculateSuperTrend(highs, lows, closes, period, multiplier)

	if len(st) != n || len(dir) != n {
		t.Fatalf("expected len %d, got %d, %d", n, len(st), len(dir))
	}

	// Prior to period-1 (index 4), st and dir should be 0
	for i := 0; i < period-1; i++ {
		if st[i] != 0.0 || dir[i] != 0 {
			t.Errorf("expected 0 at index %d before period, got st=%f dir=%d", i, st[i], dir[i])
		}
	}

	// In a sustained uptrend, direction should be 1 (bullish) and supertrend < closes[i]
	for i := period - 1; i < n; i++ {
		if dir[i] != 1 {
			t.Errorf("expected dir[%d] == 1 in uptrend, got %d", i, dir[i])
		}
		if st[i] >= closes[i] {
			t.Errorf("expected st[%d] (%f) < closes[%d] (%f) in uptrend", i, st[i], i, closes[i])
		}
	}

	// Test trend reversal to downtrend
	downtrendCloses := make([]float64, n)
	copy(downtrendCloses, closes)
	// Crash price on last bars
	for i := 15; i < n; i++ {
		downtrendCloses[i] = 50.0 // severe drop
		highs[i] = 60.0
		lows[i] = 45.0
	}
	st2, dir2 := CalculateSuperTrend(highs, lows, downtrendCloses, period, multiplier)
	if dir2[n-1] != -1 {
		t.Errorf("expected reversal to downtrend (-1) at last bar, got %d", dir2[n-1])
	}
	if st2[n-1] <= downtrendCloses[n-1] {
		t.Errorf("expected st (%f) > close (%f) in downtrend", st2[n-1], downtrendCloses[n-1])
	}

	// Edge cases
	emptyST, emptyDir := CalculateSuperTrend([]float64{}, []float64{}, []float64{}, 5, 2.0)
	if len(emptyST) != 0 || len(emptyDir) != 0 {
		t.Errorf("expected empty slices for empty input")
	}
	zeroPeriodST, _ := CalculateSuperTrend(highs, lows, closes, 0, 2.0)
	if len(zeroPeriodST) != n || zeroPeriodST[period] != 0 {
		t.Errorf("expected zero slice for period <= 0")
	}
}

func TestHeikinAshiCandles(t *testing.T) {
	opens := []float64{10, 12, 14}
	highs := []float64{13, 15, 16}
	lows := []float64{9, 11, 13}
	closes := []float64{12, 14, 15}

	haOpen, haHigh, haLow, haClose := HeikinAshiCandles(opens, highs, lows, closes)

	if len(haOpen) != 3 || len(haHigh) != 3 || len(haLow) != 3 || len(haClose) != 3 {
		t.Fatalf("expected len 3 for all Heikin Ashi slices")
	}

	// Bar 0:
	// haClose[0] = (10 + 13 + 9 + 12) / 4 = 44 / 4 = 11.0
	// haOpen[0] = (10 + 12) / 2 = 11.0
	// haHigh[0] = 13.0
	// haLow[0] = 9.0
	if !floatEquals(haClose[0], 11.0, 1e-6) {
		t.Errorf("expected haClose[0] == 11.0, got %f", haClose[0])
	}
	if !floatEquals(haOpen[0], 11.0, 1e-6) {
		t.Errorf("expected haOpen[0] == 11.0, got %f", haOpen[0])
	}
	if !floatEquals(haHigh[0], 13.0, 1e-6) {
		t.Errorf("expected haHigh[0] == 13.0, got %f", haHigh[0])
	}
	if !floatEquals(haLow[0], 9.0, 1e-6) {
		t.Errorf("expected haLow[0] == 9.0, got %f", haLow[0])
	}

	// Bar 1:
	// haClose[1] = (12 + 15 + 11 + 14) / 4 = 52 / 4 = 13.0
	// haOpen[1] = (haOpen[0] + haClose[0]) / 2 = (11.0 + 11.0) / 2 = 11.0
	// haHigh[1] = max(15, 11, 13) = 15.0
	// haLow[1] = min(11, 11, 13) = 11.0
	if !floatEquals(haClose[1], 13.0, 1e-6) {
		t.Errorf("expected haClose[1] == 13.0, got %f", haClose[1])
	}
	if !floatEquals(haOpen[1], 11.0, 1e-6) {
		t.Errorf("expected haOpen[1] == 11.0, got %f", haOpen[1])
	}
	if !floatEquals(haHigh[1], 15.0, 1e-6) {
		t.Errorf("expected haHigh[1] == 15.0, got %f", haHigh[1])
	}
	if !floatEquals(haLow[1], 11.0, 1e-6) {
		t.Errorf("expected haLow[1] == 11.0, got %f", haLow[1])
	}

	// Edge cases
	ho, hh, hl, hc := HeikinAshiCandles([]float64{}, []float64{}, []float64{}, []float64{})
	if len(ho) != 0 || len(hh) != 0 || len(hl) != 0 || len(hc) != 0 {
		t.Errorf("expected empty slices for empty input")
	}
	hoM, _, _, _ := HeikinAshiCandles([]float64{1, 2}, []float64{1}, []float64{1, 2}, []float64{1, 2})
	if len(hoM) != 2 || hoM[0] != 0 {
		t.Errorf("expected zeroed slices for mismatched inputs")
	}
}
