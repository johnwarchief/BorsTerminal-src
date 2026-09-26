// تست مرکز فرماندهی نبض بازار: گرید ۴بخشی با fetch ماک‌شده
// سنجه‌های پوشش‌داده‌شده: دماسنج همت (۲۰/۱۰) و «بدون‌دادهٔ روند»، بولد‌سبزِ خروج
// درآمد ثابت، برچسب طلایی Alpha Trio، رنگ‌بندی سرانه (۱.۵×/۰.۸×)، هشدار ۸۰٪
// پهنای باند، شمارش/ارزش صف‌ها و Circuit Breaker در اندپوینت مرده.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketPulseBar } from '@features/market/components/MarketPulseBar';
import {
  computeAlphaTrio,
  hematState,
  powerTone,
  pulseGoldFlowB,
  pulseHemat,
  useMarketPulse,
  type DepthFeed,
  type MarketPulseData,
  type SmartMoney,
  type SummaryFeed,
  type Thermometer,
} from '@features/market/api/useMarketPulse';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function smartMoney(hemat = 22.5, eqFlow = 300.5, fixedFlow = -120.2, allMarket: number | null = 172.2): SmartMoney {
  return {
    status: 'ok',
    macro: {
      value_hemat: hemat,
      good_min: 20,
      bad_max: 10,
      ...(allMarket != null ? { trade_value_all_market_hemat: allMarket } : {}),
      market_value_hemat: 24856.7,
      market_value_source: 'tse_market_overview',
    },
    watch_entry: { active: false, bearish_pct: 29.9, rule_pct: 80, bearish: 341, known: 1142 },
    flow: {
      eq_flow_b_toman: eqFlow,
      fixed_flow_b_toman: fixedFlow,
      eq_inflow: eqFlow > 0,
      fixed_outflow: fixedFlow < 0,
      ideal_fts: false,
    },
  };
}

function summary(hemat = 22.5, opts: { pcBuy?: number; pcSell?: number; power?: number; goldFlow?: number | null } = {}): SummaryFeed {
  const rows: NonNullable<SummaryFeed['rows']> = [
    { key: 'all', label: 'کل بازار' },
    {
      key: 'eq_all',
      label: 'سهام، حق تقدم و ص.سهامی',
      pc_buy_m_toman: opts.pcBuy ?? 84.1,
      pc_sell_m_toman: opts.pcSell ?? 71.7,
      buy_power: opts.power ?? 1.17,
      buy_power_up: true,
    },
  ];
  if (opts.goldFlow != null) {
    rows.push({ key: 'gold_fund', label: 'صندوق طلا', money_flow_b_toman: opts.goldFlow });
  }
  return { status: 'ok', rows, health: { value_hemat: hemat } };
}

function depth(): DepthFeed {
  return {
    status: 'ok',
    depth_available: true,
    symbols_with_depth: 3529,
    buy_queue_b_toman: 66280,
    sell_queue_b_toman: 12244,
    ratio: 5.4,
    buy_queue_count: 1471,
    sell_queue_count: 286,
  };
}

function thermo(overrides: Partial<Thermometer> = {}): Thermometer {
  return {
    status: 'ok',
    positive: 1504,
    negative: 462,
    zero: 164,
    positive_pct: 70.6,
    negative_pct: 21.7,
    entry_rule_pct: 80,
    ...overrides,
  };
}

function jsonResponse(body: unknown): Response {
  return { ok: true, json: () => Promise.resolve(body) } as unknown as Response;
}

function deadResponse(): Response {
  return { ok: false, status: 404, json: () => Promise.resolve({}) } as unknown as Response;
}

function mockRoutes(routes: Record<string, () => Response>) {
  fetchMock.mockImplementation((url: string) => {
    for (const [key, make] of Object.entries(routes)) {
      if (url.includes(key)) return Promise.resolve(make());
    }
    return Promise.resolve(deadResponse());
  });
}

function PulseLive() {
  const { data, isLoading } = useMarketPulse();
  return <MarketPulseBar pulse={data ?? null} isLoading={isLoading} />;
}

function renderPulse() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <PulseLive />
    </QueryClientProvider>,
  );
}

const emptyPulse: MarketPulseData = { smartMoney: null, summary: null, depth: null, thermometer: null };

