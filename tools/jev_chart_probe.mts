/**
 * tools/jev_chart_probe.mts — شاهدِ زندهٔ #166/#167/#168 روی چارتِ واقعی
 *
 * چرا این ابزار: آزمون‌های jsdom ثابت می‌کنند دکمه به استور می‌نویسد، ولی
 * چارتِ klinecharts روی canvas نقاشی می‌شود؛ «درگِ افقی مقیاسِ عمودی را تکان
 * نداد» و «متنِ گوشۀ چارت دیگر همیشه روی بوم نیست» را فقط با پیکسلِ واقعی می‌شود
 * اثبات کرد. پس همین‌جا برداشتِ صفحه‌نمایش انجام می‌شود، نه دیفِ DOM.
 *
 * روش: هر canvas روی هم‌منطقۀ panۀ کندل روی یک بومِ بی‌نام ترکیب می‌شود، بعد
 * «جوهِ رنگی» (تفاضلِ کانال‌ها > 40) شمرده می‌شود — یعنی بدنهٔ کندل و خطوطِ
 * رنگی، بی‌متنِ خاکستری و بی‌خطِ شبکه. سطرِ نخستین/آخرینِ پُرجو هر دو سمتِ
 * مقیاسِ عمودی است؛ اگر مقیاس بپرد، این دو عدد می‌پرند.
 * آستانۀ «حداقل ۳ پیکسل در سطر» خطِ عمودیِ کراس‌هیر را بی‌اثر می‌کند، وگرنه
 * هر سطری یک پیکسل می‌گرفت و آزمون همیشه سبز می‌شد.
 *
 * #168 را همین‌جا با دو عکسِ واقعی از گوشۀ چارت اثبات می‌کنیم
 * (probe168_idle.png / probe168_hover.png): کراس‌هیر و متنِ OHLC روی لایه‌ای
 * جدا از کندل‌ها نقاشی می‌شوند و در ترکیبِ canvas این پنل نیستند، پس شمارشِ
 * پیکسلِ canvas برای «متن هست یا نه» قابلِ اتکا نیست.
 *
 * کنترلِ مثبت: درگِ بلندِ افقی دید را به منطقۀ قیمتِ دیگری می‌برد و مقیاس باید
 * آزاد شود (longDrag.scaleRechosen). اگر آن هم صفر می‌ماند، «نگه‌داشتنِ» کوتاه
 * هیچ چیزی را ثابت نمی‌کرد.
 *
 *   JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types \
 *     tools/jev_chart_probe.mts --url http://127.0.0.1:8010/ --out _audit/jev_chart_probe.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const flag = (name: string): boolean => process.argv.includes(`--${name}`);

const BASE = arg('url', 'http://127.0.0.1:8010/');
const ROUTE = arg('route', '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF');
const OUT = arg('out', '_audit/jev_chart_probe.json');
const SHOTS = arg('shots', '_audit');
const WIDTH = Number.parseInt(arg('width', '1366'), 10);
const HEIGHT = Number.parseInt(arg('height', '900'), 10);
const WAIT_MS = Number.parseInt(arg('wait', '22000'), 10);

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) {
  const { ensureChromium } = await imp('src/browser-setup.ts');
  await ensureChromium();
}

const AUTH_INIT = () => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
};

/**
 * برداشتِ پیکسلی از panۀ کندل. skipTop/skipBottom/skipRight بر حسبِ پیکسلِ CSS:
 * برچسبِ محورِ زمان پایین و برچسبِ قیمتِ کراس‌هیر راست را حذف می‌کنند.
 */
