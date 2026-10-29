package tapeflags

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/store"
)

// frame قابِ سه‌ردیفیِ بریف است؛ فقط برایِ همان چهار ادعایِ بریف.
func frame(rows int) *store.Frame {
	fr := &store.Frame{Cols: map[string][]any{}}
	put := func(name string, vals ...any) { fr.Cols[name] = vals }
	zeros := func(n int) []any {
		out := make([]any, n)
		for i := range out {
			out[i] = 0.0
		}
		return out
	}
	put("symbol", "a", "b", "c")
	put("p_closing", 100.0, 100.0, 100.0)
	put("p_last", 102.0, 100.0, 100.0)
	put("z_tot_tran", 40.0, 5.0, 40.0)
	put("q_tot_tran", 110.0, 10.0, 10.0)
	put("month_avg_vol", 10.0, 10.0, 10.0)
	put("prev_day_vol", 10.0, 10.0, 10.0)
	put("hist_sessions", int64(60), int64(10), int64(60))
	put("prior30_vol", 300.0, 300.0, 300.0)
	put("min_low_29", 98.0, 98.0, 98.0)
	put("is6", 60.0, 60.0, 60.0)
	put("tmin", 100.0, 0.0, 0.0)
	put("buy_q1_cnt", 2.0, 0.0, 0.0)
	put("buy_q1_vol", 500.0, 0.0, 0.0)
	put("buy_i_vol", 60.0, 60.0, 60.0)
	put("sell_i_vol", 40.0, 40.0, 40.0)
	put("sell_n_vol", 60.0, 60.0, 60.0)
	put("buy_count_i", 2.0, 2.0, 2.0)
	put("sell_count_i", 2.0, 2.0, 2.0)
	put("p_closing_raw", zeros(rows)...)
	put("buyer_power_hint", zeros(rows)...)
	for _, k := range []string{"h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max", "h49_max", "h59_max"} {
		put(k, 90.0, 90.0, 90.0)
	}
	put("ctv_buy_i_val", nil, nil, nil)
	put("ctv_buy_n_val", nil, nil, nil)
	put("ctv_sell_i_val", nil, nil, nil)
	put("ctv_sell_n_val", nil, nil, nil)
	put("d_even", int64(20261014), int64(20261014), int64(20261013))
	put("min30_low", 90.0, 90.0, 90.0)
	put("mcap", 1.0, 1.0, 1.0)
	put("mcap_src", "mw", "mw", "mw")
	for i := range rows {
		fr.Codes = append(fr.Codes, "c"+string(rune('0'+i)))
	}
	return fr
}

func TestFlags(t *testing.T) {
	fr := frame(3)
	d := board.Derive(fr)
	f := Apply(fr, d)
	if !f.Clock[0] {
		t.Fatalf("row0 should be clock: vol_ratio=%v ztt=%v", f.VolRatioFile[0], f.VolRatio[0])
	}
	if f.Clock[1] || f.Susp[1] || f.Jet[1] || f.Smart[1] {
		t.Fatal("row1 has no measurable history; every volume filter must be false")
	}
	if f.Clock[2] {
		t.Fatal("row2 is not the live session; flags must be masked by is_live")
	}
	if got := f.VolRatioFile[0]; math.Abs(got-11.0) > 1e-9 {
		t.Fatalf("formula ratio = %v, want 11", got)
	}
	if !math.IsNaN(f.Resistance59[1]) {
		t.Fatal("short history must make the ladder unmeasured")
	}
}

// synthLadder هشت نقطۀ پلکان — مستقل از jetLadder نوشته شده تا اگر پیاده‌سازی
// نقطه‌ای را جا انداخت، تست هم‌دستِ همان اشتباه نشود.
var synthLadder = []string{"h2_max", "h5_max", "h9_max", "h19_max", "h29_max", "h39_max", "h49_max", "h59_max"}

