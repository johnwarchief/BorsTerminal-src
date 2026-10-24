// src/__tests__/sarkhati-selection.spec.tsx — انتخابِ ترکیبیِ دیده‌بان/پرتفوی،
// ذخیرهٔ فهرست و جدا نگه‌داشتنِ هدف/اولویت از ارسالِ سفارش.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiSelectionCard } from '@features/portfolio/components/sarkhati/SarkhatiSelectionCard';
import { useSarkhatiSelectionStore } from '@features/portfolio/stores/sarkhatiSelectionStore';
import { useSymbolStore } from '@shared/stores/symbolStore';

const F = vi.hoisted(() => ({
  failWatch: false,
  feed: [
    { symbol: 'فولاد', name: 'فولاد مبارکه', p_last: 1000, percent_change: 1.2, is_live: true },
    { symbol: 'شپنا', name: 'پالایش نفت اصفهان', p_last: 2000, percent_change: -0.5, is_live: true },
  ],
  watch: {
    status: 'success', state: 'WATCHLIST_VERIFIED', raw_count: 2, resolved_count: 2,
    unresolved_count: 0, fetched_at: '2026-10-21T10:00:00',
    categories: [{ id: 'c1', name: 'لیست من', count: 2 }],
    rows: [
      { isin: 'I1', symbol: 'فولاد', ins_code: '1', resolved: true,
        category_name: 'لیست من', mapping_error: '' },
      { isin: 'I2', symbol: 'شپنا', ins_code: '2', resolved: true,
        category_name: 'لیست من', mapping_error: '' },
    ],
  },
  port: {
    status: 'success', state: 'PORTFOLIO_PARTIALLY_VERIFIED', raw_count: 2,
    resolved_count: 1, unresolved_count: 1, missing_fields:
      ['quantity', 'free_quantity', 'sellable_quantity'],
    fetched_at: '2026-10-21T10:01:00',
    positions: [
      { isin: 'I1', symbol: 'فولاد', ins_code: '1', resolved: true,
        broker_name: 'فولاد', asset: 1000000, avg_buy: 900000 },
      { isin: 'I3', resolved: false, mapping_error: 'ISIN_NOT_MAPPED',
        broker_name: 'ناشناس', asset: 2000 },
    ],
    rows: [],
  },
  bp: {
    status: 'success', state: 'BUYING_POWER_VERIFIED', value: 50000000,
    unit: 'IRR', source: 'easytrader:/easy/api/money', formula:
      'buyPowerT2 - credit - avandCredit', fetched_at: '2026-10-21T10:02:00',
    raw: { buyPowerT2: 50000000, credit: 0, avandCredit: 0 },
    order_write_state: 'ORDER_WRITE_UNVERIFIED',
  },
}));

vi.mock('@shared/api/marketFeed', () => ({
  useMarketFeedShared: () => ({ data: F.feed, isError: false }),
}));
vi.mock('@features/portfolio/lib/orderClient', () => ({
  useEasyTraderWatchlist: () => ({
    data: F.watch, isPending: false, isError: F.failWatch,
    error: F.failWatch ? new Error('fixture failure') : null,
  }),
  useExecutionPortfolio: () => ({ data: F.port, isPending: false, isError: false }),
  useBuyingPower: () => ({ data: F.bp, isPending: false, isError: false }),
}));

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiSelectionCard /></QueryClientProvider>);
}

beforeEach(() => {
  F.failWatch = false;
  localStorage.clear();
  useSarkhatiSelectionStore.setState({
    items: [], savedAt: null, sourceTimes: {}, dirty: false,
  });
  useSymbolStore.setState({ symbol: 'فولاد' });
});

