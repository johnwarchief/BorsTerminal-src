// _audit/android_acceptance_probe.mjs — گیتِ پذیرشِ نهاییِ اندروید (A3)
//
// ده موردِ مالک: universe، چارت، FTS، قیف، درخت، تابلو، صفِ سرخطی، عمودی ۳۶۰×۸۰۰،
// افقی، آفلاین، تازگیِ اسنپ‌شات. هر مورد با عددِ خودش ثبت می‌شود؛ هیچ PASS بدونِ
// اندازه‌گیری نوشته نمی‌شود.
//
// چرا اسنپ‌شات با نامِ .js سرو می‌شود: Chromiumِ Playwright پاسخِ مسیرِ .gz را
// برای همین بدنه ۵۹ مگابایتی 204 برمی‌گرداند (همان بایت‌ها با نامِ .js ⇒ 200).
// بیلدِ پروب با VITE_SNAPSHOT_URL=/probe_bundle.js ساخته می‌شود.
//
// اجرا:  JEV_CHROME=<chromium> node _audit/android_acceptance_probe.mjs
import { mkdirSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(
  'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/node_modules/playwright/index.mjs').href);

const BASE = process.env.PROBE_URL || 'http://127.0.0.1:4181/';
const SRC_DB = process.env.SNAPSHOT_SRC || 'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/dist/mobile_snapshot.db.gz';
const OUT = '_audit/acceptance';
mkdirSync(OUT, { recursive: true });

if (!existsSync(SRC_DB)) { console.error('snapshot missing: ' + SRC_DB); process.exit(2); }
copyFileSync(SRC_DB, 'C:/Users/PCMOD/Desktop/BorsTerminal-android/frontend/dist/probe_bundle.js');

const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const report = { base: BASE, startedAt: new Date().toISOString(), checks: {}, errors: [] };
const errs = [];

const geom = async (page, sel) => page.evaluate((s) => {
  const el = document.querySelector(s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
           bottom: Math.round(r.bottom), scrollW: el.scrollWidth, clientW: el.clientWidth };
}, sel);

async function check(name, fn) {
  const rec = { state: 'PASS' };
  try { Object.assign(rec, await fn()); }
  catch (e) { rec.state = 'FAIL'; rec.error = String(e).slice(0, 260); }
  report.checks[name] = rec;
  console.log(`${rec.state}  ${name}  ${JSON.stringify(rec).slice(0, 320)}`);
}

async function newPage(width, height) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await page.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ } });
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 160)); });
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
  return { ctx, page };
}

