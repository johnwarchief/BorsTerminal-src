// تست موتور داوری مستر v2: وزن موثر، گیتینگ سه‌گانه، synthesis، برنامه معاملاتی
import { describe, expect, it } from 'vitest';
import { MasterVerdict } from '@contracts/master';
import type { AgentSignal, TechnicalPayload, FundamentalPayload, TapePayload } from '@contracts/index';
import {
  aggregateSignals,
  applyGateToAction,
  blockingGate,
  effectiveWeights,
  fundamentalGate,
  hasEntrySetup,
  isActiveSignal,
  isHoldingInBasket,
  runGatingPipeline,
  signedScore,
  synthesizeVerdict,
  tapeGate,
  technicalGate,
} from '@features/master/lib/masterMath';
import { buildTradePlan, riskLevel, stepWeightPct, rial } from '@features/master/lib/tradePlanMath';

const NOW = 1726000000000;

function sig(
  agent: AgentSignal['agentId'],
  direction: AgentSignal['direction'],
  score: number | null,
  patch: Partial<AgentSignal> = {},
): AgentSignal {
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

/** سیگنال بنیادی کامل با dataQuality */
function fundSig(direction: AgentSignal['direction'], score: number, quality: 'complete' | 'incomplete' = 'complete'): AgentSignal<FundamentalPayload> {
  return sig('fundamental', direction, score, {
    confidence: quality === 'incomplete' ? 'nodata' : 'high',
    payload: { kind: 'fts_card', score: 4, passes: {}, riskGates: [], epsSeries: [], dataGaps: [], staleness: false, statementAgeDays: 10, dataQuality: quality, peVsSector: null, profitYoY: null },
  }) as AgentSignal<FundamentalPayload>;
}

/** سیگنال تکنیکال با ستاپ‌ها */
function techSig(direction: AgentSignal['direction'], score: number, setups: TechnicalPayload['setups']): AgentSignal<TechnicalPayload> {
  return sig('technical', direction, score, {
    payload: { kind: 'setup', timeframe: 'daily', setups, stopLossRef: null, stopLossPrice: null, keyLevels: [], dataQuality: 'complete' },
  }) as AgentSignal<TechnicalPayload>;
}

/** سیگنال تابلو با الگو */
function tapeSig(pattern: TapePayload['pattern'], score: number, conf: AgentSignal['confidence'] = 'high'): AgentSignal<TapePayload> {
  return sig('tape', pattern === 'closing_auction_pop' ? 'bullish' : 'neutral', score, {
    confidence: conf,
    payload: { kind: 'tape_pattern', pattern, lastVsClose: 0.02, volumeMultiple: 3.5 },
  }) as AgentSignal<TapePayload>;
}

describe('وزن موثر (رفع باگ سهم ۰)', () => {
  it('وزن فعال بین آرای فعال بازتوزیع می شود — جمع ۱', () => {
    const w = effectiveWeights({ fundamental: sig('fundamental', 'bullish', 80), technical: sig('technical', 'bullish', 60) }, NOW);
    // 4/(4+3) و 3/(4+3)
    expect(w.fundamental).toBeCloseTo(4 / 7, 5);
    expect(w.technical).toBeCloseTo(3 / 7, 5);
    expect(w.tape).toBe(0);
    expect(w.portfolio).toBe(0);
    const sum = w.fundamental + w.technical + w.tape + w.portfolio;
    expect(sum).toBeCloseTo(1, 5);
  });

  it('ایجنت غیرفعال وزن صفر می گیرد نه وزن خام', () => {
    const w = effectiveWeights({ tape: sig('tape', 'bullish', 50, { confidence: 'nodata' }) }, NOW);
    expect(w.tape).toBe(0);
  });

  it('همه وزن ها غیرفعال ⇒ بدون رای فعال — همه صفر', () => {
    const w = effectiveWeights({ tape: sig('tape', 'bullish', 50, { validForMs: 1 }) }, NOW + 1000);
    expect(w.fundamental).toBe(0);
    expect(w.technical).toBe(0);
    expect(w.tape).toBe(0);
    expect(w.portfolio).toBe(0);
  });

  it('هر چهار فعال ⇒ نسبت وزن های خام', () => {
    const w = effectiveWeights({
      fundamental: fundSig('bullish', 80),
      technical: techSig('bullish', 60, ['trend']),
      tape: tapeSig('closing_auction_pop', 70),
      portfolio: sig('portfolio', 'neutral', 50),
    }, NOW);
    expect(w.fundamental).toBeCloseTo(0.4, 5);
    expect(w.technical).toBeCloseTo(0.3, 5);
    expect(w.tape).toBeCloseTo(0.2, 5);
    expect(w.portfolio).toBeCloseTo(0.1, 5);
  });
});

describe('گیت ۱ — بنیادی (شرط لازم)', () => {
  it('رد بنیادی ⇒ fail', () => {
    const g = fundamentalGate(fundSig('bearish', 25), NOW);
    expect(g.status).toBe('fail');
    expect(g.note).toContain('هرگز خرید');
  });

  it('بنیادی صعودی ⇒ pass', () => {
    expect(fundamentalGate(fundSig('bullish', 75), NOW).status).toBe('pass');
  });

  it('داده ناقص ⇒ nodata نه fail', () => {
    expect(fundamentalGate(fundSig('neutral', 50, 'incomplete'), NOW).status).toBe('nodata');
  });

  it('سیگنال غایب ⇒ missing', () => {
    expect(fundamentalGate(undefined, NOW).status).toBe('missing');
  });
});

describe('گیت ۲ — تکنیکال (موقعیت زمانی)', () => {
  it('ستاپ جت/پولبک ⇒ ورود مستقیم (pass)', () => {
    expect(technicalGate(techSig('bullish', 70, ['breakout']), NOW).status).toBe('pass');
    expect(technicalGate(techSig('bullish', 70, ['pullback']), NOW).status).toBe('pass');
  });

  it('بدون ستاپ ⇒ زیر نظر تا فیبو ۳۳-۴۰ (wait)', () => {
    const g = technicalGate(techSig('neutral', 50, ['range']), NOW);
    expect(g.status).toBe('wait');
    expect(g.note).toContain('فیبو ۳۳-۴۰');
  });

  it('نزولی ⇒ fail', () => {
    expect(technicalGate(techSig('bearish', 20, ['choch']), NOW).status).toBe('fail');
  });

  it('payload بدون ستاپ ⇒ pass (داده قدیمی گیت زمانی نمی سازد)', () => {
    const s = sig('technical', 'bullish', 70);
    expect(technicalGate(s, NOW).status).toBe('pass');
  });

  it('hasEntrySetup جت و پولبک را می شناسد', () => {
    expect(hasEntrySetup(techSig('bullish', 70, ['breakout', 'trend']))).toBe(true);
    expect(hasEntrySetup(techSig('neutral', 50, []))).toBe(false);
  });
});

describe('گیت ۳ — تابلو (تایید نقدینگی)', () => {
  it('الگوی ساعت ⇒ pass', () => {
    expect(tapeGate(tapeSig('closing_auction_pop', 75), NOW).status).toBe('pass');
  });

  it('حجم مشکوک بدون ساعت ⇒ wait', () => {
    const g = tapeGate(tapeSig('suspicious_volume', 55), NOW);
    expect(g.status).toBe('wait');
    expect(g.note).toContain('حجم مشکوک');
  });

  it('پاسخ ساده/سایر ⇒ wait', () => {
    expect(tapeGate(tapeSig('none', 40), NOW).status).toBe('wait');
  });
});

describe('تقدم سلسله مراتبی (Gating Pipeline)', () => {
  it('رد بنیادی ⇒ سهم هرگز خرید نمی گیرد — حتی با تکنیکال و تابلو قوی', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: fundSig('bearish', 25),
      technical: techSig('bullish', 90, ['breakout']),
      tape: tapeSig('closing_auction_pop', 85),
    }, NOW);
    expect(v.finalAction).not.toBe('buy');
    expect(v.finalAction).not.toBe('strong_buy');
    expect(v.finalAction).not.toBe('hold');
    expect(MasterVerdict.safeParse(v).success).toBe(true);
  });

  it('بدون ستاپ تکنیکال ⇒ خرید به زیر نظر تنزل می کند', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: fundSig('bullish', 85),
      technical: techSig('neutral', 55, ['range']),
      tape: tapeSig('closing_auction_pop', 70),
    }, NOW);
    expect(v.finalAction).toBe('watch');
  });

  it('ستاپ جت فعال ⇒ خرید می ماند', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: fundSig('bullish', 85),
      technical: techSig('bullish', 70, ['breakout']),
      tape: tapeSig('closing_auction_pop', 70),
    }, NOW);
    expect(v.finalAction === 'buy' || v.finalAction === 'strong_buy').toBe(true);
  });

  it('blockingGate اولین گیت شکست خورده را بر می گرداند', () => {
    const gates = runGatingPipeline({ fundamental: fundSig('bearish', 20), technical: techSig('bearish', 30, ['choch']) }, NOW);
    const blocked = blockingGate(gates);
    expect(blocked).not.toBeNull();
    expect(blocked?.gate).toBe('fundamental');
  });

  it('applyGateToAction — نگهداری با رد بنیادی به کاهش می رود', () => {
    const gates = runGatingPipeline({ fundamental: fundSig('bearish', 20) }, NOW);
    expect(applyGateToAction('hold', gates)).toBe('reduce');
    expect(applyGateToAction('strong_buy', gates)).toBe('watch');
  });
});

