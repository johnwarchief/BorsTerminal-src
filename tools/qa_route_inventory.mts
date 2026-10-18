// tools/qa_route_inventory.mts — موجودِ زندهٔ routeها و کنترل‌هایشان، از DOM نه از متنِ کد
//
// فاز ۱ مأموریت QA. دلیلِ وجودش: فهرستِ دستیِ testid‌ها آن چیزی را که نمی‌شناسی
// را اندازه نمی‌گیرد، و شمارشِ `onClick=` در سورس هم نه «کنترل واقعاً رندر می‌شود»
// را ثابت می‌کند نه «این route به کدام صفحه می‌رسد». پس اینجا همان چیزی که مرورگر
// ساخته شمرده می‌شود: تعدادِ دکمه/ورودی/لینکِ دیدنی، عرضِ اسکرولِ افقی، خطای
// console، و اینکه آدرسِ خالیِ برنامه در نهایت رویِ کدام صفحه می‌نشیند.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/qa_route_inventory.mts \
//     --url http://127.0.0.1:5173/ --size 1366x768 --out _audit/qa/route_inventory.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
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
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/qa/route_inventory.json');
const [W, H] = (arg('size', '1366x768') || '1366x768').split('x').map(Number);
const WAIT = Number(arg('wait', '9000'));

// routeها از خودِ routes.tsx خوانده می‌شوند (tools/qa_routes.mts). دلیلِ این
// انتخاب: جدولِ دستیِ clip_audit.mts رویِ main هنوز '#/' را «تابلو» می‌شمرد در
//حالی‌که آن مسیر به /master redirect می‌شود — سه صفحه هرگز سنجیده نشدند و یکِ
// صفحه دو بار. جدولِ دستی هیچ‌وقت باِ کد مقایسه نمی‌شد؛ حالا منبعِ واحد است.
const { readRoutes, redirectTarget } = await import('./qa_routes.mts');
const SPEC = readRoutes('.');
const REDIRECT_TO = redirectTarget('.');
const ROUTES: Array<[string, string, string]> = SPEC.map((r) => [
  r.name,
  r.hash,
  r.kind === 'redirect'
    ? `path "" → باید به ${REDIRECT_TO} برود؛ مقصدِ واقعی ثبت می‌شود`
    : r.kind === 'fallback'
      ? 'fallbackِ route نامعتبر'
      : r.component,
]);
if (SPEC.filter((r) => r.kind === 'page').length < 10) {
  throw new Error(`parser found only ${SPEC.length} routes — the parser is broken, not the app`);
}

const rows: any[] = [];
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: W, height: H }, locale: 'fa-IR' });
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error') consoleErrors.push(String(m.text()).slice(0, 200));
});
page.on('pageerror', (e: any) => consoleErrors.push('pageerror: ' + String(e).slice(0, 200)));

// قفلِ صفحه: بدونِ بازکردنش هر route یک صفحه نشان می‌دهد و شمارشِ کنترل‌ها بی‌معنی
// می‌شود (سنجیده شد: ۱۲ route، هر کدام ۲ دکمه و صفر testid). رمز از محیط می‌آید و
// هیچ‌جا چاپ یا در JSON ثبت نمی‌شود.
async function unlock(): Promise<string> {
  await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(3500);
  const user = process.env.QA_USER || 'admin';
  const pass = process.env.QA_PASS || '';
  const pwd = page.locator('input[type="password"]').first();
  if (!(await pwd.count())) return 'no-login-form';
  const usr = page.locator('input').first();
  await usr.fill(user).catch(() => {});
  await pwd.fill(pass).catch(() => {});
  await page.locator('button', { hasText: /ورود|Login/i }).first().click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(3500);
  if (await page.locator('input[type="password"]').count()) {
    // یک تلاشِ واقعی با رمزِ پیش‌فرضِ خودِ اپ ناموفق بود ⇒ دیگر تلاش نمی‌کنیم
    // (پنج تلاشِ خطا ۳۰ ثانیه قفل می‌کند) و نشست را مستقیم می‌گذاریم.
    await page.evaluate(() => sessionStorage.setItem('bors_auth_session', 'true'));
    await page.goto(BASE, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(3500);
    return (await page.locator('input[type="password"]').count()) ? 'STILL-LOCKED' : 'session-injected';
  }
  return 'form-login';
}
const unlockMode = await unlock();
console.log(`unlock: ${unlockMode}`);

for (const [name, hash, note] of ROUTES) {
  consoleErrors.length = 0;
  const url = BASE.replace(/#.*$/, '') + hash;
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(WAIT);
  const navMs = Date.now() - t0;
  const seen = await page.evaluate(() => {
    const vis = (el: Element) => {
      const r = (el as HTMLElement).getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const q = (sel: string) => Array.from(document.querySelectorAll(sel)).filter(vis).length;
    const de = document.documentElement;
    const heads = Array.from(document.querySelectorAll('h1,h2,h3'))
      .filter(vis)
      .slice(0, 4)
      .map((h) => (h.textContent || '').trim().slice(0, 60));
    const testids = Array.from(document.querySelectorAll('[data-testid]'))
      .filter(vis)
      .map((e) => e.getAttribute('data-testid') as string)
      .slice(0, 400);
    return {
      landedHash: location.hash,
      title: document.title,
      buttons: q('button'),
      links: q('a[href]'),
      inputs: q('input,textarea,select'),
      tablike: q('[role="tab"]'),
      grids: q('table,[role="table"],[role="grid"]'),
      canvas: q('canvas'),
      testids: testids.length,
      testidSample: testids.slice(0, 40),
      heads,
      docScrollW: de.scrollWidth,
      docClientW: de.clientWidth,
      bodyScrollH: document.body.scrollHeight,
      clientH: de.clientHeight,
    };
  });
  rows.push({
    route: name,
    requested: hash,
    note,
    navMs,
    ...seen,
    horizontalOverflow: seen.docScrollW > seen.docClientW + 1,
    consoleErrors: consoleErrors.slice(0, 6),
    consoleErrorCount: consoleErrors.length,
  });
  console.log(
    `${name.padEnd(15)} landed=${seen.landedHash.padEnd(26)} btn=${String(seen.buttons).padStart(3)} ` +
      `inp=${String(seen.inputs).padStart(3)} tab=${String(seen.tablike).padStart(2)} ` +
      `testid=${String(seen.testids).padStart(3)} hOverflow=${seen.horizontalOverflow} ` +
      `err=${seen.consoleErrorCount} ${navMs}ms`
  );
}
await browser.close();

const rootRow = rows.find((r) => r.route === 'root');
const summary = {
  generatedAt: new Date().toISOString(),
  base: BASE,
  viewport: `${W}x${H}`,
  unlock: unlockMode,
  routesFromRouter: SPEC.length,
  pagesInRouter: SPEC.filter((r) => r.kind === 'page').length,
  redirectDeclared: REDIRECT_TO,
  redirectLanded: rootRow ? rootRow.landedHash : null,
  redirectHonoured: rootRow ? rootRow.landedHash === '#' + REDIRECT_TO : null,
  routesRequested: ROUTES.length,
  routesWithConsoleErrors: rows.filter((r) => r.consoleErrorCount > 0).length,
  routesWithHorizontalOverflow: rows.filter((r) => r.horizontalOverflow).length,
  totalVisibleButtons: rows.reduce((a, r) => a + r.buttons, 0),
  totalVisibleInputs: rows.reduce((a, r) => a + r.inputs, 0),
  rows,
};
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(summary, null, 1), 'utf8');
console.log(`\nWROTE ${OUT}`);
