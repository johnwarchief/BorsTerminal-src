// تست موتور Lightweight Charts (T-04 فاز ۱): نگاشت‌های خالص + رندر با ماک ماژول
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { KLineData } from '@vendor/klinecharts';
import { maLine, rsiLine, toLwCandles, toLwLine, toLwTime, toLwVolume, volumeMaLine } from '@features/technical/lib/lwChart';

const seriesStub = () => ({
  setData: vi.fn(),
  applyOptions: vi.fn(),
  priceScale: () => ({ applyOptions: vi.fn() }),
});
const paneStub = () => ({ setHeight: vi.fn(), addSeries: vi.fn(() => seriesStub()) });
const chartStub = () => ({
  addSeries: vi.fn(() => seriesStub()),
  addPane: vi.fn(() => paneStub()),
  applyOptions: vi.fn(),
  remove: vi.fn(),
  subscribeCrosshairMove: vi.fn(),
  timeScale: () => ({ fitContent: vi.fn() }),
  panes: () => [],
});

const mockTextWatermark = { applyOptions: vi.fn(), detach: vi.fn() };
const createTextWatermarkMock = vi.fn(() => mockTextWatermark);

vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => chartStub()),
  createTextWatermark: (...args: unknown[]) => createTextWatermarkMock(...args),
  CandlestickSeries: 'candlestick',
  HistogramSeries: 'histogram',
  LineSeries: 'line',
  AreaSeries: 'area',
  BarSeries: 'bar',
  BaselineSeries: 'baseline',
  ColorType: { Solid: 'solid' },
  CrosshairMode: { Normal: 0 },
  LineStyle: { Solid: 0, Dashed: 2 },
}));

const { LwChartWrapper } = await import('@features/technical/components/LwChartWrapper');
const { createChart } = await import('lightweight-charts');

const PALETTE = { up: '#10b981', down: '#f43f5e', grid: '#000', text: '#fff', background: '#0a0e17' };

function candles(n: number): KLineData[] {
  return Array.from({ length: n }, (_, i) => ({
    timestamp: Date.UTC(2025, 0, 1 + i),
    open: 100 + i,
    high: 102 + i,
    low: 99 + i,
    close: 101 + i,
    volume: 1000 + i,
  }));
}

describe('نگاشت داده به سری‌های Lightweight Charts', () => {
  it('کندل‌ها ثانیهٔ UTC و صعودی/یکتا می‌شوند', () => {
    const desc = [...candles(3)].reverse();
    const out = toLwCandles(desc);
    expect(out).toHaveLength(3);
    expect(out[0].time).toBe(toLwTime(Date.UTC(2025, 0, 1)));
    expect((out[0].time as number) < (out[2].time as number)).toBe(true);
    expect(out[0].close).toBe(101);
  });

  it('تکرار زمانی حذف می‌شود (LW حساس است)', () => {
    const dup = [candles(1)[0], candles(1)[0]];
    expect(toLwCandles(dup)).toHaveLength(1);
  });

  it('حجم با رنگ هم‌جهت کندل', () => {
    const rows: KLineData[] = [
      { timestamp: Date.UTC(2025, 0, 2), open: 10, high: 12, low: 9, close: 11, volume: 5 },
      { timestamp: Date.UTC(2025, 0, 3), open: 11, high: 12, low: 9, close: 10, volume: 6 },
    ];
    const vol = toLwVolume(rows);
    expect(vol[0].value).toBe(5);
    expect(String(vol[0].color)).toContain('16,185,129');
    expect(String(vol[1].color)).toContain('244,63,94');
  });

  it('خط عمومی مقادیر null را رد می‌کند', () => {
    const rows = candles(3);
    const out = toLwLine(rows, [null, 5, Number.NaN], '#fff');
    expect(out).toHaveLength(1);
    expect(out[0].value).toBe(5);
    expect(out[0].color).toBe('#fff');
  });

  it('MA14/MA100 و MA21 حجم و RSI14 خروجی معتبر می‌دهند', () => {
    const rows = candles(130);
    expect(maLine(rows, 14).length).toBeGreaterThan(100);
    expect(maLine(rows, 100).length).toBe(31);
    expect(volumeMaLine(rows, 21).length).toBe(110);
    const r = rsiLine(rows, 14);
    expect(r.length).toBeGreaterThan(100);
    expect(r.every((p) => p.value >= 0 && p.value <= 100)).toBe(true);
  });
});

describe('رندر LwChartWrapper', () => {
  it('چارت می‌سازد و راهنمای legend را نشان می‌دهد', async () => {
    render(<LwChartWrapper data={candles(30)} palette={PALETTE} />);
    expect(createChart).toHaveBeenCalled();
    expect(screen.getByTestId('lw-wrap')).toBeInTheDocument();
    expect(screen.getByTestId('lw-legend').textContent).toContain('نشانگر');
  });

  it('بدون خطا با دادهٔ خالی رندر می‌شود', async () => {
    render(<LwChartWrapper data={[]} palette={PALETTE} />);
    expect(screen.getByTestId('lw-host')).toBeInTheDocument();
  });

  it('تنظیمات استاندارد بوم چارت (فونت ۱۲، گرید خط‌چین، پدینگ زمان و آپشن‌های کندل) را اعمال می‌کند', async () => {
    render(<LwChartWrapper data={candles(10)} palette={PALETTE} symbol="فولاد" timeframe="D" />);
    const lastCall = vi.mocked(createChart).mock.calls[vi.mocked(createChart).mock.calls.length - 1];
    const opts = lastCall[1] as Record<string, any>;

    // ۱. محور تاریخ شمسی (fontSize: 12, minimumHeight: 28, allowBoldLabels: true)
    expect(opts.layout.fontSize).toBe(12);
    expect(opts.timeScale.minimumHeight).toBe(28);
    expect(opts.timeScale.allowBoldLabels).toBe(true);

    // ۳. خطوط گرید به‌صورت خط‌چین
    expect(opts.grid.vertLines.style).toBe(2); // LineStyle.Dashed
    expect(opts.grid.horzLines.style).toBe(2);

    // ۵. واترمارک نماد و تایم‌فریم
    const watermarkEl = screen.getByTestId('lw-watermark');
    expect(watermarkEl).toBeInTheDocument();
    expect(watermarkEl.textContent).toContain('فولاد · D');
  });

  it('پراپ‌های نماد و تایم‌فریم سفارشی در واترمارک منعکس می‌شوند', async () => {
    render(<LwChartWrapper data={[]} palette={PALETTE} symbol="خودرو" timeframe="1h" />);
    const watermarkEl = screen.getByTestId('lw-watermark');
    expect(watermarkEl.textContent).toContain('خودرو · 1h');
  });
});
