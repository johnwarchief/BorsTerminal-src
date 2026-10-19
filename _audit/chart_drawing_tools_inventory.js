// _audit/chart_drawing_tools_inventory.js — نامۀِ ابزارهایِ ترسیم: کدام درِ رابط دیده می‌شود؟
//
// پرسشِ مرحلۀِ ۳/۴ مأموریت: «ابزارهایی که هنوز وجود ندارند یا ازِ نوارِ ابزار قابلِ
// دسترسی نیستند، کامل گزارش نشوند». این هارنس هرِ شیارِ نوارِ چپ را بازشماری
// می‌کند، فلشِ زیرابزارش را می‌زند و نامِ گزینه‌هایی که واقعاً درِ DOM می‌آیند را
// ثبت می‌کند. خروجی = نامۀِ دسترسی، نه نامۀِ کد.
//
// اجرا: node _audit/chart_drawing_tools_inventory.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_drawing_tools_inventory.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const SLOTS = () => [...document.querySelectorAll('.nn-left-toolbar .tv-slot-wrapper')].map((w) => {
  const item = w.querySelector('.tool-item');
  const arrow = w.querySelector('[title="مشاهده زیرابزارها"]');
  const r = (item || w).getBoundingClientRect();
  return { title: item ? item.getAttribute('title') : null,
           hasArrow: !!arrow, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
});

const FLYOUT = () => [...document.querySelectorAll('.nn-left-toolbar [class*="flyout"] *, .nn-left-toolbar [class*="menu"] *, .nn-left-toolbar [class*="item"]')]
  .map((e) => (e.getAttribute('title') || e.textContent || '').replace(/\s+/g, ' ').trim())
  .filter((t) => t && t.length > 1 && t.length < 34);

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-tools-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
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

  const rep = { ranAt: new Date().toISOString(), viewport: [1366, 768], rail: [], slots: await page.evaluate(SLOTS) };
  rep.otherRailButtons = await page.evaluate(() => [...document.querySelectorAll('.nn-left-toolbar button')]
    .map((b) => b.getAttribute('title')).filter(Boolean));

  const n = rep.slots.length;
  for (let i = 0; i < n; i++) {
    const arrows = page.locator('.nn-left-toolbar .tv-slot-wrapper [title="مشاهده زیرابزارها"]');
    if (!(await arrows.count().catch(() => 0))) break;
    await arrows.nth(i).click({ timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(600);
    const items = await page.evaluate(FLYOUT);
    const uniq = [...new Set(items)];
    rep.rail.push({ slot: i, defaultTitle: rep.slots[i] && rep.slots[i].title, items: uniq.slice(0, 14) });
    await page.keyboard.press('Escape').catch(() => {});
    await page.mouse.click(700, 400).catch(() => {});   // بستنِ فلایاوت با کلیک رویِ بوم
    await page.waitForTimeout(400);
  }
  const all = new Set();
  for (const r of rep.rail) { (r.items || []).forEach((t) => all.add(t)); (r.defaultTitle ? [r.defaultTitle] : []).forEach((t) => all.add(t)); }
  (rep.otherRailButtons || []).forEach((t) => all.add(t));
  rep.inventory = [...all].sort();
  rep.titleIndex = await page.evaluate(() => [...document.querySelectorAll('.nn-left-toolbar [title]')]
    .map((e) => e.getAttribute('title')));
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('slots:', rep.slots.length, '| rail buttons:', (rep.otherRailButtons || []).length);
  for (const r of rep.rail) console.log(`  شیار ${r.slot} «${r.defaultTitle}» → ${JSON.stringify(r.items)}`);
  console.log('other rail:', JSON.stringify(rep.otherRailButtons));
  console.log('inventory (' + rep.inventory.length + '):', JSON.stringify(rep.inventory));
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
