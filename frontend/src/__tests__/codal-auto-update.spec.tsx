// آزمونِ خودکارسازیِ نمایش/اعمالِ به‌روزرسانیِ امضاشدهٔ دادهٔ بنیادی (Task 8b).
// قراردادها:
//   • یک هوکِ پولینگ: ۲ ثانیه وقتی اجرا در جریان است، ۳۰ ثانیه وقتی بی‌کار است؛
//     نگهبانِ alive/شمارهٔ ترتیب تا پاسخِ کهنه جایِ پاسخِ تازه را نگیرد.
//   • گذارِ running→done یک‌بار refetch غربالگری و یک بنرِ «دادهٔ بنیادی به‌روز شد».
//   • خطای بک‌اند با role=alert دیده می‌شود؛ موفقیتِ ساختگی و تاریخِ ساختگی نه.
//   • خطِ تازگی فقط از meta/freshnessِ خودِ پاسخ ساخته می‌شود.
// همهٔ درخواست‌ها با mockِ `http` (بدون شبکه) و تایمرهای جعلی کنترل می‌شوند.
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';

import FundamentalPage from '@features/fundamental/routes/FundamentalPage';
import { useCodalAutoUpdate, type DbStatus } from '@features/fundamental/api/useCodalAutoUpdate';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { jalaliOf } from '@features/fundamental/lib/assemblyEvent';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import { useSymbolStore } from '@shared/stores/symbolStore';

const { httpMock } = vi.hoisted(() => ({ httpMock: vi.fn() }));

vi.mock('@shared/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@shared/api/http')>();
  return { ...actual, http: httpMock };
});

// jsdom اندازه ندارد؛ مجازی‌ساز را به رندرِ همهٔ ردیف‌ها وادار می‌کنیم.
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 52,
      getVirtualItems: () =>
        Array.from({ length: opts.count }, (_, i) => ({ key: i, index: i, start: i * 52 })),
    }),
  };
});

let statusScript: DbStatus[] = [];
let statusCalls = 0;
let screenerCalls = 0;
let downloadCalls = 0;
/** پاسخِ POST — چون فقط status:"success" تأییدِ شروع است، هر تست می‌تواند
 *  already_running/error یا rejection را جایِ آن بگذارد. */
let downloadReply: () => Promise<unknown>;

function statusResponse(db: DbStatus): { db: DbStatus } {
  return { db };
}

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'شپنا',
    symbol_norm: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'محصولات نفتی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    gross_margin: 32.5,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: true,
    i1b_applicable: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: false,
    i3_na: false,
    i4_na: false,
    verdict: 'STRONG',
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: false,
    ...patch,
  };
}

