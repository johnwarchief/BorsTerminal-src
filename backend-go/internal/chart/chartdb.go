package chart

import (
	"context"
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"

	candlecontract "borsterminal/backend/internal/candle"
	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// dEvenToDate معادلِ _d_even_to_date: 20260928 → '2026-09-28'؛ بی‌اعتبار ⇒ "".
func dEvenToDate(v any) string {
	var s string
	switch x := v.(type) {
	case nil:
		return ""
	case string:
		s = x
	case []byte:
		s = string(x)
	case int64:
		s = fmt.Sprintf("%d", x)
	case float64:
		// str(20260928.0) درِ پایتون ده نویسه است و بی‌اعتبار می‌ماند؛ هیچ
		// عددِ شناوری تاریخِ هشت‌رقمه نمی‌سازد.
		return ""
	default:
		s = fmt.Sprint(x)
	}
	s = strings.TrimSpace(s)
	if len(s) != 8 {
		return ""
	}
	for i := 0; i < 8; i++ {
		if s[i] < '0' || s[i] > '9' {
			return ""
		}
	}
	return s[:4] + "-" + s[4:6] + "-" + s[6:]
}

// factorsFromEvents معادلِ _factors_from_events: factor(t) = ∏ ratio رویدادهای
// date > t (پیمایشِ معکوسِ O(n+m) با گردکردنِ ده رقم).
func factorsFromEvents(times []string, events []adjustEvent) []float64 {
	ev := append([]adjustEvent(nil), events...)
	sort.SliceStable(ev, func(i, j int) bool { return ev[i].Date < ev[j].Date })
	dates := make([]string, len(ev))
	ratios := make([]float64, len(ev))
	for i, e := range ev {
		dates[i] = e.Date
		ratios[i] = e.Ratio
		if ratios[i] == 0 {
			ratios[i] = 1.0
		}
	}
	out := make([]float64, len(times))
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

// watchLiveBar معادلِ _watch_live_bar: کندلِ جلسهٔ جاری از market_watch با
// تاریخِ خودِ جلسه، و خطا بی‌خاموشی.
func (s *Service) watchLiveBar(ctx context.Context, symbol, afterDate string) (map[string]any, string) {
	p18, a18, err18 := s.sid.Pred(ctx, "i.l_val18", symbol, symbolid.Board)
	p30, a30, err30 := s.sid.Pred(ctx, "i.l_val30", symbol, symbolid.Board)
	if err18 != nil || err30 != nil {
		p18, a18 = "i.l_val18 = ?", []any{symbol}
		p30, a30 = "i.l_val30 = ?", []any{symbol}
	}
	params := append(append([]any{}, a18...), a30...)
	q := "SELECT m.price_first, m.price_max, m.price_min, m.p_closing, m.q_tot_tran, " +
		"m.d_even, m.p_last " +
		"FROM instruments i LEFT JOIN market_watch m ON i.ins_code = m.ins_code " +
		"WHERE (" + p18 + " OR " + p30 + ") AND m.p_closing > 0 " +
		"ORDER BY m.d_even DESC LIMIT 1"
	var first, maxP, minP, closing, qty, lastV sql.NullFloat64
	var dEven any
	err := s.market.QueryRowContext(ctx, q, params...).Scan(&first, &maxP, &minP,
		&closing, &qty, &dEven, &lastV)
	if err == sql.ErrNoRows {
		return nil, ""
	}
	if err != nil {
		return nil, fmt.Sprintf("%T: %v", err, err)
	}
	sessionDate := dEvenToDate(dEven)
	if sessionDate == "" || (afterDate != "" && sessionDate <= afterDate) {
		return nil, ""
	}
	pFirst := orZero(first)
	pMax := orZero(maxP)
	pMin := orZero(minP)
	pClose := closing.Float64
	vol := orZero(qty)
	pLast := orZero(lastV)
	if vol <= 0 {
		return nil, ""
	}
	o := pFirst
	if o <= 0 {
		o = pClose
	}
	hi, lo := candlecontract.Widen(o, pMax, pMin, pClose)
	bar := map[string]any{
		"time": sessionDate, "open": o, "high": hi, "low": lo,
		"close": pClose, "volume": vol,
	}
	if pLast > 0 {
		bar["last"] = pLast
	} else {
		bar["last"] = nil
	}
	return bar, ""
}

func orZero(v sql.NullFloat64) float64 {
	if v.Valid {
		return v.Float64
	}
	return 0
}

// corporateEvents معادلِ _corporate_events: نشانه‌هایِ مبدأ، نمایشی — هیچ
// ضریبِ تازه‌ای اینجا ساخته نمی‌شود. جدولِ نبود ⇒ [].
func (s *Service) corporateEvents(ctx context.Context, symbol string) []map[string]any {
	pred, params := s.pred(ctx, "l_val18", symbol)
	q := fmt.Sprintf("SELECT ins_code FROM instruments WHERE %s ORDER BY updated_at DESC LIMIT 1", pred)
	var ins any
	if err := s.market.QueryRowContext(ctx, q, params...).Scan(&ins); err != nil {
		return []map[string]any{}
	}
	insCode := stringValue(ins)
	out := []map[string]any{}
	rs, err := s.market.QueryContext(ctx,
		"SELECT d_even, p_closing_not_adjusted, p_closing, source FROM price_adjust_events "+
			"WHERE ins_code=? ORDER BY d_even", insCode)
	if err != nil {
		return []map[string]any{}
	}
	for rs.Next() {
		var d, src any
		var raw, adj any
		if err := rs.Scan(&d, &raw, &adj, &src); err != nil {
			rs.Close()
			return []map[string]any{}
		}
		dt := dEvenToDate(d)
		if dt == "" {
			continue
		}
		out = append(out, map[string]any{"date": dt, "type": "priceAdjust",
			"from": jsonValue(raw), "to": jsonValue(adj), "source": sourceOr(src)})
	}
	rs.Close()
	if err := rs.Err(); err != nil {
		return []map[string]any{}
	}
	rs2, err := s.market.QueryContext(ctx,
		"SELECT d_even, shares_old, shares_new, source FROM share_change_events "+
			"WHERE ins_code=? ORDER BY d_even", insCode)
	if err != nil {
		return []map[string]any{}
	}
	for rs2.Next() {
		var d, src any
		var oldV, newV any
		if err := rs2.Scan(&d, &oldV, &newV, &src); err != nil {
			rs2.Close()
			return []map[string]any{}
		}
		dt := dEvenToDate(d)
		if dt == "" {
			continue
		}
		out = append(out, map[string]any{"date": dt, "type": "shareChange",
			"from": jsonValue(oldV), "to": jsonValue(newV), "source": sourceOr(src)})
	}
	rs2.Close()
	if err := rs2.Err(); err != nil {
		return []map[string]any{}
	}
	sort.SliceStable(out, func(i, j int) bool {
		return out[i]["date"].(string) < out[j]["date"].(string)
	})
	return out
}

func sourceOr(v any) any {
	sv := stringValue(v)
	if sv == "" {
		return "tsetmc"
	}
	return sv
}

func stringValue(v any) string {
	switch x := v.(type) {
	case nil:
		return ""
	case string:
		return x
	case []byte:
		return string(x)
	case int64:
		return fmt.Sprintf("%d", x)
	case float64:
		return strings.TrimSuffix(fmt.Sprintf("%.10g", x), ".0")
	default:
		return fmt.Sprint(x)
	}
}

// jsonValue مقدارِ ستون را برایِ JSON آماده می‌کند ([]byte ⇒ رشته).
func jsonValue(v any) any {
	switch x := v.(type) {
	case nil:
		return nil
	case []byte:
		return string(x)
	case int64:
		return float64(x)
	default:
		return x
	}
}

// scaleCandles معادلِ _fts_scaled: ضربِ هندسه در ضریبِ تعدیل با گردِ +۰٫۵
// پایین‌گرد، سه ستونِ جدا (closing/last/close) و در پایان price_basis.
func (s *Service) scaleCandles(rows []map[string]any, factors, volumes []map[string]any, basis string) []map[string]any {
	fac := map[string]float64{}
	for _, x := range factors {
		if x == nil {
			continue
		}
		k, ok := toFloat(x["factor"])
		if !ok || k == 0 {
			k = 1.0
		}
		fac[stringValue(x["time"])] = k
	}
	vol := map[string]float64{}
	for _, x := range volumes {
		if x == nil {
			continue
		}
		v, ok := toFloat(x["value"])
		if !ok {
			v = 0
		}
		vol[stringValue(x["time"])] = v
	}
	r := func(v float64) float64 {
		if v >= 0 {
			return float64(int64(floorv(v + 0.5)))
		}
		return v
	}
	out := []map[string]any{}
	for _, c := range rows {
		if c == nil {
			continue
		}
		t := stringValue(c["time"])
		if len(t) < 10 {
			continue
		}
		k, ok := fac[t[:10]]
		if !ok {
			k = 1.0
		}
		// `if not k > 0` درِ پایتون NaN را هم به ۱.۰ می‌برد (NaN > 0 تهی است).
		if math.IsNaN(k) || k <= 0 {
			k = 1.0
		}
		o := numOr0(c["open"])
		h := numOr0(c["high"])
		l := numOr0(c["low"])
		var anchor float64
		if v := c["closing"]; v != nil {
			anchor = numOr0(v)
		} else if v := c["close_raw"]; v != nil {
			anchor = numOr0(v)
		} else {
			anchor = numOr0(c["close"])
		}
		var last any
		if pyTruthy(c["last"]) {
			last = r(numOr0(c["last"]) * k)
		}
		volV := numOr0(c["volume"])
		if x, ok := vol[t[:10]]; ok {
			volV = x
		}
		row := map[string]any{
			"time": t[:10], "open": r(o * k), "high": r(h * k), "low": r(l * k),
			"volume": r(volV / k),
		}
		if anchor > 0 {
			row["closing"] = r(anchor * k)
		} else {
			row["closing"] = nil
		}
		row["last"] = last
		out = append(out, row)
	}
	pricebasis.ApplyBasis(out, false, basis)
	sort.SliceStable(out, func(i, j int) bool {
		return out[i]["time"].(string) < out[j]["time"].(string)
	})
	return out
}

func numOr0(v any) float64 {
	f, ok := toFloat(v)
	if !ok {
		return 0
	}
	return f
}

func floorv(x float64) float64 { return math.Floor(x) }

// chartDBBody معادلِ get_chart_db: تاریخچۀ کامل + کندلِ زنده + تعدیل + fts.
func (s *Service) chartDBBody(ctx context.Context, symbol string, adjustment int) map[string]any {
	rows, err := s.priceHistoryFull(ctx, symbol)
	if err != nil {
		return map[string]any{"status": "error", "message": err.Error()}
	}
	lastDBDate := ""
	if len(rows) > 0 {
		lastDBDate = stringValue(rows[len(rows)-1]["time"])
	}
	bar, liveErr := s.watchLiveBar(ctx, symbol, lastDBDate)
	liveInjected := bar != nil
	if liveInjected {
		rows = append(rows, bar)
	}
	vols := make([]map[string]any, 0, len(rows))
	times := make([]string, 0, len(rows))
	for _, c := range rows {
		cl := numOr0(c["close"])
		op := numOr0(c["open"])
		color := "#f43f5e"
		if cl >= op {
			color = "#10b981"
		}
		vols = append(vols, map[string]any{
			"time": c["time"], "value": numOr0(c["volume"]), "color": color})
		times = append(times, stringValue(c["time"]))
	}
	evs := s.storedAdjustEvents(ctx, symbol)
	src := s.storedAdjustSource(ctx, symbol)
	if len(evs) > 0 {
		src = "local-cache"
	} else if src == "" {
		src = "local-db-unseen"
	}
	cap := s.adjustCapability(evs, src)
	var fctEvents []adjustEvent
	if pyTruthy(cap["combined_available"]) {
		fctEvents = evs
	}
	fct := factorsFromEvents(times, fctEvents)
	facts := make([]map[string]any, 0, len(rows))
	for i, c := range rows {
		facts = append(facts, map[string]any{"time": c["time"], "factor": fct[i]})
	}
	evMaps := make([]map[string]any, 0, len(evs))
	for _, e := range evs {
		var date any = e.Date
		if e.NullDate {
			date = nil
		}
		evMaps = append(evMaps, map[string]any{"date": date, "ratio": e.Ratio})
	}
	var fts any
	// پایتون این صدازدن را در try می‌گذارد و خطا را `fts: null` می‌کند؛ چارت
	// هرگز بی‌تحلیل نمی‌میرد. get_chart_db entry_hint نمی‌دهد (فقط /api/fts).
	if body, failure := s.analyzeCandlesSafe(
		s.scaleCandles(rows, facts, vols, s.basis.Current()), nil); failure == "" {
		fts = body
	}
	body := map[string]any{
		"status": "success", "symbol": symbol, "count": len(rows),
		"candles": rows, "volumes": vols, "factors": facts,
		"adjustEvents": evMaps, "adjustSource": src, "adjustCapability": cap,
		"corporateEvents": s.corporateEvents(ctx, symbol),
		"liveInjected":    liveInjected, "liveError": nilIfEmpty(liveErr),
		"adjustment": adjustment, "fts": fts,
	}
	return pricebasis.ResolvePayload(body, "candles",
		[2]string{"#10b981", "#f43f5e"}, s.basis.Current())
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// priceHistoryFull تاریخچۀ کاملِ نماد را برمی‌گرداند (بدونِ limit) با حذفِ
// تکرارِ روز — پرحجم‌تر می‌ماند — و ترتیبِ صعودی.
func (s *Service) priceHistoryFull(ctx context.Context, symbol string) ([]map[string]any, error) {
	pred, params := s.pred(ctx, "symbol", symbol)
	q := fmt.Sprintf("SELECT date, open, high, low, close, volume, last, value "+
		"FROM price_history WHERE %s ORDER BY date DESC, volume DESC", pred)
	rs, err := s.market.QueryContext(ctx, q, params...)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	seen := map[string]bool{}
	rows := []map[string]any{}
	for rs.Next() {
		var date string
		var open, high, low, closeP, volume, last, value sql.NullFloat64
		if err := rs.Scan(&date, &open, &high, &low, &closeP, &volume, &last, &value); err != nil {
			return nil, err
		}
		if seen[date] {
			continue
		}
		seen[date] = true
		if !open.Valid || !high.Valid || !low.Valid || !closeP.Valid {
			return nil, fmt.Errorf("float() argument must be a string or a real number, not 'NoneType'")
		}
		row := map[string]any{
			"time": date, "open": open.Float64, "high": high.Float64,
			"low": low.Float64, "close": closeP.Float64,
			"last": numOrNil(last), "value": numOrNil(value),
			"volume": orZero(volume),
		}
		rows = append(rows, row)
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	reverseRows(rows)
	return rows, nil
}
