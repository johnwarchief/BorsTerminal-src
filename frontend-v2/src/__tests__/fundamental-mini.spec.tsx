import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Bullet } from '@features/fundamental/ui/mini/Bullet';
import { EpsBars } from '@features/fundamental/ui/mini/EpsBars';
import { RegimeGlyph } from '@features/fundamental/ui/mini/RegimeGlyph';
import { AxisGlyph } from '@features/fundamental/ui/mini/AxisGlyph';
import { PeDots } from '@features/fundamental/ui/mini/PeDots';
import { HistoryBars } from '@features/fundamental/ui/mini/HistoryBars';
import { DeltaBars } from '@features/fundamental/ui/mini/DeltaBars';

afterEach(cleanup);

describe('mini charts', () => {
  it('renders a bullet with threshold and aria label', () => {
    render(<Bullet value={45.9} max={200} threshold={60} status="fail" label="رشد ۴۵٫۹ در برابر آستانهٔ ۶۰" />);
    const img = screen.getByRole('img', { name: /آستانه/ });
    expect(img).toBeTruthy();
    expect(img.querySelectorAll('rect').length).toBeGreaterThanOrEqual(2);
    expect(img.querySelector('.fd-th-line')).toBeTruthy();
  });
  it('renders three EPS bars', () => {
    render(<EpsBars series={[1119, 1615, 1672]} status="pass" label="سری EPS" />);
    expect(screen.getByRole('img', { name: /سری EPS/ }).querySelectorAll('rect').length).toBe(3);
  });
  it('renders three regime dots with the active one', () => {
    render(<RegimeGlyph regime="neutral" status="pass" />);
    expect(document.querySelectorAll('.fd-regime-dot').length).toBe(3);
    expect(document.querySelector('.fd-regime-dot.is-active')).toBeTruthy();
  });
  it('renders a five-bar glyph with status classes', () => {
    render(<AxisGlyph statuses={['pass', 'fail', 'na', 'unknown', 'pass']} labels={['رشد', 'EPS', 'حاشیه', 'فروش', 'صنعت']} />);
    expect(screen.getByRole('img', { name: /پنج محور/ }).querySelectorAll('span').length).toBe(5);
    expect(document.querySelectorAll('.is-fail').length).toBe(1);
  });
  it('renders P/E dot against the median with a threshold marker (R13)', () => {
    render(<PeDots pe={5} median={7} peers={12} />);
    const img = screen.getByRole('img', { name: /P\/E/ });
    expect(img).toBeTruthy();
    expect(img.querySelector('.fd-th-line')).toBeTruthy();
    expect(img.querySelector('circle')).toBeTruthy();
    expect(screen.getByText('۱۲ همتا')).toBeTruthy();
  });
  it('renders one labelled bar per history value (R13/R93)', () => {
    render(<HistoryBars values={[1, 2, 3]} labels={['۱۴۰۲', '۱۴۰۳', '۱۴۰۴']} status="pass" />);
    const img = screen.getByRole('img', { name: /تاریخچه/ });
    const bars = img.querySelectorAll('.fd-history-bar.is-pass');
    expect(bars.length).toBe(3);
    expect(Array.from(bars).every((bar) => !(bar as HTMLElement).style.background)).toBe(true);
    // R93: ارتفاعِ درصدیِ هر میله inline است تا در ستونِ flex ارتفاع قطعی بگیرد.
    expect(Array.from(bars).every((bar) => (bar as HTMLElement).style.height !== '')).toBe(true);
    // R-P1-13 (Minor 3): نامِ قابل‌دسترس هر سه عدد را اعلام می‌کند، نه فقط «تاریخچه…».
    const name = img.getAttribute('aria-label') ?? '';
    expect(name.startsWith('تاریخچهٔ گزارش‌ها')).toBe(true);
    expect(name).toContain('۱۴۰۲: ۱');
    expect(name).toContain('۱۴۰۴: ۳');
  });
  it('labels evidence bars by their own name and never announces a gate pass (R-P1-8)', () => {
    render(<HistoryBars values={[160873, 250942]} labels={['دوره قبل', 'دوره جاری']} status="evidence" label="فروش دورهٔ جاری و قبل" />);
    // R-P1-13 (Minor 3): همان پیشوندِ نام حفظ است و عددِ دقیق هر میله به نام اضافه می‌شود.
    const img = screen.getByRole('img', { name: /^فروش دورهٔ جاری و قبل/ });
    const name = img.getAttribute('aria-label') ?? '';
    expect(name).toContain('دوره قبل: ۱۶۰۸۷۳');
    expect(name).toContain('دوره جاری: ۲۵۰۹۴۲');
    expect(name).not.toContain('قبول');
    expect(img.querySelectorAll('.fd-history-bar.is-evidence').length).toBe(2);
  });
  it('renders delta bars with direction classes', () => {
    render(<DeltaBars values={[null, 44.3, 3.5]} labels={['۱۴۰۳', '۱۴۰۴', '۱۴۰۵']} />);
    expect(screen.getByRole('img', { name: /رشد دوره‌ای/ })).toBeTruthy();
    expect(document.querySelectorAll('.fd-delta-bar.is-up').length).toBe(2);
    expect(document.querySelectorAll('.fd-delta-bar.is-down').length).toBe(0);
    expect(screen.getByText('۱۴۰۴')).toBeTruthy();
  });
  it('renders negative delta bars with the down class and no fake zero bar', () => {
    render(<DeltaBars values={[null, -12.5]} labels={['۱۴۰۳', '۱۴۰۴']} />);
    expect(document.querySelectorAll('.fd-delta-bar.is-down').length).toBe(1);
    expect(document.querySelectorAll('.fd-delta-bar.is-up').length).toBe(0);
    const empty = document.querySelector('.fd-delta-bar.is-empty') as HTMLElement | null;
    expect(empty).toBeTruthy();
    expect(empty?.style.height).toBe('0%');
  });
  it('tones a zero delta as flat with no growth bar (R-P1-3)', () => {
    render(<DeltaBars values={[0, 12.5]} labels={['۱۴۰۳', '۱۴۰۴']} />);
    expect(document.querySelectorAll('.fd-delta-bar.is-flat').length).toBe(1);
    expect(document.querySelectorAll('.fd-delta-bar.is-up').length).toBe(1);
    const flat = document.querySelector('.fd-delta-bar.is-flat') as HTMLElement;
    expect(flat.style.height).toBe('0%');
  });
  it('fills the plot with a locked contract: 100% max, linear halves, 10% floor, honest 0% for null and real zero (R-P1-12)', () => {
    render(
      <div className="h-[44px]">
        <DeltaBars values={[null, 44.3, 22.15, 3.5, 0]} labels={['۱۴۰', '۱۴۰۱', '۱۴۰۲', '۱۴۰۳', '۱۴۰۴']} />
      </div>,
    );
    const bars = Array.from(document.querySelectorAll('.fd-delta-bar')) as HTMLElement[];
    expect(bars).toHaveLength(5);
    // بزرگ‌ترینِ غیرصفر کلِ ناحیه را پر می‌کند و نصفِ آن نصفِ ارتفاع (خطی‌بودن، نه کفِ تصادفی).
    expect(bars[1].style.height).toBe('100%');
    expect(bars[2].style.height).toBe('50%');
    // کفِ ۱۰٪ رویِ مقدارِ کوچکِ غیرصفر می‌نشیند (طبیعی‌اش ۷٫۹٪ بود).
    expect(parseFloat(bars[3].style.height)).toBeCloseTo(10, 5);
    // نبودِ مقدار و صفرِ واقعی: میلهٔ صفرِ صادق، بدونِ رنگِ جهتِ ساختگی.
    expect(bars[0].style.height).toBe('0%');
    expect(bars[4].style.height).toBe('0%');
    expect(bars[0].className).toContain('is-empty');
    expect(bars[4].className).toContain('is-flat');
    // R-P1-13 (Minor 3): عددِ دقیق در title هر میله و در نامِ قابل‌دسترسِ ظرف است.
    expect(bars[1].closest('[title]')?.getAttribute('title')).toBe('۱۴۰۱ — +۴۴٫۳٪');
    const name = screen.getByRole('img', { name: /^رشد دوره‌ای EPS/ }).getAttribute('aria-label') ?? '';
    expect(name).toContain('۱۴۰۱: +۴۴٫۳٪');
    expect(name).toContain('۱۴۰۳: +۳٫۵٪');
  });
  it('renders an empty state when every history value is absent (R-P1-8)', () => {
    render(<HistoryBars values={[null, null]} labels={['دوره قبل', 'دوره جاری']} status="evidence" label="فروش دورهٔ جاری و قبل" />);
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByText(/ثبت نشده/)).toBeTruthy();
  });
  it('floors small history values at 8% but paints absent and true-zero history as no bar (R-P1-12 regression)', () => {
    render(<HistoryBars values={[1000, 40, null, 0]} labels={['۱۴۰۲', '۱۴۰۳', '۱۴۰۴', '۱۴۰۵']} status="pass" />);
    const bars = Array.from(document.querySelectorAll('.fd-history-bar')) as HTMLElement[];
    expect(bars).toHaveLength(4);
    expect(bars[0].style.height).toBe('100%');
    // R-P1-12: کفِ ۸٪ فقط برایِ مقدارِ واقعیِ کوچک است.
    expect(bars[1].style.height).toBe('8%');
    // Important 1: «نبودِ مقدار» و «صفرِ واقعی» میله نمی‌گیرند؛ خطِ باریکِ تُن‌دار هم نه.
    expect(bars[2].style.height).toBe('0%');
    expect(bars[3].style.height).toBe('0%');
    // تُنِ وضعیتِ هر میله دست‌نخورده می‌ماند.
    expect(bars.every((bar) => bar.classList.contains('is-pass'))).toBe(true);
    // عددِ دقیق همچنان در title هر میله است.
    expect(bars[0].closest('[title]')?.getAttribute('title')).toBe('۱۴۰۲ — ۱۰۰۰');
    expect(bars[2].closest('[title]')?.getAttribute('title')).toBe('۱۴۰۴ — —');
  });
});
