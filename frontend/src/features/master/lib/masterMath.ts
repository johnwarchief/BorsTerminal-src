// features/master/lib/masterMath.ts -- موتور تجمیع وزنی با بازتوزیع پویا
// v2 (بازطراحی مستر): وزن موثر EffectiveWeight_i = Weight_i / Sum(ActiveWeights)
// + پایپ‌لاین گیتینگ سه‌گانه FTS (بنیادی ← تکنیکال ← تابلو) + متن synthesis قانون‌محور.
// امضاهای قبلی backward-compatible حفظ شده‌اند.
import { AGENT_WEIGHTS, isSignalExpired, type AgentId, type AgentSignal } from '@contracts/signal';
import { MasterVerdict, type FinalAction } from '@contracts/master';

export const CONFLICT_DAMPEN = 0.8;

export type BusInput = Partial<Record<AgentId, AgentSignal>>;

/** گیت‌های سه‌گانه FTS — ترتیب سلسله‌مراتبی داوری */
export type GateId = 'fundamental' | 'technical' | 'tape';

export type GateStatus = 'pass' | 'wait' | 'fail' | 'nodata' | 'missing';

export type GateFinding = {
  gate: GateId;
  status: GateStatus;
  /** توضیح فارسی قانون‌محور برای UI */
  note: string;
};

// ─── نمره علامت‌دار ───────────────────────────────────────────────────────

/** نمره علامت دار: صعودی مثبت و نزولی منفی و خنثی صفر */
export function signedScore(s: AgentSignal): number {
  if (s.score == null) return 0;
  if (s.direction === 'bullish') return s.score;
  if (s.direction === 'bearish') return -s.score;
  return 0;
}

function payloadQuality(s: AgentSignal): string | undefined {
  const p = s.payload as { dataQuality?: unknown } | null;
  return typeof p?.dataQuality === 'string' ? p.dataQuality : undefined;
}

/** فعال یعنی غیرمنقضی و داده دار و کامل */
export function isActiveSignal(s: AgentSignal, now = Date.now()): boolean {
  if (isSignalExpired(s, now)) return false;
  if (s.confidence === 'nodata') return false;
  if (payloadQuality(s) === 'incomplete') return false;
  return true;
}

// ─── وزن موثر: رفع باگ «(سهم ۰)» ─────────────────────────────────────────

/**
 * وزن موثر هر ایجنت: Weight_i / Sum(ActiveWeights).
 * ایجنت غیرفعال وزن صفر می‌گیرد (نه وزن خام) و وزن‌های فعال بازتوزیع می‌شوند
 * تا جمع وزن‌های موثر همیشه ۱ باشد.
 */
export function effectiveWeights(input: BusInput, now = Date.now()): Record<AgentId, number> {
  const agents: AgentId[] = ['fundamental', 'technical', 'tape', 'portfolio'];
  const raw: Record<AgentId, number> = { fundamental: 0, technical: 0, tape: 0, portfolio: 0 };
  const activeSum = agents.reduce((sum, a) => {
    const s = input[a];
    if (s && isActiveSignal(s, now)) {
      raw[a] = AGENT_WEIGHTS[a];
      return sum + AGENT_WEIGHTS[a];
    }
    return sum;
  }, 0);
  if (activeSum <= 0) return raw;
  const out = { ...raw };
  for (const a of agents) out[a] = raw[a] / activeSum;
  return out;
}

// ─── گیتینگ سه‌گانه FTS ──────────────────────────────────────────────────

type FundPayloadish = { passes?: Record<string, boolean> | null; dataQuality?: string };
type TechPayloadish = { setups?: string[]; stopLossPrice?: number | null; dataQuality?: string };
type TapePayloadish = { pattern?: string; volumeMultiple?: number | null };

