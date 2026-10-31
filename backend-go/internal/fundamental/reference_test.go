package fundamental

import (
	"fmt"
	"testing"
)

// date می‌سازد تا جداکننده درِ این فایل هرگز به خطِ تیره تبدیل نشود: `canonicalize`
// «۱۴۰۱-۰۶-۳۱» را به «۱۴۰۱/۰۶/۳۱» برمی‌گرداند (دو شکلِ یکِ تاریخ)، پس یکِ آزمونِ
// دست‌نویس با خطِ تیره می‌تواند دو ردیفِ «دورۀ متفاوت» را به یکِ کلید برساند.
func date(y, m, d int) string { return fmt.Sprintf("%04d/%02d/%02d", y, m, d) }

func row(kv map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range kv {
		out[k] = v
	}
	return out
}

func TestNormFaAndEntitySpan(t *testing.T) {
	if got := normFa("تلفيقي"); got != "تلفیقی" {
		t.Errorf("normFa arabic-kaf/yaa: %q", got)
	}
	// «(شرکت هلپاک)» شخصیتِ حقوقی است؛ «(حسابرسی شده)» مقطعِ نامه؛ «(شرکت اصلی)»
	// عمومی؛ «(الف)» کوتاه‌تر از آستانه.
	for _, c := range []struct{ in, want string }{
		{"شرکت هلپاک", "شرکت هلپاک"},
		{"گروه پارس", "گروه پارس"},
		{"حسابرسی شده", ""},
		{"شامل مقادیر برآوردی", ""},
		{"شرکت اصلی", ""},
		{"هلپاک", ""},
		{"ا", ""},
	} {
		if got := entitySpan(c.in); got != c.want {
			t.Errorf("entitySpan(%q) = %q want %q", c.in, got, c.want)
		}
	}
	// پرانتزِ عربی و فارسی هر دو باز می‌شوند و پایانی‌ترینِ معتبر برنده است.
	title := "صورت مالی (حسابرسی شده) (شرکت هلپاک)"
	if got := titleEntitySuffix(title); got != "شرکت هلپاک" {
		t.Errorf("titleEntitySuffix = %q", got)
	}
	if got := titleEntitySuffix("صورت مالی （حسابرسی شده）"); got != "" {
		t.Errorf("arabic-paren scope mark must not be an entity, got %q", got)
	}
	if !isConsolidated("صورت مالی حسابرسی‌شدهٔ تلفیقی") {
		t.Error("تلفیقی must be consolidated")
	}
	if isConsolidated("صورت مالی حسابرسی‌شدهٔ غیرتلفیقی") {
		t.Error("غیرتلفیقی must NOT be consolidated — بندِ دومِ _is_consolidated")
	}
}

func TestRowCompletenessCountsZeroAsFilled(t *testing.T) {
	full := row(map[string]any{"revenue": 1.0, "gross_profit": 0.0,
		"operating_profit": nil, "net_profit": "", "basic_eps": "  "})
	if got := rowCompleteness(full); got != 2 {
		t.Errorf("completeness = %d want 2 (صفرِ واقعی پُر، None/رشتهٔ خالی نه)", got)
	}
}

func TestQuarterReferenceRowsPicksOnePerPeriod(t *testing.T) {
	rows := []map[string]any{
		// دو نسخۀ یکِ (دوره، طول، نوع): تلفیقیِ تازه با ستون‌هایِ خالی باید
		// ببازد — دقیقاً همان نقصی که CA-2 بست (پوستۀ بی‌عددِ تازه‌تر ردیفِ
		// عدددارِ کهنه‌تر را می‌کُشت).
		row(map[string]any{"period_end": date(1401, 6, 31), "period_months": 6,
			"report_kind": "", "title": "دوره ۶ ماهه (تلفیقی)", "tracing_no": 200,
			"revenue": nil, "gross_profit": nil, "operating_profit": nil,
			"net_profit": nil, "basic_eps": nil}),
		row(map[string]any{"period_end": date(1401, 6, 31), "period_months": 6,
			"report_kind": "", "title": "دوره ۶ ماهه", "tracing_no": 100,
			"revenue": 10.0, "gross_profit": 4.0, "operating_profit": 3.0,
			"net_profit": 2.0, "basic_eps": 0.5}),
		// ردیفِ شرکتِ فرعی زیرِ نمادِ هلدینگ: کامل و تازه هم می‌بازد (لایۀ صفر).
		row(map[string]any{"period_end": date(1402, 6, 31), "period_months": 12,
			"report_kind": "", "title": "صورت مالی (شرکت هلپاک)",
			"tracing_no": 300, "revenue": 99.0, "gross_profit": 9.0,
			"operating_profit": 9.0, "net_profit": 9.0, "basic_eps": 1.0}),
		// تنها ردیف‌هایِ این دوره هر دو «شرکتِ دیگر»اند؛ لایۀ صفر بینِ آن‌ها داوری
		// نمی‌کند، پس قاعدۀ بعدی (کامل‌بودن) می‌گزیند: ۳۰۰ با پنج ستون برِ ۱۱۰ با
		// یک ستون — و هیچ ردیفی حذف نمی‌شود (سیاستِ CA-3).
		row(map[string]any{"period_end": date(1402, 6, 31), "period_months": 12,
			"report_kind": "", "title": "صورت مالی (شرکت بهمن)", "tracing_no": 110,
			"revenue": 1.0}),
		// بی‌دورۀ واقعی: هرگز واردِ سری نمی‌شود.
		row(map[string]any{"period_end": "", "period_months": 12,
			"report_kind": "", "title": "بی‌دوره", "tracing_no": 400}),
		// یکِ دوره با دوِ طول ⇒ دو کلیدِ جدا، هر دو می‌مانند؛ طولِ این یکی از
		// عنوان خوانده می‌شود (ستون تهی) و منبعش اعلام.
		row(map[string]any{"period_end": date(1402, 9, 30), "period_months": nil,
			"report_kind": "", "title": "دوره ۹ ماهه", "tracing_no": 120,
			"revenue": 5.0}),
		row(map[string]any{"period_end": date(1402, 9, 30), "period_months": 3,
			"report_kind": "", "title": "دوره ۳ ماهه", "tracing_no": 130,
			"revenue": 5.0}),
	}
	got := QuarterReferenceRows(rows, 16)
	if len(got) != 4 {
		t.Fatalf("rows = %d want 4: %+v", len(got), keysOf(got))
	}
	// ترتیبِ نزولیِ (دوره، طول، نوع، tracing_no): 1402/09/30×9 ← ×3 ← 1402/06/31 ← 1401/06/31
	want := []struct {
		pe     string
		months int64
		tn     int64
		src    any
	}{
		{date(1402, 9, 30), 9, 120, "title"},
		{date(1402, 9, 30), 3, 130, nil},
		{date(1402, 6, 31), 12, 300, nil},
		{date(1401, 6, 31), 6, 100, nil},
	}
	for i, w := range want {
		if got[i]["period_end"] != w.pe {
			t.Errorf("row %d period_end = %v want %v", i, got[i]["period_end"], w.pe)
		}
		if m, _ := toI(got[i]["period_months"]); m != w.months {
			t.Errorf("row %d months = %v want %d", i, got[i]["period_months"], w.months)
		}
		if tn, _ := toI(got[i]["tracing_no"]); tn != w.tn {
			t.Errorf("row %d winner tracing_no = %v want %v", i, got[i]["tracing_no"], w.tn)
		}
		if src := got[i]["months_source"]; src != w.src {
			t.Errorf("row %d months_source = %v want %v", i, src, w.src)
		}
	}
}

