/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/EventFeed.test.tsx
 *
 * آزمون‌های میزبانی پنل‌ها در فید رویدادها (B3):
 * - تب رویدادها → ScannerFeed (فهرست/رویدادها/قواعد، بدون کارت)
 * - تب ۵۰ نماد → Top50Panel
 * - تب لبه آماری → EdgePanel
 * - تب‌های خود فید تنها نوار تب صفحه‌اند؛ نوار تب کشو دیگر رندر نمی‌شود
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { EventFeed } from '../EventFeed';
import { useTechnicalStore } from '../../../model/technicalStore';
import type { ChartPattern } from '../../../model/patterns/types';

vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: { data: [] },
    isLoading: false,
    isError: false,
  })),
}));

const point = (index: number, price = 100) => ({ index, price, timestamp: index * 60_000 });

const formingFlag = (): ChartPattern => ({
  id: 'events-flag',
  kind: 'FLAG_BULL',
  direction: 'bullish',
  family: 'continuation',
  tier: 1,
  anchor: point(40, 105),
  points: [],
  upper: { from: point(30, 106), to: point(40, 106) },
  lower: { from: point(30, 104), to: point(40, 104) },
  target: 112,
  stopLoss: 98,
  quality: 60,
  status: 'forming',
});

const renderFeed = () => render(<EventFeed activeSymbol="فولاد" />);

beforeEach(() => {
  useTechnicalStore.getState().reset();
  useTechnicalStore.setState({ isLeftDrawerOpen: true, activePanel: 'events' });
  useTechnicalStore.getState().setDetectedPatterns([formingFlag()]);
});

afterEach(cleanup);

describe('EventFeed panel hosting', () => {
  it('renders the scanner list in the events tab and no active event card', () => {
    renderFeed();

    const scannerPanel = screen.getByTestId('scanner-panel');
    expect(scannerPanel.contains(screen.getByTestId('pattern-list'))).toBe(true);
    expect(screen.getByTestId('pattern-row-events-flag')).toBeTruthy();
    expect(screen.getByTestId('pattern-rules')).toBeTruthy();
    expect(screen.queryByTestId('top50-panel')).toBeNull();
    // کارت رویداد فعال فقط در ریل بازرس است.
    expect(screen.queryByTestId('pattern-card')).toBeNull();
  });

  it('swaps to Top50Panel on the top50 tab', () => {
    renderFeed();

    fireEvent.click(screen.getByTestId('feed-tab-top50'));

    expect(screen.getByTestId('top50-panel')).toBeTruthy();
    expect(screen.queryByTestId('scanner-panel')).toBeNull();
    expect(useTechnicalStore.getState().activePanel).toBe('top50');
    expect(useTechnicalStore.getState().activeDrawerTab).toBe('top50');
  });

  it('shows EdgePanel only as the active tab content', () => {
    renderFeed();
    // پنل لبه برای آزمون‌های سیستمی سوار می‌ماند، ولی در تب رویدادها پنهان است.
    expect(screen.getByTestId('edge-tab-panel').className).toContain('hidden');

    fireEvent.click(screen.getByTestId('feed-tab-edge'));

    expect(screen.getByTestId('edge-tab-panel').className).not.toContain('hidden');
    expect(screen.queryByTestId('scanner-panel')).toBeNull();
  });

  it('keeps the feed tab strip as the single tab UI', () => {
    renderFeed();

    expect(screen.getByTestId('workspace-feed-tabs')).toBeTruthy();
    // تب‌های داخلی کشو دیگر روی صفحه نیستند؛ فقط تب‌های خود فید می‌مانند.
    expect(screen.queryByTestId('drawer-tab-scanner')).toBeNull();
    expect(screen.queryByTestId('drawer-tab-top50')).toBeNull();
  });
});
