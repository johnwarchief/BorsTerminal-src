// _audit/ui/toolbar_fit.js — سنجشِ نامزد‌هایِ اصلاحِ نوارِ ابزارِ چارت، پیش ازِ touchingِ کد
//
// چرا: درِ 1366×768 نوارِ ابزارِ چارت ۱۵۵۳px محتوا درِ ۹۷۶px جا می‌دهد؛ دو رفتار
// ممکن است و باید باِ عدد انتخاب شوند نه باِ سلیقه:
//   shrink → `flex-shrink:0` (قصدِ اعلام‌شدۀِ CSS: اسکرولِ افقیِ پنهان)
//   wrap   → دوِ سطرِ ۴۰ پیکسلی (همۀِ کنترل‌ها دیدنی، ۴۰px ازِ قدِ چارت کم می‌شود)
// هرِ نامزد + جابه‌جاییِ دوِ اورلیِ شناور (`technical-fts-settings` رویِ نوار،
// `fts-legend-host` رویِ دکمه‌هایِ محورِ قیمت) سنجیده می‌شود: چندِ کنترل گیرِ
// کلیک است، چندِ کنترل بیرونِ viewport است، چقدرِ متن بیرونِ دکمه می‌زند.
// usage: MSYS_NO_PATHCONV=1 node _audit/ui/toolbar_fit.js [--cand=shrink,wrap,wrap+floats] [--pick=1]
const path = require('path');
const fs = require('fs');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));
const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const arg = (n, d) => { const h = process.argv.find((a) => a.startsWith('--' + n + '=')); return h ? h.split('=').slice(1).join('=') : d; };

const CSS = {
  shrink: '.nn-top-toolbar>.nn-toolbar-group,.nn-top-toolbar .nn-btn,.nn-top-toolbar .nn-symbol-badge,.nn-top-toolbar .nn-separator{flex-shrink:0 !important;}',
  wrap: '.nn-top-toolbar{height:auto !important;min-height:40px !important;max-height:none !important;flex-wrap:wrap !important;overflow-x:visible !important;overflow-y:visible !important;row-gap:2px;padding:2px 8px !important;}'
      + '.nn-top-toolbar>.nn-toolbar-group,.nn-top-toolbar .nn-btn,.nn-top-toolbar .nn-symbol-badge,.nn-top-toolbar .nn-separator{flex-shrink:0 !important;}',
  // V2: نوار وِ هرِ گروه هرِ دو سطرِپذیر می‌شوند ⇒ هیچِ کنترلی پشتِ اسکرولِ پنهان نمی‌ماند
  wrapall: '.nn-top-toolbar{height:auto !important;min-height:40px !important;max-height:none !important;flex-wrap:wrap !important;overflow:visible !important;row-gap:2px;column-gap:6px;padding:2px 8px !important;}'
      + '.nn-top-toolbar>.nn-toolbar-group{flex-wrap:wrap !important;flex-shrink:1 !important;min-width:0 !important;}'
      + '.nn-top-toolbar .nn-btn,.nn-top-toolbar .nn-symbol-badge,.nn-top-toolbar .nn-separator{flex-shrink:0 !important;}',
  floats: '[data-testid="technical-fts-settings"]{top:2.85rem !important;}'
        + '[data-testid="fts-legend-host"]{bottom:3.85rem !important;}',
  legend: '[data-testid="fts-legend-host"]{bottom:3.85rem !important;}',
  dock: '[data-testid="technical-fts-settings"]{display:none !important;}',
};

