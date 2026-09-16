// features/master/lib/strictGates.ts -- ماشین حالت وتو (بدون میانگین خطی)
// چهار گیت سخت‌گیرانه: [بنیاد] → [تکنیکال ماژور/مینور] → [تابلوخوانی] → [سبد و رژیم ریسک]
// قوانین (M-03):
// ۱) نبود روند هفتگی صعودی ⇒ VETO فوری.
// ۲) نقض بنیادی (افت شدید فروش یا حاشیهٔ < ۲۰٪) ⇒ ورود روندی مسدود؛ فقط با جهش تابلو
//    برچسب «نوسانگیری صرفاً با حجم سبک».
// ۳) تابلو فقط زمان‌سنج ورود است (تصمیم‌ساز نیست).
// ۴) «خرید پله‌ای» فقط با سبز بودن هم‌زمان هر چهار گیت.
// Circuit Breaker: نبود داده ⇒ state=pending + دلیل صادقانه؛ هرگز وتوی ساختگی.
import type { AgentSignal } from '@contracts/signal';
import { isActiveSignal, type BusInput } from './masterMath';
import { fa0, fa1 } from './fmtNum';

export type StrictGateId = 'fundamental' | 'technical' | 'tape' | 'portfolio';

export type StrictGateState = 'passed' | 'blocked' | 'pending';

/** معادل انگلیسی وضعیت — برای برچسب (Passed/Blocked/Pending) */
export type StrictGateStateEn = 'Passed' | 'Blocked' | 'Pending';

export type StrictGate = {
  id: StrictGateId;
  label: string;
  state: StrictGateState;
  stateEn: StrictGateStateEn;
  /** دلیل ریاضی/قانونی — متن Audit Popover */
  reason: string;
  /** آیا این گیت وتوی فوری صادر می‌کند؟ */
  veto: boolean;
};

/** کف حاشیهٔ سود خالص طبق سند FTS */
export const FUNDAMENTAL_MARGIN_FLOOR_PCT = 20;
/** آستانهٔ افت شدید فروش (درصد سالانه) */
export const SALES_DROP_FLOOR_PCT = 0;

export const STRICT_GATE_LABELS: Record<StrictGateId, string> = {
  fundamental: 'بنیاد',
  technical: 'تکنیکال ماژور/مینور',
  tape: 'تابلوخوانی',
  portfolio: 'سبد و رژیم ریسک',
};

const STATE_EN: Record<StrictGateState, StrictGateStateEn> = {
  passed: 'Passed',
  blocked: 'Blocked',
  pending: 'Pending',
};

/** دادهٔ هفتگی (MA52/RSI) — در نبود منبع، همهٔ فیلدها null و گیت pending می‌ماند */
export type WeeklyTrendInput = {
  /** قیمت هفتگی زیر MA52 است؟ */
  belowMa52: boolean | null;
  /** RSI هفتگی */
  rsi: number | null;
  /** روند هفتگی صعودی است؟ */
  uptrend: boolean | null;
};

export const EMPTY_WEEKLY: WeeklyTrendInput = { belowMa52: null, rsi: null, uptrend: null };

function payloadAsRecord(s: AgentSignal | undefined): Record<string, unknown> {
  return (s?.payload ?? {}) as Record<string, unknown>;
}

