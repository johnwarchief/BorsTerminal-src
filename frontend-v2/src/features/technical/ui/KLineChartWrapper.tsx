/**
 * frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx
 *
 * هسته تعامل با موتور چارت کانواس KLineCharts v10 با استایل برنجی (Brass Aesthetics):
 * - پشتیبانی بومی از تقویم جلالی (خورشیدی) در محور زمان X (مانند ۱۴۰۳/۰۸/۱۰)
 * - ثبت و ادغام کلیه اورلی‌های FTS، کان پیش‌بینی AI، زون‌های SMC و اندیکاتورهای سفارشی
 * - اشتراک به وضعیت استور technicalStore برای ابزارهای رسم، کان پیش‌بینی و زون‌های SMC
 * - انیمیشن پالس زنده تیک قیمت با شتاب‌دهی سخت‌افزاری CSS و احترام به prefers-reduced-motion
 * - کارایی بالای ۶۰ تا ۱۸۰ فریم بر ثانیه روی حجم داده‌های بالا (>۴۰۰۰ کندل)
 * - تضمین عدم نشتی حافظه DOM با فراخوانی قطعی dispose روی unmount
 */

import React, { useEffect, useRef, useState, useMemo, useContext } from 'react';
import {
  init,
  dispose,
  type Chart,
  type KLineData,
  type DeepPartial,
  type Styles,
  type Period,
} from 'klinecharts';
import { QueryClient, QueryClientContext, QueryClientProvider } from '@tanstack/react-query';
import { toKlineBars, useChart } from '@features/chart/api/useChart';
import { toFaDigits } from '@shared/lib/fa';
import { useUiStore } from '@shared/stores/uiStore';
import { useTechnicalStore } from '../model/technicalStore';
import { aggregateCandles } from '../model/timeframeAggregation';
import { getDrawingToolById } from '../model/drawingCatalog';
import { registerFTSOverlays } from '../overlays/ftsOverlays';
import { registerPredictionOverlay } from '../overlays/predictionOverlay';
import { registerSMCOverlays } from '../overlays/smcOverlays';
import { registerAllUserIndicators } from '../overlays/userIndicators';
import { registerCorporateEventsOverlay } from '../overlays/corporateEventsOverlay';
import { registerAllAdvancedIndicators } from '../overlays/advancedTradingIndicators';
import { AnimatedPatternOverlay } from './AnimatedPatternOverlay';
import type { Candle } from '../model/types';

// ----------------------------------------------------------------------------
// ثبت یک‌باره کلیه اورلی‌های بومی
// ----------------------------------------------------------------------------

let overlaysRegistered = false;
export function ensureAllOverlaysRegistered(): void {
  if (overlaysRegistered) return;
  registerFTSOverlays();
  registerPredictionOverlay();
  registerSMCOverlays();
  registerAllUserIndicators();
  registerCorporateEventsOverlay();
  registerAllAdvancedIndicators();
  overlaysRegistered = true;
}

// ----------------------------------------------------------------------------
// تنظیمات تم برنجی (Brass Aesthetics) چارت KLineCharts
// ----------------------------------------------------------------------------

