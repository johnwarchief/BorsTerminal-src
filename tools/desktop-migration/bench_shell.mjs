/**
 * Repeatable shell benchmark for BorsTerminal desktop migration (M0).
 *
 * Launches an already-running backend's shell window against the same data,
 * attaches to WebView2 over CDP, logs in with the documented local account,
 * and records cold/warm readiness, API/resource volume, JS heap and frame time.
 *
 * usage:
 *   node tools/desktop-migration/bench_shell.mjs --label pywebview-dev \
 *     --runs 3 --backend http://127.0.0.1:8102 --out artifacts/desktop-migration
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(fileURLToPath(new URL('../../frontend/package.json', import.meta.url)));
const puppeteer = require('puppeteer-core');

const ROOT = path.resolve(fileURLToPath(new URL('../..', import.meta.url)));
const nodeExe = process.execPath;

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
}

const label = arg('label', 'pywebview-dev');
const runs = Number(arg('runs', '3'));
const backend = arg('backend', 'http://127.0.0.1:8102');
const outRoot = path.resolve(arg('out', path.join(ROOT, 'artifacts/desktop-migration')));
const shellKind = arg('shell', 'pywebview'); // pywebview | exe
const shellPath = arg('path', path.join(ROOT, '.venv/Scripts/python.exe'));
const shellArgs = arg('args', 'bors_entry.py');
const port = new URL(backend).port || '8102';
const cdpBase = Number(arg('cdp', '9222'));
const warmProfile = arg('warm-profile', '0') === '1';
const coldFirst = arg('cold-first', '1') === '1';
const selfContained = arg('self-contained', '0') === '1';
const coldData = arg('cold-data', '0') === '1';
const readySel = arg('ready-selector', '[data-testid="nav-market"]');
const marketNav = arg('market-nav', '[data-testid="nav-market"]');
const techNav = arg('tech-nav', '[data-testid="nav-technical"]');
const marketRowSel = arg('market-row', '[data-testid="tape-row"]');
const techReadySel = arg('tech-ready', '[data-testid="nn-chart-host"] canvas');
const scrollSel = arg('scroll', '[data-testid="tape-scroll"]');
const profileDir = path.resolve(arg('profile-dir', path.join(outRoot, '.shell-profile')));

const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const outDir = path.join(outRoot, `${stamp}-${label}`);
fs.mkdirSync(outDir, { recursive: true });

async function prewarm() {
  const paths = ['/api/update/version', '/api/market', '/api/chart/%D9%81%D9%88%D9%84%D8%A7%D8%AF'];
  const out = {};
  for (const p of paths) {
    const t0 = Date.now();
    try {
      const r = await fetch(backend + p, { headers: { 'Accept-Encoding': 'gzip' } });
      const buf = await r.arrayBuffer();
      out[p] = { ms: Date.now() - t0, status: r.status, kb: Math.round(buf.byteLength / 1024) };
    } catch (e) {
      out[p] = { ms: Date.now() - t0, error: String(e).slice(0, 200) };
    }
  }
  return out;
}

function cleanupProfileProcesses(marker) {
  const script = `
    Get-CimInstance Win32_Process |
      Where-Object { $_.CommandLine -and $_.CommandLine.Contains('${marker.replace(/\\/g, '\\\\')}') } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  `;
  try {
    execFileSync('powershell.exe', ['-NoProfile', '-Command', script], { timeout: 30000 });
  } catch {
    /* best effort */
  }
}

async function portFree(p, timeoutMs = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      await fetch(`http://127.0.0.1:${p}/json/version`);
    } catch {
      return true;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
}

function psJson(script) {
  const out = execFileSync('powershell.exe', ['-NoProfile', '-Command', script], {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
  });
  return out.trim() ? JSON.parse(out) : [];
}

