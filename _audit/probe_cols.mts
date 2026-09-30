/**
 * _audit/probe_cols.mts -- ستونِ هر سرستون با ستونِ سلولش یکی است؟
 *
 * چشم با اسکرین‌شاتِ مقیاس‌شده قضاوت می‌کند؛ اینجا مرکزِ هر <th> را با مرکزِ
 * <td>ِ هم‌شمارهٔ همان ردیف می‌سنجد و بیشترین اختلافِ پیکسلی را می‌گوید.
 * اجرایِ یک‌بار‌مصرف برایِ ممیزیِ بصریِ قیف:
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types _audit/probe_cols.mts
 */
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) (await imp('src/browser-setup.ts')).ensureChromium();

const WIDTH = Number.parseInt(process.argv[2] ?? '1366', 10);
const browser = await chromium.launch({
  executablePath: CHROME || undefined,
  args: ['--no-sandbox', '--font-render-hinting=none'],
});
const page = await browser.newPage({ viewport: { width: WIDTH, height: 1000 } });
await page.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await page.goto('http://127.0.0.1:8002/#/master', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(16000);

const report = await page.evaluate(() => {
  const cx = (el: Element) => {
    const b = el.getBoundingClientRect();
    return { c: b.left + b.width / 2, w: Math.round(b.width), t: (el.textContent ?? '').trim().slice(0, 14) };
  };
  const out: Record<string, unknown> = {};
  for (const key of ['tape', 'technical', 'fundamental', 'handover']) {
    const sec = document.querySelector(`[data-testid="funnel-stage-${key}"]`);
    if (!sec) {
      out[key] = 'absent';
      continue;
    }
    const tables = Array.from(sec.querySelectorAll('table'));
    out[key] = {
      tables: tables.length,
      sectionH: Math.round(sec.getBoundingClientRect().height),
      rows: sec.querySelectorAll('tbody tr').length,
      // ترازِ سرستون با سلولِ اولِ همان ستون
      misaligned: tables.map((tb) => {
        const th = Array.from(tb.querySelectorAll('thead th'));
        const firstTds = Array.from(tb.querySelectorAll('tbody tr:first-child td'));
        return th.map((h, i) => {
          const a = cx(h);
          const b = firstTds[i] ? cx(firstTds[i]) : null;
          return {
            h: a.t,
            hc: Math.round(a.c),
            hw: a.w,
            cell: b ? { t: b.t, c: Math.round(b.c), w: b.w } : null,
            dx: b ? Math.round(a.c - b.c) : null,
          };
        });
      }),
      // عرضِ ستونِ سرستونِ جدولِ دوم (صفِ سنجیده‌نشده) با اولی یکی است؟
      pendingVsMain:
        tables.length > 1
          ? Array.from(tables[1].querySelectorAll('thead th')).map((h) => Math.round(cx(h).c))
          : null,
      mainCols: tables.length > 1 ? Array.from(tables[0].querySelectorAll('thead th')).map((h) => Math.round(cx(h).c)) : null,
    };
  }
  out.pageH = document.documentElement.scrollHeight;
  out.overflowX = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  return out;
});
console.log(JSON.stringify(report, null, 1));
await browser.close();
