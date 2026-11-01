package fundamental

// معماری (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳). What changes: لایۀ ۲ از
// دو فایلِ پایتون به Go می‌آید — `fts_engine.eps_ladder` (1285-1443) و
// `fts_engine.eps_assessment` (1447-1568)، به‌علاوۀ لایۀ نمایشِ کارت
// `api/fundamental.ind2_eps_track` (827-894) با دو کمکیِ خودش
// (`_interim_eps_check` 772-824 و `_eps_yoy_pct` 223-236). وابستگی‌هایِ تنها
// خوانندۀ این لایه هم همین‌جا نشسته‌اند: `eps_trend_reason` (fts_engine 1242-1280)
// و `is_insurance_sector` (fts_engine 541-544) — هیچ‌کدام درِ فایلِ دیگری پورت
// نشده بودند و تعریفِ دومِ/exported نمی‌سازم (پیشوندِ `ax2`؛ `IsInsuranceSector`
// درِ gates.go مالِ گیت‌هایِ ریسک است و فایلِ درِ جریانِ همان ایجنت، پس این شاخه
// بی‌وابستگیِ موقت می‌ماند).
//
// Invariants: داورِ این لایه فقط وکتور است — نردبان یکِ تک‌پیاده‌سازیِ مشترکِ کارت و
// اسکرینر است و اینجا قاعدۀ انتخابِ دومِ تازه‌ای ساخته نمی‌شود؛ سه پرچمِ
// `consolidated_used`/`low_quality_track`/`relaxed_evidence` از خودِ برچسبِ
// اسلات‌ها ساخته می‌شوند (ترتیبِ سنجش جزءِ قاعدۀ tier است: «تلفیقی» پیش از تنزلِ
// میاندوره می‌افتد)؛ «سطر هرگز حذف نشود» ⇒ با دوره‌هایِ کم `partial=true` با
// خانه‌هایِ nil برمی‌گردد نه نتیجهٔ تهی؛ `na + data_gap` برایِ سابقه‌ای که **هر**
// اسلاتش تلفیقی است (حکمِ مالک ۱۴۰۵-۰۷، جزوۀ ص ۴)؛ و `interim_confirms` سه‌حاله
// است (nil = رأیِ ندادن)، وتویِ سخت نه. هیچ آستانه‌ای اینجا وضع نشده: `need` از
// `th["eps_years"]` و `years` می‌آید.
//
// Lockstep: رشته‌هایِ کاربر-دیدنی این فایل عینِ اوراکل‌اند (source، جدولِ
// `eps_basis`، `threshold`، `annualize_label`، متن‌هایِ reason) و با مقایسۀ
// بایتیِ same-file درِ آزمونِ literal سنجیده می‌شوند. Guard: `axis2_test.go` رویِ
// `testdata/vectors/indicators.json` (eps_ladder/eps_assess/ind2، اوراکلِ پایتون
// رویِ فیکسچرِ کامیت‌شدۀ `testdata/fixture/market.db` در کپیِ موقتِ فقط‌خواندنی).
// Rollback: حذفِ همین دو فایل.

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/pyround"
	"borsterminal/backend/internal/symbolid"
)

// ── رشته‌هایِ کاربر-دیدنی (verbatim؛ هیچ‌کدام جایِ دومِ ترجمه ندارند) ──────────

const (
	// ax2LadderSource عینِ `source` درِ شعبۀ کاملِ eps_ladder (fts_engine:1431).
	ax2LadderSource = "کدال — صورت‌های مالی سالانه + میاندوره"

	// ax2CardSource عینِ پیش‌فرضِ `base.setdefault("source", …)` درِ
	// ind2_eps_track (api/fundamental:891) — فقط شعباتی که نردبان source
	// نگذاشته (partial/insufficient) این را می‌گیرند.
	ax2CardSource = "کدال — صورت سود و زیان (حسابرسی شده، شرکت اصلی)"

	// متن‌هایِ reasonِ نردبان (fts_engine:1393، :1408، :1436).
	ax2ReasonFewYears  = "کمتر از %d سال مالیِ متوالی با EPS ثبت‌شده (موجود: 0)"
	ax2ReasonPartial   = "فقط %d دوره از %d موجود است — %s"
	ax2ReasonInterimEst = " (برآورد میاندوره)"

	// reasonهایِ eps_assessment (fts_engine:1459، :1470، :1505-1507).
	ax2ReasonInsurance    = "صنعت بیمه — لایهٔ EPS اجرا نمیشود."
	ax2ReasonNoStatements = "هیچ صورت مالیِ معتبری با EPS ثبت نشده."
	ax2ReasonConsolidated = "صورتهای مالی تلفیقی مدنظر نیست — سال‌های %s فقط تلفیقی منتشر " +
		"شده‌اند و سابقۀ سه‌سالۀ غیرتلفیقی کامل نیست."

	// reasonهایِ `_interim_eps_check` (api/fundamental:789، :799-800، :806-807).
	ax2ReasonNoInterim   = "صورت مالی میاندوره‌ایِ غیرتلفیقی ثبت نشده."
	ax2ReasonNoNewer     = "میاندورهٔ تازه‌تر از آخرین سالِ سابقه ثبت نشده است."
	ax2ReasonInTrack     = "میاندورهٔ جاری به‌عنوان سالِ در‌جریان داخل خودِ سابقه محاسبه شده."

	// برچسبِ annualize — «۱۲» رقمِ فارسیِ متنِ پایتون است و `%d`ِ pm رقمِ لاتین
	// می‌گیرد (عینِ `"EPS میاندوره × ۱۲÷%d" % pm`).
	ax2AnnualizeLabel = "EPS میاندوره × ۱۲÷%d"

	// جدولِ `eps_basis` درِ ind2_eps_track (api/fundamental:871-884) + پیش‌فرضش.
	ax2BasisUnknown = "شاهدِ کافی برای مسیر EPS موجود نیست"

	// پسوندِ `eps_basis` — پیوسته به tier، با فاصله (api/fundamental:884-886).
	ax2BasisWithInterim = " + راستی‌آزمایی میاندوره‌ای"
	ax2BasisNoInterim   = " (میاندورهٔ مستقلِ راستی‌آزمایی موجود نیست)"

	// `threshold` درِ ind2_eps_track (api/fundamental:887).
	ax2ThresholdLabel = "%d سال مالی متوالی"

	// متن‌هایِ `eps_trend_reason` (fts_engine:1252-1280).
	ax2TrendNoHistory  = "سابقهٔ EPS محاسبه نشد"
	ax2TrendAllNegative = "سودسازی منفی در تمام دورهها"
	ax2TrendLastCrash   = "سقوط سود به زیان در سال آخر"
	ax2TrendLossLast    = "زیاندهی در سال آخر (%s)"
	ax2TrendLossAt      = "زیاندهی در %s"
	ax2TrendGrowthStop  = "توقف رشد سود در %s"
	ax2TrendDrop        = "افت سود در %s%s"
	ax2TrendDropTail    = " (افت %.1f٪)"
	ax2TrendNotRising   = "روند سودسازی صعودی نیست"
	ax2TrendYearLabel   = "سال %d"
)

