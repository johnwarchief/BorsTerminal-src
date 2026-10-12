// tools/technical_toolbar_wrap_probe.mts — شاهدِ زندهٔ نوارِ ابزارِ تکنیکال در دو قابِ باریک
//
//  این probe برای «Manual Test 2» حکمِ مالک ساخته شده: مسیرِ واقعی #/technical/<نماد> در دو
//  viewport، 1280x720 و 1366x768. همهٔ ادعاها از DOM زنده خوانده می‌شوند، نه از استور:
//
//  sensors:
//   • سطرهای نوار = خوشه‌بندی top فرزندانِ مستقیمِ header.nn-top-toolbar (رواداریِ 6px).
//   • همپوشانی = آزمونِ جفتیِ rect روی button/نشان/دراپ‌داون/گروه (جفت‌های نیاکان‌ـ‌فرزند حذف).
//   • «قابلِ کلیک» = rect داخل viewport + elementFromPoint در مرکز، همان عنصر (یا فرزندش) باشد.
//   • منوها/فلای‌اوت‌ها = rect + پیمایشِ نیاکانِ دارای overflow غیرِvisible (برش).
//   • چارت = ترکیبِ همهٔ canvasهای داخلِ .nn-canvas-area روی یک بومِ خارج از صفحه، در آفستِ
//     خودِ هر canvas (پنلِ حجم کوچک‌تر است و نباید کشیده شود)؛ مرکبِ رنگی = max>60 و
//     max-min>40. پیش از هر خوانش، موس به گوشه پارک می‌شود تا کراس‌هیر در شمارش نیفتد.
//   • جابه‌جاییِ pan با همبستگیِ متقابلِ پروفایلِ ستونی (ZNCC) در بازهٔ ±420px سنجیده می‌شود
//     و در کنارش دلتای لبهٔ چپ/راست می‌آید — کنترلِ مثبت، خودِ درگ است.
//   • zoom با «فلاتِ بدنه» سنجیده می‌شود: runهایی که ستون‌شان از ۲۵٪ بلندترین ستونِ
//     پروفایل رد شود ~ شمارِ کندل‌های دیدنی؛ کنارشِ آن دلتای لبهٔ راست (≥20px) و
//     سنسورهای قدیمی cols/runs به‌عنوانِ محافظه‌کاری می‌آیند. تحویلِ رویداد جداگانه
//     لاگ می‌شود (شمارشِ n و defaultPrevented=dp؛ trusted در هارنسِ CDP همیشه false است
//     و ملاک نیست). اگر هر دو جهتِ zoom بی‌اثر بمانند، یافتهٔ
//     wheel_zoom_not_reaching_handler با شاهدِ تحویل ثبت و صریح «تأییدنشدهٔ پیکسلی» می‌شود.
//
//  checks (خلاصه): overflow افقیِ نوار، همپوشانی صفر، تعداد سطر 1..3، همهٔ کنترل‌های الزامی
//  found+inViewport+topmost؛ منوی کندل و تعدیل: 5 آیتم/در‌قاب/بی‌برش/رویِ سطح؛ رفت‌وبرگشتِ
//  بازه (W سپس D)؛ دیالوگِ تنظیمات باز/تب/بسته؛ فلای‌اوتِ اسلاتِ 0 و 7: باز/بی‌برش/رویِ سطح/بسته؛
//  نوارِ رسم داخلِ بدنه جا می‌شود؛ چارت زنده با ارتفاع مثبت و کفِ بریده‌نشده؛ درگ و wheel اثرِ
//  پیکسلی؛ بقای zoom/pan بعد از تغییرِ viewport؛ سوییچِ موتور به ffc و بازگشت (آخرین فاز هر
//  viewport چون نوار در ffc unmount می‌شود)؛ صفر خطای کنسول/HTTP در جریانِ اصلی (خطاهای فازِ
//  موتور در سبدِ جدا engineErrors می‌نشینند تا سر‌و‌صدای headless گیت را نیندازد).
//
//  PASS این probe مکانیکی است؛ داوریِ بصری نزدِ مالک می‌ماند (visualRuling=owner-pending).
//
//   JEV_CHROME='<chrome.exe>' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/technical_toolbar_wrap_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/technical_toolbar_wrap_probe.json
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
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/technical_toolbar_wrap_probe.json');
const WAIT = Number(arg('wait', '45000'));
const SYM = arg('symbol', 'فولاد');
const VA = { width: Number(arg('wA', '1280')), height: Number(arg('hA', '720')) };
const VB = { width: Number(arg('wB', '1366')), height: Number(arg('hB', '768')) };
const DIR = OUT.split('/').slice(0, -1).join('/') || '.';
mkdirSync(DIR, { recursive: true });
const ORIGIN = new URL(BASE).origin;
const URLX = `${ORIGIN}/#/technical/${encodeURIComponent(SYM)}`;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const r2 = (v: number) => Math.round(v * 100) / 100;

const report: Record<string, unknown> = {
  base: BASE,
  url: URLX,
  symbol: SYM,
  viewportA: VA,
  viewportB: VB,
  env: {},
  steps: {},
  findings: [],
  checks: [],
  errors: [],
  engineErrors: [],
  warnings: [],
  http: [],
  screenshots: [],
  passiveWheelWarnings: 0,
  visualRuling: 'owner-pending',
  notCovered: [
    'تغذیهٔ زنده و به‌روزرسانیِ زیرِ بازار شبیه‌سازی نشد؛ این مسیر فقط با حضورِ مالک در بازارِ باز دیده می‌شود',
    'پنل‌های هشدارِ قیمتی، اسنپ‌شات، تمام‌صفحه و بازپخش خارج از شش انتظارِ اعلام‌شدهٔ این تست‌اند',
    'دکمهٔ حذفِ ترسیم‌ها عمداً کلیک نشد (window.confirm + اثرِ مخرب)؛ فقط وجود و قابِ آن سنجیده می‌شود',
    'صحتِ بصریِ رندر (رنگ/چیدمان) حکمِ مالک است؛ این probe فقط هندسه و پیکسل‌های مرکب را می‌سنجد',
  ],
};
const step = (tag: string, data: unknown) => {
  (report.steps as Record<string, unknown>)[tag] = data;
};
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};
const finding = (id: string, detail: unknown) => {
  (report.findings as Record<string, unknown>[]).push({ id, detail });
};
const warn = (msg: string) => (report.warnings as string[]).push(msg);

// ── خوانندگانِ داخلِ صفحه (خودبسنده؛ هیچ ارجاعی به دامنهٔ Node ندارند) ─────────

