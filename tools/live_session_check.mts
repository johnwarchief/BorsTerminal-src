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
const OUT = process.env.PROBE_OUT ?? '_audit/live_session.json';
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

/** وضعیتِ ردیف‌های دیدنی: متنِ هر ستون + زنده بودنِ گره
 *
 * فلاش *per-cell* خوانده نمی‌شود: کلاسِ `flash-*` روی گره‌ای می‌نشیند و
 * پیش از نمونهٔ بعدی (۳۰s در برابرِ ۵s پول) حذف می‌شود، پس «کلاسِ الان»
 * شاهدِ «آیا همان لحظه فلاش خورد» نیست. فلاش از `__flashLog` می‌آید که
 * MutationObserver درِ خودِ صفحه پر می‌کند (پایین‌تر). */
const snapshot = (n: number) =>
  page.evaluate(
    (n: number) =>
      Array.from(document.querySelectorAll('[data-testid="tape-row"]'))
        .slice(0, n)
        .map((row) => {
          const cells = Array.from(row.children).map((c) => (c.textContent ?? '').trim());
          const last = row.children[1];
          const num = (last?.querySelector('.num') ?? last) as HTMLElement | null;
          const marked = Boolean(num?.hasAttribute('data-live'));
          if (num && !marked) {
            num.setAttribute('data-live', '1');
            num.setAttribute('data-live-at', String(Date.now()));
          }
          return {
            symbol: cells[0] ?? '',
            cells,
            nodeOriginal: marked,
            sinceMarkMs: num?.getAttribute('data-live-at')
              ? Date.now() - Number(num.getAttribute('data-live-at'))
              : null,
          };
        }),
    n,
  );

/** ضبطِ هر گذارِ کلاس به `flash-*` روی ستون‌های ردیفِ تابلو — شاهدِ فلاش،
 *  لحظه‌ای و ستون‌به‌ستون، نه از روی کلاسی که دیر خوانده می‌شود. */
const startFlashLog = () =>
  page.evaluate(() => {
    const w = window as unknown as { __flashLog?: any[] };
    w.__flashLog = [];
    const obs = new MutationObserver((muts) => {
      for (const m of muts) {
        if (m.type !== 'attributes' || m.attributeName !== 'class') continue;
        const el = m.target as HTMLElement;
        const dir = Array.from(el.classList ?? []).find((c) => c.startsWith('flash-'));
        if (!dir) continue;
        const row = el.closest('[data-testid="tape-row"]');
        if (!row) continue;
        let cell = el;
        while (cell.parentElement && cell.parentElement !== row) cell = cell.parentElement;
        const col = Array.from(row.children).indexOf(cell);
        w.__flashLog!.push({
          at: Date.now(),
          symbol: ((row.children[0]?.textContent ?? '').trim()),
          col,
          dir,
          text: (cell.textContent ?? '').trim().slice(0, 40),
        });
      }
    });
    obs.observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });
    return true;
  });

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

const samples: {
  at: string; atMs: number;
  rows: Awaited<ReturnType<typeof snapshot>>;
  pulse: Awaited<ReturnType<typeof pulseText>>;
}[] = [];
const deadline = Date.now() + MINUTES * 60_000;
let i = 0;
await startFlashLog();

/* کنترلِ منفیِ خودِ ابزار (PROBE_SELFTEST=1): متنِ یک سلول را بی‌هیچ کلاسِ
 * فلاشی عوض می‌کنیم؛ اگر داوری واقعاً تفکیکِ (نماد، ستون) می‌کند باید دقیقاً
 * یک «جاافتاده» ببیند. بدونِ این کنترل `missedFlash=0` می‌تواند یعنی «همه‌چیز
 * فلاش می‌زند» و هم یعنی «سنجش هیچ‌چیز را جا نمی‌اندازد». */