// synthRow یک ردیفِ ساختگی؛ mut هر خانه را بازنویسی می‌کند. مقادیرِ هر ردیف
// عیناً درِ tape_flags.apply_tape_flags هم اجرا شد (با pandas 3.0.5) و ستونِ
// انتظار پایین از همان اجرا گرفته شده است.
type synthRow struct {
	pClosing, pLast, py   float64
	tvol, ztt             float64
	monthAvg, prevDayVol  float64
	hist, prior30, minLow float64
	is6, tmin             float64
	q1Cnt, q1Vol          float64
	buyIVol, sellIVol     float64
	sellNVol              float64
	buyCnt, sellCnt       float64
	hMax, h59             float64
	dEven                 int64
}

// synthFrame پنجاه‌ودو ردیفِ لبه است: هر فیلتر یک ردیفِ مثبت دارد، هر دروازه
// (سابقۀ کوتاه، فسیل، سقف، is6 غایب، کفِ صفر، صفِ غایب) یک ردیفِ منفی، و هر
// آستانهٔ عددی یک جفتِ «یک پله زیر/بالا» تا تغییرِ موییِ ثابت‌ها هم دیده شود.
func synthFrame() *store.Frame {
	base := synthRow{
		pClosing: 1000, pLast: 1100, py: 900,
		tvol: 1000, ztt: 150,
		monthAvg: 100, prevDayVol: 10,
		hist: 60, prior30: 3000, minLow: 980,
		is6: 100, tmin: 900,
		q1Cnt: 1, q1Vol: 10,
		buyIVol: 600, sellIVol: 400, sellNVol: 600,
		buyCnt: 6, sellCnt: 8,
		hMax: 900, h59: 900, dEven: 20261014,
	}
	rows := []struct {
		symbol string
		mut    func(r *synthRow)
	}{
		{"all", nil},
		// کف‌روبی: pl == tmin، درصدِ آخرین منفی، صفِ خریدِ سطرِ اول.
		{"roobi", func(r *synthRow) {
			r.pLast, r.py, r.tvol, r.ztt = 1000, 1100, 100, 10
			r.tmin, r.q1Cnt, r.q1Vol = 1000, 2, 150
		}},
		// سابقۀ کوتاه: هیچ پنجرۀ سی‌نشستی بسته نمی‌شود.
		{"short", func(r *synthRow) { r.hist, r.prior30, r.is6 = 10, 300, 10 }},
		// فسیل: تنها تفاوتش d_even است؛ پرچم‌ها باید خاموش شوند.
		{"fossil", func(r *synthRow) { r.dEven = 20261013 }},
		// سقفِ پلکان هم‌ترازِ pl: قیدِ pl > res رد می‌شود.
		{"cap", func(r *synthRow) { r.pLast, r.hMax, r.h59 = 1050, 1050, 1050 }},
		// is6 غایب: پولِ هوشمند و کدبه‌کد «نسنج»‌اند، جت بی‌تأثیر است.
		{"nois6", func(r *synthRow) { r.is6 = math.NaN() }},
		// pl == pc: سقفِ پلکان جت را رد می‌کند ولی ساعت/سوسپ/نقطه/هوشمند می‌مانند.
		{"pllow", func(r *synthRow) { r.pLast, r.hMax, r.h59 = 1000, 1200, 1200 }},
		// min_low_29 صفر: نشستِ بی‌معامله در پنجره، نقطه‌زنی را رد می‌کند.
		{"lowzero", func(r *synthRow) { r.pLast, r.minLow = 1050, 0 }},
		// سهمِ حقیقیِ فروش کم: پولِ هوشمند هست، کدبه‌کد نیست.
		{"legalno", func(r *synthRow) { r.pLast, r.sellNVol = 1050, 400 }},
		// صفِ خریدِ سطرِ اول غایب: کف‌روبی نمی‌سنجد.
		{"q1nil", func(r *synthRow) {
			r.pLast, r.py, r.tvol, r.ztt = 1000, 1100, 100, 10
			r.tmin, r.q1Cnt, r.q1Vol = 1000, math.NaN(), 150
		}},
		// ── جفت‌هایِ آستانه: یک پله زیر و بالایِ هر ثابت ───────────────────
		// حجمِ مشکوک ۳×: ۲٫۹۹ باید رد و ۳٫۰۱ باید بگیرد.
		{"suspBelow", func(r *synthRow) { r.tvol = 299 }},
		{"suspAbove", func(r *synthRow) { r.tvol = 301 }},
		// قدرتِ خریدارِ جت ۱٫۵× و کفِ پولِ هوشمند ۱٫۰ (>=).
		{"bpBelow", func(r *synthRow) { r.buyIVol, r.buyCnt, r.sellIVol, r.sellCnt = 149, 1, 100, 1 }},
		{"bpAbove", func(r *synthRow) { r.buyIVol, r.buyCnt, r.sellIVol, r.sellCnt = 151, 1, 100, 1 }},
		{"bpSmartEdge", func(r *synthRow) { r.buyIVol, r.buyCnt, r.sellIVol, r.sellCnt = 100, 1, 100, 1 }},
		// دلتای الگویِ ساعت ۲٪: ۱۰۱۹ رد، ۱۰۲۰ قبول.
		{"clockBelow", func(r *synthRow) { r.pLast = 1019 }},
		{"clockEdge", func(r *synthRow) { r.pLast = 1020 }},
		// مبنایِ هوشمند ۱٫۵×[is6]: ۱۴۹ رد، ۱۵۱ قبول.
		{"smartBelow", func(r *synthRow) { r.tvol = 149 }},
		{"smartAbove", func(r *synthRow) { r.tvol = 151 }},
		// تعدادِ جت > ۱۰۰.
		{"zttJetEdge", func(r *synthRow) { r.ztt = 100 }},
		{"zttJetAbove", func(r *synthRow) { r.ztt = 101 }},
		// سهمِ حقوقی ۰٫۵×حجم: ۴۹۹ رد، ۵۰۱ قبول.
		{"shareBelow", func(r *synthRow) { r.buyIVol = 499 }},
		{"shareAbove", func(r *synthRow) { r.buyIVol = 501 }},
		// کف‌روبی: درصدِ آخرین ۱٫۴۸- می‌گیرد، ۰٫۹۹- نه.
		{"roobiEdge", func(r *synthRow) {
			r.pLast, r.py, r.tmin, r.q1Cnt, r.q1Vol = 1000, 1015, 1000, 2, 150
		}},
		{"roobiNearMiss", func(r *synthRow) {
			r.pLast, r.py, r.tmin, r.q1Cnt, r.q1Vol = 1000, 1010, 1000, 2, 150
		}},
		// فاصلۀ نقطه‌زنی ۳٪: ۲٫۹ قبول، ۳٫۱ رد.
		{"distBelow", func(r *synthRow) { r.minLow = 971 }},
		{"distAbove", func(r *synthRow) { r.minLow = 969 }},
		// تعدادِ مشکوک > ۵۰ و نقطه‌زنی > ۵.
		{"zttSuspEdge", func(r *synthRow) { r.ztt = 50 }},
		{"zttSuspAbove", func(r *synthRow) { r.ztt = 51 }},
		{"zttNoqtehEdge", func(r *synthRow) { r.ztt = 5 }},
		{"zttNoqtehAbove", func(r *synthRow) { r.ztt = 6 }},
		// تعدادِ ساعت > ۳۰.
		{"zttClockEdge", func(r *synthRow) { r.ztt = 30 }},
		{"zttClockAbove", func(r *synthRow) { r.ztt = 31 }},
		// سابقۀ ۲۹ نشست نسنج است؛ ۳۰، ۳۵ و ۵۹ حجم را می‌سنجند ولی پلکانِ ۶۰ را نه.
		{"hist29", func(r *synthRow) { r.hist = 29 }},
		{"hist30", func(r *synthRow) { r.hist = 30 }},
		{"hist35", func(r *synthRow) { r.hist = 35 }},
		{"hist59", func(r *synthRow) { r.hist = 59 }},
		// نقطهٔ پنجاه‌ونهمِ پلکان تنها سقفِ بالاست: pl زیرِ آن می‌مانَد.
		{"ladder59", func(r *synthRow) { r.h59 = 1150 }},
		// تساوی‌هایِ مرزی: pl == pc باید بگیرد (>=)، درصدِ دقیقاً ۱ و صفِ دقیقاً
		// آستانه و سهمِ دقیقاً نصف باید رد شوند (>) یا بگیرند (>=).
		{"plEqPc", func(r *synthRow) { r.pLast = 1000 }},
		{"vrfOne", func(r *synthRow) { r.tvol = 100 }},
		{"q1cEdge", func(r *synthRow) {
			r.pLast, r.py, r.tvol, r.ztt = 1000, 1100, 100, 10
			r.tmin, r.q1Cnt, r.q1Vol = 1000, 1, 150
		}},
		{"q1vEdge", func(r *synthRow) {
			r.pLast, r.py, r.tvol, r.ztt = 1000, 1100, 100, 10
			r.tmin, r.q1Cnt, r.q1Vol = 1000, 2, 100
		}},
		{"shareEdge", func(r *synthRow) { r.buyIVol = 500 }},
		{"sellEdge", func(r *synthRow) { r.sellNVol = 500 }},
		{"bpEq", func(r *synthRow) { r.buyIVol, r.buyCnt, r.sellIVol, r.sellCnt = 150, 1, 100, 1 }},
		{"roobiPlpEdge", func(r *synthRow) {
			r.pLast, r.py, r.tmin, r.tvol, r.ztt, r.q1Cnt, r.q1Vol = 990, 1000, 990, 100, 10, 2, 150
		}},
		// فاصلهٔ دقیقاً ۳٪: گردکردن پیش از مقایسه، پس ۳٫۰ رد می‌شود.
		{"distEdge", func(r *synthRow) { r.minLow = 970 }},
		// ۲٫۹۹۹ پیش از مقایسه به ۳٫۰ گرد می‌شود و همچنان رد است (round2 اول).
		{"distRound", func(r *synthRow) { r.minLow = 970.01 }},
		// نسبتِ حجم دقیقاً ۳٫۰ و ۱٫۵ و مبنایِ صفرِ صادق.
		{"vrfEqThree", func(r *synthRow) { r.tvol = 300 }},
		{"smartEdge", func(r *synthRow) { r.tvol = 150 }},
		{"baseZero", func(r *synthRow) { r.prior30 = 0 }},
		{"monthZero", func(r *synthRow) { r.monthAvg = 0 }},
	}
	fr := &store.Frame{Cols: map[string][]any{}}
	for _, row := range rows {
		r := base
		if row.mut != nil {
			row.mut(&r)
		}
		fr.Codes = append(fr.Codes, row.symbol)
		put := func(name string, v float64) {
			fr.Cols[name] = append(fr.Cols[name], v)
		}
		put("p_closing", r.pClosing)
		put("p_last", r.pLast)
		put("price_yesterday", r.py)
		put("q_tot_tran", r.tvol)
		put("z_tot_tran", r.ztt)
		put("month_avg_vol", r.monthAvg)
		put("prev_day_vol", r.prevDayVol)
		put("hist_sessions", r.hist)
		put("prior30_vol", r.prior30)
		put("min_low_29", r.minLow)
		put("is6", r.is6)
		put("tmin", r.tmin)
		put("buy_q1_cnt", r.q1Cnt)
		put("buy_q1_vol", r.q1Vol)
		put("buy_i_vol", r.buyIVol)
		put("sell_i_vol", r.sellIVol)
		put("sell_n_vol", r.sellNVol)
		put("buy_count_i", r.buyCnt)
		put("sell_count_i", r.sellCnt)
		for _, name := range synthLadder {
			if name == "h59_max" {
				put(name, r.h59)
				continue
			}
			put(name, r.hMax)
		}
		fr.Cols["d_even"] = append(fr.Cols["d_even"], r.dEven)
	}
	return fr
}