// ax2BasisTier عینِ دیکشنریِ درونِ `eps_basis`؛ «یگانه منبعِ حقیقتِ متن» تا
// کارتِ Go و کارتِ پایتون دو ترجمه برایِ یکِ tier نسازند.
var ax2BasisTier = map[string]string{
	"audited_year_end":       "سال‌پایانِ حسابرسی‌شدهٔ غیرتلفیقی",
	"unaudited_year_end":     "سال‌پایانِ غیرتلفیقی (حسابرسی‌نشده)",
	"year_end_unaudited":     "سال‌پایانِ غیرتلفیقی (حسابرسی‌نشده)",
	"consolidated_year_end":  "شامل صورتِ تلفیقی — آن سال‌ها غیرتلفیقی منتشر نشده" +
		" (مبنایِ جزوه: صورتِ شرکت اصلی)",
	"year_end_plus_interim":  "سال‌پایان + میاندورهٔ سال‌سازی‌شده × ۱۲÷م",
	"insurance":              "صنعت بیمه — لایهٔ EPS اجرا نمی‌شود",
	"insufficient":           ax2BasisUnknown,
}

// ax2EpsQuality عینِ `_EPS_QUALITY` (fts_engine:1281-1282) — برچسبِ شاهدِ هر
// سطحِ نردبان از همان شمارۀ رتبه‌ای می‌آید که انتخاب شده، نه از شاخۀ جداگانه.
var ax2EpsQuality = [4]string{"audited_year_end", "unaudited_year_end",
	"consolidated_audited", "consolidated_unaudited"}

// ── تبدیل‌هایِ عددیِ همین لایه ───────────────────────────────────────────────

// ax2NeedYears عینِ `need = max(int(years or 3), 2)`؛ صفرِ ورودی «بی‌years» است
// (falsy) نه «صورتِ مالیِ صفرساله»، و کفِ ۲ هم از خودِ قاعده است نه سلیقه.
func ax2NeedYears(years int) int {
	need := years
	if need == 0 {
		need = 3
	}
	if need < 2 {
		need = 2
	}
	return need
}

// ax2NumOrNone عینِ `_num_or_none` (api/fundamental:214-220) — «داده نیست»
// هیچ‌وقت ۰٫۰ نمی‌شود (برخلافِ toF)، و NaN هم None است چون پایتون `x == x` را
// می‌آزماید. تبدیل از تعریفِ یکتایِ `float()` می‌آید (`asFloat` درِ config.go)،
// پس رقمِ یونیکد هم مثلِ پایتون پذیرفته می‌شود.
func ax2NumOrNone(v any) any {
	f, ok := asFloat(v)
	if !ok || math.IsNaN(f) {
		return nil
	}
	return f
}

// ax2Pct عینِ `_pct` (api/fundamental:199-204): رشد٪ با محافظِ مخرجِ صفر —
// nil یعنی «محاسبه نشد»، نه «صفر درصد». (همان قاعدۀ ax1Pct؛ این لایه به فایلِ
// همسایه دست نمی‌زند و تابعِ exportedِ تازه نمی‌سازد.)
func ax2Pct(new, old any) any {
	o := toF(old)
	if o <= 0 {
		return nil
	}
	return pyround.Round((toF(new)/o-1.0)*100.0, 1)
}

// ax2EpsYoyPct عینِ `_eps_yoy_pct` (api/fundamental:223-236): درصدِ رشدِ سال‌به‌سال
// همان سری EPS. چهار حالت باید nil بماند — نخستین دوره (مبنایی ندارد)، سالِ غایب،
// دورۀ جاریِ بی‌عدد، و مبنایِ صفر/زیان (از راهِ ax2Pct). هیچ‌گاه جای nil عدد ۰٪
// نمی‌نشیند، پس رابطِ کاربر همان «داده نداریم» را می‌نویسد.
func ax2EpsYoyPct(series []any) []any {
	out := make([]any, 0, len(series))
	var prev any // مثلِ `prev = None` درِ پایتون
	for i, v := range series {
		cur := ax2NumOrNone(v)
		if i == 0 || cur == nil || prev == nil {
			out = append(out, nil)
		} else {
			out = append(out, ax2Pct(cur, prev))
		}
		prev = cur
	}
	return out
}