const readToolbar = () => {
  const header = document.querySelector('header.nn-top-toolbar') as HTMLElement | null;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const rc = (r: DOMRect) => ({ x: r.left, y: r.top, w: r.width, h: r.height });
  if (!header) return { ok: false, vw, vh, headerRect: null, headerOverflowX: null, rows: [], overlaps: [], controls: [], asideCut: null };
  const hr = header.getBoundingClientRect();
  const headerOverflowX = header.scrollWidth - header.clientWidth;
  const kids = Array.from(header.children).filter((el) => {
    const r = (el as HTMLElement).getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }) as HTMLElement[];
  const tops = kids.map((el) => el.getBoundingClientRect().top).sort((a, b) => a - b);
  const rows: { top: number; count: number }[] = [];
  for (const t of tops) {
    const last = rows[rows.length - 1];
    if (last && Math.abs(t - last.top) <= 6) {
      last.count++;
      last.top = Math.min(last.top, t);
    } else {
      rows.push({ top: Math.round(t * 100) / 100, count: 1 });
    }
  }
  const cands = Array.from(
    header.querySelectorAll('button, .nn-symbol-badge, .nn-select-dropdown, .nn-toolbar-group'),
  ) as HTMLElement[];
  const vis = cands.filter((el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });
  const label = (el: HTMLElement) => el.dataset.testid || String(el.className).split(' ')[0] || el.tagName;
  const overlaps: { a: string; b: string; ix: number; iy: number }[] = [];
  for (let i = 0; i < vis.length; i++) {
    for (let j = i + 1; j < vis.length; j++) {
      const a = vis[i];
      const b = vis[j];
      if (a.contains(b) || b.contains(a)) continue;
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      const ix = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const iy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (ix > 0.5 && iy > 0.5) {
        overlaps.push({ a: label(a), b: label(b), ix: Math.round(ix * 100) / 100, iy: Math.round(iy * 100) / 100 });
      }
    }
  }
  const TIDS = [
    'timeframe-D',
    'timeframe-W',
    'timeframe-M',
    'open-chart-settings',
    'price-alert-bell',
    'nn-engine-switch',
    'nn-engine-klinecharts',
    'nn-engine-ffc',
    'nn-fts-layer-toggle',
    'nn-fib-levels-toggle',
    'nn-history-events-toggle',
    'compare-open',
  ];
  const controls = TIDS.map((tid) => {
    const el = header.querySelector(`[data-testid="${tid}"]`) as HTMLElement | null;
    if (!el) return { tid, found: false, rect: null, inViewport: false, topmost: null };
    const r = el.getBoundingClientRect();
    const inVp = r.left >= -1 && r.top >= -1 && r.right <= vw + 1 && r.bottom <= vh + 1;
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    let top: Element | null = null;
    try {
      top = document.elementFromPoint(Math.max(0, Math.min(vw - 1, cx)), Math.max(0, Math.min(vh - 1, cy)));
    } catch {
      top = null;
    }
    return { tid, found: true, rect: rc(r), inViewport: inVp, topmost: !!(top && (top === el || el.contains(top))) };
  });
  const aside = document.querySelector('.nn-left-toolbar') as HTMLElement | null;
  const body = document.querySelector('.nn-chart-body') as HTMLElement | null;
  let lastBottom = 0;
  let asideBottom = 0;
  let bodyBottom = 0;
  let cutByBody = 0;
  let scrollH = 0;
  let clientH = 0;
  if (aside && body) {
    const ar = aside.getBoundingClientRect();
    const br = body.getBoundingClientRect();
    asideBottom = ar.bottom;
    bodyBottom = br.bottom;
    scrollH = aside.scrollHeight;
    clientH = aside.clientHeight;
    for (const el of Array.from(aside.children) as HTMLElement[]) {
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) continue;
      lastBottom = Math.max(lastBottom, r.bottom);
    }
    cutByBody = Math.round((lastBottom - br.bottom) * 100) / 100;
  }
  return {
    ok: true,
    vw,
    vh,
    headerRect: rc(hr),
    headerOverflowX,
    rows,
    overlaps,
    controls,
    asideCut: { lastBottom, asideBottom, bodyBottom, cutByBody, scrollH, clientH },
  };
};

const readChart = () => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const q = (s: string) => document.querySelector(s) as HTMLElement | null;
  const rc = (el: HTMLElement | null) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  };
  const area = q('.nn-canvas-area');
  const body = q('.nn-chart-body');
  const host = q('[data-testid="nn-chart-host"]');
  const feed = q('[data-testid="nn-feed-error"]');
  const noData = q('[data-testid="nn-no-data"]');
  const out: Record<string, unknown> = {
    ok: !!area,
    vw,
    vh,
    area: rc(area),
    body: rc(body),
    host: rc(host),
    feedError: !!feed,
    feedText: feed ? (feed.textContent ?? '').slice(0, 160) : null,
    noData: !!noData,
    canvasCount: 0,
    ink: null,
  };
  if (!area) return out;
  const ar = area.getBoundingClientRect();
  const canvases = Array.from(area.querySelectorAll('canvas')) as HTMLCanvasElement[];
  const w = Math.max(1, Math.round(ar.width));
  const h = Math.max(1, Math.round(ar.height));
  const off = document.createElement('canvas');
  off.width = w;
  off.height = h;
  const ctx = off.getContext('2d', { willReadFrequently: true });
  let drawn = 0;
  if (ctx) {
    for (const c of canvases) {
      const cr = c.getBoundingClientRect();
      if (cr.width <= 0 || cr.height <= 0) continue;
      try {
        ctx.drawImage(
          c,
          Math.round(cr.left - ar.left),
          Math.round(cr.top - ar.top),
          Math.round(cr.width),
          Math.round(cr.height),
        );
        drawn++;
      } catch {
        /* لایهٔ ناسازگار */
      }
    }
    const { data } = ctx.getImageData(0, 0, w, h);
    const col = new Array(w).fill(0) as number[];
    let inkTotal = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4;
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const mx = Math.max(r, g, b);
        const mn = Math.min(r, g, b);
        if (mx > 60 && mx - mn > 40) {
          col[x]++;
          inkTotal++;
        }
      }
    }
    const bmp = col.map((v) => (v >= 3 ? 1 : 0));
    let runs = 0;
    let inkColumns = 0;
    let leftmost = -1;
    let rightmost = -1;
    for (let x = 0; x < w; x++) {
      if (bmp[x] && (x === 0 || !bmp[x - 1])) runs++;
      if (bmp[x]) {
        inkColumns++;
        if (leftmost < 0) leftmost = x;
        rightmost = x;
      }
    }
    // سنسورِ «فلاتِ بدنهٔ کندل»: روی این چارت خطوطِ میانگین هر ستون را جوهر می‌کنند
    // (بلندیِ کم در پروفایلِ ستونی) و بدنه‌هایِ چسبیده runها را سرِ‌هم می‌کنند؛ پس
    // runهایی می‌شماریم که هر ستونشان از آستانهٔ بلندی رد شود — این عدد تقریباً
    // شمارِ کندلِ دیدنیِ روی صفحه است و به zoom/pan حساس است، برخلافِ runs ساده.
    let hiMax = 0;
    for (const v of col) if (v > hiMax) hiMax = v;
    const hiThresh = Math.max(3, hiMax * 0.25);
    let bodyRuns = 0;
    let bodyCols = 0;
    for (let x = 0; x < w; x++) {
      const hi = col[x] >= hiThresh;
      if (hi && (x === 0 || col[x - 1] < hiThresh)) bodyRuns++;
      if (hi) bodyCols++;
    }
    out.canvasCount = canvases.length;
    out.ink = {
      ok: true,
      w,
      h,
      canvases: canvases.length,
      drawn,
      inkTotal,
      inkColumns,
      runs,
      leftmost,
      rightmost,
      rightGap: rightmost >= 0 ? w - 1 - rightmost : w,
      hiMax,
      hiThresh,
      bodyRuns,
      bodyCols,
      cols: col,
      bmp: bmp.join(''),
    };
  } else {
    out.canvasCount = canvases.length;
  }
  return out;
};

// دفترِ رویدادهای wheel: capture-listener شمارشان می‌کند و یک listener حبابی
// defaultPrevented را بعد از عبورِ کاملِ رویداد (یعنی بعد از کتابخانه) ثبت می‌کند.
// dp=true یعنی هندلرِ عمودیِ klinecharts رویداد را دید و preventDefault کرد.
const installWheelLog = () => {
  const w = window as unknown as Record<string, unknown>;
  w.__wl = [];
  let pending: { rec: Record<string, unknown>; ev: Event } | null = null;
  w.addEventListener(
    'wheel',
    (e) => {
      const we = e as WheelEvent;
      const tgt = (we.target as Element | null) ?? null;
      const cls = tgt ? String((tgt as HTMLElement).className || tgt.tagName) : '';
      const rec: Record<string, unknown> = {
        t: Math.round(performance.now()),
        trusted: we.trusted,
        dy: we.deltaY,
        dx: we.deltaX,
        mode: we.deltaMode,
        cx: we.clientX,
        cy: we.clientY,
        tg: cls.slice(0, 64),
        dp: null,
      };
      (w.__wl as unknown[]).push(rec);
      pending = { rec, ev: e };
    },
    { capture: true, passive: true },
  );
  w.addEventListener(
    'wheel',
    (e) => {
      if (pending && e === pending.ev) pending.rec.dp = (e as WheelEvent).defaultPrevented;
    },
    { passive: true },
  );
};

