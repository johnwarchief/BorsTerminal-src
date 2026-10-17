/**
 * tools/perf_market_hours_browser_probe.mts — شواهدِ مرورگریِ مسیرِ دادهٔ بازار
 *
 * چه چیزی می‌سنجد (همه رویِ همان pollingِ خودِ برنامه؛ حلقۀ اضافه نمی‌سازیم):
 *   ۱) چند درخواست /api در دقیقه، حجمِ انتقالِ هر مسیر، و این‌که آیا یکِ داده
 *      از چند مسیرِ جدا خواسته می‌شود
 *   ۲) long taskها (PerformanceObserver) — همان چیزی که کاربر «قِند» می‌بیند
 *   ۳) هزینهٔ JSON.parse پاسخِ بازار (۷ مگابایت در هر polling)
 *   ۴) آیا snapshotِ تازه، scroll/انتخابِ کاربر را می‌شکند
 *   ۵) خطاهای console و درخواست‌های لغوشده/معلق
 *
 * اجرا: ریگِ کنترلی روی ۸۰۲۰ (backend همین ورک‌تری + کپیِ market.db)
 *   MSYS_NO_PATHCONV=1 node --experimental-strip-types \
 *     tools/perf_market_hours_browser_probe.mts --url http://127.0.0.1:8020 --out ...
 */
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const HERE = import.meta.dirname ?? process.cwd();
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
// این ورک‌تری `npm ci` نشده؛ playwright-core را از همان node_modules موجود
// (frontendِ ورک‌تریِ خواهر) قرض می‌گیریم — ابزارِ سنجش است، نه سورسِ اپ.
const req = createRequire(arg('pw', join(HERE, '../../system2-ui/frontend/index.js')));
const { chromium } = req('playwright-core');

const BASE = arg('url', 'http://127.0.0.1:8020').replace(/\/$/, '');
const OUT = resolve(arg('out', join(HERE, '../_audit/perf-market-hours')));
const WINDOW_S = Number(arg('window', '90'));
mkdirSync(OUT, { recursive: true });

