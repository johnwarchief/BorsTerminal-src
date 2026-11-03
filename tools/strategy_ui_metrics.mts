// tools/strategy_ui_metrics.mts — اندازه‌گیریِ «قبل/بعد»ی تبِّ استراتژی FTS
//
// فقط اسکرین‌شات کافی نیست: این سنجه عدد می‌دهد — توزیعِ اندازهٔ فونت، متن‌های
// ریزتر از ۱۱px، سرریزِ افقی، هندسۀ کارت‌های چهار مرحله، هم‌پوشانی‌ها، ارتفاع
// کل صفحه، و شمارِ چیپ‌هایِ گرد. خروجی JSON + دو JPEG در _audit/strategy-ui/.
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  || 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:8107/';
const TAG = process.argv[3] || 'before';
const OUT = 'C:/Users/PCMOD/Desktop/_bors-fts-technical/_audit/strategy-ui';
mkdirSync(OUT, { recursive: true });

const { chromium } = await import(pathToFileURL(PKG).href);
const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });

const SIZES = [{ w: 1366, h: 768 }, { w: 1920, h: 1080 }];
const report: Record<string, unknown> = {};

for (const vp of SIZES) {
  const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h },
    deviceScaleFactor: 1 });
  await ctx.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session', 'true'); } catch {} });
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));
  await page.goto(BASE + '#/master', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="fts-funnel-workspace"]', { timeout: 40000 });
  await page.waitForSelector('[data-testid="funnel-counts"]', { timeout: 40000 });
  await page.waitForTimeout(2500);

  const m = await page.evaluate(() => {
    const px = (s: string) => Math.round(parseFloat(s) * 10) / 10;
    const vis = (e: Element) => {
      const r = e.getBoundingClientRect();
      const st = getComputedStyle(e);
      return r.width > 1 && r.height > 1 && st.visibility !== 'hidden' && st.opacity !== '0';
    };
    const all = Array.from(document.querySelectorAll('body *')).filter(vis);
    const fontBuckets: Record<string, number> = {};
    let tiny = 0; let tinyExample = '';
    for (const e of all) {
      const own = Array.from(e.childNodes).some((n) => n.nodeType === 3 && (n.textContent || '').trim());
      if (!own) continue;
      const f = px(getComputedStyle(e).fontSize);
      const k = String(f);
      fontBuckets[k] = (fontBuckets[k] || 0) + 1;
      if (f < 11) { tiny += 1; if (!tinyExample) tinyExample = (e.textContent || '').trim().slice(0, 40); }
    }
    const de = document.documentElement;
    const overflowX = Math.max(0, de.scrollWidth - de.clientWidth);
    const wide = all.filter((e) => e.getBoundingClientRect().right > window.innerWidth + 2)
      .slice(0, 6).map((e) => ({ t: (e.textContent || '').trim().slice(0, 26),
        cls: String(e.className).slice(0, 60) }));
    const stepper = Array.from(document.querySelectorAll(
      '[data-testid="fts-process-stepper"] button, [data-testid="fts-process-stepper"] [role="button"]'));
    const boxes = stepper.map((e) => {
      const r = e.getBoundingClientRect();
      return { label: (e.textContent || '').trim().slice(0, 22),
        x: Math.round(r.x), y: Math.round(r.y),
        w: Math.round(r.width), h: Math.round(r.height),
        font: px(getComputedStyle(e).fontSize) };
    });
    const overlaps: string[] = [];
    for (let i = 0; i < stepper.length; i += 1) {
      for (let j = i + 1; j < stepper.length; j += 1) {
        const a = stepper[i].getBoundingClientRect(); const b = stepper[j].getBoundingClientRect();
        const ow = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const oh = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (ow > 3 && oh > 3) {
          overlaps.push(((stepper[i].textContent || '').trim().slice(0, 12)
            + ' × ' + (stepper[j].textContent || '').trim().slice(0, 12)));
        }
      }
    }
    const chips = all.filter((e) => String(e.className).includes('rounded-full')).length;
    const clickable = all.filter((e) => {
      const r = e.getBoundingClientRect();
      return (e.tagName === 'BUTTON' || e.getAttribute('role') === 'button') && (r.height < 28 || r.width < 60);
    }).length;
    const muted = all.filter((e) => {
      const c = getComputedStyle(e).color;
      return Array.from(e.childNodes).some((n) => n.nodeType === 3 && (n.textContent || '').trim())
        && /115, 121|156, 163|107, 114/.test(c);
    }).length;
    return {
      pageHeightPx: de.scrollHeight,
      viewport: { w: window.innerWidth, h: window.innerHeight },
      overflowXPx: overflowX,
      wideElements: wide,
      fontBuckets,
      tinyTextNodes: tiny,
      tinyExample,
      stepperCount: stepper.length,
      stepperBoxes: boxes,
      stepperOverlaps: overlaps,
      roundedFullElements: chips,
      smallClickTargets: clickable,
      lowContrastNodes: muted,
      workspaceHeightPx: Math.round((document
        .querySelector('[data-testid="fts-funnel-workspace"]')?.getBoundingClientRect().height) || 0),
    };
  });

  const path = OUT + '/' + TAG + '-' + vp.w + 'x' + vp.h + '.jpeg';
  await page.screenshot({ path, fullPage: true, type: 'jpeg', quality: 62 });
  report[vp.w + 'x' + vp.h] = { ...m, shot: path, pageErrors: errs.slice(0, 4) };
  await ctx.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 1));
