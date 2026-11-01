package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). What changes: این فایل
// لایۀ «سریِ فعالیت ماهانه» را از fts_engine.py (1068-1185) و api/fundamental.py
// (177-196، 463-533) به Go می‌آورد — همان پنج تابعِ داده‌ای که کارتِ بنیادی، قیفِ
// لایۀ ۱ و لایۀ ۱ب از یک منبع می‌خوانند. Invariants: هیچ داوریِ دومی ساخته
// نمی‌شود؛ انتخابِ «برندۀ (سال،ماه)» و مخرجِ YoY همان قواعدِ پایتون‌اند. Lockstep:
// MS_SERIES_COLS ← fts_engine.py:1129؛ سه رشتهٔ denominator_basis ← :1177/:1182/
// :1184 (عیناً درِ بارنامهٔ API می‌نشینند، پس کدپوینت‌ها عوض نمی‌شوند). Guard:
// series_test.go رویِ testdata/vectors/series.json که اوراکلِ پایتون ساخته.
// Rollback: revertِ همین کامیت.
//
// چرا داورِ واحد: pred/params از sym_in (internal/symbolid)، حذفِ «نامِ شرکتِ
// دیگر» از titleEntitySuffix (reference.go)، تبدیل‌های عددی از toF/toI/isFalsy/
// pyStr (text.go). هیچ‌کدام اینجا بازساخته نمی‌شود.

import (
	"context"
	"fmt"

	"borsterminal/backend/internal/symbolid"
)

// msSeriesCols عینِ fts_engine.MS_SERIES_COLS (fts_engine.py:1129). ترتیبِ
// ستون‌ها قراردادِ ردیفِ ۷تایی است: index 3 = ytd_revenue (مبنایِ dedupe)،
// index 4 = ytd_revenue_prev (مخرجِ ستون)، index 6 = title (فیلترِ شخصیت).
const msSeriesCols = "year, month, monthly_revenue, ytd_revenue, ytd_revenue_prev, " +
	"period_end, title"

// seriesTitleLimit ردیف‌ها را با LIMITِ اوراکل می‌خواند. پیش از این کارت LIMIT ۶۰
// و موتور LIMIT ۳۰ داشت؛ سقفِ تازه همان ۶۰ (fts_engine.py:1133-1147).
const seriesTitleLimit = 60

// ── سه رشتهٔ مخرج (denominator_basis) ────────────────────────────────────────
// عیناً از fts_engine.py:1177/1182/1185؛ این‌ها درِ بارنامۀ API می‌روند پس یک
// کدپوینت هم نباید جابه‌جا شود. با کدپوینتِ استخراج‌شده از خودِ سورس راستی‌آزمایی
// شده‌اند: هجنگ `ٔ` = U+0654، گیومه‌های `«»` = U+00AB/U+00BB، خطِ Longer = U+2014.
// جداکنندۀ تاریخ درِ قالبِ سوم همان U+002F است که اینجا «/» نوشته می‌شود (نه
// چیزی که پایانه نشان می‌دهد).
const (
	seriesBasisColumn = "ستون «مقایسهٔ دورهٔ مشابه سال قبل» در همان گزارش"
	seriesBasisAbsent = "ناموجود — ردیف تجمیعی همان دورهٔ سال قبل نیست"
	seriesBasisRow    = "تجمیعی %02d/%d از گزارش فعالیت ماهانه (نه ماه قبل)"
)

// seriesKey کلیدِ (سال، ماه) درِ _dedupe_ym است. پایتون یک‌جا دو نوعِ کلید می‌سازد:
// int-زوجِ (int(r[0] or 0), int(r[1] or 0)) و رشته‌زوجِ (str(r[0]), str(r[1])).
// این دو درِ dictِ پایتون هرگز با هم نمی‌خورند، پس اینجا هم دو نوعِ isInt جدا
// نگه‌شان می‌دارد؛ وگرنه ردیفی که «۱۴۰۴» رشته‌ای دارد با «۱۴۰۴» عددی یکِ کلید
// می‌شد و برندۀ اشتباهی سرِ جدول می‌آمد (fts_engine.py:1078-1083).
type seriesKey struct {
	isInt bool
	i0    int64
	i1    int64
	s0    string
	s1    string
}