/** گیت ۱ — بنیادی: شرط لازم. رد ⇒ سهم حداکثر «فاقد بنیاد/حذف‌شده» است، هرگز خرید نمی‌گیرد. */
export function fundamentalGate(fund: AgentSignal | undefined, now = Date.now()): GateFinding {
  if (!fund) return { gate: 'fundamental', status: 'missing', note: 'سیگنال بنیادی هنوز منتشر نشده است.' };
  if (isSignalExpired(fund, now)) return { gate: 'fundamental', status: 'missing', note: 'سیگنال بنیادی منقضی شده است.' };
  if (fund.confidence === 'nodata') return { gate: 'fundamental', status: 'nodata', note: 'داده بنیادی ناقص است؛ داوری بنیادی ممکن نیست.' };
  const p = fund.payload as FundPayloadish;
  if (p?.dataQuality === 'incomplete') return { gate: 'fundamental', status: 'nodata', note: 'داده بنیادی ناقص است؛ داوری بنیادی ممکن نیست.' };
  const rejected = fund.direction === 'bearish';
  if (rejected) return { gate: 'fundamental', status: 'fail', note: 'رد بنیادی: سهم حداکثر فاقد بنیاد/حذف‌شده است و هرگز خرید نمی‌گیرد.' };
  return { gate: 'fundamental', status: 'pass', note: 'شرط لازم بنیادی برقرار است.' };
}

/** آیا سیگنال تکنیکال داده ستاپ دارد؟ payload بدون ستاپ یعنی داده قدیمی/ساختگی */
function hasSetupData(tech: AgentSignal): boolean {
  const p = tech.payload as TechPayloadish;
  return Array.isArray(p?.setups);
}

/** آیا سیگنال تکنیکال ستاپ ورود مستقیم دارد (جت/پولبک)؟ */
export function hasEntrySetup(tech: AgentSignal): boolean {
  const p = tech.payload as TechPayloadish;
  const setups = Array.isArray(p?.setups) ? p.setups : [];
  return setups.includes('breakout') || setups.includes('pullback');
}

/** گیت ۲ — تکنیکال: موقعیت زمانی. جت/پولبک ⇒ ورود مستقیم؛ وگرنه «زیر نظر تا فیبو ۳۳-۴۰». */
export function technicalGate(tech: AgentSignal | undefined, now = Date.now()): GateFinding {
  if (!tech) return { gate: 'technical', status: 'missing', note: 'سیگنال تکنیکال هنوز منتشر نشده است.' };
  if (isSignalExpired(tech, now)) return { gate: 'technical', status: 'missing', note: 'سیگنال تکنیکال منقضی شده است.' };
  if (tech.confidence === 'nodata') return { gate: 'technical', status: 'nodata', note: 'داده تکنیکال موجود نیست.' };
  if (tech.direction === 'bearish') return { gate: 'technical', status: 'fail', note: 'ساختار تکنیکال نزولی است: ورود ممنوع.' };
  if (!hasSetupData(tech)) return { gate: 'technical', status: 'pass', note: 'ستاپ تکنیکال ثبت نشده؛ گیت زمانی اعمال نمی شود.' };
  if (hasEntrySetup(tech)) return { gate: 'technical', status: 'pass', note: 'ستاپ جت/پولبک فعال است: ورود مستقیم مجاز است.' };
  return { gate: 'technical', status: 'wait', note: 'ورود مستقیم نیست: زیر نظر تا اصلاح به فیبو ۳۳-۴۰ درصد.' };
}

/** گیت ۳ — تابلو: تأیید نهایی نقدینگی. حجم مشکوک + الگوی ساعت. */
export function tapeGate(tape: AgentSignal | undefined, now = Date.now()): GateFinding {
  if (!tape) return { gate: 'tape', status: 'missing', note: 'سیگنال تابلو هنوز منتشر نشده است.' };
  if (isSignalExpired(tape, now)) return { gate: 'tape', status: 'missing', note: 'سیگنال تابلو منقضی شده است.' };
  if (tape.confidence === 'nodata') return { gate: 'tape', status: 'nodata', note: 'داده تابلو موجود نیست.' };
  const p = tape.payload as TapePayloadish;
  const isClock = p?.pattern === 'closing_auction_pop';
  const isSusp = p?.pattern === 'suspicious_volume';
  if (isClock) return { gate: 'tape', status: 'pass', note: 'الگوی ساعت فعال است: تأیید نقدینگی کامل.' };
  if (isSusp) return { gate: 'tape', status: 'wait', note: 'حجم مشکوک هست ولی الگوی ساعت تایید نشده: ورود پله‌ای محافظه‌کارانه.' };
  return { gate: 'tape', status: 'wait', note: 'تایید نقدینگی تابلو ندارد: ورود فقط پله‌ای کوچک.' };
}

