// features/market/components/TapeStatusBar.tsx -- نوار وضعیت تابلو: شمارش، سلامت فید و کنترل پولینگ
import { fmtAge } from '@shared/lib/time';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';

const POLL_OPTIONS = [
  { ms: 15_000, label: '15 ثانیه' },
  { ms: 60_000, label: '1 دقیقه' },
  { ms: 300_000, label: '5 دقیقه' },
];

export function TapeStatusBar({
  shown,
  total,
  liveCount,
  fossilCount,
  signals,
  isLoading,
  isError,
  isFetching,
  dataUpdatedAt,
  pollMs,
  onPollChange,
  onRetry,
}: {
  shown: number;
  total: number;
  liveCount: number;
  fossilCount: number;
  signals: number;
  isLoading: boolean;
  isError: boolean;
  isFetching: boolean;
  dataUpdatedAt: number;
  pollMs: number;
  onPollChange: (ms: number) => void;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
      {isLoading ? (
        <span>در حال دریافت تابلو...</span>
      ) : isError ? (
        <span className="text-accent-red">
          خطا در دریافت تابلو
          <button type="button" onClick={onRetry} className="mr-2 underline hover:text-accent-blue">
            تلاش دوباره
          </button>
        </span>
      ) : (
        <>
          <Badge tone="blue">
            {toFaDigits(shown)} از {toFaDigits(total)} نماد
          </Badge>
          <Badge tone="green">زنده {toFaDigits(liveCount)}</Badge>
          {fossilCount > 0 && <Badge tone="gray">غیرزنده {toFaDigits(fossilCount)}</Badge>}
          <Badge tone="orange">{toFaDigits(signals)} سیگنال تابلو</Badge>
          <span>آخرین به روز رسانی: {dataUpdatedAt ? fmtAge(dataUpdatedAt) : '-'}</span>
          {isFetching && <span>...</span>}
        </>
      )}
      <span className="mr-auto flex items-center gap-2">
        <label htmlFor="poll-ms">بازه به روز رسانی</label>
        <select
          id="poll-ms"
          value={pollMs}
          onChange={(e) => onPollChange(Number(e.target.value))}
          className="rounded-lg border border-border-c bg-bg-secondary px-2 py-1 text-xs text-text-primary"
        >
          {POLL_OPTIONS.map((o) => (
            <option key={o.ms} value={o.ms}>
              {o.label}
            </option>
          ))}
        </select>
      </span>
    </div>
  );
}
