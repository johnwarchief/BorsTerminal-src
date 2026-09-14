// features/technical/components/KLineChartWrapper.tsx -- موتور چارت TradingView-clone روی klinecharts v10
// تعامل: زوم اسکرول، پن درگ، کراس هیر OHLCV، محور قیمت با درگ فشرده + دکمه Auto-fit،
// حجم متصل به همان پنل با رنگ کندل، محور جلالی ایزوله LTR، لایه های FTS (MA/فیبو/مارکر).
// v10 داده را با setDataLoader می گیرد (applyNewData در این نسخه وجود ندارد).
// ترتیب: بک اند (api/chart) نزولی است؛ نرمال‌سازی صعودی همین‌جا قبل از feed انجام می شود.
import { useEffect, useMemo, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import type { KLineChart, KLineData } from '../../../vendor/klinecharts';
import { epochToJalali } from '../lib/jalaliDate';
import {
  FTS_OVERLAY_COLORS,
  JET_LINE_OVERLAY,
  JET_MARKER_OVERLAY,
  PULLBACK_MARKER_OVERLAY,
  fibZoneOverlayObj,
  fibZoneSpecs,
  jetLineOverlayObj,
  markerOverlayObj,
  registerFtsOverlays,
} from '../lib/ftsOverlays';

export type ChartPalette = {
  up: string;
  down: string;
  grid: string;
  text: string;
  background: string;
  /** رنگ خط محور/جداساز (اختیاری؛ پیشفرض grid) */
  axis?: string;
};

const FA_LOCALE: Record<string, unknown> = {
  time: 'زمان: ',
  open: 'باز شدن: ',
  high: 'بیشترین: ',
  low: 'کمترین: ',
  close: 'بسته شدن: ',
  volume: 'حجم: ',
  change: 'تغییر: ',
  day: 'روز',
  week: 'هفته',
  month: 'ماه',
  year: 'سال',
};

function applyPalette(chart: KLineChart, p: ChartPalette) {
  const axis = p.axis ?? p.grid;
  chart.setStyles({
    grid: {
      horizontal: { color: p.grid, style: 'solid' },
      vertical: { color: p.grid, style: 'solid' },
    },
    candle: {
      bar: {
        upColor: p.up,
        downColor: p.down,
        noChangeColor: '#888888',
        upBorderColor: p.up,
        downBorderColor: p.down,
        upWickColor: p.up,
        downWickColor: p.down,
      },
      priceMark: { high: { color: p.text }, low: { color: p.text }, last: { upColor: p.up, downColor: p.down } },
      tooltip: { showRule: 'none', showType: 'standard' },
    },
    xAxis: {
      axisLine: { color: axis },
      tickLine: { color: axis },
      tickText: { color: p.text, size: 10, family: 'Vazirmatn, sans-serif' },
    },
    yAxis: {
      axisLine: { color: axis },
      tickLine: { color: axis },
      tickText: { color: p.text, size: 10, family: 'Vazirmatn, sans-serif' },
      position: 'right',
    },
    separator: { color: axis },
    crosshair: {
      horizontal: { line: { color: axis, style: 'dashed' }, text: { color: '#fff', borderColor: axis, backgroundColor: '#2a2e39' } },
      vertical: { line: { color: axis, style: 'dashed' }, text: { color: '#fff', borderColor: axis, backgroundColor: '#2a2e39' } },
    },
    indicator: {
      bars: [{ upColor: p.up, downColor: p.down, noChangeColor: '#888888' }],
    },
  });
}

export type ChartLine = { price: number; timestamp: number };

/** رنگ استاندارد هر مووینگ FTS — MA-14 سرمه‌ای، MA-52 نارنجی، MA-100 بنفش */
export const FTS_MA_COLORS: Record<number, string> = {
  14: '#1d4ed8',
  21: '#06b6d4',
  52: '#f97316',
  100: '#a78bfa',
};

export type ChartMarkerKind = 'jet' | 'pullback';

export type ChartMarker = {
  kind: ChartMarkerKind;
  label: string;
  timestamp: number;
  price: number;
  /** up = بالای کندل (جت)، down = زیر کندل (کف دوقلو/شکار نقطه) */
  dir: 'up' | 'down';
};

export type FtsChartLayers = {
  /** دوره های مووینگ نمایشی؛ null یعنی پنهان */
  maPeriods: number[] | null;
  /** خط آبی پرواز (مقاومت جت)؛ null یعنی پنهان */
  jet: ChartLine | null;
  /** خط چین قرمز با جهت؛ null یعنی پنهان */
  choch: (ChartLine & { bearish: boolean }) | null;
  /** کمربندهای فیبو از داده بک اند؛ null/undefined یعنی بدون کمربند */
  fib: {
    zone_33_40?: { lo?: number | null; hi?: number | null } | null;
    zone_618_70?: { lo?: number | null; hi?: number | null } | null;
  } | null;
  /** مارکرهای ستاپ روی کندل ها (جت / شکار نقطه / کف دوقلو / پولبک) */
  markers: ChartMarker[];
};

export const DEFAULT_FTS_LAYERS: FtsChartLayers = {
  maPeriods: null,
  jet: null,
  choch: null,
  fib: null,
  markers: [],
};

/** نرمال‌سازی ترتیب — صعودی بر اساس timestamp (بک اند /api/chart نزولی می دهد) */
export function sortAscending(rows: KLineData[]): KLineData[] {
  return [...rows].sort((a, b) => a.timestamp - b.timestamp);
}

function syncGroup(chart: KLineChart, groupId: string, overlays: Record<string, unknown>[]) {
  try {
    chart.removeOverlay({ groupId });
  } catch {
    // نادیده بگیر
  }
  for (const o of overlays) {
    try {
      chart.createOverlay(o);
    } catch {
      // نادیده بگیر
    }
  }
}

/** SMA خوانش داده روی ایندکس — برای legend؛ فقط خوانش، نه بازتولید تحلیل */
function smaAt(rows: KLineData[], idx: number, period: number): number | null {
  if (idx < period - 1 || period < 1) return null;
  let acc = 0;
  for (let i = idx - period + 1; i <= idx; i++) acc += rows[i].close;
  return acc / period;
}

function fmtL(v: number): string {
  return Number.isFinite(v) ? toFaDigits(v.toFixed(0)) : '-';
}

function fmtVol(v: number): string {
  if (!Number.isFinite(v)) return '-';
  if (v >= 1e9) return `${toFaDigits((v / 1e9).toFixed(1))}B`;
  if (v >= 1e6) return `${toFaDigits((v / 1e6).toFixed(1))}M`;
  if (v >= 1e3) return `${toFaDigits((v / 1e3).toFixed(1))}K`;
  return toFaDigits(Math.round(v));
}

const MARKER_STYLE: Record<ChartMarkerKind, { color: string; fill: string }> = {
  jet: { color: FTS_OVERLAY_COLORS.jet, fill: FTS_OVERLAY_COLORS.jetFill },
  pullback: { color: FTS_OVERLAY_COLORS.pullback, fill: FTS_OVERLAY_COLORS.pullbackFill },
};

export type LegendMaValue = { period: number; value: number | null; color: string };

export type HoverLegendInfo = {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  date: string;
  mas: LegendMaValue[];
};

/** شناسه پنل کندل در klinecharts v10 — اندیکاتور بدون paneId در پنل جدا می افتد */
const CANDLE_PANE = 'candle_pane';
const VOL_PANE = 'vol_pane';
const RSI_PANE = 'rsi_pane';
const VOL_MA_PERIOD = 21;
const RSI_PERIOD = 14;
/** گروه اورلی‌های ترسیمی کاربر — برای undo/redo/pاک‌کردن گروهی */
export const DRAW_GROUP = 'fts-draw';

/** API imperative ابزارهای ترسیم — به DrawingToolbar و پنل تنظیمات ابزار داده می‌شود */
export type ChartDrawApi = {
  startDraw: (name: string) => void;
  undo: () => void;
  redo: () => void;
  clearDrawings: () => void;
  hideDrawings: (hide: boolean) => void;
  /** به‌روزرسانی استایل/متن آخرین ترسیم (پنل تنظیمات ابزار) */
  updateLast: (patch: { styles?: Record<string, unknown>; extendData?: Record<string, unknown> }) => void;
};

export type LastDraw = { id: string; name: string } | null;

export function KLineChartWrapper({
  data,
  palette,
  height = 600,
  layers = DEFAULT_FTS_LAYERS,
  chartType = 'candle_solid',
  showRsi = false,
  showVolMa = false,
  priceScale = 'normal',
  showGrid = true,
  showCrosshair = true,
  onCrosshairInfo,
  onApi,
  onDrawChange,
}: {
  data: KLineData[];
  palette: ChartPalette;
  height?: number;
  layers?: FtsChartLayers;
  /** نوع نمایش کندل — مقادیر candle.type در klinecharts v10 */
  chartType?: 'candle_solid' | 'candle_stroke' | 'ohlc' | 'line' | 'area';
  /** نمایش RSI وایلدر (۱۴) در پنل جدا */
  showRsi?: boolean;
  /** نمایش میانگین متحرک حجم (۲۱) روی پنل حجم */
  showVolMa?: boolean;
  /** مقیاس محور قیمت — yAxis.type در klinecharts v10 */
  priceScale?: 'normal' | 'logarithm' | 'percentage';
  showGrid?: boolean;
  showCrosshair?: boolean;
  onCrosshairInfo?: (info: { data: KLineData | null; visibleCount: number }) => void;
  /** افشای API ابزارهای ترسیم */
  onApi?: (api: ChartDrawApi | null) => void;
  /** اطلاع از تغییر آخرین ترسیم (برای پنل تنظیمات ابزار) */
  onDrawChange?: (last: LastDraw) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<KLineChart | null>(null);
  const drawHistory = useRef<{ id: string; name: string }[]>([]);
  const redoStack = useRef<{ id: string; name: string }[]>([]);
  const onDrawChangeRef = useRef(onDrawChange);
  onDrawChangeRef.current = onDrawChange;
  const [libMissing, setLibMissing] = useState(false);
  const [barCount, setBarCount] = useState(0);
  const [hoverInfo, setHoverInfo] = useState<HoverLegendInfo | null>(null);

  // صعودی‌سازی قطعی — همین لیست فید می شود و همین برای legend خوانده می شود
  const rows = useMemo(() => sortAscending(data), [data]);
  const rowsRef = useRef<KLineData[]>(rows);
  const paletteRef = useRef(palette);
  const onCrosshairRef = useRef(onCrosshairInfo);
  const layersRef = useRef<FtsChartLayers>(layers);
  rowsRef.current = rows;
  paletteRef.current = palette;
  onCrosshairRef.current = onCrosshairInfo;
  layersRef.current = layers;

  // --- init یکبار ---
  useEffect(() => {
    const el = containerRef.current;
    const api = window.klinecharts;
    if (!el || !api) {
      setLibMissing(true);
      return;
    }
    setLibMissing(false);
    try {
      registerFtsOverlays(api);
    } catch {
      // ثبت تکراری خطا نیست
    }
    try {
      api.registerLocale('fa-IR', FA_LOCALE);
    } catch {
      // ثبت تکراری خطا نیست
    }
    let chart: KLineChart | null = null;
    try {
      chart = api.init(el, { locale: 'fa-IR', timezone: 'Asia/Tehran' });
    } catch {
      setLibMissing(true);
      return;
    }
    if (!chart) {
      setLibMissing(true);
      return;
    }
    chartRef.current = chart;

    try {
      applyPalette(chart, paletteRef.current);
    } catch {
      // نادیده بگیر
    }
    // تاریخ جلالی محور X و کراس هیر
    try {
      chart.setFormatter({
        formatDate: (p: { timestamp?: number | null }) => {
          const ts = p?.timestamp;
          return ts != null && Number.isFinite(ts) ? epochToJalali(ts) : '';
        },
      });
    } catch {
      // فرمت اختیاری است
    }
    // خوراک داده از طریق setDataLoader — تنها مسیر v10
    // more همیشه false: کل تاریخچه یک‌جا داده می شود و درخواست forward/backward تکراری ساخته نمی شود
    try {
      chart.setDataLoader({
        getBars: (req) => {
          const cb = req.callback;
          if (req.type !== 'init') {
            cb([]);
            return;
          }
          cb(rowsRef.current, false);
        },
      });
      chart.setSymbol('bors');
      chart.setPeriod('day');
    } catch {
      // نادیده بگیر
    }
    try {
      chart.setOffsetRightDistance(80);
      chart.setMaxOffsetRightDistance(320);
      chart.setZoomEnabled(true);
      chart.setScrollEnabled(true);
    } catch {
      // نادیده بگیر
    }
    // حجم: هیستوگرام در پنل خودش با رنگ هماهنگ کندل
    try {
      const existing = chart.getIndicators({ paneId: VOL_PANE });
      if (!existing || existing.length === 0) {
        chart.createIndicator({ name: 'VOL', id: VOL_PANE, paneId: VOL_PANE }, true);
      }
    } catch {
      // اندیکاتور اختیاری است
    }
    // شمارش کندل قابل مشاهده برای نمایش وضعیت زوم
    try {
      chart.subscribeAction('onVisibleRangeChange', (d) => {
        const ch = (d.chart ?? chart) as KLineChart | undefined;
        if (!ch) return;
        try {
          const vr = ch.getVisibleRange();
          const count = Math.max(0, vr.realTo - vr.realFrom + 1);
          setBarCount(count);
        } catch {
          // نادیده بگیر
        }
      });
    } catch {
      // نادیده بگیر
    }
    // گزارش کندل زیر کراس هیر: legend شناور OHLCV + مقدار لحظه ای MA ها
    try {
      chart.subscribeAction('onCrosshairChange', (d) => {
        const ch = (d.chart ?? chart) as KLineChart | undefined;
        if (!ch) return;
        try {
          const cross = ch.getCrosshair();
          const k = cross?.kLineData ?? null;
          const vr = ch.getVisibleRange();
          const visibleCount = Math.max(0, vr.realTo - vr.realFrom + 1);
          if (k) {
            const idx = rowsRef.current.findIndex((c) => c.timestamp === k.timestamp);
            const mas: LegendMaValue[] = (layersRef.current.maPeriods ?? []).map((p) => ({
              period: p,
              value: idx >= 0 ? smaAt(rowsRef.current, idx, p) : null,
              color: FTS_MA_COLORS[p] ?? '#64748b',
            }));
            setHoverInfo({
              open: k.open,
              high: k.high,
              low: k.low,
              close: k.close,
              volume: k.volume ?? 0,
              date: epochToJalali(k.timestamp),
              mas,
            });
          } else {
            setHoverInfo(null);
          }
          onCrosshairRef.current?.({ data: k ?? null, visibleCount });
        } catch {
          // نادیده بگیر
        }
      });
    } catch {
      // نادیده بگیر
    }

    let timer: ReturnType<typeof setTimeout> | null = null;
    const ro = new ResizeObserver(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        try {
          chartRef.current?.resize();
        } catch {
          // نادیده بگیر
        }
      }, 100);
    });
    ro.observe(el);

    return () => {
      if (timer) clearTimeout(timer);
      ro.disconnect();
      try {
        api.dispose(el);
      } catch {
        // نادیده بگیر
      }
      chartRef.current = null;
    };
  }, []);

  // پالت تم
  useEffect(() => {
    if (chartRef.current) {
      try {
        applyPalette(chartRef.current, palette);
      } catch {
        // نادیده بگیر
      }
    }
  }, [palette]);

  // نوع چارت (کندل/کندل توخالی/بار/خط/اریا) — candle.type در klinecharts v10
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.setStyles({ candle: { type: chartType } });
    } catch {
      // نادیده بگیر
    }
  }, [chartType]);

  // مقیاس محور قیمت (خطی/لگاریتمی/درصدی) — yAxis.type
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.setStyles({ yAxis: { type: priceScale } });
    } catch {
      // نادیده بگیر
    }
  }, [priceScale]);

  // نمایش شبکه
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.setStyles({ grid: { show: showGrid } });
    } catch {
      // نادیده بگیر
    }
  }, [showGrid]);

  // نمایش کراس‌هیر
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.setStyles({ crosshair: { show: showCrosshair } });
    } catch {
      // نادیده بگیر
    }
  }, [showCrosshair]);

  // API ابزارهای ترسیم (undo/redo/پاک‌کردن) روی اورلی‌های گروه fts-draw
  useEffect(() => {
    if (!onApi) return;
    const api: ChartDrawApi = {
      startDraw: (name: string) => {
        const chart = chartRef.current;
        if (!chart) return;
        try {
          const id = chart.createOverlay({ name, groupId: DRAW_GROUP }) as string | null;
          const entry = { id: typeof id === 'string' ? id : '', name };
          drawHistory.current = [...drawHistory.current, entry];
          redoStack.current = [];
          onDrawChangeRef.current?.(entry);
        } catch {
          // نادیده بگیر
        }
      },
      undo: () => {
        const chart = chartRef.current;
        const last = drawHistory.current[drawHistory.current.length - 1];
        if (!chart || !last) return;
        try {
          chart.removeOverlay({ id: last.id });
          drawHistory.current = drawHistory.current.slice(0, -1);
          redoStack.current = [...redoStack.current, { id: '', name: last.name }];
          onDrawChangeRef.current?.(null);
        } catch {
          // نادیده بگیر
        }
      },
      redo: () => {
        const chart = chartRef.current;
        const item = redoStack.current[redoStack.current.length - 1];
        if (!chart || !item) return;
        try {
          const id = chart.createOverlay({ name: item.name, groupId: DRAW_GROUP }) as string | null;
          const entry = { id: typeof id === 'string' ? id : '', name: item.name };
          drawHistory.current = [...drawHistory.current, entry];
          redoStack.current = redoStack.current.slice(0, -1);
          onDrawChangeRef.current?.(entry);
        } catch {
          // نادیده بگیر
        }
      },
      clearDrawings: () => {
        const chart = chartRef.current;
        if (!chart) return;
        try {
          chart.removeOverlay({ groupId: DRAW_GROUP });
        } catch {
          // نادیده بگیر
        }
        drawHistory.current = [];
        redoStack.current = [];
        onDrawChangeRef.current?.(null);
      },
      hideDrawings: (hide: boolean) => {
        const chart = chartRef.current;
        if (!chart) return;
        try {
          chart.overrideOverlay({ groupId: DRAW_GROUP, styles: { visible: !hide } });
        } catch {
          // نادیده بگیر
        }
      },
      updateLast: (patch) => {
        const chart = chartRef.current;
        const last = drawHistory.current[drawHistory.current.length - 1];
        if (!chart || !last) return;
        try {
          chart.overrideOverlay({ id: last.id, ...patch });
        } catch {
          // نادیده بگیر
        }
      },
    };
    onApi(api);
    return () => onApi(null);
  }, [onApi]);

  // میانگین متحرک حجم (۲۱) روی پنل حجم
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.removeIndicator({ name: 'MA', paneId: VOL_PANE });
      if (showVolMa) {
        chart.createIndicator({ name: 'MA', calcParams: [VOL_MA_PERIOD], paneId: VOL_PANE }, true);
      }
    } catch {
      // اندیکاتور اختیاری است
    }
  }, [showVolMa]);

  // RSI وایلدر (۱۴) در پنل جدا
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.removeIndicator({ name: 'RSI', paneId: RSI_PANE });
      if (showRsi) {
        chart.createIndicator({ name: 'RSI', id: RSI_PANE, calcParams: [RSI_PERIOD], paneId: RSI_PANE }, true);
      }
    } catch {
      // اندیکاتور اختیاری است
    }
  }, [showRsi]);

  // داده: resetData تا چارت از dataLoader آرایه صعودی تازه را بگیرد
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.resetData();
      chart.scrollToRealTime();
    } catch {
      // نادیده بگیر
    }
  }, [rows]);

  // لایه مووینگ ها — روی پنل کندل (paneId: candle_pane + isStack) با رنگ استاندارد FTS
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.removeIndicator({ name: 'MA', paneId: CANDLE_PANE });
      if (!layers.maPeriods) return;
      chart.createIndicator({ name: 'MA', calcParams: layers.maPeriods, paneId: CANDLE_PANE }, true);
      chart.overrideIndicator({
        name: 'MA',
        paneId: CANDLE_PANE,
        styles: {
          lines: layers.maPeriods.map((p) => ({
            style: 'solid',
            smooth: false,
            size: p === 14 ? 1.6 : 1.2,
            color: FTS_MA_COLORS[p] ?? '#64748b',
          })),
        },
      });
    } catch {
      // نادیده بگیر
    }
  }, [layers.maPeriods]);

  // کمربندهای فیبو (از داده بک اند؛ بدون بازتولید محاسبه)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const specs = fibZoneSpecs(layers.fib ?? null);
    const anchorTs = rows.length > 0 ? rows[rows.length - 1].timestamp : 0;
    if (specs.length === 0 || anchorTs === 0) {
      syncGroup(chart, 'fts-fib', []);
      return;
    }
    syncGroup(
      chart,
      'fts-fib',
      specs.map((s) => fibZoneOverlayObj(s, anchorTs, 'fts-fib')),
    );
  }, [layers.fib, rows]);

  // مارکرهای ستاپ: جت بالا، پولبک/شکار نقطه/کف دوقلو زیر کندل
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const overlays: Record<string, unknown>[] = [];
    for (const m of layers.markers) {
      if (!m || m.timestamp <= 0) continue;
      const style = MARKER_STYLE[m.kind];
      overlays.push(
        markerOverlayObj(
          m.kind === 'jet' ? JET_MARKER_OVERLAY : PULLBACK_MARKER_OVERLAY,
          { label: m.label, color: style.color, fill: style.fill, dir: m.dir },
          m.timestamp,
          m.price,
          'fts-markers',
        ),
      );
    }
    syncGroup(chart, 'fts-markers', overlays);
  }, [layers.markers]);

  // خط آبی جت (مقاومت)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (!layers.jet || layers.jet.timestamp <= 0) {
      syncGroup(chart, 'fts-jet', []);
      return;
    }
    syncGroup(chart, 'fts-jet', [jetLineOverlayObj(layers.jet.price, layers.jet.timestamp, 'fts-jet')]);
  }, [layers.jet]);

  // خط چین قرمز CHoCH
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    if (!layers.choch || layers.choch.timestamp <= 0) {
      syncGroup(chart, 'fts-choch', []);
      return;
    }
    syncGroup(chart, 'fts-choch', [
      {
        name: JET_LINE_OVERLAY,
        groupId: 'fts-choch',
        points: [{ timestamp: layers.choch.timestamp, price: layers.choch.price }],
        extendData: {
          label: `CHoCH ${layers.choch.bearish ? 'نزولی' : 'صعودی'}`,
          color: FTS_OVERLAY_COLORS.chohRed,
        },
      },
    ]);
  }, [layers.choch]);

  const resetZoom = () => {
    try {
      chartRef.current?.scrollToRealTime();
      chartRef.current?.setBarSpace(10);
    } catch {
      // نادیده بگیر
    }
  };

  /** ذخیرهٔ تصویر چارت — از getConvertPictureUrl خود کتابخانه (شامل اورلی‌ها) */
  const screenshot = () => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      const url = chart.getConvertPictureUrl({ includeOverlay: true, type: 'png', backgroundColor: palette.background });
      if (!url) return;
      const a = document.createElement('a');
      a.href = url;
      a.download = 'chart.png';
      a.click();
    } catch {
      // نادیده بگیر
    }
  };

  /** تمام‌صفحهٔ رپر چارت */
  const toggleFullscreen = () => {
    const el = containerRef.current?.parentElement;
    try {
      if (document.fullscreenElement) void document.exitFullscreen();
      else void el?.requestFullscreen?.();
    } catch {
      // نادیده بگیر
    }
  };

  if (libMissing) {
    return (
      <div
        className="flex items-center justify-center rounded-2xl border border-dashed border-border-c bg-bg-secondary p-10 text-center text-xs text-text-muted"
        style={{ height }}
        data-testid="kline-missing"
      >
        کتابخانه چارت بارگذاری نشد؛ صفحه را تازه کن
      </div>
    );
  }

  return (
    <div className="glass-panel relative overflow-hidden rounded-2xl p-px" dir="ltr" data-testid="kline-wrap">
      <div ref={containerRef} style={{ height }} data-testid="kline-host" />
      {/* legend شیشه‌ای گوشه بالا: OHLCV فارسی + MA های فعال با رنگ خودشان */}
      <div
        className="pointer-events-none absolute left-2 top-1 z-10 flex max-w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-lg border border-[var(--hairline)] bg-bg-card/80 px-2.5 py-1 text-[10px] shadow-sm backdrop-blur-md"
        data-testid="kline-legend"
      >
        {hoverInfo ? (
          <>
            <span className="text-text-secondary" data-testid="kline-legend-date">{hoverInfo.date}</span>
            <span className="text-text-secondary">O:{fmtL(hoverInfo.open)}</span>
            <span className="text-text-secondary">H:{fmtL(hoverInfo.high)}</span>
            <span className="text-text-secondary">L:{fmtL(hoverInfo.low)}</span>
            <span className={hoverInfo.close >= hoverInfo.open ? 'font-bold text-accent-green' : 'font-bold text-accent-red'}>
              C:{fmtL(hoverInfo.close)}
            </span>
            <span className="text-text-secondary">V:{fmtVol(hoverInfo.volume)}</span>
            {hoverInfo.mas.map((m) => (
              <span key={m.period} className="font-bold" style={{ color: m.color }} data-testid={`kline-legend-ma-${m.period}`}>
                MA{m.period}:{m.value == null ? '-' : toFaDigits(m.value.toFixed(0))}
              </span>
            ))}
          </>
        ) : (
          <span className="text-text-muted">برای دیدن OHLCV نشانگر را روی چارت ببرید</span>
        )}
      </div>
      {/* کنترل نما: شمارش کندل + Auto-fit + اسکرین‌شات + تمام‌صفحه */}
      <div className="absolute right-2 top-1 z-10 flex items-center gap-2 text-[10px] text-text-muted">
        <span data-testid="kline-zoom-state">{barCount > 0 ? `${barCount} کندل در نما` : ''}</span>
        <button
          type="button"
          onClick={resetZoom}
          className="pointer-events-auto rounded border border-border-c bg-bg-card/80 px-2 py-0.5 text-[10px] text-text-secondary backdrop-blur-sm transition-colors hover:text-text-primary"
          data-testid="kline-autofit"
        >
          Auto-fit
        </button>
        <button
          type="button"
          onClick={screenshot}
          title="ذخیره تصویر چارت"
          className="pointer-events-auto rounded border border-border-c bg-bg-card/80 px-2 py-0.5 text-[10px] text-text-secondary backdrop-blur-sm transition-colors hover:text-text-primary"
          data-testid="kline-screenshot"
        >
          📷
        </button>
        <button
          type="button"
          onClick={toggleFullscreen}
          title="تمام‌صفحه"
          className="pointer-events-auto rounded border border-border-c bg-bg-card/80 px-2 py-0.5 text-[10px] text-text-secondary backdrop-blur-sm transition-colors hover:text-text-primary"
          data-testid="kline-fullscreen"
        >
          ⛶
        </button>
      </div>
    </div>
  );
}
