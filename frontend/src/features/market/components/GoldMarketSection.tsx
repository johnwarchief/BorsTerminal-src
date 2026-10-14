// features/market/components/GoldMarketSection.tsx -- بازارِ طلا (صفحاتِ ۱، ۳، ۱۰، ۱۱، ۱۲)
//
// پنج صفحۀ مرجع حولِ این مفهوم‌اند و همه درِ یک بخشِ تازه با زیرتب می‌نشینند:
// ۱ و ۳ یک داشبورد با دو چینش‌اند (شباهت، اجازهٔ حذف نیست — هر دو درِ ماتریس
// ردیابی می‌مانند)، ۱۰ داشبوردِ جامع، ۱۱ جدول‌هایِ جدا، ۱۲ نقشه و ترکیبِ صندوق‌ها.
//
// سه تصمیمِ اصلی:
// ۱) سه جدولِ *جدا* با مدلِ دادهٔ خودش (صریحِ مأموریت): «صندوقِ طلا/نقره»،
//    «اوراقِ مرابحۀ طلا/سلفِ سکه»، «گواهی و نمادهایِ مبتنی بر طلا». یک جدولِ
//    واحدِ مخلوط که ماهیتِ ابزارها را قاطی کند ساخته نمی‌شود، و بی‌ستونِ
//    متعلقِ به آن ابزار هم نمی‌ماند.
// ۲) هر چیزی که منبع ندارد (انس، سکهٔ فیزیکی، تتر، دلار، مسکن، تورم، قیمتِ
//    آینده، ارزشِ ذاتیِ قفل‌شده) کارتِ «منبع داده در دسترس نیست» می‌گیرد با
//    علتِ خودِ سرور. هیچ عددی برایِ پرکردنِ کارت ساخته نمی‌شود و برچسبِ «زنده»
//    نمی‌گیرد.
// ۳) donut و treemap دو نمایِ *مستقل‌اند*: یکی جایگزینِ دیگری نمی‌شود؛ هر دو
//    از یک پاسخِ سازگار می‌خوانند و زمانِ محاسبه‌شان نشان داده می‌شود.

import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { DownloadRowsButton } from '@shared/components/DownloadRowsButton';
import { toExportTable } from '@shared/lib/tableExport';
import { useMstatGold, type GoldMarketFeed, type GoldSymbol } from '../api/useMarketPanels';
import { DonutChart, donutColor } from './DonutChart';
import { MarketTreemap } from './MarketTreemap';
import { Sparkline } from './Sparkline';
import { SourceNotice, StatusError, StatusLoading, StatusNoData, StatusSection } from './StatusShell';
import { TONE_CLASS, toneOf } from '../lib/tones';

const SUB_TABS = [
  { key: 'overview', label: 'نمای کلیِ طلا' },
  { key: 'tables', label: 'جدول‌های طلا و سکه' },
  { key: 'funds', label: 'صندوق‌های طلا: ترکیب و نقشه' },
] as const;

type SubTab = (typeof SUB_TABS)[number]['key'];

/** طبقه‌بندیِ ابزارهایِ طلا: صندوق در برابرِ اوراق/سلف در برابرِ بقیه */
function bucketOf(s: GoldSymbol): 'fund' | 'paper' | 'other' {
  if (s.cls === 'fund') return 'fund';
  if (s.kind === 'other' || s.cls === 'other') return 'paper';
  return 'other';
}

function sortRows(rows: GoldSymbol[], key: keyof GoldSymbol, desc: boolean) {
  return [...rows].sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    if (typeof av === 'number' && typeof bv === 'number') return desc ? bv - av : av - bv;
    const as = String(av ?? '');
    const bs = String(bv ?? '');
    return desc ? bs.localeCompare(as, 'fa') : as.localeCompare(bs, 'fa');
  });
}

