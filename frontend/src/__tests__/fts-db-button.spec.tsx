// دکمهٔ «دیتابیس کدال»: نوارِ پیشرفتِ درونِ دکمه و حالتِ پایان.
// درصد پیش از این فقط متن بود؛ کاربر در دانلودِ چندده‌مگابایتی هیچ حسِ
// حرکتی نداشت. این تست‌ها مواظبِ بست‌شدنِ درصد و عقب‌نگرد‌کردنِ نوارند.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

type Db = { running: boolean; stage: string; percent?: number; error?: string };

// نوارِ ابزار فقط وقتی هست که ردیفی باشد، پس یک ردیفِ کمینه می‌دهیم.
const ROW = {
  symbol: 'فولاد', name: 'فولاد', sector_name: 'صنعت', pricing_mode: 'free',
  rev_growth: 10, gross_margin: 20, sales_to_mcap: 1, profit_potential_pct: 30,
  eps_series: [1, 2], eps_last: 2, eps_data_gap: false, score: 5,
} as unknown as FtsScreenRow;

function paint(dbUpdate: Db | null) {
  return render(
    <FtsScreenTable rows={[ROW]} onSelect={() => {}} onDbUpdate={() => {}} dbUpdate={dbUpdate} />,
  );
}
const bar = () => screen.queryByTestId('fts-db-progress');

describe('نوارِ پیشرفتِ دکمهٔ دیتابیس', () => {
  it('در حالتِ بی‌کار نواری نیست', () => {
    paint(null);
    expect(bar()).toBeNull();
  });

  it('درصدِ دانلود را همان‌قدر عرض می‌دهد', () => {
    paint({ running: true, stage: 'downloading', percent: 42 });
    expect(bar()?.style.width).toBe('42%');
  });

  it('درصدِ خرابِ سرور دکمه را از قاب بیرون نمی‌زند', () => {
    paint({ running: true, stage: 'downloading', percent: 9999 });
    expect(bar()?.style.width).toBe('100%');
  });

  it('درصدِ منفی هم بست می‌شود', () => {
    paint({ running: true, stage: 'downloading', percent: -5 });
    expect(bar()?.style.width).toBe('0%');
  });

  it('در «ادغام» که سرور درصد نمی‌دهد، نوار عقب‌گرد نمی‌کند', () => {
    paint({ running: true, stage: 'merging' });
    expect(bar()?.style.width).toBe('100%');
  });

  it('پایانِ موفق: تیک و متنِ «به‌روز شد»، بی‌نوار', () => {
    paint({ running: false, stage: 'done' });
    expect(screen.getByTestId('fts-db-update').textContent).toContain('به‌روز شد');
    expect(bar()).toBeNull();
  });

  it('خطا حالتِ «به‌روز شد» را نمی‌گیرد', () => {
    paint({ running: false, stage: 'done', error: 'شبکه قطع شد' });
    const b = screen.getByTestId('fts-db-update');
    expect(b.textContent).toContain('خطای دیتابیس کدال');
    expect(b.textContent).not.toContain('به‌روز شد');
  });
});
