// __tests__/inspector-fts-rail.spec.tsx — پنج کارتِ بنیادی درِ پنلِ چپ
//
// سه چیز سنجیده می‌شود (بندِ ۲ مأموریتِ رابط):
//  ۱) پنج کارت از همان خروجیِ canonicalِ تک‌نمادی خوانده می‌شوند — رابط داورِ
//     دوم نمی‌سازد؛ `null`ِ موتور «نظر نمی‌دهد» است نه صفر و نه سرخِ «رد».
//  ۲) هر کارت لینکِ همان drill-downِ موجود است (`/fundamental/<sym>?drill=N`) —
//     نه یک مسیرِ جزئیاتِ موازی.
//  ۳) علتِ بی‌داده از خودِ بک‌اند (`gap_cause`) یا واژگانِ محور (`gapLabel`)
//     می‌آید، نه از متنِ عمومیِ بی‌ربط.
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import FtsIndicatorRail from '@features/fundamental/components/FtsIndicatorRail';
import FundamentalPage from '@features/fundamental/routes/FundamentalPage';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const CARD = {
  status: 'success',
  symbol: 'فولاد',
  sector: 'فولاد',
  score: 3,
  verdict: 'PASS',
  pricing_mode: 'free',
  applicable: true,
  // سه‌حالۀ عمدی: دو PASS، یکِ رد، دو «نظر نمی‌دهد» (null) — هیچ‌کدام صفر نیست
  passes: {
    '1_growth': true,
    '2_eps_trend': false,
    '3_gross_margin': null,
    '4_sales_to_mcap': null,
    '5_industry': true,
  },
  indicators: {
    '1': { monetary: { monetary_pct: 52, threshold: 40, months: 6 }, volume: { applicable: true } },
    '2': { eps_series: [300, 180, null], years_available: 2, years_required: 3 },
    '3': { margin_pct: null },
    '4': { sales_to_mcap: null, gap_cause: 'ارزش بازار این نماد نرسید' },
    '5': { label: 'نرخ آزاد', sector: 'فولاد' },
  },
  profile: { kind: 'production', volume_applicable: true },
  metrics: {},
  thresholds: {},
  data_gaps: [],
  history: [],
  fs_count: 1,
  excluded: false,
  exclusion_reasons: [],
};

function mockFetch() {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => {
    // همان دو قدمِ تستِ `fundamental-page.spec.tsx`: نماد درِ URL.percentEncode
    // می‌رود، پس مقایسه با متنِ خامِ فارسی هیچ‌وقت نمی‌خورد.
    let u = String(url).split('?')[0];
    try {
      u = decodeURIComponent(u);
    } catch {
      /* URL انکود نشده */
    }
    if (u === '/api/fundamental/فولاد') return Promise.resolve(new Response(JSON.stringify(CARD)));
    if (u === '/api/fundamental/فولاد/quarters') {
      return Promise.resolve(new Response(JSON.stringify({ status: 'success', quarters: [] })));
    }
    if (u === '/api/screener' || u === '/api/market' || u === '/api/calendar/upcoming') {
      return Promise.resolve(new Response(JSON.stringify({ status: 'success', data: [], count: 0 })));
    }
    return Promise.resolve(new Response(JSON.stringify({ status: 'success', data: [] })));
  });
}

function qc() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

beforeEach(() => mockFetch());

