import React, { useEffect, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';

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
  if (bytes < 1024) return `${toFaDigits(Math.round(bytes))} بایت`;
  const mb = bytes / (1024 * 1024);
  return `${toFaDigits(mb < 10 ? mb.toFixed(1) : Math.round(mb))} مگابایت`;
}

function phaseTitle(progress: BootProgress | null): string {
  if (!progress) return 'آماده‌سازی دادهٔ آفلاین…';
  switch (progress.phase) {
    case 'download':
      return 'دریافت دادهٔ آفلاین…';
    case 'decompress':
      return 'بازگشایی بسته…';
    case 'database':
      return 'ساختن پایگاه داده…';
  }
}

/** یک خط: حجمِ دریافت‌شده (فقط وقتی منبع آن را اعلام کرده) و زمانِ گذشته.
 *  بی‌عددِ حجم، زمان تنها شاهدِ زنده ماندنِ مرحله است. */
function statusLine(progress: BootProgress | null, elapsedS: number): string {
  const spent = `${toFaDigits(elapsedS)} ثانیه`;
  if (!progress) return spent;
  if (progress.phase !== 'download') return spent;
  if (progress.totalBytes > 0) {
    return `${formatBytes(progress.loadedBytes)} از ${formatBytes(progress.totalBytes)} · ${spent}`;
  }
  return `بدونِ حجمِ اعلامی · ${spent}`;
}

export function MobileBootstrap({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [progress, setProgress] = useState<BootProgress | null>(null);
  const [elapsedS, setElapsedS] = useState(0);

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

  useEffect(() => {
    if (status !== 'loading') return;
    const t0 = Date.now();
    const id = window.setInterval(() => setElapsedS(Math.round((Date.now() - t0) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [status]);

  if (status === 'loading') {
    // یک عددِ پیوسته برایِ هر سه مرحله (دریافت ۰→۷۰، بازگشایی ۸۵، دیتابیس ۹۵)
    const percent = progress?.overallPercent ?? null;
    const width = percent === null ? 32 : Math.max(4, Math.min(100, percent));

    return (
      <div
        dir="rtl"
        data-testid="mobile-boot"
        className="flex h-screen w-screen flex-col items-center justify-center bg-bg-primary p-6 text-center text-text-primary"
      >
        <div className="w-full max-w-sm rounded-2xl border border-bg-secondary bg-bg-primary/70 p-5 shadow-lg">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-right text-base font-bold">{phaseTitle(progress)}</h2>
            <div className="shrink-0 text-lg font-bold tabular-nums" aria-live="polite">
              {percent === null ? '…' : `${toFaDigits(percent)}٪`}
            </div>
          </div>

          <div
            className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-bg-secondary"
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
              style={percent === null ? undefined : { width: `${width}%` }}
            />
          </div>

          <p className="mt-3 text-xs tabular-nums text-text-muted">{statusLine(progress, elapsedS)}</p>
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
