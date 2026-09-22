// Dump what's actually rendered: body text sample, any table-ish nodes, errors.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => errors.push('PAGEERR: ' + e.message.slice(0, 200)));
  await page.goto('http://localhost:8001/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);

  const snap = await page.evaluate(() => ({
    title: document.title,
    bodyLen: document.body ? document.body.textContent.length : 0,
    bodySample: document.body ? document.body.textContent.replace(/\s+/g, ' ').slice(0, 400) : '',
    tableCount: document.querySelectorAll('table').length,
    divCount: document.querySelectorAll('div').length,
    btnCount: document.querySelectorAll('button').length,
    btnTexts: [...document.querySelectorAll('button')].slice(0, 25).map((b) => b.textContent.trim().slice(0, 20)),
    href: location.href,
  }));
  console.log(JSON.stringify(snap, null, 1));
  console.log('ERRORS:', errors.slice(0, 10).join(' | '));
  await page.screenshot({ path: '_audit/_shot_nav.png' });
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
