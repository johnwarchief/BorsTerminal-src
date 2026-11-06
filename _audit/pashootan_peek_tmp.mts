// _audit/pashootan_peek_tmp.mts — نگاهیِ مرورگری به PDFِ پاشوتان (صفحه‌هایِ نخست)
import { pathToFileURL } from 'node:url';
const PKG = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await b.newPage();
const f = pathToFileURL('C:/Users/PCMOD/Desktop/BorsTerminal/docs/Technical_Pashootan.pdf').href + '#page=1';
await page.goto(f, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);
const txt = await page.evaluate(() => document.body.innerText.slice(0, 400)).catch(() => '');
console.log('inner-text:', JSON.stringify(txt.slice(0, 200)));
for (const pg of [1, 2, 5]) {
  await page.goto(pathToFileURL('C:/Users/PCMOD/Desktop/BorsTerminal/docs/Technical_Pashootan.pdf').href + `#page=${pg}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `_audit/pashootan_p${pg}.png` });
}
await b.close();
console.log('shots saved');
