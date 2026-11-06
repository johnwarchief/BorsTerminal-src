// tools/funnel_browser_probe.mts — شاهدِ زندهٔ زنجیرِ قیف FTS در مرورگر: شمارش، هویتِ
// نمادها، و گذارِ حالت‌ها — نه فقط حضورِ DOM و نه فقط موفقیتِ کلیک (§۱۳ حکمِ مالک).
//
//  چه چیزی را زنده ثابت می‌کند (§۱۲ و §۱۳ حکمِ مالک — برابریِ قیف/درخت/استاد):
//   ۰) روندگیر روی استاد: درِ ورودی ↔ گره‌های زنجیر ↔ شمارشِ کارت‌ها یکی؛ تابلو و
//      تکنیکال یک مجموعه‌اند (تکنیکال دوباره روی universe نمی‌نشیند)؛ گره‌ها
//      نایکنواست؛ پوششِ تکنیکال حسابش می‌خواند (live=سنجیده، بودجه=سقف).
//   ۰ب) نوسانگیر روی استاد: همان چهار مسیر + پیش‌فرض‌های جزوه دست‌نخورده و بی‌چیپ.
//   ۱) برابریِ درخت↔استاد (نوسانگیر): نوارِ درخت و چهار کشوی کاندیدا با اسنپِ استاد
//      مو‌به‌مو می‌خوانند — همان مجموعه‌ها، همان شمار‌ها.
//   ۲) نردبانِ سفارشی روی درخت: r0 بی‌فیلتر → f_susp (A) → f_legal (B) → f_clock (C)
//      → AB → ABC؛ هر پله زیرمجموعهٔ پلهٔ قبل؛ A∩B از راهِ خاموش‌کردن دقیقاً همان AB
//      (AND نه OR — اجتماع به‌عنوانِ کنترلِ منفی)؛ بازگشتِ مو‌به‌مو به r0.
//   ۳) کشو‌های عمیقِ پلهٔ AB + درِ تکنیکالِ خاموش («رد بی‌حذف»).
//   ۴) پیچ‌های بنیادی: کف/انتظار/ریست — بازگشتِ دقیق (baseline از اسنپِ تازه).
//   ۵) نشت: swing/hourglass/trend چیپ‌های سفارشی را قرض نمی‌گیرند؛ بازگشتِ
//      روندگیر مو‌به‌مو P0؛ حالتِ مرور از اسکرینر شروع می‌شود و برمی‌گردد.
//
//  صداقتِ دامنه (چه چیزی درِ DOM نیست):
//   • ترتیبِ گره‌های چیپ فقط در کارتِ استاد دیده می‌شود؛ نوارِ درخت گره نمی‌آورد —
//     پس برابریِ نردبان مجموعه‌ویز است، نه زنجیر‌ویز.
//   • «چرا این نماد از درِ تابلو افتاد» per-symbol در DOMِ قیف نیست (ردیف‌های تابلو
//     why ندارند)؛ علیت از راهِ برابریِ شمار‌ها + بازگشتِ دقیق پسِ خاموش‌کردن ثابت
//     می‌شود، و فهرستِ خودِ ریخته‌شده‌ها ثبت می‌شود.
//   • «بیرونِ بودجهٔ TECH_QUERY_CAP» فقط شمارشی است، نه فهرستِ نمادی.
//   • ردیف‌های قبول‌شدهٔ بنیادی که درِ تحویل رد/بی‌داده‌اند در کارتِ تحویل per-row
//     نمی‌آیند؛ فقط در شمارشِ «رد/بی‌داده» دیده می‌شوند — این شکاف ثبت می‌شود.
//   • کشوی تابلو/تکنیکال همهٔ picked (با ردها) را نشان می‌دهد ولی کشوی بنیادی/تحویل
//     فقط قبول‌شده‌ها را؛ pending در کشو نیست — عدم‌تقارنِ ثبت‌شده.
//   • نوارِ درخت pending ندارد (کارت‌های استاد دارند) — تقارنِ اطلاعی ثبت می‌شود.
//
//   JEV_CHROME='<chrome.exe>' MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/funnel_browser_probe.mts \
//     --url http://127.0.0.1:8002/ --out _audit/funnel_browser_probe.json
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
const OUT = arg('out', '_audit/funnel_browser_probe.json');
const WAIT = Number(arg('wait', '45000'));
const DIR = OUT.split('/').slice(0, -1).join('/') || '.';
mkdirSync(DIR, { recursive: true });

// ارقامِ فارسی از نقطه‌کد ساخته می‌شوند تا ویرایشِ اسکریپتی رقم را ندزدد
const FA = Array.from({ length: 10 }, (_, d) => String.fromCharCode(0x6f0 + d)).join('');
const FAD = '[' + FA[0] + '-' + FA[9] + ']';
const FA_RE = new RegExp(FAD + '+');
const ZWNJ_RE = new RegExp(String.fromCharCode(0x200c), 'g');
const MINUS = String.fromCharCode(0x2212);
const DOT_SEP = String.fromCharCode(0xb7);
const norm = (s: string | null): string =>
  (s ?? '').replace(ZWNJ_RE, '').replace(/\u064a/g, '\u06cc').replace(/\s+/g, ' ').trim();
const faNum = (s: string | null): number | null => {
  const m = (s ?? '').match(FA_RE);
  if (!m) return null;
  return Number(m[0].split('').map((c) => String(c.charCodeAt(0) - 0x6f0)).join(''));
};
const faNums = (s: string | null): number[] => {
  const m = (s ?? '').match(new RegExp(FAD + '+', 'g'));
  return (m ?? []).map((x) => faNum(x)).filter((n): n is number => n != null);
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const report: Record<string, unknown> = { base: BASE, steps: {}, errors: [], http: [], checks: [], notes: [] };
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
    /* دروازهٔ محلی */
  }
});
const page = await context.newPage();
page.on('pageerror', (e: { message: string }) => (report.errors as string[]).push(`pageerror: ${e.message}`));
page.on('console', (m: { type: () => string; text: () => string; location: () => { url?: string } }) => {
  if (m.type() !== 'error') return;
  const url = m.location()?.url ?? '';
  if (url.endsWith('/favicon.ico')) return;
  (report.errors as string[]).push(`console: ${url} :: ${m.text().slice(0, 220)}`);
});
page.on('response', (r: { status: () => number; url: () => string }) => {
  if (r.status() >= 400) (report.http as string[]).push(`${r.status()} ${r.url()}`);
});

