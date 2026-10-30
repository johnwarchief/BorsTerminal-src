package mstat

import (
	"math"
	"reflect"
	"testing"
)

// TestPanelsMatchGolden هر چهار پنلِ Task 5 را با بدنهٔ اوراکلِ پایتون می‌سنجد.
func TestPanelsMatchGolden(t *testing.T) {
	h := openFixture(t)
	cases := []struct {
		name string
		run  func() (map[string]any, error)
	}{
		{"histogram_all", func() (map[string]any, error) { return histogramPanel(h.Market, "all") }},
		{"histogram_eq_all", func() (map[string]any, error) { return histogramPanel(h.Market, "eq_all") }},
		{"thermometer_all", func() (map[string]any, error) { return thermometerPanel(h.Market, "all") }},
		{"thermometer_eq_all", func() (map[string]any, error) { return thermometerPanel(h.Market, "eq_all") }},
		{"depth_all", func() (map[string]any, error) { return depthPanel(h.Market, "all") }},
		{"depth_eq_all", func() (map[string]any, error) { return depthPanel(h.Market, "eq_all") }},
		{"clientsplit_all", func() (map[string]any, error) { return clientSplitPanel(h.Market, "all") }},
		{"clientsplit_fixed", func() (map[string]any, error) { return clientSplitPanel(h.Market, "fixed") }},
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

// TestTallyBoundaries مرزهایِ نیم‌باز/نیم‌بسته را بدونِ DB قفل می‌کند: ‎-5، -1،
// 1، 3 و 5 در هر دو spec رویِ لبهٔ سطل‌اند و هرکدام باید دقیقاً در یک سطل
// بنشیند، نه دو — و histo7 با همین مقدارها لبه‌هایِ خودش را هم می‌سنجد. مجموعِ
// میله‌ها هم باید برابرِ تعدادِ مقدارهایِ غیرِ nil بماند و nil هیچ سطلی را
// نشمارد.
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

	// فازِ دوم: buy_q_vol تهی (NULL) برایِ m4، با همان مبنایِ ۱M. حجمِ صف ناپیدا
	// است، پس پایتون این ردیف را base_unknown می‌شمارد، نه normal؛ حذفِ شرطِ
	// isNaN(qvol) در همین سطر لو می‌رود. سمتِ فروش دست‌نخورده می‌ماند.
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET buy_q_vol = NULL WHERE ins_code = 'm4'"); err != nil {
		t.Fatal(err)
	}
	body, err = depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols_with_depth", 5)
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 0, "below_base": 1, "no_trade": 0, "base_unknown": 1,
	})
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 1, "below_base": 1, "no_trade": 0, "base_unknown": 0,
	})
}

// TestDepthNullSellQueueValue «بی‌داده ≠ صفر» را رویِ صفِ فروش می‌سنجد: sell_q_val
// تهی با buy_q_valِ موجود. m1 از have بیرون نمی‌رود (bq_val تهی نیست) و در سمتِ
// خرید همچنان شمرده می‌شود؛ هم isEmpty(opp) رویِ NaN و هم zeroIfNaN(SQVal) در
// جمعِ فروش فقط همین‌جا اجرا می‌شوند. مبنا در این کپی نامعلوم است (NaN)، پس
// m1/m4 رویِ خرید و m3/m5 رویِ فروش در سطلِ base_unknown می‌افتند.
func TestDepthNullSellQueueValue(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET sell_q_val = NULL WHERE ins_code = 'm1'"); err != nil {
		t.Fatal(err)
	}
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols_with_depth", 5)
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 2,
	})
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 2,
	})
	wantFloat(t, body, "buy_queue_b_toman", 0.3)
	wantFloat(t, body, "sell_queue_b_toman", 5.2)
	wantFloat(t, body, "ratio", 0.07)
}

