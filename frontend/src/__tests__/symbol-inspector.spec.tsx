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

function renderInspector(path = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <SymbolInspector />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// §۱۵.۲۰ دو صفحۀ محلی: هر چه به «جزئیات بازار» رفته با یک کلیک دیده می‌شود —
// تست‌ها بازنویسیِ ادعا نیستند، دنبالۀ جابه‌جایی‌اند.
function openDetail() {
  fireEvent.click(screen.getByTestId('inspector-tab-detail'));
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
    expect(screen.getAllByText('شپنا').length).toBeGreaterThan(0);
    openDetail();
    expect(screen.getByText(/چارت تکنیکال ↗/)).toBeInTheDocument();
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

  it('صفحۀ «در یک نگاه»: گیج، دو چراغ، قدرت خرید/فروش و حجم/ارزش', () => {
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
    // §۱۵.۲۰: «سرانۀ خریدار» دیگر چراغِ جدا نیست؛ همان دو سرانه + نوارِ سهم +
    // نسبت درِ خانۀ «قدرت خرید/فروش» می‌نشینند (یک implementation، دو مصرف‌کننده).
    expect(screen.getByTestId('inspector-power')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-buy-sell')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-volume')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-events')).toBeInTheDocument();
    // چراغِ سبد و پیوندِ «چارت تکنیکال» به صفحۀ دوم رفته‌اند؛ بی‌باز کردنش نباید دیده شود
    expect(screen.queryByText('پرتفوی')).not.toBeInTheDocument();
    openDetail();
    expect(screen.getByText('پرتفوی')).toBeInTheDocument();
    expect(screen.getAllByText('نگهداری').length).toBeGreaterThan(0);
  });

  // ترتیبِ سطرها رأیِ مالک است، نه سلیقۀ پیاده‌ساز (§۱۵.۲۰): یک تستِ ترتیب،
  // اگر جابه‌جاییِ بعدی چیزی را از صفحۀ اول بیاندازد سرِ همین‌جا می‌شکند.
  it('ترتیبِ «در یک نظرة» همان رأیِ ۱۴۰۵-۰۷-۱۷ است', () => {
    useSymbolStore.getState().setSymbol('شپنا');
    // نشانگرِ مرحلۀ غربالگری فقط در مسیرِ خودِ قیف می‌آید (§تب‌هایِ بیرونِ قیف
    // null)، پس سنجشِ ترتیب باید درِ همان مسیر باشد.
    renderInspector('/technical/شپنا');
    const want = ['inspector-volume', 'inspector-market-cap', 'inspector-power',
                  'inspector-regulatory', 'تکنیکال FTS', 'نمره بنیادی',
                  'inspector-stage', 'inspector-events', 'inspector-veto-why'];
    const glance = screen.getByTestId('inspector-page-glance');
    const seen: string[] = [];
    glance.querySelectorAll('*').forEach((el) => {
      const tid = el.getAttribute('data-testid');
      const hit = tid && want.includes(tid) ? tid
        : /^(تکنیکال FTS|نمره بنیادی)$/.test((el.textContent ?? '').trim())
          ? (el.textContent ?? '').trim() : null;
      if (hit && seen[seen.length - 1] !== hit && !seen.includes(hit)) seen.push(hit);
    });
    expect(seen).toEqual(want);
  });

  it('بدون سیگنال برچسب بدون داده می دهد', () => {
    useSymbolStore.getState().setSymbol('فولاد');
    renderInspector();
    expect(screen.getAllByText('بدون داده').length).toBeGreaterThan(0);
    expect(screen.getByText(/۰\/۴ سیگنال/)).toBeInTheDocument();
  });
});
