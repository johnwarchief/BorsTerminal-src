// __tests__/fts-pipeline-bar.spec.tsx -- تست‌های نوار سراسری زنجیره و مودال مشاور FTS
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { FtsPipelineBar } from '../widgets/FtsPipelineBar';
import { StrategyHorizonSelector } from '../features/master/ui/StrategyHorizonSelector';

function renderWithClient(ui: React.ReactElement, initialRoute = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('FtsPipelineBar & StrategyHorizonSelector', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
    useStrategyStore.getState().setHorizon('trend');
  });

  it('وقتی نمادی انتخاب نشده، نوار خط لوله رندر نمی‌شود', () => {
    const { container } = renderWithClient(<FtsPipelineBar />);
    expect(container.firstChild).toBeNull();
  });

  it('با انتخاب نماد، نوار ۴ مرحله‌ای FTS به همراه نشان‌ها رندر می‌شود', () => {
    useSymbolStore.getState().setSymbol('فولاد');
    renderWithClient(<FtsPipelineBar />, '/market');

    const bar = screen.getByTestId('fts-pipeline-bar');
    expect(bar).toBeInTheDocument();
    expect(screen.getByText('فولاد')).toBeInTheDocument();

    expect(screen.getByTestId('fts-pipeline-step-tape')).toBeInTheDocument();
    expect(screen.getByTestId('fts-pipeline-step-technical')).toBeInTheDocument();
    expect(screen.getByTestId('fts-pipeline-step-fundamental')).toBeInTheDocument();
    expect(screen.getByTestId('fts-pipeline-step-master')).toBeInTheDocument();
  });

  it('کلیک روی دکمه مشاور تحلیلی، مودال تشریحی FTS را باز می‌کند', () => {
    useSymbolStore.getState().setSymbol('شپنا');
    renderWithClient(<FtsPipelineBar />, '/master');

    const copilotBtn = screen.getByRole('button', { name: /مشاور تحلیلی FTS/i });
    expect(copilotBtn).toBeInTheDocument();

    fireEvent.click(copilotBtn);

    const modal = screen.getByTestId('fts-analyst-modal');
    expect(modal).toBeInTheDocument();
    expect(screen.getByText(/مشاور تحلیلی و گزارش تشریحی نماد شپنا/i)).toBeInTheDocument();

    // بررسی وجود ۴ پرسش کلیدی تحلیلی
    expect(screen.getByText(/چرا بخریم یا نخریم؟ \(حکم قطعی\)/i)).toBeInTheDocument();
    expect(screen.getByText(/ستاپ تکنیکال و رفتار تابلوی سهم/i)).toBeInTheDocument();
    expect(screen.getByText(/عملکرد کدال و سلامت ۵ شاخص/i)).toBeInTheDocument();
    expect(screen.getByText(/برنامه معامله و حد ضرر دقیق/i)).toBeInTheDocument();

    // بستن مودال با کلیک روی ضربدر
    const closeBtn = screen.getByRole('button', { name: /بستن/i });
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId('fts-analyst-modal')).not.toBeInTheDocument();
  });

  it('انتخابگر StrategyHorizonSelector گزینه‌ها را تغییر می‌دهد و رویداد کلیک را شلیک می‌کند', () => {
    let selectedHorizon = 'trend';
    let modalOpened = false;

    const { rerender } = render(
      <StrategyHorizonSelector
        horizon={selectedHorizon as any}
        recommendedHorizon="hourglass"
        onSelectHorizon={(h) => {
          selectedHorizon = h;
        }}
        onOpenAnalystModal={() => {
          modalOpened = true;
        }}
      />,
    );

    expect(screen.getByTestId('strategy-horizon-selector')).toBeInTheDocument();
    expect(screen.getByText(/پیشنهاد سیستم: افق بلندمدت FTS/i)).toBeInTheDocument();

    // کلیک روی نوسان‌گیر
    const swingBtn = screen.getByTestId('strategy-btn-swing');
    fireEvent.click(swingBtn);
    expect(selectedHorizon).toBe('swing');

    // کلیک روی ساعت شنی
    const hourglassBtn = screen.getByTestId('strategy-btn-hourglass');
    fireEvent.click(hourglassBtn);
    expect(selectedHorizon).toBe('hourglass');

    // کلیک روی دکمه باز کردن مودال
    const openModalBtn = screen.getByRole('button', { name: /مشاور تشریحی FTS/i });
    fireEvent.click(openModalBtn);
    expect(modalOpened).toBe(true);
  });
});