// ax2PyInt مثلِ `int(x)` رویِ سطرهایِ تاریخ: رشتهٔ رقمی (شاملِ رقمِ یونیکد) یا
// عدد. `period.FiscalYear` برشِ چهار *نویسه*یِ گروهِ `Nd{4}` است، پس این‌جا
// «+»/«_»/اعشار reachable نیست و تطبیقِ سختِ رقم با ValueErrorِ پایتون یکی می‌ماند.
func ax2PyInt(v any) (int, bool) {
	switch x := v.(type) {
	case string:
		if x == "" {
			return 0, false
		}
		var b strings.Builder
		for _, r := range x {
			if r >= '0' && r <= '9' {
				b.WriteRune(r)
				continue
			}
			d, ok := decimalDigit(r)
			if !ok {
				return 0, false
			}
			b.WriteByte('0' + byte(d))
		}
		n, err := strconv.ParseInt(b.String(), 10, 64)
		if err != nil {
			return 0, false
		}
		return int(n), true
	default:
		n, ok := asInt(v)
		if !ok {
			return 0, false
		}
		return n, true
	}
}

// ax2FiscalYearInt مثلِ `int(CP.fiscal_year(pe) or 0)`: بی‌دوره ⇒ ۰.
func ax2FiscalYearInt(periodEnd any) int {
	fy := period.FiscalYear(periodEnd)
	if fy == nil || *fy == "" {
		return 0
	}
	y, ok := ax2PyInt(*fy)
	if !ok {
		return 0
	}
	return y
}

// ax2IsInsuranceSector عینِ `is_insurance_sector` (fts_engine:541-544): رویِ
// `norm_fa(sector)` آزموده می‌شود، نه رویِ نماد (رفعِ باگِ v7.3). فهرستِ نشانه‌ها
// همان INSURANCE_TOKENS است.
var ax2InsuranceTokens = []string{"بیمه", "بازنشستگی"}

func ax2IsInsuranceSector(sector string) bool {
	s := normFa(sector)
	if s == "" {
		return false
	}
	for _, t := range ax2InsuranceTokens {
		if strings.Contains(s, normFa(t)) {
			return true
		}
	}
	return false
}

// ── eps_trend_reason (fts_engine:1242-1280) ─────────────────────────────────

// ax2TrendReason دلیلِ شکستِ روندِ EPS را از خودِ سری می‌سازد تا کاربر علتِ رد
// را ببیند، نه پیامِ مبهمِ «دیتا ناقص». بازگشت به نقطهٔ واقعیِ شکست: اولِ همه
// زیاندهی (که مهم‌ترین دلیلِ رد است)، بعدِ افت/توقفِ رشد.
func ax2TrendReason(series []float64, years []string) string {
	vals := make([]float64, 0, len(series))
	vals = append(vals, series...)
	yrs := years
	if len(vals) == 0 {
		return ax2TrendNoHistory
	}
	n := len(vals)
	ylab := func(i int) string {
		if i >= 0 && i < len(yrs) {
			return yrs[i]
		}
		return fmt.Sprintf(ax2TrendYearLabel, i+1)
	}
	if !allPositive(vals) {
		if allNonPositive(vals) {
			return ax2TrendAllNegative
		}
		if vals[n-1] <= 0 && (n < 2 || vals[n-2] > 0) {
			return ax2TrendLastCrash
		}
		if vals[n-1] <= 0 {
			return fmt.Sprintf(ax2TrendLossLast, ylab(n-1))
		}
		for i, v := range vals {
			if v <= 0 {
				return fmt.Sprintf(ax2TrendLossAt, ylab(i))
			}
		}
	}
	for i := 0; i+1 < n; i++ {
		if vals[i+1] <= vals[i] {
			if vals[i+1] == vals[i] {
				return fmt.Sprintf(ax2TrendGrowthStop, ylab(i+1))
			}
			tail := ""
			if vals[i] != 0 {
				pct := pyround.Round((vals[i+1]/vals[i]-1.0)*100.0, 1)
				tail = fmt.Sprintf(ax2TrendDropTail, math.Abs(pct))
			}
			return fmt.Sprintf(ax2TrendDrop, ylab(i+1), tail)
		}
	}
	return ax2TrendNotRising
}

func allPositive(vals []float64) bool {
	for _, v := range vals {
		if !(v > 0) {
			return false
		}
	}
	return true
}

func allNonPositive(vals []float64) bool {
	for _, v := range vals {
		if !(v <= 0) {
			return false
		}
	}
	return true
}

// ── eps_ladder (fts_engine:1285-1443) ───────────────────────────────────────

// ax2LadderColumns عینِ ستون‌هایِ همان کوئری — ترتیب درِ پایتون محلِ unpack است،
// اینجا خواندن به‌نام است و فهرست دست‌نخورده می‌ماند.
const ax2LadderColumns = "period_end, period_months, title, basic_eps, net_profit, tracing_no"

// ax2Record یکِ ردیفِ EPS‌دارِ نردبان — همان هفت‌تاییِ درونِ `per_year`
// (months, audited, eps, net, period_end, consolidated, tracing_no).
type ax2Record struct {
	months  int
	audited bool
	eps     float64
	net     any    // `_fn`: nilِ واقعی حفظ می‌شود، صفرِ جعلی نه
	pe      string // canonical (or "")
	cons    bool
	tracing any // خامِ ستونِ tracing_no
}

// ax2Bucket خانهٔ یکِ سالِ مالی: سالانہ‌ها و میاندوره‌ها جدا.
type ax2Bucket struct {
	annual []ax2Record
	interim []ax2Record
}

// ax2RankKey عینِ سه‌تاییِ `_rank`: (سطحِ شاهد، −طولِ دوره، دورۀ canonical).
// طولِ بیشتر اول، و درِ تساوی دورۀ *قدیمی‌تر* (پایتون `pe` صعودی می‌چیند).
type ax2RankKey struct {
	quality int
	negLen  int
	pe      string
}

func (a ax2RankKey) cmp(b ax2RankKey) int {
	if a.quality != b.quality {
		if a.quality < b.quality {
			return -1
		}
		return 1
	}
	if a.negLen != b.negLen {
		if a.negLen < b.negLen {
			return -1
		}
		return 1
	}
	if a.pe != b.pe {
		if a.pe < b.pe {
			return -1
		}
		return 1
	}
	return 0
}

