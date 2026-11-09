package httpapi

import (
	"math"
	"math/big"
	"net/http"
	"strings"
	"unicode"
)

// IntQuery پارامترِ صحیحِ مقولۀ کوئری با همان بدنهٔ 422 که FastAPI می‌دهد
// (`int_parsing`، loc = ["query", name])؛ این نسخۀ **مرجعِ مشترک** است و
// internal/chart/handlers.go نگه‌دارندۀ کپیِ خصوصیِ خودش است (پوشش‌داده‌شدۀ
// گیتِ B3؛ دست‌نخورده).
//
// رفتارِ اندازه‌گیری‌شده روی FastAPI 0.141.1 / pydantic 2.12.5 با امضایِ
// `limit: int = 16` (api/fundamental.py:2216) و `days: int = 20`
// (api/market.py:1449) — شاهدِ زنده درِ query_test.go:
//   - کلیدِ غایب               ⇒ مقدارِ پیش‌فرضِ امضا
//   - کلیدِ حاضر و خالی        ⇒ 422 با input="" (خالی «کلید نیست» نیست)
//   - `1.0` / `007` / `+7`      ⇒ 200 (lax؛ کسری که تمام‌اش صفر است صحیح است)
//   - `1.9` / `1e2` / `5.`      ⇒ 422
//   - ` 7 ` / تب / NBSP         ⇒ 200 (پیرایشِ فضای Unicode، دو سر)
//   - `99999999999999999999`    ⇒ 200 (بی‌سقف؛ خودِ مسیر clamp می‌کند)
//   - کلیدِ تکراری              ⇒ آخرینِ occurrences (starlette QueryParams)،
//     نه نخستینِ `URL.Query().Get()`
func IntQuery(w http.ResponseWriter, r *http.Request, name string, def int) (int, bool) {
	vals := r.URL.Query()[name]
	if len(vals) == 0 {
		return def, true
	}
	raw := vals[len(vals)-1]
	v, ok := parseLaxInt(raw)
	if !ok {
		UnprocessableAs(w, "int_parsing", []string{"query", name},
			"Input should be a valid integer, unable to parse string as an integer", raw)
		return 0, false
	}
	return v, true
}

// parseLaxInt همان «int در برابر رشته»ِ pydantic در حالتِ lax است، با همین
// قاعدۀ سنجیده‌شده: پیرایشِ فضای Unicode، یکِ نشانه، جداکنندۀ `_` فقط میانِ
// رقم‌ها (Python-style)، و شکلِ اعشاریِ «رقم‌ها.رقم‌ها» که فقط وقتی پذیرفتنی است
// کسرش تمام‌صفر باشد (`5.` و `.5` و توانیِ `1e2` هر سه 422).
//
// قدرهایِ بزرگ‌تر از int64 به MinInt/MaxInt سیرابه می‌شوند. هر دو مصرف‌کنندۀ
// IntQuery پیش از هر کاری min/max می‌زنند (`clampLimit`ِ بنیادی تا 40 و
// `tapehistory.ClampDays` تا 120)، پس سیرابه با عددِ بی‌سقفِ پایتون یکِ نتیجه
// می‌دهد؛ هر مصرف‌کنندۀ تازه‌ای که limit را بی‌clamp بکار ببرد باید این را بداند.
func parseLaxInt(raw string) (int, bool) {
	s := strings.TrimFunc(raw, unicode.IsSpace)
	if s == "" {
		return 0, false
	}
	neg := false
	if s[0] == '+' || s[0] == '-' {
		neg = s[0] == '-'
		s = s[1:]
	}
	intPart, frac, isFloat, ok := splitDecimal(s)
	if !ok {
		return 0, false
	}
	if isFloat {
		// کسرِ غیرصفر درِ پایتون 422 است؛ اعشاریِ صحیح‌العدد پذیرفته می‌شود.
		if strings.Trim(frac, "0") != "" {
			return 0, false
		}
	}
	if v, ok := applySign(intPart, neg); ok {
		return v, true
	}
	return 0, false
}

// splitDecimal رشتهٔ بی‌نشانه را به (قسمتِ صحیح، قسمتِ کسری) می‌شکند و قواعدِ
// رقم/زیرخطِ pydantic را همین‌جا می‌سنجد: «رقم‌ها» یا «رقم‌ها.رقم‌ها»؛ هیچ چیزِ
// دیگری (نقطهٔ پایانی، نقطۀ آغازی، نمادِ توانی، `_` درِ کسر) پذیرفته نیست.
func splitDecimal(s string) (intPart, frac string, isFloat, ok bool) {
	if i := strings.IndexByte(s, '.'); i >= 0 {
		intPart, frac, isFloat = s[:i], s[i+1:], true
	} else {
		intPart = s
	}
	if !isDigits(intPart) {
		return "", "", false, false
	}
	if isFloat && !isDigits(frac) {
		return "", "", false, false
	}
	return intPart, frac, isFloat, true
}

// isDigits رقم‌هایِ ASCII را با جداکنندۀ `_`ِ میانی می‌پذیرد؛ ارقامِ فارسی،
// عربی و تمام‌عرضی درِ پایتون 422 می‌گیرند، پس اینجا هم نه.
func isDigits(s string) bool {
	if s == "" {
		return false
	}
	prevDigit := false
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c == '_':
			// نه آغاز، نه پایان، نه دو تا پشتِ هم.
			if !prevDigit || i == len(s)-1 {
				return false
			}
			prevDigit = false
		case c >= '0' && c <= '9':
			prevDigit = true
		default:
			return false
		}
	}
	return true
}

// applySign صحیحِ بی‌سقف را به int می‌رساند؛ جداکننده‌هایِ `_` (که isDigits
// جایِ درستشان را تضمین کرده) حذف می‌شوند، بی‌سقفی به نزدیک‌ترین کرانِ int
// (سیرابه، نه خطا) و صفرهایِ پیشِ رقم حذف می‌شوند تا رشتهٔ هزاررقمی ارزان بماند.
func applySign(digits string, neg bool) (int, bool) {
	digits = strings.TrimLeft(strings.ReplaceAll(digits, "_", ""), "0")
	if digits == "" {
		return 0, true
	}
	if neg {
		digits = "-" + digits
	}
	b, ok := new(big.Int).SetString(digits, 10)
	if !ok {
		return 0, false
	}
	if !b.IsInt64() {
		if b.Sign() > 0 {
			return math.MaxInt, true
		}
		return math.MinInt, true
	}
	n := b.Int64()
	if n > int64(math.MaxInt) {
		return math.MaxInt, true
	}
	if n < int64(math.MinInt) {
		return math.MinInt, true
	}
	return int(n), true
}

// StringQuery رشتهٔ کوئری با همان قاعدۀ تکرارِ IntQuery: starlette آخرین
// occurrence را می‌دهد، `URL.Query().Get()` نخستین را. کلیدِ غایب ⇒ پیش‌فرض.
// (بندِ ۵ مأموریت: «متنِ فرستاده‌شده» با «متنِ انتخاب‌شده» یکی نیست؛ پنلِ
// مالک ممکن است یکِ فیلتر را دو بار بفرستد.)
func StringQuery(r *http.Request, name, def string) string {
	vals := r.URL.Query()[name]
	if len(vals) == 0 {
		return def
	}
	return vals[len(vals)-1]
}
