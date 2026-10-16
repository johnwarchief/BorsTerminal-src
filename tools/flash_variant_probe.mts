/** tools/flash_variant_probe.mts — اثباتِ زندهٔ «آبی فقط در دیده‌بان، جهت‌دار در بقیه»
 *   ۱) دیدۀ‌بان (WatchTable): فلاشِ بی‌جهتِ آبی رویِ خودِ عدد (flash-neutral)، بی‌جعبه.
 *   ۲) تابلو (TapeTable): فلاشِ جهت‌دارِ پس‌زمینه (flash-up سبز) — و هیچ flash-neutral نیست.
 *   (بدونِ `as`/`!` درونِ evaluate تا strip-types گره نزند؛ آن کد درِ مرورگر می‌دود.)
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n: string, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/$/, '');
const OUT = arg('out', '_audit/flash/variant');
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.setItem('bors-portfolio-watch', JSON.stringify(['ویستا', 'سایپا', 'آروند', 'سیملاز', 'پتروپاک']));
});
const page = await ctx.newPage();

const rgb = (s: string) => (String(s).match(/\d+/g) || []).slice(0, 3).map(Number).join(',');
const isBlue = (c: string) => { const p = c.split(',').map(Number); return p.length === 3 && p[2] > 150 && p[2] > p[0] + 30 && p[2] > p[1] + 20; };

// ── دیدۀ‌بان ────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/#/watch`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="watch-table"] .num.inline-block', { timeout: 60000 });
await page.waitForTimeout(2000);
const watch = await page.evaluate(() => {
  const cells = Array.from(document.querySelectorAll('[data-testid="watch-table"] .num.inline-block'));
  const neutral = cells.find((c) => !c.classList.contains('rounded'));
  // --accent-blue خام ممکن است hex/oklch باشد؛ آن را از یک عنصرِ زنده به rgbِ حل‌شده می‌بریم
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent-blue)';
  document.body.appendChild(probe);
  const accentResolved = getComputedStyle(probe).color;
  probe.remove();
  const anyRounded = cells.some((c) => c.classList.contains('rounded'));
  if (!neutral) return { error: 'no neutral cell', accentResolved, hasRounded: anyRounded };
  const restColor = getComputedStyle(neutral).color;
  neutral.style.setProperty('--flash-rest', restColor);
  neutral.classList.remove('flash-neutral');
  void neutral.offsetWidth;
  neutral.classList.add('flash-neutral');
  const anims = neutral.getAnimations();
  let peakColor = '', endColor = '', dur = 0;
  if (anims.length) {
    const a = anims[0];
    const d = a.effect.getComputedTiming().duration || 750;
    dur = d;
    a.pause();
    a.currentTime = 0; peakColor = getComputedStyle(neutral).color;
    a.currentTime = d; endColor = getComputedStyle(neutral).color;
    a.currentTime = 0; // رویِ اوجِ آبی متوقف می‌ماند تا اسکرین‌شاتِ رنگِ فلاش گرفته شود
    neutral.setAttribute('data-flash-probe', '1');
  }
  return { accentResolved, restColor, peakColor, endColor, dur, hasRoundedCell: anyRounded };
});
const shotWatch = `${OUT}-watch.jpeg`;
await page.screenshot({ path: shotWatch, type: 'jpeg', quality: 90, clip: { x: 8, y: 116, width: 1160, height: 168 } } as any);
// خودِ خانۀِ فلاش‌خورده را در بزرگ‌نماییِ ۳× می‌گیریم تا آبیِ عدد بی‌ابهام دیده شود
await page.emulateMedia({ reducedMotion: 'no-preference' });
const cellLoc = page.locator('[data-flash-probe="1"]');
if (await cellLoc.count()) {
  const box = await cellLoc.boundingBox();
  if (box) await page.screenshot({ path: `${OUT}-cell.png`, clip: { x: box.x - 6, y: box.y - 6, width: box.width + 12, height: box.height + 12 } });
}

// ── تابلو ───────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.num.inline-block.rounded', { timeout: 60000 });
await page.waitForTimeout(2000);
const board = await page.evaluate(() => {
  const cell = document.querySelector('.num.inline-block.rounded');
  const neutralCount = document.querySelectorAll('.flash-neutral').length;
  if (!cell) return { error: 'no market cell', neutralCount };
  cell.classList.remove('flash-up', 'flash-down');
  void cell.offsetWidth;
  cell.classList.add('flash-up');
  const anims = cell.getAnimations();
  let bg = '';
  if (anims.length) {
    const a = anims[0];
    const d = a.effect.getComputedTiming().duration || 1600;
    a.pause(); a.currentTime = 0.12 * d; bg = getComputedStyle(cell).backgroundColor; a.cancel();
  }
  return { bg, neutralCount };
});
const shotBoard = `${OUT}-board.jpeg`;
await page.screenshot({ path: shotBoard, type: 'jpeg', quality: 72 });

const bluePeak = watch.peakColor || '';
const blueAccent = watch.accentResolved || '';
const boardBg = rgb(board.bg || '');
const checks: Array<[string, boolean, unknown]> = [
  ['دیده‌بان: فلاشِ بی‌جهت رویِ عدد هست (بدونِ جعبه)', !!watch.peakColor && watch.hasRoundedCell === false, watch],
  ['دیده‌بان: رنگِ اوج == --accent-blue (آبی)، rgbِ حل‌شده', bluePeak !== '' && bluePeak === blueAccent, { peak: bluePeak, accent: blueAccent }],
  ['دیده‌بان: اوجِ آبی واقعاً آبی است', isBlue(rgb(bluePeak)), bluePeak],
  ['دیده‌بان: در پایان به رنگِ عادیِ سلول برمی‌گردد', !!watch.endColor && watch.endColor === watch.restColor, { end: watch.endColor, rest: watch.restColor }],
  ['دیده‌بان: مدتِ فلاش زیرِ یک ثانیه', watch.dur > 0 && watch.dur < 1000, { dur: watch.dur }],
  ['تابلو: فلاشِ جهت‌دارِ پس‌زمینه (سبز، نه آبی)', board.bg && !isBlue(boardBg), { bgRaw: board.bg, bg: boardBg }],
  ['تابلو: هیچ فلاشِ آبیِ neutral درِ تابلو نیست (آبی فقط دیدۀ‌بان)', board.neutralCount === 0, { neutralCount: board.neutralCount }],
];
const failed = checks.filter((x) => !x[1]);
writeFileSync(`${OUT}.json`, JSON.stringify({ base: BASE, watch, board, checks }, null, 1));
for (const c of checks) console.log(`${c[1] ? 'PASS' : 'FAIL'} ${c[0]}${c[1] ? '' : '  ' + JSON.stringify(c[2])}`);
console.log(`watch peak=${watch.peakColor} rest=${watch.restColor} dur=${watch.dur}ms | board bg=${board.bg}`);
await browser.close();
process.exit(failed.length ? 1 : 0);
