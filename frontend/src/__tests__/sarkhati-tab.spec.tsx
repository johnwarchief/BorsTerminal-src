// src/__tests__/sarkhati-tab.spec.tsx — تبِّ مستقلِ «سرخطی»: route، state، و
// «هیچ کنترلی بی‌پشتوانهٔ بک‌اند باز نمی‌شود»
//
// چه چیزی سنجیده می‌شود (و چرا این‌ها آزمونِ «رندر شدن» نیستند):
//  ۱) مقصدِ مستقل درِ ناوبری و درِ routes هست (نه فقط یکِ پنلِ جانبی).
//  ۲) فرم باِ جابه‌جایی بینِ بخش‌ها و صفحات نمی‌سوزد، ولی باِ عوض‌شدنِ نماد
//     پاک می‌شود — و «پاک‌شدنِ بی‌دلیل» با «بی‌اعتبارشدنِ لازم» یکی نیست.
//  ۳) تأییدِ نهایی باِ تغییرِ پارامتر باطل می‌شود (قاعدۀ confirm_epoch).
//  ۴) بازکردنِ تب، عوض‌کردنِ بخش، یا رندرِ دوباره هیچ dispatch نمی‌سازد.
//  ۵) «لغو» تنها باِ capability ساخته می‌شود، و «تأییدِ لغو» تنها وقتی نوشته
//     می‌شود که خودِ پاسخ `cancelled_confirmed` داده باشد.
//  ۶) نبودنِ سرویس و نبودنِ سابقه، صفرِ سبز نمی‌شود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SarkhatiPage from '@features/portfolio/routes/SarkhatiPage';
import { NAV_SECTIONS } from '@app/components/Sidebar';
import { mainRoutes } from '../routes';
import { useSarkhatiFormStore } from '@features/portfolio/stores/sarkhatiFormStore';
import { useSymbolStore } from '@shared/stores/symbolStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS_ON = { place: true, list_orders: true, order_state: true,
  queue_position: true, cancel: false, best_bid_ask: false, balances: false };

const MODE_MATRIX = {
  mock: { implemented: true, active: true, door: '/api/execution/*', proves: 'x' },
  dry_run: { implemented: true, active: true, door: '/api/execution/*', proves: 'x' },
  live: { implemented: false, active: false, door: '/api/execution/*', proves: 'y' },
  paper: { implemented: true, active: false, door: '/api/bot/*', can_reach_broker: false, proves: 'z' },
  backtest: { implemented: false, active: false, door: null, can_reach_broker: false, proves: 'w' },
};

function statusBody(patch: Record<string, unknown> = {}) {
  return {
    status: 'success', adapter: 'mock', dry_run: true, experimental: true,
    live_enabled: false, live: false, live_requested: false,
    nothing_will_leave_the_machine: true, wire_hypothesis: false, blocked_on: [],
    confirm_gate: { required: false, phrase: 'تأییدِ نهایی' },
    capabilities: CAPS_ON,
    // نشستِ اتصال‌شده همان چیزی است که بیلدِ mock واقعاً می‌دهد (خواندۀ زنده از
    // /api/execution/status در ۸۱۰۱: state=connected، account_label=mock-acct-1).
    // حالت‌هایِ بی‌نشست درِ بخشِ «قدمِ راهنما» سنجیده می‌شوند، نه اینجا.
    session: { state: 'connected', account_label: 'mock-acct-1' },
    kill_switch: 'ARMED', halted: false, kill_reason: '', ledger_size: 1,
    durable_events: 3, recovered_after_restart: 0, scheduled_pending: 0,
    confirm_epoch: 2, clock_source: 'system', clock_limit: 'ساعتِ سیستم بی‌NTP',
    mode_matrix: MODE_MATRIX,
    queue_rank: { claims_first: false, official_rank_source: null, why: 'رتبه از کارگزاری نخوانده شد' },
    wire_provenance: {
      host: { value: 'https://api-mts.test', kind: 'first-party-config' },
      order_create: { value: '/core/api/v2/order', kind: 'third-party-code-only',
        official_docs: 'absent (swagger/openapi = 403)', hypothesis: true },
    },
    timings: { samples: 0, phases: {} },
    limits: { max_orders: 1, require_confirmation: true, max_order_value: null },
    ...patch,
  };
}

