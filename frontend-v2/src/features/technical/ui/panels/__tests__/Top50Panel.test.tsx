/**
 * frontend-v2/src/features/technical/ui/panels/__tests__/Top50Panel.test.tsx
 *
 * پوشش تعاملی پنل ۵۰ نماد برتر (منتقل‌شده از آزمون کشوی بازنشسته — R-PB-6):
 * ۱. فیلتر جستجو روی ردیف‌ها
 * ۲. فیلتر دسته‌بندی (سهام عادی/حق تقدم/همه)
 * ۳. ستون سیگنال و بج سیگنال بر پایهٔ دادهٔ تابلو و سیگنال‌های استور
 *
 * همان فیکسچر/موکِ آزمون قبلی کشو (useBoard با سه نماد و QueryClient).
 */

import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Top50Panel, type AssetCategoryFilter } from '../Top50Panel';
import { useTechnicalStore } from '../../../model/technicalStore';

vi.mock('@features/market/api/useBoard', () => ({
  useBoard: vi.fn(() => ({
    data: {
      data: [
        { symbol: 'فولاد', name: 'فولاد مبارکه', sector_name: 'فلزات', p_last: 5850, percent_last: 2.5, q_tot_cap: 900_000_000_000, tvol: 150_000_000 },
        { symbol: 'فملی', name: 'ملی مس', sector_name: 'فلزات', p_last: 7420, percent_last: 1.8, q_tot_cap: 800_000_000_000, tvol: 100_000_000 },
        { symbol: 'شپنا', name: 'پالایش نفت', sector_name: 'نفت', p_last: 4610, percent_last: -0.6, q_tot_cap: 700_000_000_000, tvol: 120_000_000 },
      ],
    },
    isLoading: false,
    isError: false,
  })),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

/** میزبان همان وضعیتِ جستجو/دسته‌ای است که EventFeed نگه می‌دارد. */
function Harness({ activeSymbol = 'فولاد' }: { activeSymbol?: string }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AssetCategoryFilter>('all');
  return (
    <Top50Panel
      activeSymbol={activeSymbol}
      onSelect={() => {}}
      searchQuery={searchQuery}
      onSearchQueryChange={setSearchQuery}
      selectedCategory={selectedCategory}
      onCategoryChange={setSelectedCategory}
    />
  );
}

function renderPanel(activeSymbol = 'فولاد') {
  return render(
    <QueryClientProvider client={queryClient}>
      <Harness activeSymbol={activeSymbol} />
    </QueryClientProvider>
  );
}

describe('Top50Panel interactions', () => {
  beforeEach(() => {
    useTechnicalStore.getState().reset();
  });

  afterEach(cleanup);

  it('filters symbols when user types into the search input', () => {
    renderPanel();

    expect(screen.getByTestId('top50-row-فولاد')).toBeTruthy();
    expect(screen.getByTestId('top50-row-فملی')).toBeTruthy();

    const searchInput = screen.getByTestId('top50-search-input') as HTMLInputElement;
    fireEvent.change(searchInput, { target: { value: 'فملی' } });

    expect(screen.getByTestId('top50-row-فملی')).toBeTruthy();
    expect(screen.queryByTestId('top50-row-فولاد')).toBeNull();
  });

  it('renders category filter chips and filters the list by category', () => {
    renderPanel();

    for (const cat of ['all', 'stock', 'right', 'fund'] as const) {
      expect(screen.getByTestId(`category-filter-${cat}`)).toBeTruthy();
    }

    // هر سه نماد فیکسچر سهام عادی‌اند.
    fireEvent.click(screen.getByTestId('category-filter-stock'));
    expect(screen.getByTestId('top50-row-فولاد')).toBeTruthy();

    // در فیکسچر حق تقدمی نیست.
    fireEvent.click(screen.getByTestId('category-filter-right'));
    expect(screen.queryByTestId('top50-row-فولاد')).toBeNull();

    // بازگشت به همه.
    fireEvent.click(screen.getByTestId('category-filter-all'));
    expect(screen.getByTestId('top50-row-فولاد')).toBeTruthy();
  });

  it('renders the signal column with a badge derived from the board row', () => {
    renderPanel();

    expect(screen.getByText('سیگنال')).toBeTruthy();

    // فیکسچر بدون قدرت خریدار/حجم خاص: سیگنال خنثی.
    const signalCell = screen.getByTestId('top50-signal-فولاد');
    expect(signalCell.textContent).toBe('خنثی');
    expect(screen.getByTestId('top50-signal-فملی').textContent).toBe('خنثی');
  });

  it('shows the pullback signal for the selected symbol from the store', () => {
    useTechnicalStore.getState().setDetectedPullbackSignals([
      { id: 'pullback-1', type: 'BULLISH', index: 42, timestamp: 42 * 60_000, price: 101, superTrendPrice: 99, qualityScore: 77 },
    ]);

    renderPanel('فولاد');

    // نماد فعال سیگنال پولبک استور را نشان می‌دهد، نه سیگنال خنثی تابلو.
    expect(screen.getByTestId('top50-signal-فولاد').textContent).toBe('پولبک خرید');
    // سایر ردیف‌ها همچنان از دادهٔ تابلو سیگنال می‌گیرند.
    expect(screen.getByTestId('top50-signal-فملی').textContent).toBe('خنثی');
  });
});
