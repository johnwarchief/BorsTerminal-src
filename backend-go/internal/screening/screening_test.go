package screening

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/store"
)

func TestEligibility(t *testing.T) {
	cases := []struct {
		name   string
		row    map[string]any
		ok     bool
		code   string
		reason string
	}{
		{"stale", map[string]any{"is_live": false, "st_title": "مجاز"}, false, "NOT_LIVE_SESSION", "درِ تازۀترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)"},
		{"stopped", map[string]any{"is_live": true, "stop_state": "متوقف"}, false, "STOPPED", "متوقف: متوقف"},
		{"forbidden", map[string]any{"is_live": true, "st_title": "ممنوع", "st_d": int64(20261014), "st_h": int64(93000)}, false, "FORBIDDEN_STATE", "ممنوع (طی معاملات — ساعت ۰۹:۳۰)"},
		{"stopped-title", map[string]any{"is_live": true, "st_title": "مجاز-متوقف", "st_d": int64(20261013)}, false, "STOPPED", "مجاز-متوقف — از نشستِ ۲۰۲۶۱۰۱۳"},
		{"permitted", map[string]any{"is_live": true, "st_title": "مجاز"}, true, "PERMITTED_STATE", "وضعیتِ ثبت‌شدۀ نماد: مجاز"},
		{"other-title", map[string]any{"is_live": true, "st_title": "محفوظ"}, true, "NO_BLOCKING_STATE", "وتوی معتبری ثبت نشده (وضعیت: محفوظ)"},
		{"none", map[string]any{"is_live": true}, true, "NO_BLOCKING_STATE", "وضعیتی برایِ این نماد ثبت نشده — وتویی نیست"},
	}
	for _, c := range cases {
		ok, code, reason := Eligibility(c.row, 20261014)
		if ok != c.ok || code != c.code || reason != c.reason {
			t.Fatalf("%s: got (%v,%q,%q) want (%v,%q,%q)", c.name, ok, code, reason, c.ok, c.code, c.reason)
		}
	}
}

// TestMissingKeysMatchPythonGet کلیدِ غایب باید مثلِ row.get(...) رفتار کند:
// is_liveِ غایب وتو نمی‌کند (پایتون `row.get("is_live") is False`)، و st_codeِ
// تنها کدِ وضعیت را در علت می‌آورد.
func TestMissingKeysMatchPythonGet(t *testing.T) {
	ok, code, reason := Eligibility(map[string]any{"st_code": "B"}, 20261014)
	if !ok || code != "NO_BLOCKING_STATE" || reason != "وتوی معتبری ثبت نشده (وضعیت: B)" {
		t.Fatalf("code-only row: got (%v,%q,%q)", ok, code, reason)
	}
	ok, code, reason = Eligibility(map[string]any{"is_live": nil, "st_title": "مجاز"}, 20261014)
	if !ok || code != "PERMITTED_STATE" || reason != "وضعیتِ ثبت‌شدۀ نماد: مجاز" {
		t.Fatalf("nil is_live: got (%v,%q,%q)", ok, code, reason)
	}
}

// TestWhitespaceIsTrimmedLikePython str.strip() رویِ عنوان اعمال می‌شود، پس
// برچسبِ «ممنوع» با فاصلۀِ اضافه هم وتو می‌شود و علت عنوانِ تمیزشده را دارد.
func TestWhitespaceIsTrimmedLikePython(t *testing.T) {
	row := map[string]any{
		"is_live": true, "st_title": "  ممنوع  ",
		"st_d": float64(20261014), "st_h": float64(93000),
	}
	ok, code, reason := Eligibility(row, 20261014)
	if ok || code != "FORBIDDEN_STATE" || reason != "ممنوع (طی معاملات — ساعت ۰۹:۳۰)" {
		t.Fatalf("padded title: got (%v,%q,%q)", ok, code, reason)
	}
}

// TestStateReasonFallsBackToDEven وقتی نشستِ جاری صفر است، d_evenِ خودِ ردیف
// مبنا می‌شود (پایتون: `session_day if session_day else row.get("d_even")`).
func TestStateReasonFallsBackToDEven(t *testing.T) {
	row := map[string]any{
		"is_live": true, "st_title": "ممنوع",
		"st_d": float64(20261013), "st_h": int64(90000), "d_even": int64(20261013),
	}
	ok, code, reason := Eligibility(row, 0)
	if ok || code != "FORBIDDEN_STATE" || reason != "ممنوع (طی معاملات — ساعت ۰۹:۰۰)" {
		t.Fatalf("d_even fallback: got (%v,%q,%q)", ok, code, reason)
	}
}

