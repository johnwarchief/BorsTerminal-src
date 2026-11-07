// _audit/chart_drawing_tool_matrix_v2.js — هرِ ابزارِ ترسیم، از رابطِ واقعی تا بازیابیِ پس ازِ reload
//
// نسخۀِ اولِ این هارنس (`chart_drawing_tool_matrix.js`) را با نتایجِ تأییدشدۀِ دیگر
// درِ تعارض انداخته بود: «ابزار درِ فلایاوت چیزی رسم نمی‌کند» می‌گفت، در حالی که
// `chart_drawing_anchor.js` رفت‌وبرگشتِ «خط روند» را کارکرد ثبت کرده بود. علت‌هایِ
// واقعیِ آن تعارض، درِ اجرایِ ۱۴۰-۰۷-۲۷ اندازه‌گیری شد (نه حدس):
//
//   الف) شمارشِ «ترسیم» با `getOverlays()`ِ خام: آن فهرست ۷۷ اورلیِ **لایه‌هایِ موتور**
//      (الگو/پیش‌شرط/رویدادِ شرکتی) را هم می‌شمرد، پس «تازگی» با id بی‌معنا بود — idها
//      با هرِ re-render عوض می‌شوند. از این دور، رسمِ خودی با `name == overlayType`ِ همان
//      ابزار و با **امضایِ نقاط** شناخته می‌شود، بی‌شمارشِ لایه‌ها.
//   ب) هدف‌ها فقط از ریلِ پیش‌فرض برداشته می‌شدند؛ فرزندانِ فلایاوت اصلاً باز نمی‌شدند.
//      از این دور فهرست از خودِ DOM درمی‌آید: ریل + هرِ فلایاوت بازشده.
//   ج) «حذف تمام ترسیم‌ها» پشتِ `window.confirm`ِ بومی است و آن گفت‌وگو هرگز تأیید نشد،
//      پس پاک‌سازیِ ضمنیِ هارنس بی‌اثر بود. از این دور هیچ‌جا آن دکمه فشرده نمی‌شود:
//      ترسیم‌هایِ از‌پیش‌موجودِ نماد دست‌نخورده می‌مانند (حکمِ مالک) و هارنس فقط رسمِ
//      خودِ آزمون را با `removeOverlay({id})` برمی‌گرداند.
//
// ترتیبِ هرِ ابزار: انتخاب ← نقاطِ لازم ← لنگرِ زمان/قیمت ← zoom/pan/resize ←
// خطی↔لگاریتمی ← خام↔عملکردی ← reload و بازیابی ← ویرایش ← حذفِ رسمِ خودی.
// تبدیلِ مختصات از همان فراخوانیِ تأییدشده: `convertFromPixel([{x,y}], {paneId})`.
// هیچ عددی درِ این فایل برایِ «قبول» ساخته نمی‌شود؛ registryِ ابزار از خودِ
// `DrawingToolbar.tsx` خوانده می‌شود.
// اجرا: node _audit/chart_drawing_tool_matrix_v2.js   [BORS_TOOL="خط روند" برایِ تک‌آزمون]
const path = require('path');
const fs = require('fs');
const os = require('os');
const pw = require(path.join(process.cwd(), 'frontend', 'node_modules', 'playwright-core'));
const ROOT = process.cwd();
const OUT = path.join(ROOT, '_audit', 'chart_drawing_tool_matrix_v2.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = process.env.BORS_SYM || 'فولاد';
const ONLY = process.env.BORS_TOOL || '';
const TOOLBAR = path.join(ROOT, 'frontend', 'src', 'features', 'technical',
                          'nahayatnegar', 'components', 'DrawingToolbar.tsx');

// registryِ خودی: نامِ ابزار ← overlayType (خط روند → segment، بازگشتی → fibonacciLine …)
function toolTypes() {
  const src = fs.readFileSync(TOOLBAR, 'utf8');
  const map = {};
  const rx = /\{\s*id:\s*'([^']+)',\s*name:\s*'([^']+)',\s*overlayType:\s*'([^']+)'/g;
  let m;
  while ((m = rx.exec(src))) {
    if (!map[m[2]]) map[m[2]] = { id: m[1], overlayType: m[3] };
  }
  return map;
}

