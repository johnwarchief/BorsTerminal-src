// _audit/ui/interact_audit.js — آزمونِ تعاملِ واقعیِ هرِ سطح (باز کردن ↔ بستن)
//
// مرحلۀِ ۳D مأموریت: «مودال‌ها، درُورها و منوها واقعاً باز و بسته شوند؛ فوکوس و
// Escape کار کند». اینِ جاروب باِ فهرستِ قدم‌هایِ اعلامی، هرِ تعامل را انجام
// می‌دهد و می‌سنجد:
//   · باز شد؟ (شمارِ لایه + دیده‌شدنِ آن درِ viewport هدف)
//   · کاملِ کامل درِ viewport است؟ (بیرون‌زدگی px از هرِ سو + بریدگیِ ancestor)
//   · فوکوس داخلِ لایه نشست؟ (activeElement)
//   · بسته شد؟ (Escape یا دکمۀِ بستنِ خودش) و بعدِ بستن، بی‌اثر/پنهان است؟
//   · سرریزِ افقیِ صفحه و خطاهایِ کنسول بعدِ قدم، نسبتِ بهِ قبلش
// هیچِ قدمی سفارشِ واقعی نمی‌فرستد و هیچِ دکمۀِ «نصبِ آپدیت / پاک‌کردنِ تاریخچه /
// علامت‌زدنِ همه» فشرده نمی‌شود (اینها داده را عوض می‌کنند).
//
// usage (بک‌اندِ worktree رویِ :8000):
//   MSYS_NO_PATHCONV=1 node _audit/ui/interact_audit.js --only=market
//   node _audit/ui/interact_audit.js --out=INTERACT.json --shots=_audit/ui/shots/int
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const h = argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'INTERACT.json'));
const SHOTS = arg('shots', '_audit/ui/shots/int');
const ONLY = arg('only', '');
const WAIT = Number(arg('settle', 1500));
const TRIGGER_WAIT = Number(arg('trigger-wait', 20000));

