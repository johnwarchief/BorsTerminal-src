/**
 * tools/ui_audit_s1.mts — ماتریسِ responsiveِ همهٔ routeها، قابلِ تکرار و قابلِ diff
 *
 * چرا این ابزار هست (مأموریتِ audit سیستمِ اول، ۲۰۲۶-۱۰-۱۵): آزمون‌های jsdom
 * متن و رندر را ثابت می‌کنند ولی هیچ‌چیز دربارهٔ چیدمانِ واقعی. این اسکریپت
 * Chromium واقعی را با viewport داده‌شده بالا می‌آورد، هر route را می‌گردد و
 * به‌جای «خوب به نظر می‌رسد» عدد بیرون می‌دهد:
 *
 *   • overflow افقی/عمودیِ بدنه (scrollWidth − clientWidth)
 *   • عناصر بیرونِ viewport، با تفکیکِ «درِ کانتینرِ اسکرول‌شونده» (مجاز) از
 *     «واقعاً بیرونِ صفحه» (ایراد) — بی‌این تفکیک، هر جدولِ عریبی قرمز می‌شود
 *   • متن بریده (scrollWidth > clientWidth با overflow نه‌visible) با نامِ
 *     testid/کلاس و خودِ متن
 *   • اسکرول‌بارهای افقی (فقط اطلاع‌رسان: جدولِ پرحجم حق دارد)
 *   • خطاهای کنسول و requestهای شکست‌خورده
 *   • ارتفاعِ ستون‌های اصلی (app-main، سایدبار، پنل‌ها) و وضعیتِ stickyِ هدر
 *     پس از اسکرول تا انتها
 *
 * ورودی‌ها: --base (آدرس اپ)، --viewports 2560x1440,3840x2160, --routes،
 * --clicks «route=متنِ دکمه» برایِ آزمودنِ مودال/تب، --out.
 *
 * هیچ سفارشی ارسال نمی‌شود و هیچ داده‌ای تغییر نمی‌کند: فقط GET و کلیکِ
 * رابط. نشستِ محلی ازِ همان دروازهٔ همیشگی (bors_auth_session درِ sessionStorage)
 * تزریق می‌شود — رمز تایپ نمی‌شود.
 *
 * اجرا (با Chromiumِ موجود رویِ این ماشین؛ بی‌JEV_CHROME خودِ jev-browser نصبش
 * را صدا می‌زند که اینجا شبکه‌ای نیست):
 *   JEV_CHROME=<chrome.exe> node --experimental-strip-types tools/ui_audit_s1.mts \
 *       --base http://127.0.0.1:8123 --viewports 2560x1440,3840x2160
 */
import { mkdirSync } from 'node:fs';
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const BASE = arg('base', 'http://127.0.0.1:8123/');
const VIEWPORTS = (arg('viewports', '2560x1440') || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)
  .map((s) => {
    const [w, h] = s.split('x').map((n) => Number.parseInt(n, 10));
    return { width: w, height: h, label: s };
  });
const WAIT_MS = Number.parseInt(arg('wait', '9000'), 10);
const OUT = arg('out', '_audit/ui_audit.json');
const SHOT_DIR = arg('shots', '_audit/ui-audit');

interface RouteSpec { path: string; name: string; ready: string; clicks?: string[] }

/** فهرستِ routeها از `frontend/src/routes.tsx` — نه از سایدبار. */
const ROUTES: RouteSpec[] = [
  { path: '/master', name: 'غربالگری FTS', ready: '[data-testid="funnel-body"], .app-main' },
  { path: '/market', name: 'تابلوخوانی', ready: '[data-testid="market-table"], .app-main' },
  { path: '/market-status', name: 'وضعیت بازار', ready: '.app-main' },
  { path: '/notifications', name: 'مرکز اعلان', ready: '.app-main' },
  { path: '/fundamental/فولاد', name: 'بنیادی (نماددار)', ready: '.app-main' },
  { path: '/technical/فولاد', name: 'تکنیکال (نماددار)', ready: 'canvas, .app-main' },
  { path: '/strategy-tree/فولاد', name: 'درخت استراتژی', ready: '.app-main' },
  { path: '/portfolio', name: 'مدیریت پرتفوی', ready: '.app-main' },
  { path: '/watch', name: 'دیده‌بان بازار', ready: '[data-testid="watch-summary"], .app-main' },
  { path: '/engine-lab', name: 'آزمایشگاه موتور (ابزار توسعه)', ready: '.app-main, body' },
  { path: '/no-such-route', name: 'صفحۀ نشانیِ ثبت‌نشده', ready: '[data-testid="route-not-found"]' },
];

