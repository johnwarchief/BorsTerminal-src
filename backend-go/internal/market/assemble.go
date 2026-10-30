package market

import (
	"math"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
)

// عینِ _DROP_FIELDS در api/market.py — فقط برایِ بدنۀ پیش‌فرض.
var dropFields = map[string]bool{
	"eps": true, "price_max": true, "price_min": true,
	"buy_n_vol": true, "sell_n_vol": true,
	"buy_q_vol": true, "buy_q_val": true, "buy_q_cnt": true,
	"sell_q_vol": true, "sell_q_val": true, "sell_q_cnt": true,
	"prev_day_vol": true, "d1_vol": true, "max30_high": true,
	"plp_raw": true, "tmax": true, "vol_trend": true, "suspicious_vol": true,
	"d_even": true, "resistance_59": true, "dist_min30_pct": true,
	"ctv_buy_i_val": true, "ctv_buy_n_val": true,
	"ctv_sell_i_val": true, "ctv_sell_n_val": true,
}

// عینِ _KEEP_NULL — NaN در اینجا یعنی «کلید نیامد»، نه صفر.
var keepNull = map[string]bool{
	"vol_ratio": true, "vol_dod": true, "vol_trend": true, "dist_min30_pct": true,
	"p_max": true, "p_min": true, "p_first": true,
	"month_avg_vol": true, "prev_day_vol": true, "d1_vol": true,
	"prior30_vol": true, "min_low_29": true, "percent_last": true, "percent_change": true,
	"plp_raw": true, "vol_ratio_file": true, "hist_sessions": true, "tmin": true, "tmax": true,
	"buy_q1_cnt": true, "mcap": true, "mcap_src": true,
	"buyer_power": true, "buy_power_i": true, "sell_power_i": true,
	"buyer_power_raw": true, "resistance_59": true,
	"retail_buy_pct": true, "legal_buy_pct": true, "retail_sell_pct": true, "legal_sell_pct": true,
	"pct_basis": true, "ctv_d": true, "pct_is_current": true,
	"h2_max": true, "h5_max": true, "h9_max": true, "h19_max": true,
	"h29_max": true, "h39_max": true, "h49_max": true, "h59_max": true,
	"min30_low": true, "max30_high": true, "is5": true, "is6": true,
	"st_code": true, "st_title": true, "st_d": true, "st_h": true,
	"sup_flag": true, "sup_title": true, "sup_reason_count": true, "sup_reasons": true,
	"stop_state": true, "stop_since": true, "stop_reasons": true,
}

// put همان دو پاسِ پایتون را یکی می‌کند: «NaN ⇒ صفر» برایِ ستون‌هایِ عادی
// (np.nan_to_num)، «NaN ⇒ کلید نیامد» برایِ _KEEP_NULL (ماسکِ isfinite در
// _slim_records)، و «NULL ⇒ ۰» برایِ بقیه (replace/fillna(0)ِ پایتون رویِ
// ستون‌هایِ object). پس nil فقط در _KEEP_NULL کلید نمی‌سازد.
func put(rec map[string]any, name string, v any) {
	switch x := v.(type) {
	case nil:
		if keepNull[name] {
			return
		}
		rec[name] = int64(0)
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			if keepNull[name] {
				return
			}
			rec[name] = 0.0
			return
		}
		rec[name] = x
	case int64, bool:
		rec[name] = x
	case string:
		// vol_trend/pct_basis در مشتقات رشته‌اند و "" یعنی null؛ mcap_src نه:
		// رشتهٔ خالیِ آن از بانک می‌آید و مثلِ پایتون مقدار است، نه null.
		if x == "" && (name == "vol_trend" || name == "pct_basis") {
			return
		}
		rec[name] = x
	}
}

// numericCols ستون‌هایی را نشان می‌دهد که pandas آن‌ها را float64 می‌خواند:
// دستِ‌کم یک عدد و هیچ غیرعددی. NULLِ این ستون‌ها پیش از put صفرِ float64
// می‌شود (همان nan_to_num) و NULLِ ستونِ object در put به صفرِ صحیح
// (fillna(0)); هر دو در JSON «۰»اند و تفکیک فقط برایِ هم‌شکلیِ نوعِ داخلی است.
func numericCols(fr *store.Frame) map[string]bool {
	out := make(map[string]bool, len(fr.Cols))
	for name, vals := range fr.Cols {
		seen, all := false, true
		for _, v := range vals {
			switch v.(type) {
			case nil:
			case float64, int64:
				seen = true
			default:
				all = false
			}
		}
		out[name] = seen && all
	}
	return out
}

