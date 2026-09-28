// tools/tab_cost_probe.mts — هزینهٔ واقعیِ هر تب چقدر است؟ (CPU، دافعهٔ کامپوزیت، شبکه)
//
// مالک گفت «گرافیک زیاد مصرف می‌شود، احتمالاً قیف یا درخت». این ادعا با چشم
// سنجیده نمی‌شود؛ پس هر تب تنها باز می‌شود، شمارندهٔ rAF و Long Task روی همان
// صفحه می‌نشیند، و معیارهای CDP (Script/Layout/RecalcStyle/Task) دو بار در فاصلۀ
// ۱۲ ثانیه خوانده می‌شوند. تفاوتِ دو خوانش = هزینهٔ خالصِ همان تب در حالتِ عادی.
//
//   JEV_CHROME='...chromium-1234/chrome-win64/chrome.exe' MSYS_NO_PATHCONV=1 \
//   node --experimental-strip-types tools/tab_cost_probe.mts --url http://127.0.0.1:5173/
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
const OUT = arg('out', '_audit/tab_cost.json');
const WINDOW = Number(arg('window', '12000'));
const SETTLE = Number(arg('settle', '9000'));

const TABS: [string, string][] = [
  ['tape', '#/'],
  ['technical', '#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['fundamental', '#/fundamental/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['masterFunnel', '#/master'],
  ['masterVerdict', '#/master/%D9%81%D9%88%D9%84%D8%A7%D8%AF'],
  ['tree', '#/strategy-tree'],
  ['portfolio', '#/portfolio'],
];

const INSTRUMENT = () => {
  // شمارندۀ خودِ پروب با setTimeout می‌تپد تا requestAnimationFrameِ صفحه را
  // اشباع نکند؛ وگرنه «فریم» چیزی است که ما ساخته‌ایم نه اپ.
  const w = window as unknown as {
    __probe?: { raf: number; long: number; longMs: number };
    requestAnimationFrame?: (cb: FrameRequestCallback) => number;
  };
  const st = { raf: 0, long: 0, longMs: 0 };
  w.__probe = st;
  const orig = w.requestAnimationFrame!.bind(w);
  w.requestAnimationFrame = (cb: FrameRequestCallback) =>
    orig((t) => {
      st.raf++;
      cb(t);
    });
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        st.long++;
        st.longMs += e.duration;
      }
    }).observe({ entryTypes: ['longtask'] });
  } catch {
    /* longtask در بعضی نسخه‌ها نیست */
  }
};

const READ = () => {
  const p = (window as unknown as { __probe?: { raf: number; long: number; longMs: number } }).__probe;
  return {
    raf: p?.raf ?? 0,
    long: p?.long ?? 0,
    longMs: Math.round(p?.longMs ?? 0),
    domNodes: document.getElementsByTagName('*').length,
    canvases: Array.from(document.querySelectorAll('canvas')).map((c) => `${c.width}x${c.height}`),
    animating: document.getAnimations?.().length ?? -1,
  };
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const report: Record<string, unknown> = { base: BASE, windowMs: WINDOW, tabs: {} };

for (const [key, route] of TABS) {
  const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem('bors_auth_session', 'true');
    } catch {
      /* دروازۀ محلی */
    }
  });
  const page = await context.newPage();
  let requests = 0;
  let bytes = 0;
  page.on('response', async (res: { url: () => string; status: () => number; headers: () => Record<string, string> }) => {
    if (!res.url().includes('/api/')) return;
    requests++;
    bytes += Number(res.headers()['content-length'] ?? 0);
  });
  const cdp = await context.newCDPSession(page);
  await cdp.send('Performance.enable');
  const metrics = async (): Promise<Record<string, number>> => {
    const r = (await cdp.send('Performance.getMetrics')) as { metrics: { name: string; value: number }[] };
    const o: Record<string, number> = {};
    for (const m of r.metrics) o[m.name] = m.value;
    return o;
  };

  await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(SETTLE);
  await page.evaluate(INSTRUMENT as never);
  requests = 0;
  bytes = 0;
  const m0 = await metrics();
  const a0 = await page.evaluate(READ as never);
  await page.waitForTimeout(WINDOW);
  const m1 = await metrics();
  const a1 = await page.evaluate(READ as never);
  const d = (k: string) => +(((m1[k] ?? 0) - (m0[k] ?? 0)) * 1000).toFixed(0);

  report.tabs[key] = {
    route,
    scriptMs: d('ScriptDuration'),
    layoutMs: d('LayoutDuration'),
    recalcStyleMs: d('RecalcStyleDuration'),
    taskMs: d('TaskDuration'),
    styleCount: (m1['StyleCount'] ?? 0) - (m0['StyleCount'] ?? 0),
    layoutCount: (m1['LayoutCount'] ?? 0) - (m0['LayoutCount'] ?? 0),
    recalcCount: (m1['RecalcStyleCount'] ?? 0) - (m0['RecalcStyleCount'] ?? 0),
    rafCalls: a1.raf - a0.raf,
    longTasks: a1.long - a0.long,
    longTaskMs: a1.longMs - a0.longMs,
    domNodes: a1.domNodes,
    canvases: a1.canvases,
    runningAnimations: a1.animating,
    apiRequests: requests,
    apiBytes: bytes,
  };
  await page.screenshot({ path: OUT.replace(/\.json$/, `_${key}.png`) });
  await context.close();
}

await browser.close();
mkdirSync(OUT.split('/')[0] ?? '.', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
const rows = Object.entries(report.tabs as Record<string, Record<string, number>>);
console.log('تب'.padEnd(15), 'Task'.padStart(7), 'Script'.padStart(7), 'Layout'.padStart(7), 'Style'.padStart(7), 'rAF'.padStart(6), 'long'.padStart(5), 'DOM'.padStart(7), 'req'.padStart(4), 'KB'.padStart(7));
for (const [k, v] of rows) {
  console.log(
    k.padEnd(15),
    String(v.taskMs).padStart(7),
    String(v.scriptMs).padStart(7),
    String(v.layoutMs).padStart(7),
    String(v.recalcStyleMs).padStart(7),
    String(v.rafCalls).padStart(6),
    String(v.longTasks).padStart(5),
    String(v.domNodes).padStart(7),
    String(v.apiRequests).padStart(4),
    String(Math.round((v.apiBytes ?? 0) / 1024)).padStart(7),
  );
}