const CLICKS: Record<string, string[]> = {};
// قالب: "/watch=ستون‌ها|حذف  /market=فیلترها|ستون‌ها" (جداکنندهٔ برچسب‌ها «|»،
// چون خودِ برچسب‌ها ویرگول دارند)
for (const spec of (arg('clicks', '') || '').split(';').map((s) => s.trim()).filter(Boolean)) {
  const i = spec.indexOf('=');
  if (i > 0) {
    const key = spec.slice(0, i).trim();
    CLICKS[key] = (CLICKS[key] || []).concat(
      spec.slice(i + 1).split('|').map((s) => s.trim()).filter(Boolean));
  }
}

// --only /technical/فولاد,/watch → برایِ حلقۀِ قبل/بعدِ یکِ اصلاح
const ONLY = (arg('only', '') || '').split(',').map((s) => s.trim()).filter(Boolean);
const ROUTES_RUN = ONLY.length ? ROUTES.filter((r) => ONLY.some((o) => r.path.startsWith(o))) : ROUTES;

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const CHROME = process.env.JEV_CHROME ?? '';

/** تنها راهِ ورود: دروازهٔ محلیِ UI — نشستِ sessionStorage، بی‌تایپِ رمز. */
const AUTH_INIT = () => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors_auth_session');
  } catch { /* پوستهٔ بی‌دروازه هم می‌پذیرد */ }
};

/**
 * هندسۀ صفحه. همه‌چیز درِ یک evaluateِ سادهٔ JS (بی‌type stripping درِ این
 * مسیر) — و همه با عدد، نه با رأی.
 */
