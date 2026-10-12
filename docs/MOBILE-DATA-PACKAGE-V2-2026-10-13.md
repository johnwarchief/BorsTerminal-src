# بستۀ دادۀ موبایل — قرارداد v2، امضا، نسخۀ یکتا و سازگاری (۲۰۲۶-۱۰-۱۳)

مأموریت: Stage 4 دورِ اندروید. شاخه `arena/fts-mobile-uiux-20261007`، مبدأ
`28f7715` (بازرسی شد؛ همان چیزی است که مأموریت گزارش داده بود). هیچ merge،
tag، ریلیز عمومی یا انتشار APK انجام نشده و `mobile-latest` دست‌نخورده است.

دسترس‌پذیریِ داده: همهِ عددّهای این سند از اجرای واقعی روی همین ماشین‌اند؛
هرجا اجرا نشده، صریح `BLOCKED` یا `NOT RUN` نوشته شده است.

## ۱) ساختِ واقعیِ بسته (نه fixture)

سازنده `scripts/build_mobile_snapshot.py` رویِ **کپیِ فقط‌خواندنیِ** دیتابیس
اجرا شد. `market.db` عملیاتیِ این checkout با `sqlite3.backup()` (WAL-safe،
`mode=ro`) به `_audit/tmp/stage4/market_src.db` کپی شده بود و از همان کپی، سه
ورودیِ متفاوت با حذفِ `price_history` نمادهایِ دیگر ساخته شد — سه بسته، سه
دستۀ بایتیِ **واقعاً متفاوت**:

| بسته | package_id | built_at | gz بایت | gz_sha256 (۱۶ نویسهٔ اول) | baked |
| --- | --- | --- | --- | --- | --- |
| pkg_full | 20261012T224841-2eef179b | 2026-10-12T22:48:41 | 16,133,606 | 2eef179bae50f84e | 4627 (۱ fail) |
| pkg1 | 20261012T235159-48080eea | 2026-10-12T23:51:59 | 1,452,865 | 48080eeaabfd28c6 | 48 |
| pkg2 | 20261012T235326-1e6ad9ff | 2026-10-12T23:53:26 | 1,387,014 | 1e6ad9fff2b28a54 | 48 |
| pkg3 | 20261012T235415-59808ca6 | 2026-10-12T23:54:15 | 1,333,013 | 59808ca6c2b29647 | 48 |
| pkg_bad_db | 20261012T235642-3e45185e | 2026-10-12T23:56:42 | 1,332,872 | 3e45185ec712d7cd | 48 |

بازرسِ مستقل `tools/verify_mobile_snapshot.py` (هیچ کدی از سازنده را صدا
نمی‌زند مگر امضا/بررسی) برای هر سه بستۀ سالم: `verdict: PASS`،
`gz_bytes` و `gz_sha256`ِ manifest = بایت‌هایِ واقعی، `integrity_check: ok`،
جدول‌های `baked/meta/instruments/price_history` حاضر، `market_board` پخته،
`meta.built_at`/`meta.app_version`/`meta.schema` با manifest هم‌خوان، و
«تغییرِ یکِ بایتِ manifest ⇒ امضا رد» (`tampered_manifest_signature: rejected`).

`market.db` و `user.dbِ checkout` پیش و پس از هر اجرا مقایسه شدند:
`checkout_files_unchanged: true` (sha256/size/mtime یکسان).

## ۲) امضایِ manifest (اصالتِ ناشر، نه فقطِ تمامیت)

- الگوریتم: بلوکِ **minisign** با `alg = Ed` (Ed25519 رویِ پیامِ خام). انتخاب
  با سنجش، نه حدس: درِ Chromium همین ماشین `crypto.subtle` کلیدِ Ed25519 را
  با `importRaw` می‌پذیرد و `verify=true` / بدنهٔ دست‌خورده `false` داد
  (`_audit/tmp/stage5/crypto_probe.json`). الگوریتمِ `ED` (امضایِ رویِ
  blake2b، خروجیِ `tauri signer`) صریح **رد** می‌شود، چون WebCrypto blake2b
  ندارد — کلاینت به‌جایِ پذیرشِ بی‌آزمون، `signature-alg-unknown` می‌دهد.