// TestSessionDayBeatsDEven گلدنِ ردیفِ «ممنوع08» را می‌سنجد: st_d در نشستِ
// پیشین ثبت شده (۲۰۲۶۱۰۱۳) ولی نشستِ جاری ۲۰۲۶۱۰۱۴ است، پس برچسب «از نشستِ»
// می‌گیرد نه «طی معاملات».
func TestSessionDayBeatsDEven(t *testing.T) {
	row := map[string]any{
		"is_live": true, "st_title": "ممنوع",
		"st_d": float64(20261013), "st_h": float64(90000), "d_even": int64(20261013),
	}
	ok, code, reason := Eligibility(row, 20261014)
	if ok || code != "FORBIDDEN_STATE" || reason != "ممنوع — از نشستِ ۲۰۲۶۱۰۱۳" {
		t.Fatalf("session day precedence: got (%v,%q,%q)", ok, code, reason)
	}
}

type goldenRow struct {
	Symbol   string `json:"symbol"`
	Eligible bool   `json:"screening_eligible"`
	Code     string `json:"screening_exclusion_code"`
	Reason   string `json:"screening_exclusion_reason"`
}

type goldenBoard struct {
	Data []goldenRow `json:"data"`
	Meta struct {
		DEven int64 `json:"d_even"`
	} `json:"meta"`
}

// TestFixtureVerdictsMatchGolden قوی‌ترین اوراکل است: همان ۳۰ ردیفِ فیکسچر
// با store.LoadBoard خوانده می‌شود و رأیِ هر ردیف با market.json که خودِ پایتون
// ساخته مقایسه می‌شود. گلدن کد/علت را فقط برای ردیفِ ردشده سریال می‌کند
// (api/market.py)، پس برای ردیفِ قبول‌شده فقط bool و نبودِ کلیدهایِ رد سنجیده
// می‌شود.
func TestFixtureVerdictsMatchGolden(t *testing.T) {
	fr, d := fixtureFrame(t)
	gold := readGolden(t)
	if fr.N() != 30 || len(gold.Data) != 30 {
		t.Fatalf("rows = frame %d، golden %d; want 30 both", fr.N(), len(gold.Data))
	}
	if gold.Meta.DEven == 0 {
		t.Fatal("golden meta.d_even is missing; session day is unknown")
	}
	bySymbol := make(map[string]goldenRow, len(gold.Data))
	for _, g := range gold.Data {
		bySymbol[g.Symbol] = g
	}
	seen := make(map[string]bool, len(gold.Data))
	excluded := 0
	for i := 0; i < fr.N(); i++ {
		sym, ok := fr.Cols["symbol"][i].(string)
		if !ok {
			t.Fatalf("row %d: symbol has Go type %T", i, fr.Cols["symbol"][i])
		}
		g, ok := bySymbol[sym]
		if !ok {
			t.Fatalf("symbol %q is not in the golden", sym)
		}
		seen[sym] = true
		gotOK, gotCode, gotReason := Eligibility(goldenRecord(fr, d.IsLive[i], i), gold.Meta.DEven)
		if gotOK != g.Eligible {
			t.Errorf("%s: eligible = %v، golden %v", sym, gotOK, g.Eligible)
		}
		if g.Eligible {
			if g.Code != "" || g.Reason != "" {
				t.Errorf("%s: golden carries exclusion code/reason for an eligible row", sym)
			}
			continue
		}
		if gotCode != g.Code || gotReason != g.Reason {
			t.Errorf("%s: got (%q، %q)، golden (%q، %q)", sym, gotCode, gotReason, g.Code, g.Reason)
		}
		excluded++
	}
	if len(seen) != 30 {
		t.Fatalf("matched %d symbols، want 30", len(seen))
	}
	// فیکسچر قصداً هر وتو را دارد: کهنه (سخت05)، تعلیقِ صریح (متوقف07)،
	// «ممنوع» (ممنوع08) و «متوقف» در عنوان (پول‌هوشمند06).
	if excluded != 4 {
		t.Fatalf("golden excluded rows = %d، want 4 (one per veto path)", excluded)
	}
}

// goldenRecord رکوردِ سریال‌شده را از قاب می‌سازد: کلیدهایِ NULL غایب‌اند
// (همان _slim_recordsِ پایتون) و is_live از مشتقِ board می‌آید.
func goldenRecord(fr *store.Frame, live bool, i int) map[string]any {
	rec := make(map[string]any, 8)
	for _, k := range []string{"st_title", "st_code", "st_d", "st_h", "stop_state", "d_even"} {
		vals := fr.Cols[k]
		if i < len(vals) && vals[i] != nil {
			rec[k] = vals[i]
		}
	}
	rec["is_live"] = live
	return rec
}

// fixtureFrame فیکسچرِ مخزن را در t.TempDir() کپی می‌کند؛ بانکِ عملیاتیِ کاربر
// هرگز باز نمی‌شود و تست چیزی در مخزن نمی‌نویسد.
func fixtureFrame(t *testing.T) (*store.Frame, *board.Derived) {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
	if err != nil {
		t.Fatal(err)
	}
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	fr, err := store.LoadBoard(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	return fr, board.Derive(fr)
}

func readGolden(t *testing.T) goldenBoard {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("..", "board", "testdata", "golden", "market.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g goldenBoard
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("golden/market.json: %v", err)
	}
	return g
}
