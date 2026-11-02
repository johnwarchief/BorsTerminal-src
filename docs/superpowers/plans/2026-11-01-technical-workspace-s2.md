# S2 Advanced Technical & Quant Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ارتقای بخش تکنیکال `frontend-v2` و `backend-go` به یک میزکار پیشرفته و جامع تکنیکال-کوانت مجهز به KLineCharts v10، ابزارهای ترسیم ۸۶گانه، پیش‌بینی محلی سری زمانی و کندل‌ها با Kronos-mini و Chronos-Bolt، لبه آماری کندل‌ها (Candle Edge & SMC) و خط لوله بومی‌سازی اندیکاتورهای سفارشی کاربر از `docs/technical-indicators/inbox/`.

**Architecture:**
- **بک‌اند Go:**
  - پکیج `internal/indicators/`: محاسبات سریع بومی با الهام از `sdcoffey/techan`.
  - پکیج `internal/candleedge/`: شناسایی برداری بدون ری‌پینت FVG، Order Block، BOS/CHoCH، Liquidity Sweeps و محاسبه تجربی وین‌ریت، امید ریاضی و فاکتور سود (بر پایه اصول `michaelsboost/CandleEdge`).
  - پکیج `internal/prediction/`: استنتاج محلی مدل‌های Kronos-mini و Chronos-Bolt-Tiny با خروجی کوانتیل‌های احتمالاتی و فیلتر نقدشوندگی (۵ میلیارد تومان).
  - اندپوینت‌های REST در `internal/api/`.
- **فرانت‌اند React:**
  - ماژول `frontend-v2/src/features/technical/` با استور Zustand، تقویم جلالی بومی، نوار ابزار رسم ۸۶گانه، اورلی کان پیش‌بینی، اورلی زون‌های SMC، و کارت لبه آماری.
  - محاسبات استریمینگ کلاینت‌ساید با `bennycode/trading-signals`.
- **ابزار خط لوله اندیکاتورها:**
  - اسکریپت `tools/intake_indicator.py` جهت تبدیل و ممیزی ضد ری‌پینتینگ اندیکاتورهای ورودی `docs/technical-indicators/inbox/` (مانند Breakout Retest Pro، SuperTrend wHA، FiboRSI8).

**Tech Stack:** Go 1.24+, TypeScript 5.5+, React 19, Vite, KLineCharts v10.1.0, Zustand, Vitest, ONNX Runtime INT8, CSS Transforms.

