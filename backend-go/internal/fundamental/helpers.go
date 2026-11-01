package fundamental

// کمک‌تابع‌هایِ نمایشِ عدد — عینِ `_n`، `_pct_txt`، `_fa`، `_state` درِ
// api/fundamental.py. این‌ها رأیِ تازه نمی‌سازند؛ فقط شکلِ عدد رویِ سیم.
// (قراردادِ مشترکِ fan-out: هر شاخهٔ بنیادی باید از همین‌ها بخورد، نه از
// تعریفِ دومِ هم‌نام درِ فایلِ خودش — همان بلیّتی که `codal_periods.py` بست.)

import (
	"strconv"
	"strings"

	"borsterminal/backend/internal/pyround"
)

// faDigitsTable رقمِ لاتین → فارسی، مثلِ _FA_DIGITS.
func faDigits(s string) string {
	var b strings.Builder
	b.Grow(len(s) + len(s)/2)
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(rune(0x06F0 + (r - '0')))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// fa مثلِ `_fa(v)`: str(v).translate(_FA_DIGITS).
func fa(v any) string { return faDigits(pyStr(v)) }

// n مثلِ `_n(v, nd)`: جداکنندهٔ هزارگان؛ nil/غیرعدد ⇒ «—» (نه صفرِ گمراه‌کننده).
// پایتون با "{:,.Nd}".format(float(v)) می‌سازد — همان گردکردنِ نیم‌به‌زوج، پس
// اول pyround و بعدِ گروه‌بندی.
func n(v any, nd int) string {
	f := toF(v)
	if v == nil {
		return "—"
	}
	switch x := v.(type) {
	case string:
		if strings.TrimSpace(x) == "" {
			return "—"
		}
		if _, err := strconv.ParseFloat(x, 64); err != nil {
			return "—"
		}
	case bool:
		_ = x
	}
	s := strconv.FormatFloat(pyround.Round(f, nd), 'f', nd, 64)
	neg := strings.HasPrefix(s, "-")
	if neg {
		s = s[1:]
	}
	intPart, decPart := s, ""
	if i := strings.IndexByte(s, '.'); i >= 0 {
		intPart, decPart = s[:i], s[i:]
	}
	var grouped strings.Builder
	for i, c := range intPart {
		if i > 0 && (len(intPart)-i)%3 == 0 {
			grouped.WriteByte(',')
		}
		grouped.WriteRune(c)
	}
	out := grouped.String() + decPart
	if neg {
		out = "-" + out
	}
	return out
}

// n0 مثلِ `_n(v)` با صفرِ اعشار (پرکاربردترین شکلِ کارت).
func n0(v any) string { return n(v, 0) }

// pctText مثلِ `_pct_txt(v, signed)`: None ⇒ «—»، وگرنه عددِ یک‌دهم با ٪.
//
// علامتِ «+» فقط برایِ مقدارِ نامنفی می‌آید — همان قاعدۀ `"%+.1f"` درِ پایتون:
// عددِ منفی خودش «−» دارد و «+» یعنی «+۱۰٪» نه «+-۱۰٪».
func pctText(v any, signed bool) string {
	if v == nil {
		return "—"
	}
	f, ok := asFloat(v)
	if !ok {
		return "—"
	}
	s := strconv.FormatFloat(pyround.Round(f, 1), 'f', 1, 64)
	if signed && !strings.HasPrefix(s, "-") {
		s = "+" + s
	}
	return s + "٪"
}

// pctUnsigned مثلِ `_pct_txt(v, signed=False)`.
func pctUnsigned(v any) string { return pctText(v, false) }

// state مثلِ `_state(passed, na, gap)`: na ⇒ "na"، gap ⇒ "nodata"، وگرنه pass/fail.
// ترتیبِ همین سه شرط درِ پایتون مهم است: `na` بر `gap` مقدم است.
func state(passed bool, na bool, gap bool) string {
	if na {
		return "na"
	}
	if gap {
		return "nodata"
	}
	if passed {
		return "pass"
	}
	return "fail"
}

// truthy مثلِ `bool(x)` درِ پایتون رویِ مقداری که از SQLite/JSON می‌آید.
func truthy(v any) bool { return !isFalsy(v) }

// faInt مثلِ `_fa(int(v))` برایِ برچسبِ شمارۀ دوره درِ جدولِ شاخص ۲.
func faInt(v any) string {
	i, ok := toI(v)
	if !ok {
		return ""
	}
	return faDigits(strconv.FormatInt(i, 10))
}
