import { changePct } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { classifyAssetType, type AssetType } from './assetType';

export interface Breadth {
  up: number; down: number; flat: number; unknown: number; total: number;
  upPct: number; downPct: number; flatPct: number;
}

/** پهنا: شمارشِ مثبت/منفی/بی‌تغییر روی همهٔ ردیف‌های همین پیلود — تعریف پنهان ندارد. */
export function breadthOf(rows: readonly MarketRow[]): Breadth {
  let up = 0; let down = 0; let flat = 0; let unknown = 0;
  for (const row of rows) {
    const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
    if (pct == null) { unknown += 1; continue; }
    if (pct > 0) up += 1;
    else if (pct < 0) down += 1;
    else flat += 1;
  }
  const known = up + down + flat;
  const pctOf = (n: number) => (known ? Math.round((n / known) * 100) : 0);
  return { up, down, flat, unknown, total: rows.length,
    upPct: pctOf(up), downPct: pctOf(down),
    flatPct: Math.max(0, 100 - pctOf(up) - pctOf(down)) };
}

export function boardSums(rows: readonly MarketRow[]): { value: number; volume: number } {
  let value = 0; let volume = 0;
  for (const row of rows) {
    if (row.q_tot_cap != null && Number.isFinite(row.q_tot_cap)) value += row.q_tot_cap;
    if (row.q_tot_tran != null && Number.isFinite(row.q_tot_tran)) volume += row.q_tot_tran;
  }
  return { value, volume };
}

const COMPOSITION_TYPES: AssetType[] = ['stock', 'payeh', 'right', 'energy', 'fund'];

export const TYPE_LABEL: Record<AssetType | 'other', string> = {
  stock: 'سهام',
  payeh: 'پایه',
  option: 'اختیار',
  fund: 'صندوق',
  bond: 'اوراق',
  right: 'حق تقدم',
  teseh: 'تسه',
  tal: 'TAL',
  ati: 'آتی',
  kala: 'کالا',
  energy: 'انرژی',
  other: 'سایر',
};

export function compositionOf(rows: readonly MarketRow[]): { type: AssetType | 'other'; count: number; value: number }[] {
  const counts = new Map<AssetType, { count: number; value: number }>();
  for (const row of rows) {
    const type = classifyAssetType(row);
    const slot = counts.get(type) ?? { count: 0, value: 0 };
    slot.count += 1;
    if (row.q_tot_cap != null && Number.isFinite(row.q_tot_cap)) slot.value += row.q_tot_cap;
    counts.set(type, slot);
  }
  const out = COMPOSITION_TYPES.map((type) => ({
    type: type as AssetType | 'other',
    count: counts.get(type)?.count ?? 0,
    value: counts.get(type)?.value ?? 0,
  }));
  let other = { count: 0, value: 0 };
  for (const [type, slot] of counts) {
    if (!COMPOSITION_TYPES.includes(type)) {
      other = { count: other.count + slot.count, value: other.value + slot.value };
    }
  }
  if (other.count > 0) out.push({ type: 'other', ...other });
  return out;
}
