/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShell.test.tsx
 *
 * آزمون‌های پوستهٔ تازهٔ میزکار تکنیکال (TradingView-style shell):
 * ۱. رندر نوار بالا، نوار فعالیت، چارت، ریل بازرس و فید رویدادها
 * ۲. نوار فعالیت طبق §3: چارت | اسکنر | اندیکاتورها | تنظیمات (R-PB-4)
 * ۳. هم‌گامی برچسب و محتوای فید با تب‌های خود فید (R-PB-5)
 *
 * بچه‌های سنگین (چارت، نوار رسم، کنترل‌های پیش‌بینی)، کوئری‌ها و هوک تابلو
 * همان‌طور که در آزمون‌های موجود میزکار موک می‌شوند.
 */

import { render, screen, fireEvent, cleanup, within } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TechnicalWorkspace } from '../../TechnicalWorkspace';
import { useTechnicalStore } from '../../../model/technicalStore';
import type { ChartPattern } from '../../../model/patterns/types';

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

const formingPattern = (): ChartPattern => ({
  id: 'shell-flag',
  kind: 'FLAG_BULL',
  direction: 'bullish',
  family: 'continuation',
  tier: 1,
  anchor: { index: 40, price: 105, timestamp: 40 * 60_000 },
  points: [],
  upper: { from: { index: 30, price: 106, timestamp: 30 * 60_000 }, to: { index: 40, price: 106, timestamp: 40 * 60_000 } },
  lower: { from: { index: 30, price: 104, timestamp: 30 * 60_000 }, to: { index: 40, price: 104, timestamp: 40 * 60_000 } },
  target: 112,
  stopLoss: 98,
  quality: 60,
  status: 'forming',
});

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

  it('activity bar lists the spec §3 sections, not the feed tabs (R-PB-4)', () => {
    renderShell();

    for (const id of ['chart', 'scanner', 'indicators', 'settings']) {
      expect(screen.getByTestId(`activity-section-${id}`)).toBeTruthy();
    }
    // تب‌های فید باید فقط در خود فید باشند، نه در نوار فعالیت.
    expect(screen.queryByTestId('activity-panel-events')).toBeNull();
    expect(screen.queryByTestId('activity-panel-top50')).toBeNull();
    expect(screen.queryByTestId('activity-panel-edge')).toBeNull();

    // `aria-current` به‌جای `aria-pressed` برای بخش فعال.
    expect(screen.getByTestId('activity-section-chart').getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('activity-section-chart').getAttribute('aria-pressed')).toBeNull();

    fireEvent.click(screen.getByTestId('activity-section-scanner'));
    expect(screen.getByTestId('activity-section-scanner').getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('activity-section-chart').getAttribute('aria-current')).toBeNull();
  });

  it('scanner section opens the feed on the events panel (R-PB-4 / R-PB-5)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('activity-section-scanner'));

    expect(useTechnicalStore.getState().activePanel).toBe('events');
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);
    // «رویدادها» همان پنل اسکنر/رویدادهای میزبان است.
    expect(screen.getByTestId('scanner-panel')).toBeDefined();
    expect(screen.getByTestId('workspace-feed-active-panel').textContent).toBe('رویدادها');
  });

  it('feed tab strip keeps the hosted panel and the label in sync (R-PB-5)', () => {
    renderShell();

    // باز کردن از نوار فعالیت: پنل رویدادها (اسکنر) رندر می‌شود.
    fireEvent.click(screen.getByTestId('activity-section-scanner'));
    expect(screen.getByTestId('scanner-panel')).toBeDefined();
    expect(screen.getByTestId('feed-tab-events').getAttribute('aria-selected')).toBe('true');

    // سوییچ به ۵۰ نماد از تب‌های خود فید: پنل ۵۰ نماد و همان برچسب.
    fireEvent.click(screen.getByTestId('feed-tab-top50'));

    expect(screen.queryByTestId('scanner-panel')).toBeNull();
    expect(screen.getByTestId('top50-panel')).toBeDefined();
    expect(screen.getByTestId('feed-tab-top50').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('workspace-feed-active-panel').textContent).toBe('۵۰ نماد');
    expect(useTechnicalStore.getState().activePanel).toBe('top50');
  });

  it('renders exactly one active event card, inside the rail (B3)', () => {
    useTechnicalStore.getState().setDetectedPatterns([formingPattern()]);
    renderShell();

    // فید روی تب رویدادها باز می‌شود: ScannerFeed بدون کارت.
    fireEvent.click(screen.getByTestId('activity-section-scanner'));

    const cards = screen.getAllByTestId('pattern-card');
    expect(cards).toHaveLength(1);
    expect(screen.getByTestId('workspace-rail').contains(cards[0]!)).toBe(true);
    expect(screen.getByTestId('workspace-feed').querySelector('[data-testid="pattern-card"]')).toBeNull();
    expect(cards[0]!.textContent).toContain('کیفیت ساختار ۶۰');

    // تعویض تب فید کارت ریل را تکرار نمی‌کند.
    fireEvent.click(screen.getByTestId('feed-tab-top50'));
    expect(screen.getAllByTestId('pattern-card')).toHaveLength(1);
  });

  it('indicators section opens the feed on the indicators panel (R-PB-4)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('activity-section-indicators'));

    expect(useTechnicalStore.getState().activePanel).toBe('indicators');
    expect(screen.getByTestId('indicators-panel')).toBeDefined();
    expect(screen.getByTestId('workspace-feed-active-panel').textContent).toBe('اندیکاتورها');
  });

  it('chart section collapses the feed (R-PB-4)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('activity-section-scanner'));
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);

    fireEvent.click(screen.getByTestId('activity-section-chart'));

    expect(useTechnicalStore.getState().isLeftDrawerOpen).toBe(false);
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(true);
    expect(screen.queryByTestId('scanner-panel')).toBeNull();
  });

  it('settings section shows the existing chart settings in the rail (R-PB-4)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('activity-section-settings'));

    expect(screen.getByTestId('workspace-settings-panel')).toBeDefined();
    const logToggle = screen.getByTestId('settings-toggle-log-scale');
    expect(logToggle.getAttribute('role')).toBe('switch');

    const before = useTechnicalStore.getState().isLogScale;
    fireEvent.click(logToggle);
    expect(useTechnicalStore.getState().isLogScale).toBe(!before);
  });

  it('retires the wide drawer: no legacy drawer testids remain (B4)', () => {
    renderShell();

    expect(screen.queryByTestId('wide-workspace-drawer')).toBeNull();
    expect(screen.queryByTestId('wide-workspace-drawer-collapsed')).toBeNull();
    expect(screen.queryByTestId('slim-activity-bar')).toBeNull();
    expect(screen.queryByTestId('drawer-backdrop')).toBeNull();
    expect(screen.queryByTestId('drawer-resizer-handle')).toBeNull();
  });

  it('feed header pop-out opens the portal with the selected panel and Escape closes it (B4)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('feed-tab-top50'));
    fireEvent.click(screen.getByTestId('portal-modal-btn'));

    const portal = screen.getByTestId('portal-modal-backdrop');
    expect(within(portal).getByTestId('top50-panel')).toBeTruthy();

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(screen.queryByTestId('portal-modal-backdrop')).toBeNull();
  });

  it('collapsing the feed hides the panel but keeps the activity bar and header toggle (B4)', () => {
    renderShell();

    fireEvent.click(screen.getByTestId('activity-section-scanner'));
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);

    fireEvent.click(screen.getByTestId('workspace-feed-toggle'));

    expect(useTechnicalStore.getState().isLeftDrawerOpen).toBe(false);
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(true);
    expect(screen.queryByTestId('scanner-panel')).toBeNull();
    // نوار فعالیت و سربرگ فید (با دکمهٔ جمع‌کردن) دست‌نخورده می‌مانند.
    expect(screen.getByTestId('workspace-activity')).toBeDefined();
    expect(screen.getByTestId('workspace-feed-toggle').getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(screen.getByTestId('workspace-feed-toggle'));
    expect(screen.getByTestId('workspace-feed-body').hasAttribute('hidden')).toBe(false);
    expect(screen.getByTestId('scanner-panel')).toBeDefined();
  });
});
