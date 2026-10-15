// _audit/ui/shots_after.js — تصویرهایِ «بعد» برایِ سندِ نهایی (برش‌خورده، کم‌حجم)
// سه قاب درِ ۱۳۶۶×۷۶۸ رویِ buildِ نهایی: کاربنچِ تکنیکال، پنلِ اندیکاتورها، درگاهِ ورود.
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/shots_after.js
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
const OUTDIR = path.join(REPO, 'docs', 'ui-audit', 'img');

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  // ۱) درگاهِ ورود (بی‌احراز) — هدفِ لمِ اصلاح‌شده
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  const gate = await page.evaluate(() => {
    const c = document.querySelector('form') || document.body;
    const r = c.getBoundingClientRect();
    return { x: Math.max(0, r.x - 16), y: Math.max(0, r.y - 16), width: Math.min(r.width + 32, innerWidth), height: Math.min(r.height + 32, innerHeight) };
  });
  await page.screenshot({ path: path.join(OUTDIR, 'after-login-gate.png'), clip: gate });

  // ورود برایِ دوِ قابِ بعدی
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }

  // ۲) کاربنچِ تکنیکال: نوارِ ابزارِ wrap شده + چارت
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('فولاد'), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(15000);
  const wb = await page.evaluate(() => {
    const el = document.querySelector('.tv-workbench') || document.querySelector('[data-testid="chart-area"]');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: Math.min(r.width, innerWidth), height: Math.min(r.height, innerHeight) };
  });
  if (wb) await page.screenshot({ path: path.join(OUTDIR, 'after-technical-workbench.png'), clip: wb });

  // ۳) پنلِ اندیکاتورها (باز) — باید تمامش درِ قاب باشد
  await page.locator('button[title="پنل اندیکاتورها"]').first().click();
  await page.waitForTimeout(1500);
  const panel = await page.evaluate(() => {
    const cands = [...document.querySelectorAll('div')].filter((d) => {
      const cs = getComputedStyle(d); const r = d.getBoundingClientRect();
      return cs.position === 'absolute' && r.width > 200 && r.width < 340 && /اندیکاتور/.test(String(d.innerText || '').slice(0, 200));
    });
    const el = cands[0]; if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: Math.min(r.width + 16, innerWidth), height: Math.min(r.height + 16, innerHeight) };
  });
  if (panel) await page.screenshot({ path: path.join(OUTDIR, 'after-indicator-panel.png'), clip: panel });

  await ctx.close(); await browser.close();
  const files = fs.readdirSync(OUTDIR).map((f) => f + ' = ' + Math.round(fs.statSync(path.join(OUTDIR, f)).size / 1024) + 'KB');
  console.log('written to docs/ui-audit/img:\n  ' + files.join('\n  '));
})();