const drainWheelLog = () => {
  const w = window as unknown as Record<string, unknown>;
  const a = (w.__wl as Record<string, unknown>[]) ?? [];
  w.__wl = [];
  const trusted = a.filter((x) => x.trusted === true).length;
  const dp = a.filter((x) => x.dp === true).length;
  const byTg: Record<string, number> = {};
  for (const x of a) {
    const k = String(x.tg);
    byTg[k] = (byTg[k] ?? 0) + 1;
  }
  return { n: a.length, trusted, dp, byTg, head: a.slice(0, 5), tail: a.slice(-5) };
};

const readMenu = (idx: number) => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const rc = (r: DOMRect) => ({ x: r.left, y: r.top, w: r.width, h: r.height });
  const dds = Array.from(document.querySelectorAll('.nn-select-dropdown')) as HTMLElement[];
  const dd = dds[idx];
  if (!dd) return { ok: false, idx, vw, vh };
  const btn = dd.querySelector('button') as HTMLElement | null;
  const br = btn ? rc(btn.getBoundingClientRect()) : null;
  const menu = dd.querySelector('.nn-dropdown-menu') as HTMLElement | null;
  if (!menu) return { ok: true, idx, open: false, btnRect: br, vw, vh };
  const r = menu.getBoundingClientRect();
  const items = Array.from(menu.querySelectorAll('.nn-dropdown-item')).map((it) =>
    (it.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40),
  );
  let top: Element | null = null;
  try {
    top = document.elementFromPoint(
      Math.max(0, Math.min(vw - 1, r.left + r.width / 2)),
      Math.max(0, Math.min(vh - 1, r.top + r.height / 2)),
    );
  } catch {
    top = null;
  }
  let clippedBy: unknown = null;
  let a = menu.parentElement;
  while (a && a !== document.body && a !== document.documentElement) {
    const cs = getComputedStyle(a);
    const nx = cs.overflowX !== 'visible';
    const ny = cs.overflowY !== 'visible';
    if (nx || ny) {
      const ar = a.getBoundingClientRect();
      const dx = nx ? Math.max(0, r.right - ar.right, ar.left - r.left) : 0;
      const dy = ny ? Math.max(0, r.bottom - ar.bottom, ar.top - r.top) : 0;
      if (dx > 0.5 || dy > 0.5) {
        clippedBy = {
          tag: a.tagName,
          cls: String((a as HTMLElement).className).slice(0, 60),
          ox: cs.overflowX,
          oy: cs.overflowY,
          dx: Math.round(dx * 100) / 100,
          dy: Math.round(dy * 100) / 100,
        };
        break;
      }
    }
    a = a.parentElement;
  }
  const inVp = r.left >= -1 && r.top >= -1 && r.right <= vw + 1 && r.bottom <= vh + 1;
  const itemEls = Array.from(menu.querySelectorAll('.nn-dropdown-item')) as HTMLElement[];
  const itemSizes = itemEls.map((it) => ({
    w: Math.round(it.getBoundingClientRect().width),
    sw: it.scrollWidth,
    t: (it.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 24),
  }));
  const widest = itemSizes.reduce((a, b) => (b.sw > a.sw ? b : a), itemSizes[0] ?? { w: 0, sw: 0, t: '' });
  const widestEl = itemEls.find((it) => it.scrollWidth === widest.sw) ?? null;
  const spans = widestEl ? (Array.from(widestEl.querySelectorAll('span')) as HTMLElement[]) : [];
  const descSpan = spans.length ? spans[spans.length - 1] : null;
  const cs = getComputedStyle(menu);
  const ddRect = rc(dd.getBoundingClientRect());
  return {
    ok: true,
    idx,
    open: true,
    btnRect: br,
    menuRect: rc(r),
    items,
    itemCount: items.length,
    inViewport: inVp,
    topmost: !!(top && (top === menu || menu.contains(top))),
    clippedBy,
    ddRect,
    menuScrollW: menu.scrollWidth,
    menuMinWidth: cs.minWidth,
    menuMaxWidth: cs.maxWidth,
    widest,
    descWhiteSpace: descSpan ? getComputedStyle(descSpan).whiteSpace : null,
    descScrollW: descSpan ? descSpan.scrollWidth : null,
    vw,
    vh,
  };
};

const readSettings = () => {
  const wrap = document.querySelector('[data-testid="chart-settings"]') as HTMLElement | null;
  if (!wrap) return { exists: false };
  const dialog = (wrap.querySelector('[role="dialog"]') as HTMLElement | null) ?? wrap;
  const r = dialog.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const inVp = r.left >= -1 && r.top >= -1 && r.right <= vw + 1 && r.bottom <= vh + 1;
  return {
    exists: true,
    rect: { x: r.left, y: r.top, w: r.width, h: r.height },
    inViewport: inVp,
    scrollOverflowY: dialog.scrollHeight - dialog.clientHeight,
    hasClose: !!document.querySelector('[data-testid="chart-settings-close"]'),
    hasDone: !!document.querySelector('[data-testid="chart-settings-done"]'),
    tabs: Array.from(document.querySelectorAll('[data-testid^="settings-tab-"]')).length,
    vw,
    vh,
  };
};

const readFlyout = (k: number) => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const rc = (r: DOMRect) => ({ x: r.left, y: r.top, w: r.width, h: r.height });
  const wraps = Array.from(document.querySelectorAll('.nn-left-toolbar .tv-slot-wrapper')) as HTMLElement[];
  const w0 = wraps[k];
  if (!w0) return { ok: false, index: k, vw, vh };
  const arrow = w0.querySelector('.tv-slot-arrow') as HTMLElement | null;
  const arr = arrow ? rc(arrow.getBoundingClientRect()) : null;
  const menu = w0.querySelector('.tv-flyout-menu') as HTMLElement | null;
  if (!menu) return { ok: true, index: k, open: false, arrowRect: arr, vw, vh };
  const r = menu.getBoundingClientRect();
  const items = Array.from(menu.querySelectorAll('.tv-flyout-item')).map((it) =>
    (it.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40),
  );
  let top: Element | null = null;
  try {
    top = document.elementFromPoint(
      Math.max(0, Math.min(vw - 1, r.left + r.width / 2)),
      Math.max(0, Math.min(vh - 1, r.top + r.height / 2)),
    );
  } catch {
    top = null;
  }
  let clippedBy: unknown = null;
  let a = menu.parentElement;
  while (a && a !== document.body && a !== document.documentElement) {
    const cs = getComputedStyle(a);
    const nx = cs.overflowX !== 'visible';
    const ny = cs.overflowY !== 'visible';
    if (nx || ny) {
      const ar = a.getBoundingClientRect();
      const dx = nx ? Math.max(0, r.right - ar.right, ar.left - r.left) : 0;
      const dy = ny ? Math.max(0, r.bottom - ar.bottom, ar.top - r.top) : 0;
      if (dx > 0.5 || dy > 0.5) {
        clippedBy = {
          tag: a.tagName,
          cls: String((a as HTMLElement).className).slice(0, 60),
          ox: cs.overflowX,
          oy: cs.overflowY,
          dx: Math.round(dx * 100) / 100,
          dy: Math.round(dy * 100) / 100,
        };
        break;
      }
    }
    a = a.parentElement;
  }
  const inVp = r.left >= -1 && r.top >= -1 && r.right <= vw + 1 && r.bottom <= vh + 1;
  return {
    ok: true,
    index: k,
    open: true,
    arrowRect: arr,
    menuRect: rc(r),
    items,
    itemCount: items.length,
    title: (menu.firstElementChild ? (menu.firstElementChild.textContent ?? '') : '').replace(/\s+/g, ' ').trim().slice(0, 40),
    inViewport: inVp,
    topmost: !!(top && (top === menu || menu.contains(top))),
    clippedBy,
    vw,
    vh,
  };
};

