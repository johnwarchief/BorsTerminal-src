// Full column + chart inventory for one tradersarena.ir page (no cap, no guessing).
// Uses the Playwright bundled with the jev-browser plugin.
//
//   NODE_PATH="<jev-browser>/package/node_modules" node _audit/ta_detail.js <path>
//
const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'https://tradersarena.ir';
const target = BASE + (process.argv[2] || '/');
const OUT = '_audit/ta_detail' + (process.argv[2] || '/').replace(/[^a-z0-9]+/gi, '_') + '.json';

const CANDIDATES = [
  process.env.TA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

(async () => {
  const exe = CANDIDATES.find((p) => fs.existsSync(p));
  const browser = await chromium.launch({ headless: true, executablePath: exe });
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, locale: 'fa-IR' });
  const page = await ctx.newPage();
  const calls = [];
  page.on('response', (res) => {
    const u = res.url();
    if (u.startsWith(BASE) && /\/data\/|\.json|\/api\/|\/chart\//.test(u)) {
      calls.push({ url: u.replace(BASE, ''), status: res.status() });
    }
  });

  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch((e) => console.log('nav:', e.message.slice(0, 90)));
  await page.waitForTimeout(7000);

  const dump = await page.evaluate(() => {
    const txt = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const tables = [...document.querySelectorAll('table')].map((t) => {
      const heads = [...t.querySelectorAll('thead th')].map(txt).filter(Boolean);
      const firstRow = [...t.querySelectorAll('tbody tr')].slice(0, 1)
        .flatMap((r) => [...r.querySelectorAll('td')].map(txt));
      return {
        id: t.id || '',
        cls: (t.className || '').slice(0, 60),
        headers: heads.length ? heads : [...t.querySelectorAll('tr')].slice(0, 1).flatMap((r) => [...r.querySelectorAll('th')].map(txt)),
        sampleRow: firstRow.slice(0, 24),
        rows: t.querySelectorAll('tbody tr').length,
        visible: !!(t.offsetParent),
      };
    }).filter((t) => t.headers.length || t.rows);

    // Every chart the page mounted: Highcharts keeps the live objects.
    let charts = [];
    const HC = window.Highcharts;
    if (HC && typeof HC.charts !== 'undefined') {
      charts = [...HC.charts].filter(Boolean).map((c) => ({
        type: c.options && c.options.chart && c.options.chart.type,
        title: c.options && c.options.title && c.options.title.text,
        yAxis: (c.yAxis || []).map((a) => a.options && a.options.title && a.options.title.text).filter(Boolean),
        series: (c.series || []).map((s) => ({ name: s.name, points: s.data ? s.data.length : 0 })),
        range: c.xAxis && c.xAxis[0] && c.xAxis[0].title ? c.xAxis[0].title.text : '',
      }));
    }
    const tabs = [...document.querySelectorAll('[role=tab], .nav-tabs a, .tablinks, ul.tabs li, .mat-tab-label, .tab')].map(txt).filter((s) => s && s.length < 40);
    const menus = [...document.querySelectorAll('a[href]')]
      .map((a) => ({ href: a.getAttribute('href'), text: txt(a).slice(0, 44) }))
      .filter((a) => a.href && a.href.startsWith('/') && a.text);
    const gate = /نیازمند (تهیه )?اشتراک/.test(document.body.innerText);
    return { url: location.href, title: document.title, tables, charts, tabs: [...new Set(tabs)], menus, gate, textLen: document.body.innerText.length };
  });

  dump.calls = calls;
  fs.writeFileSync(OUT, JSON.stringify(dump, null, 1));
  console.log(target, '→ tables:', dump.tables.length, 'charts:', dump.charts.length, 'json:', calls.length, 'gate:', dump.gate);
  console.log('saved:', OUT);
  if (dump.tabs.length) console.log('tabs:', dump.tabs.join(' | '));
  for (const t of dump.tables) console.log(`  table rows=${t.rows} visible=${t.visible} cols=${t.headers.length}: ${t.headers.join(' / ').slice(0, 200)}`);
  for (const c of dump.charts) console.log(`  chart «${c.title || '-'}» type=${c.type} series=${c.series.map((s) => s.name + '(' + s.points + ')').join(', ')}`);
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