// seriesBuildKey عینِ try/exceptِ خط‌هایِ 1080-1083. `int(x or 0)` پیشِ تبدیل
// هیچ‌ارزشِ کاذب را صفر می‌کند، پس orZero + toI؛ اگر هر دو عدد شدند کلیدِ int،
// وگرنه کلِ زوج به str()ِ پایتون می‌رود (pyStr همان رشتهٔ None/«None» می‌دهد،
// دقیقاً مثلِ str(None) درِ پایتون).
func seriesBuildKey(r []any) seriesKey {
	i0, ok0 := toI(orZero(r[0]))
	i1, ok1 := toI(orZero(r[1]))
	if ok0 && ok1 {
		return seriesKey{isInt: true, i0: i0, i1: i1}
	}
	return seriesKey{isInt: false, s0: pyStr(r[0]), s1: pyStr(r[1])}
}

// SeriesDedupeYm پورتِ fts_engine._dedupe_ym (1068-1090): برایِ هر (سال،ماه)
// ردیفی که ytd_revenue بزرگ‌تری دارد نگه داشته می‌شود و درِ تساوی *اولین* ردیفِ
// مرتب‌شده می‌ماند (شرطِ `_f(r[i]) > _f(best[i])` اکید است، پس «=» جابه‌جا نمی‌کند)
// و ترتیبِ خروجی ترتیبِ نخستینِ رؤیتِ کلیدهاست، نه ترتیبِ اندازه.
func SeriesDedupeYm(rows [][]any, ytdIdx int) [][]any {
	best := map[seriesKey][]any{}
	order := []seriesKey{}
	for _, r := range rows {
		k := seriesBuildKey(r)
		if _, seen := best[k]; !seen {
			order = append(order, k)
			best[k] = r
			continue
		}
		if toF(seriesCell(r, ytdIdx)) > toF(seriesCell(best[k], ytdIdx)) {
			best[k] = r
		}
	}
	out := make([][]any, 0, len(order))
	for _, k := range order {
		out = append(out, best[k])
	}
	return out
}

// SeriesYtdDenominator پورتِ fts_engine.ytd_denominator (1157-1185): مخرجِ «همان
// دورۀ سالِ قبل» — اول ستونِ رسمیِ ytd_revenue_prev، وگرنه ردیفِ (سال−۱، همان
// ماه) از خودِ سری، وگرنه None. نبودِ هر دو ⇒ ytd_prev=nil که فراخواننده data_gap
// می‌شمارد نه صفر. خروجی map[string]any با کلیدهای year/month (int64)،
// ytd_now/ytd_prev (float64 یا nil) و denominator_basis (متنِ verbatim) است تا
// دقیقاً همان JSONِ پایتون ساخته شود؛ رشتهٔ سوم با Sprintfِ %02d/%d ساخته می‌شود
// چون `% (month, year - 1)` درِ پایتون همین رقم‌هایِ ASCII را می‌گذارد.
func SeriesYtdDenominator(rows [][]any) map[string]any {
	if len(rows) == 0 {
		return nil
	}
	cur := rows[0]
	year := seriesInt(cur, 0)
	month := seriesInt(cur, 1)
	ytdNow := toF(seriesCell(cur, 3))
	if ytdNow <= 0 || month <= 0 {
		return nil
	}
	prevCol := 0.0
	if len(cur) > 4 {
		prevCol = toF(cur[4])
	}
	if prevCol > 0 {
		return map[string]any{"year": year, "month": month, "ytd_now": ytdNow,
			"ytd_prev": prevCol, "denominator_basis": seriesBasisColumn}
	}
	for _, r := range rows[1:] {
		if seriesInt(r, 0) == year-1 && seriesInt(r, 1) == month {
			prevVal := toF(seriesCell(r, 3))
			if prevVal <= 0 {
				return map[string]any{"year": year, "month": month, "ytd_now": ytdNow,
					"ytd_prev": nil, "denominator_basis": seriesBasisAbsent}
			}
			return map[string]any{"year": year, "month": month, "ytd_now": ytdNow,
				"ytd_prev":          prevVal,
				"denominator_basis": fmt.Sprintf(seriesBasisRow, month, year-1)}
		}
	}
	return map[string]any{"year": year, "month": month, "ytd_now": ytdNow,
		"ytd_prev": nil, "denominator_basis": seriesBasisAbsent}
}

