package candleedge_test

import (
	"math"
	"testing"

	"borsterminal/backend/internal/candleedge"
)

func floatNear(a, b, epsilon float64) bool {
	return math.Abs(a-b) <= epsilon
}

func TestDetectFairValueGaps_Bullish(t *testing.T) {
	// Candle 0: H=100, L=90
	// Candle 1: Big impulsive green: H=120, L=98
	// Candle 2: H=130, L=105 -> Gap between L(2)=105 and H(0)=100 is 5
	candles := []candleedge.Candle{
		{Timestamp: 1000, Open: 92, High: 100, Low: 90, Close: 98, Volume: 1000},
		{Timestamp: 2000, Open: 99, High: 120, Low: 98, Close: 118, Volume: 5000},
		{Timestamp: 3000, Open: 106, High: 130, Low: 105, Close: 125, Volume: 2000},
	}
	zones := candleedge.DetectFairValueGaps(candles, 1.0)
	if len(zones) != 1 {
		t.Fatalf("expected 1 zone, got %d", len(zones))
	}
	z := zones[0]
	if !z.IsBullish {
		t.Errorf("expected bullish zone")
	}
	if z.Type != candleedge.ZoneFVG {
		t.Errorf("expected type FVG, got %s", z.Type)
	}
	if !floatNear(z.Top, 105.0, 1e-6) {
		t.Errorf("expected top 105, got %f", z.Top)
	}
	if !floatNear(z.Bottom, 100.0, 1e-6) {
		t.Errorf("expected bottom 100, got %f", z.Bottom)
	}
	if !floatNear(z.Equilibrium, 102.5, 1e-6) {
		t.Errorf("expected equilibrium 102.5, got %f", z.Equilibrium)
	}
	if z.Mitigated {
		t.Errorf("expected unmitigated zone")
	}
}

func TestDetectFairValueGaps_BearishAndMitigation(t *testing.T) {
	// Bearish FVG:
	// Candle 0: H=120, L=110
	// Candle 1: Big red drop: H=112, L=90
	// Candle 2: H=98, L=85 -> Gap between L(0)=110 and H(2)=98 is 12 (Top=110, Bottom=98, Eq=104)
	// Candle 3: Retest: H=105, L=95 -> Reaches 105 >= Eq(104), so mitigated!
	candles := []candleedge.Candle{
		{Timestamp: 1000, Open: 115, High: 120, Low: 110, Close: 112, Volume: 1000},
		{Timestamp: 2000, Open: 111, High: 112, Low: 90, Close: 92, Volume: 6000},
		{Timestamp: 3000, Open: 91, High: 98, Low: 85, Close: 88, Volume: 2000},
		{Timestamp: 4000, Open: 89, High: 105, Low: 95, Close: 101, Volume: 3000},
	}
	zones := candleedge.DetectFairValueGaps(candles, 2.0)
	if len(zones) != 1 {
		t.Fatalf("expected 1 bearish zone, got %d", len(zones))
	}
	z := zones[0]
	if z.IsBullish {
		t.Errorf("expected bearish zone")
	}
	if !floatNear(z.Top, 110.0, 1e-6) {
		t.Errorf("expected top 110, got %f", z.Top)
	}
	if !floatNear(z.Bottom, 98.0, 1e-6) {
		t.Errorf("expected bottom 98, got %f", z.Bottom)
	}
	if !floatNear(z.Equilibrium, 104.0, 1e-6) {
		t.Errorf("expected equilibrium 104, got %f", z.Equilibrium)
	}
	if !z.Mitigated {
		t.Errorf("expected zone to be mitigated by candle 3")
	}
	if z.MitigatedTs != 4000 {
		t.Errorf("expected mitigated timestamp 4000, got %d", z.MitigatedTs)
	}
}

func TestDetectFairValueGaps_EdgeCases(t *testing.T) {
	// Empty or < 3 candles
	emptyZones := candleedge.DetectFairValueGaps(nil, 1.0)
	if len(emptyZones) != 0 {
		t.Errorf("expected 0 zones for nil slice")
	}
	twoCandles := []candleedge.Candle{
		{Timestamp: 100, Open: 10, High: 12, Low: 9, Close: 11},
		{Timestamp: 200, Open: 11, High: 13, Low: 10, Close: 12},
	}
	if len(candleedge.DetectFairValueGaps(twoCandles, 1.0)) != 0 {
		t.Errorf("expected 0 zones for 2 candles")
	}
}

