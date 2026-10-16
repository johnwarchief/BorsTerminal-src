// tools/ui_mobile_probe.mjs -- سنجشِ عرضِ گوشی (۳۶۰/۳۹۰/۴۳۰) باِ روشِ ثابت
//
// بندِ ۲.۱ مأموریتِ System 2: «جدول درِ گوشی به‌اندازه‌ای فشرده یاِ بریده است که
// اطلاعات عملاً قابلِ استفاده نیست» وِ «عرض‌هایِ ۳۶۰، ۳۹۰ وِ ۴۳۰ را آزمایش کن».
// اینِ فایل همانِ ادعا را بهِ عددِ قابلِ مقایسه تبدیل می‌کند -- پیشِ ازِ اصلاح وِ
// پسِ ازِ آن، باِ یکِ روشِ واحدِ اندازه‌گیری وِ بی‌تغییرِ آستانه‌ها:
//   docOverflow   سرریزِ افقیِ سند (نوارِ اسکرولِ کلِ صفحه = بدترینِ حالتِ گوشی)
//   clipped       برگِ انتهاییِ بریده‌شده (scrollWidth > clientWidth) باِ متنِ نمونه
//   tiny          برگِ باِ فونتِ محاسبه‌شده کوچک‌ترِ ازِ ۱۱px
//   tap           کنترلِ قابلِ لمسِ زیرِ ۴۰px درِ هرِ بعد (راهنمایِ Android/iOS: ۴۸)
//   hscrollers    ظرفِ اسکرولِ افقیِ واقعی -- وِ آیاِ باِ کیبورد/لمس قابلِ درک است
//   bottomBar     ارتفاعِ نوارِ پایینِ fixed وِ آیاِ محتوا زیرِ آنِ می‌رود
//
// اجرا:  node tools/ui_mobile_probe.mjs --base=http://127.0.0.1:8012 \
//          --out=_audit/ui2/mobile-before.json --shots=_audit/ui2
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const args = Object.fromEntries(process.argv.slice(2).map((a) => {
  const m = /^--([^=]+)=(.*)$/.exec(a);
  return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true];
}));
const BASE = args.base || 'http://127.0.0.1:8012';
const OUT = args.out || path.join('_audit', 'ui2', 'mobile-before.json');
const SHOTS = !!args.shots;
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const AUTH = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];

const WIDTHS = (args.widths || '360,390,430').split(',').map((w) => Number(w));
const HEIGHT = Number(args.height || 844);
const ROUTES = (args.routes || 'market|/market,market-status|/market-status,watch|/watch,'
  + 'notifications|/notifications,technical|/technical/فولاد,fundamental|/fundamental/فولاد,'
  + 'portfolio|/portfolio/فولاد,order-line|/order-line').split(',').map((s) => {
  const i = s.indexOf('|');
  return { name: s.slice(0, i), path: s.slice(i + 1) };
});

