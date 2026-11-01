package fundamental

// آزمونِ لایۀ صورت‌های مالی — داورِ این فایل فقط وکتور است:
// `testdata/vectors/statements.json` را اوراکلِ پایتون (`tools/parity/
// gen_fundamental_layer_vectors.py`) رویِ همان فیکسچرِ یخ‌زدۀ تسکِ ۱ نوشته و
// کامیت شده. هیچ انتظارِ دستی اینجا نوشته نشده؛ هر مقدارِ مقایسه‌شده از خودِ
// همان فایل خوانده می‌شود (نامِ نمادها هم، چون دو نماد نیم‌فاصله دارند و تایپِ
// دستی‌شان رقم/نویسه می‌دزدد).
//
// مقایسه سخت‌گیرانه است: عدد باید bit-به-bit بخورد (هیچ تلورانسِ نسبی — این ستون‌ها
// از بانک می‌آیند، نه از حساب، و `gross_margin` تنها سه عددِ محاسبه‌شده دارد که
// pyroundِ همان پایتون است)، `null` یعنی nil، ترتیبِ آرایه معنا دارد، و کلیدهای
// هر دو طرف باید یکی باشند تا فیلدِ گم‌شده («months_source» و «unit_valid») با
// «بقیه درست است» رد نشود.

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/period"
)

// stmtOpenFixture کپیِ فقط‌خواندنی از فیکسچرِ کامیت‌شده درِ پوشۀ موقت. قیدِ سختِ
// پروژه: بانکِ ریشه هیچ‌وقت با SQLite باز نمی‌شود؛ اینجا همان الگویِ golden_test.go
// (کپی ← `db.Open(dir, true)`)، بی‌دست‌زدنِ آن فایل.
func stmtOpenFixture(t *testing.T) *Service {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "market.db"), raw, 0o644); err != nil {
		t.Fatal(err)
	}
	h, err := db.Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	return New(h.Market)
}

// stmtVectors فایلِ داور را می‌خواند و ثابت می‌کند پُرشدهٔ واقعی است، نه فایلِ
// نصفه‌نیمه‌ای که آزمون را سبزِ کاذب کند.
func stmtVectors(t *testing.T) map[string]any {
	t.Helper()
	path := filepath.Join("testdata", "vectors", "statements.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read referee %s: %v", path, err)
	}
	if len(raw) == 0 {
		t.Fatalf("referee file %s is empty", path)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatalf("referee %s is not valid JSON: %v", path, err)
	}
	// حداقل‌هایِ هر گروه = همان چیزی که اورتکاژنر می‌نویسد (۵ نماد × …): ۶۵ کیس.
	// بی‌این سنجه، یکِ فایلِ بریده هم «هرچه هست را گذراند» و سبز می‌شد.
	for _, want := range []struct {
		key string
		min int
	}{
		{"annual", 15}, {"reference", 5}, {"gross", 15}, {"names", 5}, {"quarter_ref", 25},
	} {
		list, ok := doc[want.key].([]any)
		if !ok {
			t.Fatalf("referee has no %q array: %v", want.key, doc[want.key])
		}
		if len(list) < want.min {
			t.Fatalf("referee %q has %d cases, want >= %d — فایلِ وکتور truncated است",
				want.key, len(list), want.min)
		}
	}
	total := 0
	for _, v := range doc {
		if list, ok := v.([]any); ok {
			total += len(list)
		}
	}
	if total < 65 {
		t.Fatalf("referee covers %d cases, want >= 65", total)
	}
	return doc
}

// stmtCases یکِ گروه را به کیس‌هایِ map باز می‌کند و نماد/limit/… را از خودِ
// وکتور می‌خواند (نه از جدولِ دستی).
func stmtCases(t *testing.T, doc map[string]any, key string) []map[string]any {
	t.Helper()
	list, ok := doc[key].([]any)
	if !ok {
		t.Fatalf("referee group %q is not an array", key)
	}
	out := make([]map[string]any, 0, len(list))
	for i, c := range list {
		m, ok := c.(map[string]any)
		if !ok {
			t.Fatalf("%s[%d]: case is %#v, want object", key, i, c)
		}
		if _, has := m["symbol"]; !has {
			t.Fatalf("%s[%d]: case has no symbol: %v", key, i, m)
		}
		out = append(out, m)
	}
	return out
}

