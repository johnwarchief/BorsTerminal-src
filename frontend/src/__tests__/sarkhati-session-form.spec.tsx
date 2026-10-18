// فرمِ نشانیِ نشست درِ کارتِ اتصالِ «سرخطی» (مأموریتِ 2026-10-18، مرحلۀ سه)
//
// این پرونده ده دروغی را می‌سنجد که یک رابطِ اتصال می‌تواند بگوید، و هیچ‌کدام
// ازِ آن‌ها با «کد هست» رد نمی‌شوند:
//  • نشانی درِ متنِ دکمه، یادداشت، tooltip یا لاگ نشت کند؛
//  • «ثبتِ نشست» با «تأییدِ نشست» یکی خوانده شود؛
//  • نشانیِ خالی راهی به سرور بفرستَد و «خطایِ سرور» بگیرَد؛
//  • پاسخِ نرسیده «پاک شد» گزارش شود؛
//  • نشستِ بدل «متصل» شود، یا تنظیمِ ذخیره‌شده «ارسالِ سفارش» را باز کند؛
//  • بازکردنِ صفحه یا فرستادنِ نشانی، سفارشی بسازَد یا پرسشی به میزبانِ
//    کارگزاری بفرستَد.
// هیچ‌جا درِ این پرونده درخواستِ واقعیِ کارگزاری شبیه‌سازی نمی‌شود: تنها آدرس‌هایِ
// `/api/execution/*` خودِ برنامه عبور می‌کنند، و همان‌ها هم fixture اند.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiSessionForm } from '@features/portfolio/components/sarkhati/SarkhatiSessionForm';
import { CODE_LABEL } from '@features/portfolio/lib/orderClient';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const SECRET = 'SEC-AbCdEf-0123456789';

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS_RO = { place: false, list_orders: true, order_state: true,
  queue_position: true, cancel: false, best_bid_ask: false, balances: false };

/** پاسخِ `/status` باِ نشستِ «هیچ نشانی درِ حافظه نیست» — حالتِ آغازینِ واقعی */
function statusNoToken(patch: Record<string, unknown> = {}) {
  return {
    status: 'success', adapter: 'easytrader', dry_run: true, live_enabled: false,
    live: false, live_requested: false, read_only: true, traffic_allowed: true,
    session_live: false, nothing_will_leave_the_machine: false, wire_hypothesis: true,
    blocked_on: [], capabilities: CAPS_RO,
    session: { state: 'disconnected', account_label: '', origin: 'easytrader',
      proven: false, verified_by: {} },
    connection_config: { adapter: 'mock', adapter_source: 'default', read_only: false,
      writes_gate: 'env:BORS_EXECUTION_LIVE', applies_on_restart: true, secrets_stored: false },
    kill_switch: 'ARMED', halted: false, ledger_size: 0, durable_events: 0,
    clock_source: 'system', clock_limit: 'ساعتِ سیستم',
    ...patch,
  };
}

/** پسِ `set_token` خودِ بک‌اند حالت را `unknown` می‌گذارد و `proven` را false */
const statusEntered = () => statusNoToken({
  session: { state: 'unknown', account_label: 'easytrader-session',
    origin: 'easytrader', proven: false, verified_by: {} },
  session_live: true, live: true,
});

const CONFIG_RO = {
  status: 'success',
  stored: { adapter: 'easytrader', read_only: true, source: 'settings', updated_at: 1 },
  effective: { adapter: 'easytrader', traffic_allowed: true, read_only: true,
    live_requested: false, session_live: false, writes_gate: 'env:BORS_EXECUTION_LIVE' },
  applies_on_restart: true, secrets_stored: false,
  detail: 'token/رمز/کوکی هیچ‌جا درِ این تنظیم نمی‌نشیند',
};

const OK_SET = { status: 'success', live: false, dry_run: true,
  session: { state: 'unknown', origin: 'easytrader', proven: false },
  // شکلِ قرارداد: شمارشِ بی‌اعتبارشده‌ها، نه بُولین (سنجشِ زندۀ /session: `0`)
  confirmations_voided: 2, capabilities: CAPS_RO,
  detail: 'token فقط درِ حافظه ماند؛ با restart می‌میرد' };

type Calls = Array<{ url: string; method: string; body: string }>;

/** مسیردهندهٔ fixture باِ یک اهرمِ حالَتی: `POST /session` همان‌جا پاسخِ `/status`
 *  را عوض می‌کند، دقیقاً مثلِ خودِ بک‌اند (نشستِ تازه ⇒ حالتِ تازه). */
