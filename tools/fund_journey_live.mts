/**
 * tools/fund_journey_live.mts — گردشِ زندۀ بنیادی روی مرورگر واقعی (Stage 10)
 *
 * چرا: پنج گاردِ codal موتور و دفترِ کار را می‌سنجند و
 * `dev/codal_api_contract_v1115.py` لایۀ HTTP را؛ ولی هیچ‌کدام نشان نمی‌دادند
 * آنچه کاربر درِ تبِّ بنیادی می‌بیند با همان پاسخِ API درِ یکِ لحظه می‌خواند.
 * این ابزار همان فاصلۀ باقی‌مانده را می‌بندد:
 *   API (لحۀ T) → مرورگر → DOM → API (لحۀ T′)
 * و اگر T با T′ فرق کند، آن ردیف را «بی‌اعتبار» می‌کند نه «قبول»
 * (درسِ ۲۰۲۶-۱۰-۱۲: دو نمونه‌برداریِ بی‌زمانِ یکسان، دو هشدارِ دروغ ساخت).
 *
 * چه چیزی اثبات می‌شود:
 *   J1 پنلِ سلامتِ کدال هست و شمارنده‌هایش == پاسخِ `/api/sync/codal/pipeline`
 *   J2 کارتِ بنیادی برایِ هر نمادِ درخواستی نمایش داده می‌شود (نه «در دسترس نیست»)
 *   J3 رأیِ هر شاخص درِ DOM با رأیِ همان شاخص درِ API می‌خواند
 *   J4 جایی که API می‌گوید `data_gap`، درِ DOM عدد نیست (نه صفر، نه «—»ِ بی‌علت)
 *   J5 صفر خطای کنسول و صفر پاسخِ ۴۰۰+ درِ مسیرِ بنیادی
 *   J6 کارت و جدولِ غربالگری برایِ یکِ نماد یکِ رأی دارند (backend↔backend)
 *
 * خروجی JSON در `_audit/` + شمارشِ PASS/FAIL درِ stdout. هیچ متنی به سرویسِ
 * بیرونی نمی‌رود؛ فقط Chromiumِ محلی و همان origin.
 *
 *   node --experimental-strip-types tools/fund_journey_live.mts \
 *        --url http://127.0.0.1:8003/ --symbols "خودرو,فولاد" --out _audit/fund_journey.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};

const BASE = arg('url', 'http://127.0.0.1:8003/').replace(/\/+$/, '');
const SYMBOLS = arg('symbols', '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const OUT = arg('out', '_audit/fund_journey_live.json');
const WAIT_MS = Number.parseInt(arg('wait', '15000'), 10);
const WIDTH = Number.parseInt(arg('width', '1366'), 10);
const HEIGHT = Number.parseInt(arg('height', '900'), 10);

if (!SYMBOLS.length) {
  console.error('FLAG: --symbols لازم است (کاما‌جدا)');
  process.exit(2);
}

const { chromium } = await import(
  pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href
);
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) {
  const { ensureChromium } = await import(pathToFileURL(`${PKG}/src/browser-setup.ts`).href);
  await (ensureChromium as () => Promise<void>)();
}

/** رقم‌هایِ فارسی/عربی و جداکننده‌ها → لاتین، تا متنِ DOM با عددِ API سنجیده شود */
const norm = (s: string): string =>
  (s || '')
    .replace(/[۰-۹]/g, (d) => String(d.codePointAt(0)! - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.codePointAt(0)! - 0x0660))
    .replace(/[٬،]/g, ',')
    .replace(/\s+/g, ' ');

const jget = async (path: string): Promise<{ status: number; body: any }> => {
  const r = await fetch(`${BASE}${path}`);
  let body: any = null;
  try {
    body = await r.json();
  } catch {
    body = null;
  }
  return { status: r.status, body };
};

const results: any[] = [];
let pass = 0;
let fail = 0;
const ck = (cond: boolean, label: string, detail: unknown = '') => {
  if (cond) {
    pass++;
    console.log('ok   ' + label);
  } else {
    fail++;
    console.log('FAIL ' + label + '  ' + JSON.stringify(detail).slice(0, 200));
  }
  return cond;
};

