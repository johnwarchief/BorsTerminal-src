/**
 * frontend-v2/src/features/technical/model/candleEdgeScanner.ts
 *
 * اسکنر پرایس‌اکشن، تشخیص الگوهای کندل‌استیک و محاسبه لبه آماری (CandleEdge):
 * پورت مستقیم محاسبات تجربی احتمالاتی بر پایه michaelsboost/CandleEdge.
 * شناسایی الگوهای: Hammer, Inverted Hammer, Bullish/Bearish Engulfing,
 * Morning/Evening Star, Doji, Pinbar و محاسبه وین‌ریت‌های پیش‌رو (۱، ۳ و ۵ باره).
 */

import type {
  Candle,
  CandlePatternType,
  DetectedPattern,
  CandleEdgeReport,
  PriceZone,
  MarketRegime,
  MarketStructurePoint,
} from './types';

export interface EmpiricalDistribution {
  negativeLarge: number; // بازده کمتر از -۲٪
  negativeSmall: number; // بازده بین -۲٪ تا ۰٪
  positiveSmall: number; // بازده بین ۰٪ تا +۲٪
  positiveLarge: number; // بازده بیشتر از +۲٪
}

export interface EdgeScanResult {
  detectedPatterns: DetectedPattern[];
  latestPattern: DetectedPattern | null;
  winRate1Bar: number;
  winRate3Bar: number;
  winRate5Bar: number;
  profitFactor: number;
  riskRewardRatio: number;
  sampleCount: number;
  distribution: EmpiricalDistribution;
}

/**
 * تشخیص الگوهای کندلی در ایندکس مشخص از سری زمانی
 */