const SIG = `(function(){
  const SKIP_BOTTOM = 46, SKIP_RIGHT = 74;
  const boxes = [...document.querySelectorAll('canvas')]
    .map((c) => ({ c, r: c.getBoundingClientRect() }))
    .filter((x) => x.r.width > 260 && x.r.height > 140);
  if (!boxes.length) return { err: 'no-canvas' };
  boxes.sort((a, b) => b.r.width * b.r.height - a.r.width * a.r.height);
  const main = boxes[0];
  const stack = boxes.filter(
    (x) => Math.abs(x.r.top - main.r.top) < 6 && Math.abs(x.r.left - main.r.left) < 6,
  );
  const W = Math.round(main.r.width), H = Math.round(main.r.height);
  const off = document.createElement('canvas');
  off.width = W; off.height = H;
  const o = off.getContext('2d', { willReadFrequently: true });
  if (!o) return { err: 'no-2d' };
  o.clearRect(0, 0, W, H);
  for (const s of stack) {
    const g = s.c.getContext('2d');
    if (!g) continue;
    try { o.drawImage(s.c, 0, 0, W, H); } catch { return { err: 'tainted' }; }
  }
  let data;
  try { data = o.getImageData(0, 0, W, H).data; } catch (e) { return { err: String(e).slice(0, 60) }; }
  const cols = W - SKIP_RIGHT;
  const rows = H - SKIP_BOTTOM;
  const rowCount = new Array(H).fill(0);
  const colCount = new Array(W).fill(0);
  let ink = 0;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const i = (y * W + x) * 4;
      const a = data[i + 3];
      if (a < 24) continue;
      const r = data[i], gg = data[i + 1], b = data[i + 2];
      const chroma = Math.max(r, gg, b) - Math.min(r, gg, b);
      if (chroma > 40) {
        rowCount[y]++; colCount[x]++; ink++;
      }
    }
  }
  const firstWhere = (arr, min) => { for (let i = 0; i < arr.length; i++) if (arr[i] >= min) return i; return -1; };
  const lastWhere = (arr, min) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] >= min) return i; return -1; };
  // سطرهایِ تمام‌عریض = خطِ افقیِ ثابت (تراز/مقاومتِ FTS). این‌ها نقشۀ قیمت→پیکسل
  // را مستقیم نشان می‌دهند: اگر مقیاس نگه داشته شود سرِجایشان می‌مانند، اگر
  // از نو چیده شود جابه‌جا می‌شوند. (برخلافِ سقف/کفِ کندل، که با دادۀ تازه عوض
  // می‌شود حتی وقتی مقیاس ثابت است.)
  const wideRows = [];
  for (let y = 0; y < rows; y++) if (rowCount[y] > cols * 0.5) wideRows.push(y);
  return {
    pane: { w: W, h: H, layers: stack.length },
    rowFirst: firstWhere(rowCount, 3),
    rowLast: lastWhere(rowCount, 3),
    colFirst: firstWhere(colCount, 2),
    colLast: lastWhere(colCount, 2),
    wideRows: wideRows.join(','),
    ink,
  };
})()`;

const report: Record<string, unknown> = {
  base: BASE,
  route: ROUTE,
  viewport: { width: WIDTH, height: HEIGHT },
  at: new Date().toISOString(),
};

const browser = await chromium.launch({ headless: !flag('--show'), executablePath: CHROME || undefined });
const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT } });
await context.addInitScript(AUTH_INIT);
const page = await context.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200));
});
page.on('pageerror', (e: { message: string }) => consoleErrors.push(`pageerror: ${e.message}`.slice(0, 200)));

const sig = () => page.evaluate(SIG) as Promise<Record<string, number | string>>;
const num = (s: Record<string, number | string>, k: string) => (typeof s[k] === 'number' ? (s[k] as number) : NaN);

