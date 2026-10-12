/** tools/perf_raf_render_probe.mts — Stage 6: نسبت‌دهیِ رندر به‌ازایِ دلتا + منشأِ rAF
 *
 *  فقط مشاهده؛ هیچ تغییرِ رفتاری، هیچ درخواستِ تازه‌ای به منبع، هیچ نوشتنی.
 *  سه چیز را از هم جدا می‌شمارد (قبلاً درِ یکِ شمارندهٔ «گره‌هایِ دست‌خورده» قاطی بود):
 *    ۱) شبکه: پاسخِ /api/market/delta — وضعیت، rev، تعدادِ ردیف، last_sync  (بندۀ Playwright، بیرونِ نخِ اصلیِ صفحه)
 *    ۲) DOM:MutationObserver با تفکیکِ نوعِ تغییر (افزودنِ گره / حذف / متن / کلاسِ فلاش / صفتِ دیگر) و هویتِ ردیف
 *    ۳) هزینه: Task/Script/Layout/RecalcStyle از CDP، به‌ازایِ هر دورِ دلتا
 *
 *  قیدهایِ شناخته‌شده (درِ خروجیِ JSON ذیلِ `limits` هم نوشته می‌شود):
 *    • شمارشِ مستقیمِ render/commitِ React با ابزارِ فعلی ممکن نیست (نه پروفایلرِ ساختۀِ dev، نه
 *      React DevTools hook). معیارِ جایگزین: تعدادِ سلول‌هایی که *مقدارِ دیدنی‌شان* عوض شده
 *      (کلاسِ flash یا متنِ `.num.inline-block`) + ScriptΔ هر دور. این را «تعدادِ render» نخوانید.
 *    • ردیف‌هایِ تابلو درِ gridِ مجازی‌سازی‌شده‌اند (TanStack `useVirtualizer`، `TapeTable.tsx:344`)
 *      و فقط ردیف‌هایِ دیدنی درِ DOM هست‌اند؛ انتخابگرِ قدیمی (`tr`/`table`/`[role=rowgroup]`)
 *      صفر.matches می‌دهد و ناظر رویِ `document.body` می‌افتاد. حالا: `[data-testid="tape-scroll"]`
 *      و هویتِ ردیف از `select-box-${symbol}` (همین فایلِ بالا، سطرِ 232).
 *    • زمانِ انتشارِ داده درِ منبع (TSETMC) درِ هیچ پاسخی نیست؛ `meta.last_sync` زمانِ *چرخۀِ
 *      سرور* است و `rev_at` زمانِ دیدنِ تغییر توسطِ کلاینت. پس Source→Backend غیرقابل‌اندازه‌گیریِ مستقیم.
 *
 *  اجرا (رویِ buildِ dev تا stackها خوانا باشند؛ ۵۱۷۳ → /api به ۸۰۰۱):
 *    MSYS_NO_PATHCONV=1 JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
 *    node --experimental-strip-types tools/perf_raf_render_probe.mts --url http://127.0.0.1:5173/ \
 *      --out _audit/perf_raf_render --seconds 90 --selftest
 *
 *  پنجرۀِ اجرا: بیرونِ ساعتِ بازار ریتمِ پولینگِ تابلو CLOSED_POLL_MS = ۵ دقیقه است
 *  (`marketHours.ts:14`) — با `--seconds 60` هیچِ دلتایی دیده نمی‌شود و خروجی
 *  `blocked` می‌گیرد. سنجشِ واقعی: شنبه–چهارشنبه ۰۸:۴۵–۱۲:۳۰ تهران و `--seconds 120`.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const flag = (n: string) => process.argv.includes(`--${n}`);
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/+$/, '');
const OUT = arg('out', '_audit/perf_raf_render');
const SYM = arg('symbol', 'فولاد');
const SECONDS = Math.max(10, Math.min(Number(arg('seconds', '60')) || 60, 600));
const SELFTEST = flag('selftest');
const SKIP_TECH = flag('skip-tech');
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({
  executablePath: process.env.JEV_CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });

// ── قلاب‌ها پیش‌ازِ هر کدِ برنامه (addInitScript) تا mountِ نمودار هم دیده شود ──
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* دروازۀ UI */ }
  const w = window as unknown as Record<string, any>;
  w.__p = {
    raf: { requested: 0, executed: 0, frames: [] as number[], stacks: {} as Record<string, number> },
    fetch: [] as { url: string; t0: number; t1: number; status: number; bytes: number }[],
    rafAfterVisible: 0,
    navStart: Date.now(),
  };
  const P = w.__p;
  const origRaf = w.requestAnimationFrame.bind(w);
  w.requestAnimationFrame = function (cb: FrameRequestCallback) {
    P.raf.requested++;
    const st = (new Error().stack || '').split('\n').slice(2, 5)
      .map((s) => (s.trim().match(/at ([\w.$<>]+)/) || [0, '?'])[1]).join(' < ');
    P.raf.stacks[st] = (P.raf.stacks[st] || 0) + 1;
    return origRaf((ts) => { P.raf.executed++; if (P.raf.frames.length < 20000) P.raf.frames.push(Math.round(ts)); return cb(ts); });
  };
  // فقط مشاهدهٔ آدرسِ خودِ درخواست‌هایِ تابلو — هیچ بدنه‌ای اینجا خوانده نمی‌شود.
  const origFetch = w.fetch.bind(w);
  w.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : (input as Request)?.url || '';
    const track = /\/api\/market(\/delta)?\?|\/api\/market$/.test(url);
    const t0 = Date.now();
    const res = await origFetch(input as RequestInfo, init);
    if (track) {
      P.fetch.push({
        url: url.replace(/^https?:\/\/[^/]+/, ''), t0, t1: Date.now(),
        status: res.status, bytes: Number(res.headers.get('content-length') || 0),
      });
      if (P.fetch.length > 4000) P.fetch.splice(0, 2000);
    }
    return res;
  };
});

