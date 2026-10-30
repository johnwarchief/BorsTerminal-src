package mstat

import (
	"encoding/json"
	"math"
	"testing"

	"borsterminal/backend/internal/marketphase"
)

// toMap بدنهٔ تایپ‌دار را از درِ JSON می‌گذراند تا با goldenِ canon مقایسه شود
// (همان کاری که لایهٔ HTTP می‌کند).
func toMap(t *testing.T, v any) map[string]any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

// TestPhaseGoldens هر سه صحنهٔ market_phase را می‌سنجد. s3 و s4 مثلِ خودِ
// اوراکل (tools/parity/gen_mstat_golden.py) از کپیِ نوشتنیِ s1 ساخته می‌شوند،
// نه از یک فیکسچرِ دست‌نخورده با سه انتظارِ متفاوت.
func TestPhaseGoldens(t *testing.T) {
	for _, s := range []string{"s1", "s3", "s4"} {
		t.Run(s, func(t *testing.T) {
			h := openWritableFixture(t)
			switch s {
			case "s3":
				// بی‌وضعیتِ رسمی: phase از تقویم می‌آید.
				mustExec(t, h.Market, `UPDATE market_index SET market_state = NULL,
				    market_state_title = NULL`)
			case "s4":
				// نشستِ فعالیت رویِ جمعه اعلام شده.
				mustExec(t, h.Market, `UPDATE market_index SET d_even = 20261016,
				    activity_h_even = 123000 WHERE d_even = 20261014`)
			}
			got := marketphase.FromDB(h.Market, pinnedNow)
			// golden از مسیرِ session_phase آمده و statusِ route را دارد؛ status
			// مثلِ source مالِ لایهٔ انتقال است، نه خروجیِ موتور.
			compareGolden(t, s+" phase", loadGolden(t, s, "phase"),
				toMap(t, got), "status")
		})
	}
}

// TestSummaryMatchesGolden کلِ بدنهٔ summary را با اوراکلِ پایتون می‌سنجد:
// ده سطر، asof، phase و health.
func TestSummaryMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := summaryPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "summary", loadGolden(t, "s1", "summary"), got)
}

// TestMarketSnapshotMatchesGolden همان بازار/شاخص/prev/retail را قفل می‌کند.
func TestMarketSnapshotMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "market-snapshot", loadGolden(t, "s1", "market_snapshot"), got)
}

// TestSummaryRows: ده سطرِ ثابت به همان ترتیبِ categoryRows، هر سطر با همان
// یازده کلید. buy_power_up از buy_powerِ منتشرشده قابلِ بازسازی است چون در این
// فیکسچر هیچ مقداری رویِ مرزِ گردکردن نیست (مرزِ خام را
// TestSummaryBuyPowerUpUsesRaw می‌سنجد).
func TestSummaryRows(t *testing.T) {
	h := openFixture(t)
	got, err := summaryPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	rows, ok := got["rows"].([]map[string]any)
	if !ok {
		t.Fatalf("rows is %T", got["rows"])
	}
	if len(rows) != len(categoryRows) {
		t.Fatalf("rows = %d, want %d", len(rows), len(categoryRows))
	}
	keys := []string{"key", "label", "symbols", "traded", "volume_b_shares",
		"value_b_toman", "pc_buy_m_toman", "pc_sell_m_toman", "buy_power",
		"buy_power_up", "money_flow_b_toman"}
	up, down := 0, 0
	for i, c := range categoryRows {
		if rows[i]["key"] != c.Key || rows[i]["label"] != c.Label {
			t.Fatalf("row %d = %v/%v, want %v/%v", i, rows[i]["key"],
				rows[i]["label"], c.Key, c.Label)
		}
		if len(rows[i]) != len(keys) {
			t.Fatalf("%s has %d keys, want %d: %v", c.Key, len(rows[i]),
				len(keys), rows[i])
		}
		for _, k := range keys {
			if _, ok := rows[i][k]; !ok {
				t.Fatalf("%s missing key %s", c.Key, k)
			}
		}
		wantUp := false
		if p, ok := rows[i]["buy_power"].(float64); ok && p >= 1.0 {
			wantUp = true
		}
		if rows[i]["buy_power_up"] != wantUp {
			t.Fatalf("%s buy_power_up = %v, want %v from buy_power %v", c.Key,
				rows[i]["buy_power_up"], wantUp, rows[i]["buy_power"])
		}
		if wantUp {
			up++
		} else {
			down++
		}
	}
	if up == 0 || down == 0 {
		t.Fatalf("buy_power_up coverage = %d up / %d down; need both", up, down)
	}
}