const readEngine = () => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const g = (s: string) => document.querySelector(s) as HTMLElement | null;
  const rc = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  };
  const inVpOf = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    return r.left >= -1 && r.top >= -1 && r.right <= vw + 1 && r.bottom <= vh + 1;
  };
  const topmostOf = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    let top: Element | null = null;
    try {
      top = document.elementFromPoint(
        Math.max(0, Math.min(vw - 1, r.left + r.width / 2)),
        Math.max(0, Math.min(vh - 1, r.top + r.height / 2)),
      );
    } catch {
      top = null;
    }
    return !!(top && (top === el || el.contains(top)));
  };
  const group = g('[data-testid="nn-engine-switch"]');
  const kline = g('[data-testid="nn-engine-klinecharts"]');
  const ffc = g('[data-testid="nn-engine-ffc"]');
  const back = g('[data-testid="fts-engine-back"]');
  const err = g('[data-testid="fts-engine-error"]');
  return {
    vw,
    vh,
    group: group ? { rect: rc(group), inViewport: inVpOf(group), topmost: topmostOf(group) } : null,
    kline: kline
      ? { rect: rc(kline), inViewport: inVpOf(kline), topmost: topmostOf(kline), pressed: kline.getAttribute('aria-pressed') }
      : null,
    ffc: ffc
      ? { rect: rc(ffc), inViewport: inVpOf(ffc), topmost: topmostOf(ffc), pressed: ffc.getAttribute('aria-pressed') }
      : null,
    engineChart: !!g('[data-testid="fts-engine-chart"]'),
    engineHost: !!g('[data-testid="fts-engine-host"]'),
    engineBack: back ? { rect: rc(back), inViewport: inVpOf(back), topmost: topmostOf(back) } : null,
    engineErr: err ? (err.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 200) : null,
    klineHost: !!g('[data-testid="nn-chart-host"]'),
    toolbar: !!g('header.nn-top-toolbar'),
  };
};

const readTf = () => {
  const get = (id: string) => {
    const el = document.querySelector(`[data-testid="timeframe-${id}"]`) as HTMLElement | null;
    return el ? { found: true, active: el.className.includes('active') } : { found: false, active: false };
  };
  return { D: get('D'), W: get('W'), M: get('M') };
};

// ── سنسورِ حرکتی: همبستگیِ متقابلِ پروفایلِ ستونی ─────────────────────────────
const zncc = (a: number[], b: number[]): { shift: number; score: number; score0: number } => {
  const n = Math.min(a.length, b.length);
  const corr = (s: number): number => {
    const lo = Math.max(0, -s);
    const hi = Math.min(n, n - s);
    const len = hi - lo;
    if (len < 120) return -2;
    let ma = 0;
    let mb = 0;
    for (let i = lo; i < hi; i++) {
      ma += a[i];
      mb += b[i + s];
    }
    ma /= len;
    mb /= len;
    let num = 0;
    let da = 0;
    let db = 0;
    for (let i = lo; i < hi; i++) {
      const x = a[i] - ma;
      const y = b[i + s] - mb;
      num += x * y;
      da += x * x;
      db += y * y;
    }
    if (da <= 1e-9 || db <= 1e-9) return -2;
    return num / Math.sqrt(da * db);
  };
  const score0 = corr(0);
  let shift = 0;
  let score = score0;
  for (let s = -420; s <= 420; s++) {
    if (s === 0) continue;
    const v = corr(s);
    if (v > score) {
      score = v;
      shift = s;
    }
  }
  return { shift, score, score0 };
};

const inkOf = (c: Record<string, unknown> | null) => {
  const ink = c ? (c.ink as Record<string, unknown> | null) : null;
  return ink && ink.ok ? ink : null;
};
const inkSummary = (ink: Record<string, unknown> | null) =>
  ink
    ? {
        w: ink.w,
        h: ink.h,
        drawn: ink.drawn,
        inkTotal: ink.inkTotal,
        inkColumns: ink.inkColumns,
        runs: ink.runs,
        leftmost: ink.leftmost,
        rightmost: ink.rightmost,
        rightGap: ink.rightGap,
        bodyRuns: ink.bodyRuns,
        bodyCols: ink.bodyCols,
        hiThresh: ink.hiThresh,
      }
    : null;
const chartStep = (c: Record<string, unknown>, extra: Record<string, unknown> = {}) => ({
  canvasCount: c.canvasCount,
  area: c.area,
  body: c.body,
  feedError: c.feedError,
  feedText: c.feedText,
  noData: c.noData,
  ink: inkSummary(inkOf(c)),
  ...extra,
});

type AnyEval = Record<string, any>;

// ── راه‌اندازی ────────────────────────────────────────────────────────────────
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: VA });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
  } catch {
    /* دروازهٔ محلی */
  }
});
const page = await context.newPage();
let enginePhase = false;
page.on('pageerror', (e: { message: string }) => {
  const bucket = enginePhase ? (report.engineErrors as string[]) : (report.errors as string[]);
  bucket.push(`pageerror: ${e.message}`);
});
let passiveWheelWarnings = 0;
page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
  const url = m.location()?.url ?? '';
  const txt = m.text();
  if (/Unable to preventDefault inside passive/i.test(txt)) {
    passiveWheelWarnings++;
    (report.warnings as string[]).push(`passive-wheel: ${txt.slice(0, 220)}`);
    return;
  }
  if (m.type() === 'error') {
    if (url.endsWith('/favicon.ico')) return;
    const bucket = enginePhase ? (report.engineErrors as string[]) : (report.errors as string[]);
    bucket.push(`console: ${url} :: ${txt.slice(0, 220)}`);
  } else if (m.type() === 'warning') {
    (report.warnings as string[]).push(`${txt.slice(0, 220)}`);
  }
});
page.on('response', (r: { status: () => number; url: () => string }) => {
  if (r.status() >= 400) {
    const bucket = enginePhase ? (report.engineErrors as string[]) : (report.http as string[]);
    bucket.push(`${r.status()} ${r.url()}`);
  }
});

