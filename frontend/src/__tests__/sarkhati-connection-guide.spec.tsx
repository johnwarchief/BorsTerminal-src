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
  step('session', 'نشست API', 'BLOCKED', 'بررسی read-only'),
  step('contract', 'قرارداد API', 'UNVERIFIED'),
  step('read_only', 'پرسشِ read-only', 'BLOCKED'),
  step('account', 'منبع حساب/پرتفوی', 'BLOCKED'),
  step('capabilities', 'قابلیت‌های آداپتور', 'PASS'),
];
const DIAG = {
  status: 'success', app_version: '1.0.95', adapter: 'easytrader',
  state: 'BROWSER_READY_API_UNVERIFIED',
  state_label: 'مرورگر آماده است؛ اتصال API کارگزاری هنوز تأیید نشده است',
  steps: BASE_STEPS, next_action: 'بررسی read-only', secrets_stored: false,
};

function routes(diag: unknown = DIAG, host: unknown = { host: { healthy: true } }) {
  const calls: string[] = [];
  fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
    const u = String(url); calls.push(`${init?.method ?? 'GET'} ${u}`);
    if (u.includes('/connection/diagnose') || u.includes('/connection/verify')) {
      return Promise.resolve(json(diag));
    }
    if (u.includes('/browser-host')) return Promise.resolve(json(host));
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

beforeEach(() => fetchMock.mockReset());

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
      .toHaveTextContent('هنوز تأیید نشده');
  });

  it('صفحهٔ ورود، اقدام ورود دستی می‌دهد', async () => {
    routes({ ...DIAG, state: 'LOGIN_REQUIRED',
      state_label: 'مرورگر باز است؛ ورود دستی مالک لازم است',
      next_action: 'در پنجره وارد شوید',
      steps: BASE_STEPS.map((s) => s.key === 'login'
        ? { ...s, status: 'BLOCKED', action: 'در پنجره وارد شوید' } : s) });
    renderCard();
    expect(await screen.findByTestId('connection-login-needed')).toHaveTextContent('وارد EasyTrader');
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

  it('بررسی وضعیت فقط endpoint تشخیص را صدا می‌زند', async () => {
    const calls = routes(); renderCard();
    await screen.findByTestId('connection-check');
    fireEvent.click(screen.getByTestId('connection-check'));
    await waitFor(() => expect(calls.some((c) => c === 'POST /api/execution/connection/verify')).toBe(true));
    expect(calls.some((c) => /\/order|\/dispatch/.test(c))).toBe(false);
  });
});
