// __tests__/order-line.spec.ts -- سرخطیِ چندنمادی: استقلال، ضدِ تکرار، نتیجهٔ نامعلوم
//
// سطحِ اینِ فایل «تستِ واحد + بک‌اندِ ماک» است (بندِ ۱.۵ مأموریت: چهارِ سطحِ تست
// جدا‌اند). اتصالِ واقعی درِ همینِ فایل آزموده نمی‌شود وِ هیچِ رکوردی ازِ آنِ سطح
// اینجا ادعا نمی‌شود؛ آنچه سنجیده می‌شود رفتارِ رابط باِ قراردادِ واقعیِ
// `api/execution.py` است، رویِ پاسخ‌هایی که عیناً شکلِ آنِ قرارداد را دارند.
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  batchDispatch, draftBody, localGaps, tabDispatch, tabPreflight,
} from '@features/execution/lib/orderLineActions';
import {
  emptyTab, sanitizeRehydrated, useOrderLineStore, type OrderTab,
} from '@features/execution/stores/orderLineStore';

type Call = { path: string; body: Record<string, unknown> };
let calls: Call[] = [];
let mode: 'ok' | 'timeout' | 'html' | 'reject' = 'ok';

const json = (b: unknown) => ({ ok: true, status: 200, json: async () => b }) as unknown as Response;

function record(id: string, over: Partial<OrderTab> = {}): OrderTab {
  const t = emptyTab({ symbol: 'شپنا', price: '1040', quantity: '100', ...over });
  return { ...t, id, executionId: `x-${id}` };
}

function seed(...tabs: OrderTab[]) {
  useOrderLineStore.setState({ tabs, activeId: tabs[0]?.id ?? null });
}

function deps() {
  const s = () => useOrderLineStore.getState();
  return {
    beginSend: (id: string) => s().beginSend(id),
    endSend: (id: string) => s().endSend(id),
    mark: (id: string, f: Partial<OrderTab>) => s().mark(id, f),
  };
}

const tab = (id: string) => useOrderLineStore.getState().tabs.find((t) => t.id === id)!;

beforeEach(() => {
  calls = [];
  mode = 'ok';
  localStorage.clear();
  useOrderLineStore.setState({ tabs: [], activeId: null });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = String(url);
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ path, body });
    const eid = String(body.execution_id ?? '');
    if (mode === 'html') return json('<!doctype html><html></html>') as unknown as Response;
    if (mode === 'timeout') return Promise.reject(new Error('network down'));
    if (path.includes('/preflight')) {
      return json({ status: 'success', adapter: 'mock', dry_run: true, live: false,
                    execution_id: eid, ok: true, checks: { session: 'PASS', instrument: 'PASS' },
                    reasons: {}, unknown: [] });
    }
    if (path.includes('/prepare')) {
      return json({ status: 'success', execution_id: eid, mode: 'safe', dry_run: true,
                    sendable: true, checks: { limits: 'PASS' }, payload_preview: { symbol: body.symbol },
                    wire_preview: null, wire_hypothesis: false, plan: null, timings: { prepared_ms: 3 } });
    }
    if (path.includes('/dispatch')) {
      if (mode === 'reject') {
        return json({ status: 'error', code: 'PRICE_LIMIT', detail: 'قیمت خارج از دامنه',
                      execution_id: eid, checks: { price: 'FAIL' } });
      }
      return json({ status: 'success', adapter: 'mock', dry_run: true, live: false,
                    execution_id: eid, kill_switch: { state: 'armed' },
                    record: { execution_id: eid, symbol: body.symbol, status: 'acknowledged',
                              order_state: 'open', broker_order_id: `B-${eid}`, rtt_ms: 12 },
                    timings: { dispatch_ms: 14, response_ms: 12, observed_ms: null } });
    }
    return json({ status: 'success', execution_id: eid });
  }));
});

