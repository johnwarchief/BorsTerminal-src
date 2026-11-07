// _audit/ta_ui_probe_v1.js -- بازرسیِ رابطِ tradersarena.ir با مرورگرِ واقعی (Playwright + Edge)
// تصحیحِ برچسب (به‌دستِ مالک): این فایل «رهاورد» نبود؛ تریدرز آرنا است. مرجعِ اصلیِ مأموریت
// rahavard365.com است و در _audit/ra365_ui_probe_v1.js سنجیده می‌شود. داده‌های این فایل فقط
// برای «اطلاعات وضعیت بازار» و به‌عنوان رابطِ دومِ برچسب‌دار معتبر است، نه اثباتِ پاریتیِ رهاورد.
// هدف: ثابت کند درِ رابطِ واقعی چه چیزی دیده می‌شود و چه چیزی به نشستِ کاربر نیاز دارد.
// فقط خواندنی: هیچ فرمی پر نمی‌شود، هیچ رمز/کوکی/توکنی خوانده یا ذخیره نمی‌شود.
// پروفایل مرورگر بیرونِ مخزن است (temp) تا هیچ نشستِ کاربری درِ فایل‌هایِ پروژه نیفتد.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, '_audit');
const PROFILE = path.join(os.tmpdir(), 'bors-ta-probe-profile');
const BROWSERS = [
  process.env.TA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

const arg = (name, dflt) => {
  const i = process.argv.indexOf('--' + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
};

const INS = { فولاد: '46348559193224090', وبملت: '778253364357513', شبهرن: '22667016906590506', ولانا: '66830065858417081', خگستر: '48990026850202503' };

const PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => Array.from(document.querySelectorAll(s));
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  const toolbar = q('.technical-chart-drawing-toolbar, #hexa').length > 0;
  const toolItems = q('.technical-chart-drawing-toolbar *, #hexa *')
    .map((e) => e.getAttribute && (e.getAttribute('title') || e.getAttribute('data-title') || txt(e)))
    .filter((s) => s && s.length > 1 && s.length < 60);
  const gated = q('*')
    .map((e) => (e.childElementCount === 0 ? txt(e) : ''))
    .filter((s) => /ورود|ثبت‌نام|خرید اشتراک|ابتدا وارد|مجاز نیست|پریمیوم| restricted/.test(s) && s.length < 160);
  return {
    url: location.href,
    title: document.title,
    ready: document.readyState,
    nodes: q('*').length,
    canvases: q('canvas').length,
    svgs: q('svg').length,
    tables: q('table').length,
    toolbarPresent: toolbar,
    toolbarItems: uniq(toolItems).slice(0, 60),
    indicatorBlocks: uniq(q('[class*="indicator" i], [id*="indicator" i]').map(txt).filter((s) => s && s.length < 80)).slice(0, 25),
    gateMessages: uniq(gated).slice(0, 12),
    // وضعیتِ احراز هویت فقط به‌صورتِ بولینِ همان attributerِ خودِ صفحه خوانده می‌شود؛
    // هیچ مقدارِ کوکی، لوکال‌استوریج یا توکنی بیرون نمی‌رود.
    pageAuthFlag: (() => {
      const el = document.querySelector('[data-authenticated]');
      return el ? el.getAttribute('data-authenticated') : null;
    })(),
    bodyTextSample: txt(document.body).slice(0, 240),
  };
};

(async () => {
  if (!BROWSERS.length) throw new Error('no browser executable found (set TA_BROWSER)');
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: BROWSERS[0],
    headless: arg('headless', 'true') !== 'false',
    viewport: { width: 1600, height: 900 },
    locale: 'fa-IR',
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  const results = {};
  for (const [sym, ins] of Object.entries(INS)) {
    if (arg('symbol', null) && arg('symbol', null) !== sym) continue;
    const url = `https://tradersarena.ir/${ins}/chart/price`;
    const rec = { url };
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForTimeout(6000);
      rec.probe = await page.evaluate(PROBE);
      rec.toolbarSelectorHit = await page
        .waitForSelector('.technical-chart-drawing-toolbar, #hexa', { timeout: 15000 })
        .then(() => true)
        .catch(() => false);
      rec.screenshot = `_audit/ta_ui_${sym}.png`;
      await page.screenshot({ path: path.join(OUT_DIR, `ta_ui_${sym}.png`), fullPage: true });
    } catch (e) {
      rec.error = String(e && e.message ? e.message : e).slice(0, 200);
    }
    results[sym] = rec;
    console.log(`\n== ${sym} == ${rec.url}`);
    if (rec.probe) {
      console.log('  title:', rec.probe.title, '| nodes:', rec.probe.nodes,
        '| canvas:', rec.probe.canvases, '| svg:', rec.probe.svgs, '| table:', rec.probe.tables);
      console.log('  authFlag:', rec.probe.pageAuthFlag, '| toolbar:', rec.probe.toolbarPresent,
        'selector:', rec.toolbarSelectorHit);
      console.log('  tools:', rec.probe.toolbarItems.slice(0, 25).join(' / ') || '(none)');
      console.log('  gate msgs:', rec.probe.gateMessages.join(' | ') || '(none)');
    }
    if (rec.error) console.log('  ERROR:', rec.error);
  }
  fs.writeFileSync(path.join(OUT_DIR, 'ta_ui_probe.json'), JSON.stringify(results, null, 1));
  console.log('\nwrote _audit/ta_ui_probe.json');
  await ctx.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