const PROBE = (routeName: string) => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  const vh = de.clientHeight;
  const css = (el: Element) => getComputedStyle(el);
  const clipsOwn = (el: Element) => {
    const o = css(el).overflowX;
    const oy = css(el).overflowY;
    return o === 'auto' || o === 'scroll' || o === 'hidden' || oy === 'auto' || oy === 'scroll';
  };
  const idOf = (el: Element) =>
    el.getAttribute('data-testid')
    || (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '')
    || el.tagName.toLowerCase();

  // اسکرول‌بار افقیِ ناخواستهٔ بدنه/اپ‌مین: هر کسِ دیگر مجاز است
  const bodyOverflowX = de.scrollWidth - de.clientWidth;
  const bodyOverflowY = de.scrollHeight - de.clientHeight;
  const mains = Array.from(document.querySelectorAll('.app-main, main'));
  const mainOverflow = mains.map((m) => ({
    node: idOf(m),
    x: (m as HTMLElement).scrollWidth - (m as HTMLElement).clientWidth,
    y: (m as HTMLElement).scrollHeight - (m as HTMLElement).clientHeight,
    w: (m as HTMLElement).clientWidth,
    h: (m as HTMLElement).clientHeight,
  }));

  const outside: any[] = [];
  const insideScroller: any[] = [];
  const clipped: any[] = [];
  const scrollables: any[] = [];
  const seen = new Set<string>();

  const inScrollableAncestor = (el: Element) => {
    let p = el.parentElement;
    while (p && p !== document.body) {
      if (clipsOwn(p)) return idOf(p);
      p = p.parentElement;
    }
    return null;
  };

  for (const el of Array.from(document.querySelectorAll('body *'))) {
    const b = (el as HTMLElement).getBoundingClientRect();
    if (b.width === 0 && b.height === 0) continue;
    const style = css(el);
    if (style.visibility === 'hidden' || style.display === 'none'
        || Number(style.opacity) === 0) continue;
    // sr-only برایِ خواناِ صفحه‌آرام است: ۱ پیکسل و بریده — هرگز یافته نیست
    const cn = typeof el.className === 'string' ? el.className : '';
    if (/(^|\s)sr-only(\s|$)/.test(cn) || el.closest('.sr-only')) continue;
    // پوششِ کاملِ صفحۀ بلندتر از viewport «محتوایِ اسکرول‌شونده» است، نه
    // عنصرِ بیرون‌زده: پوسته `min-h-screen` عمداً قد می‌کشد.
    if (b.height > vh && b.width > vw * 0.9) continue;
    // عناصرِ کاملاً بیرونِ viewport با viewportIntersection صفر (مثلِ تبِ
    // بسته‌شده) را رد می‌کنیم؛ فقط چیزی که «کمی» بیرون زده ایراد است.
    const overRight = b.right - vw;
    const overLeft = -b.left;
    const overBottom = b.bottom - vh;
    if (overRight > 2 || overLeft > 2 || overBottom > 2) {
      const key = `${idOf(el)}#${overRight.toFixed(0)},${overBottom.toFixed(0)}`;
      if (!seen.has(key)) {
        seen.add(key);
        const rec = { node: idOf(el), overRight: Math.round(overRight),
          overLeft: Math.round(overLeft), overBottom: Math.round(overBottom),
          box: { w: Math.round(b.width), h: Math.round(b.height) },
          text: ((el.textContent || '').trim().slice(0, 40)) };
        const anc = inScrollableAncestor(el);
        if (anc) { rec.inScroller = anc; insideScroller.push(rec); } else { outside.push(rec); }
      }
    }
    // بریدگیِ متن: element خودش overflow دارد و محتوا بزرگ‌تر از جایش است
    const t = (el.textContent || '').trim();
    if (t && el.children.length === 0 && (el as HTMLElement).scrollWidth - (el as HTMLElement).clientWidth > 1
        && style.overflowX !== 'visible') {
      const key = `${idOf(el)}|${t.slice(0, 24)}`;
      if (!seen.has(key)) {
        seen.add(key);
        clipped.push({ node: idOf(el), lostPx: (el as HTMLElement).scrollWidth - (el as HTMLElement).clientWidth,
          text: t.slice(0, 48),
          box: { w: (el as HTMLElement).clientWidth, h: (el as HTMLElement).clientHeight },
          cls: (typeof el.className === 'string' ? el.className : '').slice(0, 70),
          parent: el.parentElement ? idOf(el.parentElement) : null,
          parentW: el.parentElement ? (el.parentElement as HTMLElement).clientWidth : null });
      }
    }
    if ((el as HTMLElement).scrollWidth - (el as HTMLElement).clientWidth > 2
        && (style.overflowX === 'auto' || style.overflowX === 'scroll')) {
      scrollables.push({ node: idOf(el), extra: (el as HTMLElement).scrollWidth - (el as HTMLElement).clientWidth });
    }
  }

  // اسکرولِ عمودیِ خودِ صفحه: پوسته `min-h-screen overflow-hidden` است، پس
  // صفحهٔ بلند *طرح* است. ولی چند پیکسل اضافی (اسکرولِ جعلی) یعنی چیزی از
  // ارتفاعِ viewport بیرون زده — همان چیزی که پایینِ چارت را می‌بُرد.
  const pageScroll = de.scrollHeight - de.clientHeight;
  const spuriousScroll = pageScroll > 0 && pageScroll <= 48;

  // آخرین عنصرِ دیدنیِ صفحه + آیا *واقعاً* قابلِ رسیدن است؟ پوسته `overflow-hidden`
  // است، پس محتوای بلندتر از آن بدونِ یک اسکرول‌کنندۀِ داخلی بریده و دست‌نیافتنی
  // می‌ماند. اینجا همان را با عدد می‌سنجیم: نزدیک‌ترین ancestor با overflow-y
  // قابل‌اسکرول را پیدا می‌کنیم، او را تا انتها می‌بریم و دوباره نگاه می‌کنیم.
  const nearestScroller = (el: Element) => {
    let p = el.parentElement;
    while (p && p !== document.body) {
      const oy = css(p).overflowY;
      if ((oy === 'auto' || oy === 'scroll') && p.scrollHeight > p.clientHeight + 2) return p;
      p = p.parentElement;
    }
    return null;
  };

  let lastVisible: any = null;
  {
    let best: any = null;
    for (const el of Array.from(document.querySelectorAll('main *, body > div *'))) {
      const b = (el as HTMLElement).getBoundingClientRect();
      if (b.height === 0 || b.width === 0) continue;
      const style = css(el);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const cn = typeof el.className === 'string' ? el.className : '';
      if (/(^|\s)sr-only(\s|$)/.test(cn) || el.closest('.sr-only')) continue;
      if (!best || b.bottom > best.bottom) {
        best = { el, bottom: Math.round(b.bottom), node: idOf(el),
          text: ((el.textContent || '').trim().slice(0, 36)) };
      }
    }
    if (best) {
      const sc = nearestScroller(best.el);
      let reachable = pageScroll >= 0 && best.bottom <= vh + 2;
      let how = 'درِ viewport';
      if (sc) {
        const before = sc.scrollTop;
        sc.scrollTop = sc.scrollHeight;
        const after = Math.round(best.el.getBoundingClientRect().bottom);
        const cb = sc.getBoundingClientRect();
        reachable = after <= cb.bottom + 2 && after >= cb.top - 2;
        how = `اسکرولِ داخلی (${idOf(sc)} ${Math.round(sc.scrollHeight)}/${Math.round(sc.clientHeight)})`;
        sc.scrollTop = before;
      } else if (best.bottom > vh + 2 && pageScroll > 0) {
        const top0 = document.documentElement.scrollTop;
        document.documentElement.scrollTop = document.documentElement.scrollHeight;
        window.scrollTo(0, document.body.scrollHeight);
        reachable = Math.round(best.el.getBoundingClientRect().bottom) <= vh + 2;
        how = 'اسکرولِ صفحه';
        document.documentElement.scrollTop = top0;
      } else if (best.bottom > vh + 2) {
        reachable = false;
        how = 'هیچ اسکرول‌کننده‌ای نیست — زیرِ overflow-hidden بریده می‌شود';
      }
      lastVisible = { node: best.node, bottom: best.bottom, text: best.text,
        reachable, how, clippedByShell: !reachable && best.bottom > vh };
    }
  }

  // وضعیتِ هدر هنگامِ اسکرول (sticky/fixed یا نه)
  const headerEl = document.querySelector('header, [data-testid="app-header"], [data-testid="topbar"]');
  const headerPosition = headerEl ? css(headerEl).position : null;
  const headerSticky = headerPosition === 'sticky' || headerPosition === 'fixed';

  // اسکرول تا انتها و دوباره: آیا هدر/کنترلِ ضروری می‌ماند؟
  const stickyAfterScroll: any = { scrolled: false };
  const scroller = (mains[0] && (mains[0] as HTMLElement).scrollHeight > (mains[0] as HTMLElement).clientHeight
    ? mains[0] : de);
  scroller.scrollTop = scroller.scrollHeight;
  window.scrollTo(0, document.body.scrollHeight);
  const header = document.querySelector('header, [data-testid="app-header"], [data-testid="topbar"]');
  if (header) {
    const hb = header.getBoundingClientRect();
    stickyAfterScroll.headerVisible = hb.top >= -2 && hb.bottom > 0 && hb.height > 0;
    stickyAfterScroll.headerTop = Math.round(hb.top);
  }
  stickyAfterScroll.scrollTop = Math.round(scroller.scrollTop);
  stickyAfterScroll.scrollHeight = Math.round(scroller.scrollHeight);
  stickyAfterScroll.scrolled = true;

  // شمارشِ ردیف‌ها: «۹ صفحه اسکرول» با «۲۰۰ ردیفِ رندر‌شده» وقتی یکی می‌شود که
  // فهرست سقف/اسکرولِ داخلی نداشته باشد. این عدد همان را جدا می‌کند.
  const rowCounts: Record<string, number> = {};
  for (const el of Array.from(document.querySelectorAll('[data-testid]'))) {
    const id = el.getAttribute('data-testid') || '';
    if (!/(^|-)row$/.test(id)) continue;
    rowCounts[id] = (rowCounts[id] || 0) + 1;
  }

  const sidebar = document.querySelector('[data-testid="sidebar"], aside nav, nav');
  return {
    route: routeName,
    viewport: { w: vw, h: vh, dpr: window.devicePixelRatio },
    bodyOverflowX, bodyOverflowY, pageScroll, spuriousScroll,
    lastVisible, headerPosition, headerSticky, rowCounts,
    mainOverflow,
    outside: outside.slice(0, 24),
    insideScroller: insideScroller.slice(0, 12),
    clipped: clipped.slice(0, 24),
    scrollables: scrollables.slice(0, 12),
    stickyAfterScroll,
    sidebarBox: sidebar ? (b => ({ w: Math.round(b.width), h: Math.round(b.height) }))(sidebar.getBoundingClientRect()) : null,
    title: document.title,
  };
};

