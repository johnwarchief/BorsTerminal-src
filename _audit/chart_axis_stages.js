// _audit/chart_axis_stages.js — ممیزیِ عددیِ مرحله‌به‌مرحلۀ محورِ قیمت و کندل‌ها
//
// مسیر را در ششِ مرحلۀ جدا می‌خواند و برایِ هر مرحله عددِ همانِ اجرا را ثبت می‌کند:
//   ۱ منبعِ داده / ۲ کندل‌های API / ۳ تعدیلِ شرکتی / ۴ تبدیلِ چارت / ۵ سریِ داده / ۶ مقیاسِ قیمت
//
// «۱۴۷٬۰۰۰ در حالی که آخرین بستۀ ۴٬۴۱۰ است» ادعایی است که باید به یکِ مرحلۀ
// مشخص برگردد، نه به حدس. پس این هارنس هیچ عددی نمی‌سازد:
//   - مرحلۀ ۲ از همانِ آدرسی خوانده می‌شود که چارتِ زنده می‌گیرد (پروکسیِ vite ⇒ ۸۰۰۱)،
//   - مرحلۀ ۵ و ۶ از خودِ نمونهٔ klinecharts درِ حافظۀ کامپوننت بیرون کشیده می‌شود
//     (پیمایشِ React fiber؛ هیچ خطایِ debug در سورس تزریق نمی‌شود و چیزی منتشر نمی‌شود)،
//   - مرحلۀ ۳ به‌جای بازسازیِ ضریب، نسبتِ «ارزانی که رابط می‌فرستد» به «ارزانی که
//     موتور رسم می‌کند» را کندل‌به‌کندل می‌شمارد؛ اگر ضربی رخ داده باشد همان‌جا پیدا می‌شود.
// اجرا:  node _audit/chart_axis_stages.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
// TAG برایِ این که بتوانِ «پیش از اصلاح» و «پس از اصلاح» را درِ دو فایلِ جدا ثبت کرد
const TAG = process.env.BORS_STAGES_TAG || 'after';
const OUT = path.join(ROOT, '_audit', `chart_axis_stages_${TAG}.json`);
const REF = path.join(ROOT, '_audit', 'ra365_ref_bars.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';
const VIEWPORTS = [[1366, 768], [1600, 900]];

/** مرحلۀ ۲ + ۵ + ۶ — همه در بافتِ صفحه، همه به شکلِ عددِ خالی.
 *  آرگومان `{sym, ref}` می‌گیرد؛ متغیرِ بیرونِ این تابع درِ صفحه وجود ندارد. */
const READ_PAGE = async (arg) => {
  const SYM = arg.sym;
  const out = { apiUrl: `/api/chart/${encodeURIComponent(SYM)}` };

  // --- مرحلۀ ۲: همانِ پاسخی که چارت می‌خواند ---
  const res = await fetch(out.apiUrl, { credentials: 'same-origin' });
  const json = await res.json();
  const list = Array.isArray(json) ? json : (json.candles || json.data || []);
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : NaN);
  const rows = list.map((c) => ({
    time: String(c.time ?? c.timestamp ?? c.date ?? ''),
    o: num(c.open ?? c.o), h: num(c.high ?? c.h), l: num(c.low ?? c.l), c: num(c.close ?? c.c),
  })).filter((r) => r.time && Number.isFinite(r.c));
  const vols = (Array.isArray(json.volumes) ? json.volumes : []).map((v) => num(v.value ?? v.volume));
  const factors = (Array.isArray(json.factors) ? json.factors : []).map((f) => ({
    time: String(f.time ?? ''), factor: num(f.factor),
  }));
  out.api = {
    httpStatus: res.status,
    candleCount: list.length,
    seriesCount: rows.length,
    volumeSeriesCount: vols.length,
    factorCount: factors.length,
    first: rows[0] ?? null,
    last3: rows.slice(-3),
    closeMinAll: rows.length ? Math.min(...rows.map((r) => r.c)) : null,
    closeMaxAll: rows.length ? Math.max(...rows.map((r) => r.c)) : null,
    closeMinLast300: rows.length ? Math.min(...rows.slice(-300).map((r) => r.c)) : null,
    closeMaxLast300: rows.length ? Math.max(...rows.slice(-300).map((r) => r.c)) : null,
    volumeMaxAll: vols.length ? Math.max(...vols.filter(Number.isFinite)) : null,
    lastFactor: factors.length ? factors[factors.length - 1] : null,
    factorsOutsideUnit: factors.filter((f) => !(f.factor > 0.0001 && f.factor <= 1.0001)).slice(0, 8),
    adjustSource: json.adjustSource ?? null,
    degraded: json.degraded ?? null,
    lastDataTime: json.lastDataTime ?? json.last_data_time ?? null,
    priceBasis: json.priceBasis ?? json.price_basis ?? null,
    capabilityKeys: json.adjustCapability ? Object.keys(json.adjustCapability) : null,
    functionalAvailable: json.adjustCapability ? json.adjustCapability.functional_available ?? null : null,
    combinedAvailable: json.adjustCapability ? json.adjustCapability.combined_available ?? null : null,
    topFieldNames: Object.keys(json).slice(0, 40),
  };

  // --- نمونهٔ موتور: پیمایشِ fiber، بدونِ تغییرِ سورس ---
  const looksLikeChart = (v) => !!v && typeof v === 'object' &&
    typeof v.getDataList === 'function' && typeof v.getVisibleRange === 'function';
  let host = document.querySelector('canvas');
  let hops = 0, found = null, via = null;
  while (host && !found && hops < 12) {
    const fk = Object.keys(host).find((k) => k.startsWith('__reactFiber$'));
    if (!fk) { host = host.parentElement; hops++; continue; }
    let fiber = host[fk];
    let up = 0;
    while (fiber && up < 80) {
      up++;
      let hook = fiber.memoizedState, hg = 0;
      while (hook && hg < 120) {
        hg++;
        const ms = hook.memoizedState;
        if (looksLikeChart(ms)) { found = ms; via = `hook@depth${up}`; break; }
        if (ms && typeof ms === 'object' && looksLikeChart(ms.current)) { found = ms.current; via = `ref@depth${up}`; break; }
        hook = hook.next;
      }
      if (found) break;
      const st = fiber.stateNode;
      if (st && typeof st === 'object') {
        for (const key of Object.keys(st)) {
          if (looksLikeChart(st[key])) { found = st[key]; via = `class.${key}`; break; }
        }
      }
      if (found) break;
      fiber = fiber.return;
    }
    host = host.parentElement; hops++;
  }
  if (!found) {
    out.chart = { error: 'CHART_INSTANCE_NOT_FOUND', hops, domCanvases: document.querySelectorAll('canvas').length };
    return out;
  }

  const chart = found;
  const dl = chart.getDataList() || [];
  const vr = chart.getVisibleRange();
  const val = (d) => ({
    time: new Date(d.timestamp).toISOString().slice(0, 10),
    o: d.open, h: d.high, l: d.low, c: d.close, v: d.volume ?? null,
  });
  const vis = dl.slice(vr.from, vr.to);
  const pane = (id) => {
    const b = chart.getSize(id, 'main');
    return b ? { w: Math.round(b.width), h: Math.round(b.height), left: Math.round(b.left), top: Math.round(b.top) } : null;
  };
  // مرحلۀ ۶: دو انتهای پن را به مقدارِ محورِ همانِ پن برگردان
  const edgeValues = (id) => {
    const b = chart.getSize(id, 'main');
    if (!b) return null;
    const top = chart.convertFromPixel([{ x: Math.round(b.left + b.width / 2), y: Math.round(b.top + 1) }], { paneId: id });
    const bottom = chart.convertFromPixel([{ x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height - 1) }], { paneId: id });
    const pick = (v) => (Array.isArray(v) ? v[0] : v) || {};
    return { topValue: pick(top).value ?? null, bottomValue: pick(bottom).value ?? null };
  };
  out.chart = {
    via,
    symbol: chart.getSymbol() || null,
    period: chart.getPeriod() || null,
    stylesCandle: (() => { const s = chart.getStyles(); return { type: s?.candle?.type, precision: s?.candle?.price?.precision ?? null }; })(),
    panes: { candle: pane('candle_pane'), vol: pane('sub_pane_vol') },
    axisValues: { candle: edgeValues('candle_pane'), vol: edgeValues('sub_pane_vol') },
    dataList: {
      length: dl.length,
      last3: dl.slice(-3).map(val),
      minClose: dl.length ? Math.min(...dl.map((d) => d.close)) : null,
      maxClose: dl.length ? Math.max(...dl.map((d) => d.close)) : null,
      minLow: dl.length ? Math.min(...dl.map((d) => d.low)) : null,
      maxHigh: dl.length ? Math.max(...dl.map((d) => d.high)) : null,
      maxVolume: dl.length ? Math.max(...dl.map((d) => d.volume ?? 0)) : null,
    },
    visible: {
      from: vr.from, to: vr.to, realFrom: vr.realFrom, realTo: vr.realTo, count: vis.length,
      minLow: vis.length ? Math.min(...vis.map((d) => d.low)) : null,
      maxHigh: vis.length ? Math.max(...vis.map((d) => d.high)) : null,
      maxVolume: vis.length ? Math.max(...vis.map((d) => d.volume ?? 0)) : null,
      last3: vis.slice(-3).map(val),
    },
    indicators: (chart.getIndicators?.() ?? []).map((i) => ({ name: i.name, paneId: i.paneId })),
    overlayCount: (chart.getOverlays?.() ?? []).length,
  };

  // --- مرحلۀ ۳: نسبتِ کندل‌به‌کندلِ رابط ← موتور (تاریخِ مشترک) ---
  const volByDate = new Map((Array.isArray(json.volumes) ? json.volumes : [])
    .map((v) => [String(v.time ?? '').slice(0, 10), num(v.value ?? v.volume)]));
  const apiByDate = new Map(rows.map((r) => [r.time.slice(0, 10), r]));
  const pairs = [];
  for (const d of dl) {
    const key = new Date(d.timestamp).toISOString().slice(0, 10);
    const r = apiByDate.get(key);
    if (!r) continue;
    const apiVol = volByDate.get(key) ?? (d.volume ?? null);
    pairs.push({
      date: key,
      apiClose: r.c, renderClose: d.close,
      closeRatio: r.c ? d.close / r.c : null,
      apiHigh: r.h, renderHigh: d.high,
      apiVolume: apiVol, renderVolume: d.volume ?? null,
      volumeRatio: apiVol ? (d.volume ?? 0) / apiVol : null,
    });
  }
  const ratios = [...new Set(pairs.map((p) => p.closeRatio))].sort((a, b) => a - b);
  const volRatios = [...new Set(pairs.map((p) => p.volumeRatio).filter((v) => v != null))].sort((a, b) => a - b);
  out.adjustStage = {
    matchedCandles: pairs.length,
    distinctCloseRatios: ratios.slice(0, 12),
    ratioCount: ratios.length,
    distinctVolumeRatios: volRatios.slice(0, 12),
    volumeRatioCount: volRatios.length,
    firstThreePairs: pairs.slice(0, 3),
    lastThreePairs: pairs.slice(-3),
  };

  // آنچه کاربر درِ صفحه می‌خواند (متنِ DOM، نه پیکسل)
  out.domReadout = [...document.querySelectorAll('div,span')]
    .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim())
    .filter((s) => s.length > 8 && s.length < 160 && /(O|H|L|C|باز|بسته|_high|close)/i.test(s))
    .slice(0, 5);

  out.storedSettings = (() => {
    try { return JSON.parse(localStorage.getItem('fts.chart.settings.v1') || 'null'); } catch { return null; }
  })();

  // ── مرحلۀ ۱ و ۴: سریِ رسم‌شدۀ خودی در برابرِ مرجع، تاریخ‌به‌تاریخ ──
  // مرجع = بارِ روزانۀ همانِ ابزار درِ ره‌آورد (type7 = سریِ تعدیل‌شده، type0 = خام).
  // هیچ عددی اینجا ساخته نمی‌شود: اگر تاریخِ مشترکی نیست، درِ sharedDates می‌آید.
  const refT7 = arg?.ref?.type7 || {};
  if (Object.keys(refT7).length) {
    const byDate = new Map(dl.map((d) => [new Date(d.timestamp).toISOString().slice(0, 10), d]));
    const diffs = [];
    for (const [date, refC] of Object.entries(refT7)) {
      const ours = byDate.get(date);
      if (!ours || !Number.isFinite(refC) || refC <= 0) continue;
      diffs.push({ date, ref: refC, ours: ours.close,
                   absDiff: Math.abs(ours.close - refC),
                   pct: Math.abs(ours.close - refC) / refC * 100 });
    }
    diffs.sort((x, y) => y.absDiff - x.absDiff);
    const oursSorted = dl.slice(-5).map((d) => ({
      date: new Date(d.timestamp).toISOString().slice(0, 10), close: d.close,
      ref: refT7[new Date(d.timestamp).toISOString().slice(0, 10)] ?? null,
    }));
    out.parityDaily = {
      reference: 'ره‌آورد ۳۶۵ — exchange.asset:453، تایم‌فریمِ روزانه، سریِ type7 (تعدیل‌شده)',
      sharedDates: diffs.length,
      exactMatches: diffs.filter((x) => x.absDiff === 0).length,
      maxAbsDiff: diffs.length ? diffs[0].absDiff : null,
      maxAbsDiffPct: diffs.length ? +diffs[0].pct.toFixed(4) : null,
      meanAbsDiff: diffs.length ? +(diffs.reduce((s, x) => s + x.absDiff, 0) / diffs.length).toFixed(3) : null,
      worst: diffs.slice(0, 6),
      oursLast5: oursSorted,
    };
  }
  return out;
};

