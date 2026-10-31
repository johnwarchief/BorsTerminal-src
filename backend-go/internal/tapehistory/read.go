package tapehistory

// گاردِ چهارگانهٔ bors-architecture (پلنِ B4 §۳). What changes: لایۀ *خواندنِ*
// tape_flag_history.py در کنارِ لایۀ نوشتنِ موجود (Recorder). Invariants: هیچ
// داوریِ تازه‌ای نمی‌سازد؛ «روزِ ثبت‌نشده» با «روزِ غیرفعال» یکی نمی‌شود؛
// کلیدِ روز درِ JSON رشته است (orjson کلیدِ عددی را رد می‌کند — شاهدِ زنده
// ۱۴۰۵-۰۷-۲۱)؛ user.db درِ فازِ A نوشته نمی‌شود، پس `ensure()` پایتون اینجا
// ترجمه ندارد و تفاوتش درِ گیت اعلام می‌شود. Lockstep: هیچ (نه spec، نه ESLint،
// نه وابستگی). Guard: طلایی‌هایِ tape_* درِ testdata/golden/s1 با همان فیکسچر.
// Rollback: revertِ همین کامیت.

import (
	"context"
	"database/sql"
	"encoding/json"
	"strconv"
	"strings"
)

// Reader همان اتصالِ user.db و همان حالتِ پروسهٔ `write_error` را می‌خواند که
// مسیرِ نوشتن (Recorder) می‌نویسد — درِ پایتون `_last_err` یک متغیرِ ماژول است،
// پس «آخرین خطایِ نوشتن» درِ پاسخِ خواندن هم از همان پروسه می‌آید، نه از داده.
type Reader struct {
	user    *sql.DB
	lastErr func() string
}

func NewReader(user *sql.DB, lastErr func() string) *Reader {
	return &Reader{user: user, lastErr: lastErr}
}

// ParseCodes عینِ `[s.strip() for s in codes.split(",") if s.strip()][:400]`.
func ParseCodes(raw string) []string {
	out := []string{}
	for _, part := range strings.Split(raw, ",") {
		s := strings.TrimSpace(part)
		if s == "" {
			continue
		}
		out = append(out, s)
	}
	if len(out) > 400 {
		out = out[:400]
	}
	return out
}

// ClampDays عینِ `max(1, min(int(days or 20), 120))`: صفر «بی‌عدد» خوانده می‌شود
// و ۲۰ می‌گیرد، ولی منفی همان‌طور می‌ماند و بعد به ۱ بالا می‌آید.
func ClampDays(days int) int {
	if days == 0 {
		days = 20
	}
	if days > 120 {
		days = 120
	}
	if days < 1 {
		return 1
	}
	return days
}

// TradingDays روزهایی که **واقعاً رصد شده‌اند** — نه هر روزِ تقویمی. خطایِ SQLite
// (مثلاً جدولِ نبود) فهرستِ خالی می‌دهد، نه کرش.
func (r *Reader) TradingDays(ctx context.Context, limit int) []int64 {
	rows, err := r.user.QueryContext(ctx,
		"SELECT d_even FROM tape_flag_day_meta ORDER BY d_even DESC LIMIT ?", limit)
	if err != nil {
		return nil
	}
	defer rows.Close()
	out := []int64{}
	for rows.Next() {
		var d int64
		if err := rows.Scan(&d); err != nil {
			return out
		}
		out = append(out, d)
	}
	return out
}

// ReliableFrom اولین روزی که این جدول درِ آن نوشته شده؛ پیش‌از آن هیچ سابقه‌ای
// قابل‌اعتماد نیست.
func (r *Reader) ReliableFrom(ctx context.Context) any {
	var d sql.NullInt64
	err := r.user.QueryRowContext(ctx, "SELECT MIN(d_even) FROM tape_flag_day_meta").Scan(&d)
	if err != nil || !d.Valid {
		return nil
	}
	return d.Int64
}

func inPlaceholders(n int) string {
	if n <= 0 {
		return ""
	}
	return strings.TrimSuffix(strings.Repeat("?,", n), ",")
}

// flagShell ساختارِ اولیهٔ یکِ فیلتر — عینِ dictِ پایتون، با total و last_seen_at.
func flagShell() map[string]any {
	return map[string]any{"days": map[string]any{}, "total": 0, "last_seen_at": nil}
}

