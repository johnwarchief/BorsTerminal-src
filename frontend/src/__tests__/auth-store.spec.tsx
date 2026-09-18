import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../shared/stores/authStore';

describe('سیستم احراز هویت ترمینال (authStore)', () => {
  beforeEach(() => {
    useAuthStore.getState().resetCredentials();
  });

  it('ورود با رمز عبور اشتباه با خطا مواجه می‌شود', () => {
    const res = useAuthStore.getState().login('admin', 'wrong_pass');
    expect(res.success).toBe(false);
    expect(res.error).toContain('اشتباه');
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('ورود موفق با اعتبار پیش‌فرض admin / bors123', () => {
    const res = useAuthStore.getState().login('admin', 'bors123');
    expect(res.success).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().username).toBe('admin');
  });

  it('خروج از حساب وضعیت ورود را باطل می‌کند', () => {
    useAuthStore.getState().login('admin', 'bors123');
    expect(useAuthStore.getState().isAuthenticated).toBe(true);

    useAuthStore.getState().logout();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('تغییر رمز عبور با اعتبارسنجی رمز قدیمی کار می‌کند', () => {
    // تلاش با رمز قدیمی نادرست
    const failRes = useAuthStore.getState().changePassword('wrong', 'new_pass_123');
    expect(failRes.success).toBe(false);

    // تغییر موفق
    const okRes = useAuthStore.getState().changePassword('bors123', 'my_new_pass');
    expect(okRes.success).toBe(true);

    // ورود با رمز جدید
    const loginRes = useAuthStore.getState().login('admin', 'my_new_pass');
    expect(loginRes.success).toBe(true);
  });

  it('به‌روزرسانی همزمان نام کاربری و رمز عبور (updateCredentials)', () => {
    // تلاش با رمز فعلی اشتباه
    const failRes = useAuthStore.getState().updateCredentials('wrong', 'trader_pro', 'pass_9999');
    expect(failRes.success).toBe(false);
    expect(failRes.error).toContain('نادرست');

    // به‌روزرسانی موفق
    const okRes = useAuthStore.getState().updateCredentials('bors123', 'trader_pro', 'pass_9999');
    expect(okRes.success).toBe(true);
    expect(useAuthStore.getState().username).toBe('trader_pro');

    // بررسی ورود با نام کاربری و رمز جدید
    useAuthStore.getState().logout();
    const loginNew = useAuthStore.getState().login('trader_pro', 'pass_9999');
    expect(loginNew.success).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('تغییر نام کاربری بدون تغییر رمز عبور', () => {
    const okRes = useAuthStore.getState().updateCredentials('bors123', 'analyst');
    expect(okRes.success).toBe(true);
    expect(useAuthStore.getState().username).toBe('analyst');

    useAuthStore.getState().logout();
    // ورود با نام کاربری جدید و همان رمز قبلی
    const loginRes = useAuthStore.getState().login('analyst', 'bors123');
    expect(loginRes.success).toBe(true);
  });

  it('حفاظت ضد بروت‌فورس پس از ۵ تلاش ناموفق فعال می‌شود', () => {
    // ۴ تلاش ناموفق
    for (let i = 1; i <= 4; i++) {
      const res = useAuthStore.getState().login('admin', 'wrong_' + i);
      expect(res.success).toBe(false);
      expect(useAuthStore.getState().failedAttempts).toBe(i);
      expect(useAuthStore.getState().lockoutUntil).toBeNull();
    }

    // تلاش پنجم منجر به قفل شدن می‌شود
    const fifthRes = useAuthStore.getState().login('admin', 'wrong_5');
    expect(fifthRes.success).toBe(false);
    expect(fifthRes.error).toContain('قفل');
    expect(useAuthStore.getState().failedAttempts).toBe(5);
    expect(useAuthStore.getState().lockoutUntil).toBeGreaterThan(Date.now());
    expect(useAuthStore.getState().getLockoutRemaining()).toBeGreaterThan(0);

    // تلاش حتی با رمز درست در حالت قفل رد می‌شود
    const blockedRes = useAuthStore.getState().login('admin', 'bors123');
    expect(blockedRes.success).toBe(false);
    expect(blockedRes.error).toContain('مسدود');
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