// dropUnusedFields درِ _DROP_FIELDS است، ولی رویِ ردیف‌هایِ *ساخته‌شده* و فقط
// *بعد* از ثبتِ سابقه. پایتون این صافی را در _slim_records رویِ *همهٔ* ستون‌هایِ
// قابِ نهایی می‌زند — خام و محاسبه‌شده یکی — و شاهد را پیش از آن از قابِ کامل
// می‌نویسد؛ resistance_59 هم شاهد است و هم در بدنۀ پیش‌فرض حذف می‌شود، پس
// ترتیب این دو کار باربر است.
func dropUnusedFields(recs []map[string]any) {
	for _, rec := range recs {
		for name := range dropFields {
			delete(rec, name)
		}
	}
}

// assemble ردیفِ کامل می‌سازد — بی درِ _DROP_FIELDS. حذفِ ستون‌هایِ بدنۀ پیش‌فرض
// کارِ dropUnusedFields است و بعد از ثبتِ سابقه انجام می‌شود.
func assemble(fr *store.Frame, d *board.Derived, fl *tapeflags.Flags) []map[string]any {
	n := fr.N()
	numeric := numericCols(fr)
	out := make([]map[string]any, n)
	for i := 0; i < n; i++ {
		rec := map[string]any{"ins_code": fr.Codes[i]}
		for name, vals := range fr.Cols {
			if name == "ins_code" {
				continue
			}
			if i < len(vals) {
				v := vals[i]
				if v == nil && numeric[name] && !keepNull[name] {
					v = 0.0
				}
				put(rec, name, v)
			}
		}
		// ستون‌هایِ محاسبه‌شده — همان نام‌هایی که رابط می‌خواند.
		put(rec, "tvol", d.Tvol[i])
		put(rec, "percent_change", d.PercentChange[i])
		put(rec, "percent_last", d.PercentLast[i])
		put(rec, "plp_raw", d.PlpRaw[i])
		put(rec, "buyer_power", d.BuyerPower[i])
		put(rec, "buy_power_i", d.BuyPowerI[i])
		put(rec, "sell_power_i", d.SellPowerI[i])
		put(rec, "retail_buy_pct", d.RetailBuyPct[i])
		put(rec, "legal_buy_pct", d.LegalBuyPct[i])
		put(rec, "retail_sell_pct", d.RetailSellPct[i])
		put(rec, "legal_sell_pct", d.LegalSellPct[i])
		put(rec, "pct_basis", d.PctBasis[i])
		put(rec, "vol_dod", d.VolDod[i])
		put(rec, "vol_trend", d.VolTrend[i])
		put(rec, "vol_ratio", board.Round1(fl.VolRatio[i]))
		put(rec, "vol_ratio_file", board.Round2(fl.VolRatioFile[i]))
		put(rec, "buyer_power_raw", fl.BuyerPowerRaw[i])
		put(rec, "resistance_59", fl.Resistance59[i])
		put(rec, "dist_min30_pct", d.DistMin30Pct[i])
		put(rec, "mcap", d.Mcap[i])
		// mcap_src از خودِ ستونِ قاب می‌آید (NULL ⇒ کلید نیامد، "" ⇒ مقدارِ
		// صریح)؛ درِ Derived.McapSrc فقط برایِ مصرف‌کنندگانِ داخلی است.
		rec["is_live"] = d.IsLive[i]
		rec["f_clock"] = fl.Clock[i]
		rec["f_susp"] = fl.Susp[i]
		rec["f_jet"] = fl.Jet[i]
		rec["f_roobi"] = fl.Roobi[i]
		rec["f_noqteh"] = fl.Noqteh[i]
		rec["f_smart"] = fl.Smart[i]
		rec["f_legal"] = fl.Legal[i]
		put(rec, "suspicious_vol", fl.Susp[i])
		out[i] = rec
	}
	return out
}
