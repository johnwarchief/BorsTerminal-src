package fundamental

// آزمونِ «تعریفِ یکتای float()» درِ لایۀ صورت‌های مالی — پیش‌تر این لایه
// `strconv.ParseFloat`ِ خودش را داشت و متنِ «۱۲۵» (رقمِ فارسی) را رد می‌کرد؛
// پایتون `float("۱۲۵")` را ۱۲۵ می‌گیرد، پس آن ردیف از نردبانِ EPS می‌افتاد و
// رتبه‌بندیِ ردیفِ مرجع (کامل‌بودن) هم عددِ دیگری را برمی‌گزید. این آزمون دو
// شاخه را می‌سنجد: تبدیلِ واحد، و بدنهٔ واقعی روی کپیِ موقتِ فیکسچر.
//
// قیدِ سختِ پروژه رعایت شده: فایلِ کامیت‌شدهٔ فیکسچر هرگز باز نمی‌شود؛ همه‌چیز
// درِ پوشۀ موقت است (همان الگویِ golden_test.go، با دسترسیِ نوشتن برایِ
// ساختنِ ردیفِ آزمایشی).

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
)

// stmtfloatFixtureRW کپیِ فیکسچر درِ پوشۀ موقت و باز کردنِ رونویسی (نوشتن فقط
// درِ کپی است، نه درِ فایلِ کامیت‌شده).
func stmtfloatFixtureRW(t *testing.T) *Service {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "market.db"), raw, 0o644); err != nil {
		t.Fatal(err)
	}
	h, err := db.OpenWritableForTest(dir)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	return New(h.Market)
}

// stmtfloatSymbol نامِ نماد را از خودِ فیکسچر می‌خواند (تا متنِ فارسی دستی
// نشود) — ردیفِ سالِ ۱۴۰۴ که EPSِ آن متنی می‌شود.
func stmtfloatSymbol(t *testing.T, s *Service, ctx context.Context) string {
	t.Helper()
	raw, err := s.rows(ctx, "SELECT symbol FROM financial_statements WHERE tracing_no = 5005", nil)
	if err != nil {
		t.Fatalf("read symbol: %v", err)
	}
	if len(raw) == 0 {
		t.Fatal("فیکسچر ردیفِ tracing_no=5005 ندارد — آزمون بی‌معنا می‌شود")
	}
	sym := strOr(raw[0]["symbol"])
	if sym == "" {
		t.Fatal("نمادِ خالی")
	}
	return sym
}

// TestStmtFloatUnicodeDigits تعریفِ یکتای `float()` را می‌سنجد: رقمِ یونیکد
// (پایتون: float("۱۲۵") ⇒ ۱۲۵) و زیرخط (float("1_000") ⇒ ۱۰۰۰) پذیرفته
// می‌شوند، و کنترلِ منفی روشن است: رشتهٔ بی‌محتوا ⇒ None (نه صفرِ جعلی).
// رقم‌ها با faDigits از ASCII ساخته می‌شوند، نه دستی.
func TestStmtFloatUnicodeDigits(t *testing.T) {
	fa125 := faDigits("125")
	for _, c := range []struct {
		in   any
		want float64
		nil_ bool
	}{
		{in: fa125, want: 125},
		{in: "1_000", want: 1000},
		{in: "12.5", want: 12.5},
		{in: "abc", nil_: true},
		{in: "", nil_: true},
		{in: nil, nil_: true},
		{in: 0.0, want: 0},
	} {
		got := stmtFloatOrNull(c.in)
		if c.nil_ {
			if got != nil {
				t.Errorf("stmtFloatOrNull(%#v) = %#v, want nil", c.in, got)
			}
			continue
		}
		f, ok := got.(float64)
		if !ok {
			t.Errorf("stmtFloatOrNull(%#v) = %#v, want float64", c.in, got)
			continue
		}
		if f != c.want {
			t.Errorf("stmtFloatOrNull(%#v) = %v, want %v", c.in, f, c.want)
		}
	}
}

