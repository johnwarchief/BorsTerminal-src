/**
 * frontend-v2/src/features/technical/ui/panels/__tests__/IndicatorsPanel.test.tsx
 *
 * پوشش تعاملی پنل اندیکاتورها (منتقل‌شده از آزمون کشوی بازنشسته — R-PB-6):
 * ۱. دکمه‌های مد کانال و ثبت مد انتخاب‌شده در استور
 * ۲. کلیدهای روشن/خاموش اندیکاتورها و ثبت وضعیت در استور
 *
 * همان پیش‌فرض‌های آزمون قبلی: reset + enableDefaultIndicators.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { IndicatorsPanel } from '../IndicatorsPanel';
import { useTechnicalStore } from '../../../model/technicalStore';

describe('IndicatorsPanel interactions', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
    useTechnicalStore.getState().enableDefaultIndicators();
  });

  afterEach(cleanup);

  it('renders the smart indicator toggles and channel mode switcher', () => {
    render(<IndicatorsPanel />);

    for (const id of ['DoubleTap3D', 'SuperTrendPullback', 'AutoTrendlineCHoCH', 'MultiModeChannel']) {
      expect(screen.getByTestId(`toggle-indicator-${id}`)).toBeTruthy();
    }
    expect(useTechnicalStore.getState().channelMode).toBe('regression');
    expect(screen.getByTestId('channel-mode-btn-regression')).toBeTruthy();
  });

  it('toggles channel modes on button click and records them in the store', () => {
    render(<IndicatorsPanel />);

    fireEvent.click(screen.getByTestId('channel-mode-btn-retest_channel'));
    expect(useTechnicalStore.getState().channelMode).toBe('retest_channel');

    fireEvent.click(screen.getByTestId('channel-mode-btn-donchian'));
    expect(useTechnicalStore.getState().channelMode).toBe('donchian');

    fireEvent.click(screen.getByTestId('channel-mode-btn-regression'));
    expect(useTechnicalStore.getState().channelMode).toBe('regression');
  });

  it('toggles the multi-mode channel indicator off and on in the store', () => {
    render(<IndicatorsPanel />);

    const toggle = screen.getByTestId('toggle-indicator-MultiModeChannel');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    expect(useTechnicalStore.getState().activeUserIndicators).toContain('MultiModeChannel');

    fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    expect(useTechnicalStore.getState().activeUserIndicators).not.toContain('MultiModeChannel');
    // مدهای کانال فقط وقتی اندیکاتور روشن است دیده می‌شوند.
    expect(screen.queryByTestId('channel-mode-btn-regression')).toBeNull();

    fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-pressed')).toBe('true');
    expect(useTechnicalStore.getState().activeUserIndicators).toContain('MultiModeChannel');
    expect(screen.getByTestId('channel-mode-btn-regression')).toBeTruthy();
  });

  it('toggles a supplementary indicator and keeps the store in sync', () => {
    render(<IndicatorsPanel />);

    const toggle = screen.getByTestId('toggle-indicator-DoubleTap3D');
    expect(toggle.getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-pressed')).toBe('false');
    expect(useTechnicalStore.getState().activeUserIndicators).not.toContain('DoubleTap3D');
    // سایر اندیکاتورهای پیش‌فرض دست‌نخورده می‌مانند.
    expect(useTechnicalStore.getState().activeUserIndicators).toContain('SuperTrendPullback');
  });
});