// ── خواندنِ یک اسنپ‌شاتِ کامل از قیف (زنجیر + در + شمارش‌ها + چهار کارت + تب‌ها) ──
const readState = () =>
  page.evaluate((minus) => {
    const txt = (el: Element | null | undefined) =>
      el ? (el.textContent ?? '').replace(/\s+/g, ' ').trim() : null;
    const nodes = Array.from(document.querySelectorAll('[data-testid^="funnel-chain-"]')).map((el) => ({
      key: (el.getAttribute('data-testid') ?? '').replace('funnel-chain-', ''),
      numText: el.querySelector('.num')?.textContent ?? null,
      title: el.getAttribute('title') ?? '',
    }));
    const doorEl = document.querySelector('[data-testid="funnel-door-label"]');
    const chainEl = document.querySelector('[data-testid="funnel-tape-chain"]');
    const covEls = Array.from(document.querySelectorAll('[data-testid="funnel-tech-coverage"]'));
    const countsRow = document.querySelector('[data-testid="funnel-counts"]');
    const universeSpan = countsRow
      ? Array.from(countsRow.querySelectorAll('span')).find((s) => (s.textContent ?? '').includes('universe'))
      : null;
    const t = (tid: string) => txt(document.querySelector(`[data-testid="${tid}"]`));

    const stages: Record<string, unknown> = {};
    for (const key of ['tape', 'technical', 'fundamental', 'handover']) {
      const stage = document.querySelector(`[data-testid="funnel-stage-${key}"]`);
      if (!stage) {
        stages[key] = null;
        continue;
      }
      const header = stage.querySelector('header');
      const nums = header ? Array.from(header.querySelectorAll('span.num')) : [];
      let countBadge: string | null = null;
      let dropped: string | null = null;
      let unmeasuredBadge: string | null = null;
      for (const s of nums) {
        const tx = (s.textContent ?? '').replace(/\s+/g, ' ').trim();
        if (countBadge == null && tx.includes('نماد') && !tx.startsWith(minus) && !tx.includes('رد') && !tx.includes('سنجیده')) {
          countBadge = tx;
        } else if (dropped == null && tx.startsWith(minus)) {
          dropped = tx;
        } else if (unmeasuredBadge == null && tx.includes('سنجیده')) {
          unmeasuredBadge = tx;
        }
      }
      const rejEl = stage.querySelector(`[data-testid="funnel-rejected-${key}"]`);
      const pendEl = stage.querySelector(`[data-testid="funnel-pending-${key}"]`);
      const emptyEl = stage.querySelector(`[data-testid="funnel-empty-${key}"]`);
      const pendingHeader = pendEl ? txt(pendEl.querySelector('p')) : null;
      const rows: Record<string, { mark: string | null; title: string; inPending: boolean }> = {};
      const main: string[] = [];
      const pendingRows: string[] = [];
      for (const tr of Array.from(stage.querySelectorAll('tr[data-fkey]'))) {
        const sym = tr.getAttribute('data-fkey') ?? '';
        if (!sym) continue;
        const inPending = pendEl ? pendEl.contains(tr) : false;
        const dot = tr.querySelector('button span.rounded-full');
        let mark: string | null = null;
        if (dot) {
          const cn = dot.className;
          mark = cn.includes('bg-accent-green')
            ? 'pass'
            : cn.includes('bg-accent-red')
              ? 'reject'
              : cn.includes('bg-accent-yellow')
                ? 'pending'
                : cn.includes('bg-border-c')
                  ? 'unavailable'
                  : null;
        }
        rows[sym] = { mark, title: tr.getAttribute('title') ?? '', inPending };
        (inPending ? pendingRows : main).push(sym);
      }
      const veto = Array.from(stage.querySelectorAll('[data-testid^="funnel-assembly-veto-"]')).map((el) =>
        (el.getAttribute('data-testid') ?? '').replace('funnel-assembly-veto-', ''),
      );
      stages[key] = {
        countBadge,
        dropped,
        rejectedBadge: txt(rejEl),
        unmeasuredBadge,
        pendingHeader,
        empty: txt(emptyEl),
        main,
        pendingRows,
        rows,
        veto,
      };
    }

    const chips: Record<string, string | null> = {};
    for (const f of ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal']) {
      const el = document.querySelector(`[data-testid="funnel-tape-chip-${f}"]`);
      chips[f] = el ? el.getAttribute('aria-pressed') : null;
    }
    const prefsEl = document.querySelector('[data-testid="funnel-tape-prefs"]');
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'))
      .filter((el) => (el.getAttribute('data-testid') ?? '').startsWith('funnel-step-'))
      .map((el) => ({
        key: (el.getAttribute('data-testid') ?? '').replace('funnel-step-', ''),
        selected: el.getAttribute('aria-selected') === 'true',
        text: (el.textContent ?? '').replace(/\s+/g, ' ').trim(),
      }));
    const cards = Array.from(document.querySelectorAll('[data-testid^="funnel-stage-"]')).map((el) => ({
      key: (el.getAttribute('data-testid') ?? '').replace('funnel-stage-', ''),
      active: /border-accent-blue\/70/.test(el.className),
    }));
    return {
      nodes,
      doorText: txt(doorEl),
      chainTitle: chainEl?.getAttribute('title') ?? '',
      coverage: covEls.map((el) => txt(el)),
      counts: {
        pass: t('funnel-count-pass'),
        pending: t('funnel-count-pending'),
        reject: t('funnel-count-reject'),
        unavailable: t('funnel-count-unavailable'),
        universeText: txt(universeSpan),
      },
      freshness: t('funnel-tape-freshness'),
      chips,
      chipPrefsText: txt(prefsEl),
      tabs,
      cards,
      stages,
    };
  }, MINUS);

type RawStage = {
  countBadge: string | null;
  dropped: string | null;
  rejectedBadge: string | null;
  unmeasuredBadge: string | null;
  pendingHeader: string | null;
  empty: string | null;
  main: string[];
  pendingRows: string[];
  rows: Record<string, { mark: string | null; title: string; inPending: boolean }>;
  veto: string[];
};
type RawState = {
  nodes: { key: string; numText: string | null; title: string }[];
  doorText: string | null;
  chainTitle: string;
  coverage: (string | null)[];
  counts: {
    pass: string | null;
    pending: string | null;
    reject: string | null;
    unavailable: string | null;
    universeText: string | null;
  };
  freshness: string | null;
  chips: Record<string, string | null>;
  chipPrefsText: string | null;
  tabs: { key: string; selected: boolean; text: string }[];
  cards: { key: string; active: boolean }[];
  stages: Record<string, RawStage | null>;
};

type StageSnap = {
  countBadge: number | null;
  dropped: number | null;
  rejectedBadge: number | null;
  unmeasuredBadge: number | null;
  pendingHeader: string | null;
  empty: string | null;
  main: string[];
  pendingRows: string[];
  rows: Record<string, { mark: string | null; title: string; inPending: boolean }>;
  veto: string[];
};
type Snap = {
  label: string;
  keys: string[];
  nums: (number | null)[];
  titles: string[];
  doorText: string | null;
  doorLabel: string;
  door: { boardScope: number | null; total: number | null; review: boolean };
  chainTitle: string;
  counts: {
    pass: number | null;
    pending: number | null;
    reject: number | null;
    unavailable: number | null;
    universe: number | null;
  };
  coverage1: { live: number | null; universe: number | null; beyond: number | null; raw: string | null };
  coverage2: { resolved: number | null; wanted: number | null; raw: string | null };
  freshness: string | null;
  chips: Record<string, boolean>;
  chipInput: number | null;
  tabs: { key: string; selected: boolean; text: string }[];
  activeTab: string | null;
  activeCard: string | null;
  cards: { key: string; active: boolean }[];
  stages: Record<string, StageSnap>;
};

const stageSnap = (s: RawStage): StageSnap => ({
  countBadge: faNum(s.countBadge),
  dropped: faNum(s.dropped),
  rejectedBadge: faNum(s.rejectedBadge),
  unmeasuredBadge: faNum(s.unmeasuredBadge),
  pendingHeader: s.pendingHeader,
  empty: s.empty,
  main: s.main,
  pendingRows: s.pendingRows,
  rows: s.rows,
  veto: s.veto,
});