const RECORDS = [{
  execution_id: 'ui-777', broker: 'mock', symbol: 'فولاد', isin: 'IRO1IKCO0001',
  side: 'buy', price: 12610, quantity: 1000, mode: 'safe', status: 'unknown_result',
  order_state: 'unknown', broker_order_id: null, attempts: 1, rtt_ms: null,
  response_at: null, scheduled_at: null, actual_send_wall_ms: null,
  clock_offset_ms: null, filled_quantity: null, queue_position: null,
  error_code: 'TIMEOUT', error_detail: 'ack lost', events: ['dispatch'],
}];

const LEDGER = { status: 'success', adapter: 'mock', dry_run: true, live: false,
  kill_switch: 'ARMED', open_ids: ['ui-777'],
  scheduled: [{ execution_id: 'ui-555', state: 'waiting', target_wall_ms: 1792236000000,
    send_at_wall_ms: 1792235997000, confirm_epoch: 1 }],
  records: RECORDS };

const FEED = { status: 'success', rev: 9, count: 1, live_count: 1, fossil_count: 0,
  meta: { d_even: 20261017, h_even: 112000 },
  data: [{ ins_code: '46', symbol: 'فولاد', name: 'شرکت فولاد مبارکه',
    p_last: 12610, p_closing: 12600, price_yesterday: 12500, percent_change: 0.8,
    tmin: 11250, row_h: 112000, is_live: true, st_title: 'عادی' }] };

const EVENTS = { status: 'success', adapter: 'mock', dry_run: true, count: 1,
  events: [{ id: 11, execution_id: 'ui-777', written_at: '2026-10-17T11:20:00',
    at_epoch: 1792236000, kind: 'dispatch', status: 'unknown_result',
    order_state: 'unknown', error_code: 'TIMEOUT', detail: 'ack lost',
    broker: 'mock', symbol: 'فولاد', side: 'buy', price: 12610, quantity: 1000,
    filled: null, mode: 'safe' }] };

function route(handlers: Record<string, unknown> = {}) {
  const calls: string[] = [];
  fetchMock.mockImplementation((url: string, init?: { body?: string; method?: string }) => {
    const u = String(url);
    calls.push(`${init?.method ?? 'GET'} ${u}`);
    for (const [frag, body] of Object.entries(handlers)) {
      if (u.includes(frag)) return Promise.resolve(json(body));
    }
    if (u.includes('/api/execution/status')) return Promise.resolve(json(statusBody()));
    if (u.includes('/api/execution/order/preview')) {
      return Promise.resolve(json({ status: 'success', adapter: 'mock',
        live: false, dry_run: true, send_ready: false,
        prepared_token: 'tok-tab', execution_id: 'ui-tab-fx',
        expires_in_ms: 120000, phase: 'previewed',
        summary: { symbol: 'فولاد', side: 'buy', price: 12610, quantity: 1000,
          value: 12610000, warnings: [], live: false, dry_run: true,
          send_ready: false },
        timings: { preview_ms: 8 } }));
    }
    if (u.includes('/api/execution/order/confirm')) {
      return Promise.resolve(json({ status: 'validated', dry_run: true,
        record: { execution_id: 'ui-tab-fx', broker: 'mock', symbol: 'فولاد',
          side: 'buy', price: 12610, quantity: 1000, status: 'validated',
          order_state: 'unknown', broker_order_id: null, attempts: 0, events: [] } }));
    }
    if (u.includes('/api/execution/ledger')) return Promise.resolve(json(LEDGER));
    if (u.includes('/api/execution/events')) return Promise.resolve(json(EVENTS));
    if (u.includes('/api/execution/timings')) {
      return Promise.resolve(json({ status: 'success', dry_run: true, adapter: 'mock',
        samples: 6, clock: 'monotonic',
        phases: { dispatch_ms: { n: 6, p50: 41.5, p95: 88.2, p99: null, min: 12, max: 90, thin: false } } }));
    }
    if (u.includes('/api/execution/connect')) {
      return Promise.resolve(json({ status: 'success', states_supported: ['CONNECTED'],
        browser: { open: false }, allowed_hosts: ['login.emofid.com'],
        login_hosts_configured: ['login.emofid.com'],
        host_roles: { auth: ['account.emofid.com', 'login.emofid.com'], ui: ['d.easytrader.ir'],
          api: ['api-mts.orbis.easytrader.ir'], evidence: 'مشاهدهٔ فقط‌خواندنی ۲۰۲۶-۱۰-۱۷' },
        last_verify: { state: 'DISCONNECTED', reason: 'نشستی در حافظه نیست', checked_at: '11:20:00' },
        secrets_stored: false }));
    }
    if (u.includes('/api/execution/audit/')) return Promise.resolve(json({ status: 'success', found: true, events: EVENTS.events }));
    if (u.includes('/api/execution/cancel/')) {
      return Promise.resolve(json({ status: 'success', execution_id: 'ui-777',
        order_state: 'cancelled', cancel_accepted: true, cancelled_confirmed: true,
        note: 'لغو تأیید شد', record: { ...RECORDS[0], status: 'reconciled', order_state: 'cancelled' } }));
    }
    if (u.includes('/api/market')) return Promise.resolve(json(FEED));
    return Promise.resolve(json({ status: 'success' }));
  });
  return calls;
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SarkhatiPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  useSarkhatiFormStore.setState({ bySymbol: {} });
  useSymbolStore.getState().setSymbol('فولاد');
});