function route(handlers: Record<string, unknown> = {}): { calls: Calls; secretSeen: () => boolean } {
  let status = statusNoToken();
  const calls: Calls = [];
  const secret = { seen: false };
  fetchMock.mockImplementation((url: unknown, init?: RequestInit) => {
    const u = String(url);
    const body = typeof init?.body === 'string' ? init.body : '';
    calls.push({ url: u, method: String(init?.method ?? 'GET'), body });
    if (body.includes(SECRET)) secret.seen = true;
    for (const [frag, reply] of Object.entries(handlers)) {
      if (u.includes(frag)) return Promise.resolve(json(reply));
    }
    if (u.includes('/api/execution/session')) {
      if (String(init?.method) === 'POST') status = statusEntered();
      if (String(init?.method) === 'DELETE') status = statusNoToken();
      return Promise.resolve(json(OK_SET));
    }
    if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG_RO));
    if (u.includes('/api/execution/status')) return Promise.resolve(json(status));
    if (u.endsWith('/api/execution/connect')) {
      return Promise.resolve(json({ status: 'success', browser: { open: false },
        traffic_mode: 'read_only', session_proven: false, last_verify: null }));
    }
    if (u.includes('/api/execution/portfolio')) {
      return Promise.resolve(json({ status: 'unverified_session', rows: null,
        error: 'بی‌نشانی هیچ پرسشی به کارگزاری نمی‌رود' }));
    }
    return Promise.resolve(json({ status: 'success' }));
  });
  return { calls, secretSeen: () => secret.seen };
}

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><SarkhatiSessionForm /></QueryClientProvider>);
}

/** انتظار برایِ *محتوا*، نه وجودِ گره: چیپ‌ها بی‌داده هم رندر می‌شوند */
async function settled(testId: string, want: RegExp | string) {
  await waitFor(() => {
    const el = screen.queryByTestId(testId);
    const text = el?.textContent ?? '';
    expect(el, testId + ' هنوز رندر نشده').not.toBeNull();
    expect(want instanceof RegExp ? want.test(text) : text.includes(want),
      testId + ' = ' + text).toBe(true);
  });
}

const gateText = (key: string) => screen.getByTestId(`sarkhati-gate-${key}`).textContent ?? '';
const gateTitle = (key: string) =>
  screen.getByTestId(`sarkhati-gate-${key}`).getAttribute('title') ?? '';