const makeState = (label: string, raw: RawState): Snap => {
  const nodes = raw.nodes.map((n) => ({ key: n.key, num: faNum(n.numText), title: n.title }));
  const doorFull = norm(raw.doorText);
  const segs = doorFull.split(DOT_SEP);
  const doorSeg = segs.length > 1 ? segs[segs.length - 1] : doorFull;
  const labelSeg = segs.length > 1 ? segs.slice(0, -1).join(' ') : '';
  const ci = labelSeg.indexOf(':');
  const doorLabel = (ci >= 0 ? labelSeg.slice(ci + 1) : labelSeg).trim();
  const doorNums = faNums(doorSeg);
  const review = doorSeg.includes('اسکرینر');
  const c1 = faNums(raw.coverage[0] ?? null);
  const c2 = faNums(raw.coverage[1] ?? null);
  const chipInputM = norm(raw.chipPrefsText).match(new RegExp('ورودی:\\s*(' + FAD + '+)'));
  const chips: Record<string, boolean> = {};
  for (const [k, v] of Object.entries(raw.chips)) chips[k] = v === 'true';
  const stages: Record<string, StageSnap> = {};
  for (const key of ['tape', 'technical', 'fundamental', 'handover']) {
    const s = raw.stages[key];
    if (s) stages[key] = stageSnap(s);
  }
  return {
    label,
    keys: nodes.map((n) => n.key),
    nums: nodes.map((n) => n.num),
    titles: nodes.map((n) => n.title),
    doorText: raw.doorText,
    doorLabel,
    door: review
      ? { boardScope: null, total: doorNums[0] ?? null, review: true }
      : { boardScope: doorNums[0] ?? null, total: doorNums[1] ?? null, review: false },
    chainTitle: raw.chainTitle,
    counts: {
      pass: faNum(raw.counts.pass),
      pending: faNum(raw.counts.pending),
      reject: faNum(raw.counts.reject),
      unavailable: faNum(raw.counts.unavailable),
      universe: faNum(raw.counts.universeText),
    },
    coverage1: { live: c1[0] ?? null, universe: c1[1] ?? null, beyond: c1.length > 2 ? c1[2] : 0, raw: raw.coverage[0] ?? null },
    coverage2: raw.coverage[1] ? { resolved: c2[0] ?? null, wanted: c2[1] ?? null, raw: raw.coverage[1] } : { resolved: null, wanted: null, raw: null },
    freshness: raw.freshness,
    chips,
    chipInput: chipInputM ? faNum(chipInputM[1]) : null,
    tabs: raw.tabs,
    activeTab: raw.tabs.find((t) => t.selected)?.key ?? null,
    activeCard: raw.cards.find((c) => c.active)?.key ?? null,
    cards: raw.cards,
    stages,
  };
};

const snap = async (label: string): Promise<Snap> => {
  const raw = (await readState()) as RawState;
  if (!raw.stages.tape || !raw.stages.technical || !raw.stages.fundamental || !raw.stages.handover) {
    throw new Error(`stage cards not rendered at ${label}`);
  }
  const s = makeState(label, raw);
  (report.steps as Record<string, unknown>)[label] = s;
  return s;
};

// ── عملیاتِ مجموعه‌ای — هویتِ نماد، نه فقط شمار ──────────────────────────────
const asSet = (a: string[]): Set<string> => new Set(a);
const setEq = (a: Set<string>, b: Set<string>): boolean => a.size === b.size && [...a].every((x) => b.has(x));
const isSubset = (a: Set<string>, b: Set<string>): boolean => [...a].every((x) => b.has(x));
const inter = (a: Set<string>, b: Set<string>): Set<string> => new Set([...a].filter((x) => b.has(x)));
const diff = (a: Set<string>, b: Set<string>): string[] => [...a].filter((x) => !b.has(x)).sort();
const uni = (a: Set<string>, b: Set<string>): Set<string> => new Set([...a, ...b]);
const size = (a: Set<string>): number => a.size;

const monotone = (nums: (number | null)[]): boolean => {
  if (nums.length === 0 || nums.some((n) => n == null)) return false;
  for (let i = 1; i < nums.length; i++) {
    if ((nums[i] as number) > (nums[i - 1] as number)) return false;
  }
  return true;
};
const keysEqual = (keys: string[], expected: readonly string[]): boolean =>
  keys.length === expected.length && keys.every((k, i) => k === expected[i]);
const doorHas = (s: Snap, needle: string): boolean => norm(s.doorText).includes(norm(needle));
const universeNode = (s: Snap): number | null => (s.keys[0] === 'universe' || s.keys[0] === 'screen' ? (s.nums[0] ?? null) : null);
const lastTapeNode = (s: Snap): number | null => {
  const i = s.keys.findIndex((k) => k === 'technical');
  if (i <= 0) return null;
  return s.nums[i - 1] ?? null;
};
const crossOk = (s: Snap): boolean => {
  const lt = lastTapeNode(s);
  const un = universeNode(s);
  return (
    s.door.boardScope === un && s.door.total === lt && lt != null && un != null && !s.door.review
  );
};

// ── تعامل: دکمه‌ها با testid، انتظار تا حالتِ واقعی ──────────────────────────
const pressOf = (testid: string): Promise<string | null> =>
  page.evaluate((tid) => document.querySelector(`[data-testid="${tid}"]`)?.getAttribute('aria-pressed') ?? null, testid);

const clickT = async (testid: string): Promise<void> => {
  const hit = await page.evaluate((tid) => {
    const el = document.querySelector(`[data-testid="${tid}"]`) as HTMLElement | null;
    if (!el) return false;
    el.click();
    return true;
  }, testid);
  if (!hit) throw new Error(`not found: ${testid}`);
};

const ensurePressed = async (testid: string, on: boolean, tries = 5): Promise<boolean> => {
  for (let t = 0; t < tries; t++) {
    if (((await pressOf(testid)) === 'true') === on) return true;
    await clickT(testid);
    for (let i = 0; i < 8; i++) {
      await sleep(150);
      if (((await pressOf(testid)) === 'true') === on) return true;
    }
  }
  return false;
};

