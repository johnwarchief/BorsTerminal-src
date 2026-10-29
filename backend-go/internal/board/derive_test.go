package board

import (
	"math"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/store"
)

func testFrame() *store.Frame {
	cols := map[string][]any{
		"symbol":          {"a", "b", "c", "d"},
		"p_closing":       {1100.0, 100.0, 100.0, 1000.0},
		"p_last":          {1100.0, 100.0, 125.0, 1000.0},
		"price_yesterday": {1000.0, 1.0, 100.0, 100.0},
		"price_change":    {100.0, 99.0, 25.0, 900.0},
		"q_tot_tran":      {10.0, 10.0, 10.0, 10.0},
		"month_avg_vol":   {5.0, 5.0, 5.0, 5.0},
		"prev_day_vol":    {4.0, 4.0, 4.0, 4.0},
		"buy_i_vol":       {10.0, 10.0, 10.0, 10.0},
		"sell_i_vol":      {10.0, 10.0, 10.0, 10.0},
		"buy_count_i":     {2.0, 0.0, 2.0, 2.0},
		"sell_count_i":    {2.0, 0.0, 2.0, 2.0},
		"ctv_buy_i_val":   {nil, nil, nil, nil},
		"ctv_buy_n_val":   {nil, nil, nil, nil},
		"ctv_sell_i_val":  {nil, nil, nil, nil},
		"ctv_sell_n_val":  {nil, nil, nil, nil},
		"d_even":          {int64(20261014), int64(20261014), int64(20261014), int64(20261013)},
		"min30_low":       {900.0, 90.0, 90.0, 900.0},
		"mcap":            {1.0, 1.0, 1.0, 1.0},
		"mcap_src":        {"mw", "mw", "mw", "mw"},
	}
	fr := &store.Frame{Cols: cols}
	for i := range cols["symbol"] {
		fr.Codes = append(fr.Codes, "c"+string(rune('0'+i)))
	}
	return fr
}

func TestPercentChangeGuards(t *testing.T) {
	d := Derive(testFrame())
	if got := d.PercentChange[1]; !math.IsNaN(got) {
		t.Fatalf("price_yesterday=1 is a guard value: percent must be null, got %v", got)
	}
	if got := d.PercentChange[0]; math.Abs(got-10.0) > 1e-9 {
		t.Fatalf("percent_change = %v, want 10", got)
	}
	if got := d.PercentChange[3]; !math.IsNaN(got) {
		t.Fatalf("|pct|>100 must be hidden, got %v", got)
	}
	if got := d.PercentLast[2]; math.Abs(got-25.0) > 1e-9 {
		t.Fatalf("percent_last = %v, want 25", got)
	}
	if got := d.PlpRaw[1]; math.Abs(got-9900.0) > 1e-9 {
		t.Fatalf("plp_raw must use py>0 only, got %v", got)
	}
	if !math.IsNaN(d.BuyerPower[1]) {
		t.Fatal("zero buy count must yield null buyer_power, not 1.0")
	}
	if d.VolTrend[0] != "up" {
		t.Fatalf("vol_dod 2.5 => up, got %q", d.VolTrend[0])
	}
	if d.IsLive[3] {
		t.Fatal("older d_even must not be live")
	}
	if got := d.DistMin30Pct[0]; math.Abs(got-18.18) > 1e-9 {
		t.Fatalf("dist_min30_pct = %v, want 18.18", got)
	}
}

func TestRoundHalfEven(t *testing.T) {
	// 2.675×100 درِ دودویی دقیقاً رویِ tie (267.5) می‌افتد و نیم‌به‌زوج ۲۶۸
	// می‌دهد؛ pandas/numpy هم همین 2.68 را می‌دهند (سنجشِ محلی). round(2.675, 2)
	// خودِ پایتون 2.67 است چون مقدارِ دقیقِ دودویی را ده‌دهی گرد می‌کند، ولی
	// api/market.py برایِ ستون‌هایِ درصد Series.round یعنی numpy را صدا می‌زند.
	for in, want := range map[float64]float64{
		2.675: 2.68, 2.665: 2.66, 1.005: 1.0, 1.015: 1.01, 0.125: 0.12, 0.135: 0.14,
	} {
		if got := Round2(in); got != want {
			t.Fatalf("Round2(%v) = %v, want %v", in, got, want)
		}
	}
}

// TestPercentChangeFallsBackToPriceChange شاخهٔ جایگزینِ پایتون را می‌سنجد:
// p_closing غایب ولی price_change و price_yesterday معتبر ⇒ نسبتِ رسمیِ TSETMC.
func TestPercentChangeFallsBackToPriceChange(t *testing.T) {
	fr := testFrame()
	fr.Cols["p_closing"][2] = nil
	d := Derive(fr)
	if got := d.PercentChange[2]; math.Abs(got-25.0) > 1e-9 {
		t.Fatalf("fallback percent_change = %v, want 25", got)
	}
}

