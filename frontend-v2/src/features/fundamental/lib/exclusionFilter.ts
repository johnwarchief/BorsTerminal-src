import { useSyncExternalStore } from 'react';

export type ExcludeAxis = '1a' | '1b' | '2' | '3' | '4' | '5';

export const EXCLUDE_AXES: readonly ExcludeAxis[] = ['1a', '1b', '2', '3', '4', '5'];

export const EXCLUDE_LABEL: Record<ExcludeAxis, string> = {
  '1a': 'رشد ریالی (شاخص ۱الف)',
  '1b': 'رشد تولیدی (شاخص ۱ب)',
  '2': 'سابقهٔ سه‌سالهٔ EPS (شاخص ۲)',
  '3': 'حاشیهٔ ناخالص (شاخص ۳)',
  '4': 'فروش / ارزش بازار (شاخص ۴)',
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
