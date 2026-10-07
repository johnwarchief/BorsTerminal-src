import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = 'http://127.0.0.1:5174/#/master';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const report: any = { views: {} };
  
  for (const width of [390, 768, 1366]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    
    // Auth bypass
    await context.addInitScript(() => {
      sessionStorage.setItem('bors_auth_session', 'true');
    });
    
    await page.goto(URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000); // wait for DB and Funnel to load
    
    console.log(`Testing width ${width}...`);
    
    const viewportData = await page.evaluate(() => {
      const de = document.documentElement;
      return {
        w: de.clientWidth,
        h: de.clientHeight,
        overflowX: de.scrollWidth - de.clientWidth
      };
    });
    
    const funnelActive = await page.locator('text=قیفِ غربالگری FTS').count() > 0 || await page.locator('text=تعداد نماد').count() > 0;
    const bodyText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').substring(0, 1000));
    
    // Try to open Funnel explicitly if it's hidden behind a button
    // Actually MasterPage shows Funnel if no symbol is selected.
    
    mkdirSync('_audit', { recursive: true });
    await page.screenshot({ path: `_audit/funnel-${width}.png` });
    
    report.views[width] = {
      viewport: viewportData,
      funnelVisible: funnelActive,
      textSnippet: bodyText
    };
    
    await context.close();
  }
  
  await browser.close();
  writeFileSync('_audit/funnel_probe_report.json', JSON.stringify(report, null, 2));
  console.log('Done!');
}

run().catch(console.error);
