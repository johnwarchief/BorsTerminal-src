// features/market/components/MarketCompareSection.tsx -- نمودارِ مقایسه‌ای (صفحۀ ۱۳)
//
// مرجع جدولی از «سری‌ها» می‌دهد و نموداری که همه رویِ یک محورِ زمانِ مشترک
// نرمال می‌شوند (پایۀ ۱۰۰)، با بازه‌هایِ 5y/1y/6m/3m/1m/5d و سوییچِ «%»/«log».
//
// چهار چیز درِ این فایل عمداً سخت گرفته شده:
// ۱) نرمال‌سازی از `technical/lib/compare.ts` است (`alignCompare`): همان
//    زمان‌هایِ مشترک را می‌گیرد و پایه را از اولین زمانِ مشترک می‌سازد. فرمولِ
//    دومِ مقایسه درِ این تب نساخته می‌شود (مرحلۀ ۶ مأموریت).
// ۲) سری‌ها در **یک** درخواست می‌آیند (`/api/mstat/series`). هوک درِ حلقه مجاز
//    نیست و یک درخواست به‌ازای هر نماد round-tripِ واحدِ تب را می‌شکست.
// ۳) سری‌هایِ بی‌منبع حذف نمی‌شوند و خطِ ساختگی هم نمی‌شوند: درِ جدول
//    «غیرفعال + علت» می‌نشینند. انس/دلار/تورم/مسکن/سکهٔ فیزیکی منبعِ داخلی
//    ندارند (سنجشِ market.db: نه درِ price_history نه درِ instruments) و علت از
//    خودِ `/api/mstat/gold` می‌آید.
// ۴) بازه‌ای که بانک ندارد وعده داده نمی‌شود: `price_history` از ۲۰۲۴-۰۸-۲۴
//    شروع می‌شود، پس «۵ سال» بیشینۀ *موجود* است و روزِ واقعاً دیدنی زیرِ
//    نمودار نوشته می‌شود. و چون مبدأ «پایانیِ خام» است، نمودار «نسبت به
//    پایۀِ ۱۰۰» خوانده می‌شود نه «بازدهیِ تعدیل‌شده».

import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { toFaDigits, fmtPct } from '@shared/lib/fmt';
import { alignCompare, COMPARE_BASE } from '@features/technical/lib/compare';
import { toKLine } from '@features/technical/nahayatnegar/lib/useNnData';
import type { KLineData } from '@vendor/klinecharts';
import { StatusError, StatusLoading, StatusNoData, StatusSection, SourceNotice } from './StatusShell';
import { useMstatGold } from '../api/useMarketPanels';

const RANGES = [
  { key: '5y', label: '۵ سال', days: 1825 },
  { key: '1y', label: '۱ سال', days: 365 },
  { key: '6m', label: '۶ ماه', days: 182 },
  { key: '3m', label: '۳ ماه', days: 91 },
  { key: '1m', label: '۱ ماه', days: 30 },
  { key: '5d', label: '۵ روز', days: 5 },
] as const;
type RangeKey = (typeof RANGES)[number]['key'];

const INDEX_LABEL = 'کل بورس';

const SeriesPoint = z.object({ d: z.string().nullish(), v: z.number().nullish() });
const SeriesSchema = z.object({
  status: z.string(),
  computed_at: z.string().nullish(),
  days: z.number().nullish(),
  unit: z.string().nullish(),
  basis: z.string().nullish(),
  symbols: z.array(z.string()).nullish(),
  series: z.record(z.string(), z.array(SeriesPoint)).nullish(),
  points: z.record(z.string(), z.number()).nullish(),
  no_source: z.array(z.string()).nullish(),
  first_date: z.record(z.string(), z.string().nullish()).nullish(),
  last_date: z.record(z.string(), z.string().nullish()).nullish(),
});

