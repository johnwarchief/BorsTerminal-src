import { describe, expect, it } from 'vitest';
import { detectAllPatterns } from '../registry';
import { PATTERN_CONFIG } from '../config';
import type { EngineCandle } from '../../doubleTapEngine';

/** ۵۰۰ کندل مصنوعی با نوسانِ کافی برای درگیرکردنِ همهٔ دتکتورها. */
function series(n = 500): EngineCandle[] {
  return Array.from({ length: n }, (_, i) => {
    const base = 100 + Math.sin(i / 7) * 8 + Math.sin(i / 23) * 4;
    return {
      timestamp: 1_700_000_000_000 + i * 60_000,
      open: base,
      high: base + 1.2,
      low: base - 1.2,
      close: base + 0.3,
    };
  });
}

// spec §۴: اسکنِ ۵۰۰ کندل باید زیرِ بودجهٔ ۵۰ms بماند و هیچ long task نسازد.
describe('اسکنِ الگوها — بودجهٔ زمان', () => {
  it('۵۰۰ کندل را زیرِ ۵۰ms اسکن می‌کند', () => {
    const candles = series(500);
    // یک اجرای گرم‌کردن تا JIT و ساختِ کشِ اولیه در اندازه‌گیری نیاید.
    detectAllPatterns(candles, PATTERN_CONFIG);
    const t0 = performance.now();
    detectAllPatterns(candles, PATTERN_CONFIG);
    const ms = performance.now() - t0;
    expect(ms).toBeLessThan(50);
  });

  it('سریِ کوتاه و بی‌نوسان را بدونِ خطا و سریع برمی‌گرداند', () => {
    const flat: EngineCandle[] = Array.from({ length: 40 }, (_, i) => ({
      timestamp: i * 60_000, open: 100, high: 101, low: 99, close: 100,
    }));
    const t0 = performance.now();
    expect(detectAllPatterns(flat, PATTERN_CONFIG)).toEqual([]);
    expect(performance.now() - t0).toBeLessThan(20);
  });
});
