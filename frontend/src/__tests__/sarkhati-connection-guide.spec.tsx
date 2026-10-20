// اتصال: مرحله‌های جدا، پیام «مرورگر آماده API تأیید نشده»، و نبودِ سبزِ جعلی.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiConnectionCard } from '@features/portfolio/components/sarkhati/SarkhatiConnectionCard';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

function step(key: string, title: string, status: string, action = '') {
  return { key, title, status, evidence: `${key}-evidence`, reason: `${key}-reason`,
    action, observed_at: '2026-10-20T21:00:00' };
}

const BASE_STEPS = [
  step('backend', 'Backend و نسخه', 'PASS'),
  step('host', 'Browser host', 'PASS'),
  step('cdp', 'CDP محلی', 'PASS'),
  step('page', 'صفحهٔ EasyTrader', 'PASS'),
  step('login', 'وضعیت ورود', 'UNVERIFIED'),
  step('session', 'دسترسی به حساب', 'BLOCKED', 'بررسی read-only'),
  step('contract', 'قرارداد API', 'UNVERIFIED'),
  step('read_only', 'پرسشِ read-only', 'BLOCKED'),
  step('account', 'منبع حساب/پرتفوی', 'BLOCKED'),
  step('capabilities', 'قابلیت‌های آداپتور', 'PASS'),
];
const DIAG = {
  status: 'success', app_version: '1.0.95', adapter: 'easytrader',
  state: 'BROWSER_READY_API_UNVERIFIED',
  state_label: 'مرورگر آماده است؛ هنوز دسترسی به حساب تأیید نشده است',
  steps: BASE_STEPS, next_action: 'بررسی read-only', secrets_stored: false,
};

function routes(diag: unknown = DIAG, host: unknown = { host: { healthy: true } }) {
  const calls: string[] = [];
  fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
    const u = String(url); calls.push(`${init?.method ?? 'GET'} ${u}`);
    if (u.includes('/connection/diagnose') || u.includes('/connection/verify')) {
      return Promise.resolve(json(diag));
    }
    if (u.includes('/connection/capture-session')) {
      return Promise.resolve(json({ status: 'success', code: 'CAPTURED',
        token_present: true, page_host: 'd.easytrader.ir', token: 'SECRET-TOKEN',
        secrets_returned: false, secrets_stored: false }));
    }
    if (u.includes('/browser-host')) return Promise.resolve(json(host));
    if (u.includes('/connect/verify')) return Promise.resolve(json({ status: 'success',
      verify: { state: 'CONNECTED', reason: 'از پرسشِ صریحِ کارگزاری',
        token_present: true,
        proof: { path: '/core/api/order', status: 200, kind: 'third-party-code-only' } },
      connect: {} }));
    if (u.includes('/connect')) return Promise.resolve(json({ status: 'success',
      last_verify: {}, browser: { open: false }, login_hosts_configured: [] }));
    if (u.includes('/config')) return Promise.resolve(json({ status: 'success',
      stored: {}, effective: {}, applies_on_restart: true }));
    if (u.includes('/portfolio')) return Promise.resolve(json({ status: 'no_source', rows: null }));
    return Promise.resolve(json({ status: 'success' }));
  });
  return calls;
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiConnectionCard /></QueryClientProvider>);
}

beforeEach(() => {
  fetchMock.mockReset();
  localStorage.setItem('sarkhati-auto-capture', '0');
});

