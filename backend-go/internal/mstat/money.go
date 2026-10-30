package mstat

import (
	"math"
	"sort"
)

// Money همهٔ ارقامِ ریالیِ یک نماد است. هر فیلدِ اختیاری NaN می‌تواند باشد
// (یعنی NULL/«ساخته‌شدنی نبود»)؛ فقط ارقامِ تجمعیِ vol/val/trades همان
// رفتارِ _fِ پایتون را دارند و NULL در آن‌ها صفر می‌شود.
type Money struct {
	Vol, Val, Vwap, Trades float64
	BQVal, SQVal           float64
	BQVol, SQVol, BQCnt    float64
	SQCnt                  float64
	BQ1Vol, BQ1Px          float64
	SQ1Vol, SQ1Px          float64
	HasCT                  bool
	RetailBuy, RetailSell  float64
	InstBuy, InstSell      float64
	ValueSource            string
	DDDBuy                 float64
	NBuyI, NSellI          int64
	NBuyN, NSellN          int64
	PCBuy, PCSell, Power   float64
	Flow                   float64
	Base                   float64
	QState                 string
}

func cget(ct *CTRow, v float64) float64 {
	if ct == nil {
		return 0
	}
	// پایتون هر خانهٔ client_type را پیش از مصرف با _f می‌خواند؛ NULL و
	// بی‌نهایت هر دو صفر می‌شوند، نه NaN.
	return f0(v)
}

// money همان mstat_engine.money: ارزش هر گروه = مبدأ اگر بود، وگرنه حجم×VWAP.
//
// سه حالتِ value_source از شمارشِ خانه‌هایِ native می‌آید: هر چهار خانه
// بود ⇒ native، بعضی ⇒ mixed، هیچ ⇒ reconstructed. `client_type_value` فقط
// از GetClientTypeHistory پر می‌شود و آن مسیر برایِ نشستِ جاری ۵۰۰ می‌دهد؛
// پس «ردیف نیست» قاعدۀ روز است و بازسازی جایِ آن می‌نشیند — هرگز صفرِ جعلی.
func money(r *Row, baseEst map[string]float64) Money {
	// پایتون همین سه رقم را با _f می‌خواند: NULL (و بی‌نهایت) در آن‌ها صفر
	// می‌شود، نه NaN — چون جمعِ بعدیِ دسته‌ها (agg) با NaN آلوده می‌شد.
	vol, val := f0(r.QVol), f0(r.QVal)
	m := Money{
		Vol: vol, Val: val, Trades: f0(r.NTrades),
		HasCT: r.CT != nil,
	}
	ct := r.CT
	// opt(key)ِ پایتون: NULL ⇒ None (اینجا NaN)، بی‌نهایت ⇒ 0 با _f.
	m.BQVal, m.SQVal = fopt(r.BuyQVal), fopt(r.SellQVal)
	m.BQVol, m.SQVol = fopt(r.BuyQVol), fopt(r.SellQVol)
	m.BQCnt, m.SQCnt = fopt(r.BuyQCnt), fopt(r.SellQCnt)
	m.BQ1Vol, m.BQ1Px = fopt(r.BuyQ1Vol), fopt(r.BuyQ1Px)
	m.SQ1Vol, m.SQ1Px = fopt(r.SellQ1Vol), fopt(r.SellQ1Px)

	var vwap float64
	if d := div(val, vol); d != nil && *d != 0 {
		vwap = *d
	} else if p := f0(r.PClosing); p != 0 {
		vwap = p
	}
	m.Vwap = vwap

	native := map[string]float64{}
	if r.CTV != nil {
		for name, v := range map[string]float64{
			"buy_i_val": r.CTV.BuyIVal, "buy_n_val": r.CTV.BuyNVal,
			"sell_i_val": r.CTV.SellIVal, "sell_n_val": r.CTV.SellNVal,
			"buy_ddd_val": r.CTV.BuyDDDVal,
		} {
			if !isNaN(v) {
				native[name] = v
			}
		}
	}
	got := 0
	pick := func(out string, nativeKey string, vol float64) {
		if v, ok := native[nativeKey]; ok {
			switch out {
			case "retail_buy":
				m.RetailBuy = v
			case "retail_sell":
				m.RetailSell = v
			case "inst_buy":
				m.InstBuy = v
			case "inst_sell":
				m.InstSell = v
			}
			got++
			return
		}
		v := cget(ct, vol) * vwap
		switch out {
		case "retail_buy":
			m.RetailBuy = v
		case "retail_sell":
			m.RetailSell = v
		case "inst_buy":
			m.InstBuy = v
		case "inst_sell":
			m.InstSell = v
		}
	}
	pick("retail_buy", "buy_i_val", ctVal(ct, func(c *CTRow) float64 { return c.BuyIVol }))
	pick("retail_sell", "sell_i_val", ctVal(ct, func(c *CTRow) float64 { return c.SellIVol }))
	pick("inst_buy", "buy_n_val", ctVal(ct, func(c *CTRow) float64 { return c.BuyNVol }))
	pick("inst_sell", "sell_n_val", ctVal(ct, func(c *CTRow) float64 { return c.SellNVol }))
	switch {
	case got == 4:
		m.ValueSource = "native"
	case got > 0:
		m.ValueSource = "mixed"
	default:
		m.ValueSource = "reconstructed"
	}
	if v, ok := native["buy_ddd_val"]; ok {
		m.DDDBuy = v
	} else {
		m.DDDBuy = cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyDDDVol })) * vwap
	}
	// تعدادِ همان گروه؛ int()ِ پایتون به سمتِ صفر می‌برد.
	m.NBuyI = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyCountI })))
	m.NSellI = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.SellCountI })))
	m.NBuyN = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyCountN })))
	m.NSellN = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.SellCountN })))
	if v := div(m.RetailBuy, float64(m.NBuyI)); v != nil {
		m.PCBuy = *v
	} else {
		m.PCBuy = math.NaN()
	}
	if v := div(m.RetailSell, float64(m.NSellI)); v != nil {
		m.PCSell = *v
	} else {
		m.PCSell = math.NaN()
	}
	if v := div(m.PCBuy, m.PCSell); v != nil {
		m.Power = *v
	} else {
		m.Power = math.NaN()
	}
	m.Flow = m.RetailBuy - m.RetailSell
	if b, ok := baseEst[r.Code]; ok {
		m.Base = b
	} else {
		m.Base = math.NaN()
	}
	// eff_base_vol: «مبنایِ اعلامی» فقط اگر با _f معنادار باشد؛ بی‌نهایت صفر
	// است و به برآوردِ ۴ نشست می‌رسد، نه به یک عددِ بی‌معنا.
	if bv := f0(r.BaseVol); bv > 1.0 {
		m.Base = bv
	}
	m.QState = queueState(r, m)
	return m
}

