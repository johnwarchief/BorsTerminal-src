package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳): این فایل هیچ داوریِ
// دومی نمی‌سازد. «کدام ردیف نمایندۀ این دورۀ این نماد است» یک تعریفِ واحد دارد —
// `title_entity_suffix` ← `statement_rank` ← کامل‌بودن ← newest tracing_no — و
// کارت/قیف/سریِ فصلی/نویسنده هر چهار از همان یک قاعده می‌خوانند؛ اینجا فقط
// *خواننده* است، نه داورِ دوم، و هیچ آستانه یا فیلترِ تازه‌ای اضافه نمی‌کند.
// ردیفی حذف نمی‌شود (سیاستِ CA-3: تاریخچه حفظ است) و `publish_date` خام عمداً
// درِ رتبه‌بندی نیست. هیچ قفلِ spec/eslint/guardی درِ این لایه درگیر نیست؛
// بازگشت = revertِ همین کامیت.
//
// یک واقعیتِ اندازه‌گیری‌شده درِ همین تسک (کنترلِ منفیِ reference_test.go):
// `canonicalize` جداکننده را یکسان می‌کند، پس «۱۴۰۱-۰۶-۳۱» درِ این لایه به
// «۱۴۰۱/۰۶/۳۱» تبدیل می‌شود و با همان دورۀ اسلashed یکِ کلید می‌سازد؛ ولی شرطِ
// `DATED_SQL` درِ SQL آن ردیف را بی‌دوره می‌شمارد و از مسیرِ واقعی بیرون می‌گذارد.
// یعنی فیلترِ خواننده و پاک‌سازیِ این لایه دو قاعدۀ *جدید* نیستند — همان دو
// شرطِ codal_periods (شکلِ canonical درِ SQL، تبدیلِ هر شکلِ تاریخ درِ پایتون).

import (
	"sort"
	"strings"

	"borsterminal/backend/internal/period"
)

// fsNumberKeys عینِ fts_engine.FS_NUMBER_KEYS — تنها چیزی که «کامل‌بودنِ ردیف»
// با آن شمرده می‌شود. هیچ آستانه‌ای درِ این لایه نیست.
var fsNumberKeys = []string{"revenue", "gross_profit", "operating_profit",
	"net_profit", "basic_eps"}

// stableFields عینِ stable_fields درِ quarter_reference_rows؛ ترتیبش بخشی از
// signature است، پس دست‌نخورده می‌ماند.
var stableFields = []string{"title", "report_kind", "revenue", "gross_profit",
	"operating_profit", "net_profit", "basic_eps"}

// پسوندهایِ پرانتزیِ «مقطعِ نامه» و نشانۀ «اسمِ یکِ شخصیتِ حقوقی» — هر سه فهرست
// عینِ fts_engine (سنجشِ بانکِ کاری درِ کامنتِ آن فایل: از ۱۹۱ پسوند، ۱۸۹ تا
// شخصیت‌اند و ۲ تا صفتِ بی‌نام).
var (
	titleScopeMarks    = []string{"حسابرس", "تلفیق", "اصلاحی"}
	titleEntityMarks   = []string{"شرکت", "شرکای", "موسسه", "مؤسسه", "گروه",
		"بانک", "بانك", "صندوق", "بیمه", "بيمه"}
	titleEntityGeneric = []string{"اصلی", "مادر", "خود", "دیگر", "همه", "فرعی"}
)

const (
	titleParenOpen  = "（("
	titleParenClose = "）)"
)

// isConsolidated عینِ fts_engine._is_consolidated: «تلفیقی» دارد و
// «غیرتلفیقی» ندارد. بی‌بندِ دوم، «…حسابرسی‌شدهٔ غیرتلفیقی» تلفیقی خوانده می‌شد.
func isConsolidated(title string) bool {
	t := normFa(title)
	return strings.Contains(t, "تلفیقی") && !strings.Contains(t, "غیرتلفیقی")
}

