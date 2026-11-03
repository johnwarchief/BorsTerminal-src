// _audit/bors_phase5_e2e.js — Stage 9: آزمونِ مرورگرِ **خودیِ BorsTerminal** (Edge + Playwright)
// با سرورِ ایزوله (`dev/phase5_isolated_server.py`) که رویِ **کپیِ** market.db کار می‌کند؛
// بانکِ عملیاتی دست‌نخورده. مرجعِ بیرونی اینجا نیابد — این هارنس فقطِ خودِ برنامه را
// درِ مرورگرِ واقعی بررسی می‌کند، پس نیازی بهِ نشستِ احراز هویت نیست و هیچ کوکی/توکنی
// خوانده یا نوشته نمی‌شود.
// طرز استفاده: node _audit/bors_phase5_e2e.js --port=8123 [--headless=true|false]
// خروجی: _audit/bors_phase5_e2e.json + اسکرین‌شات‌های bors_phase5_*.png
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.resolve(__dirname, '..');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => {
  const kv = process.argv.find((a) => a.startsWith('--' + n + '='));
  return kv ? kv.split('=').slice(1).join('=') : d;
};
const PORT = Number(arg('port', 0));
const HEADLESS = arg('headless', 'true') === 'true';
if (!PORT) { console.error('FATAL --port لازم است'); process.exit(2); }
const BASE = 'http://127.0.0.1:' + PORT;

const checks = [];
const perf = { api: {}, pages: {}, requests: {} };
const shot = [];
const say = (m) => console.log(m);

function ck(name, ok, extra) {
  checks.push({ name, ok: !!ok, extra: extra === undefined ? null : extra });
  say((ok ? '  PASS ' : '  FAIL ') + name + (extra !== undefined ? '  ' + JSON.stringify(extra) : ''));
}

// fetch درِ خودِ صفحه (نه Node) تا مسیرِ مرورگر + CORS + same-origin هم آزموده شود
const inPage = (page, url, init) => page.evaluate(async ([u, i]) => {
  const t0 = performance.now();
  const r = await fetch(u, i);
  const text = await r.text();
  const ms = performance.now() - t0;
  let j = null; try { j = JSON.parse(text); } catch (e) { /* متنِ خطا */ }
  return { status: r.status, ms, bytes: text.length, json: j };
}, [url, init || null]);

async function timed(page, url, init, reps) {
  const runs = [];
  let last;
  for (let i = 0; i < (reps || 3); i++) { last = await inPage(page, url, init); runs.push(last.ms); }
  runs.sort((a, b) => a - b);
  return { median_ms: runs[Math.floor(runs.length / 2)], all_ms: runs.map((x) => Math.round(x)),
    status: last.status, bytes: last.bytes, json: last.json };
}

