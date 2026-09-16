// features/master/lib/managementSummary.ts -- خلاصهٔ تحلیلی مدیریتی، کاملاً آفلاین
// Rule-Based NLG: فقط قالب‌های شرطی روی state داوری — هیچ API یا مدل بیرونی.
// لحن مالی شفاف؛ هر جمله از دادهٔ موجود ساخته می‌شود و در نبود داده صادقانه می‌گوید.
import { toFaDigits } from '@shared/lib/fmt';
import { fa0, fa1 } from './fmtNum';
import type { MasterVerdict } from '@contracts/master';
import type { AgentSignal } from '@contracts/signal';
import type { BusInput } from './masterMath';
import { signedScore } from './masterMath';
import {
  DEFINITE_ACTION_FA,
  type DefiniteDecision,
  type HourglassSwitch,
  type StrictGate,
  type StrictGatesResult,
  hourglassSwitch,
  warRegimeCap,
} from './strictGates';

export type SummaryLine = {
  id: 'verdict' | 'conflict' | 'regime' | 'switch' | 'next';
  title: string;
  text: string;
  tone: 'green' | 'red' | 'yellow' | 'blue' | 'gray';
};

const AGENT_FA: Record<string, string> = {
  fundamental: 'بنیادی',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'پرتفوی',
};

function fa(x: number, digits = 1): string {
  return toFaDigits(Number(x.toFixed(digits)));
}

function dirFa(s: AgentSignal | undefined): string {
  if (!s) return 'بی‌رأی';
  if (s.direction === 'bullish') return 'صعودی';
  if (s.direction === 'bearish') return 'نزولی';
  return 'خنثی';
}

/**
 * جملات خلاصهٔ مدیریتی — قانون‌محور و قابل تست.
 * ترتیب ثابت: حکم → تعارض لایه‌ها → رژیم ریسک → سوییچ ساعت شنی → اقدام بعدی.
 */
