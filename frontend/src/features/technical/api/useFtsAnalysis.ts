// features/technical/api/useFtsAnalysis.ts -- تحلیل FTS سمت سرور (بدج استریپ)
// موازی با بج های tech_rtv.js قدیمی: روند D/W/M، فیبو، جت، CHoCH، شکار نقطه، موتور خروج.
// پاسخ empty (نماد بدون تاریخچه) حالت مشروع است و ماسک نمی شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const TrendLeg = z.object({
  trend: z.string(),
  // مبنایِ رأی: 'pivots' یا 'recent-window' (پیوتِ کهنه ⇒ سنجشِ مستقیمِ بازهٔ اخیر)
  basis: z.string().nullish(),
  hh: z.boolean().nullish(),
  hl: z.boolean().nullish(),
  last_high: z.number().nullish(),
  prev_high: z.number().nullish(),
  last_low: z.number().nullish(),
  prev_low: z.number().nullish(),
  // تازه‌ترین پیوت چند کندل عقب است و خودش کِی بسته شده — بدونِ این دو، چارت
  // نمی‌تواند بگوید رأیِ روند روی ساختارِ زنده است یا روی چند ماه پیش.
  stale_bars: z.number().nullish(),
  last_pivot_time: z.string().nullish(),
});

const FibZone = z.object({
  lo: z.number().nullish(),
  hi: z.number().nullish(),
  in_zone: z.boolean().nullish(),
});

const Fib = z
  .object({
    retrace_base_high: z.number().nullish(),
    retrace_base_low: z.number().nullish(),
    zone_33_40: FibZone.nullish(),
    zone_618_70: FibZone.nullish(),
    // سطوحِ کاملِ ابزارِ فیبو (۰ تا ۱) و خودِ موجِ لنگر — چارت این‌ها را رسم
    // می‌کند و هیچ‌چیز را دوباره حساب نمی‌کند.
    levels: z.array(z.object({ ratio: z.number(), price: z.number() })).nullish(),
    leg: z
      .object({
        direction: z.string().nullish(),
        start: z.string().nullish(),
        end: z.string().nullish(),
        high: z.number().nullish(),
        low: z.number().nullish(),
        // موجِ بی‌پیوتِ فراکتال = «در حال تشکیل» (P0#4)؛ رابط این را با
        // ساختارِ تأییدشده یکی نمی‌گیرد.
        provisional: z.boolean().nullish(),
      })
      .nullish(),
  })
  .nullish();

const Setup = z.object({
  date: z.string(),
  kind: z.string(),
  label: z.string(),
  price: z.number(),
  side: z.string().nullish(),
});

const Jet = z.object({
  active: z.boolean().nullish(),
  resistance: z.number().nullish(),
  // تاریخِ همان کندلِ سقفِ پلکان — خطِ مقاومت فقط تا همین‌جا رسم می‌شود، نه رویِ
  // کلِ تاریخِ چارت (سلسله‌مراتبِ دورِ J).
  resistance_date: z.string().nullish(),
  ceiling: z.number().nullish(),
  ceiling_date: z.string().nullish(),
  // لایۀ «سقفِ ایستاده» (جزوه: مقاومتِ استاتیکِ افقی). این سه کلید باید درِ
  // قرارداد باشند، وگرنه Zod آن‌ها را بی‌صدا دور می‌ریزد و tier هرگز نمی‌رسد.
  static_broke: z.boolean().nullish(),
  tier: z.string().nullish(),
  ath: z.boolean().nullish(),
  close: z.number().nullish(),
  pct_above_res: z.number().nullish(),
  // «چرا جت نیست» — سرور بی‌تاریخچهٔ کافی همین را می‌فرستد و فرانت قبلاً
  // دورش می‌ریخت، پس برچسب بی‌دلیل خاموش می‌ماند.
  reason: z.string().nullish(),
  // تعدادِ واقعی در برابرِ کفِ لازم (P0#2) — «ناکافی» با عدد، نه بی‌صدا.
  bars_available: z.number().nullish(),
  bars_required: z.number().nullish(),
});

const Choch = z.object({
  bearish: z.boolean().nullish(),
  bullish: z.boolean().nullish(),
  level: z.number().nullish(),
  label: z.string().nullish(),
  // قاعدۀ تأیید از سرور خوانده می‌شود نه از عددِ دست‌نویسِ فرانت (دو بسته، حاشیۀ ۱٪)
  confirm_days: z.number().nullish(),
  margin: z.number().nullish(),
  reason: z.string().nullish(),
});

