// _audit/chart_parity_measure.js — شاهدِ پیکسلیِ چارت درِ دو viewport، با کنترلِ مثبت
//
// اجرا:  node _audit/chart_parity_measure.js            (بک‌اند 8001 + vite 5173 بالا باشند)
// روش:  skills/canvas-chart-live-pixel-check — نقشۀِ قیمت→پیکسل ازِ سطرهایِ رنگیِ تمام‌عرض،
// نه ازِ گسترۀِ بدنهٔ کندل‌ها (دامِ شناخته‌شده). هر نتیجهٔ «تکان نخورد» فقط باِ کنترلِ
// مثبتِ همانِ اجرا اعتبار دارد.
const path = require('path');
const fs = require('fs');
const pw = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.join(__dirname, '..');
const BASE = process.env.BORS_BASE || 'http://localhost:5173';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const SYM = process.env.BORS_SYM || '\u0641\u0648\u0644\u0627\u062f';
const SYM2 = process.env.BORS_SYM2 || '\u0634\u0633\u062a\u0627';
const OUT = path.join(ROOT, '_audit', 'chart_parity_measure.json');
const VIEWPORTS = [[1366, 768], [1600, 900]];
const USER = process.env.BORS_USER || 'admin';
const PASS = process.env.BORS_PASS || 'bors123';

const PROBE = () => {
  const panes = [];
  const byPane = new Map();
  for (const c of document.querySelectorAll('canvas')) {
    const r = c.getBoundingClientRect();
    if (r.width < 60 || r.height < 40) continue;
    const key = Math.round(r.left) + ':' + Math.round(r.top);
    if (!byPane.has(key)) byPane.set(key, []);
    byPane.get(key).push(c);
  }
  for (const [key, list] of byPane) {
    const rect = list[0].getBoundingClientRect();
    const off = document.createElement('canvas');
    off.width = Math.round(rect.width); off.height = Math.round(rect.height);
    const ctx = off.getContext('2d', { willReadFrequently: true });
    for (const c of list) ctx.drawImage(c, 0, 0, off.width, off.height);
    const { data } = ctx.getImageData(0, 0, off.width, off.height);
    const inkRow = new Array(off.height).fill(0);
    for (let y = 0; y < off.height; y++) {
      let n = 0;
      for (let x = 0; x < off.width; x++) {
        const i = (y * off.width + x) * 4;
        const mx = Math.max(data[i], data[i + 1], data[i + 2]);
        const mn = Math.min(data[i], data[i + 1], data[i + 2]);
        if (mx > 60 && (mx - mn) > 40) n++;
      }
      inkRow[y] = n;
    }
    // سطرهایِ تمام‌عرض = نقشۀِ قیمت→پیکسل (قاعدهٔ ۲ مهارت)
    const full = [];
    for (let y = 0; y < off.height; y++) if (inkRow[y] > off.width * 0.9) full.push(y);
    panes.push({ key, w: off.width, h: off.height, canvases: list.length,
                 inkRows: inkRow.reduce((a, b) => a + b, 0), fullWidthRows: full });
  }
  const de = document.documentElement;
  const clipped = [];
  for (const el of document.querySelectorAll('h1,h2,h3,span,p,button,label,th,td,div')) {
    const cs = getComputedStyle(el);
    if (cs.overflow === 'visible' && cs.textOverflow === 'clip') continue;
    if (el.scrollWidth > el.clientWidth + 1 && (el.textContent || '').trim().length > 1) {
      if (cs.overflowX === 'hidden' || cs.textOverflow === 'ellipsis') {
        clipped.push({ tag: el.tagName, cls: (el.className || '').slice(0, 40),
                       sw: el.scrollWidth, cw: el.clientWidth, txt: (el.textContent || '').trim().slice(0, 26) });
      }
    }
  }
  const dpr = window.devicePixelRatio;
  const canvasDpr = [...document.querySelectorAll('canvas')].slice(0, 4)
    .map(c => ({ css: Math.round(c.getBoundingClientRect().width), attr: c.width }));
  return {
    href: location.href,
    innerW: window.innerWidth, innerH: window.innerHeight,
    docScrollW: de.scrollWidth, docClientW: de.clientWidth,
    bodyScrollH: document.body.scrollHeight, bodyClientH: document.body.clientHeight,
    horizontalOverflow: de.scrollWidth > de.clientWidth + 1,
    dpr, canvasDpr, panes, clippedCount: clipped.length, clipped: clipped.slice(0, 8),
    drawKeys: Object.keys(localStorage).filter(k => /draw/i.test(k)),
    settingsKeys: Object.keys(localStorage).filter(k => /fts\.(chart|settings)/i.test(k)),
    passwordGate: !!document.querySelector('input[type=password]'),
  };
};

