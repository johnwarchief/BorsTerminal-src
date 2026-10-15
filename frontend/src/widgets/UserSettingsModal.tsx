// widgets/UserSettingsModal.tsx — نامِ نمایشی و قفلِ صفحه (محلی، بی‌رمزِ ثابت)
import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { normalizeCode, useAuthStore } from '@shared/stores/authStore';
import { useDialogA11y } from '@shared/lib/useDialogA11y';

interface UserSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function UserSettingsModal({ open, onClose }: UserSettingsModalProps) {
  const currentUsername = useAuthStore((s) => s.username);
  const locked = useAuthStore((s) => s.locked);
  const setDisplayName = useAuthStore((s) => s.setDisplayName);
  const setLock = useAuthStore((s) => s.setLock);
  const clearLock = useAuthStore((s) => s.clearLock);
  const panelRef = useDialogA11y<HTMLDivElement>({ open, onClose });

  const [username, setUsername] = useState(currentUsername);
  const [currentCode, setCurrentCode] = useState('');
  const [newCode, setNewCode] = useState('');
  const [confirmCode, setConfirmCode] = useState('');

  const [showCurrentCode, setShowCurrentCode] = useState(false);
  const [showNewCode, setShowNewCode] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (open) {
      setUsername(currentUsername);
      setCurrentCode('');
      setNewCode('');
      setConfirmCode('');
      setError(null);
      setSuccess(null);
    }
  }, [open, currentUsername]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const name = username.trim();
    if (!name || name.length < 2) {
      setError('نام نمایشی باید حداقل ۲ کاراکتر باشد.');
      return;
    }
    if (newCode) {
      // مقایسه باید رویِ کدِ نرمال‌شده باشد: «۴۴۵۵» و «4455» یکِ کدند، وگرنه
      // کاربرِ فارسی‌زبان نمی‌تواند قفل بگذارد یا عوض کند.
      const fresh = normalizeCode(newCode);
      if (fresh.length < 4) {
        setError('کدِ صفحه باید حداقل ۴ رقم باشد.');
        return;
      }
      if (fresh !== normalizeCode(confirmCode)) {
        setError('تکرارِ کد با کدِ جدید همخوانی ندارد.');
        return;
      }
    }

    setLoading(true);
    try {
      const nameRes = setDisplayName(name);
      if (!nameRes.success) {
        setError(nameRes.error || 'نام ذخیره نشد.');
        return;
      }

      if (!locked) {
        if (!newCode) {
          setSuccess('نام ذخیره شد. برایِ قفلِ صفحه، یکِ کدِ حداقل ۴ رقمی بگذارید.');
          return;
        }
        const res = await setLock(newCode);
        if (!res.success) {
          setError(res.error || 'قفل چیده نشد.');
          return;
        }
        setSuccess('قفلِ صفحه فعال شد. این کد فقط رویِ همین دستگاه کار می‌کند و هیچ‌جا به‌صورتِ متن ذخیره نمی‌شود.');
      } else {
        if (!newCode && !currentCode) {
          setSuccess('نام ذخیره شد.');
          return;
        }
        if (!currentCode) {
          setError('برایِ تغییر یا برداشتنِ قفل، کدِ فعلی لازم است.');
          return;
        }
        const off = await clearLock(currentCode);
        if (!off.success) {
          setError(off.error || 'کدِ فعلی نادرست است.');
          return;
        }
        if (newCode) {
          const on = await setLock(newCode);
          if (!on.success) {
            setError(on.error || 'قفلِ جدید فعال نشد؛ قفلِ قبلی برداشته شد.');
            return;
          }
          setSuccess('کدِ صفحه عوض شد.');
        } else {
          setSuccess('قفلِ صفحه برداشته شد؛ برنامه بی‌پرسش باز می‌شود.');
        }
      }
      setCurrentCode('');
      setNewCode('');
      setConfirmCode('');
    } finally {
      setLoading(false);
    }
  };

  return createPortal(
    <div
      role="presentation"
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        tabIndex={-1}
        dir="rtl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-settings-title"
        data-testid="user-settings-modal"
        className="glass-panel relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-secondary p-6 shadow-2xl transition-all outline-none overscroll-contain"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between border-b border-[var(--hairline)] pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-accent bg-border-accent/15 text-sm text-accent-blue">
              ⚙
            </span>
            <div>
              <h2 id="user-settings-title" className="text-sm font-black text-text-primary sm:text-base">
                نام و قفلِ صفحه
              </h2>
              <p className="text-2xs text-text-muted">
                قفلِ نمایشیِ محلی — ربطی به حسابِ کارگزاری ندارد
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

        {error && (
          <div
            role="alert"
            data-testid="settings-error"
            className="mb-3 rounded-xl border border-accent-red/40 bg-accent-red/10 p-2.5 text-xs font-bold text-accent-red"
          >
            {error}
          </div>
        )}

        {success && (
          <div
            role="status"
            data-testid="settings-success"
            className="mb-3 rounded-xl border border-accent-green/40 bg-accent-green/10 p-2.5 text-xs font-bold text-accent-green"
          >
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-xs font-bold text-text-secondary">
              نام نمایشی
            </label>
            <input
              type="text"
              data-testid="settings-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
              required
            />
          </div>

          <div className="border-t border-[var(--hairline)] pt-2">
            <div
              data-testid="settings-lock-state"
              className="mb-2 flex items-center justify-between text-2xs"
            >
              <span className="font-bold text-text-secondary">قفلِ صفحه</span>
              <span className={locked ? 'font-bold text-accent-green' : 'text-text-muted'}>
                {locked ? 'فعال' : 'غیرفعال'}
              </span>
            </div>

            {locked && (
              <div className="mb-2">
                <div className="mb-1 flex items-center justify-between">
                  <label className="text-xs font-bold text-text-secondary">
                    کدِ فعلی <span className="text-accent-red">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowCurrentCode((v) => !v)}
                    className="text-[11px] text-text-muted hover:text-text-primary"
                  >
                    {showCurrentCode ? 'پنهان' : 'نمایش'}
                  </button>
                </div>
                <input
                  type={showCurrentCode ? 'text' : 'password'}
                  data-testid="settings-current-code"
                  autoComplete="off"
                  value={currentCode}
                  onChange={(e) => setCurrentCode(e.target.value)}
                  placeholder="برایِ تغییر یا برداشتنِ قفل"
                  className="num w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
                />
              </div>
            )}

            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs font-bold text-text-secondary">
                {locked ? 'کدِ جدید' : 'کدِ صفحه (حداقل ۴ رقم)'}
                {locked ? <span className="text-2xs font-normal text-text-muted"> (اختیاری)</span> : null}
              </label>
              <button
                type="button"
                onClick={() => setShowNewCode((v) => !v)}
                className="text-[11px] text-text-muted hover:text-text-primary"
              >
                {showNewCode ? 'پنهان' : 'نمایش'}
              </button>
            </div>
            <input
              type={showNewCode ? 'text' : 'password'}
              data-testid="settings-new-code"
              autoComplete="off"
              value={newCode}
              onChange={(e) => setNewCode(e.target.value)}
              placeholder={locked ? 'اگر می‌خواهید کد را عوض کنید' : 'مثلاً ۴ رقم'}
              className="num w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
            />

            {!!newCode && (
              <div className="mt-2">
                <label className="mb-1 block text-xs font-bold text-text-secondary">
                  تکرارِ کدِ جدید
                </label>
                <input
                  type={showNewCode ? 'text' : 'password'}
                  data-testid="settings-confirm-code"
                  autoComplete="off"
                  value={confirmCode}
                  onChange={(e) => setConfirmCode(e.target.value)}
                  className="num w-full rounded-xl border border-border-c bg-bg-card/70 px-3 py-2 text-xs font-mono text-text-primary transition-all focus:border-border-accent focus:outline-none focus:ring-1 focus:ring-border-accent"
                  required
                />
              </div>
            )}
          </div>

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
              data-testid="settings-submit"
              disabled={loading}
              className="rounded-xl border border-border-accent bg-border-accent/20 px-4 py-2 text-xs font-black text-accent-blue transition-all hover:bg-border-accent/30 disabled:opacity-50"
            >
              {loading
                ? 'در حال ثبت…'
                : locked
                  ? newCode
                    ? 'ذخیره و تغییر کد'
                    : currentCode
                      ? 'برداشتنِ قفل'
                      : 'ذخیره'
                  : 'فعال‌کردنِ قفل'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}
