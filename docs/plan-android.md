# PLAN-android — نسخۀ اندروید BorsTerminal

> این فایل درِ ۲۰۲۶-۰۹-۲۹ (برنچ `feat/android`) مسیرِ «Termux» را فرض کرده بود:
> اجرایِ همان بک‌اند FastAPI رویِ گوشی. آن فرض **باطل است** و بازخوانده شد:
> نه اسکریپت‌هایِ `android/` نوشته شد (پوشه وجود ندارد و `.gitignore` خطِ
> `/android/` را دارد)، نه اجرایِ CPython/uvicorn رویِ اندروید درِ این پروژه
> آزموده شد. مسیرِ واقعی ازِ دورِ `arena/fts-mobile-uiux-20261007` چیزِ دیگری است.

## معماریِ فعلی (همان چیزی که درِ مخزن هست)

- پوسته: **Capacitor 8** ⇒ `frontend/android/` + `frontend/capacitor.config.ts`،
  `applicationId = com.borsterminal.mobile`، minSdk ۲۴ / target ۳۶.
- رویِ گوشی **هیچ بک‌اندی اجرا نمی‌شود**. همان SPA با `VITE_LOCAL_DATA=1` بیلد
  می‌شود و درِ WebView ازِ یکِ **بستۀ دادۀ آفلاین** (`mobile_snapshot.db.gz`
  داخلِ APK + کشِ دستگاه) می‌خواند؛ تابلو/چارتِ زنده مستقیم از
  `cdn.tsetmc.com` و به‌روزرسانیِ بستۀ داده ازِ GitHub Releases.
- بیلد و انتشار: `.github/workflows/mobile.yml` (Gradle درِ CI؛ رویِ ماشینِ
  توسعه Java/Android SDK نصب نیست).
- نسخۀ برنامه ازِ `frontend/package.json` می‌آید و `versionCode` ازِ آن مشتق
  می‌شود (major·۱e6 + minor·۱e3 + patch). خطِ اندروید ازِ این دور **سریِ ۱٫۱.x**
  را دارد تا عددش با شمارندۀ دسکتاپ (۱٫۰.x) و با برچسبِ `vX.Y.Z` قاطی نشود.

## قفل‌هایِ انتشار (هر چهار تا نشکند، ریلیز نمی‌شود)

1. **امضایِ APK**: `assembleRelease` با keystoreِ پروژه ازِ دو secret
   (`ANDROID_RELEASE_KEYSTORE_B64` / `ANDROID_RELEASE_KEYSTORE_PROPS`). بی‌کلید،
   APK بی‌امضا می‌ماند و انتشار بسته است؛ `app-debug.apk` هرگز به‌عنوان نسخۀ
   رسمی منتشر نمی‌شود و `debug.keystore` درِ خودِ Gradle هم رد می‌شود.
   گارد: `dev/android_release_v1110.py`.
2. **ریشۀ اعتمادِ داده**: کلیدِ عمومیِ manifest باید درِ باندل نشسته باشد
   (`vars.MOBILE_MANIFEST_PUBKEY`) و امضایِ بستۀ هدف معتبر باشد.
3. **سریِ داده**: بیلدِ تازه هرگز رویِ `mobile-latest`/`data-latest` منتشرشده
   می‌نویسد؛ سریِ جدید `mobile-latest-v2` است و هنوز ساخته/منتشر نشده.
4. **دستۀ گیت‌ها**: `tsc` صفر خطا + `vitest` سبز + باندلِ نسخۀ رسمی + manifest
   ادغام‌شده با `aapt2` + `apksigner verify`.

## وضعیتِ کنونی و کارهایِ باقی‌مانده

| مورد | وضعیت |
| --- | --- |
| کدِ رابط/دیتایِ آفلاین، قیف، بنیادی، چارت، تابلو | درِ شاخه هست و درِ CI سبز می‌سازد |
| سخت‌سازیِ manifest (allowBackup، صفحه‌کلید، cleartext، non-debuggable) | انجام شد (دورِ ۲۰۲۶-۱۰-۱۵) |
| آزمونِ WebView رویِ دستگاه | jobِ شبیه‌ساز اضافه شد؛ نتیجه درِ گزارشِ ریلیز ثبت می‌شود |
| کلیدِ امضایِ Android | **مالک** — keystore رسمی ساخته/درِ CI گذاشته نشده |
| کلیدِ امضایِ بستۀ داده | **مالک** — `~/.bors_mobile_keys` نیست و repo variable تنظیم نشده |
| هم‌راستایی با دسکتاپ | شاخۀ اندروید ۳۱۰ کامیت پشتِ `github/main` است؛ ادغامِ کورکورانه انجام نشد (تصمیمِ مالک، با عدد درِ گزارشِ ریلیز) |

**مرجعِ وضعیتِ هر دور**: `docs/android/ANDROID-RELEASE-REPORT-2026-10-15.md` و
`docs/MOBILE-DATA-PACKAGE-V2-2026-10-13.md`.