export function buildManagementSummary(args: {
  symbol: string;
  verdict: MasterVerdict;
  input: BusInput;
  strict: StrictGatesResult;
  decision: DefiniteDecision;
  warRegime: boolean;
  superFundamental: boolean;
  industryCapPct: number;
}): SummaryLine[] {
  const { symbol, verdict, input, strict, decision, warRegime, superFundamental, industryCapPct } = args;
  const lines: SummaryLine[] = [];

  // ۱) حکم قطعی
  lines.push({
    id: 'verdict',
    title: 'حکم مدیریتی',
    text:
      decision.action === 'ladder_buy'
        ? `${symbol}: هر چهار گیت هم‌زمان سبز است؛ ورود پله‌ای طبق برنامهٔ زیر مجاز می‌شود.`
        : decision.action === 'veto'
          ? `${symbol}: وتوی سخت‌گیرانه فعال است؛ تا رفع مانع، هیچ ورودی مجاز نیست.`
          : decision.action === 'high_risk_swing'
            ? `${symbol}: ورود روندی مسدود است؛ تنها نوسانگیری سبک با حجم کنترل‌شده مجاز است.`
            : `${symbol}: در وضعیت پایش است؛ ورود تا تکمیل تایید لایه‌ها به تعویق می‌افتد.`,
    tone:
      decision.action === 'ladder_buy'
        ? 'green'
        : decision.action === 'veto'
          ? 'red'
          : decision.action === 'high_risk_swing'
            ? 'yellow'
            : 'blue',
  });

  // ۲) تعارض لایه‌ها با لحن مالی
  const fund = input.fundamental;
  const tech = input.technical;
  const tape = input.tape;
  const conflictBits: string[] = [];
  if (fund && tech) {
    const fs = signedScore(fund);
    const ts = signedScore(tech);
    if (fs > 20 && ts < -20) {
      conflictBits.push(
        `بنیادی (${dirFa(fund)}، نمرهٔ ${fa(Math.abs(fs), 0)}) در برابر تکنیکال (${dirFa(tech)}) ایستاده است؛ شکاف ${fa(Math.abs(fs - ts), 0)} واحدی، ورود پله‌ای را به تایید زمان‌سنج گره می‌زند.`,
      );
    } else if (ts > 20 && fs < -20) {
      conflictBits.push(
        `ستاپ تکنیکال جذاب است اما بنیادی (نمرهٔ ${fa(Math.abs(fs), 0)}) آن را پشتیبانی نمی‌کند؛ بنیاد ضعیف، ستاپ را فاقد اعتبار سرمایه‌ای می‌کند.`,
      );
    } else if (fs > 0 && ts > 0) {
      conflictBits.push('بنیادی و تکنیکال هم‌جهت‌اند؛ ریسک تناقض افق زمانی فعلاً پایین است.');
    } else if (fs < 0 && ts < 0) {
      conflictBits.push('هر دو لایهٔ بنیادی و تکنیکال ضعیف‌اند؛ بازده ریسک‌پذیر نیست.');
    }
  } else {
    conflictBits.push('برای سنجش تعارض لایه‌ها به هر دو سیگنال بنیادی و تکنیکال فعال نیاز است.');
  }
  if (tape && (tape.payload as { pattern?: string } | null)?.pattern === 'suspicious_volume') {
    conflictBits.push('تابلو حجم مشکوک نشان می‌دهد؛ این نشانه زمان‌سنج است، نه مجوز ورود.');
  }
  if (verdict.hasConflict) {
    conflictBits.push('تضاد افق زمانی باعث تنزیل اطمینان برآیند شد.');
  }
  lines.push({
    id: 'conflict',
    title: 'تعارض لایه‌ها',
    text: conflictBits.join(' '),
    tone: verdict.hasConflict ? 'yellow' : 'gray',
  });

  // ۳) رژیم ریسک/جنگ
  const cap = warRegimeCap(warRegime);
  lines.push({
    id: 'regime',
    title: 'رژیم ریسک',
    text: cap
      ? `رژیم ریسک/جنگ فعال است: سقف ورود به سهام ${toFaDigits(cap.min)}٪ تا ${toFaDigits(cap.max)}٪ کل سرمایه است و پوشش طلا/دلار (۲ تا ۳ برابر ارزش بورسی) الزامی است.`
      : `رژیم نرمال است؛ سقف تمرکز هر صنعت ${toFaDigits(industryCapPct)}٪ و سقف هر تک‌سهم ${toFaDigits(20)}٪ پابرجاست.`,
    tone: cap ? 'yellow' : 'gray',
  });

  // ۴) سوییچ اهرم ساعت شنی
  const sw: HourglassSwitch = hourglassSwitch({
    superFundamental,
    weekly: strict.weekly,
    fundScore: typeof fund?.score === 'number' ? fund.score : null,
  });
  lines.push({
    id: 'switch',
    title: 'سوییچ اهرم ساعت شنی',
    text: sw.active
      ? `${sw.reason} حجم پیشنهادی ${toFaDigits(sw.volumeMultiple ?? 0)} برابر حالت عادی است.`
      : sw.reason,
    tone: sw.active ? 'green' : 'gray',
  });

  // ۵) اقدام بعدی — کدام گیت مانع است
  const blockers = strict.gates.filter((g) => g.state !== 'passed');
  lines.push({
    id: 'next',
    title: 'اقدام بعدی',
    text:
      blockers.length === 0
        ? 'هیچ مانعی باقی نیست؛ برنامهٔ معاملاتی پایین را طبق پله‌ها اجرا کن.'
        : `مانع‌های فعلی: ${blockers.map((g) => `${g.label} (${g.reason})`).join(' · ')}`,
    tone: decision.action === 'ladder_buy' ? 'green' : 'blue',
  });

  return lines;
}

export type ArbitrationLabel = {
  text: string;
  tone: 'green' | 'red' | 'yellow' | 'gray' | 'blue';
};

