package fundamental

// آزمونِ اوراکل (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). تنها داورِ این
// لایه فایلِ testdata/vectors/indicators.json است که اوراکلِ پایتون
// (api/fundamental.py) رویِ فیکسچرِ کامیت‌شدۀ testdata/fixture/market.db نوشته —
// هیچ انتظاری اینجا تایپِ دستی نشده: کلیدها، نوع‌ها و ارقام از همان JSON خوانده
// می‌شوند و تبدیل‌ها با ورودیِ خودِ کیس صدا زده می‌شوند.
//
// مقایسه کلید‌به‌کلید است و نوعِ هر کلید هم سنجیده می‌شود تا nil و false و ۰ از
// هم جدا بمانند («بی‌داده» ≠ «رد» ≠ «صفر»). فهرستِ کلیدها باید دقیقاً یکی باشد،
// وگرنه شاخه‌هایِ شرطیِ `_nodata`/`note_breadth`/`source_detail` گم‌شده «مساوی»
// خوانده می‌شد.
//
// قیدِ گیت‌ها: market.dbِ ریشۀ مارکت هرگز باز نمی‌شود؛ اینجا فقط کپیِ فیکسچر درِ
// پوشۀ موقت و آن هم فقط‌خواندنی (همان الگویِ golden_test.go).

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
)

// ax1VectorsPath اوراکلِ عددی؛ ax1OraclePy/ax1FtsPy منبعِ رشته‌هایِ verbatim.
const (
	ax1VectorsPath = "testdata/vectors/indicators.json"
	ax1OraclePy    = "../../../api/fundamental.py"
	ax1FtsPy       = "../../../fts_engine.py"
)

type (
	ax1CaseKV struct {
		Symbol string          `json:"symbol"`
		Out    json.RawMessage `json:"out"`
	}
	ax1CaseMap struct {
		Symbol string         `json:"symbol"`
		Out    map[string]any `json:"out"`
	}
	ax1CaseProf struct {
		Symbol string         `json:"symbol"`
		Sector string         `json:"sector"`
		Out    map[string]any `json:"out"`
	}
	ax1CaseMonth struct {
		Symbol string  `json:"symbol"`
		Rows   [][]any `json:"rows"`
	}
)

type ax1Vectors struct {
	Ind1a   []ax1CaseMap   `json:"ind1a"`
	Ind1b   []ax1CaseMap   `json:"ind1b"`
	Axis1   []ax1CaseKV    `json:"axis1"`
	States  []ax1CaseMap   `json:"states"`
	Profile []ax1CaseProf  `json:"profile"`
	Monthly []ax1CaseMonth `json:"monthly"`
}

// ax1LoadVectors فایلِ داور را می‌خواند و حداقلِ شمارِ کیس هر کلید را می‌سنجد؛
// کمِ‌تر یعنی داور دست‌خورده/نیمه‌کاره است و سبز شدنش بی‌معنی.
func ax1LoadVectors(t *testing.T) ax1Vectors {
	t.Helper()
	b, err := os.ReadFile(ax1VectorsPath)
	if err != nil {
		t.Fatalf("خواندنِ vectors: %v", err)
	}
	var v ax1Vectors
	if err := json.Unmarshal(b, &v); err != nil {
		t.Fatalf("تجزیهٔ vectors: %v", err)
	}
	for _, c := range []struct {
		name string
		n    int
		want int
	}{
		{"ind1a", len(v.Ind1a), 5}, {"ind1b", len(v.Ind1b), 5},
		{"axis1", len(v.Axis1), 5}, {"states", len(v.States), 5},
		{"profile", len(v.Profile), 5}, {"monthly", len(v.Monthly), 5},
	} {
		if c.n < c.want {
			t.Fatalf("کلید %q درِ فایلِ داور %d کیس دارد، حداقلِ انتظار %d",
				c.name, c.n, c.want)
		}
	}
	return v
}

// ax1OpenFixture کپیِ فیکسچر درِ پوشۀ موقت، فقط‌خواندنی.
func ax1OpenFixture(t *testing.T) *Service {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatalf("خواندنِ فیکسچر: %v", err)
	}
	path := filepath.Join(dir, "market.db")
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatalf("کپیِ فیکسچر: %v", err)
	}
	h, err := db.Open(dir, true)
	if err != nil {
		t.Fatalf("بازکردنِ کپیِ فیکسچر: %v", err)
	}
	t.Cleanup(func() { _ = h.Close() })
	s := New(h.Market)
	t.Cleanup(func() { _ = s.Close() })
	return s
}

func ax1SeriesFor(v ax1Vectors, symbol string) [][]any {
	for _, m := range v.Monthly {
		if m.Symbol == symbol {
			return m.Rows
		}
	}
	return nil
}

func ax1ProfileFor(v ax1Vectors, symbol string) map[string]any {
	for _, p := range v.Profile {
		if p.Symbol == symbol {
			return p.Out
		}
	}
	return nil
}

func ax1Ind1aFor(v ax1Vectors, symbol string) map[string]any {
	for _, c := range v.Ind1a {
		if c.Symbol == symbol {
			return c.Out
		}
	}
	return nil
}

func ax1Ind1bFor(v ax1Vectors, symbol string) map[string]any {
	for _, c := range v.Ind1b {
		if c.Symbol == symbol {
			return c.Out
		}
	}
	return nil
}

// ── مقایسهٔ نوع‌دار ──────────────────────────────────────────────────────────

