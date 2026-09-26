// features/portfolio/stores/targetAllocation.ts -- استور محلی پرتفوی هدف
// state هدف/فعلی طبق ماموریت باید داخل features/portfolio باشد — نه استور اشتراکی.
// persist با localStorage؛ نرمال‌سازی جمع درصدها به ۱۰۰٪.
import { create } from 'zustand';
import { toFaDigits } from '@shared/lib/fmt';

/** یک طبقه دارایی هدف */
export type TargetClass = {
  id: string;
  label: string;
  /** درصد پیشنهادی FTS (نقطه شروع) */
  pct: number;
  /** رنگ CSS برای چارت دونات */
  color: string;
  /** توضیح طبقه */
  hint?: string;
};

/** طبقات پیش‌فرض FTS — نسبت‌های مصوب سند: طلا و سکه ۴۵٪ (فیزیکی+گواهی) · سهام ۱۵٪ · ارز دیجیتال ۱۵٪ · نقره ۱۰٪ · درآمد ثابت ۱۵٪ — جمع ۱۰۰٪ */
export const FTS_DEFAULT_TARGETS: TargetClass[] = [
  { id: 'gold', label: 'طلای فیزیکی، سکه و شمش', pct: 30, color: '#f59e0b', hint: '۴۵٪ طلا و سکه طبق سند (فیزیکی + گواهی) — پوشش ریسک تورمی/جنگی' },
  { id: 'gold-cert', label: 'صندوق‌ها و گواهی سپردهٔ طلا', pct: 15, color: '#eab308', hint: 'مکمل طلا تا سقف ۴۵٪ سند' },
  { id: 'crypto', label: 'ارز دیجیتال', pct: 15, color: '#22d3ee', hint: '۱۵٪ طبق سند مدیریت سرمایه' },
  { id: 'silver', label: 'نقره / گواهی سپردهٔ کالایی', pct: 10, color: '#94a3b8', hint: '۱۰٪ طبق سند' },
  { id: 'equity', label: 'صندوق سهامی و سهام مستقیم', pct: 15, color: '#10b981', hint: '۱۵٪ سهام مستقیم — سقف هر تک‌سهم ۲۰٪' },
  { id: 'fixed', label: 'صندوق درآمد ثابت / نقدینگی پارک‌شده', pct: 15, color: '#64748b', hint: '۱۵٪ درآمد ثابت و نقدینگی' },
];

const STORAGE_KEY = 'bors-portfolio-target';

/** جمع درصدها؛ درصد نامعتبر صفر حساب می‌شود */
export function sumPct(classes: TargetClass[]): number {
  return classes.reduce((s, c) => s + (Number.isFinite(c.pct) && c.pct > 0 ? c.pct : 0), 0);
}

/** نرمال‌سازی به ۱۰۰٪ — جمع صفر یعنی بدون تغییر (بازگشت به پیش‌فرض) */
export function normalizePct(classes: TargetClass[]): TargetClass[] {
  const total = sumPct(classes);
  if (total <= 0) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
  if (Math.abs(total - 100) < 0.05) return classes.map((c) => ({ ...c }));
  return classes.map((c) => ({
    ...c,
    pct: Math.round(((c.pct > 0 ? c.pct : 0) / total) * 1000) / 10,
  }));
}

/** اعتبارسنجی: جمع ≤ ۱۰۰ (اجازه فضای نقد آزاد بیشتر) */
export function isValidAllocation(classes: TargetClass[]): boolean {
  const total = sumPct(classes);
  return total > 0 && total <= 100 + 1e-9;
}

function loadInitial(): TargetClass[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
    const parsed = JSON.parse(raw) as TargetClass[];
    if (!Array.isArray(parsed) || parsed.length === 0) return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
    return parsed.map((c) => ({ ...c, pct: Number(c.pct) || 0 }));
  } catch {
    return FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
  }
}

type TargetState = {
  classes: TargetClass[];
  /** نمای فعال: هدف یا فعلی */
  view: 'target' | 'current';
  setView: (v: 'target' | 'current') => void;
  /** ویرایش دستی درصدها — قبل از ذخیره نرمال می‌شود */
  setClasses: (classes: TargetClass[]) => void;
  editClass: (id: string, pct: number) => void;
  addClass: (c: TargetClass) => void;
  removeClass: (id: string) => void;
  reset: () => void;
};

