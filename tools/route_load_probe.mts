/** tools/route_load_probe.mts — صفحۀ واقعی رویِ یک نشانیِ مشخص بالا می‌آید؟
 *
 * برایِ سنجشِ «نسخۀ Portable» و «کپیِ پچ‌شده» به‌کار می‌رود: همان چک را رویِ هر
 * سرورِ محلی می‌زند. چهار چیز درِ هر route:
 *   • عنصرِ testidِ خودِ صفحۀ مقصد درِ DOM هست (نه فقط آدرسِ عوض‌شده)
 *   • شمارۀ گره‌های DOM از حدِ معقول پایین‌تر نمی‌رود (سفیدیِ SPA را می‌گیرد)
 *   • درخواستِ /api/ شکستِ ۵xx یا ۴xx نداد
 *   • console error جدیدی ثبت نشد
 * بی‌این چهار مورد، «برنامه باز شد» یعنی هیچ‌چیز.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=… node --experimental-strip-types \
 *     tools/route_load_probe.mts --url http://127.0.0.1:8101 --out _audit/tmp/portable_routes
 */
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8101').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/route_load');
const LABEL = arg('label', BASE);

const ROUTES: { hash: string; testid: string; name: string }[] = [
  { hash: '#/market-status', testid: 'market-status-page', name: 'وضعیت بازار' },
  { hash: '#/watch', testid: 'watch-market-workspace', name: 'دیدهبان بازار' },
  { hash: '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF', testid: 'nn-chart-host', name: 'تکنیکال (چارت)' },
  { hash: '#/fundamental', testid: 'fts-screen-row', name: 'بنیادی (غربالگری)' },
  { hash: '#/notifications', testid: 'notifications-page', name: 'مرکز اعلان' },
  { hash: '#/market', testid: 'tape-row', name: 'تابلو' },
];

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
await page.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });

const errors: string[] = [];
const badHttp: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 160)));
page.on('response', (r) => {
  if (r.url().includes('/api/') && r.status() >= 400) badHttp.push(`${r.status()} ${r.url().slice(-70)}`);
});

const rows: { name: string; hash: string; found: boolean; nodes: number; ms: number }[] = [];
for (const r of ROUTES) {
  const t0 = Date.now();
  await page.goto(`${BASE}/${r.hash}`, { waitUntil: 'domcontentloaded' });
  let found = false;
  for (let i = 0; i < 12 && !found; i++) {
    found = await page.evaluate((id) => !!document.querySelector(`[data-testid="${id}"]`), r.testid);
    if (!found) await page.waitForTimeout(1000);
  }
  const nodes = await page.evaluate(() => document.querySelectorAll('*').length);
  rows.push({ name: r.name, hash: r.hash, found, nodes, ms: Date.now() - t0 });
  console.log(`${found ? 'ok  ' : 'FAIL'} ${r.name} (${r.hash}) — گره‌ها: ${nodes}، زمان: ${Date.now() - t0}ms`);
}
const mode = await page.evaluate(async () => {
  try {
    const j = await (await fetch('/api/update/version')).json();
    return { version: j.version, mode: j.mode ?? null, instance: j.instance ?? null };
  } catch { return null; }
});
await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(9000);
await page.screenshot({ path: `${OUT}.png`, fullPage: false });

const checks = [
  { n: 'هر شش route عنصرِ صفحۀ خودش را ساخت', ok: rows.every((x) => x.found), d: rows.map((x) => [x.name, x.found]) },
  // آستانه از خودِ صحنه‌ها گرفته شده، نه حدس: «دیدهبان» درِ حالتِ خالیِ
  // رصد (Stateِ درستِ صفحۀ نو) ۳۴۲ گره دارد؛ پس کفِ ۲۵0 یعنی «سفید نیست».
  { n: 'هیچ صفحۀ سفیدی (هر route > ۲۵۰ گره DOM)', ok: rows.every((x) => x.nodes > 250), d: rows.map((x) => [x.name, x.nodes]) },
  { n: 'درخواست /api/ با ۴xx/۵xx برنگشت', ok: badHttp.length === 0, d: badHttp.slice(0, 6) },
  { n: 'خطای console ثبت نشد', ok: errors.length === 0, d: errors.slice(0, 6) },
];
for (const c of checks) console.log(`${c.ok ? 'PASS' : 'FAIL'}  ${c.n}  ${JSON.stringify(c.d ?? '')}`);
const json = {
  label: LABEL, base: BASE, at: new Date().toISOString(), viewport: '1366x768',
  version: mode, routes: rows,
  passed: checks.filter((c) => c.ok).length, failed: checks.filter((c) => !c.ok).map((c) => c.n),
  checks,
};
writeFileSync(`${OUT}.json`, JSON.stringify(json, null, 2), 'utf8');
console.log(`\n${json.passed}/${checks.length} — ${OUT}.json`);
await browser.close();