const SELFTEST = process.env.PROBE_SELFTEST === '1';
/* سطرِ *آخر* از بریدۀ دیدنی: سطرهایِ بالای جدول با هر پول بازنوشته می‌شوند و
 * React متنِ تزریق‌شده را پاک می‌کند؛ آنجا کنترلِ منفی بی‌نتیجه می‌شود. */
const sentinel = () =>
  page.evaluate((idx: number) => {
    const all = document.querySelectorAll('[data-testid="tape-row"]');
    const row = all[Math.min(idx, all.length) - 1];
    const cell = row?.children[5];
    if (!cell) return null;
    const target = (cell.querySelector('.num') ?? cell) as HTMLElement;
    const sym = (row.children[0]?.textContent ?? '').trim();
    const from = (cell.textContent ?? '').trim();
    target.textContent = '999-CTRL';
    return { sym, col: 5, from, to: (cell.textContent ?? '').trim(), rowCount: all.length };
  }, ROWS);
let selftest: { expect: any; missedSeen: number; otherMissed: number } | null = null;
let selftestAtMs = 0;

while (Date.now() < deadline) {
  const atMs = Date.now();
  const rows = await snapshot(ROWS);
  samples.push({ at: `t${i}`, atMs, rows, pulse: await pulseText() });
  if (SELFTEST && i === 0) {
    selftest = { expect: await sentinel(), missedSeen: 0, otherMissed: 0 };
    selftestAtMs = Date.now();
  }
  i += 1;
  await page.waitForTimeout(30_000);
}

const flashLog = (await page.evaluate(
  () => ((window as unknown as { __flashLog?: any[] }).__flashLog ?? []),
)) as { at: number; symbol: string; col: number; dir: string; text: string }[];

// ── داوری ────────────────────────────────────────────────────────────────
// هر جفتِ متوالی: کدام ستون عوض شد و درِ همان پنجره، برایِ همان نماد و همان
// ستون، یک گذارِ `flash-*` ضبط شد؟ نبودِ ضبط = فلاش نخورد.
const changedCells = new Set<string>();
const missedFlash: { symbol: string; col: number; from: string; to: string }[] = [];
const colLabels = ['نماد', 'آخرین', 'پایانی', 'اختلاف٪', 'حجم', 'ارزش', 'تعداد', 'قدرت', 'الگو'];
let flashedCells = 0;
for (let s = 1; s < samples.length; s += 1) {
  const a = samples[s - 1];
  const b = samples[s];
  const inWindow = flashLog.filter((f) => f.at > a.atMs && f.at <= b.atMs);
  for (const rb of b.rows) {
    const ra = a.rows.find((x) => x.symbol === rb.symbol);
    if (!ra) continue;
    rb.cells.forEach((v, col) => {
      if (col === 0 || v === ra.cells[col]) return;
      changedCells.add(colLabels[col] ?? String(col));
      const flashed = inWindow.some((f) => f.symbol === rb.symbol && f.col === col);
      if (flashed) flashedCells += 1;
      else missedFlash.push({ symbol: rb.symbol, col, from: ra.cells[col], to: v });
    });
  }
}
const market = byEndpoint['/api/market'] ?? {};
const fresh = Object.values(payloadWatch).filter((e) => (e.changes ?? 0) > 0).length;

if (selftest?.expect) {
  const exp = selftest.expect as { sym: string; col: number; to: string };
  const hit = missedFlash.find((m) => m.symbol === exp.sym && m.col === exp.col);
  selftest.missedSeen = hit ? 1 : 0;
  selftest.otherMissed = missedFlash.filter((m) => m !== hit).length;
}

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
  flashRecords: flashLog.length,
  flashCellsMatched: flashedCells,
  selftest,
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
      flashRecords: report.flashRecords,
      flashCellsMatched: report.flashCellsMatched,
      missedFlashCount: missedFlash.length,
      selftest: report.selftest,
      nodesKeptOriginal: report.nodesKeptOriginal,
      verdictChanged: report.firstPulse?.verdict !== report.lastPulse?.verdict,
      errors: report.errors,
    },
    null,
    1,
  ),
);
