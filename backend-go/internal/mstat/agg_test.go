package mstat

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"
)

// TestAggUnit قیدهایِ _agg را رویِ ردیف‌هایِ دست‌ساز قفل می‌کند: شمارشِ
// معامله‌شده فقط با val>0، عمق فقط با bq_valِ موجود، NaN در سه خانهٔ دیگرِ
// عمق صفر می‌شود، و سرانه/قدرت می‌توانند None (NaN) بمانند.
func TestAggUnit(t *testing.T) {
	t.Run("counts and depth", func(t *testing.T) {
		rows := []*Row{
			{M: Money{Val: 1e10, Vol: 2e9, BQVal: 4e10, SQVal: 6e10, BQVol: 7, SQVol: 8}},
			// bq_val غایب است: پایتون کلِ بلوکِ عمق را رد می‌کند، پس حتی
			// sq_valِ موجودِ همین ردیف هم جمع نمی‌شود.
			//
			// این حالتِ دست‌ساز تنها نگهبانِ همین قاعده است: در فیکسچرِ s1 هر
			// ۳۸ ردیف bq_val/sq_val/bq_vol/sq_volِ غیرتهی دارند، پس تستِ اوراکل
			// به‌تنهایی نمی‌تواند شاخهٔ `or 0.0` را بگیرد.
			{M: Money{Val: 0, BQVal: math.NaN(), SQVal: 1e9}},
			// صفرِ واقعیِ صف «بی‌داده» نیست: depth را می‌شمارد و صفر جمع می‌کند.
			{M: Money{Val: 5, BQVal: 0, SQVal: math.NaN(),
				BQVol: math.NaN(), SQVol: math.NaN()}},
		}
		a := aggOf(rows)
		if a.N != 3 || a.NTraded != 2 {
			t.Fatalf("n/n_traded = %d/%d, want 3/2", a.N, a.NTraded)
		}
		if a.DepthN != 2 {
			t.Fatalf("depth_n = %d, want 2 (NaN bq_val is not depth)", a.DepthN)
		}
		if a.Vol != 2e9 || a.Val != 1e10+5 {
			t.Fatalf("vol/val = %v/%v, want %v/%v", a.Vol, a.Val, 2e9, 1e10+5)
		}
		if a.BQ != 4e10 || a.SQ != 6e10 {
			t.Fatalf("bq/sq = %v/%v, want 4e10/6e10", a.BQ, a.SQ)
		}
		if a.BQV != 7 || a.SQV != 8 {
			t.Fatalf("bqv/sqv = %v/%v, want 7/8 (NaN counts as 0)", a.BQV, a.SQV)
		}
	})

	t.Run("per capita and power", func(t *testing.T) {
		// rb/nbi = 2e7/2 = 1e7 ⇒ ۱ میلیون تومان؛ rs/nsi = 1e7/2 ⇒ ۰٫۵؛
		// قدرت = ۱ ÷ ۰٫۵ = ۲.
		a := aggOf([]*Row{{M: Money{RetailBuy: 2e7, RetailSell: 1e7, NBuyI: 2, NSellI: 2}}})
		if a.PCBuymt != 1.0 || a.PCSellmt != 0.5 || a.Power != 2.0 {
			t.Fatalf("pc/power = %v/%v/%v, want 1/0.5/2",
				a.PCBuymt, a.PCSellmt, a.Power)
		}
		// nbi=0 ⇒ سرانهٔ خرید None، و در نتیجه قدرت هم None.
		a = aggOf([]*Row{{M: Money{RetailBuy: 5, NBuyI: 0, NSellI: 1}}})
		if !isNaN(a.PCBuymt) || !isNaN(a.Power) {
			t.Fatalf("nbi=0 pc_buy/power = %v/%v, want NaN/NaN", a.PCBuymt, a.Power)
		}
		// nsi=0 ⇒ سرانهٔ فروش None (نه صفر) و قدرت None.
		a = aggOf([]*Row{{M: Money{RetailBuy: 2e7, NBuyI: 2, NSellI: 0}}})
		if !isNaN(a.PCSellmt) || !isNaN(a.Power) {
			t.Fatalf("nsi=0 pc_sell/power = %v/%v, want NaN/NaN", a.PCSellmt, a.Power)
		}
		// صفرِ واقعیِ فروش سرانهٔ صفر می‌دهد (نه None)، ولی قدرت تقسیم بر
		// صفر است ⇒ None. این همان تفاوتِ «۰» و «ساختنی نبود» است.
		a = aggOf([]*Row{{M: Money{RetailBuy: 1e7, RetailSell: 0, NBuyI: 1, NSellI: 4}}})
		if a.PCSellmt != 0 || !isNaN(a.Power) {
			t.Fatalf("zero sell pc/power = %v/%v, want 0/NaN", a.PCSellmt, a.Power)
		}
		// دستهٔ خالی: همهٔ جمع‌ها صفر، هر دو سرانه و قدرت None.
		a = aggOf(nil)
		if a.N != 0 || a.Val != 0 || !isNaN(a.PCBuymt) || !isNaN(a.PCSellmt) || !isNaN(a.Power) {
			t.Fatalf("empty agg = %+v", a)
		}
	})

	t.Run("display units", func(t *testing.T) {
		// هر یکا رویِ توانِ دقیقِ ده سنجیده می‌شود تا ضریبِ 1e9/1e10/1e3
		// جابه‌جا نماند: ۱e9 سهم = ۱ میلیارد سهم، ۱e10 ریال = ۱ میلیارد تومان،
		// و ۱۰۰۰ میلیارد تومان = ۱ همت.
		a := aggOf([]*Row{{M: Money{
			Val: 1e10, Vol: 1e9, RetailBuy: 2e10, RetailSell: 1e10,
			BQVal: 1e10, SQVal: 1e10,
		}}})
		if a.FlowBT != 1 || a.VolBS != 1 || a.ValBT != 1 || a.ValHemat != 0.001 ||
			a.BQBt != 1 || a.SQBt != 1 {
			t.Fatalf("units = flow %v vol %v val %v hemat %v bq %v sq %v, want 1/1/1/0.001/1/1",
				a.FlowBT, a.VolBS, a.ValBT, a.ValHemat, a.BQBt, a.SQBt)
		}
		if a.FlowBT != (2e10-1e10)/1e10 {
			t.Fatalf("flow_bt = %v, want (rb-rs)/1e10", a.FlowBT)
		}
	})
}

