package tapehistory

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"strings"
	"testing"

	"borsterminal/backend/internal/parity"
	"borsterminal/backend/internal/period"
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
	// internal/market همان پوشش را رویِ سیم می‌سنجد، اینجا بدنه مقایسه می‌شود.
	// پیش‌تر همین‌جا `got["status"] = "success"` ساخته می‌شد و به‌همین‌دلیل این
	// فیلد هرگز سنجیده نمی‌شد؛ حالا status از هر دو سو کنار گذاشته می‌شود و
	// جداگانه برایش شاهدِ مثبت می‌گیریم.
	if s, ok := want["status"]; !ok || s != "success" {
		t.Errorf("%s: golden status = %#v (present=%v), want \"success\"", label, s, ok)
	}
	// و سمتِ Go هم باید بی‌status باشد: این فیلد کارِ مسیر است، نه history_for.
	if _, ok := got["status"]; ok {
		t.Errorf("%s: HistoryFor invented a status field: %v", label, got["status"])
	}
	body, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	var norm map[string]any
	if err := json.Unmarshal(body, &norm); err != nil {
		t.Fatal(err)
	}
	res := parity.Compare(want, norm, parity.Options{Exclude: []string{"status"}})
	// اگر مسیرِ status یک‌روزه عوض شود، Exclude بی‌صدا بی‌اثر می‌شود؛ همان‌جا
	// باید قرمز دیده شود، نه درِ مقایسهٔ بعدی.
	if !slices.Contains(res.Excluded, "status") {
		t.Errorf("%s: status was not actually excluded from the diff", label)
	}
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

// pyStrippedRunes آن نویسه‌هایی‌اند که `.strip()`ِ پایتون از دو سر می‌چیند
// (Py_UNICODE_ISSPACE) — فهرستِ اندازه‌گیری‌شده با اوراکلِ واقعی: هر x.strip()==""
// برای همین‌ها درست است و U+001C..U+001F هم درِ فهرست است؛ strings.TrimSpaceِ Go
// همین چهار تا را نمی‌چیند و به‌همین‌دلیل period.Trim اینجا الزامی است.
var pyStrippedRunes = []rune{
	0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f, 0x20,
	0x85, 0xa0, 0x1680, 0x2000, 0x200a, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
}

// pyNonStrippedRunes نویسه‌هایی‌اند که پایتون *نمی‌چیند*؛ اگر Go یکی‌شان را
// بچیند، Go جلوتر از اوراکل رفته است (U+200B زیرِ قاعدۀ .strip() نیست).
var pyNonStrippedRunes = []rune{0x00, 0x200b, 0x2060, 0xfeff}

// TestParseCodesMatchesPythonStrip باگِ A: `[s.strip() for s in codes.split(",")
// if s.strip()]` درِ api/market.py — با TrimSpace، کدِ آلوده به U+001C همان‌طور
// کثیف می‌ماند و پارامترِ `IN (?)` هیچ ردیفی را نمی‌بیند.
func TestParseCodesMatchesPythonStrip(t *testing.T) {
	// متنِ خامِ زیر عیناً به اوراکلِ پایتون داده شد و همین فهرست برگشت:
	//   ['INS-1', 'INS-2']
	raw := "\x1cINS-1, \x1d ,INS-2\x1f,\x1e\x1f"
	want := []string{"INS-1", "INS-2"}
	got := ParseCodes(raw)
	if strings.Join(got, "|") != strings.Join(want, "|") {
		t.Errorf("ParseCodes(%q) = %q, python oracle %q", raw, got, want)
	}
	// شاهدِ همان شکافِ دو زبان: TrimSpaceِ Go این چهار تا را نمی‌چیند، پس با
	// TrimSpace کیسِ بالا قطعا کثیف می‌ماند.
	for r := 0x1c; r <= 0x1f; r++ {
		if strings.TrimSpace(string(rune(r))) == "" {
			t.Errorf("expected TrimSpace to leave U+%04X alone (that is the bug)", r)
		}
	}
	// قاعدۀ دو زبان باید یکی باشد: هر چه پایتون می‌چیند اینجا هم چیده شود…
	for _, r := range pyStrippedRunes {
		pad := string(r)
		if out := ParseCodes(pad + "INS-X" + pad); len(out) != 1 || out[0] != "INS-X" {
			t.Errorf("U+%04X: ParseCodes = %q want [INS-X]", r, out)
		}
		// و رشته‌ای که پایتون «فقط فاصله» می‌بیند و دور می‌اندازد (`if s.strip()`)
		// نباید به کلیدِ تهی تبدیل شود.
		if out := ParseCodes("A," + pad + ",B"); len(out) != 2 || out[0] != "A" || out[1] != "B" {
			t.Errorf("U+%04X: ParseCodes = %q want [A B]", r, out)
		}
		if out := period.Trim(pad + "INS-X" + pad); out != "INS-X" {
			t.Errorf("U+%04X: period.Trim = %q want INS-X", r, out)
		}
	}
	// …و هیچ نویسۀ دیگری نباید چیده شود.
	for _, r := range pyNonStrippedRunes {
		if out := ParseCodes(string(r) + "INS-X"); len(out) != 1 || out[0] != string(r)+"INS-X" {
			t.Errorf("U+%04X must not be stripped by Python: ParseCodes = %q", r, out)
		}
	}
}

