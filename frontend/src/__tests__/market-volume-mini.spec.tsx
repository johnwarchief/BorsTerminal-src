// تست مینی‌چارت جریان حجم (P-03): بدون داده صادقانه + هایلایت پنجره‌های FTS
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  FTS_WINDOWS,
  MARKET_CLOSE,
  MARKET_OPEN,
  VolumeFlowMini,
  inFtsWindow,
} from '@features/market/components/VolumeFlowMini';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function json(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function renderMini(symbol: string, compact = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <VolumeFlowMini symbol={symbol} compact={compact} />
    </QueryClientProvider>,
  );
}

describe('پنجره‌های حساس FTS', () => {
  it('بازهٔ معاملات و دو پنجرهٔ FTS', () => {
    expect(MARKET_OPEN).toBe('08:45');
    expect(MARKET_CLOSE).toBe('12:30');
    expect(FTS_WINDOWS).toEqual([
      ['09:00', '09:30'],
      ['12:00', '12:30'],
    ]);
  });

  it('inFtsWindow فقط داخل پنجره‌ها درست است', () => {
    expect(inFtsWindow('09:00')).toBe(true);
    expect(inFtsWindow('09:15')).toBe(true);
    expect(inFtsWindow('09:30')).toBe(true);
    expect(inFtsWindow('12:15')).toBe(true);
    expect(inFtsWindow('10:00')).toBe(false);
    expect(inFtsWindow('08:45')).toBe(false);
    expect(inFtsWindow('13:00')).toBe(false);
  });
});

describe('مینی‌چارت جریان حجم', () => {
  beforeEach(() => fetchMock.mockReset());

  it('بدون نماد انتخابی چیزی رندر نمی‌شود', () => {
    const { container } = renderMini('');
    expect(container.firstChild).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('بودن داده ⇒ میله‌ها با هایلایت پنجرهٔ FTS', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        json({
          status: 'success',
          buckets: [
            { t: '09:15', vol: 100, dir: 'up' },
            { t: '10:00', vol: 50, dir: 'down' },
            { t: '12:15', vol: 200, dir: 'up' },
          ],
        }),
      ),
    );
    renderMini('شپنا');
    expect(await screen.findByTestId('volume-mini-chart')).toBeInTheDocument();
    expect(screen.getByTestId('volume-mini-bar-09:15')).toHaveAttribute('data-fts-window', 'true');
    expect(screen.getByTestId('volume-mini-bar-12:15')).toHaveAttribute('data-fts-window', 'true');
    expect(screen.getByTestId('volume-mini-bar-10:00')).not.toHaveAttribute('data-fts-window');
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/market/intraday/');
  });

  it('نبود اندپوینت/داده ⇒ «بدون داده» صادقانه (بدون mock)', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response),
    );
    renderMini('شپنا');
    expect(await screen.findByTestId('volume-mini-empty')).toHaveTextContent('بدون داده');
    expect(screen.queryByTestId('volume-mini-chart')).not.toBeInTheDocument();
  });

  it('پاسخ خالی (بدون bucket) هم «بدون داده» است', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(json({ status: 'success', buckets: [] })));
    renderMini('شپنا');
    expect(await screen.findByTestId('volume-mini-empty')).toBeInTheDocument();
  });
});