describe('مدل‌های محلی مرکز فرماندهی', () => {
  it('دماسنج همت: ≥۲۰ سبز / ≤۱۰ قرمز / میانه کهربایی؛ داده ناقص null', () => {
    expect(hematState(20)).toBe('good');
    expect(hematState(19.9)).toBe('mid');
    expect(hematState(10)).toBe('bad');
    expect(hematState(9.4)).toBe('bad');
    expect(hematState(null)).toBeNull();
    expect(hematState(Number.NaN)).toBeNull();
  });

  it('رنگ‌بندی P/S: ≥۱.۵× سبز، <۰.۸× قرمز، میانه کهربایی', () => {
    expect(powerTone(1.5)).toBe('good');
    expect(powerTone(2.2)).toBe('good');
    expect(powerTone(0.79)).toBe('bad');
    expect(powerTone(1.1)).toBe('mid');
    expect(powerTone(null)).toBeNull();
    expect(powerTone(Number.NaN)).toBeNull();
  });

  it('جریان طلا از ردیف gold_fund؛ نبود ردیف = null', () => {
    expect(pulseGoldFlowB({ ...emptyPulse, summary: summary(20, { goldFlow: -955 }) })).toBe(-955);
    expect(pulseGoldFlowB({ ...emptyPulse, summary: summary(20, { goldFlow: null }) })).toBeNull();
    expect(pulseGoldFlowB(emptyPulse)).toBeNull();
  });

  it('Alpha Trio: خروج درآمد ثابت + ورود سهام + خروج طلا (طلا فقط اگر داده باشد)', () => {
    const withGoldOut: MarketPulseData = {
      ...emptyPulse,
      smartMoney: smartMoney(22.5, 300, -120),
      summary: summary(22.5, { goldFlow: -50 }),
    };
    expect(computeAlphaTrio(withGoldOut)?.active).toBe(true);
    const goldIn: MarketPulseData = { ...withGoldOut, summary: summary(22.5, { goldFlow: 50 }) };
    expect(computeAlphaTrio(goldIn)?.active).toBe(false);
    const noGold: MarketPulseData = { ...withGoldOut, summary: summary(22.5, { goldFlow: null }) };
    expect(computeAlphaTrio(noGold)?.active).toBe(true);
    expect(computeAlphaTrio(noGold)?.goldOutflow).toBeNull();
    const eqOut: MarketPulseData = { ...withGoldOut, smartMoney: smartMoney(22.5, -300, -120) };
    expect(computeAlphaTrio(eqOut)?.active).toBe(false);
    expect(computeAlphaTrio(emptyPulse)).toBeNull();
  });

  it('«nodata» حالتِ چهارمِ داوری است، نه صفر و نه نامساعد', () => {
    const nodata = {
      status: 'ok',
      rows: [],
      health: { value_hemat: null, state: 'nodata' as const, label: 'بدون داده' },
    };
    expect(pulseHemat({ ...emptyPulse, summary: nodata })?.state).toBe('nodata');
    expect(pulseHemat({ ...emptyPulse, summary: nodata })?.label).toBe('بدون داده');
  });

  it('همت از health خلاصه هم تغذیه می‌شود؛ نبود هر دو null', () => {
    expect(pulseHemat({ ...emptyPulse, summary: summary(9) })?.state).toBe('bad');
    expect(pulseHemat(emptyPulse)).toBeNull();
  });
});

