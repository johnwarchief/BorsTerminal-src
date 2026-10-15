// _audit/ui/tab_probe.js — Tab واقعاً فوکوس را جابه‌جا می‌کند؟ کجا گیر می‌کند؟
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/tab_probe.js [--route=/market]
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const NAME = () => {
  const el = document.activeElement; if (!el || el === document.documentElement) return 'html';
  if (el === document.body) return 'body';
  return (el.getAttribute('data-testid') || el.tagName.toLowerCase() + '.' + String(el.className || '').split(/\s+/)[0]) +
    '«' + String(el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 14) + '»';
};
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1000);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click(); await page.waitForTimeout(2200);
  }
  const route = arg('route', '/market');
  await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(1200);
  console.log('قبل ازِ کلیک focus =', await page.evaluate(NAME));
  await page.locator('[data-testid="tape-row"]').first().click();
  await page.waitForTimeout(1400);
  console.log('پس ازِ کلیکِ ردیف focus =', await page.evaluate(NAME));
  console.log('عنصرهایِ inert =', JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('[inert]')].map((e) => e.getAttribute('data-testid') || String(e.className).slice(0, 26)))));
  console.log('count tabbable =', await page.evaluate(() => document.querySelectorAll('a[href],button:not([disabled]),input:not([type=hidden]),select,[tabindex]:not([tabindex="-1"])').length));
  for (let i = 1; i <= 8; i++) { await page.keyboard.press('Tab'); console.log('  Tab#' + i + ' →', await page.evaluate(NAME)); }
  await page.keyboard.press('Shift+Tab'); console.log('  Shift+Tab →', await page.evaluate(NAME));
  const ok = await page.evaluate(() => { const el = document.querySelector('[data-testid="tape-row"]'); el.setAttribute('tabindex', '-1'); el.focus(); return el === document.activeElement; });
  console.log('focus() رویِ ردیف کار کرد؟', ok, '→', await page.evaluate(NAME));
  for (let i = 1; i <= 3; i++) { await page.keyboard.press('Tab'); console.log('  Tab#' + i + ' (ازِ ردیف) →', await page.evaluate(NAME)); }
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
