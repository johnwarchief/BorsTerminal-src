// tools/funnel_chain_probe.mts — شاهدِ زندهٔ دو ادعای Ruling #2 روی اپِ واقعی (نه jsdom)
//
//  §۱A — تختهٔ بازار: چند فیلتر = اشتراک (AND)، نه اجتماع (OR).
//      «حجم مشکوک» و «کد به کد حقوقی به حقیقی» را روی #/market می‌زند و از شمارندۀ
//      واقعیِ جدول می‌خواند: N_both ≤ min(N_susp, N_legal)؛ چون اجتماع N_both ≥ max
//      می‌داد، نامساوی دوم سنسورِ ضدهماست (اگر شمارِ دو مجموعه یکی بود این تفکیک
//      ممکن نیست و صریح vacuous ثبت می‌شود). برگشتِ شمارش به N0 با خاموش‌کردنِ هر دو
//      و تکرارپذیری در سه ترتیبِ متفاوتِ کلیک، سنسور را زنده نگه می‌دارد.
//
//  §۱B — قیفِ FTS روی #/master: اجرای ترتیبی — هر گره فقط روی بازماندگانِ گرهٔ قبلی
//      می‌نشیند. کلیدهای نوارِ «زنجیرۀ اجرا» با تغییرِ preset مو‌به‌مو عوض می‌شوند و
//      بازماندگان در هر خوانش نایکنواست؛ آخرین گرهٔ نواری == «نشانه»ی درِ ورودی و
//      گرهِ universe == شمارِ اولِ همان در (هر دو از یک اسنپ‌شاتِ DOM خوانده می‌شوند).
//      چیپ‌های روشنی که از تخته روشن مانده‌اند (f_susp, f_legal) نباید در زنجیرِ
//      preset نشت کنند — مجموعهٔ کلیدها مو‌به‌مو چک می‌شود.
//
//  §۱C — شاخهٔ دستی روی #/strategy-tree: دکمهٔ چهارمِ «مسیر سفارشی (انتخاب دستی)»
//      همان preset=custom است و چیپ‌های تخته را از استور می‌خواند؛ فاز ۳ این را زنده
//      می‌سنجد: با هر دو چیپ روشن عددِ نوار برابرِ اشتراکِ تخته است، با خاموش‌کردنِ
//      «کد به کد» به یک‌فیلترهٔ تخته می‌رسد، و با swing عوض می‌شود — دوطرفه.
//
//  صداقتِ دامنه (حکمِ مالک، Option A): تنها تکهٔ راستی‌آزمایی‌نشده، رشتهٔ درِ خودِ
//  پنلِ قیف برای custom است («چیپ‌هایِ روشنِ تبِ تابلو — همه با هم») — عمداً
//  live-reachable نشد: custom به horizon آن پنل اضافه نمی‌شود و دامنهٔ UI تازه ساخته
//  نمی‌شود. معناشناسیِ custom+چیپ‌ها روی صفحهٔ درخت زنده اثبات می‌شود (فاز ۳)؛
//  پوششِ همان رشته فقط تستِ واحد است (fts-funnel-stages.spec) و live-unverified
//  می‌ماند.
//
//   JEV_CHROME='<chrome.exe>' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/funnel_chain_probe.mts \
//     --url http://127.0.0.1:5173/ --out _audit/funnel_chain_probe.json
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
const OUT = arg('out', '_audit/funnel_chain_probe.json');
const WAIT = Number(arg('wait', '45000'));
const DIR = OUT.split('/').slice(0, -1).join('/') || '.';
mkdirSync(DIR, { recursive: true });

// ارقامِ فارسی از نقطه‌کد ساخته می‌شوند تا ویرایشِ اسکریپتی رقم را ندزدد
const FA = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d)).join('');
const FAD = '[' + FA[0] + '-' + FA[9] + ']';
const FA_RE = new RegExp(FAD + '+');
const ZWNJ_RE = new RegExp(String.fromCharCode(0x200c), 'g');
const norm = (s: string | null): string =>
  (s ?? '').replace(ZWNJ_RE, '').replace(/\u064a/g, '\u06cc').replace(/\s+/g, ' ').trim();
