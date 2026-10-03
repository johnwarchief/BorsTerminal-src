// features/technical/lib/resample.ts -- بازنمونه‌گیری کندل روزانه به هفتگی/ماهانه (کلاینت)
// خالص و مستقل از DOM. کلید گروه هفتگی = **شنبهٔ** همان هفته (UTC)؛ ماهانه = YYYY-MM.
// open=اولین، close=آخرین، high/low=بیشینه/کمینه، volume=جمع؛ timestamp=آخرین کندل گروه.
// شنبه، نه دوشنبه: نشستِ ایران شنبه تا چهارشنبه است و همین تقویم درِ همۀ اپ یکی
// است — `api/chart.py::_fts_resample` و `nahayatnegar/lib/timeframe.ts`. با کلیدِ
// دوشنبه، سطلِ هفتگیِ این مسیر با سطلِ چارتِ زنده نمی‌خواند.
import type { KLineData } from '../../../vendor/klinecharts';

export type ResamplePeriod = 'day' | 'week' | 'month';

const DAY_MS = 86_400_000;

function groupKey(ts: number, period: ResamplePeriod): string {
  const d = new Date(ts);
  if (period === 'month') return d.toISOString().slice(0, 7);
  if (period === 'week') {
    // getUTCDay: یکشنبه=۰ … شنبه=۶ ⇒ فاصله تا شنبۀ همان هفته
    const dow = (d.getUTCDay() + 1) % 7;
    const saturday = ts - dow * DAY_MS;
    return new Date(saturday).toISOString().slice(0, 10);
  }
  return d.toISOString().slice(0, 10);
}

/** بازنمونه‌گیری صعودی‌محور؛ ورودی ناصعودی هم پذیرفته می‌شود (اول مرتب می‌شود) */
export function resample(candles: KLineData[], period: ResamplePeriod): KLineData[] {
  if (period === 'day') return [...candles];
  const sorted = [...candles].sort((a, b) => a.timestamp - b.timestamp);
  const out: KLineData[] = [];
  let key: string | null = null;
  let cur: KLineData | null = null;
  for (const c of sorted) {
    const k = groupKey(c.timestamp, period);
    if (cur == null || k !== key) {
      if (cur) out.push(cur);
      key = k;
      cur = { timestamp: c.timestamp, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume ?? 0 };
    } else {
      cur.high = Math.max(cur.high, c.high);
      cur.low = Math.min(cur.low, c.low);
      cur.close = c.close;
      cur.timestamp = c.timestamp;
      cur.volume = (cur.volume ?? 0) + (c.volume ?? 0);
    }
  }
  if (cur) out.push(cur);
  return out;
}
