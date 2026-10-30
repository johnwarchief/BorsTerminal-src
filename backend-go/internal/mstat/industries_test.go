package mstat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/parity"
)

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

// compareGolden تطبیقِ کاملِ بدنه با canonِ B1؛ استثناها فقط قراردادِ همین
// پنل‌اند (ساعتِ دیواری) و در فهرست صریح آمده‌اند.
//
// بدنهٔ Go پیش از مقایسه از درِ JSON می‌گذرد: canon فقط []any/map[string]any
// را می‌شناسد، ولی پنل‌ها ساختارِ تایپ‌دار می‌سازند ([]map[string]any،
// map[string]bool) و لایهٔ HTTP هم همان را به JSON می‌نویسد. normalize اینجا
// یعنی مقایسه همان چیزی است که کلاینت می‌بیند، نه شکلِ داخلیِ structها.
func compareGolden(t *testing.T, name string, want, got map[string]any, exclude ...string) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal body: %v", name, err)
	}
	var norm map[string]any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal body: %v", name, err)
	}
	// source خروجیِ موتور نیست: _mstat_compute (و Task 9's Service.compute) آن را
	// با setdefault رویِ بدنه می‌نشاند. همان کار این‌جا هم تکرار می‌شود تا پنل‌ها
	// وفادارِ پایتون بمانند. setdefault است، نه overwrite: پنلی که خودش sourceِ
	// اشتباه بگذارد در diff لو می‌رود.
	if _, ok := norm["source"]; !ok {
		norm["source"] = mstatSource
	}
	res := parity.Compare(want, norm, parity.Options{Exclude: exclude})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", name, d)
		}
		t.Fatalf("%s: %d diffs", name, len(res.Diffs))
	}
}

var pinnedNow = time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)

func TestIndustriesMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "industries", loadGolden(t, "s1", "industries"), got)
}

// TestIndustriesTrimsSectorName: پایتون `(r.get("sector_name") or "").strip()`
// می‌خواند. فاصلهٔ معمولی، NBSP و U+001F در دو سرِ نام باید همان بدنهٔ طلایی را
// بدهد (همان رشتهٔ industry، همان leader، همان rows) — نه صنعتی تازه با نامِ
// آلوده. این تست گروه‌بندی را ادعا نمی‌کند: در s1 هر صنعت فقط یک نماد دارد؛
// گروه‌بندی/رتبه را TestRankIndustries می‌سنجد.
func TestIndustriesTrimsSectorName(t *testing.T) {
	h := openWritableFixture(t)
	for _, c := range []struct{ code, sector string }{
		{"m1", " فلزات اساسي "},
		{"m2", "بانكها و موسسات اعتباري\u00a0"},
		{"m3", "سرمایه گذاريها\x1f"},
	} {
		if _, err := h.Market.Exec(
			"UPDATE instruments SET sector_name = ? WHERE ins_code = ?", c.sector, c.code); err != nil {
			t.Fatal(err)
		}
	}
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "industries-trim", loadGolden(t, "s1", "industries"), got)
	for _, x := range got["rows"].([]map[string]any) {
		name := x["industry"].(string)
		if pyStrip(name) != name {
			t.Fatalf("industry %q kept surrounding whitespace", name)
		}
	}
}

// TestIndustriesInnerWhitespacePreserved: strip فقط لبه‌ها را می‌برد؛ فاصلهٔ
// داخلی و کنترلِ غیرِفاصله (NUL و DEL) وسطِ نام باید دست‌نخورده بمانند، وگرنه
// نامِ صنعت بی‌صدا عوض می‌شود. U+001C و U+001Fِ لبه‌ها باید بریده شوند.
func TestIndustriesInnerWhitespacePreserved(t *testing.T) {
	h := openWritableFixture(t)
	want := "فلزات\x00  اساسي\x7f"
	if _, err := h.Market.Exec(
		"UPDATE instruments SET sector_name = ? WHERE ins_code = 'm1'",
		" \x1c"+want+"\x1f "); err != nil {
		t.Fatal(err)
	}
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	rows := got["rows"].([]map[string]any)
	if len(rows) != 3 {
		t.Fatalf("rows = %d, want 3", len(rows))
	}
	found := ""
	for _, x := range rows {
		if name := x["industry"].(string); strings.Contains(name, "فلزات") {
			found = name
		}
	}
	if found != want {
		t.Fatalf("industry = %q, want %q (inner spaces/controls must survive strip)", found, want)
	}
}

