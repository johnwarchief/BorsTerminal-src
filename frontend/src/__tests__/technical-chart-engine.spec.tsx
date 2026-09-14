// تست موتور چارت TradingView-clone: لایه های FTS، مارکر ها، کمربند فیبو و محور جلالی
// klinecharts واقعی از vendor اسکریپت تگ می آید؛ در jsdom با ماک وفادار به قرارداد v10 (setDataLoader) جایگزین می شود.
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { KLineChart, KLineData, KLineChartsApi } from '@vendor/klinecharts';
import { KLineChartWrapper, sortAscending, type ChartDrawApi, type ChartPalette, type FtsChartLayers } from '@features/technical/components/KLineChartWrapper';
import { FtsBottomStrip } from '@features/technical/components/FtsBottomStrip';
import {
  FIB_ZONE_OVERLAY,
  JET_MARKER_OVERLAY,
  JET_LINE_OVERLAY,
  PULLBACK_MARKER_OVERLAY,
  fibZoneSpecs,
} from '@features/technical/lib/ftsOverlays';
import { epochToJalali } from '@features/technical/lib/jalaliDate';

// ---- ماک klinecharts v10 (فقط متدهایی که رپر واقعا صدا می زند) ----
type CreatedOverlay = Record<string, unknown>;
type CreatedIndicator = { name: string; calcParams?: number[]; paneId?: string };

function makeChartMock() {
  const state = {
    overlays: [] as CreatedOverlay[],
    indicators: [] as CreatedIndicator[],
    actions: new Map<string, (d: { chart: unknown }) => void>(),
    loader: null as { getBars: (req: unknown) => void } | null,
    symbol: '',
    period: '',
    formatter: null as unknown,
    barSpace: 10,
    disposed: false,
    crosshair: null as { kLineData?: KLineData } | null,
  };
  const chart: KLineChart = {
    setDataLoader: vi.fn((l) => {
      state.loader = l as unknown as { getBars: (req: unknown) => void };
    }),
    setSymbol: vi.fn((s) => {
      state.symbol = s;
    }),
    setPeriod: vi.fn((p) => {
      state.period = p;
    }),
    getDataList: vi.fn(() => []),
    getVisibleRangeDataList: vi.fn(() => []),
    getVisibleRange: vi.fn(() => ({ from: 0, to: 9, realFrom: 0, realTo: 9 })),
    resetData: vi.fn(),
    setStyles: vi.fn(),
    getStyles: vi.fn(() => ({})),
    setFormatter: vi.fn((f) => {
      state.formatter = f;
    }),
    setLocale: vi.fn(),
    setTimezone: vi.fn(),
    setThousandsSeparator: vi.fn(),
    setOffsetRightDistance: vi.fn(),
    setMaxOffsetRightDistance: vi.fn(),
    setPaneOptions: vi.fn(),
    layout: vi.fn(),
    resize: vi.fn(),
    getSize: vi.fn(() => ({ width: 800, height: 600 })),
    zoom: vi.fn(),
    zoomAtCoordinate: vi.fn(),
    zoomAtDataIndex: vi.fn(),
    zoomAtTimestamp: vi.fn(),
    setZoomEnabled: vi.fn(),
    isZoomEnabled: vi.fn(() => true),
    setScrollEnabled: vi.fn(),
    isScrollEnabled: vi.fn(() => true),
    scrollToTimestamp: vi.fn(),
    scrollToDataIndex: vi.fn(),
    scrollToRealTime: vi.fn(),
    scrollByDistance: vi.fn(),
    scroll: vi.fn(),
    setBarSpace: vi.fn((v) => {
      state.barSpace = v;
    }),
    setCrosshair: vi.fn(),
    getCrosshair: vi.fn(() => state.crosshair),
    createIndicator: vi.fn((opts) => {
      state.indicators.push(opts as CreatedIndicator);
      return 'ind-1';
    }),
    removeIndicator: vi.fn((filter) => {
      const f = (filter ?? {}) as { name?: string; paneId?: string };
      state.indicators = state.indicators.filter(
        (i) => !((f.name == null || i.name === f.name) && (f.paneId == null || i.paneId === f.paneId)),
      );
    }),
    overrideIndicator: vi.fn(),
    getIndicators: vi.fn((f) => {
      const name = (f as { name?: string })?.name;
      const hit = state.indicators.filter((i) => !name || i.name === name);
      return hit.map(() => ({ setStyles: vi.fn() }));
    }),
    createOverlay: vi.fn((o) => {
      state.overlays.push(o);
      return o;
    }),
    removeOverlay: vi.fn((f) => {
      const groupId = (f as { groupId?: string })?.groupId;
      state.overlays = state.overlays.filter((o) => o.groupId !== groupId);
    }),
    getOverlays: vi.fn(() => state.overlays),
    overrideOverlay: vi.fn(),
    subscribeAction: vi.fn((t, cb) => {
      state.actions.set(t, cb as (d: { chart: unknown }) => void);
    }),
    unsubscribeAction: vi.fn(),
    executeAction: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
  } as unknown as KLineChart;
  return { chart, state };
}

