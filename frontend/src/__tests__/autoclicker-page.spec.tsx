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
}));

vi.mock('@features/portfolio/lib/orderClient', () => ({
  orderApi: {
    strategySettings: api.settings,
    strategyProbe: api.probe,
    strategyPrepare: api.prepare,
    strategyTrigger: api.trigger,
    strategyAbort: api.abort,
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
      }],
    },
    isPending: false, isError: false,
  }),
  useBrowserHost: () => ({
    data: { host: { healthy: true, status: 'open', cdp_url: 'http://127.0.0.1:9223' } },
    isPending: false, refetch: vi.fn(),
  }),
  useExecutionStatus: () => ({
    data: { session: { proven: true, state: 'connected' }, live_enabled: false },
    isPending: false, isError: false,
  }),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter><AutoClickerPage /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockClear());
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
});
