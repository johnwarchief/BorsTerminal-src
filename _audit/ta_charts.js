// Chart inventory for tradersarena.ir: which charting library, and what each
// mounted chart actually contains (legend, series names, axis labels, range).
// Highcharts objects were not on window during the first pass, so this probes
// the DOM around every canvas/svg instead.
//
//   NODE_PATH="<jev-browser>/package/node_modules" node _audit/ta_charts.js "/"
const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'https://tradersarena.ir';
const target = BASE + (process.argv[2] || '/');
const OUT = '_audit/ta_charts.json';
const CANDIDATES = [
  process.env.TA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

(async () => {
  const exe = CANDIDATES.find((p) => fs.existsSync(p));
  const browser = await chromium.launch({ headless: true, executablePath: exe });
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 1000 }, locale: 'fa-IR' })).newPage();
  await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(8000);

  const dump = await page.evaluate(() => {
    const txt = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');
    const libs = {
      Highcharts: typeof window.Highcharts,
      echarts: typeof window.echarts,
      Chart: typeof window.Chart,
      plotly: typeof window.Plotly,
      amcharts: typeof window.am4core,
      googlecharts: typeof window.google,
      d3: typeof window.d3,
      apexcharts: typeof window.ApexCharts,
      tradingview: typeof window.TradingView,
    };
    const canvasOwners = [...document.querySelectorAll('canvas')].map((c) => {
      let box = c;
      for (let i = 0; i < 6 && box.parentElement; i++) {
        box = box.parentElement;
        if (box.querySelector('h1,h2,h3,h4,.title,.card-title')) break;
      }
      const legends = [...box.querySelectorAll('span,li,.legend *,tspan')]
        .map((e) => txt(e)).filter((s) => s && s.length > 1 && s.length < 28);
      return {
        w: c.width, h: c.height, visible: !!(c.offsetParent),
        containerId: box.id || (box.className || '').toString().slice(0, 50),
        heading: txt(box.querySelector('h1,h2,h3,h4,.title,.card-title')),
        legendWords: [...new Set(legends)].slice(0, 26),
      };
    });
    // svg-based charts (highcharts writes text nodes for axis labels and legend)
    const svgCharts = [...document.querySelectorAll('svg')].filter((s) => s.querySelectorAll('path rect,rect,path').length > 6).map((s) => ({
      cls: (s.getAttribute('class') || '').slice(0, 40),
      texts: [...s.querySelectorAll('text')].map(txt).filter(Boolean).slice(0, 40),
    }));
    const controls = {
      selects: [...document.querySelectorAll('select')].map((s) => ({
        name: s.name || s.id, options: [...s.options].map((o) => o.textContent.trim()).slice(0, 20),
      })),
      ranges: [...document.querySelectorAll('input[type=range],input[type=date]')].map((i) => i.name || i.id || i.type),
      buttons: [...document.querySelectorAll('button')]
        .map((b) => ({ text: txt(b).slice(0, 30), cls: (b.className || '').slice(0, 40) }))
        .filter((b) => b.text).slice(0, 80),
    };
    return { url: location.href, title: document.title, libs, canvasOwners, svgCharts: svgCharts.slice(0, 25), controls };
  });

  fs.writeFileSync(OUT, JSON.stringify(dump, null, 1));
  console.log('libs:', JSON.stringify(dump.libs));
  console.log('canvas:', dump.canvasOwners.length, 'svgCharts:', dump.svgCharts.length);
  for (const c of dump.canvasOwners.slice(0, 20)) {
    console.log(`  #${c.containerId} vis=${c.visible} h="${c.heading}" legend=${c.legendWords.slice(0, 12).join(', ')}`);
  }
  for (const s of dump.svgCharts.slice(0, 12)) console.log('  svg:', s.texts.slice(0, 14).join(' | '));
  console.log('selects:', JSON.stringify(dump.controls.selects).slice(0, 900));
  console.log('saved:', OUT);
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
