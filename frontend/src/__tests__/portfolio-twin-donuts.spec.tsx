// تست دونات دوقلو + سنجهٔ هم‌ترازی + state مشتق صنایع (M-04)
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';
import { TwinDonuts } from '@features/portfolio/components/TwinDonuts';
import { SectorMatrix } from '@features/portfolio/components/SectorMatrix';
import { useAssetValues } from '@features/portfolio/stores/assetValues';
import { useTargetAllocation } from '@features/portfolio/stores/targetAllocation';
import {
  FTS_STANDARD_BUCKETS,
  FTS_STANDARD_TOTAL_PCT,
  alignmentScore,
  alignmentStatus,
  compareToStandard,
  dataCoverage,
  filledPct,
  rebalanceOrders,
  trackingError,
} from '@features/portfolio/model/standardAllocation';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

let decisions: Record<string, unknown>[] = [];

function feed() {
  return {
    status: 'success',
    decisions,
    portfolio: decisions.filter((d) => d.status === 'accept'),
    monitor: [],
    counts: {},
    limits: { min: 5, max: 7, weight_cap_pct: 20 },
  };
}

function ok(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
  return { ...utils, qc };
}

beforeEach(() => {
  decisions = [];
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    if (String(url) === '/api/selection/portfolio') return Promise.resolve(ok(feed()));
    return Promise.resolve(ok({ status: 'empty' }));
  });
  localStorage.clear();
  useAssetValues.getState().reset();
  useTargetAllocation.getState().reset();
});

describe('مدل سبد استاندارد و سنجهٔ هم‌ترازی', () => {
  it('نسبت‌های مصوب سند: ۴۵/۱۵/۱۵/۱۰/۱۵ و جمع ۱۰۰٪', () => {
    expect(FTS_STANDARD_BUCKETS.map((b) => b.pct)).toEqual([45, 15, 15, 10, 15]);
    expect(FTS_STANDARD_TOTAL_PCT).toBe(100);
    expect(FTS_STANDARD_BUCKETS.map((b) => b.label)).toEqual([
      'طلا و سکه',
      'سهام مستقیم',
      'ارز دیجیتال',
      'نقره',
      'درآمد ثابت و نقدینگی',
    ]);
  });

  it('وزن واقعی: سهام از پوزیشن‌های سبد و طلا از ارزش ثبت‌شده محاسبه می‌شود', () => {
    const rows = compareToStandard({
      equityWeightPct: 12,
      totalValueToman: 1_000_000_000,
      values: { gold: 500_000_000, crypto: 0, silver: 0, fixed: 0 },
    });
    const equity = rows.find((r) => r.bucket.id === 'equity')!;
    expect(equity.actualPct).toBe(12);
    expect(equity.source).toBe('basket');
    expect(equity.deviationPct).toBe(-3);
    expect(equity.state).toBe('underweight');

    const gold = rows.find((r) => r.bucket.id === 'gold')!;
    expect(gold.actualPct).toBe(50);
    expect(gold.source).toBe('value');
    expect(gold.state).toBe('overweight');

    // طبقات ثبت‌نشده «بدون داده» می‌مانند (نه صفر ساختگی)
    const silver = rows.find((r) => r.bucket.id === 'silver')!;
    expect(silver.actualPct).toBeNull();
    expect(silver.state).toBe('nodata');
    expect(silver.deviationPct).toBeNull();

    const coverage = dataCoverage(rows);
    expect(coverage).toEqual({ covered: 2, total: 5 });
  });

  it('خطای انحراف و نمرهٔ انطباق از انحراف معیار طبقات دارای داده', () => {
    const rows = compareToStandard({
      equityWeightPct: 18,
      totalValueToman: 1_000_000_000,
      values: { gold: 450_000_000, crypto: 150_000_000, silver: 100_000_000, fixed: 150_000_000 },
    });
    // انحراف‌ها: طلا ۰ · سهام +۳ · کریپتو ۰ · نقره ۰ · نقد ۰ ⇒ TE=3
    const te = trackingError(rows);
    expect(te).toBe(3);
    expect(alignmentScore(te)).toBe(94);
    const st = alignmentStatus(rows, alignmentScore(te));
    expect(st.label).toContain('سهام مستقیم');
    expect(st.label).toContain('مازاد');
    expect(st.tone).toBe('green');
  });

  it('بدون داده هیچ نمره‌ای ساخته نمی‌شود', () => {
    const rows = compareToStandard({ equityWeightPct: null, totalValueToman: 0, values: { gold: 0, crypto: 0, silver: 0, fixed: 0 } });
    expect(trackingError(rows)).toBeNull();
    expect(alignmentScore(null)).toBeNull();
    expect(filledPct(rows)).toBeNull();
    expect(alignmentStatus(rows, null).tone).toBe('gray');
  });

  it('دستورات ری‌بالانس: خرید کسری و فروش مازاد با مبلغ ریالی', () => {
    const rows = compareToStandard({
      equityWeightPct: 5,
      totalValueToman: 1_000_000_000,
      values: { gold: 600_000_000, crypto: 150_000_000, silver: 100_000_000, fixed: 150_000_000 },
    });
    const orders = rebalanceOrders(rows, 1_000_000_000);
    const gold = orders.find((o) => o.bucket.id === 'gold')!;
    expect(gold.action).toBe('sell'); // ۶۰٪ در برابر هدف ۴۵٪
    expect(gold.amountToman).toBe(150_000_000);
    const equity = orders.find((o) => o.bucket.id === 'equity')!;
    expect(equity.action).toBe('buy'); // ۵٪ در برابر هدف ۱۵٪
    expect(equity.amountToman).toBe(100_000_000);
  });
});

