// نگهبانِ race درِ پولینگِ «دیتابیس کدال» (کار #44، دورِ E).
// دو حالتی که پیش از این هیچ محافظی نداشتند:
//  ۱) ترتیبِ رسیدن با ترتیبِ زدن یکی نیست: ریتم ۲ ثانیه است و درخواستِ پیشین هنوز
//     در راه است؛ پاسخِ کهنه («در حال دریافت… ۳۰٪») جایِ پاسخِ تازه («پایان») را
//     می‌گرفت و دکمه تا پایانِ TTL قفل می‌ماند.
//  ۲) افکت به خودِ `dbUpd` وابسته بود ⇒ هر پاسخ آن را از نو می‌ساخت؛ و نوشتنِ state
//     پس ازِ رفتنِ صفحه محافظ نداشت.
// راهِ سنجش: `setInterval` جعل می‌شود تا تیک‌ها را خودِ تست بزند (نه صبرِ واقعی)،
// و پاسخ‌ها deferred می‌شوند تا ترتیبِ رسیدن درِ دستِ تست باشد.
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';

import FundamentalPage from '@features/fundamental/routes/FundamentalPage';
import { useSymbolStore } from '@shared/stores/symbolStore';

type DbStatus = { running: boolean; stage: string; percent?: number; detail?: string; error?: string };
type Deferred = { p: Promise<{ db: DbStatus }>; resolve: (v: { db: DbStatus }) => void };

function deferred(): Deferred {
  let resolve!: (v: { db: DbStatus }) => void;
  const p = new Promise<{ db: DbStatus }>((res) => { resolve = res; });
  return { p, resolve };
}

const queue: Deferred[] = [];
let statusCalls = 0;
let screenerCalls = 0;
let ticks: Array<() => void> = [];
const fetchMock = vi.fn();

function mockBody(url: string): unknown {
  const u = decodeURIComponent(url.split('?')[0]);
  if (u === '/api/screener') {
    screenerCalls += 1;
    return {
      status: 'success', count: 1, thresholds: {}, max_score: 5,
      data: [{
        symbol: 'شپنا', name: 'پالایش نفت اصفهان', sector_name: 'فراورده‌هاي نفتي',
        score: 4, applicable: true, verdict: 'STRONG', excluded: false,
        passes: { 'ال': true, 'ب': true, 'پ': true, 'ت': true, 'ث': true },
      }],
    };
  }
  if (u === '/api/sync/codal/db-status') {
    statusCalls += 1;
    // نخستینِ فراخوانی «خواندنِ یک‌بارِ وضعیتِ درِ جریان» است (بازگشتِ کاربر وسطِ
    // دانلود) — آن را بی‌کنترل پاسخ می‌دهیم تا صفِ تست فقط تیک‌هایِ polling باشد.
    if (statusCalls === 1) return { db: { running: false, stage: 'idle' } };
    const d = deferred();
    queue.push(d);
    return d.p;                     // ترتیبِ حل‌شدن درِ دستِ تست
  }
  if (u === '/api/sync/codal/db-download') return { status: 'ok', started: true };
  return { status: 'success', data: [] };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/fundamental/']}>
        <Routes>
          <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const button = () => screen.getByTestId('fts-db-update');

/** یکِ تیکِ polling، با flushِ promiseهایِ باز */
async function tick() {
  await act(async () => { ticks[ticks.length - 1]?.(); await Promise.resolve(); });
}
async function settle() {
  // چند دورِ microtask + یکِ macrotask: برایِ نشستنِ پاسخِ Query لازم است
  for (let i = 0; i < 4; i++) {
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  }
}
async function resolveNext(i: number, db: DbStatus) {
  await act(async () => { queue[i].resolve({ db }); await Promise.resolve(); await Promise.resolve(); });
}

beforeEach(() => {
  vi.clearAllMocks();
  queue.length = 0;
  ticks = [];
  statusCalls = 0;
  screenerCalls = 0;
  useSymbolStore.getState().setSymbol('');
  // ریتمِ ۲ ثانیه‌ای را صبر نمی‌کنیم: callbackِ interval را می‌گیریم و خودمان می‌زنیم.
  vi.spyOn(globalThis, 'setInterval').mockImplementation(((fn: () => void) => {
    ticks.push(fn);
    return 1 as unknown as ReturnType<typeof setInterval>;
  }) as unknown as typeof setInterval);
  fetchMock.mockImplementation((url: unknown) => {
    const body = mockBody(typeof url === 'string' ? url : String(url));
    return Promise.resolve({
      ok: true, status: 200,
      json: () => (body instanceof Promise ? body : Promise.resolve(body)),
    } as unknown as Response);
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => { vi.restoreAllMocks(); });

describe('پولینگِ وضعیتِ دیتابیس کدال', () => {
  it('پاسخِ کهنه جایِ پاسخِ تازه را نمی‌گیرد (سنجشِ race)', async () => {
    renderPage();
    await settle();
    fireEvent.click(button());
    expect(button().textContent).toContain('در حال دریافت');

    await tick();                        // درخواستِ ۱ — کند می‌رسد
    await tick();                        // درخواستِ ۲ — زود می‌رسد
    expect(queue).toHaveLength(2);

    await resolveNext(1, { running: false, stage: 'done' });
    await resolveNext(0, { running: true, stage: 'downloading', percent: 30 });

    // پایان سرِ جایش می‌ماند؛ «۳۰٪»ِ کهنه رویِ آن نمی‌نشیند و دکمه آزاد است
    expect(button().textContent).not.toContain('۳۰');
    expect(button().textContent).toContain('دیتابیس کدال');
    expect(button().hasAttribute('disabled')).toBe(false);
  });

  it('جریانِ معمولی: progress ⇒ busy و پایان ⇒ غربالگری دوباره خوانده می‌شود', async () => {
    renderPage();
    await settle();
    const firstScreener = screenerCalls;
    fireEvent.click(button());

    await tick();
    await resolveNext(0, { running: true, stage: 'merging' });
    expect(button().textContent).toContain('در حال ادغام');

    await tick();
    await resolveNext(1, { running: false, stage: 'done' });
    expect(button().textContent).toContain('دیتابیس کدال');
    expect(screenerCalls).toBeGreaterThan(firstScreener);
  });

  it('با رفتنِ صفحه حلقه بسته می‌شود و پاسخِ درِ راه بی‌خطا می‌افتد', async () => {
    // سنجشِ واقعیِ «write after unmount» درِ React 18 هشدارِ no-op نیست؛ چیزی که
    // گاردِ `alive` را لازم می‌کند نوشتنِ بی‌صاحبِ state است، پس دو چیز دیدنی
    // می‌ماند: clearIntervalِ همان حلقه، و نبودِ هر خطا/هشدارِ React.
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    let cleared = 0;
    vi.spyOn(globalThis, 'clearInterval').mockImplementation((() => { cleared += 1; }) as never);
    const { unmount } = renderPage();
    await settle();
    fireEvent.click(button());
    await tick();
    unmount();
    expect(cleared).toBeGreaterThan(0);
    await resolveNext(0, { running: false, stage: 'done' });
    expect(err.mock.calls.filter((c) => String(c[0]).includes('Cannot update'))).toHaveLength(0);
    err.mockRestore();
  });
});
