// features/market/lib/tapeRowTone.ts -- رنگِ جهت وِ tooltipِ ردیف (یکِ مرجع، دوِ نما)
//
// ازِ `TapeTable.tsx` جدا شد تاِ کارتِ موبایل هم *همانِ* رنگِ صف/جهت وِ همانِ
// tooltip را بدهد. اگرِ دوِ نما دوِ تابعِ رنگِ جدا داشته باشند، «سبزِ صف خرید» درِ
// گوشی باِ دسکتاق فرق می‌کند وِ هیچِ آزمونِ واحدی آن را نمی‌گیرد.
import type { MarketRow } from '@shared/types/marketRow';
import { fmtPct, toFaDigits } from '@shared/lib/fmt';
import {
  STRONG_CLOCK_HINT,
  detectBoxExit,
  detectGoldenHour,
  detectStrongHour,
  detectSweep,
  lastCloseDiff,
} from './tapePatterns';
import { LIMIT_PCT } from '../stores/tapeStore';

/** رنگ ردیف از روی جهت و صف -- فقط رنگ متن، بدون بکس‌های درشت */
export function pctTone(pct: number | null | undefined): string {
  if (pct == null) return 'text-text-muted';
  if (pct >= LIMIT_PCT) return 'text-accent-green font-bold';
  if (pct > 0) return 'text-accent-green';
  if (pct <= -LIMIT_PCT) return 'text-accent-red font-bold';
  if (pct < 0) return 'text-accent-red';
  return 'text-text-secondary';
}

/** tooltip یکپارچهٔ ردیف: جزئیات عددی که از چشمِ بج‌ها برداشته شده */
export function rowTooltip(r: MarketRow): string {
  const bits: string[] = [];
  if (typeof r.vol_ratio === 'number' && Number.isFinite(r.vol_ratio)) {
    bits.push(`حجم ${toFaDigits(r.vol_ratio.toFixed(1))} برابر حجم ماهانه`);
  }
  const diff = lastCloseDiff(r);
  if (diff != null) bits.push(`اختلاف آخرین و پایانی ${fmtPct(diff * 100)}`);
  const active: string[] = [];
  if (detectStrongHour(r)) active.push(`ساعت قوی (${STRONG_CLOCK_HINT})`);
  else if (detectGoldenHour(r)) active.push('ساعت طلایی');
  else if (r.f_clock) active.push('الگوی ساعت');
  if (detectSweep(r)) active.push('کف‌روبی');
  if (detectBoxExit(r)) active.push('خروج از باکس');
  if (active.length) bits.push(`اعتبار الگو: ${active.join('، ')}`);
  return bits.join(' · ');
}
