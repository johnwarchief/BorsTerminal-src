# گزارشِ نهاییِ اندروید — تکمیل، اعتبارسنجی و انتشار (۱۴۰۴-۰۷-۲۳ / 2026-10-15)

> مأموریت: تکمیلِ کارهایِ فعلیِ اپلیکیشنِ اندروید، اعتبارسنجیِ واقعیِ آن، و انتشارِ یکِ
> نسخۀ **قابل‌نصب، امن و قابل‌ارتقا**. این سند درِ هرِ مرحلۀ کار باز می‌شود؛ بند‌هایِ
> خالی یعنی آن مرحله هنوز اجرا نشده، نه اینکه موفق بوده است.

## بندِ صفر — ماتریسِ موجودیِ اندروید (همان چیزی که پیش ازِ هرِ تغییر باید خوانده شود)

### کجا واقعاً کدِ اندروید است

| پرسش | پاسخِ اثبات‌شده | شاهد |
| --- | --- | --- |
| مخزنِ کد | `johnwarchief/BorsTerminal-src` (remote `github`) | `git remote -v` درِ هرِ سه worktree |
| مخزنِ مقصدِ ریلیز اندروید | **همان** مخزنِ کد (`-src`)، نه مخزنِ توزیعِ دسکتاپ | `mobile.yml` با `gh release create` درِ `GITHUB_REPOSITORY`؛ `release.yml` دسکتاپ هم درِ `-src` می‌دود و دارایی‌هایِ ویندوزی را درِ همانجا می‌گذارد |
| شاخۀ اندروید | `arena/fts-mobile-uiux-20261007` | تنها شاخه‌ای که `frontend/android/` را دارد |
| worktree | `C:/Users/PCMOD/Desktop/BorsTerminal-android` @ `8af64a1` | `git worktree list` |
| منتشرشده یا نه | HEAD == `github/arena/fts-mobile-uiux-20261007` (`8af64a1a51ef…`) | `git ls-remote` |
| شاخۀ `feat/android` | `d55ff41` — ۲۹۴ کامیت **پشت‌سر** شاخۀ فعال، بدونِ هیچ کامیتِ اختصاصی | `git rev-list --left-right --count github/feat/android...HEAD` → `0 294` |
| `C:/Users/PCMOD/Desktop/BorsTerminal-Mobile` | clone جدا رویِ `arena/01a0f32b-borsterminal-src` @ `a83d62e`؛ همان جایی که APK `mobile-latest` (نسخۀ ۱٫۰٫۶۵) از آن ساخته شد | `git -C … rev-parse --abbrev-ref HEAD` |
| پوسته | **Capacitor 8.5.2** (`frontend/android/`, `frontend/capacitor.config.ts`)، باندلِ آفلاین با `VITE_LOCAL_DATA=1`؛ هیچ بک‌اندی رویِ گوشی اجرا نمی‌شود | `frontend/package.json:16-19`، `capacitor.config.ts:12-18` |
| `docs/plan-android.md` | **باطل است**: مسیرِ Termux + اسکریپت‌هایِ `android/` و بایندِ `127.0.0.1` را توصیف می‌کند؛ آن پوشه وجود ندارد و `.gitignore:26` خطِ `/android/` دارد | `ls android` → no such file |

### شناسۀ برنامه و نسخه

| مورد | مقدارِ واقعی | منبع |
| --- | --- | --- |
| `applicationId` / `namespace` | `com.borsterminal.mobile` | `android/app/build.gradle`، `capacitor.config.ts:13` |
| `minSdk` / `target` / `compile` | ۲۴ / ۳۶ / ۳۶، Java ۲۱ | `android/variables.gradle:2-4`, `app/capacitor.build.gradle:5` |
| `versionName` درِ کدِ امروز | `1.0.79` (مشتق ازِ `frontend/package.json`) | `frontend/package.json:4` + بلوکِ BORS-VERSION درِ `build.gradle:15-55` |
| `versionCode` درِ کدِ امروز | ۱٬۰۰۰٬۰۷۹ = major·۱e6 + minor·۱e3 + patch | همان |
| `versionName` درِ **آخرین APKهایِ منتشرشده** | `1.0` و `versionCode` قالب (قبل ازِ اصلاحِ منبعِ یکتا) | دو APKِ دانلودشده، پایشِ AndroidManifest دودویی |
| آخرین ریلیزِ منتشرشده با APK | `mobile-latest` (v1.0.65، ۲۰۲۶-۰۹-۳۰) + چهارِ ریلیزِ `mobile-parity-*` پیش‌انتشار | `gh release view` |
| سریِ دادۀ امضاشده `mobile-latest-v2` | **وجود ندارد** (`release not found`) — هرگز منتشر نشد | `gh release view mobile-latest-v2` |

