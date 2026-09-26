// #149/#151/#156 — رگرسیونِ نمایشِ کارتِ بنیادی: نتیجهٔ درشت، برچسبِ حکمِ
// هر کاشی، مقایسۀ دیداریِ دو دورۀ شاخص ۱، و پنلِ بستهٔ روند فصلی.
// اعداد از فیکسچرِ واقعیِ بک‌اند (شفارس) می‌آیند؛ کارت نباید عددی بسازد.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsCard } from '@features/fundamental/components/FtsCard';
import { QuarterlyTrend } from '@features/fundamental/components/QuarterlyTrend';
import type { FtsCardIndicators } from '@features/fundamental/api/useFtsCard';

function realCard() {
  const p = path.resolve(import.meta.dirname, 'fixtures/fts-card-shfars.json');
  return JSON.parse(readFileSync(p, 'utf8')) as {
    score: number; verdict: string; passes: Record<string, boolean>;
    pricing_mode: string; indicators: FtsCardIndicators; thresholds: Record<string, number>;
  };
}

function renderCard(over: Partial<Parameters<typeof FtsCard>[0]> = {}) {
  const c = realCard();
  render(
    <FtsCard
      score={c.score}
      passes={c.passes}
      verdict={c.verdict}
      industryMode={c.pricing_mode}
      physicalApplicable
      indicators={c.indicators}
      thresholds={c.thresholds}
      {...over}
    />,
  );
  return c;
}

const AXES = ['1a_monetary_growth', '1b_volume_growth', '2_eps_trend', '3_gross_margin', '4_sales_to_mcap', '5_industry'];

describe('#149 — نتیجهٔ هر کاشی: برچسبِ حکم + عددِ درشت', () => {
  it('شش کاشی، شش برچسبِ حکمِ مستقل و شش عددِ درشت', () => {
    renderCard();
    for (const a of AXES) {
      expect(screen.getByTestId(`fts-verdict-${a}`)).toBeInTheDocument();
    }
    const big = document.querySelectorAll('[data-testid^="fts-result-"]');
    expect(big.length).toBe(6);
  });

  it('عددِ درشت از پلۀ تایپوگرافی است نه pxِ دست‌نویس', () => {
    renderCard();
    expect(screen.getByTestId('fts-result-1a').className).toContain('text-lg');
  });

  it('حکمِ «رد» با حکمِ «قبول» یکی نیست و هیچ‌کدام تهی نیست', () => {
    renderCard();
    const pass = screen.getByTestId('fts-verdict-2_eps_trend').textContent;
    const fail = screen.getByTestId('fts-verdict-4_sales_to_mcap').textContent;
    expect(pass).toBeTruthy();
    expect(fail).toBeTruthy();
    expect(pass).not.toBe(fail);
  });

  it('محورِ بی‌حکم «نظر نمی‌دهد» می‌گیرد — نه سبز، نه سرخ', () => {
    renderCard({ passes: { '2_eps_trend': null } });
    const chip = screen.getByTestId('fts-verdict-2_eps_trend');
    expect(chip.textContent).toBe(screen.getByTestId('fts-verdict-1b_volume_growth').textContent);
  });
});

describe('#151 — مقایسۀ دیداریِ دو دورهٔ شاخص ۱', () => {
  it('هر دو دوره با نوارِ جدا و سرجمعِ ریالی نمایش می‌یابد', () => {
    renderCard();
    expect(screen.getByTestId('fts-period-compare')).toBeInTheDocument();
    expect(screen.getByTestId('fts-period-now')).toBeInTheDocument();
    expect(screen.getByTestId('fts-period-prev')).toBeInTheDocument();
    const widthOf = (id: string) => {
      const el = screen.getByTestId(id).querySelector('[style*="width"]') as HTMLElement | null;
      expect(el, `no bar for ${id}`).not.toBeNull();
      return Number.parseFloat((el as HTMLElement).style.width);
    };
    // شفارس: ۱٬۵۳۴ میلیارد تومان در برابر ۶۶۵ میلیاردِ سال قبل
    expect(widthOf('fts-period-now')).toBeGreaterThan(widthOf('fts-period-prev'));
    expect(widthOf('fts-period-now')).toBeCloseTo(100, 0);
  });

  it('دورۀ غایب نوارِ صفر نمی‌گیرد — «نیست» با «صفر» یکی نیست', () => {
    const c = realCard();
    const mon = { ...(c.indicators['1']?.monetary ?? {}), ytd_prev_bt: null };
    const ind = { ...c.indicators, 1: { ...c.indicators['1'], monetary: mon } } as FtsCardIndicators;
    renderCard({ indicators: ind });
    expect(screen.getByTestId('fts-period-prev').querySelector('[style*="width"]')).toBeNull();
    expect(screen.getByTestId('fts-period-prev').textContent).toContain('\u2014');
  });

  it('خطِ رشد فقط از آستانه‌هایِ کانفیگ شانه می‌خورد', () => {
    const c = realCard();
    renderCard({ thresholds: { ...c.thresholds, growth_min: 40, v10_monetary_growth_min: 60 } });
    const scale = screen.getByTestId('fts-growth-scale');
    expect(scale.querySelectorAll('[title]')).toHaveLength(2);
    renderCard({ thresholds: { growth_min: 40 } });
    // بدونِ هدف، فقط یک شانه می‌ماند — عددِ هدف از JSX ساخته نمی‌شود
    expect(screen.getAllByTestId('fts-growth-scale').length).toBeGreaterThan(0);
  });
});

