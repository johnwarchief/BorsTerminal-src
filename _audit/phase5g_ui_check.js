// _audit/phase5g_ui_check.js — قدمِ ۵/۷: مسیرِ تعدیل درِ مرورگرِ واقعی، هر دو موتورِ چارت
// چرا: گاردهای jsdom (technical-settings-effectiveness.spec.tsx) ثابت می‌کنند تنظیمات به
// API کتابخانه *می‌رسد*؛ اما «کدام سری رویِ محور است» فقط درِ مرورگر سنجیده می‌شود.
// قاعدۀ مأموریت: چیزی که درِ مرورگر دیده نشده را تأییدشده معرفی نکن.
//
// روش (بی‌حدس، بی‌کلیکِ شانسی):
//   ۱) نمونهٔ مرجع = همان پاسخی که خودِ چارت از `/api/chart/<sym>` می‌گیرد (کندل‌هایِ خام +
//      ضرایبِ سرور). انتظارِ هر حالت از همین دو عدد ساخته می‌شود؛ قاعدۀ دوم درِ تست نمی‌نویسیم.
//   ۲) سریِ دیدنی از *خودِ رندرر* خوانده می‌شود: `chart.getDataList()` (KLineCharts) و
//      `adapter.bars` (موتورِ دوم؛ همان آرایه‌ای که به `series` موتور تزریق می‌شود).
//      این «سریِ خام درست انتخاب شد یا نه» را عدد به عدد می‌سنجد، نه با حدسِ پیکسل.
//   ۳) مسیرِ تعامل: مرکزِ بدنهٔ یک میله با `convertToPixel` + بانگینگِ ویجتِ اصلی محاسبه و
//      کلیک می‌شود؛ سپس خطِ کلیکِ خودِ برنامه (data-testid=chart-click-row) خوانده می‌شود.
//      پیش از هر کلیک لاگِ نشست «پاک» می‌شود، پس ردیفِ دیدنی فقط با کلیکِ واقعی می‌آید.
//      (کلیکِ کور رویِ ۳۴۲۷ میله درِ ~۱۰۰۰ پیکسل، بدنه‌هایِ زیرِ پیکسل — هیچ‌وقت نمی‌خورد.)
//   ۴) حالت‌هایِ «افزایش سرمایه» و «سود نقدی» عمداً غیرفعال‌اند: کلیک باید نه سری را عوض کند
//      و نه نامِ حالت (دکمۀ mock تحویل نمی‌دهیم).
// هیچ داده‌ای درِ این مرورگر نوشته نمی‌شود؛ فقط خواندن و کلیک. لاگِ کلیک درِ پروفایلِ
// موقتِ همین اجرای تست است، نه پروفایلِ مالک.
const os = require('os');
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const SYMBOL = process.env.BORS_UI_SYMBOL || 'فولاژ';
const SYMBOL2 = process.env.BORS_UI_SYMBOL2 || 'فولاد';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PROFILE = path.join(os.tmpdir(), 'bors-phase5g-ui-profile');
const OUT_JSON = path.join(__dirname, 'PHASE5G-UI.json');
const SHOTS = path.join(__dirname, 'PHASE5G-SHOTS');

const fa2en = (s) => String(s || '').replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
  .replace(/[٬,\s]/g, '');
const round2 = (x) => Math.round(x * 100) / 100;

const report = { base: BASE, symbol: SYMBOL, symbol2: SYMBOL2, ranAt: new Date().toISOString(),
                 checks: [], consoleErrors: [], shots: [], notes: [], series: {} };
const note = (m) => { report.notes.push(m); console.log('·  ' + m); };
const ck = (label, ok, detail) => {
  report.checks.push({ label, ok: !!ok, detail });
  console.log((ok ? 'OK   ' : 'FAIL ') + label + (detail ? '  ⟨' + String(detail).slice(0, 200) + '⟩' : ''));
  return !!ok;
};

/** قفلِ ایستگاهِ کاریِ خودِ برنامه (frontend/src/widgets/LoginScreen.tsx).
 *  مقادیر از ثابت‌هایِ کارخانۀِ سورس خوانده می‌شوند — نه از پروفایلِ کاربر.
 *  هیچ رمز/کوکی درِ این فایل یا درِ گزارش نوشته نمی‌شود. */
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
  await page.waitForTimeout(6000);
  const still = await page.evaluate(() => !!document.querySelector('input[type="password"]'));
  ck('قفلِ ایستگاهِ محلی با پیش‌فرضِ سورس باز شد', !still);
}

/** دستهٔ رویدادِ `onCandleBarClick` فقط از `CandleBarView` می‌آید و بدنهٔ میله
 *  `max(1, …)` پیکسل ارتفاع دارد؛ پس باید مختصاتِ خودِ چارت را پرسید. */
