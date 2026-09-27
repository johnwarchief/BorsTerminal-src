// features/technical/engine-lab/EngineLabPage.tsx -- دو موتور، یک داده، کنارِ هم.
// این صفحه آزمایشِ مقایسه است، نه مهاجرت: چارتِ زنده را نمی‌بیند و چیزی از آن
// نمی‌خواهد. کندل‌ها یک‌بار درِ همین صفحه خوانده می‌شود و همان آبجکت به هر دو
// پنل می‌رود، تا «تفاوتِ رندر» واقعاً تفاوتِ موتور باشد نه تفاوتِ داده.
import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { ENGINE_REGISTRY, type ChartCapabilities, type ChartEngineId, type EngineBar } from '@features/technical/engine';
import { fetchCandleFeed, toKLineData } from '@features/technical/api/useCandleFeed';
import { resample, type ResamplePeriod } from '@features/technical/lib/resample';
import { epochToJalali } from '@features/technical/lib/jalaliDate';
import type { KLineData } from '../../../vendor/klinecharts';

import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { useUiStore } from '@shared/stores/uiStore';

import EnginePane from './EnginePane';
import { LAB_TIMEFRAMES, type LabMetrics, type LabTimeframe } from './types';

const TIMEFRAME_LABEL: Record<LabTimeframe, string> = { D: 'روزانه', W: 'هفتگی', M: 'ماهانه' };
const RESAMPLE_PERIOD: Record<LabTimeframe, ResamplePeriod> = { D: 'day', W: 'week', M: 'month' };

const yes = (b: boolean) => (b ? '✓' : '✗');
const num = (v: number | null | undefined) => (v == null ? '-' : toFaDigits(v));

type CapRow = { label: string; cell: (c: ChartCapabilities) => string };

const CAP_ROWS: CapRow[] = [
  { label: 'کتابخانه/نسخه', cell: (c) => c.label },
  { label: 'پنلِ مستقل', cell: (c) => toFaDigits(c.panes) },
  { label: 'اورلیِ سطح', cell: (c) => yes(c.overlay.level) },
  { label: 'اورلیِ کمربند', cell: (c) => yes(c.overlay.band) },
  { label: 'اورلیِ پاره‌خط', cell: (c) => yes(c.overlay.segment) },
  { label: 'اورلیِ نشانگر', cell: (c) => yes(c.overlay.marker) },
  { label: 'اندیکاتورِ سفارشی', cell: (c) => yes(c.customIndicator) },
  { label: 'ابزارِ ترسیمیِ داخلی', cell: (c) => yes(c.builtinDrawTools) },
  { label: 'تایم‌فریمِ دقیقه‌ای', cell: (c) => yes(c.minuteTimeframes) },
  { label: 'مقیاسِ لگاریتمی', cell: (c) => yes(c.logScale) },
  { label: 'محورِ جلالی', cell: (c) => yes(c.jalaliAxis) },
  { label: 'رویدادِ کراس‌هیر', cell: (c) => yes(c.crosshairEvents) },
  { label: 'خروجیِ تصویر', cell: (c) => yes(c.exportImage) },
  { label: 'نیازمندِ WebGL', cell: (c) => yes(c.requiresWebGL) },
];

type MetricRow = { label: string; cell: (m: LabMetrics | undefined) => string };

const METRIC_ROWS: MetricRow[] = [
  { label: 'زمانِ بالا‌آمدن (ms)', cell: (m) => num(m?.mountMs) },
  { label: 'فریم/ثانیه (FPS)', cell: (m) => num(m?.fps) },
  { label: 'تغییرِ پشته (MB)', cell: (m) => (m?.heapDeltaMb == null ? 'ناموجود' : toFaDigits(m.heapDeltaMb)) },
  { label: 'تعدادِ بوم', cell: (m) => num(m?.canvasCount) },
  { label: 'کندل در موتور', cell: (m) => num(m?.barCount) },
  { label: 'لایه در موتور', cell: (m) => num(m?.overlayCount) },
  { label: 'رندر', cell: (m) => m?.renderer ?? '-' },
  {
    label: 'آخرین اندازه‌گیری',
    cell: (m) => (m?.measuredAt == null ? 'هنوز نه' : new Date(m.measuredAt).toLocaleTimeString('fa-IR')),
  },
];