const waitChainKeys = async (keys: readonly string[]): Promise<boolean> => {
  try {
    await page.waitForFunction(
      (expected: string[]) => {
        const got = Array.from(document.querySelectorAll('[data-testid^="funnel-chain-"]')).map((el) =>
          (el.getAttribute('data-testid') ?? '').replace('funnel-chain-', ''),
        );
        return got.length === expected.length && got.every((k, i) => k === expected[i]);
      },
      [...keys],
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

const waitGone = async (sel: string): Promise<boolean> => {
  try {
    await page.waitForFunction((s) => !document.querySelector(s), sel, { timeout: WAIT });
    return true;
  } catch {
    return false;
  }
};

const K = {
  trend: ['universe', 'f_roobi', 'f_noqteh', 'technical', 'fundamental', 'handover'],
  swing: ['universe', 'f_clock', 'f_jet', 'f_susp', 'technical', 'fundamental', 'handover'],
  hourglass: ['universe', 'f_roobi', 'f_clock', 'technical', 'fundamental', 'handover'],
  custom0: ['universe', 'technical', 'fundamental', 'handover'],
  customAB: ['universe', 'f_susp', 'f_legal', 'technical', 'fundamental', 'handover'],
  customBA: ['universe', 'f_legal', 'f_susp', 'technical', 'fundamental', 'handover'],
  customB: ['universe', 'f_legal', 'technical', 'fundamental', 'handover'],
  customA: ['universe', 'f_susp', 'technical', 'fundamental', 'handover'],
  review: ['screen', 'technical', 'fundamental', 'handover'],
} as const;

const gotoMaster = async (): Promise<void> => {
  await page.evaluate(() => {
    location.hash = '#/master';
  });
  await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: WAIT });
  await page.waitForSelector('[data-testid="funnel-door-label"]', { timeout: WAIT });
};

// ── انتخابِ preset از صفحهٔ درخت (مسیرِ «مسیر سفارشی (انتخاب دستی)») ──────────
const TREE_CUSTOM = 'مسیر سفارشی';

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

const treePreset = (needle: string): Promise<{ found: boolean; selected: boolean }> =>
  page.evaluate((raw) => {
    const z = new RegExp(String.fromCharCode(0x200c), 'g');
    const nz = (s: string) => (s ?? '').replace(z, '').replace(/\s+/g, '');
    const scope = document.querySelector('[data-testid="tree-preset-label"]')?.parentElement ?? document.body;
    const btn = Array.from(scope.querySelectorAll('button')).find((b) => nz(b.textContent ?? '').includes(nz(raw)));
    if (!btn) return { found: false, selected: false };
    return { found: true, selected: /font-black/.test(btn.className) };
  }, needle);

const selectTreePreset = async (needle: string): Promise<boolean> => {
  await clickTreePreset(needle);
  for (let i = 0; i < 25; i++) {
    const st = await treePreset(needle);
    if (st.found && st.selected) return true;
    await sleep(120);
  }
  return false;
};

const gotoTreePage = async (): Promise<void> => {
  await page.evaluate(() => {
    location.hash = '#/strategy-tree';
  });
  await page.waitForSelector('[data-testid="tree-preset-label"]', { timeout: WAIT });
};

const censusOf = (s: StageSnap): Record<string, number> => {
  const m: Record<string, number> = { pass: 0, reject: 0, pending: 0, unavailable: 0, none: 0 };
  for (const r of Object.values(s.rows)) m[r.mark ?? 'none'] += 1;
  return m;
};

const whyMissing = (s: StageSnap): string[] =>
  Object.entries(s.rows)
    .filter(([, r]) => r.mark != null && r.mark !== 'pass' && !r.title)
    .map(([sym]) => sym)
    .sort();

// ── فازها ────────────────────────────────────────────────────────────────────
try {
  // فاز ۰ — روندگیرِ تازه: بستنِ قراردادِ خوانش روی هر چهار مسیر
  await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: WAIT });
  await page.waitForSelector('[data-testid="funnel-door-label"]', { timeout: WAIT });
  const modeRevOk = await ensurePressed('funnel-mode-reverse', true);
  const presetTrendOk = await ensurePressed('funnel-preset-trend', true);
  const settle0Timeout = await settleTech();
  const keys0Ok = await waitChainKeys(K.trend);
  await sleep(500);
  const p0 = await snap('p0_trend');
  const P0 = asSet(p0.stages.tape.main);
  await page.screenshot({ path: `${DIR}/funnel_browser_p0_trend.png` });

  ck('p0: حالتِ معکوس و دربِ روندگیر فعال شدند', modeRevOk && presetTrendOk, { modeRevOk, presetTrendOk });
  ck('p0: زنجیر تازه و بی‌انتظارِ تکنیکال خوانده شد', !settle0Timeout && keys0Ok, { settle0Timeout, keys0Ok });
  ck('p0: کلیدهای زنجیر مو‌به‌مو روندگیر', keysEqual(p0.keys, K.trend), { expected: K.trend, got: p0.keys });
  ck('p0: بازماندگانِ گره‌ها نایکنواست', monotone(p0.nums), p0.nums);
  ck(
    'p0: در و زنجیر می‌خوانند (universe=boardScope، نشانه=آخرین گرهٔ فیلتر)',
    crossOk(p0) && doorHas(p0, 'شخص روندگیر'),
    { door: p0.door, universe: universeNode(p0), lastTape: lastTapeNode(p0), doorText: p0.doorText },
  );
  ck(
    'p0: ‖P‖ از پنج مسیرِ مستقل یکی است (کارت، زنجیر، در، universe، «ورودی» چیپ‌ها)',
    p0.stages.tape.countBadge != null &&
      p0.stages.tape.countBadge === lastTapeNode(p0) &&
      p0.stages.tape.countBadge === p0.door.total &&
      p0.stages.tape.countBadge === p0.counts.universe &&
      p0.stages.tape.countBadge === p0.chipInput,
    {
      card: p0.stages.tape.countBadge,
      chain: lastTapeNode(p0),
      door: p0.door.total,
      universe: p0.counts.universe,
      chipInput: p0.chipInput,
    },
  );
  ck(
    'p0: کارتِ تابلو و کارتِ تکنیکال یک مجموعه‌اند (تکنیکال روی universe دوباره نمی‌نشیند)',
    setEq(asSet(p0.stages.tape.main), asSet(p0.stages.technical.main)) && P0.size > 0,
    { tape: [...P0].length, technical: p0.stages.technical.main.length },
  );
  ck(
    'p0: گرهٔ تکنیکال = ‖P‖ منهای حذفِ تکنیکال',
    lastTapeNode(p0) != null && p0.nums[p0.keys.indexOf('technical')] === P0.size - (p0.stages.technical.dropped ?? 0),
    { chainTech: p0.nums[p0.keys.indexOf('technical')], P: P0.size, dropped: p0.stages.technical.dropped },
  );
  ck(
    'p0: گرهٔ بنیادی و تحویل روی کارت‌های خودشان می‌خوانند',
    p0.nums[p0.keys.indexOf('fundamental')] === p0.stages.fundamental.main.length &&
      p0.nums[p0.keys.indexOf('handover')] === p0.stages.handover.main.length,
    {
      chainFund: p0.nums[p0.keys.indexOf('fundamental')],
      cardFund: p0.stages.fundamental.main.length,
      chainHand: p0.nums[p0.keys.indexOf('handover')],
      cardHand: p0.stages.handover.main.length,
    },
  );
  ck(
    'p0: شمارشِ تحویل = ردیف‌های کارتِ تحویل (pass و pending)',
    p0.counts.pass === p0.stages.handover.main.length && p0.counts.pending === p0.stages.handover.pendingRows.length,
    { pass: p0.counts.pass, main: p0.stages.handover.main.length, pending: p0.counts.pending, pendingRows: p0.stages.handover.pendingRows.length },
  );
  ck(
    'p0: کارتِ بنیادی زیرمجموعهٔ کارتِ تابلو و کارتِ تحویل زیرمجموعهٔ بنیادی',
    isSubset(asSet(p0.stages.fundamental.main), P0) && isSubset(asSet(p0.stages.handover.main), asSet(p0.stages.fundamental.main)),
    {
      fund: p0.stages.fundamental.main.length,
      hand: p0.stages.handover.main.length,
      P: P0.size,
      fundOutside: diff(asSet(p0.stages.fundamental.main), P0),
      handOutside: diff(asSet(p0.stages.handover.main), asSet(p0.stages.fundamental.main)),
    },
  );
  ck(
    'p0: پوششِ تکنیکال حسابش می‌خواند (live=سنجیده، بودجه=سقف، مازاد=max(۰، P−سقف))',
    p0.counts.universe != null &&
      p0.coverage1.live === p0.coverage2.resolved &&
      p0.coverage1.universe === p0.counts.universe &&
      p0.coverage2.wanted === Math.min(p0.counts.universe, 60) &&
      p0.coverage1.beyond === Math.max(0, p0.counts.universe - 60),
    { c1: p0.coverage1, c2: p0.coverage2, universe: p0.counts.universe },
  );
  ck('p0: برچسبِ تازگیِ خوراکِ تابلو روی نوار هست', (p0.freshness ?? '').length > 0, p0.freshness);
  ck(
    'p0: چهار تبِ مرحله به ترتیب، با شمارِ همان کارت، و یکی انتخاب',
    keysEqual(p0.tabs.map((t) => t.key), ['tape', 'technical', 'fundamental', 'handover']) &&
      p0.tabs.every((t) => {
        const nums = faNums(t.text);
        const stage = p0.stages[t.key];
        return nums.length > 0 && stage.countBadge != null && nums[nums.length - 1] === stage.countBadge;
      }) &&
      p0.tabs.filter((t) => t.selected).length === 1 &&
      p0.activeCard === p0.activeTab,
    { tabs: p0.tabs, activeTab: p0.activeTab, activeCard: p0.activeCard },
  );

  // فاز ۱ — سفارشیِ تازه از درخت: بی‌فیلتر، کلِ تابلو
  await gotoTreePage();
  const customSelOk = await selectTreePreset(TREE_CUSTOM);
  await gotoMaster();
  const settle1Timeout = await settleTech();
  const keys1Ok = await waitChainKeys(K.custom0);
  await sleep(500);
  const p1 = await snap('p1_custom_clean');
  const S0 = asSet(p1.stages.tape.main);
  await page.screenshot({ path: `${DIR}/funnel_browser_p1_custom_clean.png` });

  ck('p1: «مسیر سفارشی» از درخت انتخاب شد', customSelOk, { customSelOk });
  ck('p1: زنجیرِ سفارشیِ بی‌فیلتر (بی‌انتظارِ تکنیکال)', !settle1Timeout && keys1Ok, { settle1Timeout, keys1Ok });
  ck('p1: کلیدهای زنجیر = بی‌گرهٔ سفارشی', keysEqual(p1.keys, K.custom0), { expected: K.custom0, got: p1.keys });
  ck(
    'p1: در می‌گوید بی‌فیلتری و همهٔ شمارها یکی‌اند (در/boardScope/universe/کارت/«ورودی»)',
    doorHas(p1, 'بی‌فیلتر') &&
      p1.door.boardScope === p1.door.total &&
      p1.door.boardScope === S0.size &&
      p1.counts.universe === S0.size &&
      p1.chipInput === S0.size &&
      universeNode(p1) === S0.size,
    { door: p1.door, S0: S0.size, universe: p1.counts.universe, chipInput: p1.chipInput, universeNode: universeNode(p1) },
  );
  ck(
    'p1: چیپ‌های ورودی خاموش‌اند (حالتِ تازه)',
    Object.values(p1.chips).every((v) => v === false),
    p1.chips,
  );
  ck(
    'p1: پیش‌فرض‌های جزوه دست‌نخورده (کف، انتظار، درِ تکنیکال) و دکمهٔ بازگشت پنهان',
    (await pressOf('funnel-floor-3')) === 'true' &&
      (await pressOf('funnel-unmeasured-hold')) === 'true' &&
      (await pressOf('funnel-tech-screens')) === 'true' &&
      (await pressOf('funnel-prefs-reset')) == null,
    {
      floor3: await pressOf('funnel-floor-3'),
      hold: await pressOf('funnel-unmeasured-hold'),
      screens: await pressOf('funnel-tech-screens'),
      reset: await pressOf('funnel-prefs-reset'),
    },
  );

  // فاز ۲ — چیپ ۱: حجم مشکوک
  const suspOnOk = await ensurePressed('funnel-tape-chip-f_susp', true);
  const keys2Ok = await waitChainKeys(K.customA);
  const settle2Timeout = await settleTech();
  await sleep(500);
  const p2 = await snap('p2_susp');
  const SA = asSet(p2.stages.tape.main);
  const removed0 = diff(S0, SA);
  (report.steps as Record<string, unknown>).p2_removed = removed0;
  await page.screenshot({ path: `${DIR}/funnel_browser_p2_susp.png` });

  ck('p2: چیپِ «حجم مشکوک» روشن شد و گرهٔ f_susp به زنجیر آمد', suspOnOk && keys2Ok, { suspOnOk, keys2Ok });
  ck('p2: گرهٔ f_susp = بازماندگانِ کارت و درِ ورودی', p2.nums[1] === SA.size && p2.door.total === SA.size, { node: p2.nums[1], SA: SA.size, door: p2.door.total });
  ck(
    'p2: بازماندگان فقط از S0 کم شدند — نه اضافه (زیرمجموعهٔ واقعی)',
    SA.size <= S0.size && isSubset(SA, S0),
    { S0: S0.size, SA: SA.size, removed: removed0.length, outside: diff(SA, S0) },
  );
  ck(
    'p2: universe و boardScope دست‌نخورده‌اند — فیلتر فقط ردیف می‌ریزد',
    universeNode(p2) === S0.size && p2.door.boardScope === S0.size,
    { universeNode: universeNode(p2), boardScope: p2.door.boardScope, S0: S0.size },
  );

  // فاز ۳ — چیپ ۲: کد به کد — اشتراکِ دو فیلتر
  const legalOnOk = await ensurePressed('funnel-tape-chip-f_legal', true);
  const keys3Ok = await waitChainKeys(K.customAB);
  const settle3Timeout = await settleTech();
  await sleep(500);
  const p3 = await snap('p3_both');
  const SAB = asSet(p3.stages.tape.main);
  const removed1 = diff(SA, SAB);
  (report.steps as Record<string, unknown>).p3_removed = removed1;
  await page.screenshot({ path: `${DIR}/funnel_browser_p3_both.png` });

  ck(
    'p3: چیپ دوم روشن شد و هر دو گره به ترتیبِ روشن‌شدن در زنجیرند',
    legalOnOk && keys3Ok && keysEqual(p3.keys, K.customAB),
    { legalOnOk, keys3Ok, expected: K.customAB, got: p3.keys },
  );
  ck('p3: گرهٔ f_legal = بازماندگانِ نهایی و در همان را می‌گوید', p3.nums[2] === SAB.size && p3.door.total === SAB.size, { node: p3.nums[2], SAB: SAB.size, door: p3.door.total });
  ck(
    'p3: کاهشِ اشتراک — S_AB زیرمجموعهٔ S_A است و از آن بزرگ‌تر نیست',
    SAB.size <= SA.size && isSubset(SAB, SA),
    { SA: SA.size, SAB: SAB.size, removedByLegal: removed1.length, outside: diff(SAB, SA) },
  );

  // فاز ۴ — خاموش‌کردنِ چیپ ۱: برابریِ اشتراک (AND نه OR) + کنترلِ منفی
  const suspOffOk = await ensurePressed('funnel-tape-chip-f_susp', false);
  const keys4Ok = await waitChainKeys(K.customB);
  const settle4Timeout = await settleTech();
  await sleep(500);
  const p4 = await snap('p4_legal_only');
  const SB = asSet(p4.stages.tape.main);

  ck('p4: با یک چیپ، زنجیر همان یک گرهٔ f_legal را دارد', suspOffOk && keys4Ok && p4.nums[1] === SB.size, { suspOffOk, keys4Ok, node: p4.nums[1], SB: SB.size });
  ck(
    'p4: برابریِ اشتراک — A∩B از راهِ خاموش‌کردن دقیقاً همان دوچیپه است (نه اجتماع، نه اجرای مستقل)',
    setEq(inter(SA, SB), SAB),
    { SAB: SAB.size, inter: size(inter(SA, SB)), onlyInAB: diff(SAB, inter(SA, SB)), onlyInInter: diff(inter(SA, SB), SAB) },
  );
  const vacuousUnion = setEq(SA, SB);
  ck(
    'p4: کنترلِ منفی — اجتماع بزرگ‌تر از اشتراک است (یا دو مجموعه یکی‌اند و تفکیک‌ناپذیر)',
    size(uni(SA, SB)) > SAB.size || vacuousUnion,
    { union: size(uni(SA, SB)), inter: SAB.size, SA: SA.size, SB: SB.size, vacuousUnion },
  );
  ck(
    'p4: تکیِ B خودش زیرمجموعهٔ مرحلهٔ بی‌فیلتر است',
    isSubset(SB, S0) && SB.size <= S0.size,
    { SB: SB.size, S0: S0.size, outside: diff(SB, S0) },
  );

  // فاز ۵ — روشن‌کردنِ دوباره: ترتیبِ گره‌ها عوض می‌شود، مجموعه نه
  const suspOn2Ok = await ensurePressed('funnel-tape-chip-f_susp', true);
  const keys5Ok = await waitChainKeys(K.customBA);
  const settle5Timeout = await settleTech();
  await sleep(500);
  const p5 = await snap('p5_both_reordered');
  const SAB2 = asSet(p5.stages.tape.main);

  ck(
    'p5: ترتیبِ گره‌ها از ترتیبِ روشن‌شدن می‌آید (f_legal قبل از f_susp)',
    suspOn2Ok && keys5Ok && keysEqual(p5.keys, K.customBA),
    { keys5Ok, expected: K.customBA, got: p5.keys },
  );
  ck(
    'p5: جابه‌جایی‌پذیریِ AND — همان مجموعهٔ دوچیپه با ترتیبِ دیگرِ گره‌ها',
    setEq(SAB2, SAB),
    { reordered: SAB2.size, original: SAB.size, onlyInNew: diff(SAB2, SAB), onlyInOld: diff(SAB, SAB2) },
  );

  // فاز ۶ — خاموش‌کردنِ همه: بازگشتِ مو‌به‌مو به S0
  const legalOffOk = await ensurePressed('funnel-tape-chip-f_legal', false);
  const suspOff2Ok = await ensurePressed('funnel-tape-chip-f_susp', false);
  const keys6Ok = await waitChainKeys(K.custom0);
  const settle6Timeout = await settleTech();
  await sleep(500);
  const p6 = await snap('p6_reset');
  const S0back = asSet(p6.stages.tape.main);

  ck('p6: خاموش‌کردنِ هر دو، زنجیرِ بی‌گره را برگرداند', legalOffOk && suspOff2Ok && keys6Ok, { legalOffOk, suspOff2Ok, keys6Ok });
  ck(
    'p6: بازگشتِ دقیق — مجموعه مو‌به‌مو همان S0 است (بی‌نشتِ حالتِ کهنه)',
    setEq(S0back, S0),
    { S0: S0.size, back: S0back.size, missing: diff(S0, S0back), extra: diff(S0back, S0) },
  );
  ck(
    'p6: در و شمارها به بی‌فیلتر برگشتند',
    doorHas(p6, 'بی‌فیلتر') && p6.door.boardScope === p6.door.total && p6.door.total === S0.size && p6.chipInput === S0.size,
    { door: p6.door, S0: S0.size, chipInput: p6.chipInput },
  );

  // فاز ۷ — دوچیپهٔ پایانی: جدولِ per-candidate و ردِ نامرئی
  const suspOn3Ok = await ensurePressed('funnel-tape-chip-f_susp', true);
  const legalOn2Ok = await ensurePressed('funnel-tape-chip-f_legal', true);
  const keys7Ok = await waitChainKeys(K.customAB);
  const settle7Timeout = await settleTech();
  await sleep(600);
  const p7 = await snap('p7_status');
  const T7 = p7.stages.technical;
  const F7 = p7.stages.fundamental;
  const H7 = p7.stages.handover;
  const handSet7 = asSet(H7.main);
  const handPendSet7 = asSet(H7.pendingRows);
  const invisible = [...asSet(F7.main)].filter((s) => !handSet7.has(s) && !handPendSet7.has(s)).sort();
  (report.steps as Record<string, unknown>).p7_invisible = invisible;
  (report.steps as Record<string, unknown>).p7_marks = {
    tape: censusOf(p7.stages.tape),
    technical: censusOf(T7),
    fundamental: censusOf(F7),
    handover: censusOf(H7),
  };
  (report.steps as Record<string, unknown>).p7_veto = { fundamental: F7.veto, handover: H7.veto };
  (report.steps as Record<string, unknown>).p7_table = T7.main.map((s) => ({
    s,
    tech: T7.rows[s]?.mark ?? null,
    fund: F7.rows[s]?.mark ?? null,
    hand: H7.rows[s]?.mark ?? null,
    handIn: handSet7.has(s) ? 'main' : handPendSet7.has(s) ? 'pending' : null,
    whyFund: F7.rows[s]?.title || null,
    whyHand: H7.rows[s]?.title || null,
  }));
  await page.screenshot({ path: `${DIR}/funnel_browser_p7_status.png` });

  ck('p7: دوچیپه دوباره زنجیر شد و همان S_AB برگشت', suspOn3Ok && legalOn2Ok && keys7Ok && setEq(asSet(p7.stages.tape.main), SAB), {
    suspOn3Ok,
    legalOn2Ok,
    keys7Ok,
    tape: p7.stages.tape.main.length,
    SAB: SAB.size,
    onlyIn: diff(asSet(p7.stages.tape.main), SAB),
  });
  ck(
    'p7: تابلو و تکنیکال یک مجموعه‌اند (هر بازمانده یک رأیِ تکنیکال به خودش دارد)',
    setEq(asSet(p7.stages.tape.main), asSet(T7.main)),
    { tape: p7.stages.tape.main.length, technical: T7.main.length },
  );
  ck(
    'p7: بنیادی فقط روی بازماندگانِ تکنیکال (و انتظارها هم از همان‌جا)',
    isSubset(asSet(F7.main), asSet(T7.main)) && isSubset(asSet(F7.pendingRows), asSet(T7.main)),
    {
      fundOutside: diff(asSet(F7.main), asSet(T7.main)),
      pendingOutside: diff(asSet(F7.pendingRows), asSet(T7.main)),
    },
  );
  ck(
    'p7: تحویل فقط روی قبول‌شدگانِ بنیادی (و توقف‌ها هم از همان‌جا)',
    isSubset(handSet7, asSet(F7.main)) && isSubset(handPendSet7, asSet(F7.main)),
    { handOutside: diff(handSet7, asSet(F7.main)), pendOutside: diff(handPendSet7, asSet(F7.main)) },
  );
  ck(
    'p7: شمارشِ تحویل بازهم = ردیف‌های کارت (pass و pending)',
    p7.counts.pass === H7.main.length && p7.counts.pending === H7.pendingRows.length,
    { pass: p7.counts.pass, main: H7.main.length, pending: p7.counts.pending, pendingRows: H7.pendingRows.length },
  );
  const wm = [...whyMissing(T7), ...whyMissing(F7), ...whyMissing(H7)];
  ck('p7: هر ردیفِ نمایانِ رد/انتظار/بی‌داده دلیلش را روی خودِ ردیف دارد', wm.length === 0, { whyMissing: wm });
  ck(
    'p7: ردهای نامرئیِ تحویل با شمارشِ «رد+بی‌داده» یکی‌اند (سنجهٔ شکاف)',
    invisible.length === (p7.counts.reject ?? -1) + (p7.counts.unavailable ?? -1),
    { invisible: invisible.length, reject: p7.counts.reject, unavailable: p7.counts.unavailable, symbols: invisible },
  );
  ck(
    'p7: ردیف‌های تحویل markشان pass است (نه فقط برچسبِ متن)',
    H7.main.every((s) => H7.rows[s]?.mark === 'pass') && H7.pendingRows.every((s) => H7.rows[s]?.mark === 'pending'),
    {
      badMain: H7.main.filter((s) => H7.rows[s]?.mark !== 'pass'),
      badPending: H7.pendingRows.filter((s) => H7.rows[s]?.mark !== 'pending'),
    },
  );

  // فاز ۸ — تب‌های مرحله: aria-selected ⇄ کارتِ فعال
  await clickT('funnel-step-fundamental');
  await page.waitForSelector('[data-testid="funnel-step-fundamental"][aria-selected="true"]', { timeout: WAIT });
  await sleep(250);
  const rawF = (await readState()) as RawState;
  const midF = makeState('tmp_fund', rawF);
  await clickT('funnel-step-handover');
  await page.waitForSelector('[data-testid="funnel-step-handover"][aria-selected="true"]', { timeout: WAIT });
  await sleep(250);
  const p8 = await snap('p8_tabs');

  ck('p8: تبِ بنیادی → انتخاب و کارتِ همان مرحله فعال', midF.activeTab === 'fundamental' && midF.activeCard === 'fundamental', { activeTab: midF.activeTab, activeCard: midF.activeCard });
  ck('p8: تبِ تحویل → انتخاب و کارتِ همان مرحله فعال', p8.activeTab === 'handover' && p8.activeCard === 'handover', { activeTab: p8.activeTab, activeCard: p8.activeCard });
  ck('p8: همیشه فقط یک تب و یک کارت فعال', p8.tabs.filter((t) => t.selected).length === 1 && p8.cards.filter((c) => c.active).length === 1, { tabs: p8.tabs, cards: p8.cards });

  // فاز ۹ — پیچ‌های بنیادی: کف ۵ + drop، سپس بازگشتِ جزوه
  const floor5Ok = await ensurePressed('funnel-floor-5', true);
  const dropOk = await ensurePressed('funnel-unmeasured-drop', true);
  const resetShown = await page
    .waitForSelector('[data-testid="funnel-prefs-reset"]', { timeout: WAIT })
    .then(() => true)
    .catch(() => false);
  await sleep(500);
  const p9b = await snap('p9_floor5_drop');
  await page.screenshot({ path: `${DIR}/funnel_browser_p9_floor5_drop.png` });

  ck('p9: کفِ سقف و drop روشن شدند و دکمهٔ بازگشت پیدا شد', floor5Ok && dropOk && resetShown, { floor5Ok, dropOk, resetShown });
  const pendingBefore = p7.stages.fundamental.pendingRows.length;
  ck(
    'p9: با drop گروهِ انتظارِ بنیادی خالی شد (یا از اول خالی بود — خلأ ثبت می‌شود)',
    p9b.stages.fundamental.pendingRows.length === 0,
    { before: pendingBefore, after: p9b.stages.fundamental.pendingRows.length, vacuous: pendingBefore === 0 },
  );
  ck(
    'p9: با کفِ سقف، بازماندگانِ بنیادی فقط کم شدند (زیرمجموعهٔ کفِ پیش‌فرض)',
    isSubset(asSet(p9b.stages.fundamental.main), asSet(p7.stages.fundamental.main)) &&
      p9b.stages.fundamental.main.length <= p7.stages.fundamental.main.length,
    {
      before: p7.stages.fundamental.main.length,
      after: p9b.stages.fundamental.main.length,
      outside: diff(asSet(p9b.stages.fundamental.main), asSet(p7.stages.fundamental.main)),
      vacuous: p9b.stages.fundamental.main.length === p7.stages.fundamental.main.length,
    },
  );
  ck(
    'p9: شمارشِ تحویل بازهم = کارتِ تحویل در حالتِ پیچ‌های تازه',
    p9b.counts.pass === p9b.stages.handover.main.length && p9b.counts.pending === p9b.stages.handover.pendingRows.length,
    { pass: p9b.counts.pass, main: p9b.stages.handover.main.length, pending: p9b.counts.pending, pendingRows: p9b.stages.handover.pendingRows.length },
  );

  await clickT('funnel-prefs-reset');
  const resetGone = await waitGone('[data-testid="funnel-prefs-reset"]');
  await sleep(500);
  const p9c = await snap('p9_reset_prefs');
  await page.screenshot({ path: `${DIR}/funnel_browser_p9_reset.png` });

  ck(
    'p9: بازگشت به جزوه — پیش‌فرض‌ها برگشتند و دکمهٔ بازگشت رفت',
    resetGone &&
      (await pressOf('funnel-floor-3')) === 'true' &&
      (await pressOf('funnel-unmeasured-hold')) === 'true' &&
      (await pressOf('funnel-tech-screens')) === 'true',
    {
      resetGone,
      floor3: await pressOf('funnel-floor-3'),
      hold: await pressOf('funnel-unmeasured-hold'),
      screens: await pressOf('funnel-tech-screens'),
    },
  );
  ck(
    'p9: بازگشتِ دقیق — مجموعهٔ بنیادی مو‌به‌مو همان پیش از پیچ‌ها',
    setEq(asSet(p9c.stages.fundamental.main), asSet(p7.stages.fundamental.main)),
    {
      before: p7.stages.fundamental.main.length,
      after: p9c.stages.fundamental.main.length,
      missing: diff(asSet(p7.stages.fundamental.main), asSet(p9c.stages.fundamental.main)),
      extra: diff(asSet(p9c.stages.fundamental.main), asSet(p7.stages.fundamental.main)),
    },
  );

  // فاز ۱۰ — نشت: presetها چیپ‌های سفارشی را قرض نمی‌گیرند؛ برگشت‌ها مو‌به‌مو
  const swingSelOk = await ensurePressed('funnel-preset-swing', true);
  const keysSwOk = await waitChainKeys(K.swing);
  const settleSwTimeout = await settleTech();
  await sleep(500);
  const pSw = await snap('p10_swing');
  await page.screenshot({ path: `${DIR}/funnel_browser_p10_swing.png` });

  ck(
    'p10: swing کلیدهای مو‌به‌موی خودش را دارد — چیپ‌های روشنِ سفارشی نشت نکردند',
    swingSelOk && keysSwOk && keysEqual(pSw.keys, K.swing) && doorHas(pSw, 'شخص نوسانگیر'),
    { expected: K.swing, got: pSw.keys, doorText: pSw.doorText, swTimeout: settleSwTimeout },
  );
  ck('p10: swing در و زنجیر می‌خوانند و نایکنواست', crossOk(pSw) && monotone(pSw.nums), { door: pSw.door, nums: pSw.nums });

  const hgSelOk = await ensurePressed('funnel-preset-hourglass', true);
  const keysHgOk = await waitChainKeys(K.hourglass);
  const settleHgTimeout = await settleTech();
  await sleep(500);
  const pHg = await snap('p10_hourglass');

  ck(
    'p10: ساعت شنی کلیدهای مو‌به‌موی خودش را دارد (f_roobi + f_clock، بی f_susp/f_legal)',
    hgSelOk && keysHgOk && keysEqual(pHg.keys, K.hourglass) && doorHas(pHg, 'ساعت شنی'),
    { expected: K.hourglass, got: pHg.keys, doorText: pHg.doorText },
  );
  ck('p10: ساعت شنی در و زنجیر می‌خوانند و نایکنواست', crossOk(pHg) && monotone(pHg.nums), { door: pHg.door, nums: pHg.nums });

  const trBackOk = await ensurePressed('funnel-preset-trend', true);
  const keysTrOk = await waitChainKeys(K.trend);
  const settleTrTimeout = await settleTech();
  await sleep(500);
  const pTr = await snap('p10_trend_back');

  ck(
    'p10: بازگشت به روندگیر کلیدهای مو‌به‌موی روندگیر را می‌آورد',
    trBackOk && keysTrOk && keysEqual(pTr.keys, K.trend) && doorHas(pTr, 'شخص روندگیر'),
    { expected: K.trend, got: pTr.keys, doorText: pTr.doorText },
  );

  await gotoTreePage();
  const customBackOk = await selectTreePreset(TREE_CUSTOM);
  await gotoMaster();
  const keysCbOk = await waitChainKeys(K.customAB);
  const settleCbTimeout = await settleTech();
  await sleep(500);
  const pCb = await snap('p10_back_custom');
  await page.screenshot({ path: `${DIR}/funnel_browser_p10_back_custom.png` });

  ck(
    'p10: بازگشت به سفارشی — دوچیپهٔ خودش دقیقاً همان S_AB است (بی‌نشت از گردشِ presetها)',
    customBackOk && keysCbOk && setEq(asSet(pCb.stages.tape.main), SAB) && pCb.chips.f_susp === true && pCb.chips.f_legal === true,
    {
      customBackOk,
      keysCbOk,
      expected: K.customAB,
      got: pCb.keys,
      tape: pCb.stages.tape.main.length,
      SAB: SAB.size,
      missing: diff(SAB, asSet(pCb.stages.tape.main)),
      extra: diff(asSet(pCb.stages.tape.main), SAB),
      chips: pCb.chips,
    },
  );

  // حالتِ مرور: universe = اسکرینر — و برگشت
  const revSelOk = await ensurePressed('funnel-mode-review', true);
  const keysRvOk = await waitChainKeys(K.review);
  const settleRvTimeout = await settleTech();
  await sleep(500);
  const pRv = await snap('p10_review');
  await page.screenshot({ path: `${DIR}/funnel_browser_p10_review.png` });

  ck(
    'p10: حالتِ مرور — زنجیر از اسکرینر شروع می‌شود و در همان قالب می‌گوید',
    revSelOk && keysRvOk && keysEqual(pRv.keys, K.review) && pRv.door.review && doorHas(pRv, 'اسکرینر'),
    { keys: pRv.keys, door: pRv.door, doorText: pRv.doorText },
  );
  ck(
    'p10: گرهٔ اسکرینر = شمارِ در؛ و کارت‌ها/شمارش‌ها در مرور هم می‌خوانند',
    universeNode(pRv) === pRv.door.total &&
      pRv.nums[pRv.keys.indexOf('fundamental')] === pRv.stages.fundamental.main.length &&
      pRv.nums[pRv.keys.indexOf('handover')] === pRv.stages.handover.main.length &&
      pRv.counts.pass === pRv.stages.handover.main.length,
    {
      screenNode: universeNode(pRv),
      door: pRv.door.total,
      fundNode: pRv.nums[pRv.keys.indexOf('fundamental')],
      fundCard: pRv.stages.fundamental.main.length,
      handNode: pRv.nums[pRv.keys.indexOf('handover')],
      handCard: pRv.stages.handover.main.length,
      pass: pRv.counts.pass,
    },
  );
  ck(
    'p10: بودجهٔ تکنیکال در مرور فعال است (universe بزرگ‌تر از سقف ⇒ مازادِ بیرونِ بودجه)',
    pRv.coverage1.universe != null &&
      pRv.coverage1.universe === pRv.counts.universe &&
      pRv.coverage2.wanted === Math.min(pRv.counts.universe ?? 0, 60) &&
      pRv.coverage1.beyond === Math.max(0, (pRv.counts.universe ?? 0) - 60),
    { c1: pRv.coverage1, c2: pRv.coverage2, universe: pRv.counts.universe },
  );

  const revBackOk = await ensurePressed('funnel-mode-reverse', true);
  const keysBkOk = await waitChainKeys(K.customAB);
  const settleBkTimeout = await settleTech();
  await sleep(500);
  const pBk = await snap('p10_back_reverse');

  ck(
    'p10: بازگشت به معکوس — سفارشی و چیپ‌ها دست‌نخورده، همان S_AB',
    revBackOk && keysBkOk && setEq(asSet(pBk.stages.tape.main), SAB) && doorHas(pBk, 'چیپ'),
    {
      revBackOk,
      keysBkOk,
      tape: pBk.stages.tape.main.length,
      SAB: SAB.size,
      missing: diff(SAB, asSet(pBk.stages.tape.main)),
      extra: diff(asSet(pBk.stages.tape.main), SAB),
      doorLabel: pBk.doorLabel,
    },
  );

  (report.notes as string[]).push(
    'چرا این نماد از درِ تابلو افتاد per-symbol در DOMِ قیف نیست (ردیف‌های تابلو why ندارند)؛ علیت از راهِ برابریِ شمار‌ها و بازگشتِ دقیقِ فازهای ۴ و ۶ اثبات شد.',
    '«بیرونِ بودجهٔ تکنیکال» فقط شمارشی است؛ فهرستِ نمادی‌اش در DOM نیست.',
    'ردیف‌های قبول‌شدهٔ بنیادی که درِ تحویل رد/بی‌داده‌اند per-row در کارتِ تحویل نمی‌آیند؛ فقط در شمارش دیده می‌شوند — در p7_invisible ثبت شد.',
  );
} catch (e) {
  (report.steps as Record<string, unknown>).crash = String(e);
  ck('قیف: همهٔ فازها بدون خطای اجرایی تمام شدند', false, String(e));
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
      http: (report.http as string[]).slice(0, 12),
      checks: (report.checks as { name: string; ok: boolean; detail?: unknown }[]).map((c) => ({
        name: c.name,
        ok: c.ok,
        detail: c.ok ? undefined : c.detail,
      })),
    },
    null,
    2,
  ),
);
await browser.close();
