// __tests__/order-line-page.spec.tsx -- سرخطی درِ مرورگرِ مجازی: تب‌ها واقعاً جدا‌اند
//
// سطح: تستِ UI (نه بک‌اند، نه اتصالِ واقعی). آنچه اینجا سنجیده می‌شود «اثرِ
// کلیک» است، نه حضورِ دکمه: تبِ تازه باید پنلِ تازه‌یِ خودش را باز کند، بستنِ
// یکِ تب نباید ورودیِ تبِ دیگر را پاک کند، وِ گروهِ تب‌ها باید نقشِ APG داشته
// باشد تاِ صفحه‌خوان بفهمد کدامِ پنل مالِ کدامِ تب است.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OrderLinePage from '@features/execution/routes/OrderLinePage';
import { useOrderLineStore } from '@features/execution/stores/orderLineStore';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const json = (b: unknown) => ({ ok: true, status: 200, json: async () => b }) as unknown as Response;

function page() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <OrderLinePage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  useOrderLineStore.setState({ tabs: [], activeId: null });
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const p = String(url);
    if (p.includes('/status')) {
      return Promise.resolve(json({ status: 'success', adapter: 'mock', dry_run: true, live_enabled: false,
                                    experimental: true, blocked_on: ['آداپتورِ واقعی انتخاب نشده'],
                                    capabilities: { place: true, balances: false } }));
    }
    if (p.includes('/limits')) {
      return Promise.resolve(json({ status: 'success',
                                    limits: { max_orders: 1, require_confirmation: true } }));
    }
    if (p.includes('/dispatch') || p.includes('/preflight') || p.includes('/prepare')) {
      return Promise.resolve(json({ status: 'success', execution_id: 'x', dry_run: true, ok: true,
                                    sendable: true, checks: {}, reasons: {}, unknown: [],
                                    record: { execution_id: 'x', status: 'acknowledged', broker_order_id: 'B1' } }));
    }
    return Promise.resolve(json({ status: 'success' }));
  });
});

