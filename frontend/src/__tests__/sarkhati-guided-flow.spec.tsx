// src/__tests__/sarkhati-guided-flow.spec.tsx — «قدمِ شما» درِ تبِّ سرخطی
//
// بازطراحیِ 2026-10-18 یک چیزِ تازه به صفحه اضافه کرد: یک پیشنهادِ ترتیب. این
// فایل همان یک چیز را می‌سنجد، چون خطرِ اصلی‌اش همین است — یک راهنما اگر داوریِ
// دوم بسازد، دروازۀ «آمادهٔ ارسال»ِ رابط با دروازۀ واقعیِ سرویس دو نسخه از یک
// قاعده می‌شوند. پس نیمی از سنجش‌ها مستقیم رویِ تابعِ خالص است و نیمه‌اش رویِ
// همان گیتِ خودِ سرویس (`deriveGate`):
//
//  ۱) «قدم» ازِ وضعیتِ سرویس می‌آید، نه ازِ متنِ ثابت (پنج شاخهٔ deriveStep).
//  ۲) راهنما هرگز درواز را بازتر ازِ خودِ سرویس نشان نمی‌دهد: بی‌نشستِ
//     راستی‌آزمایی‌شده، قدم «اتصال» است — و این همان شرطی است که بک‌اند هم POST
//     را با آن می‌بندد.
//  ۳) «برو به …» مقصدِ درست را باز می‌کند؛ درِ توقفِ اضطراری آن «ریسک و ایمنی»
//     است، نه فرمِ سفارش.
//  ۴) کلیکِ کاربر باِ رسیدنِ پاسخِ سرویس عوض نمی‌شود (بدونِ این، صفحه وسطِ
//     خواندنِ یک بخش کاربر را به بخشِ دیگری می‌کِشاند).
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SarkhatiPage from '@features/portfolio/routes/SarkhatiPage';
import { deriveGate, type ExecutionStatus } from '@features/portfolio/lib/orderClient';
import { deriveStep, statusLine } from '@features/portfolio/lib/sarkhatiFlow';
import { useSarkhatiFormStore } from '@features/portfolio/stores/sarkhatiFormStore';
import { useSymbolStore } from '@shared/stores/symbolStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const CAPS = { place: true, list_orders: true, order_state: true, queue_position: true,
  cancel: false, best_bid_ask: false, balances: false };

/** یک وضعیتِ کامل، باِ یکِ دِلتا؛ همان چیزی که `deriveGate` می‌خواند. */
function statusOf(over: Record<string, unknown> = {}) {
  return {
    status: 'success', adapter: 'mock', dry_run: true, experimental: true,
    live_enabled: false, live: false, live_requested: false,
    nothing_will_leave_the_machine: true, wire_hypothesis: false, blocked_on: [],
    confirm_gate: { required: false }, capabilities: CAPS,
    session: { state: 'connected', account_label: 'mock-acct-1' },
    kill_switch: 'ARMED', halted: false, kill_reason: '', ledger_size: 1,
    durable_events: 3, recovered_after_restart: 0, scheduled_pending: 0,
    confirm_epoch: 2, clock_source: 'system', clock_limit: '',
    limits: {}, ...over,
  };
}

const gateOf = (over: Record<string, unknown> = {}) =>
  deriveGate(statusOf(over) as unknown as ExecutionStatus, 'ok');

const DRAFT_FULL = { price: '12610', quantity: '1000', side: 'buy' };

