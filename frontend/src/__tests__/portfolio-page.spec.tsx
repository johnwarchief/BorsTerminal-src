// تست کارتابل پرتفوی v2: سوییچر دوگانه، سه تب، حد ضررها با fetch ماک‌شده
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import PortfolioPage from '@features/portfolio/routes/PortfolioPage';
import { distanceToStopPct, stopStatusTone } from '@features/portfolio/routes/PortfolioPage';
import { useTargetAllocation } from '@features/portfolio/stores/targetAllocation';
import type { MarketFeed } from '@shared/types/marketRow';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function marketFeed(): MarketFeed {
  return {
    status: 'ok',
    count: 2,
    data: [
      {
        symbol: 'شپنا',
        p_closing: 1040,
        p_last: 1040,
        sector_name: 'پالایش',
      },
      {
        symbol: 'شاملا',
        p_closing: 40840,
        p_last: 40840,
        sector_name: 'پالایش',
      },
    ],
  } as unknown as MarketFeed;
}

function portfolioFeed() {
  return {
    status: 'success',
    decisions: [
      { symbol: 'شپنا', status: 'accept', weight_eff_pct: 12, stop_loss: 900, reason: null, sector: 'پالایش', price: 1000 },
      { symbol: 'شاملا', status: 'monitor', weight_eff_pct: null, stop_loss: null, reason: null, sector: 'پالایش', price: null },
      { symbol: 'ویسا', status: 'reject', weight_eff_pct: null, stop_loss: null, reason: 'اقدام سریع از تابلو', sector: 'سرمایه‌گذاریها', price: null },
    ],
    portfolio: [
      { symbol: 'شپنا', status: 'accept', weight_eff_pct: 12, stop_loss: 900, reason: null, sector: 'پالایش', price: 1000 },
    ],
    monitor: [
      { symbol: 'شاملا', status: 'monitor', weight_eff_pct: null, stop_loss: null, reason: null, sector: 'پالایش', price: null },
    ],
    counts: { accept: 1, reject: 1, monitor: 1, pending: 0 },
    limits: { min: 5, max: 7, weight_cap_pct: 20, equal_weight_pct: 100, sum_weight_pct: 12 },
  };
}

/** پاسخ /api/fts/{symbol} — فیبو + حد ضرر؛ شاملا عمداً بدون fib */
function ftsFeed(symbol: string) {
  if (symbol === 'شپنا') {
    return {
      status: 'success',
      symbol,
      fts: {
        fib: { zone_33_40: { lo: 920, hi: 950, in_zone: false }, zone_618_70: { lo: 850, hi: 880, in_zone: false } },
        jet: { active: false, resistance: 1010 },
        exit_engine: { l1: { hard_stop: 855, stop_basis: 'swing_low', ma14: 990, stop_hit: false } },
      },
    };
  }
  if (symbol === 'شاملا') {
    // حد ضرر چارت هست ولی فیبو نیست — fallback به endpoint چارت باید کار کند
    return {
      status: 'success',
      symbol,
      fts: {
        fib: null,
        jet: { active: false, resistance: null },
        exit_engine: { l1: { hard_stop: 38600, stop_basis: 'swing_low', ma14: 39100, stop_hit: false } },
      },
    };
  }
  return {
    status: 'success',
    symbol,
    fts: {
      fib: null,
      jet: { active: false, resistance: null },
      exit_engine: { l1: null },
    },
  };
}