// ax1Kind نامِ «ارزشِ JSON» را می‌دهد تا nil و false و ۰ از هم جدا بمانند.
func ax1Kind(v any) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case bool:
		return "bool"
	case string:
		return "string"
	case float64, int, int64:
		return "number"
	case []any, []map[string]any:
		return "array"
	case map[string]any:
		return "object"
	case json.RawMessage:
		if len(x) == 0 || string(x) == "null" {
			return "null"
		}
		return "raw"
	}
	return "other"
}

func ax1Num(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	}
	return 0, false
}

func ax1Bool(v any) (bool, bool) { b, ok := v.(bool); return b, ok }

func ax1Show(v any) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case string:
		return "«" + x + "»"
	case bool:
		if x {
			return "true"
		}
		return "false"
	}
	b, err := json.Marshal(v)
	if err != nil {
		return "?"
	}
	return string(b)
}

// ax1ValuesEqual دو ارزشِ هم‌نام را مقایسه می‌کند؛ اولِ کار نوع‌ها باید
// هم‌خانواده باشند (false ≠ null ≠ ۰) و بعد عددها عددی سنجیده می‌شوند.
func ax1ValuesEqual(path string, want, got any) (string, bool) {
	wk, gk := ax1Kind(want), ax1Kind(got)
	if wk != gk {
		return path + ": نوع " + wk + " ≠ " + gk +
			" (want=" + ax1Show(want) + " got=" + ax1Show(got) + ")", false
	}
	switch wk {
	case "null":
		return "", true
	case "bool":
		w, _ := ax1Bool(want)
		g, _ := ax1Bool(got)
		if w != g {
			return path + ": bool want=" + ax1Show(want) + " got=" + ax1Show(got), false
		}
		return "", true
	case "string":
		if want.(string) != got.(string) {
			return path + ": رشته want=" + ax1Show(want) + " got=" + ax1Show(got), false
		}
		return "", true
	case "number":
		wf, _ := ax1Num(want)
		gf, _ := ax1Num(got)
		if math.Abs(wf-gf) > 1e-9 {
			return path + ": عدد want=" + ax1Show(want) + " got=" + ax1Show(got), false
		}
		return "", true
	case "object":
		return ax1CompareMap(path, want.(map[string]any), ax1AsMap(got))
	case "array":
		wl, gl := ax1AsSlice(want), ax1AsSlice(got)
		if len(wl) != len(gl) {
			return path + fmt.Sprintf(": طولِ فهرست %d ≠ %d", len(wl), len(gl)), false
		}
		for i := range wl {
			if msg, ok := ax1ValuesEqual(fmt.Sprintf("%s[%d]", path, i), wl[i], gl[i]); !ok {
				return msg, false
			}
		}
		return "", true
	}
	if !reflect.DeepEqual(want, got) {
		return path + ": want=" + ax1Show(want) + " got=" + ax1Show(got), false
	}
	return "", true
}

func ax1AsMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return nil
}

// ax1AsSlice فهرستِ Go (ساختۀ خودِ توابع) و فهرستِ JSON را به یک شکل می‌آورد.
func ax1AsSlice(v any) []any {
	switch x := v.(type) {
	case []any:
		return x
	case []map[string]any:
		out := make([]any, len(x))
		for i, m := range x {
			out[i] = any(m)
		}
		return out
	}
	return nil
}

// ax1CompareMap هر دو طرف باید دقیقاً همان کلیدها را داشته باشند؛ بی‌این یکِ
// کلیدِ گم‌شده درِ شاخهٔ شرطی هم «مساوی» خوانده می‌شد.
func ax1CompareMap(path string, want, got map[string]any) (string, bool) {
	if got == nil {
		return path + ": خروجیِ nil در برابرِ نقشۀ اوراکل", false
	}
	for k := range want {
		if _, ok := got[k]; !ok {
			return path + "." + k + ": کلید درِ خروجیِ Go نیست", false
		}
	}
	for k := range got {
		if _, ok := want[k]; !ok {
			return path + "." + k + ": کلیدِ اضافه درِ خروجیِ Go (اوراکل نمی‌نویسدش)", false
		}
	}
	for _, k := range ax1SortedKeys(want) {
		if msg, ok := ax1ValuesEqual(path+"."+k, want[k], got[k]); !ok {
			return msg, false
		}
	}
	return "", true
}

func ax1SortedKeys(m map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && out[j] < out[j-1]; j-- {
			out[j], out[j-1] = out[j-1], out[j]
		}
	}
	return out
}

// ── لایۀ ۱الف ────────────────────────────────────────────────────────────────

func TestAx1Ind1aMatchesOracle(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	sawGap, sawNilPct, sawRow := 0, 0, 0
	for _, c := range v.Ind1a {
		series := ax1SeriesFor(v, c.Symbol)
		if len(series) == 0 {
			t.Fatalf("%s: هیچ ردیفی درِ کلید monthly برایِ این نماد نیست", c.Symbol)
		}
		got, err := s.Ind1aMonetaryGrowth(ctx, c.Symbol, series, nil, ax1ProfileFor(v, c.Symbol))
		if err != nil {
			t.Fatalf("%s: ind1a: %v", c.Symbol, err)
		}
		if msg, ok := ax1CompareMap(c.Symbol, c.Out, got); !ok {
			t.Errorf("ind1a %s: %s", c.Symbol, msg)
		}
		if b, ok := ax1Bool(c.Out["data_gap"]); ok && b {
			sawGap++
		}
		if c.Out["monetary_pct"] == nil {
			sawNilPct++
		}
		sawRow += len(series)
	}
	if sawGap == 0 || sawNilPct == 0 {
		t.Errorf("شاخۀ data_gap/monetary_pct=nil پوشش داده نشده (gap=%d nil=%d)", sawGap, sawNilPct)
	}
	if sawRow < 40 {
		t.Errorf("ردیفِ سریِ سنجیده‌شده %d است — کیس‌ها لاغر شده‌اند", sawRow)
	}
	// گرامِ نوع که اوراکل خودش ثابت می‌کند: رأیِ ۱الف همیشه bool است و `unit`
	// هیچ‌وقت حدسِ واحد نیست.
	for _, c := range v.Ind1a {
		if _, ok := ax1Bool(c.Out["pass"]); !ok {
			t.Errorf("اوراکل %s: pass باید bool باشد، نوع %s", c.Symbol, ax1Kind(c.Out["pass"]))
		}
		if ax1Kind(c.Out["unit"]) != "null" {
			t.Errorf("اوراکل %s: unit باید null باشد، نوع %s", c.Symbol, ax1Kind(c.Out["unit"]))
		}
	}
}