function pickNum(p: Record<string, unknown>, keys: string[]): number | null {
  for (const k of keys) {
    const v = p[k];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return null;
}

function pickBool(p: Record<string, unknown>, keys: string[]): boolean | null {
  for (const k of keys) {
    const v = p[k];
    if (typeof v === 'boolean') return v;
  }
  return null;
}

/**
 * خواندن دادهٔ هفتگی از payload تکنیکال (در صورت انتشار).
 * هنوز هیچ اندپوینت/سیگنالی MA52 و RSI هفتگی را منتشر نمی‌کند ⇒ خروجی null است
 * و گیت وتوی هفتگی صادقانه «در انتظار» می‌ماند (بدون ادعای کاذب).
 */
export function weeklyTrendFromSignal(tech: AgentSignal | undefined): WeeklyTrendInput {
  const p = payloadAsRecord(tech);
  const weekly = (p.weekly ?? {}) as Record<string, unknown>;
  return {
    belowMa52:
      pickBool(p, ['belowMa52', 'weekly_below_ma52', 'weeklyBelowMa52']) ??
      pickBool(weekly, ['belowMa52', 'below_ma52']),
    rsi: pickNum(p, ['weeklyRsi', 'weekly_rsi']) ?? pickNum(weekly, ['rsi']),
    uptrend: pickBool(p, ['weeklyUptrend', 'weekly_uptrend']) ?? pickBool(weekly, ['uptrend']),
  };
}

export type FundamentalMetrics = {
  /** حاشیهٔ سود ناخالص/خالص (درصد) — null یعنی منتشر نشده */
  marginPct: number | null;
  /** رشد فروش (درصد) — null یعنی منتشر نشده */
  salesGrowthPct: number | null;
  /** پاس‌شدن زیرشاخص حاشیه (اگر در passes باشد) */
  marginCheck: boolean | null;
  directionBearish: boolean;
};

export function fundamentalMetrics(fund: AgentSignal | undefined): FundamentalMetrics {
  const p = payloadAsRecord(fund);
  const passes = (p.passes ?? {}) as Record<string, boolean>;
  const metrics = (p.metrics ?? {}) as Record<string, unknown>;
  const marginCheck =
    pickBool(passes as unknown as Record<string, unknown>, [
      '3_gross_margin',
      'gross_margin',
      'GROSS_MARGIN',
      'margin',
    ]) ?? null;
  const marginPct =
    pickNum(metrics, ['gross_margin', 'margin_pct', 'net_margin']) ?? pickNum(p, ['margin_pct']);
  const salesGrowthPct =
    pickNum(metrics, ['growth_pct', 'monetary_growth_pct', 'sales_growth_pct']) ??
    pickNum(p, ['sales_growth_pct']);
  return {
    marginPct,
    salesGrowthPct,
    marginCheck,
    directionBearish: fund?.direction === 'bearish',
  };}

/** ستاپ ورود مختلف تکنیکال (جت/پولبک/شکست) */
export function hasDirectEntrySetup(tech: AgentSignal | undefined): boolean {
  const p = payloadAsRecord(tech);
  const setups = Array.isArray(p.setups) ? (p.setups as unknown[]) : [];
  return setups.includes('breakout') || setups.includes('pullback') || setups.includes('choch');
}

/** الگوی تابلو */
export function tapePattern(tape: AgentSignal | undefined): { pattern: string | null; volumeMultiple: number | null } {
  const p = payloadAsRecord(tape);
  const pattern = typeof p.pattern === 'string' ? (p.pattern as string) : null;
  return { pattern, volumeMultiple: pickNum(p, ['volumeMultiple', 'volume_multiple']) };
}

export function tapeIsSurge(tape: AgentSignal | undefined): boolean {
  const { pattern, volumeMultiple } = tapePattern(tape);
  if (pattern === 'closing_auction_pop') return true;
  return pattern === 'suspicious_volume' && volumeMultiple != null && volumeMultiple >= 3;
}

export type PortfolioRegimeInput = {
  /** آیا نماد در سبد است (رأی پرتفوی accept)؟ null = نامشخص */
  inBasket: boolean | null;
  /** وزن فعلی صنعت نماد در سبد (درصد) — null = بدون داده */
  industryUsedPct: number | null;
  /** سقف وزن صنعت طبق سند (درصد) */
  industryCapPct: number;
  /** رژیم ریسک/جنگ فعال است؟ (اعلام کاربر با داده‌ای که سیستم ندارد) */
  warRegime: boolean;
  /** وزن ثبت‌شدهٔ نماد در سبد */
  symbolWeightPct: number | null;
};

export const DEFAULT_INDUSTRY_CAP_PCT = 20;

export type StrictGatesResult = {
  gates: StrictGate[];
  weekly: WeeklyTrendInput;
  /** آیا وتوی هفتگی صادر شد؟ */
  weeklyVeto: boolean;
  /** آیا گیت هفتگی داده دارد؟ */
  weeklyHasData: boolean;
  fundamentalBlocked: boolean;
  tapeSurge: boolean;
};

/**
 * اجرای چهار گیت سخت‌گیرانه. هیچ میانگین خطی‌ای بین گیت‌ها گرفته نمی‌شود؛
 * هر گیت مستقل ارزیابی و فقط برای تشخیص «وتو» و «خرید پله‌ای» ترکیب می‌شود.
 */
export function runStrictGates(
  input: BusInput,
  regime: PortfolioRegimeInput,
  weekly: WeeklyTrendInput = EMPTY_WEEKLY,
  now = Date.now(),
): StrictGatesResult {
  const gates: StrictGate[] = [];
  const mk = (id: StrictGateId, state: StrictGateState, reason: string, veto = false): StrictGate => ({
    id,
    label: STRICT_GATE_LABELS[id],
    state,
    stateEn: STATE_EN[state],
    reason,
    veto,
  });

  // ── گیت ۱: بنیاد ────────────────────────────────────────────────
  const fund = input.fundamental;
  const fm = fundamentalMetrics(fund);
  const fundActive = fund != null && isActiveSignal(fund, now);
  let fundamentalBlocked = false;
  if (!fund) {
    gates.push(mk('fundamental', 'pending', 'سیگنال بنیادی منتشر نشده است؛ گیت بنیاد بدون داده است.'));
  } else if (!fundActive) {
    gates.push(mk('fundamental', 'pending', 'سیگنال بنیادی منقضی/ناقص است؛ گیت بنیاد ارزیابی نشد.'));
  } else {
    const marginBreach = fm.marginCheck === false || (fm.marginPct != null && fm.marginPct < FUNDAMENTAL_MARGIN_FLOOR_PCT);
    const salesBreach = fm.salesGrowthPct != null && fm.salesGrowthPct < SALES_DROP_FLOOR_PCT;
    const reasonBits: string[] = [];
    if (fm.marginPct != null) reasonBits.push(`حاشیهٔ سود ${fa1(fm.marginPct)}٪ در برابر کف ${fa0(FUNDAMENTAL_MARGIN_FLOOR_PCT)}٪`);
    if (fm.salesGrowthPct != null) reasonBits.push(`رشد فروش ${fa1(fm.salesGrowthPct)}٪ در برابر کف ${fa0(SALES_DROP_FLOOR_PCT)}٪`);
    if (fm.marginCheck != null) reasonBits.push(`زیرشاخص حاشیه: ${fm.marginCheck ? 'تایید' : 'رد'}`);
    const basis = reasonBits.length > 0 ? reasonBits.join(' · ') : 'نمرهٔ بنیادی صعودی و بدون نقض آشکار';
    if (fm.directionBearish || marginBreach || salesBreach) {
      fundamentalBlocked = true;
      gates.push(mk('fundamental', 'blocked', `نقض بنیادی ⇒ ورود روندی مسدود (${basis}).`));
    } else if (fm.marginPct == null && fm.marginCheck == null && fm.salesGrowthPct == null) {
      gates.push(mk('fundamental', 'pending', 'دادهٔ مالی کافی برای سنجش حاشیه/فروش در دسترس نیست؛ گیت بنیاد محافظه‌کارانه در انتظار است.'));
    } else {
      gates.push(mk('fundamental', 'passed', `شرط بنیادی برقرار است (${basis}).`));
    }
  }

  // ── گیت ۲: تکنیکال ماژور/مینور + وتوی روند هفتگی ─────────────────
  const tech = input.technical;
  const techActive = tech != null && isActiveSignal(tech, now);
  const weeklyHasData = weekly.uptrend != null || weekly.belowMa52 != null || weekly.rsi != null;
  // وتوی هفتگی فقط با دادهٔ صریح «روند هفتگی صعودی نیست» صادر می‌شود (بدون ادعای کاذب).
  const weeklyNotUp = weekly.uptrend === false;
  const weeklyVeto = weeklyNotUp;
  if (!tech) {
    gates.push(mk('technical', 'pending', 'سیگنال تکنیکال منتشر نشده است؛ گیت تکنیکال بدون داده است.'));
  } else if (!techActive) {
    gates.push(mk('technical', 'pending', 'سیگنال تکنیکال منقضی/ناقص است؛ گیت تکنیکال ارزیابی نشد.'));
  } else if (weeklyNotUp) {
    gates.push(
      mk(
        'technical',
        'blocked',
        `وتوی روند هفتگی: روند هفتگی صعودی نیست (MA52/RSI هفتگی تایید نکرد) ⇒ VETO فوری.`,
        true,
      ),
    );
  } else if (tech.direction === 'bearish') {
    gates.push(mk('technical', 'blocked', 'ساختار تکنیکال نزولی است ⇒ ورود ممنوع (ماژور/مینور نزولی).'));
  } else if (!hasDirectEntrySetup(tech)) {
    gates.push(mk('technical', 'pending', 'ستاپ ورود مستقیم (جت/پولبک/CHoCH) فعال نیست؛ در انتظار تریگر.'));
  } else {
    gates.push(mk('technical', 'passed', 'ستاپ ورود مستقیم روی ساختار ماژور/مینور فعال است.'));
  }
  if (!weeklyHasData) {
    // صادقانه: نبود منبع هفتگی ⇒ وتو صادر نمی‌شود، اما در audit شفاف گفته می‌شود.
    const last = gates[gates.length - 1];
    last.reason += ' (دادهٔ هفتگی MA52/RSI منتشر نشده؛ وتوی هفتگی ارزیابی نشد.)';
  }

  // ── گیت ۳: تابلوخوانی (فقط زمان‌سنج ورود) ────────────────────────
  const tape = input.tape;
  const tapeActive = tape != null && isActiveSignal(tape, now);
  const tapeSurge = tapeIsSurge(tape);
  const { pattern, volumeMultiple } = tapePattern(tape);
  if (!tape) {
    gates.push(mk('tape', 'pending', 'سیگنال تابلو منتشر نشده است؛ زمان‌سنج ورود بدون داده است.'));
  } else if (!tapeActive) {
    gates.push(mk('tape', 'pending', 'سیگنال تابلو منقضی است؛ زمان‌سنج ورود ارزیابی نشد.'));
  } else if (pattern === 'closing_auction_pop') {
    gates.push(mk('tape', 'passed', 'الگوی ساعت فعال است ⇒ زمان‌سنج ورود تایید شد.'));
  } else if (pattern === 'suspicious_volume') {
    gates.push(
      mk(
        'tape',
        'pending',
        `حجم مشکوک${volumeMultiple != null ? ` ${volumeMultiple} برابر میانگین` : ''} ⇒ تابلو فقط زمان‌سنج است؛ تصمیم‌ساز نیست.`,
      ),
    );
  } else {
    gates.push(mk('tape', 'pending', 'تایید نقدینگی تابلو وجود ندارد ⇒ ورود در انتظار زمان‌سنج.'));
  }

  // ── گیت ۴: سبد و رژیم ریسک ──────────────────────────────────────
  const cap = regime.industryCapPct > 0 ? regime.industryCapPct : DEFAULT_INDUSTRY_CAP_PCT;
  const warCap = regime.warRegime ? 20 : null;
  const overIndustry = regime.industryUsedPct != null && regime.industryUsedPct + (regime.symbolWeightPct ?? 0) > cap;
  const warOver = regime.warRegime && regime.symbolWeightPct != null && regime.symbolWeightPct > 10;
  if (warOver) {
    gates.push(
      mk(
        'portfolio',
        'blocked',
        `رژیم ریسک/جنگ فعال است و سقف ورود به سهام ${fa0(WAR_EQUITY_CAP_MIN_PCT)}٪ تا ${fa0(WAR_EQUITY_CAP_MAX_PCT)}٪ کل سرمایه است؛ وزن فعلی ${fa1(regime.symbolWeightPct)}٪ مجاز نیست.`,
      ),
    );
  } else if (overIndustry) {
    gates.push(
      mk(
        'portfolio',
        'blocked',
        `وزن صنعت با این نماد از سقف ${fa0(cap)}٪ می‌گذرد (مصرف فعلی ${fa1(regime.industryUsedPct)}٪) ⇒ گیت سبد مسدود شد.`,
      ),
    );
  } else if (regime.inBasket === true) {
    gates.push(mk('portfolio', 'passed', 'نماد در سبد است و ظرفیت صنعت برای پله‌بندی باز است.'));
  } else if (regime.industryUsedPct == null && regime.inBasket == null) {
    gates.push(mk('portfolio', 'pending', 'وضعیت سبد/صنعت نامشخص است؛ گیت سبد محافظه‌کارانه در انتظار است.'));
  } else {
    gates.push(
      mk('portfolio', 'passed', `ظرفیت صنعت آزاد است (مصرف ${fa1(regime.industryUsedPct ?? 0)}٪ از سقف ${fa0(cap)}٪${warCap != null ? ' · رژیم جنگی فعال' : ''}).`),
    );
  }

  return {
    gates,
    weekly,
    weeklyVeto,
    weeklyHasData,
    fundamentalBlocked,
    tapeSurge,
  };
}

// ─── بج تصمیم نهایی با ۴ وضعیت قطعی ────────────────────────────────────────

export type DefiniteAction = 'ladder_buy' | 'high_risk_swing' | 'watch' | 'veto' | 'veto_gate1' | 'veto_gate2';

export const DEFINITE_ACTION_FA: Record<DefiniteAction, string> = {
  ladder_buy: 'خرید پله‌ای',
  high_risk_swing: 'نوسانگیری با ریسک بالا',
  watch: 'تحت پایش/انتظار',
  veto: 'رد قطعی (وتو)',
  veto_gate1: 'وتو در گیت ۱ (توقف تا شفافیت بنیادی)',
  veto_gate2: 'وتو در گیت ۲ (توقف تا شکست تکنیکال)',
};

export type DefiniteDecision = {
  action: DefiniteAction;
  label: string;
  reason: string;
  /** آیا هر چهار گیت سبز است؟ */
  allGatesPassed: boolean;
};

/** تصمیم قطعی از گیت‌ها — بدون میانگین خطی و بدون بازتوزیع وزن؛ فقط قواعد قطعی */
export function definiteDecision(res: StrictGatesResult): DefiniteDecision {
  const byId = new Map(res.gates.map((g) => [g.id, g]));
  const passedCount = res.gates.filter((g) => g.state === 'passed').length;
  const allGatesPassed = passedCount === res.gates.length;
  const fund = byId.get('fundamental');
  const tech = byId.get('technical');

  if (res.weeklyVeto) {
    return {
      action: 'veto',
      label: DEFINITE_ACTION_FA.veto,
      reason: 'روند هفتگی صعودی نیست ⇒ وتوی فوری؛ هر ورودی رد می‌شود.',
      allGatesPassed: false,
    };
  }
  if (res.fundamentalBlocked) {
    if (res.tapeSurge) {
      return {
        action: 'high_risk_swing',
        label: DEFINITE_ACTION_FA.high_risk_swing,
        reason: 'نقض بنیادی، ورود روندی را مسدود کرده است؛ تنها با جهش تابلو، «نوسانگیری صرفاً با حجم سبک» مجاز است.',
        allGatesPassed: false,
      };
    }
    return {
      action: 'watch',
      label: DEFINITE_ACTION_FA.watch,
      reason: 'نقض بنیادی ⇒ ورود روندی مسدود و جهش تابلویی هم دیده نشده؛ سهم فقط تحت پایش است.',
      allGatesPassed: false,
    };
  }

  // وتوی سخت‌گیرانه: بدون شفافیت بنیادی (گیت ۱) یا بدون شکست تکنیکال (گیت ۲)،
  // نمرهٔ نهایی از بازتوزیع وزن تابلو/پرتفو ساخته نمی‌شود.
  if (fund?.state === 'pending') {
    return {
      action: 'veto_gate1',
      label: DEFINITE_ACTION_FA.veto_gate1,
      reason: `گیت ۱ (بنیاد) تایید نشده است: ${fund.reason} تا شفافیت بنیادی، نمرهٔ بازتوزیعی وزن‌ها معتبر نیست و ورود متوقف می‌ماند.`,
      allGatesPassed: false,
    };
  }
  if (tech?.state === 'pending') {
    return {
      action: 'veto_gate2',
      label: DEFINITE_ACTION_FA.veto_gate2,
      reason: `گیت ۲ (تکنیکال) تایید نشده است: ${tech.reason} تا شکست/تایید تکنیکال، نمرهٔ بازتوزیعی وزن‌ها معتبر نیست.`,
      allGatesPassed: false,
    };
  }

  if (allGatesPassed) {
    return {
      action: 'ladder_buy',
      label: DEFINITE_ACTION_FA.ladder_buy,
      reason: 'هر چهار گیت (بنیاد، تکنیکال، تابلو، سبد/رژیم) هم‌زمان سبز است ⇒ خرید پله‌ای مجاز.',
      allGatesPassed: true,
    };
  }
  const blockers = res.gates.filter((g) => g.state !== 'passed');
  const tape = byId.get('tape');
  return {
    action: 'watch',
    label: DEFINITE_ACTION_FA.watch,
    reason:
      `گیت‌های بدون تایید: ${blockers.map((g) => g.label).join('، ')}` +
      (tape?.state === 'pending' ? ' — تابلو فقط زمان‌سنج ورود است.' : '.'),
    allGatesPassed: false,
  };
}

/** سوییچ اهرم ساعت شنی: سهام سوپر‌بنیادی + (هفتگی زیر MA52 و RSI≤۳۰) ⇒ حجم ۲ تا ۴ برابر */
export type HourglassSwitch = {
  active: boolean;
  /** مضرب پیشنهادی حجم (۲..۴) یا null در نبود شرط */
  volumeMultiple: number | null;
  reason: string;
};

export const HOURGLASS_RSI_MAX = 30;
export const HOURGLASS_VOLUME_MIN = 2;
export const HOURGLASS_VOLUME_MAX = 4;

export function hourglassSwitch(args: {
  superFundamental: boolean;
  weekly: WeeklyTrendInput;
  fundScore: number | null;
}): HourglassSwitch {
  const { superFundamental, weekly, fundScore } = args;
  if (!superFundamental) {
    return { active: false, volumeMultiple: null, reason: 'نماد در فهرست سوپر‌بنیادی نیست؛ سوییچ اهرم ساعت شنی خاموش است.' };
  }
  if (weekly.belowMa52 == null || weekly.rsi == null) {
    return {
      active: false,
      volumeMultiple: null,
      reason: 'دادهٔ هفتگی (زیر MA52 و RSI) منتشر نشده؛ شرط سوییچ ساعت شنی قابل ارزیابی نیست.',
    };
  }
  if (weekly.belowMa52 && weekly.rsi <= HOURGLASS_RSI_MAX) {
    // شدت اشباع فروش: هرچه RSI پایین‌تر، مضرب بالاتر (۲ تا ۴)
    const t = (HOURGLASS_RSI_MAX - weekly.rsi) / HOURGLASS_RSI_MAX;
    const mult = Math.round((HOURGLASS_VOLUME_MIN + t * (HOURGLASS_VOLUME_MAX - HOURGLASS_VOLUME_MIN)) * 10) / 10;
    return {
      active: true,
      volumeMultiple: Math.min(HOURGLASS_VOLUME_MAX, Math.max(HOURGLASS_VOLUME_MIN, mult)),
      reason: `قیمت هفتگی زیر MA52 و RSI هفتگی ${fa1(weekly.rsi)} (≤ ${fa0(HOURGLASS_RSI_MAX)}) است ⇒ خرید دورهٔ جاری ${fa1(mult)} برابر${fundScore != null ? ` (نمرهٔ بنیادی ${fa0(fundScore)})` : ''}.`,
    };
  }
  return {
    active: false,
    volumeMultiple: null,
    reason: `شرط سوییچ برقرار نیست (زیر MA52: ${weekly.belowMa52 ? 'بله' : 'خیر'} · RSI هفتگی ${fa1(weekly.rsi)}).`,
  };
}

/** سقف ورود به سهام در رژیم ریسک/جنگ (۱۰ تا ۲۰ درصد کل سرمایه) */
export const WAR_EQUITY_CAP_MIN_PCT = 10;
export const WAR_EQUITY_CAP_MAX_PCT = 20;

export function warRegimeCap(active: boolean): { min: number; max: number } | null {
  return active ? { min: WAR_EQUITY_CAP_MIN_PCT, max: WAR_EQUITY_CAP_MAX_PCT } : null;
}

/** سهم ظرفیت صنعت برای وزن‌دهی پله: min(وزن پله, ظرفیت باقی‌ماندهٔ صنعت) */
export function effectiveStepWeightPct(stepWeightPct: number, industryRemainingPct: number | null): number {
  if (industryRemainingPct == null) return stepWeightPct;
  return Math.max(0, Math.round(Math.min(stepWeightPct, industryRemainingPct) * 10) / 10);
}

/** آستانهٔ «سهام سوپر‌بنیادی» برای سوییچ اهرم ساعت شنی */
export const SUPER_FUNDAMENTAL_SCORE = 80;

export function isSuperFundamental(fund: AgentSignal | undefined): boolean {
  if (!fund) return false;
  if (fund.direction !== 'bullish') return false;
  return typeof fund.score === 'number' && fund.score >= SUPER_FUNDAMENTAL_SCORE;
}
