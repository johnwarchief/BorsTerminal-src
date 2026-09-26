// features/market/signals/tapeSignals.ts -- تبدیل ردیف تابلو به AgentSignal
// خروجی دقیق قرارداد فاز 1 را پر می کند تا مستر با وزن 2 محاسبه کند.
import type { AgentSignal, Confidence, Direction, SignalWeight } from '@contracts/signal';
import type { TapePayload, TapePattern } from '@contracts/tape';
import type { MarketRow } from '@shared/types/marketRow';
import { toFaDigits } from '@shared/lib/fmt';
import {
  PER_CAPITA_MIN,
  buyerPowerRatio,
  detectClockPattern,
  detectSuspiciousVolume,
  lastVsClose,
} from '../lib/tapeMath';

function faPct(x: number): string {
  return toFaDigits((x * 100).toFixed(2)) + ' درصد';
}

function faMult(x: number): string {
  return toFaDigits(x.toFixed(1)) + ' برابر';
}

function baseId(symbol: string, kind: string, ts: number): string {
  return `tape:${symbol}:${kind}:${ts}`;
}

type Draft = {
  pattern: TapePattern;
  direction: Direction;
  confidence: Confidence;
  weight: SignalWeight;
  title: string;
  rationale: string;
  score: number;
  evidence: string[];
  payload: TapePayload;
};

/** سیگنال الگوی ساعت: آخرین معامله بالاتر از پایانی با حمایت سرانه */
function clockDraft(
  row: MarketRow,
  gap: number,
  lvc: number,
  power: number | null,
  multiple: number | null,
): Draft {
  const supported = power != null && power >= PER_CAPITA_MIN;
  return {
    pattern: 'closing_auction_pop',
    direction: 'bullish',
    confidence: supported ? 'high' : 'medium',
    weight: 'major',
    title: `الگوی ساعت در ${row.symbol ?? ''}`,
    rationale:
      `قیمت آخرین معامله ${faPct(gap)} بالاتر از قیمت پایانی است (الگوی ساعت FTS)` +
      (power != null ? ` و سرانه خرید حقیقی ${faMult(power)} سرانه فروش است` : ' و سرانه حقیقی قابل محاسبه نبود') +
      (multiple != null ? ` با حجم ${faMult(multiple)} میانگین سی نشست.` : '.'),
    score: supported ? Math.min(100, Math.round(55 + gap * 1000)) : 55,
    evidence: ['market:clock_gap', 'market:per_capita'],
    payload: {
      kind: 'tape_pattern',
      pattern: 'closing_auction_pop',
      lastVsClose: lvc,
      volumeMultiple: multiple,
    },
  };
}

/** سیگنال حجم مشکوک: حجم چند برابر میانگین بدون جهت قیمتی مشخص */
function suspDraft(row: MarketRow, multiple: number, lvc: number, power: number | null): Draft {
  return {
    pattern: 'suspicious_volume',
    direction: 'neutral',
    confidence: power != null && power >= PER_CAPITA_MIN ? 'medium' : 'low',
    weight: 'major',
    title: `حجم مشکوک در ${row.symbol ?? ''}`,
    rationale:
      `حجم معاملات ${faMult(multiple)} میانگین سی نشستِ اخیر است` +
      (power != null ? ` و قدرت خریدار حقیقی ${faMult(power)} است.` : ' و سرانه حقیقی قابل محاسبه نبود.'),
    score: Math.min(100, Math.round(40 + multiple * 8)),
    evidence: ['market:volume_spike'],
    payload: {
      kind: 'tape_pattern',
      pattern: 'suspicious_volume',
      lastVsClose: lvc,
      volumeMultiple: multiple,
    },
  };
}

/** همه سیگنال های یک ردیف: حداکثر دو سیگنال (ساعت و حجم مشکوک) */
export function rowToTapeSignals(row: MarketRow, ts = Date.now()): AgentSignal<TapePayload>[] {
  if (!row.symbol) return [];
  const lvc = lastVsClose(row.p_last, row.p_closing);
  if (lvc == null) return [];
  const power = buyerPowerRatio(row.buy_i_vol, row.buy_count_i, row.sell_i_vol, row.sell_count_i);
  const out: AgentSignal<TapePayload>[] = [];

  const clock = detectClockPattern(row);
  if (clock.hit && clock.gap != null) {
    const d = clockDraft(row, clock.gap, lvc, power, detectSuspiciousVolume(row).multiple);
    out.push({
      id: baseId(row.symbol, 'clock', ts),
      agentId: 'tape',
      symbol: row.symbol,
      ts,
      direction: d.direction,
      confidence: d.confidence,
      weight: d.weight,
      title: d.title,
      rationale: d.rationale,
      score: d.score,
      evidence: d.evidence,
      sourceView: 'market',
      sourceRef: ['API'],
      validForMs: 3600_000,
      payload: d.payload,
    });
  }

  const susp = detectSuspiciousVolume(row);
  if (susp.hit && susp.multiple != null) {
    const d = suspDraft(row, susp.multiple, lvc, power);
    out.push({
      id: baseId(row.symbol, 'susp_vol', ts),
      agentId: 'tape',
      symbol: row.symbol,
      ts,
      direction: d.direction,
      confidence: d.confidence,
      weight: d.weight,
      title: d.title,
      rationale: d.rationale,
      score: d.score,
      evidence: d.evidence,
      sourceView: 'market',
      sourceRef: ['API'],
      validForMs: 3600_000,
      payload: d.payload,
    });
  }

  return out;
}

/** سیگنال همه ردیف ها با همان ts واحد برای تجمیع یکدست */
export function rowsToTapeSignals(rows: MarketRow[], ts = Date.now()): AgentSignal<TapePayload>[] {
  return rows.flatMap((r) => rowToTapeSignals(r, ts));
}