describe('قدمِ پیشنهادی — تابعِ خالص', () => {
  it('بی‌سرویس: اتصال، و «برو به …» هم اتصال', () => {
    const g = deriveGate(null, 'absent');
    const r = deriveStep({ gate: g, symbol: 'فولاد' });
    expect(r).toMatchObject({ step: 'connect', go: 'connect' });
    expect(statusLine(g)).toBe('سرویسِ اجرا نمی‌رسد');
  });

  it('توقفِ اضطراری: قدم رویِ سفارش می‌ماند ولی مقصدِ اقدام «ریسک و ایمنی» است', () => {
    const g = gateOf({ halted: true, kill_switch: 'TRIPPED', kill_reason: 'توقف از پنلِ معامله' });
    const r = deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL });
    expect(r.step).toBe('order');
    expect(r.go).toBe('risk');
    expect(r.why).toContain('توقف از پنلِ معامله');
    expect(statusLine(g)).toBe('توقفِ اضطراری فعال است');
  });

  it('هر شاخه‌ای جز «اتصالِ لازم»، نشستِ راستی‌آزمایی‌شده می‌خواهد', () => {
    // این سنجشِ «یک داور» است: اگر رابط قدمِ بعدی را داد درحالی‌که نشستِ تأییدشده
    // نبود، دو دروازۀ متناقض ساخته بود. حالتِ توقف استثناست چون قفلش چیزِ دیگری است.
    for (const state of ['disconnected', 'expired', 'auth_failed', 'error', 'unknown']) {
      const g = gateOf({ adapter: 'easytrader', dry_run: false, live_enabled: true,
        session: { state, account_label: 'acct' } });
      const r = deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL, hasRecord: true });
      expect(r.step).toBe('connect');
      expect(g.canTrade).toBe(false);
    }
  });

  it('بی‌نشستِ قابلِ ارسال، واژۀ مأموریت نوشته می‌شود نه حدس', () => {
    expect(statusLine(gateOf({ session: { state: 'disconnected' } }))).toContain('متصل نیست');
    expect(statusLine(gateOf({ adapter: 'easytrader', dry_run: false, live_enabled: true,
      session: { state: 'expired', account_label: 'acct' } }))).toContain('نشست منقضی شده');
    expect(statusLine(gateOf({ adapter: 'easytrader', dry_run: false, live_enabled: true,
      session: { state: 'error', account_label: 'acct' } }))).toContain('خطای اتصال');
  });

  it('ترتیبِ پرسش‌ها: نماد ← سفارش ← نتیجه', () => {
    const g = gateOf();
    expect(deriveStep({ gate: g, symbol: null }).step).toBe('symbol');
    expect(deriveStep({ gate: g, symbol: 'فولاد', draft: { price: '12610' } }).step).toBe('order');
    expect(deriveStep({ gate: g, symbol: 'فولاد', draft: null }).why).toContain('قیمت یا حجم');
    expect(deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL }).step).toBe('order');
    expect(deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL, hasRecord: true }).step)
      .toBe('tracking');
  });

  it('حالتِ بدل پنهان نمی‌ماند: قدمِ «سفارش» علتِ بی‌ارسال بودن را درِ همان خط دارد', () => {
    const g = gateOf();
    expect(g.canTrade).toBe(false); // mock: هیچ چیزی بیرون نمی‌رود
    const r = deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL });
    expect(r.why).toContain('حالتِ تمرین');
    expect(statusLine(g)).toContain('بدلِ سرویس (mock)');
  });

  it('اتصالِ زندهٔ راستی‌آزمایی‌شده: قدم سفارش است و «تمرین» دیگر نوشته نمی‌شود', () => {
    const g = gateOf({ adapter: 'easytrader', dry_run: false, live_enabled: true,
      nothing_will_leave_the_machine: false, live: true,
      session: { state: 'connected', account_label: 'acct' } });
    expect(g.canTrade).toBe(true);
    const r = deriveStep({ gate: g, symbol: 'فولاد', draft: DRAFT_FULL });
    expect(r.step).toBe('order');
    expect(r.why).not.toContain('تمرین');
  });
});

// ── نیمۀِ صفحه: همان پیشنهاد، این‌بار آن‌چه کاربر می‌بیند ──────────────────────
const LEDGER = { status: 'success', adapter: 'mock', dry_run: true, live: false,
  kill_switch: 'ARMED', open_ids: [], scheduled: [], records: [] };

const FEED = { status: 'success', rev: 9, count: 1, live_count: 1, fossil_count: 0,
  meta: { d_even: 20261018, h_even: 112000 },
  data: [{ ins_code: '46', symbol: 'فولاد', name: 'شرکت فولاد مبارکه',
    p_last: 12610, p_closing: 12600, price_yesterday: 12500, percent_change: 0.8,
    tmin: 11250, row_h: 112000, is_live: true, st_title: 'عادی' }] };

function route(status: Record<string, unknown>) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/api/execution/status')) return Promise.resolve(json(status));
    if (u.includes('/api/execution/ledger')) return Promise.resolve(json(LEDGER));
    if (u.includes('/api/market')) return Promise.resolve(json(FEED));
    if (u.includes('/api/execution/connect')) {
      return Promise.resolve(json({ status: 'success', states_supported: ['CONNECTED'],
        browser: { open: false }, allowed_hosts: ['login.emofid.com'],
        login_hosts_configured: ['login.emofid.com'],
        host_roles: { auth: ['account.emofid.com'], ui: ['d.easytrader.ir'],
          api: ['api-mts.orbis.easytrader.ir'] },
        last_verify: { state: 'CONNECTED', reason: '', checked_at: '11:20:00' },
        secrets_stored: false }));
    }
    return Promise.resolve(json({ status: 'success' }));
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SarkhatiPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  useSarkhatiFormStore.setState({ bySymbol: {} });
  useSymbolStore.getState().setSymbol('فولاد');
});