export function detectPatternsAtIndex(candles: Candle[], index: number): DetectedPattern[] {
  if (index < 0 || index >= candles.length) return [];

  const curr = candles[index];
  const range = curr.high - curr.low;
  if (range <= 0) return [];

  const body = Math.abs(curr.close - curr.open);
  const upperWick = curr.high - Math.max(curr.close, curr.open);
  const lowerWick = Math.min(curr.close, curr.open) - curr.low;
  const isGreen = curr.close >= curr.open;

  const patterns: DetectedPattern[] = [];

  // ۱. دوجی (Doji)
  if (body <= 0.1 * range) {
    patterns.push({
      type: 'DOJI',
      nameFa: 'دوجی',
      nameEn: 'Doji',
      isBullish: isGreen,
      index,
      timestamp: curr.timestamp,
    });
  }

  // ۲. پین‌بار صعودی (Bullish Pinbar)
  if (lowerWick >= 0.6 * range && upperWick <= 0.2 * range) {
    patterns.push({
      type: 'BULLISH_PINBAR',
      nameFa: 'پین‌بار صعودی',
      nameEn: 'Bullish Pinbar',
      isBullish: true,
      index,
      timestamp: curr.timestamp,
    });
  }

  // ۳. پین‌بار نزولی (Bearish Pinbar)
  if (upperWick >= 0.6 * range && lowerWick <= 0.2 * range) {
    patterns.push({
      type: 'BEARISH_PINBAR',
      nameFa: 'پین‌بار نزولی',
      nameEn: 'Bearish Pinbar',
      isBullish: false,
      index,
      timestamp: curr.timestamp,
    });
  }

  // ۴. چکش (Hammer)
  if (lowerWick >= 2 * body && upperWick <= 0.25 * range && body > 0) {
    patterns.push({
      type: 'HAMMER',
      nameFa: 'چکش',
      nameEn: 'Hammer',
      isBullish: true,
      index,
      timestamp: curr.timestamp,
    });
  }

  // ۵. چکش معکوس (Inverted Hammer)
  if (upperWick >= 2 * body && lowerWick <= 0.25 * range && body > 0) {
    patterns.push({
      type: 'INVERTED_HAMMER',
      nameFa: 'چکش معکوس',
      nameEn: 'Inverted Hammer',
      isBullish: true,
      index,
      timestamp: curr.timestamp,
    });
  }

  // ۶ و ۷. الگوهای دوشمعی (Engulfing)
  if (index >= 1) {
    const prev = candles[index - 1];
    const prevRange = prev.high - prev.low;
    if (prevRange > 0) {
      // پوشای صعودی
      if (
        prev.close < prev.open &&
        curr.close > curr.open &&
        curr.close >= prev.open &&
        curr.open <= prev.close
      ) {
        patterns.push({
          type: 'BULLISH_ENGULFING',
          nameFa: 'پوشای صعودی',
          nameEn: 'Bullish Engulfing',
          isBullish: true,
          index,
          timestamp: curr.timestamp,
        });
      }

      // پوشای نزولی
      if (
        prev.close > prev.open &&
        curr.close < curr.open &&
        curr.close <= prev.open &&
        curr.open >= prev.close
      ) {
        patterns.push({
          type: 'BEARISH_ENGULFING',
          nameFa: 'پوشای نزولی',
          nameEn: 'Bearish Engulfing',
          isBullish: false,
          index,
          timestamp: curr.timestamp,
        });
      }
    }
  }

  // ۸ و ۹. الگوهای سه‌شمعی (Morning & Evening Star)
  if (index >= 2) {
    const c0 = candles[index - 2];
    const c1 = candles[index - 1];
    const c2 = curr;

    const c0Range = c0.high - c0.low;
    const c1Range = c1.high - c1.low;

    if (c0Range > 0 && c1Range > 0) {
      const c0Body = Math.abs(c0.close - c0.open);
      const c1Body = Math.abs(c1.close - c1.open);

      // ستاره صبحگاهی (Morning Star)
      if (
        c0.close < c0.open &&
        c0Body >= 0.4 * c0Range &&
        c1Body <= 0.35 * c1Range &&
        c2.close > c2.open &&
        c2.close >= (c0.open + c0.close) / 2
      ) {
        patterns.push({
          type: 'MORNING_STAR',
          nameFa: 'ستاره صبحگاهی',
          nameEn: 'Morning Star',
          isBullish: true,
          index,
          timestamp: curr.timestamp,
        });
      }

      // ستاره شامگاهی (Evening Star)
      if (
        c0.close > c0.open &&
        c0Body >= 0.4 * c0Range &&
        c1Body <= 0.35 * c1Range &&
        c2.close < c2.open &&
        c2.close <= (c0.open + c0.close) / 2
      ) {
        patterns.push({
          type: 'EVENING_STAR',
          nameFa: 'ستاره شامگاهی',
          nameEn: 'Evening Star',
          isBullish: false,
          index,
          timestamp: curr.timestamp,
        });
      }
    }
  }

  return patterns;
}

const PATTERN_PRIORITY: CandlePatternType[] = [
  'HAMMER',
  'INVERTED_HAMMER',
  'MORNING_STAR',
  'EVENING_STAR',
  'BULLISH_ENGULFING',
  'BEARISH_ENGULFING',
  'BULLISH_PINBAR',
  'BEARISH_PINBAR',
  'DOJI',
];

function selectPrimaryPattern(patterns: DetectedPattern[]): DetectedPattern {
  for (const type of PATTERN_PRIORITY) {
    const found = patterns.find((p) => p.type === type);
    if (found) return found;
  }
  return patterns[0];
}

/**
 * تشخیص آخرین الگوی معتبر در انتهای چارت
 */
export function detectLatestPattern(candles: Candle[]): DetectedPattern | null {
  if (candles.length === 0) return null;

  // بررسی کندل نهایی
  const lastIndex = candles.length - 1;
  const lastPatterns = detectPatternsAtIndex(candles, lastIndex);
  if (lastPatterns.length > 0) {
    return selectPrimaryPattern(lastPatterns);
  }

  // بررسی یک کندل قبل‌تر
  if (lastIndex >= 1) {
    const prevPatterns = detectPatternsAtIndex(candles, lastIndex - 1);
    if (prevPatterns.length > 0) {
      return selectPrimaryPattern(prevPatterns);
    }
  }

  return null;
}

