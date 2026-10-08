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

  it('در عمودی، نوارِ مراحلِ قیف و درخت اسکرولِ افقی با کفِ لمسی دارد', () => {
    // بومِ ۱۹۶۰ پیکسلیِ درختِ استراتژی از UI رفته بود و قاعدۀ
    // [data-testid='strategy-canvas-wrap'] مرده ماند (گاردِ
    // mobile-selectors همان را می‌گیرد). کفِ عرضِ واقعیِ امروز، چیپ‌هایِ
    // ۷۲۰/۷۶۰ پیکسلیِ دو نوارِ مرحله است — همان‌ها باید کشیده شوند.
    const b = mediaBlock('orientation: portrait');
    expect(b).toMatch(/fts-process-stepper'[\s\S]*?overflow-x:\s*auto/);
    expect(b).toMatch(/strategy-tree-stepper'[\s\S]*?overflow-x:\s*auto/);
    expect(b).toMatch(/strategy-tree-stepper'\] button[\s\S]*?min-height:\s*44px/);
    expect(b).not.toContain('strategy-canvas-wrap');
  });

  it('اینسپکتورِ موبایل کشو است، نه پوشانندۀ کلِ صفحه', () => {
    // گزارشِ مالک: «وقتی یک نماد را می‌زنی، سایدبار سمتِ چپ کلِ صفحهٔ گوشی
    // را می‌پوشاند» — `width:100vw` رویِ `top-0/bottom-0` می‌نشست و نوارِ
    // ناوبری و سرِ صفحه را می‌خورد.
    const b = mediaBlock('max-width: 820px');
    expect(b).toMatch(/aside\[data-shell='inspector'\][\s\S]*?top:\s*calc\(env\(safe-area-inset-top\)/);
    expect(b).toContain('bottom: calc(58px + env(safe-area-inset-bottom))');
    expect(b).toContain('width: min(100vw, 26rem)');
    // لبه باید صریح بسته باشد: با right:0 هم‌زمان، درِ RTL کشو ۵۲ پیکسل از
    // حالتِ بسته رویِ صفحه جا می‌ماند (کشویِ بسته باید کامل بیرون برود).
    expect(b).toMatch(/aside\[data-shell='inspector'\][\s\S]*?left:\s*0\s*!important/);
    expect(b).toMatch(/aside\[data-shell='inspector'\][\s\S]*?right:\s*auto\s*!important/);
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