// entitySpan عینِ fts_engine._entity_span: آیا این پرانتز نامِ یکِ شخصیتِ
// حقوقی است؟ رشتهٔ خالی یعنی نه.
func entitySpan(span string) string {
	t := trimSpace(span)
	r := []rune(t)
	if len(r) <= 2 {
		return ""
	}
	for _, m := range titleScopeMarks {
		if strings.Contains(t, m) {
			return ""
		}
	}
	if !hasAnyPrefix(t, titleEntityMarks) {
		return ""
	}
	rest := ""
	if i := strings.Index(t, " "); i >= 0 {
		rest = trimSpace(t[i+1:])
	}
	if rest == "" || contains(titleEntityGeneric, rest) {
		return ""
	}
	return t
}

// titleEntitySuffix عینِ fts_engine.title_entity_suffix: نامِ شرکتِ دیگری که درِ
// پرانتزِ عنوان آمده (صورتِ مالیِ شرکتِ فرعی زیرِ نمادِ هلدینگ)، یا "".
// پایانی‌ترین پرانتزِ معتبر برنده است، چون حلقه با هر تطبیقِ تازه found را عوض می‌کند.
func titleEntitySuffix(title string) string {
	s := []rune(title)
	found := ""
	i, n := 0, len(s)
	for i < n {
		if strings.ContainsRune(titleParenOpen, s[i]) {
			j := i + 1
			for j < n && !strings.ContainsRune(titleParenClose, s[j]) {
				j++
			}
			span := trimSpace(normFa(string(s[i+1 : j])))
			if hit := entitySpan(span); hit != "" {
				found = hit
			}
			i = j + 1
		} else {
			i++
		}
	}
	return found
}

func hasAnyPrefix(s string, marks []string) bool {
	for _, m := range marks {
		if strings.HasPrefix(s, m) {
			return true
		}
	}
	return false
}

func contains(xs []string, v string) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

// rowCompleteness عینِ fts_engine.row_completeness: شمارِ ستون‌هایِ کلیدیِ
// پُرشده. None و رشتهٔ بی‌محتوا خالی‌اند؛ صفرِ واقعی پُر است.
func rowCompleteness(row map[string]any) int {
	n := 0
	for _, k := range fsNumberKeys {
		v, ok := row[k]
		if !ok || v == nil {
			continue
		}
		if s, isStr := v.(string); isStr && trimSpace(s) == "" {
			continue
		}
		n++
	}
	return n
}

// rankTuple عینِ fts_engine.statement_rank: (دامنۀ شرکت، تلفیقی، -کاملی،
// -tracing_no) و مقایسهascending. ردیفِ «شرکتِ دیگر» و تلفیقی همیشه کنار می‌روند،
// بعد ردیفِ کامل‌تر، بعد newest.
type rankTuple [4]int64

func statementRank(otherEntity, consolidated bool, completeness int, tracingNo int64) rankTuple {
	return rankTuple{b2i(otherEntity), b2i(consolidated), -int64(completeness), -tracingNo}
}

func b2i(b bool) int64 {
	if b {
		return 1
	}
	return 0
}

func (a rankTuple) cmp(b rankTuple) int {
	for i := range a {
		if a[i] != b[i] {
			if a[i] < b[i] {
				return -1
			}
			return 1
		}
	}
	return 0
}

type quarterKey struct {
	periodEnd string
	months    int64
	hasMonths bool
	kind      string
}

type quarterEntry struct {
	rank rankTuple
	sig  string
	row  map[string]any
}

func signature(row map[string]any) string {
	var b strings.Builder
	for _, name := range stableFields {
		v, ok := row[name]
		if !ok || v == nil {
			b.WriteString("\x00")
			continue
		}
		b.WriteString(pyStr(v))
		b.WriteString("\x00")
	}
	return b.String()
}

