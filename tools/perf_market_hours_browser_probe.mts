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
// چقدر برایِ آمدنِ ردیف‌ها صبر کنیم. قبلاً همین `WINDOW_S` بود: وقتی سلکتور
// ردیف نمی‌خورد (پایین‌تر توضیح داده شده) کلِ پنجره درِ انتظار می‌سوخت.
const READY_S = Number(arg('ready', '25'));
// ساعتِ *کلاینت* را می‌توان میخکوب کرد (`--clock=2026-10-17T10:00:00`).
// چرا لازم است: ریتمِ پولینگ از `isMarketOpen()` رویِ `new Date()`ِ مرورگر
// می‌آید، و سنجشِ «کارایی درِ ساعتِ معاملات» بیرونِ آن پنجره هیچ وقتِ باز را
// نمی‌بیند. سرور دست‌نخورده و ساعتِ واقعی می‌ماند؛ فقط صفحه ساعتِ جعلی می‌بیند.
const CLOCK = arg('clock', '');
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
    status: number; failed: boolean; xc: string; enc: string; inm: boolean }> = [];
  const t0 = Date.now();
  page.on('response', (res) => {
    const u = res.url();
    if (!u.includes('/api/')) return;
    const h = res.headers();
    reqs.push({ url: u.replace(BASE, '').slice(0, 90), method: res.request().method(),
      ms: Date.now() - t0, bytes: Number(h['content-length'] ?? 0),
      status: res.status(), failed: !res.ok(),
      // `x-cache` ثابت می‌کند پاسخ از کشِ سرور آمده یا ساخته شده؛ `enc` فقط برای
      // این است که حجمِ واقعیِ سیم (gzip) با حجمِ بدنه اشتباه گرفته نشود؛ `inm`
      // نشان می‌دهد کلاینت واقعاً If-None-Match فرستاده یا نه.
      xc: h['x-cache'] ?? '', enc: h['content-encoding'] ?? 'identity',
      inm: Boolean(res.request().headers()['if-none-match']) });
  });
  page.on('requestfailed', (r) => {
    if (!r.url().includes('/api/')) return;
    reqs.push({ url: r.url().replace(BASE, '').slice(0, 90), method: r.method(),
      ms: Date.now() - t0, bytes: 0, status: 0, failed: true, xc: '', enc: '', inm: false });
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

  if (CLOCK) await page.clock.install({ time: new Date(CLOCK) });
  await page.goto(`${BASE}/#${route}`, { waitUntil: 'domcontentloaded' });
  // آمادگی را از خودِ صفحه می‌گیریم، نه از حدسِ testid.
  //
  // «ردیف» در این اپ `tbody tr` **نیست**: تابلو با div/span رندر می‌شود و
  // مجازی‌سازی دارد، پس آن سلکتور همیشه صفر می‌ماند و حلقه تا آخرِ تایم‌اوت
  // معطل می‌شد (سابقِ `first_rows_ready: null` در گزارشِ پیشین از همین‌جا
  // آمد، نه از صفحهٔ خالی). نشانهٔ پایدارِ ردیف، ستارهٔ نظارتِ هر سطر است.
  const readyAt = await page.evaluate(async (win: number) => {
    const count = () => Math.max(
      document.querySelectorAll('[data-testid^="watch-star-"]').length,
      document.querySelectorAll('tbody tr').length);
    const start = performance.now();
    const t = Date.now();
    while (Date.now() - t < win * 1000) {
      const rows = count();
      if (rows > 5) return { rows, ms: Math.round(performance.now() - start) };
      await new Promise((r) => setTimeout(r, 200));
    }
    return { rows: count(), ms: null };
  }, READY_S);
  // پنجرۀ اندازه‌گیری از *بعدِ* آمادگی شروع می‌شود: وگرنه بارِ اولیه (که ریتم
  // ندارد) با پولینگِ نشست قاطی می‌شود و «درخواست در دقیقه» معنایش می‌بازد.
  const winStart = Date.now() - t0;

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
      rows: Math.max(
        document.querySelectorAll('[data-testid^="watch-star-"]').length,
        document.querySelectorAll('tbody tr').length),
      // نشانهٔ خودِ اپ از وضعیتِ نشست: ریتمِ پولینگ از همین «بازار باز/بسته»
      // می‌آید (`shared/lib/marketHours.ts`)، پس بی‌این خط نمی‌شود فهمید
      // «درخواستِ کم» یعنی بهینه یا یعنی پنجره بیرونِ نشست بوده.
      banner: (document.querySelector('[data-freshness]')?.textContent ?? '').trim().slice(0, 80),
      clock: new Date().toString().slice(0, 33),
      perf: { longTasks: w.__perf.longTasks.length, longTotalMs: Math.round(w.__perf.longTotalMs),
        maxLongMs: Math.round(w.__perf.maxLongMs), mutations: w.__perf.mutations,
        parseMs: w.__perf.parseMs, worstLongTasks: w.__perf.longTasks
          .slice().sort((a: any, b: any) => b.dur - a.dur).slice(0, 5) },
    };
  }, scrollProbe.before);

  await page.screenshot({ path: join(OUT, `${label}.png`) });
  await browser.close();

  type Agg = { n: number; n_all: number; bytes: number; failed: number; n200: number;
    n304: number; n_other: number; revalidated: number; methods: Record<string, number>;
    xc: Record<string, number>; enc: Record<string, number>; };
  // پنجرۀ واقعیِ سنجش: فقط پولینگِ بعدِ آماده‌شدن، نه بارِ اولیه.
  const win = reqs.filter((r) => r.ms >= winStart);
  const byPath = new Map<string, Agg>();
  for (const r of reqs) {
    const key = r.url.split('?')[0];
    const e = byPath.get(key) ?? { n: 0, n_all: 0, bytes: 0, failed: 0, n200: 0, n304: 0,
      n_other: 0, revalidated: 0, methods: {}, xc: {}, enc: {} };
    e.n_all += 1;
    if (r.ms < winStart) { byPath.set(key, e); continue; }
    e.n += 1; e.bytes += r.bytes; e.failed += r.failed ? 1 : 0;
    if (r.status === 304) e.n304 += 1; else if (r.status === 200) e.n200 += 1; else e.n_other += 1;
    if (r.inm) e.revalidated += 1;
    e.methods[r.method] = (e.methods[r.method] ?? 0) + 1;
    if (r.xc) e.xc[r.xc] = (e.xc[r.xc] ?? 0) + 1;
    e.enc[r.enc] = (e.enc[r.enc] ?? 0) + 1;
    byPath.set(key, e);
  }
  const sum = (arr: typeof reqs, f: (r: typeof reqs[number]) => number) =>
    arr.reduce((a, r) => a + f(r), 0);
  return {
    label, route, viewport: `${vw}x${vh}`, window_s: WINDOW_S,
    clock: CLOCK || 'real', ready_wait_s: READY_S,
    first_rows_ready: readyAt, requests_total: reqs.length,
    requests_in_window: win.length,
    requests_per_min: +(win.length / (WINDOW_S / 60)).toFixed(1),
    // wire_bytes = بایت‌هایِ واقعیِ رویِ سوکت (content-lengthِ فشرده)؛ 304 صفر است.
    transfer_bytes_total: sum(reqs, (r) => r.bytes),
    transfer_bytes_in_window: sum(win, (r) => r.bytes),
    responses_304: win.filter((r) => r.status === 304).length,
    responses_200: win.filter((r) => r.status === 200).length,
    requests_with_inm: win.filter((r) => r.inm).length,
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
  window_s: WINDOW_S, clock: CLOCK || 'real', ready_wait_s: READY_S, results }, null, 2), 'utf8');
