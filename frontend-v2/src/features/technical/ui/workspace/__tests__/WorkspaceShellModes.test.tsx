/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShellModes.test.tsx
 *
 * آزمون مودهای میزکار ۲.۰: سوییچ تحلیل/اسکن/پژوهش، پنل‌های هر مود و
 * پالت دستور با Ctrl+K. بچه‌های سنگین و کوئری‌ها مثل بقیهٔ آزمون‌های
 * میزکار موک می‌شوند.
 */

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TechnicalWorkspace } from '../../TechnicalWorkspace';
import { useTechnicalStore } from '../../../model/technicalStore';
import { useTechnicalWorkspaceStore } from '../../../workspace/technicalWorkspaceStore';

vi.mock('../../KLineChartWrapper', () => ({
  KLineChartWrapper: () => <div data-testid="kline-chart-wrapper" />,
}));

vi.mock('../../DrawingToolbar', () => ({
  DrawingToolbar: () => <div data-testid="drawing-toolbar" />,
}));

vi.mock('../../ForecastControls', () => ({
  ForecastControls: () => <div data-testid="forecast-controls" />,
}));

vi.mock('@features/technical/api/useTechnicalQueries', () => ({
  useForecastQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useCandleEdgeQuery: vi.fn(() => ({ data: null, isLoading: false })),
  useIndicatorsQuery: vi.fn(() => ({ data: null, isLoading: false })),
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

vi.mock('@features/fundamental/api/useFtsCard', () => ({
  useFtsCard: vi.fn(() => ({ data: null, isLoading: false, isError: false })),
}));

function renderShell() {
  return render(<TechnicalWorkspace symbol="فولاد" />);
}

beforeEach(() => {
  localStorage.clear();
  useTechnicalStore.getState().reset();
  useTechnicalWorkspaceStore.getState().reset();
});

afterEach(cleanup);

describe('workspace modes', () => {
  it('starts in analysis with chart, inspector and feed', () => {
    renderShell();
    expect(screen.getByTestId('workspace-mode-label').textContent).toContain('تحلیل');
    expect(screen.getByTestId('panel-chart')).toBeTruthy();
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
    expect(screen.getByTestId('panel-feed')).toBeTruthy();
  });

  it('switches to scan and shows scanner + compact chart + feed', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('workspace-mode-scan'));

    expect(screen.getByTestId('workspace-mode-label').textContent).toContain('اسکن');
    expect(screen.getByTestId('panel-scanner')).toBeTruthy();
    expect(screen.getByTestId('panel-chart')).toBeTruthy();
    expect(screen.getByTestId('panel-feed')).toBeTruthy();
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
  });

  it('switches to research and shows chart, fundamental, feed and inspector', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('workspace-mode-research'));

    expect(screen.getByTestId('workspace-mode-label').textContent).toContain('پژوهش');
    for (const kind of ['chart', 'fundamental', 'feed', 'inspector'] as const) {
      expect(screen.getByTestId(`panel-${kind}`), kind).toBeTruthy();
    }
    expect(screen.queryByTestId('panel-scanner')).toBeNull();
  });

  it('opens the command palette with Ctrl+K and closes it with Escape', () => {
    renderShell();
    fireEvent.keyDown(window, { key: 'k', code: 'KeyK', ctrlKey: true });

    const palette = screen.getByTestId('command-palette');
    expect(within(palette).getByTestId('command-palette-input')).toBeTruthy();
    expect(within(palette).getByTestId('command-action-mode-scan')).toBeTruthy();
    expect(within(palette).getByTestId('command-action-layout-save')).toBeTruthy();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('command-palette')).toBeNull();
  });

  it('changes mode and toggles a panel from the palette', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('workspace-command-btn'));

    fireEvent.click(screen.getByTestId('command-action-mode-scan'));
    expect(useTechnicalWorkspaceStore.getState().mode).toBe('scan');
    expect(screen.queryByTestId('command-palette')).toBeNull();

    fireEvent.keyDown(window, { key: 'k', code: 'KeyK', ctrlKey: true });
    fireEvent.click(screen.getByTestId('command-action-panel-inspector'));
    expect(useTechnicalWorkspaceStore.getState().mode).toBe('scan');
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
  });
});
