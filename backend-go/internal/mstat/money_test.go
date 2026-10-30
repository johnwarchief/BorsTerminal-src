package mstat

import (
	"fmt"
	"math"
	"testing"
)

// row یک ردیفِ حداقلیِ سالم می‌سازد: ارزش÷حجم = ۱۰۰ ⇒ VWAP = ۱۰۰.
func row() *Row {
	return &Row{Code: "x", QVol: 100, QVal: 10000, PClosing: 100}
}

func ct() *CTRow {
	return &CTRow{
		BuyIVol: 10, BuyNVol: 20, SellIVol: 30, SellNVol: 40, BuyDDDVol: 50,
		BuyCountI: 4, SellCountI: 5, BuyCountN: 6, SellCountN: 7,
	}
}

// TestMoneyValueSource سه حالتِ مبدأ/ترکیبی/بازسازی را قفل می‌کند: هر خانهٔ
// نبودِ client_type_value باید با حجم×VWAP پر شود، نه صفر.
func TestMoneyValueSource(t *testing.T) {
	all := func() *CTVRow {
		return &CTVRow{BuyIVal: 1e6, BuyNVal: 2e6, SellIVal: 3e6, SellNVal: 4e6, BuyDDDVal: 5e6}
	}
	cases := []struct {
		name      string
		ctv       *CTVRow
		wantSrc   string
		wantPower float64
		// (retail_buy, retail_sell, inst_buy, inst_sell, ddd)
		want [5]float64
	}{
		{"native", all(), "native", (1e6 / 4) / (3e6 / 5),
			[5]float64{1e6, 3e6, 2e6, 4e6, 5e6}},
		{"mixed", &CTVRow{BuyIVal: 1e6, BuyNVal: math.NaN(), SellIVal: math.NaN(),
			SellNVal: math.NaN(), BuyDDDVal: math.NaN()}, "mixed",
			(1e6 / 4) / (3e3 / 5), [5]float64{1e6, 3e3, 2e3, 4e3, 5e3}},
		{"reconstructed", nil, "reconstructed", (1e3 / 4) / (3e3 / 5),
			[5]float64{1e3, 3e3, 2e3, 4e3, 5e3}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := row()
			r.CT = ct()
			r.CTV = c.ctv
			m := money(r, nil)
			if m.ValueSource != c.wantSrc {
				t.Fatalf("value_source = %s, want %s", m.ValueSource, c.wantSrc)
			}
			got := [5]float64{m.RetailBuy, m.RetailSell, m.InstBuy, m.InstSell, m.DDDBuy}
			if got != c.want {
				t.Fatalf("values = %v, want %v", got, c.want)
			}
			if m.Power != c.wantPower {
				t.Fatalf("power = %v, want %v", m.Power, c.wantPower)
			}
			if m.Flow != m.RetailBuy-m.RetailSell {
				t.Fatalf("flow = %v", m.Flow)
			}
			if !m.HasCT {
				t.Fatal("has_ct = false, want true")
			}
		})
	}
}

// TestMoneyNullStaysNull: خانهٔ نبودِ عمق یا سرانه باید NaN بماند، نه صفرِ
// باورپذیر؛ و vol/val/trades مثلِ _fِ پایتون از NULL صفر می‌شوند.
func TestMoneyNullStaysNull(t *testing.T) {
	r := row()
	// NaN همان NULLِ جدول است؛ صفرِ خالیِ ساختار، «صفرِ واقعی» است و باید
	// همان‌طور بماند. اینجا همان ستون‌هایِ nullable را NULL می‌کنیم.
	r.BuyQVal, r.SellQVal, r.BuyQ1Px = math.NaN(), math.NaN(), math.NaN()
	r.NTrades = math.NaN()
	m := money(r, nil)
	if !isNaN(m.BQVal) || !isNaN(m.SQVal) || !isNaN(m.BQ1Px) {
		t.Fatalf("depth nulls = %v/%v/%v, want NaN", m.BQVal, m.SQVal, m.BQ1Px)
	}
	if m.QState != "x" {
		t.Fatalf("qstate without depth = %s, want x", m.QState)
	}
	if !isNaN(m.PCBuy) || !isNaN(m.PCSell) || !isNaN(m.Power) || !isNaN(m.Base) {
		t.Fatalf("derived nulls = %v/%v/%v/%v", m.PCBuy, m.PCSell, m.Power, m.Base)
	}
	if m.Trades != 0 || m.HasCT {
		t.Fatalf("trades/has_ct = %v/%v", m.Trades, m.HasCT)
	}
	// صفرِ واقعیِ ارزش با NULL فرق دارد: pc_buy = 0÷۴ = ۰ می‌شود، ولی
	// قدرت (۰ ÷ NaN) ساختنی نیست.
	withCT := row()
	withCT.CT = &CTRow{BuyCountI: 4, SellCountI: math.NaN()}
	m = money(withCT, nil)
	if m.PCBuy != 0 {
		t.Fatalf("pc_buy = %v, want 0", m.PCBuy)
	}
	if !isNaN(m.Power) {
		t.Fatalf("power = %v, want NaN", m.Power)
	}
}

