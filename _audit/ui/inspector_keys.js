// _audit/ui/inspector_keys.js — داورِ نماد باِ کیبورد بسته می‌شود؟ (یادداشتِ finding c)
//
// اینِ پرسش دوِ جوابِ جدا دارد وِ هرِ دو باید درِ مرورگر سنجیده شوند:
//  · «Escape می‌بندد؟» — اگرِ نبندد، دلیلش درِ کد هست یا ایراد؟ (Esc درِ چارت
//    «لغوِ رسم» است: KLineChartWrapper.tsx:866 وِ درِ پالتِ فرمان: CommandPalette.tsx:196)
//  · «باِ کیبورد قابلِ بستن هست؟» — همانِ چیزی که WCAG 2.1.2 می‌خواهد: باِ Tab
//    بهِ دکمهٔ «بستنِ پنلِ نماد» می‌رسیم وِ Enter آن را می‌بندد؟
// additionally: پنل درِ ۱۳۶۶ modal نیست (backdrop فقطِ زیرِ lg) ⇒ صفحه باید
// درِ حالتِ بازِ پنل هم کار کند (ناوبری باِ کلیک).
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/inspector_keys.js
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

const STATE = () => {
  const aside = document.querySelector('aside[data-shell="inspector"]');
  const tabs = document.querySelector('[data-testid="inspector-tabs"]');
  const closeBtn = [...(aside ? aside.querySelectorAll('button') : [])].find((b) => b.getAttribute('aria-label') === 'بستن پنل نماد');
  const a = aside ? aside.getBoundingClientRect() : null;
  const cb = closeBtn ? closeBtn.getBoundingClientRect() : null;
  return {
    exists: !!aside,
    ariaHidden: aside ? aside.getAttribute('aria-hidden') : null,
    inert: aside ? aside.hasAttribute('inert') : null,
    box: a ? [Math.round(a.x), Math.round(a.y), Math.round(a.width), Math.round(a.height)] : null,
    onScreen: !!a && a.right > 1 && a.left < innerWidth - 1,
    closeBtn: cb ? { box: [Math.round(cb.x), Math.round(cb.y), Math.round(cb.width), Math.round(cb.height)], label: closeBtn.getAttribute('aria-label') } : null,
    focus: document.activeElement ? (document.activeElement.getAttribute('data-testid') || document.activeElement.tagName + '.' + String(document.activeElement.className || '').split(/\s+/)[0] + '«' + String(document.activeElement.textContent || '').trim().slice(0, 12) + '»') : null,
    focusInside: !!aside && aside.contains(document.activeElement),
    backdropVisible: (() => { const d = document.querySelector('div[aria-hidden="true"].fixed.inset-0'); if (!d) return null; const cs = getComputedStyle(d); return Number(cs.opacity) > 0 && cs.pointerEvents !== 'none'; })(),
    tabsText: tabs ? String(tabs.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40) : null,
    hash: location.hash,
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + String(e).slice(0, 120)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 120)); });
  const log = [];
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2500);
  }
  await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(1200);

  // ۱) باِ کلیکِ ردیف، پنل باز می‌شود
  await page.locator('[data-testid="tape-row"]').first().click();
  await page.waitForTimeout(1500);
  const opened = await page.evaluate(STATE);
  log.push({ step: 'open-by-row-click', ...opened });
  console.log('1) باز شدن باِ ردیف:', JSON.stringify(opened));

  // ۲) Escape چه می‌کند؟
  await page.keyboard.press('Escape');
  await page.waitForTimeout(900);
  const afterEsc = await page.evaluate(STATE);
  log.push({ step: 'after-Escape', ...afterEsc });
  console.log('2) پس ازِ Escape:', JSON.stringify(afterEsc));

  // ۳) کیبورد: دکمهٔ بستن داخلِ پنل کجاست وِ چندِ Tab فاصله دارد؟
  //    (پنل درِ DOM آخرِ پوسته است ⇒ درِ /market با ~۱۴۰ کنترلِ دیدنی، فاصلۀِ
  //    Tab زیاد است؛ اینِ عدد خودش شاهدِ «رساییِ کیبورد» است، نه حدس)
  const tabbableBefore = await page.evaluate(() => document.querySelectorAll('a[href],button:not([disabled]),input:not([type=hidden]),select,[tabindex]:not([tabindex="-1"])').length);
  const tabbableBeforePanel = await page.evaluate(() => {
    const aside = document.querySelector('aside[data-shell="inspector"]');
    let n = 0;
    for (const el of document.querySelectorAll('a[href],button:not([disabled]),input:not([type=hidden]),select,[tabindex]:not([tabindex="-1"])')) {
      if (el === aside || (aside && aside.contains(el))) break;
      n += 1;
    }
    return n;
  });
  await page.evaluate(() => {
    const aside = document.querySelector('aside[data-shell="inspector"]');
    const b = [...aside.querySelectorAll('button')].find((x) => x.getAttribute('aria-label') === 'بستن پنل نماد');
    b.focus();
  });
  const atCloseBtn = await page.evaluate(STATE);
  log.push({ step: 'tab-distance', tabbableBefore, tabbableBeforePanel, ...atCloseBtn });
  console.log(`3) پیش ازِ پنل ${tabbableBeforePanel} کنترلِ tabbable هست (کلِ صفحه ${tabbableBefore}); focus حالا رویِ دکمهٔ بستن: «${atCloseBtn.focus}» داخلِ پنل=${atCloseBtn.focusInside} اندازه=${JSON.stringify(atCloseBtn.closeBtn)}`);

  // ۴) Esc باِ فوکوسِ *داخلِ* پنل آن را می‌بندد؟ (رفتارِ افزوده‌شده)
  await page.keyboard.press('Escape');
  await page.waitForTimeout(1000);
  const afterEscInside = await page.evaluate(STATE);
  log.push({ step: 'after-Escape-inside-panel', ...afterEscInside });
  console.log('4) Esc باِ فوکوسِ داخلِ پنل → بسته شد؟', afterEscInside.onScreen === false ? 'بله' : 'نه', JSON.stringify(afterEscInside).slice(0, 220));

  // ۵) پنلِ بازِ صفحه را قفل نمی‌کند: باِ پنلِ باز ناوبری می‌کنیم
  await page.locator('[data-testid="tape-row"]').nth(2).click();
  await page.waitForTimeout(1200);
  const reopened = await page.evaluate(STATE);
  await page.locator('a[href*="technical"], [data-testid="nav-technical"], nav a').first().click({ timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(1800);
  const afterNav = await page.evaluate(STATE);
  log.push({ step: 'navigate-with-panel-open', reopened, afterNav });
  console.log(`5) ناوبری باِ پنلِ باز: hash=${afterNav.hash} پنل‌باز=${afterNav.onScreen} خطا=${errs.length}`);

  fs.writeFileSync(path.join(REPO, '_audit', 'ui', 'INSPECTOR_KEYS.json'), JSON.stringify({ ranAt: new Date().toISOString(), log, errors: errs }, null, 1));
  console.log('\nwrote _audit/ui/INSPECTOR_KEYS.json  errors=' + errs.length);
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
