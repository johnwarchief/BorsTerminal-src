package tapehistory

import (
	"database/sql"
	"math"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ترتیبِ FLAGS و EVIDENCE_COLS عینِ tape_flag_history.py است؛ همان ترتیب در
// متنِ ردیف‌ها و در JSONِ شواهد می‌نشیند.
var Flags = []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}

var EvidenceCols = []string{"tvol", "p_closing", "p_last", "percent_last",
	"z_tot_tran", "vol_ratio_file", "buyer_power_raw", "resistance_59", "is6"}

// flushS کفِ فاصلهٔ دو نوبتِ ثبت درِ یک روز است — نه کلید.
const flushS = 240 * time.Second

const source = "board"

var ddl = []string{
	`CREATE TABLE IF NOT EXISTS tape_flag_day (
    ins_code TEXT NOT NULL,
    flag TEXT NOT NULL,
    d_even INTEGER NOT NULL,
    symbol TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    evidence TEXT,
    source TEXT,
    PRIMARY KEY (ins_code, flag, d_even))`,
	`CREATE TABLE IF NOT EXISTS tape_flag_day_meta (
    d_even INTEGER PRIMARY KEY,
    first_at TEXT, last_at TEXT,
    passes INTEGER NOT NULL DEFAULT 1,
    symbols INTEGER,
    active_rows INTEGER)`,
}

const (
	upsertRow = "INSERT INTO tape_flag_day(ins_code, flag, d_even, symbol, first_seen_at," +
		"                          last_seen_at, evidence, source)" +
		" VALUES(?,?,?,?,?,?,?,?)" +
		" ON CONFLICT(ins_code, flag, d_even) DO UPDATE SET" +
		"   last_seen_at = excluded.last_seen_at," +
		"   passes = tape_flag_day.passes + 1"
	upsertMeta = "INSERT INTO tape_flag_day_meta(d_even, first_at, last_at, passes, symbols)" +
		" VALUES(?,?,?,1,?)" +
		" ON CONFLICT(d_even) DO UPDATE SET" +
		"   last_at = excluded.last_at," +
		"   passes = tape_flag_day_meta.passes + 1," +
		"   symbols = excluded.symbols"
)

// Recorder وضعیتِ درون‌پروسه‌ایِ ثبت را نگه می‌دارد (پنجرهٔ روز، نشانهٔ آخرین
// نوبت، خطای آخر). مقدارِ صفر آمادهٔ استفاده است.
type Recorder struct {
	mu        sync.Mutex
	ensured   bool
	lastFlush map[int64]time.Time
	lastToken map[int64]string
	lastErr   string
}

func NewRecorder() *Recorder { return &Recorder{} }

func (r *Recorder) LastErr() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.lastErr
}

// Record همان قراردادِ record_observations: پرچم‌هایِ ردیف‌هایِ زنده را برایِ
// `day` می‌نویسد. صفر یعنی «نوبتِ تکراری، پنجرهٔ بسته، یا پرچمی روشن نبود» —
// و خطا هرگز به درخواستِ تابلو نمی‌رسد؛ فقط در LastErr می‌ماند.
func (r *Recorder) Record(db *sql.DB, recs []map[string]any, day int64, token string, now time.Time) (int, error) {
	if db == nil || len(recs) == 0 || day == 0 {
		return 0, nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.lastFlush == nil {
		r.lastFlush = map[int64]time.Time{}
		r.lastToken = map[int64]string{}
	}
	if token != "" && r.lastToken[day] == token {
		return 0, nil
	}
	if t, ok := r.lastFlush[day]; ok && now.Sub(t) < flushS {
		return 0, nil
	}
	// نشانه و پنجره پیش از نوشتن مصرف می‌شوند — عینِ پایتون: نوبتِ ناموفق یا
	// خالی هم پنجرهٔ چهار دقیقه‌ای را می‌سوزاند.
	r.lastFlush[day] = now
	r.lastToken[day] = token
	n, err := r.write(db, recs, day, now)
	if err != nil {
		r.lastErr = err.Error()
		return 0, err
	}
	return n, nil
}

type obsRow struct {
	code, flag, symbol, evidence string
}

func (r *Recorder) write(db *sql.DB, recs []map[string]any, day int64, now time.Time) (int, error) {
	if !r.ensured {
		for _, q := range ddl {
			if _, err := db.Exec(q); err != nil {
				return 0, err
			}
		}
		r.ensured = true
	}
	stamp := now.Format("2006-01-02 15:04:05")
	rows := make([]obsRow, 0, len(recs))
	codes := map[string]bool{}
	for _, rec := range recs {
		if live, _ := rec["is_live"].(bool); !live {
			continue
		}
		code, _ := rec["ins_code"].(string)
		if code == "" {
			continue
		}
		symbol, _ := rec["symbol"].(string)
		ev := evidenceJSON(rec)
		for _, f := range Flags {
			if on, _ := rec[f].(bool); on {
				rows = append(rows, obsRow{code: code, flag: f, symbol: symbol, evidence: ev})
				codes[code] = true
			}
		}
	}
	if len(rows) == 0 {
		return 0, nil
	}
	tx, err := db.Begin()
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback() }()
	for _, row := range rows {
		if _, err := tx.Exec(upsertRow, row.code, row.flag, day, row.symbol,
			stamp, stamp, row.evidence, source); err != nil {
			return 0, err
		}
	}
	if _, err := tx.Exec(upsertMeta, day, stamp, stamp, len(codes)); err != nil {
		return 0, err
	}
	if err := tx.Commit(); err != nil {
		return 0, err
	}
	return len(rows), nil
}

