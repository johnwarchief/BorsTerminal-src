// Package tapeflags هفت فیلترِ تابلو است — پورتِ یک‌به‌یکِ tape_flags.py.
//
// هر آستانه عیناً از همان فایل آمده و هر عبارتِ بولی همان عبارتِ
// apply_tape_flags است. پرچم‌ها بر «همین نشست» شرط دارند (is_live)؛ نسبت‌هایِ
// کمکی (vol_ratio/vol_ratio_file/buyer_power_raw/resistance_59) نه — آن‌ها
// تاریخ‌محورند و برایِ ردیفِ فسیل هم حساب می‌مانند.
//
// NaN یعنی «سنجیده نشد»: نمادِ کم‌سابقه یا ستونِ غایب هرگز با صفرِ جعلی پر
// نمی‌شود و هر قیدِ NaN در مقایسه‌هایِ Go (و numpy) خودبه‌خود False می‌دهد.
package tapeflags

import (
	"math"
	"strconv"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/store"
)

const (
	// Σ[ih][0..29] بر سی نشستِ آخر می‌گردد و همان ۳۰ِ ثابت مخرج است؛ بانکِ ما
	// نشستِ بی‌معامله را نمی‌نویسد، پس پنجره با شمارۀِ نشست بسته می‌شود نه با
	// شمارۀِ ردیف. کمبود = «نسنج»، هرگز «بر تعدادِ موجود تقسیم کن».
	volBaseSessions = 30
	// HIST_MIN_SESSIONS در فایلِ پایتون تعریف شده ولی خوانده نمی‌شود (دروازه‌ها
	// همان volBaseSessions را می‌خواهند)؛ فقط برایِ تطابقِ نام‌ها نگه داشته شد.
	histMinSessions = 30
	// کمینهٔ نقطه‌زنی: [ih][0..28].PriceMin — بیست‌ونُه نشست. نشستِ بی‌معامله
	// PriceMin=0 دارد و فایل «MinPriceOfMonth() != 0» را صریح می‌خواهد.
	lowBaseSessions = 29
	// پلکانِ مقاومت تا [ih][59] است (بیشترینِ JET_LADDER). کمتر از شصت نشست یعنی
	// [ih][59] وجود ندارد و ExecFilter ردیف را بیرون می‌اندازد (NaN، نه کمینهٔ
	// نقاطِ موجود).
	resistanceSessions = 60

	// ضریب‌هایِ حجمیِ فایل.
	jetVolMult  = 3.0
	suspVolMult = 3.0
	// قدرتِ خریدار: سرانۀِ خریدِ حقیقی ÷ سرانۀِ فروشِ حقیقی.
	jetBuyerPower = 1.5
	// دلتای الگویِ ساعت: pl >= pc*1.02.
	clockDelta = 0.02
	// سقفِ فاصلۀِ نقطه‌زنی: round2((pc-min)/pc*100) < 3، بدونِ کرانِ پایین.
	noqtehMaxDist = 3.0
	// کف‌روبی: pl == tmin، درصدِ آخرین زیرِ منفیِ یک، و صفِ خریدِ سطرِ اول.
	roobiMaxChange = -1.0
	roobiZd1Min    = 1.0
	roobiQd1Min    = 100.0
	// آستانه‌هایِ تعدادِ معاملهٔ فایل.
	clockTrades  = 30.0
	suspTrades   = 50.0
	noqtehTrades = 5.0
	// jetTrades (tno > 1) با jetMinTrades (tno > 100) پوشیده شده است: هر ردیفی
	// که دومی را رد کند، اولی را هم رد می‌کند. پس این ثابت هیچ رفتاری را عوض
	// نمی‌کند و از بیرون قابلِ مشاهده نیست؛ فقط برایِ تطابقِ نام با فایلِ
	// پایتون نگه داشته شد، نه به‌عنوانِ آستانه‌ای زنده.
	jetTrades    = 1.0
	jetMinTrades = 100.0
	// ورودِ پولِ هوشمند: tvol > 1.5*[is6] و سرانۀِ خرید >= سرانۀِ فروش.
	smartVolMult = 1.5
	smartBPGe    = 1.0
	// کد به کدِ حقوقی به حقیقی: سهمِ هر دو سمت از حجمِ نشست.
	legalShareTvol = 0.5
)

// JetLadder نقاطِ پلکانِ مقاومت است: [ih][2] تا [ih][59]، هشت نقطه، عینِ
// JET_LADDER. ستونِ h{k}_max همان [ih][k].PriceMax است.
var JetLadder = []int{2, 5, 9, 19, 29, 39, 49, 59}

// Flags خروجیِ Apply است؛ هم‌طول و هم‌ترتیبِ قاب. NaN یعنی «سنجیده نشد» و
// هر پرچم پیشاپیش با is_live و AND شده است.
type Flags struct {
	VolRatio, VolRatioFile, BuyerPowerRaw, Resistance59 []float64
	Clock, Susp, Jet, Roobi, Noqteh, Smart, Legal       []bool
}

