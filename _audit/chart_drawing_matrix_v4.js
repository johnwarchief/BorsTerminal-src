// _audit/chart_drawing_matrix_v4.js — ماتریسِ ۲۹ ابزارِ ترسیم، عملیات‌به‌عملیات، با شاهدِ تفکیکی
//
// چه چیزی بر v3 اضافه شد (و چرا v3 قابلِ استناد نبود):
// ۱) تفکیکِ «نامِ اورلی درِ موتور ثبت نشده» از «مسیرِ رابطِ من کار نکرد». درِ v3 بیست‌و‌یکِ
//    ابزار «رسم نکرد» (dead) می‌شد و علتش مشخص نبود. درِ v4 پیشِ آزمونِ رابط، همان
//    `overlayType` برنامه‌ای با `createOverlay()` ساخته می‌شود؛ این تابع درِ klinecharts v10
//    برایِ نامِ ثبت‌نشده `null` می‌دهد ⇒ شاهدِ مستقل، بی‌هرگز وابسته به کلیک.
// ۲) بودجۀِ نقطه: ابزارهایِ چندنقطه‌ای (xabcd، امواج، پیش‌کان) با پنج کلیکِ ثابتِ v3
//    تمام نمی‌شدند. درِ v4 تا هشت نقطه + یکِ دبل‌کلیکِ پایانی، و «تمام‌شدن» از ظهورِ ردیفِ
//    انبار (flushDrawings فقط درِ onDrawEnd می‌نویسد) خوانده می‌شود.
// ۳) ماندگاری با «بازخوانی» سنجیده می‌شود، نه فقط با نوشتن: پس ازِ reload هم ردیف و هم
//    دیدۀِ موتور بررسی می‌شود (درِ v3 این ستون هرگز اجرا نشد).
// ۴) حذفِ مستقل: دو رسم از همان ابزار ساخته می‌شود و یکی حذف می‌شود؛ بقایِ دیگری شرط است.
// ۵) مخفی‌سازی رویِ خودِ ترسیم سنجیده می‌شود (not only the button title).
// ۶) حالت‌هایِ صریح: PASS / FAIL / NOT_APPLICABLE(علت) / UNREACHABLE / UNMEASURABLE(علت) /
//    NOT_RUN. هیچ ابزاری به نتیجۀِ ابزارِ دیگر تعمیم داده نمی‌شود.
//
// ایمنی: پروفیلِ مرورگر برایِ هرِ اجرا موقت است (mkdtemp) و ترسیم‌هایِ محصول فقط درِ
// localStorageِ همان پروفیل می‌نشینند ⇒ صفرِ ترسیمِ واقعیِ کاربر درِ معرضِ خطر.
// «پاک‌کن» و «حذف تمام ترسیم‌ها» هم دقیقاً به همین دلیل تنها رویِ گروهِ خودیِ هارنس کار می‌کنند.
//
// اجرا:  node _audit/chart_drawing_matrix_v4.js
//        BORS_TOOL=trendLine   فقط یکِ ابزار
//        BORS_BASE / BORS_SYM / RA_BROWSER  پیش‌فرض‌ها مثلِ v3
const path = require('path');
const fs = require('fs');
const os = require('os');
const pw = require(path.join(process.cwd(), 'frontend', 'node_modules', 'playwright-core'));
const ROOT = process.cwd();
const OUT = path.join(ROOT, '_audit', 'chart_drawing_matrix_v4.json');
const CSV = path.join(ROOT, '_audit', 'chart_drawing_matrix_v4.csv');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = process.env.BORS_SYM || 'فولاد';
const ONLY = process.env.BORS_TOOL || '';
const TOOLBAR = path.join(ROOT, 'frontend', 'src', 'features', 'technical',
                          'nahayatnegar', 'components', 'DrawingToolbar.tsx');
const KEY = `fts.drawings.v1.${SYM}`;
const OWN = 'fts-draw';
const PROBE_GRP = 'v4-name-probe';

// ابزارهایِ غیررسمی: این‌ها «حالتِ نشانگر» یا «کنش»ند، نه سازندۀِ ترسیم.
// رسم/ویرایش/حذفِ منزوی برایشان معنا ندارد و صریح NOT_APPLICABLE ثبت می‌شود.
const MODE_IDS = new Set(['crosshair', 'dot', 'arrow']);
const ACTION_IDS = new Set(['eraser']);

function registry() {
  const src = fs.readFileSync(TOOLBAR, 'utf8');
  const start = src.indexOf('const toolSlots: ToolSlot[] = [');
  const body = src.slice(start, src.indexOf('\n  ];', start));
  const slots = [];
  const at = [...body.matchAll(/slotId: '([a-zA-Z]+)'/g)];
  for (let k = 0; k < at.length; k++) {
    const from = at[k].index;
    const to = k + 1 < at.length ? at[k + 1].index : body.length;
    const block = body.slice(from, to);
    const nm = /name: '([^']+)'/.exec(block);
    const items = [];
    const iRx = /id: '([^']+)', name: '([^']+)', overlayType: '([^']+)'/g;
    let i;
    while ((i = iRx.exec(block))) {
      if (!items.some((x) => x.id === i[1] && x.name === i[2])) {
        items.push({ id: i[1], name: i[2], overlayType: i[3] });
      }
    }
    slots.push({ slotId: at[k][1], slotName: nm ? nm[1] : '', items });
  }
  return slots;
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

