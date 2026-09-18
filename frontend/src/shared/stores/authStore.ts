// shared/stores/authStore.ts -- مدیریت احراز هویت و سشن محلی ترمینال
import { create } from 'zustand';

const SESSION_KEY = 'bors_auth_session';
const USER_KEY = 'bors_auth_user';
const PASS_KEY = 'bors_auth_pass';

export const DEFAULT_USER = 'admin';
export const DEFAULT_PASS = 'bors123';

interface AuthState {
  isAuthenticated: boolean;
  username: string;
  failedAttempts: number;
  lockoutUntil: number | null;
  login: (user: string, pass: string) => { success: boolean; error?: string };
  logout: () => void;
  changePassword: (oldPass: string, newPass: string) => { success: boolean; error?: string };
  updateCredentials: (
    currentPass: string,
    newUsername: string,
    newPassword?: string,
  ) => { success: boolean; error?: string };
  resetCredentials: () => void;
  getLockoutRemaining: () => number;
}

const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 30_000; // 30 seconds lockout

export const useAuthStore = create<AuthState>((set, get) => {
  // پاکسازی سشن ماندگار در localStorage تا هر بار اجرای برنامه رمز عبور بخواهد
  if (typeof window !== 'undefined') {
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {
      // no-op
    }
  }

  // سشن صرفاً در طول یک پنجره/جلسه فعال (sessionStorage) نگه‌داری می‌شود
  const savedSession = typeof window !== 'undefined' ? sessionStorage.getItem(SESSION_KEY) : null;
  const savedUser = typeof window !== 'undefined' ? localStorage.getItem(USER_KEY) || DEFAULT_USER : DEFAULT_USER;

  return {
    isAuthenticated: savedSession === 'true',
    username: savedUser,
    failedAttempts: 0,
    lockoutUntil: null,

    getLockoutRemaining: () => {
      const { lockoutUntil } = get();
      if (!lockoutUntil) return 0;
      const rem = Math.ceil((lockoutUntil - Date.now()) / 1000);
      return rem > 0 ? rem : 0;
    },

    login: (user: string, pass: string) => {
      const state = get();
      const now = Date.now();

      // بررسی قفل ناشی از تلاش‌های ناموفق مکرر
      if (state.lockoutUntil && now < state.lockoutUntil) {
        const remainingSec = Math.ceil((state.lockoutUntil - now) / 1000);
        return {
          success: false,
          error: `دسترسی به دلیل تلاش‌های ناموفق مکرر موقتاً مسدود است. لطفاً ${remainingSec} ثانیه دیگر صبر کنید.`,
        };
      }

      const activeUser = (typeof window !== 'undefined' && localStorage.getItem(USER_KEY)) || DEFAULT_USER;
      const activePass = (typeof window !== 'undefined' && localStorage.getItem(PASS_KEY)) || DEFAULT_PASS;

      if (!user.trim() || !pass.trim()) {
        return { success: false, error: 'نام کاربری و رمز عبور را وارد کنید.' };
      }

      if (user.trim() === activeUser && pass === activePass) {
        if (typeof window !== 'undefined') {
          sessionStorage.setItem(SESSION_KEY, 'true');
        }
        set({ isAuthenticated: true, username: activeUser, failedAttempts: 0, lockoutUntil: null });
        return { success: true };
      }

      const newAttempts = state.failedAttempts + 1;
      if (newAttempts >= MAX_ATTEMPTS) {
        const lockoutTime = now + LOCKOUT_MS;
        set({ failedAttempts: newAttempts, lockoutUntil: lockoutTime });
        return {
          success: false,
          error: `۵ بار تلاش ناموفق ثبت گردید. سیستم به مدت ۳۰ ثانیه قفل شد.`,
        };
      }

      set({ failedAttempts: newAttempts });
      const left = MAX_ATTEMPTS - newAttempts;
      return {
        success: false,
        error: `نام کاربری یا رمز عبور اشتباه است (${left} تلاش باقی‌مانده تا قفل موقت).`,
      };
    },

    logout: () => {
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(SESSION_KEY);
      }
      set({ isAuthenticated: false });
    },

    changePassword: (oldPass: string, newPass: string) => {
      const activePass = (typeof window !== 'undefined' && localStorage.getItem(PASS_KEY)) || DEFAULT_PASS;
      if (oldPass !== activePass) {
        return { success: false, error: 'رمز عبور فعلی نادرست است.' };
      }
      if (!newPass || newPass.length < 4) {
        return { success: false, error: 'رمز عبور جدید باید حداقل ۴ کاراکتر باشد.' };
      }
      if (typeof window !== 'undefined') {
        localStorage.setItem(PASS_KEY, newPass);
      }
      return { success: true };
    },

    updateCredentials: (currentPass: string, newUsername: string, newPassword?: string) => {
      const activePass = (typeof window !== 'undefined' && localStorage.getItem(PASS_KEY)) || DEFAULT_PASS;
      if (currentPass !== activePass) {
        return { success: false, error: 'رمز عبور فعلی نادرست است.' };
      }

      const trimmedUser = newUsername.trim();
      if (!trimmedUser || trimmedUser.length < 2) {
        return { success: false, error: 'نام کاربری باید حداقل ۲ کاراکتر باشد.' };
      }

      if (newPassword && newPassword.length < 4) {
        return { success: false, error: 'رمز عبور جدید باید حداقل ۴ کاراکتر باشد.' };
      }

      if (typeof window !== 'undefined') {
        localStorage.setItem(USER_KEY, trimmedUser);
        if (newPassword) {
          localStorage.setItem(PASS_KEY, newPassword);
        }
      }

      set({ username: trimmedUser });
      return { success: true };
    },

    resetCredentials: () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem(PASS_KEY);
        localStorage.removeItem(SESSION_KEY);
        sessionStorage.removeItem(SESSION_KEY);
      }
      set({ isAuthenticated: false, username: DEFAULT_USER, failedAttempts: 0, lockoutUntil: null });
    },
  };
});

