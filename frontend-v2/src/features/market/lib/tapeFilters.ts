import { isOn } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';

/** هفت فیلترِ تابلوخوانیِ جزوه — همان کلیدهای سرور */
export const TAPES = [
  { key: 'f_smart', label: 'ورود پول هوشمند', short: 'پول هوشمند' },
  { key: 'f_legal', label: 'کد به کد حقوقی به حقیقی', short: 'کد به کد' },
  { key: 'f_roobi', label: 'کف‌روبی صف فروش', short: 'کف‌روبی' },
  { key: 'f_susp', label: 'حجم مشکوک', short: 'حجم مشکوک' },
  { key: 'f_clock', label: 'الگوی ساعت', short: 'الگوی ساعت' },
  { key: 'f_noqteh', label: 'نقطه‌زنی', short: 'نقطه‌زنی' },
  { key: 'f_jet', label: 'جت', short: 'جت' },
] as const;

export type TapeKey = (typeof TAPES)[number]['key'];

const LABEL: Record<TapeKey, string> = Object.fromEntries(
  TAPES.map((t) => [t.key, t.label]),
) as Record<TapeKey, string>;

export function tapeLabel(key: TapeKey): string {
  return LABEL[key];
}

export function rowTapes(row: MarketRow): TapeKey[] {
  return TAPES.filter((t) => isOn(row[t.key])).map((t) => t.key);
}

export function matchTape(row: MarketRow, key: TapeKey | null): boolean {
  return key == null || isOn(row[key]);
}

/** شمارش روی پایهٔ دیده‌شده (بعد از فیلترِ نوعِ دارایی) — مثلِ پروتوتایپ */
export function tapeCounts(rows: readonly MarketRow[]): Record<TapeKey, number> {
  const out = Object.fromEntries(TAPES.map((t) => [t.key, 0])) as Record<TapeKey, number>;
  for (const row of rows) {
    for (const tape of TAPES) if (isOn(row[tape.key])) out[tape.key] += 1;
  }
  return out;
}