// روشِ v2 -- «دیده‌شدنی» باِ «درِ DOM» یکی نیست. نسخهٔ اولِ اینِ سنجش همِۀِ
// گره‌هایِ body را می‌شمرد وِ پسِ ازِ `sr-only` (عنوانِ صفحه، ۱×۱ پیکس) وِ
// کشویِ `SymbolInspector` (باِ translate ازِ صفحه بیرونِ رفته) ده‌ها «بریدگی» وِ
// «فونتِ ریز»ِ جعلی گزارش می‌کرد. اکنون فقطِ گره‌ای شمرده می‌شود که کادرش
// لااقلِ ۴×۴ پیکس است وِ گوشۀِ بالا-راستش داخلِ viewport می‌افتد.
const MEASURE = () => {
  const root = document.documentElement;
  const vw = root.clientWidth;
  const vh = root.clientHeight;
  const onScreen = (e) => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    if (s.clipPath !== 'none' || /rect\(1px|rect\(0px/.test(s.clip || '')) return false;
    const r = e.getBoundingClientRect();
    return r.width >= 4 && r.height >= 4 && r.left >= -1 && r.top >= -1 && r.left <= vw && r.top <= vh;
  };
  const leaves = Array.from(document.querySelectorAll('body *')).filter((e) => (
    e.children.length === 0 && (e.textContent || '').trim().length > 1 && onScreen(e)
  ));
  const clipped = leaves.filter((e) => e.scrollWidth > e.clientWidth + 2);
  const tiny = leaves.filter((e) => parseFloat(getComputedStyle(e).fontSize) < 11);
  const taps = Array.from(document.querySelectorAll('a,button,input,select,[role="button"],[role="tab"]'))
    .filter((e) => {
      if (!onScreen(e)) return false;
      const r = e.getBoundingClientRect();
      return r.height < 40 || r.width < 40;
    });
  const hscroll = Array.from(document.querySelectorAll('body *')).filter((e) => {
    const s = getComputedStyle(e);
    return /auto|scroll/.test(s.overflowX) && e.scrollWidth > e.clientWidth + 4 && onScreen(e);
  });
  const bars = Array.from(document.querySelectorAll('body *')).filter((e) => {
    const s = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    return s.position === 'fixed' && r.bottom >= window.innerHeight - 2
      && r.height > 8 && r.height < 220 && r.width > vw * 0.6;
  });
  const main = document.querySelector('main') || document.body;
  const lastContent = main.lastElementChild;
  return {
    vw,
    docOverflow: Math.max(0, root.scrollWidth - root.clientWidth),
    clippedCount: clipped.length,
    clippedSample: clipped.slice(0, 6).map((e) => ({
      tag: e.tagName, text: (e.textContent || '').trim().slice(0, 26),
      lost: e.scrollWidth - e.clientWidth, ellipsis: getComputedStyle(e).textOverflow === 'ellipsis',
      title: !!e.getAttribute('title') || !!e.closest('[title]'),
    })),
    tinyCount: tiny.length,
    tinySample: tiny.slice(0, 3).map((e) => ({
      text: (e.textContent || '').trim().slice(0, 20), px: getComputedStyle(e).fontSize,
    })),
    tapCount: taps.length,
    // گروه‌بندیِ متخلفینِ لمسی: «۴۱ کنترلِ زیرِ ۴۰px» هیچِ کاری نمی‌کند؛ آنچه اصلاح
    // می‌خواهد نامِ خودِ کنترل‌هاست وِ کمترینِ عددِ دیدۀِ هرِ گروه.
    tapGroups: (() => {
      const g = new Map();
      for (const e of taps) {
        const r = e.getBoundingClientRect();
        const key = e.getAttribute('data-testid')
          || (e.getAttribute('aria-label') || '').trim().slice(0, 22)
          || (e.title || '').trim().slice(0, 22)
          || (e.textContent || '').trim().slice(0, 18)
          || `${e.tagName.toLowerCase()}.${String(e.className).split(' ')[0]}`;
        const cur = g.get(key) || { n: 0, minW: 999, minH: 999, tag: e.tagName };
        cur.n += 1;
        cur.minW = Math.min(cur.minW, Math.round(r.width));
        cur.minH = Math.min(cur.minH, Math.round(r.height));
        g.set(key, cur);
      }
      return Array.from(g.entries())
        .map(([k, v]) => ({ ctrl: k, n: v.n, minW: v.minW, minH: v.minH }))
        .sort((a, b) => b.n - a.n).slice(0, 12);
    })(),
    tapSample: taps.slice(0, 4).map((e) => {
      const r = e.getBoundingClientRect();
      return { tag: e.tagName, label: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 18),
               w: Math.round(r.width), h: Math.round(r.height) };
    }),
    hscrollCount: hscroll.length,
    hscrollDetail: hscroll.slice(0, 4).map((e) => ({
      testid: e.getAttribute('data-testid') || e.className.toString().slice(0, 28),
      over: e.scrollWidth - e.clientWidth,
      focusable: e.tabIndex >= 0 || !!e.querySelector('[tabindex],a,button,input,select'),
    })),
    bottomBar: bars.map((e) => {
      const s = getComputedStyle(e);
      const r = e.getBoundingClientRect();
      return {
        testid: e.getAttribute('data-testid') || e.tagName,
        h: Math.round(r.height),
        paddingBottom: s.paddingBottom,
        safeAreaInset: /env\(/.test(s.getPropertyValue('padding-bottom')) ? 'env-in-css' : s.paddingBottom,
        items: Array.from(e.querySelectorAll('a,button')).length,
        labelsHidden: Array.from(e.querySelectorAll('a,button')).filter((c) => {
          const t = (c.textContent || '').trim();
          return t.length === 0 || c.clientWidth < 24;
        }).length,
      };
    }),
    contentUnderBar: (() => {
      if (!bars.length || !lastContent) return null;
      const barTop = Math.min(...bars.map((e) => e.getBoundingClientRect().top));
      return Math.round(Math.max(0, lastContent.getBoundingClientRect().bottom - barTop));
    })(),
    boardCards: document.querySelectorAll('div[data-testid^="board-card-"]').length,
    boardRows: document.querySelectorAll('[data-testid="tape-row"], [data-testid^="watch-row-"], tr[data-testid]').length,
  };
};

const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });
const out = { base: BASE, generatedAt: new Date().toISOString(),
  method: 'v5 — فقطِ گره‌هایِ داخلِ viewport (بی‌sr-only وِ بی‌کشویِ آف‌کانون)، عرض‌هایِ ثابت، نشستنِ hash وِ بی‌صداشدنِ DOM پیشِ ازِ اندازه‌گیر (v3 صفحۀِ قبلی را می‌سنجید)', rows: {} };

