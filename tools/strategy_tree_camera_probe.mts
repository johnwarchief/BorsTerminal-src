// tools/strategy_tree_camera_probe.mts — شاهدِ زندهٔ دوربینِ بومِ درخت استراتژی (#/strategy-tree)
//
//  این probe برای «Manual Test 1» حکمِ مالک ساخته شده: سوژهٔ واقعی StrategyGraphRenderer است
//  (نه ObsidianStrategyGraph که فقط در تست‌ها استفاده می‌شود). همهٔ ادعاها از DOM زنده و
//  ماتریسِ transform خوانده می‌شوند، نه از استور:
//
//  sensors:
//   • transform واقعی = getComputedStyle(div[style*=translate]).transform → matrix(z,0,0,z,e,f)
//   • مبدأِ سنجش = rect خودِ .nodes-layer، نه translateDiv: در RTL این لایه پهن‌تر از قاب است
//     و ~۴۰۰px به چپ سرریز می‌کند (clientW−layerW)؛ نقشهٔ واقعی: screen = nlRect + zoom × local
//     و باقی‌ماندهٔ هر گره (بدونِ گرهِ گزیده) باید زیرِ یک پیکسل بماند — اثباتِ اینکه pan/zoom
//     فقط دوربین را می‌برد و هندسه را نه. گرهِ گزیده (scale-102) از affine مستثناست و
//     هندسه‌اش (پهنای ۱٫۰۲× و جابه‌جاییِ مرکزمحور ~۰٫۰۱×w) با چکِ اختصاصی سنجیده می‌شود.
//   • خوانشِ ٪ نوارِ کنترل به‌عنوانِ سنسورِ دومِ zoom (مستقل از ماتریس).
//
//  checks:
//   ۱. mount: zoom == clamp(min((cw−۸۰)/bw,(ch−۸۰)/bh), ۰٫۴۵, ۱٫۲) — معناشناسیِ fitView در مانت.
//   ۲. drag: دلتای pan مو‌به‌مو برابرِ دلتای موس؛ مختصاتِ گرافیِ همهٔ گره‌ها نایکنواست.
//   ۳. دکمه‌های + / −: نسبتِ دقیقِ ۱٫۱۵ / ۰٫۸۵ (تلورانسِ ۲e-4 به‌خاطرِ سریال‌سازیِ ماتریس)؛ pan دست‌نخورده.
//   ۴. wheel روی نقطهٔ کرسر: نقطهٔ گرافیِ زیرِ کرسر ثابت می‌ماند (zoom-to-cursor).
//   ۵. کنترلِ مثبتِ حرکت: درگِ بلندِ ۷۰۰px باید pan و صفحهٔ همهٔ گره‌ها را ۷۰۰px ببرد
//      (اگر این صفر شود، سنسور کور است و نتیجهٔ «تکان نخورد» بی‌ارزش می‌شود).
//   ۶. «گستره» (fitView) باید کادرِ مانت را مو‌به‌مو بازتولید کند؛ «٪» باید zoom=۱ و
//      مرکزِ bounds را بدهد (دو معنای متفاوتِ reset — هر دو با فرمولِ خودِ کد سنجیده می‌شوند).
//      کلیپِ چپِ گره‌ها در دوربینِ fit یافتهٔ جداست (شمارشِ دقیق؛ داوریِ بصریِ مالک، نه PASS/FAIL).
//   ۷. تغییرِ viewport و بازگشت: state دوربین باید دست‌نخورده بماند و affine دوباره برقرار شود.
//   ۸. inspector: در مانت باز است (stage_selection)؛ ✕ می‌بندد؛ کلیکِ گره بدونِ حرکتِ دوربین
//      بازش می‌کند؛ در حینِ wheel باز می‌ماند؛ یک رانشِ کوچک روی بدنهٔ inspector ثبت می‌شود
//      (یافتهٔ لبه‌ای — نه PASS/FAIL).
//   ۹. کشوی کاندیداها: باز/بسته می‌شود و درگ روی نوارِ آزادِ بوم (سمتِ راست — کشو در RTL
//      سمتِ چپ را می‌پوشاند) در حینِ باز بودنش pan می‌دهد.
//   ۱۰. یکپارچگیِ پایانی: مجموعهٔ عنوان‌ها و مسیرِ فعال (اجتماعِ فعال∪گزیده) مثلِ مانت.
//   هشدارهای passive-wheel کنسول به warnings می‌روند و یافتهٔ wheel_preventdefault_ineffective
//   می‌شوند، نه خطا. PASS این probe مکانیکی است؛ یافتهٔ کلیپِ چپ فقط با داوریِ مالک معنا دارد.
//
//   JEV_CHROME='<chrome.exe>' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/strategy_tree_camera_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/strategy_tree_camera_probe.json
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
const OUT = arg('out', '_audit/strategy_tree_camera_probe.json');
const WAIT = Number(arg('wait', '45000'));
const VA = { width: Number(arg('wA', '1400')), height: Number(arg('hA', '1260')) };
const VB = { width: Number(arg('wB', '1366')), height: Number(arg('hB', '768')) };
const DIR = OUT.split('/').slice(0, -1).join('/') || '.';
mkdirSync(DIR, { recursive: true });

