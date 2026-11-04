import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Bullet } from '@features/fundamental/ui/mini/Bullet';
import { EpsBars } from '@features/fundamental/ui/mini/EpsBars';
import { RegimeGlyph } from '@features/fundamental/ui/mini/RegimeGlyph';
import { AxisGlyph } from '@features/fundamental/ui/mini/AxisGlyph';
import { PeDots } from '@features/fundamental/ui/mini/PeDots';
import { HistoryBars } from '@features/fundamental/ui/mini/HistoryBars';

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
  });
});
