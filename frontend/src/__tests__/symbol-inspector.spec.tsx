// تست سایدبار بازرسی نماد: انیمیشن باز/بسته و ویجت‌ها
import { render, screen, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSignalStore } from '@shared/stores/signalStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import type { AgentSignal } from '@contracts/signal';

const NOW = 1726000000000;

function sig(agent: AgentSignal['agentId'], direction: AgentSignal['direction'], score: number): AgentSignal {
  return {
    id: `${agent}:شپنا:k:${NOW}`,
    agentId: agent,
    symbol: 'شپنا',
    ts: NOW,
    direction,
    confidence: 'high',
    weight: 'major',
    title: `سیگنال ${agent}`,
    rationale: 'استدلال آزمایشی.',
    score,
    evidence: [],
    sourceView: 'market',
    sourceRef: ['API'],
    validForMs: 24 * 3600_000,
    payload:
      agent === 'portfolio'
        ? { kind: 'position_state', decision: 'accept', weightPct: 10, stopLoss: null, alerts: [] }
        : { kind: 'x' },
  };
}

function renderInspector() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SymbolInspector />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('سایدبار بازرسی نماد', () => {
  beforeEach(() => {
    useSignalStore.getState().clearSignals();
    useSymbolStore.getState().clearSymbol();
  });

  it('بدون نماد پنهان است (لغزش به بیرون)', () => {
    renderInspector();
    const aside = screen.getByLabelText(/بازرسی نماد/);
    expect(aside.className).toContain('-translate-x-full');
    expect(aside.getAttribute('aria-hidden')).toBe('true');
  });

  it('با انتخاب نماد می لغزد داخل و هدر نشان می دهد', () => {
    useSymbolStore.getState().setSymbol('شپنا');
    renderInspector();
    const aside = screen.getByLabelText('بازرسی نماد شپنا');
    expect(aside.className).toContain('translate-x-0');
    expect(screen.getByText('شپنا')).toBeInTheDocument();
    expect(screen.getByText('پرش به چارت تکنیکال ↗')).toBeInTheDocument();
    expect(screen.getByText('بررسی کدال ↗')).toBeInTheDocument();
  });

  it('دکمه بستن نماد را خالی می کند', () => {
    useSymbolStore.getState().setSymbol('شپنا');
    renderInspector();
    fireEvent.click(screen.getByRole('button', { name: 'بستن پنل نماد' }));
    expect(useSymbolStore.getState().symbol).toBe('');
    const aside = screen.getByLabelText(/بازرسی نماد/);
    expect(aside.className).toContain('-translate-x-full');
  });

  it('مینی گیج و چهار چراغ با سیگنال فعال رندر می شوند', () => {
    useSymbolStore.getState().setSymbol('شپنا');
    const bus = useSignalStore.getState();
    bus.publishSignal(sig('fundamental', 'bullish', 80));
    bus.publishSignal(sig('technical', 'bullish', 60));
    bus.publishSignal(sig('tape', 'neutral', 50));
    bus.publishSignal(sig('portfolio', 'neutral', 55));
    renderInspector();
    expect(screen.getByLabelText('گیج برآیند')).toBeInTheDocument();
    expect(screen.getByText('نمره بنیادی')).toBeInTheDocument();
    expect(screen.getByText('تکنیکال FTS')).toBeInTheDocument();
    expect(screen.getByText('سرانه خریدار')).toBeInTheDocument();
    expect(screen.getByText('پرتفوی')).toBeInTheDocument();
    expect(screen.getByText('نگهداری')).toBeInTheDocument();
  });

  it('بدون سیگنال برچسب بدون داده می دهد', () => {
    useSymbolStore.getState().setSymbol('فولاد');
    renderInspector();
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
    expect(screen.getByText(/۰\/۴ سیگنال/)).toBeInTheDocument();
  });
});
