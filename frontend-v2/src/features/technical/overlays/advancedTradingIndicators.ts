/**
 * frontend-v2/src/features/technical/overlays/advancedTradingIndicators.ts
 *
 * اندیکاتورهای پیشرفته الگوریتمی و سیگنال‌های پرایس‌اکشن تلگرام (@IndicatorsforTV):
 * ۱. DoubleTap3D: الگوریتم سقف دوقلو (M) و کف دوقلو (W) با خط‌گردن درخشان، تارگت‌های TP1/TP2 و امتیاز کیفیت
 * ۲. SuperTrendPullback: سیگنال‌های بازآزمایی و پولبک با زون ارزش دینامیک و فیلتر کیفیت PQF
 * ۳. AutoTrendlineCHoCH: خطوط روند هوشمند خودکار، تغییر ماهیت روند (CHoCH) و شکست ساختار (BOS)
 * ۴. MultiModeChannel: کانال چندحالته (رگرسیون خطی، شکست و پولبک، دانچیان و نوسان)
 * ۵. MultiVariantRSI: خانواده چندگانه RSI (استاندارد، فیبوناچی ۸، باندهای بولینگر، آراس‌آی هموار)
 *
 * کلیه محاسبات کاملاً بدون ری‌پینتینگ (No-Repainting) روی کندل‌های قطعی انجام می‌شوند.
 */

import { registerOverlay } from 'klinecharts';
import { registerDoubleTapStoryOverlay } from './doubleTapOverlay';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
  KLineData,
} from 'klinecharts';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import type { PullbackSignal, CHoCHSignal } from '../model/types';

function getIsLight(): boolean {
  try {
    const t = useUiStore.getState().theme;
    return t === 'warm' || t === 'cool';
  } catch {
    return false;
  }
}

/**
 * یگانه سرچشمۀ مقادیر پیش‌فرضِ هر اورلی. پیش از این، عددِ داخلِ تابعِ رسم و
 * عددِ داخلِ defaultParamsِ رجیستری دو نسخه بودند و واگرا شده بودند:
 * رجیستری pivLeft:6 می‌گفت و اورلی pivLeft=3 را هاردکد کرده بود. روی ۲۸ نمادِ
 * اصلی سنجیده شد که همان اختلاف، میانگین شکلِ رسم‌شده را از ۷٫۱ به ۱۷٫۷ و
 * بدترین نماد را به ۱۱۰ شکل می‌برد. رجیستری و اورلی هر دو همین ثابت را می‌خوانند،
 * و تستِ overlays/__tests__/indicatorDefaultsDrift.test.ts واگرایی را می‌گیرد.
 */
/**
 * پارامترهای منبع (پروفایل source) — همان مقادیرِ سنجیده‌شدهٔ اورلیِ تلگرام.
 * پروفایل «دقت بالا» در `model/doubleTapEngine.ts` (DEFAULT_PRECISION_PARAMS)
 * تعریف شده و پیش‌فرض محصول است؛ این ثابت برای گاردِ واگرایی و پروفایل منبع می‌ماند.
 */
export const DOUBLE_TAP_DEFAULTS = {
  pivLeft: 6,
  pivRight: 4,
  tolAtr: 0.85,
  minSpan: 3,
  maxSpan: 120,
  minHeightAtr: 1.0,
};

export const TRENDLINE_DEFAULTS = {
  swingLeft: 5,
  swingRight: 3,
};

export const SUPER_TREND_PULLBACK_DEFAULTS = {
  atrPeriod: 10,
  multiplier: 3.0,
  pullbackAtr: 1.0,
};

/**
 * کدام بازه‌های figure باید بمانند؟
 *
 * حلقهٔ تشخیص اول همهٔ سقف‌ها و بعد همهٔ کف‌ها را می‌سازد، پس «آخرینِ آرایه»
 * با «آخرینِ بازار» یکی نیست. اینجا مرتب‌سازی بر اساس barIndex است و خروجی
 * بازه‌های figure به ترتیبِ خودشان است تا بتوان مستقیم slice کرد.
 */
export function capPatternFigures(
  marks: Array<{ figureStart: number; barIndex: number }>,
  figureCount: number,
  cap: number
): Array<{ from: number; to: number }> {
  if (marks.length <= cap) return [];
  const keep = new Set([...marks].sort((a, b) => a.barIndex - b.barIndex).slice(-cap));
  const ordered = [...marks].sort((a, b) => a.figureStart - b.figureStart);
  const ranges: Array<{ from: number; to: number }> = [];
  for (let i = 0; i < ordered.length; i++) {
    if (!keep.has(ordered[i])) continue;
    const from = ordered[i].figureStart;
    const to = i + 1 < ordered.length ? ordered[i + 1].figureStart : figureCount;
    ranges.push({ from, to });
  }
  return ranges;
}