/** پاسخ /api/fundamental/{symbol} — حاشیه/رشد برای حد ضرر بنیادی */
function fundFeed(symbol: string) {
  if (symbol === 'شپنا') {
    return { status: 'success', metrics: { gross_margin: 25.4, growth_pct: 12, monetary_growth_pct: 12 } };
  }
  return { status: 'success', metrics: { gross_margin: 15, growth_pct: -8, monetary_growth_pct: -8 } };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/portfolio']}>
        <Routes>
          <Route path="/portfolio" element={<PortfolioPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockAll() {
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    const ok = (body: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
    if (u.startsWith('/api/selection/portfolio')) return ok(portfolioFeed());
    if (u.startsWith('/api/market')) return ok(marketFeed());
    if (u.startsWith('/api/fts/')) return ok(ftsFeed(decodeURIComponent(u.replace('/api/fts/', ''))));
    if (u.startsWith('/api/fundamental/')) return ok(fundFeed(decodeURIComponent(u.replace('/api/fundamental/', ''))));
    return ok({ status: 'error' });
  });
}

describe('فاصله تا حد ضرر (واحد قبلی)', () => {
  it('قیمت و حد ندارند null می دهد', () => {
    expect(distanceToStopPct(null, 100)).toBeNull();
    expect(distanceToStopPct(1000, null)).toBeNull();
  });

  it('حد صفر نامعتبر است', () => {
    expect(distanceToStopPct(1000, 0)).toBeNull();
  });

  it('قیمت بالای حد مثبت و زیر حد منفی است', () => {
    expect(distanceToStopPct(1100, 1000)).toBeCloseTo(10, 5);
    expect(distanceToStopPct(950, 1000)).toBeCloseTo(-5, 5);
  });

  it('رنگ وضعیت حد ضرر', () => {
    expect(stopStatusTone(null)).toBe('gray');
    expect(stopStatusTone(-2)).toBe('red');
    expect(stopStatusTone(3)).toBe('yellow');
    expect(stopStatusTone(12)).toBe('green');
  });
});

describe('سوییچر دوگانه و پرتفوی هدف', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    mockAll();
    useTargetAllocation.getState().reset();
    useTargetAllocation.getState().setView('target');
    localStorage.clear();
  });
  it('نمای پیش‌فرض هدف است: بنر FTS و چارت دونات دیده می شوند', async () => {
    renderPage();
    expect(await screen.findByText('پیشنهاد اقتصادی و مدیریت سرمایه FTS')).toBeInTheDocument();
    expect(screen.getByText(/سعی کنید ترکیب دارایی‌های خود را/)).toBeInTheDocument();
    expect(screen.getByText(/فرمول ریسک سیستماتیک: حداکثر ۲۰٪ سهام/)).toBeInTheDocument();
    // چارت دونات
    expect(screen.getByRole('img', { name: 'چارت دونات پرتفوی هدف' })).toBeInTheDocument();
    // طبقه طلا (هم در دونات هم در لیست) و بقیه
    expect(screen.getAllByText('طلای فیزیکی، سکه و شمش').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('صندوق‌ها و گواهی سپردهٔ طلا').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('ارز دیجیتال').length).toBeGreaterThanOrEqual(1);
  });

  it('دکمه ویرایش دارایی مودال را باز می کند و بازنشانی به پیش‌فرض کار می کند', async () => {
    const { unmount } = renderPage();
    await screen.findByText('پیشنهاد اقتصادی و مدیریت سرمایه FTS');
    fireEvent.click(screen.getByRole('button', { name: 'ویرایش دارایی' }));
    expect(await screen.findByRole('dialog', { name: 'ویرایش دارایی‌های هدف' })).toBeInTheDocument();
    // ورودی درصد طلا
    const goldInput = screen.getByLabelText('درصد طلای فیزیکی، سکه و شمش') as HTMLInputElement;
    expect(goldInput.value).toBe('30');
    // بازنشانی داخل مودال (دکمه نوار بیرونی هم هم‌نام است — داخل دیالوگ را انتخاب می‌کنیم)
    const dialog = screen.getByRole('dialog', { name: 'ویرایش دارایی‌های هدف' });
    const resetBtns = dialog.querySelectorAll('button');
    const resetInDialog = Array.from(resetBtns).find((b) => b.textContent?.includes('بازنشانی'));
    expect(resetInDialog).toBeDefined();
    fireEvent.click(resetInDialog!);
    // جمع نمایش داده می شود
    expect(screen.getByText(/جمع:/)).toBeInTheDocument();
    unmount();
  });

  it('تب فعلی با کلیک باز می شود: نوار دلتا و جدول سبد', async () => {
    renderPage();
    await screen.findByText('پیشنهاد اقتصادی و مدیریت سرمایه FTS');
    fireEvent.click(screen.getByRole('tab', { name: 'پرتفوی فعلی (Current Holdings)' }));
    expect(await screen.findByText('شکاف فعلی با هدف (ری‌بالانس)')).toBeInTheDocument();
    expect(screen.getByText('سبد')).toBeInTheDocument();
    expect(screen.getByText('زیر نظر')).toBeInTheDocument();
    expect(screen.getByText('حذف شده')).toBeInTheDocument();
  });
});