// TestMoneyVwapFallback: VWAP = ارزش÷حجم اگر بود، وگرنه قیمت پایانی، وگرنه ۰.
func TestMoneyVwapFallback(t *testing.T) {
	cases := []struct {
		val, vol, pcl float64
		want          float64
	}{
		{10000, 100, 50, 100},
		{0, 100, 50, 50},        // تقسیمِ صفر = «نساختنی»، پس پایانی
		{math.NaN(), 0, 50, 50}, // هر دو NULL
		{math.NaN(), math.NaN(), math.NaN(), 0},
	}
	for _, c := range cases {
		r := &Row{Code: "x", QVal: c.val, QVol: c.vol, PClosing: c.pcl}
		if got := money(r, nil).Vwap; got != c.want {
			t.Errorf("vwap(%v,%v,%v) = %v, want %v", c.val, c.vol, c.pcl, got, c.want)
		}
	}
}

// TestQueueState شش حرفِ وضعیت را می‌سنجد؛ «صف» یعنی یک سمتِ دفتر خالی است.
func TestQueueState(t *testing.T) {
	pct := func(v float64) *float64 { return &v }
	cases := []struct {
		name   string
		bq, sq float64
		pct    *float64
		want   string
	}{
		{"no depth", math.NaN(), math.NaN(), pct(1), "x"},
		{"buy queue", 10, math.NaN(), pct(-1), "b"},
		{"sell queue", 0, 10, pct(1), "s"},
		{"both empty, no pct", 0, 0, nil, "x"},
		{"flat", 0, 0, pct(0), "z"},
		{"positive", 5, 5, pct(0.5), "p"},
		{"negative", 5, 5, pct(-0.5), "n"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := &Row{Code: "x", Pct: c.pct}
			m := Money{BQVal: c.bq, SQVal: c.sq}
			if got := queueState(r, m); got != c.want {
				t.Fatalf("qstate = %s, want %s", got, c.want)
			}
		})
	}
}

// TestTop50Codes: فقط سهامِ عادی رقابت می‌کند، سقف ۵۰ است، و tie با کدِ
// نزولی می‌شکند (sortِ reverseِ tuple در پایتون).
func TestTop50Codes(t *testing.T) {
	rows := []*Row{}
	for i := 0; i < 51; i++ {
		rows = append(rows, &Row{Code: fmt.Sprintf("c%02d", i), Cls: paperStock,
			TotalShares: 10, PClosing: 10})
	}
	rows = append(rows,
		&Row{Code: "z-fund", Cls: paperFund, TotalShares: 1e9, PClosing: 1e9},
		&Row{Code: "z-nan", Cls: paperStock, TotalShares: math.NaN(), PClosing: 10},
		&Row{Code: "z-zero", Cls: paperStock, TotalShares: 0, PClosing: 10},
	)
	top := top50Codes(rows)
	if len(top) != 50 {
		t.Fatalf("len = %d, want 50", len(top))
	}
	if top["c00"] {
		t.Fatal("lowest code must lose the tie")
	}
	if !top["c50"] {
		t.Fatal("highest code must win the tie")
	}
	if top["z-fund"] || top["z-nan"] || top["z-zero"] {
		t.Fatalf("fund/NaN/zero-cap symbol leaked into top50: %v", top)
	}
}

// TestInCategory دامنه‌هایِ ده سطرِ جدولِ خلاصه را قفل می‌کند.
func TestInCategory(t *testing.T) {
	t50 := map[string]bool{"s": true}
	cases := []struct {
		cls, kind, cat string
		want           bool
	}{
		{"stock", "stock", "all", true},
		{"stock", "stock", "bonds_other", false},
		{"stock", "stock", "eq_all", true},
		{"stock", "stock", "stock_right", true},
		{"right", "right", "eq_all", true},
		{"right", "right", "eq_fund", false},
		{"fund", "equity", "all", true},
		{"fund", "equity", "eq_fund", true},
		{"fund", "equity", "fixed_fund", false},
		{"fund", "fixed", "all", true},
		{"fund", "fixed", "bonds_other", false},
		{"fund", "fixed", "eq_all", false},
		{"fund", "fixed", "fixed_fund", true},
		{"fund", "gold", "all", false},
		{"fund", "gold", "bonds_other", false},
		{"fund", "gold", "gold_fund", true},
		{"fund", "silver", "silver_fund", true},
		{"fund", "lev", "lev_fund", true},
		{"fund", "commod", "all", false},
		{"fund", "commod", "bonds_other", true},
		{"other", "other", "all", false},
		{"other", "other", "bonds_other", true},
		{"stock", "stock", "unknown", false},
	}
	for _, c := range cases {
		r := &Row{Code: "s", Cls: c.cls, Kind: c.kind}
		if got := inCategory(r, c.cat, t50); got != c.want {
			t.Errorf("inCategory(%s/%s,%s) = %v, want %v",
				c.cls, c.kind, c.cat, got, c.want)
		}
	}
	r := &Row{Code: "s", Cls: paperStock, Kind: "stock"}
	if !inCategory(r, "top50", t50) {
		t.Error("top50 must follow the ranked set")
	}
	if inCategory(&Row{Code: "n", Cls: paperStock, Kind: "stock"}, "top50", t50) {
		t.Error("code outside the ranked set must not be top50")
	}
}

func TestJnumAndIsEmpty(t *testing.T) {
	if got := jnum(math.NaN()); got != nil {
		t.Fatalf("jnum(NaN) = %v, want nil", got)
	}
	if got := jnum(0); got != 0.0 {
		t.Fatalf("jnum(0) = %v, want 0", got)
	}
	if got := jnum(-1.5); got != -1.5 {
		t.Fatalf("jnum(-1.5) = %v", got)
	}
	if !isEmpty(math.NaN()) || !isEmpty(0) || isEmpty(1) {
		t.Fatal("isEmpty must treat NaN and 0 as empty, 1 as filled")
	}
}