### وضعیتِ امضا (مرحلۀ پنجم، پیش ازِ هرِ تصمیم)

| پرسش | پاسخ | شاهد |
| --- | --- | --- |
| کلیدِ امضایِ release اندروید درِ سازوکارِ رسمیِ پروژه؟ | **نه**. secrets مخزن فقط `BORS_SETUP_PASSWORD`، `RELEASE_TOKEN`، `TAURI_SIGNING_PRIVATE_KEY` (هیچ‌کدام کلیدِ Android نیست) | `gh api …/actions/secrets` — فقط نام‌ها خوانده شد |
| keystore رویِ این ماشین؟ | هیچ `*.jks` / `*.keystore` پیدا نشد؛ `~/.android/` فقط کلیدِ adb دارد | جست‌وجویِ فایل |
| CI چه چیزی می‌سازد؟ | `./gradlew assembleDebug` و همان `app-debug.apk` را منتشر می‌کند | `.github/workflows/mobile.yml:211-212` |
| گواهیِ دو APKِ منتشرشده یکی است؟ | **نه**. هر دو `CN=Android Debug، O=Android، serial=0x1` ولی اثرانگشتِ SHA-256 و `notBefore` متفاوت | پایشِ APK Signing Block (v2) درِ `_audit/tmp/apkcert/` |
| پس مسیرِ ارتقا رویِ گوشی چطور کار می‌کند؟ | **هیچ‌وقت کار نکرده است.** هر APKِ تازه از APKِ قبلی گواهیِ دیگری دارد ⇒ `INSTALL_FAILED_UPDATE_INCOMPATIBLE` ⇒ کاربر باید حذفِ کامل کند. چیزی برایِ «حفظِ قابلیتِ Upgrade» وجود ندارد؛ ولی کلیدِ رسمیِ تازه هم همینِ یک‌بارِ حذف را لازم می‌کند | اثرانگشت‌هایِ بالا |
| نسخۀ موجودِ buildشده بعد ازِ اصلاحِ نسخه | artifact رانِ ۳۸۳۲۰۵۹۳۴۴۴: `versionName 1.0.79` ✅، ولی هنوز `debuggable` و `allowBackup=true` و امضایِ debug | دانلودِ artifact و پایشِ manifest |

### گره‌هایِ بازِ که به مالک برمی‌گردند (ثبتِ Stage 0)

1. **کلیدِ امضایِ Android**: ساخت/تحویلِ keystore رسمی و گذاشتنش درِ CI. بدونِ آن، «نسخۀ رسمی»
   یا امضانشده می‌ماند یا با debug امضا می‌شود — و هر دو ممنوع‌اند.
2. **کلیدِ امضایِ بستۀ داده** (`~/.bors_mobile_keys` + `vars.MOBILE_MANIFEST_PUBKEY`): امروز
   هیچِ متغیری درِ repo تنظیم نشده (`actions/variables` خالی است)، پس گیتِ انتشارِ `mobile.yml`
   خودبه‌خود می‌بندد و گوشی هیچِ دادۀ تازه‌ای از هیچِ سریِ امضاشده نمی‌گیرد.
3. **دستگاه/شبیه‌ساز محلی**: رویِ این ماشین Java، Gradle و Android SDK نصب نیست؛ فقط `adb` هست
   و هیچِ دستگاهی وصل نیست (`adb devices` خالی). ⇒ ساخت و آزمون درِ CI انجام می‌شود.

## بندِ یک — دامنه و تکمیلِ قابلیت‌ها + WebView

قابلیت‌هایی که درِ این شاخه **ازِ قبل** پیاده شده بودند و از نو ساخته نشدند
(هر کدام با گارد/تستِ خودش): تابلو با overlay زنده، بنیادی/اسکرینر روی کلِ
universe، قیف FTS با چهار تراشه، درخت استراتژی، چارت با `price_history` رویِ
دستگاه، اینسپکتورِ کشویی، نوارِ پایینِ پنج‌تایی، صفحۀ «دریافت دادهٔ آفلاین»،
منبعِ یکتایِ نسخه، و بستۀ دادۀ امضاپذیر (قراردادِ v2، درِ انتظارِ کلید).

### آنچه درِ این دور تکمیل شد