async function flush(times = 8) {
  for (let i = 0; i < times; i++) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
  await flush(4);
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

/** کاوشگرِ خالیِ هوک — برای سنجشِ ریتمِ پولینگ بی‌دخالتِ صفحه. */
function Probe({ onDone }: { onDone?: () => void }) {
  const { status } = useCodalAutoUpdate({ onDone });
  return <span data-testid="probe-stage">{status?.stage ?? 'none'}</span>;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  statusScript = [];
  statusCalls = 0;
  screenerCalls = 0;
  downloadCalls = 0;
  useSymbolStore.getState().setSymbol('');
  downloadReply = async () => ({
    status: 'success',
    message: 'دانلود دیتابیس کدال از گیت‌هاب آغاز شد.',
  });
  httpMock.mockImplementation((url: string) => {
    if (url === '/api/sync/codal/db-download') {
      downloadCalls += 1;
      return downloadReply();
    }
    if (url === '/api/sync/codal/db-status') {
      statusCalls += 1;
      const db = statusScript.length > 1
        ? statusScript.shift()!
        : statusScript[0] ?? { running: false, stage: 'idle' };
      return Promise.resolve(statusResponse(db));
    }
    if (url.startsWith('/api/screener')) {
      screenerCalls += 1;
      return Promise.resolve({
        status: 'success',
        count: 1,
        thresholds: {},
        max_score: 5,
        data: [row()],
      });
    }
    if (url.startsWith('/api/calendar/upcoming')) {
      return Promise.resolve({ status: 'success', days: 14, count: 0, items: [], capital: [] });
    }
    if (url.startsWith('/api/market')) {
      return Promise.resolve({ status: 'success', count: 0, data: [] });
    }
    return Promise.resolve({ status: 'success', data: [] });
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('هوکِ به‌روزرسانی خودکار کدال — ریتم و نگهبان‌ها', () => {
  it('بی‌کار: یک کاوشِ فوری و سپس هر ۳۰ ثانیه — نه سریع‌تر', async () => {
    statusScript = [{ running: false, stage: 'idle' }];
    render(<Probe />);
    await flush();
    expect(statusCalls).toBe(1);

    await advance(29_999);
    expect(statusCalls).toBe(1);

    await advance(1);
    expect(statusCalls).toBe(2);

    await advance(30_000);
    expect(statusCalls).toBe(3);
  });

  it('در حال اجرا: ریتمِ ۲ ثانیه', async () => {
    statusScript = [{ running: true, stage: 'downloading', percent: 10 }];
    render(<Probe />);
    await flush();
    expect(statusCalls).toBe(1);
    expect(screen.getByTestId('probe-stage').textContent).toBe('downloading');

    await advance(1_999);
    expect(statusCalls).toBe(1);

    await advance(1);
    expect(statusCalls).toBe(2);

    await advance(2_000);
    expect(statusCalls).toBe(3);
  });

  it('با unmount شدن، پولینگ متوقف می‌شود', async () => {
    statusScript = [{ running: true, stage: 'downloading' }];
    const { unmount } = render(<Probe />);
    await flush();
    expect(statusCalls).toBe(1);

    unmount();
    await advance(60_000);
    expect(statusCalls).toBe(1);
  });

  it('بی‌کار → در حالِ اجرا: ریتم در همان mount از ۳۰s به ۲s می‌رود', async () => {
    statusScript = [
      { running: false, stage: 'idle' },
      { running: true, stage: 'downloading', percent: 5 },
    ];
    render(<Probe />);
    await flush();
    expect(statusCalls).toBe(1);

    await advance(30_000);
    expect(statusCalls).toBe(2);
    expect(screen.getByTestId('probe-stage').textContent).toBe('downloading');

    await advance(1_999);
    expect(statusCalls).toBe(2);
    await advance(1);
    expect(statusCalls).toBe(3);
  });

  it('نگهبانِ شمارهٔ ترتیب: پاسخِ کهنه‌ترِ تیک حتی بدونِ flipِ running نمی‌نشیند', async () => {
    const pending: Array<(v: { db: DbStatus }) => void> = [];
    let calls = 0;
    httpMock.mockImplementation((url: string) => {
      if (url === '/api/sync/codal/db-status') {
        calls += 1;
        statusCalls += 1;
        if (calls === 1) return Promise.resolve(statusResponse({ running: false, stage: 'idle' }));
        return new Promise((resolve) => {
          pending.push(resolve as (v: { db: DbStatus }) => void);
        });
      }
      return Promise.resolve({ status: 'success', data: [] });
    });
    render(<Probe />);
    await flush();
    expect(screen.getByTestId('probe-stage').textContent).toBe('idle');

    await advance(30_000); // تیک ۱ — در راه (بی‌کار، بدونِ flip)
    await advance(30_000); // تیک ۲ — در راه
    expect(pending).toHaveLength(2);

    // تازه‌تر اول می‌رسد، کهنه بعد؛ کهنه نباید جایِ تازه را بگیرد
    await act(async () => {
      pending[1]!({ db: { running: false, stage: 'done' } });
      await Promise.resolve();
    });
    expect(screen.getByTestId('probe-stage').textContent).toBe('done');

    await act(async () => {
      pending[0]!({ db: { running: true, stage: 'downloading', percent: 77 } });
      await Promise.resolve();
    });
    expect(screen.getByTestId('probe-stage').textContent).toBe('done');
    await flush();
  });
});

describe('صفحهٔ بنیادی — بنرِ وضعیت و اعمالِ نتیجه', () => {
  it('در حال اجرا: درصدِ صادقانه نمایش داده می‌شود', async () => {
    statusScript = [{ running: true, stage: 'downloading', percent: 41.6 }];
    renderPage();
    await flush();

    const banner = screen.getByTestId('codal-update-running');
    expect(banner.textContent).toContain('دریافت دادهٔ بنیادی ۴۲٪');
  });

  it('گذارِ running→done: بنرِ پایان + یک‌بار refetch غربالگری', async () => {
    statusScript = [
      { running: true, stage: 'merging' },
      {
        running: false,
        stage: 'done',
        freshness: { latest_financial_period: '1405/06/31', last_success: '2026-10-25T18:30:00' },
      },
      { running: false, stage: 'done' },
    ];
    renderPage();
    await flush();
    expect(screen.getByTestId('codal-update-running')).toBeInTheDocument();
    expect(screenerCalls).toBe(1);

    await advance(2_000);
    expect(screen.getByTestId('codal-update-done').textContent).toContain('دادهٔ بنیادی به‌روز شد');
    expect(screenerCalls).toBe(2);

    // ریتم پس از پایان به ۳۰s برمی‌گردد: پیش از ۳۰s تیکی زده نمی‌شود
    const afterDone = statusCalls;
    await advance(29_999);
    expect(statusCalls).toBe(afterDone);
    await advance(1);
    expect(statusCalls).toBe(afterDone + 1);

    // تیک‌های بی‌کارِ بعدی هیچ refetchِ دومی نمی‌سازند
    await advance(30_000);
    expect(screenerCalls).toBe(2);
    await advance(30_000);
    expect(screenerCalls).toBe(2);
  });

  it('خطای بک‌اند با role=alert خوانده می‌شود', async () => {
    statusScript = [
      { running: true, stage: 'downloading', percent: 10 },
      { running: false, stage: 'error', error: 'ادغام snapshot ناموفق بود' },
    ];
    renderPage();
    await flush();
    await advance(2_000);

    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('ادغام snapshot ناموفق بود');
  });

  it('بدون گذارِ running→done، موفقیتِ ساختگی نشان داده نمی‌شود', async () => {
    statusScript = [{ running: false, stage: 'done' }];
    renderPage();
    await flush();

    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screenerCalls).toBe(1);
  });

  it('دکمهٔ دستی حفظ شده و همان POST را می‌فرستد', async () => {
    statusScript = [{ running: false, stage: 'idle' }];
    renderPage();
    await flush();

    fireEvent.click(screen.getByTestId('fts-db-update'));
    await flush();

    expect(downloadCalls).toBe(1);
    expect(screen.getByTestId('codal-update-running').textContent).toContain('در حال به‌روزرسانی…');
  });

  it('POST با already_running و stageِ دوام‌دارِ done: هشدار، بی‌بنر و بی‌refetch', async () => {
    statusScript = [{ running: false, stage: 'done', ts: new Date().toISOString() }];
    downloadReply = async () => ({
      status: 'already_running',
      message: 'اسکن کدال در حال اجراست — صبر کنید.',
    });
    renderPage();
    await flush();
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screenerCalls).toBe(1);

    fireEvent.click(screen.getByTestId('fts-db-update'));
    await flush();

    expect(downloadCalls).toBe(1);
    expect(screen.getByRole('alert').textContent).toContain('اسکن کدال در حال اجراست');
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screenerCalls).toBe(1);

    // تیک‌های بعدی هم doneِ دوام‌دار را «موفقیتِ تازه» نمی‌خوانند
    await advance(2_000);
    await advance(30_000);
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screenerCalls).toBe(1);
  });

  it('POSTِ شکست‌خورده (reject): هشدار می‌آید و هیچ موفقیتی لچ نمی‌شود', async () => {
    statusScript = [
      { running: false, stage: 'idle', ts: new Date().toISOString() },
      { running: false, stage: 'done' },
    ];
    downloadReply = async () => {
      throw new Error('offline');
    };
    renderPage();
    await flush();

    fireEvent.click(screen.getByTestId('fts-db-update'));
    await flush();

    expect(screen.getByRole('alert').textContent).toContain('ارتباط با سرور برقرار نشد');
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();

    await advance(30_000);
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screenerCalls).toBe(1);
  });

  it('شروعِ تأییدشده بنرِ قبلی را پاک می‌کند و بنرِ پایانِ تازه یک‌بار می‌آید', async () => {
    statusScript = [
      { running: true, stage: 'downloading', percent: 10 },
      { running: false, stage: 'done' },
    ];
    renderPage();
    await flush();
    await advance(2_000);
    expect(screen.getByTestId('codal-update-done')).toBeInTheDocument();
    expect(screenerCalls).toBe(2);

    fireEvent.click(screen.getByTestId('fts-db-update'));
    await flush();
    expect(screen.queryByTestId('codal-update-done')).not.toBeInTheDocument();
    expect(screen.getByTestId('codal-update-running').textContent).toContain('در حال به‌روزرسانی…');

    // POST با status:"success" لچ را می‌بندد؛ doneِ بعدی یک‌بار دیگر refetch می‌کند
    await advance(2_000);
    expect(screen.getByTestId('codal-update-done')).toBeInTheDocument();
    expect(screenerCalls).toBe(3);
  });
});

