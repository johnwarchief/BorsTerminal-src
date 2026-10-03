// تستِ سیگنال تکنیکال: هیچ تشخیصی درِ فرانت ساخته نمی‌شود — فقط رأیِ موتورِ FTS
// (`/api/fts`) ترجمه می‌شود. هر سنجه یک کنترلِ منفی هم دارد: همان ورودی با رأیِ
// مخالفِ موتور باید خروجیِ مخالف بدهد (یعنی سنجه واقعاً ببیند، نه اینکه صفرِ جعلی بدهد).
import { describe, expect, it } from 'vitest';
import { technicalSignal, type TechInput } from '@features/technical/signals/technicalSignals';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

const closes = Array.from({ length: 120 }, (_, i) => 100 + i);

function input(fts: Partial<FtsAnalysisData> | null, patch: Partial<TechInput> = {}): TechInput {
  return {
    symbol: 'آزمون',
    opens: closes.map((c) => c - 1),
    closes,
    highs: closes.map((c) => c + 2),
    lows: closes.map((c) => c - 2),
    volumes: closes.map(() => 1000),
    riskGatePass: null,
    enforceRiskGates: false,
    weekly: null,
    fts: (fts == null ? null : { fib: { levels: [], zone_33_40: { in_zone: false },
      zone_618_70: { in_zone: false }, ...(fts.fib ?? {}) }, ...fts }) as FtsAnalysisData,
    ...patch,
  };
}

const run = (i: TechInput) => technicalSignal(i, 1726000000000);

describe('jets: فقط از jet.activeی موتور', () => {
  it('موتور جت را فعال می‌گوید ⇒ breakout با +3', () => {
    const s = run(input({ jet: { active: true, resistance: 3520, ath: true, pct_above_res: 5.4 } }));
    expect(s.payload.setups).toContain('breakout');
    expect(s.evidence).toContain('tech:jet_trigger');
    expect(s.rationale).toContain('سقف تاریخی');
  });

  it('کنترلِ منفی: عبورِ قیمت از مقاومتِ ۱۲۰ کندله ولی موتور می‌گوید «بدنهٔ نزولی» ⇒ هیچ جتی', () => {
    // سریِ عمداً صعودی + حجمِ بالا: اگر فرانت خودش تشخیص می‌داد، اینجا «شکست خط آبی» می‌گفت
    const s = run(input({ jet: { active: false, resistance: 101, reason: 'بدنهٔ نزولی: پایانی زیر آخرینِ بازِ همین نشست' } }));
    expect(s.payload.setups).not.toContain('breakout');
    expect(s.evidence).not.toContain('tech:jet_trigger');
    expect(s.rationale).toContain('جت نیست: بدنهٔ نزولی');
  });
});

describe('حد ضرر: عدد و مبنای خودِ موتورِ خروج', () => {
  it('l1.hard_stop با stop_basisِ خامِ موتور در payload می‌نشیند', () => {
    const s = run(input({ trend: { alignment: 'up' }, exit_engine: { verdict: 'hold', l1: { hard_stop: 2444.35, stop_basis: 'swing_low' } } }));
    expect(s.direction).toBe('bullish');
    expect(s.payload.stopLossPrice).toBe(2444.35);
    expect(s.payload.stopLossRef).toBe('swing_low');
  });

  it('مبنایِ موتور ترجمه/جایگزین نمی‌شود؛ نبودش یعنی null', () => {
    const s = run(input({ trend: { alignment: 'up' }, exit_engine: { verdict: 'hold', l1: { hard_stop: 2444.35 } } }));
    expect(s.payload.stopLossRef).toBeNull();
    expect(s.payload.stopLossPrice).toBe(2444.35);
  });
});

describe('خروج و واگرایی: از لایه‌های موتور', () => {
  it('ma14_exit فعال ⇒ سه نمره کم و سقفِ جهت در انتظار', () => {
    const s = run(input({ trend: { alignment: 'up' }, exit_engine: { verdict: 'exit', l1: { ma14_exit: true } } }));
    expect(s.direction).not.toBe('bullish');
    expect(s.evidence).toContain('tech:ma14_exit');
  });

  it('rsi_divergence در l4 ⇒ bearish_div؛ بی‌آن هیچ واگرایی‌ای از قیمت حساب نمی‌شود', () => {
    const s = run(input({ exit_engine: { verdict: 'hold', l4: { rsi_divergence: true } } }));
    expect(s.payload.setups).toContain('bearish_div');
    const n = run(input({ exit_engine: { verdict: 'hold', l4: { rsi_divergence: false } } }));
    expect(n.payload.setups).not.toContain('bearish_div');
  });
});

describe('فیبو و CHoCH', () => {
  it('داخل کمربند ۶۱٫۸–۷۰ ⇒ fibonacci؛ خارج از هر دو ⇒ نه', () => {
    const in_ = run(input({ fib: { zone_618_70: { in_zone: true } } }));
    expect(in_.payload.setups).toContain('fibonacci');
    const out_ = run(input({ fib: { zone_618_70: { in_zone: false }, zone_33_40: { in_zone: false } } }));
    expect(out_.payload.setups).not.toContain('fibonacci');
  });

  it('CHoCH نزولی −۳ و صعودی +۲، همان‌که موتور می‌گوید', () => {
    const bear = run(input({ choch: { bearish: true, bullish: false, level: 3407 } }));
    const bull = run(input({ choch: { bearish: false, bullish: true, level: 3407 } }));
    expect(bear.score).toBeLessThan(bull.score ?? 0);
    expect(bear.rationale).toContain('CHoCH نزولی');
  });
});

describe('وتوی هفتگی و بی‌رأیی', () => {
  it('matrix.decision=REJECT جهتِ صعودی را به انتظار برمی‌گرداند (قانونِ درخت، نه قانونِ جدید)', () => {
    const s = run(input({ trend: { alignment: 'up', matrix: { decision: 'REJECT' } }, jet: { active: true } }));
    expect(s.direction).toBe('neutral');
    expect(s.evidence).toContain('tech:weekly_veto');
    expect(s.title).toContain('وتوی تایم هفتگی');
  });

  it('بی‌پاسخِ موتور: هیچ تشخیصی ساخته نمی‌شود و dataQuality partial است', () => {
    const s = run(input(null));
    expect(s.confidence).toBe('low');
    expect(s.payload.dataQuality).toBe('partial');
    expect(s.evidence).toEqual(['tech:awaiting_engine']);
    expect(s.title).toContain('در انتظار رأیِ موتور');
  });

  it('گیت ریسک بنیادی همچنان بر صدورِ سیگنال مقدم است', () => {
    const s = run(input({ trend: { alignment: 'up' }, jet: { active: true } },
      { enforceRiskGates: true, riskGatePass: false }));
    expect(s.direction).toBe('neutral');
    expect(s.payload.setups).toEqual([]);
    expect(s.evidence).toEqual(['tech:risk_gate_block']);
  });
});
