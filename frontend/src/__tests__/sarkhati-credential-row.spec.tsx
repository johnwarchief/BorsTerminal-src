// src/__tests__/sarkhati-credential-row.spec.tsx — سطرِ «اعتبارنامۀ ویندوز» درِ کارتِ اتصال
//
// سه دروغی که این سطر نباید بگوید:
//  ۱) «اعتبارنامه هست» ≠ «وارد شده‌ایم» — متنِ رابط فقط «هست · نامِ پوشیده» است؛
//  ۲) نامِ کاملِ کاربری (شمارۀ موبایل) یا رمز نباید هیچ‌جا درِ DOM باشد؛
//  ۳) «پاسخی نیامده» با «نیست» یکی نیست — اولی خرابیِ در است، دومی صفرِ واقعی.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SarkhatiConnectionCard } from '@features/portfolio/components/sarkhati/SarkhatiConnectionCard';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS_RO = { place: false, list_orders: true, order_state: true,
  queue_position: true, cancel: false, best_bid_ask: false, balances: false };
const FULL_USER = '0312897911';
const SECRET = 'DUMMY-NOT-A-REAL-PASSWORD';

function statusWith(credential: unknown) {
  return {
    status: 'success', adapter: 'easytrader', dry_run: true, live_enabled: false,
    live: true, live_requested: false, read_only: true, traffic_allowed: true,
    nothing_will_leave_the_machine: false, wire_hypothesis: true, blocked_on: [],
    capabilities: CAPS_RO,
    session: { state: 'disconnected', account_label: null, origin: 'easytrader',
      proven: false, verified_by: {} },
    connection_config: { adapter: 'easytrader', adapter_source: 'settings',
      read_only: true, writes_gate: 'env:BORS_EXECUTION_LIVE',
      applies_on_restart: true, secrets_stored: false },
    ...(credential === undefined ? {} : { credential }),
    kill_switch: 'ARMED', halted: false, ledger_size: 0, durable_events: 0,
  };
}

const CONNECT = { status: 'success', states_supported: [], browser: { open: false },
  allowed_hosts: [], login_hosts_configured: [], secrets_stored: false,
  traffic_mode: 'read_only', session_proven: false, last_verify: null };
const PORTFOLIO = { status: 'no_source', adapter: 'easytrader', live: false,
  session_proven: false, as_of: null, source: 'none', rows: null, cached_at: null,
  error: null };

function route(statusBody: unknown) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.endsWith('/api/execution/status')) return Promise.resolve(json(statusBody));
    if (u.endsWith('/api/execution/connect')) return Promise.resolve(json(CONNECT));
    if (u.endsWith('/api/execution/portfolio')) return Promise.resolve(json(PORTFOLIO));
    if (u.endsWith('/api/execution/config')) {
      return Promise.resolve(json({ status: 'success', stored: {}, effective: {},
        applies_on_restart: true, secrets_stored: false, detail: '' }));
    }
    return Promise.resolve(json({ status: 'success' }));
  });
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiConnectionCard /></QueryClientProvider>);
}

describe('سطرِ اعتبارنامۀ ویندوز', () => {
  it('هست ⇒ «هست» با نامِ پوشیده، و نه نامِ کامل و نه رمز درِ DOM', async () => {
    // عمداً بدنه‌ای می‌دهیم که *انگار* بک‌اند رمز و نامِ کامل را فاش کرده است:
    // اگر روزی رابط این فیلدها را رندر کند، همین تست می‌گیردش — وگرنه سنسور
    // رویِ داده‌ای که هیچ‌وقت نبود سبز می‌شد.
    route(statusWith({ provider: 'windows-credential-manager',
      target: 'BorsTerminal:EasyTrader', present: true, code: 'OK',
      user_masked: '03*******1', user: FULL_USER, password: SECRET, blob_bytes: 24,
      last_written: '2026-10-19T00:21:32', hint: '', checked_at: 1 }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('sarkhati-credential-state')
      .getAttribute('data-code')).toBe('OK'));
    const el = screen.getByTestId('sarkhati-credential-state');
    expect(el.textContent).toContain('هست');
    expect(el.textContent).toContain('03*******1');
    const html = document.body.innerHTML;
    expect(html).not.toContain(FULL_USER);
    expect(html).not.toContain(SECRET);
    expect(screen.queryByTestId('sarkhati-credential-hint')).toBeNull();
  });

  it('نیست ⇒ «نیست» + راهنمایِ ذخیره، بدونِ اینکه «وارد شدیم» گفته شود', async () => {
    route(statusWith({ provider: 'windows-credential-manager',
      target: 'BorsTerminal:EasyTrader', present: false, code: 'MISSING',
      user_masked: '', last_written: null,
      hint: 'اعتبارنامه‌ای باِ نشانیِ BorsTerminal:EasyTrader نیست', checked_at: 2 }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('sarkhati-credential-state')
      .getAttribute('data-code')).toBe('MISSING'));
    expect(screen.getByTestId('sarkhati-credential-state').textContent).toContain('نیست');
    expect(screen.getByTestId('sarkhati-credential-hint').textContent)
      .toContain('BorsTerminal:EasyTrader');
  });

  it('سرویس پاسخ ندهد ⇒ «پاسخی نیامده»، نه «نیست»', async () => {
    fetchMock.mockImplementation(() => Promise.reject(new Error('down')));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('sarkhati-credential-state'))
      .toBeTruthy());
    const el = screen.getByTestId('sarkhati-credential-state');
    expect(el.textContent).toContain('پاسخی نیامده');
    expect(el.textContent).not.toContain('نیست');
  });

  it('ساختارِ خوانده‌نشده ⇒ متنِ روشن، بی‌ادعایِ ورود', async () => {
    route(statusWith({ provider: 'windows-credential-manager',
      target: 'BorsTerminal:EasyTrader', present: false, code: 'MALFORMED',
      user_masked: '', last_written: null, hint: 'دوباره ذخیره‌اش کنید', checked_at: 3 }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('sarkhati-credential-state')
      .getAttribute('data-code')).toBe('MALFORMED'));
    expect(screen.getByTestId('sarkhati-credential-state').textContent)
      .toContain('ساختارش خوانده نشد');
    expect(screen.getByTestId('sarkhati-credential-hint').textContent)
      .toContain('دوباره');
  });
});
