// __tests__/strategy-tree-page.spec.tsx -- تست‌های صفحه جامع درخت استراتژی FTS
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import StrategyTreePage from '../features/master/routes/StrategyTreePage';
import { useSymbolStore } from '../shared/stores/symbolStore';
import { Sidebar } from '../app/components/Sidebar';

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

    // ۴ ستون متناظر با ۴ صفحه جزوه
    expect(screen.getByText(/۱\. فیلتر بنیادی \(۵ شاخص کدال\)/i)).toBeInTheDocument();
    expect(screen.getByText(/۲\. فیلتر تکنیکال ۲ زمانه/i)).toBeInTheDocument();
    expect(screen.getByText(/۳\. تابلوخوانی و زمان‌سنج \(S\)/i)).toBeInTheDocument();
    expect(screen.getByText(/۴\. مدیریت سرمایه و خروج/i)).toBeInTheDocument();
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

  it('لینک منوی درخت استراتژی FTS در سایدبار وجود دارد', () => {
    renderWithProviders(<Sidebar />);
    const link = screen.getByRole('link', { name: /درخت استراتژی FTS/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/strategy-tree');
  });
});
