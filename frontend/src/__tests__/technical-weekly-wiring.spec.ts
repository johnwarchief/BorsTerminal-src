// تست #50: رأیِ هفتگیِ موتورِ FTSِ سرور باید به گیتِ وتو برسد و سیگنالِ تکنیکال
// روی سریِ تعدیل‌شده بدود — دو نقصی که کايزد (۱۵۲٪ صعود، «نزولی» و «توقف در فیلتر
// دوم») را ساختند.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { KLineData } from 'klinecharts';
import {
  applyAdjustmentToCandles,
  mapBackendAdjustEvents,
} from '@features/technical/nahayatnegar/lib/adjustments';
import { weeklyFromFts } from '@features/technical/lib/weeklyFromFts';
import { ftsMAs, majorResistance } from '@features/technical/lib/indicators';
import { technicalSignal } from '@features/technical/signals/technicalSignals';
import {
  definiteDecision,
  runStrictGates,
  weeklyTrendFromSignal,
  type WeeklyTrendInput,
} from '@features/master/lib/strictGates';
import type { AgentSignal, FundamentalPayload, TechnicalPayload } from '@contracts/index';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

const NOW = Date.now();
const t = (s: string) => Date.parse(`${s}T00:00:00Z`);

/** افزایشِ سرمایهٔ کايزد: ۵۸۱۰ ← ۲۶۴۲ (نسبت ≈ ۰٫۴۵) و بعد ۶۰ کندلِ صعودی */
function gappedSeries(): { raw: KLineData[]; events: ReturnType<typeof mapBackendAdjustEvents> } {
  const raw: KLineData[] = [];
  for (let i = 0; i < 120; i += 1) {
    const px = 5600 + Math.round(40 * Math.sin(i / 4));
    raw.push({ timestamp: t('2026-01-01') + i * 86400000, open: px, high: px + 130, low: px - 130, close: px, volume: 1e6 } as unknown as KLineData);
  }
  for (let j = 0; j < 60; j += 1) {
    const px = 2642 + Math.round(20 * j);
    raw.push({ timestamp: t('2026-09-08') + j * 86400000, open: px - 20, high: px + 30, low: px - 40, close: px, volume: 3e6 } as unknown as KLineData);
  }
  return { raw, events: mapBackendAdjustEvents([{ date: '2026-09-08', ratio: 0.4547 }]) };
}

function seriesOf(c: KLineData[]) {
  return {
    opens: c.map((x) => Number(x.open)),
    closes: c.map((x) => Number(x.close)),
    highs: c.map((x) => Number(x.high)),
    lows: c.map((x) => Number(x.low)),
    volumes: c.map((x) => (x.volume == null ? null : Number(x.volume))),
  };
}

function techSig(direction: 'bullish' | 'bearish' | 'neutral', setups: TechnicalPayload['setups'], weekly?: TechnicalPayload['weekly']): AgentSignal<TechnicalPayload> {
  return {
    id: `technical:كايزد:${NOW}`,
    agentId: 'technical',
    symbol: 'كايزد',
    ts: NOW,
    direction,
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال تکنیکال',
    rationale: 'آزمایشی.',
    score: 66,
    evidence: [],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: 48 * 3600_000,
    payload: {
      kind: 'setup',
      timeframe: 'daily',
      setups,
      stopLossRef: null,
      stopLossPrice: null,
      keyLevels: [],
      dataQuality: 'complete',
      weekly: weekly ?? null,
    },
  };
}

function fundSig(): AgentSignal<FundamentalPayload> {
  return {
    id: `fundamental:كايزد:${NOW}`,
    agentId: 'fundamental',
    symbol: 'كايزد',
    ts: NOW,
    direction: 'bullish',
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال بنیادی',
    rationale: 'آزمایشی.',
    score: 85,
    evidence: [],
    sourceView: 'fundamental',
    sourceRef: ['API'],
    validForMs: 90 * 24 * 3600_000,
    payload: {
      kind: 'fts_card',
      score: 5,
      passes: { '3_gross_margin': true },
      riskGates: [],
      epsSeries: [],
      dataGaps: [],
      staleness: false,
      statementAgeDays: 10,
      dataQuality: 'complete',
      peVsSector: null,
      profitYoY: null,
      metrics: { gross_margin: 26, growth_pct: 40 },
    } as unknown as FundamentalPayload,
  };
}

const REGIME = { inBasket: false, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null };

function fts(weeklyTrend: string, matrix: string, reason = 'مبنا: ۵۲ کندلِ اخیر'): FtsAnalysisData {
  return {
    trend: {
      W: { trend: weeklyTrend, basis: weeklyTrend === 'na' ? 'pivots' : 'recent-window' },
      matrix: { decision: matrix, setup: 'JET_OR_PULLBACK_HOLD', desc: '…', basis: { weekly: reason, daily: reason } },
    },
    hourglass: { active: false, weekly_close: 3700, ma52: 2055, weekly_rsi5: 78, action: 'NORMAL', desc: '' },
  } as unknown as FtsAnalysisData;
}