const PROBE = () => {
  const test = (which, o) => {
    if (!o || (typeof o !== 'object' && typeof o !== 'function')) return false;
    if (which === 'kc') {
      return typeof o.getDataList === 'function' && typeof o.getSize === 'function'
        && typeof o.convertToPixel === 'function';
    }
    return o.id === 'ffc' && Array.isArray(o.bars) && typeof o.setBars === 'function';
  };
  const cands = (ms) => {
    const out = [ms];
    if (ms && typeof ms === 'object') {
      out.push(ms.current, ms.memoizedState);
      if (Array.isArray(ms)) out.push(ms[0]);
    }
    return out;
  };
  const find = (which) => {
    const hosts = which === 'ffc'
      ? Array.prototype.slice.call(document.querySelectorAll('[data-testid="ffc-chart-host"], [data-testid="ffc-chart-host"] *'))
      : Array.prototype.slice.call(document.querySelectorAll('[k-line-chart-id]'));
    for (const host of hosts) {
      const fk = Object.keys(host).find((k) => k.indexOf('__reactFiber$') === 0);
      if (!fk) continue;
      let fiber = host[fk];
      for (let up = 0; fiber && up < 45; up++) {
        let hook = fiber.memoizedState;
        for (let n = 0; hook && n < 300; n++) {
          for (const c of cands(hook.memoizedState)) if (test(which, c)) return c;
          hook = hook.next;
        }
        if (test(which, fiber.stateNode)) return fiber.stateNode;
        fiber = fiber.return;
      }
    }
    return null;
  };
  window.__bp = { find };
};

const readSeries = (which) => {
  const h = window.__bp.find(which);
  if (!h) return null;
  const list = which === 'ffc' ? h.bars : h.getDataList();
  // کلیدِ تطبیق = تاریخِ ISOِ همان میله (سرور کندل را با `time: 'YYYY-MM-DD'` می‌فرستد
  // و چارت آن را به نیمه‌شبِ UTC می‌برد؛ ترتیبِ آرایه‌ها درِ دو طرف یکی نیست).
  return list.map((b) => {
    const ts = Number(b.timestamp ?? b.time);
    return {
      t: ts, d: new Date(ts).toISOString().slice(0, 10),
      o: Number(b.open), h: Number(b.high), l: Number(b.low), c: Number(b.close),
      v: b.volume == null ? null : Number(b.volume),
    };
  });
};

/** مختصاتِ مرکزِ بدنهٔ میلهٔ i، درِ دستگاهِ مختصاتِ صفحه (CSS px).
 *  منظره را می‌بریم سرِ میله (اسکرول/باراسپیس، نه داده)، صبر می‌کنیم محورِ قیمتِ تازه
 *  بنشیند، و بعد *برگشتِ* مختصات را می‌سنجیم: `convertFromPixel` باید همان dataIndex را
 *  بدهد. بی‌این برگشت، یک اجرایِ کهنه (محورِ پیش از اسکرول) کلیک را به میلهٔ دیگری
 *  یا بیرونِ پنل می‌اندازد و خطِ کلیک بی‌صدا خالی می‌ماند. */
const hitPoint = async (i) => {
  const c = window.__bp.find('kc');
  if (!c) return null;
  const settle = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 200))));
  if (c.getBarSpace().bar < 14) c.setBarSpace(30);
  c.scrollToDataIndex(i, 0);
  await settle();
  const hostEl = document.querySelector('[k-line-chart-id]');
  const r = hostEl.getBoundingClientRect();
  const m = c.getSize('candle_pane', 'main') || { left: 0, top: 0, width: 0, height: 0 };
  const px = (dl, j) => c.convertToPixel(
    [{ dataIndex: j, value: (Number(dl[j].open) + Number(dl[j].close)) / 2 }],
    { paneId: 'candle_pane', absolute: true },
  )[0] || {};
  let j = i, p = {}, back = {};
  for (let k = 0; k < 5; k++) {
    const dl = c.getDataList();
    if (!dl[j]) return null;
    p = px(dl, j);
    back = c.convertFromPixel([{ x: Number(p.x ?? 0), y: Number(p.y ?? 0) }],
                              { paneId: 'candle_pane', absolute: true })[0] || {};
    const bj = Number(back.dataIndex);
    if (bj === j) break;
    if (!Number.isFinite(bj) || bj < 0) return null;
    j = bj;
  }
  const dl = c.getDataList();
  const b = dl[j] || {};
  return {
    x: r.left + Number(m.left ?? 0) + Number(p.x ?? 0),
    y: r.top + Number(p.y ?? 0),
    idx: j, close: Number(b.close),
    d: b.timestamp ? new Date(Number(b.timestamp)).toISOString().slice(0, 10) : null,
    bar: c.getBarSpace().bar,
    inside: Number(p.x ?? 0) >= 0 && Number(p.x ?? 0) <= Number(m.width ?? 0) &&
            Number(p.y ?? 0) >= 0 && Number(p.y ?? 0) <= Number(r.height ?? 0),
  };
};

const ADJ_BTN = 'button[title="نوع تعدیل قیمت"]';