| ایرادِ واقعی | ریشۀ کد | اصلاح | شاهد |
| --- | --- | --- | --- |
| هشت قاعدۀ `env(safe-area-inset-*)` رویِ گوشی همیشه صفر بود | `index.html` viewport بی `viewport-fit=cover` | اضافه شد؛ `padding-bottom` بدنه و بنرِ هشدار با همان env هم‌افزوده شد (بی‌این، با cover ردیفِ آخر زیرِ ناوتی‌بار می‌ماند) | تستِ `mobile-release-hardening.spec.ts` + باندلِ built شده |
| پنلِ عیب‌یابی مقدارهایِ بیرونی را بی‌گریز درِ `innerHTML` می‌ذاشت | `diagnostics.ts` `row()` | `esc()` رویِ برچسب و مقدار؛ `package_id`/`built_at` از manifestِ ریموت و `detail` از رشتهٔ خطا می‌آیند | ادعایِ رفتاری درِ تست (یک manifestِ دست‌خورده اسکریپت نمی‌شود) |
| نسخۀ «رسمی» debuggable بود ⇒ DevTools رویِ گوشیِ کاربر + هر `console.error` بیرون می‌آمد | `mobile.yml` فقط `assembleDebug` می‌ساخت | `assembleRelease` با `debuggable false`؛ بیلدِ debug تنها برایِ آزمونِ WebView نگه داشته شد | `aapt2 dump badging` درِ CI؛ گاردِ A11 |
| صفحه‌کلید رویِ فرم/جداول می‌افتاد | manifest بی `windowSoftInputMode` | `adjustResize` (توصیۀ رسمیِ Capacitor) | گاردِ A14 |
| پشتیبانِ ابری/`adb backup` دادهٔ برنامه را بیرون می‌برد | قالبِ `allowBackup="true"` | `false` + دلیلِ ثبت‌شده درِ manifest | گاردِ A13 |
| شیءِ خطایِ کامل (stack + URLِ پاسخ ریلیز) درِ console چاپ می‌شد | `MobileBootstrap.tsx:68` | یکِ سطرِ ثابت؛ متنِ خطا همان‌جا درِ صفحه و پنل هست | گاردِ A29 (متنِ console) |
| `docs/plan-android.md` مسیرِ Termux و بایند `127.0.0.1` را دستور می‌داد؛ `resolvers.ts` به سندِ غیرموجود ارجاع می‌داد | هر دو | سندِ باطل بازنویسی شد؛ ارجاع به دو سندِ واقعی بدل شد | کامیتِ `chore(android)` |

### چک‌لیستِ WebView — حالتِ هرِ بند

| سنجه | وضعیت | کجا سنجیده می‌شود |
| --- | --- | --- |
| صفحۀ واقعی بی‌سفیدی/لودینگِ دائمی باز شود | درِ کار | `tools/android_emu_verify.sh` (دستگاه) + کاوشگرِ Chromium (سایز) |
| routeها و navigation کار کنند | درِ کار | همان (CDP: `location.hash` + تعدادِ ردیف) |
| درخواست‌هایِ داده به آدرسِ درست بروند | بخشی اثبات شد | بندِ دو (endpointهایِ واقعی با status ثبت‌شده) |
| خطای TLS/DNS/timeout/offline قابلِ تشخیص | کد درِ مسیر است؛ آزمونِ زنده درِ کار | `localData.noteFailure` + بنرِ `.bors-fatal-banner` |
| JS/file access/mixed content محدود | بله | `allowMixedContent: false` (capacitor.config.ts) + cleartext بسته؛ JS برایِ SPA لازم است |
| لینکِ خارجی رفتارِ مشخص دارد | **NOT_VERIFIED رویِ دستگاه** — هیچ لینکِ خارجی درِ رابطِ موبایل پیدا نشد؛ مسیرِ آپدیتِ دسکتاپ درِ موبایل پنهان است (`mobile.css:293`) | جست‌وجوی `https://` درِ `src/` |
| دکمهٔ بازگشت خروجِ ناخواسته/صفحۀ سفید نسازد | کد هست (`androidShell.ts` سه‌پله، ۵ تستِ jsdom)؛ آزمونِ واقعی با `keyevent 4` درِ کار | گاردِ A34 |
| background/foreground | درِ کار (adb) | گاردِ A34 |
| نشتِ حافظه/چند WebView | **NOT_VERIFIED** — بیِ دستگاهِ واقعی قابلِ سنجش نیست؛ `launchMode=singleTask` و یکِ MainActivity تک‌نفره است | بندِ هفت |
| هیچ Token درِ console/logcat چاپ نشود | کد بسته‌سازی شد + دو سنجه (CDP و logcat grep) | A29/A37 |

## بندِ دو — محیطِ داده و بک‌اندِ واقعیِ گوشی

