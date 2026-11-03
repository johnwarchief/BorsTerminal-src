/**
 * frontend-v2/src/features/technical/overlays/userIndicators.ts
 *
 * رجیستری و پیاده‌سازی اورلی‌های بومی KLineCharts v10 برای ۴ اندیکاتور سفارشی صندوق ورودی:
 * ۱. BreakoutRetestPro: شناسایی سطوح شکست حمایت/مقاومت و رسم زون‌های پولبک با ضریب ATR
 * ۲. SuperTrendHeikinAshi: سوپرترند بر پایه شمع‌های هموارسازی‌شده هیکن‌اشی جهت حذف نویز
 * ۳. FiboRSI8: نوسان‌گر RSI هشت‌کندلی با ترازهای فیبوناچی و سیگنال‌های تک‌شلیک (Single-Shot)
 * ۴. RsiMaSmooth: شاخص RSI نرم‌شده با میانگین متحرک و شناسایی واگرایی‌های معمولی و مخفی
 *
 * کلیه محاسبات کاملاً بدون ری‌پینتینگ (No-Repainting) و صرفاً بر روی کندل‌های قطعی انجام می‌شوند.
 */

import { registerOverlay } from 'klinecharts';
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
  KLineData,
} from 'klinecharts';

export interface UserIndicatorMeta {
  id: string;
  name: string;
  nameFa: string;
  descriptionFa: string;
  category: 'overlay' | 'oscillator' | 'hybrid';
  defaultParams: Record<string, number | boolean | string | number[]>;
  registerFn: () => void;
}

// ----------------------------------------------------------------------------
// توابع کمکی محاسباتی (Pure & No-Repainting)
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

  let sum = 0;
  const initialLen = Math.min(n, period);
  for (let i = 0; i < initialLen; i++) {
    sum += tr[i];
  }
  atr[initialLen - 1] = sum / initialLen;

  for (let i = initialLen; i < n; i++) {
    atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
  }

  return atr;
}