describe('وضعیت نگهداری (Holding State Logic)', () => {
  /** سیگنال پرتفوی با رأی در/برون سبد */
  function portSig(decision: 'accept' | 'monitor' | 'pending' | 'reject'): AgentSignal {
    return sig('portfolio', 'neutral', decision === 'accept' ? 55 : 40, {
      id: `portfolio:شپنا:${decision}:${NOW}`,
      confidence: 'medium',
      payload: { kind: 'position_state', decision, weightPct: decision === 'accept' ? 10 : null, stopLoss: null, alerts: [] },
    });
  }

  it('نماد خارج از سبد + گیت‌های ناتریگر ⇒ هرگز نگهداری؛ زیر نظر', () => {
    // بنیادی پاس ولی تکنیکال بدون ستاپ و تابلو بدون ساعت — برآیند خنثی میانه
    const input = {
      fundamental: fundSig('bullish', 55),
      technical: techSig('neutral', 50, ['range']),
      tape: tapeSig('suspicious_volume', 55, 'low'),
    };
    const v = aggregateSignals('شپنا', input, NOW);
    // نماد در سبد نیست (رأی پرتفوی accept نیست) ⇒ نگهداری صادر نمی شود
    expect(v.finalAction).not.toBe('hold');
    expect(v.finalAction).toBe('watch');
  });

  it('نماد خارج از سبد + بنیادی پاس + تکنیکال ناتریگر ⇒ زیر نظر حتی با نمره میانه', () => {
    const input = {
      fundamental: fundSig('bullish', 60),
      technical: techSig('bullish', 55, ['trend']), // روند هست ولی ستاپ ورود (جت/پولبک) نیست
    };
    const v = aggregateSignals('شپنا', input, NOW);
    expect(v.finalAction).not.toBe('hold');
    expect(v.finalAction).toBe('watch');
  });

  it('نماد در سبد (accept) بدون حد ضرر فعال ⇒ نگهداری مجاز می ماند', () => {
    const input = {
      fundamental: fundSig('bullish', 35), // نمره میانه پایین — برآیند خام = hold
      technical: techSig('neutral', 50, ['range']),
      portfolio: portSig('accept'),
    };
    const v = aggregateSignals('شپنا', input, NOW);
    expect(v.finalAction).toBe('hold');
  });

  it('نماد در سبد با ستاپ جت فعال ⇒ خرید/ورود، نه نگهداری', () => {
    const input = {
      fundamental: fundSig('bullish', 85),
      technical: techSig('bullish', 70, ['breakout']),
      portfolio: portSig('accept'),
    };
    const v = aggregateSignals('شپنا', input, NOW);
    expect(v.finalAction === 'buy' || v.finalAction === 'strong_buy').toBe(true);
  });

  it('نماد زیر نظر (monitor) در سبد نیست ⇒ نگهداری صادر نمی شود', () => {
    const input = {
      fundamental: fundSig('bullish', 55),
      technical: techSig('neutral', 50, ['range']),
      portfolio: portSig('monitor'),
    };
    const v = aggregateSignals('شپنا', input, NOW);
    expect(v.finalAction).not.toBe('hold');
    expect(v.finalAction).toBe('watch');
  });

  it('applyGateToAction — خارج از سبد نگهداری به زیر نظر تنزل می کند', () => {
    const gates = runGatingPipeline({ fundamental: fundSig('bullish', 55), technical: techSig('neutral', 50, ['range']) }, NOW);
    // بدون آرگومان سوم (holding) — پیش‌فرض خارج از سبد
    expect(applyGateToAction('hold', gates)).toBe('watch');
    // با آرگومان سوم true — در سبد
    expect(applyGateToAction('hold', gates, true)).toBe('hold');
  });

  it('isHoldingInBasket — فقط رأی accept فعال در سبد است', () => {
    expect(isHoldingInBasket({ portfolio: portSig('accept') }, NOW)).toBe(true);
    expect(isHoldingInBasket({ portfolio: portSig('monitor') }, NOW)).toBe(false);
    expect(isHoldingInBasket({ portfolio: portSig('pending') }, NOW)).toBe(false);
    expect(isHoldingInBasket({ portfolio: portSig('reject') }, NOW)).toBe(false);
    expect(isHoldingInBasket({}, NOW)).toBe(false);
  });
});

