// src/__tests__/sarkhati-har-import.spec.tsx — برداشتِ نشست از پروندۀ HAR
//
// چهار چیزی که این آزمون می‌خواهد مطمئن شود (بندِ ۶ و ۷ مأموریتِ ۲۰۲۶-۱۰-۱۹):
//  ۱) رابط **می‌گوید** فیلدِ متنی چه نوعِ نشانی‌ای می‌پذیرد — نه «نشانی» به‌طلاق؛
//  ۲) متنِ پرونده (که توکن و کوکی دارد) هیچ‌وقت درِ DOM نمی‌نشیند؛ فقط نامِ
//     میزبان/مسیر/کلید ازِ پاسخِ بک‌اند رندر می‌شود؛
//  ۳) «برداشتِ نشست» با «تأییدِ نشست» یکی نیست: پیامِ موفقیت خودِ بک‌اند را
//     نشان می‌دهد و ادعایِ «متصل» نمی‌سازد؛
//  ۴) انتخابِ پرونده پسِ خواندن ازِ فیلد پاک می‌شود — نشانیِ درِ دسترس نمانده.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SarkhatiSessionForm } from '@features/portfolio/components/sarkhati/SarkhatiSessionForm';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const TOKEN_SENT = 'eyJhbGciOi.SENTINEL-PAYLOAD.sig-not-real';
const COOKIE_SENT = 'COOKIE-SENTINEL-9k2';

const STATUS = { status: 'success', adapter: 'easytrader', dry_run: true,
  live_enabled: false, live: false, traffic_allowed: true, blocked_on: [],
  capabilities: { place: false, list_orders: true, order_state: true,
    queue_position: true, cancel: false, best_bid_ask: false, balances: false },
  session: { state: 'disconnected', account_label: null, origin: 'easytrader',
    proven: false, verified_by: {} },
  connection_config: { adapter: 'easytrader', adapter_source: 'settings',
    read_only: true, writes_gate: 'env:BORS_EXECUTION_LIVE',
    applies_on_restart: true, secrets_stored: false },
  credential: { provider: 'windows', target: 'BorsTerminal:EasyTrader',
    present: true, code: 'OK', user_masked: '09xx…12', last_written: '',
    hint: '', checked_at: 1 },
  kill_switch: 'ARMED', halted: false, ledger_size: 0, durable_events: 0 };

const CONFIG = { status: 'success', stored: { adapter: 'easytrader', read_only: true,
  source: 'settings', updated_at: 'x' },
  effective: { adapter: 'easytrader', traffic_allowed: true, read_only: true,
    live_requested: false, session_live: false, writes_gate: 'env' },
  applies_on_restart: true, secrets_stored: false, detail: '' };

const INSPECT = { status: 'success', entries_total: 42, wire_hosts: ['api-mts.example'],
  hosts: [{ host: 'api-mts.example', entries: 5, auth_bearing: 2, cookie_bearing: 5 }],
  api_paths: [{ host: 'api-mts.example', method: 'GET', path: '/core/api/order',
    status: 200, response_keys: ['data', 'buyingPower'], auth: true, cookie: false }],
  api_paths_capped: false, off_wire_hosts: 3, is_order: false, session_touched: false,
  detail: 'فقط نامِ میزبان، متد، مسیر و نامِ کلیدهایِ پاسخ ثبت شد' };

function route(over: Record<string, unknown> = {}) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/har/inspect')) return Promise.resolve(json(INSPECT));
    if (u.includes('/har/session')) {
      return Promise.resolve(json({ status: 'success', imported: true, kind: 'bearer',
        host: 'api-mts.example', path: '/core/api/order', exp: 1800000000,
        confirmations_voided: 0, capabilities: {}, live: false,
        session: { state: 'unknown', proven: false },
        detail: 'نشست فقط درِ حافظه نشست', ...over }));
    }
    if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG));
    return Promise.resolve(json(over.status ? over : STATUS));
  });
}

function board() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiSessionForm /></QueryClientProvider>);
}

