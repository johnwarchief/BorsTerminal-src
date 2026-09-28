// tools/funnel_live_probe.mts — شاهدِ زندهٔ قیف: خودِ مرورگر چه خوراکی می‌گیرد
//
// چرا: buildFunnel روی پاسخِ واقعیِ /api/market در Node «۱۱۰۶ دامنه / ۴۹ نشانه»
// می‌دهد ولی همان قیف در مرورگر «۱۱۹۳ ← ۰ نشانه» خوانده بود. این دو عدد با
// یک دادهٔ واحد نمی‌سازند، پس باید دید *درونِ صفحه* چه پاسخی می‌رسد: تعدادِ
// ردیف، بودِنِ پنجرۀ حجم، پرچم‌ها، و اینکه آیا چیزی (سرویس‌ورکر/کش/اسکیمای zod)
// ستون‌ها را می‌کاهد. ضمناً چیپ‌های تبِ تابلو از همان cfg و همان فید شمارش
// می‌کنند؛ مقایسۀ «چیپ» با «قیف» معلوم می‌کند خطا در داده است یا در پیکربندی.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/funnel_live_probe.mts \
//     --url http://127.0.0.1:8001/ --out _audit/funnel_live_probe.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:8001/');
const OUT = arg('out', '_audit/funnel_live_probe.json');
const WAIT = Number(arg('wait', '12000'));

const FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];
const WINDOW_KEYS = ['hist_sessions', 'prior30_vol', 'min_low_29'];

const report: Record<string, unknown> = { base: BASE, marketResponses: [], dom: {}, clicked: null, errors: [] };

const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME || undefined,
});
const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') (report.errors as string[]).push(`console: ${m.text().slice(0, 220)}`);
});

// هر پاسخ /api/market که به صفحه می‌رسد، دقیقاً در لحظۀ رسیدن شممرده می‌شود.
page.on('response', async (res: { url: () => string; status: () => number; headers: () => Record<string, string>; json: () => Promise<unknown> }) => {
  const u = res.url();
  if (!u.includes('/api/')) return;
  const h = res.headers();
  const entry: Record<string, unknown> = {
    url: u,
    status: res.status(),
    contentLength: h['content-length'] ?? null,
    etag: h['etag'] ?? null,
    cacheControl: h['cache-control'] ?? null,
    server: h['server'] ?? null,
  };
  // هر پاسخِ JSON با آرایۀ «data» شممرده می‌شود: قیف باید از /api/market
  // بخورد، و اگر دامنه‌اش (۱۱۹۳) با شمارِ خودِ فید (۵۳۶۰) نمی‌خواند، باید دید
  // آیا اصلاً_feedِ دیگری در کار است.
  if (res.status() === 200 && (h['content-type'] ?? '').includes('json')) {
    try {
      const j = (await res.json()) as { count?: number; data?: unknown; meta?: unknown };
      const rows = Array.isArray(j.data) ? (j.data as Record<string, unknown>[]) : null;
      entry.jsonTopKeys = Object.keys(j as object).slice(0, 12);
      if (rows) {
        entry.rows = rows.length;
        entry.keysInRow0 = Object.keys(rows[0] ?? {}).length;
        entry.hasTapeCols = rows.filter((r) => 'hist_sessions' in r || 'prior30_vol' in r || 'min_low_29' in r).length;
        entry.hasFlags = rows.filter((r) => FLAGS.some((k) => k in r)).length;
        entry.flagTrue = rows.filter((r) => FLAGS.some((k) => r[k] === true)).length;
        entry.hasIsLive = rows.filter((r) => 'is_live' in r).length;
      }
    } catch (e) {
      entry.parseError = String(e).slice(0, 160);
    }
  }
  (report.marketResponses as unknown[]).push(entry);
  if (!u.includes('/api/market')) return;
  if (res.status() === 200) {
    try {
      const j = (await res.json()) as { count?: number; data?: Record<string, unknown>[]; meta?: unknown };
      const rows = j.data ?? [];
      entry.meta = j.meta ?? null;
      entry.countField = j.count ?? null;
      entry.rows = rows.length;
      entry.keysInRow0 = Object.keys(rows[0] ?? {}).length;
      entry.missingWindowCols = rows.filter((r) => !('hist_sessions' in r) && !('prior30_vol' in r) && !('min_low_29' in r)).length;
      for (const k of FLAGS) entry[k] = rows.filter((r) => r[k] === true).length;
      for (const k of WINDOW_KEYS) entry[k] = rows.filter((r) => r[k] != null).length;
      entry.isLiveDefined = rows.filter((r) => r['is_live'] !== undefined).length;
      entry.isLiveTrue = rows.filter((r) => r['is_live'] === true).length;
      const anyFlag = rows.filter((r) => FLAGS.some((k) => r[k] === true));
      entry.anyFlag = anyFlag.length;
      entry.anyFlagLive = anyFlag.filter((r) => r['is_live'] !== false).length;
    } catch (e) {
      entry.parseError = String(e).slice(0, 160);
    }
  }
});

