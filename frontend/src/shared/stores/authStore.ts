// shared/stores/authStore.ts — قفلِ صفحهٔ محلی (بی‌هیچ اعتبارنامهٔ ثابت در سورس)
//
// چرا این بازنویسی: پیش‌ازِ این درِ همین فایل یکِ نام‌کاربری و رمزِ پیش‌فرضِ ثابت
// بود و درِ باندلِ built (و پس درِ APK) می‌نشست — یعنی یکِ رمز
// مشترک و دائمی که هرکس سورس یا بسته را باز کند آن را دارد. آن «ورود» هیچ‌وقت
// احرازِ هویت نبود: هیچ اندپوینتی اعتبار می‌خواست (`dev/loopback_guard_v1029.py`
// خودش می‌گوید API بی‌credential کار می‌کند و مرزِ اعتماد، loopback است). پس چیزی
// که حذف می‌شود توهمِ امنیت است، نه امنیت.
//
// چیزی که می‌ماند: همان قابلیتِ ضروریِ «صفحۀ من، چشمِ دیگران نه» — یکِ کدِ که
// خودِ کاربر می‌چیند، به‌صورتِ salted PBKDF2 ذخیره می‌شود و هیچ‌جا به‌صورتِ متن
// نگه نمی‌ماند. بی‌چیدنِ کد، قفلی نیست و برنامه بی‌پرسش باز می‌شود (رفتارِ
// پیش‌فرضِ دسکتاپ و ابزارهایِ آزمون همین است).
import { create } from 'zustand';

const SESSION_KEY = 'bors_screen_unlocked';
const USER_KEY = 'bors_auth_user';
const LOCK_KEY = 'bors_screen_lock';
/** باقی‌ماندۀ نسخۀِ پیشین: رمزِ *متن* درِ localStorage. */
const LEGACY_PASS_KEY = 'bors_auth_pass';

const MAX_ATTEMPTS = 5;
const LOCKOUT_MS = 30_000;
const PBKDF2_ITERATIONS = 150_000;

export type LockRecord = {
  v: 1;
  algo: 'PBKDF2-SHA256';
  salt: string;
  hash: string;
  iter: number;
  setAt: number;
};

const hasWindow = () => typeof window !== 'undefined';

/** ارقامِ فارسی و عربی به لاتین — وگرنه «۱۲۳۴»ِ تایپ‌شده با «1234» یکی نمی‌شود. */
export function normalizeCode(raw: string): string {
  let out = '';
  for (const ch of (raw || '').trim()) {
    const c = ch.codePointAt(0) ?? 0;
    if (c >= 0x06f0 && c <= 0x06f9) out += String(c - 0x06f0);
    else if (c >= 0x0660 && c <= 0x0669) out += String(c - 0x0660);
    else if (c >= 0x0030 && c <= 0x0039) out += String(c - 0x0030);
    else out += ch;
  }
  return out.replace(/[\u200b-\u200f\s]/g, '');
}

function readLock(): LockRecord | null {
  if (!hasWindow()) return null;
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as LockRecord;
    if (p && p.v === 1 && p.algo === 'PBKDF2-SHA256' && p.salt && p.hash) return p;
    return null;
  } catch {
    return null;
  }
}

function subtle(): SubtleCrypto | null {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  return c && c.subtle ? c.subtle : null;
}

const b64 = (buf: ArrayBuffer) =>
  btoa(String.fromCharCode(...new Uint8Array(buf)));

async function derive(code: string, saltB64: string, iter: number): Promise<string> {
  const s = subtle();
  if (!s) throw new Error('no-webcrypto');
  const salt = Uint8Array.from(atob(saltB64), (ch) => ch.charCodeAt(0));
  const key = await s.importKey('raw', new TextEncoder().encode(code), 'PBKDF2', false, [
    'deriveBits',
  ]);
  const bits = await s.deriveBits({ name: 'PBKDF2', salt, iterations: iter, hash: 'SHA-256' }, key, 256);
  return b64(bits);
}

interface AuthState {
  /** آیا کاربر قفلِ صفحه چیده است؟ (هیچ اعتبارنامۀ ثابتی وجود ندارد) */
  locked: boolean;
  isAuthenticated: boolean;
  username: string;
  failedAttempts: number;
  lockoutUntil: number | null;
  unlock: (code: string) => Promise<{ success: boolean; error?: string }>;
  setLock: (code: string) => Promise<{ success: boolean; error?: string }>;
  clearLock: (code: string) => Promise<{ success: boolean; error?: string }>;
  setDisplayName: (name: string) => { success: boolean; error?: string };
  logout: () => void;
  getLockoutRemaining: () => number;
}

