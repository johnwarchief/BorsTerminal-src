package fundamental

// پورتِ api/fundamental.py:freshness_of (2279-2439) و freshness_bulk/route.
// `as_of` تاریخِ منبع است، نه ساعتِ اجرا؛ ترتیبِ وضعیت quarantined > stale >
// missing > fresh. هیچ جدول یا آستانهٔ تازه‌ای ساخته نمی‌شود.

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/symbolid"
)

const (
	freshnessCacheTTL = 60 * time.Second
	freshnessCacheMax = 32
)

type freshnessEntry struct {
	stamp time.Time
	body  map[string]any
}

var (
	freshnessMu    sync.Mutex
	freshnessCache = map[string]freshnessEntry{}
)

// asOfISO عینِ `_asof_iso`: تاریخِ فقط-روز همان می‌ماند؛ برچسبِ زمان‌دار به
// ISO-8601 با منطقهٔ تهران می‌رود؛ مقدارِ نامفهوم دست‌نخورده برمی‌گردد.
func asOfISO(value any) any {
	s := strings.TrimSpace(strOr(value))
	if s == "" {
		return nil
	}
	if len(s) == 10 && s[4] == '-' && s[7] == '-' {
		return s
	}
	if len(s) >= 19 && s[10] == ' ' {
		return s[:10] + "T" + s[11:19] + "+03:30"
	}
	return s
}

func freshMinString(xs []string) any {
	if len(xs) == 0 {
		return nil
	}
	sort.Strings(xs)
	return xs[0]
}