// SeriesMsRows پورتِ api/fundamental._ms_series (177-196): همان شش ستون با همان
// تبدیل‌ها، بی‌داوریِ تازه. year/month از int(float(v)) — یعنی رشتهٔ عددی هم
// پذیرفته می‌شود و سرِ اعشار چیده می‌شود — و سه مقدارِ پولی از seriesNumOrNull
// که «داده نیست» را هیچ‌وقت ۰.۰ نمی‌کند (برخلافِ toF). شرطِ len(r) > n عیناً
// نگهبانِ ردیف‌هایِ کوتاه است (api/fundamental.py:191-194).
func SeriesMsRows(series [][]any) []map[string]any {
	out := make([]map[string]any, 0, len(series))
	for _, r := range series {
		out = append(out, map[string]any{
			"year":             seriesInt(r, 0),
			"month":            seriesInt(r, 1),
			"monthly_revenue":  seriesCellOrNull(r, 2),
			"ytd_revenue":      seriesCellOrNull(r, 3),
			"ytd_revenue_prev": seriesCellOrNull(r, 4),
			"period_end":       seriesCell(r, 5),
		})
	}
	return out
}

// SeriesFiscalYearRows پورتِ api/fundamental._fiscal_year_rows (463-467): ردیف‌های
// یکِ سالِ مالی، ماهِ بیشترِ اول (SliceStable چون پایتون sortِ پایدارِ برگشتی
// تساوی را به ترتیبِ پیشین می‌گذارد).
func SeriesFiscalYearRows(series [][]any, year any) [][]any {
	want := seriesToIntAny(year)
	rows := [][]any{}
	for _, r := range series {
		if seriesInt(r, 0) == want {
			rows = append(rows, r)
		}
	}
	// key=lambda r: -int(_f(r[1])) — مرتب‌سازیِ نزولیِ ماِه.
	for i := 1; i < len(rows); i++ {
		for j := i; j > 0 && seriesInt(rows[j], 1) > seriesInt(rows[j-1], 1); j-- {
			rows[j], rows[j-1] = rows[j-1], rows[j]
		}
	}
	return rows
}

// SeriesGrowthBreadth پورتِ api/fundamental._growth_breadth (517-532): از ماِه ۱ تا
// م، چند ماِه از نظرِ فروشِ تک‌ماهِ بهتر از سالِ قبل است؟ ماهی که درِ یکِ سالِ
// دیگری تکرار شده باشدِ آخرِ نوشتارش می‌ماند (نگاشتِ پایتون همین است).
func SeriesGrowthBreadth(series [][]any, year, month any) (int, int) {
	cur := map[int64]float64{}
	prev := map[int64]float64{}
	want := seriesToIntAny(year)
	for _, r := range series {
		if seriesInt(r, 0) == want {
			cur[seriesInt(r, 1)] = toF(seriesCell(r, 2))
		}
	}
	for _, r := range series {
		if seriesInt(r, 0) == want-1 {
			prev[seriesInt(r, 1)] = toF(seriesCell(r, 2))
		}
	}
	improved, compared := 0, 0
	mTop := seriesToIntAny(month)
	if mTop < 0 {
		mTop = 0
	}
	for m := int64(1); m <= mTop; m++ {
		c, hasC := cur[m]
		p, hasP := prev[m]
		if hasC && c > 0 && hasP && p > 0 {
			compared++
			if c > p {
				improved++
			}
		}
	}
	return improved, compared
}

// MonthlySeries پورتِ fts_engine.monthly_series (1133-1155) — تک‌منبعِ لایۀ ۱،
// ۱ب و سالانه‌سازیِ لایۀ ۴. pred/params از resolverِ نماد (سمبلِ چندِ نوشتاری درِ
// symbol_identity)، بعد همان کوئریِ LIMITدار، بعد حذفِ ردیفِ «عنوانِ شرکتِ دیگر»
// با titleEntitySuffix، برشِ ستونِ title (همان r[:-1])، و درِ پایان dedupe.
//
// پیش‌نویسِ خطا: خطایِ resolver درِ QuartersBody به شرطِ خامِ `symbol = ?` برمی‌گردد
// (routes.go:51-56 — همان برگشتِ لایۀ چارت درِ internal/chart/chartdb.go:82-87)؛
// این‌جا هم به همان سبب، تا «بی‌داده» جعلی به ۵۰۰ نیفتد و خطایِ *واقعیِ* بانک درِ
// خودِ کوئری بالا برود. `max(int(limit or 60), 1)` درِ اوراکل limit=0 را به ۱
// می‌رساند و limit=nil/«» را به ۶۰؛ این شاخه‌ها درِ مسیرِ HTTP اجرا نمی‌شوند چون
// httpapi.IntQuery رشته را یا int می‌کند یا ۴۲۲ می‌دهد.
func (s *Service) MonthlySeries(ctx context.Context, symbol string, limit int) ([][]any, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		pred, args = "symbol = ?", []any{symbol}
	}
	n := limit
	if n == 0 {
		n = seriesTitleLimit
	}
	if n < 1 {
		n = 1
	}
	rows, err := s.msQuery(ctx, "SELECT "+msSeriesCols+" FROM monthly_sales WHERE "+
		pred+" AND ytd_revenue IS NOT NULL AND ytd_revenue>0 "+
		"ORDER BY year DESC, month DESC LIMIT ?", append(args, int64(n)))
	if err != nil {
		return nil, err
	}
	kept := make([][]any, 0, len(rows))
	for _, r := range rows {
		title := ""
		if len(r) > 0 {
			title = strOr(r[len(r)-1])
		}
		if titleEntitySuffix(title) != "" {
			continue
		}
		kept = append(kept, r[:len(r)-1])
	}
	return SeriesDedupeYm(kept, 3), nil
}

