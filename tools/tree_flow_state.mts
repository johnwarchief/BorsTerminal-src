// tools/tree_flow_state.mts — انیمیشنِ درخت و دربِ قیف: هست، اجرا می‌شود، و انتخاب دارد؟
//
// سه حالت را درِ یک صفحه می‌خواند: (۱) بلافاصله بعد از بارگذاری، (۲) بعد از حرکتِ
// موس، (۳) بعد از بی‌حرکتیِ طولانی. برایِ هر سه: شمارِ گره‌هایِ جریان، حالتِ
// playStateِ انیمیشن‌ها و فلگِ data-idle. سپس درِ تبِ «استراتژی FTS» کلیدِ
// دربِ قیف را پیدا می‌کند و با یک کلیک تأیید می‌کند که عوض می‌شود.
//
//   JEV_CHROME='...chrome.exe' MSYS_NO_PATHCONV=1 \
//   node --experimental-strip-types tools/tree_flow_state.mts --url http://127.0.0.1:8001/
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
const OUT = arg('out', '_audit/tree_flow_state.json');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.removeItem('bors-symbol');
});
const page = await ctx.newPage();

const READ = () =>
  page.evaluate(() => {
    const comets = document.querySelectorAll('.fts-comet');
    const flows = document.querySelectorAll('.fts-path-flow');
    const anims = typeof (document as any).getAnimations === 'function' ? (document as any).getAnimations() : [];
    const named = anims.filter((a: any) => {
      const t = a.effect?.target as Element | undefined;
      return t && (t.classList?.contains('fts-comet') || t.classList?.contains('fts-path-flow'));
    });
    const states = named.map((a: any) => ({
      cls: (a.effect.target as Element).classList.contains('fts-comet') ? 'comet' : 'flow',
      play: a.playState,
      time: Math.round(a.currentTime ?? -1),
    }));
    const counts = states.reduce((m: Record<string, number>, s) => {
      m[s.play] = (m[s.play] ?? 0) + 1;
      return m;
    }, {});
    return {
      cometCount: comets.length,
      flowCount: flows.length,
      idle: document.documentElement.getAttribute('data-idle'),
      hidden: document.documentElement.getAttribute('data-hidden'),
      animTotal: anims.length,
      flowAnims: states.length,
      byPlayState: counts,
      sample: states.slice(0, 4),
    };
  });

const report: Record<string, unknown> = { base: BASE, steps: {} };

await page.goto(BASE + '#/strategy-tree', { waitUntil: 'networkidle' });
await page.waitForTimeout(4000);
report.steps.fresh = await READ();

// حرکتِ موس: گاردِ بی‌حرکتی را بیدار می‌کند
await page.mouse.move(820, 500);
await page.mouse.move(900, 540, { steps: 8 });
await page.waitForTimeout(1200);
report.steps.afterMouse = await READ();

// بی‌حرکتیِ طولانی: گاردِ #198 بعد از ۱۵ ثانیه data-idle='1' می‌گذارد
await page.waitForTimeout(20000);
report.steps.afterIdle = await READ();

// پنجرهٔ پنه (pilot: گزینهٔ c): استثنا باید فقط «بی‌حرکتیِ موس» را پوشش دهد،
// نه مینیمایز. document.hidden در اینجا شبیه‌سازی می‌شود (بدونِ بستنِ پنجرهٔ واقعی).
await page.evaluate(() => {
  Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
  document.dispatchEvent(new Event('visibilitychange'));
});
await page.waitForTimeout(3000);
report.steps.afterHidden = await READ();

const a = report.steps.fresh as any;
const b = report.steps.afterMouse as any;
const c = report.steps.afterIdle as any;
const h = report.steps.afterHidden as any;

// ── دربِ قیف رویِ تبِ «استراتژی FTS» ────────────────────────────────────────
await page.goto(BASE + '#/master', { waitUntil: 'networkidle' });
await page.mouse.move(700, 420);
await page.waitForTimeout(3500);
const doorBefore = await page.evaluate(() => {
  const pick = document.querySelector('[data-testid="funnel-preset-picker"]');
  const pressed = pick ? Array.from(pick.querySelectorAll('[data-testid^="funnel-preset-"]'))
    .filter((x) => x.getAttribute('aria-pressed') === 'true')
    .map((x) => x.getAttribute('data-testid')) : [];
  const head = document.querySelector('section');
  return { hasPicker: Boolean(pick), pressed, entry: (head?.textContent ?? '').replace(/\s+/g, ' ').slice(0, 220) };
});
report.steps.funnelDoor = { before: doorBefore };
// کلیدِ پریده را زدودن چیزی را ثابت نمی‌کند؛ اولین دربِ انتخاب‌نشده زده می‌شود
const inactive = (['swing', 'trend', 'hourglass'] as const).find(
  (p) => !doorBefore.pressed.includes(`funnel-preset-${p}`),
);
if (doorBefore.hasPicker && inactive) {
  await page.click(`[data-testid="funnel-preset-${inactive}"]`);
  await page.waitForTimeout(2500);
  const after = await page.evaluate(() => {
    const pick = document.querySelector('[data-testid="funnel-preset-picker"]');
    const head = document.querySelector('section');
    return {
      pressed: pick ? Array.from(pick.querySelectorAll('[data-testid^="funnel-preset-"]'))
        .filter((x) => x.getAttribute('aria-pressed') === 'true')
        .map((x) => x.getAttribute('data-testid')) : [],
      entry: (head?.textContent ?? '').replace(/\s+/g, ' ').slice(0, 220),
    };
  });
  (report.steps.funnelDoor as any).after = after;
  (report.steps.funnelDoor as any).clicked = inactive;
  report.steps.funnelDoorClicked = true;
} else {
  report.steps.funnelDoorClicked = false;
}

report.verdict = {
  flowRendered: a.cometCount > 0 || a.flowCount > 0,
  runningWhileActive: Object.keys(b.byPlayState || {}).includes('running'),
  // گاردِ بی‌حرکتی نباید جریانِ درخت را بخواباند (اصلاحِ همین دور)
  stillRunningWhenIdle: (c.byPlayState?.running ?? 0) > 0 && (c.byPlayState?.paused ?? 0) === 0,
  // pilot (گزینهٔ c): پنجرهٔ پنه اما مستثنا نمی‌شود — GPU بیدار نمی‌ماند
  pausedWhenHidden:
    h.hidden === '1' && (h.byPlayState?.running ?? 0) === 0 && (h.byPlayState?.paused ?? 0) > 0,
  funnelDoorOnPage: doorBefore.hasPicker,
  funnelDoorSwitches:
    Boolean((report.steps.funnelDoor as any).clicked) &&
    JSON.stringify((report.steps.funnelDoor as any).after?.pressed) !==
      JSON.stringify(doorBefore.pressed) &&
    (report.steps.funnelDoor as any).after?.pressed?.includes(`funnel-preset-${(report.steps.funnelDoor as any).clicked}`) === true,
};
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