async function adjItems(page) {
  // آیتمِ غیرفعال منو را نبسته می‌کند (`if (!available) return`) — پس اگر باز ماند،
  // کلیکِ بعدیِ دکمه باید آن را ببندد و دوباره باز کند، نه اینکه منو بسته فرض شود.
  if (await page.locator('.nn-dropdown-item').count() === 0) {
    await page.locator(ADJ_BTN).click({ timeout: 8000 });
    await page.waitForTimeout(150);
  }
  const items = await page.locator('.nn-dropdown-item').evaluateAll((els) => els.map((el, i) => ({
    i, label: String(el.textContent || '').slice(0, 40),
    disabled: (el.className || '').indexOf('nn-disabled') >= 0,
    head: String((el.querySelector('span') || {}).textContent || '').trim(),
  })));
  return items;
}

async function closeAdjMenu(page) {
  if (await page.locator('.nn-dropdown-item').count() > 0) {
    await page.locator(ADJ_BTN).click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(150);
  }
}

/** موتورِ چارت درِ `fts.chart.settings.v1` ذخیره می‌شود؛ اجرایِ پیشین می‌تواند چارت را
 *  رویِ موتورِ دوم گذاشته باشد و آن‌گاه `.nn-kline-chart` هرگز سوار نمی‌شود. راهِ بازگشت
 *  درِ خودِ موتورِ دوم است (`data-testid="fts-engine-back"`)، نه نوارِ ابزارِ KLineCharts. */
async function ensureKcEngine(page) {
  const host = page.locator('.nn-kline-chart canvas');
  if (await host.count() > 0) return true;
  const back = page.locator('[data-testid="fts-engine-back"]').first();
  if (await back.count() > 0) {
    note('موتورِ ذخیره‌شده دوم بود — با کلیدِ «بازگشت» روی صحنه برمی‌گردیم');
    await back.click({ timeout: 8000 }).catch((e) => note('بازگشت ناموفق: ' + e.message));
    await page.waitForTimeout(3000);
  }
  return (await host.count()) > 0;
}

/** آیتم‌هایِ فعال به همان ترتیبِ سورس؛ هویتشان را از سریِ عددی می‌سنجیم، نه از برچسب */
async function pickMode(page, enabledIndex) {
  const items = await adjItems(page);
  const enabled = items.filter((x) => !x.disabled);
  const want = enabled[enabledIndex];
  if (!want) throw new Error('آیتمِ فعالِ شمارهٔ ' + enabledIndex + ' پیدا نشد');
  await page.locator('.nn-dropdown-item').nth(want.i).click({ timeout: 8000 });
  await page.waitForTimeout(900);
  const badge = String(await page.locator(ADJ_BTN).innerText()).trim();
  return { head: want.head, badge };
}

async function clickDisabled(page, labelPart) {
  const items = await adjItems(page);
  const off = items.filter((x) => x.disabled);
  const want = off.find((x) => String(x.head).indexOf(labelPart) >= 0);
  if (!want) return { found: false, offCount: off.length };
  await page.locator('.nn-dropdown-item').nth(want.i).click({ timeout: 8000 });
  await page.waitForTimeout(700);
  const badge = String(await page.locator(ADJ_BTN).innerText()).trim();
  return { found: true, offCount: off.length, head: want.head, badge };
}

/** خطِ کلیک: پیش از آن لاگِ نشست را پاک کن تا ردیفِ دیدنی فقط از کلیکِ واقعی بیاید */
async function resetClickLog(page) {
  const chip = page.locator('[data-testid="chart-click-chip"]').first();
  const expanded = await chip.getAttribute('aria-expanded').catch(() => null);
  if (expanded !== 'true') await chip.click({ timeout: 8000 }).catch(() => {});
  const clr = page.locator('[data-testid="chart-click-clear"]');
  if (await clr.count() > 0) await clr.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(200);
  const open2 = await chip.getAttribute('aria-expanded').catch(() => null);
  if (open2 === 'true') await chip.click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(200);
}

async function readNewestClick(page) {
  const chip = page.locator('[data-testid="chart-click-chip"]').first();
  const expanded = await chip.getAttribute('aria-expanded').catch(() => null);
  if (expanded !== 'true') await chip.click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(200);
  const rows = page.locator('[data-testid="chart-click-row"]');
  const n = await rows.count();
  if (n === 0) return null;
  const nums = await rows.first().locator('.num').allTextContents();
  if (nums.length < 2) return null;
  const out = { date: fa2en(nums[0]).split('·')[0], label: nums[0], close: Number(fa2en(nums[1])), rows: n };
  await chip.click({ timeout: 5000 }).catch(() => {});
  return out;
}

