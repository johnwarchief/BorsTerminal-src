package prediction

import (
	"math"
	"math/rand"
)

// RunAutoregressiveForecast performs vector autoregressive drift estimation and
// Monte Carlo path simulation (inspired by Kronos-mini N=30/N=200 sampling).
// It returns forecast steps with P10/P50/P90 quantiles, upside probability, and
// volatility amplification probability.
func RunAutoregressiveForecast(closes []float64, timestamps []int64, horizon int) ([]ForecastStep, float64, float64) {
	n := len(closes)
	if n < 10 {
		return []ForecastStep{}, 0.5, 0.0
	}

	lastClose := closes[n-1]
	lastTs := timestamps[n-1]
	if lastClose <= 0 {
		return []ForecastStep{}, 0.0, 0.0
	}

	// Determine step interval dt (default 86400 seconds)
	dt := int64(86400)
	if n >= 2 {
		diff := timestamps[n-1] - timestamps[n-2]
		if diff > 0 {
			dt = diff
		}
	}

	// Use lookback window of 20 to 60 candles
	lookback := 60
	if n < lookback {
		lookback = n
	}
	if lookback < 10 {
		lookback = 10
	}

	var returns []float64
	for i := n - lookback + 1; i < n; i++ {
		if closes[i-1] > 0 && closes[i] > 0 {
			returns = append(returns, math.Log(closes[i]/closes[i-1]))
		}
	}

	m := len(returns)
	if m < 2 {
		// Insufficient return points, return flat steps
		steps := make([]ForecastStep, horizon)
		for h := 1; h <= horizon; h++ {
			p := math.Round(lastClose*100) / 100
			steps[h-1] = ForecastStep{
				StepIndex: h,
				Timestamp: lastTs + int64(h)*dt,
				P10:       p,
				P50:       p,
				P90:       p,
			}
		}
		return steps, 0.5, 0.0
	}

	// Calculate historical drift (mean log return) and volatility (sample std dev)
	sumRet := 0.0
	for _, r := range returns {
		sumRet += r
	}
	meanRet := sumRet / float64(m)

	sumSq := 0.0
	for _, r := range returns {
		diff := r - meanRet
		sumSq += diff * diff
	}
	histVol := math.Sqrt(sumSq / float64(m-1))

	// Handle flat prices edge case
	if histVol < 1e-9 {
		steps := make([]ForecastStep, horizon)
		for h := 1; h <= horizon; h++ {
			p := math.Round(lastClose*math.Exp(meanRet*float64(h))*100) / 100
			steps[h-1] = ForecastStep{
				StepIndex: h,
				Timestamp: lastTs + int64(h)*dt,
				P10:       p,
				P50:       p,
				P90:       p,
			}
		}
		upside := 0.5
		if meanRet > 1e-6 {
			upside = 1.0
		} else if meanRet < -1e-6 {
			upside = 0.0
		}
		return steps, upside, 0.0
	}

	// Monte Carlo simulation with N=200 paths (inspired by Kronos-mini)
	const numPaths = 200
	// Deterministic pseudo-random seed based on input data for reproducible execution
	seed := lastTs*31 + int64(math.Float64bits(lastClose))*17 + int64(horizon)*13 + int64(n)
	rng := rand.New(rand.NewSource(seed))

	allPaths := make([][]float64, numPaths)
	pathReturns := make([][]float64, numPaths)
	upsideCount := 0
	volAmpCount := 0

	// Z critical value for 10% and 90% in normal distribution is ~1.2815515655
	const z90 = 1.2815515655

	for p := 0; p < numPaths; p++ {
		prices := make([]float64, horizon)
		rets := make([]float64, horizon)
		currPrice := lastClose

		for h := 0; h < horizon; h++ {
			z := rng.NormFloat64()
			stepReturn := meanRet + histVol*z
			currPrice *= math.Exp(stepReturn)
			prices[h] = currPrice
			rets[h] = stepReturn
		}

		allPaths[p] = prices
		pathReturns[p] = rets

		if prices[horizon-1] > lastClose {
			upsideCount++
		}

		// Compute simulated path volatility
		if horizon >= 2 {
			pSum := 0.0
			for _, r := range rets {
				pSum += r
			}
			pMean := pSum / float64(horizon)
			pSumSq := 0.0
			for _, r := range rets {
				d := r - pMean
				pSumSq += d * d
			}
			pathVol := math.Sqrt(pSumSq / float64(horizon-1))
			if pathVol > histVol {
				volAmpCount++
			}
		} else {
			// Horizon == 1: check if deviation exceeds historical 1-sigma
			if math.Abs(rets[0]-meanRet) > histVol {
				volAmpCount++
			}
		}
	}

	upsideProb := math.Round((float64(upsideCount)/float64(numPaths))*10000) / 10000
	volAmp := math.Round((float64(volAmpCount)/float64(numPaths))*10000) / 10000

	// Generate forecast steps with smooth quantiles
	steps := make([]ForecastStep, horizon)
	for h := 1; h <= horizon; h++ {
		stepTs := lastTs + int64(h)*dt
		sqrtH := math.Sqrt(float64(h))

		// Analytical log-normal quantiles (smooth cone)
		drift := meanRet * float64(h)
		volSpread := z90 * histVol * sqrtH

		p50Raw := lastClose * math.Exp(drift)
		p10Raw := lastClose * math.Exp(drift - volSpread)
		p90Raw := lastClose * math.Exp(drift + volSpread)

		p10 := math.Round(p10Raw*100) / 100
		p50 := math.Round(p50Raw*100) / 100
		p90 := math.Round(p90Raw*100) / 100

		// Ensure strictly non-negative and monotonic
		if p10 < 0.01 {
			p10 = 0.01
		}
		if p50 < p10 {
			p50 = p10
		}
		if p90 < p50 {
			p90 = p50
		}

		steps[h-1] = ForecastStep{
			StepIndex: h,
			Timestamp: stepTs,
			P10:       p10,
			P50:       p50,
			P90:       p90,
		}
	}

	return steps, upsideProb, volAmp
}
