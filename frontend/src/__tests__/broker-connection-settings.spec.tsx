// تستِ «تنظیمِ اتصال» و خطِ راستِ نشست/پرتفوی (مأموریتِ 2026-10-18)
//
// چهار چیزی که اینجا سنجیده می‌شود، چهار دروغی است که رابطِ قبلی می‌توانست بگوید:
//  ۱) «متصل» بی‌پرسشِ واقعی — حالا برچسب ازِ `session.proven` و `verified_by` می‌آید،
//     نه ازِ حضورِ رشته‌ای درِ حافظه؛
//  ۲) «ذخیره شد» به‌جایِ «اعمال شد» — تا restart، تنظیمِ دیسک مؤثر نیست و رابط
//     باید تفاوتِ `stored` و `effective` را بگوید؛
//  ۳) درِ «فقط‌خواندنی» که ارسال را هم باز کند — بدنهٔ POST فقط دو کلید دارد و
//     هیچ‌کدام اسمِ رمز/نشانی نیست؛
//  ۴) «صفرِ ردیف» برایِ وضعیتی که منبع ندارد — `rows: null` هیچ عددی نمی‌سازد.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiConnectionCard, sessionTruth } from '@features/portfolio/components/sarkhati/SarkhatiConnectionCard';
import { DRY_RUN_LABEL, PORTFOLIO_LABEL, TRAFFIC_LABEL, deriveGate,
  type ExecutionStatus } from '@features/portfolio/lib/orderClient';
import { statusLine } from '@features/portfolio/lib/sarkhatiFlow';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS_RO = { place: false, list_orders: true, order_state: true,
  queue_position: true, cancel: false, best_bid_ask: false, balances: false };

function statusEasy(patch: Record<string, unknown> = {}) {
  return {
    status: 'success', adapter: 'easytrader', dry_run: true, live_enabled: false,
    live: true, live_requested: false, read_only: true, traffic_allowed: true,
    nothing_will_leave_the_machine: true, wire_hypothesis: true, blocked_on: [],
    capabilities: CAPS_RO,
    session: { state: 'connected', account_label: 'easytrader-session',
      origin: 'easytrader', proven: true,
      verified_by: { path: '/easy/api/account/server-time', kind: 'observed-read-only',
        hypothesis: false } },
    connection_config: { adapter: 'easytrader', adapter_source: 'settings',
      read_only: true, writes_gate: 'env:BORS_EXECUTION_LIVE',
      applies_on_restart: true, secrets_stored: false },
    kill_switch: 'ARMED', halted: false, ledger_size: 0, durable_events: 0,
    clock_source: 'system', clock_limit: 'ساعتِ سیستم',
    ...patch,
  };
}

const CONNECT_RO = { status: 'success', states_supported: [], browser: { open: false },
  allowed_hosts: [], login_hosts_configured: [], secrets_stored: false,
  traffic_mode: 'read_only', session_proven: true, last_verify: null };

const CONFIG_SAVED = { status: 'success',
  stored: { adapter: 'easytrader', read_only: true, source: 'settings', updated_at: 1 },
  effective: { adapter: 'mock', traffic_allowed: false, read_only: false,
    live_requested: false, session_live: false, writes_gate: 'env:BORS_EXECUTION_LIVE' },
  applies_on_restart: true, secrets_stored: false,
  detail: 'token/رمز/کوکی هیچ‌جا درِ این تنظیم نمی‌نشیند' };

const PORTFOLIO_NONE = { status: 'no_source', adapter: 'easytrader', live: true,
  session_proven: true, as_of: null, source: 'none', rows: null, cached_at: null,
  error: 'هیچ منبعِ مستندِ خواندنی برایِ پرتفویِ این کارگزاری درِ مخزن ثبت نشده' };

function route(handlers: Record<string, unknown> = {}) {
  const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    for (const [frag, body] of Object.entries(handlers)) {
      if (u.includes(frag)) return Promise.resolve(json(body));
    }
    if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG_SAVED));
    if (u.includes('/api/execution/portfolio')) return Promise.resolve(json(PORTFOLIO_NONE));
    if (u.endsWith('/api/execution/connect')) return Promise.resolve(json(CONNECT_RO));
    if (u.endsWith('/api/execution/status')) return Promise.resolve(json(statusEasy()));
    if (u.endsWith('/api/execution/ledger')) {
      return Promise.resolve(json({ status: 'success', adapter: 'easytrader',
        dry_run: true, live: false, open_ids: [], scheduled: [], records: [] }));
    }
    return Promise.resolve(json({ status: 'success' }));
  });
  return calls;
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiConnectionCard /></QueryClientProvider>);
}

