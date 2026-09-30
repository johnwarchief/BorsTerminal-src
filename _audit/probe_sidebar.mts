// _audit/probe_sidebar.mts -- اثباتِ زندۀ سایدبار چپ (#48/#49) روی بک‌اندِ dev (۸۰۰۲)
// پنج مظنه از بانکِ واقعی خوانده می‌شود. «جریان حجم» دو جا سنجیده می‌شود:
// (الف) حالتِ بی‌دادهٔ صادقانه در بازارِ بسته + اینکه بیرونِ نشست چیزی نوشته نمی‌شود،
// (ب) رندرِ میله‌ها با سریِ_seed_شده — فقط چیدمان/ارتفاع، نه جمع‌آوریِ زنده
// (جمع‌آوری را باید در ساعتِ بازار سنجید؛ تسکِ اتوماسیونِ فردا).
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const SYM = process.argv[2] ?? 'چتر';
const _d = new Date();
const DAY = `${_d.getFullYear()}-${String(_d.getMonth() + 1).padStart(2, '0')}-${String(_d.getDate()).padStart(2, '0')}`;
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });

const apiCalls: string[] = [];
p.on('request', (r) => {
  const u = r.url();
  if (u.includes('/api/')) apiCalls.push(new URL(u).pathname);
});

await p.addInitScript((sym) => {
  sessionStorage.setItem('bors_auth_session', 'true');
  localStorage.setItem('bors-symbol', sym);
}, SYM);

await p.goto('http://127.0.0.1:8002/#/market', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);

const readPanel = () =>
  p.evaluate(() => {
    const q = (s: string) => document.querySelector(s);
    const box = (s: string) => {
      const el = q(s);
      if (!el) return null;
      const r = (el as HTMLElement).getBoundingClientRect();
      return { h: Math.round(r.height), w: Math.round(r.width), top: Math.round(r.top) };
    };
    const strip = q('[data-testid="inspector-stage"]');
    const cur = [...document.querySelectorAll('[data-testid^="inspector-stage-"]')]
      .filter((e) => e.getAttribute('aria-current') === 'step')
      .map((e) => e.textContent);
    return {
      stage_present: !!strip,
      stage_current: cur[0] ?? null,
      stage_note: q('[data-testid="inspector-stage-next"]')?.textContent ?? null,
      stage_box: box('[data-testid="inspector-stage"]'),
      book_present: !!q('[data-testid="sidebar-orderbook"]'),
      book_rows: document.querySelectorAll('[data-testid="sidebar-orderbook"] li').length,
      book_empty: q('[data-testid="sidebar-orderbook-empty"]')?.textContent ?? null,
      book_first: [...document.querySelectorAll('[data-testid="sidebar-orderbook"] li')].slice(0, 3).map((li) => li.textContent),
      book_box: box('[data-testid="sidebar-orderbook"]'),
      flow_present: !!q('[data-testid="volume-flow-mini"]'),
      flow_bars: document.querySelectorAll('[data-testid^="volume-mini-bar-"]').length,
      flow_empty: q('[data-testid="volume-mini-empty"]')?.textContent ?? null,
      flow_box: box('[data-testid="volume-flow-mini"]'),
      inspector_h: Math.round(q('aside[aria-label^="بازرسی نماد"]')?.getBoundingClientRect().height ?? 0),
      inspector_scroll: q('aside[aria-label^="بازرسی نماد"]')?.scrollHeight ?? 0,
      doc_scroll_x: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

const closedMarket = await readPanel();
const flowCacheAfterClosed = await p.evaluate(() => localStorage.getItem('bors:market:symflow:v1'));

// (ب) رندرِ میله‌ها با سریِ seed شده — فقط چیدمان/ارتفاع سنجیده می‌شود
await p.evaluate(
  ({ sym, day }) => {
    const samples: [string, number, number][] = [
      ['09:01', 1_000_000, 19430],
      ['09:10', 1_600_000, 19440],
      ['09:25', 2_100_000, 19425],
      ['10:30', 2_300_000, 19430],
      ['12:05', 3_050_000, 19450],
      ['12:20', 3_400_000, 19440],
    ];
    const buckets: { t: string; vol: number; dir: 'up' | 'down' }[] = [];
    for (let i = 1; i < samples.length; i++) {
      const [, cum, px] = samples[i];
      const [, prevCum, prevPx] = samples[i - 1];
      buckets.push({ t: samples[i][0], vol: cum - prevCum, dir: px > prevPx ? 'up' : 'down' });
    }
    const last = samples[samples.length - 1];
    localStorage.setItem(
      'bors:market:symflow:v1',
      JSON.stringify({
        day,
        symbols: { [sym]: { last: { t: last[0], cumVol: last[1], price: last[2] }, buckets } },
      }),
    );
  },
  { sym: SYM, day: DAY },
);
await p.reload({ waitUntil: 'domcontentloaded' });
await p.waitForTimeout(20000);
const seededRender = await readPanel();
await p.screenshot({ path: '_audit/sidebar_left_seeded.png' });

// تبِ دیگر ⇒ مرحلۀ فعلی باید عوض شود
await p.goto('http://127.0.0.1:8002/#/technical/چتر', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(18000);
const onTechnical = await readPanel();

console.log(
  JSON.stringify(
    {
      symbol: SYM,
      day: DAY,
      intraday_endpoint_calls: apiCalls.filter((u) => u.includes('/intraday/')),
      api_paths_seen: [...new Set(apiCalls)].slice(0, 12),
      closed_market: closedMarket,
      flow_cache_written_outside_session: flowCacheAfterClosed,
      seeded_render: seededRender,
      on_technical_tab: onTechnical,
    },
    null,
    1,
  ),
);
await b.close();
