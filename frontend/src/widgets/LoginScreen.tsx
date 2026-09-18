// widgets/LoginScreen.tsx -- صفحه لاگین مدرن اختصاصی ترمینال (Cyberpunk / Bloomberg Dark)
import React, { useState } from 'react';
import { useAuthStore } from '@shared/stores/authStore';

export function LoginScreen() {
  const login = useAuthStore((s) => s.login);
  const activeSavedUser = useAuthStore((s) => s.username);
  const lockoutUntil = useAuthStore((s) => s.lockoutUntil);
  const getLockoutRemaining = useAuthStore((s) => s.getLockoutRemaining);

  const [username, setUsername] = useState(activeSavedUser || 'admin');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [lockoutRemaining, setLockoutRemaining] = useState<number>(0);

  React.useEffect(() => {
    if (activeSavedUser) {
      setUsername(activeSavedUser);
    }
  }, [activeSavedUser]);

  // پایش تایمر قفل ضد بروت‌فورس
  React.useEffect(() => {
    const updateCountdown = () => {
      const rem = getLockoutRemaining();
      setLockoutRemaining(rem);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [lockoutUntil, getLockoutRemaining]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (lockoutRemaining > 0) return;

    setError(null);
    setLoading(true);

    setTimeout(() => {
      const res = login(username, password);
      if (!res.success) {
        setError(res.error || 'خطا در ورود به سیستم.');
        setPassword(''); // پاکسازی رمز عبور برای امنیت بیشتر
      }
      setLoading(false);
    }, 150);
  };

  return (
    <div
      dir="rtl"
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-bg-primary p-4 font-sans text-text-primary selection:bg-neon-cyan/30"
    >
      {/* زمینه سایبرپانک گرید و نئون */}
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
        {/* هدر لاگین */}
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-neon-cyan/40 bg-neon-cyan/10 text-2xl shadow-[0_0_20px_rgba(0,229,255,0.25)]">
            ⚡
          </div>
          <h1 className="text-xl font-black tracking-tight text-text-primary md:text-2xl">
            ترمینال بورس التیمیت
          </h1>
          <p className="mt-1 text-xs text-text-muted">
            سامانه جامع داوری نخبگان بازار سرمایه بر پایه متدولوژی FTS
          </p>
          <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-accent-green/30 bg-accent-green/10 px-3 py-0.5 text-[10px] font-bold text-accent-green">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-green" />
            ایستگاه کاری امن و ایزوله
          </div>
        </div>

        {/* فرم ورود */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div
              role="alert"
              className="rounded-xl border border-accent-red/50 bg-accent-red/10 px-3.5 py-2.5 text-xs font-bold leading-5 text-accent-red"
            >
              {error}
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-xs font-bold text-text-secondary">
              نام کاربری
            </label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              className="w-full rounded-xl border border-border-c bg-bg-secondary/70 px-3.5 py-2.5 text-xs text-text-primary transition-all duration-200 focus:border-neon-cyan focus:outline-none focus:ring-2 focus:ring-neon-cyan/20"
              required
            />
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-xs font-bold text-text-secondary">
                رمز عبور
              </label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-[11px] text-text-muted hover:text-text-primary"
              >
                {showPassword ? 'پنهان‌سازی' : 'نمایش رمز'}
              </button>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-border-c bg-bg-secondary/70 px-3.5 py-2.5 text-xs font-mono text-text-primary transition-all duration-200 focus:border-neon-cyan focus:outline-none focus:ring-2 focus:ring-neon-cyan/20"
                required
              />
            </div>
          </div>

          {lockoutRemaining > 0 && (
            <div
              role="alert"
              className="rounded-xl border border-accent-red/60 bg-accent-red/15 px-3.5 py-2.5 text-center text-xs font-bold leading-5 text-accent-red shadow-inner animate-pulse"
            >
              ⛔ سیستم به دلیل تلاش‌های ناموفق قفل است: {lockoutRemaining} ثانیه صبر کنید.
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-text-muted flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent-blue" />
              ورود با احراز هویت محلی امن
            </span>
            <span className="text-[10px] text-text-muted">
              حداکثر ۵ تلاش مجاز
            </span>
          </div>

          <button
            type="submit"
            disabled={loading || lockoutRemaining > 0}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-neon-cyan/50 bg-neon-cyan/20 py-2.5 text-xs font-black text-neon-cyan transition-all duration-200 hover:bg-neon-cyan/30 hover:shadow-[0_0_15px_rgba(0,229,255,0.3)] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'در حال راستی‌آزمایی...' : lockoutRemaining > 0 ? `قفل موقت (${lockoutRemaining}s)` : 'ورود به ایستگاه معاملاتی ⏎'}
          </button>
        </form>

        <div className="mt-6 border-t border-[var(--hairline)] pt-4 text-center text-[10px] text-text-muted">
          BorsTerminal Ultimate · FTS Elite Architecture
        </div>
      </div>
    </div>
  );
}
