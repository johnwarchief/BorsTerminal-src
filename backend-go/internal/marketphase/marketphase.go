// Package marketphase تنها تعریفِ «جلسه در کدام مرحله است» — پورتِ
// market_phase.py. هیچ آستانه‌ای این‌جا ساخته نمی‌شود: فقط نگاشتِ وضعیتِ
// رسمی/تقویم به پنج مرحله و «چه چیزی در این مرحله معنا دارد».
package marketphase

import (
	"database/sql"
	"strings"
	"time"
	"unicode"
)

const (
	PreOpen    = "pre_open"
	Continuous = "continuous"
	Closed     = "closed"
	Holiday    = "holiday"
	Unknown    = "unknown"
)

var labels = map[string]string{
	PreOpen:    "پیش از آغازِ معاملات",
	Continuous: "معاملات جاری",
	Closed:     "پایانِ نشست",
	Holiday:    "تعطیلِ رسمی",
	Unknown:    "مرحل نامشخص",
}

// compOrder ترتیبِ کلیدها در not_computable است؛ dictِ پایتون ترتیبِ درج دارد
// و همان ترتیب در پاسخ می‌نشیند.
var compOrder = []string{"realized_flow", "order_pressure", "session_vs_threshold", "close_price_final"}

var computable = map[string]map[string]bool{
	PreOpen:    {"realized_flow": false, "order_pressure": true, "session_vs_threshold": false, "close_price_final": false},
	Continuous: {"realized_flow": true, "order_pressure": true, "session_vs_threshold": true, "close_price_final": false},
	Closed:     {"realized_flow": true, "order_pressure": false, "session_vs_threshold": true, "close_price_final": true},
	Holiday:    {"realized_flow": true, "order_pressure": false, "session_vs_threshold": true, "close_price_final": true},
	Unknown:    {"realized_flow": false, "order_pressure": false, "session_vs_threshold": false, "close_price_final": false},
}

var whyNot = map[string]string{
	"realized_flow":        "هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست",
	"session_vs_threshold": "جمعِ نشست کامل نشده، پس با آستانۀِ تمام‌روز سنجیده نمی‌شود",
	"close_price_final":    "قیمت پایانیِ نهایی هنوز ساخته نشده",
	"order_pressure":       "دفترِ سفارشِ همین نشست در دسترس نیست",
}

// Phase همان بدنهٔ resolve است. فیلدهایِ * به‌معنای «نبود» (null) هستند، نه صفر.
type Phase struct {
	Phase              string            `json:"phase"`
	Label              string            `json:"label"`
	PhaseSource        string            `json:"phase_source"`
	Official           bool              `json:"official"`
	OfficialState      *string           `json:"official_state"`
	OfficialStateTitle *string           `json:"official_state_title"`
	SessionDay         *int64            `json:"session_day"`
	ActivityHEven      *int64            `json:"activity_h_even"`
	IsLive             bool              `json:"is_live"`
	VerdictAllowed     bool              `json:"verdict_allowed"`
	Computable         map[string]bool   `json:"computable"`
	NotComputable      []string          `json:"not_computable"`
	WhyNot             map[string]string `json:"why_not"`
	DataUpdatedAt      *string           `json:"data_updated_at"`
	ClockNow           string            `json:"clock_now"`
	SessionStart       string            `json:"session_start"`
	SessionEnd         string            `json:"session_end"`
}

// stripPy همان str.strip()ِ پایتون: U+001C..U+001F هم whitespaceِ پایتون‌اند
// ولی unicode.IsSpace نیستند.
func stripPy(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1C && r <= 0x1F)
	})
}

func daysIn(y int, m time.Month) int {
	return time.Date(y, m+1, 0, 0, 0, 0, 0, time.UTC).Day()
}

// dateFromDEven همان _d_even_to_date: تاریخِ معتبر یا «نیست». از datetime.date
// سخت‌گیرتر است: ۳۰ فوریه و ماهِ ۱۳ هم رد می‌شوند، نه اینکه غلت بخورند.
func dateFromDEven(d int64) (time.Time, bool) {
	if d <= 0 {
		return time.Time{}, false
	}
	y := int(d / 10000)
	m := time.Month((d / 100) % 100)
	day := int(d % 100)
	if y < 1 || y > 9999 || m < 1 || m > 12 || day < 1 || day > daysIn(y, m) {
		return time.Time{}, false
	}
	return time.Date(y, m, day, 0, 0, 0, 0, time.UTC), true
}

func isTehranWeekend(d time.Time) bool {
	wd := d.Weekday()
	return wd == time.Thursday || wd == time.Friday
}

func minuteOfDay(t time.Time) int { return t.Hour()*60 + t.Minute() }