// evidenceJSON شاهدِ اولین دیدار را با همان قالبِ json.dumps پایتون می‌سازد:
// ترتیبِ EVIDENCE_COLS، جداکنندهٔ «, » و «: »، بی‌NaN.
func evidenceJSON(rec map[string]any) string {
	var b strings.Builder
	b.WriteByte('{')
	first := true
	for _, name := range EvidenceCols {
		lit, ok := jsonLiteral(rec[name])
		if !ok {
			continue
		}
		if !first {
			b.WriteString(", ")
		}
		first = false
		b.WriteString(strconv.Quote(name))
		b.WriteString(": ")
		b.WriteString(lit)
	}
	b.WriteByte('}')
	return b.String()
}

func jsonLiteral(v any) (string, bool) {
	switch x := v.(type) {
	case int64:
		return strconv.FormatInt(x, 10), true
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return "", false
		}
		return pyFloat(x), true
	case bool:
		if x {
			return "true", true
		}
		return "false", true
	case string:
		return strconv.Quote(x), true
	}
	return "", false
}

// pyFloat مثلِ reprِ پایتون: 100.0 نه 100، و مرزِ نمادِ توان همان مرزِ
// json.dumps است. قالبِ 'g'ِ Go از هفت رقمِ معنی‌دار به توان می‌افتد (مثلاً
// 1234567.0 را «1.234567e+06» می‌نویسد) ولی پایتون تا شانزده رقم اعشاری می‌نویسد؛
// شاهدِ tvol عددهایِ چندمیلیونی است، پس بدونِ این تفکیک متنِ evidence با
// پایتون یکی نمی‌ماند.
func pyFloat(f float64) string {
	s := strconv.FormatFloat(f, 'e', -1, 64) // کوتاه‌ترین رقم‌ها، همیشه با توان
	mant, expPart, ok := strings.Cut(s, "e")
	if !ok {
		return s
	}
	e, err := strconv.Atoi(expPart)
	if err != nil {
		return s
	}
	neg := strings.HasPrefix(mant, "-")
	if neg {
		mant = mant[1:]
	}
	digits := strings.Replace(mant, ".", "", 1)
	var out string
	if e >= -4 && e <= 15 {
		// نمادِ اعشاری: نقطه بعد از e+1 رقم می‌افتد.
		dp := e + 1
		switch {
		case dp <= 0:
			out = "0." + strings.Repeat("0", -dp) + digits
		case dp >= len(digits):
			out = digits + strings.Repeat("0", dp-len(digits)) + ".0"
		default:
			out = digits[:dp] + "." + digits[dp:]
		}
	} else {
		if len(digits) == 1 {
			out = digits
		} else {
			out = digits[:1] + "." + digits[1:]
		}
		out += "e" + pyExp(e)
	}
	if neg {
		return "-" + out
	}
	return out
}

// pyExp توانِ پایتون را می‌نویسد: علامت همیشه، حداقل دو رقم (e+16، e-05، e+100).
func pyExp(e int) string {
	sign := "+"
	if e < 0 {
		sign = "-"
		e = -e
	}
	d := strconv.Itoa(e)
	if len(d) < 2 {
		d = "0" + d
	}
	return sign + d
}
