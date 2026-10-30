package marketphase

import (
	"testing"
	"time"
)

func ip(v int64) *int64   { return &v }
func sp(v string) *string { return &v }

func at(h, m int) time.Time {
	return time.Date(2026, 10, 28, h, m, 0, 0, time.Local)
}

// now چهارشنبه ۲۰۲۶-۱۰-۲۸ است؛ ساعتِ دیواری در تست تزریق می‌شود.
var now = at(10, 30)

func eqI64(a, b *int64) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func eqStr(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func showI64(p *int64) any {
	if p == nil {
		return nil
	}
	return *p
}

func showStr(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}

// TestResolveBranches هر پنج مرحله و مرزهایِ ساعتی/تقویمی/رسمی را می‌سنجد.
// این جدول هم‌زمان ترتیبِ اولویت را قفل می‌کند: «باز»ِ رسمی بر تعطیلی مقدم است،
// وضعیتِ ناشناخته به «باز» ترجمه نمی‌شود، و نبودِ وضعیت فقط از تقویم می‌گوید.
func TestResolveBranches(t *testing.T) {
	cases := []struct {
		name           string
		state, title   *string
		act, ah, board *int64
		updated        *string
		at             time.Time
		want, source   string
		label          string
		official, live bool
		verdict        bool
		session        *int64
		officialState  *string
		officialTitle  *string
	}{
		{
			name: "closed past day", state: sp("F"), title: sp("بسته"),
			act: ip(20261014), ah: ip(123000), updated: sp("2026-10-14 12:30:00"), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "holiday friday", state: sp("F"), title: sp("بسته"),
			act: ip(20261016), ah: ip(123000), at: now,
			want: Holiday, source: "tsetmc_marketState", label: "تعطیلِ رسمی",
			official: true, verdict: true, session: ip(20261016),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "no official", act: ip(20261014), at: now,
			want: Unknown, source: "none", label: "مرحل نامشخص",
			session: ip(20261014),
		},
		{
			name: "today before open", state: sp("F"), title: sp("بسته"),
			act: ip(20261028), at: at(8, 30),
			want: PreOpen, source: "tsetmc_marketState", label: "پیش از آغازِ معاملات",
			official: true, session: ip(20261028),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			// 09:00:00 دیگر «پیش از آغاز» نیست؛ Python هم همین مرز را دارد.
			name: "today at session start", state: sp("F"), title: sp("بسته"),
			act: ip(20261028), at: at(9, 0),
			want: Unknown, source: "tsetmc_marketState", label: "مرحل نامشخص",
			official: true, session: ip(20261028),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "today mid-session closed state", state: sp("F"), title: sp("بسته"),
			act: ip(20261028), at: now,
			want: Unknown, source: "tsetmc_marketState", label: "مرحل نامشخص",
			official: true, session: ip(20261028),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			// 12:30:00 مرزِ پایان است: بستهٔ رسمی از این لحظه «پایانِ نشست».
			name: "today at session end", state: sp("F"), title: sp("بسته"),
			act: ip(20261028), at: at(12, 30),
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261028),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "today after session end", state: sp("F"), title: sp("بسته"),
			act: ip(20261028), at: at(13, 0),
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261028),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "official open by title", title: sp("باز"), act: ip(20261028), at: now,
			want: Continuous, source: "tsetmc_marketState", label: "معاملات جاری",
			official: true, live: true, verdict: true, session: ip(20261028),
			officialTitle: sp("باز"),
		},
		{
			// اولویت: «باز»ِ رسمی بر تعطیلیِ تقویمی مقدم است (جمعه).
			name: "official open beats holiday", title: sp("باز"), act: ip(20261016), at: now,
			want: Continuous, source: "tsetmc_marketState", label: "معاملات جاری",
			official: true, live: true, verdict: true, session: ip(20261016),
			officialTitle: sp("باز"),
		},
		{
			// نگاشتِ عنوان به‌تنهایی هم رسمی است (بدونِ state).
			name: "closed by title only", title: sp("بسته"), act: ip(20261014), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialTitle: sp("بسته"),
		},
		{
			name: "unmapped state", state: sp("Z"), title: sp("چیز"),
			act: ip(20261014), at: now,
			want: Unknown, source: "tsetmc_marketState_unmapped", label: "مرحل نامشخص",
			session:       ip(20261014),
			officialState: sp("Z"), officialTitle: sp("چیز"),
		},
		{
			// stateِ ناشناخته با عنوانِ «بسته»: عنوان نگاشت را نجات می‌دهد.
			name: "closed title with unmapped state", state: sp("Z"), title: sp("بسته"),
			act: ip(20261014), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialState: sp("Z"), officialTitle: sp("بسته"),
		},
		{
			name: "calendar closed same day", act: ip(20261028), at: at(13, 0),
			want: Closed, source: "calendar", label: "پایانِ نشست",
			verdict: true, session: ip(20261028),
		},
		{
			name: "calendar pre open same day", act: ip(20261028), at: at(8, 30),
			want: PreOpen, source: "calendar", label: "پیش از آغازِ معاملات",
			session: ip(20261028),
		},
		{
			name: "calendar holiday", act: ip(20261016), at: now,
			want: Holiday, source: "calendar", label: "تعطیلِ رسمی",
			verdict: true, session: ip(20261016),
		},
		{
			name: "calendar unknown mid-session", act: ip(20261028), at: now,
			want: Unknown, source: "none", label: "مرحل نامشخص",
			session: ip(20261028),
		},
		{
			// stripِ رسمی: stateِ « f » با فاصله به F می‌رسد و عنوانِ فقط-فاصله nil است.
			name: "trims state and blank title", state: sp(" f "), title: sp("\x1f"),
			act: ip(20261014), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialState: sp("F"),
		},
		{
			// نبودِ activity_day: board_day جای آن را می‌گیرد (همان قاعدهٔ پایتون).
			name: "board day fallback", board: ip(20261028), at: at(13, 0),
			want: Closed, source: "calendar", label: "پایانِ نشست",
			verdict: true, session: ip(20261028),
		},
		{
			name: "no activity and no board day", at: at(13, 0),
			want: Unknown, source: "none", label: "مرحل نامشخص",
		},
		{
			// فعالیتِ نامعتبر (۳۰ فوریه) رد می‌شود و board_day سالم می‌ماند.
			name: "invalid activity day falls to board", act: ip(20260230),
			board: ip(20261028), at: at(8, 30),
			want: PreOpen, source: "calendar", label: "پیش از آغازِ معاملات",
			session: ip(20261028),
		},
		{
			// activity_day بر board_day مقدم است، حتی اگر روزِ گذشته باشد.
			name: "activity day wins over board", act: ip(20261014),
			board: ip(20261028), at: at(13, 0),
			want: Unknown, source: "none", label: "مرحل نامشخص",
			session: ip(20261014),
		},
		{
			// activity_h_evenِ صفر «نبود» است، نه عددِ صفر.
			name: "zero activity hour is nil", state: sp("F"), title: sp("بسته"),
			act: ip(20261014), ah: ip(0), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialState: sp("F"), officialTitle: sp("بسته"),
		},
		{
			name: "state only closed", state: sp("F"), act: ip(20261014), at: now,
			want: Closed, source: "tsetmc_marketState", label: "پایانِ نشست",
			official: true, verdict: true, session: ip(20261014),
			officialState: sp("F"),
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := Resolve(c.state, c.title, c.act, c.ah, c.updated, c.board, c.at)
			if got.Phase != c.want || got.PhaseSource != c.source || got.Label != c.label {
				t.Fatalf("phase/source/label = %s/%s/%s, want %s/%s/%s",
					got.Phase, got.PhaseSource, got.Label, c.want, c.source, c.label)
			}
			if got.Official != c.official || got.IsLive != c.live ||
				got.VerdictAllowed != c.verdict {
				t.Fatalf("official/live/verdict = %v/%v/%v, want %v/%v/%v",
					got.Official, got.IsLive, got.VerdictAllowed,
					c.official, c.live, c.verdict)
			}
			if !eqI64(got.SessionDay, c.session) {
				t.Fatalf("session_day = %v, want %v", showI64(got.SessionDay),
					showI64(c.session))
			}
			if !eqStr(got.OfficialState, c.officialState) ||
				!eqStr(got.OfficialStateTitle, c.officialTitle) {
				t.Fatalf("official_state/title = %v/%v, want %v/%v",
					showStr(got.OfficialState), showStr(got.OfficialStateTitle),
					showStr(c.officialState), showStr(c.officialTitle))
			}
			if c.name == "closed past day" && !eqStr(got.DataUpdatedAt, c.updated) {
				t.Fatalf("data_updated_at = %v, want %v",
					showStr(got.DataUpdatedAt), showStr(c.updated))
			}
			if c.name == "closed past day" && !eqI64(got.ActivityHEven, c.ah) {
				t.Fatalf("activity_h_even = %v, want %v",
					showI64(got.ActivityHEven), showI64(c.ah))
			}
			if c.name == "zero activity hour is nil" && got.ActivityHEven != nil {
				t.Fatalf("activity_h_even = %v, want nil", showI64(got.ActivityHEven))
			}
			if got.ClockNow != c.at.Format("2006-01-02 15:04:05") {
				t.Fatalf("clock_now = %s, want %s", got.ClockNow,
					c.at.Format("2006-01-02 15:04:05"))
			}
			if got.SessionStart != "09:00" || got.SessionEnd != "12:30" {
				t.Fatalf("session window = %s..%s, want 09:00..12:30",
					got.SessionStart, got.SessionEnd)
			}
		})
	}
}

