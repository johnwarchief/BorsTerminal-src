// F-09 — تست فیلتر «حذف نمادهای ناقص/مردود بر اساس شاخص»:
// ۱) منطق خالص applyExcludeFilter/rejectedFor برای هر ۶ شاخص (و رفتار صادقانه وقتی داده نیست)
// ۲) اعمال در جدول غربالگری: شمار ردیف‌ها قبل/بعد + شمارندهٔ «X نماد حذف شد» + بازنشانی
// ۳) سوئیچ‌های دراور + ماندگاری (localStorage) + کلید کانفیگ در payload
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { FtsSettingsDrawer } from '@features/fundamental/ui/FtsSettingsDrawer';
import {
  EXCLUDE_AXES,
  EXCLUDE_CONFIG_KEY,
  EXCLUDE_LABEL,
  applyExcludeFilter,
  getExcludeAxes,
  rejectedFor,
  resetExcludeAxes,
  setExcludeAxes,
} from '@features/fundamental/lib/exclusionFilter';
import { FTS_GUIDE_DEFAULTS } from '@features/fundamental/api/useFtsConfig';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

// jsdom اندازه ندارد -- virtualizer به رندر پنجره وادار می‌شود (الگوی TapeTable/F-08)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 12;
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'نماد',
    symbol_norm: 'نماد',
    name: 'شرکت نمونه',
    sector_name: 'مواد و محصولات دارویی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    gross_margin: 32.5,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    annual_sales_bt: 90.0,
    mcap: 5e13,
    score: 4,
    i1_pass: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

/** ۵ ردیف: ۳ سالم + ۱ مردودِ شاخص ۳ + ۱ با سابقهٔ ناقص EPS (شاخص ۲) */
function mixedRows(): FtsScreenRow[] {
  return [
    row({ symbol: 'سالم۱', score: 5 }),
    row({ symbol: 'سالم۲', score: 5 }),
    row({ symbol: 'سالم۳', score: 4 }),
    row({ symbol: 'مردود۳', score: 2, i3_pass: false, gross_margin: 8 }),
    row({ symbol: 'ناقص۲', score: 3, i2_pass: false, eps_series: [null, 590, 990], eps_years_available: 2 }),
  ];
}

beforeEach(() => {
  resetExcludeAxes();
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: 'success', config: { ...FTS_GUIDE_DEFAULTS } }),
  } as unknown as Response);
});

describe('F-09 — منطق فیلتر (بدون UI)', () => {
  it('برای ۵ شاخصِ دارای پرچم، ردیف مردود/ناقص تشخیص داده می‌شود', () => {
    expect(rejectedFor(row({ i1_pass: false }), '1a')).toBe(true);
    expect(rejectedFor(row({ i1_pass: null, rev_growth: null }), '1a')).toBe(true); // ناقص
    expect(rejectedFor(row({ i2_pass: false }), '2')).toBe(true);
    expect(rejectedFor(row({ i2_pass: true, eps_series: [null, 590, 990] }), '2')).toBe(true); // ناقص
    expect(rejectedFor(row({ i3_pass: false }), '3')).toBe(true);
    expect(rejectedFor(row({ i3_pass: null, gross_margin: null }), '3')).toBe(true);
    expect(rejectedFor(row({ i4_pass: false }), '4')).toBe(true);
    expect(rejectedFor(row({ i5_pass: false }), '5')).toBe(true);
    expect(rejectedFor(row({ i5_pass: true, pricing_mode: null }), '5')).toBe(true);
  });

  it('ردیف سالم با هیچ شاخصی حذف نمی‌شود', () => {
    for (const axis of EXCLUDE_AXES) {
      expect(rejectedFor(row(), axis)).not.toBe(true);
    }
    expect(applyExcludeFilter([row(), row({ symbol: 'ب' })], [...EXCLUDE_AXES]).hidden).toBe(0);
  });

  it('شاخص ۱ب (تناژ) در پاسخ غربالگری داده ندارد ⇒ صادقانه هیچ ردیفی حذف نمی‌شود', () => {
    expect(rejectedFor(row({ i1_pass: false }), '1b')).toBeNull();
    const res = applyExcludeFilter(mixedRows(), ['1b']);
    expect(res.rows).toHaveLength(5);
    expect(res.hidden).toBe(0);
  });

  it('شمار حذف‌شده‌ها برای شاخص‌های مختلف درست است', () => {
    const rows = mixedRows();
    expect(applyExcludeFilter(rows, ['3']).hidden).toBe(1);
    expect(applyExcludeFilter(rows, ['2']).hidden).toBe(1);
    expect(applyExcludeFilter(rows, ['2', '3']).hidden).toBe(2);
    expect(applyExcludeFilter(rows, []).hidden).toBe(0);
  });

  it('انتخاب شاخص‌ها در localStorage می‌ماند و بازنشانی آن را پاک می‌کند', () => {
    setExcludeAxes(['3', '2']);
    expect(getExcludeAxes()).toEqual(['2', '3']);
    expect(localStorage.getItem('fts:exclude-rejected-axes')).toBe(JSON.stringify(['2', '3']));
    resetExcludeAxes();
    expect(getExcludeAxes()).toEqual([]);
    expect(localStorage.getItem('fts:exclude-rejected-axes')).toBe('[]');
  });
});