// k=کلیدِ ماژول، r=route، n=نامِ قدم، act=click|keys|select|none، t=هدفِ CSS،
// v=مقدارِ select/keys، exp=لایۀِ انتظار، close=escape|css|null، back=بازگشتِ حالت
const STEPS = [
  // ── تابلوخوانی ────────────────────────────────────────────────────────────
  { k: 'market', r: '/market', n: 'فیلترِ دارایی (منو)', kind: 'overlay', act: 'click', t: '[data-testid="asset-filter"] button', exp: '[data-testid="asset-filter-menu"]', close: '[data-testid="asset-filter"] button' },
  { k: 'market', r: '/market', n: 'منطقِ غربالگری (توگل)', kind: 'toggle', act: 'click', t: '[data-testid="screen-logic-toggle"]', exp: '[data-testid="screen-logic-toggle"]', close: '[data-testid="screen-logic-toggle"]' },
  { k: 'market', r: '/market', n: 'فقط زنده (توگل)', kind: 'toggle', act: 'click', t: '[data-testid="live-only-toggle"]', exp: '[data-testid="live-only-toggle"]', close: '[data-testid="live-only-toggle"]' },
  { k: 'market', r: '/market', n: 'پسوندِ عددی (توگل)', kind: 'toggle', act: 'click', t: '[data-testid="numeric-suffix-toggle"]', exp: '[data-testid="numeric-suffix-toggle"]', close: '[data-testid="numeric-suffix-toggle"]' },
  { k: 'market', r: '/market', n: 'چیپِ سریعِ فیلتر', kind: 'toggle', act: 'click', t: '[data-testid="quick-filters-bar"] button', exp: '[data-testid="tape-scroll"]', close: '[data-testid="quick-filters-bar"] button' },
  { k: 'market', r: '/market', n: 'ردیفِ تابلو → داورِ نماد', kind: 'overlay', act: 'click', t: '[data-testid="tape-row"]', exp: '[data-testid="inspector-tabs"]', close: 'escape' },

  // ── وضعیت بازار ───────────────────────────────────────────────────────────
  { k: 'market-status', r: '/market-status', n: 'توگلِ چرخشِ تیکر', kind: 'toggle', act: 'click', t: '[data-testid="ticker-mode-toggle"]', exp: '[data-testid="ticker-continuous"]', close: '[data-testid="ticker-mode-toggle"]' },
  { k: 'market-status', r: '/market-status', n: 'زیرتبِ طلا (۲)', act: 'click', t: '[data-testid="ms-gold-tabs"] [data-testid^="ms-gold-tab-"]:nth-child(2)', exp: '[data-testid^="ms-gold-tab-"]', close: '[data-testid="ms-gold-tabs"] [data-testid^="ms-gold-tab-"]:nth-child(1)' },
  { k: 'market-status', r: '/market-status', n: 'معیارِ دوناتِ طلا', kind: 'toggle', act: 'click', t: '[data-testid="ms-gold-donut-metric-cap"]', exp: '[data-testid="ms-gold-donut-coverage"]', pre: '[data-testid="ms-gold-tab-overview"]', close: null },
  { k: 'market-status', r: '/market-status', n: 'صفحه‌بندیِ کارت‌هایِ نمایِ کلی', kind: 'panel', act: 'click', t: '[data-testid="ms-glance-next"]', exp: '[data-testid="ms-glance-page"]', close: '[data-testid="ms-glance-prev"]' },
  { k: 'market-status', r: '/market-status', n: 'بازهٔ مقایسه', kind: 'toggle', act: 'click', t: '[data-testid="ms-compare-range-1m"]', exp: '[data-testid="ms-compare-span"]', close: null },
  { k: 'market-status', r: '/market-status', n: 'انتخابِ نمادِ نمودار', kind: 'panel', act: 'click', t: '[data-testid^="ms-chart-board-list-row-"]', exp: '[data-testid="ms-chart-symbol"]', close: null },

  // ── تکنیکال ────────────────────────────────────────────────────────────────
  { k: 'technical', r: '/technical/فولاد', n: 'دیالوگِ تنظیماتِ چارت (۶ تب)', act: 'click', t: '[data-testid="open-chart-settings"]', exp: '[data-testid="chart-settings"]', close: '[data-testid="chart-settings-close"]' },
  { k: 'technical', r: '/technical/فولاد', n: 'تبِ دومِ تنظیماتِ چارت', act: 'click', t: '[data-testid="chart-settings"] [data-testid^="settings-tab-"]:nth-child(2)', kind: 'toggle', exp: '[data-testid^="settings-tab-"]', close: '[data-testid="chart-settings-close"]', pre: '[data-testid="open-chart-settings"]' },
  { k: 'technical', r: '/technical/فولاد', n: 'تغییرِ تایم‌فریم → هفتگی', act: 'click', t: '[data-testid^="timeframe-"]:nth-child(2)', kind: 'toggle', exp: '[data-testid^="timeframe-"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'بازگشتِ تایم‌فریم → روزانه', act: 'click', t: '[data-testid^="timeframe-"]:nth-child(1)', kind: 'toggle', exp: '[data-testid^="timeframe-"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'منویِ موتورِ چارت', act: 'click', t: '[data-testid="nn-engine-ffc"]', kind: 'toggle', exp: '[data-testid="ffc-chart-host"], [data-testid="fts-engine-back"]', close: '[data-testid="fts-engine-back"]' },
  { k: 'technical', r: '/technical/فولاد', n: 'جمع‌کردنِ داکِ FTS', act: 'click', t: '[data-testid="fts-dock-toggle"]', exp: '[data-testid="fts-dock"]', close: '[data-testid="fts-dock-toggle"]' },
  { k: 'technical', r: '/technical/فولاد', n: 'تبِ دومِ داکِ FTS', act: 'click', t: '[data-testid="fts-dock-tab-technical"], [data-testid^="fts-dock-tab-"]:nth-child(2)', exp: '[data-testid="fts-dock-body"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'تبِ سومِ داکِ FTS', act: 'click', t: '[data-testid^="fts-dock-tab-"]:nth-child(3)', exp: '[data-testid="fts-dock-body"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'rail سایدبار: کتاب', act: 'click', t: '[data-testid="sidebar-tab-book"]', exp: '[data-testid="sidebar-body"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'rail سایدبار: سطوح', act: 'click', t: '[data-testid="sidebar-tab-levels"]', exp: '[data-testid="sidebar-body"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'rail سایدبار: watch', act: 'click', t: '[data-testid="sidebar-tab-watch"]', exp: '[data-testid="sidebar-body"]', close: null },
  { k: 'technical', r: '/technical/فولاد', n: 'جمع‌کردنِ سایدبار', kind: 'panel', act: 'click', t: '[data-testid="sidebar-collapse"]', exp: '[data-testid="technical-sidebar-collapsed"]', close: '[data-testid="sidebar-expand"]' },

  // ── بنیادی / غربالگری ──────────────────────────────────────────────────────
  { k: 'master', r: '/master/فولاد', n: 'مودالِ تحلیل‌گر FTS', act: 'click', t: '[data-testid="fts-analyst-open"]', exp: '[data-testid="fts-analyst-modal"]', pre: '[data-testid="master-toggle-advanced"]', close: 'escape' },
  { k: 'fundamental', r: '/fundamental', n: 'پری‌ستِ استراتژیک', kind: 'toggle', act: 'click', t: '[data-testid="fts-strategic-presets"] button:nth-child(3)', exp: '[data-testid="fts-screen-row"]', pre: 'aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]', close: '[data-testid="fts-strategic-presets"] button:nth-child(2)' },
  { k: 'fundamental', r: '/fundamental', n: 'جست‌وجویِ غربالگری', kind: 'panel', act: 'type', t: '[data-testid="fts-search"]', v: 'فولاد', exp: '[data-testid="fts-screen-row"]', pre: 'aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]', close: '[data-testid="fts-search-clear"]' },
  { k: 'fundamental', r: '/fundamental', n: 'پنلِ تنظیماتِ داده', act: 'click', t: '[data-testid="fts-settings-trigger"]', exp: '[data-testid="fts-settings-panel"]', close: '[data-testid="fts-settings-backdrop"]' },

  // ── مستر FTS ───────────────────────────────────────────────────────────────
  { k: 'master', r: '/master', n: 'مودِ نوسان‌گیر', kind: 'toggle', act: 'click', t: '[data-testid="funnel-mode-swing"]', exp: '[data-testid="funnel-counts"]', pre: 'aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]', close: '[data-testid="funnel-mode-trend"]' },
  { k: 'master', r: '/master', n: 'مودِ روندگیر', kind: 'toggle', act: 'click', t: '[data-testid="funnel-mode-trend"]', exp: '[data-testid="funnel-counts"]', pre: 'aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]', close: null },
  { k: 'master', r: '/master', n: 'گامِ ۲ فرایند', kind: 'panel', act: 'click', t: '[data-testid="fts-step-technical"]', exp: '[data-testid="funnel-stage-technical"]', pre: 'aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]', close: '[data-testid="fts-step-tape"]' },
  { k: 'master', r: '/master/فولاد', n: 'جزئیاتِ FTS درِ دосьیه', act: 'click', t: '[data-testid="dossier-tech-details"] summary', exp: '[data-testid="master-fts-details"]', close: null },

  // ── درخت استراتژی ──────────────────────────────────────────────────────────
  { k: 'strategy-tree', r: '/strategy-tree', n: 'rail → T تکنیکال', act: 'click', t: '[data-testid="strategy-tree-stepper"] > div > div:nth-child(2) > a', kind: 'toggle', exp: '[data-testid="strategy-tree-stepper"] a[aria-current]', close: '[data-testid="strategy-tree-stepper"] > div > div:first-child > a' },
  { k: 'strategy-tree', r: '/strategy-tree?page=', n: 'زونِ F درِ نقشه', act: 'click', t: '[data-testid="strategy-roadmap-zones"] a', exp: '[data-testid^="strategy-tree-page-"]', close: null },

  // ── پرتفوی / دیده‌بان / اطلاعیه‌ها / آزمایشگاه ─────────────────────────────
  { k: 'portfolio', r: '/portfolio', n: 'تازه‌سازیِ واچ‌لیست (نمایِ فعلی)', kind: 'panel', act: 'click', t: '[data-testid="portfolio-watchlist-refresh"]', exp: '[data-testid="portfolio-watchlist"]', pre: '[data-testid="portfolio-view-current"]', close: null },
  { k: 'watch', r: '/watch', n: 'پیشنهادِ نماد (بدونِ افزودن)', act: 'type', t: '[data-testid="watch-add-input"]', v: 'فولاد', exp: '[data-testid="watch-add-suggestions"]', close: null },
  { k: 'notifications', r: '/notifications', n: 'فیلترِ سطحِ بالا', act: 'click', t: '[data-testid="notice-level-high"]', exp: '[data-testid="notice-list"]', close: '[data-testid="notice-filters"] button:first-child' },
  { k: 'notifications', r: '/notifications', n: 'فیلترِ نوعِ اطلاعیه', kind: 'toggle', act: 'click', t: '[data-testid="notice-kind-capital"]', exp: '[data-testid="notice-list"]', close: '[data-testid="notice-kind-capital"]' },
  { k: 'notifications', r: '/notifications', n: 'منبعِ کدال', act: 'click', t: '[data-testid="notice-source-name"]', exp: '[data-testid="notice-sources"]', close: null },
  { k: 'engine-lab', r: '/engine-lab', n: 'اندازۀِ klinecharts', act: 'click', t: '[data-testid="lab-measure-klinecharts"]', exp: '[data-testid="engine-lab"]', close: null },
  { k: 'engine-lab', r: '/engine-lab', n: 'مقایسهٔ دوِ موتور', act: 'click', t: '[data-testid="lab-compare"]', exp: '[data-testid="engine-lab"]', close: null },

  // ── لایه‌هایِ سراسری ───────────────────────────────────────────────────────
  { k: 'global', r: '/market', n: 'پالتِ فرمان (Ctrl+K)', act: 'keys', t: 'body', v: 'Control+k', exp: '[data-testid="command-palette"], [role="dialog"]', close: 'escape' },
  { k: 'global', r: '/market', n: 'تنظیماتِ کاربر', act: 'click', t: '[data-testid="user-settings-btn"]', exp: '[role="dialog"]', close: 'escape' },
  { k: 'global', r: '/market', n: 'مدیرِ آپدیت (فقطِ نمایش)', act: 'click', t: '[data-testid="app-update-btn"]', exp: '[role="dialog"]', close: 'escape' },
  { k: 'technical', r: '/technical/فولاد', n: 'زنگِ هشدارِ قیمتی', act: 'click', t: '[data-testid="price-alert-bell"]', exp: '[data-testid="price-alerts-panel"]', close: '[data-testid="price-alert-bell"]' },
];

// kind: overlay = لایه‌ای که باید باز و بسته شود (مودال/درُور/منو)
//       toggle = دکمۀِ state‌دار که باِ کلیکِ دوم برمی‌گردد
//       panel  = تغییرِ محتوایِ یکِ ناحیه (تب/زیرتب) — «بستن» ندارد
const STATE_FN = ({ sel, probeSel }) => {
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const sc = document.querySelector('.app-content') || document.scrollingElement;
  const reach = (el) => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2) return true;
      if (/(auto|scroll)/.test(cs.overflowX) && p.scrollWidth > p.clientWidth + 2) return true;
    }
    return false;
  };
  const els = sel ? [...document.querySelectorAll(sel)].filter(vis) : [];
  const boxes = els.map((el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  });
  const vw = window.innerWidth, vh = window.innerHeight;
  const probe = probeSel ? (document.querySelector(probeSel) || null) : null;
  const outside = boxes.map((b) => ({
    left: Math.max(0, -b.x), top: Math.max(0, -b.y),
    right: Math.max(0, b.x + b.w - vw), bottom: Math.max(0, b.y + b.h - vh),
  })).filter((o) => o.left + o.top + o.right + o.bottom > 2);
  const inHidden = (el) => {
    for (let p = el; p; p = p.parentElement)
      if (p.getAttribute && (p.getAttribute('aria-hidden') === 'true' || p.hasAttribute('inert'))) return true;
    return false;
  };
  const ae = document.activeElement;
  // DOMRect خواصش width/height است نه w/h؛ ازِ همانِ جعبۀِ نگاشت‌شده استفاده می‌کنیم
  const inView = (b) => b && b.x < vw - 2 && b.y < vh - 2 && b.x + b.w > 2 && b.y + b.h > 2;
  const first = els[0];
  let blocked = null;
  if (first && probe) {
    const r = first.getBoundingClientRect();
    const cx = Math.round(r.x + Math.min(r.width / 2, r.width - 6));
    const cy = Math.round(r.y + Math.min(r.height / 2, r.height - 6));
    const hit = document.elementFromPoint(cx, cy);
    if (hit && hit !== first && !first.contains(hit) && !hit.contains(first)) {
      blocked = (hit.getAttribute('data-testid') || hit.id || hit.tagName.toLowerCase()) + ' «' + String(hit.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30) + '»';
    }
  }
  const state = (el) => (el ? [el.getAttribute('aria-pressed'), el.getAttribute('aria-expanded'), el.getAttribute('data-state'),
    el.getAttribute('aria-checked'), el.getAttribute('aria-current'), String(el.className).slice(0, 120)].filter((x) => x !== null).join('|') : null);
  return {
    count: els.length,
    visibleInViewport: boxes.filter(inView).length,
    probeState: state(probe),
    probeDisabled: probe ? !!probe.disabled || probe.getAttribute('aria-disabled') === 'true' || getComputedStyle(probe).pointerEvents === 'none' : null,
    probeTitle: probe ? String(probe.getAttribute('title') || '').slice(0, 90) : null,
    blocked,
    notReachable: els.filter((el) => !reach(el)).length,
    inertOpen: els.filter(inHidden).length,
    boxes: boxes.slice(0, 3),
    outside: outside.slice(0, 3),
    overflowX: document.documentElement.scrollWidth - vw,
    scrollTop: Math.round(sc.scrollTop),
    focus: ae ? (ae.getAttribute('data-testid') || ae.id || ae.tagName.toLowerCase() + (ae.className ? '.' + String(ae.className).split(' ')[0] : '')) : null,
    focusInLayer: !!(ae && els.length && els.some((el) => el === ae || el.contains(ae))),
    sig: els[0] ? String(els[0].innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70) : '',
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }

  fs.mkdirSync(path.join(REPO, SHOTS), { recursive: true });
  const onlyKeys = ONLY ? ONLY.split(',').map((x) => x.trim()) : null;
  const steps = onlyKeys ? STEPS.filter((s) => onlyKeys.includes(s.k)) : STEPS;
  const out = { ranAt: new Date().toISOString(), viewport: { W, H }, steps: [] };
  let lastRoute = null;
  for (const s of steps) {
    let symbolCleared = false;
    if (s.r !== lastRoute) {
      // «نمادِ انتخابی» درِ این اپ حالتِ سراسری است (عمدی). قدم‌هایی که نمادِ
      // خودِ route ندارند (قیف، پرتفوی، درخت) باید بی‌نماد شروع شوند، وگرنه
      // صفحهٔ بعدی دوسيهِ نمادِ قبلی را می‌نشاند و دستگیره‌هایِ درست رسم نمی‌شوند.
      if (!/(?:^|\/)(?:technical|master)\/[^/]/.test(s.r)) {
        const clear = page.locator('aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]');
        if (await clear.count().catch(() => 0)) {
          await clear.first().click({ timeout: 4000 }).catch(() => {});
          await page.waitForTimeout(900);
          symbolCleared = true;
        }
      }
      await page.goto(BASE + '/#' + s.r, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(s.r.startsWith('/master') || s.r.startsWith('/technical') ? 6000 : 3200);
      lastRoute = s.r;
    }
    const rec = { key: s.k, route: s.r, name: s.n, act: s.act, target: s.t, expect: s.exp, kind: s.kind || 'auto' };
    if (symbolCleared) rec.symbolCleared = true;
    // ۱) پیش‌شرط (بازکردنِ لایه/تب) *اول* انجام می‌شود: چهاردهِ گام درِ دورِ پیشین
    //    «NO-TRIGGER» خوانده می‌شدند چون دستگیره فقط پس ازِ کلیکِ پیش‌شرط درِ DOM
    //    می‌آید وِ شمارش، پیش ازِ آنِ کلیک انجام می‌شد.
    if (s.pre) {
      const pre1 = page.locator(s.pre).first();
      rec.preFound = await pre1.count();
      rec.preClicked = false;
      if (rec.preFound) {
        await pre1.click({ timeout: 6000 }).then(() => { rec.preClicked = true; }).catch((e) => { rec.preError = String(e).replace(/\s+/g, ' ').slice(0, 160); });
        await page.waitForTimeout(1200);
      }
    }
    const trig = page.locator(s.t);
    // ۲) منتظرِ آمدنِ دستگیره می‌نشینیم (داده‌محور: بعضی کنترل‌ها بعد ازِ رسیدنِ
    //    پاسخِ سرور رندر می‌شوند)؛ حداکثرِ TRIGGER_WAIT وِ اگر نیامد صریح
    //    NO-TRIGGER ثبت می‌شود — حذفِ گام یا سبزِ مصنوعی درِ کار نیست.
    await trig.first().waitFor({ state: 'attached', timeout: TRIGGER_WAIT }).catch(() => {});
    rec.triggerFound = await trig.count();
    if (!rec.triggerFound) {
      // شواهدِ طبقه‌بندی: چه چیزی *واقعاً* درِ اینِ route هست؟ بی‌اینِ خط،
      // NO-TRIGGER فقط «دستگیره نبود» می‌گفت و نمی‌شد تشخیص داد سلکتورِ من
      // غلط بوده یا کنترل داده‌محور/گیت‌شدنی است. `kin` = testidهایی که باِ
      // همانِ پیشوندِ دستگیره شروع می‌شوند (درِ صفحه‌ای با ۱۱۸۰ testid، نمونهٔ
      // ۶۰تاییِ اول هیچ‌وقت تاِ «ms-gold-…» نمی‌رسید).
      const hint = (s.t.match(/data-testid="([^"[]+)/) || [])[1] || '';
      const stem = hint.split('-').slice(0, 2).join('-');
      rec.onRoute = await page.evaluate(({ stem, hint }) => {
        const uniq = [...new Set([...document.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid')))];
        const kin = uniq.filter((t) => (stem && t.startsWith(stem)) || (hint && t === hint));
        return { count: uniq.length, stem, kin: kin.slice(0, 14), sample: uniq.slice(0, 40), text: String(document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120) };
      }, { stem, hint });
      rec.result = 'NO-TRIGGER'; out.steps.push(rec);
      console.log(`${s.k} ${s.n.padEnd(34)} NO-TRIGGER  pre=${rec.preClicked === undefined ? '-' : (rec.preClicked ? 'clicked' : 'FAILED(' + (rec.preError || 'absent') + ')')}  testidها=${rec.onRoute.count}  هم‌خانوادۀِ «${stem}»=«${rec.onRoute.kin.join(', ') || 'هیچ'}»`);
      continue;
    }
    if (s.needs) {
      await page.locator(s.needs).first().waitFor({ state: 'attached', timeout: TRIGGER_WAIT }).catch(() => {});
      if (!(await page.locator(s.needs).count())) { rec.result = 'BLOCKED-prereq'; out.steps.push(rec); console.log(`${s.k} ${s.n.padEnd(34)} BLOCKED-prereq`); continue; }
    }
    // خودِ دستگیره: کجا است و آیا چیزی مسیرِ کلیک را می‌گیرد؟
    const tp = await page.evaluate(STATE_FN, { sel: s.t, probeSel: s.t });
    rec.triggerBox = tp.boxes[0] || null;
    rec.triggerBlocked = tp.blocked;
    rec.triggerDisabled = tp.probeDisabled;
    rec.triggerTitle = tp.probeTitle;
    if (tp.probeDisabled) {
      // کنترلِ عمداً غیرفعال (example: منطقِ غربالگری تا دو فیلتر روشن نشوند) —
      // عیبِ رابط نیست؛ سنجشِ درست همانا «غیرفعال است و دلیلش را می‌گوید».
      rec.result = 'DISABLED-BY-DESIGN';
      out.steps.push(rec);
      console.log(`${s.k} ${s.n.padEnd(34)} DISABLED-BY-DESIGN  title=«${(tp.probeTitle || '').slice(0, 60)}»`);
      continue;
    }
    const pre = await page.evaluate(STATE_FN, { sel: s.exp, probeSel: s.t });
    const errBefore = errs.length;
    try {
      if (s.act === 'keys') await page.keyboard.press(s.v);
      else if (s.act === 'type') await trig.first().fill(s.v);
      else if (s.act === 'select') await trig.first().selectOption(s.v);
      else await trig.first().click({ timeout: 8000 });
      rec.clicked = true;
    } catch (e) {
      rec.clicked = false;
      rec.clickError = String(e).replace(/\s+/g, ' ').slice(0, 400);
    }
    await page.waitForTimeout(WAIT);
    const post = await page.evaluate(STATE_FN, { sel: s.exp, probeSel: s.t });
    // طبقه‌بندیِ سنجیده‌شده: لایه‌ای که قبلش نبود = overlay (باید بسته هم بشود)
    const kind = s.kind || (pre.count === 0 ? 'overlay' : 'panel');
    rec.kind = kind;
    rec.count = post.count;
    rec.inView = post.visibleInViewport;
    rec.inert = post.inertOpen;
    rec.notReachable = post.notReachable;
    rec.probeStateBefore = pre.probeState;
    rec.probeState = post.probeState;
    rec.box = post.boxes[0] || null;
    rec.outside = post.outside;
    rec.focus = post.focus;
    rec.focusInLayer = post.focusInLayer;
    rec.ovX = post.overflowX;
    rec.sigBefore = pre.sig;
    rec.sig = post.sig;
    if (kind === 'toggle') rec.opened = !!post.probeState && post.probeState !== pre.probeState;
    else if (kind === 'panel') { rec.opened = post.count > 0; rec.changed = post.sig !== pre.sig || post.count !== pre.count; }
    else rec.opened = post.count > 0 && post.visibleInViewport > 0 && post.inertOpen === 0;

    if (s.close) {
      let closedBy = null;
      if (s.close === 'escape') {
        await page.keyboard.press('Escape');
        closedBy = 'Escape';
      } else {
        const c = page.locator(s.close);
        if (await c.count()) { await c.first().click({ timeout: 6000 }).catch(() => {}); closedBy = s.close; }
      }
      await page.waitForTimeout(900);
      const after = await page.evaluate(STATE_FN, { sel: s.exp, probeSel: s.t });
      if (kind === 'overlay') rec.closed = after.count === 0 || after.inertOpen === after.count;
      // توگل/پنل: «بسته‌شدن» یعنی برگشتنِ حالت یا محتوایِ اول
      else rec.closed = kind === 'toggle' ? after.probeState === pre.probeState : (after.sig === pre.sig || after.count === pre.count);
      rec.closedBy = closedBy;
      rec.countAfterClose = after.count;
      rec.inertAfterClose = after.inertOpen;
      rec.stateAfterClose = after.probeState;
    }
    rec.newErrors = errs.slice(errBefore, errBefore + 3);
    const safe = s.r.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 28) + '__' + s.n.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 26);
    rec.shot = safe + '.png';
    await page.screenshot({ path: path.join(REPO, SHOTS, safe + '.png') }).catch(() => { rec.shot = null; });
    out.steps.push(rec);
    const verb = kind === 'toggle' ? 'TOGGLE' : kind === 'panel' ? 'PANEL' : 'OPEN';
    const verdict = !rec.clicked ? 'CLICK-FAILED' : rec.opened ? (kind === 'panel' && rec.changed === false ? 'PANEL-SAME(no-op)'
      : s.close ? (rec.closed ? verb + '+RESTORE OK' : verb + ', NOT-RESTORED') : verb + ' OK') : 'NOT-' + verb;
    console.log(`${s.k} ${s.n.padEnd(34)} ${verdict.padEnd(21)} n=${rec.count}${rec.box ? ' @' + rec.box.x + ',' + rec.box.y + ' ' + rec.box.w + '×' + rec.box.h : ''}`
      + (rec.outside.length ? ' OUTSIDE' : '') + (rec.ovX > 1 ? ' ovX=' + rec.ovX : '')
      + (rec.triggerBlocked ? ' BLOCKED-BY=' + rec.triggerBlocked.slice(0, 34) : '')
      + (s.close ? ' focus=' + (rec.focusInLayer ? 'in-layer' : String(rec.focus).slice(0, 22)) : '')
      + (rec.newErrors.length ? ' err:' + rec.newErrors[0].slice(0, 50) : ''));
    if (!rec.clicked) console.log('      ' + rec.clickError);
    for (const o of rec.outside || []) console.log('      outside: ' + JSON.stringify(o));
  }
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('\nwrote ' + OUT);
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
