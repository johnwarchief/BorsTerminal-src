package fundamental

// دروازه‌هایِ حذفِ خودکار (پیش‌غربالگریِ خروجی) — پورتِ `api/fundamental.risk_gates`
// و تکیه‌گاه‌هایش از `fts_engine` (ماده ۱۴۱ / نقدشوندگی / تعلیق / بیمه).
//
// این فایل هیچ رأیِ تازه‌ای نمی‌سازد: هر قاعده عیناً از اوراکلِ پایتون آمده و
// داورِ آن وکتورهایِ کامیت‌شده یا ردیف‌هایِ سنجیده‌شده درِ `axis45_test.go` است.
// تنها منبعِ مقیاس‌ها `codal_units`/`codal_periods`اند؛ هر جا آن لایه‌ها درِ Go
// هنوز ساخته نشده‌اند، نسخهٔ محلیِ `gt`-پیشوند با نشانِ `TODO(unify)` نوشته شده
// تا یکپارچه‌ساز همان را با نسخهٔ canonical عوض کند.

import (
	"context"
	"strconv"
	"strings"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/symbolid"
)

// gtHemmatRial عینِ `api/fundamental.HEMMAT_RIAL`: ۱ همت = ۱۰^۱۲ تومان =
// ۱۰^۱۳ ریال. تنها نقطۀ ورودِ «همت» به این مسیر همین ثابت است.
const gtHemmatRial = 1e13

// gtRialPerHmtBricks عینِ مخرجِ `avg_trade_value_hmt` (همت = ۱۰^۱۰ ریال درِ آن
// تابع، یعنی در واقع «میلیارد تومان») و بعدِ ÷۱۰۰۰ درِ `trade_value_hmt` که
// همان تصحیحِ واحدِ جزوه است.
const gtRialPerBillionToman = 1e10

// gtPubCanonSQL عینِ `codal_periods.pub_canon_sql`: «همین تاریخ، با ارقامِ
// لاتین و جداکنندۀ یکسان» بی‌`ORDER BY`.
//
// TODO(unify): به internal/period منتقل شود — `period.OrderExpr`/`DatedSQL`
// همان‌جا هستند و این تنها حلقۀ باقی‌مانده از آن فایل است؛ بی‌انتقالِ این، دو
// تعریفِ «تازۀترینِ انتشار» درِ مخزن می‌نشیند (همان بلیّتی که `codal_periods`
// برایِ `pub_key` بست).
//
// ترتیبِ `replace`ها داورِ خودش است: اولِ ده رقمِ فارسی (U+06F0..U+06F9)، بعدِ
// ده رقمِ عربی-هندی (U+0660..U+0669)، درِ پایان `trim` و عوضِ «-» به «/». رقم‌ها
// با `rune(0x06F0+d)` ساخته می‌شوند تا ویرایشِ دستی هیچ رقمی را بدزدد (قیدِ
// گاردِ machines).
func gtPubCanonSQL(col string) string {
	expr := "trim(" + col + ")"
	for d := 0; d < 10; d++ {
		expr = "replace(" + expr + ", '" + string(rune(0x06F0+d)) + "', '" + strconv.Itoa(d) + "')"
	}
	for d := 0; d < 10; d++ {
		expr = "replace(" + expr + ", '" + string(rune(0x0660+d)) + "', '" + strconv.Itoa(d) + "')"
	}
	return "replace(" + expr + ", '-', '/')"
}

// gtPubOrderExpr عینِ `codal_periods.pub_order_expr`: «تازۀترینِ انتشار اول»;
// NULL آخر می‌نشیند (SQLite در DESC).
func gtPubOrderExpr(col string) string { return gtPubCanonSQL(col) + " DESC" }

// gtInsuranceTokens عینِ `fts_engine.INSURANCE_TOKENS`.
var gtInsuranceTokens = []string{"بیمه", "بازنشستگی"}

// IsInsuranceSector عینِ `fts_engine.is_insurance_sector`: رویِ `sector_name`
// سنجیده می‌شود، نه رویِ نماد (رفعِ باگِ v7.3). رشتهٔ خالی هیچ‌وقت بیمه نیست.
func IsInsuranceSector(sector string) bool {
	s := normFa(sector)
	if s == "" {
		return false
	}
	for _, t := range gtInsuranceTokens {
		if strings.Contains(s, normFa(t)) {
			return true
		}
	}
	return false
}

