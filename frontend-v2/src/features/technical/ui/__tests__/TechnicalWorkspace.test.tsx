/**
 * frontend-v2/src/features/technical/ui/__tests__/TechnicalWorkspace.test.tsx
 *
 * آزمون‌های یکپارچگی میزکار جامع تکنیکال و کوانت (TechnicalWorkspace):
 * ۱. رندر نوار ابزار رسم در سمت راست و سایدبار لبه آماری در سمت چپ
 * ۲. رندر نوار کنترل‌های پیش‌بینی هوش مصنوعی در بالای چارت
 * ۳. رندر کانتینر کانواسی چارت KLineCharts
 * ۴. باز و بسته شدن سایدبار لبه آماری با دکمه اختصاصی
 * ۵. همگام‌سازی نماد فعال با استور مرکزی technicalStore
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TechnicalWorkspace } from '../TechnicalWorkspace';
import { useTechnicalStore } from '../../model/technicalStore';

// موک کردن موتور klinecharts برای محیط jsdom
vi.mock('klinecharts', () => ({
  init: () => ({
    setStyles: vi.fn(),
    setDataLoader: vi.fn(),
    setSymbol: vi.fn(),
    setPeriod: vi.fn(),
    resetData: vi.fn(),
    resize: vi.fn(),
    createOverlay: vi.fn(),
    removeOverlay: vi.fn(),
  }),
  dispose: vi.fn(),
  registerOverlay: vi.fn(),
}));

// موک کردن هوک useChart
vi.mock('@features/chart/api/useChart', async (original) => {
  const mod = await original<typeof import('@features/chart/api/useChart')>();
  return {
    ...mod,
    useChart: vi.fn(() => ({
      data: { status: 'success', candles: [] },
      isLoading: false,
      isError: false,
    })),
  };
});

describe('TechnicalWorkspace', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders drawing toolbar and candle edge sidebar', () => {
    render(<TechnicalWorkspace symbol="FOOLAD" />);

    expect(screen.getByTestId('drawing-toolbar')).toBeDefined();
    fireEvent.click(screen.getByTitle('باز کردن سایدبار لبه آماری'));
    expect(screen.getByTestId('candle-edge-card')).toBeDefined();
  });

  it('renders forecast controls and kline chart container', () => {
    render(<TechnicalWorkspace symbol="FOOLAD" />);

    expect(screen.getByTestId('forecast-controls')).toBeDefined();
    expect(screen.getByTestId('kline-chart-container')).toBeDefined();
    expect(screen.getByTestId('technical-workspace')).toBeDefined();
  });

  it('toggles the event feed body and its panels on button click', () => {
    render(<TechnicalWorkspace symbol="FOOLAD" />);

    // فید پیش‌فرض بسته است؛ اول بازش می‌کنیم.
    fireEvent.click(screen.getByTitle('باز کردن سایدبار لبه آماری'));
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);
    // پنل لبه آماری در بدنهٔ فید سوار می‌ماند (تب فعال پیش‌فرض رویدادهاست).
    expect(screen.getByTestId('candle-edge-card')).toBeDefined();

    // بستن فید، بدنه و پنل‌ها را از DOM خارج می‌کند.
    const toggleBtn = screen.getByTestId('workspace-feed-toggle');
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(true);
    expect(screen.queryByTestId('candle-edge-card')).toBeNull();

    // باز کردن مجدد فید
    fireEvent.click(screen.getByTestId('workspace-feed-toggle'));
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);
    expect(screen.getByTestId('candle-edge-card')).toBeDefined();
  });

  it('syncs symbol prop to technicalStore selectedSymbol', () => {
    render(<TechnicalWorkspace symbol="SHASTA" />);
    expect(useTechnicalStore.getState().selectedSymbol).toBe('SHASTA');
  });
});
