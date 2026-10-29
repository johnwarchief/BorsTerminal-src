// Package screening رأیِ غربالگریِ هر ردیفِ تابلو است — پورتِ یک‌به‌یکِ
// funnel_engine.screening_eligibility / _state_reason.
//
// وتوها به همان ترتیبِ قطعیتِ پایتون خوانده می‌شوند: نبودِ ردیفِ نشستِ جاری،
// سپس تعلیقِ صریح (stop_reasons)، سپس آخرین وضعیتِ ثبت‌شدۀ نماد. نبودِ هیچ‌یک
// «مجاز» نیست بلکه «وتویی ثبت نشده» است — و ردیف غربال می‌شود.
//
// ردیفِ ورودی همان رکوردِ سریال‌شده (map[string]any) است؛ کلیدِ غایب مثلِ
// row.get در پایتون None می‌دهد، نه خطا.
package screening

import (
	"fmt"
	"strconv"
	"strings"
)

// برچسب‌هایِ رسمیِ instrument_state؛ همان سه ثابتِ funnel_engine.
const (
	forbiddenTitle = "ممنوع"
	permittedTitle = "مجاز"
	stoppedMark    = "متوقف"
)

// faDigits رقمِ ASCII را فارسی می‌کند — همان قاعدهٔ AGENTS (chr(0x06F0+d))؛
// رقمِ دست‌کاری‌شده در متنِ فارسی را می‌دزدد، پس عددِ نمایشی از همین‌جا می‌رود.
func faDigits(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(rune(0x06F0 + int(r-'0')))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// num معادلِ funnel_engine._num است: float(v) و نبود در صورتِ شکست.
func num(v any) (float64, bool) {
	switch n := v.(type) {
	case int64:
		return float64(n), true
	case int:
		return float64(n), true
	case float64:
		return n, true
	case string:
		f, err := strconv.ParseFloat(n, 64)
		return f, err == nil
	default:
		return 0, false
	}
}

// stateReason برچسبِ زمان‌مندِ وضعیت است (_state_reason): وتو در همین نشستِ
// تابلو ثبت شده یا در نشستی پیش‌تر. «توقفِ امروز» گفته نمی‌شود چون لاگِ
// instrument_state رویدادمحور و ساعت‌مند است.
func stateReason(row map[string]any, title string, sessionDay int64) string {
	stD, hasD := num(row["st_d"])
	d := float64(sessionDay)
	if d == 0 {
		// session_day غایب/صفر ⇒ d_evenِ خودِ ردیف (پایتون: `session_day if
		// session_day else row.get("d_even")`).
		if v, ok := num(row["d_even"]); ok {
			d = v
		}
	}
	hhmm := ""
	if h, ok := num(row["st_h"]); ok && h != 0 {
		s := fmt.Sprintf("%06d", int(h))
		hhmm = s[:2] + ":" + s[2:4]
	}
	same := hasD && stD != 0 && d != 0 && stD == d
	if same {
		out := title + " (طی معاملات"
		if hhmm != "" {
			out += " — ساعت " + faDigits(hhmm)
		}
		return out + ")"
	}
	if hasD && stD != 0 {
		return title + " — از نشستِ " + faDigits(strconv.FormatInt(int64(stD), 10))
	}
	return "وضعیتِ ثبت‌شدۀ نماد: " + title
}

// Eligibility رأیِ یک ردیف را برمی‌گرداند: (قابلِ‌غربال؟، کدِ علت، علتِ فارسی).
//
// فقط از دادهٔ رسمیِ خودِ ردیف می‌خواند. sessionDay صفر یعنی «نشستِ جاری
// معلوم نیست» و آن‌گاه d_evenِ ردیف به کار می‌رود، عیناً مثلِ پایتون.
func Eligibility(row map[string]any, sessionDay int64) (bool, string, string) {
	title := strings.TrimSpace(strOf(row["st_title"]))
	code := strings.TrimSpace(strOf(row["st_code"]))
	// is_live باید *دقیقاً* false باشد (پایتون: `is False`)؛ کلیدِ غایب یا nil
	// وتو نمی‌کند.
	if live, ok := row["is_live"].(bool); ok && !live {
		return false, "NOT_LIVE_SESSION", "درِ تازۀترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)"
	}
	if stop := strOf(row["stop_state"]); stop != "" {
		return false, "STOPPED", "متوقف: " + stop
	}
	if strings.HasPrefix(title, forbiddenTitle) {
		return false, "FORBIDDEN_STATE", stateReason(row, title, sessionDay)
	}
	if strings.Contains(title, stoppedMark) {
		return false, "STOPPED", stateReason(row, title, sessionDay)
	}
	if strings.HasPrefix(title, permittedTitle) {
		return true, "PERMITTED_STATE", "وضعیتِ ثبت‌شدۀ نماد: " + title
	}
	if title != "" || code != "" {
		return true, "NO_BLOCKING_STATE", "وتوی معتبری ثبت نشده (وضعیت: " + titleOr(title, code) + ")"
	}
	return true, "NO_BLOCKING_STATE", "وضعیتی برایِ این نماد ثبت نشده — وتویی نیست"
}

// strOf ستونِ متنیِ سریال‌شده را می‌خواند؛ کلیدِ غایب یا nil رشتهٔ خالی است
// (همان row.get(k) or ""). ستون‌هایِ st_* / stop_state در بانک TEXT‌اند.
func strOf(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func titleOr(title, code string) string {
	if title != "" {
		return title
	}
	return code
}
