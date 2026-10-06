// __tests__/strategy-tree-page.spec.tsx -- تست‌های صفحه جامع نقشه راه و درخت تصمیم‌گیری FTS
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import StrategyTreePage from '../features/master/routes/StrategyTreePage';
import { useSymbolStore } from '../shared/stores/symbolStore';
import { Sidebar } from '../app/components/Sidebar';

vi.mock('@features/market/api/useMarketFeed', () => ({
  useMarketFeed: () => ({
    data: {
      data: [
        { symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', p_closing: 6200 },
        { symbol: 'شپنا', name: 'پالایش نفت اصفهان', p_closing: 4800 },
      ],
    },
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/strategy-tree']}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('StrategyTreePage — نقشه راه و درخت تصمیم‌گیری FTS', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
  });

  it('رندر سربرگ، نوار کاهش Universe و بوم نقشه راه FTS', () => {
    renderWithProviders(<StrategyTreePage />);

    // سربرگ
    expect(screen.getByText(/نقشه راه و درخت جامع استراتژی FTS/i)).toBeInTheDocument();
    expect(screen.getByText(/۴ چارت در یک نما/i)).toBeInTheDocument();

    // بوم نقشه راه به صورت پیش‌فرض فعال است و گرید ۴ ستونه قدیمی حذف شده
    expect(screen.getByTestId('obsidian-strategy-canvas')).toBeInTheDocument();
    expect(screen.queryByText(/نمای گرید ۴ ستونه/i)).not.toBeInTheDocument();

    // نوار کاهش Universe و مراحل FTS
    expect(screen.getByText(/کاهش کاندیداها در قیف FTS/i)).toBeInTheDocument();
    expect(screen.getByText(/گام ۱: تابلوخوانی \(S\)/i)).toBeInTheDocument();
    expect(screen.getByText(/گام ۲: تکنیکال ۲ زمانه \(T\)/i)).toBeInTheDocument();
    expect(screen.getByText(/گام ۳: بنیادی ۵ شاخص \(F\)/i)).toBeInTheDocument();
    expect(screen.getByText(/تحویل نهایی \(Delivery\)/i)).toBeInTheDocument();
  });

  it('سوییچ سبک معامله: انتخاب نوسان‌گیر، روندگیر، ساعت شنی و سفارشی', () => {
    renderWithProviders(<StrategyTreePage />);

    // کلیک روی شخص روندگیر
    const trendBtn = screen.getByRole('button', { name: /شخص روندگیر/i });
    fireEvent.click(trendBtn);
    expect(trendBtn).toHaveClass('font-black');

    // کلیک روی ساعت شنی
    const hourglassBtn = screen.getByRole('button', { name: /استراتژی ساعت شنی \(۳ تا ۱۰ ساله\)/i });
    fireEvent.click(hourglassBtn);
    expect(hourglassBtn).toHaveClass('font-black');

    // کلیک روی مسیر سفارشی
    const customBtn = screen.getByRole('button', { name: /مسیر سفارشی/i });
    fireEvent.click(customBtn);
    expect(customBtn).toHaveClass('font-black');
  });

  it('سوییچ چیدمان: تغییر حالت بین نقشه راه FTS (Roadmap) و مداری (Orbit)', () => {
    renderWithProviders(<StrategyTreePage />);

    const flowBtn = screen.getByTestId('tree-layout-flow');
    const orbitBtn = screen.getByTestId('tree-layout-orbit');

    expect(flowBtn).toBeInTheDocument();
    expect(orbitBtn).toBeInTheDocument();

    // سوییچ به مداری
    fireEvent.click(orbitBtn);
    expect(orbitBtn).toHaveAttribute('aria-pressed', 'true');

    // سوییچ بازگشت به نقشه راه
    fireEvent.click(flowBtn);
    expect(flowBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('باز شدن کشوی کاندیداهای مرحله با کلیک روی مشاهده کاندیداها', () => {
    renderWithProviders(<StrategyTreePage />);

    // کلیک روی دکمه مشاهده کاندیداهای تابلو
    const viewTapeBtn = screen.getByRole('button', { name: /مشاهده کاندیداهای تابلو/i });
    fireEvent.click(viewTapeBtn);

    // کشوی جدول کاندیداها باز می‌شود
    expect(screen.getByTestId('stage-candidate-drawer')).toBeInTheDocument();
    expect(screen.getByText(/کاندیداهای مرحله: غربالگری اول: تابلوخوانی/i)).toBeInTheDocument();

    // دکمه بستن کشو
    const closeBtn = screen.getByRole('button', { name: /بستن پنجره/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId('stage-candidate-drawer')).not.toBeInTheDocument();
  });

  it('لینک منوی درخت استراتژی FTS در سایدبار وجود دارد', () => {
    renderWithProviders(<Sidebar />);
    const link = screen.getByRole('link', { name: /درخت استراتژی FTS/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/strategy-tree');
  });

  it('جستجوی تعاملی نماد و اعمال خودکار آن بر نقشه راه استراتژی', () => {
    renderWithProviders(<StrategyTreePage />);

    // فیلد جستجو وجود دارد
    const searchInput = screen.getByPlaceholderText(/جستجوی نماد برای تطبیق زنده/i);
    expect(searchInput).toBeInTheDocument();

    // تایپ نماد فولاد
    fireEvent.change(searchInput, { target: { value: 'فولاد' } });

    // انتخاب نماد از لیست کشویی
    const resultItem = screen.getByRole('button', { name: /فولاد مبارکه/i });
    expect(resultItem).toBeInTheDocument();
    fireEvent.click(resultItem);

    // سهم در استور و به عنوان نماد فعال ست شده
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
    expect(screen.getAllByText(/نماد فعال:/i).length).toBeGreaterThanOrEqual(1);

    // دکمه پاک کردن نماد
    const clearBtn = screen.getByRole('button', { name: /حذف نماد/i });
    fireEvent.click(clearBtn);
    expect(useSymbolStore.getState().symbol).toBe('');
  });
});