/**
 * `--explain /technical` — زنجیرۀ ارتفاع از بدنه تا عنصرِ بیرون‌زده. بی‌این،
 * «۴ پیکسل اضافی» یک عددِ بی‌نشانی است؛ اینجا هر گره با clientHeight/scrollHeight،
 * margin/padding و position چاپ می‌شود تا معلوم شود آن ۴ پیکسل از کجا آمده.
 */
const EXPLAIN = (routePath: string) => {
  const de = document.documentElement;
  const vh = de.clientHeight;
  const vw = de.clientWidth;
  const idOf = (el: Element) => {
    const c = typeof el.className === 'string' ? el.className.trim().split(/\s+/).slice(0, 4).join('.') : '';
    return el.tagName.toLowerCase() + (el.getAttribute('data-testid') ? `[${el.getAttribute('data-testid')}]` : '')
      + (c ? '.' + c : '');
  };
  const out: any[] = [];
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    const b = (el as HTMLElement).getBoundingClientRect();
    if (b.height < 1) continue;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    const overBottom = b.bottom - vh;
    const selfOverflow = (el as HTMLElement).scrollHeight - (el as HTMLElement).clientHeight;
    if (overBottom <= 4 && selfOverflow <= 4) continue;  // ۴px و کمتر: نویزِ خطِ ارتفاع
    if (/(^|\s)sr-only(\s|$)/.test(s.className || '')) continue;
    out.push({ node: idOf(el).slice(0, 80), top: Math.round(b.top), bottom: Math.round(b.bottom),
      overBottom: Math.round(overBottom), clientH: (el as HTMLElement).clientHeight,
      scrollH: (el as HTMLElement).scrollHeight, w: Math.round(b.width),
      overflowY: s.overflowY, position: s.position,
      mt: s.marginTop, mb: s.marginBottom, pt: s.paddingTop, pb: s.paddingBottom,
      minH: s.minHeight, h: s.height, flex: s.flex,
      text: (el.textContent || '').trim().slice(0, 30), depth: (() => {
        let d = 0, p: Element | null = el; while ((p = p ? p.parentElement : null)) d++; return d;
      })() });
    if (out.length > 28) break;
  }
  return { routePath, viewport: { w: vw, h: vh }, docScroll: de.scrollHeight - vh, culprits: out };
};