function processSnapshot(rootPid) {
  const script = `
    $all = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,WorkingSetSize,KernelModeTime,UserModeTime,CommandLine
    $all | ConvertTo-Json -Compress -Depth 3
  `;
  let all = [];
  try {
    all = psJson(script) || [];
  } catch (e) {
    return { error: String(e).slice(0, 200) };
  }
  if (!Array.isArray(all)) all = [all];
  const byParent = new Map();
  for (const p of all) {
    const k = p.ParentProcessId;
    if (!byParent.has(k)) byParent.set(k, []);
    byParent.get(k).push(p);
  }
  const tree = [];
  const rootProc = all.find((p) => p.ProcessId === rootPid);
  if (rootProc) tree.push(rootProc);
  const walk = (pid) => {
    for (const child of byParent.get(pid) || []) {
      if (tree.some((t) => t.ProcessId === child.ProcessId)) continue;
      tree.push(child);
      walk(child.ProcessId);
    }
  };
  walk(rootPid);
  const sum = (key) => tree.reduce((a, p) => a + (Number(p[key]) || 0), 0);
  return {
    rootPid,
    processes: tree.map((p) => ({
      pid: p.ProcessId,
      name: p.Name,
      rssMB: Math.round((Number(p.WorkingSetSize) || 0) / 1048576),
    })),
    rssMB: Math.round(sum('WorkingSetSize') / 1048576),
    cpuSeconds: Math.round((sum('KernelModeTime') + sum('UserModeTime')) / 1e7),
    names: [...new Set(tree.map((p) => p.Name))],
  };
}

function closeMain(pid) {
  try {
    execFileSync('powershell.exe', ['-NoProfile', '-Command',
      `$p=Get-Process -Id ${pid} -ErrorAction SilentlyContinue; if($p){$p.CloseMainWindow()|Out-Null}`], { timeout: 15000 });
  } catch {
    /* already gone */
  }
}

function killTree(pid) {
  try {
    execFileSync('taskkill.exe', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
  } catch {
    /* already gone */
  }
}

async function waitHttp(url, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return Date.now() - t0;
    } catch {
      /* not up */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`timeout waiting for ${url}`);
}

async function waitCdp(browserURL, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(`${browserURL}/json/version`);
      if (r.ok) return Date.now() - t0;
    } catch {
      /* not up */
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`timeout waiting for CDP ${browserURL}`);
}

async function waitForAppPage(page, timeoutMs = 300000) {
  const origin = new URL(backend).origin;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if (page.url().startsWith(origin)) {
        const rs = await page.evaluate(() => document.readyState);
        if (rs === 'complete' || rs === 'interactive') return;
      }
    } catch {
      /* navigation in flight */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`app page did not become ready at ${origin}`);
}

async function loginIfNeeded(page) {
  if (await page.$(readySel)) return false;
  await page.waitForSelector('input[type="password"]', { timeout: 120000 });
  const inputs = await page.$$('input');
  await inputs[0].click();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await page.keyboard.type('admin');
  await inputs[1].click();
  await page.keyboard.type('bors123');
  await page.click('button[type="submit"]');
  await page.waitForSelector(readySel, { timeout: 120000 });
  return true;
}