func ax2RankOf(r ax2Record) ax2RankKey {
	if r.months >= 12 {
		q := 0
		if r.cons {
			q += 2
		}
		if !r.audited {
			q += 1
		}
		return ax2RankKey{quality: q, negLen: -r.months, pe: r.pe}
	}
	return ax2RankKey{quality: 4, negLen: -r.months, pe: r.pe}
}

// ax2Picked خروجیِ `_pick`: (eps, period_end, quality, months, cons, net, tn).
// برایِ سالانہ eps خام است (گردکردن کارِ مصرف‌کننده است) و net از خودِ ردیف؛
// برایِ میاندوره eps × ۱۲÷م گردِ دوردهیم است و net عمداً nil — «سودِ سال»
// ساخته نشده، فقط EPS برآورد شده است.
type ax2Picked struct {
	eps     float64
	pe      string
	quality string
	months  int
	cons    bool
	net     any
	tracing any
}

// ax2Pick بهترین رکوردِ یکِ سالِ مالی — پنج سطح: سال‌پایانِ حسابرسی‌شدۀ
// غیرتلفیقی ← حسابرسی‌نشده ← تلفیقیِ حسابرسی‌شده ← تلفیقیِ حسابرسی‌نشده ←
// بلندترین میاندورۀ همان سال × ۱۲÷م. `sorted(...)[0]`ِ پایتون پایدار است، پس
// اینجا «کمترینِ سخت‌گیرانه با برتریِ دیدارِ نخست» همان چیزی است که می‌ماند.
func ax2Pick(b ax2Bucket) ax2Picked {
	all := make([]ax2Record, 0, len(b.annual)+len(b.interim))
	all = append(all, b.annual...)
	all = append(all, b.interim...)
	best, bestKey := all[0], ax2RankOf(all[0])
	for _, r := range all[1:] {
		k := ax2RankOf(r)
		if k.cmp(bestKey) < 0 {
			best, bestKey = r, k
		}
	}
	if best.months >= 12 {
		return ax2Picked{eps: best.eps, pe: best.pe, quality: ax2EpsQuality[bestKey.quality],
			months: best.months, cons: best.cons, net: best.net, tracing: best.tracing}
	}
	quality := "annualized_interim"
	if best.months < 6 {
		quality = "annualized_interim_short"
	}
	return ax2Picked{eps: pyround.Round(best.eps*12.0/float64(best.months), 2), pe: best.pe,
		quality: quality, months: best.months, cons: best.cons, net: nil, tracing: best.tracing}
}