describe('پنج کارت بنیادی درِ پنلِ چپ', () => {
  async function renderRail() {
    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={['/']}>
          <FtsIndicatorRail symbol="فولاد" fallbackRow={null} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    // درِ «پنلِ چپ» بودنِ کارت تا رسیدنِ کارتِ canonical بی‌عدد می‌ماند؛ تا
    // رسیدنش یکِ متنِ فقطِ کارت (نرخ آزاد) گیتِ arrival است.
    await screen.findByText('نرخ آزاد');
    return screen.getByTestId('inspector-fts-cards');
  }

  it('پنج کارت رندر می‌شود و هر کدام لینکِ همان drill-down است', async () => {
    await renderRail();
    for (const [col, drill] of [['i1', '1'], ['i2', '2'], ['i3', '3'], ['i4', '4'], ['i5', '5']] as const) {
      const card = await screen.findByTestId(`inspector-card-${col}`);
      expect(card.getAttribute('href')).toBe(`/fundamental/${encodeURIComponent('فولاد')}?drill=${drill}`);
    }
  });

  it('مقدار و حکم از کارتِ canonical می‌آید؛ «رد» با «نظر نمی‌دهد» یکی نیست', async () => {
    await renderRail();
    const i1 = await screen.findByTestId('inspector-card-i1');
    expect(i1.textContent).toContain(fmtPct(52));
    expect(i1.textContent).toContain('قبول');
    // آستانه از خودِ موتور (threshold)، نه عددِ دستِ JSX
    expect(i1.textContent).toContain(`کفِ ${toFaDigits(40)}٪`);

    const i2 = await screen.findByTestId('inspector-card-i2');
    expect(i2.textContent).toContain('رد');
    expect(i2.textContent).toContain(`${toFaDigits(2)}/${toFaDigits(3)} سال`);
    // آخرین خانۀ سری EPS تهی است ⇒ «—»، نه صفر
    expect(i2.textContent).toContain('—');

    const i3 = await screen.findByTestId('inspector-card-i3');
    expect(i3.textContent).toContain('نظر نمی‌دهد');
    expect(i3.textContent).not.toContain('رد');

    const i5 = await screen.findByTestId('inspector-card-i5');
    expect(i5.textContent).toContain('نرخ آزاد');
  });

  it('شاخص ۴ بی‌مقدار ⇒ علتِ بک‌اند رویِ کارت، و هیچ صفری ساخته نمی‌شود', async () => {
    await renderRail();
    const i4 = await screen.findByTestId('inspector-card-i4');
    expect(i4.textContent).toContain('—');
    expect(i4.textContent).toContain('ارزش بازار این نماد نرسید');
    expect(i4.textContent).not.toContain(`${toFaDigits('0.0')}٪`);
    expect(i4.textContent).not.toContain('۰٪');
    // واژۀ حکم همان «نظر نمی‌دهد» است، نه «رد»
    expect((await screen.findByTestId('inspector-card-verdict-i4')).textContent).toBe('نظر نمی‌دهد');
  });
});

describe('?drill= همان پنلِ جزئیاتِ موجود را باز می‌کند', () => {
  it('ورود با ?drill=3 پنلِ شاخص ۳ را می‌گشاید (رابطِ دوم نیست)', async () => {
    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={[`/fundamental/${encodeURIComponent('فولاد')}?drill=3`]}>
          <Routes>
            <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId('fts-drilldown-3')).toBeTruthy();
  });

  it('بی‌پارامتر هیچ پنلی باز نیست، و پارامترِ بی‌معنا پنل نمی‌سازد', async () => {
    render(
      <QueryClientProvider client={qc()}>
        <MemoryRouter initialEntries={[`/fundamental/${encodeURIComponent('فولاد')}?drill=9`]}>
          <Routes>
            <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByTestId('fts-drilldown-9')).toBeNull();
    expect(screen.queryByTestId(/^fts-drilldown-/)).toBeNull();
  });

  it('پنلِ باز شده از `?drill=` به چشم می‌آید (scrollIntoView صدا می‌شود)', async () => {
    const calls: string[] = [];
    const proto = Element.prototype as unknown as { scrollIntoView: (o?: unknown) => void };
    const prev = proto.scrollIntoView;
    proto.scrollIntoView = function scrollIntoView(this: Element, o?: unknown) {
      calls.push(this.getAttribute('data-testid') || 'unknown');
      void o;
    };
    try {
      render(
        <QueryClientProvider client={qc()}>
          <MemoryRouter initialEntries={[`/fundamental/${encodeURIComponent('فولاد')}?drill=3`]}>
            <Routes>
              <Route path="/fundamental/:symbol?" element={<FundamentalPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>,
      );
      await screen.findByTestId('fts-drilldown-3');
      await waitFor(() => expect(calls).toContain('fts-drilldown-3'));
    } finally {
      proto.scrollIntoView = prev;
    }
  });
});
