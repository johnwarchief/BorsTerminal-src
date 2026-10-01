// shared/api/local/androidShell.ts — رفتارهایِ بومیِ اندروید
//
// فقط در بیلدِ موبایل بار می‌شود (زنجیرهٔ ایمپورتِ shared/api/local پشتِ
// پرچمِ VITE_LOCAL_DATA است) — بیلدِ دسکتاپ هیچ بایتی از آن ندارد.

import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

/** آیا واقعاً داخلِ پوستهٔ بومی هستیم (نه پیش‌نمایشِ مرورگر)؟ */
function isNative(): boolean {
  try {
    return Capacitor.isNativePlatform();
  } catch {
    return false;
  }
}

/**
 * دکمهٔ بازگشتِ سخت‌افزاریِ اندروید.
 *
 * بی‌این، اندروید رفتارِ پیش‌فرضش را اجرا می‌کند: **بستنِ فوریِ اپ**. کاربری
 * که یک مودال باز کرده یا سه تب جلو رفته، با یک لمسِ بازگشت کلِ برنامه را
 * می‌بندد — و چون بارگذاریِ بعدی یعنی باز کردنِ دوبارهٔ دیتابیسِ ۲۲
 * مگابایتی، هزینه‌اش فقط آزار نیست، چند ثانیه انتظار است.
 *
 * رفتارِ درست سه پله دارد:
 *   ۱. اگر چیزی رویِ صفحه باز است (مودال/کشو/پاپ‌اور) ⇒ همان بسته شود.
 *      Radix با Escape می‌بندد، پس همان رویداد فرستاده می‌شود و خودِ
 *      کتابخانه لایهٔ رویی را برمی‌دارد — بی‌آنکه اینجا فهرستی از
 *      مودال‌ها نگه داریم که روزی از کد عقب بیفتد.
 *   ۲. وگرنه اگر تاریخچهٔ درون‌برنامه‌ای عقب دارد ⇒ یک صفحه عقب.
 *   ۳. وگرنه (رویِ صفحهٔ نخست) ⇒ «برایِ خروج دوباره بزنید»، با پنجرهٔ دو
 *      ثانیه‌ای. خروجِ تکی رویِ یک برنامهٔ مالی خیلی آسان است.
 */
export function mountAndroidBack(): () => void {
  if (!isNative()) return () => {};

  let lastPress = 0;
  let toast: HTMLDivElement | null = null;

  const hint = () => {
    toast?.remove();
    toast = document.createElement('div');
    toast.className = 'bors-exit-hint';
    toast.textContent = 'برای خروج دوباره بزنید';
    document.body.appendChild(toast);
    window.setTimeout(() => {
      toast?.remove();
      toast = null;
    }, 2000);
  };

  /** آیا لایه‌ای رویِ صفحه باز است؟ Radix روی همه `data-state="open"` می‌گذارد. */
  const hasOverlay = () =>
    document.querySelector(
      '[role="dialog"][data-state="open"], [role="menu"][data-state="open"],'
      + ' [data-radix-popper-content-wrapper]',
    ) != null;

  const handle = App.addListener('backButton', ({ canGoBack }) => {
    if (hasOverlay()) {
      // همان کلیدی که خودِ Radix برایِ بستن می‌شناسد
      document.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
      );
      return;
    }
    if (canGoBack || window.history.length > 1) {
      window.history.back();
      return;
    }
    const now = Date.now();
    if (now - lastPress < 2000) {
      void App.exitApp();
      return;
    }
    lastPress = now;
    hint();
  });

  return () => {
    void handle.then((h) => h.remove()).catch(() => {});
    toast?.remove();
  };
}