// TestResolveNotComputableOrder ترتیب و متنِ why_not را برایِ هر پنج مرحله قفل
// می‌کند. ترتیب از dictِ پایتون می‌آید (realized_flow، order_pressure،
// session_vs_threshold، close_price_final)، نه از ترتیبِ الفبایی یا طول.
func TestResolveNotComputableOrder(t *testing.T) {
	why := map[string]string{
		"realized_flow":        "هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست",
		"order_pressure":       "دفترِ سفارشِ همین نشست در دسترس نیست",
		"session_vs_threshold": "جمعِ نشست کامل نشده، پس با آستانۀِ تمام‌روز سنجیده نمی‌شود",
		"close_price_final":    "قیمت پایانیِ نهایی هنوز ساخته نشده",
	}
	cases := []struct {
		name      string
		state     *string
		title     *string
		act       *int64
		at        time.Time
		wantPhase string
		want      []string
	}{
		{"pre_open", sp("F"), sp("بسته"), ip(20261028), at(8, 30), PreOpen,
			[]string{"realized_flow", "session_vs_threshold", "close_price_final"}},
		{"continuous", nil, sp("باز"), ip(20261028), now, Continuous,
			[]string{"close_price_final"}},
		{"closed", sp("F"), sp("بسته"), ip(20261014), now, Closed,
			[]string{"order_pressure"}},
		{"holiday", sp("F"), sp("بسته"), ip(20261016), now, Holiday,
			[]string{"order_pressure"}},
		{"unknown mid-session", sp("F"), sp("بسته"), ip(20261028), now, Unknown,
			[]string{"realized_flow", "order_pressure", "session_vs_threshold", "close_price_final"}},
		{"unknown no official", nil, nil, ip(20261014), now, Unknown,
			[]string{"realized_flow", "order_pressure", "session_vs_threshold", "close_price_final"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := Resolve(c.state, c.title, c.act, ip(100000), nil, nil, c.at)
			if got.Phase != c.wantPhase {
				t.Fatalf("phase = %s, want %s", got.Phase, c.wantPhase)
			}
			if len(got.NotComputable) != len(c.want) {
				t.Fatalf("not_computable = %v, want %v", got.NotComputable, c.want)
			}
			for i := range c.want {
				if got.NotComputable[i] != c.want[i] {
					t.Fatalf("not_computable[%d] = %s, want %s", i,
						got.NotComputable[i], c.want[i])
				}
				if got.WhyNot[c.want[i]] != why[c.want[i]] {
					t.Errorf("why_not[%s] = %q, want %q", c.want[i],
						got.WhyNot[c.want[i]], why[c.want[i]])
				}
			}
			if len(got.WhyNot) != len(c.want) {
				t.Fatalf("why_not has %d keys, want %d (only not_computable)",
					len(got.WhyNot), len(c.want))
			}
		})
	}
}