let logs: string[] = [];
beforeEach(() => {
  fetchMock.mockReset();
  logs = [];
  for (const m of ['log', 'warn', 'error', 'info'] as const) {
    vi.spyOn(console, m).mockImplementation((...a: unknown[]) => {
      logs.push(a.map(String).join(' '));
      return undefined;
    });
  }
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe('پنهان‌نگهداشتنِ نشانیِ نشست', () => {
  it('ورودی ماسک است و نشانی نه درِ متنِ صفحه می‌مانَد نه درِ هیچ attribute', async () => {
    const r = route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    const input = screen.getByTestId('sarkhati-token-input') as HTMLInputElement;
    expect(input.type).toBe('password');
    fireEvent.change(input, { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await waitFor(() => expect(r.calls.some((c) => c.method === 'POST')).toBe(true));
    expect(input.value).toBe('');
    const html = document.body.innerHTML + document.body.textContent;
    expect(html).not.toContain(SECRET);
    for (const el of Array.from(document.querySelectorAll('[title], [aria-label]'))) {
      expect(el.getAttribute('title') ?? '').not.toContain(SECRET);
      expect(el.getAttribute('aria-label') ?? '').not.toContain(SECRET);
    }
    expect(logs.join('\n')).not.toContain(SECRET);
  });

  it('هیچ لاگی نشانی را نمی‌بینَد، حتی وقتی پاسخِ سرویس خطا است', async () => {
    route({ '/api/execution/session': { status: 'error', code: 'UNSUPPORTED',
      detail: 'آداپتورِ فعال token نمی‌پذیرد (adapter=mock)' } });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', CODE_LABEL.UNSUPPORTED);
    expect(logs.join('\n')).not.toContain(SECRET);
    expect(document.body.textContent ?? '').not.toContain(SECRET);
  });
});

describe('ورودیِ نامعتبر و بی‌محتوا', () => {
  it('بی‌نشانی هیچ درخواستی نمی‌رود — «ثبتِ نشست» خاموش است', async () => {
    const r = route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    expect((screen.getByTestId('sarkhati-token-save') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    const posts = r.calls.filter((c) => c.method === 'POST' || c.method === 'DELETE');
    expect(posts).toEqual([]);
  });

  it('فاصلهٔ خالی نشانی نیست: نه دکمه روشن می‌شود نه درخواستی می‌رود', async () => {
    const r = route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: '   ' } });
    expect((screen.getByTestId('sarkhati-token-save') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    expect(r.calls.filter((c) => c.method === 'POST')).toEqual([]);
  });

  it('ردِ بک‌اند (UNSUPPORTED) باِ متنِ خودش خوانده می‌شود و «ثبت شد» نمی‌گوید', async () => {
    route({ '/api/execution/session': { status: 'error', code: 'UNSUPPORTED',
      detail: 'آداپتورِ فعال token نمی‌پذیرد (adapter=mock)' } });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    const note = await screen.findByTestId('sarkhati-session-note');
    expect(note.textContent ?? '').toContain(CODE_LABEL.UNSUPPORTED);
    expect(note.textContent ?? '').toContain('adapter=mock');
    expect(note.textContent ?? '').not.toContain('تأیید شد');
    expect(gateText('proven')).not.toContain('تأیید شد');
  });

  it('MISSING_TOKEN هم همان‌طور: پیامِ سرویس، نه ادعایِ رابط', async () => {
    route({ '/api/execution/session': { status: 'error', code: 'MISSING_TOKEN',
      detail: 'هیچ نشانی داده نشد — نشست پاک نمانده' } });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', CODE_LABEL.MISSING_TOKEN);
  });
});

describe('خطا و نرسیدنِ پاسخ', () => {
  it('پاسخِ نرسیده «پاک شد» نمی‌گوید؛ فقط علتِ خطا نوشته می‌شود', async () => {
    fetchMock.mockImplementation((url: unknown) => {
      const u = String(url);
      if (u.includes('/api/execution/session')) return Promise.reject(new Error('timeout'));
      if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG_RO));
      if (u.includes('/api/execution/status')) return Promise.resolve(json(statusNoToken()));
      return Promise.resolve(json({ status: 'success' }));
    });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', /timeout|نامعلوم/);
    expect(gateText('proven')).toBe('تأیید نشده');
    expect(document.body.textContent ?? '').not.toContain('پاک شد');
    expect(screen.getByTestId('sarkhati-token-input')).toHaveValue('');
  });

  it('پاسخِ ۵۰۰ یک‌بار می‌آزماید و دوباره نشانی را نمی‌فرستَد', async () => {
    fetchMock.mockImplementation((url: unknown, init?: RequestInit) => {
      const u = String(url);
      const method = String(init?.method ?? 'GET');
      if (u.includes('/api/execution/session') && method === 'POST') {
        return Promise.resolve({ ok: false, status: 500,
          json: () => Promise.resolve({}) } as unknown as Response);
      }
      if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG_RO));
      if (u.includes('/api/execution/status')) return Promise.resolve(json(statusNoToken()));
      return Promise.resolve(json({ status: 'success' }));
    });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', /۵۰۰|500/);
    const posts = fetchMock.mock.calls.filter((c) =>
      String(c[0]).includes('/api/execution/session') && String(c[1]?.method) === 'POST');
    expect(posts).toHaveLength(1);
  });
});

describe('چهار وضعیت ازِ هم جدا می‌مانند', () => {
  it('پسِ «ثبتِ نشست»: وارد شد بله، تأیید نه، ارسال نه', async () => {
    const r = route();
    renderForm();
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-gate-entered', 'نشانی وارد شد');
    expect(gateText('proven')).toBe('تأیید نشده');
    expect(gateText('writes')).toBe('خاموش');
    const post = r.calls.find((c) => c.method === 'POST' && c.url.includes('/session'));
    expect(post?.body).toBe(JSON.stringify({ token: SECRET }));
    await settled('sarkhati-session-note', '۲ تأییدِ پیشین بی‌اعتبار شد');
  });

  it('پسِ «پاک کردنِ نشست» رابط برمی‌گردد به «نشانی وارد نشده»', async () => {
    route();
    renderForm();
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-gate-entered', 'نشانی وارد شد');
    fireEvent.click(screen.getByTestId('sarkhati-token-clear'));
    await waitFor(() => expect(fetchMock.mock.calls.some((c) =>
      String(c[0]).includes('/api/execution/session') && String(c[1]?.method) === 'DELETE')).toBe(true));
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    expect(gateText('proven')).toBe('تأیید نشده');
  });

  it('نشستِ بدل باِ `proven: true` هم «تأیید شد» نمی‌گیرد', async () => {
    route({ '/api/execution/status': statusNoToken({ adapter: 'mock',
      session: { state: 'connected', origin: 'mock', proven: true,
        verified_by: { path: '/x', kind: 'observed-read-only' } } }) });
    renderForm();
    await settled('sarkhati-gate-proven', 'بدل');
    expect(gateText('proven')).not.toContain('تأیید شد');
    expect(gateText('entered')).toContain('بدل');
  });

  it('تنظیمِ ذخیره‌شدۀ «فقط‌خواندنی» گیتِ نوشتن را باز نمی‌کند', async () => {
    route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره شد و مؤثر است');
    expect(gateText('writes')).toBe('خاموش');
    expect(gateTitle('writes')).toContain('BORS_EXECUTION_LIVE');
    expect(screen.queryByTestId('sarkhati-writes-switch')).toBeNull();
  });

  it('تأییدِ مسیرِ فرضی باِ تأییدِ دیدہ‌شدہ یکی نیست', async () => {
    route({ '/api/execution/status': statusNoToken({ live: true, session_live: true,
      session: { state: 'connected', origin: 'easytrader', proven: true,
        verified_by: { path: '/core/api/order', hypothesis: true } } }) });
    renderForm();
    await settled('sarkhati-gate-proven', 'تأییدِ مسیرِ فرضی');
    expect(gateTitle('proven')).toContain('/core/api/order');
  });
  it('پاسخِ بی‌شکل (نه success نه code) «ثبت شد» نمی‌شود', async () => {
    route({ '/api/execution/session': {} });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', 'پاسخِ سرویس خوانا نبود');
    expect(gateText('proven')).toBe('تأیید نشده');
    // سنجش ازِ خودِ سطرِ وضعیت و سطرِ پاسخ است، نه ازِ کلِ صفحه: بلوکِ راهنما
    // عمدلاً می‌گوید «تأیید شد» تنها با «بررسی اتصال» می‌آید.
    expect(screen.getByTestId('sarkhati-session-note').textContent ?? '')
      .not.toContain('تأیید شد');
  });

  it('صفرِ بی‌اعتبارشده سطرِ اضافه نمی‌سازد (کنترلِ منفیِ همان شمارش)', async () => {
    route({ '/api/execution/session': { ...OK_SET, confirmations_voided: 0 } });
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-session-note', 'token فقط درِ حافظه ماند');
    expect(screen.getByTestId('sarkhati-session-note').textContent ?? '')
      .not.toContain('بی‌اعتبار');
  });

  it('نشستِ درِ حافظه باِ restart برنمی‌گردد: بارگذاریِ تازه «نشانی وارد نشده» است', async () => {
    route();
    const first = renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-gate-entered', 'نشانی وارد شد');
    first.unmount();
    // پروسۀ تازه: بک‌اند دیگر نشانی ندارد (token فقط درِ حافظه بود)
    fetchMock.mockImplementation((url: unknown) => {
      const u = String(url);
      if (u.includes('/api/execution/config')) return Promise.resolve(json(CONFIG_RO));
      if (u.includes('/api/execution/status')) return Promise.resolve(json(statusNoToken()));
      return Promise.resolve(json({ status: 'success' }));
    });
    renderForm();
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    expect(gateText('proven')).toBe('تأیید نشده');
    expect(gateText('writes')).toBe('خاموش');
  });

  it('درِ این فرم هیچ کنترلی برایِ سفارش نیست؛ فقط دو درِ نشست', async () => {
    route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    const ids = Array.from(screen.getByTestId('sarkhati-session-form')
      .querySelectorAll('[data-testid]'))
      .map((el) => el.getAttribute('data-testid') ?? '');
    expect(ids).toEqual(expect.arrayContaining(
      ['sarkhati-token-input', 'sarkhati-token-save', 'sarkhati-token-clear']));
    expect(ids.filter((id) => /dispatch|preflight|prepare|cancel|submit|order/i.test(id))).toEqual([]);
  });
});

describe('هیچ ترافیکِ سفارشی ازِ این فرم نمی‌رود', () => {
  it('بازکردنِ فرم فقط GETهایِ خودیِ برنامه است: صفر نوشتن، صفر میزبانِ بیرونی', async () => {
    const r = route();
    renderForm();
    await settled('sarkhati-gate-config', 'ذخیره');
    const writes = r.calls.filter((c) => c.method !== 'GET');
    expect(writes).toEqual([]);
    r.calls.forEach((c) => expect(c.url).toMatch(/^\/api\/execution\//));
    expect(r.secretSeen()).toBe(false);
  });

  it('هیچ درِ سفارشی (preflight/prepare/dispatch/cancel) صدا نمی‌کند، نه باِ ثبتِ نشانی و نه باِ پاککردنش', async () => {
    route();
    renderForm();
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    fireEvent.change(screen.getByTestId('sarkhati-token-input'), { target: { value: SECRET } });
    fireEvent.click(screen.getByTestId('sarkhati-token-save'));
    await settled('sarkhati-gate-entered', 'نشانی وارد شد');
    fireEvent.click(screen.getByTestId('sarkhati-token-clear'));
    await settled('sarkhati-gate-entered', 'نشانی وارد نشده');
    const orderish = fetchMock.mock.calls.filter((c) =>
      /preflight|prepare|dispatch|cancel|\/order|hold|submit/i.test(String(c[0])));
    expect(orderish).toEqual([]);
  });
});
