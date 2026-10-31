package chart

import (
	"context"
	"database/sql"
)

type adjustEvent struct {
	Date string
	// NullDate یعنی ستونِ date درِ بانک NULL است (پایتون None می‌فرستد، نه "").
	NullDate bool
	Ratio    float64
}

var adjKnownSources = map[string]bool{
	"base-price-discontinuity": true, "no-adjustment-event": true, "local-cache": true,
}

// عینِ _ADJ_FUNCTIONAL_REASON در api/chart.py (بدونِ یک نویسه تغییر).
const adjFunctionalReason = "تعدیلِ عملکردیِ واقعی (سودِ نقدیِ سرمایه‌گذاری‌شدهٔ دوباره) رویدادِ تفکیکی می‌خواهد: افزایشِ سرمایه، آورده/حق‌تقدم، سودِ نقدیِ هر مجمع و تاریخِ معافیت. ادعایِ پیشینِ همین کامنت — «هیچ‌یک از این‌ها درِ فیدِ TSETMC نیست» — با سنجشِ زنده ۱۴۰۵-۰۷-۱۳ رد شد: `ClosingPrice/GetPriceAdjustByFlow` دو پایانیِ `pClosing` و `pClosingNotAdjusted` را برایِ بازارِ کامل می‌دهد و `Instrument/GetInstrumentShareChangeByFlow` تعدادِ سهامِ قبل/بعد را؛ هر دو حالا درِ `price_adjust_events` و `share_change_events` می‌نشینند (docs/TSETMC-DATA-GAP-MATRIX.md §17). چیزی که هنوز مبدأ ندارد **نوعِ رویداد** است: `corporateTypeCode` کلیدش درِ پاسخ هست ولی ۱۴۰۵-۰۷-۱۳ درِ ۴۰۱۸ ردیفِ زنده همه null بود، و هیچ مرجعِ بازبینی‌شده‌ای معنای کدهایش را بدونِ حدس نگفته، و تفکیکِ «سودِ نقدی» از «افزایشِ سرمایه» از «معافیت» همان چیزی است که برایِ تعدیلِ عملکردی لازم است. پس فاکتورِ تجمعی از رویدادِ مبدأ ساختنی است، ولی برچسبِ نوعِ رویداد را حدس نمی‌زنیم."

// storedAdjustEvents مجموعهٔ یک‌بارکشف‌شده؛ جدولِ نبوده مثلِ پایتون «تهی» است
// (پایتون جدول را می‌سازد؛ پاسخ یکی است و Go نمی‌نویسد).
func (s *Service) storedAdjustEvents(ctx context.Context, symbol string) []adjustEvent {
	rs, err := s.market.QueryContext(ctx,
		"SELECT date, ratio FROM adjust_events WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		return nil
	}
	defer rs.Close()
	out := []adjustEvent{}
	for rs.Next() {
		var date sql.NullString
		var ratio sql.NullFloat64
		if err := rs.Scan(&date, &ratio); err != nil {
			return out
		}
		// پایتون فقط ratioِ تهی را می‌اندازد؛ ردیفی با date NULL درِ adjustEvents
		// و درِ event_count می‌ماند (بعد در factors حذفش می‌کند) و date را null
		// می‌فرستد، نه رشتهٔ تهی.
		if ratio.Valid && ratio.Float64 != 0 {
			ev := adjustEvent{Ratio: ratio.Float64}
			if date.Valid {
				ev.Date = date.String
			} else {
				ev.NullDate = true
			}
			out = append(out, ev)
		}
	}
	return out
}

func (s *Service) storedAdjustSource(ctx context.Context, symbol string) string {
	var src sql.NullString
	err := s.market.QueryRowContext(ctx,
		"SELECT source FROM adjust_verdict WHERE symbol=?", symbol).Scan(&src)
	if err != nil {
		return ""
	}
	return src.String
}

func (s *Service) adjustCapability(events []adjustEvent, source string) map[string]any {
	return map[string]any{
		"source": source, "combined_available": adjKnownSources[source],
		"indexed_available": true, "functional_available": false,
		"functional_reason": adjFunctionalReason, "event_count": len(events),
	}
}
