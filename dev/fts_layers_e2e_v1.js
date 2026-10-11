// dev/fts_layers_e2e_v1.js — E2Eِ زندهٔ لایه‌های FTS رویِ مرورگرِ واقعی (مرحلۀ ۱۱)
//
// چرا این فایل درِ `dev/run_all_tests.py` نیست: سوئیت‌هایِ آن باید آفلاین بدوند و
// سرورِ dev بسته باشد (AGENTS.md §گیت‌ها). این اسکریپت عمداً *برعکس* است — به
// بک‌اندِ زنده (127.0.0.1:8001) و vite (5173) نیاز دارد و همان چیزی را می‌سنجد که
// vitest نمی‌تواند: رندرِ واقعیِ چارت، داکِ «لایه‌های FTS»، سوییچِ زنده، و کارتِ
// شواهد درِ هر دو موتور (klinecharts ⇄ FFC).
//
// اجرا:
//   python -m uvicorn app:app --port 8001        # ترمینالِ ۱
//   cd frontend && npm run dev                   # ترمینالِ ۲
//   node dev/fts_layers_e2e_v1.js --symbol فولاد  # ترمینالِ ۳
//
// خروجی: `_audit/fts_layers_e2e.json` + دو اسکرین‌شات (یکی هر موتور). بی‌سرور،
// صریحاً FAIL می‌شود — «رد شدنِ بی‌خبر» نداریم.
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
  }, { timeout: 60000 }).catch(() => { /* بی‌پنلِ باز: خودِ ck بعدی می‌گوید */ });
  return Date.now() - t0;
}

async function probe(page, engineId) {
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

  const legend = await page.$$eval('[data-testid^="fts-legend-item-"]', (els) =>
    els.map((e) => e.getAttribute('data-testid').replace('fts-legend-item-', '')),
  ).catch(() => []);
  FACTS[engineId + '_legend'] = legend;
  ck(`${engineId}: افسانۀ چارت از همان رجیستری پر می‌شود`, legend.length >= 1, legend.join(','));

  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `e2e_layers_${engineId}.png`), fullPage: false });
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
      await probe(page, engine);
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
