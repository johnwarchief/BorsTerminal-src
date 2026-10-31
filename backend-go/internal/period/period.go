package period

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// pySpace همان مجموعه‌ای است که `\s`ِ پایتون رویِ str می‌پذیرد
// (Py_UNICODE_ISSPACE): ASCII، جداکننده‌هایِ C0 و فاصله‌هایِ یونیکد.
// `\s`ِ Go فقط [\t\n\f\r ] است (بی \v و بی یونیکد)، پس صریح می‌نویسیم.
const pySpace = `[\t\n\v\f\r \x{1c}-\x{1f}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}]`

var (
	canonRe      = regexp.MustCompile(`^([0-9]{4})/([0-9]{2})/([0-9]{2})$`)
	looseRe      = regexp.MustCompile(`([0-9]{4})` + pySpace + `*[-/]` + pySpace + `*([0-9]{1,2})` + pySpace + `*[-/]` + pySpace + `*([0-9]{1,2})`)
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

func isASCIIDigit(c byte) bool { return c >= '0' && c <= '9' }

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

// Canonicalize پورتِ codal_periods.canonicalize است.
// تفاوتِ زبانی: RE2 نگاه‌به‌عقب ندارد، پس «(?<!\d)» و «(?!\d)» با بررسیِ بایتِ
// قبل/بعد انجام می‌شود؛ و مثلِ پایتون، **اولین** تطبیقِ عبورکرده از این دو شرط
// تصمیمِ نهایی است — اگر آن تطبیق ماه/روزِ نامعتبر داشت، None می‌دهیم و به
// تطبیقِ بعدی نمی‌رویم.
func Canonicalize(raw any) *string {
	if raw == nil {
		return nil
	}
	s := digitFold(pyStr(raw))
	for _, m := range looseRe.FindAllStringSubmatchIndex(s, -1) {
		start, end := m[0], m[1]
		if start > 0 && isASCIIDigit(s[start-1]) {
			continue
		}
		if end < len(s) && isASCIIDigit(s[end]) {
			continue
		}
		mo, err1 := strconv.Atoi(s[m[4]:m[5]])
		d, err2 := strconv.Atoi(s[m[6]:m[7]])
		if err1 != nil || err2 != nil || mo < 1 || mo > 12 || d < 1 || d > 31 {
			return nil
		}
		out := fmt.Sprintf("%s/%02d/%02d", s[m[2]:m[3]], mo, d)
		return &out
	}
	return nil
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
	parts := strings.Split(*pe, "/")
	y, _ := strconv.Atoi(parts[0])
	m, _ := strconv.Atoi(parts[1])
	return y, m, true
}

func FiscalYear(period any) *string {
	pe := Canonicalize(period)
	if pe == nil {
		return nil
	}
	y := (*pe)[:4]
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
