package mstat

import (
	"testing"
)

// TestPanelsMatchGolden فقط دو پنلِ همین واحد (هیستوگرام و عمق) را با بدنهٔ
// اوراکلِ پایتون می‌سنجد؛ دماسنج و تفکیکِ حقیقی/حقوقی در واحدِ بعدی می‌آیند.
func TestPanelsMatchGolden(t *testing.T) {
	h := openFixture(t)
	cases := []struct {
		name string
		run  func() (map[string]any, error)
	}{
		{"histogram_all", func() (map[string]any, error) { return histogramPanel(h.Market, "all") }},
		{"histogram_eq_all", func() (map[string]any, error) { return histogramPanel(h.Market, "eq_all") }},
		{"depth_all", func() (map[string]any, error) { return depthPanel(h.Market, "all") }},
		{"depth_eq_all", func() (map[string]any, error) { return depthPanel(h.Market, "eq_all") }},
	}
	for _, c := range cases {
		got, err := c.run()
		if err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		compareGolden(t, c.name, loadGolden(t, "s1", c.name), got)
	}
}

// bucketCounts بارهایِ یک پنل را به نگاشتِ کلید→شمارش تبدیل می‌کند؛ کلیدِ
// تکراری یعنی سطلِ تکراری و همان‌جا لو می‌رود.
func bucketCounts(t *testing.T, body map[string]any, key string) map[string]int {
	t.Helper()
	bars, ok := body[key].([]map[string]any)
	if !ok {
		t.Fatalf("%s is %T, want []map[string]any", key, body[key])
	}
	out := make(map[string]int, len(bars))
	for _, b := range bars {
		k, ok := b["key"].(string)
		if !ok {
			t.Fatalf("%s bar key is %T, want string", key, b["key"])
		}
		if _, dup := out[k]; dup {
			t.Fatalf("%s has duplicate bucket %q", key, k)
		}
		c, ok := b["count"].(int)
		if !ok {
			t.Fatalf("%s bucket %s count is %T, want int", key, k, b["count"])
		}
		out[k] = c
	}
	return out
}

// wantCounts نگاشتِ کاملِ انتظار را می‌سنجد؛ کلیدِ غایب هم صفر نیست، خطاست.
func wantCounts(t *testing.T, got, want map[string]int) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("buckets = %d, want %d", len(got), len(want))
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("bucket %s = %d, want %d", k, got[k], v)
		}
	}
}

func sideCounts(t *testing.T, body map[string]any, side string) map[string]int {
	t.Helper()
	m, ok := body[side].(map[string]any)
	if !ok {
		t.Fatalf("%s is %T, want map[string]any", side, body[side])
	}
	out := make(map[string]int, len(m))
	for _, k := range []string{"normal", "below_base", "no_trade", "base_unknown"} {
		v, ok := m[k].(int)
		if !ok {
			t.Fatalf("%s.%s is %T, want int", side, k, m[k])
		}
		out[k] = v
	}
	return out
}

func wantInt(t *testing.T, body map[string]any, key string, want int) {
	t.Helper()
	got, ok := body[key].(int)
	if !ok {
		t.Fatalf("%s is %T, want int", key, body[key])
	}
	if got != want {
		t.Errorf("%s = %d, want %d", key, got, want)
	}
}

func wantFloat(t *testing.T, body map[string]any, key string, want float64) {
	t.Helper()
	got, ok := body[key].(float64)
	if !ok {
		t.Fatalf("%s is %T, want float64", key, body[key])
	}
	if got != want {
		t.Errorf("%s = %v, want %v", key, got, want)
	}
}

