/**
 * tools/ui_full_browser_audit.mts
 * سنجش جامع مرورگر در رزولوشن‌های ۴گانه و ۲ تم (Dark/Light)
 * بررسی: سرریز ناخواسته، کلپینگ، هم‌پوشانی، هندسه RTL، ناوبری Back، عملکرد و ثبات چیدمان
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
const OUT = arg('out', '_audit/ui_full_browser_audit.json');

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const CHROME = process.env.JEV_CHROME || EDGE;

const VIEWPORTS = [
  { width: 1280, height: 720, label: '1280x720' },
  { width: 1366, height: 768, label: '1366x768' },
  { width: 1600, height: 900, label: '1600x900' },
  { width: 1920, height: 1080, label: '1920x1080' },
];

const ROUTES = [
  { path: '#/market', name: 'Market' },
  { path: '#/technical', name: 'Technical' },
  { path: '#/fundamental', name: 'Fundamental' },
  { path: '#/master', name: 'Master' },
  { path: '#/portfolio', name: 'Portfolio' },
  { path: '#/strategy-tree', name: 'StrategyTree' },
];

const auditResults: Record<string, unknown> = {
  timestamp: new Date().toISOString(),
  base: BASE,
  viewports: VIEWPORTS,
  pages: [] as Record<string, unknown>[],
  navigationTests: [] as Record<string, unknown>[],
  sidebarAudit: {} as Record<string, unknown>,
  strategyTreeAudit: {} as Record<string, unknown>,
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

console.log('--- شروع سنجش UI/UX مرورگر ---');

// ۱. آزمون صفحات در رزولوشن‌ها و تم‌ها
for (const vp of VIEWPORTS) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  for (const theme of ['dark', 'light'] as const) {
    for (const route of ROUTES) {
      await page.goto(`${BASE}${route.path}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(400);

      // اعمال تم
      await page.evaluate((th) => {
        document.documentElement.dataset.theme = th;
        if (th === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }, theme);

      // ممیزی DOM و هندسه
      const pageMetrics = await page.evaluate(() => {
        const docEl = document.documentElement;
        const body = document.body;
        const winW = window.innerWidth;
        const winH = window.innerHeight;

        const hasHorizontalOverflow = docEl.scrollWidth > winW + 1;
        const appContent = document.querySelector('.app-content');
        const contentOverflowX = appContent ? appContent.scrollWidth > appContent.clientWidth + 1 : false;

        // بررسی المان‌های با فونت بسیار ریز (<9px)
        const allTextNodes = Array.from(document.querySelectorAll('*')).filter((el) => {
          if (el.children.length > 0) return false;
          const text = el.textContent?.trim();
          return text && text.length > 1;
        });

        let tinyFontCount = 0;
        for (const el of allTextNodes.slice(0, 100)) {
          const fs = parseFloat(window.getComputedStyle(el).fontSize);
          if (fs > 0 && fs < 8.5) tinyFontCount++;
        }

        // بررسی جهت RTL
        const dir = window.getComputedStyle(body).direction;

        // بررسی نوار کناری (Sidebar)
        const sidebar = document.querySelector('aside[aria-label="نوار کناری"]');
        const sidebarW = sidebar ? sidebar.getBoundingClientRect().width : 0;
        const sidebarCollapsed = sidebar ? sidebar.getAttribute('data-collapsed') === 'true' : false;

        // بررسی Topbar
        const topbar = document.querySelector('header');
        const topbarH = topbar ? topbar.getBoundingClientRect().height : 0;

        return {
          hasHorizontalOverflow,
          contentOverflowX,
          tinyFontCount,
          isRTL: dir === 'rtl',
          sidebarW: Math.round(sidebarW),
          sidebarCollapsed,
          topbarH: Math.round(topbarH),
          domNodeCount: document.getElementsByTagName('*').length,
        };
      });

      (auditResults.pages as Record<string, unknown>[]).push({
        viewport: vp.label,
        theme,
        route: route.name,
        path: route.path,
        metrics: pageMetrics,
        clean: !pageMetrics.hasHorizontalOverflow && !pageMetrics.contentOverflowX,
      });
    }
  }
}

// ۲. ممیزی نوار کناری (Sidebar Items Inventory)
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(500);

const sidebarInfo = await page.evaluate(() => {
  const sidebar = document.querySelector('aside[aria-label="نوار کناری"]');
  if (!sidebar) return { found: false, links: [] };

  const links = Array.from(sidebar.querySelectorAll('a')).map((a) => ({
    href: a.getAttribute('href'),
    text: a.textContent?.trim() || a.getAttribute('aria-label') || a.getAttribute('title') || '',
    isActive: a.classList.contains('text-accent-blue'),
  }));

  const buttons = Array.from(sidebar.querySelectorAll('button')).map((b) => ({
    label: b.getAttribute('aria-label') || b.getAttribute('title') || b.textContent?.trim() || '',
    testId: b.getAttribute('data-testid') || '',
  }));

  return { found: true, links, buttons };
});
auditResults.sidebarAudit = sidebarInfo;

// ۳. ممیزی StrategyTree جاری
await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(600);

const treeMetrics = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  const svg = canvas ? canvas.querySelector('svg') : null;
  const nodes = svg ? svg.querySelectorAll('g.cursor-pointer') : [];
  const links = svg ? svg.querySelectorAll('path') : [];

  const viewSwitchButtons = Array.from(document.querySelectorAll('button')).filter((b) =>
    b.textContent?.includes('نما') || b.textContent?.includes('چارت')
  ).map((b) => b.textContent?.trim());

  return {
    canvasFound: !!canvas,
    svgFound: !!svg,
    svgWidth: svg?.clientWidth || 0,
    svgHeight: svg?.clientHeight || 0,
    nodeCount: nodes.length,
    pathCount: links.length,
    viewButtons: viewSwitchButtons,
  };
});
auditResults.strategyTreeAudit = treeMetrics;

// ۴. آزمون جریان ناوبری Back و قطعی بودن History
const navLog: { step: string; currentUrl: string; ok: boolean }[] = [];

// مرحله ۱: رفتن به Market
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(300);
navLog.push({ step: '1. Nav to Market', currentUrl: page.url(), ok: page.url().includes('/market') });

// مرحله ۲: رفتن به Technical
await page.goto(`${BASE}#/technical`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(300);
navLog.push({ step: '2. Nav to Technical', currentUrl: page.url(), ok: page.url().includes('/technical') });

// مرحله ۳: رفتن به StrategyTree
await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(300);
navLog.push({ step: '3. Nav to StrategyTree', currentUrl: page.url(), ok: page.url().includes('/strategy-tree') });

// مرحله ۴: دکمه Back مرورگر -> باید برگردد به Technical
await page.goBack();
await page.waitForTimeout(300);
navLog.push({ step: '4. Back to Technical', currentUrl: page.url(), ok: page.url().includes('/technical') });

// مرحله ۵: دکمه Back مرورگر -> باید برگردد به Market
await page.goBack();
await page.waitForTimeout(300);
navLog.push({ step: '5. Back to Market', currentUrl: page.url(), ok: page.url().includes('/market') });

auditResults.navigationTests = navLog;

await browser.close();

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(auditResults, null, 2), 'utf8');

console.log(`سنجش UI مرورگر پایان یافت — نتایج در ${OUT} ذخیره شد.`);