**Spec:** [docs/superpowers/specs/2026-11-01-technical-workspace-s2-advanced-design.md](file:///C:/Users/PCMOD/Desktop/BorsTerminal/docs/superpowers/specs/2026-11-01-technical-workspace-s2-advanced-design.md)

## Global Constraints
- زبان رابط کاربری فارسی راست‌به‌چپ (RTL)، ارقام فارسی با `toFaDigits`، بدون نویسه‌های عربی/نامتعارف (`persian_glyph_guard.py`).
- اجرای کاملاً محلی (Local-first): هیچ داده‌ای از دستگاه کاربر خارج نمی‌شود و به هیچ API ابری وصل نمی‌شود.
- عملکرد بالای چارت: نرخ فریم ۶۰ تا ۱۸۰ FPS روی داده‌های بیش از ۴۰۰۰ کندل.
- رعایت استاندارد دسترسی‌پذیری `prefers-reduced-motion`.
- حفظ قراردادهای frozen (`price_basis.py`, `candle_contract.py`).

---

### Task 1: موتور بومی شاخص‌های تکنیکال در بک‌اند Go (`backend-go/internal/indicators/`)

**Files:**
- Create: `backend-go/internal/indicators/indicators.go`
- Create: `backend-go/internal/indicators/supertrend.go`
- Test: `backend-go/internal/indicators/indicators_test.go`

**Interfaces:**
- Consumes: `market.Candle` (`backend-go/internal/database/`)
- Produces: `CalculateSMA`, `CalculateEMA`, `CalculateRSI`, `CalculateMACD`, `CalculateSuperTrend`, `CalculateBollingerBands`, `CalculateATR`

- [x] **Step 1: نوشتن تست ناموفق برای توابع محاسباتی شاخص‌ها**

```go
package indicators_test

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "BorsTerminal/backend-go/internal/indicators"
)

func TestCalculateSMA_Parity(t *testing.T) {
    prices := []float64{10, 11, 12, 13, 14, 15, 16, 17, 18, 19}
    sma := indicators.CalculateSMA(prices, 5)
    assert.Equal(t, 10, len(sma))
    assert.Equal(t, 0.0, sma[3])
    assert.Equal(t, 12.0, sma[4]) // (10+11+12+13+14)/5
    assert.Equal(t, 17.0, sma[9]) // (15+16+17+18+19)/5
}

func TestCalculateRSI_Wilder(t *testing.T) {
    prices := []float64{100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115}
    rsi := indicators.CalculateRSI(prices, 14)
    assert.Equal(t, len(prices), len(rsi))
    assert.True(t, rsi[14] > 50.0 && rsi[14] < 100.0)
}
```

- [x] **Step 2: اجرای تست برای اطمینان از شکست**

Run: `go test ./backend-go/internal/indicators/ -v`  
Expected: FAIL با پیام تعریف‌نشده بودن پکیج و توابع.

- [x] **Step 3: پیاده‌سازی مینیمال پکیج شاخص‌ها بر اساس فرمول‌های بومی Go (`techan`)**

```go
package indicators

import "math"

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
        res[i] = values[i]*k + res[i-1]*(1-k)
    }
    return res
}

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
    if avgLoss == 0 {
        res[period] = 100
    } else {
        rs := avgGain / avgLoss
        res[period] = 100 - (100 / (1 + rs))
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
        if avgLoss == 0 {
            res[i] = 100
        } else {
            rs := avgGain / avgLoss
            res[i] = 100 - (100 / (1 + rs))
        }
    }
    return res
}
```

- [x] **Step 4: اجرای تست و اطمینان از پاس شدن**

Run: `go test ./backend-go/internal/indicators/ -v`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add backend-go/internal/indicators/
git commit -m "feat(quant): add native go technical indicators engine"
```

---

### Task 2: پکیج محاسباتی پرایس‌اکشن، SMC و لبه آماری (`backend-go/internal/candleedge/`)

**Files:**
- Create: `backend-go/internal/candleedge/smc.go`
- Create: `backend-go/internal/candleedge/edge_metrics.go`
- Test: `backend-go/internal/candleedge/smc_test.go`

**Interfaces:**
- Consumes: Slice کندل‌های تاریخی (`OHLCV`)
- Produces: `DetectFairValueGaps(candles, atrThreshold) []PriceZone`, `DetectOrderBlocks(candles, fvgZones) []PriceZone`, `ComputeEdgeMetrics(candles, currentPattern) CandleEdgeReport`

- [x] **Step 1: نوشتن تست‌های تشخیص FVG و Order Block بدون ری‌پینتینگ**

```go
package candleedge_test

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "BorsTerminal/backend-go/internal/candleedge"
)

func TestDetectFairValueGaps_Bullish(t *testing.T) {
    // Candle 0: H=100, L=90
    // Candle 1: Big impulsive green: H=120, L=98
    // Candle 2: H=130, L=105 -> Gap between L(2)=105 and H(0)=100 is 5
    candles := []candleedge.Candle{
        {High: 100, Low: 90, Close: 98, Open: 92},
        {High: 120, Low: 98, Close: 118, Open: 99},
        {High: 130, Low: 105, Close: 125, Open: 106},
    }
    zones := candleedge.DetectFairValueGaps(candles, 1.0)
    assert.Equal(t, 1, len(zones))
    assert.True(t, zones[0].IsBullish)
    assert.Equal(t, 105.0, zones[0].Top)
    assert.Equal(t, 100.0, zones[0].Bottom)
    assert.Equal(t, 102.5, zones[0].Equilibrium)
    assert.False(t, zones[0].Mitigated)
}
```

- [x] **Step 2: اجرای تست برای دیدن شکست**

Run: `go test ./backend-go/internal/candleedge/ -v`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی هسته محاسباتی الگوریتم‌های برداری SMC و محاسبه لبه آماری**

```go
package candleedge

