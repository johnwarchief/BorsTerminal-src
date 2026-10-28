import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const PW = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const CHROME = 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const { chromium } = await import(pathToFileURL(PW).href);

const OUT_DIR = dirname(fileURLToPath(import.meta.url));
const BASE = 'http://127.0.0.1:5180/';
const ROUTE = '#/market';
const SIZES = [
  { width: 1366, height: 768 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
];
const report = { base: BASE, route: ROUTE, source: 'frontend-v2 source via Vite 5180 -> API 8101', sizes: {} };
const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok: Boolean(ok), detail });
  if (!ok) console.error(`FAIL ${name}: ${JSON.stringify(detail)}`);
};

async function waitForBoard(page) {
  await page.waitForSelector('[data-testid="board-table"]', { timeout: 20_000 });
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="board-row"]').length > 0,
    null,
    { timeout: 20_000 },
  );
  await page.waitForTimeout(800);
}

async function metrics(page) {
  return page.evaluate(() => {
    const de = document.documentElement;
    const box = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        text: (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 180),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        display: cs.display,
      };
    };
    return {
      href: location.href,
      viewport: { width: de.clientWidth, height: de.clientHeight },
      overflowX: de.scrollWidth - de.clientWidth,
      pageTitle: document.title,
      boardCount: document.querySelector('[data-testid="board-count"]')?.textContent?.replace(/\s+/g, ' ').trim() ?? null,
      renderedRows: document.querySelectorAll('[data-testid="board-row"]').length,
      toolbar: box('[data-testid="board-toolbar"]'),
      table: box('[data-testid="board-table"]'),
      search: box('[data-testid="board-search"]'),
      savedViews: box('[data-testid="saved-views-btn"]'),
      exportButton: box('[data-testid="export-board"]'),
      drawerOpen: document.querySelector('[data-testid="market-workspace"]')?.getAttribute('data-drawer') ?? null,
    };
  });
}

async function activeTestId(page) {
  return page.evaluate(() => {
    const el = document.activeElement;
    return {
      testId: el?.getAttribute('data-testid') ?? null,
      ariaLabel: el?.getAttribute('aria-label') ?? null,
      boardIndex: el?.getAttribute('data-board-index') ?? null,
      tag: el?.tagName ?? null,
    };
  });
}

