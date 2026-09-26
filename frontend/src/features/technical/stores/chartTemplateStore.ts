// features/technical/stores/chartTemplateStore.ts -- قالب‌هایِ چارت (مطالعات + نمایش)
// هر قالب مجموعه‌ای از نام‌هایِ مطالعه و چند تنظیمِ نمایش است؛ پارامترهایِ هر
// مطالعه همان پیش‌فرضِ ثبت‌شدۀ خودش می‌ماند (رأیِ مالک: عددِ ساختگی نه).
// الگویِ ذخیره: دستی روی localStorage، مثلِ ftsConfigStore.
import { create } from 'zustand';

export type ChartTemplate = {
  id: string;
  name: string;
  /** نام‌هایِ ثبت‌شدۀ klinecharts که باید روشن باشند */
  indicators: string[];
  timeframe?: string;
  candleType?: string;
  adjustment?: string;
  priceScale?: string;
  createdAt: number;
};

const STORAGE_KEY = ['fts', 'chart', 'templates', 'v1'].join('.');

function newId(): string {
  return `tp_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function strList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const out: string[] = [];
  for (const v of raw) if (typeof v === 'string' && v.trim()) out.push(v.trim());
  return out;
}

function optStr(raw: unknown): string | undefined {
  return typeof raw === 'string' && raw.trim() ? raw.trim() : undefined;
}

/** قالبِ خراب یا بی‌نام بارگذاری نمی‌شود؛ هیچ رشته‌ای از بانک به چارت نمی‌رود */
function saneTemplate(raw: unknown): ChartTemplate | null {
  if (!raw || typeof raw !== 'object') return null;
  const t = raw as Record<string, unknown>;
  const name = optStr(t.name);
  if (!name) return null;
  const indicators = strList(t.indicators);
  return {
    id: optStr(t.id) ?? newId(),
    name,
    indicators,
    timeframe: optStr(t.timeframe),
    candleType: optStr(t.candleType),
    adjustment: optStr(t.adjustment),
    priceScale: optStr(t.priceScale),
    createdAt: typeof t.createdAt === 'number' && Number.isFinite(t.createdAt) ? t.createdAt : Date.now(),
  };
}

function load(): ChartTemplate[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    const list = Array.isArray(parsed) ? parsed : (parsed as { templates?: unknown[] }).templates ?? [];
    const out: ChartTemplate[] = [];
    for (const item of Array.isArray(list) ? list : []) {
      const t = saneTemplate(item);
      if (t) out.push(t);
    }
    return out;
  } catch {
    return [];
  }
}

function persist(templates: ChartTemplate[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ templates }));
  } catch {
    // دیسکِ پُر یا حالتِ خصوصی: فقط در حافظهٔ داخلِ برنامه می‌ماند
  }
}

export type NewTemplate = Omit<ChartTemplate, 'id' | 'createdAt'>;

type ChartTemplateState = {
  templates: ChartTemplate[];
  /** نامِ تکراری رویِ قالبِ قبلی می‌نشیند (بازنویسی، نه ردیفِ دوم) */
  saveTemplate: (input: NewTemplate) => ChartTemplate | null;
  removeTemplate: (id: string) => void;
  renameTemplate: (id: string, name: string) => void;
  clearAll: () => void;
};

export const useChartTemplateStore = create<ChartTemplateState>((set, get) => {
  const commit = (next: ChartTemplate[]) => {
    persist(next);
    set({ templates: next });
  };
  return {
    templates: load(),
    saveTemplate: (input) => {
      const name = typeof input.name === 'string' ? input.name.trim() : '';
      if (!name) return null;
      const indicators = strList(input.indicators);
      const built: ChartTemplate = {
        id: newId(),
        name,
        indicators,
        timeframe: optStr(input.timeframe),
        candleType: optStr(input.candleType),
        adjustment: optStr(input.adjustment),
        priceScale: optStr(input.priceScale),
        createdAt: Date.now(),
      };
      const rest = get().templates.filter((t) => t.name !== name);
      commit([built, ...rest]);
      return built;
    },
    removeTemplate: (id) => commit(get().templates.filter((t) => t.id !== id)),
    renameTemplate: (id, name) => {
      const clean = name.trim();
      if (!clean) return;
      commit(get().templates.map((t) => (t.id === id ? { ...t, name: clean } : t)));
    },
    clearAll: () => commit([]),
  };
});

export { STORAGE_KEY as CHART_TEMPLATE_KEY };
