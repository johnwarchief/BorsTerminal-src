import React, { useEffect, useState } from 'react';

export function MobileBootstrap({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (import.meta.env.VITE_LOCAL_DATA !== '1') {
      setStatus('ready');
      return;
    }

    setStatus('loading');
    
    // Dynamically import localData so desktop build doesn't include it
    import('@shared/api/local/localData')
      .then((m) => m.getDb())
      .then(() => {
        setStatus('ready');
      })
      .catch((err) => {
        console.error('Failed to load local DB', err);
        setErrorMsg(err instanceof Error ? err.message : String(err));
        setStatus('error');
      });
  }, []);

  if (status === 'loading') {
    return (
      <div dir="rtl" className="flex h-screen w-screen flex-col items-center justify-center bg-bg-primary text-text-primary p-6 text-center">
         <div className="mb-4 h-10 w-10 animate-spin rounded-full border-4 border-bg-secondary border-t-accent-blue"></div>
         <h2 className="text-lg font-bold">در حال آماده‌سازی داده‌های آفلاین...</h2>
         <p className="mt-2 text-xs text-text-muted">این فرآیند ممکن است چند ثانیه زمان ببرد.</p>
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
