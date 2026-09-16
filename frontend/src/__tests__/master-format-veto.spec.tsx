// تست M-05: فرمت اعداد، وتوی سخت‌گیرانه (بدون بازتوزیع وزن)، سرمایهٔ فرضی DCA، استپر متراکم ۴ گیتی
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import MasterPage from '@features/master/routes/MasterPage';
import { useSignalStore } from '@shared/stores/signalStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useCapitalStore } from '@features/master/stores/capitalStore';
import type { AgentSignal, FundamentalPayload, TechnicalPayload } from '@contracts/index';
import { DEFINITE_ACTION_FA, definiteDecision, runStrictGates, EMPTY_WEEKLY } from '@features/master/lib/strictGates';
import { layerStatusLabel } from '@features/master/lib/managementSummary';
import { buildTradeBlueprint } from '@features/master/lib/dcaCalc';
import { DEFAULT_ASSUMED_CAPITAL, fa0, fa1, fa2 } from '@features/master/lib/fmtNum';

const NOW = Date.now();
const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function fundSig(direction: 'bullish' | 'bearish', score: number, extra: Record<string, unknown> = {}): AgentSignal<FundamentalPayload> {
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
      ...extra,
    } as FundamentalPayload,
  };
}

function techSig(direction: 'bullish' | 'bearish' | 'neutral', setups: TechnicalPayload['setups']): AgentSignal<TechnicalPayload> {
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
    score: 70,
    evidence: [],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: 2 * 24 * 3600_000,
    payload: {
      kind: 'setup',
      timeframe: 'daily',
      setups,
      stopLossRef: null,
      stopLossPrice: null,
      keyLevels: [],
      dataQuality: 'complete',
    } as TechnicalPayload,
  };
}

function tapeSig(multiple: number, pattern: 'suspicious_volume' | 'closing_auction_pop' = 'suspicious_volume') {
  return {
    id: `tape:شپنا:k:${NOW}`,
    agentId: 'tape',
    symbol: 'شپنا',
    ts: NOW,
    direction: pattern === 'closing_auction_pop' ? 'bullish' : 'neutral',
    confidence: 'high',
    weight: 'major',
    title: 'سیگنال تابلو',
    rationale: 'استدلال آزمایشی.',
    score: 60,
    evidence: [],
    sourceView: 'market',
    sourceRef: ['API'],
    validForMs: 3600_000,
    payload: { kind: 'tape_pattern', pattern, lastVsClose: 0, volumeMultiple: multiple },
  } as unknown as AgentSignal;
}

const REGIME = { inBasket: true, industryUsedPct: 2.5, industryCapPct: 20, warRegime: false, symbolWeightPct: 4 };

function ftsFeed() {
  return {
    status: 'success',
    symbol: 'شپنا',
    fts: {
      fib: {
        retrace_base_high: 36030,
        retrace_base_low: 29460,
        zone_33_40: { lo: 33500, hi: 34200, in_zone: false },
        zone_618_70: { lo: 31000, hi: 31800, in_zone: false },
      },
      jet: { active: false, resistance: 36030, ath: true, close: 40840, pct_above_res: 13.35 },
      exit_engine: { verdict: 'hold', signals: [], l1: { hard_stop: 27987, stop_basis: 'swing_low', hit: false, ma14: 34386, close: 40840 } },
    },
  };
}

function renderMaster() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/master/شپنا']}>
        <Routes>
          <Route path="/master/:symbol?" element={<MasterPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    const u = String(url);
    const ok = (body: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
    if (u.startsWith('/api/fts/')) return ok(ftsFeed());
    if (u.startsWith('/api/selection/portfolio')) return ok({ status: 'success', decisions: [], counts: {}, limits: {} });
    if (u.startsWith('/api/market')) return ok({ status: 'ok', count: 0, data: [] });
    return ok({ status: 'empty' });
  });
  useSignalStore.getState().clearSignals();
  useSymbolStore.getState().setSymbol('');
  useCapitalStore.getState().reset();
  localStorage.clear();
});

describe('۱) فرمت اعداد — هیچ اعشار طولانی نمایش داده نمی‌شود', () => {
  it('fa0/fa1/fa2 اعداد را کوتاه می‌کنند', () => {
    expect(fa1(18.095633224)).toBe('۱۸.۱');
    expect(fa0(18.095633224)).toBe('۱۸');
    expect(fa2(18.095633224)).toBe('۱۸.۱۰');
    expect(fa1(2)).toBe('۲.۰');
    expect(fa0(33850.4)).toBe('۳۳٬۸۵۰');
    expect(fa0(null)).toBe('بدون داده');
  });

  it('بج «حجم مشکوک» در جدول داوری با یک رقم اعشار رندر می‌شود', () => {
    const label = layerStatusLabel('tape', tapeSig(18.095633224));
    expect(label.text).toBe('حجم مشکوک ۱۸.۱ برابر');
    expect(label.text).not.toContain('۱۸.۰۹۵۶۳۳۲۲۴');
  });

  it('دلیل ریاضی گیت‌ها هم عدد خام طولانی ندارد', () => {
    const res = runStrictGates(
      { fundamental: fundSig('bullish', 70, { metrics: { gross_margin: 18.095633224 } }), technical: techSig('bullish', ['breakout']) },
      REGIME,
      EMPTY_WEEKLY,
    );
    const g = res.gates.find((x) => x.id === 'fundamental')!;
    expect(g.reason).toContain('۱۸.۱');
    expect(g.reason).not.toContain('18.095633224');
  });
});

