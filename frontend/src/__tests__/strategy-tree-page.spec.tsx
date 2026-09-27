// __tests__/strategy-tree-page.spec.tsx -- تست‌های صفحه جامع درخت استراتژی FTS
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

describe('StrategyTreePage — درخت استراتژی ۴ صفحه‌ای FTS', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
  });

  it('رندر سربرگ و ۴ فاز درختی بر پایه جزوه FTS', () => {
    renderWithProviders(<StrategyTreePage />);

    // سربرگ
    expect(screen.getByText(/نقشه راه و درخت جامع استراتژی FTS/i)).toBeInTheDocument();
    expect(screen.getByText(/۴ چارت در یک نما/i)).toBeInTheDocument();

    // نما از آنِ بوم ابسیدین است و گریدِ تکراری پیش‌فرض باز نمی‌شود
    expect(screen.getByTestId('obsidian-strategy-canvas')).toBeInTheDocument();
    expect(screen.queryByText(/۱\. فیلتر بنیادی \(۵ شاخص کدال\)/i)).not.toBeInTheDocument();

    // ارکان متناظر با ۴ صفحه جزوه در نمای گرید
    fireEvent.click(screen.getByRole('button', { name: /نمای گرید ۴ ستونه/i }));
    expect(screen.getByText(/۱\. فیلتر بنیادی \(۵ شاخص کدال\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/۲\. فیلتر تکنیکال ۲ زمانه/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/۳\. تابلوخوانی و زمان‌سنج/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/۴\. مدیریت سرمایه و خروج/i).length).toBeGreaterThanOrEqual(1);
  });

  it('تغییر سبک بازی: کلیک روی شخص روندگیر و ساعت شنی مسیرها را به‌روزرسانی می‌کند', () => {
    renderWithProviders(<StrategyTreePage />);

    // کلیک روی شخص روندگیر
    const trendBtn = screen.getByRole('button', { name: /شخص روندگیر/i });
    fireEvent.click(trendBtn);

    expect(screen.getByText(/پلن سهامداری و روندگیری FTS/i)).toBeInTheDocument();

    // کلیک روی ساعت شنی
    const hourglassBtn = screen.getByRole('button', { name: /استراتژی ساعت شنی/i });
    fireEvent.click(hourglassBtn);

    expect(screen.getByText(/پلن سرمایه‌گذاری ساعت شنی FTS/i)).toBeInTheDocument();
  });

  it('حالت سفارشی (Custom Path): انتخاب دستی گره‌ها خلاصه استراتژی را تغییر می‌دهد', () => {
    renderWithProviders(<StrategyTreePage />);

    const customBtn = screen.getByRole('button', { name: /مسیر سفارشی/i });
    fireEvent.click(customBtn);

    expect(screen.getByText(/پلن سفارشی معامله‌گر/i)).toBeInTheDocument();
  });

  it('سوییچ نما: تغییر حالت نمایش بین گراف ابسیدین و تفکیک ۴ چارت کار می‌کند', () => {
    renderWithProviders(<StrategyTreePage />);

    // سوییچ به نمای خالص ابسیدین
    const obsidianTab = screen.getByRole('button', { name: /نمودار شبکه ابسیدین/i });
    fireEvent.click(obsidianTab);
    expect(screen.getByTestId('obsidian-strategy-canvas')).toBeInTheDocument();

    // سوییچ به نمای گرید ۴ ستونه
    const gridTab = screen.getByRole('button', { name: /نمای گرید ۴ ستونه/i });
    fireEvent.click(gridTab);
    expect(screen.queryByTestId('obsidian-strategy-canvas')).not.toBeInTheDocument();
    expect(screen.getByText(/۱\. فیلتر بنیادی \(۵ شاخص کدال\)/i)).toBeInTheDocument();

    // سوییچ مجدد به ترکیبی
    const bothTab = screen.getByRole('button', { name: /ترکیبی/i });
    fireEvent.click(bothTab);
    expect(screen.getByTestId('obsidian-strategy-canvas')).toBeInTheDocument();
    expect(screen.getByText(/۱\. فیلتر بنیادی \(۵ شاخص کدال\)/i)).toBeInTheDocument();
  });

  it('ویرایشگر تعاملی پارامترها: تغییر مقادیر استراتژی در استور و نمایش در دستورالعمل', () => {
    renderWithProviders(<StrategyTreePage />);

    // بررسی اسلایدر ضریب حجم مشکوک پیش‌فرض
    expect(screen.getByText(/ضریب حجم مشکوک:/i)).toBeInTheDocument();
    expect(screen.getByText(/جزوه: ۳\.۰×/i)).toBeInTheDocument();

    // تغییر مقدار ضریب حجم مشکوک
    const sliders = screen.getAllByRole('slider');
    expect(sliders.length).toBeGreaterThanOrEqual(1);
    fireEvent.change(sliders[0], { target: { value: '2.5' } });

    // دکمه بازنشانی به جزوه وجود دارد
    const resetBtn = screen.getByRole('button', { name: /بازنشانی به جزوه/i });
    expect(resetBtn).toBeInTheDocument();
    fireEvent.click(resetBtn);
  });

  it('لینک منوی درخت استراتژی FTS در سایدبار وجود دارد', () => {
    renderWithProviders(<Sidebar />);
    const link = screen.getByRole('link', { name: /درخت استراتژی FTS/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/strategy-tree');
  });

  it('جستجوی تعاملی نماد و اعمال خودکار آن بر درخت استراتژی', () => {
    renderWithProviders(<StrategyTreePage />);

    // فیلد جستجو وجود دارد
    const searchInput = screen.getByPlaceholderText(/جستجوی نماد یا شرکت/i);
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
    expect(screen.getByRole('button', { name: /تطبیق/i })).toBeInTheDocument();

    // دکمه پاک کردن نماد
    const clearBtn = screen.getByRole('button', { name: /حذف نماد/i });
    fireEvent.click(clearBtn);
    expect(useSymbolStore.getState().symbol).toBe('');
  });
});