// bits پرچم‌ها را به ترتیبِ Clock/Susp/Jet/Roobi/Noqteh/Smart/Legal می‌نویسد.
func bits(v ...bool) string {
	var b strings.Builder
	for _, x := range v {
		if x {
			b.WriteByte('1')
		} else {
			b.WriteByte('0')
		}
	}
	return b.String()
}

func synthIndex(fr *store.Frame) map[string]int {
	idx := make(map[string]int, fr.N())
	for i, code := range fr.Codes {
		idx[code] = i
	}
	return idx
}

// TestSyntheticAllSeven هر هفت فیلتر را هم مثبت و هم منفی می‌سنجد. ستونِ
// انتظار از اجرایِ خودِ tape_flags.apply_tape_flags رویِ همین اعداد آمده است،
// نه از حسابِ دستی.
func TestSyntheticAllSeven(t *testing.T) {
	fr := synthFrame()
	f := Apply(fr, board.Derive(fr))
	want := map[string]string{
		"all":            "1110111",
		"roobi":          "0001000",
		"short":          "0000000",
		"fossil":         "0000000",
		"cap":            "1100111",
		"nois6":          "1110100",
		"pllow":          "0100111",
		"lowzero":        "1110011",
		"legalno":        "1110110",
		"q1nil":          "0000000",
		"suspBelow":      "1000111",
		"suspAbove":      "1110111",
		"bpBelow":        "1100110",
		"bpAbove":        "1110110",
		"bpSmartEdge":    "1100110",
		"clockBelow":     "0110111",
		"clockEdge":      "1110111",
		"smartBelow":     "1000100",
		"smartAbove":     "1000111",
		"zttJetEdge":     "1100111",
		"zttJetAbove":    "1110111",
		"shareBelow":     "1110110",
		"shareAbove":     "1110111",
		"roobiEdge":      "0101100",
		"roobiNearMiss":  "0100100",
		"distBelow":      "1110111",
		"distAbove":      "1110011",
		"zttSuspEdge":    "1000111",
		"zttSuspAbove":   "1100111",
		"zttNoqtehEdge":  "0000011",
		"zttNoqtehAbove": "0000111",
		"zttClockEdge":   "0000111",
		"zttClockAbove":  "1000111",
		"hist29":         "0000000",
		"hist30":         "1100111",
		"hist35":         "1100111",
		"hist59":         "1100111",
		"ladder59":       "1100111",
		"plEqPc":         "0110111",
		"vrfOne":         "0000000",
		"q1cEdge":        "0000000",
		"q1vEdge":        "0000000",
		"shareEdge":      "1110110",
		"sellEdge":       "1110110",
		"bpEq":           "1110110",
		"roobiPlpEdge":   "0000000",
		"distEdge":       "1110011",
		"distRound":      "1110011",
		"vrfEqThree":     "1000111",
		"smartEdge":      "1000100",
		"baseZero":       "0000011",
		"monthZero":      "1110111",
	}
	for i, code := range fr.Codes {
		got := bits(f.Clock[i], f.Susp[i], f.Jet[i], f.Roobi[i], f.Noqteh[i], f.Smart[i], f.Legal[i])
		if got != want[code] {
			t.Errorf("%s: flags = %s, want %s", code, got, want[code])
		}
	}
	if len(want) != fr.N() {
		t.Fatalf("جدولِ انتظار %d ردیف دارد ولی قاب %d ردیف", len(want), fr.N())
	}
	idx := synthIndex(fr)
	if got := f.VolRatioFile[idx["all"]]; math.Abs(got-10.0) > 1e-9 {
		t.Fatalf("all: vol_ratio_file = %v, want 10", got)
	}
	if got := f.VolRatio[idx["all"]]; math.Abs(got-10.0) > 1e-9 {
		t.Fatalf("all: vol_ratio = %v, want 10", got)
	}
	if got := f.BuyerPowerRaw[idx["all"]]; math.Abs(got-2.0) > 1e-9 {
		t.Fatalf("all: buyer_power_raw = %v, want 2", got)
	}
	if got := f.Resistance59[idx["all"]]; math.Abs(got-900.0) > 1e-9 {
		t.Fatalf("all: resistance_59 = %v, want 900", got)
	}
	// نسبت‌هایِ نمایشی تاریخ‌محورند: ردیفِ کم‌سابقه هم نسبتِ ماه را دارد، ولی
	// مبنایِ فایل (و پلکان) برایش سنجیده نمی‌شود.
	if got := f.VolRatio[idx["short"]]; math.Abs(got-10.0) > 1e-9 {
		t.Fatalf("short: vol_ratio = %v, want 10", got)
	}
	if !math.IsNaN(f.VolRatioFile[idx["short"]]) {
		t.Fatalf("short: vol_ratio_file = %v, want NaN", f.VolRatioFile[idx["short"]])
	}
	if !math.IsNaN(f.Resistance59[idx["short"]]) {
		t.Fatalf("short: resistance_59 = %v, want NaN", f.Resistance59[idx["short"]])
	}
	// میانگینِ ماهِ صفر مبنایِ نمایش را نمی‌سازد: نسبتِ ماه NaN است، نه +Inf.
	if !math.IsNaN(f.VolRatio[idx["monthZero"]]) {
		t.Fatalf("monthZero: vol_ratio = %v, want NaN", f.VolRatio[idx["monthZero"]])
	}
	// prior30_vol صفر مبنایِ فایل را نمی‌سازد؛ اگر صفر در مخرج می‌ماند،
	// +Inf هر پنج دروازهٔ حجمی را باز می‌کرد.
	if !math.IsNaN(f.VolRatioFile[idx["baseZero"]]) {
		t.Fatalf("baseZero: vol_ratio_file = %v, want NaN", f.VolRatioFile[idx["baseZero"]])
	}
}

