package codal

import (
	"regexp"
	"strings"
	"unicode"
)

var (
	reBillionUnit  = regexp.MustCompile(`(?i)(?:^|[\s_/-])(?:b|bn)\s*rials?(?:$|[\s_/-])`)
	reMillionUnit  = regexp.MustCompile(`(?i)(?:^|[\s_/-])(?:m|mn|mln)\s*rials?(?:$|[\s_/-])`)
	reThousandUnit = regexp.MustCompile(`(?i)(?:^|[\s_/-])(?:k|th)\s*rials?(?:$|[\s_/-])`)
)

// cleanUnitString نرمال‌سازی نویسه‌ها: یکپارچه‌سازی فاصله‌ها، حذف ZWNJ، یکنواخت‌سازی ی/ک عربی،
// تبدیل ارقام فارسی و عربی به رقم استاندارد و کوچک‌سازی حروف انگلیسی.
func cleanUnitString(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		switch {
		case r == '\u200c': // نیم‌فاصله (ZWNJ) -> تبدیل به فاصله
			b.WriteRune(' ')
		case r == 0x064a || r == 0x0649: // 'ي' و 'ى' عربی -> 'ی' فارسی
			b.WriteRune(0x06cc)
		case r == 0x0643: // 'ك' عربی -> 'ک' فارسی
			b.WriteRune(0x06a9)
		case r >= '۰' && r <= '۹': // ارقام فارسی
			b.WriteRune('0' + (r - '۰'))
		case r >= '٠' && r <= '٩': // ارقام عربی
			b.WriteRune('0' + (r - '٠'))
		case r == '.' || r == ',' || r == '(' || r == ')' || r == '[' || r == ']' || r == '"' || r == '\'':
			b.WriteRune(' ')
		default:
			b.WriteRune(unicode.ToLower(r))
		}
	}
	// ادغام فاصله‌های متوالی
	return strings.Join(strings.Fields(b.String()), " ")
}

// NormalizeUnit تبدیل رشته واحد مالی به ضریب عددی استاندارد (بر حسب ریال).
// مقادیر پیش‌فرض برای رشته خالی یا ناشناخته ۱٫۰ است.
func NormalizeUnit(unitStr string) float64 {
	clean := cleanUnitString(unitStr)
	if clean == "" {
		return 1.0
	}

	// ۱. بررسی میلیارد (Billion / 1,000,000,000)
	if strings.Contains(clean, "میلیارد") ||
		strings.Contains(clean, "billion") ||
		strings.Contains(clean, "1000000000") ||
		strings.Contains(clean, "10^9") ||
		reBillionUnit.MatchString(clean) {
		return 1000000000.0
	}

	// ۲. بررسی میلیون (Million / 1,000,000)
	if strings.Contains(clean, "میلیون") ||
		strings.Contains(clean, "million") ||
		strings.Contains(clean, "1000000") ||
		strings.Contains(clean, "10^6") ||
		reMillionUnit.MatchString(clean) {
		return 1000000.0
	}

	// ۳. بررسی هزار (Thousand / 1,000)
	if strings.Contains(clean, "هزار") ||
		strings.Contains(clean, "thousand") ||
		strings.Contains(clean, "1000") ||
		strings.Contains(clean, "10^3") ||
		reThousandUnit.MatchString(clean) {
		return 1000.0
	}

	// ۴. ریال / مقدار پیش‌فرض ۱٫۰
	return 1.0
}

// ClassifyUnitToken بازگرداندن توکن متنی استاندارد واحد ('mrl' | 'btl' | nil)
// دقیقا منطبق با قرارداد codal_units.py و internal/fundamental/axis45.go
func ClassifyUnitToken(raw string) *string {
	clean := cleanUnitString(raw)
	if clean == "" {
		return nil
	}
	t := strings.ReplaceAll(clean, " ", "")
	hasCurrency := strings.Contains(t, "ریال") || strings.Contains(t, "تومان") ||
		strings.Contains(t, "rial") || strings.Contains(t, "toman")

	if strings.Contains(t, "میلیارد") || strings.Contains(t, "بیلیون") || strings.Contains(t, "billion") {
		if strings.Contains(t, "تومان") || strings.Contains(t, "toman") {
			btl := "btl"
			return &btl
		}
		return nil
	}

	if strings.Contains(t, "میلیون") || strings.Contains(t, "million") || strings.Contains(t, "mrl") {
		if strings.Contains(t, "ریال") || strings.Contains(t, "rial") || strings.Contains(t, "mrl") || hasCurrency {
			mrl := "mrl"
			return &mrl
		}
	}

	return nil
}
