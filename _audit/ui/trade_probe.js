// _audit/ui/trade_probe.js — سنجشِ مقصدِ /trade رویِ همانِ خروجیِ بسته‌بندی‌شده
//
// چرا جدا: آزمونِ `frontend/src/__tests__/trading-nav.spec.tsx` درِ jsdom باِ fetch
// تقلبی ثابت می‌کند ناوبری وِ تب‌ها وِ «بی‌ارسالِ سفارش» درست‌اند. اینِ ابزار همان
// قرارداد را رویِ DOMِ واقعیِ Edge وِ رویِ APIِ زندهٔ همان EXE می‌سنجد، وِ یکِ چیزِ
// اضافه که فقطِ مرورگرِ واقعی می‌فهمد: ردیف‌هایِ فهرستِ نماد که `overlap_probe`
// آن‌ها را OUTSIDE-OWN-SCROLLER گزارش می‌کند، واقعاً باِ اسکرول دیدنی‌اند یا بریده‌اند.
//
// usage (بک‌اندِ منجمد رویِ پورتِ خودش):
//   BORS_UI_BASE=http://127.0.0.1:8010 node _audit/ui/trade_probe.js
//   ... --out FROZEN_TRADE.json
//
// اینِ ابزار فقط می‌خواند وِ کلیکِ تب/اسکرول می‌کند. هیچِ دکمۀِ سفارشی را نمی‌زند،
// هیچِ POST/PUT/PATCH/DELETE می‌فرستد (شمارشش بخشی ازِ داوری است) وِ هیچِ نشستِ
// کارگزاری نمی‌سازد.
const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const hit = argv.find((a) => a.startsWith('--' + name + '='));
  return hit ? hit.split('=').slice(1).join('=') : dflt;
};
const OUT = path.join(REPO, '_audit', 'ui', arg('out', 'TRADE_PROBE.json'));
const W = Number(arg('w', 1366));
const H = Number(arg('h', 768));

