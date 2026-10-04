// تست بازطراحی تب ایجنت ارشد (M-03): ماشین وتو، استپر ۴ گیتی، خلاصهٔ آفلاین، DCA و اکشن‌ها
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router';
import MasterPage from '@features/master/routes/MasterPage';
import { useSignalStore } from '@shared/stores/signalStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useCapitalStore } from '@features/master/stores/capitalStore';
import type { AgentSignal, FundamentalPayload, TechnicalPayload } from '@contracts/index';
import {
  definiteDecision,
  hourglassSwitch,
  isSuperFundamental,
  runStrictGates,
  weeklyTrendFromSignal,
  EMPTY_WEEKLY,
  type PortfolioRegimeInput,
} from '@features/master/lib/strictGates';
import {
  buildManagementSummary,
  halfExitPlan,
  layerStatusLabel,
} from '@features/master/lib/managementSummary';
import { buildTradeBlueprint } from '@features/master/lib/dcaCalc';

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

function techSig(
  direction: 'bullish' | 'bearish' | 'neutral',
  score: number,
  setups: TechnicalPayload['setups'],
  extra: Record<string, unknown> = {},
): AgentSignal<TechnicalPayload> {
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
    payload: {
      kind: 'setup',
      timeframe: 'daily',
      setups,
      stopLossRef: null,
      stopLossPrice: null,
      keyLevels: [],
      dataQuality: 'complete',
      ...extra,
    } as TechnicalPayload,
  };
}

function tapeSig(pattern: 'closing_auction_pop' | 'suspicious_volume', multiple: number | null) {
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
    payload: { kind: 'tape_pattern', pattern, lastVsClose: 0.01, volumeMultiple: multiple },
  } as unknown as AgentSignal;
}

const REGIME: PortfolioRegimeInput = {
  inBasket: true,
  industryUsedPct: 3,
  industryCapPct: 20,
  warRegime: false,
  symbolWeightPct: 5,
};

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
      exit_engine: {
        verdict: 'hold',
        signals: [],
        l1: { hard_stop: 27987, stop_basis: 'swing_low', stop_hit: false, ma14: 34386, close: 40840 },
      },
    },
  };
}

function renderMaster() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const out = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/master/شپنا']}>
        <Routes>
          <Route path="/master/:symbol?" element={<MasterPage />} />
          <Route path="/portfolio" element={<div>صفحه پرتفوی</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  // Round L: جزئیات پشتِ گیتِ نمایش‌اند؛ این تست‌ها همان
  // جزئیات را می‌سنجند، پس بخشِ «جزئیات» اینجا باز می‌شود.
  fireEvent.click(out.getByTestId('master-toggle-advanced'));
  return out;
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string, opts?: { method?: string }) => {
    const u = String(url);
    const ok = (body: unknown) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response);
    if (u.startsWith('/api/fts/')) return ok(ftsFeed());
    if (u.startsWith('/api/selection/portfolio'))
      return ok({ status: 'success', decisions: [{ symbol: 'شپنا', status: 'accept', weight_eff_pct: 5, sector: 'فلزات اساسي' }], counts: {}, limits: {} });
    if (u.startsWith('/api/market')) return ok({ status: 'ok', count: 1, data: [{ symbol: 'شپنا', p_closing: 40840, p_last: 40840 }] });
    if (opts?.method === 'POST') return ok({ status: 'success', symbol: 'شپنا', saved_status: 'accept' });
    return ok({ status: 'empty' });
  });
  useSignalStore.getState().clearSignals();
  useSymbolStore.getState().setSymbol('');
  useCapitalStore.getState().reset();
  localStorage.clear();
});