/** برچسب وضعیت هر لایه به‌جای خط تیره — داده‌محور و صادقانه */
export function layerStatusLabel(
  agentId: 'fundamental' | 'technical' | 'tape' | 'portfolio',
  signal: AgentSignal | undefined,
  extra?: { volumeMultiple?: number | null; suspended?: boolean },
): ArbitrationLabel {
  if (!signal) return { text: `${AGENT_FA[agentId]} منتشر نشده`, tone: 'gray' };
  const p = (signal.payload ?? {}) as Record<string, unknown>;
  const setups = Array.isArray(p.setups) ? (p.setups as string[]) : [];
  const pattern = typeof p.pattern === 'string' ? p.pattern : null;

  if (signal.direction === 'bearish') {
    return { text: agentId === 'fundamental' ? 'نقض بنیادی · ورود مسدود' : 'ساختار نزولی', tone: 'red' };
  }
  if (agentId === 'fundamental') {
    const margin = typeof p.margin_pct === 'number' ? (p.margin_pct as number) : null;
    if (margin != null && margin < 20) return { text: `حاشیهٔ سود ${fa1(margin)}٪ · زیر کف`, tone: 'red' };
    if (margin != null) return { text: `حاشیهٔ سود تایید (${fa1(margin)}٪)`, tone: 'green' };
    return { text: 'بنیاد بدون نقض آشکار', tone: 'green' };
  }
  if (agentId === 'technical') {
    if (setups.includes('breakout') || setups.includes('pullback') || setups.includes('choch')) {
      return { text: 'ستاپ ورود فعال', tone: 'green' };
    }
    return { text: 'در انتظار شکست مقاومت', tone: 'yellow' };
  }
  if (agentId === 'tape') {
    const mult = extra?.volumeMultiple ?? (typeof p.volumeMultiple === 'number' ? p.volumeMultiple : null);
    if (pattern === 'closing_auction_pop') return { text: 'زمان‌سنج ورود تایید (الگوی ساعت)', tone: 'green' };
    if (pattern === 'suspicious_volume') {
      return { text: mult != null ? `حجم مشکوک ${fa1(mult)} برابر` : 'حجم مشکوک', tone: 'yellow' };
    }
    return { text: 'زمان‌سنج ورود بی‌تایید', tone: 'gray' };
  }
  const decision = p.decision;
  if (decision === 'accept') return { text: 'در سبد · ظرفیت باز', tone: 'green' };
  if (decision === 'monitor') return { text: 'زیر نظر سبد', tone: 'yellow' };
  if (decision === 'reject') return { text: 'از سبد حذف‌شده', tone: 'red' };
  return { text: 'خارج از سبد', tone: 'gray' };
}

/** خروج ۵۰٪ در مقاومت ماژور/سقف سوم با تایید بنیادی */
export type HalfExitPlan = {
  active: boolean;
  text: string;
  /** قیمت مقاومت مرجع (اگر داده باشد) */
  resistance: number | null;
};

export function halfExitPlan(args: {
  resistance: number | null;
  setupActive: boolean;
  fundamentalOk: boolean;
  currentPrice: number | null;
}): HalfExitPlan {
  const { resistance, setupActive, fundamentalOk, currentPrice } = args;
  if (resistance == null) {
    return { active: false, text: 'دادهٔ مقاومت استاتیک در دسترس نیست؛ پلن خروج ۵۰٪ ارزیابی نشد.', resistance: null };
  }
  const reached = currentPrice != null ? currentPrice >= resistance : null;
  if (setupActive && fundamentalOk) {
    return {
      active: true,
      text: `${reached === true ? 'قیمت به مقاومت رسیده' : 'در برخورد با مقاومت ماژور'} و تایید بنیادی برقرار است ⇒ اصل پول را خارج کن و ۵۰٪ سود را نگه دار.`,
      resistance,
    };
  }
  return {
    active: false,
    text: `تایید بنیادی/ستاپ برای خروج در مقاومت کامل نیست ⇒ خروج ۵۰٪ هنوز فعال نیست (مقاومت مرجع ${fa0(resistance)}).`,
    resistance,
  };
}

export const DEFINITE_LABELS = DEFINITE_ACTION_FA;

export type { StrictGate };
