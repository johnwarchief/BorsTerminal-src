package chart

import (
	"context"
	"time"

	"borsterminal/backend/internal/pricebasis"
)

// tsOf ظهرِ UTCِ همان روز، میلی‌ثانیه — قراردادِ overlay v10.
func tsOf(day string) (int64, bool) {
	t, err := time.Parse("2006-01-02", day)
	if err != nil {
		return 0, false
	}
	return time.Date(t.Year(), t.Month(), t.Day(), 12, 0, 0, 0, time.UTC).Unix() * 1000, true
}

func (s *Service) patternsBody(ctx context.Context, symbol string) map[string]any {
	basis := s.basis.Current()
	ck := symbol + "|" + basis
	if body, ok := s.cacheGet(s.patterns, ck, patternsTTL); ok {
		return body
	}
	rows, err := s.priceRows(ctx, symbol, 250)
	if err != nil {
		return map[string]any{"status": "error", "message": err.Error()}
	}
	if len(rows) < 60 {
		return map[string]any{"status": "ok", "symbol": symbol,
			"overlays": []map[string]any{}, "count": 0, "message": "تاریخچه کافی نیست"}
	}
	evs := s.storedAdjustEvents(ctx, symbol)
	pricebasis.ApplyBasis(rows, false, basis)
	// سطح‌ها در فضایِ تعدیل‌شده (چارت با factor رسم می‌کند) — وگرنه Y-mismatch.
	for _, r := range rows {
		f := 1.0
		day, _ := r["date"].(string)
		for _, e := range evs {
			if e.Date > day {
				f *= e.Ratio
			}
		}
		for _, k := range []string{"high", "low", "close", "closing", "last",
			"high_raw", "low_raw"} {
			if v, ok := r[k].(float64); ok {
				r[k] = v * f
			}
		}
	}
	ext := swingExtremes(rows, 3, 2)
	levels := mergeLevels(ext, 0.008, 6)
	baseTs, ok := tsOf(rows[0]["date"].(string))
	if !ok {
		return map[string]any{"status": "error", "message": "تاریخِ نامعتبر در تاریخچه"}
	}
	overlays := []map[string]any{}
	for _, lv := range levels {
		color := "#38bdf8"
		if lv.kind == "high" {
			color = "#f59e0b"
		}
		overlays = append(overlays, map[string]any{
			"name": "horizontalStraightLine", "kind": "sr",
			"points": []map[string]any{{"timestamp": baseTs, "value": lv.price}},
			"styles": map[string]any{"line": map[string]any{
				"style": "dashed", "size": 1, "color": color}},
			"meta": map[string]any{"strength": lv.strength, "kind": lv.kind},
		})
	}
	highs, lows := []level{}, []level{}
	for _, e := range ext {
		if e.kind == "high" {
			highs = append(highs, e)
		} else {
			lows = append(lows, e)
		}
	}
	if len(highs) > 2 {
		highs = highs[len(highs)-2:]
	}
	if len(lows) > 2 {
		lows = lows[len(lows)-2:]
	}
	for _, pair := range []struct {
		pts   []level
		kind  string
		color string
	}{{highs, "trend-high", "#ef4444"}, {lows, "trend-low", "#22c55e"}} {
		if len(pair.pts) != 2 {
			continue
		}
		pts := []map[string]any{}
		for _, p := range pair.pts {
			ts, ok := tsOf(rows[p.idx]["date"].(string))
			if !ok {
				return map[string]any{"status": "error", "message": "تاریخِ نامعتبر در تاریخچه"}
			}
			pts = append(pts, map[string]any{"timestamp": ts, "value": p.price})
		}
		overlays = append(overlays, map[string]any{
			"name": "trendLine", "kind": pair.kind, "points": pts,
			"styles": map[string]any{"line": map[string]any{
				"color": pair.color, "size": 2}},
		})
	}
	last20 := rows[len(rows)-20:]
	hi, lo := fnum(last20[0], "high"), fnum(last20[0], "low")
	for _, r := range last20[1:] {
		if h := fnum(r, "high"); h > hi {
			hi = h
		}
		if l := fnum(r, "low"); l < lo {
			lo = l
		}
	}
	startTs, ok1 := tsOf(last20[0]["date"].(string))
	endTs, ok2 := tsOf(last20[len(last20)-1]["date"].(string))
	if !ok1 || !ok2 {
		return map[string]any{"status": "error", "message": "تاریخِ نامعتبر در تاریخچه"}
	}
	overlays = append(overlays, map[string]any{
		"name": "rect", "kind": "breakout-zone",
		"points": []map[string]any{
			{"timestamp": startTs, "value": hi},
			{"timestamp": endTs, "value": lo},
		},
		"styles": map[string]any{"color": "#2962ff"},
	})
	result := map[string]any{"status": "ok", "symbol": symbol,
		"overlays": overlays, "count": len(overlays)}
	s.cachePut(s.patterns, ck, result)
	return result
}
