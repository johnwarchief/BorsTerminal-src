/** tools/perf_raf_render_probe.mts — منشأ rAF تب تکنیکال + ریزشِ رندر به‌ازای دلتا (#3 و #4)
 *  فقط مشاهده؛ هیچ تغییر رفتاری. روی buildِ dev (۵۱۳) تا stackها خوانا باشند.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n, f = '') => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/+$/, '');
const OUT = arg('out', '_audit/perf_raf_render');
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
const page = await ctx.newPage();

// ── #4 منشأ rAF در تب تکنیکال ───────────────────────────────────────────
await page.goto(`${BASE}/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000); // بگذار نمودار بنشیند
await page.evaluate(() => {
  const w = window;
  w.__raf = { n: 0, stacks: {}, frames: [] };
  const orig = w.requestAnimationFrame.bind(w);
  w.requestAnimationFrame = (cb) => {
    w.__raf.n++;
    const st = (new Error().stack || '').split('\n').slice(2, 5)
      .map((s) => (s.trim().match(/at ([\w.$<>]+)/) || [0, '?'])[1]).join(' < ');
    w.__raf.stacks[st] = (w.__raf.stacks[st] || 0) + 1;
    const t = performance.now();
    return orig((ts) => { w.__raf.frames.push(Math.round(ts)); return cb(ts); });
  };
  // آیا نمودار/داده در این بازه عوض می‌شود؟ MutationObserver روی ریشۀ چارت
  w.__mut = { n: 0 };
  const host = document.querySelector('[data-testid*="chart"], canvas')?.closest('div') || document.body;
  new MutationObserver(() => { w.__mut.n++; }).observe(host, { subtree: true, childList: true, attributes: true });
});
await page.waitForTimeout(10000);
const raf = await page.evaluate(() => {
  const r = window.__raf;
  const fr = r.frames; let maxGap = 0; for (let i = 1; i < fr.length; i++) maxGap = Math.max(maxGap, fr[i] - fr[i - 1]);
  const top = Object.entries(r.stacks).sort((a, b) => b[1] - a[1]).slice(0, 5);
  return { requests: r.n, executedFrames: fr.length, windowMs: 10000, maxFrameGapMs: Math.round(maxGap),
           medianFrameGapMs: fr.length > 1 ? (() => { const g = []; for (let i = 1; i < fr.length; i++) g.push(fr[i] - fr[i-1]); g.sort((a,b)=>a-b); return Math.round(g[g.length>>1]); })() : null,
           topStacks: top, chartMutations: window.__mut.n };
});

// ── #3 ریزشِ رندر به‌ازای دلتا در تابلو ──────────────────────────────────
// ⚠ محدودیتِ شناخته‌شده: ردیف‌هایِ TapeTable یک `grid` مجازی‌سازی‌شده‌اند و این
// انتخابگر ردیفِ درست را نمی‌گیرد؛ درِ پنجرۀ بازارِ بسته هم هیچ مقدارِ ردیفی
// عوض نشد (nodesChanged:0). پس «۰ ردیفِ دست‌خورده» را «ریزشِ رندر صفر» نخوان.
// برایِ سنجشِ درست، درِ بازارِ باز و با هدف‌گیریِ کانتینرِ ردیفِ grid تکرار شود.
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.num.inline-block', { timeout: 45000 });
await page.waitForTimeout(2000);
await page.evaluate(() => {
  const w = window;
  w.__dom = { batches: 0, nodes: 0, rowsTouched: {}, t0: Date.now() };
  const list = document.querySelector('[data-testid="tape-list"], [role="rowgroup"], table') || document.body;
  new MutationObserver((muts) => {
    w.__dom.batches++;
    let nodes = 0; const seen = new Set();
    for (const m of muts) {
      nodes += m.addedNodes.length + m.removedNodes.length + (m.type === 'characterData' ? 1 : 0);
      const row = (m.target.nodeType === 1 ? m.target : m.target.parentElement)?.closest('[data-testid^="tape-row"], tr, [role="row"]');
      if (row) { const id = row.getAttribute('data-testid') || row.getAttribute('data-symbol') || row.className; seen.add(id); }
    }
    w.__dom.nodes += nodes;
    seen.forEach((r) => { w.__dom.rowsTouched[r] = (w.__dom.rowsTouched[r] || 0) + 1; });
  }).observe(list, { subtree: true, childList: true, characterData: true, attributes: true });
});
await page.waitForTimeout(30000); // ~۶ دورِ پولینگ ۵ ثانیه‌ای
const dom = await page.evaluate(() => {
  const d = window.__dom; const rows = Object.keys(d.rowsTouched).length;
  return { secs: Math.round((Date.now() - d.t0) / 1000), mutationBatches: d.batches, nodesChanged: d.nodes, distinctRowsTouched: rows, domNodesNow: document.querySelectorAll('*').length };
});

writeFileSync(`${OUT}.json`, JSON.stringify({ base: BASE, raf, dom }, null, 1));
console.log('=== #4 rAF (technical, 10s) ===');
console.log(JSON.stringify(raf, null, 1));
console.log('=== #3 render fan-out (tape, ~30s) ===');
console.log(JSON.stringify(dom, null, 1));
await browser.close();
