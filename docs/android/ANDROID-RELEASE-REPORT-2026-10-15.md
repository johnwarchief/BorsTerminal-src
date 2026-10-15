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

## بندِ هفت — آزمونِ نصب و ارتقا رویِ دستگاه

محیطِ آزمون: **شبیه‌سازِ Android 14 (api 34، x86_64، profile pixel_5) درِ CI**.
KVM درِ runner موجود است و AVD بالا می‌آید. رویِ این ماشین هیچِ Android
SDK/Java نصب نیست و هیچِ دستگاهی وصل نیست (`adb devices` خالی)، پس این تنها
دستگاهِ در دسترس است. سه ران انجام شد و هر سه با همان کدِ رابط بودند:

| ران | نتیجه | چه یاد داد |
| --- | --- | --- |
| 38663075135 | 8 FAIL | مسیرِ artifact اشتباه بود (`apks/app-debug.apk`؛ upload-artifact ساختارِ `release/`+`debug/` را نگه می‌دارد). بی‌نصب، همهٔ سنجه‌هایِ بعدی طنینِ همان شکست بودند. |
| 38671378595 | install/launch/back/foreground/crash PASS، سه `webview-*` FAIL | اسکرین‌شات‌ها علت را نشان دادند: گفتگوی «Process system isn't responding» — **system_serverِ AVD قفل می‌کرد**، و تغییرِ مکررِ `wm size/density` همان بار را می‌ساخت. سنجۀ ANR من package-scoped بود و «ANR=0» گزارش کرد ⇒ **سبزِ جعلیِ خودم**. |
| 38696704398 (نهایی، با ابزارِ اصلاح‌شده) | زیرِ 28 دقیقه، یکِ اندازۀ ثابت | جدولِ پایین |

نتیجهٔ رانِ نهایی (`_audit/android_emu/` درِ artifactِ `android-webview-evidence-a791e46`):

| سنجه | نتیجه | شاهد |
| --- | --- | --- |
| نصبِ APK رویِ Android 14 | **PASS** | `app-debug.apk on android-14(api34) Android SDK built for x86_64` |
| اجرایِ اولیه | **PASS** | `pid=2366` |
| دکمۀِ بازگشت (یکِ لمس) | **PASS** | زنده پس ازِ بازگشت (`pid=4078`) — رفتارِ سه‌پله رویِ دستگاهِ واقعی کار می‌کند، خروجِ ناخواسته ندارد |
| background → foreground | **PASS** | `pid=4078` پس ازِ home و راه‌اندازیِ دوباره |
| crash | **PASS** | `FATAL EXCEPTION=0` درِ کلِ logcat |
| نشتِ رمز درِ logcat | **PASS** | `hit=0` با شمارشِ دامنه‌دار (فقط خطوطِ خودِ برنامه/WebView) |
| ANR | **NOT_VERIFIED برایِ ما / محیطِ مریض** | `ANR in com.borsterminal.mobile` = **0**؛ ولی 10 ANR برایِ پروسه‌هایِ خودِ AVD (7× `com.android.phone`، 3× `com.android.providers.media.module`) |
| محتوایِ DOM درِ WebView (CDP) | **NOT_VERIFIED** | `کاوشگر درِ CDP موند (300s)`؛ `page_url=https://localhost/` ازِ HTTPِ DevTools دیده شد (یعنی پوسته، asset server و originِ درست کار می‌کنند) ولی هیچ `Runtime.evaluate` جواب نداد، چون گفتگویِ سیستمی رویِ صفحه بود |
| شواهدِ مستقل (uiautomator) | **FAILِ محیطی** | درختِ دسترس‌پذیری فقط `text="Close app"` و `text="Wait"` را داشت — همان گفتگویِ ANRِ سیستم، نه صفحۀِ اپ |
| رشدِ حافظه | **NOT_VERIFIED** | `dumpsys meminfo` عدد نداد (دستگاه قفل بود) |
| به‌روزرسانی ازِ نسخۀِ رسمیِ قبلی | **NOT_VERIFIED (مستدل)** | امضایِ هر نسخۀِ منتشرشده با کلیدِ debugِ متفاوتِ آنِ ران ⇒ `INSTALL_FAILED_UPDATE_INCOMPATIBLE`. تا کلیدِ رسمیِ ثابت ساخته نشود، ارتقایِ درجا رویِ هیچ گوشی ممکن نیست (بندِ پنج) |
| حفظِ داده پس ازِ ارتقا | **NOT_VERIFIED** | بی‌ارتقایِ ممکن، آزمون معنا ندارد |
| صفحۀِ سفید / لودینگِ دائمی | **درِ Chromium رد شد، درِ دستگاه NOT_VERIFIED** | بندِ سه(الف): 27 رکورد با `bootTiming.source=bundle` و 26–38 ردیفِ واقعی |