// HistoryFor سابقۀ چندروزۀ هفت فیلتر برایِ چند نماد، به‌همراہ تقویمِ ثبت.
//
// دو فهرستِ جدا و دو شمارِ placeholder: اگر یکِ `marks` برایِ هر دو مصرف شود،
// شمارۀ نماد با شمارۀ روز نمی‌خواند و کوئری بی‌صدا هیچ ردیفی برنمی‌گرداند
// (سوختنِ واقعیِ ۱۴۰۵-۰۷-۲۱ درِ نگهبان).
func (r *Reader) HistoryFor(ctx context.Context, codes []string, days int) map[string]any {
	cal := reverseDays(r.TradingDays(ctx, days))
	out := map[string]any{
		"days":          cal,
		"reliable_from": r.ReliableFrom(ctx),
		"by_symbol":     map[string]any{},
		"flags":         append([]string(nil), Flags...),
		"write_error":   r.processError(),
	}
	if len(codes) == 0 || len(cal) == 0 {
		// تقویمِ خالی یعنی هنوز هیچ روزی رصد نشده — کوئری با `IN ()` نمی‌دود و
		// پاسخِ خالی صادق است: سابقه‌ای نیست، نه «همه‌جا غیرفعال».
		return out
	}
	query := "SELECT ins_code, flag, d_even, first_seen_at, last_seen_at, passes, evidence" +
		" FROM tape_flag_day WHERE ins_code IN (" + inPlaceholders(len(codes)) + ")" +
		" AND d_even IN (" + inPlaceholders(len(cal)) + ")"
	args := make([]any, 0, len(codes)+len(cal))
	for _, c := range codes {
		args = append(args, c)
	}
	for _, d := range cal {
		args = append(args, d)
	}
	rows, err := r.user.QueryContext(ctx, query, args...)
	if err != nil {
		// درِ پایتون نامِ استثنا و متنش درِ write_error می‌نشیند؛ Go همان فیلد را
		// با خطایِ خودش پر می‌کند (متن یکی نیست و این درِ گزارشِ B4 اعلام می‌شود).
		msg := err.Error()
		out["write_error"] = msg
		return out
	}
	defer rows.Close()
	by := out["by_symbol"].(map[string]any)
	for rows.Next() {
		var (
			code, flag string
			dEven      int64
			firstAt    sql.NullString
			lastAt     sql.NullString
			passes     sql.NullInt64
			evidence   sql.NullString
		)
		if err := rows.Scan(&code, &flag, &dEven, &firstAt, &lastAt, &passes, &evidence); err != nil {
			break
		}
		s, _ := by[code].(map[string]any)
		if s == nil {
			s = map[string]any{}
			by[code] = s
		}
		f, _ := s[flag].(map[string]any)
		if f == nil {
			f = flagShell()
			s[flag] = f
		}
		daysMap := f["days"].(map[string]any)
		daysMap[strconv.FormatInt(dEven, 10)] = map[string]any{
			"active":   true,
			"first_at": nullString(firstAt),
			"last_at":  nullString(lastAt),
			// `int(passes or 1)` درِ پایتون: صفرِ ذخیره‌شده «یکِ عبور» خوانده می‌شود.
			"passes":   passesOrOne(passes),
			"evidence": decodeEvidence(evidence),
		}
		f["total"] = f["total"].(int) + 1
		if lastAt.Valid && lastAt.String != "" {
			cur, _ := f["last_seen_at"].(string)
			if f["last_seen_at"] == nil || lastAt.String > cur {
				f["last_seen_at"] = lastAt.String
			}
		}
	}

	// روزهایِ ثبت‌شدۀ بدونِ ردیف = «غیرفعال» (نه نبودِ داده). ردیفِ موجود هرگز
	// با placeholder بازنویسی نمی‌شود (setdefault).
	for _, code := range codes {
		s, _ := by[code].(map[string]any)
		if s == nil {
			s = map[string]any{}
			by[code] = s
		}
		for _, flag := range Flags {
			f, _ := s[flag].(map[string]any)
			if f == nil {
				f = flagShell()
				s[flag] = f
			}
			daysMap := f["days"].(map[string]any)
			for _, d := range cal {
				key := strconv.FormatInt(d, 10)
				if _, ok := daysMap[key]; !ok {
					daysMap[key] = map[string]any{"active": false, "first_at": nil,
						"last_at": nil, "passes": 0, "evidence": map[string]any{}}
				}
			}
		}
	}
	return out
}

func (r *Reader) processError() any {
	if r.lastErr == nil {
		return nil
	}
	if s := r.lastErr(); s != "" {
		return s
	}
	return nil
}

func nullString(s sql.NullString) any {
	if !s.Valid {
		return nil
	}
	return s.String
}

func passesOrOne(v sql.NullInt64) int {
	if !v.Valid || v.Int64 == 0 {
		return 1
	}
	return int(v.Int64)
}

// decodeEvidence: متنِ ستونِ evidence همان JSONِ نوشته‌شده است؛ بی‌متن یا
// بی‌خوانا ⇒ {} (عینِ `except (TypeError, ValueError)` درِ پایتون).
func decodeEvidence(s sql.NullString) any {
	if !s.Valid || s.String == "" {
		return map[string]any{}
	}
	var v any
	if err := json.Unmarshal([]byte(s.String), &v); err != nil {
		return map[string]any{}
	}
	if v == nil {
		return map[string]any{}
	}
	return v
}

func reverseDays(in []int64) []int64 {
	out := make([]int64, 0, len(in))
	for i := len(in) - 1; i >= 0; i-- {
		out = append(out, in[i])
	}
	return out
}
