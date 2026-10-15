// _audit/ui/state_probe.js — سنجشِ «حالت» برایِ گام‌هایی که درِ interact_audit فقط
// «امضایِ ظرف» را می‌دیدند و PANEL-SAME/no-op گزارش می‌شدند.
//
// چرا اینِ جاروب لازم است: interact_audit برایِ kind=panel، متنِ ۷۰ کاراکترِ
// اولِ «ناحیۀِ انتظار» را مقایسه می‌کند. وقتیِ آنِ ناحیه یکِ بومِ چارت یا یکِ
// ظرفِ بزرگِ ثابت است، حالتِ واقعیِ کنترل (aria-pressed / کلاسِ active / URL /
// شمارِ سطر) عوض می‌شود ولیِ امضایِ ظرف نه — پسِ «بی‌اثر» دیده می‌شد، نه لزوماً
// باگِ UI. اینجا هرِ گامِ مبهم، حالتِ مشخصِ خودش را می‌سنجد:
//   · قبلِ قدم ← snapshot، بعدِ قدم ← snapshot، وِdiff فیلد‌به‌فیلد
//   · تگِ هدف + role/tabIndex/ disabled همِ ثبت می‌شود تا «کنترلِ واقعی» از
//     «برچسبِ اطلاعاتی» distinguish شود.
// هیچِ سفارشِ زنده‌ای نمی‌فرستد؛ هرِ قدمِ حالت‌دار برمی‌گرددِ حالتِ اول.
//
// usage (بک‌اندِ worktree رویِ :8000):
//   node _audit/ui/state_probe.js            # همهٔ کیس‌ها
//   node _audit/ui/state_probe.js --only=C4,C6
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (n, d) => { const h = argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const ONLY = arg('only', '');
const WAIT = Number(arg('settle', 1400));
const ROUTE_WAIT = Number(arg('route-wait', 3200));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'STATE.json'));
const TXT = path.join(REPO, '_audit', 'ui', arg('txt', 'STATE.txt'));

