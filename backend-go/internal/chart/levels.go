package chart

import (
	"context"
	"fmt"
	"sort"

	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/pyround"
)

type level struct {
	idx      int
	price    float64
	strength int
	kind     string
}

// fnum عددِ نقشه را می‌خواند؛ تهی/غیرعدد ⇒ 0 (ردیفِ معیوب در پایتون استثنا
// می‌دهد؛ ورودیِ پشتیبانی‌شده همیشه عدد است).
func fnum(m map[string]any, key string) float64 {
	if v, ok := m[key].(float64); ok {
		return v
	}
	return 0
}

// swingExtremes پورتِ _swing_extremes: max/min پنجرهٔ [i-k, i+k] با تکرارِ ≥ min_strength.
func swingExtremes(rows []map[string]any, k, minStrength int) []level {
	n := len(rows)
	out := []level{}
	if n < 2*k+1 {
		return out
	}
	for i := k; i < n-k; i++ {
		hi, lo := fnum(rows[i-k], "high"), fnum(rows[i-k], "low")
		for j := i - k + 1; j <= i+k; j++ {
			if h := fnum(rows[j], "high"); h > hi {
				hi = h
			}
			if l := fnum(rows[j], "low"); l < lo {
				lo = l
			}
		}
		r := rows[i]
		rh, rl := fnum(r, "high"), fnum(r, "low")
		cntHi, cntLo := 0, 0
		for j := i - k; j <= i+k; j++ {
			if absf(fnum(rows[j], "high")-rh) <= rh*0.005 {
				cntHi++
			}
			if absf(fnum(rows[j], "low")-rl) <= rl*0.005 {
				cntLo++
			}
		}
		if rh >= hi*0.995 && cntHi >= minStrength {
			out = append(out, level{idx: i, price: rh, strength: cntHi, kind: "high"})
		} else if rl <= lo*1.005 && cntLo >= minStrength {
			out = append(out, level{idx: i, price: rl, strength: cntLo, kind: "low"})
		}
	}
	return out
}