// msQuery ردیف‌هایِ یکِ کوئری را به برش‌هایِ ترتیب‌دار (tupleهایِ sqlite3.Rowِ
// پایتون) تبدیل می‌کند و ستون‌ها را با normalizeValue (همان service.go:72) به
// شکلِ مقدارهایِ پایتون می‌آورد، تا []byteهایِ ستونِ TEXT رشته شوند.
func (s *Service) msQuery(ctx context.Context, query string, args []any) ([][]any, error) {
	rs, err := s.market.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rs.Close()
	cols, err := rs.Columns()
	if err != nil {
		return nil, err
	}
	out := [][]any{}
	for rs.Next() {
		raw := make([]any, len(cols))
		ptrs := make([]any, len(raw))
		for i := range raw {
			ptrs[i] = &raw[i]
		}
		if err := rs.Scan(ptrs...); err != nil {
			return nil, err
		}
		row := make([]any, len(cols))
		for i := range cols {
			row[i] = normalizeValue(raw[i])
		}
		out = append(out, row)
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	return out, nil
}

// seriesCell مثلِ r[i] درِ پایتون برایِ ردیف‌هایِ کوتاه: بیرونِ بردار ⇒ None
// (نه کرش)، چون _dedupe_ym/ytd_denominator رویِ برش‌هایِ ۵تایی هم صدا زده
// می‌شوند (ms[key] درِ bulk).
func seriesCell(r []any, i int) any {
	if i < 0 || i >= len(r) {
		return nil
	}
	return r[i]
}

// seriesInt مثلِ int(x or 0) درِ خطِ 1171/1178/465/524 — هیچ‌ارزشِ کاذب صفر
// می‌شود، اعشار سرِ اعشار چیده می‌شود و رشتهٔ عددی پذیرفته می‌شود.
func seriesInt(r []any, i int) int64 {
	n, _ := toI(orZero(seriesCell(r, i)))
	return n
}

// seriesToIntAny مثلِ int(year) درِ api/fundamental.py:465 — تبدیلِ یکِ مقدارِ
// خام به int64؛ بی‌عدد ⇒ 0 (همان صفرِ فالتِ toI).
func seriesToIntAny(v any) int64 {
	n, _ := toI(orZero(v))
	return n
}

// seriesNumOrNull عینِ api/fundamental._num_or_none (214-220): floatِ امن، ولی
// «داده نیست» هیچ‌وقت ۰.۰ نمی‌شود — بی‌عدد و NaN ⇒ nil. توجه: برخلافِ toF که
// رشتهٔ بی‌عدد را ۰ می‌کند، اینجا None برمی‌گردد.
func seriesNumOrNull(v any) any {
	// `float(v)`ِ پایتون صفرِ واقعی را دست‌نخورده می‌گذارد — بی‌این شرط،
	// `monthly_revenue: 0.0` درِ پاسخ «بی‌داده» می‌شد (اوراکل درِ text.json همان
	// را نگه می‌دارد). فقط بی‌عدد و NaN به nil می‌روند.
	f, ok := asFloat(v)
	if !ok {
		return nil
	}
	return f
}

// seriesCellOrNull شرطِ len(r) > n را می‌گیرد و بعد seriesNumOrNull — یعنی عینِ
// `_num_or_none(r[i]) if len(r) > i else None` درِ api/fundamental.py:191-194.
func seriesCellOrNull(r []any, i int) any {
	if i >= len(r) {
		return nil
	}
	return seriesNumOrNull(r[i])
}
