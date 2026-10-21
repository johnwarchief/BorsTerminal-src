// src/__tests__/autoclicker-page.spec.tsx — صفحهٔ تنظیمات/آمادگی، بی‌ارسال
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AutoClickerPage from '@features/portfolio/routes/AutoClickerPage';

const api = vi.hoisted(() => ({
  settings: vi.fn(async (_id: string, _body: Record<string, unknown>) => ({ status: 'success' })),
  probe: vi.fn(async (_id: string) => ({ status: 'success', probe: { login: 'NOT_VISIBLE', origin_ok: true } })),
  prepare: vi.fn(async (_body: Record<string, unknown>) => ({ status: 'success', prepared_id: 'prep-1' })),
  trigger: vi.fn(async (_body: Record<string, unknown>) => ({ status: 'success' })),
  abort: vi.fn(async () => ({ status: 'success' })),
  order: vi.fn(async (_id: string) => ({ status: 'success', order: { status: 'dry_run' } })),
  refetchPortfolio: vi.fn(async () => ({})),
  refetchBp: vi.fn(async () => ({})),
  refetchStatus: vi.fn(async () => ({})),
}));

const ui = vi.hoisted(() => ({
  adapter: 'easytrader' as string,
  portfolio: null as Record<string, unknown> | null,
  bp: null as Record<string, unknown> | null,
}));

vi.mock('@features/portfolio/lib/orderClient', () => ({
  orderApi: {
    strategySettings: api.settings,
    strategyProbe: api.probe,
    strategyPrepare: api.prepare,
    strategyTrigger: api.trigger,
    strategyAbort: api.abort,
    strategyAbortIntent: api.abort,
    strategyOrder: api.order,
  },
  browserHostApi: { start: vi.fn(async () => ({ status: 'success' })) },
  useStrategies: () => ({
    data: {
      status: 'success', live_allowed: false,
      strategies: [{
        id: 'autoclicker', label: 'AutoClicker', kind: 'browser', available: true,
        configured: true, unavailable_reason: '', live_ready: false,
        settings: { strategy: 'autoclicker', enabled: true, mode: 'shadow', priority: 10,
          options: {
            form_symbol_selector: "[data-cy='order-form-header-symbol-name']",
            open_form_selector: 'button.order-buy-btn',
            price_selector: '#price', quantity_selector: '#quantity',
            submit_selector: "button[aria-label='ارسال خرید']",
            action_timeout_ms: 1200, preclick_check: true,
            intercept_pattern: '**/core/api/v2/order*', autofill: false,
            require_prefilled: true,
          }, updated_at: 1 },
        metrics: {}, outcomes: {}, last_result: null,
      }, {
        id: 'direct_api', label: 'Direct API', kind: 'http', available: true,
        configured: true, unavailable_reason: '', live_ready: false,
        settings: { strategy: 'direct_api', enabled: true, mode: 'live', priority: 0,
          options: {}, updated_at: 1 },
        metrics: {}, outcomes: {}, last_result: null,
      }],
    },
    isPending: false, isError: false,
  }),
  useBrowserHost: () => ({
    data: { host: { healthy: true, status: 'open', cdp_url: 'http://127.0.0.1:9223' } },
    isPending: false, refetch: vi.fn(),
  }),
  useExecutionStatus: () => ({
    data: { adapter: ui.adapter, session: { proven: true, state: 'connected' },
      live_enabled: false },
    isPending: false, isError: false, refetch: api.refetchStatus,
  }),
  useExecutionReadiness: () => ({
    data: { live_ready: false, blocking_count: 3,
      next_action: 'مجوزِ مالک و قراردادِ عملیاتی' },
    isPending: false, isError: false,
  }),
  useExecutionPortfolio: () => ({
    data: ui.portfolio, isPending: false, isFetching: false, error: null,
    refetch: api.refetchPortfolio,
  }),
  useBuyingPower: () => ({
    data: ui.bp, isPending: false, isFetching: false, error: null,
    refetch: api.refetchBp,
  }),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter><AutoClickerPage /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockClear());
  ui.adapter = 'easytrader';
  ui.portfolio = null;
  ui.bp = null;
  localStorage.clear();
});

