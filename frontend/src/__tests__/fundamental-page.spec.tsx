// تست صفحه تحلیل بنیادی: P/NAV هلدینگ‌ها + حذف مقایسه با گروه «سایر»
// هلدینگ (=سرمایه‌گذاری) نباید با میانهٔ P/E گروه‌های تولیدی مقایسه شود؛
// تا انتشار NAV از بک‌اند، پنل P/NAV با جانشین EPS نمایش می‌یابد.
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import FundamentalPage from '@features/fundamental/routes/FundamentalPage';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function mockJson(url: string): unknown {
  let u = url.split('?')[0];
  try {
    u = decodeURIComponent(u);
  } catch {
    /* URL انکود نشده */
  }
  if (u === '/api/screener') {
    return {
      status: 'success',
      count: 2,
      data: [
        {
          symbol: 'وغدير',
          name: 'سرمايه‌گذاري‌غدير(هلدينگ',
          sector_name: 'سایر',
          score: 2,
          eps_data_gap: true,
          excluded: false,
        },
        {
          symbol: 'شپنا',
          name: 'پالایش نفت اصفهان',
          sector_name: 'فراورده‌هاي نفتي',
          score: 4,
          eps_data_gap: false,
          excluded: false,
        },
      ],
      thresholds: {},
      max_score: 5,
    };
  }
  if (u === '/api/market') {
    return {
      status: 'success',
      data: [
        { symbol: 'وغدير', sector_name: 'سایر', pe: 11.3 },
        { symbol: 'شپنا', sector_name: 'فراورده‌هاي نفتي', pe: 5.2 },
      ],
    };
  }
  if (u === '/api/fundamental/وغدير/quarters') {
    return { status: 'success', symbol: 'وغدير', count: 0, quarters: [] };
  }
  if (u === '/api/fundamental/وغدير') {
    return {
      status: 'success',
      symbol: 'وغدير',
      sector: 'سایر',
      score: 2,
      verdict: 'WATCH',
      pricing_mode: 'neutral',
      passes: { '2_eps_trend': false },
      profile: { kind: 'production', volume_applicable: true },
      metrics: {
        eps_series: [3077, 1866, 1888],
        eps_slots: ['1402', '1403', '1404'],
        eps_partial: false,
        gross_margin: 21.2,
        sales_to_mcap: 1.12,
        profit_potential_pct: 23.7,
        mcap_stale: false,
      },
      data_gaps: [],
      history: [],
      fs_count: 1,
      excluded: false,
      exclusion_reasons: [],
    };
  }
  if (u === '/api/fts/config') return { status: 'success', config: null };
  return { status: 'success', data: [] };
}

function renderPage(symbol: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/fundamental/${encodeURIComponent(symbol)}`]}>
        <Routes>
          <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('صفحه تحلیل بنیادی — هلدینگ‌ها', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockJson(typeof url === 'string' ? decodeURIComponent(url) : '')),
      } as unknown as Response),
    );
  });

  it('هلدینگ: پنل «نیازمند ارزیابی پرتفوی هلدینگ (N/A)» جای SectorPePanel می‌نشیند — بدون P/NAV ساختگی', async () => {
    renderPage('وغدير');
    await waitFor(() => expect(screen.getByTestId('holding-pnav-panel')).toBeInTheDocument());
    // عنوان P/E در برابر صنعت برای هلدینگ رندر نمی‌شود
    expect(screen.queryByText(/P\/E در برابر صنعت/)).not.toBeInTheDocument();
    const panel = screen.getByTestId('holding-pnav-panel');
    // برچسب رسمی N/A و علت آن
    expect(panel.textContent).toContain('نیازمند ارزیابی پرتفوی هلدینگ (N/A)');
    // هیچ نسبت جانشینی (EPS به‌جای NAV) محاسبه/نمایش داده نمی‌شود
    expect(panel.textContent).not.toContain('P/NAV ≈');
    expect(panel.textContent).not.toContain('جانشین EPS');
    expect(panel.textContent).not.toContain('۱۸۸۸');
    expect(panel.textContent).not.toContain('۱۱.۳');
  });

  it('هلدینگ بدون دادهٔ EPS: همان برچسب N/A می‌ماند (بدون undefined/NaN)', async () => {
    fetchMock.mockImplementation((url: string) => {
      const base = mockJson(typeof url === 'string' ? decodeURIComponent(url) : '') as Record<string, unknown>;
      if ((typeof url === 'string' ? decodeURIComponent(url) : '').startsWith('/api/fundamental/وغدير') && !url.includes('quarters')) {
        (base as { metrics: Record<string, unknown> }).metrics = {};
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(base) } as unknown as Response);
    });
    renderPage('وغدير');
    await waitFor(() => expect(screen.getByTestId('holding-pnav-panel')).toBeInTheDocument());
    const panel = screen.getByTestId('holding-pnav-panel');
    expect(panel.textContent).toContain('N/A');
    expect(panel.textContent).not.toContain('undefined');
    expect(panel.textContent).not.toContain('NaN');
  });
});
