// tools/hidden_why_chip_probe.mts — شاهدِ زندهٔ «درِ +N از خودِ ردیف‌هایِ پنهان می‌آید»
//
// چهار چیز در مرورگر ثابت می‌کند (نه در تستِ واحد):
//   1) هر چیپِ پنهان‌دار درها را با شمارِ خودشان می‌برد؛ جمعِ درها = +N = بجِ چیپ.
//   2) مجموعهٔ درهایِ هر چیپ با سنجشِ مستقلِ رویِ JSONِ خامِ /api/market می‌خواند
//      (شمار ممکن است فرق کند، چون فرانت فرمولِ الگو را با آستانهٔ کاربر می‌زند).
//   3) در نمایِ پیش‌فرض «نمادِ خاموش» ادعا نمی‌شود؛ با جستجو «جستجو» و با صنعتِ
//      انتخابی «صنعت» اضافه می‌شود؛ با خاموش‌کردنِ «فقط زنده» هیچ ردیفی به آن در
//      نسبت داده نمی‌شود.
//   4) console و pageerror صفر‌اند.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/hidden_why_chip_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/hidden_why_chip.json
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
const BASE = arg('url', 'http://127.0.0.1:5173/');
const OUT = arg('out', '_audit/hidden_why_chip.json');
const WAIT = Number(arg('wait', '20000'));

const DOORS = ['پسوندِ عددی', 'بازار/ابزارِ خاموش', 'نمادِ خاموش', 'صنعت', 'جستجو'];
const FA = '۰۱۲۳۴۵۶۷۸۹';
/** نخستین دستهٔ رقمِ فارسیِ متن را به عدد می‌برد */
const faNum = (s: string | null): number | null => {
  if (!s) return null;
  const m = s.match(/[۰-۹]+/);
  return m ? Number(m[0].replace(/[۰-۹]/g, (c) => String(FA.indexOf(c)))) : null;
};

const report: Record<string, unknown> = { base: BASE, steps: {}, errors: [], http: [], checks: [] };
const ck = (name: string, ok: boolean, detail: unknown = null) => {
  (report.checks as Record<string, unknown>[]).push({ name, ok, detail });
  return ok;
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: 1632, height: 950 } });
await context.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
    localStorage.removeItem('bors-symbol');
  } catch {
    /* دروازۀ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
  if (m.type() !== 'error') return;
  const url = m.location()?.url ?? '';
  // سروِ dev ویکت favicon.ico ندارد و مرورگر خودش آن را می‌خواهد؛ در اپِ نصب‌شده
  // همان مسیر به index.html می‌خورد (۲۰۰). صدایِ واقعیِ خطا نیست، پس از داوریِ
  // «console تمیز» بیرون نگه داشته می‌شود — هر خطایِ دیگری نامش ثبت می‌شود.
  if (url.endsWith('/favicon.ico')) return;
  (report.errors as string[]).push(`console: ${url} :: ${m.text().slice(0, 220)}`);
});
// آدرسِ پاسخ‌هایِ خطا را جدا می‌نویسد تا «console: 404» بی‌نام نماند
page.on('response', (r: { status: () => number; url: () => string }) => {
  if (r.status() >= 400) (report.http as string[]).push(`${r.status()} ${r.url()}`);
});

// هر چیپ = یک button با تولتیپِ «ردیفِ واجدِ شرط» + بجِ اختیاریِ +N
const READ = () =>
  page.evaluate(() => {
    const bar = document.querySelector('[data-testid="quick-filters-bar"]');
    if (!bar) return [];
    const chips = Array.from(bar.querySelectorAll('button')).filter((b) =>
      (b.getAttribute('title') ?? '').includes('ردیفِ واجدِ شرط'),
    );
    return chips.map((b) => {
      const nums = Array.from(b.querySelectorAll('.num'));
      const plus = nums.find((n) => (n.textContent ?? '').trim().startsWith('+'));
      return {
        label: (b.textContent ?? '').replace(/\s+/g, ' ').trim(),
        title: (b.getAttribute('title') ?? '').replace(/\s+/g, ' ').trim(),
        badge: plus ? (plus.textContent ?? '').trim() : null,
      };
    });
  });

type Chip = {
  label: string;
  title: string;
  badge: string | null;
  count: number | null;
  doors: Record<string, number>;
};

/** «… — ۱۸ ردیفِ واجدِ شرط … نیست (پسوندِ عددی ۱۸)» → +N و هر در با شمارشِ خودش */
const parseChips = (raw: Awaited<ReturnType<typeof READ>>): Chip[] =>
  raw.map((c) => {
    const doors: Record<string, number> = {};
    const paren = c.title.match(/\(([^)]*)\)\s*$/);
    for (const part of (paren ? paren[1] : '').split('،')) {
      const dm = part.trim().match(/^(.+?)\s+([۰-۹]+)$/);
      if (dm) doors[dm[1]] = faNum(dm[2]) ?? NaN;
    }
    return { ...c, count: faNum(c.title), doors };
  });

