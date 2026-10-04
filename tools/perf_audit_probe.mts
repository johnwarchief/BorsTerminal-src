/**
 * tools/perf_audit_probe.mts — ممیزِ بزرگ Performance (PHASE: فقط اندازه‌گیری)
 *
 * سناریوها: startup، idle، scroll، tab-loop×3، نمودارِ symbol-switch (Technical)،
 * dialog open/close×10، StrategyTree mount/unmount×5، Heavy (قیف+بازرس+داossier).
 * متریک‌ها: ΔTask/Script/Layout/RecalcStyle (CDP Performance.getMetrics)،
 * long task، ریزِ rAF، heap (Runtime.getHeapUsage با GC اجباری)، شمارِ زندهٔ
 * listener/timer (wrapper در init script)، شبکه (تعداد/حجم/304)، DOM node count.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME='...chromium-1234/chrome-win64/chrome.exe' \
 *   node --experimental-strip-types tools/perf_audit_probe.mts --url http://127.0.0.1:8002/ --out _audit/perf_audit.json
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
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/+$/, '') + '/';
const OUT = arg('out', '_audit/perf_audit.json');
const QUICK = arg('quick', '') !== '';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const INIT = () => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* دروازۀ UI */
  }
  const w = window as unknown as {
    __perf: {
      listeners: Record<string, number>;
      listenerAdd: number;
      listenerRemove: number;
      timersLive: number;
      timersCreated: number;
      intervalsLive: number;
      longTasks: { n: number; totalMs: number };
      rafGaps: number[];
      net: { url: string; status: number; bytes: number; ms: number }[];
    };
  };
  w.__perf = {
    listeners: {},
    listenerAdd: 0,
    listenerRemove: 0,
    timersLive: 0,
    timersCreated: 0,
    intervalsLive: 0,
    longTasks: { n: 0, totalMs: 0 },
    rafGaps: [],
    net: [],
  };
  const P = w.__perf;
  const origAdd = EventTarget.prototype.addEventListener;
  const origRem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type: string, ...rest: unknown[]) {
    P.listenerAdd++;
    P.listeners[type] = (P.listeners[type] ?? 0) + 1;
    return (origAdd as (t: string, ...a: unknown[]) => void).call(this, type, ...rest);
  };
  EventTarget.prototype.removeEventListener = function (type: string, ...rest: unknown[]) {
    P.listenerRemove++;
    P.listeners[type] = Math.max(0, (P.listeners[type] ?? 0) - 1);
    return (origRem as (t: string, ...a: unknown[]) => void).call(this, type, ...rest);
  };
  const si = window.setInterval;
  const ci = window.clearInterval;
  const st = window.setTimeout;
  const ct = window.clearTimeout;
  window.setInterval = function (...a: Parameters<typeof si>) {
    P.timersCreated++;
    P.intervalsLive++;
    return si.apply(window, a);
  };
  window.clearInterval = ((id: number) => {
    P.intervalsLive = Math.max(0, P.intervalsLive - 1);
    return ci(id);
  }) as typeof ci;
  window.setTimeout = function (...a: Parameters<typeof st>) {
    P.timersCreated++;
    P.timersLive++;
    const wrapped = a[0];
    return st.apply(window, [
      () => {
        P.timersLive = Math.max(0, P.timersLive - 1);
        if (typeof wrapped === 'function') wrapped();
      },
      ...a.slice(1),
    ]);
  };
  if ('PerformanceObserver' in window) {
    try {
      new PerformanceObserver((l) => {
        for (const e of l.getEntries()) {
          P.longTasks.n++;
          P.longTasks.totalMs += e.duration;
        }
      }).observe({ type: 'longtask', buffered: true });
    } catch {
      /* jsdom-like */
    }
  }
  let last = performance.now();
  const tick = () => {
    const now = performance.now();
    if (P.rafGaps.length < 20000) P.rafGaps.push(now - last);
    last = now;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};