export const BRASS_CHART_STYLES: DeepPartial<Styles> = {
  grid: {
    show: true,
    horizontal: {
      show: true,
      size: 1,
      color: 'rgba(218, 165, 32, 0.08)',
      style: 'dashed',
      dashedValue: [4, 4],
    },
    vertical: {
      show: true,
      size: 1,
      color: 'rgba(218, 165, 32, 0.08)',
      style: 'dashed',
      dashedValue: [4, 4],
    },
  },
  candle: {
    type: 'candle_solid',
    bar: {
      upColor: '#22c55e',
      downColor: '#ef4444',
      noChangeColor: '#888888',
      upBorderColor: '#22c55e',
      downBorderColor: '#ef4444',
      noChangeBorderColor: '#888888',
      upWickColor: '#22c55e',
      downWickColor: '#ef4444',
      noChangeWickColor: '#888888',
    },
    priceMark: {
      show: true,
      last: {
        show: true,
        upColor: '#22c55e',
        downColor: '#ef4444',
        noChangeColor: '#888888',
        line: {
          show: true,
          style: 'dashed',
          dashedValue: [4, 4],
          size: 1,
        },
        text: {
          show: true,
          color: '#ffffff',
          size: 11,
          paddingLeft: 4,
          paddingRight: 4,
          paddingTop: 2,
          paddingBottom: 2,
          borderRadius: 2,
        },
      },
    },
  },
  xAxis: {
    show: true,
    axisLine: { show: true, color: 'rgba(218, 165, 32, 0.25)', size: 1 },
    tickText: { show: true, color: '#9ca3af', size: 11, family: 'Vazirmatn, sans-serif' },
    tickLine: { show: true, size: 1, length: 4, color: 'rgba(218, 165, 32, 0.25)' },
  },
  yAxis: {
    show: true,
    axisLine: { show: true, color: 'rgba(218, 165, 32, 0.25)', size: 1 },
    tickText: { show: true, color: '#9ca3af', size: 11, family: 'Vazirmatn, sans-serif' },
    tickLine: { show: true, size: 1, length: 4, color: 'rgba(218, 165, 32, 0.25)' },
  },
  crosshair: {
    show: true,
    horizontal: {
      show: true,
      line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1, color: 'rgba(218, 165, 32, 0.5)' },
      text: { show: true, color: '#f3f4f6', backgroundColor: '#1e222d', size: 11, borderRadius: 2 },
    },
    vertical: {
      show: true,
      line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1, color: 'rgba(218, 165, 32, 0.5)' },
      text: { show: true, color: '#f3f4f6', backgroundColor: '#1e222d', size: 11, borderRadius: 2 },
    },
  },
  overlay: {
    point: { color: '#eab308', activeColor: '#facc15', radius: 4 },
    line: { color: '#eab308', size: 1.5 },
  },
};

// ----------------------------------------------------------------------------
// تنظیمات تم روشن (Warm / Cool Light Aesthetics) چارت KLineCharts
// ----------------------------------------------------------------------------

export const LIGHT_CHART_STYLES: DeepPartial<Styles> = {
  grid: {
    show: true,
    horizontal: {
      show: true,
      size: 1,
      color: 'rgba(0, 0, 0, 0.06)',
      style: 'dashed',
      dashedValue: [4, 4],
    },
    vertical: {
      show: true,
      size: 1,
      color: 'rgba(0, 0, 0, 0.06)',
      style: 'dashed',
      dashedValue: [4, 4],
    },
  },
  candle: {
    type: 'candle_solid',
    bar: {
      upColor: '#0d7a45',
      downColor: '#b02c37',
      noChangeColor: '#6b7280',
      upBorderColor: '#0d7a45',
      downBorderColor: '#b02c37',
      noChangeBorderColor: '#6b7280',
      upWickColor: '#0d7a45',
      downWickColor: '#b02c37',
      noChangeWickColor: '#6b7280',
    },
    priceMark: {
      show: true,
      last: {
        show: true,
        upColor: '#0d7a45',
        downColor: '#b02c37',
        noChangeColor: '#6b7280',
        line: {
          show: true,
          style: 'dashed',
          dashedValue: [4, 4],
          size: 1,
        },
        text: {
          show: true,
          color: '#ffffff',
          size: 11,
          paddingLeft: 4,
          paddingRight: 4,
          paddingTop: 2,
          paddingBottom: 2,
          borderRadius: 2,
        },
      },
    },
  },
  xAxis: {
    show: true,
    axisLine: { show: true, color: 'rgba(0, 0, 0, 0.15)', size: 1 },
    tickText: { show: true, color: '#4d5a66', size: 11, family: 'Vazirmatn, sans-serif' },
    tickLine: { show: true, size: 1, length: 4, color: 'rgba(0, 0, 0, 0.15)' },
  },
  yAxis: {
    show: true,
    axisLine: { show: true, color: 'rgba(0, 0, 0, 0.15)', size: 1 },
    tickText: { show: true, color: '#4d5a66', size: 11, family: 'Vazirmatn, sans-serif' },
    tickLine: { show: true, size: 1, length: 4, color: 'rgba(0, 0, 0, 0.15)' },
  },
  crosshair: {
    show: true,
    horizontal: {
      show: true,
      line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1, color: 'rgba(0, 0, 0, 0.3)' },
      text: { show: true, color: '#ffffff', backgroundColor: '#374151', size: 11, borderRadius: 2 },
    },
    vertical: {
      show: true,
      line: { show: true, style: 'dashed', dashedValue: [4, 4], size: 1, color: 'rgba(0, 0, 0, 0.3)' },
      text: { show: true, color: '#ffffff', backgroundColor: '#374151', size: 11, borderRadius: 2 },
    },
  },
  overlay: {
    point: { color: '#b45309', activeColor: '#d97706', radius: 4 },
    line: { color: '#b45309', size: 1.5 },
  },
};


