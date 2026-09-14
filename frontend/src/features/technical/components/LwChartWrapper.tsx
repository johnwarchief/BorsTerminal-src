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
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
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
}: {
  data: KLineData[];
  palette: ChartPalette;
  height?: number;
  showRsi?: boolean;
  showVolMa?: boolean;
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
        layout: { background: { type: ColorType.Solid, color: pal.background }, textColor: pal.text, attributionLogo: false },
        grid: { vertLines: { color: pal.grid }, horzLines: { color: pal.grid } },
        rightPriceScale: { borderColor: pal.grid },
        timeScale: { borderColor: pal.grid, timeVisible: false },
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
        borderVisible: false,
        wickUpColor: pal.up,
        wickDownColor: pal.down,
        priceLineVisible: false,
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
        layout: { background: { type: ColorType.Solid, color: palette.background }, textColor: palette.text },
        grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
        rightPriceScale: { borderColor: palette.grid },
        timeScale: { borderColor: palette.grid },
      });
      seriesRef.current.candle?.applyOptions({
        upColor: palette.up,
        downColor: palette.down,
        wickUpColor: palette.up,
        wickDownColor: palette.down,
      });
    } catch {
      // نادیده بگیر
    }
  }, [palette]);

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
    <div className="glass-panel relative overflow-hidden rounded-2xl p-px" dir="ltr" data-testid="lw-wrap">
      <div ref={containerRef} style={{ height }} data-testid="lw-host" />
      <div
        className="pointer-events-none absolute left-2 top-1 z-10 flex max-w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-md bg-bg-card/70 px-2 py-1 text-[10px] backdrop-blur-sm"
        data-testid="lw-legend"
      >
        {legend ? (
          <>
            <span className="text-text-secondary" data-testid="lw-legend-date">{legend.date}</span>
            <span className="text-text-secondary">O:{fa(legend.open)}</span>
            <span className="text-text-secondary">H:{fa(legend.high)}</span>
            <span className="text-text-secondary">L:{fa(legend.low)}</span>
            <span className={legend.close >= legend.open ? 'font-bold text-accent-green' : 'font-bold text-accent-red'}>
              C:{fa(legend.close)}
            </span>
            <span className="text-text-secondary">V:{fa(legend.volume)}</span>
          </>
        ) : (
          <span className="text-text-muted">برای دیدن OHLCV نشانگر را روی چارت ببرید</span>
        )}
      </div>
    </div>
  );
}