// gtMarketSessions عینِ `fts_engine.market_sessions` — جدولِ نشست‌هایِ بازار از
// `daily_prices`، تازۀترین در ابتدا. نشستِ تهی (None) نگه داشته نمی‌شود، چون
// `is_suspended` بعدش `int()` می‌خواهد و پایتون رویِ None می‌شکند؛ داورِ این
// برش درِ آزمونِ بانکِ موقت آمده است.
func (s *Service) gtMarketSessions(ctx context.Context, n int) ([]int64, error) {
	rows, err := s.msQuery(ctx,
		"SELECT DISTINCT d_even FROM daily_prices ORDER BY d_even DESC LIMIT ?", []any{int64(n)})
	if err != nil {
		return nil, err
	}
	out := make([]int64, 0, len(rows))
	for _, r := range rows {
		if len(r) == 0 || r[0] == nil {
			continue
		}
		v, ok := toI(r[0])
		if !ok {
			continue
		}
		out = append(out, v)
	}
	return out, nil
}

// gtSessions عینِ `market_sessions(conn, 8)` — همان سقفِ پیش‌فرضِ اوراکل.
func (s *Service) gtSessions(ctx context.Context) ([]int64, error) {
	return s.gtMarketSessions(ctx, 8)
}

// IsSuspended عینِ `fts_engine.is_suspended`: تعلیق = آخرین روزِ معاملاتیِ خودِ
// نماد از نشستِ آستانه (محلِ `max_stale_sessions` درِ فهرستِ نشست‌ها) عقب‌تر باشد.
// بی‌تابلو (نمادِ فقط-کدال) تعلیق نیست؛ بی‌دو نشست هم داوری نمی‌شود.
func (s *Service) IsSuspended(ctx context.Context, symbol string,
	maxStaleSessions int, sessions []int64) (bool, error) {
	sess := sessions
	var err error
	if sess == nil {
		sess, err = s.gtSessions(ctx)
		if err != nil {
			return false, err
		}
	}
	if len(sess) < 2 {
		return false, nil
	}
	cut := maxStaleSessions
	if cut < 0 {
		cut = 0
	}
	if cut > len(sess)-1 {
		cut = len(sess) - 1
	}
	cutoff := sess[cut]
	pred18, params, err := s.sid.Pred(ctx, "i.l_val18", symbol, symbolid.Board)
	if err != nil {
		pred18, params = "i.l_val18 = ?", []any{symbol}
	}
	pred30 := strings.ReplaceAll(pred18, "i.l_val18", "i.l_val30")
	args := make([]any, 0, len(params)*2)
	args = append(args, params...)
	args = append(args, params...)
	rows, err := s.msQuery(ctx,
		"SELECT m.d_even FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code "+
			"WHERE "+pred18+" OR "+pred30+" ORDER BY m.d_even DESC LIMIT 1", args)
	if err != nil {
		return false, err
	}
	if len(rows) == 0 || len(rows[0]) == 0 || rows[0][0] == nil {
		return false, nil
	}
	last, ok := toI(rows[0][0])
	if !ok {
		return false, nil
	}
	return last < cutoff, nil
}

// M141Map عینِ `fts_engine.m141_map`: نمادهایِ مشمولِ ماده ۱۴۱ (دارایی خالص ≤
// نصفِ سرمایه) → {SI.key(symbol): bool}. تعریفِ «آخرینِ سالانۀ قابلِ استفاده»
// از همان `CP.order_expr` + `CP.pub_order_expr` و طولِ دوره از
// `period.EffectiveMonths` می‌آید، تا پنجرۀ کارت و نقشۀ اسکرینر یکِ سالِ مالی
// را ببینند. نمادی که هیچ ردیفِ رأی‌دهنده ندارد درِ نقشه **نمی‌آید** (نه مردود).
//
// دو نکته که آزمونِ بانکِ موقت ثابتشان می‌کند:
//   * «اولینِ رأی» نه «اولینِ ردیف»: ردیفی که `months < 12` یا عددِ غیرقابل‌تحویل
//     دارد ادامه می‌دهد و نماد هنوز شانسِ رأی دارد (عینِ `continue`هایِ اوراکل).
//   * فیلترِ تک‌نمادی درِ این کوئری ممنوع است — کلیدِ خروجیِ نرمال‌شده است، و
//     `symbol = ?` نوشتارهایِ عربی را بی‌صدا «پیدا نشدن» می‌کند.
func (s *Service) M141Map(ctx context.Context) (map[string]bool, error) {
	rows, err := s.rows(ctx,
		"SELECT symbol, capital, total_equity, period_end, publish_date, period_months, title "+
			"FROM financial_statements "+
			"WHERE (period_months >= 12 OR period_months IS NULL) "+
			"AND capital > 0 AND total_equity IS NOT NULL "+
			"ORDER BY symbol, "+period.OrderExpr("")+", "+gtPubOrderExpr("publish_date"),
		nil)
	if err != nil {
		return nil, err
	}
	out := map[string]bool{}
	for _, r := range rows {
		sym, _ := r["symbol"].(string)
		key := symbolid.Key(sym)
		if _, seen := out[key]; seen { // فقط جدیدترین سالِ مالیِ رأی‌دهنده ملاک است
			continue
		}
		months, _ := period.EffectiveMonths(r["period_end"], r["period_months"], strOr(r["title"]))
		if months == nil || *months < 12 {
			continue
		}
		cap, okCap := gtFloatCell(r["capital"])
		eq, okEq := gtFloatCell(r["total_equity"])
		if !okCap || !okEq {
			continue // TypeError/ValueErrorِ اوراکل ⇒ این ردیف رأی نمی‌دهد
		}
		out[key] = eq <= 0.5*cap
	}
	return out, nil
}