// ── لایۀ ۱ب ──────────────────────────────────────────────────────────────────

func TestAx1Ind1bMatchesOracle(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	levels := map[string]int{}
	withNote := 0
	for _, c := range v.Ind1b {
		mon, err := s.Ind1aMonetaryGrowth(ctx, c.Symbol, ax1SeriesFor(v, c.Symbol), nil,
			ax1ProfileFor(v, c.Symbol))
		if err != nil {
			t.Fatalf("%s: ind1a برایِ ورودیِ ind1b: %v", c.Symbol, err)
		}
		got, err := s.Ind1bVolumeGrowth(ctx, c.Symbol, mon, ax1SeriesFor(v, c.Symbol), nil,
			ax1ProfileFor(v, c.Symbol))
		if err != nil {
			t.Fatalf("%s: ind1b: %v", c.Symbol, err)
		}
		if msg, ok := ax1CompareMap(c.Symbol, c.Out, got); !ok {
			t.Errorf("ind1b %s: %s", c.Symbol, msg)
		}
		if lvl, ok := got["basis"].(string); ok {
			levels[lvl]++
		}
		if _, ok := got["note_breadth"]; ok {
			withNote++
		}
	}
	// دو سطحِ پرتکرارِ اوراکل باید ببینیم؛ سطح A با آزمونِ فیکسچرِ پایینِ همین‌جا
	// سنجیده می‌شود (درِ این پنج کیس فعال نیست چون ستونِ فیزیکی پُر نیست).
	if levels["price_effect_decomposition"] == 0 || levels["unavailable"] == 0 {
		t.Errorf("سطح‌هایِ اوراکل پوشش داده نشدند: %v", levels)
	}
	if withNote == 0 {
		t.Errorf("هیچ کیسی note_breadth ندارد — پهنایِ رشدِ نمایشی هیچ‌وقت اجرا نشده")
	}
}

// TestAx1Ind1bWithoutMonetary همان کیس‌ها را با `monetary=nil` صدا می‌زند:
// اوراکل خودش ۱الف را می‌سازد و باید پاسخِ یکی بیرون بیاید.
func TestAx1Ind1bWithoutMonetary(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	for _, c := range v.Ind1b {
		got, err := s.Ind1bVolumeGrowth(ctx, c.Symbol, nil, ax1SeriesFor(v, c.Symbol), nil,
			ax1ProfileFor(v, c.Symbol))
		if err != nil {
			t.Fatalf("%s: ind1b بی monetary: %v", c.Symbol, err)
		}
		if msg, ok := ax1CompareMap(c.Symbol, c.Out, got); !ok {
			t.Errorf("ind1b (بی monetaryِ آماده) %s: %s", c.Symbol, msg)
		}
	}
}

// TestAx1BreadthIsDisplayOnly: پهنا رأیِ ۱ب را جابه‌جا نمی‌کند. انتظار از خودِ
// فایلِ داور می‌آید: درِ هر کیس، رأیِ `pass` باید با `real_pct` و `threshold`ِ
// همان کیس بخورد، حتی وقتی پهنایِ رشد صفر است یا «همه ماه‌ها بهتر شده».
func TestAx1BreadthIsDisplayOnly(t *testing.T) {
	v := ax1LoadVectors(t)
	checked, zeroBreadth := 0, 0
	for _, c := range v.Ind1b {
		g := c.Out
		br, ok := g["breadth"].(map[string]any)
		if !ok {
			continue
		}
		rulesPass := false
		if r, ok := ax1Num(g["real_pct"]); ok {
			th, _ := ax1Num(g["threshold"])
			rulesPass = r >= th
		}
		if got, ok := ax1Bool(g["pass"]); !ok || got != rulesPass {
			t.Errorf("%s: pass=%v با رأیِ تعدیلِ تورمِ خودِ اوراکل (%v) نمی‌خواند — ratio=%v",
				c.Symbol, g["pass"], rulesPass, br["ratio"])
		}
		if ratio, ok := ax1Num(br["ratio"]); ok && ratio == 0 {
			zeroBreadth++
			if _, hasNote := g["note_breadth"]; !hasNote {
				t.Errorf("%s: پهنایِ صفر بدونِ note_breadth — نمایشِ پهنا شکسته", c.Symbol)
			}
		}
		checked++
	}
	if checked < 3 || zeroBreadth == 0 {
		t.Errorf("پهنایِ رشد کم سنجیده شد: کیس=%d کیسِ بی‌پهنا=%d", checked, zeroBreadth)
	}
}