describe('ماشین وتو سخت‌گیرانه (بدون میانگین خطی)', () => {
  it('هر چهار گیت سبز ⇒ «خرید پله‌ای»', () => {
    const res = runStrictGates(
      {
        fundamental: fundSig('bullish', 85, { metrics: { gross_margin: 24, growth_pct: 40 } }),
        technical: techSig('bullish', 70, ['breakout'], { weekly: { uptrend: true, belowMa52: false, rsi: 60 } }),
        tape: tapeSig('closing_auction_pop', 4),
      },
      REGIME,
      { uptrend: true, belowMa52: false, rsi: 60 },
    );
    expect(res.gates).toHaveLength(4);
    expect(res.gates.every((g) => g.state === 'passed')).toBe(true);
    const d = definiteDecision(res);
    expect(d.action).toBe('ladder_buy');
    expect(d.allGatesPassed).toBe(true);
  });

  it('نبود روند هفتگی صعودی ⇒ وتوی فوری', () => {
    const res = runStrictGates(
      { fundamental: fundSig('bullish', 85), technical: techSig('bullish', 70, ['breakout']), tape: tapeSig('closing_auction_pop', 4) },
      REGIME,
      { uptrend: false, belowMa52: true, rsi: 55 },
    );
    const techGate = res.gates.find((g) => g.id === 'technical')!;
    expect(techGate.state).toBe('blocked');
    expect(techGate.veto).toBe(true);
    const d = definiteDecision(res);
    expect(d.action).toBe('veto');
    expect(d.label).toBe('رد قطعی (وتو)');
  });

  it('نقض بنیادی + جهش تابلو ⇒ «نوسانگیری با ریسک بالا»؛ بدون جهش ⇒ «تحت پایش/انتظار»', () => {
    const base = {
      fundamental: fundSig('bearish', 20, { metrics: { gross_margin: 12, growth_pct: -18 } }),
      technical: techSig('bullish', 70, ['breakout'], { weekly: { uptrend: true } }),
    };
    const withSurge = runStrictGates({ ...base, tape: tapeSig('suspicious_volume', 3.4) }, REGIME, { uptrend: true, belowMa52: false, rsi: 55 });
    expect(withSurge.fundamentalBlocked).toBe(true);
    expect(definiteDecision(withSurge).action).toBe('high_risk_swing');

    const noSurge = runStrictGates({ ...base, tape: tapeSig('suspicious_volume', 1.2) }, REGIME, { uptrend: true, belowMa52: false, rsi: 55 });
    expect(definiteDecision(noSurge).action).toBe('watch');
  });

  it('حاشیهٔ زیر ۲۰٪ یا افت فروش ⇒ گیت بنیاد مسدود (دلیل ریاضی)', () => {
    const res = runStrictGates(
      { fundamental: fundSig('bullish', 70, { metrics: { gross_margin: 18, growth_pct: 5 } }), technical: techSig('bullish', 70, ['breakout']) },
      REGIME,
      EMPTY_WEEKLY,
    );
    const g = res.gates.find((x) => x.id === 'fundamental')!;
    expect(g.state).toBe('blocked');
    expect(g.reason).toContain('۱۸.۰');
    expect(g.reason).toContain('۲۰');
  });

  it('نبود دادهٔ هفتگی ⇒ وتو صادر نمی‌شود و صادقانه pending می‌ماند', () => {
    const res = runStrictGates(
      { fundamental: fundSig('bullish', 85), technical: techSig('bullish', 70, ['breakout']) },
      REGIME,
      EMPTY_WEEKLY,
    );
    expect(res.weeklyHasData).toBe(false);
    expect(res.weeklyVeto).toBe(false);
    const techGate = res.gates.find((g) => g.id === 'technical')!;
    expect(techGate.reason).toContain('دادهٔ هفتگی');
    expect(definiteDecision(res).action).not.toBe('veto');
  });

  it('رژیم جنگی + وزن بالای نماد ⇒ گیت سبد مسدود و سقف ۱۰ تا ۲۰٪ گزارش می‌شود', () => {
    const res = runStrictGates(
      { fundamental: fundSig('bullish', 85), technical: techSig('bullish', 70, ['breakout']) },
      { ...REGIME, warRegime: true, symbolWeightPct: 15 },
      EMPTY_WEEKLY,
    );
    const g = res.gates.find((x) => x.id === 'portfolio')!;
    expect(g.state).toBe('blocked');
    expect(g.reason).toContain('۱۰٪');
  });

  it('weeklyTrendFromSignal در نبود فیلد هفتگی null می‌دهد', () => {
    const w = weeklyTrendFromSignal(techSig('bullish', 70, ['breakout']));
    expect(w).toEqual({
      uptrend: null,
      belowMa52: null,
      rsi: null,
      basis: null,
      reason: null,
      matrixDecision: null,
    });
    const w2 = weeklyTrendFromSignal(techSig('bullish', 70, ['breakout'], { weekly: { uptrend: true, belowMa52: true, rsi: 28 } }));
    expect(w2.uptrend).toBe(true);
    expect(w2.rsi).toBe(28);
  });
});

