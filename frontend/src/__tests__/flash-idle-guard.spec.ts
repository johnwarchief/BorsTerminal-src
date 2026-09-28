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
    const decls = flashClasses.map((cls) => {
      const m = new RegExp(`\\.${cls}\\s*\\{\\s*animation:\\s*([^;]+);`).exec(CSS);
      expect(m, `تعریفِ .${cls}`).not.toBeNull();
      return m![1];
    });
    for (const decl of decls) {
      expect(decl).not.toContain('infinite');
      // مدت دیگر عددِ ثابت نیست: از ریتمِ تازۀِ تابلو می‌آید (flashClock.ts)
      expect(decl, 'مدتِ فلاش به متغیرِ بازۀِ تیک وصل نیست').toContain('var(--bors-flash-dur');
    }
    // هر دو کلاس باید یک مبنایِ مدت داشته باشند، وگرنه بالا/پایین دو ریتم می‌شوند
    expect(new Set(decls.map((d) => d.replace(/\bflash-(up|down)\b/, 'X'))).size).toBe(1);
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

/**
 * جریانِ ستونِ انتخابِ درخت FTS. سنجشِ ۱۴۰۵-۰۷-۰۷ رویِ ۱.۰.۵۳
 * (tools/tree_flow_state.mts، getAnimations): با حرکتِ موس ۴ انیمیشن running بود
 * و ۲۰ ثانیه بعد از آخرین حرکت هر چهار paused — مالک همان‌جا پرسید «چرا انیمیشن
 * را برای درخت FTS حذف کردی؟». کد حذف نشده بود؛ دروازۀ بی‌کاری خوابانده بودش.
 */
const GRAPH = readFileSync(
  path.resolve(import.meta.dirname, '../../src/features/master/components/ObsidianStrategyGraph.tsx'),
  'utf8',
);
const flowClasses = [
  ...new Set([...GRAPH.matchAll(/className="(fts-[a-z-]+)"/g)].map((m) => m[1])),
];

const FLOW_EXEMPT = "html[data-idle='1']:not([data-hidden='1'])";

describe('گاردِ جریانِ درخت و دروازۀ بی‌کاری', () => {
  it('کامپوننت همان دو کلاسی را می‌زند که CSS می‌شناسد', () => {
    expect(flowClasses.slice().sort()).toEqual(['fts-comet', 'fts-path-flow']);
  });

  it('بی‌حرکتیِ موس جریانِ درخت را نمی‌خواباند — درخت همان تبی است که بی‌حرکت نگاهش می‌کنند', () => {
    for (const cls of flowClasses) {
      expect(CSS, `استثنایِ ${cls} در index.css نیست`).toContain(`${FLOW_EXEMPT} .${cls}`);
    }
    const exempt = CSS.slice(CSS.indexOf(FLOW_EXEMPT));
    expect(exempt.slice(0, 300)).toMatch(/animation-play-state:\s*running\s*!important/);
  });

  /**
   * pilot (گزینهٔ c، اطمینان ۰٫۸): استثنایِ کورِ `.fts-*` رویِ پنجرهٔ مینیمایزشده
   * GPU را بیدار نگه می‌داشت؛ همان گاردی که برایِ ۱۲٪ مصرفِ v1.0.26 ساخته شد.
   */
  it('استثنا پنجرهٔ پنه را بی‌کار نمی‌گذارد — قیدِ :not([data-hidden]) سرِ جایش است', () => {
    expect(CSS).not.toMatch(/html\[data-idle='1'\]\s+\.fts-/);
    for (const cls of flowClasses) {
      expect(CSS, `${cls} بی‌قیدِ پنهانی مستثنا شده`).toContain(`${FLOW_EXEMPT} .${cls}`);
    }
  });

  it('کاهشِ حرکت اما هر دو را خاموش می‌کند (دسترس‌پذیری به بهایِ جریان فروخته نمی‌شود)', () => {
    const reduced = CSS.slice(CSS.indexOf('prefers-reduced-motion'));
    for (const cls of flowClasses) expect(reduced).toContain(`.${cls}`);
  });
});
