# آرشیوِ کارِ #57 (کارت تکنیکال) — نسخه‌برداری از ورک‌اسپیس autoclaw

> **هشدار آرشیو — این diff را کورکورانه اعمال نکنید.** این پوشه کپی یک workspace موقت در تاریخ ۱۴۰۵-۰۷-۰۹ است؛ دستورهای copy/apply پایین صفحه برای همان snapshot نوشته شده‌اند و ممکن است کد جدید را بازنویسی یا تغییرات قدیمی را برگردانند. فقط پس از بررسی سه‌طرفهٔ diff با HEAD جاری، گاردها و تست‌ها از آن استفاده کنید. این پوشه مرجع اجرای کار جاری نیست.

**چرا این پوشه هست:** `C:\Users\PCMOD\.openclaw-autoclaw\workspace\projects\BorsTerminal_Work`
یک کلونِ کاریِ موقتی است که اتوماسیون‌هایِ زنده در آن کار می‌کنند. در سنجشِ
۱۴۰۵-۰۷-۰۹ ساعت ۱۹:۳۰، آنجا **۷ فایلِ تغییریافتۀ بی‌commit** و **۳ فایلِ untracked**
باقی مانده بود که هیچ‌جا جز رویِ آن دیسک وجود نداشت؛ اگر آن ورک‌اسپیس پاک یا
بازنشانی می‌شد، کارِ #57 (کارت تکنیکال و اتصالِ رأیِ هفتگی) می‌سوخت.
این آرشیو همان را به مخزنِ اصلی می‌آورد تا در گیت‌هاب باشد.

| قلم | چیست |
| --- | --- |
| `tracked-changes.diff` | دیفِ هفت فایلِ تغییریافته بی‌commit: `api/chart.py`، `frontend/src/contracts/technical.ts`، `features/master/lib/strictGates.ts`، `features/technical/api/useFtsAnalysis.ts`، `features/technical/signals/technicalSignals.ts`، `features/technical/routes/TechnicalPage.tsx`، `__tests__/master-arbitration.spec.tsx` (+۲۵۰/−۴۰) |
| `dev/fts_trend_staleness_v1064.py` | گاردِ «رأیِ روند روی پیوتِ کهنه نماند» — در آن درخت untracked بود و به‌همین‌دلیل در `run_all_tests` ثبتش نکردیم |
| `frontend/src/features/technical/lib/weeklyFromFts.ts` | منبعِ رأیِ هفتگی برای تبِ مستر (بندِ ۱ِ سند تحویل: `useFtsPlan` فقط fib/jet/exit را نگه می‌داشت و `trend.W` را دور می‌ریخت) |
| `frontend/src/__tests__/technical-weekly-wiring.spec.ts` | تستِ همان سیم‌کشی (۸ case؛ این تست پاسخِ `/api/fts` را دستی می‌سازد — بندِ ۶ سند تحویل هنوز باز است) |

## چطور اعمال شود

از ریشۀ مخزنِ اصلی، با سروری که هیچ‌کدام از این فایل‌ها بی‌commit نداشته باشند:

```bash
git apply --3way --check docs/wip/autoclaw-57/tracked-changes.diff   # اول بسنج
git apply --3way docs/wip/autoclaw-57/tracked-changes.diff
cp docs/wip/autoclaw-57/dev/fts_trend_staleness_v1064.py dev/
cp docs/wip/autoclaw-57/frontend/src/features/technical/lib/weeklyFromFts.ts \
   frontend/src/features/technical/lib/
cp docs/wip/autoclaw-57/frontend/src/__tests__/technical-weekly-wiring.spec.ts \
   frontend/src/__tests__/
```

بعد از اعمال: `npx tsc -b --force`، `npx vitest run`، و ثبتِ گارد در
`dev/run_all_tests.py` (این‌بار که فایل واقعاً در مخزن است). سپس این پوشه را حذف کن —
آرشیو وقتی مصرف شد، مرزِ «دو درخت» را زنده نگه می‌دارد.

**دوcommit از آن ورک‌اسپیس منتقل شده و اینجا لازم نیست:** `be0b37f` (ردیفِ نشستِ باز
از پنجرۀ روزانه و امضای کش + نشانِ `[exit]`) و `aedc64b` («بی‌داده» در شاخص ۳ ≠ «رد»،
۲۹۷ ردیف) — هر دو در ریلیز ۱٫۰٫۶۵ند (`2648c52`). چهار commit دیگرِ آنجا فقط
شاهد/سند است (`dfb3519`، `b364e88`، `da2d1bd`، `76d1480`) و دیفِ `_audit/` عمداً
گرفته نشد.
