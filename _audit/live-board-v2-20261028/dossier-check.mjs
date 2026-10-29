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
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : ` ${JSON.stringify(detail)}`}`);
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
page.on('pageerror', (error) => consoleErrors.push(String(error)));

try {
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="board-row"]', { timeout: 40_000 });
  await page.waitForSelector('[data-testid="snapshot-strip"]', { timeout: 20_000 });
  await page.waitForTimeout(1000);

  const sidebarCount = await page.locator('[data-testid="symbol-sidebar"]').count();
  const dockCount = await page.locator('[data-testid="bottom-dock"]').count();
  const watchTiles = await page.locator('[data-testid="tile-t-watch"]').count();
  const symbolTiles = await page.locator('[data-testid="tile-t-symbol"]').count();
  const chartTiles = await page.locator('[data-testid="tile-t-chart"]').count();
  record('left sidebar and bottom dock exist and the symbol/chart tiles are gone',
    sidebarCount === 1 && dockCount === 1 && watchTiles === 1 && symbolTiles === 0 && chartTiles === 0,
    { sidebarCount, dockCount, watchTiles, symbolTiles, chartTiles });

  await page.click('[data-testid="board-row"]');
  await page.waitForSelector('[data-testid="symbol-title"]', { timeout: 20_000 });
  await page.waitForTimeout(700);
  const title = await page.locator('[data-testid="symbol-title"]').innerText();
  const price = await page.locator('[data-testid="symbol-price"]').innerText();
  const stats = await page.locator('[data-testid^="symbol-stat-"]').count();
  const chips = await page.locator('[data-testid^="symbol-tape-"]').count();
  record('sidebar shows the symbol at a glance: price, six stats and seven tape chips',
    title.length > 0 && price.length > 0 && stats === 6 && chips === 7,
    { title, price, stats, chips });

  await page.waitForFunction(
    () => !document.querySelector('[data-testid="tech-loading"]'),
    null,
    { timeout: 25_000 },
  ).catch(() => null);
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-testid="symbol-fund-summary"]');
    return node && (node.textContent.includes('محور قبول') || node.textContent.includes('در دسترس نیست'));
  }, null, { timeout: 25_000 }).catch(() => null);
  const symbolTech = await page.locator('[data-testid="symbol-tech"]').count();
  const techUnavailable = await page.locator('[data-testid="tech-unavailable"]').count();
  const techTrend = await page.locator('[data-testid="tech-trend"], [data-testid="tech-trend-unknown"]').count();
  const ma20 = await page.locator('[data-testid="tech-ma20"]').innerText().catch(() => '');
  const fund = await page.locator('[data-testid="symbol-fund-summary"]').innerText();
  record('technical block renders the real MA series and the fundamental summary is honest',
    symbolTech === 1 && techUnavailable === 0 && techTrend === 1 && ma20.length > 0
      && (fund.includes('محور قبول') || fund.includes('در دسترس نیست')),
    { symbolTech, techUnavailable, techTrend, ma20: ma20.slice(0, 80), fund: fund.slice(0, 160) });

  await page.waitForSelector('[data-testid="chart-panel"]', { timeout: 20_000 }).catch(() => null);
  await page.waitForSelector('[data-testid="fundamental-card-1_growth"], [data-testid="fundamental-error"]', { timeout: 25_000 }).catch(() => null);
  const charts = await page.locator('[data-testid="chart-panel"]').count();
  const cards = await page.locator('[data-testid^="fundamental-card-"]').count();
  const industry = await page.locator('[data-testid="fundamental-industry"]').count();
  const cardErrors = await page.locator('[data-testid="fundamental-error"]').count();
  record('bottom dock holds one chart and four detailed cards with the industry row',
    charts === 1 && cardErrors === 0 ? cards === 4 && industry === 1 : cardErrors === 1,
    { charts, cards, industry, cardErrors });

  await page.waitForFunction(
    () => !document.querySelector('[data-testid="chart-loading"]'),
    null,
    { timeout: 30_000 },
  ).catch(() => null);
  await page.waitForSelector('[data-testid="chart-panel"] canvas', { timeout: 30_000 }).catch(() => null);
  await page.waitForTimeout(400);
  const canvases = await page.locator('[data-testid="chart-panel"] canvas').count();
  record('dock chart loads its candles and paints a canvas', canvases > 0, { canvases });
  await shot(page, 'ws-1366-dossier.png');

  for (const [width, height, name] of [[1920, 1080, 'ws-1920-dossier.png'], [2560, 1440, 'ws-2560-dossier.png']]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(600);
    await page.waitForFunction(
      () => document.querySelector('[data-testid="chart-panel"] canvas') != null,
      null,
      { timeout: 10_000 },
    ).catch(() => null);
    await page.waitForTimeout(500);
    await shot(page, name);
  }
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(500);

  const sideBefore = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
  const sideSep = await page.locator('[data-testid="resize-sidebar"]').boundingBox();
  if (sideBefore && sideSep) {
    await page.mouse.move(sideSep.x + 1, sideSep.y + 20);
    await page.mouse.down();
    await page.mouse.move(sideSep.x + 49, sideSep.y + 20, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const sideAfter = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="symbol-title"]', { timeout: 40_000 });
    await page.waitForTimeout(900);
    const sideReload = await page.locator('[data-testid="symbol-sidebar"]').boundingBox();
    const drift = sideAfter && sideReload ? Math.abs(sideAfter.width - sideReload.width) : 99;
    record('sidebar resize widens the column and survives reload',
      sideAfter != null && sideAfter.width > sideBefore.width + 20 && drift <= 2,
      { before: sideBefore.width, after: sideAfter?.width, reload: sideReload?.width });
  } else {
    record('sidebar resize widens the column and survives reload', false, { sideBefore, sideSep });
  }

  const dockBefore = await page.locator('[data-testid="bottom-dock"]').boundingBox();
  const dockSep = await page.locator('[data-testid="resize-dock"]').boundingBox();
  if (dockBefore && dockSep) {
    await page.mouse.move(dockSep.x + 40, dockSep.y + 1);
    await page.mouse.down();
    await page.mouse.move(dockSep.x + 40, dockSep.y - 49, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const dockAfter = await page.locator('[data-testid="bottom-dock"]').boundingBox();
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="bottom-dock"]', { timeout: 40_000 });
    await page.waitForTimeout(900);
    const dockReload = await page.locator('[data-testid="bottom-dock"]').boundingBox();
    const drift = dockAfter && dockReload ? Math.abs(dockAfter.height - dockReload.height) : 99;
    record('dock resize grows the panel and survives reload',
      dockAfter != null && dockAfter.height > dockBefore.height + 20 && drift <= 2,
      { before: dockBefore.height, after: dockAfter?.height, reload: dockReload?.height });
  } else {
    record('dock resize grows the panel and survives reload', false, { dockBefore, dockSep });
  }

  await page.click('[data-testid="dock-toggle-fundamental"]');
  await page.waitForTimeout(300);
  const cardsOff = await page.locator('[data-testid="dock-fundamentals"]').count();
  const chartStays = await page.locator('[data-testid="chart-panel"]').count();
  await page.click('[data-testid="dock-toggle-fundamental"]');
  await page.waitForTimeout(300);
  const cardsOn = await page.locator('[data-testid="dock-fundamentals"]').count();
  await page.click('[data-testid="dock-toggle-chart"]');
  await page.waitForTimeout(300);
  const chartOff = await page.locator('[data-testid="dock-chart"]').count();
  const cardsStill = await page.locator('[data-testid="dock-fundamentals"]').count();
  await page.click('[data-testid="dock-toggle-chart"]');
  await page.waitForTimeout(300);
  record('each dock toggle hides only its own group',
    cardsOff === 0 && chartStays === 1 && cardsOn === 1 && chartOff === 0 && cardsStill === 1,
    { cardsOff, chartStays, cardsOn, chartOff, cardsStill });

  await page.click('[data-testid="tile-close-t-watch"]');
  await page.waitForTimeout(200);
  const closed = await page.locator('[data-testid="tile-t-watch"]').count();
  await page.keyboard.press('Control+z');
  await page.waitForTimeout(300);
  const restored = await page.locator('[data-testid="tile-t-watch"]').count();
  record('closing the watch tile is undone with Ctrl+Z', closed === 0 && restored === 1, { closed, restored });

  await page.setViewportSize({ width: 1279, height: 800 });
  await page.waitForTimeout(700);
  const narrowTabs = await page.locator('[data-testid="narrow-tab-symbol"]').count();
  const wideSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="wide"]').count();
  const narrowDock = await page.locator('[data-testid="bottom-dock"]').count();
  await page.click('[data-testid="narrow-tab-symbol"]');
  await page.waitForTimeout(500);
  const narrowSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="narrow"]').count();
  await shot(page, 'ws-1279-dossier.png');
  record('narrow width drops the wide sidebar and dock and uses the narrow sidebar',
    narrowTabs === 1 && wideSidebar === 0 && narrowDock === 0 && narrowSidebar === 1,
    { narrowTabs, wideSidebar, narrowDock, narrowSidebar });

  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(700);
  const backSidebar = await page.locator('[data-testid="symbol-sidebar"][data-variant="wide"]').count();
  const backDock = await page.locator('[data-testid="bottom-dock"]').count();
  record('returning to wide restores the saved sidebar and dock', backSidebar === 1 && backDock === 1,
    { backSidebar, backDock });

  record('no console errors', consoleErrors.length === 0, { consoleErrors: consoleErrors.slice(0, 6) });
} catch (error) {
  record('harness completed', false, { error: String(error) });
} finally {
  report.console = consoleErrors;
  report.finished = new Date().toISOString();
  writeFileSync(join(OUT, 'dossier-check.json'), JSON.stringify(report, null, 2), 'utf8');
  await browser.close();
}