// TestResolveComputableIsCallerOwned: نقشهٔ computableِ هر نتیجه ملکِ همان
// فراخوان است. پایتون dict(comp) می‌سازد؛ تغییرِ نتیجه نباید بستهٔ مرحله‌ها را
// برای درخواستِ بعدی عوض کند.
func TestResolveComputableIsCallerOwned(t *testing.T) {
	first := Resolve(nil, nil, ip(20261028), nil, nil, nil, at(8, 30))
	if first.Phase != PreOpen || first.Computable["realized_flow"] != false {
		t.Fatalf("probe = %s/%v, want pre_open with realized_flow:false",
			first.Phase, first.Computable["realized_flow"])
	}
	first.Computable["realized_flow"] = true
	first.Computable["injected"] = true

	second := Resolve(nil, nil, ip(20261028), nil, nil, nil, at(8, 30))
	if second.Computable["realized_flow"] != false {
		t.Fatal("second resolve inherited the caller's mutation of a previous result")
	}
	if _, ok := second.Computable["injected"]; ok {
		t.Fatal("second resolve inherited an injected key from a previous result")
	}
	if len(second.Computable) != 4 {
		t.Fatalf("computable has %d keys, want the 4-key template: %v",
			len(second.Computable), second.Computable)
	}
}

// TestDateFromDEven سخت‌گیریِ datetime.date را قفل می‌کند: تاریخِ غلت‌خورده
// (۳۰ فوریه، ماهِ ۱۳) پذیرفته نمی‌شود و به مرحلهٔ تقویمیِ ساختگی نمی‌رسد.
func TestDateFromDEven(t *testing.T) {
	cases := []struct {
		in   int64
		ok   bool
		want string
	}{
		{20261014, true, "2026-10-14"},
		{20240229, true, "2024-02-29"},
		{20260229, false, ""},
		{20260230, false, ""},
		{20261301, false, ""},
		{20261000, false, ""},
		{20261232, false, ""},
		{100000101, false, ""},
		{0, false, ""},
		{-1, false, ""},
		{99991231, true, "9999-12-31"},
	}
	for _, c := range cases {
		got, ok := dateFromDEven(c.in)
		if ok != c.ok {
			t.Errorf("dateFromDEven(%d) ok = %v, want %v", c.in, ok, c.ok)
			continue
		}
		if ok && got.Format("2006-01-02") != c.want {
			t.Errorf("dateFromDEven(%d) = %s, want %s", c.in,
				got.Format("2006-01-02"), c.want)
		}
	}
}
