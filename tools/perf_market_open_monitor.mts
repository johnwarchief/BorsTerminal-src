/**
 * tools/perf_market_open_monitor.mts — پایشِ مرورگریِ بازشدنِ بازار (یک کلاینت، ریتمِ خودِ اپ)
 *
 * هیچ درخواستی جز درخواست‌هایِ خودِ برنامه ساخته نمی‌شود: یک صفحهٔ Edge اپ را باز
 * می‌کند و همان مسیری را می‌رود که کاربر می‌رود. ساعتِ مرورگر دست‌کاری نمی‌شود (بی‌`--clock`)،
 * پس ریتمِ پولینگ همان «بازار باز»ِ واقعیِ `marketHours.ts` است.
 *
 * زمان‌ها (همه epochِ میلی‌ثانیه‌ایِ ساعتِ همین ماشین):
 *   t0  = لحظهٔ صدا زدنِ fetch در صفحه       th = رسیدنِ هدرها
 *   tj  = پایانِ JSON.parseِ بدنه (`res.json`) — «داده در دستِ کلاینت»
 *   paint = نخستین فریمِ پس از نخستین جهشِ DOM بعد از tj (rAF→MessageChannel) — «روی صفحه»
 *   زمان‌هایِ درونِ بدنه (`h_even`، `last_sync`، `as_of`، `computed_at`) از سرور/بورس‌اند و
 *   این ابزار فقط آن‌ها را نقل می‌کند؛ زمانِ مرورگر هرگز «زمانِ ساختِ داده» نامیده نمی‌شود.
 *
 * اجرا (فقط بعد از هماهنگی با System 1 برای :8000):
 *   node tools/perf_market_open_monitor.mts --url http://127.0.0.1:8000 --out _audit/x \
 *     --start-at 08:40 --until 12:40
 * توقف: فایلِ STOP درونِ `--out`، یا Ctrl+C، یا رسیدنِ --until/--duration.
 * تمرین رویِ ریگ: `--clock 2026-10-17T10:00:00+03:30` ساعتِ کلاینت را با فاصلهٔ ثابت جابه‌جا می‌کند
 * (`clock_offset_ms` درِ رویدادِ start؛ تحلیل‌گر همهٔ زمان‌هایِ سمتِ Node را با آن هم‌تراز می‌کند و
 * خروجی را «تمرین» برچسب می‌زند). رویِ :8000 رد می‌شود.
 * اگر کلاینتِ دیگری به همان پورت وصل باشد (مثلاً اپِ نصب‌شدهٔ مالک) اجرا نمی‌شود
 * (کد ۳) — دو کلاینت یعنی پولینگِ موازی؛ `--allow-other-clients` فقط آگاهانه.
 */
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

const HERE = import.meta.dirname ?? process.cwd();
const argv = process.argv;
const arg = (n: string, f = '') => {
  const i = argv.indexOf(`--${n}`);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : f;
};
const flag = (n: string) => argv.includes(`--${n}`);

const PW = arg('pw', existsSync(join(HERE, '../frontend/node_modules/playwright-core'))
  ? join(HERE, '../frontend/index.js') : join(HERE, '../../system2-ui/frontend/index.js'));
const { chromium } = createRequire(PW)('playwright-core');

const BASE = arg('url', 'http://127.0.0.1:8000').replace(/\/$/, '');
const PORT = Number(new URL(BASE).port || 80);
const OUT = resolve(arg('out', ''));
if (!arg('out')) { console.error('--out لازم است'); process.exit(2); }
const JOURNEY = arg('journey', 'market:900,master:300,market-status:300,fundamental:120,market:600')
  .split(',').map((s) => { const [r, sec] = s.split(':'); return { route: r, sec: Number(sec) }; });
