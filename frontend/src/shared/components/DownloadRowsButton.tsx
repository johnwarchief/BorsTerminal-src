// shared/components/DownloadRowsButton.tsx -- دکمۀ «دانلود» برایِ هر جدولِ داده‌ای
// الگو: همان چیزی که مالک از `scan-document` خواست، بی‌پکیج و بی‌هاجرتِ shadcn —
// یک اکشنِ asyncِ کوچک با حالتِ idle/error و لیبلِ ثابتِ «دانلود» (Save با Download
// قاطی نشود). عرضِ جعبه ثابت است تا عوض‌شدنِ متنِ خطا layout shift نسازد.
import { useCallback, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { downloadCsv, type ExportTable } from '@shared/lib/tableExport';

export function DownloadRowsButton({
  base,
  title,
  count,
  getTable,
  testId = 'download-rows-button',
}: {
  /** پیشوندِ نامِ فایل — نامِ خودِ جدول، نه «export» */
  base: string;
  /** توضیحِ کاملِ «چی دانلود می‌شود» در title */
  title: string;
  /** شمارِ ردیفِ دیدنی؛ صفر ⇒ دکمه غیرفعال است، نه فایلِ خالی */
  count: number;
  getTable: () => ExportTable;
  testId?: string;
}) {
  const [failed, setFailed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onClick = useCallback(() => {
    try {
      downloadCsv(base, getTable());
      setFailed(false);
    } catch {
      setFailed(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setFailed(false), 2500);
    }
  }, [base, getTable]);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={count === 0}
      data-testid={testId}
      data-count={count}
      aria-label={`دانلودِ ${count} ردیفِ دیدنی`}
      title={failed ? 'دانلود نشد — دوباره امتحان کن' : title}
      className={`inline-flex min-w-[74px] shrink-0 items-center justify-center gap-1 rounded-lg border px-2 py-1 text-2xs font-bold transition-colors ${
        failed
          ? 'border-accent-red/50 bg-accent-red/10 text-accent-red'
          : 'border-border-c/70 bg-bg-card/60 text-text-secondary hover:border-accent-green hover:text-accent-green'
      } ${count === 0 ? 'cursor-not-allowed opacity-50 hover:border-border-c/70 hover:text-text-secondary' : ''}`}
    >
      {failed ? 'خطا در دانلود' : 'دانلود'}
      {count > 0 ? <span className="num text-text-muted">({toFaDigits(count)})</span> : null}
    </button>
  );
}