function installApi(chart: KLineChart, state: { disposed: boolean }) {
  const api: KLineChartsApi = {
    version: vi.fn(() => '10.0.3-mock'),
    init: vi.fn(() => (state.disposed ? null : chart)),
    dispose: vi.fn(() => {
      state.disposed = true;
    }),
    registerLocale: vi.fn(),
    registerOverlay: vi.fn(),
    registerIndicator: vi.fn(),
    getSupportedOverlays: vi.fn(() => []),
    utils: {},
  };
  (window as unknown as { klinecharts: KLineChartsApi }).klinecharts = api;
  return api;
}

const PALETTE: ChartPalette = {
  up: '#10b981',
  down: '#f43f5e',
  grid: 'rgba(0,0,0,0.1)',
  text: '#93a3ba',
  background: '#0a0e17',
};

function candle(ts: number, i: number): KLineData {
  const base = 100 + i * 2;
  return {
    timestamp: ts,
    open: base,
    high: base + 6,
    low: base - 4,
    close: base + 3,
    volume: 1000 + i * 10,
  };
}

function candles(n: number, startTs = Date.UTC(2025, 2, 21)): KLineData[] {
  return Array.from({ length: n }, (_, i) => candle(startTs + i * 86400_000, i));
}

let mock: ReturnType<typeof makeChartMock> | null = null;

beforeEach(() => {
  mock = makeChartMock();
  installApi(mock.chart, mock.state);
});

afterEach(() => {
  (window as unknown as { klinecharts?: KLineChartsApi }).klinecharts = undefined;
  mock = null;
});

