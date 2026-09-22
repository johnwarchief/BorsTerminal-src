// Login (admin/bors123), then measure header/value alignment in every table
// on the market tab and the fundamental (FTS) tab.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function measure(page, label) {
  await sleep(3500);
  const report = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('table').forEach((tbl, ti) => {
      const ths = [...tbl.querySelectorAll('thead th')];
      const rows = [...tbl.querySelectorAll('tbody tr')].filter((r) => r.querySelectorAll('td').length);
      if (!ths.length || !rows.length) return;
      const wrap = tbl.closest('[class*="overflow"]') || tbl.parentElement;
      // first and a middle row: alignment must hold for both
      for (const row of [rows[0], rows[Math.min(rows.length - 1, 3)]]) {
        const tds = [...row.querySelectorAll('td')];
        out.push({
          table: ti, rowText: row.textContent.replace(/\s+/g, ' ').slice(0, 40),
          scrollW: wrap ? wrap.scrollWidth : null, clientW: wrap ? wrap.clientWidth : null,
          tableW: tbl.scrollWidth,
          pairs: ths.slice(0, 9).map((th, i) => {
            const td = tds[i];
            if (!td) return { h: th.textContent.trim().slice(0, 12), mismatch: 'no-cell' };
            const hb = th.getBoundingClientRect();
            const vb = td.getBoundingClientRect();
            const leftOff = vb.left - hb.left;
            const rightOff = hb.right - vb.right;
            return {
              h: th.textContent.trim().slice(0, 12),
              v: td.textContent.replace(/\s+/g, ' ').trim().slice(0, 12),
              leftOff: Math.round(leftOff), rightOff: Math.round(rightOff),
              // misaligned = value box not contained in header box (tolerance 6px)
              bad: leftOff > 6 || rightOff > 6 || vb.right > hb.right + 1,
            };
          }),
        });
      }
    });
    return out;
  });
  console.log('=== ' + label + ' ===');
  report.forEach((r) => {
    const bad = r.pairs.filter((p) => p.bad || p.mismatch);
    console.log('table#' + r.table + ' row="' + r.rowText + '" scrollW=' + r.scrollW +
      ' clientW=' + r.clientW + ' tableW=' + r.tableW +
      (bad.length ? '  MISALIGNED: ' + JSON.stringify(bad) : '  aligned OK'));
  });
  if (!report.length) console.log('(no tables rendered)');
  return report;
}

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:8001/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(2500);

  // login
  await page.fill('input[type="text"], input[name="username"], input[autocomplete="username"]', 'admin')
    .catch(() => {});
  await page.fill('input[type="password"]', 'bors123').catch(() => {});
  await page.getByRole('button', { name: /ورود/i }).click({ timeout: 8000 }).catch((e) => {
    console.log('login button issue:', e.message.split('\n')[0]);
  });
  await sleep(4000);
  console.log('after login, tables:', await page.evaluate(() => document.querySelectorAll('table').length));

  await measure(page, 'default/market tab');

  // try to reach the fundamental tab by clicking nav buttons
  const navTexts = await page.evaluate(() =>
    [...document.querySelectorAll('button, [role="tab"]')].map((b) => b.textContent.trim().slice(0, 20)));
  console.log('candidate nav buttons:', JSON.stringify(navTexts.slice(0, 30)));

  for (const t of ['بنیادی', ' fundamental', 'Fundamental', 'دیده‌بان بنیادی', 'اسکرینر']) {
    const el = page.getByRole('button', { name: t }).or(page.getByText(t)).first();
    try {
      await el.click({ timeout: 5000 });
      await sleep(3000);
      console.log('clicked nav: "' + t + '"');
      break;
    } catch (e) { /* try next */ }
  }
  await measure(page, 'fundamental tab');
  await page.screenshot({ path: '_audit/_shot_fts.png' });
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