const CASES = [
  {
    key: 'C1', route: '/market', n: 'منویِ فیلترِ بازارها (دارایی)',
    target: '[data-testid="asset-filter"] button',
    probes: ['[data-testid="asset-filter"] button', '[data-testid="asset-filter-menu"]', '[data-testid="asset-filter-menu"] input[type="checkbox"]'],
    restore: [{ act: 'click', sel: '[data-testid="asset-filter"] button' }],
  },
  {
    key: 'C2', route: '/market-status', n: 'زیرتبِ دومِ طلا',
    target: '[data-testid="ms-gold-tabs"] [data-testid^="ms-gold-tab-"]:nth-child(2)',
    probes: ['[data-testid^="ms-gold-tab-"]', '[data-testid="ms-gold-tabs"]'],
    restore: [{ act: 'click', sel: '[data-testid="ms-gold-tabs"] [data-testid^="ms-gold-tab-"]:nth-child(1)' }],
  },
  {
    key: 'C3', route: '/technical/فولاد', n: 'تبِ دومِ دیالوگِ تنظیماتِ چارت',
    pre: [{ act: 'click', sel: '[data-testid="open-chart-settings"]' }],
    target: '[data-testid="chart-settings"] [data-testid^="settings-tab-"]:nth-child(2)',
    probes: ['[data-testid^="settings-tab-"]', '[data-testid="chart-settings"]', '[data-testid="chart-settings"] input, [data-testid="chart-settings"] select'],
    restore: [{ act: 'click', sel: '[data-testid="chart-settings-close"]' }],
  },
  {
    key: 'C4', route: '/technical/فولاد', n: 'تایم‌فریم → هفتگی',
    target: '[data-testid^="timeframe-"]:nth-child(2)',
    probes: ['[data-testid^="timeframe-"]', '[data-testid="chart-timeframe-note"]', '[data-testid="chart-area"] canvas'],
    restore: [{ act: 'click', sel: '[data-testid^="timeframe-"]:nth-child(1)' }],
  },
  {
    key: 'C5', route: '/technical/فولاد', n: 'دکمۀِ موتورِ چارت (نه منو)',
    target: '[data-testid="nn-engine-ffc"]',
    probes: ['[data-testid="nn-engine-switch"]', '[data-testid^="nn-engine-"]', '[data-testid="ffc-chart-host"]', '[data-testid="fts-engine-back"]', '[data-testid="fts-engine-error"]', '[data-testid="chart-area"]'],
    // درِ حالتِ «موتور دوم» نوارِ ابزارِ KLineCharts (وِ سوئیچِ موتورِ آن) برمontage
    // می‌شود؛ راهِ بازگشتِ خودِ موتور دوم، دکمۀِ fts-engine-back است.
    restore: [{ act: 'click', sel: '[data-testid="fts-engine-back"]' }],
  },
  {
    key: 'C6', route: '/technical/فولاد', n: 'جمع‌کردنِ سایدبارِ تکنیکال',
    target: '[data-testid="sidebar-collapse"]',
    probes: ['[data-testid="technical-sidebar"]', '[data-testid="technical-sidebar-collapsed"]', '[data-testid="sidebar-expand"]', '[data-testid="sidebar-body"]'],
    restore: [{ act: 'click', sel: '[data-testid="sidebar-expand"]' }],
  },
  {
    key: 'C7', route: '/master/فولاد', n: 'تحلیل‌گر تشریحی FTS درِ دосьیه',
    // قیف درِ این نشست صفرِ سطرِ عبوری دارد (بازار بسته) → نماد ازِ خودِ قیف
    // انتخابی نیست؛ دوسيه باِ نشانیِ مستقیمِ همانِ نماد باز می‌شود.
    routeWait: 18000,
    // «مشاور تشریحی FTS» عمداً زیرِ master-toggle-advanced است (§13: خلاصه اول،
    // جزئیات دوم، پیشرفته سوم) → پیش‌شرطِ واقعی، بازکردنِ همانِ بخش است.
    pre: [{ act: 'click', sel: '[data-testid="master-toggle-advanced"]' }],
    target: '[data-testid="fts-analyst-open"]',
    probes: ['[data-testid="master-toggle-advanced"]', '[data-testid="strategy-horizon-selector"]', '[data-testid="fts-analyst-open"]', '[data-testid="fts-analyst-modal"]', '[role="dialog"]'],
    restore: [{ act: 'keys', sel: 'body', v: 'Escape' }],
  },
  {
    key: 'C8', route: '/fundamental', n: 'پری‌ستِ استراتژیک (سوپر)',
    target: '[data-testid="fts-strategic-presets"] button:nth-child(3)',
    probes: ['[data-testid="fts-strategic-presets"] button', '[data-testid="fts-screen-row"]'],
    restore: [{ act: 'click', sel: '[data-testid="fts-strategic-presets"] button:nth-child(2)' }],
  },
  {
    key: 'C9', route: '/master', n: 'مودِ روندگیر (aria-pressed)',
    target: '[data-testid="funnel-mode-trend"]',
    routeWait: 20000,
    probes: ['[data-testid^="funnel-mode-"]', '[data-testid="funnel-counts"]'],
    restore: [{ act: 'click', sel: '[data-testid="funnel-mode-swing"]' }],
  },
  {
    key: 'C10', route: '/master', n: 'گامِ ۲ فرایند (لینکِ روتر)', settle: 5000,
    target: '[data-testid="fts-step-technical"]',
    routeWait: 20000,
    probes: ['[data-testid="fts-process-stepper"]', '[data-testid^="fts-step-"]', '[data-testid^="funnel-stage-"]', '[data-testid="funnel-scroll-technical"]', '[data-testid="funnel-empty-technical"]'],
    restore: [{ act: 'click', sel: '[data-testid="fts-step-tape"]' }],
  },
  {
    key: 'C11', route: '/master/فولاد', n: 'جزئیاتِ FTS (details/summary)',
    target: '[data-testid="dossier-tech-details"] summary',
    routeWait: 18000,
    probes: ['[data-testid="dossier-tech-details"]', '[data-testid="master-fts-details"]'],
    restore: [{ act: 'click', sel: '[data-testid="dossier-tech-details"] summary' }],
  },
  {
    key: 'C12', route: '/strategy-tree', n: 'rail → گامِ T تکنیکال (لینکِ والد)',
    // testid رویِ `<span>` داخلِ `<Link>` است، پسِ خودِ span کنترلِ کلیکِ
    // navigation نیست — هدفِ درست، «a» است که آنِ span را دارد.
    target: '[data-testid="strategy-tree-stepper"] a',
    nth: 1,
    probes: ['[data-testid="strategy-tree-stepper"]', '[data-testid^="tree-flow-rail-"]', '[data-testid^="strategy-tree-page-"]', '[data-testid="strategy-roadmap-zones"]', '[data-testid="strategy-tree-stepper"] a'],
    restore: [{ act: 'click', sel: '[data-testid="strategy-tree-stepper"] a', nth: 0 }],
  },
  {
    key: 'C13', route: '/portfolio', n: 'تازه‌سازیِ واچ‌لیست',
    pre: [{ act: 'click', sel: '[data-testid="portfolio-view-current"]' }],
    target: '[data-testid="portfolio-watchlist-refresh"]',
    probes: ['[data-testid="portfolio-watchlist"]', '[data-testid^="portfolio-watchlist-open-"]', '[role="status"]'],
  },
  {
    key: 'C14', route: '/notifications', n: 'فیلترِ سطحِ بالا',
    target: '[data-testid="notice-level-high"]',
    probes: ['[data-testid="notice-filters"] button', '[data-testid="notice-level-high"]', '[data-testid="notice-list"]'],
    // restore: «نزدیک‌ترینِ همه» — همانِ کلیدِ خودشِ توگل نیست؛ `button:first-child`
    // درِ interact_audit بی‌معنی بود (دکمه‌ها داخلِ div هستند، پسِ هیچِ دکمه‌ای
    // فرزندِ اولِ والدش نیست). این‌جا همانِ دکمه را دوباره می‌زنیم تا خاموش شود.
    restore: [{ act: 'click', sel: '[data-testid="notice-level-high"]' }],
  },
  {
    key: 'C15', route: '/notifications', n: 'برچسبِ منبعِ کدال (کنترل است؟)',
    target: '[data-testid="notice-source-name"]',
    probes: ['[data-testid="notice-sources"]', '[data-testid="notice-source-name"]', '[data-testid="notice-source-fresh"]'],
  },
  {
    key: 'C16', route: '/engine-lab', n: 'اندازۀِ موتورِ klinecharts', settle: 3000,
    target: '[data-testid="lab-measure-klinecharts"]',
    // اثرِ «اندازه‌گیری» درِ جدولِ مقایسه (متن) وِ پنلِ پیادهSeen می‌نشیند، نه درِ
    // خودِ دکمه — پسِ متنِ lab-compare هم پروب می‌شود.
    probes: ['[data-testid="lab-measure-klinecharts"]', '[data-testid="lab-col-klinecharts"]', '[data-testid="lab-compare"]', '[data-testid^="lab-host-"] canvas'],
  },
  {
    key: 'C17', route: '/engine-lab', n: 'بخشِ مقایسه (کنترل است؟)',
    target: '[data-testid="lab-compare"]',
    probes: ['[data-testid="lab-compare"]', '[data-testid="lab-compare"] button', '[data-testid="lab-compare"] a'],
  },
];