describe('موتور چارت FTS', () => {
  it('داده از طریق setDataLoader v10 خوراک می شود نه applyNewData', async () => {
    const data = candles(5);
    render(<KLineChartWrapper data={data} palette={PALETTE} />);
    await waitFor(() => {
      expect(mock?.state.loader).not.toBeNull();
    });
    const m = mock!;
    const loader = m.state.loader!;
    let got: KLineData[] = [];
    loader.getBars({
      type: 'init',
      symbol: 'bors',
      period: 'day',
      timestamp: null,
      callback: (d: KLineData[]) => {
        got = d;
      },
    });
    expect(got).toHaveLength(5);
    expect(m.state.symbol).toBe('bors');
    expect(m.state.period).toBe('day');
  });

  it('فرمت تاریخ جلالی روی محور نصب می شود', async () => {
    render(<KLineChartWrapper data={candles(3)} palette={PALETTE} />);
    await waitFor(() => {
      expect(mock?.state.formatter).not.toBeNull();
    });
    const fmt = mock!.state.formatter as { formatDate: (p: { timestamp?: number | null }) => string };
    expect(fmt.formatDate({ timestamp: Date.UTC(2025, 2, 21) })).toBe(epochToJalali(Date.UTC(2025, 2, 21)));
    expect(fmt.formatDate({ timestamp: null })).toBe('');
  });

  it('اندیکاتور حجم در پنل خودش ساخته می شود', async () => {
    render(<KLineChartWrapper data={candles(3)} palette={PALETTE} />);
    await waitFor(() => {
      const vol = mock?.state.indicators.find((i) => i.name === 'VOL');
      expect(vol).toBeTruthy();
      expect(vol?.paneId).toBeTruthy();
    });
  });

  it('دکمه Auto-fit ریست زوم را صدا می زند', async () => {
    render(<KLineChartWrapper data={candles(3)} palette={PALETTE} />);
    const btn = await screen.findByTestId('kline-autofit');
    fireEvent.click(btn);
    expect(mock?.chart.scrollToRealTime).toHaveBeenCalled();
    expect(mock?.chart.setBarSpace).toHaveBeenCalled();
  });

  it('legend شناور با hover روی کندل: OHLCV + مقدار MA با رنگ', async () => {
    const data = candles(30);
    render(
      <KLineChartWrapper
        data={data}
        palette={PALETTE}
        layers={{
          maPeriods: [14, 52],
          jet: null,
          choch: null,
          fib: null,
          markers: [],
        }}
      />,
    );
    await waitFor(() => {
      expect(mock?.state.actions.has('onCrosshairChange')).toBe(true);
    });
    const hovered = data[20];
    mock!.state.crosshair = { kLineData: hovered };
    const cb = mock!.state.actions.get('onCrosshairChange')!;
    act(() => {
      cb({ chart: mock!.chart });
    });
    await waitFor(() => {
      expect(screen.getByTestId('kline-legend')).toBeInTheDocument();
    });
    const legend = screen.getByTestId('kline-legend');
    expect(legend.textContent).toContain(`O:${hovered.open.toFixed(0)}`);
    expect(legend.textContent).toContain(`H:${hovered.high.toFixed(0)}`);
    expect(legend.textContent).toContain(`C:${hovered.close.toFixed(0)}`);
    expect(legend.textContent).toContain('V:');
    // MA14 روی کندل ایندکس ۲۰ = میانگین ۱۴ بسته آخر
    const closes = data.map((c) => c.close);
    const expected = closes.slice(20 - 13, 21).reduce((a, b) => a + b, 0) / 14;
    expect(legend.textContent).toContain(`MA14:${expected.toFixed(0)}`);
    const ma14 = screen.getByTestId('kline-legend-ma-14');
    expect(ma14.getAttribute('style')).toContain('color');
  });

  it('خروج از کندل، legend را به حالت راهنما برمی گرداند', async () => {
    const data = candles(10);
    render(
      <KLineChartWrapper
        data={data}
        palette={PALETTE}
        layers={{ maPeriods: [14], jet: null, choch: null, fib: null, markers: [] }}
      />,
    );
    await waitFor(() => {
      expect(mock?.state.actions.has('onCrosshairChange')).toBe(true);
    });
    mock!.state.crosshair = { kLineData: data[5] };
    act(() => {
      mock!.state.actions.get('onCrosshairChange')!({ chart: mock!.chart });
    });
    await waitFor(() => {
      expect(screen.getByTestId('kline-legend').textContent).toContain('C:');
    });
    mock!.state.crosshair = null;
    act(() => {
      mock!.state.actions.get('onCrosshairChange')!({ chart: mock!.chart });
    });
    await waitFor(() => {
      expect(screen.getByTestId('kline-legend').textContent).toContain('برای دیدن OHLCV');
    });
  });

  it('بدون کتابخانه پیام تمیز می دهد', () => {
    (window as unknown as { klinecharts?: KLineChartsApi }).klinecharts = undefined;
    render(<KLineChartWrapper data={[]} palette={PALETTE} />);
    expect(screen.getByText('کتابخانه چارت بارگذاری نشد؛ صفحه را تازه کن')).toBeInTheDocument();
  });
});

describe('نرمال‌سازی ترتیب زمان', () => {
  it('ورودی نزولی قبل از feed صعودی می شود — 1403 قبل از 1404', async () => {
    // بک‌اند /api/chart نزولی است (تازه‌به‌قدیم)؛ چارت باید صعودی بگیرد
    // ۸ روز از ۲۸ اسفند ۱۴۰۳ تا ۶ فروردین ۱۴۰۴ — مرز دو سال
    const asc = candles(8, Date.UTC(2025, 2, 18));
    const desc = [...asc].reverse();
    render(<KLineChartWrapper data={desc} palette={PALETTE} />);
    await waitFor(() => {
      expect(mock?.state.loader).not.toBeNull();
    });
    const loader = mock!.state.loader!;
    let got: KLineData[] = [];
    loader.getBars({ type: 'init', symbol: 'bors', period: 'day', timestamp: null, callback: (d: KLineData[]) => (got = d) });
    expect(got.map((g) => g.timestamp)).toEqual([...got.map((g) => g.timestamp)].sort((a, b) => a - b));
    const first = epochToJalali(got[0].timestamp);
    const last = epochToJalali(got[got.length - 1].timestamp);
    // قالب YYYY/MM/DD رشته‌ای مرتب می‌شود: قدیمی‌ها چپ، تازه‌ها راست
    expect(first.localeCompare(last)).toBeLessThan(0);
  });

  it('sortAscending بی‌اثر روی داده مرتب و کامل روی داده معکوس', () => {
    const c = candles(3);
    expect(sortAscending(c).map((x) => x.timestamp)).toEqual(c.map((x) => x.timestamp));
    expect(sortAscending([...c].reverse()).map((x) => x.timestamp)).toEqual(c.map((x) => x.timestamp));
    // ورودی دست‌نخورده نمی‌ماند؟ کپی است
    expect(sortAscending(c)).not.toBe(c);
  });

  it('درخواست forward/backward دوباره داده نمی‌دهد (ضدِ واژگونیِ مکرر)', async () => {
    render(<KLineChartWrapper data={candles(4)} palette={PALETTE} />);
    await waitFor(() => {
      expect(mock?.state.loader).not.toBeNull();
    });
    const loader = mock!.state.loader!;
    for (const type of ['forward', 'backward', 'update'] as const) {
      let got: KLineData[] = [candle(1, 1)];
      loader.getBars({ type, symbol: 'bors', period: 'day', timestamp: null, callback: (d: KLineData[]) => (got = d) });
      expect(got).toHaveLength(0);
    }
  });
});