const results: Record<string, unknown> = { base: BASE, ts: new Date().toISOString(), scenarios: {} };
const browser = await chromium.launch({
  executablePath: process.env.JEV_CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-precise-memory-info'],
});
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(INIT);
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Performance.enable');
await cdp.send('Runtime.enable');

// شبکه: هر پاسخ API را ثبت کن
ctx.on('response', async (res) => {
  try {
    const url = res.url();
    if (!url.includes('/api/')) return;
    const sizes = await res.sizes().catch(() => null);
    const perf = (
      await page.evaluate(
        (u) => {
          const e = performance.getEntriesByName(u, 'resource')[0] as PerformanceResourceTiming | undefined;
          return e ? { ms: Math.round(e.duration) } : null;
        },
        url,
      )
    )?.ms;
    (page as unknown as { __net?: unknown }).__net = (page as unknown as { __net?: unknown[] }).__net ?? [];
    ((page as unknown as { __net: unknown[] }).__net as { url: string; status: number; bytes: number; ms: number }[]).push({
      url: url.replace(BASE, ''),
      status: res.status(),
      bytes: sizes ? sizes.bodySize + sizes.headersSize : 0,
      ms: perf ?? -1,
    });
  } catch {
    /* response بی‌بدن */
  }
});

const metrics = async () => {
  const { metrics: m } = await cdp.send('Performance.getMetrics');
  const g = (n: string) => (m.find((x) => x.name === n)?.value ?? 0) as number;
  return { task: g('TaskDuration'), script: g('ScriptDuration'), layout: g('LayoutDuration'), style: g('RecalcStyleDuration'), nodes: g('Nodes'), listeners: g('JSEventListeners') };
};
const heapMB = async () => {
  await cdp.send('HeapProfiler.collectGarbage').catch(() => undefined);
  const r = await (cdp.send('Runtime.getHeapUsage', {}) as Promise<{ usedSize: number }>);
  return Math.round((r.usedSize / 1048576) * 10) / 10;
};
const perfSide = () =>
  page.evaluate(() => {
    const P = (window as unknown as { __perf: Record<string, unknown> }).__perf;
    const gaps = (P.rafGaps as number[]).slice(-500);
    const worst = gaps.length ? Math.max(...gaps) : 0;
    const over50 = gaps.filter((x) => x > 50).length;
    const listeners = Object.fromEntries(
      Object.entries(P.listeners as Record<string, number>).filter(([, v]) => v > 0),
    );
    return {
      listenerAdd: P.listenerAdd, listenerRemove: P.listenerRemove,
      timersCreated: P.timersCreated, intervalsLive: P.intervalsLive,
      longTasks: P.longTasks, rafWorstGapMs: Math.round(worst), rafOver50ms: over50,
      listenersLiveByType: listeners,
    };
  });

async function scenario(name: string, route: string, waitMs: number, act?: () => Promise<void>) {
  await page.goto(BASE + '#' + route, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500); // عبورِ Lazy/first render
  const before = { heap: await heapMB(), m: await metrics(), side: await perfSide() };
  await page.waitForTimeout(waitMs);
  if (act) await act();
  const after = { heap: await heapMB(), m: await metrics(), side: await perfSide() };
  const net = ((page as unknown as { __net: { url: string; status: number; bytes: number; ms: number }[] }).__net ?? []);
  (results.scenarios as Record<string, unknown>)[name] = {
    windowMs: waitMs,
    heapBeforeMB: before.heap,
    heapAfterMB: after.heap,
    taskMsDelta: Math.round((after.m.task - before.m.task) * 1000),
    scriptMsDelta: Math.round((after.m.script - before.m.script) * 1000),
    layoutMsDelta: Math.round((after.m.layout - before.m.layout) * 1000),
    styleMsDelta: Math.round((after.m.style - before.m.style) * 1000),
    domNodes: after.m.nodes,
    jsListenersCdp: after.m.listeners,
    longTasksAfter: after.side.longTasks,
    rafWorstGapMs: after.side.rafWorstGapMs,
    rafOver50msTail: after.side.rafOver50ms,
    intervalsLive: after.side.intervalsLive,
    listenersByType: after.side.listenersLiveByType,
    netCount: net.length,
    netBytesMB: Math.round((net.reduce((a, x) => a + x.bytes, 0) / 1048576) * 100) / 100,
    net304: net.filter((x) => x.status === 304).length,
    slowest: [...net].sort((a, b) => b.ms - a.ms).slice(0, 5),
  };
  console.log(`${name}: heap ${before.heap}→${after.heap}MB taskΔ=${Math.round((after.m.task - before.m.task) * 1000)}ms nodes=${after.m.nodes}`);
}

