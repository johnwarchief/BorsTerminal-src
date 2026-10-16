// سایدبار چپ (#67): سه حالتِ صادقانه برایِ «وتو» — ردِ قطعی ≠ درانتظار ≠ بدونِ منبع
// شاهدِ زنده ۱۴۰۵-۰۷-۰۹: با یک سیگنالِ تابلو (همان حالتِ «رویِ ردیف کلیک کردم»)
// گیج قرمز «وتو / ورود متوقف / سد فیلتر ۱» می‌گفت، در حالی که بنیادی هنوز هیچ‌وقت
// سنجیده نشده بود. قاعدۀ مخزن (dev/weekly_veto_guard.py، dev/assembly_veto_v1064.py):
// بی‌داده وتو نیست.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSignalStore } from '@shared/stores/signalStore';
import { useCapitalStore } from '@features/master/stores/capitalStore';
import { SymbolInspector } from '@widgets/SymbolInspector';
import type { AgentSignal } from '@contracts/signal';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const SYM = 'شپنا';
const NOW = Date.now();

function sig(agent: AgentSignal['agentId'], patch: Partial<AgentSignal> = {}): AgentSignal {
  return {
    id: `${agent}:${SYM}:k:${NOW}`,
    agentId: agent,
    symbol: SYM,
    ts: NOW,
    direction: 'bullish',
    confidence: 'high',
    weight: 'major',
    title: `سیگنال ${agent}`,
    rationale: 'استدلال آزمایشی.',
    score: 70,
    evidence: [],
    sourceView: 'market',
    sourceRef: ['API'],
    validForMs: 24 * 3600_000,
    payload: { kind: 'setup', setups: ['breakout'] },
    ...patch,
  } as AgentSignal;
}

const isoIn = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

/** پاسخِ تقویم: رویدادِ مجمعِ خواستۀ آزمون */
function calendarWith(cat: string, days = 3, source: string = 'title') {
  fetchMock.mockImplementation((url: string) => {
    const body = String(url).includes('/api/calendar/upcoming')
      ? { status: 'ok', days: 14, count: 1, items: [{
          symbol: SYM, date: isoIn(days), cat,
          // «مورخ …» در عنوان ⇒ منشأ title (§۲۴ِ رأی). بی‌این میدان واکشی‌شده
          // وتو نمی‌سازد؛ سنجه‌هایِ زیر همین را می‌سنجند.
          title: 'آگهی دعوت به مجمع مورخ ۱۴۰۵/۰۷/۲۰',
          date_source: source }] }
      : { status: 'ok', data: [], items: [], decisions: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
  });
}

function renderInspector(qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  useSymbolStore.getState().setSymbol(SYM);
  return { qc, ...render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/market']}>
        <SymbolInspector />
      </MemoryRouter>
    </QueryClientProvider>,
  ) };
}

