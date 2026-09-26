// تست کامپوننت های بنیادی: تاب آوری در برابر null و رندر روند
// + تفکیک میاندوره در نردبان EPS + نردبان خالی + فارسی‌سازی نمودار فصلی
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EpsLadder } from '@features/fundamental/components/EpsLadder';
import { QuarterlyTrend } from '@features/fundamental/components/QuarterlyTrend';
import { SectorPePanel } from '@features/fundamental/components/SectorPePanel';
import type { FiscalQuarter } from '@features/fundamental/lib/fundMath';

const QUARTERS: FiscalQuarter[] = [
  // grossProfit + marginِ هم‌راستا با آن (#102: margin = سود ناخالص ÷ درآمد × ۱۰۰)
  { key: '1404-Q1', yearLabel: '1404', quarter: 1, revenue: 3_848_391, operatingProfit: null, netProfit: 251_819, grossProfit: 1_154_517, margin: 30.0 },
  { key: '1404-Q2', yearLabel: '1404', quarter: 2, revenue: 4_751_559, operatingProfit: null, netProfit: -374_561, grossProfit: -332_609, margin: -7.0 },
];

describe('کامپوننت های بنیادی', () => {
  it('نردبان EPS دوره ناقص را با خط تیره قرمز و علتِ گویا نشان می دهد', () => {
    render(<EpsLadder slots={['1403', '1404']} series={[100, null]} partial />);
    expect(screen.getByText('-')).toBeInTheDocument();
    // جای برچسب خالی «ناقص»، علتِ واقعی: فقط ۱ سال سابقه هست
    expect(screen.getByText('سابقهٔ EPS کمتر از ۲ سال')).toBeInTheDocument();
  });

  it('نردبان EPS با ۲ سالِ موجود: همان دو سال رندر + برچسب «مردود — سابقهٔ ناقص» + علت در title', () => {
    render(<EpsLadder slots={['1403', '1404']} series={[100, 150]} partial requiredYears={3} />);
    // همان دو سالِ موجود نمایش داده می‌شود — داده حیف نمی‌شود
    expect(screen.getByText('۱۰۰')).toBeInTheDocument();
    expect(screen.getByText('۱۵۰')).toBeInTheDocument();
    const label = screen.getByTestId('eps-partial-rejected');
    expect(label.textContent).toContain('مردود در شاخص ۲');
    expect(label.textContent).toContain('۲ از ۳ سال');
    // hover (title) علت شکاف را توضیح می‌دهد
    expect(label.getAttribute('title')).toContain('فقط ۲ سال از ۳ سال');
  });

  it('نردبان EPS با ۱ سالِ موجود: برچسب علت‌دار می‌گیرد — برچسب سابقهٔ ناقص نمی‌آید', () => {
    render(<EpsLadder slots={['1404']} series={[100]} partial requiredYears={3} />);
    expect(screen.getByText('سابقهٔ EPS کمتر از ۲ سال')).toBeInTheDocument();
    expect(screen.queryByTestId('eps-partial-rejected')).not.toBeInTheDocument();
  });

  it('نردبان EPS: دوره میاندوره ۳ ماهه با برچسب جدا از سود سالانه نمایش می‌یابد', () => {
    render(
      <EpsLadder
        slots={['1403', '1404']}
        series={[96, 202]}
        partial={false}
        interim={{ available: true, periodEnd: '1405/03/31', months: 3, eps: 51 }}
      />,
    );
    const interimCell = screen.getByTestId('eps-interim-cell');
    expect(interimCell.textContent).toContain('میاندوره');
    expect(interimCell.textContent).toContain('۳ ماهه');
    expect(interimCell.textContent).toContain('۵۱');
    expect(interimCell.textContent).toContain('جزئی');
    // سلول‌های سالانه با «سال مالی کامل» برچسب می‌خورند تا با میاندوره اشتباه نشوند
    const ladder = screen.getByTestId('eps-ladder');
    expect(ladder.textContent).toContain('سال مالی کامل');
  });

  it('نردبان EPS: بدون میاندوره و بدون سری، رندر نمی‌شود', () => {
    const { container } = render(<EpsLadder slots={[]} series={[]} partial={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('روند فصلی با سود منفی کرش نمی کند', () => {
    const { container } = render(<QuarterlyTrend quarters={QUARTERS} />);
    expect(container.querySelector('svg')).not.toBeNull();
    // #102: مبنای مقایسه با درآمد، سود **ناخالص** است — سربرگ هم همین را می‌گوید
    // (پیش از این «سود خالص» بود در حالی که جزوه سود ناخالص را می‌خواهد).
    expect(screen.getByText('روند فصلی درآمد و سود ناخالص')).toBeInTheDocument();
  });

  it('روند فصلی: برچسب فصل‌ها فارسی است (بهار/تابستان و…)', () => {
    render(<QuarterlyTrend quarters={QUARTERS} />);
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
    const svg = screen.getByTestId('quarterly-trend-chart');
    const labelNodes = Array.from(svg.querySelectorAll('text')).map((t) => t.textContent ?? '');
    expect(labelNodes.some((t) => t.includes('ب.ت') || t.includes('همت'))).toBe(true);
    // واحد زیر نمودار هم میلیارد تومان است (نه میلیون ریال)
    expect(screen.getByText(/ارقام میلیارد تومان/)).toBeInTheDocument();
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
