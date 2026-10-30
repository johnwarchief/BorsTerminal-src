package mstat

import (
	"encoding/json"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/market"
)

type stubFlags struct {
	m  map[string]map[string]bool
	ok bool
}

func (s stubFlags) TapeFlags() (map[string]map[string]bool, bool) { return s.m, s.ok }

// marketFlags همان منبعِ واقعیِ پرچم‌هاست: کشِ /api/market رویِ همین فیکسچر.
// امضایِ (map, ok) عینِ TapeFlags است (R7).
func marketFlags(h *db.Handles) (map[string]map[string]bool, bool) {
	svc := market.New(h, "")
	return svc.TapeFlags()
}

func flagKeys() []string {
	return []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}
}

// rowsOf بدنهٔ rows را با بررسیِ نوع برمی‌گرداند؛ تغییرِ شکلِ بدنه باید شکستِ
// نام‌دار بدهد، نه پنیکِ اَسِرشنِ بدونِ ok.
func rowsOf(t *testing.T, got map[string]any) []map[string]any {
	t.Helper()
	rows, ok := got["rows"].([]map[string]any)
	if !ok {
		t.Fatalf("rows type = %T, want []map[string]any", got["rows"])
	}
	return rows
}

// rowSymbols ترتیبِ نمادهایِ بدنه را می‌دهد؛ پنل []map[string]any برمی‌گرداند.
func rowSymbols(t *testing.T, got map[string]any) []string {
	t.Helper()
	rows := rowsOf(t, got)
	out := make([]string, len(rows))
	for i, r := range rows {
		sym, ok := r["symbol"].(string)
		if !ok {
			t.Fatalf("row %d symbol type = %T", i, r["symbol"])
		}
		out[i] = sym
	}
	return out
}

func wantOrder(t *testing.T, label string, got map[string]any, want ...string) {
	t.Helper()
	have := rowSymbols(t, got)
	if len(have) != len(want) {
		t.Fatalf("%s: rows = %v, want %v", label, have, want)
	}
	for i := range want {
		if have[i] != want[i] {
			t.Fatalf("%s: order = %v, want %v", label, have, want)
		}
	}
}

// rowCodes ins_codeهایِ بدنه را به همان ترتیب می‌دهد؛ برایِ ردیف‌هایِ هم‌نماد
// تنها راهِ دیدنِ ترتیبِ پایدار همین است.
func rowCodes(t *testing.T, got map[string]any) []string {
	t.Helper()
	rows := rowsOf(t, got)
	out := make([]string, len(rows))
	for i, r := range rows {
		code, ok := r["ins_code"].(string)
		if !ok {
			t.Fatalf("row %d ins_code type = %T", i, r["ins_code"])
		}
		out[i] = code
	}
	return out
}

// TestMainwatchGoldens دو بدنهٔ طلاییِ s1 را کامل مقایسه می‌کند و ثابت می‌کند
// پرچم‌ها از منبعِ واقعی *منتقل* می‌شوند: اگر جست‌وجویِ نقشه حذف شود یاfalse
// سخت‌کد شود، f_noqteh/f_susp رویِ m1 از دست می‌رود و تطبیق قرمز می‌شود.
func TestMainwatchGoldens(t *testing.T) {
	h := openFixture(t)
	base, ok := marketFlags(h)
	if !ok {
		t.Fatal("market service did not produce tape flags")
	}
	m1 := base[normSymbol("فولاد۲")]
	if m1 == nil {
		t.Fatalf("flag map has no entry for فولاد۲: keys=%d", len(base))
	}
	if !m1["f_noqteh"] || !m1["f_susp"] {
		t.Fatalf("فولاد۲ flags = %v, want f_noqteh and f_susp true", m1)
	}
	if m1["f_clock"] || m1["f_jet"] || m1["f_roobi"] || m1["f_smart"] || m1["f_legal"] {
		t.Fatalf("فولاد۲ flags = %v, want the other five false", m1)
	}
	for _, k := range flagKeys() {
		if _, ok := m1[k]; !ok {
			t.Fatalf("فولاد۲ missing flag key %q", k)
		}
	}

	got, err := mainwatchPanel(h.Market, stubFlags{base, true}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "mainwatch", loadGolden(t, "s1", "mainwatch_default"), got)

	got2, err := mainwatchPanel(h.Market, stubFlags{base, true}, "eq_all", "", "val", false, 5)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "mainwatch-val", loadGolden(t, "s1", "mainwatch_val"), got2)

	// منبعِ نرسیده: بدنه باید unavailable بگوید و هیچ ردیفی پرچم نگیرد —
	// «همه false» یک مقدارِ واقعی است و این دو حالت نباید یکی شوند.
	got3, err := mainwatchPanel(h.Market, stubFlags{nil, false}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got3["tape_flags_source"] != "unavailable" {
		t.Fatalf("unavailable source = %v", got3["tape_flags_source"])
	}
	for _, r := range rowsOf(t, got3) {
		if _, ok := r["tape_flags"]; ok {
			t.Fatalf("row %v carries tape_flags while source is unavailable", r["symbol"])
		}
	}
}

