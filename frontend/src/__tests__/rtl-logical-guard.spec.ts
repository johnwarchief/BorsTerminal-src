// نگهبانِ جهت: کلاسِ فیزیکیِ چپ/راست یا بی‌دلیل نمی‌ماند وِ یا بی‌بازبینی افزوده نمی‌شود
//
// چرا اینِ گیت لازم شد (فاز D): درِ فاز صفر ~۲۰ کلاسِ فیزیکی (`pl-3`, `right-0`,
// `left-1/2` …) شمرده شد، ولی «بی‌شمردنِ بدهی» آن را درست نمی‌کند. دوِ خطرِ جدا هست:
// ۱) نشتِ واقعی: `pl-3` رویِ فهرستِ فارسیِ RTL اصلاً تورفتگی نمی‌سازد (کنارۀِ شروع
//    دست‌نخورده می‌ماند) — پس رابط «باِ تورفتگی» را همان‌طور که ندیده ثابت می‌کند.
// ۲) تبدیلِ کور: هرِ `left` را بهِ `start` بردن، چیزی که درِ RTL یکِ جایِ درست دارد را
//    بهِ سمتِ دیگر می‌بَرَد (کشویِ آف‌کانواس، دستۀِ سوئیچ، جزیرۀِ `dir="ltr"`).
// پس اینِ فایل نه «ممنوعیتِ کامل» می‌گذارد نه بی‌قاعده می‌گذارد: هرِ موردِ بازبینی‌شده
// باِ **دلیل** درِ دفتر ثبت می‌شود، وِ هرِ فیزیکیِ بیرونِ دفتر ⇒ کامیت قرمز.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(import.meta.dirname, '..');

/** همانِ خانواده‌ای که فیزیکی بودنش معنی دارد: لبه، حاشیه/پدینگِ چپ‌راست، ترازِ متن */
const PHYSICAL =
  /(?:^|[\s"'`:])(?:left|right)-(?:full|auto|screen|\[[^\]]+\]|[0-9][\w./%]*)|(?:^|[\s"'`:])[pm][lr]-[0-9.]+|(?:^|[\s"'`:])text-(?:left|right)|(?:^|[\s"'`:])rounded-[lr]\b/g;

/** فایل‌هایِ بازبینی‌شده — کلید: `مسیر|کلاس`. دلیل درِ §پایینِ همینِ فایل. */
const LEDGER = new Set([
  // نقشۀِ `side` اینِ دوِ کامپوننت خودِ API است («ازِ چپِ صفحه باز شو»); درِ RTL هم
  // منظورِ واقعی همانِ لبۀِ فیزیکی است وِ `start` معنا را جابه‌جا می‌کرد.
  'shared/components/ui/tooltip.tsx|left-1/2',
  'shared/components/ui/tooltip.tsx|right-full',
  'shared/components/ui/tooltip.tsx|left-full',
  'shared/components/ui/sheet.tsx|left-0',
  'shared/components/ui/sheet.tsx|right-0',
  'widgets/SymbolInspector.tsx|left-0',
  // نقشۀِ `side` درِ tooltip یکِ جفتِ فیزیکی است (`right-full` + `mr-1.5`): حاشیه
  // «فاصله تاِ خودِ عنصر» است وِ تنها logical‑کردنِ آن، فاصله را بهِ آنِ طرفِ نشانۀ
  // فلش می‌بَرَد. چونِ API خودِ کامپوننت «ازِ چپ/راست» است، هرِ چهارِ سطرِ اینِ جفت
  // درِ همینِ دفتر می‌ماند.
  'shared/components/ui/tooltip.tsx|mr-1.5',
  'shared/components/ui/tooltip.tsx|ml-1.5',
  // بنرِ هشدارِ قیمت `fixed bottom-4 left-16` است: ۶۴px فاصله ازِ لبۀِ چپِ *فیزیکی*
  // تاِ رویِ کشویِ بازرسی (`SymbolInspector.tsx:395`، همانِ left-0ِ بالا) نیفتد.
  // اینِ دوِ موقعیت یکِ جفت‌اند؛ `start-16` بنر را بهِ آنِ طرف، رویِ سایدبار می‌برد.
  'features/technical/nahayatnegar/components/PriceAlertBanner.tsx|left-16',
  // کشو باِ `-translate-x-full` جمع می‌شود؛ `left` وِ `translate-x` یکِ جفت‌اند وِ
  // logical‑کردنِ تنها نیمی ازِ جفت، کشو را بی‌حرکت می‌کرد.
  // نوارهایِ پیشرفت: عنصرِ مادر `dir="ltr"` صریح دارد (سازۀِ عددی، نه متنِ فارسی)،
  // پس `left-0` درِ همانِ جزیرۀِ LTR درست است.
  'features/portfolio/components/DeltaBar.tsx|left-0',
  'features/portfolio/components/DeltaBar.tsx|left-1/2',
  'features/portfolio/components/SectorMatrix.tsx|left-0',
  // `left-1/2` + `translate-x-[-50%]` وسط‌چینِ تقارنی است: جهت ندارد.
  'features/master/ui/MasterVerdictCard.tsx|left-1/2',
  'features/master/ui/MasterVerdictCard.tsx|right-1/2',
  // دستۀِ سوئیچ: دکمۀِ فیزیکیِ چپ↔راست، وِ `left-[18px]` جابه‌جاییِ خودِ دست است.
  'features/fundamental/ui/FtsSettingsDrawer.tsx|left-1',
  'features/fundamental/ui/FtsSettingsDrawer.tsx|left-[18px]',
  // Tooltipِ گوشۀِ بومِ نقشۀِ بازار: جایِ گوشه‌ایِ عمدی وسطِ SVG.
  'features/market/components/MarketTreemap.tsx|left-1',
]);

