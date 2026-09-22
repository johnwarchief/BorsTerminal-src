// Login, go to the market (تابلو) tab, and measure its table alignment +
// scroll behaviour. Also checks number formatting and conditional colors.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:8001/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(2500);
  await page.fill('input[type="password"]', 'bors123').catch(() => {});
  await page.fill('input[type="text"]', 'admin').catch(() => {});
  await page.getByRole('button', { name: /ورود/i }).click({ timeout: 8000 }).catch(() => {});
  await sleep(4000);

  // click the market tab
  for (const t of ['تابلو', 'بازار']) {
    try { await page.getByRole('button', { name: t }).first().click({ timeout: 6000 }); break; }
    catch (e) {}
  }
  await sleep(4000);

  const rep = await page.evaluate(() => {
    const out = { tables: [], grids: [] };
    document.querySelectorAll('table').forEach((tbl, ti) => {
      const ths = [...tbl.querySelectorAll('thead th')];
      const rows = [...tbl.querySelectorAll('tbody tr')].filter((r) => r.querySelectorAll('td').length);
      if (!ths.length || !rows.length) return;
      const wrap = tbl.closest('[class*="overflow"]') || tbl.parentElement;
      const row = rows[0];
      const tds = [...row.querySelectorAll('td')];
      out.tables.push({
        table: ti, cols: ths.length, cells: tds.length,
        headers: ths.map((h) => h.textContent.trim().slice(0, 14)),
        values: tds.map((d) => d.textContent.replace(/\s+/g, ' ').trim().slice(0, 14)),
        scrollW: wrap ? wrap.scrollWidth : null, clientW: wrap ? wrap.clientWidth : null,
        tableW: tbl.scrollWidth,
        pairs: ths.slice(0, 12).map((th, i) => {
          const td = tds[i];
          if (!td) return { h: th.textContent.trim().slice(0, 12), mismatch: 'no-cell' };
          const hb = th.getBoundingClientRect(), vb = td.getBoundingClientRect();
          const lo = vb.left - hb.left, ro = hb.right - vb.right;
          return { h: th.textContent.trim().slice(0, 12), leftOff: Math.round(lo),
                   rightOff: Math.round(ro), bad: lo > 6 || ro > 6 || vb.right > hb.right + 1 };
        }),
      });
    });
    // grid-based "tables" (CSS grid, no <table> element)
    document.querySelectorAll('[class*="grid-cols"]').forEach((g, gi) => {
      const kids = [...g.children];
      if (kids.length < 8) return;
      out.grids.push({ grid: gi, cols: kids.length,
        sample: kids.slice(0, 8).map((k) => k.textContent.replace(/\s+/g, ' ').trim().slice(0, 16)),
        scrollW: g.scrollWidth, clientW: g.clientWidth });
    });
    return out;
  });
  console.log(JSON.stringify(rep, null, 1));
  await page.screenshot({ path: '_audit/_shot_market.png' });
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
