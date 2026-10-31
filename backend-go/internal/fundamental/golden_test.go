package fundamental

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
)

// openService همان فیکسچرِ یخ‌زدۀ تسکِ ۱ را درِ یکِ پوشۀ موقت باز می‌کند؛ کپی
// می‌شود تا بانکِ کامیت‌شده دست‌نخورده بماند (قیدِ گیت‌ها).
func openService(t *testing.T) *Service {
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

func loadGolden(t *testing.T, scenario, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", scenario, name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func compareGolden(t *testing.T, label string, want map[string]any, got any) {
	t.Helper()
	body, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal body: %v", label, err)
	}
	var norm map[string]any
	if err := json.Unmarshal(body, &norm); err != nil {
		t.Fatalf("%s: unmarshal body: %v", label, err)
	}
	res := parity.Compare(want, norm, parity.Options{})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", label, d)
		}
	}
}

type goldenCase struct {
	stem  string
	limit int
}

// quartersCases همان هفت کیسِ اوراکل است. سقفِ limit درِ این جدول می‌آید (ازِ
// پاسخِ قابلِ بازیابی نیست)؛ نامِ نماد از خودِ طلایی خوانده می‌شود، نه از
// تایپِ دستی — رقمِ فارسیِ درِ نامِ نماد درِ ویرایشِ دستی رقم می‌دزدد.
var quartersCases = []goldenCase{
	{"quarters_up", 16},
	{"quarters_mixed", 16},
	{"quarters_thin", 4},
	{"quarters_clamp_high", 999},
	{"quarters_clamp_zero", 0},
	{"quarters_negative", -5},
	{"quarters_missing", 8},
}

// TestFundamentalGoldens پاسخِ Go را با بدنه‌ای که اوراکلِ پایتون رویِ همان
// فیکسچر نوشته مقایسه می‌کند: Δ صفر، وگرنه یکی از دو لایه (SQL یا انتخابِ مرجع)
// با پایتون نمی‌خواند.
func TestFundamentalGoldens(t *testing.T) {
	ctx := context.Background()
	s := openService(t)
	defer s.Close()

	got := s.SectorsBody(ctx)
	compareGolden(t, "sectors", loadGolden(t, "s1", "sectors"), got)
	// سنجهٔ مستقل: فهرستِ Go باید همان هشت صنعتِ طلایی باشد، با همان ترتیبِ
	// واژگانیِ SQLite — بی‌این، یکِ پاسخِ تهی هم «مساویِ ساختاری» رد می‌شد.
	if list, ok := got["sectors"].([]any); !ok || len(list) == 0 {
		t.Fatalf("sectors body is empty: %+v", got)
	}

	ran := 0
	for _, c := range quartersCases {
		want := loadGolden(t, "s1", c.stem)
		sym, _ := want["symbol"].(string)
		if sym == "" {
			t.Fatalf("%s: golden has no symbol to replay", c.stem)
		}
		compareGolden(t, c.stem, want, s.QuartersBody(ctx, sym, c.limit))
		ran++
	}
	if ran != len(quartersCases) {
		t.Errorf("quarters cases run = %d want %d", ran, len(quartersCases))
	}
}