// TestSplitSidesAreIndependent قاعدهٔ ۱ِ client_split را رویِ قاب می‌سنجد:
// نبودِ ارزشِ سمتِ فروش، درصدِ سمتِ خرید را نمی‌بلعد و برعکس.
func TestSplitSidesAreIndependent(t *testing.T) {
	fr := testFrame()
	fr.Cols["ctv_buy_i_val"][0] = 10.0
	fr.Cols["ctv_buy_n_val"][0] = 5.0
	d := Derive(fr)
	if got := d.RetailBuyPct[0]; math.Abs(got-66.7) > 1e-9 {
		t.Fatalf("retail_buy_pct = %v, want 66.7", got)
	}
	if got := d.LegalBuyPct[0]; math.Abs(got-33.3) > 1e-9 {
		t.Fatalf("legal_buy_pct = %v, want 33.3", got)
	}
	if !math.IsNaN(d.RetailSellPct[0]) || !math.IsNaN(d.LegalSellPct[0]) {
		t.Fatal("buy-only values must leave the sell side unknown")
	}
	if d.PctBasis[0] != "value" {
		t.Fatalf("pct_basis = %q, want value when one side is measured", d.PctBasis[0])
	}
}

// TestSplitAllZeroIsUnknown مخرجِ صفر یعنی «ارزشی ثبت نشده»، نه «۰٪ حقیقی».
func TestSplitAllZeroIsUnknown(t *testing.T) {
	fr := testFrame()
	for _, c := range []string{"ctv_buy_i_val", "ctv_buy_n_val", "ctv_sell_i_val", "ctv_sell_n_val"} {
		fr.Cols[c][0] = 0.0
	}
	d := Derive(fr)
	if !math.IsNaN(d.RetailBuyPct[0]) || !math.IsNaN(d.LegalSellPct[0]) {
		t.Fatal("four zero source values must stay unknown, not 0%")
	}
	if d.PctBasis[0] != "" {
		t.Fatalf("pct_basis = %q, want empty when nothing is measured", d.PctBasis[0])
	}
}

// TestVolTrendNullWithoutPrevDay نگهبانِ pdv>0 را می‌سنجد؛ نبودِ روزِ قبل
// vol_dod را null می‌کند نه ۰.
func TestVolTrendNullWithoutPrevDay(t *testing.T) {
	fr := testFrame()
	fr.Cols["prev_day_vol"][0] = 0.0
	d := Derive(fr)
	if !math.IsNaN(d.VolDod[0]) {
		t.Fatalf("vol_dod = %v, want null when prev_day_vol<=0", d.VolDod[0])
	}
	if d.VolTrend[0] != "" {
		t.Fatalf("vol_trend = %q, want empty (null)", d.VolTrend[0])
	}
}

// TestNumTypes قراردادِ Num را قفل می‌کند: هر چیزی جز عددِ SQLite ⇒ NaN.
// تسکِ ۴ همین تابع را import می‌کند، پس امضایش ثابت است.
func TestNumTypes(t *testing.T) {
	for _, tc := range []struct {
		in   any
		want float64
	}{
		{float64(2.5), 2.5},
		{int64(7), 7},
		{int(3), 3},
		{nil, math.NaN()},
		{"12", math.NaN()},
		{[]byte("12"), math.NaN()},
		{true, math.NaN()},
	} {
		got := Num(tc.in)
		if math.IsNaN(tc.want) {
			if !math.IsNaN(got) {
				t.Fatalf("Num(%#v) = %v, want NaN", tc.in, got)
			}
			continue
		}
		if got != tc.want {
			t.Fatalf("Num(%#v) = %v, want %v", tc.in, got, tc.want)
		}
	}
}

// fixtureFrame فیکسچرِ مخزن را در t.TempDir() کپی می‌کند و قاب را با همان
// store.LoadBoard می‌خواند که مسیرِ تولیدیِ تسکِ ۶ می‌خواند. فیکسچر دست نمی‌خورد
// و بانکِ عملیاتیِ کاربر هرگز باز نمی‌شود.
func fixtureFrame(t *testing.T) *store.Frame {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("testdata", "fixture"))
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
	return fr
}

func rowIndex(t *testing.T, fr *store.Frame, symbol string) int {
	t.Helper()
	for i := range fr.Codes {
		if s, ok := fr.Cols["symbol"][i].(string); ok && s == symbol {
			return i
		}
	}
	t.Fatalf("symbol %q is not in the frame (codes=%v)", symbol, fr.Codes)
	return -1
}

