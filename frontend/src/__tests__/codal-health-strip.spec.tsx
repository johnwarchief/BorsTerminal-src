// __tests__/codal-health-strip.spec.tsx -- نوارِ سلامتِ خطِ کدال (بندِ ۷ مأموریتِ ۱۴۰۵-۰۷-۲۳)
//
// چه چیزی را گلوگاه می‌کند:
//  ۱) پنل فقط **همان چیزی** را می‌گوید که پاسخِ `/api/sync/codal/pipeline` دارد
//  ۲) خانۀ `null` هیچ‌وقت صفر نمی‌شود («ثبت نشده» ≠ «صفر بار»)
//  ۳) ارقام فارسی‌اند (قواعدِ رابط: `toFaDigits`)
//  ۴) با عوض‌شدنِ `data_epoch` کشِ کارت و غربالگری باطل می‌شود — و درِ اولین
//     خواندنِ نشست **نمی‌شود** (بی‌این هر ورودِ تازه به تب، کلِ کارت‌ها را
//     دوباره از سرور می‌خواهد)
//  ۵) پاسخِ خطا (`status:'error'` با HTTP 200) پنل را «نرسید» می‌کند، نه «سالم»
//  ۶) دربۀ آفلاین فقط وقتی دیده می‌شود که واقعاً روشن باشد
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CodalHealthStrip } from '@features/fundamental/components/CodalHealthStrip';

/** پاسخِ mock درِ یکِ آبجکتِ `hoisted` می‌نشیند: `vi.mock` پیش از بدنهٔ فایل
 *  بالا می‌آید، پس خواندنِ متغیرِ ماژولی داخلِ factory به TDZ می‌خورد؛
 *  `vi.resetModules()` هم رشتهٔ mock را از آنچه کامپوننت وارد کرده جدا می‌کند —
 *  همان چیزی که باعث شد پنل «نرسید» بگوید در حالی که fixture فرستاده شده بود.
 */
const state = vi.hoisted(() => ({ payload: null as unknown }));

vi.mock('@shared/api/http', () => ({
  http: vi.fn(() => Promise.resolve(state.payload)),
  HttpError: class extends Error {},
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function payload(over: Record<string, any> = {}) {
  return {
    queue: { queued: 7, running: 1, done: 3, empty: 0, failed: 2, unresolved: 1,
             total: 10496, legacy: 10496, retryable: 0 },
    instruments: { ledger: 4, present: 3, absent: 0, removed: 0, ambiguous: 1,
                   no_publisher: 0, no_fundamental: 41 },
    dirty_symbols: 5,
    incomplete_extractions: 12,
    undated_notices: 3,
    data_epoch: '8723|8723',
    last_data_update: '2026-10-14 06:00:00',
    last_successful_sync: '2026-10-14 06:00:00',
    last_attempt: '2026-10-14 06:01:00',
    checked_at: '2026-10-14 07:00:00',
    offline_gate: false,
    worker: { running: true, owner: 'app-1', started_at: '2026-10-14 05:00:00',
              cycles: 9, last: '2026-10-14 06:00:00', last_error: null },
    lock: { held: true, owner: 'app-1', heartbeat_at: '2026-10-14 06:59:00', note: null },
    catchup: { gap_seconds: 120, never_synced: false, queued: 7, failed: 2 },
    cadence: { at: '2026-10-14 07:01:00', seconds: 60, reason: 'discovery-due' },
    ...over,
  };
}

function renderStrip(qc?: QueryClient, over: Record<string, unknown> = {}) {
  // پاسخ درِ همین تابع چیده می‌شود، نه درِ `beforeEach`: registrationِ hook
  // نسبت به describeهایِ فایل ترتیب دارد و یکِ test بدونِ payload، `undefined`
  // می‌گیرد و react-query آن را «query data cannot be undefined» می‌شمارد —
  // یعنی پنل بی‌دلیل «نرسید» می‌گفت.
  state.payload = { ...payload(), ...over };
  const queryClient = qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <CodalHealthStrip />
    </QueryClientProvider>,
  );
  return queryClient;
}

afterEach(() => cleanup());

/** صبر تا پاسخ *واقعاً* نشسته باشد. نوار درِ حال بارگذاری هم رندر می‌شود و
 *  «نرسید» می‌گوید، پس شرطِ «گره exists» بلافاصله درست می‌شود و تست پیشِ
 *  رسیدنِ پاسخ قضاوت می‌کرد (سنسورِ خودِ آزمون).
 */
async function awaitData(id = 'codal-health-count-queued', want = '۷') {
  await waitFor(() => expect(screen.getByTestId(id).textContent).toContain(want));
}

describe('۱) وضعیت از پاسخ خوانده می‌شود', () => {
  it('worker روشن ⇒ «درِ کار است»', async () => {
    renderStrip();
    await awaitData();
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('working'));
    expect(screen.getByTestId('codal-health-state').textContent).toContain('درِ کار است');
  });

  it('بی‌worker و بی‌کار ⇒ بیکار، نه خطا', async () => {
    renderStrip(undefined, { worker: { running: false, cycles: 0 },
                              queue: { queued: 0, failed: 0, unresolved: 0, retryable: 0,
                                       total: 0, legacy: 0 } });
    await awaitData('codal-health-count-queued', '۰');
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('idle'));
  });

  it('چرخۀ بی‌خطا ⇒ چراغ سرخ', async () => {
    renderStrip(undefined, { worker: { running: false },
                              queue: { queued: 0, failed: 4, unresolved: 0, retryable: 0 } });
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('failed'));
  });

  it('صفِ پر با retry ⇒ «مانده که باید دوباره تلاش شود»', async () => {
    renderStrip(undefined, { worker: { running: false },
                              queue: { queued: 3, failed: 0, unresolved: 0, retryable: 2 } });
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('blocked'));
  });
});

