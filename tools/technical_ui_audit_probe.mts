/**
 * tools/technical_ui_audit_probe.mts
 * Probe for Technical UI/UX and browser behavior audit
 */
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const BASE = 'http://127.0.0.1:5173/';

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const CHROME = process.env.JEV_CHROME || EDGE;

const results: { name: string; ok: boolean; detail?: unknown }[] = [];
const push = (name: string, ok: boolean, detail?: unknown) => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok ? '' : ' :: ' + JSON.stringify(detail).slice(0, 200)}`);
};

async function runAudit() {
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const viewports = [
    { width: 1280, height: 720 },
    { width: 1366, height: 768 },
    { width: 1600, height: 900 },
    { width: 1920, height: 1080 }
  ];

  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.width}x${vp.height}`);
    const context = await browser.newContext({ viewport: vp });
    const page = await context.newPage();
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem('bors_auth_session', 'true');
      } catch {}
    });

    try {
      await page.goto(`${BASE}#/technical`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2000);

      // 1. Check if chart canvas exists
      const hasCanvas = await page.evaluate(() => {
        const canvases = document.querySelectorAll('canvas');
        return canvases.length > 0;
      });
      push(`Canvas exists (${vp.width}x${vp.height})`, hasCanvas);

      // 2. Check layout overlapping (sidebar vs main chart area)
      const layoutOverlap = await page.evaluate(() => {
        const sidebar = document.querySelector('aside');
        const main = document.querySelector('main');
        if (!sidebar || !main) return { overlap: false, missing: true };
        const sRect = sidebar.getBoundingClientRect();
        const mRect = main.getBoundingClientRect();
        const overlap = !(sRect.right <= mRect.left || sRect.left >= mRect.right);
        return { overlap, sRect: sRect.toJSON(), mRect: mRect.toJSON() };
      });
      push(`No Sidebar/Main overlap (${vp.width}x${vp.height})`, !layoutOverlap.overlap && !layoutOverlap.missing, layoutOverlap);

      // 3. Timeframe controls check
      const hasTimeframes = await page.evaluate(() => {
        const texts = Array.from(document.querySelectorAll('button, span, div')).map(el => el.textContent || '');
        return texts.some(t => t.includes('D') || t.includes('W') || t.includes('M')); // Checking for D/W/M or equivalents
      });
      push(`Timeframe controls visible (${vp.width}x${vp.height})`, hasTimeframes);
      
      // We can also take screenshots for manual review later
      await page.screenshot({ path: `_audit/technical_${vp.width}x${vp.height}.png` });

    } catch (err: any) {
      push(`Execution failed (${vp.width}x${vp.height})`, false, err.message);
    } finally {
      await context.close();
    }
  }

  await browser.close();
  const failed = results.filter(r => !r.ok).length;
  console.log(`\nTotal failures: ${failed}`);
  process.exit(failed ? 1 : 0);
}

runAudit().catch(console.error);
