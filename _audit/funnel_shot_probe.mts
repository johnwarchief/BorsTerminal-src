// _audit/funnel_shot_probe.mts -- تصویرِ مرحلۀ بنیادی در 1366×768 (بعد از اصلاحِ برچسب)
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
await page.goto(arg('url', 'http://127.0.0.1:5173/') + '#/master', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="funnel-stage-fundamental"]', { timeout: 45_000 });
await page.waitForTimeout(9000);
await page.click('[data-testid="funnel-tech-selfcheck"]');
await page.click('[data-testid="funnel-floor-1"]');
await page.waitForTimeout(2500);
const el = page.locator('[data-testid="funnel-stage-fundamental"]');
await el.scrollIntoViewIfNeeded();
await el.screenshot({ path: arg('shot', '_audit/funnel_fundamental_1366_after.png') });
const t = await el.textContent();
console.log('neutral in DOM:', /\bneutral\b/.test(t ?? ''), '| سایر صنایع:', (t ?? '').includes('سایر صنایع'),
  '| ⚠:', (t ?? '').includes('⚠'));
console.log('widths:', JSON.stringify(await page.evaluate(() => {
  const e = document.querySelector('[data-testid="funnel-stage-fundamental"]');
  return { table: e?.scrollWidth, client: e?.clientWidth, doc: document.documentElement.scrollWidth, win: innerWidth };
})));
await browser.close();
