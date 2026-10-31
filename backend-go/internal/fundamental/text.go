package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳): این فایل هیچ قاعدهٔ
// تازه‌ای نمی‌سازد — فقط همان تبدیل‌هایِ رشته/عددِ لایۀ canonicalِ پایتون
// (`fts_engine.norm_fa` و `str()`/`float()`/`int()`). What changes: دو تابعِ
// کمکیِ تازه درِ Go. Invariants: معنای «خالی بودنِ رشته» و «فalsy» باید با
// پایتون یکی بماند، چون رتبه‌بندیِ ردیف‌ها به آن‌ها تکیه است. Lockstep: هیچ
// (نه spec، نه ESLint، نه گاردِ رابط). Guard: طلایی‌هایِ s1 + reference_test.go.
// Rollback: revertِ همین کامیت.

import (
	"math"
	"strconv"
	"strings"

	"borsterminal/backend/internal/period"
)

// normFa عینِ fts_engine.norm_fa: ي→ی، ك→ک، ى→ی و حذفِ نیم‌فاصله. بی‌این
// «تلفيقي» هرگز با «تلفیقی» مطابقت نمی‌کند (باگِ واقعیِ v7.3 درِ پایتون).
var normFaRepl = strings.NewReplacer("ي", "ی", "ك", "ک", "ى", "ی", "‌", "")

func normFa(s string) string { return normFaRepl.Replace(s) }

// pyStr مثلِ str(x) درِ پایتون رویِ مقداری که از SQLite می‌آید. تنها مصرفِ آن
// درِ بازکردنِ تساویِ `statement_rank` است (signatureِ رشته‌ایِ
// quarter_reference_rows) و tracing_no درِ بانک یکتا است، پس آن تساوی رویِ دادهٔ
// واقعی هرگز ساخته نمی‌شود؛ رشته‌ها با این‌جا باز هم به همان ترتیبِ پایتون
// مقایسه می‌شوند. رقمِ صحیحِ float مثلِ reprِ پایتون «.0» می‌گیرد.
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case string:
		return x
	case bool:
		if x {
			return "True"
		}
		return "False"
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case float64:
		if math.IsNaN(x) {
			return "nan"
		}
		if math.IsInf(x, 1) {
			return "inf"
		}
		if math.IsInf(x, -1) {
			return "-inf"
		}
		s := strconv.FormatFloat(x, 'g', -1, 64)
		if !strings.ContainsAny(s, ".eE") {
			s += ".0"
		}
		return s
	default:
		return strconv.FormatFloat(toF(x), 'g', -1, 64)
	}
}

// strOr مثلِ `str(x or "")` درِ پایتون: هیچ‌ارزشِ کاذب (None، صفر، رشتهٔ خالی،
// false) به رشتهٔ خالی می‌رسد، نه به «None» یا «0».
func strOr(v any) string {
	if isFalsy(v) {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return pyStr(v)
}

func isFalsy(v any) bool {
	switch x := v.(type) {
	case nil:
		return true
	case string:
		return x == ""
	case bool:
		return !x
	case int:
		return x == 0
	case int64:
		return x == 0
	case float64:
		return x == 0
	}
	return false
}

// toF مثلِ float(v) درِ fts_engine/_f: بی‌عدد ⇒ 0.0 (پایتون هم همین‌جا جز می‌گیرد).
func toF(v any) float64 {
	switch x := v.(type) {
	case nil:
		return 0
	case float64:
		return x
	case float32:
		return float64(x)
	case int:
		return float64(x)
	case int64:
		return float64(x)
	case bool:
		if x {
			return 1
		}
		return 0
	case string:
		f, err := strconv.ParseFloat(strings.TrimSpace(x), 64)
		if err != nil {
			return 0
		}
		return f
	}
	return 0
}

// toI مثلِ int(v) رویِ مقداری که از SQLite می‌آید؛ بی‌عدد ⇒ ok=false تا
// مصرف‌کننده بتواند شاخهٔ TypeErrorِ پایتون را بازتولید کند.
func toI(v any) (int64, bool) {
	switch x := v.(type) {
	case nil:
		return 0, false
	case int:
		return int64(x), true
	case int64:
		return x, true
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return 0, false
		}
		return int64(x), true
	case string:
		s := strings.TrimSpace(x)
		if n, err := strconv.ParseInt(s, 10, 64); err == nil {
			return n, true
		}
		if f, err := strconv.ParseFloat(s, 64); err == nil {
			return int64(f), true
		}
		return 0, false
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	}
	return 0, false
}

// trailing helpers ------------------------------------------------------------

// rowMap یک ردیفِ SQLite را به نقشهٔ کلید→مقدارِ پایتون تبدیل می‌کند (dict(raw)).
func copyRow(row map[string]any) map[string]any {
	out := make(map[string]any, len(row)+2)
	for k, v := range row {
		out[k] = v
	}
	return out
}

// trimSpace مثلِ str.strip() — از لایۀ canonicalِ دوره می‌خواند تا «جای خالی»
// درِ همه‌جا یک معنا داشته باشد.
func trimSpace(s string) string { return period.Trim(s) }
