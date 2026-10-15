// _audit/ui/module_probe.js — مرحلۀِ ۴ مأموریتِ UI: پوششِ ماژول‌به‌ماژولِ ابزارها
//
// چه چیزی سنجیده می‌شود (همه درِ viewportِ واقعیِ ۱۳۶۶×۷۶۸، رویِ buildِ همینِ worktree):
//   ۱) نوارِ رسم (`.tool-item`): هرِ ابزار شمارش + جعبه + برچسب؛ هرِ ابزار کلیک
//      می‌شود و «انتخاب‌شدن» باِ کلاسِ active سنجیده می‌شود؛ بعد Escape.
//      هیچِ درَگی رویِ بوم انجام نمی‌شود → هیچِ ترسیمی ذخیره نمی‌شود.
//   ۲) پنلِ اندیکاتورها: باز/بسته + جایِ واقعی (absolute باِ right:260/top:48) +
//      بریدگی/سرریز درِ viewport + شمارِ ردیف‌هایِ اندیکاتور.
//   ۳) بازپخش (replay): شروع → replay-bar دیده شود → پایان → بار بسته شود.
//   ۴) فرمِ سفارش: جست‌وجویِ صریحِ هرِ دستگیره‌ای باِ متنِ «ثبت/ارسالِ سفارش»،
//      «خرید قطعی»، «فروش قطعی» درِ /technical وِ /market — اگر صفر بود، «اینِ
//      محصول فرمِ سفارش ندارد» به عنوانِ شاهدِ منفی ثبت می‌شود (نه حدس).
//   ۵) خطاهایِ کنسول/شبکه درِ طولِ همهٔ قدم‌ها.
// usage: node _audit/ui/module_probe.js [--out=MODULE.json]
const path = require('path'); const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'MODULE.json'));
const ROUTE = arg('route', '/technical/' + encodeURIComponent('فولاد'));
const WAIT = Number(arg('settle', 1200));

