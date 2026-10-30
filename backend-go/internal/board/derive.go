// Package board مشتقاتِ تابلو است — همان ستون‌هایِ محاسبه‌شدهٔ api/market.py
// (بخشِ درصد/سرانه/روند/زنده/درصدِ حقیقی-حقوقی) رویِ قابِ ستون‌محورِ store.
//
// NaN یعنی «هیچ مقدار»؛ تسکِ ۶ همین NaN را به null تبدیل می‌کند تا رابط «۰»
// را با «سنجیده نشد» قاطی نکند.
package board

import (
	"math"

	"borsterminal/backend/internal/clientsplit"
	"borsterminal/backend/internal/store"
)

// Derived ستون‌هایِ محاسبه‌شده، هم‌طولِ قاب و هم‌ترتیبِ آن.
type Derived struct {
	Tvol, MonthAvgVol, PrevDayVol []float64
	PercentChange, PercentLast    []float64
	PlpRaw                        []float64
	BuyerPower, BuyPowerI         []float64
	SellPowerI                    []float64
	VolDod                        []float64
	VolTrend                      []string // up|down|flat؛ "" یعنی null
	RetailBuyPct, LegalBuyPct     []float64
	RetailSellPct, LegalSellPct   []float64
	PctBasis                      []string // "value" یا ""
	IsLive                        []bool
	DistMin30Pct, Mcap            []float64
	McapSrc                       []string // NULL و "" را از هم جدا نمی‌کند و بدنۀ بازار از آن نمی‌خواند
}

// Round2 مثلِ round(x, 2)ِ numpy/pandas: نیم‌به‌زوج، نه نیم‌به‌بالا. ترتیبِ
// ضرب مهم است؛ همان round(x,2) = RoundToEven(x*100)/100.
func Round2(x float64) float64 { return math.RoundToEven(x*100.0) / 100.0 }

// Round1 مثلِ round(x, 1) با همان نیم‌به‌زوج.
func Round1(x float64) float64 { return math.RoundToEven(x*10.0) / 10.0 }

// Round0 مثلِ round(x) — برایِ سرانهٔ حجم به ازایِ هر معامله.
func Round0(x float64) float64 { return math.RoundToEven(x) }

// Num هر مقدارِ SQL را عدد می‌کند؛ null/رشته/[]byte/NaN ⇒ NaN. ستون‌هایِ
// عددیِ SQLite فقط float64/int64 می‌آیند، پس بقیهٔ انواع «غایب» هستند.
func Num(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case int:
		return float64(n)
	default:
		return math.NaN()
	}
}

func col(fr *store.Frame, name string) []any { return fr.Cols[name] }

// pick مقدارِ ردیفِ i را می‌دهد؛ ستونِ کوتاه/غایب ⇒ nil (یعنی NaN).
func pick(v []any, i int) any {
	if i < 0 || i >= len(v) {
		return nil
	}
	return v[i]
}

// nums ستون را هم‌طولِ قاب عدد می‌کند؛ هر خانهٔ بی‌عدد NaN می‌شود.
func nums(fr *store.Frame, name string) []float64 {
	raw := col(fr, name)
	out := make([]float64, fr.N())
	for i := range out {
		out[i] = Num(pick(raw, i))
	}
	return out
}