const faNum = (s: string | null): number | null => {
  const m = (s ?? '').match(FA_RE);
  if (!m) return null;
  return Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

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
    // تنظیمِ «حذفِ پسوندِ عددی» ماندگار است؛ سنجش باید از کلیدِ پاک شروع کند
    localStorage.removeItem('bors_tape_show_numeric_suffix_v1');
    // وضعیتِ تازهٔ انتخابیِ قیف: horizon پیش‌فرض trend و حالتِ پیش‌فرض reverse
    localStorage.removeItem('fts.strategy.horizon.v1');
    localStorage.removeItem('fts.funnel.prefs.v1');
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
  // همان مسیر به index.html می‌خورد (۲۰۰). صدایِ واقعیِ خطا نیست.
  if (url.endsWith('/favicon.ico')) return;
  (report.errors as string[]).push(`console: ${url} :: ${m.text().slice(0, 220)}`);
});
page.on('response', (r: { status: () => number; url: () => string }) => {
  if (r.status() >= 400) (report.http as string[]).push(`${r.status()} ${r.url()}`);
});

// ── چیپ‌های تخته ────────────────────────────────────────────────────────────
const CHIP_SUSP = 'حجم مشکوک';
const CHIP_LEGAL = 'کد به کد حقوقی به حقیقی';

const chipPressed = (label: string): Promise<string | null> =>
  page.evaluate((needle) => {
    const bar = document.querySelector('[data-testid="quick-filters-bar"]');
    if (!bar) return null;
    const z = new RegExp(String.fromCharCode(0x200c), 'g');
    const n = (s: string) => (s ?? '').replace(z, '').replace(/\s+/g, ' ').trim();
    const btn = Array.from(bar.querySelectorAll('button[aria-pressed]')).find((b) => n(b.textContent ?? '').includes(needle));
    return btn ? btn.getAttribute('aria-pressed') : null;
  }, label);

const clickChip = async (label: string): Promise<void> => {
  const hit = await page.evaluate((needle) => {
    const bar = document.querySelector('[data-testid="quick-filters-bar"]');
    if (!bar) return false;
    const z = new RegExp(String.fromCharCode(0x200c), 'g');
    const n = (s: string) => (s ?? '').replace(z, '').replace(/\s+/g, ' ').trim();
    const btn = Array.from(bar.querySelectorAll('button[aria-pressed]')).find((b) => n(b.textContent ?? '').includes(needle));
    if (!btn) return false;
    (btn as unknown as HTMLElement).click();
    return true;
  }, label);
  if (!hit) throw new Error(`chip not found: ${label}`);
};

const setChip = async (label: string, on: boolean): Promise<void> => {
  const pressed = (await chipPressed(label)) === 'true';
  if (pressed === on) return;
  await clickChip(label);
  for (let i = 0; i < 10; i++) {
    if (((await chipPressed(label)) === 'true') === on) return;
    await sleep(200);
  }
};

// ── شمارشگرِ جدول — تا سه خوانشِ پیاپیِ یکسان صبر می‌کند ─────────────────────
const shownCount = async (): Promise<number | null> => {
  const raw = await page.evaluate(() => {
    const el = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
    return el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
  });
  return faNum(raw);
};

const readCountStable = async (): Promise<number | null> => {
  let last: number | null = null;
  let same = 0;
  for (let i = 0; i < 16; i++) {
    const v = await shownCount();
    if (v != null && v === last) {
      same += 1;
      if (same >= 3) return v;
    } else {
      same = 0;
    }
    last = v;
    await sleep(350);
  }
  return last;
};

// ── خوانشِ زنجیرۀ قیف (یک اسنپ‌شات: در + گره‌ها + پوششِ تکنیکال) ─────────────
const readChain = () =>
  page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('[data-testid^="funnel-chain-"]')).map((el) => ({
      key: (el.getAttribute('data-testid') ?? '').replace('funnel-chain-', ''),
      numText: el.querySelector('.num')?.textContent ?? null,
      title: el.getAttribute('title') ?? '',
    }));
    const door = document.querySelector('[data-testid="funnel-door-label"]');
    const chain = document.querySelector('[data-testid="funnel-tape-chain"]');
    const coverage = Array.from(document.querySelectorAll('[data-testid="funnel-tech-coverage"]')).map((el) =>
      (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
    );
    return {
      nodes,
      doorText: door ? (door.textContent ?? '').replace(/\s+/g, ' ').trim() : null,
      chainTitle: (chain?.getAttribute('title') ?? '') as string,
      coverage,
    };
  });

