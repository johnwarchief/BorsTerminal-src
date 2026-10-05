// tools/ffc_marker_pixel_probe.mts — اثباتِ پیکسلیِ نشانگرِ رویداد درِ موتورِ دوم (FFC)
//
// چهار چیز، وگرنه «صفرِ پیکسل» هم می‌تواند یعنی نشانگر نیست و یعنی سنجش کر است:
//   ۱) تفاوتِ ستون‌به‌ستونِ روشن منهای خاموش (رنگِ کندلِ نزولیِ این بازار خودِ
//      فیروزه‌ای است؛ شمارشِ مطلقِ رنگ، جوهرِ نشانگر را از شمع جدا نمی‌کند)
//   ۲) نشستن رویِ کندلِ درست: برازشِ x = a + b·(شمارۀِ کندل) رویِ خوشه‌هایِ تفاضلی؛
//      جابه‌جایی رویِ کندلِ دیگر باقی‌مانده‌اندازه یک کندل (≈ b پیکسل) می‌سازد
//   ۳) درگِ افقی: خوشه‌ها باید بهاندازۀِ درگ جابه‌جا شوند (به کندل چسبیده‌اند،
//      نه بهِ صفحه) و شمارشان باید ثابت بماند
//   ۴) تغییرِ اندازه: خوشه‌ها باید درِ ریسایز هم همان‌جا بمانند (بی‌محو)
//
// رنگ‌ها از lib/corpEvents.ts اند: بنفش = تعدیلِ قیمت، فیروزه‌ای = تغییرِ سهام.
// نیازمندِ بیلدِ تازه (dist) و بک‌اند زنده:
//   JEV_BROWSER_DIR=… JEV_CHROME=… MSYS_NO_PATHCONV=1 node --experimental-strip-types \
//     tools/ffc_marker_pixel_probe.mts [نماد]
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(PKG + '/node_modules/playwright/index.mjs').href);

const BASE = process.env.PROBE_BASE || 'http://127.0.0.1:8003';
const SYM = process.argv[2] || 'فارس';
const VW = Number(process.env.PROBE_W || 1600);
const VH = Number(process.env.PROBE_H || 900);
const RW = Number(process.env.PROBE_RW || 1366);
const RH = Number(process.env.PROBE_RH || 768);
const KEY = 'fts.chart.settings.v1';
const WINDOW = 180;   // visibleBars درِ FtsEngineChart
const DRAG = 220;     // گامِ کنترلِ درگ

/** ستون‌هایِ جوهرِ بنفش/فیروزه‌ای رویِ بومِ موتورِ دوم (کامپوزیتِ لایه‌ها) */
const SHOT = () => {
  const host = document.querySelector('[data-testid="ffc-chart-host"]');
  if (!host) return { error: 'no ffc host' };
  const cs = Array.from(host.querySelectorAll('canvas'));
  if (!cs.length) return { error: 'no canvas in ffc host' };
  let banner: string | null = null;
  host.parentElement?.parentElement?.querySelectorAll('p,div').forEach((e) => {
    const t = (e.textContent || '');
    if (/WebGL|موتور|بالا‌نیامد|خطا/.test(t) && t.length < 240 && !banner) {
      banner = t.replace(/\s+/g, ' ').trim();
    }
  });
  const rects = cs.map((c) => c.getBoundingClientRect());
  const x0 = Math.min(...rects.map((r) => r.left));
  const y0 = Math.min(...rects.map((r) => r.top));
  const x1 = Math.max(...rects.map((r) => r.right));
  const y1 = Math.max(...rects.map((r) => r.bottom));
  const W = Math.round(x1 - x0);
  const H = Math.round(y1 - y0);
  const off = document.createElement('canvas');
  off.width = W; off.height = H;
  const g = off.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
  for (const c of cs) g.drawImage(c, 0, 0, W, H);
  const { data } = g.getImageData(0, 0, W, H);
  const colP = new Array(W).fill(0);
  const colT = new Array(W).fill(0);
  const rowP = new Array(H).fill(0);
  const rowT = new Array(H).fill(0);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (data[i + 3] < 40) continue;
      const r = data[i], gg = data[i + 1], b = data[i + 2];
      // بنفشِ #a855f7 و فیروزه‌ایِ #2dd4bf (lib/corpEvents) — آستانه‌ها فضایِ
      // رنگ‌اند و درِ تفاضلِ روشن/خاموش لازم نیست بی‌نقص باشند
      if (r > 110 && r < 235 && gg < 135 && b > 175) { colP[x]++; rowP[y]++; }
      else if (r < 100 && gg > 160 && b > 145 && b < 225) { colT[x]++; rowT[y]++; }
    }
  }
  const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
  return { W, H, banner, purple: sum(colP), teal: sum(colT),
    colP: colP.join(','), colT: colT.join(','),
    rowP: rowP.join(','), rowT: rowT.join(',') };
};

