// _audit/verify-20261010/probe.mts — راستی‌آزماییِ زندهٔ UI (شش بند) رویِ بک‌اندِ devِ 8002
// اجرا: JEV_CHROME=… MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/verify-20261010/probe.mts
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUTDIR = '_audit/verify-20261010';
mkdirSync(OUTDIR, { recursive: true });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const R: Record<string, unknown> = {
  base: BASE, startedAt: new Date().toISOString(), item1: {}, item2: {}, item3: {},
  item4: {}, item5: {}, item6: {}, consoleErrors: [], network: [], funnelNet: [],
};
const ckConsole = (page: any) => {
  page.on('console', (m: any) => {
    if (m.type() === 'error') (R.consoleErrors as string[]).push(`${new Date().toISOString()} console: ${String(m.text()).slice(0, 300)}`);
  });
  page.on('pageerror', (e: any) => (R.consoleErrors as string[]).push(`${new Date().toISOString()} pageerror: ${String(e.message).slice(0, 300)}`));
};
// لاگِ شبکهٔ /api/funnel: شناساییِ درخواست، زمانِ شروع/پایان، و ترتیبِ سوییچِ preset
let switchSeq = 0;
const netLog: { id: number; preset: string; startedAt: string; endedAt: string | null; ok: boolean; aborted: boolean; switchNo: number }[] = [];
let currentPreset = '';
let currentSwitch = 0;
let reqId = 0;
const attachNet = (page: any) => {
  page.on('request', (r: any) => {
    const u = String(r.url());
    if (u.includes('/api/funnel')) {
      reqId += 1;
      netLog.push({ id: reqId, preset: currentPreset, startedAt: new Date().toISOString(), endedAt: null, ok: false, aborted: false, switchNo: currentSwitch });
      (R.network as string[]).push(`REQ ${reqId} preset=${currentPreset} switch=${currentSwitch} at=${Date.now()}`);
    }
  });
  page.on('response', (r: any) => {
    const u = String(r.url());
    if (u.includes('/api/funnel')) {
      const rec = [...netLog].reverse().find((x) => x.endedAt === null);
      if (rec) { rec.endedAt = new Date().toISOString(); rec.ok = r.status() < 400; }
      (R.network as string[]).push(`RES ${rec?.id ?? '?'} status=${r.status()} at=${Date.now()}`);
    }
  });
  page.on('requestfailed', (r: any) => {
    const u = String(r.url());
    if (u.includes('/api/funnel')) {
      const rec = [...netLog].reverse().find((x) => x.endedAt === null);
      if (rec) { rec.endedAt = new Date().toISOString(); rec.aborted = true; }
      (R.network as string[]).push(`FAIL ${rec?.id ?? '?'} ${r.failure()?.cancelled ? 'aborted' : 'failed'} at=${Date.now()}`);
    }
  });
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
    localStorage.removeItem('fts.strategy.horizon.v1');
    localStorage.removeItem('fts.funnel.prefs.v1');
    localStorage.removeItem('bors-portfolio-watch');
  } catch {}
});
const page = await context.newPage();
ckConsole(page);
attachNet(page);

const go = async (route: string, sel: string, timeout = 60000) => {
  await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector(sel, { timeout });
  await sleep(1200);
};

