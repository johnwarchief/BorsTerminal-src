#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گذر از قفلِ صفحه درِ کاوشگرهایِ زنده (Playwright).

قفلِ صفحه درِ نسخۀ ۱٫۱ اختیاری شد و دیگر هیچ اعتبارنامۀ ثابتی درِ سورس یا باندل
نیست (پیش‌ازِ این `admin`/رمزِ پیش‌فرض درِ `authStore.ts` بود و درِ APK می‌نشست).
پس کاوشگرها کد را ازِ محیط می‌گیرند: `BORS_SCREEN_CODE`. اگر پروفیل قفل نداشته
باشد — که حالتِ عادیِ CI و آزمون است — این تابع هیچ کاری نمی‌کند و `False`
می‌دهد؛ اگر قفل باشد و کد داده نشده باشد، صریح خطا می‌دهد تا کاوشگر بی‌صدا
«سفید» را «سبز» نخواند.
"""
import os
import re


def unlock(pg, wait_ms=800):
    """True یعنی قفل بود و باز شد؛ False یعنی قفل نبود (نیاز به اقدام نبود)."""
    try:
        present = bool(pg.evaluate("() => !!document.querySelector('input[type=password]')"))
    except Exception:
        return False
    if not present:
        return False
    code = os.environ.get("BORS_SCREEN_CODE") or ""
    if not code:
        raise RuntimeError(
            "قفلِ صفحه فعال است و BORS_SCREEN_CODE تنظیم نشده — کاوشگر حق حدس‌زدن ندارد")
    pg.locator("input[type=password]").first.fill(code)
    try:
        pg.get_by_role("button", name=re.compile("بازکردن|ورود")).first.click(timeout=5000)
    except Exception:
        # نسخۀ قدیمیِ رابط یا دکمۀ نام‌برچسب‌دار
        pg.locator("button[type=submit]").first.click(timeout=5000)
    pg.wait_for_timeout(wait_ms)
    if pg.evaluate("() => !!document.querySelector('input[type=password]')"):
        raise RuntimeError("کدِ BORS_SCREEN_CODE قفل را باز نکرد")
    return True
