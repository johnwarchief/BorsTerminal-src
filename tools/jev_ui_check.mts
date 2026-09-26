/**
 * tools/jev_ui_check.ts — بررسیِ زندهٔ UI با Chromiumِ خودِ پروژهٔ jev-browser
 *
 * چرا این ابزار هست: آزمون‌های jsdom (vitest) متن و رندر را ثابت می‌کنند ولی هیچ‌چیز
 * دربارهٔ چیدمانِ واقعی و مقیاسِ فونت در عرض‌های مختلف. jev-browser یک Chromium
 * ایزولهٔ Playwright می‌دهد؛ اینجا همان مرورگر با viewport های واقعی باز می‌شود،
 * نشستِ محلی با bors_auth_session تزریق می‌گردد (رمز تایپ نمی‌شود — دروازهٔ ورود
 * فقط UI است) و testid ها + استایلِ محاسبه‌شده + بریدگیِ متن اندازه گرفته می‌شوند.
 *
 * هیچ متنی به سرویسِ بیرونی فرستاده نمی‌شود: از این پروژه فقط ensureChromium،
 * observe و executeActions استفاده می‌شود — نه حلقهٔ jev_run (که به Gateway نیاز دارد
 * و کلیدش روی این ماشین نیست).
 *
 *   node --experimental-strip-types tools/jev_ui_check.ts \
 *        --url http://127.0.0.1:8002/ --route '#/' \
 *        --widths 1366,1920 --testids pulse-verdict,pulse-hemat
 */
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const flag = (name: string): boolean => process.argv.includes(`--${name}`);

const BASE = arg('url', 'http://127.0.0.1:8002/');
const ROUTE = arg('route', '#/');
const WIDTHS = (arg('widths', '1366,1920') || '')
  .split(',')
  .map((w) => Number.parseInt(w.trim(), 10))
  .filter((w) => Number.isFinite(w));
const TESTIDS = (arg('testids', '') || '').split(',').map((t) => t.trim()).filter(Boolean);
const OUT = arg('out', '_audit/jev_ui_check.json');
const WAIT_MS = Number.parseInt(arg('wait', '14000'), 10);
const HEIGHT = Number.parseInt(arg('height', '900'), 10);

const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const { observe } = await imp('src/jev-browser.ts');
const { executeActions } = await imp('src/actions.ts');

/**
 * jev-browser همیشه با ensureChromium() مرورگر خودش را نصب می‌کند؛ روی این ماشین
 * نصبِ network-based مسدود است و یک chromiumِ ms-playwright از قبل هست. اگر
 * JEV_CHROME داده شده باشد همان را به کار می‌بریم، وگرنه همان ensureChromium.
 */
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) {
  const { ensureChromium } = await imp('src/browser-setup.ts');
  await ensureChromium();
}

/** دروازهٔ ورودِ محلی: sessionStorage پیش از ناوبری — کلیدِ bors_auth_session */
const AUTH_INIT = () => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* بی‌خطر: پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
};

const PROBE = (ids: string[]) => {
  const out: Record<string, unknown> = {};
  const de = document.documentElement;
  out.viewport = { w: de.clientWidth, h: de.clientHeight };
  out.pageOverflowX = de.scrollWidth - de.clientWidth;
  const cells: Record<string, unknown> = {};
  for (const id of ids) {
    const el = document.querySelector(`[data-testid="${id}"]`);
    if (!el) {
      cells[id] = null;
      continue;
    }
    const cs = getComputedStyle(el);
    // بریدگی: هر متنِ داخلِ element که scrollWidth از عرضِ خودش بیشتر دارد
    const clipped: string[] = [];
    for (const leaf of Array.from(el.querySelectorAll('*'))) {
      const t = (leaf.textContent ?? '').trim();
      if (t && leaf.scrollWidth - leaf.clientWidth > 1 && getComputedStyle(leaf).overflow !== 'visible') {
        clipped.push(`${t.slice(0, 24)}(${leaf.scrollWidth - leaf.clientWidth}px)`);
      }
    }
    const scrollable: string[] = [];
    for (const box of Array.from(el.querySelectorAll('*'))) {
      if (box.scrollWidth - box.clientWidth > 2 && getComputedStyle(box).overflowX !== 'visible') {
        scrollable.push(`${box.className.toString().slice(0, 30)} +${box.scrollWidth - box.clientWidth}px`);
      }
    }
    cells[id] = {
      text: (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 320),
      fontSize: cs.fontSize,
      box: { w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) },
      clipped: clipped.slice(0, 8),
      scrollable: scrollable.slice(0, 6),
    };
  }
  out.testids = cells;
  out.bodyText = (document.body?.innerText ?? '').replace(/\s+/g, ' ').trim().slice(0, 400);
  out.href = location.href;
  return out;
};

const report: Record<string, unknown> = { base: BASE, route: ROUTE, widths: {} };

for (const width of WIDTHS) {
  const browser = await chromium.launch({ headless: !flag('--show'), executablePath: CHROME || undefined });
  const context = await browser.newContext({ viewport: { width, height: HEIGHT } });
  await context.addInitScript(AUTH_INIT);
  const page = await context.newPage();
  const consoleErrors: string[] = [];
  page.on('console', (m: { type: () => string; text: () => string }) => {
    if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200));
  });
  page.on('pageerror', (e: { message: string }) => consoleErrors.push(`pageerror: ${e.message}`.slice(0, 200)));
  await page.goto(`${BASE}${ROUTE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(WAIT_MS);
  // jev-browser: مشاهدهٔ ساختاریافتهٔ DOM (هدف‌های شماره‌دار) + یک اسکرولِ واقعی
  const observation = await observe(page);
  await executeActions(page, [{ type: 'scroll', deltaX: 0, deltaY: 420 } as never], {
    assertUrlAllowed: () => undefined,
  });
  await page.waitForTimeout(500);
  const shot = OUT.replace(/\.json$/, `-${width}.png`);
  mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
  await page.screenshot({ path: shot, fullPage: false });
  report.widths![width] = {
    ...(await page.evaluate(PROBE, TESTIDS)),
    targets: observation?.targets?.length ?? 0,
    consoleErrors: consoleErrors.slice(0, 12),
    screenshot: shot,
  };
  await browser.close();
}

writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
console.log(JSON.stringify(report, null, 1));
