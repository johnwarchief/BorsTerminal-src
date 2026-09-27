// tools/live_flash_probe.mts — سنجشِ زندهٔ «تابلو در ساعتِ بازار» (#173)
//
// چرا: آزمون‌های jsdom ثابت می‌کنند فلش و پولینگ *منطق* دارند؛ ولی این‌ها را
// نمی‌شود در jsdom دید: آیا عددِ عوض‌شده واقعاً به DOM می‌رسد، کلاسِ flash-up/
// flash-down می‌آید، گرهٔ DOM تخریب نمی‌شود (چشمکِ ردیف)، و پنل‌هایِ نشست‌محور
// (نبض بازار، صنایع داغ، مینی‌چارتِ حجم) هم مثلِ جدول تازه می‌شوند یا نه.
//
// بازار که باز نباشد این سنجش ممکن نیست، پس نشست ساخته می‌شود:
//   ۱) clock.install روی یک روزِ معاملاتی (سه‌شنبه ۱۰:۰۰ تهران) → دروازۀ
//      isMarketOpen() در خودِ مرورگر true می‌شود و ریتمِ انتخابیِ کاربر محترم
//      می‌ماند. چهارشنبه و جمعه تعطیل‌اند؛ اگر تاریخِ ساختگی تعطیل باشد،
//      همان سنجشِ «بازارِ بسته» می‌شود (و آن هم شاهدِ مفیدی است).
//   ۲) route روی /api/market: پاسخِ *واقعیِ* capture‌شده با اعدادِ متغیر
//      برمی‌گردد — یعنی همان مسیری که تابلو فردا طی می‌کند:
//      fetch → zod → store → TapeRow → FlashNum.
//   ۳) بازه روی «۵ ثانیه» و ثانیه‌های *واقعی* گذar می‌شود.
//
// اجرا (سرورِ توسعه روی ۸۰۱۰ باید بالا باشد):
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/live_flash_probe.mts
//
// خروج: _audit/live_flash.json — شمارۀ درخواست‌ها، نمونۀ هر ردیف در هر تیک،
// کلاسِ فلش، زنده‌ماندنِ گره، متنِ نبض بازار و خطاهایِ کنسول.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const BASE = process.env.PROBE_BASE ?? 'http://127.0.0.1:8010/';
const FEED = '_audit/market_feed.json';
const OUT = '_audit/live_flash.json';
/** نشستِ ساختگی: روزِ معاملاتی + میاندادۀ بازار */
const SESSION = new Date(process.env.PROBE_SESSION ?? '2026-09-23T10:00:00+03:30');
/** ثانیه‌هایِ واقعیِ انتظار برای هر تیک، و تعدادِ تیک‌ها */
const STEP_MS = Number(process.env.PROBE_STEP ?? 6000);
const TICKS = Number(process.env.PROBE_TICKS ?? 9);

// خوراکِ واقعی: اگر نبود، یک‌بار از خودِ سرور گرفته می‌شود (بدونِ ساختنِ دادهٔ جعلی)
if (!existsSync(FEED)) {
  mkdirSync('_audit', { recursive: true });
  const res = await fetch(`${BASE.replace(/\/$/, '')}/api/market`);
  if (!res.ok) throw new Error(`پاسخِ تابلو نرسید: ${res.status}`);
  writeFileSync(FEED, await res.text(), 'utf8');
}
const RAW = readFileSync(FEED, 'utf8');
type Row = Record<string, number | string | null>;
const parse = (): { data: Row[]; count: number } => JSON.parse(RAW);

/** نمادهایی که بعد از نخستین رندر در DOM دیدنی‌اند؛ این‌ها زنده می‌شوند */
const live: Row[] = [];
let tick = 0;
const feedCounts: Record<string, number> = {};
/** یکی صعودی، یکی نزولی، تا هر دو کلاسِ فلش سنجیده شود */
const DIRS = [1, -1, 1];

const mutated = () => {
  const body = parse();
  tick += 1;
  for (let i = 0; i < live.length; i += 1) {
    const want = live[i];
    const row = body.data.find((x) => x.symbol === want.symbol);
    if (!row) continue;
    const d = (DIRS[i % DIRS.length] ?? 1) * tick;
    const py = Number(want.price_yesterday) || 1;
    const pLast = Math.max(1, Number(want.p_last) + d * 10);
    const pClose = Math.max(1, Number(want.p_closing) + d * 5);
    const vol = Number(want.q_tot_tran) + tick * 100_000;
    row.p_last = pLast;
    row.p_closing = pClose;
    row.q_tot_tran = vol;
    row.tvol = vol;
    row.z_tot_tran = Number(want.z_tot_tran) + tick;
    row.q_tot_cap = Number(want.q_tot_cap) + tick * 1_000_000_000;
    row.buy_i_vol = Number(want.buy_i_vol) + tick * 40_000;
    row.percent_last = Number((((pLast - py) / py) * 100).toFixed(2));
    row.percent_change = Number((((pClose - py) / py) * 100).toFixed(2));
  }
  return body;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم همین را می‌پذیرد */
  }
});
await context.clock.install({ time: SESSION });

