package chart

import (
	"net/http"
	"strconv"
	"time"

	"borsterminal/backend/internal/candleedge"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/indicators"
	"borsterminal/backend/internal/prediction"
)

func intQuery(w http.ResponseWriter, r *http.Request, name string, def int) (int, bool) {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return def, true
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		httpapi.UnprocessableAs(w, "int_parsing", []string{"query", name},
			"Input should be a valid integer, unable to parse string as an integer", raw)
		return 0, false
	}
	return v, true
}

func (s *Service) ChartDB(w http.ResponseWriter, r *http.Request) {
	// پارامترِ adjustment در قراردادِ کانونیک حذف شده است؛ FastAPI هم کلیدِ
	// ناشناخته را نادیده می‌گیرد، پس این مسیر هم آن را اعتبارسنجی نمی‌کند.
	symbol := r.PathValue("symbol")
	body := s.chartDBBody(r.Context(), symbol, 3)
	// معادلِ wrapperِ مسیرِ پایتون (`get_chart_db_visible`): کندلِ دیدنی
	// literal + تصحیح‌های فیلد خامِ بستهٔ نسخه‌دار، پس از price_basis و FTS.
	// نمادِ پوشش‌داده‌شده با فاکتورهای مرجع، سریِ خامِ type0 خودش را دارد؛
	// تصحیحِ نمایشیِ بسته روی آن اعمال نمی‌شود.
	if cands, ok := body["candles"].([]map[string]any); ok {
		if _, _, measured := s.measuredFactorEvents(r.Context(), symbol); !measured {
			ins := s.resolveInsCode(r.Context(), symbol)
			body["candles"] = literalDisplayCandles(LoadPack(s.dataDir), ins, symbol, cands)
		}
	}
	httpapi.WriteJSON(w, http.StatusOK, body)
}

func (s *Service) FTS(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK,
		s.analyzeSymbol(r.Context(), r.PathValue("symbol"), r.URL.Query().Get("as_of")))
}

func (s *Service) OrderBook(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.orderBookBody(r.Context(), r.PathValue("symbol")))
}

func (s *Service) KeyLevels(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.keyLevelsBody(r.Context(), r.PathValue("symbol")))
}

func (s *Service) CalendarUpcoming(w http.ResponseWriter, r *http.Request) {
	days, ok := intQuery(w, r, "days", 14)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.calendarUpcomingBody(days))
}

func (s *Service) CalendarSymbol(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.calendarSymbolBody(r.PathValue("symbol")))
}

func (s *Service) MA(w http.ResponseWriter, r *http.Request) {
	days, ok := intQuery(w, r, "days", 730)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.maBody(r.Context(), r.PathValue("symbol"), days))
}

func (s *Service) Patterns(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.patternsBody(r.Context(), r.PathValue("symbol")))
}

func (s *Service) Forecast(w http.ResponseWriter, r *http.Request) {
	horizon, ok := intQuery(w, r, "horizon", 12)
	if !ok {
		return
	}
	if horizon < 1 {
		horizon = 1
	} else if horizon > 30 {
		horizon = 30
	}

	adj, ok := intQuery(w, r, "adjustment", 3)
	if !ok {
		return
	}

	symbol := r.PathValue("symbol")
	body := s.chartDBBody(r.Context(), symbol, adj)
	cands, _ := body["candles"].([]map[string]any)

	closes := make([]float64, 0, len(cands))
	timestamps := make([]int64, 0, len(cands))
	var recentValSum float64
	var recentValCount int

	for i, c := range cands {
		cp := numOr0(c["close"])
		if cp <= 0 {
			cp = numOr0(c["closing"])
		}
		if cp <= 0 {
			cp = numOr0(c["last"])
		}
		closes = append(closes, cp)

		var ts int64
		if tStr, ok := c["time"].(string); ok && len(tStr) >= 10 {
			if t, err := time.Parse("2006-01-02", tStr[:10]); err == nil {
				ts = t.Unix()
			}
		}
		if ts == 0 {
			ts = int64(i * 86400)
		}
		timestamps = append(timestamps, ts)

		val := numOr0(c["value"])
		if val <= 0 {
			vol := numOr0(c["volume"])
			if vol > 0 && cp > 0 {
				val = vol * cp
			}
		}
		if i >= len(cands)-30 && val > 0 {
			recentValSum += val
			recentValCount++
		}
	}

	var avgDailyValue float64
	if recentValCount > 0 {
		avgDailyValue = recentValSum / float64(recentValCount)
	}
	if vStr := r.URL.Query().Get("avg_daily_value"); vStr != "" {
		if v, err := strconv.ParseFloat(vStr, 64); err == nil && v > 0 {
			avgDailyValue = v
		}
	}

	model := r.URL.Query().Get("model")
	resp := prediction.PredictHorizonWithModel(symbol, closes, timestamps, avgDailyValue, horizon, model)
	httpapi.WriteJSON(w, http.StatusOK, resp)
}

