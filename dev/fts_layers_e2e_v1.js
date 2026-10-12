// dev/fts_layers_e2e_v1.js — E2Eِ زندهٔ لایه‌های FTS رویِ مرورگرِ واقعی (مرحلۀ ۱۱)
//
// چرا این فایل درِ `dev/run_all_tests.py` نیست: سوئیت‌هایِ آن باید آفلاین بدوند و
// سرورِ dev بسته باشد (AGENTS.md §گیت‌ها). این اسکریپت عمداً *برعکس* است — به
// بک‌اندِ زنده (127.0.0.1:8001) و vite (5173) نیاز دارد و همان چیزی را می‌سنجد که
// vitest نمی‌تواند: رندرِ واقعیِ چارت، داکِ «لایه‌های FTS»، سوییچِ زنده، کارتِ
// شواهد درِ هر دو موتور (klinecharts ⇄ FFC)، و لایۀ بی‌رأیِ موتورِ سوم
// (`/api/structure3` → گروهِ `fts-e3`) که پیش‌فرض خاموش است و همین‌جا روشن می‌شود.
//
// اجرا:
//   python -m uvicorn app:app --port 8001        # ترمینالِ ۱
//   cd frontend && npm run dev                   # ترمینالِ ۲
//   node dev/fts_layers_e2e_v1.js --symbol فولاد  # ترمینالِ ۳
//
// خروجی: `_audit/fts_layers_e2e.json` + اسکرین‌شاتِ هر موتور + پیش/پسِ بومِ
// لایۀ موتورِ سوم (`e3_<engine>_canvas_off.png` / `_on.png`). بی‌سرور، صریحاً
// FAIL می‌شود — «رد شدنِ بی‌خبر» نداریم.
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const { chromium } = require(path.join(ROOT, 'frontend', 'node_modules', 'playwright-core'));

const argv = process.argv.slice(2);
const arg = (name, dflt) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};
const BASE = arg('base', 'http://localhost:5173');   // vite ۵ روی ::1 می‌نشیند؛ 127.0.0.1 پاسخ نمی‌دهد
const SYMBOL = arg('symbol', 'فولاد');
const OUT_DIR = path.join(ROOT, '_audit');
const CONFIG_KEY = 'fts.chart.settings.v1';
const PREFS_KEY = 'fts-pattern-prefs';

const FAILS = [];
const FACTS = {};
const ck = (label, cond, extra) => {
  console.log((cond ? '  ok   ' : '  FAIL ') + label + (extra ? `  [${extra}]` : ''));
  if (!cond) FAILS.push(label);
};

