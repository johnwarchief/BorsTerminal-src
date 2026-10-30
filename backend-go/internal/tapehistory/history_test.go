package tapehistory

import (
	"database/sql"
	"math"
	"path/filepath"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func openDB(t *testing.T) *sql.DB {
	t.Helper()
	conn, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "user.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

func rec(code string, live bool, on map[string]bool, ev map[string]any) map[string]any {
	m := map[string]any{"ins_code": code, "symbol": code + "-sym", "is_live": live}
	for _, f := range Flags {
		m[f] = on[f]
	}
	for k, v := range ev {
		m[k] = v
	}
	return m
}

func baseRecs() []map[string]any {
	return []map[string]any{
		rec("A", true, map[string]bool{"f_susp": true, "f_jet": true},
			map[string]any{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": int64(42)}),
		rec("B", true, map[string]bool{"f_jet": true},
			map[string]any{"tvol": 2000.0, "p_closing": 100.0, "is6": 1.0}),
		rec("C", false, map[string]bool{"f_susp": true}, nil),
	}
}

func count(t *testing.T, conn *sql.DB, q string, args ...any) int {
	t.Helper()
	var n int
	if err := conn.QueryRow(q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestRecordWritesDailyRowsAndMeta(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	now := time.Date(2026, 10, 14, 10, 30, 0, 0, time.Local)

	if n, err := r.Record(conn, baseRecs(), 20261014, "tok-1", now); err != nil || n != 3 {
		t.Fatalf("n=%d err=%v, want 3 rows", n, err)
	}
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day"); got != 3 {
		t.Fatalf("tape_flag_day rows=%d, want 3", got)
	}
	var first, last, ev, src string
	var passes int
	err := conn.QueryRow("SELECT first_seen_at, last_seen_at, passes, evidence, source"+
		" FROM tape_flag_day WHERE ins_code='A' AND flag='f_jet'").Scan(&first, &last, &passes, &ev, &src)
	if err != nil {
		t.Fatal(err)
	}
	if first != "2026-10-14 10:30:00" || last != first || passes != 1 || src != "board" {
		t.Fatalf("first=%q last=%q passes=%d src=%q", first, last, passes, src)
	}
	wantEv := `{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": 42}`
	if ev != wantEv {
		t.Fatalf("evidence=%s, want %s", ev, wantEv)
	}
	var sym string
	if err := conn.QueryRow("SELECT symbol FROM tape_flag_day WHERE ins_code='B' AND flag='f_jet'").Scan(&sym); err != nil {
		t.Fatal(err)
	}
	if sym != "B-sym" {
		t.Fatalf("symbol=%q", sym)
	}
	var metaPasses, symbols int
	if err := conn.QueryRow("SELECT passes, symbols FROM tape_flag_day_meta WHERE d_even=20261014").
		Scan(&metaPasses, &symbols); err != nil {
		t.Fatal(err)
	}
	if metaPasses != 1 || symbols != 2 {
		t.Fatalf("meta passes=%d symbols=%d, want 1 and 2", metaPasses, symbols)
	}
	// ردیف‌های بی‌پرچم و بی‌جان هیچ ردیفی نمی‌سازند.
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day WHERE ins_code='C'"); got != 0 {
		t.Fatalf("fossil row C was written (%d rows)", got)
	}
}

func TestTokenBlocksRepeatAndKeepsFirstSight(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 10, 30, 0, 0, time.Local)
	if _, err := r.Record(conn, baseRecs(), 20261014, "tok-1", t0); err != nil {
		t.Fatal(err)
	}
	// همان نشانه، حتی بعد از پنجرهٔ چهار دقیقه‌ای: نوبتِ تازه‌ای نیست.
	if n, _ := r.Record(conn, baseRecs(), 20261014, "tok-1", t0.Add(30*time.Minute)); n != 0 {
		t.Fatalf("same token wrote %d rows", n)
	}
	// نشانهٔ تازه پس از پنجره: passes جلو می‌رود، ولی شاهد و اولین‌دید عوض نمی‌شوند.
	changed := baseRecs()
	changed[0]["p_closing"] = 999.9
	if n, err := r.Record(conn, changed, 20261014, "tok-2", t0.Add(5*time.Minute)); err != nil || n != 3 {
		t.Fatalf("n=%d err=%v, want 3", n, err)
	}
	var first, ev string
	var passes int
	if err := conn.QueryRow("SELECT first_seen_at, passes, evidence FROM tape_flag_day"+
		" WHERE ins_code='A' AND flag='f_susp'").Scan(&first, &passes, &ev); err != nil {
		t.Fatal(err)
	}
	if first != "2026-10-14 10:30:00" || passes != 2 {
		t.Fatalf("first=%q passes=%d", first, passes)
	}
	if ev != `{"tvol": 1000.0, "p_closing": 500.5, "z_tot_tran": 42}` {
		t.Fatalf("evidence was rewritten: %s", ev)
	}
	if got := count(t, conn, "SELECT passes FROM tape_flag_day_meta WHERE d_even=20261014"); got != 2 {
		t.Fatalf("meta passes=%d, want 2", got)
	}
}

func TestFlushFloor(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	if _, err := r.Record(conn, baseRecs(), 20261014, "t1", t0); err != nil {
		t.Fatal(err)
	}
	if n, _ := r.Record(conn, baseRecs(), 20261014, "t2", t0.Add(10*time.Second)); n != 0 {
		t.Fatalf("flush floor leaked: %d rows", n)
	}
	if n, err := r.Record(conn, baseRecs(), 20261014, "t2", t0.Add(241*time.Second)); err != nil || n != 3 {
		t.Fatalf("after the floor n=%d err=%v, want 3", n, err)
	}
}

func TestNoLiveRowsConsumesTheWindow(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	fossil := []map[string]any{rec("C", false, map[string]bool{"f_susp": true}, nil)}
	if n, _ := r.Record(conn, fossil, 20261014, "x", t0); n != 0 {
		t.Fatalf("fossil-only frame wrote %d rows", n)
	}
	if got := count(t, conn, "SELECT COUNT(*) FROM tape_flag_day_meta"); got != 0 {
		t.Fatalf("meta row written without observations (%d)", got)
	}
	// عینِ پایتون: نشانه پیش از ساختنِ ردیف‌ها ثبت می‌شود، پس نوبتِ بعدی با همان
	// نشانه — حتی اگر ردیفِ زنده داشته باشد — تا پنجرهٔ بعدی ثبت نمی‌شود.
	if n, _ := r.Record(conn, baseRecs(), 20261014, "x", t0.Add(time.Minute)); n != 0 {
		t.Fatalf("token was not consumed by the empty batch (%d rows)", n)
	}
}

func TestEvidenceDropsMissingNaNAndInf(t *testing.T) {
	conn := openDB(t)
	r := NewRecorder()
	t0 := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	recs := []map[string]any{rec("A", true, map[string]bool{"f_jet": true}, map[string]any{
		"tvol": 1.0, "p_closing": math.NaN(), "p_last": math.Inf(1),
		"percent_last": nil, "z_tot_tran": int64(7),
	})}
	if _, err := r.Record(conn, recs, 20261014, "t", t0); err != nil {
		t.Fatal(err)
	}
	var ev string
	if err := conn.QueryRow("SELECT evidence FROM tape_flag_day WHERE ins_code='A'").Scan(&ev); err != nil {
		t.Fatal(err)
	}
	want := `{"tvol": 1.0, "z_tot_tran": 7}`
	if ev != want {
		t.Fatalf("evidence=%s, want %s", ev, want)
	}
}

func TestFailureIsSwallowedAndReported(t *testing.T) {
	conn := openDB(t)
	conn.Close()
	r := NewRecorder()
	now := time.Date(2026, 10, 14, 9, 0, 0, 0, time.Local)
	if n, err := r.Record(conn, baseRecs(), 20261014, "t", now); n != 0 || err == nil {
		t.Fatalf("closed db: n=%d err=%v", n, err)
	}
	if r.LastErr() == "" {
		t.Fatal("LastErr is empty after a failed write")
	}
}

// TestPyFloatMatchesPythonRepr مرزِ نمادِ اعشاری/توان را قفل می‌کند. قالبِ 'g'ِ
// Go از هفت رقمِ معنی‌دار به توان می‌افتد و پایتون تا شانزده رقم اعشاری می‌نویسد؛
// شاهدِ tvol/turnover عددهایِ چندمیلیونی است، پس بدونِ این تفکیک متنِ evidence
// با پایتون یکی نمی‌ماند. مقادیرِ انتظار خروجیِ repr در پایتونِ همین ماشین‌اند.
func TestPyFloatMatchesPythonRepr(t *testing.T) {
	// متغیر، نه ثابتِ تایپ‌شده: جمعِ ثابت‌ها در Go دقیق حساب می‌شود و 0.3ِ
	// گردشده می‌دهد، ولی پایتون جمعِ دو float64ِ واقعی را می‌نویسد.
	tenth, fifth := 0.1, 0.2
	cases := []struct {
		in   float64
		want string
	}{
		{1000.0, "1000.0"},
		{500.5, "500.5"},
		{1.0, "1.0"},
		{999999.0, "999999.0"},
		{1234567.0, "1234567.0"},
		{12345678.0, "12345678.0"},
		{123456789012.0, "123456789012.0"},
		{1e15, "1000000000000000.0"},
		{1e16, "1e+16"},
		{1e-4, "0.0001"},
		{1e-5, "1e-05"},
		{1.5e-5, "1.5e-05"},
		{0.000123456, "0.000123456"},
		{tenth + fifth, "0.30000000000000004"},
		{math.Copysign(0, -1), "-0.0"},
	}
	for _, c := range cases {
		if got := pyFloat(c.in); got != c.want {
			t.Fatalf("pyFloat(%v) = %q, want %q", c.in, got, c.want)
		}
	}
}
