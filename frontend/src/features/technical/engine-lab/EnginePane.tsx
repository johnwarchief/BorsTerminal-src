// features/technical/engine-lab/EnginePane.tsx -- یک ستونِ مقایسه.
// فقط رابطِ موتور را صدا می‌زند و نامِ کتابخانه نمی‌داند (جز نامِ اندیکاتور،
// که رابط آن را عمداً به خودِ موتور واگذاشته). چیزی که موتور پشتیبانی نمی‌کند
// هرگز به زور فرمان داده نمی‌شود؛ ناکامی درِ نوارِ وضعیت خوانده می‌شود.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  engineEntry,
  paletteFromTheme,
  type ChartEngine,
  type ChartEngineId,
  type ChartOverlaySpec,
  type EngineBar,
  type EngineError,
  type EngineHealth,
} from '@features/technical/engine';
import { epochToJalali } from '@features/technical/lib/jalaliDate';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

import { EMPTY_LAB_METRICS, type LabMetrics, type LabTimeframe } from './types';

const LAB_GROUP = 'lab';
const DAY_MS = 86_400_000;
const FPS_WINDOW_MS = 3_000;

/** هر موتور میانگینِ متحرک را با نامِ خودش می‌شناسد؛ ترجمۀ این نام درِ رابط نیست
 *  (v10 آن را MA می‌خواند و FFC در فهرستِ خودش SMA دارد، بی‌«MA»). */
const TREND_NAME: Record<ChartEngineId, string> = { klinecharts: 'MA', ffc: 'SMA' };
/** دورۀ مشترکِ میانگین: هر دو موتور با همین عدد محاسبه می‌کنند تا مقایسه
 *  «دو پیش‌فرضِ متفاوت» نشود */
const LAB_MA_PERIOD = 20;

const TIMEFRAME_LABEL: Record<LabTimeframe, string> = {
  D: 'روزانه',
  W: 'هفتگی',
  M: 'ماهانه',
};

type PerfWithMemory = Performance & { memory?: { usedJSHeapSize: number } };

function heapBytes(): number | null {
  const used = (performance as PerfWithMemory).memory?.usedJSHeapSize;
  return typeof used === 'number' && Number.isFinite(used) ? used : null;
}

function errText(e: unknown): string {
  return String((e as Error)?.message ?? e);
}

function quantile(values: number[], q: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

/**
 * دستۀ ثابتِ لایه‌ها؛ همه از خودِ کندل‌ها ساخته می‌شود تا دو موتور دقیقاً یک
 * شکل را بگیرند. آستانهٔ «چهار کندل» برایِ این است که segment دو نکت می‌خواهد
 * و کمربندِ صدک به نمونه‌ای بزرگ‌تر از یک بسته نیاز دارد.
 */
function labOverlays(bars: EngineBar[], symbol: string): ChartOverlaySpec[] {
  if (bars.length < 4) return [];
  const first = bars[0];
  const last = bars[bars.length - 1];
  let maxHigh = first.high;
  let maxHighTs = first.timestamp;
  for (const b of bars) {
    if (b.high > maxHigh) {
      maxHigh = b.high;
      maxHighTs = b.timestamp;
    }
  }
  const closes = bars.map((b) => b.close);
  const segFrom = bars[Math.max(0, bars.length - 20)];

  return [
    {
      id: 'lab-level',
      kind: 'level',
      group: LAB_GROUP,
      points: [{ timestamp: maxHighTs, value: maxHigh }],
      color: '#f59e0b',
      label: 'سقفِ بازه',
      width: 1,
      dashed: true,
    },
    {
      id: 'lab-band',
      kind: 'band',
      group: LAB_GROUP,
      points: [
        { timestamp: first.timestamp, value: quantile(closes, 0.25) },
        { timestamp: last.timestamp, value: quantile(closes, 0.75) },
      ],
      color: '#3b82f6',
      fill: '#3b82f622',
      label: 'کمربندِ ۲۵ تا ۷۵ درصدِ بسته',
      width: 1,
    },
    {
      id: 'lab-segment',
      kind: 'segment',
      group: LAB_GROUP,
      points: [
        { timestamp: segFrom.timestamp, value: segFrom.close },
        { timestamp: last.timestamp, value: last.close },
      ],
      color: '#26a69a',
      label: 'شیبِ ۲۰ کندلِ آخر',
      width: 2,
      dashed: false,
    },
    {
      id: 'lab-marker',
      kind: 'marker',
      group: LAB_GROUP,
      points: [{ timestamp: last.timestamp, value: last.close }],
      color: '#ef5350',
      label: `آخرین نشستِ ${symbol}`,
      dashed: false,
    },
  ];
}

function formatLabTime(ts: number, spanMs: number): string {
  const date = epochToJalali(ts);
  if (spanMs >= DAY_MS) return date;
  const clock = new Intl.DateTimeFormat('fa-IR', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tehran',
  }).format(new Date(ts));
  return `${date} ${clock}`;
}

