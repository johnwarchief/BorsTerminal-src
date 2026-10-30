package mstat

import (
	"database/sql"
	"encoding/json"
	"errors"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
)

// enrichRow همان ردیفِ دامپِ `mstat_engine.enrich` است — نه یک پنل، بلکه قابِ
// خامِ ردیف‌ها به‌همراهِ همان چیزی که `money` برایِ هر نماد می‌سازد.
//
// ستون‌هایِ خامی که در `m` نمی‌آیند (`p_first`، `p_min`، `p_max`،
// `price_change`، `total_shares`، `h_even`) عمداً این‌جا هستند: بی‌آن‌ها یک
// جابه‌جاییِ موقعیتی در SELECTِ Go بی‌صدا سبز می‌شد.
type enrichRow struct {
	Code        string         `json:"ins_code"`
	Symbol      string         `json:"symbol"`
	Cls         string         `json:"cls"`
	Kind        string         `json:"kind"`
	Pct         *float64       `json:"pct"`
	ClockPct    *float64       `json:"clock_pct"`
	PFirst      *float64       `json:"p_first"`
	PMin        *float64       `json:"p_min"`
	PMax        *float64       `json:"p_max"`
	PriceChange *float64       `json:"price_change"`
	TotalShares *float64       `json:"total_shares"`
	HEven       *int64         `json:"h_even"`
	Top50       bool           `json:"top50"`
	M           map[string]any `json:"m"`
}

type enrichGolden struct {
	AsOf map[string]any `json:"asof"`
	Rows []enrichRow    `json:"rows"`
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

// openWritableFixture همان کپیِ موقت است، ولی نوشتنی — تست‌هایی که ستون/
// جدولِ همان کپی را عوض می‌کنند (بی‌عمق، بی‌نهایت) هرگز فایلِ ردیابی‌شده را
// نمی‌نویسند.
func openWritableFixture(t *testing.T) *db.Handles {
	t.Helper()
	h, err := db.Open(copyFixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h
}

// depthColumns همان ۱۱ ستونی است که `_row_keys(False)` حذف می‌کند.
var depthColumns = map[string]bool{
	"buy_q_vol": true, "buy_q_val": true, "buy_q_cnt": true,
	"sell_q_vol": true, "sell_q_val": true, "sell_q_cnt": true,
	"buy_q1_vol": true, "buy_q1_px": true, "sell_q1_vol": true,
	"sell_q1_px": true, "buy_q1_cnt": true,
}

// dropDepthColumns جدولِ market_watch را بدونِ ستون‌هایِ عمق بازمی‌سازد —
// همان کاری که اوراکل رویِ کپیِ موقتِ خودش می‌کند. CTAS به‌جایِ ALTER DROP
// COLUMN تا درایورهایِ SQLiteِ کهن هم همان نتیجه را بدهند.
func dropDepthColumns(t *testing.T, conn *sql.DB) {
	t.Helper()
	rows, err := conn.Query("PRAGMA table_info(market_watch)")
	if err != nil {
		t.Fatal(err)
	}
	var cols []string
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			rows.Close()
			t.Fatal(err)
		}
		if !depthColumns[name] {
			cols = append(cols, name)
		}
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		t.Fatal(err)
	}
	rows.Close()
	for _, stmt := range []string{
		"CREATE TABLE market_watch_nodepth AS SELECT " + strings.Join(cols, ", ") +
			" FROM market_watch",
		"DROP TABLE market_watch",
		"ALTER TABLE market_watch_nodepth RENAME TO market_watch",
	} {
		if _, err := conn.Exec(stmt); err != nil {
			t.Fatal(err)
		}
	}
}

// openDepthlessFixture کپیِ موقتِ فیکسچر را بی‌ستون‌هایِ عمق باز می‌کند؛
// پایتون این بانک را «همگام‌نشده» می‌خواند و پنل‌هایِ صف باید بی‌داده شوند.
func openDepthlessFixture(t *testing.T) *db.Handles {
	t.Helper()
	h := openWritableFixture(t)
	dropDepthColumns(t, h.Market)
	return h
}

func readEnrich(t *testing.T, name string) enrichGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", "s1", name))
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
	g := readEnrich(t, "enrich.json")
	h := openFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	checkGolden(t, snap, g)
}

