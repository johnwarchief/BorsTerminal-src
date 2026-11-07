package chart

import (
	"context"
	"database/sql"
	"fmt"
	"sort"
	"time"

	"borsterminal/backend/internal/pyround"
)

// AdjustmentMode حالت‌های مختلف تعدیل قیمت چارت تکنیکال مطابق رهاورد ۳۶۵
type AdjustmentMode int

const (
	AdjustmentRaw             AdjustmentMode = 0 // بدون تعدیل
	AdjustmentCapitalIncrease AdjustmentMode = 1 // فقط افزایش سرمایه
	AdjustmentDividend        AdjustmentMode = 2 // فقط سود نقدی
	AdjustmentFunctional      AdjustmentMode = 3 // عملکردی (سود نقدی + افزایش سرمایه)
)

// AdjustEventItem ساختار غنی و تفکیک‌شده رویدادهای مجمع و تعدیل قیمت
type AdjustEventItem struct {
	Date     string  `json:"date"`
	Ratio    float64 `json:"ratio"`
	Type     string  `json:"type"`     // "capital_increase", "dividend", "combined"
	Source   string  `json:"source"`   // "price_adjust", "share_change", "adjust_events"
	CapRatio float64 `json:"capRatio"` // نسبت افزایش سرمایه
	DPS      float64 `json:"dps"`      // سود نقدی مصوب
}

// ComputeAdjustmentFactors محاسبه O(N+M) فاکتورهای تجمعی معکوس با پشتیبانی از حالات تعدیل
func ComputeAdjustmentFactors(times []string, events []AdjustEventItem, mode AdjustmentMode) []float64 {
	out := make([]float64, len(times))
	if len(times) == 0 {
		return out
	}

	if mode == AdjustmentRaw || len(events) == 0 {
		for i := range out {
			out[i] = 1.0
		}
		return out
	}

	// فیلتر رویدادها بر اساس حالت انتخابی کاربر
	var filtered []AdjustEventItem
	for _, ev := range events {
		if ev.Ratio <= 0 || ev.Date == "" {
			continue
		}
		switch mode {
		case AdjustmentCapitalIncrease:
			if ev.Type == "capital_increase" || ev.Type == "combined" {
				filtered = append(filtered, ev)
			}
		case AdjustmentDividend:
			if ev.Type == "dividend" || ev.Type == "combined" {
				filtered = append(filtered, ev)
			}
		case AdjustmentFunctional:
			filtered = append(filtered, ev)
		}
	}

	if len(filtered) == 0 {
		for i := range out {
			out[i] = 1.0
		}
		return out
	}

	// مرتب‌سازی بر اساس تاریخ
	sort.SliceStable(filtered, func(i, j int) bool {
		return filtered[i].Date < filtered[j].Date
	})

	dates := make([]string, len(filtered))
	ratios := make([]float64, len(filtered))
	for i, e := range filtered {
		dates[i] = e.Date
		ratios[i] = e.Ratio
	}

	f := 1.0
	j := len(dates) - 1
	for i := len(times) - 1; i >= 0; i-- {
		t := times[i]
		if len(t) > 10 {
			t = t[:10]
		}
		for j >= 0 && dates[j] > t {
			f *= ratios[j]
			j--
		}
		out[i] = pyround.Round(f, 10)
	}

	return out
}

// isNearDate بررسی می‌کند که آیا دو تاریخ در فاصله زمانی معین (به روز) قرار دارند یا خیر
func isNearDate(d1, d2 string, maxDays int) bool {
	if len(d1) > 10 {
		d1 = d1[:10]
	}
	if len(d2) > 10 {
		d2 = d2[:10]
	}
	t1, err1 := time.Parse("2006-01-02", d1)
	t2, err2 := time.Parse("2006-01-02", d2)
	if err1 != nil || err2 != nil {
		return d1 == d2
	}
	diff := t1.Sub(t2)
	if diff < 0 {
		diff = -diff
	}
	return diff <= time.Duration(maxDays)*24*time.Hour
}