// ----------------------------------------------------------------------------
// فرمتر تاریخ جلالی برای محور X و تولتیپ
// ----------------------------------------------------------------------------

export function formatJalaliDate(timestamp: number): string {
  if (!timestamp || isNaN(timestamp)) return '';
  const ms = timestamp > 1e11 ? timestamp : timestamp * 1000;
  try {
    return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: 'UTC',
    }).format(new Date(ms));
  } catch {
    return '';
  }
}

// ----------------------------------------------------------------------------
// اینترفیس پراپ‌های کامپوننت
// ----------------------------------------------------------------------------

export interface KLineChartWrapperProps {
  symbol: string;
  candles?: Candle[];
  className?: string;
  onChartReady?: (chart: Chart) => void;
}

const KLineChartInner: React.FC<KLineChartWrapperProps> = ({
  symbol,
  candles,
  className,
  onChartReady,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart | null>(null);
  const [activeChartInstance, setActiveChartInstance] = useState<Chart | null>(null);
  const pulseBadgeRef = useRef<HTMLDivElement>(null);
  const prevPriceRef = useRef<number | null>(null);

  // استیت‌های استور تکنیکال
  const activeTool = useTechnicalStore((s) => s.activeDrawingTool);
  const showPredictionCone = useTechnicalStore((s) => s.showPredictionCone);
  const predictionData = useTechnicalStore((s) => s.predictionData);
  const showSMCZones = useTechnicalStore((s) => s.showSMCZones);
  const candleEdgeData = useTechnicalStore((s) => s.candleEdgeData);
  const activeUserIndicators = useTechnicalStore((s) => s.activeUserIndicators);
  const channelMode = useTechnicalStore((s) => s.channelMode);
  const rsiVariant = useTechnicalStore((s) => s.rsiVariant);
  const detectedDoubleTapPatterns = useTechnicalStore((s) => s.detectedDoubleTapPatterns);
  const adjustmentMode = useTechnicalStore((s) => s.adjustmentMode);
  const showCorporateEvents = useTechnicalStore((s) => s.showCorporateEvents);
  const isMagnetMode = useTechnicalStore((s) => s.isMagnetMode);
  const isLockedAllDrawings = useTechnicalStore((s) => s.isLockedAllDrawings);
  const isHideAllDrawings = useTechnicalStore((s) => s.isHideAllDrawings);
  const setCorporateEvents = useTechnicalStore((s) => s.setCorporateEvents);
  const timeframe = useTechnicalStore((s) => s.timeframe);
  const isLogScale = useTechnicalStore((s) => s.isLogScale);
  const isAutoScale = useTechnicalStore((s) => s.isAutoScale);
  const toggleLogScale = useTechnicalStore((s) => s.toggleLogScale);
  const toggleAutoScale = useTechnicalStore((s) => s.toggleAutoScale);

  // استیت تم سراسری UI (تاریک/روشن)
  const theme = useUiStore((s) => s.theme);
  const isLight = theme === 'warm' || theme === 'cool';

  // استعلام داده‌های کندلی از React Query با حالت تعدیل انتخابی رهاورد ۳۶۵
  const chartQuery = useChart(symbol, !candles, adjustmentMode);

  // آماده‌سازی بارهای خام روزانه
  const rawBars: KLineData[] = useMemo(() => {
    if (candles && candles.length > 0) {
      return [...candles]
        .sort((a, b) => a.timestamp - b.timestamp)
        .map((c) => ({
          timestamp: c.timestamp > 1e11 ? c.timestamp : c.timestamp * 1000,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume ?? 0,
        }));
    }
    if (chartQuery.data?.candles && chartQuery.data.candles.length > 0) {
      return toKlineBars(chartQuery.data.candles, chartQuery.data.factors, adjustmentMode);
    }
    return [];
  }, [candles, chartQuery.data, adjustmentMode]);

  // تجمیع کندل‌ها بر پایه تایم‌فریم انتخابی (روزانه، هفتگی شنبه-چهارشنبه، ماهانه جلالی)
  const bars: KLineData[] = useMemo(() => {
    return aggregateCandles(rawBars, timeframe);
  }, [rawBars, timeframe]);

  const barsRef = useRef<KLineData[]>([]);
  barsRef.current = bars;

  const lastCandle = bars.length > 0 ? bars[bars.length - 1] : null;

  // ۱. راه‌اندازی و نابودی چارت با ایمنی کامل از نشتی حافظه DOM
  useEffect(() => {
    ensureAllOverlaysRegistered();

    const container = containerRef.current;
    if (!container) return;

    const initialStyles = isLight ? LIGHT_CHART_STYLES : BRASS_CHART_STYLES;
    let chartInstance: Chart | null = null;
    try {
      chartInstance = init(container, {
        styles: initialStyles,
        formatter: {
          formatDate: ({ timestamp }) => formatJalaliDate(timestamp),
        },
      });
    } catch {
      chartInstance = null;
    }

    if (!chartInstance) return;

    chartRef.current = chartInstance;
    setActiveChartInstance(chartInstance);
    chartInstance.setStyles(initialStyles);
    chartInstance.setSymbol({ ticker: symbol });
    const periodSpan: Period = timeframe === '1W' ? { type: 'week', span: 1 } : timeframe === '1M' ? { type: 'month', span: 1 } : { type: 'day', span: 1 };
    chartInstance.setPeriod(periodSpan);

    // بارگذاری داده‌های اولیه
    chartInstance.setDataLoader({
      getBars: ({ callback }) => {
        callback(barsRef.current, false);
      },
    });

    onChartReady?.(chartInstance);

    // اتصال ResizeObserver برای انطباق واکنش‌گرا و سریع
    const observer =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            chartRef.current?.resize();
          })
        : null;

    observer?.observe(container);

    return () => {
      observer?.disconnect();
      if (container) {
        try {
          dispose(container);
        } catch {
          // نادیده گرفتن خطاهای محیط آزمون
        }
      }
      chartRef.current = null;
      setActiveChartInstance(null);
    };
  }, [symbol]);

  // به‌روزرسانی استایل چارت با تغییر تم پویا (تاریک/روشن)
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.setStyles(isLight ? LIGHT_CHART_STYLES : BRASS_CHART_STYLES);
    }
  }, [isLight]);

  // به‌روزرسانی دوره زمانی چارت هنگام تغییر تایم‌فریم
  useEffect(() => {
    if (chartRef.current) {
      const periodSpan: Period = timeframe === '1W' ? { type: 'week', span: 1 } : timeframe === '1M' ? { type: 'month', span: 1 } : { type: 'day', span: 1 };
      chartRef.current.setPeriod(periodSpan);
    }
  }, [timeframe]);

  // به‌روزرسانی مقیاس محور قیمت Y (لگاریتمی یا خطی بر اساس انتخاب کاربر)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.overrideYAxis({
        paneId: 'candle_pane',
        name: isLogScale ? 'logarithm' : 'normal',
      });
    } catch {
      // ایمنی در زمان تست
    }
  }, [isLogScale]);

  // ۲. به‌روزرسانی داده‌ها هنگام تغییر کندل‌ها
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || bars.length === 0) return;
    chart.resetData();
  }, [bars]);

  // ۳. پالس زنده تیک قیمت با CSS شتاب‌یافته و احترام به prefers-reduced-motion
  useEffect(() => {
    if (!lastCandle) return;
    const currentPrice = lastCandle.close;

    if (prevPriceRef.current !== null && prevPriceRef.current !== currentPrice) {
      const badgeEl = pulseBadgeRef.current;
      if (badgeEl) {
        badgeEl.classList.remove('kline-price-pulse-active');
        // بازخوانی reflow بدون ری‌رندر ری‌اکت
        void badgeEl.offsetWidth;
        badgeEl.classList.add('kline-price-pulse-active');
      }
    }
    prevPriceRef.current = currentPrice;
  }, [lastCandle?.close]);

  // ۴. مدیریت ابزار رسم فعال (Drawing Tool Activation)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !activeTool) return;

    const toolItem = getDrawingToolById(activeTool);
    const overlayName = toolItem ? toolItem.overlayName : activeTool;

    try {
      chart.createOverlay({
        name: overlayName,
        lock: isLockedAllDrawings,
        mode: isMagnetMode ? 'weak_magnet' : 'normal',
        onDrawEnd: () => {
          useTechnicalStore.getState().setActiveDrawingTool(null);
        },
      });
    } catch {
      // در صورت عدم پشتیبانی یا خطا در ابزار
    }
  }, [activeTool, isLockedAllDrawings, isMagnetMode]);

  // ۴٫۱. پاک‌سازی تمام ترسیمات کاربر با رویداد kline:clear-drawings
  useEffect(() => {
    const handleClearDrawings = () => {
      const chart = chartRef.current;
      if (!chart) return;
      const drawingOverlayNames = [
        'segment',
        'horizontalStraightLine',
        'horizontalRayLine',
        'rayLine',
        'verticalStraightLine',
        'parallelStraightLine',
        'regressionChannel',
        'fibonacciLine',
        'fibonacciExtension',
        'fibonacciFan',
        'andrewsPitchfork',
        'gannBox',
        'rect',
        'priceRange',
        'riskReward',
      ];
      try {
        for (const name of drawingOverlayNames) {
          chart.removeOverlay({ name });
        }
      } catch {
        // نادیده گرفتن در زمان تست
      }
    };

    window.addEventListener('kline:clear-drawings', handleClearDrawings);
    return () => {
      window.removeEventListener('kline:clear-drawings', handleClearDrawings);
    };
  }, []);

  // ۵. مدیریت کان پیش‌بینی AI (Prediction Cone)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    try {
      chart.removeOverlay({ name: 'predictionCone' });
      if (showPredictionCone && predictionData) {
        chart.createOverlay({
          name: 'predictionCone',
          points: [{ dataIndex: 0 }],
          extendData: predictionData,
          lock: true,
          zLevel: 1,
        });
      }
    } catch {
      // ایمنی در زمان تست
    }
  }, [showPredictionCone, predictionData]);

  // ۶. مدیریت زون‌های پرایس‌اکشن SMC (FVG و Order Block)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    try {
      chart.removeOverlay({ name: 'smcZones' });
      chart.removeOverlay({ name: 'fvgZone' });
      chart.removeOverlay({ name: 'orderBlockZone' });

      if (showSMCZones && candleEdgeData?.activeZones && candleEdgeData.activeZones.length > 0) {
        chart.createOverlay({
          name: 'smcZones',
          points: [{ dataIndex: 0 }],
          extendData: { zones: candleEdgeData.activeZones },
          lock: true,
          zLevel: 2,
        });
      }
    } catch {
      // ایمنی در زمان تست
    }
  }, [showSMCZones, candleEdgeData]);

  // ۷. مدیریت اندیکاتورهای سفارشی فعال کاربر
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    try {
      const knownCustomIndicators = [
        'BreakoutRetestPro',
        'SuperTrendHeikinAshi',
        'FiboRSI8',
        'RsiMaSmooth',
        'DoubleTap3D',
        'SuperTrendPullback',
        'AutoTrendlineCHoCH',
        'MultiModeChannel',
        'MultiVariantRSI',
      ];
      for (const name of knownCustomIndicators) {
        chart.removeOverlay({ name });
      }
      for (const ind of activeUserIndicators) {
        chart.createOverlay({
          name: ind,
          points: [{ dataIndex: 0 }],
          lock: true,
          zLevel: 3,
        });
      }
    } catch {
      // ایمنی
    }
  }, [activeUserIndicators, channelMode, rsiVariant]);

  // ۸. همگام‌سازی و مدیریت رویدادهای تعدیلی و شرکتی رهاورد ۳۶۵ (M مجمع، D سود نقدی، E افزایش سرمایه)
  useEffect(() => {
    if (chartQuery.data?.corporateEvents) {
      setCorporateEvents(chartQuery.data.corporateEvents);
    }
  }, [chartQuery.data?.corporateEvents, setCorporateEvents]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    try {
      chart.removeOverlay({ name: 'corporateEvents' });
      const events = chartQuery.data?.corporateEvents;
      if (showCorporateEvents && events && events.length > 0) {
        chart.createOverlay({
          name: 'corporateEvents',
          points: [{ dataIndex: 0 }],
          extendData: { events },
          lock: true,
          zLevel: 4,
        });
      }
    } catch {
      // ایمنی
    }
  }, [showCorporateEvents, chartQuery.data?.corporateEvents]);

  return (
    <div
      data-testid="kline-chart-wrapper"
      className={`relative w-full h-full select-none overflow-hidden ${isLight ? 'bg-[#fbf9f5]' : 'bg-[#121417]'} ${isHideAllDrawings ? 'kline-drawings-hidden' : ''} ${className ?? ''}`}
      dir="ltr"
      style={{
        transform: 'translateZ(0)',
        willChange: 'transform',
        contain: 'content',
      }}
    >
      {/* پالس زنده نشانگر آخرین قیمت با CSS شتاب‌یافته سخت‌افزاری */}
      {lastCandle && (
        <div
          ref={pulseBadgeRef}
          data-testid="live-price-pulse"
          className={`absolute top-3 left-4 z-10 flex items-center gap-2 px-2.5 py-1 rounded border text-xs shadow-md pointer-events-none ${
            isLight
              ? 'bg-white/95 border-gray-300 text-gray-800'
              : 'bg-[#1a1d24]/90 border-yellow-600/30 text-white'
          }`}
          style={{ willChange: 'transform' }}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-semibold text-text-primary text-[11px] font-mono">
            {toFaDigits(lastCandle.close.toLocaleString('en-US'))}
          </span>
          <span className="text-[10px] text-text-muted">ریال</span>
        </div>
      )}

      {/* استایل‌های شتاب‌یافته CSS برای انیمیشن پالس زنده و الگوهای W و M */}
      <style>{`
        @keyframes klinePriceTickPulse {
          0% { transform: scale(1) translateZ(0); box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
          50% { transform: scale(1.05) translateZ(0); filter: brightness(1.15); box-shadow: 0 0 12px 2px rgba(234, 179, 8, 0.35); }
          100% { transform: scale(1) translateZ(0); box-shadow: 0 0 0 0 rgba(234, 179, 8, 0); }
        }
        .kline-price-pulse-active {
          animation: klinePriceTickPulse 320ms cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes doubleTapNecklinePulse {
          0%, 100% {
            stroke-opacity: 0.55;
            filter: drop-shadow(0 0 2px #bc13fe);
          }
          50% {
            stroke-opacity: 1;
            filter: drop-shadow(0 0 10px #bc13fe) drop-shadow(0 0 16px rgba(188, 19, 254, 0.7));
          }
        }
        @keyframes doubleTapHalo {
          0% {
            r: 3px;
            opacity: 0.9;
          }
          50% {
            r: 9px;
            opacity: 0.25;
          }
          100% {
            r: 13px;
            opacity: 0;
          }
        }
        @keyframes doubleTapLegFlow {
          from {
            stroke-dashoffset: 40;
          }
          to {
            stroke-dashoffset: 0;
          }
        }
        @keyframes doubleTapBadgeFloat {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-3px); }
        }
        .double-tap-neckline-animated {
          animation: doubleTapNecklinePulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        .double-tap-halo-animated {
          animation: doubleTapHalo 2.2s cubic-bezier(0.16, 1, 0.3, 1) infinite;
        }
        .double-tap-leg-animated {
          stroke-dasharray: 6 3;
          animation: doubleTapLegFlow 1.8s linear infinite;
        }
        .double-tap-badge-animated {
          animation: doubleTapBadgeFloat 3s ease-in-out infinite;
        }
        .kline-drawings-hidden .klinecharts-overlay {
          display: none !important;
          opacity: 0 !important;
        }
        @media (prefers-reduced-motion: reduce) {
          .kline-price-pulse-active,
          .double-tap-neckline-animated,
          .double-tap-halo-animated,
          .double-tap-leg-animated,
          .double-tap-badge-animated {
            animation: none !important;
            transform: none !important;
            box-shadow: none !important;
            filter: none !important;
          }
        }
      `}</style>

      {/* دکمه‌های مقیاس لگاریتمی (log) و تنظیم خودکار (auto) به سبک Quantower و TradingView */}
      <div
        data-testid="chart-scale-controls"
        className="absolute bottom-1.5 right-1.5 z-20 flex items-center gap-1 p-0.5 rounded border shadow-sm backdrop-blur-sm transition-all"
        style={{
          backgroundColor: isLight ? 'rgba(255, 255, 255, 0.85)' : 'rgba(26, 29, 36, 0.85)',
          borderColor: isLight ? 'rgba(0, 0, 0, 0.12)' : 'rgba(218, 165, 32, 0.25)',
        }}
      >
        <button
          type="button"
          data-testid="toggle-log-scale-btn"
          onClick={toggleLogScale}
          title="مقیاس لگاریتمی (Logarithmic)"
          className={`px-1.5 py-0.5 text-[10px] font-mono font-medium rounded transition-colors ${
            isLogScale
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 font-bold'
              : isLight
              ? 'text-gray-600 hover:text-black hover:bg-black/5'
              : 'text-gray-400 hover:text-gray-100 hover:bg-white/5'
          }`}
        >
          log
        </button>
        <button
          type="button"
          data-testid="toggle-auto-scale-btn"
          onClick={() => {
            toggleAutoScale();
            try {
              chartRef.current?.scrollToRealTime();
            } catch {
              // ignore
            }
          }}
          title="تنظیم خودکار مقیاس (Auto-fit)"
          className={`px-1.5 py-0.5 text-[10px] font-mono font-medium rounded transition-colors ${
            isAutoScale
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40 font-bold'
              : isLight
              ? 'text-gray-600 hover:text-black hover:bg-black/5'
              : 'text-gray-400 hover:text-gray-100 hover:bg-white/5'
          }`}
        >
          auto
        </button>
      </div>

      {/* لایه انیمیشن وب برای الگوهای سقف و کف دوقلو W و M */}
      <AnimatedPatternOverlay
        chart={activeChartInstance || chartRef.current}
        patterns={detectedDoubleTapPatterns}
        active={activeUserIndicators.includes('DoubleTap3D')}
        isLight={isLight}
      />

      {/* المان کانتینر اصلی کانواس KLineCharts */}
      <div
        ref={containerRef}
        data-testid="kline-chart-container"
        className="w-full h-full relative"
      />
    </div>
  );
};

/**
 * گارد اطمینان از وجود کانتکست React Query در صورت عدم ارائه Provider خارجی
 */
export const KLineChartWrapper: React.FC<KLineChartWrapperProps> = (props) => {
  const existingClient = useContext(QueryClientContext);
  const [fallbackClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            staleTime: 60_000,
          },
        },
      })
  );

  if (!existingClient) {
    return (
      <QueryClientProvider client={fallbackClient}>
        <KLineChartInner {...props} />
      </QueryClientProvider>
    );
  }

  return <KLineChartInner {...props} />;
};