describe('رای ظرفیت پرتفوی برای نماد خارج از سبد', () => {
  it('نماد بدون تصمیم ⇒ رأی capacity نه بدون داده', async () => {
    const { portfolioSignal } = await import('@features/portfolio/model/portfolioSignals');
    const s = portfolioSignal({ symbol: 'شاملا', decision: null, currentPrice: 1000, sectorUsedPct: 5 }, 1726000000000);
    expect(s.direction).not.toBe('neutral');
    expect(s.confidence).not.toBe('nodata');
    expect(s.score).toBeGreaterThan(0);
    expect(s.title).toContain('ظرفیت');
    expect(s.rationale).toContain('ظرفیت');
  });

  it('سقف ۲۰٪ صنعت — ظرفیت باقی مانده درست است', async () => {
    const { industryCapacity, INDUSTRY_RISK_CAP_PCT } = await import('@features/portfolio/model/portfolioSignals');
    expect(INDUSTRY_RISK_CAP_PCT).toBe(20);
    const free = industryCapacity(0);
    expect(free.remainingPct).toBe(20);
    expect(free.score).toBe(100);
    const mid = industryCapacity(12);
    expect(mid.remainingPct).toBe(8);
    expect(mid.score).toBe(40);
    const full = industryCapacity(25);
    expect(full.remainingPct).toBe(0);
    expect(full.score).toBe(0);
    expect(full.note).toContain('پر شده');
  });
});

