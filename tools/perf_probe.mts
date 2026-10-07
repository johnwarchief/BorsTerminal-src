import { chromium } from 'playwright-core';
import { writeFileSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = 'http://127.0.0.1:5174/#/master';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  
  await context.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true');
    window.performance.mark('nav_start');
  });
  
  const page = await context.newPage();
  
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  
  // Wait for the funnel to render, meaning DB is ready and local initial query is done
  await page.waitForFunction(() => {
    return document.body.innerText.includes('قیفِ غربالگری');
  }, { timeout: 10000 });
  
  const metrics = await page.evaluate(() => {
    window.performance.mark('first_useful_render');
    const perf = window.performance.getEntriesByType('mark');
    const getMark = (name: string) => {
      const m = perf.find(p => p.name === name);
      return m ? m.startTime : null;
    };
    
    // Attempt to extract DB ready time if we added a mark (we might not have)
    // We'll just return standard timing
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    
    return {
      fetchStart: nav.fetchStart,
      domInteractive: nav.domInteractive,
      domComplete: nav.domComplete,
      firstUsefulRender: getMark('first_useful_render'),
    };
  });
  
  await context.close();
  await browser.close();
  
  writeFileSync('_audit/perf_probe_report.json', JSON.stringify(metrics, null, 2));
  console.log('Performance probe done!');
}

run().catch(console.error);
