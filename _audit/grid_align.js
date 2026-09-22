// The market board renders each ROW as its own CSS grid (grid-cols-11).
// If tracks are auto-sized, a row with wider content shifts every column
// boundary vs the header row -> values no longer sit under their headers.
// This compares child x-edges between the header row and every data row.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:8001/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(2500);
  await page.fill('input[type="text"]', 'admin').catch(() => {});
  await page.fill('input[type="password"]', 'bors123').catch(() => {});
  await page.getByRole('button', { name: /ورود/i }).click({ timeout: 8000 }).catch(() => {});
  await sleep(4000);
  for (const t of ['تابلو', 'بازار']) {
    try { await page.getByRole('button', { name: t }).first().click({ timeout: 6000 }); break; }
    catch (e) {}
  }
  await sleep(4000);

  const rep = await page.evaluate(() => {
    const grids = [...document.querySelectorAll('[class*="grid-cols"]')]
      .filter((g) => g.children.length >= 8);
    if (grids.length < 2) return { err: 'not enough grids', n: grids.length };
    const edges = grids.map((g) => {
      const r = g.getBoundingClientRect();
      return {
        left: Math.round(r.left),
        childEdges: [...g.children].map((c) => {
          const b = c.getBoundingClientRect();
          return { l: Math.round(b.left), r: Math.round(b.right) };
        }),
        cls: g.className.toString().slice(0, 60),
      };
    });
    const header = edges[0];
    const drift = [];
    for (let i = 1; i < Math.min(edges.length, 40); i++) {
      const row = edges[i];
      // compare each column boundary (right edge of child j)
      const diffs = header.childEdges.map((h, j) => {
        const v = row.childEdges[j];
        if (!v) return null;
        return Math.abs(h.r - v.r);
      }).filter((d) => d != null);
      const max = Math.max(...diffs);
      if (max > 2) {
        drift.push({
          row: i, maxDrift: max,
          headerRight: header.childEdges.map((c) => c.r),
          rowRight: row.childEdges.map((c) => c.r),
        });
      }
    }
    return {
      grids: edges.length,
      headerClass: header.cls,
      headerLeft: header.left,
      driftCount: drift.length,
      drift,
    };
  });
  console.log(JSON.stringify(rep, null, 1));
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
