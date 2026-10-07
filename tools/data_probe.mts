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
    // Expose useTapeStore if possible
  });
  
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000); 
  
  const funnelEval = await page.evaluate(() => {
    // We can just grab the rows directly from the FTS logic or we can grab the DOM counts for presets!
    // Let's click "Swing" preset and see if it yields rows.
    const getActiveRows = () => {
       const rows = Array.from(document.querySelectorAll('tr[data-fkey]'));
       return rows.map(r => r.getAttribute('data-fkey'));
    };
    return getActiveRows();
  });
  
  // Try preset 'swing'
  await page.locator('[data-testid="funnel-preset-swing"]').click();
  await page.waitForTimeout(1000);
  
  // Expand technical stage to see S -> T flow
  await page.locator('[data-testid="funnel-step-technical"]').click();
  await page.waitForTimeout(500);
  
  const swingEval = await page.evaluate(() => {
    // S -> T logic
    const s_stage = Array.from(document.querySelectorAll('[data-testid="funnel-stage-tape"] tr[data-fkey]')).map(r => r.getAttribute('data-fkey'));
    const t_stage = Array.from(document.querySelectorAll('[data-testid="funnel-stage-technical"] tr[data-fkey]')).map(r => r.getAttribute('data-fkey'));
    
    // Check pending
    const s_pending = Array.from(document.querySelectorAll('[data-testid="funnel-pending-tape"] tr[data-fkey]')).map(r => r.getAttribute('data-fkey'));
    return { s_stage, t_stage, s_pending };
  });
  
  await context.close();
  await browser.close();
  
  writeFileSync('_audit/funnel_real_data.json', JSON.stringify({ funnelEval, swingEval }, null, 2));
  console.log('Real data probe done!');
}

run().catch(console.error);