// checkTallyBars شکلِ هر میله را با مشخصاتِ تولیدشده می‌سنجد: تعدادِ میله‌ها
// باید همان ۱۲/۷ باشد و key/label/color هر میله دقیقاً همان خانهٔ spec.
func checkTallyBars(t *testing.T, bars []map[string]any, spec []histoSpec) {
	t.Helper()
	if len(bars) != len(spec) {
		t.Fatalf("bars = %d, want %d", len(bars), len(spec))
	}
	for i, b := range bars {
		if b["key"] != spec[i].Key || b["label"] != spec[i].Label ||
			b["color"] != spec[i].Color {
			t.Errorf("bar %d = %v/%v/%v, want %v/%v/%v", i,
				b["key"], b["label"], b["color"],
				spec[i].Key, spec[i].Label, spec[i].Color)
		}
	}
}

// TestTallyBoundaries مرزهایِ نیم‌باز/نیم‌بسته را بدونِ DB قفل می‌کند: فیکسچرِ
// s1 هیچ بازدهیِ دقیقاً رویِ مرز ندارد (-۳، ۰، ۱۱٫۱۱)، پس یک تغییرِ بی‌صدای
// `<=` به `<` فقط با این وکتورها لو می‌رود. مقدارِ مرزی باید فقط در یک سطل
// بنشیند و مجموعِ میله‌ها برابرِ تعدادِ مقدارهایِ غیرِ nil بماند.
func TestTallyBoundaries(t *testing.T) {
	cases := []struct {
		name string
		spec []histoSpec
		one  map[float64]string
		all  map[string]int
	}{
		{
			name: "histo12",
			spec: histo12,
			one: map[float64]string{
				-5: "<-5", -3: "-4..-3", -1: "-2..-1", 0: "-1..0",
				1: "0..1", 3: "2..3", 5: "4..5",
			},
			all: map[string]int{
				"<-5": 1, "-5..-4": 0, "-4..-3": 1, "-3..-2": 0,
				"-2..-1": 1, "-1..0": 1, "0..1": 1, "1..2": 0,
				"2..3": 1, "3..4": 0, "4..5": 1, ">5": 0,
			},
		},
		{
			name: "histo7",
			spec: histo7,
			one: map[float64]string{
				-5: "<-5", -3: "-5..-3", -1: "-3..-1", 0: "-1..1",
				1: "-1..1", 3: "1..3", 5: "3..5",
			},
			all: map[string]int{
				"<-5": 1, "-5..-3": 1, "-3..-1": 1, "-1..1": 2,
				"1..3": 1, "3..5": 1, ">5": 0,
			},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			// هر مقدار تنها: باید درست یک میله را یک‌بار بشمارد و همان کلیدِ مرزی.
			for v, wantKey := range c.one {
				v := v
				bars := tally([]*float64{&v}, c.spec)
				checkTallyBars(t, bars, c.spec)
				hits := 0
				for _, b := range bars {
					if b["count"].(int) == 1 {
						hits++
						if b["key"] != wantKey {
							t.Errorf("%v landed in %s, want %s", v, b["key"], wantKey)
						}
					}
				}
				if hits != 1 {
					t.Errorf("%v hit %d buckets, want exactly 1", v, hits)
				}
			}

			// همه با هم، به‌علاوهٔ nil: nil هیچ میله‌ای را نمی‌شمارد.
			vals := make([]*float64, 0, len(c.one)+1)
			for v := range c.one {
				v := v
				vals = append(vals, &v)
			}
			vals = append(vals, nil)
			bars := tally(vals, c.spec)
			checkTallyBars(t, bars, c.spec)
			got := make(map[string]int, len(bars))
			sum := 0
			for _, b := range bars {
				k := b["key"].(string)
				got[k] = b["count"].(int)
				sum += b["count"].(int)
			}
			if sum != len(c.one) {
				t.Errorf("sum(counts) = %d, want %d non-nil values", sum, len(c.one))
			}
			wantCounts(t, got, c.all)

			for _, b := range tally([]*float64{nil}, c.spec) {
				if b["count"].(int) != 0 {
					t.Errorf("nil pct incremented %v", b["key"])
				}
			}
		})
	}
}

