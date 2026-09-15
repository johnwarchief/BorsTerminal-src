// تست دکمهٔ خودکفا تصمیم سبد (SymbolBasketAction + useSymbolBasket):
// وضعیت فعلی · افزودن به سبد (POST) · تغییر وضعیت · حذف کامل (DELETE) · حالت بدون داده
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { deriveBasketState, type BasketFeed } from '@features/portfolio/api/useSymbolBasket';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

/** فید تصمیم‌ها — شبیه پاسخ بک‌اند /api/selection/portfolio */
let decisions: Record<string, unknown>[];

function baseDecisions(): Record<string, unknown>[] {
  return [
    { symbol: 'شپنا', status: 'accept', weight_pct: 12, weight_eff_pct: 12, stop_loss: 900, note: 'پله دوم', sector: 'پالایش' },
    { symbol: 'شاملا', status: 'monitor', weight_pct: 0, stop_loss: '', note: '' },
    { symbol: 'ویسا', status: 'reject', weight_pct: 0, stop_loss: '', note: 'اقدام سریع از تابلو' },
  ];
}

function portfolioFeed() {
  return {
    status: 'success',
    decisions,
    counts: {},
    limits: { min: 5, max: 7, weight_cap_pct: 20 },
  };
}

function ok(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function renderAction(symbol = 'شپنا', compact = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SymbolBasketAction symbol={symbol} compact={compact} />
    </QueryClientProvider>,
  );
}

/** باز کردن دیالوگ — منتظر می‌ماند تا فید برسد و برچسب پایدار شود، بعد کلیک می‌کند */
async function openDialog(symbol: string, mark: string): Promise<HTMLElement> {
  renderAction(symbol);
  const btn = await screen.findByRole('button', { name: /تصمیم سبد/ });
  await waitFor(() => expect(btn.textContent).toContain(mark));
  fireEvent.click(btn);
  return screen.findByRole('dialog', { name: `تصمیم سبد برای ${symbol}` });
}

beforeEach(() => {
  decisions = baseDecisions();
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string, opts?: { method?: string; body?: string }) => {
    const u = String(url);
    const method = opts?.method ?? 'GET';
    if (u === '/api/selection/portfolio' && method === 'GET') return Promise.resolve(ok(portfolioFeed()));
    if (u === '/api/selection/decision' && method === 'POST') {
      const body = JSON.parse(opts?.body ?? '{}') as { symbol: string; status: string };
      decisions = decisions.filter((d) => d.symbol !== body.symbol);
      if (body.status !== 'pending') {
        decisions = [{ ...body, weight_eff_pct: body.status === 'accept' ? (body as { weight_pct?: number }).weight_pct ?? 0 : null }, ...decisions];
      }
      return Promise.resolve(ok({ status: 'success', symbol: body.symbol, saved_status: body.status }));
    }
    if (method === 'DELETE' && u.startsWith('/api/selection/decision/')) {
      const sym = decodeURIComponent(u.replace('/api/selection/decision/', ''));
      const before = decisions.length;
      decisions = decisions.filter((d) => d.symbol !== sym);
      return Promise.resolve(ok({ status: 'success', deleted: before - decisions.length }));
    }
    return Promise.resolve(ok({ status: 'error', message: 'اندپوینت ناشناخته: ' + u }));
  });
});

describe('deriveBasketState (خالص)', () => {
  const feed = {
    status: 'success',
    decisions: [
      { symbol: 'شپنا', status: 'accept' },
      { symbol: 'شاملا', status: 'monitor' },
      { symbol: 'ویسا', status: 'reject' },
      { symbol: 'کگل', status: 'pending' },
    ],
  } as unknown as BasketFeed;

  it('وضعیت‌های accept و monitor و reject را تشخیص می دهد', () => {
    expect(deriveBasketState(feed, 'شپنا')).toBe('accept');
    expect(deriveBasketState(feed, 'شاملا')).toBe('monitor');
    expect(deriveBasketState(feed, 'ویسا')).toBe('reject');
  });

  it('pending و نماد غایب و فید undefined همگی «خارج از سبد»اند', () => {
    expect(deriveBasketState(feed, 'کگل')).toBe('none');
    expect(deriveBasketState(feed, 'غایب')).toBe('none');
    expect(deriveBasketState(undefined, 'شپنا')).toBe('none');
    expect(deriveBasketState(feed, '')).toBe('none');
  });
});

describe('نمایش وضعیت فعلی', () => {
  it('نمادِ در سبد با دکمهٔ غیرکامپکت برچسب «در سبد» دارد', async () => {
    renderAction();
    const btn = await screen.findByRole('button', { name: /تصمیم سبد/ });
    await waitFor(() => expect(btn.textContent).toContain('در سبد'));
    // متن بدون داده نیست
    expect(btn.textContent).not.toContain('بدون داده');
  });

  it('حالت compact برچسب نشانکی دارد', async () => {
    renderAction('شپنا', true);
    expect(await screen.findByText('✓ در سبد')).toBeInTheDocument();
  });

  it('نمادِ خارج از سبد برچسب افزودن دارد', async () => {
    renderAction('فولاد');
    const btn = await screen.findByRole('button', { name: /تصمیم سبد/ });
    await waitFor(() => expect(btn.textContent).toContain('+ افزودن به سبد'));
  });
});

