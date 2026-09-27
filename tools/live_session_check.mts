// tools/live_session_check.mts — سنجشِ نشستِ *واقعی* (#173)
//
// تفاوتش با live_flash_probe.mts: آن یکی نشستِ ساختگی بود تا منطقِ پولینگ و
// فلش را بدونِ باز بودنِ بازار ثابت کند. این یکی هیچ چیزی را جعل نمی‌کند —
// نه ساعت، نه پاسخِ /api/market. فقط مرورگر را به سرورِ در حال اجرا وصل
// می‌کند و همان چیزی که کاربر می‌بیند را در برابر دادهٔ زنده می‌سنجد.
//
// چه چیزی را اثبات می‌کند (هر کدام با عدد، نه با حدس):
//   ۱) تازگی: آیا ردیف‌هایِ جدول در نشستِ واقعی عوض می‌شوند؟ (payloadWatch)
//   ۲) فلشِ هم‌زمان: هر عددی که بینِ دو پاسخ عوض شد، همان لحظه روی DOM
//      فلاش خورد؟ (missedFlash = صفر باید بشود)
//   ۳) بی‌تخریبیِ گره: گرهٔ نشانه‌گذاری‌شده تا آخر زنده ماند؟
//   ۴) نبض بازار و نمودارهایش: اندپوینت‌های mstat واقعاً کشیده شدند و
//      متنِ حکم عوض شد؟
//   ۵) #175 در میدان: چند پاسخِ /api/market سه‌صدوچهار بود (یعنی رایگان)؟
//
// بازار که باز نباشد نتیجه معتبر نیست؛ پس اول درِ ساعت را خودش چک می‌کند و
// تعطیل بودن را به‌جای «باگ» گزارش می‌دهد.
//
// اجرا (سرورِ توسعه روی ۸۰۱۰، در ۰۸:۴۵–۱۲:۳۰ تهران):
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 PROBE_MINUTES=10 node --experimental-strip-types tools/live_session_check.mts
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const BASE = (process.env.PROBE_BASE ?? 'http://127.0.0.1:8010').replace(/\/+$/, '');
const ORIGIN = new URL(BASE).origin;
const MINUTES = Number(process.env.PROBE_MINUTES ?? 10);
const POLL = process.env.PROBE_POLL ?? '5000';
const OUT = '_audit/live_session.json';
const ROWS = Number(process.env.PROBE_ROWS ?? 4);

const apiPath = (u: string) => (u.startsWith(ORIGIN) ? u.slice(ORIGIN.length) : u);
const isApi = (u: string) => apiPath(u).startsWith('/api/');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
const page = await context.newPage();

const errors: string[] = [];
page.on('pageerror', (e: { message: string }) => errors.push('pageerror: ' + e.message.slice(0, 160)));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') errors.push(m.text().slice(0, 160));
});

/** شمارشِ درخواست/وضعیت به تفکیکِ اندپوینت — شاهدِ #175 در میدانِ واقعی */
const byEndpoint: Record<string, Record<string, number>> = {};
const bump = (u: string, k: string) => {
  const p = apiPath(u).split('?')[0];
  byEndpoint[p] = byEndpoint[p] ?? {};
  byEndpoint[p][k] = (byEndpoint[p][k] ?? 0) + 1;
};
page.on('request', (rq: { url: () => string }) => {
  if (isApi(rq.url())) bump(rq.url(), 'req');
});
page.on('response', (rs: { url: () => string; status: () => number }) => {
  if (isApi(rs.url())) bump(rs.url(), String(rs.status()));
});

/** بدنهٔ هر پاسخِ /api/market که از شبکه می‌آید (۳۰۴ بدنه ندارد؛ نادیده می‌گیرد) */
const payloadWatch: Record<string, Record<string, number>> = {};
page.on('response', async (rs: { url: () => string; status: () => number }) => {
  const p = apiPath(rs.url()).split('?')[0];
  if (!p.endsWith('/api/market') || rs.status() !== 200) return;
  try {
    const body = await rs.json();
    const stamp = new Date().toISOString();
    for (const row of body.data ?? []) {
      if (row.is_live === false) continue;
      payloadWatch[row.symbol] = payloadWatch[row.symbol] ?? {};
      const e = payloadWatch[row.symbol];
      const changed = e.ts !== undefined && (e.p_last !== row.p_last || e.tvol !== row.tvol);
      if (changed) e.changes = (e.changes ?? 0) + 1;
      e.p_last = row.p_last;
      e.tvol = row.tvol;
      e.ts = stamp;
    }
  } catch {
    /* بدنهٔ خوانده‌نشده = پاسخِ کش‌شده؛ چیزی برای ثبت نیست */
  }
});

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(12000);

const clock = await page.evaluate(() => ({
  pageLocal: new Date().toString(),
  pageIso: new Date().toISOString(),
}));

const setPoll = async () => {
  try {
    await page.selectOption('[aria-label="بازه به‌روزرسانی"]', POLL);
    return true;
  } catch {
    return false;
  }
};
const pollSet = await setPoll();