**چرا ادامه ندادم:** سه رانِ پیاپی نشان داد AVDِ دونسته‌ایِ GitHub با بارِ
`gunzip 16MB → SQLite 70MB` درِ WebView قفل می‌کند؛ هر رانِ دیگر همین دیوار را
می‌خورد. این محدودیتِ محیطِ آزمون است، نه ادعایِ سلامتِ اپ و نه ادعایِ شکستِ آن.
سنجشِ واقعیِ DOM رویِ **گوشیِ خودِ مالک** (یا هر دستگاهِ فیزیکی) تنها راهِ
بستنِ این بند است؛ ابزارش درِ مخزن هست:
`bash tools/android_emu_verify.sh` با `adb` رویِ دستگاهِ وصل‌شده، و
`node --experimental-strip-types tools/android_webview_check.mts --base http://127.0.0.1:9222`.

هیچ سفارشی به حسابِ معاملاتی فرستاده نشد؛ هیچِ credential درِ آزمون نبود؛
دستگاهِ آزمون مستقل (شبیه‌ساز) بود و هیچِ داده‌ای ازِ ماشینِ مالک بیرون نرفت.

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

**زنجیرۀ امضا بی‌کلیدِ واقعی آزموده شد.** گامِ `Signing smoke test` درِ رانِ
386696704398 (درست: 38696704398) یکِ keystoreِ دورریختنی با `keytool` می‌سازد،
همان `BORS_KEYSTORE_PROPERTIES` را به Gradle می‌دهد و می‌گیرد:
`V2 Signer: certificate SHA-256 digest: bd243d220df0…f373a` و
`SMOKE OK: signingConfig + apksigner زنجیره‌شان کار می‌کند`. بی‌درنگ هم
پاکش می‌کند (`تمیز شد…`) و چون **آخرین** گام است، هیچ گامِ دیگری — از جمله
انتشار — آن فایلِ امضاشده با کلیدِ بی‌ارزش را نمی‌بیند. یعنی وقتی مالک کلیدِ
واقعی را درِ secret بگذارد، هیچ باگِ زیرساختی درِ انتظار نیست.

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

## بندِ یازده — جمعِ ۱۳‌گانه و رأیِ نهایی

### مخزن، شاخه، HEAD و کامیت‌ها

- مخزنِ کد و مقصدِ ریلیز: `johnwarchief/BorsTerminal-src`
- شاخۀ اندروید: `arena/fts-mobile-uiux-20261007` — HEAD = `8a33cc6`
  (`https://github.com/johnwarchief/BorsTerminal-src/tree/arena/fts-mobile-uiux-20261007`)
- ده کامیتِ این دور، از `8af64a1` (وضعیتِ پیشین): `7b18bdc` دروازۀ نسخۀ رسمی ·
  `e7e58d5` safe-area و گریزِ HTML · `faa6594` نسخۀ 1.1.0 و بازنویسیِ پلن ·
  `61c656d` کامنتِ `--` درِ XML · `af8a724` یافتِ APK با glob ·
  `d765cfa` نوارِ پایین · `676dfc5` دودِ امضا و درس‌هایِ شبیه‌ساز ·
  `485a491` مهلتِ CDP · `a791e46` تفکیکِ ANR · `8a33cc6` بندِ هفت
- **هیچ tag و هیچ Release تازۀ اندرویدی ساخته نشد**؛ هیچ برچسبِ `vX.Y.Z`،
  `latest.json`، assetِ ویندوزی و سریِ دادۀ منتشرشده دست‌نخورده است.
- ران‌هایِ شاهد: 38660268640 (قرمزِ XML) · 38660750562 (قرمزِ نامِ artifact) ·
  38663075135 (بیلد سبز + 8 FAILِ مسیر) · 38665643345 (معلقِ CDP) ·
  38671378595 (گفتگویِ ANR) · **38696704398** (نهایی: بیلد سبز، دودِ امضا سبز،
  چرخۀِ عمرِ دستگاه سبز، DOM NOT_VERIFIED)