describe('لایه های FTS روی چارت', () => {
  const baseLayers: FtsChartLayers = {
    maPeriods: [14, 52, 100],
    jet: { price: 150, timestamp: Date.UTC(2025, 2, 25) },
    choch: null,
    fib: {
      zone_33_40: { lo: 120, hi: 130 },
      zone_618_70: { lo: 90, hi: 100 },
    },
    markers: [{ kind: 'jet', label: 'جت', timestamp: Date.UTC(2025, 2, 25), price: 160, dir: 'up' }],
  };

  it('مووینگ های FTS با دوره های درست روی پنل کندل ساخته می شوند', async () => {
    render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      const mas = mock?.state.indicators.filter((i) => i.name === 'MA') ?? [];
      expect(mas.length).toBeGreaterThan(0);
    });
    const ma = mock!.state.indicators.find((i) => i.name === 'MA');
    expect(ma?.calcParams).toEqual([14, 52, 100]);
    expect(ma?.paneId).toBe('candle_pane');
    expect(mock?.chart.overrideIndicator).toHaveBeenCalled();
  });

  it('تاگل خاموش MA، سری را از چارت حذف می کند', async () => {
    const { rerender } = render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      expect(mock?.state.indicators.some((i) => i.name === 'MA')).toBe(true);
    });
    rerender(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={{ ...baseLayers, maPeriods: null }} />);
    await waitFor(() => {
      expect(mock?.state.indicators.some((i) => i.name === 'MA')).toBe(false);
    });
    // دوباره روشن ⇒ سری برمیگردد
    rerender(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      expect(mock?.state.indicators.some((i) => i.name === 'MA')).toBe(true);
    });
  });

  it('کمربند فیبو از داده بک اند به اورلی تبدیل می شود (بدون بازتولید محاسبه)', async () => {
    render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      expect(mock?.state.overlays.filter((o) => o.name === FIB_ZONE_OVERLAY)).toHaveLength(2);
    });
    const fibs = mock!.state.overlays.filter((o) => o.name === FIB_ZONE_OVERLAY);
    const z1 = fibs[0];
    const pts = z1.points as { price: number }[];
    expect(pts[0].price).toBe(130); // hi
    expect(pts[1].price).toBe(120); // lo
    const z2 = fibs[1];
    const pts2 = z2.points as { price: number }[];
    expect(pts2[0].price).toBe(100);
    expect(pts2[1].price).toBe(90);
    // برچسب قیمت دارد
    expect(String((z1.extendData as { label: string }).label)).toContain('۳۳-۴۰٪');
    expect(String((z2.extendData as { label: string }).label)).toContain('۶۱.۸-۷۰٪');
  });

  it('مارکر جت روی کندل ثبت می شود', async () => {
    render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      expect(mock?.state.overlays.filter((o) => o.name === JET_MARKER_OVERLAY)).toHaveLength(1);
    });
    const m = mock!.state.overlays.find((o) => o.name === JET_MARKER_OVERLAY);
    const pt = (m!.points as { timestamp: number; price: number }[])[0];
    expect(pt.price).toBe(160);
    expect((m!.extendData as { label: string }).label).toBe('جت');
    expect((m!.extendData as { dir: string }).dir).toBe('up');
  });

  it('مارکر شکار نقطه/کف دوقلو زیر کندل ثبت می شود', async () => {
    const layers: FtsChartLayers = {
      ...baseLayers,
      markers: [
        { kind: 'pullback', label: 'شکار نقطه', timestamp: Date.UTC(2025, 2, 25), price: 95, dir: 'down' },
        { kind: 'pullback', label: 'کف دوقلو', timestamp: Date.UTC(2025, 2, 24), price: 92, dir: 'down' },
      ],
    };
    render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={layers} />);
    await waitFor(() => {
      expect(mock?.state.overlays.filter((o) => o.name === PULLBACK_MARKER_OVERLAY)).toHaveLength(2);
    });
    const m = mock!.state.overlays.filter((o) => o.name === PULLBACK_MARKER_OVERLAY);
    expect((m[0].extendData as { label: string }).label).toBe('شکار نقطه');
    expect((m[1].extendData as { label: string }).label).toBe('کف دوقلو');
    expect((m[0].extendData as { dir: string }).dir).toBe('down');
  });

  it('خط مقاومت جت با لیبل قیمت', async () => {
    render(<KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />);
    await waitFor(() => {
      expect(mock?.state.overlays.filter((o) => o.name === JET_LINE_OVERLAY)).toHaveLength(1);
    });
    const line = mock!.state.overlays.find((o) => o.name === JET_LINE_OVERLAY && o.groupId === 'fts-jet');
    expect((line!.points as { price: number }[])[0].price).toBe(150);
    expect(String((line!.extendData as { label: string }).label)).toContain('150');
  });

  it('لایه null همه اورلی های گروه را پاک می کند', async () => {
    const { rerender } = render(
      <KLineChartWrapper data={candles(30)} palette={PALETTE} layers={baseLayers} />,
    );
    await waitFor(() => {
      expect(mock?.state.overlays.filter((o) => o.name === JET_MARKER_OVERLAY)).toHaveLength(1);
    });
    rerender(
      <KLineChartWrapper
        data={candles(30)}
        palette={PALETTE}
        layers={{
          maPeriods: null,
          jet: null,
          choch: null,
          fib: null,
          markers: [],
        }}
      />,
    );
    await waitFor(() => {
      expect(mock?.state.overlays.length).toBe(0);
    });
  });

  it('بدون کمربند فیبو، اورلی فیبو ساخته نمی شود', async () => {
    render(
      <KLineChartWrapper
        data={candles(30)}
        palette={PALETTE}
        layers={{ ...baseLayers, fib: null }}
      />,
    );
    await new Promise((r) => setTimeout(r, 30));
    expect(mock?.state.overlays.filter((o) => o.name === FIB_ZONE_OVERLAY)).toHaveLength(0);
  });
});