func TestDetectMarketStructure_BOS_CHoCH(t *testing.T) {
	// Create a sequence that forms:
	// 1. Swing High at candle 2 (H=120)
	// 2. Swing Low at candle 4 (L=95)
	// 3. Candle 6 breaks above Swing High (C=125 > 120) -> Bullish BOS
	// 4. Candle 8 forms a higher swing high (H=140)
	// 5. Candle 10 forms a higher swing low (L=115)
	// 6. Candle 12 crashes below Swing Low 115 (C=110 < 115) -> Bearish CHoCH (trend reversal from bull to bear)
	candles := []candleedge.Candle{
		{Timestamp: 1000, Open: 100, High: 105, Low: 98, Close: 103},   // 0
		{Timestamp: 2000, Open: 103, High: 112, Low: 101, Close: 110},  // 1
		{Timestamp: 3000, Open: 110, High: 120, Low: 108, Close: 115},  // 2: Swing High
		{Timestamp: 4000, Open: 114, High: 116, Low: 102, Close: 104},  // 3
		{Timestamp: 5000, Open: 104, High: 106, Low: 95, Close: 97},    // 4: Swing Low
		{Timestamp: 6000, Open: 97, High: 110, Low: 96, Close: 108},    // 5
		{Timestamp: 7000, Open: 109, High: 128, Low: 108, Close: 125},  // 6: Break above 120 -> BOS
		{Timestamp: 8000, Open: 125, High: 135, Low: 124, Close: 132},  // 7
		{Timestamp: 9000, Open: 132, High: 140, Low: 130, Close: 138},  // 8: Swing High
		{Timestamp: 10000, Open: 137, High: 138, Low: 120, Close: 122}, // 9
		{Timestamp: 11000, Open: 122, High: 124, Low: 115, Close: 118}, // 10: Swing Low
		{Timestamp: 12000, Open: 118, High: 122, Low: 118, Close: 120}, // 11
		{Timestamp: 13000, Open: 120, High: 123, Low: 117, Close: 121}, // 12: Confirms candle 10 swing low
		{Timestamp: 14000, Open: 120, High: 121, Low: 108, Close: 110}, // 13: Break below 115 -> CHoCH
	}

	points := candleedge.DetectMarketStructure(candles, 2)
	if len(points) == 0 {
		t.Fatalf("expected market structure points, got none")
	}

	var foundBOS, foundCHoCH bool
	for _, p := range points {
		if p.Type == candleedge.StructureBOS && p.IsBullish {
			foundBOS = true
			if p.Price <= 0 {
				t.Errorf("expected positive price on BOS")
			}
		}
		if p.Type == candleedge.StructureCHoCH && !p.IsBullish {
			foundCHoCH = true
		}
	}

	if !foundBOS {
		t.Errorf("expected to detect bullish BOS")
	}
	if !foundCHoCH {
		t.Errorf("expected to detect bearish CHoCH")
	}
}

func TestDetectOrderBlocks(t *testing.T) {
	// Bullish Order Block:
	// A bearish candle before an explosive move upwards that breaks structure or has significant displacement
	candles := []candleedge.Candle{
		{Timestamp: 1000, Open: 100, High: 102, Low: 98, Close: 101},
		{Timestamp: 2000, Open: 101, High: 103, Low: 99, Close: 102},
		// Bearish OB candle:
		{Timestamp: 3000, Open: 102, High: 103, Low: 96, Close: 97}, // red candle
		// Impulsive bullish moves:
		{Timestamp: 4000, Open: 98, High: 112, Low: 98, Close: 110},
		{Timestamp: 5000, Open: 111, High: 125, Low: 110, Close: 123},
		// Retest / mitigation:
		{Timestamp: 6000, Open: 120, High: 121, Low: 101, Close: 105}, // enters OB zone (Top: 103, Bottom: 96)
	}

	obs := candleedge.DetectOrderBlocks(candles, 10.0)
	if len(obs) == 0 {
		t.Fatalf("expected at least 1 order block")
	}

	ob := obs[0]
	if ob.Type != candleedge.ZoneOrderBlock {
		t.Errorf("expected ZoneOrderBlock, got %s", ob.Type)
	}
	if !ob.IsBullish {
		t.Errorf("expected bullish order block")
	}
	if !floatNear(ob.Top, 103.0, 1e-6) {
		t.Errorf("expected top 103, got %f", ob.Top)
	}
	if !floatNear(ob.Bottom, 96.0, 1e-6) {
		t.Errorf("expected bottom 96, got %f", ob.Bottom)
	}
	if !ob.Mitigated {
		t.Errorf("expected order block to be mitigated by retest candle")
	}
}

func TestComputeEdgeMetrics_EdgeCases(t *testing.T) {
	// Empty slice
	rep := candleedge.ComputeEdgeMetrics([]candleedge.Candle{}, 2)
	if rep.SampleCount != 0 {
		t.Errorf("expected 0 samples for empty candles")
	}
	if rep.WinRate1Bar != 0.0 || rep.ProfitFactor != 0.0 {
		t.Errorf("expected zero win rate and profit factor")
	}

	// Short series (< 3 candles)
	shortCandles := []candleedge.Candle{
		{Timestamp: 100, Open: 10, High: 11, Low: 9, Close: 10.5},
	}
	repShort := candleedge.ComputeEdgeMetrics(shortCandles, 2)
	if repShort.SampleCount != 0 {
		t.Errorf("expected 0 samples for 1 candle")
	}
}