| # | مورد | کجا درِ همین سند |
| --- | --- | --- |
| ۱ | مخزن، شاخه، HEAD و کامیت‌ها | بندِ صفر + جدولِ پایینِ همین بند |
| ۲ | وضعیتِ اولیه و کارهایِ موجود | بندِ صفر (ماتریسِ موجودی) |
| ۳ | قابلیت‌هایِ تکمیل‌شده/ناتمام | بندِ یک |
| ۴ | اصلاحاتِ کد و فایل‌ها | بندهایِ ۱، ۳، ۴ + `git diff --name-only 8af64a1..HEAD` |
| ۵ | نتایجِ build و تست‌ها | بندهایِ ۶ و ۸ |
| ۶ | وضعیتِ WebView و سازگاریِ Backend | بندِ یک (چک‌لیست) + بندِ دو (endpointها) + بندِ سه(ب) |
| ۷ | آزمونِ دستگاه/شبیه‌ساز | بندِ هفت |
| ۸ | شناسه و نسخۀ اندروید | بندِ صفر و بندِ ۶: `com.borsterminal.mobile` · 1.1.0 · 1001000 |
| ۹ | وضعیتِ امضا و سازگاریِ ارتقا | بندِ پنج |
| ۱۰ | checksum artifactها | بندِ ۶ |
| ۱۱ | URL شاخه/تگ/ریلیز | بندِ ۹ و ۱۰ |
| ۱۲ | محدودیت‌ها/اقدامِ مالک | بندِ ۱۰ (سه کارِ کوتاه) |
| ۱۳ | رأیِ نهایی | پایینِ همین بند |

### رأیِ نهایی: **PARTIAL**

کد، گیت‌ها، artifactِ آزموده‌شده و مستندات آماده‌اند؛ سه گامِ نهایی به
دو کلیدی برمی‌گردد که درِ این پروژه **وجود ندارند** و ساختنِ یک‌جانبۀ آن‌ها
ممنوع بوده (بندِ ۵ مأموریت):

- نسخۀ Release درِ CI ساخته و با `aapt2`/`apksigner` خوانده می‌شود، اما
  **بی‌امضا** است ⇒ نه قابلِ نصب، نه قابلِ انتشار.
- `app-debug.apk` عمداً منتشر نشد؛ پیش‌تر همین بود و همان دلیلِ شکستِ ارتقا
  رویِ گوشی‌ها بود.
- هیچ tag یا Release تازۀ اندرویدی ساخته نشد؛ ریلیزهایِ دسکتاپ، `latest.json`
  و سری‌هایِ داده دست‌نخورده‌اند.

**DONE_VERIFIED نبود** — سه شرطِ آن برقرار نیست: امضایِ انتشار، artifactِ
قابل‌نصب، و Release واقعاً Published. **PARTIAL** است نه BLOCKED، چون کارِ
مستوقفی انجام شد و بلاکر، یکِ اقدامِ کوتاهِ مالک است، نه نبودِ ابزار:

- 12 ایرادِ واقعی درِ کد رفع شد (بندِ ۱ و ۳) — از جمله دو ایرادِ امنیتیِ
  درِ سطحِ WebView (debuggable بودنِ نسخۀ رسمی و `innerHTMLِ` بی‌گریز).
- 52 سنجۀِ گاردِ جدید (`dev/android_release_v1110.py`) درِ `run_all_tests.py`.
- 1555 تستِ فرانت سبز، tsc صفر خطا، lint صفر خطا، بیلدِ موبایل با نسخۀ 1.1.0.
- بیلدِ release درِ CI سبز و artifact با aapt2/apksigner خوانده شد؛
  زنجیرۀ امضا با کلیدِ ساختگی **اثبات** شد (SMOKE OK).
- چرخۀِ عمرِ واقعی رویِ Android 14 سبز: نصب، اجرا، بازگشت،
  background/foreground، بی‌crash و بی‌نشتِ رمز.
- DOMِ WebView رویِ دستگاه و «ارتقایِ درجا» = NOT_VERIFIED با دلیلِ نوشته‌شده
  (AVD قفل می‌کند؛ کلیدِ ثابت وجود ندارد).

**آیا نسخۀ جدید منتشر شد؟ نه.** هیچِ APK امضانشده یا debug به‌عنوان نسخۀ رسمی
منتشر نشد. چیزی که منتشر شده، کدِ آماده، گیت‌ها، artifactِ آزموده و سه دستورِ
کوتاهِ مالک درِ بندِ دهم است.

## بندِ دوازده — دورِ دوم: بلاکرِ بیرونی، هویتِ کلید، بازاجرای گیت‌ها (2026-10-15)

چهار کامیتِ این دور روی `cad01ca5`: `9f0816a` (گاردهایِ ساختاری + سندِ مراسم) ·
`0125f20` (خواندنِ بستۀ داده با اعتبارنامه) · `0875bb6` (سنسورِ ۴۰۴) ·
`21d214b` (هویتِ گواهی + قفلِ AVD). هیچ tag و هیچ Release تازۀ اندرویدی ساخته
نشده؛ `latest.json` دسکتاپ و asset‌های ویندوز دست‌نخورده‌اند (v1.0.89 همان 13 asset است).