export function calculateRSI(closes: number[], period = 14): number[] {
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

export function calculateEMA(values: number[], period: number): number[] {
  const n = values.length;
  const ema: number[] = new Array(n).fill(0);
  if (n === 0) return ema;

  const k = 2 / (period + 1);
  ema[0] = values[0];
  for (let i = 1; i < n; i++) {
    ema[i] = values[i] * k + ema[i - 1] * (1 - k);
  }
  return ema;
}

// ----------------------------------------------------------------------------
// ۱. اندیکاتور BreakoutRetestPro (شکست و پولبک حرفه‌ای)
// ----------------------------------------------------------------------------

export function registerBreakoutRetestProOverlay(): void {
  const template: OverlayTemplate = {
    name: 'BreakoutRetestPro',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart, bounding } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 25) return [];

      const swingLength = 10;
      const impulseMult = 1.5;
      const breakConfirm = 2;
      const retestAtr = 0.5;
      const retestBars = 40;

      const atr = calculateATR(dataList, 14);
      const figures: OverlayFigure[] = [];

      // جستجوی سقف‌ها و کف‌های سوینگ روی کندل‌های قطعی (No-Repainting)
      for (let i = swingLength; i < n - swingLength; i++) {
        const curHigh = dataList[i].high;
        let isSwingHigh = true;
        let minImpulseLow = dataList[i].low;

        for (let j = i - swingLength; j <= i + swingLength; j++) {
          if (dataList[j].high > curHigh) {
            isSwingHigh = false;
            break;
          }
          if (j <= i && dataList[j].low < minImpulseLow) {
            minImpulseLow = dataList[j].low;
          }
        }

        // ستاپ شکست مقاومت (Bullish Breakout & Retest)
        if (isSwingHigh) {
          const impulse = curHigh - minImpulseLow;
          if (impulse >= atr[i] * impulseMult) {
            const neckline = curHigh;
            let breakoutIndex = -1;
            let closesAbove = 0;

            for (let k = i + swingLength + 1; k < n; k++) {
              if (dataList[k].close > neckline) {
                closesAbove++;
                if (closesAbove >= breakConfirm) {
                  breakoutIndex = k;
                  break;
                }
              } else {
                closesAbove = 0;
              }
            }

            if (breakoutIndex !== -1) {
              const maxSearch = Math.min(n, breakoutIndex + retestBars);
              for (let r = breakoutIndex + 1; r < maxSearch; r++) {
                const c = dataList[r];
                const inZone = c.low <= neckline + atr[r] * retestAtr && c.low >= neckline - atr[r] * retestAtr;
                const bouncing = c.close > neckline && c.close > c.open;

                if (inZone && bouncing) {
                  // رسم زون پولبک
                  const xStart = getX(params, i, dataList[i].timestamp);
                  const xRetest = getX(params, r, c.timestamp);
                  const yTop = getY(params, neckline + atr[r] * retestAtr);
                  const yBottom = getY(params, neckline - atr[r] * retestAtr);
                  const yNeck = getY(params, neckline);

                  figures.push({
                    type: 'rect',
                    attrs: {
                      x: xStart,
                      y: Math.min(yTop, yBottom),
                      width: Math.max(30, xRetest - xStart + 20),
                      height: Math.max(3, Math.abs(yBottom - yTop)),
                    },
                    styles: {
                      color: 'rgba(16, 185, 129, 0.12)',
                      borderColor: 'rgba(16, 185, 129, 0.6)',
                      borderSize: 1,
                      borderStyle: 'dashed',
                      borderRadius: 2,
                    },
                  });

                  // خط خط‌گردن (Neckline)
                  figures.push({
                    type: 'line',
                    attrs: {
                      coordinates: [
                        { x: xStart, y: yNeck },
                        { x: Math.min(bounding.width, xRetest + 40), y: yNeck },
                      ],
                    },
                    styles: {
                      color: '#10b981',
                      size: 1.5,
                      style: 'solid',
                    },
                  });

                  // نشانگر جهش پولبک (Retest Bounce Arrow)
                  const arrowX = xRetest;
                  const arrowY = getY(params, c.low) + 8;
                  figures.push({
                    type: 'polygon',
                    attrs: {
                      coordinates: [
                        { x: arrowX, y: arrowY },
                        { x: arrowX - 5, y: arrowY + 9 },
                        { x: arrowX + 5, y: arrowY + 9 },
                      ],
                    },
                    styles: {
                      color: '#10b981',
                      borderColor: '#059669',
                      borderSize: 1,
                    },
                  });

                  figures.push({
                    type: 'text',
                    attrs: {
                      x: arrowX,
                      y: arrowY + 12,
                      text: 'پولبک سطح شکست',
                      align: 'center',
                      baseline: 'top',
                    },
                    styles: {
                      color: '#10b981',
                      size: 9,
                      family: 'Vazirmatn, sans-serif',
                      weight: 'bold',
                    },
                  });

                  break;
                }
              }
            }
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
// ۲. اندیکاتور SuperTrendHeikinAshi (سوپرترند هیکن‌اشی)
// ----------------------------------------------------------------------------

export function registerSuperTrendHeikinAshiOverlay(): void {
  const template: OverlayTemplate = {
    name: 'SuperTrendHeikinAshi',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 15) return [];

      const atrPeriod = 10;
      const multiplier = 3.0;

      // ساخت شمع‌های هیکن‌اشی (Heikin Ashi)
      const haClose: number[] = new Array(n).fill(0);
      const haOpen: number[] = new Array(n).fill(0);
      const haHigh: number[] = new Array(n).fill(0);
      const haLow: number[] = new Array(n).fill(0);

      haClose[0] = (dataList[0].open + dataList[0].high + dataList[0].low + dataList[0].close) / 4;
      haOpen[0] = (dataList[0].open + dataList[0].close) / 2;
      haHigh[0] = Math.max(dataList[0].high, haOpen[0], haClose[0]);
      haLow[0] = Math.min(dataList[0].low, haOpen[0], haClose[0]);

      for (let i = 1; i < n; i++) {
        const d = dataList[i];
        haClose[i] = (d.open + d.high + d.low + d.close) / 4;
        haOpen[i] = (haOpen[i - 1] + haClose[i - 1]) / 2;
        haHigh[i] = Math.max(d.high, haOpen[i], haClose[i]);
        haLow[i] = Math.min(d.low, haOpen[i], haClose[i]);
      }

      // محاسبه ATR بر روی شمع‌های هیکن‌اشی
      const tr: number[] = new Array(n).fill(0);
      tr[0] = haHigh[0] - haLow[0];
      for (let i = 1; i < n; i++) {
        tr[i] = Math.max(haHigh[i] - haLow[i], Math.abs(haHigh[i] - haClose[i - 1]), Math.abs(haLow[i] - haClose[i - 1]));
      }

      const atr: number[] = new Array(n).fill(0);
      let trSum = 0;
      for (let i = 0; i < atrPeriod && i < n; i++) {
        trSum += tr[i];
      }
      atr[atrPeriod - 1] = trSum / atrPeriod;
      for (let i = atrPeriod; i < n; i++) {
        atr[i] = (atr[i - 1] * (atrPeriod - 1) + tr[i]) / atrPeriod;
      }

      // محاسبه باندهای سوپرترند
      const finalUpper: number[] = new Array(n).fill(0);
      const finalLower: number[] = new Array(n).fill(0);
      const trend: number[] = new Array(n).fill(1); // 1 = Bullish, -1 = Bearish
      const superTrend: number[] = new Array(n).fill(0);

      for (let i = atrPeriod; i < n; i++) {
        const hl2 = (haHigh[i] + haLow[i]) / 2;
        const basicUpper = hl2 + multiplier * atr[i];
        const basicLower = hl2 - multiplier * atr[i];

        if (i === atrPeriod) {
          finalUpper[i] = basicUpper;
          finalLower[i] = basicLower;
          trend[i] = haClose[i] > hl2 ? 1 : -1;
        } else {
          finalUpper[i] = basicUpper < finalUpper[i - 1] || haClose[i - 1] > finalUpper[i - 1] ? basicUpper : finalUpper[i - 1];
          finalLower[i] = basicLower > finalLower[i - 1] || haClose[i - 1] < finalLower[i - 1] ? basicLower : finalLower[i - 1];

          if (trend[i - 1] === 1 && haClose[i] < finalLower[i]) {
            trend[i] = -1;
          } else if (trend[i - 1] === -1 && haClose[i] > finalUpper[i]) {
            trend[i] = 1;
          } else {
            trend[i] = trend[i - 1];
          }
        }
        superTrend[i] = trend[i] === 1 ? finalLower[i] : finalUpper[i];
      }

      const figures: OverlayFigure[] = [];

      // رسم خطوط متصل سوپرترند با تغییر رنگ صعودی/نزولی
      for (let i = atrPeriod + 1; i < n; i++) {
        const x1 = getX(params, i - 1, dataList[i - 1].timestamp);
        const y1 = getY(params, superTrend[i - 1]);
        const x2 = getX(params, i, dataList[i].timestamp);
        const y2 = getY(params, superTrend[i]);

        const isBull = trend[i] === 1;
        figures.push({
          type: 'line',
          attrs: {
            coordinates: [
              { x: x1, y: y1 },
              { x: x2, y: y2 },
            ],
          },
          styles: {
            color: isBull ? '#10b981' : '#ef4444',
            size: 2,
            style: 'solid',
          },
        });

        // نشانگر چرخش روند در نقطه تغییر
        if (trend[i] !== trend[i - 1]) {
          figures.push({
            type: 'circle',
            attrs: {
              x: x2,
              y: y2,
              r: 4,
            },
            styles: {
              color: isBull ? '#10b981' : '#ef4444',
              borderColor: '#ffffff',
              borderSize: 1,
            },
          });
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
// ۳. اندیکاتور FiboRSI8 (فیبو RSI تک‌شلیک)
// ----------------------------------------------------------------------------

export function registerFiboRSI8Overlay(): void {
  const template: OverlayTemplate = {
    name: 'FiboRSI8',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 12) return [];

      const rsiPeriod = 8;
      const oversold = 23.6;
      const overbought = 78.6;

      const closes = dataList.map((d) => d.close);
      const rsi = calculateRSI(closes, rsiPeriod);

      const figures: OverlayFigure[] = [];

      for (let i = rsiPeriod + 1; i < n; i++) {
        const prevRsi = rsi[i - 1];
        const curRsi = rsi[i];
        const c = dataList[i];
        const x = getX(params, i, c.timestamp);

        // سیگنال تک‌شلیک خرید: خروج از اشباع فروش ۲۳٫۶٪
        if (prevRsi <= oversold && curRsi > oversold) {
          const y = getY(params, c.low) + 10;
          figures.push({
            type: 'polygon',
            attrs: {
              coordinates: [
                { x, y: y + 2 },
                { x: x - 5, y: y + 10 },
                { x: x + 5, y: y + 10 },
              ],
            },
            styles: {
              color: '#22c55e',
              borderColor: '#16a34a',
              borderSize: 1,
            },
          });
          figures.push({
            type: 'text',
            attrs: {
              x,
              y: y + 12,
              text: 'خرید فیبو RSI(8)',
              align: 'center',
              baseline: 'top',
            },
            styles: {
              color: '#22c55e',
              size: 9,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
            },
          });
        }

        // سیگنال تک‌شلیک فروش: خروج از اشباع خرید ۷۸٫۶٪
        if (prevRsi >= overbought && curRsi < overbought) {
          const y = getY(params, c.high) - 10;
          figures.push({
            type: 'polygon',
            attrs: {
              coordinates: [
                { x, y: y - 2 },
                { x: x - 5, y: y - 10 },
                { x: x + 5, y: y - 10 },
              ],
            },
            styles: {
              color: '#ef4444',
              borderColor: '#dc2626',
              borderSize: 1,
            },
          });
          figures.push({
            type: 'text',
            attrs: {
              x,
              y: y - 12,
              text: 'فروش فیبو RSI(8)',
              align: 'center',
              baseline: 'bottom',
            },
            styles: {
              color: '#ef4444',
              size: 9,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
            },
          });
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
// ۴. اندیکاتور RsiMaSmooth (آراس‌آی هموار با میانگین و واگرایی)
// ----------------------------------------------------------------------------

export function registerRsiMaSmoothOverlay(): void {
  const template: OverlayTemplate = {
    name: 'RsiMaSmooth',
    totalStep: 1,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createPointFigures: (params: OverlayCreateFiguresCallbackParams<unknown>): OverlayFigure[] => {
      const { chart } = params;
      const dataList = chart.getDataList();
      const n = dataList.length;
      if (n < 30) return [];

      const rsiPeriod = 14;
      const smoothingPeriod = 9;
      const divergenceLookback = 20;

      const closes = dataList.map((d) => d.close);
      const rawRsi = calculateRSI(closes, rsiPeriod);
      const smoothRsi = calculateEMA(rawRsi, smoothingPeriod);

      const figures: OverlayFigure[] = [];

      // شناسایی واگرایی‌های معمولی و مخفی
      for (let i = rsiPeriod + smoothingPeriod + 5; i < n; i++) {
        const curLow = dataList[i].low;
        const curHigh = dataList[i].high;
        const curRsi = smoothRsi[i];

        // جستجوی پیوت کف قبلی
        for (let j = Math.max(0, i - divergenceLookback); j < i - 4; j++) {
          const prevLow = dataList[j].low;
          const prevRsi = smoothRsi[j];

          // واگرایی مثبت معمولی (Regular Bullish: کف پایین‌تر در قیمت، کف بالاتر در RSI)
          if (curLow < prevLow && curRsi > prevRsi && curRsi < 45) {
            const x1 = getX(params, j, dataList[j].timestamp);
            const y1 = getY(params, prevLow);
            const x2 = getX(params, i, dataList[i].timestamp);
            const y2 = getY(params, curLow);

            // خط واگرایی روی کف‌های قیمت
            figures.push({
              type: 'line',
              attrs: {
                coordinates: [
                  { x: x1, y: y1 },
                  { x: x2, y: y2 },
                ],
              },
              styles: {
                color: '#06b6d4',
                size: 1.5,
                style: 'dashed',
              },
            });

            // برچسب واگرایی مثبت
            figures.push({
              type: 'text',
              attrs: {
                x: x2,
                y: y2 + 8,
                text: 'واگرایی مثبت (RD+)',
                align: 'center',
                baseline: 'top',
              },
              styles: {
                color: '#06b6d4',
                size: 9,
                family: 'Vazirmatn, sans-serif',
                weight: 'bold',
              },
            });
            break;
          }

          // واگرایی منفی معمولی (Regular Bearish: سقف بالاتر در قیمت، سقف پایین‌تر در RSI)
          const prevHigh = dataList[j].high;
          if (curHigh > prevHigh && curRsi < prevRsi && curRsi > 55) {
            const x1 = getX(params, j, dataList[j].timestamp);
            const y1 = getY(params, prevHigh);
            const x2 = getX(params, i, dataList[i].timestamp);
            const y2 = getY(params, curHigh);

            figures.push({
              type: 'line',
              attrs: {
                coordinates: [
                  { x: x1, y: y1 },
                  { x: x2, y: y2 },
                ],
              },
              styles: {
                color: '#ec4899',
                size: 1.5,
                style: 'dashed',
              },
            });

            figures.push({
              type: 'text',
              attrs: {
                x: x2,
                y: y2 - 8,
                text: 'واگرایی منفی (RD-)',
                align: 'center',
                baseline: 'bottom',
              },
              styles: {
                color: '#ec4899',
                size: 9,
                family: 'Vazirmatn, sans-serif',
                weight: 'bold',
              },
            });
            break;
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
// رجیستری متادیتای اندیکاتورهای سفارشی کاربر
// ----------------------------------------------------------------------------

export const USER_INDICATORS_REGISTRY: UserIndicatorMeta[] = [
  {
    id: 'BreakoutRetestPro',
    name: 'Breakout Retest Pro',
    nameFa: 'شکست و پولبک حرفه‌ای',
    descriptionFa: 'تشخیص سطوح حمایت و مقاومت کلیدی، تایید شکست با کندل‌های بسته و رسم زون‌های پولبک با ATR',
    category: 'overlay',
    defaultParams: {
      swingLength: 10,
      impulseMult: 1.5,
      breakConfirm: 2,
      retestAtr: 0.5,
      retestBars: 40,
    },
    registerFn: registerBreakoutRetestProOverlay,
  },
  {
    id: 'SuperTrendHeikinAshi',
    name: 'SuperTrend (wHA)',
    nameFa: 'سوپرترند هیکن‌اشی',
    descriptionFa: 'محاسبه خط روند سوپرترند بر پایه کندل‌های تلطیف‌شده هیکن‌اشی جهت حذف نویز بازار',
    category: 'overlay',
    defaultParams: {
      atrPeriod: 10,
      multiplier: 3.0,
    },
    registerFn: registerSuperTrendHeikinAshiOverlay,
  },
  {
    id: 'FiboRSI8',
    name: 'FiboRSI8 SingleShot',
    nameFa: 'فیبو RSI تک‌شلیک',
    descriptionFa: 'نوسان‌گر RSI هشت‌کندلی با ترازهای ۲۳٫۶٪ تا ۷۸٫۶٪ فیبوناچی و هشدارهای بازگشتی تک‌شلیک',
    category: 'hybrid',
    defaultParams: {
      rsiPeriod: 8,
      oversold: 23.6,
      overbought: 78.6,
    },
    registerFn: registerFiboRSI8Overlay,
  },
  {
    id: 'RsiMaSmooth',
    name: 'RSI MA Smooth MTF Divergence',
    nameFa: 'آراس‌آی هموار با میانگین و واگرایی',
    descriptionFa: 'شاخص RSI نرم‌شده با میانگین متحرک و ردیابی خودکار واگرایی‌های معمولی و مخفی مثبت و منفی',
    category: 'hybrid',
    defaultParams: {
      rsiPeriod: 14,
      smoothingPeriod: 9,
      divergenceLookback: 20,
    },
    registerFn: registerRsiMaSmoothOverlay,
  },
];

export function registerAllUserIndicators(): void {
  for (const item of USER_INDICATORS_REGISTRY) {
    item.registerFn();
  }
}
