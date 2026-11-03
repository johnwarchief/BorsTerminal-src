import { createRequire } from 'node:module';
import { join } from 'node:path';
const HERE = import.meta.dirname;
const { chromium } = createRequire(join(HERE, '../../frontend/index.js'))('playwright-core');
const b = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
for (const pinned of [true, false]) {
  const ctx = await b.newContext();
  if (pinned) await ctx.clock.install({ time: new Date('2026-10-17T10:00:00+03:30') });
  await ctx.addInitScript(() => {
    const w = window as any;
    w.__probe = { init_date: Date.now(), init_tl: document.timeline?.currentTime ?? null };
    document.addEventListener('DOMContentLoaded', () => { w.__probe.dcl_wall = Date.now(); w.__probe.dcl_tl = document.timeline?.currentTime ?? null; }, { once: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries() as any[]) Object.assign(w.__probe, { nav_dcl_s: e.domContentLoadedEventStart, nav_dcl_e: e.domContentLoadedEventEnd }); })
      .observe({ type: 'navigation', buffered: true });
  });
  const page = await ctx.newPage();
  for (const i of [0, 1]) {
    const realNav = Date.now();
    if (i === 0) await page.goto('http://127.0.0.1:8020/'); else await page.reload();
    await page.waitForTimeout(2500);
    const r = await page.evaluate(() => ({ ...(window as any).__probe, now_tl: document.timeline?.currentTime ?? null, now_date: Date.now(), now_origin: performance.timeOrigin }));
    const anchorDcl = r.dcl_wall - r.nav_dcl_s;
    console.log(pinned ? 'PIN' : 'LIVE', i, JSON.stringify(r),
      '| anchorDcl', anchorDcl, '| anchorTl(now)', r.now_date - r.now_tl,
      '| realNav(+off)', pinned ? realNav + (r.now_date - Date.now()) : realNav);
  }
  await ctx.close();
}
await b.close();
