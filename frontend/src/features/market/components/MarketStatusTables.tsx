// features/market/components/MarketStatusTables.tsx -- جدول‌های صفحۀ «وضعیت بازار»
//
// چرا جدول و نه کارت: مالک رأی داده که «جدول باید بخش اصلی صفحه بماند». هر دو
// جدول از یک اندپوینتِ آماده می‌خوانند (mainwatch و industries) و هیچ ستونی که
// داده‌اش نرسد صفر نمی‌شود — خط تیره می‌ماند.
import { useMemo, useState } from 'react';
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { FormingCandle } from '@shared/components/FormingCandle';
import { RetryAction } from '@shared/components/RetryAction';
import { useIndustries, type IndustryRow } from '../api/useIndustries';
import { useMstatMainwatch, type MainWatchRow } from '../api/useMarketStatusFeed';

const TH = 'sticky top-0 z-10 bg-bg-card/95 px-1.5 py-1.5 text-start text-3xs font-bold text-text-secondary';
const TD = 'px-1.5 py-1 text-2xs text-text-primary';

function TableShell({
  testId,
  title,
  hint,
  loading,
  error,
  empty,
  onRetry,
  children,
}: {
  testId: string;
  title: string;
  hint?: string;
  loading: boolean;
  error: boolean;
  empty: boolean;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  return (
    <section
      data-testid={testId}
      className="glass-panel flex min-w-0 flex-col gap-1.5 rounded-xl border border-border-c p-2.5"
    >
      <h3 className="text-2xs font-black text-text-primary" title={hint}>
        {title}
      </h3>
      {error ? (
        <div
          data-testid={`${testId}-error`}
          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed border-accent-red/50 bg-accent-red/5 px-2 py-1.5 text-2xs text-text-secondary"
        >
          <span>جدول نمی‌رسد — بقیۀ صفحه کار می‌کند</span>
          <RetryAction onRetry={onRetry} testId={`${testId}-retry`} />
        </div>
      ) : loading ? (
        <div data-testid={`${testId}-loading`} className="px-2 py-3 text-2xs text-text-muted">
          در حالِ خواندن…
        </div>
      ) : empty ? (
        <p data-testid={`${testId}-empty`} className="px-2 py-3 text-2xs text-text-muted">
          ردیفی نرسید — «بی‌داده» یعنی این نوبت اندازه‌گیری‌شدنی ندارد، نه این‌که بازار ساکت است.
        </p>
      ) : (
        children
      )}
    </section>
  );
}

/** سه پرچمِ تابلو که مالک درِ این جدول هم می‌خواهد (رأیِ ۱۴۰۵-۰۷-۲۲): حجمِ
 *  مشکوک، ورودِ پولِ هوشمند، و کد به کدِ حقوقی به حقیقی. نام‌ها عینِ
 *  `QUICK_LABELS` درِ تبِ تابلو است؛ داوری درِ `tape_flags.py` و فایل‌هایِ
 *  جزوه (`docs/حجم مشکوک.txt`، `docs/ورود پول هوشمند.txt`،
 *  `docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt`) و این جدول فقط
 *  همان پرچم را می‌خواند. */
const WATCH_FLAGS: { key: 'f_susp' | 'f_smart' | 'f_legal'; chip: string; full: string; tone: string }[] = [
  { key: 'f_susp', chip: 'مشکوک', full: 'حجم مشکوک', tone: 'bg-accent-yellow/15 text-accent-yellow' },
  { key: 'f_smart', chip: 'پول هوشمند', full: 'ورود پول هوشمند', tone: 'bg-accent-green/15 text-accent-green' },
  { key: 'f_legal', chip: 'کد به کد', full: 'کد به کد حقوقی به حقیقی', tone: 'bg-accent-red/15 text-accent-red' },
];

function FlagChips({ row, sourced }: { row: MainWatchRow; sourced: boolean }) {
  if (!sourced) return <span className="text-text-muted">—</span>;
  const flags = row.tape_flags;
  if (!flags) return <span className="text-3xs text-text-muted" title="این نماد درِ فیدِ تابلو نبود">بی‌پرچم</span>;
  const on = WATCH_FLAGS.filter((f) => flags[f.key]);
  if (!on.length) return <span className="text-text-muted">—</span>;
  return (
    <span className="flex flex-wrap items-center gap-1">
      {on.map((f) => (
        <span
          key={f.key}
          title={f.full}
          data-testid={`mainwatch-flag-${f.key}-${row.symbol}`}
          className={`rounded px-1 text-3xs font-bold ${f.tone}`}
        >
          {f.chip}
        </span>
      ))}
    </span>
  );
}

/** نمادهایِ زیرِ نظرِ همان نشست، با قاعدۀ «الگوی ساعت»ِ خودِ موتور */
export function MainWatchTable() {
  const { data, isLoading, isError, refetch } = useMstatMainwatch();
  const rows = data?.rows ?? [];
  const rule = data?.clock_rule;
  // «پرچم نرسید» با «پرچمی ندارد» یکی نیست: بی‌فیدِ تابلو ستون «—» می‌ماند و
  // پایینِ جدول هم همین را می‌گوید، تا هیچ نمادی بی‌دلیلِ «سالم» به‌نظر نرسد.
  const sourced = data?.tape_flags_source === 'api/market';
  return (
    <TableShell
      testId="status-mainwatch"
      title="نمادهای زیرِ نظر"
      hint="ساختۀ خودِ موتور mstat — بی‌فیلترِ دستی"
      loading={isLoading && !data}
      error={isError && !data}
      empty={rows.length === 0}
      onRetry={() => void refetch()}
    >
      {rows.length ? (
        <>
          <div className="min-w-0 max-w-full max-h-[38vh] overflow-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={TH}>نماد</th>
                  <th className={TH}>صنعت</th>
                  <th className={`${TH} text-start`}>آخرین</th>
                  <th className={`${TH} text-start`}>پایانی</th>
                  <th className={`${TH} text-center`}>کندل روز</th>
                  <th className={`${TH} text-start`}>تغییر٪</th>
                  <th className={`${TH} text-start`}>ساعت٪</th>
                  <th className={`${TH} text-start`}>نشان</th>
                  <th className={`${TH} text-start`}>ارزش</th>
                  <th className={`${TH} text-start`}>تعداد</th>
                  <th className={`${TH} text-start`}>قدرت</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r: MainWatchRow) => (
                  <tr key={r.ins_code ?? r.symbol} data-testid={`mainwatch-row-${r.symbol}`}>
                    <td className={`${TD} font-black`}>{r.symbol}</td>
                    <td className={`${TD} max-w-[16ch] text-text-secondary`}>
                      <span className="line-clamp-2">{r.industry ?? '—'}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.p_last)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.p_closing)}</span>
                    </td>
                    <td className={`${TD} text-center`}>
                      <FormingCandle candle={r} testId={`mainwatch-candle-${r.symbol}`} />
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className={`num ${r.pct_close != null && r.pct_close < 0 ? 'text-accent-red' : 'text-accent-green'}`}>
                        {fmtPct(r.pct_close ?? null)}
                      </span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtPct(r.clock_pct ?? null)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <FlagChips row={r} sourced={sourced} />
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.val_b_toman)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.trades)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{r.power != null ? `${toFaDigits(r.power.toFixed(2))}×` : '—'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="num-text text-3xs text-text-muted">
            {toFaDigits(data?.total ?? rows.length)} ردیف · «ساعت٪» با قاعدۀ{' '}
            {rule
              ? `بالای ${fmtPct(rule.min_pct ?? null)} و بیش از ${toFaDigits(rule.min_trades ?? 0)} معامله`
              : 'قواعدِ نرسیده'}{' '}
            ساخته می‌شود.
            {' '}«نشان» همان سه پرچمِ فیلترنویسِ تابلوست (حجم مشکوک، ورود پول هوشمند،
            کد به کد حقوقی به حقیقی){sourced ? '' : ' — پرچم از فیدِ تابلو نرسید'}.
          </p>
        </>
      ) : null}
    </TableShell>
  );
}

