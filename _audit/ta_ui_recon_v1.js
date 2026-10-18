// _audit/ta_ui_recon_v1.js -- شناساییِ ساختارِ DOM درِ رابطِ واقعیِ رهاورد (فقط خواندنی)
// خروجی: فهرستِ ابزارهایِ ترسیم، آیتم‌هایِ منوی اندیکاتور، و درخواستهایِ دادۀ نمودار.
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright-core'));

const ROOT = path.resolve(__dirname, '..');
const PROFILE = path.join(os.tmpdir(), 'bors-ta-probe-profile');
const EDGE = process.env.TA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const INS = { فولاد: '46348559193224090' };

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    executablePath: EDGE, headless: true, viewport: { width: 1600, height: 900 }, locale: 'fa-IR',
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  const net = [];
  page.on('response', (r) => {
    const u = r.url();
    if (/prices|candle|indicator|technical|data\//.test(u)) net.push({ url: u.slice(0, 140), status: r.status(), bytes: Number(r.headers()['content-length'] || 0) });
  });
  const sym = Object.keys(INS)[0];
  await page.goto(`https://tradersarena.ir/${INS[sym]}/chart/price`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(7000);

  const recon = await page.evaluate(() => {
    const txt = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim();
    const q = (s) => Array.from(document.querySelectorAll(s));
    const bar = document.querySelector('.technical-chart-drawing-toolbar, #hexa');
    const kids = bar ? Array.from(bar.querySelectorAll('*')) : [];
    const toolish = kids.filter((e) => (e.tagName === 'BUTTON' || e.tagName === 'IMG' || e.tagName === 'I' || e.tagName === 'SVG' || (e.className && String(e.className).match(/tool|item|btn|icon/i))));
    return {
      toolbarClass: bar ? String(bar.className) + '#' + (bar.id || '') : null,
      toolbarChildCount: bar ? bar.children.length : 0,
      tools: toolish.slice(0, 90).map((e) => ({
        tag: e.tagName,
        cls: String(e.className).slice(0, 70),
        title: e.getAttribute('title') || e.getAttribute('data-title') || e.getAttribute('aria-label') || '',
        id: e.id || '',
        rect: (() => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })(),
      })),
      topMenu: q('nav a, .menu a, [class*="menu"] button, header button').map(txt).filter((s) => s && s.length < 30).slice(0, 40),
      canvasCount: q('canvas').length,
      legendTexts: q('[class*="legend" i], [class*="indicator" i] ').map(txt).filter((s) => s && s.length < 90).slice(0, 20),
      scriptSrcs: q('script[src]').map((s) => s.getAttribute('src')).filter((s) => /technical|chart|drawing|indicator/i.test(s)),
    };
  });
  console.log('toolbar:', recon.toolbarClass, 'children:', recon.toolbarChildCount, 'canvas:', recon.canvasCount);
  console.log('tools (first 40):');
  recon.tools.slice(0, 40).forEach((t) => console.log(`  ${t.tag} ${t.cls} title="${t.title}" id=${t.id} rect=${t.rect}`));
  console.log('topMenu:', recon.topMenu.join(' | '));
  console.log('legend:', recon.legendTexts.join(' || '));
  console.log('scripts:', recon.scriptSrcs.join(', '));
  console.log('net:', JSON.stringify(net.slice(0, 12), null, 1));
  fs.writeFileSync(path.join(ROOT, '_audit', 'ta_ui_recon.json'), JSON.stringify({ recon, net }, null, 1));
  await ctx.close();
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