const BROWSERS = [
  process.env.BORS_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

async function loginThroughUI(page) {
  // درگاهِ محلیِ خودِ برنامه (authStore.ts: DEFAULT_USER/DEFAULT_PASS درِ مخزن‌اند) —
  // از راهِ فرمِ واقعی وارد می‌شویم، نه با ساختنِ سشن درِ localStorage.
  const user = arg('user', 'admin');
  const pass = arg('pass', 'bors123');
  const passBox = await page.$('input[type="password"]');
  if (!passBox) return;                        // سشن باز است
  await page.fill('input[type="text"]', user);
  await passBox.fill(pass);
  await page.click('button[type="submit"]');
  await page.waitForSelector('input[type="password"]', { state: 'detached', timeout: 25000 });
}

async function openLayersTab(page) {
  // تبِ داک هم «باز کردن» و هم «انتخاب» را در یک کلیک می‌کند (FtsDock.tsx:39-44)
  const tab = await page.$('[data-testid="fts-dock-tab-layers"]');
  if (tab) await tab.click();
  else await page.getByText('لایه‌های FTS', { exact: true }).first().click({ timeout: 15000 });
  await page.waitForSelector('[data-testid="fts-layer-panel"]', { timeout: 15000 });
}

async function waitForFeed(page, engineId) {
  // میزبانِ چارت بی‌داده هم mount می‌شود؛ پس صبر می‌کنیم تا واقعاً خوراک برسد:
  // بومِ چارت + دست‌کم یک لایۀ «فعال» در پنل. بی‌این، سنجشِ اولِ پنل همه را
  // «منتشر نشده» می‌بیند و آن را به پایِ منطق می‌گذارد — در حالی که فقط زود آمده‌ایم.
  const t0 = Date.now();
  await page.waitForSelector(`[data-testid="${engineId === 'ffc' ? 'ffc-chart-host' : 'nn-chart-host'}"] canvas`,
    { timeout: 60000 });
  await page.waitForFunction(() => {
    const els = Array.from(document.querySelectorAll('[data-testid^="fts-layer-state-"]'));
    return els.some((e) => e.textContent.trim() === 'فعال');
  }, null, { timeout: 60000 }).catch(() => { /* بی‌پنلِ باز: خودِ ck بعدی می‌گوید */ });
  // شمارِ «فعال» کافی نیست: `corp-actions` از feedِ رویدادهایِ تعدیل می‌آید و
  // زودتر از `/api/fts` روشن می‌شود، پس درِ کشِ سردِ موتورِ اول پنل هنوز
  // «اعلام نشده» است. خطِ تازگی پر می‌شود ⇔ تحلیلِ FTS رسیده؛ منتظرِ همان می‌مانیم
  // تا «زود آمدنِ سنجش» به پایِ منطقِ لایه‌ها نوشته نشود.
  await page.waitForFunction(() => {
    const e = document.querySelector('[data-testid="fts-layer-freshness"]');
    return !!e && /کندل[^\d۰-۹]*[۰-۹0-9]/.test(e.textContent) && !/اعلام نشده/.test(e.textContent);
  }, null, { timeout: 90000 }).catch(() => { /* نرسید: ckِ تازگی صادقاً FAIL می‌گوید */ });
  return Date.now() - t0;
}

async function probe(page, engineId, hostSel) {
  const rows = await page.$$eval('[data-testid^="fts-layer-row-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-layer-row-', '')),
  );
  FACTS[engineId + '_rows'] = rows.length;
  ck(`${engineId}: پنلِ کاتالوگ دست‌کم ۱۵ لایه دارد`, rows.length >= 15, `${rows.length} سطر`);

  const states = await page.$$eval('[data-testid^="fts-layer-state-"]', (els) =>
    els.map((e) => [e.getAttribute('data-testid').replace('fts-layer-state-', ''), e.textContent.trim()]),
  );
  FACTS[engineId + '_states'] = Object.fromEntries(states);
  const active = states.filter(([, s]) => s === 'فعال').map(([id]) => id);
  ck(`${engineId}: دست‌کم یک لایه رویِ دادهٔ زنده «فعال» است`, active.length >= 1, active.join(','));

  const fresh = await page.textContent('[data-testid="fts-layer-freshness"]');
  FACTS[engineId + '_freshness'] = fresh;
  // «اعلام نشده» هم /کندل/ را پاس می‌کند؛ پس عددِ واقعیِ کندل خواسته می‌شود، نه هر متنِ آشیانه
  ck(`${engineId}: خطِ تازگی شمارِ کندلِ واقعی را می‌گوید`,
    /کندل[^\d۰-۹]*[۰-۹0-9]/.test(fresh || '') && !/اعلام نشده/.test(fresh || ''), fresh);

  // سوییچِ زنده: لایۀ ساختار خاموش/روشن می‌شود و درِ localStorage می‌نشیند
  const box = await page.$('[data-testid="fts-layer-toggle-structure-points"]');
  ck(`${engineId}: سوییچِ «نقاطِ ساختاری» قابلِ کلیک است`, !!box);
  if (box) {
    const readPref = async () => {
      const raw = JSON.parse((await page.evaluate((k) => localStorage.getItem(k), PREFS_KEY)) || '{}');
      return raw && raw.structure ? raw.structure.enabled : undefined;
    };
    const was = await readPref();   // بی‌ترجیحِ ذخیره‌شده = پیش‌فرضِ true
    await box.click();
    const off = await readPref();
    ck(`${engineId}: ترجیحِ کاربر درِ localStorage ثبت شد (خاموش)`, off === false, String(off));
    await box.click();
    const on = await readPref();
    ck(`${engineId}: سوییچ دوطرفه است و به وضعیتِ پیش از آزمایش برمی‌گردد`,
      on === (was === undefined ? true : was), String(on));
  }

  // کارتِ شواهد: قاعده → الگوریتم → انوتیشن، با دهانۀ payload و دو زمان
  const evBtn = await page.$('[data-testid="fts-layer-evidence-btn-structure-points"]');
  ck(`${engineId}: دکمهٔ «شواهد» برایِ لایۀ ساختار هست`, !!evBtn);
  if (evBtn) {
    await evBtn.click();
    await page.waitForSelector('[data-testid="fts-layer-evidence"]', { timeout: 8000 });
    const rule = await page.textContent('[data-testid="fts-evidence-rule"]');
    const src = await page.textContent('[data-testid="fts-evidence-source"]');
    const times = await page.textContent('[data-testid="fts-evidence-times"]');
    FACTS[engineId + '_evidence'] = { rule, src, times };
    ck(`${engineId}: کارتِ شواهد به سندِ قواعد ارجاع می‌دهد`,
      /FTS-RULE-ALGORITHM-MAP/.test(rule || ''), (rule || '').slice(0, 90));
    ck(`${engineId}: کارتِ شواهد دهانۀ payload را نام می‌برد`,
      /structure_points/.test(src || ''), (src || '').slice(0, 90));
    ck(`${engineId}: کارتِ شواهد دو زمان را جدا می‌نویسد`,
      /رخ داد/.test(times || '') && /فهمیدیم/.test(times || ''), (times || '').slice(0, 120));
  }

  // ب-۱ درِ مرورگر: پیوتِ هفتگی سوییچِ مستقل ندارد (`structure` هر دو TF را با هم
  // خاموش/روشن می‌کند)، پس تفاوتِ بوم به «هفتگی» قابلِ انتساب نیست و آن را ادعا
  // نمی‌کنیم. درِ عوض، شمارِ هفتگی از کارتِ شواهد خوانده می‌شود: صفرنبودِ دادۀ
  // واقعیِ سرور، نه عددِ ساختگیِ فرانت.
  const wBtn = await page.$('[data-testid="fts-layer-evidence-btn-structure-points-weekly"]');
  ck(`${engineId}: دکمهٔ «شواهد» برایِ پیوتِ ساختارِ هفتگی هست`, !!wBtn);
  if (wBtn) {
    await wBtn.click();
    await page.waitForSelector('[data-testid="fts-layer-evidence"]', { timeout: 8000 });
    const wf = await page.$$eval('[data-testid="fts-layer-evidence"] dl > div', (els) =>
      els.map((e) => [((e.querySelector('dt') || {}).textContent || ''),
                      ((e.querySelector('dd') || {}).textContent || '')])).catch(() => []);
    FACTS[engineId + '_weekly_facts'] = Object.fromEntries(wf.map(([a, b]) => [a.trim(), b.trim()]));
    const cnt = ((wf.find(([a]) => a.includes('پیوت')) || ['', ''])[1] || '').trim();
    ck(`${engineId}: کارتِ شواهدِ هفتگی شمارِ واقعیِ پیوت را می‌گوید`,
      /[1-9۱-۹]/.test(cnt), cnt);
    const wsrc = await page.textContent('[data-testid="fts-evidence-source"]');
    ck(`${engineId}: کارتِ شواهدِ هفتگی دهانۀ structure_points.W را نام می‌برد`,
      /structure_points\.W/.test(wsrc || ''), (wsrc || '').slice(0, 90));
  }

  const legend = await page.$$eval('[data-testid^="fts-legend-item-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-legend-item-', '')),
  ).catch(() => []);
  FACTS[engineId + '_legend'] = legend;
  ck(`${engineId}: افسانۀ چارت از همان رجیستری پر می‌شود`, legend.length >= 1, legend.join(','));

  // ب-۳ درِ مرورگر: سطرِ کاتالوگ، سطرِ افسانه و «فعال» بودن هیچ‌کدام ثابت نمی‌کنند
  // پیکسل رویِ بوم می‌آید («کلیکِ دکمه ≠ آزمون»). سوییچِ اختصاصیِ جعبۀ رنج را
  // خاموش/روشن می‌کنیم و تصویرِ بوم را می‌سنجیم؛ کنترلِ بی‌تحركی مثلِ probeE3،
  // وگرنه «تفاوت» بی‌معناست. دو کلیک، وضعیتِ پیش از آزمایش را برمی‌گرداند.
  // «بوم» تک‌بوم نیست: klinecharts v10 هر پنل را رویِ یک canvas می‌کشد (و FFC شش بوم
  // دارد)، پس مقایسۀ فقطِ اولی می‌تواند یک رسمِ واقعی را «بی‌تغییر» نشان دهد. همهٔ
  // بوم‌های میزبان سنجیده می‌شوند و شمارهٔ بومِ تغییریافته درِ FACTS می‌نشیند.
  const shots = async () => {
    const els = await page.$$(`${hostSel} canvas`);
    const bufs = [];
    for (const el of els) bufs.push(await el.screenshot());
    return bufs;
  };
  const cmp = (a, b) => a.map((buf, i) => (buf && b[i] ? Buffer.compare(buf, b[i]) !== 0 : null));
  // دو ادعا جدا می‌شوند: (الف) سوییچ به *نگاشتِ لایه‌ها* می‌رسد — شمارِ «لایهٔ FTS»
  // درِ پنلِ موتورِ دوم کم و زیاد می‌شود؛ (ب) آن لایه رویِ *بوم* هم دیده می‌شود.
  // بی‌(الف) می‌توان پیکسل را با یک ریدرِ تصادفی عوض دید و بی‌(ب) شمارِ لایه فقط
  // حرفِ کد است؛ مرحلۀ ۶ هر دو را می‌خواهد. درِ چارتِ کهنه این خط نیست ⇒ NOTE.
  const layerCount = async () => {
    const t = await page.$eval('[data-testid="fts-engine-layer-count"]',
      (e) => e.textContent).catch(() => null);
    if (!t) return null;
    const latin = t.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)));
    const m = latin.match(/(\d+)/);
    return m ? Number(m[1]) : null;
  };

  const boxBtn = await page.$('[data-testid="fts-layer-toggle-range-box"]');
  ck(`${engineId}: سوییچِ اختصاصیِ «جعبۀ رنج» درِ پنل هست`, !!boxBtn);
  if (boxBtn) {
    const nBefore = await layerCount();
    const idle1 = await shots();
    const idle2 = await shots();
    const animates = cmp(idle1, idle2).some((x) => x === true);
    FACTS[engineId + '_box_canvas_animates'] = animates;
    FACTS[engineId + '_box_canvas_count'] = idle1.length;
    await boxBtn.click();
    await page.waitForTimeout(1200);
    const nOff = await layerCount();
    const off = await shots();
    await boxBtn.click();
    await page.waitForTimeout(1200);
    const nOn = await layerCount();
    const on = await shots();
    const diff = cmp(off, on);
    FACTS[engineId + '_box_layer_count'] = { before: nBefore, off: nOff, on: nOn };
    if (nBefore == null) {
      console.log(`  NOTE ${engineId}: شمارِ لایه درِ این میزبان منتشر نمی‌شود (چارتِ کهنه)؛ ادعۀ «سوییچ به نگاشت رسید» اینجا سنجیده نمی‌شود`);
    } else {
      ck(`${engineId}: خاموش‌کردنِ جعبۀ رنج یک لایه از نگاشت کم می‌کند و روشن‌کردن پس می‌دهد (Prefs → لایه)`,
        nOff === nBefore - 1 && nOn === nBefore, `${nBefore} → ${nOff} → ${nOn}`);
    }
    FACTS[engineId + '_box_canvas_bytes'] = {
      canvases: off.length,
      off: off.map((b) => b && b.length), on: on.map((b) => b && b.length),
      changed_indexes: diff.map((c, i) => (c ? i : -1)).filter((i) => i >= 0), animates,
    };
    const changed = diff.some((x) => x === true);
    if (animates) {
      console.log(`  NOTE ${engineId}: بوم در وضعیتِ بی‌تحرك هم فرق می‌کند؛ مقایسۀ جعبۀ رنج گویا نیست`);
    } else {
      ck(`${engineId}: خاموش/روشن‌کردنِ جعبۀ رنج بوم را عوض می‌کند (رسمِ واقعی، ب-۳)`,
        changed, `${off.length} بوم · تغییر: ${diff.map((c, i) => (c ? i : null)).filter((x) => x !== null).join(',') || 'هیچ‌کدام'}`);
      fs.mkdirSync(OUT_DIR, { recursive: true });
      // فقطِ بومِ نخستِ تغییریافته (یا صفر) ذخیره می‌شود تا جفتِ پیش/پس گم نشود
      const pick = diff.findIndex((c) => c === true);
      const idx = pick >= 0 ? pick : 0;
      if (off[idx]) fs.writeFileSync(path.join(OUT_DIR, `box_${engineId}_canvas${idx}_off.png`), off[idx]);
      if (on[idx]) fs.writeFileSync(path.join(OUT_DIR, `box_${engineId}_canvas${idx}_on.png`), on[idx]);
    }
    const boxState = await page.$eval('[data-testid="fts-layer-state-range-box"]',
      (e) => e.textContent.trim()).catch(() => '');
    ck(`${engineId}: بعد از دو کلیک، جعبۀ رنج به «فعال» برمی‌گردد`, boxState === 'فعال', boxState);
  }

  // ب-۸ درِ کلِ رجیستری: سنجشِ یک سوییچ ثابت نمی‌کند بقیه هم وصل‌اند. پنل برایِ هر سطر دو
  // ادعایِ ماشین‌خوان دارد: وضعیتِ داده («فعال» / «فعال نیست» / «منتشر نشده») و ستونِ
  // صداقتِ موتور (`K ✓/✗` و `F ✓/✗` = «امروز رویِ بوم می‌آید»). پس سوییچِ هر سطر یکی‌یکی زده
  // می‌شود و اثرش با دو سیگنال سنجیده می‌شود -- شمارِ لایه (نگاشت) و بایتِ بوم (پیکسل) -- و
  // با همان ادعا مقایسه می‌شود. دو رأیِ سخت بیرون می‌آید:
  //   ادعای «رسم می‌شود» + اثرِ صفر ⇒ رجیستر شده ولی رسم نمی‌شود (همان کلاسِ ب-۸) -- قرمز
  //   ادعای «رسم نمی‌شود» + اثرِ غیرصفر ⇒ ستونِ رجیستری خلافِ واقع می‌گوید -- قرمز
  // سطری سوییچِ مستقل ندارد (دکمه‌اش `disabled`: «همیشه با موتور می‌آید») یا قاعدۀ چرخیدۀ
  // همان موتور را ندارد، کلیک نمی‌شود و فقط درِ FACTS ثبت می‌گردد -- سبزِ الکی نیست.
  // سطرهایِ موتورِ سوم بیرونِ این حلقه‌اند: `probeE3` حالتِ اوّلیۀ «خاموش و بی‌کوئری» را
  // می‌سنجد و کلیکِ اینجا همان حالت را آلوده می‌کند (درِ همین دور آزموده شد).
  const claims = Object.fromEntries(await page.$$eval('[data-testid^="fts-layer-row-"]', (els) =>
    els.map((e) => [e.getAttribute('data-testid').replace('fts-layer-row-', ''),
      { k: /K ✓/.test(e.textContent || ''), f: /F ✓/.test(e.textContent || '') }])));
  const engineClaim = engineId === 'ffc' ? 'f' : 'k';
  const toggleIds = (await page.$$eval('[data-testid^="fts-layer-toggle-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-layer-toggle-', ''))))
    .filter((id) => !id.startsWith('e3-'));
  // سطرِ بی‌سوییچِ مستقل دکمه‌اش `disabled` است («همیشه با موتور می‌آید»)، و کلیک روی
  // دکمهٔ غیرفعال تایم‌اوتِ ۳۰ ثانیه‌ای می‌دهد؛ پس خوانده و ثبت می‌شود، نه کلیک.
  const disabledIds = await page.$$eval('[data-testid^="fts-layer-toggle-"][disabled]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-layer-toggle-', '')));
  const idleA = await shots();
  const idleB = await shots();
  const anim = cmp(idleA, idleB).some((x) => x === true);
  FACTS[engineId + '_sweep_canvas_count'] = idleA.length;
  FACTS[engineId + '_sweep_canvas_animates'] = anim;
  FACTS[engineId + '_sweep_no_own_switch'] = disabledIds;
  const base = await layerCount();
  const matrix = {};
  for (const id of toggleIds) {
    const state = (states.find(([k]) => k === id) || ['', ''])[1];
    const claim = claims[id] ? claims[id][engineClaim] : null;
    if (disabledIds.includes(id)) {
      matrix[id] = { state, claim, layer_delta: null, pixels: null, moved: null, restored: null, no_own_switch: true };
      continue;
    }
    const btn = await page.$(`[data-testid="fts-layer-toggle-${id}"]`);
    if (!btn) {
      matrix[id] = { state, claim, layer_delta: null, pixels: null, moved: null, restored: null, missing: true };
      continue;
    }
    await btn.click();
    await page.waitForTimeout(700);
    const nOff = await layerCount();
    const offShots = anim ? null : await shots();
    await btn.click();
    await page.waitForTimeout(700);
    const nOn = await layerCount();
    const onShots = anim ? null : await shots();
    // اثر درِ دو سیگنال جدا سنجیده می‌شود؛ هیچ‌کدام تنها کافی نیست:
    //   layer_delta ≠ 0 ⇒ سوییچ به نگاشتِ لایه رسید (Prefs → موتور)
    //   pixels > 0     ⇒ آن لایه رویِ بوم هم دیدنی شد
    // `moved` یعنی «کم‌اثر نبود» با هر یک از دو سیگنالِ قابل‌سنجش؛ پس میزبانی که شمارِ لایه
    // منتشر نمی‌کند (چارتِ کهنه) با بوم قضاوت می‌شود، و میزبانِ بی‌تحركِ گویا هر دو را دارد.
    const layerDelta = base != null && nOff != null ? base - nOff : null;
    const pixels = offShots && onShots ? cmp(offShots, onShots).filter((c) => c === true).length : null;
    matrix[id] = {
      state,
      claim,
      layer_delta: layerDelta,
      pixels,
      moved: layerDelta == null && pixels == null ? null : ((layerDelta ?? 0) !== 0 || (pixels ?? 0) > 0),
      restored: base == null || nOn == null ? null : nOn === base,
    };
  }
  FACTS[engineId + '_switch_matrix'] = matrix;

  // سطرهایِ سنجیده‌شدنی: سوییچِ مستقل دارند، ادعایِ موتورِ این میزبان را خوانده‌ایم، اثرش
  // قابل‌سنجش بود، و قاعدۀ خودشان «فعال» است. «فعال نیست» و «منتشر نشده» یعنی داده‌ای نیست
  // که رسم شود؛ صفر بودنِ اثرشان درِ آن حالت نقضِ ادعا نیست (وگرنه قرمزِ الکی می‌داد).
  const auditable = toggleIds.filter((id) => matrix[id] && !matrix[id].no_own_switch && !matrix[id].missing
    && matrix[id].claim != null && matrix[id].moved != null && matrix[id].state === 'فعال');
  const skipped = toggleIds.filter((id) => !auditable.includes(id));
  FACTS[engineId + '_sweep_skipped'] = skipped.map((id) => `${id}:${matrix[id]?.state ?? '?'}`);
  if (auditable.length === 0) {
    console.log(`  NOTE ${engineId}: هیچ سطرِ «فعالِ» سنجیدنی درِ این میزبان نبود (شمارِ لایه منتشر نمی‌شود${anim ? ' و بوم بی‌تحرك گویا نیست' : ''})؛ ماتریسِ «سوییچ → اثر» اینجا رأی نمی‌دهد`);
  } else {
    // ادعای «رسم می‌شود» + اثرِ صفر ⇒ رجیستر شده ولی رسم نمی‌شود (همان کلاسِ ب-۸)
    const over = auditable.filter((id) => matrix[id].claim === true && matrix[id].moved === false);
    // ادعای «رسم نمی‌شود» + اثرِ غیرصفر ⇒ ستونِ صداقتِ رجیستری خلافِ واقع می‌گوید
    const under = auditable.filter((id) => matrix[id].claim === false && matrix[id].moved === true);
    const claimTrue = auditable.filter((id) => matrix[id].claim === true);
    const claimFalse = auditable.filter((id) => matrix[id].claim === false);
    // هیچ‌کدام از این رأی‌ها رویِ فهرستِ خالی سبز نمی‌شوند (سبزِ الکی = ادعایِ آزمونِ اجراشده).
    if (claimTrue.length) {
      ck(`${engineId}: سطرهایِ «رسم می‌شود» درِ این موتور واقعاً سوییچ‌پذیرند (ب-۸)`,
        over.length === 0,
        `${claimTrue.length} سطرِ فعال با ادعایِ رسم · بی‌اثر: ${over.join(',') || 'هیچ'}`);
    } else {
      console.log(`  NOTE ${engineId}: سطرِ «فعالِ» با ادعایِ رسم که سوییچش سنجیدنی باشد نداشتیم؛ ادعایِ (الف) اینجا رأی ندارد`);
    }
    if (claimFalse.length) {
      ck(`${engineId}: سطرهایِ «رسم نمی‌شود» درِ این موتور بی‌اثرند (ستونِ K/F صادق است)`,
        under.length === 0,
        `${claimFalse.length} سطرِ فعال با ادعایِ عدمِ رسم · اثردار: ${under.join(',') || 'هیچ'}`);
    } else {
      console.log(`  NOTE ${engineId}: سطرِ «فعالِ» با ادعایِ «رسم نمی‌شود» که سوییچش سنجیدنی باشد نداشتیم؛ ادعایِ (ب) اینجا رأی ندارد`);
    }
    const turned = toggleIds.filter((id) => matrix[id]?.moved === true);
    ck(`${engineId}: سوییچ‌هایِ پنل درِ نگاشتِ لایه یا بوم بی‌اثر نیستند (ب-۸)`,
      turned.length >= 1,
      `${turned.length} سوییچ اثر داشت · ${base ?? 'بی‌شمار'} لایه · ${turned.join(',')}`);
    const restorable = toggleIds.filter((id) => matrix[id]?.restored != null);
    if (restorable.length) {
      ck(`${engineId}: هر سوییچ بعد از دو کلیک شمارِ لایه را دقیقاً برمی‌گرداند (بی‌نشتِ وضعیت)`,
        restorable.every((id) => matrix[id].restored === true),
        restorable.map((id) => `${id}:${matrix[id].restored}`).join(','));
    } else {
      console.log(`  NOTE ${engineId}: شمارِ لایه درِ این میزبان منتشر نمی‌شود؛ بازگشتِ شمار پس از دو کلیک اینجا سنجیده نمی‌شود (فقط اثرِ بوم)`);
    }
    // سطرِ «فعال نیست» که بومی را عوض می‌کند: قاعدۀ آن لایه امروز تأیید نشده ولی
    // چیزی رویِ بوم هست. درِ پولبک این تفاوتِ خودِ دو مسیرِ رسم است (کهنه خطِ سطح را
    // بی‌تأیید می‌کشد، موتورِ دوم نه) و finding شده، نه سبزِ الکی.
    const movedInactive = toggleIds.filter((id) => matrix[id] && !matrix[id].no_own_switch
      && matrix[id].state !== 'فعال' && matrix[id].moved === true);
    if (movedInactive.length) {
      console.log(`  NOTE ${engineId}: سطر(ها)ی «فعال نیست» ولی اثردار رویِ بوم (تأییدِ علت درِ گزارش): ${movedInactive.join(',')}`);
    }
    if (skipped.length) {
      console.log(`  NOTE ${engineId}: سطرهایی که درِ این دور رأی ندارند (بی‌سوییچِ مستقل / بی‌داده / بی‌ادعا): ${FACTS[engineId + '_sweep_skipped'].join(',')}`);
    }
    const noPixels = auditable.filter((id) => (matrix[id].layer_delta ?? 0) !== 0 && matrix[id].pixels === 0);
    if (anim) {
      console.log(`  NOTE ${engineId}: بوم درِ وضعیتِ بی‌تحرك هم فرق می‌کند؛ ستونِ پیکسلِ ماتریس ثبت نشده (گویا نیست)`);
    } else if (noPixels.length) {
      console.log(`  NOTE ${engineId}: لایه دارد ولی هیچ بومی عوض نمی‌شود (احتمالاً بیرونِ دید یا پنلِ دیگر): ${noPixels.join(',')}`);
    }
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `e2e_layers_${engineId}.png`), fullPage: false });
}

