// _audit/chart_toolbar_fix_experiment.js — کدام قاعدهٔ CSS همپوشانی را واقعاً پاک می‌کند؟
//
// پیش ازِ نوشتنِ هر CSS، هرِ گزینه درِ همانِ صفحۀِ زنده آزمایش می‌شود و شمارۀ
// همپوشانی/برچسبِ بریده پس ازِ هرِ گزینه گزارش می‌شود. چیزی به کد نمی‌رود که
// اندازه‌گیری نشده باشد.
// اجرا: node _audit/chart_toolbar_fix_experiment.js
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));
const ROOT = path.join(__dirname, '..');
const OUT = path.join(ROOT, '_audit', 'chart_toolbar_fix_experiment.json');
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const SYM = 'فولاد';

const MEASURE = () => {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const visible = (b) => {
    if (b.closest('[hidden],[aria-hidden="true"]')) return false;
    const cs = getComputedStyle(b);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
    if (!b.offsetParent && cs.position !== 'fixed') return false;
    const r = b.getBoundingClientRect();
    return r.width > 2 && r.height > 2 && r.left >= -1 && r.top >= -1;
  };
  const ctrls = [...document.querySelectorAll('button,[role="button"],[role="combobox"],select')].filter(visible).map((b) => {
    const r = b.getBoundingClientRect();
    return { label: norm(b.getAttribute('title') || b.getAttribute('aria-label') || b.textContent).slice(0, 26),
             x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
             clipped: b.scrollWidth > b.clientWidth + 1, over: b.scrollWidth - b.clientWidth };
  });
  let overlaps = 0; const pairs = [];
  for (let i = 0; i < ctrls.length; i++) {
    for (let j = i + 1; j < ctrls.length; j++) {
      const a = ctrls[i], b = ctrls[j];
      if (Math.abs(a.y - b.y) > Math.max(a.h, b.h)) continue;
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 2 && oy > 2) { overlaps++; pairs.push(`${a.label} × ${b.label} (${ox}x${oy})`); }
    }
  }
  const clipped = ctrls.filter((c) => c.clipped);
  // ظرف‌هایی که فرزندشان ازِ جعبه‌شان بیرون زده (علتِ اصلیِ همپوشانی)
  const overflowing = [];
  for (const b of ctrls) {
    const p = b.parentElement;
    if (!p) continue;
    const pr = p.getBoundingClientRect(), br = b.getBoundingClientRect();
    if (br.width > pr.width + 2 || br.left < pr.left - 2 || br.right > pr.right + 2) {
      overflowing.push({ child: b.label, childBox: `${Math.round(br.left)}+${Math.round(br.width)}`,
                         parent: String(p.className).split(' ')[0] || p.tagName,
                         parentBox: `${Math.round(pr.left)}+${Math.round(pr.width)}` });
    }
  }
  const tb = document.querySelector('.nn-top-toolbar');
  return { controls: ctrls.length, overlaps, pairs: pairs.slice(0, 6), clipped: clipped.length,
           clippedLabels: clipped.map((c) => `${c.label}+${c.over}`).slice(0, 6),
           overflowingParents: overflowing.length, overflowSamples: overflowing.slice(0, 5),
           toolbarW: tb ? Math.round(tb.getBoundingClientRect().width) : null,
           toolbarScrollW: tb ? tb.scrollWidth : null };
};

const RULES = [
  ['baseline', ''],
  ['R6 groups+children shrink0', '.nn-top-toolbar>.nn-toolbar-group{flex-shrink:0}'
    + '.nn-top-toolbar .nn-toolbar-group>*{flex-shrink:0}'],
  ['R7 R6 + min-width:max-content', '.nn-top-toolbar>.nn-toolbar-group{flex-shrink:0;min-width:max-content}'
    + '.nn-top-toolbar .nn-toolbar-group>*{flex-shrink:0;min-width:max-content}'
    + '.nn-top-toolbar .nn-btn{min-width:max-content}'],
  ['R8 wrap to second row', '.nn-top-toolbar{flex-wrap:wrap;height:auto;max-height:none;padding-bottom:4px}'],
  ['R9 R7 + toolbar scrolls', '.nn-top-toolbar>.nn-toolbar-group{flex-shrink:0;min-width:max-content}'
    + '.nn-top-toolbar .nn-toolbar-group>*{flex-shrink:0;min-width:max-content}'
    + '.nn-top-toolbar .nn-btn{min-width:max-content}'
    + '.nn-top-toolbar{overflow-x:auto;flex-wrap:nowrap}'],
];

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-tbfix-')),
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
  await page.waitForTimeout(7000);

  const rep = { ranAt: new Date().toISOString(), viewport: [1366, 768], trials: {} };
  for (const [name, css] of RULES) {
    await page.evaluate((c) => {
      let el = document.getElementById('bors-tbfix');
      if (!el) { el = document.createElement('style'); el.id = 'bors-tbfix'; document.head.appendChild(el); }
      el.textContent = c;
    }, css);
    await page.waitForTimeout(1200);
    rep.trials[name] = await page.evaluate(MEASURE);
    console.log(`${name.padEnd(28)} overlaps=${String(rep.trials[name].overlaps).padStart(2)} clipped=${String(rep.trials[name].clipped).padStart(2)} ` +
      `overflowingParents=${String(rep.trials[name].overflowingParents).padStart(2)} toolbar=${rep.trials[name].toolbarW}/${rep.trials[name].toolbarScrollW}`);
    if (name === 'baseline') console.log('   pairs: ' + JSON.stringify(rep.trials[name].pairs));
  }
  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), 'utf8');
  console.log('written: ' + OUT);
  await ctx.close();
})().catch((e) => { console.error('FAILED: ' + ((e && e.stack) || e)); process.exit(1); });
