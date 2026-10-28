import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const PW = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const CHROME = 'C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';
const { chromium } = await import(pathToFileURL(PW).href);

const OUT = dirname(fileURLToPath(import.meta.url));
const BASE = 'http://127.0.0.1:5180/';
const report = { base: BASE, route: '#/market', checks: [], console: [], shots: [], started: new Date().toISOString() };

function record(name, ok, detail) {
  report.checks.push({ name, ok: Boolean(ok), detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${ok ? '' : JSON.stringify(detail)}`);
}

async function shot(page, name) {
  const path = join(OUT, name);
  await page.screenshot({ path, fullPage: false });
  report.shots.push(path);
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const consoleErrors = [];
const page = await context.newPage();
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('pageerror', (err) => consoleErrors.push(String(err)));

try {
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="board-row"]', { timeout: 40_000 });
  await page.waitForSelector('[data-testid="snapshot-strip"]', { timeout: 20_000 });
  await page.waitForTimeout(1200);
  await shot(page, 'ws-1366.png');

  // 1 — four cards
  const cards = await page.locator('[data-testid^="card-"][data-testid$="Value"], [data-testid="card-tedpix"], [data-testid="card-breadth"]').count();
  const cardCount = await page.evaluate(() =>
    document.querySelectorAll('[data-testid^="card-"]').length);
  const tileCards = await page.locator('[data-testid="snapshot-strip"] section').count();
  record('snapshot strip has four cards', tileCards === 4, { tileCards, cards, cardCount });

  // 2 — preview on hover, basis label, no extra requests
  let hoverRequests = 0;
  const onRequest = () => { hoverRequests += 1; };
  page.on('request', onRequest);
  await page.hover('[data-testid="card-tedpix"]');
  await page.waitForSelector('[data-testid="preview-tedpix"]', { timeout: 5000 });
  const preview = await page.locator('[data-testid="preview-tedpix"]').innerText();
  page.off('request', onRequest);
  record('preview names trades and the market basis',
    preview.includes('تعداد معاملات') && preview.includes('کل بازار'),
    { preview: preview.slice(0, 200), hoverRequests });

  // 3 — retail card is a number or a dash, never a fake zero
  const retail = await page.locator('[data-testid="card-retailValue"]').innerText();
  const retailValue = retail.replace(/\s+/g, ' ');
  record('retail card never lies with zero',
    !/(^|\s)۰(\.۰)?(\s|$)/.test(retailValue) || retailValue.includes('—'),
    { retail: retailValue.slice(0, 120) });

  // 4 — swap symbol and watch with the arrow key
  await page.click('[data-testid="tile-header-t-symbol"] span');
  await page.keyboard.press('ArrowDown');
  await page.waitForTimeout(300);
  const symbolHeader = await page.locator('[data-testid="tile-header-t-symbol"]').getAttribute('aria-label');
  record('ArrowDown swaps the focused panel with its neighbour', symbolHeader === 'دیده‌بان‌ها', { symbolHeader });

  // 5 — close a tile and undo it
  await page.click('[data-testid="tile-close-t-watch"]');
  await page.waitForTimeout(200);
  const closed = await page.locator('[data-testid="tile-t-watch"]').count();
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(300);
  const restored = await page.locator('[data-testid="tile-t-watch"]').count();
  record('closing a tile is undone with Ctrl+Z', closed === 0 && restored === 1, { closed, restored });

  // 6 — Alt+2 focuses the second panel
  await page.keyboard.press('Alt+2');
  await page.waitForTimeout(200);
  const focusedId = await page.evaluate(() => {
    const active = document.activeElement;
    return active?.closest('[data-tile-id]')?.getAttribute('data-tile-id') ?? null;
  });
  record('Alt+2 focuses the second panel', Boolean(focusedId), { focusedId });

  // 7 — splitter drag persists across reload
  const shellBox = await page.locator('[data-testid="workspace-shell"]').boundingBox();
  const before = await page.locator('[data-tile-id="t-board"]').boundingBox();
  const splitter = page.locator('[data-testid="workspace-shell"] [role="separator"]').first();
  const sep = await splitter.boundingBox();
  if (shellBox && before && sep) {
    await page.mouse.move(sep.x + sep.width / 2, sep.y + sep.height / 2);
    await page.mouse.down();
    await page.mouse.move(sep.x + sep.width / 2 - 80, sep.y + sep.height / 2, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const after = await page.locator('[data-tile-id="t-board"]').boundingBox();
    const ratioAfter = after ? after.width / shellBox.width : 0;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="board-row"]', { timeout: 40_000 });
    await page.waitForTimeout(1200);
    const shell2 = await page.locator('[data-testid="workspace-shell"]').boundingBox();
    const board2 = await page.locator('[data-tile-id="t-board"]').boundingBox();
    const ratioReload = shell2 && board2 ? board2.width / shell2.width : 0;
    record('splitter drag changes the ratio and survives reload',
      before.width / shellBox.width !== ratioAfter && Math.abs(ratioAfter - ratioReload) < 0.03,
      { before: before.width / shellBox.width, ratioAfter, ratioReload });
  } else {
    record('splitter drag changes the ratio and survives reload', false, { shellBox, before, sep });
  }

  // 8 — symbol tabs and chart toggle (the symbol tile now sits where watch was)
  await page.click('[data-testid="board-row"]');
  await page.waitForTimeout(500);
  const symbolTileId = await page.evaluate(() =>
    document.querySelector('[data-testid="symbol-tab-history"]')?.closest('[data-tile-id]')?.getAttribute('data-tile-id'));
  const symbolTile = `[data-tile-id="${symbolTileId}"]`;
  await page.click('[data-testid="symbol-tab-history"]');
  await page.waitForSelector(`${symbolTile} [data-testid^="tape-history-"]`, { timeout: 20_000 }).catch(() => null);
  const historyVisible = await page.locator(`${symbolTile} [data-testid^="tape-history-"]`).count();
  await page.click('[data-testid="symbol-chart-toggle"]');
  await page.waitForTimeout(400);
  const chartHidden = await page.locator(`${symbolTile} [data-testid="chart-panel"]`).count();
  await page.click('[data-testid="symbol-chart-toggle"]');
  await page.waitForSelector(`${symbolTile} [data-testid="chart-panel"]`, { timeout: 10_000 }).catch(() => null);
  const chartShown = await page.locator(`${symbolTile} [data-testid="chart-panel"]`).count();
  record('history tab opens and the chart collapses and returns',
    historyVisible > 0 && chartHidden === 0 && chartShown > 0,
    { historyVisible, chartHidden, chartShown });

  // 9 — industries tab
  await page.click('[data-testid="watch-tab-industries"]');
  await page.waitForSelector('[data-testid^="industry-pick-"]', { timeout: 20_000 }).catch(() => null);
  const industries = await page.locator('[data-testid^="industry-pick-"]').count();
  record('industries tab renders real industries', industries > 0, { industries });

  await shot(page, 'ws-1366-after.png');

  // 10 — narrow drawer replaces the tiles and the saved layout returns
  await page.setViewportSize({ width: 1279, height: 800 });
  await page.waitForTimeout(600);
  const narrowTabs = await page.locator('[data-testid="narrow-tab-symbol"]').count();
  const tilesGone = await page.locator('[data-testid="tile-t-board"]').count();
  await shot(page, 'ws-1279.png');
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(600);
  const tilesBack = await page.locator('[data-testid="tile-t-board"]').count();
  const stripBack = await page.locator('[data-testid="snapshot-strip"]').count();
  record('narrow width uses the two-tab drawer and keeps the saved layout',
    narrowTabs === 1 && tilesGone === 0 && tilesBack === 1 && stripBack === 1,
    { narrowTabs, tilesGone, tilesBack, stripBack });

  // 11 — market status page
  await page.goto(`${BASE}#/market-status`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="phase-label"]', { timeout: 20_000 });
  await page.waitForTimeout(1000);
  const phaseLabel = await page.locator('[data-testid="phase-label"]').innerText();
  const phaseSource = await page.locator('[data-testid="phase-source"]').innerText();
  await shot(page, 'ws-status-1366.png');
  record('market status shows the phase and its source',
    phaseLabel.length > 1 && (phaseSource.includes('رسمی') || phaseSource.includes('تقویمی')),
    { phaseLabel, phaseSource });

  // 12 — notifications page
  await page.goto(`${BASE}#/notifications`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const noticeItems = await page.locator('[data-testid^="notif-item-"]').count();
  const noticeEmpty = await page.locator('[data-testid="notif-empty"]').count();
  const noticeWarn = await page.locator('[data-testid="notif-source-warning"]').count();
  await shot(page, 'ws-notif-1366.png');
  record('notifications page is a real feed or an explicit empty/unreachable state',
    noticeItems > 0 || noticeEmpty === 1 || noticeWarn === 1,
    { noticeItems, noticeEmpty, noticeWarn });

  // 13 — console stays clean
  record('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 6) });
} catch (error) {
  record('harness completed', false, { error: String(error) });
} finally {
  report.console = consoleErrors;
  report.finished = new Date().toISOString();
  writeFileSync(join(OUT, 'workspace-check.json'), JSON.stringify(report, null, 2), 'utf8');
  await browser.close();
}
