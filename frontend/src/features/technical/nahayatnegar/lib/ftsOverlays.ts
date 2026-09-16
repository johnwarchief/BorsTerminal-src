import type { KLineData } from 'klinecharts';

export interface FtsFiboZone {
  name: string;
  ratioStart: number;
  ratioEnd: number;
  priceStart: number;
  priceEnd: number;
  color: string;
}

export interface FtsSetupMarker {
  id: string;
  name: 'جت' | 'پولبک' | 'CHoCH' | 'نقطه‌زنی' | 'کف‌دوقلو';
  timestamp: number;
  price: number;
  type: 'buy' | 'sell' | 'warning';
  description: string;
}

export interface FtsAnalysisResult {
  logFiboZones: FtsFiboZone[];
  ma14: number | null;
  ma21Vol: number | null;
  ma52: number | null;
  ma100: number | null;
  rsi14Wilder: number | null;
  exitSignalMA14: boolean; // شرط خروج: کندل کامل زیر MA14 (high < ma14)
  setupMarkers: FtsSetupMarker[];
}

/**
 * محاسبه فیبوناچی لگاریتمی
 * در تحلیل تکنیکال بورس ایران، ترازهای فیبوناچی با فرمول لگاریتمی محاسبه می‌شوند:
 * P_target = P_low * exp(ratio * ln(P_high / P_low))
 */
export function calculateLogFiboPrice(low: number, high: number, ratio: number): number {
  if (low <= 0 || high <= 0 || high <= low) return low;
  const logRatio = Math.log(high / low);
  return Math.round(low * Math.exp(ratio * logRatio));
}

/**
 * میانگین متحرک ساده (SMA)
 */
export function calculateSMA(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) {
      sum -= values[i - period];
    }
    if (i >= period - 1) {
      result.push(sum / period);
    } else {
      result.push(null);
    }
  }
  return result;
}

/**
 * شاخص RSI بر اساس متد هموارسازی وایلدر (Wilder Smoothing)
 */
export function calculateWilderRsi(candles: KLineData[], period = 14): (number | null)[] {
  const result: (number | null)[] = [];
  if (candles.length <= period) {
    return candles.map(() => null);
  }

  let avgGain = 0;
  let avgLoss = 0;

  // مقدار اولیه
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    if (diff > 0) avgGain += diff;
    else avgLoss += Math.abs(diff);
  }

  avgGain /= period;
  avgLoss /= period;

  result.push(...Array(period).fill(null));
  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  result.push(100 - (100 / (1 + rs)));

  // هموارسازی وایلدر
  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push(100 - (100 / (1 + rs)));
  }

  return result;
}

/**
 * تحلیل کامل استراتژی FTS روی داده‌های کندل
 */