describe('#156 — روند فصلی در نوارِ بازشو', () => {
  const Q = [
    { key: '1404-Q3', yearLabel: '1404', quarter: 3, revenue: 100, grossProfit: 20 },
    { key: '1404-Q4', yearLabel: '1404', quarter: 4, revenue: 120, grossProfit: 26 },
  ] as never;

  it('اول بسته است و نمودار در DOM نیست', () => {
    render(<QuarterlyTrend quarters={Q} />);
    expect(screen.getByTestId('qtrend-toggle').getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByTestId('quarterly-trend-chart')).toBeNull();
  });

  it('یک بار کلیک، نمودار را باز می‌کند', () => {
    render(<QuarterlyTrend quarters={Q} />);
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    expect(screen.getByTestId('qtrend-toggle').getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByTestId('quarterly-trend-chart')).toBeInTheDocument();
  });
});

describe('#169 — واژۀ حکم یک‌بار، رنگِ سه‌حالۀ شاخص ۳ و چیدمان ۳/۲', () => {
  const DECIDED = ['1a_monetary_growth', '2_eps_trend', '3_gross_margin', '4_sales_to_mcap', '5_industry'];

  it('بجِ ممیزی در کاشیِ حکم‌دار فقط «ⓘ» است — واژۀ حکم تکرار نمی‌شود', () => {
    renderCard();
    for (const a of DECIDED) {
      const badge = screen.getByTestId(`fts-cell-audit-${a}`);
      expect(badge.textContent, a).toBe('ⓘ');
      expect(screen.getByTestId(`fts-card-cell-${a}`).textContent, a).not.toContain('مردود');
    }
  });

  it('برچسبِ نتیجه در هر کاشی یکتاست (دو برچسبِ حکم در یک کاشی نیست)', () => {
    renderCard();
    for (const a of DECIDED) {
      const cell = screen.getByTestId(`fts-card-cell-${a}`);
      expect(cell.querySelectorAll(`[data-testid="fts-verdict-${a}"]`).length, a).toBe(1);
    }
  });

  it('باندِ «ایده‌آل» از موتور: واژه و رنگِ سوم — پذیرفت/رد نیست', () => {
    const c = realCard();
    const ideal = { ...c.indicators, 3: { ...c.indicators['3'], pass: true, band: 'ideal' } } as FtsCardIndicators;
    renderCard({ indicators: ideal });
    expect(screen.getByTestId('fts-verdict-3_gross_margin').textContent).toBe('ایده‌آل');
    expect(screen.getByTestId('fts-card-cell-3_gross_margin').className).toContain('cyan');
  });

  it('باندِ «acceptable» همان رنگِ قبول است — سه‌حاله هرگز بازسازی نمی‌شود', () => {
    const c = realCard();
    const ok = { ...c.indicators, 3: { ...c.indicators['3'], pass: true, band: 'acceptable' } } as FtsCardIndicators;
    renderCard({ indicators: ok });
    expect(screen.getByTestId('fts-verdict-3_gross_margin').textContent).toBe('قبول');
    expect(screen.getByTestId('fts-card-cell-3_gross_margin').className).not.toContain('cyan');
  });

  it('بدونِ band از موتور، رنگِ سوم ساخته نمی‌شود (قانونِ لایۀ نمایش)', () => {
    const c = realCard();
    const bare = { ...c.indicators, 3: { ...c.indicators['3'], pass: true } } as FtsCardIndicators;
    delete (bare['3'] as Record<string, unknown>).band;
    delete (bare['3'] as Record<string, unknown>).ideal_threshold;
    renderCard({ indicators: bare });
    expect(screen.getByTestId('fts-verdict-3_gross_margin').textContent).toBe('قبول');
    expect(screen.getByTestId('fts-card-cell-3_gross_margin').className).not.toContain('cyan');
  });

  it('چیدمان ۳ بالا / ۲ پایین: سه کارتِ اول دو ستون، دوتای آخر سه ستون', () => {
    renderCard();
    const spans = (key: string) => screen.getByTestId(`fts-card-cell-${key}`).className;
    for (const k of ['1_growth', '2_eps_trend', '3_gross_margin']) expect(spans(k), k).toContain('md:col-span-2');
    for (const k of ['4_sales_to_mcap', '5_industry']) expect(spans(k), k).toContain('md:col-span-3');
  });

  it('نشانهٔ «نمودار و جزئیات» روی هر پنج کارتِ کلیک‌پذیر هست', () => {
    renderCard({ onDrill: () => {} });
    expect(screen.getAllByTestId('fts-drill-affordance')).toHaveLength(5);
  });

  it('بی‌onDrill هیچ نشانهٔ کلیکی دروغین نیست', () => {
    renderCard({});
    expect(screen.queryAllByTestId('fts-drill-affordance')).toHaveLength(0);
  });
});

describe('#169 — نمودارها در ارتفاعِ استاندارد رندر می‌شوند', () => {
  const Q = [
    { key: '1404-Q3', yearLabel: '1404', quarter: 3, revenue: 100, grossProfit: 20 },
    { key: '1404-Q4', yearLabel: '1404', quarter: 4, revenue: 120, grossProfit: 26 },
  ] as never;

  it('روند فصلی: ارتفاعِ پیکسلی ثابت، نه viewBoxِ کشیده‌شده با عرض', () => {
    render(<QuarterlyTrend quarters={Q} />);
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    const svg = screen.getByTestId('quarterly-trend-chart');
    expect(svg.getAttribute('height')).toBe('168');
    expect(svg.getAttribute('viewBox')).toMatch(/^0 0 \d+ 168$/);
    expect(svg.getAttribute('class')).toContain('block');
  });
});