describe('خطایِ ماندگارِ db-status — فقط تازه‌اش اعلان می‌سازد', () => {
  it('خطایِ چندروزهٔ پیش در ورود، «خطایِ همین حالا» خوانده نمی‌شود', async () => {
    statusScript = [{
      running: false,
      stage: 'error',
      error: 'ادغام snapshot ناموفق بود',
      ts: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    }];
    renderPage();
    await flush();

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByTestId('fts-db-update').textContent).not.toContain('خطای دیتابیس کدال');
  });

  it('خطایِ تازه (همین نشست/۶ ساعتِ اخیر) خوانده می‌شود', async () => {
    statusScript = [{
      running: false,
      stage: 'error',
      error: 'ادغام snapshot ناموفق بود',
      ts: new Date().toISOString(),
    }];
    renderPage();
    await flush();

    expect(screen.getByRole('alert').textContent).toContain('ادغام snapshot ناموفق بود');
  });
});

describe('FtsScreenTable — خطِ تازگیِ دادهٔ بنیادی', () => {
  it('دوره و تاریخِ آخرین به‌روزرسانی از freshness نمایش داده می‌شود', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        dbUpdate={{
          running: false,
          stage: 'done',
          meta: { latest_financial_period: '1405/05/31', published_at: '2026-10-24T10:00:00' },
          freshness: {
            latest_financial_period: '1405/06/31',
            last_success: '2026-10-25T18:30:00',
            source: 'db',
          },
        }}
      />,
    );

    const line = screen.getByTestId('fts-db-freshness');
    expect(line.textContent).toContain('آخرین به‌روزرسانی بنیادی:');
    expect(line.textContent).toContain(jalaliOf('2026-10-25'));
    expect(line.textContent).toContain('آخرین دوره: ۱۴۰۵/۰۶/۳۱');
    // تاریخِ خامِ ISO هرگز رویِ صفحه نمی‌نشیند
    expect(line.textContent).not.toContain('2026-10-25');
  });

  it('در نبودِ meta/freshness هیچ خطِ تازگی و هیچ تاریخِ ساختگی نیست', () => {
    render(
      <FtsScreenTable rows={[row()]} onSelect={() => {}} dbUpdate={{ running: false, stage: 'done' }} />,
    );

    expect(screen.queryByTestId('fts-db-freshness')).not.toBeInTheDocument();
    expect(screen.queryByText(/آخرین به‌روزرسانی بنیادی/)).not.toBeInTheDocument();
  });

  it('اگر freshness خالی باشد، متایِ snapshot جای خالی را پر می‌کند', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        dbUpdate={{
          running: false,
          stage: 'done',
          // بک‌اند برایِ نبودِ last_success رشتهٔ خالی می‌فرستد، نه null
          freshness: { latest_financial_period: '', last_success: '', source: '' },
          meta: { latest_financial_period: '1405/05/31', published_at: '2026-10-24T10:00:00' },
        }}
      />,
    );

    const line = screen.getByTestId('fts-db-freshness');
    expect(line.textContent).toContain(jalaliOf('2026-10-24'));
    expect(line.textContent).toContain('آخرین دوره: ۱۴۰۵/۰۵/۳۱');
  });

  it('انتشارِ تازه‌ترِ snapshot بر last_successِ عقب‌مانده مقدم است (M2)', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        dbUpdate={{
          running: false,
          stage: 'done',
          meta: {
            latest_financial_period: '1405/07/31',
            published_at: '2026-10-26T05:00:00+00:00',
          },
          // ادغامِ سمتِ کلاینت فقط کدال را می‌نویسد؛ last_success عقب می‌ماند
          freshness: {
            latest_financial_period: '1405/06/31',
            last_success: '2026-10-25T18:30:00',
            source: 'db',
          },
        }}
      />,
    );

    const line = screen.getByTestId('fts-db-freshness');
    expect(line.textContent).toContain(jalaliOf('2026-10-26'));
    expect(line.textContent).toContain('آخرین دوره: ۱۴۰۵/۰۷/۳۱');
  });

  it('انتشارِ شبانگاهیِ UTC با روزِ تهران خوانده می‌شود، نه برشِ UTC', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        dbUpdate={{
          running: false,
          stage: 'done',
          meta: {
            latest_financial_period: '1405/06/31',
            // ۲۱:۳۰ UTC = ۰۱:۰۰ تهرانِ فردا
            published_at: '2026-10-25T21:30:00+00:00',
          },
          freshness: { latest_financial_period: '', last_success: '', source: '' },
        }}
      />,
    );

    const line = screen.getByTestId('fts-db-freshness');
    expect(line.textContent).toContain(jalaliOf('2026-10-26'));
    expect(line.textContent).not.toContain(jalaliOf('2026-10-25'));
  });

  it('در نبودِ published_at، last_success جایِ تاریخ را پر می‌کند', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        dbUpdate={{
          running: false,
          stage: 'done',
          meta: { latest_financial_period: '1405/06/31', published_at: '' },
          freshness: {
            latest_financial_period: '',
            last_success: '2026-10-25T18:30:00',
            source: 'db',
          },
        }}
      />,
    );

    const line = screen.getByTestId('fts-db-freshness');
    expect(line.textContent).toContain(jalaliOf('2026-10-25'));
    expect(line.textContent).toContain('آخرین دوره: ۱۴۰۵/۰۶/۳۱');
  });
});
