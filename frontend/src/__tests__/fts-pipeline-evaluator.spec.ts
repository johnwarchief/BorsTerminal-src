// __tests__/fts-pipeline-evaluator.spec.ts -- تست‌های ارزیاب خط لولهٔ ۴ مرحله‌ای FTS
import { describe, expect, it } from 'vitest';
import type { AgentSignal } from '@contracts/signal';
import {
  evaluateFtsPipeline,
  recommendHorizon,
} from '@features/master/lib/ftsPipelineEvaluator';
import type { BusInput } from '@features/master/lib/masterMath';
import { runStrictGates, definiteDecision } from '@features/master/lib/strictGates';

const NOW = Date.now();

function dummySignal(patch: Partial<AgentSignal> = {}): AgentSignal {
  return {
    id: `test:${patch.symbol ?? 'شپنا'}:${NOW}`,
    agentId: 'fundamental',
    symbol: 'شپنا',
    ts: NOW,
    direction: 'bullish',
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال تست',
    rationale: 'تست رشنال',
    score: 80,
    evidence: [],
    sourceView: 'fundamental',
    sourceRef: [],
    validForMs: 3600_000,
    payload: {},
    ...patch,
  };
}

describe('ftsPipelineEvaluator — ارزیابی گام‌های ۴‌گانه FTS', () => {
  it('پیشنهاد افق زمانی بر اساس بنیاد: صرفاً سوپربنیادی ⇒ ساعت شنی، غیرسوپر ⇒ روندگیر یا نوسان‌گیر', () => {
    expect(recommendHorizon(5, true)).toBe('hourglass');
    expect(recommendHorizon(5, false)).toBe('trend');
    expect(recommendHorizon(5, false, true)).toBe('swing');
    expect(recommendHorizon(4, false)).toBe('trend');
    expect(recommendHorizon(3, false)).toBe('swing');
    expect(recommendHorizon(null, false)).toBe('swing');
  });

  it('گام ۱: تایید با الگوی ساعت مثبت', () => {
    const inputs: BusInput = {
      tape: dummySignal({
        agentId: 'tape',
        sourceView: 'market',
        payload: { clock_pattern: true, vol_ratio: 1.5 },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const result = evaluateFtsPipeline({
      symbol: 'شپنا',
      inputs,
      strict,
      decision,
    });

    expect(result.steps[0].status).toBe('pass');
    expect(result.steps[0].headline).toContain('الگوی ساعت فعال');
  });

  it('گام ۲: وتوی هفتگی ماژور نزولی', () => {
    const inputs: BusInput = {
      technical: dummySignal({
        agentId: 'technical',
        sourceView: 'technical',
        direction: 'bearish',
        payload: { weekly_uptrend: false },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const result = evaluateFtsPipeline({
      symbol: 'شپنا',
      horizon: 'trend',
      inputs,
      strict,
      decision,
    });

    expect(result.steps[1].status).toBe('fail');
    expect(result.steps[1].headline).toContain('وتوی ماژور هفتگی');
    expect(result.overallStatus).toBe('fail');
  });

  it('گام ۲: تایید با ستاپ جت و شکست مقاومت', () => {
    const inputs: BusInput = {
      technical: dummySignal({
        agentId: 'technical',
        sourceView: 'technical',
        direction: 'bullish',
        payload: { weekly_uptrend: true, jet_active: true },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const result = evaluateFtsPipeline({
      symbol: 'فولاد',
      inputs,
      strict,
      decision,
    });

    expect(result.steps[1].status).toBe('pass');
    expect(result.steps[1].headline).toContain('ستاپ جت');
  });

  it('محاسبه حد ضرر بر اساس افق: نوسانی ۵٪ زیر ورود، روندی زیر کف ماژور، ساعت شنی بنیادی', () => {
    const inputs: BusInput = {};
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);

    // ۱) نوسان‌گیر
    const swingRes = evaluateFtsPipeline({
      symbol: 'شپنا',
      horizon: 'swing',
      inputs,
      strict,
      decision,
      currentPrice: 10_000,
      resistancePrice: 11_500,
    });
    expect(swingRes.tradePlan.stopLossPrice).toBe(9_500); // 10,000 * 0.95
    expect(swingRes.tradePlan.stopLossPct).toBe(5);
    expect(swingRes.tradePlan.targetPrice).toBe(11_500);

    // ۲) روندگیر
    const trendRes = evaluateFtsPipeline({
      symbol: 'شپنا',
      horizon: 'trend',
      inputs,
      strict,
      decision,
      currentPrice: 10_000,
      supportPrice: 9_000,
      resistancePrice: 12_000,
    });
    expect(trendRes.tradePlan.stopLossPrice).toBe(8_550); // 9,000 * 0.95
    expect(trendRes.tradePlan.halfExitLabel).toContain('ذخیره سود ۵۰٪');

    // ۳) ساعت شنی
    const hourglassRes = evaluateFtsPipeline({
      symbol: 'شپنا',
      horizon: 'hourglass',
      inputs,
      strict,
      decision,
      currentPrice: 10_000,
    });
    expect(hourglassRes.tradePlan.stopLossPrice).toBe(8_500);
    expect(hourglassRes.tradePlan.stopLossBasis).toContain('حد ضرر قطعی');
  });

  it('تولید گزارش تشریحی ۴ بخشی انسان‌فهم', () => {
    const inputs: BusInput = {
      fundamental: dummySignal({
        agentId: 'fundamental',
        score: 5,
        payload: { score: 5, passes: {} },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const res = evaluateFtsPipeline({
      symbol: 'فملی',
      inputs,
      strict,
      decision,
      fundScore: 5,
      currentPrice: 8_500,
    });

    expect(res.narrative.why).toBeTruthy();
    expect(res.narrative.technical).toBeTruthy();
    expect(res.narrative.fundamental).toBeTruthy();
    expect(res.narrative.tradePlan).toBeTruthy();
  });

  it('تولید سناریوهای ۳گانه FTS (صعودی، رنج، نزولی) و جمع ۱۰۰٪ احتمالات', () => {
    const inputs: BusInput = {
      fundamental: dummySignal({
        agentId: 'fundamental',
        score: 5,
        payload: { score: 5, passes: {} },
      }),
      technical: dummySignal({
        agentId: 'technical',
        direction: 'bullish',
        payload: { weekly_uptrend: true, jet_active: true },
      }),
      tape: dummySignal({
        agentId: 'tape',
        payload: { clock_pattern: true, vol_ratio: 3.5 },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const res = evaluateFtsPipeline({
      symbol: 'فولاد',
      inputs,
      strict,
      decision,
      fundScore: 5,
      currentPrice: 5_000,
      resistancePrice: 5_800,
    });

    const sc = res.narrative.scenarios;
    expect(sc.bullish.probabilityPct + sc.neutral.probabilityPct + sc.bearish.probabilityPct).toBe(100);
    expect(sc.bullish.title).toContain('صعودی');
    expect(sc.bullish.targetOrStop).toContain('ذخیره سود ۵۰٪');
    expect(sc.neutral.title).toContain('رنج');
    expect(sc.bearish.title).toContain('نزولی');
    expect(sc.bearish.targetOrStop).toContain('MA-14');
  });

  it('سنجش نقدشوندگی و صف‌های بازار: الگوی کف‌روبی و الگوی ساعت', () => {
    const inputs: BusInput = {
      tape: dummySignal({
        agentId: 'tape',
        payload: {
          is_sell_queue: true,
          floor_sweep: true,
          buyer_power: 1.8,
        },
      }),
    };
    const strict = runStrictGates(inputs, { inBasket: null, industryUsedPct: null, industryCapPct: 20, warRegime: false, symbolWeightPct: null });
    const decision = definiteDecision(strict);
    const res = evaluateFtsPipeline({
      symbol: 'خکاوه',
      inputs,
      strict,
      decision,
    });

    expect(res.narrative.liquidity.queueStatus).toBe('sell_queue');
    expect(res.narrative.liquidity.headline).toContain('کف‌روبی');
    expect(res.narrative.readinessCondition).toBeTruthy();
    expect(res.narrative.traderAdvice).toContain('نوسان‌گیر');
  });
});