describe('راهنمای اتصال', () => {
  it('شش قدم اصلی را نشان می‌دهد و بازبودن صفحه را اتصال نمی‌خواند', async () => {
    routes(); renderCard();
    await screen.findByTestId('connection-step-backend');
    expect(screen.getByTestId('sarkhati-connection-state'))
      .toHaveTextContent('مرورگر آماده');
    expect(screen.getByTestId('connection-step-backend')).toHaveTextContent('PASS');
    expect(screen.getByTestId('connection-step-session')).toHaveTextContent('BLOCKED');
    expect(screen.queryByText(/^CONNECTED$/)).toBeNull();
    expect(screen.getByTestId('connection-browser-ready-api-unverified'))
      .toHaveTextContent('هنوز مطمئن نیستیم');
  });

  it('صفحهٔ ورود، اقدام ورود دستی می‌دهد', async () => {
    routes({ ...DIAG, state: 'LOGIN_REQUIRED',
      state_label: 'مرورگر باز است؛ ورود دستی مالک لازم است',
      next_action: 'در پنجره وارد شوید',
      steps: BASE_STEPS.map((s) => s.key === 'login'
        ? { ...s, status: 'BLOCKED', action: 'در پنجره وارد شوید' } : s) });
    renderCard();
    expect(await screen.findByTestId('connection-login-needed')).toHaveTextContent('وارد کارگزاری');
  });

  it('host خاموش، علت و دکمهٔ بازکردن را نشان می‌دهد', async () => {
    routes({ ...DIAG, state: 'HOST_DOWN', state_label: 'Browser host در دسترس نیست',
      next_action: '«باز کردن پنجرهٔ اتصال» را بزنید',
      steps: BASE_STEPS.map((s) => s.key === 'host'
        ? { ...s, status: 'FAIL', action: 'باز کردن پنجره' } : s) },
    { host: { healthy: false } });
    renderCard();
    await screen.findByTestId('connection-step-host');
    expect(screen.getByTestId('connection-open-host')).toBeTruthy();
    expect(screen.queryByTestId('connection-capture-session')).toBeNull();
    expect(screen.getByTestId('sarkhati-connection-next')).toHaveTextContent('باز کردن');
  });

  it('خطای تشخیص را صریح نشان می‌دهد، نه وضعیت سبز', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(
      ({ ok: false, status: 400, json: () => Promise.resolve({ detail: 'down' }) }) as unknown as Response));
    renderCard();
    expect(await screen.findByTestId('connection-error')).toBeInTheDocument();
  });

  it('فرم قدیمی نشست داخل جزئیات فنی است، نه سطح اصلی', async () => {
    routes(); renderCard();
    await screen.findByTestId('connection-step-backend');
    const form = screen.getByTestId('sarkhati-session-form');
    expect(form.closest('details')).not.toBeNull();
  });

  it('بررسی وضعیت endpoint واقعی verify را صدا می‌زند', async () => {
    const calls = routes(); renderCard();
    await screen.findByTestId('connection-check');
    fireEvent.click(screen.getByTestId('connection-check'));
    await waitFor(() => expect(calls.some((c) => c === 'POST /api/execution/connect/verify')).toBe(true));
    expect(calls.some((c) => /\/order|\/dispatch/.test(c))).toBe(false);
    expect(await screen.findByTestId('connection-note')).toHaveTextContent('ارتباط با کارگزاری');
  });

  it('حالت read-only تأییدشده را از قرارداد نوشتنِ تأییدنشده جدا نشان می‌دهد', async () => {
    routes({ ...DIAG, state: 'READ_ONLY_VERIFIED',
      state_label: 'خواندن اطلاعات حساب تأیید شد؛ ارسال سفارش هنوز فعال نیست',
      steps: BASE_STEPS.map((s) => s.key === 'session' ? { ...s, status: 'PASS' }
        : s.key === 'read_only' ? { ...s, status: 'PASS' } : s) });
    renderCard();
    await waitFor(() => expect(screen.getByTestId('sarkhati-connection-state'))
      .toHaveTextContent('خواندن'));
    const chip = screen.getByTestId('sarkhati-connection-state');
    expect(chip).toHaveTextContent('ارسال');
    expect(screen.queryByTestId('connection-capture-session')).toBeNull();
  });

  it('دریافت خودکار نشست پیش‌فرض روشن است و بدون کلیک اجرا می‌شود', async () => {
    localStorage.removeItem('sarkhati-auto-capture');
    const calls = routes(); renderCard();
    const toggle = await screen.findByTestId('connection-auto-capture');
    expect(toggle).toHaveTextContent('روشن');
    await waitFor(() => expect(calls.some(
      (c) => c === 'POST /api/execution/connection/capture-session')).toBe(true));
    expect(await screen.findByTestId('connection-note')).toHaveTextContent('خودکار');
    expect(screen.queryByText(/SECRET-TOKEN/)).toBeNull();
  });

  it('دریافت نشست از مرورگر فقط متادیتا را می‌گیرد و هیچ توکنی نمایش نمی‌دهد', async () => {
    const calls = routes(); renderCard();
    const btn = await screen.findByTestId('connection-capture-session');
    fireEvent.click(btn);
    await waitFor(() => expect(calls.some(
      (c) => c === 'POST /api/execution/connection/capture-session')).toBe(true));
    expect(await screen.findByTestId('connection-note')).toHaveTextContent('فقط در حافظه');
    expect(screen.queryByText(/SECRET-TOKEN/)).toBeNull();
  });

  it('سطح اصلی شش‌قدمِ ساده است؛ شاهدِ خام فقط داخل جزئیات فنی می‌آید', async () => {
    routes(); renderCard();
    await screen.findByTestId('connection-summary');
    expect(screen.getAllByTestId(/^connection-summary-/)).toHaveLength(6);
    expect(screen.getByTestId('connection-summary-backend')).not.toHaveTextContent('PASS');
    const detail = screen.getByTestId('sarkhati-connection-technical');
    expect(detail).toContainElement(screen.getByTestId('connection-steps'));
    expect(screen.getByTestId('connection-step-backend')).toHaveTextContent('PASS');
  });
});
