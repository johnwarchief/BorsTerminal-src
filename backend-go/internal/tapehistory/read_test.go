package tapehistory

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"borsterminal/backend/internal/parity"
)

// فیکسچر و طلایی‌هایِ B4 یک‌جا زندگی می‌کنند (تسکِ ۱: پوشۀ internal/fundamental)
// و هر دو خواننده از همان کپی می‌خورند؛ یکِ فیکسچر، یکِ اوراکل، دو مصرف‌کننده.
const (
	fixtureUser = "../fundamental/testdata/fixture/user.db"
	goldenRoot  = "../fundamental/testdata/golden"
)

func openUser(t *testing.T, mutate func(*sql.DB)) *sql.DB {
	t.Helper()
	raw, err := os.ReadFile(fixtureUser)
	if err != nil {
		t.Fatalf("B4 fixture is missing (%s): %v", fixtureUser, err)
	}
	path := filepath.Join(t.TempDir(), "user.db")
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	db.SetMaxOpenConns(2)
	t.Cleanup(func() { _ = db.Close() })
	if mutate != nil {
		mutate(db)
	}
	return db
}

func golden(t *testing.T, scenario, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(goldenRoot, scenario, name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func symbolKeys(v map[string]any) []string {
	by, _ := v["by_symbol"].(map[string]any)
	out := make([]string, 0, len(by))
	for k := range by {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func compare(t *testing.T, label string, want map[string]any, got map[string]any) {
	t.Helper()
	// `history_for` درِ پایتون هم بدنه را بی‌`status` می‌دهد و مسیر
	// `dict(status="success", **body)` آن را می‌چسباند؛ آزمونِ هندلر درِ
	// internal/market همان پوشش را می‌سنجد، اینجا بدنه مقایسه می‌شود.
	got["status"] = "success"
	body, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	var norm map[string]any
	if err := json.Unmarshal(body, &norm); err != nil {
		t.Fatal(err)
	}
	res := parity.Compare(want, norm, parity.Options{})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", label, d)
		}
	}
}

func readerFor(db *sql.DB) *Reader {
	return NewReader(db, func() string { return "" })
}

// TestTapeGoldens هفت کیسِ s1 و دو کیسِ s3 — پاسخِ Go با بدنه‌ای که اوراکلِ
// پایتون رویِ همان فیکسچر نوشته مقایسه می‌شود.
func TestTapeGoldens(t *testing.T) {
	ctx := context.Background()
	db := openUser(t, nil)

	four := golden(t, "s1", "tape_four")
	fourCodes := symbolKeys(four)
	if len(fourCodes) != 3 {
		t.Fatalf("tape_four carries %d symbols, want 3", len(fourCodes))
	}
	one := golden(t, "s1", "tape_one_day")
	upCodes := symbolKeys(one)
	if len(upCodes) != 1 {
		t.Fatalf("tape_one_day carries %d symbols, want 1", len(upCodes))
	}
	unknown := symbolKeys(golden(t, "s1", "tape_unknown_code"))
	if len(unknown) != 1 {
		t.Fatalf("tape_unknown_code must echo the requested code back")
	}

	compare(t, "tape_four", four, readerFor(db).HistoryFor(ctx, fourCodes, ClampDays(20)))
	compare(t, "tape_all", golden(t, "s1", "tape_all"),
		readerFor(db).HistoryFor(ctx, ParseCodes(""), ClampDays(20)))
	compare(t, "tape_one_day", one, readerFor(db).HistoryFor(ctx, upCodes, ClampDays(1)))
	compare(t, "tape_clamp_days", golden(t, "s1", "tape_clamp_days"),
		readerFor(db).HistoryFor(ctx, upCodes, ClampDays(9999)))
	compare(t, "tape_zero_days", golden(t, "s1", "tape_zero_days"),
		readerFor(db).HistoryFor(ctx, upCodes, ClampDays(0)))
	compare(t, "tape_unknown_code", golden(t, "s1", "tape_unknown_code"),
		readerFor(db).HistoryFor(ctx, unknown, ClampDays(20)))
	cap500 := make([]string, 0, 500)
	for i := 0; i < 500; i++ {
		cap500 = append(cap500, upCodes[0])
	}
	compare(t, "tape_cap_codes", golden(t, "s1", "tape_cap_codes"),
		readerFor(db).HistoryFor(ctx, cap500, ClampDays(20)))

	// s3/۱: جدول‌ها نیستند. پایتون با ensure می‌سازد و بعد می‌خواند؛ Go درِ فازِ A
	// نمی‌نویسد و همان بدنهٔ خالی را بی‌ساختن می‌دهد (تفاوتِ اعلام‌شده، بدنه یکی).
	noTables := openUser(t, func(d *sql.DB) {
		for _, tbl := range []string{"tape_flag_day", "tape_flag_day_meta"} {
			if _, err := d.Exec("DROP TABLE IF EXISTS " + tbl); err != nil {
				t.Fatal(err)
			}
		}
	})
	compare(t, "s3/tape_missing_tables", golden(t, "s3", "tape_missing_tables"),
		readerFor(noTables).HistoryFor(ctx, fourCodes, ClampDays(20)))

	// s3/۲: جدول هست، تقویم خالی.
	emptyMeta := openUser(t, func(d *sql.DB) {
		if _, err := d.Exec("DELETE FROM tape_flag_day_meta"); err != nil {
			t.Fatal(err)
		}
	})
	compare(t, "s3/tape_empty_meta", golden(t, "s3", "tape_empty_meta"),
		readerFor(emptyMeta).HistoryFor(ctx, upCodes, ClampDays(20)))
}

// TestDayKeysAreStrings شاهدِ زندهٔ ۱۴۰۵-۰۷-۲۱: orjson کلیدِ عددی را رد می‌کند و
// مسیر ۵۰۰ می‌داد. درِ Go هم کلیدها باید رشته بمانند (نه عدد) — این را از متنِ
// خامِ JSON می‌خوانیم، نه از نوعِ داده‌شده.
func TestDayKeysAreStrings(t *testing.T) {
	ctx := context.Background()
	body := readerFor(openUser(t, nil)).HistoryFor(ctx, ParseCodes("ISIN-NOT-HERE"), ClampDays(20))
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatal(err)
	}
	s := string(raw)
	if !strings.Contains(s, `"20261025":`) {
		t.Errorf("day keys are not quoted strings: %s", s)
	}
	// کلیدِ عددی رویِ سیم یعنی همان ۵۰۰ِ orjson برگشته است.
	if strings.Contains(s, `:{2026`) || strings.Contains(s, `,{2026`) {
		t.Errorf("numeric day key leaked into the wire: %s", s)
	}
}

// TestInactiveIsNotUnrecorded: روزی که درِ تقویم هست و ردیفی ندارد «غیرفعال»
// است؛ روزی که درِ تقویم نیست «ثبت نشده» — این دو هرگز یکی نمی‌شوند.
func TestInactiveIsNotUnrecorded(t *testing.T) {
	ctx := context.Background()
	got := readerFor(openUser(t, nil)).HistoryFor(ctx, ParseCodes("ISIN-NOT-HERE"), ClampDays(20))
	by, _ := got["by_symbol"].(map[string]any)
	per, _ := by["ISIN-NOT-HERE"].(map[string]any)
	if len(per) != len(Flags) {
		t.Fatalf("flags = %d want %d", len(per), len(Flags))
	}
	f, _ := per["f_jet"].(map[string]any)
	days, _ := f["days"].(map[string]any)
	want := golden(t, "s1", "tape_unknown_code")
	wantDays := (want["by_symbol"].(map[string]any)["ISIN-NOT-HERE"].(map[string]any)["f_jet"].(map[string]any))["days"].(map[string]any)
	if len(days) != len(wantDays) {
		t.Fatalf("days = %d want %d", len(days), len(wantDays))
	}
	for k, v := range days {
		cell, _ := v.(map[string]any)
		if cell["active"] != false {
			t.Errorf("placeholder day %s must be active:false", k)
		}
		if pw := wantDays[k].(map[string]any); pw["passes"] != float64(0) {
			t.Errorf("golden placeholder passes for %s is not 0", k)
		}
	}
	// و یکِ ردیفِ واقعاً ثبت‌شده باید active:true بماند (placeholder بازنویسی‌اش نکند).
	live := readerFor(openUser(t, nil)).HistoryFor(ctx, ParseCodes("INS-عادی01"), ClampDays(20))
	liveBy, _ := live["by_symbol"].(map[string]any)
	anyActive := false
	for _, per := range liveBy {
		p, _ := per.(map[string]any)
		for _, fl := range p {
			fm, _ := fl.(map[string]any)
			dm, _ := fm["days"].(map[string]any)
			for _, c := range dm {
				cm, _ := c.(map[string]any)
				if cm["active"] == true {
					anyActive = true
				}
			}
		}
	}
	if !anyActive {
		t.Error("the watched symbol must still show active days — the placeholder loop ate them")
	}
}

func TestParseCodesAndClamp(t *testing.T) {
	if got := ParseCodes(" a , ,b,  c "); len(got) != 3 || got[0] != "a" || got[2] != "c" {
		t.Errorf("ParseCodes = %q", got)
	}
	if got := ParseCodes(strings.Repeat("x,", 500)); len(got) != 400 {
		t.Errorf("codes cap = %d want 400", len(got))
	}
	for _, c := range []struct{ in, want int }{{0, 20}, {-5, 1}, {1, 1}, {9999, 120}, {20, 20}} {
		if got := ClampDays(c.in); got != c.want {
			t.Errorf("ClampDays(%d) = %d want %d", c.in, got, c.want)
		}
	}
}
