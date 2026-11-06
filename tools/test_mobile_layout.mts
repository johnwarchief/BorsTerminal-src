import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(PKG + '/node_modules/playwright/index.mjs').href);
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });

await page.goto('http://127.0.0.1:5173/#/technical');
await page.waitForTimeout(1000);

const user = await page.$('input[type="text"]');
if (user) {
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'bors123');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
}

await page.goto('http://127.0.0.1:5173/#/technical');
await page.waitForTimeout(3000);

await page.screenshot({ path: '_audit/mobile_layout_1024_auth.png' });
const res = await page.evaluate(() => {
  return document.body.innerHTML;
});
const fs = await import('fs');
fs.writeFileSync('_audit/mobile_layout_1024_auth.html', res);
console.log('Saved');
await browser.close();
