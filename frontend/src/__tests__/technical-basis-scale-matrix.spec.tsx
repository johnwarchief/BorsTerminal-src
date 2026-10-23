// Isolated basis × scale matrix: no owner login, no real browser.
// Proves the data series and the axis override for the four supported
// combinations: raw/combined × linear/logarithm.  Pixel-level behaviour in a
// real session remains LIVE_UI_UNVERIFIED (see the chart matrix §7).
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

let lastChartInstance: ReturnType<typeof chartStub> | null = null;
function chart() {
  if (!lastChartInstance) throw new Error('chart stub not created');
  return lastChartInstance;
}

const ISO = ['2026-01-08', '2026-01-09', '2026-01-12'];
const CHART_PAYLOAD = {
  status: 'success',
  candles: ISO.map((time, i) => ({ time, open: 100, high: 110, low: 90, close: 100 + i })),
  volumes: ISO.map((time) => ({ time, value: 1000 })),
  adjustEvents: [{ date: '2026-01-10', ratio: 0.5 }],
  factors: [
    { time: ISO[0], factor: 0.5 },
    { time: ISO[1], factor: 0.5 },
    { time: ISO[2], factor: 1 },
  ],
  corporateEvents: [],
  adjustCapability: {
    source: 'ledger+base-price-discontinuity', combined_available: true,
    functional_available: false, functional_reason: 'r',
    functional_blockers: [], chain_complete: true,
  },
};

const chartStub = () => {
  const instance = {
    setDataLoader: vi.fn(),
    setSymbol: vi.fn(),
    setPeriod: vi.fn(),
    setFormatter: vi.fn(),
    createIndicator: vi.fn(),
    removeIndicator: vi.fn(),
    setPaneOptions: vi.fn(),
    setStyles: vi.fn(),
    overrideYAxis: vi.fn(),
    overrideXAxis: vi.fn(),
    overrideOverlay: vi.fn(),
    removeOverlay: vi.fn(),
    createOverlay: vi.fn(() => 'ov-1'),
    resetData: vi.fn(),
    resize: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
    subscribeAction: vi.fn(),
    scrollToRealTime: vi.fn(),
    getDataList: vi.fn(() => []),
    getVisibleRange: vi.fn(() => ({ from: 0, to: 2 })),
    setScrollEnabled: vi.fn(),
    setZoomEnabled: vi.fn(),
    getOverlays: vi.fn(() => [] as Record<string, unknown>[]),
  };
  lastChartInstance = instance;
  return instance;
};

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
  registerIndicator: vi.fn(),
  getSupportedOverlays: vi.fn(() => []),
}));

vi.mock('@shared/api/http', () => ({
  http: vi.fn(async () => { throw new Error('no network in this test'); }),
}));

const { default: KLineChartWrapper } = await import(
  '@features/technical/nahayatnegar/components/KLineChartWrapper');

function loaderBars(): { close: number; volume?: number }[] {
  const calls = chart().setDataLoader.mock.calls;
  const last = calls[calls.length - 1]?.[0] as
    { getBars: (a: { callback: (bars: unknown[], e: unknown) => void }) => void } | undefined;
  if (!last?.getBars) throw new Error('data loader not registered');
  let out: { close: number; volume?: number }[] = [];
  last.getBars({ callback: (bars) => { out = bars as never; } });
  return out;
}

const lastYAxisOverride = () => {
  const c = chart().overrideYAxis.mock.calls;
  return c[c.length - 1]?.[0] as Record<string, unknown>;
};

const flush = async () => {
  for (let i = 0; i < 8; i += 1) await act(async () => { await Promise.resolve(); });
};

async function switchBasis(label: string) {
  fireEvent.click(screen.getByTitle('نوع تعدیل قیمت'));
  fireEvent.click(screen.getByText(label));
  await flush();
}

describe('price basis × axis scale — four supported combinations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastChartInstance = null;
    useFtsConfigStore.getState().setPriceScale('normal');
    useFtsConfigStore.getState().setView({
      axisDragLock: false, axisTickMargin: 3, wickGray: false,
      showWatermark: false, watermarkOpacity: 20, showBorders: true, showWicks: true,
      showXAxis: true, showYAxis: true,
    } as never);
  });

  it('combined × linear (default) — adjusted series, normal axis', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    const bars = loaderBars();
    expect(bars.map((b) => b.close)).toEqual([50, 50.5, 102]);
    expect(bars.map((b) => b.volume)).toEqual([1000, 1000, 1000]);
    expect(lastYAxisOverride().name).toBe('normal');
  });

  it('combined × logarithmic — adjusted series, log axis', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    act(() => useFtsConfigStore.getState().setPriceScale('logarithm'));
    await flush();
    const bars = loaderBars();
    expect(bars.map((b) => b.close)).toEqual([50, 50.5, 102]);
    expect(lastYAxisOverride().name).toBe('logarithm');
  });

  it('raw × linear — unadjusted series, normal axis', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    await switchBasis('خام (بدون تعدیل)');
    const bars = loaderBars();
    expect(bars.map((b) => b.close)).toEqual([100, 101, 102]);
    expect(bars.map((b) => b.volume)).toEqual([1000, 1000, 1000]);
    expect(lastYAxisOverride().name).toBe('normal');
  });

  it('raw × logarithmic — unadjusted series, log axis', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    await switchBasis('خام (بدون تعدیل)');
    act(() => useFtsConfigStore.getState().setPriceScale('logarithm'));
    await flush();
    const bars = loaderBars();
    expect(bars.map((b) => b.close)).toEqual([100, 101, 102]);
    expect(lastYAxisOverride().name).toBe('logarithm');
  });

  it('switching basis never changes volume or timestamps', async () => {
    const { http } = await import('@shared/api/http');
    (http as ReturnType<typeof vi.fn>).mockResolvedValueOnce(CHART_PAYLOAD);
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    await flush();
    const c = loaderBars().map((b) => b.volume);
    await switchBasis('خام (بدون تعدیل)');
    const r = loaderBars().map((b) => b.volume);
    expect(r).toEqual(c);
  });
});
