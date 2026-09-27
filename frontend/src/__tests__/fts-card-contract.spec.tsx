// رگرسیون دو باگ گزارش‌شدهٔ کاربر در نمای بنیادی:
// ۱) کارت خالی FTS وقتی بک‌اند سال مالی `history[].fiscal_year` را «رشته»
//    می‌فرستد (کدال: "1404") ولی اسکیمای فرانت `z.number()` خشک داشت؛
//    parse کل کارت می‌افتاد و صفحه به‌جای کارت، حالت «بدون داده» می‌داد.
// ۲) پنل تنظیمات به‌جای دراور ثابت سمت راست، در جریان صفحه/پایین ظاهر می‌شد؛
//    ریشه: قاعدهٔ بیرون‌از‌layer `.glass-panel{position:relative}` در index.css
//    بر utilities تیلویند (داخل @layer utilities) مقدم است و `fixed` را باطل
//    می‌کند. پس پنل نباید کلاس glass-panel داشته باشد.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import FundamentalPage from '@features/fundamental/routes/FundamentalPage';
import { FtsCardSchema } from '@features/fundamental/api/useFtsCard';
import { FtsSettingsTrigger } from '@features/fundamental/ui/FtsSettingsDrawer';
import { FTS_GUIDE_DEFAULTS } from '@features/fundamental/api/useFtsConfig';

const fetchMock = vi.fn();
// کارتِ سفارشیِ هر تست (برای حالت‌هایی مثل «excluded با امتیاز ۴»)
let cardOverride: Record<string, unknown> | null = null;
vi.stubGlobal('fetch', fetchMock);

/** کارت واقعیِ بک‌اند برای شفارس — عیناً از /api/fundamental/شفارس گرفته شده
 *  (سال مالی `history[].fiscal_year` = "1404" رشته‌ای — همان چیزی که باگ را می‌ساخت) */
function realCard() {
  const p = path.resolve(import.meta.dirname, 'fixtures/fts-card-shfars.json');
  return JSON.parse(readFileSync(p, 'utf8')) as Record<string, unknown>;
}

/** کارت حداقلیِ معتبر با تنها فیلدی که رگرسیون را می‌سازد: fiscal_year رشته‌ای */
function minimalCard(fiscalYear: unknown) {
  return {
    status: 'success',
    symbol: 'شفارس',
    sector: 'محصولات شيميايي',
    score: 4,
    verdict: 'STRONG',
    pricing_mode: 'free',
    excluded: false,
    exclusion_reasons: [],
    passes: {
      '1a_monetary_growth': true,
      '1b_volume_growth': true,
      '2_eps_trend': true,
      '3_gross_margin': true,
      '4_sales_to_mcap': false,
      '5_industry': true,
    },
    profile: { kind: 'production', volume_applicable: true },
    metrics: { eps_series: [91, 96, 202], eps_slots: ['1402', '1403', '1404'], eps_partial: false },
    indicators: {},
    data_gaps: [],
    history: [
      {
        period_end: '1404/12/29',
        fiscal_year: fiscalYear,
        revenue: 19860726,
        gross_profit: 4206191,
        net_profit: 2410320,
        eps: 202,
        audited: true,
        consolidated: false,
      },
    ],
    fs_count: 4,
  };
}

function mockJson(url: string): unknown {
  const u = decodeURIComponent(url.split('?')[0]);
  if (u === '/api/screener') {
    return {
      status: 'success',
      count: 1,
      data: [{ symbol: 'شفارس', sector_name: 'محصولات شيميايي', score: 4, eps_data_gap: false }],
      thresholds: {},
      max_score: 5,
    };
  }
  if (u === '/api/market') return { status: 'success', data: [] };
  if (u.endsWith('/quarters')) return { status: 'success', symbol: 'شفارس', count: 0, quarters: [] };
  if (u === '/api/fts/config') return { status: 'success', config: { ...FTS_GUIDE_DEFAULTS } };
  if (u.startsWith('/api/fundamental/')) return cardOverride ?? minimalCard('1404');
  return { status: 'success', data: [] };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/fundamental/شفارس']}>
        <Routes>
          <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('اسکیمای کارت FTS — تحمل سال مالی رشته‌ای (رگرسیون کارت خالی)', () => {
  it('سال مالی «رشته‌ای» کدال را می‌پذیرد (و کل کارت را نمی‌اندازد)', () => {
    const parsed = FtsCardSchema.safeParse(minimalCard('1404'));
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.history?.[0]?.fiscal_year).toBe(1404);
    }
  });

  it('سال مالی عددی و تهی را هم می‌پذیرد', () => {
    for (const v of [1404, null, undefined]) {
      const parsed = FtsCardSchema.safeParse(minimalCard(v));
      expect(parsed.success, `fiscal_year=${String(v)}`).toBe(true);
    }
    expect(FtsCardSchema.safeParse(minimalCard(null)).success).toBe(true);
    const nullCase = FtsCardSchema.safeParse(minimalCard(null));
    if (nullCase.success) expect(nullCase.data.history?.[0]?.fiscal_year).toBeNull();
  });

  it('کارت واقعیِ بک‌اند (شفارس) بدون خطا parse می‌شود', () => {
    const parsed = FtsCardSchema.safeParse(realCard());
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.score).toBe(4);
      expect(parsed.data.verdict).toBe('STRONG');
      expect(parsed.data.passes?.['5_industry']).toBe(true);
    }
  });
});

