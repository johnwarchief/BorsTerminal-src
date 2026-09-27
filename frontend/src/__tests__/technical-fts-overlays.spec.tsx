// اورلی‌های FTSِ چارت (#161): چارت باید همان اعدادِ سرور را رسم کند، نه چیزی که
// خودش حساب کرده باشد. اینجا هندسهٔ رسم را اندازه می‌گیریم، نه متن را.
import { act, fireEvent, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type OverlayCfg = { name?: string; groupId?: string; points?: { timestamp: number; value: number }[];
  extendData?: unknown; [key: string]: unknown };

let overlays: OverlayCfg[] = [];
const chartStub = () => ({
  setDataLoader: vi.fn(), setSymbol: vi.fn<(o: unknown) => void>(), setPeriod: vi.fn(),
  setFormatter: vi.fn(), createIndicator: vi.fn(), removeIndicator: vi.fn(),
  setPaneOptions: vi.fn(), setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideOverlay: vi.fn(),
  removeOverlay: vi.fn((q?: { groupId?: string }) => {
    if (q?.groupId === 'fts_strategy_overlays') overlays = [];
  }),
  createOverlay: vi.fn((cfg: OverlayCfg) => { if (cfg.groupId === 'fts_strategy_overlays') overlays.push(cfg); return 'ov'; }),
  resetData: vi.fn(), resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''),
  subscribeAction: vi.fn(), scrollToRealTime: vi.fn(), getDataList: vi.fn(() => []),
  setScrollEnabled: vi.fn(), getOverlays: vi.fn(() => [] as unknown[]),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(), registerOverlay: vi.fn(), registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

/** سه سطحِ فیبوی سرور، دو مارکرِ تاریخ‌دار و یک هشدار خروج — همه دست‌ساز */
const FTS = {
  fib: {
    retrace_base_high: 200, retrace_base_low: 100,
    zone_33_40: { lo: 155, hi: 165, in_zone: false },
    zone_618_70: { lo: 128, hi: 138, in_zone: false },
    levels: [
      { ratio: 0, price: 200 }, { ratio: 0.33, price: 165 }, { ratio: 0.4, price: 155 },
      { ratio: 0.5, price: 139 }, { ratio: 0.618, price: 128 }, { ratio: 0.7, price: 120 },
      { ratio: 1, price: 100 },
    ],
    leg: { direction: 'up', start: '2025-01-06', end: '2025-01-10', high: 200, low: 100 },
  },
  setups: [
    { date: '2025-01-07', kind: 'jet', label: 'جت', price: 210, side: 'above' },
    { date: '2025-01-09', kind: 'choch', label: 'CHoCH', price: 150, side: 'below' },
  ],
  exit_engine: { verdict: 'exit', l1: { ma14_exit: true } },
} as never;

const CANDLES = ['2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09', '2025-01-10']
  .map((time, i) => ({ time, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i, volume: 10 }));

const dayUtc = (s: string) => Date.parse(`${s}T00:00:00Z`);

async function renderChart() {
  overlays = [];
  vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
    const u = String(url);
    if (u.startsWith('/api/chart/')) {
      return { ok: true, json: async () => ({ status: 'success', candles: CANDLES, volumes: [],
        factors: CANDLES.map((c) => ({ time: c.time, factor: 1 })), adjustEvents: [] }) } as never;
    }
    return { ok: false, json: async () => ({}) } as never;
  }));
  render(<KLineChartWrapper initialSymbol="فولاد" fts={FTS} />);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  // از «تعدیل عملکردی» (پیش‌فرض) به «بدون تعدیل» تا عددِ محور همان ریالِ سرور باشد
  await act(async () => { fireEvent.click(document.querySelector('[title="نوع تعدیل قیمت"]') as HTMLElement); });
  const none = Array.from(document.querySelectorAll('.nn-dropdown-item'))
    .find((e) => (e.textContent ?? '').includes('بدون تعدیل')) as HTMLElement;
  await act(async () => { fireEvent.click(none); });
  await act(async () => { await Promise.resolve(); });
}

const drawn = (name: string) => overlays.filter((o) => o.name === name);

describe('اورلی FTS روی چارت، از دادهٔ سرور (#161)', () => {
  beforeEach(() => { vi.clearAllMocks(); overlays = []; });

  it('هر هفت سطحِ فیبو با همان عددِ سرور رسم می‌شود', async () => {
    await renderChart();
    const lines = drawn('horizontalStraightLine');
    const values = lines.map((o) => o.points?.[0]?.value).sort((a, b) => (a ?? 0) - (b ?? 0));
    expect(values).toEqual([100, 120, 128, 139, 155, 165, 200]);
  });

  it('هیچ عددِ فیبویی که سرور نگفته روی چارت نمی‌نشیند', async () => {
    await renderChart();
    const allowed = new Set((FTS as never as { fib: { levels: { price: number }[] } }).fib.levels.map((l) => l.price));
    for (const o of drawn('horizontalStraightLine')) {
      expect(allowed.has(o.points?.[0]?.value as number)).toBe(true);
    }
  });

  it('نوارِ کمربند از آغازِ موج شروع می‌شود، نه از «الان»', async () => {
    await renderChart();
    const rects = drawn('rect');
    expect(rects.length).toBe(2);
    for (const r of rects) {
      expect(r.points?.[0]?.timestamp).toBe(dayUtc('2025-01-06'));
      expect(r.points?.[1]?.timestamp).toBe(dayUtc('2025-01-10'));
    }
    expect(rects.map((r) => r.points?.[1]?.value).sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual([128, 155]);
    expect(rects.map((r) => r.points?.[0]?.value).sort((a, b) => (a ?? 0) - (b ?? 0))).toEqual([138, 165]);
  });

  it('مارکرهای ستاپ سرور سرِ کندلِ خودشان می‌نشینند', async () => {
    await renderChart();
    const marks = drawn('simpleAnnotation');
    expect(marks.map((m) => m.extendData).sort()).toEqual(['CHoCH', 'جت'].sort());
    const byLabel = Object.fromEntries(marks.map((m) => [m.extendData as string, m]));
    expect(byLabel['جت']?.points?.[0]?.timestamp).toBe(dayUtc('2025-01-07'));
    expect(byLabel['CHoCH']?.points?.[0]?.timestamp).toBe(dayUtc('2025-01-09'));
  });

  it('هشدار خروج از موتورِ سرور می‌آید، نه از شرطِ تک‌کندلیِ چارت', async () => {
    await renderChart();
    expect((document.querySelector('.nn-fts-exit-alert')?.textContent ?? '')).toContain('هشدار خروج');
  });
});
