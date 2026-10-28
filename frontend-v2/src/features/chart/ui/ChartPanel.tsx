import { useEffect, useRef } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { toKlineBars, useChart } from '../api/useChart';

interface ChartHandle {
  setStyles: (styles: unknown) => void;
  setDataLoader: (loader: unknown) => void;
  setSymbol: (symbol: { ticker: string }) => void;
  setPeriod: (period: { type: 'day'; span: number }) => void;
  resetData: () => void;
  resize: () => void;
}

export function ChartPanel({ symbol }: { symbol: string }) {
  const query = useChart(symbol);
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<ChartHandle | null>(null);
  const lib = useRef<((container: HTMLElement) => void) | null>(null);
  const bars = useRef<ReturnType<typeof toKlineBars>>([]);

  bars.current = query.data?.candles?.length ? toKlineBars(query.data.candles) : [];

  useEffect(() => {
    const hostEl = host.current;
    if (!hostEl) return;
    let alive = true;
    let created = false;
    void import('klinecharts').then(({ init, dispose }) => {
      if (!alive) return;
      const instance = init(hostEl) as unknown as ChartHandle | null;
      if (!instance) return;
      created = true;
      lib.current = dispose;
      chart.current = instance;
      instance.setStyles({
        grid: { horizontal: { color: 'rgba(255,255,255,0.05)' }, vertical: { color: 'rgba(255,255,255,0.05)' } },
        candle: { bar: { upColor: '#26a69a', downColor: '#ef5350', noChangeColor: '#888888' } },
      });
      instance.setDataLoader({
        getBars: ({ callback }: { callback: (data: unknown[], more?: boolean) => void }) => {
          callback(bars.current, false);
        },
      });
      instance.setSymbol({ ticker: symbol });
      instance.setPeriod({ type: 'day', span: 1 });
    });
    const observer = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(() => chart.current?.resize());
    observer?.observe(hostEl);
    return () => {
      alive = false;
      observer?.disconnect();
      chart.current = null;
      // همگام و فقط اگر همین افکت چارت را ساخته باشد؛ وگرنه پاک‌سازیِ دیرهنگامِ
      // mountِ قبلی (StrictMode) چارتِ تازهٔ mountِ دوم را نابود می‌کرد.
      if (created) lib.current?.(hostEl);
    };
  }, [symbol]);

  useEffect(() => {
    if (bars.current.length) chart.current?.resetData();
  }, [query.data]);

  return (
    <div className="relative h-full w-full">
      <div data-testid="chart-panel" ref={host} className="h-full w-full" dir="ltr" />
      {query.isLoading ? (
        <div data-testid="chart-loading" className="absolute inset-0 grid place-items-center bg-panel t-95 text-text-3">در حالِ بارگذاری چارت…</div>
      ) : null}
      {query.isError ? (
        <div data-testid="chart-error" className="absolute inset-0 grid place-items-center bg-panel t-95 text-down">
          چارت نیامد — {toFaDigits(String((query.error as Error)?.message ?? 'خطا'))}
        </div>
      ) : null}
      {!query.isLoading && !query.isError && !query.data?.candles?.length ? (
        <div data-testid="chart-empty" className="absolute inset-0 grid place-items-center bg-panel t-95 text-text-3">
          {query.data?.message ?? 'کندلی برای این نماد نیست.'}
        </div>
      ) : null}
    </div>
  );
}