export const useAuthStore = create<AuthState>((set, get) => {
  // پاکسازیِ عمدیِ هر نسخۀِ ماندگارِ «باز» بودن درِ localStorage: قفلِ صفحه باید
  // پسِ بستنِ برنامه دوباره بخواهد.
  if (hasWindow()) {
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {
      /* no-op */
    }
  }
  const savedSession = hasWindow() ? sessionStorage.getItem(SESSION_KEY) : null;
  const savedUser = hasWindow() ? localStorage.getItem(USER_KEY) || '' : '';

  return {
    locked: !!readLock(),
    isAuthenticated: savedSession === 'true',
    username: savedUser,
    failedAttempts: 0,
    lockoutUntil: null,

    getLockoutRemaining: () => {
      const until = get().lockoutUntil;
      if (!until) return 0;
      const rem = Math.ceil((until - Date.now()) / 1000);
      return rem > 0 ? rem : 0;
    },

    unlock: async (code: string) => {
      const state = get();
      const now = Date.now();
      if (state.lockoutUntil && now < state.lockoutUntil) {
        const remainingSec = Math.ceil((state.lockoutUntil - now) / 1000);
        return {
          success: false,
          error: `به دلیل تلاش‌های ناموفق مکرر موقتاً مسدود است. ${remainingSec} ثانیه دیگر صبر کنید.`,
        };
      }
      const attempt = normalizeCode(code);
      if (!attempt) return { success: false, error: 'کدِ صفحه را وارد کنید.' };

      const rec = readLock();
      let ok = false;
      if (rec) {
        try {
          ok = (await derive(attempt, rec.salt, rec.iter)) === rec.hash;
        } catch {
          return { success: false, error: 'این دستگاه نمی‌تواند قفل را بازسنجد.' };
        }
      } else if (hasWindow()) {
        // مهاجرت: رمزِ متنِ نسخۀِ پیشین. اگر درست بود، همان لحظه به قفلِ
        // هش‌شده تبدیل می‌شود و متنِ خام ازِ دیسک می‌رود.
        const legacy = localStorage.getItem(LEGACY_PASS_KEY);
        if (legacy && attempt === normalizeCode(legacy)) {
          await get().setLock(attempt);
          localStorage.removeItem(LEGACY_PASS_KEY);
          ok = true;
        }
      }

      if (ok) {
        if (hasWindow()) sessionStorage.setItem(SESSION_KEY, 'true');
        set({ isAuthenticated: true, failedAttempts: 0, lockoutUntil: null });
        return { success: true };
      }

      const newAttempts = state.failedAttempts + 1;
      if (newAttempts >= MAX_ATTEMPTS) {
        set({ failedAttempts: newAttempts, lockoutUntil: now + LOCKOUT_MS });
        return { success: false, error: '۵ تلاش ناموفق ⇒ قفلِ ۳۰ ثانیه‌ای.' };
      }
      set({ failedAttempts: newAttempts });
      return {
        success: false,
        error: `کدِ صفحه اشتباه است (${MAX_ATTEMPTS - newAttempts} تلاش باقی‌مانده).`,
      };
    },

    setLock: async (code: string) => {
      const attempt = normalizeCode(code);
      if (attempt.length < 4) return { success: false, error: 'کدِ صفحه باید حداقل ۴ رقم باشد.' };
      const s = subtle();
      if (!s) return { success: false, error: 'این مرورگر/WebView WebCrypto ندارد؛ قفل چیده نمی‌شود.' };
      const saltBytes = new Uint8Array(16);
      (globalThis as { crypto: Crypto }).crypto.getRandomValues(saltBytes);
      const salt = b64(saltBytes.buffer as ArrayBuffer);
      const hash = await derive(attempt, salt, PBKDF2_ITERATIONS);
      const rec: LockRecord = {
        v: 1,
        algo: 'PBKDF2-SHA256',
        salt,
        hash,
        iter: PBKDF2_ITERATIONS,
        setAt: Date.now(),
      };
      if (hasWindow()) {
        localStorage.setItem(LOCK_KEY, JSON.stringify(rec));
        localStorage.removeItem(LEGACY_PASS_KEY);
        sessionStorage.setItem(SESSION_KEY, 'true');
      }
      set({ locked: true, isAuthenticated: true, failedAttempts: 0, lockoutUntil: null });
      return { success: true };
    },

    clearLock: async (code: string) => {
      const rec = readLock();
      if (!rec) return { success: true };
      const attempt = normalizeCode(code);
      try {
        if ((await derive(attempt, rec.salt, rec.iter)) !== rec.hash) {
          return { success: false, error: 'کدِ فعلی نادرست است.' };
        }
      } catch {
        return { success: false, error: 'این دستگاه نمی‌تواند قفل را بازسنجد.' };
      }
      if (hasWindow()) {
        localStorage.removeItem(LOCK_KEY);
        localStorage.removeItem(LEGACY_PASS_KEY);
      }
      set({ locked: false });
      return { success: true };
    },

    setDisplayName: (name: string) => {
      const trimmed = (name || '').trim();
      if (!trimmed || trimmed.length < 2) {
        return { success: false, error: 'نام باید حداقل ۲ کاراکتر باشد.' };
      }
      if (hasWindow()) localStorage.setItem(USER_KEY, trimmed);
      set({ username: trimmed });
      return { success: true };
    },

    logout: () => {
      if (hasWindow()) {
        sessionStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(SESSION_KEY);
      }
      set({ isAuthenticated: false });
    },
  };
});
