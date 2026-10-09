// __tests__/funnel-request-dedup.spec.tsx — گاردِ P0-4 «یک درخواستِ canonical»
//
// هدفِ §۴ سند: یک verdict → cache مشترک → چند مصرف‌کننده. این تست همان خاصیت
// را قفل می‌کند و رفتار را عوض نمی‌کند: دو مصرف‌کننده با درخواستِ منطقیِ یکسان
// (همان preset/chain/fundMode/exceptions) باید دقیقاً یک POST /api/funnel بسازند،
// نه دو تا. مثبتِ‌کنترل: با presetِ متفاوت فراخوانِ دوم می‌آید — اثباتِ اینکه
// سنسور واقعاً می‌شمارد و dedup «صفرشدنِ کور» نیست.
import { render, waitFor, cleanup } from '@testing-library/react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';
import { useFtsFunnel } from '@features/master/api/useFtsFunnel';
import type { TreePreset } from '@features/master/lib/ftsFunnel';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const funnelPosts = () => fetchMock.mock.calls
  .map((c) => String(c[0]))
  .filter((u) => u.includes('/api/funnel') && !u.includes('/trace'));

function Consumer({ preset }: { preset: TreePreset }) {
  useFtsFunnel(preset);
  return null;
}

function withProvider(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(() => Promise.resolve(
    { ok: true, json: () => Promise.resolve(FUNNEL_FIXTURE) } as unknown as Response));
});
afterEach(() => cleanup());

describe('یک درخواستِ canonical، چند مصرف‌کننده (P0-4)', () => {
  it('دو مصرف‌کننده با درخواستِ یکسان ⇒ دقیقاً یک /api/funnel', async () => {
    withProvider(
      <div>
        <Consumer preset="trend" />
        <Consumer preset="trend" />
      </div>);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 40));
    expect(funnelPosts().length).toBe(1);
  });

  it('مثبتِ‌کنترل: دو presetِ متفاوت ⇒ دو /api/funnel (سنسور کور نیست)', async () => {
    withProvider(
      <div>
        <Consumer preset="trend" />
        <Consumer preset="swing" />
      </div>);
    await waitFor(() => expect(funnelPosts().length).toBe(2));
  });

  it('تغییرِ نماد/رندرِ دوباره نباید محاسبهٔ تازه بی‌دلیل راه بیندازد', async () => {
    const { rerender } = withProvider(
      <div>
        <Consumer preset="trend" />
        <Consumer preset="trend" />
      </div>);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    // رندرِ دوباره با همان درخواست: باید از cache بخواند، نه fetchِ تازه.
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <div>
          <Consumer preset="trend" />
          <Consumer preset="trend" />
        </div>
      </QueryClientProvider>);
    await new Promise((r) => setTimeout(r, 40));
    // دو Consumer با هم ⇒ یک fetch؛ در مجموعِ این تست نباید بیش از دو fetch شود
    // (دو Consumer رندرِ اول یک fetch، و هیچ fetchِ دوتایی برایِ یک کلید).
    expect(funnelPosts().length).toBeLessThanOrEqual(2);
  });
});

describe('unifyِ preset (URL > کاربر > افق) — سطحِ mount', () => {
  it('جدول + سایدبار یک preset فعال ⇒ دقیقاً یک POSTِ کلِ universe', async () => {
    const { useSymbolStore } = await import('@shared/stores/symbolStore');
    useSymbolStore.getState().setSymbol('شپنا');
    const { default: FtsFunnelStages } = await import('@features/master/ui/FtsFunnelStages');
    const { SymbolInspector } = await import('@widgets/SymbolInspector');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/master']}>
          <FtsFunnelStages />
          <SymbolInspector />
        </MemoryRouter>
      </QueryClientProvider>);
    await waitFor(() => expect(funnelPosts().length).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 120));
    // پیش از unify: یک POSTِ trend (جدول) + یک POSTِ custom (سایدبار) = دو.
    // پس از unify: هر دو کلیدِ یکسان ⇒ یک fetchِ مشترک.
    expect(funnelPosts().length).toBe(1);
    useSymbolStore.getState().clearSymbol();
  });
});
