package period

import (
	"encoding/json"
	"os"
	"regexp"
	"testing"
	"unicode"
)

type golden struct {
	Canonicalize []struct {
		In  any     `json:"in"`
		Out *string `json:"out"`
	} `json:"canonicalize"`
	FromTitle []struct {
		In  string  `json:"in"`
		Out *string `json:"out"`
	} `json:"from_title"`
	MonthsFromTitle []struct {
		In  string `json:"in"`
		Out *int   `json:"out"`
	} `json:"months_from_title"`
	Derive []struct {
		End   any   `json:"end"`
		Title any   `json:"title"`
		Out   []any `json:"out"`
	} `json:"derive"`
	EffectiveMonths []struct {
		End    any    `json:"end"`
		Months any    `json:"months"`
		Title  string `json:"title"`
		Out    []any  `json:"out"`
	} `json:"effective_months"`
	IsCanonical []struct {
		In  any  `json:"in"`
		Out bool `json:"out"`
	} `json:"is_canonical"`
	IsUndated []struct {
		In  any  `json:"in"`
		Out bool `json:"out"`
	} `json:"is_undated"`
	YM []struct {
		In  any   `json:"in"`
		Out []any `json:"out"`
	} `json:"ym"`
	FiscalYear []struct {
		In  any     `json:"in"`
		Out *string `json:"out"`
	} `json:"fiscal_year"`
	DescSortKey []struct {
		In  any    `json:"in"`
		Out string `json:"out"`
	} `json:"desc_sort_key"`
	Latest []struct {
		In  []any   `json:"in"`
		Out *string `json:"out"`
	} `json:"latest"`
}

