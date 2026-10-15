// widgets/LoginScreen.tsx — قفلِ صفحه (کدِ که خودِ کاربر چیده است)
//
// این صفحه فقط وقتی دیده می‌شود که کاربر درِ تنظیمات «قفلِ صفحه» چیده باشد.
// متنِ عمداً صادق است: این یکِ قفلِ محلیِ نمایش است، نه احرازِ هویتِ ازِ راهِ
// شبکه — هیچ سروری درِ کار نبودنِ آن شرکت نمی‌کند و کلِ داده رویِ همین دستگاه است.
import React, { useState } from 'react';
import { useAuthStore } from '@shared/stores/authStore';

export function LoginScreen() {
  const unlock = useAuthStore((s) => s.unlock);
  const lockoutUntil = useAuthStore((s) => s.lockoutUntil);
  const getLockoutRemaining = useAuthStore((s) => s.getLockoutRemaining);

  const [code, setCode] = useState('');
  const [showCode, setShowCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lockoutRemaining, setLockoutRemaining] = useState<number>(0);

  React.useEffect(() => {
    const updateCountdown = () => setLockoutRemaining(getLockoutRemaining());
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [lockoutUntil, getLockoutRemaining]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (lockoutRemaining > 0) return;
    setError(null);
    setLoading(true);
    const res = await unlock(code);
    if (!res.success) {
      setError(res.error || 'کد پذیرفته نشد.');
      setCode('');
    }
    setLoading(false);
  };

  return (
    <div
      dir="rtl"
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-bg-primary p-4 font-sans text-text-primary selection:bg-neon-cyan/30"
      data-testid="login-screen"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(0,229,255,0.12),transparent)]" />

      <div
        className="pointer-events-none absolute inset-0 opacity-15"
        style={{
          backgroundImage:
            'linear-gradient(to right, var(--hairline) 1px, transparent 1px), linear-gradient(to bottom, var(--hairline) 1px, transparent 1px)',
          backgroundSize: '36px 36px',
        }}
      />

      <div className="glass-panel relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-card/85 p-6 shadow-2xl backdrop-blur-xl md:p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-neon-cyan/40 bg-neon-cyan/10 text-2xl shadow-[0_0_20px_rgba(0,229,255,0.25)]">
            🔒
          </div>
          <h1 className="text-xl font-black tracking-tight text-text-primary md:text-2xl">
            ترمینال بورس التیمیت
          </h1>
          <p className="mt-1 text-xs text-text-muted">
            قفلِ همین صفحه رویِ این دستگاه فعال است
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div
              role="alert"
              data-testid="login-error"
              className="rounded-xl border border-accent-red/50 bg-accent-red/10 px-3.5 py-2.5 text-xs font-bold leading-5 text-accent-red"
            >
              {error}
            </div>
          )}

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="screen-code" className="text-xs font-bold text-text-secondary">
                کدِ صفحه
              </label>
              <button
                type="button"
                onClick={() => setShowCode((v) => !v)}
                className="text-[11px] text-text-muted hover:text-text-primary"
              >
                {showCode ? 'پنهان‌سازی' : 'نمایش کد'}
              </button>
            </div>
            <input
              id="screen-code"
              data-testid="login-code"
              type={showCode ? 'text' : 'password'}
              inputMode="text"
              autoComplete="off"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="••••"
              className="num w-full rounded-xl border border-border-c bg-bg-secondary/70 px-3.5 py-2.5 text-xs font-mono text-text-primary transition-all duration-200 focus:border-neon-cyan focus:outline-none focus:ring-2 focus:ring-neon-cyan/20"
              required
            />
          </div>

          {lockoutRemaining > 0 && (
            <div
              role="alert"
              className="rounded-xl border border-accent-red/60 bg-accent-red/15 px-3.5 py-2.5 text-center text-xs font-bold leading-5 text-accent-red shadow-inner animate-pulse"
            >
              ⛔ به دلیل تلاش‌های ناموفق قفل است: {lockoutRemaining} ثانیه صبر کنید.
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-text-muted flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-blue" />
              قفلِ نمایشیِ محلی — بی‌ارتباط با حسابِ کارگزاری
            </span>
            <span className="text-[10px] text-text-muted">حداکثر ۵ تلاش</span>
          </div>

          <button
            type="submit"
            data-testid="login-submit"
            disabled={loading || lockoutRemaining > 0}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-neon-cyan/50 bg-neon-cyan/20 py-2.5 text-xs font-black text-neon-cyan transition-all duration-200 hover:bg-neon-cyan/30 hover:shadow-[0_0_15px_rgba(0,229,255,0.3)] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? 'در حال بازسنجی…'
              : lockoutRemaining > 0
                ? `قفل موقت (${lockoutRemaining}s)`
                : 'بازکردنِ صفحه ⏎'}
          </button>
        </form>

        <div className="mt-6 border-t border-[var(--hairline)] pt-4 text-center text-[10px] text-text-muted">
          BorsTerminal Ultimate · داده رویِ همین دستگاه می‌ماند
        </div>
      </div>
    </div>
  );
}
