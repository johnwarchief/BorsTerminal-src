// Phase C/D startup probe: attach to an existing WebView2/Chromium CDP endpoint,
// log in, visit the three pages, and timestamp when each becomes actually usable.
// It never launches or kills the app; the Python orchestrator owns the process.
//
// Env: CDP_URL, APP_URL, SYMBOL (optional), OUT_JSON (optional)
import fs from 'node:fs';
import puppeteer from 'puppeteer-core';

const CDP_URL = process.env.CDP_URL || 'http://127.0.0.1:9333';
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:8000';
const SYMBOL = process.env.SYMBOL || 'فولاد';
const OUT = process.env.OUT_JSON || '';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const epoch = () => Date.now();
const rel = (t0) => Math.round((Date.now() - t0) * 10) / 10;

const out = {
  probe: 'phase_c_probe/1',
  cdp_url: CDP_URL,
  app_url: APP_URL,
  symbol: SYMBOL,
  connected_at: null,
  target_count: null,
  events: {},
  states: {},
  metrics: {},
  resources: [],
  errors: [],
  warnings: [],
};

function ev(name, extra = {}) {
  if (!out.events[name]) out.events[name] = { epoch_ms: epoch(), ...extra };
  return out.events[name];
}

async function mark(page, name, extra = {}) {
  if (out.events[name]) return out.events[name];
  let perf = null;
  try {
    perf = await page.evaluate(() => ({
      perf_ms: performance.now(),
      time_origin: performance.timeOrigin,
      nav_start: performance.getEntriesByType('navigation')[0]?.startTime ?? null,
    }));
  } catch (e) {
    perf = { error: String(e).slice(0, 120) };
  }
  return ev(name, { ...perf, ...extra });
}

async function metrics(page, name) {
  try {
    const m = await page.metrics();
    out.metrics[name] = {
      JSHeapUsedSize: m.JSHeapUsedSize ?? null,
      JSHeapTotalSize: m.JSHeapTotalSize ?? null,
      Nodes: m.Nodes ?? null,
      Documents: m.Documents ?? null,
      LayoutCount: m.LayoutCount ?? null,
    };
  } catch (e) {
    out.metrics[name] = { error: String(e).slice(0, 120) };
  }
}

function watch(page) {
  page.on('console', (m) => {
    if (m.type() === 'error') {
      out.errors.push({ kind: 'console', text: m.text().slice(0, 500), at_ms: epoch() });
    } else if (m.type() === 'warning') {
      out.warnings.push({ kind: 'console', text: m.text().slice(0, 300), at_ms: epoch() });
    }
  });
  page.on('pageerror', (e) => {
    out.errors.push({ kind: 'pageerror', text: String(e.message || e).slice(0, 500), at_ms: epoch() });
  });
  page.on('requestfailed', (r) => {
    const u = r.url();
    if (!/favicon|\.png|\.svg/i.test(u)) {
      out.errors.push({
        kind: 'requestfailed', url: u.slice(0, 300),
        text: String(r.failure()?.errorText || '').slice(0, 200), at_ms: epoch(),
      });
    }
  });
}

async function waitAny(page, selectors, timeout) {
  return page.waitForFunction(
    (sels) => sels.some((s) => document.querySelector(s)),
    { timeout, polling: 100 },
    selectors,
  );
}

async function setInput(page, selector, value) {
  await page.$eval(selector, (el, v) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    if (setter) setter.call(el, v); else el.value = v;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, value);
}

async function getResources(page) {
  try {
    return await page.evaluate(() => performance.getEntriesByType('resource')
      .filter((e) => e.name.includes('/api/'))
      .map((e) => ({
        name: e.name.replace(location.origin, ''),
        start_ms: Math.round(e.startTime * 10) / 10,
        duration_ms: Math.round(e.duration * 10) / 10,
        transfer_size: e.transferSize ?? null,
        encoded_body_size: e.encodedBodySize ?? null,
        decoded_body_size: e.decodedBodySize ?? null,
        initiator: e.initiatorType || null,
        response_status: e.responseStatus ?? null,
      })));
  } catch {
    return [];
  }
}