// TestEntityLayerOutranksNewnessAndCompleteness: لایۀ صفرِ `statement_rank` باید
// برِ سه لایۀ بعدی باشد. این آزمون همان کنترلِ منفی را می‌سوزاند: با خاموش‌کردنِ
// لایۀ دامنۀ شرکت، همین کیس قرمز می‌شود و کیس‌هایِ دیگر سبز می‌مانند.
func TestEntityLayerOutranksNewnessAndCompleteness(t *testing.T) {
	rows := []map[string]any{
		// شرکتِ فرعی: تازه‌ترین و کامل‌ترینِ این دوره.
		row(map[string]any{"period_end": date(1403, 12, 29), "period_months": 12,
			"report_kind": "", "title": "صورت مالی سالانه (شرکت هلپاک)",
			"tracing_no": 500, "revenue": 900.0, "gross_profit": 300.0,
			"operating_profit": 250.0, "net_profit": 120.0, "basic_eps": 12.0}),
		// خودِ نماد: کهنه‌تر و کم‌عددتر — با این حال برنده است.
		row(map[string]any{"period_end": date(1403, 12, 29), "period_months": 12,
			"report_kind": "", "title": "صورت مالی سالانه", "tracing_no": 450,
			"revenue": 1.0}),
	}
	got := QuarterReferenceRows(rows, 16)
	if len(got) != 1 {
		t.Fatalf("rows = %d want 1", len(got))
	}
	if tn, _ := toI(got[0]["tracing_no"]); tn != 450 {
		t.Fatalf("winner = %v want 450 — ردیفِ «شرکتِ دیگر» نمایندۀ این نماد نیست، " +
			"هرچند کامل‌تر و تازه‌تر باشد", got[0]["tracing_no"])
	}
}

func TestQuarterReferenceRowsLimitAndClamp(t *testing.T) {
	var rows []map[string]any
	for i := 1; i <= 20; i++ {
		rows = append(rows, row(map[string]any{
			"period_end": date(1401, (i%4)+1, 31), "period_months": 3,
			"report_kind": "", "title": "دوره ۳ ماهه", "tracing_no": int64(100 + i)}))
	}
	if got := len(QuarterReferenceRows(rows, 0)); got != 1 {
		t.Errorf("limit 0 clamps to 1, got %d", got)
	}
	if got := len(QuarterReferenceRows(rows, -5)); got != 1 {
		t.Errorf("negative limit clamps to 1, got %d", got)
	}
	if got := len(QuarterReferenceRows(rows, 999)); got != 4 {
		// تنها چهارِ (1401,1..4,31) کلیدِ یکتا می‌سازند؛ سقفِ ۴۰ ردیفِ موجود را
		// کوتاه نمی‌کند — یعنی clampِ بالا بی‌کرش است و limitِ بیش‌ازاندازه
		// «همه» می‌دهد، نه panic.
		t.Errorf("limit 999 over 4 distinct keys = %d want 4", got)
	}
	if got := len(QuarterReferenceRows(rows, "abc")); got != 4 {
		// ورودیِ غیرعدد ⇒ سقفِ ۱۶ (شاخهٔ TypeErrorِ پایتون)؛ ردیف‌هایِ موجود کمتر
		// از سقف‌اند، پس همان چهارِ یکتا برمی‌گردد — نه کرش، نه فهرستِ خالی.
		t.Errorf("fallback limit kept %d rows want 4", got)
	}
	if got := len(QuarterReferenceRows(nil, 16)); got != 0 {
		t.Errorf("nil rows must give an empty series, got %d", got)
	}
}

func keysOf(rows []map[string]any) []string {
	out := []string{}
	for _, r := range rows {
		s, _ := r["period_end"].(string)
		out = append(out, s)
	}
	return out
}