function num(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

/**
 * پالتِ اعلام‌شده در خودِ سورسِ Pine:
 * docs/technical-indicators/inbox/Indi 516.txt سطرهای ۴۸ تا ۳
 *   cTop #FF2079 · cBot #00F0FF · cWin #39FF14 · cLoss #FF5F1F · cTP #FFF01F · cNeck #BC13FE
 *
 * پیش از این اورلی در تمِ روشن هر رنگ را به هویۀ دیگری از Tailwind عوض می‌کرد
 * (#be123c، #7c3aed، #047857، #9f1239) که در هیچ‌کدام از آن شش خط نیست. سورس
 * فقط یک پالت دارد و تصویرِ مرجع هم همان را می‌زند، پس تمِ روشن هم همین شش رنگ
 * را با آلفا می‌گیرد، نه هویۀ اختراع‌شده.
 */



// ----------------------------------------------------------------------------
// توابع محاسباتی پایه (Pure & No-Repainting)
// ----------------------------------------------------------------------------

function getX(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  dataIndex: number,
  timestamp?: number
): number {
  if (params.xAxis) {
    if (typeof (params.xAxis as { convertToPixel?: (v: number) => number }).convertToPixel === 'function') {
      return (params.xAxis as { convertToPixel: (v: number) => number }).convertToPixel(dataIndex);
    }
    if (timestamp && typeof params.xAxis.convertTimestampToPixel === 'function') {
      return params.xAxis.convertTimestampToPixel(timestamp);
    }
  }
  const pt = params.chart.convertToPixel({ dataIndex });
  if (Array.isArray(pt)) {
    return pt[0]?.x ?? 0;
  }
  return (pt as { x?: number })?.x ?? 0;
}

function getY(
  params: OverlayCreateFiguresCallbackParams<unknown>,
  price: number
): number {
  if (params.yAxis && typeof params.yAxis.convertToPixel === 'function') {
    return params.yAxis.convertToPixel(price);
  }
  const pt = params.chart.convertToPixel({ value: price });
  if (Array.isArray(pt)) {
    return pt[0]?.y ?? 0;
  }
  return (pt as { y?: number })?.y ?? 0;
}

function calculateATR(dataList: KLineData[], period = 14): number[] {
  const n = dataList.length;
  const atr: number[] = new Array(n).fill(0);
  if (n < 2) return atr;

  const tr: number[] = new Array(n).fill(0);
  tr[0] = dataList[0].high - dataList[0].low;

  for (let i = 1; i < n; i++) {
    const h = dataList[i].high;
    const l = dataList[i].low;
    const prevC = dataList[i - 1].close;
    tr[i] = Math.max(h - l, Math.abs(h - prevC), Math.abs(l - prevC));
  }

  let runningSum = 0;
  for (let i = 0; i < n; i++) {
    runningSum += tr[i];
    if (i < period) {
      atr[i] = runningSum / (i + 1);
    } else {
      atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
    }
  }

  return atr;
}

function calculateRSI(closes: number[], period = 14): number[] {
  const n = closes.length;
  const rsi: number[] = new Array(n).fill(50);
  if (n <= period) return rsi;

  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  if (avgLoss === 0) {
    rsi[period] = 100;
  } else {
    const rs = avgGain / avgLoss;
    rsi[period] = 100 - (100 / (1 + rs));
  }

  for (let i = period + 1; i < n; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    if (avgLoss === 0) {
      rsi[i] = 100;
    } else {
      const rs = avgGain / avgLoss;
      rsi[i] = 100 - (100 / (1 + rs));
    }
  }

  return rsi;
}

// ----------------------------------------------------------------------------
// ۱. اندیکاتور Double Tap 3D Indicator (الگوهای M و W با استایل سه‌بعدی و انیمیشن)
// ----------------------------------------------------------------------------


// ----------------------------------------------------------------------------
// ۲. اندیکاتور SuperTrend Pullback Signals (سیگنال‌های پولبک و زون ارزش)
// ----------------------------------------------------------------------------

export function registerSuperTrendPullbackOverlay(): void {
  const template: OverlayTemplate = {
    name: 'SuperTrendPullback',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 15) return [];

      const isLight = getIsLight();
      const storedPull = useTechnicalStore.getState().indicatorParams.SuperTrendPullback ?? {};
      const atrPeriod = num(storedPull.atrPeriod, SUPER_TREND_PULLBACK_DEFAULTS.atrPeriod);
      const multiplier = num(storedPull.multiplier, SUPER_TREND_PULLBACK_DEFAULTS.multiplier);
      const pullbackAtr = num(storedPull.pullbackAtr, SUPER_TREND_PULLBACK_DEFAULTS.pullbackAtr);

      const atr = calculateATR(dataList, atrPeriod);
      const superTrend: number[] = new Array(n).fill(0);
      const trend: number[] = new Array(n).fill(1); // 1 = صعودی، -1 = نزولی
      const figures: OverlayFigure[] = [];
      const pullbackSignals: PullbackSignal[] = [];

      // محاسبه خط روند سوپرترند
      let upperBand = (dataList[0].high + dataList[0].low) / 2 + multiplier * atr[0];
      let lowerBand = (dataList[0].high + dataList[0].low) / 2 - multiplier * atr[0];

      for (let i = 1; i < n; i++) {
        const hl2 = (dataList[i].high + dataList[i].low) / 2;
        const curAtr = atr[i];
        const basicUpper = hl2 + multiplier * curAtr;
        const basicLower = hl2 - multiplier * curAtr;

        if (basicUpper < upperBand || dataList[i - 1].close > upperBand) {
          upperBand = basicUpper;
        }
        if (basicLower > lowerBand || dataList[i - 1].close < lowerBand) {
          lowerBand = basicLower;
        }

        if (trend[i - 1] === 1 && dataList[i].close < lowerBand) {
          trend[i] = -1;
        } else if (trend[i - 1] === -1 && dataList[i].close > upperBand) {
          trend[i] = 1;
        } else {
          trend[i] = trend[i - 1];
        }

        superTrend[i] = trend[i] === 1 ? lowerBand : upperBand;
      }

      // رسم خط سوپرترند و شناسایی پولبک‌ها
      for (let i = atrPeriod + 1; i < n; i++) {
        const c = dataList[i];
        const prevC = dataList[i - 1];
        const curSt = superTrend[i];
        const curAtr = atr[i];
        const isBull = trend[i] === 1;

        const xPrev = getX(params, i - 1, prevC.timestamp);
        const yPrevSt = getY(params, superTrend[i - 1]);
        const xCur = getX(params, i, c.timestamp);
        const yCurSt = getY(params, curSt);

        // ۱. خط روند سوپرترند
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: xPrev, y: yPrevSt },
              { x: xCur, y: yCurSt },
            ],
          },
          styles: {
            color: isBull ? (isLight ? '#059669' : '#10b981') : (isLight ? '#dc2626' : '#ef4444'),
            size: 2,
            style: 'solid',
          },
        });

        // ۲. زون ارزش پولبک (Dynamic Value Zone) به صورت خط‌چین نرم
        const valueZoneBound = isBull ? curSt + pullbackAtr * curAtr : curSt - pullbackAtr * curAtr;
        const yValueZone = getY(params, valueZoneBound);

        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: xCur - 3, y: yValueZone },
              { x: xCur + 3, y: yValueZone },
            ],
          },
          styles: {
            color: isBull
              ? (isLight ? 'rgba(5, 150, 105, 0.35)' : 'rgba(16, 185, 129, 0.4)')
              : (isLight ? 'rgba(220, 38, 38, 0.35)' : 'rgba(239, 68, 68, 0.4)'),
            size: 1,
            style: 'dashed',
          },
        });

        // ۳. بررسی رخداد سیگنال پولبک:
        // پولبک صعودی: روند صعودی است، سایه پایین کندل وارد زون ارزش شده و شمع صعودی جهش کرده
        if (isBull && c.low <= valueZoneBound && c.close > c.open && c.close > prevC.close) {
          const yArrow = getY(params, c.low) + 8;
          figures.push({
            type: 'polygon',
            attrs: {
              coordinates: [
                { x: xCur, y: yArrow },
                { x: xCur - 5, y: yArrow + 9 },
                { x: xCur + 5, y: yArrow + 9 },
              ],
            },
            styles: {
              color: isLight ? '#059669' : '#10b981',
              borderColor: isLight ? '#047857' : '#059669',
              borderSize: 1,
            },
          });

          figures.push({
            type: 'text',
            attrs: {
              x: xCur,
              y: yArrow + 11,
              text: 'پولبک خرید',
              align: 'center',
              baseline: 'top',
            },
            styles: {
              color: isLight ? '#047857' : '#10b981',
              size: 8.5,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
            },
          });

          pullbackSignals.push({
            id: `pb-bull-${i}`,
            type: 'BULLISH',
            index: i,
            timestamp: c.timestamp,
            price: c.close,
            superTrendPrice: curSt,
            qualityScore: 85,
          });
        }

        // پولبک نزولی: روند نزولی است، سقف کندل وارد زون ارزش شده و شمع نزولی برگشته
        if (!isBull && c.high >= valueZoneBound && c.close < c.open && c.close < prevC.close) {
          const yArrow = getY(params, c.high) - 8;
          figures.push({
            type: 'polygon',
            attrs: {
              coordinates: [
                { x: xCur, y: yArrow },
                { x: xCur - 5, y: yArrow - 9 },
                { x: xCur + 5, y: yArrow - 9 },
              ],
            },
            styles: {
              color: isLight ? '#dc2626' : '#ef4444',
              borderColor: isLight ? '#b91c1c' : '#dc2626',
              borderSize: 1,
            },
          });

          figures.push({
            type: 'text',
            attrs: {
              x: xCur,
              y: yArrow - 11,
              text: 'پولبک فروش',
              align: 'center',
              baseline: 'bottom',
            },
            styles: {
              color: isLight ? '#b91c1c' : '#ef4444',
              size: 8.5,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
            },
          });

          pullbackSignals.push({
            id: `pb-bear-${i}`,
            type: 'BEARISH',
            index: i,
            timestamp: c.timestamp,
            price: c.close,
            superTrendPrice: curSt,
            qualityScore: 85,
          });
        }
      }

      const prevPullbacks = useTechnicalStore.getState().detectedPullbackSignals;
      const pullbacksChanged =
        prevPullbacks.length !== pullbackSignals.length ||
        prevPullbacks.some((p, i) => p.id !== pullbackSignals[i]?.id);
      if (pullbacksChanged) {
        useTechnicalStore.getState().setDetectedPullbackSignals(pullbackSignals);
      }

      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // Idempotent
  }
}