// TestMainwatchSortKeys هر کلیدِ _GRID_SORT_KEYS را می‌پذیرد (sort_col عینِ
// نگاشتِ پایتون) و کلیدِ ناشناخته به fallbackِ پایتون می‌رود: ستونِ clock_pct
// بدونِ ترمزِ clock_ok. تمایزِ این دو در فیکسچر دیده می‌شود: sort=clock نزولی
// ترتیبِ ورود را برایِ سه ردیفِ بی‌ترمز نگه می‌دارد (m1,m3,m4)، ولی fallback
// خودِ ستون را نزولی می‌چیند (m2,m4,m3,m1).
func TestMainwatchSortKeys(t *testing.T) {
	h := openFixture(t)
	for key, col := range gridSortKeys {
		got, err := mainwatchPanel(h.Market, nil, "eq_all", "", key, true, 120)
		if err != nil {
			t.Fatalf("%s: %v", key, err)
		}
		if got["sort"] != key || got["sort_col"] != col {
			t.Errorf("%s: sort/sort_col = %v/%v, want %s/%s",
				key, got["sort"], got["sort_col"], key, col)
		}
		if got["desc"] != true {
			t.Errorf("%s: desc = %v, want true", key, got["desc"])
		}
	}
	got, err := mainwatchPanel(h.Market, nil, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	wantOrder(t, "clock", got, "وبملت۲", "فولاد۲", "حقا۲", "اوج۲")
	got, err = mainwatchPanel(h.Market, nil, "eq_all", "", "no-such-key", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["sort_col"] != "clock_pct" {
		t.Fatalf("unknown sort_col = %v, want clock_pct", got["sort_col"])
	}
	wantOrder(t, "unknown-fallback", got, "وبملت۲", "اوج۲", "حقا۲", "فولاد۲")
}

// TestMainwatchSortOrderPerKey ترتیبِ واقعیِ هر ۱۴ کلیدِ _GRID_SORT_KEYS را در
// هر دو جهت قفل می‌کند — نه فقط sort/sort_col. جدولِ انتظار از مقادیرِ تزریقیِ
// همان کپیِ فیکسچر ساخته شده است (اوراکل: mstat_engine.mainwatch):
//   - dv: m1..m4 = ۱۰۰/۳۰۰/۲۰۰/۴۰۰ (F3؛ بی آن هر چهار ردیف tie بودند و جهتِ
//     ستون دیده نمی‌شد).
//   - dp: m4 = ۱۰۱۰ تا از pc (که m1/m4 در آن tie اند) جدا شود.
//   - pcs: sell_i_volِ m3 = ۲٬۰۰۰٬۰۰۰ تا رتبه‌بندیِ pcs از val جدا شود؛ وگرنه
//     جابه‌جاییِ مدخل‌هایِ val/pcs در gridSortKeys در هر دو جهت بی‌صدا می‌ماند.
//
// نگهبانِ پایانی مطمئن می‌شود هیچ دو کلیدی ترتیبِ یکسان در هر دو جهت ندارند؛
// پس جابه‌جاییِ هر دو مدخلِ gridSortKeys باید دست‌کم یک ادعا را قرمز کند.
func TestMainwatchSortOrderPerKey(t *testing.T) {
	h := openWritableFixture(t)
	for _, u := range []struct {
		code    string
		vol, px float64
	}{
		{"m1", 100, 1000}, {"m2", 300, 500}, {"m3", 200, 970}, {"m4", 400, 1010},
	} {
		if _, err := h.Market.Exec(
			"UPDATE market_watch SET buy_q1_vol = ?, buy_q1_px = ? WHERE ins_code = ?",
			u.vol, u.px, u.code); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := h.Market.Exec(
		"UPDATE client_type SET sell_i_vol = 2000000 WHERE ins_code = 'm3'"); err != nil {
		t.Fatal(err)
	}

	// [0] نزولی، [1] صعودی.
	want := map[string][2][]string{
		"vol":      {{"وبملت۲", "فولاد۲", "حقا۲", "اوج۲"}, {"حقا۲", "اوج۲", "فولاد۲", "وبملت۲"}},
		"val":      {{"فولاد۲", "وبملت۲", "حقا۲", "اوج۲"}, {"حقا۲", "اوج۲", "وبملت۲", "فولاد۲"}},
		"pc":       {{"فولاد۲", "اوج۲", "حقا۲", "وبملت۲"}, {"وبملت۲", "حقا۲", "فولاد۲", "اوج۲"}},
		"pl":       {{"اوج۲", "حقا۲", "فولاد۲", "وبملت۲"}, {"وبملت۲", "فولاد۲", "حقا۲", "اوج۲"}},
		"pct":      {{"فولاد۲", "وبملت۲", "اوج۲", "حقا۲"}, {"حقا۲", "وبملت۲", "اوج۲", "فولاد۲"}},
		"pct_last": {{"فولاد۲", "وبملت۲", "اوج۲", "حقا۲"}, {"حقا۲", "اوج۲", "وبملت۲", "فولاد۲"}},
		"clock":    {{"وبملت۲", "فولاد۲", "حقا۲", "اوج۲"}, {"وبملت۲", "فولاد۲", "حقا۲", "اوج۲"}},
		"pcb":      {{"حقا۲", "فولاد۲", "وبملت۲", "اوج۲"}, {"اوج۲", "وبملت۲", "فولاد۲", "حقا۲"}},
		"pcs":      {{"فولاد۲", "حقا۲", "وبملت۲", "اوج۲"}, {"اوج۲", "وبملت۲", "حقا۲", "فولاد۲"}},
		"pow":      {{"حقا۲", "فولاد۲", "وبملت۲", "اوج۲"}, {"وبملت۲", "اوج۲", "فولاد۲", "حقا۲"}},
		"flow":     {{"فولاد۲", "حقا۲", "اوج۲", "وبملت۲"}, {"وبملت۲", "اوج۲", "حقا۲", "فولاد۲"}},
		"dv":       {{"اوج۲", "وبملت۲", "حقا۲", "فولاد۲"}, {"فولاد۲", "حقا۲", "وبملت۲", "اوج۲"}},
		"dp":       {{"اوج۲", "فولاد۲", "حقا۲", "وبملت۲"}, {"وبملت۲", "حقا۲", "فولاد۲", "اوج۲"}},
		"symbol":   {{"وبملت۲", "فولاد۲", "حقا۲", "اوج۲"}, {"اوج۲", "حقا۲", "فولاد۲", "وبملت۲"}},
	}

	keys := []string{
		"vol", "val", "pc", "pl", "pct", "pct_last", "clock",
		"pcb", "pcs", "pow", "flow", "dv", "dp", "symbol",
	}
	if len(keys) != len(gridSortKeys) {
		t.Fatalf("keys = %d, gridSortKeys = %d", len(keys), len(gridSortKeys))
	}
	same := func(a, b []string) bool {
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
	for i, a := range keys {
		if _, ok := gridSortKeys[a]; !ok {
			t.Fatalf("key %q is not in gridSortKeys", a)
		}
		for _, b := range keys[i+1:] {
			if same(want[a][0], want[b][0]) && same(want[a][1], want[b][1]) {
				t.Fatalf("keys %q and %q have the same expected order in both directions", a, b)
			}
		}
	}

	for _, key := range keys {
		for _, d := range []struct {
			desc bool
			idx  int
		}{{true, 0}, {false, 1}} {
			got, err := mainwatchPanel(h.Market, nil, "eq_all", "", key, d.desc, 120)
			if err != nil {
				t.Fatalf("%s desc=%v: %v", key, d.desc, err)
			}
			label := key + " desc=true"
			if !d.desc {
				label = key + " desc=false"
			}
			wantOrder(t, label, got, want[key][d.idx]...)
		}
	}
}

// TestMainwatchNilSortsLast: مقدارِ غایب (= NULL در پایتون) در هر دو جهت آخر
// می‌نشیند — پایتون None را با 1e18 (صعودی) یا -1e18 (نزولی) جایگزین می‌کند،
// پس هر دو ترتیبِ صعودی و نزولی nil را به انتها می‌فرستند.
func TestMainwatchNilSortsLast(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET buy_q1_vol = NULL WHERE ins_code = 'm2'"); err != nil {
		t.Fatal(err)
	}
	for _, desc := range []bool{true, false} {
		got, err := mainwatchPanel(h.Market, nil, "eq_all", "", "dv", desc, 120)
		if err != nil {
			t.Fatal(err)
		}
		order := rowSymbols(t, got)
		if order[len(order)-1] != "وبملت۲" {
			t.Fatalf("desc=%v: nil dem_vol row is not last: %v", desc, order)
		}
		want := []string{"فولاد۲", "حقا۲", "اوج۲"}
		for i := range want {
			if order[i] != want[i] {
				t.Fatalf("desc=%v: tied rows = %v, want %v (stable insertion)", desc, order, want)
			}
		}
	}
}

// TestMainwatchTies: ردیف‌هایِ هم‌مقدار ترتیبِ ورودشان را نگه می‌دارند — هم
// صعودی (طلاییِ val) و هم نزولی (همین‌جا). بدونِ SliceStable این ترتیب می‌شکند.
func TestMainwatchTies(t *testing.T) {
	h := openFixture(t)
	got, err := mainwatchPanel(h.Market, nil, "eq_all", "", "val", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	wantOrder(t, "val-desc", got, "فولاد۲", "وبملت۲", "حقا۲", "اوج۲")
	got, err = mainwatchPanel(h.Market, nil, "eq_all", "", "val", false, 120)
	if err != nil {
		t.Fatal(err)
	}
	wantOrder(t, "val-asc", got, "حقا۲", "اوج۲", "وبملت۲", "فولاد۲")
}

// TestMainwatchSymbolSortDirectional (R3): symbol با مقایسهٔ جهت‌دار مرتب
// می‌شود، نه sortِ صعودی و بعد reverse. دو نمادِ هم‌نام ترتیبِ ورودشان را در
// هر دو جهت نگه می‌دارند؛ با sort-then-reverse در نزولی جابه‌جا می‌شدند.
func TestMainwatchSymbolSortDirectional(t *testing.T) {
	h := openWritableFixture(t)
	for code, sym := range map[string]string{"m1": "ب", "m2": "ج", "m3": "ا", "m4": "ا"} {
		if _, err := h.Market.Exec(
			"UPDATE instruments SET l_val18 = ? WHERE ins_code = ?", sym, code); err != nil {
			t.Fatal(err)
		}
	}
	got, err := mainwatchPanel(h.Market, nil, "eq_all", "", "symbol", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	// نمادِ هم‌نام (ا) دو ردیف است؛ ترتیبِ ورودشان را با ins_code می‌سنجیم:
	// m3 پیش از m4 — همان چیزی که پایتون با reverse=True می‌دهد.
	wantOrder(t, "symbol-desc", got, "ج", "ب", "ا", "ا")
	if codes := rowCodes(t, got); codes[2] != "m3" || codes[3] != "m4" {
		t.Fatalf("symbol-desc tie order = %v, want m3 before m4", codes)
	}
	got, err = mainwatchPanel(h.Market, nil, "eq_all", "", "symbol", false, 120)
	if err != nil {
		t.Fatal(err)
	}
	wantOrder(t, "symbol-asc", got, "ا", "ا", "ب", "ج")
	if codes := rowCodes(t, got); codes[0] != "m3" || codes[1] != "m4" {
		t.Fatalf("symbol-asc tie order = %v, want m3 before m4", codes)
	}
}

// TestMainwatchLimit (R5): صفر «بی‌مقدار» است و ۱۲۰ می‌شود (نه ۱)، منفی به ۱
// بسته می‌شود، و مقدارِ بزرگ‌تر از تعدادِ ردیف‌ها همه را برمی‌گرداند. total
// همیشه اندازهٔ کلِ دسته است، نه اندازهٔ صفحه.
func TestMainwatchLimit(t *testing.T) {
	h := openFixture(t)
	for _, c := range []struct {
		limit int
		rows  int
	}{
		{0, 4}, {-5, 1}, {1, 1}, {3, 3}, {999, 4}, {4000, 4},
	} {
		got, err := mainwatchPanel(h.Market, nil, "eq_all", "", "clock", true, c.limit)
		if err != nil {
			t.Fatalf("limit=%d: %v", c.limit, err)
		}
		if n := len(rowsOf(t, got)); n != c.rows {
			t.Errorf("limit=%d: rows = %d, want %d", c.limit, n, c.rows)
		}
		if got["total"] != 4 {
			t.Errorf("limit=%d: total = %v, want 4", c.limit, got["total"])
		}
	}
}

// TestMainwatchIndustry: فیلتر رویِ (sector_name or "").strip() است — نه خام.
// نامِ صنعتِ لبه‌دار (فاصله و U+001F) باید همان صنعت بماند، و صنعتِ ناشناخته
// آرایهٔ خالی می‌دهد، نه null. strings.TrimSpace این‌جا کافی نیست چون U+001F
// whitespaceِ پایتون است ولی whitespaceِ unicode نیست.
func TestMainwatchIndustry(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE instruments SET sector_name = ? WHERE ins_code = 'm1'",
		" \u00a0فلزات اساسي\x1f "); err != nil {
		t.Fatal(err)
	}
	got, err := mainwatchPanel(h.Market, nil, "eq_all", "فلزات اساسي", "", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	wantOrder(t, "industry-strip", got, "فولاد۲")
	if got["industry"] != "فلزات اساسي" {
		t.Errorf("industry echo = %v", got["industry"])
	}
	got, err = mainwatchPanel(h.Market, nil, "eq_all", "صنعت ناشناخته", "", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(raw), `"rows":[]`) {
		t.Fatalf("unknown industry must emit an empty array, got %s", raw)
	}
	if got["total"] != 0 {
		t.Errorf("unknown industry total = %v, want 0", got["total"])
	}
}

// TestMainwatchFlagShapes: چهار حالتِ پرچم جدا می‌شوند — منبعِ نرسیده (بدونِ
// کلیدِ tape_flags)، نقشهٔ خالی با ok=true (همان «منبع نرسید»ِ پایتون)، نقشهٔ
// واقعیِ همه‌false (کلید هست، مقدار false)، و نمادی که در نقشه نیست
// (tape_flags=null، بی‌آنکه پنل خطا بدهد — عینِ flags.get()).
func TestMainwatchFlagShapes(t *testing.T) {
	h := openFixture(t)
	// ok=true با نقشهٔ ساختگیِ تک‌نماد: ردیفِ بی‌کلید null می‌گیرد، نه خطا.
	one := map[string]map[string]bool{
		normSymbol("فولاد۲"): {"f_noqteh": true},
	}
	got, err := mainwatchPanel(h.Market, stubFlags{one, true}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["tape_flags_source"] != "api/market" {
		t.Fatalf("source = %v", got["tape_flags_source"])
	}
	for _, r := range rowsOf(t, got) {
		v, ok := r["tape_flags"].(map[string]bool)
		if !ok {
			t.Fatalf("%v: tape_flags type = %T", r["symbol"], r["tape_flags"])
		}
		if r["symbol"] == "فولاد۲" {
			if !v["f_noqteh"] {
				t.Errorf("فولاد۲ f_noqteh = false, want true")
			}
			continue
		}
		if v != nil {
			t.Errorf("%v: missing symbol got %v, want nil (JSON null)", r["symbol"], v)
		}
	}

	// ok=true با نقشهٔ کاملِ همه‌false: برخلافِ «unavailable»، کلید وجود دارد.
	allFalse := map[string]map[string]bool{}
	for _, sym := range []string{"فولاد۲", "وبملت۲", "حقا۲", "اوج۲"} {
		fl := map[string]bool{}
		for _, k := range flagKeys() {
			fl[k] = false
		}
		allFalse[normSymbol(sym)] = fl
	}
	got, err = mainwatchPanel(h.Market, stubFlags{allFalse, true}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["tape_flags_source"] != "api/market" {
		t.Fatalf("all-false source = %v", got["tape_flags_source"])
	}
	for _, r := range rowsOf(t, got) {
		v, ok := r["tape_flags"].(map[string]bool)
		if !ok || v == nil {
			t.Fatalf("%v: all-false flags = %v, want a present map", r["symbol"], r["tape_flags"])
		}
		for _, k := range flagKeys() {
			if v[k] {
				t.Errorf("%v: %s = true, want false", r["symbol"], k)
			}
		}
	}

	// نقشهٔ خالی با ok=true: پایتون `if not flags` را «منبع نرسید» می‌خواند، نه
	// «هیچ نمادی پرچم ندارد»؛ پس source باید unavailable باشد و هیچ ردیفی کلیدِ
	// tape_flags نگیرد (حتی null).
	got, err = mainwatchPanel(h.Market,
		stubFlags{map[string]map[string]bool{}, true}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["tape_flags_source"] != "unavailable" {
		t.Fatalf("empty-map source = %v, want unavailable", got["tape_flags_source"])
	}
	if rows := rowsOf(t, got); len(rows) != 4 {
		t.Fatalf("empty-map rows = %d, want 4", len(rows))
	}
	for _, r := range rowsOf(t, got) {
		if _, ok := r["tape_flags"]; ok {
			t.Fatalf("%v: empty-map source attached tape_flags (%v)", r["symbol"], r["tape_flags"])
		}
	}
}

// TestMainwatchRealServiceFlagSource (F8): خودِ *market.Service رویِ فیکسچر،
// مستقیم به‌عنوانِ FlagSource داده می‌شود (نه stub)، تا پیاده‌سازیِ interface و
// انتقالِ پرچم‌ها از کشِ واقعی prove شود. سپس با تخلیهٔ تابلو همان نوع سرویس
// unavailable می‌دهد: بدنه باید source=unavailable بدهد و ردیف‌ها کلیدِ
// tape_flags نداشته باشند — عینِ _attach_tape_flags وقتی _tape_flag_map خالی است.
func TestMainwatchRealServiceFlagSource(t *testing.T) {
	dir := copyFixture(t)
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })

	svc := market.New(h, dir)
	got, err := mainwatchPanel(h.Market, svc, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["tape_flags_source"] != "api/market" {
		t.Fatalf("real-service source = %v, want api/market", got["tape_flags_source"])
	}
	flags, ok := svc.TapeFlags()
	if !ok || len(flags) == 0 {
		t.Fatalf("TapeFlags = (%d keys, ok=%v), want a non-empty available map", len(flags), ok)
	}
	rows := rowsOf(t, got)
	if len(rows) == 0 {
		t.Fatal("real-service panel returned no rows")
	}
	for _, r := range rows {
		sym, ok := r["symbol"].(string)
		if !ok {
			t.Fatalf("symbol type = %T", r["symbol"])
		}
		tape, ok := r["tape_flags"].(map[string]bool)
		if !ok || tape == nil {
			t.Fatalf("%s: tape_flags = %v (%T), want a present map", sym, r["tape_flags"], r["tape_flags"])
		}
		want, ok := flags[normSymbol(sym)]
		if !ok {
			t.Fatalf("flag map has no key for %q", sym)
		}
		if len(tape) != len(want) {
			t.Fatalf("%s: %d flags, want %d", sym, len(tape), len(want))
		}
		for k, v := range want {
			if tape[k] != v {
				t.Errorf("%s: %s = %v, want %v", sym, k, tape[k], v)
			}
		}
	}

	// تخلیهٔ تابلو: همان سرویسِ واقعی دیگر پرچمی ندارد؛ پایتون در این حالت
	// unavailable می‌دهد و ردیف‌ها بی‌کلیدِ tape_flags می‌مانند.
	if _, err := h.Market.Exec("DELETE FROM market_watch"); err != nil {
		t.Fatal(err)
	}
	emptySvc := market.New(h, dir)
	if m, ok := emptySvc.TapeFlags(); ok || len(m) != 0 {
		t.Fatalf("empty-board TapeFlags = (%d keys, ok=%v), want (0, false)", len(m), ok)
	}
	got, err = mainwatchPanel(h.Market, emptySvc, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got["tape_flags_source"] != "unavailable" {
		t.Fatalf("empty-board source = %v, want unavailable", got["tape_flags_source"])
	}
	for _, r := range rowsOf(t, got) {
		if _, ok := r["tape_flags"]; ok {
			t.Fatalf("%v: empty board attached tape_flags", r["symbol"])
		}
	}
}

// TestNormSymbol: ي/ى عربی → ی، ك → ک، لبه‌ها با stripِ پایتون بریده می‌شوند،
// و نیم‌فاصله بخشی از نماد است (حذف نمی‌شود).
func TestNormSymbol(t *testing.T) {
	for _, c := range []struct{ in, want string }{
		{"فولاد۲", "فولاد۲"},
		{"ي", "ی"},
		{"ى", "ی"},
		{"ك", "ک"},
		{"بابك", "بابک"},
		{"  فولاد\u200c۲  ", "فولاد\u200c۲"},
		{"\u00a0x\u001f", "x"},
		{"فولاد ي", "فولاد ی"},
	} {
		if got := normSymbol(c.in); got != c.want {
			t.Errorf("normSymbol(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