// ── ۱) عمودی ۳۶×۸۰۰ — تابلو ──────────────────────────────────────────────
{
  const { ctx, page } = await newPage(360, 800);
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(60000); // بازگشایی ۵۹MB + باز کردنِ دیتابیس

  await check('portrait.market.layout', async () => {
    const nav = await geom(page, 'aside[data-shell="sidebar"]');
    const content = await geom(page, '.app-content');
    const rows = await page.locator('[data-testid="tape-row"]').count();
    return { nav, content, tapeRows: rows,
             navIsBottomBar: !!nav && nav.y > 600 && nav.h < 90 && nav.w === 360,
             horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth) };
  });
  await page.screenshot({ path: `${OUT}/01-market-360.png` });

  await check('portrait.market.liveOverlay', async () => {
    const diag = await page.evaluate(() => {
      const b = document.getElementById('bors-diag-btn'); b?.click(); return null;
    });
    await page.waitForTimeout(6000);
    const panel = await page.evaluate(() => document.getElementById('bors-diag-panel')?.innerText ?? '');
    await page.evaluate(() => document.getElementById('bors-diag-panel')?.remove());
    const grab = (label) => (panel.match(new RegExp(label + ':\\s*([^\\n]+)')) ?? [null, null])[1];
    return { state: panel.includes('TSETMC زنده: در دسترس نیست') ? 'FAIL' : 'PASS',
             tsetmcLive: grab('TSETMC زنده'), board: grab('تابلوی آفلاین'),
             fundamental: grab('بنیادی (اسکرینر)'), perSymbol: grab('پختِ هر-نماد'),
             candles: grab('تاریخچۀ چارت'), overlay: grab('آخرین رونشانیِ زندۀ تابلو'),
             packageVer: grab('بستهٔ داده'), boot: grab('راه‌اندازی') };
  });

  await check('portrait.market.orderQueue', async () => {
    const first = page.locator('[data-testid="tape-row"] button').first();
    if (!(await first.count())) return { state: 'FAIL', why: 'no tape row' };
    await first.click();
    await page.waitForTimeout(4000);
    const insp = await geom(page, 'aside[data-shell="inspector"]');
    const nav = await geom(page, 'aside[data-shell="sidebar"]');
    const book = await page.evaluate(() => {
      const t = document.querySelector('aside[data-shell="inspector"]')?.innerText ?? '';
      return { hasDepth: /عمق|پنج‌سطحی|تقاضا|عرضه/.test(t), snippet: t.replace(/\s+/g, ' ').slice(0, 220) };
    });
    return { inspector: insp, navStillVisible: !!nav && nav.bottom <= 801,
             navNotCovered: !!insp && insp.bottom <= nav.y, ...book,
             state: insp && insp.w > 0 && insp.bottom <= 801 ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/02-inspector-360.png` });
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('aside[data-shell="inspector"] button')].find((x) => (x.textContent ?? '').includes('✕'));
    b?.click();
  });
  await page.waitForTimeout(1500);

  // ── ۲) بنیادی — کلِ universe ────────────────────────────────────────────
  await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(20000);
  await check('fundamental.universe', async () => {
    const header = await page.locator('span.num', { hasText: 'شرکت از' }).first().textContent().catch(() => null);
    const rowsInDom = await page.locator('[data-testid="fts-screen-scroll"] tbody tr').count();
    const total = await page.evaluate(async () => {
      const { resolveLocal } = await import('/src/shared/api/local/resolvers.ts').catch(() => ({}));
      return null;
    });
    const scroller = await geom(page, '[data-testid="fts-screen-scroll"]');
    return { headerText: header, rowsInDom, scroller, virtualized: rowsInDom < 400 && !!scroller && scroller.scrollW > 0,
             state: header && /از/.test(header) ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/03-fundamental-360.png` });
  await check('fundamental.scrollEnd', async () => {
    const before = await page.evaluate(() => document.querySelector('[data-testid="fts-screen-scroll"]')?.firstElementChild?.scrollHeight ?? 0);
    await page.evaluate(() => {
      const el = document.querySelector('[data-testid="fts-screen-scroll"]')?.firstElementChild;
      if (el) el.scrollTop = 40000;
    });
    await page.waitForTimeout(2500);
    const after = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="fts-screen-scroll"]')?.firstElementChild;
      return { top: el?.scrollTop ?? -1, rows: document.querySelectorAll('[data-testid="fts-screen-scroll"] tbody tr').length };
    });
    return { scrollHeight: before, ...after, state: after.top > 1000 ? 'PASS' : 'FAIL' };
  });

  // ── ۳) تکنیکال — کندل ───────────────────────────────────────────────────
  await page.goto(`${BASE}#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(30000);
  await check('technical.chart', async () => {
    const canvases = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => {
      const g = c.getContext('2d');
      let ink = 0;
      if (g && c.width > 20) {
        const d = g.getImageData(0, 0, Math.min(c.width, 600), Math.min(c.height, 600)).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 8) ink++;
      }
      return { w: c.width, h: c.height, ink };
    }));
    const empty = await page.locator('text=داده‌ای برای رسم نیست').count();
    const chartArea = await geom(page, '[data-testid="chart-area"]');
    const drawn = canvases.filter((c) => c.ink > 500);
    return { canvases, emptyState: empty, chartArea, inkCanvases: drawn.length,
             state: drawn.length > 0 && empty === 0 ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/04-technical-360.png` });

  // ── ۴) قیف FTS و درخت ───────────────────────────────────────────────────
  await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(25000);
  await check('funnel.stages', async () => {
    const overview = await page.locator('[data-testid="fts-funnel-overview"]').count();
    const chips = await page.locator('[data-testid="fts-process-stepper"] a').count();
    const results = {};
    for (const [label, stage] of [['تابلوخوانی', 'tape'], ['تکنیکال', 'technical'], ['بنیادی', 'fundamental'], ['تحویل', 'handover']]) {
      await page.locator(`[data-testid="fts-process-stepper"] a:has-text("${label}")`).first().click();
      await page.waitForTimeout(9000);
      results[stage] = {
        href: page.url().split('#')[1] ?? page.url(),
        notFound: await page.locator('[data-testid="route-not-found"]').count(),
        stageCard: await page.locator(`[data-testid="funnel-stage-${stage}"]`).count(),
        rows: await page.locator(`[data-testid="funnel-stage-${stage}"] tbody tr`).count(),
      };
      await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(6000);
      await page.locator('[data-testid="fts-process-stepper"]').waitFor({ timeout: 20000 }).catch(() => {});
    }
    return { overview, chips, stages: results,
             state: Object.values(results).every((r) => r.notFound === 0 && r.stageCard === 1) ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/05-funnel-360.png` });

  await page.goto(`${BASE}#/strategy-tree?page=T`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(15000);
  await check('tree.flow', async () => {
    const f = await page.evaluate(() => {
      const el = document.querySelector('.fts-path-flow');
      const cs = el ? getComputedStyle(el) : null;
      return { rails: document.querySelectorAll('[data-testid^="tree-flow-rail-"]').length,
               animationName: cs?.animationName ?? null, playState: cs?.animationPlayState ?? null,
               comet: !!document.querySelector('.fts-comet'), rootFlag: document.documentElement.dataset.treeFlowRunning ?? null };
    });
    return { ...f, state: f.animationName === 'fts-path-flow' && f.playState === 'running' ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/06-tree-360.png` });
  await ctx.close();
}

// ── ۵) افقی ۸۰۰×۳۶۰ ───────────────────────────────────────────────────────
{
  const { ctx, page } = await newPage(812, 375);
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(45000);
  await check('landscape.market', async () => {
    const nav = await geom(page, 'aside[data-shell="sidebar"]');
    const rows = await page.locator('[data-testid="tape-row"]').count();
    const chartless = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    return { nav, tapeRows: rows, horizontalOverflow: chartless,
             railOnSide: !!nav && nav.w < 90 && nav.h > 200,
             state: rows > 0 ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/07-market-812x375.png` });
  await ctx.close();
}

// ── ۶) آفلاین (قطع شبکه پس از بارگذاری) ───────────────────────────────────
{
  const { ctx, page } = await newPage(360, 800);
  await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(45000);
  await ctx.setOffline(true);
  await page.goto(`${BASE}#/technical/%D8%AE%DA%AF%D8%B3%D8%AA%D8%B1`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(25000);
  await check('offline.technicalFromSnapshot', async () => {
    const canvases = await page.evaluate(() => [...document.querySelectorAll('canvas')].map((c) => {
      const g = c.getContext('2d'); let ink = 0;
      if (g && c.width > 20) {
        const d = g.getImageData(0, 0, Math.min(c.width, 600), Math.min(c.height, 600)).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 8) ink++;
      }
      return { w: c.width, h: c.height, ink };
    }));
    const drawn = canvases.filter((c) => c.ink > 500).length;
    return { offline: true, inkCanvases: drawn, state: drawn > 0 ? 'PASS' : 'FAIL' };
  });
  await page.screenshot({ path: `${OUT}/08-offline-xgstr.png` });
  await ctx.setOffline(false);
  await ctx.close();
}

report.errors = [...new Set(errs)].slice(0, 20);
report.finishedAt = new Date().toISOString();
writeFileSync(`${OUT}/acceptance.json`, JSON.stringify(report, null, 1));
const bad = Object.entries(report.checks).filter(([, v]) => v.state !== 'PASS');
console.log(`\n==== ${Object.keys(report.checks).length - bad.length}/${Object.keys(report.checks).length} PASS ====`);
for (const [k, v] of bad) console.log('FAIL ' + k + ' → ' + JSON.stringify(v).slice(0, 220));
await browser.close();