/**
 * شناسایی خلاء نقدینگی (Fair Value Gaps - FVG)
 */
export function detectFairValueGaps(candles: Candle[], minGapRatio = 0.001): PriceZone[] {
  const zones: PriceZone[] = [];
  const n = candles.length;
  if (n < 3) return zones;

  for (let i = 1; i < n - 1; i++) {
    const prev = candles[i - 1];
    const next = candles[i + 1];
    const threshold = candles[i].close * minGapRatio;

    // FVG صعودی: Low[i+1] > High[i-1]
    if (next.low > prev.high && next.low - prev.high >= threshold) {
      const top = next.low;
      const bottom = prev.high;
      const equilibrium = (top + bottom) / 2;

      let mitigated = false;
      let mitigatedTs: number | undefined;

      for (let k = i + 2; k < n; k++) {
        if (candles[k].low <= equilibrium) {
          mitigated = true;
          mitigatedTs = candles[k].timestamp;
          break;
        }
      }

      zones.push({
        id: `fvg_bull_${candles[i].timestamp}`,
        type: 'FVG',
        isBullish: true,
        top,
        bottom,
        equilibrium,
        startIndex: i,
        startTs: candles[i].timestamp,
        mitigated,
        mitigatedTs,
      });
    }

    // FVG نزولی: High[i+1] < Low[i-1]
    if (next.high < prev.low && prev.low - next.high >= threshold) {
      const top = prev.low;
      const bottom = next.high;
      const equilibrium = (top + bottom) / 2;

      let mitigated = false;
      let mitigatedTs: number | undefined;

      for (let k = i + 2; k < n; k++) {
        if (candles[k].high >= equilibrium) {
          mitigated = true;
          mitigatedTs = candles[k].timestamp;
          break;
        }
      }

      zones.push({
        id: `fvg_bear_${candles[i].timestamp}`,
        type: 'FVG',
        isBullish: false,
        top,
        bottom,
        equilibrium,
        startIndex: i,
        startTs: candles[i].timestamp,
        mitigated,
        mitigatedTs,
      });
    }
  }

  return zones;
}

/**
 * تخمین رژیم فعلی بازار (صعودی، نزولی یا رِنج)
 */
export function estimateMarketRegime(candles: Candle[]): MarketRegime {
  const n = candles.length;
  if (n < 10) return 'RANGING';

  // مقایسه میانگین ۵ کندل اخیر با ۲۰ کندل پیشین
  const lookback = Math.min(20, n);
  let sumAll = 0;
  for (let i = n - lookback; i < n; i++) {
    sumAll += candles[i].close;
  }
  const avgLong = sumAll / lookback;

  let sumShort = 0;
  for (let i = n - 5; i < n; i++) {
    sumShort += candles[i].close;
  }
  const avgShort = sumShort / 5;

  const diffPct = (avgShort - avgLong) / avgLong;
  if (diffPct > 0.015) return 'TRENDING_BULL';
  if (diffPct < -0.015) return 'TRENDING_BEAR';
  return 'RANGING';
}

/**
 * اسکن جامع لبه آماری کندل‌ها (CandleEdge)
 */