const PointHunt = z.object({
  touches: z.number().nullish(),
  floor_price: z.number().nullish(),
  active: z.boolean().nullish(),
  bounced: z.boolean().nullish(),
  floor_idx: z.number().nullish(),
  // تاریخِ کندلِ لنگر = اطلاعاتِ ساختاریِ کانال. نشانگرِ خرید اینجا نمی‌نشیند.
  floor_date: z.string().nullish(),
  // تاریخِ کندلِ تریگر (لمس + ریباند رویِ همین کندل، فقط وقتی active است) —
  // مارکرِ خرید رویِ همین می‌نشیند (#221: anchor و تریگر دو چیزند).
  trigger_date: z.string().nullish(),
  // «چرا سنجیده نشد» با تعدادِ واقعی (P0#3): سه علتِ متمایز، سه پیام.
  reason: z.string().nullish(),
});

// پولبکِ شاخۀ صعودی (چارت ص۲: صعودی ⇒ جت یا پولبک) — سطحِ آخرین سقفِ
// شکسته‌شده + لمس + بازگشت؛ سه‌حالته، بی‌عددِ ساختگی.
const Pullback = z.object({
  active: z.boolean().nullish(),
  touching: z.boolean().nullish(),
  level: z.number().nullish(),
  level_date: z.string().nullish(),
  level_age_bars: z.number().nullish(),
  weekly_confirms: z.boolean().nullish(),
  gap_pct: z.number().nullish(),
  reason: z.string().nullish(),
});

const DoubleBottom = z.object({
  active: z.boolean().nullish(),
  neckline: z.number().nullish(),
  pct_above_neck: z.number().nullish(),
  reason: z.string().nullish(),
});

const RangeBox = z.object({
  active: z.boolean().nullish(),
  top: z.number().nullish(),
  bottom: z.number().nullish(),
  // کرانۀ زمانیِ خودِ جعبه (همان ۲۰ کندلِ قاعدۀ سرور) — بی‌این باکس روی کلِ
  // دید کشیده می‌شد و extentِ واقعیِ قاعده را دروغ می‌گفت (مرحلۀ ۶).
  start_date: z.string().nullish(),
  end_date: z.string().nullish(),
  pct_above_top: z.number().nullish(),
  reason: z.string().nullish(),
});

const ExitEngine = z.object({
  verdict: z.string(),
  signals: z.array(z.string()).nullish(),
  // پرچم‌هایی که موتور نسنجد اینجا نام برده می‌شوند؛ «خروجی ندارد» با
  // «سنجیده نشد» یکی نیست (قاعدۀ null ≠ false).
  unmeasured: z.array(z.string()).nullish(),
  l1: z
    .object({
      hard_stop: z.number().nullish(),
      stop_basis: z.string().nullish(),
      // علتِ «در حال تشکیل» با تعدادِ واقعی (P0#5): کفِ ۲۰ کندلِ بسته کامل نیست.
      stop_reason: z.string().nullish(),
      stop_hit: z.boolean().nullish(),
      ma14_exit: z.boolean().nullish(),
      ma14_exit_pending: z.boolean().nullish(),
      ma14: z.number().nullish(),
      close: z.number().nullish(),
    })
    .nullish(),
  l2: z
    .object({
      choch_break: z.boolean().nullish(),
      channel_break: z.boolean().nullish(),
      level: z.number().nullish(),
      touches: z.number().nullish(),
    })
    .nullish(),
  l3: z
    .object({
      third_peak: z.boolean().nullish(),
      third_peak_level: z.number().nullish(),
      // پهنای باندِ سقفِ سوم از سرور (پارامترِ اجرایى، B4) — رابط پهناء نمی‌سازد.
      third_peak_band_pct: z.number().nullish(),
      double_top: z.boolean().nullish(),
      hs_break: z.boolean().nullish(),
      neckline: z.number().nullish(),
      level: z.number().nullish(),
      // «لایهٔ ۳ سنجیده نشد» با تعداد (P0#6) — بی‌صدا None نیست.
      reason: z.string().nullish(),
    })
    .nullish(),
  l4: z
    .object({
      rsi_divergence: z.boolean().nullish(),
      rsi_rollover: z.boolean().nullish(),
      rsi: z.number().nullish(),
      rsi_prev_peak: z.number().nullish(),
      reason: z.string().nullish(),
    })
    .nullish(),
});

const MatrixDecision = z.object({
  decision: z.string().nullish(),
  setup: z.string().nullish(),
  desc: z.string().nullish(),
  // «چرا» — مبنایِ فارسیِ رأیِ هفتگی و روزانه (کدام پیوت‌ها یا کدام بازه)
  basis: z
    .object({ weekly: z.string().nullish(), daily: z.string().nullish() })
    .nullish(),
});