describe('افزودن/ویرایش تصمیم (POST)', () => {
  it('دیالوگ با مقادیر ثبت‌شده پر می شود و تغییر وضعیت به زیر نظر با وزن جدید POST می شود', async () => {
    await openDialog('شپنا', 'در سبد');

    // پیش‌فرض از رکورد ثبت‌شده: وزن ۱۲ و حد ۹۰۰ و یادداشت
    const w = (await screen.findByLabelText('وزن درصدی نماد')) as HTMLInputElement;
    const s = (await screen.findByLabelText('حد ضرر نماد')) as HTMLInputElement;
    const n = (await screen.findByLabelText('یادداشت تصمیم')) as HTMLInputElement;
    await waitFor(() => {
      expect(w.value).toBe('12');
      expect(s.value).toBe('900');
      expect(n.value).toBe('پله دوم');
    });

    // تغییر وضعیت به «زیر نظر» + وزن/حد/یادداشت جدید
    fireEvent.click(screen.getByLabelText('زیر نظر (بدون وزن)'));
    fireEvent.change(w, { target: { value: '7.5' } });
    fireEvent.change(s, { target: { value: '850' } });
    fireEvent.change(n, { target: { value: 'تست ثبت' } });
    fireEvent.click(screen.getByRole('button', { name: 'ثبت تصمیم' }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([u, o]) => String(u) === '/api/selection/decision' && (o as { method?: string } | undefined)?.method === 'POST',
      );
      expect(post).toBeDefined();
      const body = JSON.parse((post![1] as { body: string }).body);
      expect(body).toMatchObject({ symbol: 'شپنا', status: 'monitor', weight_pct: 7.5, stop_loss: 850, note: 'تست ثبت' });
    });

    // دیالوگ پس از ثبت موفق بسته می شود
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    // پس از invalidate، بج وضعیت جدید را می گیرد (refetch با دادهٔ بروز)
    expect(await screen.findByText('👁 زیر نظر')).toBeInTheDocument();
  });

  it('وزن خارج از بازه ۰..۱۰۰ خطای اعتبارسنجی می دهد و POST نمی زند', async () => {
    await openDialog('فولاد', '+ افزودن به سبد');
    const w = screen.getByLabelText('وزن درصدی نماد') as HTMLInputElement;
    fireEvent.change(w, { target: { value: '150' } });
    fireEvent.click(screen.getByRole('button', { name: 'ثبت تصمیم' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('وزن باید عددی بین ۰ تا ۱۰۰ باشد.');
    expect(fetchMock.mock.calls.filter(([, o]) => (o as { method?: string } | undefined)?.method === 'POST').length).toBe(0);
  });

  it('انصراف (pending) با POST status=pending ثبت می شود', async () => {
    await openDialog('شپنا', 'در سبد');
    fireEvent.click(screen.getByLabelText('انصراف — بازگشت به بررسی‌نشده'));
    fireEvent.click(screen.getByRole('button', { name: 'ثبت تصمیم' }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([u, o]) => String(u) === '/api/selection/decision' && (o as { method?: string } | undefined)?.method === 'POST',
      );
      expect(post).toBeDefined();
      expect(JSON.parse((post![1] as { body: string }).body)).toMatchObject({ symbol: 'شپنا', status: 'pending' });
    });
  });
});

describe('حذف کامل تصمیم (DELETE)', () => {
  it('دکمهٔ حذف برای نماد دارای تصمیم، DELETE با نماد encode شده می زند', async () => {
    await openDialog('شپنا', 'در سبد');

    expect(screen.getByRole('button', { name: 'حذف کامل از فهرست' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'حذف کامل از فهرست' }));

    await waitFor(() => {
      const del = fetchMock.mock.calls.find(
        ([u, o]) => String(u).startsWith('/api/selection/decision/') && (o as { method?: string } | undefined)?.method === 'DELETE',
      );
      expect(del).toBeDefined();
      expect(String(del![0])).toBe(`/api/selection/decision/${encodeURIComponent('شپنا')}`);
    });

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    // رکورد پاک شد ⇒ حالت «افزودن به سبد»
    const btn = await screen.findByRole('button', { name: /تصمیم سبد/ });
    await waitFor(() => expect(btn.textContent).toContain('+ افزودن به سبد'));
  });

  it('نماد بدون تصمیم دکمهٔ حذف ندارد', async () => {
    await openDialog('فولاد', '+ افزودن به سبد');
    expect(screen.queryByRole('button', { name: 'حذف کامل از فهرست' })).toBeNull();
  });
});

describe('Circuit Breaker — بدون داده', () => {
  it('خطای بک‌اند ⇒ برچسب صادقانه «بدون داده»؛ هیچ عدد ساختگی نمایش داده نمی شود', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({}) } as unknown as Response),
    );
    renderAction();
    const btn = await screen.findByRole('button', { name: /تصمیم سبد/ });
    await waitFor(() => expect(btn.textContent).toContain('بدون داده'));
  });

  it('در حالت خطا دیالوگ هشدار بدون داده می دهد ولی ثبت جدید ممکن است', async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string, opts?: { method?: string }) => {
      const method = opts?.method ?? 'GET';
      if (method === 'GET') {
        return Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({}) } as unknown as Response);
      }
      if (String(url) === '/api/selection/decision' && method === 'POST') {
        return Promise.resolve(ok({ status: 'success', saved_status: 'monitor' }));
      }
      return Promise.resolve(ok({ status: 'error' }));
    });
    renderAction('فولاد');
    fireEvent.click(await screen.findByRole('button', { name: /تصمیم سبد/ }));
    await screen.findByRole('dialog', { name: 'تصمیم سبد برای فولاد' });
    expect(document.body.textContent).toContain('بدون داده');

    fireEvent.click(screen.getByLabelText('زیر نظر (بدون وزن)'));
    fireEvent.click(screen.getByRole('button', { name: 'ثبت تصمیم' }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, o]) => (o as { method?: string } | undefined)?.method === 'POST');
      expect(post).toBeDefined();
    });
  });
});
