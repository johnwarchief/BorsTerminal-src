// features/technical/components/LwChartWrapper.tsx -- رندر چارت با Lightweight Charts (v5)
// موتور رسمی و متن‌باز TradingView، پشت سوییچ موتور (کنار klinecharts قدیم).
// پنل‌ها: کندل + حجم (هیستوگرام) + MA14/MA100 روی قیمت + MA21 حجم؛ RSI(14) در پنل جدا.
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createTextWatermark,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type ITextWatermarkPluginApi,
  type MouseEventParams,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { KLineData } from '../../../vendor/klinecharts';
import { epochToJalali } from '../lib/jalaliDate';
import { LW_MA_COLORS, maLine, rsiLine, toLwCandles, toLwVolume, volumeMaLine } from '../lib/lwChart';
import type { ChartPalette } from './KLineChartWrapper';

export type LwLegend = { open: number; high: number; low: number; close: number; volume: number; date: string };

function fa(v: number): string {
  return Number.isFinite(v) ? v.toFixed(0) : '-';
}

export function LwChartWrapper({
  data,
  palette,
  height = 600,
  showRsi = false,
  showVolMa = false,
  symbol = 'فولاد',
  timeframe = 'D',
}: {
  data: KLineData[];
  palette: ChartPalette;
  height?: number;
  showRsi?: boolean;
  showVolMa?: boolean;
  symbol?: string;
  timeframe?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{
    candle: ISeriesApi<'Candlestick'> | null;
    volume: ISeriesApi<'Histogram'> | null;
    ma14: ISeriesApi<'Line'> | null;
    ma100: ISeriesApi<'Line'> | null;
    volMa: ISeriesApi<'Line'> | null;
    rsi: ISeriesApi<'Line'> | null;
    rsiPane: ReturnType<IChartApi['addPane']> | null;
  }>({ candle: null, volume: null, ma14: null, ma100: null, volMa: null, rsi: null, rsiPane: null });
  const watermarkRef = useRef<ITextWatermarkPluginApi<unknown> | null>(null);
  const symbolRef = useRef(symbol);
  const timeframeRef = useRef(timeframe);
  symbolRef.current = symbol;
  timeframeRef.current = timeframe;
  const paletteRef = useRef(palette);
  const [libMissing, setLibMissing] = useState(false);
  const [legend, setLegend] = useState<LwLegend | null>(null);

  const rows = useMemo(() => [...data].sort((a, b) => a.timestamp - b.timestamp), [data]);
  const rowsRef = useRef<KLineData[]>(rows);
  rowsRef.current = rows;
  paletteRef.current = palette;

  // --- init یک‌بار ---
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let chart: IChartApi;
    const pal = paletteRef.current;
    try {
      chart = createChart(el, {
        autoSize: true,
        layout: {
          background: { type: ColorType.Solid, color: pal.background },
          textColor: pal.text,
          fontSize: 12,
          fontFamily: 'Vazirmatn, -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif',
          attributionLogo: false,
        },
        grid: {
          vertLines: { color: pal.grid, style: LineStyle.Dashed, visible: true },
          horzLines: { color: pal.grid, style: LineStyle.Dashed, visible: true },
        },
        rightPriceScale: {
          borderColor: pal.axis || '#2a2e39',
          borderVisible: true,
          alignLabels: true,
          scaleMargins: { top: 0.1, bottom: 0.15 },
        },
        timeScale: {
          borderColor: pal.axis || '#2a2e39',
          borderVisible: true,
          timeVisible: false,
          minimumHeight: 28,
          allowBoldLabels: true,
          rightOffset: 6,
          barSpacing: 8,
          ticksVisible: true,
        },
        crosshair: { mode: CrosshairMode.Normal },
        localization: {
          locale: 'fa-IR',
          timeFormatter: (t: unknown) => (typeof t === 'number' ? epochToJalali(t * 1000) : ''),
        },
      });
    } catch {
      setLibMissing(true);
      return;
    }
    chartRef.current = chart;
    try {
      seriesRef.current.candle = chart.addSeries(CandlestickSeries, {
        upColor: pal.up,
        downColor: pal.down,
        borderVisible: true,
        borderUpColor: pal.up,
        borderDownColor: pal.down,
        wickVisible: true,
        wickUpColor: pal.up,
        wickDownColor: pal.down,
        priceLineVisible: true,
        priceLineStyle: LineStyle.Dashed,
        priceLineWidth: 1,
        lastValueVisible: true,
      });
      const vol = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'vol',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      seriesRef.current.volume = vol;
      seriesRef.current.ma14 = chart.addSeries(LineSeries, {
        color: LW_MA_COLORS[14],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      seriesRef.current.ma100 = chart.addSeries(LineSeries, {
        color: LW_MA_COLORS[100],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      seriesRef.current.volMa = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 1,
        priceScaleId: 'vol',
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });

      try {
        const panes = chart.panes();
        const firstPane = panes && panes[0];
        if (firstPane && typeof createTextWatermark === 'function') {
          watermarkRef.current = createTextWatermark(firstPane, {
            horzAlign: 'center',
            vertAlign: 'center',
            lines: [
              {
                text: `${symbolRef.current} · ${timeframeRef.current}`,
                color: 'rgba(209, 212, 220, 0.05)',
                fontSize: 56,
                fontStyle: 'bold',
                fontFamily: 'Vazirmatn, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              },
            ],
          });
        }
      } catch {
        // نادیده بگیر
      }
    } catch {
      setLibMissing(true);
      return;
    }

    const onMove = (param: MouseEventParams) => {
      const s = seriesRef.current.candle;
      if (!s || param.time == null || !param.seriesData) {
        setLegend(null);
        return;
      }
      const d = param.seriesData.get(s) as CandlestickData<UTCTimestamp> | undefined;
      if (!d) {
        setLegend(null);
        return;
      }
      const volSeries = seriesRef.current.volume;
      const v = volSeries ? (param.seriesData.get(volSeries) as { value?: number } | undefined) : undefined;
      setLegend({
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: typeof v?.value === 'number' ? v.value : 0,
        date: typeof param.time === 'number' ? epochToJalali(param.time * 1000) : '',
      });
    };
    try {
      chart.subscribeCrosshairMove(onMove);
    } catch {
      // کراس‌هیر اختیاری است
    }

    return () => {
      try {
        watermarkRef.current?.detach();
      } catch {
        // نادیده بگیر
      }
      watermarkRef.current = null;
      try {
        chart.remove();
      } catch {
        // نادیده بگیر
      }
      chartRef.current = null;
      seriesRef.current = { candle: null, volume: null, ma14: null, ma100: null, volMa: null, rsi: null, rsiPane: null };
    };
  }, []);

  // --- پالت تم ---
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.applyOptions({
        layout: {
          background: { type: ColorType.Solid, color: palette.background },
          textColor: palette.text,
          fontSize: 12,
        },
        grid: {
          vertLines: { color: palette.grid, style: LineStyle.Dashed },
          horzLines: { color: palette.grid, style: LineStyle.Dashed },
        },
        rightPriceScale: { borderColor: palette.axis || '#2a2e39' },
        timeScale: { borderColor: palette.axis || '#2a2e39', minimumHeight: 28 },
      });
      seriesRef.current.candle?.applyOptions({
        upColor: palette.up,
        downColor: palette.down,
        borderVisible: true,
        borderUpColor: palette.up,
        borderDownColor: palette.down,
        wickVisible: true,
        wickUpColor: palette.up,
        wickDownColor: palette.down,
        priceLineVisible: true,
        priceLineStyle: LineStyle.Dashed,
        lastValueVisible: true,
      });
    } catch {
      // نادیده بگیر
    }
  }, [palette]);

  // --- به‌روزرسانی واترمارک نماد و تایم‌فریم ---
  useEffect(() => {
    if (watermarkRef.current) {
      try {
        watermarkRef.current.applyOptions({
          lines: [
            {
              text: `${symbol} · ${timeframe}`,
              color: 'rgba(209, 212, 220, 0.05)',
              fontSize: 56,
              fontStyle: 'bold',
              fontFamily: 'Vazirmatn, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            },
          ],
        });
      } catch {
        // نادیده بگیر
      }
    }
  }, [symbol, timeframe]);

  // --- داده ---
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const s = seriesRef.current;
    try {
      s.candle?.setData(toLwCandles(rows));
      s.volume?.setData(toLwVolume(rows));
      s.ma14?.setData(maLine(rows, 14, LW_MA_COLORS[14]));
      s.ma100?.setData(maLine(rows, 100, LW_MA_COLORS[100]));
      s.volMa?.setData(volumeMaLine(rows, 21));
      s.rsi?.setData(rsiLine(rows, 14, '#a78bfa'));
      chart.timeScale().fitContent();
    } catch {
      // دادهٔ نامعتبر نباید رندر را بشکند
    }
  }, [rows]);

  // --- MA حجم ۲۱ (نمایش/پنهان) ---
  useEffect(() => {
    try {
      seriesRef.current.volMa?.applyOptions({ visible: showVolMa });
    } catch {
      // نادیده بگیر
    }
  }, [showVolMa]);

  // --- RSI(14) در پنل جدا ---
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const s = seriesRef.current;
    try {
      if (showRsi && !s.rsi) {
        const pane = chart.addPane();
        pane.setHeight(110);
        s.rsiPane = pane;
        s.rsi = pane.addSeries(LineSeries, {
          color: '#a78bfa',
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        s.rsi.setData(rsiLine(rowsRef.current, 14, '#a78bfa'));
      } else if (!showRsi && s.rsi) {
        const idx = chart.panes().findIndex((p) => p === s.rsiPane);
        if (idx >= 0) chart.removePane(idx);
        s.rsi = null;
        s.rsiPane = null;
      }
    } catch {
      // پنل RSI اختیاری است
    }
  }, [showRsi]);

  if (libMissing) {
    return (
      <div
        className="flex items-center justify-center rounded-2xl border border-dashed border-border-c bg-bg-secondary p-10 text-center text-xs text-text-muted"
        style={{ height }}
        data-testid="lw-missing"
      >
        موتور Lightweight Charts بارگذاری نشد؛ موتور قبلی را انتخاب کن یا صفحه را تازه کن
      </div>
    );
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-[#131722]" dir="ltr" data-testid="lw-wrap">
      {/* واترمارک محو پس‌زمینه بزرگ با شفافیت ۵٪ */}
      <div
        className="pointer-events-none absolute inset-0 z-0 flex select-none items-center justify-center font-bold tracking-wider text-[52px] text-[#d1d4dc]/[0.05] sm:text-[68px]"
        data-testid="lw-watermark"
        aria-hidden="true"
      >
        {symbol} · {timeframe}
      </div>
      <div ref={containerRef} style={{ height }} className="relative z-1" data-testid="lw-host" />
      <div
        className="pointer-events-none absolute left-2 top-1 z-10 flex max-w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-md bg-[#131722]/85 px-2 py-1 text-[10px] text-[#d1d4dc] backdrop-blur-sm"
        data-testid="lw-legend"
      >
        {legend ? (
          <>
            <span className="text-[#d1d4dc]/70" data-testid="lw-legend-date">{legend.date}</span>
            <span className="text-[#d1d4dc]/80">O:{fa(legend.open)}</span>
            <span className="text-[#d1d4dc]/80">H:{fa(legend.high)}</span>
            <span className="text-[#d1d4dc]/80">L:{fa(legend.low)}</span>
            <span className={legend.close >= legend.open ? 'font-bold text-[#089981]' : 'font-bold text-[#f23645]'}>
              C:{fa(legend.close)}
            </span>
            <span className="text-[#d1d4dc]/80">V:{fa(legend.volume)}</span>
          </>
        ) : (
          <span className="text-[#d1d4dc]/50">برای دیدن OHLCV نشانگر را روی چارت ببرید</span>
        )}
      </div>
    </div>
  );
}
