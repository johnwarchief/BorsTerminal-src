package mstat

import (
	"database/sql"
	"math"
	"testing"
	"time"

	"borsterminal/backend/internal/marketphase"
)

func i64p(v int64) *int64   { return &v }
func strp(v string) *string { return &v }

func mustExec(t *testing.T, db *sql.DB, q string, args ...any) {
	t.Helper()
	if _, err := db.Exec(q, args...); err != nil {
		t.Fatalf("exec %q: %v", q, err)
	}
}

// i64At خانه‌ای را می‌خواند که یا int64 است (خروجیِ SQL/سری) یا *int64
// (فیلدهایِ Phase که مستقیم در map نشسته‌اند).
func i64At(t *testing.T, m map[string]any, k string) (int64, bool) {
	t.Helper()
	v, ok := m[k]
	if !ok {
		t.Fatalf("missing key %s", k)
	}
	if v == nil {
		return 0, false
	}
	switch n := v.(type) {
	case int64:
		return n, true
	case *int64:
		if n == nil {
			return 0, false
		}
		return *n, true
	default:
		t.Fatalf("%s is %T, want int64", k, v)
		return 0, false
	}
}

// dropIndexTotals ستون‌هایِ گردشِ market_index را حذف می‌کند — همان بانکِ
// کهنه‌ای که market_index_series باید با کوئریِ باریک‌تر از آن بخواند.
func dropIndexTotals(t *testing.T, conn *sql.DB) {
	t.Helper()
	for _, stmt := range []string{
		`CREATE TABLE market_index_notot AS SELECT d_even, idx_last, idx_change,
		    idx_pct, ew_last, ew_change, ew_pct, updated_at, market_state,
		    market_state_title, activity_h_even FROM market_index`,
		"DROP TABLE market_index",
		"ALTER TABLE market_index_notot RENAME TO market_index",
	} {
		mustExec(t, conn, stmt)
	}
}

// TestMarketIndexSeries دو ردیفِ فیکسچر را با ترتیبِ تازه‌ترین-اول و همان
// ارقامِ بانک می‌سنجد؛ هیچ ستونی بازمحاسبه نمی‌شود.
func TestMarketIndexSeries(t *testing.T) {
	h := openFixture(t)
	s := marketIndexSeries(h.Market, 2)
	if len(s) != 2 {
		t.Fatalf("series = %d rows, want 2", len(s))
	}
	if s[0]["d_even"] != int64(20261014) || s[1]["d_even"] != int64(20261013) {
		t.Fatalf("order = %v/%v, want 20261014/20261013",
			s[0]["d_even"], s[1]["d_even"])
	}
	type row struct {
		last, change, pct, ewLast, ewChange, ewPct float64
		z, qCap, qTran                             float64
	}
	want := []row{
		{7153088.29, -103912.4, -1.43, 1929823.43, -9112.1, -0.47,
			120000.0, 64000000000000.0, 3100000000.0},
		{7257000.69, 81234.5, 1.13, 1938935.53, 6210.4, 0.32,
			110000.0, 65000000000000.0, 2900000000.0},
	}
	keys := []string{"last", "change", "pct", "ew_last", "ew_change", "ew_pct",
		"z_tot_tran", "q_tot_cap", "q_tot_tran"}
	for i, w := range want {
		vals := []float64{w.last, w.change, w.pct, w.ewLast, w.ewChange, w.ewPct,
			w.z, w.qCap, w.qTran}
		for j, k := range keys {
			got, ok := s[i][k].(float64)
			if !ok || got != vals[j] {
				t.Fatalf("row %d %s = %v, want %v", i, k, s[i][k], vals[j])
			}
		}
	}
	if len(marketIndexSeries(h.Market, 1)) != 1 {
		t.Fatalf("limit 1 = %d rows", len(marketIndexSeries(h.Market, 1)))
	}
	// Python: int(limit or 1) — صفر و منفی هر دو یک ردیف.
	// (سقفِ ۶۰ با دو ردیفِ فیکسچر قابلِ سنجش نیست.)
	for _, lim := range []int{0, -5} {
		if got := marketIndexSeries(h.Market, lim); len(got) != 1 ||
			got[0]["d_even"] != int64(20261014) {
			t.Fatalf("limit %d = %v, want one newest row", lim, got)
		}
	}
	idx := marketIndex(h.Market)
	if len(idx) != 7 {
		t.Fatalf("market_index keys = %d, want 7: %v", len(idx), idx)
	}
	if _, ok := idx["z_tot_tran"]; ok {
		t.Fatal("market_index must not carry turnover columns")
	}
}