/** خوشه از ستون‌هایِ جوهرِ خالص (تفاضلِ روشن منهای خاموش).
 *  minInk لازم است: افزودنِ نشانگر، دامنه‌یِ خودکارِ محورِ قیمت را کمی جابه‌جا
 *  می‌کند و هر شمع یکِ دو پیکسل تفاوت می‌دهد؛ متنِ نشانگر ده پیکسلِ بلند دارد. */
function clusters(colStr: string, gap = 18, minInk = 5) {
  const col = colStr.split(',').map(Number);
  const runs: Array<{ xs: number[]; ws: number[] }> = [];
  let xs: number[] = [], ws: number[] = [], last = -999;
  for (let x = 0; x < col.length; x++) {
    if (col[x] < minInk) continue;
    if (xs.length && x - last > gap) { runs.push({ xs, ws }); xs = []; ws = []; }
    xs.push(x); ws.push(col[x]); last = x;
  }
  if (xs.length) runs.push({ xs, ws });
  return runs.map(({ xs, ws }) => {
    const w = ws.reduce((a, b) => a + b, 0);
    const center = Math.round(xs.reduce((a, x, i) => a + x * ws[i], 0) / w);
    return [xs[0], xs[xs.length - 1], center, w, xs.length];
  });
}
const diff = (a: string, b: string) => {
  const x = a.split(',').map(Number), y = b.split(',').map(Number);
  return x.map((v, i) => Math.max(0, v - (y[i] || 0))).join(',');
};

function regress(pts: Array<[number, number]>) {
  const n = pts.length;
  if (n < 3) return null;
  const sx = pts.reduce((a, p) => a + p[0], 0);
  const sy = pts.reduce((a, p) => a + p[1], 0);
  const sxx = pts.reduce((a, p) => a + p[0] * p[0], 0);
  const sxy = pts.reduce((a, p) => a + p[0] * p[1], 0);
  const den = n * sxx - sx * sx;
  if (!den) return null;
  const b = (n * sxy - sx * sy) / den;
  const a2 = (sy - b * sx) / n;
  const res = pts.map((p) => p[1] - (a2 + b * p[0]));
  const mean = sy / n;
  const ssTot = pts.reduce((acc, p) => acc + (p[1] - mean) ** 2, 0);
  const ssRes = res.reduce((acc, r) => acc + r * r, 0);
  return { pxPerBar: +b.toFixed(3), intercept: +a2.toFixed(1),
    maxAbsPx: +Math.max(...res.map(Math.abs)).toFixed(1),
    rmsPx: +Math.sqrt(ssRes / n).toFixed(1),
    r2: ssTot ? +(1 - ssRes / ssTot).toFixed(4) : null };
}

