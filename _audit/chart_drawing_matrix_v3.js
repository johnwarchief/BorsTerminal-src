// _audit/chart_drawing_matrix_v3.js — ماتریسِ ۲۹ ابزارِ ترسیم، با تشخیصِ رسم از stateِ خودیِ محصول
//
// چرا v3 (و نه ترمیمِ v2): تشخیصِ «این ابزار چیزی رسم کرد؟» درِ v2 با نامِ اورلیِ
// klinecharts انجام می‌شد و نام‌هایِ `rect`/`crosshair` میانِ چندِ ابزار و لایه‌هایِ موتور
// مشترک‌اند ⇒ نتیجه‌هایِ «رسم کرد» برایِ آن نام‌ها قابلِ استناد نبود (مالک همین را رد کرد).
// درِ v3 سیگنالِ ground-truth، **انبارِ ترسیمِ خودیِ محصول** است:
// `localStorage['fts.drawings.v1.<symbol>']` — جاییِ که فقط ترسیمِ کاربر می‌نشیند و هیچ
// لایه‌ای از موتور درِ آن نیست. پس اشتراکِ نامِ figure دیگر بی‌معنا نمی‌سازد.
//
// registry بی‌hardcode از خودِ `DrawingToolbar.tsx` خوانده می‌شود: هرِ `toolId` با
// `name` و `overlayType` و شیارِ والدش. برایِ هرِ toolId این چرخه سنجیده می‌شود:
//   دسترسی (rail یا فلایاوت) ← رسم ← ماندگاری ← انتخاب/ویرایش ← مخفی‌سازی ←
//   حذفِ یکِ ابزار بدونِ اثر رویِ بقیه ← هماهنگیِ وضعیتِ موتور با ترسیمِ قابل‌مشاهده.
// و درِ پایان، «حذف تمام ترسیم‌ها» درِ هرِ دو شاخه: **لغو** (دیالوگِ بومی رد می‌شود ⇒
// هیچ ترسیمی نمی‌میرد) و **تأیید** (همۀِ رسم‌هایِ خودی پاک می‌شوند، بی‌دست‌زدنِ چیزِ دیگر).
//
// پروفایلِ مرورگر موقتِ هرِ اجرای است، پس صفرِ ترسیمِ از‌پیش‌موجودِ کاربر درِ معرض خطر نیست.
// اجرا: node _audit/chart_drawing_matrix_v3.js   [BORS_TOOL=trendLine برایِ تک‌آزمون]
const path = require('path');
const fs = require('fs');
const os = require('os');
const pw = require(path.join(process.cwd(), 'frontend', 'node_modules', 'playwright-core'));
const ROOT = process.cwd();
const OUT = path.join(ROOT, '_audit', 'chart_drawing_matrix_v3.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = process.env.BORS_SYM || 'فولاد';
const ONLY = process.env.BORS_TOOL || '';
const TOOLBAR = path.join(ROOT, 'frontend', 'src', 'features', 'technical',
                          'nahayatnegar', 'components', 'DrawingToolbar.tsx');
const KEY = `fts.drawings.v1.${SYM}`;

// registry: slot → items[{id,name,overlayType}]، از خودِ سورسِ رابط
function registry() {
  const src = fs.readFileSync(TOOLBAR, 'utf8');
  const start = src.indexOf('const toolSlots: ToolSlot[] = [');
  const body = src.slice(start, src.indexOf('\n  ];', start));
  const slots = [];
  // بلوک‌ها به‌ازای هر `slotId:` بریده می‌شوند: ساختارِ `items` درِ این فایل یکسان
  // نیست (سطرِ پایانیِ آرایه بی‌کاما) و رگولارِ چندلایه همین را از دست می‌دهد.
  const at = [...body.matchAll(/slotId: '([a-zA-Z]+)'/g)];
  for (let k = 0; k < at.length; k++) {
    const from = at[k].index;
    const to = k + 1 < at.length ? at[k + 1].index : body.length;
    const block = body.slice(from, to);
    const nm = /name: '([^']+)'/.exec(block);
    const items = [];
    const iRx = /id: '([^']+)', name: '([^']+)', overlayType: '([^']+)'/g;
    let i;
    // دو `id` درِ registry با دو نامِ متفاوت تکرار شده‌اند ⇒ کلید، جفتِ (slot,id) است
    // تا هیچِ ابزاری از ۲۹ شناسه زیرِ شمارشِ نودِ ۲۷تایی پنهان بماند.
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

