// تستِ پنلِ ربات (فاز ۳ مأموریتِ ۱۴۰-۰۷-۴)
//
// چیزی که سنجیده می‌شود «بودنِ دکمه» نیست: رابط نباید چیزی را که بک‌اند نگفته
// است ادعا کند. چهار ادعایِ دروغینِ ممکن این‌جا قفل می‌شوند:
//  ۱) اجرایِ واقعی با قفلِ بسته قابلِ فعال‌شدن نیست و دکمه‌اش غیرفعال است؛
//  ۲) `no_data` «موفق» خوانده نمی‌شود؛
//  ۳) پاسخِ نرسیده (خطایِ شبکه) «اجرا شد» نمی‌شود — حالتِ جدا می‌گیرد؛
//  ۴) هیچ وعدهٔ «اولی در صف» یا «اجرایِ قطعی» درِ متنِ پنل نوشته نمی‌شود.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BotPanel } from '@features/portfolio/components/BotPanel';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS_ON = { place: true, list_orders: true, order_state: true, queue_position: false,
  cancel: false, best_bid_ask: false, balances: false };
const CAPS_OFF = { place: false, list_orders: false, order_state: false, queue_position: false,
  cancel: false, best_bid_ask: false, balances: false };

function statusBody(patch: Record<string, unknown> = {}) {
  return {
    status: 'ok',
    config: { enabled: true, mode: 'paper', preset: 'trend', chain: [], fund_mode: 'standard',
      logic: 'and', sizing_fraction: 0.05, max_orders: 1, max_order_value: 2e8,
      max_symbol_exposure: null, max_total_exposure: null, max_daily_loss: null,
      max_stale_sessions: 1, start_cash: 1e8, commission_bps: 30, slippage_bps: 10,
      max_volume_share: 0.02 },
    kill: 'ARMED', halted: false,
    live_gates: { env_live: false, adapter: 'mock', session: 'none', capabilities: CAPS_OFF,
      live_capable: false, dry_run: true, all_open: false },
    confirm_phrase: 'اجرایِ واقعیِ سرخطی را تأیید می‌کنم',
    account: { equity: 100_000_000, cash: 95_000_000, positions: 2, realized_total: -1_000_000 },
    last_runs: [], auto_run: false,
    note: 'ربات تنها با POST /api/bot/run اجرا می‌شود',
    ...patch,
  };
}

const RUN_OK = { status: 'ok', run: { at: '2026-10-15T10:00:00', session: '20261014', bars: 6,
  symbols: 6, symbols_in: 14, unpriced: ['بنیرو', 'غمینو'], expired: [],
  prev_session: '20261013', mode: 'paper', ms: 41,
  decisions: [{ date: '20261014', signals: 3, dispatched: 1, rejected: 2,
    equity: 100_400_000, halt_state: 'ARMED', notes: ['stale: وخار'] }] } };

function route(body: Record<string, unknown>) {
  fetchMock.mockImplementation((input: string | URL | Request) => {
    const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
    if (url.includes('/api/bot/history')) return Promise.resolve(json({ status: 'ok', runs: [], events: [], account: {} }));
    if (url.includes('/api/bot/status')) return Promise.resolve(json(body));
    return Promise.resolve(json({ status: 'ok' }));
  });
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}><BotPanel /></QueryClientProvider>);
}

beforeEach(() => { fetchMock.mockReset(); });