// TestMarketIndexSeriesZeroIsNull: ۰ و بی‌نهایت با _f به «غایب» می‌رسند، نه
// عددِ باورپذیر. پیش از اصلاح، +Inf تا پاسخ حمل می‌شد.
func TestMarketIndexSeriesZeroIsNull(t *testing.T) {
	h := openWritableFixture(t)
	mustExec(t, h.Market, `UPDATE market_index SET idx_change = 0, ew_change = NULL,
	    q_tot_cap = 0 WHERE d_even = 20261014`)
	mustExec(t, h.Market, `UPDATE market_index SET idx_pct = ? WHERE d_even = 20261013`,
		math.Inf(1))
	s := marketIndexSeries(h.Market, 2)
	if len(s) != 2 {
		t.Fatalf("series = %d rows, want 2", len(s))
	}
	for _, k := range []string{"change", "ew_change", "q_tot_cap"} {
		if s[0][k] != nil {
			t.Fatalf("row0 %s = %v, want nil (zero is absent)", k, s[0][k])
		}
	}
	if s[1]["pct"] != nil {
		t.Fatalf("row1 pct = %v, want nil (_f(inf)=0)", s[1]["pct"])
	}
}

// TestMarketIndexSeriesOldSchema: بانکِ بی‌ستونِ گردش باید سری را بدهد و
// ستون‌هایِ گردش null بمانند — نه صفر.
func TestMarketIndexSeriesOldSchema(t *testing.T) {
	h := openWritableFixture(t)
	dropIndexTotals(t, h.Market)
	s := marketIndexSeries(h.Market, 2)
	if len(s) != 2 {
		t.Fatalf("series = %d rows, want 2", len(s))
	}
	for i := range s {
		for _, k := range []string{"z_tot_tran", "q_tot_cap", "q_tot_tran"} {
			if s[i][k] != nil {
				t.Fatalf("row %d %s = %v, want nil on old schema", i, k, s[i][k])
			}
		}
	}
	snap, err := marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	market := snap["market"].(map[string]any)
	for _, k := range []string{"trade_value_hemat", "volume", "trades"} {
		if market[k] != nil {
			t.Fatalf("market.%s = %v, want nil without turnover columns", k, market[k])
		}
	}
	prev := snap["prev"].(map[string]any)
	if prev["q_tot_cap"] != nil || prev["z_tot_tran"] != nil {
		t.Fatalf("prev turnover = %v/%v, want nil", prev["q_tot_cap"], prev["z_tot_tran"])
	}
}

// TestMarketSnapshotPrevSelection: prev ردیفِ دومِ سری است؛ با یک ردیف null
// می‌شود (نه خودِ cur) و بدونِ ردیف، asof شیءِ {"d_even": null} می‌ماند.
func TestMarketSnapshotPrevSelection(t *testing.T) {
	h := openWritableFixture(t)
	snap, err := marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	prev, ok := snap["prev"].(map[string]any)
	if !ok || prev["d_even"] != int64(20261013) {
		t.Fatalf("prev = %v, want the 20261013 row", snap["prev"])
	}
	if prev["q_tot_cap"] != float64(65000000000000) {
		t.Fatalf("prev.q_tot_cap = %v, want full series row", prev["q_tot_cap"])
	}
	mustExec(t, h.Market, "DELETE FROM market_index WHERE d_even = 20261013")
	snap, err = marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	if snap["prev"] != nil {
		t.Fatalf("prev = %v, want nil with one row", snap["prev"])
	}
	if snap["index"] == nil {
		t.Fatal("index must stay non-nil with one row")
	}

	mustExec(t, h.Market, "DELETE FROM market_index")
	snap, err = marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	asof, ok := snap["asof"].(map[string]any)
	if !ok || len(asof) != 1 || asof["d_even"] != nil {
		t.Fatalf("asof = %#v, want object with d_even:null", snap["asof"])
	}
	if snap["index"] != nil || snap["prev"] != nil {
		t.Fatalf("index/prev = %v/%v, want nil/nil", snap["index"], snap["prev"])
	}
	market := snap["market"].(map[string]any)
	if market["trade_value_hemat"] != nil || market["volume"] != nil ||
		market["trades"] != nil {
		t.Fatalf("market = %v, want nil turnover without rows", market)
	}
}