// ground-truth: انبارِ ترسیم + شمارِ اورلی‌هایِ هم‌گروه درِ موتور (هماهنگیِ وضعیت)
const STATE = `(() => {
  const c = window.__borsChart;
  if (!c) return { error: 'NO_CHART' };
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(${JSON.stringify(KEY)}) || '[]') || []; } catch (e) {}
  const all = (c.getOverlays && c.getOverlays()) || [];
  const grp = all.filter(o => o.groupId === 'fts-draw').length;
  const pane = c.getSize('candle_pane', 'main');
  return {
    saved: saved.map(o => ({ id: o.id || null, name: o.name, group: o.groupId || null,
                             lock: o.lock === true, n: (o.points || []).length,
                             pts: (o.points || []).map(p => ({ t: p.timestamp, v: p.value == null ? null : Math.round(p.value * 100) / 100 })) })),
    savedCount: saved.length, engineDrawGroup: grp, engineTotal: all.length,
    ownGroup: (() => {
      // دیدۀِ زندۀ موتور از رسم‌هایِ گروهِ خودیِ ما: ردیفِ localStorage گاهیِ ناقص است
      // (سنجش: id=null و n=1 برایِ یکِ segmentِ دونقطه‌ای)، پس ویرایش با این سنجیده می‌شود.
      const g = all.filter(o => o.groupId === 'fts-draw');
      return g.map(o => ({ id: o.id, name: o.name,
        pts: (o.points || []).map(q => ({ t: q.timestamp ?? null, v: q.value == null ? null : Math.round(q.value * 100) / 100, i: q.dataIndex ?? null })) }));
    })(),
    visibilityTitle: (() => { const e = document.querySelector('.nn-left-toolbar [title^="ترسیم‌ها"]');
                             return e ? e.getAttribute('title') : null; })(),
    lockTitle: (() => { const e = document.querySelector('.nn-left-toolbar [title^="قفل ترسیم"]');
                        return e ? e.getAttribute('title') : null; })(),
    pane: { left: Math.round(pane.left), top: Math.round(pane.top),
            w: Math.round(pane.width), h: Math.round(pane.height) },
    canvas: (() => { const r = document.querySelector('canvas').getBoundingClientRect();
                     return { x: Math.round(r.left), y: Math.round(r.top) }; })(),
  };
})()`;

const ids = (st) => st.saved.map((o) => o.id || `${o.name}:${JSON.stringify(o.pts)}`);
const SPOTS = [[0.20, 0.30], [0.34, 0.55], [0.50, 0.34], [0.66, 0.58], [0.80, 0.42]];