describe('۱) رأیِ هفتگیِ سرور به گیتِ وتو می‌رسد (نه سیم‌کشیِ مرده)', () => {
  it('up ⇒ مجاز، down/range ⇒ وتو، na ⇒ بی‌رأی', () => {
    expect(weeklyFromFts(fts('up', 'PERMITTED'))?.uptrend).toBe(true);
    expect(weeklyFromFts(fts('down', 'REJECT'))?.uptrend).toBe(false);
    expect(weeklyFromFts(fts('range', 'REJECT'))?.uptrend).toBe(false);
    expect(weeklyFromFts(fts('na', 'UNKNOWN'))?.uptrend).toBe(null);
    expect(weeklyFromFts(null)).toBe(null);
  });

  it('زیرِ MA52 و RSI هفتگی از بلوکِ ساعت‌شنی خوانده می‌شود', () => {
    const w = weeklyFromFts(fts('up', 'PERMITTED'))!;
    expect(w.belowMa52).toBe(false);      // ۳۷۰۰ بالای ۲۰۵۵
    expect(w.rsi).toBe(78);
    expect(w.basis).toBe('recent-window');
    expect(w.reason).toContain('کندلِ اخیر');
  });

  it('سیگنالِ تکنیکال بلوکِ هفتگی را منتشر می‌کند و گیت همان را می‌خواند', () => {
    const w = weeklyFromFts(fts('down', 'REJECT'))!;
    const sig = technicalSignal({
      symbol: 'كايزد',
      ...seriesOf(gappedSeries().raw),
      riskGatePass: true,
      enforceRiskGates: false,
      weekly: w,
    });
    expect(sig.payload.weekly?.uptrend).toBe(false);
    const read = weeklyTrendFromSignal(sig);
    expect(read.uptrend).toBe(false);
    expect(read.matrixDecision).toBe('REJECT');
    const res = runStrictGates({ fundamental: fundSig(), technical: sig }, REGIME, read);
    expect(res.weeklyVeto).toBe(true);
    expect(definiteDecision(res).action).toBe('veto');
  });

  it('هفتگیِ صعودی + نبودِ تریگر ⇒ «روند مجاز است، فقط تریگر فعال نشده» (نه نزولی)', () => {
    const w = weeklyFromFts(fts('up', 'PERMITTED'))!;
    const read = weeklyTrendFromSignal(techSig('bullish', ['trend'], w));
    const res = runStrictGates({ fundamental: fundSig(), technical: techSig('bullish', ['trend'], w) }, REGIME, read);
    expect(res.weeklyVeto).toBe(false);
    const g = res.gates.find((x) => x.id === 'technical')!;
    expect(g.state).toBe('pending');
    expect(g.reason).toContain('روند مجاز است');
    expect(g.reason).not.toContain('نزولی');
    expect(definiteDecision(res).action).toBe('veto_gate2');
  });

  it('بی‌دادهٔ هفتگی ⇒ رأیِ ساختگی نمی‌دهد (وتو صادر نمی‌شود)', () => {
    const empty: WeeklyTrendInput = { belowMa52: null, rsi: null, uptrend: null };
    const res = runStrictGates({ fundamental: fundSig(), technical: techSig('bullish', ['breakout']) }, REGIME, empty);
    expect(res.weeklyVeto).toBe(false);
  });
});

describe('۲) سیگنالِ تکنیکال باید سریِ تعدیل‌شده را ببیند', () => {
  it('موتور به مقیاسِ قیمت حساس است: مقاومتِ سریِ خام پیش از مجمع می‌ماند', () => {
    const { raw, events } = gappedSeries();
    const adj = applyAdjustmentToCandles(raw, events, 'combined');
    const rRaw = majorResistance(seriesOf(raw).highs);
    const rAdj = majorResistance(seriesOf(adj).highs);
    expect(rRaw).not.toBeNull();
    expect(rAdj).not.toBeNull();
    expect(rRaw!.price).toBeGreaterThan(5000);   // سقفِ ۵۸۰۰ تومانیِ پیش از مجمع
    expect(rAdj!.price).toBeLessThan(4500);      // همان سقف روی مقیاسِ امروز
    const maRaw = ftsMAs(seriesOf(raw).closes)[100];
    const maAdj = ftsMAs(seriesOf(adj).closes)[100];
    expect(Math.abs((maRaw[maRaw.length - 1] ?? 0) - (maAdj[maAdj.length - 1] ?? 0))).toBeGreaterThan(500);
  });

  it('کندلِ پس از رویداد دست‌نخورده می‌ماند (آخرین قیمتِ تابلو عوض نمی‌شود)', () => {
    const { raw, events } = gappedSeries();
    const adj = applyAdjustmentToCandles(raw, events, 'combined');
    expect(Number(adj[adj.length - 1].close)).toBe(Number(raw[raw.length - 1].close));
  });

  it('صفحهٔ تکنیکال همان سریِ تعدیل‌شده را به سیگنال می‌دهد', () => {
    // نگهبانِ ساختاری: اگر کسی این دو خط را به feed.candles برگرداند، مقاومت و MA
    // دوباره دو مقیاسِ قیمتی را قاطی می‌کنند و تستِ بالا بی‌فایده می‌شود.
    const src = readFileSync(
      join(__dirname, '../features/technical/routes/TechnicalPage.tsx'),
      'utf-8',
    );
    expect(src).toContain("applyAdjustmentToCandles(feed.candles, mapBackendAdjustEvents(adjustEvents ?? []), 'combined')");
    expect(src).not.toContain('const candles = feed.candles');
  });
});