describe('صفحهٔ بنیادی — کارت خالی با دادهٔ رشته‌ای پر می‌شود', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockJson(typeof url === 'string' ? url : '')),
      } as unknown as Response),
    );
  });

  it('امتیاز، verdict و شش سلول شاخص را نشان می‌دهد (نه حالت بدون داده)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('امتیاز ۴ از ۵')).toBeInTheDocument());
    expect(screen.queryByText('STRONG')).toBeNull();
    expect(screen.queryByText('EXCLUDED')).toBeNull();
    /** #169: واژۀ حکم در هر سلول یک‌بار نوشته می‌شود (برچسبِ نتیجه)، و بجِ
     *  ممیزی دیگر همان واژه را تکرار نمی‌کند — «قبول» دوباره‌نویسی نشد. */
    const cells: [string, string][] = [
      ['1a_monetary_growth', 'قبول'],
      ['2_eps_trend', 'قبول'],
      ['4_sales_to_mcap', 'رد'],
    ];
    for (const [axis, word] of cells) {
      expect(screen.getByTestId(`fts-verdict-${axis}`)).toHaveTextContent(word);
      const cell = screen.getByTestId(`fts-card-cell-${axis}`);
      expect(cell.textContent).toContain(word);
      expect(cell.textContent).not.toContain('مردود');
    }
    expect(screen.getByTestId('fts-card-cell-5_industry')).toHaveTextContent('صنعت آزاد');
    // حالت «داده نیامد» نباید فعال باشد — کارت باید واقعاً رندر شده باشد
    expect(screen.queryByText(/دادهٔ کارت بنیادی/)).not.toBeInTheDocument();
  });
});

describe('علت حذف از غربالگری — داخل جعبهٔ تصمیم، بی پنلِ جدا', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockJson(typeof url === 'string' ? url : '')),
      } as unknown as Response),
    );
  });

  afterEach(() => {
    cardOverride = null;
  });

  it('امتیاز ۴ + وتوی ماده ۱۴۱ ⇒ علتِ حذف هم کنارِ «گزینه مستعد» دیده می‌شود', async () => {
    cardOverride = {
      ...minimalCard('1404'),
      score: 4,
      excluded: true,
      exclusion_reasons: ['ماده ۱۴۱ — زیان انباشته', 'نماد تعلیق'],
    };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('fts-exclusion-line')).toBeInTheDocument());
    const line = screen.getByTestId('fts-exclusion-line');
    expect(line.textContent).toContain('ماده ۱۴۱');
    expect(line.textContent).toContain('نماد تعلیق');
    // پنلِ دروازه‌های ریسک حذف است (درخواست کاربر) — فقط همین خط می‌ماند
    expect(screen.queryByText('دروازه های ریسک')).not.toBeInTheDocument();
  });

  it('بدون وتو، خطِ حذف ساخته نمی‌شود', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('امتیاز ۴ از ۵')).toBeInTheDocument());
    expect(screen.queryByTestId('fts-exclusion-line')).not.toBeInTheDocument();
  });
});

