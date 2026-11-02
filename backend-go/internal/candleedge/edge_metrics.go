package candleedge

import (
	"math"
)

// CandleEdgeReport encapsulates statistical edge metrics, active SMC zones, and market regime.
type CandleEdgeReport struct {
	Symbol           string                 `json:"symbol"`
	PatternName      string                 `json:"pattern_name"`
	WinRate1Bar      float64                `json:"win_rate_1bar"`
	WinRate3Bar      float64                `json:"win_rate_3bar"`
	WinRate5Bar      float64                `json:"win_rate_5bar"`
	ProfitFactor     float64                `json:"profit_factor"`
	RiskRewardRatio  float64                `json:"risk_reward_ratio"`
	SampleCount      int                    `json:"sample_count"`
	MarketRegime     string                 `json:"market_regime"` // "TRENDING_BULL", "TRENDING_BEAR", "RANGING"
	ActiveZones      []PriceZone            `json:"active_zones"`
	RecentStructures []MarketStructurePoint `json:"recent_structures"`
}

// detectPatternName identifies common candlestick formations on the latest closed bars.
func detectPatternName(candles []Candle) (string, bool) {
	n := len(candles)
	if n < 2 {
		return "Unknown", true
	}

	last := candles[n-1]
	prev := candles[n-2]

	rng := last.High - last.Low
	if rng <= 0 {
		return "Neutral", true
	}

	body := math.Abs(last.Close - last.Open)
	upperWick := last.High - math.Max(last.Close, last.Open)
	lowerWick := math.Min(last.Close, last.Open) - last.Low

	// Bullish / Bearish Engulfing
	if prev.Close < prev.Open && last.Close > last.Open && last.Close >= prev.Open && last.Open <= prev.Close {
		return "Bullish Engulfing", true
	}
	if prev.Close > prev.Open && last.Close < last.Open && last.Close <= prev.Open && last.Open >= prev.Close {
		return "Bearish Engulfing", false
	}

	// Hammer / Inverted Hammer / Shooting Star
	if lowerWick >= 2*body && upperWick <= 0.25*rng && body > 0 {
		return "Hammer", true
	}
	if upperWick >= 2*body && lowerWick <= 0.25*rng && body > 0 {
		return "Shooting Star", false
	}

	// Pinbar
	if lowerWick >= 0.6*rng && upperWick <= 0.2*rng {
		return "Bullish Pinbar", true
	}
	if upperWick >= 0.6*rng && lowerWick <= 0.2*rng {
		return "Bearish Pinbar", false
	}

	// Inside Bar
	if last.High <= prev.High && last.Low >= prev.Low {
		return "Inside Bar", last.Close >= last.Open
	}

	if last.Close >= last.Open {
		return "Bullish Momentum", true
	}
	return "Bearish Momentum", false
}

