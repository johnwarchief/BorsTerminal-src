// tools/funnel_browser_probe.mts — شاهدِ زندهٔ برابریِ «تابلو ↔ قیف»: همان ورودی، همان
// موتورِ فیلتر، همان نتیجه (§۱۲ و §۱۳ حکمِ مالک) — نُه ورودیِ مستقل و سه پیش‌تنظیم.
// «same input → same filter engine → same result» — حکمِ مالک؛ هیچ threshold یا ruleی عوض نشده.
//
//  فاز ب — برابریِ پایهٔ تابلو: فیلترِ تنها، ترکیب، نردبان، ریست (ورودیِ دو سطح از یک لحظه منجمد می‌شود):
//   ب۰) انجمادِ زندهٔ /api/market و بازپخشِ بایت‌به‌بایت به هر دو سطح؛ ب۱) سرشماریِ هفت چیپ با نگاشتِ یک‌به‌یک؛
//   ب۲) پیچ‌های پایه یک‌بار برایِ همه: live‌only روشن، پسوندِ عددی خاموش، جستجو و صنعت خالی؛
//   ب۳) بی‌چیپ: بدج = کلِ جدول؛ ب۴) خودآزمونِ ابزار: بازپخشِ کامل و دلتای منجمد با بایت‌های یکسان؛
//   ب۵) هر هفت چیپ تک‌تک: شمارِ چیپ (N) = بدج = مجموعهٔ جمع‌شده؛
//   ب۶) ترکیب‌ها [کف‌روبی+نقطه‌زنی] [ساعت+جت] [کف‌روبی+ساعت] [ساعت+جت+حجم] = اشتراکِ تک‌ها؛
//   ب۷) نردبانِ ساعت ⊇ ساعت+جت ⊇ ساعت+جت+حجم (نایکنوا)؛ ب۷ب) تکرارپذیریِ ساعت؛ ب۸) ریست دقیقاً به بدج.
//  فاز ت — برابریِ تابلو ↔ درخت ↔ قیف (حالتِ معکوس، مسیرِ سفارشی) برای نُه ورودیِ یکسان:
//   ت۱) ورودیِ کارتِ تابلو = گروهِ زنجیر = بدج؛ ت۲) کشوی کاندیدا مو‌به‌مو با بدج (پاس/بی‌داده)؛
//   ت۳) شمارِ کلِ بدج همان ورودیِ منجمد؛ ت۰) کنترلِ مثبت: دستِ کم یک ورودی با بدجِ ناصفر.
//  فاز م — معنایِ پیش‌تنظیم‌ها پس از برابریِ پایه (روندگیر، نوسانگیر، ساعتِ شنی):
//   م۱) چیپ‌های فعال = فیلترهای پیش‌تنظیم؛ در، بدج، ورودیِ چیپ و کارت یکی؛ م۲) سه مسیرِ ورودی یکی؛
//   م۳) کارتِ تابلو = بدج؛ م۴) پوششِ تکنیکال حسابش می‌خواند (زنده = بودجهٔ سنجیده، بیرونِ بودجه فقط شمارشی)؛
//   م۵) نشت: چیپِ مرحلهٔ ناهمخوان نباید ورودی و شمارها را عوض کند؛ م۶) پس از م، ریستِ دقیق.
//
//  صداقتِ سنجش:
//   • حالتِ معکوس همهٔ ورودی را از دروازهٔ تابلو عبور می‌دهد (all‌pass به‌حکمِ ساخت)؛
//     پس صفرهای واقعیِ فیلتر فقط در فاز ب اثبات می‌شوند، نه در ت/م.
//   • هیچ عددی برایِ سبز شدنِ آزمون جعل نمی‌شود؛ ورودیِ دو سطح از یک لحظهٔ واحد منجمد می‌شود.
//   • پوششِ تکنیکال و «بیرونِ بودجه» در ت/م فقط شمارشی‌اند؛ فهرستِ نمادی در DOM نیست —
//     آنچه قابلِ اثبات نبود صریحاً «راستی‌آزمایی‌نشده» علامت می‌خورد.
//   • کشوی بنیادی/تحویل فقط قبول‌شده‌ها را نشان می‌دهد (pending ندارد) — تقارنِ اطلاعیِ ثبت‌شده.
//
//  گزارشِ خروجی: report.freeze (انجماد)، report.b_items / t_items / m_items (ردیف‌های آزمون)،
//  report.steps (اسنپ‌ها؛ کلیدهای m_<preset> و m_<preset>_leak)، report.checks (حکم‌ها)، report.verdict.
//   اجرا (بک‌اندِ dev رویِ پورتِ ۸۰۰۲؛ بک‌اندِ نصبیِ ۸۰۰۱ دست نمی‌خورد):
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
    // کانفیگِ چیپ‌هایِ فیلترِ سریع (v۲) ماندگار است؛ سنجش باید از کلیدِ پاک شروع کند
    localStorage.removeItem('bors_tape_filter_config_v2');
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
  // ── ابزارهایِ مشترکِ فازهایِ ب/ت/م: چیپ‌ها، نشانِ شمار، ویرچوال‌اسکرول، درخت و در ──
  const nz = (s: unknown): string => norm(String(s ?? ''));
  const numOf = (t: string | null | undefined): number | null => {
    const m = nz(t).match(/[0-9۰-۹]+/);
    if (!m) return null;
    return /^[0-9]+$/.test(m[0]) ? Number(m[0]) : faNum(m[0]);
  };
  const CHIP_COUNT_RE = /\(([0-9۰-۹]+)\)/;
  const PLUS_RE = /\+\s*\(?([0-9۰-۹]+)/;
  const CHIP_ORDER: string[] = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal'];
  const CHIP_SUB: Record<string, string> = {
    f_clock: 'ساعت',
    f_susp: 'حجم',
    f_jet: 'جت',
    f_roobi: 'روبی',
    f_noqteh: 'نقطه',
    f_smart: 'هوشمند',
    f_legal: 'حقوقی',
  };
  const chipKeyOf = (text: string): string | null => {
    const t = nz(text);
    for (const k of CHIP_ORDER) if (t.includes(CHIP_SUB[k])) return k;
    return null;
  };

  const readChips = async (): Promise<{ total: number; texts: { pressed: boolean; text: string }[] }> => {
    return await page.evaluate(() => {
      const bar = document.querySelector('[data-testid="quick-filters-bar"]');
      if (!bar) return { total: 0, texts: [] as { pressed: boolean; text: string }[] };
      const btns = Array.from(bar.querySelectorAll('button[aria-pressed]'));
      return {
        total: btns.length,
        texts: btns.map((b) => ({ pressed: b.getAttribute('aria-pressed') === 'true', text: (b.textContent || '').trim() })),
      };
    });
  };

  const chipCensus = (texts: { pressed: boolean; text: string }[]): { keys: string[]; pressed: string[]; extra: string[] } => {
    const keys: string[] = [];
    const pressed: string[] = [];
    const extra: string[] = [];
    for (const t of texts) {
      const k = chipKeyOf(t.text);
      if (k === null || keys.includes(k)) {
        extra.push(t.text);
        continue;
      }
      keys.push(k);
      if (t.pressed) pressed.push(k);
    }
    return { keys, pressed, extra };
  };

  const clickChipByKey = async (key: string): Promise<boolean> => {
    const sub = CHIP_SUB[key];
    return await page.evaluate((needle: string) => {
      const bar = document.querySelector('[data-testid="quick-filters-bar"]');
      if (!bar) return false;
      const btns = Array.from(bar.querySelectorAll('button[aria-pressed]'));
      const b = btns.find((x) => (x.textContent || '').includes(needle));
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    }, sub);
  };

  const setChipsExactly = async (want: string[], rounds = 4): Promise<{ ok: boolean; total: number; pressed: string[]; extra: string[] }> => {
    const wantSet = asSet(want);
    for (let r = 0; r < rounds; r++) {
      const cur = await readChips();
      const cen = chipCensus(cur.texts);
      const missing = CHIP_ORDER.filter((k) => wantSet.has(k) && !cen.pressed.includes(k));
      const unwanted = cen.pressed.filter((k) => !wantSet.has(k));
      if (missing.length === 0 && unwanted.length === 0) break;
      for (const k of unwanted) {
        await clickChipByKey(k);
        await sleep(180);
      }
      for (const k of missing) {
        await clickChipByKey(k);
        await sleep(180);
      }
    }
    const fin = await readChips();
    const cen = chipCensus(fin.texts);
    const ok = fin.total === 7 && cen.extra.length === 0 && cen.keys.length === 7 && new Set(cen.keys).size === 7 && setEq(asSet(cen.pressed), wantSet);
    return { ok, total: fin.total, pressed: cen.pressed, extra: cen.extra };
  };

  const readPrefs = async (): Promise<{ search: string | null; sector: string | null; sectorSeen: boolean }> => {
    return await page.evaluate(() => {
      const si = document.querySelector('[data-testid="filters-side"] input[aria-label="جستجوی نماد"]') as HTMLInputElement | null;
      const se = document.querySelector('[data-testid="quick-filters-bar"] select[aria-label="فیلتر صنعت"]') as HTMLSelectElement | null;
      return { search: si ? si.value : null, sector: se ? se.value : null, sectorSeen: !!se };
    });
  };

  const gotoMarket = async (): Promise<void> => {
    if (!page.url().startsWith('http')) {
      await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
    } else {
      await page.evaluate(() => {
        location.hash = '#/market';
      });
    }
    await page.waitForSelector('[data-testid="market-filters-bar"]', { timeout: WAIT });
    await page.waitForSelector('[data-testid="tape-scroll"]', { timeout: WAIT });
    await sleep(350);
  };

  const boardBadgeRaw = async (): Promise<[number | null, number | null] | null> => {
    const raw = await page.evaluate(() => {
      const bar = document.querySelector('[data-testid="market-filters-bar"]');
      if (!bar) return null;
      const el = Array.from(bar.querySelectorAll('span')).find((s) => (s.getAttribute('title') || '').includes('فعال در جدول'));
      return el ? (el.textContent || '') : null;
    });
    if (raw === null) return null;
    const nums = faNums(raw);
    return [nums[0] ?? null, nums[1] ?? null];
  };

  const sameNums = (a: [number | null, number | null] | null, b: [number | null, number | null] | null): boolean =>
    !!a && !!b && a.length === b.length && a.every((x, i) => x === b[i]);

  const waitBadgeStable = async (tries = 40): Promise<[number | null, number | null] | null> => {
    let prev: [number | null, number | null] | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const cur = await boardBadgeRaw();
      const good = !!cur && cur[0] !== null && cur[1] !== null;
      if (good && prev && sameNums(cur, prev)) run += 1;
      else run = good ? 1 : 0;
      prev = good ? cur : null;
      if (run >= 3) return cur;
      await sleep(200);
    }
    return null;
  };

  const waitShownIs = async (target: number, tries = 30): Promise<[number | null, number | null] | null> => {
    for (let i = 0; i < tries; i++) {
      const cur = await boardBadgeRaw();
      if (cur && cur[0] === target && cur[1] === freeze.frozenCount) return cur;
      await sleep(200);
    }
    return null;
  };

  const collectBoard = async (target: number): Promise<Set<string>> => {
    const seen = new Set<string>();
    try {
      await page.setViewportSize({ width: 1632, height: 3600 });
      await sleep(250);
      for (let i = 0; i < 80; i++) {
        const step = await page.evaluate(() => {
          const syms: string[] = [];
          for (const r of Array.from(document.querySelectorAll('[data-testid="tape-row"]'))) {
            const sp = r.querySelector('span');
            const t = sp && sp.childNodes[0] ? (sp.childNodes[0].textContent || '').trim() : '';
            if (t) syms.push(t);
          }
          let atBottom = true;
          const sc = document.querySelector('[data-testid="tape-scroll"]') as HTMLElement | null;
          if (sc) {
            sc.scrollTop = sc.scrollTop + Math.max(120, Math.floor(sc.clientHeight * 0.9));
            atBottom = sc.scrollTop >= sc.scrollHeight - sc.clientHeight - 4;
          }
          return { syms, atBottom };
        });
        for (const s of step.syms) seen.add(norm(s));
        if (seen.size >= target) break;
        if (step.atBottom) break;
        await sleep(160);
      }
    } finally {
      await page.setViewportSize({ width: 1632, height: 950 });
      await sleep(150);
    }
    return seen;
  };

  const readFunnelRaw = async (): Promise<Snap | null> => {
    try {
      const raw = (await readState()) as RawState;
      if (!raw.stages.tape || !raw.stages.technical || !raw.stages.fundamental || !raw.stages.handover) return null;
      return makeState('adhoc', raw);
    } catch {
      return null;
    }
  };

  const snapSig = (s: Snap): string => JSON.stringify(s);

  const waitStableSnap = async (label: string, tries = 25): Promise<Snap | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const s = await readFunnelRaw();
      const sig = s ? snapSig(s) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && s) {
        (report.steps as Record<string, unknown>)[label] = s;
        return s;
      }
      await sleep(350);
    }
    return null;
  };

  const waitCovStable = async (tries = 25): Promise<Snap | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const s = await readFunnelRaw();
      const sig = s ? JSON.stringify({ c1: s.coverage1, c2: s.coverage2, counts: s.counts }) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && s) return s;
      await sleep(400);
    }
    return null;
  };

  const readTreeCard = async (): Promise<{ big: number | null; input: number | null; universe: number | null } | null> => {
    const raw = await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button[aria-label]')).find((b) => {
        const l = (b.getAttribute('aria-label') || '').replace(/\u200c/g, '');
        return l.includes('مشاهده') && l.includes('تابلو');
      });
      if (!btn) return null;
      let card: Element | null = btn;
      for (let i = 0; i < 5 && card; i++) {
        const t = (card.textContent || '').replace(/\u200c/g, '');
        if (t.includes('بازماندگان')) break;
        card = card.parentElement;
      }
      if (!card) return null;
      const bigEl = Array.from(card.querySelectorAll('span')).find((s) => /^[۰-۹]+$/.test((s.textContent || '').trim()));
      const big = bigEl ? (bigEl.textContent || '').trim() : null;
      const inEl = Array.from(card.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').includes('ورودی'));
      const input = inEl ? (inEl.textContent || '') : null;
      const uEl = Array.from(document.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').trim() === 'نماد فعال');
      const universe = uEl && uEl.previousElementSibling ? (uEl.previousElementSibling.textContent || '') : null;
      return { big, input, universe };
    });
    if (!raw) return null;
    return { big: numOf(raw.big), input: numOf(raw.input), universe: numOf(raw.universe) };
  };

  const waitTreeStable = async (tries = 25): Promise<{ big: number | null; input: number | null; universe: number | null } | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const cur = await readTreeCard();
      const good = !!cur && cur.big !== null && cur.universe !== null;
      const sig = good ? JSON.stringify(cur) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && cur) return cur;
      await sleep(320);
    }
    return null;
  };

  const openTapeDrawer = async (): Promise<boolean> => {
    const hit = await page.evaluate(() => {
      const b = Array.from(document.querySelectorAll('button[aria-label]')).find((x) => {
        const l = (x.getAttribute('aria-label') || '').replace(/\u200c/g, '');
        return l.includes('مشاهده') && l.includes('تابلو');
      });
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    });
    if (!hit) return false;
    try {
      await page.waitForSelector('[data-testid="stage-candidate-drawer"]', { timeout: 15000 });
      return true;
    } catch {
      return false;
    }
  };

  const readTapeDrawerRaw = async (): Promise<{ total: number | null; rows: { sym: string; status: string | null; why: string }[] } | null> => {
    const raw = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="stage-candidate-drawer"]');
      if (!root) return null;
      const tEl = Array.from(root.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').includes('مجموع'));
      const totalText = tEl && tEl.parentElement ? (tEl.parentElement.textContent || '') : null;
      const rows: { sym: string; status: string | null; why: string }[] = [];
      for (const tr of Array.from(root.querySelectorAll('tbody tr'))) {
        const tds = Array.from(tr.querySelectorAll('td'));
        const first = tds[0] ? tds[0].querySelector('span') : null;
        const sym = first ? (first.textContent || '').trim() : '';
        let status: string | null = null;
        for (const td of tds) {
          const m = (td.textContent || '').match(/(PASS|REJECT|PENDING|UNAVAILABLE)/);
          if (m) {
            status = m[1];
            break;
          }
        }
        const why = tds.length > 0 ? (tds[tds.length - 1].textContent || '').trim() : '';
        rows.push({ sym, status, why });
      }
      return { totalText, rows };
    });
    if (!raw) return null;
    return { total: numOf(raw.totalText), rows: raw.rows };
  };

  const closeTapeDrawer = async (): Promise<boolean> => {
    const hit = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="stage-candidate-drawer"]');
      if (!root) return false;
      const b = Array.from(root.querySelectorAll('button[aria-label]')).find((x) => (x.getAttribute('aria-label') || '').includes('بستن'));
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    });
    if (!hit) return false;
    return await waitGone('[data-testid="stage-candidate-drawer"]');
  };

  // ── فریزِ داده: یک لحظه از api/market، همان لحظه برایِ هر دو سطح ──
  const freeze: {
    ok: boolean;
    err: string | null;
    frozenRev: number | null;
    frozenStatus: string | null;
    frozenCount: number;
    bodyBytes: number;
    fullReplay: number;
    deltaBlocked: number;
  } = { ok: false, err: null, frozenRev: null, frozenStatus: null, frozenCount: 0, bodyBytes: 0, fullReplay: 0, deltaBlocked: 0 };
  let frozenText = '';
  const frozenSyms = new Set<string>();
  try {
    const fr = await fetch(new URL('api/market', BASE));
    if (!fr.ok) throw new Error('HTTP ' + fr.status);
    const ft = await fr.text();
    const fj = JSON.parse(ft) as { status?: string; rev?: number; data?: { symbol?: string }[] };
    const fdata = Array.isArray(fj.data) ? fj.data : [];
    freeze.frozenStatus = typeof fj.status === 'string' ? fj.status : null;
    freeze.frozenRev = typeof fj.rev === 'number' ? fj.rev : null;
    freeze.frozenCount = fdata.length;
    freeze.bodyBytes = Buffer.byteLength(ft, 'utf8');
    frozenText = ft;
    for (const row of fdata) {
      const sym = norm(row && row.symbol != null ? String(row.symbol) : '');
      if (sym) frozenSyms.add(sym);
    }
    freeze.ok = freeze.frozenCount > 0;
    if (!freeze.ok) freeze.err = 'snapshot empty (status=' + String(freeze.frozenStatus) + ')';
  } catch (e) {
    freeze.err = String(e);
  }
  if (freeze.ok) {
    await context.route(/\/api\/market(\?.*)?$/, async (route) => {
      freeze.fullReplay += 1;
      await route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: frozenText });
    });
    await context.route(/\/api\/market\/delta(\?.*)?$/, async (route) => {
      freeze.deltaBlocked += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ status: 'unchanged', rev: freeze.frozenRev ?? 0, meta: null, count: freeze.frozenCount, live_count: null, fossil_count: null }),
      });
    });
  }
  report.freeze = freeze;

  // ── نتیجه‌های خامِ فازهایِ ب/ت/م برایِ گزارش ──
  const B_ITEMS: Record<string, unknown>[] = [];
  const T_ITEMS: Record<string, unknown>[] = [];
  const M_ITEMS: Record<string, unknown>[] = [];
  const M_PAIRS: Record<string, string[]> = {
    trend: ['f_roobi', 'f_noqteh'],
    swing: ['f_clock', 'f_jet', 'f_susp'],
    hourglass: ['f_roobi', 'f_clock'],
  };
  report.b_items = B_ITEMS;
  report.t_items = T_ITEMS;
  report.m_items = M_ITEMS;
  // ── فازِ ب: تابلو، مستقل — چیپِ تک، ترکیبِ AND، رهیابِ صفر، بازنشانی، بی هیچ قیف ──
  await gotoMarket();
  await sleep(700);
  await page.screenshot({ path: `${DIR}/funnel_parity_board.png` });

  ck('ب۰', freeze.ok && freeze.frozenCount > 0, { ok: freeze.ok, count: freeze.frozenCount, rev: freeze.frozenRev, status: freeze.frozenStatus, err: freeze.err });

  const chips0 = await readChips();
  const cen0 = chipCensus(chips0.texts);
  const chipsBijective = chips0.total === 7 && cen0.extra.length === 0 && cen0.keys.length === 7 && new Set(cen0.keys).size === 7;
  ck('ب۱', chipsBijective, { total: chips0.total, keys: cen0.keys, extra: cen0.extra });

  const liveOn = await ensurePressed('live-only-toggle', true);
  const suffixOn = await ensurePressed('numeric-suffix-toggle', true);
  const prefs2 = await readPrefs();
  const prefsClean = prefs2.search === '' && prefs2.sectorSeen && prefs2.sector === '';
  ck('ب۲', liveOn && suffixOn && prefsClean, { liveOn, suffixOn, search: prefs2.search, sector: prefs2.sector, sectorSeen: prefs2.sectorSeen });

  const off = await setChipsExactly([]);
  const badge0 = await waitBadgeStable();
  const u0 = await collectBoard(badge0 && badge0[0] != null ? badge0[0] : 0);
  const removedVsFrozen = diff(frozenSyms, u0);
  const b3ok =
    off.ok && !!badge0 && badge0[0] != null && badge0[0] > 0 && badge0[1] === freeze.frozenCount && u0.size === badge0[0] && isSubset(u0, frozenSyms);
  ck('ب۳', b3ok, {
    chipsOffOk: off.ok,
    badge: badge0,
    u0Size: u0.size,
    frozenCount: freeze.frozenCount,
    subsetOfFrozen: isSubset(u0, frozenSyms),
    offFrozenCount: removedVsFrozen.length,
    offFrozenSample: removedVsFrozen.slice(0, 80),
  });

  const b4 = await page.evaluate(async () => {
    const enc = new TextEncoder();
    const ft = await (await fetch('api/market')).text();
    const dt = await (await fetch('api/market/delta?since=1')).text();
    let fullN = 0;
    let fullRev: number | null = null;
    let deltaStatus: string | null = null;
    try {
      const j = JSON.parse(ft) as { rev?: number; data?: unknown[] };
      fullN = Array.isArray(j.data) ? j.data.length : 0;
      fullRev = typeof j.rev === 'number' ? j.rev : null;
    } catch {}
    try {
      const j = JSON.parse(dt) as { status?: string };
      deltaStatus = typeof j.status === 'string' ? j.status : null;
    } catch {}
    return { fullN, fullRev, fullBytes: enc.encode(ft).length, deltaStatus };
  });
  const b4ok =
    b4.fullN === freeze.frozenCount &&
    b4.fullRev === freeze.frozenRev &&
    b4.fullBytes === freeze.bodyBytes &&
    (freeze.frozenRev == null || b4.deltaStatus === 'unchanged') &&
    freeze.fullReplay > 0 &&
    (freeze.frozenRev == null || freeze.deltaBlocked > 0);
  ck('ب۴', b4ok, { ...b4, frozenCount: freeze.frozenCount, frozenRev: freeze.frozenRev, bodyBytes: freeze.bodyBytes, fullReplay: freeze.fullReplay, deltaBlocked: freeze.deltaBlocked });

  const singles: Record<string, Set<string>> = {};
  for (const k of CHIP_ORDER) {
    const arm = await setChipsExactly([k]);
    const badge = await waitBadgeStable();
    const cur = await readChips();
    const tFound = cur.texts.find((t) => chipKeyOf(t.text) === k);
    const chipText = tFound ? tFound.text : null;
    const cm = chipText ? chipText.match(CHIP_COUNT_RE) : null;
    const pm = chipText ? chipText.match(PLUS_RE) : null;
    const chipCount = cm ? numOf(cm[1]) : null;
    const plus = pm ? numOf(pm[1]) : null;
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    singles[k] = col;
    const countOk = chipCount === null ? !!badge && badge[0] === 0 : !!badge && chipCount === badge[0];
    const ok = arm.ok && !!badge && badge[0] != null && col.size === badge[0] && isSubset(col, u0) && countOk;
    B_ITEMS.push({
      focus: 'single',
      key: k,
      ok,
      armOk: arm.ok,
      badgeShown: badge ? badge[0] : null,
      badgeTotal: badge ? badge[1] : null,
      collected: [...col].sort(),
      chipCount,
      chipText,
      plus,
      subsetOfU0: isSubset(col, u0),
      removedVsU0: diff(u0, col),
      extraVsU0: diff(col, u0),
    });
  }

  let unionAll = new Set<string>();
  for (const k of CHIP_ORDER) unionAll = uni(unionAll, singles[k]);
  const combos: { id: string; keys: string[] }[] = [
    { id: 'roobi+noqteh', keys: ['f_roobi', 'f_noqteh'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
    { id: 'roobi+clock', keys: ['f_roobi', 'f_clock'] },
    { id: 'clock+jet+susp', keys: ['f_clock', 'f_jet', 'f_susp'] },
  ];
  for (const cb of combos) {
    const arm = await setChipsExactly(cb.keys);
    const badge = await waitBadgeStable();
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    let expect = singles[cb.keys[0]];
    for (let i = 1; i < cb.keys.length; i++) expect = inter(expect, singles[cb.keys[i]]);
    const s0 = singles[cb.keys[0]];
    const s1 = singles[cb.keys[1]];
    const disc = unionAll.size > expect.size || s0.size === 0 || s1.size === 0 || setEq(s0, s1);
    const ok = arm.ok && !!badge && badge[0] != null && setEq(col, expect) && col.size === badge[0] && disc;
    B_ITEMS.push({
      focus: 'combo',
      id: cb.id,
      keys: cb.keys,
      ok,
      armOk: arm.ok,
      badgeShown: badge ? badge[0] : null,
      badgeTotal: badge ? badge[1] : null,
      collected: [...col].sort(),
      expected: [...expect].sort(),
      discriminator: disc,
      onlyBoard: diff(col, expect),
      onlyExpected: diff(expect, col),
    });
  }

  const ladder: { id: string; keys: string[] }[] = [
    { id: 'clock', keys: ['f_clock'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
    { id: 'clock+jet+susp', keys: ['f_clock', 'f_jet', 'f_susp'] },
  ];
  const ladderSets: Set<string>[] = [];
  for (const st of ladder) {
    const arm = await setChipsExactly(st.keys);
    const badge = await waitBadgeStable();
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    ladderSets.push(col);
  }
  const ladderOk = ladderSets.length === 3 && ladderSets.every((c, i) => i === 0 || isSubset(c, ladderSets[i - 1]));
  ck('ب۷', ladderOk && monotone(ladderSets.map((c) => c.size)), {
    sizes: ladderSets.map((c) => c.size),
    subset: ladderSets.map((c, i) => (i === 0 ? null : isSubset(c, ladderSets[i - 1]))),
  });

  const arm7b = await setChipsExactly(['f_clock']);
  const badge7b = await waitBadgeStable();
  const col7b = badge7b ? await collectBoard(badge7b[0] ?? 0) : new Set<string>();
  const b7bok = arm7b.ok && setEq(col7b, ladderSets[0]);
  ck('ب۷ب', b7bok, { sizeRecheck: col7b.size, sizeFirst: ladderSets[0].size, onlyRecheck: diff(col7b, ladderSets[0]), onlyFirst: diff(ladderSets[0], col7b) });

  await setChipsExactly(['f_clock']);
  await clickT('filters-reset');
  const shown8 = await waitShownIs(u0.size);
  const col8 = await collectBoard(u0.size);
  const live8 = (await pressOf('live-only-toggle')) === 'true';
  const suffix8 = (await pressOf('numeric-suffix-toggle')) === 'true';
  const cen8 = chipCensus((await readChips()).texts);
  const b8ok = !!shown8 && setEq(col8, u0) && live8 && suffix8 && cen8.pressed.length === 0 && cen8.extra.length === 0;
  ck('ب۸', b8ok, {
    shown: shown8,
    resetEqualsU0: setEq(col8, u0),
    liveOnly: live8,
    numericSuffixHidden: suffix8,
    pressedAfterReset: cen8.pressed,
    extra: cen8.extra,
    onlyAfter: diff(col8, u0),
    onlyBefore: diff(u0, col8),
  });
  // ── فازِ ت: درختِ استراتژی در مسیرِ معکوس — همان ورودی، همان نتیجه، نماد به نماد ──
  const tCases: { id: string; keys: string[] }[] = [
    ...CHIP_ORDER.map((k) => ({ id: k, keys: [k] })),
    { id: 'roobi+noqteh', keys: ['f_roobi', 'f_noqteh'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
  ];
  let anyShownT = false;
  for (const tc of tCases) {
    const item: Record<string, unknown> = {
      name: tc.id,
      keys: tc.keys,
      armOk: false,
      badge: null,
      bCollected: [],
      tree: null,
      drawerPresent: false,
      drawerClosed: false,
      drawerTotal: null,
      t1: false,
      t2: false,
      t3: false,
      t2Bad: [],
      t2OnlyDrawer: [],
      t2OnlyBoard: [],
      statusHist: {},
      ok: false,
    };
    try {
      await gotoMarket();
      const arm = await setChipsExactly(tc.keys);
      item.armOk = arm.ok;
      const badge = await waitBadgeStable();
      item.badge = badge;
      if (!badge) throw new Error('badge not stable');
      if ((badge[0] ?? 0) > 0) anyShownT = true;
      const bSet = await collectBoard(badge[0] ?? 0);
      item.bCollected = [...bSet].sort();
      await gotoMaster();
      await ensurePressed('funnel-mode-reverse', true);
      await gotoTreePage();
      try {
        await selectTreePreset(TREE_CUSTOM);
      } catch {}
      await sleep(700);
      const tn = await waitTreeStable();
      item.tree = tn;
      const drawerPresent = await openTapeDrawer();
      item.drawerPresent = drawerPresent;
      if (tc.id === tCases[0].id) {
        await page.screenshot({ path: `${DIR}/funnel_parity_t_drawer.png` });
      }
      const dr = await readTapeDrawerRaw();
      item.drawerTotal = dr ? dr.total : null;
      item.drawerClosed = await closeTapeDrawer();
      const t1 = !!tn && tn.big === badge[0] && tn.input === badge[0] && tn.universe === badge[0];
      const dsyms = dr ? dr.rows.map((r) => norm(r.sym)) : [];
      let t2: boolean;
      if ((badge[0] ?? 0) === 0) {
        t2 = !drawerPresent || dr === null || dr.rows.length === 0;
      } else {
        t2 =
          !!dr &&
          dr.total === bSet.size &&
          setEq(asSet(dsyms), bSet) &&
          dr.rows.every((r) => r.status === 'PASS' || (r.status === 'UNAVAILABLE' && nz(r.why).length > 0));
      }
      const t3 = badge[1] === freeze.frozenCount;
      const hist: Record<string, number> = {};
      if (dr) for (const r of dr.rows) hist[String(r.status)] = (hist[String(r.status)] ?? 0) + 1;
      item.t2Bad = dr
        ? dr.rows
            .filter((r) => !(r.status === 'PASS' || (r.status === 'UNAVAILABLE' && nz(r.why).length > 0)))
            .map((r) => ({ sym: norm(r.sym), status: r.status, why: r.why }))
        : [];
      item.t2OnlyDrawer = dr ? diff(asSet(dsyms), bSet) : [];
      item.t2OnlyBoard = dr ? diff(bSet, asSet(dsyms)) : [];
      item.statusHist = hist;
      item.t1 = t1;
      item.t2 = t2;
      item.t3 = t3;
      ck(`ت۱-${tc.id}`, t1, { tree: tn, badgeShown: badge[0] });
      ck(`ت۲-${tc.id}`, t2, { badgeShown: badge[0], drawerPresent, drawerTotal: dr ? dr.total : null, rows: dr ? dr.rows.length : 0, statusHist: hist, onlyDrawer: item.t2OnlyDrawer, onlyBoard: item.t2OnlyBoard });
      ck(`ت۳-${tc.id}`, t3, { badgeTotal: badge[1], frozenCount: freeze.frozenCount });
    } catch (e) {
      item.err = String(e);
    }
    item.ok = item.armOk === true && item.t1 === true && item.t2 === true && item.t3 === true && !item.err;
    T_ITEMS.push(item);
  }
  ck('ت۰', anyShownT, { anyShown: anyShownT });

  // ── فازِ م: پریست‌های قیف — فیلترها همان نتیجهٔ تابلو، پریست فقط چیدمانِ مراحل ──
  const u0Size = u0.size;
  for (const p of ['trend', 'swing', 'hourglass']) {
    const pair = M_PAIRS[p];
    const item: Record<string, unknown> = {
      preset: p,
      keys: pair,
      armOk: false,
      badge: null,
      collected: [],
      revOk: false,
      revOk2: false,
      presetOk: false,
      chainOk: false,
      techSettled: null,
      m1: false,
      m2: false,
      m3: false,
      m4: false,
      leakOk: false,
      restoreOk: false,
      ok: false,
    };
    try {
      await gotoMarket();
      const arm = await setChipsExactly(pair);
      item.armOk = arm.ok;
      const badge = await waitBadgeStable();
      item.badge = badge;
      if (!badge) throw new Error('badge not stable');
      const mSet = await collectBoard(badge[0] ?? 0);
      item.collected = [...mSet].sort();
      await gotoMaster();
      item.revOk = await ensurePressed('funnel-mode-reverse', true);
      item.revOk2 = (await pressOf('funnel-mode-reverse')) === 'true';
      item.presetOk = await ensurePressed(`funnel-preset-${p}`, true);
      const chainOk = await waitChainKeys(K[p]);
      item.chainOk = chainOk;
      item.techSettled = !(await settleTech());
      await sleep(400);
      const s = await waitStableSnap(`m_${p}`);
      const gotSet = s ? new Set(CHIP_ORDER.filter((kk) => s.chips[kk] === true)) : new Set<string>();
      const m1 =
        !!s &&
        arm.ok &&
        item.revOk === true &&
        item.revOk2 === true &&
        item.presetOk === true &&
        chainOk &&
        setEq(gotSet, asSet(pair)) &&
        s.chips.f_legal === false &&
        s.door.boardScope === u0Size &&
        s.door.total === mSet.size &&
        s.chipInput === mSet.size &&
        s.stages.tape.countBadge === mSet.size;
      const m2 = !!s && s.door.total === s.counts.universe && s.counts.universe === s.chipInput && s.chipInput === mSet.size;
      const m3 = !!s && setEq(asSet(s.stages.tape.main), mSet);
      const s4 = await waitCovStable();
      const m4 =
        !!s4 &&
        s4.coverage1.universe === mSet.size &&
        s4.counts.universe === mSet.size &&
        (mSet.size === 0 ? s4.coverage2.raw == null : s4.coverage2.wanted === Math.min(mSet.size, 60) && s4.coverage2.resolved === s4.coverage1.live);
      item.m1 = m1;
      item.m2 = m2;
      item.m3 = m3;
      item.m4 = m4;
      ck(`م۱-${p}`, m1, {
        gotChips: [...gotSet].sort(),
        boardScope: s ? s.door.boardScope : null,
        u0Size,
        doorTotal: s ? s.door.total : null,
        chipInput: s ? s.chipInput : null,
        tapeBadge: s ? s.stages.tape.countBadge : null,
        mSetSize: mSet.size,
      });
      ck(`م۲-${p}`, m2, { doorTotal: s ? s.door.total : null, countsUniverse: s ? s.counts.universe : null, chipInput: s ? s.chipInput : null, mSetSize: mSet.size });
      ck(`م۳-${p}`, m3, {
        tapeMain: s ? s.stages.tape.main.length : null,
        mSetSize: mSet.size,
        onlyTape: s ? diff(asSet(s.stages.tape.main), mSet) : [],
        onlyBoard: s ? diff(mSet, asSet(s.stages.tape.main)) : [],
      });
      ck(`م۴-${p}`, m4, { coverage1: s4 ? s4.coverage1 : null, coverage2: s4 ? s4.coverage2 : null, mSetSize: mSet.size, beyond: s4 ? s4.coverage1.beyond : null });
      let leakOk = false;
      let restoreOk = false;
      let leakDetail: Record<string, unknown> = { skipped: true };
      if (s) {
        let clicked = false;
        try {
          await clickT('funnel-tape-chip-f_legal');
          clicked = true;
        } catch {}
        await sleep(700);
        await settleTech();
        const post = await waitStableSnap(`m_${p}_leak`);
        leakOk =
          clicked &&
          !!post &&
          post.chips.f_legal === true &&
          keysEqual(post.keys, s.keys) &&
          nz(post.doorText) === nz(s.doorText) &&
          post.chipInput === s.chipInput &&
          post.counts.universe === s.counts.universe &&
          setEq(asSet(post.stages.tape.main), asSet(s.stages.tape.main));
        if (clicked) {
          try {
            await clickT('funnel-tape-chip-f_legal');
          } catch {}
          await sleep(500);
          restoreOk = (await pressOf('funnel-tape-chip-f_legal')) === 'false';
        }
        leakDetail = {
          clicked,
          leakOk,
          restoreOk,
          preUniverse: s.counts.universe,
          postUniverse: post ? post.counts.universe : null,
          preTape: s.stages.tape.main.length,
          postTape: post ? post.stages.tape.main.length : null,
          preDoor: s.door.total,
          postDoor: post ? post.door.total : null,
        };
      }
      ck(`م۵-${p}`, leakOk && restoreOk, leakDetail);
      item.leakOk = leakOk;
      item.restoreOk = restoreOk;
      item.ok = m1 && m2 && m3 && m4 && leakOk && restoreOk;
    } catch (e) {
      item.err = String(e);
    }
    M_ITEMS.push(item);
  }

  await gotoMarket();
  const offM6 = await setChipsExactly([]);
  const shownM6 = await waitShownIs(u0Size);
  const colM6 = await collectBoard(u0Size);
  const m6ok = offM6.ok && !!shownM6 && setEq(colM6, u0);
  ck('م۶', m6ok, { offOk: offM6.ok, shown: shownM6, equalsU0: setEq(colM6, u0), onlyAfter: diff(colM6, u0), onlyBefore: diff(u0, colM6) });

  (report.notes as string[]).push(
    'فریزِ داده: یک لحظه از api/market (rev و شمارِ ردیف) برایِ هر دو سطح بازپخش شد؛ درستیِ خودِ ابزار در فازِ ب آزموده شد.',
    'در حالتِ معکوس، عبورِ فیلترها ساختاری است و «زنده‌ماندن» را ثابت نمی‌کند؛ صفرهای واقعی فقط در فازِ ب اثبات می‌شوند.',
    'پوششِ تکنیکال در فازِ م فقط شمارشی است و سقفِ ۶۰ «راستی‌آزمایی‌نشده» می‌ماند؛ ناهمسانیِ چیپ و پریست در م۵ ثبت شد.',
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
