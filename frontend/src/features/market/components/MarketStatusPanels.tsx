// features/market/components/MarketStatusPanels.tsx -- بلوک‌های صفحۀ «وضعیت بازار»
//
// سه بلوک از سه اندپوینتِ جدا می‌آیند و هر سه همان قاعده را دارند: نبودِ داده
// «بی‌داده» است، نه صفر و نه سیگنال. ارتفاعِ هر بلوک یک خطِ پاسخ + نمودارِ فشرده
// است تا در ۷۶۸ پیکسلِ ارتفاعِ صفحه جدول هم جا بماند.
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { RetryAction } from '@shared/components/RetryAction';
import type {
  AsOf,
  ClientSplitFeed,
  HistogramFeed,
  PhasesFeed,
} from '../api/useMarketStatusFeed';
import { asOfText } from '../api/useMarketStatusFeed';

/** شمارشی که نیامده خط تیره است، نه صفر — صفر ادعای «سنجیده شد و نبود» می‌کند */
function countOrDash(v: number | null | undefined): string {
  return typeof v === 'number' && Number.isFinite(v) ? toFaDigits(v) : '—';
}

/** قابِ مشترک: عنوان، سنّی از asofِ همان پاسخ، و بدنه */
export function StatusPanel({
  testId,
  title,
  hint,
  asof,
  children,
}: {
  testId: string;
  title: string;
  hint?: string;
  asof?: AsOf | null;
  children: React.ReactNode;
}) {
  const stamp = asOfText(asof);
  return (
    <section
      data-testid={testId}
      className="glass-panel flex min-w-0 flex-col gap-1.5 rounded-xl border border-border-c p-2.5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2">
        <h3 className="text-2xs font-black text-text-primary" title={hint}>
          {title}
        </h3>
        <span className="num-text text-3xs text-text-muted" data-testid={`${testId}-asof`}>
          {stamp ? `ساعتِ داده: ${stamp}` : 'ساعتِ داده: بی‌داده'}
        </span>
      </div>
      {children}
    </section>
  );
}

function PanelError({ testId, onRetry }: { testId: string; onRetry: () => void }) {
  return (
    <div
      data-testid={`${testId}-error`}
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed border-accent-red/50 bg-accent-red/5 px-2 py-1.5 text-2xs text-text-secondary"
    >
      <span>داده نمی‌رسد — بقیۀ صفحه کار می‌کند</span>
      <RetryAction onRetry={onRetry} testId={`${testId}-retry`} />
    </div>
  );
}

function PanelLoading({ testId }: { testId: string }) {
  return (
    <div
      data-testid={`${testId}-loading`}
      className="flex items-center gap-2 rounded-lg border border-dashed border-border-c px-2 py-2 text-2xs text-text-muted"
    >
      <span className="inline-block size-1.5 animate-pulse rounded-full bg-accent-blue" />
      در حالِ خواندن…
    </div>
  );
}

