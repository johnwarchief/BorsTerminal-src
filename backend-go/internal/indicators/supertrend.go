package indicators

import (
	"math"
)

// CalculateSuperTrend computes the SuperTrend indicator and trend direction.
// Direction: 1 for Bullish (price above lower band), -1 for Bearish (price below upper band), 0 for uninitialized.
// In uptrend, supertrend line is the final lower band.
// In downtrend, supertrend line is the final upper band.
func CalculateSuperTrend(highs, lows, closes []float64, period int, multiplier float64) ([]float64, []int) {
	n := len(highs)
	supertrend := make([]float64, n)
	direction := make([]int, n)

	if n == 0 || len(lows) != n || len(closes) != n || period <= 0 || multiplier <= 0 || n < period {
		return supertrend, direction
	}

	atr := CalculateATR(highs, lows, closes, period)

	basicUpper := make([]float64, n)
	basicLower := make([]float64, n)
	finalUpper := make([]float64, n)
	finalLower := make([]float64, n)

	initIdx := period - 1
	hl2 := (highs[initIdx] + lows[initIdx]) / 2.0
	basicUpper[initIdx] = hl2 + multiplier*atr[initIdx]
	basicLower[initIdx] = hl2 - multiplier*atr[initIdx]
	finalUpper[initIdx] = basicUpper[initIdx]
	finalLower[initIdx] = basicLower[initIdx]

	if closes[initIdx] > finalUpper[initIdx] {
		direction[initIdx] = 1
		supertrend[initIdx] = finalLower[initIdx]
	} else if closes[initIdx] < finalLower[initIdx] {
		direction[initIdx] = -1
		supertrend[initIdx] = finalUpper[initIdx]
	} else if closes[initIdx] >= hl2 {
		direction[initIdx] = 1
		supertrend[initIdx] = finalLower[initIdx]
	} else {
		direction[initIdx] = -1
		supertrend[initIdx] = finalUpper[initIdx]
	}

	for i := period; i < n; i++ {
		hl2 = (highs[i] + lows[i]) / 2.0
		basicUpper[i] = hl2 + multiplier*atr[i]
		basicLower[i] = hl2 - multiplier*atr[i]

		// Final Lower Band:
		if basicLower[i] > finalLower[i-1] || closes[i-1] < finalLower[i-1] {
			finalLower[i] = basicLower[i]
		} else {
			finalLower[i] = finalLower[i-1]
		}

		// Final Upper Band:
		if basicUpper[i] < finalUpper[i-1] || closes[i-1] > finalUpper[i-1] {
			finalUpper[i] = basicUpper[i]
		} else {
			finalUpper[i] = finalUpper[i-1]
		}

		// Direction and SuperTrend
		if direction[i-1] == 1 {
			if closes[i] < finalLower[i] {
				direction[i] = -1
				supertrend[i] = finalUpper[i]
			} else {
				direction[i] = 1
				supertrend[i] = finalLower[i]
			}
		} else {
			if closes[i] > finalUpper[i] {
				direction[i] = 1
				supertrend[i] = finalLower[i]
			} else {
				direction[i] = -1
				supertrend[i] = finalUpper[i]
			}
		}
	}

	return supertrend, direction
}

// HeikinAshiCandles calculates synthetic Heikin-Ashi candlestick values.
// haClose = (Open + High + Low + Close) / 4
// haOpen = (haOpen_prev + haClose_prev) / 2 (or (Open + Close) / 2 for initial candle)
// haHigh = max(High, haOpen, haClose)
// haLow = min(Low, haOpen, haClose)
func HeikinAshiCandles(opens, highs, lows, closes []float64) ([]float64, []float64, []float64, []float64) {
	n := len(opens)
	haOpen := make([]float64, n)
	haHigh := make([]float64, n)
	haLow := make([]float64, n)
	haClose := make([]float64, n)

	if n == 0 || len(highs) != n || len(lows) != n || len(closes) != n {
		return haOpen, haHigh, haLow, haClose
	}

	haClose[0] = (opens[0] + highs[0] + lows[0] + closes[0]) / 4.0
	haOpen[0] = (opens[0] + closes[0]) / 2.0
	haHigh[0] = highs[0]
	haLow[0] = lows[0]

	for i := 1; i < n; i++ {
		haClose[i] = (opens[i] + highs[i] + lows[i] + closes[i]) / 4.0
		haOpen[i] = (haOpen[i-1] + haClose[i-1]) / 2.0
		haHigh[i] = math.Max(highs[i], math.Max(haOpen[i], haClose[i]))
		haLow[i] = math.Min(lows[i], math.Min(haOpen[i], haClose[i]))
	}

	return haOpen, haHigh, haLow, haClose
}