describe('مقصدِ مستقل', () => {
  it('درِ ناوبری و درِ routes هر دو ثبت شده است', () => {
    const items = NAV_SECTIONS.flatMap((s) => s.items);
    const nav = items.find((i) => i.to === '/sarkhati');
    expect(nav?.label).toBe('سرخطی');
    expect(mainRoutes.some((r) => r.path === 'sarkhati')).toBe(true);
  });

  it('صفحه باز می‌شود و خطِ وضعیت ازِ سرویس می‌آید، نه از متنِ ثابت', async () => {
    route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('sarkhati-page')).toBeInTheDocument());
    // نشست ازِ همان پاسخِ `statusBody()` خوانده می‌شود (mock بیلدِ واقعی هم
    // connected می‌دهد)؛ شاخه‌هایِ دیگرِ نشست — disconnected/expired/error — درِ
    // `sarkhati-guided-flow.spec.tsx` پاسخ‌هایِ متفاوت سنجیده می‌شوند، پس این
    // سنجش «متنِ ثابت» نیست: دو پاسخِ دیگر، دو خوانشِ دیگر می‌دهد.
    await waitFor(() => expect(screen.getByTestId('sarkhati-status-strip')
      .getAttribute('data-session')).toBe('connected'));
    expect(screen.getByTestId('sarkhati-status-strip').textContent).toContain('سرویسِ اجرا: mock');
    expect(screen.getByTestId('sarkhati-mode-live').textContent).toContain('نیست');
    expect(screen.getByTestId('sarkhati-mode-paper').textContent).toContain('خاموش');
  });
});

describe('حالَتِ فرم', () => {
  it('باِ عوض‌کردنِ بخش نمی‌سوزد و باِ عوض‌شدنِ نماد پاک می‌شود', async () => {
    route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '۱۲۶۱۰' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰۰' } });
    expect(useSarkhatiFormStore.getState().bySymbol['فولاد']?.price).toBe('۱۲۶۱۰');

    fireEvent.click(screen.getByTestId('sarkhati-tab-risk'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-risk-card')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('sarkhati-tab-order'));
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
    // همان مقدار، چون store درِ ماژول می‌ماند (نه stateِ مؤلفه)
    expect(screen.getByTestId('watch-order-price')).toHaveValue('۱۲۶۱۰');

    // نمادِ تازه هیچ‌وقت قیمتِ نمادِ قبلی را زیرِ خودش نمی‌گذارد
    useSymbolStore.getState().setSymbol('شپنا');
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toHaveValue(''));
    expect(screen.getByTestId('sarkhati-symbol-chip').textContent).toContain('شپنا');
    expect(useSarkhatiFormStore.getState().bySymbol['شپنا']).toBeUndefined();
  });

  it('خلاصۀِ نهایی و ارزشِ تخمینی پیش ازِ تأیید دیده می‌شود', async () => {
    route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '12610' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '1000' } });
    await waitFor(() => expect(screen.getByTestId('sarkhati-draft-summary').textContent)
      .toContain('۱۲٬۶۱۰٬۰۰۰ ریال'));
    expect(screen.getByTestId('sarkhati-draft-summary').textContent).toContain('هدفِ ارسال: فوری');
  });

  it('تغییرِ قیمت پس ازِ تأیید، تأیید را بی‌اعتبار می‌کند', async () => {
    route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '12610' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '1000' } });
    await waitFor(() => expect(screen.getByTestId('exec-preview')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('exec-preview'));
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('exec-confirm'));
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeChecked());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '12700' } });
    // پیش‌نمایش با تغییرِ مشخصات باطل می‌شود؛ دکمهٔ ارسال تا بررسیِ تازه خاموش است.
    await waitFor(() => expect(screen.queryByTestId('exec-confirm')).toBeNull());
    expect(screen.getByTestId('exec-submit')).toBeDisabled();
  });
});