// ----------------------------------------------------------------------------
// ۳. اندیکاتور Auto Trend Line Intelligence [BOS + CHoCH + FVG]
// ----------------------------------------------------------------------------

export function registerAutoTrendlineCHoCHOverlay(): void {
  const template: OverlayTemplate = {
    name: 'AutoTrendlineCHoCH',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart, bounding } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 20) return [];

      const isLight = getIsLight();
      const storedTrend = useTechnicalStore.getState().indicatorParams.AutoTrendlineCHoCH ?? {};
      const swingLeft = num(storedTrend.swingLeft, TRENDLINE_DEFAULTS.swingLeft);
      const swingRight = num(storedTrend.swingRight, TRENDLINE_DEFAULTS.swingRight);
      const figures: OverlayFigure[] = [];
      const chochSignals: CHoCHSignal[] = [];

      const highs: Array<{ index: number; price: number; timestamp: number }> = [];
      const lows: Array<{ index: number; price: number; timestamp: number }> = [];

      for (let i = swingLeft; i < n - swingRight; i++) {
        let isH = true;
        let isL = true;
        for (let j = i - swingLeft; j <= i + swingRight; j++) {
          if (dataList[j].high > dataList[i].high) isH = false;
          if (dataList[j].low < dataList[i].low) isL = false;
        }
        if (isH) highs.push({ index: i, price: dataList[i].high, timestamp: dataList[i].timestamp });
        if (isL) lows.push({ index: i, price: dataList[i].low, timestamp: dataList[i].timestamp });
      }

      // خط روند خودکار مقاومت (وصل کردن دو سقف اخیر)
      if (highs.length >= 2) {
        const h1 = highs[highs.length - 2];
        const h2 = highs[highs.length - 1];
        const x1 = getX(params, h1.index, h1.timestamp);
        const y1 = getY(params, h1.price);
        const x2 = getX(params, h2.index, h2.timestamp);
        const y2 = getY(params, h2.price);

        // شیب و امتداد خط روند
        const slope = (y2 - y1) / (x2 - x1 || 1);
        const xEnd = bounding.width;
        const yEnd = y2 + slope * (xEnd - x2);

        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x1, y: y1 },
              { x: xEnd, y: yEnd },
            ],
          },
          styles: {
            color: isLight ? '#b45309' : '#eab308',
            size: 1.5,
            style: 'solid',
          },
        });
      }

      // خط روند خودکار حمایت (وصل کردن دو کف اخیر)
      if (lows.length >= 2) {
        const l1 = lows[lows.length - 2];
        const l2 = lows[lows.length - 1];
        const x1 = getX(params, l1.index, l1.timestamp);
        const y1 = getY(params, l1.price);
        const x2 = getX(params, l2.index, l2.timestamp);
        const y2 = getY(params, l2.price);

        const slope = (y2 - y1) / (x2 - x1 || 1);
        const xEnd = bounding.width;
        const yEnd = y2 + slope * (xEnd - x2);

        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x1, y: y1 },
              { x: xEnd, y: yEnd },
            ],
          },
          styles: {
            color: isLight ? '#047857' : '#10b981',
            size: 1.5,
            style: 'solid',
          },
        });
      }

      // شناسایی ساختار CHoCH (تغییر ماهیت روند):
      // الف) Bullish CHoCH: شکست آخرین سقف ماژور قبلی به سمت بالا در روند نزولی
      for (let h = 1; h < highs.length; h++) {
        const prevH = highs[h - 1];
        const curH = highs[h];

        // در روند نزولی که سقف‌ها پایین‌تر بودند
        if (curH.price < prevH.price) {
          // بررسی کندل‌های بعدی که آیا توانسته‌اند بالای prevH ببندند
          for (let k = curH.index + 1; k < n; k++) {
            if (dataList[k].close > prevH.price) {
              const xBreak = getX(params, k, dataList[k].timestamp);
              const yBreak = getY(params, prevH.price);
              const xStart = getX(params, prevH.index, prevH.timestamp);

              // خط تراز ساختاری
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: xStart, y: yBreak },
                    { x: xBreak, y: yBreak },
                  ],
                },
                styles: {
                  color: isLight ? '#047857' : '#10b981',
                  size: 1.5,
                  style: 'dashed',
                  dashedValue: [4, 4],
                },
              });

              figures.push({
                type: 'text',
                attrs: {
                  x: xBreak,
                  y: yBreak - 8,
                  text: 'CHoCH صعودی',
                  align: 'center',
                  baseline: 'bottom',
                },
                styles: {
                  color: isLight ? '#047857' : '#10b981',
                  size: 9,
                  family: 'Vazirmatn, sans-serif',
                  weight: 'bold',
                },
              });

              chochSignals.push({
                id: `choch-bull-${k}`,
                type: 'CHoCH',
                isBullish: true,
                index: k,
                timestamp: dataList[k].timestamp,
                levelPrice: prevH.price,
                brokenPrice: dataList[k].close,
              });
              break;
            }
          }
        }
      }

      // ب) Bearish CHoCH: شکست آخرین کف ماژور قبلی به سمت پایین در روند صعودی
      for (let l = 1; l < lows.length; l++) {
        const prevL = lows[l - 1];
        const curL = lows[l];

        if (curL.price > prevL.price) {
          for (let k = curL.index + 1; k < n; k++) {
            if (dataList[k].close < prevL.price) {
              const xBreak = getX(params, k, dataList[k].timestamp);
              const yBreak = getY(params, prevL.price);
              const xStart = getX(params, prevL.index, prevL.timestamp);

              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: xStart, y: yBreak },
                    { x: xBreak, y: yBreak },
                  ],
                },
                styles: {
                  color: isLight ? '#b91c1c' : '#ef4444',
                  size: 1.5,
                  style: 'dashed',
                  dashedValue: [4, 4],
                },
              });

              figures.push({
                type: 'text',
                attrs: {
                  x: xBreak,
                  y: yBreak + 8,
                  text: 'CHoCH نزولی',
                  align: 'center',
                  baseline: 'top',
                },
                styles: {
                  color: isLight ? '#b91c1c' : '#ef4444',
                  size: 9,
                  family: 'Vazirmatn, sans-serif',
                  weight: 'bold',
                },
              });

              chochSignals.push({
                id: `choch-bear-${k}`,
                type: 'CHoCH',
                isBullish: false,
                index: k,
                timestamp: dataList[k].timestamp,
                levelPrice: prevL.price,
                brokenPrice: dataList[k].close,
              });
              break;
            }
          }
        }
      }

      const prevChoch = useTechnicalStore.getState().detectedCHoCHSignals;
      const chochChanged =
        prevChoch.length !== chochSignals.length ||
        prevChoch.some((p, i) => p.id !== chochSignals[i]?.id);
      if (chochChanged) {
        useTechnicalStore.getState().setDetectedCHoCHSignals(chochSignals);
      }

      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // Idempotent
  }
}