// TestAx1PhysicalPairOnFixture لایۀ ستونِ فیزیکی را رویِ فیکسچر می‌سنجد. واقعیتِ
// اندازه‌گیری‌شدۀ همین فیکسچر: `monthly_sales` ستونِ ytd_volume دارد ولی مقدارش
// NULL است، پس کمیت و مخرجِ فیزیکی nil می‌مانند و ۱ب به تعدیلِ تورمی تنزل
// می‌کند — همان چیزی که درِ پنجِ کیسِ اوراکل (basis ≠ reported_quantity) دیدنی است.
func TestAx1PhysicalPairOnFixture(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	ran := 0
	for _, c := range v.Ind1a {
		year, month := c.Out["year"], c.Out["months"]
		if year == nil || month == nil {
			continue
		}
		now, back, col := s.ax1PhysicalPair(ctx, c.Symbol, year, month)
		g := ax1Ind1bFor(v, c.Symbol)
		if col != "" && (ax1Kind(now) != "null" || ax1Kind(back) != "null") {
			if g["basis"] != "reported_quantity" {
				t.Errorf("%s: ستون %q مقدار دارد (now=%v back=%v) ولی اوراکل basis را "+
					"reported_quantity ننوشته — یکی از دو باید عوض شود", c.Symbol, col, now, back)
			}
		}
		if g["basis"] == "reported_quantity" && col == "" {
			t.Errorf("%s: اوراکل سطح A دیده ولی هیچِ ستونی پیدا نشد", c.Symbol)
		}
		ran++
	}
	if ran < 3 {
		t.Errorf("جفتِ فیزیکی برایِ %d نماد سنجیده شد (حداقلِ انتظار ۳)", ran)
	}
}

// ── رأیِ لایۀ ۱ و سه‌حالۀ پنج‌محوره ──────────────────────────────────────────

func TestAx1Axis1PassMatchesOracle(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	seen := map[string]int{}
	for _, c := range v.Axis1 {
		series := ax1SeriesFor(v, c.Symbol)
		prof := ax1ProfileFor(v, c.Symbol)
		mon, err := s.Ind1aMonetaryGrowth(ctx, c.Symbol, series, nil, prof)
		if err != nil {
			t.Fatalf("%s: ind1a: %v", c.Symbol, err)
		}
		vol, err := s.Ind1bVolumeGrowth(ctx, c.Symbol, mon, series, nil, prof)
		if err != nil {
			t.Fatalf("%s: ind1b: %v", c.Symbol, err)
		}
		want, ok := ax1Bool(ax1JSONValue(t, c.Out))
		if !ok {
			t.Fatalf("axis1 %s: خروجیِ اوراکل bool نیست (%s)", c.Symbol, ax1Kind(c.Out))
		}
		got := Axis1Pass(mon, vol)
		if got != want {
			t.Errorf("axis1_pass %s = %v want %v (monetary.pass=%v applicable=%v volume.pass=%v data_gap=%v)",
				c.Symbol, got, want, mon["pass"], vol["applicable"], vol["pass"], vol["data_gap"])
		}
		if want {
			seen["true"]++
		} else {
			seen["false"]++
		}
		if _, ok := ax1Bool(vol["pass"]); !ok {
			t.Errorf("%s: volume.pass درِ اوراکل bool نیست (%s)", c.Symbol, ax1Kind(vol["pass"]))
		}
	}
	if seen["true"] == 0 || seen["false"] == 0 {
		t.Errorf("هر دو رأیِ true/false درِ کیس‌ها لازم است، دیدیم %v", seen)
	}
}

// ax1JSONValue خروجیِ خام (RawMessage) را به همان ارزشِ JSONِ اوراکل برمی‌گرداند
// تا bool/null/object با هم قاطی نشوند.
func ax1JSONValue(t *testing.T, raw json.RawMessage) any {
	t.Helper()
	if len(raw) == 0 {
		return nil
	}
	var val any
	if err := json.Unmarshal(raw, &val); err != nil {
		t.Fatalf("تجزیۀ out: %v", err)
	}
	return val
}

