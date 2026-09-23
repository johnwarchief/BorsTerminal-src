// features/portfolio/model/portfolioSignals.ts -- سیگنال پرتفوی با وزن 1
// ورودی خالص: تصمیم ثبت شده کاربر و قیمت جاری تابلو.
// v2 (بازطراحی پرتفوی): نمادِ خارج از سبد به‌جای «بدون داده» رأی ظرفیت‌سنجی
// (Capacity Score) می‌دهد بر پایه قوانین مدیریت سرمایه FTS: سقف ۲۰٪ ریسک در
// یک صنعت + ظرفیت باقی‌مانده صنعت در سبد.
import { z } from 'zod';
import type { AgentSignal, Confidence, Direction } from '@contracts/signal';
import type { PortfolioPayload } from '@contracts/portfolio';
import { toFaDigits } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';

/** سقف تمرکز مجاز یک نماد در سبد به درصد */
export const CONCENTRATION_CAP_PCT = 25;
/** سقف ریسک یک صنعت در سبد — قانون مدیریت سرمایه FTS */
export const INDUSTRY_RISK_CAP_PCT = 20;
/** ماندگاری سیگنال پرتفوی: 7 روز */
export const PORTFOLIO_VALID_MS = 7 * 24 * 3600_000;

export const PortfolioDecisionSchema = z.object({
  symbol: z.string().min(1),
  status: z.string().nullish(),
  weight_eff_pct: z.number().nullish(),
  stop_loss: z.union([z.number(), z.string()]).nullish(),
  reason: z.string().nullish(),
  sector: z.string().nullish(),
  price: z.number().nullish(),
  name: z.string().nullish(),
});

export type PortfolioDecision = z.infer<typeof PortfolioDecisionSchema>;

export type PortfolioInput = {
  symbol: string;
  /** تصمیم ثبت شده؛ null یعنی نماد در سبد نیست */
  decision: PortfolioDecision | null;
  /** قیمت جاری تابلو برای کنترل حد ضرر */
  currentPrice: number | null;
  /** صنعت نماد برای ظرفیت‌سنجی — از تصمیم یا تابلو */
  sector?: string | null;
  /** مجموع وزن‌های ثبت‌شده صنعت همان‌گانه در سبد (بدون خود نماد) */
  sectorUsedPct?: number | null;
};

function faNum(x: number, digits = 1): string {
  return toFaDigits(x.toFixed(digits));
}

/**
 * حد ضرر آزادِ TEXT را به عدد می‌خواند. ارقام فارسی/عربی و جداکننده‌های هزارگان
 * را نرمال می‌کند و در هر حالتِ غیرقابل‌تفسیر («—»، «بدون داده»، رشتهٔ خالی، یا
 * صرفاً جداکننده) null برمی‌گرداند — صفر جعلی هرگز تولید نمی‌شود، چون صفر در
 * مصرف‌کننده‌ها «حد ضررِ واقعیِ صفر» تلقی و hard_stop سرور را سایه می‌کند.
 */
export function stopAsNumber(v: number | string | null | undefined): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string') {
    const cleaned = normalizeFa(v).replace(/[\s,،٬٫]/g, '');
    if (!/^-?\d+(\.\d+)?$/.test(cleaned)) return null;
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function base(symbol: string, ts: number, patch: Partial<AgentSignal<PortfolioPayload>>): AgentSignal<PortfolioPayload> {
  return {
    id: `portfolio:${symbol}:position_state:${ts}`,
    agentId: 'portfolio',
    symbol,
    ts,
    direction: 'neutral',
    confidence: 'medium',
    weight: 'minor',
    title: `وضعیت ${symbol} در سبد`,
    rationale: 'بدون نکته ویژه.',
    score: 55,
    evidence: ['portfolio:position'],
    sourceView: 'portfolio',
    sourceRef: ['API'],
    validForMs: PORTFOLIO_VALID_MS,
    payload: { kind: 'position_state', decision: 'pending', weightPct: null, stopLoss: null, alerts: [] },
    ...patch,
  };
}

// ─── ظرفیت‌سنجی صنعت (Capacity Score) ────────────────────────────────────

export type CapacityResult = {
  /** ظرفیت باقی‌مانده صنعت به درصد سبد (۰ تا سقف) */
  remainingPct: number;
  /** 0..100 — هرچه بالاتر، ظرفیت ورود بیشتر */
  score: number;
  /** توضیح فارسی قانون‌محور */
  note: string;
};

/**
 * ظرفیت باقی‌ماندهٔ صنعت در سبد طبق قانون FTS:
 * سقف ریسک ۲۰٪ در یک صنعت؛ ظرفیت = max(0, 20 − وزن مصرفی صنعت).
 * score = (remaining / 20) × 100 — ورود با ظرفیت صفر یعنی اشباع صنعت.
 */
export function industryCapacity(sectorUsedPct: number | null | undefined): CapacityResult {
  const used = typeof sectorUsedPct === 'number' && Number.isFinite(sectorUsedPct) ? Math.max(0, sectorUsedPct) : null;
  if (used == null) {
    return { remainingPct: INDUSTRY_RISK_CAP_PCT, score: 100, note: 'وزن صنعت در سبد مشخص نیست؛ ظرفیت کامل صنعت در نظر گرفته شد.' };
  }
  const remaining = Math.max(0, INDUSTRY_RISK_CAP_PCT - used);
  const score = Math.round((remaining / INDUSTRY_RISK_CAP_PCT) * 100);
  const note =
    remaining <= 0
      ? `سقف ریسک ${faNum(INDUSTRY_RISK_CAP_PCT, 0)} درصدی صنعت پر شده است؛ ظرفیت ورود جدید صفر.`
      : `ظرفیت باقی‌مانده صنعت ${faNum(remaining)} درصد از سقف ${faNum(INDUSTRY_RISK_CAP_PCT, 0)} درصد.`;
  return { remainingPct: Math.round(remaining * 10) / 10, score, note };
}

