import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE_URL = 'http://127.0.0.1:5174/#';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const report: any = { routes: {} };
  
  const routesToTest = ['/market', '/technical', '/fundamental', '/master', '/portfolio'];
  const width = 390;
  
  for (const route of routesToTest) {
    const context = await browser.newContext({ viewport: { width, height: 844 } });
    const page = await context.newPage();
    
    await context.addInitScript(() => {
      sessionStorage.setItem('bors_auth_session', 'true');
    });
    
    let pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('console', msg => { if(msg.type() === 'error') pageErrors.push(msg.text()) });
    
    await page.goto(`${BASE_URL}${route}`, { waitUntil: 'networkidle' });
    
    // allow some time for async local db
    await page.waitForTimeout(3000);
    
    const viewportData = await page.evaluate(() => {
      const de = document.documentElement;
      return {
        w: de.clientWidth,
        h: de.clientHeight,
        overflowX: de.scrollWidth - de.clientWidth
      };
    });
    
    const bodyText = await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').substring(0, 300));
    
    mkdirSync('_audit/nav', { recursive: true });
    await page.screenshot({ path: `_audit/nav/route-${route.replace('/', '')}.png` });
    
    report.routes[route] = {
      viewport: viewportData,
      errors: pageErrors,
      snippet: bodyText
    };
    
    await context.close();
  }
  
  await browser.close();
  writeFileSync('_audit/nav_probe_report.json', JSON.stringify(report, null, 2));
  console.log('Navigation probe done!');
}

run().catch(console.error);
