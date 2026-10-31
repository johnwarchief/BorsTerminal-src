package symbolid

import (
	"context"
	"database/sql"
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	_ "modernc.org/sqlite"
)

func testDB(t *testing.T) *sql.DB {
	t.Helper()
	path := filepath.Join(t.TempDir(), "market.db")
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(path)+"?mode=rwc")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	schema := `
CREATE TABLE instruments(ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
  isin TEXT, updated_at TEXT);
CREATE TABLE price_history(symbol TEXT, date TEXT);
CREATE TABLE user_watchlists(symbol TEXT);
CREATE TABLE financial_statements(symbol TEXT);
CREATE TABLE monthly_sales(symbol TEXT);
CREATE TABLE codal_notices(symbol TEXT);
`
	if _, err := db.Exec(schema); err != nil {
		t.Fatal(err)
	}
	ins := [][3]string{
		{"i1", "عادی01", "IRO1FOLD0001"},
		{"i2", "عادی 01", ""},
		{"i3", "عادي01", ""},
		{"i4", "آباد", "IRO1ABAD0001"},
		{"i5", "آباد3", "IRO1ABAD0001"},
		{"i6", "خودرو", "IRO1KHOD9999"},
		{"i7", "خودرو3", "IRO1KHOD0001"},
		{"i8", "پارتین2", ""},
		{"i9", "کمر1", "IRO1KAMR0001"},
		{"i10", "کمر2", "IRO2KAMR0001"},
		{"i11", "کمر3", "IRO1KAMR0001"},
	}
	for _, r := range ins {
		if _, err := db.Exec("INSERT INTO instruments VALUES(?,?,?,?,?)",
			r[0], r[1], r[1], r[2], "2026-10-27"); err != nil {
			t.Fatal(err)
		}
	}
	for _, sym := range []string{"عادی01", "عادی 01", "آباد", "آباد3", "خودرو",
		"خودرو3", "پارتین2", "کمر1", "کمر2", "کمر3"} {
		if _, err := db.Exec("INSERT INTO price_history VALUES(?,?)", sym, "2026-10-27"); err != nil {
			t.Fatal(err)
		}
	}
	for _, sym := range []string{"آباد", "خودرو", "کمر", "کمر1", "کمر2"} {
		if _, err := db.Exec("INSERT INTO financial_statements VALUES(?)", sym); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := db.Exec("INSERT INTO monthly_sales VALUES('آباد')"); err != nil {
		t.Fatal(err)
	}
	return db
}

func sorted(s []string) []string {
	out := append([]string(nil), s...)
	sort.Strings(out)
	return out
}

func TestKeyAndNorm(t *testing.T) {
	if got := Key("شهر ‌فرش"); got != "شهرفرش" {
		t.Fatalf("key=%q", got)
	}
	if got := Key("عادي01"); got != "عادی01" {
		t.Fatalf("arabic yeh key=%q", got)
	}
	if got := Norm("عادي01"); got != "عادی01" {
		t.Fatalf("norm=%q", got)
	}
	if got := Key(""); got != "" {
		t.Fatalf("empty key=%q", got)
	}
}

func TestBoardVariantsCollectSpellings(t *testing.T) {
	ctx := context.Background()
	r := New(testDB(t))
	defer r.Close()
	got, err := r.Variants(ctx, "عادی01", Board)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"عادی01", "عادی 01", "عادي01"}
	if !reflect.DeepEqual(sorted(got), sorted(want)) {
		t.Fatalf("variants=%v want=%v", sorted(got), sorted(want))
	}
	// input always present even when the DB has never seen it
	got, _ = r.Variants(ctx, "نمادتازه", Board)
	if !reflect.DeepEqual(got, []string{"نمادتازه"}) {
		t.Fatalf("unknown input must pass through: %v", got)
	}
	if got, _ := r.Variants(ctx, "", Board); got != nil {
		t.Fatalf("empty key must yield nothing: %v", got)
	}
}

