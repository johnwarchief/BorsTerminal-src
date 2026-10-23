// src/__tests__/autoclicker-round22-card.spec.tsx — نردبان + پیش‌نمایش + توقف
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Round22AutoClickerCard from '@features/portfolio/components/sarkhati/Round22AutoClickerCard';

const api = vi.hoisted(() => ({
  state: vi.fn(),
  createRun: vi.fn(async () => ({ status: 'success' })),
  check: vi.fn(async () => ({ status: 'success' })),
  arm: vi.fn(async () => ({ status: 'success' })),
  start: vi.fn(async () => ({ status: 'success' })),
  stop: vi.fn(async () => ({ status: 'success' })),
  reset: vi.fn(async () => ({ status: 'success' })),
  openPanel: vi.fn(async () => ({ status: 'success' })),
}));

vi.mock('@features/portfolio/lib/autoclickerClient', () => ({ autoclickerApi: api }));

const ORDER = ['browser_open', 'page_loaded', 'login_verified', 'panel_connected',
  'form_usable', 'symbol_side_detected', 'price_quantity_match',
  'submit_button_ready', 'constraints_checked', 'schedule_state'];

function stateView(over: Record<string, unknown> = {}) {
  const facts: Record<string, { status: string; detail: string; label: string }> = {};
  for (const k of ORDER) facts[k] = { status: 'PASS', detail: 'شاهد', label: k };
  return {
    status: 'success', app_version: '1.0.99', fact_order: ORDER, facts,
    run: {
      run_id: 'ac-1', state: 'ARMED', fired_actions: 0,
      config: { dry_run: true },
      preview: {
        max_orders_possible: 3, total_shares_possible: 3000,
        max_gross_value_rial: 30480000, total_actions: 3, dry_run: true,
        target_at_local: '2026-10-24T09:00:00.000+03:30',
        warning: 'هر کلیک می‌تواند سفارش بسازد',
      },
    },
    ceiling: { max_actions: 20, min_interval_ms: 300 },
    timezone: { name: 'Asia/Tehran', now_local: '2026-10-24T08:55:00.000+03:30' },
    ...over,
  };
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Round22AutoClickerCard />
    </QueryClientProvider>,
  );
}

describe('Round22AutoClickerCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.state.mockResolvedValue(stateView());
  });

  it('ده خانۀ نردبان را نشان می‌دهد', async () => {
    renderCard();
    await waitFor(() => expect(screen.getByTestId('autoclicker-fact-browser_open')).toBeTruthy());
    for (const k of ORDER) {
      expect(screen.getByTestId(`autoclicker-fact-${k}`)).toBeTruthy();
    }
    expect(screen.getByTestId('autoclicker-round22-ready').textContent).toContain('همهٔ شرط‌ها سبز');
  });

  it('پیش‌نمایشِ حداکثر سفارش/سهم/ارزش را از پاسخِ سرور می‌خواند', async () => {
    renderCard();
    await waitFor(() => expect(screen.getByTestId('ac22-preview')).toBeTruthy());
    const text = screen.getByTestId('ac22-preview').textContent ?? '';
    expect(text).toContain('حداکثر سفارش');
    expect(text).toContain('۳'); // ۳ اقدام با ارقامِ فارسی
    expect(text).toContain('۳۰,۴۸۰,۰۰۰');
  });

  it('توقفِ اضطراری همان اندپوینتِ stop را صدا می‌زند', async () => {
    renderCard();
    await waitFor(() => expect(screen.getByTestId('ac22-stop')).toBeTruthy());
    fireEvent.click(screen.getByTestId('ac22-stop'));
    await waitFor(() => expect(api.stop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('ac22-msg').textContent)
      .toContain('متوقف'));
  });

  it('شروع فقط پس از مسلح‌شدن فعال است', async () => {
    api.state.mockResolvedValue(stateView({
      run: { ...(stateView().run as Record<string, unknown>), state: 'DRAFT' },
    }));
    renderCard();
    await waitFor(() => expect(screen.getByTestId('ac22-start')).toBeTruthy());
    expect((screen.getByTestId('ac22-start') as HTMLButtonElement).disabled).toBe(true);
  });
});
