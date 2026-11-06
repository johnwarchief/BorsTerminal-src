/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/LayoutMenu.test.tsx
 *
 * ذخیره/بازیابی چیدمان نام‌دار و میان‌برهای undo/redo:
 *   ذخیره از منوی چیدمان → سوییچ مود → بازیابی همان چیدمان → ترکیب پنل‌ها
 *   Ctrl+Z برگشت به ریشهٔ قبلی و Ctrl+Shift+Z اجرای دوباره.
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

describe('layout menu', () => {
  it('saves a named layout, switches mode and restores it', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('layout-menu-btn'));
    const menu = screen.getByTestId('layout-menu');
    fireEvent.change(within(menu).getByTestId('layout-name-input'), { target: { value: 'چیدمان من' } });
    fireEvent.click(within(menu).getByTestId('layout-save-btn'));

    const saved = useTechnicalWorkspaceStore.getState().layouts.analysis.find((l) => l.name === 'چیدمان من');
    expect(saved).toBeTruthy();
    const savedRoot = saved!.root;

    fireEvent.click(screen.getByTestId('workspace-mode-scan'));
    expect(screen.getByTestId('panel-scanner')).toBeTruthy();

    fireEvent.click(screen.getByTestId('layout-menu-btn'));
    fireEvent.click(screen.getByTestId(`layout-item-${saved!.id}`));

    expect(useTechnicalWorkspaceStore.getState().mode).toBe('analysis');
    expect(useTechnicalWorkspaceStore.getState().root).toEqual(savedRoot);
    for (const kind of ['chart', 'inspector', 'feed'] as const) {
      expect(screen.getByTestId(`panel-${kind}`), kind).toBeTruthy();
    }
  });

  it('undoes and redoes a closed panel with Ctrl+Z and Ctrl+Shift+Z', () => {
    renderShell();
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();

    fireEvent.click(screen.getByTestId('tw-tile-close-ta-inspector'));
    expect(screen.queryByTestId('panel-inspector')).toBeNull();

    fireEvent.keyDown(window, { key: 'z', code: 'KeyZ', ctrlKey: true });
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();

    fireEvent.keyDown(window, { key: 'z', code: 'KeyZ', ctrlKey: true, shiftKey: true });
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
  });

  it('exposes undo and redo inside the menu as well', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('tw-tile-close-ta-feed'));
    fireEvent.click(screen.getByTestId('layout-menu-btn'));
    fireEvent.click(screen.getByTestId('layout-undo-btn'));
    expect(screen.getByTestId('panel-feed')).toBeTruthy();

    fireEvent.click(screen.getByTestId('layout-menu-btn'));
    fireEvent.click(screen.getByTestId('layout-redo-btn'));
    expect(screen.queryByTestId('panel-feed')).toBeNull();
  });

  it('ignores Ctrl+Z while typing a layout name', () => {
    renderShell();
    fireEvent.click(screen.getByTestId('layout-menu-btn'));
    const input = screen.getByTestId('layout-name-input');
    input.focus();
    fireEvent.keyDown(input, { key: 'z', code: 'KeyZ', ctrlKey: true });
    expect(useTechnicalWorkspaceStore.getState().undoStacks.analysis).toHaveLength(0);
  });
});
