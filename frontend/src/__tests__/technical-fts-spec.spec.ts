// تست هم‌خوانی FTS با مرجع (T-03 بخش ۱): MA14 کامل، آستانهٔ CHoCH، RSI وایلدر، واگرایی منفی، حد ضرر نوسان‌گیر
import { describe, expect, it } from 'vitest';
import { bearishDivergence, detectChoch, ma14TrailingExit, rsi } from '@features/technical/lib/indicators';
import { technicalSignal, type TechInput } from '@features/technical/signals/technicalSignals';

function flat(n: number): number[] {
  return new Array(n).fill(100);
}

describe('خروج MA14 — «کندل کامل زیر خط»', () => {
  const ma = new Array(20).fill(100);

  it('کندل کامل (OHLC) زیر خط ⇒ خروج', () => {
    const opens = [...flat(19), 95];
    const highs = [...flat(19), 96];
    const lows = [...flat(19), 94];
    const closes = [...flat(19), 95];
    const r = ma14TrailingExit(opens, highs, lows, closes, ma);
    expect(r.exit).toBe(true);
    expect(r.pending).toBe(false);
  });

  it('بدنه زیر خط ولی سایهٔ بالا بالای خط ⇒ انتظار (نه خروج)', () => {
    const opens = [...flat(19), 95];
    const highs = [...flat(19), 102];
    const lows = [...flat(19), 94];
    const closes = [...flat(19), 95];
    const r = ma14TrailingExit(opens, highs, lows, closes, ma);
    expect(r.exit).toBe(false);
    expect(r.pending).toBe(true);
  });

  it('کندل بالای خط ⇒ نه خروج نه انتظار', () => {
    const opens = [...flat(19), 101];
    const highs = [...flat(19), 103];
    const lows = [...flat(19), 100];
    const closes = [...flat(19), 102];
    const r = ma14TrailingExit(opens, highs, lows, closes, ma);
    expect(r.exit).toBe(false);
    expect(r.pending).toBe(false);
  });
});

describe('CHoCH — آستانهٔ قطعی بسته‌شدن (۰٫۳٪)', () => {
  const highs = [100, 100, 100, 100, 100, 105, 100, 100, 100, 100, 100, 110, 100, 100, 100, 100, 100];
  const lows = [98, 98, 98, 98, 98, 98, 98, 98, 96, 98, 98, 98, 98, 98, 97, 98, 98];

  it('شکست قطعی کف ⇒ نزولی', () => {
    const closes = [99, 99, 99, 99, 99, 100, 99, 99, 98, 99, 99, 100, 99, 99, 98, 97, 95];
    expect(detectChoch(highs, lows, closes, 2).type).toBe('bearish');
  });

  it('شکست ناکافی (کمتر از ۰٫۳٪) ⇒ بدون سیگنال', () => {
    const closes = [99, 99, 99, 99, 99, 100, 99, 99, 98, 99, 99, 100, 99, 99, 98, 97, 96.9];
    // آخرین بسته = 96.9 ؛ سطح 97 ⇒ آستانه = 96.709 ؛ 96.9 بالای آستانه است
    expect(detectChoch(highs, lows, closes, 2).type).toBeNull();
  });
});

describe('RSI وایلدر', () => {
  it('سری صعودی خالص ⇒ ۱۰۰ و دوره‌های آغازین null', () => {
    const vals = Array.from({ length: 25 }, (_, i) => 100 + i);
    const out = rsi(vals, 14);
    expect(out[13]).toBeNull();
    expect(out[14]).toBe(100);
    expect(out[24]).toBe(100);
  });

  it('سری نزولی خالص ⇒ ۰', () => {
    const vals = Array.from({ length: 25 }, (_, i) => 200 - i);
    expect(rsi(vals, 14)[24]).toBe(0);
  });

  it('مقدار مرجع کلاسیک وایلدر در بازهٔ درست است', () => {
    const vals = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.1, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28];
    const v = rsi(vals, 14)[14];
    expect(v).not.toBeNull();
    expect(v as number).toBeGreaterThan(69);
    expect(v as number).toBeLessThan(72);
  });
});

describe('واگرایی منفی (RD−)', () => {
  const highs = [8, 8, 8, 8, 8, 10, 8, 8, 8, 8, 8, 8, 8, 8, 12, 8, 8, 8, 8, 8];
  const rsiSeries = new Array(20).fill(50);

  it('سقف قیمتی بالاتر + سقف RSI پایین‌تر ⇒ واگرایی', () => {
    const r = [...rsiSeries];
    r[5] = 70;
    r[14] = 60;
    expect(bearishDivergence(highs, r, 3, 20)).toBe(true);
  });

  it('RSI هم‌جهت صعودی ⇒ بدون واگرایی', () => {
    const r = [...rsiSeries];
    r[5] = 60;
    r[14] = 80;
    expect(bearishDivergence(highs, r, 3, 20)).toBe(false);
  });
});

describe('حد ضرر نوسان‌گیر = ۵٪ زیر آخرین کف سوینگ', () => {
  function input(): TechInput {
    const n = 140;
    const closes = new Array(n).fill(100);
    const dip = [100, 99, 97, 94, 90, 93, 97];
    for (let i = 0; i < dip.length; i++) closes[40 + i] = dip[i];
    for (let i = 47; i < n; i++) closes[i] = 100 + (i - 46) * 1.2;
    return {
      symbol: 'فولاد',
      closes,
      opens: closes.map((c) => c - 0.5),
      highs: closes.map((c) => c + 1),
      lows: closes.map((c) => c - 1),
      volumes: new Array(n).fill(1000),
      riskGatePass: true,
      enforceRiskGates: true,
    };
  }

  it('با وجود کف سوینگ، مرجع rising_low و مقدار ۹۵٪ کف', () => {
    const s = technicalSignal(input(), 1726000000000);
    expect(s.direction).toBe('bullish');
    expect(s.payload.stopLossRef).toBe('rising_low');
    expect(s.payload.stopLossPrice as number).toBeCloseTo(84.55, 1);
  });
});