beforeEach(() => {
  useSignalStore.getState().clearSignals();
  useSymbolStore.getState().clearSymbol();
  useCapitalStore.getState().reset();
  fetchMock.mockReset();
  calendarWith('none');
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('سایدبار چپ: ردِ قطعی با «هنوز سنجیده نشده» یکی نمی‌شود', () => {
  // رأیِ مالک (1405-07-20): «در انتظار سنجش» درِ سایدبار ممنوع است و gauge با
  // حالتِ veto برایِ درِ بسته حفظ می‌شود. پس «سنجیده‌نشده» دیگر با «رد» یکی
  // نیست، ولی با «در حال محاسبه» هم یکی نیست: برچسبِ صریحِ «مسدود در …».
  it('فقط سیگنالِ تابلو (گیتِ بنیادی باز نشده) ⇒ «مسدود در بنیادی»، نه «در انتظارِ سنجش»', () => {
    useSignalStore.getState().publishSignal(sig('tape'));
    renderInspector();
    expect(screen.getByText('مسدود در بنیادی')).toBeInTheDocument();
    expect(screen.queryByText('در انتظارِ سنجش')).toBeNull();
    expect(screen.getByTestId('inspector-veto-why').textContent)
      .toContain('گیتِ بنیادیِ این نماد باز نیست');
  });

  it('بی‌هیچ داوری‌ای (نه گیتِ بسته، نه وتویِ واقعی) ⇒ گیج «وتو» نیست', () => {
    // همان قاعدۀ eabe829 که باید زنده بماند: بی‌داده وتو نیست. این حالت
    // «درِ بسته» ندارد، پس گیج حق ندارد قرمزِ وتو بگوید.
    renderInspector();
    expect(screen.queryByText('وتو'), 'بی‌هیچ حکمِ بستۀ واقعی نباید وتو بیاید').toBeNull();
    expect(screen.queryByText('ورود متوقف')).toBeNull();
  });

  it('مجمعِ قطعیِ سه روز دیگر ⇒ وتو + همان برچسبی که جدول می‌دهد', async () => {
    calendarWith('assembly');
    useSignalStore.getState().publishSignal(sig('tape'));
    renderInspector();
    expect(await screen.findByText('وتو')).toBeInTheDocument();
    // وتویِ مجمع از درخواستِ ناهمگامِ تقویم می‌آید؛ درِ محیطِ ماک به‌تاخیرِ یک
    // رندر می‌نشیند، پس منتظرِ همان بج می‌نشینیم (نه queryBy).
    expect(await screen.findByText('ورود متوقف')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-veto-why').textContent).toContain('مجمع');
  });

  // §۲۴ِ رأی درِ خودِ سایدبار: عددی که از انتشارِ اطلاعیه آمده تاریخِ مجمع نیست.
  // بک‌اند این را درِ `dev/test_calendar_v92.py` می‌پاید؛ اینجا مصرف‌کنندۀ
  // فرانتیِ همان میدان سنجیده می‌شود، چون سایدبار رأیِ دومِ خودش را دارد.
  it('مجمعِ بی‌تاریخِ جلسه در عنوان ⇒ سایدبار وتو نمی‌کند، «در انتظار» هم نه — برچسبِ اطلاعیه', () => {
    calendarWith('assembly', 3, 'publication_fallback');
    useSignalStore.getState().publishSignal(sig('fundamental'));
    useSignalStore.getState().publishSignal(sig('technical'));
    useSignalStore.getState().publishSignal(sig('tape'));
    renderInspector();
    const why = screen.getByTestId('inspector-veto-why').textContent ?? '';
    expect(why).not.toContain('مجمع');
  });

  it('لغو/تعویقِ مجمع وتو نمی‌سازد (همان قاعدۀ بک‌اند: تاریخِ نامعلوم)', () => {
    calendarWith('assemblyChange');
    useSignalStore.getState().publishSignal(sig('tape'));
    renderInspector();
    // لغو/تعویق وتویِ مجمع نمی‌سازد؛ اگر قرمزی رویِ صفحه هست، فقط از گیتِ
    // بسته‌یِ خودِ قیف است، نه از این اطلاعیه.
    expect(screen.queryByText('ورود متوقف'), 'لغوِ مجمع نباید وتویِ مجمع بسازد').toBeNull();
    expect(screen.getByTestId('inspector-veto-why').textContent).not.toContain('مجمع');
  });

  it('وتوی هفتگی از ردیفِ اسکرینرِ کش‌شده می‌آید — درخواستِ تازه‌ای ساخته نمی‌شود', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(['fts-screen', 120], {
      status: 'success',
      count: 1,
      data: [{ symbol: SYM, score: 5, weekly_veto: true, tech_matrix_decision: 'REJECT', tech_matrix_desc: 'روند نزولی' }],
    });
    useSignalStore.getState().publishSignal(sig('tape'));
    useSignalStore.getState().publishSignal(sig('fundamental', {
      payload: { score: 5, metrics: { gross_margin: 30, growth_pct: 20 } },
    }));
    renderInspector(qc);
    expect(screen.getByText('وتو')).toBeInTheDocument();
    expect(screen.getByTestId('inspector-veto-why').textContent).toContain('وتوی هفتگی — روند نزولی');
  });

  it('سیگنالِ پرتفو بی‌payload پنل را نمی‌شکند', () => {
    useSignalStore.getState().publishSignal(sig('portfolio', { payload: null }));
    expect(() => renderInspector()).not.toThrow();
    // §۱۵.۲۰: چراغِ سبد به صفحۀ «جزئیات بازار» رفته؛ ادعا همان است، فقط یک
    // کلیک جلوتر.
    fireEvent.click(screen.getByTestId('inspector-tab-detail'));
    expect(screen.getByText('پرتفوی')).toBeInTheDocument();
  });
});

describe('سایدبار چپ: رژیمِ سبد از همان منبعِ مستر خوانده می‌شود', () => {
  it('رژیمِ جنگی + وزنِ بالایِ نماد ⇒ سایدبار همان جوابِ مستر را می‌دهد، نه «خرید»', async () => {
    fetchMock.mockImplementation((url: string) => {
      const body = String(url).includes('/api/selection/portfolio')
        ? { status: 'success', decisions: [{ symbol: SYM, status: 'accept', weight_eff_pct: 15, sector: 'فلزات اساسي' }] }
        : { status: 'ok', data: [], items: [], decisions: [] };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
    });
    useCapitalStore.getState().setWarRegime(true);
    useSignalStore.getState().publishSignal(sig('fundamental', {
      payload: { score: 5, metrics: { gross_margin: 30, growth_pct: 20 } },
    }));
    useSignalStore.getState().publishSignal(sig('technical'));
    useSignalStore.getState().publishSignal(sig('tape', { payload: { pattern: 'closing_auction_pop' } }));
    renderInspector();
    await screen.findByText('تحت پایش/انتظار');
    // پیش از این اصلاح سایدبار warRegime را false ثابت می‌گذاشت و همین نماد را
    // «خرید قوی» می‌خواند، در حالی که مستر آن را در گیتِ سبد می‌بست.
    expect(screen.queryByText('خرید قوی')).toBeNull();
    expect(screen.getByTestId('inspector-veto-why').textContent).toContain('سبد');
  });
});