export function portfolioSignal(input: PortfolioInput, ts = Date.now()): AgentSignal<PortfolioPayload> {
  const { symbol } = input;

  if (!symbol || !input.decision) {
    // v2: نمادِ خارج از سبد ⇒ رأی ظرفیت‌سنجی، نه «بدون داده»
    const cap = industryCapacity(input.sectorUsedPct);
    const sym = symbol || 'unknown';
    const dir: Direction = cap.score >= 60 ? 'bullish' : cap.score >= 30 ? 'neutral' : 'bearish';
    const conf: Confidence = cap.score >= 60 ? 'medium' : 'low';
    const capacityScore = Math.round(cap.score * 0.4); // وزن پرتفوی 1 است؛ رأی ظرفیت سقف ~40
    return base(sym, ts, {
      direction: dir,
      confidence: conf,
      score: capacityScore,
      title: `ظرفیت ورود ${sym} به سبد`,
      rationale:
        input.sector != null
          ? `${cap.note} نماد در سبد نیست؛ طبق قانون مدیریت سرمایه FTS سقف ریسک هر صنعت ${faNum(INDUSTRY_RISK_CAP_PCT, 0)} درصد است.`
          : `نماد در سبد نیست. ${cap.note}`,
      evidence: ['portfolio:capacity'],
      payload: { kind: 'position_state', decision: 'pending', weightPct: null, stopLoss: null, alerts: [] },
    });
  }

  const decision = input.decision;
  const status = (decision.status ?? 'pending').toLowerCase();
  const weight = typeof decision.weight_eff_pct === 'number' ? decision.weight_eff_pct : null;
  const stop = stopAsNumber(decision.stop_loss);
  const price = typeof input.currentPrice === 'number' && Number.isFinite(input.currentPrice) ? input.currentPrice : null;

  if (status === 'reject') {
    const d: Direction = 'bearish';
    const c: Confidence = 'medium';
    return base(symbol, ts, {
      direction: d,
      confidence: c,
      score: 35,
      title: `${symbol} از سبد حذف شده`,
      rationale: `تصمیم ثبت شده کاربر حذف است${decision.reason ? `: ${decision.reason}` : '.'}`,
      evidence: ['portfolio:rejected'],
      payload: { kind: 'position_state', decision: 'reject', weightPct: weight, stopLoss: stop, alerts: [] },
    });
  }

  if (status === 'accept') {
    const alerts: string[] = [];
    if (weight != null && weight > CONCENTRATION_CAP_PCT) {
      alerts.push(`تمرکز ${faNum(weight)} درصدی بالای سقف ${faNum(CONCENTRATION_CAP_PCT)} درصد`);
    }
    if (input.sectorUsedPct != null && input.sectorUsedPct + (weight ?? 0) > INDUSTRY_RISK_CAP_PCT) {
      alerts.push(`وزن صنعت با این نماد از سقف ${faNum(INDUSTRY_RISK_CAP_PCT, 0)} درصد می‌گذرد`);
    }
    if (stop != null && price != null && price < stop) {
      return base(symbol, ts, {
        direction: 'bearish',
        confidence: 'high',
        score: 20,
        title: `حد ضرر ${symbol} فعال شد`,
        rationale: `قیمت جاری ${faNum(price, 0)} زیر حد ضرر ${faNum(stop, 0)} است${alerts.length > 0 ? `؛ ${alerts.join('؛ ')}` : '.'}`,
        evidence: ['portfolio:stop_hit'],
        payload: { kind: 'position_state', decision: 'accept', weightPct: weight, stopLoss: stop, alerts },
      });
    }
    if (alerts.length > 0) {
      return base(symbol, ts, {
        direction: 'neutral',
        confidence: 'medium',
        score: 45,
        title: `ریسک تمرکز در ${symbol}`,
        rationale: `${alerts.join('؛ ')}.`,
        evidence: ['portfolio:concentration'],
        payload: { kind: 'position_state', decision: 'accept', weightPct: weight, stopLoss: stop, alerts },
      });
    }
    return base(symbol, ts, {
      direction: 'neutral',
      confidence: 'medium',
      score: 55,
      title: `${symbol} در سبد سالم است`,
      rationale: `نگهداری با وزن ${weight != null ? faNum(weight) + ' درصد' : 'نامشخص'}.`,
      evidence: ['portfolio:healthy'],
      payload: { kind: 'position_state', decision: 'accept', weightPct: weight, stopLoss: stop, alerts },
    });
  }

  return base(symbol, ts, {
    direction: 'neutral',
    confidence: 'low',
    score: 50,
    title: `${symbol} زیر نظر است`,
    rationale: 'نماد در رادار زیر نظر است و وزنی در سبد ندارد.',
    evidence: ['portfolio:monitor'],
    payload: { kind: 'position_state', decision: 'monitor', weightPct: weight, stopLoss: stop, alerts: [] },
  });
}
