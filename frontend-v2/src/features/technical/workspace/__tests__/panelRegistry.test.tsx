/**
 * frontend-v2/src/features/technical/workspace/__tests__/panelRegistry.test.tsx
 *
 * قرارداد پنل‌های میزکار ۲.۰: هر پنل یک میزبان پایدار با
 * `data-testid="panel-<kind>"` دارد و رجیستری بدون ویرایش کامپوننت‌های
 * موجود (چارت، بازرس، فید) آن‌ها را دوباره سوار می‌کند.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspacePanelHost } from '../WorkspacePanelHost';
import { PANEL_REGISTRY } from '../panelRegistry';
import { useTechnicalStore } from '../../model/technicalStore';

vi.mock('../../ui/KLineChartWrapper', () => ({
  KLineChartWrapper: () => <div data-testid="kline-chart-wrapper" />,
}));

vi.mock('../../ui/DrawingToolbar', () => ({
  DrawingToolbar: () => <div data-testid="drawing-toolbar" />,
}));

vi.mock('../../ui/ForecastControls', () => ({
  ForecastControls: () => <div data-testid="forecast-controls" />,
}));

vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: {
      data: [
        { symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات', p_last: 5850, percent_last: 2.5 },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}));

beforeEach(() => {
  localStorage.clear();
  useTechnicalStore.getState().reset();
});

afterEach(cleanup);

describe('panel registry', () => {
  it('registers every technical panel kind', () => {
    for (const kind of ['chart', 'inspector', 'feed', 'scanner', 'fundamental', 'indicators'] as const) {
      expect(PANEL_REGISTRY[kind], kind).toBeTruthy();
    }
  });

  it('hosts inspector, feed and scanner with stable test ids', () => {
    render(
      <>
        <WorkspacePanelHost kind="inspector" />
        <WorkspacePanelHost kind="feed" />
        <WorkspacePanelHost kind="scanner" />
      </>,
    );

    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
    expect(screen.getByTestId('panel-feed')).toBeTruthy();
    expect(screen.getByTestId('panel-scanner')).toBeTruthy();
    expect(screen.getByTestId('workspace-rail')).toBeTruthy();
    expect(screen.getByTestId('workspace-feed')).toBeTruthy();
    expect(screen.getByTestId('top50-panel')).toBeTruthy();
  });

  it('puts the untouched KLineChartWrapper inside the chart pane', () => {
    render(<WorkspacePanelHost kind="chart" />);
    const host = screen.getByTestId('panel-chart');
    expect(host.querySelector('[data-testid="kline-chart-wrapper"]')).toBeTruthy();
  });
});