const FIND = `(function(){
  const looks = (v) => !!v && typeof v === 'object' && typeof v.getDataList === 'function';
  let host = document.querySelector('canvas'), c = null;
  while (host && !c) {
    const fk = Object.keys(host).find((k) => k.startsWith('__reactFiber$'));
    if (fk) { let f = host[fk];
      for (let up = 0; f && up < 80 && !c; up++, f = f.return) {
        let h = f.memoizedState;
        for (let g = 0; h && g < 120 && !c; g++, h = h.next) {
          const ms = h.memoizedState;
          if (looks(ms)) c = ms;
          else if (ms && typeof ms === 'object' && looks(ms.current)) c = ms.current;
        } } }
    host = host.parentElement;
  }
  if (c) window.__borsChart = c;
  return !!c;
})()`;

// فقط رسم‌هایِ کاربر (لایه‌هایِ موتور بیرون از شمارش) — همان قاعدهٔ خودِ wrapper
const READ = `(() => {
  const c = window.__borsChart;
  if (!c) return { error: 'NO_CHART' };
  const LAYERS = ['VOL','MA','EMA','RSI','MACD','BOLL','fts_strategy_overlays',
                  'fts_pattern_overlays','fts_corp_actions','fts_e3_overlays',
                  'crosshair','arrow','simpleAnnotation'];
  const all = (c.getOverlays && c.getOverlays()) || [];
  const one = (o) => ({ id: o.id, name: o.name, groupId: o.groupId || null,
    totalPointNum: o.totalPointNum ?? null,
    points: (o.points || []).map(p => {
      const idx = p.dataIndex ?? null;
      const bar = (idx != null && data[idx]) ? data[idx] : null;
      const bt = bar ? (bar.timestamp ?? bar.time ?? null) : null;
      return { timestamp: p.timestamp ?? null, dataIndex: idx,
        value: p.value == null ? null : Math.round(p.value * 100) / 100,
        barTime: bt == null ? null : Math.round(bt),
        barMatchesPointTime: bar ? (Math.round(bar.timestamp) === Math.round(p.timestamp)) : null };
    }) });
  const pane = c.getSize('candle_pane', 'main');
  const data = (c.getDataList && c.getDataList()) || [];
  return {
    drawings: all.map(one),
    layerCount: all.filter(o => LAYERS.includes(o.name) || (o.groupId||'').startsWith('fts_')).length,
    saved: (() => { try { return JSON.parse(localStorage.getItem('fts.drawings.v1.${SYM}') || '[]').length; }
                    catch (e) { return null; } })(),
    savedKeys: Object.keys(localStorage).filter(k => k.indexOf('fts.drawings') === 0),
    pane: { left: Math.round(pane.left), top: Math.round(pane.top),
            w: Math.round(pane.width), h: Math.round(pane.height) },
    visibleRange: (c.getVisibleRange && c.getVisibleRange()) || null,
    axisName: (() => { try { const y = c.getYAxis('candle_pane'); return y && (y.name || y._name || null); }
                       catch (e) { return null; } })(),
    barCount: data.length,
    lastClose: data.length ? data[data.length - 1].close : null,
  };
})()`;

const sig = (o) => o ? JSON.stringify([o.name, (o.points || []).map((p) => [p.timestamp, p.value])]) : null;
const tsig = (o) => o ? JSON.stringify((o.points || []).map((p) => [p.timestamp, p.dataIndex, p.barTime])) : null;

