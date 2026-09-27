// tools/market_poll_cost.mts — هزینهٔ واقعیِ هر نفسِ تابلو (#175)
//
// چه چیزی را می‌سنجد: /api/market بدنهٔ ۷٫۳ مگابایتی دارد. در ساعتِ بازار
// تابلو هر ۵ ثانیه آن را می‌خواهد ولی سینکِ داده هر ~۳۰ ثانیه یک‌بار چیزی
// عوض می‌کند. اگر هر poll بدنهٔ کامل بیاید، همان ۷٫۳ مگابایت هر بار
// decompress + JSON.parse + zod می‌شود؛ اگر اعتبارسنجیِ etag کار کند، سرور
// ۳۰۴ِ صفر‌بایتی می‌دهد و هیچ رندری ساخته نمی‌شود.
//
// دو عدد کنار هم گزارش می‌شود:
//   appPolls  — زمان‌بندیِ خودِ اپ از PerformanceResourceTiming (تازۀ واقعی)
//   baseline  — همان URL، سه بار *بدون* If-None-Match (همان چیزی که پیش از
//               این هر poll هزینه می‌کرد)
// اجرا: سرورِ توسعه روی ۸۰۱ بالا باشد.
//   JEV_CHROME=... node --experimental-strip-types tools/market_poll_cost.mts
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const BASE = process.env.PROBE_BASE ?? 'http://127.0.0.1:8010/';
const WAIT_MS = Number(process.env.PROBE_WAIT ?? 40000);
// بی‌اسلشِ انتهایی: '…:8010/' + '/api/market' دو اسلش می‌سازد و FastAPI با ۳۰۷
// به مسیرِ درست می‌فرستدش؛ آن‌وقت اندازه‌گیریِ «هزینۀ هر poll» عددِ بی‌ربط می‌دهد.
const ORIGIN = BASE.replace(/\/+$/, '');

/** PROBE_SESSION با ساعتِ ساختگی، دروازۀ «بازار باز» را باز می‌کند تا ریتمِ
 *  واقعیِ ۵ ثانیه ببینیم؛ بی‌آن، ساعتِ بسته خودِ اپ را به ۵ دقیقه می‌بندد. */
const SESSION = process.env.PROBE_SESSION ? new Date(process.env.PROBE_SESSION) : null;

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
if (SESSION) await context.clock.install({ time: SESSION });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const page = await context.newPage();
const errors: string[] = [];
// شمارشِ پاسخ‌هایِ خودِ اپ (با clockِ ساختگی Resource Timing چیزی نشان نمی‌دهد،
// ولی شبکه که دروغ نمی‌گوید): هر ۲۰۰ یعنی ۷٫۳ مگابایتِ کامل، هر ۳۰۴ یعنی صفر
const responses: { status: number; etag: string; length: string }[] = [];
page.on('response', async (res: { url: () => string; status: () => number; headers: () => Record<string, string> }) => {
  if (!res.url().includes('/api/market')) return;
  const h = res.headers();
  responses.push({ status: res.status(), etag: h['etag'] ?? '', length: h['content-length'] ?? h['content-encoding'] ?? '' });
});
page.on('pageerror', (e: { message: string }) => errors.push('pageerror: ' + e.message.slice(0, 160)));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') errors.push(m.text().slice(0, 160));
});

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);
await page.selectOption('[aria-label="بازه به‌روزرسانی"]', '5000');
await page.waitForTimeout(WAIT_MS);

const measured = await page.evaluate(async (base: string) => {
  const entries = performance
    .getEntriesByType('resource')
    .filter((e) => e.name.startsWith(base + '/api/market'))
    .map((e) => {
      const r = e as PerformanceResourceTiming;
      return {
        transferSize: Math.round(r.transferSize),
        encodedBodySize: Math.round(r.encodedBodySize),
        duration: Math.round(r.duration),
      };
    });
  const heap0 = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory?.usedJSHeapSize ?? 0;

  // خطِ پایه: همان URL بدونِ اعتبارسنجی — یعنی هر چیزی که یک pollِ کامل هزینه دارد
  let plainBytes = 0;
  let plainMs = 0;
  let etag = '';
  for (let i = 0; i < 3; i += 1) {
    const t = performance.now();
    const res = await fetch(base + '/api/market', { cache: 'no-store', headers: { Accept: 'application/json' } });
    const buf = await res.arrayBuffer();
    plainMs += performance.now() - t;
    plainBytes += buf.byteLength;
    etag = res.headers.get('etag') ?? etag;
  }
  // همان درخواست با If-None-Match — چیزی که اپِ تازه می‌فرستد
  let revalBytes = 0;
  let revalMs = 0;
  let revalStatus = 0;
  for (let i = 0; i < 3; i += 1) {
    const t = performance.now();
    const res = await fetch(base + '/api/market', {
      cache: 'no-store',
      headers: { Accept: 'application/json', 'If-None-Match': etag },
    });
    const buf = await res.arrayBuffer();
    revalMs += performance.now() - t;
    revalBytes += buf.byteLength;
    revalStatus = res.status;
  }
  const heap1 = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory?.usedJSHeapSize ?? 0;
  return {
    appPolls: entries,
    appPollCount: entries.length,
    appPollBytes: entries.reduce((a, b) => a + b.transferSize, 0),
    appPollMsMedian: entries.length ? entries.map((e) => e.duration).sort((a, b) => a - b)[Math.floor(entries.length / 2)] : 0,
    baseline: {
      bytesPerPoll: Math.round(plainBytes / 3),
      msPerPoll: Math.round(plainMs / 3),
      revalidateStatus: revalStatus,
      revalidateBytesPerPoll: Math.round(revalBytes / 3),
      revalidateMsPerPoll: Math.round(revalMs / 3),
    },
    jsHeapMB: { before: Math.round(heap0 / 1e6), after: Math.round(heap1 / 1e6) },
    domNodes: document.querySelectorAll('*').length,
  };
}, ORIGIN);

await browser.close();
const report = { appResponses: responses, base: ORIGIN, waitMs: WAIT_MS, session: SESSION ? SESSION.toISOString() : 'real-clock', ...measured, errors: errors.slice(0, 8) };
mkdirSync('_audit', { recursive: true });
writeFileSync('_audit/market_poll_cost.json', JSON.stringify(report, null, 1), 'utf8');
console.log(JSON.stringify(report, null, 1));