/** ✓/✗ رنگی می‌شود تا اختلافِ دو ستون درِ یک نگاه دیده شود */
function MatrixCell({ value }: { value: string }) {
  const tone =
    value === '✓' ? 'text-accent-green' : value === '✗' ? 'text-accent-red' : 'text-text-secondary';
  return <span className={tone}>{value}</span>;
}

export default function EngineLabPage() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const dark = theme === 'dark';

  const [symbolInput, setSymbolInput] = useState('فولاد');
  const [symbol, setSymbol] = useState('فولاد');
  const [timeframe, setTimeframe] = useState<LabTimeframe>('D');
  const [showOverlays, setShowOverlays] = useState(true);
  const [measureSignal, setMeasureSignal] = useState(0);
  const [metricsMap, setMetricsMap] = useState<Partial<Record<ChartEngineId, LabMetrics>>>({});

  // کلیدِ جدا از ['candles', symbol] تا کشِ چارتِ زنده دست‌نخورده بماند
  const feed = useQuery({
    queryKey: ['engine-lab-candles', symbol],
    queryFn: ({ signal }) => fetchCandleFeed(symbol, signal),
    enabled: symbol.trim().length > 0,
    staleTime: 5 * 60_000,
  });

  const daily = useMemo(
    () => toKLineData(feed.data?.candles ?? [], feed.data?.volumes ?? []),
    [feed.data],
  );

  // همان آبجکتِ آرایه به هر دو پنل می‌رود؛ اگر اینجا memo نبود هر رندرِ والد
  // دو موتور را مجبور به reload بی‌دلیل می‌کرد.
  const bars = useMemo<EngineBar[]>(
    () =>
      resample(daily, RESAMPLE_PERIOD[timeframe]).map(
        (c: KLineData): EngineBar => ({
          timestamp: c.timestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume ?? 0,
          turnover: c.turnover ?? null,
        }),
      ),
    [daily, timeframe],
  );

  const onMetrics = useCallback((id: ChartEngineId, m: LabMetrics) => {
    setMetricsMap((prev) => (prev[id] === m ? prev : { ...prev, [id]: m }));
  }, []);

  const commitSymbol = () => {
    const next = symbolInput.trim();
    if (next) setSymbol(next);
  };

  const noData = !feed.isPending && !feed.isError && bars.length === 0;

  return (
    <div className="flex w-full flex-col gap-3" data-testid="engine-lab">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-2">
          <h1 className="text-lg font-bold text-text-primary">آزمایشگاهِ موتورهایِ چارت</h1>
          <span className="text-2xs text-text-muted">
            مقایسهٔ قابلیت / رندر / کارایی روی یک داده — چارتِ زنده دست‌نخورده است
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border-c bg-bg-card px-2 py-2">
          <form
            className="flex items-center gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              commitSymbol();
            }}
          >
            <input
              value={symbolInput}
              onChange={(e) => setSymbolInput(e.target.value)}
              aria-label="نماد"
              className="w-32 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-border-accent"
            />
            <button
              type="submit"
              id="lab-load-symbol"
              className="rounded-lg border border-border-c px-2.5 py-1 text-2xs font-bold text-text-primary transition-colors hover:border-border-accent hover:text-accent-blue"
            >
              بارگذاری
            </button>
          </form>

          <div className="flex items-center gap-1">
            {LAB_TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                type="button"
                id={`lab-tf-${tf}`}
                onClick={() => setTimeframe(tf)}
                className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-colors ${
                  timeframe === tf
                    ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                    : 'border-border-c text-text-secondary hover:text-text-primary'
                }`}
              >
                {TIMEFRAME_LABEL[tf]}
              </button>
            ))}
          </div>

          <button
            type="button"
            id="lab-toggle-overlays"
            aria-pressed={showOverlays}
            onClick={() => setShowOverlays((v) => !v)}
            className={`rounded-lg border px-2.5 py-1 text-2xs font-bold transition-colors ${
              showOverlays
                ? 'border-border-accent bg-accent-green/15 text-accent-green'
                : 'border-border-c text-text-secondary hover:text-text-primary'
            }`}
          >
            لایه‌های FTS
          </button>

          <button
            type="button"
            id="lab-toggle-theme"
            onClick={toggleTheme}
            className="rounded-lg border border-border-c px-2.5 py-1 text-2xs font-bold text-text-primary transition-colors hover:border-border-accent hover:text-accent-blue"
          >
            {dark ? 'تمِ روشن' : 'تمِ تاریک'}
          </button>

          <button
            type="button"
            id="lab-measure-all"
            onClick={() => setMeasureSignal((n) => n + 1)}
            className="rounded-lg border border-border-accent bg-accent-blue/15 px-2.5 py-1 text-2xs font-bold text-accent-blue"
          >
            اندازه‌گیری کارایی
          </button>

          <span className="ms-auto text-2xs text-text-muted">
            {num(bars.length)} کندل یکسان به هر دو موتور
            {bars.length > 0 ? ` · آخرین: ${epochToJalali(bars[bars.length - 1].timestamp)}` : ''}
            {feed.data ? ` · منبع: ${feed.data.source === 'chart' ? 'تعدیل‌شده' : 'تاریخچهٔ محلی'}` : ''}
          </span>
        </div>
      </header>

      {feed.isError ? (
        <EmptyState
          title="دادهٔ کندلی از سرور برنگشت"
          hint="برای مقایسهٔ موتورها به کندلِ واقعی لازم است؛ سرورِ داده را بررسی کن و دوباره تلاش کن."
          action={
            <button
              type="button"
              onClick={() => void feed.refetch()}
              className="rounded-lg border border-border-accent px-3 py-1 text-2xs font-bold text-accent-blue"
            >
              تلاشِ دوباره
            </button>
          }
        />
      ) : null}

      {feed.isPending ? (
        <div className="rounded-xl border border-dashed border-border-c p-10 text-center text-xs text-text-muted">
          در حال بارگذاریِ کندل‌ها...
        </div>
      ) : null}

      {noData ? (
        <EmptyState
          title={`برای «${symbol}» کندلی پیدا نشد`}
          hint="نمادِ دیگری بنویس؛ این صفحه دادهٔ ساختگی نمی‌سازد."
        />
      ) : null}

      {!feed.isError && bars.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {ENGINE_REGISTRY.map((entry) => {
            const caps = metricsMap[entry.id]?.capabilities ?? null;
            return (
              <section key={entry.id} className="flex min-w-0 flex-col gap-2" data-testid={`lab-col-${entry.id}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xs font-bold text-text-primary">{entry.title}</h2>
                  <span className="text-3xs text-text-muted">
                    {entry.production ? 'موتورِ تولید' : 'آزمایشی'}
                  </span>
                  {!caps ? <span className="text-3xs text-accent-yellow">در حال ساخت...</span> : null}
                </div>

                <table className="w-full border-collapse overflow-hidden rounded-lg border border-border-c text-3xs">
                  <caption className="sr-only">قابلیت‌های {entry.title}</caption>
                  <tbody>
                    {CAP_ROWS.map((row) => (
                      <tr key={row.label} className="border-b border-border-c last:border-b-0">
                        <th scope="row" className="px-2 py-1 text-start font-normal text-text-secondary">
                          {row.label}
                        </th>
                        <td className="px-2 py-1 text-end font-bold">
                          {caps ? <MatrixCell value={row.cell(caps)} /> : <span className="text-text-muted">-</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <EnginePane
                  engineId={entry.id}
                  bars={bars}
                  symbol={symbol}
                  timeframe={timeframe}
                  showOverlays={showOverlays}
                  dark={dark}
                  onMetrics={onMetrics}
                  measureSignal={measureSignal}
                />
              </section>
            );
          })}
        </div>
      ) : null}

      {bars.length > 0 ? (
        <section className="overflow-hidden rounded-xl border border-border-c bg-bg-card" data-testid="lab-compare">
          <h2 className="border-b border-border-c px-2 py-1.5 text-2xs font-bold text-text-primary">
            جدولِ مقایسهٔ کارایی
          </h2>
          <table className="w-full border-collapse text-2xs">
            <thead>
              <tr className="border-b border-border-c text-text-secondary">
                <th scope="col" className="px-2 py-1.5 text-start font-normal">
                  سنجه
                </th>
                {ENGINE_REGISTRY.map((entry) => (
                  <th key={entry.id} scope="col" className="px-2 py-1.5 text-end font-bold text-text-primary">
                    {entry.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRIC_ROWS.map((row) => (
                <tr key={row.label} className="border-b border-border-c last:border-b-0">
                  <th scope="row" className="px-2 py-1 text-start font-normal text-text-secondary">
                    {row.label}
                  </th>
                  {ENGINE_REGISTRY.map((entry) => (
                    <td key={entry.id} className="px-2 py-1 text-end font-bold text-text-primary">
                      {row.cell(metricsMap[entry.id])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