const SNAP_FN = (probes) => {
  const vis = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };
  const state = (el) => {
    const cls = String(el.className || '');
    const parts = [
      el.getAttribute('aria-pressed') != null ? 'pressed=' + el.getAttribute('aria-pressed') : null,
      el.getAttribute('aria-expanded') != null ? 'expanded=' + el.getAttribute('aria-expanded') : null,
      el.getAttribute('aria-selected') != null ? 'selected=' + el.getAttribute('aria-selected') : null,
      el.getAttribute('aria-current') != null ? 'current=' + el.getAttribute('aria-current') : null,
      el.getAttribute('data-state') != null ? 'dstate=' + el.getAttribute('data-state') : null,
      el.hasAttribute('open') ? 'open' : null,
      /(^|\s)active(\s|$)/.test(cls) ? 'cls:active' : null,
      /accent-blue|neon-cyan/.test(cls) && /border-accent-blue|border-neon-cyan/.test(cls) ? 'cls:accent' : null,
    ].filter(Boolean);
    return parts.join(',');
  };
  const txt = (el) => String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const box = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; };
  const one = (sel) => {
    const all = [...document.querySelectorAll(sel)];
    const on = all.filter(vis);
    const first = on[0] || all[0] || null;
    return {
      sel,
      n: on.length,
      nAll: all.length,
      states: all.slice(0, 8).map((el) => state(el) || '-'),
      text: first ? txt(first) : '',
      box: first && on.length ? box(first) : null,
      tag: first ? first.tagName.toLowerCase() : null,
      role: first ? first.getAttribute('role') : null,
      clickable: !!first && (['BUTTON', 'A', 'INPUT', 'SELECT', 'SUMMARY'].includes(first.tagName) ||
        /^(button|link|checkbox|tab|menuitem)$/.test(String(first.getAttribute('role') || '')) ||
        first.tabIndex >= 0),
    };
  };
  return {
    at: Date.now(),
    url: location.hash,
    scroll: (() => { const sc = document.querySelector('.app-content') || document.scrollingElement; return Math.round(sc.scrollTop); })(),
    probes: probes.map(one),
  };
};