- امضا رویِ **بایت‌هایِ فایلِ مستقلِ manifest** است؛ `.sig` کنارش می‌نشیند
  (`manifest.json.sig`) و هیچ‌وقت داخلِ manifest نمی‌آید تا دورِ باطلِ
  «فایلِ خودش را هش/امضا کند» نسازیم. manifest با `newline="\n"` نوشته می‌شود
  تا بایت‌هایِ Windows و Linuxِ CI یکی بماند (با CRLF، اعتبارِ امضا به ماشینِ
  سازنده بند می‌شد — و همین، نشرۀِ کهنۀ منتشرشده را با CRLF نشان می‌دهد).
- `key_id = SHA-256(DER SPKI)[:8]`؛ ترتیبِ داوری درِ کلاینت: بایتِ خامِ manifest
  ← بررسیِ امضا ← **بعدش** `JSON.parse` و `parseManifest`. هیچ فیلدی از
  manifest پیش از تأییدِ اصالت خوانده نمی‌شود.
- کلیدِ خصوصی: بیرون از مخزن. `--keygen` نوشتنِ کلید داخلِ ریپو را رد می‌کند؛
  منبعِ کلید `BORS_MOBILE_MANIFEST_KEY` (مسیر PEM) یا `BORS_MOBILE_MANIFEST_KEY_PEM`
  (متنِ secret در CI). نبودِ کلید ⇒ سازنده `BLOCKED` با rc=3 و
  `--require-signature` همان‌جا می‌شکند؛ **کلیدِ نمایشی هرگز جایِ کلیدِ انتشار
  را نمی‌گیرد**. برایِ این دور دو جفت‌کلیدِ نمایشی در
  `C:/Users/PCMOD/Desktop/_bors_mobile_e2e_keys/{A,B}` ساخته شد (بیرونِ مخزن،
  commit نشده): A با `key_id 943988b82e5fb6fa` و B با `0bb0abcc89016d21`.
  آنچه درِ مخزن است: متنِ public، fixtureهایِ public/manifest/sig، و کد.
- CI: `vars.MOBILE_MANIFEST_PUBKEY` به vite پاس می‌شود؛ گامِ «Verify the data
  package signature» با همان ابزارِ پایتونِ مخزن بررسی می‌کند (راستی‌آزماییِ
  بسته درِ pipeline بی‌کلیدِ خصوصی ممکن است؛ public کافی است) و **دروازۀ
  انتشار** بی‌`verified` یا بی‌publickey انتشار را می‌بندد. هیچ رازِ محیطی در
  لاگ چاپ نمی‌شود (نه متنِ PEM، نه مقدارِ secret؛ فقط `key_id` و وضعیت).

## ۳) نسخۀ یکتایِ برنامه

منبع: `frontend/package.json` (هم‌اکنون `1.0.79`، هم‌راستا با
`bors_config.APP_VERSION`). CI آن را صریح می‌خواند و به سه مصرف‌کننده می‌دهد:
`VITE_APP_VERSION`، `versionName` و `versionCode` (Gradle از `JsonSlurper` و
`-PBorsVersionName/-PBorsVersionCode`)، به‌علاوهٔ متادیتایِ ریلیز.
`versionCode = major·10⁶ + minor·10³ + patch` ⇒ برای `1.0.79` عددِ `1000079`؛
سیاست در `frontend/android/app/build.gradle` نوشته شده و هر دو مقدارِ تزریق‌شدهٔ
ناهمخوان و minor/patch خارج از `0..999` را `GradleException` می‌کند.

سنجشِ واقعیِ خروجی (نه متغیرهایِ YAML): درِ `dist/assets` متنِ `1.0.79` و
کلیدِ عمومیِ امضا grep شد (`localData-DcrO4ANr.js`)؛ درِ CI دو گام اضافه شده
که پس ازِ بیلد همان‌ها را درِ فایل‌هایِ بیلدشده و درِ `merged_manifests`ِ APK
می‌جویند و نبودشان شکستِ build است.

