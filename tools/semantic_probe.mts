import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = 'http://127.0.0.1:5174/#/master';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();
  
  await context.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true'); localStorage.clear();
  });
  
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000); 
  
  const report: any = { semanticProof: {} };
  
  // Helper to click and get symbols for a stage
  const getStageSymbols = async (stageKey: string) => {
    try {
      await page.locator(`[data-testid="funnel-step-${stageKey}"]`).click();
      await page.waitForTimeout(500); // animation
      const symbols = await page.evaluate((key) => {
        return Array.from(document.querySelectorAll(`[data-testid="funnel-stage-${key}"] tr[data-fkey]`))
          .map(el => el.getAttribute('data-fkey') || '');
      }, stageKey);
      return symbols;
    } catch(e) { return []; }
  };

  const getFunnelState = async (stepName: string) => {
    const tape = await getStageSymbols('tape');
    const technical = await getStageSymbols('technical');
    const fundamental = await getStageSymbols('fundamental');
    const delivery = await getStageSymbols('delivery');
    
    report.semanticProof[stepName] = { tape, technical, fundamental, delivery };
  };
  
  // 1. Initial State (Custom preset)
  // Ensure we are on Custom Preset so we can click chips freely
  const customPreset = page.locator('[data-testid="funnel-preset-custom"]');
  if (await customPreset.count() > 0) {
    await customPreset.click();
    await page.waitForTimeout(500);
  }
  
  await getFunnelState('1_initial_custom');
  
  // 2. Select A (f_susp)
  await page.locator('[data-testid="funnel-tape-chip-f_susp"]').click();
  await page.waitForTimeout(1000);
  await getFunnelState('2_A_only_fsusp');
  
  // 3. Select A + B (f_susp + f_clock)
  await page.locator('[data-testid="funnel-tape-chip-f_clock"]').click();
  await page.waitForTimeout(1000);
  await getFunnelState('3_A_and_B');
  
  // 4. Select A + B + C (f_susp + f_clock + f_roobi)
  await page.locator('[data-testid="funnel-tape-chip-f_roobi"]').click();
  await page.waitForTimeout(1000);
  await getFunnelState('4_A_B_C');
  
  await context.close();
  await browser.close();
  
  mkdirSync('_audit', { recursive: true });
  writeFileSync('_audit/funnel_semantic_proof.json', JSON.stringify(report, null, 2));
  console.log('Semantic probe done!');
}

run().catch(console.error);
