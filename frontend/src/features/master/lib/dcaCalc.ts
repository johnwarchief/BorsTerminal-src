// features/master/lib/dcaCalc.ts -- ماشین‌حساب برنامهٔ معاملاتی و DCA (ریاضی خالص)
// ارزش ریالی (تومان) و تعداد برگهٔ هر پله از سرمایهٔ ثبت‌شده و سقف وزن صنعت.
// Circuit Breaker: نبود سرمایه/قیمت ⇒ null + «بدون داده»؛ هیچ عدد ساختگی.
export const TOMAN = 'تومان';

export type StepKey = 'step1' | 'step2' | 'breakout';

export type PlanLevelish = { lo?: number | null; hi?: number | null } | null;

export type BlueprintStep = {
  key: StepKey;
  label: string;
  lo: number | null;
  hi: number | null;
  /** قیمت مرجع برای تعداد برگه (میانهٔ بازه، وگرنه کران موجود) */
  refPrice: number | null;
  /** تومان تخصیص‌یافته به این پله */
  amountToman: number | null;
  /** تعداد برگه (سهم) */
  shares: number | null;
  /** درصد وزن مؤثر این پله از کل سرمایه */
  weightPct: number | null;
};

export type BlueprintInput = {
  /** کل سرمایه/نقدینگی (تومان) — null یعنی ثبت نشده (در آن صورت UI سرمایهٔ فرضی می‌گذارد) */
  capitalToman: number | null;
  /** آیا سرمایهٔ نمایش‌داده‌شده فرضی است؟ (برای یادداشت صادقانه) */
  assumedCapital?: boolean;
  /** وزن پایهٔ هر پله بر حسب ریسک (۲ تا ۵ درصد) */
  baseStepWeightPct: number;
  /** سقف وزن صنعت طبق سند (درصد) */
  industryCapPct: number;
  /** مصرف فعلی صنعت در سبد (درصد) */
  industryUsedPct: number | null;
  step1: PlanLevelish;
  step2: PlanLevelish;
  breakout: PlanLevelish;
  /** حد ضرر پرایس‌اکشن (کف ماژور) از سرور */
  priceActionStop: number | null;
  /** اولین مقاومت استاتیک */
  resistance: number | null;
  /** قیمت جاری برای سنجش رسیدن به مقاومت */
  currentPrice: number | null;
  /** سقف رژیم جنگی (۱۰ تا ۲۰ درصد) — null یعنی رژیم نرمال */
  warCapPct: number | null;
};

export type BlueprintResult = {
  capitalToman: number | null;
  hasCapital: boolean;
  hasPlan: boolean;
  industryCapPct: number;
  /** ظرفیت باقی‌ماندهٔ صنعت (درصد) */
  industryRemainingPct: number | null;
  /** وزن مؤثر هر پله = min(وزن پایه، ظرفیت صنعت، سقف رژیم) */
  effectiveStepWeightPct: number | null;
  steps: BlueprintStep[];
  stop: {
    /** حد ضرر عملیاتی (محافظه‌کارانه: دورتر از ورود) */
    price: number | null;
    /** −۵٪ از قیمت مرجع پله اول */
    fromPct5: number | null;
    /** کف ماژور پرایس‌اکشن (سرور) */
    priceAction: number | null;
    basis: string;
  };
  /** نسبت بازده به ریسک تا اولین مقاومت استاتیک */
  rr: number | null;
  resistance: number | null;
  notes: string[];
};

function mid(lo: number | null, hi: number | null): number | null {
  if (lo != null && hi != null) return Math.round(((lo + hi) / 2) * 100) / 100;
  return lo ?? hi ?? null;
}

function level(lo?: number | null, hi?: number | null): { lo: number | null; hi: number | null; ref: number | null } {
  const l = typeof lo === 'number' && Number.isFinite(lo) ? lo : null;
  const h = typeof hi === 'number' && Number.isFinite(hi) ? hi : null;
  return { lo: l, hi: h, ref: mid(l, h) };
}

const STEP_LABELS: Record<StepKey, string> = {
  step1: 'پله ۱ (فیبو ۰.۳۳ تا ۰.۴۰)',
  step2: 'پله ۲ (فیبو ۰.۶۱۸ تا ۰.۷۰)',
  breakout: 'ورود جت (شکست سقف تاریخی)',
};

/**
 * ساخت برنامهٔ معاملاتی با ارزش ریالی و تعداد برگه.
 * وزن مؤثر هر پله = min(وزن پایهٔ ریسک، ظرفیت باقی‌ماندهٔ صنعت، سقف رژیم جنگی).
 */
