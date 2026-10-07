import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE_URL = 'http://127.0.0.1:5174/#/master';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  // NO CACHE / NEW INCOGNITO CONTEXT
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  
  await context.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true');
  });
  
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000); // wait for load
  
  const bodyText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').substring(0, 300));
  
  await context.close();
  await browser.close();
  
  writeFileSync('_audit/missing_data_probe_report.json', JSON.stringify({ bodyText }, null, 2));
  console.log('Missing data probe done!');
}

run().catch(console.error);
