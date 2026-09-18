// features/updater/UpdateManagerModal.tsx -- مودال مدیریت به‌روزرسانی با تم سایبرپانک / بلومبرگ دارک
import React, { useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAppUpdater } from './useAppUpdater';

interface UpdateManagerModalProps {
  open: boolean;
  onClose: () => void;
}

export function UpdateManagerModal({ open, onClose }: UpdateManagerModalProps) {
  const {
    status,
    currentVersion,
    newVersion,
    releaseNotes,
    releaseDate,
    downloadProgress,
    errorMessage,
    isTauri,
    checkForUpdates,
    startDownloadAndInstall,
    relaunchApp,
    handleOfflineZipSelect,
    resetState,
  } = useAppUpdater();

  const fileInputRef = useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (open && status === 'idle') {
      checkForUpdates(false);
    }
  }, [open, status, checkForUpdates]);

  if (!open) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleOfflineZipSelect(file);
    }
  };

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="updater-title"
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 selection:bg-neon-cyan/30"
    >
      {/* بک‌دراپ */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-md transition-opacity"
        onClick={onClose}
      />

      {/* پنجره مودال سایبرپانک */}
      <div
        dir="rtl"
        className="glass-panel relative z-10 w-full max-w-lg overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-secondary p-6 shadow-[0_0_50px_rgba(0,0,0,0.8)] transition-all font-sans text-text-primary"
        onClick={(e) => e.stopPropagation()}
      >
        {/* نورپردازی پس‌زمینه */}
        <div className="pointer-events-none absolute -left-20 -top-20 h-44 w-44 rounded-full bg-neon-cyan/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -right-20 h-44 w-44 rounded-full bg-accent-blue/10 blur-3xl" />

        {/* هدر */}
        <div className="mb-5 flex items-center justify-between border-b border-[var(--hairline)] pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-neon-cyan/40 bg-neon-cyan/15 text-lg text-neon-cyan shadow-[0_0_15px_rgba(0,229,255,0.2)]">
              🚀
            </div>
            <div>
              <h2 id="updater-title" className="text-base font-black tracking-tight text-text-primary">
                مدیریت به‌روزرسانی سیستم
              </h2>
              <div className="mt-0.5 flex items-center gap-2 text-2xs text-text-muted">
                <span>نسخه فعلی: <strong className="font-mono text-text-secondary">v{currentVersion}</strong></span>
                <span>•</span>
                <span className={`inline-flex items-center gap-1 font-bold ${isTauri ? 'text-accent-green' : 'text-accent-blue'}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${isTauri ? 'bg-accent-green animate-pulse' : 'bg-accent-blue'}`} />
                  {isTauri ? 'محیط نیتیو Tauri v2' : 'محیط وب / ایزوله'}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن پنجره"
            className="rounded-lg border border-transparent p-1.5 text-text-muted transition-colors hover:border-border-c hover:bg-bg-card hover:text-text-primary"
          >
            ✕
          </button>
        </div>

        {/* بخش محتوا بر اساس وضعیت */}
        <div className="space-y-4">
          {/* خطا */}
          {errorMessage && (
            <div
              role="alert"
              className="rounded-xl border border-accent-red/50 bg-accent-red/10 p-3 text-xs font-bold text-accent-red"
            >
              <div className="flex items-center gap-2">
                <span>⚠️</span>
                <span>{errorMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => checkForUpdates(false)}
                className="mt-2 text-2xs underline hover:text-text-primary"
              >
                تلاش مجدد برای استعلام سرور
              </button>
            </div>
          )}

          {/* در حال بررسی */}
          {status === 'checking' && (
            <div className="flex flex-col items-center justify-center rounded-xl border border-border-c bg-bg-card/40 py-8 text-center">
              <div className="relative mb-3 flex h-12 w-12 items-center justify-center">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-neon-cyan/20 opacity-75" />
                <span className="relative flex h-8 w-8 items-center justify-center rounded-full border border-neon-cyan bg-neon-cyan/20 text-neon-cyan text-sm">
                  ⚡
                </span>
              </div>
              <div className="text-xs font-bold text-text-primary">در حال بررسی سرورهای توزیع و GitHub Releases...</div>
              <div className="mt-1 text-2xs text-text-muted">راستی‌آزمایی امضاهای دیجیتال Minisign</div>
            </div>
          )}

          {/* نسخه جدید موجود است */}
          {status === 'available' && newVersion && (
            <div className="rounded-xl border border-neon-cyan/40 bg-neon-cyan/5 p-4">
              <div className="flex items-center justify-between border-b border-neon-cyan/20 pb-3">
                <div className="flex items-center gap-2">
                  <span className="rounded-md bg-neon-cyan/20 px-2 py-0.5 text-xs font-black text-neon-cyan font-mono">
                    v{newVersion}
                  </span>
                  <span className="text-xs font-bold text-text-primary">نسخه جدید منتشر شده است!</span>
                </div>
                {releaseDate && (
                  <span className="text-2xs text-text-muted">
                    {new Date(releaseDate).toLocaleDateString('fa-IR')}
                  </span>
                )}
              </div>

              {/* گزارش تغییرات */}
              <div className="mt-3">
                <div className="mb-1.5 text-2xs font-bold text-text-secondary">تغییرات و بهبودها:</div>
                <div className="max-h-36 overflow-y-auto rounded-lg border border-[var(--hairline)] bg-bg-primary/70 p-3 text-xs leading-relaxed text-text-secondary font-mono whitespace-pre-wrap">
                  {releaseNotes}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                <a
                  href="https://github.com/johnwarchief/BorsTerminal/releases/latest/download/BorsTerminal_Ultimate_Setup_v1.0.2.exe"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 rounded-xl border border-border-c bg-bg-card/70 px-3.5 py-2 text-xs font-bold text-text-secondary hover:border-accent-blue hover:text-accent-blue transition-all"
                >
                  <span>دانلود مستقیم Setup.exe</span>
                  <span>↗</span>
                </a>
                <button
                  type="button"
                  onClick={startDownloadAndInstall}
                  className="flex items-center gap-2 rounded-xl border border-neon-cyan/60 bg-neon-cyan/20 px-4 py-2 text-xs font-black text-neon-cyan shadow-[0_0_15px_rgba(0,229,255,0.2)] transition-all hover:bg-neon-cyan/30 active:scale-95"
                >
                  <span>دریافت و استقرار خودکار</span>
                  <span>⇩</span>
                </button>
              </div>
            </div>
          )}

          {/* دانلود در حال پیشرفت */}
          {status === 'downloading' && (
            <div className="rounded-xl border border-border-c bg-bg-card/60 p-4">
              <div className="mb-2 flex items-center justify-between text-xs font-bold">
                <span className="text-text-primary">در حال دانلود و راستی‌آزمایی بسته نصبی...</span>
                <span className="font-mono text-neon-cyan">{downloadProgress}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-bg-primary border border-[var(--hairline)]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-accent-blue transition-all duration-200 shadow-[0_0_10px_rgba(0,229,255,0.5)]"
                  style={{ width: `${downloadProgress}%` }}
                />
              </div>
              <div className="mt-2 text-center text-2xs text-text-muted">
                امضای دیجیتال بسته به‌صورت بلادرنگ اعتبارسنجی می‌شود
              </div>
            </div>
          )}

          {/* آماده راه‌اندازی مجدد */}
          {status === 'ready-to-restart' && (
            <div className="rounded-xl border border-accent-green/50 bg-accent-green/10 p-4 text-center">
              <div className="mb-2 text-2xl">✨</div>
              <h3 className="text-sm font-black text-accent-green">به‌روزرسانی با موفقیت آماده شد</h3>
              <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                تمامی فایل‌های باینری جدید مستقر شده‌اند. جهت نهایی‌سازی و اجرای نسخه جدید، دکمه زیر را فشار دهید.
              </p>
              <button
                type="button"
                onClick={relaunchApp}
                className="mt-4 inline-flex items-center gap-2 rounded-xl border border-accent-green/60 bg-accent-green/20 px-5 py-2.5 text-xs font-black text-accent-green shadow-[0_0_20px_rgba(34,197,94,0.3)] transition-all hover:bg-accent-green/30 active:scale-95"
              >
                <span>راه‌اندازی مجدد و اعمال نسخه جدید ⏎</span>
              </button>
            </div>
          )}

          {/* برنامه به‌روز است */}
          {status === 'up-to-date' && (
            <div className="flex flex-col items-center justify-center rounded-xl border border-accent-green/30 bg-accent-green/5 py-6 text-center">
              <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full border border-accent-green/40 bg-accent-green/15 text-accent-green">
                ✓
              </div>
              <div className="text-xs font-bold text-accent-green">ترمینال شما در آخرین نسخه پایدار (v{currentVersion}) قرار دارد.</div>
              <div className="mt-1 text-2xs text-text-muted">نیازی به به‌روزرسانی نیست.</div>
              <button
                type="button"
                onClick={() => checkForUpdates(false)}
                className="mt-4 rounded-lg border border-border-c bg-bg-card px-3 py-1.5 text-2xs font-bold text-text-secondary transition-all hover:border-border-accent hover:text-text-primary"
              >
                بررسی مجدد سرور ⟳
              </button>
            </div>
          )}

          {/* بارگذاری آفلاین فایل زیپ (Fallback در صورت قطعی اینترنت) */}
          <div className="rounded-xl border border-[var(--hairline)] bg-bg-primary/50 p-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm">📦</span>
                <div>
                  <div className="text-xs font-bold text-text-secondary">بارگذاری دستی بسته آفلاین (Fallback)</div>
                  <div className="text-2xs text-text-muted">در صورت محدودیت اینترنت، فایل فشرده ریلیز (.zip/.msi) را دستی وارد کنید</div>
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip,.msi,.exe,.tar.gz"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="rounded-lg border border-border-c bg-bg-card px-3 py-1.5 text-2xs font-bold text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue"
              >
                انتخاب فایل...
              </button>
            </div>
          </div>
        </div>

        {/* فوتر مودال */}
        <div className="mt-5 flex items-center justify-between border-t border-[var(--hairline)] pt-3 text-2xs text-text-muted">
          <span>Tauri v2 · In-App Secure Updater Engine</span>
          <button
            type="button"
            onClick={() => {
              resetState();
              onClose();
            }}
            className="rounded-lg px-3 py-1 text-xs font-bold text-text-muted hover:text-text-primary"
          >
            بستن
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