// TestMarketTotalRials: عددِ رسمیِ باورپذیر بر جمعِ تابلو مقدم است، ردیفِ نصفه
// رد می‌شود، و در نبودِ هر دو عددِ ساختگی ساخته نمی‌شود.
func TestMarketTotalRials(t *testing.T) {
	h := openFixture(t)
	got, src := marketTotalRials(h.Market)
	if got != 69000000000000 || src != "tse_market_overview" {
		t.Fatalf("total = %v/%s, want 69e12/tse_market_overview", got, src)
	}
	// ردیفِ تازه‌ترین ۱e12 است ولی نصفِ مرجع (۱۰e12) هم نیست: نباید برنده شود.
	if got == 1000000000000 {
		t.Fatal("half-written newest market_totals row was accepted")
	}

	// منبعِ رسمی نیست: جمعِ dedupedِ تابلو (۲۰e12 در فیکسچر) با منبعِ خودش.
	h2 := openWritableFixture(t)
	mustExec(t, h2.Market, "DELETE FROM market_totals")
	est, src := marketTotalRials(h2.Market)
	if est != 20000000000000 || src != "board_sum_deduped" {
		t.Fatalf("fallback = %v/%s, want 20e12/board_sum_deduped", est, src)
	}

	// مرزِ باورپذیری: دقیقاً نصفِ مرجع پذیرفته می‌شود (>= lo).
	mustExec(t, h2.Market, `INSERT INTO market_totals (d_even, market_value)
	    VALUES (20261014, ?)`, est*0.5)
	half, src := marketTotalRials(h2.Market)
	if half != est*0.5 || src != "tse_market_overview" {
		t.Fatalf("half boundary = %v/%s, want %v/tse_market_overview",
			half, src, est*0.5)
	}
	// یک ذره پایین‌ترِ مرز رد می‌شود و به تابلو برمی‌گردد.
	mustExec(t, h2.Market, "UPDATE market_totals SET market_value = ?", est*0.4999)
	below, src := marketTotalRials(h2.Market)
	if below != est || src != "board_sum_deduped" {
		t.Fatalf("below boundary = %v/%s, want %v/board_sum_deduped",
			below, src, est)
	}

	// نبودِ هر دو منبع: صفر با منبعِ unavailable — نه صفرِ جعلیِ بی‌منبع.
	h3 := openWritableFixture(t)
	mustExec(t, h3.Market, "DELETE FROM market_totals")
	mustExec(t, h3.Market, "UPDATE market_watch SET market_cap = 0")
	zero, src := marketTotalRials(h3.Market)
	if zero != 0 || src != "unavailable" {
		t.Fatalf("no source = %v/%s, want 0/unavailable", zero, src)
	}
}