// ── شبکهٔ مشاهده‌ای: بدنه‌هایِ دلتا بیرونِ نخِ اصلیِ صفحه خوانده می‌شوند ──
type NetEv = { url: string; status: number; tNode: number; bytes: number;
               body: null | { kind: string; rev: number | null; rows: number; last_sync: string | null; symbols: string[] } };
const net: NetEv[] = [];
ctx.on('response', async (res) => {
  const url = res.url();
  if (!/\/api\/market/.test(url)) return;
  const ev: NetEv = { url: url.replace(/^https?:\/\/[^/]+/, ''), status: res.status(), tNode: Date.now(), bytes: 0, body: null };
  net.push(ev);
  try {
    const s = await res.sizes();
    ev.bytes = s.bodySize + s.headersSize;
  } catch { /* پاسخِ بسته‌شده */ }
  // فقط دلتا: بدنه‌هایِ کوچک. بدنهٔ کامل (~۶MB) تجزیه نمی‌شود — بارِ بی‌جهت رویِ ماشین.
  if (/\/api\/market\/delta/.test(url) && res.status() === 200) {
    try {
      const j = (await res.json()) as Record<string, unknown>;
      const meta = (j.meta ?? {}) as Record<string, unknown>;
      ev.body = {
        kind: String(j.status ?? '?'),
        rev: typeof j.rev === 'number' ? j.rev : null,
        rows: Array.isArray(j.rows) ? j.rows.length : 0,
        last_sync: (meta.last_sync as string) ?? null,
        // نمادهایِ ردیف‌هایِ تغییریافته — برایِ همپوشانیِ «دeltas چه گفت» با «DOM چه کرد».
        symbols: Array.isArray(j.rows) ? (j.rows as { symbol?: string }[]).map((r) => r?.symbol ?? '').filter(Boolean).slice(0, 400) : [],
      };
    } catch { /* 304/بدنهٔ خوانده‌نشده */ }
  }
  if (net.length > 4000) net.splice(0, 2000);
});

