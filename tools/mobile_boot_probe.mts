/**
 * tools/mobile_boot_probe.mts — شاهدِ زندهٔ صفحۀ «دریافت دادهٔ آفلاین»
 *
 * چرا: شکایتِ مالک این بود که گوشی تا ~۱۰ دقیقه روی همین صفحۀ بی‌عدد می‌ماند.
 * دو چیز باید درِ مرورگر ثابت شود، نه درِ jsdom: (۱) نوارِ پیشرفت درصدِ واقعیِ
 * بایت را می‌شمارد و عدد بالا می‌رود، (۲) متنِ صفحه کوتاه است و جملهٔ اضافی
 * ندارد. بسترِ واقعی (APK + WebView) این‌جا تقلید می‌شود: بستۀ ۱۵٫۴ مگابایتی
 * از یک سرورِ محلی با سرعتِ تعیین‌شده تکه‌تکه می‌آید (content-length اعلام
 * شده، بدنه streaming) — یعنی همان شکلی که fetch درِ WebView می‌بیند.
 *
 * ساختِ باندل (پیش از این ابزار):
 *   MSYS_NO_PATHCONV=1 VITE_LOCAL_DATA=1 VITE_SNAPSHOT_URL=/probe_bundle.js \
 *   VITE_SNAPSHOT_REMOTE=http://127.0.0.1:8099/mirror/mobile_snapshot.db.gz \
 *   VITE_SNAPSHOT_STAMP=<built_at> npm run build
 *   cp dist_mobile/mobile_snapshot.db.gz frontend/dist/probe_bundle.js
 *
 * اجرا:
 *   node --experimental-strip-types tools/mobile_boot_probe.mts \
 *        --kbps 1200 --out _audit/mobile_boot.json
 */
