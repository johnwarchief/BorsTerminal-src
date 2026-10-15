// _audit/ui/page_state.js — یکِ route را باز کن وِ بگو چه چیزی واقعاً رسم شد
//
// چرا: گام‌هایِ interact_audit «NO-TRIGGER» می‌گفتند درِ حالی که inventoryِ پیشین
// همانِ testid را دیده بود. بی‌تصویرِ کاملِ DOM وِ خطاهایِ کنسول/شبکه نمی‌شد
// تشخیص داد سلکتور غلط است، داده نیست، یا صفحه درِ حالتِ خطا مانده است.
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/page_state.js --route=/master/فولاد [--grep=funnel|mode] [--wait=25000]
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const ROUTE = arg('route', '/master');
const WAIT = Number(arg('wait', 12000));
const GREP = new RegExp(arg('grep', 'mode|step|search|preset|funnel|analyst'), 'i');

const DUMP = (src) => {
  const re = new RegExp(src, 'i');
  const ids = [...new Set([...document.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid')))];
  const marks = [...document.querySelectorAll('[data-testid]')].filter((e) => re.test(e.getAttribute('data-testid') || ''))
    .map((e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
      return { id: e.getAttribute('data-testid'), tag: e.tagName.toLowerCase(), box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)], vis: cs.display !== 'none' && cs.visibility !== 'hidden' }; });
  return {
    hash: location.hash,
    ids: ids.length,
    matched: marks.slice(0, 20),
    text: String(document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 500),
    scroll: { doc: document.documentElement.scrollHeight, appContent: (document.querySelector('.app-content') || {}).scrollHeight || null },
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [], net = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)); });
  page.on('response', (r) => { if (r.status() >= 400) net.push(r.status() + ' ' + r.url().replace(BASE, '')); });
  page.on('requestfailed', (r) => net.push('FAILED ' + r.url().replace(BASE, '') + ' ' + (r.failure() || {}).errorText));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1000);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click(); await page.waitForTimeout(2200);
  }
  await page.goto(BASE + '/#' + ROUTE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(Math.min(WAIT, 8000));
  if (arg('click', '')) {
    const c = page.locator(arg('click')).first();
    console.error('click ' + arg('click') + ' → found=' + (await c.count()));
    await c.click({ timeout: 8000 }).catch((e) => console.error('click FAILED: ' + String(e).replace(/\s+/g, ' ').slice(0, 160)));
    await page.waitForTimeout(WAIT);
  } else {
    await page.waitForTimeout(WAIT - Math.min(WAIT, 8000));
  }
  const d = await page.evaluate(DUMP, GREP.source);
  console.log(JSON.stringify({ route: ROUTE, ...d, errors: errs.slice(0, 8), network: net.slice(0, 12) }, null, 1));
  fs.mkdirSync(path.join(REPO, '_audit', 'ui', 'shots'), { recursive: true });
  await page.screenshot({ path: path.join(REPO, '_audit', 'ui', 'shots', 'STATE_' + ROUTE.replace(/[^\w]+/g, '_') + '.png') });
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
