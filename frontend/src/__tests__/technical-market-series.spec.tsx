// تست لایهٔ دادهٔ واحد «کل بورس» + رادار + fallback اولین screener (ادامهٔ فاز ۱)
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { buildMarketSeries, buildWholeMarket, TEDPIX_SOURCE } from '@features/technical/api/useMarketSeries';
import { FTS_FIB_BANDS, FTS_FIB_LEVELS } from '@features/technical/lib/ftsOverlays';
import { buildDrawingGroups, toolLabel } from '@features/technical/lib/drawingTools';
import type { KLineData } from '@vendor/klinecharts';
import { buildRadarAxes, radarComplete, radarLabelPositions, radarPolygon } from '@features/technical/lib/radar';
import { firstScreenerSymbol, type ScreenerRow } from '@features/technical/api/useScreener';
import { SidebarRadar } from '@features/technical/components/SidebarRadar';
import type { MacroTimeline } from '@features/technical/api/useMarketMacro';

function timeline(partial: Partial<MacroTimeline>): MacroTimeline {
  return { status: 'ok', ...partial } as MacroTimeline;
}

function withQuery(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

function srow(p: Partial<ScreenerRow>): ScreenerRow {
  return { symbol: 'x', ...p } as unknown as ScreenerRow;
}

describe('لایهٔ دادهٔ واحد «کل بورس»', () => {
  it('نبود تایم‌لاین ⇒ null', () => {
    expect(buildMarketSeries(null)).toBeNull();
    expect(buildMarketSeries(undefined)).toBeNull();
  });

  it('نقاط معتبر جدا و ready وقتی دو نقطه و ready=true', () => {
    const s = buildMarketSeries(
      timeline({ ready: true, day: 20260913, source: 'local:market.db', series: { val_bt: [10, '20', null, Number.NaN], t: ['09:00', '10:00', null, null] } }),
    );
    expect(s).not.toBeNull();
    expect(s!.points).toHaveLength(2);
    expect(s!.points[1]).toEqual({ label: '10:00', value: 20 });
    expect(s!.ready).toBe(true);
    expect(s!.source).toBe('local:market.db');
    expect(s!.day).toBe(20260913);
  });

  it('ready=false وقتی سرور می‌گوید آماده نیست', () => {
    const s = buildMarketSeries(timeline({ ready: false, series: { val_bt: [1], t: ['12:58'] } }));
    expect(s!.ready).toBe(false);
  });
});

function kline(n: number): KLineData[] {
  return Array.from({ length: n }, (_, i) => ({ timestamp: i * 86400000, open: 1, high: 2, low: 0.5, close: 1.5 }));
}

describe('انتخاب منبع سری «کل بورس»', () => {
  it('شاخص واقعی (کندل) اولویت دارد', () => {
    const w = buildWholeMarket(kline(3), buildMarketSeries(timeline({ ready: true, series: { val_bt: [1, 2], t: ['a', 'b'] } })));
    expect(w.kind).toBe('candles');
    expect(w.source).toBe(TEDPIX_SOURCE);
  });

  it('در نبود شاخص، سری کلان میشود', () => {
    const w = buildWholeMarket([], buildMarketSeries(timeline({ ready: true, series: { val_bt: [1, 2], t: ['a', 'b'] } })));
    expect(w.kind).toBe('macro');
  });

  it('نبود هر دو ⇒ none', () => {
    expect(buildWholeMarket([], null).kind).toBe('none');
  });
});

describe('کاتالوگ ابزارهای ترسیم FTS', () => {
  it('سطوح فیبوی FTS طبق FTS_SPEC بند ۳', () => {
    expect([...FTS_FIB_LEVELS]).toEqual([0, 0.33, 0.4, 0.618, 0.7, 1]);
    expect(FTS_FIB_BANDS.map((b) => [...b])).toEqual([[0.33, 0.4], [0.618, 0.7]]);
  });

  it('ابزارهای سفارشی FTS حتی بدون پشتیبانی vendor می‌مانند', () => {
    const g = buildDrawingGroups([]);
    const names = g.flatMap((x) => x.tools.map((t) => t.name));
    expect(names).toContain('ftsFib');
    expect(names).toContain('ftsMeasure');
    expect(names).toContain('ftsPosition');
    expect(names).not.toContain('straightLine'); // vendor-supported، بدون پشتیبانی حذف می‌شود
    expect(toolLabel('ftsPosition')).toBe('پوزیشن لانگ/شورت');
  });
});

describe('رادار بازار', () => {
  it('نرمال‌سازی محورها به ۰..۱۰۰', () => {
    const axes = buildRadarAxes({ positivePct: 70.6, power: 1, queueRatio: 1.5, tradedSharePct: 90 });
    expect(axes.map((a) => a.value)).toEqual([70.6, 50, 50, 90]);
    expect(radarComplete(axes)).toBe(true);
  });

  it('ورودی غایب ⇒ null و رادار ناقص', () => {
    const axes = buildRadarAxes({ positivePct: null, power: 1, queueRatio: null, tradedSharePct: 90 });
    expect(axes[0].value).toBeNull();
    expect(radarComplete(axes)).toBe(false);
  });

  it('چندضلعی رادار برای مقادیر معتبر ساخته و برای نامعتبر null می‌شود', () => {
    const g = radarPolygon([100, 50, 75, 25], 100, 100, 60);
    expect(g).not.toBeNull();
    expect(g!.points).toHaveLength(4);
    expect(g!.path.startsWith('M')).toBe(true);
    expect(radarPolygon([50, 50], 100, 100, 60)).toBeNull();
    expect(radarPolygon([50, 50, Number.NaN], 100, 100, 60)).toBeNull();
    expect(radarLabelPositions(4, 100, 100, 60)).toHaveLength(4);
  });
});

describe('fallback اولین screener', () => {
  it('واچ‌لیست غیرمردود مقدم است، سپس اولین غیرمردود، وگرنه null', () => {
    expect(firstScreenerSymbol([srow({ symbol: 'الف', excluded: true }), srow({ symbol: 'ب', watchlist: true })])).toBe('ب');
    expect(firstScreenerSymbol([srow({ symbol: 'ج' })])).toBe('ج');
    expect(firstScreenerSymbol([])).toBeNull();
  });
});

describe('تب رادار در سایدبار', () => {
  it('بدون داده، صادقانه «بدون داده» نشان می‌دهد', async () => {
    withQuery(<SidebarRadar />);
    expect(screen.getByTestId('sidebar-radar')).toBeInTheDocument();
    expect(screen.getByTestId('radar-empty')).toBeInTheDocument();
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
  });
});
