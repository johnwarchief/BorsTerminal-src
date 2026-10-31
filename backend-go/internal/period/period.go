package period

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// pySpace همان مجموعه‌ای است که `\s`ِ پایتون رویِ str می‌پذیرد
// (Py_UNICODE_ISSPACE): ASCII، جداکننده‌هایِ C0 و فاصله‌هایِ یونیکد.
// `\s`ِ Go فقط [\t\n\f\r ] است (بی \v و بی یونیکد)، پس صریح می‌نویسیم.
const pySpace = `[\t\n\v\f\r \x{1c}-\x{1f}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}]`

// pyDigitsExtra رقم‌هایی که درِ جدولِ یونیکدِ Go (نسخۀ ۱۵) رقمِ Nd نیستند ولی
// درِ یونیکدِ پایتونِ این ریپو (نسخۀ ۱۶) Nd‌اند: هفت بلوک، هر کدام از رقمِ صفر
// آغاز می‌شود و پیوسته است. بی این‌ها `\d`ِ دو زبان رویِ آن ۸۰ رقم جدا می‌افتاد.
var pyDigitsExtra = []struct{ lo, hi rune }{
	{0x10d40, 0x10d49}, {0x116d0, 0x116e3}, {0x11bf0, 0x11bf9}, {0x16130, 0x16139},
	{0x16d70, 0x16d79}, {0x1ccf0, 0x1ccf9}, {0x1e5f1, 0x1e5fa},
}

// pyDigits مثلِ `\d`ِ پایتون رویِ str: هر رقمِ اعشاریِ یونیکد (ردۀ Nd)، نه فقط
// [0-9]. از همان pyDigitsExtra ساخته می‌شود تا طبقۀ regex و isPyDigit یکِ منبع
// داشته باشند. الگو: pySpace برایِ `\s`.
var pyDigits = func() string {
	var b strings.Builder
	b.WriteString(`[\p{Nd}`)
	for _, rg := range pyDigitsExtra {
		fmt.Fprintf(&b, `\x{%05X}-\x{%05X}`, rg.lo, rg.hi)
	}
	b.WriteString(`]`)
	return b.String()
}()

var (
	canonRe = regexp.MustCompile(`^([0-9]{4})/([0-9]{2})/([0-9]{2})$`)
	// تنۀ _LOOSE بی‌این دو نگاه‌به‌عقب/جلو (که درِ looseSearch دستی سنجیده
	// می‌شوند): رقم‌ها `\d`ِ یونیکدند، نه [0-9].
	looseBody = `(` + pyDigits + `{4})` + pySpace + `*[-/]` + pySpace +
		`*(` + pyDigits + `{1,2})` + pySpace + `*[-/]` + pySpace + `*(` + pyDigits + `{1,2})`
	// تطبیقِ لنگردارِ همان تنه: مثلِ پایتون از هر جایِ ممکنِ آغاز می‌آزماییم، پس
	// باید تطبیق از دقیقاً همان اندیسِ پیشنهادی شروع شود.
	looseAt      = regexp.MustCompile(`\A` + looseBody)
	endAnchor    = regexp.MustCompile(`منتهی` + pySpace + `*به`)
	monthsAnchor = regexp.MustCompile(`([0-9]+)` + pySpace + `*ماهه`)
)

// pyStr مثلِ str(x) در پایتون برایِ انواعی که در JSONِ ورودی می‌آید.
func pyStr(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case bool:
		if x {
			return "True"
		}
		return "False"
	default:
		return fmt.Sprint(x)
	}
}

