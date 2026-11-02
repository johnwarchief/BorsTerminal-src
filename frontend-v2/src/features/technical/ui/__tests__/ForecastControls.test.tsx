/**
 * frontend-v2/src/features/technical/ui/__tests__/ForecastControls.test.tsx
 *
 * آزمون‌های واحد و یکپارچگی نوار کنترل‌های پیش‌بینی (ForecastControls):
 * ۱. رندر عنوان مدل هوش مصنوعی و کلید روشن/خاموش کان پیش‌بینی
 * ۲. تغییر افق زمانی پیش‌بینی با دکمه‌های سریع ۳، ۶ و ۱۲ کندل
 * ۳. نمایش بج «احتمال صعود» و «تشدید نوسان» با فرمت فارسی
 * ۴. نمایش اخطار نقدشوندگی زمانی که ارزش معاملات کمتر از ۵ میلیارد تومان باشد
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ForecastControls } from '../ForecastControls';
import { useTechnicalStore } from '../../model/technicalStore';
import type { PredictionData } from '../../model/types';

const MOCK_PREDICTION_LIQUID: PredictionData = {
  symbol: 'FOOLAD',
  generatedAt: 1730000000,
  horizon: 12,
  isLiquid: true,
  forecastSteps: [
    { stepIndex: 1, timestamp: 1730000000, p10: 100, p50: 105, p90: 110 },
  ],
  upsideProbability: 0.62,
  volatilityAmplification: 1.25,
};

const MOCK_PREDICTION_ILLIQUID: PredictionData = {
  symbol: 'KHAZAR',
  generatedAt: 1730000000,
  horizon: 6,
  isLiquid: false,
  liquidityNote: 'ارزش معاملات روزانه کمتر از ۵ میلیارد تومان',
  forecastSteps: [],
  upsideProbability: 0.45,
  volatilityAmplification: 0.9,
};

describe('ForecastControls', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders forecast controls container with AI title and cone toggle', () => {
    render(<ForecastControls />);

    expect(screen.getByTestId('forecast-controls')).toBeDefined();
    expect(screen.getByText('پیش‌بینی هوش مصنوعی')).toBeDefined();
    expect(screen.getByText('کان پیش‌بینی')).toBeDefined();
  });

  it('toggles prediction cone in technicalStore on button click', () => {
    render(<ForecastControls />);

    const coneToggle = screen.getByRole('switch');
    expect(useTechnicalStore.getState().showPredictionCone).toBe(false);

    fireEvent.click(coneToggle);
    expect(useTechnicalStore.getState().showPredictionCone).toBe(true);

    fireEvent.click(coneToggle);
    expect(useTechnicalStore.getState().showPredictionCone).toBe(false);
  });

  it('changes forecast horizon on quick button click and triggers callback', () => {
    const handleHorizonChange = vi.fn();
    render(<ForecastControls onHorizonChange={handleHorizonChange} />);

    const sixCandlesBtn = screen.getByText('۶ کندل');
    fireEvent.click(sixCandlesBtn);

    expect(useTechnicalStore.getState().forecastHorizon).toBe(6);
    expect(handleHorizonChange).toHaveBeenCalledWith(6);

    const threeCandlesBtn = screen.getByText('۳ کندل');
    fireEvent.click(threeCandlesBtn);

    expect(useTechnicalStore.getState().forecastHorizon).toBe(3);
    expect(handleHorizonChange).toHaveBeenCalledWith(3);
  });

  it('displays upside probability and volatility amplification badges when liquid', () => {
    useTechnicalStore.getState().setPredictionData(MOCK_PREDICTION_LIQUID);
    render(<ForecastControls />);

    expect(screen.getByText('احتمال صعود:')).toBeDefined();
    expect(screen.getByText('۶۲٪')).toBeDefined();

    expect(screen.getByText('تشدید نوسان:')).toBeDefined();
    expect(screen.getByText(/۱[٫\.]۲۵/)).toBeDefined();
  });

  it('displays prominent liquidity warning when symbol is illiquid (< 5 Billion Tomans)', () => {
    useTechnicalStore.getState().setPredictionData(MOCK_PREDICTION_ILLIQUID);
    render(<ForecastControls />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeDefined();
    expect(screen.getByText(/هشدار نقدشوندگی: ارزش معاملات روزانه زیر ۵ میلیارد تومان است/)).toBeDefined();
  });

  it('allows switching between Kronos models (mini, small, base)', () => {
    render(<ForecastControls />);

    expect(useTechnicalStore.getState().forecastModel).toBe('small');

    const miniBtn = screen.getByText('مینی (۴M)');
    fireEvent.click(miniBtn);
    expect(useTechnicalStore.getState().forecastModel).toBe('mini');

    const baseBtn = screen.getByText('پایه (۱۰۲M)');
    fireEvent.click(baseBtn);
    expect(useTechnicalStore.getState().forecastModel).toBe('base');
  });

  it('allows changing Rahavard 365 adjustment mode and toggling corporate events', () => {
    render(<ForecastControls />);

    expect(useTechnicalStore.getState().adjustmentMode).toBe(3);
    const select = screen.getByTestId('adjustment-mode-select');
    fireEvent.change(select, { target: { value: '1' } });
    expect(useTechnicalStore.getState().adjustmentMode).toBe(1);

    fireEvent.change(select, { target: { value: '0' } });
    expect(useTechnicalStore.getState().adjustmentMode).toBe(0);

    const eventsBtn = screen.getByRole('button', { name: /رویدادها/ });
    expect(useTechnicalStore.getState().showCorporateEvents).toBe(true);
    fireEvent.click(eventsBtn);
    expect(useTechnicalStore.getState().showCorporateEvents).toBe(false);
  });

  it('renders timeframe selector and switches timeframes (1D, 1W, 1M)', () => {
    render(<ForecastControls />);

    expect(screen.getByTestId('timeframe-selector')).toBeDefined();
    const btn1D = screen.getByTestId('timeframe-btn-1D');
    const btn1W = screen.getByTestId('timeframe-btn-1W');
    const btn1M = screen.getByTestId('timeframe-btn-1M');

    expect(btn1D.textContent).toBe('روزانه');
    expect(btn1W.textContent).toBe('هفتگی');
    expect(btn1M.textContent).toBe('ماهانه');

    expect(useTechnicalStore.getState().timeframe).toBe('1D');

    fireEvent.click(btn1W);
    expect(useTechnicalStore.getState().timeframe).toBe('1W');

    fireEvent.click(btn1M);
    expect(useTechnicalStore.getState().timeframe).toBe('1M');

    fireEvent.click(btn1D);
    expect(useTechnicalStore.getState().timeframe).toBe('1D');
  });

  it('renders indicator dropdown button and toggles popover with search and indicators', () => {
    render(<ForecastControls />);

    const dropdownBtn = screen.getByTestId('indicator-dropdown-btn');
    expect(dropdownBtn).toBeDefined();
    expect(screen.getByText('اندیکاتورها')).toBeDefined();

    // باز کردن منو
    fireEvent.click(dropdownBtn);
    expect(screen.getByTestId('indicator-dropdown-menu')).toBeDefined();

    // فیلد جستجو
    const searchInput = screen.getByTestId('indicator-search-input') as HTMLInputElement;
    expect(searchInput).toBeDefined();

    // بررسی حضور اندیکاتورهای تلگرام
    expect(screen.getByTestId('indicator-option-DoubleTap3D')).toBeDefined();
    expect(screen.getByTestId('indicator-option-SuperTrendPullback')).toBeDefined();

    // کلیک روی یک اندیکاتور جهت فعال‌سازی
    const doubleTapItem = screen.getByTestId('indicator-option-DoubleTap3D');
    fireEvent.click(doubleTapItem);
    expect(useTechnicalStore.getState().activeUserIndicators).toContain('DoubleTap3D');

    // کلیک مجدد جهت غیرفعال‌سازی
    fireEvent.click(doubleTapItem);
    expect(useTechnicalStore.getState().activeUserIndicators).not.toContain('DoubleTap3D');
  });

  it('filters indicators via search input and clears all active indicators', () => {
    render(<ForecastControls />);

    // فعال کردن اولیه دو اندیکاتور در استور
    useTechnicalStore.getState().toggleUserIndicator('DoubleTap3D');
    useTechnicalStore.getState().toggleUserIndicator('MultiModeChannel');
    expect(useTechnicalStore.getState().activeUserIndicators.length).toBe(2);

    const dropdownBtn = screen.getByTestId('indicator-dropdown-btn');
    fireEvent.click(dropdownBtn);

    // جستجوی عبارت خاص (سوپرترند)
    const searchInput = screen.getByTestId('indicator-search-input');
    fireEvent.change(searchInput, { target: { value: 'سوپرترند' } });

    expect(screen.getByTestId('indicator-option-SuperTrendPullback')).toBeDefined();
    expect(screen.queryByTestId('indicator-option-DoubleTap3D')).toBeNull();

    // تست دکمه خاموش‌کردن همه
    const clearBtn = screen.getByTestId('clear-all-indicators-btn');
    fireEvent.click(clearBtn);
    expect(useTechnicalStore.getState().activeUserIndicators.length).toBe(0);
  });
});