// TestDepthNoTradeSellSide شاخهٔ no_trade را در سمتِ فروش باز می‌کند؛ پیش از این
// فقط سمتِ خرید آن را می‌دید. m5 صفِ فروشِ یک‌طرفه دارد و با q_tot_tran=0 باید
// no_trade شود، نه base_unknown. اگر این شاخه فقط برایِ سمتِ خرید اجرا شود،
// no_trade صفر و base_unknown دو می‌شود.
func TestDepthNoTradeSellSide(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET q_tot_tran = 0 WHERE ins_code = 'm5'"); err != nil {
		t.Fatal(err)
	}
	body, err := depthPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols_with_depth", 5)
	wantCounts(t, sideCounts(t, body, "sell"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 1, "base_unknown": 1,
	})
	wantCounts(t, sideCounts(t, body, "buy"), map[string]int{
		"normal": 0, "below_base": 0, "no_trade": 0, "base_unknown": 2,
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

// subBody زیرنگاشتِ یک پنل را می‌خواند؛ نوعِ اشتباه یعنی قراردادِ بدنه شکسته.
func subBody(t *testing.T, body map[string]any, key string) map[string]any {
	t.Helper()
	m, ok := body[key].(map[string]any)
	if !ok {
		t.Fatalf("%s is %T, want map[string]any", key, body[key])
	}
	return m
}

// wantNilKey «نامعلوم» را از «صفر» جدا می‌کند: کلید باید باشد و nil، نه غایب و
// نه عددِ صفر.
func wantNilKey(t *testing.T, body map[string]any, key string) {
	t.Helper()
	if v, ok := body[key]; !ok || v != nil {
		t.Errorf("%s = %v, want nil", key, v)
	}
}

func wantBool(t *testing.T, body map[string]any, key string, want bool) {
	t.Helper()
	got, ok := body[key].(bool)
	if !ok {
		t.Fatalf("%s is %T, want bool", key, body[key])
	}
	if got != want {
		t.Errorf("%s = %v, want %v", key, got, want)
	}
}

// TestThermometerEntryThreshold مرزِ قانونِ ۸۰٪ را رویِ خودِ مرز می‌سنجد: گروهِ
// all پنج نمادِ معامله‌شده دارد. با چهار منفی و یک مثبت سهمِ منفی‌ها ۸۰٪ می‌شود
// و «فرصتِ ورود» باید true باشد؛ با سه منفی و دو مثبت ۶۰٪ می‌شود و false.
// علامتِ pct از price_yesterday نسبت به p_closing می‌آید، و نسبت در بازهٔ pxNear
// می‌ماند (۰٫۹ و ۱٫۱) تا بازدهی اصلاً محاسبه شود.
func TestThermometerEntryThreshold(t *testing.T) {
	body := func(t *testing.T, yestMult map[string]float64) map[string]any {
		t.Helper()
		h := openWritableFixture(t)
		for code, mult := range yestMult {
			if _, err := h.Market.Exec(
				"UPDATE market_watch SET price_yesterday = p_closing * ? WHERE ins_code = ?",
				mult, code); err != nil {
				t.Fatal(err)
			}
		}
		got, err := thermometerPanel(h.Market, "all")
		if err != nil {
			t.Fatal(err)
		}
		return got
	}

	t.Run("four_negative_exactly_80", func(t *testing.T) {
		got := body(t, map[string]float64{
			"m1": 1.1, "m2": 1.1, "m3": 1.1, "m4": 1.1, "m5": 0.9,
		})
		wantInt(t, got, "positive", 1)
		wantInt(t, got, "negative", 4)
		wantInt(t, got, "zero", 0)
		wantInt(t, got, "nodata", 0)
		wantInt(t, got, "not_traded", 0)
		wantFloat(t, got, "positive_pct", 20.0)
		wantFloat(t, got, "negative_pct", 80.0)
		wantFloat(t, got, "entry_rule_pct", 80.0)
		wantBool(t, got, "entry_opportunity", true)
	})

	t.Run("three_negative_60", func(t *testing.T) {
		got := body(t, map[string]float64{
			"m1": 1.1, "m2": 1.1, "m3": 1.1, "m4": 0.9, "m5": 0.9,
		})
		wantInt(t, got, "positive", 2)
		wantInt(t, got, "negative", 3)
		wantInt(t, got, "zero", 0)
		wantInt(t, got, "nodata", 0)
		wantFloat(t, got, "positive_pct", 40.0)
		wantFloat(t, got, "negative_pct", 60.0)
		wantBool(t, got, "entry_opportunity", false)
	})
}

// TestThermometerEmptyTradedGroup: وقتی هیچ نمادِ معامله‌شده‌ای در گروه نیست،
// مخرج صفر است و درصدها باید null بمانند، نه ۰. صفرِ جعلی در مقایسهٔ «≥ ۸۰٪»
// نمی‌نشیند ولی عددی است که کاربر «۰٪ منفی» می‌خواند؛ و «فرصتِ ورود» هم نباید
// از درصدِ نامعلوم ساخته شود.
func TestThermometerEmptyTradedGroup(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec("UPDATE market_watch SET q_tot_tran = 0"); err != nil {
		t.Fatal(err)
	}
	body, err := thermometerPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "positive", 0)
	wantInt(t, body, "negative", 0)
	wantInt(t, body, "zero", 0)
	wantInt(t, body, "nodata", 0)
	wantInt(t, body, "not_traded", 5)
	wantNilKey(t, body, "positive_pct")
	wantNilKey(t, body, "negative_pct")
	wantBool(t, body, "entry_opportunity", false)
	wantFloat(t, body, "entry_rule_pct", 80.0)
}

// TestClientSplitUnknownTabFallsBack: تبِ ناشناخته به دستهٔ all برمی‌گردد ولی
// نامِ خامِ tab در پاسخ می‌ماند (پایتون `_TAB_CAT.get(tab, "all")` و
// `"tab": tab`). مقایسهٔ زیرنگاشت‌ها مستقیم است، نه از راهِ رشته.
func TestClientSplitUnknownTabFallsBack(t *testing.T) {
	h := openFixture(t)
	all, err := clientSplitPanel(h.Market, "all")
	if err != nil {
		t.Fatal(err)
	}
	got, err := clientSplitPanel(h.Market, "nope")
	if err != nil {
		t.Fatal(err)
	}
	if got["tab"] != "nope" {
		t.Errorf("tab = %v, want the raw argument %q", got["tab"], "nope")
	}
	wantInt(t, got, "symbols", 5)
	for _, k := range []string{"retail", "institutional", "pc_buy_m_toman",
		"pc_sell_m_toman", "power", "money_flow_b_toman"} {
		if !reflect.DeepEqual(got[k], all[k]) {
			t.Errorf("%s = %v, want the all-tab body %v", k, got[k], all[k])
		}
	}
}

// TestClientSplitZeroDenominator: m5 تنها نمادِ تبِ fixed است. حجم‌ها، تعدادها
// و ارزش‌هایِ مبدأ صفر می‌شوند تا هر دو گروه صفر شوند. تعدادها هم باید صفر
// شوند وگرنه سرانهٔ خرید ۰÷تعداد = ۰٫۰ می‌شود، نه null. مخرجِ صفر یعنی «در این
// سمت ارزشی ثبت نشده»، پس هیچ درصدی ساخته نمی‌شود — sideShare نباید ضعیف شود.
func TestClientSplitZeroDenominator(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`UPDATE client_type SET buy_i_vol = 0, buy_n_vol = 0,
		buy_ddd_vol = 0, buy_count_i = 0, buy_count_n = 0, sell_i_vol = 0,
		sell_n_vol = 0, sell_count_i = 0, sell_count_n = 0
		WHERE ins_code = 'm5'`); err != nil {
		t.Fatal(err)
	}
	if _, err := h.Market.Exec(`UPDATE client_type_value SET buy_i_val = 0,
		buy_n_val = 0, sell_i_val = 0, sell_n_val = 0 WHERE ins_code = 'm5'`); err != nil {
		t.Fatal(err)
	}
	body, err := clientSplitPanel(h.Market, "fixed")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols", 1)
	for _, side := range []string{"retail", "institutional"} {
		m := subBody(t, body, side)
		wantNilKey(t, m, "buy_pct")
		wantNilKey(t, m, "sell_pct")
		wantFloat(t, m, "buy_b_toman", 0)
		wantFloat(t, m, "sell_b_toman", 0)
	}
	wantNilKey(t, body, "pc_buy_m_toman")
	wantNilKey(t, body, "pc_sell_m_toman")
	wantNilKey(t, body, "power")
	wantFloat(t, body, "money_flow_b_toman", 0)
}