const page = await ctx.newPage();
const cdps = await ctx.newCDPSession(page);
await cdps.send('Performance.enable');
const metrics = async () => {
  const { metrics: m } = await cdps.send('Performance.getMetrics');
  const g = (n: string) => (m.find((x) => x.name === n)?.value ?? 0) as number;
  return { task: g('TaskDuration'), script: g('ScriptDuration'), layout: g('LayoutDuration'),
           style: g('RecalcStyleDuration'), nodes: g('Nodes'), listeners: g('JSEventListeners') };
};
const stat = async () => {
  const r = await cdps.send('Runtime.evaluate', { expression: 'Date.now()', returnByValue: true }) as { result: { value: number } };
  return { nodeNow: Date.now(), pageNow: r.result.value };
};

const out: Record<string, unknown> = {
  base: BASE, startedAt: new Date().toISOString(), secondsRequested: SECONDS,
  clock: null, network: null, technical: null, board: null, limits: {
    react_render_commits: 'شمارشِ مستقیمِ render/commitِ React با این ابزار ممکن نیست؛ معیارِ جایگزین: سلول‌هایِ تغییرمقدار (flash/متن) + ScriptΔ هر دور',
    source_publish_time: 'درِ هیچ پاسخی نیست. meta.last_sync = زمانِ چرخۀِ سرور؛ rev_at = زمانِ دیدنِ کلاینت. Source→Backend غیرقابل‌اندازه‌گیریِ مستقیم.',
    virtualization: 'فقط ردیف‌هایِ دیدنی درِ DOM هست‌اند؛ «۰ ردیفِ دست‌خورده» می‌تواند یعنی «تغییری درِ دیدِ فعلی نبود»، نه «داده عوض نشد». برایِ همانیِ ردیفِ دیدنی از `select-box-${symbol}` استفاده می‌شود (data-testidِ خودِ ردیف ثابت است و هویت نمی‌دهد).',
    delta_body_symbols: 'سرفصلِ ردیف‌هایِ دلتا تا ۴۰۰ نماد نگه داشته می‌شود؛ درِ دلتاهایِ بزرگ‌تر همپوشانیِ «ردیف‌هایِ دیدنیِ نامبرده‌شده درِ دلتا» کم‌برآورد است.',
  },
};

