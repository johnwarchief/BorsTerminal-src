// FTS table number-format + color audit (retries the tab click).
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

  // the app is a router: sidebar links navigate to /fundamental
  await page.goto('http://localhost:8001/fundamental', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(6000);
  let opened = await page.evaluate(() => !!document.querySelector('table'));
  if (!opened) {
    // session may have been lost by the direct navigation — re-login and retry
    await page.fill('input[type="text"]', 'admin').catch(() => {});
    await page.fill('input[type="password"]', 'bors123').catch(() => {});
    await page.getByRole('button', { name: /ورود/i }).click({ timeout: 8000 }).catch(() => {});
    await sleep(4000);
    await page.goto('http://localhost:8001/fundamental', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(6000);
    opened = await page.evaluate(() => !!document.querySelector('table'));
  }
  if (!opened) { console.log('could not open FTS table'); await browser.close(); return; }

  const rep = await page.evaluate(() => {
    const tbl = document.querySelector('table');
    const wrap = tbl.closest('[class*="overflow"]');
    const rows = [...tbl.querySelectorAll('tbody tr')]
      .filter((r) => r.querySelectorAll('td').length).slice(0, 12);
    return {
      tableW: tbl.scrollWidth, wrapW: wrap ? wrap.clientWidth : null,
      scrollW: wrap ? wrap.scrollWidth : null,
      rowCount: rows.length,
      rows: rows.map((r) => {
        const tds = [...r.querySelectorAll('td')];
        const txt = (i) => tds[i] ? tds[i].textContent.replace(/\s+/g, ' ').trim().slice(0, 24) : '';
        const cls = (i) => tds[i] ? tds[i].className.toString() : '';
        return {
          sym: txt(0), growth: txt(1), growthCls: cls(1).includes('red') ? 'red'
            : cls(1).includes('green') ? 'green' : 'neutral',
          eps: txt(2), margin: txt(3), pot: txt(4), industry: txt(5), score: txt(6),
        };
      }),
    };
  });
  console.log(JSON.stringify(rep, null, 1));

  // growth color must match sign
  const bad = rep.rows.filter((r) => {
    const neg = r.growth.includes('-');
    return (neg && r.growthCls !== 'red') || (!neg && r.growthCls !== 'green' && r.growthCls !== 'neutral');
  });
  console.log('\ngrowth color/sign mismatches:', bad.length, JSON.stringify(bad.slice(0, 4)));
  await page.screenshot({ path: '_audit/_shot_fts2.png' });
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