### ۱۲-۱ چیزی که بیرونِ این ماشین عوض شد (بلاکرِ اصلی)

| مورد | عدد/شاهد |
| --- | --- |
| `johnwarchief/BorsTerminal-src` | `visibility = private`، `updated_at = 2026-10-15T16:45:41Z` |
| `releases/download/…` رویِ همان مخزن | HTTP 404 بی‌اعتبارنامه (هم برایِ seriesِ `mobile-latest`) |
| همان asset با API + token | HTTP 200 (`/releases/assets/<id>`، `Accept: application/octet-stream`) |
| مقایسه با رانِ موفق | 2026-10-12T23:11:31Z ازِ همان URL `bytes=16179264` گرفته شد |
| پیامد برایِ CI | `Build mobile frontend` با `curl: (22) 404` می‌مرد — رفع شد (`gh release download`) |
| پیامد برایِ گوشی | `frontend/src/shared/api/local/localData.ts` همان URL را می‌خواند و گوشی token ندارد ⇒ **هیچ APK منتشرشده‌ای دادهٔ تازه نمی‌گیرد** |
| پیامد برایِ انتشار | tag و Release اندروید رویِ همان مخزن ساخته می‌شود ⇒ **لینکِ دانلود برایِ هیچ‌کس باز نیست** |

این با کلیدِ امضا حل نمی‌شود. دو راهِ خروج (انتخابِ مالک، با دستورِ تک‌خطی درِ
`docs/android/ANDROID-KEY-CEREMONY.md` بندِ صفر): عمومی‌کردنِ همان مخزن، یا
بردنِ «چیزی که گوشی می‌خواند» (سریِ داده + ریلیز اندروید) به مخزنِ عمومیِ
`johnwarchief/BorsTerminal`. راهِ دوم دارایی‌های ویندوز را دست نمی‌زند.

### ۱۲-۲ سه ران و علتِ واقعیِ هرکدام

| ران | build-apk | upgrade-matrix | WebView | علت |
| --- | --- | --- | --- | --- |
| 38778336195 | FAIL | skipped | skipped | series `mobile-latest-v2` هیچ‌وقت منتشر نشده (۴۰۴) |
| 38778341353 | FAIL | skipped | skipped | همان ۴۰۴، این‌بار روی `mobile-latest` ⇒ ریشه: خصوصی‌شدنِ مخزن |
| 38781829171 | **PASS** | FAIL | FAIL | بیلد باز شد؛ دستگاه‌ها به دو علتِ جدا (پایینِ همین بند) |
| 38794263916 | در حالِ اجرا | — | — | با رفعِ قفلِ صفحه و هویتِ گواهی |

نتیجه‌هایِ سبزِ ران 38781829171 (اولین بیلدِ Release واقعیِ این شاخه):
`app-release-unsigned.apk` · 21,192,125 بایت · `package: name='com.borsterminal.mobile'` ·
`manifest: versionName=1.1.0 versionCode=1001000` · apksigner: `DOES NOT VERIFY` ·
`release APK signing: no` ⇒ دروازۀ انتشار درست بسته است. خلاصۀ همان ران
`BLOCKED for end users` را هم ثبت کرد (سنجشِ دسترسیِ ناشناسِ مسیرِ گوشی).

### ۱۲-۳ دو قرمزیِ دستگاه: هیچ‌کدام ایرادِ اپ نبود

- **قفلِ صفحه‌کلیدِ AVD**: `webview-360x800` درِ CDP 300s موند و `…-a11y` FAIL
  داد («هیچ واژۀ دیدنیِ برنامه نبود») — درختِ uiautomator همان لحظه مالِ
  keyguard بود. حالا `svc power stayon` + `wm dismiss-keyguard` پیش‌ازِ هر کاوش
  اجرا می‌شود (هم درِ `android_emu_verify.sh`، هم درِ `android_upgrade_matrix.sh`)
  و اگر باز هم درختِ قفل بود، حکم `NOT_VERIFIED` با علتِ نوشته‌شده است نه FAIL.
- **خطِ یتیمِ ANR**: بعدِ `fi` یک `step anr FAIL …` مانده بود که بی‌شرط اجرا
  می‌شد؛ همان ران هم‌زمان «ANR=0 برایِ ما، 9 ANR مالِ پروسه‌هایِ AVD» را
  NOT_VERIFIED و FAIL چاپ کرد. خطِ یتیم حذف شد؛ تفکیکِ فرآیند تنها رأی است.