// ────────────────────────── بند ۱ و ۲: پنلِ وضعیت بازار ──────────────────────────
try {
  await go('#/market', '[data-testid="market-status-panel"]');
  await page.screenshot({ path: `${OUTDIR}/01_market_collapsed.png` });
  const collapsed = await page.evaluate(() => {
    const p = document.querySelector('[data-testid="market-status-panel"]');
    if (!p) return null;
    const chips = Array.from(p.querySelectorAll('span[data-testid], span[title]')).filter((s) => s.querySelector?.('.num') || s.className.includes('rounded-full'));
    const chipTexts = chips.map((c) => ({
      testid: c.getAttribute('data-testid') ?? null,
      text: (c.textContent ?? '').replace(/\s+/g, ' ').trim(),
      title: c.getAttribute('title') ?? '',
    }));
    return { panelText: (p.textContent ?? '').replace(/\s+/g, ' ').trim(), chipTexts, toggle: !!p.querySelector('[data-testid="msp-toggle"]') };
  });
  (R.item1 as any).collapsed = collapsed;
  await page.click('[data-testid="msp-toggle"]');
  await sleep(700);
  await page.screenshot({ path: `${OUTDIR}/02_market_expanded.png` });
  const expanded = await page.evaluate(() => {
    const p = document.querySelector('[data-testid="market-status-panel"]');
    if (!p) return null;
    const cols = Array.from(p.querySelectorAll(':scope > div')).filter((d) => d.querySelector('.font-black'));
    return cols.map((c) => (c.textContent ?? '').replace(/\s+/g, ' ').trim());
  });
  (R.item1 as any).expandedColumns = expanded;
  const liveStats = await page.evaluate(async () => {
    const r = await fetch('api/live-stats');
    return await r.json();
  });
  (R.item1 as any).liveStats = liveStats;
  (R.item1 as any).checkedAt = new Date().toISOString();
  // بند ۲: صادقِ تازگی — متنِ «عوض‌شدنِ عدد» و «آخرین دادهٔ بازار» درحالتِ revision=0
  (R.item2 as any).dataAgeChip = collapsed?.chipTexts?.find((c: any) => c.testid === 'msp-data-age') ?? null;
  (R.item2 as any).panelFullText = collapsed?.panelText ?? null;
  (R.item2 as any).revision = (liveStats?.data ?? {}).revision;
  (R.item2 as any).marketOpen = ((liveStats?.data ?? {}).window ?? {}).market_open;
} catch (e) {
  (R.item1 as any).error = String(e);
}

// ───────────────────────── بند ۳ و ۴: پریست‌هایِ قیف ─────────────────────────
const readFunnel = () =>
  page.evaluate(() => {
    const txt = (sel: string) => {
      const el = document.querySelector(sel);
      return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
    };
    const tabs = Array.from(document.querySelectorAll('[role="tab"][data-testid^="funnel-step-"]')).map((el) => ({
      key: (el.getAttribute('data-testid') ?? '').replace('funnel-step-', ''),
      text: (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
      selected: el.getAttribute('aria-selected') === 'true',
    }));
    const rows: { sym: string; cells: string }[] = [];
    const stage = document.querySelector('[data-testid="funnel-stage-tape"]');
    if (stage) {
      for (const tr of Array.from(stage.querySelectorAll('tbody tr[data-fkey]')).slice(0, 6)) {
        rows.push({ sym: tr.getAttribute('data-fkey') ?? '', cells: (tr.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 160) });
      }
    }
    const header = stage?.querySelector('header');
    return {
      tapeHeaderLine: header ? (header.textContent ?? '').replace(/\s+/g, ' ').trim() : null,
      stageCountLine: txt('[data-testid="fts-stage-count-tape"]'),
      tabs,
      counts: {
        pass: txt('[data-testid="funnel-count-pass"]'),
        pending: txt('[data-testid="funnel-count-pending"]'),
        reject: txt('[data-testid="funnel-count-reject"]'),
        unavailable: txt('[data-testid="funnel-count-unavailable"]'),
        notRequired: txt('[data-testid="funnel-count-not-required"]'),
        market: txt('[data-testid="funnel-universe-market"]'),
        screening: txt('[data-testid="funnel-universe-screening"]'),
      },
      asOf: txt('[data-testid="funnel-as-of"]'),
      asOfTestidPresent: !!document.querySelector('[data-testid="funnel-as-of"]'),
      computing: txt('[data-testid="funnel-computing"]'),
      techCoverage: txt('[data-testid="funnel-tech-coverage"]'),
      tapeFreshness: txt('[data-testid="funnel-tape-freshness"]'),
      rows,
      chainNodes: Array.from(document.querySelectorAll('[data-testid^="funnel-chain-"]')).map((el) => ({
        key: (el.getAttribute('data-testid') ?? '').replace('funnel-chain-', ''),
        num: el.querySelector('.num')?.textContent ?? null,
      })),
      url: location.href,
    };
  });

const PRESETS: [string, string][] = [
  ['swing', '#/master?stage=tape&preset=swing'],
  ['trend', '#/master?stage=tape&preset=trend'],
  ['hourglass', '#/master?stage=tape&preset=hourglass'],
  ['custom', '#/master?stage=tape&preset=custom'],
  ['custom_fclock', '#/master?stage=tape&preset=custom&chain=f_clock'],
];
try {
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await sleep(800);
  const snaps: Record<string, unknown> = {};
  for (const [name, route] of PRESETS) {
    currentPreset = name;
    currentSwitch += 1;
    switchSeq = currentSwitch;
    await page.evaluate((r: string) => { location.hash = r.split('#')[1]; }, route);
    try {
      await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: 60000 });
    } catch { /* snapshot بازم از DOM خوانده می‌شود */ }
    await sleep(9000); // پاسخِ ۸-۱۰ مگابایتی + اسکنِ پس‌زمینه
    const s = await readFunnel();
    s.switchedAt = new Date().toISOString();
    snaps[name] = s;
    await page.screenshot({ path: `${OUTDIR}/03_funnel_${name}.png`, fullPage: false });
  }
  (R.item3 as any).presets = snaps;
  // بند ۴: hourglass دربرابَر custom — باید متفاوت باشند
  const hg = snaps.hourglass as any, cu = snaps.custom as any;
  (R.item4 as any).hourglass_vs_custom = {
    sameCounts: JSON.stringify(hg?.counts) === JSON.stringify(cu?.counts),
    hourglass: { counts: hg?.counts, computing: hg?.computing, techCoverage: hg?.techCoverage, asOf: hg?.asOf, chain: hg?.chainNodes?.map((n: any) => n.key) },
    custom: { counts: cu?.counts, computing: cu?.computing, techCoverage: cu?.techCoverage, asOf: cu?.asOf, chain: cu?.chainNodes?.map((n: any) => n.key) },
    asOfText: hg?.asOf, computingText: hg?.computing ?? hg?.techCoverage,
  };
  (R.item4 as any).funnelNetLog = netLog.slice();
  // پاسخِ دیرهنگام (stale overwrite): آیا پاسخِ presetِ n بعد از سوییچِ n+1 رسیده؟
  const late: string[] = [];
  for (let i = 0; i < netLog.length; i++) {
    const req = netLog[i];
    for (let j = i + 1; j < netLog.length; j++) {
      if (netLog[j].switchNo > req.switchNo && req.endedAt && new Date(req.endedAt).getTime() > new Date(netLog[j].startedAt).getTime() - 1) {
        // پایانِ پاسخِ req بعد از شروعِ درخواستِ بعدی — یعنی کهنه بود
      }
    }
    const nextSwitchStart = netLog.find((x, k) => k > i && x.switchNo > req.switchNo);
    if (nextSwitchStart && req.endedAt && !req.aborted && new Date(req.endedAt) > new Date(nextSwitchStart.startedAt)) {
      late.push(`req#${req.id} (preset=${req.preset}) پایان=${req.endedAt} بعد از شروعِ سوییچِ بعدی (${nextSwitchStart.preset} @ ${nextSwitchStart.startedAt})`);
    }
  }
  (R.item4 as any).lateFunnelResponses = late;
} catch (e) {
  (R.item3 as any).error = String(e);
}