// TestHistogramNodataAndNotTraded دو قاعدهٔ غیرِبدیهیِ هیستوگرام را رویِ فیکسچرِ
// موقت می‌سنجد: «nodata» فقط از میانِ نمادهایِ معامله‌شده می‌آید (حجم بالا،
// بازدهی ناپیدا) و «not_traded» از همهٔ ردیف‌هایِ گروه (حجم صفر، حتی اگر
// بازدهی محاسبه‌شدنی باشد). اعدادِ انتظار از طلاییِ eq_all می‌آیند:
// total ۴، known ۴، nodata ۰، not_traded ۰ و سطل‌های ‎>5:۱ / ‎-4..-3:۱ / ‎-1..0:۲.
func TestHistogramNodataAndNotTraded(t *testing.T) {
	t.Run("price_yesterday_null", func(t *testing.T) {
		h := openWritableFixture(t)
		if _, err := h.Market.Exec(
			"UPDATE market_watch SET price_yesterday = NULL WHERE ins_code = 'm1'"); err != nil {
			t.Fatal(err)
		}
		body, err := histogramPanel(h.Market, "eq_all")
		if err != nil {
			t.Fatal(err)
		}
		wantInt(t, body, "total", 4)
		wantInt(t, body, "known", 3)
		wantInt(t, body, "nodata", 1)
		wantInt(t, body, "not_traded", 0)
		wantCounts(t, bucketCounts(t, body, "histo12"), map[string]int{
			"<-5": 0, "-5..-4": 0, "-4..-3": 1, "-3..-2": 0,
			"-2..-1": 0, "-1..0": 2, "0..1": 0, "1..2": 0,
			"2..3": 0, "3..4": 0, "4..5": 0, ">5": 0,
		})
		wantCounts(t, bucketCounts(t, body, "histo7"), map[string]int{
			"<-5": 0, "-5..-3": 1, "-3..-1": 0, "-1..1": 2,
			"1..3": 0, "3..5": 0, ">5": 0,
		})
	})

	t.Run("q_tot_tran_zero", func(t *testing.T) {
		h := openWritableFixture(t)
		if _, err := h.Market.Exec(
			"UPDATE market_watch SET q_tot_tran = 0 WHERE ins_code = 'm4'"); err != nil {
			t.Fatal(err)
		}
		body, err := histogramPanel(h.Market, "eq_all")
		if err != nil {
			t.Fatal(err)
		}
		wantInt(t, body, "total", 3)
		wantInt(t, body, "known", 3)
		wantInt(t, body, "nodata", 0)
		wantInt(t, body, "not_traded", 1)
		wantCounts(t, bucketCounts(t, body, "histo12"), map[string]int{
			"<-5": 0, "-5..-4": 0, "-4..-3": 1, "-3..-2": 0,
			"-2..-1": 0, "-1..0": 1, "0..1": 0, "1..2": 0,
			"2..3": 0, "3..4": 0, "4..5": 0, ">5": 1,
		})
		wantCounts(t, bucketCounts(t, body, "histo7"), map[string]int{
			"<-5": 0, "-5..-3": 1, "-3..-1": 0, "-1..1": 1,
			"1..3": 0, "3..5": 0, ">5": 1,
		})
	})
}