// ── ۱) هزینهٔ mountِ تبِ تکنیکال، جدا از حالتِ پایدار ──────────────────────
if (!SKIP_TECH) {
  await page.goto(`${BASE}/#/technical/${encodeURIComponent(SYM)}`, { waitUntil: 'commit' });
  const marks: Record<string, unknown>[] = [];
  let prev = await metrics();
  let prevRaf = { r: 0, e: 0 };
  const tNav = Date.now();
  for (const at of [1000, 2000, 4000, 8000]) {
    await page.waitForTimeout(Math.max(50, tNav + at - Date.now()));
    const m = await metrics();
    const raf = await page.evaluate(() => ({
      r: (window as any).__p.raf.requested, e: (window as any).__p.raf.executed,
    }));
    const dom = await page.evaluate(() => ({
      nodes: document.querySelectorAll('*').length,
      canvases: document.querySelectorAll('canvas').length,
      rows: document.querySelectorAll('[data-testid="tape-row"]').length,
      chartReady: !!document.querySelector('[data-testid="chart-area"] canvas'),
    }));
    marks.push({ windowMs: at, taskMs: +((m.task - prev.task) * 1000).toFixed(1),
                 scriptMs: +((m.script - prev.script) * 1000).toFixed(1),
                 layoutMs: +((m.layout - prev.layout) * 1000).toFixed(1),
                 styleMs: +((m.style - prev.style) * 1000).toFixed(1),
                 rafRequestedWindow: raf.r - prevRaf.r, rafExecutedWindow: raf.e - prevRaf.e, ...dom });
    prev = m; prevRaf = raf;
  }
  // حالتِ پایدار: اول ۶ ثانیه بی‌کاری، بعدِ آن پنجرۀِ اندازه‌گیری
  await page.waitForTimeout(6000);
  const rafBase = await page.evaluate(() => ({ r: (window as any).__p.raf.requested, e: (window as any).__p.raf.executed, f: (window as any).__p.raf.frames.length }));
  const mBase = await metrics();
  const netBase = net.length;
  await page.waitForTimeout(10000);
  const rafAfter = await page.evaluate((from: number) => {
    const P = (window as any).__p;
    const f = P.raf.frames.slice(from); const gaps: number[] = [];
    for (let i = 1; i < f.length; i++) gaps.push(f[i] - f[i - 1]);
    gaps.sort((a, b) => a - b);
    return { requested: P.raf.requested, executed: P.raf.executed, framesInWindow: f.length,
             lastFrames: f.slice(-20), medianGapMs: gaps.length ? gaps[gaps.length >> 1] : null,
             worstGapMs: gaps.length ? gaps[gaps.length - 1] : null,
             topStacks: Object.entries(P.raf.stacks).sort((a, b) => (b[1] as number) - (a[1] as number)).slice(0, 6) };
  }, rafBase.f);
  const mAfter = await metrics();
  out.technical = {
    symbol: SYM, mountWindows: marks,
    steady: {
      windowMs: 10000,
      rafRequestedDelta: rafAfter.requested - rafBase.r,
      rafExecutedDelta: rafAfter.executed - rafBase.e,
      framesInWindow: rafAfter.framesInWindow,
      medianFrameGapMs: rafAfter.medianGapMs,
      topStacks: rafAfter.topStacks,
      taskMs: +((mAfter.task - mBase.task) * 1000).toFixed(1),
      scriptMs: +((mAfter.script - mBase.script) * 1000).toFixed(1),
      layoutMs: +((mAfter.layout - mBase.layout) * 1000).toFixed(1),
      styleMs: +((mAfter.style - mBase.style) * 1000).toFixed(1),
      domNodes: mAfter.nodes,
      apiResponsesInWindow: net.length - netBase,
    },
    note: 'هرِ سطرِ mountWindows پنجرۀِ (علامتِ پیشین ← این علامت) است، نه تجمعی؛ steady = ۶ ثانیه بی‌کاری و بعدِ آن ۱۰ ثانیه مشاهده. هیچ اندیکاتور/لایه‌ای خاموش نشد.',
  };
  console.log('TECH steady:', JSON.stringify(out.technical.steady));
}

// ── ۲) تابلو: نسبت‌دهیِ DOM به‌ازایِ هر دلتا ───────────────────────────────
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="tape-row"] .num.inline-block', { timeout: 60000 });
await page.waitForTimeout(2500);

const rafBeforeBoard = await page.evaluate(() => (window as any).__p.raf.requested);
await page.evaluate(() => {
  const w = window as unknown as Record<string, any>;
  const host = document.querySelector('[data-testid="tape-scroll"]');
  w.__dom = {
    installed: !!host, hostTag: host ? (host.getAttribute('data-testid') || host.tagName) : null,
    t0: Date.now(), batches: 0, added: 0, removed: 0, text: 0, flash: 0, otherAttr: 0,
    events: [] as { t: number; kind: string; sym: string | null }[],
    batchTimes: [] as number[],
    rowsSeen: 0,
  };
  const D = w.__dom;
  const symOf = (n: Element | null): string | null => {
    const row = n?.closest?.('[data-testid="tape-row"]');
    if (!row) return null;
    const box = row.querySelector('[data-testid^="select-box-"]');
    return box ? box.getAttribute('data-testid').slice('select-box-'.length) : 'row#?';
  };
  const kindOf = (m: MutationRecord): string | null => {
    if (m.type === 'childList') return m.addedNodes.length ? 'added' : (m.removedNodes.length ? 'removed' : null);
    if (m.type === 'characterData') return 'text';
    const tn = (m.target as Element).nodeType === 1 ? (m.target as Element) : (m.target as Element).parentElement;
    const cls = tn && (tn as Element).className;
    const isCell = typeof cls === 'string' && cls.includes('inline-block') && cls.includes('num');
    if (m.attributeName === 'class') return isCell && /flash-(up|down|neutral)/.test((cls as string)) ? 'flash' : 'otherAttr';
    if (m.attributeName === 'title') return 'title';
    return 'otherAttr';
  };
  new MutationObserver((muts) => {
    D.batches++;
    if (D.batchTimes.length < 8000) D.batchTimes.push(Date.now());
    for (const m of muts) {
      const k = kindOf(m);
      if (!k) continue;
      if (k === 'added') D.added += m.addedNodes.length;
      else if (k === 'removed') D.removed += m.removedNodes.length;
      else if (k === 'text') D.text++;
      else if (k === 'flash') D.flash++;
      else D.otherAttr++;
      const tn = (m.target.nodeType === 1 ? m.target : m.target.parentElement) as Element;
      if (D.events.length < 60000) D.events.push({ t: Date.now(), kind: k, sym: symOf(tn) });
    }
    D.rowsSeen = document.querySelectorAll('[data-testid="tape-row"]').length;
  }).observe(host || document.body, { subtree: true, childList: true, characterData: true, attributes: true });
});
const install = await page.evaluate(() => {
  const D = (window as any).__dom;
  return { installed: D.installed, hostTag: D.hostTag, rowsVisible: document.querySelectorAll('[data-testid="tape-row"]').length };
});
if (!install.installed) { console.log('!! ناظر رویِ tape-scroll نصب نشد — selector با ساختارِ فعلی نمی‌خواند'); }