// startup: رفتن به بازار از صفر و زمان دیدنِ جدول
const t0 = Date.now();
await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
const fp = await page.evaluate(() => {
  const fcp = performance.getEntriesByType('paint').find((p) => p.name === 'first-contentful-paint');
  return { fcpMs: fcp ? Math.round(fcp.startTime) : -1, domReadyMs: Math.round(performance.timing?.domContentLoadedEventEnd ?? 0) };
});
const tableSeen = Date.now() - t0;
try {
  await page.waitForSelector('[data-testid="tape-row"] , tbody tr', { timeout: 45000 });
} catch {
  /* بی‌نتیجه، همان ثبت می‌شود */
}
(results as { startup: unknown }).startup = {
  ...fp,
  toTableMs: Date.now() - t0,
  heapAfterStartupMB: await heapMB(),
  note: 'toTable = navigation تا اولین سطر جدول؛ بی‌پروندۀ گرمِ مرورگر، سرد',
};
console.log('startup:', JSON.stringify((results as { startup: unknown }).startup));

// Idle: بازار بسته، فقط پولینگ (60s؛ در ساعتِ بازار با idle بازاجرای --idle300 طولانی‌اش کن)
await scenario('idle-market-60s', '/market', 60000);

// Scrolling: اسکرول جدول
await scenario('scroll-market-10s', '/market', 3000, async () => {
  await page.evaluate(async () => {
    const el = document.scrollingElement ?? document.documentElement;
    for (let i = 0; i < 24; i++) {
      el.scrollTop += 260;
      await new Promise((r) => setTimeout(r, 120));
    }
    el.scrollTop = 0;
  });
});

// Tab loop ×3 با heap در هر پاس
const routes = ['/market', '/technical', '/fundamental', '/master', '/portfolio', '/strategy-tree'];
const passes: unknown[] = [];
for (let pass = 0; pass < (QUICK ? 1 : 3); pass++) {
  for (const r of routes) {
    await page.goto(BASE + '#' + r, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1600);
  }
  passes.push({ pass, heapMB: await heapMB(), nodes: (await metrics()).nodes, listenersAdd: (await perfSide()).listenerAdd });
}
(results.scenarios as Record<string, unknown>)['tab-loop'] = { passes, routes };
console.log('tab-loop:', JSON.stringify(passes));

