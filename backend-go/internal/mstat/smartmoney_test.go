package mstat

import (
	"database/sql"
	"testing"
)

// fixtureS5 همان صحنهٔ ۵ِ اوراکل: نشستِ جاری با سه روزِ mstat_snap. SQL عیناً
// همان است که gen_mstat_golden.py اجرا می‌کند؛ هر تغییرِ یکی باید آن یکی را
// قرمز کند (طلاییِ s5/smart_money.json).
func fixtureS5(t *testing.T) *sql.DB {
	t.Helper()
	h := openWritableFixture(t)
	for _, stmt := range []string{
		`INSERT INTO mstat_snap (d_even, h_even, agg)
		 SELECT d_even-1, h_even, json_set(agg, '$.d_even', d_even-1)
		 FROM mstat_snap WHERE d_even=20261014`,
		`INSERT INTO mstat_snap (d_even, h_even, agg)
		 SELECT d_even-2, h_even, json_set(agg, '$.d_even', d_even-2)
		 FROM mstat_snap WHERE d_even=20261014`,
		`UPDATE mstat_snap SET d_even=20261028,
		 agg=json_set(agg, '$.d_even', 20261028) WHERE d_even=20261014`,
		`UPDATE market_index SET d_even=20261028, market_state='A',
		 market_state_title='باز', activity_h_even=103000,
		 updated_at='2026-10-28 10:29:00' WHERE d_even=20261014`,
	} {
		if _, err := h.Market.Exec(stmt); err != nil {
			t.Fatalf("s5 fixture: %v", err)
		}
	}
	return h.Market
}

func TestSmartMoneyMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := smartMoneyPanel(h.Market, pinnedNow, newVerdictMemo())
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "smart-money", loadGolden(t, "s1", "smart_money"), got)
}

// TestSmartMoneyContinuousMatchesGolden شاخهٔ جمعِ تا-لحظه را می‌سنجد: phase
// continuous، آغازِ واقعیِ ۱۰:۰۰، pace از دو نشستِ پیش، و روندِ جریان.
func TestSmartMoneyContinuousMatchesGolden(t *testing.T) {
	got, err := smartMoneyPanel(fixtureS5(t), pinnedNow, newVerdictMemo())
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "smart-money-s5", loadGolden(t, "s5", "smart_money"), got)
}

// TestSmartMoneyKeepsLegacyShape قیدهایِ بدنه را بی‌طرفِ طلایی قفل می‌کند: پنج
// درِ حکم با همان کلیدها، شرطِ ۸۰٪ رویِ درصدِ گردنشده، و trio از خودِ flow.
func TestSmartMoneyKeepsLegacyShape(t *testing.T) {
	h := openFixture(t)
	got, err := smartMoneyPanel(h.Market, pinnedNow, newVerdictMemo())
	if err != nil {
		t.Fatal(err)
	}
	verdict := got["verdict"].(map[string]any)
	gates := verdict["gates"].([]map[string]any)
	want := []string{"liquidity", "continuity", "breadth", "flow", "window"}
	if len(gates) != len(want) {
		t.Fatalf("gates = %d, want %d", len(gates), len(want))
	}
	for i, k := range want {
		if gates[i]["key"] != k {
			t.Fatalf("gates[%d] = %v, want %s", i, gates[i]["key"], k)
		}
		for _, f := range []string{"label", "short", "state", "label_state", "vote", "detail", "rule", "why"} {
			if _, ok := gates[i][f]; !ok {
				t.Errorf("gate %s missing %q", k, f)
			}
		}
	}
	entry := got["watch_entry"].(map[string]any)
	if entry["rule_pct"] != 80.0 || entry["known"] == 0 {
		t.Errorf("watch_entry = %v", entry)
	}
	flow := got["flow"].(map[string]any)
	if _, ok := flow["trio_fts"]; !ok {
		t.Error("flow.trio_fts missing")
	}
	for _, k := range []string{"stage", "stage_label", "confirm_streak",
		"confirm_required", "flow_trend", "limitations", "for", "against"} {
		if _, ok := verdict["market_state"].(map[string]any)[k]; !ok {
			t.Errorf("market_state missing %q", k)
		}
	}
}
