import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = 'http://127.0.0.1:5174/#/master';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();
  
  await context.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true');
  });
  
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000); 
  
  const dom = await page.content();
  mkdirSync('_audit', { recursive: true });
  writeFileSync('_audit/dom_dump.html', dom);
  
  await context.close();
  await browser.close();
  console.log('DOM dumped!');
}

run().catch(console.error);