const shot = async (name: string) => {
  const p = `_audit/${name}.png`;
  await page.screenshot({ path: p });
  (report.screenshots as string[]).push(p);
};
const shotClip = async (name: string, r: { x: number; y: number; w: number; h: number } | null | undefined, pad = 8) => {
  if (!r || !(r.w > 0) || !(r.h > 0)) {
    warn(`shotClip ${name}: قابِ نامعتبر`);
    return;
  }
  const vp = page.viewportSize() ?? { width: 0, height: 0 };
  const x = Math.max(0, Math.floor(r.x - pad));
  const y = Math.max(0, Math.floor(r.y - pad));
  const width = Math.min(vp.width - x, Math.ceil(r.w + pad * 2));
  const height = Math.min(vp.height - y, Math.ceil(r.h + pad * 2));
  if (width <= 0 || height <= 0) {
    warn(`shotClip ${name}: قابِ بیرون از viewport`);
    return;
  }
  const p = `_audit/${name}.png`;
  await page.screenshot({ path: p, clip: { x, y, width, height } });
  (report.screenshots as string[]).push(p);
};
const parkInk = async () => {
  await page.mouse.move(4, 4);
  await sleep(280);
};
const rectOf = (sel: string, nth = 0): Promise<{ x: number; y: number; w: number; h: number } | null> =>
  page.evaluate(([s, i]) => {
    const els = Array.from(document.querySelectorAll(s as string)) as HTMLElement[];
    const el = els[i as number];
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  }, [sel, nth] as const);
const clickRect = async (r: { x: number; y: number; w: number; h: number } | null | undefined): Promise<boolean> => {
  if (!r || !(r.w > 0) || !(r.h > 0)) return false;
  const cx = r.x + r.w / 2;
  const cy = r.y + r.h / 2;
  const vp = page.viewportSize() ?? { width: 0, height: 0 };
  if (cx < 0 || cy < 0 || cx > vp.width + 1 || cy > vp.height + 1) return false;
  await page.mouse.click(cx, cy);
  return true;
};
const clickSel = async (sel: string, nth = 0): Promise<boolean> => clickRect(await rectOf(sel, nth));