describe('F-09 — اعمال فیلتر در جدول غربالگری', () => {
  it('انتخاب شاخص ۳ ردیف مردود را از جدول حذف می‌کند (شمار قبل/بعد + شمارنده)', () => {
    render(<FtsScreenTable rows={mixedRows()} onSelect={() => {}} />);
    expect(screen.queryByTestId('fts-axis-filter-bar')).toBeNull();
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(5);

    act(() => setExcludeAxes(['3']));
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(4);
    expect(screen.getByTestId('fts-axis-filter-count').textContent).toContain('۱ نماد');
    expect(screen.getByTestId('fts-axis-filter-bar').textContent).toContain(EXCLUDE_LABEL['3']);

    // بازنشانی از خودِ نوار جدول
    fireEvent.click(screen.getByTestId('fts-axis-filter-reset'));
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(5);
    expect(screen.queryByTestId('fts-axis-filter-bar')).toBeNull();
  });

  it('شاخص ۲ نماد با سابقهٔ ناقص EPS را حذف می‌کند', () => {
    render(<FtsScreenTable rows={mixedRows()} onSelect={() => {}} />);
    act(() => setExcludeAxes(['2']));
    const rows = screen.getAllByTestId('fts-screen-row');
    expect(rows).toHaveLength(4);
    expect(rows.map((r) => r.textContent).join(' ')).not.toContain('ناقص۲');
  });

  it('با شاخص بدون داده (۱ب) نوار فیلتر می‌آید ولی هیچ ردیفی حذف نمی‌شود', () => {
    render(<FtsScreenTable rows={mixedRows()} onSelect={() => {}} />);
    act(() => setExcludeAxes(['1b']));
    expect(screen.getAllByTestId('fts-screen-row')).toHaveLength(5);
    expect(screen.getByTestId('fts-axis-filter-count').textContent).toContain('نمادی حذف نشد');
  });
});

describe('F-09 — سوئیچ‌های دراور تنظیمات', () => {
  function renderDrawer() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <FtsSettingsDrawer open onClose={() => {}} />
      </QueryClientProvider>,
    );
  }

  it('برای هر ۶ شاخص یک سوئیچ وجود دارد و با کلیک ماندگار می‌شود', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText('فیلتر حذف بر اساس شاخص')).toBeInTheDocument());
    for (const axis of EXCLUDE_AXES) {
      expect(screen.getByText(EXCLUDE_LABEL[axis])).toBeInTheDocument();
    }
    fireEvent.click(screen.getByText(EXCLUDE_LABEL['3']));
    expect(getExcludeAxes()).toEqual(['3']);
    fireEvent.click(screen.getByText(EXCLUDE_LABEL['2']));
    expect(getExcludeAxes()).toEqual(['2', '3']);
    // بازنشانی از دراور
    fireEvent.click(screen.getByTestId('fts-drawer-axis-reset'));
    expect(getExcludeAxes()).toEqual([]);
  });

  it('شاخص ۱ب در دراور با دامنهٔ «بدون داده» و توضیح صادقانه می‌آید', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText(EXCLUDE_LABEL['1b'])).toBeInTheDocument());
    const toggle = screen.getByText(EXCLUDE_LABEL['1b']).closest('button');
    expect(toggle?.textContent).toContain('بدون داده');
    fireEvent.click(screen.getByText(EXCLUDE_LABEL['1b']));
    expect(getExcludeAxes()).toEqual(['1b']); // انتخاب می‌شود ولی طبق NO_ROW_FLAG حذفی نمی‌کند
  });

  it('انتخاب‌ها در payload ذخیرهٔ تنظیمات می‌آیند (کلید کانفیگ)', async () => {
    renderDrawer();
    await waitFor(() => expect(screen.getByText(EXCLUDE_LABEL['4'])).toBeInTheDocument());
    fireEvent.click(screen.getByText(EXCLUDE_LABEL['4']));
    fireEvent.click(screen.getByRole('button', { name: /ذخیره/ }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST');
      expect(post).toBeDefined();
      const body = JSON.parse((post![1] as RequestInit).body as string) as Record<string, unknown>;
      expect(body[EXCLUDE_CONFIG_KEY]).toEqual(['4']);
    });
  });
});
