// tools/uiux_route_probe.mts — سنجۀِ زندۀِ روت‌ها: شلوغی، ارتفاعِ نوارِ بالا، و بازگشت/بعدی
//
// چرا: بندِ B مأموریت می‌گوید هر ادعایِ «شلوغ است» باید شاهدِ اندازه‌گیری‌شده
// داشته باشد، نه قضاوتِ متنی؛ بندِ A هم می‌خواهد بدیم که دو کنترلِ تازه هیچ
// ارتفاعی به نوارِ بالا نیفزود و درِ عرضِ کم عنوانِ مسیر را نمی‌خورد. این فایل
// پس برایِ هر روت، درِ هر دو حالتِ نماد، اندازه می‌گیرد و اسکرین‌شات می‌گذارد؛
// رأیِ «حذف/جمع/نگه» باِ مالک است، اینِ فایل فقط عدد می‌دهد.
//
// دو حالتِ نماد چرا جدا: `SymbolContextStrip` باِ «نمادِ استور» می‌آید و ارتفاعِ
// چسبانِ بالایِ صفحه را عوض می‌کند (`--pinned-h`). بی‌اندازه‌گیریِ هر دو حالت،
// «صفحه جا کم دارد» نصفه‌کاره سنجیده می‌شود.
//
// اجرا:  npx tsx tools/uiux_route_probe.mts <BASE> <tag>
//        npx tsx tools/uiux_route_probe.mts http://127.0.0.1:8010/ before
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8010/';
const TAG = process.argv[3] || 'before';
const OUT = process.env.JEV_OUT_DIR
  || 'C:/Users/PCMOD/Desktop/_bors-uiux-nav/_audit/uiux-nav';
mkdirSync(OUT, { recursive: true });

/** هر روتِ ثبت‌شدۀِ `frontend/src/routes.tsx` — فهرست ازِ خودِ فایلِ routeها
 *  گرفته شده، نه ازِ نوارِ ناوبری (روتِ بی‌پیوند هم باید سنجیده شود). */
const ROUTES: Array<[string, string, string]> = [
  ['#/', 'صفحهٔ نخست (redirect به /master)', 'routes.tsx (index)'],
  ['#/market', 'تابلوخوانی', 'features/market/routes/MarketPage'],
  ['#/market-status', 'وضعیت بازار', 'features/market/routes/MarketStatusPage'],
  ['#/watch', 'دیده‌بان بازار', 'features/portfolio/components/WatchMarketWorkspace'],
  ['#/technical/فولاد', 'تحلیل تکنیکال', 'features/technical/routes/TechnicalPage'],
  ['#/fundamental/فولاد', 'تحلیل بنیادی', 'features/fundamental/routes/FundamentalPage'],
  ['#/portfolio/فولاد', 'مدیریت پرتفوی', 'features/portfolio/routes/PortfolioPage'],
  ['#/master', 'غربالگری FTS', 'features/master/routes/MasterPage'],
  ['#/master/فولاد', 'غربالگری FTS · نماد', 'features/master/routes/MasterPage'],
  ['#/strategy-tree/فولاد', 'درخت استراتژی FTS', 'features/master/routes/StrategyTreePage'],
  ['#/sarkhati', 'سرخطی', 'features/portfolio/routes/SarkhatiPage'],
  ['#/notifications', 'مرکزِ اعلان', 'features/market/routes/NotificationsPage'],
  ['#/engine-lab', 'آزمایشگاهِ موتور', 'features/technical/engine-lab/EngineLabPage'],
  ['#/nope-not-a-route', 'نشانیِ ثبت‌نشده', 'routes.tsx (fallback *)'],
];

// ۱۳۶۶×۷۶۸ کفِ مأموریت؛ ۱۶۰۰×۹۰۰ وِ ۱۹۲۰×۱۰۸۰ دسکتاپِ واقعی؛ ۱۲۸۰×۷۲۰ اضافه
const VIEWS: Array<[number, number]> = [[1366, 768], [1600, 900], [1920, 1080], [1280, 720]];
const SYM = 'فولاد';

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

