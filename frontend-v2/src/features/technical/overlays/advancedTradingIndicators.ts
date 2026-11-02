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
import type {
  OverlayTemplate,
  OverlayFigure,
  OverlayCreateFiguresCallbackParams,
  KLineData,
} from 'klinecharts';
import { toFaDigits } from '@shared/lib/fa';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import type {
  DoubleTapPattern,
  PullbackSignal,
  CHoCHSignal,
} from '../model/types';

function getIsLight(): boolean {
  try {
    const t = useUiStore.getState().theme;
    return t === 'warm' || t === 'cool';
  } catch {
    return false;
  }
}

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

export function registerDoubleTap3DOverlay(): void {
  const template: OverlayTemplate = {
    name: 'DoubleTap3D',
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
      const pivLeft = 3;
      const pivRight = 2;
      const tolAtr = 0.95;
      const minSpan = 3;
      const maxSpan = 120;
      const minHeightAtr = 0.8;

      const atr = calculateATR(dataList, 14);
      const figures: OverlayFigure[] = [];
      const detectedPatterns: DoubleTapPattern[] = [];

      // شناسایی پیوت‌های سقف و کف
      const isPivotHigh = (idx: number): boolean => {
        const h = dataList[idx].high;
        for (let j = Math.max(0, idx - pivLeft); j <= Math.min(n - 1, idx + pivRight); j++) {
          if (j !== idx && dataList[j].high > h) return false;
        }
        return true;
      };

      const isPivotLow = (idx: number): boolean => {
        const l = dataList[idx].low;
        for (let j = Math.max(0, idx - pivLeft); j <= Math.min(n - 1, idx + pivRight); j++) {
          if (j !== idx && dataList[j].low < l) return false;
        }
        return true;
      };

      const pivotHighs: Array<{ index: number; price: number; timestamp: number }> = [];
      const pivotLows: Array<{ index: number; price: number; timestamp: number }> = [];

      for (let i = pivLeft; i < n - pivRight; i++) {
        if (isPivotHigh(i)) {
          pivotHighs.push({ index: i, price: dataList[i].high, timestamp: dataList[i].timestamp });
        }
        if (isPivotLow(i)) {
          pivotLows.push({ index: i, price: dataList[i].low, timestamp: dataList[i].timestamp });
        }
      }

      // الف) ستاپ سقف دوقلو M (Double Top)
      for (let p = 0; p < pivotHighs.length - 1; p++) {
        const p1 = pivotHighs[p];
        const p2 = pivotHighs[p + 1];
        const span = p2.index - p1.index;

        if (span >= minSpan && span <= maxSpan) {
          const currentAtr = atr[p2.index] || 1;
          const diff = Math.abs(p1.price - p2.price);

          if (diff <= tolAtr * currentAtr) {
            // پیدا کردن کف میان دو سقف به عنوان خط گردن (Neckline)
            let neckLow = Infinity;
            let neckIdx = -1;
            let neckTs = p1.timestamp;

            for (let k = p1.index + 1; k < p2.index; k++) {
              if (dataList[k].low < neckLow) {
                neckLow = dataList[k].low;
                neckIdx = k;
                neckTs = dataList[k].timestamp;
              }
            }

            const patternHeight = Math.max(p1.price, p2.price) - neckLow;
            if (patternHeight >= minHeightAtr * currentAtr && neckIdx !== -1) {
              const tp1 = neckLow - patternHeight;
              const tp2 = neckLow - 1.618 * patternHeight;
              const stopLoss = Math.max(p1.price, p2.price) + 0.25 * currentAtr;
              const score = Math.min(95, Math.round(70 + (1 - diff / (tolAtr * currentAtr)) * 25));

              const x1 = getX(params, p1.index, p1.timestamp);
              const y1 = getY(params, p1.price);
              const xNeck = getX(params, neckIdx, neckTs);
              const yNeck = getY(params, neckLow);
              const x2 = getX(params, p2.index, p2.timestamp);
              const y2 = getY(params, p2.price);

              // بررسی شکست خط گردن
              let breakoutIdx = -1;
              for (let b = p2.index + 1; b < n; b++) {
                if (dataList[b].close < neckLow) {
                  breakoutIdx = b;
                  break;
                }
              }

              // پیدا کردن کف قبل از قله اول به عنوان نقطه آغاز حرکت تکانه‌ای (P0)
              let p0Low = Infinity;
              let p0Idx = -1;
              let p0Ts = p1.timestamp;
              const p0Start = Math.max(0, p1.index - span);
              for (let k = p0Start; k < p1.index; k++) {
                if (dataList[k].low < p0Low) {
                  p0Low = dataList[k].low;
                  p0Idx = k;
                  p0Ts = dataList[k].timestamp;
                }
              }
              if (p0Idx === -1 || p0Low === Infinity) {
                p0Idx = p0Start;
                p0Low = neckLow;
                p0Ts = dataList[p0Idx]?.timestamp ?? p1.timestamp;
              }

              // نقطه بازآزمایی و شکست بعد از قله دوم (P3)
              const p3Idx = breakoutIdx !== -1 ? breakoutIdx : Math.min(n - 1, p2.index + Math.max(1, Math.round(span / 2)));
              const p3Price = breakoutIdx !== -1 ? neckLow : (p2.price + neckLow) / 2;
              const p3Ts = dataList[p3Idx]?.timestamp ?? p2.timestamp;

              const p0Obj = { index: p0Idx, price: p0Low, timestamp: p0Ts };
              const p3Obj = { index: p3Idx, price: p3Price, timestamp: p3Ts };
              const x0 = getX(params, p0Idx, p0Ts);
              const y0 = getY(params, p0Low);
              const x3 = getX(params, p3Idx, p3Ts);
              const y3 = getY(params, p3Price);

              const patternStatus = breakoutIdx !== -1 ? 'active' : 'forming';
              detectedPatterns.push({
                id: `double-top-${p1.index}`,
                type: 'DOUBLE_TOP',
                origin: p0Obj,
                peak1: p1,
                neckline: { index: neckIdx, price: neckLow, timestamp: neckTs },
                peak2: p2,
                retest: p3Obj,
                breakoutIndex: breakoutIdx !== -1 ? breakoutIdx : undefined,
                target1: tp1,
                target2: tp2,
                stopLoss,
                score,
                height: patternHeight,
                status: patternStatus,
              });

              // ۱. ساقه‌های ۵ نقطه‌ای سه‌بعدی و سایه‌دار الگوی کامل M (P0 -> P1 -> Neck -> P2 -> P3)
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x0, y: y0 },
                    { x: x1, y: y1 },
                    { x: xNeck, y: yNeck },
                    { x: x2, y: y2 },
                    { x: x3, y: y3 },
                  ],
                },
                styles: {
                  color: isLight ? '#be123c' : '#ff2079',
                  size: 2.5,
                  style: 'solid',
                },
              });

              // سایه سه‌بعدی پایه‌ها (3D Extrusion)
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x0 + 3, y: y0 + 3 },
                    { x: x1 + 3, y: y1 + 3 },
                    { x: xNeck + 3, y: yNeck + 3 },
                    { x: x2 + 3, y: y2 + 3 },
                    { x: x3 + 3, y: y3 + 3 },
                  ],
                },
                styles: {
                  color: isLight ? 'rgba(190, 18, 60, 0.20)' : 'rgba(255, 32, 121, 0.35)',
                  size: 1.5,
                  style: 'solid',
                },
              });

              // ۲. خط‌گردن افقی کامل با رنگ درخشان
              const xStart = Math.min(x0, x1);
              const xEnd = Math.min(bounding.width, Math.max(x2 + 80, x3 + 40, xNeck + 120));

              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: xStart, y: yNeck },
                    { x: xEnd, y: yNeck },
                  ],
                },
                styles: {
                  color: isLight ? '#7c3aed' : '#bc13fe',
                  size: 1.8,
                  style: 'dashed',
                  dashedValue: [5, 3],
                },
              });

              // برچسب خط‌گردن و الگوی سقف دوقلو
              figures.push({
                type: 'text',
                attrs: {
                  x: x2,
                  y: y2 - 10,
                  text: `سقف دوقلو M (${toFaDigits(score)}٪)`,
                  align: 'center',
                  baseline: 'bottom',
                },
                styles: {
                  color: isLight ? '#9f1239' : '#ff2079',
                  size: 9,
                  family: 'Vazirmatn, sans-serif',
                  weight: 'bold',
                },
              });

              // ۳. خطوط حد سود TP1 و حد ضرر SL
              const yTp1 = getY(params, tp1);
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x2, y: yTp1 },
                    { x: xEnd, y: yTp1 },
                  ],
                },
                styles: {
                  color: isLight ? '#047857' : '#39ff14',
                  size: 1,
                  style: 'dashed',
                  dashedValue: [3, 3],
                },
              });

              figures.push({
                type: 'text',
                attrs: {
                  x: xEnd,
                  y: yTp1 - 4,
                  text: `هدف TP1: ${toFaDigits(Math.round(tp1))}`,
                  align: 'right',
                  baseline: 'bottom',
                },
                styles: {
                  color: isLight ? '#047857' : '#39ff14',
                  size: 8,
                  family: 'Vazirmatn, sans-serif',
                },
              });
            }
          }
        }
      }

      // ب) ستاپ کف دوقلو W (Double Bottom)
      for (let p = 0; p < pivotLows.length - 1; p++) {
        const t1 = pivotLows[p];
        const t2 = pivotLows[p + 1];
        const span = t2.index - t1.index;

        if (span >= minSpan && span <= maxSpan) {
          const currentAtr = atr[t2.index] || 1;
          const diff = Math.abs(t1.price - t2.price);

          if (diff <= tolAtr * currentAtr) {
            let neckHigh = -Infinity;
            let neckIdx = -1;
            let neckTs = t1.timestamp;

            for (let k = t1.index + 1; k < t2.index; k++) {
              if (dataList[k].high > neckHigh) {
                neckHigh = dataList[k].high;
                neckIdx = k;
                neckTs = dataList[k].timestamp;
              }
            }

            const patternHeight = neckHigh - Math.min(t1.price, t2.price);
            if (patternHeight >= minHeightAtr * currentAtr && neckIdx !== -1) {
              const tp1 = neckHigh + patternHeight;
              const tp2 = neckHigh + 1.618 * patternHeight;
              const stopLoss = Math.min(t1.price, t2.price) - 0.25 * currentAtr;
              const score = Math.min(95, Math.round(70 + (1 - diff / (tolAtr * currentAtr)) * 25));

              const x1 = getX(params, t1.index, t1.timestamp);
              const y1 = getY(params, t1.price);
              const xNeck = getX(params, neckIdx, neckTs);
              const yNeck = getY(params, neckHigh);
              const x2 = getX(params, t2.index, t2.timestamp);
              const y2 = getY(params, t2.price);

              let breakoutIdx = -1;
              for (let b = t2.index + 1; b < n; b++) {
                if (dataList[b].close > neckHigh) {
                  breakoutIdx = b;
                  break;
                }
              }

              // پیدا کردن سقف قبل از کف اول به عنوان نقطه آغاز حرکت ریزشی (T0)
              let t0High = -Infinity;
              let t0Idx = -1;
              let t0Ts = t1.timestamp;
              const t0Start = Math.max(0, t1.index - span);
              for (let k = t0Start; k < t1.index; k++) {
                if (dataList[k].high > t0High) {
                  t0High = dataList[k].high;
                  t0Idx = k;
                  t0Ts = dataList[k].timestamp;
                }
              }
              if (t0Idx === -1 || t0High === -Infinity) {
                t0Idx = t0Start;
                t0High = neckHigh;
                t0Ts = dataList[t0Idx]?.timestamp ?? t1.timestamp;
              }

              // نقطه بازآزمایی و شکست بعد از کف دوم (T3)
              const t3Idx = breakoutIdx !== -1 ? breakoutIdx : Math.min(n - 1, t2.index + Math.max(1, Math.round(span / 2)));
              const t3Price = breakoutIdx !== -1 ? neckHigh : (t2.price + neckHigh) / 2;
              const t3Ts = dataList[t3Idx]?.timestamp ?? t2.timestamp;

              const t0Obj = { index: t0Idx, price: t0High, timestamp: t0Ts };
              const t3Obj = { index: t3Idx, price: t3Price, timestamp: t3Ts };
              const x0 = getX(params, t0Idx, t0Ts);
              const y0 = getY(params, t0High);
              const x3 = getX(params, t3Idx, t3Ts);
              const y3 = getY(params, t3Price);

              const patternStatus = breakoutIdx !== -1 ? 'active' : 'forming';
              detectedPatterns.push({
                id: `double-bottom-${t1.index}`,
                type: 'DOUBLE_BOTTOM',
                origin: t0Obj,
                peak1: t1,
                neckline: { index: neckIdx, price: neckHigh, timestamp: neckTs },
                peak2: t2,
                retest: t3Obj,
                breakoutIndex: breakoutIdx !== -1 ? breakoutIdx : undefined,
                target1: tp1,
                target2: tp2,
                stopLoss,
                score,
                height: patternHeight,
                status: patternStatus,
              });

              // ۱. ساقه‌های ۵ نقطه‌ای سه‌بعدی و سایه‌دار الگوی کامل W (T0 -> T1 -> Neck -> T2 -> T3)
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x0, y: y0 },
                    { x: x1, y: y1 },
                    { x: xNeck, y: yNeck },
                    { x: x2, y: y2 },
                    { x: x3, y: y3 },
                  ],
                },
                styles: {
                  color: isLight ? '#0284c7' : '#00f0ff',
                  size: 2.5,
                  style: 'solid',
                },
              });

              // سایه سه‌بعدی پایه‌ها
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x0 + 3, y: y0 + 3 },
                    { x: x1 + 3, y: y1 + 3 },
                    { x: xNeck + 3, y: yNeck + 3 },
                    { x: x2 + 3, y: y2 + 3 },
                    { x: x3 + 3, y: y3 + 3 },
                  ],
                },
                styles: {
                  color: isLight ? 'rgba(2, 132, 199, 0.20)' : 'rgba(0, 240, 255, 0.35)',
                  size: 1.5,
                  style: 'solid',
                },
              });

              const xStart = Math.min(x0, x1);
              const xEnd = Math.min(bounding.width, Math.max(x2 + 80, x3 + 40, xNeck + 120));

              // خط‌گردن درخشان بنفش
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: xStart, y: yNeck },
                    { x: xEnd, y: yNeck },
                  ],
                },
                styles: {
                  color: isLight ? '#7c3aed' : '#bc13fe',
                  size: 1.8,
                  style: 'dashed',
                  dashedValue: [5, 3],
                },
              });

              // برچسب کف دوقلو W
              figures.push({
                type: 'text',
                attrs: {
                  x: x2,
                  y: y2 + 10,
                  text: `کف دوقلو W (${toFaDigits(score)}٪)`,
                  align: 'center',
                  baseline: 'top',
                },
                styles: {
                  color: isLight ? '#0369a1' : '#00f0ff',
                  size: 9,
                  family: 'Vazirmatn, sans-serif',
                  weight: 'bold',
                },
              });

              // تارگت TP1
              const yTp1 = getY(params, tp1);
              figures.push({
                type: 'line',
                attrs: {
                  coordinates: [
                    { x: x2, y: yTp1 },
                    { x: xEnd, y: yTp1 },
                  ],
                },
                styles: {
                  color: isLight ? '#047857' : '#39ff14',
                  size: 1,
                  style: 'dashed',
                  dashedValue: [3, 3],
                },
              });

              figures.push({
                type: 'text',
                attrs: {
                  x: xEnd,
                  y: yTp1 + 4,
                  text: `هدف TP1: ${toFaDigits(Math.round(tp1))}`,
                  align: 'right',
                  baseline: 'top',
                },
                styles: {
                  color: isLight ? '#047857' : '#39ff14',
                  size: 8,
                  family: 'Vazirmatn, sans-serif',
                },
              });
            }
          }
        }
      }

      // به‌روزرسانی الگوهای شناسایی‌شده در استور جهت نمایش در سایدبار اسکنر با بررسی تغییرات
      const prevPatterns = useTechnicalStore.getState().detectedDoubleTapPatterns;
      const patternsChanged =
        prevPatterns.length !== detectedPatterns.length ||
        prevPatterns.some(
          (p, i) =>
            p.id !== detectedPatterns[i]?.id ||
            p.status !== detectedPatterns[i]?.status ||
            p.score !== detectedPatterns[i]?.score
        );
      if (patternsChanged) {
        useTechnicalStore.getState().setDetectedDoubleTapPatterns(detectedPatterns);
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
      const atrPeriod = 10;
      const multiplier = 3.0;
      const pullbackAtr = 1.0;

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
      const swingLeft = 2;
      const swingRight = 2;
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
    defaultParams: {
      pivLeft: 6,
      pivRight: 4,
      tolAtr: 0.85,
      minHeightAtr: 1.0,
    },
    registerFn: registerDoubleTap3DOverlay,
  },
  {
    id: 'SuperTrendPullback',
    name: 'Super Trend Pullback Signals',
    nameFa: 'سیگنال‌های پولبک سوپرترند',
    descriptionFa: 'سیگنال‌های ادامه روند و ورود در پولبک با زون ارزش دینامیک و فیلتر کیفیت نوسان ATR',
    category: 'overlay',
    isDefault: true,
    defaultParams: {
      atrPeriod: 10,
      multiplier: 3.0,
      pullbackAtr: 1.0,
    },
    registerFn: registerSuperTrendPullbackOverlay,
  },
  {
    id: 'AutoTrendlineCHoCH',
    name: 'Auto Trend Line Intelligence [BOS+CHoCH+FVG]',
    nameFa: 'خط روند هوشمند و CHoCH / BOS',
    descriptionFa: 'ترسیم خودکار خطوط روند حمایت و مقاومت به همراه شناسایی تغییر ماهیت ساختار بازار (CHoCH)',
    category: 'overlay',
    isDefault: true,
    defaultParams: {
      swingLeft: 5,
      swingRight: 3,
    },
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

export function registerAllAdvancedIndicators(): void {
  for (const item of ADVANCED_INDICATORS_REGISTRY) {
    item.registerFn();
  }
}
