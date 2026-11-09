import { useEffect, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import {
  useUpdateCheck,
  useUpdateDownload,
  useUpdateInstall,
  useUpdateProgress,
  useUpdateRollback,
  useUpdateVersion,
} from '../api/useUpdater';

function megabytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '';
  const mb = Number((bytes / (1024 * 1024)).toFixed(1));
  return `${toFaDigits(mb)} مگابایت`;
}

function percent(done: number, total: number): number {
  if (!total || total <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((done / total) * 100)));
}

const lastUpdateText: Record<string, string> = {
  applied: 'آخرین به‌روزرسانی با موفقیت نصب شد.',
  rolled_back: 'آخرین به‌روزرسانی ناموفق بود؛ نسخهٔ قبلی بازگردانده شد.',
  rollback_failed: 'بازگشت به نسخهٔ قبلی هم ناموفق بود.',
  installing: 'آخرین نصب کامل نشد.',
  failed: 'آخرین به‌روزرسانی انجام نشد.',
  rolling_back: 'بازگشت به نسخهٔ قبلی در جریان بود.',
};

/** نشانِ نسخه و پنلِ به‌روزرسانی در نوارِ بالا. */
export function UpdateChip() {
  const [open, setOpen] = useState(false);
  const [poll, setPoll] = useState(false);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const version = useUpdateVersion();
  const check = useUpdateCheck();
  const download = useUpdateDownload();
  const install = useUpdateInstall();
  const rollback = useUpdateRollback();
  const progress = useUpdateProgress(open && poll);

  const current = version.data?.version ?? '';
  const progressStatus = progress.data?.status ?? '';

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('mousedown', onDown);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => {
    if (current && current !== 'dev' && version.data?.mode === 'installed') void check.mutate();
    // فقط یک‌بار با رسیدنِ نسخه بررسی می‌شود؛ خودِ بررسی دستی هم در دسترس است.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current]);

  useEffect(() => {
    if (progressStatus === 'ready' || progressStatus === 'error') setPoll(false);
  }, [progressStatus]);

  const available = check.data?.available === true;
  const busy = progressStatus === 'downloading' || progressStatus === 'verifying'
    || progressStatus === 'installing' || progressStatus === 'ready';
  const actionError = download.error ?? install.error ?? rollback.error;
  const actionMessage = download.data?.status === 'error' ? download.data.message
    : install.data?.status === 'error' ? install.data.message
      : rollback.data?.status === 'error' ? rollback.data.message
        : check.data?.status === 'error' ? check.data?.message
          : null;

  const last = version.data?.last_update;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        data-testid="update-chip"
        onClick={() => setOpen((v) => !v)}
        title="به‌روزرسانی برنامه"
        className="flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 t-10 text-text-2 hover:border-line-strong hover:text-text"
      >
        {available ? <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden /> : null}
        <span className="num" dir="ltr">{current ? `v${current}` : '—'}</span>
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="به‌روزرسانی برنامه"
          data-testid="update-panel"
          className="absolute end-0 top-full z-50 mt-1 flex w-[340px] flex-col gap-2 rounded-[var(--radius-sm)] border border-line bg-panel p-3 shadow-2xl"
        >
          <div className="flex items-center justify-between">
            <span className="t-10 font-semibold text-text">به‌روزرسانی برنامه</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="بستن" className="tape-btn">×</button>
          </div>

          <div className="flex items-center justify-between t-10 text-text-2">
            <span>نسخهٔ فعلی</span>
            <span className="num text-text" dir="ltr">{current || '—'}</span>
          </div>

          {version.data?.mode === 'portable' ? (
            <p className="t-10 text-text-3">نسخهٔ Portable با نصاب به‌روزرسانی نمی‌شود.</p>
          ) : null}

          {!busy ? (
            <button
              type="button"
              className="tape-btn self-start"
              disabled={check.isPending || !current || current === 'dev'}
              onClick={() => void check.mutate()}
            >
              {check.isPending ? 'در حال بررسی…' : 'بررسی به‌روزرسانی'}
            </button>
          ) : null}

          {check.data && !busy ? (
            check.data.available && check.data.latest_version ? (
              <div className="flex flex-col gap-1 rounded border border-line bg-panel-2 p-2">
                <div className="flex items-center justify-between t-10">
                  <span className="text-text-2">نسخهٔ تازه</span>
                  <span className="num text-text" dir="ltr">{check.data.latest_version}</span>
                </div>
                {check.data.size ? <span className="t-9 text-text-3">{megabytes(check.data.size)}</span> : null}
                {check.data.notes ? <p className="max-h-12 overflow-hidden t-9 text-text-3">{check.data.notes}</p> : null}
                <button
                  type="button"
                  data-testid="update-download"
                  className="tape-btn self-start"
                  disabled={download.isPending || check.data.installable === false}
                  onClick={() => {
                    download.mutate(undefined, { onSuccess: (res) => { if (res.status === 'started') setPoll(true); } });
                  }}
                >
                  {download.isPending ? 'در حال شروع…' : 'دریافت'}
                </button>
              </div>
            ) : (
              <p className="t-10 text-text-3">برنامه به‌روز است.</p>
            )
          ) : null}

          {poll || progressStatus ? (
            <div className="flex flex-col gap-1">
              {progressStatus === 'downloading' || progressStatus === 'verifying' ? (
                <>
                  <div className="flex items-center justify-between t-10 text-text-2">
                    <span>{progressStatus === 'verifying' ? 'راستی‌آزمایی امضا…' : 'در حال دریافت…'}</span>
                    <span className="num">{toFaDigits(percent(progress.data?.downloaded ?? 0, progress.data?.total ?? 0))}٪</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded bg-panel-3">
                    <div
                      className="h-full bg-accent transition-[width] duration-200"
                      style={{ width: `${percent(progress.data?.downloaded ?? 0, progress.data?.total ?? 0)}%` }}
                    />
                  </div>
                </>
              ) : null}
              {progressStatus === 'ready' ? (
                <>
                  <p className="t-10 text-text-2">بسته آماده است.</p>
                  <button
                    type="button"
                    data-testid="update-install"
                    className="tape-btn self-start"
                    disabled={install.isPending}
                    onClick={() => install.mutate()}
                  >
                    {install.isPending ? 'در حال نصب…' : 'نصب و راه‌اندازی دوباره'}
                  </button>
                </>
              ) : null}
              {progressStatus === 'installing' || install.data?.status === 'installing' ? (
                <p className="t-10 text-text-2">در حال نصب؛ برنامه دوباره باز می‌شود.</p>
              ) : null}
            </div>
          ) : null}

          {actionMessage ? <p className="t-10 text-down">{actionMessage}</p> : null}
          {actionError ? <p className="t-10 text-down">{actionError.message}</p> : null}

          {last ? (
            <p
              className={last.status === 'applied' ? 't-9 text-text-3' : 't-9 text-warn'}
              data-testid="update-last"
            >
              {lastUpdateText[last.status] ?? last.message ?? ''}
              {last.from && last.to ? ` (${last.from} → ${last.to})` : ''}
            </p>
          ) : null}

          {version.data?.rollback_available && version.data.rollback_version && !busy ? (
            confirmRollback ? (
              <div className="flex items-center gap-2">
                <span className="t-9 text-text-3">دادهٔ کاربر حفظ می‌شود.</span>
                <button
                  type="button"
                  data-testid="update-rollback-confirm"
                  className="tape-btn"
                  disabled={rollback.isPending}
                  onClick={() => rollback.mutate()}
                >
                  {rollback.isPending ? 'در حال بازگشت…' : 'بله، بازگردان'}
                </button>
                <button type="button" className="tape-btn" onClick={() => setConfirmRollback(false)}>انصراف</button>
              </div>
            ) : (
              <button
                type="button"
                data-testid="update-rollback"
                className="tape-btn self-start text-warn"
                onClick={() => setConfirmRollback(true)}
              >
                بازگشت به نسخهٔ {toFaDigits(version.data.rollback_version)}
              </button>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