// ارقامِ فارسی از نقطه‌کد ساخته می‌شوند تا ویرایشِ اسکریپتی رقم را ندزدد
const FA = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d)).join('');
const FAD = '[' + FA[0] + '-' + FA[9] + ']';
const FA_RE = new RegExp(FAD + '+');
const faNum = (s: string | null): number | null => {
  const m = (s ?? '').match(FA_RE);
  if (!m) return null;
  return Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const r2 = (v: number) => Math.round(v * 100) / 100;
const near = (a: number, b: number, eps: number) => Math.abs(a - b) <= eps;

const report: Record<string, unknown> = {
  base: BASE,
  viewportA: VA,
  viewportB: VB,
  steps: {},
  findings: [],
  checks: [],
  errors: [],
  warnings: [],
  http: [],
  screenshots: [],
};
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};
const finding = (id: string, detail: unknown) => {
  (report.findings as Record<string, unknown>[]).push({ id, detail });
};

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
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
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
    (report.errors as string[]).push(`console: ${url} :: ${txt.slice(0, 220)}`);
  } else if (m.type() === 'warning') {
    (report.warnings as string[]).push(`${txt.slice(0, 220)}`);
  }
});
page.on('response', (r: { status: () => number; url: () => string }) => {
  if (r.status() >= 400) (report.http as string[]).push(`${r.status()} ${r.url()}`);
});

const shot = async (name: string) => {
  const p = `_audit/${name}.png`;
  await page.screenshot({ path: p });
  (report.screenshots as string[]).push(p);
};

// ── خوانشِ کاملِ دوربین + هندسه از DOM زنده ──────────────────────────────────
type Snap = {
  ok: boolean;
  zoom: number;
  pan: [number, number];
  zoomReadout: number | null;
  cw: number;
  ch: number;
  canvasRect: { x: number; y: number; w: number; h: number };
  base: [number, number];
  border: number;
  boundsW: number;
  boundsH: number;
  nodes: { title: string; left: number; top: number; w: number; h: number; rect: { x: number; y: number; w: number; h: number }; cls: string }[];
  affineMaxErr: number;
  widthMaxErr: number;
  affineWorstTitle: string;
  widthWorstTitle: string;
  selScale102: { ratio: number; wErr: number; shiftGraph: number; w: number; title: string } | null;
  inBoundsCount: number;
  nOutside: number;
  maxLeftClip: number;
  rightGap: number;
  activeCount: number;
  selectedCount: number;
  inspectorOpen: boolean;
  inspectorLabel: string | null;
  drawerOpen: boolean;
  scrollY: number;
  scrollable: boolean;
};