const page = await context.newPage();
const errors: string[] = [];
page.on('pageerror', (e: { message: string }) => errors.push('pageerror: ' + e.message.slice(0, 160)));
page.on('console', (m: { type: () => string; text: () => string }) => {
  if (m.type() === 'error') errors.push(m.text().slice(0, 160));
});
const allReq: Record<string, number> = {};
page.on('request', (rq: { url: () => string }) => {
  const u = rq.url().replace(BASE.replace(/\/$/, ''), '');
  if (u.includes('/api/')) allReq[u] = (allReq[u] ?? 0) + 1;
});
await page.route('**/api/market', async (route) => {
  feedCounts['/api/market'] = (feedCounts['/api/market'] ?? 0) + 1;
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mutated()) });
});
for (const ep of [
  '/api/mstat/summary',
  '/api/mstat/smart-money',
  '/api/mstat/depth',
  '/api/mstat/thermometer',
  '/api/mstat/timeline',
  '/api/mstat/industries',
]) {
  await page.route('**' + ep + '*', async (route) => {
    feedCounts[ep] = (feedCounts[ep] ?? 0) + 1;
    await route.continue();
  });
}

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(15000);

// سه ردیفِ اولِ *رندرشده* را قفل کن (جدول مجازی است؛ هرچه دیده می‌شود همان
// قابلِ سنجش است) و پایۀ اعدادشان را از پاسخِ واقعی بردار
const picked = await page.evaluate(() =>
  Array.from(document.querySelectorAll('[data-testid="tape-row"]'))
    .slice(0, 3)
    .map((r) => (r.children[0]?.childNodes[0]?.nodeValue ?? '').trim()),
);
const feedRows = parse().data;
for (const s of picked) {
  const r = feedRows.find((x) => String(x.symbol) === s);
  if (r) live.push(structuredClone(r));
}

const SAMPLE = () =>
  page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid="tape-row"]'))
      .slice(0, 3)
      .map((row) => {
        const last = row.children[1];
        const num = last.querySelector('.num') ?? last;
        // یک‌بار نشانه‌گذاری: اگر گره در تیک‌های بعد هم نشانه داشت، یعنی
        // React آن را از نو نساخته (همان «بدونِ تخریبِ گره»ِ FlashNum)
        if (!num.hasAttribute('data-probe')) num.setAttribute('data-probe', '1');
        return {
          symbol: (row.children[0]?.childNodes[0]?.nodeValue ?? '').trim(),
          last: last.textContent,
          closing: row.children[2].textContent,
          pct: row.children[3].textContent,
          vol: row.children[5].textContent,
          count: row.children[6].textContent,
          value: row.children[7].textContent,
          buysell: row.children[9].textContent,
          delta: row.children[10].textContent,
          flash: num.className.split(/\s+/).filter((c) => c.startsWith('flash-')).join(',') || 'none',
          nodeAlive: num.getAttribute('data-probe') === '1',
        };
      }),
  );

const DIAG = async (tag: string) => ({
  tag,
  ...(await page.evaluate(() => ({
    pageDate: new Date().toISOString(),
    visibility: document.visibilityState,
    online: navigator.onLine,
    stamp: (document.querySelector('[data-testid="filters-side"]')?.textContent ?? '').slice(0, 60),
  }))),
});

const samples: Record<string, unknown>[] = [{ at: 't0', rows: await SAMPLE() }];
const diag: Record<string, unknown>[] = [await DIAG('t0')];
// ریتم روی ۵ ثانیه؛ بعد ثانیه‌های واقعی می‌گذرد. (clock.fastForward تایمرِ
// refetchInterval تان‌استک را بیدار نکرد، پس زمانِ واقعی تنها سنجشِ صادق است.)
await page.selectOption('[aria-label="بازه به‌روزرسانی"]', '5000');
for (let i = 1; i <= TICKS; i += 1) {
  await page.waitForTimeout(STEP_MS);
  diag.push(await DIAG(`t${i}`));
  samples.push({ at: `t${i}`, rows: await SAMPLE() });
}
const pulse = await page.evaluate(() => {
  const txt = (sel: string) => {
    const e = document.querySelector(sel);
    return e ? (e.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 200) : null;
  };
  return { verdict: txt('[data-testid="pulse-verdict"]'), hemat: txt('[data-testid="pulse-hemat"]') };
});

await browser.close();
const report = {
  session: SESSION.toISOString(),
  tradingDay: SESSION.getDay() < 4,
  picked,
  samples,
  diag,
  feedCounts,
  allReq,
  pulse,
  errors: errors.slice(0, 10),
};
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
console.log(
  JSON.stringify(
    {
      session: report.session,
      tradingDay: report.tradingDay,
      feedCounts,
      marketFetches: allReq['/api/market'] ?? 0,
      pulseFetches: allReq['/api/mstat/summary'] ?? 0,
      flashSeen: samples.flatMap((s) => (s.rows as { flash: string }[]).map((r) => r.flash)).filter((f) => f !== 'none'),
      nodesAlive: samples.every((s) => (s.rows as { nodeAlive: boolean }[]).every((r) => r.nodeAlive)),
      changed: samples.length > 1
        ? JSON.stringify((samples[0].rows as { last: string }[]).map((r) => r.last)) !==
          JSON.stringify((samples[samples.length - 1].rows as { last: string }[]).map((r) => r.last))
        : false,
      errors: report.errors,
    },
    null,
    1,
  ),
);