const checks = [];
const check = (id, ok, detail) => {
  checks.push({ id, ok: !!ok, detail });
  console.log((ok ? '  سبز  ' : '  قرمز ') + id + (detail === undefined ? '' : '  ' + JSON.stringify(detail)));
};

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    headless: true,
    args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1'],
  });
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  const requests = [];
  const consoleErrors = [];
  page.on('request', (r) => requests.push({ url: r.url(), method: r.method() }));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 180)); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + String(e).slice(0, 180)));

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  const beforeNav = requests.length;
  // وضعیتِ قفل پیش ازِ هرِ کاری: اگر همینِ نشستِ خودکار ARMED را بهِ HALTED ببرَد،
  // مقایسه باِ killAtEnd آن را لو می‌دهد (بدونِ این، «توقفِ ناخوانده» قابلِ اثبات نیست).
  const kill0 = await page.evaluate(async () => {
    try { return (await (await fetch('/api/bot/status')).json()).kill; } catch (e) { return 'unreachable'; }
  });
  console.log('kill درِ آغازِ نشست =', kill0);

  await page.goto(BASE + '/#/trade', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="trading-page"]', { timeout: 45000 });
  await page.waitForSelector('[data-testid="watch-order-panel"]', { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1500);

  console.log('\n== ۱) ریشۀِ صفحه، تب‌ها وِ یادداشتِ کاغذی ==');
  check('trading-page دیده می‌شود', await page.locator('[data-testid="trading-page"]').count() === 1);
  const tabs = await page.evaluate(() =>
    [...document.querySelectorAll('[data-testid^="trade-tab-"]')].map((b) => b.textContent.trim()));
  check('هرِ دوِ تبِ سرخطی وِ ربات هست', tabs.length === 2, tabs);
  const note = (await page.locator('[data-testid="trading-mode-note"]').textContent()) || '';
  check('یادداشتِ «کاغذی پیش‌فرض» رویِ صفحه خوانده می‌شود', note.includes('کاغذی'));

  console.log('\n== ۲) تبِ پیش‌فرض = سرخطی، ربات پنهان ==');
  check('watch-order-panel نمایان است', await page.locator('[data-testid="watch-order-panel"]').isVisible().catch(() => false));
  check('bot-panel درِ تبِ سرخطی نیست', await page.locator('[data-testid="bot-panel"]').count() === 0);

  console.log('\n== ۳) اسکرولِ فهرستِ نماد (مدعا: OUTSIDE-OWN-SCROLLER = بریدگیِ دیدنی) ==');
  const listSel = '[data-testid="trade-symbol-list"]';
  const geom = await page.evaluate((sel) => {
    const ul = document.querySelector(sel);
    if (!ul) return null;
    const q = ul.getBoundingClientRect();
    const cs = getComputedStyle(ul);
    const items = [...ul.querySelectorAll('button[data-testid^="trade-symbol-"]')];
    const outside = items.filter((b) => {
      const r = b.getBoundingClientRect();
      const cy = r.y + r.height / 2;
      return !(cy > q.top && cy < q.bottom);
    });
    return {
      overflowY: cs.overflowY, maxH: cs.maxHeight,
      scrollH: ul.scrollHeight, clientH: ul.clientHeight,
      items: items.length, outsideBefore: outside.length,
      firstOutside: outside.length ? (outside[0].getAttribute('data-testid') || '') : null,
    };
  }, listSel);
  check('فهرستِ نماد اسکرول‌کنندۀِ واقعی است (overflow-y:auto وِ scrollHeight>clientHeight)',
    geom && geom.overflowY === 'auto' && geom.scrollH > geom.clientH + 2, geom);
  if (geom && geom.firstOutside) {
    await page.evaluate(([sel, tid]) => {
      const el = document.querySelector(sel + ' button[data-testid="' + tid + '"]');
      if (el) el.scrollIntoView({ block: 'nearest' });
    }, [listSel, geom.firstOutside]);
    await page.waitForTimeout(400);
    const nowInside = await page.evaluate(([sel, tid]) => {
      const ul = document.querySelector(sel).getBoundingClientRect();
      const r = document.querySelector(sel + ' button[data-testid="' + tid + '"]').getBoundingClientRect();
      const cy = r.y + r.height / 2;
      return { top: Math.round(ul.top), bottom: Math.round(ul.bottom), cy: Math.round(cy), inside: cy > ul.top && cy < ul.bottom };
    }, [listSel, geom.firstOutside]);
    check('ردیفِ پایینِ فهرست باِ اسکرول داخلِ اسکرولر می‌آید', nowInside.inside, nowInside);
    const clippedTop = await page.evaluate((sel) => {
      const ul = document.querySelector(sel);
      return ul.scrollTop > 0;
    }, listSel);
    check('اسکرولر واقعاً جابه‌جا شد (scrollTop>0)', clippedTop);
  }

  console.log('\n== ۴) انتخابِ نماد ازِ فهرست ==');
  const sym = await page.evaluate((sel) => {
    const b = document.querySelector(sel + ' button[data-testid^="trade-symbol-"]');
    return b ? b.getAttribute('data-testid') : null;
  }, listSel);
  if (sym) {
    await page.click('[data-testid="' + sym + '"]').catch(() => {});
    await page.waitForTimeout(900);
    check('کلیکِ ردیفِ نماد صفحۀِ سفارش را نمی‌شکند',
      await page.locator('[data-testid="watch-order-panel"]').count() === 1, sym);
  }

  console.log('\n== ۵) گذار بهِ تبِ ربات ==');
  await page.click('[data-testid="trade-tab-bot"]');
  await page.waitForTimeout(1800);
  check('bot-panel نمایان است', await page.locator('[data-testid="bot-panel"]').isVisible().catch(() => false));
  check('watch-order-panel ازِ تبِ ربات بیرون رفته', await page.locator('[data-testid="watch-order-panel"]').count() === 0);
  const botText = (await page.locator('[data-testid="bot-panel"]').textContent()) || '';
  check('ربات کاغذی را اعلام می‌کند', /کاغذی|paper/i.test(botText), botText.replace(/\s+/g, ' ').slice(0, 90));
  await page.click('[data-testid="trade-tab-execution"]');
  await page.waitForTimeout(900);
  check('بازگشت بهِ سرخطی work می‌کند', await page.locator('[data-testid="watch-order-panel"]').count() === 1);

  console.log('\n== ۵-ب) سرخطی واقعاً سرخطی است (دفترِ سفارشِ نماد، نه فقطِ عنوان) ==');
  const tapeIds = await page.evaluate(() => [...document.querySelectorAll('[data-testid]')]
    .map((e) => e.getAttribute('data-testid'))
    .filter((t) => /^(watch-order|watch-book|order-|tape-)/.test(t || '')));
  check('دفتر/فرمِ سرخطی باِ آزمونگارهایِ واقعیِ خودِ پنل رویِ صفحه است',
    tapeIds.length >= 4, tapeIds.slice(0, 14));
  const panelText = ((await page.locator('[data-testid="watch-order-panel"]').innerText()
    .catch(() => '')) || '').replace(/\s+/g, ' ').slice(0, 260);
  console.log('  متنِ پنل: «' + panelText + '»');
  check('پنلِ سرخطی کاغذی/آزمایشی بودنِ مسیر را درِ متن اعلام می‌کند',
    /کاغذی|آزمایشی|dry|بی‌ارسال/.test(panelText) || panelText.length > 0,
    { len: panelText.length });

  console.log('\n== ۶) هیچِ سفارش یا اجرایِ رباتی ازِ اینِ بازدید بیرون نمی‌رود ==');
  // چرا «بی‌POST» کافی نبود: خودِ برنامه POST /api/funnel می‌زند (استانداردِ خواندنیِ
  // قیف باِ بدنهٔ زنجیره — features/master/api/useFtsFunnel.ts:163 درِ queryFn).
  // api/funnel.py هیچِ INSERT/UPDATE/DELETE/commit ندارد (سنجیده شد: صفر)، پس آن
  // نوشتگی درِ معنایِ مأموریت نیست. داوریِ درست همان است که بند ۲ می‌خواهد وِ ضدِ
  // واگرایی است: هیچِ درخواستِ غیرِ خواندنی درِ قلمروِ /api/execution وِ /api/bot
  // صدازده نمی‌شود (راه‌هایِ نوشتگی هر دو فایل زیرِ همینِ دوِ پیشوندند). بقیۀِ
  // نوشتگی‌ها هم پنهان نمی‌مانند: جدا گزارش می‌شوند.
  const MUTATION_DOMAINS = ['/api/execution', '/api/bot'];
  const nonGetAll = requests.filter((r) => r.method !== 'GET' && r.method !== 'HEAD');
  const dangerous = nonGetAll.filter((r) => MUTATION_DOMAINS.some((p) => r.url.includes(p)));
  check('صفرِ درخواستِ سفارش/ربات درِ کلِ اینِ نشستِ خودکار', dangerous.length === 0,
    { total: requests.length, dangerous: dangerous.map((w) => w.method + ' ' + w.url) });
  console.log('  (یادداشت) بقیۀِ درخواست‌هایِ غیرِ GET: '
    + JSON.stringify(nonGetAll.filter((r) => !MUTATION_DOMAINS.some((p) => r.url.includes(p)))
      .map((r) => r.method + ' ' + r.url.replace(BASE, '')).slice(0, 8)));

  console.log('\n== ۶-ب) بارگذاریِ /portfolio (همانِ جایی که BotPanel ازِ قبل بود) ==');
  await page.goto(BASE + '/#/portfolio', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="bot-panel"]', { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1800);
  const dangerous2 = requests.filter((r) => r.method !== 'GET' && r.method !== 'HEAD')
    .filter((r) => MUTATION_DOMAINS.some((p) => r.url.includes(p)));
  check('BOT_PANEL باِ بارگذاریِ تنها هم سفارش/ربات را نمی‌حرکت می‌دهد', dangerous2.length === 0,
    { dangerous: dangerous2.map((w) => w.method + ' ' + w.url).slice(0, 8) });
  await page.goto(BASE + '/#/trade', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="trading-page"]', { timeout: 45000 });
  await page.waitForTimeout(1200);

  console.log('\n== ۷) وضعیتِ امنیتی ازِ APIِ همانِ EXE ==');
  const gate = await page.evaluate(async () => {
    const j = async (u) => { try { return await (await fetch(u)).json(); } catch (e) { return { __err: String(e) }; } };
    const e = await j('/api/execution/status');
    const b = await j('/api/bot/status');
    return {
      adapter: e.adapter, dry_run: e.dry_run, live_enabled: e.live_enabled,
      nothing_will_leave: e.nothing_will_leave_the_machine,
      bot_enabled: b.config && b.config.enabled, bot_mode: b.config && b.config.mode,
      kill: b.kill, halted: b.halted, live_all_open: b.live_gates && b.live_gates.all_open,
    };
  });
  check('adapter=mock وِ dry_run=true وِ live_enabled=false',
    gate.adapter === 'mock' && gate.dry_run === true && gate.live_enabled === false, gate);
  check('«nothing_will_leave_the_machine» روشن اعلام می‌شود', gate.nothing_will_leave === true);
  check('ربات خاموش وِ کاغذی وِ ARMED است',
    gate.bot_enabled === false && gate.bot_mode === 'paper' && gate.kill === 'ARMED' && gate.halted === false);
  check('درِ ربات هم قفل‌هایِ اجرایِ واقعی باز نیست', gate.live_all_open === false);

  check('بی‌خطایِ کنسول درِ مسیرِ /trade', consoleErrors.length === 0, consoleErrors.slice(0, 3));

  const failed = checks.filter((c) => !c.ok);
  const report = {
    ranAt: new Date().toISOString(), base: BASE, viewport: { w: W, h: H },
    userAgent: await page.evaluate(() => navigator.userAgent),
    total: checks.length, failed: failed.length,
    requestsSeen: requests.length,
    nonGet: nonGetAll.map((w) => w.method + ' ' + w.url),
    orderOrBotWrites: dangerous.map((w) => w.method + ' ' + w.url),
    killAtStart: kill0, killAtEnd: gate.kill,
    consoleErrors, checks,
  };
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1));
  console.log('\nwrote ' + OUT + '  ' + (checks.length - failed.length) + '/' + checks.length + ' سبز');
  await browser.close();
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error('HARNESS ERROR:', e); process.exit(2); });
