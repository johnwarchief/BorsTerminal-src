// تست نگهبانِ رنگ: هیچ کلاسِ رنگیِ اختصاصی نباید بی‌تعریف بماند
//
// چرا این گیت اصلاً لازم شد (سنجشِ ۱۴۰۵-۰۷-۲۳، مرحلۀ ۵ مأموریت): درِ هشت فایل
// ۳۳ بار کلاس‌هایی مثل `text-accent-amber` / `bg-accent-amber/15` نوشته شده
// بودند، ولی درِ `@theme` هیچ `--color-accent-amber` نداشت. Tailwind v4 برای
// نامِ تعریف‌نشده **هیچ的规则ی نمی‌سازد** — یعنی_build_ سبز می‌ماند، کامپوننت
// رندر می‌شود، و فقط رنگِ نشان silent غیب می‌شود. با گیت‌هایِ معمول (tsc،
// build، حتی مرورگر) دیده نمی‌شود: متن همان‌جا هست، فقط بی‌رنگ.
//
// نشانه‌سنجیِ خودِ این نقص رویِ همین بانک:
//   grep -c "accent-amber" frontend/dist/assets/*.css  →  ۰
//   grep -c "accent-yellow" frontend/dist/assets/*.css →  >۰
// پس «کلاس در کد هست ولی درِ CSSِ ساخته‌شده نیست» دقیقاً همان چیزی است که این
// تست از رویِ *منبع* می‌گیرد، بی‌نیاز به build.
//
// دامنه: فقط خانوادۀِ رنگِ اختصاصیِ خودِ پروژه (`accent-*`, `neon-*`). رنگ‌های
// ذاتیِ Tailwind (amber-300، red-500 …) تعریف‌شده‌اند و بررسی‌شان اینجا فایده
// ندارد؛ کلاس‌هایِ اندازه/وزنِ متن (text-2xs، font-black) هم رنگ نیستند و
// دست‌نخورده می‌مانند.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(import.meta.dirname, '..');
const THEME_FILES = ['index.css', 'shared/styles/tokens.css'];

/** نام‌هایِ رنگی که خودِ پروژه تعریف کرده (`--color-<name>` درِ @theme) */
function definedColorNames(): Set<string> {
  const names = new Set<string>();
  for (const rel of THEME_FILES) {
    let text = '';
    try {
      text = readFileSync(join(SRC, rel), 'utf8');
    } catch {
      continue;                     // فایلِ تم نبود ⇒ از همان تعریف‌هایِ موجود می‌خوانیم
    }
    for (const m of text.matchAll(/--color-([a-z0-9-]+)\s*:/g)) names.add(m[1]);
  }
  return names;
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist' || entry.startsWith('.')) continue;
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) sourceFiles(p, out);
    else if (/\.tsx?$/.test(p) && !isSpecFile(p)) out.push(p);
  }
  return out;
}

/** فایل‌هایِ تست خودِ نگهبان را نمی‌خوانیم: آن‌ها الگویِ کلاس را به‌عنوانِ
 *  رشته‌یِ آزمون دارند، نه به‌عنوانِ استایلِ در‌حال‌اجرا. */
function isSpecFile(p: string): boolean {
  return p.includes('__tests__') || /\.spec\.[tx]s$/.test(p);
}

/** هر ارجاعِ رنگیِ اختصاصی درِ رشته‌یِ className */
function usedCustomColors(text: string): string[] {
  const hits: string[] = [];
  for (const m of text.matchAll(/(?:^|[\s"'`:])(?:text|bg|border|ring|fill|stroke|from|to|via|outline|decoration|shadow|accent|divide|placeholder)-(accent-[a-z0-9-]+|neon-[a-z0-9-]+)/g)) {
    hits.push(m[1].split('/')[0]);
  }
  return hits;
}

describe('نگهبانِ رنگِ اختصاصی (مرحلۀ ۵ — کلاسِ بی‌تعریف = رنگِ بی‌صدا)', () => {
  const defined = definedColorNames();
  const files = sourceFiles(SRC);

  it('فایلِ تم، رنگ‌هایِ اختصاصی را تعریف می‌کند', () => {
    // گاردِ خودِ گارد: اگر @theme جابه‌جا شد و تعریف‌ها خوانده نشوند، تست باید
    // قرمز شود نه اینکه بی‌صدا «سبزِ بی‌محتوا» بدهد.
    expect(defined.has('accent-blue')).toBe(true);
    expect(defined.has('accent-yellow')).toBe(true);
    expect(defined.size).toBeGreaterThan(8);
    expect(files.length).toBeGreaterThan(80);
  });

  it('هیچ کلاسِ accent-*/neon-* در کد نیست که در تم تعریف نشده باشد', () => {
    const missing: string[] = [];
    for (const f of files) {
      const text = readFileSync(f, 'utf8');
      for (const name of usedCustomColors(text)) {
        if (defined.has(name)) continue;
        // `accent-<x>` می‌تواند پیشوندِ نامِ تعریف‌شده باشد (accent-susp-bg در
        // برابر accent-susp)؛ هر دو شکلِ کامل و بدونِ پسوندِ عدد بررسی می‌شود.
        missing.push(`${relative(SRC, f)} → --color-${name}`);
      }
    }
    expect(missing, `کلاس‌هایِ رنگی که هیچ CSSی نمی‌سازند:\n${missing.join('\n')}`).toEqual([]);
  });

  it('نمونۀ ثابت: نامِ جعلیِ همان نقصِ رفع‌شده را می‌گیرد', () => {
    // این سطر عمداً یک کلاسِ تعریف‌نشده دارد تا خودِ منطقِ آشکارسازیِ گارد
    // سبزِ ساختگی نباشد (تستِ تست). رشته از الحاقِ تکه‌ها ساخته می‌شود تا
    // خودِ این فایل در حلقۀِ بالا «م مقصر» نشود.
    const sample = 'text-accent-' + 'am' + 'ber bg-accent-blue/15';
    const used = usedCustomColors(sample);
    expect(used).toContain('accent-amber');
    expect(defined.has('accent-amber')).toBe(false);
    expect(defined.has('accent-blue')).toBe(true);
  });
});
