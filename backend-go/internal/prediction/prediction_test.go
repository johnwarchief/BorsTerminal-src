package prediction_test

import (
	"math"
	"testing"
	"time"

	"borsterminal/backend/internal/prediction"
)

func makeDummyCandles(count int, startPrice, trend float64) ([]float64, []int64) {
	closes := make([]float64, count)
	timestamps := make([]int64, count)
	baseTime := time.Date(2026, 1, 1, 9, 0, 0, 0, time.UTC).Unix()

	price := startPrice
	for i := 0; i < count; i++ {
		// Small deterministic oscillation + trend
		noise := math.Sin(float64(i)*0.2) * (startPrice * 0.01)
		price = price + trend + noise
		if price <= 1.0 {
			price = 1.0
		}
		closes[i] = price
		timestamps[i] = baseTime + int64(i*86400)
	}
	return closes, timestamps
}

func TestPredictHorizon_IlliquidGuard(t *testing.T) {
	closes, timestamps := makeDummyCandles(100, 1000.0, 2.0)
	// Avg value 2B Tomans (< 5B threshold)
	resp := prediction.PredictHorizon("TEST", closes, timestamps, 2_000_000_000.0, 12)

	if resp.IsLiquid {
		t.Fatalf("expected IsLiquid=false for 2B Tomans, got true")
	}
	if len(resp.ForecastSteps) != 0 {
		t.Fatalf("expected 0 forecast steps for illiquid symbol, got %d", len(resp.ForecastSteps))
	}
	expectedNote := "میانگین ارزش معاملات کمتر از ۵ میلیارد تومان است؛ جهت جلوگیری از خطا، پیش‌بینی غیرفعال گردید."
	if resp.LiquidityNote != expectedNote {
		t.Errorf("expected note %q, got %q", expectedNote, resp.LiquidityNote)
	}
	if resp.Symbol != "TEST" {
		t.Errorf("expected symbol TEST, got %s", resp.Symbol)
	}
}

func TestPredictHorizon_LiquidProbabilistic(t *testing.T) {
	closes, timestamps := makeDummyCandles(100, 5000.0, 5.0)
	// Avg value 10B Tomans (> 5B threshold)
	resp := prediction.PredictHorizon("FOOLAD", closes, timestamps, 10_000_000_000.0, 6)

	if !resp.IsLiquid {
		t.Fatalf("expected IsLiquid=true for 10B Tomans, got false")
	}
	if resp.Horizon != 6 {
		t.Errorf("expected Horizon=6, got %d", resp.Horizon)
	}
	if len(resp.ForecastSteps) != 6 {
		t.Fatalf("expected 6 forecast steps, got %d", len(resp.ForecastSteps))
	}
	if resp.HistoricalEnd != timestamps[len(timestamps)-1] {
		t.Errorf("expected HistoricalEnd=%d, got %d", timestamps[len(timestamps)-1], resp.HistoricalEnd)
	}

	for i, step := range resp.ForecastSteps {
		if step.StepIndex != i+1 {
			t.Errorf("expected StepIndex=%d, got %d", i+1, step.StepIndex)
		}
		if step.Timestamp <= resp.HistoricalEnd {
			t.Errorf("expected future timestamp > %d, got %d", resp.HistoricalEnd, step.Timestamp)
		}
		if step.P10 > step.P50 {
			t.Errorf("step %d: P10 (%f) > P50 (%f)", i+1, step.P10, step.P50)
		}
		if step.P50 > step.P90 {
			t.Errorf("step %d: P50 (%f) > P90 (%f)", i+1, step.P50, step.P90)
		}
		if step.P10 <= 0 {
			t.Errorf("step %d: P10 (%f) <= 0", i+1, step.P10)
		}
	}
}

func TestPredictHorizon_UpsideAndVolatilityBounds(t *testing.T) {
	// 1. Moderate trend
	closes, timestamps := makeDummyCandles(100, 2000.0, 1.0)
	resp := prediction.PredictHorizon("KAVEH", closes, timestamps, 8_000_000_000.0, 12)

	if resp.UpsideProbability < 0.0 || resp.UpsideProbability > 1.0 {
		t.Errorf("UpsideProbability out of bounds: %f", resp.UpsideProbability)
	}
	if resp.VolatilityAmplification < 0.0 || resp.VolatilityAmplification > 1.0 {
		t.Errorf("VolatilityAmplification out of bounds: %f", resp.VolatilityAmplification)
	}

	// 2. Strong uptrend: UpsideProbability should be high (>= 0.70)
	upCloses, upTs := makeDummyCandles(100, 1000.0, 30.0)
	upResp := prediction.PredictHorizon("BULL", upCloses, upTs, 15_000_000_000.0, 10)
	if upResp.UpsideProbability < 0.70 {
		t.Errorf("expected high upside probability for strong uptrend, got %f", upResp.UpsideProbability)
	}

	// 3. Strong downtrend: UpsideProbability should be low (<= 0.30)
	downCloses, downTs := makeDummyCandles(100, 5000.0, -30.0)
	downResp := prediction.PredictHorizon("BEAR", downCloses, downTs, 15_000_000_000.0, 10)
	if downResp.UpsideProbability > 0.30 {
		t.Errorf("expected low upside probability for strong downtrend, got %f", downResp.UpsideProbability)
	}
}

