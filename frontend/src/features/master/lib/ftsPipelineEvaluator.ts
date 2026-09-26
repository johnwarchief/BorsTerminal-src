// features/master/lib/ftsPipelineEvaluator.ts -- ارزیابی خط لولهٔ ۴ مرحله‌ای FTS
// بر مبنای جزوه دوره نوسان‌گیری و سرمایه‌گذاری به سبک FTS (عرفان نصرتی) و چارت‌های درختی
// گام ۱ (تابلو و انتخاب S) → گام ۲ (تکنیکال ۲ زمانه T) → گام ۳ (بنیادی ۵ شاخصه F) → گام ۴ (مدیریت سرمایه و پلن معامله)
import { toFaDigits } from '@shared/lib/fmt';
import { ftsScoreOf } from '@contracts/fundamental';
import type { BusInput } from './masterMath';
import {
  type StrictGatesResult,
  type DefiniteDecision,
  isSuperFundamental,
  hasDirectEntrySetup,
} from './strictGates';

export type StrategyHorizon = 'swing' | 'trend' | 'hourglass';

export const HORIZON_LABELS: Record<StrategyHorizon, { title: string; desc: string; badge: string }> = {
  swing: {
    title: 'شخص نوسان‌گیر (معاملات ۱ تا ۲ ماه / زیر ۳ ماه)',
    desc: 'ورود بر اساس ستاپ جت یا تراز ۳۳ تا ۴۰ فیبوناچی؛ حد ضرر صلب تکنیکالی: ۵٪ زیر نقطه ورود یا تشکیل کندل کامل زیر MA-14',
    badge: 'نوسان‌گیری سریع',
  },
  trend: {
    title: 'شخص روندگیر (سرمایه‌گذاری بالای ۳ ماه)',
    desc: 'خرید پله‌ای در تراز ۳۳-۴۰ و ۶۱.۸-۷۰ فیبو، تایید ۵ شاخص بنیادی و هفتگی صعودی؛ حد ضرر تکنیکالی ندارد بلکه حد ضرر بنیادی در کدال است',
    badge: 'سهامداری روندی',
  },
  hourglass: {
    title: 'استراتژی ساعت شنی (سرمایه‌گذاری ۳ تا ۱۰ ساله)',
    desc: 'مخصوص سهام بزرگ و بنیادی (شاخص‌سازها) در تایم هفتگی زیر MA-52 و اشباع فروش عمیق RSI زیر ۷؛ اهرم خرید ۲ تا ۴ برابری',
    badge: 'افق بلندمدت FTS',
  },
};

export type PipelineStepStatus = 'pass' | 'fail' | 'wait';

export type PipelineStep = {
  step: 1 | 2 | 3 | 4;
  id: 'tape' | 'technical' | 'fundamental' | 'master';
  title: string;
  status: PipelineStepStatus;
  headline: string;
  detail: string;
  targetRoute: string;
  evidence: string[];
};

export type MarketScenarioItem = {
  title: string;
  probabilityPct: number;
  trigger: string;
  targetOrStop: string;
  action: string;
  badge: string;
};

export type MarketScenarios = {
  bullish: MarketScenarioItem;
  neutral: MarketScenarioItem;
  bearish: MarketScenarioItem;
};

export type LiquidityAssessment = {
  status: 'safe' | 'warning' | 'danger';
  headline: string;
  detail: string;
  clockPattern: boolean;
  clockDiffPct: number | null;
  volRatio: number | null;
  buyerPower: number | null;
  queueStatus: 'buy_queue' | 'sell_queue' | 'balanced';
  queueNote: string;
  actionAdvice: string;
};

export type NarrativeReport = {
  /** چرا بخریم یا نخریم؟ (حکم قطعی بر مبنای فیلترهای ۳گانه FTS) */
  why: string;
  /** وضعیت ستاپ تکنیکال ۲ زمانه (هفتگی ماژور + روزانه مینور و ستاپ‌ها) */
  technical: string;
  /** صورت‌های مالی کدال و ۵ شاخص بنیادی FTS */
  fundamental: string;
  /** برنامه ورود، حد ضرر نوسان‌گیر/روندگیر و مدیریت سرمایه */
  tradePlan: string;
  /** سناریوهای ۳گانه بازار بر مبنای FTS (صعودی جت/فیبو، رنج در باکس، نزولی و حد ابطال) */
  scenarios: MarketScenarios;
  /** تحلیل نقدشوندگی، تابلوی بازار، صفوف و الگوی ساعت */
  liquidity: LiquidityAssessment;
  /** شرط شفاف فعال‌سازی ورود یا رفع ریجکت/وتو */
  readinessCondition: string;
  /** توصیه اختصاصی بر اساس دیدگاه معامله‌گر (نوسان‌گیر vs روندگیر vs ساعت شنی) */
  traderAdvice: string;
};

export type PipelineEvaluation = {
  symbol: string;
  horizon: StrategyHorizon;
  recommendedHorizon: StrategyHorizon;
  steps: [PipelineStep, PipelineStep, PipelineStep, PipelineStep];
  overallStatus: PipelineStepStatus;
  overallHeadline: string;
  score: number | null;
  tradePlan: {
    entryPrice: number | null;
    stopLossPrice: number | null;
    stopLossBasis: string;
    stopLossPct: number | null;
    targetPrice: number | null;
    targetLabel: string;
    halfExitPrice: number | null;
    halfExitLabel: string;
    weightPct: number;
  };
  narrative: NarrativeReport;
};

function numFa(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return toFaDigits(Number(n.toFixed(digits)));
}