**هیچ بک‌اندی رویِ گوشی اجرا نمی‌شود.** `localhost`/`127.0.0.1` درِ این معماری
نقشی ندارد؛ `vite.config.ts:26` آن را فقط درِ دورِ توسعه پروکسی می‌کند و
`resolvers.ts:200` یکِ URLِ ساختگیِ محلی است که هرگز درخواست نمی‌شود. منبع‌های
واقعیِ گوشی دوتایند:

| اندپوینت | قابلیت | وضعیتِ سنجیده‌شده (۲۰۲۶-۱۰-۱۵، ازِ این ماشین) |
| --- | --- | --- |
| `…/releases/download/mobile-latest/mobile_snapshot.db.gz` | بستۀ دادۀ آفلاین | `200`، `16179264` بایت |
| `…/mobile_snapshot.db.meta.json` | مانیفستِ بسته | `200`، `111` بایت؛ فقط چهار کلیدِ قدیمی (`app_version 1.0.79`, `built_at 2026-10-08T16:16:15`, `baked_ok 4627`, `gz_bytes`) |
| `…/mobile_snapshot.db.meta.json.sig` | امضایِ manifest | **`404`** ⇒ سریِ منتشرشده بی‌امضاست |
| `mobile-latest-v2` (سریِ امضاشده) | — | **ریلیزی وجود ندارد** ⇒ هنوز منتشر نشده |
| `cdn.tsetmc.com/api/StockGet/GetMarketWatch` | تابلویِ زنده | `URLError: timed out` ازِ این ماشین (بیِ رفررِ جعلیِ کلاینت) |
| `cdn.tsetmc.com/api/TradeHistory/…` | تاریخچۀ چارتِ زنده | `URLError: timed out` ازِ این ماشین |
| `…/UpdateManagerModal` فایلِ exe | آپدیتِ دسکتاپ | درِ موبایل با `mobile.css:293` پنهان است؛ مصرفِ دیگری ندارد |

شاهدش درِ `_audit/android_release/stage2_endpoints.json` است. **راستی‌آزماییِ
TSETMC ازِ این ماشین ممکن نیست** (خروجِ زمان)؛ سنجشِ زندهٔ آن باید درِ شبکهٔ
runnerِ CI (jobِ شبیه‌ساز، که `Network.enable` درخواست‌ها و status را ثبت
می‌کند) انجام شود و جدا گزارش شود. هیچ موفقیتی با mock به‌جای اتصالِ واقعی
ثبت نمی‌شود.

پیامدِ امنیتیِ مستقیمِ این جدول: چون کلیدِ عمومی درِ هیچ بیلدی نبوده
(`vars.MOBILE_MANIFEST_PUBKEY` تنظیم نشده) و `.sig` هم منتشر نشده، کلاینتِ
فعال‌شدۀ جدید درِ حالتِ fail-closed هیچ بستۀ بیرونی را نمی‌پذیرد و گوشی فقط
رویِ دادۀ همراهِ APK می‌ماند. این باگِ رابط نیست؛ نبودِ ریشۀ اعتماد است و
مراسمش مالک (بندِ پنج).

## بندِ سه — طراحی برایِ انتشار رویِ اندازه‌هایِ مختلف

دو نیمه دارد و **عمداً جدا** گزارش می‌شود: (الف) کاوشگرِ Chromium رویِ همین
ماشین — باندلِ واقعیِ موبایل با پرچمِ `VITE_LOCAL_DATA=1` و بستۀ دادۀ واقعی،
(ب) WebViewِ اندروید رویِ شبیه‌ساز درِ CI. عددهایِ (الف) چیدمان را ثابت می‌کند
نه رفتارِ دستگاه را: `env(safe-area-inset-*)` درِ Chromium همیشه صفر است
(ناچِ تقلیدی نیست)، صفحه‌کلید تقلید نمی‌شود و پلِ بومی صدا زده نمی‌شود.

### الف) سه اندازه × نُه route — `tools/android_viewport_probe.mts`

| اندازۀ CSS (dpr) | بستۀ داده | زمانِ راه‌اندازی | نوارِ پایین | سرریزِ افقی | ردیف‌ها | خطایِ console واقعی |
| --- | --- | --- | --- | --- | --- | --- |
| 360x800 (x3) | gz 16,179,264 -> 70,619,136 بایت | 407ms (دریافت 225 / بازگشایی 168 / بازکردن 15) | {y:742 h:58 bottom:800} | 0px | تابلو 26 / بنیادی 23 / engine-lab 38 / دیده‌بان 7 | 0 |
| 390x844 (x3) | همان | 391ms (212 / 165 / 15) | {y:786 h:58 bottom:844} | 0px | 27 / 23 / 38 / 7 | 0 |
| 412x915 (x3) | همان | 379ms (205 / 160 / 14) | {y:857 h:58 bottom:915} | 0px | 29 / 25 / 38 / 7 | 0 |