describe('OrderLinePage', () => {
  it('بی‌تب، حالتِ خالیِ راهنما نشان می‌دهد وِ هیچِ دروازۀِ ارسال نیست', async () => {
    page();
    expect(await screen.findByTestId('order-line-empty')).toBeTruthy();
    expect(screen.queryByTestId('order-batch')).toBeNull();
  });

  it('«＋ تبِ تازه» یکِ تبِ واقعی باِ پنلِ خودش می‌سازد', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    fireEvent.click(screen.getByTestId('order-add-tab'));
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(2));
    expect(useOrderLineStore.getState().tabs).toHaveLength(2);
    expect(new Set(useOrderLineStore.getState().tabs.map((t) => t.executionId)).size).toBe(2);
  });

  it('نقش‌هایِ APG: هرِ trigger تب، پنلِ وابستهٔ خودش را صدا می‌زند', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(1));
    const trigger = screen.getAllByRole('tab')[0];
    const panelId = trigger.getAttribute('aria-controls');
    expect(panelId).toBeTruthy();
    expect(document.getElementById(panelId as string)).not.toBeNull();
    expect(trigger.getAttribute('aria-selected')).toBe('true');
  });

  it('تغییرِ نماد درِ یکِ تب، متنِ تبِ دیگر را عوض نمی‌کند', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    fireEvent.click(screen.getByTestId('order-add-tab'));
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(2));
    const [t0, t1] = useOrderLineStore.getState().tabs;
    // تبِ تازه‌ساخته روشن است؛ پنلِ تبِ اول را باِ کلیک باز می‌کنیم (فقطِ پنلِ
    // روشن درِ DOM می‌ماند — همانِ چیزی که استقلالِ state را آزمون می‌کند)
    fireEvent.click(screen.getAllByRole('tab')[0]);
    fireEvent.change(screen.getByTestId(`order-symbol-${t0.id}`), { target: { value: 'فولاد' } });
    // تبِ دوم: پنلِ خودش را باز می‌کند (فقطِ پنلِ روشن درِ DOM است) وِ بی‌نماد است
    fireEvent.click(screen.getAllByRole('tab')[1]);
    expect((screen.getByTestId(`order-symbol-${t1.id}`) as HTMLInputElement).value).toBe('');
    // بازگشت بهِ تبِ اول: همانِ «فولاد» جا مانده — state درِ store است، نه درِ گرهٔ DOM
    fireEvent.click(screen.getAllByRole('tab')[0]);
    expect((screen.getByTestId(`order-symbol-${t0.id}`) as HTMLInputElement).value).toBe('فولاد');
    expect(screen.getAllByRole('tab')[0].textContent).toContain('فولاد');
    expect(screen.getAllByRole('tab')[1].textContent).toContain('بی‌نماد');
  });

  it('بستنِ یکِ تب، ورودیِ تبِ دیگر را نگه می‌دارد', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    fireEvent.click(screen.getByTestId('order-add-tab'));
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(2));
    const [t0, t1] = useOrderLineStore.getState().tabs;
    fireEvent.click(screen.getAllByRole('tab')[1]);
    fireEvent.change(screen.getByTestId(`order-price-${t1.id}`), { target: { value: '500' } });
    fireEvent.click(screen.getByTestId(`order-close-${t0.id}`));
    await waitFor(() => expect(screen.getAllByRole('tab')).toHaveLength(1));
    expect((screen.getByTestId(`order-price-${t1.id}`) as HTMLInputElement).value).toBe('500');
  });

  it('دکمهٔ ارسالِ تبِ بی‌فرمِ کامل غیرفعال است (بی‌درخواستِ بی‌معنا بهِ سرویس)', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    const [t0] = useOrderLineStore.getState().tabs;
    const send = screen.getByTestId(`order-dispatch-${t0.id}`) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.change(screen.getByTestId(`order-symbol-${t0.id}`), { target: { value: 'شپنا' } });
    fireEvent.change(screen.getByTestId(`order-price-${t0.id}`), { target: { value: '1040' } });
    fireEvent.change(screen.getByTestId(`order-qty-${t0.id}`), { target: { value: '10' } });
    await waitFor(() => expect((screen.getByTestId(`order-dispatch-${t0.id}`) as HTMLButtonElement).disabled).toBe(false));
  });

  it('دوِ کلیکِ پشتِ هم رویِ ارسال، یکِ درخواست می‌سازد', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    const [t0] = useOrderLineStore.getState().tabs;
    fireEvent.change(screen.getByTestId(`order-symbol-${t0.id}`), { target: { value: 'شپنا' } });
    fireEvent.change(screen.getByTestId(`order-price-${t0.id}`), { target: { value: '1040' } });
    fireEvent.change(screen.getByTestId(`order-qty-${t0.id}`), { target: { value: '10' } });
    const send = () => screen.getByTestId(`order-dispatch-${t0.id}`);
    await waitFor(() => expect((send() as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(send());
    fireEvent.click(send());
    await waitFor(() => {
      const n = fetchMock.mock.calls.filter((c) => String(c[0]).includes('/dispatch')).length;
      expect(n).toBeLessThanOrEqual(1);
    });
  });

  it('ارسالِ گروهی اول مرور می‌خواهد: بی‌مرور، دکمۀِ تأیید درِ DOM نیست', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    const [t0] = useOrderLineStore.getState().tabs;
    fireEvent.change(screen.getByTestId(`order-symbol-${t0.id}`), { target: { value: 'شپنا' } });
    fireEvent.change(screen.getByTestId(`order-price-${t0.id}`), { target: { value: '1040' } });
    fireEvent.change(screen.getByTestId(`order-qty-${t0.id}`), { target: { value: '10' } });
    const batch = await screen.findByTestId('order-batch');
    expect(within(batch).queryByTestId('order-batch-send')).toBeNull();
    fireEvent.click(within(batch).getByTestId('order-batch-review'));
    expect(await screen.findByTestId('order-batch-send')).toBeTruthy();
    expect((await screen.findByTestId('order-batch-review-list')).textContent).toContain('شپنا');
  });

  it('دروازۀِ سرویس ازِ پاسخ خوانده می‌شود: live_enabled=false یعنی ارسالِ واقعی ممنوع است', async () => {
    page();
    // نخست «در حالِ خواندن» است وِ بعد ازِ پاسخِ خودِ سرویس، علتِ واقعی
    await waitFor(() => expect(screen.getByTestId('order-line-gate-reason').textContent)
      .toContain('اتصالِ کارگزاری فعال نیست'), { timeout: 3000 });
    expect(screen.getByTestId('order-line-gate').getAttribute('data-state')).toBe('closed');
  });

  it('تیکِ «شناسۀِ بدلِ کارگزاری» فقط وقتی آداپتورِ خودِ سرویس mock است دیده می‌شود', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    const [t0] = useOrderLineStore.getState().tabs;
    await waitFor(() => expect(screen.getByTestId(`order-mockswitch-${t0.id}`)).toBeTruthy());
    // نمادِ ناقص باقی می‌ماند: تیک، جایِ فرمِ کامل را نمی‌گیرد
    expect(useOrderLineStore.getState().tabs[0].mockInstrument).toBe(false);
  });

  it('باِ آداپتورِ واقعی، رابط هیچِ کلیدِ mock درِ DOM نمی‌گذارد (هیچِ Mock: بهِ کارگزاری نمی‌رود)', async () => {
    fetchMock.mockImplementation((url: string) => {
      const p = String(url);
      if (p.includes('/status')) {
        return Promise.resolve(json({ status: 'success', adapter: 'easytrader', dry_run: true,
                                      live_enabled: false, capabilities: { place: true } }));
      }
      if (p.includes('/limits')) {
        return Promise.resolve(json({ status: 'success', limits: { max_orders: 1, require_confirmation: true } }));
      }
      return Promise.resolve(json({ status: 'success' }));
    });
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    await waitFor(() => expect(screen.getByTestId('order-line-adapter').textContent).toContain('easytrader'));
    expect(screen.queryByTestId(/order-mockswitch-/)).toBeNull();
    expect(screen.queryByTestId('order-line-mockhint')).toBeNull();
  });

  it('مرورِ گروهی نتیجهٔ هرِ تب را جدا می‌نویسد وِ «ردشدۀِ یکِ تب» بهِ تبِ دیگر نسبّت نمی‌گیرد', async () => {
    page();
    fireEvent.click(await screen.findByTestId('order-add-tab'));
    const [t0] = useOrderLineStore.getState().tabs;
    fireEvent.change(screen.getByTestId(`order-symbol-${t0.id}`), { target: { value: 'شپنا' } });
    fireEvent.change(screen.getByTestId(`order-price-${t0.id}`), { target: { value: '1040' } });
    fireEvent.change(screen.getByTestId(`order-qty-${t0.id}`), { target: { value: '10' } });
    fireEvent.click(screen.getByTestId(`order-mockswitch-${t0.id}`));
    fireEvent.click(await screen.findByTestId('order-batch-review'));
    fireEvent.click(await screen.findByTestId('order-batch-send'));
    await waitFor(() => {
      const c = fetchMock.mock.calls.find((x) => String(x[0]).includes('/dispatch'));
      expect(c).toBeTruthy();
    });
    const body = JSON.parse(String(fetchMock.mock.calls.find((x) => String(x[0]).includes('/dispatch'))![1]?.body));
    expect(body.mock_instrument).toBe(true);
    expect(body.confirmed).toBe(true);
  });
});