describe('پنلِ ربات', () => {
  it('سطرِ وضعیت ازِ خودِ API ساخته می‌شود، نه ازِ حدس', async () => {
    route(statusBody());
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('bot-panel')).toBeInTheDocument());
    expect(await screen.findByText(/۲ موقعیت/)).toBeInTheDocument();
    expect(screen.getByText('آماده')).toBeInTheDocument();
  });

  it('دکمهٔ انتقال به اجرایِ واقعی با قفلِ بسته غیرفعال می‌ماند', async () => {
    route(statusBody());
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-toggle-open'));
    const btn = await screen.findByTestId('bot-live-arm');
    expect(btn).toBeDisabled();
    expect(screen.getAllByText(/BORS_EXECUTION_LIVE/).length).toBeGreaterThan(0);
    expect(screen.getByText(/اجرایِ واقعی بسته است/)).toBeInTheDocument();
  });

  it('با سه قفلِ باز هم باید عبارتِ تأیید نوشته شود', async () => {
    route(statusBody({
      live_gates: { env_live: true, adapter: 'easytrader', session: 'connected',
        capabilities: CAPS_ON, live_capable: true, dry_run: false, all_open: true },
    }));
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-toggle-open'));
    const btn = await screen.findByTestId('bot-live-arm');
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByTestId('bot-live-confirm'),
      { target: { value: 'اجرایِ واقعیِ سرخطی را تأیید می‌کنم' } });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);
    await waitFor(() => expect(fetchMock.mock.calls
      .some((c) => String(c[0]).includes('/api/bot/config'))).toBe(true));
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes('/api/bot/config'))!;
    expect(JSON.parse(String((call[1] as RequestInit).body))).toMatchObject({ mode: 'live' });
  });

  it('no_data «موفق» خوانده نمی‌شود', async () => {
    route(statusBody());
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
      if (url.includes('/api/bot/run')) return Promise.resolve(json({ status: 'no_data', message: 'بی‌اقدام' }));
      if (url.includes('/api/bot/history')) return Promise.resolve(json({ status: 'ok', runs: [], events: [], account: {} }));
      return Promise.resolve(json(statusBody()));
    });
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-run'));
    expect(await screen.findByText(/داده‌ای نبود/)).toBeInTheDocument();
    expect(screen.queryByText(/نشست اجرا شد/)).not.toBeInTheDocument();
  });

  it('پاسخِ نرسیده حالتِ «نامعلوم» می‌گیرد، نه «اجرا شد»', async () => {
    route(statusBody());
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
      if (url.includes('/api/bot/run')) return Promise.reject(new Error('network down'));
      if (url.includes('/api/bot/history')) return Promise.resolve(json({ status: 'ok', runs: [], events: [], account: {} }));
      return Promise.resolve(json(statusBody()));
    });
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-run'));
    expect(await screen.findByText(/نامعلوم/, {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByText(/نشست اجرا شد/)).not.toBeInTheDocument();
  });

  it('بی‌پاسخ، درخواستِ نوشتنی دوباره ارسال نمی‌شود (هیچ retry کور درِ مسیرِ ربات)', async () => {
    route(statusBody());
    let attempts = 0;
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
      if (url.includes('/api/bot/run')) { attempts += 1; return Promise.reject(new Error('boom')); }
      if (url.includes('/api/bot/history')) return Promise.resolve(json({ status: 'ok', runs: [], events: [], account: {} }));
      return Promise.resolve(json(statusBody()));
    });
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-run'));
    await screen.findByText(/نامعلوم/, {}, { timeout: 4000 });
    expect(attempts).toBe(1);
  });

  it('اجرایِ کاغذیِ موفق، نشست و شمارها را ازِ پاسخ نشان می‌دهد', async () => {
    route(statusBody());
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
      if (url.includes('/api/bot/run')) return Promise.resolve(json(RUN_OK));
      if (url.includes('/api/bot/history')) return Promise.resolve(json({ status: 'ok', runs: RUN_OK.run, events: [], account: {} }));
      return Promise.resolve(json(statusBody()));
    });
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-run'));
    expect(await screen.findByText(/۲۰۲۶۱۰۱۴/)).toBeInTheDocument();
    expect(screen.getByText(/۱ تصمیم/)).toBeInTheDocument();
  });

  it('خطاهایِ اعتبارسنجیِ پیکربندی درِ پنل خوانده می‌شود', async () => {
    route(statusBody());
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = String(typeof input === 'object' && 'url' in input ? input.url : input);
      if (url.includes('/api/bot/config')) {
        return Promise.resolve(json({ status: 'error', message: 'پیکربندی رد شد',
          errors: ['sizing_fraction بیرونِ مجاز 0.001…0.25: 0.9'] }));
      }
      return Promise.resolve(json(statusBody()));
    });
    renderPanel();
    fireEvent.click(await screen.findByTestId('bot-toggle-open'));
    fireEvent.change(screen.getByDisplayValue('5'), { target: { value: '90' } });
    fireEvent.blur(screen.getByDisplayValue('90'));
    const list = await screen.findByTestId('bot-config-errors');
    expect(list.textContent).toContain('sizing_fraction');
  });

  it('درِ HALTED دکمهٔ ادامه نشان داده می‌شود و توقف نه', async () => {
    route(statusBody({ kill: 'HALTED', halted: true }));
    renderPanel();
    expect(await screen.findByTestId('bot-resume')).toBeInTheDocument();
    expect(screen.queryByTestId('bot-halt')).not.toBeInTheDocument();
  });

  it('هیچ وعدهٔ «اولی در صف» یا «اجرایِ قطعی» درِ متنِ پنل نیست', async () => {
    route(statusBody());
    const { container } = renderPanel();
    await screen.findByTestId('bot-panel');
    const text = container.textContent ?? '';
    expect(text).not.toMatch(/اول می‌شود|اولی|قطعی اجرا|تضمینی/);
  });

  it('یکِ فشارِ دکمه = یکِ نشست: قیف، ردیفِ قیمت‌دار و سیگنال جدا نمایش داده می‌شوند', async () => {
    route(statusBody({ last_runs: [RUN_OK.run] }));
    renderPanel();
    const line = await screen.findByTestId('bot-last-run');
    expect(line.textContent).toContain('۱۴ درِ قیف');
    expect(line.textContent).toContain('۶ ردیف');
    expect(line.textContent).toContain('۳ سیگنال');
    expect(line.textContent).toContain('۱ ارسال');
  });

  it('سیگنالِ پرِشده‌نشدۀ این نشست «درِ انتظارِ نشستِ بعد» است، نه ارسال‌شده', async () => {
    route(statusBody({ pending_drafts: 6, last_runs: [RUN_OK.run] }));
    renderPanel();
    const pend = await screen.findByTestId('bot-pending-line');
    expect(pend.textContent).toContain('۶ سیگنال درِ انتظارِ نشستِ بعد');
    expect(pend.textContent).not.toMatch(/ارسالِ قطعی|پر شد/);
  });
});
