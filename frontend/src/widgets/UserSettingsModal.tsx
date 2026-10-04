// widgets/UserSettingsModal.tsx -- پنجره تنظیمات حساب کاربری، تغییر نام کاربری و رمز عبور
import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useAuthStore } from '@shared/stores/authStore';
import { useDialogA11y } from '@shared/lib/useDialogA11y';

interface UserSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function UserSettingsModal({ open, onClose }: UserSettingsModalProps) {
  const currentUsername = useAuthStore((s) => s.username);
  const updateCredentials = useAuthStore((s) => s.updateCredentials);
  const panelRef = useDialogA11y<HTMLDivElement>({ open, onClose });

  const [username, setUsername] = useState(currentUsername);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // همگام‌سازی نام کاربری فعلی هنگام باز شدن
  React.useEffect(() => {
    if (open) {
      setUsername(currentUsername);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setError(null);
      setSuccess(null);
    }
  }, [open, currentUsername]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!currentPassword) {
      setError('جهت اعمال هرگونه تغییر، وارد کردن رمز عبور فعلی الزامی است.');
      return;
    }

    if (!username.trim() || username.trim().length < 2) {
      setError('نام کاربری باید حداقل ۲ کاراکتر باشد.');
      return;
    }

    if (newPassword) {
      if (newPassword.length < 4) {
        setError('رمز عبور جدید باید حداقل ۴ کاراکتر باشد.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('تکرار رمز عبور با رمز عبور جدید همخوانی ندارد.');
        return;
      }
    }

    setLoading(true);
    setTimeout(() => {
      const res = updateCredentials(
        currentPassword,
        username.trim(),
        newPassword ? newPassword : undefined,
      );

      if (!res.success) {
        setError(res.error || 'خطا در ذخیره‌سازی اطلاعات.');
      } else {
        setSuccess('اطلاعات کاربری با موفقیت به‌روزرسانی شد.');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }
      setLoading(false);
    }, 150);
  };

  return createPortal(
    <div
      role="presentation"
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* پس‌زمینه نیمه‌شفاف */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* بدنه دیالوگ */}
      <div
        ref={panelRef}
        tabIndex={-1}
        dir="rtl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-settings-title"
        className="glass-panel relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-secondary p-6 shadow-2xl transition-all outline-none overscroll-contain"
        onClick={(e) => e.stopPropagation()}
      >
        {/* هدر پنجره */}
        <div className="mb-4 flex items-center justify-between border-b border-[var(--hairline)] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-accent bg-border-accent/15 text-sm text-accent-blue">
              ⚙
            </span>
            <div>
              <h2 id="user-settings-title" className="text-sm font-black text-text-primary sm:text-base">
                تنظیمات حساب کاربری و امنیت
              </h2>
              <p className="text-2xs text-text-muted">
                تغییر نام کاربری و رمز عبور ورود به ترمینال
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن پنجره"
            className="rounded-lg p-1.5 text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
          >
            ✕
          </button>
        </div>

        {/* پیام‌های وضعیت */}
        {error && (
          <div
            role="alert"
            className="mb-3 rounded-xl border border-accent-red/40 bg-accent-red/10 p-2.5 text-xs font-bold text-accent-red"
          >
            {error}
          </div>
        )}

        {success && (
          <div
            role="status"
            className="mb-3 rounded-xl border border-accent-green/40 bg-accent-green/10 p-2.5 text-xs font-bold text-accent-green"
          >
            {success}
          </div>
        )}

        {/* فرم */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-xs font-bold text-text-secondary">
              نام کاربری
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              className="w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
              required
            />
          </div>

          <div className="border-t border-[var(--hairline)] pt-2">
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-bold text-text-secondary">
                رمز عبور فعلی <span className="text-accent-red">*</span>
              </label>
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="text-[11px] text-text-muted hover:text-text-primary"
              >
                {showCurrentPassword ? 'پنهان' : 'نمایش'}
              </button>
            </div>
            <input
              type={showCurrentPassword ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="جهت تایید هویت، رمز عبور فعلی را وارد کنید"
              className="w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
              required
            />
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-bold text-text-secondary">
                رمز عبور جدید <span className="text-2xs font-normal text-text-muted">(اختیاری)</span>
              </label>
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="text-[11px] text-text-muted hover:text-text-primary"
              >
                {showNewPassword ? 'پنهان' : 'نمایش'}
              </button>
            </div>
            <input
              type={showNewPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="اگر قصد تغییر رمز را دارید، رمز جدید را وارد کنید"
              className="w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
            />
          </div>

          {newPassword && (
            <div>
              <label className="mb-1 block text-xs font-bold text-text-secondary">
                تکرار رمز عبور جدید
              </label>
              <input
                type={showNewPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="تکرار رمز عبور جدید"
                className="w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
                required
              />
            </div>
          )}

          <div className="mt-2 flex items-center justify-end gap-2 border-t border-[var(--hairline)] pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-border-c bg-bg-card px-4 py-2 text-xs font-bold text-text-secondary transition-all hover:border-border-accent hover:text-text-primary"
            >
              انصراف
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-xl border border-border-accent bg-border-accent/20 px-4 py-2 text-xs font-black text-accent-blue transition-all hover:bg-border-accent/30 disabled:opacity-50"
            >
              {loading ? 'در حال ثبت...' : 'ذخیره تغییرات'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}
