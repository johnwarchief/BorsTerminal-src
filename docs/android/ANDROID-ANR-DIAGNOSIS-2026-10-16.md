# تشخیصِ ANR درِ `webview-on-emulator` — رأیِ داده‌شده با بلوکِ خودِ logcat

**تاریخ:** ۲۰۲۶-۱۰-۱۶ · **شاخه:** `mission/android-parity-2026-10-16`
**شاهدِ مرجع (تغییرنکردۀ دانلودشده از GitHub Actions):** run `38819805470`، job
`webview-on-emulator`، artifact `android-webview-evidence-897efdd1…` (۱٬۷۴۸٬۶۴۷ بایت،
۹ فایل: `logcat.txt`، `steps.tsv`، `summary.json`، `a11y-360x800-evidence.txt`،
`ui-360x800.xml`، `360x800.png`، `install.log`، `monkey_1.log`، `webview-360x800.log`)
· کپیِ محلیِ خوانده‌شده: `_audit/tmp/emu_ev_old/` · دستگاه: `Android SDK built for x86_64`،
Android 14 (api34) · **APKِ آزمایشِ آن ران `app-debug.apk` بوده، نه همان `android-1.1.0` منتشرشده.**

---

## ۱) رأیِ کوتاه

ANR **از منطقِ برنامه نیست**. علتِ ثبت‌شده خودِ اندروید این است:

```
10-15 23:18:53.874 E/ActivityManager: ANR in com.borsterminal.mobile (…/.MainActivity)
10-15 23:18:53.874 E/ActivityManager: PID: 4110
10-15 23:18:53.874 E/ActivityManager: Reason: Input dispatching timed out
                                     (Application does not have a focused window)
```

«Application does **not have a focused window**» یعنی درِ لحظۀ لمس، این اپ **هیچ
پنجرۀ دارایِ فوکوسی نداشته** که رویداد به آن برسد. این با «UI thread قفل کرده»
فرقِ ماهوی دارد: درِ آن حالت اندروید می‌گوید `Window … is not responding` یا
`executing service`/`Broadcast of Intent`. هیچ‌کدام از این سه درِ بلوکِ ما نیست.

سه شاهدِ مستقل، همان تفسیر را می‌دهند:

| شاهد | مقدار | چه معنی دارد |
| --- | --- | --- |
| `Displayed …MainActivity` | **+59s978ms** | اولین فریمِ فعالیت پس ازِ ۶۰ ثانیه نشسته — پنجره دیر ساخته شده، نه این‌که پیامی خورده و پاسخ نداده |
| `InputDispatcher` ×۶ | `Waiting because no window has focus but ActivityRecord{…borsterminal…} may eventually add a window` | سیستمِ ورودی *منتظر* پنجرۀ ما بوده؛ یعنی اپ زنده بوده و پنجره نداشت |
| `a11y-360x800-evidence.txt` | `mCurrentFocus=null` و درختِ `uiautomator` مالِ `com.android.launcher3` («Home settings / Wallpapers / Widgets») | FAILِ «هیچ واژۀ دیدنیِ برنامه نبود» رأیِ **کاوش** بود، نه رأیِ برنامه: در آن لحظه صفحه‌یِ لانچر رویِ صفحه بود |

و فشارِ منابع درِ همان بلوکِ ANR:

```
/proc/pressure/cpu   some avg10=91.84  avg60=89.66  avg300=83.05
CPU usage …          100% TOTAL: 33% user + 60% kernel + 4% irq + 2.3% softirq
                     system_server 45% · launcher3 21% · our app 18% · systemui 11%
```

یعنی ۹۲٪ از ده‌ثانیه‌یِ آخرِ نمونه، حداقلِ یکِ تسک **آماده ولی بی‌CPU** بوده؛ و سهمِ
خودِ اپ ۱۸٪ بوده در حالی که `system_server` ۴۵٪ مصرف می‌کرده. AVDِ دوهسته‌ای با
بافتِ نرم (`swiftshader`) درِ این حالت، زمان‌بندیِ پنجره را نمی‌رساند.

## ۲) پس سهمِ برنامه چقدر است؟ (مرزِ صادقانۀ این تشخیص)

یک سهمِ واقعیِ اپ وجود دارد که نباید پشتِ محیط قایم شود: bootِ اپ یک
`gunzip` ۱۶ مگابایت → ۷۰ مگابایت و بازکردنِ SQLite درِ **WASM رویِ همین رشتهٔ
UI** است (`localData.ts:656-671`: مسیرِ `CompressionStream` و بازگشتِ
`fflate.gunzipSync`؛ بازکردنِ بانک درِ `openDatabase`). رویِ این AVD هر دو
گران‌اند. اما:

- این کار **پس ازِ** اولین فریمِ صفحهٔ boot انجام می‌شود (پیش‌نویسِ صفحۀ
  «در حال بارگذاری دادۀ آفلاین» از ران‌هایِ `4b684cf5`/`8a8f6610` درِ خودِ APK هست)،
  پس علّتِ «پنجره‌ای که فوکوس می‌گیرد» را حذف نمی‌کند، بلکه *تأخیر* می‌دهد.
- `EGL_emulation: app_time_stats avg=39365ms` (یکِ فریم ۳۹ ثانیه) نشان می‌دهد
  گلوگاهِ اصلی **کامپوزیتِ گرافیکیِ شبیه‌ساز** است، نه جاوااسکریپت.
- `crash` سبز بود (`FATAL EXCEPTION=0`) و `back_button`/`background_foreground`
  PASS شدند؛ اپ درِ همان ران بالا آمده و زنده مانده است.

**نتیجه:** `PARTIAL` — محیطِ تست مقصّرِ اصلی است و یک کارِ سنگینِ اپ‌سمت هم رویِ
رشتهٔ UI وجود دارد که اندازه‌گیریِ جدا نشده. حلِّ اولی با تنظیمِ AVD و کاوش؛ حلِّ
دومی (offloadِ gunzip/SQLite ازِ UI) نیاز به سنجشِ قبل/بعد دارد و ادعایِ بدونِ
عدد نمی‌شود.

## ۳) چه چیزی درِ کاوشگر عوض شد (تا رأیِ بعدی تشخیص باشد، نه قرمزِ بی‌نام)

`tools/android_emu_verify.sh`:

| تغییر | چرا |
| --- | --- |
| `webview-<label>-a11y` اگر `FOCUS_OK=no` ⇒ `NOT_VERIFIED` با ذکرِ `mCurrentFocus` و سطرهایِ `no window has focus` | سنجه‌ای که پنجرۀ هدف را ندیده نمی‌تواند بگوید «متنِ برنامه نیست»؛ شش سطرِ InputDispatcher درِ همین ران گواهِ آن است |
| `step boot_displayed INFO` با عددِ `Displayed +NNsNNNms` | زمانِ اولین فریم باید درِ گزارش باشد، نه فقط درِ logcat |
| `step anr_reason INFO` و `step anr_pressure INFO`، با برشِ **بلوکِ خودِ ANR** (`grep -A40 "ANR in $PKG"`) | `-m1` رویِ کلِ فایل، بلوکِ ANRِ اولِ فایل را می‌داد که مالِ `com.android.providers.media` بود — عددِ اشتباه با ظاهرِ درست |
| `counts.info` درِ `summary.json` | بی‌این، جمعِ pass/fail/not_verified با شمارِ سطرهایِ steps نمی‌خواند و «سکوت» جایِ شاهد می‌نشست |

**سنجشِ سنسور، پیش ازِ ادعا:** هر چهار استخراجِ تازه رویِ `logcat.txt` واقعیِ همان ران
آزموده شد و مقدار داد — `+59s978ms`، `Reason: Input dispatching timed out (Application
does not have a focused window)`، `psi some avg10=91.84`، `100% TOTAL: 33% user + 60%
kernel`. نسخهٔ `-A28` برایِ `TOTAL` صفر می‌داد و با `-A40` درست شد؛ همان خطا درِ
نسخۀِ اولِ این بند بود که با دیدنِ خروجِ خالی اصلاح شد، نه با پذیرفتنِ «ندارد».

## ۴) آنچه هنوز اثبات نشده

- **رویِ دستگاهِ واقعی هیچ‌چیز سنجیده نشده.** رویِ این ماشین هیچ Android toolchain
  نیست؛ چکِرِ `mobile-use:setup-mobile-use` (اجراشده درِ این جلسه) هر هشتِ نیاز را
  `fail` داد: SDK root، adbِ SDK، emulator، `emulator_controller.proto`، aapt، AVD،
  JDK ۱۷+. تنها «دستگاه»ِ موجود، شبیه‌سازِ KVM درِ GitHub Actions است.
- آیا با AVDِ سالم‌تر (GPU ازِ software به guest، RAM/هستهٔ بیشتر، بی‌`wm size`) ANR
  از بین می‌رود — **NOT_PROVEN**؛ باید با رانِ تازه سنجیده شود.
- آیا سهمِ bootِ اپ (gunzip/SQLite رویِ UI) قابلِ اندازه‌گیریِ جدا رویِ دستگاه است —
  **NOT_PROVEN**؛ `mem_growth` درِ همان ران هم `NOT_VERIFIED` بود (`dumpsys meminfo`
  عدد نداد).
- DOMِ واقعیِ WebView (کاوشِ CDP) همچنان **NOT_VERIFIED** است: درِ آن ران socket
  (`webview_devtools_remote_2368`) شناسایی شد ولی CDP پاسخ نداد.
