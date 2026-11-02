package prediction

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// MinLiquidityThreshold defines the minimum daily traded value (5 Billion Tomans)
// required for AI prediction. Below this threshold, predictions are disabled
// to avoid spurious statistical noise in illiquid symbols.
const MinLiquidityThreshold = 5_000_000_000.0

// ForecastStep represents a single forward step in the probabilistic forecast cone.
type ForecastStep struct {
	StepIndex int     `json:"step_index"`
	Timestamp int64   `json:"timestamp"`
	P10       float64 `json:"p10"` // Lower bound (10th percentile)
	P50       float64 `json:"p50"` // Median forecast (50th percentile)
	P90       float64 `json:"p90"` // Upper bound (90th percentile)
}

// PredictionResponse represents the response containing probabilistic forecasts and risk metrics.
type PredictionResponse struct {
	Symbol                  string         `json:"symbol"`
	GeneratedAt             int64          `json:"generated_at"`
	Horizon                 int            `json:"horizon"`
	ModelUsed               string         `json:"model_used,omitempty"`
	IsLiquid                bool           `json:"is_liquid"`
	LiquidityNote           string         `json:"liquidity_note,omitempty"`
	HistoricalEnd           int64          `json:"historical_end"`
	ForecastSteps           []ForecastStep `json:"forecast_steps"`
	UpsideProbability       float64        `json:"upside_probability"`
	VolatilityAmplification float64        `json:"volatility_amplification"`
}

// PredictHorizon evaluates liquidity and runs probabilistic time-series forecasting
// over the requested horizon (1..30 candles) using the default Kronos model.
func PredictHorizon(symbol string, closes []float64, timestamps []int64, avgDailyValue float64, horizon int) PredictionResponse {
	return PredictHorizonWithModel(symbol, closes, timestamps, avgDailyValue, horizon, "small")
}

// PredictHorizonWithModel executes neural inference with the specified Kronos model (mini, small, base),
// falling back safely to analytical vector autoregressive simulation when needed.
func PredictHorizonWithModel(symbol string, closes []float64, timestamps []int64, avgDailyValue float64, horizon int, model string) PredictionResponse {
	resp := PredictionResponse{
		Symbol:        symbol,
		GeneratedAt:   time.Now().Unix(),
		ForecastSteps: []ForecastStep{},
	}

	// Clamp horizon to safe range 1..30
	if horizon < 1 {
		horizon = 1
	} else if horizon > 30 {
		horizon = 30
	}
	resp.Horizon = horizon

	// Validate inputs length
	n := len(closes)
	if len(timestamps) < n {
		n = len(timestamps)
	}

	if n > 0 {
		resp.HistoricalEnd = timestamps[n-1]
	}

	// Liquidity Guard: 5 Billion Tomans minimum threshold
	if avgDailyValue < MinLiquidityThreshold {
		resp.IsLiquid = false
		resp.LiquidityNote = "میانگین ارزش معاملات کمتر از ۵ میلیارد تومان است؛ جهت جلوگیری از خطا، پیش‌بینی غیرفعال گردید."
		return resp
	}
	resp.IsLiquid = true

	// If fewer than 10 candles, statistical forecasting is not reliable
	if n < 10 {
		return resp
	}

	if model == "" {
		model = "small"
	}

	// Try running real Kronos local neural inference
	if neuralResp, err := invokeKronos(symbol, closes[:n], timestamps[:n], horizon, model); err == nil && len(neuralResp.ForecastSteps) > 0 {
		neuralResp.IsLiquid = true
		if neuralResp.HistoricalEnd == 0 {
			neuralResp.HistoricalEnd = resp.HistoricalEnd
		}
		if neuralResp.GeneratedAt == 0 {
			neuralResp.GeneratedAt = resp.GeneratedAt
		}
		return *neuralResp
	}

	// Fallback to built-in Go autoregressive Monte Carlo engine
	steps, upsideProb, volAmp := RunAutoregressiveForecast(closes[:n], timestamps[:n], horizon)
	resp.ForecastSteps = steps
	resp.UpsideProbability = upsideProb
	resp.VolatilityAmplification = volAmp
	resp.ModelUsed = "Autoregressive-MonteCarlo"

	return resp
}

func findKronosScript() string {
	candidates := []string{
		"tools/kronos_inference.py",
		"../tools/kronos_inference.py",
		"../../tools/kronos_inference.py",
		"../../../tools/kronos_inference.py",
		"../../../../tools/kronos_inference.py",
	}
	if root := os.Getenv("BORS_ROOT"); root != "" {
		candidates = append(candidates, filepath.Join(root, "tools", "kronos_inference.py"))
	}
	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil && !fi.IsDir() {
			if abs, err := filepath.Abs(c); err == nil {
				return abs
			}
			return c
		}
	}
	if wd, err := os.Getwd(); err == nil {
		dir := wd
		for i := 0; i < 6; i++ {
			p := filepath.Join(dir, "tools", "kronos_inference.py")
			if fi, err := os.Stat(p); err == nil && !fi.IsDir() {
				return p
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}
	return ""
}

func invokeKronos(symbol string, closes []float64, timestamps []int64, horizon int, model string) (*PredictionResponse, error) {
	scriptPath := findKronosScript()
	if scriptPath == "" {
		return nil, os.ErrNotExist
	}

	inputData := map[string]any{
		"symbol":     symbol,
		"horizon":    horizon,
		"model":      model,
		"closes":     closes,
		"timestamps": timestamps,
	}
	inputBytes, err := json.Marshal(inputData)
	if err != nil {
		return nil, err
	}

	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, "python", scriptPath, "--stdin")
	repoRoot := filepath.Dir(filepath.Dir(scriptPath))
	if fi, err := os.Stat(repoRoot); err == nil && fi.IsDir() {
		cmd.Dir = repoRoot
	}
	cmd.Stdin = bytes.NewReader(inputBytes)
	outBytes, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	var res PredictionResponse
	if err := json.Unmarshal(outBytes, &res); err != nil {
		return nil, err
	}
	return &res, nil
}