// Symbol switching stress در Technical
const symbols = await page.evaluate(async () => {
  const res = await fetch('/api/market');
  const j = (await res.json()) as { data: { symbol?: string }[] };
  return j.data.map((r) => r.symbol).filter((s): s is string => !!s).slice(0, 20);
});
const symBefore = { heap: await heapMB(), m: await metrics() };
for (const s of symbols) {
  await page.goto(`${BASE}#/technical/${encodeURIComponent(s)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(700);
}
const symAfter = { heap: await heapMB(), m: await metrics() };
const canvasCount = await page.evaluate(() => document.querySelectorAll('canvas').length);
const listenersDelta = (await metrics()).listeners - symBefore.m.listeners;
(results.scenarios as Record<string, unknown>)['symbol-stress-20-technical'] = {
  count: symbols.length,
  heapBeforeMB: symBefore.heap,
  heapAfterMB: symAfter.heap,
  taskMsDelta: Math.round((symAfter.m.task - symBefore.m.task) * 1000),
  jsListenersDelta: listenersDelta,
  canvasNodes: canvasCount,
  net: ((page as unknown as { __net: unknown[] }).__net ?? []).length,
};
console.log('symbol-stress:', JSON.stringify((results.scenarios as Record<string, never>)['symbol-stress-20-technical']));

// Dialogs: دراورِ تنظیمات بنیادی ۱۰ بار
await page.goto(BASE + '#/fundamental', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="fts-settings-trigger"]', { timeout: 40000 });
const dBefore = await heapMB();
for (let i = 0; i < 10; i++) {
  await page.click('[data-testid="fts-settings-trigger"] button');
  await page.waitForTimeout(350);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(250);
}
const dAfter = await heapMB();
(results.scenarios as Record<string, unknown>)['dialogs-open-close-10'] = {
  heapBeforeMB: dBefore,
  heapAfterMB: dAfter,
  jsListeners: (await metrics()).listeners,
  intervalsLive: (await perfSide()).intervalsLive,
};

// Strategy Tree mount/unmount ×5
const treePasses: unknown[] = [];
for (let i = 0; i < 5; i++) {
  const b = { heap: await heapMB(), m: await metrics() };
  await page.goto(BASE + '#/strategy-tree', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3500);
  await page.goto(BASE + '#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const a = { heap: await heapMB(), m: await metrics() };
  treePasses.push({
    i,
    heapAfterMountUnmountMB: a.heap,
    taskMsWindow: Math.round((a.m.task - b.m.task) * 1000),
    styleMsWindow: Math.round((a.m.style - b.m.style) * 1000),
    layoutMsWindow: Math.round((a.m.layout - b.m.layout) * 1000),
    nodesAfter: a.m.nodes,
    listenersAfter: a.m.listeners,
  });
}
(results.scenarios as Record<string, unknown>)['tree-mount-unmount-5'] = treePasses;

// Heavy: قیف با نمادِ lit + بازرس باز + درختِ با جریان — تخمینِ «سنگینِ واقعی»: master با نماد + سپس tree با همان نماد و flow روشن
const sym0 = await page.evaluate(() => (document.querySelector('[data-fkey]') as HTMLElement)?.getAttribute('data-fkey') ?? '');
await page.goto(BASE + '#/master/' + encodeURIComponent(sym0 || 'خودرو'), { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);
await scenario('heavy-master-dossier-20s', '/master/' + encodeURIComponent(sym0 || 'خودرو'), 20000);
await page.goto(BASE + '#/strategy-tree/' + encodeURIComponent(sym0 || 'خودرو'), { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);
await page.evaluate(() => {
  // روشن‌کردنِ انیمیشنِ جریانِ درخت از طریقِ استور (دکمۀ UI همان کار را می‌کند)
  const btn = Array.from(document.querySelectorAll('button')).find((b) => (b.textContent ?? '').includes('مستقیم'));
  btn?.click();
});
await scenario('heavy-tree-flow-20s', '/strategy-tree/' + encodeURIComponent(sym0 || 'خودرو'), 20000, async () => {
  await page.waitForTimeout(1000);
});

const finalNet = (page as unknown as { __net: { url: string; status: number; bytes: number; ms: number }[] }).__net ?? [];
const byUrl: Record<string, { n: number; bytes: number; slowestMs: number; codes: Record<string, number> }> = {};
for (const r of finalNet) {
  const key = r.url.split('?')[0].replace(/\/[^/]+$/, '/:x');
  const e = (byUrl[key] ??= { n: 0, bytes: 0, slowestMs: 0, codes: {} });
  e.n++;
  e.bytes += r.bytes;
  e.slowestMs = Math.max(e.slowestMs, r.ms);
  e.codes[String(r.status)] = (e.codes[String(r.status)] ?? 0) + 1;
}
(results as { networkTotals: unknown }).networkTotals = byUrl;

await browser.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(results, null, 1), 'utf8');
console.log('\nOUT →', OUT);