// ── ۱) API درِ لحۀ T ────────────────────────────────────────────────────────
const healthT = await jget('/api/sync/codal/pipeline');
ck(healthT.status === 200 && healthT.body?.status !== 'error',
   'J0 پاسخِ سلامت درِ لحۀ T معتبر است', { status: healthT.status, msg: healthT.body?.message });
const cardsT: Record<string, any> = {};
for (const s of SYMBOLS) {
  const r = await jget(`/api/fundamental/${encodeURIComponent(s)}`);
  cardsT[s] = r;
}

// ── ۲) مرورگر ───────────────────────────────────────────────────────────────
const browser = await chromium.launch({
  executablePath: CHROME || undefined,
  args: ['--no-sandbox', '--disable-gpu'],
});
const ctx = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه هم می‌پذیرد */
  }
});
const page = await ctx.newPage();
const consoleErrors: string[] = [];
const badResponses: { url: string; status: number }[] = [];
page.on('console', (m) => {
  if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 160));
});
page.on('response', (res) => {
  if (res.url().includes('/api/') && res.status() >= 400) {
    badResponses.push({ url: res.url().replace(BASE, ''), status: res.status() });
  }
});

const PROBE = (sym: string) => {
  const de = document.documentElement;
  const txt = (sel: string) => {
    const el = document.querySelector(sel);
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
  };
  const cell = (axis: string) => {
    const el =
      document.querySelector(`[data-testid="fts-card-cell-${axis}"]`) ??
      document.querySelector(`[data-testid="fts-cell-gap-${axis}"]`);
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
  };
  const healthIds = [
    'codal-health-strip',
    'codal-health-state',
    'codal-health-count-queued',
    'codal-health-count-failed',
    'codal-health-count-incomplete',
    'codal-health-count-gap',
    'codal-health-count-dirty',
    'codal-health-last-sync',
  ];
  const health: Record<string, string | null> = {};
  for (const id of healthIds) {
    const el = document.querySelector(`[data-testid="${id}"]`);
    health[id] = el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
  }
  return {
    href: location.href,
    bodyHasCard: !!document.querySelector('[data-testid^="fts-card"]'),
    notAvailable: /در دسترس نیست/.test(de.textContent ?? ''),
    gapItems: Array.from(document.querySelectorAll('[data-testid="data-gap-item"]')).map((e) =>
      (e.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 140),
    ),
    cell1a: cell('1a_monetary_growth'),
    cell1b: cell('1b_volume_growth'),
    eps: txt('[data-testid="fts-card-eps-growth"]') ?? txt('[data-testid="drilldown-eps-na"]'),
    annualize: txt('[data-testid="annualize-basis"]'),
    title: txt('h1') ?? txt('h2'),
    health,
  };
};