// Derive همهٔ مشتقاتِ تابلو را از یک قاب می‌سازد. قواعد عینِ api/market.py:
// نگهبانِ price_yesterday=1، سقفِ ۱۰۰٪ برایِ نمایش، سرانهٔ خرید/فروش با مخرجِ
// صفرِ صادق، درصدِ ارزش‌محورِ client_split، روندِ حجم و «زنده» بودنِ نشست.
func Derive(fr *store.Frame) *Derived {
	n := fr.N()
	d := &Derived{}

	// tvol: NULL/NaN → 0 (پایتون: fillna(0.0)).
	d.Tvol = nums(fr, "q_tot_tran")
	for i := range d.Tvol {
		if math.IsNaN(d.Tvol[i]) {
			d.Tvol[i] = 0
		}
	}
	d.MonthAvgVol = nums(fr, "month_avg_vol")
	d.PrevDayVol = nums(fr, "prev_day_vol")

	// ── درصدِ تغییر ────────────────────────────────────────────────────
	// TSETMC برایِ حق‌تقدم/اختیار و نمادهایِ تازه‌لیست‌شده price_yesterday را ۱
	// می‌فرستد؛ نگهبان است نه قیمت. کفِ ۱ فقط برایِ *نمایش* است (plp_raw خام
	// با قیدِ py>0 می‌ماند تا فیلترها ردیفِ درست را از دست ندهند).
	pc := nums(fr, "p_closing")
	pl := nums(fr, "p_last")
	py := nums(fr, "price_yesterday")
	chg := nums(fr, "price_change")
	pyOK := make([]float64, n)
	for i := range pyOK {
		pyOK[i] = math.NaN()
		if py[i] > 1.0 {
			pyOK[i] = py[i]
		}
	}
	d.PercentChange = make([]float64, n)
	d.PercentLast = make([]float64, n)
	d.PlpRaw = make([]float64, n)
	for i := 0; i < n; i++ {
		fromClose := Round2((pc[i] - pyOK[i]) / pyOK[i] * 100)
		// p_closing غایب باشد ولی price_change معتبر ⇒ نسبتِ رسمیِ TSETMC.
		fromChange := Round2(chg[i] / pyOK[i] * 100)
		x := fromClose
		if math.IsNaN(x) {
			x = fromChange
		}
		// درصدِ غیرممکن (بزرگ‌تر از بازهٔ مجازِ تابلو) نمایش داده نمی‌شود.
		if math.IsNaN(x) || math.Abs(x) > 100 {
			x = math.NaN()
		}
		d.PercentChange[i] = x

		y := Round2((pl[i] - pyOK[i]) / pyOK[i] * 100)
		if math.IsNaN(y) || math.Abs(y) > 100 {
			y = math.NaN()
		}
		d.PercentLast[i] = y

		r := math.NaN()
		if py[i] > 0 {
			r = Round2((pl[i] - py[i]) / py[i] * 100)
		}
		d.PlpRaw[i] = r
	}

	// ── سرانهٔ حجمِ خرید/فروش ─────────────────────────────────────────
	// مخرجِ صفر یعنی «هیچ معاملهٔ حقیقی در آن سمت نبوده» ⇒ NaN، نه ۱٫۰۰ِ
	// بی‌طرف؛ فیلترهایِ جت از همین NaNِ صادق می‌خوانند.
	bi, si := nums(fr, "buy_i_vol"), nums(fr, "sell_i_vol")
	bc, sc := nums(fr, "buy_count_i"), nums(fr, "sell_count_i")
	buyPer := make([]float64, n)
	sellPer := make([]float64, n)
	d.BuyerPower = make([]float64, n)
	d.BuyPowerI = make([]float64, n)
	d.SellPowerI = make([]float64, n)
	for i := 0; i < n; i++ {
		buyPer[i], sellPer[i] = math.NaN(), math.NaN()
		if bc[i] > 0 {
			buyPer[i] = bi[i] / bc[i]
		}
		if sc[i] > 0 {
			sellPer[i] = si[i] / sc[i]
		}
		bp := Round2(buyPer[i] / sellPer[i])
		if bp > 10.0 {
			bp = 10.0
		}
		d.BuyerPower[i] = bp
		d.BuyPowerI[i] = Round0(buyPer[i])
		d.SellPowerI[i] = Round0(sellPer[i])
	}

	// ── درصدِ حقیقی/حقوقی ─────────────────────────────────────────────
	// تنها ورودیِ چهار درصد، چهار ارزشِ مبدأِ client_type_value است؛ حجم×قیمت
	// اینجا حساب نمی‌شود و نبودِ ارزش برایِ همان نمادِ همان نشست «نامشخص» است.
	d.RetailBuyPct = make([]float64, n)
	d.LegalBuyPct = make([]float64, n)
	d.RetailSellPct = make([]float64, n)
	d.LegalSellPct = make([]float64, n)
	d.PctBasis = make([]string, n)
	biV, bnV := col(fr, "ctv_buy_i_val"), col(fr, "ctv_buy_n_val")
	siV, snV := col(fr, "ctv_sell_i_val"), col(fr, "ctv_sell_n_val")
	put := func(dst []float64, i int, p *float64) {
		if p == nil {
			dst[i] = math.NaN()
			return
		}
		dst[i] = *p
	}
	for i := 0; i < n; i++ {
		s := clientsplit.Shares(pick(biV, i), pick(bnV, i), pick(siV, i), pick(snV, i))
		put(d.RetailBuyPct, i, s.RetailBuy)
		put(d.LegalBuyPct, i, s.LegalBuy)
		put(d.RetailSellPct, i, s.RetailSell)
		put(d.LegalSellPct, i, s.LegalSell)
		if s.Basis != nil {
			d.PctBasis[i] = *s.Basis
		}
	}

	// ── روندِ حجم: tvol نسبت به آخرین روزِ معامله‌شده ─────────────────
	// pdv<=0/NaN ⇒ vol_dod و vol_trend هر دو null (نه ۰ یعنی «افتِ کامل»).
	d.VolDod = make([]float64, n)
	d.VolTrend = make([]string, n)
	for i := 0; i < n; i++ {
		pdv := math.NaN()
		if d.PrevDayVol[i] > 0 {
			pdv = d.PrevDayVol[i]
		}
		d.VolDod[i] = Round2(d.Tvol[i] / pdv)
		switch {
		case math.IsNaN(d.VolDod[i]):
			d.VolTrend[i] = ""
		case d.VolDod[i] >= 1.10:
			d.VolTrend[i] = "up"
		case d.VolDod[i] <= 0.90:
			d.VolTrend[i] = "down"
		default:
			d.VolTrend[i] = "flat"
		}
	}

	// ── زنده = تازه‌ترین d_evenِ همین قاب ────────────────────────────
	// ردیف‌هایِ نشستِ پیشین (فسیل) درِ محاسبه می‌مانند ولی «زنده» نیستند.
	de := nums(fr, "d_even")
	maxDe := math.Inf(-1)
	for _, v := range de {
		if !math.IsNaN(v) && v > maxDe {
			maxDe = v
		}
	}
	d.IsLive = make([]bool, n)
	for i := 0; i < n; i++ {
		d.IsLive[i] = !math.IsNaN(de[i]) && de[i] == maxDe
	}

	// فاصله از کفِ ۳۰ روزه، بر مبنایِ قیمتِ پایانی.
	min30 := nums(fr, "min30_low")
	d.DistMin30Pct = make([]float64, n)
	for i := 0; i < n; i++ {
		d.DistMin30Pct[i] = Round2((pc[i] - min30[i]) / pc[i] * 100)
	}

	// mcap/mcap_src همان SQLِ fts_engine است (بانِ مرده درِ store اعمال شده)؛
	// اینجا فقط خوانده می‌شود. "" یعنی کلید نبود، نه صفر.
	d.Mcap = nums(fr, "mcap")
	d.McapSrc = make([]string, n)
	for i := 0; i < n; i++ {
		if s, ok := pick(col(fr, "mcap_src"), i).(string); ok {
			d.McapSrc[i] = s
		}
	}
	return d
}