describe('کف‌های کارت FTS — از پاسخِ بک‌اند، نه عددِ ثابتِ UI', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockJson(typeof url === 'string' ? url : '')),
      } as unknown as Response),
    );
  });

  afterEach(() => {
    cardOverride = null;
  });

  it('آستانهٔ غیرپیش‌فرض در همان سلول دیده می‌شود (اسلایدرِ تنظیمات کارت را بی‌روغن نمی‌کند)', async () => {
    cardOverride = {
      ...minimalCard('1404'),
      indicators: {
        '1': { volume: { threshold: 11, applicable: true, pass: true } },
        '2': { years_required: 4, strictly_rising: true, eps_series: [1, 2, 3, 4], pass: true },
        '3': { margin_pct: 31.5, threshold: 26, ideal_threshold: 28, pass: true },
        '4': { sales_to_mcap: 0.9, sales_threshold: 0.77, pass: true },
        '5': { verdict: 'free', pass: true },
      },
    };
    renderPage();
    await waitFor(() => expect(screen.getByText('امتیاز ۴ از ۵')).toBeInTheDocument());
    expect(screen.getByTestId('fts-card-cell-1_growth').textContent).toMatch(/≥\s*۱۱٪/);
    expect(screen.getByTestId('fts-card-cell-2_eps_trend').textContent).toContain('۴ سالِ رشد');
    const m = screen.getByTestId('fts-card-cell-3_gross_margin').textContent ?? '';
    expect(m).toMatch(/≥\s*۲۶٪/);
    expect(m).toContain('ایده‌آل ۲۸٪');
    expect(screen.getByTestId('fts-card-cell-4_sales_to_mcap').textContent).toMatch(/۰[./]۷۷×/);
    // هیچ‌کدام از کف‌های پیش‌فرض نباید جای عددِ بک‌اند نشسته باشد
    expect(m).not.toMatch(/≥\s*۲۰٪/);
  });

  it('هلدینگِ معاف: پنلِ P/NAV می‌آید هرچند نام/گروه را هیچ طبقه‌بندی نشناسد', async () => {
    cardOverride = {
      ...minimalCard('1404'),
      sector: 'فعاليتهاي كمكي به نهادهاي مالي واسط',
      indicators: { '4': { na: true, exempt: true, reason: 'هلدینگ؛ N/A' } },
    };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('holding-pnav-panel')).toBeInTheDocument());
    expect(screen.queryByTestId('fts-strategy-summary')).not.toBeInTheDocument();
  });

  it('صندوق (رأی ۱۵): «FTS ندارد» نشان داده می‌شود نه متنِ «هلدینگ/سرمایه‌گذاری»', async () => {
    cardOverride = {
      ...minimalCard('1404'),
      sector: 'صندوق‌های سرمایه‌گذاری',
      applicable: false,
      verdict: 'FTS ندارد',
      indicators: { '4': { na: true, exempt: true, reason: 'صندوق؛ N/A' } },
    };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('fts-strategy-summary')).toBeInTheDocument());
    expect(screen.queryByTestId('holding-pnav-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('fts-strategy-summary').textContent).toContain('FTS ندارد');
  });

  it('قرارداد اختیار: داوری برایش صادر نمی‌شود و به نماد اصلی ارجاع داده می‌شود', async () => {
    cardOverride = {
      ...minimalCard('1404'),
      score: null,
      applicable: false,
      verdict: 'FTS ندارد',
      ref_symbol: 'خبهمن',
      ref_reason: 'قرارداد اختیار معامله — تحلیل به نماد اصلی آن',
      indicators: {},
    };
    renderPage();
    await waitFor(() => expect(screen.getByTestId('fts-strategy-summary')).toBeInTheDocument());
    expect(screen.getByTestId('fts-referral').textContent).toContain('قرارداد اختیار');
    expect(screen.getByTestId('fts-referral-open').textContent).toBe('خبهمن');
    // علت را خودِ backend می‌نویسد؛ رابط نباید نسخهٔ «صندوق» را نشان دهد
    expect(screen.getByTestId('fts-strategy-summary').textContent).not.toContain('صندوق است');
  });

  it('شاخصِ «نظر نمی‌دهد» (رأیِ مالک ۱۴۰۵-۰۷-۰۳) به‌جای «مردود» سرخ نمی‌شود', async () => {
    const base = minimalCard('1404');
    cardOverride = {
      ...base,
      passes: { ...base.passes, '4_sales_to_mcap': null },
      indicators: { '4': { na: true, exempt: true, reason: 'هلدینگ؛ نسبت فروش به ارزش بازار کاربرد ندارد (N/A).' } },
    };
    renderPage();
    await waitFor(() => expect(screen.getByText('امتیاز ۴ از ۵')).toBeInTheDocument());
    const cell = screen.getByTestId('fts-card-cell-4_sales_to_mcap');
    expect(cell.textContent).not.toContain('مردود');
    expect(cell.className).not.toContain('accent-red');
  });
});

describe('پنل تنظیمات FTS — دراور ثابت سمت راست (رگرسیون جای‌گیری)', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'success', config: { ...FTS_GUIDE_DEFAULTS } }),
    } as unknown as Response);
  });

  it('کلاس glass-panel ندارد (position:relative بیرون‌از‌layer، `fixed` را باطل می‌کند)', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <FtsSettingsTrigger open onToggle={() => {}} />
      </QueryClientProvider>,
    );
    const panel = screen.getByTestId('fts-settings-panel');
    expect(panel.parentElement).toBe(document.body);
    expect(panel.className).toContain('fixed');
    expect(panel.className).toContain('inset-y-0');
    expect(panel.className).toContain('start-0'); // RTL: inset-inline-start = لبهٔ راست
    expect(panel.className).not.toContain('glass-panel');
  });
});
