// رگرسیون چیدمان/پاسخ‌گویی: جدول‌های عریض باید داخل کانتینر خودشان اسکرول شوند
// و کل صفحه را در رزولوشن‌های کوچک از کادر بیرون نزنند (باگِ «اعداد بیرون از ستون/اورفلو»).
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';

function row() {
  return {
    symbol: 'شپنا',
    name: 'پالایش نفت اصفهان',
    sector_name: 'فرآورده‌های نفتی',
    pricing_mode: 'neutral',
    rev_growth: 45.2,
    gross_margin: 22.1,
    profit_potential_pct: 51.0,
    sales_to_mcap: 1.4,
    score: 4,
    excluded: false,
    eps_series: [100, 200, 300],
    i1_pass: true,
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: true,
  } as never;
}

describe('چیدمان پاسخ‌گو — جدول بنیادی', () => {
  it('پنل جدول min-w-0/max-w-full دارد و اسکرول افقی داخل خودِ اسکرول‌کانتینر است', () => {
    const { container } = render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    const panel = container.querySelector('.glass-panel');
    expect(panel?.className).toContain('min-w-0');
    expect(panel?.className).toContain('max-w-full');
    const scroller = screen.getByTestId('fts-screen-scroll');
    expect(scroller.className).toContain('overflow-auto');
    // جدول عرض کمینه دارد ولی درونِ اسکرولر می‌ماند. عددِ کمینه *قید* است، نه
    // سلیقه: روبشِ زنده (ws10) دید درِ viewportِ ۱۳۶۶ با پنلِ نمادِ باز، ظرفِ
    // جدول ۱۱۹۶ پیکسل است و `min-w-[1240px]` همان‌جا ۴۴ پیکسل را پشتِ لبه می‌برد
    // (سرریزِ افقی). پس کمینه باید از تنگ‌ترین ظرفِ واقعی کمتر بماند.
    const table = container.querySelector('table');
    const minW = Number(/min-w-\[(\d+)px\]/.exec(String(table?.className))?.[1] ?? 0);
    expect(minW).toBeGreaterThan(0);
    expect(minW).toBeLessThanOrEqual(1196);
  });

  it('نوار جدول اسلات تنظیمات را می‌پذیرد (بدون عنوان بالای جدول)', () => {
    render(
      <FtsScreenTable
        rows={[row()]}
        onSelect={() => {}}
        settingsSlot={<button data-testid="slot">تنظیمات</button>}
      />,
    );
    expect(screen.getByTestId('slot')).toBeInTheDocument();
    expect(screen.queryByText('دیده‌بان کلان بنیادی — ماتریس ۵ شاخص FTS')).toBeNull();
  });
});