/** کاراکترهایِ جداکننده درِ الگو (`"`, `'`, ``:``، فاصله) بخشی ازِ تطبیق‌اند وِ درِ کلیدِ
 *  دفتر نباید بیایند، وِگرنه `"'left-1"` باِ `left-1` یکی نمی‌شود. */
function token(raw: string): string {
  return raw.trim().replace(/^[^a-z]+/, '');
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry.startsWith('.')) continue;
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) sourceFiles(p, out);
    else if (/\.tsx?$/.test(p) && !p.includes('__tests__')) out.push(p);
  }
  return out;
}

describe('نگهبانِ جهت (فاز D — دفترِ کلاس‌هایِ فیزیکیِ بازبینی‌شده)', () => {
  const files = sourceFiles(SRC);

  it('منبع را می‌خواند وِ دفترِ بازبینی‌شده‌ها هنوز درِ منبع هست (گاردِ خودِ گارد)', () => {
    expect(files.length).toBeGreaterThan(80);
    const all = new Set<string>();
    for (const f of files) {
      const rel = relative(SRC, f).replace(/\\/g, '/');
      for (const m of readFileSync(f, 'utf8').matchAll(PHYSICAL)) {
        all.add(`${rel}|${token(m[0])}`);
      }
    }
    const stale = [...LEDGER].filter((k) => !all.has(k));
    expect(stale, `درِ دفترِ مواردی ثبت شده که دیگر درِ منبع نیستند (باید حذف شوند تاِ دفتر دروغ نگفت):\n${stale.join('\n')}`).toEqual([]);
  });

  it('هیچِ کلاسِ فیزیکیِ بیرونِ دفتر درِ منبع نیست', () => {
    const offenders: string[] = [];
    for (const f of files) {
      const rel = relative(SRC, f).replace(/\\/g, '/');
      for (const m of readFileSync(f, 'utf8').matchAll(PHYSICAL)) {
        const key = `${rel}|${token(m[0])}`;
        if (!LEDGER.has(key)) offenders.push(key);
      }
    }
    expect(
      offenders,
      `کلاسِ فیزیکیِ بی‌بازبینی — یاِ بهِ logical تبدیلش کن (ps-/pe-/start-/end-/text-start) یاِ باِ دلیل درِ LEDGER ثبتش کن:\n${[...new Set(offenders)].sort().join('\n')}`,
    ).toEqual([]);
  });
});
