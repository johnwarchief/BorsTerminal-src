// features/updater/UpdateManagerModal.tsx -- مودال مدیریت به‌روزرسانی با تم سایبرپانک / بلومبرگ دارک
import React, { useRef } from 'react';
import { Modal } from '@shared/ui/Modal';
import { useAppUpdater } from './useAppUpdater';
import { openAppLog } from './api/diagnostics';

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
    downloadedBytes,
    totalBytes,
    isDelta,
    packageSize,
    errorMessage,
    checkForUpdates,
    startDownloadAndInstall,
    relaunchApp,
    handleOfflineZipSelect,
    resetState,
  } = useAppUpdater();

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fmtBytes = (n: number): string => {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB'];
    const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
    return (n / Math.pow(1024, i)).toFixed(i ? 1 : 0) + ' ' + u[i];
  };

  React.useEffect(() => {
    if (open && status === 'idle') {
      checkForUpdates(false);
    }
  }, [open, status, checkForUpdates]);

  if (!open) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const exe = files.find((f) => f.name.toLowerCase().endsWith('.exe'));
    const sig = files.find((f) => f.name.toLowerCase().endsWith('.sig'));
    if (exe) {
      handleOfflineZipSelect(exe, sig);
    } else if (files.length) {
      handleOfflineZipSelect(files[0], undefined);
    }
    e.target.value = ''; // اجازهٔ انتخابِ مجددِ همان فایل
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="مدیریت به‌روزرسانی سیستم"
      description={`نسخه فعلی: v${currentVersion} · هستهٔ پایتون · آپدیترِ درون‌برنامه‌ای`}
      className="max-w-lg"
      testId="updater-modal"
    >
      <div className="relative p-5">
        {/* نورپردازی پس‌زمینه */}
        <div className="pointer-events-none absolute -left-20 -top-20 h-44 w-44 rounded-full bg-neon-cyan/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 -right-20 h-44 w-44 rounded-full bg-accent-blue/10 blur-3xl" />
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
                  {isDelta && (
                    <span
                      title="فقط تغییراتِ این نسخه دانلود می‌شود، نه کلِ نصب‌کننده"
                      className="inline-flex items-center gap-1 rounded-md border border-accent-green/50 bg-accent-green/15 px-2 py-0.5 text-2xs font-black text-accent-green"
                    >
                      <span>Δ</span>
                      <span>به‌روزرسانیِ سبک</span>
                      {packageSize > 0 && (
                        <span className="font-mono opacity-80">· {fmtBytes(packageSize)}</span>
                      )}
                    </span>
                  )}
                  {!isDelta && packageSize > 0 && (
                    <span className="text-2xs font-mono text-text-muted">
                      حجم: {fmtBytes(packageSize)}
                    </span>
                  )}
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
                  href={
                    newVersion
                      ? `https://github.com/johnwarchief/BorsTerminal/releases/download/v${newVersion}/BorsTerminal_Ultimate_Setup_v${newVersion}.exe`
                      : 'https://github.com/johnwarchief/BorsTerminal/releases/latest'
                  }
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
              <div className="mt-2 flex items-center justify-between text-2xs text-text-muted">
                <span className="font-mono">
                  {totalBytes > 0
                    ? `${fmtBytes(downloadedBytes)} / ${fmtBytes(totalBytes)}`
                    : 'در حال اتصال به سرور...'}
                </span>
                <span>امضای دیجیتال بسته قبل از اجرا تأیید می‌شود</span>
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
                accept=".exe,.sig,.zip,.msi,.tar.gz"
                multiple
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
            <div className="mt-2 text-2xs text-text-muted">
              هر دو فایل را با هم انتخاب کنید: نصب‌کننده (setup.exe) و امضای آن (setup.exe.sig).
              نصب فقط در صورتِ تأییدِ امضای دیجیتال اجرا می‌شود.
            </div>
          </div>
        </div>

        {/* فوتر مودال */}
        <div className="mt-5 flex items-center justify-between border-t border-[var(--hairline)] pt-3 text-2xs text-text-muted">
          <span>In-App Secure Updater · minisign</span>
          <div className="flex items-center gap-2">
            {/* v1.0.13: کنسول دیگر باز نمی‌شود؛ لاگ‌ها از اینجا دیده می‌شوند. */}
            <button
              type="button"
              onClick={async () => {
                try {
                  await openAppLog();
                } catch {
                  /* در محیطِ تستِ بدونِ سرور بی‌اثر است */
                }
              }}
              title="باز کردن فایل لاگ برنامه (logs/bors.log)"
              className="rounded-lg px-3 py-1 text-xs font-bold text-text-muted hover:text-text-primary"
            >
              مشاهدهٔ لاگ
            </button>
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
      </div>
    </Modal>
  );
}
