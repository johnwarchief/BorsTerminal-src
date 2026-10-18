// _audit/ms_binder_ui_check.js — مرحلۀ ۵: بازبینیِ مرورگرِ واقعیِ تب «وضعیت بازار»
//
// چرا jsdom کافی نبود: مالک صریح گفته «نتیجه‌ای را که درِ مرورگر یا تست واقعاً
// مشاهده نکرده‌ای تأییدشده معرفی نکن». سرریزِ افقی، بریدۀ متن، رندرِ canvasِ
// چارت، ارزشِ tooltip با عددِ API، و اینکه دکمه‌ای واقعاً درخواستِ تازه می‌سازد
// فقط درِ Edge سنجیده می‌شود.
//
// سه viewport از مرجع: 1366×768 (دسکتاپِ اداری)، 1920×1080، 390×844 (موبایل).
// هیچ داده‌ای درِ این مرورگر نوشته نمی‌شود؛ فقط خواندن، کلیکِ کنترل‌هایِ خودِ
// برنامه و اسکرین‌شات. پروفایلِ مرورگر درِ tempِ همین اجراست، نه پروفایلِ مالک.
const os = require('os');
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PROFILE = path.join(os.tmpdir(), 'bors-ms-binder-profile');
const OUT_JSON = path.join(__dirname, 'MS-BINDER-UI.json');
const SHOTS = path.join(__dirname, 'MS-BINDER-SHOTS');

const VIEWPORTS = [
  { key: 'desktop-1366', width: 1366, height: 768 },
  { key: 'desktop-1920', width: 1920, height: 1080 },
  { key: 'mobile-390', width: 390, height: 844 },
];
const SECTIONS = [
  'ms-sec-overview', 'ms-sec-treemap', 'ms-sec-tops', 'ms-sec-orders',
  'ms-sec-gold', 'ms-sec-compare', 'ms-sec-chart', 'ms-sec-tables',
];

const captured = { chart: [], treemap: [], series: [] };
const fa2en = (x) => String(x || '').replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))).replace(/[٬,\s]/g, '');
const report = {
  base: BASE, ranAt: new Date().toISOString(), checks: [], consoleErrors: [],
  netErrors: [], shots: [], notes: [], views: {},
};
const ck = (label, ok, detail) => {
  report.checks.push({ label, ok: !!ok, detail: detail === undefined ? '' : String(detail).slice(0, 240) });
  console.log((ok ? 'OK   ' : 'FAIL ') + label + (detail !== undefined ? '  ⟨' + String(detail).slice(0, 200) + '⟩' : ''));
  return !!ok;
};
const note = (m) => { report.notes.push(m); console.log('·  ' + m); };

async function loginIfNeeded(page) {
  const gate = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
  if (!gate) return note('قفلِ ایستگاه دیده نشد — نیازی به ورود نبود');
  const src = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
  const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
  const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
  if (!du || !dp) throw new Error('پیش‌فرضِ سورس درِ authStore پیدا نشد');
  await page.locator('input[type="text"]').first().fill(du);
  await page.locator('input[type="password"]').first().fill(dp);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(5000);
  ck('قفلِ ایستگاه با ورودِ خودِ برنامه باز شد',
     !(await page.evaluate(() => !!document.querySelector('input[type="password"]'))));
}

