// tools/pulse_chart_probe_v1059.mts -- اثباتِ زندهٔ سه خواستۀ ۱٫۰٫۵۹ از DOMِ خودِ برنامه
//
//   ۱) نبض بازار: عنوانِ ردیفِ جریان «معاملات خرد» است، نه «سهام»
//   ۲) «ورود به بازار»: پنج در در یک سطر، توضیح‌ها پشتِ یک کلید -- قدِ پنل هم
//      اندازه گرفته می‌شود («کاربر خسته نشه، کوتاه‌ترش بکن» باید عدد داشته باشد)
//   ۳) کندل: پایانِ سری در دو اندپوینت یکی است، کندلی بعد از تاریخِ نشست نیست،
//      و وقتی /api/chart می‌میرد چارت منبعِ جایگزین را رویِ خودش می‌نویسد
//
//   JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types \
//     tools/pulse_chart_probe_v1059.mts --url http://127.0.0.1:8001/ --out _audit/pulse_chart_1059.json
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8001/').replace(/\/$/, '');
const SYMBOL = arg('symbol', 'فولاد');
const OUT = arg('out', '_audit/pulse_chart_1059.json');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 180)); });
page.on('pageerror', (e) => errors.push('pageerror: ' + String(e).slice(0, 180)));

const report: Record<string, unknown> = { base: BASE, symbol: SYMBOL };

// ── ۱ و ۲) نبض بازار در تبِ تابلو ────────────────────────────────────────────
await page.goto(`${BASE}/#/market`, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="pulse-verdict"]', { timeout: 45_000 });
await page.waitForSelector('[data-testid="pulse-smart"]', { timeout: 45_000 });

report.pulse = await page.evaluate(() => {
  const smart = document.querySelector('[data-testid="pulse-smart"]');
  const verdict = document.querySelector('[data-testid="pulse-verdict"]');
  const chipRow = document.querySelector('[data-testid="pulse-verdict-gate-flow"]')?.parentElement;
  const gateLabels = Array.from(document.querySelectorAll('[data-testid^="pulse-verdict-gate-"]'))
    .map((el) => (el.textContent ?? '').trim());
  const chipTops = new Set(
    Array.from(document.querySelectorAll('[data-testid^="pulse-verdict-gate-"]'))
      .map((el) => Math.round(el.getBoundingClientRect().top)),
  );
  return {
    smartText: smart?.textContent?.trim().slice(0, 220) ?? null,
    hasRetailLabel: (smart?.textContent ?? '').includes('معاملات خرد'),
    hasLegacyStockLabel: (smart?.textContent ?? '').includes('سهام'),
    verdictLabel: document.querySelector('[data-testid="pulse-verdict-label"]')?.textContent?.trim() ?? null,
    verdictHeight: verdict ? Math.round(verdict.getBoundingClientRect().height) : null,
    gateCount: gateLabels.length,
    gatesOnOneRow: chipTops.size <= Math.max(1, Math.ceil(gateLabels.length / 4)),
    chipRowTag: chipRow?.tagName ?? null,
    gateChips: gateLabels,
    whysVisibleByDefault: !!document.querySelector('[data-testid^="pulse-verdict-why-"]'),
    toggleText: document.querySelector('[data-testid="pulse-verdict-whys-toggle"]')?.textContent?.trim() ?? null,
  };
});

const toggle = page.locator('[data-testid="pulse-verdict-whys-toggle"]');
if (await toggle.count()) {
  await toggle.first().click();
  await page.waitForTimeout(250);
  report.pulseExpanded = await page.evaluate(() => {
    const verdict = document.querySelector('[data-testid="pulse-verdict"]');
    return {
      verdictHeight: verdict ? Math.round(verdict.getBoundingClientRect().height) : null,
      whys: Array.from(document.querySelectorAll('[data-testid^="pulse-verdict-why-"]'))
        .map((el) => (el.textContent ?? '').trim()),
    };
  });
  await toggle.first().click(); // بستن -- حالتِ پیش‌فرض برای عکسِ بعدی برنگردد
}

// ── ۳) کندل: برابریِ دو اندپوینت از خودِ مرورگر ──────────────────────────────
report.apiParity = await page.evaluate(async (sym: string) => {
  const get = async (p: string) => {
    const r = await fetch(p);
    return r.ok ? await r.json() : { status: 'http-' + r.status };
  };
  const j = (await get(`/api/chart/${encodeURIComponent(sym)}`)) as any;
  const d = (await get(`/api/chart-db/${encodeURIComponent(sym)}`)) as any;
  const asc = (a: any[]) => [...a].sort((x, y) => x.time.localeCompare(y.time));
  const c = asc(j.candles ?? []);
  const e = asc(d.candles ?? []);
  const lastOf = (s: any[]) => (s.length ? s[s.length - 1] : null);
  const a = lastOf(c), b = lastOf(e);
  const today = new Date().toISOString().slice(0, 10);
  return {
    chartCount: c.length, dbCount: e.length,
    chartAdjustEvents: (j.adjustEvents ?? []).length,
    chartLast: a, dbLast: b,
    sameLastDate: !!a && !!b && a.time === b.time,
    sameLastOhlc: !!a && !!b && ['open', 'high', 'low', 'close'].every(
      (k) => Math.abs(Number(a[k]) - Number(b[k])) < 1e-6,
    ),
    // کندلِ شبح: هیچ ردیفی بعد از امروز نباید باشد
    futureBars: [...c, ...e].filter((x) => x.time > today).map((x) => x.time),
    // کندلِ بی‌حجمِ صاف (نشانهٔ کندلِ جعلیِ پیش از بازگشایی)
    zeroVolumeBars: e.filter((x) => Number(x.volume) === 0).map((x) => x.time).slice(-3),
    liveInjected: { chart: !!j.liveInjected, db: !!d.liveInjected },
    degraded: { chart: !!j.degraded, db: !!d.degraded },
  };
}, SYMBOL);

// ── ۳ب) نوارِ منبع: /api/chart را می‌کُشیم تا فال‌بک دیده شود ─────────────────
await page.goto(`${BASE}/#/technical/${encodeURIComponent(SYMBOL)}`, { waitUntil: 'networkidle' });
await page.waitForSelector('.nn-kline-chart canvas, [data-testid="nn-chart-host"]', { timeout: 45_000 });
await page.waitForTimeout(2500);
report.chartNormal = await page.evaluate(() => ({
  note: document.querySelector('[data-testid="chart-feed-note"]')?.textContent?.trim() ?? null,
}));

await page.route('**/api/chart/**', (route) => route.abort('failed'));
await page.goto(`${BASE}/#/technical/${encodeURIComponent('خساپا')}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(4000);
report.chartDegraded = await page.evaluate(() => {
  const n = document.querySelector('[data-testid="chart-feed-note"]');
  return {
    present: !!n,
    note: n?.textContent?.trim() ?? null,
    title: n?.getAttribute('title') ?? null,
    canvas: !!document.querySelector('.nn-kline-chart canvas'),
  };
});
await page.unroute('**/api/chart/**');

report.consoleErrors = errors;
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report, null, 2));
await browser.close();