async function login(page) {
  if (!(await page.evaluate(() => !!document.querySelector('input[type=password]')))) return;
  await page.locator('input[type="text"]').first().fill(USER);
  await page.locator('input[type="password"]').first().fill(PASS);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForTimeout(3500);
}

(async () => {
  const ctx = await pw.chromium.launchPersistentContext(
    fs.mkdtempSync(path.join(require('os').tmpdir(), 'bors-chart-measure-')),
    { executablePath: EXE, viewport: null, args: ['--no-first-run', '--disable-sync'] });
  const page = ctx.pages()[0] || await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 220)); });
  page.on('pageerror', e => errors.push('pageerror: ' + String(e).slice(0, 220)));
  page.on('requestfailed', r => errors.push('requestfailed: ' + r.url().slice(0, 160) + ' :: ' + (r.failure() || {}).errorText));
  page.on('response', r => { if (r.status() >= 400) errors.push('http ' + r.status() + ' ' + r.url().slice(0, 160)); });
  const report = { ranAt: new Date().toISOString(), base: BASE, symbol: SYM, viewports: [], errors };

  for (const [w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    await login(page);
    await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
    await page.waitForFunction(() => document.querySelectorAll('canvas').length > 0, null, { timeout: 45000 });
    await page.waitForTimeout(4000);
    const entry = { viewport: [w, h], baseline: await page.evaluate(PROBE) };
    await page.screenshot({ path: path.join(ROOT, '_audit', `cpm_${w}x${h}_baseline.png`) });

    const rowsOf = (p) => (p.panes[0] || {}).fullWidthRows || [];
    // نقشۀِ قیمت→پیکسل: هشِ نوارِ محورِ قیمت. سطرهایِ تمام‌عرض درِ این تمّا فقط ۲ تا
    // پیدا می‌شدند و درگِ ۷۰۰px هم آن‌ها را تکان نمی‌داد — یعنی سنسور کور، نه چارتِ
    // بی‌حرکت. برچسب‌هایِ محورِ قیمت مستقیماً همان مقیاسند، پس تصویرِ خودِ نوار را هش می‌کنیم.
    const axisStrip = async (name) => {
      // برچسبِ crosshair رویِ محورِ قیمت باِ هر موقعیتِ ماوس عوض می‌شود؛ بی‌بیرون‌بردنِ
      // ماوس، هر «جابه‌جاییِ محور» گزارش‌شده می‌تواند همانِ hover باشد نه مقیاس.
      await page.mouse.move(4, 4);
      await page.waitForTimeout(450);
      const ax = (await page.evaluate(() => {
        const cs = [...document.querySelectorAll('canvas')].map((c, i) => {
          const r = c.getBoundingClientRect();
          return { i, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
        }).filter(r => r.w >= 20 && r.w <= 90 && r.h > 120);
        return cs.sort((a, b) => b.h - a.h)[0] || null;
      }));
      if (!ax) return { found: false };
      const buf = await page.screenshot({ clip: { x: ax.x, y: ax.y, width: ax.w, height: ax.h } });
      return { found: true, pane: ax, sha: require('crypto').createHash('sha256').update(buf).digest('hex').slice(0, 16) };
    };
    const box = await page.locator('canvas').first().boundingBox();
    const cx = box.x + box.width * 0.55, cy = box.y + box.height * 0.5;
    const strip0 = await axisStrip('baseline');
    // کنترلِ منفی: دو گرفتنِ پشتِ سرهم بی‌هیچِ تعامل باید یکسان باشد، وگرنه سنسور نویز دارد
    const stripIdle = await axisStrip('idle-repeat');
    entry.idleRepeat = { a: strip0.sha || null, b: stripIdle.sha || null,
                         stable: !!strip0.found && strip0.sha === stripIdle.sha };
    // کنترلِ مثبت ۱: درگِ کوتاهِ ~۵۰px درِ پن → محور نباید جابه‌جا شود
    await page.mouse.move(cx, cy); await page.mouse.down();
    await page.mouse.move(cx + 50, cy, { steps: 8 }); await page.mouse.up();
    await page.waitForTimeout(1200);
    const stripShort = await axisStrip('short');
    const afterShort = await page.evaluate(PROBE);
    entry.axisStrip = strip0;
    entry.shortDrag = { before: strip0.sha || null, after: stripShort.sha || null,
                        scaleHeld: !!strip0.found && strip0.sha === stripShort.sha,
                        rowsBefore: rowsOf(entry.baseline).length, rowsAfter: rowsOf(afterShort).length };
    // کنترلِ مثبت ۲: کشیدنِ محورِ قیمت باِ ~۲۲۰px → مقیاس باید عوض شود (سازۀِ کور نباشد)
    const ax = strip0.pane || { x: cx - 300, y: cy, w: 60, h: 300 };
    const ay = ax.y + Math.round(ax.h / 2);
    await page.mouse.move(ax.x + Math.round(ax.w / 2), ay); await page.mouse.down();
    await page.mouse.move(ax.x + Math.round(ax.w / 2), ay - 220, { steps: 12 }); await page.mouse.up();
    await page.waitForTimeout(1500);
    const stripLong = await axisStrip('long');
    entry.longDrag = { before: stripShort.sha || null, after: stripLong.sha || null,
                       scaleRechosen: !!stripShort.found && stripShort.sha !== stripLong.sha };
    await page.screenshot({ path: path.join(ROOT, '_audit', `cpm_${w}x${h}_afterdrag.png`) });

    // تغییرِ نماد و بازگشت: باقی‌ماندنِ حالتِ نمادِ قبلی
    await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM2);
    await page.waitForTimeout(5000);
    const other = await page.evaluate(PROBE);
    await page.evaluate((s) => { location.hash = '#/technical/' + encodeURIComponent(s); }, SYM);
    await page.waitForTimeout(5000);
    entry.symbolSwitch = { otherSymbol: SYM2, other: other, back: await page.evaluate(PROBE) };
    report.viewports.push(entry);
  }
  report.errors = errors.slice(0, 20);
  fs.writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
  console.log('written: ' + OUT);
  console.log('console/page errors captured: ' + report.errors.length);
  for (const e of report.errors.slice(0, 6)) console.log('  ' + e.slice(0, 180));
  for (const v of report.viewports) {
    const b = v.baseline;
    console.log('\n== ' + v.viewport.join('x') + ' ==');
    console.log('  panes=' + b.panes.length + ' dpr=' + b.dpr + ' canvasDpr=' + JSON.stringify(b.canvasDpr)
      + ' innerW=' + b.innerW + '/' + b.innerH);
    console.log('  horizontalOverflow=' + b.horizontalOverflow + ' clippedText=' + b.clippedCount
      + ' docScrollW/ClientW=' + b.docScrollW + '/' + b.docClientW);
    console.log('  ink=' + b.panes.map(p => p.inkRows + '/' + p.fullWidthRows.length).join(', '));
    console.log('  positive controls: shortDrag scaleHeld=' + v.shortDrag.scaleHeld
      + ' | longDrag scaleRechosen=' + v.longDrag.scaleRechosen
      + ' (axisStrip found=' + (v.axisStrip.found === true) + ', idleRepeat stable=' + v.idleRepeat.stable + ')');
    for (const c of (b.clipped || [])) console.log('  clipped: ' + c.tag + '.' + c.cls + ' ' + c.sw + '>' + c.cw + ' «' + c.txt + '»');
    console.log('  after symbol switch back: panes=' + v.symbolSwitch.back.panes.length
      + ' clipped=' + v.symbolSwitch.back.clippedCount);
  }
  await ctx.close();
})().catch(e => { console.error('HARNESS FAILED: ' + (e && e.stack || e)); process.exit(1); });