(async () => {
  const slots = registry();
  const tools = [];
  for (const s of slots) for (const it of s.items) tools.push({ ...it, slotId: s.slotId, slotName: s.slotName });
  const rep = { ranAt: new Date().toISOString(), symbol: SYM, viewport: [1366, 768],
                storageKey: KEY, registrySlots: slots.length, registryTools: tools.length,
                tools: {}, summary: {} };

  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(os.tmpdir(), 'bors-m3-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  let autoAccept = false;                   // فقط برایِ شاخۀِ «تأییدِ حذفِ تمام»
  const page = ctx.pages()[0] || await ctx.newPage();
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

  let st = await page.evaluate(STATE);
  rep.baseline = { savedCount: st.savedCount, engineDrawGroup: st.engineDrawGroup,
                   engineTotal: st.engineTotal, visibilityTitle: st.visibilityTitle,
                   lockTitle: st.lockTitle };
  const pane = st.pane;

  // ── کنترلِ مثبت: خط روند باید درِ انبارِ خودی ردیف بسازد ─────────────────
  const CONTROL = 'trendLine';
  const ctrl = await (async () => {
    await page.locator(`.nn-left-toolbar .tool-item[title="خط روند"]`).first().click({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(500);
    const n0 = (await page.evaluate(STATE)).savedCount;
    for (const [fx, fy] of SPOTS.slice(0, 2)) {
      await page.mouse.click(pane.left + Math.round(pane.w * fx), pane.top + Math.round(pane.h * fy));
      await page.waitForTimeout(700);
    }
    const s1 = await page.evaluate(STATE);
    return { before: n0, after: s1.savedCount, drew: s1.savedCount > n0 };
  })();
  rep.positiveControl = { toolId: CONTROL, ...ctrl };
  if (!ctrl.drew) {
    console.error('CONTROL FAILED: «خط روند» ردیفی درِ انبارِ ترسیم نساخت — سنسور کور است؛ ' +
                  'هیچ نتیجۀِ دیگری گزارش نمی‌شود.');
    fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
    await ctx.close();
    process.exit(3);
  }

  // هرِ ابزار رویِ بومِ تمیز سنجیده می‌شود: گروهِ ترسیمِ **خودیِ همین هارنس**
  // (`fts-draw`) پاک می‌شود. این ترسیم‌هایِ کاربر نیستند — پروفایلِ اجرا موقتِ هرِ
  // دور است و خطِ مبنایِ آن صفر بود؛ رسمِ از‌پیش‌موجودِ نماد هرگز حذف نمی‌شود
  // (حکمِ مالک). بی‌این پاکسازی، رسمِ مانده از ابزارِ پیشین زیرِ کلیک‌هایِ بعدی
  // می‌آید و «رسم نکرد» گزارش می‌شود (سنجشِ trendLine: ۵ کلیک، صفرِ ردیف).
  const waitSaved0 = async (cmp, limitMs) => {
    const t0 = Date.now();
    let last = await page.evaluate(STATE);
    while (Date.now() - t0 < limitMs) {
      if (cmp(last)) return last;
      await page.waitForTimeout(500);
      last = await page.evaluate(STATE);
    }
    return last;
  };
  const resetOwn = async () => {
    await page.keyboard.press('Escape').catch(() => {});
    await page.evaluate(`(() => {
      try { window.__borsChart.removeOverlay({ groupId: 'fts-draw' }); } catch (e) {}
      try { localStorage.removeItem(${JSON.stringify(KEY)}); } catch (e) {}
    })()`);
    await page.waitForTimeout(600);
    // صفرشدنِ کلیدِ localStorage شرط نیست (نوشتۀِ debounce‌شدۀِ پیشین می‌تواند پس ازِ
    // removeItem دوباره بنشیند) — آنچه باید تمیز شود دیدِ موتور است؛ تشخیصِ رسم با
    // تفاوتِ مجموعه‌ها ساخته می‌شود، نه با شمارشِ مطلق.
    const clean = await waitSaved0((x) => x.ownGroup.length === 0, 5000);
    return clean;
  };
  await resetOwn();

  // ماندگاریِ ترسیم درِ محصول با تأخیر است (debounce): درِ اجرایِ ۱۴۰-۰۷-۲۷ ردیفِ
  // trendLine چندِ گام **پس از** حلقۀِ کلیک درِ localStorage ظاهر شد. بی‌صبر
  // شماریدن یعنی «رسم نکرد»ِ دروغین. این تابع تا مهلت، وضعِ انبار را تعقیب می‌کند.
  const waitSaved = async (cmp, limitMs = 9000) => {
    const t0 = Date.now();
    let last = await page.evaluate(STATE);
    while (Date.now() - t0 < limitMs) {
      if (cmp(last)) return last;
      await page.waitForTimeout(600);
      last = await page.evaluate(STATE);
    }
    return last;
  };

  const wanted = tools.filter((t) => !ONLY || t.id === ONLY || t.name === ONLY);
  for (const t of wanted) {
    await resetOwn();
    const rec = { name: t.name, overlayType: t.overlayType, slotId: t.slotId,
                  reachable: false, drew: false };
    // ۱) دسترسی: پیش‌فرضِ شیار با یکِ کلیک، فرزند با بازشدنِ فلایاوت
    await page.keyboard.press('Escape').catch(() => {});
    await page.mouse.move(600, 28).catch(() => {});
    await page.waitForTimeout(250);
    const isActive = () => page.evaluate(`(() => {
      const a = document.querySelector('.nn-left-toolbar .tool-item.active');
      const f = document.querySelector('.tv-flyout-item.active');
      return { rail: a ? a.getAttribute('title') : null, flyout: f ? (f.textContent||'').trim() : null };
    })()`);
    const railTitles = () => page.evaluate(`(() => [...document.querySelectorAll(
        '.nn-left-toolbar .tv-slot-wrapper .tool-item')].map(e => (e.getAttribute('title')||'').trim()))()`);
    const railEl = page.locator(`.nn-left-toolbar .tool-item[title="${t.name}"]`).first();
    if (await railEl.count().catch(() => 0)) {
      await railEl.click({ timeout: 4000 }).catch(() => {});
      await page.waitForTimeout(400);
      // ابزارِ از‌پیش‌فعال با یکِ کلیکِ دیگر خاموش می‌شود (کرکرۀِ toggle) — اگر
      // فعال نبود، دوباره کلیک می‌شود؛ بی‌این، «رسم نکرد»ِ TrendLine درِ اجرایِ
      // تنهایی فقط به‌خاطرِ این بود که کنترلِ مثبت همان ابزار را فعال کرده بود.
      let a = await isActive();
      if (a.rail !== t.name) {
        await railEl.click({ timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(400);
        a = await isActive();
      }
      rec.activeAfterSelect = (await railTitles()).includes(t.name);
      rec.reachable = true; rec.via = 'rail';
    } else {
      const arrows = await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').count();
      for (let i = 0; i < arrows && !rec.reachable; i++) {
        await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i)
          .click({ timeout: 4000 }).catch(() => {});
        await page.waitForTimeout(550);
        const child = page.locator('.tv-flyout-item', { hasText: t.name }).first();
        if (await child.count().catch(() => 0)) {
          await child.click({ timeout: 4000 }).catch(() => {});
          await page.waitForTimeout(400);
          // نشانهٔ واقعیِ انتخاب درِ خودِ رابط است، نه کلاسِ .active: شیار، نامِ
          // ابزارِ برگزیده را درِ titleِ خودش می‌گذارد. بی‌این، «خط افقی» و ۲۱ ابزارِ
          // فلایاوتی «رسم نکرد» گزارش شدند چون کلیکِ دومِ من فلایاوت را بست.
          for (let tries = 0; tries < 4 && !(await railTitles()).includes(t.name); tries++) {
            await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').nth(i)
              .click({ timeout: 4000 }).catch(() => {});
            await page.waitForTimeout(500);
            await page.locator('.tv-flyout-item', { hasText: t.name }).first()
              .click({ timeout: 4000 }).catch(() => {});
            await page.waitForTimeout(500);
          }
          rec.activeAfterSelect = (await railTitles()).includes(t.name);
          rec.reachable = true; rec.via = `flyout:${i}`;
        } else {
          await page.keyboard.press('Escape').catch(() => {});
          await page.waitForTimeout(200);
        }
      }
    }
    await page.waitForTimeout(450);
    if (!rec.reachable) { rep.tools[`${t.slotId}:${t.id}:${t.name}`] = rec; continue; }

    // ۲) رسم: تشخیص با **تفاوتِ مجموعه‌ها**، نه شمارشِ مطلق — ماندگاریِ debounce‌شدۀِ
    // ابزارِ پیشین می‌تواند پس ازِ پاکسازی دوباره بنشیند (سنجش: n0=1 با آن‌که
    // کلید را پاک کرده بودم) و آنگاه «رسم نکرد»ِ دروغین می‌سازد.
    const before0 = await page.evaluate(STATE);
    const ids0 = new Set((before0.ownGroup || []).map((o) => o.id));
    const sig0 = new Set((before0.saved || []).map((o) => `${o.name}:${JSON.stringify(o.pts)}`));
    rec.n0 = before0.savedCount;
    rec.engineOwn0 = ids0.size;
    let clicks = 0;
    for (const [fx, fy] of SPOTS) {
      await page.mouse.click(pane.left + Math.round(pane.w * fx), pane.top + Math.round(pane.h * fy));
      clicks++;
      await page.waitForTimeout(650);
      const s1 = await waitSaved((x) => (x.saved || []).some((o) =>
        !sig0.has(`${o.name}:${JSON.stringify(o.pts)}`)), 3500);
      if (s1.saved.some((o) => !sig0.has(`${o.name}:${JSON.stringify(o.pts)}`))) { rec.drew = true; break; }
    }
    rec.clicks = clicks;
    const s2 = await waitSaved((x) => (x.saved || []).some((o) =>
      !sig0.has(`${o.name}:${JSON.stringify(o.pts)}`)), 9000);
    const newSaved = (s2.saved || []).filter((o) => !sig0.has(`${o.name}:${JSON.stringify(o.pts)}`));
    const newEngine = (s2.ownGroup || []).filter((o) => !ids0.has(o.id));
    rec.savedAfterDraw = s2.savedCount;
    rec.newSaved = newSaved.length;
    rec.newEngine = newEngine.map((o) => ({ id: o.id, name: o.name, n: (o.pts || []).length }));
    rec.drew = newSaved.length > 0;
    if (!rec.drew && newEngine.length) rec.drewInEngineOnly = true;
    const newRows = newSaved;
    rec.stored = newRows.length ? newRows[newRows.length - 1] : null;
    rec.storedAdded = newRows.length;
    if (!rec.drew || !rec.stored) {
      rec.deadReason = !rec.activeAfterSelect ? 'tool not activated by the UI path tried'
        : (rec.drewInEngineOnly ? 'engine drew, nothing persisted' : 'no drawing after 5 clicks');
      rep.tools[`${t.slotId}:${t.id}:${t.name}`] = rec; continue;
    }
    const rowId = rec.stored.id || rec.stored.name;
    const own0 = s2.ownGroup[s2.ownGroup.length - 1] || null;
    const anchorOwn = own0 ? JSON.stringify(own0.pts) : null;
    const anchorPts = JSON.stringify(rec.stored.pts);
    rec.anchorOwn = own0 ? own0.pts : null;
    rec.anchorOwnId = own0 ? own0.id : null;

    // ۳) هماهنگیِ وضعیتِ موتور با ترسیمِ قابل‌مشاهده
    rec.engineCoherent = s2.engineDrawGroup >= s2.savedCount
      || s2.engineTotal >= s2.savedCount;
    rec.engineAtDraw = { drawGroup: s2.engineDrawGroup, total: s2.engineTotal, saved: s2.savedCount };

    // ۴) ویرایش: درگِ نقطۀِ اول (ابزارِ انتخاب + پیکسلِ واقعیِ همان نقطه)
    const px = await page.evaluate(`(() => {
      const c = window.__borsChart;
      const p = ${JSON.stringify((rec.stored.pts || [])[0] || {})};
      if (!p.t) return null;
      try {
        const r = c.convertToPixel([{ timestamp: p.t, value: p.v }], { paneId: 'candle_pane' });
        const q = Array.isArray(r) ? r[0] : r;
        if (!q || !Number.isFinite(q.x)) return null;
        const b = document.querySelector('canvas').getBoundingClientRect();
        return { x: Math.round(b.left + q.x), y: Math.round(b.top + q.y) };
      } catch (e) { return null; }
    })()`);
    rec.editPixel = px;
    if (px) {
      await page.locator('.nn-left-toolbar .tool-item[title="پیکان انتخاب"]').first()
        .click({ timeout: 3000 }).catch(async () => {
          await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').first().click({ timeout: 3000 }).catch(() => {});
          await page.waitForTimeout(450);
          await page.locator('.tv-flyout-item', { hasText: 'پیکان انتخاب' }).first().click({ timeout: 3000 }).catch(() => {});
        });
      await page.waitForTimeout(500);
      await page.mouse.move(px.x, px.y);
      await page.mouse.down();
      await page.mouse.move(px.x + 46, px.y + 30, { steps: 8 });
      await page.mouse.up();
      await page.waitForTimeout(1100);
      const s3 = await waitSaved((x) => {
        const q = x.ownGroup.find((o) => o.id === rec.anchorOwnId) || x.ownGroup[x.ownGroup.length - 1];
        return !!q && anchorOwn && JSON.stringify(q.pts) !== anchorOwn;
      }, 7000);
      const q3 = s3.ownGroup.find((o) => o.id === rec.anchorOwnId) || s3.ownGroup[s3.ownGroup.length - 1];
      const row3 = s3.saved.find((o) => o.id === rowId) || s3.saved[s3.saved.length - 1];
      rec.editChangedEngine = !!q3 && !!anchorOwn && JSON.stringify(q3.pts) !== anchorOwn;
      rec.editChangedStored = !!row3 && JSON.stringify(row3.pts) !== anchorPts;
      rec.ptsAfterEditEngine = q3 ? q3.pts : null;
      rec.ptsAfterEdit = row3 ? row3.pts : null;
      rec.othersUntouchedByEdit = s3.savedCount === s2.savedCount;
      await page.keyboard.press('Escape').catch(() => {});
    }

    // ۵) مخفی‌سازی: کرکرۀِ «ترسیم‌ها: نمایان» باید وضعیت را عوض کند
    const vis0 = (await page.evaluate(STATE)).visibilityTitle;
    await page.locator('.nn-left-toolbar [title^="ترسیم‌ها"]').first().click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(800);
    const vis1 = (await page.evaluate(STATE)).visibilityTitle;
    rec.visibilityToggle = { before: vis0, after: vis1, changed: vis0 !== vis1 };
    await page.locator('.nn-left-toolbar [title^="ترسیم‌ها"]').first().click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(600);

    // ۶) حذفِ همین یکِ رسم، بدونِ اثر رویِ دیگر رسم‌هایِ خودی
    const before = await page.evaluate(STATE);
    const idsBefore = ids(before);
    let deleted = false;
    if (px) {
      await page.mouse.click(px.x, px.y);            // انتخابِ ترسیم
      await page.waitForTimeout(500);
      await page.keyboard.press('Delete').catch(() => {});
      await page.waitForTimeout(1100);
      const mid = await waitSaved((x) => x.savedCount < before.savedCount, 7000);
      deleted = mid.savedCount < before.savedCount;
      if (!deleted) {                                // شاخۀِ پاک‌کن
        await page.locator('.nn-left-toolbar [title="مشاهده زیرابزارها"]').first()
          .click({ timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(450);
        await page.locator('.tv-flyout-item', { hasText: 'پاک‌کن' }).first()
          .click({ timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(400);
        await page.mouse.click(px.x, px.y);
        await page.waitForTimeout(1100);
        const mid2 = await waitSaved((x) => x.savedCount < before.savedCount, 7000);
        deleted = mid2.savedCount < before.savedCount;
      }
    }
    const afterDel = await page.evaluate(STATE);
    rec.deleteOne = { tried: !!px, removed: deleted,
                      beforeCount: before.savedCount, afterCount: afterDel.savedCount,
                      othersSurvived: idsAfter(idsBefore, afterDel).missing === 1
                        ? true : idsBefore.length - afterDel.savedCount === 1 };
    rep.tools[`${t.slotId}:${t.id}:${t.name}`] = rec;
  }

  // ── «حذف تمام ترسیم‌ها»: لغو، سپس تأیید ────────────────────────────────
  // شاخه‌هایِ حذفِ سراسری بی‌ «چیزی برایِ حذف» بی‌معنايند: یکِ رسمِ خودی تازه می‌سازیم.
  await resetOwn();
  await page.locator('.nn-left-toolbar .tool-item[title="خط روند"]').first().click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(400);
  await page.mouse.click(pane.left + Math.round(pane.w * 0.30), pane.top + Math.round(pane.h * 0.40));
  await page.waitForTimeout(600);
  await page.mouse.click(pane.left + Math.round(pane.w * 0.55), pane.top + Math.round(pane.h * 0.60));
  await waitSaved((x) => x.savedCount > 0 || x.ownGroup.length > 0, 8000);
  const sAll = await page.evaluate(STATE);
  await page.locator('.nn-left-toolbar [title="حذف تمام ترسیم‌ها"]').first()
    .click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(900);
  const sCancel = await page.evaluate(STATE);
  rep.deleteAllCancel = { beforeCancel: sAll.savedCount, afterCancel: sCancel.savedCount,
                          nothingRemoved: sCancel.savedCount === sAll.savedCount
                            && sCancel.ownGroup.length === sAll.ownGroup.length,
                          hadSomethingToRemove: sAll.savedCount + sAll.ownGroup.length > 0 };
  autoAccept = true;
  await page.locator('.nn-left-toolbar [title="حذف تمام ترسیم‌ها"]').first()
    .click({ timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(1400);
  const sAfter = await page.evaluate(STATE);
  rep.deleteAllAccept = { before: sCancel.savedCount, after: sAfter.savedCount,
                          engineDrawGroup: sAfter.engineDrawGroup,
                          cleared: sAfter.savedCount === 0 };
  autoAccept = false;

  const list = Object.entries(rep.tools);
  rep.summary = {
    deleteAllCancelHadTarget: rep.deleteAllCancel.hadSomethingToRemove,
    registryTools: tools.length, tested: list.length,
    reachable: list.filter(([, v]) => v.reachable).length,
    drew: list.filter(([, v]) => v.drew).length,
    persisted: list.filter(([, v]) => v.storedAdded > 0).length,
    editedEngine: list.filter(([, v]) => v.editChangedEngine).length,
    editedStored: list.filter(([, v]) => v.editChangedStored).length,
    storedRowsWithoutId: list.filter(([, v]) => v.stored && v.stored.id === null).length,
    visibilityToggled: list.filter(([, v]) => v.visibilityToggle && v.visibilityToggle.changed).length,
    deletedOne: list.filter(([, v]) => v.deleteOne && v.deleteOne.removed).length,
    isolatedDelete: list.filter(([, v]) => v.deleteOne && v.deleteOne.othersSurvived).length,
    engineCoherent: list.filter(([, v]) => v.engineCoherent).length,
    dead: list.filter(([, v]) => v.reachable && !v.drew).map(([k]) => k),
    unreachable: list.filter(([, v]) => !v.reachable).map(([k]) => k),
    deleteAll: { hadTarget: !!rep.deleteAllCancel.hadSomethingToRemove,
                 cancelHeld: rep.deleteAllCancel.nothingRemoved,
                 acceptCleared: rep.deleteAllAccept.cleared },
  };
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  const s = rep.summary;
  console.log(`registry=${s.registryTools} tested=${s.tested} reachable=${s.reachable} ` +
              `drew=${s.drew} persisted=${s.persisted}`);
  console.log(`edited(engine)=${s.editedEngine} edited(store)=${s.editedStored} storedRowsWithoutId=${s.storedRowsWithoutId} visibility=${s.visibilityToggled} deleteOne=${s.deletedOne} ` +
              `isolated=${s.isolatedDelete} engineCoherent=${s.engineCoherent}`);
  console.log(`deleteAll: cancel holds=${s.deleteAll.cancelHeld} accept clears=${s.deleteAll.acceptCleared} ` +
              `(${rep.deleteAllAccept.before} → ${rep.deleteAllAccept.after})`);
  console.log('dead: ' + JSON.stringify(s.dead.map((k) => k + '(' +
              ((rep.tools[k] || {}).deadReason) + ')' )));
  console.log('unreachable: ' + JSON.stringify(s.unreachable));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });

function idsAfter(beforeList, st) {
  const now = ids(st);
  const missing = beforeList.filter((i) => !now.includes(i)).length;
  return { missing };
}
