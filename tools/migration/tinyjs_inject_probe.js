// tools/migration/tinyjs_inject_probe.js — in-window measurement for TinyJS
//
// TinyJS's packaged launcher deliberately ignores inherited WebView2 flags, so
// --remote-debugging-port cannot be used on a built .exe (the launcher passes
// its own AdditionalBrowserArguments; tinyjs #29). Its documented manifest hook
// "inject" runs this file at document-start inside the real app window, so the
// same facts fe_probe.js collects over CDP are collected here from inside:
// navigation timing, long tasks/TBT, frame cadence, API request sizes, heap.
//
// It self-drives the SAME scenario as fe_probe.js (login gate -> landing route
// ready -> reload -> tab cycle -> chart) and POSTs one JSON report to the local
// collector started by shell_probe.py. It never writes app data.
(() => {
  const STAGE_KEY = '__bors_shell_probe_stage';
  const COLLECT = 'http://127.0.0.1:8151/collect';
  const DEADLINE = 180000;
  if (sessionStorage.getItem(STAGE_KEY) === 'done') return;

  // ---------- collector (same signals as fe_probe.js INIT) ----------
  const p = { longtasks: [], events: [], frames: [], heap: [], lastMut: 0, domNodes: 0 };
  window.__perf = p;
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) p.longtasks.push({ t: Math.round(e.startTime), d: Math.round(e.duration) });
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) { p.noLongtask = String(e); }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.duration < 8) continue;
        p.events.push({ name: e.name, d: Math.round(e.duration) });
      }
    }).observe({ type: 'event', buffered: true });
  } catch (e) { p.noEvent = String(e); }
  let lastFrame = 0;
  const tick = (t) => {
    if (lastFrame) {
      p.frames.push(Math.round(t - lastFrame));
      if (p.frames.length > 4000) p.frames.splice(0, 500);
    }
    lastFrame = t;
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  setInterval(() => {
    if (performance.memory) p.heap.push({ t: Math.round(performance.now()), used: performance.memory.usedJSHeapSize });
    p.domNodes = document.getElementsByTagName('*').length;
  }, 1000);
  const mark = () => { p.lastMut = performance.now(); };
  const startMut = () => {
    try { new MutationObserver(mark).observe(document.body, { subtree: true, childList: true, characterData: true }); }
    catch (e) { p.noMut = String(e); }
  };
  if (document.body) startMut(); else addEventListener('DOMContentLoaded', startMut);

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function waitFor(fn, timeout = DEADLINE, step = 100) {
    const t0 = performance.now();
    while (performance.now() - t0 < timeout) {
      try { if (fn()) return true; } catch (e) { /* keep polling */ }
      await sleep(step);
    }
    return false;
  }

  // v1.0.98's sidebar is button-based and its workspace-tab layer decides what
  // mounts; a hash-driven probe can open these four reliably. /fundamental only
  // renders through its own workspace tab, so it is deliberately NOT measured
  // here instead of reporting a misleading timeout.
  const ROUTES = [
    { route: '/market', label: 'market', marker: '[data-testid="tape-row"]', min: 10 },
    { route: '/market-status', label: 'market-status', marker: '[data-testid^="treemap-cell-"]', min: 1 },
    { route: '/technical', label: 'technical', marker: '[data-testid="chart-area"]', min: 1 },
    // v1.0.98 opens the master workspace on a symbol dossier, so the funnel
    // workspace element is not always mounted; either one means "master drawn".
    { route: '/master', label: 'master', marker: '[data-testid="fts-funnel-workspace"], [data-testid="master-dossier"]', min: 1 },
  ];
  const byName = {};
  for (const r of ROUTES) byName[r.route.slice(1)] = r;
  const routeFromHash = (hash) => {
    const h = String(hash || '').replace(/^#\/?/, '').split('/')[0];
    return byName[h] || ROUTES[0];
  };
  const ready = (rt) => {
    if (!location.hash.startsWith('#' + rt.route)) return false;
    if (document.querySelectorAll('[data-testid$="-loading"]').length > 0) return false;
    if (document.querySelectorAll(rt.marker).length < rt.min) return false;
    return (window.__perf.lastMut || 0) > 0 && (performance.now() - window.__perf.lastMut) > 700;
  };

  function setNativeValue(el, value) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const gateNow = () => !!document.querySelector('input[type="password"]');
  async function loginIfGate(waitMs) {
    if (waitMs > 0) await waitFor(gateNow, waitMs, 100);
    if (!gateNow()) return false;
    const user = document.querySelector('input[type="text"]');
    const pass = document.querySelector('input[type="password"]');
    if (user) setNativeValue(user, 'admin');
    if (pass) setNativeValue(pass, 'bors123');
    await sleep(100);
    const btn = document.querySelector('button[type="submit"]');
    if (btn) btn.click();
    await waitFor(() => !document.querySelector('input[type="password"]'), 15000, 150);
    return true;
  }

  function drainFrames() {
    const fr = (p.frames || []).slice().sort((a, b) => a - b);
    const out = {
      n: fr.length,
      med: fr.length ? fr[Math.floor(fr.length / 2)] : 0,
      p95: fr.length ? fr[Math.floor(fr.length * 0.95)] : 0,
      max: fr.length ? fr[fr.length - 1] : 0,
      over32: fr.filter((x) => x > 32).length,
      over100: fr.filter((x) => x > 100).length,
    };
    p.frames = [];
    return out;
  }

  function drain(resCursor) {
    const lt = p.longtasks || [];
    const res = performance.getEntriesByType('resource').slice(resCursor || 0);
    const api = res.filter((r) => r.name.includes('/api/'));
    const byUrl = {};
    for (const r of api) {
      const u = r.name.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
      const b = byUrl[u] || (byUrl[u] = { n: 0, ms: 0, maxMs: 0, encoded: 0, transfer: 0 });
      b.n += 1; b.ms += r.duration; b.maxMs = Math.max(b.maxMs, r.duration);
      b.encoded += r.encodedBodySize || 0; b.transfer += r.transferSize || 0;
    }
    const frameStats = drainFrames();
    const heap = p.heap.length ? p.heap[p.heap.length - 1].used : 0;
    const nav = performance.getEntriesByType('navigation')[0] || {};
    const paint = performance.getEntriesByType('paint');
    const get = (n) => { const x = paint.find((y) => y.name === n); return x ? x.startTime : null; };
    const out = {
      firstPaint: get('first-paint'),
      firstContentfulPaint: get('first-contentful-paint'),
      domContentLoaded: nav.domContentLoadedEventEnd,
      loadEnd: nav.loadEventEnd,
      longtasks: lt.length,
      tbt: lt.reduce((a, x) => a + Math.max(0, x.d - 50), 0),
      worst: lt.reduce((a, x) => Math.max(a, x.d), 0),
      requests: Object.entries(byUrl)
        .map(([k, v]) => ({ url: k, n: v.n, avgMs: Math.round(v.ms / v.n), maxMs: Math.round(v.maxMs), encoded: v.encoded, transfer: v.transfer }))
        .sort((a, b) => (b.encoded + b.transfer) - (a.encoded + a.transfer)),
      requestTotal: api.length,
      apiBytesEncoded: api.reduce((a, r) => a + (r.encodedBodySize || 0), 0),
      apiBytesTransfer: api.reduce((a, r) => a + (r.transferSize || 0), 0),
      frames: frameStats,
      heapMB: Math.round(heap / 1e6 * 10) / 10,
      domNodes: document.getElementsByTagName('*').length,
    };
    p.longtasks = [];
    p.events = [];
    p.frames = [];
    return { ...out, resIndexAfter: performance.getEntriesByType('resource').length };
  }

  // The first load starts with an empty hash and the app only writes #/master
  // after the local login, so hash-only detection waits forever. Accept a
  // rendered workspace marker as proof of the landing route, then wait for it
  // to settle (no hash requirement here — that check belongs to tab clicks).
  const settled = (rt) => document.querySelectorAll('[data-testid$="-loading"]').length === 0
    && document.querySelectorAll(rt.marker).length >= rt.min
    && (performance.now() - (window.__perf.lastMut || 0)) > 700;

  async function waitLanding() {
    const t0 = performance.now();
    let rt = null;
    while (performance.now() - t0 < 15000) {
      const h = String(location.hash || '');
      if (h.replace(/^#\/?/, '').length) { rt = routeFromHash(h); break; }
      const found = ROUTES.find((r) => document.querySelectorAll(r.marker).length >= r.min);
      if (found) { rt = found; break; }
      await sleep(100);
    }
    if (!rt) rt = routeFromHash(location.hash);
    // Best-effort: a fresh profile can land on a view none of these markers
    // describe (e.g. the analysis space), and waiting 3 minutes there would
    // block the whole probe. The tab cycle navigates explicitly afterwards.
    const okSettled = await waitFor(() => settled(rt), 30000, 100);
    return { rt, okSettled };
  }

  async function cycleTabs() {
    const out = [];
    for (const rt of ROUTES) {
      const since = performance.getEntriesByType('resource').length;
      const t0 = performance.now();
      const link = document.querySelector(`aside[aria-label="نوار کناری"] a[href$="${rt.route}"]`);
      if (link) link.click(); else location.hash = '#' + rt.route;
      const ok = await waitFor(() => ready(rt), 60000, 100);
      const d = drain(since);
      d.tab = rt.label;
      d.route = rt.route;
      d.clickToReady = ok ? Math.round(performance.now() - t0) : null;
      d.hash = location.hash;
      out.push(d);
      post({ stage: 'event', event: 'tab', tab: rt.label, ms: d.clickToReady, hash: location.hash });
      title('tab:' + rt.label + ':' + (d.clickToReady == null ? '-' : Math.round(d.clickToReady)));
    }
    return out;
  }

  async function chartPhase() {
    if (!document.querySelector('canvas')) {
      location.hash = '#/technical';
      await sleep(500);
    }
    await waitFor(() => document.querySelectorAll('canvas').length >= 1, 60000, 100);
    let symbols = [];
    try {
      const j = await (await fetch('/api/mstat/mainwatch?group=eq_all&industry=')).json();
      symbols = (j.rows || []).slice(0, 3).map((r) => r.symbol).filter(Boolean);
    } catch (e) { /* fall through with none */ }
    const res = [];
    for (const sym of symbols) {
      const since = performance.getEntriesByType('resource').length;
      const t0 = performance.now();
      location.hash = '#/technical/' + encodeURIComponent(sym);
      let hist = null;
      if (await waitFor(() => performance.getEntriesByType('resource')
        .some((r) => decodeURIComponent(r.name).includes('/api/chart/' + sym) && r.responseEnd > 0), 60000, 100)) {
        hist = Math.round(performance.now() - t0);
      }
      await sleep(2000);
      const d = drain(since);
      d.symbol = sym;
      // A <50ms match is a previously-cached resource entry, not this
      // navigation's fetch; report it as cached instead of a fake fast number.
      d.cached = hist !== null && hist < 50;
      d.historyMs = d.cached ? null : hist;
      res.push(d);
    }
    const canvas = document.querySelector('canvas');
    let interaction = null;
    if (canvas && symbols.length) {
      const r = canvas.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const wheelEvt = (dy) => new WheelEvent('wheel', { deltaY: dy, clientX: cx, clientY: cy, bubbles: true, cancelable: true });
      p.frames = []; p.longtasks = [];
      const t0 = performance.now();
      for (let i = 0; i < 12; i++) canvas.dispatchEvent(wheelEvt(i % 2 ? -120 : 120));
      const wheelMs = Math.round(performance.now() - t0);
      await sleep(400);
      const wheel = drain(undefined);
      wheel.label = 'wheel-zoom';
      p.frames = []; p.longtasks = [];
      const t1 = performance.now();
      canvas.dispatchEvent(new MouseEvent('mousedown', { clientX: cx, clientY: cy, bubbles: true }));
      for (let i = 1; i <= 14; i++) {
        canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: cx + (240 * i) / 14, clientY: cy + (40 * i) / 14, bubbles: true }));
      }
      canvas.dispatchEvent(new MouseEvent('mouseup', { clientX: cx + 240, clientY: cy + 40, bubbles: true }));
      const panMs = Math.round(performance.now() - t1);
      await sleep(800);
      const pan = drain(undefined);
      pan.label = 'drag-pan';
      interaction = { wheelMs, panMs, wheel, pan };
    }
    return { symbols: res, interaction };
  }

  // The wrapped page's plain fetch to another loopback port was observed to
  // never reach the collector. TinyJS injects a `tiny` global whose fetch runs
  // in the app's own backend process (no page-level origin/CORS gate), so try
  // that first and keep plain fetch as the fallback.
  // Out-of-band progress channel: the collector POST never arrived from inside
  // the wrapped page (page-level fetch and tiny.fetch both), so the window
  // title — visible to Win32 EnumWindows — carries milestones instead.
  const title = (s) => { try { document.title = 'BSP|' + s; } catch (e) { /* ignore */ } };

  async function post(payload) {
    const body = JSON.stringify(payload);
    if (window.tiny && typeof window.tiny.fetch === 'function') {
      try {
        await window.tiny.fetch(COLLECT, { method: 'POST', headers: { 'content-type': 'text/plain' }, body });
        return true;
      } catch (e) { /* fall through */ }
    }
    try {
      await fetch(COLLECT, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
        body,
      });
      return true;
    } catch (e) {
      return false;
    }
  }

  (async () => {
    try {
      const stage = sessionStorage.getItem(STAGE_KEY) || 'first';
      post({ stage: 'event', event: 'start', stageName: stage, hash: location.hash });
      title(stage + ':start');
      await waitFor(() => document.body, 10000, 50);
      // Only the first load may take time to paint the local login gate; on the
      // reload the session is already there, and a 4s poll would inflate the
      // "cold after reload" number by 4s.
      const gate = await loginIfGate(stage === 'first' ? 4000 : 0);
      post({ stage: 'event', event: 'login', gate, hash: location.hash });
      title(stage + ':login');
      const land = await waitLanding();
      const rt1 = land.rt;
      post({ stage: 'event', event: 'landing', hash: location.hash, settled: land.okSettled });
      title(stage + ':landing-' + (land.okSettled ? 'ok' : 'nosettle'));
      const firstReadyMs = Math.round(performance.now());
      const meta = {
        stage, gate, firstReadyMs, landing: location.hash, landingRoute: rt1.route,
        landingSettled: land.okSettled,
        ua: navigator.userAgent, dpr: window.devicePixelRatio,
        innerWidth: window.innerWidth, innerHeight: window.innerHeight,
        cores: navigator.hardwareConcurrency,
      };
      if (stage === 'first') {
        sessionStorage.setItem(STAGE_KEY, 'second');
        location.reload();
        return;
      }
      const afterReload = drain(0);
      afterReload.readyMs = Math.round(performance.now());
      afterReload.landingRoute = rt1.route;
      const tabs = await cycleTabs();
      title('tabs-done');
      const chart = await chartPhase();
      title('done|cold=' + afterReload.readyMs + '|' + tabs.map((t) => t.clickToReady == null ? '-' : Math.round(t.clickToReady)).join(','));
      await post({ ...meta, cold: afterReload, tabs, chart });
      sessionStorage.setItem(STAGE_KEY, 'done');
    } catch (e) {
      try { await post({ stage: 'error', error: String(e).slice(0, 400) }); } catch (_) { /* ignore */ }
    }
  })();
})();
