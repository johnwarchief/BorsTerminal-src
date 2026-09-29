// tools/tab_anim_probe.mts — «چه چیزی بی‌وقفه انیمیشن می‌خورد؟»
//
// tab_cost_probe رویِ تبِ تابلو ۶۷ انیمیشنِ در حال اجرا و ۲۸۳ بازمحاسبۀ استایل
// در ۱۲ ثانیه دید (بقیۀ تب‌ها ۲ تا ۷ انیمیشن). این ابزار نام/سرایتِ همان
// انیمیشن‌ها را چاپ می‌کند تا معلوم شود کدام یک «بی‌وقفه» است و آیا باید
// با reduced-motion خاموش شود.
//
//   JEV_BROWSER_DIR=... JEV_CHROME=... MSYS_NO_PATHCONV=1 \
//   node --experimental-strip-types tools/tab_anim_probe.mts --url http://127.0.0.1:8001/

import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8001/').replace(/\/+$/, '');
const OUT = arg('out', '_audit/tab_anim.json');
const ROUTE = arg('route', '#/');
const SAMPLES = Number(arg('samples', '2'));
const GAP = Number(arg('gap', '6000'));

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const page = await (await browser.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
await page.goto(`${BASE}/${ROUTE}`, { waitUntil: 'networkidle' }).catch(() => {});
await page.waitForTimeout(6000);

const read = () =>
  page.evaluate(() => {
    const running = document.getAnimations().filter((a) => a.playState === 'running');
    const byName: Record<string, { n: number; sample: string; infinite: number; dur: string }> = {};
    for (const a of running) {
      const anim = a as Animation & { effect?: KeyframeAnimationOptions };
      const target = (anim.effect?.target as HTMLElement) ?? null;
      const nm = anim.animationName ?? (anim as any).id ?? '?';
      const opt = (anim.effect as KeyframeEffect)?.getTiming?.() ?? {};
      const infinite = opt.iterations === Infinity || String(opt.iterations) === 'Infinity' ? 1 : 0;
      const key = `${nm}|${infinite}|${Math.round(Number(opt.duration) || 0)}ms`;
      const g = (byName[key] ??= { n: 0, sample: '', infinite });
      g.n += 1;
      if (!g.sample && target) {
        const cls = (target.className ?? '').toString().slice(0, 60);
        g.sample = `${target.tagName}.${cls}`.slice(0, 90);
      }
    }
    return {
      at: new Date().toISOString().slice(11, 19),
      runningTotal: running.length,
      infiniteTotal: running.filter((a) => {
        const t = (a.effect as KeyframeEffect)?.getTiming?.() ?? {};
        return t.iterations === Infinity;
      }).length,
      byName,
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
  });

const runs = [];
for (let i = 0; i < SAMPLES; i += 1) {
  runs.push(await read());
  if (i + 1 < SAMPLES) await page.waitForTimeout(GAP);
}
await browser.close();
writeFileSync(OUT, JSON.stringify({ base: BASE, route: ROUTE, runs }, null, 1), 'utf8');
for (const r of runs) {
  console.log(`at=${r.at} running=${r.runningTotal} infinite=${r.infiniteTotal} reducedMotion=${r.reducedMotion}`);
  for (const [k, v] of Object.entries(r.byName).sort((a, b) => b[1].n - a[1].n).slice(0, 12)) {
    console.log(`   ${k} n=${v.n} sample=${v.sample}`);
  }
}
console.log('wrote ' + OUT);