// ComputeEdgeMetrics evaluates historical forward statistical edge over 1, 3, and 5 bars.
// Zero-divide protected, pure Go.
func ComputeEdgeMetrics(candles []Candle, swingPeriod int) CandleEdgeReport {
	n := len(candles)
	if n < 3 {
		return CandleEdgeReport{
			MarketRegime:     "RANGING",
			ActiveZones:      []PriceZone{},
			RecentStructures: []MarketStructurePoint{},
		}
	}

	patternName, isBullishPattern := detectPatternName(candles)

	// Evaluate forward win rate over 1, 3, 5 bars
	var wins1, wins3, wins5 int
	var sampleCount int
	var totalGains, totalLosses float64
	var gainCount, lossCount int

	// Loop over historical bars having at least 5 bars ahead
	maxEvalIndex := n - 6
	if maxEvalIndex < 1 {
		maxEvalIndex = n - 2
	}

	for j := 1; j <= maxEvalIndex; j++ {
		// Filter historical setups with matching directional bias
		c := candles[j]
		isBullishCandle := c.Close >= c.Open

		if isBullishCandle == isBullishPattern {
			sampleCount++

			// 1-bar forward evaluation
			var ret1 float64
			if isBullishPattern {
				ret1 = (candles[j+1].Close - c.Close) / c.Close
			} else {
				ret1 = (c.Close - candles[j+1].Close) / c.Close
			}
			if ret1 > 0 {
				wins1++
				totalGains += ret1
				gainCount++
			} else if ret1 < 0 {
				totalLosses += -ret1
				lossCount++
			}

			// 3-bar forward evaluation
			if j+3 < n {
				var ret3 float64
				if isBullishPattern {
					ret3 = (candles[j+3].Close - c.Close) / c.Close
				} else {
					ret3 = (c.Close - candles[j+3].Close) / c.Close
				}
				if ret3 > 0 {
					wins3++
				}
			}

			// 5-bar forward evaluation
			if j+5 < n {
				var ret5 float64
				if isBullishPattern {
					ret5 = (candles[j+5].Close - c.Close) / c.Close
				} else {
					ret5 = (c.Close - candles[j+5].Close) / c.Close
				}
				if ret5 > 0 {
					wins5++
				}
			}
		}
	}

	var winRate1, winRate3, winRate5 float64
	if sampleCount > 0 {
		winRate1 = (float64(wins1) / float64(sampleCount)) * 100.0
		winRate3 = (float64(wins3) / float64(sampleCount)) * 100.0
		winRate5 = (float64(wins5) / float64(sampleCount)) * 100.0
	}

	var profitFactor float64
	if totalLosses > 0 {
		profitFactor = totalGains / totalLosses
	} else if totalGains > 0 {
		profitFactor = totalGains * 100.0 // capped positive edge
	}

	var riskRewardRatio float64
	if gainCount > 0 && lossCount > 0 {
		avgGain := totalGains / float64(gainCount)
		avgLoss := totalLosses / float64(lossCount)
		if avgLoss > 0 {
			riskRewardRatio = avgGain / avgLoss
		}
	} else if gainCount > 0 {
		riskRewardRatio = 1.0
	}

	// Detect Market Structure and determine Regime
	structures := DetectMarketStructure(candles, swingPeriod)
	bullishStructures := 0
	bearishStructures := 0
	for _, s := range structures {
		if s.IsBullish {
			bullishStructures++
		} else {
			bearishStructures++
		}
	}

	marketRegime := "RANGING"
	if bullishStructures > bearishStructures {
		marketRegime = "TRENDING_BULL"
	} else if bearishStructures > bullishStructures {
		marketRegime = "TRENDING_BEAR"
	}

	// Calculate active SMC zones (unmitigated FVG and Order Blocks)
	fvgMinGap := 0.001 * candles[n-1].Close
	fvgZones := DetectFairValueGaps(candles, fvgMinGap)
	obZones := DetectOrderBlocks(candles, 0.005*candles[n-1].Close)

	var activeZones []PriceZone
	for _, z := range fvgZones {
		if !z.Mitigated {
			activeZones = append(activeZones, z)
		}
	}
	for _, z := range obZones {
		if !z.Mitigated {
			activeZones = append(activeZones, z)
		}
	}

	// Keep recent structures (last 10)
	var recentStructures []MarketStructurePoint
	if len(structures) > 10 {
		recentStructures = structures[len(structures)-10:]
	} else {
		recentStructures = structures
	}

	if activeZones == nil {
		activeZones = []PriceZone{}
	}
	if recentStructures == nil {
		recentStructures = []MarketStructurePoint{}
	}

	return CandleEdgeReport{
		PatternName:      patternName,
		WinRate1Bar:      winRate1,
		WinRate3Bar:      winRate3,
		WinRate5Bar:      winRate5,
		ProfitFactor:     profitFactor,
		RiskRewardRatio:  riskRewardRatio,
		SampleCount:      sampleCount,
		MarketRegime:     marketRegime,
		ActiveZones:      activeZones,
		RecentStructures: recentStructures,
	}
}
