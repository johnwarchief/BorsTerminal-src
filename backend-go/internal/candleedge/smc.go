package candleedge

import (
	"fmt"
)

// ZoneType defines the classification of a Smart Money price zone.
type ZoneType string

const (
	ZoneFVG        ZoneType = "FVG"
	ZoneOrderBlock ZoneType = "ORDER_BLOCK"
)

// MarketStructureType defines structural breaks in price action.
type MarketStructureType string

const (
	StructureBOS   MarketStructureType = "BOS"   // Break of Structure (trend continuation)
	StructureCHoCH MarketStructureType = "CHoCH" // Change of Character (trend reversal)
)

// Candle represents an OHLCV bar.
type Candle struct {
	Timestamp int64   `json:"timestamp"`
	Open      float64 `json:"open"`
	High      float64 `json:"high"`
	Low       float64 `json:"low"`
	Close     float64 `json:"close"`
	Volume    float64 `json:"volume"`
}

// PriceZone represents an institutional order block or fair value gap.
type PriceZone struct {
	ID          string   `json:"id"`
	Type        ZoneType `json:"type"`
	IsBullish   bool     `json:"is_bullish"`
	Top         float64  `json:"top"`
	Bottom      float64  `json:"bottom"`
	Equilibrium float64  `json:"equilibrium"`
	StartIndex  int      `json:"start_index"`
	StartTs     int64    `json:"start_ts"`
	Mitigated   bool     `json:"mitigated"`
	MitigatedTs int64    `json:"mitigated_ts,omitempty"`
}

// MarketStructurePoint represents a detected BOS or CHoCH point.
type MarketStructurePoint struct {
	Type      MarketStructureType `json:"type"`
	IsBullish bool                `json:"is_bullish"`
	Price     float64             `json:"price"`
	Timestamp int64               `json:"timestamp"`
	Index     int                 `json:"index,omitempty"`
}

// DetectFairValueGaps identifies 3-candle imbalance zones (FVG).
// Bullish FVG: Low[i+1] > High[i-1] with gap >= minGap.
// Bearish FVG: High[i+1] < Low[i-1] with gap >= minGap.
// Equilibrium: 50% midpoint of the imbalance zone.
// Auto-mitigation: Subsequent price crossing the 50% equilibrium level.
func DetectFairValueGaps(candles []Candle, minGap float64) []PriceZone {
	n := len(candles)
	if n < 3 {
		return []PriceZone{}
	}

	var zones []PriceZone
	for i := 1; i < n-1; i++ {
		// Bullish FVG: Gap between candle i-1 High and candle i+1 Low
		if candles[i+1].Low > candles[i-1].High {
			gap := candles[i+1].Low - candles[i-1].High
			if gap >= minGap {
				top := candles[i+1].Low
				bottom := candles[i-1].High
				eq := (top + bottom) / 2.0
				z := PriceZone{
					ID:          fmt.Sprintf("fvg-bull-%d", i),
					Type:        ZoneFVG,
					IsBullish:   true,
					Top:         top,
					Bottom:      bottom,
					Equilibrium: eq,
					StartIndex:  i,
					StartTs:     candles[i].Timestamp,
					Mitigated:   false,
				}

				// Check auto-mitigation by subsequent candles
				for k := i + 2; k < n; k++ {
					if candles[k].Low <= eq {
						z.Mitigated = true
						z.MitigatedTs = candles[k].Timestamp
						break
					}
				}
				zones = append(zones, z)
			}
		}

		// Bearish FVG: Gap between candle i-1 Low and candle i+1 High
		if candles[i+1].High < candles[i-1].Low {
			gap := candles[i-1].Low - candles[i+1].High
			if gap >= minGap {
				top := candles[i-1].Low
				bottom := candles[i+1].High
				eq := (top + bottom) / 2.0
				z := PriceZone{
					ID:          fmt.Sprintf("fvg-bear-%d", i),
					Type:        ZoneFVG,
					IsBullish:   false,
					Top:         top,
					Bottom:      bottom,
					Equilibrium: eq,
					StartIndex:  i,
					StartTs:     candles[i].Timestamp,
					Mitigated:   false,
				}

				// Check auto-mitigation by subsequent candles
				for k := i + 2; k < n; k++ {
					if candles[k].High >= eq {
						z.Mitigated = true
						z.MitigatedTs = candles[k].Timestamp
						break
					}
				}
				zones = append(zones, z)
			}
		}
	}

	return zones
}