// TestMacroHealthThresholds مرزهایِ ۲۰/۱۰/۵۰ همت را از دو طرف می‌سنجد و
// نشان می‌دهد داور رویِ عددِ خام است، نه عددِ گردشدهٔ منتشرشده.
func TestMacroHealthThresholds(t *testing.T) {
	cases := []struct {
		hemat     float64
		state     string
		label     string
		excellent bool
		published float64
	}{
		{20.0, "good", "مساعد", false, 20.0},
		{20.004, "good", "مساعد", false, 20.0},
		{19.999, "mid", "متوسط", false, 20.0}, // خام < ۲۰ است ولی منتشرشده ۲۰
		{10.0, "bad", "نامساعد", false, 10.0},
		{10.001, "mid", "متوسط", false, 10.0}, // خام > ۱۰ است ولی منتشرشده ۱۰
		{50.0, "good", "مساعد", true, 50.0},
		{49.999, "good", "مساعد", false, 50.0},
	}
	for _, c := range cases {
		got := macroHealthFrom(&Agg{NTraded: 1, ValHemat: c.hemat}, nil, 0, "", nil, nil)
		if got["state"] != c.state || got["label"] != c.label ||
			got["excellent"] != c.excellent {
			t.Errorf("hemat %v: state/label/excellent = %v/%v/%v, want %v/%v/%v",
				c.hemat, got["state"], got["label"], got["excellent"],
				c.state, c.label, c.excellent)
		}
		if v := got["value_hemat"].(float64); v != c.published {
			t.Errorf("hemat %v: published = %v, want %v", c.hemat, v, c.published)
		}
		if got["good_min"] != 20.0 || got["bad_max"] != 10.0 ||
			got["excellent_min"] != 50.0 {
			t.Errorf("hemat %v: thresholds = %v/%v/%v", c.hemat,
				got["good_min"], got["bad_max"], got["excellent_min"])
		}
		if got["market_value_hemat"] != nil || got["market_value_source"] != nil {
			t.Errorf("hemat %v: market value = %v/%v, want nil/nil", c.hemat,
				got["market_value_hemat"], got["market_value_source"])
		}
	}
	// کلِ بازار فقط گزارش می‌شود و کلیدش فقط در شاخهٔ عادی هست.
	all := &Agg{NTraded: 1, ValHemat: 1.126}
	got := macroHealthFrom(&Agg{NTraded: 1, ValHemat: 12}, all, 69000000000000,
		"tse_market_overview", nil, nil)
	if got["trade_value_all_market_hemat"] != 1.13 {
		t.Fatalf("all-market trade value = %v, want 1.13",
			got["trade_value_all_market_hemat"])
	}
	if got["market_value_hemat"] != 6.9 ||
		got["market_value_source"] != "tse_market_overview" {
		t.Fatalf("market value = %v/%v, want 6.9/tse_market_overview",
			got["market_value_hemat"], got["market_value_source"])
	}
}

// TestMacroHealthPhaseGate: مرحلِ بی‌اجازه «بدون داده» با برچسبِ همان مرحل است،
// نه «نامساعد»؛ why فقط سه کلیدِ غیرِ order_pressure را به ترتیب دارد.
func TestMacroHealthPhaseGate(t *testing.T) {
	preOpen := marketphase.Resolve(strp("F"), strp("بسته"), i64p(20261028),
		nil, nil, nil, pinnedNow.Add(-2*time.Hour))
	if preOpen.Phase != marketphase.PreOpen {
		t.Fatalf("probe phase = %s, want pre_open", preOpen.Phase)
	}
	got := macroHealthFrom(&Agg{NTraded: 1, ValHemat: 100}, nil, 0, "",
		&preOpen, nil)
	if got["state"] != "nodata" || got["label"] != "پیش از آغازِ معاملات" {
		t.Fatalf("state/label = %v/%v, want nodata/پیش از آغازِ معاملات",
			got["state"], got["label"])
	}
	if got["label"] == "نامساعد" {
		t.Fatal("a disallowed phase must never be judged نامساعد")
	}
	if got["value_hemat"] != nil || got["excellent"] != false {
		t.Fatalf("value/excellent = %v/%v, want nil/false",
			got["value_hemat"], got["excellent"])
	}
	if got["phase"] != marketphase.PreOpen ||
		got["phase_source"] != "tsetmc_marketState" || got["phase_official"] != true {
		t.Fatalf("phase = %v/%v/%v", got["phase"], got["phase_source"],
			got["phase_official"])
	}
	if d, ok := i64At(t, got, "session_day"); !ok || d != 20261028 {
		t.Fatalf("session_day = %v/%v, want 20261028/true", d, ok)
	}
	why, ok := got["why"].([]string)
	if !ok || len(why) != 3 {
		t.Fatalf("why = %#v, want 3 strings", got["why"])
	}
	wantWhy := []string{
		"هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست",
		"جمعِ نشست کامل نشده، پس با آستانۀِ تمام‌روز سنجیده نمی‌شود",
		"قیمت پایانیِ نهایی هنوز ساخته نشده",
	}
	for i := range wantWhy {
		if why[i] != wantWhy[i] {
			t.Errorf("why[%d] = %q, want %q", i, why[i], wantWhy[i])
		}
	}
	if _, ok := got["cause"]; ok {
		t.Fatal("disallowed phase body must not carry cause")
	}

	// مرحلِ نامشخص هم بی‌اجازه است؛ برچسبش «مرحل نامشخص» است.
	unknown := marketphase.Resolve(nil, nil, i64p(20261014), nil, nil, nil, pinnedNow)
	got = macroHealthFrom(&Agg{NTraded: 1, ValHemat: 100}, nil, 0, "", &unknown, nil)
	if got["state"] != "nodata" || got["label"] != "مرحل نامشخص" {
		t.Fatalf("unknown phase = %v/%v, want nodata/مرحل نامشخص",
			got["state"], got["label"])
	}
}

