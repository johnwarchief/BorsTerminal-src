// __tests__/flash-idle-guard.spec.ts — گاردِ #198
// دروازۀ بی‌کاری (idleGate) نباید فلشِ تغییرِ عدد را میخکوب کند.
// اندازه‌گیریِ ۱۴۰۵-۰۷-۰۵ روی برنامۀ در حال اجرا با بازارِ باز: ۱۵ ثانیه بعد از
// آخرین حرکتِ موس `html[data-idle='1']` می‌شود و `animation-play-state: paused`
// تحمیلیِ آن به فلش هم می‌چکید — currentTime روی صفر میخکوب، صفر رویداد
// animationend روی ۱۰۴ فلشِ واقعی. یعنی تابلو در همان حالتی که مالک به آن
// نگاه می‌کند (دست روی موس نیست) هرگز رنگِ تازه‌شدن نمی‌داد. بعد از استثنای
// امروز: ۲۷۸ فلش، ۱۴۰ شروع، ۱۴۰ پایان، میانگین ۱۵۶۷ میلی‌ثانیه.
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const CSS = readFileSync(path.resolve(import.meta.dirname, '../../src/index.css'), 'utf8');
const FLASH = readFileSync(
  path.resolve(import.meta.dirname, '../../src/shared/components/FlashNum.tsx'),
  'utf8',
);

/** کلاس‌هایی که خودِ کامپوننت به سلول می‌چسباند — گارد با منبعِ حقیقت می‌خواند */
const flashClasses = [...FLASH.matchAll(/'(flash-[a-z]+)'/g)].map((m) => m[1]).filter((v, i, a) => a.indexOf(v) === i);

describe('گاردِ فلش و دروازۀ بی‌کاری', () => {
  it('کامپوننتِ سلول همان دو کلاسی را می‌زند که CSS می‌شناسد', () => {
    expect(flashClasses.sort()).toEqual(['flash-down', 'flash-up']);
  });

  it('گاردِ بی‌کاری هنوز همه‌چیز را pause می‌کند (صرفه‌جوییِ GPU حفظ شود)', () => {
    expect(cssHasGlobalIdlePause(CSS)).toBe(true);
  });

  it('ولی فلش از آن مستثنی است — وگرنه number تغییر می‌کند و رنگ دیده نمی‌شود', () => {
    for (const cls of flashClasses) {
      expect(CSS, `استثنایِ ${cls} در index.css نیست`).toContain(`html[data-idle='1'] .${cls}`);
    }
    const exempt = CSS.slice(CSS.indexOf(`html[data-idle='1'] .flash-up`));
    expect(exempt.slice(0, 400)).toMatch(/animation-play-state:\s*running\s*!important/);
  });

  it('فلش یک‌موردی است نه بی‌پایان، و مدتشان یکی است', () => {
    for (const cls of flashClasses) {
      const m = new RegExp(`\\.${cls}\\s*\\{\\s*animation:\\s*([^;]+);`).exec(CSS);
      expect(m, `تعریفِ .${cls}`).not.toBeNull();
      const decl = m![1];
      expect(decl).not.toContain('infinite');
      expect(decl).toMatch(/1\.6s/);
    }
  });

  it('حرکتِ کاهش‌یافته هنوز فلش را خاموش می‌کند (دست‌نخورده ماندنِ دسترس‌پذیری)', () => {
    const reduced = CSS.slice(CSS.indexOf('prefers-reduced-motion'));
    expect(reduced).toContain('.flash-up');
    expect(reduced).toContain('.flash-down');
    expect(reduced.slice(0, 500)).toMatch(/animation:\s*none\s*!important/);
  });
});

function cssHasGlobalIdlePause(css: string): boolean {
  const i = css.indexOf("html[data-idle='1'] *");
  return i >= 0 && css.slice(i, i + 260).includes('animation-play-state: paused !important');
}
