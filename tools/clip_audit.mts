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
// --sizes 1280x720,1366x768,1600x900,1920x1080  (قد هم مهم است: چیزی که درِ ۹۰۰
// پیکسل جا می‌شود درِ ۷۶۸ بریده می‌شود؛ --widths فقط برایِ سازگاریِ گذشته مانده)
const SIZES: Array<[number, number]> = (arg('sizes', '')
  ? arg('sizes', '').split(',').map((s: string) => s.split('x').map(Number) as [number, number])
  : arg('widths', '1180,1366,1920').split(',').map((w: string) => [Number(w), 900] as [number, number]));
const WAIT = Number(arg('wait', '11000'));
// تم هم یک حالتِ رندر است: ارقامِ درشتِ «نبض بازار» درِ تمِ روشن با همین
// leading فشرده کشیده می‌شوند؛ بی‌اندازه‌گیریِ هر دو تم، «سالم است» نصفه است.
const THEME = arg('theme', 'dark');

const ROUTES: Array<[string, string, string?]> = [
  ['tape', '#/'],
  ['tape-inspector', '#/', 'inspector'],
  ['technical', '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['technical-dialog', '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF', 'chartSettings'],
  ['fundamental', '#/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['masterFunnel', '#/master'],
  ['masterVerdict', '#/master/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['tree', '#/strategy-tree'],
  ['portfolio', '#/portfolio'],
  ['palette', '#/', 'palette'],
];

/** حالت‌هایی که با یک تعاملِ واقعی باز می‌شوند (دیالوگ/پالت/بازرس) */
const STATE_ACTIONS: Record<string, (p: any) => Promise<string>> = {
  async inspector(p) {
    const row = p.locator('tbody tr').first();
    await row.click({ timeout: 6000 }).catch(() => {});
    await p.waitForTimeout(2500);
    return 'inspector-clicked';
  },
  async palette(p) {
    await p.keyboard.press('Control+k');
    await p.waitForTimeout(1200);
    return 'ctrl+k';
  },
  async chartSettings(p) {
    // «تنظیمات» تنها نیست: نوارِ بالا دکمهٔ «تنظیمات کاربر» دارد و درِ DOM
    // اول می‌آید؛ نامِ کاملِ خودِ دکمه لازم است، وگرنه دیالوگِ چارت باز نمی‌شود
    // و سنجشِ این حالت بی‌آنکه چیزی داد بزند هیچی را اندازه می‌گیرد.
    const btn = p.getByRole('button', { name: 'تنظیمات چارت', exact: true }).first();
    await btn.click({ timeout: 6000 }).catch(() => {});
    await p.waitForTimeout(1500);
    return 'settings-open';
  },
};


/** کنترلِ مثبت: یک عنصرِ عمداً‌بریده‌شده به صفحه اضافه می‌کند. اگر اسکن آن را
 *  نگرفت، «صفرِ مشکل» یعنی سنسور کر است، نه اینکه رابط سالم باشد. */
const PLANT = (kind: string) => {
  const el = document.createElement('div');
  el.dataset.testid = 'clip-canary-' + kind;
  el.style.cssText = 'position:fixed;left:8px;bottom:8px;width:60px;height:18px;z-index:99999;'
    + 'font-size:14px;white-space:nowrap;';
  el.textContent = 'kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk';
  if (kind === 'cut') el.style.overflow = 'hidden';
  else if (kind === 'ellipsized') { el.style.overflow = 'hidden'; el.style.textOverflow = 'ellipsis'; }
  else el.style.overflow = 'visible';
  document.body.appendChild(el);
  return el.getBoundingClientRect().width;
};
const UNPLANT = () => document.querySelectorAll('[data-testid^="clip-canary-"]').forEach((e) => e.remove());

const SCAN = () => {
  type Hit = { path: string; cls: string; overX: number; overY: number; text: string; scrollable: boolean; kind: string; hasTitle: boolean };
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
    // «پنهان با سه‌نقطه» با «بریده‌شده» دو چیزند: جدولِ تابلو نامِ بلند را
    // عمداً با ellipsis می‌بُرد و titleِ کامل را رویِ ردیف دارد. بی‌این تفکیک،
    // هر ردیفِ سالم هم «۶۸ پیکسل مشکل» گزارش می‌شد و آدم سراغِ تعمیرِ چیزِ
    // درست می‌رود.
    const ellipX = overX > 2 && (cs.textOverflow === 'ellipsis'
      || (cs.webkitLineClamp && cs.webkitLineClamp !== 'none'));
    const ellipY = overY > 2 && Boolean(cs.webkitLineClamp && cs.webkitLineClamp !== 'none');
    // «بریده» فقط وقتی است که همان محور overflow:hidden/clip باشد. با
    // overflow:visible محتوا بیرون می‌زند و *دیده می‌شود* (حداکثر رویِ هم
    // می‌افتد)، پس نقصِ برش نیست؛ پیش از این، رقم‌هایِ درشتِ «نبض بازار» با
    // leadingِ فشرده سه تا هفت پیکسل بیرون می‌زدند و همه «بریده» گزارش
    // می‌شدند، در حالی که هیچ‌کدام زیرِ هیچ clip ancestor سالمی نبود.
    const hardX = ox === 'hidden' || ox === 'clip';
    const hardY = oy === 'hidden' || oy === 'clip';
    const clippedX = overX > 2 && hardX && !ellipX;
    const clippedY = overY > 2 && hardY && !ellipY;
    const bleeds = (overX > 6 && !hardX && !canScrollX) || (overY > 6 && !hardY && !canScrollY);
    if (!clippedX && !clippedY && !canScrollX && !bleeds) continue;
    // فقط چیزی که واقعاً بیرونِ صفحه می‌زند یا متنش بریده می‌شود
    const offscreen = r.right > pageW + 1 || r.bottom > pageH + 1 || r.left < -1;
    if (!clippedX && !clippedY && !bleeds && !offscreen) continue;
    const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent ?? '').trim().length > 0);
    hits.push({
      kind: ellipX || ellipY ? 'ellipsized' : canScrollX || canScrollY ? 'scrollable'
        : (clippedX || clippedY) ? 'cut' : 'bleeds',
      hasTitle: el.hasAttribute('title') || Boolean((el.closest('[title]') as HTMLElement | null)?.title),
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
const report: Record<string, unknown> = { base: BASE, theme: THEME, sizes: SIZES.map(([w, h]) => `${w}x${h}`), widths: {} };
const ONLY = arg('only', '').split(',').filter(Boolean) as string[];
for (const [name, route, state] of ROUTES) {
  if (ONLY.length && !ONLY.includes(name)) continue;
  report.widths[name] = {};
  for (const [w, h] of SIZES) {
    const context = await browser.newContext({ viewport: { width: w, height: h } });
    await context.addInitScript(([theme]: any) => {
      try {
        sessionStorage.setItem('bors_auth_session', 'true');
        localStorage.setItem('bors-theme', theme);
        localStorage.removeItem('bors-symbol');
      } catch {
        /* دروازۀ محلی */
      }
    }, [THEME]);
    const page = await context.newPage();
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(WAIT);
    const canary = arg('selftest', '') ? ['cut', 'ellipsized', 'bleeds'] : [];
    for (const k of canary) await page.evaluate(PLANT as never, k);
    let opened: string | null = null;
    if (state) opened = await STATE_ACTIONS[state](page).catch((e: Error) => `failed: ${String(e.message).slice(0, 60)}`);
    const scanned = await page.evaluate(SCAN as never);
    if (canary.length) {
      const caught = new Set((scanned.hits as Array<{ text: string; kind: string }>)
        .filter((x) => (x.text || '').startsWith('kkkk')).map((x) => x.kind));
      (scanned as Record<string, unknown>).canary = Object.fromEntries(
        canary.map((k) => [k, caught.has(k) || (k === 'bleeds' && caught.has('bleeds'))]));
      await page.evaluate(UNPLANT as never);
    }
    report.widths[name][`${w}x${h}`] = { ...(scanned as object), state: state ?? null, opened };
    await context.close();
  }
}
await browser.close();
mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');

for (const [name, byW] of Object.entries(report.widths as Record<string, Record<string, { pageOverflowX: number; hits: unknown[] }>>)) {
  for (const [w, v] of Object.entries(byW)) {
    console.log(`${name.padEnd(14)} ${w}  overflowX=${v.pageOverflowX}  problems=${v.hits.length}`);
    for (const h of v.hits.slice(0, 6) as { path: string; overX: number; overY: number; n: number; text: string; kind: string; hasTitle: boolean }[]) {
      console.log(`    ${h.path.slice(0, 58).padEnd(58)} x+${String(h.overX).padStart(4)} y+${String(h.overY).padStart(4)} n=${h.n} ${h.kind}${h.hasTitle ? '+title' : ''} ${h.text.slice(0, 30)}`);
    }
  }
}