// TestMissingColumnsAreUnmeasured قراردادِ col/numAt را قفل می‌کند: ستونِ غایب
// «نسنج» است، هرگز «صفر» و هرگز «درست». ردیفِ all بی این ستون‌ها همه‌چیزش
// روشن بود؛ نبودشان باید هر هفت پرچم را خاموش کند و هیچ پنیکی نسازد.
func TestMissingColumnsAreUnmeasured(t *testing.T) {
	fr := synthFrame()
	for _, name := range []string{
		"hist_sessions", "prior30_vol", "is6", "tmin", "buy_q1_cnt",
		"buy_q1_vol", "min_low_29", "buy_count_i", "sell_count_i",
	} {
		delete(fr.Cols, name)
	}
	for _, name := range synthLadder {
		delete(fr.Cols, name)
	}
	f := Apply(fr, board.Derive(fr))
	for i, code := range fr.Codes {
		if got := bits(f.Clock[i], f.Susp[i], f.Jet[i], f.Roobi[i], f.Noqteh[i], f.Smart[i], f.Legal[i]); got != "0000000" {
			t.Fatalf("%s: flags = %s, want 0000000 when the columns are missing", code, got)
		}
		if !math.IsNaN(f.Resistance59[i]) || !math.IsNaN(f.BuyerPowerRaw[i]) || !math.IsNaN(f.VolRatioFile[i]) {
			t.Fatalf("%s: missing columns must stay unmeasured (res=%v bp=%v vrf=%v)",
				code, f.Resistance59[i], f.BuyerPowerRaw[i], f.VolRatioFile[i])
		}
	}
}

