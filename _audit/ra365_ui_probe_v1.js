// _audit/ra365_ui_probe_v1.js -- بازرسیِ رابطِ واقعیِ «ره‌آورد ۳۶۵» (rahavard365.com) با مرورگرِ واقعی
// چرا این فایل جداست: پیش از این، ta_ui_probe_v1.js نشانیِ tradersarena.ir را باز می‌کرد و
// آن را «رهاورد» صدا می‌زد. این دو محصولِ جدا هستند (ره‌آورد: Next.js + TradingView؛
// تریدرز آرنا: lightweight-charts). اینجا فقط rahavard365.com هدف است.
// فقط خواندنی: هیچ فرمی پر نمی‌شود، هیچ رمز/کوکی/توکنی خوانده یا ذخیره نمی‌شود.
// پروفایل مرورگر بیرونِ مخزن است (temp) تا هیچ نشستِ کاربری درِ فایل‌هایِ پروژه نیفتد.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, '_audit');
const PROFILE = path.join(os.tmpdir(), 'bors-ra365-probe-profile');
const BROWSERS = [
  process.env.RA_BROWSER,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].filter(Boolean);

const NAV_TIMEOUT = 90000;

// PROBE: آنچه درِ رابطِ واقعی دیده می‌شود + وضعیتِ دسترسی (بدونِ خواندنِ نشست)
const PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => Array.from(document.querySelectorAll(s));
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  const leaves = q('*').filter((e) => e.childElementCount === 0).map(txt);
  const gate = uniq(leaves)
    .filter((s) => s && s.length < 160 && /ورود|ثبت ?نام|خرید اشتراک|ابتدا وارد|مجاز|پریمیوم|محدود| اشتراک/.test(s))
    .slice(0, 15);
  return {
    url: location.href,
    title: document.title,
    ready: document.readyState,
    nodes: q('*').length,
    canvases: q('canvas').length,
    svgs: q('svg').length,
    tables: q('table').length,
    iframes: q('iframe').map((f) => (f.src || '').slice(0, 120)).slice(0, 8),
    // ردپایِ ویجت/کتابخانۀ چارت
    chartLib: {
      tradingview: q('[class*="tv-chart" i], [id*="tradingview" i], [class*="tradingview" i]').length,
      lightweight: q('[class*="lightweight" i]').length,
      svgCrosshair: q('svg[class*="crosshair" i]').length,
    },
    // پیوندهایِ نماد که درِ همین صفحه پیدا می‌شوند (/asset/<id>/...)
    assetLinks: uniq(q('a[href*="/asset/"]').map((a) => a.getAttribute('href'))).slice(0, 40),
    // شمارۀ نماد از رویِ همان لینک‌ها
    symbolTexts: uniq(q('a[href*="/asset/"]').map((a) => txt(a)).filter((s) => s && s.length < 40)).slice(0, 40),
    toolbarItems: uniq(
      q('[class*="toolbar" i] *, [class*="tools" i] *, [class*="drawing" i] *')
        .map((e) => (e.getAttribute && (e.getAttribute('title') || e.getAttribute('data-title') || e.getAttribute('aria-label')) || txt(e)))
        .filter((s) => s && s.length > 1 && s.length < 60)
    ).slice(0, 80),
    gateMessages: gate,
    loginAffordance: uniq(leaves).filter((s) => s && /^(ورود|登录|Login|وارد شوید|ورود یا ثبت‌نام)$/.test(s)).slice(0, 5),
    bodyTextSample: txt(document.body).slice(0, 400),
  };
};

(async () => {
  if (!BROWSERS.length) throw new Error('no browser executable found (set RA_BROWSER)');
  const exe = BROWSERS.find((p) => fs.existsSync(p));
  if (!exe) throw new Error('browser exe not found: ' + BROWSERS.join(' | '));
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: exe,
    headless: false,
    viewport: { width: 1600, height: 900 },
    locale: 'fa-IR',
    args: ['--no-first-run', '--no-default-browser-check'],
  });
  const page = ctx.pages()[0] || (await ctx.newPage());

  // هر پاسِ داده‌ای که خودِ صفحه می‌گیرد ثبت می‌شود (نشانی + کد + حجم)، نه بدنه‌اش.
  const net = [];
  page.on('response', (r) => {
    try {
      const u = r.url();
      if (/api|data|asset|chart|price|candle|indicator/i.test(u) && !/\.(png|jpg|svg|woff2?|css|js)(\?|$)/i.test(u)) {
        net.push({ url: u.slice(0, 180), status: r.status(), type: r.request().resourceType() });
      }
    } catch { /* بی‌سر‌و‌صدا */ }
  });

  const steps = {};
  const run = async (name, url, shot) => {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
      // صبر برای تمام‌شدنِ اسپلشِ SPA
      await page.waitForTimeout(9000);
      try {
        await page.waitForSelector('.SplashScreen_splashContainer__IdB9n', { state: 'detached', timeout: 30000 });
      } catch { /* اسپلش نرفته بود؛ همان وضعیتِ واقعی را گزارش می‌کنیم */ }
      await page.waitForTimeout(3000);
      steps[name] = await page.evaluate(PROBE);
      steps[name].splashStillPresent = await page.evaluate(() => !!document.querySelector('.SplashScreen_splashContainer__IdB9n'));
      if (shot) await page.screenshot({ path: path.join(OUT_DIR, shot), fullPage: false });
      steps[name].shot = shot || null;
      console.log(`[ok] ${name} :: ${steps[name].url} :: nodes=${steps[name].nodes} tv=${steps[name].chartLib.tradingview} splash=${steps[name].splashStillPresent}`);
    } catch (e) {
      steps[name] = { error: String(e).slice(0, 300), url };
      console.log(`[fail] ${name} :: ${String(e).slice(0, 200)}`);
    }
  };

  await run('home', 'https://rahavard365.com/', 'ra365_home.png');
  await run('stock', 'https://rahavard365.com/stock', 'ra365_stock.png');

  // اگر لینکِ نمادی در /stock پیدا شد، همان را به‌عنوان صفحۀ چارت باز کن (حدس نمی‌زنیم).
  let chartUrl = null;
  const links = (steps.stock && steps.stock.assetLinks) || (steps.home && steps.home.assetLinks) || [];
  const l = links.find((h) => /\/asset\/[^/]+\/(chart|values|$)/.test(h || '')) || links[0];
  if (l) chartUrl = new URL(l, 'https://rahavard365.com/').href;
  if (chartUrl) {
    await run('assetChart', chartUrl, 'ra365_asset_chart.png');
    steps.assetChartUrl = chartUrl;
  } else {
    steps.assetChartUrl = null;
    steps.assetChartNote = 'هیچ لینک /asset/ در home/stock قابل شمارش نبود؛ صفحۀ نماد حدس زده نشد';
  }

  const out = { ranAt: new Date().toISOString(), browser: exe, profile: PROFILE, steps, network: net.slice(0, 60) };
  fs.writeFileSync(path.join(OUT_DIR, 'ra365_ui_probe.json'), JSON.stringify(out, null, 2), 'utf8');
  console.log('\n=== خلاصه ===');
  for (const [k, v] of Object.entries(steps)) {
    if (!v || k === 'assetChartUrl') continue;
    console.log(`${k}: ${v.error ? 'ERROR ' + v.error : `title=${v.title} nodes=${v.nodes} gate=${(v.gateMessages || []).length} toolbar=${(v.toolbarItems || []).length}`}`);
  }
  console.log('assetChartUrl: ' + steps.assetChartUrl);
  await ctx.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