export const useTargetAllocation = create<TargetState>((set) => {
  const persist = (classes: TargetClass[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(classes));
    } catch {
      // حافظه در دسترس نیست — فقط state
    }
  };
  return {
    classes: loadInitial(),
    view: 'target',
    setView: (v) => set({ view: v }),
    setClasses: (classes) => {
      const norm = normalizePct(classes);
      persist(norm);
      set({ classes: norm });
    },
    editClass: (id, pct) =>
      set((s) => {
        const next = s.classes.map((c) => (c.id === id ? { ...c, pct: Math.max(0, Math.round(pct * 10) / 10) } : c));
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    addClass: (c) =>
      set((s) => {
        const next = [...s.classes, c];
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    removeClass: (id) =>
      set((s) => {
        const next = s.classes.filter((c) => c.id !== id);
        persist(normalizePct(next));
        return { classes: normalizePct(next) };
      }),
    reset: () => {
      const fresh = FTS_DEFAULT_TARGETS.map((c) => ({ ...c }));
      persist(fresh);
      set({ classes: fresh });
    },
  };
});

// ─── نوار شکاف و ری‌بالانس (Rebalancing Delta) ──────────────────────────

export type DeltaRow = {
  id: string;
  label: string;
  color: string;
  targetPct: number;
  /**
   * وزنِ فعلی همان طبقه؛ null یعنی «اندازه‌ای نداریم».
   * صفرِ ساختگی ممنوع است: «طلا ۰٪ — هدف ۴۵٪» یعنی کسریِ ۴۵ واحدی، در حالی که
   * یعنی «نمی‌دانیم». (#106)
   */
  currentPct: number | null;
  /** مخرجِ درصدِ فعلی: 'capital' = از کلِ سرمایه، 'basket' = فقط از سبد */
  basis: DeltaBasis;
  /** مازاد/کسری؛ null یعنی داوری نداریم */
  delta: number | null;
  /** چرا عددی نیست — برای متنِ صادقانهٔ ردیف */
  reason: string | null;
  /** منبعِ اندازهٔ فعلی؛ دونات و نوارِ شکاف یک عدد را یک‌جا می‌سنجند (#106) */
  measure: DeltaMeasure;
  /**
   * هدفِ *طبقه* وقتی چند ردیفِ هدف یک طبقه‌اند (طلا = فیزیکی + گواهی).
   * تابلو نمی‌تواند این دو را از هم بشناسد، پس مقایسه با جمعِ هدف‌های آن‌ها
   * انجام می‌شود؛ بیرونِ این، delta با targetPctِ خودِ ردیف بی‌معناست.
   */
  classTargetPct?: number;
  /** نامِ ردیف‌های هم‌طبقه — برای این‌که کاربر بداند عدد مال کدام دو سطر است */
  classLabel?: string;
};

export type DeltaBasis = 'capital' | 'basket' | null;

/** از کدام منبع اندازه گرفتیم — دونات و نوارِ شکاف باید یک عدد را یک‌جا بسنجند */
export type DeltaMeasure = 'class_mix' | 'basket_weights' | 'asset_value' | null;

/**
 * کلیدهای class_mix_pctِ بک‌اند (خروجیِ mstat_engine.classify) → شناسهٔ طبقهٔ هدف.
 * منبعِ یکتاست: صندوقِ سهامی و سهامِ مستقیم هر دو «سهام»اند؛ صندوقِ درآمد ثابت
 * همان «نقدینگی/درآمد ثابت» است. طبقه‌ای که این‌جا نیست (مثلاً crypto) از تابلو
 * قابل شناختن نیست و فقط از ارزشِ دستی خوانده می‌شود.
 */
export const MIX_KEY_TO_CLASS: Record<string, string> = {
  gold: 'gold',
  silver: 'silver',
  fixed: 'fixed',
  stock: 'equity',
  equity: 'equity',
  // حقِ تقدم ادعای سهامی است و در جزوه هم سهام شمرده می‌شود؛ نگاشتِ نبودش یعنی
  // وزنِ یک ردیفِ سهامی بی‌صدا از ترکیبِ فعلی بیفتد.
  right: 'equity',
  mixed: 'equity',
  lev: 'equity',
  commod: 'equity',
  fof: 'equity',
  etf: 'equity',
};

/** «طلا و سکه» دو ردیفِ هدف را می‌پوشاند (فیزیکی + گواهی سپرده) → یکی شمرده می‌شود */
const CLASS_ALIAS: Record<string, string> = { 'gold-cert': 'gold' };

/** کلیدِ طبقهٔ یک ردیف، همان‌طور که بک‌اند در /api/selection/portfolio می‌سازد:
 *  صندوق‌ها با kind (gold/fixed/lev/…) و بقیه با cls (stock/right/…) شناخته می‌شوند. */
function rowClassKey(ac: { cls: string; kind?: string | null }): string {
  return ac.cls === 'fund' ? (ac.kind ?? '') : ac.cls;
}

export type DeltaHolding = {
  weight_eff_pct?: number | null;
  /** طبقهٔ ردیف از سمتِ بک‌اند؛ null/undefined یعنی «نمی‌دانیم» */
  asset_class?: { cls: string; kind?: string | null } | null;
};

export type DeltaInputs = {
  /** درصدِ هر طبقهٔ دارایی از سبد، آن‌طور که بک‌اند از classify ساخته است */
  classMixPct?: Record<string, number> | null;
  /** ارزشِ ریالی خودِ سبد (قیمت × تعدادِ ردیف‌ها)؛ null یعنی ناقص */
  basketValueToman?: number | null;
  /** کلِ سرمایهٔ ثبت‌شده (دارایی‌های غیرسهامی + نقدینگی) */
  totalToman?: number;
  /** ارزشِ دستی هر طبقه (تومان) — تنها منبعِ طبقاتی که تابلو نمی‌شناسد */
  valuesByClass?: Record<string, number>;
};

/** درصدِ سبد به مخرجِ کلِ سرمایه؛ بی‌ارزشِ سبد یا سرمایه، همان درصدِ سبد می‌ماند */
function toCapitalPct(
  pctOfBasket: number,
  basketValue: number | null | undefined,
  totalToman: number | undefined,
): { pct: number; basis: Exclude<DeltaBasis, null> } {
  const round = (x: number) => Math.round(x * 10) / 10;
  if (totalToman && basketValue && basketValue > 0 && basketValue <= totalToman) {
    return { pct: round((pctOfBasket * basketValue) / totalToman), basis: 'capital' };
  }
  return { pct: round(pctOfBasket), basis: 'basket' };
}

/**
 * مقایسهٔ ترکیبِ فعلی با هدف — #106.
 * فعلی سه منبع دارد، به همین اولویت: (۱) ترکیبِ طبقاتِ سبد که بک‌اند از
 * «قیمت × تعداد» ساخته، (۲) ارزشِ دستیِ ثبت‌شدهٔ همان طبقه، (۳) هیچ‌کدام ⇒ null.
 * پیش از این هر طبقهٔ غیرسهامی صفرِ خالص می‌گرفت و «کسریِ کامل» اعلام می‌شد.
 * طبقاتی که چند ردیفِ هدف دارند (طلا) در سطحِ گروه سنجیده می‌شوند: عدد روی اولین
 * ردیف می‌نشیند و با جمعِ هدفِ اعضا مقایسه می‌گردد؛ بقیهٔ اعضا «بدون داده» می‌مانند.
 */
export function buildDelta(
  classes: TargetClass[],
  holdings: DeltaHolding[],
  inputs: DeltaInputs = {},
): DeltaRow[] {
  const { classMixPct = null, basketValueToman = null, totalToman = 0, valuesByClass = {} } = inputs;
  const hasMix = !!classMixPct && Object.keys(classMixPct).length > 0;

  // جمعِ طبقاتِ هم‌نام (gold و gold-cert هر دو طلای سبد را می‌شمارند)
  const byClass: Record<string, number> = {};
  if (hasMix) {
    for (const [k, v] of Object.entries(classMixPct as Record<string, number>)) {
      const cls = MIX_KEY_TO_CLASS[k];
      if (!cls) continue;
      byClass[cls] = Math.round(((byClass[cls] ?? 0) + v) * 10) / 10;
    }
  }
  // منبعِ جانشینِ طبقهٔ سهام: جمعِ وزنِ ردیف‌هایی که بک‌اند طبقاتشان را *نشناخته*
  // است (مثلاً سبدی که تعداد ندارد و ترکیبی نمی‌فرستد). ردیفی که طبقه‌اش معلوم
  // است دیگر در ترکیبِ طبقات شمرده شده؛ جمعش کردنِ دوباره‌اش همان وزن را دو بار
  // می‌کند — و اگر هیچِ آن‌ها سهام نباشد، «سهام ۰٪» هم صادقانه نیست: هیچ ردیفی
  // ادعای سهامی نداشته، پس «اندازه‌ای نداریم».
  const eqUnknownRows = holdings.filter((h) => {
    const ac = h.asset_class;
    if (!ac) return true;
    const mapped = MIX_KEY_TO_CLASS[rowClassKey(ac)];
    return mapped === 'equity';
  });
  const eqFromBasket =
    eqUnknownRows.length > 0
      ? Math.round(
          eqUnknownRows.reduce((s, h) => s + (typeof h.weight_eff_pct === 'number' ? h.weight_eff_pct : 0), 0) * 10,
        ) / 10
      : null;

  // گروه‌های هم‌alias: «طلا» دو ردیفِ هدف دارد (فیزیکی + گواهی) ولی تابلو یک
  // طبقه می‌دهد. مقایسه در سطحِ *گروه* انجام می‌شود و فقط ردیفِ حمل‌کننده (اولین
  // عضو) عدد می‌گیرد؛ بقیه null می‌مانند تا یک وزن دو بار شمرده نشود.
  const groups = new Map<string, TargetClass[]>();
  for (const c of classes) {
    const key = CLASS_ALIAS[c.id] ?? c.id;
    const arr = groups.get(key);
    if (arr) arr.push(c);
    else groups.set(key, [c]);
  }
  const r1 = (x: number) => Math.round(x * 10) / 10;

  return classes.map((c) => {
    const key = CLASS_ALIAS[c.id] ?? c.id;
    const members = groups.get(key) ?? [c];
    const multi = members.length > 1;
    const isCarrier = members[0].id === c.id;
    // هدفِ گروه = جمعِ هدفِ اعضا؛ هدفِ ردیفِ تنها = هدفِ خودش
    const goalPct = multi ? r1(members.reduce((s, m) => s + (m.pct > 0 ? m.pct : 0), 0)) : c.pct;
    const classLabel = multi ? members.map((m) => m.label).join(' + ') : undefined;
    const carrierLabel = members[0].label;

    let pct: number | null = null;
    let basis: DeltaBasis = null;
    let measure: DeltaMeasure = null;
    let reason: string | null = null;

    // اندازهٔ سطحِ طبقه: ترکیبِ سبدِ بک‌اند، وگرنه جانشینِ وزنِ سبد (فقط سهام)
    const fromMix = byClass[key] != null;
    const groupSrc = fromMix ? (byClass[key] as number) : key === 'equity' ? eqFromBasket : null;

    if (groupSrc != null) {
      if (isCarrier) {
        const scaled = toCapitalPct(groupSrc, basketValueToman, totalToman);
        pct = scaled.pct;
        basis = scaled.basis;
        measure = fromMix ? 'class_mix' : 'basket_weights';
        if (!fromMix) reason = 'وزنِ ردیف‌هایی که طبقه‌شان مشخص نیست؛ تعدادِ ردیف‌ها ثبت نشده است';
      } else {
        reason = `تابلو این را از «${carrierLabel}» جدا نمی‌کند؛ وزنِ طبقه در همان ردیف سنجیده می‌شود`;
      }
    } else if (totalToman > 0 && c.id in (valuesByClass ?? {}) && (valuesByClass[c.id] ?? 0) > 0) {
      // ارزشِ دستی به شناسهٔ خودِ طبقه بسته است، نه به alias: وگرنه طلای فیزیکی
      // و گواهیِ سپردهٔ طلا یک عدد را دو بار می‌شمرند.
      pct = Math.round(((valuesByClass[c.id] as number) / totalToman) * 1000) / 10;
      basis = 'capital';
      measure = 'asset_value';
    } else if (holdings.length === 0) {
      reason = 'سبد خالی است؛ دارایی‌ای برای سنجیدن وجود ندارد';
    } else if (hasMix) {
      reason = 'هیچِ نمادی از سبد به این طبقه نگاشت نشد';
    } else {
      reason = 'ردیف‌ها تعداد/قیمت ندارند یا ترکیبِ سبد ذخیره نشده است';
    }

    return {
      id: c.id,
      label: c.label,
      color: c.color,
      targetPct: c.pct,
      currentPct: pct,
      basis,
      delta: pct == null ? null : r1(pct - goalPct),
      reason,
      measure,
      ...(multi ? { classTargetPct: goalPct, classLabel } : {}),
    };
  });
}

/**
 * جملهٔ headline خلاصهٔ پرتفوی: «طلا و سکه ۴۳٪ از سرمایه — هدف ۴۵٪».
 * مخرج (سرمایه/سبد) در خودِ جمله می‌آید؛ بدونِ آن ۸۷٪ از سبد با ۴۵٪ از سرمایه
 * قابل مقایسه نیست. هدف هم هدفِ *طبقه* است (classTargetPct)، نه سطرِ تنها —
 * وگرنه ۸۷٪ طلا با ۳۰٪ «طلای فیزیکی» سنجیده می‌شد و مازادِ جعلی در می‌آمد.
 */
export function mixSentence(rows: DeltaRow[]): string | null {
  const known = rows.filter((r) => r.currentPct != null && Math.abs(r.delta ?? 0) > 0.05);
  if (known.length === 0) return null;
  const worst = known.reduce(
    (m, r) => (Math.abs(r.delta ?? 0) > Math.abs(m.delta ?? 0) ? r : m),
    known[0],
  );
  const basisLabel = worst.basis === 'capital' ? 'از سرمایه' : 'از سبد';
  const kind = (worst.delta ?? 0) > 0 ? 'مازاد' : 'کسری';
  return `${worst.label}: ${toFaDigits(worst.currentPct as number)}٪ ${basisLabel} — هدف ${toFaDigits(
    worst.classTargetPct ?? worst.targetPct,
  )}٪ (${kind} ${toFaDigits(Math.abs(worst.delta as number))}٪)`;
}