// EpsLadder سابقهٔ سودسازی با نردبانِ شفافِ شاهد است — تک‌پیاده‌سازیِ هر دو مسیر
// (کارت و اسکرینر). نبودنِ سالانۀ مستقیم هرگز به‌تنهایی data_gap نیست؛ هر تنزل
// با `evidence` برچسب می‌خورد، نه این‌که پنهان شود. سالِ درِ جریان (فقط میاندوره)
// بیرونِ سابقه می‌ماند مگر این‌که سابقۀ needساله از آبِ تمام‌ها درنیاید.
//
// دو قاعدۀ شکست‌ناپذیر که درِ همین تابع نشسته‌اند: ردیفِ «شرکتِ دیگر»
// (`titleEntitySuffix`) از سبدِ بیرون می‌ماند — بی‌این EPS یکِ شرکتِ فرعی واردِ
// سابقۀ سودسازی نماد می‌شد — و طولِ دوره از `EffectiveMonths` می‌آید نه از ستونِ
// خام («دورۀ ۶ ماهه» با ستونِ ۱۲ شش‌ماهه است).
//
// بی‌هیچ ردیفِ EPS‌دارِ معتبر `{}` برمی‌گردد (عینِ `return {}`)؛ داوریِ «بی‌شاهد»
// کارِ `EpsAssessment` است.
func (s *Service) EpsLadder(ctx context.Context, symbol string, years int) (map[string]any, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		// همان برگشتِ لایۀ صورتِ مالی (statements.go): خطایِ واقعیِ بانک درِ
		// کوئریِ بعدی بالا می‌رود، پس این «بی‌داده» جعلی نمی‌سازد.
		pred, args = "symbol = ?", []any{symbol}
	}
	query := "SELECT " + ax2LadderColumns + " FROM financial_statements WHERE " + pred +
		" AND basic_eps IS NOT NULL " +
		"AND (period_months > 0 OR period_months IS NULL) " +
		"AND " + period.DatedSQL("") + " ORDER BY period_end DESC LIMIT 120"
	raw, err := s.rows(ctx, query, args)
	if err != nil {
		return nil, err
	}

	perYear := map[int]*ax2Bucket{}
	for _, r := range raw {
		title := strOr(r["title"])
		if titleEntitySuffix(title) != "" {
			continue
		}
		months, _ := period.EffectiveMonths(r["period_end"], r["period_months"], title)
		fy := period.FiscalYear(r["period_end"])
		if fy == nil {
			continue // `int(None)` ⇒ TypeError ⇒ `continue`
		}
		y, ok := ax2PyInt(*fy)
		if !ok {
			continue // `float(eps)`/`int(…)ِ` بی‌محتوا ⇒ ValueError ⇒ `continue`
		}
		// `float(eps)` — تعریفِ یکتایِ پایتون (`asFloat` درِ config.go): رقمِ
		// یونیکد و زیرخط هم پذیرفته می‌شوند، پس EPSِ «۱۲۵» ۱۲۵ است و نه بی‌محتوا.
		ev, ok := asFloat(r["basic_eps"])
		if !ok {
			continue
		}
		if y <= 0 || months == nil || *months == 0 {
			continue
		}
		cons := isConsolidated(title)
		bucket, seen := perYear[y]
		if !seen {
			bucket = &ax2Bucket{}
			perYear[y] = bucket
		}
		rec := ax2Record{months: *months, audited: stmtIsAudited(title), eps: ev,
			net: stmtFloatOrNull(r["net_profit"]), pe: strNilToEmpty(period.Canonicalize(r["period_end"])),
			cons: cons, tracing: r["tracing_no"]}
		if *months >= 12 {
			bucket.annual = append(bucket.annual, rec)
		} else {
			bucket.interim = append(bucket.interim, rec)
		}
	}
	if len(perYear) == 0 {
		return map[string]any{}, nil
	}

	yearsSorted := make([]int, 0, len(perYear))
	for y := range perYear {
		yearsSorted = append(yearsSorted, y)
	}
	sort.Slice(yearsSorted, func(i, j int) bool { return yearsSorted[i] > yearsSorted[j] })

	hasAnnual := func(y int) bool { return len(perYear[y].annual) > 0 }
	complete := make([]int, 0, len(yearsSorted))
	for _, y := range yearsSorted {
		if hasAnnual(y) {
			complete = append(complete, y)
		}
	}
	newest := yearsSorted[0]
	inProgress := 0
	hasInProgress := false
	if !hasAnnual(newest) {
		inProgress, hasInProgress = newest, true
	}
	need := ax2NeedYears(years)
	window := make([]int, 0, need)
	if len(complete) > 0 {
		y := complete[0]
		for len(window) < need {
			if _, ok := perYear[y]; !ok {
				break
			}
			window = append(window, y)
			y--
		}
		if len(window) < need && hasInProgress && inProgress == window[0]+1 {
			window = append([]int{inProgress}, window...)
			inProgress, hasInProgress = 0, false
		}
	}

	out := map[string]any{
		"years_required":   need,
		"years_available":  len(window),
		"in_progress_year": ax2OrNilInt(inProgress, hasInProgress),
		"fiscal_years":     ax2YearsReversed(window),
	}
	if len(window) < need {
		if len(window) == 0 {
			out["eps_series"] = nil
			out["pass"] = false
			out["data_gap"] = true
			out["available_periods"] = 0
			out["periods_missing"] = need
			out["partial"] = false
			out["reason"] = fmt.Sprintf(ax2ReasonFewYears, need)
			return out, nil
		}
		pickedG := make(map[int]ax2Picked, len(window))
		top := window[0]
		for _, y := range window {
			pickedG[y] = ax2Pick(*perYear[y])
			if y > top {
				top = y
			}
		}
		slots := make([]int, 0, need)
		for y := top - need + 1; y <= top; y++ {
			slots = append(slots, y)
		}
		series := make([]any, 0, need)
		slotStrs := make([]any, 0, need)
		periodEnds := make([]any, 0, need)
		evidence := make([]any, 0, need)
		monthsOut := make([]any, 0, need)
		nets := make([]any, 0, need)
		tnos := make([]any, 0, need)
		have := make([]string, 0, len(window))
		for _, y := range slots {
			slotStrs = append(slotStrs, strconv.Itoa(y))
			p, ok := pickedG[y]
			if !ok {
				series = append(series, nil)
				periodEnds = append(periodEnds, nil)
				evidence = append(evidence, "missing")
				monthsOut = append(monthsOut, nil)
				nets = append(nets, nil)
				tnos = append(tnos, nil)
				continue
			}
			series = append(series, pyround.Round(toF(p.eps), 2))
			periodEnds = append(periodEnds, p.pe)
			evidence = append(evidence, p.quality)
			monthsOut = append(monthsOut, p.months)
			nets = append(nets, p.net)
			tnos = append(tnos, p.tracing)
			have = append(have, strconv.Itoa(y))
		}
		reason := ""
		if len(have) < need {
			parts := make([]string, 0, len(have))
			for _, y := range have {
				n, _ := ax2PyInt(y)
				parts = append(parts, fmt.Sprintf("%s: %s", y, pyStr(pickedG[n].eps)))
			}
			reason = fmt.Sprintf(ax2ReasonPartial, len(have), need, strings.Join(parts, " و "))
		}
		out["eps_series"] = series
		out["period_slots"] = slotStrs
		out["period_ends"] = periodEnds
		out["evidence"] = evidence
		out["period_months"] = monthsOut
		out["net_profit_series"] = nets
		out["ref_tracing_nos"] = tnos
		out["available_periods"] = len(have)
		out["periods_missing"] = need - len(have)
		out["partial"] = true
		out["pass"] = false
		out["data_gap"] = true
		out["reason"] = reason
		return out, nil
	}

	picked := make([]ax2Picked, 0, len(window))
	for _, y := range window {
		picked = append(picked, ax2Pick(*perYear[y]))
	}
	rev := make([]ax2Picked, 0, len(picked))
	for i := len(picked) - 1; i >= 0; i-- {
		rev = append(rev, picked[i])
	}
	seriesRaw := make([]float64, 0, len(rev))
	series := make([]any, 0, len(rev))
	slotStrs := make([]any, 0, len(rev))
	periodEnds := make([]any, 0, len(rev))
	ev := make([]string, 0, len(rev))
	evOut := make([]any, 0, len(rev))
	monthsOut := make([]any, 0, len(rev))
	nets := make([]any, 0, len(rev))
	tnos := make([]any, 0, len(rev))
	consAny, auditedOnly, relaxed, lowQ := false, true, false, false
	for i, p := range rev {
		seriesRaw = append(seriesRaw, p.eps)
		series = append(series, pyround.Round(toF(p.eps), 2))
		slotStrs = append(slotStrs, strconv.Itoa(window[len(window)-1-i]))
		periodEnds = append(periodEnds, p.pe)
		ev = append(ev, p.quality)
		evOut = append(evOut, p.quality)
		monthsOut = append(monthsOut, p.months)
		nets = append(nets, p.net)
		tnos = append(tnos, p.tracing)
		if p.cons {
			consAny = true
		}
		if p.quality != "audited_year_end" {
			auditedOnly = false
			relaxed = true
		}
		if strings.HasPrefix(p.quality, "annualized_interim") {
			lowQ = true
		}
	}
	strictlyRising := true
	for i := 0; i+1 < len(seriesRaw); i++ {
		if !(seriesRaw[i] < seriesRaw[i+1]) {
			strictlyRising = false
			break
		}
	}
	out["eps_series"] = series
	out["period_slots"] = slotStrs
	out["partial"] = false
	out["available_periods"] = need
	out["periods_missing"] = 0
	out["period_ends"] = periodEnds
	out["evidence"] = evOut
	out["period_months"] = monthsOut
	out["net_profit_series"] = nets
	out["ref_tracing_nos"] = tnos
	out["consecutive_years"] = true
	out["strictly_rising"] = strictlyRising
	out["all_profitable"] = allPositive(seriesRaw)
	out["consolidated_used"] = consAny
	out["audited_only"] = auditedOnly
	out["relaxed_evidence"] = relaxed
	out["low_quality_track"] = lowQ
	out["fiscal_years"] = ax2YearsReversed(window)
	out["data_gap"] = false
	out["source"] = ax2LadderSource
	pass := strictlyRising && allPositive(seriesRaw)
	out["pass"] = pass
	softGap := !pass && len(ev) > 0 && ev[len(ev)-1] == "annualized_interim_short"
	out["soft_gap"] = softGap
	if pass {
		out["reason"] = ""
	} else {
		reason := ax2TrendReason(seriesRaw, ax2YearsReversedStr(window))
		if softGap {
			reason += ax2ReasonInterimEst
		}
		out["reason"] = reason
	}
	return out, nil
}