describe('انتخابِ سرخطی از دیده‌بان و پرتفوی', () => {
  it('نمادِ مشترک یک ردیف با هر دو منبع است؛ ردیفِ نگاشت‌نشده قابلِ انتخاب نیست', () => {
    renderCard();
    const row = screen.getByTestId('sarkhati-source-row-isin:I1');
    expect(row.textContent).toContain('دیده‌بان');
    expect(row.textContent).toContain('پرتفوی');
    expect(screen.getByTestId('sources-watchlist').textContent).toContain('۲');
    expect(screen.getByTestId('sources-portfolio').textContent).toContain('۱');
    expect(screen.getByTestId('sources-unresolved').textContent).toContain('۱');
  });

  it('انتخاب، هدف، بودجه، اولویت و ذخیره — بدونِ هیچ مقدار مالی در پروفایل', () => {
    renderCard();
    fireEvent.click(screen.getByTestId('sarkhati-source-pick-isin:I1'));
    expect(screen.getByTestId('sarkhati-selection-count').textContent).toContain('۱');
    fireEvent.click(screen.getByTestId('sarkhati-goal-sell-0'));
    fireEvent.change(screen.getByTestId('sarkhati-amount-0'),
      { target: { value: '۱۲۰۰۰۰۰' } });
    fireEvent.click(screen.getByTestId('sarkhati-selection-save'));
    const raw = localStorage.getItem('bors-sarkhati-selection-v1') ?? '';
    const saved = JSON.parse(raw) as { items: Array<Record<string, unknown>>; savedAt: string };
    expect(saved.savedAt).toBeTruthy();
    expect(saved.items).toHaveLength(1);
    expect(saved.items[0]).toMatchObject({ key: 'isin:I1', symbol: 'فولاد', goal: 'sell' });
    expect(saved.items[0].amount).toBe('۱۲۰۰۰۰۰');
    expect(raw).not.toContain('buyPower');
    expect(raw).not.toContain('token');
    expect(raw).not.toContain('asset');
  });

  it('نمادِ مشترک با یک ISIN یکی می‌شود، حتی اگر املاي منبع‌ها فرق کند', () => {
    const symWatch = F.watch.rows[0].symbol;
    const symPort = F.port.positions[0].symbol;
    F.watch.rows[0].symbol = 'فولاد مبارکه';
    F.port.positions[0].symbol = 'فولاد';
    try {
      renderCard();
      const row = screen.getByTestId('sarkhati-source-row-isin:I1');
      expect(row.textContent).toContain('دیده‌بان');
      expect(row.textContent).toContain('پرتفوی');
      expect(screen.queryByTestId('sarkhati-source-row-sym:فولاد')).toBeNull();
    } finally {
      F.watch.rows[0].symbol = symWatch;
      F.port.positions[0].symbol = symPort;
    }
  });

  it('دو ISINِ متفاوت برایِ یک نماد جدا می‌مانند و گزارش می‌شوند', () => {
    F.watch.rows.push({ isin: 'I4', symbol: 'فولاد', ins_code: '1', resolved: true,
      category_name: 'لیست من', mapping_error: '' });
    try {
      renderCard();
      expect(screen.getByTestId('sources-identity-conflicts').textContent).toContain('۱');
      expect(screen.getByTestId('sarkhati-source-row-isin:I1')).toBeTruthy();
      expect(screen.getByTestId('sarkhati-source-row-isin:I4')).toBeTruthy();
    } finally {
      F.watch.rows.pop();
    }
  });

  it('خطای دیده‌بان دادهٔ قبلی را سبز نگه نمی‌دارد', () => {
    F.failWatch = true;
    try {
      renderCard();
      expect(screen.getByTestId('sources-watchlist').textContent).toContain('در دسترس نیست');
      expect(screen.getByTestId('sources-watchlist-error').textContent)
        .toContain('fixture failure');
      expect(screen.queryByTestId('sarkhati-source-row-isin:I1')).toBeNull();
    } finally {
      F.failWatch = false;
    }
  });

  it('انتخابِ نماد برای فرم، فرم را رویِ همان نماد می‌گذارد', () => {
    renderCard();
    fireEvent.click(screen.getByTestId('sarkhati-source-use-isin:I2'));
    expect(useSymbolStore.getState().symbol).toBe('شپنا');
  });

  it('اولویت و پاک‌کردن درِ همان store می‌ماند', () => {
    const s = useSarkhatiSelectionStore.getState();
    s.toggle({ symbol: 'الف', name: '', isin: null, ins_code: null, sources: ['market'] });
    s.toggle({ symbol: 'ب', name: '', isin: null, ins_code: null, sources: ['market'] });
    const bKey = useSarkhatiSelectionStore.getState().items[1].key;
    useSarkhatiSelectionStore.getState().move(bKey, -1);
    expect(useSarkhatiSelectionStore.getState().items.map((x) => x.symbol)).toEqual(['ب', 'الف']);
    useSarkhatiSelectionStore.getState().clear();
    expect(useSarkhatiSelectionStore.getState().items).toHaveLength(0);
  });
});
