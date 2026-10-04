// features/technical/components/FtsEngineChart.tsx -- میزبانِ موتورِ دوم درِ تب تکنیکال
// چارتِ اصلی (klinecharts) دست‌نخورده می‌ماند؛ این پنل فقط وقتی می‌آید که کاربر
// خودش موتور را عوض کرده باشد. رابطِ موتور (engine/) تنها راهِ تماس است: نه
// نامِ کتابخانه‌ای اینجا می‌آید، نه داوری -- لایه‌ها از همان `/api/fts` می‌آیند
// (lib/engineFtsLayers) و عددی که سرور نگفته رسم نمی‌شود.
// صادق‌گویی دو چیز است: بالا‌نیامدنِ موتور با پیامِ خودش (FFC WebGL2 می‌خواهد)،
// و قابلیتِ نبودنِ خودش (محورِ جلالی، ترسیم‌هایِ ذخیره‌شده، بازپخش).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import { engineEntry, paletteFromTheme, type ChartEngine, type ChartEngineId, type EngineBar, type EngineError } from '../engine';
import { engineFtsLayers } from '../lib/engineFtsLayers';
import { epochToJalali, parseCandleTimestamp } from '../lib/jalaliDate';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

const GROUPS = ['fts-fib', 'fts-pattern'] as const;

export function FtsEngineChart({
  engineId,
  bars,
  fts,
  dark,
  logScale,
  candleStyle,
  onEngineChange,
}: {
  engineId: ChartEngineId;
  bars: EngineBar[];
  fts: FtsAnalysisData | null | undefined;
  dark: boolean;
  logScale: boolean;
  candleStyle: 'candles' | 'bars' | 'line' | 'area' | 'heikin';
  /** نوارِ ابزارِ klinecharts وقتی این موتور روی صحنه نیست در دسترس نیست، پس
   *  راهِ بازگشت همین‌جا باید باشد — وگرنه کاربر در یک چارتِ بی‌کلید می‌ماند. */
  onEngineChange?: (id: ChartEngineId) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const engineRef = useRef<ChartEngine | null>(null);
  const [engine, setEngine] = useState<ChartEngine | null>(null);
  const [errors, setErrors] = useState<EngineError[]>([]);

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
    setErrors([]);
    setEngine(null);

    void (async () => {
      let created: ChartEngine;
      try {
        created = await entry.create();
      } catch (e) {
        if (alive) setErrors([{ code: 'create', message: String(e) }]);
        return;
      }
      if (!alive) {
        created.destroy();
        return;
      }
      engineRef.current = created;
      off.push(created.onError((err) => alive && setErrors((prev) => [...prev, err])));
      try {
        await created.mount(host, {
          visibleBars: 180,
          palette: paletteFromTheme(dark),
          candleStyle,
          formatTime: (ts) => epochToJalali(ts),
          formatPrice: (v) => fmtInt(v),
        });
        await created.ready();
      } catch (e) {
        // موتورِ بالا‌نیامده داده نمی‌گیرد تا «چارتِ خالی» با «ناکام» اشتباه
        // خوانده نشود؛ بانرِ همان پایین خطا را می‌گوید.
        if (alive) setErrors((prev) => [...prev, { code: 'mount', message: String(e) }]);
        return;
      }
      if (alive) setEngine(created);
    })();

    const ro = new ResizeObserver(() => engineRef.current?.resize());
    ro.observe(host);

    return () => {
      alive = false;
      ro.disconnect();
      off.forEach((f) => f());
      engineRef.current?.destroy();
      engineRef.current = null;
    };
    // کال‌پس‌ها فقط هنگامِ mount خوانده می‌شوند؛ عوض‌شدنِ آن‌ها نباید موتور را
    // از نو بسازد (هر ساختِ دوباره یعنی پرشِ نما درِ بازارِ باز).
  }, [engineId]);

  const layers = useMemo(() => {
    if (bars.length === 0) return [];
    const anchor = bars[bars.length - 1].timestamp;
    const start = bars[0].timestamp;
    return engineFtsLayers({
      fts,
      anchorTs: anchor,
      startTs: start,
      toDisp: (p) => p,
      tsForDate: (d) => {
        const ts = parseCandleTimestamp(d);
        return Number.isFinite(ts) && ts > 0 ? ts : null;
      },
    });
  }, [bars, fts]);

  // دو گروه، هر بار کاملِ جایگزین -- وگرنه لایه‌های تکراری روی هم می‌نشینند
  useEffect(() => {
    if (!engine) return;
    const byGroup = new Map<string, typeof layers>();
    for (const l of layers) {
      const list = byGroup.get(l.group) ?? [];
      list.push(l);
      byGroup.set(l.group, list);
    }
    for (const g of GROUPS) engine.applyOverlays(g, byGroup.get(g) ?? []);
  }, [engine, layers]);

  useEffect(() => {
    engine?.setLogScale(logScale);
  }, [engine, logScale]);

  useEffect(() => {
    engine?.setCandleStyle(candleStyle);
  }, [engine, candleStyle]);

  useEffect(() => {
    if (!engine || bars.length === 0) return;
    engine.setBars(bars);
    engine.scrollToLast();
  }, [engine, bars]);

  const reload = useCallback(() => engineRef.current?.reloadData(), []);
  useEffect(() => {
    reload();
  }, [reload, bars.length]);

  const caps = engine?.capabilities ?? null;
  const failed = errors.some((e) => e.code === 'create' || e.code === 'mount' || e.code === 'no-webgl2');

  return (
    <div className="relative flex h-full min-h-0 w-full flex-col" data-testid="fts-engine-chart">
      <div ref={hostRef} className="min-h-0 flex-1" data-testid="fts-engine-host" />
      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--hairline)] px-2 py-1 text-[10px] text-text-muted">
        <span className="font-bold text-text-secondary">موتور: {caps ? caps.label : engineId}</span>
        <span>کندل: {toFaDigits(bars.length)}</span>
        <span>لایهٔ FTS: {toFaDigits(layers.length)}</span>
        {caps && !caps.jalaliAxis ? <span>محورِ زمان میلادی است (متنِ جلالی فقط در برچسب‌ها)</span> : null}
        {caps ? null : <span>در حال ساختنِ موتور…</span>}
        {onEngineChange ? (
          <button
            type="button"
            data-testid="fts-engine-back"
            onClick={() => onEngineChange('klinecharts')}
            className="mr-auto rounded border border-border-c px-2 py-0.5 text-text-secondary transition-colors hover:border-accent-blue hover:text-accent-blue"
          >
            بازگشت به KLineCharts
          </button>
        ) : null}
      </div>
      {failed ? (
        <div className="absolute inset-x-0 top-0 m-2 rounded-lg border border-accent-red/40 bg-bg-card/95 p-2 text-[11px] text-accent-red" data-testid="fts-engine-error">
          {errors.map((e, k) => (
            <div key={`${e.code}-${k}`}>
              {e.code}: {e.message}
            </div>
          ))}
          <div>با «موتور: KLineCharts» به چارتِ همیشگی برگردید.</div>
        </div>
      ) : null}
    </div>
  );
}