// ax2YearsReversed همان `[str(y) for y in reversed(window)]` — قدیمی ← تازه.
func ax2YearsReversed(window []int) []any {
	out := make([]any, 0, len(window))
	for i := len(window) - 1; i >= 0; i-- {
		out = append(out, strconv.Itoa(window[i]))
	}
	return out
}

func ax2YearsReversedStr(window []int) []string {
	out := make([]string, 0, len(window))
	for i := len(window) - 1; i >= 0; i-- {
		out = append(out, strconv.Itoa(window[i]))
	}
	return out
}

// ax2OrNilInt مثلِ `in_progress`ِ پایتون: یا شمارۀ سال یا None.
func ax2OrNilInt(v int, present bool) any {
	if !present {
		return nil
	}
	return v
}

// strNilToEmpty عینِ `CP.canonicalize(pe) or ""`.
func strNilToEmpty(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// ── eps_assessment (fts_engine:1447-1568) ───────────────────────────────────

// EpsAssessment داوریِ نهاییِ شاخص ۲ رویِ یکِ نردبان است — کارت و اسکرینر همان را
// می‌خوانند. بیمه پیش‌گیت است (لایه اجرا نمی‌شود) و سابقه‌ای که **هر** اسلاتش از
// صورتهایِ تلفیقی باشد «رد» هم نیست و «سبز» هم: `na + data_gap`.
//
// سه پرچم از خودِ برچسبِ اسلات‌ها ساخته می‌شوند، نه از شاخۀ خاصِ نردبان (شعبۀ
// partial هرگز consolidated_used را نمی‌گذاشت) و ترتیبِ سنجشِ tier جزءِ قاعده است:
// «تلفیقی» مبنایِ جزوه نیست و باید زودتر از تنزلِ میاندوره بیفتد.
func (s *Service) EpsAssessment(ctx context.Context, symbol string, years int,
	sector string) (map[string]any, error) {
	need := ax2NeedYears(years)
	if ax2IsInsuranceSector(sector) {
		return map[string]any{"eps_series": nil, "pass": false, "na": true,
			"data_gap": false, "years_required": need, "years_available": 0,
			"evidence_tier": "insurance", "strict_evidence": false,
			"relaxed_evidence": false, "consolidated_used": false,
			"low_quality_track": false, "soft_gap": false,
			"reason":         ax2ReasonInsurance}, nil
	}
	track, err := s.EpsLadder(ctx, symbol, need)
	if err != nil {
		return nil, err
	}
	ev := ax2EvidenceStrs(track["evidence"])
	if len(track) == 0 || ax2NumIsZero(ax2GetOr(track, "available_periods", 0)) {
		reason := track["reason"]
		if isFalsy(reason) {
			reason = ax2ReasonNoStatements
		}
		return map[string]any{"eps_series": nil, "pass": false, "data_gap": true,
			"years_required": need, "years_available": 0,
			"evidence_tier": "insufficient", "strict_evidence": false,
			"relaxed_evidence": false, "consolidated_used": false,
			"low_quality_track": false, "soft_gap": false,
			"reason":         reason}, nil
	}

	consYears := make([]string, 0, len(ev))
	slots := ax2SlotStrings(track["period_slots"])
	for i, e := range ev {
		if i < len(slots) && strings.HasPrefix(e, "consolidated_") {
			consYears = append(consYears, slots[i])
		}
	}
	track["consolidated_used"] = len(consYears) > 0
	track["low_quality_track"] = ax2AnyHasPrefix(ev, "annualized_interim")
	track["relaxed_evidence"] = ax2AnyNotStrict(ev)

	tier := "insufficient"
	switch {
	case len(ev) > 0 && ax2AllEqual(ev, "audited_year_end"):
		tier = "audited_year_end"
	case len(consYears) > 0:
		tier = "consolidated_year_end"
	case truthy(track["low_quality_track"]):
		tier = "year_end_plus_interim"
	case truthy(track["relaxed_evidence"]):
		tier = "year_end_unaudited"
	}
	track["evidence_tier"] = tier
	track["strict_evidence"] = tier == "audited_year_end"
	if tier == "consolidated_year_end" {
		track["pass"] = false
		track["na"] = true
		track["data_gap"] = true
		track["consolidated_years"] = ax2ToAny(consYears)
		note := fmt.Sprintf(ax2ReasonConsolidated, strings.Join(consYears, "، "))
		prior := strOr(track["reason"])
		if prior != "" {
			note = prior + " " + note
		}
		track["reason"] = note
	}
	return track, nil
}

// ax2EvidenceStrs مثلِ `[str(e or "") for e in (track.get("evidence") or [])]`.
func ax2EvidenceStrs(v any) []string {
	list, _ := v.([]any)
	out := make([]string, 0, len(list))
	for _, e := range list {
		out = append(out, strOr(e))
	}
	return out
}

// ax2SlotStrings مثلِ `(track.get("period_slots") or [])` با str.
func ax2SlotStrings(v any) []string {
	list, _ := v.([]any)
	out := make([]string, 0, len(list))
	for _, y := range list {
		out = append(out, pyStr(y))
	}
	return out
}

func ax2ToAny(xs []string) []any {
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, x)
	}
	return out
}