/** هر خط منتظر *محتوا* می‌ماند، نه وجودِ گره: این مؤلفه‌ها بی‌داده هم رندر
 *  می‌شوند («—»، «پاسخی نیامده»)، و انتظارِ بی‌محتوا آزمون را بی‌محابا سبز می‌کند. */
async function settled(testId: string, re: RegExp | string) {
  await waitFor(() => {
    const el = screen.queryByTestId(testId);
    const text = el?.textContent ?? '';
    expect(el, testId + ' هنوز رندر نشده').not.toBeNull();
    expect(re instanceof RegExp ? re.test(text) : text.includes(re),
      testId + ' = ' + text).toBe(true);
  });
}

const FA_DIGIT = /[۰-۹]/;

describe('تنظیمِ اتصالِ کارگزاری', () => {
  beforeEach(() => fetchMock.mockReset());

  it('«ذخیره شد» را ازِ «اعمال شد» جدا می‌گوید (restart لازم است)', async () => {
    route();
    renderCard();
    // stored = easytrader ولی effective = mock → همان تفاوتِ موردِ انتظار
    await settled('sarkhati-config-stored', 'easytrader');
    await settled('sarkhati-config-effective', 'mock');
    expect(screen.getByTestId('sarkhati-config-restart')).toBeDefined();
  });

  it('تنظیمِ مؤثر وقتی باِ ذخیره‌شده یکی است، پیامِ restart نمی‌دهد', async () => {
    route({ '/api/execution/config': { ...CONFIG_SAVED,
      effective: { ...CONFIG_SAVED.effective, adapter: 'easytrader' } } });
    renderCard();
    await settled('sarkhati-config-effective', 'easytrader');
    expect(screen.queryByTestId('sarkhati-config-restart')).toBeNull();
  });

  it('ذخیره فقط دو کلید می‌فرستد و هیچ مقدارِ محرمانه‌ای درِ بدنه نیست', async () => {
    const calls = route();
    renderCard();
    await settled('sarkhati-config-stored', 'easytrader');
    fireEvent.click(screen.getByTestId('sarkhati-read-only'));
    fireEvent.click(screen.getByTestId('sarkhati-config-save'));
    await waitFor(() => {
      const post = calls.find((c) => c.url.includes('/api/execution/config')
        && c.init?.method === 'POST');
      expect(post).toBeDefined();
      const body = JSON.parse(String(post?.init?.body));
      expect(Object.keys(body).sort()).toEqual(['adapter', 'read_only']);
      expect(JSON.stringify(body)).not.toMatch(/token|secret|authorization|password/i);
    });
  });

  it('کلیدِ ذخیره‌شدنِ فقط‌خواندنی رویِ آداپتورِ مفید روشن می‌ماند', async () => {
    route();
    renderCard();
    await settled('sarkhati-config-stored', 'easytrader');
    // تنظیمِ ذخیره‌شده read_only=true ⇒ کلید ازِ اول فشرده است؛ ادعایِ «خاموش»
    // ساختنِ حالتِ فقط‌خواندنی درِ رابط نیست، ازِ پاسخ می‌آید.
    expect(screen.getByTestId('sarkhati-read-only').getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByTestId('sarkhati-read-only'));
    expect(screen.getByTestId('sarkhati-read-only').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('sarkhati-config-dirty')).toBeDefined();
  });
});

