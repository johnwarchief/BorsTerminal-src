// tools/map_geometry_probe.mts — سنجشِ هندسۀ زندۀ «نقشۀ چهار صفحۀ FTS»
// سه پرسش را با پیکسل جواب می‌دهد، نه با jsdom:
//   ۱) برچسبِ هر گره درونِ کارتِ خودش جا می‌شود؟ (سرریزِ متن = نقشهٔ ناخوانا)
//   ۲) مقیاسِ رندر چقدر است و بوم چقدر قد/پهنا دارد؟ (باید در ۱۹۲۰ خوانا و در ۱۳۶۶ قابل‌اسکرول باشد)
//   ۳) اسکرول افقی از کدام لب شروع می‌شود؟ (RTL: باید از صفحۀ ۱، یعنی لبۀ راست)
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/map_geometry_probe.mts \
//     --url http://127.0.0.1:8002/ --out _audit/map_geometry.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
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
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/map_geometry.json');
const WAIT = Number(arg('wait', '14000'));

const report: Record<string, unknown> = { base: BASE, checks: [], errors: [], shots: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('fts.strategy.custom_parameters.v2');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') (report.errors as string[]).push(`console: ${m.text().slice(0, 160)}`);
});

await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-node-id="tape_volume"]', { timeout: WAIT });
await page.waitForTimeout(1200);

const GEOM = () =>
  page.evaluate(() => {
    const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
    if (!canvas) return { error: 'no canvas' };
    const c = canvas.getBoundingClientRect();
    const rows = Array.from(document.querySelectorAll('[data-node-id]'));
    const overflow: { id: string; label: string; over: number }[] = [];
    let sample: Record<string, number> | null = null;
    for (const g of rows) {
      const id = g.getAttribute('data-node-id') ?? '';
      if (g.getAttribute('data-node-kind') !== 'leaf') continue;
      const rect = g.querySelector('rect');
      const text = g.querySelector('text');
      if (!rect || !text) continue;
      const r = rect.getBoundingClientRect();
      const t = text.getBoundingClientRect();
      if (!sample) sample = { cardW: Math.round(r.width), textW: Math.round(t.width), cardH: Math.round(r.height) };
      const over = Math.max(0, r.left - t.left, t.right - r.right);
      if (over > 2) overflow.push({ id, label: (text.textContent ?? '').slice(0, 34), over: Math.round(over) });
    }
    const scroller = canvas.closest('[class*="overflow-x-auto"]') as HTMLElement | null;
    return {
      canvasCss: { w: Math.round(c.width), h: Math.round(c.height) },
      viewBox: canvas.getAttribute('viewBox'),
      rows: rows.length,
      sample,
      overflowCount: overflow.length,
      overflow: overflow.slice(0, 12),
      scroll: scroller
        ? { left: Math.round(scroller.scrollLeft), max: Math.round(scroller.scrollWidth - scroller.clientWidth), dir: getComputedStyle(scroller).direction }
        : null,
      zoneSlots: Array.from(document.querySelectorAll('[data-zone-frame]')).map((z) => `${z.getAttribute('data-zone-frame')}:${z.getAttribute('data-zone-slot')}`),
    };
  });

const g1920 = await GEOM();
report.g1920 = g1920;
const dir = await page.evaluate(() => document.documentElement.dir || getComputedStyle(document.documentElement).direction);
report.htmlDir = dir;
ck('برچسبِ هیچ گره‌ای از کارتِ خودش بیرون نمی‌زند', (g1920.overflowCount ?? 0) === 0, g1920.overflow);
ck('چهار Zone با جایگاهِ ۰ تا ۳ رسم شده', JSON.stringify(g1920.zoneSlots) === '["F:0","T:1","S:2","M:3"]', g1920.zoneSlots);
ck('اسکرولِ افقی از لبۀ راست (صفحۀ ۱) شروع می‌شود',
  Boolean(g1920.scroll && g1920.scroll.max === 0) || Boolean(g1920.scroll && Math.abs(g1920.scroll.left) >= g1920.scroll.max - 2),
  g1920.scroll);

const shot = OUT.replace(/\.json$/, '-1920.png');
mkdirSync(dirname(shot), { recursive: true });
await page.screenshot({ path: shot, fullPage: false });
(report.shots as string[]).push(shot);

// ارتفاعِ ستونِ نقشه: اگر از دیدِ ۱۰۸۰ بلندتر باشد، مالک باید اسکرول عمودی کند
const tall = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  const c = canvas?.getBoundingClientRect();
  return { canvasH: Math.round(c?.height ?? 0), viewportH: window.innerHeight, pageH: document.body.scrollHeight };
});
report.tall = tall;
ck('بوم در ۱۰۸۰ بدون اسکرولِ عمودیِ زیاد جا می‌شود', tall.canvasH <= tall.viewportH * 0.95, tall);

await page.setViewportSize({ width: 1366, height: 900 });
await page.waitForTimeout(700);
const g1366 = await GEOM();
report.g1366 = g1366;
ck('در ۱۳۶۶ هم متن‌ها درونِ کارت‌اند', (g1366.overflowCount ?? 0) === 0, g1366.overflow);
const shot2 = OUT.replace(/\.json$/, '-1366.png');
await page.screenshot({ path: shot2, fullPage: false });
(report.shots as string[]).push(shot2);

await browser.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
const failed = (report.checks as { ok: boolean }[]).filter((x) => !x.ok).length;
console.log(`${(report.checks as unknown[]).length} سنجش — ${failed} ناکام`);
console.log(JSON.stringify({ g1920, g1366, tall, dir }, null, 1).slice(0, 2600));
process.exit(failed ? 1 : 0);