// Resolve مرحلِ جلسه را از وضعیتِ رسمی (و در نبودش، از تقویم/ساعت) می‌سازد.
// now تزریقی است تا تست ساعتِ دیواریِ ماشین را مصرف نکند.
func Resolve(officialState, officialTitle *string, activityDay, activityHEven *int64,
	updatedAt *string, boardDay *int64, now time.Time) Phase {
	var st *string
	if officialState != nil {
		if v := strings.ToUpper(stripPy(*officialState)); v != "" {
			st = &v
		}
	}
	var title *string
	if officialTitle != nil {
		if v := stripPy(*officialTitle); v != "" {
			title = &v
		}
	}
	var act *time.Time
	if activityDay != nil {
		if t, ok := dateFromDEven(*activityDay); ok {
			act = &t
		}
	}
	if act == nil && boardDay != nil {
		if t, ok := dateFromDEven(*boardDay); ok {
			act = &t
		}
	}
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	officialSeen := st != nil || title != nil
	officiallyClosed := (st != nil && *st == "F") || (title != nil && strings.Contains(*title, "بسته"))
	officiallyOpen := title != nil && strings.HasSuffix(*title, "باز")
	sameDay := act != nil && act.Equal(today)
	weekend := act != nil && isTehranWeekend(*act)

	var phase, source string
	switch {
	case officiallyOpen:
		// وضعیتِ رسمی می‌گوید باز است؛ مرزهایِ حراجِ پیش‌گشایش/پیش‌بستن
		// منبعِ تأییدشده ندارند و ادعا نمی‌شوند. این شاخه بر تعطیلی مقدم است.
		phase, source = Continuous, "tsetmc_marketState"
	case officiallyClosed:
		hm := minuteOfDay(now)
		switch {
		case weekend:
			// تعطیلی اول می‌آید: پنجشنبه/جمعه با «نشستِ تمام‌شده» یکی نیست.
			phase = Holiday
		case sameDay && hm < 9*60:
			phase = PreOpen
		case sameDay && hm < 12*60+30:
			// بازار «بسته» می‌گوید ولی ساعت در پنجرهٔ معاملات است: میان‌پرده،
			// قطعِ موقت، یا سینکِ میانی. مرحلهٔ تازه اختراع نمی‌شود.
			phase = Unknown
		default:
			phase = Closed
		}
		source = "tsetmc_marketState"
	case officialSeen:
		phase, source = Unknown, "tsetmc_marketState_unmapped"
	default:
		// هیچ وضعیتِ رسمی‌ای نرسیده؛ ساعت فقط «احتمال» می‌دهد.
		hm := minuteOfDay(now)
		switch {
		case weekend:
			phase, source = Holiday, "calendar"
		case sameDay && hm < 9*60:
			phase, source = PreOpen, "calendar"
		case sameDay && hm >= 12*60+30:
			phase, source = Closed, "calendar"
		default:
			phase, source = Unknown, "none"
		}
	}
	// هر فراخوانی نقشهٔ تازه می‌گیرد: پایتون هم dict(comp) می‌سازد. اگر نقشهٔ
	// بسته را مستقیم بدهیم، تغییرِ فراخوان جدولِ همهٔ درخواست‌هایِ بعدی را
	// آلوده می‌کند.
	src := computable[phase]
	comp := make(map[string]bool, len(src))
	for k, v := range src {
		comp[k] = v
	}
	not := []string{}
	why := map[string]string{}
	for _, k := range compOrder {
		if !comp[k] {
			not = append(not, k)
			why[k] = whyNot[k]
		}
	}
	var sessionDay *int64
	if act != nil {
		d := int64(act.Year())*10000 + int64(act.Month())*100 + int64(act.Day())
		sessionDay = &d
	}
	var ah *int64
	if activityHEven != nil && *activityHEven != 0 {
		v := *activityHEven
		ah = &v
	}
	return Phase{
		Phase: phase, Label: labels[phase], PhaseSource: source,
		Official:      officialSeen && source == "tsetmc_marketState",
		OfficialState: st, OfficialStateTitle: title,
		SessionDay: sessionDay, ActivityHEven: ah,
		IsLive:         phase == Continuous,
		VerdictAllowed: phase == Continuous || phase == Closed || phase == Holiday,
		Computable:     comp, NotComputable: not, WhyNot: why,
		DataUpdatedAt: updatedAt, ClockNow: now.Format("2006-01-02 15:04:05"),
		SessionStart: "09:00", SessionEnd: "12:30",
	}
}

// FromDB همان from_db: تازه‌ترین ردیفِ market_index (نویسنده: سینکِ TSETMC).
// پایگاهِ کهنه — نبودِ جدول/ستون — بی‌وضعیتِ رسمی می‌شود، نه خطا.
func FromDB(db *sql.DB, now time.Time) Phase {
	var d, ah sql.NullInt64
	var updated, ms, mst sql.NullString
	err := db.QueryRow(`SELECT d_even, updated_at, market_state, market_state_title,
	    activity_h_even FROM market_index ORDER BY d_even DESC LIMIT 1`).
		Scan(&d, &updated, &ms, &mst, &ah)
	var board sql.NullInt64
	_ = db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&board)
	var boardPtr *int64
	if board.Valid {
		v := board.Int64
		boardPtr = &v
	}
	if err != nil {
		return Resolve(nil, nil, nil, nil, nil, boardPtr, now)
	}
	var dPtr, ahPtr *int64
	if d.Valid {
		v := d.Int64
		dPtr = &v
	}
	if ah.Valid {
		v := ah.Int64
		ahPtr = &v
	}
	var uPtr, msPtr, mstPtr *string
	if updated.Valid {
		v := updated.String
		uPtr = &v
	}
	if ms.Valid {
		v := ms.String
		msPtr = &v
	}
	if mst.Valid {
		v := mst.String
		mstPtr = &v
	}
	return Resolve(msPtr, mstPtr, dPtr, ahPtr, uPtr, boardPtr, now)
}