const browser = await chromium.launch({ headless: true, executablePath: CHROME });
try {
  for (const size of SIZES) {
    const context = await browser.newContext({ viewport: size, acceptDownloads: true });
    const page = await context.newPage();
    const consoleErrors = [];
    const pageErrors = [];
    const failedRequests = [];
    const apiResponses = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 240));
    });
    page.on('pageerror', (error) => pageErrors.push(String(error.message).slice(0, 240)));
    page.on('requestfailed', (request) => failedRequests.push({
      url: request.url(),
      reason: request.failure()?.errorText ?? 'unknown',
    }));
    page.on('response', (response) => {
      const url = new URL(response.url());
      if (url.pathname.startsWith('/api/')) apiResponses.push({
        status: response.status(),
        path: url.pathname,
      });
    });

    await page.goto(`${BASE}${ROUTE}`, { waitUntil: 'domcontentloaded' });
    await waitForBoard(page);
    const initial = await metrics(page);
    const shot = join(OUT_DIR, `board-${size.width}x${size.height}.png`);
    await page.screenshot({ path: shot });

    check(`${size.width}: route and data rendered`, initial.href.endsWith('#/market') && initial.renderedRows > 0, initial);
    check(`${size.width}: no horizontal page overflow`, initial.overflowX === 0, initial.overflowX);

    const result = { initial, screenshot: shot, interactions: {} };

    if (size.width === 1366) {
      await page.click('[data-testid="saved-views-btn"]');
      check('1366: saved-view menu opens with focused name input', await page.getByTestId('view-name-input').evaluate((el) => el === document.activeElement));
      await page.fill('[data-testid="view-name-input"]', 'morning');
      await page.click('[data-testid="save-view-btn"]');
      await page.waitForSelector('[data-testid="view-apply-morning"]');
      const savedState = await page.evaluate(() => {
        const raw = localStorage.getItem('bors-market-v2');
        if (!raw) return { count: 0, hasState: false };
        const parsed = JSON.parse(raw);
        return {
          count: parsed?.state?.savedViews?.length ?? 0,
          hasState: Boolean(parsed?.state?.savedViews?.[0]?.state),
        };
      });
      check('1366: saved view persists complete state', savedState.count === 1 && savedState.hasState, savedState);
      const viewsShot = join(OUT_DIR, 'board-1366x768-views.png');
      await page.screenshot({ path: viewsShot });
      result.interactions.savedViews = { ...savedState, screenshot: viewsShot };

      await page.keyboard.press('Escape');
      const afterEscape = await activeTestId(page);
      check('1366: Escape returns focus to views trigger', afterEscape.testId === 'saved-views-btn', afterEscape);

      await page.fill('[data-testid="board-search"]', 'zzz');
      await page.waitForTimeout(250);
      await page.click('[data-testid="saved-views-btn"]');
      await page.click('[data-testid="view-apply-morning"]');
      await page.waitForFunction(() => document.querySelector('[data-testid="board-search"]')?.value === '');
      const afterApply = {
        query: await page.getByTestId('board-search').inputValue(),
        focus: await activeTestId(page),
        rows: await page.locator('[data-testid="board-row"]').count(),
      };
      check('1366: applying view restores query and rows', afterApply.query === '' && afterApply.rows > 0, afterApply);
      check('1366: applying view returns focus to trigger', afterApply.focus.testId === 'saved-views-btn', afterApply.focus);

      await page.click('[data-testid="saved-views-btn"]');
      const remove = page.locator('[data-testid="view-apply-morning"] + button');
      await remove.focus();
      await remove.click();
      const afterDelete = await activeTestId(page);
      check('1366: deleting a view moves focus to name input', afterDelete.testId === 'view-name-input', afterDelete);
      const countAfterDelete = await page.evaluate(() => {
        const raw = localStorage.getItem('bors-market-v2');
        return raw ? (JSON.parse(raw)?.state?.savedViews?.length ?? 0) : 0;
      });
      check('1366: deleted view is removed from storage', countAfterDelete === 0, countAfterDelete);
      await page.keyboard.press('Escape');

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 20_000 }),
        page.click('[data-testid="export-board"]'),
      ]);
      const downloadPath = await download.path();
      const csv = readFileSync(downloadPath);
      const csvText = csv.toString('utf8');
      const exportEvidence = {
        filename: download.suggestedFilename(),
        bytes: csv.length,
        sha256: createHash('sha256').update(csv).digest('hex'),
        hasUtf8Bom: csv.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf])),
        hasSeparatorHint: csvText.startsWith('\ufeffsep=;\r\n'),
        hasSourceProvenance: csvText.includes('# منبع;/api/market'),
        hasSearchProvenance: csvText.includes('# جستجو;'),
        nonEmptyLines: csvText.split('\r\n').filter(Boolean).length,
      };
      check('1366: CSV download has BOM and provenance', exportEvidence.hasUtf8Bom && exportEvidence.hasSeparatorHint && exportEvidence.hasSourceProvenance, exportEvidence);
      result.interactions.export = exportEvidence;

      await page.keyboard.press('Control+K');
      await page.waitForFunction(() => document.activeElement?.getAttribute('data-testid') === 'board-search');
      check('1366: Ctrl+K focuses search', true, await activeTestId(page));

      const rows = page.locator('[data-testid="board-row"]');
      await rows.first().focus();
      await page.keyboard.press('ArrowDown');
      await page.waitForFunction(() => document.activeElement?.getAttribute('data-board-index') === '1');
      check('1366: ArrowDown moves roving row focus', true, await activeTestId(page));

      const countBeforeFilter = await page.getByTestId('board-count').textContent();
      await page.click('[data-testid="tape-f_clock"]');
      await page.waitForFunction(() => document.querySelector('[data-testid="tape-f_clock"]')?.getAttribute('aria-pressed') === 'true');
      await page.waitForTimeout(400);
      const filtered = {
        before: countBeforeFilter?.replace(/\s+/g, ' ').trim(),
        after: (await page.getByTestId('board-count').textContent())?.replace(/\s+/g, ' ').trim(),
        rows: await page.locator('[data-testid="board-row"]').count(),
      };
      check('1366: tape filter changes visible count', filtered.before !== filtered.after && filtered.rows > 0, filtered);
      await page.click('[data-testid="tape-f_clock"]');
      await page.waitForTimeout(300);

      await page.click('[data-testid="watch-tab-clock"]');
      await page.waitForSelector('[data-testid="watch-body"]');
      const watch = {
        height: await page.getByTestId('watch-body').evaluate((el) => Math.round(el.getBoundingClientRect().height)),
        textLength: (await page.getByTestId('watch-body').textContent())?.trim().length ?? 0,
        scope: (await page.getByTestId('watch-scope-label').textContent())?.replace(/\s+/g, ' ').trim(),
        count: (await page.getByTestId('watch-count-clock').textContent())?.replace(/\s+/g, ' ').trim(),
      };
      check('1366: clock watch panel opens with scope and count', watch.height > 0 && watch.textLength > 0 && watch.scope?.includes('کل تابلو') && Boolean(watch.count), watch);
      const watchShot = join(OUT_DIR, 'board-1366x768-watch.png');
      await page.screenshot({ path: watchShot });
      result.interactions.watch = { ...watch, screenshot: watchShot };
      await page.click('[data-testid="watch-close"]');

      await page.locator('[data-testid="board-row"]').first().click();
      await page.waitForSelector('[role="dialog"]');
      await page.waitForSelector('[data-testid="order-book"]');
      await page.waitForTimeout(800);
      const drawer = await page.evaluate(() => {
        const el = document.querySelector('[role="dialog"]');
        const rect = el?.getBoundingClientRect();
        const search = document.querySelector('[data-testid="board-search"]');
        const book = document.querySelector('[data-testid="order-book"]');
        return {
          width: rect ? Math.round(rect.width) : 0,
          height: rect ? Math.round(rect.height) : 0,
          searchDisplay: search ? getComputedStyle(search).display : null,
          overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          orderBookSection: Boolean(document.querySelector('[data-testid="drawer-orderbook-section"]')),
          historySection: Boolean(document.querySelector('[data-testid="drawer-history-section"]')),
          bookFreshness: book?.getAttribute('data-freshness') ?? null,
          bookSessionNote: Boolean(document.querySelector('[data-testid="order-book-session-note"]')),
          bookTotals: Boolean(document.querySelector('[data-testid="order-book-totals"]')),
        };
      });
      check('1366: narrow drawer opens, hides search and keeps page width', drawer.width > 0 && drawer.searchDisplay === 'none' && drawer.overflowX === 0, drawer);
      check(
        '1366: depth freshness agrees with its totals',
        Boolean(drawer.bookFreshness)
          && (drawer.bookFreshness === 'current' ? drawer.bookTotals : !drawer.bookTotals && drawer.bookSessionNote),
        drawer,
      );
      const drawerShot = join(OUT_DIR, 'board-1366x768-drawer.png');
      await page.screenshot({ path: drawerShot });
      result.interactions.drawer = { ...drawer, screenshot: drawerShot };

      await page.keyboard.press('Control+K');
      await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
      await page.waitForFunction(() => document.activeElement?.getAttribute('data-testid') === 'board-search');
      const afterDrawerShortcut = await page.evaluate(() => ({
        focus: document.activeElement?.getAttribute('data-testid'),
        searchDisplay: getComputedStyle(document.querySelector('[data-testid="board-search"]')).display,
        drawerOpen: document.querySelector('[data-testid="market-workspace"]')?.getAttribute('data-drawer'),
      }));
      check('1366: Ctrl+K closes drawer and focuses visible search', afterDrawerShortcut.focus === 'board-search' && afterDrawerShortcut.searchDisplay !== 'none' && afterDrawerShortcut.drawerOpen === 'closed', afterDrawerShortcut);

      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.locator('[data-testid="board-row"]').first().click();
      await page.waitForSelector('[role="dialog"]');
      const reduced = await page.evaluate(() => ({
        matches: matchMedia('(prefers-reduced-motion: reduce)').matches,
        drawerAnimation: getComputedStyle(document.querySelector('[role="dialog"]')).animationDuration,
      }));
      check('1366: reduced-motion shortens drawer animation', reduced.matches && parseFloat(reduced.drawerAnimation) < 0.001, reduced);
      result.interactions.reducedMotion = reduced;
      await page.keyboard.press('Escape');
    } else {
      check(`${size.width}: toolbar labels are visible`, (initial.savedViews?.text ?? '').includes('نماها'), initial.savedViews);
    }

    const successfulPaths = new Set(apiResponses.filter((item) => item.status >= 200 && item.status < 300).map((item) => item.path));
    const hardFailedRequests = failedRequests.filter((item) => item.reason !== 'net::ERR_ABORTED');
    const cancelledRequests = failedRequests.filter((item) => item.reason === 'net::ERR_ABORTED');
    const unresolvedCancellations = cancelledRequests.filter((item) => !successfulPaths.has(new URL(item.url).pathname));
    const serverErrors = apiResponses.filter((item) => item.status >= 400);
    result.consoleErrors = consoleErrors.slice(0, 20);
    result.pageErrors = pageErrors.slice(0, 20);
    result.hardFailedRequests = hardFailedRequests.slice(0, 20);
    result.cancelledRequests = cancelledRequests.slice(0, 20);
    result.unresolvedCancellations = unresolvedCancellations;
    result.serverErrors = serverErrors;
    result.apiResponses = [...new Map(apiResponses.map((item) => [`${item.status} ${item.path}`, item])).values()];
    result.final = await metrics(page);
    check(`${size.width}: console and page errors absent`, consoleErrors.length === 0 && pageErrors.length === 0, {
      consoleErrors,
      pageErrors,
    });
    check(`${size.width}: no HTTP or transport errors; cancellations have a 2xx counterpart`, hardFailedRequests.length === 0 && serverErrors.length === 0 && unresolvedCancellations.length === 0, {
      hardFailedRequests,
      serverErrors,
      unresolvedCancellations,
      cancelledRequests,
    });
    report.sizes[size.width] = result;
    await context.close();
  }
} finally {
  await browser.close();
}

const failures = checks.filter((item) => !item.ok);
report.checks = checks;
report.failures = failures.length;
writeFileSync(join(OUT_DIR, 'live-check.json'), JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify({
  checks: checks.length,
  failures,
  consoleByWidth: Object.fromEntries(Object.entries(report.sizes).map(([width, data]) => [width, {
    consoleErrors: data.consoleErrors,
    pageErrors: data.pageErrors,
    hardFailedRequests: data.hardFailedRequests,
    cancelledRequests: data.cancelledRequests.length,
    unresolvedCancellations: data.unresolvedCancellations,
  }])),
  screenshots: Object.fromEntries(Object.entries(report.sizes).map(([width, data]) => [width, data.screenshot])),
}, null, 2));
if (failures.length) process.exitCode = 1;