/**
 * پیشنهاد خودکار افق بر اساس منطق جزوه FTS:
 * - ساعت شنی (۳ تا ۱۰ ساله): صرفاً برای نمادهای بزرگ و سوپربنیادی در کف تاریخی
 * - شخص روندگیر (بالای ۳ ماه): تایید ۵ شاخص بنیادی (امتیاز بنیادی ≥ ۴ از ۵) و روند هفتگی صعودی
 * - شخص نوسان‌گیر (زیر ۳ ماه): وجود ستاپ مستقیم ورود (جت، فیبو ۳۳-۴۰، یا کف دوقلو)
 */
export function recommendHorizon(
  fundScore: number | null,
  isSuper: boolean,
  hasSetup = false,
): StrategyHorizon {
  if (isSuper) return 'hourglass';
  if (hasSetup) return 'swing';
  if (fundScore != null && fundScore >= 4) return 'trend';
  return 'swing';
}

function cleanVetoReason(reason: string): string {
  if (!reason) return 'توقف به دلیل عدم شفافیت گزارش بنیادی در کدال یا روند هفتگی نزولی';
  return reason
    .replace(/فیلترهای ۳گانه FTS/g, 'فیلترهای FTS')
    .replace(/گیت‌های سخت‌گیرانه/g, 'فیلترهای FTS')
    .replace(/گیت‌های/g, 'فیلترهای')
    .replace(/گیت ۱/g, 'فیلتر بنیاد')
    .replace(/گیت ۲/g, 'فیلتر تکنیکال')
    .replace(/گیت ۳/g, 'فیلتر تابلو')
    .replace(/گیت ۴/g, 'فیلتر سبد و ریسک')
    .replace(/گیت/g, 'فیلتر')
    .replace(/لایه‌ها/g, 'فیلترهای FTS')
    .replace(/لایه/g, 'فیلتر')
    .replace(/^[:\s.-]+|[:\s.-]+$/g, '')
    .trim();
}