func (s *Service) Edge(w http.ResponseWriter, r *http.Request) {
	swingPeriod, ok := intQuery(w, r, "swing_period", 5)
	if !ok {
		return
	}
	if swingPeriod < 1 {
		swingPeriod = 5
	}

	symbol := r.PathValue("symbol")
	body := s.chartDBBody(r.Context(), symbol, 3)
	cands, _ := body["candles"].([]map[string]any)

	edgeCandles := make([]candleedge.Candle, 0, len(cands))
	for i, c := range cands {
		op := numOr0(c["open"])
		hi := numOr0(c["high"])
		lo := numOr0(c["low"])
		cl := numOr0(c["close"])
		if cl <= 0 {
			cl = numOr0(c["closing"])
		}
		if cl <= 0 {
			cl = numOr0(c["last"])
		}
		vol := numOr0(c["volume"])

		var ts int64
		if tStr, ok := c["time"].(string); ok && len(tStr) >= 10 {
			if t, err := time.Parse("2006-01-02", tStr[:10]); err == nil {
				ts = t.Unix()
			}
		}
		if ts == 0 {
			ts = int64(i * 86400)
		}

		edgeCandles = append(edgeCandles, candleedge.Candle{
			Timestamp: ts,
			Open:      op,
			High:      hi,
			Low:       lo,
			Close:     cl,
			Volume:    vol,
		})
	}

	report := candleedge.ComputeEdgeMetrics(edgeCandles, swingPeriod)
	report.Symbol = symbol
	httpapi.WriteJSON(w, http.StatusOK, report)
}

type IndicatorsResponse struct {
	Symbol string         `json:"symbol"`
	Count  int            `json:"count"`
	Dates  []string       `json:"dates"`
	Latest map[string]any `json:"latest"`
	Series map[string]any `json:"series"`
}

func (s *Service) Indicators(w http.ResponseWriter, r *http.Request) {
	symbol := r.PathValue("symbol")
	body := s.chartDBBody(r.Context(), symbol, 3)
	cands, _ := body["candles"].([]map[string]any)

	n := len(cands)
	dates := make([]string, 0, n)
	opens := make([]float64, 0, n)
	highs := make([]float64, 0, n)
	lows := make([]float64, 0, n)
	closes := make([]float64, 0, n)

	for _, c := range cands {
		dates = append(dates, stringValue(c["time"]))
		opens = append(opens, numOr0(c["open"]))
		highs = append(highs, numOr0(c["high"]))
		lows = append(lows, numOr0(c["low"]))
		cl := numOr0(c["close"])
		if cl <= 0 {
			cl = numOr0(c["closing"])
		}
		if cl <= 0 {
			cl = numOr0(c["last"])
		}
		closes = append(closes, cl)
	}

	sma20 := indicators.CalculateSMA(closes, 20)
	sma50 := indicators.CalculateSMA(closes, 50)
	sma200 := indicators.CalculateSMA(closes, 200)

	ema9 := indicators.CalculateEMA(closes, 9)
	ema21 := indicators.CalculateEMA(closes, 21)

	rsi14 := indicators.CalculateRSI(closes, 14)

	macdLine, signalLine, hist := indicators.CalculateMACD(closes, 12, 26, 9)

	supertrend, stDir := indicators.CalculateSuperTrend(highs, lows, closes, 10, 3.0)

	bbUpper, bbMiddle, bbLower := indicators.CalculateBollingerBands(closes, 20, 2.0)

	atr14 := indicators.CalculateATR(highs, lows, closes, 14)

	latest := map[string]any{}
	if n > 0 {
		latest["close"] = closes[n-1]
		latest["sma20"] = sma20[n-1]
		latest["sma50"] = sma50[n-1]
		latest["sma200"] = sma200[n-1]
		latest["ema9"] = ema9[n-1]
		latest["ema21"] = ema21[n-1]
		latest["rsi14"] = rsi14[n-1]
		latest["macd"] = macdLine[n-1]
		latest["macd_signal"] = signalLine[n-1]
		latest["macd_hist"] = hist[n-1]
		latest["supertrend"] = supertrend[n-1]
		latest["supertrend_direction"] = stDir[n-1]
		latest["bollinger_upper"] = bbUpper[n-1]
		latest["bollinger_middle"] = bbMiddle[n-1]
		latest["bollinger_lower"] = bbLower[n-1]
		latest["atr14"] = atr14[n-1]
	}

	series := map[string]any{
		"sma20":                sma20,
		"sma50":                sma50,
		"sma200":               sma200,
		"ema9":                 ema9,
		"ema21":                ema21,
		"rsi14":                rsi14,
		"macd":                 macdLine,
		"macd_signal":          signalLine,
		"macd_hist":            hist,
		"supertrend":           supertrend,
		"supertrend_direction": stDir,
		"bollinger_upper":      bbUpper,
		"bollinger_middle":     bbMiddle,
		"bollinger_lower":      bbLower,
		"atr14":                atr14,
	}

	resp := IndicatorsResponse{
		Symbol: symbol,
		Count:  n,
		Dates:  dates,
		Latest: latest,
		Series: series,
	}

	httpapi.WriteJSON(w, http.StatusOK, resp)
}