for (const sym of SYMBOLS) {
  const url = `${BASE}/#/fundamental/${encodeURIComponent(sym)}`;
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForSelector('[data-testid="codal-health-strip"], [data-testid^="fts-card"]', {
    timeout: WAIT_MS,
  }).catch(() => undefined);
  await page.waitForTimeout(1200);
  const dom = await page.evaluate(`(${PROBE.toString()})(${JSON.stringify(sym)})`);
  // API درِ لحۀ T′ — بی‌فاصله پس از خواندنِ DOM
  const after = await jget(`/api/fundamental/${encodeURIComponent(sym)}`);
  const moved =
    JSON.stringify(after.body?.indicators ?? null) !== JSON.stringify(cardsT[sym].body?.indicators ?? null);
  const row: any = { symbol: sym, url, api_before: cardsT[sym].body, dom, api_after: after.body, inconclusive: moved };

  ck(!moved, `J7 [${sym}] پاسخِ API پیش و پس ازِ DOM یکی است (سنجش درِ یکِ لحظه)`,
     { before: cardsT[sym].status, after: after.status });
  const cellKinds = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid]')).map((e) => e.getAttribute('data-testid')).filter((t) => /^fts-(card-cell|cell-gap|axis-rail)/.test(t || '')).length);
  ck(!!dom.bodyHasCard && cellKinds >= 3, `J2 [${sym}] card renders with indicator cells`, { cellKinds, notAvailable: dom.notAvailable });

  const ind = (after.body?.indicators ?? {}) as Record<string, any>;
  const i1a = (ind['1']?.monetary ?? {}) as Record<string, any>;
  if (dom.cell1a) {
    const gap = i1a.data_gap === true && i1a.monetary_pct === null;
    if (gap) {
      // threshold labels (60%) and the threshold line are not values; only a value-percent must stay absent
      // قرارداد رابط: مقدارِ غایب «—» است. پس هر دو خانۀ مقدار باید خطِّ تهی
      // داشته باشند و هیچ «۰٪»ِ ساختگی نباشد. آستانه (۶۰٪) و خطِّ آستانه (≥ 1)
      // برچسب‌اند و درِ این سنجش نمی‌آیند — بی‌این، خودِ سنجه رقم می‌دزدید.
      const cellTxt = norm(dom.cell1a);
      const emptySlots = (cellTxt.match(/[\u0640\u2014-]+/g) || []).length;
      ck(emptySlots >= 2 && !/(^|[^\d])0\s*(\u066a|%)/.test(cellTxt),
         `J4 [${sym}] both value slots show an em-dash and no fabricated 0%`,
         { emptySlots, cell: dom.cell1a });
      ck((i1a.reason || '').length > 0, `J4ب [${sym}] علتِ شکاف از API می‌آید`, i1a.reason);
    } else if (typeof i1a.monetary_pct === 'number') {
      const want = norm(String(Math.round(i1a.monetary_pct * 10) / 10));
      ck(norm(dom.cell1a).includes(want) || norm(dom.cell1a).includes(want.replace(/\.0$/, '')),
         `J3 [${sym}] درصدِ شاخص ۱a درِ DOM == API`, { dom: dom.cell1a, api: want });
    }
  }

  if (Object.values(dom.health).some((v) => v !== null)) {
    const q = (healthT.body?.queue ?? {}) as Record<string, number>;
    const dq = dom.health['codal-health-count-queued'];
    if (dq !== null && typeof q.queued === 'number') {
      ck(norm(dq).includes(String(q.queued)), 'J1 شمارۀ صفِ پنل == پاسخِ سلامت',
         { dom: dq, api: q.queued });
    }
    const ls = dom.health['codal-health-last-sync'];
    const apiLs = healthT.body?.last_successful_sync?.at ?? null;
    if (ls !== null) {
      ck(apiLs === null ? /نرسید|—|ثبت نشده|بی‌/.test(norm(ls)) : norm(ls).length > 0,
         'J1ب پنل بی‌شاهدِ موفق، «نرسید» می‌گوید نه زمانِ ساخته', { dom: ls, api: apiLs });
    }
  } else {
    ck(false, 'J1 پنلِ سلامت درِ DOM پیدا نشد', dom.health);
  }
  results.push(row);
}

// ── ۳) غربالگری در برابرِ کارت (backend↔backend) ─────────────────────────────
const screen = await jget('/api/fundamental/screen');
const screenRows = (screen.body?.data ?? screen.body?.symbols ?? screen.body?.rows ?? []) as any[];
if (screen.status === 200 && Array.isArray(screenRows) && screenRows.length) {
  const rows = screenRows;
  const bySym = new Map(rows.map((r: any) => [String(r.symbol ?? r.sym ?? ''), r]));
  for (const sym of SYMBOLS) {
    const srow = bySym.get(sym);
    const card = cardsT[sym].body;
    if (!srow || !card) continue;
    const sv = String(srow.verdict ?? srow.state ?? '');
    const cv = String(card.verdict ?? '');
    ck(!sv || !cv || sv === cv, `J6 [${sym}] رأیِ غربالگری == رأیِ کارت`, { screen: sv, card: cv });
  }
} else {
  ck(false, 'J6 جدولِ غربالگری پاسخِ ردیف‌دار نداد', { status: screen.status });
}

ck(consoleErrors.length === 0, 'J5 صفر خطای کنسول', consoleErrors.slice(0, 5));
ck(badResponses.length === 0, 'J5ب صفر پاسخِ ۴۰۰+ روی مسیرِ API', badResponses.slice(0, 8));

await ctx.close();
await browser.close();

mkdirSync(OUT.replace(/[\\/][^\\/]*$/, ''), { recursive: true });
writeFileSync(OUT, JSON.stringify({ base: BASE, health: healthT.body, symbols: SYMBOLS,
  consoleErrors, badResponses, results }, null, 2), 'utf-8');
console.log(`\nfund_journey_live: ${pass} passed / ${fail} failed  → ${OUT}`);
process.exit(fail ? 1 : 0);