// TestPyStrip همان قراردادِ str.strip() را رویِ نویسه‌هایِ مرزی می‌سنجد:
// U+001C..U+001F هم whitespaceِ پایتون‌اند ولی unicode.IsSpace نیستند.
func TestPyStrip(t *testing.T) {
	for _, c := range []struct{ in, want string }{
		{"  x  ", "x"},
		{"\u00a0x\u00a0", "x"},
		{"\x1cx\x1d", "x"},
		{"\x1ex\x1f", "x"},
		{"x\x00\x7fy", "x\x00\x7fy"},
		{"a  b", "a  b"},
	} {
		if got := pyStrip(c.in); got != c.want {
			t.Errorf("pyStrip(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

// TestRankIndustries رتبه‌بندیِ دومعیاره را بدونِ DB قفل می‌کند: ترتیبِ ورود
// نباید رتبه را تعیین کند، tie ارزش با ترتیبِ پایدار و tie شکستِ نهایی با
// جریان (nil = 0) حل شود، جریانِ نامثبت رتبه نگیرد، و لیدر فقط با هر دو
// رتبهٔ ≤ 5 انتخاب شود. وکتورِ «leader score order» نشان می‌دهد کاندید از
// کمترین امتیاز می‌آید نه از out[0]، و وکتورِ «rank_value 6» نیمهٔ ارزشیِ
// گاردِ لیدر را می‌سنجد (امتیازِ کمینه با rank_value=6 باید رد شود). بدونِ
// این وکتورها حذفِ هر کدام از sortها/گارد بی‌صدا سبز می‌ماند (فیکسچرِ s1
// ترتیبِ ورود = ترتیبِ ارزش دارد).
func TestRankIndustries(t *testing.T) {
	type want struct {
		rv     int
		rf     any
		score  int
		leader bool
	}
	cases := []struct {
		name       string
		in         []*outRow
		wantOrder  []string
		wantLeader string
		want       map[string]want
	}{
		{
			// (a) ترتیبِ ورود A,B,C ولی ارزش B>C>A: رتبه و ترتیبِ نهایی از
			// ارزش می‌آید، نه از ترتیبِ ساخت. لیدر A است که آخرِ جدول می‌نشیند.
			name: "insertion order differs from value order",
			in: []*outRow{
				{industry: "A", valueBT: 10, flowBT: 5.0},
				{industry: "B", valueBT: 100},
				{industry: "C", valueBT: 50, flowBT: 1.0},
			},
			wantOrder:  []string{"B", "C", "A"},
			wantLeader: "A",
			want: map[string]want{
				"A": {rv: 3, rf: 1, score: 4, leader: true},
				"B": {rv: 1, rf: nil, score: 5, leader: false},
				"C": {rv: 2, rf: 2, score: 4, leader: false},
			},
		},
		{
			// (b) ارزشِ برابر: رتبه با ترتیبِ ورودِ پایدار (A,B,C) و ترتیبِ نهایی
			// با جریانِ (جریانِ nil = ۰) شکسته می‌شود: ۰ِ A و C جلوتر از -5ِ B.
			name: "equal value stable rank and flow tie-break",
			in: []*outRow{
				{industry: "A", valueBT: 10},
				{industry: "B", valueBT: 10, flowBT: -5.0},
				{industry: "C", valueBT: 10, flowBT: 0.0},
			},
			wantOrder:  []string{"A", "C", "B"},
			wantLeader: "",
			want: map[string]want{
				"A": {rv: 1, rf: nil, score: 5, leader: false},
				"B": {rv: 2, rf: nil, score: 6, leader: false},
				"C": {rv: 3, rf: nil, score: 7, leader: false},
			},
		},
		{
			// (c) فقط جریانِ اکیداً مثبت رتبه می‌گیرد؛ صفرِ واقعی، nil و منفی
			// هیچ‌کدام رتبه ندارند و جریمهٔ len+1 می‌خورند.
			name: "only strictly positive flow is ranked",
			in: []*outRow{
				{industry: "A", valueBT: 40, flowBT: 3.0},
				{industry: "B", valueBT: 30, flowBT: 0.0},
				{industry: "C", valueBT: 20},
				{industry: "D", valueBT: 10, flowBT: -2.0},
			},
			wantOrder:  []string{"A", "B", "C", "D"},
			wantLeader: "A",
			want: map[string]want{
				"A": {rv: 1, rf: 1, score: 2, leader: true},
				"B": {rv: 2, rf: nil, score: 7, leader: false},
				"C": {rv: 3, rf: nil, score: 8, leader: false},
				"D": {rv: 4, rf: nil, score: 9, leader: false},
			},
		},
		{
			// (d) بهترین امتیاز (X با ۱+۶=۷، هم‌امتیاز با بقیه و اول به‌خاطرِ
			// ترتیبِ پایدار) rank_flow=۶ دارد ⇒ لیدر ندارد؛ حذفِ قیدِ ≤۵ همین‌جا
			// X را لیدر می‌کند و تست قرمز می‌شود.
			name: "leader rejected when best rank_flow is 6",
			in: []*outRow{
				{industry: "X", valueBT: 600, flowBT: 1.0},
				{industry: "Y", valueBT: 500, flowBT: 2.0},
				{industry: "Z", valueBT: 400, flowBT: 3.0},
				{industry: "W", valueBT: 300, flowBT: 4.0},
				{industry: "V", valueBT: 200, flowBT: 5.0},
				{industry: "U", valueBT: 100, flowBT: 6.0},
			},
			wantOrder:  []string{"X", "Y", "Z", "W", "V", "U"},
			wantLeader: "",
			want: map[string]want{
				"X": {rv: 1, rf: 6, score: 7, leader: false},
				"Y": {rv: 2, rf: 5, score: 7, leader: false},
				"Z": {rv: 3, rf: 4, score: 7, leader: false},
				"W": {rv: 4, rf: 3, score: 7, leader: false},
				"V": {rv: 5, rf: 2, score: 7, leader: false},
				"U": {rv: 6, rf: 1, score: 7, leader: false},
			},
		},
		{
			// (d') بهترین امتیازِ یک صنعتِ بدونِ جریان هم لیدر نمی‌شود.
			name: "leader rejected when best flow is nil",
			in: []*outRow{
				{industry: "X", valueBT: 100, flowBT: -1.0},
				{industry: "Y", valueBT: 50},
			},
			wantOrder:  []string{"X", "Y"},
			wantLeader: "",
			want: map[string]want{
				"X": {rv: 1, rf: nil, score: 4, leader: false},
				"Y": {rv: 2, rf: nil, score: 5, leader: false},
			},
		},
		{
			// (e) امتیازِ بی‌رتبه = rank_value + len(out) + 1 (اینجا ۳).
			name: "unranked leader score",
			in: []*outRow{
				{industry: "A", valueBT: 100},
				{industry: "B", valueBT: 10, flowBT: -3.0},
			},
			wantOrder:  []string{"A", "B"},
			wantLeader: "",
			want: map[string]want{
				"A": {rv: 1, rf: nil, score: 4, leader: false},
				"B": {rv: 2, rf: nil, score: 5, leader: false},
			},
		},
		{
			// (f) کاندیدِ لیدر از کمترین امتیاز می‌آید، نه از out[0]: ورودی A,B
			// ولی امتیازِ B=2 و A=4 ⇒ لیدر B و ترتیبِ نهایی B,A. حذفِ sortِ cand
			// همان A را (rv 2، rf 2، هر دو ≤ 5) لیدر می‌کند و تست قرمز می‌شود.
			name: "leader score order beats insertion order",
			in: []*outRow{
				{industry: "A", valueBT: 50, flowBT: 1.0},
				{industry: "B", valueBT: 100, flowBT: 2.0},
			},
			wantOrder:  []string{"B", "A"},
			wantLeader: "B",
			want: map[string]want{
				"A": {rv: 2, rf: 2, score: 4, leader: false},
				"B": {rv: 1, rf: 1, score: 2, leader: true},
			},
		},
		{
			// (g) نیمهٔ rank_value گارد: پنج صنعتِ پر‌ارزش با جریانِ nil (امتیازِ
			// rv+7) و یک صنعتِ کم‌ارزش با جریانِ مثبت (امتیازِ 6+1=7) ⇒ cand[0]=L
			// با rank_value=6 و rank_flow=1. حذفِ top.rankValue <= 5 همین L را
			// لیدر می‌کند (تست قرمز) چون rf=1 ≤ 5 است و گارد را رد می‌کند.
			name: "leader rejected when best score has rank_value 6",
			in: []*outRow{
				{industry: "H1", valueBT: 600},
				{industry: "H2", valueBT: 500},
				{industry: "H3", valueBT: 400},
				{industry: "H4", valueBT: 300},
				{industry: "H5", valueBT: 200},
				{industry: "L", valueBT: 100, flowBT: 1.0},
			},
			wantOrder:  []string{"H1", "H2", "H3", "H4", "H5", "L"},
			wantLeader: "",
			want: map[string]want{
				"H1": {rv: 1, rf: nil, score: 8, leader: false},
				"H2": {rv: 2, rf: nil, score: 9, leader: false},
				"H3": {rv: 3, rf: nil, score: 10, leader: false},
				"H4": {rv: 4, rf: nil, score: 11, leader: false},
				"H5": {rv: 5, rf: nil, score: 12, leader: false},
				"L":  {rv: 6, rf: 1, score: 7, leader: false},
			},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			leader := rankIndustries(c.in)
			if leader != c.wantLeader {
				t.Errorf("leader = %q, want %q", leader, c.wantLeader)
			}
			order := make([]string, 0, len(c.in))
			for _, x := range c.in {
				order = append(order, x.industry)
			}
			if len(order) != len(c.wantOrder) {
				t.Fatalf("order = %v, want %v", order, c.wantOrder)
			}
			for i := range order {
				if order[i] != c.wantOrder[i] {
					t.Fatalf("order = %v, want %v", order, c.wantOrder)
				}
			}
			for _, x := range c.in {
				w, ok := c.want[x.industry]
				if !ok {
					t.Fatalf("unexpected industry %q", x.industry)
				}
				if x.rankValue != w.rv || x.rankFlow != w.rf ||
					x.leaderScore != w.score || x.leader != w.leader {
					t.Errorf("%s = rv %d rf %v score %d leader %v, want %d %v %d %v",
						x.industry, x.rankValue, x.rankFlow, x.leaderScore, x.leader,
						w.rv, w.rf, w.score, w.leader)
				}
			}
		})
	}
}

// TestIndustriesUntradedIndustry: صنعتِ بی‌معامله «جریانِ اندازه‌گیری‌نشده»
// دارد، نه صفر — flow/flow_pct/avg_pct/rank_flow باید null باشند و امتیازش
// با جریمهٔ len+1 بسته شود. m1 همچنان لیدر است.
func TestIndustriesUntradedIndustry(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`UPDATE market_watch
		SET q_tot_cap = 0, price_yesterday = NULL WHERE ins_code = 'm3'`); err != nil {
		t.Fatal(err)
	}
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	rows := got["rows"].([]map[string]any)
	if len(rows) != 3 {
		t.Fatalf("rows = %d, want 3", len(rows))
	}
	want := []string{"فلزات اساسي", "بانكها و موسسات اعتباري", "سرمایه گذاريها"}
	for i, name := range want {
		if rows[i]["industry"] != name {
			t.Fatalf("rows[%d].industry = %v, want %s", i, rows[i]["industry"], name)
		}
	}
	m3 := rows[2]
	if m3["flow_b_toman"] != nil || m3["flow_pct_of_value"] != nil || m3["avg_pct"] != nil {
		t.Errorf("untraded flow/flow_pct/avg_pct = %v/%v/%v, want nil/nil/nil",
			m3["flow_b_toman"], m3["flow_pct_of_value"], m3["avg_pct"])
	}
	if m3["rank_flow"] != nil {
		t.Errorf("untraded rank_flow = %v, want nil", m3["rank_flow"])
	}
	if v := m3["value_b_toman"].(float64); v != 0 {
		t.Errorf("untraded value_b_toman = %v, want 0", v)
	}
	if rv := m3["rank_value"].(int); rv != 3 {
		t.Errorf("untraded rank_value = %d, want 3", rv)
	}
	if score := m3["leader_score"].(int); score != 7 { // 3 + (3+1)
		t.Errorf("untraded leader_score = %d, want 7 (rank_value + len(rows)+1)", score)
	}
	if m3["leader"].(bool) {
		t.Error("untraded industry must not be leader")
	}
	if !rows[0]["leader"].(bool) || got["leader"] != "فلزات اساسي" {
		t.Errorf("leader = %v / rows[0].leader = %v, want فلزات اساسي/true",
			got["leader"], rows[0]["leader"])
	}
}

// TestIndustriesNoLeader: وقتی هیچ صنعتی معامله ندارد، هیچ لیدری هم نیست —
// leader بدنه null (nilIfEmpty)، همهٔ جریان‌ها null، و رتبهٔ ارزش با ترتیبِ
// پایدارِ ورود (m1,m2,m3) می‌نشیند چون همه در صفر مساوی‌اند.
func TestIndustriesNoLeader(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`UPDATE market_watch
		SET q_tot_cap = 0, price_yesterday = NULL
		WHERE ins_code IN ('m1', 'm2', 'm3')`); err != nil {
		t.Fatal(err)
	}
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if got["leader"] != nil {
		t.Fatalf("leader = %v, want nil", got["leader"])
	}
	rows := got["rows"].([]map[string]any)
	if len(rows) != 3 {
		t.Fatalf("rows = %d, want 3", len(rows))
	}
	want := []string{"فلزات اساسي", "بانكها و موسسات اعتباري", "سرمایه گذاريها"}
	for i, x := range rows {
		if x["industry"] != want[i] {
			t.Fatalf("rows[%d].industry = %v, want %s (stable insertion order)",
				i, x["industry"], want[i])
		}
		if x["flow_b_toman"] != nil || x["rank_flow"] != nil || x["avg_pct"] != nil {
			t.Errorf("%v flow/rank_flow/avg_pct = %v/%v/%v, want nil/nil/nil",
				x["industry"], x["flow_b_toman"], x["rank_flow"], x["avg_pct"])
		}
		if x["leader"].(bool) {
			t.Errorf("%v leader = true, want false", x["industry"])
		}
		if rv := x["rank_value"].(int); rv != i+1 {
			t.Errorf("%v rank_value = %d, want %d", x["industry"], rv, i+1)
		}
		if score := x["leader_score"].(int); score != i+1+4 {
			t.Errorf("%v leader_score = %d, want %d", x["industry"], score, i+1+4)
		}
	}
}