const readSnap = (): Snap => {
  // این تابع به‌صورت رشته داخل صفحه اجرا می‌شود؛ هیچ ارجاعی به دامنهٔ Node ندارد
  const faD = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d));
  const parseFa = (s: string | null): number | null => {
    const m = (s ?? '').match(new RegExp(`[${faD[0]}-${faD[9]}]+`));
    if (!m) return null;
    return Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
  };
  const fail: Snap = {
    ok: false, zoom: 0, pan: [0, 0], zoomReadout: null, cw: 0, ch: 0,
    canvasRect: { x: 0, y: 0, w: 0, h: 0 }, base: [0, 0], border: 0, boundsW: 0, boundsH: 0,
    nodes: [], affineMaxErr: 0, widthMaxErr: 0, affineWorstTitle: '', widthWorstTitle: '', selScale102: null,
    inBoundsCount: 0, nOutside: 0, maxLeftClip: 0, rightGap: 0, activeCount: 0, selectedCount: 0,
    inspectorOpen: false, inspectorLabel: null, drawerOpen: false, scrollY: 0, scrollable: false,
  };
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]') as HTMLElement | null;
  if (!canvas) return fail;
  const tl = Array.from(canvas.children).find(
    (el) => (el as HTMLElement).style && (el as HTMLElement).style.transform.includes('translate'),
  ) as HTMLElement | undefined;
  if (!tl) return fail;
  const m = new DOMMatrixReadOnly(getComputedStyle(tl).transform); // matrix(zoom,0,0,zoom,e,f)
  const zoom = m.a;
  const e = m.e;
  const f = m.f;
  const cr = canvas.getBoundingClientRect();
  const nl = tl.querySelector('.nodes-layer') as HTMLElement | null;
  // مبدأِ واقعیِ نقشه = گوشهٔ .nodes-layer (نه translateDiv): در RTL این لایه پهن‌تر از قاب است
  // و به چپ سرریز می‌کند؛ screen = nlRect + zoom × local تنها نقشهٔ درست است.
  const nlRect = nl ? nl.getBoundingClientRect() : null;
  const base: [number, number] = nlRect ? [nlRect.left, nlRect.top] : [cr.left, cr.top];
  const border = parseFloat(getComputedStyle(canvas).borderLeftWidth) || 0;
  const boundsW = nl ? parseFloat(nl.style.width) : 0;
  const boundsH = nl ? parseFloat(nl.style.height) : 0;
  const els = Array.from(tl.querySelectorAll('.nodes-layer > div[role="button"]')) as HTMLElement[];
  let affineMaxErr = 0;
  let widthMaxErr = 0;
  let affineWorstTitle = '';
  let widthWorstTitle = '';
  let selScale102: Snap['selScale102'] = null;
  let inBoundsCount = 0;
  let nOutside = 0;
  let maxLeftClip = 0;
  let rightmost = -Infinity;
  let activeCount = 0;
  let selectedCount = 0;
  const nodes = els.map((el) => {
    const rr = el.getBoundingClientRect();
    const left = parseFloat(el.style.left);
    const top = parseFloat(el.style.top);
    const w = parseFloat(el.style.width);
    const h = parseFloat(el.style.height);
    const title = el.querySelector('span[title]')?.getAttribute('title') ?? '';
    const cls = el.className;
    // گرهِ گزیده scale-102 دارد (scale مرکزمحور): پهنای ۱٫۰۲× و لبهٔ چپ −۰٫۰۱×w؛
    // از معیارِ affine مستثنا و جداگانه سنجیده می‌شود.
    if (/\bscale-102\b/.test(cls)) {
      selScale102 = {
        ratio: rr.width / (zoom * w),
        wErr: Math.abs(rr.width - zoom * w * 1.02),
        shiftGraph: (rr.left - base[0]) / zoom - left,
        w,
        title,
      };
    } else {
      // خطاها در فضای صفحه سنجیده می‌شوند: screen باید nlRect + zoom × local باشد
      const ex = Math.abs(rr.left - (base[0] + zoom * left));
      const ey = Math.abs(rr.top - (base[1] + zoom * top));
      const ew = Math.abs(rr.width - zoom * w);
      if (Math.max(ex, ey) > affineMaxErr) {
        affineMaxErr = Math.max(ex, ey);
        affineWorstTitle = title;
      }
      if (ew > widthMaxErr) {
        widthMaxErr = ew;
        widthWorstTitle = title;
      }
    }
    const inside =
      rr.left >= cr.left - 0.5 && rr.top >= cr.top - 0.5 && rr.right <= cr.right + 0.5 && rr.bottom <= cr.bottom + 0.5;
    if (inside) inBoundsCount++;
    else nOutside++;
    maxLeftClip = Math.max(maxLeftClip, cr.left - rr.left);
    rightmost = Math.max(rightmost, rr.right);
    if (cls.includes('border-border-accent')) activeCount++;
    if (/\bring-2\b/.test(cls)) selectedCount++;
    return {
      title,
      left, top, w, h,
      rect: { x: rr.left, y: rr.top, w: rr.width, h: rr.height },
      cls,
    };
  });
  const pctBtn = canvas.querySelector('button[title^="بازنشانی"]') as HTMLElement | null;
  const inspector = document.querySelector('[data-testid="strategy-node-inspector"]') as HTMLElement | null;
  const drawer = document.querySelector('[data-testid="stage-candidate-drawer"]') as HTMLElement | null;
  const se = document.scrollingElement as HTMLElement;
  return {
    ok: true,
    zoom, pan: [e, f],
    zoomReadout: parseFa(pctBtn ? pctBtn.textContent : null),
    cw: canvas.clientWidth, ch: canvas.clientHeight,
    canvasRect: { x: cr.left, y: cr.top, w: cr.width, h: cr.height },
    base, border, boundsW, boundsH,
    nodes, affineMaxErr, widthMaxErr, affineWorstTitle, widthWorstTitle, selScale102,
    inBoundsCount, nOutside, maxLeftClip, rightGap: Number.isFinite(rightmost) ? cr.right - rightmost : 0,
    activeCount, selectedCount,
    inspectorOpen: !!inspector,
    inspectorLabel: inspector ? (inspector.querySelector('h3')?.textContent ?? null) : null,
    drawerOpen: !!drawer,
    scrollY: window.scrollY,
    scrollable: se.scrollHeight > window.innerHeight + 1,
  };
};

const sigOf = (s: Snap): string =>
  JSON.stringify([
    r2(s.pan[0]), r2(s.pan[1]), Math.round(s.zoom * 10000) / 10000,
    s.nodes.length, s.activeCount, s.selectedCount,
    s.nodes.reduce((acc, n) => acc + n.title.length, 0),
    s.nodes.reduce((acc, n) => acc + (n.cls.length % 7), 0),
    r2(s.affineMaxErr), s.inBoundsCount,
  ]);

const settle = async (tag: string): Promise<Snap> => {
  let prev = '';
  let snap = await page.evaluate(readSnap);
  for (let i = 0; i < 22; i++) {
    const sig = sigOf(snap);
    if (sig === prev) return snap;
    prev = sig;
    await sleep(170);
    snap = await page.evaluate(readSnap);
  }
  (report.warnings as string[]).push(`settle timeout at ${tag}`);
  return snap;
};

