// _audit/ui/escape_draw.js — میانبرِ Escape برایِ لغوِ ابزارِ رسم کِی کار می‌کند؟
// سه حالتِ فوکوس سنجیده می‌شود: رویِ خودِ دکمۀِ ابزار، رویِ بومِ چارت، و رویِ body.
// usage: node _audit/ui/escape_draw.js
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;

const ACTIVE = () => {
  const items = [...document.querySelectorAll('.tool-item')];
  const on = items.map((e, i) => (e.classList.contains('active') ? i : -1)).filter((i) => i >= 0);
  const ae = document.activeElement;
  return {
    active: on,
    focus: ae ? (ae.className ? ae.tagName.toLowerCase() + '.' + String(ae.className).split(' ')[0] : ae.tagName.toLowerCase()) : null,
    nEscListenersUnknown: null,
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('فولاد'), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(16000);

  const cases = [
    { name: 'focus=tool-button', focusTool: true, canvas: false },
    { name: 'focus=chart-canvas', focusTool: false, canvas: true },
    { name: 'focus=body', focusTool: false, canvas: false },
  ];
  const out = [];
  for (const c of cases) {
    // ابزارِ «خط روند» (#1) را انتخاب می‌کنیم
    await page.locator('.tool-item').nth(1).click();
    await page.waitForTimeout(900);
    const before = await page.evaluate(ACTIVE);
    if (c.canvas) {
      const host = page.locator('[data-testid="nn-chart-host"], .nn-kline-chart, canvas').first();
      await host.click({ position: { x: 30, y: 30 }, timeout: 5000 }).catch(() => {});
    } else if (!c.focusTool) {
      await page.evaluate(() => { document.activeElement && document.activeElement.blur(); });
    }
    const focusNow = await page.evaluate(ACTIVE);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(1200);
    const after = await page.evaluate(ACTIVE);
    out.push({ case: c.name, afterClick: before, beforeEsc: focusNow, afterEsc: after, cancelled: after.active.join() !== before.active.join() });
    // بازگشتِ تمیز: ابزارِ صلیبی را دستی انتخاب کن
    await page.locator('.tool-item').nth(0).click();
    await page.waitForTimeout(600);
  }
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'ESCAPE_DRAW.json'), JSON.stringify({ ranAt: new Date().toISOString(), out, errs }, null, 2));
  for (const r of out) {
    console.log(r.case + '  afterClick.active=' + JSON.stringify(r.afterClick.active) + ' focus=' + r.beforeEsc.focus +
      '  afterEsc.active=' + JSON.stringify(r.afterEsc.active) + '  CANCELLED=' + r.cancelled);
  }
  console.log('console errors=' + errs.length);
  await browser.close();
})();