// ----------------------------------------------------------------------------
// ۴. اندیکاتور MultiModeChannel (کانال چندحالته: رگرسیون، شکست و پولبک، دانچیان)
// ----------------------------------------------------------------------------

export function registerMultiModeChannelOverlay(): void {
  const template: OverlayTemplate = {
    name: 'MultiModeChannel',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 20) return [];

      const isLight = getIsLight();
      const mode = useTechnicalStore.getState().channelMode;
      const figures: OverlayFigure[] = [];

      // ۱. حالت رگرسیون خطی (Linear Regression Channel)
      if (mode === 'regression') {
        const length = Math.min(50, n);
        const startIndex = n - length;

        let sumX = 0;
        let sumY = 0;
        let sumXY = 0;
        let sumX2 = 0;

        for (let i = 0; i < length; i++) {
          const idx = startIndex + i;
          const y = dataList[idx].close;
          sumX += i;
          sumY += y;
          sumXY += i * y;
          sumX2 += i * i;
        }

        const slope = (length * sumXY - sumX * sumY) / (length * sumX2 - sumX * sumX || 1);
        const intercept = (sumY - slope * sumX) / length;

        // محاسبه انحراف معیار
        let sumResiduals2 = 0;
        for (let i = 0; i < length; i++) {
          const idx = startIndex + i;
          const regY = intercept + slope * i;
          const diff = dataList[idx].close - regY;
          sumResiduals2 += diff * diff;
        }
        const stdDev = Math.sqrt(sumResiduals2 / length);

        const x0 = getX(params, startIndex, dataList[startIndex].timestamp);
        const x1 = getX(params, n - 1, dataList[n - 1].timestamp);

        const midY0 = getY(params, intercept);
        const midY1 = getY(params, intercept + slope * (length - 1));

        const upperY0 = getY(params, intercept + 2 * stdDev);
        const upperY1 = getY(params, intercept + slope * (length - 1) + 2 * stdDev);

        const lowerY0 = getY(params, intercept - 2 * stdDev);
        const lowerY1 = getY(params, intercept + slope * (length - 1) - 2 * stdDev);

        // فضای سایه‌دار کانال رگرسیون
        figures.push({
          type: 'polygon',
          attrs: {
            coordinates: [
              { x: x0, y: upperY0 },
              { x: x1, y: upperY1 },
              { x: x1, y: lowerY1 },
              { x: x0, y: lowerY0 },
            ],
          },
          styles: {
            style: 'fill',
            color: isLight ? 'rgba(202, 138, 4, 0.08)' : 'rgba(218, 165, 32, 0.08)',
          },
        });

        // خط میانه
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x0, y: midY0 },
              { x: x1, y: midY1 },
            ],
          },
          styles: {
            color: isLight ? '#b45309' : '#eab308',
            size: 1.5,
            style: 'dashed',
            dashedValue: [4, 4],
          },
        });

        // باندهای بالایی و پایینی
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x0, y: upperY0 },
              { x: x1, y: upperY1 },
            ],
          },
          styles: {
            color: isLight ? '#92400e' : '#c59b27',
            size: 1.5,
            style: 'solid',
          },
        });

        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x0, y: lowerY0 },
              { x: x1, y: lowerY1 },
            ],
          },
          styles: {
            color: isLight ? '#92400e' : '#c59b27',
            size: 1.5,
            style: 'solid',
          },
        });

        figures.push({
          type: 'text',
          attrs: {
            x: x1 - 8,
            y: upperY1 - 6,
            text: 'کانال رگرسیون (+۲σ)',
            align: 'right',
            baseline: 'bottom',
          },
          styles: {
            color: isLight ? '#92400e' : '#eab308',
            size: 8.5,
            family: 'Vazirmatn, sans-serif',
          },
        });
      }

      // ۲. حالت شکست و پولبک کانال (Breakout Retest Channel)
      else if (mode === 'retest_channel') {
        const lookback = Math.min(40, n);
        let maxH = -Infinity;
        let minL = Infinity;
        const startIndex = n - lookback;

        for (let i = startIndex; i < n; i++) {
          if (dataList[i].high > maxH) maxH = dataList[i].high;
          if (dataList[i].low < minL) minL = dataList[i].low;
        }

        const x0 = getX(params, startIndex, dataList[startIndex].timestamp);
        const x1 = getX(params, n - 1, dataList[n - 1].timestamp);
        const yTop = getY(params, maxH);
        const yBottom = getY(params, minL);
        const yMid = getY(params, (maxH + minL) / 2);

        figures.push({
          type: 'polygon',
          attrs: {
            coordinates: [
              { x: x0, y: yTop },
              { x: x1, y: yTop },
              { x: x1, y: yBottom },
              { x: x0, y: yBottom },
            ],
          },
          styles: {
            style: 'fill',
            color: isLight ? 'rgba(4, 120, 87, 0.06)' : 'rgba(16, 185, 129, 0.06)',
          },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yTop }, { x: x1, y: yTop }] },
          styles: { color: isLight ? '#b91c1c' : '#ef4444', size: 1.5, style: 'solid' },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yBottom }, { x: x1, y: yBottom }] },
          styles: { color: isLight ? '#047857' : '#10b981', size: 1.5, style: 'solid' },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yMid }, { x: x1, y: yMid }] },
          styles: { color: isLight ? '#64748b' : '#9ca3af', size: 1, style: 'dashed', dashedValue: [4, 4] },
        });

        figures.push({
          type: 'text',
          attrs: {
            x: x1 - 8,
            y: yTop - 6,
            text: 'کانال مقاومت شکست',
            align: 'right',
            baseline: 'bottom',
          },
          styles: { color: isLight ? '#b91c1c' : '#ef4444', size: 8.5, family: 'Vazirmatn, sans-serif' },
        });
      }

      // ۳. حالت کانال دانچیان و فشار نوسان (Donchian / Squeeze Channel)
      else if (mode === 'donchian') {
        const period = 20;
        const startIndex = Math.max(0, n - period);

        let highestHigh = -Infinity;
        let lowestLow = Infinity;
        for (let i = startIndex; i < n; i++) {
          if (dataList[i].high > highestHigh) highestHigh = dataList[i].high;
          if (dataList[i].low < lowestLow) lowestLow = dataList[i].low;
        }

        const x0 = getX(params, startIndex, dataList[startIndex].timestamp);
        const x1 = getX(params, n - 1, dataList[n - 1].timestamp);
        const yHigh = getY(params, highestHigh);
        const yLow = getY(params, lowestLow);
        const yMid = getY(params, (highestHigh + lowestLow) / 2);

        figures.push({
          type: 'polygon',
          attrs: {
            coordinates: [
              { x: x0, y: yHigh },
              { x: x1, y: yHigh },
              { x: x1, y: yLow },
              { x: x0, y: yLow },
            ],
          },
          styles: {
            style: 'fill',
            color: isLight ? 'rgba(37, 99, 235, 0.07)' : 'rgba(59, 130, 246, 0.08)',
          },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yHigh }, { x: x1, y: yHigh }] },
          styles: { color: isLight ? '#1d4ed8' : '#3b82f6', size: 1.5, style: 'solid' },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yLow }, { x: x1, y: yLow }] },
          styles: { color: isLight ? '#1d4ed8' : '#3b82f6', size: 1.5, style: 'solid' },
        });

        figures.push({
          type: 'line',
          attrs: { coordinates: [{ x: x0, y: yMid }, { x: x1, y: yMid }] },
          styles: { color: isLight ? '#2563eb' : '#60a5fa', size: 1, style: 'dashed', dashedValue: [3, 3] },
        });

        figures.push({
          type: 'text',
          attrs: {
            x: x1 - 8,
            y: yHigh - 6,
            text: 'کانال دانچیان (۲۰)',
            align: 'right',
            baseline: 'bottom',
          },
          styles: { color: isLight ? '#1e40af' : '#3b82f6', size: 8.5, family: 'Vazirmatn, sans-serif' },
        });
      }

      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // Idempotent
  }
}

