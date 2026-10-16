// tools/ui_dead_space.mjs -- شمارشِ فضایِ مردهٔ صفحۀِ اول (فاز G، بندِ «یکِ ترمینالِ یکپارچه»)
//
// «سرریز صفر» وِ «خطای کنسول صفر» نمی‌گویند صفحه چقدر ازِ ۷۶۸ پیکسلِ ارتفاع را
// بی‌مصرف می‌دهد. دو سنجه:
//  ۱) جعبهٔ بلندِ بی‌متن که حاشیه/پس‌زمینه دارد (پنلی که رندر شده وِ چیزی نشان
//     نمی‌دهد). بومِ چارت، SVG وِ ریلِ باریکِ آیکون «مرده» نیست، پس کنار گذاشته
//     می‌شوند — سنجه‌ای که چارت را خطا بگیرد، درِ گزارش بی‌ارزش است.
//  ۲) بزرگ‌ترین فاصلۀِ عمودیِ بی‌محتوا مابینِ دو بلوکِ دیدنی (همانِ نوارِ خالیِ
//     وسطِ بنرِ «تصمیم استراتژیک»).
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BASE || 'http://127.0.0.1:8010';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const AUTH = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
const USER = (AUTH.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
const PASS = (AUTH.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
const ROUTES = (process.env.ROUTES || 'market,market-status,fundamental,technical,strategy-tree,master,portfolio,watch,notifications').split(',');

const browser = await chromium.launch({ executablePath: EXE, args: ['--force-device-scale-factor=1'] });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 }, locale: 'fa-IR', deviceScaleFactor: 1 });
const page = await ctx.newPage();
await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
if (USER && PASS && await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
  await page.locator('input[type="text"]').first().fill(USER);
  await page.locator('input[type="password"]').first().fill(PASS);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(1800);
}
for (const r of ROUTES) {
  await page.goto(`${BASE}/#/${r}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4200);
  const out = await page.evaluate(() => {
    const VPH = window.innerHeight;
    const painted = [];
    const texts = [];
    for (const el of document.querySelectorAll('main *')) {
      const b = el.getBoundingClientRect();
      if (b.bottom <= 0 || b.top >= VPH || b.width < 60) continue;
      const cs = getComputedStyle(el);
      const hasMedia = !!el.querySelector('canvas,svg,img,video');
      const textLen = (el.innerText || '').trim().length;
      if (el.children.length === 0) {
        if (textLen > 1) texts.push({ top: Math.round(b.top), bottom: Math.round(b.bottom), t: textLen });
        continue;
      }
      const bordered = (parseFloat(cs.borderWidth) || 0) > 0 && cs.borderStyle !== 'none';
      const bg = cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)';
      if (b.height >= 64 && textLen <= 2 && (bordered || bg) && !hasMedia) {
        painted.push({
          h: Math.round(b.height), w: Math.round(b.width), top: Math.round(b.top),
          node: `${el.tagName.toLowerCase()}[${el.getAttribute('data-testid') || ''}].${(el.getAttribute('class') || '').split(' ').slice(0, 3).join('.')}`.slice(0, 88),
        });
      }
    }
    const keep = painted.filter((b, i) => !painted.some((o, j) => j !== i && o.h >= b.h && o.w >= b.w && o.top <= b.top && o.top + o.h >= b.top + b.h));
    // بزرگ‌ترین فاصلۀِ مابینِ دو متنِ دیدنی (رویِ هم‌پوشانی‌ها حساب نمی‌شود: فقطِ شکافِ خالی)
    texts.sort((a, b) => a.top - b.top);
    let gap = 0, gapAt = null;
    let reach = 0;
    for (const t of texts) {
      if (t.top - reach > gap) { gap = t.top - reach; gapAt = reach; }
      reach = Math.max(reach, t.bottom);
    }
    const lastBottom = texts.length ? Math.max(...texts.map((t) => Math.min(t.bottom, VPH))) : 0;
    return {
      deadPx: keep.reduce((a, b) => a + b.h, 0), boxes: keep.slice(0, 5),
      gapPx: Math.round(gap), gapAfter: gapAt == null ? null : Math.round(gapAt),
      lastTextBottom: Math.round(lastBottom),
    };
  });
  console.log(`/${r}: جعبهٔ بی‌محتوا=${out.deadPx}px · بزرگ‌ترین شکاف=${out.gapPx}px (پس ازِ top=${out.gapAfter}) · آخرینِ متن درِ ${out.lastTextBottom}px`);
  for (const b of out.boxes) console.log(`    ${b.h}x${b.w} @top=${b.top}  ${b.node}`);
}
await browser.close();