func ctVal(ct *CTRow, f func(*CTRow) float64) float64 {
	if ct == nil {
		return math.NaN()
	}
	return f(ct)
}

func isEmpty(v float64) bool { return isNaN(v) || v == 0 }

// queueState همان queue_state: تک‌حرفِ وضعیتِ صف — b=خرید، s=فروش، p=مثبت،
// n=منفی، z=صفر، x=بی‌داده. نبودِ عمق x می‌دهد، نه z.
func queueState(r *Row, m Money) string {
	if isNaN(m.BQVal) {
		return "x"
	}
	if m.BQVal > 0 && isEmpty(m.SQVal) {
		return "b"
	}
	if m.SQVal > 0 && isEmpty(m.BQVal) {
		return "s"
	}
	if r.Pct == nil {
		return "x"
	}
	switch {
	case *r.Pct > 0:
		return "p"
	case *r.Pct < 0:
		return "n"
	default:
		return "z"
	}
}

// top50Codes همان top50_codes: پنجاه شرکتِ بزرگ بر پایهٔ تعدادِ سهام × پایانی.
// فقط سهامِ عادی رقابت می‌کند؛ tie با کدِ نزولی می‌شکند (sortِ reverseِ
// tuple در پایتون).
func top50Codes(rows []*Row) map[string]bool {
	type scored struct {
		cap  float64
		code string
	}
	list := []scored{}
	for _, r := range rows {
		if r.Cls != paperStock {
			continue
		}
		// پایتون: cap = _f(total_shares) * _f(p_closing) — NULL/بی‌نهایت صفر.
		cap := f0(r.TotalShares) * f0(r.PClosing)
		if cap > 0 {
			list = append(list, scored{cap, r.Code})
		}
	}
	sort.SliceStable(list, func(i, j int) bool {
		if list[i].cap != list[j].cap {
			return list[i].cap > list[j].cap
		}
		return list[i].code > list[j].code
	})
	out := map[string]bool{}
	for i, s := range list {
		if i >= 50 {
			break
		}
		out[s.code] = true
	}
	return out
}

// goldSilverLevKinds دنبالهٔ tupleِ پایتون در bonds_other
// (_ALL_FUND_KINDS + ("gold", "silver", "lev"))؛ خودِ فهرستِ صندوق‌ها از
// terms_gen.go می‌آید تا ویرایشِ mstat_engine از گارد رد نشود.
var goldSilverLevKinds = []string{"gold", "silver", "lev"}

// inCategory همان in_category: دامنه‌ها همان سطرهایِ `market0`ِ تریدرزآرنا.
func inCategory(r *Row, cat string, top50 map[string]bool) bool {
	cls, kind := r.Cls, r.Kind
	switch cat {
	case "all":
		return cls == paperStock || cls == paperRight ||
			(cls == paperFund && inStrings(kind, allFundKinds))
	case "bonds_other":
		if cls == paperStock || cls == paperRight {
			return false
		}
		if cls == paperFund {
			return !inStrings(kind, allFundKinds) && !inStrings(kind, goldSilverLevKinds)
		}
		return true
	case "eq_all":
		return cls == paperStock || cls == paperRight ||
			(cls == paperFund && inStrings(kind, eqFundKinds))
	case "stock_right":
		return cls == paperStock || cls == paperRight
	case "eq_fund":
		return cls == paperFund && inStrings(kind, eqFundKinds)
	case "fixed_fund":
		return cls == paperFund && kind == "fixed"
	case "lev_fund":
		return cls == paperFund && kind == "lev"
	case "gold_fund":
		return cls == paperFund && kind == "gold"
	case "silver_fund":
		return cls == paperFund && kind == "silver"
	case "top50":
		return top50[r.Code]
	}
	return false
}

func inStrings(s string, xs []string) bool {
	for _, x := range xs {
		if s == x {
			return true
		}
	}
	return false
}

// jnum برایِ JSON: NaN ⇒ null، وگرنه خودِ عدد.
func jnum(v float64) any {
	if isNaN(v) {
		return nil
	}
	return v
}