**BLOCKED محلی:** `java` و Android SDK روی این ماشین نیست (`java: command
not found`، `local.properties` نبود) ⇒ `gradlew assembleRelease` و خواندنِ
`versionName/versionCode` از APK درِ این دور **اجرا نشد**؛ فقط درِ CI.
ادعایِ «APK ساخته و راستی‌آزمایی شد» درِ این دور نیست.

## ۴) نگهداشتِ نسخهٔ سالم و rollback — باگِ واقعی که مرورگر دید

قرارداد: پس ازِ **فعال‌سازیِ موفق** حداکثر دو بسته می‌ماند (فعال + آخرینِ
فعال‌شدۀِ معتبر). هیچ پاک‌سازیِ پیش‌دستانه‌ای نیست: نه پیش ازِ اعتبارسنجی، نه
درِ شکستِ دانلود، نه درِ کمبودِ فضا. `rollbackToPreviousPackage()` فقط به
بستۀِ **فعال‌شدۀِ قبلی** اشاره می‌کند و پیش از جابه‌جاییِ pointer، digestِ
بایت‌هایِ کشیده را دوباره می‌سنجد.

مرحلۀ ۵ یکِ باگِ جدی نشان داد که آزمون‌های jsdom نمی‌دیدند:
`Cache.keys()` درِ مرورگر **آدرسِ مطلق** می‌دهد
(`http://origin/pkg/<id>.gz`)، اما pointer رشتهٔ نسبیِ `pkg/<id>.gz` را نگه
می‌دارد؛ مقایسهٔ این دو هرگز برابری نمی‌داد، پس «محفوظ‌ها» هیچ‌وقت محفوظ
نمی‌ماندند و پاک‌سازی **همان بستۀِ پیشینِ سالم** را حذف می‌کرد (درِ Chromium:
پس ازِ فعال‌سازیِ دوم، staging تهی شد و rollback بی‌نامزد ماند).
`retainPackages()` اکنون با `absCacheKey()` کلیدها را حل می‌کند.

دو اصلاحِ دیگر که همان اجرا لازم کرد:
- بستۀِ **ردشده** در staging نمی‌ماند (`dropRejectedCandidate`) — هر دورِ
  ناموفق با package_idِ تازه وگرنه چند مگابایتِ بی‌مصرف می‌انباشَد؛ فعال و
  پیشینِ سالم در این مسیر هرگز حذف نمی‌شوند (کنترلِ منفی درِ آزمون).
- پنلِ 🛠 دکمۀِ «بازگشت به نسخۀ پیشین» دارد (نامزدِ معتبر هست ⇒ دکمه هست) و
  `snapshotStatus().previousPackageId` را رو می‌کند؛ بی‌این، rollback فقط توابع
  بود و رویِ گوشی مصرف‌کننده نداشت.

**آزمونِ سنسور:** fakeِ jsdom با کلیدِ نسبی، باگ را پنهان می‌کرد. fake
`Cache` در `mobile-snapshot-integrity.spec.ts` به رفتارِ مرورگر («کلید = آدرسِ
مطلق») برگردانده شد. با همان fake و **بی** اصلاحِ `retainPackages`، پنج آزمون
قرمز می‌شوند: ۱۸ «سه فعال‌سازی ⇒ دقیقاً دو بسته»، ۱۹ «اجرایِ دوبارۀ نگهداشت
پایدار است»، ۲۰ «rollback به آخرین فعال‌شدۀ معتبر»، ۲۱ «digestِ بستۀ پیشین» و
۲۳ «بستۀِ ردشده درِ staging نمی‌ماند» — و با اصلاح، هر ۳۳ سبز. (این را با
بازگرداندنِ موقتِ همان دو سطرِ معیوب و مقایسۀ sha1 فایل سنجیدم، نه با حدس.)