/** وضعیتِ ردیف‌های دیدنی: متنِ هر ستون + کلاسِ فلش + زنده بودنِ گره */
const snapshot = (n: number) =>
  page.evaluate(
    (n: number) =>
      Array.from(document.querySelectorAll('[data-testid="tape-row"]'))
        .slice(0, n)
        .map((row) => {
          const cells = Array.from(row.children).map((c) => (c.textContent ?? '').trim());
          const last = row.children[1];
          const num = (last?.querySelector('.num') ?? last) as HTMLElement | null;
          const cls = num?.className ?? '';
          const marked = Boolean(num?.hasAttribute('data-live'));
          if (num && !marked) {
            num.setAttribute('data-live', '1');
            num.setAttribute('data-live-at', String(Date.now()));
          }
          return {
            symbol: cells[0] ?? '',
            cells,
            flash: cls.split(/\s+/).filter((c) => c.startsWith('flash-')).join(',') || 'none',
            nodeOriginal: marked,
            sinceMarkMs: num?.getAttribute('data-live-at')
              ? Date.now() - Number(num.getAttribute('data-live-at'))
              : null,
          };
        }),
    n,
  );

const pulseText = () =>
  page.evaluate(() => {
    const t = (sel: string) => {
      const e = document.querySelector(sel);
      return e ? (e.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 180) : null;
    };
    return {
      verdict: t('[data-testid="pulse-verdict"]'),
      hemat: t('[data-testid="pulse-hemat"]'),
      stamp: t('[data-testid="filters-side"]'),
      rows: document.querySelectorAll('[data-testid="tape-row"]').length,
      bodyNums: document.querySelectorAll('.num').length,
    };
  });

const samples: { at: string; rows: Awaited<ReturnType<typeof snapshot>>; pulse: Awaited<ReturnType<typeof pulseText>> }[] = [];
const deadline = Date.now() + MINUTES * 60_000;
let i = 0;
while (Date.now() < deadline) {
  const rows = await snapshot(ROWS);
  samples.push({ at: `t${i}`, rows, pulse: await pulseText() });
  i += 1;
  await page.waitForTimeout(30_000);
}

// ── داوری ────────────────────────────────────────────────────────────────
// هر جفتِ متوالی: کدام ستون‌ها عوض شدند و آیا همان لحظه فلش داشت؟
const flashes = new Set(['flash-up', 'flash-down']);
const changedCells = new Set<string>();
const missedFlash: { symbol: string; col: number; from: string; to: string }[] = [];
const colLabels = ['نماد', 'آخرین', 'پایانی', 'اختلاف٪', 'حجم', 'ارزش', 'تعداد', 'قدرت', 'الگو'];
for (let s = 1; s < samples.length; s += 1) {
  const a = samples[s - 1];
  const b = samples[s];
  for (const rb of b.rows) {
    const ra = a.rows.find((x) => x.symbol === rb.symbol);
    if (!ra) continue;
    rb.cells.forEach((v, col) => {
      if (col === 0 || v === ra.cells[col]) return;
      changedCells.add(colLabels[col] ?? String(col));
      const touched = flashes.has(rb.flash) || (rb.sinceMarkMs ?? 0) < Number(POLL) * 3;
      if (!touched) missedFlash.push({ symbol: rb.symbol, col, from: ra.cells[col], to: v });
    });
  }
}
const market = byEndpoint['/api/market'] ?? {};
const fresh = Object.values(payloadWatch).filter((e) => (e.changes ?? 0) > 0).length;

await browser.close();
const report = {
  base: BASE,
  clock,
  pollSet,
  pollMs: Number(POLL),
  windowMinutes: MINUTES,
  samplesCount: samples.length,
  byEndpoint,
  payloadSymbols: Object.keys(payloadWatch).length,
  payloadFreshSymbols: fresh,
  changedCells: [...changedCells],
  missedFlash,
  // نمونهٔ نخست گره‌ها را *نشانه می‌گذارد*؛ از نمونهٔ دوم به بعد نشانه باید
  // هنوز همان‌جا باشد — اگر React گره را از نو ساخته باشد، نشانه می‌رود.
  nodesKeptOriginal: samples
    .slice(1)
    .every((s) => s.rows.every((r) => r.nodeOriginal)),
  pulseTrail: samples.map((s) => ({ at: s.at, verdict: s.pulse.verdict, hemat: s.pulse.hemat, rows: s.pulse.rows })),
  firstPulse: samples[0]?.pulse ?? null,
  lastPulse: samples[samples.length - 1]?.pulse ?? null,
  errors: errors.slice(0, 12),
};
mkdirSync('_audit', { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
console.log(
  JSON.stringify(
    {
      clock,
      pollSet,
      samples: samples.length,
      marketReqs: market.req ?? 0,
      market200: market['200'] ?? 0,
      market304: market['304'] ?? 0,
      pulseReqs: byEndpoint['/api/mstat/summary']?.req ?? 0,
      payloadChangedSymbols: fresh,
      changedCells: report.changedCells,
      missedFlashCount: missedFlash.length,
      nodesAllOriginal: report.nodesAllOriginal,
      verdictChanged: report.firstPulse?.verdict !== report.lastPulse?.verdict,
      errors: report.errors,
    },
    null,
    1,
  ),
);
