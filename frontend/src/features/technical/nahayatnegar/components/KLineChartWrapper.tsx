/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, no-restricted-syntax -- ?? vendored ???? ?????? */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as klinecharts from 'klinecharts';
import { init, dispose, Chart, KLineData } from 'klinecharts';
import { nahayatNegarDarkTheme, nahayatNegarLightTheme } from '../lib/chartTheme';
import { useUiStore } from '@shared/stores/uiStore';
import {
  AdjustmentMode, CorporateAction, applyAdjustmentToCandles, mapBackendAdjustEvents
} from '../lib/adjustments';
import { aggregateCandles, timeframePeriod, type Timeframe } from '../lib/timeframe';
import { analyzeFts, type FtsAnalysisResult } from '../lib/ftsOverlays';
import {
  registerFtsOverlays,
  FTS_CORP_ACTION_OVERLAY,
} from '../../lib/ftsOverlays';
import {
  clearSymbolDrawings,
  commit as commitHistory,
  initHistory,
  loadDrawings,
  loadSymbolDrawings,
  redo as redoHistory,
  saveDrawings,
  saveSymbolDrawings,
  snapToOhlc,
  undo as undoHistory,
  type StoredOverlay,
} from '../../lib/drawStore';
import { FtsToolbar } from './FtsToolbar';
import { DrawingToolbar } from './DrawingToolbar';
import { FloatingPropertiesBar } from './FloatingPropertiesBar';
import { SymbolSearchModal, SymbolInfo } from './SymbolSearchModal';
import { MarketDepthWidget } from '../../components/MarketDepthWidget';
import { IconClose } from './TradingViewIcons';
import {
  buildPatternOverlays,
  PATTERN_LABELS,
  type PatternOverlaySpec,
} from '../../lib/patternOverlays';
import {
  detectChochConfirmed,
  detectDoubleBottom,
  detectFibZigzag,
  detectHeadShoulders,
  detectHourglass,
  detectJet,
  detectMa14Exit,
  detectPointHunt,
  detectThirdPeak,
} from '../../lib/ftsPatterns';
import { usePatternPrefsStore } from '../../stores/patternPrefsStore';
import { useFtsConfigStore } from '../../stores/ftsConfigStore';
import { parseCandleTimestamp } from '../../lib/jalaliDate';

import '../styles/nahayatNegarStyles.css';

export interface ChartProps {
  initialSymbol?: string;
  initialName?: string;
  initialMarket?: string;
  boardRow?: { p_last?: number | null; p_closing?: number | null; percent_change?: number | null } | null;
  replayActive?: boolean;
  onToggleReplay?: () => void;
  onOpenSettings?: () => void;
  onSymbolChange?: (sym: SymbolInfo) => void;
  onTimeframeChange?: (tf: Timeframe) => void;
  onAdjustmentChange?: (adj: AdjustmentMode) => void;
}

// فرمت‌بندی تاریخ شمسی (جلالی) بدون پکیج اضافه با استفاده از Intl نیتیو جاوااسکریپت
function formatJalali(timestamp: number, type?: string): string {
  try {
    const date = new Date(timestamp);
    const isIntraday = type === 'minute' || type === 'hour';
    return new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: isIntraday ? '2-digit' : undefined,
      minute: isIntraday ? '2-digit' : undefined,
    }).format(date);
  } catch (e) {
    return new Date(timestamp).toLocaleDateString('fa-IR');
  }
}

// --- فاز ۴: نگاشت خروجی موتور ۹ الگو به اورلی‌های موتور چارت (آورلی‌های توکار v10) ---
// گروه مستقل «fts_pattern_overlays»؛ الگوی خاموش ⇒ هیچ اورلی‌ای ساخته نمی‌شود.
const PATTERN_GROUP_ID = 'fts_pattern_overlays';

function patternOverlayColor(spec: PatternOverlaySpec): string {
  const st = spec.styles as { color?: unknown } | undefined;
  return typeof st?.color === 'string' ? st.color : '#787b86';
}

/** یک spec الگو را به اورلی موتور چارت نگاشت می‌کند (بدون بازتولید محاسبه). */
function toChartOverlay(spec: PatternOverlaySpec, startTs: number): Record<string, unknown> {
  const color = patternOverlayColor(spec);
  const p0 = spec.points[0];

  // گرامرِ بصریِ per-pattern — هر الگو شکل/استایلِ مخصوصِ خودش را دارد (فاز ۴+).
  // ۱) مارکرها (نقطه‌زنی ◎ / خروج زیر MA14 ⨯): چیپِ برچسب‌دار روی خودِ کندل.
  if (spec.overlayName === 'ftsPointHunt' || spec.overlayName === 'ftsExitCross') {
    const glyph = spec.kind === 'ma14exit' ? '⨯' : '◎';
    return {
      name: 'simpleAnnotation',
      groupId: PATTERN_GROUP_ID,
      lock: true,
      points: [{ timestamp: p0.timestamp, value: p0.value }],
      extendData: `${glyph} ${spec.label}`,
      styles: {
        text: {
          color,
          size: 11,
          family: 'Vazirmatn',
          backgroundColor: 'rgba(11,17,28,0.78)',
          borderColor: color,
          borderSize: 1,
          borderRadius: 4,
          paddingLeft: 4,
          paddingRight: 4,
          paddingTop: 1,
          paddingBottom: 1,
        },
      },
    };
  }

  // ۲) زون/کمربند (فیبو ۱ و ۲، سقف سوم، ساعت شنی): مستطیلِ تمام‌عرض با پرِ ملایم و بوردرِ خط‌چین.
  if (spec.points.length >= 2) {
    const a = spec.points[0].value;
    const b = spec.points[1].value;
    const hi = Math.max(a, b);
    const lo = Math.min(a, b);
    const lastTs = spec.points[1].timestamp || p0.timestamp;
    return {
      name: 'rect',
      groupId: PATTERN_GROUP_ID,
      lock: true,
      points: [
        { timestamp: startTs, value: hi },
        { timestamp: lastTs, value: lo },
      ],
      styles: { polygon: { color, borderColor: color, borderSize: 1, borderStyle: 'dashed' } },
    };
  }

  // ۳) خطِ افقیِ تمام‌عرض: ضخامت/نوعِ خط مخصوصِ هر الگو
  //    جت و خطِ گردنِ دوقلو پررنگ و ممتد؛ CHoCH و خطِ گردنِ سر‌و‌شانه نازک و خط‌چین.
  const lineStyleByKind: Record<string, { size: number; style: 'solid' | 'dashed' | 'dotted' }> = {
    jet: { size: 2, style: 'solid' },
    double: { size: 2, style: 'solid' },
    choch: { size: 1, style: 'dashed' },
    headshoulders: { size: 1, style: 'dashed' },
  };
  const ls = lineStyleByKind[spec.kind] ?? { size: 1, style: 'solid' as const };
  return {
    name: 'horizontalStraightLine',
    groupId: PATTERN_GROUP_ID,
    lock: true,
    points: [{ timestamp: p0.timestamp, value: p0.value }],
    styles: { line: { color, size: ls.size, style: ls.style } },
  };
}

/** فالبکِ زون: کانالِ قیمتیِ دوانقطه‌ای (overlayِ تضمین‌شده) وقتی «rect» در این نسخه overlay نیست. */
function toZoneFallback(spec: PatternOverlaySpec, startTs: number): Record<string, unknown> {
  const color = patternOverlayColor(spec);
  const a = spec.points[0].value;
  const b = spec.points.length > 1 ? spec.points[1].value : a;
  const lastTs = spec.points.length > 1 ? (spec.points[1].timestamp || startTs) : startTs;
  return {
    name: 'priceChannelLine',
    groupId: PATTERN_GROUP_ID,
    lock: true,
    points: [{ timestamp: startTs, value: a }, { timestamp: lastTs, value: b }],
    styles: { line: { color, size: 1, style: 'dashed' } },
  };
}

