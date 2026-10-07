// _audit/mobile_data_probe.mjs — سنجشِ زندهٔ «داده» روی ۳۶۰×۸۰۰ با اسنپ‌شاتِ سبک
// (بستهٔ کامل ۲۳ مگابایتی درِ Chromiumِ Playwright با 204 برمی‌گردد؛ این بسته
// ۰٫۲ مگابایتی همان قراردادِ داده است با ۵ نماد و کلِ ۸۷۳ ردیفِ اسکرینر.)
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(
  'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/node_modules/playwright/index.mjs').href);

const BASE = process.env.PROBE_URL || 'http://127.0.0.1:4181/';
const OUT = '_audit/data';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 360, height: 800 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
await page.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });

const out = { base: BASE, steps: [] };
const step = async (name, fn) => {
  const rec = { step: name };
  try { Object.assign(rec, await fn()); } catch (e) { rec.error = String(e).slice(0, 240); }
  out.steps.push(rec);
  console.log(name, JSON.stringify(rec).slice(0, 500));
};

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(25000);

await step('boot', async () => ({
  timing: await page.evaluate(() => window.bootTiming ?? null),
  tapeRows: await page.locator('[data-testid="tape-row"]').count(),
  feedError: await page.locator('text=فیدِ تابلو برنگشت').count(),
  sidebar: await page.evaluate(() => {
    const r = document.querySelector('aside[data-shell="sidebar"]')?.getBoundingClientRect();
    return r ? { y: Math.round(r.y), h: Math.round(r.height), bottom: Math.round(r.bottom) } : null;
  }),
}));
await page.screenshot({ path: `${OUT}/01-market.png` });

await step('inspector-open', async () => {
  const row = page.locator('[data-testid="tape-row"] button').first();
  if (!(await row.count())) return { skipped: 'ردیفِ تابلو نیست' };
  await row.click();
  await page.waitForTimeout(2500);
  return {
    inspector: await page.evaluate(() => {
      const el = document.querySelector('aside[data-shell="inspector"]');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
               bottom: Math.round(r.bottom), transform: cs.transform.slice(0, 40) };
    }),
    closeBtn: await page.evaluate(() => {
      const b = [...document.querySelectorAll('aside[data-shell="inspector"] button')]
        .find((x) => (x.textContent ?? '').includes('✕'));
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    }),
  };
});
await page.screenshot({ path: `${OUT}/02-inspector.png` });
await page.evaluate(() => {
  const b = [...document.querySelectorAll('aside[data-shell="inspector"] button')]
    .find((x) => (x.textContent ?? '').includes('✕'));
  b?.click();
});
await page.waitForTimeout(1200);

await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
await step('fundamental-universe', async () => ({
  header: await page.locator('[data-testid="fts-screen-scroll"]')
    .locator('xpath=ancestor::*[.//span[contains(text(),"شرکت از")]]').first()
    .locator('span.num').first().textContent().catch(() => null),
  headerAny: await page.locator('span.num', { hasText: 'شرکت از' }).first().textContent().catch(() => null),
  domRows: await page.locator('[data-testid="fts-screen-scroll"] [role="row"], [data-testid="fts-screen-scroll"] tbody tr').count(),
  scrollWidth: await page.evaluate(() => {
    const el = document.querySelector('[data-testid="fts-screen-scroll"]');
    return el ? { scrollW: el.scrollWidth, clientW: el.clientWidth } : null;
  }),
}));
await page.screenshot({ path: `${OUT}/03-fundamental.png` });
// پایینِ جدول را هم ببین: اگر ۸۷۳ ردیف واقعاً درِ DOMِ مجازی باشد، اسکرول طولِ کل را می‌دهد
await step('fundamental-scrolled', async () => {
  await page.evaluate(() => {
    const el = document.querySelector('[data-testid="fts-screen-scroll"]');
    if (el) el.scrollTop = 6000;
  });
  await page.waitForTimeout(1500);
  return {
    scrollTop: await page.evaluate(() => document.querySelector('[data-testid="fts-screen-scroll"]')?.scrollTop ?? -1),
    domRows: await page.locator('[data-testid="fts-screen-scroll"] tbody tr').count(),
  };
});

await page.goto(`${BASE}#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(25000);
await step('chart-canvas', async () => ({
  canvases: await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => {
    const g = c.getContext('2d');
    let ink = 0;
    if (g && c.width > 20) {
      const d = g.getImageData(0, 0, Math.min(c.width, 500), Math.min(c.height, 500)).data;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 8) ink++;
    }
    return { w: c.width, h: c.height, ink };
  })),
  emptyState: await page.locator('text=داده‌ای برای رسم نیست').count(),
}));
await page.screenshot({ path: `${OUT}/04-technical.png` });

await page.goto(`${BASE}#/strategy-tree?page=T`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
await step('tree-flow', async () => ({
  rails: await page.locator('[data-testid^="tree-flow-rail-"]').count(),
  flow: await page.evaluate(() => {
    const el = document.querySelector('.fts-path-flow');
    const comet = document.querySelector('.fts-comet');
    return {
      flowAnimation: el ? getComputedStyle(el).animationName + ' ' + getComputedStyle(el).animationPlayState : null,
      flowOpacityKeyframes: !!el,
      comet: !!comet,
      rootFlag: document.documentElement.dataset.treeFlowRunning ?? null,
    };
  }),
}));
await page.screenshot({ path: `${OUT}/05-tree.png` });

out.errors = [...new Set(errors)].slice(0, 12);
writeFileSync(`${OUT}/probe.json`, JSON.stringify(out, null, 1));
await browser.close();