// freshnessOf عینِ `freshness_of(conn, symbol)`.
func (s *Service) freshnessOf(ctx context.Context, symbol string) map[string]any {
	variants := []string{symbol}
	if vs, err := s.sid.Variants(ctx, symbol, symbolid.Codal); err == nil {
		seen := map[string]bool{symbol: true}
		for _, v := range vs {
			if v != "" && !seen[v] {
				seen[v] = true
				variants = append(variants, v)
			}
		}
	}

	var msTracing, msPeriod, msPub any
	msIn, msArgs := inPlaceholders(variants)
	rows, qerr := s.msQuery(ctx, "SELECT ms.tracing_no, ms.period_end, n.publish_date"+
		" FROM monthly_sales ms LEFT JOIN codal_notices n ON n.tracing_no = ms.tracing_no"+
		" WHERE ms.symbol IN ("+msIn+") ORDER BY "+period.OrderExpr("ms")+
		", ms.tracing_no DESC LIMIT 1", msArgs)
	if qerr == nil && len(rows) > 0 && len(rows[0]) >= 3 {
		msTracing, msPeriod, msPub = rows[0][0], rows[0][1], rows[0][2]
	}

	var fsTracing, fsPeriod, fsPub any
	if rows, err := s.AnnualStatements(ctx, symbol, false, false, 6); err == nil {
		if ref := PickReference(rows, nil); len(ref) > 0 {
			fsTracing = ref["tracing_no"]
			fsPeriod = ref["period_end"]
			if pubRows, qerr := s.msQuery(ctx,
				"SELECT publish_date FROM financial_statements WHERE tracing_no=?",
				[]any{fsTracing}); qerr == nil && len(pubRows) > 0 && len(pubRows[0]) > 0 {
				fsPub = pubRows[0][0]
			}
		}
	}

	var board any
	bpred, bargs, berr := s.sid.Pred(ctx, "i.l_val18", symbol, symbolid.Board)
	if berr != nil {
		bpred, bargs = "i.l_val18 = ?", []any{symbol}
	}
	if brows, qerr := s.msQuery(ctx, "SELECT MAX(m.d_even) FROM instruments i"+
		" JOIN market_watch m ON m.ins_code = i.ins_code WHERE "+bpred, bargs); qerr == nil &&
		len(brows) > 0 && len(brows[0]) > 0 {
		board = brows[0][0]
	}

	dirty := map[string]string{}
	if placeholders, args := inPlaceholders(variants); placeholders != "" {
		if rows, err := s.msQuery(ctx, "SELECT axis, reason FROM pipeline_dirty WHERE symbol IN ("+
			placeholders+")", args); err == nil {
			for _, r := range rows {
				ax := strOr(r[0])
				if _, seen := dirty[ax]; !seen {
					dirty[ax] = strOr(r[1])
				}
			}
		}
	}

	type qEntry struct {
		err string
		pub any
	}
	qLatest := map[string]qEntry{}
	qIn, qArgs := inPlaceholders(variants)
	if qrows, qerr := s.msQuery(ctx,
		"SELECT e.kind, e.last_error, n.publish_date FROM codal_extracted e"+
			" JOIN codal_notices n ON n.tracing_no = e.tracing_no"+
			" WHERE e.state='quarantined' AND n.symbol IN ("+qIn+")"+
			" ORDER BY e.kind, "+period.PubOrderExpr("n.publish_date"), qArgs); qerr == nil {
		for _, r := range qrows {
			kind := strOr(r[0])
			if kind != "ms" && kind != "fs" {
				continue
			}
			if _, seen := qLatest[kind]; !seen {
				qLatest[kind] = qEntry{err: strOr(r[1]), pub: r[2]}
			}
		}
	}

	canonPub := map[string]string{}
	if s := pubKeyOf(msPub); s != "" {
		canonPub["ms"] = s
	}
	if s := pubKeyOf(fsPub); s != "" {
		canonPub["fs"] = s
	}
	qAxes := map[string]string{}
	qMap := map[string][]string{
		"ms": {"1_growth", "4_sales_to_mcap"},
		"fs": {"2_eps_trend", "3_gross_margin"},
	}
	for _, kind := range []string{"ms", "fs"} {
		entry, ok := qLatest[kind]
		if !ok {
			continue
		}
		if cPub, known := canonPub[kind]; known {
			qKey := pubKeyOf(entry.pub)
			if qKey == "" || qKey < cPub {
				continue
			}
		}
		for _, ax := range qMap[kind] {
			if _, exists := qAxes[ax]; !exists {
				reason := entry.err
				if reason == "" {
					reason = "validation"
				}
				qAxes[ax] = reason
			}
		}
	}

	boardISO := ""
	if board != nil {
		if n, ok := toI(board); ok && n != 0 {
			bs := fmt.Sprintf("%08d", n)
			boardISO = bs[:4] + "-" + bs[4:6] + "-" + bs[6:8]
		}
	}

	msAsof := ""
	if msTracing != nil {
		if v := period.J2GDate(strOr(msPub)); v != nil {
			msAsof = *v
		} else if v := period.J2GDate(strOr(msPeriod)); v != nil {
			msAsof = *v
		}
	}
	fsAsof := ""
	if fsTracing != nil {
		if v := period.J2GDate(strOr(fsPub)); v != nil {
			fsAsof = *v
		} else if v := period.J2GDate(strOr(fsPeriod)); v != nil {
			fsAsof = *v
		}
	}
	// مثلِ پایتون، مقایسهٔ محورِ ۴ رویِ همان ISO انجام می‌شود، نه رشتهٔ خامِ
	// «YYYY-MM-DD HH:MM:SS» که ترتیبِ واژگانی‌اش با تاریخِ فقط-روز یکی نیست.
	msAsof = isoString(msAsof)
	fsAsof = isoString(fsAsof)

	axis := func(name, source, asOf string, tracingNo, periodEnd any, present bool) map[string]any {
		state := "missing"
		reason := ""
		if present {
			if _, isDirty := dirty[name]; isDirty {
				state = "stale"
			} else {
				state = "fresh"
			}
		}
		if r, isQ := qAxes[name]; isQ {
			state = "quarantined"
			reason = r
		} else if state == "stale" {
			reason = dirty[name]
		}
		var canonicalEnd any
		if pe := period.Canonicalize(periodEnd); pe != nil {
			canonicalEnd = *pe
		}
		asOfVal := asOfISO(asOf)
		return map[string]any{
			"as_of": asOfVal, "source": source,
			"tracing_no": tracingNo, "period_end": canonicalEnd,
			"state": state, "reason": reason,
		}
	}

	salesAsof := ""
	if msAsof != "" && boardISO != "" {
		salesAsof = msAsof
		if boardISO > salesAsof {
			salesAsof = boardISO
		}
	} else if msAsof != "" {
		salesAsof = msAsof
	} else {
		salesAsof = boardISO
	}

	axes := map[string]any{
		"1_growth": axis("1_growth", "monthly_sales", msAsof,
			msTracing, msPeriod, msTracing != nil),
		"2_eps_trend": axis("2_eps_trend", "financial_statements", fsAsof,
			fsTracing, fsPeriod, fsTracing != nil),
		"3_gross_margin": axis("3_gross_margin", "financial_statements", fsAsof,
			fsTracing, fsPeriod, fsTracing != nil),
		"4_sales_to_mcap": axis("4_sales_to_mcap", "monthly_sales+market_watch", salesAsof,
			msTracing, msPeriod, msTracing != nil && boardISO != ""),
		"5_industry": axis("5_industry", "instruments", boardISO,
			nil, nil, boardISO != ""),
	}
	fundStamps := []string{}
	for _, k := range []string{"1_growth", "2_eps_trend", "3_gross_margin"} {
		if ax, ok := axes[k].(map[string]any); ok {
			if v, ok := ax["as_of"].(string); ok && v != "" {
				fundStamps = append(fundStamps, v)
			}
		}
	}
	return map[string]any{
		"symbol": symbol,
		"as_of":  freshMinString(fundStamps),
		"axes":   axes,
	}
}

