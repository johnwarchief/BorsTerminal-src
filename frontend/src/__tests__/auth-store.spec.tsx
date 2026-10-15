// authStore — قفلِ صفحهٔ محلی
//
// چیزی که این پرونده می‌بندد همان چیزی است که نسخۀ پیشین باز میگذاشت: یکِ
// اعتبارنامۀ ثابت درِ سورس (`admin` / `bors123`) که درِ باندلِ APK هم می‌نشست.
// سنجه‌هایِ ۱ و ۲ دقیقاً همان «دربندِ جادویی» را رد می‌کنند، و سنجه‌هایِ ۶ و ۹
// ثابت می‌کنند رویِ دیسک فقطِ هش می‌ماند، نه کدِ خام.
import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore, normalizeCode } from '../shared/stores/authStore';

// jsdom هیچ SubtleCrypto ندارد؛ WebCrypto نود همان PBKDF2 را می‌دهد که درِ
// WebView و مرورگر استفاده می‌شود (بی‌این، تست «قفل چیده نمی‌شود» را می‌داد).
import { webcrypto } from 'node:crypto';

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
}

const LOCK_KEY = 'bors_screen_lock';
const LEGACY_KEY = 'bors_auth_pass';

function resetAll() {
  localStorage.clear();
  sessionStorage.clear();
  const st = useAuthStore.getState();
  st.logout();
  useAuthStore.setState({ locked: false, failedAttempts: 0, lockoutUntil: null, username: '' });
}

describe('قفلِ صفحهٔ محلی', () => {
  beforeEach(() => resetAll());

  it('۰ ارقامِ فارسی و لاتین یکِ کدند (وگرنه «۱۲۳۴»ِ تایپ‌شده هرگز باز نمی‌شود)', () => {
    expect(normalizeCode('۱۲۳۴')).toBe('1234');
    expect(normalizeCode('١٢٣٤')).toBe('1234');
    expect(normalizeCode(' 12 34 ')).toBe('1234');
    expect(normalizeCode('۱۲‍۳۴')).toBe('1234');
  });

  it('۱ بی‌چیدنِ قفل، هیچِ کدی نمی‌پذیرد — نه «باز» است نه «درِ ورود»', async () => {
    expect(useAuthStore.getState().locked).toBe(false);
    const res = await useAuthStore.getState().unlock('bors123');
    expect(res.success).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('۲ هیچ اعتبارنامۀ ثابتی در store نمانده است', () => {
    const keys = Object.keys(useAuthStore.getState());
    expect(keys).not.toContain('login');
    expect(keys).toContain('unlock');
    expect(keys).toContain('setLock');
    expect(LOCK_KEY in localStorage).toBe(false);
  });

  it('۳ کدِ کوتاه قفل نمی‌کند', async () => {
    const res = await useAuthStore.getState().setLock('123');
    expect(res.success).toBe(false);
    expect(useAuthStore.getState().locked).toBe(false);
  });

  it('۴ چیدنِ کد ⇒ قفل فعال و همین نشست باز است', async () => {
    const res = await useAuthStore.getState().setLock('1234');
    expect(res.success).toBe(true);
    expect(useAuthStore.getState().locked).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('۵ کدِ درست می‌گشاید و کدِ غلط رد می‌شود', async () => {
    await useAuthStore.getState().setLock('۴۳۲۱');
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);

    const bad = await useAuthStore.getState().unlock('0000');
    expect(bad.success).toBe(false);
    expect(bad.error).toContain('اشتباه');

    const good = await useAuthStore.getState().unlock('4321');
    expect(good.success).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('۶ رویِ دیسک فقط salt+hash است، نه کدِ خام', async () => {
    await useAuthStore.getState().setLock('9876');
    const blob = localStorage.getItem(LOCK_KEY) || '';
    expect(blob).toContain('PBKDF2-SHA256');
    expect(blob).not.toContain('9876');
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it('۷ پنج تلاشِ ناموفق ⇒ قفلِ ۳۰ ثانیه‌ای (سنسورِ ضد بروت‌فورس زنده است)', async () => {
    await useAuthStore.getState().setLock('1111');
    useAuthStore.getState().logout();
    for (let i = 0; i < 5; i++) await useAuthStore.getState().unlock('0000');
    const blocked = await useAuthStore.getState().unlock('1111');
    expect(blocked.success).toBe(false);
    expect(blocked.error).toContain('مسدود');
    expect(useAuthStore.getState().getLockoutRemaining()).toBeGreaterThan(0);
  });

  it('۸ رمزِ متنِ نسخۀ پیشین یک‌بار مهاجرت می‌کند و بعد خاموش می‌شود', async () => {
    localStorage.setItem(LEGACY_KEY, 'oldsecret1');
    useAuthStore.setState({ locked: false });

    const wrong = await useAuthStore.getState().unlock('nope');
    expect(wrong.success).toBe(false);

    const ok = await useAuthStore.getState().unlock('oldsecret1');
    expect(ok.success).toBe(true);
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
    const blob = localStorage.getItem(LOCK_KEY) || '';
    expect(blob).toContain('PBKDF2-SHA256');
    expect(blob).not.toContain('oldsecret1');
    expect(useAuthStore.getState().locked).toBe(true);
  });

  it('۹ برداشتنِ قفل با کدِ نادرست ممکن نیست، با کدِ درست بله', async () => {
    await useAuthStore.getState().setLock('5566');
    const bad = await useAuthStore.getState().clearLock('0000');
    expect(bad.success).toBe(false);
    expect(useAuthStore.getState().locked).toBe(true);

    const good = await useAuthStore.getState().clearLock('5566');
    expect(good.success).toBe(true);
    expect(useAuthStore.getState().locked).toBe(false);
    expect(localStorage.getItem(LOCK_KEY)).toBeNull();
  });

  it('۱۰ نام نمایشی ذخیره می‌شود و نقشی درِ احراز هویت ندارد', () => {
    expect(useAuthStore.getState().setDisplayName('x').success).toBe(false);
    expect(useAuthStore.getState().setDisplayName('trader').success).toBe(true);
    expect(useAuthStore.getState().username).toBe('trader');
    expect(localStorage.getItem('bors_auth_user')).toBe('trader');
    expect(useAuthStore.getState().locked).toBe(false);
  });
});