async function run(label: string, route: string, vw: number, vh: number) {
  const browser = await chromium.launch({
    executablePath: arg('executable',
      'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe') || undefined,
  });
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();

  const reqs: Array<{ url: string; method: string; ms: number; bytes: number;
    status: number; failed: boolean }> = [];
  const t0 = Date.now();
  page.on('response', (res) => {
    const u = res.url();
    if (!u.includes('/api/')) return;
    reqs.push({ url: u.replace(BASE, '').slice(0, 90), method: res.request().method(),
      ms: Date.now() - t0, bytes: Number(res.headers()['content-length'] ?? 0),
      status: res.status(), failed: !res.ok() });
  });
  page.on('requestfailed', (r) => {
    if (!r.url().includes('/api/')) return;
    reqs.push({ url: r.url().replace(BASE, '').slice(0, 90), method: r.method(),
      ms: Date.now() - t0, bytes: 0, status: 0, failed: true });
  });
  const consoleErrors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e).slice(0, 200)));

  // long taskها و هزینهٔ parse درِ خودِ صفحه ثبت می‌شوند
  await page.addInitScript(() => {
    const w = window as any;
    w.__perf = { longTasks: [], longTotalMs: 0, maxLongMs: 0, mutations: 0, parseMs: [] };
    try {
      const po = new PerformanceObserver((l) => {
        for (const e of l.getEntries()) {
          w.__perf.longTasks.push({ at: Math.round(e.startTime), dur: Math.round(e.duration) });
          w.__perf.longTotalMs += e.duration;
          w.__perf.maxLongMs = Math.max(w.__perf.maxLongMs, e.duration);
        }
      });
      po.observe({ entryTypes: ['longtask'] });
    } catch { /* longtask unsupported */ }
    // هر JSON.parse بزرگ اندازه می‌گیرد: pollingِ ۷ مگابایتی همین‌جا دیده می‌شود
    const orig = JSON.parse.bind(JSON);
    (JSON as any).parse = function (text: any, ...rest: any[]) {
      const s = typeof text === 'string' ? text.length : 0;
      const a = performance.now();
      const out = orig(text, ...rest);
      if (s > 500_000) w.__perf.parseMs.push({ bytes: s, ms: Math.round(performance.now() - a) });
      return out;
    };
    const mo = new MutationObserver((list) => {
      let n = 0;
      for (const m of list) n += m.addedNodes.length + (m.type === 'attributes' ? 1 : 0);
      w.__perf.mutations += n;
    });
    document.addEventListener('DOMContentLoaded', () => {
      const host = document.querySelector('main') ?? document.body;
      mo.observe(host, { childList: true, subtree: true, attributes: true });
    });
  });

  await page.goto(`${BASE}/#${route}`, { waitUntil: 'domcontentloaded' });
  // آمادگی را از خودِ صفحه می‌گیریم، نه از حدسِ testid
  const readyAt = await page.evaluate(async (win: number) => {
    const start = performance.now();
    const t = Date.now();
    while (Date.now() - t < win * 1000) {
      const rows = document.querySelectorAll('tbody tr').length;
      if (rows > 5) return { rows, ms: Math.round(performance.now() - start) };
      await new Promise((r) => setTimeout(r, 200));
    }
    return { rows: document.querySelectorAll('tbody tr').length, ms: null };
  }, WINDOW_S);

  const scrollProbe = await page.evaluate(() => {
    const sc = document.scrollingElement as Element | null;
    const host = Array.from(document.querySelectorAll<HTMLElement>('*'))
      .find((el) => el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 200);
    const target = host ?? sc;
    if (!target) return { scrolled: false };
    (target as HTMLElement).scrollTop = 400;
    return { scrolled: true, before: (target as HTMLElement).scrollTop };
  });
  await page.waitForTimeout(WINDOW_S * 1000);
  const after = await page.evaluate((before: number | undefined) => {
    const sc = document.scrollingElement as Element | null;
    const host = Array.from(document.querySelectorAll<HTMLElement>('*'))
      .find((el) => el.scrollHeight > el.clientHeight + 40 && el.clientHeight > 200);
    const target = (host ?? sc) as HTMLElement | null;
    const w = window as any;
    return {
      scrollAfter: target ? target.scrollTop : null, scrollBefore: before ?? null,
      domNodes: document.getElementsByTagName('*').length,
      rows: document.querySelectorAll('tbody tr').length,
      perf: { longTasks: w.__perf.longTasks.length, longTotalMs: Math.round(w.__perf.longTotalMs),
        maxLongMs: Math.round(w.__perf.maxLongMs), mutations: w.__perf.mutations,
        parseMs: w.__perf.parseMs, worstLongTasks: w.__perf.longTasks
          .slice().sort((a: any, b: any) => b.dur - a.dur).slice(0, 5) },
    };
  }, scrollProbe.before);

  await page.screenshot({ path: join(OUT, `${label}.png`) });
  await browser.close();

  const byPath = new Map<string, { n: number; bytes: number; failed: number }>();
  for (const r of reqs) {
    const key = r.url.split('?')[0];
    const e = byPath.get(key) ?? { n: 0, bytes: 0, failed: 0 };
    e.n += 1; e.bytes += r.bytes; e.failed += r.failed ? 1 : 0;
    byPath.set(key, e);
  }
  return {
    label, route, viewport: `${vw}x${vh}`, window_s: WINDOW_S,
    first_rows_ready: readyAt, requests_total: reqs.length,
    requests_per_min: +(reqs.length / (WINDOW_S / 60)).toFixed(1),
    transfer_bytes_total: reqs.reduce((a, r) => a + r.bytes, 0),
    by_path: [...byPath.entries()].map(([p, v]) => ({ path: p, ...v }))
      .sort((a, b) => b.bytes - a.bytes),
    console_errors: consoleErrors.slice(0, 10),
    ...after,
  };
}

const results = [];
results.push(await run('market-1366x768', '/market', 1366, 768));
results.push(await run('master-1366x768', '/master', 1366, 768));
results.push(await run('market-1920x1080', '/market', 1920, 1080));

const file = join(OUT, 'browser-perf.json');
writeFileSync(file, JSON.stringify({ ran_at: new Date().toISOString(), base: BASE,
  window_s: WINDOW_S, results }, null, 2), 'utf8');
for (const r of results) {
  console.log(`\n### ${r.label}  rows=${r.rows} ready=${r.first_rows_ready.ms}ms`);
  console.log(`requests=${r.requests_total} (${r.requests_per_min}/min) transfer=${(r.transfer_bytes_total / 1048576).toFixed(1)}MB`);
  console.log(`longTasks=${r.perf.longTasks} total=${r.perf.longTotalMs}ms max=${r.perf.maxLongMs}ms mutations=${r.perf.mutations} domNodes=${r.domNodes}`);
  console.log(`parse: ${JSON.stringify(r.perf.parseMs.slice(0, 6))}`);
  console.log(`scroll ${r.scrollBefore} -> ${r.scrollAfter}  consoleErrors=${r.console_errors.length}`);
  console.log(r.by_path.slice(0, 6).map((b) => `  ${b.path} n=${b.n} ${(b.bytes / 1048576).toFixed(2)}MB fail=${b.failed}`).join('\n'));
}
console.log(`\n→ ${file}`);