const IND_SORTS: Record<string, (r: IndustryRow) => number | null> = {
  value: (r) => (typeof r.value_b_toman === 'number' ? r.value_b_toman : null),
  flow: (r) => (typeof r.flow_b_toman === 'number' ? r.flow_b_toman : null),
  pct: (r) => (typeof r.avg_pct === 'number' ? r.avg_pct : null),
};

/** جمعِ صنایع — همان ردیف‌هایی که «صنایع داغ» در کشو از سه‌تای اولشان کارت می‌سازد */
export function IndustriesTable() {
  const { data, isLoading, isError, refetch } = useIndustries();
  const [sort, setSort] = useState<keyof typeof IND_SORTS>('value');
  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    const get = IND_SORTS[sort];
    return [...all].sort((a, b) => {
      const av = get(a);
      const bv = get(b);
      // سنجهٔ نرسیده هیچ‌وقت رتبه نمی‌گیرد و به جای صفر پایین می‌نشیند
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return bv - av;
    });
  }, [data, sort]);
  return (
    <TableShell
      testId="status-industries"
      title="جمعِ صنایع"
      hint="میانگینِ تغییرِ پایانی نسبت به دیروز در هر صنعت"
      loading={isLoading && !data}
      error={isError && !data}
      empty={rows.length === 0}
      onRetry={() => void refetch()}
    >
      {rows.length ? (
        <>
          <div className="flex flex-wrap items-center gap-1 text-3xs">
            <span className="text-text-muted">مرتب‌سازی:</span>
            {(
              [
                { key: 'value', label: 'ارزش' },
                { key: 'flow', label: 'جریان' },
                { key: 'pct', label: 'میانگین٪' },
              ] as const
            ).map((o) => (
              <button
                key={o.key}
                type="button"
                data-testid={`industries-sort-${o.key}`}
                aria-pressed={sort === o.key}
                onClick={() => setSort(o.key)}
                className={`rounded-full border px-2 py-0.5 font-bold transition-all ${
                  sort === o.key
                    ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                    : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="min-w-0 max-w-full max-h-[38vh] overflow-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={TH}>صنعت</th>
                  <th className={`${TH} text-start`}>نماد</th>
                  <th className={`${TH} text-start`}>مثبت</th>
                  <th className={`${TH} text-start`}>منفی</th>
                  <th className={`${TH} text-start`}>میانگین٪</th>
                  <th className={`${TH} text-start`}>ارزش</th>
                  <th className={`${TH} text-start`}>جریان</th>
                  <th className={`${TH} text-start`}>صف خرید</th>
                  <th className={`${TH} text-start`}>صف فروش</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.industry} data-testid={`industry-row-${r.industry}`}>
                    <td className={`${TD} max-w-[22ch] font-bold`}>
                      <span className="line-clamp-2">{r.industry}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.symbols)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num text-accent-green">{fmtInt(r.positive)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num text-accent-red">{fmtInt(r.negative)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{r.avg_pct != null ? fmtPct(r.avg_pct) : '—'}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.value_b_toman)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{r.flow_b_toman != null ? fmtInt(r.flow_b_toman) : '—'}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.buy_queue_b_toman)}</span>
                    </td>
                    <td className={`${TD} text-start`}>
                      <span className="num">{fmtInt(r.sell_queue_b_toman)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </TableShell>
  );
}