// DetectOrderBlocks detects bullish and bearish order blocks created prior to an impulsive displacement.
// Bullish OB: Last down-close candle before an impulsive rally.
// Bearish OB: Last up-close candle before an impulsive drop.
// Auto-mitigation: Retesting of the order block zone by subsequent candles.
func DetectOrderBlocks(candles []Candle, minDisplacement float64) []PriceZone {
	n := len(candles)
	if n < 3 {
		return []PriceZone{}
	}

	if minDisplacement <= 0 {
		minDisplacement = 0.001
	}

	var zones []PriceZone
	for i := 0; i < n-1; i++ {
		// Bullish Order Block candidate: candle i is the last bearish candle (Close <= Open)
		// immediately before an impulsive bullish move starting at i+1
		if candles[i].Close <= candles[i].Open && candles[i+1].Close > candles[i+1].Open {
			impulsive := false
			maxForwardIdx := i + 3
			if maxForwardIdx >= n {
				maxForwardIdx = n - 1
			}

			var impulseEndIdx int
			for m := i + 1; m <= maxForwardIdx; m++ {
				move := candles[m].High - candles[i].Low
				if move >= minDisplacement && candles[m].Close > candles[i].High {
					impulsive = true
					impulseEndIdx = m
					break
				}
			}

			if impulsive {
				top := candles[i].High
				bottom := candles[i].Low
				eq := (top + bottom) / 2.0
				z := PriceZone{
					ID:          fmt.Sprintf("ob-bull-%d", i),
					Type:        ZoneOrderBlock,
					IsBullish:   true,
					Top:         top,
					Bottom:      bottom,
					Equilibrium: eq,
					StartIndex:  i,
					StartTs:     candles[i].Timestamp,
					Mitigated:   false,
				}

				// Check retest / mitigation by subsequent candles
				for k := impulseEndIdx + 1; k < n; k++ {
					if candles[k].Low <= top {
						z.Mitigated = true
						z.MitigatedTs = candles[k].Timestamp
						break
					}
				}
				zones = append(zones, z)
			}
		}

		// Bearish Order Block candidate: candle i is the last bullish candle (Close >= Open)
		// immediately before an impulsive bearish move starting at i+1
		if candles[i].Close >= candles[i].Open && candles[i+1].Close < candles[i+1].Open {
			impulsive := false
			maxForwardIdx := i + 3
			if maxForwardIdx >= n {
				maxForwardIdx = n - 1
			}

			var impulseEndIdx int
			for m := i + 1; m <= maxForwardIdx; m++ {
				move := candles[i].High - candles[m].Low
				if move >= minDisplacement && candles[m].Close < candles[i].Low {
					impulsive = true
					impulseEndIdx = m
					break
				}
			}

			if impulsive {
				top := candles[i].High
				bottom := candles[i].Low
				eq := (top + bottom) / 2.0
				z := PriceZone{
					ID:          fmt.Sprintf("ob-bear-%d", i),
					Type:        ZoneOrderBlock,
					IsBullish:   false,
					Top:         top,
					Bottom:      bottom,
					Equilibrium: eq,
					StartIndex:  i,
					StartTs:     candles[i].Timestamp,
					Mitigated:   false,
				}

				// Check retest / mitigation by subsequent candles
				for k := impulseEndIdx + 1; k < n; k++ {
					if candles[k].High >= bottom {
						z.Mitigated = true
						z.MitigatedTs = candles[k].Timestamp
						break
					}
				}
				zones = append(zones, z)
			}
		}
	}

	return zones
}