describe('سنthesis متن تضاد (قانون محور)', () => {
  it('تضاد بنیادی گرم / تکنیکال سرد به زبان ساده شرح داده می شود', () => {
    const input = { fundamental: fundSig('bullish', 85), technical: techSig('bearish', 25, ['choch']) };
    const v = aggregateSignals('شپنا', input, NOW);
    const gates = runGatingPipeline(input, NOW);
    const text = synthesizeVerdict('شپنا', input, v, gates, NOW);
    expect(text).toContain('بنیادی');
    expect(text).toContain('تکنیکال');
    expect(text).toContain('پیشنهاد مستر');
  });

  it('رد بنیادی در متن synthesis می آید', () => {
    const input = { fundamental: fundSig('bearish', 20), technical: techSig('bullish', 80, ['breakout']) };
    const v = aggregateSignals('شپنا', input, NOW);
    const gates = runGatingPipeline(input, NOW);
    const text = synthesizeVerdict('شپنا', input, v, gates, NOW);
    expect(text).toContain('گیت بنیادی');
    expect(text).toContain('هرگز خرید');
  });

  it('بدون رأی فعال متن صریح می دهد', () => {
    const text = synthesizeVerdict('شپنا', {}, aggregateSignals('شپنا', {}, NOW), runGatingPipeline({}, NOW), NOW);
    expect(text).toContain('هیچ رأی فعالی');
  });
});

