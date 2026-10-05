// tools/toolbar_reach_probe.mts — نوارِ ابزارِ چارت درِ هر اندازه چندتا کنترلِ
// بیرون‌زده دارد؟ (یادداشتِ دورِ پیشین می‌گفت «دکمهٔ تنظیمات درِ ۱۳۶۶ پنهان است»)
// پاسخِ اندازه‌گیری: درِ 1280/1366/1600/1920 هیچ‌وقت؛ scrollWidth == clientWidth.
//   JEV_CHROME=... MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/toolbar_reach_probe.mts
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(PKG + '/node_modules/playwright/index.mjs').href);
const b = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const out: any = {};
for (const [w, h] of [[1280,720],[1366,768],[1600,900],[1920,1080]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session','true'); });
  const p = await ctx.newPage();
  await p.goto('http://127.0.0.1:8003/#/technical/فولاد', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(10000);
  out[`${w}x${h}`] = await p.evaluate(() => {
    const bar = document.querySelector('.nn-top-toolbar') as HTMLElement | null;
    if (!bar) return { missing: true };
    const kids = Array.from(bar.querySelectorAll('button,[data-testid]')) as HTMLElement[];
    const br = bar.getBoundingClientRect();
    const off = kids.filter(e => { const r = e.getBoundingClientRect();
      return r.width > 0 && (r.right > br.right + 1 || r.left < br.left - 1); })
      .map(e => ({ id: e.dataset.testid || e.getAttribute('title') || e.textContent?.trim().slice(0,16) || e.className.toString().slice(0,20),
                   over: Math.round(Math.max(e.getBoundingClientRect().right - br.right, br.left - e.getBoundingClientRect().left)) }));
    return { scrollW: bar.scrollWidth, clientW: bar.clientWidth, overflowBy: bar.scrollWidth - bar.clientWidth,
             overflowX: getComputedStyle(bar).overflowX, scrollbar: getComputedStyle(bar).scrollbarWidth,
             offscreenControls: off.slice(0, 8), count: off.length };
  });
  // آیا کاربر می‌تواند بدونِ دانستنِ اسکرول، آن دکمه را ببیند؟
  const vis = await p.evaluate(() => {
    const bar = document.querySelector('.nn-top-toolbar') as HTMLElement;
    const btn = bar?.querySelector('[title="تنظیمات چارت"]') as HTMLElement | null;
    if (!btn) return { present: false };
    const r = btn.getBoundingClientRect(), br = bar.getBoundingClientRect();
    return { present: true, inViewport: r.right <= br.right + 1 && r.left >= br.left - 1,
             needsScrollBy: Math.max(0, Math.round(r.right - br.right)), w: Math.round(r.width) };
  });
  out[`${w}x${h}`].settingsBtn = vis;
  await ctx.close();
}
console.log(JSON.stringify(out, null, 1));
await b.close();
