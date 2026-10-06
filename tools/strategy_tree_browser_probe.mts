/**
 * tools/strategy_tree_browser_probe.mts
 * آزمون زنده در مرورگر واقعی برای Strategy Tree (Flow & Orbit)، سایدبار و ناوبری
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/+$/, '') + '/';
const OUT = arg('out', '_audit/strategy_tree_browser_probe.json');

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const CHROME = process.env.JEV_CHROME || EDGE;

const results: Record<string, unknown> = {
  ts: new Date().toISOString(),
  base: BASE,
  checks: [] as Record<string, unknown>[],
};

const push = (name: string, ok: boolean, detail: unknown) => {
  (results.checks as Record<string, unknown>[]).push({ name, ok, detail });
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok ? '' : ' :: ' + JSON.stringify(detail).slice(0, 200)}`);
};

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

// ۱. بارگذاری صفحه Strategy Tree
await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(600);

const canvasExists = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  return !!canvas;
});
push('۱. بوم گراف در Strategy Tree رندر شد', canvasExists, { canvasExists });

// ۲. بررسی چیدمان فلوچارت (Flow)
const flowMetrics = await page.evaluate(() => {
  const nodeEls = Array.from(document.querySelectorAll('.nodes-layer > div'));
  const svg = document.querySelector('[data-testid="strategy-edges-svg"]');
  const pathEls = svg ? Array.from(svg.querySelectorAll('path')) : [];

  return {
    nodeCount: nodeEls.length,
    pathCount: pathEls.length,
    firstNodePos: nodeEls[0] ? { x: (nodeEls[0] as HTMLElement).style.left, y: (nodeEls[0] as HTMLElement).style.top } : null,
  };
});
push('۲. فلوچارت دارای گره‌ها و یال‌های محاسبه‌شده است', flowMetrics.nodeCount >= 10 && flowMetrics.pathCount >= 10, flowMetrics);

// ۳. سوییچ به حالت مداری (Orbit)
const orbitBtn = await page.waitForSelector('[data-testid="tree-layout-orbit"]');
await orbitBtn?.click();
await page.waitForTimeout(400);

const orbitMetrics = await page.evaluate(() => {
  const orbitRings = document.querySelector('.orbit-rings');
  const indicator = document.body.textContent?.includes('مدار منظومه‌ای');
  return {
    ringsFound: !!orbitRings,
    indicator,
  };
});
push('۳. سوییچ به چیدمان مداری (Orbit) با موفقیت اجرا شد', orbitMetrics.ringsFound && !!orbitMetrics.indicator, orbitMetrics);

// ۴. بازگشت به Flow
const flowBtn = await page.waitForSelector('[data-testid="tree-layout-flow"]');
await flowBtn?.click();
await page.waitForTimeout(300);

// ۵. کلیک و بازرسی نود
const nodeClicked = await page.evaluate(() => {
  const targetNode = Array.from(document.querySelectorAll('.nodes-layer > div')).find((el) =>
    el.textContent?.includes('حجم') || el.textContent?.includes('مشکوک')
  ) as HTMLElement | undefined;

  if (targetNode) {
    targetNode.click();
    return true;
  }
  return false;
});
await page.waitForTimeout(300);

const inspectorInfo = await page.evaluate(() => {
  const inspector = document.querySelector('[data-testid="strategy-node-inspector"]');
  const hasSlider = inspector ? !!inspector.querySelector('input[type="range"]') : false;
  return {
    inspectorFound: !!inspector,
    hasSlider,
  };
});
push('۴. انتخاب نود و نمایش پنل بازرسی با اسلایدر پارامترها', nodeClicked && inspectorInfo.inspectorFound && inspectorInfo.hasSlider, inspectorInfo);

// ۵-ب. بررسی باز شدن کشوی کاندیداهای مرحله
const drawerCheck = await page.evaluate(async () => {
  const btn = Array.from(document.querySelectorAll('button')).find((b) =>
    b.textContent?.includes('مشاهده کاندیداهای تابلو')
  );
  if (!btn) return { opened: false };
  btn.click();
  return { clicked: true };
});
await page.waitForTimeout(300);
const drawerFound = await page.evaluate(() => {
  const drawer = document.querySelector('[data-testid="stage-candidate-drawer"]');
  const hasTable = drawer ? !!drawer.querySelector('table') : false;
  // بستن کشو
  const closeBtn = drawer ? (Array.from(drawer.querySelectorAll('button')).find(b => b.textContent?.includes('✕')) as HTMLElement) : null;
  if (closeBtn) closeBtn.click();
  return { drawerFound: !!drawer, hasTable };
});
push('۴-ب. باز شدن جدول کاندیداهای مرحله‌به‌مرحله FTS', drawerFound.drawerFound && drawerFound.hasTable, drawerFound);

// ۶. ممیزی سایدبار و گروه‌بندی بخش‌ها
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(400);

const sidebarSections = await page.evaluate(() => {
  const sidebar = document.querySelector('aside[aria-label="نوار کناری"]');
  const sectionHeaders = sidebar ? Array.from(sidebar.querySelectorAll('.uppercase')).map((el) => el.textContent?.trim()) : [];
  const links = sidebar ? Array.from(sidebar.querySelectorAll('a')).map((a) => a.getAttribute('href')) : [];
  return { sectionHeaders, linkCount: links.length };
});
push('۵. ساختار سایدبار دارای گروه‌بندی معنایی و حفظ کامل دسترسی‌هاست', sidebarSections.sectionHeaders.length >= 2 && sidebarSections.linkCount === 6, sidebarSections);

// ۷. راستی‌آزمایی در رزولوشن‌های ۴گانه
const viewports = [
  { w: 1280, h: 720, name: '1280x720' },
  { w: 1366, h: 768, name: '1366x768' },
  { w: 1600, h: 900, name: '1600x900' },
  { w: 1920, h: 1080, name: '1920x1080' },
];

for (const vp of viewports) {
  await page.setViewportSize({ width: vp.w, height: vp.h });
  await page.waitForTimeout(200);

  const overflow = await page.evaluate(() => {
    return {
      docOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      contentOverflow: document.querySelector('.app-content') ? document.querySelector('.app-content')!.scrollWidth > document.querySelector('.app-content')!.clientWidth + 1 : false,
    };
  });
  push(`رزولوشن ${vp.name}: چیدمان بدون سرریز افقی`, !overflow.docOverflow && !overflow.contentOverflow, overflow);
}

await browser.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(results, null, 2), 'utf8');

const failed = (results.checks as { ok: boolean }[]).filter((c) => !c.ok).length;
console.log(`\nپایان آزمون Strategy Tree و سایدبار در مرورگر — ${failed} خطا`);
process.exit(failed ? 1 : 0);
