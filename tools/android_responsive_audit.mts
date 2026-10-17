// ممیزیِ responsive همۀ routeها در Chromium با بیلدِ موبایل (VITE_LOCAL_DATA) و
// همان بایت‌هایِ پختِ CI. سنجه‌ها بی‌اسکرین‌شات‌نگری‌اند:
//   ۱) overflowX — scrollWidth بزرگ‌تر ازِ viewport
//   ۲) عناصرِ بیرونِ viewport — boundingِ هر المانِ دیدنیِ تعاملی/متنی
//   ۳) پوشیدگی — centerِ هر کنترلِ تعاملی با elementsFromPoint؛ اگر المانِ
//        رویی زیرِ نوارِ پائین/ریلِ کناری باشد ⇒ کنترلِ غیرقابلِ لمس
//   ۴) هدفِ لمسی کوچک — دکمه/لینکِ دیدنی کوچک‌تر از 44x44 (هشدار)
//   ۵) بریدگیِ متن — scrollWidth > clientWidth درِ ظرفِ بی‌ellipsisِ فعال
// شبکه‌هایِ بیرونی abort می‌شوند (رفتارِ آفلاینِ APK؛ determinism). فونتِ
// بزرگ‌نماییِ سیستم با بزرگکردنِ font-sizeِ ریشۀ html تقلید می‌شود — limitِ
// این تقلید درِ گزارش صریح می‌آید (font boostingِ WebView دقیقاً همین اثرِ
// rem را ندارد).
import { createServer } from 'node:http';
import { createReadStream, existsSync, readFileSync, statSync, mkdirSync, writeFileSync } from 'node:fs';
import { extname, join, resolve, relative, sep, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';

const DIST = resolve('frontend/dist');
const PORT = Number(process.env.BORS_ANDROID_AUDIT_PORT ?? 8799);
const OUT = resolve(process.env.BORS_ANDROID_AUDIT_OUT ?? '_audit/android_responsive');
if (!existsSync(join(DIST, 'index.html'))) throw new Error('Build frontend/dist before running the Android responsive audit.');
if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error('BORS_ANDROID_AUDIT_PORT must be between 1 and 65535.');
const { chromium } = await import(pathToFileURL(
  resolve('frontend/node_modules/playwright/index.mjs'),
).href);
mkdirSync(OUT, { recursive: true });
const MIME: Record<string, string> = {
  '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html',
  '.json': 'application/json', '.wasm': 'application/wasm', '.png': 'image/png',
  '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.db': 'application/octet-stream',
  '.gz': 'application/octet-stream', '.svg': 'image/svg+xml',
};
const server = createServer((rq, rs) => {
  let p: string;
  try { p = decodeURIComponent(new URL(rq.url ?? '/', 'http://127.0.0.1').pathname); }
  catch { rs.writeHead(400); rs.end(); return; }
  const rel = p === '/' ? 'index.html' : p.replace(/^\/+/, '');
  const file = resolve(DIST, rel);
  const fromDist = relative(DIST, file);
  console.log('REQ', rq.method, p, 'exists=' + (existsSync(file) && statSync(file).isFile()));
  if (p.includes('mobile_snapshot')) {
    console.log('ASSET', p, 'exists=' + (existsSync(file) && statSync(file).isFile()), 'path=' + file);
  }
  if (fromDist === '..' || fromDist.startsWith('..' + sep) || isAbsolute(fromDist)) {
    rs.writeHead(403); rs.end(); return;
  }
  if (existsSync(file) && statSync(file).isFile()) {
    rs.writeHead(200, { 'content-type': MIME[extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(rs);
    return;
  }
  if (extname(p)) { rs.writeHead(404); rs.end(); return; } // assetِ نامعلوم ⇒ 404 (سروِ APK)
  rs.writeHead(200, { 'content-type': 'text/html' });
  rs.end(readFileSync(join(DIST, 'index.html')));
});
await new Promise<void>((r, reject) => {
  server.once('error', reject);
  server.listen(PORT, '127.0.0.1', () => { server.off('error', reject); r(); });
});

const ALL_ROUTES = [
  ['master', '#/master'], ['market', '#/market'], ['market-status', '#/market-status'],
  ['fundamental', '#/fundamental/فولاد'], ['technical', '#/technical/فولاد'],
  ['engine-lab', '#/engine-lab'], ['strategy-tree', '#/strategy-tree/فولاد'],
  ['portfolio', '#/portfolio'], ['watch', '#/watch'], ['notifications', '#/notifications'],
  ['nope404', '#/nope-does-not-exist'],
] as const;
const routeFilter = new Set((process.env.BORS_ANDROID_AUDIT_ROUTES ?? '').split(',').map((x) => x.trim()).filter(Boolean));
const ROUTES = routeFilter.size ? ALL_ROUTES.filter(([name]) => routeFilter.has(name)) : ALL_ROUTES;

const ALL_SIZES: { tag: string; w: number; h: number; dpr: number; land?: boolean }[] = [
  { tag: '360x800', w: 360, h: 800, dpr: 3 },
  { tag: '390x844', w: 390, h: 844, dpr: 3 },
  { tag: '430x932', w: 430, h: 932, dpr: 3 },
  { tag: '360x640', w: 360, h: 640, dpr: 3 },
  { tag: '812x375L', w: 812, h: 375, dpr: 2, land: true },
  { tag: '820x1180', w: 820, h: 1180, dpr: 2 }, // تبلت
];
const sizeFilter = new Set((process.env.BORS_ANDROID_AUDIT_SIZES ?? '').split(',').map((x) => x.trim()).filter(Boolean));
const SIZES = sizeFilter.size ? ALL_SIZES.filter((size) => sizeFilter.has(size.tag)) : ALL_SIZES;
const FONT_SCALES = [1, 1.25]; // دومین دور = تقلیدِ font scalingِ سیستم

type Issue = { kind: string; sel: string; note: string };

async function probe(page: any, land: boolean): Promise<{ issues: Issue[]; metrics: Record<string, unknown> }> {
  return page.evaluate(({ land: isLand }: { land: boolean }) => {
    const vw = window.innerWidth; const vh = window.innerHeight;
    const issues: Issue[] = [];
    const sel = (el: Element): string => {
      const cls = (el.getAttribute('class') ?? '').split(/\s+/).filter(Boolean).slice(0, 2).join('.');
      const id = el.id ? `#${el.id}` : '';
      return `${el.tagName.toLowerCase()}${id}${cls ? `.${cls}` : ''}`.slice(0, 90);
    };
    const visibleRect = (el: Element): { left: number; right: number; top: number; bottom: number; width: number; height: number } | null => {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return null;
      let left = r.left; let right = r.right; let top = r.top; let bottom = r.bottom;
      let opacity = 1;
      let p: HTMLElement | null = el as HTMLElement;
      while (p) {
        const cs = getComputedStyle(p);
        opacity *= Number(cs.opacity || 1);
        if (p.hidden || p.hasAttribute('inert') || p.getAttribute('aria-hidden') === 'true'
          || cs.visibility === 'hidden' || cs.display === 'none'
          || cs.contentVisibility === 'hidden' || opacity < 0.05) return null;
        if (p !== el) {
          const pr = p.getBoundingClientRect();
          if (cs.overflowX !== 'visible' && cs.overflowX !== 'overlay') {
            left = Math.max(left, pr.left); right = Math.min(right, pr.right);
          }
          if (cs.overflowY !== 'visible' && cs.overflowY !== 'overlay') {
            top = Math.max(top, pr.top); bottom = Math.min(bottom, pr.bottom);
          }
        }
        p = p.parentElement;
      }
      left = Math.max(left, 0); right = Math.min(right, window.innerWidth);
      top = Math.max(top, 0); bottom = Math.min(bottom, window.innerHeight);
      if (right - left < 1 || bottom - top < 1) return null;
      return { left, right, top, bottom, width: right - left, height: bottom - top };
    };
    const visible = (el: Element): boolean => visibleRect(el) !== null;
    const hasScrollableAncestor = (el: Element, axis: 'x' | 'y'): boolean => {
      let p = el.parentElement;
      while (p && p !== document.body) {
        const cs = getComputedStyle(p);
        const overflow = axis === 'x' ? cs.overflowX : cs.overflowY;
        const scrollable = axis === 'x'
          ? p.scrollWidth > p.clientWidth + 1
          : p.scrollHeight > p.clientHeight + 1;
        if (/auto|scroll|overlay/.test(overflow) && scrollable) return true;
        p = p.parentElement;
      }
      return false;
    };
    const docOverflowX = document.documentElement.scrollWidth - document.documentElement.clientWidth;
    if (docOverflowX > 4) {
      issues.push({ kind: 'document-overflow-x', sel: 'documentElement',
        note: 'scrollWidth=' + document.documentElement.scrollWidth + ' clientWidth=' + document.documentElement.clientWidth });
    }

    // ۲) تعاملی/متنیِ بیرونِ viewport
    const inter = [...document.querySelectorAll('a,button,input,select,textarea,[role="button"],[role="tab"],[role="checkbox"]')];
    let offscreen = 0;
    for (const el of inter) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      if ((r.left < -4 || r.right > vw + 4) && !hasScrollableAncestor(el, 'x')) {
        offscreen += 1;
        if (issues.length < 40) issues.push({ kind: 'offscreen', sel: sel(el),
          note: `x=[${Math.round(r.left)},${Math.round(r.right)}] vw=${vw}` });
      }
    }
    // ۳) پوشیدگی زیرِ نوار/ریل
    const barSel = (el: Element | null) => el?.closest('[data-shell="sidebar"]') ?? null;
    const NAV_SELECTOR = '[data-shell="sidebar"]';
    let covered = 0;
    for (const el of inter) {
      if (!visible(el)) continue;
      const r = visibleRect(el);
      if (!r) continue;
      const cx = Math.min(Math.max(r.left + r.width / 2, 1), vw - 1);
      const cy = Math.min(Math.max(r.top + r.height / 2, 1), vh - 1);
      const top = document.elementFromPoint(cx, cy);
      if (!top) continue;
      const onNav = barSel(top);
      if (onNav && !el.contains(top) && !top.contains(el) && !el.closest(NAV_SELECTOR)) {
        covered += 1;
        if (issues.length < 40) issues.push({ kind: 'covered', sel: sel(el),
          note: `covered-by=${sel(onNav)}` });
      }
    }
    // ۴) هدفِ لمسی کوچک (فقط کنترل‌هایِ درFlowِ دیدنی)
    let tiny = 0; let tinyEx = '';
    for (const el of inter) {
      if (!visible(el)) continue;
      if (el.closest('[class*="chart"],canvas')) continue;
      const r = visibleRect(el);
      if (!r) continue;
      if ((r.width < 44 || r.height < 44) && r.width >= 8 && r.height >= 8) {
        tiny += 1;
        if (!tinyEx) tinyEx = `${sel(el)} (${Math.round(r.width)}x${Math.round(r.height)})`;
      }
    }
    // ۵) بریدگیِ متنِ بی‌ellipsis درِ ظرفِ overflow-hidden
    let clipped = 0; let clipEx = '';
    const walk = (el: Element) => {
      const cs = getComputedStyle(el);
      const direct = [...el.childNodes].some((n) => n.nodeType === 3 && (n.textContent ?? '').trim().length > 3);
      if (!direct || cs.display === 'none' || !visible(el)) return;
      if (el.scrollWidth - el.clientWidth > 2 && cs.textOverflow !== 'ellipsis'
        && /hidden|clip/.test(cs.overflowX)) {
        clipped += 1;
        if (!clipEx) clipEx = `${sel(el)} sw=${el.scrollWidth} cw=${el.clientWidth}`;
      }
    };
    for (const el of document.querySelectorAll('p,span,td,th,div,label,h1,h2,h3,h4')) walk(el);
    if (clipped > 0) {
      issues.push({ kind: 'clipped-text', sel: clipEx || 'text',
        note: 'count=' + clipped + '; example=' + clipEx });
    }
    if ((document.body.innerText ?? '').includes('خطا در بارگذاری داده‌ها')) {
      issues.push({ kind: 'mobile-boot-error', sel: 'MobileBootstrap',
        note: (document.body.innerText ?? '').slice(0, 240) });
    }
    const bootT = (window as any).bootTiming ?? null;
    const head = document.querySelector('[data-testid="tape-head"]') as HTMLElement | null;
    const tableViewport = head?.parentElement as HTMLElement | null;
    const stickyFilter = document.querySelector('.app-main .panel-in.sticky') as HTMLElement | null;
    const marketRoot = stickyFilter?.parentElement as HTMLElement | null;
    const tapePanel = head?.closest('.glass-panel') as HTMLElement | null;
    const box = (el: HTMLElement | null) => el ? (() => {
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      return { cls: el.className.toString().slice(0, 100), x: Math.round(r.x), y: Math.round(r.y),
        w: Math.round(r.width), h: Math.round(r.height), pos: cs.position, display: cs.display,
        direction: cs.flexDirection, gap: cs.gap, marginTop: cs.marginTop, transform: cs.transform,
        scrollTop: el.scrollTop, clientHeight: el.clientHeight };
    })() : null;
    const rowNodes = [...document.querySelectorAll('[data-testid="tape-row"]')].filter(visible).slice(0, 3) as HTMLElement[];
    const firstRow = rowNodes[0] ?? null;
    const gridProbe = (el: HTMLElement | null) => el ? {
      gridTemplateColumns: getComputedStyle(el).gridTemplateColumns,
      position: getComputedStyle(el).position,
      zIndex: getComputedStyle(el).zIndex,
      rect: (() => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y),
        w: Math.round(r.width), h: Math.round(r.height) }; })(),
      width: Math.round(el.getBoundingClientRect().width),
      children: [...el.children].slice(0, 12).map((child) => {
        const r = child.getBoundingClientRect();
        return { text: (child.textContent ?? '').trim().slice(0, 32),
          x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
      }),
    } : null;
    const active = document.activeElement as HTMLElement | null;
    return {
      issues,
      metrics: {
        vw, vh, overflowX: docOverflowX,
        interCount: inter.length, offscreenCount: offscreen, coveredCount: covered,
        tinyTargets: tiny, tinyExample: tinyEx, clippedCount: clipped, clippedExample: clipEx,
        boot: bootT ? { source: bootT.source, totalMs: bootT.totalMs } : null,
        pageScroll: { x: window.scrollX, y: window.scrollY },
        stickyFilter: gridProbe(stickyFilter),
        layout: { appMain: box(document.querySelector('.app-main') as HTMLElement | null),
          marketRoot: box(marketRoot), filter: box(stickyFilter), tapePanel: box(tapePanel),
          marketChildren: marketRoot ? [...marketRoot.children].map((el) => box(el as HTMLElement)) : [] },
        activeElement: active ? { tag: active.tagName, label: active.getAttribute('aria-label'), text: (active.innerText ?? '').slice(0, 80) } : null,
        selects: [...document.querySelectorAll('select')].map((el) => ({
          label: el.getAttribute('aria-label'), value: (el as HTMLSelectElement).value,
          focused: el === active,
        })),
        tapeTable: head ? {
          headers: [...head.children].map((el) => (el.textContent ?? '').trim()),
          viewportWidth: tableViewport?.clientWidth ?? null,
          contentWidth: tableViewport?.scrollWidth ?? null,
          canScrollX: !!tableViewport && tableViewport.scrollWidth > tableViewport.clientWidth + 1,
          headGrid: gridProbe(head), rowGrid: gridProbe(firstRow),
          rows: rowNodes.map((row) => [...row.children].map((cell) => (cell.textContent ?? '').trim())),
        } : null,
        textLen: (document.body.innerText ?? '').length,
        bodyTextSample: (document.body.innerText ?? '').slice(0, 1400),
      },
    };
  }, { land });
}

const report: any = { at: new Date().toISOString(), dist: DIST, port: PORT,
  selectedRoutes: ROUTES.map(([name]) => name), selectedSizes: SIZES.map((size) => size.tag),
  target: 'Playwright viewport emulation via Edge; this does not verify Android WebView on a device.',
  note: 'Chromium + APK-like server؛ شبکه بیرونی abort (آفلاینِ APK). font-scale تقلیدِ rem است نه font-boostingِ WebView.',
  runs: [] };

let browser: any = null;
let failed = 0;
let warningRuns = 0;
try {
browser = await chromium.launch({
  channel: process.env.BORS_ANDROID_AUDIT_BROWSER ?? 'msedge',
  args: ['--no-sandbox'],
});
for (const size of SIZES) {
  for (const fs of FONT_SCALES) {
    if (fs > 1 && !['360x800', '812x375L'].includes(size.tag)) continue; // نمونه‌ای، نه تمامِ ماتریس
    const ctx = await browser.newContext({
      viewport: { width: size.w, height: size.h }, deviceScaleFactor: size.dpr,
      isMobile: !size.land, hasTouch: true, locale: 'fa-IR', serviceWorkers: 'block',
    });
    // Block every HTTP(S) host except this localhost server. A restrictive CSP
    // is also added to the local preview document; no app request can leave.
    const externalHttp = /^https?:\/\/(?!127\.0\.0\.1(?::\d+)?(?:\/|$)|localhost(?::\d+)?(?:\/|$))/i;
    await ctx.route(externalHttp, (r: any) => r.abort());
    await ctx.addInitScript((scale: number) => {
      try { sessionStorage.setItem('bors_screen_unlocked', 'true'); } catch { /* noop */ }
      if (scale !== 1) {
        const s = document.createElement('style');
        s.textContent = `html{font-size:${scale * 100}% !important}`;
        document.addEventListener('DOMContentLoaded', () => document.documentElement.appendChild(s));
      }
    }, fs);
    const dir = join(OUT, `${size.tag}${fs !== 1 ? '@font125' : ''}`);
    mkdirSync(dir, { recursive: true });
    for (const [name, hash] of ROUTES) {
      const page = await ctx.newPage();
      const pageErrors: string[] = [];
      const consoleErrors: string[] = [];
      page.on('console', (m: any) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 180)); });
      page.on('pageerror', (e: Error) => pageErrors.push(String(e).slice(0, 160)));
      page.on('response', async (r: any) => {
        if (!r.url().includes('mobile_snapshot')) return;
        const b = await r.body().catch(() => new Uint8Array());
        console.log('RESPONSE', r.request().method(), r.status(), r.url(), 'bytes=' + b.byteLength,
          'head=' + [...b.slice(0, 2)].map((x: number) => x.toString(16).padStart(2, '0')).join(''));
      });
      try {
        await page.goto(`http://127.0.0.1:${PORT}/${hash}`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
        await page.waitForFunction(
          () => {
            const timing = (window as any).bootTiming;
            return (typeof timing?.source === 'string' && timing.source.length > 0
              && typeof timing.totalMs === 'number' && timing.totalMs > 0)
              || (document.body.innerText ?? '').includes('خطا در بارگذاری داده‌ها');
          },
          undefined,
          { timeout: 60_000 },
        );
        await page.waitForTimeout(2500); // جدول/چارت بنشیند
        const { issues, metrics } = await probe(page, !!size.land);
        const warnings: Issue[] = [];
        const tinyTargets = Number(metrics.tinyTargets ?? 0);
        if (tinyTargets > 0) {
          warnings.push({ kind: 'small-touch-target', sel: String(metrics.tinyExample ?? ''),
            note: 'count=' + tinyTargets + '; recommended minimum=44x44' });
          warningRuns += 1;
        }
        const shot = join(dir, `${name}.png`);
        await page.screenshot({ path: shot });
        report.runs.push({ size: size.tag, font: fs, route: name, metrics, issues,
          warnings, pageErrors, consoleErrors, screenshot: shot });
        const bad = issues.length;
        if (bad || pageErrors.length) failed += 1;
        console.log(`${size.tag}${fs !== 1 ? '@1.25' : ''} ${name.padEnd(15)} overflowX=${metrics.overflowX} off=${metrics.offscreenCount} cov=${metrics.coveredCount} tiny=${metrics.tinyTargets} clip=${metrics.clippedCount} boot=${(metrics as any).boot?.source} err=${pageErrors.length}`);
      } catch (e) {
        report.runs.push({ size: size.tag, font: fs, route: name, fatal: String(e).slice(0, 200) });
        failed += 1;
        console.log(`${size.tag} ${name} FATAL ${String(e).slice(0, 120)}`);
      } finally {
        await page.close().catch(() => {});
      }
    }
    await ctx.close();
  }
}
} catch (e) {
  report.fatal = String(e).slice(0, 500);
  failed += 1;
  console.error('FATAL', report.fatal);
} finally {
  await browser?.close().catch(() => {});
  await new Promise<void>((r) => server.close(() => r()));
}
report.runsWithIssues = failed;
report.runsWithWarnings = warningRuns;
mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, 'responsive_report.json'), JSON.stringify(report, null, 1), 'utf8');
console.log('DONE runs=', report.runs.length, 'withIssues=', failed, 'withWarnings=', warningRuns);
process.exitCode = failed > 0 ? 1 : 0;
