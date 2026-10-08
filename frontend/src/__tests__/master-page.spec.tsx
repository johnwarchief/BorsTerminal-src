// تست داشبورد مستر v2: گیتینگ، برنامه معاملاتی، synthesis با fetch ماک‌شده
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { useSignalStore } from '@shared/stores/signalStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import type { AgentSignal, FundamentalPayload, TechnicalPayload } from '@contracts/index';
import MasterPage from '@features/master/routes/MasterPage';

const NOW = Date.now();

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function fundSig(direction: 'bullish' | 'bearish', score: number): AgentSignal<FundamentalPayload> {
  return {
    id: `fundamental:شپنا:k:${NOW}`,
    agentId: 'fundamental',
    symbol: 'شپنا',
    ts: NOW,
    direction,
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال بنیادی',
    rationale: 'استدلال آزمایشی.',
    score,
    evidence: [],
    sourceView: 'fundamental',
    sourceRef: ['API'],
    validForMs: 90 * 24 * 3600_000,
    payload: {
      kind: 'fts_card',
      score: 4,
      passes: {},
      riskGates: [],
      epsSeries: [],
      dataGaps: [],
      staleness: false,
      statementAgeDays: 10,
      dataQuality: 'complete',
      peVsSector: null,
      profitYoY: null,
    },
  };
}

function techSig(direction: 'bullish' | 'bearish' | 'neutral', score: number, setups: TechnicalPayload['setups']): AgentSignal<TechnicalPayload> {
  return {
    id: `technical:شپنا:k:${NOW}`,
    agentId: 'technical',
    symbol: 'شپنا',
    ts: NOW,
    direction,
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال تکنیکال',
    rationale: 'استدلال آزمایشی.',
    score,
    evidence: [],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: 2 * 24 * 3600_000,
    payload: { kind: 'setup', timeframe: 'daily', setups, stopLossRef: null, stopLossPrice: null, keyLevels: [], dataQuality: 'complete' },
  };
}

function ftsFeed(hasFib = true) {
  return {
    status: 'success',
    symbol: 'شپنا',
    fts: {
      fib: hasFib
        ? {
            retrace_base_high: 36030,
            retrace_base_low: 29460,
            zone_33_40: { lo: 33500, hi: 34200, in_zone: false },
            zone_618_70: { lo: 31000, hi: 31800, in_zone: false },
          }
        : null,
      jet: { active: false, resistance: 36030, ath: true, close: 40840, pct_above_res: 13.35 },
      exit_engine: {
        verdict: 'hold',
        signals: [],
        l1: { hard_stop: 27987, stop_basis: 'swing_low', stop_hit: false, ma14_exit: false, ma14_exit_pending: false, ma14: 34386, close: 40840 },
      },
    },
  };
}

function renderMaster(openAdvanced = true) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const out = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/master/شپنا']}>
        <Routes>
          <Route path="/master/:symbol?" element={<MasterPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // Round L: خلاصه اول، جزئیات دوم — برآیندهایِ قدیمی این تست‌ها در بخشِ
  // «جزئیات و برنامهٔ معاملاتی»اند، پس همان‌جا باز می‌شود (خودِ گیتِ باز/بسته در
  // تستِ «پیش‌فرض بسته است» می‌سنجد).
  if (openAdvanced) {
    fireEvent.click(out.getByTestId('master-toggle-advanced'));
  }
  return out;
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    if (u.includes('/api/funnel')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(FUNNEL_FIXTURE) } as unknown as Response);
    }
    if (u.startsWith('/api/fts/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(ftsFeed()) } as unknown as Response);
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'empty' }) } as unknown as Response);
  });
  useSignalStore.getState().clearSignals();
  useSymbolStore.getState().setSymbol('');
});

describe('داشبورد مستر v2', () => {
  it('برآیند و ماتریس چهار ایجنت و گیتینگ و برنامه معاملاتی را نشان می دهد', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 80));
    useSignalStore.getState().publishSignal(techSig('bullish', 60, ['breakout']));
    renderMaster();
    await waitFor(() => {
      expect(screen.getByText('برآیند مستر برای شپنا')).toBeInTheDocument();
    });
    // کارت برنامه معاملاتی
    await waitFor(() => {
      expect(screen.getByText('برنامه معاملاتی شپنا')).toBeInTheDocument();
    });
    expect(screen.getByText('Trade Execution Blueprint') || screen.getAllByText(/برنامه معاملاتی/).length).toBeTruthy();
    // فیلترهای ۴گانه
    expect(await screen.findByText('چرخه فیلترهای ۴گانه FTS')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۱: بنیادی')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۲: تکنیکال')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۳: تابلو')).toBeInTheDocument();
    // باکس synthesis
    expect(screen.getByLabelText('تحلیل داوری مستر')).toBeInTheDocument();
    // آمار رای‌گیری
    expect(screen.getByText('آمار رای‌گیری')).toBeInTheDocument();
    useSignalStore.getState().clearSignals();
  });

  it('پارامترهای پله‌ها از دادهٔ چارت ماک‌شده می‌آیند', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 80));
    useSignalStore.getState().publishSignal(techSig('bullish', 60, ['breakout']));
    renderMaster();
    await waitFor(() => {
      expect(screen.getByText('برنامه معاملاتی شپنا')).toBeInTheDocument();
    });
    // اعداد فیبو ماک‌شده در کارت رندر شده‌اند
    await waitFor(() => {
      expect(screen.getByText(/۳۳٬۵۰۰|33500/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/۲۷٬۹۸۷|27987/).length).toBeGreaterThan(0);
  });

  it('رد بنیادی ⇒ حکم ورود پله‌ای نمی‌آید و گیتینگ رد را نشان می‌دهد', async () => {
    useSignalStore.getState().publishSignal(fundSig('bearish', 25));
    useSignalStore.getState().publishSignal(techSig('bullish', 85, ['breakout']));
    renderMaster();
    await waitFor(() => {
      expect(screen.getByText('برنامه معاملاتی شپنا')).toBeInTheDocument();
    });
    // گیت بنیادی رد
    await waitFor(() => {
      const failBadges = screen.getAllByText('رد');
      expect(failBadges.length).toBeGreaterThan(0);
    });
    // هرگز خرید نمی‌گیرد — badge حکم نهایی
    expect(screen.queryByText('ورود پله‌ای')).toBeNull();
    // synthesis دلیل را می‌گوید
    const box = screen.getByLabelText('تحلیل داوری مستر');
    expect(box.textContent).toContain('هرگز خرید');
  });

  it('بدون سیگنال حالت خالی تمیز دارد', async () => {
    renderMaster();
    await waitFor(() => {
      expect(screen.getByText('هنوز سیگنالی در باس نیست')).toBeInTheDocument();
    });
  });

  // Round L: برآیندِ تک‌ناماد بالای صفحه است و جزئیات زیرِ یک گیتِ نمایش
  it('خلاصه در بالا، جزئیات پیش‌فرض بسته — و با کلیک باز می‌شود', async () => {
    renderMaster(false);
    expect(screen.getByTestId('master-dossier')).toBeInTheDocument();
    expect(screen.queryByText('آمار رای‌گیری')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('master-toggle-advanced'));
    await waitFor(() => expect(screen.getByText('آمار رای‌گیری')).toBeInTheDocument());
  });
});