// TestSideShareAndComplement ریاضیِ محضِ سهم را بی‌DB قفل می‌کند: منفی/NaN/مخرجِ
// صفر ⇒ nil؛ گردکردنِ یک‌رقمی؛ و حقوقی مکملِ *همان* سهمِ گردشده است. بردارِ
// ۳:۱۹۹۷ گره را نشان می‌دهد: حقیقی ۰٫۱ و مکمل ۹۹٫۹؛ گردکردنِ مستقلِ حقوقی
// ۹۹٫۸ می‌داد و دو سمت به ۱۰۰ نمی‌رسیدند.
func TestSideShareAndComplement(t *testing.T) {
	for _, c := range []struct {
		name          string
		retail, legal float64
	}{
		{"zero denominator", 0, 0},
		{"negative retail", -1, 5},
		{"negative legal", 5, -1},
		{"NaN retail", math.NaN(), 5},
		{"NaN legal", 5, math.NaN()},
	} {
		if got := sideShare(c.retail, c.legal); got != nil {
			t.Errorf("%s: sideShare = %v, want nil", c.name, got)
		}
	}
	if got := sideShare(1, 2); got != 33.3 {
		t.Errorf("sideShare(1,2) = %v, want 33.3", got)
	}
	if got := complement(sideShare(1, 2)); got != 66.7 {
		t.Errorf("complement(33.3) = %v, want 66.7", got)
	}
	if got := complement(nil); got != nil {
		t.Errorf("complement(nil) = %v, want nil", got)
	}
	if got := complement(sideShare(100, 900)); got != 90.0 {
		t.Errorf("complement(10.0) = %v, want 90.0", got)
	}
	if got := sideShare(3, 1997); got != 0.1 {
		t.Errorf("sideShare(3,1997) = %v, want 0.1", got)
	}
	if got := complement(0.1); got != 99.9 {
		t.Errorf("complement(0.1) = %v, want 99.9 (independent legal rounding gives 99.8)", got)
	}
}