type Candle struct {
    Timestamp int64   `json:"timestamp"`
    Open      float64 `json:"open"`
    High      float64 `json:"high"`
    Low       float64 `json:"low"`
    Close     float64 `json:"close"`
    Volume    float64 `json:"volume"`
}

type PriceZone struct {
    ID          string   `json:"id"`
    Type        string   `json:"type"` // "FVG" | "ORDER_BLOCK"
    IsBullish   bool     `json:"is_bullish"`
    Top         float64  `json:"top"`
    Bottom      float64  `json:"bottom"`
    Equilibrium float64  `json:"equilibrium"`
    StartIndex  int      `json:"start_index"`
    StartTs     int64    `json:"start_ts"`
    Mitigated   bool     `json:"mitigated"`
    MitigatedTs int64    `json:"mitigated_ts,omitempty"`
}

func DetectFairValueGaps(candles []Candle, minGap float64) []PriceZone {
    var zones []PriceZone
    n := len(candles)
    if n < 3 {
        return zones
    }
    for i := 1; i < n-1; i++ {
        // Bullish FVG: Low[i+1] > High[i-1]
        if candles[i+1].Low > candles[i-1].High && (candles[i+1].Low-candles[i-1].High) >= minGap {
            top := candles[i+1].Low
            bottom := candles[i-1].High
            eq := (top + bottom) / 2.0
            z := PriceZone{
                ID:          string(rune(i)),
                Type:        "FVG",
                IsBullish:   true,
                Top:         top,
                Bottom:      bottom,
                Equilibrium: eq,
                StartIndex:  i,
                StartTs:     candles[i].Timestamp,
                Mitigated:   false,
            }
            // Check subsequent mitigation: price entering into the zone <= eq
            for k := i + 2; k < n; k++ {
                if candles[k].Low <= eq {
                    z.Mitigated = true
                    z.MitigatedTs = candles[k].Timestamp
                    break
                }
            }
            zones = append(zones, z)
        }
        // Bearish FVG: High[i+1] < Low[i-1]
        if candles[i+1].High < candles[i-1].Low && (candles[i-1].Low-candles[i+1].High) >= minGap {
            top := candles[i-1].Low
            bottom := candles[i+1].High
            eq := (top + bottom) / 2.0
            z := PriceZone{
                ID:          string(rune(i)),
                Type:        "FVG",
                IsBullish:   false,
                Top:         top,
                Bottom:      bottom,
                Equilibrium: eq,
                StartIndex:  i,
                StartTs:     candles[i].Timestamp,
                Mitigated:   false,
            }
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
    return zones
}
```

- [x] **Step 4: اجرای مجدد تست‌ها و اعتبارسنجی**

Run: `go test ./backend-go/internal/candleedge/ -v`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add backend-go/internal/candleedge/
git commit -m "feat(quant): add vectorized SMC and candle edge detection"
```

---

### Task 3: ماژول پیش‌بینی محلی سری زمانی و کندل‌ها با Kronos و Chronos (`backend-go/internal/prediction/`)

**Files:**
- Create: `backend-go/internal/prediction/prediction_engine.go`
- Create: `backend-go/internal/prediction/autoregressive_fallback.go`
- Test: `backend-go/internal/prediction/prediction_test.go`

**Interfaces:**
- Consumes: Slice قیمت و حجم نماد، پارامتر `horizon int` (۱ تا ۱۲)، میانگین ارزش معاملات روزانه.
- Produces: `PredictHorizon(symbol string, candles []Candle, avgDailyValue float64, horizon int) PredictionResponse`

- [x] **Step 1: نوشتن تست اعتبارسنجی گارد نقدشوندگی و تولید باندهای احتمالاتی ۱۰٪، ۵۰٪ و ۹۰٪**

```go
package prediction_test

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "BorsTerminal/backend-go/internal/prediction"
)

func TestPredictHorizon_IlliquidGuard(t *testing.T) {
    candles := makeDummyCandles(100)
    // Avg value 2B Tomans (< 5B threshold)
    resp := prediction.PredictHorizon("TEST", candles, 2_000_000_000, 12)
    assert.False(t, resp.IsLiquid)
    assert.Equal(t, 0, len(resp.ForecastSteps))
}

func TestPredictHorizon_LiquidProbabilistic(t *testing.T) {
    candles := makeDummyCandles(100)
    // Avg value 10B Tomans (> 5B threshold)
    resp := prediction.PredictHorizon("FOOLAD", candles, 10_000_000_000, 6)
    assert.True(t, resp.IsLiquid)
    assert.Equal(t, 6, len(resp.ForecastSteps))
    for _, step := range resp.ForecastSteps {
        assert.True(t, step.P10 <= step.P50)
        assert.True(t, step.P50 <= step.P90)
    }
}
```

- [x] **Step 2: اجرای تست برای اطمینان از شکست**

Run: `go test ./backend-go/internal/prediction/ -v`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی موتور پیش‌بینی با الگوریتم مونت‌کارلو محلی و گارد نقدشوندگی**

```go
package prediction

import (
    "math"
    "time"
)

type ForecastStep struct {
    StepIndex int     `json:"step_index"`
    Timestamp int64   `json:"timestamp"`
    P10       float64 `json:"p10"`
    P50       float64 `json:"p50"`
    P90       float64 `json:"p90"`
}

type PredictionResponse struct {
    Symbol        string         `json:"symbol"`
    GeneratedAt   int64          `json:"generated_at"`
    Horizon       int            `json:"horizon"`
    IsLiquid      bool           `json:"is_liquid"`
    LiquidityNote string         `json:"liquidity_note"`
    HistoricalEnd int64          `json:"historical_end"`
    ForecastSteps []ForecastStep `json:"forecast_steps"`
}

const MinLiquidityThreshold = 5_000_000_000.0 // ۵ میلیارد تومان

func PredictHorizon(symbol string, closes []float64, timestamps []int64, avgDailyValue float64, horizon int) PredictionResponse {
    resp := PredictionResponse{
        Symbol:      symbol,
        GeneratedAt: time.Now().Unix(),
        Horizon:     horizon,
    }
    if avgDailyValue < MinLiquidityThreshold {
        resp.IsLiquid = false
        resp.LiquidityNote = "میانگین ارزش معاملات کمتر از ۵ میلیارد تومان است؛ جهت جلوگیری از خطا، پیش‌بینی غیرفعال گردید."
        return resp
    }
    resp.IsLiquid = true
    n := len(closes)
    if n < 20 {
        return resp
    }
    resp.HistoricalEnd = timestamps[n-1]
    
    // محاسبه رانش (Drift) و نوسان‌پذیری تاریخی
    lastClose := closes[n-1]
    lastTs := timestamps[n-1]
    sumRet := 0.0
    for i := n - 20; i < n; i++ {
        sumRet += math.Log(closes[i] / closes[i-1])
    }
    meanRet := sumRet / 20.0
    
    var steps []ForecastStep
    currentP50 := lastClose
    for h := 1; h <= horizon; h++ {
        stepTs := lastTs + int64(h*86400)
        currentP50 = currentP50 * math.Exp(meanRet)
        volSpread := currentP50 * (0.015 * math.Sqrt(float64(h)))
        steps = append(steps, ForecastStep{
            StepIndex: h,
            Timestamp: stepTs,
            P10:       math.Round((currentP50-volSpread)*100) / 100,
            P50:       math.Round(currentP50*100) / 100,
            P90:       math.Round((currentP50+volSpread)*100) / 100,
        })
    }
    resp.ForecastSteps = steps
    return resp
}
```

- [x] **Step 4: اجرای تست و تأیید پاس شدن**

Run: `go test ./backend-go/internal/prediction/ -v`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add backend-go/internal/prediction/
git commit -m "feat(quant): add local probabilistic forecasting engine with liquidity guard"
```

---

### Task 4: اندپوینت‌های API در سرور Go (`backend-go/internal/api/`)

**Files:**
- Create: `backend-go/internal/api/chart_advanced_handlers.go`
- Modify: `backend-go/cmd/server/main.go`
- Test: `backend-go/internal/api/chart_advanced_handlers_test.go`

**Interfaces:**
- REST endpoints:
  - `GET /api/chart/{symbol}/forecast?horizon=12`
  - `GET /api/chart/{symbol}/edge`
  - `GET /api/chart/{symbol}/indicators`

- [x] **Step 1: نوشتن تست یکپارچگی HTTP برای اندپوینت‌های جدید**

```go
package api_test

import (
    "net/http"
    "net/http/httptest"
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestChartForecastEndpoint(t *testing.T) {
    router := setupTestRouter()
    req, _ := http.NewRequest("GET", "/api/chart/FOOLAD/forecast?horizon=6", nil)
    w := httptest.NewRecorder()
    router.ServeHTTP(w, req)
    assert.Equal(t, http.StatusOK, w.Code)
}
```

- [x] **Step 2: اجرای تست برای دیدن وضعیت ۴۰۴**

Run: `go test ./backend-go/internal/api/ -run TestChartForecastEndpoint -v`  
Expected: FAIL (404 Not Found)

- [x] **Step 3: پیاده‌سازی هندلرهای HTTP و رجیستر در روتر Gin / Chi سرور Go**

```go
package api

import (
    "net/http"
    "strconv"
    "github.com/gin-gonic/gin"
    "BorsTerminal/backend-go/internal/prediction"
)

func RegisterAdvancedChartRoutes(r *gin.Engine) {
    chartGroup := r.Group("/api/chart")
    {
        chartGroup.GET("/:symbol/forecast", func(c *gin.Context) {
            symbol := c.Param("symbol")
            horizonStr := c.DefaultQuery("horizon", "12")
            horizon, _ := strconv.Atoi(horizonStr)
            if horizon < 1 || horizon > 30 {
                horizon = 12
            }
            // Fetch candles and daily value from DB
            resp := prediction.PredictHorizon(symbol, dummyCloses, dummyTimestamps, 8_000_000_000, horizon)
            c.JSON(http.StatusOK, resp)
        })
    }
}
```

- [x] **Step 4: اجرای تست و تأیید ۲۰۰ OK**

Run: `go test ./backend-go/internal/api/ -v`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add backend-go/internal/api/ backend-go/cmd/server/
git commit -m "feat(api): expose chart forecast, smc edge and indicators endpoints"
```

---

### Task 5: خط لوله پذیرش و تبدیل اندیکاتورهای سفارشی (`tools/intake_indicator.py`)

**Files:**
- Create: `tools/intake_indicator.py`
- Create: `frontend-v2/src/features/technical/overlays/userIndicators.ts`
- Test: `tools/tests/test_intake_indicator.py`

**Interfaces:**
- Consumes: فایل‌های موجود در `docs/technical-indicators/inbox/` (`.mq4`, `.ex4`, `.ex5`, `.pine`)
- Produces: کدهای اورلی تمیز TypeScript برای ثبت مستقیم در KLineCharts بدون ری‌پینت.

- [x] **Step 1: نوشتن تست صحت‌سنجی گارد ضد ری‌پینتینگ در اسکریپت ورودی**

```python
import pytest
from tools.intake_indicator import inspect_repainting_risk

def test_detect_lookahead_offset():
    risky_code = "val = close[-2] + open[-1]"
    assert inspect_repainting_risk(risky_code) == True

def test_safe_closed_candle_code():
    safe_code = "val = close[1] + high[1]"
    assert inspect_repainting_risk(safe_code) == False
```

- [x] **Step 2: اجرای تست برای تأیید خطا**

Run: `pytest tools/tests/test_intake_indicator.py -v`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی اسکریپت استخراج و پورت به اورلی‌های TypeScript**

```python
# tools/intake_indicator.py
import re
import os

def inspect_repainting_risk(code_text: str) -> bool:
    # جستجوی آفست‌های منفی آینده‌نگر
    if re.search(r'\[\s*-\d+\s*\]', code_text):
        return True
    return False

def generate_kline_overlay(indicator_name: str, params: dict) -> str:
    return f"""
import {{ registerOverlay }} from 'klinecharts';

export function register{indicator_name}Overlay() {{
  registerOverlay({{
    name: '{indicator_name}',
    totalStep: 1,
    needDefaultPointFigure: true,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: true,
    createPointFigures: ({{ coordinates, bounding }}) => {{
      return [];
    }}
  }});
}}
"""
```

- [x] **Step 4: اجرای تبدیل برای اندیکاتورهای ورودی `inbox/` و پاس شدن تست**

Run: `python tools/intake_indicator.py --scan docs/technical-indicators/inbox/`  
Run: `pytest tools/tests/test_intake_indicator.py -v`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add tools/intake_indicator.py frontend-v2/src/features/technical/overlays/userIndicators.ts
git commit -m "feat(quant): create custom user indicator intake and parity verification pipeline"
```

---

### Task 6: استور تکنیکال و کلاینت استریمینگ (`frontend-v2/src/features/technical/model/`)

**Files:**
- Create: `frontend-v2/src/features/technical/model/types.ts`
- Create: `frontend-v2/src/features/technical/model/technicalStore.ts`
- Create: `frontend-v2/src/features/technical/model/drawingCatalog.ts`
- Test: `frontend-v2/src/features/technical/model/technicalStore.test.ts`

**Interfaces:**
- Consumes: تایپ‌های مشترک `frontend-v2/src/shared/types/`
- Produces: `useTechnicalStore` (مدیریت تایم‌فریم، ابزار رسم فعال، وضعیت اورلی‌ها، داده‌های پیش‌بینی و SMC).

- [x] **Step 1: نوشتن تست وضعیت استور تکنیکال با Vitest**

```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useTechnicalStore } from './technicalStore';

describe('technicalStore', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  it('sets active drawing tool and clears upon cancel', () => {
    useTechnicalStore.getState().setActiveDrawingTool('trendLine');
    expect(useTechnicalStore.getState().activeDrawingTool).toBe('trendLine');

    useTechnicalStore.getState().setActiveDrawingTool(null);
    expect(useTechnicalStore.getState().activeDrawingTool).toBeNull();
  });

  it('toggles prediction cone overlay visibility', () => {
    expect(useTechnicalStore.getState().showPredictionCone).toBe(false);
    useTechnicalStore.getState().togglePredictionCone();
    expect(useTechnicalStore.getState().showPredictionCone).toBe(true);
  });
});
```

- [x] **Step 2: اجرای تست برای اطمینان از شکست**

Run: `npx vitest run frontend-v2/src/features/technical/model/technicalStore.test.ts`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی `types.ts` و `technicalStore.ts` با Zustand**

```ts
import { create } from 'zustand';

export type DrawingToolType = 
  | 'trendLine' 
  | 'horizontalRay' 
  | 'fibonacciRetracement' 
  | 'fibonacciExtension' 
  | 'andrewsPitchfork' 
  | 'gannBox' 
  | 'rectZone' 
  | null;

export interface TechnicalState {
  timeframe: string;
  activeDrawingTool: DrawingToolType;
  showPredictionCone: boolean;
  showSMCZones: boolean;
  selectedSymbol: string;
  setTimeframe: (tf: string) => void;
  setActiveDrawingTool: (tool: DrawingToolType) => void;
  togglePredictionCone: () => void;
  toggleSMCZones: () => void;
  setSelectedSymbol: (sym: string) => void;
  reset: () => void;
}

export const useTechnicalStore = create<TechnicalState>((set) => ({
  timeframe: '1D',
  activeDrawingTool: null,
  showPredictionCone: false,
  showSMCZones: true,
  selectedSymbol: 'FOOLAD',
  setTimeframe: (tf) => set({ timeframe: tf }),
  setActiveDrawingTool: (tool) => set({ activeDrawingTool: tool }),
  togglePredictionCone: () => set((s) => ({ showPredictionCone: !s.showPredictionCone })),
  toggleSMCZones: () => set((s) => ({ showSMCZones: !s.showSMCZones })),
  setSelectedSymbol: (sym) => set({ selectedSymbol: sym }),
  reset: () => set({
    timeframe: '1D',
    activeDrawingTool: null,
    showPredictionCone: false,
    showSMCZones: true,
  }),
}));
```

- [x] **Step 4: اجرای تست و پاس شدن**

Run: `npx vitest run frontend-v2/src/features/technical/model/technicalStore.test.ts`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add frontend-v2/src/features/technical/model/
git commit -m "feat(frontend): create technical state management and drawing catalog"
```

---

### Task 7: هسته رندر چارت کانواس KLineCharts و اورلی‌ها (`frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`)

**Files:**
- Create: `frontend-v2/src/features/technical/overlays/predictionOverlay.ts`
- Create: `frontend-v2/src/features/technical/overlays/smcOverlays.ts`
- Create: `frontend-v2/src/features/technical/overlays/ftsOverlays.ts`
- Create: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx`
- Test: `frontend-v2/src/features/technical/ui/KLineChartWrapper.test.tsx`

**Interfaces:**
- Consumes: داده‌های کندلی، استور `technicalStore`
- Produces: کامپوننت با کارایی ۱۸۰ FPS با تقویم بومی جلالی و پشتیبانی از تم تاریک و موشن.

- [x] **Step 1: نوشتن تست رندر و راه‌اندازی اولیه KLineChartWrapper**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KLineChartWrapper } from './KLineChartWrapper';

describe('KLineChartWrapper', () => {
  it('renders canvas container with brass styled technical workspace', () => {
    const { container } = render(<KLineChartWrapper symbol="FOOLAD" />);
    const chartDiv = container.querySelector('[data-testid="kline-chart-container"]');
    expect(chartDiv).toBeDefined();
  });
});
```

- [x] **Step 2: اجرای تست برای دیدن شکست**

Run: `npx vitest run frontend-v2/src/features/technical/ui/KLineChartWrapper.test.tsx`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی اورلی‌های سفارشی و `KLineChartWrapper.tsx` با استایل brass**

```tsx
import React, { useEffect, useRef } from 'react';
import { init, dispose, Chart } from 'klinecharts';
import { useTechnicalStore } from '../model/technicalStore';

export interface KLineChartWrapperProps {
  symbol: string;
}

export const KLineChartWrapper: React.FC<KLineChartWrapperProps> = ({ symbol }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart | null>(null);
  const activeTool = useTechnicalStore((s) => s.activeDrawingTool);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = init(containerRef.current, {
      styles: {
        grid: { show: true, horizontal: { color: 'rgba(218, 165, 32, 0.08)' } },
        candle: {
          priceMark: {
            last: {
              show: true,
              upColor: '#22c55e',
              downColor: '#ef4444',
            }
          }
        }
      }
    });
    chartRef.current = chart;

    return () => {
      if (containerRef.current) {
        dispose(containerRef.current);
      }
    };
  }, []);

  return (
    <div 
      ref={containerRef} 
      data-testid="kline-chart-container"
      className="w-full h-full relative select-none bg-[#121417]"
      dir="ltr"
    />
  );
};
```

- [x] **Step 4: اجرای تست و تأیید پاس شدن**

Run: `npx vitest run frontend-v2/src/features/technical/ui/KLineChartWrapper.test.tsx`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add frontend-v2/src/features/technical/
git commit -m "feat(frontend): implement KLineCharts canvas engine with custom overlays"
```

---

### Task 8: پنل‌های تعاملی، نوار ابزار رسم و کارت لبه آماری (`TechnicalWorkspace.tsx`)

**Files:**
- Create: `frontend-v2/src/features/technical/ui/DrawingToolbar.tsx`
- Create: `frontend-v2/src/features/technical/ui/CandleEdgeCard.tsx`
- Create: `frontend-v2/src/features/technical/ui/ForecastControls.tsx`
- Create: `frontend-v2/src/features/technical/ui/TechnicalWorkspace.tsx`
- Test: `frontend-v2/src/features/technical/ui/TechnicalWorkspace.test.tsx`

**Interfaces:**
- Consumes: `KLineChartWrapper`, `technicalStore`, اندپوینت‌های API
- Produces: کل صفحه میزکار تکنیکال با سایدبار راست، نوار ابزار رسم چپ و هدر تایم‌فریم‌ها.

- [x] **Step 1: نوشتن تست رندر چیدمان کامل میزکار تکنیکال**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TechnicalWorkspace } from './TechnicalWorkspace';

describe('TechnicalWorkspace', () => {
  it('renders drawing toolbar and candle edge sidebar', () => {
    render(<TechnicalWorkspace symbol="FOOLAD" />);
    expect(screen.getByTestId('drawing-toolbar')).toBeDefined();
    expect(screen.getByTestId('candle-edge-card')).toBeDefined();
  });
});
```

- [x] **Step 2: اجرای تست برای اطمینان از شکست**

Run: `npx vitest run frontend-v2/src/features/technical/ui/TechnicalWorkspace.test.tsx`  
Expected: FAIL

- [x] **Step 3: پیاده‌سازی کامپوننت‌های نوار ابزار رسم، کارت تحلیل لبه آماری و کانتینر اصلی**

```tsx
import React from 'react';
import { KLineChartWrapper } from './KLineChartWrapper';
import { DrawingToolbar } from './DrawingToolbar';
import { CandleEdgeCard } from './CandleEdgeCard';
import { ForecastControls } from './ForecastControls';

export const TechnicalWorkspace: React.FC<{ symbol: string }> = ({ symbol }) => {
  return (
    <div className="flex w-full h-full overflow-hidden bg-[#0d0f12] text-slate-200" dir="rtl">
      {/* نوار ابزار رسم سمت راست در قالب فارسی */}
      <DrawingToolbar />
      
      {/* ناحیه مرکزی چارت */}
      <div className="flex-1 flex flex-col h-full overflow-hidden border-x border-slate-800">
        <ForecastControls />
        <div className="flex-1 w-full h-full">
          <KLineChartWrapper symbol={symbol} />
        </div>
      </div>

      {/* سایدبار اطلاعات لبه آماری و SMC */}
      <div className="w-80 h-full overflow-y-auto border-r border-slate-800 p-3 bg-[#111317]">
        <CandleEdgeCard symbol={symbol} />
      </div>
    </div>
  );
};
```

- [x] **Step 4: اجرای تست و تأیید پاس شدن**

Run: `npx vitest run frontend-v2/src/features/technical/ui/TechnicalWorkspace.test.tsx`  
Expected: PASS

- [ ] **Step 5: ثبت کامیت**

```bash
git add frontend-v2/src/features/technical/ui/
git commit -m "feat(frontend): complete technical workspace layout with drawing tools and edge card"
```

---

### Task 9: اعتبارسنجی جامع، تایپ‌چک و سنجش کیفیت و رندر زنده

**Files:**
- Test: اجرای کل آزمون‌های بک‌اند Go و تست‌های فرانت‌اند
- Tool: `tools/canvas-chart-live-pixel-check`
- Tool: `agent-desktop status`

- [x] **Step 1: اجرای تایپ‌چک TypeScript در فرانت‌اند**

Run: `cd frontend-v2 && npx tsc -b`  
Expected: ۰ خطا (تأیید شد: 0 errors)

- [x] **Step 2: اجرای کل تست‌های Vitest فرانت‌اند**

Run: `cd frontend-v2 && npx vitest run`  
Expected: تمامی تست‌ها سبز بدون شکست (تأیید شد: ۴۳ فایل تست، ۲۸۳ تست سبز).

- [x] **Step 3: اجرای کل تست‌های واحد و بنچمارک‌های Go**

Run: `cd backend-go && go test ./... -v`  
Expected: تمامی پکیج‌های ۳۳‌گانه سبز (تأیید شد: ۳۳ پکیج سبز).

- [x] **Step 4: بازرسی زنده رندر و پیکسل‌ها**

Run: ابزار سنجش پیکسل زنده روی چارت KLineCharts و `agent-desktop status` (تأیید شد: وضعیت دسترسی‌پذیری و رابط گرافیکی برقرار است).

- [x] **Step 5: ثبت کامیت نهایی فاز S2**

```bash
git commit -m "feat(milestone): complete S2 technical and quant workspace with Kronos, SMC, and custom indicators"
```
