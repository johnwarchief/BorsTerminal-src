/**
 * tools/round79_live_probe.mts — اثباتِ زندهٔ P0 دورِ تحقیق UX
 *   الف) Ctrl+K پالتِ سه‌شیار را باز می‌کند (نماد/صفحه/فرمان)
 *   ب) فرمان «تغییر پوسته» واقعاً data-theme را عوض می‌کند و برمی‌گرداند
 *   ج) تبِ قیف، اسکرول را به کارتِ همان مرحله می‌برد
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types tools/round79_live_probe.mts \
 *     --url http://127.0.0.1:8002/ --out _audit/round79_live.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/round79_live.json');
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) {
  const { ensureChromium } = await imp('src/browser-setup.ts');
  await ensureChromium();
}

const results: Record<string, unknown> = { base: BASE, checks: [] as Record<string, unknown>[] };
const push = (name: string, ok: boolean, detail: unknown) => {
  (results.checks as Record<string, unknown>[]).push({ name, ok, detail });
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok ? '' : ' :: ' + JSON.stringify(detail).slice(0, 200)}`);
};

const browser = await chromium.launch({
  executablePath: CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
await page.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه */
  }
});

await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: 40000 });

// الف+ب) پالت سه‌شیار و فرمانِ واقعیِ پوسته
await page.keyboard.press('Control+k');
await page.waitForTimeout(700);
const tiers = await page.evaluate(() => {
  const dlg = document.querySelector('[role="dialog"][aria-label="پالت فرمان"]');
  const t = dlg?.textContent ?? '';
  return { symbol: t.includes('نماد'), page: t.includes('صفحه'), command: t.includes('فرمان') };
});
push('پالت: سه شیار نماد/صفحه/فرمان رسم می‌شود', tiers.symbol && tiers.page && tiers.command, tiers);

const themeBefore = await page.evaluate(() => document.documentElement.dataset.theme ?? 'dark');
const cmdBtn = await page.evaluateHandle(() => {
  const btns = Array.from(document.querySelectorAll('[role="dialog"] [role="option"]')) as HTMLElement[];
  return btns.find((b) => (b.textContent ?? '').includes('تغییر پوسته')) ?? null;
});
await (cmdBtn.asElement() as { click: () => Promise<void> } | null)?.click();
await page.waitForTimeout(350);
const themeAfter = await page.evaluate(() => document.documentElement.dataset.theme ?? 'dark');
push('فرمانِ پوسته، data-theme را واقعاً عوض می‌کند', themeAfter !== themeBefore, { themeBefore, themeAfter });
// بازگردانی تم به حالت اول
await page.keyboard.press('Control+k');
await page.waitForTimeout(500);
const cmdBtn2 = await page.evaluateHandle(() => {
  const btns = Array.from(document.querySelectorAll('[role="dialog"] [role="option"]')) as HTMLElement[];
  return btns.find((b) => (b.textContent ?? '').includes('تغییر پوسته')) ?? null;
});
await (cmdBtn2.asElement() as { click: () => Promise<void> } | null)?.click();
await page.waitForTimeout(250);
const themeRestored = await page.evaluate(() => document.documentElement.dataset.theme ?? 'dark');
push('تم به حالت اول برگشت (دو بار اجرا)', themeRestored === themeBefore, { themeBefore, themeRestored });

// ج) تب قیف اسکرول می‌کند
const scrollState = await page.evaluate(async () => {
  const targets = () =>
    [document.querySelector('.app-content'), document.scrollingElement].filter(Boolean) as HTMLElement[];
  const before = Math.max(0, ...targets().map((t) => t.scrollTop));
  const tab = document.querySelector('[data-testid="funnel-step-technical"]') as HTMLElement | null;
  tab?.click();
  await new Promise((r) => setTimeout(r, 650));
  return { before, after: Math.max(0, ...targets().map((t) => t.scrollTop)) };
});
push(
  'تبِ قیف، کارتِ همان مرحله را به دید می‌آورد (اسکرولِ واقعی)',
  scrollState.after > scrollState.before || scrollState.after > 40,
  scrollState,
);

await browser.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(results, null, 1), 'utf8');
const failed = (results.checks as { ok: boolean }[]).filter((c) => !c.ok).length;
console.log(`\n${(results.checks as unknown[]).length} سنجش — ${failed} ناکام`);
process.exit(failed ? 1 : 0);