const MEASURE = () => {
  const tb = document.querySelector('.nn-top-toolbar');
  if (!tb) return { missing: true };
  const vw = innerWidth, vh = innerHeight;
  const lab = (el) => (el.getAttribute('data-testid') || el.tagName.toLowerCase() + '.' + String(el.className || '').split(/\s+/)[0]) + '«' + String(el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 14) + '»';
  const inView = (r) => r.width > 1 && r.height > 1 && r.x >= 0 && r.y >= 0 && r.bottom <= vh + 1 && r.right <= vw + 1;
  const btns = [...tb.querySelectorAll('button, [data-testid], .nn-symbol-badge')];
  const tbr = tb.getBoundingClientRect();
  const cont = document.querySelector('.nahayat-negar-container').getBoundingClientRect();
  const scrollable = /(auto|scroll|hidden)/.test(getComputedStyle(tb).overflowX);
  const rows = btns.map((b) => {
    const r = b.getBoundingClientRect();
    const cx = Math.round(r.x + r.width / 2), cy = Math.round(r.y + r.height / 2);
    const hit = cx >= 0 && cy >= 0 && cx <= vw && cy <= vh ? document.elementFromPoint(cx, cy) : null;
    const covered = hit && !(hit === b || b.contains(hit));
    let spill = 0;
    const bb = b.getBoundingClientRect();
    for (const kid of b.querySelectorAll('span,svg')) {
      const kr = kid.getBoundingClientRect();
      spill = Math.max(spill, Math.round(Math.max(0, bb.left - kr.left, kr.right - bb.right)));
    }
    // بیرونِ پنجرۀِ نوار: اگرِ نوار اسکرول‌شدنی باشد «پشتِ اسکرول» (رسیدنی)، وگرنه
    // ظرفِ والد (`overflow:hidden`) آنِ کنترل را می‌بُرد ⇒ غیرقابلِرسیدن
    const outBand = r.right > tbr.right + 1 || r.left < tbr.left - 1 || r.bottom > cont.bottom + 1 || r.top < cont.top - 1;
    return { n: lab(b), box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
             w: Math.round(r.width), need: Math.round(b.scrollWidth), spill, out: outBand,
             state: !inView(r) ? 'OFF-VIEWPORT' : outBand ? (scrollable ? 'BEHIND-SCROLL' : 'CLIPPED-BY-CONTAINER') : covered ? 'COVERED_BY:' + (hit.getAttribute('data-testid') || hit.tagName + '.' + String(hit.className).split(/\s+/)[0]) + '«' + String(hit.textContent || '').trim().slice(0, 10) + '»' : 'ok' };
  });
  // اورلی‌هایِ شناور هم کنترل‌اند: مرکزِ خودشان رویِ خودشان؟
  const floats = ['[data-testid="technical-fts-settings"]', '[data-testid="fts-legend-host"]', '[data-testid="price-axis-buttons"]']
    .map((s) => {
      const el = document.querySelector(s);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const cx = Math.round(r.x + r.width / 2), cy = Math.round(r.y + r.height / 2);
      const hit = document.elementFromPoint(cx, cy);
      const ctl = [...document.querySelectorAll('button,[data-testid]')].filter((c) => !el.contains(c) && !c.contains(el));
      const clash = ctl.filter((c) => { const q = c.getBoundingClientRect(); return q.left < r.right - 1 && q.right > r.left + 1 && q.top < r.bottom - 1 && q.bottom > r.top + 1 && inView(q); });
      return { s, box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
               self: !!hit && (hit === el || el.contains(hit) || hit.contains(el)),
               clash: clash.slice(0, 4).map((c) => lab(c)) };
    }).filter(Boolean);
  const canvas = document.querySelector('.nn-canvas-area');
  const cs = getComputedStyle(tb);
  return {
    applied: { display: cs.display, flexWrap: cs.flexWrap, height: cs.height, maxH: cs.maxHeight, ovX: cs.overflowX, align: cs.alignItems },
    bandH: Math.round(tb.getBoundingClientRect().height),
    canvasH: canvas ? Math.round(canvas.getBoundingClientRect().height) : null,
    chartBottom: Math.round(document.querySelector('.nahayat-negar-container').getBoundingClientRect().bottom),
    clientW: tb.clientWidth, scrollW: tb.scrollWidth, slack: tb.scrollWidth - tb.clientWidth,
    counts: { covered: rows.filter((r) => r.state.startsWith('COVERED')).length,
              behind: rows.filter((r) => r.state === 'BEHIND-SCROLL').length,
              clipped: rows.filter((r) => r.state === 'CLIPPED-BY-CONTAINER').length,
              off: rows.filter((r) => r.state === 'OFF-VIEWPORT').length,
              spill: rows.filter((r) => r.spill > 1).length, total: rows.length },
    rows: rows.filter((r) => r.state !== 'ok' || r.spill > 1),
    groups: [...tb.children].map((c) => { const q = c.getBoundingClientRect(); return String(c.className).slice(0, 18) + '[' + [Math.round(q.x), Math.round(q.y), Math.round(q.width), Math.round(q.height)].join(',') + ']'; }),
    all: rows.map((r) => ({ n: r.n, box: r.box })), floats,
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--no-first-run', '--disable-sync', '--force-device-scale-factor=1', '--remote-debugging-port=0'] });
  const ctx = await browser.newContext({ viewport: { width: Number(arg('w', 1366)), height: Number(arg('h', 768)) }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1000);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    await page.locator('input[type="text"]').first().fill((src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('input[type="password"]').first().fill((src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1]);
    await page.locator('button[type="submit"]').first().click();
    await page.waitForTimeout(2200);
  }
  if (arg('pick', '0') === '1') {
    await page.goto(BASE + '/#/market', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelectorAll('[data-testid="tape-row"]').length > 5, null, { timeout: 60000 }).catch(() => {});
    await page.locator('[data-testid="tape-row"]').first().click().catch(() => {});
    await page.waitForTimeout(1200);
  }
  const cands = arg('cand', 'shrink,wrap,wrap+floats').split(',');
  for (const route of arg('routes', '/technical/فولاد').split(',')) {
    await page.goto(BASE + '/#' + route, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!document.querySelector('.nn-top-toolbar'), null, { timeout: 45000 }).catch(() => {});
    await page.waitForTimeout(2500);
    const passes = ['BEFORE', ...cands];
    for (const pass of passes) {
      await page.evaluate(() => {
        document.getElementById('exp-toolbar')?.remove();
        const tb = document.querySelector('.nn-top-toolbar');
        if (tb) { tb.style.cssText = ''; for (const el of tb.querySelectorAll('*')) el.style.flexShrink = ''; }
      });
      const parts = pass.split('+').map((c) => c.trim());
      if (pass !== 'BEFORE') {
        const css = parts.map((c) => CSS[c] || '').join('');
        await page.evaluate((c) => { const s = document.createElement('style'); s.id = 'exp-toolbar'; s.textContent = c; document.head.appendChild(s); }, css);
        // «سطرِپذیر» باید رویِ خودِ ظرف هم بنشیند؛ درِ اینِ صفحه یکِ قاعدۀِ
        // استایل‌شیت باِ !important مقدارِ flex-wrap را عوض نکرد (سنجیده شد) پس
        // برایِ آزمایش، خصوصیت‌هایِ ظرف را inline می‌دهیم (حقِ اولِ بالاتر)
        if (parts.some((p) => p.startsWith('wrap'))) {
          await page.evaluate(() => {
            const tb = document.querySelector('.nn-top-toolbar');
            tb.style.setProperty('height', 'auto', 'important');
            tb.style.setProperty('min-height', '40px', 'important');
            tb.style.setProperty('max-height', 'none', 'important');
            tb.style.setProperty('flex-wrap', 'wrap', 'important');
            tb.style.setProperty('overflow', 'visible', 'important');
            tb.style.setProperty('row-gap', '2px', 'important');
          });
        }
        await page.waitForTimeout(250);
      }
      const m = await page.evaluate(MEASURE);
      if (m.missing) { console.log(`${route} ${pass}: no toolbar`); continue; }
      console.log(`\n== ${route} [${pass}] band=${m.bandH}px canvas=${m.canvasH}px chartBottom=${m.chartBottom} toolbar ${m.clientW}/${m.scrollW} slack=${m.slack}`);
      console.log(`   applied ${JSON.stringify(m.applied)}`);
      console.log(`   controls=${m.counts.total} covered=${m.counts.covered} behind-scroll=${m.counts.behind} clipped=${m.counts.clipped} off-viewport=${m.counts.off} text-spill=${m.counts.spill}`);
      console.log('   groups ' + m.groups.join('  '));
      if (arg('boxes', '0') === '1') {
        for (const r of m.all) console.log(`     ${r.n.padEnd(32)} [${r.box.join(',')}]`);
      }
      for (const r of m.rows.slice(0, 12)) console.log(`     ${r.n.padEnd(30)} w=${String(r.w).padStart(4)} need=${String(r.need).padStart(4)} spill=${String(r.spill).padStart(3)}  ${r.state}`);
      for (const f of m.floats) console.log(`   float ${f.s.padEnd(42)} box=${JSON.stringify(f.box)} self-hit=${f.self} clash=${f.clash.join(' | ') || '-'}`);
    }
    await page.evaluate(() => { document.getElementById('exp-toolbar')?.remove(); });
  }
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('ERR', e); process.exit(1); });
