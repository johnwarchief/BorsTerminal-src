// اسکرولِ برنامه‌ای رویِ جدولِ بازار، بی‌ساعتِ میخکوب: فاصلهٔ فریم‌هایِ rAF و long-animation-frame
// (اسکرولِ scrollTop رویِ نخِ اصلی اجرا می‌شود؛ ورودیِ چرخِ موشِ واقعی نیست).
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';
const HERE = import.meta.dirname;
const argv = process.argv.slice(2);
const arg = (n: string, d = '') => { const i = argv.indexOf(`--${n}`); return i >= 0 ? argv[i + 1] : d; };
const BASE = arg('url', 'http://127.0.0.1:8020');
const OUT = arg('out');
const { chromium } = createRequire(join(HERE, '../../frontend/index.js'))('playwright-core');
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const ctx = await b.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
// ردیف‌هایِ تابلو گریدِ مجازی‌اند (همان شمارندهٔ پایشگر)، نه tbody tr
const rows = await page.waitForFunction(() => document.querySelectorAll('[data-testid^="watch-star-"]').length > 5, null, { timeout: 90000 })
  .then(() => true).catch(() => false);
await page.waitForTimeout(3000);
const r = await page.evaluate(async () => {
  let el = document.querySelector('[data-testid^="watch-star-"]') as HTMLElement | null;
  while (el && !(el.scrollHeight > el.clientHeight + 40 && /(auto|scroll)/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
  const target = el ?? undefined;
  if (!target) return { scrolled: false };
  const rowsBefore = document.querySelectorAll('[data-testid^="watch-star-"]').length;
  const loaf: number[] = [];
  let po: PerformanceObserver | null = null;
  try {
    po = new PerformanceObserver((l) => { for (const e of l.getEntries() as any[]) loaf.push(Math.round(e.blockingDuration ?? e.duration)); });
    po.observe({ type: 'long-animation-frame' as any });
  } catch { /* بی‌LoAF */ }
  const deltas: number[] = [];
  const max = target.scrollHeight - target.clientHeight;
  let dir = 1, last = performance.now(), passes = 0;
  const t0 = last;
  await new Promise<void>((done) => {
    const step = (ts: number) => {
      deltas.push(ts - last); last = ts;
      target.scrollTop += dir * 60;
      if (target.scrollTop >= max - 1) { dir = -1; passes++; }
      else if (target.scrollTop <= 0 && dir < 0) { dir = 1; passes++; }
      if (ts - t0 < 6000) requestAnimationFrame(step); else done();
    };
    requestAnimationFrame(step);
  });
  po?.disconnect();
  const s = deltas.slice(1).sort((a, b) => a - b);
  const q = (p: number) => Math.round(s[Math.min(s.length - 1, Math.floor((s.length - 1) * p))] * 10) / 10;
  return { scrolled: true, target: `${target.tagName}.${String(target.className).slice(0, 40)}`, rows_dom: rowsBefore,
    scroll_px: max, passes, frames: s.length, frame_ms_median: q(0.5), frame_ms_p95: q(0.95),
    frame_ms_max: Math.round(s[s.length - 1]), frames_over_50ms: s.filter((x) => x > 50).length,
    loaf_n: loaf.length, loaf_blocking_ms_total: loaf.reduce((a, x) => a + x, 0) };
});
writeFileSync(OUT, JSON.stringify({ rows_ready: rows, ...r }, null, 1));
console.log(JSON.stringify(r));
await b.close();