// TestStmtFloatUnicodeDigitsInStatementRow بدنهٔ واقعی را می‌سنجد: ردیفِ
// `financial_statements` که `basic_eps` آن متنِ «۱۲۵» است باید ۱۲۵ بدهد، از
// نردبانِ EPS نیفتد (پیش‌تر nil می‌شد و آن سال از سابقه بیرون می‌رفت)، و
// رشتهٔ بی‌محتوا مثلِ پایتون (`ValueError` ⇒ ردیف بی‌محتوا) هم به nil برسد.
func TestStmtFloatUnicodeDigitsInStatementRow(t *testing.T) {
	ctx := context.Background()
	s := stmtfloatFixtureRW(t)
	// resolverِ نماد یک اتصالِ جدا نگه می‌دارد؛ بدونِ بستنش، ویندوز فایلِ
	// کپی را قفل نگه می‌دارد و پاک‌سازیِ پوشۀ موقت شکست می‌خورد.
	defer s.Close()
	sym := stmtfloatSymbol(t, s, ctx)
	epsText := faDigits("125")

	if _, err := s.market.ExecContext(ctx,
		"UPDATE financial_statements SET basic_eps = ? WHERE tracing_no = 5005", epsText); err != nil {
		t.Fatalf("update basic_eps: %v", err)
	}
	// مقدار باید واقعاً TEXT مانده باشد تا شاخهٔ متنِ `float()` سنجیده شود.
	rawType, err := s.rows(ctx, "SELECT typeof(basic_eps) AS t FROM financial_statements"+
		" WHERE tracing_no = 5005", nil)
	if err != nil {
		t.Fatalf("read typeof: %v", err)
	}
	if len(rawType) == 0 || strOr(rawType[0]["t"]) != "text" {
		t.Fatalf("basic_eps باید TEXT بماند، ولی شد: %v", rawType)
	}

	// ۱) صورتِ مالی: EPS باید ۱۲۵ باشد، نه nil.
	rows, err := s.AnnualStatements(ctx, sym, false, false, 10)
	if err != nil {
		t.Fatalf("annual_statements: %v", err)
	}
	eps := stmtfloatEPSOf(rows, "1404")
	if eps == nil {
		t.Fatalf("EPSِ سالِ ۱۴۰۴ = nil — ردیف بی‌مقدار افتاد")
	}
	if f, ok := eps.(float64); !ok || f != 125 {
		t.Errorf("EPSِ سالِ ۱۴۰۴ = %#v, want 125", eps)
	}

	// ۲) نردبانِ EPS: سه سال باید کامل بماند (ردیف حذف نشود).
	ladder, err := s.EpsLadder(ctx, sym, 3)
	if err != nil {
		t.Fatalf("eps_ladder: %v", err)
	}
	if got, _ := ladder["years_available"].(int); got != 3 {
		t.Errorf("years_available = %#v, want 3 (ردیفِ EPSِ متنی افتاد)", ladder["years_available"])
	}
	if !stmtfloatHasFloat(ladder["eps_series"], 125) {
		t.Errorf("eps_series = %#v — ۱۲۵ درِ سری نیست", ladder["eps_series"])
	}

	// ۳) کنترلِ منفی: متنِ بی‌محتوا باید مثلِ پایتون (ValueError) بی‌مقدار بماند
	// و آن سال از نردبان بیفتد.
	if _, err := s.market.ExecContext(ctx,
		"UPDATE financial_statements SET basic_eps = ? WHERE tracing_no = 5004", "abc"); err != nil {
		t.Fatalf("update basic_eps (control): %v", err)
	}
	rows, err = s.AnnualStatements(ctx, sym, false, false, 10)
	if err != nil {
		t.Fatalf("annual_statements (control): %v", err)
	}
	if eps := stmtfloatEPSOf(rows, "1403"); eps != nil {
		t.Errorf("EPSِ سالِ ۱۴۰۳ = %#v, want nil (متنِ بی‌محتوا)", eps)
	}
	ladder, err = s.EpsLadder(ctx, sym, 3)
	if err != nil {
		t.Fatalf("eps_ladder (control): %v", err)
	}
	// سالِ بی‌مقدار باید از نردبان بیفتد (پایتون: ValueError ⇒ `continue`)، پس
	// سابقه دیگر پیوسته و کامل نیست.
	if got, _ := ladder["years_available"].(int); got != 2 {
		t.Errorf("years_available (control) = %#v, want 2 (ردیفِ بی‌محتوا نباید بماند)",
			ladder["years_available"])
	}
	if gap, _ := ladder["data_gap"].(bool); !gap {
		t.Errorf("data_gap (control) = %#v, want true", ladder["data_gap"])
	}
}

// stmtfloatEPSOf مقدارِ `basic_eps` را از فهرستِ صورت‌های مالی برای یک سالِ
// مالی برمی‌دارد (nil یعنی آن سال اصلاً در فهرست نیست).
func stmtfloatEPSOf(rows []map[string]any, fiscalYear string) any {
	for _, r := range rows {
		if strOr(r["fiscal_year"]) == fiscalYear {
			return r["basic_eps"]
		}
	}
	return nil
}

// stmtfloatHasFloat آیا این مقدارِ عددی در فهرست هست؟
func stmtfloatHasFloat(v any, want float64) bool {
	list, ok := v.([]any)
	if !ok {
		return false
	}
	for _, item := range list {
		if f, ok := item.(float64); ok && f == want {
			return true
		}
	}
	return false
}