for (const w of WIDTHS) {
  const ctx = await browser.newContext({ viewport: { width: w, height: HEIGHT }, locale: 'fa-IR', deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));
  await page.goto(`${BASE}/#${ROUTES[0].path}`, { waitUntil: 'domcontentloaded' });
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    await page.locator('input[type="text"]').first().fill(USER);
    await page.locator('input[type="password"]').first().fill(PASS);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(1500);
  }
  out.rows[w] = {};
  for (const r of ROUTES) {
    await page.goto(`${BASE}/#${r.path}`, { waitUntil: 'domcontentloaded' });
    // ناوبریِ بی‌بارگذاری (hashchange) صفحۀِ پیشین را درِ DOM نگه می‌دارد وِ آزمونِ
    // «بی‌صداشدن» رویِ گره‌هایِ قدیمی quiet می‌شود: درِ اجرایِ v6/shots یکِ سطرِ
    // market-status، کارت‌هایِ /market را گزارش کرد. `reload` هرِ سطرِ سنجش را ازِ
    // صفحۀِ خودش شروع می‌کند (ورود درِ localStorage می‌ماند).
    await page.reload({ waitUntil: 'domcontentloaded' });
    // v5: روتر اینِ برنامه hash-based است، پسِ `goto` بهِ `#/ دیگری` یکِ documentِ
    // همانِ صفحۀِ قبلی را نگه می‌دارد. نسخهٔ v3 باِ «طولِ متن > ۴۰۰» آماده‌شدن را
    // می‌سنجید وِ آنِ شرط را DOMِ *قبلی* برآورده می‌کرد -- نتيجۀِ آن اعدادِ جابه‌جا
    // (کارتِ /market رویِ سطرِ /market-status) وِ چهارِ صفحۀِ آخرِ یکسان درِ ۴۳۰.
    // اکنون: (۱) hashِ مقصد بنشیند، (۲) بی‌صداشدنِ DOM (۳۵۰ms بی‌Mutation) وِ بعد
    // اندازه‌گیر. `hashOk` ثبت می‌شود تاِ اینِ خطایِ روشِ پیشین قابلِ ردیابی بماند.
    const tSettle = Date.now();
    // hashِ مرورگر percent-encoded است وِ مسیرِ آزمونِ فارسی نه؛ بی‌decodeURIComponent
    // اینِ مقایسه هرگزِ true نمی‌شد (اجرای v5 برایِ three صفحّه hash=BAD داد وِ آنِ
    // سطرهایِ بی‌اعتبار بودند).
    const hashOk = await page.waitForFunction(
      (p) => decodeURIComponent(window.location.hash).includes(p), r.path, { timeout: 10000 })
      .then(() => true).catch(() => false);
    // صفحّه‌هایِ پویا هرگزِ کاملاً بی‌صدا نمی‌شوند (انیمیشن/فلاشِ اعداد)؛ پسِ سقفِ
    // سکوت ۲.۵s است وِ رد نشدنِ آن هم ثبت می‌شود، نه اینکه ۳۰s بلوکه کند.
    const quiet = await page.waitForFunction(() => new Promise((resolve) => {
      let t = setTimeout(done, 300);
      const obs = new MutationObserver(() => { clearTimeout(t); t = setTimeout(done, 300); });
      function done() { obs.disconnect(); resolve(true); }
      obs.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
    }), { timeout: 2500 }).then(() => true).catch(() => false);
    const settleMs = Date.now() - tSettle;
    const m = await page.evaluate(MEASURE);
    m.consolePageErrors = errs.length;
    m.settleMs = settleMs;
    m.hashOk = hashOk;
    m.quiet = quiet;
    m.measuredRoute = await page.evaluate(() => (document.querySelector('h1.sr-only') || {}).textContent || null);
    out.rows[w][r.name] = m;
    const cells = [
      `doc=${m.docOverflow}px`, `clip=${m.clippedCount}`, `tiny=${m.tinyCount}`,
      `tap<40=${m.tapCount}`, `hsc=${m.hscrollCount}`,
      `bar=${m.bottomBar.map((b) => `${b.h}px/pb:${b.paddingBottom}`).join('+') || '—'}`,
      `under=${m.contentUnderBar ?? '—'}px`, `cards=${m.boardCards}`, `rows=${m.boardRows}`, `settle=${m.settleMs}ms`, `hash=${m.hashOk?'ok':'BAD'}`
    ].join(' ');
    console.log(`${String(w).padStart(4)}×${HEIGHT} ${r.name.padEnd(14)} ${cells}`);
    if (SHOTS && w === 390 && ['market', 'market-status'].includes(r.name)) {
      fs.mkdirSync(path.join(REPO, '_audit', 'ui2'), { recursive: true });
      await page.screenshot({ path: path.join('_audit', 'ui2', `mobile-390-${r.name}.png`), fullPage: false });
    }
  }
  await ctx.close();
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf8');
console.log(`→ ${OUT}`);
await browser.close();
