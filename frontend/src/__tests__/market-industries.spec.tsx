// تست اسکرینر صنعت داغ: مرتب‌سازی ورود پول/درصد با fetch ماک‌شده
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IndustryScreener } from '@features/market/components/IndustryScreener';
import { topIndustriesByFlow, topIndustriesByPct, type IndustryRow } from '@features/market/api/useIndustries';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function r(over: Partial<IndustryRow> & { industry: string }): IndustryRow {
  return { symbols: 10, positive: 5, negative: 2, avg_pct: 1, value_b_toman: 100, flow_b_toman: 0, ...over } as IndustryRow;
}

const rows = [r({ industry: 'سیمان', flow_b_toman: 50, avg_pct: 3 }), r({ industry: 'فولاد', flow_b_toman: 400, avg_pct: 9 }), r({ industry: 'پتروشیمی', flow_b_toman: 500, avg_pct: 7 })];

describe('مرتب‌سازهای صنعت', () => {
  it('topIndustriesByFlow نزولی روی جریان و حداکثر n', () => {
    expect(topIndustriesByFlow(rows, 2).map((x) => x.industry)).toEqual(['پتروشیمی', 'فولاد']);
    expect(topIndustriesByFlow(null)).toEqual([]);
  });

  it('topIndustriesByPct نزولی روی درصد', () => {
    expect(topIndustriesByPct(rows, 3).map((x) => x.industry)).toEqual(['فولاد', 'پتروشیمی', 'سیمان']);
  });

  it('ردیف بدون عددِ سنجه حذف می‌شود', () => {
    const dirty = [r({ industry: 'بدون', flow_b_toman: null }), r({ industry: 'سالم', flow_b_toman: 5 })];
    expect(topIndustriesByFlow(dirty).map((x) => x.industry)).toEqual(['سالم']);
  });
});

describe('کامپوننت اسکرینر صنعت', () => {
  beforeEach(() => fetchMock.mockReset());

  function json(body: unknown): Response {
    return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
  }

  function renderScreener() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <IndustryScreener />
      </QueryClientProvider>,
    );
  }

  it('سه صنعت بر اساس ورود پول و تغییر حالت به درصد', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json({ status: 'ok', rows, leader: 'فولاد' })));
    renderScreener();
    await waitFor(() => expect(screen.getByText(/^فولاد/)).toBeInTheDocument());
    // پیش‌فرض: نزولی جریان -> پتروشیمی(500) > فولاد(400) > سیمان(50)
    const items = () => screen.getAllByRole('listitem').map((li) => li.textContent ?? '');
    expect(items()[0]).toMatch('پتروشیمی');
    expect(items()[1]).toMatch('فولاد');
    fireEvent.click(screen.getByRole('button', { name: 'بیشترین درصد' }));
    // نزولی درصد -> فولاد(9) > پتروشیمی(7) > سیمان(3)
    expect(items()[0]).toMatch('فولاد');
    expect(items()[2]).toMatch('سیمان');
  });

  it('خطا/نبود داده حالت بدون داده', async () => {
    fetchMock.mockImplementation(() => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) }));
    renderScreener();
    await waitFor(() => expect(screen.getByText('بدون داده')).toBeInTheDocument());
  });
});