type Preset = 'trend' | 'swing';
const KEYS: Record<Preset, string[]> = {
  trend: ['universe', 'f_roobi', 'f_noqteh', 'technical', 'fundamental', 'handover'],
  swing: ['universe', 'f_clock', 'f_jet', 'f_susp', 'technical', 'fundamental', 'handover'],
};

type Snap = {
  preset: string;
  keys: string[];
  nums: (number | null)[];
  titles: string[];
  doorText: string | null;
  door: { boardScope: number | null; entries: number | null } | null;
  chainTitle: string;
  coverage: string[];
};

const makeSnap = (preset: string, read: Awaited<ReturnType<typeof readChain>>): Snap => {
  const nodes = read.nodes.map((n) => ({ key: n.key, num: faNum(n.numText), title: n.title }));
  const last = norm(read.doorText).split('\u00b7').pop() ?? '';
  const m = last.match(new RegExp('از\\s*(' + FAD + '+)[^،]*،\\s*(' + FAD + '+)\\s*نشانه'));
  return {
    preset,
    keys: nodes.map((n) => n.key),
    nums: nodes.map((n) => n.num),
    titles: nodes.map((n) => n.title),
    doorText: read.doorText,
    door: m ? { boardScope: faNum(m[1]), entries: faNum(m[2]) } : null,
    chainTitle: read.chainTitle,
    coverage: read.coverage,
  };
};

const monotone = (nums: (number | null)[]): boolean => {
  if (nums.length === 0 || nums.some((n) => n == null)) return false;
  for (let i = 1; i < nums.length; i++) {
    if ((nums[i] as number) > (nums[i - 1] as number)) return false;
  }
  return true;
};

const keysEqual = (keys: string[], expected: readonly string[]): boolean =>
  keys.length === expected.length && keys.every((k, i) => k === expected[i]);

const lastTapeOf = (s: Snap): { key: string; num: number | null } | null => {
  const i = s.keys.findIndex((k) => k === 'technical');
  if (i <= 0) return null;
  return { key: s.keys[i - 1], num: s.nums[i - 1] };
};
const universeOf = (s: Snap): number | null => (s.keys[0] === 'universe' ? (s.nums[0] ?? null) : null);

const crossOk = (s: Snap): boolean => {
  const lt = lastTapeOf(s);
  const un = universeOf(s);
  return s.door != null && lt != null && un != null && lt.num != null && s.door.boardScope === un && s.door.entries === lt.num;
};

const doorHas = (s: Snap, needle: string): boolean => norm(s.doorText).includes(norm(needle));

const waitKeys = async (preset: Preset): Promise<boolean> => {
  try {
    await page.waitForFunction(
      (expected) => {
        const keys = Array.from(document.querySelectorAll('[data-testid^="funnel-chain-"]')).map((el) =>
          (el.getAttribute('data-testid') ?? '').replace('funnel-chain-', ''),
        );
        return keys.length === expected.length && keys.every((k, i) => k === expected[i]);
      },
      [...KEYS[preset]],
      { timeout: WAIT },
    );
    return true;
  } catch {
    return false;
  }
};

const settleTech = async (): Promise<boolean> => {
  try {
    await page.waitForFunction(
      (needle) => {
        const z = new RegExp(String.fromCharCode(0x200c), 'g');
        return !(document.body.textContent ?? '').replace(z, '').includes(needle);
      },
      norm('تکنیکال در حالِ خواندن'),
      { timeout: 60000 },
    );
    return false;
  } catch {
    return true;
  }
};

// ── فاز ۱: تختهٔ بازار — AND نه OR ──────────────────────────────────────────
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="quick-filters-bar"]', { timeout: WAIT });
await page.waitForFunction(
  (fa) => {
    const el = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
    if (!el) return false;
    for (const ch of el.textContent ?? '') {
      const d = fa.indexOf(ch);
      if (d >= 0) return d > 0;
    }
    return false;
  },
  FA,
  { timeout: WAIT },
);