/** مقایسۀ عدد به عددِ سریِ رندرر با انتظارِ ساخته‌شده از پاسखाۀ سرور */
function compare(tag, got, want) {
  if (!got) return { ok: false, detail: 'سریِ رندرر خوانده نشد' };
  if (!want || want.length === 0) return { ok: false, detail: 'مرجعِ سرور خالی است' };
  const byDate = new Map(want.map((w) => [w.d, w]));
  let matched = 0, miss = 0, bad = 0;
  const samples = [];
  for (const g of got) {
    const w = byDate.get(g.d);
    if (!w) { miss++; continue; }
    if (Math.abs(g.c - w.c) <= (w.tol == null ? 0.51 : w.tol)) matched++;
    else { bad++; if (samples.length < 4) samples.push(g.d + ' دید=' + g.c + ' انتظار=' + w.c); }
  }
  return { ok: bad === 0 && matched > 0 && miss === 0, matched, miss, bad, samples,
           detail: 'تطبیق=' + matched + ' بی‌مرجع=' + miss + ' اختلاف=' + bad +
                   (samples.length ? ' | ' + samples.join(' ; ') : ''), got: got.length, want: want.length };
}

(async () => {
  if (!fs.existsSync(EXE)) throw new Error('msedge not found: ' + EXE);
  fs.mkdirSync(SHOTS, { recursive: true });
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: EXE, headless: false, viewport: { width: 1366, height: 768 },
    args: ['--no-first-run', '--no-default-browser-check', '--disable-features=Translate'],
  });
  const page = ctx.pages()[0] || await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') report.consoleErrors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => report.consoleErrors.push('pageerror: ' + String(e.message).slice(0, 200)));

  const url = BASE + '/#/technical/' + encodeURIComponent(SYMBOL);
  note('باز کردن ' + url);
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForTimeout(2500);
  await loginIfNeeded(page);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForTimeout(4000);
  await ensureKcEngine(page);
  await page.waitForSelector('.nn-kline-chart canvas', { timeout: 120000 });
  await page.waitForTimeout(3000);
  await page.evaluate(PROBE);

  // ── مرجعِ عدد: همان اندپوینتی که خودِ چارت می‌خواند ─────────────────────
  const api = await page.evaluate(async (sym) => {
    const r = await fetch('/api/chart/' + encodeURIComponent(sym));
    const j = await r.json();
    return { status: j.status, count: j.count, candles: j.candles, factors: j.factors,
             adjustEvents: j.adjustEvents, adjustRejected: j.adjustRejected,
             adjustSource: j.adjustSource, capability: j.adjustCapability };
  }, SYMBOL);
  ck('پاسخِ /api/chart موفق است', api.status === 'success', api.status);
  ck('بلوکِ توانایی از سرور می‌آید (coverage + blockers)',
     !!(api.capability && api.capability.coverage && Array.isArray(api.capability.functional_blockers)),
     JSON.stringify(api.capability && api.capability.functional_blockers));
  const facVals = [...new Set((api.factors || []).map((f) => Number(f.factor)))].sort((a, b) => a - b);
  ck('ضرایبِ سرور غیربدیهی‌اند (پیشِ رویداد ≠ ۱)', facVals.some((v) => Math.abs(v - 1) > 1e-9),
     'distinct=' + facVals.slice(0, 4).join(', '));
  note('کندل‌ها: ' + (api.count || 0) + ' | ضریب‌ها: ' + (api.factors || []).length +
       ' | رویدادهایِ اعمال‌شده: ' + (api.adjustEvents || []).length +
       ' | ردشده: ' + (api.adjustRejected || []).length);

  const factorByDate = new Map();
  for (const f of (api.factors || [])) {
    const d = String(f.time || '').slice(0, 10);
    const v = Number(f.factor);
    if (d && Number.isFinite(v) && v > 0) factorByDate.set(d, v);
  }
  const fOf = (d) => factorByDate.get(d) ?? 1;
  // سرور کندل‌ها را با `time: 'YYYY-MM-DD'` و از تازه به کهنه می‌فرستد؛ اینجا به ترتیبِ
  // صعودی برمی‌گردیم تا «نخستین میله» درِ نمایِ بازدهی همان میله‌ای باشد که چارت نشان می‌دهد.
  const asc = (api.candles || []).slice().sort((a, b) => String(a.time).localeCompare(String(b.time)));
  // انتظارِ هر سه حالت، از کندلِ خامِ سرور × ضریبِ همان روز (قاعدۀ سورس، نه قاعدۀ تست).
  // «none» دست‌نخورده عبور می‌کند (بدونِ گرد)، «combined» گردِ صحیح می‌گیرد،
  // «performance» شاخصِ دو رقمِ ممیز رویِ همان گردِ صحیح.
  const rawSeries = asc.map((c) => ({ d: String(c.time).slice(0, 10), c: Number(c.close), tol: 0.51 }));
  const combSeries = asc.map((c) => ({
    d: String(c.time).slice(0, 10), c: Math.round(Number(c.close) * fOf(String(c.time).slice(0, 10))), tol: 0.51,
  }));
  const base = combSeries.length ? combSeries[0].c : 0;
  const perfSeries = combSeries.map((w) => ({ d: w.d, c: round2(w.c / base * 100), tol: 0.011 }));
  report.series = { rawCount: rawSeries.length, factorCount: factorByDate.size,
                    distinctFactors: facVals.length, oldest: rawSeries[0] && rawSeries[0].d,
                    newest: rawSeries[rawSeries.length - 1] && rawSeries[rawSeries.length - 1].d,
                    firstCombined: base,
                    lastCombined: combSeries[combSeries.length - 1] && combSeries[combSeries.length - 1].c };

  const box = await page.locator('.nn-kline-chart').boundingBox();
  if (!box) throw new Error('بومِ چارت پیدا نشد');

  // ── ۱) سریِ دیدنی درِ هر سه حالت، از خودِ رندرر ────────────────────────
  // هویتِ هر حالت را از *عدد* می‌گیریم، نه از ترتیبِ فهرست: سه حالتِ فعال را یکی‌یکی
  // انتخاب و سلسلةِ رندرر را می‌خوانیم، سپس می‌بینیم کدام برچسب سریِ خام را داد،
  // کدام خام×ضریب را و کدام شاخصِ ۱۰۰ را. بی‌این، فرضِ ترتیبِ منو درِ تست نشسته بود.
  const modes = [];
  for (const i of [0, 1, 2]) {
    const lab = await pickMode(page, i);
    modes.push({ i, lab, s: await page.evaluate(readSeries, 'kc') });
  }
  ck('سه حالتِ فعال انتخاب شد و برچسبِ کرکره با هر انتخاب عوض شد (کنترلِ زنده، نه مرده)',
     modes.every((m) => m.lab && m.lab.badge === m.lab.head) &&
     new Set(modes.map((m) => m.lab.head)).size === 3,
     modes.map((m) => m.lab.head).join(' | '));

  const kindOf = (want) => modes.filter((m) => compare('', m.s, want).ok);
  const kNone = kindOf(rawSeries), kComb = kindOf(combSeries), kPerf = kindOf(perfSeries);
  ck('درِ سه حالت، دقیقاً یک حالت_seriesِ خامِ سرور را می‌رسمد (انتخابِ سریِ خام)',
     kNone.length === 1, 'برچسب‌ها: ' + modes.map((m) => m.lab.head).join(' / ') +
       ' → خام=' + (kNone[0] && kNone[0].lab.head));
  ck('درِ سه حالت، دقیقاً یک حالتِ دیگر خام×ضریبِ سرور را می‌رسمد (سریِ عملکردی)',
     kComb.length === 1 && kComb[0] !== kNone[0], 'عملکردی=' + (kComb[0] && kComb[0].lab.head));
  ck('درِ سه حالت، دقیقاً یک حالت شاخصِ ۱۰۰ِ همان سریِ عملکردی است (نمایِ بازدهی)',
     kPerf.length === 1 && kPerf[0] !== kComb[0], 'بازدهی=' + (kPerf[0] && kPerf[0].lab.head));
  const sNone = kNone[0] && kNone[0].s, sComb = kComb[0] && kComb[0].s;
  const cNone = compare('none', sNone, rawSeries), cComb = compare('combined', sComb, combSeries);
  const cPerf = compare('performance', kPerf[0] && kPerf[0].s, perfSeries);
  ck('سریِ عملکردی = خامِ سرور × ضریبِ همان روز، میله‌به‌میله (بی‌قاعدۀِ دوم درِ مرورگر)',
     cComb.ok, cComb.detail);
  ck('سریِ خام = کندلِ خامِ سرور، میله‌به‌میله', cNone.ok, cNone.detail);
  const nAdj = (sNone && sComb)
    ? sNone.filter((g, i) => sComb[i] && Math.abs(g.c - sComb[i].c) > 0.51).length : -1;
  ck('حالتِ خام و حالتِ عملکردی دو سریِ واقعاً متفاوت می‌دهند (تعدیلِ مرده نیست)', nAdj > 0,
     'میله‌هایِ متفاوت=' + nAdj + ' از ' + (sNone ? sNone.length : 0));
  const sPerf = kPerf[0] && kPerf[0].s;
  ck('سریِ بازدهی = ۱۰۰ × عملکردی ÷ نخستینِ عملکردی، میله‌به‌میله', cPerf.ok, cPerf.detail);
  const firstPerf = sPerf && sPerf.length ? sPerf[0].c : null;
  ck('لنگرِ نما: نخستین میلهٔ بازدهی دقیقاً ۱۰۰', firstPerf != null && Math.abs(firstPerf - 100) < 1e-6, 'first=' + firstPerf);

  // لنگرِ بی‌اعمالِ دوبار: آخرین میله در «خام» و «عملکردی» یک عدد است (ضریبِ لنگر = ۱)
  const lastNone = sNone && sNone.length ? sNone[sNone.length - 1].c : null;
  const lastComb = sComb && sComb.length ? sComb[sComb.length - 1].c : null;
  ck('آخرین میله با تعدیل دست‌نخورده می‌ماند (فاکتورِ لنگر = ۱، بی‌اعمالِ دوبار)',
     lastNone != null && Math.abs(lastNone - lastComb) <= 0.51, 'none=' + lastNone + ' comb=' + lastComb);

  // ── ۲) مسیرِ تعامل: کلیکِ محاسبه‌شده رویِ یک میله، درِ دو حالت ──────────
  // میله‌ای با ضریبِ ≠ ۱ (پیشِ رویداد) ⇒ عددِ دیدنی باید نسبتِ سرور را بدهد.
  // از انتهای سلسلةِ دیدنی به عقب می‌رویم: نخستین میله‌ای که تعدیل دیده است،
  // تازه‌ترینِ آن‌هاست و به لبۀِ راستِ دید نزدیک‌تر.
  if (kComb[0]) await pickMode(page, kComb[0].i);
  let idx = -1;
  if (sComb && sNone) {
    for (let i = sComb.length - 1; i >= 0; i--) {
      if (!sNone[i] || sNone[i].c <= 2) continue;
      if (Math.abs(sNone[i].c - sComb[i].c) > 0.51 && Math.abs(fOf(sNone[i].d) - 1) > 1e-9) { idx = i; break; }
    }
    if (idx < 0) for (let i = sComb.length - 1; i >= 0; i--) {
      if (Math.abs(sNone[i].c - sComb[i].c) > 0.51) { idx = i; break; }
    }
  }
  ck('میله‌ای با ضریبِ غیر۱ برایِ کلیک پیدا شد (پیشِ رویدادِ تعدیل)', idx >= 0,
     'dataIndex=' + idx + ' از ' + (sComb ? sComb.length : 0) + ' میله');

  let combHit = null, noneHit = null, hpA = null, hpB = null;

  async function hunt() {
    await resetClickLog(page);
    const hp = await page.evaluate(hitPoint, idx);
    if (!hp) return hp;
    await page.mouse.click(hp.x, hp.y);
    await page.waitForTimeout(500);
    let hit = await readNewestClick(page);
    if (!hit) {                            // گردِ پیکسل/لایۀِ مزاحم: حصارِ کوچکِ y
      for (const dy of [-3, 3, -6, 6, -10, 10, -16, 16]) {
        await resetClickLog(page);
        await page.mouse.click(hp.x, hp.y + dy);
        await page.waitForTimeout(400);
        hit = await readNewestClick(page);
        if (hit) { note('کلیک با جابه‌جاییِ ' + dy + ' پیکسل خورد'); break; }
      }
    }
    return { hp, hit };
  }

  if (idx >= 0) {
    const A = await hunt();
    hpA = A && A.hp; combHit = A && A.hit;
    note('کلیکِ عملکردی: پیکسل (' + (hpA ? hpA.x.toFixed(1) + ',' + hpA.y.toFixed(1) : '—') + ')' +
         ' inside=' + (hpA && hpA.inside) + ' idx=' + (hpA && hpA.idx) + ' d=' + (hpA && hpA.d) +
         ' bar=' + (hpA && hpA.bar) + ' → ' + JSON.stringify(combHit) +
         ' | closeِ رندرر=' + (hpA && hpA.close));

    if (kNone[0]) await pickMode(page, kNone[0].i);
    const B = await hunt();
    hpB = B && B.hp; noneHit = B && B.hit;
    note('کلیکِ خام: پیکسل (' + (hpB ? hpB.x.toFixed(1) + ',' + hpB.y.toFixed(1) : '—') + ')' +
         ' inside=' + (hpB && hpB.inside) + ' idx=' + (hpB && hpB.idx) + ' → ' + JSON.stringify(noneHit) +
         ' | closeِ رندرر=' + (hpB && hpB.close));
  }

  ck('نقطۀِ کلیک از برگشتِ مختصاتِ خودِ چارت آمد (همان dataIndex، داخلِ پنل، درِ هر دو حالت)',
     !!hpA && !!hpB && hpA.idx === hpB.idx && hpA.idx === idx && hpA.inside && hpB.inside,
     'A=' + JSON.stringify(hpA && { idx: hpA.idx, inside: hpA.inside, bar: hpA.bar }) +
     ' B=' + JSON.stringify(hpB && { idx: hpB.idx, inside: hpB.inside, bar: hpB.bar }) + ' خواسته=' + idx);
  ck('کلیکِ واقعی رویِ میله، خطِ کلیک را پر کرد (هر دو حالت)', !!(combHit && noneHit),
     'comb=' + JSON.stringify(combHit) + ' none=' + JSON.stringify(noneHit));
  if (combHit && noneHit && hpA && hpB) {
    ck('همان میله درِ هر دو حالت خوانده شد (تاریخِ دیدنی یکی است)', combHit.date === noneHit.date,
       combHit.date + ' vs ' + noneHit.date);
    ck('خطِ کلیک عددِ خودِ رندرر را می‌گوید (بی‌قاعدۀ دوم درِ UI)',
       Math.abs(combHit.close - hpA.close) <= 0.51 && Math.abs(noneHit.close - hpB.close) <= 0.51,
       'chip=' + combHit.close + '/' + noneHit.close + ' renderer=' + hpA.close + '/' + hpB.close);
    // comb = round(none·f) ⇒ |comb/none − f| ≤ 0.5/none؛ تلورانس از همین گرد می‌آید، نه از بازکردنِ دلخواه
    const ratio = combHit.close / noneHit.close;
    const fHere = fOf(hpA.d);
    const tol = 0.5 / noneHit.close + 1e-9;
    const facHit = facVals.find((v) => Math.abs(v - ratio) <= tol);
    ck('نسبتِ (عملکردی ÷ خام) رویِ همان میله = ضریبِ سرور',
       !!facHit && Math.abs(facHit - fHere) <= tol,
       'ratio=' + ratio.toFixed(8) + ' سرور=' + fHere + ' تلورانسِ گرد=' + tol.toExponential(2) +
         ' میله=' + hpA.d);
  }

  // ── ۳) حالت‌هایِ غیرفعال نباید چیزی را عوض کنند (بی‌دکمۀ mock) ─────────
  const labelNow = (await pickMode(page, 2)).head;
  const before = await page.evaluate(readSeries, 'kc');
  const d1 = await clickDisabled(page, 'سود نقدی');
  const d2 = await clickDisabled(page, 'افزایش سرمایه');
  await closeAdjMenu(page);
  const after = await page.evaluate(readSeries, 'kc');
  ck('فهرستِ تعدیل پنج حالت دارد، دو تایِ آن‌ها خوانا غیرفعال‌اند',
     d1.found && d2.found && d1.offCount === 2, JSON.stringify([d1.offCount, d2.offCount, d1.found, d2.found]));
  ck('کلیک رویِ حالتِ غیرفعال نامِ حالت را عوض نمی‌کند (برگشتِ دقیق، نه زیررشته)',
     d1.badge === labelNow && d2.badge === labelNow, 'انتظار=' + labelNow + ' دید=' + d1.badge + '/' + d2.badge);
  ck('کلیک رویِ حالتِ غیرفعال سری را دست نمی‌زند',
     before && after && before.length === after.length &&
     before.every((b, i) => Math.abs(b.c - after[i].c) < 1e-9),
     'len ' + (before && before.length) + '→' + (after && after.length));

  // ── ۴) نمادِ دوم + سوییچِ نماد (حالتِ چارت پس از سوییچ) ─────────────────
  note('سوییچ به نمادِ دوم: ' + SYMBOL2);
  await page.goto(BASE + '/#/technical/' + encodeURIComponent(SYMBOL2), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await ensureKcEngine(page);
  await page.waitForSelector('.nn-kline-chart canvas', { timeout: 120000 });
  await page.waitForTimeout(3500);
  const api2 = await page.evaluate(async (sym) => {
    const r = await fetch('/api/chart/' + encodeURIComponent(sym));
    const j = await r.json();
    return { status: j.status, count: j.count, candles: j.candles, factors: j.factors };
  }, SYMBOL2);
  const f2 = new Map();
  for (const f of (api2.factors || [])) {
    const d = String(f.time || '').slice(0, 10); const v = Number(f.factor);
    if (d && Number.isFinite(v) && v > 0) f2.set(d, v);
  }
  const want2 = (api2.candles || []).map((c) => {
    const d = String(c.time).slice(0, 10);
    return { d, c: Math.round(Number(c.close) * (f2.get(d) ?? 1)), tol: 0.51 };
  });
  await pickMode(page, kComb[0] ? kComb[0].i : 0);
  const s2 = await page.evaluate(readSeries, 'kc');
  const c2 = compare('combined2', s2, want2);
  ck('نمادِ دوم: سریِ عملکردی از ضرایبِ همان نماد می‌آید (بی‌سریِ کهنه)',
     api2.status === 'success' && c2.ok, 'status=' + api2.status + ' ' + c2.detail);

  // ── ۵) موتورِ دوم: همان سری، از آداپترِ خودش ───────────────────────────
  await page.goto(BASE + '/#/technical/' + encodeURIComponent(SYMBOL), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await ensureKcEngine(page);
  await page.waitForSelector('.nn-kline-chart canvas', { timeout: 120000 });
  await page.waitForTimeout(3000);
  await page.evaluate(PROBE);
  await pickMode(page, kComb[0] ? kComb[0].i : 0);

  const engineBtn = page.locator('[data-testid="nn-engine-ffc"]');
  if (await engineBtn.count() === 0) {
    ck('کلیدِ موتورِ دوم درِ نوار پیدا شد', false, 'locator empty');
  } else {
    await engineBtn.click({ timeout: 8000 }).catch((e) => note('سوییچ موتور ناموفق: ' + e.message));
    await page.waitForTimeout(4000);
    const canvases = await page.locator('canvas').count();
    ck('موتورِ دوم بوم دارد', canvases > 0, 'canvas=' + canvases);
    const sFfc = await page.evaluate(readSeries, 'ffc');
    const cFfc = compare('ffc', sFfc, combSeries);
    ck('موتورِ دوم سریِ عملکردی (خام × ضریبِ سرور) را می‌گیرد، نه سریِ خام',
       cFfc.ok && cFfc.matched > 0, cFfc.detail);
    const rawFfc = compare('ffc-raw', sFfc, rawSeries);
    ck('سریِ موتورِ دوم با سریِ خام برابری نمی‌کند (تعدیل واقعاً رویِ آن اعمال شده)',
       rawFfc.bad > 0, 'اختلاف با خام=' + rawFfc.bad + ' میله');
    const modesFfc = await page.locator(ADJ_BTN).count();
    const basis = String(await page.locator('[data-testid="ffc-adjust-basis"]').first().textContent().catch(() => ''));
    ck('موتورِ دوم مبنایِ سریِ خود را رویِ صحنه اعلام می‌کند (کرکرۀ تعدیل ندارد، پس ادعا باید خوانا باشد)',
       basis.indexOf('عملکردی') >= 0, basis);
    note('موتورِ دوم کرکرۀ تعدیلِ نوارِ ابزارِ KLineCharts را ندارد؛ کنترل روی صحنه: ' +
         (modesFfc === 0 ? 'خیر — تنها اعلامِ مبنایِ سری هست' : 'بله'));
    await page.screenshot({ path: path.join(SHOTS, 'ffc-1366x768.png') });
    report.shots.push('ffc-1366x768.png');
    await page.locator('[data-testid="fts-engine-back"]').first().click({ timeout: 8000 })
      .catch((e) => note('بازگشت به موتورِ اصلی ناموفق: ' + e.message));
    await page.waitForTimeout(2500);
    ck('کلیدِ «بازگشت» موتورِ دوم به چارتِ اصلی برمی‌گردد (موتورِ دوم درِ حالِ گیر نمی‌ماند)',
       (await page.locator('.nn-kline-chart canvas').count()) > 0);
  }

  // ── ۶) حالتِ چارت پس از سوییچِ بازه (روزانه ↔ هفتگی) ───────────────────
  await pickMode(page, kComb[0] ? kComb[0].i : 0);
  const sD = await page.evaluate(readSeries, 'kc');
  await page.locator('[data-testid="timeframe-W"]').click({ timeout: 8000 }).catch((e) => note('سوییچ هفتگی نشد: ' + e.message));
  await page.waitForTimeout(2500);
  const sW = await page.evaluate(readSeries, 'kc');
  await page.locator('[data-testid="timeframe-D"]').click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(2500);
  const sD2 = await page.evaluate(readSeries, 'kc');
  ck('بازهٔ هفتگی کندل‌ها را بازآرایی می‌کند (کمتر از روزانه، بی‌سریِ کهنه)',
     sW && sD && sW.length > 0 && sW.length < sD.length, 'D=' + (sD && sD.length) + ' W=' + (sW && sW.length));
  ck('برگشت به روزانه همان سریِ عملکردیِ کامل را بازمی‌گرداند',
     sD2 && sD && sD2.length === sD.length &&
     Math.abs(sD2[sD2.length - 1].c - sD[sD.length - 1].c) < 1e-6,
     'len ' + (sD && sD.length) + '→' + (sD2 && sD2.length));

  await page.screenshot({ path: path.join(SHOTS, 'klinecharts-1366x768.png') });
  report.shots.push('klinecharts-1366x768.png');

  // ── ۷) ریسپانسیو ───────────────────────────────────────────────────────
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOTS, 'klinecharts-390x844.png') });
  report.shots.push('klinecharts-390x844.png');
  const sSmall = await page.evaluate(readSeries, 'kc');
  ck('درِ ۳۹۰×۸۴۴ همان سریِ عملکردی روی صحنه می‌ماند',
     sSmall && sSmall.length === (sD2 || []).length, 'len=' + (sSmall && sSmall.length));
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.waitForTimeout(1200);

  ck('هیچ خطای Console درِ این مسیر ثبت نشد', report.consoleErrors.length === 0,
     report.consoleErrors.slice(0, 3).join(' | '));

  fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 1), 'utf8');
  const failed = report.checks.filter((c) => !c.ok);
  console.log('\nنتیجه: ' + (report.checks.length - failed.length) + ' سبز، ' + failed.length + ' قرمز');
  console.log('JSON: ' + OUT_JSON);
  console.log('shots: ' + report.shots.join(', '));
  await ctx.close();
  process.exit(failed.length ? 1 : 0);
})().catch((e) => {
  console.error('FATAL ' + String(e));
  try { fs.writeFileSync(OUT_JSON, JSON.stringify(report, null, 1), 'utf8'); } catch { /* بی‌نوشتنِ گزارش بهتر از بی‌گزارش است */ }
  process.exit(2);
});