func stmtCaseSymbol(t *testing.T, key string, i int, c map[string]any) string {
	t.Helper()
	sym, ok := c["symbol"].(string)
	if !ok || sym == "" {
		t.Fatalf("%s[%d]: symbol = %#v", key, i, c["symbol"])
	}
	return sym
}

func stmtCaseInt(t *testing.T, key string, i int, c map[string]any, field string) int {
	t.Helper()
	f, ok := c[field].(float64)
	if !ok {
		t.Fatalf("%s[%d]: %s = %#v, want number", key, i, field, c[field])
	}
	return int(f)
}

func stmtCaseFloat(t *testing.T, key string, i int, c map[string]any, field string) float64 {
	t.Helper()
	f, ok := c[field].(float64)
	if !ok {
		t.Fatalf("%s[%d]: %s = %#v, want number", key, i, field, c[field])
	}
	return f
}

// ── مقایسه‌گرِ ساختاریافته ──────────────────────────────────────────────────

func stmtIsNilValue(v any) bool {
	switch x := v.(type) {
	case nil:
		return true
	case map[string]any:
		return len(x) == 0
	}
	return false
}

// stmtAsSlice هر فهرستِ ردیفِ Go را به []anyِ JSON می‌برد؛ nil slice هم فهرستِ
// خالی است چون اوراکل هیچ‌وقت null برنمی‌گرداند (همیشه `[]`).
func stmtAsSlice(v any) ([]any, bool) {
	switch x := v.(type) {
	case []any:
		return x, true
	case []map[string]any:
		out := make([]any, 0, len(x))
		for _, m := range x {
			out = append(out, m)
		}
		return out, true
	case nil:
		return nil, true
	}
	return nil, false
}

// stmtAsNumber فقط اعدادِ واقعی را عدد می‌شمارد: `true`ِ JSON هیچ‌وقت با ۱ِ
// Go نمی‌چسبد، چون اوراکل برایِ پرچم‌ها bool می‌نویسد و این لایه bool برمی‌گرداند.
func stmtAsNumber(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	case int32:
		return float64(x), true
	}
	return 0, false
}

// stmtAssertValue یکِ مقدارِ وکتور را با مقدارِ Go می‌سنجد. بی‌تلورانسِ عددی:
// فیکسچر و محاسبات هر دو deterministic‌اند و تلورانس فقط باگِ گردکردن را پنهان
// می‌کند. سنجشِ Go-به-Go (آزمونِ دو شاخۀ `rows`) هم از همین راه می‌رود، پس
// عددِ سمتِ want می‌تواند int64/float64ِ خودِ Go باشد، نه فقط float64ِ JSON.
func stmtAssertValue(t *testing.T, path string, want, got any) {
	t.Helper()
	if w, isNum := stmtAsNumber(want); isNum {
		g, ok := stmtAsNumber(got)
		if !ok {
			t.Errorf("%s: want number %v, got %T %v", path, w, got, got)
			return
		}
		if w != g {
			t.Errorf("%s: number want %v got %v", path, w, g)
		}
		return
	}
	switch w := want.(type) {
	case nil:
		if !stmtIsNilValue(got) {
			t.Errorf("%s: want null, got %T %v", path, got, got)
		}
	case map[string]any:
		g, ok := got.(map[string]any)
		if !ok {
			t.Errorf("%s: want object, got %T %v", path, got, got)
			return
		}
		for k, wv := range w {
			gv, exists := g[k]
			if !exists {
				t.Errorf("%s.%s: missing in Go (اوراکل مقدار می‌داد: %#v)", path, k, wv)
				continue
			}
			stmtAssertValue(t, path+"."+k, wv, gv)
		}
		for k := range g {
			if _, exists := w[k]; !exists {
				t.Errorf("%s.%s: extra key in Go", path, k)
			}
		}
	case []any:
		g, ok := stmtAsSlice(got)
		if !ok {
			t.Errorf("%s: want array, got %T %v", path, got, got)
			return
		}
		// ترتیبِ آرایه معنا دارد: سالانہ «جدیدترین در ابتدا» است و سریِ فصلی
		// `sort(..., reverse=True)`؛ جابه‌جایی دو ردیف رأیِ دیگری می‌سازد.
		if len(g) != len(w) {
			t.Errorf("%s: array length want %d got %d", path, len(w), len(g))
			return
		}
		for i := range w {
			stmtAssertValue(t, fmt.Sprintf("%s[%d]", path, i), w[i], g[i])
		}
	case string:
		g, ok := got.(string)
		if !ok {
			t.Errorf("%s: want string %q, got %T %v", path, w, got, got)
			return
		}
		if w != g {
			t.Errorf("%s: want %q got %q", path, w, g)
		}
	case bool:
		g, ok := got.(bool)
		if !ok {
			t.Errorf("%s: want bool %v, got %T %v", path, w, got, got)
			return
		}
		if w != g {
			t.Errorf("%s: want %v got %v", path, w, g)
		}
	default:
		t.Errorf("%s: unhandled want type %T", path, want)
	}
}

