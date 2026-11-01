package fundamental

// ارزش بازار — تک‌منبعِ حقیقت (ستونِ market_cap درِ اسنپ‌شاتِ تابلو).
// مرجع: api/fundamental.py:262-426 و fts_engine.has_market_cap_col/
// mcap_dead_band_sql (تک‌تعریفش درِ internal/store). هیچ ضربِ دستیِ
// «تعدادِ سهام × قیمت» اینجا ساخته نمی‌شود؛ اگر تابلو عددِ معتبر ندارد،
// شاخصِ ۴ باید «قابل محاسبه نبود» بگوید، نه یک عددِ ساختگی.
//
// تنها تفاوتِ اعلام‌شده (R7): پایتون بی‌ستون اول مهاجرت می‌کند
// (ensure_market_cap_schema) و دوباره می‌پرسد؛ Go درِ فازِ A user.db/market.db
// را نمی‌نویسد، پس همان «دسترس نیست» را با پرچمِ market_cap_column_missing
// اعلام می‌کند. بدنه یکی است، اثرِ جانبی نه.

import (
	"context"
	"math"
	"strings"

	"borsterminal/backend/internal/mstat"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/symbolid"
)

// همت = ۱۰^۱۲ تومان = ۱۰^۱۳ ریال (قاعدهٔ جزوه؛ تنها نقطۀ تبدیلِ این یکا).
const hemmatRial = 1e13

const (
	mcapErrNoRow    = "symbol_not_on_board"       // نماد فقط-کدال (صندوق/حق تقدم/…)
	mcapErrNoCol    = "market_cap_column_missing" // market.db پیش از مهاجرت v10
	mcapErrNoValue  = "market_cap_missing_value"  // سطر هست ولی ستون NULL/≤0
	mcapErrBadValue = "market_cap_invalid_value"  // NaN/inf در ستونِ ذخیره‌شده
	mcapErrNoBand   = "market_cap_no_live_band"   // مجازِ قیمت max<=min ⇒ نشانه، نه ارزش
)

// hmtToRials تنها نقطۀ تبدیلِ همت → ریال درِ این مسیر (عینِ _hmt_to_rials).
func hmtToRials(hmt any) float64 { return toF(hmt) * hemmatRial }

// pyReason همان `str(e)[:120]` درِ دو شاخۀ خطادارِ پایتون است. متنِ خطا بینِ دو
// backend یکسان نیست (و مقایسه نمی‌شود)، ولی **بودنِ** کلیدِ reason شکلِ پاسخ را
// حفظ می‌کند؛ برش رویِ rune است چون پایتون کدپوینت می‌شمارد نه بایت.
func pyReason(err error) string {
	if err == nil {
		return ""
	}
	r := []rune(err.Error())
	if len(r) > 120 {
		r = r[:120]
	}
	return string(r)
}

// rialErrorTuple مثلِ `_rials_or_none`: (مقدار|nil، خطا|nil). صفر/منفی/NaN/inf
// «ارزش بازار» نیستند؛ None برمی‌گردد تا مصرف‌کننده حدس نزند ۰ یعنی «بی‌داده».
func rialErrorTuple(v any) (any, any) {
	if v == nil {
		return nil, mcapErrNoValue
	}
	f, ok := asFloat(v)
	if !ok {
		return nil, mcapErrBadValue
	}
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return nil, mcapErrBadValue
	}
	if f <= 0 {
		return nil, mcapErrNoValue
	}
	return f, nil
}