// ax2AnyHasPrefix مثلِ `any(e.startswith(p) for e in ev)`.
func ax2AnyHasPrefix(ev []string, p string) bool {
	for _, e := range ev {
		if strings.HasPrefix(e, p) {
			return true
		}
	}
	return false
}

// ax2AnyNotStrict مثلِ `any(e not in ("audited_year_end", "missing") for e in ev)`
// — «missing» خانهٔ غایب است، نه شاهدِ بی‌کیفیت؛ بی‌این استثنا هر سابقۀ partial
// relaxed می‌شد.
func ax2AnyNotStrict(ev []string) bool {
	for _, e := range ev {
		if e != "audited_year_end" && e != "missing" {
			return true
		}
	}
	return false
}

func ax2AllEqual(ev []string, want string) bool {
	for _, e := range ev {
		if e != want {
			return false
		}
	}
	return true
}

// ax2GetOr مثلِ `track.get(key, default)`.
func ax2GetOr(m map[string]any, key string, def any) any {
	if v, ok := m[key]; ok {
		return v
	}
	return def
}

// ax2NumIsZero مثلِ `== 0` رویِ مقداری که یا عدد است یا nil (بی‌عدد ⇒ ۰، همان
// پیش‌فرضِ `get(key, 0)`).
func ax2NumIsZero(v any) bool {
	f, ok := asFloat(v)
	if !ok {
		return true
	}
	return f == 0
}

// ── _interim_eps_check (api/fundamental:772-824) ────────────────────────────

// ax2InterimEpsCheck می‌پرسد آیا سالِ مالیِ جاری هم با همان شتابِ سودسازی پیش
// می‌رود: EPS تجمیعیِ میاندوره × ۱۲÷ماه = برآوردِ سالِ جاری، مقایسه با آخرین EPS
// سال‌پایان. دو گِردِشِ واقعی بسته شده‌اند — اگر همان میاندوره پیش‌تر داخلِ سابقه
// باشد مقایسهٔ عدد با خودش می‌شود، و اگر تازه‌ترین میاندوره از آخرین سالِ سابقه
// قدیمی‌تر باشد «قطعِ روند» کاذب می‌سازد؛ پس فقط میاندورۀ **تازه‌تر از سال‌های
// سابقه** دیده می‌شود.
func (s *Service) ax2InterimEpsCheck(ctx context.Context, symbol string, lastFyEps any,
	trackPeriodEnds []any, trackYears []any) (map[string]any, error) {
	pred, args, err := s.sid.Pred(ctx, "symbol", symbol, symbolid.Codal)
	if err != nil {
		pred, args = "symbol = ?", []any{symbol}
	}
	query := "SELECT period_end, period_months, basic_eps, title FROM financial_statements " +
		"WHERE " + pred + " AND " + period.DatedSQL("") +
		" AND period_months BETWEEN 1 AND 11 AND basic_eps IS NOT NULL " +
		"ORDER BY period_end DESC LIMIT 40"
	raw, err := s.rows(ctx, query, args)
	if err != nil {
		return nil, err
	}
	cand := make([]map[string]any, 0, len(raw))
	for _, r := range raw {
		if isConsolidated(strOr(r["title"])) {
			continue
		}
		cand = append(cand, r)
	}
	if len(cand) == 0 {
		return map[string]any{"available": false, "reason": ax2ReasonNoInterim}, nil
	}
	seen := make(map[string]bool, len(trackPeriodEnds))
	for _, pe := range trackPeriodEnds {
		if s, ok := pe.(string); ok {
			seen[s] = true
		}
	}
	newestTy := 0
	for _, y := range trackYears {
		n, ok := ax2PyInt(strOr(y))
		if !ok {
			newestTy = 0
			break // `max(…)` با بی‌عددِ هر عضو می‌شکند ⇒ `except` ⇒ ۰
		}
		if n > newestTy {
			newestTy = n
		}
	}
	if newestTy != 0 {
		newer := make([]map[string]any, 0, len(cand))
		for _, r := range cand {
			if ax2FiscalYearInt(r["period_end"]) > newestTy {
				newer = append(newer, r)
			}
		}
		if len(newer) == 0 {
			return map[string]any{"available": false, "reason": ax2ReasonNoNewer}, nil
		}
		cand = newer
	}
	first := cand[0]
	peC := strNilToEmpty(period.Canonicalize(first["period_end"]))
	if seen[peC] {
		return map[string]any{"available": false, "period_end": peC,
			"reason": ax2ReasonInTrack}, nil
	}
	pm := int(toF(first["period_months"]))
	if pm == 0 {
		pm = 1
	}
	eps := toF(first["basic_eps"])
	y := ax2FiscalYearInt(first["period_end"])
	var prev map[string]any
	wantFy := strconv.Itoa(y - 1)
	for _, r := range cand[1:] {
		fy := period.FiscalYear(r["period_end"])
		if fy == nil || *fy != wantFy {
			continue
		}
		if int(toF(r["period_months"])) == pm {
			prev = r
			break
		}
	}
	projected := pyround.Round(eps*12.0/float64(pm), 2)
	out := map[string]any{
		"available":           true,
		"period_end":          peC,
		"period_months":       pm,
		"eps_interim":         pyround.Round(eps, 2),
		"eps_projected_year":  projected,
		"annualize_label":     fmt.Sprintf(ax2AnnualizeLabel, pm),
		"title":               stmtFirstRunes(strOr(first["title"]), 70),
	}
	if prev == nil {
		out["same_period_last_year"] = nil
		out["interim_yoy_pct"] = nil
	} else {
		out["same_period_last_year"] = pyround.Round(toF(prev["basic_eps"]), 2)
		out["interim_yoy_pct"] = ax2Pct(eps, toF(prev["basic_eps"]))
	}
	if lastFyEps == nil {
		out["continues_trend"] = nil
	} else {
		out["continues_trend"] = projected > toF(lastFyEps)
	}
	return out, nil
}

