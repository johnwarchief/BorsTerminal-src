// Inventory of tradersarena.ir: every page visited, the JSON endpoints it
// fetched, the tables it rendered and the charts it mounted.
// Driven by the Playwright that ships inside the jev-browser plugin.
//
//   NODE_PATH="<jev-browser>/package/node_modules" node _audit/ta_inventory.js [maxPages]
//
// Public pages only: no credentials are typed, stored or read anywhere here.
const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'https://tradersarena.ir';
const MAX = Number(process.argv[2] || 10);
const OUT = '_audit/ta_inventory.json';
// jev-browser ships Playwright 1.63 but its matching headless-shell build is not
// cached here, so drive the machine's own Chromium-family browser instead.
const CANDIDATES = [
  process.env.TA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

const isJsonish = (u) => /\/data\/|\.json|\/api\/|\/chart\//.test(u);

async function sniffPage(page, url) {
  const calls = [];
  const onResponse = async (res) => {
    const u = res.url();
    if (!u.startsWith(BASE) || !isJsonish(u)) return;
    const len = Number(res.headers()['content-length'] || '0');
    const rec = { url: u.replace(BASE, ''), status: res.status(), bytes: len };
    try {
      const ct = res.headers()['content-type'] || '';
      if (ct.includes('json')) {
        const body = await res.json();
        if (Array.isArray(body)) {
          rec.shape = `array[${body.length}]`;
          if (body.length && typeof body[0] === 'object') rec.itemKeys = Object.keys(body[0]).slice(0, 40);
        } else if (body && typeof body === 'object') {
          rec.keys = Object.keys(body).slice(0, 60);
        }
      }
    } catch (e) { /* body already consumed or not json — keep the URL */ }
    calls.push(rec);
  };
  page.on('response', onResponse);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(4500);

  const view = await page.evaluate(() => {
    const txt = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const tables = [...document.querySelectorAll('table')].map((t) => ({
      headers: [...t.querySelectorAll('thead th, thead td')].map((th) => txt(th)).filter(Boolean).slice(0, 30),
      rows: t.querySelectorAll('tbody tr').length,
      nearestTitle: (() => {
        let p = t;
        for (let i = 0; i < 6 && p; i++) {
          const h = p.previousElementSibling;
          if (h && /h1|h2|h3|h4|caption/.test(h.tagName || '')) return txt(h);
          p = p.parentElement;
        }
        return '';
      })(),
    }));
    const headings = [...document.querySelectorAll('h1,h2,h3,h4,summary,.card-title,.widgettitle')]
      .map((h) => txt(h)).filter((s) => s && s.length < 90).slice(0, 40);
    const canvases = [...document.querySelectorAll('canvas')].length;
    const svgs = [...document.querySelectorAll('svg')].length;
    const chartDivs = [...document.querySelectorAll('[id*=chart i],[class*=chart i],[id*=highcharts i],[data-highcharts-chart]')]
      .map((d) => d.id || d.className).filter(Boolean).slice(0, 30);
    const nav = [...document.querySelectorAll('a[href]')]
      .map((a) => ({ href: a.getAttribute('href'), text: txt(a).slice(0, 40) }))
      .filter((a) => a.href && a.href.startsWith('/') && !/\.(png|jpg|svg|css|js|ico|webp)$/i.test(a.href));
    const loginGate = /ورود|ثبت‌نام|عضویت|اشتراک|درخواست/.test(document.body ? document.body.innerText : '')
      && document.querySelectorAll('table').length === 0;
    return {
      title: document.title,
      url: location.href,
      tables, headings, canvases, svgs, chartDivs,
      nav: nav.slice(0, 120),
      loginGate,
      textLen: document.body ? document.body.innerText.length : 0,
    };
  }).catch((e) => ({ error: String(e).slice(0, 160) }));

  page.off('response', onResponse);
  return { view, calls };
}

(async () => {
  const exe = CANDIDATES.find((p) => fs.existsSync(p));
  const browser = await chromium.launch({ headless: true, executablePath: exe });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'fa-IR' });
  const page = await ctx.newPage();

  const seed = [BASE + '/', BASE + '/market', BASE + '/markets', BASE + '/industry', BASE + '/money-flow'];
  const seen = new Set();
  const pages = [];
  const queue = seed.slice();

  while (queue.length && pages.length < MAX) {
    const url = queue.shift();
    const key = url.replace(/\/+$/, '');
    if (seen.has(key)) continue;
    seen.add(key);
    const { view, calls } = await sniffPage(page, url);
    if (view.error) { pages.push({ url, error: view.error, calls }); continue; }
    pages.push({ url: view.url, title: view.title, ...view, calls });
    console.log(`[${pages.length}] ${view.url}  tables=${view.tables.length} json=${calls.length} canvas=${view.canvases} gate=${view.loginGate}`);
    for (const a of view.nav || []) {
      const abs = BASE + a.href;
      if (!abs.startsWith(BASE)) continue;
      if (/^\/(data|api|dashboard|market|industry|money|flow|chart|report|stat|market-|screen|watch|sector|index|symbol|company|history)/i.test(a.href)
          && !seen.has(abs.replace(/\/+$/, '')) && queue.length < 40) queue.push(abs);
    }
  }

  const endpoints = {};
  for (const p of pages) {
    for (const c of p.calls || []) {
      const e = (endpoints[c.url] = endpoints[c.url] || { url: c.url, seenOn: [], bytes: c.bytes, keys: c.keys || null, itemKeys: c.itemKeys || null, shape: c.shape || null });
      if (!e.seenOn.includes(p.url)) e.seenOn.push(p.url);
    }
  }
  const out = { fetchedAt: new Date().toISOString(), pages, endpoints: Object.values(endpoints).sort((a, b) => a.url.localeCompare(b.url)) };
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log(`\n${pages.length} صفحه، ${out.endpoints.length} اندپوینت → ${OUT}`);
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
