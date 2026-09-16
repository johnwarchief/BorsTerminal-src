// تست بازرس جریان حجم (P-02): بسته/صفر ارتفاع تا انتخاب سهم، سپس شیت کشویی
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VolumeFlow } from '@features/market/components/VolumeFlow';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function json(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function renderSheet(symbol: string, onClose?: () => void) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <VolumeFlow symbol={symbol} onClose={onClose} />
    </QueryClientProvider>,
  );
}

describe('بازرس جریان حجم (Side Sheet)', () => {
  beforeEach(() => fetchMock.mockReset());

  it('تا سطری انتخاب نشده، ارتفاع صفر/بسته است', () => {
    const { container } = renderSheet('');
    expect(screen.queryByTestId('volume-sheet')).not.toBeInTheDocument();
    expect(container.firstChild).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('با انتخاب نماد به‌صورت شیت راست باز می‌شود و دکمه بستن فراخوانی می‌شود', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        json({
          status: 'success',
          candles: [],
          volumes: [
            { time: '2026-01-01', value: 100, color: '#3b82f6' },
            { time: '2026-01-02', value: 200, color: '#ef4444' },
          ],
        }),
      ),
    );
    const onClose = vi.fn();
    renderSheet('شپنا', onClose);
    const sheet = await screen.findByTestId('volume-sheet');
    expect(sheet).toHaveAttribute('aria-label', 'بازرس جریان حجم شپنا');
    fireEvent.click(screen.getByRole('button', { name: 'بستن بازرس جریان حجم' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