## ۵) زنجیرۀ کامل درِ Chromium واقعی

ابزار: `tools/mobile_signed_package_e2e.mts`. همان `vite build`ِ موبایل (با
`VITE_MOBILE_MANIFEST_PUBKEY` کلیدِ A، `VITE_SNAPSHOT_URL=/probe_bundle.js`،
`VITE_SNAPSHOT_REMOTE=/release`)، سرورِ Node روی `127.0.0.1`، و بایت‌هایِ
**واقعیِ** بسته‌ها. رابطِ واقعی اجرا می‌شود: بنرِ راه‌اندازی، پنلِ 🛠، دکمۀِ
«بررسی دستیِ به‌روزرسانی داده» و دکمۀِ بازگشت.

نتیجه: `66/66 PASS` (`_audit/mobile_stage5_e2e.json`)، موتورِ Chromium
`151.0.7922.34`، مسیرِ اجراییِ همان chromium-1234 که WebView شبیه‌سازی می‌شود.

| سنجه | چه می‌سنجد | رأی |
| --- | --- | --- |
| S0 | بوت از بستۀِ همراهِ APK، تابلو ردیف دارد، بی‌فعال‌سازی pointer نوشته نمی‌شود | PASS |
| S1 | manifest امضاشده ← … ← pointer و مُهرِ built_at | PASS |
| S2 | فعال‌سازیِ دوم؛ pkg1 نامزدِ بازگشت می‌ماند؛ دو بسته در staging | PASS |
| S3 | فعال‌سازیِ سوم؛ فقط دو تا می‌ماند و pkg1 حذف می‌شود | PASS |
| S4 | reload: منبع «کشِ دستگاه» و دادۀ pkg3 (۴۷۴۰ کندل) مصرف می‌شود | PASS |
| S5–S12 | هشت تزریقِ شکست: امضا نیست، امضا دست‌خورده، امضایِ کلیدِ دیگر، manifest دست‌خورده، gz نصفه، gz دست‌خورده، SQLite باز نمی‌شود، ریلیز نیست — در **همه**: رأیِ درست، فعال و پیشین و دو بستهٔ سالم می‌مانند | PASS |
| S13 | پس ازِ هشت شکست، pkg3 هنوز خوانده می‌شود و تابلو ردیف دارد | PASS |
| S14–S15 | بازگشت به pkg2 (فقط نامزدِ معتبر) و مصرفِ دادۀِ او (۶۸۷۴ کندل) | PASS |
| S16 | pointerِ بی‌بسته: بازنشسته می‌شود و برنامه به بستۀِ APK برمی‌گردد، بی‌کرش | PASS |
| S17 | manifestِ **کهنۀ منتشرشده** (همان ۱۱۱ بایت، امضاشده با کلیدِ نمایشی) ⇒ رد با `manifest-field-missing`، pointer ساخته نمی‌شود، دادۀِ همراه مصرف می‌ماند | PASS |
| NP | بیلدِ بی‌کلیدِ عمومی ⇒ `signing-key-unconfigured`، هیچ فعال‌سازی، دادۀِ APK سالم (`7/7` در `_audit/tmp/stage5/e2e_no_pubkey.json`) | PASS |

زمان‌هایِ واقعیِ راه‌اندازی روی همین ماشین (بستۀ ۱٫۴ مگابایتی): دریافت ۵۳ms،
بازگشایی ۲۶ms، باز کردن SQLite ۶ms؛ از کشِ دستگاه: ۳۵/۲۹/۲ms.

محدودیتِ صادقانه: پاسخِ بزرگِ `.gz` درِ Chromiumِ دسکتاپ به fetch **۲۰۴** می‌شود
(اندازه‌گیری‌شده: `gz_fetch_check.mts`؛ ۱٫۴MB و ۱۶MB و ۶۲MB همه ۲۰۴، همان بایت
با نامِ `.js` ⇒ ۲۰۰)؛ پس بایت‌ها درِ پروب با `page.route` تحویل می‌شوند. رویِ
گوشی همان مسیر از `CapacitorHttp` بومی می‌رود. **این پروب Android WebView را
اثبات نمی‌کند**؛ Cache API و crypto.subtle و DecompressionStreamِ واقعی را درِ
Chromium اثبات می‌کند. نتیجهٔ jsdom جایِ این را نمی‌گیرد.

