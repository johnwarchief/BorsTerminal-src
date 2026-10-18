// features/market/components/StatusShell.tsx -- قاب‌هایِ مشترکِ صفحۀ «وضعیت بازار»
//
// چرا فایلِ جدا: هفت section تازه + چهار بلوکِ موجود همه به یک قاب نیاز دارند
// (عنوان، زیرنویس، ساعتِ داده، حالتِ loading/error/بی‌داده، و «منبع نرسیده» با
// علت). `MarketStatusPanels.tsx` همان قاب را برایِ سه بلوکِ قدیمی داشت؛ کپی‌کردنش
// در هفت فایلِ تازه یعنی هفت بارِ drift در رنگِ خطا و متنِ بی‌داده — و مرحلۀ ۱
// مأموریت صریح است که این چهار حالت در کلِ صفحه یکسان بمانند.
//
// بی‌داده ≠ صفر ≠ خطا: سه پیامِ جدا، سه ظاهرِ جدا. هیچ‌کدام عدد نمی‌سازند.
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import { RetryAction } from '@shared/components/RetryAction';
import type { PanelReason } from '../api/useMarketPanels';
import { TONE_CLASS, toneOf, type PanelTone } from '../lib/tones';
import type { AsOf } from '../api/useMarketStatusFeed';
import { asOfText } from '../api/useMarketStatusFeed';

export function StatusSection({
  testId,
  title,
  hint,
  asof,
  badge,
  toolbar,
  children,
}: {
  testId: string;
  title: string;
  hint?: string;
  asof?: AsOf | null;
  /** برچسبِ مختصرِ مبنای/یکا — تا هیچ عددی بی‌واحد نماند */
  badge?: string;
  toolbar?: React.ReactNode;
  children: React.ReactNode;
}) {
  const stamp = asOfText(asof);
  return (
    <section
      data-testid={testId}
      className="glass-panel flex min-w-0 flex-col gap-2 rounded-xl border border-border-c p-2.5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <h3 className="text-2xs font-black text-text-primary" title={hint}>
          {title}
        </h3>
        <span className="num-text text-3xs text-text-muted" data-testid={`${testId}-asof`}>
          {stamp ? `ساعتِ داده: ${stamp}` : 'ساعتِ داده: بی‌داده'}
        </span>
      </div>
      {badge ? (
        <div
          className="num-text text-3xs text-text-muted"
          data-testid={`${testId}-basis`}
          title="مبنایِ محاسبه از خودِ پاسخِ API می‌آید، نه از رابط"
        >
          {badge}
        </div>
      ) : null}
      {toolbar}
      {children}
    </section>
  );
}

export function StatusLoading({ testId }: { testId: string }) {
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

export function StatusError({ testId, onRetry }: { testId: string; onRetry: () => void }) {
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

/** حالتِ «بی‌داده» — صریح، بی‌عدد، و با ذکرِ اینکه این یعنی «سنجیده نشد» */
export function StatusNoData({
  testId,
  text = 'این بلوک در این نشست داده‌ای ندارد — «بی‌داده» یعنی سنجیده نشده، نه صفر.',
}: {
  testId: string;
  text?: string;
}) {
  return (
    <p
      data-testid={`${testId}-nodata`}
      className="rounded-lg border border-dashed border-border-c bg-bg-card px-2 py-2 text-2xs text-text-muted"
    >
      {text}
    </p>
  );
}

/**
 * «منبع داده در دسترس نیست» با علت.
 * مرحلۀ ۳ مأموریت: نبودِ منبع باید صریح اعلام شود و هیچ عددی برایش نساخته
 * شود. علت از خودِ پاسخ می‌آید (`no_source` / `blockers`)، پس رابط چیزی را
 * حدس نمی‌زند.
 */
export function SourceNotice({
  testId,
  items,
  kind = 'no_source',
}: {
  testId: string;
  items?: PanelReason[] | null;
  kind?: 'no_source' | 'blocker';
}) {
  if (!items?.length) return null;
  return (
    <ul
      data-testid={`${testId}-${kind}`}
      className="flex flex-col gap-1 rounded-lg border border-dashed border-accent-yellow/40 bg-accent-yellow/5 px-2 py-1.5"
    >
      {items.map((r) => (
        <li key={r.key} className="flex flex-wrap items-baseline gap-x-1 text-3xs text-text-secondary">
          <span className="font-black text-text-primary">{r.label}:</span>
          <span>{r.why}</span>
          {r.needed ? <span className="text-text-muted">({r.needed})</span> : null}
        </li>
      ))}
    </ul>
  );
}

/** برچسبِ رنگیِ یکدستِ مثبت/منفی/خنثی/بی‌داده */
export function ToneChip({
  tone,
  children,
  testId,
}: {
  tone: unknown;
  children: React.ReactNode;
  testId?: string;
}) {
  const t = toneOf(tone) as PanelTone;
  return (
    <span
      data-testid={testId}
      className={`num-text rounded px-1 py-0.5 text-2xs font-bold ${TONE_CLASS[t].text} ${TONE_CLASS[t].bg}`}
    >
      {children}
    </span>
  );
}

/** میله‌ای که طولش از خودِ مقدارِ ردیف می‌آید (نه از ترتیب) */
export function ValueBar({
  testId,
  pct,
  tone = 'pos',
}: {
  testId: string;
  pct: number | null | undefined;
  tone?: unknown;
}) {
  const t = toneOf(tone) as PanelTone;
  const width = typeof pct === 'number' && Number.isFinite(pct) ? Math.min(100, Math.max(0, pct)) : 0;
  return (
    <span
      data-testid={testId}
      className="block h-1.5 w-full overflow-hidden rounded-full bg-bg-secondary"
      aria-hidden
    >
      <span
        className={`block h-full rounded-full ${TONE_CLASS[t].dot}`}
        style={{ width: `${width}%` }}
      />
    </span>
  );
}

export function DashOr({ v, digits }: { v: number | null | undefined; digits?: number }) {
  if (typeof v !== 'number' || !Number.isFinite(v)) return <>—</>;
  return <>{digits == null ? fmtInt(v) : toFaDigits(v.toFixed(digits))}</>;
}