describe('fibZoneSpecs از داده بک اند', () => {
  it('هر دو کمربند معتبر می سازد', () => {
    const specs = fibZoneSpecs({
      zone_33_40: { lo: 2739.2, hi: 2839.93, in_zone: false },
      zone_618_70: { lo: 2346.44, hi: 2447.83, in_zone: true },
    });
    expect(specs).toHaveLength(2);
    expect(specs[0].lo).toBeCloseTo(2739.2);
    expect(specs[0].hi).toBeCloseTo(2839.93);
    expect(specs[1].label).toContain('طلایی');
  });

  it('null و کمربند ناقص هیچ نمی سازد', () => {
    expect(fibZoneSpecs(null)).toHaveLength(0);
    expect(fibZoneSpecs({ zone_33_40: null, zone_618_70: { lo: null, hi: null } })).toHaveLength(0);
    expect(fibZoneSpecs({ zone_33_40: { lo: 100, hi: 90 } })).toHaveLength(0); // hi<=lo
  });

  it('اعداد نامعتبر (نامنفی/NaN) رد می شوند', () => {
    expect(
      fibZoneSpecs({ zone_33_40: { lo: Number.NaN, hi: 100 } }),
    ).toHaveLength(0);
  });
});

describe('فعالیت زوم (onVisibleRangeChange)', () => {
  it('شمارش کندل قابل مشاهده آپدیت می شود', async () => {
    render(<KLineChartWrapper data={candles(20)} palette={PALETTE} />);
    await waitFor(() => {
      expect(mock?.state.actions.has('onVisibleRangeChange')).toBe(true);
    });
    const cb = mock!.state.actions.get('onVisibleRangeChange')!;
    act(() => {
      cb({ chart: mock!.chart });
    });
    await waitFor(() => {
      expect(screen.getByTestId('kline-zoom-state').textContent).toContain('10');
    });
  });
});

