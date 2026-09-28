// tools/board_poison_probe.mts -- تابلو بعد از تبِ دیگر هم سالم می‌ماند؟
//
// چرا: کشِ If-None-Match در shared/api/http.ts سطحِ ماژول است و تا پیش از
// 1405-07-06 فقط با *آدرس* کلید می‌خورد. همان /api/market را دو اسکیمای zod
// متفاوت می‌خوانند: تابلو کامل، و useMarketCloses فقط {symbol, p_closing}.
// اسکیما کلیدهای ناشناخته را می‌کاهد، پس اگر کاربر اول به «درخت استراتژی»
// (که useMarketCloses را mount می‌کند) برود و بعد به «تابلوخوانی/بازار» برگردد،
// ۳۰۴ِ تابلو می‌توانست ردیف‌های دوفیلدی را تحویل بگیرد — یعنی باگِ قیف درِ
// تبِ تابلو هم دیده می‌شد. این ابزار همان ترتیبِ تب را درِ دو context تازه
// می‌سنجد: (الف) مستقیم تابلو، (ب) اول درخت استراتژی بعد تابلو.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/board_poison_probe.mts \
//     --url http://127.0.0.1:8001/ --out _audit/board_poison.json
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
const BASE = arg('url', 'http://127.0.0.1:8001/');
const OUT = arg('out', '_audit/board_poison.json');
const WAIT = Number(arg('wait', '14000'));

const READ_BOARD = () => {
  const rows = document.querySelectorAll('[data-testid="tape-row"]');
  const chips = Array.from(document.querySelectorAll('[data-testid="quick-filters-bar"] button')).map((b) =>
    (b.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 34),
  );
  const first = rows[0];
  const cells = Array.from(first?.querySelectorAll('div') ?? []).slice(0, 10).map((d) =>
    (d.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 16),
  );
  const badges = document.querySelectorAll('[data-testid^="badge-"]').length;
  const flashing = document.querySelectorAll('.flash-up, .flash-down').length;
  const door = (document.body.innerText.match(/[^\n]*نماد[^\n]*/g) ?? []).slice(0, 4);
  return {
    rows: rows.length,
    badges,
    flashing,
    chips: chips.slice(0, 14),
    firstCells: cells,
    counters: door,
  };
};

const report: Record<string, unknown> = { base: BASE, runs: {} };

for (const [name, route] of [
  ['board-first', '#/'],
  ['tree-then-board', '#/strategy-tree'],
] as [string, string][]) {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
  const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem('bors_auth_session', 'true');
    } catch {
      /* پوستهٔ بدونِ دروازه */
    }
  });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on('pageerror', (e: { message: string }) => errors.push(`pageerror: ${e.message}`.slice(0, 160)));
  const marketReqs: { status: number; len: number | null }[] = [];
  page.on('response', (res: { url: () => string; status: () => number; headers: () => Record<string, string> }) => {
    if (res.url().includes('/api/market')) {
      marketReqs.push({ status: res.status(), len: res.headers()['content-length'] ?? null });
    }
  });

  if (route === '#/strategy-tree') {
    await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(Math.min(WAIT, 8000));
    // همان کاری که کاربر می‌کند: یک نگاهِ سریع به قیف، بعد برگشت به تابلو
    try {
      await page.getByText('قیف انتخاب خودکار', { exact: false }).first().click({ timeout: 6000 });
    } catch {
      /* اگر تب خودش قیف را نشان می‌دهد، کلیک لازم نیست */
    }
    await page.waitForTimeout(Math.min(WAIT, 9000));
  }
  await page.goto(`${BASE}#/`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT);
  const board = await page.evaluate(READ_BOARD as never);
  report.runs[name] = { board, marketReqs, errors };
  await page.screenshot({ path: OUT.replace(/\.json$/, `_${name}.png`) });
  await browser.close();
}

mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report, null, 1).slice(0, 3000));