// TestAx1StatesTristate سه‌حالۀ `v10_axis_states` را با اوراکل می‌زند.
//
// فایلِ داور برایِ محورهای ۲..۴ هیچ شاخصی نمی‌فرستد (هر کیس فقط symbol/out
// دارد)، پس ستونِ 1_growth مقداراً با پنجِ ردیفِ اوراکل مقایسه می‌شود — ورودی‌ها
// خودِ پاسخ‌هایِ پایتون‌اند — و برایِ بقیۀ محورها فقط «پنجِ کلید + نوعِ nil/bool»
// سنجیده می‌شود. قاعدۀ خودِ آن چهار شاخه درِ جدولِ پایینِ همین آزمون آمده و
// ورودی‌اش ساختگیِ قاعده است، یعنی «با داور راستی‌آزمایی نشده».
func TestAx1StatesTristate(t *testing.T) {
	v := ax1LoadVectors(t)
	matched, nilSeen := 0, 0
	for _, c := range v.States {
		mon := ax1Ind1aFor(v, c.Symbol)
		if mon == nil {
			t.Errorf("%s: کیسِ ind1a ندارد — ستونِ 1_growth سنجیده نشد", c.Symbol)
			continue
		}
		got := V10AxisStates(map[string]any{"1": map[string]any{"monetary": mon}},
			map[string]any{"1_growth": mon["pass"]})
		for _, k := range []string{"1_growth", "2_eps_trend", "3_gross_margin",
			"4_sales_to_mcap", "5_industry"} {
			if _, ok := got[k]; !ok {
				t.Errorf("%s: کلید %q درِ خروجی نیست", c.Symbol, k)
			}
		}
		if len(got) != 5 {
			t.Errorf("%s: پنجِ کلید انتظار است، got %d", c.Symbol, len(got))
		}
		for k, val := range got {
			if val == nil {
				nilSeen++
				continue
			}
			if _, ok := ax1Bool(val); !ok {
				t.Errorf("%s.%s: بی bool و بی nil نیست (%s)", c.Symbol, k, ax1Kind(val))
			}
		}
		if msg, ok := ax1ValuesEqual(c.Symbol+".1_growth", c.Out["1_growth"], got["1_growth"]); !ok {
			t.Errorf("v10_axis_states %s", msg)
		} else {
			matched++
		}
	}
	if matched != len(v.States) {
		t.Errorf("ستونِ 1_growth برایِ %d/%d کیس سنجیده شد", matched, len(v.States))
	}
	if nilSeen == 0 {
		t.Errorf("هیچ محوری بی‌نظر نشد — سه‌حالۀ nil هیچ‌وقت اجرا نشده")
	}

	// قاعدۀ خودِ اوراکل (خط‌هایِ ۷۲۱ تا ۷۲۸): هر کدام از این شاخه‌ها باید nil
	// بدهد؛ بی‌درخواستِ عددی. (راستی‌آزمایی با داورِ عددی: نشده.)
	nilCases := []struct {
		name string
		key  string
		ind  map[string]any
	}{
		{"1 data_gap", "1_growth", map[string]any{"1": map[string]any{
			"monetary": map[string]any{"data_gap": true, "monetary_pct": 80.0}}}},
		{"1 بی عدد", "1_growth", map[string]any{"1": map[string]any{
			"monetary": map[string]any{"monetary_pct": nil}}}},
		{"2 na", "2_eps_trend", map[string]any{"2": map[string]any{"na": true, "pass": true}}},
		{"2 gap", "2_eps_trend", map[string]any{"2": map[string]any{"data_gap": true, "pass": true}}},
		{"2 بی رأی", "2_eps_trend", map[string]any{"2": map[string]any{"pass": nil}}},
		{"3 na", "3_gross_margin", map[string]any{"3": map[string]any{
			"na": true, "margin_pct": 25.0}}},
		{"3 بی‌معنا", "3_gross_margin", map[string]any{"3": map[string]any{
			"band": "not_applicable", "margin_pct": 25.0}}},
		{"3 بی عدد", "3_gross_margin", map[string]any{"3": map[string]any{"margin_pct": nil}}},
		{"4 na", "4_sales_to_mcap", map[string]any{"4": map[string]any{"na": true}}},
		{"4 exempt", "4_sales_to_mcap", map[string]any{"4": map[string]any{"exempt": true}}},
		{"4 موجود نیست", "4_sales_to_mcap", map[string]any{"4": map[string]any{"available": false}}},
	}
	for _, tc := range nilCases {
		got := V10AxisStates(tc.ind, map[string]any{tc.key: true})
		if got[tc.key] != nil {
			t.Errorf("قاعدۀ %q: انتظارِ nil، got %v", tc.name, got[tc.key])
		}
	}
	// `available`ِ غایب باید True خوانده شود (پیش‌فرضِ .get) و Noneِ حاضر بی‌نظر
	// بدهد — خطِ ۷۲۷، همان جایی که `or` نمی‌تواند جایش را بگیرد.
	withOut := V10AxisStates(map[string]any{"4": map[string]any{}},
		map[string]any{"4_sales_to_mcap": true})
	if withOut["4_sales_to_mcap"] != true {
		t.Errorf("کلیدِ غایبِ available باید True بخواند، got %v", withOut["4_sales_to_mcap"])
	}
	withNil := V10AxisStates(map[string]any{"4": map[string]any{"available": nil}},
		map[string]any{"4_sales_to_mcap": true})
	if withNil["4_sales_to_mcap"] != nil {
		t.Errorf("available=nil باید بی‌نظر بدهد، got %v", withNil["4_sales_to_mcap"])
	}
	// رأیِ نهاییِ layeh ۱ وقتی ۱الف رد است: false، حتی اگر ۱ب applicable نباشد.
	if Axis1Pass(map[string]any{"pass": false}, map[string]any{"applicable": false, "pass": true}) {
		t.Error("rأیِ ۱الف رد را هیچ N/Aی جبران نمی‌کند")
	}
}

// ── ورودیِ طبقه‌بندی و گرامِ رشته‌ها ──────────────────────────────────────────

// TestAx1ProfileVectorsLoad ثابت می‌کند ورودیِ ۱الف/۱ب از داور می‌آید: سه فیلدِ
// مصرفیِ من درِ پنجِ کیس پرند. طبقه‌بندیِ کامل کارِ فایلِ همسایه است.
func TestAx1ProfileVectorsLoad(t *testing.T) {
	v := ax1LoadVectors(t)
	emptySector := 0
	for _, c := range v.Profile {
		for _, k := range []string{"revenue_basis", "volume_applicable", "volume_note"} {
			val, ok := c.Out[k]
			if !ok {
				t.Errorf("profile %s: کلید %q غایب است", c.Symbol, k)
				continue
			}
			if ax1Kind(val) == "null" {
				t.Errorf("profile %s: کلید %q درِ اوراکل null است", c.Symbol, k)
			}
		}
		if _, ok := ax1Bool(c.Out["volume_applicable"]); !ok {
			t.Errorf("profile %s: volume_applicable bool نیست (%s)", c.Symbol,
				ax1Kind(c.Out["volume_applicable"]))
		}
		if c.Sector == "" {
			emptySector++
			// `company_profile()`ِ بی‌آرگومان = صنعتِ خالی + نامِ خالی، یعنی همین
			// کیس؛ پس شکلِ پیش‌فرضِ من با اوراکل سنجیدنی است.
			if msg, ok := ax1CompareMap("ax1DefaultProfile", c.Out, ax1DefaultProfile()); !ok {
				t.Errorf("ax1DefaultProfile ≠ company_profile() درِ اوراکل: %s", msg)
			}
		}
	}
	if emptySector == 0 {
		t.Error("کیسِ بی‌صنعت درِ profile نیست — پیش‌فرضِ بی‌آرگومان راستی‌آزمایی نشده")
	}
}

