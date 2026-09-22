// Discover the real nav labels + which tables exist on each tab.
const { chromium } = require('playwright-core');
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
  const browser = await chromium.launch({ executablePath: EDGE, headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:8001/', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);

  const nav = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('button, a, [role="tab"]').forEach((el) => {
      const t = (el.textContent || '').trim();
      if (t && t.length < 24 && (el.getAttribute('role') === 'tab' ||
          el.closest('nav') || el.className.toString().includes('nav'))) {
        out.push({ tag: el.tagName, text: t, cls: (el.className || '').toString().slice(0, 60) });
      }
    });
    return out;
  });
  console.log('NAV:', JSON.stringify(nav, null, 1));

  const tables = await page.evaluate(() =>
    [...document.querySelectorAll('table')].map((t) => {
      const ths = [...t.querySelectorAll('thead th')].map((h) => h.textContent.trim());
      return { cols: ths, rows: t.querySelectorAll('tbody tr').length };
    }));
  console.log('TABLES on default tab:', JSON.stringify(tables, null, 1));
  await browser.close();
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
