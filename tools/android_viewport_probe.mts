#!/usr/bin/env node
/**
 * tools/android_viewport_probe.mts — هر route در هر سه اندازۀ تلفن، رویِ
 * باندلِ واقعیِ موبایل (VITE_LOCAL_DATA=1) با بستۀ دادۀ ۱۶ مگابایتی
 *
 * چرا جدا ازِ jobِ شبیه‌ساز: این سنجش درِ Chromium است، **نه** WebViewِ
 * اندروید. مزیتش: همیشه اجرا می‌شود و DOM را کامل می‌بیند. محدودیتش:
 * `env(safe-area-inset-*)` را هرگز بزرگ نمی‌کند (ناچِ تقلیدی ندارد)،
 * صفحه‌کلید را نشان نمی‌دهد و پلِ بومی/CapacitorHttp را ندارد. پس عددهایِ این
 * فایل «چیدمان درِ سه viewport» را ثابت می‌کند، نه «رفتار روی دستگاه»؛ حکمِ
 * دستگاه از tools/android_emu_verify.sh می‌آید و دو نتیجه درِ گزارش جدا
 * نوشته می‌شوند.
 *
 * چرا routeها تک‌تک: `/#/watch` که درِ دورِ پیش فرض می‌شد اصلاً route نیست
 * (routes.tsx: `''`، `market`، `fundamental/:symbol?`، `technical/:symbol?`،
 * `engine-lab`، `strategy-tree/:symbol?`، `portfolio`، `master/:symbol?`،
 * `*`) و صفحهٔ «پیدا نشد» را می‌داد؛ بی‌این فهرست، «ردیف=۰» به حسابِ چیدمان
 * گذاشته می‌شد در حالی که ابزار اشتباه بود.
 *
 * چرا بستۀ داده نامش `probe_bundle.js` است و نه `.gz`: Chromium درِ همین
 * harness پاسخِ بیگانیِ بزرگ را «دانلود» می‌کند و fetch با 204 و بدنهٔ صفر
 * برمی‌گردد (۲ مگابایت ⇒ ۲۰۰، ۱۰ و ۲۳ مگابایت ⇒ ۲۰۴؛ curl رویِ همان پورت همهٔ
 * بایت‌ها را می‌گیرد). بی‌دانستنِ این، پیامِ «بستۀ همراهِ برنامه gz نبود» به
 * حسابِ اپ می‌گذارید.
 *
 * پیش‌ساخت:
 *   cd frontend && MSYS_NO_PATHCONV=1 VITE_LOCAL_DATA=1 VITE_APP_VERSION=1.1.0 \
 *        VITE_SNAPSHOT_URL=/probe_bundle.js npm run build
 *   cp ../dist_mobile/mobile_snapshot.db.gz dist/probe_bundle.js
 *   JEV_CHROME=<chromium> node --experimental-strip-types \
 *        tools/android_viewport_probe.mts --asset probe_bundle.js
 */
import { createServer } from 'node:http';
import { createReadStream, existsSync, readFileSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, d = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : d; };
const DIST = resolve(arg('dist', 'frontend/dist'));
const ASSET = arg('asset', 'probe_bundle.js');
const PORT = Number.parseInt(arg('port', '8107'), 10);
const OUTDIR = arg('out', '_audit/android_release');
const SHOTS = join(OUTDIR, 'viewports');
const SIZES = arg('sizes', '360x800x3,390x844x3,412x915x3').split(',');
const ROUTES = arg('routes', ',market,fundamental,technical,strategy-tree,master,engine-lab,portfolio,nope-404').split(',');
const CHROME = process.env.JEV_CHROME ?? '';

if (!existsSync(join(DIST, 'index.html'))) throw new Error(`dist/index.html نیست: ${DIST}`);
if (!existsSync(join(DIST, ASSET))) {
  throw new Error(`بستۀ داده درِ dist نیست: ${ASSET} — cp dist_mobile/mobile_snapshot.db.gz frontend/dist/${ASSET}`);
}
mkdirSync(SHOTS, { recursive: true });