for (const r of results) {
  console.log(`\n### ${r.label}  rows=${r.rows} ready=${r.first_rows_ready.ms}ms`);
  console.log(`clock=${r.clock}  banner=${r.banner}`);
  console.log(`window: req=${r.requests_in_window} (${r.requests_per_min}/min) ` +
    `200=${r.responses_200} 304=${r.responses_304} inm=${r.requests_with_inm} ` +
    `wire=${(r.transfer_bytes_in_window / 1048576).toFixed(2)}MB   ` +
    `(all incl. first load: ${r.requests_total} / ${(r.transfer_bytes_total / 1048576).toFixed(2)}MB)`);
  console.log(`longTasks=${r.perf.longTasks} total=${r.perf.longTotalMs}ms max=${r.perf.maxLongMs}ms mutations=${r.perf.mutations} domNodes=${r.domNodes}`);
  console.log(`parse: ${JSON.stringify(r.perf.parseMs.slice(0, 6))}`);
  console.log(`scroll ${r.scrollBefore} -> ${r.scrollAfter}  consoleErrors=${r.console_errors.length}`);
  console.log(r.by_path.slice(0, 6).map((b) => `  ${b.path} n=${b.n}/${b.n_all} ` +
    `200=${b.n200} 304=${b.n304} inm=${b.revalidated} ${(b.bytes / 1048576).toFixed(2)}MB ` +
    `xc=${JSON.stringify(b.xc)} fail=${b.failed}`).join('\n'));
}
console.log(`\n→ ${file}`);