// oracleRow همان ردیفِ دامپِ اوراکل است؛ `m` عیناً همان ارقامِ پایتون است.
type oracleRow struct {
	Code  string         `json:"ins_code"`
	Top50 bool           `json:"top50"`
	M     map[string]any `json:"m"`
}

type oracleDump struct {
	AsOf map[string]any `json:"asof"`
	Rows []oracleRow    `json:"rows"`
}

func readOracleDump(t *testing.T) oracleDump {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", "s1", "enrich.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g oracleDump
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// oracleNum یک خانهٔ m را می‌خواند: null یعنی «نبود» (ok=false)، مثلِ None.
func oracleNum(t *testing.T, m map[string]any, key string) (float64, bool) {
	t.Helper()
	v, ok := m[key]
	if !ok {
		t.Fatalf("golden m has no key %q", key)
	}
	if v == nil {
		return 0, false
	}
	f, ok := v.(float64)
	if !ok {
		t.Fatalf("golden m[%q] is %T, want number", key, v)
	}
	return f, true
}

func oracleMust(t *testing.T, m map[string]any, key string) float64 {
	t.Helper()
	f, ok := oracleNum(t, m, key)
	if !ok {
		t.Fatalf("golden m[%q] is null, want number", key)
	}
	return f
}

func oracleInt(t *testing.T, m map[string]any, key string) int64 {
	t.Helper()
	return int64(oracleMust(t, m, key))
}

// pyDiv همان _divِ پایتون رویِ دو عددِ موجود: مخرجِ صفر ⇒ None.
func pyDiv(a, b float64) float64 {
	if math.IsNaN(a) || math.IsNaN(b) || b == 0 {
		return math.NaN()
	}
	return a / b
}

// pythonAgg همان _agg را از رویِ ارقامِ طلاییِ پایتون بازمی‌سازد — بدونِ
// money()ِ Go، تا تست تجمیع، تجمیعِ Go را با خودش نسنجد. ترتیبِ جمع همان
// ترتیبِ ردیف‌هایِ طلایی است، پس تساویِ دقیقِ float معتبر است.
func pythonAgg(t *testing.T, rows []oracleRow) *Agg {
	t.Helper()
	a := &Agg{}
	for _, r := range rows {
		m := r.M
		if v := oracleMust(t, m, "val"); v > 0 {
			a.NTraded++
		}
		a.Vol += oracleMust(t, m, "vol")
		a.Val += oracleMust(t, m, "val")
		a.RB += oracleMust(t, m, "retail_buy")
		a.RS += oracleMust(t, m, "retail_sell")
		a.IB += oracleMust(t, m, "inst_buy")
		a.IS += oracleMust(t, m, "inst_sell")
		a.NBI += oracleInt(t, m, "n_buy_i")
		a.NSI += oracleInt(t, m, "n_sell_i")
		a.NBN += oracleInt(t, m, "n_buy_n")
		a.NSN += oracleInt(t, m, "n_sell_n")
		if bq, ok := oracleNum(t, m, "bq_val"); ok {
			a.DepthN++
			a.BQ += bq
			sq, _ := oracleNum(t, m, "sq_val")
			bqv, _ := oracleNum(t, m, "bq_vol")
			sqv, _ := oracleNum(t, m, "sq_vol")
			a.SQ += sq
			a.BQV += bqv
			a.SQV += sqv
		}
	}
	a.N = len(rows)
	a.PCBuymt = pyDiv(pyDiv(a.RB, float64(a.NBI)), 1e7)
	a.PCSellmt = pyDiv(pyDiv(a.RS, float64(a.NSI)), 1e7)
	a.Power = pyDiv(a.PCBuymt, a.PCSellmt)
	a.FlowBT = (a.RB - a.RS) / 1e10
	a.VolBS = a.Vol / 1e9
	a.ValBT = a.Val / 1e10
	a.ValHemat = a.ValBT / 1e3
	a.BQBt = a.BQ / 1e10
	a.SQBt = a.SQ / 1e10
	return a
}

// TestAggMatchesPythonOracle تجمیع را با ارقامِ دامپِ پایتون می‌سنجد: هم کلِ
// ردیف‌ها و هم زیرمجموعهٔ top50؛ انتظار در تست و از منبعی جدا (mهایِ طلایی)
// بازسازی می‌شود، نه از money()ِ Go.
func TestAggMatchesPythonOracle(t *testing.T) {
	g := readOracleDump(t)
	if len(g.Rows) != 38 {
		t.Fatalf("golden rows = %d, want 38 (s1 fixture)", len(g.Rows))
	}
	h := openFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	rows := enrich(snap)
	if len(rows) != len(g.Rows) {
		t.Fatalf("rows = %d, want %d", len(rows), len(g.Rows))
	}
	for i, want := range g.Rows {
		if rows[i].Code != want.Code {
			t.Fatalf("row %d = %s, want %s", i, rows[i].Code, want.Code)
		}
		if rows[i].Top50 != want.Top50 {
			t.Fatalf("%s top50 = %v, want %v", want.Code, rows[i].Top50, want.Top50)
		}
	}

	got := aggOf(rows)
	want := pythonAgg(t, g.Rows)
	if got.N != 38 || got.NTraded == 0 || got.Val == 0 {
		t.Fatalf("probe: agg n/n_traded/val = %d/%d/%v", got.N, got.NTraded, got.Val)
	}
	checkAgg(t, "all", want, got)

	topWant := []oracleRow{}
	for _, r := range g.Rows {
		if r.Top50 {
			topWant = append(topWant, r)
		}
	}
	if len(topWant) != 2 {
		t.Fatalf("golden top50 rows = %d, want 2", len(topWant))
	}
	top := selectRows(rows, "top50")
	if len(top) != 2 {
		t.Fatalf("selectRows(top50) = %d rows, want 2", len(top))
	}
	gotTop := aggOf(top)
	checkAgg(t, "top50", pythonAgg(t, topWant), gotTop)
	if gotTop.Val >= got.Val || gotTop.N >= got.N {
		t.Fatalf("top50 subset not distinct: n %d/%d val %v/%v",
			gotTop.N, got.N, gotTop.Val, got.Val)
	}
}

// checkAgg هر خانه را دقیق می‌سنجد؛ NaN فقط با NaN برابر است (Noneِ پایتون).
func checkAgg(t *testing.T, label string, want, got *Agg) {
	t.Helper()
	nums := []struct {
		name string
		want float64
		got  float64
	}{
		{"vol", want.Vol, got.Vol},
		{"val", want.Val, got.Val},
		{"rb", want.RB, got.RB},
		{"rs", want.RS, got.RS},
		{"ib", want.IB, got.IB},
		{"is", want.IS, got.IS},
		{"bq", want.BQ, got.BQ},
		{"sq", want.SQ, got.SQ},
		{"bqv", want.BQV, got.BQV},
		{"sqv", want.SQV, got.SQV},
		{"pc_buy_mt", want.PCBuymt, got.PCBuymt},
		{"pc_sell_mt", want.PCSellmt, got.PCSellmt},
		{"power", want.Power, got.Power},
		{"flow_bt", want.FlowBT, got.FlowBT},
		{"vol_bs", want.VolBS, got.VolBS},
		{"val_bt", want.ValBT, got.ValBT},
		{"val_hemat", want.ValHemat, got.ValHemat},
		{"bq_bt", want.BQBt, got.BQBt},
		{"sq_bt", want.SQBt, got.SQBt},
	}
	for _, c := range nums {
		if math.IsNaN(c.want) || math.IsNaN(c.got) {
			if math.IsNaN(c.want) != math.IsNaN(c.got) {
				t.Errorf("%s.%s = %v, want %v", label, c.name, c.got, c.want)
			}
			continue
		}
		if c.got != c.want {
			t.Errorf("%s.%s = %v, want %v", label, c.name, c.got, c.want)
		}
	}
	ints := []struct {
		name string
		want int64
		got  int64
	}{
		{"n", int64(want.N), int64(got.N)},
		{"n_traded", int64(want.NTraded), int64(got.NTraded)},
		{"depth_n", int64(want.DepthN), int64(got.DepthN)},
		{"nbi", want.NBI, got.NBI},
		{"nsi", want.NSI, got.NSI},
		{"nbn", want.NBN, got.NBN},
		{"nsn", want.NSN, got.NSN},
	}
	for _, c := range ints {
		if c.got != c.want {
			t.Errorf("%s.%s = %d, want %d", label, c.name, c.got, c.want)
		}
	}
}

// TestCategoryBucketsAndSelectRows: هر کلیدِ categoryRows حاضر است (حتی
// خالی)، top50 دقیقاً همان selectRows است، و شمارش‌ها از فیکسچر می‌آیند —
// نه «حداقل صفر».
func TestCategoryBucketsAndSelectRows(t *testing.T) {
	h := openFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	rows := enrich(snap)
	if len(rows) != 38 {
		t.Fatalf("fixture rows = %d, want 38", len(rows))
	}
	b := categoryBuckets(rows)
	// شمارش‌هایِ زیر از اوراکلِ پایتون (in_category رویِ همان cls/kind/top50ِ
	// دامپِ enrich) آمده‌اند؛ همهٔ ده دسته در این فیکسچر غیرخالی‌اند.
	wantCounts := map[string]int{
		"all": 5, "bonds_other": 30, "eq_all": 4, "stock_right": 3,
		"eq_fund": 1, "fixed_fund": 1, "top50": 2, "lev_fund": 1,
		"gold_fund": 1, "silver_fund": 1,
	}
	if len(b) != len(categoryRows) {
		t.Fatalf("buckets has %d keys, want %d", len(b), len(categoryRows))
	}
	for _, c := range categoryRows {
		got, ok := b[c.Key]
		if !ok {
			t.Fatalf("bucket %q missing", c.Key)
		}
		if len(got) != wantCounts[c.Key] {
			t.Fatalf("bucket %q = %d rows, want %d", c.Key, len(got), wantCounts[c.Key])
		}
	}
	top := selectRows(rows, "top50")
	if len(top) != 2 || top[0].Code != "m1" || top[1].Code != "m2" {
		codes := []string{}
		for _, r := range top {
			codes = append(codes, r.Code)
		}
		t.Fatalf("selectRows(top50) = %v, want [m1 m2]", codes)
	}
	if len(b["top50"]) != len(top) {
		t.Fatalf("buckets[top50] = %d rows, selectRows = %d", len(b["top50"]), len(top))
	}
	for i := range top {
		if b["top50"][i] != top[i] {
			t.Fatalf("buckets[top50][%d] = %s, selectRows = %s",
				i, b["top50"][i].Code, top[i].Code)
		}
	}
	// m3 حقِ تقدم است و در رقابتِ top50 شرکت نمی‌کند (فقط سهامِ عادی).
	for _, r := range rows {
		if r.Code == "m3" && r.Top50 {
			t.Fatal("m3 (right) must not be top50")
		}
	}
	for _, r := range top {
		if r.Code == "m3" {
			t.Fatal("selectRows(top50) leaked the right row m3")
		}
	}
	// دستهٔ ناشناخته: برشِ خالی (نه nil، وگرنه JSON آن null می‌شود).
	if got := selectRows(rows, "no-such-category"); got == nil || len(got) != 0 {
		t.Fatalf("unknown category = %v, want empty non-nil slice", got)
	}
	// «حتی خالی»: یک ردیفِ other هیچ‌کدام از سطل‌هایِ صندوق را پر نمی‌کند، ولی
	// کلیدشان باید حاضر باشد.
	empty := categoryBuckets([]*Row{{Code: "x", Cls: "other", Kind: "other"}})
	if len(empty) != len(categoryRows) {
		t.Fatalf("empty buckets keys = %d, want %d", len(empty), len(categoryRows))
	}
	for _, c := range []string{"eq_fund", "fixed_fund", "lev_fund", "gold_fund",
		"silver_fund", "top50", "all"} {
		got, ok := empty[c]
		if !ok {
			t.Fatalf("bucket %q missing on a one-row set", c)
		}
		if len(got) != 0 {
			t.Fatalf("bucket %q = %d rows, want 0", c, len(got))
		}
	}
	if len(empty["bonds_other"]) != 1 {
		t.Fatalf("bonds_other = %d rows, want 1", len(empty["bonds_other"]))
	}
}
