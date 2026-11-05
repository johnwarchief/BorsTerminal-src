/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
 *
 * آزمون‌های پوستهٔ تازهٔ میزکار تکنیکال (TradingView-style shell):
 * ۱. رندر نوار بالا، نوار فعالیت، چارت، ریل بازرس و فید رویدادها
 * ۲. سوییچ پنل فید از نوار فعالیت و ثبت آن در technicalStore
 *
 * بچه‌های سنگین (چارت، نوار رسم، کنترل‌های پیش‌بینی)، کوئری‌ها و هوک تابلو
 * همان‌طور که در آزمون‌های موجود میزکار موک می‌شوند.
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TechnicalWorkspace } from '../../TechnicalWorkspace';
import { useTechnicalStore } from '../../../model/technicalStore';

// موک کردن بچه‌های سنگین میزکار
vi.mock('../../KLineChartWrapper', () => ({
  KLineChartWrapper: () => <div data-testid="kline-chart-wrapper" />,
}));

vi.mock('../../DrawingToolbar', () => ({
  DrawingToolbar: () => <div data-testid="drawing-toolbar" />,
}));

vi.mock('../../ForecastControls', () => ({
  ForecastControls: () => <div data-testid="forecast-controls" />,
}));

// موک کردن کوئری‌های تحلیلی بک‌اند
vi.mock('@features/technical/api/useTechnicalQueries', () => ({
  useForecastQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useCandleEdgeQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useIndicatorsQuery: vi.fn(() => ({ data: null, isLoading: false })),
}));

// موک کردن هوک تابلو بازار (مصرف‌کنندهٔ آن کشوی موقت فید است)
vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: {
      data: [
        {
          symbol: 'فولاد',
          name: 'فولاد مبارکه',
          sector_name: 'فلزات',
          p_last: 5850,
          percent_last: 2.5,
          q_tot_cap: 900_000_000_000,
          tvol: 150_000_000,
        },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}));

function renderShell() {
  return render(<TechnicalWorkspace symbol="FOOLAD" />);
}

describe('WorkspaceShell', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders topbar, activity bar, chart stage, rail and feed', () => {
    renderShell();
    expect(screen.getByTestId('workspace-topbar')).toBeTruthy();
    expect(screen.getByTestId('workspace-activity')).toBeTruthy();
    expect(screen.getByTestId('kline-chart-wrapper')).toBeTruthy();
    expect(screen.getByTestId('workspace-rail')).toBeTruthy();
    expect(screen.getByTestId('workspace-feed')).toBeTruthy();
  });

  it('switches the feed panel from the activity bar', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('activity-panel-top50'));
    expect(useTechnicalStore.getState().activePanel).toBe('top50');
  });
});