// ── annual_statements ───────────────────────────────────────────────────────

// TestAnnualStatementsMatchesOracle همان `annual_statements(con, sym, limit=lim)`
// با پیش‌فرض‌هایِ اورتکاژنر (require_audit/exclude_consolidated = True).
func TestAnnualStatementsMatchesOracle(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "annual")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	withRows, emptyCases := 0, 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "annual", i, c)
		lim := stmtCaseInt(t, "annual", i, c, "limit")
		got, err := s.AnnualStatements(ctx, sym, true, true, lim)
		if err != nil {
			t.Fatalf("annual_statements(%s, %d): %v", sym, lim, err)
		}
		if len(got) > 0 {
			withRows++
		} else {
			emptyCases++
		}
		stmtAssertValue(t, "annual", c["out"], got)
	}
	// شاخۀ «سالانۀ ۱۲ماهه ندارد» باید واقعاً اجرا شده باشد، نه با خاص‌رفتار
	// رد شود: فیکسچر دو نماد بی‌سالانہ دارد (کم‌سابقه11 هیچ ردیفی، متنوع01 همه
	// با تاریخِ خط‌تیره که DATED_SQL درِ SQL بیرونشان می‌گذارد).
	if emptyCases == 0 {
		t.Errorf("no symbol produced zero annual rows — شاخۀ بی‌سالانہ آزمون نشده")
	}
	if withRows == 0 {
		t.Errorf("no symbol produced any annual row — لایۀ انتخاب آزمون نشده")
	}
}

// ── reference_annual / pick_reference ────────────────────────────────────────

// TestReferenceAnnualMatchesOracle شاخه‌هایِ تنزلِ `pick_reference` را رویِ
// ردیف‌هایِ واقعیِ همان فیکسچر می‌سنجد (limit=12، بی‌need).
func TestReferenceAnnualMatchesOracle(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "reference")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	hits, misses := 0, 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "reference", i, c)
		got, err := s.ReferenceAnnual(ctx, sym, nil)
		if err != nil {
			t.Fatalf("reference_annual(%s): %v", sym, err)
		}
		if len(got) > 0 {
			hits++
		} else {
			misses++
		}
		stmtAssertValue(t, "reference", c["out"], got)
	}
	if misses == 0 || hits == 0 {
		t.Errorf("reference tiers under-covered: hits=%d misses=%d — یکِ شاخه هیچ‌وقت اجرا نشده", hits, misses)
	}
}

// ── gross_margin / margin_reference ──────────────────────────────────────────

