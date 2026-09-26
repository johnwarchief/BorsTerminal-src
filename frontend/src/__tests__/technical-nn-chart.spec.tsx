// تست چارت پورت‌شدهٔ NahayatNegar (T-17): mount + APIهای klinecharts v10
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

type OverlayCfg = {
  name?: string;
  groupId?: string;
  points?: unknown[];
  lock?: boolean;
  onDrawStart?: () => void;
  onDrawEnd?: () => void;
  onPressedMoveStart?: () => void;
  onPressedMoveEnd?: () => void;
  [key: string]: unknown;
};

let lastChartInstance: ReturnType<typeof chartStub> | null = null;

/** نمونهٔ چارتِ ساخته‌شده؛ نبودنش یعنی تست بی‌خبر از چارت رد شده است */
function chart() {
  if (!lastChartInstance) throw new Error('chart stub هنوز ساخته نشده');
  return lastChartInstance;
}

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
    overrideOverlay: vi.fn(),
    removeOverlay: vi.fn(),
    createOverlay: vi.fn<(cfg: OverlayCfg) => string>(() => 'ov-1'),
    resetData: vi.fn(),
    resize: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
    subscribeAction: vi.fn(),
    scrollToRealTime: vi.fn(),
    getDataList: vi.fn(() => []),
    setScrollEnabled: vi.fn(),
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

const { KLineChartWrapper } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
const { init } = await import('klinecharts');