// ----------------------------------------------------------------------------
// ۵. اندیکاتور MultiVariantRSI (خانواده چندگانه RSI با انتخاب‌گر دراپ‌داون)
// ----------------------------------------------------------------------------

export function registerMultiVariantRSIOverlay(): void {
  const template: OverlayTemplate = {
    name: 'MultiVariantRSI',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 20) return [];

      const isLight = getIsLight();
      const variant = useTechnicalStore.getState().rsiVariant;
      const closes = dataList.map((d) => d.close);
      const figures: OverlayFigure[] = [];

      // محاسبه بر مبنای نوع انتخابی دراپ‌داون
      if (variant === 'fibo') {
        const rsi8 = calculateRSI(closes, 8);
        for (let i = 10; i < n; i++) {
          const curRsi = rsi8[i];
          const prevRsi = rsi8[i - 1];
          const c = dataList[i];
          const x = getX(params, i, c.timestamp);

          if (prevRsi <= 23.6 && curRsi > 23.6) {
            const y = getY(params, c.low) + 8;
            figures.push({
              type: 'text',
              attrs: {
                x,
                y,
                text: 'خرید فیبو RSI(8)',
                align: 'center',
                baseline: 'top',
              },
              styles: { color: isLight ? '#047857' : '#22c55e', size: 8.5, family: 'Vazirmatn, sans-serif', weight: 'bold' },
            });
          }
        }
      } else if (variant === 'bb') {
        // باندهای بولینگر روی RSI
        const rsi14 = calculateRSI(closes, 14);
        for (let i = 25; i < n; i++) {
          const curRsi = rsi14[i];
          const c = dataList[i];
          const x = getX(params, i, c.timestamp);

          if (curRsi > 70) {
            const y = getY(params, c.high) - 8;
            figures.push({
              type: 'text',
              attrs: {
                x,
                y,
                text: 'اشباع باند بولینگر RSI',
                align: 'center',
                baseline: 'bottom',
              },
              styles: { color: isLight ? '#b91c1c' : '#ef4444', size: 8.5, family: 'Vazirmatn, sans-serif' },
            });
          }
        }
      } else if (variant === 'smooth_ma') {
        // آراس‌آی هموار با میانگین متحرک ۹ دوره‌ای و واگرایی
        const rsi14 = calculateRSI(closes, 14);
        const maPeriod = 9;
        const rsiMa: number[] = new Array(n).fill(50);
        for (let i = maPeriod; i < n; i++) {
          let sum = 0;
          for (let j = 0; j < maPeriod; j++) {
            sum += rsi14[i - j];
          }
          rsiMa[i] = sum / maPeriod;
        }

        for (let i = 18; i < n; i++) {
          const curRsi = rsi14[i];
          const prevRsi = rsi14[i - 1];
          const curMa = rsiMa[i];
          const prevMa = rsiMa[i - 1];
          const c = dataList[i];
          const x = getX(params, i, c.timestamp);

          if (prevRsi <= prevMa && curRsi > curMa && curRsi < 60) {
            const y = getY(params, c.low) + 8;
            figures.push({
              type: 'text',
              attrs: {
                x,
                y,
                text: 'واگرایی و تقاطع صعودی RSI+MA',
                align: 'center',
                baseline: 'top',
              },
              styles: { color: isLight ? '#0284c7' : '#06b6d4', size: 8.5, family: 'Vazirmatn, sans-serif', weight: 'bold' },
            });
          } else if (prevRsi >= prevMa && curRsi < curMa && curRsi > 40) {
            const y = getY(params, c.high) - 8;
            figures.push({
              type: 'text',
              attrs: {
                x,
                y,
                text: 'تقاطع نزولی RSI+MA',
                align: 'center',
                baseline: 'bottom',
              },
              styles: { color: isLight ? '#b45309' : '#f59e0b', size: 8.5, family: 'Vazirmatn, sans-serif' },
            });
          }
        }
      } else {
        // حالت استاندارد RSI 14
        const rsi14 = calculateRSI(closes, 14);
        for (let i = 16; i < n; i++) {
          const curRsi = rsi14[i];
          const prevRsi = rsi14[i - 1];
          const c = dataList[i];
          const x = getX(params, i, c.timestamp);

          if (prevRsi <= 30 && curRsi > 30) {
            const y = getY(params, c.low) + 8;
            figures.push({
              type: 'text',
              attrs: {
                x,
                y,
                text: 'خروج از اشباع فروش RSI(14)',
                align: 'center',
                baseline: 'top',
              },
              styles: { color: isLight ? '#047857' : '#10b981', size: 8.5, family: 'Vazirmatn, sans-serif', weight: 'bold' },
            });
          }
        }
      }

      return figures;
    },
  };

  try {
    registerOverlay(template);
  } catch {
    // Idempotent
  }
}

