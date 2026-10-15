// آزمونِ مسیرِ «معامله» (مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۲)
//
// سه چیز را می‌سنجد، نه رندرِ دکمه: (۱) سرخطی/اجرایِ سفارش وِ رباتِ معاملاتی ازِ
// رسیدۀِ ناوبریِ اصلی باز می‌شوند — پیش ازِ اینِ دور `ExecutionPanel` هیچ mountی درِ
// برنامه نداشت؛ (۲) همانِ پنل‌هایِ موجود مصرف می‌شوند، نه یکِ کپیِ موازی؛
// (۳) بازِ کردنِ صفحه وِ عوضِ کردنِ تب هیچِ درخواستِ ارسالیِ نمی‌سازد — کاغذی
// پیش‌فرضِ خودِ سرویس است وِ اینِ صفحه فقط نشان می‌دهد.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TradingPage from '@features/portfolio/routes/TradingPage';
import type { MarketRow } from '@shared/types/marketRow';
import { NAV_SECTIONS } from '../app/components/Sidebar';
import { mainRoutes } from '../routes';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const calls: { u: string; method: string }[] = [];

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const META = { d_even: 20261015, h_even: 102335 };

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا', name: 'پالایش نفت اصفهان', ins_code: 'A1',
    p_last: 1025, p_closing: 1000, is_live: true, row_h: 102335, ...patch,
  } as MarketRow;
}

/** بی‌نشستِ احرازشده: سرویسِ اجرا live_enabled=false می‌گوید (کاغذی/بدونِ ارسال). */
const EXEC_STATUS = {
  status: 'success', adapter: 'none', dry_run: true, live_enabled: false, live: false,
  live_requested: false, nothing_will_leave_the_machine: true, wire_hypothesis: false,
  blocked_on: ['no_session'], capabilities: {
    place: false, list_orders: false, order_state: false, queue_position: false,
    cancel: false, best_bid_ask: false, balances: false,
  },
  session: { state: 'idle', account_label: null },
  kill_switch: 'DISARMED', halted: false, ledger_size: 0, durable_events: 0,
  clock_source: 'system', clock_limit: 'ساعتِ سیستم',
};

const BOT_STATUS = { status: 'success', running: false, config: { mode: 'paper' }, records: [] };

beforeEach(() => {
  fetchMock.mockReset();
  calls.length = 0;
  fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
    const u = String(url);
    calls.push({ u, method: String(init?.method ?? 'GET') });
    if (u.includes('/api/market/delta')) {
      return Promise.resolve(json({ status: 'success', rev: 3, count: 0, changed: [], meta: META }));
    }
    if (u.includes('/api/market')) {
      return Promise.resolve(json({ status: 'success', rev: 3, count: 2, data: [row(), row({ symbol: 'خودرو' })], meta: META }));
    }
    if (u.includes('/api/execution/status')) return Promise.resolve(json(EXEC_STATUS));
    if (u.includes('/api/execution/ledger')) return Promise.resolve(json({ status: 'success', records: [], open_ids: [], scheduled: [] }));
    if (u.includes('/api/bot/status')) return Promise.resolve(json(BOT_STATUS));
    return Promise.resolve(json({ status: 'success', data: [], records: [], runs: [] }));
  });
});

function mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TradingPage />
    </QueryClientProvider>,
  );
}

describe('مسیرِ «معامله» درِ ناوبری', () => {
  it('رسیدۀِ ناوبری یکِ مقصدِ مستقلِ /trade دارد', () => {
    const items = NAV_SECTIONS.flatMap((s) => s.items);
    const hit = items.find((i) => i.to === '/trade');
    expect(hit).toBeTruthy();
    expect(hit?.label).toContain('سرخطی');
    expect(hit?.label).toContain('ربات');
  });

  it('درِ routes ثبت شده است، نه فقطِ یکِ لینکِ مرده', () => {
    expect(mainRoutes.some((r) => r.path === 'trade')).toBe(true);
  });
});

describe('پنل‌ها بی‌کپیِ موازی مصرف می‌شوند', () => {
  it('تبِ نخست همانِ پنلِ معامله است وِ تبِ دوم همانِ پنلِ ربات', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('watch-order-panel')).toBeInTheDocument());
    expect(screen.queryByTestId('bot-panel')).toBeNull();

    fireEvent.click(screen.getByTestId('trade-tab-bot'));
    await waitFor(() => expect(screen.getByTestId('bot-panel')).toBeInTheDocument());
    expect(screen.queryByTestId('watch-order-panel')).toBeNull();
  });

  it('کاغذی بودنِ پیش‌فرض رویِ صفحه نوشته شده است', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('trading-mode-note')).toBeInTheDocument());
    expect(screen.getByTestId('trading-mode-note').textContent).toContain('کاغذی');
  });
});

describe('هیچِ ارسالی ازِ اینِ صفحه نمی‌رود', () => {
  it('نه درِ mount وِ نه باِ عوضِ کردنِ تب، هیچِ POST/PUT/DELETE نمی‌شود', async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId('watch-order-panel')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('trade-tab-bot'));
    await waitFor(() => expect(screen.getByTestId('bot-panel')).toBeInTheDocument());
    const writes = calls.filter((c) => c.method !== 'GET');
    expect(writes.map((c) => `${c.method} ${c.u}`)).toEqual([]);
  });
});
