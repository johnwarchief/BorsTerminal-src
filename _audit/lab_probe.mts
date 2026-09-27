/**
 * _audit/lab_probe.mts — شاهدِ زندهٔ #208/#210 با Playwrightِ jev-browser
 *
 * دو چیز باید ثابت شود:
 *  ۱) پس از حذفِ باندلِ دوم، تبِ تکنیکالِ واقعی هنوز کندل رسم می‌کند (جوهِ
 *     رنگیِ روی canvas) و خطایِ کنسولی ندارد، و
 *  ۲) engine-lab هر دو موتور را با *یک* داده بالا می‌آورد؛ health و metrik‌های
 *     هر کدام خوانده می‌شود و اگر موتوری بالا نیاید، دلیلش *دیده* می‌شود نه
 *     پنِ خالی (چون رندرِ خالی در مقایسه یعنی «صفر»، و صفرِ جعلی ممنوع).
 *
 * روشِ شمارشِ جوهِ رنگی از tools/jev_chart_probe.mts است: تفاضلِ کانال‌ها > 40
 * روی هر بومِ ≥۴۰px — بدنهٔ کندل و خطوطِ رنگی، بی‌متنِ خاکستری و خطِ شبکه.
 *
 * اجرا (از ریشهٔ مخزن، باEnvِ jev-browser):
 *   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
 *   MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/lab_probe.mts
 */
import { mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = (await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href)) as {
  chromium: typeof import('playwright').chromium;
};

const BASE = process.env.LAB_URL ?? 'http://127.0.0.1:5173';
const EXE = process.env.JEV_CHROME ?? '';
const OUT = '_audit';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  ...(EXE ? { executablePath: EXE } : {}),
  // swiftshader تا WebGL2 در سرِ بی‌GPU هم باشد؛ اگر باز نبود، پنِ FFC دلیلش
  // را خودش می‌گوید (no-webgl2) و این هم یکی از یافته‌های مقایسه است.
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errors: string[] = [];
page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(`console: ${m.text().slice(0, 160)}`);
});

/** شمارشِ بوم‌هایِ جوهِ‌دار در کلِ صفحه یا درونِ یک ظرف (sel = null یعنی کل) */
const inkIn = (sel: string | null) =>
  page.evaluate((s: string | null) => {
    const root: ParentNode = s ? (document.querySelector(s) ?? document) : document;
    const list = Array.from(root.querySelectorAll('canvas'));
    let inky = 0;
    let total = 0;
    for (const cv of list) {
      if (cv.clientWidth < 40 || cv.clientHeight < 40) continue;
      total++;
      const g = cv.getContext('2d', { willReadFrequently: true });
      if (!g) continue;
      let d: Uint8ClampedArray;
      try {
        d = g.getImageData(0, 0, cv.width, cv.height).data;
      } catch {
        continue;
      }
      let ink = 0;
      for (let i = 0; i < d.length; i += 16) {
        if (Math.abs(d[i] - d[i + 1]) > 40 || Math.abs(d[i + 1] - d[i + 2]) > 40) ink++;
      }
      if (ink > 20) inky++;
    }
    return { inky, total };
  }, sel);

const readPane = async (id: string) => {
  const sel = `[data-testid="lab-col-${id}"]`;
  const text = await page
    .locator(sel)
    .innerText()
    .then((t) => t.replace(/\s+/g, ' ').trim().slice(0, 700))
    .catch(() => null);
  if (text == null) return null;
  return { text, ink: await inkIn(sel) };
};

// ── ۱) تبِ تکنیکالِ واقعی، پس از حذفِ باندلِ دوم ─────────────────────────
await page.goto(`${BASE}/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF`, { waitUntil: 'domcontentloaded' });
// صبرِ فعال تا جوهِ رنگی بیاید (vite پس ازِ هر ویرایش دوباره transform می‌کند؛
// صبرِ ثابت یا کرشِ واقعی را نشان می‌دهد یا خودِ ابزار را).
let techInk = { inky: 0, total: 0 };
for (let i = 0; i < 20; i++) {
  await page.waitForTimeout(2000);
  techInk = await inkIn(null);
  if (techInk.inky > 0) break;
}
const technical = {
  url: page.url(),
  canvases: await page.locator('canvas').count(),
  ink: techInk,
  bodyHasCandleError: /کتابخانه چارت بارگذاری نشد|خطای|cannot read/i.test(
    await page.locator('body').innerText(),
  ),
};
await page.screenshot({ path: `${OUT}/lab_technical_after_consolidation.png` });

// ── ۲) آزمایشگاه: دو موتور، یک داده ─────────────────────────────────────
await page.goto(`${BASE}/#/engine-lab`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(18000);
const labBefore = {
  present: await page.locator('[data-testid="engine-lab"]').count(),
  canvases: await page.locator('canvas').count(),
  kline: await readPane('klinecharts'),
  ffc: await readPane('ffc'),
};
// «اندازه‌گیری» هر دو پن در یک لحظه، تا FPSها هم‌زمانِ یکسان داشته باشند
for (const id of ['klinecharts', 'ffc']) {
  const btn = page.locator(`[data-testid="lab-measure-${id}"]`);
  if (await btn.count()) {
    await btn.first().click().catch(() => undefined);
  }
}
await page.waitForTimeout(4200);
const labAfter = {
  kline: await readPane('klinecharts'),
  ffc: await readPane('ffc'),
  compareTable: (
    await page.locator('[data-testid="lab-compare"]').innerText().catch(() => '')
  ).replace(/\s+/g, ' ').slice(0, 900),
};
await page.screenshot({ path: `${OUT}/lab_engines.png`, fullPage: true });

console.log(JSON.stringify({ technical, labBefore, labAfter, errors: errors.slice(0, 12) }, null, 2));
await browser.close();
