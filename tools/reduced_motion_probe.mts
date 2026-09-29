// tools/reduced_motion_probe.mts — این ماشین به Chromium چه می‌گوید؟
//
// چرا: انیمیشنِ درخت دو در دارد. درِ CSS زیرِ `prefers-reduced-motion: reduce`
// مدتِ *همه* انیمیشن‌ها را ۰٫۰۱ms می‌کند — یعنی play-state همان «running» می‌ماند
// و دیده نمی‌شود. سنجشِ ۱٫۰٫۵۴ دقیقاً همین را نمی‌دید (playState می‌خواند)، پس
// «سبز» بود درحالی‌که رویِ صفحه چیزی تکان نمی‌خورد. اینجا خودِ مقدارِ media query
// و مدتِ واقعیِ انیمیشن خوانده می‌شود.
//
//   JEV_CHROME='...' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/reduced_motion_probe.mts --url http://127.0.0.1:8001/
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
const BASE = arg('url', 'http://127.0.0.1:8001/');
const ROUTE = arg('route', '#/strategy');
const OUT = arg('out', '_audit/reduced_motion_probe.json');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
// --reduced = همان چیزی که پنجرۀ بومی (WebView2) وقتی «افکت‌هایِ انیمیشنِ»
// ویندوز خاموش است به صفحه می‌دهد. headless به‌طورِ پیش‌فرض این را از OS
// نمی‌خواند، پس بدونِ این کلید نمی‌توان معلولِ مالک را دید.
const REDUCED = process.argv.includes('--reduced');
const ctx = await browser.newContext({
  viewport: { width: 1632, height: 950 },
  ...(REDUCED ? { reducedMotion: 'reduce' as const } : {}),
});
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
await page.goto(BASE + ROUTE, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

const read = async () =>
  page.evaluate(() => {
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const noPref = matchMedia('(prefers-reduced-motion: no-preference)').matches;
    const out: any[] = [];
    for (const sel of ['.fts-path-flow', '.fts-comet', '.animate-spin-slow']) {
      const els = Array.from(document.querySelectorAll(sel)).slice(0, 3);
      for (const el of els) {
        const cs = getComputedStyle(el as Element);
        out.push({
          sel,
          animationName: cs.animationName,
          duration: cs.animationDuration,
          playState: cs.animationPlayState,
          iteration: cs.animationIterationCount,
          display: cs.display,
          opacity: cs.opacity,
          rect: (el as HTMLElement).getBoundingClientRect().width + 'x' +
                (el as HTMLElement).getBoundingClientRect().height,
        });
      }
      if (!els.length) out.push({ sel, missing: true });
    }
    return {
      reduce,
      noPref,
      idleAttr: document.documentElement.dataset.idle ?? null,
      hiddenAttr: document.documentElement.dataset.hidden ?? null,
      treeFlow: document.documentElement.dataset.treeFlow ?? null,
      treeFlowRunning: document.documentElement.dataset.treeFlowRunning ?? null,
      animations: out,
      treeSvgCount: document.querySelectorAll('svg').length,
    };
  });

const before = await read();
// حرکتِ موس: درِ data-idle را باز می‌کند
await page.mouse.move(700, 400);
await page.waitForTimeout(600);
const afterMove = await read();

// کنترلِ تازه: تنظیمِ درون‌برنامه باید هر دو جهت را کار کند
async function shot() {
  return (await page.screenshot({ type: 'png' })).toString('base64');
}
const motion = async (label: string) => {
  const a = await shot();
  await page.waitForTimeout(1200);
  const b = await shot();
  return { label, pixelsChanged: a !== b, ...(await read()) };
};

const flowCtl = await page.locator('[data-testid="tree-flow-toggle"]').count();
const states: any[] = [{ mode: '(initial)', ...(await motion('initial')) }];
if (flowCtl) {
  await page.locator('[data-testid="tree-flow-off"]').click();
  await page.waitForTimeout(800);
  states.push({ mode: 'off', ...(await motion('off')) });
  await page.locator('[data-testid="tree-flow-always"]').click();
  await page.waitForTimeout(800);
  states.push({ mode: 'always', ...(await motion('always')) });
}

// بی‌حرکتیِ طولانی: حالتِ واقعیِ تماشایِ بی‌دست
await page.waitForTimeout(35000);
const idle = await read();

// دو فریمِ واقعی: اگر چیزی تکان نخورد، diff صفر است
const result = { url: BASE, route: ROUTE, reducedEmulation: REDUCED,
                 before, afterMove, idle, states };
writeFileSync(OUT, JSON.stringify(result, null, 1));
const brief = (s: any) => ({
  mode: s.mode,
  reduce: s.reduce,
  treeFlow: s.treeFlow, running: s.treeFlowRunning,
  pathFlow: (s.animations.find((a: any) => a.sel === '.fts-path-flow') || {}).animationName,
  pathFlowDuration: (s.animations.find((a: any) => a.sel === '.fts-path-flow') || {}).duration,
  cometsPresent: !(s.animations.find((a: any) => a.sel === '.fts-comet') || {}).missing,
  pixelsChanged: s.pixelsChanged,
});
console.log(JSON.stringify({ reducedEmulation: REDUCED,
                            states: states.map(brief),
                            afterIdle: brief({ mode: 'idle', ...idle,
                                               pixelsChanged: undefined }) }, null, 1));
await browser.close();