export const KLineChartWrapper: React.FC<ChartProps> = ({
  initialSymbol = 'خودرو',
  initialName = 'ایران خودرو',
  initialMarket = 'بورس',
  boardRow,
  replayActive,
  onToggleReplay,
  onOpenSettings,
  onSymbolChange,
  onTimeframeChange,
  onAdjustmentChange,
}) => {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const theme = useUiStore((s) => s.theme);
  // لِجِندِ الگوهای فعالِ FTS روی چارت (رنگِ هر الگو از تنظیماتِ کاربر)
  const [activePatterns, setActivePatterns] = useState<{ kind: string; color: string; label: string }[]>([]);
  const [isPatternLegendCollapsed, setIsPatternLegendCollapsed] = useState<boolean>(false);
  const chartRef = useRef<Chart | null>(null);

  // استیت‌های نماد جاری
  const [currentSymbol, setCurrentSymbol] = useState<string>(initialSymbol);
  // همگام‌سازی با تغییرِ نماد از بیرون (سایدبار/واچ‌لیست/URL):
  // بدونِ این، چارت نمادِ اولیه را قفل می‌کرد و انتخاب‌های بیرونی بی‌اثر بودند.
  useEffect(() => {
    setCurrentSymbol((prev) => (initialSymbol && initialSymbol !== prev ? initialSymbol : prev));
  }, [initialSymbol]);

  // گوش دادن به تغییرات وضعیت تمام‌صفحه و ری‌سایز فوری و در فریم بعدی
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isFs = !!(
        document.fullscreenElement ||
        (document as any).webkitFullscreenElement ||
        (document as any).mozFullScreenElement ||
        (document as any).msFullscreenElement
      );
      setIsFullscreen(isFs);
      chartRef.current?.resize();
      requestAnimationFrame(() => {
        chartRef.current?.resize();
      });
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);
  const [currentName, setCurrentName] = useState<string>(initialName);
  const [currentMarket, setCurrentMarket] = useState<string>(initialMarket);
  const [isSymbolSearchOpen, setIsSymbolSearchOpen] = useState<boolean>(false);

  // استیت‌های نوار بالا
  const [activeTimeframe, setActiveTimeframe] = useState<Timeframe>('D');
  const [activeCandleType, setActiveCandleType] = useState<string>('candle_solid');
  const [activeAdjustment, setActiveAdjustment] = useState<AdjustmentMode>('combined');
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showIndicatorsModal, setShowIndicatorsModal] = useState<boolean>(false);

  // استیت‌های نوار رسم چپ
  const [activeToolId, setActiveToolId] = useState<string | null>('crosshair');
  const [isMagnetActive, setIsMagnetActive] = useState<boolean>(false);
  const [isDrawingLocked, setIsDrawingLocked] = useState<boolean>(false);
  const [isDrawingsHidden, setIsDrawingsHidden] = useState<boolean>(false);

  // نوار شناور تنظیمات المان انتخاب‌شده
  const [selectedOverlayId, setSelectedOverlayId] = useState<string | null>(null);
  const selectedOverlayIdRef = useRef<string | null>(selectedOverlayId);
  selectedOverlayIdRef.current = selectedOverlayId;
  const [selectedOverlayName, setSelectedOverlayName] = useState<string>('');
  const [overlayColor, setOverlayColor] = useState<string>('#2962ff');
  const [overlayWidth, setOverlayWidth] = useState<number>(2);
  const [overlayStyle, setOverlayStyle] = useState<'solid' | 'dashed' | 'dotted'>('solid');
  const [isOverlayLocked, setIsOverlayLocked] = useState<boolean>(false);

  // استیت‌های جامع تنظیمات چارت از ftsConfigStore (با دسترسی مستقیم به view و مقیاس‌ها)
  const ftsView = useFtsConfigStore((s) => s.view);
  const ftsPriceScale = useFtsConfigStore((s) => s.priceScale);
  const ftsChartType = useFtsConfigStore((s) => s.chartType);
  const ftsShowGrid = useFtsConfigStore((s) => s.showGrid);
  const ftsShowCrosshair = useFtsConfigStore((s) => s.showCrosshair);

  const [activeRange, setActiveRange] = useState<string>('1Y');
  const [isLogScale, setIsLogScale] = useState<boolean>(ftsPriceScale === 'logarithm');
  const [isAutoScale, setIsAutoScale] = useState<boolean>(true);
  const [isDepthOpen, setIsDepthOpen] = useState<boolean>(false);
  const [isChartReady, setIsChartReady] = useState<boolean>(false);

  // استیت ابزار خط‌کش / اندازه‌گیری (Measure / Ruler Tool)
  const [measureState, setMeasureState] = useState<{
    isActive: boolean;
    startX: number;
    startY: number;
    startPrice: number;
    startTs: number;
    startIdx: number;
    currX: number;
    currY: number;
    currPrice: number;
    currTs: number;
    currIdx: number;
  } | null>(null);
  const isMeasuringRef = useRef<boolean>(false);

  useEffect(() => {
    setIsLogScale(ftsPriceScale === 'logarithm');
  }, [ftsPriceScale]);

  // داده‌های چارت
  const [rawCandles, setRawCandles] = useState<KLineData[]>([]);
  const [corporateActions, setCorporateActions] = useState<CorporateAction[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [hasData, setHasData] = useState<boolean>(true);

  // استراتژی FTS
  const [isFtsActive, setIsFtsActive] = useState<boolean>(true);
  const [ftsAnalysis, setFtsAnalysis] = useState<FtsAnalysisResult | null>(null);

  // اندیکاتورهای فعال
  const [indicators, setIndicators] = useState<{ [key: string]: boolean }>({
    VOL: true,
    MA: false,
    EMA: false,
    RSI: false,
    MACD: false,
    BOLL: false,
  });

  // مپ کردن داده‌های تعدیل‌شده
  const adjustedCandles = useMemo(() => {
    return applyAdjustmentToCandles(rawCandles, corporateActions, activeAdjustment);
  }, [rawCandles, corporateActions, activeAdjustment]);

  // رفرنس پایدار به دیتای جاری کندل‌ها جهت پیشگیری از closure قدیمی در دیتا لودر
  const adjustedCandlesRef = useRef<KLineData[]>(adjustedCandles);
  adjustedCandlesRef.current = adjustedCandles;

  // کندل‌های نمایشی: سریِ روزانهٔ تعدیل‌شده روی بازهٔ انتخابی تجمیع می‌شود.
  // KLineCharts خودش هیچ بازآرایی‌ای انجام نمی‌دهد؛ setPeriod فقط برچسب محور را
  // عوض می‌کند، پس اگر تجمیع اینجا انجام نشود نمای هفتگی همان کندل روزانه است.
  const displayCandles = useMemo(
    () => aggregateCandles(adjustedCandles, activeTimeframe),
    [adjustedCandles, activeTimeframe]
  );
  const displayCandlesRef = useRef<KLineData[]>(displayCandles);
  displayCandlesRef.current = displayCandles;

  // اجرای تحلیل FTS روی داده‌های تعدیل‌شده
  useEffect(() => {
    if (adjustedCandles.length > 0) {
      const result = analyzeFts(adjustedCandles);
      setFtsAnalysis(result);
    } else {
      setFtsAnalysis(null);
    }
  }, [adjustedCandles]);

  // ۱. دریافت داده‌های کندل از بک‌اند (با رعایت قرارداد، فال‌بک چندلایه و نگاشت دفاعی)
  const fetchCandleData = useCallback(async (symbol: string) => {
    setIsLoading(true);
    try {
      let url = `/api/chart/${encodeURIComponent(symbol)}`;
      if (symbol === 'شاخص کل' || symbol === 'TEDPIX') {
        url = '/api/index/tedpix?limit=0';
      }

      let res: Response | null = null;
      let json: any = null;
      try {
        res = await fetch(url);
        if (res.ok) {
          json = await res.json();
        }
      } catch {
        // خطای شبکه - تلاش با اندپوینت محلی
      }

      let rawList = Array.isArray(json) ? json : (json?.candles || json?.data || []);

      // فال‌بک لایه ۲: اگر از اندپوینت اول پاسخی نیامد، خطا داد، یا فقط یک کندل برگشت (باگ تک‌خط عمودی):
      // فوراً از اندپوینت /api/history (دیتابیس محلی چند صد کندلی) واکشی می‌کنیم
      if (!Array.isArray(rawList) || rawList.length <= 1) {
        try {
          const histUrl = `/api/history/${encodeURIComponent(symbol)}`;
          const histRes = await fetch(histUrl);
          if (histRes.ok) {
            const histJson = await histRes.json();
            const histList = Array.isArray(histJson) ? histJson : (histJson?.candles || histJson?.data || []);
            if (Array.isArray(histList) && histList.length > 1) {
              json = histJson;
              rawList = histList;
            }
          }
        } catch {
          // خطا در فال‌بک دوم
        }
      }

      // فال‌بک لایه ۳: اگر هنوز داده‌ای یافت نشد، تلاش با /api/chart-db
      if (!Array.isArray(rawList) || rawList.length === 0) {
        try {
          const fallbackUrl = (symbol === 'شاخص کل' || symbol === 'TEDPIX')
            ? '/api/chart-db/فولاد'
            : `/api/chart-db/${encodeURIComponent(symbol)}`;
          const fbRes = await fetch(fallbackUrl);
          if (fbRes.ok) {
            const fbJson = await fbRes.json();
            const fbList = Array.isArray(fbJson) ? fbJson : (fbJson?.candles || fbJson?.data || []);
            if (Array.isArray(fbList) && fbList.length > 0) {
              json = fbJson;
              rawList = fbList;
            }
          }
        } catch {
          // خطا در فال‌بک سوم
        }
      }

      const rawEvents = json?.adjustEvents || json?.adjust_events || [];
      // حجم: سرور حجم را جدا در volumes=[{time,value}] می‌دهد؛ با کلیدِ تاریخ به کندل‌ها
      // می‌چسبانیم تا پنل حجم (VOL) مثل تریدینگ‌ویو پر شود.
      const volByTime: Record<string, number> = {};
      const rawVols = Array.isArray(json?.volumes) ? json.volumes : [];
      for (const v of rawVols) {
        if (v && typeof v.time === 'string') volByTime[v.time] = Number(v.value ?? v.volume ?? 0);
      }

      if (!Array.isArray(rawList) || rawList.length === 0) {
        setRawCandles([]);
        setHasData(false);
        setIsLoading(false);
        return;
      }

      // نگاشت دفاعی به KLineData استاندارد v10 با استفاده از parseCandleTimestamp و فیلتر کندل‌های نامعتبر
      const parsedCandles: KLineData[] = rawList
        .map((c: any) => {
          const ts = parseCandleTimestamp(c.timestamp ?? c.time ?? c.date ?? c.dateStr);

          const open = Number(c.open ?? c.o ?? 0);
          const high = Number(c.high ?? c.h ?? open);
          const low = Number(c.low ?? c.l ?? open);
          const close = Number(c.close ?? c.c ?? open);
          const volume = (typeof c.time === 'string' && volByTime[c.time] !== undefined)
            ? volByTime[c.time]
            : (c.volume !== undefined ? Number(c.volume ?? c.v ?? 0) : undefined);
          const turnover = c.turnover !== undefined ? Number(c.turnover ?? 0) : undefined;

          return { timestamp: ts, open, high, low, close, volume, turnover };
        })
        .filter((c: KLineData) =>
          Number.isFinite(c.timestamp) && c.timestamp > 0 &&
          Number.isFinite(c.open) && c.open > 0 &&
          Number.isFinite(c.high) && c.high > 0 &&
          Number.isFinite(c.low) && c.low > 0 &&
          Number.isFinite(c.close) && c.close > 0
        )
        .sort((a: KLineData, b: KLineData) => a.timestamp - b.timestamp);

      // نگاشت رویدادهای مجمع و تعدیل
      const parsedActions = mapBackendAdjustEvents(rawEvents);

      setCorporateActions(parsedActions);
      setRawCandles(parsedCandles);
      setHasData(parsedCandles.length > 0);
    } catch (e) {
      setRawCandles([]);
      setHasData(false);
    } finally {
      setIsLoading(false);
    }
  }, []);


  // واکشی اولیه دیتا هنگام تغییر نماد
  useEffect(() => {
    fetchCandleData(currentSymbol);
  }, [currentSymbol, fetchCandleData]);

  // --- فاز ۳ (wiring): ماندگاری ترسیم‌ها + میانبرها + مگنت ---
  const magnetRef = useRef(isMagnetActive);
  magnetRef.current = isMagnetActive;
  const candlesRef = useRef<KLineData[]>(adjustedCandles);
  candlesRef.current = adjustedCandles;
  const drawHistRef = useRef(initHistory<StoredOverlay[]>([]));

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const snapshot = (): StoredOverlay[] => {
      try {
        const all = chart.getOverlays() as { id?: string; name?: string; groupId?: string; points?: unknown; styles?: unknown; extendData?: unknown }[];
        return all
          .filter((o) => o && typeof o.name === 'string' &&
            (o.groupId === 'fts-draw' || (!o.groupId && !['VOL', 'MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'fts_strategy_overlays', 'fts_pattern_overlays', 'fts_corp_actions'].includes(o.name))))
          .map((o) => ({
            name: o.name as string,
            groupId: 'fts-draw',
            points: (o.points ?? []) as StoredOverlay['points'],
            ...(o.styles ? { styles: o.styles as Record<string, unknown> } : {}),
            ...(o.extendData ? { extendData: o.extendData as Record<string, unknown> } : {}),
          }));
      } catch (e) {
        void e;
        return [];
      }
    };

    const applySnapshot = (rows: StoredOverlay[]) => {
      try {
        chart.removeOverlay({ groupId: 'fts-draw' });
        rows.forEach((o) => chart.createOverlay({ ...o, groupId: 'fts-draw' } as never));
      } catch (e) {
        void e;
      }
    };

    // ۱) ابتدا پاکسازی قطعی ترسیم‌های نماد قبلی از روی چارت
    try {
      chart.removeOverlay({ groupId: 'fts-draw' });
    } catch {
      // safe
    }

    // ۲) بازیابی ترسیم‌های اختصاصی این نماد (کلید اختصاصی fts.drawings.v1.{symbol} یا تایم‌فریم)
    const symDrawings = loadSymbolDrawings(currentSymbol);
    const restored = symDrawings.length > 0 ? symDrawings : loadDrawings(currentSymbol, activeTimeframe);
    if (restored.length > 0) {
      applySnapshot(restored);
    }
    drawHistRef.current = initHistory(restored);

    const maybeSnap = () => {
      if (!magnetRef.current) return;
      const candles = candlesRef.current;
      if (!candles || candles.length === 0) return;
      try {
        const all = chart.getOverlays() as { id?: string; points?: { timestamp?: number; value?: number }[]; name?: string }[];
        const last = all[all.length - 1];
        if (!last?.id || !Array.isArray(last.points) || last.points.length === 0) return;
        const snapped = last.points.map((p) => {
          if (typeof p.timestamp !== 'number' || typeof p.value !== 'number') return p;
          const idx = candles.reduce((best, c, i) =>
            Math.abs(c.timestamp - (p.timestamp as number)) < Math.abs(candles[best].timestamp - (p.timestamp as number)) ? i : best, 0);
          const c = candles[idx];
          const r = snapToOhlc(p.value, { open: c.open, high: c.high, low: c.low, close: c.close }, 0.4);
          return r.snapped ? { ...p, value: r.price } : p;
        });
        chart.overrideOverlay({ id: last.id, points: snapped } as never);
      } catch (e) {
        void e;
      }
    };

    // ۳) ذخیرهٔ خودکار تغییرات ترسیم در دو سطح نماد و تایم‌فریم + اعمال مگنت
    const tick = () => {
      maybeSnap();
      const snap = snapshot();
      const h = drawHistRef.current;
      if (JSON.stringify(snap) !== JSON.stringify(h.present)) {
        drawHistRef.current = commitHistory(h, snap);
        saveSymbolDrawings(currentSymbol, snap);
        saveDrawings(currentSymbol, activeTimeframe, snap);
      }
    };
    const timer = setInterval(tick, 2000);

    // ۳) میانبرها: Delete/Backspace حذف المان انتخاب‌شده، Esc لغو رسم، Ctrl+Z/Y (و Ctrl+Shift+Z) Undo/Redo
    const onKey = (ev: KeyboardEvent) => {
      const tag = ((ev.target as HTMLElement | null)?.tagName ?? '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (ev.key === 'Escape') {
        setActiveToolId('crosshair');
        setSelectedOverlayId(null);
        setMeasureState(null);
        return;
      }

      if (ev.key === 'Delete' || ev.key === 'Backspace') {
        try {
          const selectedId = selectedOverlayIdRef.current;
          if (selectedId) {
            chart.removeOverlay({ id: selectedId } as never);
            setSelectedOverlayId(null);
          } else {
            const all = chart.getOverlays() as { id?: string }[];
            const last = all[all.length - 1];
            if (last?.id) chart.removeOverlay({ id: last.id });
          }
        } catch (e) {
          void e;
        }
        return;
      }
      if ((ev.ctrlKey || ev.metaKey) && ['z', 'Z', 'y', 'Y'].includes(ev.key)) {
        ev.preventDefault();
        const isRedo = ev.key.toLowerCase() === 'y' || ev.shiftKey;
        const h = drawHistRef.current;
        const next = isRedo ? redoHistory(h) : undoHistory(h);
        if (next !== h) {
          drawHistRef.current = next;
          applySnapshot(next.present);
          saveDrawings(currentSymbol, activeTimeframe, next.present);
        }
      }
    };
    window.addEventListener('keydown', onKey);

    return () => {
      clearInterval(timer);
      window.removeEventListener('keydown', onKey);
    };
  }, [currentSymbol, activeTimeframe, isChartReady]);

  // ۲. راه‌اندازی اولیه KLineChart مطابق با KlineCharts v10.0.3
  useEffect(() => {
    if (!chartContainerRef.current) return;

    // ثبت اورلی‌های سفارشی FTS (شامل tvFibLog و ftsCorpAction)
    try {
      const regFn = (klinecharts as any).registerOverlay ?? (typeof window !== 'undefined' ? (window as any).klinecharts?.registerOverlay : undefined);
      if (typeof regFn === 'function') {
        registerFtsOverlays({ registerOverlay: regFn });
      }
    } catch {
      // safe idempotent
    }

    // init در v10 با layout.yAxis و formatter
    const chart = init(chartContainerRef.current, {
      layout: {
        barSpaceLimit: { min: 2, max: 40 },
        yAxis: { position: 'right', inside: false }
      },
      thousandsSeparator: { sign: ',' },
      formatter: {
        formatDate: ({ timestamp, type }) => formatJalali(timestamp, type)
      },
      timezone: 'Asia/Tehran',
      styles: (theme === 'light' ? nahayatNegarLightTheme : nahayatNegarDarkTheme) as never
    });

    if (!chart) return;
    chartRef.current = chart;
    setIsChartReady(true);

    // ثبت دیتا لودر در v10 (جایگزین قطعی applyNewData)
    chart.setDataLoader({
      getBars: ({ callback }) => {
        // بازگرداندن دیتای جاری کندل‌ها از طریق ref جهت پیشگیری از آرایه خالی
        callback(displayCandlesRef.current, { forward: false, backward: false });
      }
    });

    // تنظیم سمبل و بازه زمانی
    chart.setSymbol({
      ticker: currentSymbol,
      pricePrecision: 0,
      volumePrecision: 0
    });
    chart.setPeriod(timeframePeriod(activeTimeframe));

    if (displayCandlesRef.current.length > 0) {
      chart.resetData();
      chart.scrollToRealTime();
    }

    // ایجاد اندیکاتور حجم پیش‌فرض در پنجره فرعی
    chart.createIndicator({ name: 'VOL', id: 'sub_pane_vol', paneId: 'sub_pane_vol' }, false);
    chart.setPaneOptions({ id: 'sub_pane_vol', height: 100, minHeight: 85 });
    chart.setStyles({
      indicator: {
        bars: [{ upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#787b86' }],
        lines: [
          { style: 'solid', smooth: true, size: 1.5, color: '#f59e0b' },
          { style: 'solid', smooth: true, size: 1.5, color: '#2962ff' },
          { style: 'solid', smooth: true, size: 1.5, color: '#ab47bc' }
        ]
      }
    } as never);

    // پاسخ به تغییر سایز
    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);
    // ResizeObserver روی کانتینر تا چارت فوراً کل فضای آزاد را بگیرد (چیدمان flex)
    // همچنین با تاخیر ۲۲۰ میلی‌ثانیه برای همگامی دقیق با ترنزیشن ۲۰۰ میلی‌ثانیه‌ای پدینگ سایدبار/داور
    let ro: ResizeObserver | null = null;
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    try {
      if (chartContainerRef.current) {
        ro = new ResizeObserver(() => {
          try {
            chart.resize();
            if (resizeTimer) clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
              try {
                chart.resize();
              } catch (e) {
                void e;
              }
            }, 220);
          } catch (e) {
            void e;
          }
        });
        ro.observe(chartContainerRef.current);
      }
    } catch (e) {
      ro = null;
      void e;
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      if (resizeTimer) clearTimeout(resizeTimer);
      try {
        ro?.disconnect();
      } catch (e) {
        void e;
      }
      if (chartContainerRef.current) {
        dispose(chartContainerRef.current);
      }
      setIsChartReady(false);
      chartRef.current = null;
    };
  }, []); // فقط یک‌بار هنگام Mount شدن کامپوننت

  // همگام‌سازی زنده سبک چارت با تم فعال (روشن/تاریک) و تنظیمات پیشرفته ftsConfigStore
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const isLight = theme === 'light';
    const baseTheme = isLight ? nahayatNegarLightTheme : nahayatNegarDarkTheme;

    // ۱. استخراج رنگ‌های کندل با پیش‌فرض‌های امن و شفافیت صفر (کنتراست بالا در هر دو تم)
    const rawUp = ftsView?.candleUp;
    const rawDown = ftsView?.candleDown;
    const candleUpColor = (rawUp && rawUp !== 'transparent') ? rawUp : '#089981';
    const candleDownColor = (rawDown && rawDown !== 'transparent') ? rawDown : '#f23645';

    const showBorders = ftsView?.showBorders !== false;
    const rawBorderUp = ftsView?.borderUp;
    const rawBorderDown = ftsView?.borderDown;
    const borderUpColor = showBorders
      ? ((rawBorderUp && rawBorderUp !== 'transparent') ? rawBorderUp : candleUpColor)
      : candleUpColor;
    const borderDownColor = showBorders
      ? ((rawBorderDown && rawBorderDown !== 'transparent') ? rawBorderDown : candleDownColor)
      : candleDownColor;

    const showWicks = ftsView?.showWicks !== false;
    const rawWickUp = ftsView?.wickUp;
    const rawWickDown = ftsView?.wickDown;
    const wickUpColor = showWicks
      ? ((rawWickUp && rawWickUp !== 'transparent') ? rawWickUp : candleUpColor)
      : 'transparent';
    const wickDownColor = showWicks
      ? ((rawWickDown && rawWickDown !== 'transparent') ? rawWickDown : candleDownColor)
      : 'transparent';

    // ۲. نگاشت قطعی نوع کندل به یکی از ۶ مقدار مجاز کتابخانه KlineCharts v10
    const validCandleType: 'candle_solid' | 'candle_stroke' | 'candle_up_stroke' | 'candle_down_stroke' | 'ohlc' | 'area' =
      ftsChartType === 'area' ? 'area'
      : ftsChartType === 'ohlc' ? 'ohlc'
      : ftsChartType === 'candle_stroke' ? 'candle_stroke'
      : ftsChartType === 'candle_up_stroke' ? 'candle_up_stroke'
      : ftsChartType === 'candle_down_stroke' ? 'candle_down_stroke'
      : 'candle_solid';

    // ۳. استخراج رنگ پس‌زمینه چارت بر مبنای تنظیمات ftsView و هماهنگی با تم
    const bgSetting = ftsView?.background;
    const chartBgColor =
      bgSetting === 'light' ? '#ffffff'
      : bgSetting === 'classic' ? '#1e222d'
      : bgSetting === 'custom' ? (ftsView?.customBgColor || (isLight ? '#ffffff' : '#131722'))
      : (isLight ? '#ffffff' : '#131722');

    if (chartContainerRef.current) {
      chartContainerRef.current.style.backgroundColor = chartBgColor;
    }

    // ۴. رنگ و سبک خطوط گرید و نشانگر کراس‌هیر
    const defaultGridColor = isLight ? '#f0f3fa' : '#242731';
    const gridColor = ftsView?.gridColor && ftsView?.gridColor !== '#1e222d' && ftsView?.gridColor !== '#242731'
      ? ftsView.gridColor
      : defaultGridColor;
    const gridStyle = ftsView?.gridStyle === 'dashed' ? 'dashed'
      : ftsView?.gridStyle === 'dotted' ? 'dotted'
      : 'solid';
    const gridDashedValue = ftsView?.gridStyle === 'dotted' ? [2, 2] : [4, 4];
    const isGridNone = ftsView?.gridStyle === 'none';
    const showGridLines = ftsShowGrid && !isGridNone;
    const showHorz = showGridLines && (ftsView?.showGridHorz !== false);
    const showVert = showGridLines && (ftsView?.showGridVert !== false);

    const crosshairStyle = ftsView?.crosshairStyle === 'solid' ? 'solid'
      : ftsView?.crosshairStyle === 'dotted' ? 'dotted'
      : 'dashed';
    const crosshairDashedValue = ftsView?.crosshairStyle === 'dotted' ? [2, 2] : [4, 4];

    try {
      chart.setStyles({
        ...baseTheme,
        separator: {
          size: 1,
          color: gridColor,
          fill: true,
          activeBackgroundColor: 'rgba(41, 98, 255, 0.2)'
        },
        xAxis: {
          size: 32,
          axisLine: {
            show: true,
            color: isLight ? '#e0e3eb' : '#2a2e39',
            size: 1
          },
          tickText: {
            size: 12,
            family: 'Vazirmatn',
            color: isLight ? '#434651' : '#d1d4dc',
            marginStart: 4,
            marginEnd: 4
          },
          tickLine: {
            show: true,
            length: 4,
            color: isLight ? '#e0e3eb' : '#2a2e39'
          }
        },
        grid: {
          show: showGridLines,
          horizontal: {
            show: showHorz,
            color: gridColor,
            style: gridStyle,
            dashedValue: gridDashedValue,
            size: 1
          },
          vertical: {
            show: showVert,
            color: gridColor,
            style: gridStyle,
            dashedValue: gridDashedValue,
            size: 1
          }
        },
        candle: {
          type: validCandleType,
          bar: {
            upColor: candleUpColor,
            downColor: candleDownColor,
            noChangeColor: '#888888',
            upBorderColor: borderUpColor,
            downBorderColor: borderDownColor,
            noChangeBorderColor: '#888888',
            upWickColor: wickUpColor,
            downWickColor: wickDownColor,
            noChangeWickColor: '#888888'
          },
          tooltip: {
            showRule: ftsView?.statusShowOhlc === false ? 'none' : 'always',
            showType: 'standard'
          },
          area: {
            lineSize: 2,
            lineColor: '#2962ff',
            value: 'close',
            fillColor: [
              { offset: 0, color: 'rgba(41, 98, 255, 0.28)' },
              { offset: 1, color: 'rgba(41, 98, 255, 0.00)' }
            ]
          },
          priceMark: {
            show: true,
            last: {
              show: true,
              upColor: candleUpColor,
              downColor: candleDownColor,
              noChangeColor: '#888888',
              line: { show: true, style: 'dashed', dashedValue: [3, 3], size: 1 },
              text: { show: true, size: 11, family: 'Vazirmatn', color: '#ffffff' }
            },
            high: {
              show: true,
              color: isLight ? '#64748b' : '#d1d4dc',
              text: { size: 10, family: 'Vazirmatn' }
            },
            low: {
              show: true,
              color: isLight ? '#64748b' : '#d1d4dc',
              text: { size: 10, family: 'Vazirmatn' }
            }
          }
        },
        crosshair: {
          show: ftsShowCrosshair,
          horizontal: {
            show: ftsShowCrosshair,
            line: {
              show: ftsShowCrosshair,
              style: crosshairStyle,
              dashedValue: crosshairDashedValue,
              size: 1,
              color: isLight ? '#94a3b8' : '#787b86'
            }
          },
          vertical: {
            show: ftsShowCrosshair,
            line: {
              show: ftsShowCrosshair,
              style: crosshairStyle,
              dashedValue: crosshairDashedValue,
              size: 1,
              color: isLight ? '#94a3b8' : '#787b86'
            }
          }
        },
        indicator: {
          bars: [{ upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#787b86' }],
          lines: [
            { style: 'solid', smooth: true, size: 1.5, color: '#f59e0b' },
            { style: 'solid', smooth: true, size: 1.5, color: '#2962ff' },
            { style: 'solid', smooth: true, size: 1.5, color: '#ab47bc' }
          ],
          tooltip: {
            showRule: ftsView?.statusShowIndicators === false ? 'none' : 'always',
            showType: 'standard',
            text: {
              size: 11,
              family: 'Vazirmatn',
              color: isLight ? '#131722' : '#d1d4dc',
              marginStart: 6,
              marginEnd: 6
            }
          }
        },
        yAxis: {
          reverse: !!ftsView?.yAxisReverse,
          inside: !!ftsView?.yAxisInside,
          position: ftsView?.priceScalePos ?? 'right',
          axisLine: {
            show: true,
            color: isLight ? '#e0e3eb' : '#2a2e39',
            size: 1
          },
          tickLine: {
            show: true,
            length: 3,
            color: isLight ? '#e0e3eb' : '#2a2e39'
          },
          tickText: {
            color: isLight ? '#64748b' : '#d1d4dc',
            size: 11,
            family: 'Vazirmatn'
          }
        }
      } as never);

      try {
        chart.setPaneOptions({ id: 'sub_pane_vol', height: 110, minHeight: 90 });
      } catch (e) {
        void e;
      }

      if (ftsView?.timezone) {
        (chart as any).setTimezone?.(ftsView.timezone);
      }

      // ۴. مقیاس قیمت — استفاده از نام استاندارد رجیسترشده در v10 (normal / logarithm / percentage)
      const yAxisName = ftsPriceScale === 'logarithm'
        ? 'logarithm'
        : ftsPriceScale === 'percentage'
        ? 'percentage'
        : 'normal';

      chart.overrideYAxis({
        paneId: 'candle_pane',
        name: yAxisName
      } as never);

      // ۵. تزریق فوری و بازنشانی کندل‌های جاری جهت رندر بی‌درنگ و تضمین عدم خالی ماندن بوم
      if (displayCandlesRef.current && displayCandlesRef.current.length > 0) {
        chart.setDataLoader({
          getBars: ({ callback }) => {
            callback(displayCandlesRef.current, { forward: false, backward: false });
          }
        });
        chart.resetData();
        chart.scrollToRealTime();
      }
    } catch (e) {
      void e;
    }
  }, [theme, ftsView, ftsPriceScale, ftsChartType, ftsShowGrid, ftsShowCrosshair]);

  // ۳. ارسال دیتای جدید به کلاینت KLineChart از طریق setDataLoader در v10
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // بازنشانی و فراخوانی مجدد لودر دیتا در v10
    chart.setDataLoader({
      getBars: ({ callback }) => {
        callback(displayCandles, { forward: false, backward: false });
      }
    });

    chart.setSymbol({
      ticker: currentSymbol,
      pricePrecision: 0,
      volumePrecision: 0
    });
    chart.setPeriod(timeframePeriod(activeTimeframe));

    chart.resetData();
    chart.setOffsetRightDistance?.(50);
    chart.scrollToRealTime();

    const raf = requestAnimationFrame(() => {
      try {
        chart.resize();
        chart.scrollToRealTime();
      } catch (e) {
        void e;
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [displayCandles, currentSymbol]);


  // ۴. رسم و پاک‌سازی اورلی‌های تحلیلی استراتژی FTS
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !isFtsActive || !ftsAnalysis) return;

    // شناسه گروه اورلی‌های FTS
    const ftsGroupId = 'fts_strategy_overlays';
    chart.removeOverlay({ groupId: ftsGroupId } as never);

    // رسم زون‌های فیبوی لگاریتمی FTS (زون ۰.۳۳ تا ۰.۴۰ و زون ۰.۶۱۸ تا ۰.۷۰)
    try {
      ftsAnalysis.logFiboZones.forEach((z) => {
        if (z.priceStart > 0 && z.priceEnd > 0) {
          chart.createOverlay({
            name: 'straightLine',
            groupId: ftsGroupId,
            lock: true,
            points: [
              { timestamp: Date.now(), value: z.priceStart },
              { timestamp: Date.now(), value: z.priceEnd }
            ],
            styles: {
              line: {
                style: 'dashed',
                size: 1,
                color: z.ratioStart >= 0.6 ? '#2962ff' : '#ffab00'
              }
            }
          } as never);
        }
      });

      // رسم مارکرهای ستاپ FTS (جت، پولبک، CHoCH، نقطه‌زنی، کف‌دوقلو) با سیستم Collision Avoidance & Stacking Offset
      // ۱. گروه‌بندی بر اساس زمان/کندل جهت تشخیص هم‌پوشانی
      const markersByTime = new Map<number, typeof ftsAnalysis.setupMarkers>();
      for (const m of ftsAnalysis.setupMarkers) {
        const bucket = markersByTime.get(m.timestamp) ?? [];
        bucket.push(m);
        markersByTime.set(m.timestamp, bucket);
      }

      // ۲. تجمیع برچسب‌های هم‌زمان در یک کندل و تفکیک سطوح بالا (مقاومت/جت) و پایین (حمایت/نقطه‌زنی/کف‌دوقلو/پولبک)
      const processedMarkers: Array<{
        timestamp: number;
        price: number;
        label: string;
        color: string;
      }> = [];

      markersByTime.forEach((group, ts) => {
        const lowGroup = group.filter((m) => m.name !== 'جت');
        const highGroup = group.filter((m) => m.name === 'جت');

        if (lowGroup.length > 0) {
          const uniqueNames = Array.from(new Set(lowGroup.map((m) => m.name)));
          const combinedLabel = uniqueNames.join(' • ');
          const basePrice = Math.min(...lowGroup.map((m) => m.price));
          processedMarkers.push({
            timestamp: ts,
            price: basePrice,
            label: combinedLabel,
            color: '#089981',
          });
        }

        if (highGroup.length > 0) {
          const uniqueNames = Array.from(new Set(highGroup.map((m) => m.name)));
          const combinedLabel = uniqueNames.join(' • ');
          const basePrice = Math.max(...highGroup.map((m) => m.price));
          processedMarkers.push({
            timestamp: ts,
            price: basePrice,
            label: combinedLabel,
            color: '#ffab00',
          });
        }
      });

      // ۳. اعمال Stacking Offset بین مارکرهای نزدیک جهت جلوگیری از برخورد بصری
      processedMarkers.sort((a, b) => a.timestamp - b.timestamp);
      for (let i = 1; i < processedMarkers.length; i++) {
        const prev = processedMarkers[i - 1];
        const curr = processedMarkers[i];
        const timeDiff = Math.abs(curr.timestamp - prev.timestamp);
        if (timeDiff <= 2 * 24 * 60 * 60 * 1000 && Math.abs(curr.price - prev.price) / Math.max(1, prev.price) < 0.025) {
          curr.price = curr.color === '#ffab00' ? curr.price * 1.028 : curr.price * 0.972;
        }
      }

      // ۴. رندر مارکرهای مرتب با برچسب کنتراست بالا و پس‌زمینه خوانا
      processedMarkers.forEach((m) => {
        chart.createOverlay({
          name: 'simpleAnnotation',
          groupId: ftsGroupId,
          lock: true,
          points: [{ timestamp: m.timestamp, value: m.price }],
          extendData: m.label,
          styles: {
            text: {
              color: '#ffffff',
              size: 10.5,
              family: 'Vazirmatn, sans-serif',
              weight: 'bold',
              backgroundColor: m.color === '#089981' ? 'rgba(8, 153, 129, 0.92)' : 'rgba(255, 171, 0, 0.92)',
              borderColor: '#1e222d',
              borderSize: 1,
              borderRadius: 4,
              paddingLeft: 6,
              paddingRight: 6,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
        } as never);
      });
    } catch (e) {
      // مدیریت خطا
    }

    return () => {
      chart.removeOverlay({ groupId: ftsGroupId } as never);
    };
  }, [isFtsActive, ftsAnalysis]);
  // ۵. لایهٔ ۹ الگوی FTS (فاز ۴): موتور الگوها روی کندل‌های تعدیل‌شده + ترسیم واقعی روی چارت
  const patternPrefs = usePatternPrefsStore((s) => s.prefs);
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const clearPatterns = () => {
      try {
        chart.removeOverlay({ groupId: PATTERN_GROUP_ID } as never);
      } catch (e) {
        void e;
      }
    };
    if (adjustedCandles.length === 0) {
      clearPatterns();
      setActivePatterns([]);
      return;
    }

    const opens = adjustedCandles.map((c) => c.open);
    const highs = adjustedCandles.map((c) => c.high);
    const lows = adjustedCandles.map((c) => c.low);
    const closes = adjustedCandles.map((c) => c.close);

    const inputs = {
      jet: detectJet(highs, closes),
      fib: detectFibZigzag(highs, lows),
      choch: detectChochConfirmed(highs, lows, closes),
      pointHunt: detectPointHunt(lows),
      double: detectDoubleBottom(lows, closes),
      headShoulders: detectHeadShoulders(highs),
      thirdPeak: detectThirdPeak(highs, closes),
      ma14Exit: detectMa14Exit(opens, highs, lows, closes),
      hourglass: detectHourglass(closes),
    };
    const specs = buildPatternOverlays(
      inputs,
      patternPrefs,
      adjustedCandles.map((c) => ({ timestamp: c.timestamp })),
    );

    setActivePatterns(
      Array.from(
        new Map(
          specs.map((s) => [
            s.kind,
            { kind: s.kind, color: patternOverlayColor(s), label: PATTERN_LABELS[s.kind] ?? s.kind },
          ]),
        ).values(),
      ),
    );

    clearPatterns();
    const startTs = adjustedCandles[0].timestamp;
    // ارزشِ نشانگرها: اگر مقدار صفر/نامعتبر بود از کندلِ همان زمان بگیر (نقطه‌زنی ⇒ کف، خروج ⇒ بسته)
    // تا نشانگر روی قیمت ۰ و بیرون از دید رسم نشود.
    const priceAt = (ts: number, pick: 'low' | 'close'): number => {
      const row = adjustedCandles.find((c) => c.timestamp >= ts) ?? adjustedCandles[adjustedCandles.length - 1];
      return row ? (pick === 'low' ? row.low : row.close) : 0;
    };
    for (const spec of specs) {
      try {
        if ((spec.kind === 'pointhunt' || spec.kind === 'ma14exit') && !(spec.points[0].value > 0)) {
          spec.points[0].value = priceAt(spec.points[0].timestamp, spec.kind === 'ma14exit' ? 'close' : 'low');
        }
        // زونِ بی‌داده (مثلِ MA52=۰) رسم نشود تا باندِ تختِ بی‌معنا نسازد.
        if (spec.points.length >= 2 && !(spec.points[0].value > 0 || spec.points[1].value > 0)) continue;
        const made = chart.createOverlay(toChartOverlay(spec, startTs) as never);
        // اگر overlayِ زون در این نسخه ثبت نشده بود (مثلاً rect صرفاً figure است) کانال رسم می‌شود.
        if (!made && spec.points.length >= 2) {
          chart.createOverlay(toZoneFallback(spec, startTs) as never);
        }
      } catch (e) {
        void e;
      }
    }

    return clearPatterns;
  }, [adjustedCandles, patternPrefs]);

  // ۶. لایهٔ رویدادهای شرکتی و مجامع (D: سود نقدی DPS، S: افزایش سرمایه سهام جایزه و آورده)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const corpGroupId = 'fts_corp_actions';
    try {
      chart.removeOverlay({ groupId: corpGroupId } as never);
    } catch {
      // safe
    }

    if (ftsView?.showCorporateActions === false || corporateActions.length === 0 || displayCandles.length === 0) {
      return;
    }

    try {
      corporateActions.forEach((action) => {
        // سرور نوعِ رویداد را نمی‌فرستد (فقط نسبتِ گسست قیمت پایه)، پس برچسبِ
        // «سود نقدی» یا «افزایش سرمایه» روی این مارکر ساختگی می‌شد؛ تنها عددِ
        // واقعیِ موجود همان نسبت است و همان نمایش داده می‌شود.
        const matchCandle = displayCandles.find((c) => Math.abs(c.timestamp - action.timestamp) < 24 * 60 * 60 * 1000)
          ?? displayCandles.find((c) => c.timestamp >= action.timestamp);

        if (!matchCandle) return;

        const tooltip = `تعدیل قیمت پایه · ×${
          action.ratio.toLocaleString('fa-IR', { maximumFractionDigits: 4 })
        }`;

        chart.createOverlay({
          name: FTS_CORP_ACTION_OVERLAY,
          groupId: corpGroupId,
          lock: true,
          points: [{ timestamp: matchCandle.timestamp, value: matchCandle.low }],
          extendData: {
            kind: 'A',
            text: tooltip,
            color: '#f59e0b',
          },
        } as never);
      });
    } catch (e) {
      void e;
    }

    return () => {
      try {
        chart.removeOverlay({ groupId: corpGroupId } as never);
      } catch (e) {
        void e;
      }
    };
  }, [corporateActions, displayCandles, ftsView?.showCorporateActions]);

  // هندلرهای رویداد ماوس برای ابزار خط‌کش / اندازه‌گیری (Measure / Ruler Tool)
  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.shiftKey || activeToolId === 'ruler') {
      const rect = chartContainerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const cross = chartRef.current?.getCrosshair();
      const lastCandle = adjustedCandles[adjustedCandles.length - 1];
      const startPrice = cross?.kLineData?.close ?? lastCandle?.close ?? 1000;
      const startTs = cross?.kLineData?.timestamp ?? lastCandle?.timestamp ?? Date.now();
      const startIdx = cross?.dataIndex ?? (adjustedCandles.length - 1);

      isMeasuringRef.current = true;
      setMeasureState({
        isActive: true,
        startX: x,
        startY: y,
        startPrice,
        startTs,
        startIdx,
        currX: x,
        currY: y,
        currPrice: startPrice,
        currTs: startTs,
        currIdx: startIdx,
      });
      return;
    }

    if (measureState?.isActive) {
      setMeasureState(null);
      if (activeToolId === 'ruler') {
        setActiveToolId('crosshair');
      }
    }
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isMeasuringRef.current || !measureState) return;
    const rect = chartContainerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const cross = chartRef.current?.getCrosshair();
    const currPrice = cross?.kLineData?.close ?? measureState.startPrice;
    const currTs = cross?.kLineData?.timestamp ?? measureState.startTs;
    const currIdx = cross?.dataIndex ?? measureState.startIdx;

    setMeasureState((prev) => (prev ? {
      ...prev,
      currX: x,
      currY: y,
      currPrice,
      currTs,
      currIdx,
    } : null));
  };

  const handleCanvasMouseUp = () => {
    if (isMeasuringRef.current) {
      isMeasuringRef.current = false;
      if (measureState && Math.abs(measureState.currX - measureState.startX) < 6 && Math.abs(measureState.currY - measureState.startY) < 6) {
        setMeasureState(null);
        if (activeToolId === 'ruler') {
          setActiveToolId('crosshair');
        }
      }
    }
  };


  // ذخیره فوری ترسیمات جاری در حافظه پیش از تغییر نماد یا تایم‌فریم
  const flushDrawings = useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      const all = chart.getOverlays() as {
        id?: string;
        name?: string;
        groupId?: string;
        points?: { timestamp?: number; value?: number }[];
        lock?: boolean;
        styles?: unknown;
        extendData?: unknown;
      }[];
      const snap: StoredOverlay[] = all
        .filter((o) => o?.groupId === 'fts-draw' && o?.name && Array.isArray(o.points))
        .map((o) => ({
          id: o.id ?? `d_${Math.random().toString(36).slice(2, 8)}`,
          name: o.name as string,
          points: o.points as { timestamp: number; value: number }[],
          lock: !!o.lock,
          styles: o.styles,
          extendData: o.extendData,
        }));
      if (snap.length > 0) {
        saveSymbolDrawings(currentSymbol, snap);
        saveDrawings(currentSymbol, activeTimeframe, snap);
      }
    } catch {
      // safe
    }
  }, [currentSymbol, activeTimeframe]);

  // هندلر تغییر نماد
  const handleSelectSymbol = (sym: SymbolInfo) => {
    flushDrawings();
    setCurrentSymbol(sym.symbol);
    setCurrentName(sym.name);
    setCurrentMarket(sym.market);
    if (onSymbolChange) onSymbolChange(sym);
  };

  // هندلر تغییر تایم‌فریم — تجمیع در displayCandles انجام می‌شود و افکتِ دیتا آن را
  // به چارت می‌دهد؛ این‌جا فقط وضعیت و برچسب محور عوض می‌شود.
  const handleTimeframeChange = (tf: Timeframe) => {
    flushDrawings();
    setActiveTimeframe(tf);
    chartRef.current?.setPeriod(timeframePeriod(tf));
    if (onTimeframeChange) onTimeframeChange(tf);
  };

  // هندلر تغییر استایل کندل
  const handleCandleTypeChange = (type: string) => {
    setActiveCandleType(type);
    const chart = chartRef.current;
    if (!chart) return;

    if (type === 'area') {
      chart.setStyles({ candle: { type: 'area' as never } });
    } else {
      chart.setStyles({ candle: { type: type as never } });
    }
  };

  // هندلر تغییر حالت تعدیل
  const handleAdjustmentChange = (mode: AdjustmentMode) => {
    setActiveAdjustment(mode);
    if (onAdjustmentChange) onAdjustmentChange(mode);
  };

  // هندلر ابزارهای رسم در نوار چپ
  const handleSelectTool = (toolId: string, overlayType: string) => {
    setActiveToolId(toolId);
    const chart = chartRef.current;
    if (!chart) return;

    if (overlayType === 'crosshair') {
      setSelectedOverlayId(null);
      return;
    }

    if (overlayType === 'eraser') {
      chart.removeOverlay({ groupId: 'fts-draw' });
      setSelectedOverlayId(null);
      flushDrawings();
      return;
    }

    // بررسی حالت فیبوناچی لگاریتمی (Logarithmic Fibonacci) بر مبنای تنظیمات یا مقیاس جاری
    let finalOverlayType = overlayType;
    const isLogFib = ftsView?.fibLogarithmic || isLogScale;
    if (toolId.includes('fib') || overlayType === 'fibonacciLine' || overlayType === 'tvFibRetracement') {
      finalOverlayType = isLogFib ? 'tvFibLog' : 'fibonacciLine';
    } else if (toolId === 'ruler') {
      finalOverlayType = 'ftsMeasure';
    } else if (toolId === 'longPosition' || toolId === 'shortPosition') {
      finalOverlayType = 'ftsPosition';
    }

    // ایجاد Overlay در KlineCharts v10 با انتساب قطعی به groupId: 'fts-draw'
    // و جلوگیری از Pan/Scroll شدن بوم چارت در حین رسم و جابجایی المان
    try {
      const lineStyleObj = overlayStyle === 'solid'
        ? { style: 'solid' as const }
        : overlayStyle === 'dotted'
        ? { style: 'dashed' as const, dashedValue: [2, 2] }
        : { style: 'dashed' as const, dashedValue: [6, 6] };

      const id = chart.createOverlay({
        name: finalOverlayType,
        groupId: 'fts-draw',
        lock: isDrawingLocked,
        needDefaultYAxisFigure: toolId === 'horizontalLine' || toolId === 'priceLabel',
        needDefaultXAxisFigure: toolId === 'verticalLine',
        styles: {
          point: {
            color: '#2962ff',
            activeColor: '#1e53e5',
            borderColor: '#ffffff',
            activeBorderColor: '#ffffff',
            borderSize: 1.5,
            radius: 4.5,
            activeRadius: 5.5,
          },
          line: {
            color: overlayColor,
            size: overlayWidth,
            ...lineStyleObj,
          },
          polygon: {
            color: overlayColor + '22',
          },
        },
        onDrawStart: () => {
          chart.setScrollEnabled(false);
        },
        onDrawEnd: () => {
          chart.setScrollEnabled(true);
          flushDrawings();
        },
        onPressedMoveStart: () => {
          chart.setScrollEnabled(false);
        },
        onPressedMoveEnd: () => {
          chart.setScrollEnabled(true);
          flushDrawings();
        },
        onSelected: (params: any) => {
          if (params?.overlay?.id) {
            setSelectedOverlayId(String(params.overlay.id));
            setSelectedOverlayName(params.overlay.name || toolId);
          }
        },
      } as never);

      if (id) {
        setSelectedOverlayId(typeof id === 'string' ? id : String(id));
        setSelectedOverlayName(toolId);
      }
    } catch (e) {
      console.warn('Error creating overlay:', e);
    }
  };

  // هندلرهای نوار شناور تنظیمات المان با overrideOverlay در v10
  const handleColorChange = (c: string) => {
    setOverlayColor(c);
    if (chartRef.current && selectedOverlayId) {
      chartRef.current.overrideOverlay({
        id: selectedOverlayId,
        styles: { line: { color: c }, polygon: { color: c + '22' } }
      } as never);
    }
  };

  const handleWidthChange = (w: number) => {
    setOverlayWidth(w);
    if (chartRef.current && selectedOverlayId) {
      chartRef.current.overrideOverlay({
        id: selectedOverlayId,
        styles: { line: { size: w } }
      } as never);
    }
  };

  const handleStyleChange = (s: 'solid' | 'dashed' | 'dotted') => {
    setOverlayStyle(s);
    if (chartRef.current && selectedOverlayId) {
      const lineStyleObj = s === 'solid'
        ? { style: 'solid' as const, dashedValue: [] }
        : s === 'dotted'
        ? { style: 'dashed' as const, dashedValue: [2, 2] }
        : { style: 'dashed' as const, dashedValue: [6, 6] };

      chartRef.current.overrideOverlay({
        id: selectedOverlayId,
        styles: { line: lineStyleObj }
      } as never);
    }
  };

  const handleToggleOverlayLock = () => {
    const next = !isOverlayLocked;
    setIsOverlayLocked(next);
    if (chartRef.current && selectedOverlayId) {
      chartRef.current.overrideOverlay({
        id: selectedOverlayId,
        lock: next
      } as never);
    }
  };

  const handleDeleteSelectedOverlay = () => {
    if (chartRef.current && selectedOverlayId) {
      chartRef.current.removeOverlay({ id: selectedOverlayId } as never);
      setSelectedOverlayId(null);
    }
  };

  // پاک‌سازی تمام ترسیم‌های اختصاصی نماد
  const handleClearDrawings = () => {
    if (chartRef.current) {
      chartRef.current.removeOverlay({ groupId: 'fts-draw' });
      drawHistRef.current = initHistory([]);
      saveSymbolDrawings(currentSymbol, []);
      saveDrawings(currentSymbol, activeTimeframe, []);
      setSelectedOverlayId(null);
    }
  };

  // کنترل اندیکاتورها در v10: createIndicator / removeIndicator
  const toggleIndicator = (indName: string) => {
    const chart = chartRef.current;
    if (!chart) return;
    const currentState = indicators[indName];

    if (currentState) {
      chart.removeIndicator({ name: indName });
      setIndicators(prev => ({ ...prev, [indName]: false }));
    } else {
      if (['MA', 'EMA', 'BOLL'].includes(indName)) {
        chart.createIndicator({ name: indName, paneId: 'candle_pane' }, true);
      } else {
        chart.createIndicator({ name: indName, paneId: `sub_pane_${indName.toLowerCase()}` });
      }
      setIndicators(prev => ({ ...prev, [indName]: true }));
    }
  };

  // تغییر مقیاس لگاریتمی در v10 با overrideYAxis (name: 'logarithm' | 'normal')
  const toggleLogScale = () => {
    const chart = chartRef.current;
    if (!chart) return;
    const next = !isLogScale;
    setIsLogScale(next);
    useFtsConfigStore.getState().setPriceScale(next ? 'logarithm' : 'normal');
    chart.overrideYAxis({
      paneId: 'candle_pane',
      name: next ? 'logarithm' : 'normal'
    } as never);
  };

  // ریست اسکیل خودکار با اسکرول به زمان حال و بازنشانی محور قیمت
  const handleAutoScale = () => {
    const chart = chartRef.current;
    if (!chart) return;
    try {
      chart.setOffsetRightDistance?.(50);
      chart.scrollToRealTime();
      chart.resize();
    } catch {
      chart.scrollToRealTime();
    }
  };


  // تمام‌صفحه
  const handleToggleFullscreen = () => {
    const el = containerRef.current || chartContainerRef.current?.parentElement;
    const isFs = !!(
      document.fullscreenElement ||
      (document as any).webkitFullscreenElement ||
      (document as any).mozFullScreenElement ||
      (document as any).msFullscreenElement
    );
    if (!isFs) {
      if (el?.requestFullscreen) {
        void el.requestFullscreen();
      } else if ((el as any)?.webkitRequestFullscreen) {
        void (el as any).webkitRequestFullscreen();
      }
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        void document.exitFullscreen();
      } else if ((document as any).webkitExitFullscreen) {
        void (document as any).webkitExitFullscreen();
      }
      setIsFullscreen(false);
    }
  };

  // عکس‌برداری با متد رسمی v10
  const handleTakeSnapshot = () => {
    const chart = chartRef.current;
    if (!chart) return;
    const url = chart.getConvertPictureUrl(true);
    if (url) {
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentSymbol}_chart.png`;
      a.click();
    }
  };

  return (
    <div className="nahayat-negar-container" ref={containerRef}>
      {/* نوار ابزار بالا */}
      <FtsToolbar
        symbolName={currentSymbol}
        companyName={currentName}
        marketName={currentMarket}
        boardRow={boardRow}
        onOpenSymbolSearch={() => setIsSymbolSearchOpen(true)}
        activeTimeframe={activeTimeframe}
        onTimeframeChange={handleTimeframeChange}
        activeCandleType={activeCandleType}
        onCandleTypeChange={handleCandleTypeChange}
        activeAdjustment={activeAdjustment}
        onAdjustmentChange={handleAdjustmentChange}
        onOpenIndicators={() => setShowIndicatorsModal(!showIndicatorsModal)}
        isFtsActive={isFtsActive}
        onToggleFts={() => setIsFtsActive(!isFtsActive)}
        replayActive={replayActive}
        onToggleReplay={onToggleReplay}
        isFullscreen={isFullscreen}
        onToggleFullscreen={handleToggleFullscreen}
        onOpenSettings={onOpenSettings}
        onTakeSnapshot={handleTakeSnapshot}
        onToggleDepth={() => setIsDepthOpen((prev) => !prev)}
        isDepthOpen={isDepthOpen}
      />

      {/* ویجت ۵ مظنه برتر عمق بازار */}
      <MarketDepthWidget
        symbol={currentSymbol}
        boardRow={boardRow}
        isOpen={isDepthOpen}
        onClose={() => setIsDepthOpen(false)}
      />

      {/* نوار شناور تنظیمات المان */}
      <FloatingPropertiesBar
        visible={!!selectedOverlayId}
        selectedToolName={selectedOverlayName}
        currentColor={overlayColor}
        currentWidth={overlayWidth}
        currentStyle={overlayStyle}
        isLocked={isOverlayLocked}
        onColorChange={handleColorChange}
        onWidthChange={handleWidthChange}
        onStyleChange={handleStyleChange}
        onToggleLock={handleToggleOverlayLock}
        onDelete={handleDeleteSelectedOverlay}
        onClose={() => setSelectedOverlayId(null)}
      />

      {/* بدنه چارت: نوار رسم در منتهی‌الیه چپ + بوم چارت */}
      <div className="nn-chart-body" dir="ltr">
        <DrawingToolbar
          activeToolId={activeToolId}
          onSelectTool={handleSelectTool}
          onClearDrawings={() => {
            // ۴) پاک‌کردن ترسیم‌های همین نماد از ذخیره‌سازی هم
            try {
              clearSymbolDrawings(currentSymbol);
            } catch (e) {
              void e;
            }
            handleClearDrawings();
          }}
          isMagnetActive={isMagnetActive}
          onToggleMagnet={() => setIsMagnetActive(!isMagnetActive)}
          isLocked={isDrawingLocked}
          onToggleLock={() => {
            const next = !isDrawingLocked;
            setIsDrawingLocked(next);
            chartRef.current?.setStyles({ overlay: { lock: next } } as never);
          }}
          isHideActive={isDrawingsHidden}
          onToggleHide={() => {
            const next = !isDrawingsHidden;
            setIsDrawingsHidden(next);
            chartRef.current?.setStyles({ overlay: { visible: !next } } as never);
          }}
        />

        <main
          className="nn-canvas-area"
          onMouseDown={handleCanvasMouseDown}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
        >
          {/* هشدار خروج استراتژی FTS */}
          {isFtsActive && ftsAnalysis?.exitSignalMA14 && (
            <div className="nn-fts-exit-alert">
              <span>هشدار خروج FTS: کل کندل زیر میانگین ۱۴ قرار گرفت.</span>
            </div>
          )}

          {/* کانتینر اصلی کتابخانه KlineCharts */}
          {/* کانتینر اصلی کتابخانه KlineCharts با لِجِندِ جمع‌شوندهٔ الگوها */}
          {activePatterns.length > 0 ? (
            isPatternLegendCollapsed ? (
              <div className="nn-pattern-legend" data-testid="fts-pattern-legend">
                <button
                  type="button"
                  className="nn-legend-chip nn-legend-summary-chip"
                  onClick={() => setIsPatternLegendCollapsed(false)}
                  title="نمایش جزئیات الگوها"
                  data-testid="fts-pattern-legend-toggle"
                >
                  <span className="nn-legend-dot" style={{ background: '#2962ff' }} />
                  <span>{activePatterns.length.toLocaleString('fa-IR')} الگوی فعال</span>
                  <span className="nn-legend-chevron">▾</span>
                </button>
              </div>
            ) : (
              <div className="nn-pattern-legend" data-testid="fts-pattern-legend">
                {activePatterns.map((p) => (
                  <span key={p.kind} className="nn-legend-chip">
                    <span className="nn-legend-dot" style={{ background: p.color }} />
                    {p.label}
                  </span>
                ))}
                <button
                  type="button"
                  className="nn-legend-chip nn-legend-toggle-btn"
                  onClick={() => setIsPatternLegendCollapsed(true)}
                  title="جمع کردن نشانگرهای الگو"
                  aria-label="جمع کردن"
                  data-testid="fts-pattern-legend-collapse"
                >
                  ✕
                </button>
              </div>
            )
          ) : null}
          <div
            ref={chartContainerRef}
            className={`nn-kline-chart ${activeToolId && !['crosshair', 'arrow', 'dot'].includes(activeToolId) ? 'drawing-active-crosshair' : ''}`}
          />

          {/* ابزار اندازه‌گیری / خط‌کش تعاملی (Measure / Ruler Tool) */}
          {measureState && (
            <div className="nn-measure-overlay" data-testid="measure-overlay">
              <div
                className="nn-measure-box"
                style={{
                  left: `${Math.min(measureState.startX, measureState.currX)}px`,
                  top: `${Math.min(measureState.startY, measureState.currY)}px`,
                  width: `${Math.abs(measureState.currX - measureState.startX)}px`,
                  height: `${Math.max(2, Math.abs(measureState.currY - measureState.startY))}px`,
                  backgroundColor: measureState.currPrice >= measureState.startPrice
                    ? 'rgba(8, 153, 129, 0.16)'
                    : 'rgba(242, 54, 69, 0.16)',
                  border: `1px dashed ${
                    measureState.currPrice >= measureState.startPrice ? '#089981' : '#f23645'
                  }`,
                }}
              />
              <div
                className="nn-measure-badge"
                data-testid="measure-badge"
                style={{
                  left: `${Math.max(10, Math.min((chartContainerRef.current?.clientWidth ?? 350) - 160, Math.max(measureState.startX, measureState.currX) + 12))}px`,
                  top: `${Math.max(10, Math.min(measureState.startY, measureState.currY))}px`,
                  borderColor: measureState.currPrice >= measureState.startPrice ? '#089981' : '#f23645',
                }}
              >
                {(() => {
                  const deltaPrice = measureState.currPrice - measureState.startPrice;
                  const pct = measureState.startPrice > 0 ? (deltaPrice / measureState.startPrice) * 100 : 0;
                  const bars = Math.abs(measureState.currIdx - measureState.startIdx) + 1;
                  const days = Math.max(1, Math.round(Math.abs(measureState.currTs - measureState.startTs) / (24 * 60 * 60 * 1000)));
                  const isPos = deltaPrice >= 0;

                  return (
                    <>
                      <div className="nn-measure-badge-row">
                        <span className="nn-measure-badge-label">درصد تغییر:</span>
                        <span className="nn-measure-badge-val" style={{ color: isPos ? '#089981' : '#f23645' }} dir="ltr">
                          {isPos ? '+' : ''}{pct.toFixed(2)}%
                        </span>
                      </div>
                      <div className="nn-measure-badge-row">
                        <span className="nn-measure-badge-label">اختلاف قیمت:</span>
                        <span className="nn-measure-badge-val" style={{ color: isPos ? '#089981' : '#f23645' }}>
                          {Math.round(deltaPrice).toLocaleString('fa-IR')} ریال
                        </span>
                      </div>
                      <div className="nn-measure-badge-row">
                        <span className="nn-measure-badge-label">تعداد بار / کندل:</span>
                        <span className="nn-measure-badge-val">{bars.toLocaleString('fa-IR')} کندل</span>
                      </div>
                      <div className="nn-measure-badge-row">
                        <span className="nn-measure-badge-label">بازه زمانی:</span>
                        <span className="nn-measure-badge-val">{days.toLocaleString('fa-IR')} روز</span>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          )}

          {/* کلیدهای مینیاتوری دائمی گوشه پایین-راست کانتینر چارت (Log / Auto / %) */}
          <div className="nn-price-axis-buttons" data-testid="price-axis-buttons">
            <button
              type="button"
              className={`nn-axis-btn ${ftsPriceScale === 'percentage' ? 'active' : ''}`}
              onClick={() => {
                const next = ftsPriceScale === 'percentage' ? 'normal' : 'percentage';
                useFtsConfigStore.getState().setPriceScale(next);
                chartRef.current?.overrideYAxis({ paneId: 'candle_pane', name: next } as never);
              }}
              title="مقیاس درصدی (%)"
              data-testid="axis-btn-percent"
            >
              %
            </button>
            <button
              type="button"
              className={`nn-axis-btn ${isLogScale || ftsPriceScale === 'logarithm' ? 'active' : ''}`}
              onClick={toggleLogScale}
              title="مقیاس لگاریتمی"
              data-testid="axis-btn-log"
            >
              log
            </button>
            <button
              type="button"
              className={`nn-axis-btn ${isAutoScale ? 'active' : ''}`}
              onClick={() => {
                setIsAutoScale(true);
                handleAutoScale();
              }}
              title="تنظیم خودکار مقیاس"
              data-testid="axis-btn-auto"
            >
              auto
            </button>
          </div>

          {/* وضعیت صادقانه بدون دیتا (بدون ساخت دیتای تقلبی/mock) */}
          {!isLoading && !hasData && (
            <div className="nn-no-data-banner">
              اطلاعات کندل‌استیک برای نماد «{currentSymbol}» در دسترس نیست.
            </div>
          )}
        </main>
      </div>

      {/* نوار پایینی تفکیک‌شده و هماهنگ */}
      <footer className="nn-bottom-bar">
        <div className="nn-range-buttons">
          <span className="pe-1 text-[11px] font-semibold text-[var(--nn-text-secondary)]">بازه زمانی:</span>
          {['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'All'].map((rng) => (
            <button
              key={rng}
              type="button"
              className={`nn-range-btn ${activeRange === rng ? 'active' : ''}`}
              onClick={() => {
                setActiveRange(rng);
                chartRef.current?.scrollToRealTime();
              }}
            >
              {rng}
            </button>
          ))}
        </div>

        <div className="nn-timezone-badge">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#089981]" />
          <span>تهران (UTC+3:30)</span>
        </div>
      </footer>

      {/* پنجره جستجوی نماد */}
      <SymbolSearchModal
        isOpen={isSymbolSearchOpen}
        onClose={() => setIsSymbolSearchOpen(false)}
        onSelectSymbol={handleSelectSymbol}
        currentSymbol={currentSymbol}
      />

      {/* پنل مودال اندیکاتورها */}
      {showIndicatorsModal && (
        <div
          style={{
            position: 'absolute',
            top: '48px',
            right: '260px',
            backgroundColor: '#1e222d',
            border: '1px solid #2a2e39',
            borderRadius: '8px',
            padding: '14px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
            zIndex: 150,
            width: '280px',
            direction: 'rtl'
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '10px',
              borderBottom: '1px solid #2a2e39',
              paddingBottom: '6px'
            }}
          >
            <span style={{ fontWeight: 'bold', fontSize: '13px', color: '#ffffff' }}>اندیکاتورها و اسیلاتورها</span>
            <button
              onClick={() => setShowIndicatorsModal(false)}
              style={{ background: 'none', border: 'none', color: '#787b86', cursor: 'pointer' }}
            >
              <IconClose size={16} />
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { id: 'VOL', label: 'حجم معاملات (Volume)' },
              { id: 'MA', label: 'میانگین متحرک ساده (MA 14/100)' },
              { id: 'EMA', label: 'میانگین متحرک نمایی (EMA 50)' },
              { id: 'RSI', label: 'شاخص قدرت نسبی (RSI 14 Wilder)' },
              { id: 'MACD', label: 'مکدی (MACD)' },
              { id: 'BOLL', label: 'باندهای بولینگر (Bollinger)' },
            ].map((ind) => (
              <label
                key={ind.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  color: indicators[ind.id] ? '#2962ff' : '#d1d4dc'
                }}
              >
                <input
                  type="checkbox"
                  checked={!!indicators[ind.id]}
                  onChange={() => toggleIndicator(ind.id)}
                />
                <span>{ind.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default KLineChartWrapper;