(async () => {
  const report = { ranAt: new Date().toISOString(), symbol: SYM, timeframe: 'D',
    apiBase: BASE, backendProxyTarget: 'http://127.0.0.1:8001', views: {} };

  // مرجعِ منجمد (ره‌آورد) برایِ تاریخ‌هایِ مشترک — فقط برایِ مقایسه، نه اثباتِ برابری
  const refMaps = { type0: {}, type7: {} };
  if (fs.existsSync(REF)) {
    const ref = JSON.parse(fs.readFileSync(REF, 'utf8'));
    const byDate = (k) => {
      const e = ref.bars?.[k];
      const m = {};
      for (const b of (e?.bars || [])) m[String(b.utc).slice(0, 10)] = b.c;
      return m;
    };
    refMaps.type0 = byDate(`${SYM}|type0|D`);
    refMaps.type7 = byDate(`${SYM}|type7|D`);
    const pick = (k) => {
      const e = ref.bars?.[k];
      if (!e) return null;
      const b = e.bars || [];
      return { n: e.n, ticker: e.ticker, last3: b.slice(-3).map((x) => ({
        utc: x.utc, o: x.o, h: x.h, l: x.l, c: x.c, v: x.v })) };
    };
    report.referenceFrozen = { file: '_audit/ra365_ref_bars.json',
      daily_type0_raw: pick(`${SYM}|type0|D`), daily_type7_functional: pick(`${SYM}|type7|D`),
      weekly_type0_raw: pick(`${SYM}|type0|W`) };
  } else {
    report.referenceFrozen = { file: '_audit/ra365_ref_bars.json', error: 'MISSING' };
  }

  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-axis-stages-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => consoleErrors.push('PAGEERROR ' + String(e).slice(0, 200)));

  await page.setViewportSize({ width: VIEWPORTS[0][0], height: VIEWPORTS[0][1] });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  // فرمِ ورود پس ازِ بوتِ ناهمگام می‌آید؛ «هنوز نیست» در ۲.۵ ثانیه به معنای
  // «لازم نیست» نیست — پس فرم را منتظر می‌شویم، نه یک نگاهِ سریع.
  const haveForm = await page.waitForSelector('input[type=password]', { timeout: 20000 })
    .then(() => true).catch(() => false);
  if (haveForm) {
    await page.locator('input[type="text"]').first().fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForFunction(() => !document.querySelector('input[type=password]'), null, { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(3000);
  }
  await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.click('[data-testid="timeframe-D"]').catch(() => {});
  await page.waitForTimeout(6000);

  for (const [w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.waitForTimeout(2500);
    const r = await page.evaluate(READ_PAGE, { sym: SYM, ref: refMaps });
    report.views[`${w}x${h}`] = r;
    await page.screenshot({ path: path.join(ROOT, `_audit`, `stages_${TAG}_${SYM}_${w}x${h}.png`) });
  }
  report.consoleErrors = consoleErrors.slice(0, 12);
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');

  for (const [k, v] of Object.entries(report.views)) {
    const a = v.api, c = v.chart || {}, s3 = v.adjustStage || {};
    console.log(`\n=== ${k} ===`);
    console.log(`مرحلۀ ۲ API      : candles=${a.candleCount} factors=${a.factorCount} source=${a.adjustSource} degraded=${a.degraded} lastDataTime=${a.lastDataTime}`);
    console.log(`                  last3=${JSON.stringify((a.last3 || []).map((r) => r.c))}  closeMin/MaxAll=${a.closeMinAll}/${a.closeMaxAll}  volMax=${a.volumeMaxAll}`);
    console.log(`مرحلۀ ۵ سریِ موتور: length=${(c.dataList || {}).length} last3=${JSON.stringify(((c.dataList || {}).last3 || []).map((d) => d.c))}`);
    console.log(`                  minClose/maxClose=${(c.dataList || {}).minClose}/${(c.dataList || {}).maxClose} maxVol=${(c.dataList || {}).maxVolume}`);
    console.log(`مرحلۀ ۶ مقیاسِ قیمت: candle=${JSON.stringify((c.axisValues || {}).candle)} vol=${JSON.stringify((c.axisValues || {}).vol)}`);
    console.log(`                  visible=${JSON.stringify(c.visible && { from: c.visible.from, to: c.visible.to, minLow: c.visible.minLow, maxHigh: c.visible.maxHigh, maxVol: c.visible.maxVolume })}`);
    console.log(`                  panes=${JSON.stringify(c.panes)} via=${c.via || c.error}`);
    console.log(`مرحلۀ ۳ نسبت‌ها   : matched=${s3.matchedCandles} closeRatios=${JSON.stringify(s3.distinctCloseRatios)} volRatios=${JSON.stringify(s3.distinctVolumeRatios)}`);
    console.log(`خوانشِ DOM       : ${JSON.stringify((v.domReadout || []).slice(0, 2))}`);
    if (v.parityDaily) {
      const p = v.parityDaily;
      console.log(`مرحلۀ ۱+۴ پاریتیِ روزانۀ فولاد با مرجع (${p.reference})`);
      console.log(`                  dates=${p.sharedDates} exact=${p.exactMatches} maxAbs=${p.maxAbsDiff} max|Δ%|=${p.maxAbsDiffPct} mean|Δ|=${p.meanAbsDiff}`);
      console.log(`                  worst=${JSON.stringify((p.worst || []).slice(0, 3))}`);
      console.log(`                  oursLast5=${JSON.stringify((p.oursLast5 || []).map((x) => [x.date, x.close, x.ref]))}`);
    }
    console.log(`تنظیماتِ ذخیره   : adjustment=${JSON.stringify(v.storedSettings?.adjustment ?? v.storedSettings?.view?.adjustment ?? null)} scale=${JSON.stringify(v.storedSettings?.priceScale ?? v.storedSettings?.view?.priceScale ?? null)}`);
  }
  console.log('\nwritten: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('HARNESS FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
