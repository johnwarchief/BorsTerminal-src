// تست چارت پورت‌شدهٔ NahayatNegar (T-14): mount + استفاده از APIهای klinecharts v10
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { KLineData } from 'klinecharts';

const chartStub = () => ({
  setDataLoader: vi.fn(),
  setSymbol: vi.fn(),
  setPeriod: vi.fn(),
  setFormatter: vi.fn(),
  createIndicator: vi.fn(),
  removeIndicator: vi.fn(),
  setPaneOptions: vi.fn(),
  setStyles: vi.fn(),
  resetData: vi.fn(),
  resize: vi.fn(),
  createOverlay: vi.fn(() => 'ov-1'),
  removeOverlay: vi.fn(),
  overrideOverlay: vi.fn(),
  subscribeAction: vi.fn(),
  scrollToRealTime: vi.fn(),
  getDataList: vi.fn(() => []),
});

vi.mock('klinecharts', () => ({
  init: vi.fn(() => chartStub()),
  dispose: vi.fn(),
}));

const { KLineChartNahayatNegar } = await import('@features/technical/nahayatnegar/components/KLineChartWrapper');
const { init } = await import('klinecharts');

const CANDLE = { timestamp: Date.UTC(2026, 0, 1), open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 } as unknown as KLineData;

describe('چارت پورت‌شدهٔ NahayatNegar روی klinecharts v10', () => {
  it('mount می‌شود و init صدا زده می‌شود', () => {
    render(<KLineChartNahayatNegar initialSymbol="فولاد" initialName="فولاد مبارکه" data={[CANDLE]} />);
    expect(init).toHaveBeenCalled();
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
    expect(screen.getAllByText(/فولاد/).length).toBeGreaterThan(0);
  });

  it('بدون داده و بدون corporateActions هم بدون خطا رندر می‌شود', () => {
    render(<KLineChartNahayatNegar />);
    expect(document.querySelector('.nahayat-negar-container')).toBeTruthy();
  });
});