// ───────────────────────── بند ۵: ۶۰ ثانیه بی‌دست‌کاری ─────────────────────────
try {
  await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="tape-scroll"]', { timeout: 60000 });
  await sleep(2500);
  const boardSnap = () =>
    page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('[data-testid="tape-row"]')).slice(0, 10).map((r) => {
        const spans = Array.from(r.querySelectorAll('span')).slice(0, 4).map((s) => (s.textContent ?? '').trim());
        return spans.join(' | ');
      });
      const p = document.querySelector('[data-testid="market-status-panel"]');
      return { rows, panel: (p?.textContent ?? '').replace(/\s+/g, ' ').trim(), scroll: (document.querySelector('[data-testid="tape-scroll"]')?.scrollHeight ?? 0) };
    });
  const t0 = await boardSnap();
  const t0at = new Date().toISOString();
  await sleep(60000);
  const t1 = await boardSnap();
  const t1at = new Date().toISOString();
  const stats = await page.evaluate(async () => (await (await fetch('api/live-stats')).json()).data);
  await page.screenshot({ path: `${OUTDIR}/05_idle_60s.png` });
  (R.item5 as any) = {
    t0at, t1at,
    rowsChanged: JSON.stringify(t0.rows) !== JSON.stringify(t1.rows),
    t0rows: t0.rows.slice(0, 5), t1rows: t1.rows.slice(0, 5),
    panelBefore: t0.panel, panelAfter: t1.panel,
    panelChanged: t0.panel !== t1.panel,
    revision: stats?.revision, cycles: stats?.cycles, marketOpen: stats?.window?.market_open,
  };
} catch (e) {
  (R.item5 as any).error = String(e);
}

