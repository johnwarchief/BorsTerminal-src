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
  pulseIndex,
  useMarketPulse,
  type DepthFeed,
  type MarketPulseData,
  type SmartMoney,
  type SummaryFeed,
  type Thermometer,
} from '@features/market/api/useMarketPulse';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function smartMoney(hemat = 22.5, eqFlow = 300.5, fixedFlow = -120.2, allMarket: number | null = 172.2,
  index: Record<string, number | null> | null = null,
  extra: { goldFlow?: number | null; bearishPct?: number | null } = {}): SmartMoney {
  const bear = extra.bearishPct ?? 29.9;
  const gold = extra.goldFlow;
  const ideal = eqFlow > 0 && fixedFlow < 0;
  // حکمِ ساختگی از همان اعدادِ fixture — همان کاری که موتور روی دادهٔ واقعی
  // می‌کند. متن‌ها از payload می‌آیند، پس این‌جا «کارِ بک‌اند» تقلید می‌شود نه
  // محاسبهٔ دوباره در لایهٔ نمایش.
  const liqGood = hemat != null && hemat >= 20;
  return {
    status: 'ok',
    macro: {
      value_hemat: hemat,
      good_min: 20,
      bad_max: 10,
      state: hemat == null ? 'nodata' : liqGood ? 'good' : hemat <= 10 ? 'bad' : 'mid',
      label: hemat == null ? 'بدون داده' : liqGood ? 'مساعد' : 'متوسط',
      ...(allMarket != null ? { trade_value_all_market_hemat: allMarket } : {}),
      market_value_hemat: 24856.7,
      market_value_source: 'tse_market_overview',
      ...(index ? { index } : {}),
    },
    watch_entry: { active: bear >= 80, bearish_pct: bear, rule_pct: 80, bearish: 341, known: 1142 },
    flow: {
      eq_flow_b_toman: eqFlow,
      fixed_flow_b_toman: fixedFlow,
      eq_inflow: eqFlow > 0,
      fixed_outflow: fixedFlow < 0,
      ideal_fts: ideal,
      ...(gold != null ? { gold_flow_b_toman: gold, gold_outflow: gold < 0 } : {}),
      trio_fts: ideal && (gold == null || gold < 0),
    },
    verdict: {
      status: 'ok',
      verdict: liqGood && ideal ? 'go' : 'wait',
      label: liqGood && ideal ? 'روزِ ورود است' : 'صبر — نشانه‌ها مخالف‌اند',
      reason:
        liqGood && ideal
          ? 'نقدینگی: مساعد · پولِ حقیقی: حالتِ آرمانی'
          : 'موافقِ ورود — نقدینگی: مساعد · مخالفِ ورود — پولِ حقیقی: خروجِ پول از سهام',
      basis: 'fts_notes_p13_p14',
      gates: [
        {
          key: 'liquidity',
          label: 'گردشِ پولِ امروز',
          short: 'نقدینگی',
          state: liqGood ? 'ok' : 'bad',
          label_state: liqGood ? 'مساعد' : 'نامساعد',
          vote: liqGood ? 1 : -1,
          detail: '۲۲.۵ همت',
          rule: 'بالایِ ۲۰ خوب · بالایِ ۵۰ عالی · زیرِ ۱۰ نامساعد (جزوه ص۱۳)',
          why: 'سبز یعنی گردشِ پولِ امروزِ سهام و حق تقدم از کفِ جزوه بالاتر رفته است.',
        },
        {
          key: 'continuity',
          label: 'تداومِ سه نشستِ اخیر',
          short: 'تداوم',
          state: 'nodata',
          label_state: 'بدون داده',
          vote: 0,
          detail: 'تاریخچه کامل نیست — ۱ نشست از ۳',
          rule: 'همان جهتِ نقدینگی در ۳ تا ۴ نشستِ پیاپی (جزوه ص۱۳)',
          why: 'بی‌رنگ یعنی تاریخچۀ سه نشستِ اخیر کامل نشده.',
        },
        {
          key: 'breadth',
          label: 'درصدِ نمادهایِ نزولی',
          short: 'پهنایِ بازار',
          state: bear >= 80 ? 'ok' : 'mid',
          label_state: bear >= 80 ? 'فرصتِ ورود' : 'بدونِ فرصتِ کف',
          vote: bear >= 80 ? 1 : 0,
          detail: '٪۸۸ منفی',
          rule: '۸۰٪ منفی = بازار فرصتِ ورود دارد، نه هشدار (جزوه ص۱۳)',
          why: 'زرد یعنی درصدِ نمادهایِ نزولی از آستانۀ ۸۰٪ پایین‌تر بوده؛ پس نشانه‌ای برای ورود نیست.',
        },
        {
          key: 'flow',
          label: 'جهتِ پولِ حقیقی',
          short: 'پولِ حقیقی',
          state: ideal ? 'ok' : 'bad',
          label_state: ideal ? 'حالتِ آرمانی' : 'خروجِ پول از سهام',
          vote: ideal ? 1 : -1,
          rule: 'خروجِ طلا و درآمد ثابت ⇄ ورودِ سهام و حق تقدم (جزوه ص۱۴)',
          why: 'سبز یعنی پولِ حقیقی هم‌زمان از درآمد ثابت و طلا بیرون آمده و به سهام وارد شده است.',
        },
        {
          key: 'window',
          label: 'پنجرهٔ زمانیِ جزوه',
          short: 'ساعت',
          state: 'mid',
          label_state: 'خارجِ پنجره‌ها',
          vote: 0,
          detail: 'ساعتِ داده ۱۲:۵۹',
          rule: 'درآمد ثابت در نیم‌ساعتِ اول · شفافیتِ طلا ۱۲:۱۵–۱۲:۳۰ (جزوه ص۱۴)',
          why: 'زرد یعنی بیرونِ پنجره‌هایِ جزوه‌ایم؛ این شرط رأیی در حکم ندارد.',
        },
      ],
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
    // چهار گروهِ واقعیِ خلاصه (اعدادِ نشستِ ۱۴۰۵/۰۷/۰۴) — کارت سرانه این‌ها را
    // ردیف‌به‌ردیف نشان می‌دهد، پس fixture هم باید آن‌ها را داشته باشد.
    { key: 'stock_right', label: 'سهام و حق تقدم', pc_buy_m_toman: 61, pc_sell_m_toman: 37.1, buy_power: 1.64 },
    { key: 'eq_fund', label: 'صندوق‌های سهامی و مختلط', pc_buy_m_toman: 75.8, pc_sell_m_toman: 163.8, buy_power: 0.46 },
    { key: 'fixed_fund', label: 'صندوق درآمد ثابت', pc_buy_m_toman: 177.7, pc_sell_m_toman: 221.3, buy_power: 0.86 },
    {
      key: 'gold_fund',
      label: 'صندوق‌های طلا',
      pc_buy_m_toman: 60.3,
      pc_sell_m_toman: 240.1,
      buy_power: 0.25,
      ...(opts.goldFlow != null ? { money_flow_b_toman: opts.goldFlow } : {}),
    },
  ];
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

  it('Alpha Trio: سه شرط و ترکیبشان را موتور می‌بندد؛ نمایش فقط می‌خواند', () => {
    // gold_outflow/null سه‌مقدار از payload می‌آید (نبودِ دادهٔ طلا = لغوِ الزام).
    const withGoldOut: MarketPulseData = {
      ...emptyPulse,
      smartMoney: smartMoney(22.5, 300, -120, null, null, { goldFlow: -50 }),
      summary: summary(22.5, { goldFlow: -50 }),
    };
    expect(computeAlphaTrio(withGoldOut)?.active).toBe(true);
    expect(computeAlphaTrio(withGoldOut)?.goldOutflow).toBe(true);
    const goldIn: MarketPulseData = {
      ...withGoldOut,
      smartMoney: smartMoney(22.5, 300, -120, null, null, { goldFlow: 50 }),
    };
    expect(computeAlphaTrio(goldIn)?.active).toBe(false);
    expect(computeAlphaTrio(goldIn)?.goldOutflow).toBe(false);
    const noGold: MarketPulseData = { ...withGoldOut, smartMoney: smartMoney(22.5, 300, -120) };
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
    // آستانه‌های واقعیِ payload — جای خطِ «روند ۳-۴ روزه: بدون داده» را گرفت
    // که در هر دو شاخه یکی بود و هیچ‌وقت راست نمی‌شد.
    expect(screen.getByTestId('pulse-hemat').textContent).toContain('مساعد از ۲۰.۰ همت');
    expect(screen.getByTestId('pulse-smart').textContent).toContain('۳۰۰.۵');
    expect(screen.getByTestId('pulse-queues').textContent).toContain('۱۴۷۱');
    expect(screen.getByTestId('pulse-percapita').textContent).toContain('۱.۲×');
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('mstat/thermometer'))).toBe(true);
  });

  it('سه شرطِ چیپِ آلفا تک‌تک نشان داده می‌شوند (طلا بدون داده = ؟، نه ✗)', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300, -120)),
      'mstat/summary': () => jsonResponse(summary(22.5, { goldFlow: null })),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-alpha-conditions')).toBeTruthy());
    const t = screen.getByTestId('pulse-alpha-conditions').textContent ?? '';
    expect(t).toContain('ورود سهام');
    expect(t).toContain('خروج درآمد ثابت');
    expect(t).toContain('خروج طلا');
    expect(t).toContain('؟');
  });

  it('قدرت خریدار به تفکیکِ گروه: ردیف‌های واقعیِ خلاصه، رنگ از آستانهٔ ۱.۵/۰.۸', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-groups')).toBeTruthy());
    const t = screen.getByTestId('pulse-groups').textContent ?? '';
    // صندوق درآمد ثابت: ۰.۸۶ → زیر ۰.۸ نیست، پس کهربایی؛ عدد را همان‌طور
    // که دماسنج نشان می‌دهد بخوان (یک رقمِ ممیز).
    expect(t).toContain('صندوق درآمد ثابت');
    expect(t).toContain('۰.۹×');
    expect(t).toContain('صندوق‌های طلا');
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

  it('۸۰٪ منفی «فرصتِ ورود» است نه هشدار — و داورش payload است نه نمایش', async () => {
    mockRoutes({
      // thermometer خودش ۸۳.۵٪ منفی می‌گوید؛ اگر نمایش داوری می‌کرد این چیپ
      // بی‌نیاز از payload روشن می‌شد. اینجا smart-money عمداً active=false را
      // می‌فرستد تا ثابت شود چیپ فقط از رأیِ موتور باز می‌شود.
      'mstat/smart-money': () => jsonResponse(smartMoney(22.5, 300.5, -120.2, null, null, { bearishPct: 83.5 })),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo({ negative_pct: 83.5 })),
    });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-breadth-warn')).toBeInTheDocument());
    const chip = screen.getByTestId('pulse-breadth-warn');
    expect(chip.textContent).toContain('۸۰٪');
    expect(chip.textContent).toContain('فرصتِ ورود');
    expect(chip.className).toContain('text-accent-green');
    expect(chip.textContent).not.toContain('⚠');
  });

  it('زیرِ آستانه هیچ «فرصت» یا «هشدار»ی نقاشی نمی‌شود', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo({ negative_pct: 83.5 })),
    });
    renderPulse();
    // عددِ دماسنج ۸۳.۵٪ است ولی رأیِ موتور active=false -- نمایش مقایسه نمی‌کند.
    await waitFor(() => expect(screen.getByTestId('pulse-queues')).toBeInTheDocument());
    expect(screen.queryByTestId('pulse-breadth-warn')).not.toBeInTheDocument();
  });

  it('حکمِ امروز: تیتر، علت و پنج درِ جزوه از payload نمایش داده می‌شود', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse(smartMoney()),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    await waitFor(() =>
      expect(screen.getByTestId('pulse-verdict-label').textContent).toContain('روزِ ورود است'),
    );
    expect(screen.getByTestId('pulse-verdict-reason').textContent).toContain('حالتِ آرمانی');
    for (const k of ['liquidity', 'continuity', 'breadth', 'flow', 'window']) {
      expect(screen.getByTestId(`pulse-verdict-gate-${k}`)).toBeInTheDocument();
    }
    // هر شرط یک سطرِ مستقل است (#170) و یک جملهٔ «رنگش یعنی چی» دارد
    const list = screen.getByTestId('pulse-verdict-gate-flow').parentElement;
    expect(list?.tagName).toBe('UL');
    expect(list?.children).toHaveLength(5);
    for (const k of ['liquidity', 'continuity', 'breadth', 'flow', 'window']) {
      expect(screen.getByTestId(`pulse-verdict-why-${k}`).textContent).toBeTruthy();
    }
    // هیچ‌جا شمارهٔ «قدم» نمی‌ماند — ترتیبی در داوری نیست
    expect(screen.getByTestId('pulse-verdict').textContent).not.toContain('قدمِ');
    const flow = screen.getByTestId('pulse-verdict-gate-flow');
    expect(flow.textContent).toContain('جهتِ پولِ حقیقی');
    expect(flow.getAttribute('title')).toContain('حالتِ آرمانی');
    // درِ بی‌داده با رنگِ داوری‌شده نمی‌نشیند
    const cont = screen.getByTestId('pulse-verdict-gate-continuity');
    expect(cont.getAttribute('title')).toContain('بدون داده');
    expect(cont.textContent).toContain('؟');
    expect(screen.getByTestId('pulse-verdict-mark-continuity').className).toContain('text-text-muted');
    // دو شاخص روی هم در ستونِ راست و حکم کنارشان
    const idx = screen.getByTestId('pulse-index');
    expect(idx.className).toContain('flex-col');
    expect(idx.parentElement).toBe(screen.getByTestId('pulse-verdict').parentElement);
  });

  it('حکم نرسیده (اندپوینتِ پولِ هوشمند مرد) → «بدون داده»، نه «وارد نشو»', async () => {
    mockRoutes({
      'mstat/smart-money': () => jsonResponse({ status: 'error', message: 'x' }),
      'mstat/summary': () => jsonResponse(summary()),
      'mstat/depth': () => jsonResponse(depth()),
      'mstat/thermometer': () => jsonResponse(thermo()),
    });
    renderPulse();
    // کارتِ همت می‌آید (اسکیما رد نشد) ولی حکمی نیست: «بدون داده» و بی‌رنگ.
    await waitFor(() => expect(screen.getByTestId('pulse-smart')).toBeInTheDocument());
    expect(screen.getByTestId('pulse-verdict-label').textContent).toContain('بدون داده');
    expect(screen.getByTestId('pulse-verdict').className).not.toContain('text-accent-red');
    expect(screen.queryAllByTestId(/^pulse-verdict-gate-/)).toHaveLength(0);
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

describe('نوارِ شاخص کل و هموزن', () => {
  it('pulseIndex فقط عددِ خام را رد می‌کند؛ شاخصِ غایب null است', () => {
    expect(pulseIndex(null)).toBeNull();
    expect(pulseIndex({ smartMoney: smartMoney(), summary: null, depth: null, thermometer: null })).toBeNull();
    const withIx: MarketPulseData = {
      smartMoney: smartMoney(22.5, 300.5, -120.2, 172.2, {
        d_even: 20260926, last: 7153088.29, change: -103955.13, pct: -1.43,
        ew_last: 1929823.43, ew_change: -9196.9, ew_pct: -0.48,
      }),
      summary: null, depth: null, thermometer: null,
    };
    expect(pulseIndex(withIx)).toMatchObject({ last: 7153088.29, pct: -1.43, ewLast: 1929823.43 });
  });

  it('دو عددِ رسمی با رقمِ فارسی و علامتِ درصد نمایش داده می‌شوند', async () => {
    mockRoutes({
      'mstat/smart-money': () =>
        jsonResponse(smartMoney(22.5, 300.5, -120.2, 172.2, {
          d_even: 20260926, last: 7153088.29, change: -103955.13, pct: -1.43,
          ew_last: 1929823.43, ew_change: -9196.9, ew_pct: -0.48,
        })),
    });
    renderPulse();
    // نوار همیشه رندر می‌شود؛ باید منتظر نشستِ کوئری ماند، نه نخستین رندر
    await waitFor(() =>
      expect(screen.getByTestId('pulse-index').textContent).toContain('۷٬۱۵۳٬۰۸۸'),
    );
    const strip = screen.getByTestId('pulse-index');
    expect(strip.textContent).toContain('۱٬۹۲۹٬۸۲۳');
    expect(strip.textContent).toContain('-۱.۴۳٪');
    expect(strip.querySelector('.text-accent-red')).not.toBeNull();
  });

  it('شاخصِ غایب «بدون داده» است، نه صفر — و بقیهٔ پنل می‌ماند', async () => {
    mockRoutes({ 'mstat/smart-money': () => jsonResponse(smartMoney()) });
    renderPulse();
    await waitFor(() => expect(screen.getByTestId('pulse-hemat').textContent).toContain('۲۲.۵'));
    const strip = screen.getByTestId('pulse-index');
    expect(strip.textContent).toContain('بدون داده');
    expect(strip.textContent).not.toMatch(/۰٫۰۰٪/);
    expect(strip.textContent).not.toMatch(/[▲▼]/);
  });

  it('فقط عددِ پایانی بیاید: درصدِ ساختگی و فلشِ جهت ساخته نمی‌شود', async () => {
    mockRoutes({
      'mstat/smart-money': () =>
        jsonResponse(smartMoney(22.5, 300.5, -120.2, 172.2, { d_even: 20260926, last: 7153088.29 })),
    });
    renderPulse();
    await waitFor(() =>
      expect(screen.getByTestId('pulse-index').textContent).toContain('۷٬۱۵۳٬۰۸۸'),
    );
    const strip = screen.getByTestId('pulse-index');
    expect(strip.textContent).not.toContain('٪');
    expect(strip.textContent).not.toMatch(/[▲▼]/);
    expect(strip.textContent).toContain('بدون داده'); // هموزنِ بی‌عدد
  });
});
