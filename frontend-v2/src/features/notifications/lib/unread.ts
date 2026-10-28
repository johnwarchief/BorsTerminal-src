export type Level = 'high' | 'medium' | 'low' | 'unclassified';

export const LEVEL_LABEL: Record<Level, string> = {
  high: 'بالا',
  medium: 'متوسط',
  low: 'پایین',
  unclassified: 'بی‌طبقه',
};

export const LEVEL_ORDER: Level[] = ['high', 'medium', 'low', 'unclassified'];

export interface Notice {
  id?: string | number | null;
  level: Level;
  title: string;
  symbol?: string | null;
  company?: string | null;
  publish_date?: string | null;
  url?: string | null;
  kind?: string | null;
  occurrences?: number | null;
}

export function unreadCount(items: readonly Notice[], readIds: ReadonlySet<string>): number {
  let count = 0;
  for (const item of items) {
    if (item.level !== 'high' && item.level !== 'medium') continue;
    if (item.id != null && readIds.has(String(item.id))) continue;
    count += 1;
  }
  return count;
}

const KEY = 'bors-notif-read-v1';

export function readState(): Set<string> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    const list = Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
    return new Set<string>(list);
  } catch {
    return new Set();
  }
}

export function markRead(id: string): void {
  const next = readState();
  next.add(id);
  try { localStorage.setItem(KEY, JSON.stringify([...next])); } catch { /* ذخیره‌نشدن خواندن را نمی‌شکند */ }
  window.dispatchEvent(new Event('bors:notif-read'));
}