- مادۀ ارتقا درِ آن ران اصلاً بوت نشد (`adb: device offline` برایِ ۷ دقیقه،
  exit 224) درحالی‌که WebViewِ همان ران بالا آمد ⇒ مهلتِ بوت رویِ 20m رفت.

### ۱۲-۴ گیت‌هایِ بازاجراشده (اعدادِ همین دور)

| گیت | فرمان | نتیجه |
| --- | --- | --- |
| تایپ‌چک | `npx tsc -b` | 0 خطا |
| تستِ فرانت | `npx vitest run` | 149 پرونده، 1564 pass، 1 skip |
| lint + مرزها | `npm run lint` | 0 خطا |
| گاردِ اندروید | `python dev/android_release_v1110.py` | **83/83** |
| گاردِ حروفِ فارسی | `python dev/persian_glyph_guard.py` | 4/4 |
| همۀ گاردها | `python dev/run_all_tests.py` | 6 قرمزِ ازِ پیش موجود (بدونِ تغییر) |
| چیدمانِ 360px | `node tools/android_viewport_probe.mts` | 27 پرونده (3 اندازه × 9 route)، 0 سنجۀ رد |
| بی‌اعتبارنامۀ ثابت درِ باندل | پایشِ `frontend/dist` (39 فایل) | 0 برخورد با `bors123` |

قرمزهایِ پایه همان شش موردِ ثبت‌شدۀ دورهایِ پیشین است (KLineCharts v10 API،
setupهایِ سه‌حالته، Round J jet، یکپارچگیِ کندل/parity، R1/R2 housekeeping،
فیلترهایِ نوار) و هیچ‌کدام درِ این دور به اندروید ربط ندارد.

### ۱۲-۵ عددِ چیدمانِ 360×800 (همان چیزی که خواسته شده بود)

`nav` جعبه‌اش `x=0 y=688 w=360 h=112` و `bottom=800` ⇒ نوارِ دو ردیفی دقیقاً
لبه‌یِ پایین می‌نشیند و رویِ محتوا نمی‌افتد؛ `tabWidths = [56,56,56,56,56,56]`
(هیچ تبی زیرِ 44px نیست)، `navRowScrolls = false`، `utilityClipped = 0`،
`padClearsBar` با `appContentPadBottom = 120px` ≥ 112px. بوتِ بستۀ داده:
gz 16,179,264 B ⇒ SQLite 70,619,136 B درِ 422ms (`fetch 234 / gunzip 169 / open 19`).
`utilityHidden = 1` همان دکمۀ «به‌روزرسانی» است که درِ حالتِ بی‌سرور عمداً
`0×0` است — پنهان، نه بریده؛ و درِ حکم شمرده نمی‌شود.

### ۱۲-۶ اثرانگشتِ چهار APKِ منتشرشده — مدرکِ «چرا کلیدِ رسمی»

`tools/apk_cert_fingerprint.py` (نویس، بی‌Java) گواهی را ازِ خودِ فایل می‌خواند:

| ریلیز | گواهی | SHA-256ِ گواهی |
| --- | --- | --- |
| `mobile-latest` (مخزنِ توزیع) | `CN=Android Debug`، valid از 2026-10-07 | `15:92:23:E4:…:36:3C:CF:35` |
| `mobile-uiux-20261007` | `CN=Android Debug`، valid از 2026-10-07 | `7C:13:31:22:…:90:8B:82:BE` |
| `mobile-parity-b336ad3` | `CN=Android Debug`، valid از 2026-10-08 | `DA:C8:5F:57:…:30:3C:F3:50` |
| `mobile-parity-9f7427d` | `CN=Android Debug`، valid از 2026-10-12 | `27:04:64:18:…:23:38:A2:30` |

چهار بیلد، چهار گواهیِ debugِ متفاوت ⇒ هیچ‌کدام با کلیدِ دیگری سازگار نیست و
ارتقایِ درجا رویِ گوشیِ نصب‌شده ناممکن است. این همان دلیلی است که نسخهٔ رسمی
نیاز به **یک** keystore دارد و چرا نسخهٔ اوّلِ رسمی باید با حذفِ نسخۀ قبلی نصب
شود (هشدارِ Release Notes درِ بندِ ۱۰ ازِ پیش نوشته شده است).

### ۱۲-۷ چهار سنسوری که درِ این دور دروغ می‌گفتند و اصلاح شدند