await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(Math.min(WAIT, 7000));

// قیف فقط وقتی «قیف انتخاب خودکار» برگزیده باشد_mount می‌شود؛ نقشۀ چهارچارتی
// پیش‌فرضِ تب است، پس نخستین برداشتِ بی‌کلیک همیشه «گره نیست» می‌دهد.
const modeBtn = page.getByText('قیف انتخاب خودکار', { exact: false }).first();
report.clicked = null;
try {
  await modeBtn.click({ timeout: 8000 });
  report.clicked = 'قیف انتخاب خودکار';
} catch (e) {
  report.clicked = `click failed: ${String(e).slice(0, 120)}`;
}
await page.waitForTimeout(WAIT);

const READ = () => {
  const txt = (sel: string) => {
    const el = document.querySelector(sel);
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 300) : null;
  };
  const body = document.body?.innerText ?? '';
  const door = body.split('\n').find((l) => l.includes('ورودیِ قیف')) ?? null;
  const steps: Record<string, string | null> = {};
  steps['funnel-tech-coverage'] = txt('[data-testid="funnel-tech-coverage"]');
  for (const k of ['tape', 'technical', 'fundamental', 'handover']) {
    steps[`funnel-step-${k}`] = txt(`[data-testid="funnel-step-${k}"]`);
    steps[`funnel-stage-${k}`] = txt(`[data-testid="funnel-stage-${k}"]`);
    steps[`funnel-pending-${k}`] = txt(`[data-testid="funnel-pending-${k}"]`);
  }
  return {
    href: location.href,
    door,
    steps,
    bodyHead: body.replace(/\s+/g, ' ').slice(0, 1800),
    sw: {
      controller: !!navigator.serviceWorker?.controller,
      supported: 'serviceWorker' in navigator,
    },
    localKeys: Object.keys(localStorage),
    tapeCfg: localStorage.getItem('bors_tape_filter_config'),
    perfAttrs: {
      perf: document.documentElement.getAttribute('data-perf'),
      idle: document.documentElement.getAttribute('data-idle'),
      flashDur: getComputedStyle(document.documentElement).getPropertyValue('--bors-flash-dur').trim(),
    },
  };
};

report.dom.strategyTree = await page.evaluate(READ as never);

/**
 * خواندنِ ورودی‌هایِ واقعیِ قیف از درخت fiber: دامنه/نشانه‌ای که *خودِ کامپوننت*
 * می‌بیند، نه چیزی که از بیرون بازسازی می‌شود. تا اینجا داده (۵۳۶۰ ردیف، ۱۲۸
 * پرچم) و باندل (بایت‌به‌بایت با buildِ HEAD یکی) هر دو سنجیده بودند و باز
 * «1193 <- 0» می‌آمد؛ پس باید دید feed.data داخلِ اپ چند ردیف دارد.
 */
