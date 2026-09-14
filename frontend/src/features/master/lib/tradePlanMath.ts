// features/master/lib/tradePlanMath.ts -- ریاضیات خالص برنامه معاملاتی FTS
// پله‌ها و حد ضرر و وزن سرمایه — همه از دادهٔ سرور (fib/jet/exit) ساخته می‌شوند.
// بازتولید فیبو در فرانت ممنوع (Circuit Breaker: داده نیست ⇒ «بدون داده»).

export type PlanLevel = {
  /** شناسه پله */
  key: 'step1' | 'step2' | 'breakout' | 'stop';
  lo: number | null;
  hi: number | null;
};

export type MoneyWeight = {
  /** درصد سرمایه در هر پله: 2-5٪ بر اساس سطح ریسک */
  pct: number;
};

export const STEP_WEIGHT_FLOOR_PCT = 2;
export const STEP_WEIGHT_CEIL_PCT = 5;

/**
 * سطح ریسک از 0 (کم‌خطر) تا 100 (پرخطر) به وزن هر پله نگاشت می‌شود:
 * وزن = 5 - (ریسک × 3 / 100) ⇒ کم‌خطر 5٪، پرخطر 2٪.
 */
export function stepWeightPct(riskLevel: number): number {
  const r = Math.max(0, Math.min(100, riskLevel));
  return Math.round((STEP_WEIGHT_CEIL_PCT - (r * (STEP_WEIGHT_CEIL_PCT - STEP_WEIGHT_FLOOR_PCT)) / 100) * 10) / 10;
}

/** تعیین سطح ریسک 0..100 از وضعیت گیت‌ها و تضاد — برای وزن‌دهی پله‌ها */
export function riskLevel(input: { hasConflict: boolean; gateFails: number; gateWaits: number }): number {
  let r = 20; // پایه
  if (input.hasConflict) r += 30;
  r += input.gateFails * 25;
  r += input.gateWaits * 12;
  return Math.max(0, Math.min(100, r));
}

export type TradePlan = {
  /** پله اول: تراز فیبو 33-40٪ اصلاحی — null یعنی بدون داده چارت */
  step1: PlanLevel | null;
  /** پله دوم: تراز فیبو 61.8-70٪ — null یعنی بدون داده چارت */
  step2: PlanLevel | null;
  /** پله شکست: سقف استاتیک (ستاپ جت) — null یعنی بدون داده چارت */
  breakout: PlanLevel | null;
  /** حد ضرر: 5٪ زیر آخرین کف ماژور یا شکست MA-14 — null یعنی بدون داده چارت */
  stop: { price: number | null; basis: string };
  /** وزن پیشنهادی هر پله از سرمایه */
  weight: MoneyWeight;
};

export type PlanInput = {
  fib: {
    zone_33_40?: { lo?: number | null | undefined; hi?: number | null | undefined } | null | undefined;
    zone_618_70?: { lo?: number | null | undefined; hi?: number | null | undefined } | null | undefined;
  } | null | undefined;
  jet: {
    active?: boolean | null | undefined;
    resistance?: number | null | undefined;
  } | null | undefined;
  exit: {
    l1?: {
      hard_stop?: number | null | undefined;
      stop_basis?: string | null | undefined;
      ma14?: number | null | undefined;
    } | null | undefined;
  } | null | undefined;
  /** سطح ریسک 0..100 — از riskLevel() */
  risk: number;
};

/** ساخت برنامه معاملاتی از دادهٔ سرور — بدون محاسبهٔ فیبو در فرانت */
export function buildTradePlan(input: PlanInput): TradePlan {
  const z1 = input.fib?.zone_33_40 ?? null;
  const z2 = input.fib?.zone_618_70 ?? null;
  const step1 =
    z1 != null && (z1.lo != null || z1.hi != null)
      ? { key: 'step1' as const, lo: z1.lo ?? null, hi: z1.hi ?? null }
      : null;
  const step2 =
    z2 != null && (z2.lo != null || z2.hi != null)
      ? { key: 'step2' as const, lo: z2.lo ?? null, hi: z2.hi ?? null }
      : null;
  const res = input.jet?.resistance ?? null;
  const breakout = res != null ? { key: 'breakout' as const, lo: res, hi: null } : null;

  const hard = input.exit?.l1?.hard_stop ?? null;
  const ma14 = input.exit?.l1?.ma14 ?? null;
  const basisRaw = input.exit?.l1?.stop_basis ?? null;
  // حد ضرر: 5٪ زیر آخرین کف ماژور (hard_stop سرور همین است) یا شکست MA-14
  const stopPrice = hard ?? ma14 ?? null;
  const basis =
    basisRaw === 'entry'
      ? '۵٪ زیر کف ورود'
      : basisRaw === 'swing_low'
        ? '۵٪ زیر آخرین کف ماژور'
        : ma14 != null && hard == null
          ? 'شکست MA-14'
          : 'بدون داده';

  return {
    step1,
    step2,
    breakout,
    stop: { price: stopPrice, basis },
    weight: { pct: stepWeightPct(input.risk) },
  };
}

/** رندر عدد ریالی دقیق — بدون داده یعنی عبارت صریح */
export function rial(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'بدون داده';
  return Math.round(x).toLocaleString('fa-IR');
}
