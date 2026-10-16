// tools/ui_mstat_boot_timing.mjs -- تشخیصِ علتِ تأخیرِ اولینِ /api/mstat (فاز G، بندِ ۵)
//
// آزمونِ زمانِ پاسخ را ضعیف نمی‌کند وِ روشِ سنجشِ آن را عوض نمی‌کند: اینِ فایل فقط
// شاهد می‌گیرد. توالیِ boot باِ آزمونِ اصلی یکی است (goto → login → +۲۰۰۰ms → rebase)،
// ولیِ ساعت ازِ خودِ مرورگر (performance.now) خوانده می‌شود تاِ همهٔ رویدادها رویِ یکِ
// خطِ زمان بمانند؛ آفستِ «به rebase» بعداً ازِ epochِ همانِ لحظه حساب می‌شود.
//
// اجرا: node tools/ui_mstat_boot_timing.mjs --base=http://127.0.0.1:8010 --runs=3
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = /^--([^=]+)=(.*)$/.exec(a);
    return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true];
  })
);
const BASE = args.base || 'http://127.0.0.1:8010';
const RUNS = Number(args.runs || 3);
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const AUTH_SRC = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH_SRC.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH_SRC.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];

// هرِ fetch/XHR رویِ ساعتِ خودِ صفحه ثبت می‌شود +ِ لحظۀِ ناپدیدشدنِ فرمِ ورود،
// نشستنِ خودِ route، وِ عددی‌شدنِ کارتِ شاخص. بی‌هیچِ تغییرِ behavior.
const INIT = `
window.__tl = { api: [], marks: [], state: {} };
const seen = {};
const mark = (k) => { if (!seen[k]) { seen[k] = 1; window.__tl.marks.push({ k, t: Math.round(performance.now()) }); } };
const of_ = window.fetch;
window.fetch = function (u, o) {
  const p = String(typeof u === 'string' ? u : (u && u.url) || '');
  if (p.includes('/api/')) window.__tl.api.push({ p: p.split('?')[0].replace('/api/', ''), q: p.includes('?') ? p.split('?')[1].slice(0, 40) : '', t: Math.round(performance.now()) });
  return of_.apply(this, arguments);
};
const xo = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function (m, u) {
  const p = String(u || '');
  if (p.includes('/api/')) window.__tl.api.push({ p: p.split('?')[0].replace('/api/', ''), t: Math.round(performance.now()) });
  return xo.apply(this, arguments);
};
setInterval(() => {
  try {
    const login = !!document.querySelector('input[type="password"]');
    mark(login ? 'login-screen' : 'login-gone');
    const shell = !!document.querySelector('[data-testid="notifications-page"], [data-testid="market-status-page"], main');
    if (shell && !login) mark('shell-mounted');
    const card = document.querySelector('[data-testid="ms-index-cards-span"]');
    if (card && /[۰-۹]/.test(card.textContent || '')) mark('index-card-numeric');
    const susp = document.querySelector('[data-testid="route-loading"], .animate-pulse');
    if (susp && !login) mark('suspense-fallback-seen');
    const tabs = document.querySelectorAll('[role="tab"]').length;
    if (tabs && !window.__tl.state.tabs) { window.__tl.state.tabs = tabs; mark('tabs-first-seen'); }
  } catch (e) {}
}, 40);
`;

const browser = await chromium.launch({ executablePath: EXE, args: ['--remote-debugging-port=0'] });
const rows = [];

for (let i = 0; i < RUNS; i += 1) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: 'fa-IR', deviceScaleFactor: 1 });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 120)); });
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));
  await page.goto(`${BASE}/#/market-status`, { waitUntil: 'domcontentloaded' });
  if (USER && PASS && await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    await page.locator('input[type="text"]').first().fill(USER);
    await page.locator('input[type="password"]').first().fill(PASS);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2000);
  }
  const rebase = { epoch: Date.now(), origin: await page.evaluate(() => performance.timeOrigin) };
  const dataMs = await (async () => {
    const t = Date.now();
    for (;;) {
      const ok = await page.evaluate(() => {
        const el = document.querySelector('[data-testid="ms-index-cards-span"]');
        return !!el && /[۰-۹]/.test(el.textContent || '');
      });
      if (ok) return Date.now() - t;
      if (Date.now() - t > 12000) return null;
      await page.waitForTimeout(150);
    }
  })();
  const tl = await page.evaluate(() => ({
    api: window.__tl.api,
    marks: window.__tl.marks,
    nav: Math.round((performance.getEntriesByType('navigation')[0] || {}).domContentLoadedEventEnd || 0),
    js: performance.getEntriesByType('resource').filter((r) => r.name.includes('/assets/') && r.name.endsWith('.js'))
      .sort((a, b) => b.responseEnd - a.responseEnd).slice(0, 4)
      .map((r) => `${r.name.split('/').pop()}→${Math.round(r.responseEnd)}ms`),
  }));
  const toRebase = (t) => Math.round(rebase.origin + t - rebase.epoch);
  const mstat = tl.api.filter((a) => a.p.includes('mstat'));
  rows.push({
    run: i + 1,
    firstMstatFromRebase: mstat.length ? toRebase(mstat[0].t) : null,
    indexCardFromRebase: (() => { const m = tl.marks.find((x) => x.k === 'index-card-numeric'); return m ? toRebase(m.t) : null; })(),
    dataMs,
    marks: tl.marks.map((m) => `${m.k}@${m.t}(=${toRebase(m.t)} rel)`),
    apiFromNav: tl.api.slice(0, 22).map((a) => `${a.p}@${a.t}`),
    lastJs: tl.js,
    errs: errs.slice(0, 2),
  });
  await ctx.close();
}
await browser.close();

for (const r of rows) {
  console.log(`── run ${r.run} ──`);
  console.log(`  اولینِ mstat: ${r.firstMstatFromRebase}ms پس ازِ rebase · کارتِ شاخص: ${r.indexCardFromRebase}ms · آزمونِ دیدنی: ${r.dataMs}ms`);
  console.log(`  رویدادها (performance.now = آفست بهِ rebase): ${JSON.stringify(r.marks)}`);
  console.log(`  ترتیبِ پرسش‌ها: ${JSON.stringify(r.apiFromNav)}`);
  console.log(`  دیرترینِ chunk‌ها: ${JSON.stringify(r.lastJs)}`);
  if (r.errs.length) console.log(`  خطا: ${JSON.stringify(r.errs)}`);
}
const ok = rows.filter((r) => r.firstMstatFromRebase != null);
console.log(`\nمیانگینِ اولینِ mstat نسبت بهِ rebase: ${Math.round(ok.reduce((a, r) => a + r.firstMstatFromRebase, 0) / Math.max(1, ok.length))}ms`);