func absf(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

// mergeLevels پورتِ _merge_levels.
func mergeLevels(ext []level, mergePct float64, keep int) []level {
	if len(ext) == 0 {
		return nil
	}
	ext = append([]level(nil), ext...)
	sort.SliceStable(ext, func(i, j int) bool { return ext[i].price < ext[j].price })
	merged := []level{}
	for _, e := range ext {
		if len(merged) > 0 {
			last := merged[len(merged)-1]
			if absf(e.price-last.price)/last.price <= mergePct {
				if e.strength > last.strength {
					merged[len(merged)-1] = e
				}
				continue
			}
		}
		merged = append(merged, e)
	}
	sort.SliceStable(merged, func(i, j int) bool { return merged[i].idx > merged[j].idx })
	if len(merged) > keep {
		merged = merged[:keep]
	}
	return merged
}

// orderBlocks پورتِ _order_blocks: بلوکِ تقاضا/عرضه رویِ swingهایِ پرمعامله.
func orderBlocks(rows []map[string]any, ext []level, lookback int, volMult float64, keep int) []map[string]any {
	if len(rows) == 0 || len(ext) == 0 {
		return []map[string]any{}
	}
	sum := 0.0
	for _, r := range rows {
		sum += fnum(r, "volume")
	}
	avgVol := sum / float64(len(rows))
	out := []map[string]any{}
	off := append([]level(nil), ext...)
	sort.SliceStable(off, func(i, j int) bool { return off[i].idx > off[j].idx })
	used := map[int]bool{}
	for _, e := range off {
		if len(out) >= keep*2 || used[e.idx] {
			break
		}
		i := e.idx
		if i < 0 || i >= len(rows) {
			continue
		}
		body := rows[i]
		lo := i - lookback
		if lo < 0 {
			lo = 0
		}
		hi := i + lookback + 1
		if hi > len(rows) {
			hi = len(rows)
		}
		w := rows[lo:hi]
		if fnum(body, "volume") < avgVol*volMult {
			continue
		}
		top, bot := fnum(w[0], "high"), fnum(w[0], "low")
		for _, x := range w[1:] {
			if h := fnum(x, "high"); h > top {
				top = h
			}
			if l := fnum(x, "low"); l < bot {
				bot = l
			}
		}
		kind := ""
		if e.kind == "high" && fnum(body, "close") >= fnum(body, "open") {
			kind = "supply"
		} else if e.kind == "low" && fnum(body, "close") <= fnum(body, "open") {
			kind = "demand"
		}
		if kind == "" {
			continue
		}
		end := i + lookback
		if end > len(rows)-1 {
			end = len(rows) - 1
		}
		out = append(out, map[string]any{
			"type": kind, "time_start": rows[lo]["date"], "time_end": rows[end]["date"],
			"top": top, "bottom": bot, "strength": e.strength,
		})
		used[e.idx] = true
	}
	if len(out) > keep {
		out = out[:keep]
	}
	return out
}

// keyLevelsFromHistory پورتِ _key_levels_from_history (۳ مقاومت + ۳ حمایت).
func keyLevelsFromHistory(rows []map[string]any) map[string]any {
	levels := []map[string]any{}
	blocks := []map[string]any{}
	if len(rows) == 0 {
		return map[string]any{"levels": levels, "blocks": blocks, "count": 0}
	}
	ext := swingExtremes(rows, 3, 2)
	merged := mergeLevels(ext, 0.008, 10)
	if len(merged) == 0 {
		return map[string]any{"levels": levels, "blocks": blocks, "count": 0}
	}
	res, sup := []level{}, []level{}
	for _, e := range merged {
		if e.kind == "high" {
			res = append(res, e)
		} else {
			sup = append(sup, e)
		}
	}
	byStrength := func(v []level) []level {
		sort.SliceStable(v, func(i, j int) bool {
			if v[i].strength != v[j].strength {
				return v[i].strength > v[j].strength
			}
			return v[i].idx > v[j].idx
		})
		if len(v) > 3 {
			v = v[:3]
		}
		return v
	}
	chosen := append(byStrength(res), byStrength(sup)...)
	sort.SliceStable(chosen, func(i, j int) bool { return chosen[i].idx > chosen[j].idx })
	for _, e := range chosen {
		levels = append(levels, map[string]any{
			"price": pyround.Round(e.price, 0), "strength": e.strength,
			"kind": e.kind, "date": rows[e.idx]["date"],
		})
	}
	blocks = orderBlocks(rows, ext, 2, 1.5, 3)
	return map[string]any{"levels": levels, "blocks": blocks,
		"count": len(levels) + len(blocks)}
}

// keyLevelsBody همان get_key_levels؛ کش پیش از کارِ سنگین، و «تاریخچهٔ کم» کش نمی‌شود.
func (s *Service) keyLevelsBody(ctx context.Context, symbol string) map[string]any {
	basis := s.basis.Current()
	ck := symbol + "|" + basis
	if body, ok := s.cacheGet(s.keyLevels, ck, keyLevelsTTL); ok {
		return body
	}
	rows, err := s.priceRows(ctx, symbol, 250)
	if err != nil {
		return map[string]any{"status": "error", "message": err.Error()}
	}
	pricebasis.ApplyBasis(rows, false, basis)
	if len(rows) < 60 {
		return map[string]any{"status": "ok", "symbol": symbol, "levels": []map[string]any{},
			"blocks": []map[string]any{}, "count": 0,
			"message": "تاریخچهٔ کافی نیست (< 60 روز)"}
	}
	res := keyLevelsFromHistory(rows)
	res["status"] = "ok"
	res["symbol"] = symbol
	res["message"] = fmt.Sprintf("%d روز آخر", len(rows))
	s.cachePut(s.keyLevels, ck, res)
	return res
}
