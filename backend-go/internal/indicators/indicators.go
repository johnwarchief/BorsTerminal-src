package indicators

import (
	"math"
)

// CalculateSMA computes the Simple Moving Average over the specified period.
// If period <= 0 or len(values) < period, it returns a zeroed slice of length len(values).
func CalculateSMA(values []float64, period int) []float64 {
	n := len(values)
	res := make([]float64, n)
	if period <= 0 || n < period {
		return res
	}
	sum := 0.0
	for i := 0; i < period; i++ {
		sum += values[i]
	}
	res[period-1] = sum / float64(period)
	for i := period; i < n; i++ {
		sum += values[i] - values[i-period]
		res[i] = sum / float64(period)
	}
	return res
}

// CalculateEMA computes the Exponential Moving Average over the specified period.
// Initial EMA at index period-1 is the SMA of the first `period` elements.
// Multiplier k = 2 / (period + 1).
// If period <= 0 or len(values) < period, it returns a zeroed slice of length len(values).
func CalculateEMA(values []float64, period int) []float64 {
	n := len(values)
	res := make([]float64, n)
	if period <= 0 || n < period {
		return res
	}
	k := 2.0 / float64(period+1)
	sum := 0.0
	for i := 0; i < period; i++ {
		sum += values[i]
	}
	res[period-1] = sum / float64(period)
	for i := period; i < n; i++ {
		res[i] = values[i]*k + res[i-1]*(1.0-k)
	}
	return res
}

// CalculateRSI computes the Relative Strength Index using Wilder's smoothing technique.
// If period <= 0 or len(values) <= period, it returns a zeroed slice of length len(values).
func CalculateRSI(values []float64, period int) []float64 {
	n := len(values)
	res := make([]float64, n)
	if period <= 0 || n <= period {
		return res
	}

	gains := 0.0
	losses := 0.0
	for i := 1; i <= period; i++ {
		diff := values[i] - values[i-1]
		if diff > 0 {
			gains += diff
		} else {
			losses -= diff
		}
	}

	avgGain := gains / float64(period)
	avgLoss := losses / float64(period)

	if avgGain+avgLoss == 0 {
		res[period] = 50.0
	} else if avgLoss == 0 {
		res[period] = 100.0
	} else {
		rs := avgGain / avgLoss
		res[period] = 100.0 - (100.0 / (1.0 + rs))
	}

	for i := period + 1; i < n; i++ {
		diff := values[i] - values[i-1]
		gain := 0.0
		loss := 0.0
		if diff > 0 {
			gain = diff
		} else {
			loss = -diff
		}

		avgGain = (avgGain*float64(period-1) + gain) / float64(period)
		avgLoss = (avgLoss*float64(period-1) + loss) / float64(period)

		if avgGain+avgLoss == 0 {
			res[i] = 50.0
		} else if avgLoss == 0 {
			res[i] = 100.0
		} else {
			rs := avgGain / avgLoss
			res[i] = 100.0 - (100.0 / (1.0 + rs))
		}
	}

	return res
}

// CalculateMACD computes the Moving Average Convergence Divergence.
// Returns macdLine, signalLine, and histogram.
// All slices have length equal to len(values).
func CalculateMACD(values []float64, fastPeriod, slowPeriod, signalPeriod int) ([]float64, []float64, []float64) {
	n := len(values)
	macdLine := make([]float64, n)
	signalLine := make([]float64, n)
	histogram := make([]float64, n)

	if fastPeriod <= 0 || slowPeriod <= 0 || signalPeriod <= 0 || n == 0 {
		return macdLine, signalLine, histogram
	}

	// Ensure fastPeriod is less than slowPeriod; if inverted, swap them for consistency
	if fastPeriod > slowPeriod {
		fastPeriod, slowPeriod = slowPeriod, fastPeriod
	}

	if n < slowPeriod {
		return macdLine, signalLine, histogram
	}

	fastEMA := CalculateEMA(values, fastPeriod)
	slowEMA := CalculateEMA(values, slowPeriod)

	slowStart := slowPeriod - 1
	for i := slowStart; i < n; i++ {
		macdLine[i] = fastEMA[i] - slowEMA[i]
	}

	sigStart := slowStart + signalPeriod - 1
	if n <= sigStart {
		return macdLine, signalLine, histogram
	}

	// Initial signal line value is SMA of MACD over [slowStart, sigStart]
	sum := 0.0
	for i := slowStart; i <= sigStart; i++ {
		sum += macdLine[i]
	}
	signalLine[sigStart] = sum / float64(signalPeriod)
	histogram[sigStart] = macdLine[sigStart] - signalLine[sigStart]

	k := 2.0 / float64(signalPeriod+1)
	for i := sigStart + 1; i < n; i++ {
		signalLine[i] = macdLine[i]*k + signalLine[i-1]*(1.0-k)
		histogram[i] = macdLine[i] - signalLine[i]
	}

	return macdLine, signalLine, histogram
}

// CalculateBollingerBands calculates upper band, middle band (SMA), and lower band.
// stdDevMultiplier is typically 2.0.
func CalculateBollingerBands(values []float64, period int, stdDevMultiplier float64) ([]float64, []float64, []float64) {
	n := len(values)
	upper := make([]float64, n)
	middle := make([]float64, n)
	lower := make([]float64, n)

	if period <= 0 || n < period {
		return upper, middle, lower
	}

	middle = CalculateSMA(values, period)

	for i := period - 1; i < n; i++ {
		m := middle[i]
		varSum := 0.0
		for j := i - period + 1; j <= i; j++ {
			diff := values[j] - m
			varSum += diff * diff
		}
		variance := varSum / float64(period)
		stdDev := math.Sqrt(variance)

		upper[i] = m + stdDevMultiplier*stdDev
		lower[i] = m - stdDevMultiplier*stdDev
	}

	return upper, middle, lower
}

// CalculateATR computes Wilder's Average True Range.
// If input slices are of mismatched lengths, period <= 0, or len < period,
// it returns a zeroed slice of length len(highs).
func CalculateATR(highs, lows, closes []float64, period int) []float64 {
	n := len(highs)
	res := make([]float64, n)
	if n == 0 || len(lows) != n || len(closes) != n || period <= 0 || n < period {
		return res
	}

	tr := make([]float64, n)
	tr[0] = highs[0] - lows[0]
	for i := 1; i < n; i++ {
		hl := highs[i] - lows[i]
		hc := math.Abs(highs[i] - closes[i-1])
		lc := math.Abs(lows[i] - closes[i-1])
		currTR := hl
		if hc > currTR {
			currTR = hc
		}
		if lc > currTR {
			currTR = lc
		}
		tr[i] = currTR
	}

	sum := 0.0
	for i := 0; i < period; i++ {
		sum += tr[i]
	}
	res[period-1] = sum / float64(period)

	for i := period; i < n; i++ {
		res[i] = (res[i-1]*float64(period-1) + tr[i]) / float64(period)
	}

	return res
}