func TestPredictHorizon_EdgeCases(t *testing.T) {
	// Edge 1: Empty slices
	respEmpty := prediction.PredictHorizon("EMPTY", []float64{}, []int64{}, 10_000_000_000.0, 12)
	if len(respEmpty.ForecastSteps) != 0 {
		t.Errorf("expected empty steps for empty inputs, got %d", len(respEmpty.ForecastSteps))
	}

	// Edge 2: Nil slices
	respNil := prediction.PredictHorizon("NIL", nil, nil, 10_000_000_000.0, 12)
	if len(respNil.ForecastSteps) != 0 {
		t.Errorf("expected empty steps for nil inputs, got %d", len(respNil.ForecastSteps))
	}

	// Edge 3: Single candle (< 10 threshold)
	respSingle := prediction.PredictHorizon("SINGLE", []float64{1000.0}, []int64{12345678}, 10_000_000_000.0, 12)
	if len(respSingle.ForecastSteps) != 0 {
		t.Errorf("expected empty steps for single candle, got %d", len(respSingle.ForecastSteps))
	}

	// Edge 4: 9 candles (< 10 threshold)
	closes9, ts9 := makeDummyCandles(9, 1000.0, 1.0)
	resp9 := prediction.PredictHorizon("NINE", closes9, ts9, 10_000_000_000.0, 12)
	if len(resp9.ForecastSteps) != 0 {
		t.Errorf("expected empty steps for 9 candles, got %d", len(resp9.ForecastSteps))
	}

	// Edge 5: Flat prices (e.g., 30 candles locked in price limit)
	flatCloses := make([]float64, 30)
	flatTs := make([]int64, 30)
	for i := 0; i < 30; i++ {
		flatCloses[i] = 2500.0
		flatTs[i] = int64(1700000000 + i*86400)
	}
	respFlat := prediction.PredictHorizon("FLAT", flatCloses, flatTs, 10_000_000_000.0, 5)
	if len(respFlat.ForecastSteps) != 5 {
		t.Fatalf("expected 5 steps for flat series, got %d", len(respFlat.ForecastSteps))
	}
	for _, step := range respFlat.ForecastSteps {
		if step.P10 != 2500.0 || step.P50 != 2500.0 || step.P90 != 2500.0 {
			t.Errorf("expected flat 2500.0, got P10=%f, P50=%f, P90=%f", step.P10, step.P50, step.P90)
		}
	}
	if respFlat.VolatilityAmplification != 0.0 {
		t.Errorf("expected 0 vol amplification for flat prices, got %f", respFlat.VolatilityAmplification)
	}

	// Edge 6: Horizon clamping
	closes30, ts30 := makeDummyCandles(30, 1000.0, 1.0)
	// Under-range: horizon <= 0 clamped to 1
	respH0 := prediction.PredictHorizon("H0", closes30, ts30, 10_000_000_000.0, 0)
	if respH0.Horizon != 1 || len(respH0.ForecastSteps) != 1 {
		t.Errorf("expected clamped horizon 1, got %d (%d steps)", respH0.Horizon, len(respH0.ForecastSteps))
	}
	respHNeg := prediction.PredictHorizon("HNEG", closes30, ts30, 10_000_000_000.0, -10)
	if respHNeg.Horizon != 1 || len(respHNeg.ForecastSteps) != 1 {
		t.Errorf("expected clamped horizon 1, got %d (%d steps)", respHNeg.Horizon, len(respHNeg.ForecastSteps))
	}
	// Over-range: horizon > 30 clamped to 30
	respH100 := prediction.PredictHorizon("H100", closes30, ts30, 10_000_000_000.0, 100)
	if respH100.Horizon != 30 || len(respH100.ForecastSteps) != 30 {
		t.Errorf("expected clamped horizon 30, got %d (%d steps)", respH100.Horizon, len(respH100.ForecastSteps))
	}

	// Edge 7: Mismatched slice lengths
	closesLong, tsLong := makeDummyCandles(50, 1000.0, 1.0)
	respMismatch := prediction.PredictHorizon("MISMATCH", closesLong[:40], tsLong[:30], 10_000_000_000.0, 5)
	if len(respMismatch.ForecastSteps) != 5 {
		t.Errorf("expected 5 steps for mismatched lengths, got %d", len(respMismatch.ForecastSteps))
	}
}

func TestPredictHorizonWithModel_Models(t *testing.T) {
	closes, timestamps := makeDummyCandles(50, 4000.0, 5.0)

	for _, model := range []string{"mini", "small", "base"} {
		resp := prediction.PredictHorizonWithModel("TEST_"+model, closes, timestamps, 10_000_000_000.0, 5, model)
		if !resp.IsLiquid {
			t.Errorf("model %s: expected IsLiquid=true", model)
		}
		if len(resp.ForecastSteps) != 5 {
			t.Errorf("model %s: expected 5 steps, got %d", model, len(resp.ForecastSteps))
		}
		expectedModelPrefix := "Kronos-" + model
		if resp.ModelUsed != expectedModelPrefix {
			t.Errorf("model %s: expected ModelUsed=%s, got %s", model, expectedModelPrefix, resp.ModelUsed)
		}
		if resp.HistoricalEnd <= 0 {
			t.Errorf("model %s: expected HistoricalEnd > 0, got %d", model, resp.HistoricalEnd)
		}
		for i, step := range resp.ForecastSteps {
			if step.P10 <= 0 || step.P50 <= 0 || step.P90 <= 0 {
				t.Errorf("model %s step %d: expected positive quantiles, got p10=%f, p50=%f, p90=%f", model, i, step.P10, step.P50, step.P90)
			}
			if step.P10 > step.P50 || step.P50 > step.P90 {
				t.Errorf("model %s step %d: monotonicity broken p10=%f, p50=%f, p90=%f", model, i, step.P10, step.P50, step.P90)
			}
		}
	}
}

func BenchmarkPredictHorizon(b *testing.B) {
	closes, timestamps := makeDummyCandles(120, 2500.0, 3.0)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = prediction.PredictHorizon("BENCH", closes, timestamps, 10_000_000_000.0, 12)
	}
}