/** توزیعِ درصدِ تغییر — معادلِ histo-statusِ تریدرزآرنا، با سطل‌هایِ خودی */
export function BreadthHistogram({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data: HistogramFeed | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const buckets = data?.histo12 ?? [];
  const max = buckets.reduce((m, b) => Math.max(m, b.count), 0);
  const total = data?.known ?? buckets.reduce((s, b) => s + b.count, 0);
  return (
    <StatusPanel
      testId="status-histogram"
      title="توزیعِ درصدِ تغییرِ قیمت"
      hint={data?.basis ? `مبنایِ سنجش: ${data.basis}` : undefined}
      asof={data?.asof}
    >
      {isError && !data ? (
        <PanelError testId="status-histogram" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <PanelLoading testId="status-histogram" />
      ) : buckets.length === 0 ? (
        <p data-testid="status-histogram-empty" className="text-2xs text-text-muted">
          سطلی برایِ این نشست ساخته نشده — «بی‌داده» یعنی اندازه‌گیری ممکن نبود، نه بازارِ بی‌حرکت.
        </p>
      ) : (
        <>
          <div dir="ltr" className="flex h-[74px] items-end gap-[3px]">
            {buckets.map((b) => {
              const h = max > 0 ? Math.round((b.count / max) * 100) : 0;
              const color =
                b.color === 'neg' ? 'bg-accent-red' : b.color === 'pos' ? 'bg-accent-green' : 'bg-border-c';
              return (
                <div
                  key={b.key}
                  data-testid={`histo-bucket-${b.key}`}
                  className="flex min-w-0 flex-1 flex-col items-center justify-end gap-0.5"
                  title={`${b.label}: ${toFaDigits(b.count)} نماد`}
                >
                  <span className="num text-3xs leading-3 text-text-secondary">{toFaDigits(b.count)}</span>
                  <span
                    className={`w-full rounded-t ${color} ${b.count === 0 ? 'opacity-25' : 'opacity-90'}`}
                    style={{ height: `${Math.max(2, (h / 100) * 52)}px` }}
                  />
                </div>
              );
            })}
          </div>
          <div dir="ltr" className="flex gap-[3px] text-3xs text-text-muted">
            {buckets.map((b, i) => {
              // دوازده برچسبِ کامل در ۳۹ پیکسل جا نمی‌شوند (سنجشِ زنده: حروف
              // روی هم افتادند). فقط هر سومین میله نام می‌گیرد، کوتاه‌شده؛
              // نامِ کامل درِ titleِ همان میله است.
              const show = i % 3 === 0 || i === buckets.length - 1;
              const short = show ? (b.label.includes(' تا ') ? b.label.split(' تا ')[0] : b.label) : '';
              const edge = i === 0 || i === buckets.length - 1;
              return (
                <span
                  key={b.key}
                  className={`min-w-0 flex-1 ${edge ? `overflow-visible whitespace-nowrap ${i === 0 ? 'text-start' : 'text-end'}` : 'truncate text-center'}`}
                  title={b.label}
                >
                  {short}
                </span>
              );
            })}
          </div>
          <p className="num-text text-3xs text-text-secondary" data-testid="status-histogram-foot">
            سنجیده‌شده: <span className="num">{toFaDigits(total)}</span> · بی‌داده:{' '}
            <span className="num">{countOrDash(data?.nodata)}</span> · بی‌معامله:{' '}
            <span className="num">{countOrDash(data?.not_traded)}</span>
          </p>
        </>
      )}
    </StatusPanel>
  );
}

/** تفکیکِ حقیقی/حقوقی — دو نوارِ تقسیم‌شده، بی‌عددِ ساختگی */
export function ClientSplitPanel({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data: ClientSplitFeed | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const rows: Array<{ key: 'retail' | 'institutional'; label: string }> = [
    { key: 'retail', label: 'حقیقی' },
    { key: 'institutional', label: 'حقوقی' },
  ];
  return (
    <StatusPanel testId="status-clientsplit" title="تفکیکِ خریدِ حقیقی و حقوقی" asof={data?.asof}>
      {isError && !data ? (
        <PanelError testId="status-clientsplit" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <PanelLoading testId="status-clientsplit" />
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map(({ key, label }) => {
            const s = data?.[key];
            const buy = s?.buy_b_toman;
            const sell = s?.sell_b_toman;
            const have = typeof buy === 'number' && typeof sell === 'number' && buy + sell > 0;
            const buyPct = have ? (buy! / (buy! + sell!)) * 100 : 0;
            return (
              <div key={key} data-testid={`clientsplit-${key}`} className="flex flex-col gap-0.5">
                <div className="flex items-baseline justify-between gap-2 text-2xs">
                  <span className="font-bold text-text-primary">{label}</span>
                  {have ? (
                    <span className="num-text text-text-secondary">
                      خرید <span className="num">{fmtInt(buy)}</span> · فروش{' '}
                      <span className="num">{fmtInt(sell)}</span> میلیارد تومان · قدرت{' '}
                      <span className="num">{fmtPct(s?.buy_pct ?? null)}</span>
                    </span>
                  ) : (
                    <span className="text-text-muted">بی‌داده</span>
                  )}
                </div>
                <div dir="ltr" className="flex h-1.5 w-full overflow-hidden rounded-full bg-bg-secondary">
                  <span className="block bg-accent-green" style={{ width: `${have ? buyPct : 0}%` }} />
                  <span className="block flex-1 bg-accent-red/80" />
                </div>
              </div>
            );
          })}
          <p className="num-text text-3xs text-text-secondary">
            خالصِ خریدِ حقیقی: <span className="num">{fmtInt(data?.pc_buy_m_toman)}</span> · فروش:{' '}
            <span className="num">{fmtInt(data?.pc_sell_m_toman)}</span> م.ت · جریانِ کل:{' '}
            <span className="num">{fmtInt(data?.money_flow_b_toman)}</span> میلیارد تومان
          </p>
        </div>
      )}
    </StatusPanel>
  );
}

/** فازهای نشست — چند بار هر جهتِ جابه‌جایی رخ داد (معادلِ نمودارِ وضعیتِ تریدرزآرنا) */
export function SessionPhasesPanel({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data: PhasesFeed | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  const rows = [
    { key: 'green', tone: 'text-accent-green border-accent-green/40 bg-accent-green/10', items: data?.green ?? [] },
    { key: 'red', tone: 'text-accent-red border-accent-red/40 bg-accent-red/10', items: data?.red ?? [] },
  ];
  return (
    <StatusPanel
      testId="status-phases"
      title="چرخشِ وضعیتِ نمادها"
      hint="جابه‌جاییِ وضعیتِ هر نماد (صفِ خرید/فروش/مثبت/منفی) بین دو نقطۀِ نمونه‌برداریِ متوالی"
    >
      {isError && !data ? (
        <PanelError testId="status-phases" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <PanelLoading testId="status-phases" />
      ) : data?.ready === false ? (
        <p data-testid="status-phases-empty" className="text-2xs text-text-muted">
          فقط <span className="num">{toFaDigits(data?.points ?? 0)}</span> نقطه در تاریخچه — برای داوریِ
          فاز به دو نقطه نیاز است؛ این «بی‌حرکتی» نیست.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {rows.map((r) => (
            <div key={r.key} className="flex flex-wrap items-center gap-1" data-testid={`phases-${r.key}`}>
              {r.items.length === 0 ? (
                <span className="text-2xs text-text-muted">
                  {r.key === 'green' ? 'هیچِ جابه‌جاییِ مثبتی ثبت نشد' : 'هیچِ جابه‌جاییِ منفی ثبت نشد'}
                </span>
              ) : null}
              {r.items.map((p) => (
                <span
                  key={p.key}
                  data-testid={`phase-${p.key}`}
                  className={`rounded-full border px-1.5 py-0.5 text-3xs font-bold ${r.tone}`}
                  title={p.label}
                >
                  {p.label} <span className="num">{toFaDigits(p.count)}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
    </StatusPanel>
  );
}