describe('چارت پورت‌شدهٔ NahayatNegar روی klinecharts v10', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lastChartInstance = null;
    useFtsConfigStore.getState().setPriceScale('normal');
    useFtsConfigStore.getState().setView({
      candleUp: '#089981',
      candleDown: '#f23645',
      borderUp: '#089981',
      borderDown: '#f23645',
      wickUp: '#089981',
      wickDown: '#f23645',
      showBorders: true,
      showWicks: true,
    });
  });

  it('mount می‌شود و init صدا زده می‌شود', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" initialName="فولاد مبارکه" />);
    expect(init).toHaveBeenCalled();
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
  });

  it('بدون پراپ هم بدون خطا رندر می‌شود', () => {
    render(<KLineChartWrapper />);
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
  });

  it('رنگ‌های کندل و بوردر همواره مقادیر معتبر و دارای کنتراست هستند (عدم تولید undefined یا شفافیت)', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    expect(chart().setStyles).toHaveBeenCalled();

    const setStylesCalls = chart().setStyles.mock.calls;
    const lastStyleCall = setStylesCalls[setStylesCalls.length - 1][0];
    const candle = lastStyleCall?.candle;

    expect(candle).toBeDefined();
    expect(candle.bar.upColor).toBe('#089981');
    expect(candle.bar.downColor).toBe('#f23645');
    expect(candle.bar.upBorderColor).toBe('#089981');
    expect(candle.bar.downBorderColor).toBe('#f23645');
    expect(candle.bar.upWickColor).toBe('#089981');
    expect(candle.bar.downWickColor).toBe('#f23645');
    expect(candle.type).toBe('candle_solid');
  });

  it('در صورت نال بودن مقادیر در استور، فالبک‌های پیش‌فرض امن (#089981 و #f23645) فعال می‌شوند', () => {
    act(() => {
      useFtsConfigStore.getState().setView({
        candleUp: null,
        candleDown: null,
        borderUp: null,
        borderDown: null,
        wickUp: null,
        wickDown: null,
      });
    });

    render(<KLineChartWrapper initialSymbol="فولاد" />);
    const setStylesCalls = chart().setStyles.mock.calls;
    const lastStyleCall = setStylesCalls[setStylesCalls.length - 1][0];
    const candle = lastStyleCall?.candle;

    expect(candle.bar.upColor).toBe('#089981');
    expect(candle.bar.downColor).toBe('#f23645');
    expect(candle.bar.upBorderColor).toBe('#089981');
    expect(candle.bar.downBorderColor).toBe('#f23645');
    expect(candle.bar.upWickColor).toBe('#089981');
    expect(candle.bar.downWickColor).toBe('#f23645');
  });

  it('تغییر مقیاس با دکمه لگاریتمی در نوار پایین name: logarithm را به overrideYAxis ارسال می‌کند', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    const logBtn = screen.getByTitle('مقیاس لگاریتمی');
    expect(logBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(logBtn);
    });

    expect(chart().overrideYAxis).toHaveBeenCalledWith(
      expect.objectContaining({
        paneId: 'candle_pane',
        name: 'logarithm',
      })
    );
    expect(useFtsConfigStore.getState().priceScale).toBe('logarithm');

    // کلیک مجدد به حالت نرمال برمی‌گرداند
    act(() => {
      fireEvent.click(logBtn);
    });

    expect(chart().overrideYAxis).toHaveBeenCalledWith(
      expect.objectContaining({
        paneId: 'candle_pane',
        name: 'normal',
      })
    );
    expect(useFtsConfigStore.getState().priceScale).toBe('normal');
  });

  it('تنظیمات تم شامل separator به اندازه 1 و xAxis با ارتفاع 32px است', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    const setStylesCalls = chart().setStyles.mock.calls;
    const lastCall = setStylesCalls[setStylesCalls.length - 1][0];
    expect(lastCall?.separator?.size).toBe(1);
    expect(lastCall?.xAxis?.size).toBe(32);
    expect(lastCall?.separator?.fill).toBe(true);
  });

  it('نوار پایینی شامل بازه‌های زمانی و بج تایم‌زون تهران است و دکمه تکراری ندارد', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    expect(screen.getByText(/تهران \(UTC\+3:30\)/)).toBeInTheDocument();
    expect(screen.getByText('بازه زمانی:')).toBeInTheDocument();
    expect(screen.getByText('1D')).toBeInTheDocument();
    expect(screen.getByText('1Y')).toBeInTheDocument();
    expect(screen.getByText('All')).toBeInTheDocument();
    expect(document.querySelector('.nn-bottom-bar')).toBeInTheDocument();
  });

  it('انتخاب ابزار خط‌کش (ruler) اورلی ftsMeasure را در گروه fts-draw ایجاد کرده و کنترل اسکرول را متصل می‌کند', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    const rulerBtn = screen.getByTitle('خط‌کش اندازه‌گیری');
    expect(rulerBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(rulerBtn);
    });

    expect(chart().createOverlay).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'ftsMeasure',
        groupId: 'fts-draw',
        onDrawStart: expect.any(Function),
        onDrawEnd: expect.any(Function),
        onPressedMoveStart: expect.any(Function),
        onPressedMoveEnd: expect.any(Function),
      })
    );

    // بررسی هوک‌های اسکرول
    const overlayCall = chart().createOverlay.mock.calls.find(
      (c) => c[0].name === 'ftsMeasure'
    );
    if (!overlayCall) throw new Error('پیکربندِ ftsMeasure هرگز به چارت نرسید');
    const opts = overlayCall[0];

    opts.onDrawStart?.();
    expect(chart().setScrollEnabled).toHaveBeenCalledWith(false);

    opts.onDrawEnd?.();
    expect(chart().setScrollEnabled).toHaveBeenCalledWith(true);

    opts.onPressedMoveStart?.();
    expect(chart().setScrollEnabled).toHaveBeenCalledWith(false);

    opts.onPressedMoveEnd?.();
    expect(chart().setScrollEnabled).toHaveBeenCalledWith(true);
  });

  it('تغییر تایم‌فریم متد flushDrawings را فراخوانی کرده و ترسیم‌های جاری را در localStorage ذخیره می‌کند', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);

    chart().getOverlays.mockReturnValue([
      {
        id: 'overlay_test_1',
        name: 'segment',
        groupId: 'fts-draw',
        points: [{ timestamp: 1600000000000, value: 5000 }],
        lock: false,
      },
    ]);

    const weekBtn = screen.getByRole('button', { name: 'هفتگی' });

    act(() => {
      fireEvent.click(weekBtn);
    });

    const saved = localStorage.getItem('fts.drawings.v1.فولاد');
    expect(saved).toBeTruthy();
    const parsed = JSON.parse(saved || '[]');
    expect(parsed).toHaveLength(1);
    expect(parsed[0].name).toBe('segment');
  });

  // ── «تعدیل عملکردی» (نمایِ بازدهی) ─────────────────────────────────────
  it('حالتِ «تعدیل عملکردی» در منو فعال است و با انتخاب، دقتِ محور به دو رقم می‌رود', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { fireEvent.click(screen.getByTitle('نوع تعدیل قیمت')); });

    const chip = screen.getByText('تعدیل عملکردی').closest('.nn-dropdown-item') as HTMLElement;
    expect(chip.className).not.toContain('nn-disabled');
    act(() => { fireEvent.click(chip); });

    const calls = chart().setSymbol.mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    expect(calls[calls.length - 1][0].pricePrecision).toBe(2);
  });

  it('در حالتِ عملکردی محور percentage روی دادهٔ درصدی نمی‌نشیند (درصدِ درصد = ۰٫۰۱٪)', () => {
    act(() => { useFtsConfigStore.getState().setPriceScale('percentage'); });
    render(<KLineChartWrapper initialSymbol="فولاد" />);
    act(() => { fireEvent.click(screen.getByTitle('نوع تعدیل قیمت')); });
    act(() => { fireEvent.click(screen.getByText('تعدیل عملکردی').closest('.nn-dropdown-item') as HTMLElement); });

    const y = chart().overrideYAxis.mock.calls;
    expect(y[y.length - 1][0].name).toBe('normal');

    act(() => { fireEvent.click(screen.getByTitle('نوع تعدیل قیمت')); });
    act(() => { fireEvent.click(screen.getByText('بدون تعدیل').closest('.nn-dropdown-item') as HTMLElement); });
    const y2 = chart().overrideYAxis.mock.calls;
    expect(y2[y2.length - 1][0].name).toBe('percentage');
    act(() => { useFtsConfigStore.getState().setPriceScale('normal'); });
  });
});

