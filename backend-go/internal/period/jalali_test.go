package period

import "testing"

// مقادیرِ طلایی از اجرایِ مستقیمِ codal_periods روی همان ورودی‌ها گرفته شده‌اند.
func TestJ2GDateGolden(t *testing.T) {
	cases := []struct {
		in   string
		want *string
	}{
		{"1405/06/31", strPtr("2026-09-22")},
		{"1405/06/31 09:00:00", strPtr("2026-09-22 09:00:00")},
		{"1404/12/29", strPtr("2026-03-20")},
		{"1403/12/30 23:59:59", strPtr("2025-03-20 23:59:59")},
		{"۱۴۰۵/۰۶/۳۱ ۰۹:۰۰:۰۰", strPtr("2026-09-22 09:00:00")},
		{"1405/07/31", nil},
		{"2026-11-03", nil},
		{"", nil},
	}
	for _, c := range cases {
		got := J2GDate(c.in)
		if (got == nil) != (c.want == nil) || (got != nil && *got != *c.want) {
			t.Errorf("J2GDate(%q)=%v want %v", c.in, derefAny(got), derefAny(c.want))
		}
	}
}

func TestPubKeyGolden(t *testing.T) {
	cases := []struct {
		in   string
		want *string
	}{
		{"۱۴۰۵/۰۶/۱۳ ۲۳:۵۳:۵۷", strPtr("1405/06/13 23:53:57")},
		{"1405-06-01", strPtr("1405/06/01")},
		{"1405/6/1 23:11", strPtr("1405/06/01 23:11:00")},
		{"bad", nil},
		{"1405/13/01", nil},
		{"1405/06/01 25:00:00", strPtr("1405/06/01")},
	}
	for _, c := range cases {
		got := PubKey(c.in)
		if (got == nil) != (c.want == nil) || (got != nil && *got != *c.want) {
			t.Errorf("PubKey(%q)=%v want %v", c.in, derefAny(got), derefAny(c.want))
		}
	}
}

func TestJalaliMonthLenGolden(t *testing.T) {
	cases := []struct {
		jy, jm, want int
	}{
		{1403, 12, 30},
		{1404, 12, 29},
		{1405, 12, 29},
		{1405, 6, 31},
	}
	for _, c := range cases {
		if got := jalaliMonthLen(c.jy, c.jm); got != c.want {
			t.Errorf("jalaliMonthLen(%d,%d)=%d want %d", c.jy, c.jm, got, c.want)
		}
	}
}

func strPtr(s string) *string { return &s }

func derefAny(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}