// ground truth: انبارِ خودی + دیدۀِ موتور + وضعیتِ واقعیِ دیدنی بودن
const STATE = `(() => {
  const c = window.__borsChart;
  if (!c) return { error: 'NO_CHART' };
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(${JSON.stringify(KEY)}) || '[]') || []; } catch (e) {}
  const all = (c.getOverlays && c.getOverlays()) || [];
  const own = all.filter(o => o.groupId === ${JSON.stringify(OWN)});
  const row = (o) => ({ id: o.id ?? null, name: o.name ?? null,
    n: (o.points || []).length,
    pts: (o.points || []).map(p => ({ t: p.timestamp ?? null, v: p.value == null ? null : Math.round(p.value * 100) / 100 })),
    visible: (o.visible === undefined ? null : o.visible),
    // klinecharts v10 فیلدِ currentStep را می‌دهد نه step. قاعدۀِ «تمام‌شدن» از
    // خودِ موتور خوانده شد (probe_step.js): currentStep === -1 یعنی رسم بسته شده.
    currentStep: (o.currentStep === undefined ? null : o.currentStep),
    totalStep: (o.totalStep === undefined ? null : o.totalStep),
    keys: Object.keys(o).join(',') });
  const dl = (c.getDataList && c.getDataList()) || [];
  return {
    saved: saved.map(o => ({ id: o.id ?? null, name: o.name ?? null, n: (o.points || []).length,
      pts: (o.points || []).map(p => ({ t: p.timestamp ?? null, v: p.value == null ? null : Math.round(p.value * 100) / 100 })) })),
    savedCount: saved.length,
    own: own.map(row), ownCount: own.length,
    engineTotal: all.length,
    barCount: dl.length,
    lastTs: dl.length ? dl[dl.length - 1].timestamp : null,
    firstTs: dl.length ? dl[0].timestamp : null,
    visibilityTitle: (() => { const e = document.querySelector('.nn-left-toolbar [title^="ترسیم‌ها"]');
                              return e ? e.getAttribute('title') : null; })(),
    armedRail: (() => { const e = document.querySelector('.nn-left-toolbar .tv-slot-wrapper .tool-item.active');
                        return e ? (e.getAttribute('title') || '').trim() : null; })(),
    canvasDrawingClass: (() => { const e = document.querySelector('.nn-kline-chart');
                                 return e ? e.className : null; })(),
    pane: (() => { const s = c.getSize ? c.getSize('candle_pane', 'main') : null;
      return s ? { left: Math.round(s.left), top: Math.round(s.top),
                   w: Math.round(s.width), h: Math.round(s.height) } : null; })(),
    // pane مختصاتِ داخلِ کانتینرِ چارت را می‌دهد؛ کلیک نیازمندِ مبدأِ صفحه است
    chartRect: (() => { const e = document.querySelector('.nn-kline-chart') || document.querySelector('canvas');
      const r = e ? e.getBoundingClientRect() : null;
      return r ? { x: Math.round(r.left), y: Math.round(r.top) } : null; })(),
  };
})()`;

// کاوشِ ثبتِ نام: برنامه‌ای، بی‌هیچ کلیکِ رابطی. `createOverlay` درِ klinecharts v10
// برایِ نامِ ثبت‌نشده `null` برمی‌گرداند — پس این کاوش «آیا اصلاً چنین اورلی‌ای هست» را
// جدا از «رابط با کلیک می‌سازد یا نه» می‌سنجد.
async function probeOverlayName(arg) {
  const c = window.__borsChart;
  const dl = c.getDataList();
  if (!dl.length) return { error: 'NO_DATA', name: arg.name, returnedId: null, objects: [] };
  const n = dl.length;
  const mk = (i) => {
    const row = dl[Math.max(0, n - 1 - i * 6)];
    return { timestamp: row.timestamp, value: row.close };
  };
  const pts = [mk(6), mk(4), mk(2), mk(0)];
  try { c.removeOverlay({ groupId: arg.grp }); } catch (e) {}
  let id = null, err = null;
  try { id = c.createOverlay({ name: arg.name, groupId: arg.grp, points: pts }); }
  catch (e) { err = String((e && e.message) || e); }
  const got = (c.getOverlays() || []).filter((o) => o.groupId === arg.grp)
    .map((o) => ({ id: o.id ?? null, name: o.name ?? null, n: (o.points || []).length,
                   step: o.step ?? null, totalStep: o.totalStep ?? null }));
  try { c.removeOverlay({ groupId: arg.grp }); } catch (e) {}
  return { name: arg.name, returnedId: id ?? null, error: err, objects: got };
}