| سنسور | دروغ | اصلاح |
| --- | --- | --- |
| برشِ workflow درِ گارد | `WF.split(name)[1]` با ذکرِ نام درِ توضیحِ jobِ دیگر بدنهٔ اشتباه می‌داد ⇒ A30/A32 بی‌دلیل قرمز | `job_body/step_body/step_pos` از سطرِ ساختاری + A67..A69 با کنترلِ منفی |
| `notFound` کاوشگرِ viewport | `/پیدا نشد|۴۰|404/` رویِ متنِ body ⇒ 9 پروندۀ واقعی ۴۰۴ خوانده شد و خودِ صفحۀ ۴۰۴ false | testidِ `route-not-found` + حکمِ جدیدِ `no404Fallback` (A73..A75) |
| رأیِ ANR | خطِ یتیم بعدِ `fi` ⇒ همیشه FAIL | حذف؛ تفکیکِ فرآیند تنها رأی (A79) |
| `apk_cert_fingerprint` | جدولِ idها ازِ حافظه + هندسۀ غلط ⇒ رویِ APKِ debug حکمِ «OFFICIAL-CERT» داد | جفت‌ها با پارسِ ساختاری شناخته می‌شوند، هندسه ازِ اندازه‌گیریِ واقعی، حکم fail-closed (A80) |

### ۱۲-۸ رأی

**PARTIAL — منتشر نشده و منتشرنشدنی تا دو تصمیمِ مالک.** گیت‌هایِ کد و بیلد
سبزند و بیلدِ Release واقعی ساخته و ازِ خودِ artifact خوانده شد؛ امضایِ رسمی
و دسترسیِ ناشناسِ مخزنِ src دو قفلِ بیرونی‌اند. هیچ APK بی‌امضا یا debug به‌عنوان
نسخۀ رسمی منتشر نشد و هیچ نسخۀ منتشرشده‌ای حذف/بازنویسی نشد.

## بندِ سیزده — «src خصوصی می‌ماند»: راهِ عمومیِ داده و ریلیز، و مادۀ ارتقایِ سبز

مالک تصمیم گرفت `johnwarchief/BorsTerminal-src` خصوصی بماند. پس «خصوصی‌بودن»
با «کدِ موبایل باید عمومی خوانده شود» درگیر نمی‌شود — دو مقصد جدا می‌شود.

### ۱۳-۱ جداسازیِ مقصدها

| چیز | مقصد | چرا |
| --- | --- | --- |
| کد، workflow، ران‌ها، secrets و vars | `…-src` (خصوصی) | `secrets.*` / `vars.*` از مخزنِ خودِ workflow خوانده می‌شوند |
| بستۀ دادۀ موبایل (`mobile_snapshot.db.gz` + `.meta.json` + `.sig`) | `johnwarchief/BorsTerminal` (عمومی) | گوشی token ندارد |
| ریلیز و tag اندروید (`android-1.1.0`) | `johnwarchief/BorsTerminal` (عمومی) | لینکِ نصب باید برایِ کاربر باز باشد |

پیاده‌سازی: `SERIES_REPO` و `PUBLISH_REPO` درِ `mobile.yml`، `REPO_DEFAULT` درِ
`scripts/publish_mobile_series.py`، پیش‌فرضِ `REMOTE_BASE` درِ `localData.ts`، و دو
specِ دادۀ موبایل + کاوشگرِ سازگاریِ کلاینتِ کهنه. هیچ tokenی درِ باندل نیست و
هیچ مسیرِ احرازِ هویتی درِ فرانت وجود ندارد (شاهد: `grep -rl Authorization
frontend/src` → صفر فایل). نوشتنِ ریلیز درِ مخزنِ عمومی با
`secrets.RELEASE_TOKEN` انجام می‌شود، چون `GITHUB_TOKEN`ِ کارفرما به آن مخزن
نوشتن نمی‌کند.

### ۱۳-۲ یک قفلِ اضافه که ازِ همین جدول می‌آید

`api/update.py:66` آپدیتِ دسکتاپ را ازِ
`…/BorsTerminal/releases/latest/download/latest.json` می‌خواند، و آن مسیر «آخرین
ریلیزِ **غیرپیش‌انتشار**» است. اگر ریلیزِ اندروید درِ همان مخزن stable منتشر شود،
`latest` به `android-…` می‌چرخد و آپدیتِ ویندوز 404 می‌گیرد. پس
`prerelease=false` درِ گامِ انتشار صریحاً رد می‌شود؛ لینکِ مستقیمِ APK مستقل از
این پرچم باز و ثابت است. گامِ پسِ انتشار هم همین را اندازه می‌گیرد:
`releases/latest/download/latest.json` را ناشناس می‌خواند و نسخه‌اش را چاپ می‌کند.