const MIME: Record<string, string> = {
  '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html',
  '.json': 'application/json', '.wasm': 'application/wasm', '.png': 'image/png',
  '.woff2': 'font/woff2', '.gz': 'application/octet-stream', '.map': 'application/json',
};
const server = createServer((req, res) => {
  const p = decodeURIComponent((req.url ?? '/').split('?')[0]);
  const rel = p === '/' ? 'index.html' : p.replace(/^\/+/, '');
  const file = join(DIST, rel);
  if (existsSync(file) && statSync(file).isFile()) {
    res.writeHead(200, { 'content-type': MIME[extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(res);
    return;
  }
  res.writeHead(200, { 'content-type': 'text/html' });   // SPA fallback، مثلِ asset serverِ اندروید
  res.end(readFileSync(join(DIST, 'index.html')));
});
await new Promise<void>((r) => server.listen(PORT, '127.0.0.1', r));

const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const browser = await chromium.launch({ executablePath: CHROME || undefined, args: ['--no-sandbox'] });
const results: Record<string, unknown>[] = [];

for (const spec of SIZES) {
  const [w, h, dpr] = spec.split('x').map((n) => Number.parseInt(n, 10));
  const ctx = await browser.newContext({
    viewport: { width: w, height: h }, deviceScaleFactor: dpr, isMobile: true,
    hasTouch: true, locale: 'fa-IR',
  });
  // آفلاینِ مصنوعی: هیچ درخواستی از این سنجش بیرون نمی‌رود (قیدیِ پروژه)
  await ctx.route('**://*.tsetmc.com/**', (r) => r.abort());
  await ctx.route('**://github.com/**', (r) => r.abort());
  // دروازۀ ورودِ محلی: سشن درِ sessionStorage است (authStore.ts:42)
  await ctx.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* بی‌اهمیت */ } });
  const page = await ctx.newPage();

  for (const route of ROUTES) {
    const errs: string[] = [];
    const onConsole = (m: { type: () => string; text: () => string }) => {
      if (m.type() === 'error') errs.push(String(m.text()).slice(0, 160));
    };
    const onPageError = (e: Error) => errs.push(`pageerror: ${String(e).slice(0, 160)}`);
    page.on('console', onConsole);
    page.on('pageerror', onPageError);
    await page.goto(`http://127.0.0.1:${PORT}/#/${route}`, { waitUntil: 'domcontentloaded' });
    try {
      await page.waitForFunction(() => !document.querySelector('[data-testid="mobile-boot"]'), { timeout: 60000 });
    } catch { /* صفحۀ بارگذاری تمام نشد — درِ record ثبت می‌شود */ }
    await page.waitForTimeout(2500);
    const m = await page.evaluate(() => {
      const box = (el: Element | null) => {
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height), bottom: Math.round(b.bottom) };
      };
      const bar = document.querySelector("aside[data-shell='sidebar']");
      const rows = document.querySelectorAll('[data-testid$="-row"], table tbody tr, [role="row"]');
      const last = rows[rows.length - 1] as HTMLElement | undefined;
      const probe = document.createElement('div');
      probe.style.cssText = 'position:fixed;left:0;bottom:0;padding-bottom:env(safe-area-inset-bottom,0px);visibility:hidden';
      document.body.appendChild(probe);
      const inset = getComputedStyle(probe).paddingBottom;
      probe.remove();
      const app = document.querySelector('.app-content');
      return {
        vw: innerWidth, vh: innerHeight,
        route: location.hash,
        title: document.title,
        bootCard: !!document.querySelector('[data-testid="mobile-boot"]'),
        fatalBanner: !!document.querySelector('.bors-fatal-banner'),
        notFound: /پیدا نشد|۴۰|404/.test(document.body.innerText.slice(0, 400)),
        bootTiming: (window as unknown as { bootTiming?: unknown }).bootTiming ?? null,
        viewportMeta: (document.querySelector('meta[name=viewport]') || {}).content || null,
        overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        rowCount: rows.length,
        textLen: document.body.innerText.replace(/\s+/g, ' ').trim().length,
        navBox: box(bar),
        navPadBottom: bar ? getComputedStyle(bar).paddingBottom : null,
        appContentPadBottom: app ? getComputedStyle(app).paddingBottom : null,
        lastRowBottom: last ? Math.round(last.getBoundingClientRect().bottom) : null,
        safeAreaBottom: inset,
        touchTargetsUnder44: Array.from(document.querySelectorAll("aside[data-shell='sidebar'] button, aside[data-shell='sidebar'] a"))
          .map((e) => Math.round(e.getBoundingClientRect().height)).filter((n) => n > 0 && n < 44).length,
        // عرضِ هدفِ لمس اندازه می‌شود ولی حکمِ قرمز نیست: درِ ۳۶۰px شش تب +
        // سه دکمۀِ خوشۀِ پایین هم‌زمان ۴۴pxِ عرض نمی‌گیرند؛ انتخابِ راه‌حل
        // (نوارِ لغزان یا منتقل‌کردنِ آن سه دکمه) رأیِ مالک است، نه تصمیمِ ابزار.
        navItemsUnder44Wide: Array.from(document.querySelectorAll("aside[data-shell='sidebar'] a"))
          .map((e) => Math.round(e.getBoundingClientRect().width)).filter((n) => n > 0 && n < 44).length,
        barScrolls: (() => { const b = document.querySelector("aside[data-shell='sidebar']");
          return b ? b.scrollWidth > b.clientWidth + 1 : null; })(),
      };
    });
    page.off('console', onConsole);
    page.off('pageerror', onPageError);
    // ERR_FAILED ها خودِ همین سنجش ساخته (route.abort برایِ tsetmc/github)؛
    // آن‌ها خطایِ اپ نیست و درِ حکم شمارش نمی‌شوند.
    const realErrs = errs.filter((e) => !/ERR_FAILED|Failed to load resource/.test(e));
    const shot = join(SHOTS, `${w}x${h}-${route || 'index'}.png`);
    await page.screenshot({ path: shot, fullPage: false });
    // فقط routeهایی که جدول دارند باید ردیف بدهند؛ technical (چارت)،
    // strategy-tree (گراف) و master (نمایِ مرحلۀ یکِ نماد، بی‌نماد = راهنما)
    // ردیفِ جدولی ندارند و صفرشان ایراد نیست.
    const TABLE_ROUTES = ['', 'market', 'fundamental', 'engine-lab', 'portfolio'];
    const expectRows = TABLE_ROUTES.includes(route);
    results.push({
      size: spec, route: route || '(index)', measured: m,
      consoleErrors: errs.slice(0, 8), blockedByHarness: errs.length - realErrs.length,
      screenshot: shot.replace(/\\/g, '/'),
      verdict: {
        booted: !m.bootCard && !m.fatalBanner,
        noHorizontalOverflow: Number(m.overflowX) <= 0,
        rowsRendered: expectRows ? Number(m.rowCount) > 0 : m.rowCount === 0,
        navOnScreen: m.navBox === null || Number(m.navBox.bottom) <= Number(m.vh) + 1,
        touchTargetsOk: Number(m.touchTargetsUnder44) === 0,
        cleanConsole: realErrs.length === 0,
      },
    });
  }
  await ctx.close();
}
await browser.close();
server.close();