// MarketCapInfo عینِ get_tsetmc_market_cap_info: نخست سطرِ جاریِ تابلو، سپس
// آخرین market_capِ معتبرِ daily_prices با پرچمِ stale. هیچ‌وقت صفر برنمی‌گردد
// که شاخصِ ۴ آن را «بازارِ صفر» و نسبت را «بی‌نهایت» بخواند.
func (s *Service) MarketCapInfo(ctx context.Context, symbol string) map[string]any {
	out := map[string]any{"symbol": symbol, "rials": nil, "hmt": nil, "source": nil,
		"asof": nil, "stale": false, "error": nil}
	pred18, args18, err := s.sid.Pred(ctx, "i.l_val18", symbol, symbolid.Board)
	if err != nil {
		out["error"] = "db_unavailable"
		out["reason"] = pyReason(err)
		return out
	}
	where := "(" + pred18 + " OR " + strings.ReplaceAll(pred18, "i.l_val18", "i.l_val30") + ")"
	args := append(append([]any{}, args18...), args18...)

	if !store.HasColumn(s.market, "market_watch", "market_cap") {
		out["error"] = mcapErrNoCol
		return out
	}
	hasBand := store.HasColumn(s.market, "market_watch", "allowed_max") &&
		store.HasColumn(s.market, "market_watch", "allowed_min")
	sel := "m.market_cap, m.market_cap_src, m.d_even"
	if hasBand {
		sel += ", CASE WHEN " + store.McapDeadBandSQL("m") + " THEN 1 ELSE 0 END"
	}
	// کوئریِ تابلو درِ پایتون try/except sqlite3.Error دارد و خطا را با row=None
	// می‌بلعد؛ تاریخچه و on_board such exception‌ها را بی‌catch به handlerِ بیرونی
	// می‌فرستند (⇒ error=mcap_lookup_failed). این تفاوتِ محلِ catch اینجا حفظ شده.
	row, err := s.queryRow(ctx, "SELECT "+sel+" FROM market_watch m"+
		" JOIN instruments i ON i.ins_code = m.ins_code"+
		" WHERE "+where+" ORDER BY i.updated_at DESC LIMIT 1", args)
	if err != nil {
		row = nil
	}
	if row != nil && hasBand && truthy(row[3]) {
		// تابلو بانِ معاملۀ زنده ندارد ⇒ «قیمت × سهام» ارزشِ بازار نیست؛ مقدار درِ
		// بانک می‌ماند ولی واردِ فروش÷ارزش نمی‌شود — حتی از مسیرِ تاریخچه.
		out["error"] = mcapErrNoBand
		out["asof"] = row[2]
		return out
	}
	if row != nil {
		mcap, errFlag := rialErrorTuple(row[0])
		if mcap != nil {
			f := toF(mcap)
			out["rials"] = f
			out["hmt"] = pyround.Round(f/hemmatRial, 4)
			out["source"] = orStr(row[1], "tse_board")
			out["asof"] = row[2]
			return out
		}
		out["error"] = errFlag
		out["asof"] = row[2]
	} else {
		onBoard, err := s.queryRow(ctx, "SELECT 1 FROM instruments i WHERE "+where+" LIMIT 1", args)
		if err != nil {
			out["error"] = "mcap_lookup_failed"
			out["reason"] = pyReason(err)
			return out
		}
		if onBoard == nil {
			out["error"] = mcapErrNoRow
		} else {
			out["error"] = mcapErrNoValue
		}
	}
	// ۲) آخرین مقدارِ معتبرِ ثبت‌شده (امروزِ خالی جای دیروزِ معتبر را نمی‌گیرد)
	if store.HasColumn(s.market, "daily_prices", "market_cap") {
		hist, err := s.queryRow(ctx, "SELECT d.market_cap, d.market_cap_src, d.d_even"+
			" FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code"+
			" WHERE "+where+" AND d.market_cap > 0"+
			" ORDER BY d.d_even DESC LIMIT 1", args)
		if err != nil {
			out["error"] = "mcap_lookup_failed"
			out["reason"] = pyReason(err)
			return out
		}
		if hist != nil {
			hm, _ := rialErrorTuple(hist[0])
			if hm != nil {
				f := toF(hm)
				out["rials"] = f
				out["hmt"] = pyround.Round(f/hemmatRial, 4)
				out["source"] = orStr(hist[1], "tse_board")
				out["asof"] = hist[2]
				out["stale"] = true
				out["error"] = nil
			}
		}
	} else if out["error"] == mcapErrNoValue {
		out["error"] = mcapErrNoCol
	}
	return out
}

// BoardTotalMarketCap عینِ board_total_market_cap: جمعِ ستونِ market_cap روی
// market_watch **ممنوع** است (یکِ شرکت چند ردیفِ تابلو دارد و ردیفِ نشست‌های
// قدیمی حذف نمی‌شود؛ جمعِ دستی ۲٫۸ برابر شد). عدد از همان تک‌منبعِ mstat می‌آید
// و فقط وقتی نیامده به جمعِ تابلو بازمی‌گردد، با منبعِ پشتیبانِ اعلام‌شده.
func (s *Service) BoardTotalMarketCap(ctx context.Context) (float64, string) {
	total, src := mstat.MarketTotalRials(s.market)
	if total > 0 {
		return total, src
	}
	if store.HasColumn(s.market, "market_watch", "market_cap") {
		row, err := s.queryRow(ctx, "SELECT SUM(market_cap) FROM market_watch"+
			" WHERE market_cap > 0", nil)
		if err == nil && row != nil {
			if t := toF(row[0]); t > 0 {
				return t, "market_watch.market_cap"
			}
		}
	}
	return 0, mcapErrNoCol
}

// orStr مثلِ `str(x or default)`.
func orStr(v any, def string) string {
	if isFalsy(v) {
		return def
	}
	return pyStr(v)
}