// خودآزمونِ سنسور: ثابت می‌کند شمارنده‌ها کور نیست‌اند. هیچ داده‌ای دستکاری نمی‌شود؛
// فقط یکِ سلولِ دیدنی یک‌بار کلاسِ فلاش/متنِ موقت می‌گیرد و به حالتِ اول برمی‌گردد.
let selftest: Record<string, unknown> = { skipped: true };
if (SELFTEST) {
  selftest = await page.evaluate(() => {
    const D = (window as any).__dom;
    const before = { batches: D.batches, flash: D.flash, text: D.text };
    const cell = document.querySelector('[data-testid="tape-row"] .num.inline-block');
    if (!cell) return { error: 'no .num.inline-block cell' };
    const origText = cell.textContent, origCls = cell.className;
    cell.classList.add('flash-up');
    (cell.firstChild as Text).nodeValue = ((cell.firstChild as Text)?.nodeValue || '') + ' ';
    return new Promise((res) => setTimeout(() => {
      const mid = { batches: D.batches, flash: D.flash, text: D.text };
      cell.className = origCls; (cell.firstChild as Text).nodeValue = origText;
      setTimeout(() => res({
        injected: { flash: mid.flash - before.flash, text: mid.text - before.text, batches: mid.batches - before.batches },
        afterRevert: { batches: D.batches - before.batches, flash: D.flash - before.flash, text: D.text - before.text },
        restored: cell.textContent === origText && cell.className === origCls,
        note: 'selftest = اثباتِ دیدِ سنسور، نه شاهدِ بازار',
      }), 120);
    }, 120));
  });
}

const netWinStart = Date.now();
const baseCounters = (await page.evaluate(() => {
  const D = (window as any).__dom;
  return { batches: D.batches, added: D.added, removed: D.removed, text: D.text, flash: D.flash, otherAttr: D.otherAttr };
})) as Record<string, number>;
const visibleSymbols = () => page.evaluate(() =>
  [...document.querySelectorAll('[data-testid="tape-row"]')].map((r) => {
    const box = r.querySelector('[data-testid^="select-box-"]');
    return box ? box.getAttribute('data-testid').slice('select-box-'.length) : '?';
  }));