const pressed0 = { susp: await chipPressed(CHIP_SUSP), legal: await chipPressed(CHIP_LEGAL) };
await setChip(CHIP_SUSP, false);
await setChip(CHIP_LEGAL, false);
const N0 = await readCountStable();
await setChip(CHIP_SUSP, true);
const N_susp = await readCountStable();
await setChip(CHIP_LEGAL, true);
const N_both = await readCountStable();
await page.screenshot({ path: `${DIR}/funnel_chain_market.png` });
await setChip(CHIP_SUSP, false);
const N_legal = await readCountStable();
await setChip(CHIP_LEGAL, false);
const N0back = await readCountStable();
await setChip(CHIP_LEGAL, true);
await setChip(CHIP_SUSP, true);
const N_both2 = await readCountStable();
await setChip(CHIP_SUSP, false);
await setChip(CHIP_SUSP, true);
const N_both3 = await readCountStable();
const pressedEnd = { susp: await chipPressed(CHIP_SUSP), legal: await chipPressed(CHIP_LEGAL) };

const bb = { pressed0, N0, N_susp, N_legal, N_both, N_both2, N_both3, N0back, pressedEnd };
report.steps.board = bb;
ck('تخته: هر دو چیپ پیش از سنجش خاموش بودند', pressed0.susp === 'false' && pressed0.legal === 'false', pressed0);
ck(
  'تخته: همهٔ خوانش‌ها عددی شدند (سنسور کور نیست)',
  [N0, N_susp, N_legal, N_both, N_both2, N_both3, N0back].every((n) => n != null),
  bb,
);
ck(
  'تخته: هر فیلتر تنها ≤ بی‌فیلتر',
  N0 != null && N_susp != null && N_legal != null && N_susp <= N0 && N_legal <= N0,
  bb,
);
ck(
  'تخته: N_both ≤ min(N_susp، N_legal) — اشتراک، نه اجتماع',
  N_both != null && N_susp != null && N_legal != null && N_both <= Math.min(N_susp, N_legal),
  bb,
);
const vacuous = N_susp === N_legal;
ck(
  'تخته: اجتماع رد می‌شود (N_both < max یا دو مجموعه در شمار یکی و تفکیک‌ناپذیر است)',
  N_both != null && N_susp != null && N_legal != null && (N_both < Math.max(N_susp, N_legal) || (vacuous && N_both === N_susp)),
  { ...bb, vacuous },
);
ck(
  'تخته: دست‌کم یک فیلتر واقعاً ردیف می‌ریزد (سنجش خلأ نیست)',
  N0 != null && N_susp != null && N_legal != null && (N_susp < N0 || N_legal < N0),
  bb,
);
ck('تخته: خاموش‌کردنِ هر دو → برگشت دقیق به N0', N0back === N0 && N0 != null, bb);
ck(
  'تخته: تکرارپذیری — N_both2 = N_both3 = N_both در سه ترتیبِ کلیک',
  N_both != null && N_both2 === N_both && N_both3 === N_both,
  bb,
);
ck(
  'تخته: در پایان هر دو چیپ روشن ماندند (برای آزمونِ نشت به قیف)',
  pressedEnd.susp === 'true' && pressedEnd.legal === 'true',
  pressedEnd,
);

// ── فاز ۲: قیف — زنجیرِ ترتیبی ──────────────────────────────────────────────
await page.evaluate(() => {
  location.hash = '#/master';
});
await page.waitForSelector('[data-testid="funnel-tape-chain"]', { timeout: WAIT });
await page.waitForSelector('[data-testid="funnel-door-label"]', { timeout: WAIT });
// قالبِ در («از N نمادِ زندهٔ تابلو، M نشانه») قالبِ حالتِ مهندسیِ معکوس است؛
// قفلش می‌کنیم تا تغییرِ بی‌صدای پیش‌فرضِ استور، قالب را عوض نکند.
if (!(await page.$('[data-testid="funnel-mode-reverse"][aria-pressed="true"]'))) {
  await page.click('[data-testid="funnel-mode-reverse"]');
  await page.waitForSelector('[data-testid="funnel-mode-reverse"][aria-pressed="true"]', { timeout: WAIT });
}