type Run = Record<string, unknown>;
const report: { base: string; tag: string; runs: Run[] } = { base: BASE, tag: TAG, runs: [] };

function slug(s: string): string {
  return s.replace(/^#\//, '').replace(/[^\w\u0600-\u06FF-]+/g, '_').slice(0, 34) || 'root';
}

// برایِ گرفتنِ فقط یک روت (مثلاً روتِ ریدایرکتِ «#/» که در پیمایشِ کامل هم می‌آید)
const ONLY = (process.env.PROBE_ONLY || '').split(',').map((s) => s.trim()).filter(Boolean);
const ROWS = ONLY.length ? ROUTES.filter(([href]) => ONLY.includes(slug(href))) : ROUTES;

for (const [href, label, file] of ROWS) {
  for (const state of ['nosym', 'sym'] as const) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    await ctx.addInitScript(([st, sym]) => {
      try {
        sessionStorage.setItem('bors_auth_session', 'true');
        if (st === 'sym') localStorage.setItem('bors-symbol', sym);
        else localStorage.removeItem('bors-symbol');
      } catch { /* noop */ }
    }, [state, SYM] as [string, string]);
    const page = await ctx.newPage();
    const errors: string[] = [];
    const bad: string[] = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 180)); });
    page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 180)));
    page.on('response', (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url().slice(0, 110)}`); });

    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.evaluate((h) => { window.location.hash = h.slice(1); }, href);
    await page.waitForTimeout(3200);            // chunk تنبل + queryها

    const perView: Run[] = [];
    for (const [w, h] of VIEWS) {
      await page.setViewportSize({ width: w, height: h });
      await page.waitForTimeout(900);
      const m = await page.evaluate(() => {
        const vis = (el: Element) => {
          const r = el.getBoundingClientRect();
          const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.opacity !== '0';
        };
        const bar = document.querySelector('[data-pinned="topbar"]');
        const strip = document.querySelector('[data-testid="symbol-strip"]')
          || document.querySelector('.symbol-strip-bar');
        const cs = getComputedStyle(document.querySelector('.app-content') || document.documentElement);
        const all = Array.from(document.querySelectorAll('button, a[href], input, select, [role="tab"], [role="menuitem"]'));
        const inVP = all.filter((e) => {
          const r = e.getBoundingClientRect();
          return vis(e) && r.top < window.innerHeight && r.bottom > 0;
        });
        const secs = Array.from(document.querySelectorAll('main section, main [data-shell]'))
          .filter(vis)
          .map((s) => {
            const r = s.getBoundingClientRect();
            const hd = s.querySelector('h1,h2,h3,h4');
            return { top: Math.round(r.top + window.scrollY), h: Math.round(r.height),
              label: (hd ? hd.textContent : s.getAttribute('data-shell') || s.tagName || '').trim().slice(0, 40) };
          });
        const title = document.querySelector('[data-pinned="topbar"] nav a');
        const titleW = title ? Math.round(title.getBoundingClientRect().width) : 0;
        const scrollable = document.querySelector('.app-content');
        return {
          viewport: { w: window.innerWidth, h: window.innerHeight },
          topbarHeight: bar ? Math.round(bar.getBoundingClientRect().height) : null,
          stripPresent: !!strip,
          stripHeight: strip ? Math.round(strip.getBoundingClientRect().height) : null,
          pinnedH: (cs.getPropertyValue('--pinned-h') || '').trim(),
          controlsTotal: all.length,
          controlsInView: inVP.length,
          sections: secs.length,
          sectionList: secs.slice(0, 14),
          belowFoldPx: scrollable ? Math.max(0, Math.round(scrollable.scrollHeight - scrollable.clientHeight)) : 0,
          hOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          titleText: title ? (title.textContent || '').trim().slice(0, 30) : null,
          titleWidthPx: titleW,
          navBack: (() => {
            const b = document.querySelector('[data-testid="nav-back"]');
            return b ? { present: true, disabled: !(b instanceof HTMLButtonElement) || b.disabled,
              label: b.getAttribute('aria-label') } : { present: false };
          })(),
          navForward: (() => {
            const b = document.querySelector('[data-testid="nav-forward"]');
            return b ? { present: true, disabled: !(b instanceof HTMLButtonElement) || b.disabled,
              label: b.getAttribute('aria-label') } : { present: false };
          })(),
          pageTextChars: (document.querySelector('main')?.innerText || '').length,
        };
      });
      const name = `${TAG}__${slug(href)}__${w}x${h}__${state}.png`;
      await page.screenshot({ path: `${OUT}/${name}` });
      perView.push({ viewport: `${w}x${h}`, ...m, screenshot: name });
    }

    report.runs.push({ href, label, file, state, views: perView,
      consoleErrors: Array.from(new Set(errors)).slice(0, 8),
      badResponses: Array.from(new Set(bad)).slice(0, 8) });
    await ctx.close();
  }
}

// ── بندِ A درِ مرورگرِ واقعی: تاریخچۀِ درونِ برنامه باِ back/forwardِ خودِ مرورگر هم‌خوان می‌ماند
{
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript(() => {
    try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 180)); });
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + String(e).slice(0, 180)));
  await page.goto(`${BASE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  const seq: string[] = [];
  const read = async () => await page.evaluate(() => {
    const b = document.querySelector('[data-testid="nav-back"]');
    const f = document.querySelector('[data-testid="nav-forward"]');
    const bar = document.querySelector('[data-pinned="topbar"]');
    let hash = window.location.hash;
    try { hash = decodeURIComponent(hash); } catch { /* بی‌خطر: همان خام می‌ماند */ }
    return {
      hash,
      back: b ? ((b instanceof HTMLButtonElement && b.disabled) ? 'off' : 'on') : 'absent',
      fwd: f ? ((f instanceof HTMLButtonElement && f.disabled) ? 'off' : 'on') : 'absent',
      barH: bar ? Math.round(bar.getBoundingClientRect().height) : null,
    };
  });
  const step = async (label: string) => { const s = await read(); seq.push(`${label} ⇒ ${s.hash} back=${s.back} fwd=${s.fwd} bar=${s.barH}`); return s; };

  await page.evaluate(() => { window.location.hash = '/market'; });
  await page.waitForTimeout(1800); await step('رفتن به #/market');
  await page.evaluate(() => { window.location.hash = '/technical/فولاد'; });
  await page.waitForTimeout(2200); await step('رفتن به #/technical/فولاد');
  await page.evaluate(() => { window.location.hash = '/notifications'; });
  await page.waitForTimeout(1800); await step('رفتن به #/notifications');
  // درِ بستۀِ پایه (پیش از تغییر) این دکمه‌ها وجود ندارند؛ نبودشان خطا نیست،
  // خودش شاهدِ «قبل» است. کلیک فقط وقتی انجام می‌شود که دکمه دیده شود.
  const clickIf = async (testid: string) => {
    const loc = page.locator(`[data-testid="${testid}"]`);
    if (await loc.count() === 0) return false;
    await loc.click({ timeout: 5000 }).catch(() => {});
    return true;
  };
  const focusOf = async () => await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    return { testid: el?.getAttribute('data-testid') ?? null, tag: el?.tagName ?? null };
  });
  const b1 = await clickIf('nav-back'); await page.waitForTimeout(1800);
  seq.push(`کلیکِ بازگشت${b1 ? '' : ' (دکمه غایب بود)'} ⇒ ${(await read()).hash}`);
  const focusAfterBack = await focusOf();
  await page.keyboard.press('Tab');
  const focusAfterTab = await focusOf();
  const b2 = await clickIf('nav-back'); await page.waitForTimeout(1800);
  seq.push(`کلیکِ بازگشتِ دوباره${b2 ? '' : ' (دکمه غایب بود)'} ⇒ ${(await read()).hash}`);
  const f1 = await clickIf('nav-forward'); await page.waitForTimeout(1500);
  seq.push(`کلیکِ بعدی${f1 ? '' : ' (دکمه غایب بود)'} ⇒ ${(await read()).hash}`);
  await page.goBack(); await page.waitForTimeout(1500); await step('backِ خودِ مرورگر');
  await page.goForward(); await page.waitForTimeout(1500); await step('forwardِ خودِ مرورگر');
  // درِ عرضِ کم، عنوانِ مسیر نباید زیرِ دکمه‌ها له شود
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(900);
  const narrow = await page.evaluate(() => {
    const t = document.querySelector('[data-pinned="topbar"] nav a');
    const r = t ? t.getBoundingClientRect() : null;
    const bb = document.querySelector('[data-testid="nav-back"]');
    return { titleW: r ? Math.round(r.width) : null, titleText: t ? (t.textContent || '').trim() : null,
      backRect: bb ? Math.round(bb.getBoundingClientRect().width) : null };
  });
  await page.screenshot({ path: `${OUT}/${TAG}__narrow390__topbar.png` });
  report.runs.push({ href: 'NAV-SEQUENCE', label: 'بندِ A زنده', views: seq, narrow390: narrow,
    focusAfterBack, focusAfterTab,
    consoleErrors: Array.from(new Set(errors)).slice(0, 8) });
  await ctx.close();
}

