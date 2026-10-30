package mstat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
)

// enrichGolden همان دامپِ `mstat_engine.enrich` است — نه یک پنل، بلکه قابِ
// خامِ ردیف‌ها به‌همراهِ همان چیزی که `money` برایِ هر نماد می‌سازد.
type enrichGolden struct {
	AsOf map[string]any `json:"asof"`
	Rows []struct {
		Code     string         `json:"ins_code"`
		Symbol   string         `json:"symbol"`
		Cls      string         `json:"cls"`
		Kind     string         `json:"kind"`
		Pct      *float64       `json:"pct"`
		ClockPct *float64       `json:"clock_pct"`
		Top50    bool           `json:"top50"`
		M        map[string]any `json:"m"`
	} `json:"rows"`
}

// copyFixture فیکسچرِ mstat را در t.TempDir() کپی می‌کند؛ فایلِ ردیابی‌شده
// هرگز باز نوشتنی نمی‌شود (همان الگویِ تست‌هایِ B1).
func copyFixture(t *testing.T) string {
	t.Helper()
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join("testdata", "fixture", name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dst
}

func openFixture(t *testing.T) *db.Handles {
	t.Helper()
	h, err := db.Open(copyFixture(t), true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h
}

func readEnrich(t *testing.T) enrichGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", "s1", "enrich.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g enrichGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// TestSnapshotMatchesGolden ردیف‌به‌ردیفِ enrich را با اوراکلِ پایتون می‌سنجد؛
// این تست فقط شکل را نمی‌بیند — هر یکایِ ریالی، VWAP، سرانه، قدرت، جریان،
// value_source و qstate را هم قفل می‌کند.
func TestSnapshotMatchesGolden(t *testing.T) {
	g := readEnrich(t)
	h := openFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if len(snap.Rows) != len(g.Rows) {
		t.Fatalf("rows = %d, want %d", len(snap.Rows), len(g.Rows))
	}
	checkAsOf(t, snap.AsOf, g.AsOf, len(snap.Rows))

	top50 := top50Codes(snap.Rows)
	// همان کاری که enrichِ پایتون می‌کند: نشانِ top50 رویِ خودِ ردیف می‌نشیند
	// تا تست، خروجیِ top50Codes را هم بسنجد.
	for _, r := range snap.Rows {
		r.Top50 = top50[r.Code]
	}
	if n, ok := asOfInt(t, g.AsOf, "top50"); ok && int64(len(top50)) != n {
		t.Fatalf("top50 = %d, want %d", len(top50), n)
	}

	byCode := map[string]*Row{}
	for _, r := range snap.Rows {
		if _, dup := byCode[r.Code]; dup {
			t.Fatalf("duplicate ins_code %q", r.Code)
		}
		byCode[r.Code] = r
	}
	for _, want := range g.Rows {
		t.Run(want.Code, func(t *testing.T) {
			got, ok := byCode[want.Code]
			if !ok {
				t.Fatalf("golden row missing from snapshot")
			}
			if got.Symbol != want.Symbol || got.Cls != want.Cls || got.Kind != want.Kind {
				t.Fatalf("identity = %s/%s/%s, want %s/%s/%s", got.Symbol,
					got.Cls, got.Kind, want.Symbol, want.Cls, want.Kind)
			}
			if !eqPtr(got.Pct, want.Pct) {
				t.Fatalf("pct = %v, want %v", show(got.Pct), show(want.Pct))
			}
			if !eqPtr(got.ClockPct, want.ClockPct) {
				t.Fatalf("clock_pct = %v, want %v", show(got.ClockPct), show(want.ClockPct))
			}
			if got.Top50 != want.Top50 {
				t.Fatalf("top50 = %v, want %v", got.Top50, want.Top50)
			}
			m := money(got, snap.BaseEst)
			checkMoney(t, m, want.M)
		})
	}
}

func asOfInt(t *testing.T, m map[string]any, k string) (int64, bool) {
	t.Helper()
	v, ok := m[k]
	if !ok {
		t.Fatalf("asof has no key %s", k)
	}
	if v == nil {
		return 0, false
	}
	f, ok := v.(float64)
	if !ok {
		t.Fatalf("asof.%s is %T, want number", k, v)
	}
	return int64(f), true
}

func checkAsOf(t *testing.T, got AsOf, want map[string]any, rows int) {
	t.Helper()
	if d, ok := asOfInt(t, want, "d_even"); ok {
		if got.DEven == nil || *got.DEven != d {
			t.Fatalf("asof.d_even = %v, want %d", got.DEven, d)
		}
	} else if got.DEven != nil {
		t.Fatalf("asof.d_even = %v, want null", *got.DEven)
	}
	if h, _ := asOfInt(t, want, "h_even"); got.HEven != h {
		t.Fatalf("asof.h_even = %d, want %d", got.HEven, h)
	}
	if c, ok := asOfInt(t, want, "client_d_even"); ok {
		if got.ClientDEven == nil || *got.ClientDEven != c {
			t.Fatalf("asof.client_d_even = %v, want %d", got.ClientDEven, c)
		}
	} else if got.ClientDEven != nil {
		t.Fatalf("asof.client_d_even = %v, want null", *got.ClientDEven)
	}
	lag, hasLag := want["client_lag_days"].(bool)
	if hasLag {
		if got.ClientLag == nil || *got.ClientLag != lag {
			t.Fatalf("asof.client_lag_days = %v, want %v", got.ClientLag, lag)
		}
	} else if got.ClientLag != nil {
		t.Fatalf("asof.client_lag_days = %v, want null", *got.ClientLag)
	}
	depth, ok := want["depth"].(bool)
	if !ok || !depth {
		t.Fatalf("golden asof.depth = %v, want true (fixture has depth)", want["depth"])
	}
	if !got.Depth {
		t.Fatal("asof.depth = false, want true")
	}
	if n, ok := asOfInt(t, want, "n"); ok && int64(rows) != n {
		t.Fatalf("asof.n = %d, want %d", rows, n)
	}
}

func eqPtr(a, b *float64) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func show(p *float64) any {
	if p == nil {
		return nil
	}
	return *p
}

// checkMoney هر عددِ ریالی را با تساویِ دقیق می‌سنجد و null را از عدد جدا
// نگه می‌دارد: خانهٔ nullِ طلایی باید NaN بدهد و خانهٔ عددی باید همان عدد.
func checkMoney(t *testing.T, m Money, want map[string]any) {
	t.Helper()
	pairs := map[string]float64{
		"vol": m.Vol, "val": m.Val, "vwap": m.Vwap, "trades": m.Trades,
		"bq_val": m.BQVal, "sq_val": m.SQVal, "bq_vol": m.BQVol, "sq_vol": m.SQVol,
		"bq_cnt": m.BQCnt, "sq_cnt": m.SQCnt, "bq1_vol": m.BQ1Vol, "bq1_px": m.BQ1Px,
		"sq1_vol": m.SQ1Vol, "sq1_px": m.SQ1Px,
		"retail_buy": m.RetailBuy, "retail_sell": m.RetailSell,
		"inst_buy": m.InstBuy, "inst_sell": m.InstSell,
		"ddd_buy": m.DDDBuy, "pc_buy": m.PCBuy, "pc_sell": m.PCSell,
		"power": m.Power, "flow": m.Flow, "base": m.Base,
	}
	for k, got := range pairs {
		w, ok := want[k]
		if !ok {
			t.Fatalf("golden has no key %s", k)
		}
		if w == nil {
			if !isNaN(got) {
				t.Fatalf("%s = %v, want null", k, got)
			}
			continue
		}
		wf, ok := w.(float64)
		if !ok {
			t.Fatalf("%s golden is %T, want number", k, w)
		}
		if isNaN(got) || got != wf {
			t.Fatalf("%s = %v, want %v", k, got, wf)
		}
	}
	if want["value_source"] != m.ValueSource {
		t.Fatalf("value_source = %s, want %v", m.ValueSource, want["value_source"])
	}
	if want["qstate"] != m.QState {
		t.Fatalf("qstate = %s, want %v", m.QState, want["qstate"])
	}
	if want["has_ct"] != m.HasCT {
		t.Fatalf("has_ct = %v, want %v", m.HasCT, want["has_ct"])
	}
	for k, got := range map[string]int64{"n_buy_i": m.NBuyI, "n_sell_i": m.NSellI,
		"n_buy_n": m.NBuyN, "n_sell_n": m.NSellN} {
		wf, ok := want[k].(float64)
		if !ok {
			t.Fatalf("%s golden is %T, want number", k, want[k])
		}
		if float64(got) != wf {
			t.Fatalf("%s = %d, want %v", k, got, want[k])
		}
	}
}