// TestMacroHealthNoTrades: نشستِ بی‌معامله «بدون داده» است؛ cause «هنوز
// معامله‌ای نشده» فقط در نشستِ زنده است، و آخرین نشستِ گردش‌دار فقط وقتی
// db داده شود خوانده می‌شود.
func TestMacroHealthNoTrades(t *testing.T) {
	closed := marketphase.Resolve(strp("F"), strp("بسته"), i64p(20261014),
		nil, nil, nil, pinnedNow)
	h := openFixture(t)
	got := macroHealthFrom(nil, nil, 69000000000000, "tse_market_overview",
		&closed, h.Market)
	if got["state"] != "nodata" || got["label"] != "بدون داده" {
		t.Fatalf("state/label = %v/%v, want nodata/بدون داده",
			got["state"], got["label"])
	}
	if got["cause"] != "unknown" {
		t.Fatalf("cause = %v, want unknown (closed session)", got["cause"])
	}
	if d, ok := i64At(t, got, "last_traded_session"); !ok || d != 20261014 {
		t.Fatalf("last_traded_session = %v/%v, want 20261014/true", d, ok)
	}
	if got["last_value_hemat"] != 18.0 {
		t.Fatalf("last_value_hemat = %v, want 18.0", got["last_value_hemat"])
	}
	if got["market_value_hemat"] != 6.9 ||
		got["market_value_source"] != "tse_market_overview" {
		t.Fatalf("market value = %v/%v", got["market_value_hemat"],
			got["market_value_source"])
	}
	if got["trade_value_all_market_hemat"] != nil {
		t.Fatalf("all-market trade value = %v, want nil",
			got["trade_value_all_market_hemat"])
	}

	// نشستِ زنده: همان «بدون داده» ولی علتش «هنوز معامله‌ای نشده» است.
	live := marketphase.Resolve(nil, strp("باز"), i64p(20261028), nil, nil, nil,
		pinnedNow)
	got = macroHealthFrom(&Agg{}, nil, 0, "", &live, nil)
	if got["cause"] != "no_trades_yet" {
		t.Fatalf("live cause = %v, want no_trades_yet", got["cause"])
	}
	if got["last_traded_session"] != nil || got["last_value_hemat"] != nil {
		t.Fatalf("db=nil last session = %v/%v, want nil/nil",
			got["last_traded_session"], got["last_value_hemat"])
	}
	if got["phase"] != marketphase.Continuous {
		t.Fatalf("phase = %v, want continuous", got["phase"])
	}
	if d, ok := i64At(t, got, "session_day"); !ok || d != 20261028 {
		t.Fatalf("session_day = %v/%v, want 20261028/true", d, ok)
	}

	// بی‌مرحل: هر دو علت‌ها غایب‌اند و cause «unknown» است.
	got = macroHealthFrom(nil, nil, 0, "", nil, nil)
	if got["cause"] != "unknown" || got["phase"] != nil || got["session_day"] != nil {
		t.Fatalf("no-phase body = %v/%v/%v, want unknown/nil/nil",
			got["cause"], got["phase"], got["session_day"])
	}
}

// TestMacroHealthNormalKeepsPhase: شاخهٔ عادی شش کلیدِ مرحل را می‌دهد و live
// را از session_is_live اعلام می‌کند.
func TestMacroHealthNormalKeepsPhase(t *testing.T) {
	live := marketphase.Resolve(nil, strp("باز"), i64p(20261028), nil, nil, nil,
		pinnedNow)
	got := macroHealthFrom(&Agg{NTraded: 1, ValHemat: 25}, nil, 0, "", &live, nil)
	if got["state"] != "good" || got["session_is_live"] != true ||
		got["phase_label"] != "معاملات جاری" ||
		got["phase_source"] != "tsetmc_marketState" {
		t.Fatalf("normal live body = %v", got)
	}
	if got["trade_value_all_market_hemat"] != nil {
		t.Fatal("trade_value_all_market_hemat must be nil without an all-market Agg")
	}
}