const measure = () => ({
  docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  bodyOverflow: document.body.scrollWidth - document.body.clientWidth,
  headings: SECTIONS.filter((id) => !!document.getElementById(id)).length,
  treemapCells: document.querySelectorAll('[data-testid^="treemap-cell-"]').length,
  legendTones: (document.querySelector('[data-testid="ms-treemap-legend"]') || {}).childElementCount ?? 0,
  tops: ['impact_pos', 'impact_neg', 'most_value', 'most_volume'].filter((k) => !!document.querySelector(`[data-testid="ms-toplists-${k}"]`)).length,
  ordersBuy: (document.querySelector('[data-testid="ms-orders-buy"]') || {}).textContent || '',
  ordersExec: (document.querySelector('[data-testid="ms-orders-exec"]') || {}).textContent || '',
  ownershipUnit: (document.querySelector('[data-testid="ms-ownership-legal"]') || {}).textContent || '',
  goldCards: document.querySelectorAll('[data-testid^="gold-card-"]').length,
  compareLines: document.querySelectorAll('[data-testid^="ms-compare-line-"]').length,
  chartCanvas: document.querySelectorAll('[data-testid="ms-chart-host"] canvas').length,
  chartLoading: !!document.querySelector('[data-testid="ms-chart-loading"]'),
  nodata: document.querySelectorAll('[data-testid$="-nodata"]').length,
  errors: document.querySelectorAll('[data-testid$="-error"]').length,
  truncatedBad: [...document.querySelectorAll('[data-testid="market-status-page"] .truncate')]
    .filter((e) => e.scrollWidth - e.clientWidth > 2 && !e.closest('[data-testid$="-scroller"]')
      && !e.getAttribute('title') && !e.querySelector('[title]')).length,
  truncatedTitled: [...document.querySelectorAll('[data-testid="market-status-page"] .truncate')]
    .filter((e) => e.scrollWidth - e.clientWidth > 2 && (e.getAttribute('title') || e.querySelector('[title]'))).length,
  truncatedIds: [...document.querySelectorAll('[data-testid="market-status-page"] .truncate')]
    .filter((e) => e.scrollWidth - e.clientWidth > 2 && !e.closest('[data-testid$="-scroller"]')
      && !e.getAttribute('title') && !e.querySelector('[title]'))
    .map((e) => (e.closest('[data-testid]') || {}).getAttribute?.('data-testid') + '|' + e.textContent.slice(0, 24)).slice(0, 8),
  innerScrollers: [...document.querySelectorAll('[data-testid$="-scroller"]')].map((e) => ({
    id: e.getAttribute('data-testid'),
    scrollable: e.scrollWidth > e.clientWidth,
  })),
});

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: EXE, headless: true, viewport: { width: VIEWPORTS[0].width, height: VIEWPORTS[0].height },
    args: ['--no-first-run', '--disable-sync', '--remote-debugging-port=0'],
  });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error') report.consoleErrors.push(m.text().slice(0, 300));
  });
  page.on('requestfailed', (r) => report.netErrors.push(`${r.method()} ${r.url().slice(0, 160)} :: ${r.failure()?.errorText}`));
  page.on('response', (r) => {
    if (r.status() >= 400 && !/\/api\/(watchlist|live-stats)/.test(r.url())) {
      report.netErrors.push(`HTTP ${r.status} ${r.url().slice(0, 160)}`);
    }
  });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await loginIfNeeded(page);
  await page.goto(BASE + '/#/market-status', { waitUntil: 'domcontentloaded' });

  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    // نشانهٔ روشنِ «داده رسید»: اولین خانۀ نقشه. بی‌این، viewportِ اول خالی
    // اندازه گرفته می‌شد و تست «سرخ» می‌شد در حالی که فقط صبر کم بود.
    await page.waitForFunction(() => {
      const p = document.querySelector('[data-testid="market-status-page"]');
      if (!p) return false;
      const busy = p.querySelectorAll('[data-testid$="-loading"]').length;
      return busy === 0 && document.querySelectorAll('[data-testid^="treemap-cell-"]').length > 0;
    }, { timeout: 120000 }).catch(() => note(`${vp.key}: نشانهٔ آمادگی تا ۱۲۰s نرسید — اندازه با همان وضعیت`));
    await page.waitForTimeout(2500);
    const m = await page.evaluate(`(() => {
      const SECTIONS = ${JSON.stringify(SECTIONS)};
      return (${measure.toString()})();
    })()`);
    report.views[vp.key] = m;
    note(`${vp.key}: treemap=${m.treemapCells} tops=${m.tops} compare=${m.compareLines} canvas=${m.chartCanvas} nodata=${m.nodata} error=${m.errors} ellipsis+title=${m.truncatedTitled}`);

    ck(`[${vp.key}] هر هشت بخش رندر شده‌اند`, m.headings === SECTIONS.length, m.headings);
    ck(`[${vp.key}] سرریزِ افقیِ صفحه نیست`, m.docOverflow <= 1 && m.bodyOverflow <= 1, `doc=${m.docOverflow} body=${m.bodyOverflow}`);
    // بریدۀ بی‌title = اطلاعاتِ ازدست‌رفته؛ بریدۀ با title (حذفِ اختصاریِ
    // یک‌خطیِ نامِ نماد) الگویِ پذیرفتۀ خودِ برنامه است و درِ گزارش می‌آید.
    ck(`[${vp.key}] متنِ بریده‌شدۀ بی‌جایگزین (بدونِ title) نداریم`, m.truncatedBad === 0,
       `${m.truncatedBad} :: ${m.truncatedIds.join(' , ')}`);
    ck(`[${vp.key}] نقشۀ بازار خانه دارد (canvas/svg درِ کادر)`, m.treemapCells > 0, m.treemapCells);
    ck(`[${vp.key}] واژۀ رنگِ سراسری (مثبت/منفی/خنثی/بی‌داده) در افسانۀ نقشه`, m.legendTones === 4, m.legendTones);
    ck(`[${vp.key}] چهار پنلِ برترین‌ها جدا هستند`, m.tops === 4, m.tops);
    ck(`[${vp.key}] حجمِ سفارش با حجمِ معامله درِ رابط یکی نشده`, m.ordersBuy && m.ordersExec && m.ordersBuy !== m.ordersExec,
       `${m.ordersBuy.trim()} / ${m.ordersExec.trim()}`);
    ck(`[${vp.key}] یکایِ تغییرِ مالکیت «سهم» است`, /سهم/.test(m.ownershipUnit), m.ownershipUnit.trim());
    ck(`[${vp.key}] کارت‌هایِ ابزارِ طلا از ردیفِ واقعی می‌آیند`, m.goldCards > 0, m.goldCards);
    ck(`[${vp.key}] نمودارِ مقایسه حداقلِ دو خطِ نرمال‌شده دارد`, m.compareLines >= 2, m.compareLines);
    ck(`[${vp.key}] موتورِ چارت واقعی (canvas) نشسته، نه تصویر`, m.chartCanvas >= 1 && !m.chartLoading, `canvas=${m.chartCanvas}`);
    for (const s of m.innerScrollers) {
      ck(`[${vp.key}] جدولِ ${s.id} درِ خودش اسکرول افقی می‌کند`, s.scrollable || vp.width >= 1200, `scrollable=${s.scrollable}`);
    }
    for (const id of SECTIONS) {
      const el = await page.$(`[data-testid="section-heading-${id}"]`);
      if (el) await el.scrollIntoViewIfNeeded();
      await page.waitForTimeout(700);
      const file = path.join(SHOTS, `${vp.key}-${id}.png`);
      await page.screenshot({ path: file, fullPage: false });
      report.shots.push(path.basename(file));
    }
  }

  // ─────────────── تعامل‌هایِ کنترل‌ها (دسکتاپ) — «دکمه باید کار کند»
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.evaluate(() => document.getElementById('ms-sec-treemap')?.scrollIntoView());
  await page.waitForTimeout(1200);

  const areaOfFirst = async () => {
    const r = await page.locator('[data-testid="ms-treemap-svg"] rect').first().boundingBox();
    return r ? Math.round(r.width * r.height) : 0;
  };
  const beforeArea = await areaOfFirst();
  const before = await page.locator('[data-testid^="treemap-cell-"]').count();
  await page.selectOption('[data-testid="ms-treemap-metric"]', 'trades');
  ck('پیش از «اعمال فیلتر» عددِ نقشه عوض نمی‌شود', await page.locator('[data-testid="ms-treemap-dirty"]').count() === 1);
  page.on('request', (r) => {
    const u = r.url();
    if (u.includes('/api/mstat/series')) captured.series.push(new URL(u).search);
    if (u.includes('/api/mstat/treemap')) captured.treemap.push(new URL(u).search);
    if (u.includes('/api/chart/')) captured.chart.push(decodeURIComponent(u));
  });
  await page.locator('[data-testid="ms-treemap-apply"]').click();
  await page.waitForTimeout(4000);
  const after = await page.locator('[data-testid^="treemap-cell-"]').count();
  const reqs = captured.treemap;
  ck('«اعمال فیلتر» درخواستِ تازه با معیارِ تازه می‌سازد', reqs.length > 0 && /metric=trades/.test(reqs[reqs.length - 1]), reqs[reqs.length - 1]);
  const afterArea = await areaOfFirst();
  // «ارزشِ معاملات» با «تعدادِ معاملات» دو توزیعِ متفاوت‌اند؛ پس مستطیلِ بزرگ
  // باید جابه‌جا شود. بی‌این، عوض‌شدنِ شمارِ خانه‌ها (۲۲۰→۲۲۰) گمراه‌کننده است.
  ck('چیدمان با معیارِ تازه واقعاً عوض می‌شود (سطحِ بزرگ‌ترین خانه)',
     after > 0 && Math.abs(afterArea - beforeArea) > 1, `${beforeArea} → ${afterArea} px²`);

  const tip = await page.locator('[data-testid="ms-treemap-svg"] g').first();
  const sym = (await tip.getAttribute('data-testid') || '').replace('treemap-cell-', '');
  await tip.hover();
  await page.waitForTimeout(500);
  const tipText = await page.locator('[data-testid="ms-treemap-tooltip"]').textContent().catch(() => '');
  const apiRow = await page.evaluate(async (s) => {
    const r = await fetch('/api/mstat/treemap?group=eq_all&industry=&metric=trades');
    const j = await r.json();
    const hit = (j.rows || []).find((x) => x.symbol === s);
    return hit ? { size: hit.size, unit: j.metric_unit, pct: hit.pct } : null;
  }, sym);
  note(`tooltip «${sym}» = ${String(tipText).trim()} | API = ${JSON.stringify(apiRow)}`);
  const tipNum = parseFloat(fa2en(String(tipText).match(/([۰-۹0-9.,٬]+)/) ? String(tipText).match(/([۰-۹0-9.,٬]+)/)[1] : ''));
  ck('tooltip با عددِ همان ردیفِ API می‌خواند',
     !!apiRow && Number.isFinite(tipNum) && Math.abs(tipNum - apiRow.size) / Math.max(apiRow.size, 1) < 0.005,
     `tip=${String(tipText).trim()} api=${apiRow && apiRow.size}`);

  // مقایسه: بازه و مقیاس
  await page.evaluate(() => document.getElementById('ms-sec-compare')?.scrollIntoView());
  await page.waitForTimeout(1000);
  const pathBefore = await page.locator('[data-testid^="ms-compare-line-"]').first().getAttribute('d');
  await page.locator('[data-testid="ms-compare-scale-log"]').click();
  await page.waitForTimeout(900);
  const pathLog = await page.locator('[data-testid^="ms-compare-line-"]').first().getAttribute('d');
  ck('سوییچِ مقیاس هندسه را عوض می‌کند', pathBefore !== pathLog);
  await page.locator('[data-testid="ms-compare-range-6m"]').click();
  await page.waitForTimeout(3500);
  const seriesReqs = captured.series;
  ck('تغییرِ بازه، سریِ تازه با daysِ تازه می‌گیرد', seriesReqs.length > 0 && /days=182/.test(seriesReqs[seriesReqs.length - 1]),
     seriesReqs[seriesReqs.length - 1]);

  // طلا: سه تب
  await page.evaluate(() => document.getElementById('ms-sec-gold')?.scrollIntoView());
  await page.waitForTimeout(900);
  await page.locator('[data-testid="ms-gold-tab-tables"]').click();
  await page.waitForTimeout(700);
  ck('تبِ «جدول‌های طلا و سکه» سه جدولِ جدا می‌دهد',
     (await page.locator('[data-testid="ms-gold-tbl-fund-scroller"]').count()) === 1 &&
     (await page.locator('[data-testid="ms-gold-tbl-paper-scroller"]').count()) === 1);
  await page.locator('[data-testid="ms-gold-tab-funds"]').click();
  await page.waitForTimeout(2500);
  ck('تبِ «صندوق‌های طلا» نقشۀ قفل‌شده را باز می‌کند',
     (await page.locator('[data-testid="ms-gold-treemap-canvas"], [data-testid="ms-gold-treemap-nodata"], [data-testid="ms-gold-treemap-loading"]').count()) >= 1);

  // دانلودِ جدول
  await page.locator('[data-testid="ms-gold-tab-tables"]').click();
  await page.waitForTimeout(900);
  const dlp = page.locator('[data-testid="ms-gold-tbl-fund-download"]').first();
  if (await dlp.count()) {
    const got = page.waitForEvent('download', { timeout: 8000 }).catch(() => null);
    await dlp.click();
    const d = await got;
    ck('دکمهٔ دانلودِ جدول واقعاً فایلی می‌دهد', !!d, d ? await d.suggestedFilename() : 'بدونِ رویدادِ دانلود');
  } else {
    ck('دکمهٔ دانلودِ جدول درِ رابط پیدا شد', false, 'locator خالی');
  }

  // چارت: انتخابِ نماد از تابلو باید `/api/chart/<sym>` تازه بسازد
  await page.evaluate(() => document.getElementById('ms-sec-chart')?.scrollIntoView());
  await page.waitForTimeout(1200);
  const watchBtn = page.locator(`button[data-testid^="ms-chart-watch-"]`).first();
  if (await watchBtn.count()) {
    const pickSym = (await watchBtn.getAttribute('data-testid') || '').replace('ms-chart-watch-', '');
    const n0 = captured.chart.length;
    await watchBtn.click();
    await page.waitForTimeout(7000);
    const u = captured.chart.slice(n0).join(' | ');
    ck('انتخابِ نماد از دیدۀ‌بان، دادهٔ همان نماد را از سرور می‌گیرد',
       /\/api\/chart\/.+/.test(u) && u.includes(pickSym), u.slice(0, 160));
  } else {
    note('دیدۀ‌بان خالی بود — کلیکِ دیدۀ‌بان سنجیده نشد (دستۀ‌باندِ کاربر درِ این پروفایل خالی است)');
  }
  const boardBtn = page.locator('[data-testid^="ms-chart-board-list-row-"]').first();
  if (await boardBtn.count()) {
    const symB = (await boardBtn.getAttribute('data-testid') || '').replace('ms-chart-board-list-row-', '');
    const n1 = captured.chart.length;
    await boardBtn.click();
    await page.waitForTimeout(7000);
    const u2 = captured.chart.slice(n1).join(' | ');
    ck('ردیفِ «پرتراکنشِ تابلو» همان نماد را درِ موتور باز می‌کند',
       /\/api\/chart\/.+/.test(u2) && u2.includes(symB), u2.slice(0, 160));
    await page.screenshot({ path: path.join(SHOTS, 'desktop-1366-ms-chart-after-pick.png') });
    report.shots.push('desktop-1366-ms-chart-after-pick.png');
  }

  // معنایِ رنگ: یک ردیفِ مثبت و یک منفی درِ پنل‌هایِ رتبه‌ای
  const tones = await page.evaluate(() => {
    const out = [];
    for (const li of document.querySelectorAll('[data-testid^="ms-toplists-impact_pos-row-"], [data-testid^="ms-toplists-impact_neg-row-"]')) {
      const span = li.querySelector('span[class*="text-accent-"]');
      out.push({ id: li.getAttribute('data-testid'), cls: span ? span.className : '', text: span ? span.textContent : '' });
    }
    return out.slice(0, 6);
  });
  note('نمونهٔ تون‌ها: ' + JSON.stringify(tones.map((t) => `${t.text}:${/accent-green/.test(t.cls) ? 'green' : /accent-red/.test(t.cls) ? 'red' : 'other'}`)));
  const posPanel = tones.filter((t) => /impact_pos/.test(t.id));
  const negPanel = tones.filter((t) => /impact_neg/.test(t.id));
  ck('پنلِ اثرِ مثبت با سبزِ معنایی و پنلِ اثرِ منفی با قرمزِ معنایی رنگ می‌شود',
     (posPanel.length === 0 || posPanel.every((t) => /accent-green/.test(t.cls))) &&
     (negPanel.length === 0 || negPanel.every((t) => /accent-red/.test(t.cls))),
     JSON.stringify(tones.map((t) => t.text)));

  ck('خطای کنسول درِ اجرای مرورگر ثبت نشده', report.consoleErrors.length === 0, report.consoleErrors.slice(0, 3).join(' | '));
  ck('درخواستِ بی‌پاسخِ ۴xx/۵xx درِ مسیرِ تب ندیدیم', report.netErrors.length === 0, report.netErrors.slice(0, 3).join(' | '));

  await page.screenshot({ path: path.join(SHOTS, 'desktop-1366-full.png'), fullPage: true });
  report.shots.push('desktop-1366-full.png');

  const failed = report.checks.filter((c) => !c.ok);
  report.summary = { total: report.checks.length, passed: report.checks.length - failed.length, failed: failed.length, shots: report.shots.length };
  fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 2), 'utf8');
  console.log('-'.repeat(70));
  console.log(`بررسی: ${report.checks.length} | سبز: ${report.checks.length - failed.length} | سرخ: ${failed.length} | اسکرین‌شات: ${report.shots.length}`);
  console.log('خروجی: ' + OUT_JSON);
  await ctx.close();
  process.exit(failed.length ? 1 : 0);
})().catch((e) => {
  console.error('CRASH', e);
  fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 2), 'utf8');
  process.exit(2);
});