// TestGrossMarginMatchesOracle همان `gross_margin(con, sym, min_margin, optimal,
// ref=reference_annual(con, sym))` با سه جفتِ آستانه برای هر نماد. ششِ کیسِ
// بی‌جوابِ فیکسچر (کم‌سابقه11 و متنوع01) هم از همین حلقه می‌گذرند؛ چیزی برای‌شان
// ساخته نمی‌شود.
func TestGrossMarginMatchesOracle(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "gross")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	refs := map[string]map[string]any{}
	nulls, values := 0, 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "gross", i, c)
		minMargin := stmtCaseFloat(t, "gross", i, c, "min")
		optimal := stmtCaseFloat(t, "gross", i, c, "opt")
		ref, ok := refs[sym]
		if !ok {
			// اورتکاژنر یک‌بار `reference_annual` می‌خواند و همان `ref` را رد
			// می‌کند؛ اینجا هم ردیفِ مرجع از خودِ لایه می‌آید و به همان وکتور
			// سنجیده می‌شود، تا مسیرِ margin_reference (ref → need → تنزل) رویِ
			// همان ردیفی بخورد که پایتون دید.
			gotRef, err := s.ReferenceAnnual(ctx, sym, nil)
			if err != nil {
				t.Fatalf("reference_annual(%s): %v", sym, err)
			}
			stmtAssertValue(t, "gross.ref", c["ref"], gotRef)
			ref = gotRef
			refs[sym] = ref
		}
		got, err := s.GrossMargin(ctx, sym, minMargin, optimal, ref, nil)
		if err != nil {
			t.Fatalf("gross_margin(%s, %v, %v): %v", sym, minMargin, optimal, err)
		}
		if got == nil {
			nulls++
		} else {
			values++
		}
		stmtAssertValue(t, "gross", c["out"], got)
	}
	// «سود ناخالص ندارد/ردیف ندارد» باید دیده باشد، وگرنه صفرِ گمراه‌کننده هم
	// سبز رد می‌شد.
	if nulls == 0 {
		t.Errorf("no gross_margin call returned null — شاخۀ «قابل محاسبه نبود» آزمون نشده")
	}
	if values == 0 {
		t.Errorf("no gross_margin call produced a number — حاشیه هیچ‌وقت ساخته نشده")
	}
}

// TestGrossMarginRowsBranchEqualsQueryBranch قاعدۀ خودِ fts_engine است (بندِ
// P-2 و docstringِ margin_reference): «bulk ردیف‌های ازپیش‌خوانده را می‌دهد تا
// کوئریِ دوم زده نشود» — یعنی دو ورودیِ `rows` و `conn` باید یکِ ردیف را مرجع
// بگیرند. انتظارِ دستی اینجا نمی‌آید؛ مبنایِ داوری همان عددِ وکتورِ پایتون است.
func TestGrossMarginRowsBranchEqualsQueryBranch(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "gross")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	checked := 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "gross", i, c)
		minMargin := stmtCaseFloat(t, "gross", i, c, "min")
		optimal := stmtCaseFloat(t, "gross", i, c, "opt")
		rows, err := s.AnnualStatements(ctx, sym, false, false, 12)
		if err != nil {
			t.Fatalf("annual_statements(%s): %v", sym, err)
		}
		viaRows, err := s.GrossMargin(ctx, sym, minMargin, optimal, nil, rows)
		if err != nil {
			t.Fatalf("gross_margin(rows=%d): %v", len(rows), err)
		}
		viaQuery, err := s.GrossMargin(ctx, sym, minMargin, optimal, nil, nil)
		if err != nil {
			t.Fatalf("gross_margin(rows=nil): %v", err)
		}
		// ردیفِ بی‌سالانہ آرایۀ خالی می‌دهد و `rows != nil` می‌ماند (همان تفکیکِ
		// `if rows is not None` درِ پایتون)؛ پس هر دو باید بی‌جواب باشند.
		stmtAssertValue(t, "gross.rows", viaQuery, viaRows)
		stmtAssertValue(t, "gross", c["out"], viaRows)
		checked++
	}
	if checked != len(cases) {
		t.Errorf("rows-branch cases checked = %d want %d", checked, len(cases))
	}
}

// ── company_name_of ─────────────────────────────────────────────────────────

// TestCompanyNameOfMatchesOracle ترتیبِ «تازۀترین دوره اول، بی‌دوره آخر، سپس
// tracing_no DESC» را رویِ ردیف‌هایِ واقعیِ همان فیکسچر می‌سنجد — از جمله نمادی
// که بی‌نام است و رشتهٔ خالی می‌گیرد، نه خطا.
func TestCompanyNameOfMatchesOracle(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "names")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	blanks := 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "names", i, c)
		got, err := s.CompanyNameOf(ctx, sym)
		if err != nil {
			t.Fatalf("company_name_of(%s): %v", sym, err)
		}
		if got == "" {
			blanks++
		}
		stmtAssertValue(t, "names", c["out"], got)
	}
	if blanks == 0 {
		t.Errorf("no symbol produced an empty company name — شاخۀ بی‌نام آزمون نشده")
	}
}