// TestPaddedCodeKeyIsCleanAndStillMatches باگِ A از سوِ پیامد: کلیدِ by_symbol
// پاکیزه می‌ماند و ردیف‌های واقعی همان نماد دیده می‌شوند. با TrimSpace کلید کثیف
// می‌ماند، IN (?) نمی‌خواند و همۀ روزها «غیرفعال» می‌شدند.
func TestPaddedCodeKeyIsCleanAndStillMatches(t *testing.T) {
	ctx := context.Background()
	clean := symbolKeys(golden(t, "s1", "tape_one_day"))[0]
	got := readerFor(openUser(t, nil)).HistoryFor(ctx, ParseCodes("\x1c"+clean), ClampDays(1))
	by, _ := got["by_symbol"].(map[string]any)
	if len(by) != 1 {
		t.Fatalf("by_symbol has %d keys, want exactly 1 (%q leaked?)", len(by), "\x1c"+clean)
	}
	if _, ok := by[clean]; !ok {
		t.Fatalf("dirty key leaked into by_symbol: %v", symbolKeys(got))
	}
	// و پاسخ با همان نمادِ بی‌پدینگ باید بیت‌به‌bit یکی باشد — یعنی کوئری
	// واقعاً ردیف‌ها را پیدا کرده است (طلاییِ tape_one_day همان days=1 است).
	plain := readerFor(openUser(t, nil)).HistoryFor(ctx, ParseCodes(clean), ClampDays(1))
	compare(t, "padded-vs-plain", golden(t, "s1", "tape_one_day"), got)
	compare(t, "plain", golden(t, "s1", "tape_one_day"), plain)
	if _, ok := plain["status"]; ok {
		t.Errorf("HistoryFor must not invent a status field: %v", plain["status"])
	}
}

// pyEvidenceOracle خروجی‌های واقعیِ `tape_flag_history.history_for` برایِ نه
// ورودیِ ستونِ evidence است — اوراکل در tempِ in-memory SQLite اجرا شد و همین
// متن‌ها چاپ شد (بندِ B گزارش). ستونِ «ورودی» متنِ خامِ همان ردیف است و
// pyJSON همان json.dumpsِ مقدارِ برگشتی؛ فاصله‌های چاپِ پایتون («", "» و ": "»)
// را حذف کرده‌ایم چون هیچ رشته‌ای با فاصله در این نمونه‌ها نیست و Go متنِ
// فشرده می‌نویسد.
var pyEvidenceOracle = []struct {
	code, column, pyJSON string
}{
	{"INS-B0", "null", "null"},
	{"INS-B1", "9007199254740993", "9007199254740993"},
	{"INS-B2", `{"n": 9007199254740993, "ratio": 3.4}`, `{"n":9007199254740993,"ratio":3.4}`},
	{"INS-B3", "{not json at all", "{}"},
	{"INS-B4", "", "{}"},
	{"INS-B5", "\x00NULL", "{}"}, // NULLِ واقعیِ SQL (نه رشته)
	{"INS-B6", `{"a": 1} {"b": 2}`, "{}"},
	{"INS-B7", `{"a": 1}  `, `{"a":1}`},
	{"INS-B8", "   ", "{}"},
}