describe('هیچ اقدامِ ناخواسته‌ای', () => {
  it('بازکردنِ تب و چرخیدنِ بینِ بخش‌ها هیچ dispatch/POST نمی‌زند', async () => {
    const calls = route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('sarkhati-page')).toBeInTheDocument());
    for (const id of ['sarkhati-tab-connect', 'sarkhati-tab-schedule',
      'sarkhati-tab-tracking', 'sarkhati-tab-monitor', 'sarkhati-tab-risk']) {
      fireEvent.click(screen.getByTestId(id));
      await waitFor(() => expect(screen.getByTestId(id)).toHaveAttribute('aria-selected', 'true'));
    }
    expect(calls.filter((c) => c.includes('/dispatch'))).toEqual([]);
    expect(calls.filter((c) => c.startsWith('POST'))).toEqual([]);
  });

  it('پیش‌فرود هیچ سفارشی نمی‌سازد و «ارسال‌شده» خوانده نمی‌شود', async () => {
    const calls = route({
      '/api/execution/preflight': { status: 'success', adapter: 'mock',
        checks: { instrument: 'PASS', price: 'PASS', quantity: 'PASS', session: 'FAIL',
          place: 'PASS', kill_switch: 'PASS', duplicate: 'PASS' },
        reasons: { session: 'نشست نیست' }, ok: false, unknown: [] },
    });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '12610' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '1000' } });
    fireEvent.click(screen.getByTestId('exec-detail-toggle'));
    await waitFor(() => expect(screen.getByTestId('exec-preflight')).toBeEnabled());
    fireEvent.click(screen.getByTestId('exec-preflight'));
    await waitFor(() => expect(calls.some((c) => c.includes('/preflight'))).toBe(true));
    expect(screen.getByTestId('watch-order-reason').textContent).toContain('پیش‌فرود: ۶ سبز');
    expect(screen.getByTestId('watch-order-reason').textContent).toContain('۱ رد — session (نشست نیست)');
    expect(screen.getByTestId('watch-order-reason').textContent).not.toContain('ارسال‌شده');
    expect(calls.filter((c) => c.includes('/dispatch'))).toEqual([]);
  });
});

describe('لغو و ردِّپا باِ capability', () => {
  it('بی‌capabilityِ لغو، دکمه‌اش ساخته نمی‌شود و علت نوشته می‌شود', async () => {
    route();
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-tracking'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-row-ui-777')).toBeInTheDocument());
    expect(screen.queryByTestId('sarkhati-cancel-ui-777')).toBeNull();
    expect(screen.getByTestId('sarkhati-cancel-unsupported').textContent)
      .toContain('capabilities.cancel: false');
    expect(screen.getByTestId('sarkhati-reconcile-ui-777')).toBeEnabled();
  });

  it('باِ capabilityِ لغو، درخواست باِ confirm:true می‌رود و «تأییدِ لغو» ازِ پاسخ است', async () => {
    const calls = route();
    fetchMock.mockImplementation((url: string, init?: { method?: string; body?: string }) => {
      const u = String(url);
      calls.push(`${init?.method ?? 'GET'} ${u}`);
      if (u.includes('/api/execution/status')) {
        return Promise.resolve(json(statusBody({
          capabilities: { ...CAPS_ON, cancel: true }, dry_run: false, live_enabled: true,
          live: true, nothing_will_leave_the_machine: false,
          session: { state: 'connected', account_label: 'mock-acct-1' },
        })));
      }
      if (u.includes('/api/execution/ledger')) {
        return Promise.resolve(json({ ...LEDGER,
          records: [{ ...RECORDS[0], broker_order_id: 'BR-777', status: 'acknowledged',
            order_state: 'open', error_code: null }] }));
      }
      if (u.includes('/api/execution/cancel/')) return Promise.resolve(json({
        status: 'success', execution_id: 'ui-777', order_state: 'cancelled',
        cancel_accepted: true, cancelled_confirmed: true, note: 'لغو تأیید شد',
        record: { ...RECORDS[0], status: 'reconciled', order_state: 'cancelled' },
      }));
      if (u.includes('/api/market')) return Promise.resolve(json(FEED));
      return Promise.resolve(json(EVENTS));
    });
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-tracking'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-cancel-ui-777')).toBeEnabled());
    expect(screen.getByTestId('sarkhati-row-ui-777').textContent).toContain('BR-777');
    fireEvent.click(screen.getByTestId('sarkhati-cancel-ui-777'));
    await waitFor(() => expect(calls.some((c) => c.includes('POST /api/execution/cancel/ui-777')))
      .toBe(true));
    const sentBody = fetchMock.mock.calls
      .map((c) => String((c[1] as { body?: string } | undefined)?.body ?? ''))
      .find((b) => b.includes('confirm'));
    expect(sentBody).toContain('"confirm":true');
    await waitFor(() => expect(screen.getByTestId('sarkhati-track-answer').textContent)
      .toContain('لغو تأیید شد'));
    expect(screen.queryByTestId('sarkhati-cancel-unsupported')).toBeNull();
  });

  it('ردِّپا ازِ /audit خوانده می‌شود، نه از حافظهٔ رابط', async () => {
    const calls = route();
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-tracking'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-audit-ui-777')).toBeEnabled());
    fireEvent.click(screen.getByTestId('sarkhati-audit-ui-777'));
    await waitFor(() => expect(calls.some((c) => c.includes('/api/execution/audit/ui-777')))
      .toBe(true));
    await waitFor(() => expect(screen.getByTestId('sarkhati-trail-ui-777').textContent)
      .toContain('dispatch'));
  });
});