describe('کامپوننت دونات دوقلو', () => {
  it('دو دونات هم‌اندازه + مرکز «تخصیص هدف» و «درصد پرشده»', async () => {
    decisions = [{ symbol: 'شپنا', status: 'accept', weight_eff_pct: 12, sector: 'فلزات اساسي' }];
    renderWithClient(<TwinDonuts />);
    expect(await screen.findByText('تحلیل دارایی‌های پرتفو')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'چارت دونات پرتفوی هدف' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'چارت دونات پرتفوی واقعی' })).toBeInTheDocument();
    expect(screen.getByText('تخصیص هدف')).toBeInTheDocument();
    expect(screen.getByText('درصد پرشده از سرمایه')).toBeInTheDocument();
    // لیست هدف شامل برچسب طبقات سند
    expect(screen.getAllByText('طلای فیزیکی، سکه و شمش').length).toBeGreaterThanOrEqual(1);
  });

  it('سنجهٔ هم‌ترازی و دکمهٔ دستورات ری‌بالانس کار می‌کنند', async () => {
    decisions = [{ symbol: 'شپنا', status: 'accept', weight_eff_pct: 12, sector: 'فلزات اساسي' }];
    useAssetValues.getState().setTotalToman(1_000_000_000);
    useAssetValues.getState().setValue('gold', 600_000_000);
    renderWithClient(<TwinDonuts />);
    await screen.findByText('تحلیل دارایی‌های پرتفو');
    // نمرهٔ انطباق عددی نمایش داده می‌شود
    await waitFor(() => expect(screen.getByText(/خطای انحراف \(TE\)/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /محاسبه دستورات ری‌بالانس/ }));
    expect(await screen.findByText(/فروش .* از طلا و سکه/)).toBeInTheDocument();
    expect(screen.getAllByText(/خرید .* در سهام مستقیم/).length).toBeGreaterThanOrEqual(1);
  });

  it('بدون پوزیشن و بدون ارزش ⇒ «بدون داده» صادقانه', async () => {
    renderWithClient(<TwinDonuts />);
    await screen.findByText('تحلیل دارایی‌های پرتفو');
    expect(screen.getAllByText(/بدون داده/).length).toBeGreaterThan(0);
    expect(screen.getByText(/برای ساخت پرتفوی واقعی/)).toBeInTheDocument();
  });

  it('با showActual={false} دونات واقعی حذف می‌شود تا در تب هدف تکرار نشود', async () => {
    renderWithClient(<TwinDonuts showActual={false} />);
    expect(await screen.findByText('تحلیل دارایی‌های پرتفو')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'چارت دونات پرتفوی هدف' })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'چارت دونات پرتفوی واقعی' })).not.toBeInTheDocument();
  });
});

describe('state مشتق صنایع: افزودن نماد بلافاصله وزن صنعت را عوض می‌کند', () => {
  it('وپاسار با ۴٪ ردیف بانکی را از ۰٪ به ۴٪ می‌برد و در بازهٔ سند می‌ماند', async () => {
    const { qc } = renderWithClient(<SectorMatrix />);
    const bankRow = (await screen.findByText('بانکی')).closest('tr')!;
    // ابتدا بدون پوزیشن
    await waitFor(() => expect(within(bankRow).getByText('بدون پوزیشن')).toBeInTheDocument());

    // افزودن پوزیشن بانکی (وپاسار ۴٪) در سبد
    decisions = [{ symbol: 'وپاسار', status: 'accept', weight_eff_pct: 4, sector: 'بانكها و موسسات اعتباري' }];
    await qc.invalidateQueries({ queryKey: ['portfolio'] });

    await waitFor(() => expect(within(bankRow).getByText('وپاسار')).toBeInTheDocument());
    expect(within(bankRow).getAllByText('۴٪').length).toBeGreaterThanOrEqual(1);
    expect(within(bankRow).getByText('در محدوده')).toBeInTheDocument();
  });

  it('عبور از سقف سند ⇒ بج قرمز «نقض سقف وزنی (Overweight)»', async () => {
    decisions = [
      { symbol: 'وپاسار', status: 'accept', weight_eff_pct: 7, sector: 'بانكها و موسسات اعتباري' },
      { symbol: 'وبملت', status: 'accept', weight_eff_pct: 6, sector: 'بانكها و موسسات اعتباري' },
    ];
    renderWithClient(<SectorMatrix />);
    const bankRow = (await screen.findByText('بانکی')).closest('tr')!;
    await waitFor(() => expect(within(bankRow).getByText('۱۳٪')).toBeInTheDocument());
    expect(within(bankRow).getByText(/نقض سقف وزنی \(Overweight\)/)).toBeInTheDocument();
    expect(within(bankRow).getByText('وپاسار')).toBeInTheDocument();
    expect(within(bankRow).getByText('وبملت')).toBeInTheDocument();
  });
});