// لایۀ موتورِ سوم (`/api/structure3`): پیش‌فرض خاموش و بی‌رأی است، پس سنجشِ آن
// سه چیز را می‌خواهد -- (۱) خاموش بودن واقعاً «منتشر نشده» است نه صفرِ ساختگی،
// (۲) روشن‌کردن کوئریِ واقعی را می‌زند و لایه را «فعال» می‌کند، (۳) رویِ بوم
// چیزی عوض می‌شود. بندِ سوم را نمی‌توان با تستِ واحد اثبات کرد (کدِ ترسیم درِ
// بوم است)، پس از راهِ مقایسۀ تصویرِ بوم سنجیده می‌شود.
async function probeE3(page, engineId, hostSel) {
  const stateOf = (id) => page.$eval(`[data-testid="fts-layer-state-${id}"]`, (e) => e.textContent.trim());
  const rows = await page.$$eval('[data-testid^="fts-layer-row-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-layer-row-', '')));
  for (const id of ['e3-zigzag', 'e3-choch']) {
    ck(`${engineId}: کاتالوگ سطرِ «${id}» را دارد`, rows.includes(id), rows.length + ' سطر');
  }

  const readFlag = async () => {
    const raw = JSON.parse((await page.evaluate((k) => localStorage.getItem(k), CONFIG_KEY)) || '{}');
    return !!(raw && raw.view && raw.view.showStructure3 === true);
  };
  FACTS[engineId + '_e3_off_flag'] = await readFlag();
  ck(`${engineId}: موتورِ سوم پیش‌فرض خاموش است`, (await readFlag()) === false);
  const offState = await stateOf('e3-zigzag').catch(() => '');
  FACTS[engineId + '_e3_off_state'] = offState;
  ck(`${engineId}: بی‌کوئری، لایه «منتشر نشده» است نه «صفر»`, offState === 'منتشر نشده', offState);

  const canvasSel = `${hostSel} canvas`;
  const shot = async () => {
    const el = await page.$(canvasSel);
    return el ? el.screenshot() : null;
  };
  const off1 = await shot();
  const off2 = await shot();
  ck(`${engineId}: بومِ پیش از روشن‌کردن گرفته شد`, !!off1 && !!off2);
  // کنترلِ بی‌تحركی: دو بار در یک وضعیت باید یکی باشد، وگرنه «تغییر» بی‌معناست
  const animates = off1 && off2 && Buffer.compare(off1, off2) !== 0;
  FACTS[engineId + '_e3_canvas_animates'] = animates;

  const resp = page.waitForResponse((r) => r.url().includes('/api/structure3'), { timeout: 90000 });
  await page.click('[data-testid="fts-layer-toggle-e3-zigzag"]');
  const got = await resp.catch(() => null);
  ck(`${engineId}: روشن‌کردنِ لایه کوئریِ /api/structure3 را می‌زند`, !!got,
    got ? `${got.status()} ${new URL(got.url()).pathname}` : 'بی‌پاسخ');
  ck(`${engineId}: ترجیحِ showStructure3 درِ localStorage ثبت شد`, (await readFlag()) === true);

  await page.waitForFunction((id) => {
    const e = document.querySelector(`[data-testid="fts-layer-state-${id}"]`);
    return !!e && e.textContent.trim() !== 'منتشر نشده';
  }, 'e3-zigzag', { timeout: 90000 }).catch(() => null);
  const onState = await stateOf('e3-zigzag').catch(() => '');
  FACTS[engineId + '_e3_on_state'] = onState;
  ck(`${engineId}: لایه رویِ دادهٔ زنده «فعال» شد`, onState === 'فعال', onState);
  await page.waitForTimeout(1200);   // افکتِ ترسیم + یک قابِ رسم

  const on1 = await shot();
  if (off1 && on1) {
    const changed = Buffer.compare(off1, on1) !== 0;
    FACTS[engineId + '_e3_canvas_bytes'] = { off: off1.length, on: on1.length, animates };
    if (animates) {
      console.log('  NOTE بوم در وضعیتِ بی‌تحرك هم تفاوت می‌کند؛ مقایسۀ تصویر گویا نیست');
    } else {
      ck(`${engineId}: روشن‌کردنِ لایهٔ موتورِ سوم بوم را عوض می‌کند (رسمِ واقعی)`, changed,
        `${off1.length} → ${on1.length} بایت`);
    }
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(path.join(OUT_DIR, `e3_${engineId}_canvas_off.png`), off1);
    fs.writeFileSync(path.join(OUT_DIR, `e3_${engineId}_canvas_on.png`), on1);
  }

  const status = await page.textContent('[data-testid="fts-e3-status"]').catch(() => null);
  if (status != null) {
    FACTS[engineId + '_e3_status'] = status;
    ck(`${engineId}: خطِ وضعیتِ موتورِ سوم شمارِ پیوتِ واقعی را می‌گوید`,
      /[۰-۹0-9]+\s*پیوت/.test(status) && /بی‌رأی/.test(status), status.slice(0, 90));
  }

  const evBtn = await page.$('[data-testid="fts-layer-evidence-btn-e3-zigzag"]');
  ck(`${engineId}: دکمهٔ «شواهد» برایِ لایۀ موتورِ سوم هست`, !!evBtn);
  if (evBtn) {
    await evBtn.click();
    await page.waitForSelector('[data-testid="fts-layer-evidence"]', { timeout: 8000 });
    const rule = await page.textContent('[data-testid="fts-evidence-rule"]');
    const src = await page.textContent('[data-testid="fts-evidence-source"]');
    const times = await page.textContent('[data-testid="fts-evidence-times"]').catch(() => '');
    const body = await page.textContent('[data-testid="fts-layer-evidence"]');
    FACTS[engineId + '_e3_evidence'] = { rule, src, times };
    ck(`${engineId}: کارتِ شواهدِ موتورِ سوم صریح «خارج از قواعد جزوه» را می‌گوید`,
      /خارج از قواعد جزوه/.test(rule || ''), (rule || '').slice(0, 90));
    ck(`${engineId}: کارتِ شواهد دهانۀ /api/structure3 را نام می‌برد`,
      /api\/structure3/.test(src || ''), (src || '').slice(0, 90));
    ck(`${engineId}: کارتِ شواهد آستانه‌ها را از خودِ موتور می‌خواند`,
      /ATR/.test(body || '') && /کفِ/.test(body || ''), (body || '').slice(0, 120));
    ck(`${engineId}: کارتِ شواهدِ موتورِ سوم دو زمان را جدا می‌نویسد`,
      /رخ داد/.test(times || '') && /فهمیدیم/.test(times || ''), (times || '').slice(0, 120));
  }

  const legend = await page.$$eval('[data-testid^="fts-legend-item-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-legend-item-', ''))).catch(() => []);
  FACTS[engineId + '_e3_legend'] = legend;
  ck(`${engineId}: افسانه هم ردیفِ موتورِ سوم را بعد از روشن‌کردن نشان می‌دهد`,
    legend.includes('e3-zigzag'), legend.join(','));

  await page.screenshot({ path: path.join(OUT_DIR, `e2e_e3_${engineId}.png`), fullPage: false });
}

