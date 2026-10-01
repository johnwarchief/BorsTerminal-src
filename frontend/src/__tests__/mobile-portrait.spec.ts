// چیدمانِ موبایل — قواعدی که فقط در CSS زندگی می‌کنند و هیچ تستِ رفتاری
// نمی‌بیندشان. اینجا مستقیم از خودِ فایل خوانده می‌شوند تا حذفِ تصادفی
// بی‌صدا نماند.
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

const css = fs.readFileSync('src/shared/styles/mobile.css', 'utf8');
/** بدنهٔ اولین @media ای که همهٔ شرط‌ها را دارد. */
function mediaBlock(...needles: string[]): string {
  const i = css.split('@media').findIndex((b) => needles.every((n) => b.startsWith(n) || b.slice(0, 80).includes(n)));
  return i > 0 ? css.split('@media')[i] : '';
}

describe('چیدمانِ موبایل', () => {
  it('سایدبار در صفحهٔ کوچک به نوارِ پایین می‌رود', () => {
    const b = mediaBlock('max-width: 820px');
    expect(b).toMatch(/aside\[data-shell='sidebar'\][\s\S]*?bottom:\s*0/);
    expect(b).toMatch(/top:\s*auto/);
  });

  it('هدفِ لمسی کمتر از ۴۴ پیکسل نیست', () => {
    expect(css).toMatch(/min-height:\s*44px/);
  });

  it('ناحیهٔ امنِ بالا و پایین هر دو رعایت شده', () => {
    expect(css).toContain('env(safe-area-inset-top)');
    expect(css).toContain('env(safe-area-inset-bottom)');
  });

  it('در عمودی، بومِ درخت کفِ عرض دارد تا برچسب‌ها خوانا بماند', () => {
    // بی‌این، بومِ ۱۹۶۰ پیکسلی در ۴۱۲ پیکسل با مقیاسِ ۰٫۲۱ رسم می‌شد.
    const b = mediaBlock('orientation: portrait');
    // انتخابگر از obsidian-strategy-canvas به strategy-canvas-wrap رفت:
    // کفِ عرض باید رویِ *ظرف* باشد نه خودِ svg، وگرنه نسبتِ ابعاد می‌شکند.
    expect(b).toMatch(/strategy-canvas-wrap'\]\s*\{[\s\S]*?min-width:\s*760px/);
  });

  it('در عمودی، جدول‌ها افقی اسکرول می‌خورند نه اینکه ستون‌ها له شوند', () => {
    expect(mediaBlock('orientation: portrait')).toMatch(/table\s*\{[\s\S]*?min-width:\s*640px/);
  });

  it('در عمودی، نوارِ فیلترها یک ردیفِ کشیدنی است نه چهار ردیفِ شکسته', () => {
    const b = mediaBlock('orientation: portrait');
    expect(b).toMatch(/quick-filters-bar[\s\S]*?flex-wrap:\s*nowrap/);
    expect(b).toMatch(/quick-filters-bar[\s\S]*?overflow-x:\s*auto/);
  });
});

describe('صفحهٔ تکنیکال در گوشی', () => {
  it('سایدبارِ تکنیکال از جریانِ ستون بیرون می‌آید', () => {
    // باگِ اسکرین‌شاتِ ۷: ظرف تا ۱۲۸۰px ستونی است و سایدبار h-full دارد،
    // پس کلِ ارتفاع را می‌خورد و چارت صفر می‌ماند.
    expect(css).toMatch(/technical-sidebar'\]\s*\{[\s\S]*?position:\s*fixed/);
  });

  it('ناحیهٔ چارت کفِ ارتفاع دارد', () => {
    expect(css).toMatch(/chart-area'\]\s*\{[\s\S]*?min-height:\s*62vh/);
  });
});
