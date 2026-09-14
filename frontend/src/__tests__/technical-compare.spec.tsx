// تست مقایسهٔ چند نماد (T-10 قطعهٔ ۳): نرمال‌سازی base=100 + هم‌ترازی + هندسه + پنل
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import type { KLineData } from '@vendor/klinecharts';
import { COMPARE_BASE, COMPARE_COLORS, alignCompare, baseLineY, compareGeometry, normalizeTo100 } from '@features/technical/lib/compare';
import { ComparePanel } from '@features/technical/components/ComparePanel';

const t0 = Date.UTC(2025, 0, 1);
function bars(closes: number[]): KLineData[] {
  return closes.map((c, i) => ({ timestamp: t0 + i * 86_400_000, open: c, high: c, low: c, close: c, volume: 1 }));
}
function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe('نرمال‌سازی و هم‌ترازی مقایسه', () => {
  it('نرمال‌سازی به پایهٔ ۱۰۰ از اولین بسته', () => {
    const n = normalizeTo100(bars([10, 12, 15]));
    expect(n.values).toEqual([100, 120, 150]);
    expect(n.ts).toHaveLength(3);
  });

  it('سری خالی ⇒ خروجی خالی (صادقانه)', () => {
    expect(normalizeTo100([])).toEqual({ ts: [], values: [] });
    expect(normalizeTo100(bars([0, 0]))).toEqual({ ts: [], values: [] });
  });

  it('هم‌ترازی روی زمان‌های مشترک و درصد تغییر', () => {
    const a = bars([10, 12, 15]).slice(0, 3);
    const b = [{ ...bars([20, 22, 25])[1] }, bars([20, 22, 25])[2]];
    const r = alignCompare([
      { symbol: 'الف', candles: a },
      { symbol: 'ب', candles: b },
    ]);
    // زمان مشترک: دو کندل آخر
    expect(r.timestamps).toHaveLength(2);
    expect(r.lines).toHaveLength(2);
    // «الف» از کندل دوم پایه می‌شود: 12→100 و 15→125
    expect(r.lines[0].values[0]).toBeCloseTo(COMPARE_BASE, 6);
    expect(r.lines[0].values[1]).toBeCloseTo(125, 6);
    expect(r.lines[0].changePct).toBeCloseTo(25, 6);
  });

  it('زمان مشترک کمتر از دو نقطه ⇒ بدون خط', () => {
    const r = alignCompare([
      { symbol: 'الف', candles: bars([10, 11]) },
      { symbol: 'ب', candles: bars([20, 21]).map((c) => ({ ...c, timestamp: c.timestamp + 5 * 86_400_000 })) },
    ]);
    expect(r.lines).toEqual([]);
    expect(compareGeometry(r)).toBeNull();
  });
});

describe('هندسهٔ چارت مقایسه', () => {
  const result = alignCompare([{ symbol: 'الف', candles: bars([10, 12, 15]) }]);

  it('مسیر خط و رنگ ساخته می‌شود', () => {
    const g = compareGeometry(result, 300, 100, 10);
    expect(g).not.toBeNull();
    expect(g!.lines[0].path.startsWith('M')).toBe(true);
    expect(g!.lines[0].color).toBe(COMPARE_COLORS[0]);
    expect(g!.min).toBeLessThanOrEqual(100);
    expect(g!.max).toBeGreaterThanOrEqual(100);
  });

  it('y خط مرجع ۱۰۰ داخل محدودهٔ چارت است', () => {
    const g = compareGeometry(result, 300, 100, 10)!;
    const y = baseLineY(g, 100, 10);
    expect(y).toBeGreaterThanOrEqual(10);
    expect(y).toBeLessThanOrEqual(90);
  });
});

describe('پنل مقایسه', () => {
  it('بسته فقط دکمهٔ بازکردن را دارد؛ بعد از باز شدن ورودی و پیام بدون‌داده', async () => {
    withQuery(<ComparePanel activeSymbol="فولاد" />);
    expect(screen.getByTestId('compare-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('compare-input')).toBeNull();
    fireEvent.click(screen.getByTestId('compare-toggle'));
    expect(screen.getByTestId('compare-input')).toBeInTheDocument();
    // در jsdom دادهای fetch نمی‌شود ⇒ هندسه null و پیام صادقانه
    expect(await screen.findByTestId('compare-empty')).toBeInTheDocument();
  });

  it('افزودن و حذف نماد رخدادهای UI را می‌سازد', () => {
    withQuery(<ComparePanel activeSymbol="فولاد" />);
    fireEvent.click(screen.getByTestId('compare-toggle'));
    fireEvent.change(screen.getByTestId('compare-input'), { target: { value: 'خودرو' } });
    fireEvent.click(screen.getByTestId('compare-add'));
    expect(screen.getByTestId('compare-remove-خودرو')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('compare-remove-خودرو'));
    expect(screen.queryByTestId('compare-remove-خودرو')).toBeNull();
  });
});