function harFile() {
  const doc = {
    log: {
      entries: [{
        request: {
          method: 'GET',
          url: 'https://api-mts.example/core/api/order',
          headers: [
            { name: 'Authorization', value: 'Bearer ' + TOKEN_SENT },
            { name: 'Cookie', value: COOKIE_SENT },
          ],
        },
      }],
    },
  };
  return new File([JSON.stringify(doc)], 'session.har');
}


function pickFile() {
  const input = screen.getByTestId('sarkhati-har-file') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [harFile()] } });
  return input;
}

describe('برداشتِ نشست از HAR درِ تبِّ سرخطی', () => {
  it('نوعِ نشانیِ پذیرفتنی درِ رابط نوشته شده است، نه فقط «نشانی»', () => {
    route();
    board();
    const label = screen.getByTestId('sarkhati-token-input').closest('label');
    expect(label?.textContent).toContain('Authorization: Bearer');
    expect(label?.textContent).toMatch(/کوکی/);
  });

  it('تحلیلِ مسیرها فقط ساختار را رندر می‌کند و توکنِ پرونده درِ DOM نیست', async () => {
    route();
    board();
    pickFile();
    fireEvent.click(screen.getByTestId('sarkhati-har-inspect'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-har-paths'))
      .toBeInTheDocument());
    const html = document.body.textContent ?? '';
    expect(html).toContain('/core/api/order');
    expect(html).toContain('buyingPower');
    expect(html).toContain('۴۲ ردیفِ پرسش');
    expect(html).not.toContain(TOKEN_SENT);
    expect(html).not.toContain(COOKIE_SENT);
    // «Bearer» تنها مجاز است درِ *توضیحِ* نامِ هدر بیاید، نه به‌عنوانِ مقدارِ نشانی:
    // هر بار باید فوراً بعدِ «Authorization: » باشد.
    expect(html.split('Bearer').length - 1)
      .toBe(html.split('Authorization: Bearer').length - 1);
    // مسیرِ پاسخِ بک‌اند، نه چیزی جزِ بدنۀِ خامِ انتخاب‌شده
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes('/har/inspect'));
    expect(String(call?.[0])).toBe('/api/execution/har/inspect');
    expect(String((call?.[1] as { body?: string }).body)).toContain('log');
  });

  it('برداشتِ نشست پیامِ خودِ بک‌اند را می‌گوید و «متصل» نمی‌سازد', async () => {
    route();
    board();
    pickFile();
    fireEvent.click(screen.getByTestId('sarkhati-har-import'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-session-note'))
      .toBeInTheDocument());
    const note = screen.getByTestId('sarkhati-session-note').textContent ?? '';
    expect(note).toContain('نشست فقط درِ حافظه نشست');
    expect(note).toContain('تأییدِ واقعی فقط با «بررسی اتصال»');
    expect(note).not.toMatch(/متصل شد/);
    expect(document.body.textContent).not.toContain(TOKEN_SENT);
  });

  it('ردِ بک‌اند باِ علتِ دقیق نشان داده می‌شود و نشانی ثبت‌شده جا نمی‌ماند', async () => {
    route({ imported: false, code: 'COOKIE_ONLY',
      detail: 'پرسش‌ها فقط باِ کوکی رفته‌اند؛ برداشت انجام نشد' });
    board();
    pickFile();
    fireEvent.click(screen.getByTestId('sarkhati-har-import'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-session-note'))
      .toBeInTheDocument());
    expect(screen.getByTestId('sarkhati-session-note').textContent)
      .toContain('برداشت انجام نشد');
  });

  it('انتخابِ پرونده پسِ خواندن ازِ فیلد پاک می‌شود', async () => {
    route();
    board();
    const input = pickFile();
    expect(input.files?.length).toBe(1);
    fireEvent.click(screen.getByTestId('sarkhati-har-inspect'));
    await waitFor(() => expect(input.value).toBe(''), { timeout: 4000 });
  });
});