// ── سناریو ────────────────────────────────────────────────────────────────────
try {
  await page.goto(URLX, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('header.nn-top-toolbar', { timeout: WAIT });
  await page.waitForSelector(
    '[data-testid="nn-chart-host"], [data-testid="nn-feed-error"], [data-testid="nn-no-data"]',
    { timeout: WAIT },
  );
  await sleep(1400);
  await parkInk();
  await shot('tech_00_mount_1280');
  report.env = {
    ua: await page.evaluate(() => navigator.userAgent),
    chrome: process.env.JEV_CHROME ?? 'default',
    pkg: PKG,
  };
  const href = await page.evaluate(() => location.href);
  ck('route_technical_1280', href.includes('/technical/'), { href });

  // ── فاز 1: نوارِ ابزار در 1280 ─────────────────────────────────────────────
  const tb1 = (await page.evaluate(readToolbar)) as AnyEval;
  step('toolbar_1280', {
    headerRect: tb1.headerRect,
    headerOverflowX: tb1.headerOverflowX,
    rows: tb1.rows,
    overlapCount: (tb1.overlaps ?? []).length,
    asideCut: tb1.asideCut,
  });
  ck('toolbar_present_1280', !!tb1.ok, { headerRect: tb1.headerRect });
  ck('toolbar_no_horizontal_overflow_1280', !!tb1.ok && (tb1.headerOverflowX ?? 999) <= 1, {
    headerOverflowX: tb1.headerOverflowX,
    headerRect: tb1.headerRect,
  });
  ck('toolbar_no_overlap_1280', !!tb1.ok && (tb1.overlaps ?? []).length === 0, {
    overlaps: (tb1.overlaps ?? []).slice(0, 6),
  });
  ck('toolbar_rows_sane_1280', !!tb1.ok && (tb1.rows ?? []).length >= 1 && (tb1.rows ?? []).length <= 3, {
    rows: tb1.rows,
  });
  const REQ = [
    'timeframe-D',
    'timeframe-W',
    'timeframe-M',
    'open-chart-settings',
    'price-alert-bell',
    'nn-engine-switch',
    'nn-engine-klinecharts',
    'nn-engine-ffc',
    'nn-fts-layer-toggle',
    'nn-fib-levels-toggle',
    'nn-history-events-toggle',
  ];
  const ctrls1 = (tb1.controls ?? []) as AnyEval[];
  const bad1 = ctrls1.filter((c) => REQ.includes(c.tid) && !(c.found && c.inViewport && c.topmost));
  ck('toolbar_controls_1280', bad1.length === 0, {
    bad: bad1,
    optional: ctrls1.filter((c) => !REQ.includes(c.tid)),
    all: ctrls1.map((c) => `${c.tid}:${c.found ? '1' : '0'}${c.inViewport ? 'v' : '-'}${c.topmost ? 't' : '-'}`).join(' '),
  });
  const eng1 = ctrls1.find((c) => c.tid === 'nn-engine-switch');
  ck('toolbar_engine_switch_clickable_1280', !!(eng1 && eng1.found && eng1.inViewport && eng1.topmost), {
    engine: eng1 ?? null,
  });
  await shotClip('tech_01_toolbar_1280', tb1.headerRect, 8);

  // ── فاز 2: منوهای دراپ‌داون (کندل idx 0، تعدیل idx 1) ─────────────────────
  const menuFlow = async (idx: number, prefix: string, shotName: string, sfx: string) => {
    let m = (await page.evaluate(readMenu, idx)) as AnyEval;
    if (m.ok && !m.open) {
      const ok = await clickRect(m.btnRect);
      if (!ok) warn(`${prefix}: دکمهٔ منو خارج از viewport بود`);
      await sleep(300);
      m = (await page.evaluate(readMenu, idx)) as AnyEval;
    }
    step(`${prefix}_${sfx}`, {
      open: !!m.open,
      itemCount: m.itemCount ?? 0,
      inViewport: m.inViewport ?? null,
      topmost: m.topmost ?? null,
      clippedBy: m.clippedBy ?? null,
      menuRect: m.menuRect ?? null,
      items: m.items ?? null,
      menuScrollW: m.menuScrollW ?? null,
      menuMinWidth: m.menuMinWidth ?? null,
      menuMaxWidth: m.menuMaxWidth ?? null,
      widest: m.widest ?? null,
      descWhiteSpace: m.descWhiteSpace ?? null,
      descScrollW: m.descScrollW ?? null,
    });
    ck(`${prefix}_open_${sfx}`, !!m.ok && !!m.open && m.itemCount === 5, { itemCount: m.itemCount ?? 0 });
    ck(`${prefix}_in_viewport_${sfx}`, !!m.open && m.inViewport === true, { menuRect: m.menuRect ?? null, vw: m.vw, vh: m.vh });
    ck(`${prefix}_unclipped_${sfx}`, !!m.open && (m.clippedBy === null || m.clippedBy === undefined), {
      clippedBy: m.clippedBy ?? null,
      menuRect: m.menuRect ?? null,
    });
    ck(`${prefix}_topmost_${sfx}`, !!m.open && m.topmost === true, { topmost: m.topmost ?? null });
    if (m.open && m.menuRect) await shotClip(shotName, m.menuRect, 12);
    await clickRect(m.btnRect);
    await sleep(280);
    const m2 = (await page.evaluate(readMenu, idx)) as AnyEval;
    ck(`${prefix}_closed_${sfx}`, m2.ok === true && m2.open === false, { closed: m2.open === false });
  };
  await menuFlow(0, 'candle_menu', 'tech_02_candle_menu_1280', '1280');
  await menuFlow(1, 'adj_menu', 'tech_03_adj_menu_1280', '1280');

  // ── فاز 3: رفت‌وبرگشتِ بازهٔ زمانی (W سپس D) ───────────────────────────────
  const tf0 = (await page.evaluate(readTf)) as AnyEval;
  step('timeframe_1280_initial', tf0);
  await clickSel('[data-testid="timeframe-W"]');
  await sleep(950);
  const tfW = (await page.evaluate(readTf)) as AnyEval;
  ck('timeframe_week_active_1280', tfW.W.found && tfW.W.active && !tfW.D.active, { after: tfW, before: tf0 });
  await clickSel('[data-testid="timeframe-D"]');
  await sleep(950);
  const tfD = (await page.evaluate(readTf)) as AnyEval;
  ck('timeframe_back_day_1280', tfD.D.found && tfD.D.active && !tfD.W.active, { after: tfD });

  // ── فاز 4: دیالوگِ تنظیماتِ چارت ───────────────────────────────────────────
  await clickSel('[data-testid="open-chart-settings"]');
  await sleep(450);
  const st = (await page.evaluate(readSettings)) as AnyEval;
  step('settings_1280', st);
  ck('chart_settings_open_1280', !!st.exists, { exists: !!st.exists });
  ck('chart_settings_visible_1280', !!st.exists && st.inViewport === true && st.tabs >= 1, {
    inViewport: st.inViewport,
    tabs: st.tabs,
    hasClose: st.hasClose,
    hasDone: st.hasDone,
    rect: st.rect,
  });
  await shot('tech_04_settings_1280');
  let how = 'none';
  let st2 = st;
  if (st.exists) {
    await clickSel('[data-testid="chart-settings-close"]');
    await sleep(340);
    st2 = (await page.evaluate(readSettings)) as AnyEval;
    if (!st2.exists) how = 'close';
    if (st2.exists) {
      await clickSel('[data-testid="chart-settings-done"]');
      await sleep(340);
      st2 = (await page.evaluate(readSettings)) as AnyEval;
      if (!st2.exists) how = 'done';
    }
    if (st2.exists) {
      await page.keyboard.press('Escape');
      await sleep(340);
      st2 = (await page.evaluate(readSettings)) as AnyEval;
      if (!st2.exists) how = 'escape';
    }
  }
  ck('chart_settings_closed_1280', !st2.exists, { how });

  // ── فاز 5: فلای‌اوت‌های نوارِ رسم (اسلاتِ 0 و اسلاتِ 7) ─────────────────────
  const flyoutFlow = async (k: number, prefix: string, shotName: string, sfx: string) => {
    let f = (await page.evaluate(readFlyout, k)) as AnyEval;
    if (f.ok && !f.open && f.arrowRect) {
      for (let a = 0; a < 2 && !f.open; a++) {
        await clickRect(f.arrowRect);
        await sleep(400);
        f = (await page.evaluate(readFlyout, k)) as AnyEval;
      }
    }
    step(`${prefix}_${sfx}`, {
      open: !!f.open,
      itemCount: f.itemCount ?? 0,
      title: f.title ?? null,
      inViewport: f.inViewport ?? null,
      topmost: f.topmost ?? null,
      clippedBy: f.clippedBy ?? null,
      menuRect: f.menuRect ?? null,
      items: f.items ?? null,
    });
    ck(`${prefix}_open_${sfx}`, !!f.ok && !!f.open && (f.itemCount ?? 0) >= 2, {
      itemCount: f.itemCount ?? 0,
      title: f.title ?? null,
    });
    ck(`${prefix}_unclipped_${sfx}`, !!f.open && (f.clippedBy === null || f.clippedBy === undefined) && f.inViewport === true, {
      clippedBy: f.clippedBy ?? null,
      inViewport: f.inViewport ?? null,
      menuRect: f.menuRect ?? null,
    });
    ck(`${prefix}_topmost_${sfx}`, !!f.open && f.topmost === true, { topmost: f.topmost ?? null });
    if (f.open && f.menuRect) await shotClip(shotName, f.menuRect, 12);
    let method = 'none';
    if (f.open) {
      await clickRect(f.arrowRect);
      await sleep(340);
      let c = (await page.evaluate(readFlyout, k)) as AnyEval;
      if (!c.open) method = 'arrow';
      if (c.open) {
        await page.evaluate(() => {
          const aside = document.querySelector('.nn-left-toolbar') as HTMLElement | null;
          if (aside) aside.click();
        });
        await sleep(320);
        c = (await page.evaluate(readFlyout, k)) as AnyEval;
        if (!c.open) method = 'aside-js';
      }
      ck(`${prefix}_closed_${sfx}`, !c.open, { method });
      if (c.open) finding('flyout_close_failed', { slot: k, suffix: sfx, method });
    } else {
      ck(`${prefix}_closed_${sfx}`, false, { method: 'never-opened' });
    }
  };
  await flyoutFlow(0, 'flyout_slot0', 'tech_05_flyout_slot0_1280', '1280');
  await flyoutFlow(7, 'flyout_slot7', 'tech_06_flyout_slot7_1280', '1280');
  ck(
    'drawing_rail_fits_1280',
    !!tb1.ok && !!tb1.asideCut && tb1.asideCut.cutByBody <= 1 && tb1.asideCut.lastBottom <= (tb1.vh ?? VA.height) + 1,
    tb1.asideCut,
  );

  // ── فاز 6: چارت در 1280 — پیکسل، درگ، wheel ────────────────────────────────
  let ch = (await page.evaluate(readChart)) as AnyEval;
  let attempts = 0;
  for (attempts = 1; attempts <= 24; attempts++) {
    const ink = inkOf(ch);
    if (ink && (ink.inkColumns as number) >= 30) break;
    await sleep(500);
    await parkInk();
    ch = (await page.evaluate(readChart)) as AnyEval;
  }
  step('chart_1280', chartStep(ch, { attempts }));
  const areaA = (ch.area ?? { x: 0, y: 0, w: 0, h: 0 }) as AnyEval;
  const bodyA = (ch.body ?? { x: 0, y: 0, w: 0, h: 0 }) as AnyEval;
  ck('chart_area_present_1280', !!(ch.ok && areaA.w > 100 && areaA.h > 100), { area: ch.area, canvasCount: ch.canvasCount });
  ck('chart_height_positive_1280', (ch.canvasCount as number) > 0 && areaA.h > 160, {
    canvasCount: ch.canvasCount,
    area: ch.area,
  });
  ck(
    'chart_not_bottom_clipped_1280',
    areaA.h >= 160 && areaA.y + areaA.h <= (ch.vh as number) + 1 && bodyA.h >= 160 && areaA.h >= 0.5 * bodyA.h,
    { area: ch.area, body: ch.body, vh: ch.vh },
  );
  const inkA = inkOf(ch);
  ck('ink_sensor_baseline_1280', !!inkA && (inkA.inkColumns as number) >= 30, {
    ink: inkSummary(inkA),
    attempts,
    feedError: ch.feedError,
    noData: ch.noData,
  });

  // 6a. درگِ pan — با کنترلِ مثبتِ درون‌خطی (خودِ درگ)
  const dragAndRead = async (from: { x: number; y: number }, dx: number, steps: number) => {
    await page.mouse.move(from.x, from.y);
    await sleep(40);
    await page.mouse.down();
    for (let i = 1; i <= steps; i++) {
      await page.mouse.move(from.x + (dx * i) / steps, from.y);
      await sleep(16);
    }
    await page.mouse.up();
    await sleep(300);
    await parkInk();
    return (await page.evaluate(readChart)) as AnyEval;
  };
  const dragEffective = (a: Record<string, unknown>, b: Record<string, unknown>) => {
    const A = inkOf(a);
    const B = inkOf(b);
    if (!A || !B) return { ok: false, why: 'no-ink', dl: 0, dr: 0, z: null, corrOk: false };
    const dl = (B.leftmost as number) - (A.leftmost as number);
    const dr = (B.rightmost as number) - (A.rightmost as number);
    const z = zncc(A.cols as number[], B.cols as number[]);
    const corrOk = Math.abs(z.shift) >= 25 && z.score >= 0.5 && z.score > z.score0 + 0.02;
    return { ok: Math.abs(dl) >= 25 || Math.abs(dr) >= 25 || corrOk, dl, dr, z, corrOk };
  };
  const dragFrom = { x: areaA.x + areaA.w * 0.5, y: areaA.y + areaA.h * 0.42 };
  let afterDrag = await dragAndRead(dragFrom, 260, 10);
  let dragRes = dragEffective(ch, afterDrag);
  if (!dragRes.ok) {
    afterDrag = await dragAndRead(dragFrom, 360, 10);
    dragRes = dragEffective(ch, afterDrag);
  }
  step('chart_1280_after_drag', chartStep(afterDrag, { drag: { dl: r2(dragRes.dl), dr: r2(dragRes.dr), corrOk: dragRes.corrOk, shift: dragRes.z ? dragRes.z.shift : null, score: dragRes.z ? r2(dragRes.z.score) : null } }));
  ck('drag_pan_effective_1280', dragRes.ok, {
    dl: r2(dragRes.dl),
    dr: r2(dragRes.dr),
    corr: dragRes.z ? { shift: dragRes.z.shift, score: r2(dragRes.z.score), score0: r2(dragRes.z.score0) } : null,
    before: inkSummary(inkOf(ch)),
    after: inkSummary(inkOf(afterDrag)),
  });
  if (!dragRes.ok) finding('drag_pan_not_effective_1280', { dl: r2(dragRes.dl), dr: r2(dragRes.dr), note: 'درگِ افقیِ 260 و سپس 360 پیکسلی هیچ ردِ پیکسلی نگذاشت؛ یا pan غیرفعال است یا سنسور کور است' });
  await shot('tech_07a_after_drag_1280');

  // 6b. wheel — zoom
  const cpt = { x: areaA.x + areaA.w / 2, y: areaA.y + areaA.h * 0.38 };
  await page.evaluate(installWheelLog);
  const wheelDo = async (times: number, delta: number, gap: number) => {
    await page.mouse.move(cpt.x, cpt.y);
    await sleep(60);
    for (let i = 0; i < times; i++) {
      await page.mouse.wheel(0, delta);
      await sleep(gap);
    }
    await sleep(320);
    await parkInk();
    return (await page.evaluate(readChart)) as AnyEval;
  };
  const zoomEffective = (a: Record<string, unknown>, b: Record<string, unknown>) => {
    const A = inkOf(a);
    const B = inkOf(b);
    if (!A || !B) {
      return { ok: false, why: 'no-ink', dBody: 0, bodyOk: false, dR: 0, rightOk: false, dCols: 0, colsOk: false, dRuns: 0, runsOk: false };
    }
    // سنسورِ اصلی: شمارشِ «فلاتِ بدنه» (سکوهای بلندِ پروفایلِ ستونی) ~ شمارِ کندلِ دیدنی.
    // سنسورهای قدیمی (cols/runs) روی این چارت کورند و فقط برای محافظه‌کاری می‌مانند.
    const dBody = Math.abs((B.bodyRuns as number) - (A.bodyRuns as number));
    const bodyOk = (A.bodyRuns as number) >= 8 && dBody >= Math.max(4, 0.15 * (A.bodyRuns as number));
    // ثانویه: لبهٔ راست — zoom-in به لبه می‌چسبد، zoom-out از نشانگر فاصله می‌گیرد
    const dR = Math.abs((B.rightmost as number) - (A.rightmost as number));
    const rightOk = dR >= 20;
    const dCols = Math.abs((B.inkColumns as number) - (A.inkColumns as number));
    const colsOk = dCols >= Math.max(10, 0.25 * (A.inkColumns as number));
    const dRuns = Math.abs((B.runs as number) - (A.runs as number));
    const runsOk = (A.runs as number) >= 12 && (B.runs as number) >= 12 && dRuns >= Math.max(3, 0.15 * (A.runs as number));
    return {
      ok: bodyOk || rightOk || colsOk || runsOk,
      dBody,
      bodyOk,
      dR,
      rightOk,
      dCols,
      colsOk,
      dRuns,
      runsOk,
      before: { bodyRuns: A.bodyRuns, rightmost: A.rightmost, inkColumns: A.inkColumns, runs: A.runs },
      after: { bodyRuns: B.bodyRuns, rightmost: B.rightmost, inkColumns: B.inkColumns, runs: B.runs },
    };
  };
  let afterZoom = await wheelDo(8, -240, 110);
  let wheelExpected = 8;
  let zoomRes = zoomEffective(afterDrag, afterZoom);
  if (!zoomRes.ok) {
    // محافظه‌کارانه: اگر zoom-in بی‌اثر ماند، جهتِ معکوس هم آزموده می‌شود
    afterZoom = await wheelDo(8, 240, 100);
    wheelExpected = 16;
    zoomRes = zoomEffective(afterDrag, afterZoom);
  }
  const wl = (await page.evaluate(drainWheelLog)) as AnyEval;
  const wheelDelivered = (wl.n as number) > 0 && (wl.dp as number) > 0;
  step('wheel_delivery_1280', {
    ...wl,
    expected: wheelExpected,
    note: 'wheelِ CDP با isTrusted=false می‌رسد؛ ملاکِ تحویل+پردازش، شمارشِ رویداد (n) و defaultPrevented (dp) است، نه trusted',
  });
  ck('wheel_events_delivered_1280', wheelDelivered, { n: wl.n, dp: wl.dp, trusted: wl.trusted, byTg: wl.byTg, expected: wheelExpected });
  step('chart_1280_after_zoom', chartStep(afterZoom, { zoom: zoomRes }));
  ck('wheel_zoom_effective_1280', zoomRes.ok, zoomRes);
  if (!zoomRes.ok) finding('wheel_zoom_not_reaching_handler_1280', { ...zoomRes, delivery: { n: wl.n, dp: wl.dp, byTg: wl.byTg }, note: 'wheel در هر دو جهتِ zoom هیچ تغییری در سنسورِ پیکسلی نگذاشت (تحویلِ رویداد جدا سنجیده شده: wheel_events_delivered_1280)؛ این مسیر «تأییدنشدهٔ پیکسلی» است، نه اثباتِ خرابی' });
  await shot('tech_07_chart_zoomed_1280');

  // ── فاز 7: تغییرِ viewport به 1366 — بقای zoom/pan ─────────────────────────
  await page.setViewportSize(VB);
  await sleep(900);
  await parkInk();
  const chB = (await page.evaluate(readChart)) as AnyEval;
  step('chart_1366_after_resize', chartStep(chB));
  const areaB = (chB.area ?? { x: 0, y: 0, w: 0, h: 0 }) as AnyEval;
  ck('chart_alive_after_resize_1366', (chB.canvasCount as number) > 0 && areaB.h > 160 && areaB.y + areaB.h <= (chB.vh as number) + 1, {
    canvasCount: chB.canvasCount,
    area: chB.area,
  });
  const C0 = (inkOf(ch)?.inkColumns as number) ?? 0;
  const C1 = (inkOf(afterDrag)?.inkColumns as number) ?? 0;
  const C3 = (inkOf(afterZoom)?.inkColumns as number) ?? 0;
  const C4 = (inkOf(chB)?.inkColumns as number) ?? 0;
  ck(
    'zoompan_survives_resize_1280_to_1366',
    Math.abs(C4 - C3) <= Math.max(0.35 * C3, 15) && (Math.abs(C3 - C0) < 0.15 * C0 || Math.abs(C4 - C0) >= 0.1 * C0),
    { C0, C1, C3, C4, note: 'C = شمارشِ ستون‌های مرکب؛ پایداریِ C3→C4 یعنی نمای zoom/pan بعد از resize بازنشانی نشد' },
  );
  await shot('tech_08_after_resize_1366');

  // ── فاز 8: تکرارِ سنسورهای نوار در 1366 ────────────────────────────────────
  const tb2 = (await page.evaluate(readToolbar)) as AnyEval;
  step('toolbar_1366', {
    headerRect: tb2.headerRect,
    headerOverflowX: tb2.headerOverflowX,
    rows: tb2.rows,
    overlapCount: (tb2.overlaps ?? []).length,
    asideCut: tb2.asideCut,
  });
  ck('toolbar_present_1366', !!tb2.ok, { headerRect: tb2.headerRect });
  ck('toolbar_no_horizontal_overflow_1366', !!tb2.ok && (tb2.headerOverflowX ?? 999) <= 1, {
    headerOverflowX: tb2.headerOverflowX,
  });
  ck('toolbar_no_overlap_1366', !!tb2.ok && (tb2.overlaps ?? []).length === 0, {
    overlaps: (tb2.overlaps ?? []).slice(0, 6),
  });
  ck('toolbar_rows_sane_1366', !!tb2.ok && (tb2.rows ?? []).length >= 1 && (tb2.rows ?? []).length <= 3, {
    rows: tb2.rows,
  });
  const ctrls2 = (tb2.controls ?? []) as AnyEval[];
  const bad2 = ctrls2.filter((c) => REQ.includes(c.tid) && !(c.found && c.inViewport && c.topmost));
  ck('toolbar_controls_1366', bad2.length === 0, {
    bad: bad2,
    optional: ctrls2.filter((c) => !REQ.includes(c.tid)),
    all: ctrls2.map((c) => `${c.tid}:${c.found ? '1' : '0'}${c.inViewport ? 'v' : '-'}${c.topmost ? 't' : '-'}`).join(' '),
  });
  const eng2 = ctrls2.find((c) => c.tid === 'nn-engine-switch');
  ck('toolbar_engine_switch_clickable_1366', !!(eng2 && eng2.found && eng2.inViewport && eng2.topmost), {
    engine: eng2 ?? null,
  });
  await shotClip('tech_09_toolbar_1366', tb2.headerRect, 8);

  await menuFlow(0, 'candle_menu', 'tech_10_candle_menu_1366', '1366');
  await menuFlow(1, 'adj_menu', 'tech_11_adj_menu_1366', '1366');
  await flyoutFlow(0, 'flyout_slot0', 'tech_12_flyout_slot0_1366', '1366');
  await flyoutFlow(7, 'flyout_slot7', 'tech_13_flyout_slot7_1366', '1366');
  ck(
    'drawing_rail_fits_1366',
    !!tb2.ok && !!tb2.asideCut && tb2.asideCut.cutByBody <= 1 && tb2.asideCut.lastBottom <= (tb2.vh ?? VB.height) + 1,
    tb2.asideCut,
  );

  // ── فاز 9 (آخرین در هر viewport): سوییچِ موتور — نوار در ffc unmount می‌شود ──
  const engA = (await page.evaluate(readEngine)) as AnyEval;
  step('engine_before_1366', {
    group: engA.group,
    kline: engA.kline,
    ffc: engA.ffc,
    engineChart: engA.engineChart,
    klineHost: engA.klineHost,
    toolbar: engA.toolbar,
  });
  ck(
    'engine_switch_visible_1366',
    !!(engA.group && engA.group.inViewport && engA.group.topmost && engA.kline && engA.kline.pressed === 'true'),
    { group: engA.group, kline: engA.kline },
  );
  enginePhase = true;
  if (engA.ffc && engA.ffc.rect) await clickRect(engA.ffc.rect);
  else warn('engine: دکمهٔ ffc پیدا نشد');
  await page
    .waitForSelector('[data-testid="fts-engine-chart"], [data-testid="fts-engine-back"]', { timeout: 15000 })
    .catch(() => warn('engine ffc: انتظارِ رندر به پایان رسید'));
  await sleep(1300);
  const engB = (await page.evaluate(readEngine)) as AnyEval;
  step('engine_ffc_1366', {
    engineChart: engB.engineChart,
    engineHost: engB.engineHost,
    engineBack: engB.engineBack,
    engineErr: engB.engineErr,
    group: engB.group,
    toolbar: engB.toolbar,
  });
  ck('engine_switch_to_ffc_1366', engB.engineChart === true && !engB.group, {
    engineChart: engB.engineChart,
    toolbarGone: !engB.group,
    engineErr: engB.engineErr,
  });
  if (engB.engineErr) finding('ffc_engine_error_in_headless_1366', { text: engB.engineErr });
  await shot('tech_14_engine_ffc_1366');
  if (engB.engineBack && engB.engineBack.rect) await clickRect(engB.engineBack.rect);
  else warn('engine back: دکمهٔ بازگشت پیدا نشد');
  await page
    .waitForSelector('[data-testid="nn-chart-host"] canvas, header.nn-top-toolbar', { timeout: 15000 })
    .catch(() => warn('engine back: انتظارِ بازگشت به پایان رسید'));
  await sleep(900);
  const engC = (await page.evaluate(readEngine)) as AnyEval;
  step('engine_back_1366', {
    klineHost: engC.klineHost,
    toolbar: engC.toolbar,
    kline: engC.kline,
    group: engC.group,
  });
  enginePhase = false;
  ck(
    'engine_switch_back_kline_1366',
    engC.klineHost === true && engC.toolbar === true && !!(engC.kline && engC.kline.pressed === 'true'),
    { klineHost: engC.klineHost, toolbar: engC.toolbar, kline: engC.kline },
  );
  await parkInk();
  const chF = (await page.evaluate(readChart)) as AnyEval;
  const areaF = (chF.area ?? { x: 0, y: 0, w: 0, h: 0 }) as AnyEval;
  ck('chart_alive_final_1366', (chF.canvasCount as number) > 0 && areaF.h > 160, {
    canvasCount: chF.canvasCount,
    area: chF.area,
    ink: inkSummary(inkOf(chF)),
  });
  await shot('tech_15_final_1366');
} catch (e) {
  (report.errors as string[]).push(`probe: ${e instanceof Error ? e.message : String(e)}`);
  try {
    await shot('tech_99_crash');
  } catch {
    /* بی‌فایده */
  }
} finally {
  report.passiveWheelWarnings = passiveWheelWarnings;
  if (passiveWheelWarnings > 0) {
    finding('passive_wheel_warnings', {
      count: passiveWheelWarnings,
      note: 'هشدارهای کنسول دربارهٔ preventDefault روی شنوندهٔ passive wheel؛ رفتارِ کارکردی در سنسورِ پیکسلی جدا سنجیده شد',
    });
  }
  ck('no_console_errors', (report.errors as string[]).length === 0, {
    errors: (report.errors as string[]).slice(0, 5),
    engineErrors: (report.engineErrors as string[]).length,
  });
  ck('no_http_errors', (report.http as string[]).length === 0, (report.http as string[]).slice(0, 5));

  const checks = report.checks as { ok: boolean; name: string }[];
  const failed = checks.filter((c) => !c.ok).map((c) => c.name);
  report.failed = failed;
  report.verdict = failed.length ? 'FAIL' : 'PASS';
  report.counts = { total: checks.length, passed: checks.length - failed.length };
  report.verdictNote = 'PASS مکانیکی است؛ داوریِ بصری نزدِ مالک می‌ماند (visualRuling=owner-pending)';
  writeFileSync(OUT, JSON.stringify(report, null, 2));
  console.log(`verdict=${report.verdict} ${JSON.stringify(report.counts)}`);
  if (failed.length) console.log(`failed: ${failed.join(', ')}`);
  console.log(`findings: ${JSON.stringify((report.findings as unknown[]).map((f) => (f as { id: string }).id))}`);
  console.log(`engineErrors=${(report.engineErrors as string[]).length} warnings=${(report.warnings as string[]).length}`);
  console.log(`out=${OUT}`);
  process.exitCode = failed.length ? 1 : 0;
  await browser.close();
}