async function openPage() {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(os.tmpdir(), 'bors-matrix2-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  // هیچ گفت‌وگویِ بومی‌ای تأیید نمی‌شود؛ اگر چیزی بپرسد، بسته می‌شود (حکمِ «دست‌نزدن»)
  ctx.on('dialog', (d) => d.dismiss().catch(() => {}));
  const page = ctx.pages()[0] || await ctx.newPage();
  page.on('dialog', (d) => d.dismiss().catch(() => {}));
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  if (await page.waitForSelector('input[type=password]', { timeout: 20000 }).then(() => true).catch(() => false)) {
    await page.locator('input[type="text"]').first().fill('admin');
    await page.locator('input[type="password"]').first().fill('bors123');
    await page.locator('button[type="submit"]').first().click();
    await page.waitForFunction(() => !document.querySelector('input[type=password]'), null, { timeout: 30000 }).catch(() => {});
  }
  await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
  await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
  await page.click('[data-testid="timeframe-D"]').catch(() => {});
  await page.waitForTimeout(6000);
  if (!(await page.evaluate(FIND))) throw new Error('chart instance not reachable through fiber');
  return { ctx, page };
}

async function setScale(page, which) {
  await page.click('button[title="تنظیمات چارت"]').catch(() => {});
  await page.waitForTimeout(1200);
  await page.click('[data-testid="settings-tab-scales"]').catch(() => {});
  await page.waitForTimeout(900);
  await page.locator('[data-testid="chart-settings"] button', { hasText: which === 'logarithm' ? 'لگاریتمی' : 'خطی' })
    .first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.click('[data-testid="chart-settings-done"]').catch(() => {});
  await page.waitForTimeout(1800);
}

async function setSeriesMode(page, text) {
  await page.click('[title="نوع تعدیل قیمت"]').catch(() => {});
  await page.waitForTimeout(400);
  await page.locator('.nn-dropdown-item', { hasText: text }).first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(1600);
}

const closeFlyout = async (page) => {
  await page.keyboard.press('Escape').catch(() => {});
  await page.mouse.move(600, 28).catch(() => {});
  await page.waitForTimeout(250);
};

// فهرستِ هدف از خودِ رابط: پیش‌فرض‌هایِ ریل + فرزندانِ هرِ فلایاوت
async function enumerateTargets(page) {
  const rail = await page.evaluate(() => [...document.querySelectorAll('.nn-left-toolbar .tv-slot-wrapper')]
    .map((w, i) => ({ i, title: (w.querySelector('.tool-item') || {}).getAttribute
      ? (w.querySelector('.tool-item').getAttribute('title') || '').trim() : '' })));
  const targets = rail.filter((r) => r.title).map((r) => ({ title: r.title, via: 'rail', slot: r.i }));
  const arrows = await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').count();
  for (let i = 0; i < arrows; i++) {
    await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i)
      .click({ timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(650);
    const items = await page.evaluate(() => [...document.querySelectorAll('.tv-flyout-item')]
      .map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean));
    for (const t of [...new Set(items)]) {
      if (!targets.some((x) => x.title === t)) targets.push({ title: t, via: 'flyout', slot: i });
    }
    await closeFlyout(page);
  }
  return { railSlots: rail.length, arrows, targets };
}

async function selectTool(page, t) {
  await closeFlyout(page);
  if (t.via === 'flyout') {
    await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(t.slot)
      .click({ timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(600);
    const child = page.locator('.tv-flyout-item', { hasText: t.title }).first();
    if (!(await child.count().catch(() => 0))) return false;
    await child.click({ timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(450);
    return true;
  }
  const el = page.locator(`.nn-left-toolbar .tool-item[title="${t.title}"]`).first();
  if (!(await el.count().catch(() => 0))) return false;
  await el.click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(450);
  return true;
}

const SPOTS = [[0.24, 0.34], [0.40, 0.58], [0.56, 0.30], [0.72, 0.52], [0.84, 0.40]];

async function drawOnce(page, pane, type, before) {
  const beforeSigs = new Set((before.drawings || []).filter((o) => o.name === type).map(sig));
  let clicks = 0, made = null, lastCount = -1, settled = 0;
  for (const [fx, fy] of SPOTS) {
    await page.mouse.click(pane.left + Math.round(pane.w * fx), pane.top + Math.round(pane.h * fy));
    clicks++;
    await page.waitForTimeout(560);
    const st = await page.evaluate(READ);
    const freshOnes = (st.drawings || []).filter((o) => o.name === type && !beforeSigs.has(sig(o)));
    if (freshOnes.length) made = freshOnes[freshOnes.length - 1];
    if (!made) continue;
    const need = made.totalPointNum;
    const n = made.points.length;
    if (need && n >= need) break;                       // موتور خودش شمارۀِ نقاط را می‌گوید
    if (!need) {                                        // بی‌اعلامیِ موتور: با ثباتِ شمارش داوری می‌کنیم
      if (n === lastCount && n >= 2) settled++; else settled = 0;
      lastCount = n;
      if (settled >= 1) break;
    }
  }
  // لنگر از حالتِ کامل گرفته می‌شود: تا دو خواندنِ پی‌در‌پی شمارۀِ نقاط ثابت بماند
  // صبر می‌کنیم. کلیکِ دوم درِ موتور با تأخیرِ بیش از ۵۲۰ms ثبت می‌شود، و اسنپشاتِ
  // زودهنگام «۱ نقطه» می‌داد که بعداً ۲ شد — همان «ناپایداریِ دروغین» درِ دورِ پیش.
  let done = made;
  if (made) {
    let prevN = -1, stable = 0;
    for (let k = 0; k < 8 && stable < 2; k++) {
      await page.waitForTimeout(450);
      const st = await page.evaluate(READ);
      const cur = (st.drawings || []).find((o) => o.id === made.id) ||
                  (st.drawings || []).find((o) => o.name === type && !beforeSigs.has(sig(o))) || made;
      const n = (cur.points || []).length;
      stable = (n === prevN && n >= 2) ? stable + 1 : 0;
      prevN = n;
      done = cur;
    }
  }
  return { made: done, clicks };
}

(async () => {
  const types = toolTypes();
  const { ctx, page } = await openPage();
  const rep = { ranAt: new Date().toISOString(), symbol: SYM, viewport: [1366, 768],
                registrySize: Object.keys(types).length, positiveControl: null,
                tools: {}, meta: {}, summary: {} };
  let base = await page.evaluate(READ);
  if (base.error) { console.error('NO_CHART'); await ctx.close(); process.exit(2); }
  rep.baseline = { drawings: base.drawings.length, layers: base.layerCount, saved: base.saved,
                   savedKeys: base.savedKeys, axisName: base.axisName, lastClose: base.lastClose };
  const pane = base.pane;
  rep.pane = pane;

  // ── کنترلِ مثبت: «خط روند» باید segment بسازد، وگرنه سنسور کور است ──────
  const CONTROL = 'خط روند';
  const ctrlType = (types[CONTROL] || {}).overlayType || 'segment';
  const okSel = await selectTool(page, { title: CONTROL, via: 'rail', slot: 1 });
  const beforeCtrl = await page.evaluate(READ);
  const ctrl = okSel ? (await drawOnce(page, pane, ctrlType, beforeCtrl)).made : null;
  rep.positiveControl = { title: CONTROL, expectsOverlayType: ctrlType, selectable: okSel,
                          drew: !!ctrl, overlay: ctrl };
  if (!ctrl) {
    console.error('CONTROL FAILED: «خط روند» اورلیِ `' + ctrlType + '` نساخت — سنسور قابل‌اتکا ' +
                  'نیست و هیچ نتیجۀِ دیگری از این اجرا گزارش نمی‌شود.');
    fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
    await ctx.close();
    process.exit(3);
  }
  // فقط رسمِ خودِ آزمون برداشته می‌شود؛ ترسیم‌هایِ پیشینِ نماد دست‌نخورده می‌مانند
  await page.evaluate((id) => window.__borsChart.removeOverlay({ id: id }), ctrl.id);
  await page.waitForTimeout(700);
  base = await page.evaluate(READ);
  rep.afterControlCleanup = { drawings: base.drawings.length, saved: base.saved };

  // ── هدف‌ها ─────────────────────────────────────────────────────────────
  const { railSlots, arrows, targets } = await enumerateTargets(page);
  rep.meta.railSlots = railSlots;
  rep.meta.flyoutArrows = arrows;
  rep.meta.targetsFound = targets.length;
  const drawable = targets.filter((t) => types[t.title]);
  const wanted = drawable.filter((t) => !ONLY || t.title === ONLY);
  rep.meta.targetsInRegistry = drawable.length;
  rep.meta.targetsNonToolChrome = targets.filter((t) => !types[t.title]).map((t) => t.title);
  rep.meta.targetsWanted = wanted.length;

  for (const t of wanted) {
    const type = types[t.title].overlayType;
    const rec = { via: t.via, slot: t.slot, overlayType: type, reachable: false, drew: false };
    rec.reachable = await selectTool(page, t);
    if (!rec.reachable) { rep.tools[t.title] = rec; continue; }
    const before = await page.evaluate(READ);
    const beforeSigs = new Set(before.drawings.map(sig));
    const r = await drawOnce(page, pane, type, before);
    rec.clicks = r.clicks;
    rec.drew = !!r.made;
    rec.overlay = r.made || null;
    if (!r.made) { rep.tools[t.title] = rec; await closeFlyout(page); continue; }
    // لنگر از حالتِ کامل گرفته می‌شود: یکِ مکثِ کوتاه تا نقاطِ پایانی ثبت شوند.
    // اسنپشاتِ میانةِ رسم «ناپایداریِ دروغین» می‌سازد (یکِ نقطه در برابرِ دو نقطه) —
    // همان چیزی که دورِ پیش درِ matrix دیدیم و نتایجِ هشت‌گانه را بی‌معنا کرد.
    await page.waitForTimeout(700);
    const committed = await page.evaluate(READ);
    const madeNow = (committed.drawings || []).find((o) => o.id === r.made.id) || r.made;
    const id = madeNow.id;
    rec.anchor = madeNow.points;
    rec.anchorPointCount = madeNow.points.length;
    rec.totalPointNum = madeNow.totalPointNum ?? null;
    const anchorSig = sig(madeNow);

    const findMe = (st) => (st.drawings || []).find((o) => o.id === id) ||
                            (st.drawings || []).find((o) => sig(o) === anchorSig) || null;
    const probe = async (label, act) => {
      await act();
      const st = await page.evaluate(READ);
      const o = findMe(st);
      rec[label] = o ? { points: o.points } : { gone: true, drawings: st.drawings.length };
      if (!o) { rec[label + 'TimeStable'] = false; return; }
      const now = (o.points || []).map((p) => p.timestamp);
      const was = rec.anchor.map((p) => p.timestamp);
      const barNow = (o.points || []).map((p) => p.barTime);
      const barWas = rec.anchor.map((p) => p.barTime);
      rec[label + 'TimeStable'] = JSON.stringify(now) === JSON.stringify(was);
      // «همان کندل» شهادِ محکم‌تر است: بارِ زیرِ هرِ نقطه (timeِ کندل) عوض نشود
      rec[label + 'SameCandle'] = barWas.every((b, i) => b && barNow[i] === b);
      rec[label + 'VisibleRange'] = st.visibleRange;
    };

    await probe('afterZoom', async () => {
      await page.mouse.move(pane.left + Math.round(pane.w * 0.15), pane.top + Math.round(pane.h * 0.94));
      await page.mouse.wheel(0, -240);
      await page.waitForTimeout(800);
    });
    await probe('afterPan', async () => {
      // درگ از 0.62w×0.5h دقیقاً رویِ دومینِ نقطۀِ رسم فرود می‌آمد و **آن را جابه‌جا**
      // می‌کرد؛ آن «لنگر جابه‌جا شد» دروغِ خودِ هارنس بود (سنجشِ ۱۴۰-۰۷-۲۷: dataIndex
      // نقطۀِ دوم با آن حرکت عوض شد). pan از نوارِ پایینِ پن و به‌دور از نقاط انجام می‌شود.
      await page.mouse.move(pane.left + Math.round(pane.w * 0.80), pane.top + Math.round(pane.h * 0.94));
      await page.mouse.down();
      await page.mouse.move(pane.left + Math.round(pane.w * 0.58), pane.top + Math.round(pane.h * 0.94), { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(900);
    });
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.waitForTimeout(1400);
    await probe('afterResize', async () => {});
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.waitForTimeout(1100);

    await probe('afterLog', () => setScale(page, 'logarithm'));
    rec.axisNameInLog = (await page.evaluate(READ)).axisName;
    await probe('afterLinear', () => setScale(page, 'linear'));
    rec.axisNameInLinear = (await page.evaluate(READ)).axisName;

    await probe('afterRaw', () => setSeriesMode(page, 'خام'));
    const rawState = await page.evaluate(READ);
    rec.lastCloseRaw = rawState.lastClose;
    await probe('afterAdjusted', () => setSeriesMode(page, 'عملکردی'));
    const adjState = await page.evaluate(READ);
    rec.lastCloseAdjusted = adjState.lastClose;

    // ── reload: ماندگاری در stateِ خودی و بازیابی ──
    const savedNow = adjState.saved;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
    await page.waitForTimeout(6000);
    await page.evaluate(FIND);
    const re = await page.evaluate(READ);
    const sameSig = (re.drawings || []).find((o) => sig(o) === anchorSig);
    rec.beforeReloadSavedCount = savedNow;
    rec.afterReload = { drawings: re.drawings.length, saved: re.saved,
                        restoredExact: !!sameSig,
                        sameTypeCount: (re.drawings || []).filter((o) => o.name === type).length,
                        points: sameSig ? sameSig.points : null,
                        id: sameSig ? sameSig.id : null };

    // ── ویرایش: درگ از **پیکسلِ واقعیِ** نقطۀِ اول، نه از حدسِ مختصاتِ کلیک ──
    // drawOnce ممکن است پیش ازِ رسیدن به SPOTS[0] کامل شده باشد، پس «درگ از SPOTS[0]»
    // بی‌اثر می‌ماند (سنجش: editMoved 0/1 با آن روش). اینجا از خودِ موتور می‌پرسیم.
    // پیکسل از نقطۀِ **بازیابی‌شده** خوانده می‌شود: پس ازِ reload دید به آخرینِ کندل
    // می‌رود، پس مختصاتِ پیش‌از‌reload جایِ دیگری رویِ بوم می‌افتد (سنجش: درگِ بی‌اثر).
    const liveForEdit = (rec.afterReload && rec.afterReload.points && rec.afterReload.points.length)
      ? rec.afterReload.points : rec.anchor;
    const pt0 = liveForEdit[0] || {};
    const px = await page.evaluate(`(() => {
      const c = window.__borsChart;
      try {
        const r = c.convertToPixel([{ dataIndex: ${JSON.stringify(pt0.dataIndex ?? null)},
                                     timestamp: ${JSON.stringify(pt0.timestamp ?? null)},
                                     value: ${JSON.stringify(pt0.value ?? null)} }],
                                   { paneId: 'candle_pane' });
        const q = Array.isArray(r) ? r[0] : r;
        return q && Number.isFinite(q.x) ? { x: Math.round(q.x), y: Math.round(q.y) } : null;
      } catch (e) { return null; }
    })()`);
    // مختصاتِ convertToPixel نسبیِ بوم است، نه مختصاتِ صفحه — بی‌این اصلاح، درگِ ویرایش
    // رویِ نوارِ ابزار فرود می‌آمد و «ویرایش کار نمی‌کند» گزارش می‌شد (سنسور، نه محصول).
    const box = await page.evaluate(`(() => { const c = document.querySelector('canvas');
      const r = c.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top) }; })()`);
    rec.editStartPixel = px;
    rec.canvasOrigin = box;
    if (!px) { rep.tools[t.title] = { ...rec, editSkipped: 'no pixel' }; continue; }
    const sx = box.x + px.x, sy = box.y + px.y;
    const curId = (rec.afterReload.id) || id;
    await probe('afterEdit', async () => {
      // ویرایشِ نقطه با ابزارِ «انتخاب» انجام می‌شود، نه وقتی کرکره هنوز در حالتِ
      // رسم است؛ آن‌جا mouse-down آغازِ رسمِ تازه است (سنجش: با کرکرۀِ رسم، هیچ
      // نقطه‌ای جابه‌جا نشد و «ویرایش نمی‌کند» گزارش می‌شد — خطایِ توالی، نه نقص).
      await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').first()
        .click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(500);
      await page.locator('.tv-flyout-item', { hasText: 'پیکان انتخاب' }).first()
        .click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(600);
      await page.mouse.move(sx, sy);
      await page.mouse.down();
      await page.mouse.move(sx + 42, sy + 26, { steps: 6 });
      await page.mouse.up();
      await page.waitForTimeout(900);
    });
    rec.editMovedAnchor = !!rec.afterEdit && !rec.afterEdit.gone &&
      JSON.stringify(rec.afterEdit.points) !== JSON.stringify(rec.anchor);
    // ویرایشِ درست باید نقطه را به کندلِ دیگری ببرد (زمان عوض شود) و قیمتِ خودی بماند
    rec.editTimeChanged = !!rec.afterEdit && !rec.afterEdit.gone &&
      JSON.stringify(rec.afterEdit.points.map((p) => p.timestamp)) !==
      JSON.stringify(rec.anchor.map((p) => p.timestamp));

    // ── حذفِ رسمِ خودی (و فقط آن) ──
    await page.evaluate((oid) => window.__borsChart.removeOverlay({ id: oid }), curId);
    await page.waitForTimeout(800);
    const afterDelete = await page.evaluate(READ);
    rec.afterDeleteOwn = { drawings: afterDelete.drawings.length, saved: afterDelete.saved,
                           mineStillThere: !!(afterDelete.drawings || []).find((o) => sig(o) === anchorSig) };
    rep.tools[t.title] = rec;
    await closeFlyout(page);
  }

  const end = await page.evaluate(READ);
  const list = Object.entries(rep.tools);
  const drew = list.filter(([, v]) => v.drew);
  const KEYS = ['afterZoom', 'afterPan', 'afterResize', 'afterLog', 'afterLinear',
                'afterRaw', 'afterAdjusted', 'afterEdit'];
  rep.summary = {
    control: true,
    targetsInRegistry: rep.meta.targetsInRegistry,
    tested: list.length,
    reachable: list.filter(([, v]) => v.reachable).length,
    drawing: drew.length,
    dead: list.filter(([, v]) => v.reachable && !v.drew).map(([k]) => k),
    unreachable: list.filter(([, v]) => !v.reachable).map(([k]) => k),
    restoredExactAfterReload: drew.filter(([, v]) => v.afterReload && v.afterReload.restoredExact).length,
    persistedToOwnStorage: drew.filter(([, v]) => (v.beforeReloadSavedCount || 0) > 0 &&
      (v.afterReload.saved || 0) >= v.beforeReloadSavedCount).length,
    anchorTimeStableAllTransforms: drew.filter(([, v]) => KEYS.filter((k) => k !== 'afterEdit')
      .every((k) => v[k + 'TimeStable'])).length,
    sameCandleAllTransforms: drew.filter(([, v]) => KEYS.filter((k) => k !== 'afterEdit')
      .every((k) => v[k + 'SameCandle'])).length,
    perKeyStability: KEYS.reduce((a, k) => (a[k] = drew.filter(([, v]) => v[k + 'TimeStable']).length, a), {}),
    survivedTransformsAtAll: drew.filter(([, v]) => KEYS.every((k) => v[k] && !v[k].gone)).length,
    editMovedAnchor: drew.filter(([, v]) => v.editMovedAnchor).length,
    editMovedTime: drew.filter(([, v]) => v.editTimeChanged).length,
    deleteRemovedOwnDrawing: drew.filter(([, v]) => v.afterDeleteOwn && !v.afterDeleteOwn.mineStillThere).length,
    priceValueChangedAcrossSeries: drew.filter(([, v]) => {
      const st = v.afterRaw;
      return st && !st.gone && st.points && v.anchor &&
        st.points.some((p, i) => Math.abs((p.value ?? 0) - ((v.anchor[i] || {}).value ?? 0)) > 0.5);
    }).length,
    lastCloseRaw: drew.length ? rep.tools[drew[0][0]].lastCloseRaw : null,
    lastCloseAdjusted: drew.length ? rep.tools[drew[0][0]].lastCloseAdjusted : null,
    axisNameInLog: drew.length ? rep.tools[drew[0][0]].axisNameInLog : null,
    axisNameInLinear: drew.length ? rep.tools[drew[0][0]].axisNameInLinear : null,
    finalDrawings: end.drawings.length,
    finalSaved: end.saved,
    preexistingDrawingsTouched: end.drawings.length - rep.baseline.drawings,
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  const s = rep.summary;
  console.log(`registry=${rep.registrySize} targetsInRegistry=${s.targetsInRegistry} ` +
              `reachable=${s.reachable} drawing=${s.drawing} survivedAll=${s.survivedTransformsAtAll}`);
  console.log(`restored exact after reload: ${s.restoredExactAfterReload}/${s.drawing}  ` +
              `persisted to own storage: ${s.persistedToOwnStorage}/${s.drawing}`);
  console.log(`anchor time stable through 7 transforms: ${s.anchorTimeStableAllTransforms}/${s.drawing}`);
  console.log(`same-candle under every point through 7 transforms: ${s.sameCandleAllTransforms}/${s.drawing}`);
  console.log('per-transform stability: ' + JSON.stringify(s.perKeyStability));
  console.log(`edit moved: ${s.editMovedAnchor}/${s.drawing} (time changed ${s.editMovedTime}/${s.drawing})  own drawing deleted: ${s.deleteRemovedOwnDrawing}/${s.drawing}`);
  console.log(`price value changed across raw↔adjusted: ${s.priceValueChangedAcrossSeries}/${s.drawing}`);
  console.log(`lastClose raw=${s.lastCloseRaw} adjusted=${s.lastCloseAdjusted} axis log=${s.axisNameInLog} linear=${s.axisNameInLinear}`);
  console.log('dead (reachable, draws nothing): ' + JSON.stringify(s.dead));
  console.log('unreachable: ' + JSON.stringify(s.unreachable));
  console.log(`chrome (not tools): ${JSON.stringify(rep.meta.targetsNonToolChrome)}`);
  console.log(`pre-existing drawings touched: ${s.preexistingDrawingsTouched} ` +
              `(baseline ${rep.baseline.drawings} → final ${s.finalDrawings}, saved ${s.finalSaved})`);
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