describe('وضعیت‌هایِ خطا و نبودِ داده', () => {
  it('بی‌سرویسِ اجرا (۴۰۴ = در نیست): نه صفرِ سبز، نه دکمهٔ باز', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(
      { ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response));
    renderPage();
    // «در حالِ خواندنِ وضعیت» حالتِ اولیۀِ واقعی است؛ سنجشِ ما وضعیتی است که
    // سرویس *نیامده* (خطا)، نه وضعیتی که هنوز در راه است.
    // `http()` خودش دو بار با backoff تلاش می‌کند (~۲٫۴ ثانیه)؛ «نبودِ سرویس»
    // بعدِ تمامِ شدنِ آن تلاش‌ها اعلام می‌شود، نه بعدِ اولین خطا.
    await waitFor(() => expect(screen.getByTestId('sarkhati-status-strip').textContent)
      .toContain('سرویسِ اجرا نیست'), { timeout: 8000 });
    await waitFor(() => expect(screen.getByTestId('sarkhati-gate-reason').textContent)
      .toContain('سرویسِ اجرای سفارش در این نسخه پاسخ نمی‌دهد'), { timeout: 15000 });
    // بازطراحیِ ۲۰۲۶-۱۰-۱۸: بی‌سرویس، نگاهِ اول «اتصال» است و فرم اصلاً ساخته
    // نمی‌شود — «دکمهٔ باز» نمی‌تواند باشد، و رفتنِ کاربر به آن هم دروازه را باز
    // نمی‌کند: اگر فرم باز شد، «ارسال» باید خاموش باشد.
    expect(screen.getByTestId('sarkhati-page').getAttribute('data-step')).toBe('connect');
    expect(screen.queryByTestId('exec-submit')).toBeNull();
    fireEvent.click(screen.getByTestId('sarkhati-tab-order'));
    await waitFor(() => expect(screen.getByTestId('exec-submit')).toBeInTheDocument());
    expect(screen.getByTestId('exec-submit')).toBeDisabled();
  }, 20000);

  // بیلدِ منجمد درِ میانشِ همگام‌سازی یک‌بار ۵۰۰ داد و نوارِ وضعیت تا ابد
  // «سرویسِ اجرا نیست» ماند؛ خطایِ گذرا باید خودش را بازیابد (۴۰۴ نه).
  it('خطایِ گذرایِ وضعیت بی‌درنگ «سرویس نیست» نمی‌شود', async () => {
    let hits = 0;
    fetchMock.mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes('/api/execution/status')) {
        hits += 1;
        if (hits < 3) {
          return Promise.resolve({ ok: false, status: 500,
            json: () => Promise.resolve({}) } as unknown as Response);
        }
        return Promise.resolve(json(statusBody()));
      }
      if (u.includes('/api/market')) return Promise.resolve(json(FEED));
      if (u.includes('/api/execution/ledger')) return Promise.resolve(json(LEDGER));
      return Promise.resolve(json({ status: 'success' }));
    });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('sarkhati-status-strip').textContent)
      .toContain('سرویسِ اجرا: mock'), { timeout: 12000 });
    expect(hits).toBeGreaterThanOrEqual(3);
  }, 25000);

  it('سابقه اگر نرسد، «خالی» نمی‌گوید', async () => {
    fetchMock.mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes('/api/execution/events')) return Promise.reject(new Error('boom'));
      if (u.includes('/api/market')) return Promise.resolve(json(FEED));
      if (u.includes('/api/execution/ledger')) return Promise.resolve(json(LEDGER));
      if (u.includes('/api/execution/timings')) {
        return Promise.resolve(json({ status: 'success', phases: {} }));
      }
      return Promise.resolve(json(statusBody()));
    });
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-monitor'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-monitor-card')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId('sarkhati-ev-error')).toBeInTheDocument(),
      { timeout: 6000 });
    expect(screen.queryByTestId('sarkhati-ev-empty')).toBeNull();
  });

  it('زمانِ سرورِ کارگزاری و جایِ صف صریح NOT_PROVEN می‌مانند', async () => {
    route();
    renderPage();
    await waitFor(() => expect(screen.getByTestId('exec-schedule')).toBeInTheDocument());
    expect(screen.getByTestId('exec-server-clock').textContent).toContain('NOT_PROVEN');
    fireEvent.click(screen.getByTestId('sarkhati-tab-schedule'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-schedule-card')).toBeInTheDocument());
    expect(screen.getByTestId('sarkhati-server-clock-note').textContent).toContain('NOT_PROVEN');
    expect(screen.getByTestId('sarkhati-timing-dispatch_ms').textContent).toContain('۴۱');
    fireEvent.click(screen.getByTestId('sarkhati-tab-risk'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-prov-order_create')).toBeInTheDocument());
    expect(screen.getByTestId('sarkhati-prov-order_create').textContent).toContain('فرضیه');
  });

  it('زمان‌بندیِ درِ انتظار باِ «لغوِ زمان‌بندی» بی‌dispatch لغو می‌شود', async () => {
    const calls = route({
      '/api/execution/schedule/ui-555': { status: 'success', execution_id: 'ui-555',
        aborted: true, note: 'پیشِ آتش لغو شد — هیچ درخواستی به کارگزاری نرفت' },
    });
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-schedule'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-sched-cancel-ui-555')).toBeEnabled());
    fireEvent.click(screen.getByTestId('sarkhati-sched-cancel-ui-555'));
    await waitFor(() => expect(calls.some((c) => c.includes('DELETE /api/execution/schedule/ui-555')))
      .toBe(true));
    await waitFor(() => expect(screen.getByTestId('sarkhati-sched-answer').textContent)
      .toContain('پیشِ آتش لغو شد'));
    expect(calls.filter((c) => c.includes('/dispatch'))).toEqual([]);
  });
});