// TestSnapshotDepthlessMatchesGolden قراردادِ بانکِ همگام‌نشده را می‌سنجد:
// ستون‌هایِ عمق نیستند، پس `_row_keys(False)` کلیدهایشان را اصلاً نمی‌گذارد و
// money برایِ هر نماد `bq_val=None` و `qstate='x'` می‌دهد — نه صفرِ خالیِ
// struct که پنل‌هایِ عمق/تفکیکِ مشتریان ردیفِ خیالی می‌شمردند. طلایی از اجرایِ
// تازهٔ همان اوراکلِ پایتون رویِ همان کپیِ بی‌عمق می‌آید.
func TestSnapshotDepthlessMatchesGolden(t *testing.T) {
	g := readEnrich(t, "enrich_nodepth.json")
	if depth, ok := g.AsOf["depth"].(bool); !ok || depth {
		t.Fatalf("golden asof.depth = %v, want false", g.AsOf["depth"])
	}
	// سمتِ پایتون: دامپِ اوراکل خودش باید null/x بدهد، نه صفرِ خالی.
	for _, want := range g.Rows {
		if want.M["bq_val"] != nil || want.M["qstate"] != "x" {
			t.Fatalf("golden %s says bq_val=%v qstate=%v, want null/x",
				want.Code, want.M["bq_val"], want.M["qstate"])
		}
	}
	h := openDepthlessFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if snap.Depth || snap.AsOf.Depth {
		t.Fatalf("snapshot.depth/asof.depth = %v/%v, want false", snap.Depth,
			snap.AsOf.Depth)
	}
	checkGolden(t, snap, g)
	for _, r := range snap.Rows {
		if !isNaN(r.BuyQVol) || !isNaN(r.BuyQVal) || !isNaN(r.BuyQCnt) ||
			!isNaN(r.SellQVol) || !isNaN(r.SellQVal) || !isNaN(r.SellQCnt) ||
			!isNaN(r.BuyQ1Vol) || !isNaN(r.BuyQ1Px) || !isNaN(r.SellQ1Vol) ||
			!isNaN(r.SellQ1Px) || !isNaN(r.BuyQ1Cnt) {
			t.Fatalf("%s depth fields must be NULL (NaN), got %v/%v/%v %v/%v/%v %v/%v %v/%v %v",
				r.Code, r.BuyQVol, r.BuyQVal, r.BuyQCnt, r.SellQVol, r.SellQVal,
				r.SellQCnt, r.BuyQ1Vol, r.BuyQ1Px, r.SellQ1Vol, r.SellQ1Px,
				r.BuyQ1Cnt)
		}
		m := money(r, snap.BaseEst)
		if !isNaN(m.BQVal) || m.QState != "x" {
			t.Fatalf("%s money bq_val/qstate = %v/%s, want null/x", r.Code,
				m.BQVal, m.QState)
		}
	}
}

