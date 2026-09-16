// features/fundamental/lib/exclusionFilter.ts -- فیلتر «حذف نمادهای ناقص/مردود بر اساس شاخص»
// کاربر در دراور تنظیمات، برای هر شاخص می‌تواند انتخاب کند که نمادهای مردود/ناقص آن شاخص
// از جدول غربالگری حذف شوند. تشخیص «مردود» از پرچم‌های خودِ ردیف (`i*_pass`) و تشخیص «ناقص»
// از نبودِ دادهٔ همان شاخص است؛ هرجا داده/پرچم نباشد صادقانه «نامعلوم» برمی‌گردانیم و
// هیچ ردیفی حذف نمی‌شود (Circuit Breaker).
//
// ماندگاری: کلید `exclude_rejected_indicators` به POST /api/fts/config هم فرستاده می‌شود
// (اگر بک‌اند روزی آن را به FTS_DEFAULTS اضافه کند، ماندگاری سمت سرور می‌شود)؛ تا آن زمان
// وضعیت در localStorage مرورگر نگه داشته می‌شود تا با reload پاک نشود.
import { useSyncExternalStore } from 'react';
import type { FtsScreenRow } from '../api/useFtsScreen';
import { EPS_REQUIRED_YEARS, epsHistory } from './epsHistory';

export type ExcludeAxis = '1a' | '1b' | '2' | '3' | '4' | '5';

/** ترتیب نمایش ردیف‌های تنظیمات */
export const EXCLUDE_AXES: readonly ExcludeAxis[] = ['1a', '1b', '2', '3', '4', '5'];

/** کلید کانفیگ (برای ماندگاری سمت سرور — باید به FTS_DEFAULTS بک‌اند اضافه شود) */
export const EXCLUDE_CONFIG_KEY = 'exclude_rejected_indicators';

const STORAGE_KEY = 'fts:exclude-rejected-axes';

export const EXCLUDE_LABEL: Record<ExcludeAxis, string> = {
  '1a': 'رشد ریالی (شاخص ۱الف)',
  '1b': 'رشد مقداری / تناژ فیزیکی (شاخص ۱ب)',
  '2': 'سابقهٔ سه‌سالهٔ EPS (شاخص ۲)',
  '3': 'حاشیهٔ ناخالص (شاخص ۳)',
  '4': 'نسبت فروش / ارزش بازار (شاخص ۴)',
  '5': 'دروازهٔ صنعت (شاخص ۵)',
};

/** شاخص‌هایی که ردیفِ غربالگری برای تشخیصشان داده/پرچم ندارد — همان‌جا صادقانه می‌گوییم */
export const NO_ROW_FLAG: Partial<Record<ExcludeAxis, string>> = {
  '1b':
    'پاسخ غربالگری ستون تناژ فیزیکی ندارد؛ این گزینه فقط در کارت نماد و برای شرکت‌های تولیدی معنا دارد، پس هیچ ردیفی از جدول حذف نمی‌شود.',
};

function isAxis(v: unknown): v is ExcludeAxis {
  return typeof v === 'string' && (EXCLUDE_AXES as readonly string[]).includes(v);
}

function normalize(list: readonly unknown[] | null | undefined): ExcludeAxis[] {
  if (!Array.isArray(list)) return [];
  return EXCLUDE_AXES.filter((a) => list.some((x) => isAxis(x) && x === a));
}

function readStorage(): ExcludeAxis[] {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return normalize(JSON.parse(raw) as unknown[]);
  } catch {
    return [];
  }
}

let state: ExcludeAxis[] = readStorage();
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

/** وضعیت فعلی (سنپ از localStorage) */
export function getExcludeAxes(): ExcludeAxis[] {
  return state;
}

export function setExcludeAxes(next: readonly ExcludeAxis[]) {
  const norm = normalize(next);
  const same = norm.length === state.length && norm.every((a, i) => a === state[i]);
  state = norm;
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* حافظهٔ مرورگر در دسترس نیست — وضعیت فقط در همان نشست می‌ماند */
  }
  if (!same) emit();
}

export function toggleExcludeAxis(axis: ExcludeAxis) {
  setExcludeAxes(state.includes(axis) ? state.filter((a) => a !== axis) : [...state, axis]);
}

export function resetExcludeAxes() {
  setExcludeAxes([]);
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** هوک اشتراک — جدول و دراور هر دو از همین منبع می‌خوانند */
export function useExcludeAxes(): ExcludeAxis[] {
  return useSyncExternalStore(subscribe, getExcludeAxes, getExcludeAxes);
}

/**
 * آیا این ردیف برای شاخص داده‌شده «مردود یا ناقص» است؟
 * true = حذف شود · false = سالم · null = پرچم/داده نداریم (صادقانه: حذف نمی‌شود)
 */
export function rejectedFor(row: FtsScreenRow, axis: ExcludeAxis): boolean | null {
  switch (axis) {
    case '1a':
      if (row.i1_pass === false) return true;
      if (row.i1_pass == null && row.rev_growth == null) return true;
      return row.i1_pass === true ? false : null;
    case '1b':
      // ستون تناژ در پاسخ غربالگری وجود ندارد ⇒ تشخیص ممکن نیست
      return null;
    case '2': {
      const hist = epsHistory(
        row.eps_series,
        row.eps_years_required ?? EPS_REQUIRED_YEARS,
        row.eps_years_available,
      );
      if (hist.state !== 'complete') return true;
      if (row.i2_pass === false) return true;
      return row.i2_pass === true ? false : null;
    }
    case '3':
      if (row.i3_pass === false) return true;
      if (row.i3_pass == null && row.gross_margin == null) return true;
      return row.i3_pass === true ? false : null;
    case '4':
      if (row.i4_pass === false) return true;
      if (row.i4_pass == null && row.profit_potential_pct == null && row.sales_to_mcap == null) return true;
      return row.i4_pass === true ? false : null;
    case '5':
      if (row.i5_pass === false) return true;
      if (row.pricing_mode == null) return true;
      return row.i5_pass === true ? false : null;
    default:
      return null;
  }
}

/** اعمال فیلتر: ردیف‌های باقی‌مانده + شمار حذف‌شده‌ها */
export function applyExcludeFilter(
  rows: readonly FtsScreenRow[],
  axes: readonly ExcludeAxis[],
): { rows: FtsScreenRow[]; hidden: number } {
  const active = axes.filter((a) => EXCLUDE_AXES.includes(a) && !NO_ROW_FLAG[a]);
  if (active.length === 0) return { rows: [...rows], hidden: 0 };
  const kept = rows.filter((r) => !active.some((a) => rejectedFor(r, a) === true));
  return { rows: kept, hidden: rows.length - kept.length };
}
