// تست چارت پورت‌شدهٔ NahayatNegar (T-17): mount + APIهای klinecharts v10
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const chartStub = () => ({
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
});

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
  it('mount می‌شود و init صدا زده می‌شود', () => {
    render(<KLineChartWrapper initialSymbol="فولاد" initialName="فولاد مبارکه" />);
    expect(init).toHaveBeenCalled();
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
  });

  it('بدون پراپ هم بدون خطا رندر می‌شود', () => {
    render(<KLineChartWrapper />);
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
  });
});
