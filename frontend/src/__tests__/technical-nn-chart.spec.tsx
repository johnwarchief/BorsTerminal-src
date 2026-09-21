// تست چارت پورت‌شدهٔ NahayatNegar (T-17): mount + APIهای klinecharts v10
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFtsConfigStore } from '@features/technical/stores/ftsConfigStore';

let lastChartInstance: any = null;

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
    createOverlay: vi.fn(() => 'ov-1'),
    resetData: vi.fn(),
    resize: vi.fn(),
    getConvertPictureUrl: vi.fn(() => ''),
    subscribeAction: vi.fn(),
    scrollToRealTime: vi.fn(),
    getDataList: vi.fn(() => []),
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
    expect(lastChartInstance?.setStyles).toHaveBeenCalled();

    const setStylesCalls = lastChartInstance.setStyles.mock.calls;
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
    const setStylesCalls = lastChartInstance.setStyles.mock.calls;
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

    expect(lastChartInstance?.overrideYAxis).toHaveBeenCalledWith(
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

    expect(lastChartInstance?.overrideYAxis).toHaveBeenCalledWith(
      expect.objectContaining({
        paneId: 'candle_pane',
        name: 'normal',
      })
    );
    expect(useFtsConfigStore.getState().priceScale).toBe('normal');
  });
});