const HourglassStrategy = z.object({
  active: z.boolean().nullish(),
  weekly_close: z.number().nullable().nullish(),
  ma52: z.number().nullable().nullish(),
  // تعدادِ کندلِ هفتگیِ واقعی: ma52 فقط با ۵۲ تا از این‌ها سنجیده می‌شود و
  // زیرِ آن «سنجیده نشد» است، نه میانگینِ کوتاه‌ترِ جا‌زده.
  weekly_bars: z.number().nullable().nullish(),
  weekly_rsi: z.number().nullable().nullish(),
  /** پارامترهای مؤثر ساعت‌شنی؛ برای توضیح و ممیزی تنظیمات فعال */
  rsi_period: z.number().int().nullish(),
  rsi_oversold: z.number().nullish(),
  ma52_position_mode: z.enum(["below", "above", "either"]).nullish(),
  ma52_position_match: z.boolean().nullable().nullish(),
  /** نام legacy؛ backend همین مقدار را برای سازگاری هم برمی‌گرداند. */
  weekly_rsi5: z.number().nullable().nullish(),
  // پهنای سایۀ MA52 از سرور (B4) — رابط ±۳٪ نمی‌سازد.
  ma52_band_pct: z.number().nullish(),
  action: z.string().nullish(),
  desc: z.string().nullish(),
});

// نقاطِ ساختاریِ برچسب‌دار (HH/HL/LH/LL) — زمانِ وقوع جدا از زمانِ تأیید
// (confirm_time) تا مارکرِ تاریخی به آینده نگاه نکند (ضدِ repaint، مرحلۀ ۱۰).
const StructurePoint = z.object({
  idx: z.number(),
  time: z.string(),
  confirm_idx: z.number().nullish(),
  confirm_time: z.string().nullish(),
  price: z.number(),
  kind: z.string(),
  label: z.string(),
  ref_time: z.string().nullish(),
  ref_price: z.number().nullish(),
  // درجۀبندیِ ماژور (مأموریت ۱۴۰۵-۰۷-۲۸): فهرستِ لایۀِ ساختار حالا فقط
  // Extremeهایِ ماژور است، پس رابط باید بتواند بگوید این نقطه با چه عددی ماژور
  // شمرده شده است.
  major: z.boolean().nullish(),
  leg_pct: z.number().nullish(),
  leg_atr_x: z.number().nullish(),
  recent: z.boolean().nullish(),
});

// ── پروندۀِ «چه چیزی رأی را ساخت» — کنارِ رأی، نه داخلِ آن ────────────────────
// `confirmed_trend` رأیِ داورِ System 1 رویِ ماژورهاست؛ `provisional` فقط اطلاع
// است و هیچِ کامپوننتی حق ندارد با آن جهت یا حکمِ قیف را عوض کند.
const MajorSwingPoint = z.object({
  idx: z.number(),
  time: z.string(),
  kind: z.string(),
  price: z.number(),
  confirm_idx: z.number().nullish(),
  confirm_time: z.string().nullish(),
  confirm_age_bars: z.number().nullish(),
  leg_pct: z.number().nullish(),
  leg_pct_in: z.number().nullish(),
  leg_pct_out: z.number().nullish(),
  out_pending: z.boolean().nullish(),
  leg_atr_x: z.number().nullish(),
  recent: z.boolean().nullish(),
  ma100_ctx: z.string().nullish(),
});

const ProvisionalLeg = z.object({
  idx: z.number(),
  time: z.string(),
  price: z.number().nullish(),
  provisional: z.boolean().nullish(),
  confirmed: z.boolean().nullish(),
  bars_since: z.number().nullish(),
  bars_to_confirm: z.number().nullish(),
});

const MajorContext = z.object({
  timeframe: z.string().nullish(),
  confirmed_trend: z.string().nullish(),
  verdict_basis: z.string().nullish(),
  /** آخرینِ کندلِ **بستهٔ** همان سری — مبنایِ «قطعی بودن»ِ رأی */
  as_of: z.string().nullish(),
  daily_as_of: z.string().nullish(),
  bars: z.number().nullish(),
  /** سبدِ هفتگی/ماهانۀِ آخر هنوز کندلِ روزانۀِ جدید می‌گیرد (اطلاع، نه رأی) */
  bucket_forming: z.boolean().nullish(),
  major_swings: z.array(MajorSwingPoint).nullish(),
  counts: z
    .object({
      pivots: z.number().nullish(),
      majors: z.number().nullish(),
      major_highs: z.number().nullish(),
      major_lows: z.number().nullish(),
      minor_highs: z.number().nullish(),
      minor_lows: z.number().nullish(),
      undecided: z.number().nullish(),
      dropped_minor: z.number().nullish(),
    })
    .nullish(),
  threshold: z.object({ atr_x: z.number().nullish(), floor_pct: z.number().nullish() }).nullish(),
  enough_extremes: z.boolean().nullish(),
  provisional: z
    .object({
      since_pivot_time: z.string().nullish(),
      bars_since_last_pivot: z.number().nullish(),
      high: ProvisionalLeg.nullish(),
      low: ProvisionalLeg.nullish(),
      note: z.string().nullish(),
    })
    .nullish(),
  reason: z.string().nullish(),
});