// gtFloatCell عینِ `float(cap)` رویِ مقداری که از SQLite می‌آید؛ بی‌عدد ⇒ ok=false
// تا شاخۀ exceptِ پایتون بازتولید شود (رشتهٔ بی‌عدد درِ ستونِ بی‌نوع معنا دارد).
func gtFloatCell(v any) (float64, bool) {
	switch x := v.(type) {
	case nil:
		return 0, false
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(x), 64)
		if err != nil {
			return 0, false
		}
		return f, true
	}
	return toF(v), true
}

// AvgTradeValueHmt عینِ `fts_engine.avg_trade_value_hmt`: میانگینِ ارزشِ ریالیِ
// معاملات رویِ `sessions` نشستِ اخیرِ خودِ نماد → {SI.key(symbol): عدد/۱۰^۱۰}.
// نامِ اوراکل «همت» است ولی مقیاش «میلیارد تومان» می‌ماند؛ تصحیحِ واحد درِ
// `TradeValueHmt` است، نه اینجا (دو مصرف، یک ضریب).
func (s *Service) AvgTradeValueHmt(ctx context.Context, sessions int) (map[string]float64, error) {
	sess, err := s.gtSessions(ctx)
	if err != nil {
		return nil, err
	}
	// `market_sessions(conn)[:max(int(sessions), 1)]` — برش، نه فیلترِ دوباره.
	lim := sessions
	if lim < 1 {
		lim = 1
	}
	if lim < len(sess) {
		sess = sess[:lim]
	}
	if len(sess) == 0 {
		return map[string]float64{}, nil
	}
	cutoff := sess[0]
	for _, v := range sess[1:] {
		if v < cutoff {
			cutoff = v
		}
	}
	rows, err := s.msQuery(ctx,
		"SELECT i.l_val18, AVG(d.q_tot_cap), COUNT(*) "+
			"FROM daily_prices d JOIN instruments i ON i.ins_code = d.ins_code "+
			"WHERE d.q_tot_cap > 0 AND d.d_even >= ? GROUP BY i.l_val18",
		[]any{cutoff})
	if err != nil {
		return nil, err
	}
	out := map[string]float64{}
	for _, r := range rows {
		sym := strOr(seriesCell(r, 0))
		if sym == "" {
			continue // `if sym` درِ درکِ پایتون: نمادِ خالی واردِ نقشه نمی‌شود
		}
		val := toF(seriesCell(r, 1)) // `(val or 0.0)` — تهی ⇒ ۰٫۰
		out[symbolid.Key(sym)] = val / gtRialPerBillionToman
	}
	return out, nil
}

// M141Hit عینِ `api/fundamental.m141_hit`: نقشه یک‌بار ساخته یا تزریق می‌شود تا
// حلقۀ واچ‌لیست به N+1 نیفتد؛ نبودِ صورتِ مالیِ سالانه «مشمول نیست» است نه «رد».
func (s *Service) M141Hit(ctx context.Context, symbol string, m141Map map[string]bool) (bool, error) {
	if m141Map == nil {
		built, err := s.M141Map(ctx)
		if err != nil {
			return false, err
		}
		m141Map = built
	}
	return m141Map[symbolid.Key(symbol)], nil
}

// TradeValueHmt عینِ `api/fundamental.trade_value_hmt`: میانگینِ ارزشِ معاملات به
// **همتِ واقعی** (None/بی‌داده ⇒ ۰٫۰). نکتهٔ واحدِ اوراکل همین‌جاست:
// `avg_trade_value_hmt` با وجودِ نامش ÷۱۰^۱۰ می‌دهد (میلیارد تومان)، پس تقسیمِ
// دوباره بر ۱۰۰۰ همتِ درست می‌سازد؛ بی‌این تصحیح آستانۀ «۲ همت» عملاً ۲ میلیارد
// تومان می‌شد و نقدشوندگیِ تقریباً کلِ بازار قبول می‌گشت.
func (s *Service) TradeValueHmt(ctx context.Context, symbol string,
	liqMap map[string]float64) (float64, error) {
	if liqMap == nil {
		built, err := s.AvgTradeValueHmt(ctx, 30)
		if err != nil {
			return 0, err
		}
		liqMap = built
	}
	v, ok := liqMap[symbolid.Key(symbol)]
	if !ok {
		return 0.0, nil
	}
	return v / 1000.0, nil
}

