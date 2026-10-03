// نگهبانِ قراردادِ رویدادِ کلیک رویِ چارت (کار #48).
// دو چیز سنجیده می‌شود: (۱) ریدرِ خامِ `onCandleBarClick` به رویدادی می‌رسد که
// نماد/بازه/میله/نتیجهٔ موتور را پایدار نگه می‌دارد و درِ لاگِ محلی می‌ماند؛
// (۲) هیچ تشخیصِ ستاپی درِ فرانت بازسازی نمی‌شود — اگر موتور برایِ آن میله چیزی
// نگفته باشد، رویداد «کندل» است، نه ستاپِ حدسی.
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { buildBarClick, describeClick } from '@features/technical/nahayatnegar/lib/barClicks';
import { useChartClickStore, CLICK_LOG_CAP } from '@features/technical/stores/chartClickStore';

const ts = (d: string) => Date.parse(`${d}T00:00:00Z`);
const bar = (d: string, close = 100) => ({ timestamp: ts(d), open: close - 1, high: close + 2, low: close - 2, close, volume: 10 });

type ClickCb = (data?: unknown) => void;
let clickHandlers: ClickCb[] = [];
let overlays: Record<string, unknown>[] = [];

const chartStub = () => ({
  setDataLoader: vi.fn(), setSymbol: vi.fn(), setPeriod: vi.fn(), setFormatter: vi.fn(),
  createIndicator: vi.fn(), removeIndicator: vi.fn(), setPaneOptions: vi.fn(),
  setStyles: vi.fn(), overrideYAxis: vi.fn(), overrideOverlay: vi.fn(),
  createOverlay: vi.fn(() => 'ov-1'), removeOverlay: vi.fn(), resetData: vi.fn(),
  resize: vi.fn(), getConvertPictureUrl: vi.fn(() => ''),
  subscribeAction: vi.fn((type: string, cb: ClickCb) => {
    if (type === 'onCandleBarClick') clickHandlers.push(cb);
  }),
  unsubscribeAction: vi.fn(),
  scrollToRealTime: vi.fn(), getDataList: vi.fn(() => []), setScrollEnabled: vi.fn(),
  getOverlays: vi.fn(() => overlays),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
  registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
  getSupportedIndicators: vi.fn(() => []),
}));

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as unknown as Response;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  clickHandlers = [];
  overlays = [];
  useChartClickStore.setState({ clicks: [] });
  vi.stubGlobal('fetch', vi.fn(async () =>
    ok({
      status: 'success',
      candles: [bar('2025-01-05'), bar('2025-01-06'), bar('2025-01-07')],
      volumes: [], factors: [], adjustEvents: [],
    })));
});

describe('سازندۀ رویداد (بدون DOM)', () => {
  it('بی‌میله یا بی‌نماد ⇒ هیچ رویدادی؛ عددِ صفر یا تاریخِ جعلی ساخته نمی‌شود', () => {
    expect(buildBarClick({ symbol: 'فولاد', timeframe: 'D', bar: null })).toBeNull();
    expect(buildBarClick({ symbol: '', timeframe: 'D', bar: bar('2025-01-06') as never })).toBeNull();
    expect(buildBarClick({
      symbol: 'فولاد', timeframe: 'D', bar: { timestamp: 0, close: 1 } as never,
    })).toBeNull();
  });

  it('نتیجۀ موتور از همان میله می‌آید و ستاپِ روزِ دیگر به آن نمی‌چسبد', () => {
    const e = buildBarClick({
      symbol: 'فولاد',
      timeframe: 'D',
      bar: bar('2025-01-08', 120) as never,
      setups: [
        { date: '2025-01-08', kind: 'jet', label: 'جت', price: 130 },
        { date: '2025-01-07', kind: 'choch', label: 'تغییر ساختار', price: 90 },
      ],
    });
    expect(e).not.toBeNull();
    expect(e!.symbol).toBe('فولاد');
    expect(e!.timeframe).toBe('D');
    expect(e!.barDate).toMatch(/^\d{4}\/\d{2}\/\d{2}$/);
    expect(e!.engineSetups).toEqual([{ kind: 'jet', label: 'جت', price: 130 }]);
    expect(e!.close).toBe(120);
    // نه مارکرِ رسم‌شده و نه ستاپی رویِ خودِ میله ⇒ کلیکِ کندل، نه مارکر
    expect(e!.kind).toBe('candle');
    expect(e!.marker).toBeNull();
  });

  it('میله‌ای که موتور رویش برچسب گذاشته ⇒ رویدادِ مارکر با همان برچسب', () => {
    const t = ts('2025-01-08');
    const e = buildBarClick({
      symbol: 'فولاد',
      timeframe: 'W',
      bar: bar('2025-01-08', 120) as never,
      setups: [{ date: '2025-01-08', kind: 'jet', label: 'جت', price: 130 }],
      overlays: [{ name: 'simpleAnnotation', groupId: 'fts_strategy_overlays',
                   points: [{ timestamp: t }], extendData: 'جت • دو کف' }],
      adjustments: [{ timestamp: t, ratio: 1.2345 }],
    });
    expect(e!.kind).toBe('marker');
    expect(e!.marker).toBe('جت • دو کف');
    expect(e!.adjustRatio).toBe(1.2345);
    expect(describeClick(e!)).toContain('۱٫۲۳۴۵');
    expect(e!.key).toContain('|W|');
  });

  it('تطبیقِ تعدیل با timestamp است، نه با رشتهٔ تاریخِ سرور (سرور میلادی می‌فرستد)', () => {
    const t = ts('2025-01-08');
    const e = buildBarClick({
      symbol: 'فولاد', timeframe: 'D', bar: bar('2025-01-08') as never,
      adjustments: [
        { timestamp: ts('2025-01-07'), ratio: 1.5 },   // روزِ دیگر ⇒ نباید بخورد
        { timestamp: t, ratio: 2.25 },
      ],
    });
    expect(e!.adjustRatio).toBe(2.25);
  });
});

