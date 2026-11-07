package period

// پورتِ تبدیل‌هایِ تقویمیِ codal_periods: j2g_date، pub_key و کمکی‌هایِ داخلی.
// هیچ قاعدهٔ تازه‌ای اینجا ساخته نمی‌شود؛ همان الگوریتم‌هایِ پایتون با همان
// سخت‌گیری (سال ۱۳۰۰..۱۵۰۰، طولِ ماهِ شمسی، ساعتِ نامعتبر ⇒ حذفِ ساعت).

import (
	"fmt"
	"regexp"
	"unicode/utf8"
)

var pubRe = regexp.MustCompile(`^([0-9]{4})\s*[-/]\s*([0-9]{1,2})\s*[-/]\s*([0-9]{1,2})(?:\s+([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?)?`)
var clockRe = regexp.MustCompile(`^([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?`)

func j2g(jy, jm, jd int) (int, int, int) {
	jy += 1595
	days := -355668 + 365*jy + (jy/33)*8 + ((jy%33)+3)/4 + jd
	if jm < 7 {
		days += (jm - 1) * 31
	} else {
		days += (jm-7)*30 + 186
	}
	gy := 400 * (days / 146097)
	days %= 146097
	if days > 36524 {
		days--
		gy += 100 * (days / 36524)
		days %= 36524
		if days >= 365 {
			days++
		}
	}
	gy += 4 * (days / 1461)
	days %= 1461
	if days > 365 {
		gy += (days - 1) / 365
		days = (days - 1) % 365
	}
	gd := days + 1
	leap := (gy%4 == 0 && gy%100 != 0) || gy%400 == 0
	salA := []int{31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}
	if leap {
		salA[1] = 29
	}
	gm := 0
	for gm < 12 && gd > salA[gm] {
		gd -= salA[gm]
		gm++
	}
	return gy, gm + 1, gd
}

func g2j(gy, gm, gd int) (int, int, int) {
	gDM := []int{0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334}
	gy2 := gy
	if gm > 2 {
		gy2 = gy + 1
	}
	days := 355666 + 365*gy + (gy2+3)/4 - (gy2+99)/100 + (gy2+399)/400 + gd + gDM[gm-1]
	jy := -1595 + 33*(days/12053)
	days %= 12053
	jy += 4 * (days / 1461)
	days %= 1461
	if days > 365 {
		jy += (days - 1) / 365
		days = (days - 1) % 365
	}
	var jm, jd int
	if days < 186 {
		jm = 1 + days/31
		jd = 1 + days%31
	} else {
		jm = 7 + (days-186)/30
		jd = 1 + (days-186)%30
	}
	return jy, jm, jd
}

// jalaliMonthLen طولِ ماهِ شمسی؛ اسفند فقط با رفت‌وبرگشتِ j2g/g2j سنجیده می‌شود.
func jalaliMonthLen(jy, jm int) int {
	if jm <= 6 {
		return 31
	}
	if jm <= 11 {
		return 30
	}
	gy, gm, gd := j2g(jy, 12, 30)
	j2y, j2m, j2d := g2j(gy, gm, gd)
	if j2y == jy && j2m == 12 && j2d == 30 {
		return 30
	}
	return 29
}

// clockSearch عینِ `re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?", s)`.
// خروجی: رشته‌هایِ ساعت/دقیقه/ثانیه و true.
func clockSearch(s string) (string, string, string, bool) {
	prevDigit := false
	for i := 0; i < len(s); {
		r, size := utf8Decode(s[i:])
		dig := isPyDigit(r)
		if dig && !prevDigit {
			if m := clockRe.FindStringSubmatchIndex(s[i:]); m != nil {
				hh := s[i+m[2] : i+m[3]]
				mi := s[i+m[4] : i+m[5]]
				ss := ""
				if m[6] >= 0 {
					ss = s[i+m[6] : i+m[7]]
				}
				return hh, mi, ss, true
			}
		}
		prevDigit = dig
		i += size
	}
	return "", "", "", false
}

func utf8Decode(s string) (rune, int) {
	return utf8.DecodeRuneInString(s)
}

// J2GDate عینِ `codal_periods.j2g_date`: تاریخِ شمسی (با ساعتِ اختیاری) ⇒
// «YYYY-MM-DD[ HH:MM:SS]»؛ نامعتبر ⇒ nil.
func J2GDate(raw string) *string {
	s := digitFold(pyStr(raw))
	m := looseSearch(s)
	if m == nil {
		return nil
	}
	jy, okY := pyInt(s[m[2]:m[3]])
	jm, okM := pyInt(s[m[4]:m[5]])
	jd, okD := pyInt(s[m[6]:m[7]])
	if !okY || !okM || !okD {
		return nil
	}
	if jm < 1 || jm > 12 || jd < 1 || jd > 31 {
		return nil
	}
	if jy < 1300 || jy > 1500 {
		return nil
	}
	if jd > jalaliMonthLen(jy, jm) {
		return nil
	}
	gy, gm, gd := j2g(jy, jm, jd)
	out := fmt.Sprintf("%04d-%02d-%02d", gy, gm, gd)
	if hh, mi, ss, ok := clockSearch(s); ok {
		h, okH := pyInt(hh)
		mn, okN := pyInt(mi)
		sc := 0
		okS := true
		if ss != "" {
			sc, okS = pyInt(ss)
		}
		if okH && okN && okS && h <= 23 && mn <= 59 && sc <= 59 {
			out += fmt.Sprintf(" %02d:%02d:%02d", h, mn, sc)
		}
	}
	return &out
}

// PubKey عینِ `codal_periods.pub_key`: «YYYY/MM/DD[ HH:MM:SS]» canonical یا nil.
// ساعتِ نامعتبر حذف می‌شود ولی تاریخ می‌ماند — همان رفتارِ اوراکل.
func PubKey(raw string) *string {
	s := digitFold(pyStr(raw))
	m := pubStart(s)
	if m == nil {
		return nil
	}
	mo, okM := pyInt(s[m[4]:m[5]])
	d, okD := pyInt(s[m[6]:m[7]])
	if !okM || !okD || mo < 1 || mo > 12 || d < 1 || d > 31 {
		return nil
	}
	out := fmt.Sprintf("%s/%02d/%02d", s[m[2]:m[3]], mo, d)
	if m[8] >= 0 {
		hh, _ := pyInt(s[m[8]:m[9]])
		mi, _ := pyInt(s[m[10]:m[11]])
		ss := 0
		if m[12] >= 0 {
			ss, _ = pyInt(s[m[12]:m[13]])
		}
		if hh <= 23 && mi <= 59 && ss <= 59 {
			out += fmt.Sprintf(" %02d:%02d:%02d", hh, mi, ss)
		}
	}
	return &out
}

// pubStart عینِ جست‌وجویِ `_PUB_RE` با شرطِ «(?<!\d)» در آغاز.
func pubStart(s string) []int {
	prevDigit := false
	for i := 0; i < len(s); {
		r, size := utf8Decode(s[i:])
		dig := isPyDigit(r)
		if dig && !prevDigit {
			if m := pubRe.FindStringSubmatchIndex(s[i:]); m != nil {
				for k, v := range m {
					if v >= 0 {
						m[k] += i
					}
				}
				return m
			}
		}
		prevDigit = dig
		i += size
	}
	return nil
}