describe('خلاصهٔ تحلیلی مدیریتی (کاملاً آفلاین)', () => {
  const strict = runStrictGates(
    { fundamental: fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 45 } }), technical: techSig('bullish', 70, ['breakout']) },
    REGIME,
    { uptrend: true, belowMa52: true, rsi: 24 },
  );

  it('پنج بند قاعده‌محور با لحن مالی و بدون درخواست بیرونی', () => {
    const verdict = {
      symbol: 'شپنا',
      ts: NOW,
      compositeScore: 42,
      finalAction: 'buy' as const,
      contributions: [],
      dissent: [],
      usedSignalIds: ['a'],
      discardedSignalIds: [],
      hasConflict: false,
    };
    const lines = buildManagementSummary({
      symbol: 'شپنا',
      verdict,
      input: { fundamental: fundSig('bullish', 85), technical: techSig('bullish', 70, ['breakout']) },
      strict,
      decision: definiteDecision(strict),
      warRegime: true,
      superFundamental: true,
      industryCapPct: 20,
    });
    expect(lines.map((l) => l.id)).toEqual(['verdict', 'scenario', 'conflict', 'regime', 'switch', 'next']);
    expect(lines.find((l) => l.id === 'regime')!.text).toContain('۱۰٪');
    expect(lines.find((l) => l.id === 'regime')!.text).toContain('طلا/دلار');
    expect(lines.find((l) => l.id === 'switch')!.text).toContain('زیر MA52');
    expect(lines.find((l) => l.id === 'switch')!.tone).toBe('green');
  });

  it('برچسب لایه‌ها جای خط تیره را می‌گیرد', () => {
    expect(layerStatusLabel('technical', techSig('bullish', 60, ['trend'])).text).toBe('در انتظار شکست مقاومت');
    expect(layerStatusLabel('tape', tapeSig('suspicious_volume', 3)).text).toContain('حجم مشکوک ۳.۰ برابر');
    expect(layerStatusLabel('fundamental', { ...fundSig('bullish', 70), payload: { ...fundSig('bullish', 70).payload, margin_pct: 24 } } as AgentSignal).text).toContain('حاشیهٔ سود تایید');
    expect(layerStatusLabel('portfolio', undefined).text).toContain('منتشر نشده');
  });

  it('خروج ۵۰٪ فقط با تایید بنیادی و ستاپ فعال می‌شود', () => {
    expect(halfExitPlan({ resistance: 36000, setupActive: true, fundamentalOk: true, currentPrice: 36500 }).active).toBe(true);
    expect(halfExitPlan({ resistance: null, setupActive: true, fundamentalOk: true, currentPrice: 36500 }).active).toBe(false);
    expect(halfExitPlan({ resistance: 36000, setupActive: false, fundamentalOk: true, currentPrice: 36500 }).active).toBe(false);
  });
});