// مرحلۀ ۷ -- آزمونِ *یکپارچۀ* سه موتور، نه سه آزمونِ جدا. `/api/structure3` عینِ
// `/api/fts` از `_fts_analysis_series(symbol)` می‌خواند (`api/structure3.py:54`) و
// رابطِ کاربری هیچ `mabna` به `/api/fts` نمی‌فرستد (`useFtsAnalysis.ts:322`)، پس
// مبنایِ سری، عمقِ تحلیل و لنگرِ نمایشِ دو پاسخ باید یکی باشد. اگر واگرا شوند،
// چارت دو ضریبِ متفاوت (`r` و `r3` در `FtsEngineChart.tsx:153`) رویِ یک محور می‌زند
// و لایۀ «مقایسۀ بی‌رأی» دیگر رویِ همان قیمت‌هایِ موتورِ اول نیست.
// پاسخ‌ها از *همان نشستِ مرورگر* شنود می‌شوند (نه درخواستِ جدا از پایتون): همان
// کشِ CDNِ سرور، همان لحظه، همان مسیرِ تولیدیِ رابط.
async function probeEnginesAgree(engineId, seen, seenUrl) {
  const f = seen.fts || null;
  const e = seen.e3 || null;
  const wire = {
    url: { fts: seenUrl.fts || null, e3: seenUrl.e3 || null },
    fts: f && { status: f.status, basis: f.analysis_basis, bars: f.bars, ref_close: f.ref_close,
                pivots_D: (f.fts?.structure_points?.D || []).length,
                pivots_W: (f.fts?.structure_points?.W || []).length },
    e3: e && { status: e.status, basis: e.basis, bars: e.bars, ref_close: e.ref_close,
               pivots: (e.points || []).length, choch: (e.choch || []).length,
               official: e.official, voting: e.voting },
  };
  FACTS[engineId + '_wire_agreement'] = wire;
  ck(`${engineId}: پاسخِ هر دو موتور درِ همان نشستِ مرورگر شنود شد`, !!f && !!e,
    JSON.stringify({ fts: !!f, e3: !!e, urls: wire.url }));
  if (!f || !e) return;
  ck(`${engineId}: هر دو پاسخ status:successاند (نه empty/insufficient ساختگی)`,
    f.status === 'success' && e.status === 'success', `${f.status} / ${e.status}`);
  ck(`${engineId}: مبنا و عمقِ سریِ دو موتور یکی است (مقایسه رویِ همان کندل‌ها)`,
    f.analysis_basis === e.basis && f.bars === e.bars,
    `مبنایِ ۱=${f.analysis_basis} · ۳=${e.basis} · کندلِ ۱=${f.bars} · ۳=${e.bars}`);
  ck(`${engineId}: لنگرِ نمایشِ دو موتور یکی است (وگرنه r و r3 دو ضریبِ جدا می‌شوند)`,
    typeof f.ref_close === 'number' && typeof e.ref_close === 'number' &&
    Math.abs(f.ref_close - e.ref_close) < 1e-9,
    `${f.ref_close} ⇄ ${e.ref_close}`);
  // ادعایِ مرحلۀ ۲ درِ سیمِ زنده (نه دادهٔ کاشته‌شدۀ تستِ واحد): این لایه رأی نمی‌دهد
  ck(`${engineId}: درِ دادوستدِ زنده هم موتورِ سوم بی‌رأی اعلام می‌شود`,
    e.official === false && e.voting === false, `official=${e.official} voting=${e.voting}`);
  console.log(`  NOTE ${engineId}: شمارِ پیوت -- موتورِ ۱ (D/W): ${wire.fts.pivots_D}/${wire.fts.pivots_W} · موتورِ ۳: ${wire.e3.pivots} (دو الگوریتمِ جدا، هیچ‌کدام با دیگری جمع نمی‌شود)`);
}