// TestBuyPowerUp مرزِ ۱ و «بی‌داده» را جدای از DB قفل می‌کند.
func TestBuyPowerUp(t *testing.T) {
	cases := []struct {
		power float64
		want  bool
	}{
		{math.NaN(), false},
		{0, false},
		{0.999, false},
		{0.9996, false},
		{1.0, true},
		{1.001, true},
		{2.17, true},
	}
	for _, c := range cases {
		if got := buyPowerUp(c.power); got != c.want {
			t.Errorf("buyPowerUp(%v) = %v, want %v", c.power, got, c.want)
		}
	}
}

// TestSummaryBuyPowerUpUsesRaw: قدرتِ خام ۰٫۹۹۹۶ است و منتشرشده‌اش ۱٫۰
// (گردکردن به دو رقم). رنگ باید از خام بیاید: <۱ قرمز، نه سبز.
func TestSummaryBuyPowerUpUsesRaw(t *testing.T) {
	h := openWritableFixture(t)
	mustExec(t, h.Market, `UPDATE client_type SET buy_i_vol = 999600,
	    sell_i_vol = 1000000, buy_count_i = 1000, sell_count_i = 1000
	    WHERE ins_code = 'm7' AND d_even = 20261014`)
	got, err := summaryPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	var gold map[string]any
	for _, r := range got["rows"].([]map[string]any) {
		if r["key"] == "gold_fund" {
			gold = r
		}
	}
	if gold == nil {
		t.Fatal("gold_fund row missing")
	}
	if v := gold["buy_power"].(float64); v != 1.0 {
		t.Fatalf("published buy_power = %v, want 1.0 (rounded from 0.9996)", v)
	}
	if gold["buy_power_up"] != false {
		t.Fatalf("buy_power_up = %v, want false from raw 0.9996",
			gold["buy_power_up"])
	}
}

// TestSummaryHealthLiquidityFallback قاعدهٔ R2 را می‌سنجد: summary به
// macroHealthFrom دستِ db نمی‌دهد، پس «آخرین نشستِ گردش‌دار» نمی‌آورد؛ مسیرِ
// market_snapshot (macroHealth) آن را از market_liquidity می‌خواند.
func TestSummaryHealthLiquidityFallback(t *testing.T) {
	h := openWritableFixture(t)
	mustExec(t, h.Market, `UPDATE market_watch SET q_tot_cap = 0
	    WHERE d_even = (SELECT MAX(d_even) FROM market_watch)`)

	got, err := summaryPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	health, ok := got["health"].(map[string]any)
	if !ok {
		t.Fatalf("health is %T", got["health"])
	}
	if health["state"] != "nodata" || health["label"] != "بدون داده" ||
		health["cause"] != "unknown" {
		t.Fatalf("summary health = %v/%v/%v, want nodata/بدون داده/unknown",
			health["state"], health["label"], health["cause"])
	}
	if v, ok := health["last_traded_session"]; !ok || v != nil {
		t.Fatalf("summary health last_traded_session = %v, want nil (db=nil)", v)
	}
	if v, ok := health["last_value_hemat"]; !ok || v != nil {
		t.Fatalf("summary health last_value_hemat = %v, want nil (db=nil)", v)
	}
	if health["market_value_source"] != "tse_market_overview" ||
		health["market_value_hemat"] != 6.9 {
		t.Fatalf("summary market value = %v/%v, want 6.9/tse_market_overview",
			health["market_value_hemat"], health["market_value_source"])
	}

	// همان صحنه از مسیرِ macroHealth (که market_snapshot صدایش می‌زند).
	direct, err := macroHealth(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	if direct["state"] != "nodata" {
		t.Fatalf("macroHealth state = %v, want nodata", direct["state"])
	}
	if d, ok := i64At(t, direct, "last_traded_session"); !ok || d != 20261014 {
		t.Fatalf("macroHealth last_traded_session = %v/%v, want 20261014/true",
			d, ok)
	}
	if direct["last_value_hemat"] != 18.0 {
		t.Fatalf("macroHealth last_value_hemat = %v, want 18.0",
			direct["last_value_hemat"])
	}

	snap, err := marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	retail := snap["retail"].(map[string]any)
	if retail["value_hemat"] != nil || retail["state"] != "nodata" ||
		retail["label"] != "بدون داده" {
		t.Fatalf("snapshot retail = %v/%v/%v, want nil/nodata/بدون داده",
			retail["value_hemat"], retail["state"], retail["label"])
	}
	if len(retail) != 8 {
		t.Fatalf("retail has %d keys, want the 8-key projection: %v",
			len(retail), retail)
	}
	if _, ok := retail["last_traded_session"]; ok {
		t.Fatal("retail must not leak the liquidity fallback fields")
	}
}
