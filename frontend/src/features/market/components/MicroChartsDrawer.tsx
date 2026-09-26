// features/market/components/MicroChartsDrawer.tsx -- دراور میکروچارت‌های درون‌روز
// بالای جدول: اوردر‌بوک فلو (bq_bt آبی در برابر sq_bt نارنجی) و پهنای باند احساسات
// (pos در برابر neg). سری کمتر از ۲ نقطه = «بدون داده»؛ عدد ساختگی رندر نمی‌شود.
import { useMemo, useState } from 'react';
import { CollapseBody, CollapseToggle } from '@shared/components/Collapse';
import { useMarketTimeline } from '../api/useTimeline';
import { useIntradayCache } from '../api/useIntradayCache';
import {
  MIN_CHART_POINTS,
  detectBreadthFlip,
  detectBullishCross,
  timelinePoints,
  toSeriesColumns,
} from '../lib/timelineMath';
import { mergePoints } from '../lib/intradayCache';
import { BreadthGauge, OrderBookGauge } from './SnapshotGauge';

type Series = { name: string; color: string; values: (number | null)[] };

/** منحنی SVG نرمال‌شده روی مین/ماکس مشترک همه سری‌ها */
function MiniLineChart({ series, times }: { series: Series[]; times: string[] }) {
  const W = 300;
  const H = 72;
  const flat = series.flatMap((s) => s.values).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  const min = Math.min(...flat);
  const max = Math.max(...flat);
  const span = max - min || 1;
  const n = times.length;
  const toPoints = (values: (number | null)[]) =>
    values
      .map((v, i) => (v == null || !Number.isFinite(v) ? null : `${((i / Math.max(1, n - 1)) * W).toFixed(1)},${(H - 4 - ((v - min) / span) * (H - 8)).toFixed(1)}`))
      .filter((p): p is string => p != null)
      .join(' ');
  return (
    <div dir="ltr" className="min-w-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-20 w-full" role="img" aria-label={series.map((s) => s.name).join(' و ')}>
        <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="currentColor" strokeOpacity="0.15" strokeWidth="1" />
        {series.map((s) => (
          <polyline key={s.name} points={toPoints(s.values)} fill="none" stroke={s.color} strokeWidth="2" />
        ))}
      </svg>
      <div className="mt-0.5 flex items-center justify-between text-2xs text-text-muted num" dir="rtl">
        <span>{times[0] ?? ''}</span>
        <span>{times[times.length - 1] ?? ''}</span>
      </div>
    </div>
  );
}

function ChartCard({
  testId,
  title,
  legend,
  note,
  badge,
  body,
}: {
  testId: string;
  title: string;
  legend: { color: string; label: string }[];
  note?: string | null;
  badge?: React.ReactNode;
  body: React.ReactNode;
}) {
  return (
    <div data-testid={testId} className="glass-panel flex min-w-0 flex-col gap-1 rounded-xl border border-border-c p-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-2xs font-black text-text-primary">{title}</h4>
        {badge}
      </div>
      {body}
      <div className="flex flex-wrap items-center gap-3 text-2xs text-text-secondary">
        {legend.map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1">
            <span className="inline-block h-0.5 w-4 rounded" style={{ background: l.color }} />
            {l.label}
          </span>
        ))}
        {note ? <span className="text-text-muted">{note}</span> : null}
      </div>
    </div>
  );
}