// goldenRow فقط کلیدهایی را می‌خواند که اوراکل دارد؛ عددهایِ غایب (null) هم
// همین‌جا با *float64 نیل شناخته می‌شوند.
type goldenRow struct {
	Symbol       string   `json:"symbol"`
	FClock       bool     `json:"f_clock"`
	FSusp        bool     `json:"f_susp"`
	FJet         bool     `json:"f_jet"`
	FRoobi       bool     `json:"f_roobi"`
	FNoqteh      bool     `json:"f_noqteh"`
	FSmart       bool     `json:"f_smart"`
	FLegal       bool     `json:"f_legal"`
	IsLive       bool     `json:"is_live"`
	VolRatio     *float64 `json:"vol_ratio"`
	VolRatioFile *float64 `json:"vol_ratio_file"`
	Resistance59 *float64 `json:"resistance_59"`
}

type goldenFile struct {
	Count     int         `json:"count"`
	LiveCount int         `json:"live_count"`
	Data      []goldenRow `json:"data"`
}

// readGolden از پوشۀ گلدنِ internal/board می‌خواند؛ هیچ نوشتنی در مخزن نیست.
func readGolden(t *testing.T, name string) goldenFile {
	t.Helper()
	path, err := filepath.Abs(filepath.Join("..", "board", "testdata", "golden", name))
	if err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(b, &g); err != nil {
		t.Fatalf("%s: %v", name, err)
	}
	return g
}

