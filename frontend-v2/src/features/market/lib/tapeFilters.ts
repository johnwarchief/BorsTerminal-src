import { isOn } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';

/** هفت فیلترِ جزوه — همان نام‌ها و همان پرچم‌های سرور */
export const TAPES = [
  { key: 'smart', label: 'پول هوشمند', flag: 'f_smart' },
  { key: 'legal', label: 'کد به کد', flag: 'f_legal' },
  { key: 'roobi', label: 'کف‌روبی', flag: 'f_roobi' },
  { key: 'susp', label: 'حجم مشکوک', flag: 'f_susp' },
  { key: 'clock', label: 'الگوی ساعت', flag: 'f_clock' },
  { key: 'noqteh', label: 'نقطه‌زنی', flag: 'f_noqteh' },
  { key: 'jet', label: 'جت', flag: 'f_jet' },
] as const;

export type TapeKey = (typeof TAPES)[number]['key'];
export type ScreenLogic = 'and' | 'or';

const BY_KEY = new Map(TAPES.map((t) => [t.key, t]));

export function tapeOn(row: MarketRow, key: TapeKey): boolean {
  const tape = BY_KEY.get(key);
  return tape ? isOn(row[tape.flag]) : false;
}

export function tapeCounts(rows: readonly MarketRow[]): Record<TapeKey, number> {
  const out = Object.fromEntries(TAPES.map((t) => [t.key, 0])) as Record<TapeKey, number>;
  for (const row of rows) {
    for (const tape of TAPES) if (isOn(row[tape.flag])) out[tape.key] += 1;
  }
  return out;
}

/** «اشتراک» = همهٔ چیپ‌های روشن لازم‌اند؛ «اجتماع» = کم‌از‌یکی کافی است. */
export function matchesTapes(row: MarketRow, active: readonly TapeKey[], logic: ScreenLogic): boolean {
  if (active.length === 0) return true;
  return logic === 'and' ? active.every((k) => tapeOn(row, k)) : active.some((k) => tapeOn(row, k));
}