// ───────────────────────── بند ۶: دیده‌بان بازار ─────────────────────────
try {
  await page.goto(`${BASE}#/portfolio`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  const sections = await page.evaluate(() => {
    const mine = document.querySelector('[data-testid="portfolio-section-mine"]');
    const watch = document.querySelector('[data-testid="portfolio-section-watch"]');
    return {
      mine: mine ? (mine.textContent ?? '').trim() : null,
      watch: watch ? (watch.textContent ?? '').trim() : null,
    };
  });
  (R.item6 as any).subtabs = sections;
  if (!sections.watch) {
    (R.item6 as any).verdict = 'SUBTABS_ABSENT';
  } else {
    await page.click('[data-testid="portfolio-section-watch"]');
    await sleep(1500);
    await page.screenshot({ path: `${OUTDIR}/06_watch_initial.png` });
    // افزودنِ سه نماد
    for (const sym of ['شپنا', 'فولاد', 'خساپ']) {
      await page.fill('[data-testid="watch-add-input"]', sym);
      await sleep(700);
      await page.click('[data-testid="watch-add-btn"]');
      await sleep(700);
    }
    await sleep(2500);
    const rowsInfo = await page.evaluate(() => ({
      workspace: !!document.querySelector('[data-testid="watch-market-workspace"]'),
      empty: document.querySelector('[data-testid="watch-empty"]')?.textContent ?? null,
      rowIds: Array.from(document.querySelectorAll('[data-testid^="watch-row-"]')).map((e) => e.getAttribute('data-testid')),
      feedAge: document.querySelector('[data-testid="watch-feed-age"]')?.textContent ?? null,
    }));
    (R.item6 as any).afterAdd = rowsInfo;
    await page.screenshot({ path: `${OUTDIR}/06_watch_three_symbols.png` });
    const clicks: Record<string, unknown> = [];
    const ids = (rowsInfo.rowIds ?? []).slice(0, 3) as string[];
    for (const tid of ids) {
      const sym = tid.replace('watch-row-', '');
      await page.click(`[data-testid="${tid}"]`);
      await sleep(3000);
      const panels = await page.evaluate(() => {
        const g = (sel: string) => {
          const el = document.querySelector(sel);
          return el ? { symbol: el.getAttribute('data-symbol'), text: (el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 200) } : null;
        };
        return { chart: g('[data-testid="watch-chart"]'), orderbook: g('[data-testid="watch-orderbook"]'), summary: g('[data-testid="watch-summary"]'),
                 obRows: document.querySelectorAll('[data-testid="watch-orderbook-rows"] [class]').length };
      });
      (clicks as any[]).push({ clicked: sym, panels });
      await page.screenshot({ path: `${OUTDIR}/06_watch_click_${sym.replace(/[^\u0600-\u06EF\w]/g, '')}.png` });
    }
    (R.item6 as any).clicks = clicks;
    // عرض‌ها: 1366 و 1920 — overflow/RTL
    const widthChecks: Record<string, unknown> = {};
    for (const w of [1366, 1920]) {
      await page.setViewportSize({ width: w, height: 900 });
      await sleep(1500);
      widthChecks[w] = await page.evaluate(() => {
        const de = document.documentElement;
        const clipped: string[] = [];
        for (const leaf of Array.from(document.querySelectorAll('[data-testid="watch-market-workspace"] *, [data-testid="market-status-panel"]'))) {
          const t = (leaf.textContent ?? '').trim();
          if (t && leaf.scrollWidth - leaf.clientWidth > 1 && getComputedStyle(leaf).overflow !== 'visible' && t.length < 60) clipped.push(t.slice(0, 30));
        }
        const gridCols = getComputedStyle(document.querySelector('[data-testid="watch-chart"]')?.parentElement ?? document.body).gridTemplateColumns;
        return { pageOverflowX: de.scrollWidth - de.clientWidth, gridCols, clippedSample: [...new Set(clipped)].slice(0, 10) };
      });
      await page.screenshot({ path: `${OUTDIR}/06_watch_width_${w}.png` });
    }
    (R.item6 as any).widthChecks = widthChecks;
  }
} catch (e) {
  (R.item6 as any).error = String(e);
}

R.finishedAt = new Date().toISOString();
writeFileSync(`${OUTDIR}/probe_result.json`, JSON.stringify(R, null, 2), 'utf8');
console.log(JSON.stringify({ done: true, errors: (R.consoleErrors as string[]).length, item6subtabs: (R.item6 as any).subtabs }, null, 1));
await browser.close();
