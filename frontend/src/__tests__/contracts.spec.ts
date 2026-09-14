// تست قرارداد Signal -- قفل کامپایلری و زمان اجرا
import { describe, expect, it } from 'vitest';
import {
  AGENT_WEIGHTS,
  BaseSignal,
  FundamentalPayload,
  MasterVerdict,
  PortfolioPayload,
  TapePayload,
  TechnicalPayload,
  isSignalExpired,
  validateSignal,
} from '@contracts/index';
import { fmtHemmat, fmtInt, toFaDigits } from '@shared/lib/fmt';

const BASE = {
  id: 'fundamental:شپنا:fts_card:1726000000000',
  agentId: 'fundamental',
  symbol: 'شپنا',
  ts: 1726000000000,
  direction: 'bullish',
  confidence: 'high',
  title: 'نسبت P/E زیر میانگین صنعت',
  rationale: 'P/E سهم 5.2 در برابر میانگین صنعت 7.8 است',
  sourceView: 'fundamental',
} as const;

describe('قرارداد BaseSignal', () => {
  it('سیگنال معتبر پارس می شود', () => {
    const r = BaseSignal.safeParse(BASE);
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.weight).toBe('major');
      expect(r.data.score).toBeNull();
    }
  });

  it('سیگنال خراب رد می شود', () => {
    const r = BaseSignal.safeParse({ ...BASE, title: 'x' });
    expect(r.success).toBe(false);
    expect(validateSignal({ ...BASE, title: 'x' })).toBeNull();
  });

  it('انقضا درست محاسبه می شود', () => {
    expect(isSignalExpired({ ts: 1000, validForMs: 500 }, 2000)).toBe(true);
    expect(isSignalExpired({ ts: 1000, validForMs: 5000 }, 2000)).toBe(false);
  });

  it('وزن مصوب ایجنت ها همان 4-3-2-1 است', () => {
    expect(AGENT_WEIGHTS).toMatchObject({ fundamental: 4, technical: 3, tape: 2, portfolio: 1 });
  });
});

describe('قرارداد payload ایجنت ها', () => {
  it('بنیادی: نردبان EPS با دوره بدون داده', () => {
    const r = FundamentalPayload.safeParse({
      kind: 'fts_card',
      score: 4,
      passes: { '1a_monetary_growth': true },
      epsSeries: [120, null, 98],
    });
    expect(r.success).toBe(true);
  });

  it('تکنیکال: ستاپ با حد ضرر', () => {
    const r = TechnicalPayload.safeParse({
      kind: 'setup',
      timeframe: 'daily',
      setups: ['breakout'],
      stopLossRef: 'ma14',
      keyLevels: [{ type: 'resistance', price: 5200 }],
    });
    expect(r.success).toBe(true);
  });

  it('تابلو: الگوی ساعت', () => {
    const r = TapePayload.safeParse({ kind: 'tape_pattern', pattern: 'closing_auction_pop', lastVsClose: 0.012 });
    expect(r.success).toBe(true);
  });

  it('پرتفو: وضعیت تصمیم', () => {
    const r = PortfolioPayload.safeParse({ kind: 'position_state', decision: 'monitor', weightPct: 12.5 });
    expect(r.success).toBe(true);
  });

  it('مستر: verdict کامل', () => {
    const r = MasterVerdict.safeParse({
      symbol: 'شپنا',
      ts: 1726000000000,
      compositeScore: 42,
      finalAction: 'watch',
      contributions: [{ agentId: 'fundamental', score: 60, signalCount: 2, confidence: 'high' }],
      dissent: [{ agents: ['fundamental', 'technical'], gap: 90, note: 'اختلاف دیدگاه' }],
      usedSignalIds: ['fundamental:شپنا:fts_card:1726000000000'],
      discardedSignalIds: [],
    });
    expect(r.success).toBe(true);
  });
});

describe('ابزار fmt', () => {
  it('ارقام فارسی و همت', () => {
    expect(toFaDigits(123)).toBe('۱۲۳');
    expect(fmtInt(1500000)).toBe('۱٬۵۰۰٬۰۰۰');
    expect(fmtInt(null)).toBe('-');
    expect(fmtHemmat(2.5e13)).toBe('۲.۵۰ همت');
  });
});