describe('برنامه معاملاتی (Trade Plan)', () => {
  const feed = {
    fib: {
      zone_33_40: { lo: 33500, hi: 35200 },
      zone_618_70: { lo: 29500, hi: 31000 },
    },
    jet: { active: false, resistance: 36030 },
    exit: { l1: { hard_stop: 27987, stop_basis: 'swing_low', ma14: 34386 } },
  };

  it('پله ها از داده چارت ساخته می شوند', () => {
    const p = buildTradePlan({ ...feed, risk: 30 });
    expect(p.step1).not.toBeNull();
    expect(p.step1?.lo).toBe(33500);
    expect(p.step1?.hi).toBe(35200);
    expect(p.step2?.lo).toBe(29500);
    expect(p.breakout?.lo).toBe(36030);
  });

  it('حد ضرر ۵٪ زیر کف ماژور با پایه فارسی', () => {
    const p = buildTradePlan({ ...feed, risk: 30 });
    expect(p.stop.price).toBe(27987);
    expect(p.stop.basis).toContain('کف ماژور');
  });

  it('غیب داده چارت ⇒ null و برچسب بدون داده — بازتولید نمی شود', () => {
    const p = buildTradePlan({ fib: null, jet: null, exit: null, risk: 50 });
    expect(p.step1).toBeNull();
    expect(p.step2).toBeNull();
    expect(p.breakout).toBeNull();
    expect(p.stop.price).toBeNull();
    expect(p.stop.basis).toBe('بدون داده');
    expect(rial(p.step1?.lo ?? null)).toBe('بدون داده');
  });

  it('وزن پله ۲ تا ۵ درصد بر اساس ریسک', () => {
    expect(stepWeightPct(0)).toBe(5);
    expect(stepWeightPct(100)).toBe(2);
    expect(stepWeightPct(50)).toBe(3.5);
  });

  it('سطح ریسک با تضاد و گیت شکسته بالا می رود', () => {
    const low = riskLevel({ hasConflict: false, gateFails: 0, gateWaits: 0 });
    const high = riskLevel({ hasConflict: true, gateFails: 1, gateWaits: 2 });
    expect(low).toBe(20);
    expect(high).toBe(99); // 20 + 30 + 25 + 24 = 99 (سقف 100)
  });
});

describe('رگرسیون — داوری پایه', () => {
  it('میانگین وزنی هر چهار ایجنت (پایه قبلی حفظ شده)', () => {
    const v = aggregateSignals('شپنا', {
      fundamental: sig('fundamental', 'bullish', 80),
      technical: sig('technical', 'bullish', 60),
      tape: sig('tape', 'neutral', 50),
      portfolio: sig('portfolio', 'bullish', 70),
    }, NOW);
    // (4*80 + 3*60 + 2*0 + 1*70) / 10 = 57
    expect(v.compositeScore).toBe(57);
    expect(MasterVerdict.safeParse(v).success).toBe(true);
  });

  it('نمره علامت دار و فعالی (پایه قبلی)', () => {
    expect(signedScore(sig('tape', 'bullish', 80))).toBe(80);
    expect(signedScore(sig('tape', 'bearish', 80))).toBe(-80);
    expect(signedScore(sig('tape', 'neutral', 80))).toBe(0);
    expect(isActiveSignal(sig('tape', 'bullish', 80), NOW)).toBe(true);
    expect(isActiveSignal(sig('tape', 'bullish', 80, { confidence: 'nodata' }), NOW)).toBe(false);
  });
});
