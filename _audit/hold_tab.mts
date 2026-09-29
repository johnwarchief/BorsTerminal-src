// scratch: hold one route open (headless jev chromium) so proc_tree_audit can
// measure the process split while that tab is the active surface.
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? '';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const url = arg('url', 'http://127.0.0.1:8001/');
const seconds = Number(arg('seconds', '70'));
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME || undefined,
});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'networkidle' });
if (arg('route', '')) await page.goto(url + arg('route'), { waitUntil: 'networkidle' });
await page.waitForTimeout(seconds * 1000);
const title = await page.title();
console.log('held', url + arg('route', ''), 'seconds', seconds, 'title', title);
await browser.close();