export function scanCandleEdge(
  candles: Candle[],
  symbol = 'UNKNOWN',
  targetPatternType?: CandlePatternType
): CandleEdgeReport {
  const n = candles.length;
  const latestPattern = detectLatestPattern(candles);
  const patternName = latestPattern?.nameFa ?? 'خنثی';
  const isBullishTarget = latestPattern?.isBullish ?? true;

  if (n < 6) {
    return {
      symbol,
      patternName,
      winRate1Bar: 50,
      winRate3Bar: 50,
      winRate5Bar: 50,
      profitFactor: 1.0,
      riskRewardRatio: 1.0,
      sampleCount: 0,
      marketRegime: 'RANGING',
      activeZones: [],
      recentStructures: [],
    };
  }

  let sampleCount = 0;
  let wins1 = 0;
  let wins3 = 0;
  let wins5 = 0;
  let totalGains = 0;
  let totalLosses = 0;
  let gainCount = 0;
  let lossCount = 0;

  // بررسی سوابق تاریخی که حداقل ۵ کندل بعد از آنها موجود است
  const maxEvalIndex = n - 6;

  for (let j = 1; j <= maxEvalIndex; j++) {
    let matchesTarget = false;

    if (targetPatternType) {
      const patterns = detectPatternsAtIndex(candles, j);
      matchesTarget = patterns.some((p) => p.type === targetPatternType);
    } else {
      // تطابق جهت‌گیری کندل با جهت الگوی جاری
      const c = candles[j];
      const isGreen = c.close >= c.open;
      matchesTarget = isGreen === isBullishTarget;
    }

    if (matchesTarget) {
      const entryPrice = candles[j].close;
      if (entryPrice <= 0) continue;

      sampleCount++;

      // بازده ۱ کندل بعد
      const c1 = candles[j + 1].close;
      const ret1 = isBullishTarget
        ? (c1 - entryPrice) / entryPrice
        : (entryPrice - c1) / entryPrice;

      if (ret1 > 0) {
        wins1++;
        totalGains += ret1;
        gainCount++;
      } else if (ret1 < 0) {
        totalLosses += Math.abs(ret1);
        lossCount++;
      }

      // بازده ۳ کندل بعد
      if (j + 3 < n) {
        const c3 = candles[j + 3].close;
        const ret3 = isBullishTarget
          ? (c3 - entryPrice) / entryPrice
          : (entryPrice - c3) / entryPrice;
        if (ret3 > 0) wins3++;
      }

      // بازده ۵ کندل بعد
      if (j + 5 < n) {
        const c5 = candles[j + 5].close;
        const ret5 = isBullishTarget
          ? (c5 - entryPrice) / entryPrice
          : (entryPrice - c5) / entryPrice;
        if (ret5 > 0) wins5++;
      }
    }
  }

  const winRate1Bar = sampleCount > 0 ? (wins1 / sampleCount) * 100 : 50;
  const winRate3Bar = sampleCount > 0 ? (wins3 / sampleCount) * 100 : 50;
  const winRate5Bar = sampleCount > 0 ? (wins5 / sampleCount) * 100 : 50;

  let profitFactor = 1.0;
  if (totalLosses > 0) {
    profitFactor = totalGains / totalLosses;
  } else if (totalGains > 0) {
    profitFactor = Math.min(10.0, totalGains * 100);
  }

  let riskRewardRatio = 1.0;
  if (gainCount > 0 && lossCount > 0) {
    const avgGain = totalGains / gainCount;
    const avgLoss = totalLosses / lossCount;
    if (avgLoss > 0) {
      riskRewardRatio = avgGain / avgLoss;
    }
  }

  // زون‌های نقدینگی فعال
  const allZones = detectFairValueGaps(candles);
  const activeZones = allZones.filter((z) => !z.mitigated);

  // تخمین رژیم بازار
  const marketRegime = estimateMarketRegime(candles);

  // نقاط ساختاری بازار اخیر
  const recentStructures: MarketStructurePoint[] = [];

  return {
    symbol,
    patternName,
    winRate1Bar: Number(winRate1Bar.toFixed(1)),
    winRate3Bar: Number(winRate3Bar.toFixed(1)),
    winRate5Bar: Number(winRate5Bar.toFixed(1)),
    profitFactor: Number(profitFactor.toFixed(2)),
    riskRewardRatio: Number(riskRewardRatio.toFixed(2)),
    sampleCount,
    marketRegime,
    activeZones,
    recentStructures,
  };
}