const symStart = await visibleSymbols();
const mBoardA = await metrics();
const clockA = await stat();
// نمونۀِ ۱-ثانیه‌ایِ هزینه (یکِ فراخوانیِ CDP در هر ثانیه) تا بتوان Script/Layout را
// به‌ازایِ هر دلتا نسبت داد؛ بی‌این فقطِ میانگینِ کلِ پنجره درِ دست است.
const series: { t: number; task: number; script: number; layout: number; style: number }[] = [];
const tEnd = Date.now() + SECONDS * 1000;
while (Date.now() < tEnd) {
  await page.waitForTimeout(1000);
  const m = await metrics();
  series.push({ t: Date.now(), task: +m.task.toFixed(4), script: +m.script.toFixed(4),
                layout: +m.layout.toFixed(4), style: +m.style.toFixed(4) });
  if (series.length > 900) series.splice(0, 300);
}
const mBoardB = await metrics();
const clockB = await stat();
const symEnd = await visibleSymbols();
const board = await page.evaluate((winStart: number) => {
  const D = (window as any).__dom;
  const P = (window as any).__p;
  return {
    secs: Math.round((Date.now() - D.t0) / 1000), batches: D.batches, added: D.added, removed: D.removed,
    text: D.text, flash: D.flash, otherAttr: D.otherAttr, events: D.events,
    batchTimes: D.batchTimes.filter((t: number) => t >= winStart),
    rowsVisibleNow: document.querySelectorAll('[data-testid="tape-row"]').length,
    domNodes: document.querySelectorAll('*').length,
    countersNow: { batches: D.batches, added: D.added, removed: D.removed, text: D.text, flash: D.flash, otherAttr: D.otherAttr },
    fetchLog: P.fetch.slice(-400),
    rafRequestedDuringBoard: P.raf.requested,
  };
}, netWinStart);
// چشمِ رویداد: لاگِ خودِ صفحه (t1 = لحظۀ رسیدنِ پاسخ روی ساعتِ صفحه، که با ساعتِ
// Node روی این ماشین تا ~۱ms یکی است). بدنه‌هایِ Playwright فقط پیوست می‌شوند.
const winEvents = (board.fetchLog as { url: string; t1: number; status: number; bytes: number }[])
  .filter((f) => f.t1 >= netWinStart);
const bodies = net.filter((e) => e.tNode >= netWinStart);
const ev = (board.events as { t: number; kind: string; sym: string | null }[]).filter((x) => x.t >= netWinStart);
const revOf = (u: string) => { const m = /since=(\d+)/.exec(u); return m ? Number(m[1]) : null; };
const bTimes = board.batchTimes as number[];
const joined = winEvents.map((f) => {
  const isDelta = /\/delta/.test(f.url);
  const near = bodies.find((b) => b.url === f.url && Math.abs(b.tNode - f.t1) <= 3000);
  const prev = winEvents[winEvents.indexOf(f) - 1];
  return {
    at: f.t1, url: f.url, kind: isDelta ? 'delta' : 'full', httpStatus: f.status,
    pageBytes: f.bytes, since: revOf(f.url),
    body: near?.body ?? null,
    revAdvanced: !!(near?.body && prev && (revOf(prev.url) ?? -1) !== (revOf(f.url) ?? -1)) ||
                 (!!isDelta && near?.body?.kind === 'delta'),
  };
});
const changedDeltas = joined.filter((j) => j.kind === 'delta' && j.body?.kind === 'delta');
const windowOnly = (k: string) => (board.countersNow?.[k] ?? 0) - (baseCounters?.[k] ?? 0);
out.clock = { nodeMinusPageMs: Math.round(((clockA.nodeNow + clockB.nodeNow) / 2) - ((clockA.pageNow + clockB.pageNow) / 2)),
              note: 'همۀِ زمان‌ها Date.now() رویِ یکِ ماشین؛ اختلافِ ساعتِ صفحه/Node باید ~۰ باشد' };
