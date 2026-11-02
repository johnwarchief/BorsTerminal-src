/**
 * ui/__tests__/TelegramCatalogList.test.tsx
 *
 * شمارش سطر، فیلترِ جستجو، lazy بودن تصویر، باز/بسته شدن لایت‌باکس، و اینکه
 * سطرِ پیاده‌شده سوئیچ دارد و سطرِ دیگر نوشتهٔ «پیاده‌سازی نشده».
 */

import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import { TelegramCatalogList } from '../TelegramCatalogList';
import { useTechnicalStore } from '../../model/technicalStore';
import { TELEGRAM_CATALOG } from '../../lib/telegramIndicatorCatalog';

afterEach(cleanup);

describe('TelegramCatalogList', () => {
  it('renders all 64 rows', () => {
    render(<TelegramCatalogList />);
    expect(screen.getByTestId('telegram-catalog-list')).toBeDefined();
    expect(screen.getByTestId('telegram-row-p01')).toBeDefined();
    expect(screen.getByTestId('telegram-row-p64')).toBeDefined();
    expect(screen.getAllByTestId(/telegram-row-p\d{2}/)).toHaveLength(64);
  });

  it('shows the matched count in Persian digits', () => {
    render(<TelegramCatalogList />);
    const box = screen.getByTestId('telegram-catalog-count');
    expect(box.textContent).toContain('۶۴');
  });

  it('filters on search', () => {
    render(<TelegramCatalogList />);
    fireEvent.change(screen.getByTestId('telegram-catalog-search'), { target: { value: 'supertrend' } });
    const rows = screen.getAllByTestId(/telegram-row-p\d{2}/);
    expect(rows.length).toBeLessThan(64);
    expect(rows.length).toBeGreaterThan(0);
  });

  it('matches an attachment filename through the search box', () => {
    render(<TelegramCatalogList />);
    fireEvent.change(screen.getByTestId('telegram-catalog-search'), { target: { value: 'Indi 225.txt' } });
    expect(screen.getByTestId('telegram-row-p14')).toBeDefined();
    expect(screen.queryByTestId('telegram-row-p01')).toBeNull();
  });

  it('lazy-loads every thumbnail', () => {
    render(<TelegramCatalogList />);
    const thumbs = screen.getAllByTestId(/^telegram-thumb-p\d{2}$/);
    expect(thumbs).toHaveLength(64);
    for (const thumb of thumbs) {
      const img = thumb.querySelector('img');
      // jsdom 30 خاصیتِ img.loading را منعکس نمی‌کند (همیشه undefined)؛ پس خودِ صفتِ HTML
      expect(img?.getAttribute('loading')).toBe('lazy');
    }
  });

  it('opens and closes the lightbox with Escape', () => {
    render(<TelegramCatalogList />);
    fireEvent.click(screen.getByTestId('telegram-thumb-p12'));
    expect(screen.getByTestId('telegram-lightbox')).toBeDefined();
    fireEvent.keyDown(screen.getByTestId('telegram-lightbox'), { key: 'Escape' });
    expect(screen.queryByTestId('telegram-lightbox')).toBeNull();
  });

  it('linked rows toggle the overlay, others say not implemented', () => {
    useTechnicalStore.getState().reset();
    render(<TelegramCatalogList />);
    fireEvent.click(screen.getByTestId('toggle-indicator-p12'));
    expect(useTechnicalStore.getState().activeUserIndicators).toContain('DoubleTap3D');
    expect(screen.getByTestId('telegram-status-p01').textContent).toContain('پیاده‌سازی نشده');
  });

  it('renders the verbatim caption and never a translated one', () => {
    render(<TelegramCatalogList />);
    const row = TELEGRAM_CATALOG.find((r) => r.id === 'p02');
    expect(row?.captionEn).toContain('Timeframe M30');
    expect(screen.getByTestId('telegram-caption-p02').textContent).toContain('M30');
  });
});