/** اجرای کامل پایپ‌لاین گیتینگ — خروجی برای UI و برای قید اقدام نهایی. */
export function runGatingPipeline(input: BusInput, now = Date.now()): GateFinding[] {
  return [
    fundamentalGate(input.fundamental, now),
    technicalGate(input.technical, now),
    tapeGate(input.tape, now),
  ];
}

/** اولین گیت شکست‌خورده (fail) — سهم پشت آن مانده است. null یعنی هیچ گیت fail نشده. */
export function blockingGate(gates: GateFinding[]): GateFinding | null {
  return gates.find((g) => g.status === 'fail') ?? null;
}

// ─── وضعیت نگهداری (Holding State) ───────────────────────────────────────

type PortfolioPayloadish = { decision?: unknown };

/**
 * آیا نماد در سبد فعلی است؟ رأی پرتفوی accept یعنی در سبد است.
 * غیب سیگنال/رأی یعنی در سبد نیست (محافظه‌کارانه).
 */
export function isHoldingInBasket(input: BusInput, now = Date.now()): boolean {
  return basketVote(input, now) === true;
}

/**
 * سه‌حالتیِ رأی سبد: true = در سبد (accept) · false = خارج از سبد (رأی فعال با تصمیم غیر از accept)
 * · null = سیگنال پرتفوی فعالی منتشر نشده — وضعیت سبد نامشخص و قید تنزل اعمال نمی‌شود.
 */
export function basketVote(input: BusInput, now = Date.now()): boolean | null {
  const port = input.portfolio;
  if (!port || !isActiveSignal(port, now)) return null;
  const p = port.payload as PortfolioPayloadish;
  return p?.decision === 'accept';
}

// ─── اعمال گیتینگ روی اقدام نهایی ────────────────────────────────────────

function isBuyAction(a: FinalAction): boolean {
  return a === 'buy' || a === 'strong_buy';
}

/**
 * قید گیتینگ روی اقدام نهایی:
 * - رد بنیادی (گیت ۱ fail) ⇒ هرگز خرید/خرید قوی/نگهداری؛ حداکثر «زیر نظر/کاهش/فروش».
 * - گیت تکنیکال fail ⇒ خرید به «زیر نظر» تنزل می‌کند.
 * - گیت تکنیکال wait (بدون ستاپ مستقیم) ⇒ خرید به «زیر نظر» تنزل می‌کند.
 * - وضعیت نگهداری: «نگهداری» فقط برای نمادهای موجود در سبد فعلی معتبر است؛
 *   نمادِ خارج از سبد (رأی پرتفوی فعالِ غیر accept) هرگز «نگهداری» نمی‌گیرد —
 *   حداکثر «زیر نظر» (در انتظار اصلاح/فیبو یا تریگر). null یعنی وضعیت سبد
 *   نامشخص (سیگنال پرتفوی منتشر نشده) ⇒ قید اعمال نمی‌شود.
 */
export function applyGateToAction(action: FinalAction, gates: GateFinding[], holdingInBasket: boolean | null = false): FinalAction {
  if (action === 'no_data') return action;
  const fund = gates.find((g) => g.gate === 'fundamental');
  const tech = gates.find((g) => g.gate === 'technical');

  let out = action;
  if (fund?.status === 'fail') {
    // رد بنیادی: سهم حداکثر «فاقد بنیاد/حذف‌شده» — خرید و نگهداری تازه ممنوع.
    if (isBuyAction(out)) out = 'watch';
    if (out === 'hold') out = 'reduce';
  }
  if (tech?.status === 'fail' && (isBuyAction(out) || out === 'hold')) out = 'watch';
  if (tech?.status === 'wait' && isBuyAction(out)) out = 'watch';

  // قید وضعیت نگهداری: نماد خارج از سبد بدون تریگر ورود هرگز «نگهداری» نیست.
  // «نگهداری» فقط برای نمادهای موجود در سبد فعلی (رأی پرتفوی accept) معتبر است؛
  // نماد خارج از سبد حتی با گیت بنیادی پاس‌شده، در انتظار تریگر ورود ⇒ «زیر نظر».
  if (holdingInBasket === false && out === 'hold') out = 'watch';
  return out;
}

