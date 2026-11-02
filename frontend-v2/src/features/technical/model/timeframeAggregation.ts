/**
 * frontend-v2/src/features/technical/model/timeframeAggregation.ts
 *
 * موتور تجمیع زمانی کندل‌ها بر پایه تقویم کاری بورس تهران (TSE):
 * - روزانه (1D): کندل‌های خام بدون تغییر
 * - هفتگی (1W): تجمیع شنبه تا چهارشنبه در قالب یک کندل هفتگی واحد
 * - ماهانه (1M): تجمیع ماه‌های شمسی تقویم جلالی (فروردین تا اسفند)
 */

import type { KLineData } from 'klinecharts';

export type TimeframeId = '1D' | '1W' | '1M';

export interface TimeframeOption {
  id: TimeframeId;
  labelFa: string;
  tooltipFa: string;
}

export const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { id: '1D', labelFa: 'روزانه', tooltipFa: 'تایم‌فریم روزانه (جلسات معاملاتی بورس تهران)' },
  { id: '1W', labelFa: 'هفتگی', tooltipFa: 'تایم‌فریم هفتگی (شنبه تا چهارشنبه)' },
  { id: '1M', labelFa: 'ماهانه', tooltipFa: 'تایم‌فریم ماهانه (ماه‌های خورشیدی تقویم جلالی)' },
];

/**
 * کلید یکتای هفته معاملاتی بورس تهران (شنبه تا چهارشنبه)
 * شنبه روز اول هفته کاری در تقویم ایران است.
 */
export function getTseWeekKey(timestamp: number): string {
  const d = new Date(timestamp);
  // getUTCDay: 0=یکشنبه, 1=دوشنبه, 2=سه‌شنبه, 3=چهارشنبه, 4=پنج‌شنبه, 5=جمعه, 6=شنبه
  const day = d.getUTCDay();
  // فاصله روزها از شنبه:
  // شنبه (6) -> 0
  // یکشنبه (0) -> 1
  // دوشنبه (1) -> 2
  // سه‌شنبه (2) -> 3
  // چهارشنبه (3) -> 4
  // پنج‌شنبه (4) -> 5
  // جمعه (5) -> 6
  const daysSinceSaturday = (day + 1) % 7;
  const satMs = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - daysSinceSaturday * 86_400_000;
  const satDate = new Date(satMs);
  return `${satDate.getUTCFullYear()}-${satDate.getUTCMonth() + 1}-${satDate.getUTCDate()}`;
}

/**
 * کلید ماه شمسی تقویم جلالی (سال و ماه خورشیدی)
 */
export function getJalaliMonthKey(timestamp: number): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      timeZone: 'UTC',
    });
    const parts = formatter.formatToParts(new Date(timestamp));
    const year = parts.find((p) => p.type === 'year')?.value ?? '';
    const month = parts.find((p) => p.type === 'month')?.value ?? '';
    return `${year}-${month}`;
  } catch {
    const d = new Date(timestamp);
    return `${d.getUTCFullYear()}-${d.getUTCMonth() + 1}`;
  }
}

/**
 * تجمیع داده‌های کندلی بر اساس تایم‌فریم انتخابی
 */
export function aggregateCandles(candles: KLineData[], timeframe: string): KLineData[] {
  if (!candles || candles.length === 0) return [];
  if (timeframe === '1D') {
    return candles;
  }

  const groups = new Map<string, KLineData[]>();

  for (const c of candles) {
    const key = timeframe === '1W' ? getTseWeekKey(c.timestamp) : getJalaliMonthKey(c.timestamp);
    let list = groups.get(key);
    if (!list) {
      list = [];
      groups.set(key, list);
    }
    list.push(c);
  }

  const result: KLineData[] = [];

  for (const list of groups.values()) {
    if (list.length === 0) continue;
    // مرتب‌سازی زمانی درون گروه
    list.sort((a, b) => a.timestamp - b.timestamp);

    const first = list[0];
    const last = list[list.length - 1];

    let high = -Infinity;
    let low = Infinity;
    let volume = 0;

    for (const item of list) {
      if (item.high > high) high = item.high;
      if (item.low < low) low = item.low;
      volume += item.volume ?? 0;
    }

    result.push({
      timestamp: last.timestamp,
      open: first.open,
      high,
      low,
      close: last.close,
      volume,
    });
  }

  return result.sort((a, b) => a.timestamp - b.timestamp);
}