// fixtureFrame فیکسچرِ مخزن را در t.TempDir() کپی می‌کند و با همان
// store.LoadBoard می‌خواند که مسیرِ تولیدی می‌خواند. بانکِ عملیاتیِ کاربر هرگز
// باز نمی‌شود.
func fixtureFrame(t *testing.T) *store.Frame {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
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

// checkNum گلدن را با خروجی می‌سنجد؛ null در گلدن یعنی NaN در Go.
func checkNum(bad *[]string, label string, got float64, want *float64) {
	if want == nil {
		if !math.IsNaN(got) {
			*bad = append(*bad, fmt.Sprintf("%s = %v، گلدن null دارد", label, got))
		}
		return
	}
	if math.IsNaN(got) || math.Abs(got-*want) > 1e-9 {
		*bad = append(*bad, fmt.Sprintf("%s = %v، گلدن %v می‌گوید", label, got, *want))
	}
}

// TestFixtureFlagsGolden پورت را رویِ همان سی ردیفِ فیکسچر می‌سنجد که اوراکلِ
// طلایی از آن ساخته شده است: هر هفت پرچم برایِ هر سی ردیف از market.json
// (خروجیِ drop_unused=True)، و نسبت‌ها/پلکان از market_all.json (drop_unused=False)
// که تنها اوراکلی است که resistance_59 را نگه می‌دارد.
//
// vol_ratio در market.json یک رقمِ اعشار است چون api/market.py پیش از
// سریال‌سازی یک بارِ دیگر round(1) می‌زند؛ پس همین گردکردنِ نمایشی هم اینجا
// بازپخش می‌شود. gap‌ها همه یک‌جا گزارش می‌شوند، نه اولی‌شان.
func TestFixtureFlagsGolden(t *testing.T) {
	fr := fixtureFrame(t)
	d := board.Derive(fr)
	f := Apply(fr, d)

	market := readGolden(t, "market.json")
	all := readGolden(t, "market_all.json")
	if market.Count != 30 || fr.N() != 30 || len(market.Data) != 30 {
		t.Fatalf("rows: frame=%d، گلدن count=%d، گلدن data=%d — هر سه باید ۳۰ باشند",
			fr.N(), market.Count, len(market.Data))
	}
	if len(all.Data) != len(market.Data) {
		t.Fatalf("market_all rows = %d، market rows = %d", len(all.Data), len(market.Data))
	}

	idx := make(map[string]int, fr.N())
	for i := 0; i < fr.N(); i++ {
		if s, ok := fr.Cols["symbol"][i].(string); ok {
			idx[s] = i
		}
	}
	var bad []string
	live := 0
	for _, g := range market.Data {
		i, ok := idx[g.Symbol]
		if !ok {
			t.Fatalf("نمادِ %q در قاب نیست", g.Symbol)
		}
		if g.IsLive {
			live++
		}
		got := bits(f.Clock[i], f.Susp[i], f.Jet[i], f.Roobi[i], f.Noqteh[i], f.Smart[i], f.Legal[i])
		want := bits(g.FClock, g.FSusp, g.FJet, g.FRoobi, g.FNoqteh, g.FSmart, g.FLegal)
		if got != want {
			bad = append(bad, fmt.Sprintf("%s: پرچم‌ها %s، گلدن %s (vrf=%v res=%v live=%v)",
				g.Symbol, got, want, f.VolRatioFile[i], f.Resistance59[i], d.IsLive[i]))
		}
		checkNum(&bad, g.Symbol+".vol_ratio", board.Round1(f.VolRatio[i]), g.VolRatio)
		checkNum(&bad, g.Symbol+".vol_ratio_file", f.VolRatioFile[i], g.VolRatioFile)
	}
	if live != market.LiveCount {
		t.Fatalf("is_live rows = %d، گلدن %d", live, market.LiveCount)
	}
	for _, g := range all.Data {
		i, ok := idx[g.Symbol]
		if !ok {
			t.Fatalf("نمادِ %q در market_all هست ولی در قاب نیست", g.Symbol)
		}
		checkNum(&bad, g.Symbol+".resistance_59", f.Resistance59[i], g.Resistance59)
	}
	if len(bad) > 0 {
		t.Fatalf("اختلاف با گلدن (%d مورد):\n%s", len(bad), strings.Join(bad, "\n"))
	}
}