const out = {
  at: new Date().toISOString(), dist: DIST.replace(/\\/g, '/'), asset: ASSET,
  note: 'Chromium — نه WebViewِ اندروید؛ env(safe-area-inset-*) اینجا همیشه صفر است و صفحه‌کلید تقلید نمی‌شود',
  results,
};
mkdirSync(OUTDIR, { recursive: true });
writeFileSync(join(OUTDIR, 'viewport_probe.json'), JSON.stringify(out, null, 2), 'utf8');
let bad = 0;
for (const r of results as { size: string; route: string; verdict: Record<string, boolean>; measured: Record<string, unknown> }[]) {
  const failed = Object.entries(r.verdict).filter(([, v]) => !v).map(([k]) => k);
  if (failed.length) bad++;
  console.log(`${r.size} ${r.route.padEnd(14)} rows=${String(r.measured.rowCount).padStart(4)} ` +
    `ovfX=${r.measured.overflowX} nav=${JSON.stringify(r.measured.navBox)} ` +
    `${failed.length ? 'FAIL: ' + failed.join(', ') : 'ok'}`);
}
console.log(`\nPROBE ${results.length} record (3 انداز × ${ROUTES.length} route) — ${bad} با سنجۀ رد`);
process.exit(bad ? 1 : 0);