const report: Record<string, unknown> = { base: BASE, viewports: [], generatedAt: new Date().toISOString() };
mkdirSync(SHOT_DIR, { recursive: true });

/** `--vars /technical` — متغیرهای ارتفاعِ پوسته و جایِ هر نوارِ چسبان. */
const VARS = () => {
  const de = document.documentElement;
  const ac = document.querySelector('.app-content') as HTMLElement | null;
  const main = document.querySelector('.app-main') as HTMLElement | null;
  const bar = document.querySelector('.symbol-strip-bar') as HTMLElement | null;
  const top = document.querySelector('[data-testid="topbar"], header') as HTMLElement | null;
  const cs = (el: HTMLElement | null) => (el ? getComputedStyle(el) : null);
  return {
    viewport: { w: de.clientWidth, h: de.clientHeight },
    docScroll: de.scrollHeight - de.clientHeight,
    pinnedH: ac ? cs(ac)!.getPropertyValue('--pinned-h').trim() : null,
    contentMaxW: main ? cs(main)!.getPropertyValue('--content-max-w').trim() : null,
    gutterX: main ? cs(main)!.getPropertyValue('--gutter-x').trim() : null,
    topbar: top ? { h: Math.round(top.getBoundingClientRect().height), pos: cs(top)!.position } : null,
    strip: bar ? { h: Math.round(bar.getBoundingClientRect().height), pos: cs(bar)!.position } : null,
    mainBox: main ? { top: Math.round(main.getBoundingClientRect().top),
      h: Math.round(main.getBoundingClientRect().height),
      pt: cs(main)!.paddingTop, pb: cs(main)!.paddingBottom } : null,
    // اگر فهرستی flex-1 با=min-height:0 و overflow-auto داشته باشیم، ارتفاعش
    // باید «باقی‌مانده» باشد — یک پیکسل یعنی والدِ آن قدِ مشخص ندارد.
    feed: (() => {
      const ul = document.querySelector('[data-testid="notice-list"], [data-testid="tape-scroll"], [data-testid="fts-screen-scroll"]') as HTMLElement | null;
      if (!ul) return null;
      const par = ul.parentElement as HTMLElement | null;
      return { node: ul.getAttribute('data-testid'), clientH: ul.clientHeight,
        scrollH: ul.scrollHeight, rectH: Math.round(ul.getBoundingClientRect().height),
        parentTag: par ? par.tagName.toLowerCase() : null,
        parentTestid: par ? par.getAttribute('data-testid') : null,
        parentDisplay: par ? getComputedStyle(par).display : null,
        parentDir: par ? getComputedStyle(par).flexDirection : null,
        parentClientH: par ? par.clientHeight : null,
        parentScrollH: par ? par.scrollHeight : null,
        parentHeightCss: par ? getComputedStyle(par).height : null };
    })(),
  };
};