describe('استقلالِ تب‌ها (سناریوهایِ ۱–۴)', () => {
  it('سه تب باِ سه نماد، سه state جدا دارند', () => {
    seed(record('a'), record('b', { symbol: 'فولاد' }), record('c', { symbol: 'خودرو' }));
    expect(useOrderLineStore.getState().tabs.map((t) => t.symbol)).toEqual(['شپنا', 'فولاد', 'خودرو']);
    expect(new Set(useOrderLineStore.getState().tabs.map((t) => t.executionId)).size).toBe(3);
  });

  it('ویرایشِ یکِ تب هیچِ تبِ دیگری را تکان نمی‌دهد', () => {
    seed(record('a'), record('b', { symbol: 'فولاد', price: '500', quantity: '7' }));
    useOrderLineStore.getState().patch('a', { symbol: 'شپنا', price: '1040', quantity: '200' });
    const b = tab('b');
    expect(b.symbol).toBe('فولاد');
    expect(b.price).toBe('500');
    expect(b.quantity).toBe('7');
  });

  it('بستنِ یکِ تب، شناسهٔ اجرا وِ ورودیِ بقیه را دست‌نخورده می‌گذارد', () => {
    seed(record('a'), record('b'), record('c'));
    const before = useOrderLineStore.getState().tabs.filter((t) => t.id !== 'b')
      .map((t) => `${t.id}:${t.executionId}:${t.symbol}`);
    useOrderLineStore.getState().closeTab('b');
    const after = useOrderLineStore.getState().tabs.map((t) => `${t.id}:${t.executionId}:${t.symbol}`);
    expect(after).toEqual(before);
    expect(useOrderLineStore.getState().activeId).not.toBe('b');
  });

  it('تبِ تازه بی‌تبِ دیگر ساخته نمی‌شود؛ هرِ تب شناسۀِ اجرایِ خودش را دارد', () => {
    const id = useOrderLineStore.getState().addTab({ symbol: 'شپنا' });
    const t = useOrderLineStore.getState().tabs.find((x) => x.id === id)!;
    expect(t.executionId).toMatch(/^x-/);
    expect(t.phase).toBe('idle');
    expect(t.inFlight).toBe(false);
  });
});

describe('اعتبارسنجی (سناریوِ ۵)', () => {
  it('قیمت/تعداد/نمادِ ناقص ازِ رابط بیرون نمی‌رود', () => {
    const t = record('a', { price: '', quantity: '' });
    expect(localGaps(t).sort()).toEqual(['قیمتِ معتبر نوشته نشده', 'تعدادِ معتبر نوشته نشده'].sort());
    seed({ ...t, symbol: '' });
    expect(localGaps(tab('a'))[0]).toBe('نماد نوشته نشده');
  });

  it('بی‌عددِ واقعی هیچِ درخواستی بهِ سرویس نمی‌رود', async () => {
    seed(record('a', { price: '', quantity: '' }));
    await tabPreflight(tab('a'), deps());
    expect(calls).toHaveLength(0);
    expect(tab('a').phase).toBe('draft');
  });

  it('ارقامِ فارسی همانِ ارقامِ لاتین خوانده می‌شوند (بی‌صفرشدنِ بی‌صدا)', async () => {
    seed(record('a', { price: '۱۰۴۰', quantity: '۱۰۰' }));
    await tabDispatch(tab('a'), deps());
    expect(calls[0].body.price).toBe(1040);
    expect(calls[0].body.quantity).toBe(100);
  });
});

describe('نگاشتِ کارگزاری -- `mock_instrument` رأیِ صریحِ کاربر است، نه عادتِ رابط', () => {
  it('بی‌تیک، بدنه هیچِ `mock_instrument` ندارد: رابط نگاشتِ کارگزاری نمی‌سازد', () => {
    expect('mock_instrument' in draftBody(record('a'))).toBe(false);
  });

  it('تیکِ یکِ تب فقط درِ همانِ تب `mock_instrument: true` می‌فرستد', async () => {
    seed(record('a'), record('b', { symbol: 'فولاد' }));
    useOrderLineStore.getState().patch('a', { mockInstrument: true });
    await tabDispatch(tab('a'), deps());
    await tabDispatch(tab('b'), deps());
    expect(calls[0].body.mock_instrument).toBe(true);
    expect('mock_instrument' in calls[1].body).toBe(false);
  });

  it('بازیابیِ صفحه تیکِ همانِ تب را نگه می‌دارد ولیِ هیچِ نوشتاری آغاز نمی‌کند', () => {
    seed({ ...record('a', { mockInstrument: true }), phase: 'sending', inFlight: true });
    const s = sanitizeRehydrated(tab('a'));
    expect(s.mockInstrument).toBe(true);
    expect(s.phase).toBe('draft');
    expect(calls).toHaveLength(0);
  });
});