### ۱۳-۳ آنچه دربارهٔ بستۀ دادۀ عمومی اندازه گرفته شد

چیزی که امروز درِ مخزنِ عمومی به‌عنوان `mobile-latest` هست، قراردادِ **کهنه** دارد:

- `mobile_snapshot.db.meta.json` (ناشناس، 200) = 106 بایت، فقط چهار کلید:
  `app_version=1.0.65`, `built_at=2026-10-07T09:29:30`, `baked_ok=4381`,
  `gz_bytes=23498222`.
- `mobile_snapshot.db.gz` (ناشناس) = 23,498,222 بایت ← gunzip ← 78,729,216 بایت
  SQLite با 10 جدول (`baked, meta, instruments, market_watch, price_history,
  boards, market_index, market_totals, …`)؛ جدولِ `tsetmc` را ندارد و `meta`اش
  کلیدهایِ `app_version/baked_ok/baked_fail/built_at/schema` دارد.
- `parseManifest()` درِ کلاینت این‌ها را لازم می‌دارد: `schema_version`,
  `package_id`, `built_at`, `gz_sha256`, `app_version`, `min_app_version`
  (و `series` را با `checkSeries` می‌سنجد). هیچ‌کدام درِ آن meta نیست ⇒ بسته **رد**
  می‌شود و گوشی همان بستۀ همراهِ APK را نگه می‌دارد.

خواندش: کانالِ تازه‌سازیِ داده تا سریِ v2 منتشر نشود باز نیست — و این
fail-closedِ مستند است، نه خرابیِ پنهان. انتشارِ v2 درِ مخزنِ عمومی (بندِ ۶ سندِ
مراسم با `--repo` جدید) و `MOBILE_MANIFEST_PUBKEY` کارِ مالک است.

### ۱۳-۴ مادۀ ارتقایِ واقعی: ۱۲ PASS / ۰ FAIL (ران 38797140980، شبیۀ Android 14)

سه APK با دو کلیدِ دورریختنیِ هم‌انسان ساخته شد (هیچ‌وقت منتشر نشدند، بی‌درنگ
پاک شدند): `a1` با کلیدِ A و نسخۀ 1.1.0/versionCode 1001000، `a2` با همان کلیدِ A
و 1.1.1/1001001، `b1` با کلیدِ B و 1.1.1/1001001.

| سنج | نتیجه | شاهد |
| --- | --- | --- |
| boot | PASS | `sys.boot_completed=1` |
| build-a1/a2/b1 | PASS | سه `app-release.apk` (نامِ خروجی با کلید عوض می‌شود) |
| same-key-fingerprint-stable | PASS | `ad20cef6bd02ed58…` درِ هر دو بیلدِ یکسان |
| other-key-fingerprint-differs | PASS | `11c73980ba615193…` |
| clean-install-official | PASS | versionCode 1001000 |
| launch-after-clean-install | PASS | pid=2925 |
| **upgrade-same-key** | **PASS** | 1.1.0/1001000 → 1.1.1/1001001 با همان گواهی — ارتقایِ درجا واقعاً کار می‌کند |
| **reject-different-cert** | **PASS** | اندروید `INSTALL_FAILED_UPDATE_INCOMPATIBLE` داد |
| fresh-install-after-uninstall | PASS | پسِ حذف، کلیدِ دیگر نصب می‌شود (دادهٔ محلی می‌سوزد) |
| version-source-restored | PASS | `package.json` به 1.1.0 برگشت |

چهار قرمزیِ رانِ پیشین (38794263916) ازِ همین‌جا رفع شد: `-PBorsVersionCode`
جعلی بود و گاردِ BORS-VERSION آن را رد می‌کرد (پیامِ AGP گمراه‌کننده:
«does not specify compileSdk»)، حالا نسخۀ بالاتر ازِ مبنایِ یکتا نوشته و بازگردانده
می‌شود. چون مشتریِ اندرویدی وجود ندارد، سازگاریِ backwards لازم نیست؛ آنچه لازم
است **ثابت‌ماندنِ یک کلید** است و این مادۀ آن را با دو کلیدِ متفاوت اثبات کرد.

### ۱۳-۵ WebView رویِ دستگاه: چرخۀِ عمر سبز، محتوایِ صفحه هنوز بی‌اثبات

درِ همان ران: `install` PASS، `launch` PASS (pid=2611)، `back_button` PASS
(پنجرۀ «برایِ خروج دوباره بزنید» و پروسه زنده)، `background_foreground` PASS،
`crash` PASS (`FATAL EXCEPTION=0`)، `logcat_secrets` PASS (hit=0؛ خطوطِ سیستمی
شمرده نشد)، `anr` NOT_VERIFIED (صفر ANR برایِ `com.borsterminal.mobile`؛ ۶ ANR مالِ
پروسه‌هایِ خودِ AVD — پس خطِ یتیمِ قبلی، که همیشه FAIL می‌داد، رفع شده است).