describe('ماشین‌حساب برنامهٔ معاملاتی و DCA', () => {
  const base = {
    baseStepWeightPct: 5,
    industryCapPct: 20,
    industryUsedPct: 3,
    step1: { lo: 33500, hi: 34200 },
    step2: { lo: 31000, hi: 31800 },
    breakout: { lo: 36030 },
    priceActionStop: 27987,
    resistance: 42000,
    currentPrice: 40840,
    warCapPct: null,
  };

  it('با سرمایهٔ ۱۰۰ میلیونی، مبلغ و تعداد برگه از وزن مؤثر (سقف صنعت) ساخته می‌شود', () => {
    const r = buildTradeBlueprint({ ...base, capitalToman: 100_000_000 });
    expect(r.hasCapital).toBe(true);
    expect(r.industryRemainingPct).toBe(17);
    // وزن مؤثر = min(5, 17) = 5
    expect(r.effectiveStepWeightPct).toBe(5);
    const s1 = r.steps.find((s) => s.key === 'step1')!;
    expect(s1.refPrice).toBe(33850);
    expect(s1.amountToman).toBe(5_000_000);
    expect(s1.shares).toBe(Math.floor(5_000_000 / 33850));
    expect(r.rr).not.toBeNull();
  });

  it('نبود سرمایه ⇒ مبلغ/برگه null (بدون عدد ساختگی) و یادداشت صادقانه', () => {
    const r = buildTradeBlueprint({ ...base, capitalToman: null });
    expect(r.hasCapital).toBe(false);
    expect(r.steps.every((s) => s.amountToman === null && s.shares === null)).toBe(true);
    expect(r.notes.join(' ')).toContain('سرمایهٔ کل ثبت نشده');
  });

  it('ظرفیت صفر صنعت وزن پله را صفر می‌کند و رژیم جنگی سقف را پایین می‌آورد', () => {
    const full = buildTradeBlueprint({ ...base, capitalToman: 100_000_000, industryUsedPct: 20 });
    expect(full.industryRemainingPct).toBe(0);
    expect(full.effectiveStepWeightPct).toBe(0);
    expect(full.steps[0].amountToman).toBeNull();

    const war = buildTradeBlueprint({ ...base, capitalToman: 100_000_000, warCapPct: 20 });
    expect(war.effectiveStepWeightPct).toBe(5);
  });
});

describe('سوییچ اهرم ساعت شنی', () => {
  it('سوپر‌بنیادی + زیر MA52 و RSI≤۳۰ ⇒ روشن با حجم ۲ تا ۴ برابر', () => {
    const sw = hourglassSwitch({ superFundamental: true, weekly: { uptrend: false, belowMa52: true, rsi: 20 }, fundScore: 5 });
    expect(sw.active).toBe(true);
    expect(sw.volumeMultiple).toBeGreaterThanOrEqual(2);
    expect(sw.volumeMultiple).toBeLessThanOrEqual(4);
  });

  it('نبود دادهٔ هفتگی ⇒ خاموش با دلیل صادقانه', () => {
    const sw = hourglassSwitch({ superFundamental: true, weekly: EMPTY_WEEKLY, fundScore: 5 });
    expect(sw.active).toBe(false);
    expect(sw.reason).toContain('منتشر نشده');
  });

  it('سوپر‌بنیادی فقط با تایید هر ۵ شاخص FTS (۵ از ۵) و جهت صعودی', () => {
    // نمرهٔ بنیادی ۰ تا ۵ از payload.score خوانده می‌شود، نه نمرهٔ ۰ تا ۱۰۰٬ اعتماد ترکیبی
    expect(isSuperFundamental(fundSig('bullish', 85, { score: 5 }))).toBe(true);
    expect(isSuperFundamental(fundSig('bullish', 95, { score: 4 }))).toBe(false);
    expect(isSuperFundamental(fundSig('bearish', 95, { score: 5 }))).toBe(false);
    // صندوق حتی با ۵ از ۵ هم سوپربنیادی نیست: داوری FTS برایش صادر نشده (رأی ۱۵)
    expect(isSuperFundamental(fundSig('bullish', 85, { score: 5, applicable: false }))).toBe(false);
    expect(isSuperFundamental(undefined)).toBe(false);
  });
});

