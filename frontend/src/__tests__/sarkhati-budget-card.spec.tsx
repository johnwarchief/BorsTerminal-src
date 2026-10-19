// src/__tests__/sarkhati-budget-card.spec.tsx — کارتِ پیش‌نمایشِ بودجه
//
// چهار دروغی که این کارت نباید بگوید:
//  ۱) بی‌قدرتِ خریدِ کارگزاری هیچ تعدادی نمی‌سازد — «محاسبه نشد»، نه صفر؛
//  ۲) «ازِ کارگزاری» را بی‌`from_broker: true` ادعا نمی‌کند؛
//  ۳) سقفِ تعدادِ تأییدنشده را مجازبودن نمی‌خواند؛
//  ۴) بی‌پاسخ هیچ عددی درِ صفحه نمی‌ماند.
//
// دو نکته‌ای که نسخهٔ اولِ این فایل غلط ازِ آب درآورد و اصلاح شد:
//  • مؤلفه باِ `data-testid`هایش ازِ رندرِ *اول* وجود دارد (بدنۀِ خالیِ پرسش)، پس
//    waitFor رویِ «پیدا شد» هیچی نیست؛ انتظار باید رویِ *محتوا* باشد.
//  • پاسخِ ۵۰۰ درِ `http.ts` دو بار backoff می‌خورد (۸۰۰ + ۱۶۰۰ms)، پس سطرِ خطا
//    ازِ مهلتِ یکِ ثانیه‌ایِ پیش‌فرض بیرون می‌زند — timeoutِ همان آزمون باز شد.
// ارقامِ انتظار باِ رقمِ لاتین نوشته می‌شوند و `num()` آن‌ها را ازِ متنِ فارسی
// بیرون می‌کشد — تایپِ مستقیمِ رقمِ فارسی درِ این مخزن رقم می‌دزدد.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SarkhatiBudgetCard } from '@features/portfolio/components/sarkhati/SarkhatiBudgetCard';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;
const httpFail = (status: number) =>
  ({ ok: false, status, json: () => Promise.resolve({}) }) as unknown as Response;

/** رقم‌هایِ فارسیِ یکِ متن به رشته‌یِ لاتین (بی‌جداکننده) */
const num = (t: unknown): string =>
  (String(t ?? '').match(/[۰-۹]/g) ?? []).map((c) =>
    String(c.charCodeAt(0) - 0x06f0)).join('');

const text = (id: string) => screen.getByTestId(id).textContent;
const shown = (id: string, want: RegExp, ms = 3000) =>
  waitFor(() => expect(text(id)).toMatch(want), { timeout: ms });

const BASE = { status: 'success', symbol: 'داروند', side: 'buy',
  instrument: { ins_code: '7740831252462823', isin: 'IRO1DRVN0001', resolved: true },
  band: { present: true, source: 'market.db', lot_size: 1, allowed_min: 10370,
    allowed_max: 11010, p_last: 11010, as_of: '2026-10-19 06:25:50' },
  price: 11010, price_basis: 'allowed_max',
  buying_power_rial: null, buying_power_source: 'آداپتورِ فعلی هیچ خوانشِ حسابی ندارد',
  plan: { status: 'UNKNOWN', quantity: null, price: null, gross_rial: null,
    fee_rial: null, total_rial: null, remaining_rial: null, lot_size: 1,
    max_qty: null, caps_verified: false, assumptions: [], why: 'بی‌قدرتِ خرید' },
  blockers: ['قدرت خرید ازِ کارگزاری نرسیده'], is_order: false, from_broker: false };

const OK_PLAN = { ...BASE.plan, status: 'OK', quantity: 908, gross_rial: 9997080,
  fee_rial: 11996, total_rial: 10009076, remaining_rial: 0, caps_verified: true };

function withBudget(body: unknown) {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/api/execution/budget')) return Promise.resolve(json(body));
    return Promise.resolve(json({ status: 'success' }));
  });
}

function board(side: 'buy' | 'sell' = 'buy') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SarkhatiBudgetCard symbol="داروند" side={side} adapter="easytrader" />
    </QueryClientProvider>,
  );
}