import { createServer } from 'node:http';
import { createReadStream, existsSync, readFileSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { extname, join, resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const DIST = resolve(arg('dist', 'frontend/dist'));
const BUNDLE = resolve(arg('bundle', 'dist_mobile/mobile_snapshot.db.gz'));
const ASSET = arg('asset', '/probe_bundle.js');
const PORT = Number.parseInt(arg('port', '8099'), 10);
const KBPS = Number.parseInt(arg('kbps', '1200'), 10) || 1200;
const OUT = arg('out', '_audit/mobile_boot.json');
const SHOT_MID = arg('shot-mid', '_audit/mobile_boot_mid.png');
const SHOT_READY = arg('shot-ready', '_audit/mobile_boot_ready.png');
const SHOT_DRAWER = arg('shot-drawer', '_audit/mobile_boot_drawer.png');
const CHROME = process.env.JEV_CHROME ?? '';

const MIME: Record<string, string> = {
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.html': 'text/html',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.map': 'application/json',
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

if (!existsSync(join(DIST, 'index.html'))) throw new Error(`dist/index.html نیست: ${DIST}`);
if (!existsSync(BUNDLE)) throw new Error(`بستۀ داده نیست: ${BUNDLE}`);
const bundleBytes = statSync(BUNDLE).size;

// ── سرورِ محلی: فایل‌های dist + بستۀ تکه‌تکه با سرعتِ کنترل‌شده ───────────
const server = createServer((req, res) => {
  const path = decodeURIComponent((req.url ?? '/').split('?')[0]);
  if (path === ASSET) {
    res.writeHead(200, {
      'content-type': 'application/octet-stream',
      'content-length': String(bundleBytes),
      'cache-control': 'no-store',
    });
    const chunk = 64 * 1024;
    const delayMs = (chunk / 1024 / KBPS) * 1000;
    const stream = createReadStream(BUNDLE, { highWaterMark: chunk });
    const pump = async () => {
      for await (const buf of stream) {
        if (res.writableEnded || !res.write(buf)) await new Promise<void>((r) => res.once('drain', r));
        await sleep(delayMs);
      }
      res.end();
    };
    void pump().catch(() => res.destroy());
    return;
  }
  // مسیرِ آینه: همان بسته با نامِ ریلیز — برایِ آزمودنِ درگاهِ پشتیبان
  if (path === '/mirror/mobile_snapshot.db.gz') {
    res.writeHead(200, { 'content-type': 'application/octet-stream', 'content-length': String(bundleBytes) });
    createReadStream(BUNDLE).pipe(res);
    return;
  }
  const rel = path === '/' || path === '/#' ? 'index.html' : path.replace(/^\/+/, '');
  const file = join(DIST, rel);
  if (rel && file.startsWith(DIST) && existsSync(file) && statSync(file).isFile()) {
    res.writeHead(200, { 'content-type': MIME[extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(res);
    return;
  }
  // SPA fallback — همان رفتاری که asset serverِ اندروید برای مسیرِ ناشناخته
  res.writeHead(200, { 'content-type': 'text/html' });
  res.end(readFileSync(join(DIST, 'index.html')));
});
await new Promise<void>((r) => server.listen(PORT, '127.0.0.1', r));

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({
  executablePath: CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
  locale: 'fa-IR',
});
await ctx.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* مهم نیست */ }
});
// آفلاینِ مصنوعی: هیچ درخواستِ بیرونی از این سنجش بیرون نمی‌رود
await ctx.route('**://*.tsetmc.com/**', (r) => r.abort());
await ctx.route('**://github.com/**', (r) => r.abort());
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 200)}`));

const READ = () => {
  const card = document.querySelector('[data-testid="mobile-boot"]');
  const texts: string[] = [];
  if (card) {
    card.querySelectorAll('h2,p,div,span').forEach((el) => {
      if (el.children.length === 0) {
        const t = (el.textContent ?? '').trim();
        if (t) texts.push(t);
      }
    });
  }
  const bar = document.querySelector('[role="progressbar"] > div') as HTMLElement | null;
  const timing = (window as unknown as { bootTiming?: Record<string, unknown> }).bootTiming;
  return { booting: !!card, texts, barWidthPx: bar ? Math.round(bar.getBoundingClientRect().width) : 0,
           timing: timing ?? null };
};

const t0 = Date.now();
await page.goto(`http://127.0.0.1:${PORT}/#/`, { waitUntil: 'commit' });

// کارتِ boot بعد ازِ mount می‌آید؛ نبودش درِ لحظۀ اول طبیعی است، پس اول
// ظهورش را انتظار می‌کشیم و بعد نمونه‌برداری را شروع می‌کنیم.
const appeared = await page
  .waitForSelector('[data-testid="mobile-boot"]', { timeout: 20000 })
  .then(() => true)
  .catch(() => false);

type Sample = { atMs: number; texts: string[]; barWidthPx: number };
const samples: Sample[] = [];
let midShot = false;

if (appeared) {
  for (let i = 0; i < 700; i++) {
    const snap = await page.evaluate(READ);
    if (!snap.booting) break;
    samples.push({ atMs: Date.now() - t0, texts: snap.texts, barWidthPx: snap.barWidthPx });
    if (!midShot && snap.barWidthPx > 60) {
      await page.screenshot({ path: resolve(SHOT_MID) });
      midShot = true;
    }
    await sleep(100);
  }
}
await page
  .waitForFunction(() => !document.querySelector('[data-testid="mobile-boot"]'), { timeout: 90000 })
  .catch(() => undefined);
await page.waitForTimeout(1500);
await page.screenshot({ path: resolve(SHOT_READY) });
const final = await page.evaluate(READ);
const appReady = await page.evaluate(() => {
  const root = document.querySelector('#root');
  return !!root && root.children.length > 0 && !document.querySelector('[data-testid="mobile-boot"]');
});
const url = page.url();
// هر لایه‌ای که بعدِ بوت رویِ صفحه مانده است (sheet/dialog/sidebar) — همان
// شکلی که «سایدبار کلِ گوشی را پوشاند» دیده شد؛ بی‌این عدد، صفحهٔ آماده
// هم از نگاهِ تست سبز است.
const overlays = await page.evaluate(() => {
  const vw = innerWidth, vh = innerHeight;
  const out: { sel: string; w: number; h: number; coverPct: number; onScreen: boolean;
               left: number; right: number; cssLeft: string; cssRight: string;
               translate: string; transform: string; text: string }[] = [];  document.querySelectorAll('[data-shell],[role="dialog"],[aria-modal="true"]').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return;
    // برگۀ آف‌کanvas (sheetِ بسته با translate) اندازه دارد ولی رویِ صفحه
    // نیست؛ پس تقاطعِ مستطیل با viewport شرطِ «پوشاننده بودن» است.
    const onScreen = r.right > 4 && r.left < vw - 4 && r.bottom > 4 && r.top < vh - 4;
    out.push({
      sel: `${el.tagName.toLowerCase()}[${el.getAttribute('data-shell') ?? el.getAttribute('role') ?? 'aria-modal'}]`,
      w: Math.round(r.width), h: Math.round(r.height),
      coverPct: Math.round((r.width * r.height) / (vw * vh) * 100),
      onScreen,
      left: Math.round(r.left), right: Math.round(r.right),
      cssLeft: cs.left, cssRight: cs.right,
      translate: cs.translate, transform: cs.transform,
      text: (el.textContent ?? '').trim().slice(0, 40),
    });
  });
  return {
    layers: out,
    symbol: (() => { try { return localStorage.getItem('bors-symbol') ?? ''; } catch { return ''; } })(),
    // قاعدۀ mobile.css فقط با این کلاس و این media query می‌رسد؛ بی‌این دو
    // عدد، «قاعده در فایل هست» با «قاعده رویِ صفحه اثر دارد» یکی می‌شود.
    htmlClass: document.documentElement.className,
    portrait: matchMedia('(orientation: portrait)').matches,
    maxW: [...document.styleSheets].flatMap((s) => {
      try { return Array.from(s.cssRules); } catch { return []; }
    }).filter((r) => r instanceof CSSMediaRule)
      .map((r) => (r as CSSMediaRule).conditionText).slice(0, 8),
  };
});