// TestAx1LiteralsAreOracleVerbatim رشته‌هایِ کاربر-دیدنیِ axis1.go را با خودِ
// سورسِ پایتون مقایسه می‌کند: هر نسخۀ تازه باید عیناً درِ api/fundamental.py
// (یا fts_engine.py برایِ طبقه‌بندی) پیدا شود. این همان گرامِ «رقمِ دزدیده‌شده»ِ
// dev/persian_glyph_guard.py است، ولی رویِ هر دو زبان.
func TestAx1LiteralsAreOracleVerbatim(t *testing.T) {
	goSrc, err := os.ReadFile("axis1.go")
	if err != nil {
		t.Fatalf("خواندنِ axis1.go: %v", err)
	}
	oracle, err := os.ReadFile(ax1OraclePy)
	if err != nil {
		t.Skipf("سورسِ اوراکل درِ این مسیر نیست: %v — راستی‌آزمایی نشده", err)
	}
	fts, err := os.ReadFile(ax1FtsPy)
	if err != nil {
		t.Skipf("fts_engine.py نیست: %v — راستی‌آزمایی نشده", err)
	}
	hay := string(oracle) + "\n" + string(fts)
	re := regexp.MustCompile(`"([^"\n]*[^\x00-\x7F][^"\n]*)"`)
	checked := map[string]bool{}
	for _, m := range re.FindAllStringSubmatch(string(goSrc), -1) {
		lit := m[1]
		if checked[lit] {
			continue
		}
		checked[lit] = true
		if !strings.Contains(hay, lit) {
			t.Errorf("رشتۀ %q عیناً درِ سورسِ پایتون نیست (هجنگ/رقم/گیومه را بسنج)", lit)
		}
	}
	if len(checked) < 12 {
		t.Errorf("تنها %d رشته سنجیده شد — انتظارِ حداقلِ دوازده", len(checked))
	}
}

// ── تبدیل‌ها، با ورودیِ خودِ کیس‌ها ───────────────────────────────────────────

func TestAx1ConversionsFromOracle(t *testing.T) {
	v := ax1LoadVectors(t)
	btCases, pctCases, periodCases, realCases, reasonCases := 0, 0, 0, 0, 0

	for _, c := range v.Ind1a {
		g := c.Out
		if now, ok := ax1Num(g["ytd_now_mrl"]); ok {
			if msg, ok := ax1ValuesEqual(c.Symbol+".ytd_now_bt", g["ytd_now_bt"], ax1Bt(now)); !ok {
				t.Errorf("ax1Bt: %s", msg)
			}
			btCases++
		}
		if prev, ok := ax1Num(g["ytd_prev_mrl"]); ok {
			if msg, ok := ax1ValuesEqual(c.Symbol+".ytd_prev_bt", g["ytd_prev_bt"], ax1Bt(prev)); !ok {
				t.Errorf("ax1Btِ مخرج: %s", msg)
			}
			btCases++
		}
		if b, ok := ax1Bool(g["data_gap"]); ok && !b {
			now, _ := ax1Num(g["ytd_now_mrl"])
			prev, _ := ax1Num(g["ytd_prev_mrl"])
			if msg, ok := ax1ValuesEqual(c.Symbol+".monetary_pct", g["monetary_pct"],
				ax1Pct(now, prev)); !ok {
				t.Errorf("ax1Pct: %s", msg)
			}
			pctCases++
		}
		if _, ok := g["period"].(string); ok {
			month, _ := ax1Num(g["months"])
			year, _ := ax1Num(g["year"])
			if want := ax1Period(int64(month), int64(year)); want != g["period"] {
				t.Errorf("period %s: اوراکل %v و Sprintfِ من %q", c.Symbol, g["period"], want)
			}
			periodCases++
		}
		// `ref_period_end` عینِ ششمینِ ستونِ نخستینِ ردیفِ سری است — و فقط درِ
		// شاخۀ موفق نوشته می‌شود (شکلِ _nodata آن را ندارد).
		if _, has := g["ref_period_end"]; has {
			if series := ax1SeriesFor(v, c.Symbol); len(series) > 0 {
				if msg, ok := ax1ValuesEqual(c.Symbol+".ref_period_end", g["ref_period_end"],
					ax1Cell(series[0], 5)); !ok {
					t.Errorf("ref_period_end: %s", msg)
				}
			}
		}
	}
	if btCases < 4 || pctCases < 3 || periodCases < 3 {
		t.Errorf("تبدیل‌ها کم سنجیده شدند: bt=%d pct=%d period=%d", btCases, pctCases, periodCases)
	}

	for _, c := range v.Ind1b {
		g := c.Out
		if g["basis"] != "price_effect_decomposition" {
			continue
		}
		monetaryPct := ax1Ind1aFor(v, c.Symbol)["monetary_pct"]
		if msg, ok := ax1ValuesEqual(c.Symbol+".real_pct", g["real_pct"],
			ax1RealGrowth(monetaryPct, g["price_benchmark_pct"])); !ok {
			t.Errorf("ax1RealGrowth: %s", msg)
		}
		realCases++
		// متنِ رأیِ ۱ب هم از ارقامِ همان کیس ساخته می‌شود، پس با Sprintfِ من باید
		// یکی بماند (رقمِ ASCIIِ %+.1f/%.0f بخشی از قرارداد است).
		if r, ok := g["reason"].(string); ok && strings.HasPrefix(r, "رشد اسمی ") {
			mon, _ := ax1Num(monetaryPct)
			bench, _ := ax1Num(g["price_benchmark_pct"])
			if want := fmt.Sprintf(ax1ReasonRealFail, mon, bench); want != r {
				t.Errorf("reasonِ ۱ب %s: بازسازیِ من %q ≠ اوراکل %q", c.Symbol, want, r)
			}
			reasonCases++
		}
	}
	if realCases < 3 || reasonCases < 3 {
		t.Errorf("لایۀ واقعی/متنِ رأی کم سنجیده شد: real=%d reason=%d (حداقلِ انتظار ۳)",
			realCases, reasonCases)
	}
}