describe('کارتِ پیش‌نمایشِ بودجه', () => {
  it('بی‌قدرتِ خرید هیچ تعدادی نمی‌سازد و علت را می‌نویسد', async () => {
    withBudget(BASE);
    board();
    await shown('sarkhati-budget-blockers', /قدرت خرید ازِ کارگزاری نرسیده/);
    expect(text('sarkhati-budget-qty')).toContain('محاسبه نشد');
    expect(text('sarkhati-budget-total')).toBe('—');
    expect(text('sarkhati-budget-power')).toContain('نرسیده');
    expect(num(text('sarkhati-budget-qty'))).toBe('');
    expect(num(text('sarkhati-budget-total'))).toBe('');
  });

  it('«ازِ کارگزاری» بی‌from_broker ادعا نمی‌شود', async () => {
    withBudget(BASE);
    board();
    await shown('sarkhati-budget-source', /محاسبۀِ خودِ برنامه/);
    expect(screen.getByTestId('sarkhati-budget-card').getAttribute('data-from-broker'))
      .toBe('false');
  });

  it('باِ from_brokerِ واقعی همان برچسب روشن می‌شود', async () => {
    withBudget({ ...BASE, buying_power_rial: 10000000, from_broker: true,
      buying_power_source: 'broker', plan: OK_PLAN, blockers: [] });
    board();
    await shown('sarkhati-budget-source', /ازِ کارگزاری/);
    expect(screen.getByTestId('sarkhati-budget-card').getAttribute('data-from-broker'))
      .toBe('true');
  });

  it('باِ قدرتِ خریدِ واقعی، تعداد و مبلغ ازِ همان پاسخ نوشته می‌شود', async () => {
    withBudget({ ...BASE, buying_power_rial: 10000000, from_broker: true,
      plan: OK_PLAN, blockers: [] });
    board();
    await shown('sarkhati-budget-qty', /۹۰۸/);
    expect(num(text('sarkhati-budget-total'))).toBe('10009076');
    expect(num(text('sarkhati-budget-power'))).toBe('10000000');
    expect(num(text('sarkhati-budget-price'))).toBe('11010');
    expect(text('sarkhati-budget-price')).toContain('سقفِ مجازِ همین نماد');
    expect(screen.queryByTestId('sarkhati-budget-caps')).toBeNull();
  });

  it('سقفِ تعدادِ نرسیده، مجازبودن را ادعا نمی‌کند', async () => {
    withBudget({ ...BASE, buying_power_rial: 10000000, from_broker: true,
      plan: { ...OK_PLAN, caps_verified: false } });
    board();
    await shown('sarkhati-budget-caps', /مجازبودنش تأیید نشده/);
  });

  it('نماد بی‌شناسۀِ رسمی صریح رد می‌شود، نه حدس', async () => {
    withBudget({ ...BASE, instrument: { ins_code: '', isin: '', resolved: false },
      band: { ...BASE.band, present: false, allowed_min: null, allowed_max: null },
      price: null, price_basis: null,
      blockers: ['نماد درِ تابلویِ امروز ردیفی ندارد'] });
    board();
    await shown('sarkhati-budget-unresolved', /بی‌شناسۀِ رسمی/);
    expect(num(text('sarkhati-budget-price'))).toBe('');
    expect(text('sarkhati-budget-band')).toBe('—');
  });

  it('آدرسِ پرسش باِ نماد و جهتِ فرم بسته می‌شود', async () => {
    withBudget(BASE);
    fetchMock.mockClear();
    board('sell');
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const url = String(fetchMock.mock.calls.find(
      (c) => String(c[0]).includes('/api/execution/budget'))?.[0]);
    expect(url).toContain('side=sell');
    expect(decodeURIComponent(url)).toContain('symbol=داروند');
  });

  it('بی‌پاسخ هیچ عددی درِ صفحه نیست و خطا صادقانه می‌ماند', async () => {
    // ۴۰۴ نه ۵۰۰: «درِ بودجه نیست» همان حالتِ واقعیِ یکِ بک‌اندِ قدیمی است، و
    // برخلافِ ۵۰۰ نه درِ http.ts backoff می‌خورد نه درِ query دوباره تلاش می‌شود —
    // آزمونِ «خطا» نباید سه‌لایه شود تا خطا دیده شود.
    fetchMock.mockImplementation((url: string) => (
      String(url).includes('/api/execution/budget')
        ? Promise.resolve(httpFail(404))
        : Promise.resolve(json({ status: 'success' }))));
    board();
    await shown('sarkhati-budget-error', /پاسخ نداد/, 4000);
    expect(text('sarkhati-budget-qty')).toContain('محاسبه نشد');
    expect(num(text('sarkhati-budget-total'))).toBe('');
  });
});