describe('گرید ۴بخشی با fetch ماک‌شده', () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it('چهار بخش با داده کامل: همت، مثلث جریان، تراز صف‌ها و سرانه', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary(22.5, { goldFlow: -955 })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-hemat').textContent).toContain('۲۲.۵'));
    expect(screen.getByTestId('pulse-hemat').textContent).toContain('مساعد');
    expect(screen.getByTestId('pulse-hemat').textContent).toContain('روند ۳-۴ روزه: بدون داده');
    expect(screen.getByTestId('pulse-smart').textContent).toContain('۳۰۰.۵');
    expect(screen.getByTestId('pulse-queues').textContent).toContain('۱۴۷۱');
    expect(screen.getByTestId('pulse-percapita').textContent).toContain('۱.۲×');
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('mstat/thermometer'))).toBe(true);
  });

  it('همتِ «بدون داده»: پاسخ را اسکیما نمی‌شکند و پنل داوری نمی‌سازد', async () => {
    // نشستِ باز نشده: ماکرو مقدار ندارد و state=nodata می‌فرستد. اگر این رشته
    // در اسکیما نبود کل پاسخ دور ریخته می‌شد و جریان پول هم غیب می‌شد.
    mockRoutes({
      'mstat/smart-money': () =>
        jsonResponse({
          status: 'ok',
          macro: { value_hemat: null, state: 'nodata', label: 'بدون داده', market_value_hemat: null },
          watch_entry: { active: false, bearish_pct: 0, rule_pct: 80, bearish: 0, known: 0 },
          flow: { eq_flow_b_toman: 300.5, fixed_flow_b_toman: -120.2, eq_inflow: true, fixed_outflow: true },
        }),
      'mstat/summary': () =>
        jsonResponse({ status: 'ok', rows: [], health: { value_hemat: null, state: 'nodata', label: 'بدون داده' } }),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-smart').textContent).toContain('۳۰۰.۵'));
    expect(screen.getByTestId('pulse-hemat').textContent).toContain('بدون داده');
    expect(screen.getByTestId('pulse-hemat').textContent).not.toContain('نامساعد');
  });

  it('خروج درآمد ثابت: عدد منفی با رنگ سبز بولد', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300.5, -120.2)),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByText('▼ ۱۲۰.۲ ب.ت خروج')).toBeInTheDocument());
    expect(screen.getByText('▼ ۱۲۰.۲ ب.ت خروج').className).toContain('text-accent-green');
  });

  it('برچسب طلایی Alpha Trio فقط در ترکیب کامل فعال می‌شود', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300, -120)),
      'mstat/summary': () => jsonResponse(summary(22.5, { goldFlow: -50 })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-alpha-trio')).toBeInTheDocument());
    expect(screen.getByTestId('pulse-alpha-trio').textContent).toContain('ایده‌آل‌ترین شرایط ورود نوسانی');
  });

  it('رنگ‌بندی سرانه: ۱.۵× سبز', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary(22.5, { power: 1.5 })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByText('۱.۵×')).toBeInTheDocument());
    expect(screen.getByText('۱.۵×').className).toContain('text-accent-green');
  });

  it('رنگ‌بندی سرانه: ۰.۷۵× قرمز', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary(22.5, { power: 0.75 })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByText('۰.۸×')).toBeInTheDocument());
    expect(screen.getByText('۰.۸×').className).toContain('text-accent-red');
  });

  it('هشدار عبور منفی از ۸۰٪ پهنای باند', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo({ negative_pct: 83.5 })),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-breadth-warn')).toBeInTheDocument());
    expect(screen.getByTestId('pulse-breadth-warn').textContent).toContain('۸۰٪');
  });

  it('طلا بدون داده → برچسب «تا ۱۲:۳۰»', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary(22.5, { goldFlow: null })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByText('تا ۱۲:۳۰')).toBeInTheDocument());
  });

  it('کارت ارزش کل بازار عددِ رسمی را می‌برد و گردشِ روز تیترِ خودش را دارد', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300.5, -120.2, 172.2)),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    // دو عدد هرگز یکی نمی‌شوند: ۲۴٬۸۵۶.۷ همت ارزشِ بازار است، ۱۷۲.۲ همت گردشِ روز.
    await waitFor(() => expect(screen.getByTestId('pulse-market-cap').textContent).toContain('۲۴۸۵۶.۷'));
    expect(screen.getByTestId('pulse-market-cap').textContent).toContain('ارزش کل بازار');
    expect(screen.getByTestId('pulse-market-cap').textContent).not.toContain('۱۷۲.۲');
    expect(screen.getByTestId('pulse-trade-value').textContent).toContain('گردش امروزِ کل بازار');
    expect(screen.getByTestId('pulse-trade-value').textContent).toContain('۱۷۲.۲');
  });

  it('ارزش کل بازار غایب → «بدون داده» در همان بلوک، نه صفر', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300.5, -120.2, null)),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-market-cap')).toBeInTheDocument());
    expect(screen.getByTestId('pulse-market-cap').textContent).toContain('بدون داده');
  });

  it('Circuit Breaker: اندپوینت مرده فقط بخش خودش «بدون داده» می‌شود', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-smart').textContent).toContain('۳۰۰.۵'));
    expect(screen.getByTestId('pulse-queues').textContent).toContain('بدون داده');
    expect(screen.getByTestId('pulse-hemat').textContent).toContain('مساعد');
  });

  it('همهٔ اندپوینت‌ها خراب → همهٔ بخش‌ها بدون داده، بدون کرش', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(deadResponse()));
    renderPulse();
    await waitFor(() => expect(screen.getAllByText(/بدون داده/).length).toBeGreaterThanOrEqual(5));
  });
});