const FIBER_PROBE = () => {
  const el = document.querySelector('[data-testid="funnel-stage-tape"]') as HTMLElement | null;
  if (!el) return { error: 'no funnel node' };
  const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
  if (!key) return { error: 'no fiber key' };
  const out: Record<string, unknown> = { hops: 0, hooks: [] as unknown[], hookShapes: [] as unknown[] };
  const rowsOf = (v: unknown) => (Array.isArray(v) ? v.length : v && typeof v === 'object' && Array.isArray((v as { data?: unknown[] }).data) ? (v as { data: unknown[] }).data.length : null);
  /** هر آبجکتِ قیف را در عمقِ ۳ پیدا می‌کند: شکلِ useMemo در React ۱۹ یک لایه‌ای
   *  `{memoizedState, deps}` است و ممکن است بیشتر بپیچد. */
  const dig = (v: unknown, depth: number, hits: Record<string, unknown>[]) => {
    if (!v || typeof v !== 'object' || depth > 3) return;
    const o = v as Record<string, unknown>;
    if ('boardScope' in o && 'stages' in o) hits.push(o);
    for (const k of ['memoizedState', 'memoizedProps', 'current', 'data']) {
      if (o[k] && typeof o[k] === 'object') dig(o[k], depth + 1, hits);
    }
  };
  let f: unknown = (el as unknown as Record<string, unknown>)[key];
  for (let hop = 0; f && hop < 80; hop++) {
    out.hops = hop;
    const fbr = f as { memoizedState?: unknown; return?: unknown; type?: { name?: string; displayName?: string } };
    const name = fbr.type?.name ?? fbr.type?.displayName ?? '';
    let h = fbr.memoizedState as { memoizedState?: unknown; next?: unknown } | null;
    let i = 0;
    while (h && i < 40) {
      const ms = h.memoizedState as Record<string, unknown> | null;
      const hits: Record<string, unknown>[] = [];
      dig(ms, 0, hits);
      for (const c of hits) {
        const st = c.stages as Record<string, { entries: { symbol: string }[] }>;
        (out.hooks as unknown[]).push({
          hop, name, kind: 'funnel', i,
          boardScope: c.boardScope, total: c.total,
          stageCounts: Object.fromEntries(Object.entries(st).map(([k, v]) => [k, v.entries.length])),
          firstSymbols: (st.tape?.entries ?? []).slice(0, 6).map((e) => e.symbol),
        });
      }
      if (ms && typeof ms === 'object') {
        const q = ms as { data?: { data?: unknown[]; count?: number }; status?: string; error?: { message?: string }; dataUpdatedAt?: number };
        if (q.data && typeof q.data === 'object' && Array.isArray(q.data?.data)) {
          const arr = q.data.data;
          const r0 = (arr[0] ?? {}) as Record<string, unknown>;
          (out.hooks as unknown[]).push({
            hop, name, i, kind: 'query',
            rows: arr.length,
            count: q.data.count ?? null,
            status: q.status ?? null,
            updatedAt: q.dataUpdatedAt ?? null,
            err: q.error?.message?.slice(0, 90) ?? null,
            feedKeys: Object.keys(q.data as object).slice(0, 10),
            row0Keys: Object.keys(r0).length,
            row0KeyNames: Object.keys(r0).slice(0, 6),
            row0IsArray: Array.isArray(r0),
            row0Sample: JSON.stringify(r0)?.slice(0, 220) ?? null,
            row0Proto: Object.getPrototypeOf(r0)?.constructor?.name ?? null,
            row0HasTape: ['hist_sessions', 'prior30_vol', 'min_low_29'].some((k) => k in r0),
            row0HasFlag: ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'].some((k) => k in r0),
            flagTrue: arr.filter((x) => ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'].some((k) => (x as Record<string, unknown>)[k] === true)).length,
            liveNotFalse: arr.filter((x) => (x as Record<string, unknown>).is_live !== false).length,
          });
        }
        const rl = rowsOf(ms);
        if (rl != null && rl > 10) {
          (out.hooks as unknown[]).push({ hop, name, i, kind: 'array', len: rl });
        }
        if ('clock' in ms && 'jet' in ms && 'suspiciousVolume' in ms) {
          (out.hooks as unknown[]).push({ hop, name, i, kind: 'cfg', cfg: ms });
          const p = (f as { memoizedProps?: Record<string, unknown> }).memoizedProps;
          if (p) (out.hooks as unknown[]).push({ hop, name, i, kind: 'props', preset: p.preset ?? null, propKeys: Object.keys(p).slice(0, 8) });
        }
        if (Array.isArray(ms) && ms.every((x) => typeof x === 'string')) {
          (out.hooks as unknown[]).push({ hop, name, i, kind: 'stringArray', value: ms });
        }
      }
      (out.hookShapes as unknown[]).push({
        hop, name, i,
        t: ms === null ? 'null' : Array.isArray(ms) ? 'array' : typeof ms,
        keys: ms && typeof ms === 'object' && !Array.isArray(ms) ? Object.keys(ms).slice(0, 8) : null,
        len: Array.isArray(ms) ? ms.length : undefined,
      });
      h = h.next as typeof h;
      i++;
    }
    f = fbr.return;
  }
  return out;
};
report.dom.fiber = await page.evaluate(FIBER_PROBE as never);
await page.screenshot({ path: OUT.replace(/\.json$/, '_tree.png'), fullPage: false });

// تبِ تابلو: چیپ‌ها با همان cfg و همان فید می‌شمارند — مقایسۀ deciding
await page.goto(`${BASE}#/`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(Math.min(WAIT, 9000));
const board = await page.evaluate(() => {
  const bar = document.querySelector('[data-testid="quick-filters-bar"]');
  const chips = Array.from(bar?.querySelectorAll('button') ?? []).map((b) =>
    (b.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40),
  );
  const counter = document.querySelector('[data-testid="tape-row-counter"]');
  return {
    chips: chips.slice(0, 24),
    counter: counter ? (counter.textContent ?? '').trim() : null,
    bodyCounter: (document.body.innerText.match(/[^\n]*نماد[^\n]*/g) ?? []).slice(0, 6),
  };
});
report.dom.board = board;
await page.screenshot({ path: OUT.replace(/\.json$/, '_board.png'), fullPage: false });

mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report.dom, null, 2).slice(0, 2600));
console.log('responses', JSON.stringify(report.marketResponses, null, 1).slice(0, 2600));
console.log('errors', report.errors);
await browser.close();