// ── quarter_reference_rows ──────────────────────────────────────────────────

// TestQuarterReferenceRowsMatchesOracle همان کوئریِ اورتکاژنر (پیش‌فیلترِ
// DATED_SQL، بدونِ ORDER BY) و سپس لایۀ انتخابِ موجود درِ reference.go، رویِ
// پنج limit از جمله صفر و ۹۹۹ که به ۱ و ۴۰ می‌چسبند.
func TestQuarterReferenceRowsMatchesOracle(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "quarter_ref")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	clamped := 0
	empties := 0
	for i, c := range cases {
		sym := stmtCaseSymbol(t, "quarter_ref", i, c)
		lim := stmtCaseInt(t, "quarter_ref", i, c, "limit")
		raw, err := s.rows(ctx, "SELECT period_end, period_months, revenue, gross_profit,"+
			" operating_profit, net_profit, basic_eps, publish_date, title, tracing_no,"+
			" report_kind FROM financial_statements WHERE symbol = ? AND "+
			period.DatedSQL(""), []any{sym})
		if err != nil {
			t.Fatalf("raw quarter rows for %s: %v", sym, err)
		}
		got := QuarterReferenceRows(raw, lim)
		if lim < 1 || lim > 40 {
			clamped++
		}
		if len(got) == 0 {
			empties++
		}
		stmtAssertValue(t, "quarter_ref", c["out"], got)
	}
	if clamped == 0 || empties == 0 {
		t.Errorf("quarter_ref under-covered: clamped=%d empties=%d", clamped, empties)
	}
}

// ── درِ واحد (codal_units) ───────────────────────────────────────────────────

// TestStatementUnitFieldsComeFromRow وکتورهایِ `unit_valid`/`unit_label`/
// `unit_norm`/`unit` را دوباره می‌خواند و ثابت می‌کند مقیاس از خودِ ردیف آمده،
// نه از ثابتِ ماژول: هیچ مقدارِ تازه‌ای اینجا نوشته نمی‌شود، فقط همان چهار
// فیلد از بدنهٔ برگشتیِ Go جدا می‌شوند.
func TestStatementUnitFieldsComeFromRow(t *testing.T) {
	doc := stmtVectors(t)
	cases := stmtCases(t, doc, "gross")
	ctx := context.Background()
	s := stmtOpenFixture(t)
	defer s.Close()

	seen := 0
	for i, c := range cases {
		want := c["out"]
		w, ok := want.(map[string]any)
		if !ok {
			continue
		}
		sym := stmtCaseSymbol(t, "gross", i, c)
		got, err := s.GrossMargin(ctx, sym, stmtCaseFloat(t, "gross", i, c, "min"),
			stmtCaseFloat(t, "gross", i, c, "opt"), mustStmtRefOf(t, s, ctx, c), nil)
		if err != nil {
			t.Fatalf("gross_margin(%s): %v", sym, err)
		}
		for _, key := range []string{"unit", "unit_label", "unit_valid"} {
			stmtAssertValue(t, "gross."+key, w[key], got[key])
		}
		seen++
	}
	if seen == 0 {
		t.Errorf("no gross_margin vector carried a unit object — لایۀ واحد آزمون نشده")
	}
}

// mustStmtRefOf `ref` را از همان لایه می‌گیرد (اوراکلِ وکتور هم چنین کرد)؛ بی‌
// خواندنِ ردیفِ مرجع از JSON، چون آن ردیف خودش زیرِ داوریِ همین فایل است.
func mustStmtRefOf(t *testing.T, s *Service, ctx context.Context,
	c map[string]any) map[string]any {
	t.Helper()
	ref, err := s.ReferenceAnnual(ctx, c["symbol"].(string), nil)
	if err != nil {
		t.Fatalf("reference_annual: %v", err)
	}
	return ref
}