// col ستونِ اختیاری؛ نبودنش nil است و numAt آن را NaN می‌خواند.
func col(fr *store.Frame, name string) []any { return fr.Cols[name] }

// numAt خانهٔ i را عدد می‌کند؛ ستونِ غایب یا کوتاه ⇒ NaN (هرگز صفرِ جعلی).
func numAt(v []any, i int) float64 {
	if v == nil || i < 0 || i >= len(v) {
		return math.NaN()
	}
	return board.Num(v[i])
}

// nums ستون را به‌اندازۀِ کلِ قاب عدد می‌کند؛ ستونِ غایب همه‌اش NaN می‌شود.
// (برخلافِ شمارشِ طولِ خودِ ستون، اینجا نبودِ ستون به ایندکسِ بیرون از بازه
// نمی‌رسد و هیچ فیلتری روشن نمی‌شود.)
func nums(fr *store.Frame, name string) []float64 {
	raw := col(fr, name)
	out := make([]float64, fr.N())
	for i := range out {
		out[i] = numAt(raw, i)
	}
	return out
}

// volumeBase میانگینِ نمایشیِ ماه؛ صفرِ جعلی نمی‌سازد.
func volumeBase(fr *store.Frame) []float64 {
	out := make([]float64, fr.N())
	for i := range out {
		v := numAt(col(fr, "month_avg_vol"), i)
		if v > 0 {
			out[i] = v
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

// formulaVolumeBase مبنایِ حجمِ فایل: Σ[ih][0..29] ÷ ۳۰، فقط با سی نشستِ کامل.
// نشستِ بی‌معامله در ∑ صفر است، پس نبودنِ ردیفش همان صفرِ سایت است.
func formulaVolumeBase(fr *store.Frame) []float64 {
	n := fr.N()
	out := make([]float64, n)
	prior := col(fr, "prior30_vol")
	hist := col(fr, "hist_sessions")
	for i := 0; i < n; i++ {
		base := numAt(prior, i) / volBaseSessions
		h := numAt(hist, i)
		if base > 0 && !math.IsNaN(h) && h >= volBaseSessions {
			out[i] = base
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

// ratio حجمِ همین نشست ÷ مبناء؛ مبنایِ NaN همان نسبتِ NaN را می‌دهد.
func ratio(fr *store.Frame, d *board.Derived, base []float64) []float64 {
	out := make([]float64, fr.N())
	for i := range out {
		out[i] = d.Tvol[i] / base[i]
	}
	return out
}

// resistanceLadder بیشترینِ سقفِ [ih][2..59]، فقط با شصت نشستِ کامل.
// NaN عینِ fillna(0) است: نشستِ بی‌معامله سقف را بالا نمی‌برد، ولی خودِ
// کم‌سابقگی سنجش را ناممکن می‌کند (فایل [ih][59] را صریح می‌خواهد).
func resistanceLadder(fr *store.Frame) []float64 {
	n := fr.N()
	out := make([]float64, n)
	hist := col(fr, "hist_sessions")
	for i := 0; i < n; i++ {
		best := 0.0
		for _, k := range JetLadder {
			name := "h" + strconv.Itoa(k) + "_max"
			v := numAt(col(fr, name), i)
			if !math.IsNaN(v) && v > best {
				best = v
			}
		}
		h := numAt(hist, i)
		if !math.IsNaN(h) && h >= resistanceSessions {
			out[i] = best
		} else {
			out[i] = math.NaN()
		}
	}
	return out
}

// bpRaw قدرتِ خریدارِ حقیقی نسبت به فروشندهٔ حقیقی (سرانۀِ حجم به تعداد) —
// بی‌سقف و بی‌گردکردن، چون قیدِ فایل رویِ همین عدد است. صفر/صفر در هیچ سمتی
// «قدرتِ برابر» نیست، NaN است.
func bpRaw(fr *store.Frame, i int) float64 {
	bc := numAt(col(fr, "buy_count_i"), i)
	sc := numAt(col(fr, "sell_count_i"), i)
	if !(bc > 0) || !(sc > 0) {
		return math.NaN()
	}
	buy := numAt(col(fr, "buy_i_vol"), i) / bc
	sell := numAt(col(fr, "sell_i_vol"), i) / sc
	return buy / sell
}

// Apply هفت پرچم و چهار ستونِ کمکی را می‌سازد؛ ورودی را دست نمی‌زند.
func Apply(fr *store.Frame, d *board.Derived) *Flags {
	n := fr.N()
	f := &Flags{
		VolRatio:      make([]float64, n),
		VolRatioFile:  make([]float64, n),
		BuyerPowerRaw: make([]float64, n),
		Resistance59:  resistanceLadder(fr),
		Clock:         make([]bool, n),
		Susp:          make([]bool, n),
		Jet:           make([]bool, n),
		Roobi:         make([]bool, n),
		Noqteh:        make([]bool, n),
		Smart:         make([]bool, n),
		Legal:         make([]bool, n),
	}
	vr := ratio(fr, d, volumeBase(fr))
	vrf := ratio(fr, d, formulaVolumeBase(fr))
	for i := 0; i < n; i++ {
		// گردکردنِ apply_tape_flags: دو رقم اعشار. api/market.py رویِ همین
		// vol_ratio یک بارِ دیگر round(1) می‌زند (فقط نمایش).
		f.VolRatio[i] = board.Round2(vr[i])
		f.VolRatioFile[i] = board.Round2(vrf[i])
		f.BuyerPowerRaw[i] = bpRaw(fr, i)
	}
	pc := nums(fr, "p_closing")
	pl := nums(fr, "p_last")
	ztt := nums(fr, "z_tot_tran")
	tmin := nums(fr, "tmin")
	q1c := nums(fr, "buy_q1_cnt")
	q1v := nums(fr, "buy_q1_vol")
	is6 := nums(fr, "is6")
	bi := nums(fr, "buy_i_vol")
	sn := nums(fr, "sell_n_vol")
	hist := nums(fr, "hist_sessions")
	prior := nums(fr, "prior30_vol")
	minLow := nums(fr, "min_low_29")
	for i := 0; i < n; i++ {
		alive := d.IsLive[i]
		plp := d.PlpRaw[i]
		bp := f.BuyerPowerRaw[i]
		// A) الگویِ ساعت: pl >= pc*1.02 و حجمِ ۱×مبناء و tno > 30.
		f.Clock[i] = alive && pc[i] > 0 && pl[i] >= pc[i]*(1.0+clockDelta) &&
			vrf[i] > 1.0 && ztt[i] > clockTrades
		// B) حجمِ مشکوک: tvol > 3×مبناء و tno > 50.
		f.Susp[i] = alive && vrf[i] > suspVolMult && ztt[i] > suspTrades
		// C) جت: حجمِ ۳× و قدرتِ خریدارِ ۱٫۵× و pl>=pc و plp>0 و
		//    پلکانِ هشت‌نقطه‌ای < pl و tno > 100. پلکانِ تمام‌صفر رد نمی‌شود
		//    (سایت هم رد نمی‌کند)؛ چیزی که سنجش را می‌بندد کم‌سابقگی است، و
		//    همان با NaNِ Resistance59 از درِ پایین رد می‌شود.
		f.Jet[i] = alive && vrf[i] > jetVolMult && bp >= jetBuyerPower &&
			pc[i] > 0 && pl[i] >= pc[i] && plp > 0 &&
			ztt[i] > jetTrades && ztt[i] > jetMinTrades &&
			pl[i] > f.Resistance59[i]
		// D) کف‌روبی: آخرین معامله رویِ آستانۀِ مجازِ پایین چسبیده، بیش از یک
		//    درصد پایین، و صفِ خریدِ سطرِ اول دو سفارش با بیش از ۱۰۰ سهم.
		f.Roobi[i] = alive && pl[i] > 0 && tmin[i] > 0 && pl[i] == tmin[i] &&
			q1c[i] > roobiZd1Min && plp < roobiMaxChange && q1v[i] > roobiQd1Min
		// E) نقطه‌زنی: فاصله از کمینۀِ [ih][0..28] زیرِ ۳٪ (بدونِ کرانِ پایین —
		//    کف‌شکن خودِ قوی‌ترینِ مصداقِ «نزدیکِ کف» است). صفرِ min_low_29
		//    یعنی نشستِ بی‌معامله در پنجره و کلِ ردیف را رد می‌کند.
		low := minLow[i]
		if low == 0 || math.IsNaN(hist[i]) || hist[i] < lowBaseSessions {
			low = math.NaN()
		}
		dist := board.Round2((pc[i] - low) / pc[i] * 100)
		f.Noqteh[i] = alive && pc[i] > 0 && dist < noqtehMaxDist &&
			vrf[i] > 1.0 && ztt[i] > noqtehTrades
		// F) ورودِ پولِ هوشمند — خطِ اولِ فایل دروازه است: بی سی اسلاتِ کامل و
		//    بی prior30_vol ردیف بیرون می‌افتد. [is6] جایِ مبنایِ حجم نیست و
		//    نبودش «نسنج» است (NaN)، نه صفر — وگرنه tvol > 1.5*0 هر ردیفی را
		//    روشن می‌کرد.
		line1 := !math.IsNaN(hist[i]) && hist[i] >= volBaseSessions && !math.IsNaN(prior[i])
		f.Smart[i] = alive && line1 && d.Tvol[i] > smartVolMult*is6[i] &&
			bp >= smartBPGe && pc[i] > 0 && pl[i] >= pc[i] && plp > 0
		// G) کد به کدِ حقوقی به حقیقی: پولِ هوشمند + هر دو سمت بیش از نیمی از
		//    حجمِ نشست. (نامِ فایل «حقوقی به حقیقی» است ولی قیدهایش «حقوقی
		//    می‌خرد / حقیقی می‌فروشد» — از متنِ فایل پیروی می‌شود، نه از نام.)
		f.Legal[i] = f.Smart[i] && bi[i] > legalShareTvol*d.Tvol[i] &&
			sn[i] > legalShareTvol*d.Tvol[i]
	}
	return f
}