export type EnginePaneProps = {
  engineId: ChartEngineId;
  bars: EngineBar[];
  symbol: string;
  timeframe: LabTimeframe;
  showOverlays: boolean;
  dark: boolean;
  onMetrics: (engineId: ChartEngineId, metrics: LabMetrics) => void;
  /** شمارۀ «اندازه‌گیری کاراییِ» صفحه؛ عوض‌شدنش همان کارِ دکمۀ خودِ پنل را می‌کند */
  measureSignal?: number;
};

export default function EnginePane({
  engineId,
  bars,
  symbol,
  timeframe,
  showOverlays,
  dark,
  onMetrics,
  measureSignal,
}: EnginePaneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const engineRef = useRef<ChartEngine | null>(null);
  const mountStartRef = useRef(0);
  const paintedRef = useRef(false);
  const fpsRafRef = useRef(0);
  const darkRef = useRef(dark);
  const onMetricsRef = useRef(onMetrics);
  const seenSignalRef = useRef(measureSignal);

  const [engine, setEngine] = useState<ChartEngine | null>(null);
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const [errors, setErrors] = useState<EngineError[]>([]);
  const [metrics, setMetrics] = useState<LabMetrics>(EMPTY_LAB_METRICS);
  const [hoverText, setHoverText] = useState<string | null>(null);

  useEffect(() => {
    darkRef.current = dark;
  }, [dark]);

  useEffect(() => {
    onMetricsRef.current = onMetrics;
  }, [onMetrics]);

  const refreshHealth = useCallback(() => {
    const h = engineRef.current?.health();
    if (!h) return;
    setHealth(h);
    setMetrics((prev) => ({
      ...prev,
      canvasCount: h.canvasCount,
      barCount: h.barCount,
      overlayCount: h.overlayCount,
      renderer: h.renderer,
    }));
  }, []);

  // ---- ساختن / mount / destroy -------------------------------------------
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const entry = engineEntry(engineId);
    if (!entry) {
      setErrors([{ code: 'no-entry', message: `موتور «${engineId}» در رجیستری نیست` }]);
      return;
    }

    let alive = true;
    const off: (() => void)[] = [];
    paintedRef.current = false;
    mountStartRef.current = performance.now();
    setErrors([]);
    setHealth(null);
    setMetrics(EMPTY_LAB_METRICS);

    const boot = async () => {
      let created: ChartEngine;
      try {
        created = await entry.create();
      } catch (e) {
        if (alive) setErrors([{ code: 'create', message: errText(e) }]);
        return;
      }
      if (!alive) {
        created.destroy();
        return;
      }
      engineRef.current = created;
      setMetrics((prev) => ({ ...prev, capabilities: created.capabilities }));
      off.push(created.onError((err) => alive && setErrors((prev) => [...prev, err])));
      off.push(
        created.onCrosshair((info) => {
          if (!alive) return;
          setHoverText(
            info.timestamp == null
              ? null
              : `${epochToJalali(info.timestamp)} · ${info.price == null ? '-' : fmtInt(info.price)}`,
          );
        }),
      );

      try {
        await created.mount(host, {
          visibleBars: 90,
          palette: paletteFromTheme(darkRef.current),
          candleStyle: 'candles',
          formatTime: formatLabTime,
          formatPrice: (v) => fmtInt(v),
        });
        await created.ready();
      } catch (e) {
        // موتورِ بالا‌نیامده داده نمی‌گیرد تا «چارتِ خالی» با «ناکام» اشتباه
        // خوانده نشود؛ نوارِ وضعیت همان خطایِ onError/health را می‌گوید.
        if (alive) {
          setErrors((prev) => [...prev, { code: 'mount', message: errText(e) }]);
          setHealth(created.health());
        }
        return;
      }
      if (!alive) return;
      setEngine(created);
    };

    void boot();

    return () => {
      alive = false;
      off.forEach((f) => f());
      engineRef.current?.destroy();
      engineRef.current = null;
      setEngine(null);
    };
  }, [engineId]);

  // ---- داده --------------------------------------------------------------
  useEffect(() => {
    if (!engine) return;
    engine.setBars(bars);
    engine.scrollToLast();
    engine.resize();

    // دو فریمِ بعدی = یک فریمِ نقاشی‌شده؛ مدتِ mount از شروعِ create خوانده می‌شود
    if (!paintedRef.current && bars.length > 0) {
      paintedRef.current = true;
      requestAnimationFrame(() =>
        requestAnimationFrame(() =>
          setMetrics((prev) => ({
            ...prev,
            mountMs: Math.round(performance.now() - mountStartRef.current),
          })),
        ),
      );
    }
    refreshHealth();
  }, [engine, bars, refreshHealth]);

  // ---- تم ----------------------------------------------------------------
  useEffect(() => {
    if (!engine) return;
    engine.setPalette(paletteFromTheme(dark));
    engine.resize();
  }, [engine, dark]);

  // ---- لایه‌هایِ آزمایشی ---------------------------------------------------
  useEffect(() => {
    if (!engine) return;
    const supported = labOverlays(bars, symbol).filter((s) => engine.capabilities.overlay[s.kind]);
    if (showOverlays && supported.length > 0) engine.applyOverlays(LAB_GROUP, supported);
    else engine.clearOverlays(LAB_GROUP);
    refreshHealth();
  }, [engine, bars, symbol, showOverlays, refreshHealth]);

  // ---- اندیکاتورها --------------------------------------------------------
  useEffect(() => {
    if (!engine) return;
    const caps = engine.capabilities;
    // حجمDepth را هر دو موتور درِ خودِ mount به‌عنوان پنلِ حجم می‌سازند؛
    // افزودنِ اندیکاتورِ حجم روی آن، روی klinecharts دومین VOL در همان پنل
    // می‌گذاشت و مقایسه را ناعادلانه می‌کرد.
    if (caps.customIndicator) {
      engine.addIndicator({
        id: 'lab-trend',
        name: TREND_NAME[engineId],
        pane: 'price',
        // یک دورۀ مشترک: v10 آن را calcParams می‌خواهد و FFC paramsِ نام‌دار
        // ({period}) — هر دو آداپتر همین یک عدد را می‌فهمند.
        params: [LAB_MA_PERIOD],
        colors: ['#f59e0b'],
      });
    }
    refreshHealth();
  }, [engine, engineId, refreshHealth]);

  // ---- پنجرۀ ۳ ثانیه‌ایِ نرخِ فریم ----------------------------------------
  const measure = useCallback(() => {
    cancelAnimationFrame(fpsRafRef.current);
    const heap0 = heapBytes();
    const start = performance.now();
    let frames = 0;

    const tick = () => {
      frames += 1;
      const elapsed = performance.now() - start;
      if (elapsed < FPS_WINDOW_MS) {
        fpsRafRef.current = requestAnimationFrame(tick);
        return;
      }
      const heap1 = heapBytes();
      setMetrics((prev) => ({
        ...prev,
        fps: Math.round((frames * 1000) / elapsed),
        heapDeltaMb:
          heap0 != null && heap1 != null ? Math.round(((heap1 - heap0) / 1_048_576) * 10) / 10 : null,
        canvasCount: engineRef.current?.health().canvasCount ?? prev.canvasCount,
        measuredAt: Date.now(),
      }));
    };

    fpsRafRef.current = requestAnimationFrame(tick);
  }, []);

  useEffect(() => () => cancelAnimationFrame(fpsRafRef.current), []);

  useEffect(() => {
    if (measureSignal == null || measureSignal === seenSignalRef.current) return;
    seenSignalRef.current = measureSignal;
    measure();
  }, [measureSignal, measure]);

  useEffect(() => {
    onMetricsRef.current(engineId, metrics);
  }, [engineId, metrics]);

  const allErrors = useMemo(() => {
    const seen = new Set<string>();
    const out: EngineError[] = [];
    for (const e of [...errors, ...(health?.errors ?? [])]) {
      const key = `${e.code}|${e.message}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(e);
    }
    return out;
  }, [errors, health]);

  const errored = allErrors.length > 0;
  const status = engine
    ? errored
      ? 'آماده، با خطا'
      : 'آماده'
    : errored
      ? 'بالا نیامد'
      : 'در حال ساخت...';
  const statusTone = engine
    ? errored
      ? 'text-accent-yellow'
      : 'text-accent-green'
    : errored
      ? 'text-accent-red'
      : 'text-accent-yellow';

  return (
    <div className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-border-c bg-bg-card">
      <div ref={hostRef} className="h-[320px] w-full min-w-0 lg:h-[420px]" data-testid={`lab-host-${engineId}`} />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border-c bg-bg-secondary px-2 py-1.5 text-3xs text-text-secondary">
        <span className="font-bold text-text-primary">
          {symbol} · {TIMEFRAME_LABEL[timeframe]}
        </span>
        <span className={statusTone}>{status}</span>
        <span>رندر: {health?.renderer ?? '-'}</span>
        <span>بوم: {toFaDigits(metrics.canvasCount)}</span>
        <span>کندل: {toFaDigits(metrics.barCount)}</span>
        <span>لایه: {toFaDigits(metrics.overlayCount)}</span>
        <span>
          بالا‌آمدن: {metrics.mountMs == null ? '-' : `${toFaDigits(metrics.mountMs)}ms`}
        </span>
        <span>فریم/ثانیه: {metrics.fps == null ? '-' : toFaDigits(metrics.fps)}</span>
        <span>
          پشته: {metrics.heapDeltaMb == null ? 'ناموجود' : `${toFaDigits(metrics.heapDeltaMb)}MB`}
        </span>
        {hoverText ? <span className="text-text-muted">{hoverText}</span> : null}
        <button
          type="button"
          onClick={measure}
          data-testid={`lab-measure-${engineId}`}
          className="ms-auto rounded-md border border-border-c px-2 py-0.5 text-3xs font-bold text-text-primary transition-colors hover:border-border-accent hover:text-accent-blue"
        >
          اندازه‌گیری
        </button>
      </div>

      {errored ? (
        <ul className="flex flex-col gap-0.5 border-t border-border-c bg-accent-red/10 px-2 py-1.5 text-3xs text-accent-red">
          {allErrors.map((e) => (
            <li key={`${e.code}-${e.message}`}>
              {e.code}: {e.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