// TestAx1BoundaryFromVectors مرزهایی که داور واقعاً می‌زند، بی‌عددِ تایپ‌شدۀ من:
// درِ همین پنج کیس هم «بالایِ کف» و هم «زیرِ کف» و هم «بینِ کف و هدف» هست و یکِ
// کیس بی‌مخرج رأیِ nil می‌گیرد. پس هم دروازۀ قبولی دو طرفه سنجیده شده و هم شاخۀ
// data_gap؛ برایِ کیسِ بینِ کف و هدف، فاصلگیِ بالاِ کف هم باید صفر نباشد (آن نماد
// دقیقاً یکِ قدمِ کوچک بالایِ کف است، نه رویِ کف).
func TestAx1BoundaryFromVectors(t *testing.T) {
	v := ax1LoadVectors(t)
	aboveFloor, belowFloor, between, gaps := 0, 0, 0, 0
	for _, c := range v.Ind1a {
		g := c.Out
		if b, _ := ax1Bool(g["data_gap"]); b {
			gaps++
			if g["monetary_pct"] != nil {
				t.Errorf("%s: data_gap=true ولی monetary_pct عدد دارد (%v)",
					c.Symbol, g["monetary_pct"])
			}
			if _, ok := g["strong"]; ok {
				t.Errorf("%s: شاخۀ گپ نباید کلیدِ strong داشته باشد", c.Symbol)
			}
			continue
		}
		pct, ok := ax1Num(g["monetary_pct"])
		if !ok {
			continue
		}
		floor, okF := ax1Num(g["threshold"])
		if !okF {
			t.Errorf("%s: آستانه درِ کیس نیست", c.Symbol)
			continue
		}
		if got, _ := ax1Bool(g["pass"]); got != (pct >= floor) {
			t.Errorf("%s: pass=%v ولی pct=%v و کفِ خودِ اوراکل=%v", c.Symbol, got, pct, floor)
		}
		if target, okT := ax1Num(g["target_threshold"]); okT {
			if got, _ := ax1Bool(g["strong"]); got != (pct >= target) {
				t.Errorf("%s: strong=%v ولی pct=%v و هدفِ خودِ اوراکل=%v",
					c.Symbol, got, pct, target)
			}
			if pct >= floor && pct < target {
				between++
				if pct-floor <= 0 {
					t.Errorf("%s: کیسِ «بینِ کف و هدف» رویِ کف نشسته (فاصله=%v)", c.Symbol, pct-floor)
				}
			}
		}
		if pct >= floor {
			aboveFloor++
		} else {
			belowFloor++
		}
	}
	if aboveFloor == 0 || belowFloor == 0 {
		t.Errorf("یکِ طرفِ دروازۀ قبولی سنجیده نشده: بالا=%d پایین=%d", aboveFloor, belowFloor)
	}
	if between == 0 {
		t.Error("هیچ کیسی بینِ کف و هدف نیست — برچسبِ «رشد قوی» و مرزِ یک‌قدم‌بالایِ کف پوشش داده نشد")
	}
	if gaps == 0 {
		t.Error("هیچ کیسی data_gap ندارد — شاخۀ «مقایسۀ سال‌به‌سال ممکن نیست» سنجیده نشد")
	}
}

