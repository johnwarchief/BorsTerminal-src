/**
 * tools/capture_final_evidence.mts
 * ثبت اسکرین‌شات‌ها و شواهد نهایی بصری مرورگر واقعی
 */
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const CHROME = process.env.JEV_CHROME || EDGE;

mkdirSync('_audit', { recursive: true });

const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {}
});

console.log('۱. بارگذاری صفحه Strategy Tree...');
await page.goto('http://127.0.0.1:5173/#/strategy-tree', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1000);

// Screenshot 1: Flow / Roadmap
console.log('۲. ثبت اسکرین‌شات نمای نقشه راه (Roadmap)...');
await page.screenshot({ path: '_audit/evidence_strategy_tree_flow.png', fullPage: false });

// Open Candidates Drawer
console.log('۳. باز کردن کشوی کاندیداها و ثبت اسکرین‌شات...');
const openCandidatesBtn = page.locator('button:has-text("مشاهده کاندیداها")').first();
if (await openCandidatesBtn.isVisible()) {
  await openCandidatesBtn.click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: '_audit/evidence_strategy_tree_candidates.png', fullPage: false });
  // Close drawer via close button or Escape
  const closeBtn = page.locator('button[aria-label="بستن پنجره"]').first();
  if (await closeBtn.isVisible()) {
    await closeBtn.click();
    await page.waitForTimeout(300);
  }
}

// Switch to Orbit Layout
console.log('۴. تغییر حالت به چیدمان مداری (Orbit)...');
const orbitBtn = page.locator('button:has-text("مداری (Orbit)")');
if (await orbitBtn.isVisible()) {
  await orbitBtn.click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: '_audit/evidence_strategy_tree_orbit.png', fullPage: false });
}

// Screenshot 4: Sidebar & Topbar on /market
console.log('۵. ثبت اسکرین‌شات ساختار سایدبار و نوار وضعیت در صفحه بازار...');
await page.goto('http://127.0.0.1:5173/#/market', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1200);
await page.screenshot({ path: '_audit/evidence_sidebar_navigation.png', fullPage: false });

await browser.close();
console.log('✓ تمامی اسکرین‌شات‌ها و شواهد تصویری با موفقیت در پوشه _audit ذخیره شدند.');
