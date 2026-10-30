package mstat

import (
	"database/sql"
	"sort"
	"strings"

	"borsterminal/backend/internal/pyround"
)

type industryBucket struct {
	name        string
	n, pos, neg int
	val, flow   float64
	bq, sq      float64
	pctSum      float64
	nPct        int
}

// outRow یک سطرِ در حالِ ساختِ پاسخ است؛ rankFlow nil یعنی «رتبه ندارد»
// (خروجِ پول)، نه صفر. نوع در سطحِ بستهٔ بالاتر از تابع است تا هم‌خانواده‌های
// sort و flowVal بتوانند به آن اشاره کنند.
type outRow struct {
	industry    string
	symbols     int
	positive    int
	negative    int
	avgPct      any
	valueBT     float64
	flowBT      any
	flowPct     any
	buyQueue    float64
	sellQueue   float64
	rankValue   int
	rankFlow    any
	leaderScore int
	leader      bool
}

// industriesPanel همان industriesِ پایتون: هر صنعت با شمارِ مثبت/منفی، ارزش،
// جریان و صف‌ها؛ سپس رتبه‌بندیِ دو‌معیارهٔ FTS (ارزش + ورودِ پولِ خرد) و
// لیدرِ روز. هیچ کوئریِ تازه‌ای زده نمی‌شود — همه از همان enrich می‌آید.
func industriesPanel(db *sql.DB) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	by := map[string]*industryBucket{}
	order := []string{}
	for _, r := range rows {
		if r.Cls != paperStock && r.Cls != paperRight {
			continue
		}
		// پایتون نامِ صنعت را با str.strip() می‌خواند؛ نامِ با فاصلهٔ دو سر
		// (یا NBSP) باید همان صنعت باشد، نه صنعتی تازه با نامِ آلوده.
		nm := strings.TrimSpace(r.SectorName)
		if nm == "" {
			continue
		}
		b := by[nm]
		if b == nil {
			b = &industryBucket{name: nm}
			by[nm] = b
			order = append(order, nm)
		}
		b.n++
		if r.Pct != nil && *r.Pct > 0 {
			b.pos++
		} else if r.Pct != nil && *r.Pct < 0 {
			b.neg++
		}
		// میانگینِ درصد فقط رویِ نمادهایی که واقعاً درصد دارند؛ بی‌داده در
		// مخرج نمی‌نشیند (وگرنه میانگین به سمتِ صفر کشیده می‌شد).
		if r.Pct != nil {
			b.pctSum += *r.Pct
			b.nPct++
		}
		b.val += r.M.Val
		b.flow += r.M.Flow
		b.bq += zeroIfNaN(r.M.BQVal)
		b.sq += zeroIfNaN(r.M.SQVal)
	}
	out := make([]*outRow, 0, len(order))
	for _, nm := range order {
		b := by[nm]
		traded := b.val > 0
		var flow any
		var flowPct any
		// صنعتِ بی‌معامله «جریانِ اندازه‌گیری‌نشده» دارد، نه صفر؛ None تا در
		// صدرِ «ورودِ پول» صفرِ سبزِ جعلی نگیرد.
		if traded {
			flow = pyround.Round(b.flow/1e10, 1)
			flowPct = pyround.Round(100.0*b.flow/b.val, 2)
		}
		var avg any
		if b.nPct > 0 {
			avg = pyround.Round(b.pctSum/float64(b.nPct), 2)
		}
		out = append(out, &outRow{
			industry: nm, symbols: b.n, positive: b.pos, negative: b.neg,
			avgPct: avg, valueBT: pyround.Round(b.val/1e10, 1), flowBT: flow,
			flowPct:  flowPct,
			buyQueue: pyround.Round(b.bq/1e10, 1), sellQueue: pyround.Round(b.sq/1e10, 1),
		})
	}
	byVal := append([]*outRow(nil), out...)
	sort.SliceStable(byVal, func(i, j int) bool { return byVal[i].valueBT > byVal[j].valueBT })
	rankVal := map[string]int{}
	for i, x := range byVal {
		rankVal[x.industry] = i + 1
	}
	byFlow := []*outRow{}
	for _, x := range out {
		if x.flowBT != nil && x.flowBT.(float64) > 0 {
			byFlow = append(byFlow, x)
		}
	}
	sort.SliceStable(byFlow, func(i, j int) bool {
		return byFlow[i].flowBT.(float64) > byFlow[j].flowBT.(float64)
	})
	rankFlow := map[string]int{}
	for i, x := range byFlow {
		rankFlow[x.industry] = i + 1
	}
	for _, x := range out {
		rv := rankVal[x.industry]
		rf, ok := rankFlow[x.industry]
		x.rankValue = rv
		if ok {
			x.rankFlow = rf
		}
		// (rv or len(out)) + (rf if rf else len(out)+1)؛ rank_value همیشه ≥۱
		// است، پس جای‌گزینِ `rv or` هرگز نمی‌نشیند.
		if ok {
			x.leaderScore = rv + rf
		} else {
			x.leaderScore = rv + (len(out) + 1)
		}
	}
	leader := ""
	if len(out) > 0 {
		cand := append([]*outRow(nil), out...)
		sort.SliceStable(cand, func(i, j int) bool { return cand[i].leaderScore < cand[j].leaderScore })
		top := cand[0]
		if top.rankValue <= 5 && top.rankFlow != nil && top.rankFlow.(int) <= 5 {
			leader = top.industry
		}
	}
	for _, x := range out {
		x.leader = x.industry == leader
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].valueBT != out[j].valueBT {
			return out[i].valueBT > out[j].valueBT
		}
		return flowVal(out[i]) > flowVal(out[j])
	})
	rowsOut := make([]map[string]any, 0, len(out))
	for _, x := range out {
		rowsOut = append(rowsOut, map[string]any{
			"industry": x.industry, "symbols": x.symbols,
			"positive": x.positive, "negative": x.negative,
			"avg_pct": x.avgPct, "value_b_toman": x.valueBT,
			"flow_b_toman": x.flowBT, "flow_pct_of_value": x.flowPct,
			"buy_queue_b_toman": x.buyQueue, "sell_queue_b_toman": x.sellQueue,
			"rank_value": x.rankValue, "rank_flow": x.rankFlow,
			"leader_score": x.leaderScore, "leader": x.leader,
		})
	}
	// `source` همان ثابتِ پوششِ مسیر در پایتون است (api/market_status._mstat_compute
	// با setdefault رویِ هر پنل می‌نشاند)؛ بدنهٔ HTTP بدونِ آن با طلایی یکی نیست.
	return map[string]any{"status": "ok", "source": "local:market.db",
		"asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"rows": rowsOut, "leader": nilIfEmpty(leader)}, nil
}

func flowVal(x *outRow) float64 {
	if x.flowBT == nil {
		return 0
	}
	return x.flowBT.(float64)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
