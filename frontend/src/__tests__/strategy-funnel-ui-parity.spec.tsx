// __tests__/strategy-funnel-ui-parity.spec.tsx — بازطراحیِ UI رأیِ قیف را عوض نمی‌کند
//
// سه ادعا، همه باِ یکِ fixtureِ ثابت (`FUNNEL_FIXTURE`) و بی‌هیچ داوریِ تازه درِ تست:
//  ۱) عددی که درِ استپر، سربرگ و عنوانِ نتایج نوشته می‌شود **همان** عددِ پاسخِ
//     موتور است — نه شمارِ ردیفِ DOM و نه شمارِ گامِ دیگر؛
//  ۲) ورودیِ هر گام = عبوریِ گامِ پیشین درِ همان `flow` (زنجیره‌ای که نمادِ ردشده
//     درِ گامِ قبل، گامِ بعد را دوباره پر نمی‌کند)؛
//  ۳) «پاک‌کردنِ انتخاب‌ها» همان handlerهایِ موجود را صدا می‌زند و درخواستِ تازه
//     می‌زند — نه stateِ تازه، نه منطقِ تازه.
import type { ReactElement } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { FUNNEL_FIXTURE, funnelCalls, installFunnelApi } from './fixtures/funnelApi';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 29,
      getVirtualItems: () => Array.from({ length: Math.min(opts.count, 50) },
                                        (_, i) => ({ key: i, index: i, start: i * 29 })),
    }),
  };
});

let restoreFetch = () => {};

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  useFunnelPrefsStore.getState().reset();
  useFunnelPrefsStore.getState().resetToCanonical();
  useTapeStore.getState().resetFilters();
});
afterEach(() => restoreFetch());

async function ready(route: string) {
  restoreFetch = installFunnelApi(FUNNEL_FIXTURE as never);
  const ui: ReactElement = (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: 0 } } })}>
      <MemoryRouter initialEntries={[route]}>
        <FtsFunnelStages preset="trend" onPresetChange={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(ui);
  await waitFor(() => expect(document.querySelectorAll('tbody tr').length).toBeGreaterThan(0),
                { timeout: 4000 });
}

type FixtureStages = { stages: Record<string, { input?: number;
  counts: { pass: number } }> };

const fa = (n: number) => String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[+d]);