export function GoldMarketSection() {
  const [tab, setTab] = useState<SubTab>('overview');
  const { data, isLoading, isError, refetch } = useMstatGold(60);
  const symbols = useMemo(() => data?.symbols ?? [], [data]);

  return (
    <StatusSection
      testId="ms-gold"
      title="بازارِ طلا، سکه و صندوق‌های طلا"
      hint="نمادهایِ طلا/نقرۀ *واقعاً* رویِ تابلو + اعلامِ صریحِ چیزهایی که منبع ندارند"
      asof={data?.asof}
      badge={data ? `مبنا: ${data.basis} · تاریخچه: ${data.history_source}` : undefined}
      toolbar={
        <div className="flex flex-wrap items-center gap-1" role="tablist" data-testid="ms-gold-tabs">
          {SUB_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              data-testid={`ms-gold-tab-${t.key}`}
              onClick={() => setTab(t.key)}
              className={`rounded-full border px-2.5 py-1 text-2xs font-bold transition-colors ${
                tab === t.key
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      }
    >
      {isError && !data ? (
        <StatusError testId="ms-gold" onRetry={() => void refetch()} />
      ) : isLoading && !data ? (
        <StatusLoading testId="ms-gold" />
      ) : !symbols.length ? (
        <>
          <StatusNoData testId="ms-gold" text="هیچ نمادِ طلا/نقره‌ای رویِ تابلویِ این نشست نیست." />
          <SourceNotice testId="ms-gold" items={data?.no_source} />
        </>
      ) : tab === 'overview' ? (
        <GoldOverview data={data!} />
      ) : tab === 'tables' ? (
        <GoldTables data={data!} />
      ) : (
        <GoldFunds data={data!} />
      )}
    </StatusSection>
  );
}

// ══════════════════════════════════════════ ۱) نمایِ کلی (صفحاتِ ۱ و ۳ و ۱۰)
function GoldOverview({ data }: { data: GoldMarketFeed }) {
  const [metric, setMetric] = useState<'value' | 'cap'>('value');
  const symbols = data.symbols ?? [];
  const funds = symbols.filter((s) => bucketOf(s) === 'fund');

  const slices = useMemo(
    () =>
      funds
        .map((s, i) => ({
          key: s.symbol,
          label: s.symbol,
          value:
            metric === 'value'
              ? (s.value_b_toman ?? 0)
              : (s.market_cap_b_toman ?? 0),
          color: donutColor(i),
        }))
        .filter((x) => x.value > 0),
    [funds, metric],
  );
  const sum = slices.reduce((a, s) => a + s.value, 0);
  const coverage = funds.length ? (slices.length / funds.length) * 100 : 0;

  return (
    <div className="flex min-w-0 flex-col gap-2">
      {/* ردیفِ «دارایی‌هایِ مبتنی بر طلا» */}
      <div
        className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6"
        data-testid="ms-gold-cards"
      >
        {symbols.slice(0, 12).map((s) => {
          const tone = toneOf(s.tone);
          return (
            <div
              key={s.ins_code ?? s.symbol}
              data-testid={`gold-card-${s.symbol}`}
              data-tone={tone}
              className={`flex min-w-0 flex-col gap-1 rounded-lg border bg-bg-card px-2 py-1.5 ${TONE_CLASS[tone].border}`}
            >
              <div className="flex items-baseline justify-between gap-1">
                <Link
                  to={`/technical/${encodeURIComponent(s.symbol)}`}
                  data-testid={`gold-card-link-${s.symbol}`}
                  className="truncate text-2xs font-black text-text-primary hover:text-accent-blue"
                >
                  {s.symbol}
                </Link>
                <span className="shrink-0 rounded border border-border-c px-1 text-3xs text-text-muted">
                  {s.kind === 'gold' ? 'طلا' : s.kind === 'silver' ? 'نقره' : s.cls}
                </span>
              </div>
              <span className="num text-2xs text-text-secondary">{fmtInt(s.p_closing ?? null)}</span>
              <span className={`num-text text-2xs font-bold ${TONE_CLASS[tone].text}`}>
                {fmtPct(s.pct ?? null)}
              </span>
              <Sparkline
                testId={`gold-spark-${s.symbol}`}
                values={(s.spark ?? []).map((p) => p.v)}
                tone={tone}
                label={s.symbol}
                width={92}
                height={22}
              />
              <span className="truncate text-3xs text-text-muted" title={s.name ?? undefined}>
                {s.name}
              </span>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
        {/* donut با سوییچِ معیار — دو عددِ جدا، نه یک عدد با برچسبِ عوض‌شده */}
        <div className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <h4 className="text-2xs font-black text-text-primary">ترکیبِ صندوق‌های طلا</h4>
            <div className="flex items-center gap-1" data-testid="ms-gold-donut-metric">
              {(
                [
                  { k: 'value', l: 'ارزش معاملات' },
                  { k: 'cap', l: 'ارزش بازار' },
                ] as const
              ).map((o) => (
                <button
                  key={o.k}
                  type="button"
                  data-testid={`ms-gold-donut-metric-${o.k}`}
                  aria-pressed={metric === o.k}
                  onClick={() => setMetric(o.k)}
                  className={`rounded-full border px-1.5 py-0.5 text-3xs font-bold ${
                    metric === o.k
                      ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                      : 'border-border-c text-text-secondary'
                  }`}
                >
                  {o.l}
                </button>
              ))}
            </div>
          </div>
          <DonutChart
            testId="ms-gold-donut"
            slices={slices}
            unit="میلیارد تومان"
            centerTop={toFaDigits(sum.toFixed(0))}
            centerBottom="میلیارد تومان"
          />
          <p className="num-text text-3xs text-text-muted" data-testid="ms-gold-donut-coverage">
            معیار: {metric === 'value' ? 'ارزش معاملاتِ همین نشست' : 'ارزش بازار'} ·{' '}
            {toFaDigits(slices.length)} از {toFaDigits(funds.length)} صندوقِ طلا مقدارِ این معیار
            دارند ({toFaDigits(coverage.toFixed(0))}٪) — حلقه فقط همین را می‌پوشاند.
          </p>
        </div>

        <PortfolioTrend symbols={funds} />
      </div>

      {/* کارت‌هایِ بی‌منبع: صریح، با علت، بی‌عدد */}
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 xl:grid-cols-4" data-testid="ms-gold-nosource">
        {(data.no_source ?? []).map((n) => (
          <div
            key={n.key}
            data-testid={`gold-nosource-${n.key}`}
            className="flex min-w-0 flex-col gap-1 rounded-lg border border-dashed border-accent-yellow/40 bg-accent-yellow/5 px-2 py-1.5"
          >
            <div className="flex items-baseline justify-between gap-1">
              <span className="text-2xs font-black text-text-primary">{n.label}</span>
              <span className="rounded border border-border-c bg-bg-card px-1 text-3xs text-text-muted">
                بی‌منبع
              </span>
            </div>
            <p className="text-3xs text-text-secondary">{n.why}</p>
            {n.needed ? <p className="text-3xs text-text-muted">لازم: {n.needed}</p> : null}
          </div>
        ))}
      </div>
      <SourceNotice testId="ms-gold" items={data.access_limits} kind="blocker" />
    </div>
  );
}

/** «مدیریتِ سبدِ دارایی»: مجموعِ ارزشِ بازارِ صندوق‌های طلا در زمان + قله */
function PortfolioTrend({ symbols }: { symbols: GoldSymbol[] }) {
  // سریِ مجموع از جعبه‌هایِ sparkِ هر نماد ساخته می‌شود؛ فقط روزهایی که *دست‌کم
  // یک* نماد مقدار دارد می‌نشینند و روزِ بی‌مقدار صفر نمی‌شود.
  const series = useMemo(() => {
    const byDay = new Map<string, number>();
    for (const s of symbols) {
      for (const p of s.spark ?? []) {
        if (!p.d || typeof p.v !== 'number' || !Number.isFinite(p.v)) continue;
        byDay.set(p.d, (byDay.get(p.d) ?? 0) + p.v);
      }
    }
    return [...byDay.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1));
  }, [symbols]);

  if (series.length < 2) {
    return (
      <div className="flex min-w-0 flex-col gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
        <h4 className="text-2xs font-black text-text-primary">روندِ ارزشِ بازارِ صندوق‌های طلا</h4>
        <p data-testid="ms-gold-trend-nodata" className="text-3xs text-text-muted">
          {toFaDigits(series.length)} نقطه — خطِ روند نمی‌کشیم، چون یک نقطه هر شلی را
          «روند» نشان می‌دهد.
        </p>
      </div>
    );
  }
  const vals = series.map(([, v]) => v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const peakAt = series[vals.indexOf(max)]?.[0] ?? '';
  const W = 480;
  const H = 120;
  const x = (i: number) => (i / (series.length - 1)) * W;
  const y = (v: number) => H - 8 - ((v - min) / (max - min || 1)) * (H - 16);
  const d = series.map(([, v], i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');

  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-1">
        <h4 className="text-2xs font-black text-text-primary">روندِ ارزشِ بازارِ صندوق‌های طلا</h4>
        <span className="num-text text-3xs text-text-muted">{toFaDigits(series.length)} روز</span>
      </div>
      <div className="w-full overflow-hidden">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-[120px] w-full" role="img" aria-label="روندِ ارزشِ بازار">
          <path d={d} fill="none" stroke="var(--accent-blue)" strokeWidth="1.6" data-testid="ms-gold-trend-path" />
          <circle cx={x(series.findIndex((s) => s[0] === peakAt))} cy={y(max)} r="3" fill="var(--accent-yellow)" />
          <text x={Math.min(W - 60, x(series.findIndex((s) => s[0] === peakAt)) + 5)} y={y(max) - 4}
                className="fill-text-muted" style={{ fontSize: 8 }}>
            قله {toFaDigits(Math.round(max).toLocaleString('en-US'))}
          </text>
        </svg>
      </div>
      <p className="num-text text-3xs text-text-muted" data-testid="ms-gold-trend-span">
        از {peakAt ? toFaDigits(series[0][0]) : '—'} تا {toFaDigits(series[series.length - 1][0])} ·
        مجموعِ ارزشِ بازار (میلیارد تومان) · قله در {toFaDigits(peakAt)}
      </p>
    </div>
  );
}

// ══════════════════════════════════════════ ۲) جدول‌هایِ جدا (صفحۀ ۱۱)
const TABLE_COLS = {
  fund: ['نماد', 'نام', 'آخرین', 'پایانی', 'تغییر٪', 'ارزش معاملات (م.ت)', 'حجم (م.سهم)', 'ارزش بازار (م.ت)', 'تعداد معامله'],
  paper: ['نماد', 'نام', 'طبقه', 'پایانی', 'تغییر٪', 'ارزش معاملات (م.ت)', 'حجم (م.سهم)'],
  other: ['نماد', 'نام', 'پایانی', 'تغییر٪', 'ارزش معاملات (م.ت)', 'حجم (م.سهم)'],
} as const;

function GoldTable({
  testId,
  title,
  hint,
  rows,
  cols,
  cells,
  base,
}: {
  testId: string;
  title: string;
  hint: string;
  rows: GoldSymbol[];
  cols: readonly string[];
  cells: (r: GoldSymbol) => (string | number | null)[];
  base: string;
}) {
  const [sortKey, setSortKey] = useState(0);
  const [desc, setDesc] = useState(true);
  const sorted = useMemo(() => {
    const keyByCol = ['symbol', 'name', 'p_closing', 'pct', 'value_b_toman', 'volume_m_share', 'market_cap_b_toman', 'trades'] as const;
    const k = keyByCol[sortKey] ?? 'symbol';
    return sortRows(rows, k as keyof GoldSymbol, desc);
  }, [rows, sortKey, desc]);

  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-1">
        <h4 className="text-2xs font-black text-text-primary" title={hint}>
          {title} <span className="num-text text-3xs text-text-muted">({toFaDigits(rows.length)})</span>
        </h4>
        <DownloadRowsButton
          base={base}
          title={`دانلودِ ${title}`}
          count={sorted.length}
          testId={`${testId}-download`}
          getTable={() => toExportTable([...cols], sorted, cells)}
        />
      </div>
      {rows.length ? (
        <div className="min-w-0 max-w-full overflow-x-auto" data-testid={`${testId}-scroller`}>
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr>
                {cols.map((c, i) => (
                  <th
                    key={c}
                    data-testid={`${testId}-th-${i}`}
                    onClick={() => {
                      if (i === sortKey) setDesc((d) => !d);
                      else {
                        setSortKey(i);
                        setDesc(true);
                      }
                    }}
                    className="sticky top-0 z-10 cursor-pointer bg-bg-card/95 px-1.5 py-1 text-start text-3xs font-bold text-text-secondary"
                    aria-sort={sortKey === i ? (desc ? 'descending' : 'ascending') : undefined}
                  >
                    {c}
                    {sortKey === i ? (desc ? ' ↓' : ' ↑') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.ins_code ?? r.symbol} data-testid={`${testId}-row-${r.symbol}`}>
                  {cells(r).map((v, i) => (
                    <td key={i} className="px-1.5 py-1 text-2xs text-text-primary">
                      {i === 0 ? (
                        <Link
                          to={`/technical/${encodeURIComponent(String(v))}`}
                          className="font-black hover:text-accent-blue"
                        >
                          {String(v)}
                        </Link>
                      ) : typeof v === 'number' ? (
                        <span className="num-text">{toFaDigits(v.toFixed?.(1) ?? v)}</span>
                      ) : (
                        (v ?? '—')
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p data-testid={`${testId}-empty`} className="text-3xs text-text-muted">
          این گروه ابزاری درِ این نشست نیست — جدولِ مخلوطِ جایگزین ساخته نمی‌شود.
        </p>
      )}
    </div>
  );
}

function GoldTables({ data }: { data: GoldMarketFeed }) {
  const symbols = data.symbols ?? [];
  const funds = symbols.filter((s) => bucketOf(s) === 'fund');
  const papers = symbols.filter((s) => bucketOf(s) === 'paper');
  const others = symbols.filter((s) => bucketOf(s) === 'other');
  const money = (s: GoldSymbol) => [
    s.symbol, s.name ?? '', s.p_last ?? null, s.p_closing ?? null, s.pct ?? null,
    s.value_b_toman ?? null, s.volume_m_share ?? null, s.market_cap_b_toman ?? null, s.trades ?? null,
  ];
  const paper = (s: GoldSymbol) => [
    s.symbol, s.name ?? '', s.kind ?? s.cls ?? '', s.p_closing ?? null, s.pct ?? null,
    s.value_b_toman ?? null, s.volume_m_share ?? null,
  ];
  const other = (s: GoldSymbol) => [
    s.symbol, s.name ?? '', s.p_closing ?? null, s.pct ?? null, s.value_b_toman ?? null, s.volume_m_share ?? null,
  ];
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <GoldTable
        testId="ms-gold-tbl-fund"
        title="طلا و سکه (صندوق‌های قابلِ معامله)"
        hint={data.unit?.price ?? ''}
        rows={funds}
        cols={TABLE_COLS.fund}
        cells={money}
        base="طلا-صندوق"
      />
      <GoldTable
        testId="ms-gold-tbl-paper"
        title="اوراقِ مرابحۀ طلا و سلفِ سکه"
        hint="ابزارِ بدهی/سلف، نه مالکیتِ فیزیکیِ طلا"
        rows={papers}
        cols={TABLE_COLS.paper}
        cells={paper}
        base="اوراق-طلا"
      />
      <GoldTable
        testId="ms-gold-tbl-other"
        title="سایرِ نمادهایِ مبتنی بر طلا"
        hint="هر ردیفی که نه صندوق است نه اوراق"
        rows={others}
        cols={TABLE_COLS.other}
        cells={other}
        base="سایر-طلا"
      />
      <p className="num-text text-3xs text-text-muted" data-testid="ms-gold-tables-unit">
        یکاها: قیمت {data.unit?.price ?? '—'} · ارزش {data.unit?.value ?? '—'} · حجم{' '}
        {data.unit?.volume ?? '—'} · «ارزشِ ذاتی» درِ مرجع پشتِ ورود/عضویت است و اینجا
        ستونِ جعلی ندارد.
      </p>
      <SourceNotice testId="ms-gold-tables" items={data.access_limits} kind="blocker" />
    </div>
  );
}

// ══════════════════════════════════ ۳) ترکیب + نقشه (صفحۀ ۱۲، دو نمایِ مستقل)
function GoldFunds({ data }: { data: GoldMarketFeed }) {
  const funds = (data.symbols ?? []).filter((s) => bucketOf(s) === 'fund');
  const slices = funds
    .map((s, i) => ({ key: s.symbol, label: `${s.symbol} — ${s.name ?? ''}`, value: s.market_cap_b_toman ?? 0, color: donutColor(i) }))
    .filter((x) => x.value > 0);
  const sum = slices.reduce((a, s) => a + s.value, 0);
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border-c bg-bg-card px-2 py-1.5">
        <h4 className="text-2xs font-black text-text-primary">
          ترکیبِ ارزشِ بازارِ صندوق‌های طلا (نمایِ اول)
        </h4>
        <DonutChart
          testId="ms-gold-funds-donut"
          slices={slices}
          unit="میلیارد تومان"
          centerTop={toFaDigits(sum.toFixed(0))}
          centerBottom="م.ت"
        />
        <p className="num-text text-3xs text-text-muted">
          زمانِ محاسبه: {toFaDigits(data.computed_at ?? '')} · منبع: {data.basis}
        </p>
      </div>
      {/* نمایِ دومِ مستقل: همان نقشۀ بازار با دامنهٔ قفل‌شده رویِ صندوق‌های طلا */}
      <MarketTreemap
        testId="ms-gold-treemap"
        title="نقشۀ بازارِ صندوق‌های طلا (نمایِ دوم)"
        fixedGroup="gold_fund"
      />
      <p className="num-text text-3xs text-text-muted" data-testid="ms-gold-funds-independent">
        donut و نقشه دو نمایِ *مستقل* از یک پاسخ‌اند؛ یکی جایگزینِ دیگری نمی‌شود —
        حلقه سهمِ هر صندوق را می‌شمارد و نقشه سطح را از معیارِ انتخابی می‌سازد.
      </p>
    </div>
  );
}