// وضعیتِ عمومیِ canonical و جدولِ نقش‌ها — تنها منبعِ متنِ «وضعیت FTS» و تنها
// مرجعِ «این پرچم تریگر است یا زمینه یا هشدار یا خروج».
const StatusTrigger = z.object({
  kind: z.string(),
  price: z.number().nullish(),
  date: z.string().nullish(),
  label: z.string().nullish(),
  role: z.string().nullish(),
});

const FtsStatus = z.object({
  code: z.string(),
  text: z.string(),
  trigger: StatusTrigger.nullable().nullish(),
  exits: z.array(z.string()).nullish(),
  warnings: z.array(z.string()).nullish(),
  unknown: z.array(z.string()).nullish(),
  vetoed: z.boolean().nullish(),
  context_only: z.boolean().nullish(),
  priority: z.array(z.string()).nullish(),
  roles: z.record(z.string(), z.string()).nullish(),
});

export const FtsAnalysis = z.object({
  trend: z
    .object({
      D: TrendLeg.nullish(),
      W: TrendLeg.nullish(),
      M: TrendLeg.nullish(),
      alignment: z.string().nullish(),
      matrix: MatrixDecision.nullish(),
      // مبنایِ زمانیِ رأی: آخرینِ کندلِ بستهٔ روزانۀِ ساختار (کندلِ تکمیل‌نشده
      // درِ ساختارِ جهت نیست، فقط زیرِ `provisional` گزارش می‌شود).
      as_of: z.string().nullish(),
      major_swings: z
        .object({
          D: MajorContext.nullish(),
          W: MajorContext.nullish(),
          M: MajorContext.nullish(),
        })
        .nullish(),
    })
    .nullish(),
  fib: Fib,
  jet: Jet.nullish(),
  choch: Choch.nullish(),
  point_hunt: PointHunt.nullish(),
  pullback: Pullback.nullish(),
  double_bottom: DoubleBottom.nullish(),
  range_box: RangeBox.nullish(),
  exit_engine: ExitEngine.nullish(),
  hourglass: HourglassStrategy.nullish(),
  setups: z.array(Setup).nullish(),
  // فهرستِ خالی زیرِ کفِ تاریخچه «۰ ستاپ» نیست (P0#11)؛ رابط این را می‌خواند.
  setups_state: z.string().nullish(),
  setups_bars_available: z.number().nullish(),
  setups_bars_required: z.number().nullish(),
  // نقاطِ ساختاریِ HH/HL/LH/LL — لایۀ «ساختار روند» (روزانه مرجع، هفتگی زمینه).
  structure_points: z
    .object({
      D: z.array(StructurePoint).nullish(),
      W: z.array(StructurePoint).nullish(),
    })
    .nullish(),
  status: FtsStatus.nullish(),
  roles: z.record(z.string(), z.string()).nullish(),
});

export type FtsAnalysisData = z.infer<typeof FtsAnalysis>;

const FtsResponse = z.object({
  status: z.string(),
  symbol: z.string().nullish(),
  fts: FtsAnalysis.nullish(),
  // «از کجا حساب شد» و «روی چند نشست» — بی‌این دو خطِ «مبنا» در کارت نمی‌آید
  // و واگراییِ سریِ محلی با CDN بی‌صدا می‌ماند.
  analysis_basis: z.string().nullish(),
  bars: z.number().nullish(),
  // لنگرِ نمایش: آخرین بستۀ سریِ تحلیلِ سرور. موتور دوم (FFC) بی‌این عدد
  // نمی‌تواند قیمتِ سرور را به فضایِ کندلِ رسم‌شده ببرد (B5).
  ref_close: z.number().nullish(),
  // فقط در status === 'error' پر می‌شود؛ قبلاً دور ریخته می‌شد و نشان‌ها
  // تا ابد «در حال دریافت…» می‌ماندند.
  message: z.string().nullish(),
});

export type FtsResponseData = z.infer<typeof FtsResponse>;

export function useFtsAnalysis(symbol: string) {
  return useQuery({
    queryKey: ['fts-analysis', symbol],
    queryFn: ({ signal }) =>
      http<z.infer<typeof FtsResponse>>(`/api/fts/${encodeURIComponent(symbol)}`, {
        schema: FtsResponse,
        signal,
      }),
    enabled: symbol.length > 0,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