async function run(isOff: boolean) {
  const browser = await chromium.launch({
    headless: true, executablePath: process.env.JEV_CHROME || undefined,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  const ctx = await browser.newContext({ viewport: { width: VW, height: VH } });
  await ctx.addInitScript(([key, flag]: any) => {
    try {
      sessionStorage.setItem('bors_auth_session', 'true');
      const j = JSON.parse(localStorage.getItem(key) || '{}');
      j.view = Object.assign({}, j.view || {}, { showCorporateActions: !flag });
      localStorage.setItem(key, JSON.stringify(j));
    } catch { /* noop */ }
  }, [KEY, isOff]);
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('pageerror', (e: Error) => errs.push(String(e.message).slice(0, 160)));
  await page.goto(`${BASE}/#/technical/${encodeURIComponent(SYM)}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(14000);
  let switched = false;
  try {
    await page.getByText('موتور دوم', { exact: false }).first().click({ timeout: 7000 });
    switched = true;
  } catch { /* درِ گزارش */ }
  await page.waitForTimeout(6000);
  const before = await page.evaluate(SHOT) as any;
  await page.locator('[data-testid="ffc-chart-host"]').screenshot({
    path: `_audit/ffc_marker_${isOff ? 'off' : 'on'}_${VW}.png`,
  });

  const box = await page.locator('[data-testid="ffc-chart-host"]').boundingBox();
  let after: any = null, zoomed: any = null;
  if (box) {
    const cx = box.x + box.width * 0.6, cy = box.y + box.height * 0.5;
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    for (let i = 1; i <= 11; i++) await page.mouse.move(cx + (DRAG * i) / 11, cy, { steps: 1 });
    await page.mouse.up();
    await page.waitForTimeout(2500);
    after = await page.evaluate(SHOT) as any;
    // زومِ درون‌محور رویِ انتهایِ نمودار: اگر نشانگر به کندلِ خودش چسبیده باشد،
    // نشانگرِ ۶ کندل مانده به انتها باید به فاصلۀِ ۶×پهنایِ کندل از لبه بایستد
    for (let i = 0; i < 10; i++) {
      await page.mouse.move(cx + DRAG, cy);
      await page.mouse.wheel(0, -260);
      await page.waitForTimeout(200);
    }
    await page.waitForTimeout(2500);
    zoomed = await page.evaluate(SHOT) as any;
    await page.locator('[data-testid="ffc-chart-host"]').screenshot({
      path: `_audit/ffc_marker_${isOff ? 'off' : 'on'}_zoom.png`,
    });
  }

  await page.setViewportSize({ width: RW, height: RH });
  await page.waitForTimeout(3000);
  const resized = await page.evaluate(SHOT) as any;

  let api: any = null;
  if (!isOff) {
    api = await page.evaluate(async (s: string) => {
      const r = await fetch(`/api/chart/${encodeURIComponent(s)}`);
      const j: any = await r.json();
      return { times: (j.candles ?? []).map((c: any) => String(c.time)),
        events: (j.corporateEvents ?? []).map((e: any) => ({ date: String(e.date ?? ''), type: String(e.type ?? '') })) };
    }, SYM);
  }
  await page.close(); await browser.close();
  return { switched, errs, before, after, resized, api };
}

const on = await run(false);
const off = await run(true);

// لنگرِ نشانگر همان قاعدۀِ barAt درِ lib/corpEvents: روزِ دقیق، وگرنه نخستین
// کندلِ پس از آن. /api/chart کندل‌ها را از تازه به کهنه می‌فرستد، پس صعودی مرتب.
const asc = (on.api?.times ?? []).map((t: string) => String(t).slice(0, 10)).sort();
const nBars = asc.length;
const anchorIdx = (d0: string) => {
  const d = String(d0).slice(0, 10);
  const exact = asc.indexOf(d);
  return exact >= 0 ? exact : asc.findIndex((t) => t >= d);
};
const evAll = (on.api?.events ?? []).map((e: any) => ({ ...e, idx: anchorIdx(e.date) }));
const inSeries = evAll.filter((e) => e.idx >= 0);
const inWindow = inSeries.filter((e) => e.idx >= nBars - WINDOW);
const idxBy = (t: RegExp) => inWindow.filter((e) => t.test(e.type)).map((e) => e.idx).sort((a, b) => a - b);

const pair = (colOn: string, colOff: string, idxs: number[]) => {
  const d = diff(colOn, colOff);
  // گامِ ۴۰ پیکسل: هر برچسبِ رویداد از چندِ خوشکِ متن ساخته می‌شود و رویدادها
  // از هم دورند؛ با این، خوشک‌ها به یک نشانگر می‌چسبند و نشانگرها جدا می‌مانند.
  const cl = clusters(d, 40);
  const k = Math.min(cl.length, idxs.length);
  const xs = cl.slice(cl.length - k).map((c) => c[2]);
  const ix = idxs.slice(idxs.length - k);
  const f = regress(ix.map((i, j) => [i, xs[j]] as [number, number]));
  // فاصلۀِ هر رویدادِ موردِ انتظار تا نزدیک‌ترین خوشکه: باقی‌ماندۀِ برازش را
  // رویداد‌به‌رویداد نشان می‌دهد (جایِ غلط = دست‌کم یکِ کندل خطا)
  const perEvent = f ? ix.map((i) => {
    const xp = f.intercept + f.pxPerBar * i;
    const near = cl.reduce((b, c) => (Math.abs(c[2] - xp) < Math.abs(b[2] - xp) ? c : b), cl[0]);
    return { barIndex: i, predictedX: Math.round(xp), clusterX: near[2], deltaPx: Math.round(near[2] - xp) };
  }) : null;
  return { clusters: cl, expected: idxs.length, paired: k, perEvent,
    fit: f };
};

const dP = diff(on.before.colP, off.before.colP);
const dT = diff(on.before.colT, off.before.colT);
const fitP = pair(on.before.colP, off.before.colP, idxBy(/priceAdjust/));
const fitT = pair(on.before.colT, off.before.colT, idxBy(/shareChange/));

// کنترلِ درگ: تفاضلِ پس از درگ هم باید خوشه بدهد؛ هر خوشه‌ای که پیش‌تر دیدیم
// باید DRAG پیکسل جابه‌جا شده باشد (چسبیده به کندل). تطبیق با نزدیک‌ترین همسایه،
// چون درگ ممکن است یک نشانگر را از نما بیرون یا داخل ببرد.
const panP = diff(on.after?.colP ?? '', off.after?.colP ?? '');
const panT = diff(on.after?.colT ?? '', off.after?.colT ?? '');
const beforeC = clusters(dP).concat(clusters(dT)).map((c) => c[2]).sort((a, b) => a - b);
const afterC = clusters(panP).concat(clusters(panT)).map((c) => c[2]).sort((a, b) => a - b);
const matched = beforeC.map((x) => {
  let best: number | null = null, bd = 1e9;
  for (const y of afterC) {
    const d2 = Math.abs(y - (x + DRAG));
    if (d2 < bd) { bd = d2; best = y; }
  }
  return { before: x, want: x + DRAG, after: best, offPx: best == null ? null : Math.round(bd) };
}).filter((m) => m.offPx != null && m.offPx <= 120);

const rzP = diff(on.resized?.colP ?? '', off.resized?.colP ?? '');
const rzT = diff(on.resized?.colT ?? '', off.resized?.colT ?? '');

const res = {
  symbol: SYM, viewport: `${VW}x${VH}`, resizedTo: `${RW}x${RH}`, base: BASE,
  dragPx: DRAG, window: WINDOW,
  switched: { on: on.switched, off: off.switched },
  bars: nBars, eventsTotal: evAll.length, eventsAnchoredToABar: inSeries.length,
  eventsInWindow: inWindow.length,
  windowEvents: inWindow.map((e) => ({ date: e.date, type: e.type, barIndex: e.idx })),
  rawCounts: {
    on: { purple: on.before.purple, teal: on.before.teal },
    off: { purple: off.before.purple, teal: off.before.teal },
  },
  diffInk: { purple: clusters(dP).reduce((a, c) => a + c[3], 0),
             teal: clusters(dT).reduce((a, c) => a + c[3], 0) },
  fitPriceAdjust: { clusters: fitP.clusters, expected: fitP.expected, paired: fitP.paired, fit: fitP.fit },
  fitShareChange: { clusters: fitT.clusters, expected: fitT.expected, paired: fitT.paired, fit: fitT.fit },
  priceAxisRows: { purple: clusters(on.before.rowP, 4).length, note: 'ردیف‌هایِ بنفشِ خاموش برایِ بازرسی' },
  pan: { dragPx: DRAG, beforeCenters: beforeC, afterCenters: afterC,
    matched, unmatched: beforeC.length - matched.length,
    afterDiffInk: clusters(panP).reduce((a, c) => a + c[3], 0) + clusters(panT).reduce((a, c) => a + c[3], 0) },
  resize: { purpleClusters: clusters(rzP), tealClusters: clusters(rzT),
    onW: on.resized?.W, offW: off.resized?.W },
  banners: { on: on.before.banner, off: off.before.banner },
  consoleErrors: on.errs.concat(off.errs).slice(0, 8),
};
writeFileSync(`_audit/p0_ffc_marker_${SYM}_${VW}x${VH}.json`, JSON.stringify(res, null, 1), 'utf8');
console.log(JSON.stringify({
  symbol: SYM, switched: res.switched, bars: nBars, eventsTotal: evAll.length,
  eventsInWindow: res.eventsInWindow, rawCounts: res.rawCounts, diffInk: res.diffInk,
  fitP: res.fitPriceAdjust, fitT: res.fitShareChange,
  pan: { before: beforeC, after: afterC, matched: res.pan.matched,
    unmatched: res.pan.unmatched, afterDiffInk: res.pan.afterDiffInk },
  resize: { purple: res.resize.purpleClusters, teal: res.resize.tealClusters },
  banner: res.banners.on, errs: res.consoleErrors,
}, null, 1));
