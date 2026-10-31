package period

import (
	"database/sql"
	"encoding/json"
	"os"
	"sort"
	"testing"

	_ "modernc.org/sqlite"
)

type sqlVec struct {
	Text []struct {
		Call  string  `json:"call"`
		Alias *string `json:"alias"`
		Out   string  `json:"out"`
	} `json:"text"`
	Rows []struct {
		TracingNo int64   `json:"tracing_no"`
		PeriodEnd *string `json:"period_end"`
	} `json:"rows"`
	PyCanonicalIDs []int64 `json:"py_canonical_ids"`
	DatedIDs       []int64 `json:"dated_ids"`
	UndatedIDs     []int64 `json:"undated_ids"`
	OrderIDs       []int64 `json:"order_ids"`
	LatestDatedID  *int64  `json:"latest_dated_id"`
	LatestAnyID    *int64  `json:"latest_any_id"`
	SeamIDs        []int64 `json:"seam_ids"`
}

func loadSQL(t *testing.T) sqlVec {
	t.Helper()
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var all struct {
		SQL sqlVec `json:"sql"`
	}
	if err := json.Unmarshal(raw, &all); err != nil {
		t.Fatal(err)
	}
	if len(all.SQL.Rows) == 0 || len(all.SQL.Text) == 0 {
		t.Fatal("sql section is empty — a vacuous golden")
	}
	return all.SQL
}

// TestSQLTextGolden هر دو زبان باید همان رشته را به SQLite بدهند؛ متن‌ها از خودِ
// codal_periods.py ثبت شده‌اند.
func TestSQLTextGolden(t *testing.T) {
	v := loadSQL(t)
	counts := map[string]int{}
	for _, c := range v.Text {
		alias := ""
		if c.Alias != nil {
			alias = *c.Alias
		}
		var got string
		switch c.Call {
		case "dated_sql":
			got = DatedSQL(alias)
		case "undated_sql":
			got = UndatedSQL(alias)
		case "order_expr":
			got = OrderExpr(alias)
		case "latest_order_sql":
			got = LatestOrderSQL(alias)
		case "DATED_SQL":
			got = DatedSQL("")
		case "UNDATED_SQL":
			got = UndatedSQL("")
		case "VALID_GLOB":
			got = ValidGlob
		default:
			t.Fatalf("unknown sql call in golden: %q", c.Call)
		}
		counts[c.Call]++
		if got != c.Out {
			t.Errorf("%s(%q):\n got %s\nwant %s", c.Call, alias, got, c.Out)
		}
	}
	// هر سازنده چهار مستعار می‌خواهد؛ بی‌این، کم شدنِ ردیف‌هایِ طلایی آزمون را
	// بی‌صدا توخالی می‌کرد.
	for _, call := range []string{"dated_sql", "undated_sql", "order_expr", "latest_order_sql"} {
		if counts[call] != 4 {
			t.Errorf("%s vectors = %d, want 4", call, counts[call])
		}
	}
}

func openVectorDB(t *testing.T, v sqlVec) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	db.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = db.Close() })
	if _, err := db.Exec("CREATE TABLE financial_statements " +
		"(tracing_no INTEGER PRIMARY KEY, period_end TEXT)"); err != nil {
		t.Fatal(err)
	}
	for _, r := range v.Rows {
		var val any
		if r.PeriodEnd != nil {
			val = *r.PeriodEnd
		}
		if _, err := db.Exec("INSERT INTO financial_statements (tracing_no, period_end) VALUES (?, ?)",
			r.TracingNo, val); err != nil {
			t.Fatal(err)
		}
	}
	return db
}

