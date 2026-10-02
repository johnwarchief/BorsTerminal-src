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

  it('در عمودی، جدول‌هایِ عریض کفِ عرض دارند — و فقط همان‌ها', () => {
    const b = mediaBlock('orientation: portrait');
    // کف باید به‌قدری باشد که هفت ستونِ جدولِ بنیادی له نشوند
    expect(b).toMatch(/fts-screen-scroll'\] table[\s\S]*?min-width:\s*920px/);
    // و قاعده نباید سراسری باشد: جدولِ پنج‌مظنه و ماتریسِ صنایع باریک‌اند
    // و کفِ ۹۲۰ آن‌ها را از پنلِ تنگشان بیرون می‌زند.
    expect(b).not.toMatch(/\n\s*html\.bors-mobile table\s*\{/);
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

describe('گوشیِ افقی', () => {
  it('شرطِ ورود به چیدمانِ موبایل ارتفاع را هم می‌بیند', () => {
    // گوشیِ افقی ۹۱۵×۴۱۲ است؛ با قیدِ «عرض ≤ ۸۲۰» از همهٔ قاعده‌ها بیرون
    // می‌افتاد و چیدمانِ کاملِ دسکتاپ رویِ ۴۱۲ پیکسل ارتفاع می‌نشست.
    expect(css).toMatch(/@media \(max-width: 820px\), \(max-height: 520px\)/);
  });

  it('در افقی نوار به ریلِ عمودیِ باریک برمی‌گردد، نه نوارِ پایین', () => {
    // نوارِ پایین آنجا ۵۸ از ۴۱۲ پیکسل را می‌خورد — ۱۴٪ از چیزی که کم داریم.
    const b = mediaBlock('orientation: landscape');
    expect(b).toMatch(/aside\[data-shell='sidebar'\][\s\S]*?width:\s*52px/);
    expect(b).toMatch(/flex-direction:\s*column/);
  });

  it('در افقی چارت بیشترِ قاب را می‌گیرد', () => {
    expect(mediaBlock('orientation: landscape')).toMatch(/chart-area'\][\s\S]*?min-height:\s*78vh/);
  });
});