// سنجشِ مستقل رویِ JSONِ خام: همان رتبهٔ درها، با پرچمِ خامِ بک‌اند
const readFeed = () =>
  page.evaluate(async () => {
  const res = await fetch('/api/market', { headers: { accept: 'application/json' } });
  const j: any = await res.json();
  const rows: any[] = j.data ?? j;
  const FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];
  const ZWNJ = new RegExp(String.fromCharCode(0x200c), 'g');
  const norm = (s: string) => (s ?? '').replace(ZWNJ, '').replace(/ي/g, 'ی');
  const suffix = (s: string) => /[0-9۰-۹]$/.test((s ?? '').trim());
  const classify = (d: any): string => {
    const name = norm(d.name);
    const sym = norm(d.symbol).toUpperCase();
    const sec = norm(d.sector_name);
    if (sym.startsWith('ض') || (sym.startsWith('ط') && !sym.startsWith('طال'))) return 'option';
    if (name.includes('صندوق') || name.includes('ETF') || sec.includes(norm('صندوق سرمايه'))) return 'fund';
    if (
      sym.startsWith('اخزا') || sym.startsWith('اراد') || sym.startsWith('افاد') || sym.startsWith('گام') ||
      name.includes('اوراق') || name.includes('اسناد') || sec.includes(norm('اوراق تامين'))
    )
      return 'bond';
    if (sym.endsWith('ح') || name.includes('حق تقدم')) return 'right';
    if (sym.startsWith('تسه') || sym.startsWith('تملی') || name.includes('تسهیلات')) return 'teseh';
    if (sym.startsWith('طال') || sym.includes('TAL')) return 'tal';
    if (name.includes('آتی') && /[0-9]$/.test(sym)) return 'ati';
    if (sec.includes('کالا') || sym.includes('سلف') || name.includes('سلف')) return 'kala';
    if (sec.includes('انرژی') || sec.includes('برق') || name.includes('انرژی')) return 'energy';
    if (Number(d.board) === 2) return 'payeh';
    return 'stock';
  };
  const DEFAULTS = ['stock', 'payeh', 'right', 'energy', 'fund'];
  const inDefault = (r: any) => DEFAULTS.includes(classify(r));
  const doorOf = (r: any): string | null => {
    if (suffix(r.symbol)) return 'پسوندِ عددی';
    if (!inDefault(r)) return 'بازار/ابزارِ خاموش';
    if (r.is_live === false) return 'نمادِ خاموش';
    return null;
  };
  const perFlag: Record<string, { count: number; doors: Record<string, number> }> = {};
  for (const f of FLAGS) perFlag[f] = { count: 0, doors: {} };
  let hiddenRows = 0;
  let flaggedDead = 0;
  for (const r of rows) {
    if (!suffix(r.symbol) && inDefault(r) && r.is_live !== false) continue;
    hiddenRows += 1;
    const d = doorOf(r);
    for (const f of FLAGS) {
      if (r[f] !== true) continue;
      perFlag[f].count += 1;
      if (d) perFlag[f].doors[d] = (perFlag[f].doors[d] ?? 0) + 1;
      if (d === 'نمادِ خاموش') flaggedDead += 1;
    }
  }
  return { rows: rows.length, hiddenRows, flaggedDead, perFlag };
});

const LABEL_TO_FLAG: Record<string, string> = {
  'الگوی ساعت': 'f_clock',
  'حجم مشکوک': 'f_susp',
  'فیلتر جت': 'f_jet',
  'کف‌روبی': 'f_roobi',
  'نقطه زنی': 'f_noqteh',
};
const flagOf = (c: Chip): string | null => {
  const key = Object.keys(LABEL_TO_FLAG).find((k) => c.title.startsWith(k) || c.label.startsWith(k));
  return key ? LABEL_TO_FLAG[key] : null;
};

await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="quick-filters-bar"]', { timeout: WAIT });
// یک چرخۀِ کاملِ داده + شمارشِ چیپ‌ها
await page.waitForFunction(
  () =>
    Array.from(document.querySelectorAll('[data-testid="quick-filters-bar"] button')).some((b) =>
      (b.getAttribute('title') ?? '').includes('ردیفِ واجدِ شرط'),
    ),
  {},
  { timeout: WAIT },
);