// checkGolden مقایسهٔ مشترکِ دو دامپ: asof، ترتیبِ ردیف‌ها، و هر عددِ یک ردیف.
func checkGolden(t *testing.T, snap *Snapshot, g enrichGolden) {
	t.Helper()
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

	// ترتیب: طلایی همان ترتیبِ خروجیِ کوئری است؛ مقایسهٔ فقط بر ins_code یک
	// جابه‌جاییِ JOIN/ORDER BY را بی‌صدا سبز می‌کرد.
	for i, want := range g.Rows {
		if snap.Rows[i].Code != want.Code {
			t.Fatalf("row %d = %q, want %q (order must match the oracle)", i,
				snap.Rows[i].Code, want.Code)
		}
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
			// ستون‌هایِ خام — قفلِ موقعیت در SELECT.
			for _, c := range []struct {
				name string
				got  float64
				want *float64
			}{
				{"p_first", got.PFirst, want.PFirst},
				{"p_min", got.PMin, want.PMin},
				{"p_max", got.PMax, want.PMax},
				{"price_change", got.PriceChange, want.PriceChange},
				{"total_shares", got.TotalShares, want.TotalShares},
			} {
				if !eqNum(c.got, c.want) {
					t.Fatalf("%s = %v, want %v", c.name, c.got, show(c.want))
				}
			}
			if want.HEven == nil {
				if got.HasHEven {
					t.Fatalf("h_even = %d, want null", got.HEven)
				}
			} else if !got.HasHEven || got.HEven != *want.HEven {
				t.Fatalf("h_even = %d (has=%v), want %d", got.HEven, got.HasHEven,
					*want.HEven)
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
	// depth را خودِ طلایی تعیین می‌کند: s1 بانکِ همگام‌شده (true) و
	// enrich_nodepth بانکِ بی‌ستونِ عمق (false) را قفل می‌کند.
	depth, ok := want["depth"].(bool)
	if !ok {
		t.Fatalf("golden asof.depth = %v, want bool", want["depth"])
	}
	if got.Depth != depth {
		t.Fatalf("asof.depth = %v, want %v", got.Depth, depth)
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

// eqNum خانهٔ خامِ ردیف را می‌سنجد: nullِ طلایی باید NaN بدهد (قراردادِ
// «NaN یعنی NULL»)، و عدد باید دقیقاً همان عدد باشد.
func eqNum(got float64, want *float64) bool {
	if want == nil {
		return isNaN(got)
	}
	return !isNaN(got) && got == *want
}

func show(p *float64) any {
	if p == nil {
		return nil
	}
	return *p
}

// TestSnapshotInfCollapses: بی‌نهایتِ ذخیره‌شده در REAL با `_f`ِ پایتون صفر
// می‌شود. پیش از اصلاح، Go همان +Inf را تا پنل حمل می‌کرد (`bq_val=+Inf` و
// qstate غلط) و top50 یک نمادِ بی‌قیمت را با cap=+Inf بالا می‌کشید.
func TestSnapshotInfCollapses(t *testing.T) {
	h := openWritableFixture(t)
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET buy_q_val = ? WHERE ins_code = 'm2'", math.Inf(1)); err != nil {
		t.Fatal(err)
	}
	if _, err := h.Market.Exec(
		"UPDATE market_watch SET total_shares = ? WHERE ins_code = 'm1'", math.Inf(1)); err != nil {
		t.Fatal(err)
	}
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	byCode := map[string]*Row{}
	for _, r := range snap.Rows {
		byCode[r.Code] = r
	}
	m2, ok := byCode["m2"]
	if !ok {
		t.Fatal("m2 missing")
	}
	if !math.IsInf(m2.BuyQVal, 1) {
		t.Fatalf("probe: raw buy_q_val = %v, want +Inf from the database", m2.BuyQVal)
	}
	// m2 صفِ فروش دارد (sell_q_val = 5e8)؛ با bq_val=Inf پیش از اصلاح
	// qstate 'z' می‌شد و بعد از _f باید 's' باشد.
	m := money(m2, snap.BaseEst)
	if m.BQVal != 0 {
		t.Fatalf("bq_val = %v, want 0 (python _f(inf))", m.BQVal)
	}
	if m.QState != "s" {
		t.Fatalf("qstate = %s, want s", m.QState)
	}
	top := top50Codes(snap.Rows)
	if top["m1"] {
		t.Fatal("m1 with total_shares=+Inf must not enter top50 (_f(inf)=0)")
	}
	if !top["m2"] {
		t.Fatal("m2 must stay in top50")
	}
}

// fakeRows برایِ شبیه‌سازیِ خطایِ میانِ جریانِ ردیف‌هاست — چیزی که با SQLiteِ
// سالم نمی‌شود ساخت: یا اسکنِ ردیفِ شمارهٔ failScan می‌شکند، یا Err پس از
// پایان خطا می‌دهد.
type fakeRows struct {
	rows     [][]any
	i        int
	failScan int // ۱-پایه؛ ۰ یعنی هیچ
	endErr   error
	done     bool
}

func (f *fakeRows) Next() bool {
	if f.done || f.i >= len(f.rows) {
		f.done = true
		return false
	}
	f.i++
	return true
}

func (f *fakeRows) Scan(dest ...any) error {
	if f.i == f.failScan {
		return errors.New("scan boom")
	}
	if f.i == 0 || f.i > len(f.rows) {
		return errors.New("scan without row")
	}
	row := f.rows[f.i-1]
	if len(dest) != len(row) {
		return errors.New("arity")
	}
	for k, d := range dest {
		p, ok := d.(*any)
		if !ok {
			return errors.New("dest is not *any")
		}
		*p = row[k]
	}
	return nil
}

func (f *fakeRows) Err() error {
	if f.done {
		return f.endErr
	}
	return nil
}

// TestMidStreamSQLErrorsDiscardResults: پایتون هر دو کوئری را با fetchall
// می‌خواند؛ خطایِ میانِ راه استثنا می‌دهد و except آن نتیجه را کامل دور
// می‌ریزد. نگه‌داشتنِ ردیف‌هایِ پیش از خطا یک value_source/برآوردِ می‌سازد که
// پایتون هرگز نمی‌دهد.
func TestMidStreamSQLErrorsDiscardResults(t *testing.T) {
	ctv := [][]any{
		{"a", 1.0, 2.0, 3.0, 4.0, 5.0},
		{"b", 6.0, 7.0, 8.0, 9.0, 10.0},
	}
	base := [][]any{{"a", 10.0}, {"a", 20.0}}

	if got, ok := scanCTV(&fakeRows{rows: ctv}); !ok || len(got) != 2 {
		t.Fatalf("clean CTV scan = %v/%d rows, want ok/2", ok, len(got))
	}
	if got, ok := scanCTV(&fakeRows{rows: ctv, failScan: 2}); ok || got != nil {
		t.Fatalf("CTV scan error kept %d rows, want whole result discarded", len(got))
	}
	if got, ok := scanCTV(&fakeRows{rows: ctv, endErr: errors.New("stream boom")}); ok || got != nil {
		t.Fatalf("CTV rows.Err kept %d rows, want whole result discarded", len(got))
	}

	if got := collectBaseVolumes(&fakeRows{rows: base}); len(got) != 1 || got["a"] != 15 {
		t.Fatalf("clean base = %v, want a:15", got)
	}
	if got := collectBaseVolumes(&fakeRows{rows: base, failScan: 2}); len(got) != 0 {
		t.Fatalf("base scan error = %v, want empty map", got)
	}
	if got := collectBaseVolumes(&fakeRows{rows: base, endErr: errors.New("stream boom")}); len(got) != 0 {
		t.Fatalf("base rows.Err = %v, want empty map", got)
	}
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