func TestComputeEdgeMetrics_ValidData(t *testing.T) {
	// 30 candles in general uptrend with typical pullbacks
	n := 30
	candles := make([]candleedge.Candle, n)
	for i := 0; i < n; i++ {
		base := 100.0 + float64(i)*2.0
		// introduce occasional pullback
		if i%5 == 0 {
			base -= 3.0
		}
		candles[i] = candleedge.Candle{
			Timestamp: int64(1000 + i*100),
			Open:      base,
			High:      base + 3.0,
			Low:       base - 1.0,
			Close:     base + 2.0,
			Volume:    10000 + float64(i)*100,
		}
	}

	rep := candleedge.ComputeEdgeMetrics(candles, 2)
	if rep.SampleCount <= 0 {
		t.Errorf("expected sample count > 0, got %d", rep.SampleCount)
	}
	if rep.WinRate1Bar < 0.0 || rep.WinRate1Bar > 100.0 {
		t.Errorf("expected WinRate1Bar in [0, 100], got %f", rep.WinRate1Bar)
	}
	if rep.MarketRegime == "" {
		t.Errorf("expected non-empty market regime")
	}
	if rep.ProfitFactor < 0.0 {
		t.Errorf("profit factor should be non-negative")
	}
}

func TestDetectOrderBlocks_Bearish(t *testing.T) {
	// Bearish Order Block:
	// A bullish candle before an impulsive drop
	candles := []candleedge.Candle{
		{Timestamp: 1000, Open: 100, High: 102, Low: 98, Close: 99},
		{Timestamp: 2000, Open: 99, High: 101, Low: 98, Close: 100},
		// Bullish OB candle:
		{Timestamp: 3000, Open: 100, High: 106, Low: 99, Close: 105}, // green candle
		// Impulsive bearish drops:
		{Timestamp: 4000, Open: 104, High: 104, Low: 90, Close: 91}, // drops below 99
		{Timestamp: 5000, Open: 91, High: 92, Low: 80, Close: 82},
		// Retest / mitigation:
		{Timestamp: 6000, Open: 85, High: 100, Low: 84, Close: 95}, // High 100 >= Bottom 99 -> mitigated!
	}

	obs := candleedge.DetectOrderBlocks(candles, 10.0)
	if len(obs) == 0 {
		t.Fatalf("expected at least 1 bearish order block")
	}

	var foundBearish bool
	for _, ob := range obs {
		if !ob.IsBullish && ob.Type == candleedge.ZoneOrderBlock {
			foundBearish = true
			if !floatNear(ob.Top, 106.0, 1e-6) {
				t.Errorf("expected top 106, got %f", ob.Top)
			}
			if !floatNear(ob.Bottom, 99.0, 1e-6) {
				t.Errorf("expected bottom 99, got %f", ob.Bottom)
			}
			if !ob.Mitigated {
				t.Errorf("expected bearish order block to be mitigated by candle 5")
			}
		}
	}
	if !foundBearish {
		t.Errorf("expected to find bearish order block")
	}
}

func TestComputeEdgeMetrics_Patterns(t *testing.T) {
	// Test Hammer pattern
	candlesHammer := []candleedge.Candle{
		{Timestamp: 1000, Open: 100, High: 102, Low: 98, Close: 100},
		{Timestamp: 2000, Open: 100, High: 102, Low: 98, Close: 100},
		{Timestamp: 3000, Open: 95, High: 96, Low: 80, Close: 95.5}, // long lower wick (15), body 0.5, small upper wick 0.5
	}
	rep := candleedge.ComputeEdgeMetrics(candlesHammer, 2)
	if rep.PatternName != "Hammer" {
		t.Errorf("expected Hammer, got %s", rep.PatternName)
	}

	// Test Bullish Engulfing
	candlesEngulf := []candleedge.Candle{
		{Timestamp: 1000, Open: 100, High: 102, Low: 98, Close: 100},
		{Timestamp: 2000, Open: 100, High: 101, Low: 92, Close: 93}, // red candle (body 7)
		{Timestamp: 3000, Open: 92, High: 103, Low: 91, Close: 102}, // green engulfing (body 10)
	}
	repEngulf := candleedge.ComputeEdgeMetrics(candlesEngulf, 2)
	if repEngulf.PatternName != "Bullish Engulfing" {
		t.Errorf("expected Bullish Engulfing, got %s", repEngulf.PatternName)
	}
}