async function measure(page, t0, runDir) {
  const result = {};
  await waitForAppPage(page);
  result.pageUrl = page.url();
  result.pageReadyMs = Date.now() - t0;

  const nav = await page.evaluate(() => {
    const n = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByType('paint').map((p) => ({ name: p.name, ms: Math.round(p.startTime) }));
    return n
      ? {
          domContentLoadedMs: Math.round(n.domContentLoadedEventEnd),
          loadMs: Math.round(n.loadEventEnd),
          responseEndMs: Math.round(n.responseEnd),
          transferSize: n.transferSize,
          paint,
        }
      : { paint };
  });
  result.navigation = nav;

  const didLogin = await loginIfNeeded(page);
  result.loginRequired = didLogin;
  result.shellReadyMs = Date.now() - t0;

  const metrics0 = await page.metrics();
  result.jsHeapMB = +(metrics0.JSHeapUsedSize / 1048576).toFixed(1);
  result.domNodes = metrics0.Nodes;

  // ── market ────────────────────────────────────────────────────────────
  const tMarket = Date.now();
  await page.click(marketNav);
  await page.waitForFunction(
    (sel) => document.querySelectorAll(sel).length >= 20,
    { timeout: 180000, polling: 250 },
    marketRowSel,
  );
  result.marketReadyMs = Date.now() - tMarket;
  result.marketRows = await page.evaluate((sel) => document.querySelectorAll(sel).length, marketRowSel);

  const marketRes = await page.evaluate(() => {
    return performance
      .getEntriesByType('resource')
      .filter((e) => /\/api\/(market|mstat|live-stats)/.test(e.name))
      .map((e) => ({
        path: e.name.replace(location.origin, ''),
        ms: Math.round(e.duration),
        transferKB: Math.round(e.transferSize / 1024),
        decodedKB: Math.round(e.decodedBodySize / 1024),
      }))
      .slice(-20);
  });
  result.marketRequests = marketRes;

  result.scroll = await page.evaluate(async (scrollSelector) => {
    const el = document.querySelector(scrollSelector);
    if (!el) return { error: 'no tape-scroll' };
    el.scrollTop = 0;
    const frames = [];
    let last = performance.now();
    await new Promise((res) => {
      const t0 = performance.now();
      const step = (t) => {
        frames.push(t - last);
        last = t;
        el.scrollTop += 48;
        if (t - t0 < 2000) requestAnimationFrame(step);
        else res();
      };
      requestAnimationFrame(step);
    });
    const sorted = frames.slice(1).sort((a, b) => a - b);
    const q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] || 0;
    return {
      frames: sorted.length,
      p50ms: +q(0.5).toFixed(1),
      p95ms: +q(0.95).toFixed(1),
      maxMs: +(sorted[sorted.length - 1] || 0).toFixed(1),
      over33ms: sorted.filter((x) => x > 33).length,
    };
  }, scrollSel);

  await page.setViewport({ width: 1920, height: 1080 });
  await new Promise((r) => setTimeout(r, 800));
  await page.screenshot({ path: path.join(runDir, 'market-1920x1080.png') });
  await page.setViewport({ width: 1366, height: 768 });
  await new Promise((r) => setTimeout(r, 800));
  await page.screenshot({ path: path.join(runDir, 'market-1366x768.png') });

  // ── technical ─────────────────────────────────────────────────────────
  const tTech = Date.now();
  await page.click(techNav);
  await page.waitForSelector(techReadySel, { timeout: 180000 });
  await page.waitForFunction(
    () => performance.getEntriesByType('resource').some((e) => /\/api\/chart\//.test(e.name) && e.responseEnd > 0),
    { timeout: 180000, polling: 250 },
  );
  await new Promise((r) => setTimeout(r, 1500));
  result.technicalReadyMs = Date.now() - tTech;
  result.technicalCanvases = await page.evaluate(
    () => document.querySelectorAll('[data-testid="nn-chart-host"] canvas, [data-testid="chart-host"] canvas').length,
  );
  result.chartRequests = await page.evaluate(() =>
    performance
      .getEntriesByType('resource')
      .filter((e) => /\/api\/chart\//.test(e.name))
      .map((e) => ({ path: e.name.replace(location.origin, ''), ms: Math.round(e.duration), decodedKB: Math.round(e.decodedBodySize / 1024) }))
      .slice(-5),
  );
  await page.screenshot({ path: path.join(runDir, 'technical-1366x768.png') });
  await page.setViewport({ width: 1920, height: 1080 });
  await new Promise((r) => setTimeout(r, 800));
  await page.screenshot({ path: path.join(runDir, 'technical-1920x1080.png') });

  const metrics1 = await page.metrics();
  result.jsHeapAfterMB = +(metrics1.JSHeapUsedSize / 1048576).toFixed(1);
  result.jsHeapPeakMB = +(metrics1.JSHeapTotalSize / 1048576).toFixed(1);

  result.freshness = await page.evaluate(async () => {
    const grab = async (p) => {
      try {
        const r = await fetch(p, { cache: 'no-store' });
        return await r.json();
      } catch (e) {
        return { error: String(e) };
      }
    };
    return {
      version: await grab('/api/update/version'),
      syncState: await grab('/api/market/sync-state'),
    };
  });

  return result;
}

const all = [];
cleanupProfileProcesses(profileDir);
if (coldFirst && !warmProfile && fs.existsSync(profileDir)) {
  fs.rmSync(profileDir, { recursive: true, force: true });
}
fs.mkdirSync(profileDir, { recursive: true });
const prewarmResult = selfContained ? null : await prewarm();

if (selfContained && coldData) {
  const dataDir = path.join(path.dirname(shellPath), 'data');
  for (const f of ['market.db', 'market.db-wal', 'market.db-shm']) {
    fs.rmSync(path.join(dataDir, f), { force: true });
  }
  fs.rmSync(path.join(dataDir, 'BorsTerminal_Ultimate', 'webview2'), { recursive: true, force: true });
}

for (let run = 1; run <= runs; run++) {
  const runDir = path.join(outDir, `run-${run}`);
  fs.mkdirSync(runDir, { recursive: true });
  const cdpPort = cdpBase + run;
  await portFree(cdpPort, 5000);

  const env = {
    ...process.env,
    BORS_PORT: port,
    BORS_NO_FETCH_LOOPS: '1',
    BORS_CODAL_AUTO: '0',
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${cdpPort}`,
    ...(selfContained ? {} : { LOCALAPPDATA: path.join(profileDir, 'localappdata') }),
  };
  let cmd, args;
  if (shellKind === 'exe') {
    cmd = shellPath;
    args = [];
  } else {
    cmd = shellPath;
    args = shellArgs.split(' ').filter(Boolean);
  }

  const t0 = Date.now();
  const child = spawn(cmd, args, {
    cwd: ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: false,
  });
  let launcherLog = '';
  child.stdout.on('data', (d) => (launcherLog += d));
  child.stderr.on('data', (d) => (launcherLog += d));

  let record = { run, label, shellKind, t0, t0Iso: new Date(t0).toISOString(), env: {
    BORS_PORT: port,
    BORS_NO_FETCH_LOOPS: '1',
    BORS_CODAL_AUTO: '0',
    cdpPort,
    freshProfile: coldFirst && run === 1,
  } };
  try {
    if (selfContained) {
      const cdpPromise = waitCdp(`http://127.0.0.1:${cdpPort}`, 300000);
      record.backendReadyMs = await waitHttp(`${backend}/api/update/version`, 600000);
      record.backendWasWarm = false;
      record.cdpMs = await cdpPromise;
    } else {
      await waitHttp(`${backend}/api/update/version`, 60000);
      record.backendWasWarm = true;
      record.cdpMs = await waitCdp(`http://127.0.0.1:${cdpPort}`, 300000);
    }
    const browser = await puppeteer.connect({
      browserURL: `http://127.0.0.1:${cdpPort}`,
      defaultViewport: null,
    });
    let page = null;
    const deadline = Date.now() + 90000;
    while (!page && Date.now() < deadline) {
      const pages = await browser.pages();
      page = pages.find((p) => /127\.0\.0\.1|localhost/.test(p.url())) || pages[0];
      if (!page) await new Promise((r) => setTimeout(r, 200));
    }
    if (!page) throw new Error('no page target');
    const consoleErrors = [];
    page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 400)}`));
    page.on('console', (m) => {
      if (m.type() === 'error') consoleErrors.push(`console: ${m.text().slice(0, 400)}`);
    });
    record = { ...record, ...(await measure(page, t0, runDir)) };
    record.consoleErrors = consoleErrors.slice(0, 20);
    const idle0 = processSnapshot(child.pid);
    await new Promise((r) => setTimeout(r, 3000));
    const idle1 = processSnapshot(child.pid);
    record.process = idle1;
    record.idleCpuSeconds3s = (idle1.cpuSeconds || 0) - (idle0.cpuSeconds || 0);
    await browser.disconnect();
  } catch (e) {
    record.error = String(e).slice(0, 800);
    record.launcherLog = launcherLog.slice(-4000);
  }
  closeMain(child.pid);
  await new Promise((r) => setTimeout(r, 4000));
  killTree(child.pid);
  cleanupProfileProcesses(profileDir);
  if (selfContained) {
    cleanupProfileProcesses(path.join(path.dirname(shellPath), 'data', 'BorsTerminal_Ultimate'));
  }
  await new Promise((r) => setTimeout(r, 3000));
  fs.writeFileSync(path.join(outDir, `run-${run}.json`), JSON.stringify(record, null, 2));
  fs.writeFileSync(path.join(outDir, `run-${run}-launcher.log`), launcherLog);
  all.push(record);
  console.log(JSON.stringify({ run, ok: !record.error, shellReadyMs: record.shellReadyMs, marketReadyMs: record.marketReadyMs, technicalReadyMs: record.technicalReadyMs, rssMB: record.process?.rssMB, error: record.error }, null, 0));
}

const summary = { label, prewarm: prewarmResult, runs: all, generatedAt: new Date().toISOString() };
fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 2));
console.log('OUT', outDir);