async function main() {
  const tConnect = epoch();
  let browser = null;
  for (let i = 0; i < 120; i++) {
    try {
      browser = await puppeteer.connect({ browserURL: CDP_URL, defaultViewport: null });
      break;
    } catch {
      await sleep(250);
    }
  }
  if (!browser) throw new Error('CDP connect timeout');
  out.connected_at = { epoch_ms: epoch(), rel_to_probe_ms: rel(tConnect) };

  const pages = await browser.pages();
  out.target_count = pages.length;
  const page = pages.find((p) => p.url().startsWith(APP_URL))
    || pages.find((p) => !p.url().startsWith('devtools://'))
    || pages[0];
  if (!page) throw new Error('no page target');
  watch(page);

  // Wait until the boot page has handed over to the app (or we are already there).
  for (let i = 0; i < 240; i++) {
    const u = page.url();
    if (u.startsWith(APP_URL) || (await page.$('input[autocomplete="username"]'))) break;
    await sleep(250);
  }
  await page.waitForFunction(() => document.readyState !== 'loading', { timeout: 30000 });
  await mark(page, 'app_document_ready', { url: page.url() });
  await metrics(page, 'app_document_ready');

  // Login gate is client-side; sessionStorage does not survive a new app window.
  const login = await page.$('input[autocomplete="username"]');
  if (login) {
    await mark(page, 'login_ready');
    await setInput(page, 'input[autocomplete="username"]', 'admin');
    await setInput(page, 'input[autocomplete="current-password"]', 'bors123');
    const values = await page.evaluate(() => Array.from(document.querySelectorAll('input'))
      .map((i) => ({ type: i.type, value: i.value })));
    out.states.login_values = values;
    const tSubmit = epoch();
    await page.click('button[type="submit"]');
    ev('login_submit', { epoch_ms: tSubmit });
    await waitAny(page, [
      '[data-testid="fts-funnel-workspace"]',
      '[data-testid="master-breadcrumb"]',
      '[data-testid="master-open-funnel"]',
    ], 30000);
    await mark(page, 'master_ready');
  } else {
    ev('login_skipped');
    await waitAny(page, ['[data-testid="fts-funnel-workspace"]', '[data-testid="master-breadcrumb"]'], 30000);
    await mark(page, 'master_ready');
  }
  await metrics(page, 'master_ready');

  // Market board: first rendered row, virtualized so 30 rows is the expected cap.
  await mark(page, 'market_nav_begin');
  await page.evaluate(() => { location.hash = '#/market'; });
  await waitAny(page, ['[data-testid="market-page"]'], 30000);
  await page.waitForFunction(
    () => document.querySelectorAll('[data-testid="tape-row"]').length > 0,
    { timeout: 45000, polling: 100 },
  );
  await mark(page, 'market_rows_visible', {
    rows: await page.evaluate(() => document.querySelectorAll('[data-testid="tape-row"]').length),
  });
  await sleep(1000);
  out.states.market_rows_after_1s = await page.evaluate(
    () => document.querySelectorAll('[data-testid="tape-row"]').length,
  );
  await metrics(page, 'market_ready');

  // Technical: a canvas in the active chart host AND the FTS freshness line with
  // a real last-bar date. The previous probe falsely waited for the ffc host while
  // klinecharts is the default, so accept either engine host.
  await mark(page, 'technical_nav_begin');
  await page.evaluate((s) => { location.hash = `#/technical/${encodeURIComponent(s)}`; }, SYMBOL);
  await waitAny(page, ['[data-testid="chart-area"]'], 30000);
  try {
    // A canvas and the FTS strip can both exist while /api/chart is failing:
    // on origin/main 01ded7d the route returned 422 and this probe still called
    // the chart "ready". Require a successful chart response with a real body
    // and a freshness line that names an actual analysis bar count.
    await page.waitForFunction(() => {
      const chart = document.querySelector('[data-testid="chart-area"]');
      const canvas = chart && chart.querySelector('canvas');
      const fresh = document.querySelector('[data-testid="fts-layer-freshness"]');
      const text = fresh?.textContent || '';
      const chartEntries = performance.getEntriesByType('resource')
        .filter((e) => e.name.includes('/api/chart/'));
      const chartOk = chartEntries.some((e) =>
        (e.responseStatus === 200 || e.responseStatus == null)
        && (e.decodedBodySize || 0) > 1000);
      return !!canvas && canvas.width > 0 && canvas.height > 0
        && /[۰-۹0-9]+\s*کندل/.test(text) && chartOk;
    }, { timeout: 60000, polling: 100 });
    const chartEntries = await page.evaluate(() => performance.getEntriesByType('resource')
      .filter((e) => e.name.includes('/api/chart/'))
      .map((e) => ({
        name: e.name.replace(location.origin, ''),
        duration_ms: Math.round(e.duration * 10) / 10,
        status: e.responseStatus ?? null,
        transfer: e.transferSize ?? null,
        encoded: e.encodedBodySize ?? null,
        decoded: e.decodedBodySize ?? null,
      })));
    await mark(page, 'technical_ready', {
      ...(await page.evaluate(() => ({
        chart_host: document.querySelector('[data-testid="ffc-chart-host"]') ? 'ffc'
          : document.querySelector('[data-testid="nn-chart-host"]') ? 'nn' : 'other',
        freshness: document.querySelector('[data-testid="fts-layer-freshness"]')?.textContent?.trim() || '',
        bars: document.querySelector('[data-testid="fts-layer-freshness"]')?.textContent
          ?.match(/([۰-۹0-9]+)\s*کندل/)?.[1] || null,
        last_bar: document.querySelector('[data-testid="fts-layer-freshness"]')?.textContent
          ?.match(/آخرین کندل:\s*([^·]+)/)?.[1]?.trim() || null,
        canvas: (() => {
          const c = document.querySelector('[data-testid="chart-area"] canvas');
          return c ? { w: c.width, h: c.height } : null;
        })(),
      }))),
      chart_api: chartEntries,
    });
  } catch (e) {
    ev('technical_timeout', {
      chart_host: await page.evaluate(() => document.querySelector('[data-testid="ffc-chart-host"]') ? 'ffc'
        : document.querySelector('[data-testid="nn-chart-host"]') ? 'nn' : 'other'),
      freshness: await page.evaluate(() => document.querySelector('[data-testid="fts-layer-freshness"]')?.textContent || null),
      chart_api: await page.evaluate(() => performance.getEntriesByType('resource')
        .filter((x) => x.name.includes('/api/chart/'))
        .map((x) => ({ name: x.name.replace(location.origin, ''),
          status: x.responseStatus ?? null, decoded: x.decodedBodySize ?? null }))),
    });
    out.errors.push({ kind: 'timeout', text: `technical: ${e.message}`.slice(0, 400), at_ms: epoch() });
  }
  await metrics(page, 'technical_ready');

  // Fundamental: the page shell appears before data; wait for the FTS summary or
  // the holding P/NAV panel, whichever is available for this symbol.
  await mark(page, 'fundamental_nav_begin');
  await page.evaluate((s) => { location.hash = `#/fundamental/${encodeURIComponent(s)}`; }, SYMBOL);
  await waitAny(page, ['[data-testid="fundamental-page"]'], 30000);
  try {
    await waitAny(page, ['[data-testid="fts-strategy-summary"]', '[data-testid="holding-pnav-panel"]'], 45000);
    await mark(page, 'fundamental_ready');
  } catch (e) {
    ev('fundamental_timeout');
    out.errors.push({ kind: 'timeout', text: `fundamental: ${e.message}`.slice(0, 400), at_ms: epoch() });
  }
  await metrics(page, 'fundamental_ready');

  out.resources = await getResources(page);
  // A short idle sample after the last page is usable; RAM sampling is done by Python.
  await sleep(2000);
  await metrics(page, 'idle_2s');
  out.finished_at = { epoch_ms: epoch() };

  if (OUT) fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf8');
  console.log(JSON.stringify({
    ok: !out.errors.some((e) => e.kind === 'timeout'),
    events: out.events,
    errors: out.errors.length,
  }));
  try { await browser.disconnect(); } catch { /* already gone */ }
}

main().catch((e) => {
  out.fatal = String(e && e.stack || e).slice(0, 2000);
  out.finished_at = { epoch_ms: epoch() };
  if (OUT) fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf8');
  console.error('PROBE_FATAL', out.fatal);
  process.exitCode = 2;
});