const read0 = await readChain();
const initial: Preset | null = norm(read0.doorText).includes(norm('شخص روندگیر'))
  ? 'trend'
  : norm(read0.doorText).includes(norm('شخص نوسانگیر'))
    ? 'swing'
    : null;
report.steps.funnelInitial = {
  preset: initial,
  doorText: read0.doorText,
  keys: read0.nodes.map((n) => n.key),
  coverage: read0.coverage,
};
ck('قیف: preset اولیه از درِ ورودی تشخیص داده شد', initial != null, read0.doorText);

if (initial) {
  const initSettleTimeout = await settleTech();
  const initKeysOk = await waitKeys(initial);
  await sleep(300);
  const snap1 = makeSnap(initial, await readChain());
  await sleep(4000);
  const snap2 = makeSnap(initial, await readChain());
  report.steps.chainInit = { snap1, snap2, initSettleTimeout };
  ck(
    `قیف ${initial}: کلیدهای زنجیر مو‌به‌مو`,
    initKeysOk && keysEqual(snap1.keys, KEYS[initial]),
    { expected: KEYS[initial], got: snap1.keys },
  );
  ck(`قیف ${initial}: بازماندگان نایکنواست (خوانش ۱)`, monotone(snap1.nums), snap1.nums);
  ck(`قیف ${initial}: بازماندگان نایکنواست (خوانش ۲، ۴ ثانیه بعد)`, monotone(snap2.nums), snap2.nums);
  ck(
    `قیف ${initial}: در و زنجیر می‌خوانند (universe=boardScope، نشانه=آخرین گرهٔ نواری، نامِ preset در در)`,
    crossOk(snap2) && doorHas(snap2, initial === 'trend' ? 'شخص روندگیر' : 'شخص نوسانگیر'),
    { door: snap2.door, universe: universeOf(snap2), lastTape: lastTapeOf(snap2), doorText: snap2.doorText },
  );
  ck(
    'قیف: عنوانِ نوار «اجرای ترتیبی» را می‌گوید',
    norm(snap2.chainTitle).includes(norm('اجرای ترتیبی')),
    snap2.chainTitle,
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_master_${initial}.png` });

  const other: Preset = initial === 'trend' ? 'swing' : 'trend';
  await page.click(`[data-testid="funnel-preset-${other}"]`);
  const otherKeysOk = await waitKeys(other);
  const otherSettleTimeout = await settleTech();
  await sleep(300);
  const snap3 = makeSnap(other, await readChain());
  report.steps.chainOther = { preset: other, snap3, otherSettleTimeout };
  ck(
    `قیف ${other}: پس از تغییرِ preset کلیدها مو‌به‌مو عوض شدند`,
    otherKeysOk && keysEqual(snap3.keys, KEYS[other]),
    { expected: KEYS[other], got: snap3.keys },
  );
  ck(
    `قیف ${other}: نامِ preset تازه در در`,
    doorHas(snap3, other === 'trend' ? 'شخص روندگیر' : 'شخص نوسانگیر'),
    snap3.doorText,
  );
  ck(`قیف ${other}: بازماندگان نایکنواست`, monotone(snap3.nums), snap3.nums);
  ck(
    `قیف ${other}: در و زنجیر می‌خوانند`,
    crossOk(snap3),
    { door: snap3.door, universe: universeOf(snap3), lastTape: lastTapeOf(snap3) },
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_master_${other}.png` });

  await page.click(`[data-testid="funnel-preset-${initial}"]`);
  const backOk = await waitKeys(initial);
  ck('قیف: برگشت به preset اولیه کلیدها را برمی‌گرداند (کنترل دوطرفه)', backOk, { expected: KEYS[initial] });
}

// ── فاز ۳: شاخهٔ دستی روی #/strategy-tree — معناشناسیِ custom+چیپها، زنده ─────
//  §۱C: دکمهٔ چهارمِ «مسیر سفارشی (انتخاب دستی)» preset=custom را زنده می‌کند و
//  چیپ‌های تخته از استور خوانده می‌شوند؛ این‌جا ثابت می‌شود عددِ نوار (سرِ نوار،
//  جعبهٔ Universe و «ورودی» گام ۱) با اشتراکِ دو فیلترِ تخته یکی است، با خاموش‌کردنِ
//  یک چیپ به عددِ یک‌فیلتره می‌رسد، و با swing عوض می‌شود — دوطرفه، با بستنِ حلقه.
const treeStep: Record<string, unknown> = {};
report.steps.tree = treeStep;