// HmtToRials عینِ `api/fundamental.hmt_to_rials` — تنها نقطۀ تبدیلِ این یکا درِ
// مسیرِ API (پیش‌شرطِ ارزشِ بازار و آستانۀ نقدشوندگی هر دو همین‌جا به ریال
// می‌آیند: یکِ ضریب، دو مصرف).
func HmtToRials(hmt any) float64 { return toF(hmt) * gtHemmatRial }

// RiskGates عینِ `api/fundamental.risk_gates`: دلیلِ حذف‌هایِ خودکار (خارج از
// پنج محور) به‌صورتِ فهرستِ رشته‌هایِ فارسی. آرگومانِ `th` درِ اوراکل هرگز
// خوانده نمی‌شود، پس اینجا هم نمی‌آید.
//
// ترتیبِ شش گیت و متنِ هر پیام داوری‌شدنی است: بیمه، تعلیق (با `try/exceptِ`
// اوراکل — خطایِ بانک «بدونِ تعلیق» می‌شود، نه خطایِ ۵۰۰)، ماده ۱۴۱، کفِ ارزشِ
// بازار، نقدشوندگی، و درِ پایانِ Include/Excludeِ صنعت.
func (s *Service) RiskGates(ctx context.Context, symbol, sector string, mcapRials any,
	cfg map[string]any, m141Map map[string]bool, liqMap map[string]float64,
	gate map[string]any) ([]string, error) {
	if cfg == nil {
		cfg = map[string]any{}
	}
	reasons := []string{}
	if IsInsuranceSector(sector) {
		reasons = append(reasons, "صنعت بیمه — حذف خودکار")
	}
	// `int(cfg.get("suspended_max_stale_sessions", 3) or 3)` — نبودِ کلید ۳،
	// و هر ارزشِ کاذبِ دیگری (از جمله ۰ِ کاربر) هم ۳ می‌شود.
	rawStale, had := cfg["suspended_max_stale_sessions"]
	if !had {
		rawStale = 3
	}
	stale := 3
	if truthy(rawStale) {
		if i, ok := toI(rawStale); ok {
			stale = int(i)
		}
	}
	susp, err := s.IsSuspended(ctx, symbol, stale, nil)
	if err == nil && susp {
		reasons = append(reasons, "نماد تعلیق — حذف خودکار")
	}
	// ۱) ماده ۱۴۱ — وقتی روشن است، نمادِ مشمول فوراً از واچ‌لیست بیرون می‌رود.
	if truthy(cfg["filter_m141"]) {
		hit, err := s.M141Hit(ctx, symbol, m141Map)
		if err != nil {
			return nil, err
		}
		if hit {
			reasons = append(reasons, "ماده ۱۴۱ — زیان انباشته بیش از نصف سرمایه")
		}
	}
	// ۲) کفِ ارزشِ بازار — ورودیِ پانل «همت» است؛ ۱ همت = ۱۰^۱۳ ریال.
	floor := HmtToRials(cfg["mcap_min_hmt"])
	if floor > 0 {
		mcap := toF(mcapRials)
		if mcap <= 0 {
			reasons = append(reasons, "ارزش بازار نامشخص (کف ارزش بازار قابل بررسی نیست)")
		} else if mcap < floor {
			reasons = append(reasons, "ارزش بازار ("+n(mcap/gtHemmatRial, 2)+" همت) زیرِ کفِ "+
				n(toF(cfg["mcap_min_hmt"]), 2)+" همت")
		}
	}
	// ۳) نقدشوندگی — حداقلِ میانگینِ ارزشِ معاملاتِ روزانه (همت).
	minLi := toF(cfg["min_trade_val"])
	if minLi > 0 {
		tv, err := s.TradeValueHmt(ctx, symbol, liqMap)
		if err != nil {
			return nil, err
		}
		if tv <= 0 {
			reasons = append(reasons, "ارزش معاملات ناموجود (پیش‌شرط نقدشوندگی احراز نشد)")
		} else if tv < minLi {
			reasons = append(reasons, "نقدشوندگی ("+n(tv, 4)+" همت) زیرِ کفِ "+n(minLi, 4)+" همت")
		}
	}
	// ۴) فیلترِ صنعتِ Include/Exclude.
	g := gate
	if g == nil {
		g = IndustryGate(sector, cfg)
	}
	if truthy(g["active"]) && !truthy(g["pass"]) && truthy(g["reason"]) {
		reasons = append(reasons, strOr(g["reason"]))
	}
	return reasons, nil
}