describe('صحنهٔ کامل تب ایجنت ارشد', () => {
  it('استپر چهار گیتی، حکم قطعی، خلاصهٔ مدیریتی و ماشین‌حساب رندر می‌شوند', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 45 } }));
    useSignalStore.getState().publishSignal(techSig('bullish', 70, ['breakout']));
    renderMaster();

    expect(await screen.findByText('برآیند مستر برای شپنا')).toBeInTheDocument();
    // استپر ۴ فیلتر
    expect(screen.getByText('فیلتر ۱: بنیاد')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۲: تکنیکال')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۳: تابلو')).toBeInTheDocument();
    expect(screen.getByText('فیلتر ۴: سبد و ریسک')).toBeInTheDocument();
    // حکم قطعی + خلاصهٔ آفلاین
    expect(screen.getByLabelText('حکم نهایی سخت‌گیرانه')).toBeInTheDocument();
    expect(screen.getByLabelText('خلاصهٔ تحلیلی مدیریتی')).toBeInTheDocument();
    // ماشین‌حساب DCA + سرمایهٔ ثبت‌نشده
    expect(await screen.findByText('ماشین‌حساب برنامهٔ معاملاتی و DCA')).toBeInTheDocument();
    expect(screen.getByLabelText('سرمایهٔ کل (تومان)')).toBeInTheDocument();
    expect(screen.getAllByText(/بدون داده/).length).toBeGreaterThan(0);
    // اکشن‌ها
    expect(screen.getByRole('button', { name: 'ثبت پله در سبد' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'افزودن به واچ‌لیست تحت نظر' })).toBeInTheDocument();
    // جدول داوری بدون خط تیره: برچسب لایه
    expect(screen.getByText('برچسب لایه')).toBeInTheDocument();
    useSignalStore.getState().clearSignals();
  }, 15000);

  it('«ثبت پله در سبد» تصمیم accept را با وزن مؤثر POST می‌کند', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 45 } }));
    useSignalStore.getState().publishSignal(techSig('bullish', 70, ['breakout']));
    useCapitalStore.getState().setTotalToman(100_000_000);
    renderMaster();
    await screen.findByText('ماشین‌حساب برنامهٔ معاملاتی و DCA');
    fireEvent.click(screen.getByRole('button', { name: 'ثبت پله در سبد' }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([u, o]) => String(u) === '/api/selection/decision' && (o as { method?: string } | undefined)?.method === 'POST',
      );
      expect(post).toBeDefined();
      const body = JSON.parse((post![1] as { body: string }).body);
      expect(body.symbol).toBe('شپنا');
      expect(body.status).toBe('accept');
      expect(typeof body.weight_pct).toBe('number');
    });
    // پس از ثبت، به تب پرتفوی منتقل می‌شود
    expect(await screen.findByText('صفحه پرتفوی')).toBeInTheDocument();
    useSignalStore.getState().clearSignals();
  });

  it('هیچ سیگنالی ⇒ حالت خالی تمیز می‌ماند', async () => {
    renderMaster();
    expect(await screen.findByText('هنوز سیگنالی در باس نیست')).toBeInTheDocument();
  });

  it('در وضعیت وتو (فیلتر ۲): گیج نمره «وتو / فاقد تایید» و بج «ورود ممنوع (توقف در فیلتر دوم)» نشان می‌دهد', async () => {
    useSignalStore.getState().publishSignal(fundSig('bullish', 85, { metrics: { gross_margin: 26, growth_pct: 45 } }));
    // تکنیکال بدون ستاپ شکست و منفی ⇒ وتو در فیلتر ۲
    useSignalStore.getState().publishSignal(techSig('neutral', 40, []));
    renderMaster();

    expect(await screen.findByText('برآیند مستر برای شپنا')).toBeInTheDocument();
    // در وضعیت وتو، برچسب صریح داخل گیج و بج قرمز رندر می‌شوند:
    expect(screen.getByText('وتو / فاقد تایید')).toBeInTheDocument();
    expect(screen.getByText('ورود ممنوع (توقف در فیلتر دوم)')).toBeInTheDocument();
    expect(screen.queryByText('خرید قوی')).toBeNull();
    useSignalStore.getState().clearSignals();
  });

  it('محاسبه R/R در غیاب مقاومت تاریخی: بر مبنای تارگت ستاپ جت (+۲۰٪) محاسبه شده و ۰.۰ نیست', () => {
    const r = buildTradeBlueprint({
      capitalToman: 100_000_000,
      assumedCapital: false,
      baseStepWeightPct: 5,
      industryCapPct: 20,
      industryUsedPct: 2,
      step1: { lo: 10000, hi: null },
      step2: null,
      breakout: null,
      priceActionStop: 9500, // حد ضرر ۵٪
      resistance: null, // بدون مقاومت تاریخی
      currentPrice: 10000,
      warCapPct: null,
    });
    // تارگت ستاپ جت = ۱۲۰۰۰ (+۲۰٪)
    // ریسک = ۵۰۰ ریال (-۵٪) -> پاداش = ۲۰۰۰ ریال -> R/R = 4.0
    expect(r.rr).toBe(4);
    expect(r.notes.some((n) => n.includes('ستاپ جت (+۲۰٪)'))).toBe(true);
  });
});