(async () => {
  const url = `${BASE}/#/technical/${encodeURIComponent(SYMBOL)}`;
  const browser = await chromium.launch({
    executablePath: BROWSERS[0],
    args: ['--disable-blink-features=AutomationControlled'],
  });
  try {
    for (const engine of ['klinecharts', 'ffc']) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e && e.message)));
      // شنودِ همان دو درخواستِ تولیدیِ رابط (نه درخواستِ جدا از بیرون): هر کدام یک‌بار،
      // نخستینِ پاسخِ کامل. `structure3` درِ `probeE3` زده می‌شود، پس اینجا پر می‌شود.
      // دامینِ `/api/fts/` تنها نیست: `/api/fts/config` هم همین زیررشته را دارد و
      // `status:success` می‌فرستد، ولی `analysis_basis` و `bars` درِ آن نیست — این
      // اشتباه درِ دورِ اولِ مرحلۀ ۷ رخ داد و مقایسه را به `undefined ⇄ عدد` انداخت.
      const seen = {};
      const seenUrl = {};
      page.on('response', async (r) => {
        const u = r.url() || '';
        const isCfg = /\/api\/fts\/config(\?|$)/.test(u);
        const key = u.includes('/api/structure3') ? 'e3'
          : (u.includes('/api/fts/') && !isCfg ? 'fts' : null);
        if (!key || seen[key]) return;
        try {
          const body = await r.json();
          // دهانۀ مقایسه باید درِ بدنه باشد، وگرنه پاسخِ دیگری جا را پر کرده است
          if (body && body.status && (key === 'e3' ? body.basis : body.analysis_basis)) {
            seen[key] = body;
            seenUrl[key] = u.replace(/^https?:\/\/[^/]+/, '');
          }
        } catch (_) { /* بی‌خبر رد می‌شویم و ck می‌گوید */ }
      });
      await page.addInitScript(([key, eng]) => {
        try {
          const raw = JSON.parse(localStorage.getItem(key) || '{}');
          raw.chartEngine = eng;
          if (!raw.view) raw.view = {};
          raw.view.showLegend = true;
          localStorage.setItem(key, JSON.stringify(raw));
        } catch (_) { /* بی‌مصرف: کلیدِ تازه */ }
      }, [CONFIG_KEY, engine]);
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await loginThroughUI(page);
      const hostSel = engine === 'ffc' ? '[data-testid="ffc-chart-host"]' : '[data-testid="nn-chart-host"]';
      try {
        await page.waitForSelector(hostSel, { timeout: 45000 });
      } catch (_) {
        ck(`${engine}: میزبانِ چارت ظاهر شد`, false, 'بی‌خبر نشوید — سرور بالا نیست یا feed خطا داد');
        continue;
      }
      ck(`${engine}: میزبانِ چارت ظاهر شد`, true);
      // میزبان بی‌داده هم mount می‌شود؛ بوم فقط وقتی خوراکِ زنده برسد ساخته می‌شود
      let drewCanvas = true;
      try {
        await page.waitForSelector(`${hostSel} canvas`, { timeout: 60000 });
      } catch (_) {
        drewCanvas = false;
      }
      ck(`${engine}: چارت رویِ دادهٔ زنده رندر شد (بوم ساخته شد)`, drewCanvas);
      await page.waitForSelector('[data-testid="chart-area"]', { timeout: 15000 });
      try {
        await openLayersTab(page);
      } catch (_) {
        ck(`${engine}: تبِ داکِ «لایه‌های FTS» باز شد`, false);
        continue;
      }
      ck(`${engine}: تبِ داکِ «لایه‌های FTS» باز شد`, true);
      const waitedMs = await waitForFeed(page, engine);
      FACTS[engine + '_feed_ms'] = waitedMs;
      await probe(page, engine, hostSel);
      await probeE3(page, engine, hostSel);
      await probeEnginesAgree(engine, seen, seenUrl);
      ck(`${engine}: بی‌خطایِ console/pageerror`, errors.length === 0, errors.slice(0, 2).join(' | '));
      await ctx.close();
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(OUT_DIR, 'fts_layers_e2e.json'),
    JSON.stringify({ base: BASE, symbol: SYMBOL, facts: FACTS, fails: FAILS }, null, 1));
  console.log();
  if (FAILS.length) {
    console.log(`E2E FAIL (${FAILS.length}):`);
    FAILS.forEach((f) => console.log('  -', f));
    process.exit(1);
  }
  console.log('FTS LAYERS E2E OK — هر دو موتور رویِ مرورگرِ واقعی سنجیده شد');
})().catch((e) => {
  console.log('E2E FAIL — اجرا نشد:', String(e && e.message).slice(0, 300));
  process.exit(2);
});
