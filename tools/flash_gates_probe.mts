/** tools/flash_gates_probe.mts — اثباتِ زندهٔ دروازههایِ فلاش
 *   ۱) prefers-reduced-motion: هیچ فلاشی (تابلو و قهرمان) نباید بدود.
 *   ۲) گاردِ بی‌کاری (data-idle='1'): فلاش باید استثنا باشد و running بماند.
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/flash_gates_probe.mts --url http://127.0.0.1:5173/
 */
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n: string, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/$/, '');
const { chromium } = await imp('node_modules/playwright/index.mjs');

async function names(reduced: boolean, idle: boolean) {
  const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const page = await ctx.newPage();
  await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.num.inline-block', { timeout: 45000 });
  await page.waitForTimeout(1500);
  if (idle) await page.evaluate(() => document.documentElement.setAttribute('data-idle', '1'));
  const out = await page.evaluate(() => {
    const probe = (cls: string) => {
      const s = document.createElement('span');
      s.className = `num inline-block ${cls}`;
      document.body.appendChild(s);
      const name = getComputedStyle(s).animationName;
      const play = document.getAnimations().some((a) => (a as Animation).effect?.target === s)
        ? getComputedStyle(s).animationPlayState : 'n/a';
      s.remove();
      return { name, play };
    };
    return { tape: probe('flash-up'), hero: probe('live-flash-up') };
  });
  await browser.close();
  return out;
}

const rm = await names(true, false);   // کاهشِ حرکت
const idle = await names(false, true); // بی‌کاری
const checks: Array<[string, boolean, unknown]> = [
  ['prefers-reduced-motion: فلاشِ تابلو خاموش', rm.tape.name === 'none', rm.tape],
  ['prefers-reduced-motion: فلاشِ قهرمان خاموش', rm.hero.name === 'none', rm.hero],
  ['بی‌کاری: فلاشِ تابلو استثنا و running', idle.tape.name === 'flash-up' && idle.tape.play === 'running', idle.tape],
  ['بی‌کاری: فلاشِ قهرمان هم running (قبلاً فریز می‌شد = رنگِ گیرکرده)', idle.hero.name === 'flash-up' && idle.hero.play === 'running', idle.hero],
];
let bad = 0;
for (const [n, ok, d] of checks) { console.log(`${ok ? 'PASS' : 'FAIL'} ${n}${ok ? '' : '  ' + JSON.stringify(d)}`); if (!ok) bad++; }
process.exit(bad ? 1 : 0);
