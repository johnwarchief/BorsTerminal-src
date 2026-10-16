// _audit/ws7b_rename_check.mts — سنجشِ زندهٔ واژگانِ «غربالگری» درِ رابط
//
// رأیِ مالک: user-facing «قیف» → «غربالگری»، «فرماندهی FTS» → «غربالگری FTS»؛
// endpoint و نامِ فایل و data-testid دست‌نخورده می‌مانند. پس سنجش هم فقط رویِ
// **متنِ دیدنی** است: هیچ گرهٔ متنیِ قابل‌رویت درِ پنج مسیرِ اصلی نباید «قیف»
 // داشته باشد. «مرکز فرماندهی نبض بازار» سامانۀ دیگری است (نبض بازار) و دست‌خورده نیست.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const ROUTES = ['#/master', '#/market', '#/fundamental', '#/portfolio', '#/strategy-tree'];
const PULSE_OK = 'مرکز فرماندهی نبض بازار';

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error' || m.type() === 'warning') consoleErrors.push(`${m.type()}: ${m.text().slice(0, 140)}`);
});
page.on('pageerror', (e: any) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 140)}`));

const results: Record<string, unknown> = {};
for (const r of ROUTES) {
  await page.goto(`${BASE}${r}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  const found = await page.evaluate((pulseOk: string) => {
    const bad: { text: string; tag: string; testid: string | null }[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n: Text | null;
    const attr = document.documentElement.outerHTML;
    while ((n = walker.nextNode() as Text | null)) {
      const t = (n.textContent ?? '').trim();
      if (!t) continue;
      if (!/قیف|فرماندهی/.test(t)) continue;
      if (t.includes(pulseOk)) continue;
      const el = n.parentElement;
      bad.push({ text: t.slice(0, 90), tag: el?.tagName ?? '?', testid: el?.getAttribute('data-testid') ?? null });
    }
    return { visibleQyf: bad,
             // آترابیوت‌هایِ دیدنی (aria-label/title/placeholder) هم شمار می‌آیند
             attrHits: ['قیف', 'فرماندهی FTS'].flatMap((w) =>
               Array.from(attr.matchAll(new RegExp(`(aria-label|title|placeholder)="[^"]*${w}[^"]*"`, 'g')))
                    .map((m) => m[0].slice(0, 110))) };
  }, PULSE_OK);
  results[r] = found;
}

const screenshot = '_audit/ws7b_rename_master.png';
await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: 120_000 });
const headings = await page.evaluate(() => ({
  // سرآمدِ خودِ کارگاه درِ <section data-testid="fts-funnel-workspace"> است، نه
  // درِ <section> هر مرحله (آن یکی h3 دارد)؛ انتخابگرِ قبلی گرهٔ اشتباه را می‌خواند.
  funnelH2: document.querySelector('[data-testid="fts-funnel-workspace"] > h2')?.textContent?.trim()
    ?? Array.from(document.querySelectorAll('h2')).map((h) => h.textContent?.trim() ?? '').find((t) => t.includes('غربالگری'))
    ?? null,
  stepperLabel: document.querySelector('[data-testid="fts-process-stepper"]')
    ?.getAttribute('aria-label') ?? null,
}));
await page.screenshot({ path: screenshot, fullPage: false });

const leaks = Object.entries(results).flatMap(([route, v]) => {
  const x = v as { visibleQyf: unknown[]; attrHits: string[] };
  return [...(x.visibleQyf as unknown[]).map((i) => `${route} :: ${JSON.stringify(i)}`),
          ...x.attrHits.map((h) => `${route} :: attr ${h}`)];
});
const out = { base: BASE, at: new Date().toISOString(), routes: results, headings,
              leakCount: leaks.length, leaks: leaks.slice(0, 20),
              consoleErrors: consoleErrors.slice(0, 8),
              verdicts: {
                no_visible_funnel_word_anywhere: leaks.length === 0,
                workspace_heading_is_screening: (headings.funnelH2 ?? '').includes('غربالگری'),
                stepper_label_is_screening: (headings.stepperLabel ?? '').includes('غربالگری'),
              } };
mkdirSync('_audit', { recursive: true });
writeFileSync('_audit/ws7b_rename_check.json', JSON.stringify(out, null, 2));
console.log(JSON.stringify(out.verdicts, null, 2));
console.log(`leaks=${leaks.length}`);
leaks.slice(0, 10).forEach((l) => console.log('  ' + l));
await browser.close();