const EXPLAIN_ROUTE = arg('explain', '');
if (EXPLAIN_ROUTE) {
  const vp = VIEWPORTS[0];
  const browser = await chromium.launch({ headless: true, executablePath: CHROME || undefined });
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  await context.addInitScript(AUTH_INIT);
  const page = await context.newPage();
  await page.goto(`${BASE}#${EXPLAIN_ROUTE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT_MS);
  const got = await page.evaluate(EXPLAIN, EXPLAIN_ROUTE);
  const vars = await page.evaluate(VARS);
  writeFileSync(OUT, JSON.stringify({ ...got, shell: vars }, null, 1));
  await page.screenshot({ path: `${SHOT_DIR}/explain-${vp.label}-${EXPLAIN_ROUTE.replace(/[^a-z0-9]+/gi, '_')}.png` });
  console.log(JSON.stringify({ shell: vars, docScroll: (got as any).docScroll }, null, 1));
  await browser.close();
  process.exit(0);
}

for (const vp of VIEWPORTS) {
  const browser = await chromium.launch({ headless: true, executablePath: CHROME || undefined });
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: 1 });
  await context.addInitScript(AUTH_INIT);
  const page = await context.newPage();
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on('console', (m: { type: () => string; text: () => string }) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200));
  });
  page.on('pageerror', (e: { message: string }) => consoleErrors.push(`pageerror: ${e.message}`.slice(0, 200)));
  page.on('requestfailed', (r: { url: () => string; failure: () => { errorText?: string } }) =>
    failedRequests.push(`${r.url().slice(0, 90)} ${r.failure()?.errorText ?? ''}`.slice(0, 140)));

  const rows: unknown[] = [];
  for (const route of ROUTES_RUN) {
    await page.goto(`${BASE}#${route.path}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(WAIT_MS);
    try {
      await page.waitForSelector(route.ready, { timeout: 6000 });
    } catch { /* آماده نشد — خودش یک یافته است */ }
    const geom = await page.evaluate(PROBE, route.name);
    const clicks: Record<string, unknown> = {};
    for (const label of (CLICKS[route.path] || [])) {
      try {
        if (label.startsWith('aria:')) {
          // بعضی کنترل‌ها فقط aria-label دارند (متنِ دیدنی ندارند)
          await page.getByLabel(label.slice(5), { exact: false }).locator('visible=true')
            .first().click({ timeout: 6000 });
        } else {
        const byTitle = page.locator(`[title="${label}"] >> visible=true`).first();
        if (await byTitle.count()) {
          await byTitle.click({ timeout: 6000 });
        } else {
          // فقط عنصرِ دیدنی: «اولین»ِ match اغلب گرهی درِ پنلِ بسته است و
          // کلیکِ آن بی‌صدا timeout می‌شود (دیده شد).
          await page.getByText(label, { exact: false }).locator('visible=true').first()
            .click({ timeout: 6000 });
        }
        }
        await page.waitForTimeout(1500);
        clicks[label] = { opened: true, after: await page.evaluate(PROBE, `${route.name} ← ${label}`) };
        await page.keyboard.press('Escape');
        await page.waitForTimeout(600);
      } catch (e) {
        clicks[label] = { opened: false, error: (e as Error).message.slice(0, 120) };
      }
    }
    const shot = `${SHOT_DIR}/${vp.label.replace('x', '×')}-${route.path.replace(/[^a-z0-9]+/gi, '_') || 'root'}.png`;
    await page.screenshot({ path: shot, fullPage: false });
    rows.push({ path: route.path, name: route.name, shot, geom, clicks });
    console.log(`  ${vp.label} ${route.path} → overflowX=${(geom as any).bodyOverflowX}`
      + ` outside=${(geom as any).outside.length} clipped=${(geom as any).clipped.length}`);
  }
  await browser.close();
  report.viewports!.push({ viewport: vp.label, consoleErrors: consoleErrors.slice(0, 10),
    failedRequests: failedRequests.slice(0, 10), rows });
}

writeFileSync(OUT, JSON.stringify(report, null, 1));
console.log(`written: ${OUT}`);
