// __tests__/handover-selection.spec.tsx — بندِ اول مأموریتِ پروندۀ نماد:
// «جدول تحویل باید از یک فهرست صرف به محیطی برای انتخاب و اقدام روی نمادها تبدیل شود»
//
// چیزی که اثبات می‌شود (و هیچ‌کدام ازِ کدِ بک‌اند قابلِ گرفتن نیست):
//   ۱) انتخابِ تک و چند، با شمارِ دیدنی و بدونِ ردیفِ تکراری درِ فهرستِ انتخاب
//   ۲) «انتخاب همۀ نتایج فعلی» idempotent است — دو بار زدنش شمار را دو نمی‌کند
//   ۳) افزودنِ دسته‌ای به واچ‌لیست: تفکیکِ «افزوده‌شده» از «از قبل موجود» و
//      پاک‌نشدنِ انتخاب پس از عملیات (درخواستِ مالک)
//   ۴) «بررسی در برآیند» همان نمادِ انتخابی را می‌برد و **هیچ** داوریِ قیف را
//      عوض نمی‌کند — درخواستِ قیفِ پیش و پس از عملیات‌ها باید یکی باشد
import type { ReactElement } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import type { ApiPayload } from '@features/master/lib/funnelView';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { useScreenFilterStore } from '@shared/stores/screenFilterStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSelectedSymbolsStore } from '@shared/stores/selectedSymbolsStore';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { FUNNEL_FIXTURE, funnelCalls, installFunnelApi } from './fixtures/funnelApi';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 50;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number; estimateSize?: (i: number) => number }) => ({
      getTotalSize: () => opts.count * 29,
      getVirtualItems: () => Array.from({ length: Math.min(opts.count, WINDOW) },
                                        (_, i) => ({ key: i, index: i, start: i * 29 })),
    }),
  };
});

/** دو ردیفِ عبوری از تحویل: با یک ردیف، «چندتایی» اثبات نمی‌شود. */
function twoRowFixture(): ApiPayload {
  const p = structuredClone(FUNNEL_FIXTURE) as ApiPayload;
  const rows = p.entries?.handover ?? [];
  if (rows.length === 0) throw new Error('فیکسچرِ پایه ردیفِ تحویل ندارد');
  const second = { ...rows[0], symbol: 'زرشمان', name: 'زرشمان پارس', rank: 2 };
  //Clone تازه است، پس جایِ درجا نوشتن بی‌خطر است (بازسازیِ کلِ آبجکت نوع را
  // از Recordِ کامل می‌افتاد و tsc را می‌سوزاند).
  p.entries!.handover = [...rows, second];
  if (p.stages?.handover) p.stages.handover.matched = rows.length + 1;
  return p;
}

let restoreFunnel = () => {};
let restoreWatch = () => {};
const watchPosts: string[] = [];
/** واچ‌لیستِ سرورِ ساختگی: `existed` را بانک می‌گوید (upsert)، پس ردیفِ تکراری
 *  ساخته نمی‌شود و شمارۀ «از قبل موجود» از واقعیت می‌آید نه از کشِ فرانت. */
function installWatchApi(seed: string[] = []) {
  const have = new Set(seed.map(normalizeFa));
  const inner = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('/api/watchlist') && String(init?.method ?? 'GET') === 'POST') {
      const body = JSON.parse(String(init?.body ?? '{}')) as { symbol?: string };
      const symbol = String(body.symbol ?? '');
      watchPosts.push(symbol);
      const existed = have.has(normalizeFa(symbol));
      have.add(normalizeFa(symbol));
      return new Response(JSON.stringify({ status: 'success', count: have.size, existed }),
                          { status: 200, headers: { 'content-type': 'application/json' } });
    }
    return inner(input, init);
  };
  restoreWatch = () => { globalThis.fetch = inner; };
}

const renderAt = (ui: ReactElement, at = '/master?stage=handover&preset=custom') =>
  render(<MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter>);

async function ready() {
  renderAt(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: 0 } } })}>
      <FtsFunnelStages preset="custom" onPresetChange={() => {}} />
    </QueryClientProvider>,
  );
  // نوارِ عملیات از همان رندرِ اول هست (پیش از رسیدنِ پاسخِ قیف)؛ شاهدِ واقعی
  // رسیدنِ داده، ردیف‌هایِ خودِ جدول‌اند — وگرنه assertها رویِ جدولِ خالی می‌خورند.
  return waitFor(() => {
    const el = screen.getByTestId('funnel-stage-handover');
    if (!within(el).queryByTestId('select-box-فولاد')) throw new Error('ردیف‌ها نرسیده‌اند');
    return el;
  }, { timeout: 4000 });
}