type swingPoint struct {
	index     int
	price     float64
	timestamp int64
	isHigh    bool
}

// DetectMarketStructure detects swing points, Break of Structure (BOS) and Change of Character (CHoCH).
// BOS: Trend continuation break (breaking swing high in uptrend or swing low in downtrend).
// CHoCH: Trend reversal break (breaking swing high in downtrend or swing low in uptrend).
func DetectMarketStructure(candles []Candle, swingPeriod int) []MarketStructurePoint {
	n := len(candles)
	if n < 3 {
		return []MarketStructurePoint{}
	}
	if swingPeriod < 1 {
		swingPeriod = 2
	}

	// 1. Identify confirmed swing highs and lows
	isSwingHigh := make([]bool, n)
	isSwingLow := make([]bool, n)

	for i := swingPeriod; i < n-swingPeriod; i++ {
		high := candles[i].High
		low := candles[i].Low

		sh := true
		sl := true

		for k := 1; k <= swingPeriod; k++ {
			if candles[i-k].High > high || candles[i+k].High >= high {
				sh = false
			}
			if candles[i-k].Low < low || candles[i+k].Low <= low {
				sl = false
			}
		}

		if sh {
			isSwingHigh[i] = true
		}
		if sl {
			isSwingLow[i] = true
		}
	}

	// 2. Track structure progression
	var points []MarketStructurePoint
	var lastHigh *swingPoint
	var lastLow *swingPoint
	lastHighBroken := false
	lastLowBroken := false
	trend := 0 // 0 = undefined, 1 = bull, -1 = bear

	for j := 0; j < n; j++ {
		// Check if a swing point at (j - swingPeriod) is confirmed
		confIdx := j - swingPeriod
		if confIdx >= 0 {
			if isSwingHigh[confIdx] {
				lastHigh = &swingPoint{
					index:     confIdx,
					price:     candles[confIdx].High,
					timestamp: candles[confIdx].Timestamp,
					isHigh:    true,
				}
				lastHighBroken = false
			}
			if isSwingLow[confIdx] {
				lastLow = &swingPoint{
					index:     confIdx,
					price:     candles[confIdx].Low,
					timestamp: candles[confIdx].Timestamp,
					isHigh:    false,
				}
				lastLowBroken = false
			}
		}

		// Check structural break above last confirmed swing high
		if lastHigh != nil && !lastHighBroken && candles[j].Close > lastHigh.price {
			lastHighBroken = true
			if trend == -1 {
				// CHoCH: Downtrend reversed to uptrend
				points = append(points, MarketStructurePoint{
					Type:      StructureCHoCH,
					IsBullish: true,
					Price:     candles[j].Close,
					Timestamp: candles[j].Timestamp,
					Index:     j,
				})
				trend = 1
			} else {
				// BOS: Uptrend continuation or initial break
				points = append(points, MarketStructurePoint{
					Type:      StructureBOS,
					IsBullish: true,
					Price:     candles[j].Close,
					Timestamp: candles[j].Timestamp,
					Index:     j,
				})
				trend = 1
			}
		}

		// Check structural break below last confirmed swing low
		if lastLow != nil && !lastLowBroken && candles[j].Close < lastLow.price {
			lastLowBroken = true
			if trend == 1 {
				// CHoCH: Uptrend reversed to downtrend
				points = append(points, MarketStructurePoint{
					Type:      StructureCHoCH,
					IsBullish: false,
					Price:     candles[j].Close,
					Timestamp: candles[j].Timestamp,
					Index:     j,
				})
				trend = -1
			} else {
				// BOS: Downtrend continuation or initial break
				points = append(points, MarketStructurePoint{
					Type:      StructureBOS,
					IsBullish: false,
					Price:     candles[j].Close,
					Timestamp: candles[j].Timestamp,
					Index:     j,
				})
				trend = -1
			}
		}
	}

	return points
}