const TREE_SWING = 'شخص نوسان‌گیر';
const TREE_CUSTOM = 'مسیر سفارشی';

// nz = حذفِ ZWNJ و همهٔ فاصله‌ها از دو سو تا محلِ اتصالِ واژه‌ها سنسور را کور نکند
const treePreset = (needle: string): Promise<{ found: boolean; selected: boolean }> =>
  page.evaluate((raw) => {
    const z = new RegExp(String.fromCharCode(0x200c), 'g');
    const nz = (s: string) => (s ?? '').replace(z, '').replace(/\s+/g, '');
    const scope = document.querySelector('[data-testid="tree-preset-label"]')?.parentElement ?? document.body;
    const btn = Array.from(scope.querySelectorAll('button')).find((b) => nz(b.textContent ?? '').includes(nz(raw)));
    if (!btn) return { found: false, selected: false };
    return { found: true, selected: /font-black/.test(btn.className) };
  }, needle);

const clickTreePreset = async (needle: string): Promise<void> => {
  const hit = await page.evaluate((raw) => {
    const z = new RegExp(String.fromCharCode(0x200c), 'g');
    const nz = (s: string) => (s ?? '').replace(z, '').replace(/\s+/g, '');
    const scope = document.querySelector('[data-testid="tree-preset-label"]')?.parentElement ?? document.body;
    const btn = Array.from(scope.querySelectorAll('button')).find((b) => nz(b.textContent ?? '').includes(nz(raw)));
    if (!btn) return false;
    (btn as unknown as HTMLElement).click();
    return true;
  }, needle);
  if (!hit) throw new Error('tree preset button not found');
};

const selectTreePreset = async (needle: string): Promise<boolean> => {
  await clickTreePreset(needle);
  for (let i = 0; i < 25; i++) {
    const st = await treePreset(needle);
    if (st.found && st.selected) return true;
    await sleep(120);
  }
  return false;
};

const waitTreeHeader = async (mode: 'eq' | 'ne', target: number | null): Promise<boolean> => {
  if (target == null) return false;
  try {
    await page.waitForFunction(
      (args: { mode: string; target: number }) => {
        const faD = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d));
        const faRe = new RegExp('[' + faD[0] + '-' + faD[9] + ']+');
        const el = Array.from(document.querySelectorAll('span')).find((s) =>
          (s.textContent ?? '').replace(/\s+/g, ' ').trim().startsWith('کل Universe بازار'),
        );
        if (!el) return false;
        const m = (el.textContent ?? '').match(faRe);
        if (!m) return false;
        const v = Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
        return args.mode === 'eq' ? v === args.target : v !== args.target;
      },
      { mode, target },
      { timeout: WAIT },
    );
    return true;
  } catch {
    return false;
  }
};

const readTreeStrip = () =>
  page.evaluate(() => {
    const faD = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d));
    const faRe = new RegExp('[' + faD[0] + '-' + faD[9] + ']+');
    const num = (s: string | null | undefined): number | null => {
      const m = (s ?? '').match(faRe);
      if (!m) return null;
      return Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
    };
    const headerEl = Array.from(document.querySelectorAll('span')).find((s) =>
      (s.textContent ?? '').replace(/\s+/g, ' ').trim().startsWith('کل Universe بازار'),
    );
    const headerNum = num(headerEl?.textContent ?? null);
    const region = Array.from(document.querySelectorAll('[role="region"]')).find((r) =>
      (r.textContent ?? '').replace(/\s+/g, ' ').includes('کل بازار'),
    );
    if (!region) return { missing: true, headerNum, universeBig: null, tapeIn: null, tapePass: null, tapeRej: null };
    const boxes = Array.from(region.children) as HTMLElement[];
    const universeBig = num(boxes[0]?.querySelector('span.text-lg')?.textContent ?? null);
    const tapeBox = boxes[1];
    const tapePass = num(tapeBox?.querySelector('span.text-lg')?.textContent ?? null);
    const tapeText = (tapeBox?.textContent ?? '').replace(/\s+/g, ' ');
    const inM = tapeText.match(new RegExp('ورودی:\\s*([' + faD[0] + '-' + faD[9] + ']+)'));
    const rejM = tapeText.match(new RegExp('رد:\\s*([' + faD[0] + '-' + faD[9] + ']+)'));
    const faN = (g: string | undefined): number | null =>
      g ? Number(g.split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join('')) : null;
    return {
      missing: false,
      headerNum,
      universeBig,
      tapeIn: faN(inM?.[1]),
      tapePass,
      tapeRej: faN(rejM?.[1]),
    };
  });