func load(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func eqStr(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func eqInt(a, b *int) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func TestGolden(t *testing.T) {
	g := load(t)
	for _, c := range g.Canonicalize {
		if got := Canonicalize(c.In); !eqStr(got, c.Out) {
			t.Errorf("Canonicalize(%v) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.FromTitle {
		if got := FromTitle(c.In); !eqStr(got, c.Out) {
			t.Errorf("FromTitle(%q) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.MonthsFromTitle {
		if got := MonthsFromTitle(c.In); !eqInt(got, c.Out) {
			t.Errorf("MonthsFromTitle(%q) = %v, want %v", c.In, derefInt(got), derefInt(c.Out))
		}
	}
	for _, c := range g.Derive {
		p, src := Derive(c.End, c.Title)
		wantP, _ := c.Out[0].(string)
		wantS, _ := c.Out[1].(string)
		if !eqStr(p, strOrNil(wantP)) || src != wantS {
			t.Errorf("Derive(%v,%v) = %v,%q want %v,%q", c.End, c.Title, deref(p), src, wantP, wantS)
		}
	}
	for _, c := range g.EffectiveMonths {
		n, src := EffectiveMonths(c.End, c.Months, c.Title)
		wantN := -1
		if c.Out[0] != nil {
			wantN = int(c.Out[0].(float64))
		}
		wantS, _ := c.Out[1].(string)
		if (n == nil) != (wantN == -1) || (n != nil && *n != wantN) || src != wantS {
			t.Errorf("EffectiveMonths(%v,%v,%q) = %v,%q want %d,%q", c.End, c.Months, c.Title, derefInt(n), src, wantN, wantS)
		}
	}
	for _, c := range g.IsCanonical {
		if got := IsCanonical(c.In); got != c.Out {
			t.Errorf("IsCanonical(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.IsUndated {
		if got := IsUndated(c.In); got != c.Out {
			t.Errorf("IsUndated(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.YM {
		y, m, ok := YM(c.In)
		wantY, wantM := -1, -1
		if c.Out[0] != nil {
			wantY = int(c.Out[0].(float64))
		}
		if c.Out[1] != nil {
			wantM = int(c.Out[1].(float64))
		}
		if ok != (wantY != -1) || (ok && (y != wantY || m != wantM)) {
			t.Errorf("YM(%v) = %d,%d,%v want %d,%d", c.In, y, m, ok, wantY, wantM)
		}
	}
	for _, c := range g.FiscalYear {
		if got := FiscalYear(c.In); !eqStr(got, c.Out) {
			t.Errorf("FiscalYear(%v) = %v", c.In, deref(got))
		}
	}
	for _, c := range g.DescSortKey {
		if got := DescSortKey(c.In); got != c.Out {
			t.Errorf("DescSortKey(%v) = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Latest {
		if got := Latest(c.In); !eqStr(got, c.Out) {
			t.Errorf("Latest(%v) = %v", c.In, deref(got))
		}
	}
}

func deref(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}

func derefInt(p *int) int {
	if p == nil {
		return -1
	}
	return *p
}

func strOrNil(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// ── گاردِ دو باگِ هم‌سنجی با پایتون ──────────────────────────────────────────
//
// TestCanonicalizeLookaround دو چیزی را که درِ سنجشِ مستقلِ پایتون/Go واگرا بود
// با ورودی/خروجیِ صریح می‌آزماید (بی‌وابستگی به فایلِ طلایی، تا پیامِ خطا خودِ
// باگ را بگوید):
//
//	۱) re.searchِ پایتون نویسه‌به‌نویسه جلو می‌رود، پس تاریخِ شروع‌شده وسطِ
//	   دامانۀ یکِ تطبیقِ ردشده را هم می‌بیند؛ FindAllِ غیرهم‌پوشانِ Go نمی‌دید.
//	۲) \dِ پایتون رویِ str هر رقمِ اعشاریِ یونیکد است، نه [0-9] — و درِ هر دو
//	   جهت: هم تاریخی که Go نمی‌دید، هم رقمِ افزوده‌ای که باید تاریخ را بی‌دوره
//	   کند (جهتِ دوم خطرناک‌تر بود).
//
// رقم‌ها با \u نوشته شده‌اند تا نمایشِ ترمینال رقم و جداکننده را نجَدَبد.
func TestCanonicalizeLookaround(t *testing.T) {
	const dvYear, dvMonth, dvDay = "१४०५", "०६", "३१"
	const dvBadMonth, dvBadDay = "१३", "४५"
	const fwYear = "１４０５"
	cases := []struct {
		name string
		in   string
		want string
	}{
		{"overlap-inside-rejected", "1405/02/3012/06/03", "3012/06/03"},
		{"overlap-after-letter", "x1405/02/3012/06/03", "3012/06/03"},
		{"first-passing-match-decides", "1405/02/3012/13/03", ""},
		{"trailing-fullwidth-digit", "1405/06/31０", ""},
		{"devanagari-date", dvYear + "/" + dvMonth + "/" + dvDay, dvYear + "/06/31"},
		{"devanagari-month-only", "1405/" + dvMonth + "/31", "1405/06/31"},
		{"devanagari-bad-month", dvYear + "/" + dvBadMonth + "/" + dvBadDay, ""},
		{"unicode-digit-before", "१" + "1405/06/31", ""},
		{"fullwidth-date", fwYear + "/０６/３１", fwYear + "/06/31"},
	}
	for _, c := range cases {
		if got := Canonicalize(c.in); !eqStr(got, strOrNil(c.want)) {
			t.Errorf("%s: Canonicalize(%q) = %q, want %q", c.name, c.in, deref(got), c.want)
		}
	}
}

// TestUnicodeYearStaysRaw سالِ canonical عینِ نویسه‌هایِ تطبیق‌شده می‌ماند (پایتون
// f"{y}/…" را با گروهِ خام می‌سازد)، پس canonical نیست ولی ym/fiscal_year باید
// مثلِ پایتون کار کنند: int() رویِ هر رقمِ Nd، و pe[:4] یعنی چهار *نویسه*.
func TestUnicodeYearStaysRaw(t *testing.T) {
	const dvYear = "१४०५"
	in := dvYear + "/०६/३१"
	pe := Canonicalize(in)
	if want := dvYear + "/06/31"; pe == nil || *pe != want {
		t.Fatalf("Canonicalize(%q) = %q, want %q", in, deref(pe), want)
	}
	if IsCanonical(*pe) {
		t.Errorf("IsCanonical(%q) = true، ولی CANON_REِ پایتون با [0-9] است", *pe)
	}
	if y, m, ok := YM(in); !ok || y != 1405 || m != 6 {
		t.Errorf("YM(%q) = %d,%d,%v, want 1405,6,true", in, y, m, ok)
	}
	if fy := FiscalYear(in); fy == nil || *fy != dvYear {
		t.Errorf("FiscalYear(%q) = %q, want %q (چهار نویسه، نه چهار بایت)", in, deref(fy), dvYear)
	}
}

// TestPyDigitClass طبقۀ رقمِ regex و isPyDigit باید یکِ جواب بدهند و هر دو همان
// \dِ پایتون باشند: ردۀ Nd (ارقامِ ASCII، فارسی، عربی، وِیانگاری، تمام‌عرض و
// بلوک‌هایِ افزودۀ یونیکدِ ۱۶)، ولی نه No/Nl مثلِ ² و ½ و Ⅰ.
func TestPyDigitClass(t *testing.T) {
	class := regexp.MustCompile(pyDigits)
	seen := 0
	for r := rune(0); r <= 0x10FFFF; r++ {
		// هر «شمارنده» (Nd + No + Nl) کاندیدِ \d است؛ بی‌این که کلِ فضایِ نویسه را
		// با regex بکاويم، سمتِ منفیِ آزمون هم پوشش داده می‌شود.
		if !unicode.IsNumber(r) {
			continue
		}
		seen++
		if got, want := isPyDigit(r), class.MatchString(string(r)); got != want {
			t.Fatalf("isPyDigit(%#X) = %v، ولی طبقۀ regex %v", r, got, want)
		}
	}
	if seen < 700 {
		t.Fatalf("فقط %d شمارنده دیدیم؛ پایشِ طبقه بی‌محتوا شده است", seen)
	}
	for _, r := range []rune{'0', '9', 0x0669, 0x06F0, 0x0966, 0xFF10, 0x10D40, 0x116E3, 0x1E5FA} {
		if !isPyDigit(r) {
			t.Errorf("%#X باید رقمِ Nd باشد (\\dِ پایتون می‌پذیرد)", r)
		}
	}
	for _, r := range []rune{0x00B2, 0x00B3, 0x00BD, 0x2160, 0x2460, 0x1D7BF} {
		if isPyDigit(r) {
			t.Errorf("%#X رقمِ اعشاری (Nd) نیست، پس \\d هم نمی‌پذیردش", r)
		}
	}
}

// TestPyDigitValueDecades قاعدۀ pyDigitValue (عقب‌رفتن تا آغازِ بلوک و moduloِ
// ده) تنها وقتی با int()ِ پایتون یکی است که هر بلوکِ Nd از صفر آغاز شود و
// ده‌تاییِ پیوسته باشد (بلوک‌هایِ بلندتر از ده، چندِ ده‌تاییِ پشت‌هم‌اند). همین
// ساختار اینجا سنجیده می‌شود تا بلوکِ بی‌تراز قرمز شود، نه این‌که بی‌صدا تاریخِ
// غلط بسازد.
func TestPyDigitValueDecades(t *testing.T) {
	for r := rune(0); r <= 0x10FFFF; r++ {
		if !isPyDigit(r) {
			continue
		}
		v := pyDigitValue(r)
		if v < 0 || v > 9 {
			t.Fatalf("pyDigitValue(%#X) = %d", r, v)
		}
		if isPyDigit(r - 1) {
			if prev := pyDigitValue(r - 1); v != (prev+1)%10 {
				t.Errorf("%#X: ارزشِ رقمِ پیوسته باید (%d+1)%%10 باشد، شد %d", r, prev, v)
			}
		} else if v != 0 {
			t.Errorf("%#X آغازِ بلوکِ رقم است ولی ارزشش %d است، نه صفر", r, v)
		}
	}
}