// ── شروعِ سرد با نشانیِ مستقیم: دکمه‌ها نباید تاریخچۀِ ساختگی نشان دهند
{
  const cold: string[] = [];
  // هر نشانی در بافتِ تازه: goto با هشِ متفاوت در همان سند، ناوبریِ درون‌برنامه‌ای
  // است و تاریخچهٔ نشانیِ قبلی را به ارث می‌برد؛ آن دیگر «شروعِ سرد» نیست.
  for (const url of [`${BASE}#/technical/فولاد`, `${BASE}#/market`, `${BASE}`]) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    await ctx.addInitScript(() => {
      try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* noop */ }
    });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2600);
    const st = await page.evaluate(() => {
      const b = document.querySelector('[data-testid="nav-back"]');
      const f = document.querySelector('[data-testid="nav-forward"]');
      const hash = window.location.hash;
      const before = hash;
      if (b instanceof HTMLButtonElement) b.click();
      const after = window.location.hash;
      return { url: location.href, hash,
        back: b instanceof HTMLButtonElement ? (b.disabled ? 'off' : 'on') : 'absent',
        fwd: f instanceof HTMLButtonElement ? (f.disabled ? 'off' : 'on') : 'absent',
        disabledClickMoved: before !== after };
    });
    cold.push(`${url} ⇒ ${st.hash} back=${st.back} fwd=${st.fwd} disabledClickMoved=${st.disabledClickMoved}`);
    await ctx.close();
  }
  report.runs.push({ href: 'COLD-START', label: 'شروعِ سرد', views: cold });
}

await browser.close();
writeFileSync(`${OUT}/${TAG}-routes.json`, JSON.stringify(report, null, 2), 'utf-8');
const lines = (report.runs as Array<Record<string, unknown>>).map((r) => {
  const v = (r.views as Array<Record<string, unknown>> | undefined) ?? [];
  if (typeof v[0] === 'string') return `${String(r.href)}\n  ${v.join('\n  ')}`;
  return `${String(r.href)} [${String(r.state)}] ` + v.map((x) => {
    const vp = x.viewport as { w?: number; h?: number } | string;
    const vpText = typeof vp === 'string' ? vp : `${vp?.w}x${vp?.h}`;
    return `${vpText} bar=${x.topbarHeight} strip=${x.stripHeight ?? '-'} pin=${x.pinnedH || '-'} ctl=${x.controlsInView}/${x.controlsTotal} fold=${x.belowFoldPx} ovf=${x.hOverflow} nav=${(x.navBack as Record<string, unknown>).present ? 'yes' : 'no'}`;
  }).join(' | ');
});
console.log(`probe done: ${OUT}/${TAG}-routes.json`);
console.log(lines.join('\n'));
