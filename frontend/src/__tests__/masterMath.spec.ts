// تست موتور تجمیع مستر: وزن دهی و تضاد و آستانه ها
import { describe, expect, it } from 'vitest';
import { MasterVerdict } from '@contracts/master';
import { aggregateSignals, fundamentalGate, isActiveSignal, signedScore } from '@features/master/lib/masterMath';
import type { AgentSignal } from '@contracts/signal';

const NOW = 1726000000000;

function sig(agent: AgentSignal['agentId'], direction: AgentSignal['direction'], score: number | null, patch: Partial<AgentSignal> = {}): AgentSignal {
  return {
    id: `${agent}:شپنا:k:${NOW}`,
    agentId: agent,
    symbol: 'شپنا',
    ts: NOW,
    direction,
    confidence: 'high',
    weight: 'major',
    title: `سیگنال ${agent}`,
    rationale: 'استدلال آزمایشی.',
    score,
    evidence: [],
    sourceView: agent === 'tape' ? 'market' : agent === 'fundamental' ? 'fundamental' : agent === 'technical' ? 'technical' : 'portfolio',
    sourceRef: ['API'],
    validForMs: 90 * 24 * 3600_000,
    payload: { kind: 'x' },
    ...patch,
  };
}

describe('گیت بنیادیِ قیف', () => {
  it('صندوق ⇒ nodata با دلیلِ «صندوق»، نه «داده ناقص» (رأی ۱۵)', () => {
    const g = fundamentalGate(
      sig('fundamental', 'neutral', null, {
        confidence: 'nodata',
        payload: { kind: 'fts_card', score: 0, applicable: false },
      }),
      NOW,
    );
    expect(g.status).toBe('nodata');
    expect(g.note).toContain('صندوق');
    expect(g.note).not.toContain(' ناقص ');
  });

  it('دادهٔ ناقص ⇒ همان دلیلِ قبلی', () => {
    const g = fundamentalGate(
      sig('fundamental', 'neutral', null, {
        confidence: 'nodata',
        payload: { kind: 'fts_card', score: 0 },
      }),
      NOW,
    );
    expect(g.status).toBe('nodata');
    expect(g.note).toContain('ناقص');
  });
});

describe('نمره علامت دار و فعالی', () => {
  it('صعودی مثبت و نزولی منفی و خنثی صفر', () => {
    expect(signedScore(sig('tape', 'bullish', 80))).toBe(80);
    expect(signedScore(sig('tape', 'bearish', 80))).toBe(-80);
    expect(signedScore(sig('tape', 'neutral', 80))).toBe(0);
    expect(signedScore(sig('tape', 'bullish', null))).toBe(0);
  });

  it('منقضی و نودیتا و ناقص غیرفعال اند', () => {
    expect(isActiveSignal(sig('tape', 'bullish', 80), NOW)).toBe(true);
    expect(isActiveSignal(sig('tape', 'bullish', 80, { validForMs: 1 }), NOW + 100)).toBe(false);
    expect(isActiveSignal(sig('tape', 'bullish', 80, { confidence: 'nodata' }), NOW)).toBe(false);
    expect(isActiveSignal(sig('fundamental', 'neutral', null, { payload: { kind: 'fts_card', dataQuality: 'incomplete' } }), NOW)).toBe(false);
  });
});

describe('تجمیع وزنی', () => {
  it('میانگین وزنی هر چهار ایجنت', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: sig('fundamental', 'bullish', 80),
      technical: sig('technical', 'bullish', 60),
      tape: sig('tape', 'neutral', 50),
      portfolio: sig('portfolio', 'bullish', 70),
    }, NOW);
    // (4*80 + 3*60 + 2*0 + 1*70) / 10 = 57
    expect(v.compositeScore).toBe(57);
    expect(v.finalAction).toBe('strong_buy');
    expect(v.hasConflict).toBe(false);
    expect(v.usedSignalIds).toHaveLength(4);
    expect(MasterVerdict.safeParse(v).success).toBe(true);
  });

  it('بازتوزیع وزن در غیاب بنیادی', () => {
    const v = aggregateSignals('شپنا', {
      technical: sig('technical', 'bullish', 60),
      tape: sig('tape', 'neutral', 50),
    }, NOW);
    // (3*60 + 2*0) / 5 = 36 -> نرمال 68 -> buy
    expect(v.compositeScore).toBe(36);
    expect(v.finalAction).toBe('buy');
    expect(v.contributions.find((c) => c.agentId === 'fundamental')?.signalCount).toBe(0);
  });

  it('سیگنال منقضی کنار گذاشته و ثبت می شود', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: sig('fundamental', 'bullish', 80, { validForMs: 1 }),
      technical: sig('technical', 'bullish', 60),
    }, NOW + 100);
    expect(v.usedSignalIds).toHaveLength(1);
    expect(v.discardedSignalIds).toHaveLength(1);
    expect(v.compositeScore).toBe(60);
  });

  it('تضاد بنیادی و تکنیکال پرچم و تنزیل می آورد', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: sig('fundamental', 'bullish', 80),
      technical: sig('technical', 'bearish', 20),
    }, NOW);
    expect(v.hasConflict).toBe(true);
    expect(v.dissent).toHaveLength(1);
    expect(v.dissent[0].agents).toEqual(['fundamental', 'technical']);
    expect(v.dissent[0].gap).toBe(100);
    // خام: (320 - 60) / 7 = 37.1 -> تنزیل 0.8 = 29.7
    expect(v.compositeScore).toBeCloseTo(29.7, 1);
    expect(MasterVerdict.safeParse(v).success).toBe(true);
  });

  it('بدون تضاد در توافق', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: sig('fundamental', 'bullish', 80),
      technical: sig('technical', 'bullish', 75),
    }, NOW);
    expect(v.hasConflict).toBe(false);
    expect(v.dissent).toHaveLength(0);
  });

  it('آستانه های اقدام نهایی', () => {
    const only = (score: number) => aggregateSignals('شپنا', { fundamental: sig('fundamental', 'bullish', score) }, NOW);
    expect(only(50).finalAction).toBe('strong_buy');
    expect(only(30).finalAction).toBe('buy');
    expect(only(0).finalAction).toBe('hold');
    const bear = (score: number) => aggregateSignals('شپنا', { fundamental: sig('fundamental', 'bearish', score) }, NOW);
    expect(bear(30).finalAction).toBe('sell');
    expect(bear(80).finalAction).toBe('strong_sell');
  });

  it('بدون سیگنال اقدامی نیست', () => {
    const v = aggregateSignals('شپنا', {}, NOW);
    expect(v.finalAction).toBe('no_data');
    expect(v.compositeScore).toBe(0);
    expect(MasterVerdict.safeParse(v).success).toBe(true);
  });
});