describe('قفل‌شدنِ رویداد درِ لاگ', () => {
  it('دو کلیک رویِ یک میله ⇒ یکِ ردیف (کلیدِ پایدار)، کلیکِ میلهٔ دیگر ردیفِ تازه', () => {
    const first = buildBarClick({ symbol: 'فولاد', timeframe: 'D', bar: bar('2025-01-06') as never })!;
    const second = buildBarClick({ symbol: 'فولاد', timeframe: 'D', bar: bar('2025-01-06') as never, atMs: 1 })!;
    const other = buildBarClick({ symbol: 'فولاد', timeframe: 'D', bar: bar('2025-01-07') as never })!;
    const st = useChartClickStore.getState();
    st.log(first); st.log(second); st.log(other);
    const clicks = useChartClickStore.getState().clicks;
    expect(clicks).toHaveLength(2);
    expect(clicks[0].key).toBe(other.key);
    expect(useChartClickStore.getState().clicks[0].key).toBe(other.key);
  });

  it('ردیفِ خرابِ ذخیره‌شده بارگذاری نمی‌شود و سقفِ لاگ نگه داشته می‌شود', () => {
    localStorage.setItem(
      ['fts', 'chart', 'click-log', 'v1'].join('.'),
      JSON.stringify({ clicks: [{ symbol: 'فولاد' }, null, '_x_', { timeframe: 'Q' }] }),
    );
    const mod = useChartClickStore.getState();
    expect(mod.clicks).toHaveLength(0);

    for (let i = 0; i < CLICK_LOG_CAP + 12; i++) {
      mod.log(buildBarClick({ symbol: `نماد${i}`, timeframe: 'D', bar: bar('2025-01-06') as never })!);
    }
    expect(useChartClickStore.getState().clicks.length).toBe(CLICK_LOG_CAP);
  });

  it('کلیدِ ردیف از timestampِ میله ساخته می‌شود، نه از رشتهٔ تاریخِ دیدنی', () => {
    const e = buildBarClick({ symbol: 'فولاد', timeframe: 'W', bar: bar('2025-01-06', 130) as never })!;
    expect(e.key).toBe(`فولاد|W|${e.barTs}`);
    // دو کلیک رویِ یک میله ⇒ همان کلید، پس لاگ ردیفِ دوم نمی‌سازد
    const again = buildBarClick({ symbol: 'فولاد', timeframe: 'W', bar: bar('2025-01-06', 131) as never, atMs: 2 })!;
    expect(again.key).toBe(e.key);
  });
});

describe('سیم‌کشی درِ چارت', () => {
  async function settle(ms = 40) {
    await act(async () => { await new Promise((r) => setTimeout(r, ms)); });
  }

  it('کلیکِ موتور رویِ میله ⇒ رویداد درِ لاگ و یک خط درِ نوارِ پایینی', async () => {
    overlays = [{ name: 'simpleAnnotation', groupId: 'fts_strategy_overlays',
                  points: [{ timestamp: ts('2025-01-06') }], extendData: 'جت' }];
    render(
      <KLineChartWrapper
        initialSymbol="فولاد"
        fts={{ setups: [{ date: '2025-01-06', kind: 'jet', label: 'جت', price: 130, side: 'above' }] } as never}
      />,
    );
    await settle();

    expect(clickHandlers.length).toBeGreaterThan(0);
    const cb = clickHandlers[clickHandlers.length - 1];
    await act(async () => { cb({ dataIndex: 1, data: { current: bar('2025-01-06', 130) } }); });

    const last = useChartClickStore.getState().clicks[0];
    expect(last?.symbol).toBe('فولاد');
    expect(last?.timeframe).toBe('D');
    expect(last?.kind).toBe('marker');
    expect(last?.marker).toBe('جت');
    expect(last?.engineSetups.map((s) => s.label)).toEqual(['جت']);

    const chip = screen.getByTestId('chart-click-chip');
    expect(chip.textContent).toContain('جت');

    fireEvent.click(chip);
    const rows = screen.getAllByTestId('chart-click-row');
    expect(rows).toHaveLength(1);

    fireEvent.click(screen.getByTestId('chart-click-clear'));
    expect(useChartClickStore.getState().clicks).toHaveLength(0);
    expect(screen.getByTestId('chart-click-chip').textContent).toContain('—');
  });

  it('کلیک بی‌میله (فضایِ خالی) هیچ ردیفی نمی‌سازد', async () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await settle();
    const cb = clickHandlers[clickHandlers.length - 1];
    await act(async () => { cb({ dataIndex: 9, data: {} }); });
    await act(async () => { cb(undefined); });
    expect(useChartClickStore.getState().clicks).toHaveLength(0);
  });
});