describe('نوار HUD پایین چارت', () => {
  it('مقادیر MA با رنگ خودشان + سطوح و حد ضرر رندر می شود', () => {
    render(
      <FtsBottomStrip
        data={{
          mas: { 14: 2573.4, 21: 2500, 52: 2400, 100: 2300 },
          stackLabel: 'سالم صعودی',
          stackTone: 'green',
          setups: ['breakout'],
          resistance: 2820,
          support: 2300,
          stopLoss: 2573,
        }}
      />,
    );
    const strip = screen.getByTestId('fts-bottom-strip');
    expect(strip).toBeInTheDocument();
    expect(strip.textContent).toContain('MA14');
    expect(strip.textContent).toContain('MA100');
    expect(strip.textContent).toContain('سالم صعودی');
    expect(strip.textContent).toContain('breakout');
    // اعداد فارسی
    expect(screen.getByTestId('strip-ma-14').textContent).toMatch(/MA14/);
    expect(screen.getByTestId('strip-ma-14').getAttribute('style')).toContain('color');
  });

  it('سطوح غایب با خط تیره و بدون_crash رندر می شوند', () => {
    render(
      <FtsBottomStrip
        data={{
          mas: { 14: null },
          stackLabel: 'نامشخص',
          stackTone: 'gray',
          setups: [],
          resistance: null,
          support: null,
          stopLoss: null,
        }}
      />,
    );
    const strip = screen.getByTestId('fts-bottom-strip');
    expect(strip.textContent).toContain('MA14: -');
    expect(screen.queryByTestId('strip-setups')).toBeNull();
  });
});

describe('ابزارهای تریدینگ‌ویویی چارت (فاز ۳)', () => {
  it('نوع چارت روی استایل candle.type اعمال می‌شود', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} chartType="line" />);
    await waitFor(() => {
      expect(mock?.chart.setStyles).toHaveBeenCalledWith({ candle: { type: 'line' } });
    });
  });

  it('میانگین متحرک حجم (۲۱) روی پنل حجم ساخته می‌شود', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} showVolMa />);
    await waitFor(() => {
      const ma = mock?.state.indicators.find((i) => i.name === 'MA' && i.paneId === 'vol_pane');
      expect(ma).toBeTruthy();
      expect(ma?.calcParams).toEqual([21]);
    });
  });

  it('RSI(14) در پنل جدا ساخته می‌شود', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} showRsi />);
    await waitFor(() => {
      const rsi = mock?.state.indicators.find((i) => i.name === 'RSI');
      expect(rsi).toBeTruthy();
      expect(rsi?.paneId).toBe('rsi_pane');
    });
  });

  it('دکمه اسکرین‌شات تصویر چارت را می‌گیرد', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} />);
    const btn = await screen.findByTestId('kline-screenshot');
    fireEvent.click(btn);
    expect(mock?.chart.getConvertPictureUrl).toHaveBeenCalled();
  });

  it('دکمه تمام‌صفحه وجود دارد', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} />);
    expect(await screen.findByTestId('kline-fullscreen')).toBeInTheDocument();
  });

  it('مقیاس قیمت روی yAxis.type اعمال می‌شود', async () => {
    render(<KLineChartWrapper data={candles(6)} palette={PALETTE} priceScale="logarithm" />);
    await waitFor(() => {
      expect(mock?.chart.setStyles).toHaveBeenCalledWith({ yAxis: { type: 'logarithm' } });
    });
  });

  it('onApi: startDraw اورلی می‌سازد و clear پاک می‌کند', async () => {
    let api: ChartDrawApi | null = null;
    render(
      <KLineChartWrapper
        data={candles(6)}
        palette={PALETTE}
        onApi={(a) => {
          api = a;
        }}
      />,
    );
    await waitFor(() => {
      expect(api).not.toBeNull();
    });
    (api as unknown as ChartDrawApi).startDraw('straightLine');
    expect(mock?.chart.createOverlay).toHaveBeenCalledWith({ name: 'straightLine', groupId: 'fts-draw' });
    (api as unknown as ChartDrawApi).clearDrawings();
    expect(mock?.chart.removeOverlay).toHaveBeenCalledWith({ groupId: 'fts-draw' });
  });
});