const gotoTreePage = async (): Promise<void> => {
  await page.evaluate(() => {
    location.hash = '#/strategy-tree';
  });
  await page.waitForSelector('[data-testid="tree-preset-label"]', { timeout: WAIT });
};

const gotoMarketAnchor = async (): Promise<void> => {
  await page.evaluate(() => {
    location.hash = '#/market';
  });
  await page.waitForSelector('[title="تعداد نمادهای فعال در جدول"]', { timeout: WAIT });
  await page.waitForFunction(
    (fa) => {
      const el = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
      if (!el) return false;
      for (const ch of el.textContent ?? '') {
        const d = fa.indexOf(ch);
        if (d >= 0) return d > 0;
      }
      return false;
    },
    FA,
    { timeout: WAIT },
  );
};

try {
  // لنگرِ تخته: هر دو چیپ از فاز ۱ روشن مانده‌اند
  await gotoMarketAnchor();
  const chipsAnchor = { susp: await chipPressed(CHIP_SUSP), legal: await chipPressed(CHIP_LEGAL) };
  const C_both = await readCountStable();
  treeStep.chipsAnchor = chipsAnchor;
  treeStep.C_both = C_both;
  ck(
    'درخت: لنگر — هر دو چیپ روشن و عددِ تخته = N_both فاز ۱',
    chipsAnchor.susp === 'true' && chipsAnchor.legal === 'true' && C_both != null && C_both === N_both,
    { chipsAnchor, C_both, N_both },
  );

  // ۱) custom با دو چیپ → عددِ نوار باید اشتراکِ تخته باشد
  await gotoTreePage();
  const preSwing = await treePreset(TREE_SWING);
  const preCustom = await treePreset(TREE_CUSTOM);
  treeStep.presetSensor = { preSwing, preCustom };
  ck(
    'درخت: سنسورِ انتخاب دوحالته — پیش از کلیک swing روشن و سفارشی خاموش',
    preSwing.found && preSwing.selected && preCustom.found && !preCustom.selected,
    { preSwing, preCustom },
  );
  const customOk = await selectTreePreset(TREE_CUSTOM);
  const postSwing = await treePreset(TREE_SWING);
  const rBothWait = await waitTreeHeader('eq', C_both);
  await sleep(400);
  const rBoth = await readTreeStrip();
  treeStep.customBoth = { customOk, postSwing, rBothWait, rBoth };
  ck('درخت: «مسیر سفارشی» انتخاب شد و swing خاموش شد', customOk && !postSwing.selected, { customOk, postSwing });
  ck(
    'درخت: سرِ نوار و جعبهٔ Universe و ورودیِ گام ۱ با دو چیپ = اشتراکِ تخته',
    rBothWait && rBoth.headerNum === C_both && rBoth.universeBig === C_both && rBoth.tapeIn === C_both,
    { C_both, rBoth },
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_tree_custom_both.png` });

  // ۲) کنترل دوطرفه: swing باید عدد را عوض کند
  const swingOk = await selectTreePreset(TREE_SWING);
  const rSwingWait = await waitTreeHeader('ne', C_both);
  await sleep(400);
  const rSwing = await readTreeStrip();
  treeStep.swingControl = { swingOk, rSwingWait, rSwing };
  ck(
    'درخت: با swing عدد از C_both فاصله گرفت (کنترل دوطرفه)',
    swingOk && rSwingWait && rSwing.headerNum !== C_both,
    { C_both, rSwing },
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_tree_swing.png` });

  // ۳) بازگشت به custom → عدد برمی‌گردد
  const backCustomOk = await selectTreePreset(TREE_CUSTOM);
  const rBackWait = await waitTreeHeader('eq', C_both);
  await sleep(400);
  const rBack = await readTreeStrip();
  treeStep.backToCustom = { backCustomOk, rBackWait, rBack };
  ck(
    'درخت: بازگشت به سفارشی عدد را به C_both برمی‌گرداند',
    backCustomOk && rBackWait && rBack.headerNum === C_both,
    { C_both, rBack },
  );

  // ۴) یک‌چیپه: خاموش‌کردنِ «کد به کد» روی تخته، سپس همان عدد روی نوار
  await gotoMarketAnchor();
  await setChip(CHIP_LEGAL, false);
  const C_susp = await readCountStable();
  treeStep.C_susp = C_susp;
  ck('درخت: تخته — یک‌چیپه = N_susp فاز ۱ (تکرارپذیری)', C_susp != null && C_susp === N_susp, { C_susp, N_susp });

  await gotoTreePage();
  const custom2Ok = await selectTreePreset(TREE_CUSTOM);
  const rSuspWait = await waitTreeHeader('eq', C_susp);
  await sleep(400);
  const rSusp = await readTreeStrip();
  const suspChanged = C_susp != null && C_both != null && C_susp !== C_both;
  treeStep.customSusp = { custom2Ok, rSuspWait, rSusp, suspChanged };
  ck(
    'درخت: با یک چیپ عددِ نوار = عددِ تختهٔ یک‌چیپه',
    custom2Ok && rSuspWait && rSusp.headerNum === C_susp && rSusp.universeBig === C_susp,
    { C_susp, rSusp },
  );
  ck(
    'درخت: خاموش‌کردنِ «کد به کد» عدد را از C_both جدا کرد (یا تفکیک‌ناپذیر بود)',
    suspChanged ? rSusp.headerNum !== C_both : C_susp === C_both,
    { C_both, C_susp, rSusp, vacuousSusp: !suspChanged },
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_tree_custom_susp.png` });

  // ۵) بستنِ حلقه: روشن‌کردنِ دوباره → برگشتِ دوطرفه روی تخته و نوار
  await gotoMarketAnchor();
  await setChip(CHIP_LEGAL, true);
  const C_both2 = await readCountStable();
  treeStep.C_both2 = C_both2;
  ck('درخت: تخته — روشن‌کردنِ دوباره برگشت به C_both', C_both2 != null && C_both2 === C_both, { C_both, C_both2 });

  await gotoTreePage();
  const custom3Ok = await selectTreePreset(TREE_CUSTOM);
  const rBoth2Wait = await waitTreeHeader('eq', C_both2);
  await sleep(400);
  const rBoth2 = await readTreeStrip();
  treeStep.finalBoth = { custom3Ok, rBoth2Wait, rBoth2 };
  ck(
    'درخت: حلقه بسته شد — سفارشی با دو چیپ دوباره = C_both2',
    custom3Ok && rBoth2Wait && rBoth2.headerNum === C_both2 && rBoth2.universeBig === C_both2 && rBoth2.tapeIn === C_both2,
    { C_both2, rBoth2 },
  );
  await page.screenshot({ path: `${DIR}/funnel_chain_tree_final_both.png` });
} catch (e) {
  treeStep.crash = String(e);
  ck('درخت: فاز ۳ بدون خطای اجرایی تمام شد', false, String(e));
}

const failed = (report.checks as { name: string; ok: boolean }[]).filter((c) => !c.ok);
report.verdict = failed.length === 0 && (report.errors as string[]).length === 0 ? 'PASS' : 'FAIL';
report.failed = failed.map((f) => f.name);

writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(
  JSON.stringify(
    {
      verdict: report.verdict,
      failed: report.failed,
      errors: report.errors,
      http: report.http,
      board: report.steps.board,
      tree: report.steps.tree,
      checks: (report.checks as { name: string; ok: boolean }[]).map((c) => ({ name: c.name, ok: c.ok })),
    },
    null,
    2,
  ),
);
await browser.close();
