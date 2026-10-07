// دکمهٔ بازگشتِ سخت‌افزاریِ اندروید.
//
// بی‌این، اندروید رفتارِ پیش‌فرضش را اجرا می‌کند: بستنِ فوریِ اپ. کاربری
// که یک مودال باز کرده با یک لمس کلِ برنامه را می‌بندد — و بارگذاریِ
// بعدی یعنی بازکردنِ دوبارهٔ دیتابیسِ ۲۲ مگابایتی.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const listeners: Record<string, (e: { canGoBack: boolean }) => void> = {};
const exitApp = vi.fn();
vi.mock('@capacitor/app', () => ({
  App: {
    addListener: (name: string, cb: (e: { canGoBack: boolean }) => void) => {
      listeners[name] = cb;
      return Promise.resolve({ remove: vi.fn() });
    },
    exitApp: () => exitApp(),
  },
}));
let native = true;
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => native } }));

const back = (canGoBack = false) => listeners.backButton?.({ canGoBack });

describe('دکمهٔ بازگشتِ اندروید', () => {
  beforeEach(() => { native = true; exitApp.mockReset(); document.body.innerHTML = ''; });
  afterEach(() => { vi.useRealTimers(); });

  it('در مرورگر هیچ شنونده‌ای نمی‌بندد', async () => {
    native = false;
    const { mountAndroidBack } = await import('@shared/api/local/androidShell');
    delete listeners.backButton;
    mountAndroidBack();
    expect(listeners.backButton).toBeUndefined();
  });

  it('پلهٔ ۱ — لایهٔ باز را می‌بندد، نه صفحه را', async () => {
    const { mountAndroidBack } = await import('@shared/api/local/androidShell');
    mountAndroidBack();
    const dlg = document.createElement('div');
    dlg.setAttribute('role', 'dialog');
    dlg.setAttribute('data-state', 'open');
    document.body.appendChild(dlg);
    const esc = vi.fn();
    document.addEventListener('keydown', esc);
    const spy = vi.spyOn(window.history, 'back').mockImplementation(() => {});
    back(true);
    expect(esc).toHaveBeenCalled();
    expect(spy).not.toHaveBeenCalled(); // صفحه نباید عقب برود
    spy.mockRestore();
  });

  it('پلهٔ ۲ — بی‌لایهٔ باز، یک صفحه عقب می‌رود', async () => {
    const { mountAndroidBack } = await import('@shared/api/local/androidShell');
    mountAndroidBack();
    const spy = vi.spyOn(window.history, 'back').mockImplementation(() => {});
    back(true);
    expect(spy).toHaveBeenCalled();
    expect(exitApp).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it('پلهٔ ۳ — رویِ صفحهٔ نخست، لمسِ اول فقط راهنما می‌دهد', async () => {
    const { mountAndroidBack } = await import('@shared/api/local/androidShell');
    mountAndroidBack();
    vi.spyOn(window.history, 'back').mockImplementation(() => {});
    Object.defineProperty(window.history, 'length', { value: 1, configurable: true });
    back(false);
    expect(exitApp).not.toHaveBeenCalled();
    expect(document.querySelector('.bors-exit-hint')?.textContent)
      .toBe('برای خروج دوباره بزنید');
  });

  it('پلهٔ ۳ — لمسِ دومِ سریع خارج می‌شود', async () => {
    const { mountAndroidBack } = await import('@shared/api/local/androidShell');
    mountAndroidBack();
    vi.spyOn(window.history, 'back').mockImplementation(() => {});
    Object.defineProperty(window.history, 'length', { value: 1, configurable: true });
    back(false);
    back(false);
    expect(exitApp).toHaveBeenCalledTimes(1);
  });
});