// ── فاز ۲: کشویِ بازشده — لبه، ارتفاع و در دسترس بودنِ ✕ ─────────────────
// کشو باید به لبۀ صفحه بچسبد و دکمۀ بستنش زیرِ نوارِ وضعیتِ گوشی نرود؛
// هر دو بار درِ گزارشِ این فاز اندازه گرفته می‌شوند.
await page.evaluate(() => { try { localStorage.setItem('bors-symbol', 'خودرو'); } catch { /* مهم نیست */ } });
await page.reload({ waitUntil: 'commit' });
await page.waitForFunction(() => {
  const el = document.querySelector('aside[data-shell="inspector"]');
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.left >= -2 && r.right < innerWidth && !document.querySelector('[data-testid="mobile-boot"]');
}, { timeout: 60000 }).catch(() => undefined);
await page.waitForTimeout(900);
const drawer = await page.evaluate(() => {
  const el = document.querySelector('aside[data-shell="inspector"]');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const close = [...el.querySelectorAll('button')].find((b) => (b.textContent ?? '').includes('✕'));
  const cr = close?.getBoundingClientRect();
  return {
    left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top),
    width: Math.round(r.width), height: Math.round(r.height),
    flushToEdge: Math.abs(r.left) <= 1,
    closeFound: !!close,
    closeTop: cr ? Math.round(cr.top) : null,
    closeSize: cr ? `${Math.round(cr.width)}×${Math.round(cr.height)}` : '',
    symbolShown: (el.querySelector('header div')?.textContent ?? '').trim(),
  };
});
await page.screenshot({ path: resolve(SHOT_DRAWER) });

await browser.close();
server.close();

// ── داوری ────────────────────────────────────────────────────────────────
const FA = '۰۱۲۳۴۵۶۷۸۹';
/** رابط فارسی است: رقمِ لاتین درِ متن پیدا نمی‌شود، پس با کدپوینت خوانده می‌شود. */
const faInt = (s: string): number | null => {
  const m = /([۰-۹]+)\s*٪/.exec(s);
  if (!m) return null;
  return Number([...m[1]].map((c) => FA.indexOf(c)).join(''));
};
const percents = samples.map((s) => faInt(s.texts.join(' '))).filter((n): n is number => n !== null);
const monotone = percents.every((n, i) => i === 0 || n >= percents[i - 1]);
const longest = samples.flatMap((s) => s.texts).sort((a, b) => b.length - a.length)[0] ?? '';
const timings = (final.timing ?? {}) as Record<string, number | string>;

const report = {
  served: { bundleBytes, kbps: KBPS, asset: ASSET },
  bootSamples: samples.length,
  bootMs: percents.length ? samples.at(-1)?.atMs ?? 0 : 0,
  percentFirst: percents[0] ?? null,
  percentLast: percents.length ? percents[percents.length - 1] : null,
  percentMonotone: monotone,
  distinctPercents: [...new Set(percents)].length,
  bootTexts: samples.length ? samples[Math.floor(samples.length / 2)].texts : [],
  longestLine: { text: longest, chars: longest.length },
  allLines: [...new Set(samples.flatMap((s) => s.texts))],
  appReady,
  drawer,
  overlays: overlays.layers,
  bootSymbol: overlays.symbol,
  htmlClass: overlays.htmlClass,
  portrait: overlays.portrait,
  appUrl: url,
  bootTiming: timings,
  consoleErrors: consoleErrors.slice(0, 6),
  screenshots: { mid: SHOT_MID, ready: SHOT_READY, midTaken: midShot },
};
// ۷۰٪ یعنی دریافت تمام شده؛ مرحلۀ بازگشایی (۸۵٪) و دیتابیس (۹۵٪) رویِ
// ماشینِ تست چندصد میلی‌ثانیه‌اند و ممکن است هیچ نمونه‌ای از ایشان ثبت نشود،
// پس رقمِ آخرِ نمونه‌شده نباید از ۹۵٪ خواسته شود — یکنوا بودن کافی است.
const verdict =
  appReady && typeof report.percentLast === 'number' && report.percentLast >= 70
  && monotone && report.distinctPercents >= 5 && longest.length <= 44
    ? 'PASS' : 'CHECK';
mkdirSync(dirname(resolve(OUT)), { recursive: true });
writeFileSync(resolve(OUT), JSON.stringify({ verdict, ...report }, null, 1), 'utf8');
console.log(JSON.stringify({ verdict, ...report }, null, 1));
if (verdict !== 'PASS') process.exitCode = 1;
