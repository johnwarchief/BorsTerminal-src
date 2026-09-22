// Number-format + conditional-color audit on the market board and FTS table.
// Checks: Persian digit rendering, sign/percent formatting, red/green color
// consistency vs the sign of the underlying value, and "-" placeholders.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const FA_DIGITS = /[۰-۹]/;

function classifyColor(el) {
  const cls = el.className.toString();
  if (cls.includes('text-accent-red') || cls.includes('text-red')) return 'red';
  if (cls.includes('text-accent-green') || cls.includes('text-green')) return 'green';
  return 'neutral';
}

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

  const market = await page.evaluate(() => {
    const grids = [...document.querySelectorAll('[class*="grid-cols"]')]
      .filter((g) => g.children.length >= 8);
    const rows = grids.slice(1, 12).map((g) => {
      const kids = [...g.children];
      return {
        sym: kids[0].textContent.trim().slice(0, 10),
        price: kids[1].textContent.trim(),
        pct: kids[2].textContent.trim(),
        pctColor: kids[2].className.toString().includes('red') ? 'red'
          : kids[2].className.toString().includes('green') ? 'green' : 'neutral',
        vol: kids[3].textContent.trim(),
        ratio: kids[4].textContent.trim(),
        buy: kids[5].textContent.trim(),
        sell: kids[6].textContent.trim(),
        power: kids[7].textContent.trim(),
      };
    });
    return rows;
  });
  console.log('=== market board rows ===');
  market.forEach((r) => console.log(JSON.stringify(r)));

  // consistency: negative pct must be red, positive must be green
  const bad = market.filter((r) => {
    const neg = r.pct.includes('-');
    return (neg && r.pctColor !== 'red') || (!neg && r.pctColor !== 'green');
  });
  console.log('\ncolor/sign mismatches:', bad.length, JSON.stringify(bad.slice(0, 5)));
  const noFaDigits = market.filter((r) => !FA_DIGITS.test(r.pct) || !FA_DIGITS.test(r.price));
  console.log('cells not using Persian digits:', noFaDigits.length,
    JSON.stringify(noFaDigits.slice(0, 3)));

  // FTS table
  await page.getByRole('button', { name: 'بنیادی' }).click({ timeout: 8000 }).catch(() => {});
  await sleep(4000);
  const fts = await page.evaluate(() => {
    const tbl = document.querySelector('table');
    if (!tbl) return { err: 'no fts table' };
    const rows = [...tbl.querySelectorAll('tbody tr')].filter((r) => r.querySelectorAll('td').length)
      .slice(0, 10).map((r) => {
        const tds = [...r.querySelectorAll('td')];
        const txt = (i) => tds[i] ? tds[i].textContent.replace(/\s+/g, ' ').trim().slice(0, 22) : '';
        return { sym: txt(0), growth: txt(1), eps: txt(2), margin: txt(3), pot: txt(4),
                 industry: txt(5), score: txt(6) };
      });
    return { rows, scrollW: tbl.scrollWidth };
  });
  console.log('\n=== FTS rows ===');
  console.log(JSON.stringify(fts, null, 1));
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