27 رکورد، صفر سنجۀِ رد. `technical` / `strategy-tree` / `master` ردیفِ جدولی
ندارند (چارت، گراف، راهنمایِ مرحله) و صفرشان ایراد حساب نمی‌شود؛ `nope-404`
عمداً آدرسِ ثبت‌نشده است و باید «پیدا نشد» بدهد، نه جدول. 27 خطِ `ERR_FAILED`
درِ console ساختۀِ خودِ کاوشگر است (آفلاینِ مصنوعیِ عمدی) و درِ حکم شمارش
نمی‌شود. شواهد: `_audit/android_release/viewport_probe.json` + 27 اسکرین‌شات
درِ `_audit/android_release/viewports/`.

### ایرادِ واقعیِ همین بند: نوارِ پایین درِ گوشی «ریلِ عمودی» می‌ماند

پیش ازِ اصلاح (اندازۀ زنده درِ 360x800): نوار 58px بود ولی سه گروهِ `nav` هر
کدام **135px** قد و خوشۀِ تم/به‌روزرسانی/تنظیمات **92px** — یعنی ردیفِ
پایینیِ هر گروه بیرون می‌زد و رویِ محتوا می‌افتاد (دکمۀ ⚙ دقیقاً رویِ پنلِ
«صفر فروش» درِ `360x800-index.png`ِ پیشین). هدفِ لمسیِ عرضی هم اندازهٔ خودِ
آیکون بود: **21px**.

پس ازِ اصلاح (همان کاوشگر، همان باندل، دو رکوردِ قبل/بعد درِ
`_audit/android_release_before/` و `_audit/android_release/`):

| سنجه | پیش ازِ اصلاح | پس ازِ اصلاح |
| --- | --- | --- |
| رکورد‌هایِ بی‌سنگِ رد (27 = 3 اندازه × 9 route) | 27 از 27 | 0 از 27 |
| هدفِ لمسیِ زیرِ 44px درِ **قد** (هر رکورد) | 3 | 0 |
| عرضِ هر تب درِ 360×800 | 21px | 32px (37px درِ 390 و 412) |
| جعبۀِ نوار درِ 360×800 | {y:742 h:58 bottom:800} | همان (نوار خودش درست بود، درونش نه) |
| اسکرولِ افقیِ نوار | بی‌اسکرول | بی‌اسکرول (`scrollWidth == clientWidth`) |

باقی‌مانده که **رأیِ مالک** است نه تصمیمِ من: درِ 360px، شش تب + سه دکمۀِ
خوشۀِ پایین (160px) هم‌زمان 44pxِ *عرضی* نمی‌گیرند. دو راهِ واقعی هست —
نوارِ لغزان (تب‌ها 44px می‌شوند ولی بعضی‌ها بیرونِ دید) یا برداشتنِ آن سه
دکمه به نوارِ بالا — و هیچ‌کدام یک‌طرفه انتخاب نشد که مبادا تبی درِ ساعتِ
بازار از دسترس بیفتد. کاوشگر عدد را ثبت می‌کند (`navItemsUnder44Wide: 6`)
بدونِ اینکه به‌خاطرش قرمز شود.

### ب) WebView رویِ دستگاه

_(پس ازِ رانِ شبیه‌ساز پر می‌شود — نصب، سه اندازۀ واقعی، بازگشت،
background/foreground، crash/ANR و logcat. بی‌KVM صریحاً `NOT_VERIFIED`.)_

## بندِ شش — ساختِ Release و اعتبارسنجیِ artifact

فرایندِ واقعیِ ساخت ازِ خودِ پروژه خوانده شد: Gradle Wrapper درِ `frontend/android`
(AGP 8.13.0 / Gradle 8.14.3 / Java 21) و بیلد درِ GitHub Actions، چون رویِ این
ماشین Java/Android SDK نصب نیست. `bundleRelease` (AAB) عمداً ساخته نشد: مقصدِ
توزیعِ این پروژه GitHub Release است و فایلِ قابلِ نصبِ مستقیم؛ AAB رویِ گوشی
نصب نمی‌شود و هیچ مصرف‌کنندۀ دیگری برایش وجود ندارد.

شاهدِ رانِ 38663075135 (شاخۀ `arena/fts-mobile-uiux-20261007` @ `af8a724`،
`workflow_dispatch` با `publish=false`):

