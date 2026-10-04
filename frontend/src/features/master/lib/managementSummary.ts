// features/master/lib/managementSummary.ts -- خلاصهٔ تحلیلی مدیریتی، کاملاً آفلاین
// Rule-Based NLG: فقط قالب‌های شرطی روی state داوری — هیچ API یا مدل بیرونی.
// لحن مالی شفاف؛ هر جمله از دادهٔ موجود ساخته می‌شود و در نبود داده صادقانه می‌گوید.
import { toFaDigits } from '@shared/lib/fmt';
import { fa0, fa1 } from './fmtNum';
import type { MasterVerdict } from '@contracts/master';
import type { AgentSignal } from '@contracts/signal';
import { ftsScoreOf } from '@contracts/fundamental';
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
  id: 'verdict' | 'scenario' | 'conflict' | 'regime' | 'switch' | 'next';
  title: string;
  text: string;
  tone: 'green' | 'red' | 'yellow' | 'blue' | 'gray';
};

export type MarketScenario = {
  name: string;
  title: string;
  description: string;
  tone: 'green' | 'red' | 'yellow' | 'blue';
};

/** پوشش کامل حداقل ۸ سناریوی محتمل و واقع‌گرایانه بازار */
export function detectMarketScenario(args: {
  symbol: string;
  input: BusInput;
  strict: StrictGatesResult;
  decision: DefiniteDecision;
  superFundamental: boolean;
  warRegime: boolean;
  currentPrice?: number | null;
  resistancePrice?: number | null;
}): MarketScenario {
  const { symbol, input, strict, decision, superFundamental, warRegime, currentPrice, resistancePrice } = args;
  const fund = input.fundamental;
  const tech = input.technical;
  const tape = input.tape;
  const tapePat = (tape?.payload as { pattern?: string } | null)?.pattern;

  // ۱. سناریو ۵: فرصت خرید عمیق (Deep Hourglass)
  if (superFundamental && strict.weekly.belowMa52 && (strict.weekly.rsi != null && strict.weekly.rsi <= 30)) {
    return {
      name: 'deep_hourglass',
      title: 'فرصت خرید عمیق (Deep Hourglass)',
      description: `نماد ${symbol} سهمی سوپربنیادی در کف ماژور با RSI هفتگی زیر ۳۰ است؛ فرصت استثنایی برای فعال‌سازی اهرم ساعت شنی با خرید سنگین (۲ تا ۴ برابر حجم عادی) مهیاست.`,
      tone: 'green',
    };
  }

  // ۲. سناریو ۱: تله ارزش (Value Trap)
  const fundGood = fund != null && (fund.direction === 'bullish' || (typeof fund.score === 'number' && fund.score >= 60));
  const techBad = strict.weeklyVeto || (tech != null && tech.direction === 'bearish');
  if (fundGood && techBad) {
    return {
      name: 'value_trap',
      title: 'تله ارزش (Value Trap)',
      description: `بنیاد و صورت‌های مالی سهم ممتاز است، اما نمودار زیر میانگین یا درگیر ساختار نزولی است؛ خرید اکیداً ممنوع بوده و تا تایید کف و برگشت پول باید صبر کرد.`,
      tone: 'red',
    };
  }

  // ۳. سناریو ۲: تله پامپ تابلو (Pump Trap)
  const isTapePump = strict.tapeSurge || tapePat === 'closing_auction_pop' || tapePat === 'suspicious_volume';
  if (strict.fundamentalBlocked && isTapePump) {
    return {
      name: 'pump_trap',
      title: 'تله پامپ تابلو (Pump Trap)',
      description: `ورود پول سنگین و تحرکات تابلویی روی نمادی با نقص یا زیان بنیادی آشکار است؛ ورود روندی اکیداً ممنوع بوده و صرفاً نوسان‌گیری کوتاه‌مدت فوق‌العاده سبک مجاز است.`,
      tone: 'yellow',
    };
  }

  // ۴. سناریو ۶: رژیم جنگی (War Regime)
  if (warRegime) {
    return {
      name: 'war_regime',
      title: 'رژیم جنگی (War Regime)',
      description: `به دلیل تنش‌های ژئوپلیتیک و ریسک سیستماتیک، سقف ورود به سهام به ۱۰٪ تا ۲۰٪ محدود شده و پوشش دارایی امن (طلا و دلار) الزامی است.`,
      tone: 'yellow',
    };
  }

  // ۵. سناریو ۷: سقف صنعت سبد (Industry Cap)
  const portGate = strict.gates.find((g) => g.id === 'portfolio');
  if (portGate?.state === 'blocked') {
    return {
      name: 'industry_cap',
      title: 'سقف صنعت سبد (Industry Cap)',
      description: `ظرفیت مجاز این صنعت در پورتفولیو تکمیل شده است؛ انضباط مدیریت ریسک، مانع خرید پله جدید در این گروه است حتی اگر سهم سیگنال مثبت داشته باشد.`,
      tone: 'red',
    };
  }

  // ۶. سناریو ۸: حفظ سود ۵۰٪ (Half Profit Preservation)
  if (currentPrice != null && resistancePrice != null && resistancePrice > 0 && currentPrice >= resistancePrice * 0.98) {
    return {
      name: 'half_profit',
      title: 'حفظ سود ۵۰٪ (Half Profit Preservation)',
      description: `قیمت به تراز مقاومت ماژور (${fa0(resistancePrice)} ریال) رسیده است؛ برای مصون‌سازی سود، خروج اصل سرمایه و نگهداری ۵۰٪ سود توصیه می‌شود.`,
      tone: 'blue',
    };
  }

  // ۷. سناریو ۳: توقف در سد مقاومت (Resistance Wall)
  if (currentPrice != null && resistancePrice != null && resistancePrice > currentPrice) {
    const distPct = ((resistancePrice - currentPrice) / currentPrice) * 100;
    if (distPct < 5) {
      return {
        name: 'resistance_wall',
        title: 'توقف در سد مقاومت (Resistance Wall)',
        description: `فاصله با مقاومت پیش‌رو کمتر از ۵٪ است (${fa1(distPct)}٪ تا ${fa0(resistancePrice)} ریال) و نسبت R/R نامساعد است؛ توقف تا شکست پرحجم سد مقاومت یا پولبک الزامی است.`,
        tone: 'yellow',
      };
    }
  }

  // ۸. سناریو ۴: پرتاب ستاپ جت (Jet Breakout)
  if (decision.action === 'ladder_buy' && isTapePump) {
    return {
      name: 'jet_breakout',
      title: 'پرتاب ستاپ جت (Jet Breakout)',
      description: `شکست معتبر سقف قیمتی همگام با حجم ۳ برابری و سرانه خریدار سنگین فعال شده است؛ فیلترهای ۴گانه تایید شده و ستاپ پرتاب جت آماده ورود است.`,
      tone: 'green',
    };
  }

  // حالت پیش‌فرض بر مبنای تصمیم فیلترها
  if (decision.allGatesPassed) {
    return {
      name: 'four_filters_aligned',
      title: 'هم‌پوشانی فیلترهای ۴گانه',
      description: `هر چهار فیلتر (بنیاد، تکنیکال، تابلو و سبد) هم‌راستا هستند؛ ورود پله‌ای طبق جدول پله‌بندی مجاز است.`,
      tone: 'green',
    };
  }
  return {
    name: 'filter_watch',
    title: 'پایش ساختار و فیلترها',
    description: `سهم در حال حاضر در فاز تجمیع یا انتظار تریگر فیلترها قرار دارد؛ ورود روندی تا صدور سیگنال هم‌زمان متوقف است.`,
    tone: 'blue',
  };
}

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
 * ترتیب: حکم → سناریوی بازار → ارکان تحلیلی → رژیم ریسک → سوییچ ساعت شنی → اقدام بعدی.
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
  currentPrice?: number | null;
  resistancePrice?: number | null;
}): SummaryLine[] {
  const { symbol, verdict, input, strict, decision, warRegime, superFundamental, industryCapPct, currentPrice, resistancePrice } = args;
  const lines: SummaryLine[] = [];

  // ۱) حکم قطعی
  lines.push({
    id: 'verdict',
    title: 'حکم مدیریتی',
    text:
      decision.action === 'ladder_buy'
        ? `${symbol}: هر چهار فیلتر هم‌زمان سبز است؛ ورود پله‌ای طبق برنامهٔ زیر مجاز می‌شود.`
        : decision.action === 'veto'
          ? `${symbol}: وتوی سخت‌گیرانه فعال است؛ تا رفع مانع، هیچ ورودی مجاز نیست.`
          : decision.action === 'high_risk_swing'
            ? `${symbol}: ورود روندی مسدود است؛ تنها نوسانگیری سبک با حجم کنترل‌شده مجاز است.`
            : `${symbol}: در وضعیت پایش است؛ ورود تا تکمیل تایید ارکان تحلیلی به تعویق می‌افتد.`,
    tone:
      decision.action === 'ladder_buy'
        ? 'green'
        : decision.action === 'veto'
          ? 'red'
          : decision.action === 'high_risk_swing'
            ? 'yellow'
            : 'blue',
  });

  // ۲) سناریوی محتمل بازار (یکی از ۸ سناریو)
  const scenario = detectMarketScenario({
    symbol,
    input,
    strict,
    decision,
    superFundamental,
    warRegime,
    currentPrice,
    resistancePrice,
  });
  lines.push({
    id: 'scenario',
    title: `سناریوی بازار: ${scenario.title}`,
    text: scenario.description,
    tone: scenario.tone,
  });

  // ۳) تعارض ارکان تحلیلی با لحن مالی
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
      conflictBits.push('هر دو رکن بنیادی و تکنیکال ضعیف‌اند؛ بازده ریسک‌پذیر نیست.');
    }
  } else {
    conflictBits.push('برای سنجش هم‌راستایی ارکان تحلیلی به هر دو سیگنال بنیادی و تکنیکال فعال نیاز است.');
  }
  if (tape && (tape.payload as { pattern?: string } | null)?.pattern === 'suspicious_volume') {
    conflictBits.push('تابلو حجم مشکوک نشان می‌دهد؛ این نشانه زمان‌سنج است، نه مجوز ورود.');
  }
  if (verdict.hasConflict) {
    conflictBits.push('تضاد افق زمانی باعث تنزیل اطمینان برآیند شد.');
  }
  lines.push({
    id: 'conflict',
    title: 'ارکان تحلیلی',
    text: conflictBits.join(' '),
    tone: verdict.hasConflict ? 'yellow' : 'gray',
  });

  // ۴) رژیم ریسک/جنگ
  const cap = warRegimeCap(warRegime);
  lines.push({
    id: 'regime',
    title: 'رژیم ریسک',
    text: cap
      ? `رژیم ریسک/جنگ فعال است: سقف ورود به سهام ${toFaDigits(cap.min)}٪ تا ${toFaDigits(cap.max)}٪ کل سرمایه است و پوشش طلا/دلار (۲ تا ۳ برابر ارزش بورسی) الزامی است.`
      : `رژیم نرمال است؛ سقف تمرکز هر صنعت ${toFaDigits(industryCapPct)}٪ و سقف هر تک‌سهم ${toFaDigits(20)}٪ پابرجاست.`,
    tone: cap ? 'yellow' : 'gray',
  });

  // ۵) سوییچ اهرم ساعت شنی
  const sw: HourglassSwitch = hourglassSwitch({
    superFundamental,
    weekly: strict.weekly,
    fundScore: ftsScoreOf(fund),
  });
  lines.push({
    id: 'switch',
    title: 'سوییچ اهرم ساعت شنی',
    text: sw.active
      ? `${sw.reason} حجم پیشنهادی ${toFaDigits(sw.volumeMultiple ?? 0)} برابر حالت عادی است.`
      : sw.reason,
    tone: sw.active ? 'green' : 'gray',
  });

  // ۶) اقدام بعدی — کدام فیلتر مانع است
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
      text: `${reached === true ? 'قیمت به مقاومت رسیده' : 'در برخورد با مقاومت ماژور'} و تایید بنیادی برقرار است؛ پس اصل پول را خارج کن و ۵۰٪ سود را نگه دار.`,
      resistance,
    };
  }
  return {
    active: false,
    text: `تایید بنیادی/ستاپ برای خروج در مقاومت کامل نیست؛ پس خروج ۵۰٪ هنوز فعال نیست (مقاومت مرجع ${fa0(resistance)}).`,
    resistance,
  };
}

export const DEFINITE_LABELS = DEFINITE_ACTION_FA;

export type { StrictGate };