const DRAIN_S = Number(arg('drain', '10'));
const SAMPLE_S = Number(arg('sample', '5'));
const WARM_AFTER_S = Number(arg('warm-after', '30'));
const READY_S = Number(arg('ready', '60'));
const FRESH_EACH_CYCLE = !flag('no-fresh-context');
// فقط برایِ تمرین رویِ ریگ: ساعتِ کلاینت با فاصلهٔ ثابت جلو/عقب می‌رود تا ریتمِ «بازار باز» دیده شود
const CLOCK = arg('clock');
if (CLOCK && PORT === 8000) { console.error('--clock رویِ :8000 مجاز نیست — پایشِ زنده ساعتِ واقعی می‌خواهد'); process.exit(2); }
const CLOCK_OFF = CLOCK ? Date.parse(CLOCK) - Date.now() : 0;
if (CLOCK && !Number.isFinite(CLOCK_OFF)) { console.error(`--clock نامعتبر: ${CLOCK}`); process.exit(2); }
mkdirSync(OUT, { recursive: true });
const EV = join(OUT, 'events.jsonl');
const STOP = join(OUT, 'STOP');
const emit = (o: Record<string, unknown>) => appendFileSync(EV, JSON.stringify({ tn: Date.now(), ...o }) + '\n', 'utf8');

function atToday(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number);
  const d = new Date(); d.setHours(h, m, 0, 0);
  if (d.getTime() < Date.now() - 12 * 3600_000) d.setDate(d.getDate() + 1);
  return d.getTime();
}

function netstat(): Array<{ local: string; remote: string; state: string; pid: number }> {
  const out = execFileSync('netstat', ['-ano', '-p', 'TCP'], { encoding: 'utf8', windowsHide: true });
  return out.split(/\r?\n/).map((l) => l.trim().split(/\s+/))
    .filter((p) => p.length === 5 && p[0] === 'TCP')
    .map((p) => ({ local: p[1], remote: p[2], state: p[3], pid: Number(p[4]) }));
}

function otherClients(): Array<{ pid: number; conns: number }> {
  const rows = netstat();
  const server = rows.find((r) => r.state === 'LISTENING' && r.local.endsWith(`:${PORT}`))?.pid;
  const by = new Map<number, number>();
  for (const r of rows) {
    if (r.state === 'ESTABLISHED' && r.remote.endsWith(`:${PORT}`) && r.pid !== server && r.pid !== process.pid) {
      by.set(r.pid, (by.get(r.pid) ?? 0) + 1);
    }
  }
  return [...by.entries()].map(([pid, conns]) => ({ pid, conns }));
}

const stopNow = () => existsSync(STOP) || stopping;
let stopping = false;
process.on('SIGINT', () => { stopping = true; });

// ---- آغاز ----
const tStartAt = arg('start-at') ? atToday(arg('start-at')) : 0;
if (tStartAt) {
  emit({ k: 'armed', start_at: tStartAt, pid_self: process.pid });
  while (Date.now() < tStartAt && !stopNow()) await new Promise((r) => setTimeout(r, Math.min(30_000, tStartAt - Date.now())));
}
const tEnd = arg('until') ? atToday(arg('until'))
  : arg('duration') ? Date.now() + Number(arg('duration')) * 1000 : Number.POSITIVE_INFINITY;

const others = otherClients();
emit({ k: 'start', base: BASE, port: PORT, pid_self: process.pid, journey: JOURNEY, other_clients: others,
  tz_offset_min: -new Date().getTimezoneOffset(), node: process.version, pw: PW,
  clock_pin: CLOCK || null, clock_offset_ms: CLOCK_OFF });
if (others.length && !flag('allow-other-clients')) {
  emit({ k: 'refused', reason: 'another client is connected to the port', other_clients: others });
  console.error(`کلاینتِ دیگری به :${PORT} وصل است (${JSON.stringify(others)}) — پایشِ مرورگری اجرا نشد.`);
  process.exit(3);
}