| سنجه | خروجِ واقعیِ CI |
| --- | --- |
| نسخۀ بیلدشده | `manifest: versionName=1.1.0 versionCode=1001000` از `merged_manifests/release/processReleaseManifest/AndroidManifest.xml` |
| badgingِ خودِ APK | `package: name='com.borsterminal.mobile' versionCode='1001000' versionName='1.1.0'` · `targetSdkVersion:'36'` · `minSdkVersion` 24 |
| مجوزها درِ APK | تنها `android.permission.INTERNET` + `com.borsterminal.mobile.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` (مجوزِ signature-level خودِ AndroidX، نه مجوزِ کاربر) |
| `debuggable` | **نیست** (`aapt2 dump badging` آن را چاپ نمی‌کند؛ گام صریحاً presence را چک و رد می‌کند) |
| برچسبِ برنامه | `application-label:'بورس‌ترمینال'` |
| نامِ artifact | `app-release-unsigned.apk` — یعنی Gradle درست گفت: کلیدِ انتشار تنظیم نشده |
| اندازه / SHA-256 | 21,191,169 بایت · `42e55258f33a440051d1adc7c75ee551d39d3fd816017f1d5af8a70003a97521` |
| `apksigner verify` | «APK بی‌امضاست» · `release APK signing: no · certificate sha256: namoloom` |
| دروازۀ انتشار | `PUBLISH = رد شد؛ اینِ ران فقط artifact می‌سازد` |
| بستۀ دادۀ داخلِ APK | سریِ `mobile-latest` · 16,179,264 بایت · `built_at 2026-10-08T16:16:15` (کهنه: هفت روز) |

مقایسه با نسخۀ منتشرشدۀ پیشین: debug امضا 25,327,555 بایت و `debuggable` —
یعنی نسخۀ ریلیز هم کوچک‌تر است هم غیرقابلِ اتصالِ DevTools.

**ساختِ موفق Gradle به‌تنهایی آمادگی نیست** و اینجا دقیقاً همین معنی را داد:
artifact آماده است، اما بی‌امضا ⇒ نه قابلِ نصب رویِ گوشی، نه قابلِ انتشار.

## بندِ هفت — آزمونِ نصب و ارتقا

محیطِ آزمون: **شبیه‌سازِ Android درِ CI** (api 34، x86_64، profile pixel_5،
KVM تأیید شد). رویِ این ماشین هیچِ Android SDK/Java نصب نیست و هیچِ دستگاهی
وصل نیست (`adb devices` خالی)، پس شبیه‌ساز تنها دستگاهِ در دسترس است.

اولین ران (38663075135) هر 8 سنجه را قرمز داد و علتِ واقعی **ابزار** بود نه اپ:
`adb install apks/app-debug.apk` — `actions/upload-artifact` ساختارِ
`release/` و `debug/` را نگه می‌دارد، پس فایلِ دانلودی
`apks/debug/app-debug.apk` است. بی‌نصب، «اپ با یکِ بازگشت بست» و
«پس از home برنگشت» فقط طنینِ همان شکست بودند. دو «hit» نشتِ رمز هم
`E/BackupPasswordManager(541)` خودِ اندروید بود. هر سه درِ همان ران اصلاح شد
(یافتِ مسیر با `find`، fail-fast با NOT_VERIFIED، دامنه‌دارکردنِ شمارشِ نشت) و
گارد A42/A43/A44 همین را قفل می‌کند.

نتیجهٔ رانِ اصلاح‌شده (38665643345):

| سنجه | نتیجه |
| --- | --- |
| نصبِ APK | _(پس ازِ ران)_ |
| اجرایِ اولیه و صفحۀ اصلی | — |
| بارگذاریِ WebView و navigation | — |
| قطع و وصلِ شبکه | — |
| دکمۀ بازگشت | — |
| background / foreground | — |
| crash / ANR / logcat | — |
| نشتِ رمز درِ logcat و console | — |
| به‌روزرسانی از نسخۀ رسمیِ قبلی | **NOT_VERIFIED** — نسخۀ قبلی با کلیدِ debugِ دیگری امضا شده و کلیدِ رسمیِ این پروژه وجود ندارد؛ نصبِ رو‌رویی از نظرِ اندروید ناممکن است (بندِ پنج) |
| حفظِ داده پس ازِ ارتقا | **NOT_VERIFIED** — بی‌ارتقایِ ممکن، آزمونِ بی‌معنا است |

## بندِ هشت — تست‌ها و گیت‌ها (نام، فرمان، exit code، نتیجه)