دو سنجۀ محتوا سبز نشدند و علتشان درِ کدِ کاوشگر بود، نه اپ:
- CDP: نامِ socket ازِ pidِ خودِ اپ ساخته می‌شد، و WebView پروسۀ رندرِ جدا دارد ⇒
  «CDP درِ دسترس نیست». حالا نام ازِ `/proc/net/unix` خوانده می‌شود و بی‌socket،
  پروندۀ شواهد نوشته می‌شود.
- درختِ دسترس‌پذیری: فهرستِ واژگان پنج کلمهٔ تنگ بود؛ حالا ازِ خودِ سورسِ رابط
  گرفته شده (قیف 159، تابلو 476، شاخص 426، معامله 105، غربالگری 87، بورس 74) و
  درِ شکست، تعداد گره‌ها + `mCurrentFocus` + متن‌هایِ دیدنی ثبت می‌شود.
- راه‌اندازی هم یک تلاشِ تنها بود و flakeِ system_server را FAIL می‌کرد؛ سه تلاش
  با شواهد شد.

**حکمِ صادق:** «DOM/محتوایِ صفحه رویِ دستگاه» تا رانِ تازه = **NOT_VERIFIED**؛
«برنامۀ واقعی رویِ شبیه‌ساز نصب و اجرا می‌شود و نمی‌میرد» = **PASS**. عددِ چیدمانِ
سه viewport ازِ Chromium می‌آید (بندِ ۱۲-۵) و جایِ سنجشِ دستگاه را نمی‌گیرد.

### ۱۳-۶ بی‌اعتبارنامۀ ثابت درِ خودِ artifact

`app-release-unsigned.apk` ازِ artifactِ ران 38781829171 (sha256
`ef4591f2854b…42ac`، که با sha256ِ چاپ‌شدۀ همان ران یکی است — یعنی دانلودِ
artifact همان بایت‌هایِ بیلد است) باز شد و ۳۵ فایل js درِ `assets/public/` با
الگوهایِ `Authorization`, `Bearer`, `ghp_…`, `PRIVATE KEY`, `storepass`,
`bors123`, `DEFAULT_PASS`, و `password="…"` اسکن شد: **صفر برخورد**.
مکانیزمِ قفلِ صفحه (`crypto.subtle` / `deriveBits` / `bors_screen_lock`) درِ
باندل هست، پس قابلیتِ لازم مانده و اعتبارنامۀ ثابت نرفته است.

### ۱۳-۷ گیت‌ها درِ همین دور

`tsc -b` صفر خطا · دو specِ دادۀ موبایل 44/44 · گاردِ اندروید **97/97** ·
`persian_glyph_guard` 4/4 · `run_all_tests` با 6 قرمزِ ازِ پیش موجود (بدونِ تغییر) ·
`bash -n` رویِ هر دو اسکریپتِ دستگاه · YAMLِ `mobile.yml` با `yaml.safe_load`
اعتبارسنجی شد (و دو بار که خراب شده بود، همین اعتبارسنجی گرفت: lines 324 و 536).

### ۱۳-۸ کارِ دقیقِ باقی‌ماندهٔ مالک

1. `bash scripts/android_release_key_ceremony.sh keygen` → `backup` →
   `verify-backup` → `restore` (drill) → `publish-secrets` (دو secret).
2. `python scripts/sign_mobile_manifest.py --keygen …` و `gh variable set
   MOBILE_MANIFEST_PUBKEY --repo johnwarchief/BorsTerminal-src`.
3. `bash scripts/android_release_key_ceremony.sh fingerprint` و `gh variable set
   ANDROID_RELEASE_CERT_SHA256 --repo johnwarchief/BorsTerminal-src` (اثرانگشتِ
   public، نه کلیدِ خصوصی).
4. `python scripts/publish_mobile_series.py --yes` — حالا درِ **مخزنِ عمومی**
   سریِ `mobile-latest-v2` را با `.sig` منتشر می‌کند.
5. `gh workflow run mobile.yml -f publish=true` (با `prerelease` پیش‌فرضِ true).
   دروازۀ چهارشرطی: APK امضاشده، کلیدِ عمومی درِ باندل، امضایِ بستۀ داده معتبر،
   و سریِ هدفِ کهنه نبودن. بی‌هر چهار، منتشر نمی‌شود.