describe('ارسالِ مستقل وِ گروهی (سناریوهایِ ۶ وِ ۸)', () => {
  it('پیش‌فرود وِ ارسال، هرکدام یکِ درخواست باِ همانِ شناسه (مسیرِ رابط بی‌«آماده‌سازی» است)', async () => {
    seed(record('a'));
    await tabPreflight(tab('a'), deps());
    expect(tab('a').phase).toBe('validated');
    await tabDispatch(tab('a'), deps());
    expect(tab('a').phase).toBe('acknowledged');
    expect(calls.map((c) => c.path)).toEqual([
      '/api/execution/preflight', '/api/execution/dispatch',
    ]);
    expect(new Set(calls.map((c) => String(c.body.execution_id))).size).toBe(1);
  });

  it('ارسالِ گروهی = چندِ درخواستِ مستقل، بی‌endpointِ گروهیِ ساختگی', async () => {
    seed(record('a'), record('b', { symbol: 'فولاد' }), record('c', { symbol: 'خودرو' }));
    const r = await batchDispatch(useOrderLineStore.getState().tabs, deps(),
      { status: 'success', limits: { max_orders: 3, require_confirmation: true } } as never);
    expect(r.attempted).toBe(3);
    expect(calls.every((c) => c.path === '/api/execution/dispatch')).toBe(true);
    expect(new Set(calls.map((c) => String(c.body.execution_id))).size).toBe(3);
  });

  it('سقفِ هم‌زمانی ازِ limits خوانده می‌شود: max_orders=1 یعنی یکی‌یکی', async () => {
    seed(record('a'), record('b'));
    const r = await batchDispatch(useOrderLineStore.getState().tabs, deps(),
      { status: 'success', limits: { max_orders: 1, require_confirmation: true } } as never);
    expect(r.concurrency).toBe(1);
    expect(r.attempted).toBe(2);
  });

  it('ردِ یکِ تب، نتیجهٔ تبِ دیگر را عوض نمی‌کند', async () => {
    seed(record('a'), record('b'));
    mode = 'reject';
    await tabDispatch(tab('a'), deps());
    mode = 'ok';
    await tabDispatch(tab('b'), deps());
    expect(tab('a').phase).toBe('failed');
    expect(tab('a').note).toContain('قیمت خارج از دامنه');
    expect(tab('b').phase).toBe('acknowledged');
    expect((tab('b').result as Record<string, unknown>)).toBeTruthy();
  });

  it('شناسۀِ کارگزاری ازِ پاسخِ سرویس خوانده می‌شود، نه ساخته', async () => {
    seed(record('a'));
    await tabDispatch(tab('a'), deps());
    const rec = (tab('a').result as { record: { broker_order_id: string } }).record;
    expect(rec.broker_order_id).toBe('B-x-a');
  });
});

describe('ضدِ تکرار وِ نتیجهٔ نامعلوم (سناریوهایِ ۷، ۹، ۱۰)', () => {
  it('دوِ کلیکِ سریع رویِ یکِ تب، یکِ dispatch می‌سازد', async () => {
    seed(record('a'));
    const t = tab('a');
    await Promise.all([tabDispatch(t, deps()), tabDispatch(t, deps())]);
    expect(calls.filter((c) => c.path === '/api/execution/dispatch')).toHaveLength(1);
  });

  it('قطعِ ارتباط «رد» نیست: نتیجهٔ نامعلوم باِ همانِ شناسه', async () => {
    seed(record('a'));
    mode = 'timeout';
    await tabDispatch(tab('a'), deps());
    expect(tab('a').phase).toBe('unknown_result');
    expect(tab('a').note).toContain('نامعلوم');
    expect(tab('a').executionId).toBe('x-a');
  });

  it('پاسخِ HTML (fallbackِ SPA) بهِ «موفق» ترجمه نمی‌شود', async () => {
    seed(record('a'));
    mode = 'html';
    await tabDispatch(tab('a'), deps());
    expect(tab('a').phase).toBe('unknown_result');
    // یکِ تلاش، بی‌retryِ خودکار رویِ نوشتار
    expect(calls.filter((c) => c.path === '/api/execution/dispatch')).toHaveLength(1);
  });

  it('بازیابیِ صفحه سفارشِ درِ حالِ ارسال را دوباره اجرا نمی‌کند', () => {
    const stuck = record('a', { phase: 'sending' });
    const back = sanitizeRehydrated({ ...stuck, inFlight: true });
    expect(back.phase).toBe('draft');
    expect(back.inFlight).toBe(false);
    expect(back.note).toContain('هیچِ سفارشی خودکار ارسال نمی‌شود');
    expect(back.executionId).toBe('x-a');
  });

  it('تبِ پایان‌یافته برایِ تلاشِ تازه شناسۀِ تازه می‌گیرد (بی‌ادعایِ تکرارِ همانِ سفارش)', () => {
    seed({ ...record('a'), phase: 'acknowledged' });
    useOrderLineStore.getState().resetForNextAttempt('a');
    expect(tab('a').executionId).not.toBe('x-a');
    expect(tab('a').phase).toBe('idle');
    expect(tab('a').symbol).toBe('شپنا');
  });

  it('بدنهٔ درخواست هیچِ فیلدِ مشترکی ازِ تبِ دیگر ندارد', () => {
    const a = record('a', { symbol: 'شپنا', price: '1040', quantity: '100' });
    const b = record('b', { symbol: 'فولاد', price: '500', quantity: '10' });
    const ba = draftBody(a, true);
    const bb = draftBody(b, true);
    expect([ba.symbol, ba.price, ba.quantity]).toEqual(['شپنا', 1040, 100]);
    expect([bb.symbol, bb.price, bb.quantity]).toEqual(['فولاد', 500, 10]);
    expect(ba.confirmed).toBe(true);
    expect(bb.confirmed).toBe(true);
  });
});