/** شاخصِ کل از /api/index/tedpix می‌آید — درِ price_history ردیفی ندارد (سنجش).
 *  `time` رشتهٔ تاریخ است (همان قراردادِ `/api/chart`)؛ تبدیلِ دوباره نساخته
 *  می‌شود، `toKLine`ِ خودِ فیچر تکنیکال آن را می‌دهد. */
const TedpixSchema = z.object({
  status: z.string(),
  candles: z
    .array(z.object({ time: z.string(), open: z.number(), high: z.number(), low: z.number(), close: z.number() }))
    .nullish(),
  source: z.string().nullish(),
  unit: z.string().nullish(),
});

const PALETTE = [
  '#38bdf8', '#fbbf24', '#a78bfa', '#34d399', '#fb7185',
  '#60a5fa', '#f472b6', '#fbbf24', '#94a3b8',
] as const;

const W = 760;
const H = 260;
const PAD = 14;

const DAY_MS = 86_400_000;

export function MarketCompareSection() {
  const [range, setRange] = useState<RangeKey>('1y');
  const [scale, setScale] = useState<'pct' | 'log'>('pct');
  const [picked, setPicked] = useState<string[]>(['شاخص کل', 'عيار', 'فولاد']);
  const [hover, setHover] = useState<number | null>(null);

  const gold = useMstatGold(60);
  const wantIndex = picked.includes('شاخص کل');
  const symbols = useMemo(() => picked.filter((p) => p !== 'شاخص کل'), [picked]);
  const days = RANGES.find((r) => r.key === range)?.days ?? 365;

  const seriesQ = useQuery({
    queryKey: ['mstat-series', symbols.join(','), days],
    enabled: symbols.length > 0,
    staleTime: 60_000,
    queryFn: ({ signal }) =>
      http<z.infer<typeof SeriesSchema>>(
        `/api/mstat/series?symbols=${encodeURIComponent(symbols.join(','))}&days=${days}`,
        { schema: SeriesSchema, signal },
      ),
  });
  const indexQ = useQuery({
    queryKey: ['mstat-index-tedpix'],
    enabled: wantIndex,
    staleTime: 10 * 60_000,
    queryFn: ({ signal }) =>
      http<z.infer<typeof TedpixSchema>>('/api/index/tedpix?limit=0', { schema: TedpixSchema, signal }),
  });

  const goldSymbols = useMemo(() => gold.data?.symbols ?? [], [gold.data]);

  /** همهٔ سری‌ها به شکلِ کندلِ KLineData تا `alignCompare` تک‌مسیر بماند */
  const series = useMemo(() => {
    const out: { symbol: string; label: string; candles: KLineData[]; basis: string }[] = [];
    if (wantIndex) {
      const cs = toKLine(indexQ.data?.candles ?? []);
      if (cs.length)
        out.push({
          symbol: 'شاخص کل',
          label: INDEX_LABEL,
          candles: cs,
          basis: `واحدِ شاخص · ${indexQ.data?.source ?? 'tsetmc'}`,
        });
    }
    const map = seriesQ.data?.series ?? {};
    for (const s of symbols) {
      const pts = map[s] ?? [];
      const cs = pts
        .map((p) => {
          const ts = Date.parse(`${p.d ?? ''}T00:00:00Z`);
          return { ts, v: p.v } as const;
        })
        .filter((p): p is { ts: number; v: number } => Number.isFinite(p.ts) && typeof p.v === 'number' && p.v > 0)
        .map((p) => ({
          timestamp: p.ts, open: p.v, high: p.v, low: p.v, close: p.v, volume: 0,
        }) as KLineData);
      if (cs.length)
        out.push({ symbol: s, label: s, candles: cs, basis: seriesQ.data?.basis ?? 'قیمتِ پایانیِ خام' });
    }
    return out;
  }, [wantIndex, indexQ.data, symbols, seriesQ.data]);

  const aligned = useMemo(
    () => alignCompare(series.map((s) => ({ symbol: s.symbol, candles: s.candles }))),
    [series],
  );

  const geo = useMemo(() => {
    if (!aligned.lines.length || aligned.timestamps.length < 2) return null;
    const vals = aligned.lines.flatMap((l) => l.values).filter((v) => Number.isFinite(v) && v > 0);
    if (vals.length < 2) return null;
    const tf = (v: number) => (scale === 'log' ? Math.log10(v) : v);
    let min = Math.min(...vals.map(tf));
    let max = Math.max(...vals.map(tf));
    if (max === min) {
      min -= 1;
      max += 1;
    }
    const innerW = W - PAD * 2;
    const innerH = H - PAD * 2;
    const xOf = (i: number) => PAD + (i * innerW) / (aligned.timestamps.length - 1);
    const yOf = (v: number) => PAD + innerH * (1 - (tf(v) - min) / (max - min));
    return {
      xOf,
      min,
      max,
      baseY: yOf(COMPARE_BASE),
      lines: aligned.lines.map((l, i) => ({
        symbol: l.symbol,
        label: series.find((s) => s.symbol === l.symbol)?.label ?? l.symbol,
        color: PALETTE[i % PALETTE.length],
        path: l.values
          .map((v, k) => `${k === 0 ? 'M' : 'L'}${xOf(k).toFixed(2)} ${yOf(v).toFixed(2)}`)
          .join(' '),
        line: l,
      })),
    };
  }, [aligned, scale, series]);

  const spanDays = useMemo(
    () =>
      aligned.timestamps.length
        ? Math.round((aligned.timestamps[aligned.timestamps.length - 1] - aligned.timestamps[0]) / DAY_MS)
        : 0,
    [aligned.timestamps],
  );

  const toggle = useCallback((sym: string) => {
    setPicked((p) => (p.includes(sym) ? p.filter((x) => x !== sym) : [...p, sym]));
  }, []);

  const missingFromFeed = useMemo(() => {
    const ns = seriesQ.data?.no_source ?? [];
    return picked.filter((p) => p !== 'شاخص کل' && ns.includes(p));
  }, [seriesQ.data, picked]);

  return (
    <StatusSection
      testId="ms-compare"
      title="نمودارِ مقایسه‌ای"
      hint="سری‌ها رویِ زمانِ مشترک و به پایۀِ ۱۰۰ نرمال می‌شوند — مقایسۀ درصدی، نه قیمتِ خامِ واحدهایِ بی‌ربط"
      asof={gold.data?.asof}
      badge={`پایۀ نرمال‌سازی: اولین زمانِ مشترک = ۱۰۰ (alignCompare) · مبدأِ هر سری درِ فهرستِ کنار می‌آید`}
      toolbar={
        <div className="flex flex-wrap items-center gap-2" data-testid="ms-compare-controls">
          <div className="flex flex-wrap items-center gap-1" role="group" aria-label="بازۀِ زمانی">
            {RANGES.map((r) => (
              <button
                key={r.key}
                type="button"
                data-testid={`ms-compare-range-${r.key}`}
                aria-pressed={range === r.key}
                onClick={() => setRange(r.key)}
                className={`rounded-full border px-2 py-0.5 text-3xs font-bold ${
                  range === r.key
                    ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                    : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1" role="group" aria-label="مقیاسِ محور">
            {(['pct', 'log'] as const).map((s) => (
              <button
                key={s}
                type="button"
                data-testid={`ms-compare-scale-${s}`}
                aria-pressed={scale === s}
                onClick={() => setScale(s)}
                className={`rounded-full border px-2 py-0.5 text-3xs font-bold ${
                  scale === s
                    ? 'border-accent-green bg-accent-green/15 text-accent-green'
                    : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-green'
                }`}
              >
                {s === 'pct' ? '%' : 'log'}
              </button>
            ))}
          </div>
        </div>
      }
    >
      {gold.isError && !gold.data ? (
        <StatusError testId="ms-compare" onRetry={() => void gold.refetch()} />
      ) : gold.isLoading && !gold.data ? (
        <StatusLoading testId="ms-compare" />
      ) : (
        <div className="grid grid-cols-1 gap-2 xl:grid-cols-[minmax(0,250px)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-1" data-testid="ms-compare-chooser">
            <CandidateRow
              testId="ms-compare-cand-index"
              label={INDEX_LABEL}
              available
              checked={wantIndex}
              onToggle={() => toggle('شاخص کل')}
              note="واحدِ شاخص · /api/index/tedpix"
            />
            {goldSymbols.map((s) => (
              <CandidateRow
                key={s.symbol}
                testId={`ms-compare-cand-${s.symbol}`}
                label={`${s.symbol} — ${s.name ?? ''}`}
                available
                checked={picked.includes(s.symbol)}
                onToggle={() => toggle(s.symbol)}
                note={
                  s.kind === 'gold'
                    ? 'صندوقِ طلا · ریال'
                    : s.kind === 'silver'
                      ? 'صندوقِ نقره · ریال'
                      : `${s.cls} · ریال`
                }
              />
            ))}
            {(gold.data?.no_source ?? []).map((n) => (
              <CandidateRow
                key={n.key}
                testId={`ms-compare-cand-missing-${n.key}`}
                label={n.label}
                available={false}
                checked={false}
                note={n.why}
              />
            ))}
          </div>

          <div className="flex min-w-0 flex-col gap-1">
            {geo ? (
              <>
                <div className="w-full overflow-hidden" data-testid="ms-compare-canvas">
                  <svg
                    viewBox={`0 0 ${W} ${H}`}
                    className="h-[260px] w-full"
                    role="img"
                    aria-label="نمودارِ مقایسه‌ایِ نرمال‌شده"
                    data-testid="ms-compare-svg"
                    onMouseMove={(e) => {
                      const svg = (e.currentTarget as SVGSVGElement) ?? null;
                      if (!svg) return;
                      const box = svg.getBoundingClientRect();
                      if (box.width <= 0) return;
                      const rel = ((e.clientX - box.left) / box.width) * W;
                      const i = Math.round(((rel - PAD) / (W - PAD * 2)) * (aligned.timestamps.length - 1));
                      setHover(Math.max(0, Math.min(aligned.timestamps.length - 1, i)));
                    }}
                    onMouseLeave={() => setHover(null)}
                  >
                    <line
                      x1={PAD} y1={geo.baseY} x2={W - PAD} y2={geo.baseY}
                      stroke="var(--text-muted)" strokeDasharray="3 3" strokeWidth="0.8"
                    />
                    <text x={PAD + 2} y={geo.baseY - 3} className="fill-text-muted" style={{ fontSize: 8 }}>
                      پایۀ ۱۰۰
                    </text>
                    {geo.lines.map((l) => (
                      <path
                        key={l.symbol}
                        d={l.path}
                        fill="none"
                        stroke={l.color}
                        strokeWidth="1.6"
                        data-testid={`ms-compare-line-${l.symbol}`}
                      />
                    ))}
                    {hover != null ? (
                      <line
                        x1={geo.xOf(hover)} y1={PAD} x2={geo.xOf(hover)} y2={H - PAD}
                        stroke="var(--text-muted)" strokeWidth="0.6"
                        data-testid="ms-compare-crosshair"
                      />
                    ) : null}
                  </svg>
                </div>
                <ul className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="ms-compare-legend">
                  {geo.lines.map((l) => (
                    <li key={l.symbol} className="flex items-baseline gap-1 text-3xs">
                      <span className="inline-block size-2 shrink-0 rounded-sm" style={{ background: l.color }} />
                      <button
                        type="button"
                        onClick={() => toggle(l.symbol)}
                        data-testid={`ms-compare-unpick-${l.symbol}`}
                        className="font-bold text-text-primary hover:text-accent-red"
                        title="حذفِ این سری"
                      >
                        {l.label}
                      </button>
                      <span className="num-text text-text-secondary">
                        {toFaDigits(
                          (hover != null ? l.line.values[hover] : l.line.last)?.toFixed?.(1) ?? '—',
                        )}
                      </span>
                      <span className="num-text text-accent-blue">{fmtPct(l.line.changePct ?? null)}</span>
                    </li>
                  ))}
                </ul>
                <p className="num-text text-3xs text-text-muted" data-testid="ms-compare-span">
                  {toFaDigits(aligned.timestamps.length)} زمانِ مشترک · {toFaDigits(spanDays)} روزِ دیدنی از
                  بازۀِ درخواستیِ «{RANGES.find((r) => r.key === range)?.label}» ({toFaDigits(days)} روز) ·
                  مقیاسِ {scale === 'log' ? 'لگاریتمی' : 'درصدی'}
                  {spanDays < days
                    ? ` (بانک تا این اندازه تاریخچه دارد — «${RANGES.find((r) => r.key === range)?.label}»ِ درخواستی واقعی نیست)`
                    : ''}.
                </p>
                {hover != null ? (
                  <p className="num-text text-3xs text-text-secondary" data-testid="ms-compare-hover-date">
                    {new Date(aligned.timestamps[hover]).toISOString().slice(0, 10)}
                  </p>
                ) : null}
              </>
            ) : (
              <StatusNoData
                testId="ms-compare"
                text="دو سریِ هم‌پوشان نرسیده — بی‌زمانِ مشترکِ کافی خطِ مقایسه نمی‌کشیم."
              />
            )}
            {seriesQ.isError ? (
              <SourceNotice
                testId="ms-compare-feed"
                items={[
                  {
                    key: 'series',
                    label: 'سریِ نمادها',
                    why: ' /api/mstat/series نرسید — سریِ شاخص اگر رسیده باشد همان‌جا می‌ماند',
                  },
                ]}
              />
            ) : null}
            {wantIndex && indexQ.isError ? (
              <SourceNotice
                testId="ms-compare-index"
                items={[
                  {
                    key: 'tedpix',
                    label: 'شاخصِ کل',
                    why: ' /api/index/tedpix نرسید (منبعِ بیرونی) — سریِ شاخص از نمودار می‌افتد',
                  },
                ]}
              />
            ) : null}
            {missingFromFeed.length ? (
              <SourceNotice
                testId="ms-compare-nosrc"
                items={missingFromFeed.map((s) => ({
                  key: s,
                  label: s,
                  why: 'ردیفی درِ price_history این بانک ندارد',
                }))}
              />
            ) : null}
          </div>
        </div>
      )}
    </StatusSection>
  );
}

function CandidateRow({
  testId,
  label,
  available,
  checked,
  onToggle,
  note,
}: {
  testId: string;
  label: string;
  available: boolean;
  checked: boolean;
  onToggle?: () => void;
  note?: string;
}) {
  return (
    <div
      data-testid={testId}
      data-available={available ? '1' : '0'}
      className={`flex min-w-0 items-start gap-1.5 rounded-lg border px-2 py-1 text-2xs ${
        available ? 'border-border-c bg-bg-card' : 'border-dashed border-border-c bg-bg-secondary'
      }`}
    >
      <input
        type="checkbox"
        id={`${testId}-input`}
        checked={checked}
        disabled={!available}
        onChange={() => onToggle?.()}
        className="mt-0.5 size-3 shrink-0 accent-[var(--accent-blue)]"
        data-testid={`${testId}-check`}
      />
      <div className="min-w-0">
        <label
          htmlFor={`${testId}-input`}
          title={label}
          className={`block line-clamp-2 break-words font-bold ${available ? 'cursor-pointer text-text-primary' : 'text-text-muted'}`}
        >
          {label}
        </label>
        {note ? (
          <span
            className={`block line-clamp-2 break-words text-3xs leading-4 ${available ? 'text-text-muted' : 'text-accent-yellow'}`}
            title={note}
            data-testid={`${testId}-note`}
          >
            {available ? note : `بی‌منبع — ${note}`}
          </span>
        ) : null}
      </div>
    </div>
  );
}
