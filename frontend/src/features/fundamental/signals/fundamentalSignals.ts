// features/fundamental/signals/fundamentalSignals.ts -- سیگنال بنیادی با وزن 4
// ماندگاری 90 روزه (فصلی) و پرچم کهنگی بالای 120 روز.
import type { AgentSignal, Confidence, Direction } from '@contracts/signal';
import type { DataQuality } from '@contracts/signal';
import type { FundamentalPayload } from '@contracts/fundamental';
import { toFaDigits } from '@shared/lib/fmt';
import { peBonus, yoyBonus } from '../lib/fundMath';

/** آستانه کهنگی صورت مالی به روز */
export const STALE_AFTER_DAYS = 120;
/** ماندگاری سیگنال بنیادی: 90 روز */
export const FUND_VALID_MS = 90 * 24 * 3600_000;
/** ماندگاری سیگنال خلاء داده: 7 روز */
export const NODATA_VALID_MS = 7 * 24 * 3600_000;

export type FundamentalInput = {
  symbol: string;
  ftsScore: number | null;
  passes: Record<string, boolean>;
  epsSeries: (number | null)[];
  pe: number | null;
  sectorMedianPE: number | null;
  profitYoY: number | null;
  statementAgeDays: number | null;
  hasStatements: boolean;
  epsPartial: boolean;
  /** رأی ۱۵ — صندوق در پنج‌شاخصه نمی‌گنجد؛ هیچ داوری صادر نمی‌شود */
  applicable?: boolean;
};

function faNum(x: number, digits = 1): string {
  return toFaDigits(x.toFixed(digits));
}

/** سیگنال خلاء داده: خنثی با کیفیت ناقص */
function nodataSignal(symbol: string, ts: number): AgentSignal<FundamentalPayload> {
  return {
    id: `fundamental:${symbol}:nodata:${ts}`,
    agentId: 'fundamental',
    symbol,
    ts,
    direction: 'neutral',
    confidence: 'nodata',
    weight: 'major',
    title: `داده بنیادی ${symbol} ناقص است`,
    rationale: 'صورت مالی معتبری در کدال برای این نماد نیست؛ داوری بنیادی ممکن نیست.',
    score: null,
    evidence: ['fts:no_statements'],
    sourceView: 'fundamental',
    sourceRef: ['API'],
    validForMs: NODATA_VALID_MS,
    payload: {
      kind: 'fts_card',
      score: 0,
      passes: {},
      riskGates: [],
      epsSeries: [],
      dataGaps: [],
      staleness: false,
      statementAgeDays: null,
      dataQuality: 'incomplete',
      peVsSector: null,
      profitYoY: null,
      applicable: true,
    },
  };
}

/** سیگنال «FTS ندارد»: خنثی، بدون داوری، با دلیلِ درست (نه «داده ناقص») */
function notApplicableSignal(symbol: string, ts: number): AgentSignal<FundamentalPayload> {
  return {
    id: `fundamental:${symbol}:not_applicable:${ts}`,
    agentId: 'fundamental',
    symbol,
    ts,
    direction: 'neutral',
    confidence: 'nodata',
    weight: 'major',
    title: `FTS برای ${symbol} داوری ندارد`,
    rationale: 'این نماد صندوقِ سرمایه‌گذاری است؛ رشد فروش، حاشیه سود و نسبت فروش به ارزش '
      + 'بازار بر سبدِ دارایی معنا ندارد، پس پنج‌شاخصه مردود یا تأیید نمی‌شود.',
    score: null,
    evidence: ['fts:not_applicable'],
    sourceView: 'fundamental',
    sourceRef: ['API', 'CODAL'],
    validForMs: FUND_VALID_MS,
    payload: {
      kind: 'fts_card',
      score: 0,
      passes: {},
      riskGates: [],
      epsSeries: [],
      dataGaps: [],
      staleness: false,
      statementAgeDays: null,
      dataQuality: 'complete',
      peVsSector: null,
      profitYoY: null,
      applicable: false,
    },
  };
}

export function fundamentalSignal(input: FundamentalInput, ts = Date.now()): AgentSignal<FundamentalPayload> {
  const { symbol } = input;
  if (!symbol || !input.hasStatements) return nodataSignal(symbol || 'unknown', ts);
  if (input.applicable === false) return notApplicableSignal(symbol, ts);

  const age = input.statementAgeDays;
  const stale = age != null && age > STALE_AFTER_DAYS;
  const med = input.sectorMedianPE;
  const pe = input.pe;
  const yoy = input.profitYoY;

  const bullishCond = pe != null && med != null && med > 0 && pe > 0 && pe < med && yoy != null && yoy > 0;
  const bearishCond = pe != null && med != null && med > 0 && pe > 1.5 * med && yoy != null && yoy < 0;

  const ftsBase = input.ftsScore == null ? 22 : (input.ftsScore / 5) * 45;
  const composite = Math.max(0, Math.min(100, Math.round(ftsBase + peBonus(pe, med) + yoyBonus(yoy) + 10)));

  let direction: Direction;
  let score: number;
  if (bullishCond) {
    direction = 'bullish';
    score = Math.max(composite, 71);
  } else if (bearishCond) {
    direction = 'bearish';
    score = Math.min(composite, 29);
  } else {
    direction = composite >= 60 ? 'bullish' : composite <= 40 ? 'bearish' : 'neutral';
    score = composite;
  }

  let confidence: Confidence = score >= 70 ? 'high' : score >= 45 ? 'medium' : 'low';
  if (stale) confidence = confidence === 'high' ? 'medium' : confidence;

  const dataQuality: DataQuality = stale || input.epsPartial ? 'partial' : 'complete';
  const bits: string[] = [];
  if (input.ftsScore != null) bits.push(`امتیاز FTS ${faNum(input.ftsScore, 0)} از 5`);
  if (pe != null && med != null && med > 0)
    bits.push(`P/E ${faNum(pe, 2)} در برابر میانه صنعت ${faNum(med, 2)}`);
  else bits.push('P/E قابل اتکا نیست');
  if (yoy != null) bits.push(`رشد سود فصلی ${faNum(yoy)} درصد`);
  else bits.push('رشد فصلی قابل محاسبه نیست');
  if (age != null) bits.push(`سن آخرین صورت مالی ${faNum(age, 0)} روز`);
  if (stale) bits.push('داده کهنه است و اعتماد سقف متوسط گرفت');

  return {
    id: `fundamental:${symbol}:fts_card:${ts}`,
    agentId: 'fundamental',
    symbol,
    ts,
    direction,
    confidence,
    weight: 'major',
    title: direction === 'bullish' ? `بنیادی ${symbol} ارزنده است` : direction === 'bearish' ? `بنیادی ${symbol} گران است` : `بنیادی ${symbol} خنثی است`,
    rationale: bits.join('؛ ') + '.',
    score,
    evidence: ['fts:score', 'fts:pe_vs_sector', 'fts:profit_yoy'],
    sourceView: 'fundamental',
    sourceRef: ['API', 'CODAL'],
    validForMs: FUND_VALID_MS,
    payload: {
      kind: 'fts_card',
      score: input.ftsScore ?? 0,
      passes: input.passes,
      riskGates: [],
      epsSeries: input.epsSeries,
      dataGaps: [],
      staleness: stale,
      statementAgeDays: age,
      dataQuality,
      peVsSector: pe != null && med != null && med > 0 ? pe / med : null,
      profitYoY: yoy,
      // تا اینجا از گیتِ بالا رد شده، پس داوری معنا داشته است
      applicable: true,
    },
  };
}