const INIT = (pinned: boolean) => {
  const w = window as any;
  if (w.__mon) return;
  const q: any[] = [];
  // زیرِ ساعتِ میخکوبِ Playwright، timeOrigin هنگامِ initScript برابرِ -1 و performance.mark صفر است؛ Date.now درست است
  const now = pinned ? () => Date.now() : () => performance.timeOrigin + performance.now();
  // startTimeِ entryها نسبت به آغازِ واقعیِ ناوبری است. لنگر = Date.nowِ لحظهٔ DOMContentLoaded − domContentLoadedEventStart
  // (آزمون: بی‌میخکوب با timeOriginِ واقعی ≤۰.۶ms اختلاف). تا رسیدنِ لنگر entryها نگه داشته می‌شوند.
  const initWall = Date.now();
  let anchor: number | null = pinned ? null : performance.timeOrigin;
  let dclWall: number | null = null;
  document.addEventListener('DOMContentLoaded', () => { dclWall = Date.now(); }, { once: true });
  const pendRel: [any, number][] = [];
  const pushRel = (o: any, rel: number) => { if (anchor != null) q.push({ ...o, t: anchor + rel }); else pendRel.push([o, rel]); };
  const flush = () => {
    if (anchor == null && pendRel.length && Date.now() - initWall > 20000) anchor = initWall;
    if (anchor == null) return;
    const approx = anchor === initWall;
    for (const [o, rel] of pendRel.splice(0)) q.push({ ...o, t: anchor + rel, ...(approx ? { t_approx: true } : {}) });
  };
  const KEYS = new Set(['as_of', 'computed_at', 'last_sync', 'd_even', 'h_even', 'activity_h_even',
    'data_updated_at', 'clock_now', 'session_day', 'official_state', 'phase', 'phase_source', 'rev',
    'rev_at', 'status', 'reason', 'count', 'live_count', 'fossil_count', 'since', 'client_d_even',
    'client_lag_days', 'cached_for_ms', 'stale', 'age_s']);
  // نقشه‌هایِ نماد‌کلید (status_matrix ~۵هزار نماد) را نمی‌گردیم: پیمایش‌شان رویِ نخِ اصلیِ صفحه Long Task می‌سازد
  const extract = (o: any, pre = '', d = 0, out: any = {}) => {
    if (!o || typeof o !== 'object' || Array.isArray(o) || d > 3) return out;
    const ks = Object.keys(o);
    if (ks.length > 64) { out[`${pre}n_keys`] = ks.length; return out; }
    for (const k of ks) {
      const v = o[k];
      if (Array.isArray(v)) out[`${pre}n_${k}`] = v.length;
      else if (v && typeof v === 'object') extract(v, `${pre}${k}.`, d + 1, out);
      else if (KEYS.has(k)) out[pre + k] = v;
    }
    return out;
  };
  w.__mon = { q, drain: () => { flush(); return q.splice(0, q.length); }, nav: {} };
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) pushRel({ k: 'lt', dur: Math.round(e.duration) }, e.startTime); })
      .observe({ type: 'longtask', buffered: true });
  } catch { q.push({ k: 'warn', msg: 'longtask unsupported' }); }
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) pushRel({ k: 'lcp', size: (e as any).size }, e.startTime); })
      .observe({ type: 'largest-contentful-paint', buffered: true });
  } catch { /* بی‌LCP */ }
  // getEntriesByType زیرِ ساعتِ میخکوبِ Playwright خالی است؛ observer در هر دو حالت کار می‌کند
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries() as any[]) {
      Object.assign(w.__mon.nav, { dcl: Math.round(e.domContentLoadedEventEnd), load: Math.round(e.loadEventEnd) || null, transfer: e.transferSize });
      if (anchor == null && dclWall != null && e.domContentLoadedEventStart > 0) { anchor = dclWall - e.domContentLoadedEventStart; flush(); }
    } }).observe({ type: 'navigation', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') w.__mon.nav.fcp = Math.round(e.startTime); })
      .observe({ type: 'paint', buffered: true });
  } catch { q.push({ k: 'warn', msg: 'nav/paint observer unsupported' }); }
  const of = w.fetch.bind(w);
  let seq = 0;
  w.fetch = async (input: any, init?: any) => {
    const url = typeof input === 'string' ? input : input?.url ?? String(input);
    if (!url.includes('/api/')) return of(input, init);
    const id = ++seq;
    const method = String(init?.method ?? input?.method ?? 'GET').toUpperCase();
    const t0 = now();
    const route = location.hash;
    try {
      const res = await of(input, init);
      const th = now();
      const h = res.headers;
      const base = { id, url: url.replace(location.origin, ''), method, route, t0, th, status: res.status,
        xc: h.get('x-cache') ?? '', date: h.get('date') ?? '', enc: h.get('content-encoding') ?? '',
        inm: Boolean(init?.headers && (init.headers['If-None-Match'] || init.headers['if-none-match'])) };
      q.push({ k: 'fh', ...base });
      const oj = res.json.bind(res);
      res.json = async () => {
        const a = now();
        const body = await oj();
        const tj = now();
        q.push({ k: 'f', ...base, tj, json_ms: Math.round(tj - a), ts: extract(body) });
        return body;
      };
      return res;
    } catch (e) {
      q.push({ k: 'ff', id, url: url.replace(location.origin, ''), method, route, t0, t1: now(), err: String(e).slice(0, 160) });
      throw e;
    }
  };
  const area = (n: Node | null) => {
    const el = (n && n.nodeType === 1 ? n : n?.parentElement) as Element | null;
    const a = el?.closest?.('[data-testid]');
    return a ? a.getAttribute('data-testid')!.replace(/-\d+$/, '-#').slice(0, 48) : 'root';
  };
  let pend: any = null;
  const mo = new MutationObserver((list) => {
    const areas: Record<string, number> = {};
    for (const m of list) {
      const a = area(m.target);
      areas[a] = (areas[a] ?? 0) + m.addedNodes.length + m.removedNodes.length + (m.type === 'characterData' ? 1 : 0);
    }
    if (pend) { for (const [k, v] of Object.entries(areas)) pend.areas[k] = (pend.areas[k] ?? 0) + v; return; }
    pend = { t: now(), areas };
    requestAnimationFrame(() => {
      const ch = new MessageChannel();
      ch.port1.onmessage = () => { q.push({ k: 'mut', t: pend.t, paint: now(), areas: pend.areas, route: location.hash }); pend = null; };
      ch.port2.postMessage(0);
    });
  });
  const attach = () => mo.observe(document.getElementById('root') ?? document.body, { childList: true, subtree: true, characterData: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach); else attach();
  w.__mon.sample = () => {
    const b = document.querySelector('[data-testid="freshness-badge"]');
    const m = (performance as any).memory;
    return { k: 'smp', t: now(), drift_ms: Math.round(Date.now() - now()), route: location.hash,
      vis: document.visibilityState,
      rows: Math.max(document.querySelectorAll('[data-testid^="watch-star-"]').length, document.querySelectorAll('tbody tr').length),
      dom: document.getElementsByTagName('*').length,
      heap_mb: m ? Math.round(m.usedJSHeapSize / 1e5) / 10 : null,
      fresh: b?.getAttribute('data-freshness') ?? null, conn: b?.getAttribute('data-connection') ?? null,
      data_age_ms: b?.getAttribute('data-data-age-ms') || null, label: b?.getAttribute('aria-label') ?? null };
  };
};

const browser = await chromium.launch({
  executablePath: arg('executable', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe') || undefined,
  headless: !flag('headed'),
});
let ctx: any = null;
let page: any = null;

async function openContext(label: string, route: string) {
  if (ctx) { await drain(); await ctx.close().catch(() => {}); }
  ctx = await browser.newContext({ viewport: { width: Number(arg('vw', '1366')), height: Number(arg('vh', '768')) } });
  if (CLOCK) await ctx.clock.install({ time: new Date(Date.now() + CLOCK_OFF) });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  await ctx.addInitScript(INIT, Boolean(CLOCK));
  page = await ctx.newPage();
  page.on('requestfinished', async (r: any) => {
    if (!r.url().includes('/api/')) return;
    try {
      const res = await r.response();
      const h = res ? res.headers() : {};
      const s = await r.sizes().catch(() => null);
      emit({ k: 'net', url: r.url().replace(BASE, ''), method: r.method(), status: res?.status() ?? 0,
        timing: r.timing(), wire: s?.responseBodySize ?? null, hdr_bytes: s?.responseHeadersSize ?? null,
        xc: h['x-cache'] ?? '', enc: h['content-encoding'] ?? 'identity', date: h['date'] ?? '',
        etag: h['etag'] ?? '', cc: h['cache-control'] ?? '', clen: h['content-length'] ?? '' });
    } catch (e) { emit({ k: 'warn', msg: `net: ${String(e).slice(0, 120)}` }); }
  });
  page.on('requestfailed', (r: any) => {
    if (r.url().includes('/api/')) emit({ k: 'netfail', url: r.url().replace(BASE, ''), method: r.method(), err: r.failure()?.errorText ?? '' });
  });
  page.on('console', (m: any) => { if (m.type() === 'error' || m.type() === 'warning') emit({ k: 'console', level: m.type(), text: m.text().slice(0, 300) }); });
  page.on('pageerror', (e: any) => emit({ k: 'pageerror', text: String(e).slice(0, 300) }));
  return load(label, route, () => page.goto(`${BASE}/#/${route}`, { waitUntil: 'domcontentloaded' }));
}

async function load(label: string, route: string, go: () => Promise<unknown>) {
  const tNav = Date.now();
  emit({ k: 'phase', name: label, route, t: tNav });
  let err: string | null = null;
  try { await go(); } catch (e) { err = String(e).slice(0, 200); }
  const ready = await page.evaluate(async (win: number) => {
    const count = () => Math.max(document.querySelectorAll('[data-testid^="watch-star-"]').length, document.querySelectorAll('tbody tr').length);
    const t = Date.now();
    while (Date.now() - t < win * 1000) {
      if (count() > 5) return { rows: count(), t: performance.timeOrigin + performance.now() };
      await new Promise((r) => setTimeout(r, 100));
    }
    return { rows: count(), t: null };
  }, READY_S).catch((e: unknown) => ({ rows: 0, t: null, err: String(e).slice(0, 160) }));
  const nav = await page.evaluate(() => {
    const m = (window as any).__mon?.nav ?? {};
    return { origin: performance.timeOrigin, dcl: m.dcl ?? null, load: m.load ?? null, fcp: m.fcp ?? null,
      transfer: m.transfer ?? null };
  }).catch(() => null);
  emit({ k: 'load', name: label, route, t_nav: tNav, err, ready, nav });
  await page.screenshot({ path: join(OUT, `${label}.png`) }).catch(() => {});
}

async function drain() {
  if (!page) return;
  try {
    const evs = await page.evaluate(() => {
      const w = window as any;
      if (!w.__mon) return [];
      const out = w.__mon.drain();
      out.push(w.__mon.sample());
      return out;
    });
    for (const e of evs) emit(e);
  } catch (e) { emit({ k: 'warn', msg: `drain: ${String(e).slice(0, 120)}` }); }
}

const sleepUntil = async (t: number) => {
  let nextDrain = Date.now() + DRAIN_S * 1000;
  let nextSample = Date.now() + SAMPLE_S * 1000;
  while (Date.now() < Math.min(t, tEnd) && !stopNow()) {
    await new Promise((r) => setTimeout(r, 500));
    if (Date.now() >= nextSample) {
      // نمونهٔ دوره‌ای بی‌تخلیه (سبک)، تا سنِ داده/نشان بینِ دو تخلیه هم دیده شود
      await page.evaluate(() => { const w = window as any; if (w.__mon) w.__mon.q.push(w.__mon.sample()); }).catch(() => {});
      nextSample = Date.now() + SAMPLE_S * 1000;
    }
    if (Date.now() >= nextDrain) { await drain(); nextDrain = Date.now() + DRAIN_S * 1000; }
  }
};

try {
  await openContext('cold-0', JOURNEY[0].route);
  await sleepUntil(Date.now() + WARM_AFTER_S * 1000);
  if (!stopNow() && Date.now() < tEnd) {
    await drain();
    await load('warm-0', JOURNEY[0].route, () => page.reload({ waitUntil: 'domcontentloaded' }));
  }
  let cycle = 0;
  while (!stopNow() && Date.now() < tEnd) {
    for (let i = 0; i < JOURNEY.length && !stopNow() && Date.now() < tEnd; i++) {
      const leg = JOURNEY[i];
      if (cycle > 0 && i === 0 && FRESH_EACH_CYCLE) {
        await openContext(`cold-${cycle}`, leg.route);
      } else if (!(cycle === 0 && i === 0)) {
        await drain();
        emit({ k: 'phase', name: `nav-${cycle}-${i}`, route: leg.route, t: Date.now() });
        await page.evaluate((r: string) => { location.hash = `#/${r}`; }, leg.route);
      }
      await sleepUntil(Date.now() + leg.sec * 1000);
      await drain();
      await page.screenshot({ path: join(OUT, `c${cycle}-${i}-${leg.route}.png`) }).catch(() => {});
    }
    cycle += 1;
  }
} finally {
  await drain();
  emit({ k: 'end', reason: existsSync(STOP) ? 'stop-file' : stopping ? 'sigint' : 'until/duration' });
  await browser.close().catch(() => {});
}