// LoadAutonomousAdjustmentEvents استخراج رویدادهای مستقل مجمع و تعدیل از market.db با تفکیک دقیق نوع رویداد و جلوگیری از احتساب مضاعف
func (s *Service) LoadAutonomousAdjustmentEvents(ctx context.Context, symbol string) []AdjustEventItem {
	var events []AdjustEventItem

	// ۱. استعلام شناسه نماد و رویدادهای تفکیکی price_adjust_events و share_change_events
	var insCode string
	pred, params := s.pred(ctx, "l_val18", symbol)
	allParams := append(params, symbol)
	q := fmt.Sprintf("SELECT ins_code FROM instruments WHERE %s ORDER BY (CASE WHEN l_val18=? THEN 0 ELSE 1 END), updated_at DESC LIMIT 1", pred)
	var ins any
	if err := s.market.QueryRowContext(ctx, q, allParams...).Scan(&ins); err == nil {
		insCode = stringValue(ins)
	}
	if insCode == "" {
		_ = s.market.QueryRowContext(ctx, "SELECT ins_code FROM price_adjust_events WHERE symbol=? LIMIT 1", symbol).Scan(&insCode)
		if insCode == "" {
			_ = s.market.QueryRowContext(ctx, "SELECT ins_code FROM share_change_events WHERE symbol=? LIMIT 1", symbol).Scan(&insCode)
		}
	}
	if insCode != "" {
			// رویدادهای تغییر سهام (افزایش سرمایه)
			rsShare, errShare := s.market.QueryContext(ctx,
				"SELECT d_even, shares_old, shares_new, source FROM share_change_events "+
					"WHERE ins_code=? ORDER BY d_even", insCode)
			if errShare == nil {
				for rsShare.Next() {
					var d, src any
					var oldV, newV sql.NullFloat64
					if err := rsShare.Scan(&d, &oldV, &newV, &src); err == nil {
						dt := dEvenToDate(d)
						if dt != "" && oldV.Valid && newV.Valid && newV.Float64 > 0 && oldV.Float64 > 0 {
							ratio := oldV.Float64 / newV.Float64
							events = append(events, AdjustEventItem{
								Date:     dt,
								Ratio:    ratio,
								Type:     "capital_increase",
								Source:   sourceOrString(src),
								CapRatio: (newV.Float64 - oldV.Float64) / oldV.Float64,
							})
						}
					}
				}
				rsShare.Close()
			}

			// رویدادهای تعدیل قیمت (سود نقدی مجمع)
			rsPrice, errPrice := s.market.QueryContext(ctx,
				"SELECT d_even, p_closing_not_adjusted, p_closing, source FROM price_adjust_events "+
					"WHERE ins_code=? ORDER BY d_even", insCode)
	if errPrice == nil {
		for rsPrice.Next() {
			var d, src any
			var raw, adj sql.NullFloat64
			if err := rsPrice.Scan(&d, &raw, &adj, &src); err == nil {
				dt := dEvenToDate(d)
				if dt != "" && raw.Valid && adj.Valid && raw.Float64 > 0 && adj.Float64 > 0 {
					ratio := adj.Float64 / raw.Float64
					events = append(events, AdjustEventItem{
						Date:   dt,
						Ratio:  ratio,
						Type:   "dividend",
						Source: sourceOrString(src),
						DPS:    raw.Float64 - adj.Float64,
					})
				}
			}
		}
		rsPrice.Close()
	}
	}

	// ۲. استعلام از جدول canonical adjust_events برای رویدادهای تاریخی که در جداول فلو ثبت نشده‌اند
	baseEvents := s.storedAdjustEvents(ctx, symbol)
	for _, be := range baseEvents {
		if be.NullDate || be.Date == "" || be.Ratio <= 0 {
			continue
		}
		// تطابق با رویدادهای ثبت‌شده قبلی بر اساس نزدیکی تاریخ تا از اعمال دوگانه جلوگیری شود
		alreadyMatched := false
		for _, ev := range events {
			if isNearDate(be.Date, ev.Date, 4) {
				alreadyMatched = true
				break
			}
		}
		if !alreadyMatched {
			evType := "dividend"
			if be.Ratio < 0.50 {
				evType = "capital_increase"
			}
			events = append(events, AdjustEventItem{
				Date:   be.Date,
				Ratio:  be.Ratio,
				Type:   evType,
				Source: "adjust_events",
			})
		}
	}

	sort.SliceStable(events, func(i, j int) bool {
		return events[i].Date < events[j].Date
	})

	return events
}

func sourceOrString(v any) string {
	s := stringValue(v)
	if s == "" {
		return "tsetmc"
	}
	return s
}