const TOOLS_FN = () => {
  const items = [...document.querySelectorAll('.tool-item')];
  const vw = window.innerWidth, vh = window.innerHeight;
  return {
    count: items.length,
    list: items.map((el, i) => {
      const r = el.getBoundingClientRect();
      const b = { i, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
      b.active = el.classList.contains('active');
      b.title = String(el.getAttribute('title') || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
      b.inView = b.x >= 0 && b.y >= 0 && b.x + b.w <= vw && b.y + b.h <= vh;
      b.zero = r.width < 2 || r.height < 2;
      const cx = Math.round(b.x + Math.min(b.w / 2, b.w - 4)), cy = Math.round(b.y + Math.min(b.h / 2, b.h - 4));
      const hit = b.inView ? document.elementFromPoint(cx, cy) : null;
      b.hitSelf = !!hit && (hit === el || el.contains(hit));
      b.blockedBy = hit && !b.hitSelf ? (hit.getAttribute('data-testid') || hit.title || hit.tagName.toLowerCase()) : null;
      return b;
    }),
  };
};

const PANEL_FN = () => {
  const vw = window.innerWidth, vh = window.innerHeight;
  // پنلِ اندیکاتورها: تنها میزبانِ absolute باِ عرضِ ۲۸۰ که داخلِ میزبانِ چارت است
  const cands = [...document.querySelectorAll('div')].filter((d) => {
    const cs = getComputedStyle(d);
    const r = d.getBoundingClientRect();
    return cs.position === 'absolute' && r.width > 200 && r.width < 340 && r.height > 120 &&
      /اندیکاتور/.test(String(d.innerText || '').slice(0, 400));
  });
  const el = cands[0] || null;
  if (!el) return { open: false };
  const r = el.getBoundingClientRect();
  const rows = [...el.querySelectorAll('label, [class*="item"], li')].length;
  return {
    open: true,
    box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    inView: r.x >= 0 && r.y >= 0 && r.right <= vw && r.bottom <= vh,
    outside: { top: Math.max(0, -r.y), bottom: Math.max(0, r.bottom - vh), left: Math.max(0, -r.x), right: Math.max(0, r.right - vw) },
    rows,
    text: String(el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160),
    z: getComputedStyle(el).zIndex,
  };
};

const ORDERSCAN_FN = () => {
  const words = ['ثبت سفارش', 'ارسال سفارش', 'خرید قطعی', 'فروش قطعی', 'ثبتِ سفارش', 'درخواستِ خرید'];
  const els = [...document.querySelectorAll('button, a, input[type="submit"], [role="button"]')];
  const hit = els.filter((e) => words.some((wd) => String(e.textContent || '').includes(wd) || String(e.getAttribute('title') || '').includes(wd)))
    .map((e) => ({ tag: e.tagName.toLowerCase(), text: String(e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40) }));
  return { orderControls: hit.length, samples: hit.slice(0, 5), totalControls: els.length };
};

const TESTID_FN = (sel) => {
  const els = [...document.querySelectorAll(sel)];
  const e = els[0];
  if (!e) return { n: 0 };
  const r = e.getBoundingClientRect();
  const vw = window.innerWidth, vh = window.innerHeight;
  return {
    n: els.length,
    box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    inView: r.y >= 0 && r.bottom <= vh && r.x >= 0 && r.right <= vw,
    text: String(e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120),
  };
};

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = []; const net = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 180)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 180)); });
  page.on('response', (r) => { if (r.status() >= 400) net.push(r.status() + ' ' + r.url().replace(BASE, '').slice(0, 110)); });

  const out = { ranAt: new Date().toISOString(), viewport: { W, H }, route: ROUTE, steps: [] };
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  await page.goto(BASE + '/#' + ROUTE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(14000);

  // ── ۱) نوارِ رسم ───────────────────────────────────────────────────────────
  const tools = await page.evaluate(TOOLS_FN);
  out.steps.push({ what: 'drawing-toolbar-inventory', ...tools });
  const perTool = [];
  for (let i = 0; i < tools.count; i++) {
    const sel = `.tool-item:nth-of-type(${i + 1})`;
    let r;
    try {
      const before = await page.evaluate(TOOLS_FN);
      const el = page.locator('.tool-item').nth(i);
      await el.click({ timeout: 4000 });
      await page.waitForTimeout(WAIT);
      const after = await page.evaluate(TOOLS_FN);
      const wasActive = before.list[i] && before.list[i].active;
      const isActive = after.list[i] && after.list[i].active;
      r = { i, title: (after.list[i] || {}).title, wasActive, isActive, changed: wasActive !== isActive };
      await page.keyboard.press('Escape');
      await page.waitForTimeout(700);
      const esc = await page.evaluate(TOOLS_FN);
      r.afterEscapeActive = !!(esc.list[i] && esc.list[i].active);
    } catch (e) {
      r = { i, error: String(e).replace(/\s+/g, ' ').slice(0, 140) };
    }
    perTool.push(r);
  }
  out.steps.push({ what: 'drawing-tool-click-each', results: perTool });

  // ── ۲) پنلِ اندیکاتورها ────────────────────────────────────────────────────
  const indBtn = 'button[title="پنل اندیکاتورها"]';
  let ind = {};
  try {
    await page.locator(indBtn).first().waitFor({ state: 'attached', timeout: 12000 });
    await page.locator(indBtn).first().click({ timeout: 5000 });
    await page.waitForTimeout(WAIT);
    ind.opened = await page.evaluate(PANEL_FN);
    await page.locator(indBtn).first().click({ timeout: 5000 });
    await page.waitForTimeout(WAIT);
    ind.closed = await page.evaluate(PANEL_FN);
  } catch (e) {
    ind.error = String(e).replace(/\s+/g, ' ').slice(0, 160);
  }
  out.steps.push({ what: 'indicator-panel', ...ind });

  // ── ۳) بازپخش ──────────────────────────────────────────────────────────────
  const rp = {};
  try {
    const start = 'button[title="شروع بازپخش کندل‌ها"]';
    await page.locator(start).first().waitFor({ state: 'attached', timeout: 12000 });
    await page.locator(start).first().click({ timeout: 5000 });
    await page.waitForTimeout(3000);
    // کنترل‌هایِ بازپخش درِ تبِّ «بازپخش» داکِ FTS نشسته‌اند (TechnicalPage.tsx:385)؛
    // پسِ پیشِ سنجش، داک باز و آنِ تب انتخاب می‌شود — بیِ این، bar هیچ‌وقت رسم نمی‌شد
    // وِ جاروب اشتباهاً «بازپخش کار نمی‌کند» می‌گفت.
    rp.dockPre = [];
    for (const sel of ['[data-testid="fts-dock-toggle"]', '[data-testid="fts-dock-tab-replay"]']) {
      const l = page.locator(sel).first();
      if (await l.count().catch(() => 0)) {
        try { await l.click({ timeout: 4000 }); rp.dockPre.push(sel + ' = clicked'); }
        catch (e) { rp.dockPre.push(sel + ' = FAILED ' + String(e).slice(0, 60)); }
        await page.waitForTimeout(1500);
      } else rp.dockPre.push(sel + ' = absent');
    }
    rp.bar = await page.evaluate(TESTID_FN, '[data-testid="replay-bar"]');
    rp.progress = await page.evaluate(TESTID_FN, '[data-testid="replay-progress"]');
    const stop = 'button[title="پایان بازپخش کندل‌ها"]';
    await page.locator(stop).first().waitFor({ state: 'attached', timeout: 8000 });
    await page.locator(stop).first().click({ timeout: 5000 });
    await page.waitForTimeout(2500);
    rp.barAfterStop = await page.evaluate(TESTID_FN, '[data-testid="replay-bar"]');
  } catch (e) {
    rp.error = String(e).replace(/\s+/g, ' ').slice(0, 160);
  }
  out.steps.push({ what: 'replay', ...rp });

  // ── ۴) فرمِ سفارش (شاهدِ منفی) ─────────────────────────────────────────────
  out.steps.push({ what: 'order-form-scan-technical', ...(await page.evaluate(ORDERSCAN_FN)) });
  await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  out.steps.push({ what: 'order-form-scan-market', ...(await page.evaluate(ORDERSCAN_FN)) });
  await page.goto(BASE + '/#/portfolio', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  out.steps.push({ what: 'order-form-scan-portfolio', ...(await page.evaluate(ORDERSCAN_FN)) });

  out.consoleErrors = errs;
  out.networkErrors = net;
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2));

  const lines = [];
  lines.push(`module_probe viewport=${W}x${H} route=${ROUTE} at=${out.ranAt}`);
  for (const s of out.steps) {
    if (s.what === 'drawing-toolbar-inventory') {
      lines.push(`\n[tools] count=${s.count}`);
      for (const t of s.list) lines.push(`  #${t.i} ${t.title} box=[${t.x},${t.y},${t.w},${t.h}] active=${t.active} inView=${t.inView} zero=${t.zero} hitSelf=${t.hitSelf}${t.blockedBy ? ' BLOCKED-BY=' + t.blockedBy : ''}`);
    } else if (s.what === 'drawing-tool-click-each') {
      lines.push('\n[tool clicks]');
      for (const r of s.results) {
        lines.push(`  #${r.i} ${(r.title || '').slice(0, 26)} was=${r.wasActive} now=${r.isActive} changed=${r.changed} afterEsc=${r.afterEscapeActive}${r.error ? ' ERR=' + r.error : ''}`);
      }
    } else {
      lines.push('\n[' + s.what + '] ' + JSON.stringify(s).slice(0, 600));
    }
  }
  lines.push('\nconsole errors=' + errs.length + ' network errors=' + net.length);
  for (const e of errs.slice(0, 10)) lines.push('  ERR ' + e);
  for (const e of net.slice(0, 10)) lines.push('  NET ' + e);
  const text = lines.join('\n') + '\n';
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', arg('txt', 'MODULE.txt')), text);
  process.stdout.write(text);
  await browser.close();
})();
