import type { KLineData } from 'klinecharts';

const DAY_MS = 86_400_000;

/**
 * TSETMC تاریخچهٔ درون‌روزی (۱/۵/۱۵/۶۰ دقیقه‌ای) منتشر نمی‌کند — نه در CDN و نه در
 * نهایت‌نگار. پس تنها سه بازه با دادهٔ واقعی وجود دارد و بقیه حذف شده‌اند تا
 * کندلِ روزانه زیرِ برچسبِ «ساعتی» سرو نشود.
 */
export const SUPPORTED_TIMEFRAMES = ['D', 'W', 'M'] as const;
export type Timeframe = (typeof SUPPORTED_TIMEFRAMES)[number];

export const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  D: 'روزانه',
  W: 'هفتگی',
  M: 'ماهانه',
};

export function timeframePeriod(tf: Timeframe): { span: number; type: 'day' | 'week' | 'month' } {
  return tf === 'W' ? { span: 1, type: 'week' } : tf === 'M' ? { span: 1, type: 'month' } : { span: 1, type: 'day' };
}

/** کلیدِ سطلِ تقویمی؛ هفته از شنبه (تعطیلات ایران) شروع می‌شود */
function bucketKey(ts: number, tf: Timeframe): number {
  const day = Math.floor(ts / DAY_MS);
  if (tf === 'W') return Math.floor((day - 2) / 7);
  const d = new Date(ts);
  return d.getUTCFullYear() * 12 + d.getUTCMonth();
}

/**
 * تجمیع کندل‌های روزانه به هفتگی/ماهانه.
 * open=نخستینِ سطل، close=آخرینِ سطل، high/low=بیشینه/کمینه، volume/turnover=جمع.
 * stamps روی آخرین کندلِ سطل می‌نشیند تا میلهٔ همیشه‌باز، روزِ آخرِ معاملاتی باشد.
 */
export function aggregateCandles(candles: KLineData[], tf: Timeframe): KLineData[] {
  if (tf === 'D' || candles.length === 0) return candles;

  // ترتیبِ صعودی پیش‌شرطِ پیمایشِ تک‌پاس است؛ ماژول باید مستقل از فراخوان هم درست باشد.
  const src = candles.every((c, i) => i === 0 || c.timestamp >= candles[i - 1].timestamp)
    ? candles
    : [...candles].sort((a, b) => a.timestamp - b.timestamp);

  const out: KLineData[] = [];
  let key = NaN;
  let bar: KLineData | null = null;

  const closeBar = () => { if (bar) out.push(bar); };

  for (const c of src) {
    const k = bucketKey(c.timestamp, tf);
    if (k !== key) {
      closeBar();
      key = k;
      bar = { ...c };
      continue;
    }
    if (!bar) continue;
    bar = {
      ...bar,
      timestamp: c.timestamp,
      high: Math.max(bar.high, c.high),
      low: Math.min(bar.low, c.low),
      close: c.close,
      // هیچ‌داده ≠ صفرِ معاملاتی: اگر هیچ دو میله‌ای حجم نداشت، میلهٔ تجمیعی هم
      // باید undefined بماند و در پنل حجم جای خالی نشان دهد.
      volume: bar.volume === undefined && c.volume === undefined
        ? undefined : (bar.volume ?? 0) + (c.volume ?? 0),
      turnover: bar.turnover === undefined && c.turnover === undefined
        ? undefined : (bar.turnover ?? 0) + (c.turnover ?? 0)
    };
  }
  closeBar();

  return out;
}