describe('قدمِ پیشنهادی — همان چیزی که صفحه نشان می‌دهد', () => {
  it('بی‌نشست، نگاهِ اول «اتصال» است و فرمِ سفارش باز نمی‌شود', async () => {
    route(statusOf({ adapter: 'easytrader', dry_run: false, live_enabled: true,
      nothing_will_leave_the_machine: false,
      session: { state: 'disconnected', account_label: null } }));
    renderPage();
    // نخستِ خودِ پاسخِ سرویس باید برسَد: خطِ «اتصالِ زنده» فقط ازِ همان پاسخ
    // نوشته می‌شود. بی‌این سنجش بی‌معنی است، چون نگاهِ اولِ صفحه — پیشِ هر
    // پاسخی — رویِ «اتصال» است و «connect» را ازِ حالتِ بارگذاری هم می‌دهد.
    await waitFor(() => expect(screen.getByTestId('sarkhati-status-line').textContent)
      .toContain('اتصالِ زنده'));
    expect(screen.getByTestId('sarkhati-page').getAttribute('data-suggested-step'))
      .toBe('connect');
    expect(screen.getByTestId('sarkhati-connect-section')).toBeInTheDocument();
    expect(screen.getByTestId('sarkhati-status-line').textContent).toContain('متصل نیست');
    expect(screen.queryByTestId('watch-order-price')).toBeNull();
    // ولی «قفل» نیست: کاربر می‌تواند خودش برود سراغِ فرم — راهنما راه را بند نمی‌کند
    fireEvent.click(screen.getByTestId('sarkhati-tab-order'));
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
  });

  it('کلیکِ کاربر باِ رسیدنِ وضعیت جابه‌جا نمی‌شود؛ پیشنهاد درِ خطِ بالا می‌ماند', async () => {
    route(statusOf());
    renderPage();
    fireEvent.click(screen.getByTestId('sarkhati-tab-symbol'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-page')
      .getAttribute('data-suggested-step')).toBe('order'));
    expect(screen.getByTestId('sarkhati-page').getAttribute('data-step')).toBe('symbol');
    expect(screen.getByTestId('sarkhati-symbol-section')).toBeInTheDocument();
    // «برو به …» هست، و همان کاری را می‌کند که پیشنهاد می‌گوید
    fireEvent.click(screen.getByTestId('sarkhati-next-action'));
    await waitFor(() => expect(screen.getByTestId('watch-order-price')).toBeInTheDocument());
  });

  it('توقفِ اضطراری: دکمه به «ریسک و ایمنی» می‌برد، نه به فرمِ سفارش', async () => {
    route(statusOf({ halted: true, kill_switch: 'TRIPPED', kill_reason: 'توقف از پنلِ معامله' }));
    renderPage();
    await waitFor(() => expect(screen.getByTestId('sarkhati-step-why').textContent)
      .toContain('توقف از پنلِ معامله'));
    expect(screen.getByTestId('sarkhati-page').getAttribute('data-suggested-step')).toBe('order');
    expect(screen.getByTestId('sarkhati-next-action').getAttribute('data-go')).toBe('risk');
    expect(screen.getByTestId('sarkhati-tab-risk').getAttribute('data-suggested')).toBe('true');
    fireEvent.click(screen.getByTestId('sarkhati-next-action'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-risk-card')).toBeInTheDocument());
  });

  it('پنلِ اتصال یک مسیرِ اصلی دارد و ردیفِ قدیمی را تکرار نمی‌کند', async () => {
    route(statusOf());
    renderPage();
    await waitFor(() => expect(screen.getByTestId('sarkhati-order-section')).toBeInTheDocument());
    // قدمِ ۳ هیچ کنترلِ اتصالِ دومی نمی‌سازد؛ نشست را فقط به‌صورتِ نشان می‌خواند
    expect(screen.queryAllByTestId('connect-broker-row')).toHaveLength(0);
    expect(screen.getByTestId('watch-order-panel').getAttribute('data-session')).toBe('connected');
    // پنلِ جدید یک دکمهٔ اصلیِ host دارد؛ مسیرِ قدیمی در جزئیاتِ فنی است، نه
    // کنارِ مسیرِ اصلی (پیش از این دو «بررسی اتصال» رویِ صفحه می‌شد).
    fireEvent.click(screen.getByTestId('sarkhati-tab-connect'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-connect-section')).toBeInTheDocument());
    expect(screen.getAllByTestId('connection-open-host')).toHaveLength(1);
    expect(screen.getByTestId('sarkhati-connection-technical')).toBeInTheDocument();
  });

  it('هیچ‌چیز ازِ صفحه بیرون نرفته: چهار قدم و سه ابزارِ حرفه‌ای همه tabند', async () => {
    route(statusOf());
    renderPage();
    const tabs = await screen.findAllByRole('tab');
    expect(tabs.map((t) => t.getAttribute('data-testid')).sort()).toEqual([
      'sarkhati-tab-connect', 'sarkhati-tab-monitor', 'sarkhati-tab-order',
      'sarkhati-tab-risk', 'sarkhati-tab-schedule', 'sarkhati-tab-symbol',
      'sarkhati-tab-tracking',
    ].sort());
    // جزئیاتِ فنی بسته است، نه حذف‌شده: خطِ جریانِ نُه‌گامه داخلش زنده است
    expect(screen.getByTestId('sarkhati-node-gate')).toBeInTheDocument();
  });
});
