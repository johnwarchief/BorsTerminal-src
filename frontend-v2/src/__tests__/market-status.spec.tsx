import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MarketStatusPage } from '@features/market/routes/MarketStatusPage';
import { usePhase } from '@features/market/api/usePhase';
import { useBoard } from '@features/market/api/useBoard';
import { useMarketSnapshot } from '@features/market/api/useMarketSnapshot';

vi.mock('@features/market/api/usePhase', () => ({ usePhase: vi.fn() }));
vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@features/market/api/useMarketSnapshot', () => ({ useMarketSnapshot: vi.fn() }));

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MarketStatusPage />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe('MarketStatusPage', () => {
  it('labels an official phase differently from a calendar guess', () => {
    vi.mocked(usePhase).mockReturnValue({ data: { status: 'ok', phase: 'continuous', label: 'بازار باز', official: true, phase_source: 'tsetcm_marketState', is_live: true }, isLoading: false, isError: false } as never);
    vi.mocked(useBoard).mockReturnValue({ data: { meta: { d_even: 20261028, last_sync: '12:00' }, live_count: 5, fossil_count: 2 }, isLoading: false, isError: false } as never);
    vi.mocked(useMarketSnapshot).mockReturnValue({ data: undefined, isLoading: false, isError: false } as never);
    mount();
    expect(screen.getByTestId('phase-label').textContent).toBe('بازار باز');
    expect(screen.getByTestId('phase-source').textContent).toContain('رسمی');
  });

  it('says unknown instead of guessing when phase is missing', () => {
    vi.mocked(usePhase).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
    vi.mocked(useBoard).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
    vi.mocked(useMarketSnapshot).mockReturnValue({ data: undefined, isLoading: false, isError: false } as never);
    mount();
    expect(screen.getByTestId('phase-label').textContent).toContain('نامعلوم');
  });
});
