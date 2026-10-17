// تستِ پنلِ سرخطی رویِ آداپتورِ EasyTrader (مأموریتِ ۱۴۰۵-۰۷-۲۴، بندِ ۴-ب و ۶)
//
// چیزی که این فایل می‌سنجد «رندر شدنِ دکمه» نیست — می‌سنجد که *هیچ کنترلی بی‌
// پشتیبانِ واقعیِ بک‌اند روشن نمی‌شود*: بی‌نشست «Connected» نمایش داده نمی‌شود،
// بی‌تأییدِ نهایی ارسال ممکن نیست، پاسخِ TIMEOUT «ردشده» خوانده نمی‌شود، و
// نشانیِ نشست هرگز درِ DOM باقی نمی‌ماند.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExecutionPanel } from '@features/portfolio/components/ExecutionPanel';
import type { MarketRow } from '@shared/types/marketRow';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

function row(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا', name: 'پالایش نفت اصفهان', ins_code: 'A1',
    p_last: 1025, p_closing: 1000, is_live: true, row_h: 102335, ...patch,
  } as MarketRow;
}

const CAPS_ON = { place: true, list_orders: true, order_state: true,
  queue_position: true, cancel: false, best_bid_ask: false, balances: false };
const CAPS_OFF = { place: false, list_orders: false, order_state: false,
  queue_position: false, cancel: false, best_bid_ask: false, balances: false };

function statusEasy(patch: Record<string, unknown> = {}) {
  return {
    status: 'success', adapter: 'easytrader', dry_run: false, live_enabled: true,
    live: true, live_requested: true, nothing_will_leave_the_machine: false,
    wire_hypothesis: true, blocked_on: [], capabilities: CAPS_ON,
    session: { state: 'connected', account_label: 'easytrader-session' },
    kill_switch: 'ARMED', halted: false, ledger_size: 0, durable_events: 0,
    clock_source: 'system', clock_limit: 'ساعتِ سیستم',
    ...patch,
  };
}

const LEDGER = { status: 'success', adapter: 'easytrader', dry_run: false, live: true,
  kill_switch: 'ARMED', open_ids: [], scheduled: [], records: [] };

/** پاسخ‌ها را مسیرِ‌محور می‌کیم تا هر آزمون فقط مسیرِ موردِ خودش را ببیند */
function route(status: unknown, handlers: Record<string, unknown> = {}) {
  const calls: string[] = [];
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    calls.push(u);
    for (const [frag, body] of Object.entries(handlers)) {
      if (u.includes(frag)) return Promise.resolve(json(body));
    }
    if (u.includes('/api/execution/')) {
      if (u.endsWith('/status')) return Promise.resolve(json(status));
      if (u.endsWith('/ledger')) return Promise.resolve(json(LEDGER));
      return Promise.resolve(json({ status: 'success', adapter: 'easytrader' }));
    }
    return Promise.resolve(json({ status: 'success', rev: 3, count: 0, data: [],
      meta: { d_even: 20261015, h_even: 102335 } }));
  });
  return calls;
}

function renderPanel(r: MarketRow = row()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ExecutionPanel symbol={r.symbol ?? 'شپنا'} row={r} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
});