func TestLineVariantsIsinGate(t *testing.T) {
	ctx := context.Background()
	r := New(testDB(t))
	defer r.Close()
	cases := []struct {
		sym  string
		raws []string
		ev   string
	}{
		{"آباد3", []string{"آباد"}, "isin-agree"},
		{"خودرو3", nil, "isin-clash"},
		{"کمر3", nil, "isin-clash"}, // دو ISIN زیرِ پایهٔ نام
		{"پارتین2", nil, "exact"},   // پایه ردیفِ کدال ندارد
		{"آباد3", nil, "exact"},     // در دامنهٔ تابلو هیچ الحاقی مجاز نیست
	}
	for i, c := range cases {
		domain := Domain(Codal)
		if i == len(cases)-1 {
			domain = Board
		}
		raws, ev, err := r.LineVariants(ctx, c.sym, domain)
		if err != nil {
			t.Fatal(err)
		}
		if ev != c.ev || !reflect.DeepEqual(sorted(raws), sorted(c.raws)) {
			t.Errorf("%s/%s: raws=%v ev=%q, want %v/%q", c.sym, domain, raws, ev, c.raws, c.ev)
		}
	}
}

func TestClassSiblingsAndEvidence(t *testing.T) {
	ctx := context.Background()
	r := New(testDB(t))
	defer r.Close()
	if got, ev, _ := r.ClassSiblings(ctx, "پارتین"); !reflect.DeepEqual(got, []string{"پارتین2"}) || ev != "no-isin" {
		t.Fatalf("siblings=%v/%q", got, ev)
	}
	if got, ev, _ := r.ClassSiblings(ctx, "آباد"); got != nil || ev != "same-key" {
		t.Fatalf("base present: %v/%q", got, ev)
	}
	if got, ev, _ := r.ClassSiblings(ctx, ""); got != nil || ev != "unmatched" {
		t.Fatalf("empty: %v/%q", got, ev)
	}
	cases := []struct {
		sym  string
		dom  Domain
		want string
	}{
		{"عادی01", Board, "same-key"},
		{"آباد", Codal, "same-key"},
		{"خودرو3", Codal, "isin-clash"},
		{"آباد4", Codal, "no-isin"},
		{"ناموجود", Codal, "unmatched"},
	}
	for _, c := range cases {
		got, err := r.Evidence(ctx, c.sym, c.dom)
		if err != nil || got != c.want {
			t.Errorf("evidence(%s/%s)=%q/%v want %q", c.sym, c.dom, got, err, c.want)
		}
	}
}

func TestPred(t *testing.T) {
	ctx := context.Background()
	r := New(testDB(t))
	defer r.Close()
	sqlText, params, err := r.Pred(ctx, "symbol", "آباد", Board)
	if err != nil {
		t.Fatal(err)
	}
	if sqlText != "symbol IN (?)" || len(params) != 1 || params[0] != "آباد" {
		t.Fatalf("pred=%q params=%v", sqlText, params)
	}
	if sqlText, _, _ := r.Pred(ctx, "symbol", "", Board); sqlText != "1=0" {
		t.Fatalf("empty symbol pred=%q", sqlText)
	}
}

// کنترلِ منفیِ کش: نوشتنِ اتصالِ دیگر باید دیده شود، وگرنه نامزدِ تازه برایِ
// همیشه گم می‌شود (همان سوراخی که data_version در پایتون می‌بندد).
func TestCacheSeesForeignCommit(t *testing.T) {
	ctx := context.Background()
	db := testDB(t)
	r := New(db)
	defer r.Close()
	if _, err := r.Variants(ctx, "آباد", Board); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("INSERT INTO instruments VALUES('i20','آباد ۴','', '', '2026-10-28')"); err != nil {
		t.Fatal(err)
	}
	got, err := r.Variants(ctx, "آباد۴", Board)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(sorted(got), sorted([]string{"آباد۴", "آباد ۴"})) {
		t.Fatalf("stale cache: %v", sorted(got))
	}
}