const key = async (tag: string): Promise<Snap> => {
  await sleep(140);
  const s = await settle(tag);
  (report.steps as Record<string, unknown>)[tag] = {
    zoom: Math.round(s.zoom * 10000) / 10000,
    pan: [r2(s.pan[0]), r2(s.pan[1])],
    zoomReadout: s.zoomReadout,
    nodes: s.nodes.length,
    active: s.activeCount,
    selected: s.selectedCount,
    affineMaxErr: r2(s.affineMaxErr),
    widthMaxErr: r2(s.widthMaxErr),
    inBounds: s.inBoundsCount,
    inspector: s.inspectorOpen ? (s.inspectorLabel ?? '').slice(0, 40) : null,
    drawer: s.drawerOpen,
    scrollY: s.scrollY,
    scrollable: s.scrollable,
  };
  return s;
};

const localInvariance = (a: Snap, b: Snap): number => {
  if (a.nodes.length !== b.nodes.length) return 1e9;
  let mx = 0;
  for (let i = 0; i < a.nodes.length; i++) {
    mx = Math.max(mx, Math.abs(a.nodes[i].left - b.nodes[i].left), Math.abs(a.nodes[i].top - b.nodes[i].top));
  }
  return mx;
};
const titlesEqual = (a: Snap, b: Snap): boolean =>
  a.nodes.length === b.nodes.length && a.nodes.every((n, i) => n.title === b.nodes[i].title);
// مجموعهٔ مسیرِ فعال = گره‌های border-border-accent ∪ گرهِ گزیده (scale-102 border-accent-blue
// جای border-border-accent را می‌گیرد؛ پس اجتماع مقایسه می‌شود، نه شمارشِ خام).
const pathTitles = (s: Snap): string[] =>
  Array.from(
    new Set(
      s.nodes
        .filter((n) => n.cls.includes('border-border-accent') || /\bring-2\b/.test(n.cls))
        .map((n) => n.title),
    ),
  ).sort();

const clickBtnByTitlePrefix = async (prefix: string): Promise<boolean> =>
  page.evaluate((p) => {
    const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
    if (!canvas) return false;
    const btn = Array.from(canvas.querySelectorAll('button[title]')).find((b) =>
      (b.getAttribute('title') ?? '').startsWith(p),
    ) as HTMLElement | undefined;
    if (!btn) return false;
    btn.click();
    return true;
  }, prefix);

const drag = async (x1: number, y1: number, dx: number, dy: number, steps = 5) => {
  await page.mouse.move(x1, y1);
  await sleep(40);
  await page.mouse.down();
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(x1 + (dx * i) / steps, y1 + (dy * i) / steps);
    await sleep(16);
  }
  await page.mouse.up();
};