(async () => {
  const slots = registry();
  const tools = [];
  for (const s of slots) for (const it of s.items) tools.push({ ...it, slotId: s.slotId, slotName: s.slotName });
  const kinds = {};
  for (const t of tools) {
    t.kind = MODE_IDS.has(t.id) ? 'mode' : (ACTION_IDS.has(t.id) ? 'action' : 'drawing');
    kinds[t.kind] = (kinds[t.kind] || 0) + 1;
  }
  let headSha = '(unknown)';
  try { headSha = require('child_process').execSync('git rev-parse HEAD', { cwd: ROOT }).toString().trim(); }
  catch (e) { headSha = '(git failed: ' + e.message + ')'; }
  const rep = { ranAt: new Date().toISOString(), sha: headSha, symbol: SYM, base: BASE,
                viewport: [1366, 768],
                storageKey: KEY, ownGroup: OWN, registrySlots: slots.length, registryTools: tools.length,
                tools: {}, nameProbe: {}, summary: {} };

  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(os.tmpdir(), 'bors-m4-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  let autoAccept = false;
  let phase = 'boot';
  const logs = [];
  const page = ctx.pages()[0] || await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') logs.push({ phase, type: m.type(), text: m.text().slice(0, 200) }); });
  page.on('pageerror', (e) => logs.push({ phase, type: 'pageerror', text: String(e.message).slice(0, 200) }));
  const dialogHook = (d) => (autoAccept ? d.accept() : d.dismiss()).catch(() => {});
  ctx.on('dialog', dialogHook); page.on('dialog', dialogHook);

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
  if (!(await page.evaluate(FIND))) { console.error('NO_CHART_HANDLE'); await ctx.close(); process.exit(2); }
  // صبر برایِ شرطِ واقعی، نه خوابِ ثابت: بدخانۀِ سنجشِ قبلی با canvas دیدنی ولی
  // بی‌داده (barCount=0) شروع می‌شد و کلِ اجرا را بی‌معنا می‌کرد.
  const haveData = () => page.evaluate(`(() => {
    const c = window.__borsChart;
    return !!(c && c.getDataList && c.getDataList().length > 0);
  })()`);
  if (!(await haveData())) {
    await page.waitForTimeout(5000);
    await page.evaluate(FIND).catch(() => {});
  }
  await page.waitForFunction(`(() => {
    const c = window.__borsChart;
    return !!(c && c.getDataList && c.getDataList().length > 0);
  })`, null, { timeout: 120000 }).catch(() => {});

  const state = () => page.evaluate(STATE);
  const settle = async (cmp, limitMs = 9000) => {
    const t0 = Date.now();
    let last = await state();
    while (Date.now() - t0 < limitMs) {
      if (cmp(last)) return last;
      await page.waitForTimeout(500);
      last = await state();
    }
    return last;
  };
  let st0 = await state();
  const view = { pane: st0.pane, rect: st0.chartRect || { x: 0, y: 0 } };
  rep.baseline = { savedCount: st0.savedCount, ownCount: st0.ownCount, engineTotal: st0.engineTotal,
                   barCount: st0.barCount, pane: st0.pane, chartRect: st0.chartRect,
                   visibilityTitle: st0.visibilityTitle };
  if (!view.pane || !st0.barCount) { console.error('NO_PANE_OR_DATA: ' + JSON.stringify(st0).slice(0, 200)); await ctx.close(); process.exit(2); }

  const sig = (o) => `${o.name}:${JSON.stringify(o.pts)}`;
  // نقطه رویِ بوم: pane مختصاتِ داخلِ کانتینرِ چارت را می‌دهد، کلیکِ مرورگرِ صفحه را
  const spot = (fx, fy) => ({
    x: view.rect.x + view.pane.left + Math.round(view.pane.w * fx),
    y: view.rect.y + view.pane.top + Math.round(view.pane.h * fy),
  });
  // رسم تمام‌شده = currentStep === -1. این قاعده از خودِ موتور خوانده شد
  // (_scratch/live/probe_step.js): پس ازِ یکِ کلیک currentStep=2 و رسم باز است؛
  // با نقطۀِ آخر -1 می‌شود. ابزارهایِ تک‌نقطه‌ای (خطِ افقی/عمودی، برچسب) از
  // همان کلیکِ اول -1 می‌گیرند، پس با n>=2 سنجیدنشان غلط بود.
  const done = (o) => o.currentStep === -1;
  const freshDone = (x, base) => x.own.filter((o) => !base.has(sig(o)) && done(o));
  const freshAny = (x, base) => x.own.filter((o) => !base.has(sig(o)));
  const resetOwn = async () => {
    await page.keyboard.press('Escape').catch(() => {});
    await page.evaluate(`(() => {
      try { window.__borsChart.removeOverlay({ groupId: ${JSON.stringify(OWN)} }); } catch (e) {}
      try { localStorage.removeItem(${JSON.stringify(KEY)}); } catch (e) {}
    })()`);
    await page.waitForTimeout(700);
    const s = await settle((x) => x.ownCount === 0, 6000);
    if (s.pane) { view.pane = s.pane; if (s.chartRect) view.rect = s.chartRect; }
    return s;
  };
  const relaunch = async () => {
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 90000 });
    await page.waitForTimeout(5000);
    if (!(await page.evaluate(FIND))) return null;
    await page.waitForFunction(`(() => {
      const c = window.__borsChart;
      return !!(c && c.getDataList && c.getDataList().length > 0);
    })`, null, { timeout: 120000 }).catch(() => {});
    const s = await settle((x) => !!x.barCount, 30000);
    if (s.pane) { view.pane = s.pane; if (s.chartRect) view.rect = s.chartRect; }
    return s;
  };

  // ── رسم با رابط: تا هشت نقطه؛ موفقیت = ترسیمِ تمام‌شدۀِ تازه درِ موتور ─────
  // نقطه‌ها درِ نیمۀِ راستِ بوم انتخاب می‌شوند: timestampِ نقطۀِ اول اگر درِ سمتِ چپ
  // باشد، پس ازِ بازخوانی ازِ دیدۀِ خودکارِ چارت بیرون می‌افتد (سنجشِ
  // _scratch/live/probe_frame.js: convertToPixel → x=-22) و درگِ ویرایش رویِ
  // هیچ‌چیز نمی‌نشیند؛ آن «ویرایش نمی‌کند» artifactِ سنسور بود، نه رفتارِ محصول.
  const SPOTS = [[0.50, 0.28], [0.58, 0.52], [0.66, 0.34], [0.74, 0.60],
                 [0.82, 0.44], [0.88, 0.30], [0.94, 0.55], [0.62, 0.68]];
  const attempt = async (spotsList, s0) => {
    const base = new Set(s0.own.map(sig));
    const used = [];
    for (const [fx, fy] of spotsList) {
      const p = spot(fx, fy);
      used.push(p);
      await page.mouse.click(p.x, p.y);
      await page.waitForTimeout(600);
      const s = await settle((x) => freshDone(x, base).length > 0, 2200);
      const f = freshDone(s, base);
      if (f.length) {
        return { ok: true, clicks: used.length, state: s, fresh: f, used,
                 started: freshAny(s, base).length > 0,
                 storedFresh: s.saved.filter((o) => !base.has(sig(o))).length };
      }
    }
    const sf = await state();
    if (freshAny(sf, base).length) {
      // رسم باز مانده: نقطه آمده ولی step به سقف نرسیده — دبل‌کلیکِ پایانی
      const last = used[used.length - 1];
      await page.mouse.dblclick(last.x, last.y).catch(() => {});
      await page.waitForTimeout(800);
      const s2 = await settle((x) => freshDone(x, base).length > 0, 5000);
      const f2 = freshDone(s2, base);
      return { ok: f2.length > 0, clicks: used.length + 1, state: s2, fresh: f2, used,
               started: true, closedBy: f2.length ? 'dblclick' : null,
               storedFresh: s2.saved.filter((o) => !base.has(sig(o))).length };
    }
    return { ok: false, clicks: used.length, state: sf, fresh: [], used, started: false,
             storedFresh: sf.saved.filter((o) => !base.has(sig(o))).length };
  };

  // ── کنترلِ مثبت: خط روند باید هم رابط و هم کاوشِ نام را رد کند ────────────
  phase = 'positive-control';
  await resetOwn();
  await page.locator('.nn-left-toolbar .tool-item[title="خط روند"]').first().click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(400);
  const pcDraw = await attempt(SPOTS.slice(0, 4), await state());
  rep.positiveControl = { toolId: 'trendLine', clicks: pcDraw.clicks, drew: pcDraw.ok,
                          fresh: pcDraw.fresh, savedCount: pcDraw.state.savedCount,
                          ownCount: pcDraw.state.ownCount };
  if (!pcDraw.ok) {
    console.error('CONTROL FAILED: «خط روند» ترسیمِ تمام‌شدۀِ تازه نساخت — سنسور کور است؛ ' +
                  'هیچ نتیجه‌ای گزارش نمی‌شود. seen=' + JSON.stringify(pcDraw.state.own).slice(0, 300));
    fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
    await ctx.close();
    process.exit(3);
  }

  // ── کاوشِ ثبتِ نام، برایِ هر overlayTypeِ سازندۀِ ترسیم ──────────────────
  phase = 'name-probe';
  const typesToProbe = [...new Set(tools.filter((t) => t.kind === 'drawing').map((t) => t.overlayType))];
  const probeName = async (name) => (await page.evaluate(probeOverlayName, { name, grp: PROBE_GRP })) ||
    { name, returnedId: null, error: 'PROBE_RETURNED_UNDEFINED', objects: [] };
  for (const ty of typesToProbe) {
    rep.nameProbe[ty] = await probeName(ty);
    // نام‌هایی که رابط به‌جای نوعِ خامِ رجیستری می‌فرستد (بازنگاشتِ handleSelectTool)
    if (ty === 'fibonacciLine') rep.nameProbe['tvFibLog'] = await probeName('tvFibLog');
    if (ty === 'measure') rep.nameProbe['ftsMeasure'] = await probeName('ftsMeasure');
    if (ty === 'rect') rep.nameProbe['ftsPosition'] = await probeName('ftsPosition');
  }
  // ارجاعِ سند: نامِ واقعیِ اورلی‌ای که رابط برایِ پیکانِ رسم می‌فرستد
  await resetOwn();

  // ── چرخۀِ هرِ ابزار ───────────────────────────────────────────────────────
  const only = ONLY.split(',').map((s) => s.trim()).filter(Boolean);
  const wanted = tools.filter((t) => !only.length || only.includes(t.id) || only.includes(t.name));
  for (const t of wanted) {
    const key = `${t.slotId}:${t.id}:${t.name}`;
    phase = 'tool:' + key;
    await resetOwn();
    const rec = { slotId: t.slotId, slotName: t.slotName, toolId: t.id, name: t.name,
                  overlayType: t.overlayType, kind: t.kind, reachable: false };
    const entry = rep.nameProbe[t.overlayType];
    rec.nameProbe = entry ? { registered: !!(entry.returnedId || (entry.objects || []).length),
                              returnedId: entry.returnedId, error: entry.error,
                              objects: entry.objects } : null;

    // ۱) دسترسی و سلاح‌شدن
    await page.keyboard.press('Escape').catch(() => {});
    await page.mouse.move(600, 28).catch(() => {});
    await page.waitForTimeout(220);
    const railTitles = () => page.evaluate(`(() => [...document.querySelectorAll(
      '.nn-left-toolbar .tv-slot-wrapper .tool-item')].map(e => (e.getAttribute('title')||'').trim()))()`);
    const armed = () => page.evaluate(`(() => {
      const a = document.querySelector('.nn-left-toolbar .tv-slot-wrapper .tool-item.active');
      const k = document.querySelector('.nn-kline-chart');
      return { rail: a ? (a.getAttribute('title')||'').trim() : null,
               drawingClass: k ? /drawing-active-crosshair/.test(k.className) : null };
    })()`);
    const railEl = page.locator(`.nn-left-toolbar .tool-item[title="${t.name}"]`).first();
    if (await railEl.count().catch(() => 0)) {
      const a0 = await armed();
      if (a0.rail !== t.name) {
        await railEl.click({ timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(450);
      }
      rec.via = 'rail';
      rec.reachable = true;
    } else {
      const arrows = await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').count();
      for (let i = 0; i < arrows && !rec.reachable; i++) {
        await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i)
          .click({ timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(500);
        const child = page.locator('.tv-flyout-item', { hasText: t.name }).first();
        if (await child.count().catch(() => 0)) {
          await child.click({ timeout: 4000 }).catch(() => {});
          await page.waitForTimeout(450);
          // کلیکِ دومِ فلایاوت منو را می‌بندد و انتخاب را می‌سوزاند: فقط تا وقتی که
          // رابط خودِ ابزار را «فعال» نشان دهد دوباره تلاش می‌شود.
          for (let g = 0; g < 4 && (await armed()).rail !== t.name; g++) {
            await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i)
              .click({ timeout: 4000 }).catch(() => {});
            await page.waitForTimeout(450);
            await page.locator('.tv-flyout-item', { hasText: t.name }).first()
              .click({ timeout: 4000 }).catch(() => {});
            await page.waitForTimeout(450);
          }
          rec.via = `flyout:${i}`;
          rec.reachable = true;
        } else {
          await page.keyboard.press('Escape').catch(() => {});
          await page.waitForTimeout(200);
        }
      }
    }
    rec.armedAfterSelect = await armed();
    rec.railTitles = await railTitles();
    if (!rec.reachable) {
      rec.status = { reach: 'UNREACHABLE' };
      rep.tools[key] = rec;
      continue;
    }
    rec.status = { reach: 'PASS' };

    // حالت‌ها و کنش‌ها: رسم/ویرایش/حذفِ منزوی برایشان معنا ندارد
    if (rec.kind === 'mode') {
      rec.status = { reach: 'PASS', draw: 'NOT_APPLICABLE', persist: 'NOT_APPLICABLE',
                     edit: 'NOT_APPLICABLE', hide: 'NOT_APPLICABLE', deleteOne: 'NOT_APPLICABLE',
                     isolated: 'NOT_APPLICABLE', coherence: 'NOT_APPLICABLE' };
      rec.note = 'cursor mode (overlayType=crosshair): it selects a pointer style, not a drawing';
      rep.tools[key] = rec;
      continue;
    }
    if (rec.kind === 'action') {
      // «پاک‌کن» درِ خودِ handleSelectTool گروهِ ترسیمِ خودی را می‌برد: کنشِ حذف، نه رسم
      const b = (await state()).ownCount;
      const after = await settle((x) => x.ownCount === 0, 5000);
      rec.status = { reach: 'PASS', draw: 'NOT_APPLICABLE', persist: 'NOT_APPLICABLE',
                     edit: 'NOT_APPLICABLE', hide: 'NOT_APPLICABLE',
                     deleteOne: after.ownCount === 0 && b === 0 ? 'NOT_RUN' : 'NOT_APPLICABLE',
                     isolated: 'NOT_APPLICABLE', coherence: 'NOT_APPLICABLE' };
      rec.note = 'action, not a drawing: selecting it removes the whole own group (ownCount ' + b + ' -> ' + after.ownCount + ')';
      rep.tools[key] = rec;
      continue;
    }

    // ۲) رسم: تا هشت نقطه؛ موفقیت = ترسیمِ تمام‌شدۀِ تازه درِ موتور
    const s0 = await state();
    const drawn = await attempt(SPOTS, s0);
    const clicked = drawn.used;
    rec.clicks = drawn.clicks;
    rec.drew = drawn.ok;
    rec.newEngine = drawn.fresh;
    rec.effectiveEngineName = drawn.fresh.length ? drawn.fresh[0].name : null;
    rec.startedButUnfinished = !drawn.ok && drawn.started;
    rec.storedFreshAfterDraw = drawn.storedFresh;
    rec.status.draw = drawn.ok ? 'PASS' : 'FAIL';
    rec.drawNote = drawn.ok ? null
      : (rec.nameProbe && rec.nameProbe.registered === false
          ? `overlayType '${t.overlayType}' is not a registered overlay name: createOverlay -> ${JSON.stringify(rec.nameProbe.returnedId)}${rec.nameProbe.error ? ' / ' + rec.nameProbe.error : ''}`
          : (drawn.started
              ? `engine made an overlay for '${t.overlayType}' but it never reached currentStep>=totalStep in ${drawn.clicks} clicks; seen=${JSON.stringify(drawn.state.own).slice(0, 220)}`
              : `tool armed but no overlay appeared in the own group after ${drawn.clicks} clicks (armed rail=${JSON.stringify((rec.armedAfterSelect || {}).rail)})`));

    if (!rec.drew) {
      rec.status.persist = 'NOT_RUN'; rec.status.edit = 'NOT_RUN'; rec.status.hide = 'NOT_RUN';
      rec.status.deleteOne = 'NOT_RUN'; rec.status.isolated = 'NOT_RUN';
      rec.status.coherence = rec.nameProbe && rec.nameProbe.registered === false ? 'NOT_APPLICABLE' : 'NOT_RUN';
      rep.tools[key] = rec;
      continue;
    }

    // ۳) ماندگاری پس ازِ ذخیره و بازخوانی
    const preReload = await state();
    rec.beforeReload = { saved: preReload.savedCount, own: preReload.ownCount,
                         ownDetail: preReload.own };
    const after = await relaunch();
    if (!after) {
      rec.status.persist = 'UNMEASURABLE';
      rec.persistNote = 'chart handle lost after reload';
    } else {
      const pr = await settle((x) => x.savedCount > 0 || x.ownCount > 0, 15000);
      rec.afterReload = { saved: pr.savedCount, own: pr.ownCount, engineTotal: pr.engineTotal,
                          ownDetail: pr.own };
      rec.persisted = pr.savedCount >= 1;
      rec.restoredInEngine = pr.ownCount >= 1;
      rec.status.persist = (rec.persisted && rec.restoredInEngine) ? 'PASS'
        : (rec.persisted ? 'UNMEASURABLE' : 'FAIL');
      rec.persistNote = rec.status.persist === 'PASS' ? null
        : `stored=${pr.savedCount} engineOwnAfterReload=${pr.ownCount} (before reload stored=${rec.beforeReload.saved} own=${rec.beforeReload.own})`;
    }
    if (rec.status.persist !== 'PASS') { rep.tools[key] = rec; continue; }

    // ۴) ویرایش: نقطه‌ای را می‌کشیم که درِ دید باشد. pts[0]ِ خام اغلب پس ازِ
    //    بازخوانی بیرونِ ویژپورتِ خودکارِ چارت می‌افتد و درگ بی‌هدف می‌ماند
    //    (سنجشِ _scratch/live/probe_frame.js: x=-22 و جابه‌جایی=false، در حالی که
    //    درگ رویِ نقطۀِ دیدنی همان ترسیم را واقعاً جابه‌جا کرد).
    const anchor0 = rec.newEngine[0];
    const anchorOwnId = anchor0 ? anchor0.id : null;
    const anchorPts = anchor0 ? JSON.stringify(anchor0.pts || []) : null;
    const ptsNow = (((await state()).own.find((o) => o.id === anchorOwnId) || anchor0) || {}).pts || [];
    const cand = await page.evaluate((list) => {
      const c = window.__borsChart;
      const b = document.querySelector('canvas').getBoundingClientRect();
      let s = { width: b.width, height: b.height };
      try { const q = c.getSize && c.getSize('candle_pane', 'main'); if (q) s = q; } catch (e) {}
      const out = [];
      list.forEach((p, i) => {
        let r = null;
        try {
          const z0 = c.convertToPixel([{ timestamp: p.t, value: p.v }], { paneId: 'candle_pane' });
          const z = Array.isArray(z0) ? z0[0] : z0;
          if (z && Number.isFinite(z.x) && Number.isFinite(z.y)) r = { x: z.x, y: z.y };
        } catch (e) { r = null; }
        out.push({ i, t: p.t, v: p.v, rel: r,
                   page: r ? { x: Math.round(b.left + r.x), y: Math.round(b.top + r.y) } : null,
                   inside: !!r && r.x >= 8 && r.y >= 8 && r.x <= s.width - 8 && r.y <= s.height - 8 });
      });
      return { cands: out, paneW: Math.round(s.width), paneH: Math.round(s.height),
               canvas: { x: Math.round(b.left), y: Math.round(b.top) } };
    }, ptsNow);
    rec.editCandidates = cand.cands;
    rec.editPane = { w: cand.paneW, h: cand.paneH, canvas: cand.canvas };
    const chosen = cand.cands.filter((x) => x.inside && x.page).sort((a, b) => a.i - b.i)[0] || null;
    const px = chosen ? chosen.page : null;
    const pxSource = chosen ? 'convertToPixel: first point inside the viewport'
      : (cand.cands.some((x) => x.page)
          ? 'every anchor point is outside the current viewport'
          : 'convertToPixel returned nothing usable');
    rec.editPixel = px; rec.pixelSource = pxSource;
    await page.locator('.nn-left-toolbar .tool-item[title="پیکان انتخاب"]').first()
      .click({ timeout: 3000 }).catch(async () => {
        await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').first().click({ timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(400);
        await page.locator('.tv-flyout-item', { hasText: 'پیکان انتخاب' }).first().click({ timeout: 3000 }).catch(() => {});
      });
    await page.waitForTimeout(400);
    const ownBeforeEdit = (await state()).ownCount;
    if (px) {
      await page.mouse.move(px.x, px.y);
      await page.waitForTimeout(250);
      await page.mouse.down();
      await page.waitForTimeout(250);
      await page.mouse.move(px.x + 46, px.y + 30, { steps: 10 });
      await page.waitForTimeout(300);
      await page.mouse.up();
      await page.waitForTimeout(1000);
    }
    const s2 = await settle((x) => {
      const o = x.own.find((q) => q.id === anchorOwnId) || x.own[0];
      return !!o && anchorPts && JSON.stringify(o.pts) !== anchorPts;
    }, 8000);
    const o2 = s2.own.find((q) => q.id === anchorOwnId) || s2.own[0] || null;
    rec.editMovedEngine = !!o2 && !!anchorPts && JSON.stringify(o2.pts) !== anchorPts;
    rec.editMovedStored = s2.savedCount >= 1 && s2.saved.some((o) => JSON.stringify(o.pts) !== anchorPts);
    rec.ownAfterEdit = s2.ownCount;
    rec.editDrewExtraOverlay = s2.ownCount > ownBeforeEdit;
    rec.status.edit = (rec.editMovedEngine || rec.editMovedStored) ? 'PASS'
      : (!px ? 'UNMEASURABLE' : (rec.editDrewExtraOverlay ? 'UNMEASURABLE' : 'FAIL'));
    rec.editNote = rec.status.edit === 'PASS' ? null
      : (rec.status.edit === 'UNMEASURABLE'
          ? `sensor has no usable target (${pxSource}; candidates=${JSON.stringify(cand.cands.map((x) => [x.i, x.rel]))})`
          : `drag at a visible anchor point (${px.x},${px.y}) did not move the drawing; pts before=${anchorPts} after=${o2 ? JSON.stringify(o2.pts) : 'gone'}`);

    // ۵) مخفی‌سازی و نمایشِ مجدد، رویِ خودِ ترسیم
    const v0 = await state();
    const vis0 = v0.own.map((o) => o.visible);
    await page.locator('.nn-left-toolbar [title^="ترسیم‌ها"]').first().click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(900);
    const v1 = await state();
    await page.locator('.nn-left-toolbar [title^="ترسیم‌ها"]').first().click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(900);
    const v2 = await state();
    rec.visibility = { before: vis0, hidden: v1.own.map((o) => o.visible),
                       back: v2.own.map((o) => o.visible),
                       titleBefore: v0.visibilityTitle, titleAfter: v1.visibilityTitle,
                       titleBack: v2.visibilityTitle };
    const titleMoved = v0.visibilityTitle !== v1.visibilityTitle && v1.visibilityTitle !== v2.visibilityTitle;
    const flagsSeen = v1.own.some((o) => o.visible !== null);
    rec.status.hide = (flagsSeen ? v1.own.every((o) => o.visible === false) && v2.own.every((o) => o.visible !== false)
                                 : titleMoved) ? 'PASS'
      : (flagsSeen || titleMoved) ? 'FAIL' : 'UNMEASURABLE';
    rec.hideNote = rec.status.hide === 'PASS' ? null
      : `engine exposes visible=${JSON.stringify(flagsSeen)} titleMoved=${titleMoved} ` +
        `titles=${v0.visibilityTitle}|${v1.visibilityTitle}|${v2.visibilityTitle}`;

    // ۶) رسمِ دوم از همان ابزار، سپس حذفِ یکی ← حذفِ منزوی
    await page.keyboard.press('Escape').catch(() => {});
    const railBack = page.locator(`.nn-left-toolbar .tool-item[title="${t.name}"]`).first();
    if ((await armed()).rail !== t.name) {
      if (await railBack.count().catch(() => 0)) {
        await railBack.click({ timeout: 3000 }).catch(() => {});
      } else {
        const arrows = await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').count();
        for (let i = 0; i < arrows; i++) {
          await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i).click({ timeout: 3000 }).catch(() => {});
          await page.waitForTimeout(400);
          const child = page.locator('.tv-flyout-item', { hasText: t.name }).first();
          if (await child.count().catch(() => 0)) { await child.click({ timeout: 3000 }).catch(() => {}); break; }
          await page.keyboard.press('Escape').catch(() => {});
        }
      }
      await page.waitForTimeout(400);
    }
    const before2 = await state();
    const second = await attempt(SPOTS.slice(3, 8), before2);
    const s3 = second.state;
    rec.second = { drew: second.ok, clicks: second.clicks, own: second.fresh,
                   ownCount: s3.ownCount, savedCount: s3.savedCount };
    rec.coherenceAtDraw = { engineOwn: s3.ownCount, stored: s3.savedCount,
                            agree: s3.ownCount === s3.savedCount };

    // نشانیِ حذف هم نقطۀِ دیدنیِ همانِ ترسیم است (نه کلیکِ نخستِ خام که پس ازِ
    // بازخوانی ممکن است بیرونِ ویژپورت باشد)
    const delTarget = (rec.editMovedEngine && px) ? { x: px.x + 46, y: px.y + 30 }
      : (rec.editPixel || clicked[0] || spot(0.5, 0.3));
    await page.mouse.click(delTarget.x, delTarget.y).catch(() => {});
    await page.waitForTimeout(500);
    await page.keyboard.press('Delete').catch(() => {});
    await page.waitForTimeout(1000);
    let s4 = await settle((x) => x.ownCount < s3.ownCount, 7000);
    let viaEraser = false;
    if (s4.ownCount >= s3.ownCount) {
      // شاخۀِ پاک‌کن. توجه: درِ خودِ رابط، «انتخابِ پاک‌کن» کلِ گروهِ خودی را می‌برد
      // (handleSelectTool → removeOverlay({groupId}))، پس این شاخه حذفِ منزوی نمی‌دهد
      // و اگر خورد، علتِ NOT_APPLICABLE بودنِ حذفِ منزوی ثبت می‌شود.
      await page.locator('.nn-left-toolbar .tool-item[title="پاک‌کن"]').first()
        .click({ timeout: 3000 }).catch(async () => {
          await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').first().click({ timeout: 3000 }).catch(() => {});
          await page.waitForTimeout(400);
          await page.locator('.tv-flyout-item', { hasText: 'پاک‌کن' }).first().click({ timeout: 3000 }).catch(() => {});
        });
      viaEraser = true;
      await page.mouse.click(delTarget.x, delTarget.y).catch(() => {});
      await page.waitForTimeout(1000);
      s4 = await settle((x) => x.ownCount < s3.ownCount, 7000);
    }
    const removedOne = s4.ownCount < s3.ownCount;
    const othersSurvived = s4.ownCount >= 1;
    rec.deleteOne = { tried: true, viaEraser, before: s3.ownCount, after: s4.ownCount,
                      removed: removedOne, survivors: s4.own.map((o) => o.name),
                      storedAfter: s4.savedCount };
    rec.status.deleteOne = removedOne ? 'PASS' : 'FAIL';
    if (!removedOne) {
      rec.status.isolated = 'NOT_RUN';
      rec.isolatedNote = 'nothing was removed, so isolation could not be measured';
    } else if (s3.ownCount < 2) {
      rec.status.isolated = 'NOT_RUN';
      rec.isolatedNote = `only ${s3.ownCount} drawing existed (second drawing of the same tool did not complete)`;
    } else if (othersSurvived) {
      rec.status.isolated = 'PASS';
    } else {
      rec.status.isolated = 'FAIL';
      rec.isolatedNote = viaEraser
        ? 'the eraser path removed every own drawing (own-group wipe is what selecting it does)'
        : `deleting one removed ${s3.ownCount}, survivors ${s4.ownCount}`;
    }

    // ۷) هماهنگیِ وضعیتِ موتور با ترسیمِ انبار: بی‌کنسلی درِ انبار و بی‌ردیفِ بی‌ترسیم
    const s5 = await settle((x) => x.ownCount === x.savedCount, 12000);
    rec.coherence = { engineOwn: s5.ownCount, stored: s5.savedCount, waitedMs: 12000 };
    rec.status.coherence = (s5.ownCount === s5.savedCount && rec.coherenceAtDraw.agree) ? 'PASS' : 'FAIL';
    rec.coherenceNote = rec.status.coherence === 'PASS' ? null
      : `at draw: engine=${rec.coherenceAtDraw.engineOwn} stored=${rec.coherenceAtDraw.stored}; ` +
        `after delete and 12s settle: engine=${s5.ownCount} stored=${s5.savedCount}`;
    rep.tools[key] = rec;
  }

  // ── «حذف تمام ترسیم‌ها»: لغو، سپس تأیید ─────────────────────────────────
  phase = 'delete-all';
  await resetOwn();
  await page.locator('.nn-left-toolbar .tool-item[title="خط روند"]').first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(400);
  const dTarget = await attempt(SPOTS.slice(0, 4), await state());
  const d0 = dTarget.state;
  rep.deleteAllTarget = { completed: dTarget.ok, clicks: dTarget.clicks,
                          saved: d0.savedCount, own: d0.ownCount };
  await page.locator('.nn-left-toolbar [title="حذف تمام ترسیم‌ها"]').first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(1000);
  const dCancel = await state();
  autoAccept = true;
  await page.locator('.nn-left-toolbar [title="حذف تمام ترسیم‌ها"]').first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(1500);
  const dAccept = await settle((x) => x.ownCount === 0, 8000);
  autoAccept = false;
  rep.deleteAll = {
    hadTarget: dTarget.ok && d0.ownCount > 0 && d0.savedCount > 0,
    targetSaved: d0.savedCount, targetOwn: d0.ownCount,
    cancel: { saved: dCancel.savedCount, own: dCancel.ownCount,
              held: dCancel.savedCount === d0.savedCount && dCancel.ownCount === d0.ownCount },
    accept: { saved: dAccept.savedCount, own: dAccept.ownCount, cleared: dAccept.savedCount === 0 && dAccept.ownCount === 0 },
  };

  const list = Object.entries(rep.tools);
  const count = (op, ...vals) => list.filter(([, v]) => vals.includes((v.status || {})[op])).length;
  rep.summary = {
    registryTools: tools.length, tested: list.length,
    drawingTools: list.filter(([, v]) => v.kind === 'drawing').length,
    modes: list.filter(([, v]) => v.kind === 'mode').length,
    actions: list.filter(([, v]) => v.kind === 'action').length,
    reach: { PASS: count('reach', 'PASS'), UNREACHABLE: count('reach', 'UNREACHABLE') },
    draw: { PASS: count('draw', 'PASS'), FAIL: count('draw', 'FAIL'),
            NOT_APPLICABLE: count('draw', 'NOT_APPLICABLE'), NOT_RUN: count('draw', 'NOT_RUN') },
    persist: { PASS: count('persist', 'PASS'), FAIL: count('persist', 'FAIL'),
               UNMEASURABLE: count('persist', 'UNMEASURABLE'), NOT_RUN: count('persist', 'NOT_RUN') },
    edit: { PASS: count('edit', 'PASS'), FAIL: count('edit', 'FAIL'),
            UNMEASURABLE: count('edit', 'UNMEASURABLE'), NOT_RUN: count('edit', 'NOT_RUN') },
    hide: { PASS: count('hide', 'PASS'), FAIL: count('hide', 'FAIL'),
            UNMEASURABLE: count('hide', 'UNMEASURABLE'), NOT_RUN: count('hide', 'NOT_RUN') },
    deleteOne: { PASS: count('deleteOne', 'PASS'), FAIL: count('deleteOne', 'FAIL'), NOT_RUN: count('deleteOne', 'NOT_RUN') },
    isolated: { PASS: count('isolated', 'PASS'), FAIL: count('isolated', 'FAIL'), NOT_RUN: count('isolated', 'NOT_RUN') },
    coherence: { PASS: count('coherence', 'PASS'), FAIL: count('coherence', 'FAIL'),
                 NOT_APPLICABLE: count('coherence', 'NOT_APPLICABLE'), NOT_RUN: count('coherence', 'NOT_RUN') },
    unregisteredNames: Object.entries(rep.nameProbe)
      .filter(([, v]) => !(v && (v.returnedId || (v.objects || []).length))).map(([k]) => k),
    deleteAll: rep.deleteAll,
  };
  rep.console = logs.slice(0, 120);

  const rows = [['key', 'slot', 'toolId', 'name', 'overlayType', 'kind', 'reach', 'draw', 'persist',
                 'edit', 'hide', 'deleteOne', 'isolated', 'coherence', 'nameRegistered', 'note']];
  for (const [k, v] of list) {
    const s = v.status || {};
    rows.push([k, v.slotId, v.toolId, v.name, v.overlayType, v.kind, s.reach, s.draw, s.persist,
               s.edit, s.hide, s.deleteOne, s.isolated, s.coherence,
               v.nameProbe ? String(v.nameProbe.registered) : '',
               (v.drawNote || v.persistNote || v.editNote || v.hideNote || v.isolatedNote || v.note || '').replace(/[\t\n]/g, ' ')]);
  }
  fs.writeFileSync(CSV, '\uFEFF' + rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\r\n'), 'utf8');
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  const sm = rep.summary;
  console.log(`registry=${sm.registryTools} tested=${sm.tested} drawing=${sm.drawingTools} modes=${sm.modes} actions=${sm.actions}`);
  console.log(`reach ${JSON.stringify(sm.reach)}`);
  console.log(`draw ${JSON.stringify(sm.draw)}`);
  console.log(`persist ${JSON.stringify(sm.persist)}`);
  console.log(`edit ${JSON.stringify(sm.edit)}`);
  console.log(`hide ${JSON.stringify(sm.hide)}`);
  console.log(`deleteOne ${JSON.stringify(sm.deleteOne)} isolated ${JSON.stringify(sm.isolated)}`);
  console.log(`coherence ${JSON.stringify(sm.coherence)}`);
  console.log(`unregistered overlayType names: ${JSON.stringify(sm.unregisteredNames)}`);
  console.log(`deleteAll hadTarget=${sm.deleteAll.hadTarget} cancelHeld=${sm.deleteAll.cancel.held} acceptCleared=${sm.deleteAll.accept.cleared} (target ${sm.deleteAll.targetSaved} -> cancel ${sm.deleteAll.cancel.saved} -> accept ${sm.deleteAll.accept.saved})`);
  console.log('csv: ' + CSV);
  console.log('json: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