// ─── سنthesis متن تضاد آرا (قانون‌محور) ──────────────────────────────────

const AGENT_FA_GATE: Record<GateId, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
};

/** جهت یک سیگنال برای زبان ساده */
function dirFa(s: AgentSignal | undefined): string {
  if (!s) return 'بی‌رأی';
  if (s.direction === 'bullish') return 'صعودی';
  if (s.direction === 'bearish') return 'نزولی';
  return 'خنثی';
}

/**
 * ساخت متن تحلیل داوری مستر از همان state داوری — قانون‌محور، نه LLM.
 * توضیح سادهٔ تعارض‌ها + پیشنهاد اکشن بر پایهٔ گیتینگ.
 */
export function synthesizeVerdict(
  symbol: string,
  input: BusInput,
  verdict: MasterVerdict,
  gates: GateFinding[],
  now = Date.now(),
): string {
  const parts: string[] = [];
  const fundActive = input.fundamental != null && isActiveSignal(input.fundamental, now);
  const techActive = input.technical != null && isActiveSignal(input.technical, now);
  const tapeActive = input.tape != null && isActiveSignal(input.tape, now);
  const activeCount = [fundActive, techActive, tapeActive].filter(Boolean).length;

  if (activeCount === 0) {
    return `برای ${symbol} هنوز هیچ رأی فعالی در دسترس نیست؛ ابتدا تب‌های بنیادی، تکنیکال و تابلو را باز کن.`;
  }

  // ۱) تعارض‌ها به زبان ساده
  const fund = input.fundamental;
  const tech = input.technical;
  const tape = input.tape;

  if (fundActive && techActive && fund && tech) {
    const fs = signedScore(fund);
    const ts = signedScore(tech);
    if (fs > 20 && ts < -20) {
      parts.push(`بنیادی ${dirFa(fund)} است اما تکنیکال ${dirFa(tech)} مانده؛ پیشنهاد مستر: ورود فقط پس از اصلاح تا پله اول فیبو ۳۳-۴۰ و تایید تکنیکال.`);
    } else if (ts > 20 && fs < -20) {
      parts.push(`تکنیکال ${dirFa(tech)} سیگنال داده اما بنیادی رد شده است؛ ستاپ بدون پشتوانه بنیادی اعتبار ندارد.`);
    }
  }
  if (tapeActive && techActive && tape && tech) {
    const tapeP = tape.payload as TapePayloadish;
    if (tapeP?.pattern === 'suspicious_volume' && tech.direction === 'neutral') {
      parts.push('تابلو با حجم مشکوک سیگنال ورود داده، اما سهم هنوز تریگر تکنیکال ندارد؛ ورود فقط پس از فعال شدن ستاپ یا اصلاح تا پله اول.');
    }
  }

  // ۲) وضعیت گیتینگ — کدام گیت مانده
  const waiting = gates.filter((g) => g.status === 'wait' || g.status === 'fail');
  for (const g of waiting) {
    if (g.status === 'fail') parts.push(`سهم پشت گیت ${AGENT_FA_GATE[g.gate]} مانده است: ${g.note}`);
  }

  // ۳) جمع‌بندی
  const blocked = blockingGate(gates);
  if (blocked) {
    parts.push(`حکم نهایی: به دلیل رد گیت ${AGENT_FA_GATE[blocked.gate]}، سهم تا رفع آن فقط «نگهداری/خروج» است و هرگز خرید نمی‌گیرد.`);
  } else if (verdict.hasConflict) {
    parts.push('به دلیل تضاد افق زمانی، اطمینان برآیند تنزیل شد؛ ورود پله‌ای با حجم کم پیشنهاد می‌شود.');
  } else if (activeCount === 3) {
    parts.push('هر سه گیت فعال و هم‌جهت‌اند؛ ورود پله‌ای طبق برنامه معاملاتی مجاز است.');
  }

  if (parts.length === 0) {
    parts.push(`برآیند فعلی برای ${symbol} ${verdict.finalAction === 'no_data' ? 'بدون داده است' : 'روشن است'}؛ آرای فعال در گیج بالا آمده است.`);
  }
  return parts.join(' ');
}

