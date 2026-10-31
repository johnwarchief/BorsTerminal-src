package chart

import (
	"context"
	"database/sql"
	"strconv"
)

// basketEntry معادلِ _basket_entry: قیمتِ خریدِ ثبت‌شده در سبد (مبنایِ «۵٪ زیرِ
// قیمتِ خرید» درِ حدِ ضررِ تفکیکی). فقط ردیفِ accept با قیمتِ مثبت.
func (s *Service) basketEntry(symbol string) *float64 {
	if s.user == nil {
		return nil
	}
	var price sql.NullFloat64
	var status sql.NullString
	err := s.user.QueryRow(
		"SELECT price, status FROM selection_decisions WHERE symbol = ?", symbol).
		Scan(&price, &status)
	if err != nil {
		return nil
	}
	if status.String != "accept" || !price.Valid || price.Float64 <= 0 {
		return nil
	}
	v := price.Float64
	return &v
}

// chartSnapshot برایِ /api/fts همان ۲۰ ثانیه‌ای است که پایتون پاسخِ فال‌بک را
// نگه می‌دارد (CHART_FALLBACK_TTL درِ api/chart.py). بی‌این، دو درخواستِ پشتِ
// هم درِ نشستِ پرتحرک دو «آخرین کندل» متفاوت می‌دادند، در حالی که پایتون یک
// پاسخِ ثابت می‌دهد. خودِ /api/chart-db همچنان بی‌کش است، مثلِ پایتون.
func (s *Service) chartSnapshot(ctx context.Context, symbol string) map[string]any {
	key := symbol
	if body, ok := s.cacheGet(s.chartBody, key, chartFallbackTTL); ok {
		return body
	}
	body := s.chartDBBody(ctx, symbol, 3)
	if st, _ := body["status"].(string); st == "success" {
		if cands, _ := body["candles"].([]map[string]any); len(cands) > 0 {
			s.cachePut(s.chartBody, key, body)
		}
	}
	return body
}

// analysisSeries معادلِ _fts_analysis_series رویِ همان چیزی که B3 می‌دهد: مسیرِ
// محلی (پایتون با BORS_CHART_CDN=off دقیقاً همین سری را می‌سازد).
func (s *Service) analysisSeries(ctx context.Context, symbol string) ([]map[string]any, string) {
	body := s.chartSnapshot(ctx, symbol)
	if st, _ := body["status"].(string); st != "success" {
		return nil, "local-db-raw"
	}
	cands, _ := body["candles"].([]map[string]any)
	facts, _ := body["factors"].([]map[string]any)
	vols, _ := body["volumes"].([]map[string]any)
	scaled := s.scaleCandles(cands, facts, vols, s.basis.Current())
	if len(scaled) >= 2 {
		if flagged(asMap(body["adjustCapability"])["combined_available"], true) {
			return scaled, "local-db-adjusted"
		}
		return scaled, "local-db-raw"
	}
	return cands, "local-db-raw"
}

// candlesUptoAsOf معادلِ _candles_upto_asof: برشِ واقعیِ ورودی.
func candlesUptoAsOf(candles []map[string]any, asOf string) []map[string]any {
	if asOf == "" {
		return candles
	}
	out := []map[string]any{}
	for _, c := range candles {
		t, _ := c["time"].(string)
		if len(t) > 10 {
			t = t[:10]
		}
		if t <= asOf {
			out = append(out, c)
		}
	}
	return out
}

// ftsCacheKey معادلِ _fts_analysis_cache_key — ترتیبِ فیلدها بخشی از قرارداد است.
func ftsCacheKey(symbol string, lastClose any, entryHint *float64, basis, asOf, engine string, hg map[string]any) string {
	period, _ := hg["hourglass_rsi_period"].(int)
	oversold, _ := hg["hourglass_rsi_oversold"].(float64)
	mode, _ := hg["hourglass_ma52_position"].(string)
	hgKey := "rsi=" + strconv.Itoa(period) + ":oversold=" +
		strconv.FormatFloat(oversold, 'g', 6, 64) + ":ma52=" + mode
	hint := "None"
	if entryHint != nil {
		hint = pyFloatStr(*entryHint)
	}
	key := symbol + "|tf=daily|" + pyStr(lastClose) + "|" + hint +
		"|asof=" + asOf + "|rs=" + ftsTechRulesetVersion + "|eng=" + engine
	if hgKey != "" {
		key += "|hg=" + hgKey
	}
	return key + "|" + basis
}

// analyzeSymbol معادلِ _fts_analyze_symbol: سری + برشِ as_of + کشِ ۹۰۰ ثانیه.
func (s *Service) analyzeSymbol(ctx context.Context, symbol, asOf string) map[string]any {
	candles, basis := s.analysisSeries(ctx, symbol)
	if len(candles) == 0 {
		return map[string]any{"status": "empty", "symbol": symbol, "fts": nil}
	}
	if asOf != "" {
		candles = candlesUptoAsOf(candles, asOf)
		if len(candles) == 0 {
			return map[string]any{"status": "empty", "symbol": symbol,
				"fts": nil, "as_of": asOf}
		}
	}
	hint := s.basketEntry(symbol)
	hg := s.hourglassSettings()
	key := ftsCacheKey(symbol, candles[len(candles)-1]["close"], hint, basis, asOf, s.engine, hg)
	if body, ok := s.cacheGet(s.fts, key, ftsTTL); ok {
		return body
	}
	fts, failure := s.analyzeCandlesSafe(candles, hint)
	if failure != "" {
		// معادلِ `except Exception as e` درِ _fts_analyze_symbol: متنِ خطا
		// درایور-وابسته است، شکلِ بدنه نه.
		return map[string]any{"status": "error", "symbol": symbol, "message": failure}
	}
	evs := s.storedAdjustEvents(ctx, symbol)
	src := s.storedAdjustSource(ctx, symbol)
	if src == "" {
		if len(evs) > 0 {
			src = "local-cache"
		} else {
			src = "local-db-unseen"
		}
	}
	result := map[string]any{
		"status": "success", "symbol": symbol, "fts": fts,
		"analysis_basis": basis, "bars": len(candles),
		"trend_engine":     s.engine,
		"adjustCapability": s.adjustCapability(evs, src),
	}
	if asOf != "" {
		result["as_of"] = asOf
	}
	s.mu.Lock()
	if len(s.fts) > ftsCacheMax {
		s.fts = map[string]cacheEntry{}
	}
	s.mu.Unlock()
	s.cachePut(s.fts, key, result)
	return result
}

// ftsCacheKeys وکتورهایِ تستِ کنترلِ منفی: کلیدها با as_of/مبنا/تنظیم عوض
// می‌شوند و هیچ داوریِ تاریخی به cutoff دیگر نشت نمی‌کند.
func ftsCacheKeys(s *Service) []string {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]string, 0, len(s.fts))
	for k := range s.fts {
		out = append(out, k)
	}
	return out
}