// ── ind2_eps_track (api/fundamental:827-894) ────────────────────────────────

// Ind2EpsTrack لایۀ ۲ (EPS سه سالِ مالیِ متوالی، اکیداً صعودی و همگی مثبت) — لایۀ
// نمایشِ کارت. داوری درِ `EpsAssessment` است (همان تابعی که اسکرینر می‌خواند)، پس
// کارت و اسکرینر دو عدد از دو قاعده نمی‌بینند؛ این‌جا فقط سه چیز افزوده می‌شود:
// نشانه‌هایِ جدول (partial/period_slots)، درصدِ رشدِ سال‌به‌سالِ سری
// (`eps_yoy_pct` — موتور می‌سازد، UI دوباره حک نمی‌کند) و راستی‌آزماییِ میاندوره
// (`interim_confirms` — هشدارِ نرم، وتویِ سخت نه؛ قراردادِ v9.7.4).
//
// `th` نقشۀ آستانه‌هاست (nil/خالی ⇒ `V10Thresholds({})`) و `lastFyEps` تنها وقتی
// مصرف می‌شود که سریِ EPS عددِ راستی‌آزمایی‌شدۀ آخر نداشته باشد — سه‌حالگی‌اش
// (nil ≠ ۰) درِ `ax2InterimEpsCheck` حفظ می‌شود.
func (s *Service) Ind2EpsTrack(ctx context.Context, symbol string, th map[string]any,
	sector string, lastFyEps any) (map[string]any, error) {
	if len(th) == 0 {
		th = V10Thresholds(nil)
	}
	need := int(toF(th["eps_years"]))
	base, err := s.EpsAssessment(ctx, symbol, need, sector)
	if err != nil {
		return nil, err
	}
	tier := strOr(ax2GetOr(base, "evidence_tier", "insufficient"))
	if tier == "" {
		tier = "insufficient"
	}
	// حالتِ «ناقص»: دوره‌هایِ موجود نشان داده می‌شوند و جایِ غایب خالی می‌ماند.
	ser := ax2SliceOrEmpty(base["eps_series"])
	realVals := make([]any, 0, len(ser))
	for _, v := range ser {
		if v != nil {
			realVals = append(realVals, v)
		}
	}
	yrNeed := int(toF(ax2GetOr(base, "years_required", need)))
	base["partial"] = truthy(ax2GetOr(base, "partial", false)) ||
		(len(ser) > 0 && len(realVals) < yrNeed)
	if _, ok := base["available_periods"]; !ok {
		base["available_periods"] = len(realVals)
	}
	if _, ok := base["periods_missing"]; !ok {
		missing := int(toF(ax2GetOr(base, "years_required", need))) - len(realVals)
		if missing < 0 {
			missing = 0
		}
		base["periods_missing"] = missing
	}
	if isFalsy(ax2GetOr(base, "period_slots", nil)) {
		fs := ax2SliceOrEmpty(base["fiscal_years"])
		slots := make([]any, 0, len(fs))
		for _, y := range fs {
			slots = append(slots, pyStr(y))
		}
		base["period_slots"] = slots
	}
	base["eps_yoy_pct"] = ax2EpsYoyPct(ser)

	var latest any
	if len(realVals) > 0 {
		latest = ax2NumOrNone(realVals[len(realVals)-1])
	}
	if latest == nil {
		latest = lastFyEps
	}
	interim, err := s.ax2InterimEpsCheck(ctx, symbol, latest,
		ax2SliceOrEmpty(base["period_ends"]), ax2SliceOrEmpty(base["fiscal_years"]))
	if err != nil {
		return nil, err
	}
	if interim == nil {
		interim = map[string]any{}
	}
	base["interim"] = interim
	switch {
	case !truthy(interim["available"]), interim["continues_trend"] == nil:
		base["interim_confirms"] = nil
	default:
		base["interim_confirms"] = truthy(interim["continues_trend"])
	}
	basis, ok := ax2BasisTier[tier]
	if !ok {
		basis = ax2BasisUnknown
	}
	if truthy(interim["available"]) {
		basis += ax2BasisWithInterim
	} else {
		basis += ax2BasisNoInterim
	}
	base["eps_basis"] = basis
	base["threshold"] = fmt.Sprintf(ax2ThresholdLabel, need)
	for key, def := range map[string]any{"consolidated_used": false,
		"low_quality_track": false, "soft_gap": false,
		"source": ax2CardSource, "reason": ""} {
		if _, ok := base[key]; !ok {
			base[key] = def
		}
	}
	return base, nil
}

// ax2SliceOrEmpty مثلِ `x or []` رویِ فهرستِ سری‌ها: nil و خالی یکی‌اند.
func ax2SliceOrEmpty(v any) []any {
	if list, ok := v.([]any); ok {
		return list
	}
	return []any{}
}