// TestAx1ZeroRevenueStaysZero ثابت می‌کند چرا `ax1MsSeries` کپیِ `SeriesMsRows`
// است نه فراخوانِ آن: درِ ردیف‌هایِ اوراکل `monthly_revenue: 0.0` کنارِ
// `ytd_revenue_prev: null` می‌نشیند، و `_num_or_none(0.0)` درِ پایتون همان ۰٫۰ را
// نگه می‌دارد. بی‌این تفکیک، صفرِ واقعی «بی‌داده» خوانده می‌شد.
func TestAx1ZeroRevenueStaysZero(t *testing.T) {
	v := ax1LoadVectors(t)
	ctx := context.Background()
	s := ax1OpenFixture(t)

	zeroRows, verified := 0, 0
	for _, c := range v.Ind1a {
		hasZero := false
		for _, item := range ax1AsSlice(c.Out["series"]) {
			row := ax1AsMap(item)
			if f, ok := ax1Num(row["monthly_revenue"]); ok && f == 0 {
				zeroRows++
				hasZero = true
			}
		}
		if !hasZero {
			continue
		}
		got, err := s.Ind1aMonetaryGrowth(ctx, c.Symbol, ax1SeriesFor(v, c.Symbol), nil,
			ax1ProfileFor(v, c.Symbol))
		if err != nil {
			t.Fatalf("%s: ind1a: %v", c.Symbol, err)
		}
		for _, g := range ax1AsSlice(got["series"]) {
			if f, ok := ax1Num(ax1AsMap(g)["monthly_revenue"]); ok && f == 0 {
				verified++
			}
		}
	}
	if zeroRows == 0 {
		t.Error("فیکسچر ردیفِ monthly_revenue=0 ندارد — گرامِ صفر/nil سنجیده نشد")
	}
	if verified != zeroRows {
		t.Errorf("ردیفِ صفر: اوراکل %d و خروجیِ Go %d — صفر نباید nil شود", zeroRows, verified)
	}
	// خودِ تبدیل: صفر می‌ماند، nil و رشتهٔ خالی می‌روند (قواعدِ `_num_or_none`).
	for _, tc := range []struct {
		in   any
		kind string
		num  float64
	}{
		{0.0, "number", 0}, {nil, "null", 0}, {"", "null", 0}, {2.5, "number", 2.5},
	} {
		got := ax1NumOrNull(tc.in)
		if ax1Kind(got) != tc.kind {
			t.Errorf("ax1NumOrNull(%v) نوع=%s want %s", tc.in, ax1Kind(got), tc.kind)
		}
		if tc.kind == "number" {
			if f, _ := ax1Num(got); f != tc.num {
				t.Errorf("ax1NumOrNull(%v)=%v want %v", tc.in, got, tc.num)
			}
		}
	}
}

// TestAx1NoSeriesNodataShape شکلِ `_nodata` را برایِ نمادی بی‌گزارش می‌سنجد.
// فهرستِ کلیدها از خودِ سورسِ پایتون خوانده می‌شود (ax1NoSeriesKeys)، پس شمار
// و اسمِ کلیدها انتظارِ تایپ‌شدۀ من نیست. متنِ reason/remediation این شاخه درِ
// هیچِ کیسِ عددیِ این فایل نیست؛ برابریِ رشته‌ها را آزمونِ verbatimِ بالا می‌سنجد
// و راستی‌آزماییِ عددیِ آن دو رشته: نشده.
func TestAx1NoSeriesNodataShape(t *testing.T) {
	ctx := context.Background()
	s := ax1OpenFixture(t)

	got, err := s.Ind1aMonetaryGrowth(ctx, "نماد بی گزارش", [][]any{}, nil, nil)
	if err != nil {
		t.Fatalf("ind1a بی سری: %v", err)
	}
	base := ax1NoSeriesKeys(t)
	for _, k := range base {
		if _, ok := got[k]; !ok {
			t.Errorf("کلید %q درِ پاسخِ بی‌داده نیست", k)
		}
	}
	if len(got) != len(base) {
		t.Errorf("پاسخِ بی‌داده %d کلید دارد want %d (هیچ extra نباید اضافه شود)",
			len(got), len(base))
	}
	if len(ax1AsSlice(got["series"])) != 0 {
		t.Errorf("series باید تهی باشد: %v", got["series"])
	}
	if b, _ := ax1Bool(got["data_gap"]); !b {
		t.Errorf("data_gap باید true باشد، got %v", got["data_gap"])
	}
	if got["monetary_pct"] != nil {
		t.Errorf("monetary_pct باید nil بماند، got %v", got["monetary_pct"])
	}
	if p, _ := ax1Bool(got["pass"]); p {
		t.Error("رأیِ بی‌داده هرگز pass نیست")
	}
	if got["unit"] != nil {
		t.Errorf("unit باید nil باشد، got %v", got["unit"])
	}
	if r, _ := got["reason"].(string); r == "" {
		t.Error("reason خالی است")
	}
}

// ax1NoSeriesKeys کلیدهایِ ثابتِ `_nodata` را از بدنةِ همان تابع درِ
// api/fundamental.py بیرون می‌کشد (پیشِ هر extra)؛ بی‌سورسِ پایتون آزمون شکست
// می‌خورد تا «سبزِ ساختگی» نشود.
func ax1NoSeriesKeys(t *testing.T) []string {
	t.Helper()
	src, err := os.ReadFile(ax1OraclePy)
	if err != nil {
		t.Skipf("سورسِ اوراکل نیست: %v — راستی‌آزمایی نشده", err)
	}
	i := strings.Index(string(src), "def _nodata(reason, **extra)")
	if i < 0 {
		t.Fatal("ساختارِ _nodata درِ اوراکل پیدا نشد")
	}
	lines := strings.Split(string(src)[i:], "\n")
	re := regexp.MustCompile(`"([a-z_]+)":`)
	var keys []string
	stop := false
	for _, line := range lines[1:] {
		if strings.Contains(line, "gap.update(extra)") {
			stop = true
			break
		}
		for _, m := range re.FindAllStringSubmatch(line, -1) {
			keys = append(keys, m[1])
		}
	}
	if !stop {
		t.Fatal("پایانِ بدنة _nodata درِ اوراکل پیدا نشد")
	}
	if len(keys) < 8 {
		t.Fatalf("کلیدهایِ _nodata کم است: %v", keys)
	}
	return keys
}