describe('خطِ جریانِ اجرا (ستونِ فقراتِ صفحه)', () => {
  /** وضعیتِ گره‌ها ازِ `data-state` خوانده می‌شود، نه ازِ رنگ — رنگِ تنها
   *  اثباتِ کور است و درِ a11y هم رأی ندارد. همهٔ سنجش‌ها داخلِ waitFor هستند:
   *  هر نُه گره ازِ أولِ رندر درِ DOM هست، پس «بودنش» اصلاً مدرک نیست و
   *  سنجشِ بی‌انتظار، وضعیتِ «هنوز داده نرسیده» را می‌خواند. */
  const node = (id: string) => screen.getByTestId('sarkhati-node-' + id);
  const stateOf = (id: string) => node(id).getAttribute('data-state');
  const titleOf = (id: string) => String(node(id).getAttribute('title') ?? '');

  it('گره‌ها ازِ پاسخِ سرویس می‌آیند، نه ازِ متنِ ثابت: گیتِ اجرا بی‌live بسته است', async () => {
    route({ '/api/execution/status': statusBody({
      blocked_on: ['D1: نشستِ مالک درِ حافظه نیست'] }) });
    renderPage();
    // «held» تنها باِ یکِ رأیِ بک‌اند معنی دارد: بی‌رسیدنِ پاسخ هم gate held است،
    // پس نخستِ آن‌چه ثابت می‌شود رسیدنِ خودِ وضعیت است (رخدادِ ماندگار > ۰).
    await waitFor(() => expect(stateOf('history')).toBe('done'));
    expect(stateOf('gate')).toBe('held');
    // علت ازِ blocked_onِ خودِ پاسخ می‌آید؛ هیچ «قابلِ استفاده» یا «آمادهٔ
    // ارسال» نوشته نمی‌شود (بندِ ۵ مأموریت).
    expect(titleOf('gate')).toContain('گیتِ اجرا بسته است');
    expect(titleOf('gate')).toContain('D1: نشستِ مالک درِ حافظه نیست');
  });

  it('گیتِ held بی‌علتِ سرویس «باز است» نمی‌شود — رابط دروغ‌گو نیست', async () => {
    route({ '/api/execution/status': statusBody({ blocked_on: [], live_requested: false }) });
    renderPage();
    await waitFor(() => expect(stateOf('history')).toBe('done'));
    expect(stateOf('gate')).toBe('held');
    expect(titleOf('gate')).not.toContain('باز است');
    expect(titleOf('gate')).toContain('درخواست نشده');
  });

  it('بی‌نماد، گرهٔ «نماد» نوبت را می‌گیرد و بقیه پیش ازِ نماد سبز نمی‌شوند', async () => {
    useSymbolStore.getState().setSymbol('');
    route({ '/api/execution/ledger': { ...LEDGER, records: [], open_ids: [] } });
    renderPage();
    await waitFor(() => expect(stateOf('symbol')).toBe('now'));
    expect(stateOf('send')).toBe('idle');
    expect(stateOf('accept')).toBe('idle');
    expect(screen.getByTestId('sarkhati-pipeline-hint').getAttribute('data-node')).toBe('symbol');
  });

  it('unknown_result: «ارسال» مبهم می‌ماند، نه انجام‌شده و نه انجام‌نشده', async () => {
    route();
    renderPage();
    // رکوردِ پیش‌فرضِ آزمون unknown_result است (ack گم شده).
    await waitFor(() => expect(stateOf('send')).toBe('unknown'));
    expect(stateOf('accept')).toBe('unknown');
    expect(stateOf('check')).toBe('unknown');
    expect(stateOf('send')).not.toBe('done');
    expect(stateOf('send')).not.toBe('bad');
    await waitFor(() => expect(screen.getByTestId('sarkhati-pipeline-hint').textContent)
      .toContain('تعیینِ تکلیف نشده'));
  });

  it('مدتِ هر گره از /timings می‌آید؛ گرهٔ بی‌فاز «—» می‌گیرد نه صفر', async () => {
    route();
    renderPage();
    await waitFor(() => expect(node('send').textContent).toContain('۴۱.۵ms'));
    expect(node('confirm').textContent).toContain('—');
    expect(node('preflight').textContent).toContain('—');
    expect(node('send').textContent).not.toContain('۰ms');
  });

  it('توقفِ اضطراری: گیت، علتِ توقف را می‌گوید نه علتِ نبودِ اتصال', async () => {
    route({ '/api/execution/status': statusBody({ halted: true, kill_switch: 'TRIPPED',
      kill_reason: 'توقف از پنلِ معامله', blocked_on: ['D1: نشستِ مالک درِ حافظه نیست'] }) });
    renderPage();
    await waitFor(() => expect(titleOf('gate')).toContain('توقفِ اضطراری'));
    expect(stateOf('gate')).toBe('held');
    expect(titleOf('gate')).toContain('توقف از پنلِ معامله');
    expect(titleOf('gate')).not.toContain('D1:');
  });

  it('اتصالِ زنده باِ شواهد: گیت باز می‌شود و «ارسال» هنوز ادعا ندارد', async () => {
    route({ '/api/execution/status': statusBody({
      live_enabled: true, live: true, dry_run: false, nothing_will_leave_the_machine: false,
      halted: false, blocked_on: [],
      session: { state: 'connected', account_label: 'mock-acct-1' },
    }), '/api/execution/ledger': { ...LEDGER, records: [], open_ids: [] } });
    renderPage();
    await waitFor(() => expect(stateOf('gate')).toBe('done'));
    expect(titleOf('gate')).toContain('گیتِ اجرا باز است');
    expect(['idle', 'now']).toContain(stateOf('send'));
    expect(stateOf('accept')).not.toBe('done');
  });
});