const def = parseChips(await READ());
report.steps.default = def;
const FEED = await readFeed();
report.feed = FEED;
ck('حداقل یک چیپ ردیفِ پنهان دارد', def.length > 0, def.map((c) => c.label));
ck(
  'هر در شناخته‌شده است و با شمارِ بی‌صفر',
  def.every((c) => Object.keys(c.doors).every((d) => DOORS.includes(d) && c.doors[d] > 0)),
  def.map((c) => c.doors),
);
ck(
  'جمعِ درها = +N = بجِ رویِ همان چیپ',
  def.every((c) => {
    const sum = Object.values(c.doors).reduce((a, b) => a + b, 0);
    return sum === c.count && faNum(c.badge) === c.count;
  }),
  def.map((c) => ({ label: c.label, count: c.count, badge: c.badge, doors: c.doors })),
);
ck(
  'درِ «نمادِ خاموش» بی‌سهم نام برده نمی‌شود',
  def.every((c) => !(c.doors['نمادِ خاموش'] > 0)),
  def.map((c) => c.doors),
);

// مجموعهٔ درها باید با سنجشِ مستقل یکی باشد؛ شمارِ کل ممکن است با آستانهٔ کاربر
// فرق کند، چون فرانت فرمولِ الگو را دوباره می‌زند.
const drift: Record<string, unknown> = {};
for (const c of def) {
  const flag = flagOf(c);
  const mine = flag ? FEED.perFlag[flag] : null;
  if (!mine) {
    drift[c.label] = 'no independent flag match';
    continue;
  }
  drift[flag] = {
    domCount: c.count,
    feedCount: mine.count,
    domDoors: Object.keys(c.doors),
    feedDoors: Object.keys(mine.doors),
    sameDoors:
      JSON.stringify(Object.keys(c.doors).sort()) === JSON.stringify(Object.keys(mine.doors).sort()),
  };
}
report.drift = drift;
ck(
  'مجموعهٔ درهایِ هر چیپ با سنجشِ مستقل یکی است',
  Object.values(drift).every((v: any) => v.sameDoors),
  drift,
);

// ── حالتِ دو: جستجو ────────────────────────────────────────────────────────
await page.fill('input[aria-label="جستجوی نماد"]', 'پتروشیمی');
await page.waitForTimeout(1400);
const search = parseChips(await READ());
report.steps.search = search;
ck(
  'با جستجو، درِ «جستجو» به یکی از چیپ‌ها اضافه شد',
  search.some((c) => c.doors['جستجو'] > 0),
  search.map((c) => c.doors),
);

// ── حالتِ سه: صنعت ─────────────────────────────────────────────────────────
await page.fill('input[aria-label="جستجوی نماد"]', '');
await page.waitForTimeout(1000);
const sectorName = await page.evaluate(() => {
  const opts = Array.from(
    document.querySelectorAll('select[aria-label="فیلتر صنعت"] option'),
  ) as HTMLOptionElement[];
  const pick = opts.find((o) => o.value && !o.value.startsWith('همه'));
  return pick ? pick.value : null;
});
if (sectorName) {
  await page.selectOption('select[aria-label="فیلتر صنعت"]', sectorName);
  await page.waitForTimeout(1400);
  const bySector = parseChips(await READ());
  report.steps.sector = { sectorName, chips: bySector };
  ck(
    'با صنعتِ انتخابی، درِ «صنعت» اضافه شد',
    bySector.some((c) => c.doors['صنعت'] > 0),
    bySector.map((c) => c.doors),
  );
  await page.selectOption('select[aria-label="فیلتر صنعت"]', '');
  await page.waitForTimeout(1000);
} else {
  report.steps.sector = 'no sector option in feed';
}

// ── حالتِ چهار: «فقط زنده» خاموش → هیچ ردیفی به آن در نسبت داده نمی‌شود ─────
await page.click('[data-testid="live-only-toggle"]');
await page.waitForTimeout(1400);
const liveOff = parseChips(await READ());
report.steps.liveOff = liveOff;
ck(
  'با خاموش‌کردنِ «فقط زنده» هیچ ردیفی به آن در نسبت داده نمی‌شود',
  liveOff.every((c) => !(c.doors['نمادِ خاموش'] > 0)),
  liveOff.map((c) => c.doors),
);
await page.click('[data-testid="live-only-toggle"]');

const failed = (report.checks as any[]).filter((c) => !c.ok);
report.verdict = failed.length === 0 && (report.errors as string[]).length === 0 ? 'PASS' : 'FAIL';
report.failed = failed.map((f) => f.name);

mkdirSync(OUT.split('/').slice(0, -1).join('/'), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ verdict: report.verdict, checks: report.checks, errors: report.errors }, null, 2));
await browser.close();