const TARGET_FN = ({ sel, nth }) => {
  const all = [...document.querySelectorAll(sel)];
  const el = nth == null ? all[0] : all[nth];
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {
    found: true, n: all.length,
    tag: el.tagName.toLowerCase(), role: el.getAttribute('role'),
    clickable: ['BUTTON', 'A', 'INPUT', 'SELECT', 'SUMMARY'].includes(el.tagName) ||
      /^(button|link|checkbox|tab|menuitem)$/.test(String(el.getAttribute('role') || '')) || el.tabIndex >= 0,
    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
    box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    hit: (() => { const h = document.elementFromPoint(Math.round(r.x + Math.min(r.width / 2, r.width - 6)), Math.round(r.y + Math.min(r.height / 2, r.height - 6))); return h ? (h.getAttribute('data-testid') || h.tagName.toLowerCase()) : null; })(),
  };
};

function diff(a, b) {
  const out = [];
  for (let i = 0; i < a.probes.length; i++) {
    const x = a.probes[i], y = b.probes[i];
    const ch = [];
    if (x.n !== y.n) ch.push(`n ${x.n}→${y.n}`);
    if (x.nAll !== y.nAll) ch.push(`nAll ${x.nAll}→${y.nAll}`);
    if (x.states.join(';') !== y.states.join(';')) ch.push(`states ${JSON.stringify(x.states)}→${JSON.stringify(y.states)}`);
    if (x.text !== y.text) ch.push(`text «${x.text.slice(0, 40)}»→«${y.text.slice(0, 40)}»`);
    if (JSON.stringify(x.box) !== JSON.stringify(y.box)) ch.push(`box ${JSON.stringify(x.box)}→${JSON.stringify(y.box)}`);
    if (ch.length) out.push(`${y.sel} :: ${ch.join(' | ')}`);
  }
  if (a.url !== b.url) out.push(`URL ${a.url} → ${b.url}`);
  return out;
}

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)); });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }

  const cases = ONLY ? CASES.filter((c) => ONLY.split(',').map((x) => x.trim()).includes(c.key)) : CASES;
  const out = { ranAt: new Date().toISOString(), viewport: { W, H }, base: BASE, cases: [] };
  // «نمادِ انتخابی» درِ این اپ حالتِ سراسری است (عمدی: /master باِ نماد، دوسيه
  // را نشان می‌دهد نه قیف را). پیشینِ همانِ جاروب بهِ همین دلیل سه کیس را
  // NO-TARGET کرد. پسِ پیشِ هرِ کیس، نماد پاک می‌شود تا کیس‌ها بهِ هم وابسته نباشند.
  const resetSymbol = async () => {
    await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const btn = page.locator('aside[data-shell="inspector"] button[aria-label="بستن پنل نماد"]');
    if (await btn.count().catch(() => 0)) {
      await btn.first().click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(1200);
      return 'cleared';
    }
    return 'none-selected';
  };
  for (const c of cases) {
    const rec = { key: c.key, route: c.route, name: c.n, target: c.target };
    const wait = c.settle || WAIT;
    const L = (sel, nth) => (nth == null ? page.locator(sel).first() : page.locator(sel).nth(nth));
    rec.reset = await resetSymbol();
    // هرِ کیس مستقل: همیشه navigate — حالتِ نماد/تبِ کیسِ قبل نباید سرایت کند
    await page.goto(BASE + '/#' + c.route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(c.routeWait || ROUTE_WAIT);
    for (const p of c.pre || []) {
      try {
        await L(p.sel, p.nth).waitFor({ state: 'attached', timeout: 15000 });
        await L(p.sel, p.nth).click({ timeout: 5000 });
        await page.waitForTimeout(wait);
        rec['pre_' + p.sel] = 'clicked';
      } catch (e) {
        rec['pre_' + p.sel] = 'FAILED ' + String(e).replace(/\s+/g, ' ').slice(0, 120);
      }
    }
    try {
      await L(c.target, c.nth).waitFor({ state: 'attached', timeout: c.attach || 15000 });
      rec.targetInfo = await page.evaluate(TARGET_FN, { sel: c.target, nth: c.nth });
    } catch (e) {
      rec.targetInfo = { found: false, err: String(e).replace(/\s+/g, ' ').slice(0, 160) };
    }
    if (!rec.targetInfo || !rec.targetInfo.found) {
      rec.verdict = 'NO-TARGET';
      out.cases.push(rec);
      fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
      continue;
    }
    try {
      rec.before = await page.evaluate(SNAP_FN, c.probes);
      try {
        await L(c.target, c.nth).click({ timeout: 6000 });
        rec.clicked = true;
      } catch (e) {
        rec.clicked = false;
        rec.clickError = String(e).replace(/\s+/g, ' ').slice(0, 200);
      }
    await page.waitForTimeout(wait);
    rec.after = await page.evaluate(SNAP_FN, c.probes);
    rec.changes = diff(rec.before, rec.after);
    rec.errAfter = errs.length;
    const changed = rec.changes.length > 0;
    rec.verdict = !rec.clicked ? 'CLICK-FAILED'
      : !rec.targetInfo.clickable ? 'TARGET-NOT-A-CONTROL'
        : changed ? 'STATE-CHANGED (' + rec.changes.length + ')'
          : 'STATE-UNCHANGED';
    const restored = [];
    for (const r of c.restore || []) {
      try {
        await L(r.sel, r.nth).waitFor({ state: 'attached', timeout: 8000 });
        if (r.act === 'keys') await page.keyboard.press(r.v);
        else await L(r.sel, r.nth).click({ timeout: 5000 });
        await page.waitForTimeout(wait);
        restored.push(r.sel + ' = ok');
      } catch (e) {
        restored.push(r.sel + ' = FAILED ' + String(e).replace(/\s+/g, ' ').slice(0, 90));
      }
    }
    rec.restore = restored;
    if (c.restore && c.restore.length) {
      rec.afterRestore = await page.evaluate(SNAP_FN, c.probes);
      rec.restoreDrift = diff(rec.before, rec.afterRestore);
    }
    out.cases.push(rec);
    fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
    } catch (e) {
      rec.verdict = 'PROBE-ERROR';
      rec.probeError = String(e).replace(/\s+/g, ' ').slice(0, 200);
      out.cases.push(rec);
      fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
    }
  }
  out.consoleErrors = errs;
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2));

  const lines = [];
  lines.push(`state_probe  viewport=${W}x${H}  base=${BASE}  at=${out.ranAt}`);
  lines.push('');
  for (const c of out.cases) {
    lines.push(`${c.key}  ${c.name}   [${c.verdict}]`);
    lines.push(`     reset(symbol)=${c.reset || '-'}   target ${c.target}${c.nth ? ' [nth=' + c.nth + ']' : ''}`);
    lines.push(`     → tag=${c.targetInfo ? c.targetInfo.tag : '-'} role=${c.targetInfo ? c.targetInfo.role : '-'} clickable=${c.targetInfo ? c.targetInfo.clickable : '-'} disabled=${c.targetInfo ? c.targetInfo.disabled : '-'} box=${c.targetInfo ? JSON.stringify(c.targetInfo.box) : '-'} hit=${c.targetInfo ? c.targetInfo.hit : '-'}`);
    if (c.clickError) lines.push(`     clickError: ${c.clickError}`);
    if (c.targetInfo && c.targetInfo.err) lines.push(`     attachError: ${c.targetInfo.err}`);
    if (c.probeError) lines.push(`     probeError: ${c.probeError}`);
    if (Object.keys(c).some((k) => k.startsWith('pre_'))) {
      lines.push('     pre: ' + Object.keys(c).filter((k) => k.startsWith('pre_')).map((k) => k.slice(4) + ' => ' + c[k]).join(' ; '));
    }
    for (const p of (c.after || { probes: [] }).probes) {
      lines.push(`     · ${p.sel}  n=${p.n}  states=${JSON.stringify(p.states)}  box=${JSON.stringify(p.box)}`);
      lines.push(`        text=${p.text}`);
    }
    for (const ch of c.changes || []) lines.push(`     Δ ${ch}`);
    if (c.restore) lines.push(`     restore: ${c.restore.join(' ; ')}`);
    if (c.restoreDrift && c.restoreDrift.length) lines.push(`     DRIFT-after-restore: ${c.restoreDrift.join(' | ')}`);
    lines.push('');
  }
  lines.push(`console/page errors during run = ${out.consoleErrors.length}`);
  for (const e of out.consoleErrors.slice(0, 12)) lines.push('  ERR ' + e);
  const text = lines.join('\n') + '\n';
  fs.writeFileSync(TXT, text);
  process.stdout.write(text);
  await browser.close();
})();