## ۶) سازگاریِ کهنه با قراردادِ تازه

واقعیتِ منتشرشده (فقط خوانده شد؛ چیزی بازنویسی نشد):

| چیز | مقدار |
| --- | --- |
| tag | `mobile-latest` (pre-release، منتشر ۲۰۲۶-۰۹-۳۰، به‌روزرسانیِ آسست‌ها ۲۰۲۶-۱۰-۰۸) |
| `mobile_snapshot.db.gz` | ۱۶٬۱۷۹٬۲۶۴ بایت · sha256 `c36eb08a5bbc9e0e…` · دانلود ۷ |
| `mobile_snapshot.db.meta.json` | ۱۱۱ بایت · sha256 `1b5d5e2ce1fcecb7…` · دانلود ۶ |
| شکلِ manifest | چهار کلید: `app_version`, `built_at`, `baked_ok`, `gz_bytes` — بی‌`schema_version`، بی‌`gz_sha256`، بی‌`package_id`؛ با CRLF |
| APK | `bors-terminal-mobile.apk` ۲۵٬۳۲۷٬۵۳۵ بایت · sha256 `61959eabaa6c4cff…` |
| همان gz محلی | `dist_mobile/mobile_snapshot.db.gz` **بایت‌به‌بایت** همان فایلِ منتشرشده |

سپس بایلدِ **داخلِ همان APK** (`assets/public/**`) بیرون کشیده و درِ Chromium
اجرا شد: `tools/mobile_old_client_compat_probe.mts` ⇒ `8/8 PASS`
(`_audit/mobile_stage6_old_client.json`). آنچه کلاینتِ کهنه با کاندیدای v2 کرد:

- با manifestِ v2 **بوت کرد**: پنلِ 🛠 گفت «4627 بسته»، «تابلوی آفلاین 5921 ردیف»،
  «منبع: دانلود از ریلیز» — فیلدهایِ افزوده (`schema_version`, `package_id`,
  `gz_sha256`, `min_app_version`, `db_schema`) برایش بی‌معنا و بی‌ضررند؛
- دورۀِ ۱۵ ثانیه‌ایِ بررسیِ پس‌زمینه اجرا شد، کاندیدای تازه‌تر را **دانلود و کش**
  کرد (اندازهٔ کش = ۱٬۳۳۳٬۰۱۳ بایت، همان gz) و مُهرِ `built_at` را نوشت؛
- کلیدهایِ وضعیتِ نسلِ جدید (`bors_snapshot_active_v2`,
  `bors-mobile-snapshot-staging-v2`) را نمی‌نویسد ⇒ فضایِ وضعیتِ دو نسل با هم
  نمی‌جنگد؛
- پس ازِ reload همان بستۀِ v2 از کشِ او («کشِ دستگاه») مصرف شد؛
- هیچ استثنایِ مدیریت‌نشده درِ کنسول.

و جهتِ دیگر (کلاینتِ همین شاخه با آرتیفکتِ امروزِ `mobile-latest`) درِ S17 سنجیده
شد: **رد** (`manifest-field-missing: schema_version نیست`) و برگشت به بستۀِ
همراهِ برنامه. یعنی `mobile-latest` را نمی‌شود با قراردادِ v2 قاطی کرد.

