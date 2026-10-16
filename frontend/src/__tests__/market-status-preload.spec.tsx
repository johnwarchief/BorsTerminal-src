// تستِ پیش‌خوانیِ صفحۀِ اولِ «وضعیت بازار» (فاز G، بندِ ۵)
//
// دو ادعا که بی‌اینِ آزمون قابلِ اعتماد نیست:
//  ۱) پیش‌خوانیِ route درخواستِ *اضافه* نمی‌سازد: کلید ازِ خودِ isِ hook می‌آید،
//     پسِ کامپوننت درِ همانِ پرسشِ در حالِ جریان شرکت می‌کند.
//  ۲) تاِ احرازِ هویت انجام نشده، هیچِ پرسشی ازِ اینِ route بیرون نمی‌رود
//     (پیش‌خوانیِ بی‌هویت یعنی بارِ سرور برایِ کسی که صفحه را نمی‌بیند).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, renderHook, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from '@app/layouts/AppShell';
import { useAuthStore } from '@shared/stores/authStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { preloadMarketStatusFirstScreen } from '@features/market/lib/preloadMarketStatusFirstScreen';
import { useMstatHistogram } from '@features/market/api/useMarketStatusFeed';
import { useMstatIndexCards } from '@features/market/api/useMarketPanels';
import { mainRoutes } from '../routes';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const urls = () => fetchMock.mock.calls.map((c) => String(c[0]));
const countOf = (frag: string) => urls().filter((u) => u.includes(frag)).length;

beforeEach(() => {
  fetchMock.mockReset();
  // `{ status: 'ok' } } برایِ هر دو قراردادِ mstat معتبر است (بقیه nullish).
  fetchMock.mockImplementation(() => Promise.resolve(
    { ok: true, status: 200, json: async () => ({ status: 'ok' }) } as unknown as Response,
  ));
  localStorage.clear();
  useSymbolStore.getState().clearSymbol();
  useAuthStore.setState({ isAuthenticated: true });
});

function wrapper(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const fresh = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('preloadMarketStatusFirstScreen', () => {
  it('به‌ازایِ هرِ پنل، دقیقاً یکِ پرسش می‌فرستد (دو بارِ صدازدن = دو پرسش نیست)', async () => {
    const qc = fresh();
    preloadMarketStatusFirstScreen(qc);
    preloadMarketStatusFirstScreen(qc);
    await waitFor(() => expect(qc.getQueryData(['mstat-indexcards', 30])).toBeTruthy());
    expect(countOf('/api/mstat/indexcards')).toBe(1);
    expect(countOf('/api/mstat/histogram')).toBe(1);
  });

  it('isِ خودِ صفحه درِ همانِ پرسش شرکت می‌کند، نه درِ پرسشِ دوم', async () => {
    const qc = fresh();
    preloadMarketStatusFirstScreen(qc);
    const { result } = renderHook(
      () => ({ cards: useMstatIndexCards(), histo: useMstatHistogram() }),
      { wrapper: wrapper(qc) },
    );
    await waitFor(() => {
      expect(result.current.cards.data).toBeTruthy();
      expect(result.current.histo.data).toBeTruthy();
    });
    expect(countOf('/api/mstat/indexcards')).toBe(1);
    expect(countOf('/api/mstat/histogram')).toBe(1);
  });

  it('کلیدِ پیش‌خوانی باِ کلیدِ is یکی است (اگرِ یکی عوض شود، اینِ سطر قرمز می‌شود)', () => {
    const qc = fresh();
    preloadMarketStatusFirstScreen(qc);
    expect(qc.getQueryCache().find({ queryKey: ['mstat-indexcards', 30] })).toBeTruthy();
    expect(qc.getQueryCache().find({ queryKey: ['mstat-histogram', 'all'] })).toBeTruthy();
  });
});

describe('AppShell — درِوازۀِ پیش‌خوانی', () => {
  function renderApp(initial: string, client: QueryClient) {
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[initial]}>
          <Routes>
            <Route path="/" element={<AppShell />}>
              {mainRoutes.map((r) => (
                <Route key={r.path} path={r.path || undefined} index={!r.path} element={r.element} />
              ))}
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it('رویِ «وضعیت بازار»، کارتِ شاخص ازِ پوسته پیش‌خوانی می‌شود', async () => {
    renderApp('/market-status', fresh());
    await waitFor(() => expect(countOf('/api/mstat/indexcards')).toBe(1), { timeout: 4000 });
    expect(countOf('/api/mstat/histogram')).toBe(1);
  });

  it('بی‌احرازِ هویت، هیچِ پرسشِ mstat ازِ اینِ route نمی‌رود', async () => {
    useAuthStore.setState({ isAuthenticated: false });
    renderApp('/market-status', fresh());
    await waitFor(() => expect(screen_login()).toBeTruthy());
    expect(countOf('/api/mstat/')).toBe(0);
  });

  it('درِ صفحۀِ دیگر، کارِ «وضعیت بازار» پیش‌خوانی نمی‌شود', async () => {
    renderApp('/master', fresh());
    await new Promise((r) => setTimeout(r, 150));
    expect(countOf('/api/mstat/indexcards')).toBe(0);
    expect(countOf('/api/mstat/histogram')).toBe(0);
  });
});

const screen_login = () => document.querySelector('input[type="password"]');