export function analyzeFts(candles: KLineData[]): FtsAnalysisResult {
  if (!candles || candles.length < 20) {
    return {
      logFiboZones: [],
      ma14: null,
      ma21Vol: null,
      ma52: null,
      ma100: null,
      rsi14Wilder: null,
      exitSignalMA14: false,
      setupMarkers: []
    };
  }

  const closes = candles.map(c => c.close);
  const volumes = candles.map(c => c.volume ?? 0);

  // ۱. میانگین‌ها
  const ma14Series = calculateSMA(closes, 14);
  const ma21VolSeries = calculateSMA(volumes, 21);
  const ma52Series = calculateSMA(closes, 52);
  const ma100Series = calculateSMA(closes, 100);
  const rsiSeries = calculateWilderRsi(candles, 14);

  const lastIdx = candles.length - 1;
  const lastCandle = candles[lastIdx];
  const lastMA14 = ma14Series[lastIdx];
  const lastMA21Vol = ma21VolSeries[lastIdx];
  const lastMA52 = ma52Series[lastIdx];
  const lastMA100 = ma100Series[lastIdx];
  const lastRSI = rsiSeries[lastIdx];

  // شرط خروج FTS: کندل کامل زیر MA14 (یعنی حتی بیشترین قیمت کندل زیر میانگین باشد)
  const exitSignalMA14 = lastMA14 !== null ? lastCandle.high < lastMA14 : false;

  // ۲. محاسبه زون‌های فیبوی لگاریتمی (بر مبنای سقف و کف دوره اخیر ۱۰۰ کندل)
  const lookback = Math.min(100, candles.length);
  const recentSlice = candles.slice(-lookback);
  let localMin = Infinity;
  let localMax = -Infinity;

  for (const c of recentSlice) {
    if (c.low < localMin) localMin = c.low;
    if (c.high > localMax) localMax = c.high;
  }

  const logFiboZones: FtsFiboZone[] = [
    {
      name: 'زون طلایی (۰.۳۳–۰.۴۰)',
      ratioStart: 0.33,
      ratioEnd: 0.40,
      priceStart: calculateLogFiboPrice(localMin, localMax, 0.33),
      priceEnd: calculateLogFiboPrice(localMin, localMax, 0.40),
      color: 'rgba(255, 171, 0, 0.22)'
    },
    {
      name: 'زون بازگشت ماژور (۰.۶۱۸–۰.۷۰)',
      ratioStart: 0.618,
      ratioEnd: 0.70,
      priceStart: calculateLogFiboPrice(localMin, localMax, 0.618),
      priceEnd: calculateLogFiboPrice(localMin, localMax, 0.70),
      color: 'rgba(41, 98, 255, 0.22)'
    },
    {
      name: 'تراز مبنا (۱.۰)',
      ratioStart: 1.0,
      ratioEnd: 1.0,
      priceStart: localMax,
      priceEnd: localMax,
      color: 'rgba(242, 54, 69, 0.4)'
    }
  ];

  // ۳. تشخیص مارکرهای ستاپ FTS
  const setupMarkers: FtsSetupMarker[] = [];

  for (let i = 20; i < candles.length; i++) {
    const c = candles[i];
    const prev = candles[i - 1];
    const ma14 = ma14Series[i];
    const ma21V = ma21VolSeries[i];
    const range = c.high - c.low;

    // ستاپ جت (Breakout پرقدرت با حجم بیش از ۲ برابر میانگین حجم)
    if (ma21V && c.volume && c.volume > 2 * ma21V && c.close > c.open && (c.close - c.low) > 0.8 * range) {
      setupMarkers.push({
        id: `jet_${c.timestamp}`,
        name: 'جت',
        timestamp: c.timestamp,
        price: c.high,
        type: 'buy',
        description: 'ستاپ جت FTS: شکست پرقدرت با حجم بیش از دو برابر میانگین'
      });
    }

    // ستاپ پولبک (برخورد ملایم با MA14 در روند صعودی با کاهش حجم)
    if (ma14 && prev.close > ma14 && c.low <= ma14 && c.close >= ma14 && c.volume && ma21V && c.volume < ma21V) {
      setupMarkers.push({
        id: `pullback_${c.timestamp}`,
        name: 'پولبک',
        timestamp: c.timestamp,
        price: c.low,
        type: 'buy',
        description: 'ستاپ پولبک FTS: بازآزمایی سطح میانگین ۱۴ با حجم کاهشی'
      });
    }

    // ستاپ CHoCH (تغییر ماهیت روند)
    if (i >= 5 && c.close > candles[i - 3].high && candles[i - 2].close < candles[i - 4].close) {
      setupMarkers.push({
        id: `choch_${c.timestamp}`,
        name: 'CHoCH',
        timestamp: c.timestamp,
        price: c.close,
        type: 'buy',
        description: 'تغییر ماهیت روند ساختاری (Change of Character)'
      });
    }

    // ستاپ نقطه‌زنی (واکنش دقیق به زون فیبوی لگاریتمی)
    const z1 = logFiboZones[0];
    if (c.low >= z1.priceStart && c.low <= z1.priceEnd && c.close > c.open) {
      setupMarkers.push({
        id: `sniper_${c.timestamp}`,
        name: 'نقطه‌زنی',
        timestamp: c.timestamp,
        price: c.low,
        type: 'buy',
        description: 'ستاپ نقطه‌زنی FTS: واکنش به زون فیبوی لگاریتمی ۰.۳۳-۰.۴۰'
      });
    }

    // ستاپ کف دوقلو
    if (i >= 15) {
      const prevLow = Math.min(...candles.slice(i - 12, i - 4).map(k => k.low));
      if (Math.abs(c.low - prevLow) / prevLow < 0.015 && c.close > c.open) {
        setupMarkers.push({
          id: `double_bottom_${c.timestamp}`,
          name: 'کف‌دوقلو',
          timestamp: c.timestamp,
          price: c.low,
          type: 'buy',
          description: 'الگوی کف دوقلو در محدوده حمایتی'
        });
      }
    }
  }

  return {
    logFiboZones,
    ma14: lastMA14 !== null ? Math.round(lastMA14) : null,
    ma21Vol: lastMA21Vol !== null ? Math.round(lastMA21Vol) : null,
    ma52: lastMA52 !== null ? Math.round(lastMA52) : null,
    ma100: lastMA100 !== null ? Math.round(lastMA100) : null,
    rsi14Wilder: lastRSI !== null ? Math.round(lastRSI * 10) / 10 : null,
    exitSignalMA14,
    setupMarkers: setupMarkers.slice(-15) // نگهداری ۱۵ مارکر اخیر برای حفظ کارایی
  };
}