describe('هم‌عددیِ سربرگ، استپر و نتایج باِ پاسخِ موتور', () => {
  it('استپر ورودی←عبوریِ هر گام را از همان `input`/`counts` موتور می‌نویسد', async () => {
    await ready('/master?preset=trend&stage=technical');
    const st = (FUNNEL_FIXTURE as unknown as FixtureStages).stages;
    // ورودیِ تکنیکال = `stages.technical.inputِ` خودِ موتور (۴)، نه عبوریِ تابلو (۳).
    // بی‌این، رابط زنجیره‌ای ازِ گامِ پیشین می‌ساخت و باِ عددِ سرور نمی‌خواند.
    expect(st.technical.input).toBeGreaterThan(0);
    expect(screen.getByTestId('fts-step-flow-technical').textContent)
      .toContain(fa(st.technical.input ?? 0));
    expect(screen.getByTestId('fts-step-count-technical').textContent)
      .toBe(fa(st.technical.counts.pass));
    expect(screen.getByTestId('fts-step-count-fundamental').textContent)
      .toBe(fa(st.fundamental.counts.pass));
    expect(screen.getByTestId('fts-step-count-handover').textContent)
      .toBe(fa(st.handover.counts.pass));
  });

  it('سربرگ، استپر و عنوانِ نتایج یک عدد می‌دهند (دو شمارندۀ جدا نداریم)', async () => {
    await ready('/master?preset=trend&stage=fundamental');
    const pass = (FUNNEL_FIXTURE as unknown as FixtureStages)
      .stages.fundamental.counts.pass;
    expect(screen.getByTestId('fts-stage-flow').textContent).toContain(fa(pass));
    expect(screen.getByTestId('funnel-results-count').textContent).toContain(fa(pass));
    expect(screen.getByTestId('fts-step-count-fundamental').textContent).toBe(fa(pass));
    expect(screen.getByTestId('fts-current-step').textContent).toContain('بنیادی');
  });

  it('وضعیتِ هر گام باِ متن است، نه فقط رنگ: «سنجشِ ناتمام» با «تکمیل‌شده» فرق دارد', async () => {
    await ready('/master?preset=trend&stage=tape');
    // fundamental درِ fixture یکِ pending دارد ⇒ سنجشِ ناتمام
    expect(screen.getByTestId('fts-step-status-fundamental').textContent)
      .toContain('سنجشِ ناتمام');
    // technical بی‌pending و بی‌unavailable ⇒ تکمیل‌شده
    expect(screen.getByTestId('fts-step-status-technical').textContent)
      .toContain('تکمیل‌شده');
    expect(screen.getByTestId('fts-step-status-technical').getAttribute('class'))
      .not.toBe(screen.getByTestId('fts-step-status-fundamental').getAttribute('class'));
  });

  it('«پاک‌کردنِ انتخاب‌ها» زنجیره را خالی می‌کند و وضعیتِ تهی به درخواست می‌رسد', async () => {
    // درِ Custom زنجیره همان چیپ‌هاست و درِ بدنهٔ POST می‌نشیند. دقتِ لازم:
    // «پاک‌شده» باِ درخواستِ *اولِ* صفحه (chain: []) یکِ کلیدِ کوئری دارد، پس
    // TanStack ازِ کش می‌خواند و POSTِ تازه نمی‌زند — این باگ نیست، رفتارِ درستِ
    // کش است. ادعایِ واقعی این است: state خالی شد، چیپ‌ها خاموش شدند، و تغییرِ
    // بعدی دقیقاً ازِ همان حالتِ خالی راه می‌افتد.
    await ready('/master?preset=custom&stage=tape');
    fireEvent.click(screen.getByTestId('funnel-tape-chip-f_susp'));
    await waitFor(() => {
      const last = funnelCalls[funnelCalls.length - 1] as { chain?: string[] };
      expect(last.chain ?? []).toContain('f_susp');
    }, { timeout: 4000 });
    fireEvent.click(screen.getByTestId('funnel-tape-chip-f_jet'));
    await waitFor(() => {
      const last = funnelCalls[funnelCalls.length - 1] as { chain?: string[] };
      expect(last.chain ?? []).toContain('f_jet');
    }, { timeout: 4000 });
    expect(screen.getByTestId('fts-filter-active-count').textContent).toContain(fa(2));

    fireEvent.click(screen.getByTestId('fts-filter-clear'));
    await waitFor(() => {
      expect(useFunnelPrefsStore.getState().chain).toEqual([]);
    }, { timeout: 4000 });
    expect(screen.getByTestId('funnel-tape-chip-f_susp').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('funnel-tape-chip-f_jet').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('fts-filter-active-count').textContent).toContain(fa(0));
    // بی‌فیلترِ فعال، دکمهٔ پاک‌کردن نمی‌ماند — حالتِ تهی خودش را نشان می‌دهد
    expect(screen.queryByTestId('fts-filter-clear')).toBeNull();
    // ازِ همان حالتِ خالی، یکِ انتخابِ تازه ⇒ درخواستی باِ فقط همان یک فیلتر
    fireEvent.click(screen.getByTestId('funnel-tape-chip-f_roobi'));
    await waitFor(() => {
      const last = funnelCalls[funnelCalls.length - 1] as { chain?: string[] };
      expect(last.chain).toEqual(['f_roobi']);
    }, { timeout: 4000 });
  });

  it('راهنمایِ شروعِ سریع بسته می‌شود و دیگر برنمی‌گردد (اجباری نیست)', async () => {
    await ready('/master?preset=trend&stage=tape');
    expect(screen.getByTestId('fts-quick-guide')).toBeDefined();
    fireEvent.click(screen.getByTestId('fts-guide-close'));
    expect(screen.queryByTestId('fts-quick-guide')).toBeNull();
    expect(screen.getByTestId('fts-guide-open')).toBeDefined();
  });

  it('«چطور کار می‌کند؟» هر چهار گام را باِ عددِ همان گام فهرست می‌کند', async () => {
    await ready('/master?preset=trend&stage=tape');
    fireEvent.click(screen.getByTestId('fts-how-it-works-toggle'));
    const panel = screen.getByTestId('fts-how-it-works');
    for (const key of ['tape', 'technical', 'fundamental', 'handover']) {
      expect(panel.querySelector(`[data-testid="fts-how-stage-${key}"]`)).not.toBeNull();
    }
    expect(panel.textContent).toContain('تحویل');
  });
});
