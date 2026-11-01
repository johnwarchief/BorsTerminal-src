package screener

import (
	"context"
	"database/sql"
	"sort"
	"strings"
	"time"

	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

type rawPriceHistoryRow struct {
	date   string
	open   float64
	high   float64
	low    float64
	close  float64
	volume float64
	last   *float64
}

// GetHistory واکشی سری تاریخی کندل‌ها و حجم برای نماد مشخص.
func (s *Service) GetHistory(ctx context.Context, symbol string) (map[string]any, error) {
	cleanSym := strings.TrimSpace(symbol)
	if cleanSym == "" {
		return map[string]any{
			"status":  "empty",
			"candles": []any{},
			"volumes": []any{},
		}, nil
	}

	symKey := symbolid.Key(cleanSym)

	// واکشی از جدول price_history با بررسی کلید نماد
	query := `
		SELECT date, open, high, low, close, COALESCE(volume, 0), last, symbol
		FROM price_history
		WHERE symbol = ? OR symbol = ?
		ORDER BY date ASC
	`
	// تست با نماد اصلی و نماد با نویسه‌های عربی/فارسی معکوس
	altSym := strings.ReplaceAll(strings.ReplaceAll(cleanSym, "ی", "ي"), "ک", "ك")
	if altSym == cleanSym {
		altSym = strings.ReplaceAll(strings.ReplaceAll(cleanSym, "ي", "ی"), "ك", "ک")
	}

	rows, err := s.marketDB.QueryContext(ctx, query, cleanSym, altSym)
	if err != nil {
		// اگر جدول وجود نداشت یا خطایی بود
		return map[string]any{
			"status":  "empty",
			"candles": []any{},
			"volumes": []any{},
		}, nil
	}
	defer rows.Close()

	var collected []rawPriceHistoryRow
	for rows.Next() {
		var dateStr string
		var openVal, highVal, lowVal, closeVal, volVal float64
		var lastVal sql.NullFloat64
		var rowSym string

		if err := rows.Scan(&dateStr, &openVal, &highVal, &lowVal, &closeVal, &volVal, &lastVal, &rowSym); err != nil {
			continue
		}

		if symbolid.Key(rowSym) != symKey {
			continue
		}

		if closeVal <= 0 || highVal <= 0 {
			continue
		}

		// اعتبارسنجی تاریخ
		tParsed, err := time.Parse("2006-01-02", strings.TrimSpace(dateStr))
		if err != nil {
			// تلاش برای سایر فرمت‌ها مثل YYYYMMDD یا YYYY/MM/DD
			dClean := strings.ReplaceAll(strings.TrimSpace(dateStr), "/", "-")
			tParsed, err = time.Parse("2006-01-02", dClean)
			if err != nil {
				continue
			}
		}
		stdDate := tParsed.Format("2006-01-02")

		var lPtr *float64
		if lastVal.Valid && lastVal.Float64 > 0 {
			v := lastVal.Float64
			lPtr = &v
		}

		collected = append(collected, rawPriceHistoryRow{
			date:   stdDate,
			open:   openVal,
			high:   highVal,
			low:    lowVal,
			close:  closeVal,
			volume: volVal,
			last:   lPtr,
		})
	}

	if len(collected) == 0 {
		return map[string]any{
			"status":  "empty",
			"candles": []any{},
			"volumes": []any{},
		}, nil
	}

	// سورت بر اساس تاریخ صعودی و حجم نزولی
	sort.Slice(collected, func(i, j int) bool {
		if collected[i].date != collected[j].date {
			return collected[i].date < collected[j].date
		}
		return collected[i].volume > collected[j].volume
	})

	// حذف روزهای تکراری با حفظ ردیف پرحجم‌تر
	dedup := make([]rawPriceHistoryRow, 0, len(collected))
	seenDates := make(map[string]bool)
	for _, r := range collected {
		if seenDates[r.date] {
			continue
		}
		seenDates[r.date] = true
		dedup = append(dedup, r)
	}

	upColor := "rgba(34, 197, 94, 0.4)"
	dnColor := "rgba(239, 68, 68, 0.4)"

	candles := make([]map[string]any, len(dedup))
	volumes := make([]map[string]any, len(dedup))

	for i, r := range dedup {
		var lastVal any = nil
		if r.last != nil && *r.last > 0 {
			lastVal = pyround.Round(*r.last, 2)
		}
		candles[i] = map[string]any{
			"time":  r.date,
			"open":  pyround.Round(r.open, 2),
			"high":  pyround.Round(r.high, 2),
			"low":   pyround.Round(r.low, 2),
			"close": pyround.Round(r.close, 2),
			"last":  lastVal,
		}

		cColor := dnColor
		if r.close >= r.open {
			cColor = upColor
		}
		volumes[i] = map[string]any{
			"time":  r.date,
			"value": pyround.Round(r.volume, 2),
			"color": cColor,
		}
	}

	basePayload := map[string]any{
		"status":  "success",
		"candles": candles,
		"volumes": volumes,
	}

	resolved := pricebasis.ResolvePayload(basePayload, "candles", [2]string{upColor, dnColor}, pricebasis.Default)
	return resolved, nil
}
