// _audit/mobile_portrait_probe.mjs — سنجشِ زندهٔ چیدمانِ موبایل (۳۶۰×۸۰۰)
// اجرا:  JEV_CHROME=<chromium> node _audit/mobile_portrait_probe.mjs
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PW = process.env.PW_PKG
  || 'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/node_modules/playwright/index.mjs';
const { chromium } = await import(pathToFileURL(PW).href);

const EXE = process.env.JEV_CHROME || '';
const BASE = process.env.PROBE_URL || 'http://127.0.0.1:5199/';
const OUT = '_audit/portrait';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EXE || undefined });
const ctx = await browser.newContext({
  viewport: { width: 360, height: 800 },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
  userAgent: 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36',
});
const page = await ctx.newPage();
await page.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* پوستهٔ بدونِ دروازه */ }
});
const errors = [];
const badNet = [];
page.on('response', (r) => { if (r.status() >= 400) badNet.push(`${r.status()} ${r.url().slice(0, 120)}`); });
page.on('requestfailed', (r) => badNet.push(`FAIL ${r.url().slice(0, 120)}`));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => errors.push(`pageerror: ${String(e).slice(0, 200)}`));

const rectOf = async (sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
           bottom: Math.round(r.bottom), scrollW: el.scrollWidth, clientW: el.clientWidth };
}, sel);

const shot = async (name) => page.screenshot({ path: `${OUT}/${name}.png` });

const out = { base: BASE, viewport: { w: 360, h: 800 }, steps: [] };

async function step(name, fn) {
  const rec = { step: name };
  try { Object.assign(rec, await fn()); } catch (e) { rec.error = String(e).slice(0, 300); }
  out.steps.push(rec);
  console.log(name, JSON.stringify(rec).slice(0, 400));
}

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(45000);

await step('boot', async () => ({
  borsMobile: await page.evaluate(() => document.documentElement.classList.contains('bors-mobile')),
  bodyOverflowX: await page.evaluate(() => document.documentElement.scrollWidth),
  sidebar: await rectOf('aside[data-shell="sidebar"]'),
  content: await rectOf('.app-content'),
  tapeScroll: await rectOf('[data-testid="tape-scroll"]'),
  tapeRows: await page.locator('[data-testid="tape-row"]').count(),
  fatal: await page.locator('.bors-fatal-banner').count(),
  feedError: await page.locator('text=فیدِ تابلو برنگشت').count(),
}));
await shot('01-market');

await step('diagnostics', async () => {
  await page.locator('#bors-diag-btn').click();
  await page.waitForTimeout(4000);
  const txt = await page.evaluate(() => document.getElementById('bors-diag-panel')?.innerText ?? '');
  return { panel: txt.replace(/\s+/g, ' ').slice(0, 1400) };
});

await step('symbol-inspector', async () => {
  const before = await rectOf('aside[data-shell="sidebar"]');
  await page.locator('[data-testid="tape-row"] button').first().click();
  await page.waitForTimeout(1500);
  const insp = await rectOf('aside[data-shell="inspector"]');
  const closeBtn = await rectOf('aside[data-shell="inspector"] button:has-text("✕")');
  return { inspector: insp, close: closeBtn, sidebarAfter: before,
           navVisible: insp ? (before && before.y >= 0 && before.y < 800) : null };
});
await shot('02-inspector');

await step('close-inspector', async () => {
  await page.locator('aside[data-shell="inspector"] button:has-text("✕")').click().catch(() => {});
  await page.waitForTimeout(800);
  return { inspector: await rectOf('aside[data-shell="inspector"]') };
});

await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
await step('fundamental', async () => ({
  header: await page.locator('span.num:has-text("شرکت از")').first().textContent().catch(() => null),
  domRows: await page.locator('[data-testid="fts-screen-scroll"] tbody tr').count(),
  scroll: await rectOf('[data-testid="fts-screen-scroll"]'),
}));
await shot('03-fundamental');

await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
await step('funnel-overview', async () => ({
  overview: await page.locator('[data-testid="fts-funnel-overview"]').count(),
  stepper: await page.locator('[data-testid="fts-process-stepper"]').count(),
  stepperRect: await rectOf('[data-testid="fts-process-stepper"]'),
}));
await shot('04-master');

await step('funnel-stage-technical', async () => {
  await page.locator('[data-testid="fts-process-stepper"] a', { hasText: 'تکنیکال' }).first().click();
  await page.waitForTimeout(9000);
  return {
    href: page.url(),
    notFound: await page.locator('[data-testid="route-not-found"]').count(),
    stageView: await page.locator('[data-testid="fts-stage-technical"]').count(),
    stageCard: await page.locator('[data-testid="funnel-stage-technical"]').count(),
    stepChips: await page.locator('[data-testid^="funnel-step-"]').count(),
  };
});
await shot('05-stage-technical');

await page.goto(`${BASE}#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(20000);
await step('technical-chart', async () => {
  const canvases = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => {
    const g = c.getContext('2d');
    let ink = 0;
    if (g && c.width > 10) {
      const d = g.getImageData(0, 0, Math.min(c.width, 400), Math.min(c.height, 400)).data;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 8) ink++;
    }
    return { w: c.width, h: c.height, ink };
  }));
  return {
    canvases,
    emptyState: await page.locator('text=داده‌ای برای رسم نیست').count(),
    chartArea: await rectOf('[data-testid="chart-area"]'),
  };
});
await shot('06-technical');

out.errors = errors.slice(0, 25);
out.badNet = [...new Set(badNet)].slice(0, 20);
console.log('ERRORS', JSON.stringify(errors.slice(0, 10), null, 1));
const { writeFileSync } = await import('node:fs');
writeFileSync(`${OUT}/probe.json`, JSON.stringify(out, null, 1));
await browser.close();
