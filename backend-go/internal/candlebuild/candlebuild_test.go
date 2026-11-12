package candlebuild

import (
	"database/sql"
	"math"
	"testing"

	_ "modernc.org/sqlite"
)

func newDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	stmts := []string{
		`CREATE TABLE adjustment_factors(symbol TEXT, date TEXT, ratio REAL,
		 kind TEXT, source TEXT, method TEXT, confidence TEXT, status TEXT,
		 q_before REAL, q_after REAL, prev_close REAL, capture_sha256 TEXT,
		 run_id TEXT, revision TEXT, details TEXT, created_at TEXT)`,
		`CREATE TABLE reference_raw(symbol TEXT, date TEXT, open REAL, high REAL,
		 low REAL, close REAL, volume REAL, run_id TEXT, capture_sha256 TEXT)`,
		`CREATE TABLE reference_adjusted(symbol TEXT, date TEXT, close REAL,
		 capture_sha256 TEXT)`,
	}
	for _, s := range stmts {
		if _, err := db.Exec(s); err != nil {
			t.Fatal(err)
		}
	}
	return db
}

func fixture(t *testing.T) *sql.DB {
	t.Helper()
	db := newDB(t)
	raw := []struct {
		d, o, h, l, c, v float64
	}{
		{0, 100, 105, 95, 100, 10},
		{0, 110, 112, 108, 110, 20},
		{0, 120, 121, 119, 120, 30},
	}
	dates := []string{"2026-01-01", "2026-01-02", "2026-01-03"}
	for i, r := range raw {
		if _, err := db.Exec(
			"INSERT INTO reference_raw VALUES('الف',?,?,?,?,?,?,?,?)",
			dates[i], r.o, r.h, r.l, r.c, r.v, "run", "cap"); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := db.Exec(
		"INSERT INTO adjustment_factors VALUES('الف','2026-01-03',0.5,'capital_increase'," +
			"'rahavard-type7-type0','implied-ratio-change','reference-exact'," +
			"'MEASURED_REFERENCE',2,1,120,'cap','run','rev1','{}','now')"); err != nil {
		t.Fatal(err)
	}
	for i, closeP := range []float64{50, 55, 120} {
		if _, err := db.Exec(
			"INSERT INTO reference_adjusted VALUES('الف',?,?,'cap')",
			dates[i], closeP); err != nil {
			t.Fatal(err)
		}
	}
	return db
}

func TestBuildAdjustsAndVerifies(t *testing.T) {
	db := fixture(t)
	res, err := Build(db)
	if err != nil {
		t.Fatal(err)
	}
	if res.Symbols != 1 || res.AdjustedRows != 3 || res.ExactRows != 3 {
		t.Fatalf("unexpected result: %+v", res)
	}
	if res.MaxRelError > 1e-12 {
		t.Fatalf("max rel error %g", res.MaxRelError)
	}
	rows, err := db.Query(
		"SELECT date, close, factor FROM adjusted_candles ORDER BY date")
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	got := map[string][2]float64{}
	for rows.Next() {
		var d string
		var c, f float64
		if err := rows.Scan(&d, &c, &f); err != nil {
			t.Fatal(err)
		}
		got[d] = [2]float64{c, f}
	}
	for _, want := range []struct {
		d string
		c float64
		f float64
	}{
		{"2026-01-01", 50, 0.5},
		{"2026-01-02", 55, 0.5},
		{"2026-01-03", 120, 1.0},
	} {
		if got[want.d] != [2]float64{want.c, want.f} {
			t.Errorf("%s: got %+v want %+v", want.d, got[want.d], want)
		}
	}
	statuses := map[string]string{}
	rs, err := db.Query("SELECT date, status FROM adjustment_verification")
	if err != nil {
		t.Fatal(err)
	}
	defer rs.Close()
	for rs.Next() {
		var d, s string
		if err := rs.Scan(&d, &s); err != nil {
			t.Fatal(err)
		}
		statuses[d] = s
	}
	if len(statuses) != 3 {
		t.Fatalf("verification rows %d", len(statuses))
	}
	for _, s := range statuses {
		if s != "EXACT" {
			t.Fatalf("status %q", s)
		}
	}
}

func TestBuildIdempotent(t *testing.T) {
	db := fixture(t)
	first, err := Build(db)
	if err != nil {
		t.Fatal(err)
	}
	second, err := Build(db)
	if err != nil {
		t.Fatal(err)
	}
	if first.AdjustedRows != second.AdjustedRows ||
		first.MaxRelError != second.MaxRelError ||
		first.Revisions[0] != second.Revisions[0] {
		t.Fatalf("not idempotent: %+v vs %+v", first, second)
	}
	var n int
	if err := db.QueryRow("SELECT COUNT(*) FROM adjusted_candles").Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 3 {
		t.Fatalf("duplicate rows after rebuild: %d", n)
	}
}

func TestVerificationFlagsMismatch(t *testing.T) {
	db := fixture(t)
	if _, err := db.Exec(
		"UPDATE reference_adjusted SET close=51 WHERE date='2026-01-01'"); err != nil {
		t.Fatal(err)
	}
	res, err := Build(db)
	if err != nil {
		t.Fatal(err)
	}
	if res.MismatchRows != 1 || res.ExactRows != 2 {
		t.Fatalf("unexpected result: %+v", res)
	}
	var status string
	if err := db.QueryRow(
		"SELECT status FROM adjustment_verification WHERE date='2026-01-01'").
		Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "DIFF" {
		t.Fatalf("status %q", status)
	}
}

func referenceFixtureDB(t *testing.T) *sql.DB {
	t.Helper()
	db := newDB(t)
	for _, r := range referenceFixtureRaw {
		if _, err := db.Exec("INSERT INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
			referenceFixtureSymbol, r.date, r.open, r.high, r.low, r.close,
			r.volume, "run", "cap"); err != nil {
			t.Fatal(err)
		}
	}
	for d, c := range referenceFixtureAdjustedClose {
		if _, err := db.Exec("INSERT INTO reference_adjusted VALUES(?,?,?,?)",
			referenceFixtureSymbol, d, c, "cap"); err != nil {
			t.Fatal(err)
		}
	}
	for _, f := range referenceFixtureFactors {
		if _, err := db.Exec(
			"INSERT INTO adjustment_factors(symbol,date,ratio,kind,revision,"+
				"capture_sha256) VALUES(?,?,?,?,?,?)",
			referenceFixtureSymbol, f.date, f.ratio, f.kind, f.revision,
			f.capture); err != nil {
			t.Fatal(err)
		}
	}
	return db
}

func TestBuildMatchesReferenceType7(t *testing.T) {
	db := referenceFixtureDB(t)
	if _, err := Build(db); err != nil {
		t.Fatal(err)
	}
	rows, err := db.Query(
		"SELECT date, open, high, low, close, volume, factor FROM adjusted_candles "+
			"WHERE symbol=? ORDER BY date", referenceFixtureSymbol)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	seen := 0
	for rows.Next() {
		var d string
		var o, h, l, c, v, f float64
		if err := rows.Scan(&d, &o, &h, &l, &c, &v, &f); err != nil {
			t.Fatal(err)
		}
		want, ok := referenceFixtureType7[d]
		if !ok {
			t.Fatalf("unexpected date %s", d)
		}
		seen++
		for _, fld := range []struct {
			name      string
			got, want float64
		}{
			{"open", o, want[0]}, {"high", h, want[1]}, {"low", l, want[2]},
			{"close", c, want[3]}, {"volume", v, want[4]},
		} {
			rel := math.Abs(fld.got/fld.want - 1)
			if rel > 1e-9 {
				t.Errorf("%s %s: got %.17g want %.17g (rel %.3g)",
					d, fld.name, fld.got, fld.want, rel)
			}
		}
		if d == "2026-11-10" && f != 1.0 {
			t.Errorf("chain anchor factor = %v, want 1", f)
		}
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if seen != len(referenceFixtureType7) {
		t.Fatalf("materialized %d of %d reference rows",
			seen, len(referenceFixtureType7))
	}
}

func TestBuildCoversZeroEventReferenceSymbol(t *testing.T) {
	db := newDB(t)
	for _, r := range zeroEventRows {
		if _, err := db.Exec("INSERT INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
			zeroEventSymbol, r.date, r.open, r.high, r.low, r.close, r.volume,
			zeroEventRun, zeroEventCapture); err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec("INSERT INTO reference_adjusted VALUES(?,?,?,?)",
			zeroEventSymbol, r.date, r.close, zeroEventCapture); err != nil {
			t.Fatal(err)
		}
	}
	res, err := Build(db)
	if err != nil {
		t.Fatal(err)
	}
	if res.Symbols != 1 || res.AdjustedRows != len(zeroEventRows) {
		t.Fatalf("zero-event reference symbol not materialized: %+v", res)
	}
	if res.ExactRows != len(zeroEventRows) || res.MismatchRows != 0 {
		t.Fatalf("identity chain must verify exact: %+v", res)
	}
	rows, err := db.Query(
		"SELECT date, open, high, low, close, volume, factor, revision "+
			"FROM adjusted_candles WHERE symbol=? ORDER BY date", zeroEventSymbol)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	seen := 0
	for rows.Next() {
		var d, revision string
		var o, h, l, c, v, f float64
		if err := rows.Scan(&d, &o, &h, &l, &c, &v, &f, &revision); err != nil {
			t.Fatal(err)
		}
		if seen >= len(zeroEventRows) {
			t.Fatalf("more rows than the reference carries")
		}
		want := zeroEventRows[seen]
		seen++
		if d != want.date {
			t.Fatalf("date %q, want %q", d, want.date)
		}
		for _, fld := range []struct {
			name      string
			got, want float64
		}{
			{"open", o, want.open}, {"high", h, want.high}, {"low", l, want.low},
			{"close", c, want.close}, {"volume", v, want.volume}, {"factor", f, 1.0},
		} {
			if fld.got != fld.want {
				t.Errorf("%s %s = %v, want %v", d, fld.name, fld.got, fld.want)
			}
		}
		if revision != zeroEventCapture {
			t.Errorf("%s revision = %q, want the capture identity", d, revision)
		}
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if seen != len(zeroEventRows) {
		t.Fatalf("materialized %d of %d rows", seen, len(zeroEventRows))
	}
}
