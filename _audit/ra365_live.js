// _audit/ra365_live.js -- کارگرِ نشستِ زنده‌ی ره‌آورد ۳۶۵ (rahavard365.com) با همان پروفایلِ لاگین‌شده
// پروفایل: %TEMP%\bors-ra365-probe-profile (خارج از مخزن). مالک یک‌بار درِ آن لاگین کرده است؛
// هر اجرا همین پروفایل را باز می‌کند پس نشست احراز هویت‌شده حفظ است. هیچ رمز/کوکی/توکنی
// خوانده یا در فایل نمی‌آید — فقط متن/تعدادِ DOM و اسکرین‌شات.
// طرز استفاده: node _audit/ra365_live.js --job=_audit/ra365_job_<x>.js --out=_audit/ra365_<x>.json
// فایلِ job یک تابع async exports می‌کند: ({ page, ctx, shot, probe, say }) => report
const os = require('os');
const fs = require('fs');
const path = require('path');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.resolve(__dirname, '..');
const PROFILE = path.join(os.tmpdir(), 'bors-ra365-probe-profile');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => {
  const kv = process.argv.find((a) => a.startsWith('--' + n + '='));
  if (kv) return kv.slice(n.length + 3);
  const i = process.argv.indexOf('--' + n);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : d;
};

// PROBE: آنچه درِ رابطِ واقعی دیده می‌شود (متن/شمارش) + ردپایِ ویجتِ چارت
const PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => { try { return Array.from(document.querySelectorAll(s)); } catch { return []; } };
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  const leaves = q('body *').filter((e) => e.childElementCount === 0).map(txt);
  const short = leaves.filter((s) => s && s.length > 0 && s.length < 120);
  return {
    url: location.href,
    title: document.title,
    ready: document.readyState,
    nodes: q('body *').length,
    canvases: q('canvas').length,
    svgs: q('svg').length,
    iframes: q('iframe').map((f) => (f.src || '').slice(0, 90)).filter(Boolean).slice(0, 6),
    chartWidgets: {
      tradingview: q('[class*="tradingview" i], [id*="tradingview" i], [class*="tv-chart" i]').length,
      lightweight: q('[class*="lightweight" i]').length,
    },
    // وضعیتِ احراز هویت فقط از رویِ همان چیزی که درِ صفحه نوشته می‌شود
    loginButtonPresent: short.some((s) => /^(ورود|ورود \/ ثبت‌نام|ثبت‌نام)$/.test(s)),
    logoutTextPresent: short.some((s) => /خروج|حساب کاربری|اشتراک من|پروفایل من/.test(s)),
    paywallOrGate: uniq(short.filter((s) => /خرید اشتراک|ابتدا وارد|مجاز نیست|محدود|نسخۀ رایگان|پریمیوم/.test(s))).slice(0, 8),
    toolbarItems: uniq(
      q('[class*="toolbar" i] *, [class*="tools" i] *, [class*="drawing" i] *, [title], [aria-label]')
        .map((e) => (e.getAttribute && (e.getAttribute('title') || e.getAttribute('aria-label') || e.getAttribute('data-title'))) || (e.childElementCount === 0 ? txt(e) : ''))
        .filter((s) => s && s.length > 1 && s.length < 60)
    ).slice(0, 120),
    visibleTextSample: txt(document.body).slice(0, 700),
    axisLikeTexts: uniq(short.filter((s) => /^[\d\u06F0-\u06F9.,%]{1,12}$/.test(s))).slice(0, 60),
    jalaliDates: uniq(short.filter((s) => /^[\d\u06F0-\u06F9]{1,4}-[\d\u06F0-\u06F9]{1,2}-[\d\u06F0-\u06F9]{1,2}$/.test(s))).slice(0, 20),
  };
};

(async () => {
  const jobPath = path.resolve(ROOT, arg('job', '_audit/ra365_job_smoke.js'));
  const outPath = path.resolve(ROOT, arg('out', '_audit/ra365_live_out.json'));
  if (!fs.existsSync(EXE)) throw new Error('msedge not found: ' + EXE);
  if (!fs.existsSync(jobPath)) throw new Error('job not found: ' + jobPath);

  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: EXE,
    headless: arg('headless', 'false') === 'true',
    viewport: { width: 1600, height: 900 },
    locale: 'fa-IR',
    args: ['--no-first-run', '--no-default-browser-check'],
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  const net = [];
  page.on('response', (r) => {
    try {
      const u = r.url();
      if (/rahavard365\.com\/api/i.test(u)) net.push({ url: u.slice(0, 160), status: r.status(), type: r.request().resourceType(), bytes: Number(r.headers()['content-length'] || 0) });
    } catch { /* بی‌صدا */ }
  });

  const used = { screenshots: [] };
  const shot = async (name, p = page) => {
    const file = path.join(ROOT, '_audit', name.endsWith('.png') ? name : name + '.png');
    await p.screenshot({ path: file, fullPage: false }).catch((e) => console.log('shot fail', String(e).slice(0, 100)));
    used.screenshots.push(path.basename(file));
    return path.basename(file);
  };
  const probe = async (p = page) => p.evaluate(PROBE);
  const say = (m) => console.log(m);

  let report;
  let failure = null;
  try {
    report = await require(jobPath)({ page, ctx, shot, probe, say, PROBE, net });
  } catch (e) {
    failure = String(e && e.stack ? e.stack : e).slice(0, 1200);
    report = { error: failure };
  }
  const out = { ranAt: new Date().toISOString(), profile: PROFILE, browser: EXE, job: path.basename(jobPath), report, screenshots: used.screenshots, apiCalls: net.slice(0, 80) };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2), 'utf8');
  console.log('WROTE ' + outPath + (failure ? '  (job failed)' : ''));
  await ctx.close();
})().catch((e) => { console.error('FATAL ' + String(e)); process.exit(1); });