describe('۲) وتوی سخت‌گیرانه — ممنوعیت بازتوزیع وزن', () => {
  it('بنیاد بدون داده ⇒ سوئیچ قطعی به «وتو در گیت ۱»', () => {
    const res = runStrictGates({ technical: techSig('bullish', ['breakout']) }, REGIME, EMPTY_WEEKLY);
    const d = definiteDecision(res);
    expect(d.action).toBe('veto_gate1');
    expect(d.label).toBe('وتو در گیت ۱ (توقف تا شفافیت بنیادی)');
    expect(d.allGatesPassed).toBe(false);
  });

  it('در انتظار شکست تکنیکال ⇒ سوئیچ قطعی به «وتو در گیت ۲»', () => {
    const res = runStrictGates(
      {
        fundamental: fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 40 } }),
        technical: techSig('bullish', ['trend']),
        tape: tapeSig(3.2),
      },
      REGIME,
      EMPTY_WEEKLY,
    );
    const d = definiteDecision(res);
    expect(d.action).toBe('veto_gate2');
    expect(d.label).toBe('وتو در گیت ۲ (توقف تا شکست تکنیکال)');
  });

  it('هر چهار گیت سبز ⇒ «خرید پله‌ای» (تنها حالت معتبر خرید)', () => {
    const res = runStrictGates(
      {
        fundamental: fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 40 } }),
        technical: techSig('bullish', ['breakout']),
        tape: tapeSig(4, 'closing_auction_pop'),
      },
      REGIME,
      { uptrend: true, belowMa52: false, rsi: 55 },
    );
    expect(res.gates.every((g) => g.state === 'passed')).toBe(true);
    expect(definiteDecision(res).action).toBe('ladder_buy');
    expect(DEFINITE_ACTION_FA.ladder_buy).toBe('خرید پله‌ای');
  });

  it('در تب ارشد متن بازتوزیع وزن حذف شده و به‌جایش «بازتوزیع نمی‌شوند» آمده', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 40 } }));
    renderMaster();
    await screen.findByText('آمار رای‌گیری');
    expect(document.body.textContent).not.toContain('وزن‌ها بین آرای فعال بازتوزیع شده‌اند');
    expect(document.body.textContent).toContain('بازتوزیع نمی‌شوند');
  });
});

describe('۳) ماشین‌حساب پله‌ها — سرمایهٔ فرضی پیش‌فرض', () => {
  it('با سرمایهٔ فرضی ۱۰۰ میلیونی، مبلغ و تعداد برگه فوراً محاسبه می‌شود', () => {
    const r = buildTradeBlueprint({
      capitalToman: DEFAULT_ASSUMED_CAPITAL,
      assumedCapital: true,
      baseStepWeightPct: 5,
      industryCapPct: 20,
      industryUsedPct: 2,
      step1: { lo: 33500, hi: 34200 },
      step2: { lo: 31000, hi: 31800 },
      breakout: { lo: 36030 },
      priceActionStop: 27987,
      resistance: 42000,
      currentPrice: 40840,
      warCapPct: null,
    });
    expect(DEFAULT_ASSUMED_CAPITAL).toBe(100_000_000);
    expect(r.hasCapital).toBe(true);
    const s1 = r.steps.find((s) => s.key === 'step1')!;
    expect(s1.amountToman).toBe(5_000_000);
    expect(s1.shares).toBeGreaterThan(0);
    expect(r.notes.join(' ')).toContain('سرمایهٔ فرضی پیش‌فرض');
  });

  it('در تب ارشد ستون‌های مبلغ/تعداد برگه «بدون داده» نمی‌مانند', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 40 } }));
    renderMaster();
    await screen.findByText('ماشین‌حساب برنامهٔ معاملاتی و DCA');
    expect(screen.getByLabelText('سرمایهٔ کل (تومان)')).toHaveValue(100000000);
    expect(screen.getAllByText(/سرمایهٔ فرضی/).length).toBeGreaterThan(0);
    // داخل ماشین‌حساب، ستون‌های مبلغ/برگه عدد دارند (بدون «بدون داده»)
    const blueprint = screen.getByLabelText('برنامه معاملاتی و ماشین‌حساب DCA');
    await waitFor(() => expect(within(blueprint).queryByText('بدون داده')).toBeNull());
  });
});

describe('۴) استپر افقی متراکم چهار گیتی', () => {
  it('چهار کارت در یک نوار افقی (تک‌ردیفه در lg) با وضعیت رنگی', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 40 } }));
    useSignalStore.getState().publishSignal(techSig('bullish', ['breakout']));
    renderMaster();
    const pipeline = (await screen.findByText('پایپ‌لاین گیتینگ FTS')).closest('div.glass-panel') as HTMLElement;
    expect(pipeline).toBeTruthy();
    const list = pipeline.querySelector('ol')!;
    expect(list.className).toContain('lg:flex-row');
    expect(list.querySelectorAll('li').length).toBe(4);
    // برچسب‌های پله‌ها
    expect(screen.getByText('گیت ۱ · بنیادی')).toBeInTheDocument();
    expect(screen.getByText('گیت ۴ · سبد و رژیم ریسک')).toBeInTheDocument();
    // وضعیت‌های رنگی
    expect(screen.getAllByLabelText(/وضعیت گیت .*: (عبور|رد|انتظار)/).length).toBe(4);
    // Audit Popover در DOM هست (نمایش با هاور) — یکی برای هر گیت
    expect(within(pipeline).getAllByRole('tooltip').length).toBe(4);
    expect(screen.getAllByText(/دلیل ریاضی وضعیت/).length).toBe(4);
  });
});
