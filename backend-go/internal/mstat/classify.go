package mstat

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

const (
	paperStock = "stock"
	paperRight = "right"
	paperFund  = "fund"
)

// normalized همان _norm: ي/ى→ی، ك→ک، حذفِ نیم‌فاصله و ZWJ، trim.
var normalized = strings.NewReplacer(
	"\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9",
	"\u200C", "", "\u200D", "",
)

func norm(s string) string { return strings.TrimSpace(normalized.Replace(s)) }

// wordHit همان _word_hit: کلید باید از چپ مرزِ واژه داشته باشد.
func wordHit(name, key string) bool {
	rs, ks := []rune(name), []rune(key)
	if len(ks) == 0 {
		return false
	}
	for i := 0; i+len(ks) <= len(rs); i++ {
		if string(rs[i:i+len(ks)]) != key {
			continue
		}
		if i == 0 || !unicode.IsLetter(rs[i-1]) {
			return true
		}
	}
	return false
}

// wholeWord همان _whole_word: مرز از دو سو.
func wholeWord(name, key string) bool {
	rs, ks := []rune(name), []rune(key)
	if len(ks) == 0 {
		return false
	}
	for i := 0; i+len(ks) <= len(rs); i++ {
		if string(rs[i:i+len(ks)]) != key {
			continue
		}
		left := i == 0 || !unicode.IsLetter(rs[i-1])
		right := i+len(ks) >= len(rs) || !unicode.IsLetter(rs[i+len(ks)])
		if left && right {
			return true
		}
	}
	return false
}

func anySub(s string, keys []string) bool {
	for _, k := range keys {
		if strings.Contains(s, k) {
			return true
		}
	}
	return false
}

func fundKind(name, symbol string) string {
	full := name + " " + symbol
	for _, fk := range fundKindTerms {
		for _, k := range fk.Keys {
			if wordHit(full, k) {
				return fk.Kind
			}
		}
	}
	// rstripِ پایتون همهٔ فاصله‌هایِ یونیکد را می‌زداید (از جمله NBSP)؛ برشِ
	// مجموعهٔ بایتِ محدود، نامی با فاصلهٔ نشکنِ پایانی را به «etf» می‌انداخت.
	tail := strings.TrimRightFunc(name, unicode.IsSpace)
	if strings.HasSuffix(tail, "-د") {
		return "fixed"
	}
	if strings.HasSuffix(tail, "-س") || strings.HasSuffix(tail, "-ب") {
		return "equity"
	}
	return "etf"
}

func isOption(name, symbol string) bool {
	full := name + " " + symbol
	return anySub(full, optionKeys)
}

func isFund(name, symbol, sector string) bool {
	n, c := norm(name), norm(sector)
	return anySub(n, fundName) || anySub(c, fundSector)
}

func isBond(symbol, name, sector string) bool {
	s, n, c := strings.ToUpper(norm(symbol)), norm(name), norm(sector)
	if hasAnyPrefix(s, bondSymPrefix) || anySub(n, bondName) || anySub(c, bondSector) {
		return true
	}
	for _, k := range bondWord {
		if wholeWord(n, k) {
			return true
		}
	}
	if s != "" {
		last, _ := utf8.DecodeLastRuneInString(s)
		if unicode.IsDigit(last) {
			for _, k := range futuresWord {
				if wholeWord(n, k) {
					return true
				}
			}
		}
	}
	return false
}

func hasAnyPrefix(s string, prefixes []string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}

func isTeseh(sector string) bool { return anySub(norm(sector), tesehSector) }

func endsWithH(symbol string) bool {
	s := strings.ToUpper(norm(symbol))
	return s != "" && strings.HasSuffix(s, "ح")
}

// classify همان ترتیبِ assetType.ts: اختیار → صندوق → اوراق → تسهیلات →
// حق تقدم → paperType.
func classify(paperType *int64, name, symbol, sector string) (string, string) {
	if isOption(name, symbol) {
		return "other", "other"
	}
	if isFund(name, symbol, sector) {
		return paperFund, fundKind(name, symbol)
	}
	if isBond(symbol, name, sector) {
		return "other", "other"
	}
	if isTeseh(sector) {
		return "other", "other"
	}
	if endsWithH(symbol) || strings.Contains(norm(name), "حق تقدم") {
		return paperRight, "right"
	}
	if paperType == nil {
		return "other", "other"
	}
	switch *paperType {
	case 1, 2:
		return paperStock, "stock"
	case 4:
		return paperRight, "right"
	case 8:
		if isFund(name, symbol, sector) {
			return paperFund, fundKind(name, symbol)
		}
		if endsWithH(symbol) || strings.Contains(norm(name), "حق تقدم") {
			return paperRight, "right"
		}
		return paperStock, "stock"
	}
	return "other", "other"
}
