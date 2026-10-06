/**
 * tools/symbol_switch_stress_probe.mts
 * آزمون استرس تعویض سریع نمادها (Rapid Symbol Switching) و مهار Race Condition
 */
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const CHROME = process.env.JEV_CHROME || EDGE;

const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
await page.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {}
});

await page.goto('http://127.0.0.1:5173/#/strategy-tree', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(500);

console.log('--- شروع آزمون تعویض سریع نمادها ---');

// تعویض سریع نمادها با فواصل کوتاه ۵۰ تا ۱۰۰ میلی‌ثانیه
const symbols = ['فولاد', 'شپنا', 'خودرو', 'فملی', 'ذوب'];

for (const sym of symbols) {
  await page.evaluate((s) => {
    // شبیه‌سازی تغییر نماد از طریق استور سراسری
    const win = window as unknown as { __BORS_SET_SYMBOL__?: (sym: string) => void };
    if (win.__BORS_SET_SYMBOL__) {
      win.__BORS_SET_SYMBOL__(s);
    } else {
      // شبیه‌سازی ناوبری یا انتخاب
      window.location.hash = `#/strategy-tree/${encodeURIComponent(s)}`;
    }
  }, sym);
  await page.waitForTimeout(80);
}

// صبر برای تثبیت آخرین نماد ('ذوب')
await page.waitForTimeout(600);

const finalState = await page.evaluate(() => {
  const hash = window.location.hash;
  const bodyText = document.body.textContent || '';
  const hasZob = bodyText.includes('ذوب');
  return { hash, hasZob };
});

console.log(`نتیجه پایانی: هش URL = ${finalState.hash} | نمایش نماد ذوب = ${finalState.hasZob}`);
await browser.close();

if (finalState.hasZob) {
  console.log('OK آزمون تعویض سریع نمادها با موفقیت پاس شد (بدون Race Condition).');
  process.exit(0);
} else {
  console.log('FAIL نماد نهایی تثبیت نشد.');
  process.exit(1);
}