describe('درِ رابط فقط با پشتیبانِ واقعی باز می‌شود', () => {
  it('بی‌نشست (live_enabled=false): ارسال خاموش است و دلیل از سرویس می‌آید', async () => {
    route(statusEasy({ live_enabled: false, live: false, dry_run: true,
      nothing_will_leave_the_machine: true, capabilities: CAPS_OFF,
      blocked_on: ['D1: نشستِ مالک درِ حافظه نیست'],
      session: { state: 'disconnected' } }));
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-order-panel')
      .getAttribute('data-session')).toBe('disconnected'));
    expect(screen.getByTestId('exec-submit')).toBeDisabled();
    expect(screen.getByTestId('watch-order-reason').textContent)
      .toContain('D1: نشستِ مالک');
    expect(screen.getByTestId('exec-submit')).not.toBeEnabled();
  });

  it('«Connected» از متنِ رابط نمی‌آید: نشستِ منقضی همان‌طور نوشته می‌شود', async () => {
    route(statusEasy({ session: { state: 'expired' } }));
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-order-panel')
      .getAttribute('data-session')).toBe('expired'));
    expect(document.body.textContent).toContain('نشست منقضی شده');
    expect(document.body.textContent).not.toContain('Connected');
  });

  it('نشستِ بدل با live خاموش، «باز»ِ سبز نمی‌شود', async () => {
    route(statusEasy({ live_enabled: false, live: false, dry_run: true,
      nothing_will_leave_the_machine: true, capabilities: CAPS_OFF,
      session: { state: 'connected', account_label: 'mock-acct-1' } }));
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-order-panel')
      .getAttribute('data-session')).toBe('connected'));
    expect(document.body.textContent).toContain('نشستِ بدل باز است');
    expect(document.body.textContent).not.toMatch(/>نشست باز است</);
  });

  it('ارسال بی‌تأییدِ نهایی ممکن نیست و با تأیید روشن می‌شود', async () => {
    const calls = route(statusEasy());
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '۱۰۲۵' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰' } });
    expect(screen.getByTestId('exec-submit')).toBeDisabled();
    const before = calls.length;
    fireEvent.click(screen.getByTestId('exec-confirm'));
    await waitFor(() => expect(screen.getByTestId('exec-submit')).not.toBeDisabled());
    expect(calls.length).toBe(before);            // تیک خوردن هیچ درخواستی نمی‌زند
    fireEvent.click(screen.getByTestId('exec-submit'));
    await waitFor(() => expect(calls.some((u) => u.includes('/api/execution/dispatch')))
      .toBe(true));
  });

  it('گیتِ عبارتِ تأیید (§۲-۲): تا عبارتِ اعلامیِ بک‌اند تایپ نشود، ارسال خاموش است',
    async () => {
      const calls = route(statusEasy({
        confirm_gate: { required: true, phrase: 'تأییدِ نهایی' },
      }));
      renderPanel();
      await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
      fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '۱۰۲۵' } });
      fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰' } });
      fireEvent.click(screen.getByTestId('exec-confirm'));
      await waitFor(() => expect(screen.getByTestId('exec-confirm-phrase'))
        .toBeInTheDocument());
      expect(screen.getByTestId('exec-submit')).toBeDisabled();
      // پیشوند/نزدیک کافی است؟ نه — و این همان چیزی است که بک‌اند هم رد می‌کند
      fireEvent.change(screen.getByTestId('exec-confirm-phrase'),
        { target: { value: 'تأیید' } });
      expect(screen.getByTestId('exec-submit')).toBeDisabled();
      fireEvent.change(screen.getByTestId('exec-confirm-phrase'),
        { target: { value: 'تأییدِ نهایی' } });
      await waitFor(() => expect(screen.getByTestId('exec-submit')).not.toBeDisabled());
      const before = calls.length;
      fireEvent.click(screen.getByTestId('exec-submit'));
      await waitFor(() => expect(calls.some((u) => u.includes('/api/execution/dispatch')))
        .toBe(true));
      expect(calls.length).toBeGreaterThan(before);
      const sent = fetchMock.mock.calls
        .map((c) => String((c[1] as { body?: string } | undefined)?.body ?? ''))
        .find((b) => b.includes('confirm_phrase'));
      expect(sent).toBeTruthy();
      expect(sent ?? '').toContain('confirm_phrase');
    });

  it('بی‌الزامِ بک‌اند (dry-run/بدل)، فیلدِ عبارت ساخته نمی‌شود', async () => {
    route(statusEasy({ dry_run: true, live: false,
      confirm_gate: { required: false, phrase: 'تأییدِ نهایی' } }));
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
    expect(screen.queryByTestId('exec-confirm-phrase')).toBeNull();
  });

  it('توقف درِ حالتِ بدل هم کار می‌کند — توقف به نشستِ کارگزاری نیاز ندارد', async () => {
    const calls = route(statusEasy());
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-kill-switch')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('watch-kill-switch'));
    await waitFor(() => expect(calls.some((u) => u.includes('/api/execution/halt')))
      .toBe(true));
  });

  it('پیش‌فرود «ارسال‌شده» خوانده نمی‌شود — خطِ پاسخ رأیِ همان اقدام است', async () => {
    route(statusEasy(), {
      '/api/execution/preflight': { status: 'success', adapter: 'easytrader',
        checks: { execution_id: 'PASS', instrument: 'PASS', side: 'PASS', price: 'PASS',
          quantity: 'PASS', session: 'UNKNOWN', balance: 'UNKNOWN', duplicate: 'PASS',
          place: 'PASS', kill_switch: 'PASS' },
        reasons: {}, ok: true, unknown: ['session', 'balance'] },
    });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-preflight')).toBeEnabled());
    fireEvent.click(screen.getByTestId('exec-preflight'));
    await waitFor(() => expect(screen.getByTestId('watch-order-reason').textContent)
      .toContain('پیش‌فرود: ۸ سبز'));
    expect(screen.getByTestId('watch-order-reason').textContent).toContain('۲ نامعلوم');
    expect(screen.getByTestId('watch-order-reason').textContent).not.toContain('ارسال‌شده');
    expect(screen.getByTestId('watch-order-phase').textContent).toContain('پیش‌فرود');
  });

  it('توقف وضعیتِ سفارش را عوض نمی‌کند، فقط خطِ پاسخ را', async () => {
    route(statusEasy(), {
      '/api/execution/halt': { status: 'success', halted: true, kill_switch: 'HALTED',
        aborted_schedules: 0, adapter: 'easytrader', dry_run: false },
    });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-kill-switch')).toBeEnabled());
    fireEvent.click(screen.getByTestId('watch-kill-switch'));
    await waitFor(() => expect(screen.getByTestId('watch-order-reason').textContent)
      .toContain('توقف برقرار شد'));
    expect(screen.getByTestId('watch-order-phase').textContent).toContain('بی‌سفارش');
  });
});

