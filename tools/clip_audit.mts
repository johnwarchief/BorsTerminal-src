// tools/clip_audit.mts — هر عنصری که محتوایش از کادرش بیرون زده، در هر تب و هر رزولوشن
//
// آدیتِ ریسپانسیو با فهرستِ دستیِ testid ها کامل نیست: چیزی که نمی‌شناسی را
// اندازه نمی‌گیری. این ابزار درم‌کلِ صفحه را می‌پیماید و هر گره‌ای که
// scrollWidth/clientWidth یا scrollHeight/clientHeight اش بیرونِ کادر است و
// overflowِ قابلِ اسکرول ندارد گزارش می‌کند؛ با عرضِ اضافی، کلاسِ خودش، و
// اینکه آیا متنِ بریده‌شده برای کاربر معنا دارد یا نه.
//
//   JEV_CHROME='...' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/clip_audit.mts \
//     --url http://127.0.0.1:5173/ --widths 1180,1366,1920 --out _audit/clip_audit.json
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/clip_audit.json');
const WIDTHS = arg('widths', '1180,1366,1920').split(',').map(Number);
const WAIT = Number(arg('wait', '11000'));

const ROUTES: [string, string][] = [
  ['tape', '#/'],
  ['technical', '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['fundamental', '#/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['masterFunnel', '#/master'],
  ['masterVerdict', '#/master/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['tree', '#/strategy-tree'],
  ['portfolio', '#/portfolio'],
];

const SCAN = () => {
  type Hit = { path: string; cls: string; overX: number; overY: number; text: string; scrollable: boolean };
  const hits: Hit[] = [];
  const pageW = document.documentElement.clientWidth;
  const pageH = document.documentElement.clientHeight;
  const all = Array.from(document.querySelectorAll('body *')) as HTMLElement[];
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 12 || r.height < 8) continue;
    const overX = el.scrollWidth - el.clientWidth;
    const overY = el.scrollHeight - el.clientHeight;
    const ox = cs.overflowX, oy = cs.overflowY;
    const canScrollX = overX > 2 && (ox === 'auto' || ox === 'scroll');
    const canScrollY = overY > 2 && (oy === 'auto' || oy === 'scroll');
    const clippedX = overX > 2 && !canScrollX;
    const clippedY = overY > 2 && !canScrollY;
    if (!clippedX && !clippedY && !canScrollX) continue;
    // فقط چیزی که واقعاً بیرونِ صفحه می‌زند یا متنش بریده می‌شود
    const offscreen = r.right > pageW + 1 || r.bottom > pageH + 1 || r.left < -1;
    if (!clippedX && !clippedY && !offscreen) continue;
    const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent ?? '').trim().length > 0);
    hits.push({
      path: (() => {
        const parts: string[] = [];
        let n: HTMLElement | null = el;
        for (let i = 0; n && i < 3; i++) {
          parts.unshift(n.tagName.toLowerCase() + (n.dataset.testid ? `[${n.dataset.testid}]` : n.id ? `#${n.id}` : ''));
          n = n.parentElement;
        }
        return parts.join(' > ');
      })(),
      cls: (el.className || '').toString().slice(0, 90),
      overX: Math.max(0, clippedX ? overX : 0),
      overY: Math.max(0, clippedY ? overY : 0),
      scrollable: canScrollX || canScrollY,
      text: own ? (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 60) : '',
    });
  }
  // بدترین‌ها اول، و تکراری‌ها (همان کلاس در هر ردیفِ جدول) یکی می‌شوند
  const byKey = new Map<string, Hit & { n: number }>();
  for (const h of hits.sort((a, b) => b.overX + b.overY - (a.overX + a.overY))) {
    const k = h.path + h.cls;
    const prev = byKey.get(k);
    if (prev) prev.n++;
    else byKey.set(k, { ...h, n: 1 });
  }
  return {
    pageOverflowX: document.documentElement.scrollWidth - pageW,
    pageOverflowY: document.documentElement.scrollHeight - pageH,
    hits: Array.from(byKey.values()).slice(0, 14),
  };
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const report: Record<string, unknown> = { base: BASE, widths: {} };
for (const [name, route] of ROUTES) {
  report.widths[name] = {};
  for (const w of WIDTHS) {
    const context = await browser.newContext({ viewport: { width: w, height: 900 } });
    await context.addInitScript(() => {
      try {
        sessionStorage.setItem('bors_auth_session', 'true');
        localStorage.removeItem('bors-symbol');
      } catch {
        /* دروازۀ محلی */
      }
    });
    const page = await context.newPage();
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(WAIT);
    report.widths[name][w] = await page.evaluate(SCAN as never);
    await context.close();
  }
}
await browser.close();
mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');

for (const [name, byW] of Object.entries(report.widths as Record<string, Record<string, { pageOverflowX: number; hits: unknown[] }>>)) {
  for (const [w, v] of Object.entries(byW)) {
    console.log(`${name.padEnd(14)} ${w}  overflowX=${v.pageOverflowX}  problems=${v.hits.length}`);
    for (const h of v.hits.slice(0, 5) as { path: string; overX: number; overY: number; n: number; text: string }[]) {
      console.log(`    ${h.path.slice(0, 62).padEnd(62)} x+${String(h.overX).padStart(4)} y+${String(h.overY).padStart(4)} n=${h.n} ${h.text.slice(0, 34)}`);
    }
  }
}
