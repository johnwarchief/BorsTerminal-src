import { useSyncExternalStore } from 'react';
import type { ScreenerCoreRow } from '../api/useScreenerCore';

export type ExcludeAxis = '1a' | '1b' | '2' | '3' | '4' | '5';

export const EXCLUDE_AXES: readonly ExcludeAxis[] = ['1a', '1b', '2', '3', '4', '5'];

export const EXCLUDE_LABEL: Record<ExcludeAxis, string> = {
  '1a': 'رشد ریالی (شاخص ۱الف)',
  '1b': 'رشد تولیدی (شاخص ۱ب)',
  '2': 'سابقهٔ سه‌سالهٔ EPS (شاخص ۲)',
  '3': 'حاشیه سود ناخالص (شاخص ۳)',
  '4': 'پتانسیل سود (شاخص ۴)',
  '5': 'دروازهٔ صنعت (شاخص ۵)',
};

export const NO_ROW_FLAG: Partial<Record<ExcludeAxis, string>> = {
  '1b': 'پاسخ غربالگری ستون تناژ فیزیکی ندارد؛ این گزینه هیچ ردیفی را حذف نمی‌کند.',
};

const STORAGE_KEY = 'fts:exclude-rejected-axes';

function isAxis(value: unknown): value is ExcludeAxis {
  return typeof value === 'string' && (EXCLUDE_AXES as readonly string[]).includes(value);
}

function normalize(list: readonly unknown[] | null | undefined): ExcludeAxis[] {
  if (!Array.isArray(list)) return [];
  return EXCLUDE_AXES.filter((axis) => list.some((item) => isAxis(item) && item === axis));
}

function readStorage(): ExcludeAxis[] {
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    return raw ? normalize(JSON.parse(raw) as unknown[]) : [];
  } catch {
    return [];
  }
}

let state: ExcludeAxis[] = readStorage();
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

export function getExcludeAxes(): ExcludeAxis[] {
  return state;
}

export function setExcludeAxes(next: readonly ExcludeAxis[]) {
  const normalized = normalize(next);
  const same = normalized.length === state.length && normalized.every((axis, index) => axis === state[index]);
  state = normalized;
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* فقط همان نشست */
  }
  if (!same) emit();
}

export function toggleExcludeAxis(axis: ExcludeAxis) {
  setExcludeAxes(state.includes(axis) ? state.filter((item) => item !== axis) : [...state, axis]);
}

export function resetExcludeAxes() {
  setExcludeAxes([]);
}

function subscribe(callback: () => void) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function useExcludeAxes(): ExcludeAxis[] {
  return useSyncExternalStore(subscribe, getExcludeAxes, getExcludeAxes);
}

export function rejectedFor(row: ScreenerCoreRow, axis: ExcludeAxis): boolean | null {
  switch (axis) {
    case '1a':
      if (row.i1_pass === false) return true;
      if (row.i1_pass == null && row.rev_growth == null) return true;
      return row.i1_pass === true ? false : null;
    case '1b':
      return null;
    case '2': {
      if (row.i2_na === true) return null;
      if (row.i2_pass === false) return true;
      if (row.i2_pass === true) return false;
      const series = Array.isArray(row.eps_series) ? row.eps_series : [];
      const real = series.filter((value) => typeof value === 'number' && Number.isFinite(value)).length;
      const required = row.eps_years_required ?? 3;
      const available = Math.max(real, Math.min(Math.max(0, Math.trunc(row.eps_years_available ?? 0)), required));
      return available < required ? true : null;
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

export function applyExcludeFilter(rows: readonly ScreenerCoreRow[], axes: readonly ExcludeAxis[]) {
  const active = axes.filter((axis) => EXCLUDE_AXES.includes(axis) && !NO_ROW_FLAG[axis]);
  if (active.length === 0) return { rows: [...rows], hidden: 0 };
  const kept = rows.filter((row) => !active.some((axis) => rejectedFor(row, axis) === true));
  return { rows: kept, hidden: rows.length - kept.length };
}