/** ارزیابی کامل زنجیره FTS برای نماد مشخص بر پایه مفاهیم جزوه نصرتی */
export function evaluateFtsPipeline(args: {
  symbol: string;
  horizon?: StrategyHorizon;
  inputs: BusInput;
  strict: StrictGatesResult;
  decision: DefiniteDecision;
  currentPrice?: number | null;
  resistancePrice?: number | null;
  supportPrice?: number | null;
  fundScore?: number | null;
  realYearsEps?: number | null;
  salesGrowthPct?: number | null;
  grossMarginPct?: number | null;
}): PipelineEvaluation {
  const {
    symbol,
    inputs,
    strict,
    decision,
    salesGrowthPct = null,
    grossMarginPct = null,
  } = args;

  // امتیاز ۰ تا ۵ شمار شاخص‌های بنیادی (payload.score) — نه نمره ۰ تا ۱۰۰ اعتماد ترکیبی.
  const fundScore = args.fundScore ?? ftsScoreOf(inputs.fundamental);

  const superFund = isSuperFundamental(inputs.fundamental);
  const hasSetup = hasDirectEntrySetup(inputs.technical);

  const recommendedHorizon = recommendHorizon(fundScore, superFund, hasSetup);
  const horizon = args.horizon ?? recommendedHorizon;

  // ──────────────────────────────────────────────────────────
  // استخراج داده‌ها و سطوح کلیدی (فیبوناچی، مقاومت استاتیک، کف حمایتی)
  // ──────────────────────────────────────────────────────────
  const tapeSig = inputs.tape;
  const tapePayload = (tapeSig?.payload ?? {}) as Record<string, unknown>;
  const techSig = inputs.technical;
  const techPayload = (techSig?.payload ?? {}) as Record<string, unknown>;
  const fundSig = inputs.fundamental;
  const fundPayload = (fundSig?.payload ?? {}) as Record<string, unknown>;

  const currentPrice =
    args.currentPrice ??
    (typeof tapePayload.p_last === 'number' && tapePayload.p_last > 0 ? tapePayload.p_last : null) ??
    (typeof tapePayload.p_closing === 'number' && tapePayload.p_closing > 0 ? tapePayload.p_closing : null) ??
    (typeof techPayload.close === 'number' && techPayload.close > 0 ? techPayload.close : null) ??
    null;

  const closingPrice =
    (typeof tapePayload.p_closing === 'number' && tapePayload.p_closing > 0 ? tapePayload.p_closing : null) ??
    currentPrice;

  const lastPrice =
    (typeof tapePayload.p_last === 'number' && tapePayload.p_last > 0 ? tapePayload.p_last : null) ??
    currentPrice;

  // مقاومت استاتیک طبق ستاپ جت یا سقف قبلی
  const resistancePrice =
    args.resistancePrice ??
    (typeof techPayload.resistance === 'number' && techPayload.resistance > 0 ? techPayload.resistance : null) ??
    (currentPrice ? Math.round(currentPrice * 1.15) : null);

  // کف حمایتی یا تراز ۳۳ تا ۴۰ فیبوناچی
  const supportPrice =
    args.supportPrice ??
    (typeof techPayload.support === 'number' && techPayload.support > 0 ? techPayload.support : null) ??
    (currentPrice ? Math.round(currentPrice * 0.95) : null);

  const supportStr = supportPrice
    ? `${toFaDigits(supportPrice)} ریال`
    : currentPrice
      ? `${toFaDigits(Math.round(currentPrice * 0.95))} ریال`
      : 'کف حمایتی (تراز ۳۳-۴۰ فیبو)';

  const resistanceStr = resistancePrice
    ? `${toFaDigits(resistancePrice)} ریال`
    : currentPrice
      ? `${toFaDigits(Math.round(currentPrice * 1.15))} ریال`
      : 'سقف مقاومت استاتیک';

  // ──────────────────────────────────────────────────────────
  // گام ۱: تابلوخوانی و غربالگری (S: Selection)
  // ──────────────────────────────────────────────────────────
  // الگوی ساعت: قیمت آخرین معامله بیش از ۱٪ بزرگتر از قیمت پایانی باشد
  const clockDiffPct =
    lastPrice != null && closingPrice != null && closingPrice > 0
      ? ((lastPrice - closingPrice) / closingPrice) * 100
      : null;

  const clockPattern = Boolean(
    tapePayload.clock_pattern ??
    tapePayload.f_clock ??
    (clockDiffPct != null && clockDiffPct >= 1.0)
  );

  // حجم مشکوک: بررسی حداقل ۳ برابر میانگین ماهانه (۲۱ روزه)
  const volRatio = typeof tapePayload.vol_ratio === 'number'
    ? tapePayload.vol_ratio
    : (tapePayload.vol_multiple as number) ?? null;

  const isSuspiciousVol = volRatio != null && volRatio >= 3.0;
  const buyerPower = typeof tapePayload.buyer_power === 'number' ? tapePayload.buyer_power : null;
  const isFloorSweep = Boolean(tapePayload.floor_sweep ?? tapePayload.kef_roobi);

  // تشخیص وضعیت صف‌ها
  const queueStatus: 'buy_queue' | 'sell_queue' | 'balanced' =
    tapePayload.is_sell_queue
      ? 'sell_queue'
      : tapePayload.is_buy_queue
        ? 'buy_queue'
        : 'balanced';

  let tapeStatus: PipelineStepStatus = 'wait';
  let tapeHeadline = 'تابلو در انتظار تایید زمان‌سنج ورود';
  let tapeDetail = 'سیگنال تابلویی قوی (الگوی ساعت یا حجم مشکوک ۳ برابری) در معاملات امروز ثبت نشده است.';
  const tapeEvidence: string[] = [];

  if (clockPattern) {
    tapeStatus = 'pass';
    tapeHeadline = 'الگوی ساعت فعال (آخرین معامله بیش از ۱٪ بالاتر از پایانی)';
    tapeDetail = 'طبق جزوه FTS، قیمت آخرین معامله از پایانی سبقت گرفته است؛ به احتمال زیاد فردا سهم مثبت باز می‌شود.';
    tapeEvidence.push(clockDiffPct != null ? `الگوی ساعت (+${numFa(clockDiffPct, 1)}٪)` : 'الگوی ساعت مثبت');
  } else if (isSuspiciousVol) {
    tapeStatus = 'pass';
    tapeHeadline = `حجم مشکوک پرقدرت (${numFa(volRatio, 1)} برابر میانگین ماهانه)`;
    tapeDetail = 'حجم معاملات به بیش از ۳ برابر میانگین ۲۱ روزه رسیده و نشان‌دهنده دست‌به‌دست شدن سهم است.';
    tapeEvidence.push(`حجم مشکوک ${numFa(volRatio, 1)}×`);
  } else if (isFloorSweep) {
    tapeStatus = 'pass';
    tapeHeadline = 'الگوی کف‌روبی صف فروش';
    tapeDetail = 'سهم صف فروش بوده اما سفارش‌های خرید قوی در حال بلعیدن و جمع کردن صف هستند.';
    tapeEvidence.push('کف‌روبی صف فروش');
  } else if (tapeSig?.direction === 'bullish') {
    tapeStatus = 'pass';
    tapeHeadline = 'جریان نقدینگی و ورود پول مثبت';
    tapeDetail = 'برآیند سرانه خریداران و ورود پول به نماد مثبت ارزیابی شده است.';
    tapeEvidence.push('ورود پول مثبت');
  } else if (tapeSig?.direction === 'bearish') {
    tapeStatus = 'fail';
    tapeHeadline = 'فشار فروش یا خروج پول حقیقی';
    tapeDetail = 'برتری با فروشندگان است یا صف فروش بدون خریدار قوی مشاهده می‌شود.';
    tapeEvidence.push('تراز منفی تابلو');
  } else {
    tapeStatus = 'wait';
    tapeEvidence.push('بدون الگوی ساعت یا حجم مشکوک');
  }

  if (buyerPower != null) {
    tapeEvidence.push(`قدرت خریدار: ${numFa(buyerPower, 2)}`);
  }

  const step1: PipelineStep = {
    step: 1,
    id: 'tape',
    title: 'تابلوخوانی و زمان‌سنج ورود (S)',
    status: tapeStatus,
    headline: tapeHeadline,
    detail: tapeDetail,
    targetRoute: '/market',
    evidence: tapeEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۲: تحلیل تکنیکال دو زمانه FTS (T: Technical)
  // تایم هفتگی (ماژور) + تایم روزانه (مینور)
  // ──────────────────────────────────────────────────────────
  const weekly = strict.weekly;
  const weeklyUptrend = weekly.uptrend ?? (techPayload.weekly_uptrend as boolean) ?? null;
  const jetActive = Boolean(techPayload.jet_active ?? (techPayload.jet as Record<string, unknown> | undefined)?.active);
  const chochBullish = Boolean(techPayload.choch_bullish ?? (techPayload.choch as Record<string, unknown> | undefined)?.bullish);
  const pointHuntActive = Boolean(techPayload.point_hunt_active ?? (techPayload.point_hunt as Record<string, unknown> | undefined)?.active);
  const doubleBottomActive = Boolean(techPayload.double_bottom_active ?? (techPayload.double_bottom as Record<string, unknown> | undefined)?.active);

  let techStatus: PipelineStepStatus = 'wait';
  let techHeadline = 'ساختار تکنیکال در انتظار ستاپ معتبر';
  let techDetail = 'روند یا ستاپ معتبری هنوز تایید قطعی دریافت نکرده است.';
  const techEvidence: string[] = [];

  // قانون صلب جزوه صفحه ۲ و ۷: تایم هفتگی نزولی یا خنثی = Reject قطعی
  if (weeklyUptrend === false && horizon !== 'hourglass') {
    techStatus = 'fail';
    techHeadline = 'ریجکت هفتگی (وتوی ماژور هفتگی: روند هفتگی نزولی یا خنثی است)';
    techDetail = 'طبق چارت درختی جزوه FTS، شرط اول تکنیکال روند صعودی تایم هفتگی است؛ روند نزولی یا خنثی هفتگی ریجکت (Reject) قطعی است.';
    techEvidence.push('ریجکت روند هفتگی (وتوی ماژور)');
  } else if (jetActive) {
    techStatus = 'pass';
    techHeadline = 'ستاپ جت فعال (استراتژی جت: عبور از سقف تاریخی یا مقاومت استاتیک)';
    techDetail = 'قیمت با کندل پرقدرت مقاومت استاتیک را شکسته است؛ طبق جزوه تا ۳ روز کاری بعد از تثبیت فرصت ورود وجود دارد.';
    techEvidence.push('ستاپ جت FTS');
  } else if (chochBullish) {
    techStatus = 'pass';
    techHeadline = 'تغییر ساختار CHoCH صعودی';
    techDetail = 'آخرین سقف در روند نزولی شکسته شده و اولین نشانه تغییر روند به سمت صعودی شکل گرفته است.';
    techEvidence.push('تغییر ساختار CHoCH');
  } else if (pointHuntActive) {
    techStatus = 'pass';
    techHeadline = 'استراتژی نقطه‌زنی (برخورد به کف سوم یا پنجم)';
    techDetail = 'واکنش حمایتی روی کف کانال یا خط روند با حد ضرر بسیار کوتاه ثبت شده است.';
    techEvidence.push('نقطه‌زنی در کف');
  } else if (doubleBottomActive) {
    techStatus = 'pass';
    techHeadline = 'ستاپ کف دوقلو با شکست خط گردن';
    techDetail = 'آخرین سقف رو به بالا شکسته شده و الگوی بازگشتی کف دوقلو تایید گردید.';
    techEvidence.push('کف دوقلو');
  } else if (techSig?.direction === 'bullish') {
    techStatus = 'pass';
    techHeadline = 'روند روزانه صعودی و تایید ستاپ پولبک';
    techDetail = 'کندل‌ها بالاتر از میانگین متحرک تثبیت شده‌اند و واکنش به تراز ۳۳-۴۰ فیبو مثبت است.';
    techEvidence.push('روند صعودی');
  } else if (weeklyUptrend === true) {
    techStatus = 'wait';
    techHeadline = 'تایم هفتگی صعودی؛ در انتظار ستاپ ورود روزانه';
    techDetail = 'روند کلان سهم صعودی است؛ باید منتظر پولبک به تراز ۳۳ تا ۴۰ فیبوناچی یا شکست مقاومت استاتیک (ستاپ جت) ماند.';
    techEvidence.push('هفتگی صعودی');
  }

  const step2: PipelineStep = {
    step: 2,
    id: 'technical',
    title: 'تکنیکال ۲ زمانه FTS (T)',
    status: techStatus,
    headline: techHeadline,
    detail: techDetail,
    targetRoute: '/technical',
    evidence: techEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۳: سلامت ۵ شاخص بنیادی (F: Fundamental)
  // ۱) فروش ماهانه ۲) سودآوری ۳ ساله ۳) حاشیه سود بالای ۲۰-۳۰٪ ۴) فروش به ارزش بازار ۵) چشم‌انداز صنعت
  // ──────────────────────────────────────────────────────────
  const excluded = Boolean(fundPayload.excluded ?? (fundSig as Record<string, unknown> | undefined)?.excluded);
  const exclusionReasons = Array.isArray(fundPayload.exclusion_reasons)
    ? (fundPayload.exclusion_reasons as string[])
    : [];

  let fundStatus: PipelineStepStatus = 'wait';
  let fundHeadline = 'بررسی ۵ شاخص بنیادی در دست ارزیابی';
  let fundDetail = 'گزارش‌های فعالیت ماهانه و صورت‌های مالی کدال فراخوانی نشده است.';
  const fundEvidence: string[] = [];

  if (excluded) {
    fundStatus = 'fail';
    fundHeadline = 'توقف به دلیل نرخ‌گذاری دستوری شدید یا ابهام در صورت‌های مالی';
    fundDetail = `علت: ${cleanVetoReason(exclusionReasons.join(' · ') || 'صنعت مشمول نرخ‌گذاری دستوری شدید یا نماد متوقف است')}`;
    fundEvidence.push('رد در فیلتر بنیادی');
  } else if (fundScore != null) {
    if (fundScore >= 4) {
      fundStatus = 'pass';
      fundHeadline = fundScore === 5 ? '💎 نماد سوپربنیادی FTS (تایید هر ۵ شاخص)' : 'بنیاد ممتاز (تایید ۴ شاخص از ۵ شاخص FTS)';
      fundDetail = 'شرکت رشد فروش ماهانه بالای ۴۰٪، سودآوری ۳ ساله صعودی و حاشیه سود ناخالص مطلوب ثبت کرده است.';
      fundEvidence.push(`امتیاز ${toFaDigits(fundScore)} از ۵`);
    } else if (fundScore >= 3) {
      fundStatus = horizon === 'swing' ? 'pass' : 'wait';
      fundHeadline = 'بنیاد متوسط (تایید ۳ شاخص از ۵ شاخص FTS)';
      fundDetail = 'برای نوسان‌گیری سبک با ستاپ جت قابل قبول است، اما برای روندگیری بلندمدت یا ساعت شنی تایید کامل ندارد.';
      fundEvidence.push(`امتیاز ${toFaDigits(fundScore)} از ۵`);
    } else {
      fundStatus = 'fail';
      fundHeadline = `رد در فیلتر بنیادی (امتیاز ${toFaDigits(fundScore)} از ۵)`;
      fundDetail = 'شرکت معیارهای رشد فروش سالانه یا حاشیه سود بالای ۲۰٪ را تامین نکرده است.';
      fundEvidence.push(`امتیاز ضعیف ${toFaDigits(fundScore)}`);
    }
  }

  if (salesGrowthPct != null) {
    fundEvidence.push(`رشد فروش: ${numFa(salesGrowthPct, 0)}٪`);
  }
  if (grossMarginPct != null) {
    fundEvidence.push(`حاشیه سود: ${numFa(grossMarginPct, 1)}٪`);
  }

  const step3: PipelineStep = {
    step: 3,
    id: 'fundamental',
    title: 'سلامت ۵ شاخص بنیادی (F)',
    status: fundStatus,
    headline: fundHeadline,
    detail: fundDetail,
    targetRoute: '/fundamental',
    evidence: fundEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۴: مدیریت سرمایه و برنامه معامله (Trade Plan & Capital)
  // تفکیک نوسان‌گیر (استاپ ۵٪ یا MA-14) از روندگیر (حد ضرر بنیادی در کدال)
  // ──────────────────────────────────────────────────────────
  let masterStatus: PipelineStepStatus = 'wait';
  let masterHeadline = 'در انتظار تایید نهایی ارکان FTS';
  let masterDetail = 'برای صدور مجوز ورود پله‌ای، نیازمند تایید هم‌زمان تابلو، چارت و بنیاد هستیم.';

  // محاسبه حد ضرر دقیق
  let stopLossPrice: number = 0;
  let stopLossBasis = '';
  let stopLossPct: number = 5.0;

  if (currentPrice != null && currentPrice > 0) {
    if (horizon === 'swing') {
      stopLossPrice = Math.round(currentPrice * 0.95);
      stopLossPct = 5.0;
      stopLossBasis = `حد ضرر قطعی نوسان‌گیر: ${toFaDigits(stopLossPrice)} ریال (-۵٪ زیر ورود یا کندل زیر MA-14)`;
    } else if (horizon === 'trend') {
      stopLossPrice = supportPrice != null ? Math.round(supportPrice * 0.95) : Math.round(currentPrice * 0.92);
      stopLossPct = Math.round(((currentPrice - stopLossPrice) / currentPrice) * 1000) / 10;
      stopLossBasis = `حد ضرر قطعی کف حمایتی: ${toFaDigits(stopLossPrice)} ریال (حد ضرر روندگیر: گزارش فصلی کدال)`;
    } else {
      stopLossPrice = Math.round(currentPrice * 0.85);
      stopLossPct = 15.0;
      stopLossBasis = `حد ضرر قطعی ساعت شنی: ${toFaDigits(stopLossPrice)} ریال (-۱۵٪ در اشباع عمیق)`;
    }
  } else {
    stopLossPrice = 10000;
    stopLossPct = 5.0;
    stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`;
  }

  // هدف قیمتی و مقاومت استاتیک
  let targetPrice: number = 0;
  const targetLabel = 'مقاومت استاتیک اول (ذخیره سود ۵۰٪)';

  if (resistancePrice != null && resistancePrice > 0) {
    targetPrice = resistancePrice;
  } else if (currentPrice != null && currentPrice > 0) {
    targetPrice =
      horizon === 'swing'
        ? Math.round(currentPrice * 1.15)
        : horizon === 'trend'
          ? Math.round(currentPrice * 1.25)
          : Math.round(currentPrice * 1.6);
  } else {
    targetPrice = Math.round(stopLossPrice * 1.25);
  }

  const halfExitPrice: number = resistancePrice ?? Math.round(targetPrice * 0.95);
  const halfExitLabel = 'ذخیره سود ۵۰٪ در مقاومت استاتیک جهت خروج اصل سرمایه';
  const weightPct = horizon === 'swing' ? 3.5 : horizon === 'trend' ? 5.0 : 10.0;

  if (decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2') {
    masterStatus = 'fail';
    masterHeadline = '⛔ ورود ممنوع (توقف در فیلترهای FTS)';
    masterDetail = cleanVetoReason(decision.reason || 'توقف به دلیل ریجکت هفتگی یا عدم احراز شرایط ۵ شاخص بنیادی');
  } else if (decision.action === 'ladder_buy') {
    masterStatus = 'pass';
    masterHeadline = '🎯 خرید پله‌ای مجاز (هم‌پوشانی کامل ۳ رکن FTS)';
    masterDetail = `همگرایی کامل تابلو (S)، تکنیکال ۲ زمانه (T) و بنیاد (F) برای ${HORIZON_LABELS[horizon].badge} حاصل شده است.`;
  } else if (decision.action === 'high_risk_swing') {
    masterStatus = horizon === 'swing' ? 'pass' : 'wait';
    masterHeadline = '⚡ نوسان‌گیری با حجم سبک مجاز';
    masterDetail = 'ورود روندی مسدود است اما ستاپ نوسانی با حد ضرر صلب ۵٪ (یا کندل زیر MA-14) تایید شده است.';
  } else {
    masterStatus = 'wait';
    masterHeadline = '⏳ تحت نظر و پایش (در انتظار تایید تابلو)';
    masterDetail = 'سهم مستعد است اما ورود تا زمان تایید الگوی ساعت یا شکست پرحجم مقاومت به تعویق می‌افتد.';
  }

  const step4: PipelineStep = {
    step: 4,
    id: 'master',
    title: 'مدیریت سرمایه و پلن ورود FTS',
    status: masterStatus,
    headline: masterHeadline,
    detail: masterDetail,
    targetRoute: '/master',
    evidence: [
      `افق: ${HORIZON_LABELS[horizon].badge}`,
      `حد ضرر: ${toFaDigits(stopLossPrice)} ریال`,
      `هدف اول: ${toFaDigits(targetPrice)} ریال`,
    ],
  };

  // ──────────────────────────────────────────────────────────
  // سناریوهای ۳گانه بازار بر مبنای منطق جزوه FTS
  // ──────────────────────────────────────────────────────────
  let bullishProb = 35;
  let neutralProb = 45;
  let bearishProb = 20;

  if (decision.action === 'ladder_buy') {
    bullishProb = 70;
    neutralProb = 20;
    bearishProb = 10;
  } else if (decision.action === 'veto' || weeklyUptrend === false) {
    bullishProb = 15;
    neutralProb = 35;
    bearishProb = 50;
  } else if (decision.action === 'high_risk_swing') {
    bullishProb = 45;
    neutralProb = 30;
    bearishProb = 25;
  } else if (fundStatus === 'pass' && techStatus === 'pass') {
    bullishProb = 55;
    neutralProb = 30;
    bearishProb = 15;
  }

  const scenarios: MarketScenarios = {
    bullish: {
      title: jetActive
        ? 'سناریوی صعودی: پرتاب ستاپ جت به سوی سقف تاریخی'
        : 'سناریوی صعودی: حرکت از تراز فیبو به سوی مقاومت اول',
      probabilityPct: bullishProb,
      trigger: `شکست و تثبیت قیمت بالای مقاومت استاتیک ${resistanceStr} همگام با تایید الگوی ساعت یا حجم مشکوک ۳ برابری.`,
      targetOrStop: `هدف اول: ${toFaDigits(targetPrice)} ریال · طبق قانون FTS ذخیره سود ۵۰٪ جهت خروج اصل سرمایه و نگهداری سود باقیمانده.`,
      action: jetActive
        ? 'تا ۳ روز کاری بعد از کندل تثبیت مقاومت، فرصت ورود پله‌ای وجود دارد.'
        : 'خرید پله اول در تراز ۳۳ تا ۴۰ فیبوناچی و تکمیل پله دوم در صورت پولبک.',
      badge: 'صعودی (جت/فیبو)',
    },
    neutral: {
      title: 'سناریوی رنج: درجا زدن در باکس رنج یا کانال نوسانی',
      probabilityPct: neutralProb,
      trigger: `نوسان قیمت بین کف حمایتی ${supportStr} تا سقف مقاومت ${resistanceStr} با کاهش حجم معاملات.`,
      targetOrStop: `کف باکس: ${supportStr} برای خرید نوسانی · سقف باکس: ${resistanceStr} برای فروش و خروج.`,
      action: 'پرهیز از خرید در میانه باکس؛ صبر برای خروج پول از صندوق‌های درآمد ثابت و شکست سقف باکس رنج با کندل پرقدرت.',
      badge: 'رنج / باکس',
    },
    bearish: {
      title: 'سناریوی نزولی: شکست کف حمایتی و فعال شدن حد ضرر',
      probabilityPct: bearishProb,
      trigger: `از دست رفتن سطح حمایتی ${supportStr} یا افت ۵٪ زیر نقطه ورود.`,
      targetOrStop:
        horizon === 'swing'
          ? `حد ضرر نوسان‌گیر: ${toFaDigits(stopLossPrice)} ریال (-۵٪ یا تشکیل کندل کامل زیر MA-14)`
          : `حد ضرر روندگیر: توقف رشد فروش ماهانه در کدال یا افت حاشیه سود به زیر ۲۰٪ (حد ضرر نوسان‌گیر: تشکیل کندل کامل زیر MA-14)`,
      action:
        horizon === 'swing'
          ? 'خروج بی‌چون‌وچرا با قبول ضرر جزئی جهت حفظ اصل سرمایه.'
          : 'بررسی صورت مالی میان‌دوره‌ای؛ در صورت افت سودآوری، تعویض سهم با نماد بنیادی دیگر.',
      badge: 'ابطال ستاپ',
    },
  };

  // ──────────────────────────────────────────────────────────
  // تحلیل نقدشوندگی، صفوف و تابلوی بازار
  // ──────────────────────────────────────────────────────────
  let liqStatus: 'safe' | 'warning' | 'danger' = 'safe';
  let liqHeadline = 'جریان معاملات روان و نقدشوندگی مناسب';
  let liqDetail = 'معاملات سهم به صورت پیوسته انجام می‌شود و ریسک قفل شدن سرمایه در صفوف اندک است.';
  let queueNote = 'سفارشات خرید و فروش در تعادل نسبی قرار دارند.';
  let liqAdvice = 'ورود پله‌ای با رعایت ترازهای فیبوناچی مجاز است.';

  if (queueStatus === 'sell_queue') {
    if (isFloorSweep) {
      liqStatus = 'warning';
      liqHeadline = 'صف فروش در حال جمع‌آوری (کف‌روبی FTS)';
      liqDetail = 'سهم صف فروش است اما سفارش‌های خرید قوی در حال بلعیدن و جمع کردن صف هستند.';
      queueNote = 'کف‌روبی فعال است؛ ورود با احتیاط و صرفاً پله اول.';
      liqAdvice = 'برای ورود شتاب‌زده نباشید؛ اجازه دهید صف کاملاً جمع شده و قیمت مثبت شود.';
    } else {
      liqStatus = 'danger';
      liqHeadline = 'ریسک صف فروش و عدم نقدشوندگی';
      liqDetail = 'سهم در صف فروش قفل است و خریدار درشتی در تابلو دیده نمی‌شود؛ امکان خروج سریع با حد ضرر وجود ندارد.';
      queueNote = 'صف فروش سنگین بدون خریدار معتبر.';
      liqAdvice = 'اکیداً از میانگین کم کردن در صف فروش خودداری کنید تا روند هفتگی تایید شود.';
    }
  } else if (queueStatus === 'buy_queue') {
    liqStatus = 'warning';
    liqHeadline = 'صف خرید سنگین (هشدار پرهیز از سرخطی زدن هیجانی)';
    liqDetail = 'سهم با تقاضای بالا مواجه است؛ در صورت پر نشدن حجم مبنا یا عرضه سهامدار عمده، ریسک اصلاح وجود دارد.';
    queueNote = 'صف خرید تشکیل شده است.';
    liqAdvice = 'طبق ستاپ جت، تا ۳ روز بعد از شکست مقاومت فرصت ورود با کندل تثبیت هست؛ از سرخطی زدن هیجانی پرهیز کنید.';
  } else if (clockPattern) {
    liqStatus = 'safe';
    liqHeadline = 'الگوی ساعت تایید شد (تحرکات مثبت در دقایق پایانی)';
    liqDetail = `قیمت آخرین معامله ${clockDiffPct != null ? numFa(clockDiffPct, 1) + '٪' : ''} بالاتر از پایانی است؛ خریداران کنترل بازار را در دست دارند.`;
    queueNote = 'تعادل مثبت با برتری خریداران در انتهای بازار.';
    liqAdvice = 'فرصت مطلوب برای ورود پله‌ای نوسان‌گیری با استاپ ۵٪.';
  }

  const liquidity: LiquidityAssessment = {
    status: liqStatus,
    headline: liqHeadline,
    detail: liqDetail,
    clockPattern,
    clockDiffPct,
    volRatio,
    buyerPower,
    queueStatus,
    queueNote,
    actionAdvice: liqAdvice,
  };

  // ──────────────────────────────────────────────────────────
  // شرط شفاف فعال‌سازی یا رفع وتو (Readiness Condition)
  // ──────────────────────────────────────────────────────────
  let readinessCondition = '';
  if (decision.action === 'ladder_buy') {
    readinessCondition = `تمامی شروط سه‌گانه FTS (روند هفتگی صعودی، ۵ شاخص بنیادی کدال و تایید تابلو) سبز هستند. ورود در محدوده فعلی یا تراز ۳۳-۴۰ فیبو با رعایت حد ضرر ${toFaDigits(stopLossPrice)} ریال مجاز است.`;
  } else if (weeklyUptrend === false) {
    readinessCondition = `شرط رفع ریجکت هفتگی: قیمت باید بالای میانگین متحرک تثبیت شود و کف‌ها و سقف‌های بالاتر در تایم هفتگی شکل بگیرد؛ تا آن زمان، هیچ ورودی مجاز نیست.`;
  } else if (fundStatus === 'fail') {
    readinessCondition = `شرط تایید بنیادی: انتشار گزارش ماهانه جدید در کدال با رشد فروش بالای ۴۰٪ یا صورت مالی با حاشیه سود بالای ۲۰٪.`;
  } else if (jetActive) {
    readinessCondition = `ستاپ جت فعال شده است؛ تثبیت قیمت بالای مقاومت استاتیک ${resistanceStr} به مدت ۳ روز کاری و تایید الگوی ساعت شرط تکمیل پله‌های خرید است.`;
  } else {
    readinessCondition = `شرط ورود معتبر: ۱) شکست مقاومت استاتیک ${resistanceStr} ۲) تایید الگوی ساعت (آخرین بالاتر از پایانی) یا حجم مشکوک ۳ برابری.`;
  }

  // ──────────────────────────────────────────────────────────
  // توصیه اختصاصی بر اساس دیدگاه معامله‌گر (Trader Advice)
  // ──────────────────────────────────────────────────────────
  let traderAdvice = '';
  if (horizon === 'swing') {
    traderAdvice = `توصیه به شخص نوسان‌گیر (زیر ۳ ماه): ورود با ستاپ جت یا تراز ۳۳-۴۰ فیبو مجاز است. حد ضرر صلب شما ۵٪ زیر نقطه ورود یا بسته شدن یک کندل کامل زیر MA-14 است. در برخورد با مقاومت اول حتماً ۵۰٪ سود را سیو کنید تا اصل پول آزاد شود.`;
  } else if (horizon === 'trend') {
    traderAdvice = `توصیه به شخص روندگیر (بالای ۳ ماه): نوسانات روزانه قیمت اهمیتی ندارد؛ خرید پله‌ای در تراز ۳۳-۴۰ و ۶۱.۸-۷۰ فیبو انجام دهید. حد ضرر شما صورت‌های مالی فصلی کدال است، تا زمان رشد فروش و سودآوری سهم را نگه دارید.`;
  } else {
    traderAdvice = `توصیه استراتژی ساعت شنی (۳ تا ۱۰ ساله): مخصوص سهام بزرگ و بنیادی (شاخص‌سازها) در کف تاریخی تایم هفتگی زیر MA-52 و اشباع RSI زیر ۷. با اهرم ۲ تا ۴ برابر خرید کنید و دیدگاه چندساله داشته باشید.`;
  }

  // ──────────────────────────────────────────────────────────
  // تولید متون ۴گانه تشریحی روان بر پایه مفاهیم جزوه
  // ──────────────────────────────────────────────────────────
  const narrativeWhy =
    decision.action === 'ladder_buy'
      ? `نماد ${symbol} فیلترهای سه‌گانه FTS را پاس کرده است؛ گزارش‌های مالی صعودی، روند هفتگی مثبت و تابلوی پرتقاضا هم‌پوشانی دارند. در افق ${HORIZON_LABELS[horizon].badge}، ورود پله‌ای مجاز و کم‌ریسک است.`
      : decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2'
        ? `ورود به نماد ${symbol} متوقف است. علت: ${cleanVetoReason(decision.reason || 'عدم تایید روند هفتگی یا نقص بنیادی')}. تا رفع این مانع، خرید جدید انجام نمی‌شود.`
        : decision.action === 'high_risk_swing'
          ? `ورود روندی به ${symbol} مسدود است، اما جهش تابلو دیده می‌شود؛ صرفاً نوسان‌گیری سبک با حد ضرر ۵٪ (یا کندل زیر MA-14) مجاز است.`
          : `بنیاد نماد ${symbol} تایید است، اما در تابلو تایید نقدینگی ثبت نشده؛ ورود در انتظار زمان‌سنج است.`;

  const narrativeTech =
    techStatus === 'pass'
      ? `در تحلیل تکنیکال، ${techHeadline}. واکنش قیمت به ترازهای فیبوناچی مثبت است و تایم هفتگی مسیر صعودی را تایید می‌کند.`
      : techStatus === 'fail'
        ? `در تحلیل تکنیکال، ${techHeadline}. چارت سهم فاقد ستاپ معتبر یا درگیر روند نزولی هفتگی است و ورود ریسک افت قیمت دارد.`
        : `قیمت در محدوده حمایتی ${supportStr} تا مقاومت ${resistanceStr} در حال درجا زدن است؛ ورود صرفاً با شکست مقاومت ${resistanceStr} (ستاپ جت) یا تایید تراز ۳۳-۴۰ فیبو مجاز است.`;

  const marginStr =
    grossMarginPct != null
      ? numFa(grossMarginPct, 1)
      : typeof fundPayload.gross_margin_pct === 'number'
        ? numFa(fundPayload.gross_margin_pct, 1)
        : '۲۵';

  const narrativeFund =
    fundStatus === 'pass'
      ? `بررسی گزارش فعالیت ماهانه و صورت سود و زیان کدال نشان می‌دهد که شرکت رشد فروش و حاشیه سود بالای ۲۰٪ ثبت کرده است (${fundHeadline}). صنعت شرکت مشمول نرخ‌گذاری دستوری شدید نیست و سودآوری مورد تایید FTS است.`
      : fundStatus === 'fail'
        ? `توقف به دلیل عدم احراز ۵ شاخص بنیادی FTS (${fundHeadline}). سرمایه‌گذاری روی شرکتی که رشد فروش و حاشیه سود پایدار در کدال ندارد، ریسک بالایی دارد.`
        : `گزارش‌های کدال با حاشیه سود ${marginStr}٪ در دست بررسی است؛ گزارش فصلی بعدی جهت تایید رشد فروش رصد خواهد شد.`;

  const entryStr = currentPrice ? `${toFaDigits(currentPrice)} ریال` : 'قیمت فعلی تابلوی بازار';
  const narrativeTrade =
    decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2'
      ? `با توجه به فعال بودن وتو، خرید جدیدی انجام نمی‌شود و سرمایه باید در نمادهای برتر یا صندوق‌های درآمد ثابت و طلا حفظ شود.`
      : `محدوده ورود پله‌ای: ${entryStr}. حد ضرر نوسان‌گیر: ${toFaDigits(stopLossPrice)} ریال (-۵٪ یا کندل زیر MA-14). در صورت صعود تا مقاومت اول (${toFaDigits(targetPrice)} ریال)، طبق قانون FTS نیمی از سهم (۵۰٪) فروخته می‌شود تا اصل پول آزاد شده و معامله بدون ریسک ادامه یابد.`;

  const steps: [PipelineStep, PipelineStep, PipelineStep, PipelineStep] = [step1, step2, step3, step4];

  const hasFail = steps.some((s) => s.status === 'fail');
  const allPass = steps.every((s) => s.status === 'pass');
  const overallStatus: PipelineStepStatus = hasFail ? 'fail' : allPass ? 'pass' : 'wait';

  const overallHeadline =
    overallStatus === 'pass'
      ? 'تایید کامل فیلترهای سه‌گانه FTS'
      : overallStatus === 'fail'
        ? 'ریجکت یا توقف در فیلترهای FTS'
        : 'در حال تکمیل اعتبارسنجی FTS';

  return {
    symbol,
    horizon,
    recommendedHorizon,
    steps,
    overallStatus,
    overallHeadline,
    score: fundScore,
    tradePlan: {
      entryPrice: currentPrice,
      stopLossPrice,
      stopLossBasis,
      stopLossPct,
      targetPrice,
      targetLabel,
      halfExitPrice,
      halfExitLabel,
      weightPct,
    },
    narrative: {
      why: narrativeWhy,
      technical: narrativeTech,
      fundamental: narrativeFund,
      tradePlan: narrativeTrade,
      scenarios,
      liquidity,
      readinessCondition,
      traderAdvice,
    },
  };
}