// TestDecodeEvidenceMatchesPythonJSON باگِ B: `json.loads(evidence) if evidence
// else {}` هیچ شاخۀ «null ⇒ {}» ندارد و عددِ صحیحِ درشت را هم حفظ می‌کند.
func TestDecodeEvidenceMatchesPythonJSON(t *testing.T) {
	ctx := context.Background()
	db := openUser(t, func(d *sql.DB) {
		for _, c := range pyEvidenceOracle {
			var ev any = c.column
			if c.column == "\x00NULL" {
				ev = nil
			}
			_, err := d.Exec("INSERT INTO tape_flag_day(ins_code, flag, d_even, symbol,"+
				" first_seen_at, last_seen_at, passes, evidence, source)"+
				" VALUES(?,?,?,?,?,?,?,?,?)",
				c.code, "f_jet", 20261028, "probe", "09:00:00", "12:00:00", 1, ev, "probe")
			if err != nil {
				t.Fatalf("seed %s: %v", c.code, err)
			}
		}
	})
	codes := make([]string, 0, len(pyEvidenceOracle))
	for _, c := range pyEvidenceOracle {
		codes = append(codes, c.code)
	}
	body := readerFor(db).HistoryFor(ctx, ParseCodes(strings.Join(codes, ",")), ClampDays(20))
	by, _ := body["by_symbol"].(map[string]any)
	for _, c := range pyEvidenceOracle {
		per, _ := by[c.code].(map[string]any)
		f, _ := per["f_jet"].(map[string]any)
		cell, _ := f["days"].(map[string]any)["20261028"].(map[string]any)
		if cell == nil {
			t.Errorf("%s: no day cell for evidence %q", c.code, c.column)
			continue
		}
		raw, err := json.Marshal(cell["evidence"])
		if err != nil {
			t.Errorf("%s: marshal evidence: %v", c.code, err)
			continue
		}
		t.Logf("evidence %-24q  python=%-26s go=%s", c.column, c.pyJSON, raw)
		if string(raw) != c.pyJSON {
			t.Errorf("%s: evidence %q -> go %s, python oracle %s", c.code, c.column, raw, c.pyJSON)
		}
	}
	// دو شاهدِ ساختاری روی همان دو کیسی که باگِ B می‌ساخت:
	per := by["INS-B0"].(map[string]any)["f_jet"].(map[string]any)
	if v := per["days"].(map[string]any)["20261028"].(map[string]any)["evidence"]; v != nil {
		t.Errorf("`null` must stay null on the wire, got %#v", v)
	}
	perBig := by["INS-B1"].(map[string]any)["f_jet"].(map[string]any)
	if v, ok := perBig["days"].(map[string]any)["20261028"].(map[string]any)["evidence"]; !ok || v == nil {
		t.Errorf("big integer scalar vanished: %#v", v)
	} else if n, isNum := v.(json.Number); !isNum || n.String() != "9007199254740993" {
		// float64 این عدد را نمی‌تواند نگه دارد؛ json.Number یعنی رقم‌ها نروختند.
		t.Errorf("big integer must survive as an exact number, got %#v (%T)", v, v)
	}
}

// TestTradingDaysIsAllOrNothing باگِ C: `fetchall()`ِ پایتون یا همه ردیف‌ها را
// می‌دهد یا sqlite3.Error ⇒ فهرستِ خالی؛ نیمه‌فهرست هیچ‌جا درِ اوراکل تولید
// نمی‌شود. اینجا تقویم را با ردیفی که Scanِ Go را می‌شکند آلوده می‌کنیم تا
// همان مسیرِ نیمه‌فهرست باز شود.
func TestTradingDaysIsAllOrNothing(t *testing.T) {
	ctx := context.Background()
	db := openUser(t, func(d *sql.DB) {
		// DDL واقعی جدولِ meta ستونِ INTEGER PRIMARY KEY دارد و 'abc' را با
		// IntegrityError رد می‌کند (این را اوراکل سنجید)؛ پس برای رسیدن به
		// ستونی که ارزشِ خواندنی‌اش int نیست، همان نامِ جدول را بی‌affinity
		// می‌سازیم — تنها راهِ قطعیِ شکستنِ Scan در حلقه.
		if _, err := d.Exec("DROP TABLE tape_flag_day_meta"); err != nil {
			t.Fatal(err)
		}
		if _, err := d.Exec("CREATE TABLE tape_flag_day_meta" +
			"(d_even, first_at, last_at, passes, symbols, active_rows)"); err != nil {
			t.Fatal(err)
		}
		for _, v := range []any{20261028, 20261027, nil} {
			if _, err := d.Exec("INSERT INTO tape_flag_day_meta VALUES(?,?,?,?,?,?)",
				v, "a", "b", 1, 1, 1); err != nil {
				t.Fatal(err)
			}
		}
	})
	r := readerFor(db)
	// ردیفِ NULL در DESC *آخر* می‌نشیند، پس نیمه‌فهرستِ قبلی [20261028 20261027]
	// بود: دو روز واقعیِ ثبت‌شده که گم می‌شدند و بقیهٔ روزها «ثبت‌نشده» خوانده
	// می‌شدند. حالا یا همه، یا هیچ.
	if days := r.TradingDays(ctx, 20); len(days) != 0 {
		t.Errorf("TradingDays = %v, want empty calendar (partial list is the bug)", days)
	}
	body := r.HistoryFor(ctx, ParseCodes("INS-1"), ClampDays(20))
	if got := body["days"]; fmt.Sprint(got) != "[]" {
		t.Errorf("body days = %v, want []", got)
	}
	if by, _ := body["by_symbol"].(map[string]any); len(by) != 0 {
		t.Errorf("empty calendar must give the empty body, got %v", symbolKeys(body))
	}
	if raw, err := json.Marshal(body["days"]); err != nil || string(raw) != "[]" {
		t.Errorf("days on the wire = %s (err %v), want []", raw, err)
	}
}
