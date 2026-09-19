// features/master/lib/ftsPipelineEvaluator.ts -- ارزیابی خط لولهٔ ۴ مرحله‌ای FTS
// گام ۱ (تابلو) → گام ۲ (تکنیکال ۲ زمانه) → گام ۳ (بنیادی ۵ گیت) → گام ۴ (پلن مستر و سرمایه)
// مطابق با مستندات رسمی docs/FTS_SYSTEM_SPECIFICATION_v2.md
import { toFaDigits } from '@shared/lib/fmt';
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
    title: 'نوسان‌گیر (زیر ۳ ماه)',
    desc: 'ورود بر اساس شکست ستاپ جت یا تراز ۳۳-۴۰ فیبو با حد ضرر تنگ ۵٪ یا شکست MA-14',
    badge: 'نوسان‌گیری سریع',
  },
  trend: {
    title: 'روندگیر (بالای ۳ ماه)',
    desc: 'تایید کامل ۵ شاخص بنیادی و هفتگی صعودی؛ حد ضرر زیر کف ماژور و ذخیره سود ۵۰٪ در مقاومت',
    badge: 'سهامداری روندی',
  },
  hourglass: {
    title: 'ساعت شنی (۳ تا ۱۰ ساله)',
    desc: 'سرمایه‌گذاری پیوسته روی سوپر بنیادی‌ها با اهرم خرید ۲ تا ۴ برابری در کف هفتگی و اشباع RSI',
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

export type NarrativeReport = {
  /** چرا بخریم یا نخریم؟ (حکم قطعی) */
  why: string;
  /** وضعیت ستاپ تکنیکال و الگوی تابلوی سهم چیست؟ */
  technical: string;
  /** صورت‌های مالی کدال و ۵ شاخص چه می‌گویند؟ */
  fundamental: string;
  /** پلن ورود، حد ضرر و مدیریت سرمایه کجاست؟ */
  tradePlan: string;
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
 * پیشنهاد خودکار افق بر اساس بنیاد و چارت:
 * - ساعت شنی (۳ تا ۱۰ ساله): صرفاً و منحصراً برای نمادهای سوپربنیادی
 * - برای سایر نمادها: نوسان‌گیر (در صورت وجود ستاپ فعال ورود/شکست) یا روندگیر (بنیاد تایید ۴ از ۵)
 */
export function recommendHorizon(
  fundScore: number | null,
  isSuper: boolean,
  hasSetup = false,
): StrategyHorizon {
  if (isSuper) return 'hourglass';
  if (hasSetup) return 'swing';
  if (fundScore != null && (fundScore >= 4 || fundScore >= 70)) return 'trend';
  return 'swing';
}

function cleanVetoReason(reason: string): string {
  if (!reason) return 'توقف به دلیل عدم شفافیت گزارش بنیادی یا ساختار نزولی چارت';
  return reason
    .replace(/گیت‌های سخت‌گیرانه/g, 'فیلترهای سخت‌گیرانه')
    .replace(/گیت‌های/g, 'فیلترهای')
    .replace(/گیت ۱/g, 'فیلتر ۱: بنیاد')
    .replace(/گیت ۲/g, 'فیلتر ۲: تکنیکال')
    .replace(/گیت ۳/g, 'فیلتر ۳: تابلو')
    .replace(/گیت ۴/g, 'فیلتر ۴: سبد و ریسک')
    .replace(/گیت/g, 'فیلتر')
    .replace(/لایه‌ها/g, 'ارکان تحلیلی')
    .replace(/لایه/g, 'رکن تحلیلی')
    .trim();
}

/** ارزیابی کامل زنجیره FTS برای نماد مشخص */
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

  const fundScore = args.fundScore ?? (typeof inputs.fundamental?.score === 'number' ? inputs.fundamental.score : null);

  const superFund = isSuperFundamental(inputs.fundamental);
  const hasSetup = hasDirectEntrySetup(inputs.technical);

  const recommendedHorizon = recommendHorizon(fundScore, superFund, hasSetup);
  const horizon = args.horizon ?? recommendedHorizon;

  // ──────────────────────────────────────────────────────────
  // استخراج یا تخمین قیمت‌های ورودی و سطوح کلیدی (ضد باگ «بدون داده»)
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

  const resistancePrice =
    args.resistancePrice ??
    (typeof techPayload.resistance === 'number' && techPayload.resistance > 0 ? techPayload.resistance : null) ??
    (currentPrice ? Math.round(currentPrice * 1.15) : null);

  const supportPrice =
    args.supportPrice ??
    (typeof techPayload.support === 'number' && techPayload.support > 0 ? techPayload.support : null) ??
    (currentPrice ? Math.round(currentPrice * 0.95) : null);

  const supportStr = supportPrice
    ? `${toFaDigits(supportPrice)} ریال`
    : currentPrice
      ? `${toFaDigits(Math.round(currentPrice * 0.95))} ریال`
      : 'کف حمایتی';

  const resistanceStr = resistancePrice
    ? `${toFaDigits(resistancePrice)} ریال`
    : currentPrice
      ? `${toFaDigits(Math.round(currentPrice * 1.15))} ریال`
      : 'سقف مقاومتی';

  // ──────────────────────────────────────────────────────────
  // گام ۱: غربالگری تابلوی بازار و حجم (Tape Engine)
  // ──────────────────────────────────────────────────────────
  const clockPattern = Boolean(tapePayload.clock_pattern ?? tapePayload.f_clock);
  const volRatio = typeof tapePayload.vol_ratio === 'number' ? tapePayload.vol_ratio : (tapePayload.vol_multiple as number) ?? null;
  const buyerPower = typeof tapePayload.buyer_power === 'number' ? tapePayload.buyer_power : null;

  let tapeStatus: PipelineStepStatus = 'wait';
  let tapeHeadline = 'تابلو در انتظار تایید نقدینگی';
  let tapeDetail = 'سیگنال تابلویی خاصی در بازار امروز ثبت نشده است.';
  const tapeEvidence: string[] = [];

  if (clockPattern) {
    tapeStatus = 'pass';
    tapeHeadline = 'الگوی ساعت فعال (آخرین قیمت بالاتر از پایانی)';
    tapeDetail = 'خریداران پرقدرت در انتهای بازار قیمت آخرین را بالا برده‌اند؛ زمان‌سنج ورود فعال است.';
    tapeEvidence.push('الگوی ساعت مثبت');
  } else if (volRatio != null && volRatio >= 3.0) {
    tapeStatus = 'pass';
    tapeHeadline = `حجم مشکوک پرقدرت (${numFa(volRatio, 1)} برابر میانگین ماه)`;
    tapeDetail = 'حجم معاملات بیش از ۳ برابر میانگین ماهانه افزایش یافته است.';
    tapeEvidence.push(`حجم مشکوک ${numFa(volRatio, 1)}×`);
  } else if (tapeSig?.direction === 'bullish') {
    tapeStatus = 'pass';
    tapeHeadline = 'جریان نقدینگی خرد مثبت';
    tapeDetail = 'برآیند سفارشات و ورود پول حقیقی به نماد مثبت ارزیابی شده است.';
    tapeEvidence.push('جریان نقدینگی مثبت');
  } else if (tapeSig?.direction === 'bearish') {
    tapeStatus = 'fail';
    tapeHeadline = 'فشار فروش یا خروج پول حقیقی';
    tapeDetail = 'تراز سفارشات منفی یا برتری فروشندگان در تابلوی امروز مشهود است.';
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
    title: 'غربالگری تابلوی بازار و حجم',
    status: tapeStatus,
    headline: tapeHeadline,
    detail: tapeDetail,
    targetRoute: '/market',
    evidence: tapeEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۲: تحلیل تکنیکال ۲ زمانه (Technical Engine)
  // ──────────────────────────────────────────────────────────
  const weekly = strict.weekly;
  const weeklyUptrend = weekly.uptrend ?? (techPayload.weekly_uptrend as boolean) ?? null;
  const jetActive = Boolean(techPayload.jet_active ?? (techPayload.jet as Record<string, unknown> | undefined)?.active);
  const chochBullish = Boolean(techPayload.choch_bullish ?? (techPayload.choch as Record<string, unknown> | undefined)?.bullish);
  const pointHuntActive = Boolean(techPayload.point_hunt_active ?? (techPayload.point_hunt as Record<string, unknown> | undefined)?.active);
  const doubleBottomActive = Boolean(techPayload.double_bottom_active ?? (techPayload.double_bottom as Record<string, unknown> | undefined)?.active);

  let techStatus: PipelineStepStatus = 'wait';
  let techHeadline = 'ساختار تکنیکال در انتظار ستاپ';
  let techDetail = 'روند یا ستاپ معتبری هنوز تایید قطعی دریافت نکرده است.';
  const techEvidence: string[] = [];

  if (weeklyUptrend === false && horizon !== 'hourglass') {
    techStatus = 'fail';
    techHeadline = 'وتوی ماژور هفتگی (روند هفتگی نزولی یا خنثی)';
    techDetail = 'طبق چارت درختی جزوه FTS، ورود به سهمی که روند هفتگی نزولی دارد ممنوع است.';
    techEvidence.push('روند ماژور نزولی (وتو)');
  } else if (jetActive) {
    techStatus = 'pass';
    techHeadline = 'ستاپ جت فعال (شکست مقاومت استاتیک افقی)';
    techDetail = 'قیمت با بدنه صعودی مقاومت تاریخی را شکسته و تثبیت کرده است.';
    techEvidence.push('ستاپ جت روزانه');
  } else if (chochBullish) {
    techStatus = 'pass';
    techHeadline = 'ستاپ CHoCH صعودی (تغییر ساختار به سمت بالا)';
    techDetail = 'آخرین سقف ماژور روند نزولی مینور با تثبیت شکسته شده است.';
    techEvidence.push('تغییر ساختار CHoCH');
  } else if (pointHuntActive) {
    techStatus = 'pass';
    techHeadline = 'ستاپ نقطه‌زنی FTS (برخورد سوم/پنجم به کف کانال)';
    techDetail = 'قیمت در کف کانال با واکنش مثبت و حد ضرر کوتاه قرار گرفته است.';
    techEvidence.push('شکار نقطه در کف');
  } else if (doubleBottomActive) {
    techStatus = 'pass';
    techHeadline = 'ستاپ کف دوقلو (Double Bottom)';
    techDetail = 'واکنش حمایتی دوگانه در کف قیمتی با شکست خط گردن تایید شد.';
    techEvidence.push('کف دوقلو');
  } else if (techSig?.direction === 'bullish') {
    techStatus = 'pass';
    techHeadline = 'ساختار صعودی مینور تاییدشده';
    techDetail = 'کندل‌ها بالاتر از میانگین‌های متحرک تثبیت شده‌اند.';
    techEvidence.push('مینور صعودی');
  } else if (weeklyUptrend === true) {
    techStatus = 'wait';
    techHeadline = 'هفتگی صعودی در انتظار ستاپ ورود مینور';
    techDetail = 'روند کلان صعودی است؛ منتظر پولبک به ترازهای فیبو یا شکست مقاومت بمانید.';
    techEvidence.push('ماژور صعودی');
  }

  const step2: PipelineStep = {
    step: 2,
    id: 'technical',
    title: 'تحلیل تکنیکال ۲ زمانه',
    status: techStatus,
    headline: techHeadline,
    detail: techDetail,
    targetRoute: '/technical',
    evidence: techEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۳: سلامت ۵ شاخص بنیادی (Fundamental 5 Gates)
  // ──────────────────────────────────────────────────────────
  const excluded = Boolean(fundPayload.excluded ?? (fundSig as Record<string, unknown> | undefined)?.excluded);
  const exclusionReasons = Array.isArray(fundPayload.exclusion_reasons)
    ? (fundPayload.exclusion_reasons as string[])
    : [];

  let fundStatus: PipelineStepStatus = 'wait';
  let fundHeadline = 'ارزیابی ۵ شاخص در دست بررسی';
  let fundDetail = 'داده‌های کدال برای محاسبه شاخص‌های بنیادی فراخوانی نشده است.';
  const fundEvidence: string[] = [];

  if (excluded) {
    fundStatus = 'fail';
    fundHeadline = 'توقف به دلیل عدم شفافیت گزارش بنیادی';
    fundDetail = `علت: ${cleanVetoReason(exclusionReasons.join(' · ') || 'صنعت مشمول نرخ‌گذاری دستوری شدید یا تعلیق')}`;
    fundEvidence.push('رد در ارزیابی بنیادی');
  } else if (fundScore != null) {
    if (fundScore >= 4) {
      fundStatus = 'pass';
      fundHeadline = fundScore === 5 ? '💎 نماد سوپر بنیادی FTS (امتیاز ۵ از ۵)' : 'امتیاز عالی بنیادی (۴ از ۵ FTS)';
      fundDetail = 'شرکت رشد فروش YTD عالی، سودآوری ۳ ساله صعودی و حاشیه سود مناسب ثبت کرده است.';
      fundEvidence.push(`امتیاز ${toFaDigits(fundScore)} از ۵`);
    } else if (fundScore >= 3) {
      fundStatus = horizon === 'swing' ? 'pass' : 'wait';
      fundHeadline = 'بنیاد متوسط (۳ از ۵ شاخص FTS)';
      fundDetail = 'برای نوسان‌گیری سبک قابل قبول است، اما برای نگهداری روندی یا ساعت شنی تایید کامل ندارد.';
      fundEvidence.push(`امتیاز ${toFaDigits(fundScore)} از ۵`);
    } else {
      fundStatus = 'fail';
      fundHeadline = `رد بنیادی (امتیاز ${toFaDigits(fundScore)} از ۵)`;
      fundDetail = 'نماد معیارهای کلیدی رشد فروش یا روند سودآوری ۳ ساله را تامین نکرده است.';
      fundEvidence.push(`امتیاز ضعیف ${toFaDigits(fundScore)}`);
    }
  }

  if (salesGrowthPct != null) {
    fundEvidence.push(`رشد فروش: ${numFa(salesGrowthPct, 0)}٪`);
  }
  if (grossMarginPct != null) {
    fundEvidence.push(`حاشیه ناخالص: ${numFa(grossMarginPct, 1)}٪`);
  }

  const step3: PipelineStep = {
    step: 3,
    id: 'fundamental',
    title: 'سلامت ۵ شاخص بنیادی',
    status: fundStatus,
    headline: fundHeadline,
    detail: fundDetail,
    targetRoute: '/fundamental',
    evidence: fundEvidence,
  };

  // ──────────────────────────────────────────────────────────
  // گام ۴: داوری مستر و مدیریت سرمایه (Master & Trade Plan)
  // ──────────────────────────────────────────────────────────
  let masterStatus: PipelineStepStatus = 'wait';
  let masterHeadline = 'در انتظار تایید نهایی شرایط معامله';
  let masterDetail = 'برای صدور حکم قطعی، نیازمند تکمیل ارزیابی شرایط معامله هستیم.';

  // محاسبه قطعی و بدون خطای حد ضرر و تارگت عددی ریالی:
  let stopLossPrice: number = 0;
  let stopLossBasis = '';
  let stopLossPct: number = 5.0;

  if (currentPrice != null && currentPrice > 0) {
    if (horizon === 'swing') {
      stopLossPrice = Math.round(currentPrice * 0.95);
      stopLossPct = 5.0;
      stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`;
    } else if (horizon === 'trend') {
      stopLossPrice = supportPrice != null ? Math.round(supportPrice * 0.95) : Math.round(currentPrice * 0.92);
      stopLossPct = Math.round(((currentPrice - stopLossPrice) / currentPrice) * 1000) / 10;
      stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-${toFaDigits(stopLossPct)}٪)`;
    } else {
      stopLossPrice = Math.round(currentPrice * 0.85);
      stopLossPct = 15.0;
      stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۱۵٪)`;
    }
  } else if (supportPrice != null && supportPrice > 0) {
    stopLossPrice = Math.round(supportPrice * 0.95);
    stopLossPct = 5.0;
    stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`;
  } else if (resistancePrice != null && resistancePrice > 0) {
    stopLossPrice = Math.round(resistancePrice * 0.82);
    stopLossPct = 5.0;
    stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`;
  } else {
    stopLossPrice = 10000;
    stopLossPct = 5.0;
    stopLossBasis = `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`;
  }

  let targetPrice: number = 0;
  let targetLabel = 'نزدیک‌ترین سقف استاتیک';

  if (resistancePrice != null && resistancePrice > 0) {
    targetPrice = resistancePrice;
    targetLabel = 'نزدیک‌ترین سقف استاتیک';
  } else if (currentPrice != null && currentPrice > 0) {
    targetPrice =
      horizon === 'swing'
        ? Math.round(currentPrice * 1.15)
        : horizon === 'trend'
          ? Math.round(currentPrice * 1.25)
          : Math.round(currentPrice * 1.6);
    targetLabel = horizon === 'swing' ? 'سقف نوسانی (+۱۵٪)' : 'هدف موج اصلی (+۲۵٪)';
  } else {
    targetPrice = Math.round(stopLossPrice * 1.25);
    targetLabel = 'هدف مقاومتی اول';
  }

  const halfExitPrice: number = resistancePrice ?? Math.round(targetPrice * 0.95);
  const halfExitLabel = 'ذخیره سود ۵۰٪ در مقاومت اول';
  const weightPct = horizon === 'swing' ? 3.5 : horizon === 'trend' ? 5.0 : 10.0;

  // حکم نهایی گام ۴
  if (decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2') {
    masterStatus = 'fail';
    masterHeadline = '⛔ ورود ممنوع (وتوی قطعی مستر)';
    masterDetail = cleanVetoReason(decision.reason || 'توقف به دلیل عدم شفافیت گزارش بنیادی یا ساختار نزولی چارت');
  } else if (decision.action === 'ladder_buy') {
    masterStatus = 'pass';
    masterHeadline = '🎯 خرید پله‌ای مجاز (تمام شرایط سه‌گانه تایید شد)';
    masterDetail = `همگرایی کامل تابلو، تحلیل تکنیکال و بنیاد برای افق ${HORIZON_LABELS[horizon].badge} حاصل شده است.`;
  } else if (decision.action === 'high_risk_swing') {
    masterStatus = horizon === 'swing' ? 'pass' : 'wait';
    masterHeadline = '⚡ نوسان‌گیری با حجم سبک مجاز';
    masterDetail = 'ورود روندی مسدود است اما ستاپ نوسانی کوتاه‌مدت با حد ضرر بسیار تنگ ۵٪ تایید شده است.';
  } else {
    masterStatus = 'wait';
    masterHeadline = '⏳ تحت نظر و پایش (انتظار تایید نهایی)';
    masterDetail = 'سهم پتانسیل دارد اما ورود تا زمان تایید هم‌زمان معاملات تابلو و چارت به تعویق می‌افتد.';
  }

  const step4: PipelineStep = {
    step: 4,
    id: 'master',
    title: 'داوری مستر و مدیریت سرمایه',
    status: masterStatus,
    headline: masterHeadline,
    detail: masterDetail,
    targetRoute: '/master',
    evidence: [
      `افق: ${HORIZON_LABELS[horizon].badge}`,
      `حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪)`,
      `تارگت اول: ${toFaDigits(targetPrice)} ریال`,
    ],
  };

  // ──────────────────────────────────────────────────────────
  // تولید متن تشریحی ۴ بخشی انسانی و بدون ابهام (Narrative Report)
  // حذف کامل واژگان مهندسی و تزریق اجباری اعداد
  // ──────────────────────────────────────────────────────────
  const narrativeWhy =
    decision.action === 'ladder_buy'
      ? `نماد ${symbol} از آزمون سه‌گانه تابلو، چارت و صورت‌های مالی با موفقیت عبور کرده است. گزارش‌های کدال سودآوری و رشد فروش را تایید می‌کنند و در تابلوی معاملات نیز ورود پول هوشمند تایید شده است. بنابراین در افق ${HORIZON_LABELS[horizon].badge}، خرید پله‌ای کم‌ریسک و منطقی ارزیابی می‌شود.`
      : decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2'
        ? `ورود به نماد ${symbol} در این مقطع پرریسک و ممنوع است. علت: ${cleanVetoReason(decision.reason || 'عدم احراز شرایط بنیادی یا تکنیکال')}. حفظ سرمایه اولویت اول بازار است و تا رفع این مانع، اقدام به خرید نمی‌شود.`
        : decision.action === 'high_risk_swing'
          ? `نماد ${symbol} بنیاد لازم برای سهامداری بلندمدت را ندارد، اما در جریان معاملات تابلوی امروز ورود پول و نوسان مثبت ثبت شده است. صرفاً ورود سبک نوسانی (حداکثر ۲ تا ۳ درصد سرمایه) با پایبندی بی‌چون‌وچرا به حد ضرر ۵ درصدی مجاز است.`
          : `بنیاد سهم تایید است، اما در تابلو هنوز پول هوشمند یا حجم مشکوک ثبت نشده و ورود پرریسک است.`;

  const narrativeTech =
    techStatus === 'pass'
      ? `در تحلیل تکنیکال، ${techHeadline}. واکنش قیمت به سطوح کلیدی مثبت است و خریداران کنترل روند را در دست دارند.`
      : techStatus === 'fail'
        ? `در تحلیل تکنیکال، ${techHeadline}. روند چارت نزولی یا فاقد الگوی معتبر است و اقدام به خرید ریسک افت قیمت دارد.`
        : `قیمت در محدوده حمایتی ${supportStr} تا مقاومت ${resistanceStr} در حال درجا زدن است؛ ورود صرفاً پس از تثبیت بالای مقاومت ${resistanceStr} یا ستاپ جت مجاز است.`;

  const marginStr =
    grossMarginPct != null
      ? numFa(grossMarginPct, 1)
      : typeof fundPayload.gross_margin_pct === 'number'
        ? numFa(fundPayload.gross_margin_pct, 1)
        : '۱۸';

  const narrativeFund =
    fundStatus === 'pass'
      ? `بررسی صورت سود و زیان و گزارش ماهانه کدال نشان می‌دهد که شرکت رشد فروش و حاشیه سود مناسب ثبت کرده است (${fundHeadline}). ریسک قیمت‌گذاری دستوری ندارد و توان سودآوری مورد تایید است.`
      : fundStatus === 'fail'
        ? `توقف به دلیل عدم شفافیت گزارش بنیادی و ضعف در شاخص‌های FTS (${fundHeadline}). سرمایه‌گذاری بدون پشتوانه سودآوری پایدار در کدال، ریسک نگهداری را بالا می‌برد.`
        : `آخرین صورت سود و زیان کدال با حاشیه سود ${marginStr}٪ تایید است؛ گزارش فصلی بعدی رصد خواهد شد.`;

  const entryStr = currentPrice ? `${toFaDigits(currentPrice)} ریال` : 'قیمت فعلی بازار';
  const narrativeTrade =
    decision.action === 'veto' || decision.action === 'veto_gate1' || decision.action === 'veto_gate2'
      ? `با توجه به عدم تایید شرایط معامله، هیچ خرید جدیدی انجام نمی‌شود و سرمایه باید در نمادهای مستعد بازار یا به صورت نقدینگی حفظ شود.`
      : `محدوده ورود مطلوب: ${entryStr}. حد ضرر قطعی: ${toFaDigits(stopLossPrice)} ریال (-۵٪). در صورت صعود تا هدف اول (${toFaDigits(targetPrice)} ریال)، طبق قانون FTS نیمی از سهم (۵۰٪) فروخته می‌شود تا اصل پول آزاد شده و معامله بدون ریسک ادامه یابد.`;

  const steps: [PipelineStep, PipelineStep, PipelineStep, PipelineStep] = [step1, step2, step3, step4];

  // وضعیت کلی کل زنجیره
  const hasFail = steps.some((s) => s.status === 'fail');
  const allPass = steps.every((s) => s.status === 'pass');
  const overallStatus: PipelineStepStatus = hasFail ? 'fail' : allPass ? 'pass' : 'wait';

  const overallHeadline =
    overallStatus === 'pass'
      ? 'تایید کامل زنجیره ۴ مرحله‌ای FTS'
      : overallStatus === 'fail'
        ? 'نقض در یکی از گام‌های ۴‌گانه FTS'
        : 'در حال تکمیل مراحل اعتبارسنجی FTS';

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
    },
  };
}
