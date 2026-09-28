// tools/funnel_move_prefs_probe.mts — شاهدِ زندهٔ «قیف رفت به تبِ استراتژی FTS» + پیچ‌های درِ بنیادی
//
// سه چیز را در خودِ مرورگر ثابت می‌کند:
//   1) تبِ «استراتژی FTS» بی‌نماد دیگر پیامِ خالی نیست: قیفِ چهارمرحله‌ای همان‌جاست.
//   2) پیچ‌هایِ جدید (کفِ بنیادی / سنجیده‌نشده) شمارشِ واقعیِ قیف را عوض می‌کنند.
//   3) انتخابِ نماد از قیف، داوری را باز می‌کند؛ دکمهٔ بازگشت، قیف را برمی‌گرداند؛
//      و تبِ «درخت استراتژی» دیگر قیف ندارد.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/funnel_move_prefs_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/funnel_move_prefs.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/funnel_move_prefs.json');
const WAIT = Number(arg('wait', '14000'));

const report: Record<string, unknown> = { base: BASE, steps: {}, errors: [] };
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
    localStorage.removeItem('fts.funnel.prefs.v1');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') (report.errors as string[]).push(`console: ${m.text().slice(0, 220)}`);
});

const SNAP = () => {
  const txt = (sel: string) => {
    const el = document.querySelector(sel);
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 220) : null;
  };
  const counts: Record<string, string | null> = {};
  for (const k of ['tape', 'technical', 'fundamental', 'handover']) counts[k] = txt(`[data-testid="funnel-step-${k}"]`);
  return {
    href: location.href,
    counts,
    pending: txt('[data-testid="funnel-pending-fundamental"]'),
    prefs: txt('[data-testid="funnel-prefs"]'),
    reset: !!document.querySelector('[data-testid="funnel-prefs-reset"]'),
    coverage: txt('[data-testid="funnel-tech-coverage"]'),
    emptyState: (document.body.innerText.match(/نمادی انتخاب نشده/) ?? [null])[0],
    masterHead: (document.body.innerText.split('\n').find((l) => l.includes('برآیند مستر')) ?? null),
    funnelRows: document.querySelectorAll('[data-fkey]').length,
  };
};

await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);
report.steps.masterNoSymbol = await page.evaluate(SNAP as never);
await page.screenshot({ path: OUT.replace(/\.json$/, '_master_funnel.png') });

// پیچِ کفِ بنیادی: ۲ از ۵
const click = async (sel: string, key: string) => {
  try {
    await page.click(sel, { timeout: 8000 });
    await page.waitForTimeout(2500);
    report.steps[key] = await page.evaluate(SNAP as never);
  } catch (e) {
    report.steps[key] = `click failed: ${String(e).slice(0, 140)}`;
  }
};
await click('[data-testid="funnel-floor-2"]', 'floor2');
await click('[data-testid="funnel-floor-5"]', 'floor5');
await click('[data-testid="funnel-unmeasured-pass"]', 'unmeasuredPass');
await click('[data-testid="funnel-unmeasured-drop"]', 'unmeasuredDrop');
await click('[data-testid="funnel-unmeasured-hold"]', 'unmeasuredHold');
await click('[data-testid="funnel-floor-3"]', 'floor3');
report.steps.afterResetDefaults = await page.evaluate(SNAP as never);

// کلیکِ سطرِ قیف ⇒ داوریِ مستر باز می‌شود و قیف می‌رود
const firstRow = page.locator('[data-fkey] button').first();
try {
  report.steps.pickedSymbol = (await firstRow.textContent())?.trim() ?? null;
  await firstRow.click({ timeout: 8000 });
  await page.waitForTimeout(4000);
  report.steps.masterWithSymbol = await page.evaluate(SNAP as never);
  await page.screenshot({ path: OUT.replace(/\.json$/, '_master_verdict.png') });
  // دکمهٔ بازگشت به قیف
  await page.click('[data-testid="master-open-funnel"]', { timeout: 8000 });
  await page.waitForTimeout(6000);
  report.steps.backToFunnel = await page.evaluate(SNAP as never);
} catch (e) {
  report.steps.pickFlow = `failed: ${String(e).slice(0, 160)}`;
}

// تبِ درخت دیگر نباید قیف داشته باشد
await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(9000);
report.steps.tree = await page.evaluate(() => {
  const body = document.body.innerText;
  return {
    funnelTestids: document.querySelectorAll('[data-testid^="funnel-"]').length,
    doorButton: (body.match(/قیف انتخاب خودکار/g) ?? []).length,
    viewButtons: Array.from(document.querySelectorAll('button'))
      .map((b) => (b.textContent ?? '').replace(/\s+/g, ' ').trim())
      .filter((t) => t.includes('نمای') || t.includes('شبکه') || t.includes('ترکیبی'))
      .slice(0, 6),
  };
});

mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report.steps, null, 1).slice(0, 4200));
console.log('errors', report.errors);
await browser.close();