describe('پاسخِ کارگزاری درِ رابط تعبیر نمی‌شود', () => {
  it('TIMEOUT ⇒ «نتیجه نامعلوم»، هرگز «ردشده»', async () => {
    route(statusEasy(), {
      '/api/execution/dispatch': { status: 'error', code: 'TIMEOUT',
        detail: 'پاسخی نیامد', unknown_result: true, execution_id: 'ui-x' },
    });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '۱۰۲۵' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰' } });
    fireEvent.click(screen.getByTestId('exec-confirm'));
    // رندرِ تازه: «ارسال» فقط پس ازِ دیدنِ تأیید روشن می‌شود (بی‌انتظار، آزمون
    // رویِ دکمهٔStill-disabled کلیک می‌کرد و بی‌صدا سبز/سرخ می‌شد)
    await waitFor(() => expect(screen.getByTestId('exec-submit')).toBeEnabled());
    fireEvent.click(screen.getByTestId('exec-submit'));
    await waitFor(() => expect(screen.getByTestId('watch-order-reason').textContent)
      .toContain('نامعلوم'));
    expect(screen.getByTestId('watch-order-phase').textContent).toContain('نتیجه نامعلوم');
    expect(screen.getByTestId('watch-order-reason').textContent).not.toContain('ردشده');
  });

  it('پذیرش با شناسۀِ کارگزاری: همان شناسه نمایش داده می‌شود', async () => {
    route(statusEasy(), {
      '/api/execution/dispatch': { status: 'success', adapter: 'easytrader',
        record: { execution_id: 'ui-1', broker: 'easytrader', symbol: 'شپنا',
          side: 'buy', price: 1025, quantity: 100, status: 'acknowledged',
          order_state: 'pending', broker_order_id: 'BR-00471', attempts: 1,
          events: ['accepted'] } },
    });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-confirm')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('watch-order-price'), { target: { value: '۱۰۲۵' } });
    fireEvent.change(screen.getByTestId('watch-order-qty'), { target: { value: '۱۰۰' } });
    fireEvent.click(screen.getByTestId('exec-confirm'));
    // رندرِ تازه: «ارسال» فقط پس ازِ دیدنِ تأیید روشن می‌شود (بی‌انتظار، آزمون
    // رویِ دکمهٔStill-disabled کلیک می‌کرد و بی‌صدا سبز/سرخ می‌شد)
    await waitFor(() => expect(screen.getByTestId('exec-submit')).toBeEnabled());
    fireEvent.click(screen.getByTestId('exec-submit'));
    await waitFor(() => expect(screen.getByTestId('exec-order-id').textContent)
      .toContain('BR-00471'));
    expect(screen.getByTestId('watch-order-phase').textContent).toContain('تأییدشده');
  });

  it('بی‌capabilityِ صف، هیچ چیپِ «صف» رویِ ردیفِ تاریخچه نمی‌نشیند', async () => {
    route(statusEasy({ capabilities: { ...CAPS_ON, queue_position: false } }), {
      '/api/execution/ledger': { ...LEDGER, records: [{ execution_id: 'ui-9',
        broker: 'easytrader', symbol: 'شپنا', side: 'buy', status: 'acknowledged',
        order_state: 'open', broker_order_id: 'BR-1', price: 1025, quantity: 100 }] },
    });
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-detail-toggle')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('exec-detail-toggle'));
    await waitFor(() => expect(screen.getByTestId('exec-history-ui-9')).toBeInTheDocument());
    expect(screen.queryByTestId('exec-queue-ui-9')).toBeNull();
    expect(screen.getByTestId('exec-refresh-ui-9')).toBeEnabled();
  });

  it('موجودیِ نرسیده صفر نمی‌شود', async () => {
    route(statusEasy({ capabilities: { ...CAPS_ON, balances: false } }));
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('watch-order-balance').textContent)
      .toContain('بی‌داده'));
    expect(screen.getByTestId('watch-order-balance-note').textContent)
      .toContain('صفر جا نمی‌زند');
  });

  it('نشانیِ نشست پس ازِ ذخیره درِ DOM نمی‌ماند و درِ هیچ پاسخِ دیگری نیست', async () => {
    const calls = route(statusEasy());
    renderPanel();
    await waitFor(() => expect(screen.getByTestId('exec-detail-toggle')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('exec-detail-toggle'));
    const secret = 'tok-live-secret-should-not-render';
    fireEvent.change(screen.getByTestId('exec-token-input'), { target: { value: secret } });
    fireEvent.click(screen.getByTestId('exec-token-save'));
    await waitFor(() => expect(calls.some((u) => u.includes('/api/execution/session')))
      .toBe(true));
    expect(screen.getByTestId('exec-token-input')).toHaveValue('');
    expect(document.body.textContent ?? '').not.toContain(secret);
  });
});