export function buildTradeBlueprint(input: BlueprintInput): BlueprintResult {
  const notes: string[] = [];
  const capital = typeof input.capitalToman === 'number' && input.capitalToman > 0 ? input.capitalToman : null;
  if (capital == null) {
    notes.push('سرمایهٔ کل ثبت نشده است؛ برای محاسبهٔ ریالی، سرمایهٔ فرضی را وارد کن.');
  } else if (input.assumedCapital) {
    notes.push('این محاسبه با «سرمایهٔ فرضی پیش‌فرض» انجام شده است؛ عدد واقعی را در ورودی سرمایهٔ کل جایگزین کن.');
  }

  const cap = input.industryCapPct > 0 ? input.industryCapPct : 20;
  const remaining = input.industryUsedPct != null ? Math.max(0, Math.round((cap - input.industryUsedPct) * 10) / 10) : null;
  if (remaining != null && remaining <= 0) notes.push(`ظرفیت صنعت پر است (مصرف ${input.industryUsedPct}٪ از سقف ${cap}٪).`);

  const war = input.warCapPct;
  let weight = Math.max(0, Math.min(input.baseStepWeightPct, 100));
  if (remaining != null) weight = Math.min(weight, remaining);
  if (war != null) weight = Math.min(weight, war);
  weight = Math.round(weight * 10) / 10;
  const effectiveStepWeightPct = weight;

  const s1 = level(input.step1?.lo, input.step1?.hi);
  const s2 = level(input.step2?.lo, input.step2?.hi);
  const bj = level(input.breakout?.lo, input.breakout?.hi);

  const mkStep = (key: StepKey, lv: { lo: number | null; hi: number | null; ref: number | null }): BlueprintStep => {
    const hasLevel = lv.ref != null;
    const amount = capital != null && hasLevel && weight > 0 ? Math.round((capital * weight) / 100) : null;
    const shares = amount != null && lv.ref != null && lv.ref > 0 ? Math.floor(amount / lv.ref) : null;
    return {
      key,
      label: STEP_LABELS[key],
      lo: lv.lo,
      hi: lv.hi,
      refPrice: lv.ref,
      amountToman: amount,
      shares,
      weightPct: hasLevel ? weight : null,
    };
  };

  const steps: BlueprintStep[] = [mkStep('step1', s1), mkStep('step2', s2), mkStep('breakout', bj)];
  const hasPlan = steps.some((s) => s.refPrice != null);

  const entry = s1.ref ?? s2.ref ?? bj.ref ?? input.currentPrice ?? null;
  const fromPct5 = entry != null ? Math.round(entry * 0.95 * 100) / 100 : null;
  const priceAction = input.priceActionStop != null && Number.isFinite(input.priceActionStop) ? input.priceActionStop : null;
  // عملیاتی = دورتر از ورود (محافظه‌کارانه برای نسبت R/R)
  const operativeStop =
    fromPct5 != null && priceAction != null ? Math.min(fromPct5, priceAction) : (fromPct5 ?? priceAction ?? null);
  const basis =
    fromPct5 != null && priceAction != null
      ? 'محافظه‌کارانه: دورترین حد از −۵٪ و کف ماژور'
      : fromPct5 != null
        ? '۵٪ زیر قیمت مرجع پله اول'
        : priceAction != null
          ? 'کف ماژور پرایس‌اکشن'
          : 'بدون داده';

  const resistance = input.resistance != null && Number.isFinite(input.resistance) ? input.resistance : null;
  let rr: number | null = null;
  if (entry != null && operativeStop != null && entry - operativeStop > 0) {
    const risk = entry - operativeStop;
    if (resistance != null && resistance > entry) {
      const reward = resistance - entry;
      rr = Math.round((reward / risk) * 100) / 100;
    } else {
      // در صورت نبود مقاومت تاریخی یا عبور قیمت از آن (سقف تاریخی / ستاپ جت)،
      // فرمول مبتنی بر تارگت پیش‌فرض ستاپ جت (+۲۰٪ بالای نقطه ورود) محاسبه می‌شود
      const jetTarget = Math.round(entry * 1.20);
      const reward = jetTarget - entry;
      rr = Math.round((reward / risk) * 100) / 100;
      notes.push('مقاومت تاریخی بالاتر در دسترس نیست؛ نسبت R/R بر مبنای تارگت پیش‌فرض ستاپ جت (+۲۰٪) محاسبه شد.');
    }
  } else if (entry != null && entry > 0) {
    // اگر حد ضرر عملیاتی غایب باشد، حد ضرر استاندارد ۵٪ در نظر گرفته می‌شود
    const fallbackStop = Math.round(entry * 0.95);
    const risk = entry - fallbackStop;
    const target = resistance != null && resistance > entry ? resistance : Math.round(entry * 1.20);
    const reward = target - entry;
    if (risk > 0) {
      rr = Math.round((reward / risk) * 100) / 100;
    }
  }

  return {
    capitalToman: capital,
    hasCapital: capital != null,
    hasPlan,
    industryCapPct: cap,
    industryRemainingPct: remaining,
    effectiveStepWeightPct,
    steps,
    stop: { price: operativeStop, fromPct5, priceAction, basis },
    rr,
    resistance,
    notes,
  };
}

/** قالب تومان با جداکنندهٔ فارسی */
export function toman(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'بدون داده';
  return Math.round(x).toLocaleString('fa-IR');
}