func pubKeyOf(v any) string {
	if v == nil {
		return ""
	}
	if k := period.PubKey(strOr(v)); k != nil {
		return *k
	}
	return ""
}

func isoString(raw string) string {
	if s, ok := asOfISO(raw).(string); ok {
		return s
	}
	return ""
}

func inPlaceholders(values []string) (string, []any) {
	parts := make([]string, 0, len(values))
	args := make([]any, 0, len(values))
	for _, v := range values {
		parts = append(parts, "?")
		args = append(args, v)
	}
	return strings.Join(parts, ","), args
}

// FreshnessBody عینِ `freshness_bulk`: کشِ ۶۰ثانیه‌ایِ process-local با سقفِ ۳۲.
func (s *Service) FreshnessBody(ctx context.Context, symbols []string) (map[string]any, error) {
	clean := make([]string, 0, len(symbols))
	for _, sym := range symbols {
		if t := strings.TrimSpace(sym); t != "" {
			clean = append(clean, t)
		}
	}
	keyParts := append([]string(nil), clean...)
	sort.Strings(keyParts)
	key := strings.Join(keyParts, "\x00")
	freshnessMu.Lock()
	if hit, ok := freshnessCache[key]; ok && time.Since(hit.stamp) < freshnessCacheTTL {
		freshnessMu.Unlock()
		return hit.body, nil
	}
	freshnessMu.Unlock()

	items := make([]any, 0, len(clean))
	for _, sym := range clean {
		items = append(items, s.freshnessOf(ctx, sym))
	}
	body := map[string]any{"status": "success", "count": len(clean), "items": items}

	freshnessMu.Lock()
	freshnessCache[key] = freshnessEntry{stamp: time.Now(), body: body}
	if len(freshnessCache) > freshnessCacheMax {
		freshnessCache = map[string]freshnessEntry{}
		freshnessCache[key] = freshnessEntry{stamp: time.Now(), body: body}
	}
	freshnessMu.Unlock()
	return body, nil
}