out.network = {
  window: joined,
  marketState: { last_sync: changedDeltas[changedDeltas.length - 1]?.body?.last_sync ?? null,
                 TehranWall: new Date(Date.now() + 3.5 * 3600_000).toISOString().slice(0, 16).replace('T', ' ') },
  totals: { responsesInWindow: joined.length, deltas: joined.filter((j) => j.kind === 'delta').length,
            deltasWithChanges: changedDeltas.length, unchanged: joined.filter((j) => j.body?.kind === 'unchanged').length,
            fulls: joined.filter((j) => j.kind === 'full').length,
            playwrightBodiesCaptured: bodies.filter((b) => b.body).length },
};
out.board = {
  selectorInstall: install, selftest,
  blocked: joined.length === 0
    ? 'BLOCKED — درِ اینِ پنجره هیچِ درخواستِ تازۀِ تابلو دیده نشد (بیرونِ ساعتِ بازار ریتم ۵ دقیقۀ CLOSED_POLL_MS است). نسبت‌دهیِ رندر به دلتا نیازمندِ بازارِ باز.'
    : null,
  window: { secs: board.secs, startWall: netWinStart, rowsVisibleNow: board.rowsVisibleNow, domNodes: board.domNodes,
            taskMs: +((mBoardB.task - mBoardA.task) * 1000).toFixed(1),
            scriptMs: +((mBoardB.script - mBoardA.script) * 1000).toFixed(1),
            layoutMs: +((mBoardB.layout - mBoardA.layout) * 1000).toFixed(1),
            styleMs: +((mBoardB.style - mBoardA.style) * 1000).toFixed(1),
            rafRequestedDelta: board.rafRequestedDuringBoard - rafBeforeBoard },
  counters: { batches: windowOnly('batches'), nodesAdded: windowOnly('added'), nodesRemoved: windowOnly('removed'),
              textChangedCells: windowOnly('text'), flashCells: windowOnly('flash'), otherAttr: windowOnly('otherAttr'),
              note: 'text/flash = سلولِ دیدنیِ تغییرمقدار، نه تعدادِ renderِ React؛ otherAttr/title = ردیفی که آبجکتِ داده‌اش عوض شده' },
  perResponse: joined.map((j) => {
    const after = ev.filter((x) => x.t > j.at && x.t <= j.at + 4000);
    const syms = new Set(after.filter((x) => x.kind === 'flash' || x.kind === 'text').map((x) => x.sym).filter(Boolean));
    const objSyms = new Set(after.filter((x) => x.kind === 'title').map((x) => x.sym).filter(Boolean));
    // s0 = آخرینِ نمونه پیش‌ازِ رسیدنِ پاسخ (تا کارِ JSON/React میانِ دو نمونه جا نیفتد)
    const beforeS = series.filter((s) => s.t <= j.at);
    const s0 = beforeS[beforeS.length - 1] ?? series[0];
    const s1 = series.filter((s) => s.t > j.at + 2500)[0] ?? series[series.length - 1];
    const inDelta = new Set(j.body?.symbols ?? []);
    return { at: j.at, kind: j.kind, bodyKind: j.body?.kind ?? null, rev: j.body?.rev ?? null,
             rowsInDelta: j.body?.rows ?? null, pageBytes: j.pageBytes, last_sync: j.body?.last_sync ?? null,
             visibleRowsNamedInDelta: (j.kind === 'delta' ? symStart.filter((s) => inDelta.has(s)).length : null),
             domEvents4s: after.length,
             mutationBatches4s: bTimes.filter((t) => t > j.at && t <= j.at + 4000).length,
             visibleRowsValueChanged: syms.size, visibleRowsDataObjectReplaced: objSyms.size,
             changedSymbols: [...syms].slice(0, 12),
             nodesAdded: after.filter((x) => x.kind === 'added').length,
             nodesRemoved: after.filter((x) => x.kind === 'removed').length,
             scriptMsAfter: +(s1.script - s0.script).toFixed(1), layoutMsAfter: +(s1.layout - s0.layout).toFixed(1),
             styleMsAfter: +(s1.style - s0.style).toFixed(1), taskMsAfter: +(s1.task - s0.task).toFixed(1) };
  }),
  visibleSymbols: { start: symStart, end: symEnd },
  costSeries: series,
  costSeriesSamples: series.length,
  rawFetchLog: board.fetchLog,
};
writeFileSync(`${OUT}.json`, JSON.stringify(out, null, 1), 'utf8');
console.log('CLOCK', JSON.stringify(out.clock));
console.log('INSTALL', JSON.stringify(install));
console.log('SELFTEST', JSON.stringify(selftest));
console.log('BOARD', JSON.stringify(out.board.counters), JSON.stringify(out.board.window));
console.log('NET', JSON.stringify(out.network.totals));
if (out.board.blocked) console.log('!!', out.board.blocked);
console.log('OUT →', `${OUT}.json`);
await browser.close();
