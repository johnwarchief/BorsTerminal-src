// _audit/ui/installed_probe.js — نسخۀِ نصبی رویِ 127.0.0.1:8001، فقطِ خواندنی
//
// چرا و باِ چه حدی: مالک خواسته نسخۀِ نصبی هم درِ ۱۳۶۶×۷۶۸ سنجیده شود، اما
// DB/حساب/تنظیمات/خودِ برنامۀِ نصبی نباید دست بخورد. پسِ اینِ جاروب:
//   · هیچِ نامِ کاربری/رمزی تایپ نمی‌کند و واردِ هیچِ حسابی نمی‌شود؛
//   · فقطِ صفحۀِورود را بارگذاری وِ اندازه‌گیری می‌کند (خودِ درگاهِ ورود هم
//     بخشیِ ازِ آدیتِ responsive است)؛
//   · ازِ پروفایلِ موقتِ خودِ harness استفاده می‌کند (contextِ ناپایدار، بسته
//     می‌شود) — هیچِ فایلیِ کنارِ برنامۀِ نصبی نوشته نمی‌شود؛
//   · همزمانِ نشانه‌هایِ build (نامِ asset هایِ hash‌شده) را بی‑HTMLِ صفحه
//     می‌خواند تا معلوم شود نسخۀِ نصبی باِ buildِ آدیت‌شده یکی است یا نه.
// usage: node _audit/ui/installed_probe.js [--base=http://127.0.0.1:8001]
const path = require('path'); const fs = require('fs');
const http = require('http');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };
const BASE = arg('base', 'http://127.0.0.1:8001');
const EXE = process.env.RA_BROWSER || String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
const W = Number(arg('w', 1366)), H = Number(arg('h', 768));
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'INSTALLED.json'));

const get = (url) => new Promise((res, rej) => {
  const req = http.get(url, (r) => { let b = ''; r.setEncoding('utf8'); r.on('data', (c) => (b += c)); r.on('end', () => res({ status: r.statusCode, body: b, headers: r.headers })); });
  req.on('error', rej); req.setTimeout(8000, () => req.destroy(new Error('timeout')));
});

const PAGE_FN = () => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const de = document.documentElement;
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (r.right <= vw + 1 && r.left >= -1 && r.bottom <= vh + 1 && r.top >= -1) continue;
    out.push({
      id: el.getAttribute('data-testid') || el.id || el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0],
      box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      over: { right: Math.max(0, Math.round(r.right - vw)), bottom: Math.max(0, Math.round(r.bottom - vh)), left: Math.max(0, Math.round(-r.x)) },
    });
  }
  const focusables = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')]
    .filter((e) => !e.disabled && e.getClientRects().length);
  const small = focusables.filter((e) => { const r = e.getBoundingClientRect(); return r.width < 24 || r.height < 24; })
    .map((e) => ({ id: e.getAttribute('data-testid') || e.id || e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0], box: [Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)] }));
  return {
    url: location.href,
    viewport: [vw, vh],
    dpr: window.devicePixelRatio,
    scrollW: de.scrollWidth, scrollH: de.scrollHeight,
    ovX: de.scrollWidth - vw,
    rootFont: getComputedStyle(de).fontSize,
    heading: String((document.querySelector('h1,h2') || {}).innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80),
    hasPassword: !!document.querySelector('input[type="password"]'),
    outOfBounds: out.slice(0, 12),
    outCount: out.length,
    focusable: focusables.length,
    smallTargets: small.slice(0, 10),
    bodyText: String(document.body.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 220),
  };
};

(async () => {
  const out = { ranAt: new Date().toISOString(), base: BASE, viewport: { W, H } };
  // ۱) HTTPِ مستقیم: چه buildی سرو می‌شود؟ (بدونِ مرورگر، بدونِ حالت)
  try {
    const r = await get(BASE + '/');
    out.http = { status: r.status, server: r.headers['server'] || null, bytes: r.body.length };
    out.http.assets = [...r.body.matchAll(/(?:src|href)="([^"]+\.(?:js|css))"/g)].map((m) => m[1]).slice(0, 8);
    out.http.title = ((r.body.match(/<title>([^<]*)<\/title>/i) || [])[1] || '').trim();
    out.http.loginGateMarkup = /رمز|نام کاربری|password/i.test(r.body);
  } catch (e) {
    out.http = { error: String(e).slice(0, 160) };
  }
  // ۲) buildِ آدیت‌شده برایِ مقایسه
  try {
    const idx = fs.readFileSync(path.join(REPO, 'frontend', 'dist', 'index.html'), 'utf8');
    out.auditedBuildAssets = [...idx.matchAll(/(?:src|href)="([^"]+\.(?:js|css))"/g)].map((m) => m[1]).slice(0, 8);
  } catch (e) { out.auditedBuildAssets = ['unreadable: ' + String(e).slice(0, 60)]; }

  // ۳) رندرِ صفحۀِورود درِ ۱۳۶۶×۷۶۸ — بی‌ورودِ حساب
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });
  try {
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(3500);
    out.render = await page.evaluate(PAGE_FN);
    out.render.consoleErrors = errs;
    await page.screenshot({ path: path.join(REPO, '_audit', 'ui', 'shots', 'installed', 'gate_1366x768.png') });
    out.screenshot = '_audit/ui/shots/installed/gate_1366x768.png';
  } catch (e) {
    out.render = { error: String(e).replace(/\s+/g, ' ').slice(0, 200), consoleErrors: errs };
  }
  await ctx.close();
  await browser.close();

  fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
  const lines = [];
  lines.push(`installed_probe base=${BASE} viewport=${W}x${H} at=${out.ranAt}`);
  lines.push('http: ' + JSON.stringify(out.http));
  lines.push('audited build assets: ' + JSON.stringify(out.auditedBuildAssets));
  const r = out.render || {};
  if (r.error) lines.push('render: ERROR ' + r.error);
  else {
    lines.push(`render: url=${r.url} viewport=${JSON.stringify(r.viewport)} dpr=${r.dpr} rootFont=${r.rootFont}`);
    lines.push(`  heading=«${r.heading}» loginGate=${r.hasPassword} focusable=${r.focusable}`);
    lines.push(`  scroll=${JSON.stringify([r.scrollW, r.scrollH])} ovX=${r.ovX} outOfBounds=${r.outCount}`);
    for (const o of r.outOfBounds || []) lines.push(`    OOB ${o.id} ${JSON.stringify(o.box)} over=${JSON.stringify(o.over)}`);
    for (const s of r.smallTargets || []) lines.push(`    SMALL ${s.id} ${JSON.stringify(s.box)}`);
    lines.push('  console errors=' + (r.consoleErrors || []).length);
    for (const e of r.consoleErrors || []) lines.push('    ERR ' + e);
  }
  const text = lines.join('\n') + '\n';
  fs.writeFileSync(path.join(REPO, '_audit', 'ui', arg('txt', 'INSTALLED.txt')), text);
  process.stdout.write(text);
})();