beforeEach(() => {
  sessionStorage.clear();
  useFunnelPrefsStore.getState().reset();
  useFunnelPrefsStore.getState().resetToCanonical();
  useTapeStore.getState().resetFilters();
  useScreenFilterStore.getState().setLogic('and');
  useSelectedSymbolsStore.getState().clear();
  useSymbolStore.getState().clearSymbol();
  watchPosts.length = 0;
  restoreFunnel = installFunnelApi(twoRowFixture());
});

afterEach(() => { restoreFunnel(); restoreWatch(); });

describe('انتخاب از جدول تحویل', () => {
  it('هر ردیفِ عبوری جعبۀ انتخاب دارد؛ یک کلیک = یک نماد انتخاب‌شده', async () => {
    const hand = await ready();
    const box = within(hand).getByTestId('select-box-فولاد');
    fireEvent.click(box);
    expect(box).toHaveAttribute('aria-checked', 'true');
    expect(within(hand).getByTestId('funnel-selection-count').textContent)
      .toContain('۱ نماد انتخاب شده');
    // کلیکِ دوم همان نماد را برداشت می‌کند (سوییچ است، نه شمارنده)
    fireEvent.click(box);
    expect(within(hand).getByTestId('funnel-selection-count').textContent)
      .toContain('چیزی انتخاب نشده');
  });

  it('انتخاب چند نماد، و «انتخاب همۀ نتایج فعلی» بی‌ردیفِ تکراری', async () => {
    const hand = await ready();
    fireEvent.click(within(hand).getByTestId('select-box-فولاد'));
    fireEvent.click(within(hand).getByTestId('select-box-زرشمان'));
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(2);
    // «همه» رویِ انتخابِ جزئیِ قبلی می‌نشیند و چیزی را دوتا نمی‌کند
    fireEvent.click(within(hand).getByTestId('funnel-select-all'));
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(2);
    expect(within(hand).getByTestId('funnel-selection-count').textContent)
      .toContain('۲ در این جدول');
    fireEvent.click(within(hand).getByTestId('funnel-select-all'));
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(2);
  });

  it('افزودنِ دسته‌ای به واچ‌لیست: افزوده/از‌قبل‌موجود جدا شمرده می‌شود و انتخاب نمی‌سوزد', async () => {
    installWatchApi(['زرشمان']);          // یکی از دو از قبل در لیست است
    const hand = await ready();
    fireEvent.click(within(hand).getByTestId('funnel-select-all'));
    fireEvent.click(within(hand).getByTestId('funnel-bulk-watch'));
    await waitFor(() => expect(screen.getByTestId('funnel-bulk-result')).toBeInTheDocument());
    const msg = String(screen.getByTestId('funnel-bulk-result').textContent);
    expect(msg).toContain('افزوده شد: ۱');
    expect(msg).toContain('از قبل در واچ‌لیست: ۱');
    // نمادی که از قبل بود دوباره POST نمی‌شود؟ نه: upsert است و رکوردِ تکراری
    // درِ بانک ساخته نمی‌شود — آنچه رابط می‌گوید همان تفکیکِ صادق است.
    expect(watchPosts.sort()).toEqual(['زرشمان', 'فولاد'].sort());
    // رأیِ مالک: «انتخاب‌ها در زمان عملیات دسته‌ای از بین نروند»
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(2);
    expect(within(hand).getByTestId('funnel-selection-count').textContent)
      .toContain('۲ نماد انتخاب شده');
  });

  it('«بررسی در برآیند» نمادِ انتخابی را می‌برد و نتیجۀ قیف را تکان نمی‌دهد', async () => {
    installWatchApi([]);
    const hand = await ready();
    fireEvent.click(within(hand).getByTestId('select-box-فولاد'));
    const before = JSON.stringify(funnelCalls);
    fireEvent.click(within(hand).getByTestId('funnel-bulk-watch'));
    await waitFor(() => expect(screen.getByTestId('funnel-bulk-result')).toBeInTheDocument());
    fireEvent.click(within(hand).getByTestId('funnel-bulk-review'));
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
    // عملیاتِ دسته‌ای نباید دورِ داوریِ تازه‌ای بسازد یا چیزی درِ درخواست عوض کند
    expect(JSON.stringify(funnelCalls)).toBe(before);
  });
});
