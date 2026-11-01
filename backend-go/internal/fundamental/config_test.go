package fundamental

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

// وکتورها را اوراکلِ پایتون می‌سازد: tools/parity/gen_fundamental_vectors.py →
// testdata/vectors/*.json. هیچ انتظاری درِ این فایل دست‌نویس نیست.

func loadVectors(t *testing.T, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "vectors", name))
	if err != nil {
		t.Fatalf("run tools/parity/gen_fundamental_vectors.py first: %v", err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

// nearlyEqual مثلِ مقایسۀ عددیِ پاریتی: رقم‌هایِ اعشاریِ same-value باید برابر
// باشند؛ bool با عدد یکی نیست (Python 1 == True، ولی درِ payload این دو فرق دارند).
func nearlyEqual(t *testing.T, path string, want, got any) {
	t.Helper()
	switch w := want.(type) {
	case nil:
		if got != nil {
			t.Errorf("%s: want nil, got %#v", path, got)
		}
	case bool:
		g, ok := got.(bool)
		if !ok || g != w {
			t.Errorf("%s: want bool %v, got %#v", path, w, got)
		}
	case float64:
		g, ok := asFloat(got)
		if !ok {
			t.Errorf("%s: want number %v, got %#v", path, w, got)
			return
		}
		if math.Abs(g-w) > 1e-12*math.Max(1, math.Abs(w)) {
			t.Errorf("%s: want %v, got %v", path, w, g)
		}
	case string:
		g, ok := got.(string)
		if !ok || g != w {
			t.Errorf("%s: want %q, got %#v", path, w, got)
		}
	case []any:
		g, ok := got.([]string)
		if !ok {
			if g2, ok2 := got.([]any); ok2 {
				g = make([]string, len(g2))
				for i := range g2 {
					g[i], _ = g2[i].(string)
				}
			} else {
				t.Errorf("%s: want list %v, got %#v", path, w, got)
				return
			}
		}
		want2 := make([]string, len(w))
		for i := range w {
			want2[i], _ = w[i].(string)
		}
		if !reflect.DeepEqual(g, want2) {
			t.Errorf("%s: want %v, got %v", path, want2, g)
		}
	case map[string]any:
		g, ok := got.(map[string]any)
		if !ok {
			t.Errorf("%s: want object, got %#v", path, got)
			return
		}
		for k := range w {
			nearlyEqual(t, path+"."+k, w[k], g[k])
		}
		for k := range g {
			if _, ok := w[k]; !ok {
				t.Errorf("%s.%s: extra key in Go output", path, k)
			}
		}
	default:
		if !reflect.DeepEqual(want, got) {
			t.Errorf("%s: want %#v got %#v", path, want, got)
		}
	}
}

// TestThresholdVectors ترتیبِ پرابِ آستانه‌ها را شاخه‌به‌شاخه می‌پاید — همان‌جا که
// بازبینی گفت «این شاخه دیده نمی‌شود».
func TestThresholdVectors(t *testing.T) {
	v := loadVectors(t, "thresholds.json")
	cases, _ := v["cases"].([]any)
	if len(cases) < 15 {
		t.Fatalf("threshold vectors are empty (%d)", len(cases))
	}
	seenProbeFlip := 0
	for i, raw := range cases {
		c := raw.(map[string]any)
		cfg := c["cfg"].(map[string]any)
		want := c["out"].(map[string]any)
		got := V10Thresholds(deepCopyMap(cfg))
		for _, key := range []string{"monetary_growth_min", "monetary_growth_target",
			"margin_min", "margin_ideal", "eps_years", "volume_growth_min",
			"volume_breadth_min", "sales_to_mcap_min", "potential_min",
			"inflation_benchmark", "inflation_basis"} {
			nearlyEqual(t, casePath(i, cfg, key), want[key], got[key])
		}
		if len(cfg) > 0 && toF(got["margin_min"]) != 20.0 {
			seenProbeFlip++
		}
	}
	if seenProbeFlip == 0 {
		t.Error("no vector actually moved margin_min — the probe order is untested")
	}
}

func casePath(i int, cfg map[string]any, key string) string {
	return "case " + itoa(i) + " cfg=" + mustJSON(cfg) + " " + key
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	return s
}

func mustJSON(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

func deepCopyMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

// TestFtsConfigVectors پاک‌سازیِ نوع و boundها را از فایلِ تنظیمات می‌خواند.
func TestFtsConfigVectors(t *testing.T) {
	cases, _ := loadVectors(t, "config.json")["cases"].([]any)
	if len(cases) < 12 {
		t.Fatalf("config vectors are empty (%d)", len(cases))
	}
	dir := t.TempDir()
	probe := 0
	for _, raw := range cases {
		c := raw.(map[string]any)
		label, _ := c["label"].(string)
		path := filepath.Join(dir, "fts_thresholds.json")
		if c["file"] == nil && label == "missing" {
			_ = os.Remove(path)
		} else {
			body, err := json.Marshal(c["file"])
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, body, 0o644); err != nil {
				t.Fatal(err)
			}
		}
		want, _ := c["out"].(map[string]any)
		if c["error"] != nil {
			t.Skipf("%s: python raised %v", label, c["error"])
		}
		got := LoadFtsConfig(dir)
		for _, key := range []string{"eps_years", "watchlist_max", "suspended_max_stale_sessions",
			"hourglass_rsi_period", "hourglass_rsi_oversold", "hourglass_ma52_position",
			"industry_mode", "mandatory_sectors", "free_sectors", "include_industries",
			"exclude_industries", "exclude_rejected_indicators", "filter_m141",
			"exclude_base_market", "holdings_sales_na", "growth_min", "margin_min",
			"mcap_min_hmt", "min_trade_val", "sales_to_mcap_ideal", "profit_potential_min",
			"pharma_margin_exempt_min", "v10_monetary_growth_min", "v10_inflation_basis"} {
			if w, ok := want[key]; ok {
				nearlyEqual(t, label+"."+key, w, got[key])
			}
		}
		if label == "body14" {
			if b, ok := got["filter_m141"].(bool); !ok || !b {
				t.Errorf("body14: filter_m141 must coerce 1 → true, got %#v", got["filter_m141"])
			}
			probe++
		}
		if label == "body6" {
			if p, ok := got["hourglass_rsi_period"].(int); !ok || p != 7 {
				t.Errorf("body6: out-of-range period must fall back to 7, got %#v", got["hourglass_rsi_period"])
			}
			probe++
		}
		if label == "body10" {
			if p, ok := got["eps_years"].(int); !ok || p != 6 {
				t.Errorf("body10: legacy streak_periods must migrate to eps_years=6, got %#v", got["eps_years"])
			}
			probe++
		}
	}
	if probe != 3 {
		t.Errorf("only %d of the three discriminating config cases were exercised", probe)
	}
}

// TestMathIsInt مثلِ `parsed.is_integer()`: 7.0 عددِ صحیح است، 7.5 نه.
func TestHourglassPeriodKeepsIntegralFloat(t *testing.T) {
	dir := t.TempDir()
	body, _ := json.Marshal(map[string]any{"hourglass_rsi_period": 7.0})
	if err := os.WriteFile(filepath.Join(dir, "fts_thresholds.json"), body, 0o644); err != nil {
		t.Fatal(err)
	}
	if p, ok := LoadFtsConfig(dir)["hourglass_rsi_period"].(int); !ok || p != 7 {
		t.Errorf("7.0 must stay 7 (int), got %#v", LoadFtsConfig(dir)["hourglass_rsi_period"])
	}
	body, _ = json.Marshal(map[string]any{"hourglass_rsi_period": 7.5})
	if err := os.WriteFile(filepath.Join(dir, "fts_thresholds.json"), body, 0o644); err != nil {
		t.Fatal(err)
	}
	if p, ok := LoadFtsConfig(dir)["hourglass_rsi_period"].(int); !ok || p != 7 {
		t.Errorf("7.5 is not integral in Python — it falls back to the default 7, got %#v",
			LoadFtsConfig(dir)["hourglass_rsi_period"])
	}
}

// TestNoOrFallbackForZeroInflation صفرِ کاربر باید صفر بماند.
func TestNoOrFallbackForZeroInflation(t *testing.T) {
	got := V10Thresholds(map[string]any{"v10_inflation_basis": 0.0})
	if f, _ := got["inflation_benchmark"].(float64); f != 0.0 {
		t.Errorf("inflation 0 must stay 0, got %v", got["inflation_benchmark"])
	}
	got = V10Thresholds(map[string]any{"v10_inflation_basis": -1.0})
	if f, _ := got["inflation_benchmark"].(float64); f != 60.0 {
		t.Errorf("negative basis must fall back to 60, got %v", got["inflation_benchmark"])
	}
}