// wantNum مقایسه با مقدارِ گلدن است؛ NaN یعنی آن کلید در گلدن نیامده (null).
func wantNum(t *testing.T, label string, got, want float64) {
	t.Helper()
	if math.IsNaN(want) {
		if !math.IsNaN(got) {
			t.Fatalf("%s = %v, but the golden has the key absent (null)", label, got)
		}
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("%s = %v, golden says %v", label, got, want)
	}
}

// TestFixtureDerivations پورت را رویِ همان ۳۰ ردیفِ فیکسچر می‌سنجد که اوراکلِ
// طلایی (golden/market.json) از آن ساخته شده است. انتظارها از همان گلدن خوانده
// شده‌اند، نه دستی حساب شده؛ ردیف‌ها قصداً لبه‌هایِ واقعی‌اند:
//
//   - نگهبان03: price_yesterday=1 (نگهبان) ⇒ percent_change و percent_last
//     غایب‌اند ولی plp_raw خام 209900 می‌ماند؛ mcap هم NULL است.
//   - بی‌معامله04: tvol=0 ⇒ vol_dod=0 و vol_trend=down؛ سرانهٔ خرید/فروش غایب.
//   - عادی01: p_closing=price_yesterday ⇒ percent_change=0 نه 10 (ستونِ پایانی
//     بر relative رسمی مقدم است)، و split با ۴ ارزشِ متمایز.
//   - سخت05: d_even کهنه ⇒ is_live=false؛ سهمِ فروش 20/80.
//   - کدبه‌کد09 و پول‌هوشمند06: درصدهایِ اعشاریِ گردشده.
//   - کم‌سابقه11: split با دو سمتِ کاملِ متفاوت.
//
// live_count گلدن ۲۹ است (یک ردیفِ فسیل).
func TestFixtureDerivations(t *testing.T) {
	fr := fixtureFrame(t)
	if fr.N() != 30 {
		t.Fatalf("rows = %d, want 30", fr.N())
	}
	d := Derive(fr)

	live := 0
	for _, v := range d.IsLive {
		if v {
			live++
		}
	}
	if live != 29 {
		t.Fatalf("is_live rows = %d, golden live_count is 29", live)
	}

	guard := rowIndex(t, fr, "نگهبان03")
	wantNum(t, "نگهبان03.percent_change", d.PercentChange[guard], math.NaN())
	wantNum(t, "نگهبان03.percent_last", d.PercentLast[guard], math.NaN())
	wantNum(t, "نگهبان03.plp_raw", d.PlpRaw[guard], 209900.0)
	wantNum(t, "نگهبان03.dist_min30_pct", d.DistMin30Pct[guard], 46.0)
	wantNum(t, "نگهبان03.vol_dod", d.VolDod[guard], 0.15)
	wantNum(t, "نگهبان03.mcap", d.Mcap[guard], math.NaN())
	if d.McapSrc[guard] != "" {
		t.Fatalf("نگهبان03.mcap_src = %q, golden has it null", d.McapSrc[guard])
	}
	if d.VolTrend[guard] != "down" {
		t.Fatalf("نگهبان03.vol_trend = %q, want down", d.VolTrend[guard])
	}
	if !d.IsLive[guard] {
		t.Fatal("نگهبان03.d_even is the newest: it must be live")
	}

	noTrade := rowIndex(t, fr, "بی‌معامله04")
	wantNum(t, "بی‌معامله04.tvol", d.Tvol[noTrade], 0.0)
	wantNum(t, "بی‌معامله04.buyer_power", d.BuyerPower[noTrade], math.NaN())
	wantNum(t, "بی‌معامله04.buy_power_i", d.BuyPowerI[noTrade], math.NaN())
	wantNum(t, "بی‌معامله04.vol_dod", d.VolDod[noTrade], 0.0)
	wantNum(t, "بی‌معامله04.dist_min30_pct", d.DistMin30Pct[noTrade], math.NaN())
	wantNum(t, "بی‌معامله04.mcap", d.Mcap[noTrade], math.NaN())
	wantNum(t, "بی‌معامله04.retail_buy_pct", d.RetailBuyPct[noTrade], math.NaN())
	wantNum(t, "بی‌معامله04.retail_sell_pct", d.RetailSellPct[noTrade], math.NaN())
	if d.VolTrend[noTrade] != "down" {
		t.Fatalf("بی‌معامله04.vol_trend = %q, want down", d.VolTrend[noTrade])
	}
	if d.McapSrc[noTrade] != "mw" {
		t.Fatalf("بی‌معامله04.mcap_src = %q, want mw", d.McapSrc[noTrade])
	}
	if d.PctBasis[noTrade] != "" {
		t.Fatalf("بی‌معامله04.pct_basis = %q, want empty", d.PctBasis[noTrade])
	}

	normal := rowIndex(t, fr, "عادی01")
	wantNum(t, "عادی01.percent_change", d.PercentChange[normal], 0.0)
	wantNum(t, "عادی01.percent_last", d.PercentLast[normal], 10.0)
	wantNum(t, "عادی01.plp_raw", d.PlpRaw[normal], 10.0)
	wantNum(t, "عادی01.vol_dod", d.VolDod[normal], 1.0)
	wantNum(t, "عادی01.dist_min30_pct", d.DistMin30Pct[normal], 12.0)
	wantNum(t, "عادی01.mcap", d.Mcap[normal], 5e12)
	wantNum(t, "عادی01.retail_buy_pct", d.RetailBuyPct[normal], 66.7)
	wantNum(t, "عادی01.legal_buy_pct", d.LegalBuyPct[normal], 33.3)
	wantNum(t, "عادی01.retail_sell_pct", d.RetailSellPct[normal], 57.1)
	wantNum(t, "عادی01.legal_sell_pct", d.LegalSellPct[normal], 42.9)
	if d.VolTrend[normal] != "flat" {
		t.Fatalf("عادی01.vol_trend = %q, want flat", d.VolTrend[normal])
	}
	if d.PctBasis[normal] != "value" {
		t.Fatalf("عادی01.pct_basis = %q, want value", d.PctBasis[normal])
	}

	fossil := rowIndex(t, fr, "سخت05")
	if d.IsLive[fossil] {
		t.Fatal("سخت05 has an older d_even: it must not be live")
	}
	wantNum(t, "سخت05.percent_change", d.PercentChange[fossil], 50.0)
	wantNum(t, "سخت05.percent_last", d.PercentLast[fossil], 65.0)
	wantNum(t, "سخت05.vol_dod", d.VolDod[fossil], 15.0)
	wantNum(t, "سخت05.dist_min30_pct", d.DistMin30Pct[fossil], 3.33)
	wantNum(t, "سخت05.retail_buy_pct", d.RetailBuyPct[fossil], 83.3)
	wantNum(t, "سخت05.legal_buy_pct", d.LegalBuyPct[fossil], 16.7)
	wantNum(t, "سخت05.retail_sell_pct", d.RetailSellPct[fossil], 20.0)
	wantNum(t, "سخت05.legal_sell_pct", d.LegalSellPct[fossil], 80.0)
	if d.VolTrend[fossil] != "up" {
		t.Fatalf("سخت05.vol_trend = %q, want up", d.VolTrend[fossil])
	}

	block := rowIndex(t, fr, "کدبه‌کد09")
	wantNum(t, "کدبه‌کد09.percent_change", d.PercentChange[block], 14.29)
	wantNum(t, "کدبه‌کد09.percent_last", d.PercentLast[block], 15.71)
	wantNum(t, "کدبه‌کد09.vol_dod", d.VolDod[block], 50.0)
	wantNum(t, "کدبه‌کد09.dist_min30_pct", d.DistMin30Pct[block], 2.5)

	smart := rowIndex(t, fr, "پول‌هوشمند06")
	wantNum(t, "پول‌هوشمند06.percent_change", d.PercentChange[smart], 5.26)
	wantNum(t, "پول‌هوشمند06.percent_last", d.PercentLast[smart], 7.89)
	wantNum(t, "پول‌هوشمند06.vol_dod", d.VolDod[smart], 33.33)
	wantNum(t, "پول‌هوشمند06.retail_buy_pct", d.RetailBuyPct[smart], 90.0)
	wantNum(t, "پول‌هوشمند06.legal_buy_pct", d.LegalBuyPct[smart], 10.0)
	wantNum(t, "پول‌هوشمند06.retail_sell_pct", d.RetailSellPct[smart], 55.6)
	wantNum(t, "پول‌هوشمند06.legal_sell_pct", d.LegalSellPct[smart], 44.4)

	short := rowIndex(t, fr, "کم‌سابقه11")
	wantNum(t, "کم‌سابقه11.retail_buy_pct", d.RetailBuyPct[short], 75.0)
	wantNum(t, "کم‌سابقه11.legal_buy_pct", d.LegalBuyPct[short], 25.0)
	wantNum(t, "کم‌سابقه11.retail_sell_pct", d.RetailSellPct[short], 50.0)
	wantNum(t, "کم‌سابقه11.legal_sell_pct", d.LegalSellPct[short], 50.0)
	wantNum(t, "کم‌سابقه11.vol_dod", d.VolDod[short], 2.5)

	simple := rowIndex(t, fr, "ساده12")
	wantNum(t, "ساده12.dist_min30_pct", d.DistMin30Pct[simple], 0.89)
	wantNum(t, "ساده12.vol_dod", d.VolDod[simple], 0.17)
	wantNum(t, "ساده12.mcap", d.Mcap[simple], 100000000012.0)
}