export function MicroChartsDrawer() {
  const { data, isLoading } = useMarketTimeline();
  const [open, setOpen] = useState(false);

  /** نقاط تایم‌لاین بک‌اند */
  const backendPoints = useMemo(() => timelinePoints(toSeriesColumns(data?.series)), [data]);

  // ثبت ~۳۰ثانیه‌ایِ آخرین اسنپ‌شات در کش محلی (فقط ساعات بازار) و ادغام با بک‌اند
  const latest = backendPoints.length > 0 ? backendPoints[backendPoints.length - 1] : null;
  const cached = useIntradayCache(latest);
  const points = useMemo(() => mergePoints(backendPoints, cached), [backendPoints, cached]);

  const model = useMemo(() => {
    const times = points.map((p) => p.t);
    const bq = points.map((p) => p.bq);
    const sq = points.map((p) => p.sq);
    const pos = points.map((p) => p.pos);
    const neg = points.map((p) => p.neg);
    return {
      times,
      bq,
      sq,
      pos,
      neg,
      ready: points.length >= MIN_CHART_POINTS,
      snapshot: points.length > 0 ? points[points.length - 1] : null,
      cross: detectBullishCross(bq, sq),
      flip: detectBreadthFlip(pos, neg),
    };
  }, [points]);

  // تا تیک‌های زنده قطعی لود نشده‌اند، دراور (و دو کادر میان‌خالی) اصلاً رندر نمی‌شود
  // تا جدول بلافاصله زیر کارت‌های ۴گانهٔ نبض بنشیند.
  if (isLoading || !data) return null;

  return (
    <div className="glass-panel panel-in flex flex-col gap-2 rounded-2xl p-3">
      <CollapseToggle
        open={open}
        onToggle={() => setOpen((v) => !v)}
        testId="micro-charts-toggle"
        label="نمودارهای جریان سفارش‌ها و جو بازار"
        openLabel="باز کردنِ نمودارها"
      />
      <CollapseBody open={open}>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ChartCard
              testId="micro-orderbook"
              title="ارزش سفارش های خرید و فروش (سهام، حق تقدم و ص.سهامی)"
              legend={[
                { color: '#3b82f6', label: 'ارزش صف خرید' },
                { color: '#f97316', label: 'ارزش صف فروش' },
              ]}
              note={model.ready ? null : 'حالت لحظه‌ای — نمودار خطی با رسیدن به ۲ نقطه'}
              badge={
                model.cross.hit ? (
                  <span
                    data-testid="bullish-cross"
                    title="Bullish Cross: عبور ارزش صف خرید از فروش + فاصله گرفتن"
                    className="rounded-full border border-accent-green/50 bg-accent-green/15 px-2 py-0.5 text-2xs font-black text-accent-green"
                  >
                    ▲ برتری تقاضا
                  </span>
                ) : null
              }
              body={
                model.ready ? (
                  <MiniLineChart series={[{ name: 'bq_bt', color: '#3b82f6', values: model.bq }, { name: 'sq_bt', color: '#f97316', values: model.sq }]} times={model.times} />
                ) : (
                  <OrderBookGauge bq={model.snapshot?.bq ?? null} sq={model.snapshot?.sq ?? null} />
                )
              }
            />
            <ChartCard
              testId="micro-breadth"
              title="نمادهای مثبت و منفی (سهام، حق تقدم و ص.سهامی)"
              legend={[
                { color: '#22c55e', label: 'مثبت‌ها' },
                { color: '#ef4444', label: 'منفی‌ها' },
              ]}
              note={model.ready ? null : 'حالت لحظه‌ای — نمودار خطی با رسیدن به ۲ نقطه'}
              badge={
                model.flip ? (
                  <span
                    data-testid="breadth-flip"
                    className={`rounded-full border px-2 py-0.5 text-2xs font-black ${
                      model.flip === 'bull' ? 'border-accent-green/50 bg-accent-green/15 text-accent-green' : 'border-accent-red/50 bg-accent-red/15 text-accent-red'
                    }`}
                  >
                    {model.flip === 'bull' ? 'معکوس به مثبت' : 'معکوس به منفی'}
                  </span>
                ) : null
              }
              body={
                model.ready ? (
                  <MiniLineChart series={[{ name: 'pos', color: '#22c55e', values: model.pos }, { name: 'neg', color: '#ef4444', values: model.neg }]} times={model.times} />
                ) : (
                  <BreadthGauge pos={model.snapshot?.pos ?? null} neg={model.snapshot?.neg ?? null} />
                )
              }
            />
        </div>
        {data.note ? <p className="mt-1 text-2xs text-text-muted">{data.note}</p> : null}
      </CollapseBody>
    </div>
  );
}