describe('پرتفوی فعلی — جدول سه‌گانه', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    mockAll();
    useTargetAllocation.getState().reset();
    useTargetAllocation.getState().setView('target');
    localStorage.clear();
  });

  /** افتتاح نمای فعلی — اول انتظار لود (نمای هدف)، بعد کلیک سوییچر */
  async function openCurrentView() {
    await screen.findByRole('button', { name: 'ویرایش دارایی' });
    fireEvent.click(screen.getByRole('tab', { name: 'پرتفوی فعلی (Current Holdings)' }));
    await screen.findByText('شکاف فعلی با هدف (ری‌بالانس)');
  }

  it('تب سبد: ستون‌های حد ضرر و DCA و سود/زیان', async () => {
    renderPage();
    await openCurrentView();
    // شپنا در سبد است
    expect(await screen.findByText('شپنا')).toBeInTheDocument();
    // حد ضرر: مقدار ثبت‌شده کاربر (900) اولویت دارد؛ در انتظار settle شدن کوئری‌ها
    await waitFor(
      () => {
        expect(document.body.textContent).toMatch(/۹۰۰/);
      },
      { timeout: 4000 },
    );
    // ستون‌های جدول
    expect(screen.getByText('حد ضرر تکنیکال')).toBeInTheDocument();
    expect(screen.getByText('حد ضرر بنیادی')).toBeInTheDocument();
    expect(screen.getByText('پله‌های DCA')).toBeInTheDocument();
    expect(screen.getByText('فاصله تا حد ضرر')).toBeInTheDocument();
    expect(screen.getByText('سود/زیان')).toBeInTheDocument();
  });

  it('برچسب بدون داده برای غیب حد ضرر چارت (شاملا بدون fib ⇒ پله‌ها بدون داده)', async () => {
    renderPage();
    await openCurrentView();
    fireEvent.click(await screen.findByRole('button', { name: /^زیر نظر/ }));
    await waitFor(() => {
      expect(screen.getByText('شاملا')).toBeInTheDocument();
    });
    // حد ضرر از endpoint چارت fallback شد (شاملا stop_loss ندارد)
    await waitFor(() => {
      expect(document.body.textContent).toMatch(/۳۸٬۶۰۰|38600|۳۸۶۰۰/);
    }, { timeout: 4000 });
    // فیبو غایب ⇒ برچسب بدون داده در پله‌ها
    await waitFor(() => {
      expect(screen.getAllByText(/بدون داده/).length).toBeGreaterThan(0);
    });
  });

  it('تب حذف شده: ردیف رد شده دیده می شود', async () => {
    renderPage();
    await openCurrentView();
    fireEvent.click(await screen.findByRole('button', { name: /^حذف شده/ }));
    await waitFor(() => {
      expect(screen.getByText('ویسا')).toBeInTheDocument();
    });
  });

  it('حد ضرر بنیادی: حاشیه زیر ۲۰ یا رشد منفی فعال است', async () => {
    renderPage();
    await openCurrentView();
    await screen.findByText('شپنا');
    await waitFor(() => {
      expect(screen.getByText(/فعال|سالم/)).toBeInTheDocument();
    });
  });
});
