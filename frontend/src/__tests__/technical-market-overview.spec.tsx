// تست نمای کل بورس (فاز ۱) — هندسهٔ چارت خطی نمای کلان + رندر بدون نماد
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { buildLineGeometry, finiteSeries } from '@features/technical/lib/macroChart';
import { MarketOverview } from '@features/technical/components/MarketOverview';

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe('هندسهٔ چارت خطی کلان', () => {
  it('کمتر از دو نقطه معتبر ⇒ بدون داده (null)', () => {
    expect(buildLineGeometry([])).toBeNull();
    expect(buildLineGeometry([5])).toBeNull();
    expect(buildLineGeometry([null, null])).toBeNull();
    expect(buildLineGeometry([1, Number.NaN])).toBeNull();
  });

  it('دو نقطه به بالا مسیر polyline می‌سازد', () => {
    const g = buildLineGeometry([10, 20, 15], 300, 120, 10);
    expect(g).not.toBeNull();
    expect(g!.points).toHaveLength(3);
    expect(g!.path.startsWith('M')).toBe(true);
    expect(g!.path.includes('L')).toBe(true);
    expect(g!.min).toBe(10);
    expect(g!.max).toBe(20);
  });

  it('خط تخت باعث تقسیم بر صفر نمی‌شود', () => {
    const g = buildLineGeometry([7, 7, 7], 300, 120, 10);
    expect(g).not.toBeNull();
    expect(g!.points.every((p) => Number.isFinite(p.y))).toBe(true);
  });

  it('رشتهٔ عددی و null در سری کلان فیلتر می‌شوند', () => {
    expect(finiteSeries([1, '2', null, 'x', undefined, 3])).toEqual([1, 2, 3]);
  });
});

describe('نمای کل بورس بدون نماد', () => {
  it('عنوان «کل بورس» و کارت‌های نبض رندر می‌شوند (نه صفحهٔ خالی)', async () => {
    withQuery(<MarketOverview />);
    expect(screen.getByTestId('market-overview')).toBeInTheDocument();
    expect(screen.getByText('کل بورس')).toBeInTheDocument();
    expect(screen.getByTestId('macro-stats')).toBeInTheDocument();
    // بدون داده‌ی fetched، کارت‌ها صادقانه «بدون داده» می‌دهند نه عدد ساختگی
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
  });

  it('دادهٔ غایب باعث علامت قرمز کاذب در کارت «تعادل صف‌ها» نمی‌شود', () => {
    withQuery(<MarketOverview />);
    const tile = screen.getByText('تعادل صف‌ها').closest('div') as HTMLElement;
    expect(tile).not.toBeNull();
    const value = tile.querySelector('.num') as HTMLElement;
    // نبود عمق بازار ⇒ «بدون داده» (نه صفر/نه قرمز کاذب)
    expect(value.textContent).toBe('بدون داده');
    expect(value.className).not.toContain('text-accent-red');
  });
});