// TestDepthBaseBranches شاخه‌هایِ «کمتر از مبنا» و «عادی» را باز می‌کند: در
// طلاییِ s1 هر چهار سطلِ یک‌طرفه base_unknown‌اند (مبنا NaN)، پس مقایسهٔ مبنا
// هرگز اجرا نمی‌شود. با base_volِ اعلامی (‎>1 در instruments) مبنا معلوم
// می‌شود: m1 با حجمِ صفِ ۲٫۰M زیرِ مبنایِ ۳٫۰M (below)، m4 با ۱٫۰M برابرِ مبنا
// (normal)؛ سمتِ فروش هم m3 با ۵۰M زیرِ ۶۰M و m5 با ۱M برابرِ ۱M.
func TestDepthBaseBranches(t *testing.T) {
	h := openWritableFixture(t)
	for _, u := range []struct {
		code string
		base float64
	}{
		{"m1", 3e6}, {"m4", 1e6}, {"m3", 6e7}, {"m5", 1e6},
	} {
		if _, err := h.Market.Exec(
			"UPDATE instruments SET base_vol = ? WHERE ins_code = ?", u.base, u.code); err != nil {
			t.Fatal(err)
		}
	}
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols_with_depth", 5)
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 1, "below_base": 1, "no_trade": 0, "base_unknown": 0,
	})
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 1, "below_base": 1, "no_trade": 0, "base_unknown": 0,
	})
}

// TestDepthNoTrade قاعدهٔ ترتیبِ شاخه‌ها را قفل می‌کند: «بدونِ معامله» پیش از
// مقایسهٔ مبنا می‌آید. m1 صفِ خریدِ یک‌طرفه و مبنایِ نامعلوم (NaN) دارد؛ با
// حجمِ صفر باید no_trade بشود، نه base_unknown. اگر شرطِ vol<=0 حذف شود،
// no_trade صفر و base_unknown دو می‌شود.
func TestDepthNoTrade(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET q_tot_tran = 0 WHERE ins_code = 'm1'"); err != nil {
		t.Fatal(err)
	}
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols_with_depth", 5)
	wantInt(t, body, "buy_queue_count", 2)
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 1, "base_unknown": 1,
	})
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 2,
	})
}

// TestDepthRatioNilWhenSellQueueZero «نسبتِ نامعلوم» را از «نسبتِ صفر» جدا
// می‌کند: با صفرشدنِ صفِ فروش، مخرج صفر است و پاسخ باید null باشد، نه ۰.
func TestDepthRatioNilWhenSellQueueZero(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec("UPDATE market_watch SET sell_q_val = 0"); err != nil {
		t.Fatal(err)
	}
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	if body["ratio"] != nil {
		t.Errorf("ratio = %v, want nil (zero sell denominator)", body["ratio"])
	}
	wantFloat(t, body, "sell_queue_b_toman", 0)
	wantInt(t, body, "sell_queue_count", 0)
	if avail, ok := body["depth_available"].(bool); !ok || !avail {
		t.Errorf("depth_available = %v, want true (depth columns still populated)", body["depth_available"])
	}
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 0,
	})
}

// TestDepthUnavailableDepthless قراردادِ «بی‌داده ≠ صفر» را با بانکِ بی‌ستونِ
// عمق می‌سنجد: هیچ ردیفی عمق ندارد، پس depth_available و asof.depth هر دو
// false و همهٔ جمع‌ها/سطل‌ها صفرند و ratio null است.
func TestDepthUnavailableDepthless(t *testing.T) {
	h := openDepthlessFixture(t)
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	if avail, ok := body["depth_available"].(bool); !ok || avail {
		t.Errorf("depth_available = %v, want false", body["depth_available"])
	}
	wantInt(t, body, "symbols_with_depth", 0)
	wantInt(t, body, "buy_queue_count", 0)
	wantInt(t, body, "sell_queue_count", 0)
	wantFloat(t, body, "buy_queue_b_toman", 0)
	wantFloat(t, body, "sell_queue_b_toman", 0)
	if body["ratio"] != nil {
		t.Errorf("ratio = %v, want nil", body["ratio"])
	}
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 0,
	})
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 0,
	})
	asof, ok := body["asof"].(map[string]any)
	if !ok {
		t.Fatalf("asof is %T, want map[string]any", body["asof"])
	}
	if depth, ok := asof["depth"].(bool); !ok || depth {
		t.Errorf("asof.depth = %v, want false", asof["depth"])
	}
}