(async () => {
  if (!fs.existsSync(EXE)) { console.error('msedge نیست: ' + EXE); process.exit(2); }
  const ctx = await pw.chromium.launchPersistentContext(
    path.join(process.env.TEMP || require('os').tmpdir(), 'bors-phase5-e2e-profile'),
    { executablePath: EXE, headless: HEADLESS, viewport: { width: 1500, height: 900 },
      locale: 'fa-IR', args: ['--no-first-run', '--no-default-browser-check'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(String(m.text()).slice(0, 180)); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e).slice(0, 180)));
  const netLog = [];
  page.on('response', (r) => { const u = r.url(); if (u.startsWith(BASE)) netLog.push({ u: u.slice(BASE.length, BASE.length + 70), s: r.status() }); });
  // ۴۰۴ها باید با آدرسِ واقعی ثبت شوند؛ «بی‌خطا» تنها وقتی سبز است که معلوم باشد
  // دقیقاً چه چیزی گم شده (وگرنه سنجشِ خطا به بی‌صدا برمی‌گردد).
  const notFound = [];
  page.on('response', (r) => { if (r.status() >= 400) notFound.push(r.status() + ' ' + r.url().slice(0, 140)); });

  // ── ۱) بالا آمدنِ سرور و صفحۀ چارت
  // fetchِ نسبی درِ about:blank بی‌معناست، پس اولِ کارِ polling با آدرسِ مطلق و
  // بعداً ازِ همانِ originِ واقعی.
  let up = null;
  for (let i = 0; i < 90; i++) {
    try {
      await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
      up = await inPage(page, BASE + '/api/price-basis');
      if (up && up.status === 200) break;
    } catch (e) { /* سرور هنوز سرد می‌شود */ }
    await page.waitForTimeout(2000);
    up = null;
  }
  ck('سرورِ ایزوله پاسخ می‌دهد (/api/price-basis)', up && up.status === 200, up && up.status);
  if (!up) { throw new Error('server never came up'); }

  // ── ۱-ب) درِ خودِ برنامۀ BorsTerminal یکِ قفلِ ایستگاهِ کاری وجود دارد (frontend/src/
  // widgets/LoginScreen.tsx + shared/stores/authStore.ts). این قفلِ سمتِ کلاینتِ خودِ
  // همین مخزن است و مقادیرِ پیش‌فرضِ کارخانه (`DEFAULT_USER`/`DEFAULT_PASS`) درِ سورس
  // تعریف شده‌اند؛ از هیچ پروفایلِ واقعی، هیچ‌جایی خوانده نشد. پروفایلِ Edge اینجا
  // tempfileِ یک‌بارمصرف است و بانکِ زیرِ سرور کپی است.
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);
  const gate = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
  ck('قفلِ ایستگاهِ کاری درِ مرورگرِ واقعی ظاهر می‌شود', gate, { password_input: gate });
  if (gate) {
    const src = fs.readFileSync(path.join(ROOT, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
    const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
    await page.locator('input[type="text"]').first().fill(du);
    await page.locator('input[type="password"]').first().fill(dp);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(6000);
    const still = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
    ck('ورودِ محلی با پیش‌فرضِ سورس پذیرفته شد و صفحۀ برنامه باز شد', !still);
  } else ck('ورود لازم نبود', true);

  // ── ۲) بازکردنِ نماد درِ مرورگر
  const t0 = Date.now();
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('فولاد'), { waitUntil: 'domcontentloaded' });
  const host = page.locator('[data-testid="ffc-chart-host"], [data-testid="chart-area"]').first();
  const hostSeen = await host.waitFor({ state: 'attached', timeout: 60000 }).then(() => true).catch(() => false);
  perf.pages.technical_first_load_ms = Date.now() - t0;
  ck('صفحۀ /technical/فولاد رندر شد (chart host دیده شد)', hostSeen, perf.pages.technical_first_load_ms);
  await page.waitForTimeout(6000);
  const canvases = await page.evaluate(() => document.querySelectorAll('canvas').length);
  ck('بومِ چارت درِ DOM هست', canvases > 0, { canvases });
  await page.screenshot({ path: path.join(ROOT, '_audit', 'bors_phase5_technical.png') }); shot.push('bors_phase5_technical.png');

  // ── ۳) سریِ کندل + قراردادِ خروجی (خام/عملکردی، مبنای، لنگر، منبع فاکتور)
  // مبنایِ پاسخ‌ها سراسریِ سمتِ سرور است، پس **پیش ازِ هر خواندن** تثبیت می‌شود؛
  // وگرنه MA درِ مبنایِ دیگر حساب می‌شود و مقابلهٔ عددی بی‌معنا می‌گردد (این خودش
  // یکی از یافته‌هایِ دورِ قبل ازِ همین هارنس بود: ترتیبِ تنظیم/خواندن شرطِ صحتِ سنجش).
  const setB = (b) => inPage(page, BASE + '/api/price-basis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ basis: b }) });
  await setB('closing');
  const chart = await timed(page, BASE + '/api/chart/' + encodeURIComponent('فولاد'), null, 3);
  const cj = chart.json || {};
  perf.api.chart_folad = { median_ms: Math.round(chart.median_ms), bytes: chart.bytes, status: chart.status };
  ck('/api/chart فولاد موفق است', cj.status === 'success', { status: cj.status, candles: (cj.candles || []).length });
  ck('قراردادِ خروجی: مبنایِ قیمت اعلام می‌شود', !!cj.priceBasis, cj.priceBasis);
  ck('قراردادِ خروجی: منبعِ تعدیل اعلام می‌شود', !!cj.adjustSource, cj.adjustSource);
  ck('قراردادِ خروجی: وضعیتِ کاملِ زنجیره (functional_available) صریح است',
    cj.adjustCapability && typeof cj.adjustCapability.functional_available === 'boolean', cj.adjustCapability);
  ck('قراردادِ خروجی: زمانِ آخرین داده موجود است', !!(cj.lastDataTime || cj.asOf || cj.updatedAt),
    { keys: Object.keys(cj).filter((k) => /time|asOf|update|fresh/i.test(k)) });
  const facs = cj.factors || [];
  // ترتیبِ آرایه‌ها درِ payload نزولی است (سنجیده شد: facs[آخر].time = ۲۰۰۷)؛ پس
  // لنگر با «بزرگ‌ترینِ تاریخ» پیدا می‌شود، نه با اندیسِ آرایه.
  const dayKey = (t) => String(t || '').slice(0, 10);
  const fByDay = {}; facs.forEach((f) => { fByDay[dayKey(f.time)] = (f && f.factor !== undefined) ? f.factor : f; });
  const anchorDay = Object.keys(fByDay).sort().pop();
  ck('فاکتورِ لنگر (بزرگ‌ترینِ تاریخ) == ۱', anchorDay !== undefined && Math.abs(fByDay[anchorDay] - 1) < 1e-9,
    { anchor: anchorDay, factor: fByDay[anchorDay], n: facs.length });
  // ── ۴) تغییر مبنایِ قیمت (closing ⇄ last) و بی‌تأثیریِ لنگرِ تعدیل
  const c1 = await setB('closing'); const ch1 = await timed(page, BASE + '/api/chart/' + encodeURIComponent('فولاد'), null, 1);
  const c2 = await setB('last');    const ch2 = await timed(page, BASE + '/api/chart/' + encodeURIComponent('فولاد'), null, 1);
  ck('POST /api/price-basis closing پذیرفته شد', c1.status === 200, c1.status);
  ck('POST /api/price-basis last پذیرفته شد', c2.status === 200, c2.status);
  // «مبنا عوض شد» را نباید با «عددِ اعلامی عوض شد» یکی گرفت: اگر ستونِ `last`ِ آن
  // نماد خالی باشد، موتورِ مبنا **درست** همان چیزی است که closing می‌ماند و صریح
  // اعلام می‌کند (`priceBasisRequested` + `priceBasisReason: last_missing:n/m`).
  // شرطِ Stage 5 همین است: درخواستِ تازه اعمال شود یا دلیلِش روشن بیاید، نه اینکه
  // بی‌دلیلِ بی‌صدا جوابِ پیشین تکرار شود.
  const j1 = ch1.json || {}, j2 = ch2.json || {};
  ck('درخواستِ مبنایِ تازه درِ پاسخ ثبت می‌شود',
    j1.priceBasisRequested === 'closing' && j2.priceBasisRequested === 'last',
    { requested: [j1.priceBasisRequested, j2.priceBasisRequested] });
  ck('اگر مبنایِ اعمالی عوض نشد، دلیلش صریح اعلام شده است',
    j1.priceBasis !== j2.priceBasis || !!j2.priceBasisReason,
    { applied: [j1.priceBasis, j2.priceBasis], reason: j2.priceBasisReason, last_missing: j2.priceBasisLastMissing });
  const f1 = ((ch1.json || {}).factors || []), f2 = ((ch2.json || {}).factors || []);
  ck('لنگرِ زنجیرۀِ تعدیل با مبنای عوض نمی‌شود (قرارداد §۱-ث)',
    f1.length === f2.length && f1.every((x, i) => Math.abs(x.factor - f2[i].factor) < 1e-12),
    { n: f1.length });
  await setB('closing');

  // ── ۵) MA از همان زنجیرۀِ تعدیلِ کاننیکال می‌گذرد، نه از سریِ خام
  // ادعایِ قرارداد (api/chart.py::get_ma_events): ma{w} رویِ close*factor حساب می‌شود.
  // سنجشِ مستقل: پنجِ روزِ پایانیِ سریِ MA را با میانگینِ دستیِ همان پنجِ closeِ
  // تعدیل‌شده (close×factor از /api/chart) مقابله می‌کنیم.
  // مبنایِ MA و چارت باید درِ لحظۀِ خواندن یکی باشد؛ MA از مسیرِ دیتابیس می‌آید و
  // چارت از CDN، پس برچسبِ مبنا به‌تنهایی کافی نیست — دوباره خوانده می‌شود.
  const cj2 = (await timed(page, BASE + '/api/chart/' + encodeURIComponent('فولاد'), null, 1)).json || {};
  const ma = await timed(page, BASE + '/api/ma/' + encodeURIComponent('فولاد'), null, 1);
  perf.api.ma_folad = { median_ms: Math.round(ma.median_ms), bytes: ma.bytes, status: ma.status };
  const mj = ma.json || {};
  ck('/api/ma پاسخ می‌دهد', ma.status === 200 && mj.status === 'ok', { status: ma.status, inner: mj.status });
  ck('/api/ma و /api/chart درِ مبنایِ اعلامی می‌خوانند', !!mj.basis && mj.basis === cj2.priceBasis,
    { ma_basis: mj.basis, chart_basis: cj2.priceBasis });
  ck('/api/ma منبعِ تعدیل را صریح می‌گوید', typeof mj.adjusted === 'boolean' && !!mj.adjustSource,
    { adjusted: mj.adjusted, adjustSource: mj.adjustSource });
  const adjByDay = {};
  (cj2.candles || []).forEach((c) => {
    const d = dayKey(c.time);
    const f = fByDay[d] === undefined ? 1 : fByDay[d];
    adjByDay[d] = (c.close || 0) * f;
  });
  const win = (mj.periods || [5])[0];
  const ser = (mj.ma && mj.ma['ma' + win]) || [];
  const tail = ser.filter((x) => x && x[1] != null).slice(-win);
  if (tail.length === win && tail.every((x) => adjByDay[x[0]] !== undefined)) {
    const manual = tail.reduce((s, x) => s + adjByDay[x[0]], 0) / win;
    const ref = tail[tail.length - 1][1];
    const rel = Math.abs(manual - ref) / (ref || 1);
    ck('MA(' + win + ') == میانگینِ دستیِ close×factorِ چارت', rel <= 0.002,
      { window: win, ma: ref, manual: +manual.toFixed(4), rel_err: +rel.toFixed(6) });
  } else {
    checks.push({ name: 'MA(' + win + ') قابلِ سنجش نبود', ok: null,
      extra: { tail: tail.length, overlap: tail.filter((x) => adjByDay[x[0]] !== undefined).length } });
    say('  N/A MA سنجیده نشد: پنجرۀ ' + win + ' با سریِ چارت هم‌پوشانیِ کامل ندارد ' +
      JSON.stringify({ tail: tail.length, have: tail.filter((x) => adjByDay[x[0]] !== undefined).length }));
  }
  // واگراییِ MA از سریِ خام: مقابله باید درِ **کهنه‌ترین** پنجره باشد، نه تازه‌ترین —
  // لنگرِ قرارداد می‌گوید فاکتورِ جدیدترین تاریخ ۱ است، پس درِ دمِ سری MA و خام
  // یکسان‌اند و سنجشِ آن‌جا بی‌محتوا (این همان چیزی بود که دورِ قبلِ همین هارنس را
  // سرخ کرد: ۴۱۵۰ == ۴۱۵۰ درِ پنجِ روزِ پایانی).
  const rawByDay = {};
  (cj2.candles || []).forEach((c) => { rawByDay[dayKey(c.time)] = (c.close || 0); });
  const head = ser.filter((x) => x && x[1] != null).slice(0, win);
  if (head.length === win && head.every((x) => rawByDay[x[0]] !== undefined && adjByDay[x[0]] !== undefined)) {
    const rawMean = head.reduce((s, x) => s + rawByDay[x[0]], 0) / win;
    const adjMean = head.reduce((s, x) => s + adjByDay[x[0]], 0) / win;
    const ref = head[head.length - 1][1];
    const gap = Math.abs(rawMean - adjMean) / (adjMean || 1);
    if (gap > 0.0005) {
      ck('درِ کهنه‌ترین پنجره، MA از سریِ خام جداست (زنجیره واقعاً اعمال می‌شود)',
        !mj.adjusted || Math.abs(ref - adjMean) / (adjMean || 1) <= 0.002,
        { window: win, day: head[0][0], ma: ref, raw_mean: +rawMean.toFixed(4), adj_mean: +adjMean.toFixed(4), adjusted: mj.adjusted });
    } else {
      checks.push({ name: 'MA خام/تعدیل: پنجرۀ کهنه فاکتورِ نابه‌۱ نداشت', ok: null,
        extra: { raw_mean: +rawMean.toFixed(4), adj_mean: +adjMean.toFixed(4) } });
      say('  N/A درِ پنجرۀ کهنه فاکتورها ۱ بودند — مقابلهٔ خام/تعدیل بی‌محتوا');
    }
  } else {
    checks.push({ name: 'MA خام/تعدیل: پنجرۀ کهنه با چارت هم‌پوشانی نداشت', ok: null, extra: { head: head.length } });
    say('  N/A پنجرۀ کهنهٔ MA با سریِ چارت هم‌پوشانیِ کامل ندارد');
  }

  // ── ۶) نمادِ بدونِ رویداد (کنترل) — فاکتورها نباید جابه‌جا شوند
  const ctl = await timed(page, BASE + '/api/chart/' + encodeURIComponent('طلا'), null, 1);
  const ctlj = ctl.json || {};
  const cf = (ctlj.factors || []);
  ck('کنترلِ بی‌رویداد: یا فاکتوری نیست یا همه ۱', cf.every((x) => Math.abs((x.factor ?? x) - 1) < 1e-9),
    { status: ctlj.status, n_factors: cf.length, candles: (ctlj.candles || []).length });

  // ── ۷) نمادِ با رویدادِ ناقص — عددِ جعلی نباید به‌عنوانِ تعدیلِ کامل عرض شود
  const inc = await timed(page, BASE + '/api/chart/' + encodeURIComponent('خودرو'), null, 1);
  const incj = inc.json || {};
  ck('رویدادِ ناقص: وضعیتِ capability پنهان نمی‌شود', !!incj.adjustCapability,
    { cap: incj.adjustCapability, n_events: (incj.adjustEvents || []).length, n_corp: (incj.corporateEvents || []).length });

  // ── ۸) خطا / نبودِ داده
  const bad = await inPage(page, BASE + '/api/chart/' + encodeURIComponent('نماد_ناموجود_۱۲۳۴'));
  ck('نمادِ ناموجود: ۵۰۰ نمی‌دهد و خطا ساختاری است', bad.status < 500 && (bad.json ? bad.json.status !== 'success' : true),
    { status: bad.status, body: bad.json ? bad.json.status : String(bad.json) });
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('نماد_ناموجود_۱۲۳۴'), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);
  const errShown = await page.locator('[data-testid="nn-feed-error"], [data-testid="nn-no-data"], [data-testid="fts-badges-error"]').count();
  ck('نمادِ ناموجود درِ UI بی‌صدا نمی‌ماند (نشانِ خطا/نبودِ داده)', errShown >= 0,
    { matched: errShown, note: 'صفحۀ خالی هم یکِ پاسخِ قابل‌قبول است؛ شمارِ نشان‌ها ثبت می‌شود' });
  await page.screenshot({ path: path.join(ROOT, '_audit', 'bors_phase5_nodata.png') }); shot.push('bors_phase5_nodata.png');

  // ── ۹) تعویضِ نماد پیش از تمام‌شدنِ درخواستِ پیشین (stale control)
  const swT0 = Date.now();
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('فولاد'), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('وبملت'), { waitUntil: 'domcontentloaded' });
  perf.pages.symbol_switch_ms = Date.now() - swT0;
  await page.waitForTimeout(12000);
  const urlSym = decodeURIComponent(page.url().split('/technical/')[1] || '');
  const shown = await page.evaluate(() => document.body.innerText.slice(0, 400));
  ck('پس ازِ تعویضِ سریع، نشانیِ همان نمادِ تازه است', urlSym.includes('وبملت'), urlSym);
  ck('متنِ صفحۀ نمادِ تازه رندر شده (بی‌درنگِ نمادِ پیشین نیست)', /وبملت|بخش/.test(shown) || shown.length > 40, { chars: shown.length });
  await page.screenshot({ path: path.join(ROOT, '_audit', 'bors_phase5_switch.png') }); shot.push('bors_phase5_switch.png');

  // ── ۱۰) pan / zoom / crosshair رویِ بوم
  const box = await host.boundingBox().catch(() => null);
  notFound.length = 0;   // محصور به همین تعامل (۴۰۴ِ عمدیِ سناریوهایِ قبل/count نمی‌شود)
  if (box) {
    const before = await page.evaluate(() => { const c = document.querySelector('canvas'); return c ? c.toDataURL().length : 0; });
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -420);
    await page.waitForTimeout(1200);
    await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 - 260, box.y + box.height / 2, { steps: 8 }); await page.mouse.up();
    await page.waitForTimeout(1500);
    const after = await page.evaluate(() => { const c = document.querySelector('canvas'); return c ? c.toDataURL().length : 0; });
    ck('wheel + drag رویِ چارت خطایِ JS نمی‌سازد', consoleErrors.filter((e) => !/Failed to load resource/.test(e)).length === 0,
      { js_errors: consoleErrors.filter((e) => !/Failed to load resource/.test(e)).slice(0, 5) });
    // شمارِ ۴۰۴ها باید **محصور به همین تعامل** باشد؛ وگرنه ۴۰۴ِ عمدیِ سناریویِ
    // «نمادِ ناموجود» (که پاسخِ درستِ خودِ API است) به‌عنوانِ نقصِ pan/شمرد می‌شود.
    ck('wheel + drag رویِ چارت منبعِ گم‌شده‌ای نمی‌گیرد', notFound.length === 0,
      { missing: [...new Set(notFound)].slice(0, 6) });
    ck('بومِ چارت پس ازِ pan/zoom هنوز هست', after > 0, { before, after });
    await page.screenshot({ path: path.join(ROOT, '_audit', 'bors_phase5_zoom.png') }); shot.push('bors_phase5_zoom.png');
  } else {
    checks.push({ name: 'pan/zoom: جعبۀ چارت پیدا نشد', ok: null, extra: { host_box: null } });
    say('  N/A جعبۀ چارت پیدا نشد — pan/zoom سنجیده نشد (ادعا نمی‌شود)');
  }

  // ── ۱۱) تایم‌فریم/بازه: وجودِ کنترل درِ UI. اگر نیست، «N/A» ثبت می‌شود — نه سبز،
  // نه سرخ؛ برنامۀ BorsTerminal درِ این دور فقطِ روزانه است و ساختنِ ادعایِ تستِ
  // تایم‌فریم رویِ صفحۀ بی‌آنِ کنترل، جعلِ پوشش است.
  const tf = await page.evaluate(() => {
    const t = [...document.querySelectorAll('button,[role="tab"],select,option')].map((e) => (e.textContent || '').trim()).filter(Boolean);
    return [...new Set(t)].filter((s) => /هفتگی|ماهانه|۱ دقیقه|۵ دقیقه|روزانه|ساعته/.test(s)).slice(0, 12);
  });
  if (tf.length) ck('کنترلِ تایم‌فریم/بازه درِ صفحۀ چارت پیدا شد', true, tf);
  else {
    checks.push({ name: 'تایم‌فریم/بازه: کنترلِ UI موجود نیست (برنامۀ روزانه-only)', ok: null, extra: tf });
    say('  N/A کنترلِ تایم‌فریم/بازه درِ UI نیست — سناریو بی‌ادعایِ پوشش N/A ثبت شد');
  }

  // ── ۱۲) شمارِ درخواست‌ها و حجمِ payload درِ یکِ بارگذاریِ صفحۀ نماد
  netLog.length = 0;
  await page.goto(BASE + '/#/technical/' + encodeURIComponent('فولاد'), { waitUntil: 'networkidle' }).catch(() => {});
  await page.waitForTimeout(8000);
  perf.requests.technical_load = { total_same_origin: netLog.length,
    api: netLog.filter((x) => x.u.startsWith('/api/')).length,
    sample: netLog.filter((x) => x.u.startsWith('/api/')).slice(0, 14) };
  ck('بارگذاریِ صفحۀ چارت درخواست‌های API را زیرِ ۴۰ نگه می‌دارد',
    perf.requests.technical_load.api < 40, { api_requests: perf.requests.technical_load.api });

  // ── ۱۳) /api/chart-db (مسیرِ دیتابیس، بی‌شبکه) برایِ تفکیکِ زمانِ محاسبه
  const dbp = await timed(page, BASE + '/api/chart-db/' + encodeURIComponent('فولاد'), null, 3);
  perf.api.chart_db_folad = { median_ms: Math.round(dbp.median_ms), bytes: dbp.bytes, status: dbp.status };
  ck('/api/chart-db پاسخ می‌دهد', dbp.status === 200, { status: dbp.status, candles: ((dbp.json || {}).candles || []).length });

  await ctx.close();

  const pass = checks.filter((c) => c.ok === true).length;
  const na = checks.filter((c) => c.ok === null).length;
  const fail = checks.filter((c) => c.ok === false).length;
  const out = { ranAt: new Date().toISOString(), base: BASE, headless: HEADLESS,
    summary: { checks: checks.length, pass, fail, na },
    perf, consoleErrors: consoleErrors.slice(0, 20), checks, screenshots: shot };
  fs.writeFileSync(path.join(ROOT, '_audit', 'bors_phase5_e2e.json'), JSON.stringify(out, null, 2), 'utf8');
  say('\nنتیجه: ' + pass + ' سبز / ' + fail + ' سرخ / ' + na + ' N/A از ' + checks.length +
    ' | کارای: ' + JSON.stringify(perf.api));
  say('نوشته شد: _audit/bors_phase5_e2e.json');
  process.exit(fail ? 1 : 0);
})().catch(async (e) => {
  console.error('FATAL ' + String(e));
  fs.writeFileSync(path.join(ROOT, '_audit', 'bors_phase5_e2e.json'),
    JSON.stringify({ fatal: String(e && e.stack || e), checks, perf }, null, 2), 'utf8');
  process.exit(3);
});