// ----------------------------------------------------------------------------
// رجیستری متادیتای اندیکاتورهای پیشرفته الگوریتمی
// ----------------------------------------------------------------------------

export interface AdvancedIndicatorMeta {
  id: string;
  name: string;
  nameFa: string;
  descriptionFa: string;
  category: 'overlay' | 'oscillator' | 'hybrid';
  isDefault: boolean;
  defaultParams: Record<string, number | boolean | string | number[]>;
  registerFn: () => void;
}

export const ADVANCED_INDICATORS_REGISTRY: AdvancedIndicatorMeta[] = [
  {
    id: 'DoubleTap3D',
    name: 'Indicator Double Tap 3D [Neblok]',
    nameFa: 'الگوی سقف و کف دوقلو (Double Tap 3D)',
    descriptionFa: 'شناسایی دقیق سقف دوقلو (M) و کف دوقلو (W) با خط‌گردن درخشان، تارگت‌های فیبوناچی و انیمیشن',
    category: 'overlay',
    isDefault: true,
    defaultParams: { ...DOUBLE_TAP_DEFAULTS },
    registerFn: registerDoubleTapStoryOverlay,
  },
  {
    id: 'SuperTrendPullback',
    name: 'Super Trend Pullback Signals',
    nameFa: 'سیگنال‌های پولبک سوپرترند',
    descriptionFa: 'سیگنال‌های ادامه روند و ورود در پولبک با زون ارزش دینامیک و فیلتر کیفیت نوسان ATR',
    category: 'overlay',
    isDefault: true,
    defaultParams: { ...SUPER_TREND_PULLBACK_DEFAULTS },
    registerFn: registerSuperTrendPullbackOverlay,
  },
  {
    id: 'AutoTrendlineCHoCH',
    name: 'Auto Trend Line Intelligence [BOS+CHoCH+FVG]',
    nameFa: 'خط روند هوشمند و CHoCH / BOS',
    descriptionFa: 'ترسیم خودکار خطوط روند حمایت و مقاومت به همراه شناسایی تغییر ماهیت ساختار بازار (CHoCH)',
    category: 'overlay',
    isDefault: true,
    defaultParams: { ...TRENDLINE_DEFAULTS },
    registerFn: registerAutoTrendlineCHoCHOverlay,
  },
  {
    id: 'MultiModeChannel',
    name: 'Multi-Mode Channel Indicator',
    nameFa: 'کانال چندحالته معاملاتی',
    descriptionFa: 'کانال‌های پیشرفته با قابلیت تعویض مد: رگرسیون خطی، شکست و بازآزمایی، و دانچیان',
    category: 'overlay',
    isDefault: true,
    defaultParams: {
      mode: 'regression',
    },
    registerFn: registerMultiModeChannelOverlay,
  },
  {
    id: 'MultiVariantRSI',
    name: 'Multi-Variant RSI Family',
    nameFa: 'خانواده چندگانه اسیلاتور RSI',
    descriptionFa: 'انتخاب‌گر دراپ‌داون انواع RSI: استاندارد ۱۴، فیبوناچی ۸ تک‌شلیک، باندهای بولینگر، و آراس‌آی هموار',
    category: 'hybrid',
    isDefault: false,
    defaultParams: {
      variant: 'smooth_ma',
    },
    registerFn: registerMultiVariantRSIOverlay,
  },
];

export { registerDoubleTapStoryOverlay as registerDoubleTap3DOverlay } from './doubleTapOverlay';

export function registerAllAdvancedIndicators(): void {
  for (const item of ADVANCED_INDICATORS_REGISTRY) {
    item.registerFn();
  }
}
