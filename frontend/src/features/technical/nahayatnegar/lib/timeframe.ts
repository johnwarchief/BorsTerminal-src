import type { KLineData } from 'klinecharts';
import { epochToJalali } from '../../lib/jalaliDate';

const DAY_MS = 86_400_000;

/**
 * TSETMC تاریخچۀ درون‌روزی (یک و پنج و پانزده و سی دقیقه‌ای و ساعتی) منتشر نمی‌کند —
 * نه در CDN و نه در نهایت‌نگار. پس تنها سه بازه با دادهٔ واقعی وجود دارد و بقیه
 * حذف شده‌اند تا کندلِ روزانه زیرِ برچسبِ «ساعتی» سرو نشود.
 */
export const SUPPORTED_TIMEFRAMES = ['D', 'W', 'M'] as const;
export type Timeframe = (typeof SUPPORTED_TIMEFRAMES)[number];

/**
 * capabilityِ صریحِ «منبع»، جدا از توانِ رندرِ کتابخانه. کاوشِ زندۀ ۱۴۰۵-۰۷-۱۲
 * (`_audit/probe_intraday_sources.py`) نُه خانوادۀ نآزمودۀ `cdn.tsetmc.com/api`
 * (Trades/Chart/History/StaticData/MarketData) را زد و هیچ‌کدام داده نداد: یا ۴۰۴
 * یا همان صفحۀ ضدربات. با ده مسیرِ دورِ پیش (LIVE_HOT_STATE.md §۸) جمعاً نوزده
 * مسیرِ آزموده‌شدۀ مرده — پس کندلِ درون‌روزه برایِ هیچ نمادی قابلِ ساخت نیست و
 * «کندلِ باز» فقط برایِ جلسۀ جاری و فقط از تابلویِ زنده معنا دارد.
 */
export const UNSUPPORTED_TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h'] as const;

export const INTRADAY_CAPABILITY = {
  supported: false,
  /** دلیلِ کامل — جایِ آن tooltip و مستند است، نه متنِ دیدنی */
  reason: 'منبعِ درون‌روزیِ نماد در TSETMC منتشر نمی‌شود (نوزده مسیرِ آزموده‌شده مرده‌اند).',
  fallback: 'D' as Timeframe,
};

export function isSupportedTimeframe(tf: unknown): tf is Timeframe {
  return typeof tf === 'string' && (SUPPORTED_TIMEFRAMES as readonly string[]).includes(tf);
}

/**
 * درخواستِ بازه‌ای که منبعِ داده ندارد باید صریح به روزانه تنزل کند و دلیلش را
 * بگوید — سکوتِ بی‌نشانه یعنی کاربر فکر می‌کند چارت خراب است.
 */
export function resolveTimeframe(req: unknown): { timeframe: Timeframe; degraded: string | null } {
  if (isSupportedTimeframe(req)) return { timeframe: req, degraded: null };
  if (typeof req === 'string' && (UNSUPPORTED_TIMEFRAMES as readonly string[]).includes(req)) {
    return {
      timeframe: INTRADAY_CAPABILITY.fallback,
      degraded: `بازۀ «${req}» منبعِ داده ندارد؛ نمای روزانه رسم می‌شود.`,
    };
  }
  const label = typeof req === 'string' && req.length > 0 && req.length <= 8 ? req : 'ناشناخته';
  return {
    timeframe: INTRADAY_CAPABILITY.fallback,
    degraded: `بازۀ «${label}» درِ این برنامه داده ندارد؛ نمای روزانه رسم می‌شود.`,
  };
}


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

/** کلیدهایِ نوارِ «بازه زمانی» پایینِ چارت، به همان ترتیبی که دکمه‌ها می‌نشینند */
export const VIEW_RANGES = ['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'All'] as const;

const RANGE_DAYS: Record<string, number> = {
  '1D': 1, '5D': 5, '1M': 31, '3M': 92, '6M': 183, '1Y': 365, '5Y': 1826,
};

/**
 * دکمه‌های «بازه زمانی» باید واقعاً زوم کنند: چند کندلِ آخر در دید بماند.
 * مبنایِ شمار تقویمِ میلادیِ همان کندل‌هاست و YTD سالِ جلالیِ آخرین کندل.
 * حداقلِ ۵ کندل: سریِ ما روزانه است و «۱ روز» رویِ چارتِ تک‌کندل شبیه خرابی
 * به‌نظر می‌رسد، نه یک نمادِ بزرگ‌نمایی.
 */
export function rangeVisibleBars(rng: string, candles: readonly { timestamp: number }[]): number {
  const n = candles.length;
  if (n === 0) return 0;
  if (rng === 'All' || (rng !== 'YTD' && !RANGE_DAYS[rng])) return n;
  const last = candles[n - 1].timestamp;
  let count: number;
  if (rng === 'YTD') {
    const year = epochToJalali(last).slice(0, 4);
    count = candles.filter((c) => epochToJalali(c.timestamp).slice(0, 4) === year).length;
  } else {
    const cutoff = last - RANGE_DAYS[rng] * DAY_MS;
    count = candles.filter((c) => c.timestamp >= cutoff).length;
  }
  return Math.min(n, Math.max(Math.min(5, n), count));
}
