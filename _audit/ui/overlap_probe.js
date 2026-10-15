// _audit/ui/overlap_probe.js — چه کنترلی زیرِ کنترلِ دیگر گیر کرده است؟
//
// چرا: مرحلۀ «ایرادِ b» از یک کلیکِ نگام‌شده آمد — Playwright گفت مسیرِ کلیکِ
// `open-chart-settings` را `fts-settings-btn` گرفته است. اینِ clase را نمی‌توان
// باِ حدس بست: باید برایِ هرِ route، هرِ کنترلِ دیدنی را جداگانه سنجید که
// نقطۀِ مرکزیِ خودش رویِ خودِش است یا چیزِ دیگر. `elementFromPoint` تنهاِ راهِ
// واقعی است (درِ DOM «z-index» حرفِ آخر را نمی‌زند، چیدمانِ نهایی می‌زند).
// خروجی: INTERCEPTED (گیرکرده) / CLIPPED (بیرونِ viewport) / OK
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/overlap_probe.js [--routes=/technical/فولاد] [--shots=1]
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const ROUTES_ARG = arg('routes', '');
const SHOTS = arg('shots', '') === '1';

const PROBE_FN = (max) => {
  const vw = innerWidth, vh = innerHeight;
  const label = (el) => {
    const t = (el.getAttribute('data-testid') || el.id || el.tagName.toLowerCase() + '.' +
      String(el.className || '').split(/\s+/).filter(Boolean).slice(0, 2).join('.'));
    const tx = String(el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 20);
    return `${t} «${tx}»`;
  };
  const sel = 'button,[role="button"],a[href],input,select,[data-testid]';
  const all = [...document.querySelectorAll(sel)].filter((el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return false;
    if (el.closest('[inert],[aria-hidden="true"]')) return false;
    // محتوایِ <details>ِ بسته درِ Chromium باِ `content-visibility:hidden` ازِ رسم
    // بیرون است ولی کادرِ اندازۀِ «اگرِ باز بود» را برمی‌گرداند ⇒ elementFromPoint
    // آنِ نقطه را عنصرِ بعدی می‌گوید وِ اینِ پرس‌وجو «رویِ آنِ کنترلِ دیگر افتاده»
    // گزارش می‌کرد (مثبتِ کاذب). کنترلِ بسته، کنترلِ دیدنی نیست.
    const det = el.closest('details');
    if (det && !det.open) return false;
    const r = el.getBoundingClientRect();
    return r.width > 3 && r.height > 3;
  });
  const out = [];
  let scanned = 0;
  // «نزدیک‌ترینِ اسکرول‌کننده»: اگرِ کنترل بیرونِ پنجرۀِ اسکرولرِ خودش باشد،
  // چیزِ دیگری رویِ آن نیست — فقطِ پایینِ تا است وِ باِ اسکرول دیدنی می‌شود
  // (fit_check.js رسیدن را جدا می‌سنجد). بی‌اینِ تفکیک، ردیف‌هایِ پایینِ جدولِ
  // اسکرول‌دار «COVERED-BY-فوتر» گزارش می‌شدند (مثبتِ کاذب).
  const nearestScroller = (c) => {
    for (let p = c.parentElement; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll|hidden)/.test(cs.overflowY) && p.scrollHeight > p.clientHeight + 2) return p;
    }
    return null;
  };
  for (const el of all) {
    if (scanned++ > max) break;
    const r = el.getBoundingClientRect();
    const cx = Math.round(r.x + r.width / 2), cy = Math.round(r.y + r.height / 2);
    // بیرونِ viewport = یا پایینِ تا (اسکرول‌شدنی) یا بریدگیِ واقعی؛ تفکیکش باِ
    // اینِ پرس‌وجو نشدنی است پس علامتِ جدا می‌گیرد
    if (cx < 0 || cy < 0 || cx > vw || cy > vh) { out.push({ el: label(el), kind: 'OFF-VIEWPORT', box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } }); continue; }
    const sc = nearestScroller(el);
    if (sc) {
      const q = sc.getBoundingClientRect();
      // نقطۀِ centralِ که می‌کوبیم باید داخلِ پنجرۀِ اسکرولرِ خودش باشد؛ ردیفی که
      // نیمی ازِ آن پایینِ اسکرولر است «زیرِ فوتر» بهِ نظر می‌رسد درِ حالی که
      // اسکرولر خودش بریده‌اش است وِ باِ اسکرول دیدنی می‌شود (مثبتِ کاذب).
      if (!(cx > q.left && cx < q.right && cy > q.top && cy < q.bottom)) {
        out.push({ el: label(el), kind: 'OUTSIDE-OWN-SCROLLER', box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
                   hit: (sc.getAttribute('data-testid') || String(sc.className).slice(0, 30)) + ' [' + Math.round(q.top) + '..' + Math.round(q.bottom) + ']' });
        continue;
      }
    }
    const hit = document.elementFromPoint(cx, cy);
    if (!hit) continue;
    if (hit === el || el.contains(hit)) continue;
    if (hit.contains(el)) {
      //组织能力‌دهندۀِ نقطه، والدِ خودش است ⇒ خودِ کنترل pointer-events ندارد
      if (getComputedStyle(el).pointerEvents !== 'none') {
        out.push({ el: label(el), kind: 'NO-HIT-TARGET', box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } });
      }
      continue;
    }
    const hitLabel = label(hit);
    const isChrome = !!hit.closest('header.glass-strip,[data-chrome="strip"]');
    out.push({
      el: label(el), kind: isChrome ? 'COVERED-BY-CHROME' : 'COVERED', hit: hitLabel,
      box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      hitBox: { x: Math.round(hit.getBoundingClientRect().x), y: Math.round(hit.getBoundingClientRect().y), w: Math.round(hit.getBoundingClientRect().width), h: Math.round(hit.getBoundingClientRect().height) },
    });
  }
  return { vw, vh, total: all.length, findings: out };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 140)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  const ALL = require('./routes.js').ROUTES;
  const routes = ROUTES_ARG ? ALL.filter((r) => ROUTES_ARG.split(',').includes(r[0])) : ALL;
  const out = { ranAt: new Date().toISOString(), viewport: { W, H }, routes: [] };
  for (const [route, marker, min] of routes) {
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    if (marker) await page.waitForFunction(([m, k]) => document.querySelectorAll(m).length >= k, [marker, min || 1], { timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(1800);
    const p = await page.evaluate(PROBE_FN, 260);
    const hidden = p.findings.filter((f) => f.kind === 'OFF-VIEWPORT' || f.kind === 'OUTSIDE-OWN-SCROLLER');
    const bad = p.findings.filter((f) => f.kind !== 'OFF-VIEWPORT' && f.kind !== 'OUTSIDE-OWN-SCROLLER');
    console.log(`\n== ${route}  controls=${p.total}  covered=${bad.length}  below-fold=${hidden.length}`);
    for (const f of bad.slice(0, 25)) console.log(`   ${f.kind}  ${f.el}  box=${JSON.stringify(f.box)}  ←  زیرِ «${f.hit}» ${JSON.stringify(f.hitBox)}`);
    for (const f of hidden.slice(0, 4)) console.log(`   ${f.kind}  ${f.el}  box=${JSON.stringify(f.box)}${f.hit ? '  اسکرولر: ' + f.hit : ''}`);
    if (SHOTS && bad.length) await page.screenshot({ path: path.join(REPO, '_audit', 'ui', 'shots', 'OVERLAP_' + route.replace(/[^\w]+/g, '_') + '.png') }).catch(() => {});
    out.routes.push({ route, ...p, errors: errs.splice(0, errs.length).slice(0, 5) });
  }
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'OVERLAP.json'), JSON.stringify(out, null, 1));
  console.log('\nwrote _audit/ui/OVERLAP.json');
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
