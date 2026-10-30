package mstat

import "math"

// Agg همان خروجیِ _agg است: جمع‌هایِ ریالی، شمارش‌ها، و نسبت‌ها در یکایِ نمایشی.
// هر سرانه/نسبتی که پایتون None می‌دهد اینجا NaN است (قراردادِ «NaN یعنی
// NULL») و تبدیلش به null در لایهٔ JSON می‌نشیند، نه اینجا.
type Agg struct {
	N, NTraded int
	Vol, Val   float64
	RB, RS     float64
	IB, IS     float64
	NBI, NSI   int64
	NBN, NSN   int64
	BQ, SQ     float64
	BQV, SQV   float64
	DepthN     int

	PCBuymt, PCSellmt float64 // NaN = None
	Power             float64
	FlowBT, VolBS     float64
	ValBT, ValHemat   float64
	BQBt, SQBt        float64
}

func enrich(snap *Snapshot) []*Row {
	top := top50Codes(snap.Rows)
	for _, r := range snap.Rows {
		r.M = money(r, snap.BaseEst)
		r.Top50 = top[r.Code]
	}
	return snap.Rows
}

// aggOf همان _agg: یک پاس رویِ ردیف‌هایِ یک دسته. جمعِ عمق فقط رویِ ردیف‌هایی
// که bq_val دارند می‌نشیند (پایتون `if m["bq_val"] is not None`)، ولی سه
// خانهٔ دیگرِ همان ردیف با `or 0.0` خوانده می‌شوند — NaN یعنی NULL، پس صفر.
func aggOf(rows []*Row) *Agg {
	a := &Agg{}
	for _, r := range rows {
		m := r.M
		if m.Val > 0 {
			a.NTraded++
		}
		a.Vol += m.Vol
		a.Val += m.Val
		a.RB += m.RetailBuy
		a.RS += m.RetailSell
		a.IB += m.InstBuy
		a.IS += m.InstSell
		a.NBI += m.NBuyI
		a.NSI += m.NSellI
		a.NBN += m.NBuyN
		a.NSN += m.NSellN
		if !isNaN(m.BQVal) {
			a.DepthN++
			a.BQ += m.BQVal
			a.SQ += zeroIfNaN(m.SQVal)
			a.BQV += zeroIfNaN(m.BQVol)
			a.SQV += zeroIfNaN(m.SQVol)
		}
	}
	a.N = len(rows)
	a.PCBuymt = nanDiv(div(a.RB, float64(a.NBI)), 1e7)
	a.PCSellmt = nanDiv(div(a.RS, float64(a.NSI)), 1e7)
	a.Power = nanDiv(div(a.PCBuymt, a.PCSellmt), 1)
	a.FlowBT = (a.RB - a.RS) / 1e10
	a.VolBS = a.Vol / 1e9
	a.ValBT = a.Val / 1e10
	a.ValHemat = a.ValBT / 1e3
	a.BQBt = a.BQ / 1e10
	a.SQBt = a.SQ / 1e10
	return a
}

func zeroIfNaN(v float64) float64 {
	if isNaN(v) {
		return 0
	}
	return v
}

// nanDiv همان _div(نتیجه, مخرج) است: None می‌ماند None.
func nanDiv(v *float64, denom float64) float64 {
	if v == nil || denom == 0 || math.IsNaN(*v) {
		return math.NaN()
	}
	return *v / denom
}

func categoryBuckets(rows []*Row) map[string][]*Row {
	out := make(map[string][]*Row, len(categoryRows))
	for _, c := range categoryRows {
		out[c.Key] = nil
	}
	for _, r := range rows {
		for _, c := range categoryRows {
			if c.Key == "top50" {
				if r.Top50 {
					out[c.Key] = append(out[c.Key], r)
				}
			} else if inCategory(r, c.Key, nil) {
				out[c.Key] = append(out[c.Key], r)
			}
		}
	}
	return out
}

func selectRows(rows []*Row, cat string) []*Row {
	out := []*Row{}
	if cat == "top50" {
		for _, r := range rows {
			if r.Top50 {
				out = append(out, r)
			}
		}
		return out
	}
	for _, r := range rows {
		if inCategory(r, cat, nil) {
			out = append(out, r)
		}
	}
	return out
}
