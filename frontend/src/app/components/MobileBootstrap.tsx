import React, { useEffect, useState } from 'react';

type BootProgress = {
  phase: 'download' | 'decompress' | 'database';
  source: 'cache' | 'bundle' | 'release' | '';
  loadedBytes: number;
  totalBytes: number;
  percent: number | null;
  overallPercent: number | null;
};

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '۰ بایت';
  if (bytes < 1024) return \`\${Math.round(bytes)} بایت\`;
  const mb = bytes / (1024 * 1024);
  if (mb < 10) return \`\${mb.toFixed(1)} مگابایت\`;
  return \`\${mb.toFixed(0)} مگابایت\`;
}

function phaseTitle(progress: BootProgress | null): string {
  if (!progress) return 'در حال آماده‌سازی داده‌های آفلاین…';
  switch (progress.phase) {
    case 'download':
      return 'در حال دریافت داده‌های آفلاین…';
    case 'decompress':
      return 'در حال بازگشایی داده‌های آفلاین…';
    case 'database':
      return 'در حال آماده‌سازی پایگاه داده…';
  }
}

export function MobileBootstrap({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [progress, setProgress] = useState<BootProgress | null>(null);

  useEffect(() => {
    if (import.meta.env.VITE_LOCAL_DATA !== '1') {
      setStatus('ready');
      return;
    }

    setStatus('loading');
    let unsubscribe = () => {};

    import('@shared/api/local/localData')
      .then((m) => {
        unsubscribe = m.subscribeBootProgress(setProgress);
        return m.getDb();
      })
      .then(() => {
        setStatus('ready');
      })
      .catch((err) => {
        console.error('Failed to load local DB', err);
        setErrorMsg(err instanceof Error ? err.message : String(err));
        setStatus('error');
      });

    return () => unsubscribe();
  }, []);

  if (status === 'loading') {
    const percent = progress?.overallPercent ?? progress?.percent ?? null;
    const downloaded = progress?.loadedBytes ?? 0;
    const total = progress?.totalBytes ?? 0;
    const remaining = total > 0 ? Math.max(0, total - downloaded) : 0;
    const hasDownloadSize = progress?.phase === 'download' && total > 0;
    const progressWidth = percent === null ? 32 : Math.max(4, Math.min(100, percent));

    return (
      <div
        dir="rtl"
        className="flex h-screen w-screen flex-col items-center justify-center bg-bg-primary text-text-primary p-6 text-center"
      >
        <div className="mb-5 w-full max-w-sm rounded-2xl border border-bg-secondary bg-bg-primary/70 p-5 shadow-lg">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="text-right">
              <h2 className="text-base font-bold">{phaseTitle(progress)}</h2>
              <p className="mt-1 text-xs text-text-muted">
                {progress?.phase === 'download'
                  ? 'پیشرفت دریافت بر اساس حجم واقعی بسته محاسبه می‌شود.'
                  : 'پس از دریافت، داده‌ها بازگشایی و برای استفادهٔ آفلاین آماده می‌شوند.'}
              </p>
            </div>
            <div className="shrink-0 text-lg font-bold tabular-nums" aria-live="polite">
              {percent === null ? '…' : \`\${percent}٪\`}
            </div>
          </div>

          <div
            className="h-2.5 w-full overflow-hidden rounded-full bg-bg-secondary"
            role="progressbar"
            aria-label="پیشرفت آماده‌سازی داده‌های آفلاین"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent ?? undefined}
          >
            <div
              className={percent === null
                ? 'h-full w-1/3 rounded-full bg-accent-blue animate-pulse'
                : 'h-full rounded-full bg-accent-blue transition-[width] duration-200 ease-out'}
              style={percent === null ? undefined : { width: \`\${progressWidth}%\` }}
            />
          </div>

          {hasDownloadSize ? (
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg bg-bg-secondary/60 p-2">
                <div className="text-text-muted">دریافت‌شده</div>
                <div className="mt-1 font-bold tabular-nums">{formatBytes(downloaded)}</div>
              </div>
              <div className="rounded-lg bg-bg-secondary/60 p-2">
                <div className="text-text-muted">باقی‌مانده</div>
                <div className="mt-1 font-bold tabular-nums">{formatBytes(remaining)}</div>
              </div>
              <div className="col-span-2 text-text-muted">
                {formatBytes(total)} حجم کل بسته
              </div>
            </div>
          ) : (
            <div className="mt-4 text-xs text-text-muted">
              {progress?.phase === 'download'
                ? 'در حال دریافت بسته… حجم نهایی هنوز از پاسخ منبع مشخص نشده است.'
                : progress?.phase === 'decompress'
                  ? 'دریافت کامل شد؛ بازگشایی بسته در حال انجام است.'
                  : 'دیتابیس در حال ساخته‌شدن و آماده‌سازی است.'}
            </div>
          )}
        </div>

        <div className="text-[11px] text-text-muted">
          لطفاً برنامه را نبندید؛ این مرحله بیشتر در اولین اجرا یا پس از پاک‌شدن داده‌های محلی طول می‌کشد.
        </div>
      </div>
    );
  }

  if (status === 'error') {
     return (
        <div dir="rtl" className="flex h-screen w-screen flex-col items-center justify-center bg-bg-primary p-6 text-center text-text-primary">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-accent-red/20 text-3xl text-accent-red">
            ⛔
          </div>
          <h1 className="mb-2 text-xl font-bold">خطا در بارگذاری داده‌ها</h1>
          <p className="mb-8 text-sm text-text-secondary" dir="ltr">
            {errorMsg}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-accent-blue px-6 py-2.5 text-sm font-bold text-bg-primary transition-opacity hover:opacity-90"
          >
            تلاش مجدد
          </button>
        </div>
     );
  }

  if (status === 'idle') return null;

  return <>{children}</>;
}