describe('۲ و ۳) غایب ⇒ علت، نه صفر؛ ارقام ⇒ فارسی', () => {
  it('شمارش‌ها با رقمِ فارسی و testidهایِ قرارداد', async () => {
    renderStrip();
    await awaitData();
    expect(screen.getByTestId('codal-health-count-incomplete').textContent).toContain('۱۲');
    expect(screen.getByTestId('codal-health-count-gap').textContent).toContain('۴۱');
    expect(screen.getByTestId('codal-health-count-dirty').textContent).toContain('۵');
    // failed + unresolved = ۳
    expect(screen.getByTestId('codal-health-count-failed').textContent).toContain('۳');
    // هیچ رقمِ لاتینی درِ شمارش‌ها نمی‌نشیند (قواعدِ رابط). `data_epoch` مستثنا
    // است: آن امضایِ opaque بک‌اند است نه شمارۀ بازار، و بازنویسیِ ارقامش
    // «کد» را قاری‌ناپذیر می‌کند.
    for (const id of ['codal-health-count-queued', 'codal-health-count-failed',
                      'codal-health-count-incomplete', 'codal-health-count-gap',
                      'codal-health-count-dirty', 'codal-health-last-sync']) {
      expect(screen.getByTestId(id).textContent).not.toMatch(/[0-9]/);
    }
  });

  it('null ⇒ «—» و علتِ همان خانۀ خالی', async () => {
    renderStrip(undefined, { last_data_update: null, last_successful_sync: null,
                              last_attempt: null, queue: null, dirty_symbols: null,
                              incomplete_extractions: null, instruments: null,
                              data_epoch: null, worker: null });
    await waitFor(() => expect(screen.getByTestId('codal-health-last-sync')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-count-queued').textContent).toContain('—'));
    const sync = screen.getByTestId('codal-health-last-sync');
    expect(sync.textContent).toContain('—');
    expect(sync.textContent).not.toContain('۰');
    expect(sync.getAttribute('title')).toContain('last_data_update = null');
    // خانۀ صفِ نرسیده هم صفر نمی‌شود
    expect(screen.getByTestId('codal-health-count-queued').textContent).toContain('—');
    expect(screen.getByTestId('codal-health-count-gap').textContent).toContain('—');
  });
});

describe('۴) باختنِ کش با امضایِ تازگی', () => {
  it('درِ اولین خواندن بی‌invalidate؛ با عوض‌شدنِ epoch کارت و غربال باطل می‌شوند', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(qc, 'invalidateQueries');
    state.payload = { ...payload(), data_epoch: 'A|1' };
    render(
      <QueryClientProvider client={qc}>
        <CodalHealthStrip />
      </QueryClientProvider>,
    );
    await awaitData();
    expect(spy).not.toHaveBeenCalled();

    const next = { ...payload(), data_epoch: 'B|2' };
    state.payload = next;
    qc.setQueryData(['codal-health'], next);
    await waitFor(() => expect(spy).toHaveBeenCalled());
    const keys = spy.mock.calls.map((c) => (c[0] as { queryKey?: unknown }).queryKey);
    expect(keys).toEqual(expect.arrayContaining([['fts-card'], ['fts-screen']]));

    // epochِ عوض‌نشده ⇒ دو بار باطل نمی‌کند
    spy.mockClear();
    qc.setQueryData(['codal-health'], { ...payload(), data_epoch: 'B|2' });
    await waitFor(() => expect(screen.getByTestId('codal-health-state')).toBeTruthy());
    expect(spy).not.toHaveBeenCalled();
  });
});

describe('۵ و ۶) خطا و دربۀ آفلاین', () => {
  it('پاسخِ status:error با HTTP 200 ⇒ «نرسید» با علت', async () => {
    renderStrip(undefined, { status: 'error', message: 'bank locked',
                              worker: null, queue: null });
    // هر دو شرط درِ یکِ waitFor: «نرسید» فقط وقتی معنی دارد که علتِ سرور هم
    // رویِ همان رندر نشسته باشد (رندرِ بارگذاری هم data-state را unreachable
    // می‌گذاشت و تست رویِ همان قضاوت می‌کرد).
    await waitFor(() => {
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('unreachable');
      expect(screen.getByTestId('codal-health-state').getAttribute('title')).toContain('bank locked');
    });
  });

  it('پیشِ رسیدنِ پاسخ ⇒ «خوانده می‌شود»، نه «نرسید»', async () => {
    let release!: (v: unknown) => void;
    const gate = new Promise((r) => { release = r; });
    const mod = await import('@shared/api/http');
    const httpMock = mod.http as ReturnType<typeof vi.fn>;
    httpMock.mockImplementationOnce(() => gate);
    renderStrip();
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('loading'));
    expect(screen.queryByText('وضعیتِ خطِ کدال نرسید')).toBeNull();
    release(payload());
    await awaitData();
    expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('working');
  });

  it('شبکه‌ای که هیچ پاسخی نمی‌دهد ⇒ همان «نرسید»، نه صفر', async () => {
    state.payload = undefined;
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <CodalHealthStrip />
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('codal-health-strip').getAttribute('data-state')).toBe('unreachable'));
    expect(screen.getByTestId('codal-health-count-queued').textContent).toContain('—');
  });

  it('دربۀ آفلاین فقط وقتی روشن است دیده می‌شود', async () => {
    renderStrip();
    await awaitData();
    expect(screen.queryByText('دربۀ آفلاین روشن')).toBeNull();

    cleanup();
    renderStrip(undefined, { offline_gate: true });
    await awaitData();
    expect(screen.getByText('دربۀ آفلاین روشن')).toBeTruthy();
  });

  it('جزئیات پشتِ expander است، ولی چراغِ بعدی و امضا درِ همان خط‌اند', async () => {
    renderStrip();
    await awaitData();
    expect(screen.getByTestId('codal-health-last-sync').textContent).toContain('۲۰۲۶');
    expect(screen.getByText('امضایِ تازگی:')).toBeTruthy();
    expect(screen.getByText(/چرخۀ بعدی/)).toBeTruthy();
  });
});