// TestQuartersPreservesNullFromLiveQuery: #102 (رأیِ جزوه) — نبودِ «سود ناخالص»
// درِ پاسخ حفظ می‌شود؛ نه صفر می‌شود و نه با سودِ خالص جایگزین.
//
// چرا این آزمون رویِ یکِ بانکِ ساخته‌شده می‌نشیند و نه رویِ طلایی‌ها: هیچ‌یک از
// هفت کیسِ `quarters_*` درِ فیکسچرِ تسکِ ۱ ردیفِ **دوره‌دارِ** بی‌سودناخالص ندارد
// (همان‌ها که NULL بودند با تاریخِ خط‌تیره بودند و `DATED_SQL` از درِ SQL بیرونشان
// می‌گذارد). یعنی مقایسهٔ طلایی‌ها تنهایی این شاخه را نمی‌دید و یک باگِ
// «gross_profit را از net_profit پر کن» سبز رد می‌شد. درِ بانکِ عملیاتی چنین
// ردیفی هست (صندوق/بیمه) و گیتِ B4 رویِ کپیِ یخ‌زدۀ همان بانک آن را می‌سنجد.
func TestQuartersPreservesNullFromLiveQuery(t *testing.T) {
	// بانکِ موقتی رویِ دیسک، نه `:memory:` با استخرِ یک‌اتصالی: خودِ ریزولورِ
	// هویت یکِ اتصالِ اختصاصی را نگه می‌دارد (کشِ data_version) و آن‌وقت
	// نخستین کوئریِ خواندن برای همیشه منتظرِ اتصال می‌ماند.
	conn, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	if _, err := conn.Exec("CREATE TABLE financial_statements (" +
		"symbol TEXT, period_end TEXT, period_months INTEGER, title TEXT," +
		"revenue REAL, gross_profit REAL, operating_profit REAL, net_profit REAL," +
		"basic_eps REAL, publish_date TEXT, tracing_no INTEGER, report_kind TEXT)"); err != nil {
		t.Fatal(err)
	}
	// دو دوره: یکی با gross_profit تهی و سودِ خالصِ پُر (توسّتِ اصلی)، یکی سالم.
	if _, err := conn.Exec("INSERT INTO financial_statements VALUES "+
		"(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		"شهرفرش", "1404/09/30", 9, "دوره ۹ ماهه", 100.0, nil, 30.0, 12.0, 1.5,
		"1404/10/20 10:00:00", 700, ""); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("INSERT INTO financial_statements VALUES "+
		"(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		"شهرفرش", "1404/06/31", 6, "دوره ۶ ماهه", 60.0, 20.0, 18.0, 8.0, 1.0,
		"1404/07/20 10:00:00", 600, ""); err != nil {
		t.Fatal(err)
	}
	// ردیفِ بی‌دوره: هرگز نباید درِ سری بیاید (شرطِ DATED_SQL درِ SQL).
	if _, err := conn.Exec("INSERT INTO financial_statements VALUES "+
		"(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
		"شهرفرش", "1404-12-29", 12, "سالانه با خط تیره", 200.0, nil, nil, nil, nil,
		"1405/01/01", 800, ""); err != nil {
		t.Fatal(err)
	}

	s := New(conn)
	// ریزولورِ هویت یکِ اتصالِ اختصاصی نگه می‌دارد؛ بی‌Close، فایلِ بانکِ موقت
	// موقعِ پاک کردنِ TempDir قفل می‌ماند (ویندوز).
	t.Cleanup(func() { _ = s.Close() })
	got := s.QuartersBody(context.Background(), "شهرفرش", 16)
	rows, _ := got["quarters"].([]any)
	if len(rows) != 2 {
		t.Fatalf("rows = %d want 2 (بی‌دوره از درِ SQL فیلتر می‌شود): %+v", len(rows), got)
	}
	newest, _ := rows[0].(map[string]any)
	if newest["period_end"] != "1404/09/30" {
		t.Fatalf("row 0 = %v", newest)
	}
	v, ok := newest["gross_profit"]
	if !ok {
		t.Errorf("gross_profit key must be present even when null: %+v", newest)
	} else if v != nil {
		t.Errorf("gross_profit must stay null, got %v (net_profit=%v)", v, newest["net_profit"])
	}
	if newest["net_profit"] != 12.0 {
		t.Errorf("net_profit = %v want 12 — تهیِ یکِ ستون ستونِ دیگر را عوض نمی‌کند", newest["net_profit"])
	}
	// کلیدهایِ داخلی نباید درِ ردیفِ عمومی بنشینند.
	for _, extra := range []string{"title", "tracing_no", "report_kind", "months_source"} {
		if _, present := newest[extra]; present {
			t.Errorf("internal column %q leaked into the public row", extra)
		}
	}
	if got["status"] != "success" || got["symbol"] != "شهرفرش" || got["count"] != 2 {
		t.Errorf("envelope = %v/%v/%v", got["status"], got["symbol"], got["count"])
	}
}
