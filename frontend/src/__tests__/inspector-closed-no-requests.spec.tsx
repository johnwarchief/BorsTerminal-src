// __tests__/inspector-closed-no-requests.spec.tsx — دراورِ بسته هیچ پرسشی نمی‌زند
//
// چرا لازم شد: سنجشِ زندهٔ ۱۳۶×۷۶۸ رویِ «وضعیت بازار» نشان داد اولینِ درخواستِ
// mstatِ خودِ صفحه درِ ۴٬۲۷ms آغاز می‌شود، چون پوسته پیشِ آن سه پرسشِ سنگین
// (`/api/market`، `/api/funnel`، `/api/screener`) را از `SymbolInspector`ی می‌فرستد
// که کاربر هرگز باز نکرده است. اینِ تست همان را قفل می‌کند؛ مثبتِ‌کنترل لازم است
// چون «صفرِ کور» (کوئری هرگز وصل نیست) همان تعدادِ درخواست را می‌دهد.
import { render, waitFor, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const heavy = () => fetchMock.mock.calls
  .map((c) => String(c[0]))
  .filter((u) => ['/api/funnel', '/api/screener', '/api/market'].some((p) => u.includes(p)));

function mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <MemoryRouter initialEntries={['/market-status']}>
      <QueryClientProvider client={qc}>
        <SymbolInspector />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(() => Promise.resolve(
    { ok: true, json: () => Promise.resolve(FUNNEL_FIXTURE) } as unknown as Response));
  useSymbolStore.setState({ symbol: '' });
});
afterEach(() => cleanup());

describe('پنجرۀِ جزئیاتِ بسته', () => {
  it('بی‌نماد ⇒ نه تابلو، نه قیف، نه اسکرینر از پوسته پرسیده می‌شود', async () => {
    mount();
    await new Promise((r) => setTimeout(r, 120));
    expect(heavy()).toEqual([]);
  });

  it('مثبتِ‌کنترل: باِ نمادِ انتخاب‌شده همان پرسش‌ها می‌روند (سنسور کور نیست)', async () => {
    useSymbolStore.setState({ symbol: 'فولاد' });
    mount();
    await waitFor(() => expect(heavy().length).toBeGreaterThan(0), { timeout: 3000 });
    expect(heavy().join(' ')).toContain('/api/funnel');
  });
});