تصمیمِ مسیرِ کاندیدا (بی‌آنکه `mobile-latest` دست بخورد): سریِ **جدا**.
`mobile.yml` اکنون `SNAPSHOT_SERIES` (پیش‌فرض `mobile-latest`) و ورودیِ
`snapshot_series` دارد؛ همان مسیر درِ بیلد به `VITE_SNAPSHOT_REMOTE` تزریق
می‌شود، پس APKِ سریِ تازه فقط سریِ خودش را می‌خواند. برایِ انتشارِ v2 لازم است
(الف) جفت‌کلیدِ واقعیِ انتشار ساخته و public آن درِ `vars.MOBILE_MANIFEST_PUBKEY`
بگذارده شود، (ب) manifest + `.sig` رویِ tagِ جدید (`mobile-latest-v2`) منتشر شود.
این دور **هیچ‌کدام منتشر نشد** و نه گامی از CI اجرا شد (NOT RUN).

## ۷) آزمون‌ها

| فرمان | نتیجه |
| --- | --- |
| `npx vitest run` (کل فرانت) | 148 پروندۀ تست، 1541 pass، 1 skip، 0 fail (46.7s) |
| `npx tsc -b` | صفر خطا |
| `vite build` موبایل | موفق؛ نسخۀ ۱٫۰٫۷۹ و کلیدِ عمومی درِ بایلد grep شد |
| `python -m py_compile` (سازنده، امضاگر، بازرس، گارد) | OK |
| `dev/mobile_manifest_sign_v1079.py` | 23 passed / 0 failed |
| `python dev/run_all_tests.py` (کل گیت‌ها) | 85 سروند: 78 OK / 7 FAIL — هر هفت قرمز بی‌ربط به این مأموریت و از پیش موجود: `chart_api_check_v95` (فایلِ `archive/legacy_static/vendor/klinecharts.min.js` درِ این worktree نیست)، `candle integrity` (به بک‌اندِ زنده با `--api` نیاز دارد ⇒ عملاً NOT RUN)، `R1/R2 housekeeping` (`market.db.lzma` درِ این worktree نیست)، `technical setups` ۳۲/۳۷، `jet` ۳۸/۱، `tape filters` ۲۱۴/۲۱۶ (دو رأیِ داده‌ای روی market.dbِ ۸ اکتبرِ همین worktree). هیچ‌کدام فایلِ این مأموریت را ایمپورت نمی‌کنند؛ گیتِ جدیدِ موبایل درِ همان اجرا `OK … 23/23` بود. |
| `scripts/build_mobile_snapshot.py` end-to-end رویِ snapshotِ مستقل | ۳ بستۀِ سالم + ۱ بستۀِ خرابِ عمدی، همه بازرسیِ مستقل |
| `tools/mobile_signed_package_e2e.mts` | 66/66 PASS + 7/7 (بی‌کلید) |
| `tools/mobile_old_client_compat_probe.mts` | 8/8 PASS |
| `gradlew` / راستی‌آزماییِ متادیتایِ APK | **BLOCKED** محلاً (JDK/SDK نیست) — درِ CI |
| `mobile.yml` درِ GitHub Actions | **NOT RUN** (هیچ workflow اجرا نشد) |

## ۸) رأی‌هایِ لازم از مالک

1. انتشارِ سریِ v2 (`mobile-latest-v2`) و جفت‌کلیدِ واقعیِ امضا — بازگردانیِ
   `mobile-latest`ِ امروز به سریِ تازه یا نگه‌داشتنش برایِ گوشی‌هایِ کهنه.
2. پاک‌سازیِ بستۀِ ردشده: الان فقط ردیفِ **همان** نامزدِ ردشده می‌رود؛ اگر
   بخواهید بعد ازِ هر چند شکستِ پیاپی یکِ جاروبِ کلی هم باشد، بگویید.
3. دکمۀِ «بازگشت به نسخۀ پیشین» درِ پنلِ 🛠: جایِ دیگری (مثلاً بنرِ قرمزِ خطا)
   هم لازم دارد؟
4. `baked_fail: 1` در بستۀِ کامل (pkg_full): یکِ اندپوینت درِ پخت خطا داد؛
   ببندش را جدا بررسی کنم؟
5. دورِ ۱۵ ثانیه‌ایِ بررسیِ پس‌زمینه (باز هم درِ هر دو نسل) — برایِ گوشیِ شما
   مناسب است یا بلندترش کنم؟
