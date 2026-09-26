// تست فلش بدون رفرش: وقتی مقدار prop عوض می‌شود، کلاس flash-up/flash-down
// باید روی همان گره DOM اعمال شود (بدون تخریب نود) تا کاربر تغییر را «در آن واحد» ببیند.
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { FlashNum } from '@shared/components/FlashNum';
import { TapeTable } from '@features/market/components/TapeTable';

// jsdom اندازه ندارد -- مجازی‌ساز باید وادار به رندرِ کامل شود، وگرنه ردیفی
// روی صفحه نیست و آزمونِ فلاشِ تابلو الکی سبز (یا الکی قرمز) می‌شود.
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 40,
      getVirtualItems: () =>
        Array.from({ length: count }, (_, i) => ({ key: i, index: i, start: i * 40, size: 40 })),
    }),
  };
});

function boardRow(patch: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    p_closing: 5000,
    p_last: 5100,
    percent_change: 2,
    tvol: 1_000_000,
    month_avg_vol: 1_000_000,
    vol_ratio: 1.5,
    buyer_power: 1.2,
    z_tot_tran: 120,
    is_live: true,
    ...patch,
  } as MarketRow;
}

const r = (v: number | null | undefined) => String(v ?? '-');

describe('FlashNum — فلش لحظه‌ای بدون رفرش', () => {
  it('با افزایش مقدار، کلاس flash-up می‌گیرد', () => {
    const { rerender } = render(<FlashNum value={100} render={r} />);
    const el = screen.getByText('100');
    expect(el.className).not.toContain('flash-up');
    rerender(<FlashNum value={125} render={r} />);
    expect(screen.getByText('125').className).toContain('flash-up');
  });

  it('با کاهش مقدار، کلاس flash-down می‌گیرد', () => {
    const { rerender } = render(<FlashNum value={200} render={r} />);
    rerender(<FlashNum value={150} render={r} />);
    expect(screen.getByText('150').className).toContain('flash-down');
  });

  it('همان گره DOM حفظ می‌شود (بدون key/بازسازی)', () => {
    const { rerender } = render(<FlashNum value={10} render={r} />);
    const before = screen.getByText('10');
    rerender(<FlashNum value={20} render={r} />);
    const after = screen.getByText('20');
    expect(after.isSameNode(before)).toBe(true);
  });

  it('مقدار null→عدد فلش نمی‌زند (فقط تغییر واقعی عدد)', () => {
    const { rerender } = render(<FlashNum value={null} render={r} />);
    rerender(<FlashNum value={5} render={r} />);
    expect(screen.getByText('5').className).not.toMatch(/flash-(up|down)/);
  });
});

// ── فلاشِ واقعیِ تابلو ───────────────────────────────────────────────────────
// واحدِ FlashNum سبز بود ولی هیچ‌کس ثابت نمی‌کرد ستون‌هایِ تابلو به آن وصل
//اند؛ یعنی «flash کار نمی‌کند» می‌توانست بی‌آزمون بماند. اینجا همان مسیرِ
// کاربر را می‌زنیم: دادهٔ تازه می‌آید → همان سلول، عددِ تازه، رنگِ تازه،
// بدونِ رفرش و بدونِ ساختِ دوبارهٔ گره.
describe('TapeTable — ستون‌هایِ متغیر با آمدنِ دادهٔ تازه فلاش می‌زنند', () => {
  const table = (rows: MarketRow[]) =>
    render(<TapeTable rows={rows} selected="" onSelect={() => {}} />);

  // خودِ گرهٔ FlashNum (نه پاکتش): فلاش روی همان اسپنِ `px-1` می‌نشیند.
  const flashCell = (txt: string): HTMLElement => {
    const hits = (Array.from(screen.getAllByText(txt)) as HTMLElement[]).filter((el) =>
      el.classList.contains('px-1'),
    );
    expect(hits).toHaveLength(1);
    return hits[0];
  };

  it('تغییرِ «آخرین» و «حجم» روی همان گره‌ها کلاسِ flash-up می‌گیرد', () => {
    const base = boardRow();
    const { rerender } = table([base]);
    const cellBefore = flashCell('۵٬۱۰۰');
    expect(document.querySelectorAll('.flash-up, .flash-down')).toHaveLength(0);

    rerender(
      <TapeTable
        rows={[boardRow({ p_last: 5250, tvol: 2_500_000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );

    const flashed = document.querySelectorAll('.flash-up');
    // سه ستون از این دو عدد مشتق‌اند: آخرین، حجم، و اختلافِ آخرین/پایانی. اگر
    // FlashNum به جدول وصل نباشد این لیست خالی است و عددِ تازه بی‌صدا جایگزین
    // می‌شود — یعنی همان «flash کار نمی‌کند» که فقط با چشم دیده می‌شد.
    expect(flashed.length).toBeGreaterThanOrEqual(3);
    // گره تخریب نشده: همان نودِ DOM با عددِ تازه.
    expect(flashCell('۵٬۲۵۰').isSameNode(cellBefore)).toBe(true);
    expect(screen.getByText('شپنا')).toBeInTheDocument();
  });

  it('افتِ «آخرین» flash-down می‌گیرد، نه flash-up', () => {
    const base = boardRow({
      symbol: 'فولاد', name: 'فولاد مبارکه', p_closing: 3000, p_last: 3100,
      percent_change: 3, tvol: 900_000,
    });
    const { rerender } = table([base]);
    rerender(
      <TapeTable
        rows={[boardRow({ symbol: 'فولاد', name: 'فولاد مبارکه', p_closing: 3000, p_last: 2950, percent_change: 3, tvol: 900_000 })]}
        selected=""
        onSelect={() => {}}
      />,
    );
    const down = Array.from(document.querySelectorAll('.flash-down')) as HTMLElement[];
    expect(down.some((el) => el.textContent?.includes('۲٬۹۵۰'))).toBe(true);
    // جهتِ اشتباه ممنوع: در افتِ قیمت هیچ سلولی نباید flash-up بگیرد.
    expect(document.querySelectorAll('.flash-up')).toHaveLength(0);
  });

  it('دادهٔ بی‌تغییر در دورِ رأی‌گیریِ بعدی هیچ فلاشی نمی‌زند', () => {
    const { rerender } = table([boardRow()]);
    rerender(
      <TapeTable rows={[boardRow()]} selected="" onSelect={() => {}} />,
    );
    expect(document.querySelectorAll('.flash-up, .flash-down')).toHaveLength(0);
  });
});