// digitFold: رقمِ فارسی (U+06F0..) و عربی (U+0660..) → ASCII، مثلِ _DIGITSِ پایتون.
func digitFold(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		switch {
		case r >= '۰' && r <= '۹':
			b.WriteRune('0' + (r - '۰'))
		case r >= '٠' && r <= '٩':
			b.WriteRune('0' + (r - '٠'))
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

// isPyDigit مثلِ `\d`ِ پایتون رویِ str: هر رقمِ اعشاریِ یونیکد (ردۀ Nd). برایِ
// خودِ رقم‌ها و برایِ دو «(?<!\d)» و «(?!\d)»ِ _LOOSE به همین نیاز است، نه
// [0-9]ِ ASCII؛ وگرنه یکِ تاریخِ درست که بلافاصله بعدش رقمِ تمام‌عرض آمده درِ Go
// تاریخ می‌شد، ولی پایتون آن را بی‌دوره می‌شمارد (شاهدش درِ testdata/cases.json).
func isPyDigit(r rune) bool {
	if r < 0 {
		return false
	}
	if unicode.IsDigit(r) {
		return true
	}
	for _, rg := range pyDigitsExtra {
		if r >= rg.lo && r <= rg.hi {
			return true
		}
	}
	return false
}

// pyDigitValue ارزشِ اعشاریِ رقم، مثلِ int()ِ پایتون رویِ یکِ رقم. بلوک‌هایِ رقم
// درِ یونیکد ده‌تاییِ پیوسته و از رقمِ صفرند، پس با عقب‌رفتن تا آغازِ بلوک و
// moduloِ ۱۰ می‌آید. (رویِ هر ۷۶۰ رقمِ Ndِ پایتونِ این ریپو با int() برابری‌اش
// سنجیده شده است.)
func pyDigitValue(r rune) int {
	if !isPyDigit(r) {
		return -1
	}
	base := r
	for isPyDigit(base - 1) {
		base--
	}
	return int((r - base) % 10)
}

// pyInt مثلِ int()ِ پایتون رویِ رشتهٔ فقط‌رقم: هر رقمِ Nd با ارزشِ اعشاریِ خودش
// وارد می‌شود (پایتون هم همین کار را می‌کند)، پس دو رقمِ وِیانگاریِ صفر‌وشش هم
// شش می‌دهد؛ رشتهٔ خالی یا بی‌رقم خطاست.
func pyInt(s string) (int, bool) {
	if s == "" {
		return 0, false
	}
	n := 0
	for _, r := range s {
		v := pyDigitValue(r)
		if v < 0 {
			return 0, false
		}
		n = n*10 + v
	}
	return n, true
}

// pyIsSpace همان مجموعه‌ای است که `pySpace` برایِ `\s`ِ پایتون می‌نویسد
// (Py_UNICODE_ISSPACE). unicode.IsSpaceِ Go بی‌U+001C..U+001F است، پس پیش‌فرضِ
// strings.TrimSpace با .strip()ِ پایتون یکی نیست و ردیفِ شاهدش درِ
// testdata/cases.json (sql.rows id 17) قرمز می‌شود.
func pyIsSpace(r rune) bool {
	switch {
	case r >= '\t' && r <= '\r',
		r >= 0x1c && r <= 0x1f,
		r == ' ', r == 0x85, r == 0xa0, r == 0x1680,
		r >= 0x2000 && r <= 0x200a,
		r == 0x2028, r == 0x2029, r == 0x202f, r == 0x205f, r == 0x3000:
		return true
	}
	return false
}

// pyTrim مثلِ str.strip() بی‌آرگومان درِ پایتون.
func pyTrim(s string) string { return strings.TrimFunc(s, pyIsSpace) }

// Trim همان .strip() برایِ مصرفِ بقیهٔ پکیج‌ها. هر جا «خالی بودنِ رشته» سنجیده
// می‌شود باید همین باشد، نه strings.TrimSpace (تفاوتِ U+001C..U+001F درِ
// testdata/cases.json ردیفِ ۱۷ ثبت شده است).
func Trim(s string) string { return pyTrim(s) }

// looseSearch مثلِ _LOOSE.searchِ پایتون کار می‌کند، نه مثلِ FindAllِ Go:
// پایتون یک‌یکِ نویسه جلو می‌رود و درِ هر جایِ ممکن تلاش می‌کند، پس تطبیق‌ها
// می‌توانند هم‌پوشانی داشته باشند و «اولین» یعنی اولین *نویسه‌ای* که از آنجا
// تطبیق کامل شد. با FindAllِ غیرهم‌پوشان، تاریخِ درستِ شروع‌شده وسطِ دامانۀ
// یکِ تطبیقِ ردشده هرگز دیده نمی‌شد: درِ ردیفِ canonicalizeِ testdata/cases.json
// همان ورودی در Go بی‌جواب می‌ماند و پایتون دورۀ سالِ ۳۰۱۲ را برمی‌گرداند.
// جایِ آغازِ کاندید = رقمی که نویسهٔ پیشِ آن رقمِ Nd نیست (شرطِ (?<!\d))؛
// بقیهٔ جای‌ها نمی‌توانند آغاز باشند.
// خروجی: اندیس‌هایِ مطلقِ FindStringSubmatchIndex، یا nil.
func looseSearch(s string) []int {
	prevDigit := false
	for i := 0; i < len(s); {
		r, size := utf8.DecodeRuneInString(s[i:])
		dig := isPyDigit(r)
		if dig && !prevDigit {
			// \A لنگر می‌دهد که تطبیق از همین i شروع شود؛ شرطِ (?!\d) را بعداً رویِ
			// نویسهٔ پس از تطبیق می‌سنجیم. گروهِ آخرِ الگو \d{1,2} است، پس بازگشتِ
			// پایتون به نسخۀ یک‌رقمی فایدۀ دوم نمی‌دهد (اگر رقمِ دوم هست، همان
			// رقمِ دوم شرط را می‌شکند؛ اگر نیست، نسخهٔ یک‌رقمی همان تطبیقِ ماست).
			if m := looseAt.FindStringSubmatchIndex(s[i:]); m != nil {
				end := i + m[1]
				if end >= len(s) || !isPyDigit(firstRune(s[end:])) {
					for k, v := range m {
						if v >= 0 {
							m[k] += i
						}
					}
					return m
				}
			}
		}
		prevDigit = dig
		i += size
	}
	return nil
}

func firstRune(s string) rune {
	r, _ := utf8.DecodeRuneInString(s)
	return r
}

// Canonicalize پورتِ codal_periods.canonicalize است.
// تفاوتِ زبانی: RE2 نگاه‌به‌عقب ندارد، پس «(?<!\d)» و «(?!\d)» با بررسیِ نویسهٔ
// قبل/بعد انجام می‌شود (looseSearch)؛ و مثلِ پایتون، **اولین** تطبیقِ عبورکرده از
// این دو شرط تصمیمِ نهایی است — اگر آن تطبیق ماه/روزِ نامعتبر داشت، None می‌دهیم
// و به تطبیقِ بعدی نمی‌رویم. سال درِ خروجی **عینِ نویسه‌هایِ تطبیق‌شده** می‌ماند
// (رقمِ یونیکد هم می‌تواند باشد) و فقط ماه/روز ASCII می‌شوند، چون پایتون
// f"{y}/{mo:02d}/{d:02d}" را با گروهِ خامِ سال می‌سازد.
func Canonicalize(raw any) *string {
	if raw == nil {
		return nil
	}
	s := digitFold(pyStr(raw))
	m := looseSearch(s)
	if m == nil {
		return nil
	}
	mo, ok1 := pyInt(s[m[4]:m[5]])
	d, ok2 := pyInt(s[m[6]:m[7]])
	if !ok1 || !ok2 || mo < 1 || mo > 12 || d < 1 || d > 31 {
		return nil
	}
	out := fmt.Sprintf("%s/%02d/%02d", s[m[2]:m[3]], mo, d)
	return &out
}

func FromTitle(title string) *string {
	s := title
	if m := endAnchor.FindStringIndex(s); m != nil {
		s = s[m[1]:]
	}
	return Canonicalize(s)
}

func MonthsFromTitle(title string) *int {
	m := monthsAnchor.FindStringSubmatch(digitFold(title))
	if m == nil {
		return nil
	}
	n, err := strconv.Atoi(m[1])
	if err != nil || n < 1 || n > 12 {
		return nil
	}
	return &n
}

func Derive(datasourceEnd, title any) (*string, string) {
	if pe := Canonicalize(datasourceEnd); pe != nil {
		return pe, "datasource"
	}
	if pe := Canonicalize(title); pe != nil {
		return pe, "title"
	}
	return nil, ""
}

func EffectiveMonths(periodEnd, periodMonths any, title string) (*int, string) {
	var col *int
	raw := ""
	if periodMonths != nil {
		raw = pyTrim(pyStr(periodMonths))
	}
	if raw != "" {
		if f, err := strconv.ParseFloat(raw, 64); err == nil {
			c := int(f)
			if c >= 1 && c <= 12 {
				col = &c
			}
		}
	}
	tm := MonthsFromTitle(title)
	if tm == nil {
		if col != nil {
			return col, "column"
		}
		return nil, ""
	}
	tp := FromTitle(title)
	pe := Canonicalize(periodEnd)
	if tp != nil && pe != nil && *tp != *pe {
		if col != nil {
			return col, "column"
		}
		return nil, ""
	}
	if col != nil && *col == *tm {
		return col, "column"
	}
	return tm, "title"
}

func IsCanonical(value any) bool {
	if value == nil {
		return false
	}
	return canonRe.MatchString(pyTrim(pyStr(value)))
}

func IsUndated(value any) bool { return !IsCanonical(value) }

func YM(period any) (int, int, bool) {
	pe := Canonicalize(period)
	if pe == nil {
		return 0, 0, false
	}
	// int()ِ پایتون رویِ هر رقمِ Nd کار می‌کند و سالِ canonical می‌تواند رقمِ
	// یونیکد باشد (canonicalize گروهِ خامِ سال را برمی‌گرداند)، پس Atoiِ ASCII
	// کافی نیست.
	parts := strings.Split(*pe, "/")
	y, ok1 := pyInt(parts[0])
	m, ok2 := pyInt(parts[1])
	if !ok1 || !ok2 {
		return 0, 0, false
	}
	return y, m, true
}

// FiscalYear سالِ مالیِ دوره یا nil. برشِ پایتون pe[:4] چهار *نویسه* است، نه چهار
// بایت، و سالِ canonical می‌تواند رقمِ چندبایتی باشد.
func FiscalYear(period any) *string {
	pe := Canonicalize(period)
	if pe == nil {
		return nil
	}
	r := []rune(*pe)
	y := string(r[:min(len(r), 4)])
	return &y
}

func DescSortKey(period any) string {
	if pe := Canonicalize(period); pe != nil {
		return *pe
	}
	return ""
}

func Latest(periods []any) *string {
	best := ""
	for _, p := range periods {
		if pe := Canonicalize(p); pe != nil && *pe > best {
			best = *pe
		}
	}
	if best == "" {
		return nil
	}
	return &best
}
