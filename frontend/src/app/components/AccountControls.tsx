// app/components/AccountControls.tsx --.theme، تنظیمات، آپدیت وِ خروج: یکِ مرجع، سه نما
//
// چرا جدا شد: بندِ ۲.۳ مأموریتِ System ۲ می‌گوید ناوبریِ گوشی باید همانِ قابلیت‌های
// سایدبارِ دسکتاق را داشته باشد، نه کم‌تر. وقتی سایدبار درِ ≤۷۶۷px پنهان می‌شود
// (تا نوارِ پایین تنها مرجعِ ناوبری بماند وِ ۵۶px عرضِ گوشی آزاد شود)، اینِ چهارِ
// کنترل هم باید جایی برسند -- پسِ به‌جایِ نوشتنِ دومینِ نسخۀِ آن‌ها درِ MobileNav،
// خودِ همانِ گره ازِ سایدبار بیرونِ اینِ فایل آمد.
//
// `layout` فقطِ آرایشِ بصری را عوض می‌کند (ریلِ جمع‌شده / کارتِ بازِ دسکتاق / کشویِ
// گوشی)؛ حالتِ modalها وِ `logout` همین‌جا زندگی می‌کنند تا هیچِ نما بی‌خبر ازِ
// دیگری باز نماند.
import { useState } from 'react';
import { useAuthStore } from '@shared/stores/authStore';
import { ThemeToggle } from './ThemeToggle';
import { UserSettingsModal } from '@widgets/UserSettingsModal';
import { UpdateManagerModal } from '@widgets/UpdateManagerModal';

export function AccountControls({ layout }: { layout: 'rail' | 'card' | 'sheet' }) {
  const username = useAuthStore((s) => s.username);
  const logout = useAuthStore((s) => s.logout);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [updateOpen, setUpdateOpen] = useState(false);

  const modals = (
    <>
      <UserSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <UpdateManagerModal open={updateOpen} onClose={() => setUpdateOpen(false)} />
    </>
  );

  if (layout === 'rail') {
    return (
      <div className="flex flex-col items-center gap-1.5 py-1">
        <ThemeToggle compact />
        <button
          type="button"
          onClick={() => setUpdateOpen(true)}
          data-testid="app-update-btn"
          className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-text-secondary transition-all hover:border-neon-cyan hover:text-neon-cyan"
          title="به‌روزرسانی ترمینال"
          aria-label="به‌روزرسانی ترمینال"
        >
          🚀
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          data-testid="user-settings-btn"
          className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue"
          title={`تنظیمات کاربر: ${username}`}
        >
          ⚙
        </button>
        <button
          type="button"
          onClick={logout}
          className="rounded-lg border border-border-c bg-bg-card/60 p-1.5 text-xs text-accent-red transition-all hover:border-accent-red/40 hover:bg-accent-red/10"
          title="خروج از حساب"
        >
          ⎋
        </button>
        {modals}
      </div>
    );
  }

  if (layout === 'sheet') {
    return (
      <div className="mt-1 border-t border-border-c pt-1.5" data-testid="mobile-account-row">
        <div className="grid grid-cols-2 gap-1">
          <div className="flex min-h-[44px] items-center justify-center rounded-lg border border-border-c bg-bg-card/60 px-2">
            <ThemeToggle compact />
          </div>
          <button
            type="button"
            onClick={() => setUpdateOpen(true)}
            data-testid="app-update-btn"
            className="flex min-h-[44px] items-center justify-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2 text-2xs font-bold text-text-secondary"
          >
            🚀 به‌روزرسانی
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            data-testid="user-settings-btn"
            className="flex min-h-[44px] items-center justify-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2 text-2xs font-bold text-text-secondary"
          >
            ⚙ تنظیماتِ حساب
          </button>
          <button
            type="button"
            onClick={logout}
            className="flex min-h-[44px] items-center justify-center gap-1 rounded-lg border border-accent-red/40 bg-accent-red/10 px-2 text-2xs font-bold text-accent-red"
          >
            ⎋ خروج
          </button>
        </div>
        <p className="mt-1 truncate text-3xs text-text-muted">حساب: {username}</p>
        {modals}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/50 p-2 backdrop-blur">
      <div className="flex items-center justify-between gap-1 pb-1.5 border-b border-border-c/50">
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          data-testid="user-settings-btn"
          className="flex items-center gap-1.5 truncate text-2xs font-bold text-text-primary hover:text-accent-blue transition-colors"
          title="تنظیمات کاربر"
        >
          <span className="text-accent-blue">⚙</span>
          <span className="truncate max-w-[85px]">{username}</span>
        </button>
        <button
          type="button"
          onClick={logout}
          className="rounded border border-transparent px-1 text-2xs text-accent-red hover:border-accent-red/40 hover:bg-accent-red/10 transition-colors"
          title="خروج از حساب"
        >
          خروج ⎋
        </button>
      </div>
      <div className="flex items-center justify-between gap-1 pt-1.5">
        <ThemeToggle compact />
        <button
          type="button"
          onClick={() => setUpdateOpen(true)}
          data-testid="app-update-btn"
          className="flex items-center gap-1 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1 text-3xs font-bold text-text-secondary transition-all hover:border-neon-cyan hover:text-neon-cyan"
          title="مدیریت و بررسی به‌روزرسانی سیستم"
        >
          <span>🚀</span>
          <span>آپدیت</span>
        </button>
      </div>
      {modals}
    </div>
  );
}