describe('راستِ نشست و ترافیک', () => {
  beforeEach(() => fetchMock.mockReset());

  it('حالتِ فقط‌خواندنی باِ همان برچسبِ بک‌اند نشان داده می‌شود', async () => {
    route();
    renderCard();
    await settled('sarkhati-traffic-mode', TRAFFIC_LABEL.read_only.text);
  });

  it('«بی‌ترافیک» باِ «فقط‌خواندنی» یکی نمی‌شود', async () => {
    route({ '/api/execution/connect': { ...CONNECT_RO, traffic_mode: 'blocked',
      session_proven: false } });
    renderCard();
    await settled('sarkhati-traffic-mode', TRAFFIC_LABEL.blocked.text);
  });

  it('نشستِ تأییدشده ازِ مسیرِ دیدہ‌شدہ باِ تأییدِ مسیرِ فرضی فرق دارد', () => {
    const observed = (statusEasy() as unknown) as ExecutionStatus;
    expect(sessionTruth(observed)).toBe(
      'نشست تأیید شد — ازِ مسیرِ فقط‌خواندنیِ دیدہ‌شدہ');
    const hypo = (statusEasy({ session: { ...observed.session,
      verified_by: { path: '/core/api/order', hypothesis: true } } }) as unknown) as ExecutionStatus;
    expect(sessionTruth(hypo)).toContain('فهرستِ سفارش');
  });

  it('بی‌`proven` هیچ «تأیید شد» ای نوشته نمی‌شود — حتی باِ نشستِ connected', () => {
    const s = (statusEasy({ session: { state: 'connected', origin: 'easytrader',
      proven: false, verified_by: {} } }) as unknown) as ExecutionStatus;
    const text = sessionTruth(s);
    expect(text).toBe('نشست تأیید نشده (پرسشِ موفق در کار نیست)');
    expect(text).not.toContain('تأیید شد');
  });

  it('آداپتورِ بدل هرگز «متصلِ کارگزاری» نمی‌شود', () => {
    const s = (statusEasy({ adapter: 'mock', session: { state: 'connected',
      origin: 'mock', proven: false, verified_by: {} } }) as unknown) as ExecutionStatus;
    expect(sessionTruth(s)).toBe('آداپتورِ بدل — هیچ پرسشی به کارگزاری نرفته');
  });
});

describe('خطِ وضعیتِ اولِ صفحه (قدمِ «سرخطی»)', () => {
  it('درِ فقط‌خواندنی «بی‌ترافیک» نمی‌گوید: یکِ GET واقعاً بیرون می‌رود', () => {
    const s = (statusEasy() as unknown) as ExecutionStatus;
    const gate = deriveGate(s, 'ok');
    expect(statusLine(gate)).toContain('فقط‌خواندنی');
    expect(statusLine(gate)).not.toContain('بی‌ترافیک');
    expect(gate.canTrade).toBe(false);
    expect(gate.reason).toContain('فقط‌خواندنی');
  });

  it('بی‌ترافیکِ واقعی همان «بی‌ارسال» می‌ماند و باِ فقط‌خواندنی یکی نمی‌شود', () => {
    const s = (statusEasy({ read_only: false, traffic_allowed: false,
      blocked_on: ['ترافیک خاموش است'] }) as unknown) as ExecutionStatus;
    const line = statusLine(deriveGate(s, 'ok'));
    expect(line).not.toContain('فقط‌خواندنی');
    expect(line).toContain(DRY_RUN_LABEL);
  });
});

describe('خطِ پرتفویِ فقط‌خواندنی', () => {
  beforeEach(() => fetchMock.mockReset());

  it('«بی‌منبع» هیچ ردیفی نمی‌سازد و «صفر» نمی‌نویسد', async () => {
    route();
    renderCard();
    await settled('sarkhati-portfolio-status', PORTFOLIO_LABEL.no_source);
    const line = screen.getByTestId('sarkhati-portfolio-status').textContent ?? '';
    expect(line).toBe(PORTFOLIO_LABEL.no_source);
    expect(line).not.toMatch(FA_DIGIT);
    expect(screen.getByTestId('sarkhati-portfolio-error')).toBeDefined();
  });

  it('ردیف‌هایِ واقعی فقط ازِ پاسخِ سرور شمارده می‌شوند', async () => {
    route({ '/api/execution/portfolio': { ...PORTFOLIO_NONE, status: 'success',
      source: 'live', as_of: '2026-10-18T12:00:00+03:30', rows: [
        { symbol: 'فولاد', quantity: 1000 }, { symbol: 'شپنا', quantity: 200 }] } });
    renderCard();
    await settled('sarkhati-portfolio-status', PORTFOLIO_LABEL.success);
    const line = screen.getByTestId('sarkhati-portfolio-status').textContent ?? '';
    expect(line).toContain(PORTFOLIO_LABEL.success);
    expect(line).toMatch(FA_DIGIT);
    expect(screen.getByTestId('sarkhati-portfolio-asof')).toBeDefined();
  });
});
