// Walk every tradersarena.ir page the home menu links to and record what it
// actually shows: columns, chart legends, and the JSON endpoints it fetches.
// Public (logged-out) surface only — nothing is typed, stored or read here.
//
//   NODE_PATH="<jev-browser>/package/node_modules" node _audit/ta_walk.js [maxPages]
const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'https://tradersarena.ir';
const MAX = Number(process.argv[2] || 40);
const OUT = '_audit/ta_walk.json';
const CANDIDATES = [
  process.env.TA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

const SEEDS = [
  '/', '/money-flow', '/heatmap/market', '/compare', '/extras/incognito-charts',
  '/extras/tal', '/extras/tops', '/extras/market-values', '/market/histo-status',
  '/extras/long-term-money-flow-filters', '/market-watch-pro', '/market-watch',
  '/pivot-watch', '/signal-watch', '/extras/techno-watch', '/extras/orders-watch',
  '/market/history?type=0', '/market/history?type=1', '/market/history?type=2',
  '/chart/daily/market?type=0', '/market/chart?type=0', '/market/chart?type=1',
  '/market/chart?type=2', '/000/chart/price', '/999/chart/price',
  '/gold-funds/chart/price', '/silver-funds/chart/price', '/leveraged-funds/chart/price',
  '/options-arena', '/options-arena/history', '/options-arena/watch', '/options-arena/strategy',
  '/industries/stock-funds', '/industries/fixed-income-funds', '/industries/leveraged-funds',
  '/industries/gold-funds', '/industries/silver-funds', '/industries/sector-funds',
  '/industries/index-funds', '/industries/mixed-funds', '/industries/classic-stock-funds',
  '/industries/real-state-funds', '/industries/energy-funds', '/industries/fund-in-funds',
  '/industries/57', '/industries/27', '/industries/44',
];

const PROBE = () => {
  const txt = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
  const tables = [...document.querySelectorAll('table')].map((t) => ({
    headers: [...t.querySelectorAll('thead th')].map(txt).filter(Boolean),
    rows: t.querySelectorAll('tbody tr').length,
    sample: [...t.querySelectorAll('tbody tr')].slice(0, 1).flatMap((r) => [...r.querySelectorAll('td')].map(txt)).slice(0, 20),
    visible: !!(t.offsetParent),
  })).filter((t) => (t.headers.length || t.rows) && t.visible);
  const legends = [...new Set([...document.querySelectorAll('.apexcharts-legend-text')]
    .map((e) => txt(e)).filter(Boolean))];
  const chartHeads = [...document.querySelectorAll('.apexcharts-toolbar, .apexcharts-menu')]
    .length;
  const titles = [...document.querySelectorAll('h1,h2,h3,h4,.card-title,.panel-title,.title')]
    .map(txt).filter((s) => s && s.length > 2 && s.length < 70);
  const canvases = document.querySelectorAll('canvas').length;
  const svgs = document.querySelectorAll('svg').length;
  const bodyTxt = document.body ? document.body.innerText : '';
  return {
    url: location.href,
    title: document.title,
    tables, legends, chartHeads, canvases, svgs,
    titles: [...new Set(titles)].slice(0, 30),
    gate: /نیازمند (تهیه )?اشتراک|برای مشاهده این بخش|لطفاً وارد شوید/.test(bodyTxt),
    loginRedirect: /\/login/.test(location.href),
    textLen: bodyTxt.length,
  };
};

(async () => {
  const exe = CANDIDATES.find((p) => fs.existsSync(p));
  const browser = await chromium.launch({ headless: true, executablePath: exe });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, locale: 'fa-IR' });
  const page = await ctx.newPage();
  const results = [];
  const queue = SEEDS.slice();
  const seen = new Set();
  let count = 0;

  while (queue.length && count < MAX) {
    const path = queue.shift();
    if (seen.has(path)) continue;
    seen.add(path);
    count++;
    const calls = [];
    const onRes = (res) => {
      const u = res.url();
      if (u.startsWith(BASE) && /\/data\/|\/api\/|\.json/.test(u)) calls.push(u.replace(BASE, '').split('?')[0]);
    };
    page.on('response', onRes);
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch((e) => calls.push('NAV-FAIL ' + e.message.slice(0, 60)));
    await page.waitForTimeout(4200);
    const view = await page.evaluate(PROBE).catch((e) => ({ error: String(e).slice(0, 120) }));
    page.off('response', onRes);
    const rec = { path, ...view, calls: [...new Set(calls)] };
    results.push(rec);
    const cols = rec.tables ? rec.tables.reduce((m, t) => Math.max(m, t.headers.length), 0) : 0;
    console.log(`${path.padEnd(42)} gate=${rec.gate ? 'Y' : '-'} tables=${(rec.tables || []).length} maxCols=${cols} charts=${(rec.legends || []).length > 0 ? 'legend' : (rec.canvases || 0) + (rec.svgs || 0)} json=${(rec.calls || []).length}`);
  }

  fs.writeFileSync(OUT, JSON.stringify({ fetchedAt: new Date().toISOString(), results }, null, 1));
  console.log(`\n${results.length} صفحه → ${OUT}`);
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