describe('AutoClicker — تنظیمات و آمادگی', () => {
  it('آمادگی را از پاسخ می‌سازد و تنظیمات را shadow ذخیره می‌کند', async () => {
    renderPage();
    expect(screen.getByTestId('autoclicker-page')).toBeTruthy();
    expect(screen.getByTestId('autoclicker-gate-host').textContent).toContain('سبز');
    expect(screen.getByTestId('autoclicker-gate-prefill').textContent).toContain('سبز');
    fireEvent.click(screen.getByTestId('autoclicker-save'));
    await waitFor(() => expect(api.settings).toHaveBeenCalled());
    const body = api.settings.mock.calls[0][1] as Record<string, unknown>;
    expect(body.mode).toBe('shadow');
    const opts = body.options as Record<string, unknown>;
    expect(opts.autofill).toBe(false);
    expect(opts.require_prefilled).toBe(true);
    expect(opts.headless).toBe(false);
  });

  it('dry-run فقط با prepared_id و تأیید صریح اجرا می‌شود', async () => {
    renderPage();
    fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'فولاد' } });
    fireEvent.change(screen.getByTestId('autoclicker-price'), { target: { value: '1000' } });
    fireEvent.change(screen.getByTestId('autoclicker-qty'), { target: { value: '10' } });
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('autoclicker-dry-run')).toBeTruthy());
    expect(screen.getByTestId('autoclicker-dry-run')).toBeDisabled();
    fireEvent.click(screen.getByTestId('autoclicker-dry-ack'));
    await waitFor(() => expect(screen.getByTestId('autoclicker-dry-run')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('autoclicker-dry-run'));
    await waitFor(() => expect(api.trigger).toHaveBeenCalledWith({ prepared_id: 'prep-1' }));
  });

  it('هدف را به تهران می‌فرستد و intent_key پایدار می‌ماند تا «قصد تازه»', async () => {
    renderPage();
    fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'فولاد' } });
    fireEvent.change(screen.getByTestId('autoclicker-price'), { target: { value: '1000' } });
    fireEvent.change(screen.getByTestId('autoclicker-qty'), { target: { value: '10' } });
    fireEvent.change(screen.getByTestId('autoclicker-target'),
      { target: { value: '2026-10-22T08:45' } });
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalled());
    const first = api.prepare.mock.calls[0][0] as Record<string, unknown>;
    expect(first.target_tehran).toBe('2026-10-22T08:45');
    expect(typeof first.intent_key).toBe('string');
    expect(first.intent_key).toBeTruthy();
    fireEvent.click(screen.getByTestId('autoclicker-new-intent'));
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalledTimes(2));
    const second = api.prepare.mock.calls[1][0] as Record<string, unknown>;
    expect(second.intent_key).not.toBe(first.intent_key);
  });

  it('دو تب با همان فرم یک intent_key مشترک می‌گیرند', async () => {
    const fill = () => {
      fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'فولاد' } });
      fireEvent.change(screen.getByTestId('autoclicker-price'), { target: { value: '1000' } });
      fireEvent.change(screen.getByTestId('autoclicker-qty'), { target: { value: '10' } });
    };
    const first = renderPage();
    fill();
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalledTimes(1));
    const key1 = (api.prepare.mock.calls[0][0] as Record<string, unknown>).intent_key;
    first.unmount();
    renderPage();
    fill();
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalledTimes(2));
    const key2 = (api.prepare.mock.calls[1][0] as Record<string, unknown>).intent_key;
    expect(key2).toBe(key1);
  });

  it('مسیر API را با همان intent و بدونِ کلیک انتخاب می‌کند', async () => {
    // `direct_api` در پاسخِ strategies است؛ این تست انتخاب مسیر را قفل می‌کند.
    renderPage();
    fireEvent.click(screen.getByTestId('autoclicker-path-api'));
    fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'فولاد' } });
    fireEvent.change(screen.getByTestId('autoclicker-price'), { target: { value: '1000' } });
    fireEvent.change(screen.getByTestId('autoclicker-qty'), { target: { value: '10' } });
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(api.prepare).toHaveBeenCalled());
    const body = api.prepare.mock.calls[0][0] as Record<string, unknown>;
    expect(body.strategy).toBe('direct_api');
    expect(body.intent_key).toBeTruthy();
    expect(screen.getByTestId('autoclicker-result-empty')).toBeTruthy();
  });

  it('پاسخ scheduled را انتظار می‌خواند، نه شکست', async () => {
    api.trigger.mockResolvedValueOnce({ status: 'scheduled' });
    renderPage();
    fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'فولاد' } });
    fireEvent.change(screen.getByTestId('autoclicker-price'), { target: { value: '1000' } });
    fireEvent.change(screen.getByTestId('autoclicker-qty'), { target: { value: '10' } });
    fireEvent.change(screen.getByTestId('autoclicker-target'),
      { target: { value: '2026-10-22T08:45' } });
    fireEvent.click(screen.getByTestId('autoclicker-prepare'));
    await waitFor(() => expect(screen.getByTestId('autoclicker-dry-run')).toBeTruthy());
    fireEvent.click(screen.getByTestId('autoclicker-dry-ack'));
    fireEvent.click(screen.getByTestId('autoclicker-dry-run'));
    await waitFor(() => expect(screen.getByTestId('autoclicker-answer').textContent)
      .toContain('زمان‌بندی'));
  });

  it('مسیر API مفید حسابِ خوانده‌شده و برچسبِ sellable را نشان می‌دهد', async () => {
    ui.adapter = 'mofid';
    ui.portfolio = {
      status: 'success', state: 'PORTFOLIO_READ_ONLY_UNVERIFIED',
      sellable_state: 'CLIENT_DERIVED_UNVERIFIED',
      source: 'mofid:/Portfolio/Daily + /Order/customer/status (first-party Titan client)',
      positions: [{ isin: 'IRO1TEST0001', symbol: 'TEST', quantity: 1000,
        sellable_quantity: 850, open_sell: 50 }],
      error: null,
    };
    ui.bp = { status: 'success', state: 'BUYING_POWER_VERIFIED',
      value: 500000000, unit: 'IRR' };
    renderPage();
    fireEvent.click(screen.getByTestId('autoclicker-path-api'));
    await waitFor(() => expect(screen.getByTestId('autoclicker-mofid-account')).toBeTruthy());
    expect(screen.getByTestId('autoclicker-mofid-bp').textContent).toContain('IRR');
    expect(screen.getByTestId('autoclicker-mofid-bp').textContent).toContain('۵۰۰');
    expect(screen.getByTestId('autoclicker-mofid-portfolio').textContent)
      .toContain('CLIENT_DERIVED_UNVERIFIED');
    fireEvent.change(screen.getByTestId('autoclicker-symbol'), { target: { value: 'TEST' } });
    await waitFor(() => expect(screen.getByTestId('autoclicker-mofid-row').textContent)
      .toContain('۸۵۰'));
    fireEvent.click(screen.getByTestId('autoclicker-mofid-refresh'));
    await waitFor(() => expect(api.refetchPortfolio).toHaveBeenCalled());
    expect(api.refetchBp).toHaveBeenCalled();
    expect(api.refetchStatus).toHaveBeenCalled();
    expect(screen.getByTestId('autoclicker-gate-account').textContent).toContain('خوانده شد');
  });
});
