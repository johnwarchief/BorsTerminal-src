// تست کامپوننت های بنیادی: تاب آوری در برابر null و رندر روند
// (نردبان EPS در `FtsDrillDown` زنده است؛ `EpsLadder` مرده حذف شد و
//  حکم‌هایش به src/__tests__/fts-drilldown.spec.tsx منتقل شده)
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QuarterlyTrend } from '@features/fundamental/components/QuarterlyTrend';
import { SectorPePanel } from '@features/fundamental/components/SectorPePanel';
import type { FiscalQuarter } from '@features/fundamental/lib/fundMath';

const QUARTERS: FiscalQuarter[] = [
  // grossProfit + marginِ هم‌راستا با آن (#102: margin = سود ناخالص ÷ درآمد × ۱۰۰)
  { key: '1404-Q1', yearLabel: '1404', quarter: 1, revenue: 3_848_391, operatingProfit: null, netProfit: 251_819, grossProfit: 1_154_517, margin: 30.0 },
  { key: '1404-Q2', yearLabel: '1404', quarter: 2, revenue: 4_751_559, operatingProfit: null, netProfit: -374_561, grossProfit: -332_609, margin: -7.0 },
];

describe('کامپوننت های بنیادی', () => {
  it('روند فصلی با سود منفی کرش نمی کند', () => {
    const { container } = render(<QuarterlyTrend quarters={QUARTERS} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    expect(container.querySelector('svg')).not.toBeNull();
    // #102: مبنای مقایسه با درآمد، سود **ناخالص** است — سربرگ هم همین را می‌گوید
    // (پیش از این «سود خالص» بود در حالی که جزوه سود ناخالص را می‌خواهد).
    expect(screen.getByText('روند فصلی درآمد و سود ناخالص')).toBeInTheDocument();
  });

  it('روند فصلی: برچسب فصل‌ها فارسی است (بهار/تابستان و…)', () => {
    render(<QuarterlyTrend quarters={QUARTERS} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    const svg = screen.getByTestId('quarterly-trend-chart');
    expect(svg.textContent).toContain('بهار');
    expect(svg.textContent).toContain('تابستان');
    // برچسب فصل نمایشی (text node) فرمت «فصل سال» دارد — نه «سال-Qشماره»
    const labelNodes = Array.from(svg.querySelectorAll('text')).map((t) => t.textContent ?? '');
    expect(labelNodes.some((t) => /^بهار ۰۴$/.test(t))).toBe(true);
    expect(labelNodes.some((t) => /^تابستان ۰۴$/.test(t))).toBe(true);
  });

  it('روند فصلی: محور Y با برچسب مقیاس (میلیارد تومان/همت) رندر می‌شود', () => {
    render(<QuarterlyTrend quarters={QUARTERS} />);
    // #156 — پنل بسته است؛ نمودار را با کلیکِ نوار باز می‌کنیم
    fireEvent.click(screen.getByTestId('qtrend-toggle'));
    const svg = screen.getByTestId('quarterly-trend-chart');
    const labelNodes = Array.from(svg.querySelectorAll('text')).map((t) => t.textContent ?? '');
    expect(labelNodes.some((t) => t.includes('ب.ت') || t.includes('همت'))).toBe(true);
    // واحد زیر نمودار هم میلیارد تومان است (نه میلیون ریال)
    // #156 — پانوشتِ «ارقام میلیارد تومان» به برچسبِ خودِ نوارِ بازشو رفت
    expect(screen.getByTestId('qtrend-toggle').textContent).toContain('میلیارد تومان');
  });

  it('روند خالی حالت خالی تمیز دارد', () => {
    render(<QuarterlyTrend quarters={[]} />);
    expect(screen.getByText('سری فصلی برای این نماد نیست')).toBeInTheDocument();
  });

  it('پنل صنعت تخفیف را درست نشان می دهد', () => {
    render(<SectorPePanel pe={5} median={7} sector="الف" />);
    expect(screen.getByText(/ارزان تر/)).toBeInTheDocument();
  });

  it('پنل صنعت بدون P/E حالت خالی دارد', () => {
    render(<SectorPePanel pe={null} median={7} sector="الف" />);
    expect(screen.getByText('P/E قابل اتکا برای مقایسه صنعتی نیست')).toBeInTheDocument();
  });
});