// ─── داوری اصلی ──────────────────────────────────────────────────────────

function toAction(normalized: number): FinalAction {
  if (normalized >= 75) return 'strong_buy';
  if (normalized >= 60) return 'buy';
  if (normalized >= 40) return 'hold';
  if (normalized >= 25) return 'sell';
  return 'strong_sell';
}

function round1(x: number): number {
  return Math.round(x * 10) / 10;
}

export function aggregateSignals(symbol: string, input: BusInput, now = Date.now()): MasterVerdict {
  const agents: AgentId[] = ['fundamental', 'technical', 'tape', 'portfolio'];
  const usedSignalIds: string[] = [];
  const discardedSignalIds: string[] = [];
  const contributions = agents.map((agentId) => {
    const s = input[agentId];
    if (!s) return { agentId, score: 0, signalCount: 0, confidence: 'nodata' as const };
    if (!isActiveSignal(s, now)) {
      discardedSignalIds.push(s.id);
      return { agentId, score: 0, signalCount: 0, confidence: s.confidence };
    }
    usedSignalIds.push(s.id);
    return { agentId, score: signedScore(s), signalCount: 1, confidence: s.confidence };
  });

  const activeWeight = agents.reduce(
    (sum, a) => sum + (usedSignalIds.some((id) => input[a]?.id === id) ? AGENT_WEIGHTS[a] : 0),
    0,
  );
  let composite = 0;
  if (activeWeight > 0) {
    let weighted = 0;
    for (const c of contributions) {
      const s = input[c.agentId];
      if (s && usedSignalIds.includes(s.id)) weighted += AGENT_WEIGHTS[c.agentId] * c.score;
    }
    composite = round1(weighted / activeWeight);
  }

  // تضاد افق زمانی: بنیادی داغ صعودی در برابر تکنیکال سرد و برعکس
  const fund = input.fundamental;
  const tech = input.technical;
  const fundHot = fund && usedSignalIds.includes(fund.id) && (fund.score ?? 0) > 70 && fund.direction === 'bullish';
  const fundCold = fund && usedSignalIds.includes(fund.id) && (fund.score ?? 100) < 30;
  const techHot = tech && usedSignalIds.includes(tech.id) && (tech.score ?? 0) > 70 && tech.direction === 'bullish';
  const techCold = tech && usedSignalIds.includes(tech.id) && (tech.score ?? 100) < 30;
  const hasConflict = Boolean((fundHot && techCold) || (techHot && fundCold));

  const dissent: MasterVerdict['dissent'] = [];
  if (hasConflict && fund && tech) {
    const gap = Math.max(0, Math.min(200, Math.abs(signedScore(fund) - signedScore(tech))));
    dissent.push({
      agents: ['fundamental', 'technical'],
      gap: round1(gap),
      note: 'تضاد افق زمانی: بنیادی و تکنیکال در دو جهت مخالف داوری کردند؛ اطمینان نهایی تنزیل شد.',
    });
    composite = round1(composite * CONFLICT_DAMPEN);
  }

  const hasAny = usedSignalIds.length > 0;
  const normalized = (composite + 100) / 2;
  const rawAction: FinalAction = hasAny ? toAction(normalized) : 'no_data';

  // v2: گیتینگ سه‌گانه روی اقدام نهایی اعمال می‌شود (رد بنیادی ⇒ هرگز خرید)
  // v3: وضعیت نگهداری — «نگهداری» فقط وقتی نماد در سبد فعلی است (رأی پرتفوی accept)؛
  // بدون رأی پرتفوی (null) قید تنزل اعمال نمی‌شود — محافظه‌کارانه با خط پایه.
  const gates = runGatingPipeline(input, now);
  const holding = basketVote(input, now);
  const finalAction = applyGateToAction(rawAction, gates, holding);

  return {
    symbol,
    ts: now,
    compositeScore: composite,
    finalAction,
    contributions,
    dissent,
    usedSignalIds,
    discardedSignalIds,
    hasConflict,
  };
}
