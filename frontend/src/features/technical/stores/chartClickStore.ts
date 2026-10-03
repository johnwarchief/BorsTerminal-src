// features/technical/stores/chartClickStore.ts -- لاگِ کلیکِ چارت، محلی و پایدار
// نماد/بازه/میله/نتیجهٔ موتور درِ هر ردیف ثابت می‌ماند (کلیدِ پایدارِ ردیف
// `symbol|timeframe|barTs` است — timestampِ میله، نه رشتهٔ تاریخِ دیدنی)، پس یک میله دو بار ردیفِ دوم نمی‌گیرد — فقط
// زمانِ کلیکِ تازه‌تر. سقفِ ۵۰ ردیف: لاگِ بی‌سقف درِ نشستِ طولانی دیسک را
// پر می‌کند و چیزی به کاربر برنمی‌گرداند.
import { create } from 'zustand';

import type { ChartBarClick } from '../nahayatnegar/lib/barClicks';

const STORAGE_KEY = ['fts', 'chart', 'click-log', 'v1'].join('.');
export const CLICK_LOG_CAP = 50;

function saneClick(raw: unknown): ChartBarClick | null {
  if (!raw || typeof raw !== 'object') return null;
  const e = raw as Record<string, unknown>;
  if (typeof e.symbol !== 'string' || !e.symbol.trim()) return null;
  if (e.timeframe !== 'D' && e.timeframe !== 'W' && e.timeframe !== 'M') return null;
  if (typeof e.barTs !== 'number' || !Number.isFinite(e.barTs) || e.barTs <= 0) return null;
  if (typeof e.barDate !== 'string' || !/^\d{4}\/\d{2}\/\d{2}$/.test(e.barDate)) return null;
  if (e.kind !== 'candle' && e.kind !== 'marker') return null;
  if (typeof e.close !== 'number' || !Number.isFinite(e.close)) return null;
  const setupsRaw = Array.isArray(e.engineSetups) ? e.engineSetups : [];
  const engineSetups = setupsRaw
    .filter((s) => s && typeof s === 'object' && typeof (s as { label?: unknown }).label === 'string')
    .map((s) => {
      const o = s as { kind?: unknown; label: string; price?: unknown };
      return {
        kind: typeof o.kind === 'string' ? o.kind : '',
        label: o.label,
        price: typeof o.price === 'number' && Number.isFinite(o.price) ? o.price : 0,
      };
    });
  return {
    key: typeof e.key === 'string' && e.key ? e.key : `${e.symbol}|${e.timeframe}|${e.barTs}`,
    symbol: e.symbol.trim(),
    timeframe: e.timeframe,
    barTs: e.barTs,
    barDate: e.barDate,
    kind: e.kind,
    marker: typeof e.marker === 'string' ? e.marker : null,
    engineSetups,
    adjustRatio: typeof e.adjustRatio === 'number' && Number.isFinite(e.adjustRatio) ? e.adjustRatio : null,
    close: e.close,
    atMs: typeof e.atMs === 'number' && Number.isFinite(e.atMs) ? e.atMs : Date.now(),
  };
}

export function loadClicks(): ChartBarClick[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    const list = Array.isArray(parsed) ? parsed : (parsed as { clicks?: unknown[] })?.clicks ?? [];
    const out: ChartBarClick[] = [];
    for (const item of Array.isArray(list) ? list : []) {
      const e = saneClick(item);
      if (e) out.push(e);
    }
    return out.slice(0, CLICK_LOG_CAP);
  } catch {
    return [];
  }
}

function persist(clicks: ChartBarClick[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ clicks }));
  } catch {
    // حالتِ خصوصیِ مرورگر/دیسکِ پُر: حافظۀ داخلی کار می‌کند، خطا بیرون نمی‌زند
  }
}

type ChartClickState = {
  /** تازه‌ترین در خانۀ صفر؛ مصرف‌کننده خودش با `find` نماد/بازه را انتخاب می‌کند */
  clicks: ChartBarClick[];
  /** افزودن: ردیفِ همسان (همان نماد/بازه/میله) جابه‌جا می‌شود، تکثیر نمی‌شود */
  log: (e: ChartBarClick) => void;
  clear: () => void;
};

function commit(set: (partial: { clicks: ChartBarClick[] }) => void, next: ChartBarClick[]): void {
  persist(next);
  set({ clicks: next });
}

export const useChartClickStore = create<ChartClickState>((set, get) => ({
  clicks: loadClicks(),
  log: (e) => {
    const rest = get().clicks.filter((c) => c.key !== e.key);
    commit(set, [e, ...rest].slice(0, CLICK_LOG_CAP));
  },
  clear: () => commit(set, []),
}));