| گیت | فرمان | exit | نتیجهٔ واقعی |
| --- | --- | --- | --- |
| تایپ‌چکِ فرانت | `npx tsc -b` | 0 | صفر خطا |
| کل سورۀ فرانت | `npx vitest run --maxWorkers=2` | 0 | 149 پرونده، 1555 passed / 1 skipped / 0 failed |
| گاردِ لنگرهایِ نسخه | `python dev/version_anchor_guard.py` | 0 | 6 checks, 0 failed — VERSION ANCHOR GUARD OK |
| گاردِ زنجیرۀ انتشارِ اندروید | `python dev/android_release_v1110.py` | 0 | 46 passed / 0 failed |
| گاردِ امضایِ manifest داده | `python dev/mobile_manifest_sign_v1079.py` | 0 | 51 passed / 0 failed |
| گاردِ هم‌کلیدیِ پخت/اجرا | `python dev/mobile_bake_key_parity_v1079.py` | 0 | 13 passed / 0 failed |
| گاردِ نویسهٔ فارسی | `python dev/persian_glyph_guard.py` | 0 | 4 passed / 0 failed |
| بیلدِ موبایل | `VITE_LOCAL_DATA=1 … npm run build` | 0 | باندلِ ساخته شد؛ `viewport-fit=cover` و `1.1.0` درِ خروجیِ بیلدشده راستی‌آزمایی شد |
| کاوشگرِ سه اندازه × نُه route | `node --experimental-strip-types tools/android_viewport_probe.mts` | 0 | 27 رکورد، 0 سنجۀِ رد |
| گیتِ CI (تایپ + تست) | `npx tsc -b && npx vitest run` درِ runner | 0 | سبز (پیش ازِ ساختِ APK) |
| بیلدِ release + debug درِ CI | `./gradlew assembleRelease assembleDebug` | 0 | سبز؛ artifact با aapt2/apksigner خوانده شد (بندِ شش) |
| کل گاردهایِ پایتون | `python dev/run_all_tests.py` | 1 | شش گارد قرمز: KLineCharts v10 API، technical setups three-state، Round J jet، candle integrity، R1/R2 housekeeping، tape filters (214/216). **راستی‌آزماییِ انتساب:** همین شش درِ کامیتِ پایه `8af64a1` (پیش ازِ هیچ تغییرِ من، درِ یکِ worktreeِ جدا ازِ همین commit) هم قرمزند؛ `tape_filters_v1034.py` آنجا هم 214/216 داد. دو قرمزِ آن اجرا (board history windows و hot state) به‌خاطرِ نبودِ `market.db` درِ آن worktree بود (فایلِ gitignored). متنِ دو ردِ tape filters هم دقیقاً معنایِ جت/سقف است = موتورِ تکنیکال، که دامنهٔ این مأموریت نیست. هیچ‌کدام ازِ 26 فایلِ تغییریم درِ مسیرِ آن گاردها نیست (تک فایلِ مشترک `bors_config.py` بود و آن گاردها نسخه نمی‌خوانند). |
| گاردِ جدید درِ همان suite | `android release chain` | 0 | 46/46 (اجراش درِ دلِ `run_all_tests.py`) |
| lintِ فرانت | `npm run lint` | 0 | صفر خطا، صفر warning |
| syntaxِ اسکریپتِ دستگاه | `bash -n tools/android_emu_verify.sh` | 0 | درست |
| آزمونِ WebView رویِ دستگاه | jobِ `webview-on-emulator` | — | _(پایینِ همین بند، پس ازِ رانِ نهایی)_ |

هیچ تستی حذف یا ضعیف نشد تا گزارش سبز شود؛ دو قرمزِ اولِ CI (کامنتِ `--` درِ
XML و نامِ `app-release-unsigned.apk`) با **رفعِ علت** بسته شدند و هر دو به
گارد اضافه شدند تا برنگردند.

## بندِ نه — مقصدِ رسمیِ انتشار و نسخه‌گذاری

ازِ رویِ workflowها و ریلیزهایِ قبلی خوانده شد، نه حدس:

| چیز | مقصد |
| --- | --- |
| کد + بیلد | `johnwarchief/BorsTerminal-src` (تگِ `vX.Y.Z` دسکتاپ اینجا می‌دود) |
| ریلیزِ دسکتاپ | همان مخزن با assetهایِ ویندوزی + `latest.json` (`release.yml` → `scripts/publish_github_release.py`) |
| ریلیزِ اندروید | همان مخزن، با برچسبِ **مجزا** (`mobile-parity-*` تا پیش‌ازِ این دور) |
| سریِ دادۀ گوشی | تگ‌هایِ `mobile-latest` / `data-latest` درِ همان مخزن — asset، نه git |