try {
  await page.goto(`${BASE}${ROUTE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT_MS);

  // ۱) مکان‌نما بیرونِ چارت: متنِ چسبان (#168) نباید روی بوم باشد
  await page.mouse.move(6, 6);
  await page.waitForTimeout(700);
  const idle = await sig();
  report.idle = idle;

  // ۲) مکان‌نما روی چارت: با follow_cross متن همان‌جا می‌آید
  const box = await page.evaluate(
    `(()=>{const cs=[...document.querySelectorAll('canvas')].filter(c=>c.getBoundingClientRect().width>260&&c.getBoundingClientRect().height>140);cs.sort((a,b)=>b.getBoundingClientRect().width*b.getBoundingClientRect().height-a.getBoundingClientRect().width*a.getBoundingClientRect().height);const r=cs[0].getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()`,
  ) as { x: number; y: number; w: number; h: number };
  report.candlePane = box;
  // #168 با برداشتِ پیکسلِ خودِ صفحه سنجیده می‌شود: کراس‌هیر و متن روی لایه‌ای
  // جدا از کندل‌ها نقاشی می‌شوند و در ترکیبِ canvas این پنل نیستند.
  const topLeftClip = { x: box.x, y: box.y, width: Math.min(box.w, 560), height: Math.min(box.h, 150) };
  await page.screenshot({ path: `${SHOTS}/probe168_idle.png`, clip: topLeftClip });
  const cx = Math.round(box.x + box.w * 0.55);
  const cy = Math.round(box.y + box.h * 0.45);
  await page.mouse.move(cx, cy);
  await page.waitForTimeout(700);
  const hover = await sig();
  report.hover = hover;
  await page.screenshot({ path: `${SHOTS}/probe168_hover.png`, clip: topLeftClip });
  await page.screenshot({ path: `${SHOTS}/probe_hover.png`, clip: { x: box.x, y: box.y, width: Math.min(box.w, 900), height: Math.min(box.h, 320) } });

  // ۳) درگِ افقیِ واقعی (#167) — مقیاسِ عمودی نباید بپرد
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(cx - i * 18, cy, { steps: 2 });
  await page.mouse.up();
  await page.waitForTimeout(900);
  const afterDrag = await sig();
  report.afterDrag = afterDrag;
  const dy = {
    rowFirst: num(afterDrag, 'rowFirst') - num(hover, 'rowFirst'),
    rowLast: num(afterDrag, 'rowLast') - num(hover, 'rowLast'),
  };
  const dx = {
    colFirst: num(afterDrag, 'colFirst') - num(hover, 'colFirst'),
    colLast: num(afterDrag, 'colLast') - num(hover, 'colLast'),
  };
  report.drag = {
    wideRowsBefore: String(hover.wideRows ?? ''),
    wideRowsAfter: String(afterDrag.wideRows ?? ''),
    verticalJumpRows: dy,
    horizontalShiftCols: dx,
    scaleHeld: String(hover.wideRows ?? '') === String(afterDrag.wideRows ?? ''),
    panned: Math.abs(dx.colFirst) > 4 || Math.abs(dx.colLast) > 4,
  };

  // ۴) نوعِ چارت (#166): هر دکمه باید روی پیکسل‌ها اثر بگذارد
  // ۴) کنترلِ مثبت: درگِ بلندی که دید را به منطقۀ قیمتِ دیگری می‌برد باید
  // مقیاس را آزاد کند — وگرنه «صفرِ پرش» می‌تواند یعنی «سنجه هیچی نمی‌بیند».
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  for (let i = 1; i <= 12; i++) await page.mouse.move(cx - i * 120, cy, { steps: 3 });
  await page.mouse.up();
  await page.waitForTimeout(900);
  const afterLongDrag = await sig();
  report.afterLongDrag = afterLongDrag;
  report.longDrag = {
    wideRowsBefore: String(afterDrag.wideRows ?? ''),
    wideRowsAfter: String(afterLongDrag.wideRows ?? ''),
    horizontalShiftCols: num(afterLongDrag, 'colLast') - num(afterDrag, 'colLast'),
    // کنترلِ مثبت: درگِ بلند دید را به منطقۀ قیمتِ دیگری می‌برد؛ مقیاس باید
    // آزاد شود. اگر اینجا هم تکانی نخورد، سنجهٔ «نگه‌داشتن» بی‌معنی است.
    scaleRechosen:
      String(afterDrag.wideRows ?? '') !== String(afterLongDrag.wideRows ?? ''),
  };
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT_MS);

  // ۵) نوعِ چارت (#166): هر دکمه باید هم در استور و هم روی پیکسل‌ها اثر بگذارد
  await page.mouse.move(6, 6);
  await page.click('[data-testid="open-chart-settings"]');
  await page.waitForTimeout(700);
  const dialog = await page.evaluate(
    `(()=>{const d=document.querySelector('[data-testid="chart-settings"]');if(!d)return{open:false};
      const tabs=[...d.querySelectorAll('[data-testid^="settings-tab-"]')].map(t=>t.textContent.trim());
      const r=d.getBoundingClientRect();
      return{open:true,tabs,box:{w:Math.round(r.width),h:Math.round(r.height)},
        overflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth}})()`,
  ) as Record<string, unknown>;
  report.dialog = dialog;
  await page.screenshot({ path: `${SHOTS}/probe_dialog_${WIDTH}.png` });

  await page.click('[data-testid="settings-tab-symbol"]');
  await page.waitForTimeout(250);
  const types: Record<string, unknown> = {};
  let shotIdx = 0;
  const byText = async (label: string) => {
    // کلیک فقط داخلِ دیالوگ — منوی «نوعِ کندل»ِ نوارِ ابزار هم دکمهٔ «خط» دارد
    const modal = page.locator('[data-testid="chart-settings"]');
    await modal.getByRole('button', { name: label, exact: true }).first().click();
    await page.waitForTimeout(500);
    // دیالوگ روی چارت را با بک‌دراپِ تار می‌پوشاند: برای عکسِ مقایسه‌ای ببند و باز کن
    await page.click('[data-testid="chart-settings-close"]');
    await page.waitForTimeout(700);
    await page.mouse.move(6, 6);
    await page.waitForTimeout(350);
    const s = await sig();
    const stored = await page.evaluate(
      `(()=>{try{return (JSON.parse(localStorage.getItem('fts.chart.settings.v1')||'{}')).chartType}catch{return null}})()`,
    );
    types[label] = {
      storeChartType: stored,
      rowFirst: num(s, 'rowFirst'),
      rowLast: num(s, 'rowLast'),
      ink: num(s, 'ink'),
      err: s.err ?? null,
    };
    await page.screenshot({
      path: `${SHOTS}/probe_type_${(shotIdx += 1)}_${String(stored)}.png`,
      clip: { x: box.x, y: box.y, width: Math.min(box.w, 700), height: Math.min(box.h, 420) },
    });
    await page.click('[data-testid="open-chart-settings"]');
    await page.waitForTimeout(400);
    await page.click('[data-testid="settings-tab-symbol"]');
    await page.waitForTimeout(250);
  };
  for (const label of ['کندل شمعی', 'خط', 'هیکین-آشی', 'اریا']) {
    try {
      await byText(label);
    } catch (e) {
      types[label] = `ERR ${String((e as Error).message).slice(0, 90)}`;
    }
  }
  report.chartTypes = types;
  const kinds = Object.values(types).filter((t) => typeof t === 'object' && t !== null) as {
    ink: number;
    rowFirst: number;
    rowLast: number;
  }[];
  report.chartTypesDistinct = new Set(kinds.map((t) => `${t.rowFirst}:${t.rowLast}:${t.ink}`)).size;

  // ۶) تب‌های دیگر را هم باز کن و خطای کنسول را ببین
  for (const id of ['status', 'scales', 'colors', 'precision', 'events']) {
    try {
      await page.click(`[data-testid="settings-tab-${id}"]`);
      await page.waitForTimeout(220);
      await page.screenshot({ path: `${SHOTS}/probe_tab_${id}_${WIDTH}.png` });
    } catch (e) {
      report[`tab_${id}_err`] = String((e as Error).message).slice(0, 90);
    }
  }
  await page.screenshot({ path: `${SHOTS}/probe_dialog_events_${WIDTH}.png` });
  await page.click('[data-testid="chart-settings-close"]');
} catch (e) {
  report.fatal = String((e as Error).message).slice(0, 300);
}

report.consoleErrors = consoleErrors.slice(0, 20);
mkdirSync(SHOTS, { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report, null, 2));
await browser.close();