func queryIDs(t *testing.T, db *sql.DB, q string) []int64 {
	t.Helper()
	rs, err := db.Query(q)
	if err != nil {
		t.Fatalf("query failed: %v\nsql: %s", err, q)
	}
	defer rs.Close()
	out := []int64{}
	for rs.Next() {
		var n int64
		if err := rs.Scan(&n); err != nil {
			t.Fatal(err)
		}
		out = append(out, n)
	}
	if err := rs.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

func eqIDs(a, b []int64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func sortedIDs(xs []int64) []int64 {
	out := append([]int64(nil), xs...)
	sort.Slice(out, func(i, j int) bool { return out[i] < out[j] })
	return out
}

func one(p *int64) []int64 {
	if p == nil {
		return nil
	}
	return []int64{*p}
}

// TestSQLBehaviorGolden همان رشته‌ها را رویِ SQLite می‌گذارد و ردیف‌هایِ برگشته را
// با چیزی که پایتون از همان SQLite ثبت کرده مقایسه می‌کند: متنِ یکسان کافی نیست،
// «کدام ردیف برنده است و به چه ترتیب» هم باید یکسان بیفتد.
func TestSQLBehaviorGolden(t *testing.T) {
	v := loadSQL(t)
	db := openVectorDB(t, v)

	if got := queryIDs(t, db, "SELECT tracing_no FROM financial_statements WHERE "+
		DatedSQL("")+" ORDER BY tracing_no"); !eqIDs(got, v.DatedIDs) {
		t.Errorf("dated ids = %v want %v", got, v.DatedIDs)
	}
	if got := queryIDs(t, db, "SELECT tracing_no FROM financial_statements WHERE "+
		UndatedSQL("")+" ORDER BY tracing_no"); !eqIDs(got, v.UndatedIDs) {
		t.Errorf("undated ids = %v want %v", got, v.UndatedIDs)
	}
	if got := queryIDs(t, db, "SELECT tracing_no FROM financial_statements ORDER BY "+
		OrderExpr("")+", tracing_no DESC"); !eqIDs(got, v.OrderIDs) {
		t.Errorf("order ids = %v want %v", got, v.OrderIDs)
	}
	// دو شکلِ «آخرین» که درِ پایتون هر دو مصرف می‌شوند: با فیلترِ بی‌دوره و بی‌آن
	// (بی‌دوره بازندهٔ ترتیب است، نه حذف‌شده — نمادی که فقط ردیفِ بی‌دوره دارد
	// بی‌جواب نمی‌ماند).
	if got := queryIDs(t, db, "SELECT tracing_no FROM financial_statements WHERE "+DatedSQL("")+
		" "+LatestOrderSQL("")+" LIMIT 1"); !eqIDs(got, one(v.LatestDatedID)) {
		t.Errorf("latest with dated filter = %v want %v", got, one(v.LatestDatedID))
	}
	if got := queryIDs(t, db, "SELECT tracing_no FROM financial_statements "+
		LatestOrderSQL("")+" LIMIT 1"); !eqIDs(got, one(v.LatestAnyID)) {
		t.Errorf("latest without filter = %v want %v", got, one(v.LatestAnyID))
	}

	// دو شرط باید تقسیمِ کامل بدهند: نه ردیفی هم‌زمان در هر دو، نه ردیفی بیرون.
	var all []int64
	for _, r := range v.Rows {
		all = append(all, r.TracingNo)
	}
	both := append(append([]int64{}, v.DatedIDs...), v.UndatedIDs...)
	if !eqIDs(sortedIDs(both), sortedIDs(all)) || len(v.DatedIDs) == 0 || len(v.UndatedIDs) == 0 {
		t.Errorf("dated+undated is not a partition: %v + %v over %v", v.DatedIDs, v.UndatedIDs, all)
	}
	if len(v.OrderIDs) != len(v.Rows) {
		t.Errorf("order ids = %d rows, want %d (every row must be ranked)",
			len(v.OrderIDs), len(v.Rows))
	}
}

// TestTrimSeamIsReproduced شرطِ پایتون (`.strip()`) و شرطِ SQL (`trim()` فقط
// فاصلهٔ U+0020) رویِ سه ردیفِ شاهد جدا می‌افتند. Go باید هر دو را عینِ پایتون
// بدهد؛ اگر روزی یکی را به دیگری «نزدیک» کنیم این آزمون قرمز می‌شود، چون آن‌وقت
// با پایتونِ درِ همان بانک نمی‌خواند.
func TestTrimSeamIsReproduced(t *testing.T) {
	v := loadSQL(t)
	db := openVectorDB(t, v)

	pyWant := map[int64]bool{}
	for _, id := range v.PyCanonicalIDs {
		pyWant[id] = true
	}
	seam := map[int64]bool{}
	for _, id := range v.SeamIDs {
		seam[id] = true
	}
	if len(v.SeamIDs) < 3 {
		t.Fatalf("seam rows = %d; vectors no longer carry the trim gap", len(v.SeamIDs))
	}

	// شرطِ پایتون از همان ردیف‌ها درِ Go بازخوانی می‌شود
	for _, r := range v.Rows {
		var val any
		if r.PeriodEnd != nil {
			val = *r.PeriodEnd
		}
		if got := IsCanonical(val); got != pyWant[r.TracingNo] {
			t.Errorf("IsCanonical(%q) = %v, python recorded %v", deref(r.PeriodEnd), got,
				pyWant[r.TracingNo])
		}
	}

	// شرطِ SQL از Go: تفکیکِ واقعی، و شکافِ بینِ دو شرط باید مو‌به‌مو همان
	// seam_idsِ ثبت‌شده باشد و از جای خالیِ غیرفاصله آمده باشد.
	sqlDated := map[int64]bool{}
	for _, id := range queryIDs(t, db, "SELECT tracing_no FROM financial_statements WHERE "+
		DatedSQL("")) {
		sqlDated[id] = true
	}
	var gotSeam []int64
	for _, r := range v.Rows {
		if pyWant[r.TracingNo] != sqlDated[r.TracingNo] {
			gotSeam = append(gotSeam, r.TracingNo)
			if r.PeriodEnd == nil || !hasNonSpaceWhitespace(*r.PeriodEnd) {
				t.Errorf("seam row %d (%q) has no non-space whitespace", r.TracingNo, *r.PeriodEnd)
			}
		}
	}
	if !eqIDs(sortedIDs(gotSeam), sortedIDs(v.SeamIDs)) {
		t.Errorf("seam rows = %v want %v", gotSeam, v.SeamIDs)
	}
}

// hasNonSpaceWhitespace: جای خالی‌ای که `.strip()`ِ پایتون برمی‌دارد و `trim()`ِ
// SQLite نه (تب، nbsp، U+001C..).
func hasNonSpaceWhitespace(s string) bool {
	for _, r := range s {
		if pyIsSpace(r) && r != ' ' {
			return true
		}
	}
	return false
}