// ── فاز ۰: رفتن به صفحه و انتظارِ سکونِ داده ─────────────────────────────────
const origin = new URL(BASE).origin;
await page.goto(`${origin}/#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="obsidian-strategy-canvas"] .nodes-layer', { timeout: WAIT });
const s0 = await key('mount');
ck('canvas_found', s0.ok, { nodes: s0.nodes.length });
await shot('camera_00_mount');

// ۱. فرمولِ fitView در مانت + خوانشِ ٪ + affine
const fitScale = Math.min(Math.max(Math.min((s0.cw - 80) / s0.boundsW, (s0.ch - 80) / s0.boundsH), 0.45), 1.2);
ck('fit_formula_mount', near(s0.zoom, fitScale, 1e-6), {
  zoom: s0.zoom, expected: fitScale, cw: s0.cw, ch: s0.ch, boundsW: s0.boundsW, boundsH: s0.boundsH,
  clamped: fitScale === 0.45 || fitScale === 1.2,
});
ck('zoom_readout_match', s0.zoomReadout === Math.round(s0.zoom * 100), {
  readout: s0.zoomReadout, round: Math.round(s0.zoom * 100),
});
ck('affine_ok_mount', s0.affineMaxErr < 0.75 && s0.widthMaxErr < 0.75, {
  affineMaxErr: r2(s0.affineMaxErr), affineWorst: s0.affineWorstTitle,
  widthMaxErr: r2(s0.widthMaxErr), widthWorst: s0.widthWorstTitle,
});
const sel = s0.selScale102;
ck('selected_scale102_geometry', !!sel && near(sel.ratio, 1.02, 0.005) && sel.wErr < 1.5 && Math.abs(sel.shiftGraph + 0.01 * sel.w) < 2.0, sel
  ? { ratio: Math.round(sel.ratio * 10000) / 10000, wErr: r2(sel.wErr), shiftGraph: r2(sel.shiftGraph), w: sel.w, title: sel.title }
  : null);
ck('sensor_visible_nodes_mount', s0.inBoundsCount >= 20, {
  inBounds: s0.inBoundsCount, nodes: s0.nodes.length,
  note: 'سنسورِ درقاب چشم دارد: باید بخشِ بزرگی از گره‌ها را ببیند',
});
ck('inspector_open_at_mount', s0.inspectorOpen, { label: s0.inspectorLabel });
ck('no_scroll_at_viewportA', !s0.scrollable, { scrollable: s0.scrollable, scrollY: s0.scrollY });

// ۲. درگِ pan — دلتای دقیق + نایکنواییِ مختصاتِ گرافی
const p0 = { x: s0.canvasRect.x + 220, y: s0.canvasRect.y + 170 };
await drag(p0.x, p0.y, 160, 96);
const s1 = await key('drag');
ck('drag_pan_exact', near(s1.pan[0] - s0.pan[0], 160, 0.05) && near(s1.pan[1] - s0.pan[1], 96, 0.05), {
  delta: [r2(s1.pan[0] - s0.pan[0]), r2(s1.pan[1] - s0.pan[1])], expected: [160, 96],
});
ck('drag_zoom_unchanged', near(s1.zoom, s0.zoom, 1e-9), { zoom: s1.zoom });
ck('drag_graphspace_invariant', localInvariance(s0, s1) < 0.01, { maxDelta: localInvariance(s0, s1) });
ck('drag_affine_ok', s1.affineMaxErr < 0.75, { affineMaxErr: r2(s1.affineMaxErr), worst: s1.affineWorstTitle });
ck('drag_titles_identical', titlesEqual(s0, s1));
await shot('camera_01_drag');

// ۳. دکمه‌های zoom
await clickBtnByTitlePrefix('بزرگ');
const s2 = await key('zoomInBtn');
ck('zoomin_btn_ratio', near(s2.zoom, Math.min(s1.zoom * 1.15, 2.5), 2e-4), { zoom: s2.zoom, from: s1.zoom });
ck('zoomin_pan_hold', near(s2.pan[0], s1.pan[0], 0.01) && near(s2.pan[1], s1.pan[1], 0.01), { pan: s2.pan });
await clickBtnByTitlePrefix('کوچک');
const s3 = await key('zoomOutBtn');
ck('zoomout_btn_ratio', near(s3.zoom, Math.max(s2.zoom * 0.85, 0.35), 2e-4), { zoom: s3.zoom, from: s2.zoom });
ck('zoomBtns_affine_ok', s2.affineMaxErr < 0.75 && s3.affineMaxErr < 0.75, {
  in: r2(s2.affineMaxErr), inWorst: s2.affineWorstTitle, out: r2(s3.affineMaxErr), outWorst: s3.affineWorstTitle,
});
await shot('camera_02_buttons');

// ۴. wheel روی نقطهٔ کرسر — anchor ثابت
const cpt = { x: s3.canvasRect.x + s3.canvasRect.w / 2, y: s3.canvasRect.y + s3.canvasRect.h / 2 };
// عکسِ نقشهٔ screen = nlRect + zoom × local: مختصاتِ گرافیِ نقطهٔ روی‌صفحه
const gUnder = (s: Snap, pt: { x: number; y: number }) => [
  (pt.x - s.base[0]) / s.zoom,
  (pt.y - s.base[1]) / s.zoom,
];
const g3 = gUnder(s3, cpt);
await page.mouse.move(cpt.x, cpt.y);
await sleep(60);
await page.mouse.wheel(0, -120);
const s4 = await key('wheelIn');
const g4 = gUnder(s4, cpt);
const ratioIn = s4.zoom / s3.zoom;
const kIn = [1, 2, 3, 4].find((k) => Math.abs(ratioIn - Math.pow(1.1, k)) < 1e-4) ?? null;
ck('wheel_in_factor', kIn !== null, { ratio: ratioIn, k: kIn });
ck('wheel_in_anchor', Math.hypot(g4[0] - g3[0], g4[1] - g3[1]) < 1.0, {
  gBefore: [r2(g3[0]), r2(g3[1])], gAfter: [r2(g4[0]), r2(g4[1])],
  dist: r2(Math.hypot(g4[0] - g3[0], g4[1] - g3[1])),
});
await shot('camera_03_wheel_in');
await page.mouse.wheel(0, 120);
const s5 = await key('wheelOut');
const g5 = gUnder(s5, cpt);
const ratioOut = s5.zoom / s4.zoom;
const kOut = [1, 2, 3, 4].find((k) => Math.abs(ratioOut - Math.pow(0.9, k)) < 1e-4) ?? null;
ck('wheel_out_factor', kOut !== null, { ratio: ratioOut, k: kOut });
ck('wheel_out_anchor', Math.hypot(g5[0] - g4[0], g5[1] - g4[1]) < 1.0, {
  dist: r2(Math.hypot(g5[0] - g4[0], g5[1] - g4[1])),
});
await shot('camera_04_wheel_out');

// ۵. کنترلِ مثبت: درگِ بلندِ ۷۰۰ — سنسورِ حرکت زنده؟
const p1 = { x: s5.canvasRect.x + 150, y: s5.canvasRect.y + 220 };
await drag(p1.x, p1.y, 700, 0, 6);
const s6 = await key('longDrag');
ck('control_longdrag_exact', near(s6.pan[0] - s5.pan[0], 700, 0.05), { delta: r2(s6.pan[0] - s5.pan[0]) });
const shift = s6.nodes.map((n, i) => n.rect.x - s5.nodes[i].rect.x);
const shiftOk = shift.length > 0 && shift.every((v) => near(v, 700, 0.1));
ck('control_node_screen_shift', shiftOk, { min: r2(Math.min(...shift)), max: r2(Math.max(...shift)) });
await shot('camera_05_longdrag');

// ۶a. «گستره» = بازگشتِ دقیق به دوربینِ مانت
await clickBtnByTitlePrefix('تنظیم');
const s7 = await key('fitReset');
ck('fit_reset_to_mount_exact', near(s7.zoom, s0.zoom, 1e-9) && near(s7.pan[0], s0.pan[0], 0.02) && near(s7.pan[1], s0.pan[1], 0.02), {
  mount: [s0.zoom, r2(s0.pan[0]), r2(s0.pan[1])], fit: [s7.zoom, r2(s7.pan[0]), r2(s7.pan[1])],
});
const clipOf = (s: Snap) => ({ inBounds: s.inBoundsCount, nOutside: s.nOutside, maxLeftClip: r2(s.maxLeftClip), rightGap: r2(s.rightGap) });
const c7 = clipOf(s7);
const c0 = clipOf(s0);
ck('fit_reset_reproduces_mount_framing', c7.inBounds === c0.inBounds && c7.nOutside === c0.nOutside && near(c7.maxLeftClip, c0.maxLeftClip, 0.5) && near(c7.rightGap, c0.rightGap, 0.5), {
  mount: c0, fitReset: c7,
});
finding('fit_view_offcenter_left_clip', {
  mount: c0,
  note: 'fitView مبدأِ nodes-layer را صفر می‌گیرد ولی لایه در RTL ~۴۰۰px به چپ سرریز می‌کند (clientW−layerW)؛ نتیجه: کادرِ fit به‌چپ آفست می‌شود — چند گرهِ چپ‌ لبه از قاب بیرون می‌مانند و سمتِ راست نوارِ خالی می‌ماند. عمداً اصلاح نشده: داوریِ بصریِ مالک لازم است.',
});
await shot('camera_06_fit_reset');

// ۶b. «٪» = zoom ۱ + مرکزِ bounds (مشتق از مانت)
const centerX = (s0.cw / 2 - s0.pan[0]) / s0.zoom;
const centerY = (s0.ch / 2 - s0.pan[1]) / s0.zoom;
await drag(200, 200, -240, -140, 4);
await clickBtnByTitlePrefix('بزرگ');
await clickBtnByTitlePrefix('بزرگ');
await clickBtnByTitlePrefix('بزرگ');
const sPre = await key('pctResetPre');
await clickBtnByTitlePrefix('بازنشانی');
const s8 = await key('pctReset');
ck('pct_reset_zoom_one', near(s8.zoom, 1, 1e-9), { zoom: s8.zoom, from: sPre.zoom });
ck('pct_reset_centered', near(s8.pan[0], s8.cw / 2 - centerX, 0.51) && near(s8.pan[1], s8.ch / 2 - centerY, 0.51), {
  pan: [r2(s8.pan[0]), r2(s8.pan[1])],
  expected: [r2(s8.cw / 2 - centerX), r2(s8.ch / 2 - centerY)],
  mountVsReset: { fitZoom: s0.zoom, resetZoom: s8.zoom },
});
await shot('camera_07_pct_reset');

// ۷. تغییرِ viewport و بازگشت — state دوربین باید دوام بیاورد
await page.setViewportSize(VB);
await sleep(250);
const s9 = await key('viewportB');
ck('viewportB_transform_survives', near(s9.zoom, s8.zoom, 0.02) && near(s9.pan[0], s8.pan[0], 0.02) && near(s9.pan[1], s8.pan[1], 0.02), {
  before: [s8.zoom, r2(s8.pan[0]), r2(s8.pan[1])], atB: [s9.zoom, r2(s9.pan[0]), r2(s9.pan[1])],
});
ck('viewportB_affine_ok', s9.affineMaxErr < 0.75, { affineMaxErr: r2(s9.affineMaxErr), worst: s9.affineWorstTitle });
ck('viewportB_nodes_identical', titlesEqual(s8, s9), { nodes: s9.nodes.length });
await shot('camera_08_vp_b');

// ۷b. سنجشِ رفتاریِ wheel در viewport کوچکِ اسکرول‌دار (شواهدِ یافتهٔ محتملِ passive)
let preReturnSnap: Snap = s9;
if (s9.scrollable) {
  await page.evaluate(() => {
    const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
    if (canvas) canvas.scrollIntoView({ block: 'center' });
  });
  await sleep(250);
  const bPrev = await settle('vpBWheelPre');
  const bc = { x: bPrev.canvasRect.x + bPrev.canvasRect.w / 2, y: bPrev.canvasRect.y + bPrev.canvasRect.h / 2 };
  await page.mouse.move(bc.x, bc.y);
  await sleep(60);
  await page.mouse.wheel(0, -240);
  await sleep(200);
  const bPost = await settle('vpBWheelPost');
  preReturnSnap = bPost;
  finding('wheel_small_viewport_behavior', {
    scrollBefore: bPrev.scrollY, scrollAfter: bPost.scrollY,
    pageScrolled: bPost.scrollY !== bPrev.scrollY,
    zoomBefore: bPrev.zoom, zoomAfter: bPost.zoom,
    zoomChanged: bPost.zoom !== bPrev.zoom,
    note: 'اگر صفحه اسکرول شده و zoom هم عوض شده => preventDefault در شنوندهٔ wheel اثر ندارد (محتملاً passive)',
  });
}

await page.setViewportSize(VA);
await sleep(250);
const s10 = await key('viewportBack');
ck('viewportBack_transform_survives', near(s10.zoom, preReturnSnap.zoom, 0.02) && near(s10.pan[0], preReturnSnap.pan[0], 0.02) && near(s10.pan[1], preReturnSnap.pan[1], 0.02), {
  before: [preReturnSnap.zoom, r2(preReturnSnap.pan[0]), r2(preReturnSnap.pan[1])],
  back: [s10.zoom, r2(s10.pan[0]), r2(s10.pan[1])],
  comparedAgainst: preReturnSnap === s9 ? 'viewportB' : 'viewportB+wheel',
});
ck('viewportBack_affine_ok', s10.affineMaxErr < 0.75, { affineMaxErr: r2(s10.affineMaxErr), worst: s10.affineWorstTitle });
await shot('camera_09_vp_back');

// ۸. inspector: بستنِ ✕ ← کلیکِ گره ← wheel در حینِ باز بودن ← یافتهٔ لبه‌ای
const closed = await page.evaluate(() => {
  const insp = document.querySelector('[data-testid="strategy-node-inspector"]');
  if (!insp) return 'no-inspector';
  const btn = Array.from(insp.querySelectorAll('button')).find((b) => (b.getAttribute('aria-label') ?? '') === 'بستن');
  if (!btn) return 'no-close';
  (btn as HTMLElement).click();
  return 'clicked';
});
await sleep(200);
const s11 = await key('inspectorClosed');
ck('inspector_close_ok', closed === 'clicked' && !s11.inspectorOpen, { action: closed, open: s11.inspectorOpen });
await shot('camera_10_inspector_closed');

// انتخابِ گره: نزدیک‌ترین مرکز به مرکزِ بوم، در محدودهٔ امن (دور از نوارِ ابزار و inspector)
const pick = await page.evaluate(() => {
  const canvas = document.querySelector('[data-testid="obsidian-strategy-canvas"]') as HTMLElement;
  const tl = Array.from(canvas.children).find(
    (el) => (el as HTMLElement).style && (el as HTMLElement).style.transform.includes('translate'),
  ) as HTMLElement;
  const cr = canvas.getBoundingClientRect();
  const els = Array.from(tl.querySelectorAll('.nodes-layer > div[role="button"]')) as HTMLElement[];
  const cx = cr.left + cr.width / 2;
  const cy = cr.top + cr.height / 2;
  let best: { i: number; x: number; y: number; title: string; d: number } | null = null;
  els.forEach((el, i) => {
    const r = el.getBoundingClientRect();
    const mx = r.left + r.width / 2;
    const my = r.top + r.height / 2;
    const safe =
      mx >= cr.left + 40 && mx <= cr.right - 400 && my >= cr.top + 90 && my <= cr.bottom - 120;
    if (!safe) return;
    const d = Math.hypot(mx - cx, my - cy);
    if (!best || d < best.d) best = { i, x: mx, y: my, title: el.querySelector('span[title]')?.getAttribute('title') ?? '', d };
  });
  return best;
});
ck('clickable_node_found', !!pick, pick ? { index: pick.i, title: pick.title } : null);
if (pick) {
  await page.mouse.click(pick.x, pick.y);
  await sleep(220);
  const s12 = await key('nodeClick');
  const labelNorm = (x: string | null) => (x ?? '').replace(/\s+/g, ' ').trim();
  ck('node_click_opens_inspector', s12.inspectorOpen && labelNorm(s12.inspectorLabel) === labelNorm(pick.title), {
    inspector: s12.inspectorOpen, label: s12.inspectorLabel, nodeTitle: pick.title,
  });
  ck('node_click_no_camera_jump', near(s12.zoom, s11.zoom, 0.02) && near(s12.pan[0], s11.pan[0], 0.02) && near(s12.pan[1], s11.pan[1], 0.02), {
    before: [s11.zoom, r2(s11.pan[0])], after: [s12.zoom, r2(s12.pan[0])],
  });
  await shot('camera_11_inspector_open');

  await page.mouse.move(s12.canvasRect.x + s12.canvasRect.w / 2, s12.canvasRect.y + s12.canvasRect.h / 2);
  await sleep(60);
  await page.mouse.wheel(0, -120);
  const s13 = await key('inspectorDuringWheel');
  ck('inspector_survives_wheel', s13.inspectorOpen && s13.zoom !== s12.zoom, {
    open: s13.inspectorOpen, zoomFrom: s12.zoom, zoomTo: s13.zoom,
  });
  await shot('camera_12_inspector_wheel');

  // یافتهٔ لبه‌ای: رانشِ کوچک از روی بدنهٔ inspector — آیا بوم pan می‌کند؟
  const ip = await page.evaluate(() => {
    const insp = document.querySelector('[data-testid="strategy-node-inspector"]') as HTMLElement | null;
    if (!insp) return null;
    const el =
      (insp.querySelector('div.text-xs p') as HTMLElement | null) ??
      (insp.querySelector('p') as HTMLElement | null) ??
      insp;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  });
  if (ip) {
    await drag(ip.x, ip.y, 60, 0, 4);
    const s13b = await settle('inspectorDrag');
    finding('drag_on_inspector_body_pans_canvas', {
      panDeltaX: r2(s13b.pan[0] - s13.pan[0]),
      panDeltaY: r2(s13b.pan[1] - s13.pan[1]),
      note: 'mousedown روی inspector به کانتینر bubble می‌کند؛ انتظار از کد: pan با کشیدن روی بدنهٔ inspector هم حرکت می‌کند',
    });
  }
  const closed2 = await page.evaluate(() => {
    const insp = document.querySelector('[data-testid="strategy-node-inspector"]');
    if (!insp) return false;
    const btn = Array.from(insp.querySelectorAll('button')).find((b) => (b.getAttribute('aria-label') ?? '') === 'بستن') as HTMLElement | undefined;
    if (!btn) return false;
    btn.click();
    return true;
  });
  await sleep(180);
  const s14 = await settle('inspectorClosedAfter');
  ck('inspector_reclose_ok', closed2 && !s14.inspectorOpen, { open: s14.inspectorOpen });
}

// ۹. کشوی کاندیداها: باز ← درگ روی نوارِ آزادِ بوم ← بسته
const opened = await page.evaluate(() => {
  const btn = Array.from(document.querySelectorAll('button[aria-label]')).find((b) =>
    (b.getAttribute('aria-label') ?? '').includes('تابلو'),
  ) as HTMLElement | undefined;
  if (!btn) return false;
  btn.click();
  return true;
});
await sleep(260);
const s15 = await key('drawerOpen');
ck('drawer_open_ok', opened && s15.drawerOpen, { opened, drawer: s15.drawerOpen });
await shot('camera_13_drawer_open');
// کشو در RTL سمتِ چپ را می‌پوشاند (end-0)؛ نوارِ آزادِ درگ سمتِ راستِ قاب است
const strip = { x: s15.canvasRect.x + s15.canvasRect.w - 130, y: s15.canvasRect.y + 320 };
await drag(strip.x, strip.y, 120, 0, 4);
const s16 = await key('drawerPan');
ck('drawer_pan_exact', near(s16.pan[0] - s15.pan[0], 120, 0.05) && near(s16.pan[1], s15.pan[1], 0.05), {
  delta: [r2(s16.pan[0] - s15.pan[0]), r2(s16.pan[1] - s15.pan[1])],
  drawerOpenDuringPan: s16.drawerOpen,
});
await shot('camera_14_drawer_pan');
const drawerClosed = await page.evaluate(() => {
  const drawer = document.querySelector('[data-testid="stage-candidate-drawer"]');
  if (!drawer) return false;
  const btn = Array.from(drawer.querySelectorAll('button')).find((b) =>
    (b.getAttribute('aria-label') ?? '').includes('بستن'),
  ) as HTMLElement | undefined;
  if (!btn) return false;
  btn.click();
  return true;
});
await sleep(200);
const s17 = await key('drawerClosed');
ck('drawer_close_ok', drawerClosed && !s17.drawerOpen, { closed: drawerClosed, drawer: s17.drawerOpen });

// ۱۰. یکپارچگیِ پایانی
const sEnd = await key('final');
ck('final_titles_identical', titlesEqual(s0, sEnd), { nodes: sEnd.nodes.length });
ck('final_activepath_identical', JSON.stringify(pathTitles(s0)) === JSON.stringify(pathTitles(sEnd)), {
  mountCount: pathTitles(s0).length, endCount: pathTitles(sEnd).length,
  mount: pathTitles(s0), end: pathTitles(sEnd),
});
ck('final_node_count_stable', s0.nodes.length === sEnd.nodes.length, { mount: s0.nodes.length, end: sEnd.nodes.length });
await shot('camera_15_final');

if (passiveWheelWarnings > 0) {
  finding('wheel_preventdefault_ineffective', {
    consoleWarnings: passiveWheelWarnings,
    note: 'preventDefault در شنوندهٔ wheel بی‌اثر است (شنونده روی ریشهٔ React passive نشسته)؛ شاهدِ رفتاری: wheel در viewport کوچک هم‌زمان صفحه را اسکرول و بوم را zoom کرد.',
  });
}
report.passiveWheelWarnings = passiveWheelWarnings;
ck('no_console_errors', (report.errors as string[]).length === 0, report.errors);
ck('no_http_errors', (report.http as string[]).length === 0, report.http);

const checks = report.checks as { ok: boolean; name: string }[];
const failed = checks.filter((c) => !c.ok).map((c) => c.name);
report.failed = failed;
report.verdict = failed.length ? 'FAIL' : 'PASS';
report.counts = { total: checks.length, passed: checks.length - failed.length };

writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(`verdict=${report.verdict} ${report.counts ? JSON.stringify(report.counts) : ''}`);
if (failed.length) console.log(`failed: ${failed.join(', ')}`);
console.log(`findings: ${JSON.stringify((report.findings as unknown[]).map((f) => (f as { id: string }).id))}`);
console.log(`out=${OUT}`);

await browser.close();