تصمیمِ این دور: برچسبِ نسخۀ رسمیِ اندروید `android-<versionName>` است
(`android-1.1.0`). دلیل: (۱) با هیچ برچسبِ دسکتاپی (`vX.Y.Z`) نمی‌خواند،
(۲) با نامِ سریِ داده (`mobile-latest`، `data-latest`) نمی‌خواند، پس هیچ
احتمالی برایِ بازنویسیِ `latest.json`، امضاهایِ ویندوزی یا بستۀ دادۀ
منتشرشده نیست، و (۳) عددِ نسخۀ اندروید درِ خودش قابلِ استناد است. گاردِ A26/A27
همین را الزامی می‌کند و A28 چک می‌کند `release.yml` دسکتاپ اصلاً کلمۀ
«android» نداشته باشد.

نسخه‌گذاری: `versionName` از `frontend/package.json` (منبعِ یکتا) و
`versionCode` مشتقِ یکنوا ازِ آن. خطِ اندروید ازِ این دور سریِ 1.1.x را دارد
(1.1.0 ⇒ versionCode 1001000) تا با شمارندۀ دسکتاپ (که به 1.0.88 رسیده و
1.0.89 را خودش برمی‌دارد) قاطی نشود و versionCode هرگز پایین نیاید.

## بندِ ده — انتشارِ واقعی

**منتشر نشد.** سه دلیلِ مستقل، هر سه بیرونی و هر سه با شاهد:

1. **کلیدِ امضایِ Android وجود ندارد** ⇒ artifact بی‌امضا است
   (`app-release-unsigned.apk`) و گامِ انتشار صراحتاً رد می‌کند. APKِ بی‌امضا
   رویِ هیچ گوشی نصب نمی‌شود و debug هم جایِ آن را نمی‌گیرد.
2. `vars.MOBILE_MANIFEST_PUBKEY` تنظیم نشده (فهرستِ variables مخزن **خالی** است)
   ⇒ بیلد بی‌ریشۀ اعتماد ساخته می‌شود و گیتِ publish همان‌جا می‌شکند.
3. بستۀ دادۀ هدف `.sig` ندارد (404) و سریِ `mobile-latest-v2` اصلاً ساخته
   نشده ⇒ «امضایِ بستۀ داده معتبر نشد؛ انتشارِ APKِ بی‌منبعِ اعتماد ممنوع».

برایِ همین هیچ tag و هیچ Release تازۀ اندرویدی ساخته نشد؛ تنها کاری که با
مخزنِ انتشار شد، **خواندن** بود (`gh release view`، `gh api …/artifacts`).
ریلیزهایِ دسکتاپ، `latest.json`، امضاها و `codal.db.lzma` دست‌نخورده‌اند
(هیچ گامِ این workflow به آن‌ها نزدیک نمی‌شود و A28 این را می‌سنجد).

### اقدامِ دقیقِ باقی‌ماندۀ مالک (سه کار، هر سه کوتاه)

1. **کلیدِ Android** (یک‌بار، بیرونِ این ماشین هم نگه‌داری شود):
   `keytool -genkeypair -keystore bors-android-release.jks -alias bors -keyalg RSA -keysize 2048 -validity 10000`
   سپس دو secret درِ مخزن: `ANDROID_RELEASE_KEYSTORE_B64` = خروجیِ
   `base64 -w0 bors-android-release.jks` و `ANDROID_RELEASE_KEYSTORE_PROPS` =
   سه سطرِ `storePassword=…` / `keyAlias=bors` / `keyPassword=…`.
   رمزها هیچ‌جا درِ فرمان یا log چاپ نمی‌شوند؛ Gradle فقط مسیرِ فایل را می‌بیند.
   **هشدارِ واقعی:** چون هیچ نسخۀ منتشرشده‌ای با این کلید امضا نشده، اولین
   ریلیزِ امضاشده رویِ گوشی‌هایی که نسخۀ debug دارند با
   `INSTALL_FAILED_UPDATE_INCOMPATIBLE` می‌خورد و باید یک‌بار حذف و دوباره نصب
   شود. از این پس همان کلید ثابت می‌ماند و ارتقا عادی می‌شود.
2. **کلیدِ manifestِ داده**: مراسمِ `~/.bors_mobile_keys` (اسکریپتِ
   `scripts/sign_mobile_manifest.py`)، گذاشتنِ کلیدِ عمومی درِ
   `vars.MOBILE_MANIFEST_PUBKEY`، و انتشارِ سریِ `mobile-latest-v2` با `.sig`.
3. **اجرایِ انتشار**: `gh workflow run mobile.yml -f publish=true -f prerelease=false -f snapshot_series=mobile-latest-v2`.
   دروازۀ سه‌قفلۀ داخلِ workflow خودش چک می‌کند؛ اگر هرِ قفل باز نباشد با
   `BLOCKED` می‌ایستد و چیزی منتشر نمی‌کند.