// QuarterReferenceRows پورتِ fts_engine.quarter_reference_rows: برایِ هر
// (دوره، طول، نوع) یکِ مرجع می‌گزیند و هیچ ردیفی حذف نمی‌کند — بازنده‌ها فقط از
// دیدِ این سریِ فصلی کنار می‌روند. publish_date خام درِ رتبه‌بندی نیست (دو
// نوشتارِ رقمیِ یکِ تاریخ درِ یکِ ستون، مقایسهٔ واژگانی را بی‌اعتماد می‌کند).
func QuarterReferenceRows(rows []map[string]any, limit any) []map[string]any {
	best := map[quarterKey]quarterEntry{}
	order := make([]quarterKey, 0, len(rows))
	for _, raw := range rows {
		row := copyRow(raw)
		pe := period.Canonicalize(row["period_end"])
		if pe == nil {
			continue
		}
		row["period_end"] = *pe
		months, monthsSrc := period.EffectiveMonths(*pe, row["period_months"], strOr(row["title"]))
		if months == nil {
			row["period_months"] = nil
		} else {
			row["period_months"] = *months
		}
		if monthsSrc == "title" || monthsSrc == "" {
			if monthsSrc == "" {
				row["months_source"] = "unknown"
			} else {
				row["months_source"] = monthsSrc
			}
		}
		kind := strOr(row["report_kind"])
		title := strOr(row["title"])
		tn, _ := toI(orZero(row["tracing_no"]))
		key := quarterKey{periodEnd: *pe, kind: kind}
		if months != nil {
			key.months = int64(*months)
			key.hasMonths = true
		}
		rank := statementRank(titleEntitySuffix(title) != "", isConsolidated(title),
			rowCompleteness(row), tn)
		sig := signature(row)
		cur, seen := best[key]
		if !seen {
			best[key] = quarterEntry{rank: rank, sig: sig, row: row}
			order = append(order, key)
			continue
		}
		if c := rank.cmp(cur.rank); c < 0 || (c == 0 && sig > cur.sig) {
			// کلید جابه‌جا نمی‌شود: ترتیبِ درجِ پایتون درِ best.values() حفظ است.
			cur.rank, cur.sig, cur.row = rank, sig, row
			best[key] = cur
		}
	}

	selected := make([]map[string]any, 0, len(order))
	for _, k := range order {
		selected = append(selected, best[k].row)
	}
	sort.SliceStable(selected, func(i, j int) bool {
		// reverse=Trueِ پایتون: کلیدِ بزرگ‌تر اول، و تساوی با ترتیبِ درج می‌ماند
		// (sliceِ stable همان قاعدۀ first-occurrence را حفظ می‌کند).
		return orderKey(selected[i]).cmp(orderKey(selected[j])) > 0
	})
	// برشِ پایتون (`selected[:n]`) بی‌کرش کوتاه‌تر را می‌دهد؛ اینجا هم همان.
	if n := clampLimit(limit); len(selected) > n {
		selected = selected[:n]
	}
	return selected
}

// orderKey مثلِ tupleِ `order_key` درِ پایتون؛ ترتیبِ واژگانیِ رشته‌ها و
// مقایسهٔ عددیِ هر چهار جزء درِ یکِ int64 بسته می‌شود تا با reverse=True بخورد.
func orderKey(row map[string]any) int64Order {
	m, _ := toI(orZero(row["period_months"]))
	tn, _ := toI(orZero(row["tracing_no"]))
	pe, _ := row["period_end"].(string)
	kind, _ := row["report_kind"].(string)
	return int64Order{pe: pe, months: m, kind: kind, tracing: tn}
}

type int64Order struct {
	pe      string
	months  int64
	kind    string
	tracing int64
}

func (a int64Order) cmp(b int64Order) int {
	if a.pe != b.pe {
		if a.pe < b.pe {
			return -1
		}
		return 1
	}
	if a.months != b.months {
		if a.months < b.months {
			return -1
		}
		return 1
	}
	if a.kind != b.kind {
		if a.kind < b.kind {
			return -1
		}
		return 1
	}
	if a.tracing != b.tracing {
		if a.tracing < b.tracing {
			return -1
		}
		return 1
	}
	return 0
}

// clampLimit مثلِ `max(1, min(int(limit), 40))` با همان برگشتِ ۱۶ برایِ ورودیِ
// غیرعدد (پایتون TypeError/ValueError را می‌گیرد).
func clampLimit(limit any) int {
	n, ok := toI(orZero(limit))
	if !ok {
		return 16
	}
	if n < 1 {
		return 1
	}
	if n > 40 {
		return 40
	}
	return int(n)
}

// orZero مثلِ `x or 0` درِ پایتون برایِ شمارش‌ها: هیچ‌ارزشِ کاذب صفر می‌شود.
func orZero(v any) any {
	if isFalsy(v) {
		return 0
	}
	return v
}