// TestClientSplitLegalShareIsComplement همان گرهِ ۳:۱۹۹۷ را از مسیرِ کاملِ پنل
// می‌سنجد: در تبِ fixed فقط m5 هست و حجم‌هایِ ۳ و ۱۹۹۷ با VWAPِ ۱۰۰۰ ارزشِ
// ۳۰۰۰ و ۱٬۹۹۷٬۰۰۰ ریال می‌دهند. حقوقی باید مکملِ ۰٫۱ یعنی ۹۹٫۹ باشد؛ محاسبهٔ
// مستقل ۹۹٫۸ می‌داد.
func TestClientSplitLegalShareIsComplement(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(`UPDATE client_type SET buy_i_vol = 3, buy_n_vol = 1997,
		sell_i_vol = 3, sell_n_vol = 1997 WHERE ins_code = 'm5'`); err != nil {
		t.Fatal(err)
	}
	body, err := clientSplitPanel(h.Market, "fixed")
	if err != nil {
		t.Fatal(err)
	}
	wantInt(t, body, "symbols", 1)
	retail := subBody(t, body, "retail")
	institutional := subBody(t, body, "institutional")
	wantFloat(t, retail, "buy_pct", 0.1)
	wantFloat(t, institutional, "buy_pct", 99.9)
	wantFloat(t, retail, "sell_pct", 0.1)
	wantFloat(t, institutional, "sell_pct", 99.9)
}

// TestNilOrRound قراردادِ تبدیلِ «NaN یعنی None» را با گردکردن قفل می‌کند:
// NaN ⇒ nil، عدد ⇒ همان roundِ پایتون، و صفرِ منفی هم عددی صفر می‌ماند.
func TestNilOrRound(t *testing.T) {
	if got := nilOrRound(math.NaN(), 1); got != nil {
		t.Errorf("nilOrRound(NaN) = %v, want nil", got)
	}
	if got := nilOrRound(1.234, 2); got != 1.23 {
		t.Errorf("nilOrRound(1.234, 2) = %v, want 1.23", got)
	}
	got := nilOrRound(math.Copysign(0, -1), 1)
	f, ok := got.(float64)
	if !ok || f != 0 {
		t.Errorf("nilOrRound(-0.0, 1) = %v (%T), want numeric zero", got, got)
	}
}
