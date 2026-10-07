import { chromium } from 'playwright-core';
import { writeFileSync, mkdirSync } from 'node:fs';

const CHROME = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const URL = 'http://127.0.0.1:5174/#/technical/فملی';

async function run() {
  const browser = await chromium.launch({ executablePath: CHROME, headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  
  await context.addInitScript(() => {
    sessionStorage.setItem('bors_auth_session', 'true');
    // Inject a way to set symbol
    window.addEventListener('load', () => {
      // Force symbol
      const setSymbol = (window as any).useSymbolStore?.getState()?.setSymbol;
      if (setSymbol) setSymbol('ÙÙ…Ù„ÛŒ');
    });
  });
  
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000); 
  
  // Try another way to set symbol via UI if store isn't exposed
  try {
    const searchBtn = page.locator('button[aria-label="Ø¬Ø³ØªØ¬Ùˆ"]');
    if (await searchBtn.count() > 0) {
      await searchBtn.first().click();
      await page.keyboard.type('ÙÙ…Ù„ÛŒ');
      await page.waitForTimeout(500);
      await page.keyboard.press('Enter');
    }
  } catch (e) {}
  
  await page.waitForTimeout(4000); // Wait for chart and db
  
  const report: any = {};
  
  // Wait for __TEST_CHART__ to be attached
  try {
    await page.waitForFunction(() => !!(window as any).__TEST_CHART__, { timeout: 10000 });
  } catch (e) {
    console.error("Chart did not mount");
    return;
  }
  
  // Helper to extract visible Y coordinates
  const extractChartScale = async () => {
    return await page.evaluate(() => {
      const chart = (window as any).__TEST_CHART__;
      const dataList = chart.getDataList();
      if (!dataList || dataList.length === 0) return null;
      
      const lastData = dataList[dataList.length - 1];
      
      const yAxisConfig = chart.getStyles().yAxis;
      const scaleType = yAxisConfig.type; 
      
      return {
        scaleType,
        dataLength: dataList.length,
        lastClose: lastData?.close
      };
    });
  };
  
  report.initialLinear = await extractChartScale();
  
  const logBtn = page.locator('text=LOG');
  if (await logBtn.count() > 0) {
    await logBtn.first().click();
    await page.waitForTimeout(500);
    report.afterLogToggle = await extractChartScale();
  }
  
  await context.close();
  await browser.close();
  
  mkdirSync('_audit', { recursive: true });
  writeFileSync('_audit/tech_semantic_proof.json', JSON.stringify(report, null, 2));
  console.log('Tech probe done!');
}

run().catch(console.error);
