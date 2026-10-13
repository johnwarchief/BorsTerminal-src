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


---

# دور ۵ (Stage 8) — ایمن‌سازی به‌روزرسانی آفلاین، سازگاری v1/v2 و آمادگی انتشار

مبدأ: کامیت `644c296` (دور ۴) روی همان شاخه. هیچ merge، tag، release یا
انتشاری انجام نشد و `mobile-latest` دست‌نخورده ماند.

## ۹) `baked_fail: 1` — علتِ واقعی، نه حدس

ادعایِ نخستِ من (شاخۀ «نمادِ فقط‌کدال») باطل شد، چون ستونِ نماد در `instruments`
را `ins_code` خوانده بودم؛ نماد در `l_val18` است. سنجشِ دوباره روی همان snapshot:

| جدول | ردیف‌های این نماد |
| --- | --- |
| `instruments.l_val18` | `'معيار '` (ي عربی U+064A + فاصلۀ انتهایی) — یک ردیف |
| `price_history.symbol` | `'معيار '` — ۳۶۵ ردیف |
| `financial_statements.symbol` | `'معيار '` — ۸ ردیف |
| `monthly_sales.symbol` | `'معيار '` ۳ ردیف + `'معیار'` (ی فارسی) ۱ ردیف |
| `codal_notices.symbol` | `'معيار '` ۳۹ ردیف + `'معیار'` ۱ + `'عیار'` ۳ |

علت: سازنده در `_symbols_from_screener` با `.strip()` فاصلۀ انتهایی را می‌کَند،
در حالی که رابط کاربر نماد را عیناً می‌فرستد (`useFtsCard.ts`:
`encodeURIComponent(symbol)`) و `resolvers.ts:201` کلید را از مسیرِ
decodeشده می‌سازد. پس دو چیز غلط بود: درخواستِ بی‌فاصله ⇒ ۴۰۴ ⇒ همان یک skip؛
و کلیدِ پختۀ آفلاین ≠ کلیدِ درخواستِ اجرا ⇒ کارتِ آن نماد روی گوشی خالی می‌ماند
حتی اگر بیلد سبز می‌شد. از ۹۲۲ نماد اسکرینر، دقیقاً یکی فاصلۀ اضافی دارد
(سنجیده شد، نه فرض).

رفع: سازنده نماد را عیناً نگه می‌دارد و فقط ردیفِ بی‌نماد/فقط‌فضا را می‌اندازد.
رفعِ دیگری که آزمودم و سپس پس گرفتم: خواندنِ نام شرکت از `codal_notices` باعث
می‌شد نمادِ بریده‌شده هم ۲۰۰ بگیرد — ولی با حقیقتِ دوم:
`sector='سایر'` و `revenue=473900` در برابرِ `sector='سرمايه گذاريها'` و
`revenue=0` برای رشتهٔ خام. نرمال‌سازیِ یک‌طرفه در یک سو مشکل را حل نمی‌کند،
دومین حقیقت می‌سازد. `api/fundamental.py` به وضعیت مبدأ برگشت (`git diff` خالی).

بازتولید کامل پس از رفع: `baked=4628 skip=0` — بستۀ `20261013T020546-010db36a` · gz 16٬۶۱۹٬۷۵۳ B · sha256 `010db36a26f12dcb50beaef0fc2206d44ac4cdddc52046917d12c63b3c9b20cb` · `series=mobile-latest-v2`، بازرسیِ مستقل `PASS` (امضا valid، tamper rejected، `integrity_check ok`) و کلید `fundamental/معيار ` (همان رشتهٔ خامِ فاصلهدار) در ۹۲۲ کلیدِ fundamental پیدا است. شمارندهٔ سازنده دست‌نخورده است
(ت۶ گارد) و کنترل منفی نشان می‌دهد گارد رفتارِ strip را می‌بیند (ت۳).

گارد: `dev/mobile_bake_key_parity_v1079.py` (۱۳ سنجه، ثبت‌شده در
`dev/run_all_tests.py`) + دو آزمون در `mobile-resolver.spec.ts` (کلیدِ
decodeشده = کلیدِ پخت؛ و پیام خطا نام کلیدِ خام را می‌گوید).

ماند: خودِ ذخیرۀ نماد کثیف (`'معيار '`) در لایۀ مشترکِ خوانش — رأیِ مالک.
ردیفِ D-7 در roadmap با این سنجش به‌روز شد.

## ۱۰) سریِ مستقلِ v2 و دروازۀ سری

- سازنده فیلد `series` را در manifest می‌نویسد (`--series`، پیش‌فرض
  `mobile-latest-v2`).
- کلاینت `VITE_SNAPSHOT_SERIES` را در بیلد دارد و پس از تأییدِ امضا و پیش از هر
  مصرف، سری را می‌سنجد: ناهمخوان ⇒ `series-mismatch`، بی‌سری ⇒ `series-unknown`.
  هر دو رد، نه پذیرشِ بی‌آزمون.
- CI: `SNAPSHOT_SERIES` + ورودیِ `snapshot_series` (پیش‌فرض `mobile-latest`) که
  به `VITE_SNAPSHOT_REMOTE` و `VITE_SNAPSHOT_SERIES` تزریق می‌شود. این job هیچ
  چیزی روی `mobile-latest` منتشر نمی‌کند؛ فقط می‌خواند.
- تصمیم کلید: یک کلید برای سری v2 کافی است. امضا برای این است که بستۀ دانلودیِ
  *این* کلاینت از ناشرِ *این* کلاینت باشد و public در APK مهر شده و `key_id`
  باید بخواند. سری کهنه هیچ امضایی ندارد و کلاینت کهنه هم چیزی راستی‌آزمایی
  نمی‌کند (سنجیده شد) ⇒ کلید دوم چیزی به امنیت اضافه نمی‌کند و چرخشِ بی‌دلیلِ
  کلید انتشار فقط ریسکِ از دست رفتنِ اعتماد است.
- شواهد مرورگر واقعی (بیلد `mobile-latest-v2`): `74/74 PASS` در
  `_audit/mobile_stage8_e2e.json` — شامل S18 (بستۀ سریِ دیگر با امضای معتبر ⇒
  `series-mismatch`) و S17 (manifest کهنۀ منتشرشده ⇒ `manifest-field-missing`).
- سازگاری کهنه با کاندیدای v2 دوباره اجرا شد، این‌بار با آرتیفکت واقعیِ
  منتشرشده: `tools/mobile_old_client_compat_probe.mts --first v1_live` ⇒
  `8/8 PASS` (`_audit/mobile_stage8_old_client.json`): بوت از همان gz منتشرشده
  («4627 بسته»، «تابلوی آفلاین 5865 ردیف»، «منبع: دانلود از ریلیز») و سپس
  دانلودِ کاندیدای v2 و مصرفش پس از reload. بایت‌های
  `dist_mobile/mobile_snapshot.db.gz` با digest ریلیز یکی است (`c36eb08a…`) ⇒
  آزمون روی همان دادۀ زنده انجام شد، نه کپیِ ساخته‌شده.

## ۱۱) staging، rollback و جایِ واقعیِ دکمه

- اصلاح `absCacheKey` دورِ پیش حفظ شد و در همه سناریوها دوباره سنجیده شد
  (S2–S4، S13–S16). بستۀ ردشده هم در staging نمی‌ماند (ت۲۳).
- بنر مرگبار حالا دکمۀ «بازگشت به <package_id>» دارد — فقط وقتی یک بستۀ
  فعال‌شدۀ معتبر در حافظه مانده باشد. شواهد: jsdom ت۲۷ و مرورگر واقعی S19:
  بوتِ بی‌بسته + بستۀ خراب ⇒ بنر ⇒ کلیک ⇒ pointer به نامزد معتبر ⇒ reload از
  «کشِ دستگاه» با ردیف تابلو.
- «بخش مدیریت به‌روزرسانی/نسخه‌ها» روی گوشی رسیدنی نیست. اندازه‌گیری در
  390×844: سایدبارِ موبایل نوارِ `position:fixed` با ارتفاع ۵۸px و
  `overflow:hidden` است در حالی که محتوایش ۱۴۴px می‌خواهد؛
  `[data-testid="app-update-btn"]` = `display:none` با راستۀ `(0,0,0,0)`
  (قاعدهٔ `mobile.css`: آپدیتر باینری روی اندروید بن‌بست است). با نمایان‌کردنِ
  دستی، راستۀ دکمه `y=825..865` در برابرِ `viewport=844` افتاد ⇒ بیرونِ صفحه.
  پنلی که در آن مودال ساخته بودم پس گرفته شد (کدِ مرده نمی‌گذارم) و بازگشت در
  همان دو سطحی ماند که کاربر گوشی واقعاً می‌بیند: پنل 🛠 (دور ۴) و بنر خطا
  (این دور). نشاندنِ خواستۀ شما در «مدیریت به‌روزرسانی» یک تغییرِ چیدمانِ نوارِ
  پایین می‌خواهد — رأیِ شما.

## ۱۲) کلید انتشار: وضعیت واقعی

- `~/.bors_mobile_keys` روی این ماشین وجود ندارد ⇒ نه چرخشی انجام شد نه
  بازنویسی؛ `vars.MOBILE_MANIFEST_PUBKEY` هم تنظیم نشده (شاهد CI: خطِ
  `VITE_MOBILE_MANIFEST_PUBKEY:` خالی در ران `38310343999`).
- کلیدهای `_bors_mobile_e2e_keys/{A,B}` فقط نمایشی‌اند (public در fixtureها و
  آزمون‌ها، private بیرون مخزن، هیچ‌کدام در CI تنظیم نشده).
- ابزارِ نگهداری اضافه شد: `--keygen --encrypted` با عبارت عبورِ
  `BORS_MOBILE_MANIFEST_KEY_PASS` (PKCS#8 رمزدار؛ مسیر openssl هم `-passin
  env:`). بی‌عبارت عبور ⇒ `BLOCKED` با پیامی که نام متغیر را می‌گوید نه مقدار
  رمز را؛ امضا/بررسی با کلید رمزدار آزموده شد. گارد: `31/31`.
- BLOCKED عمدی: کلید واقعی انتشار ساخته نشد. دلیل اندازه‌گیری‌شده: روی این
  ماشین نه نگهداری آفلاین/backupِ کلید خصوصی فایل‌محور را می‌توانم اثبات کنم
  نه رمزِ دیسک را؛ «روالِ نگهداری و بازیابی مشخص‌نشده» را نباید فعال کرد.
  حداقلِ باز شدن گیت: `python scripts/sign_mobile_manifest.py --keygen
  --encrypted --out-dir ~/.bors_mobile_keys` روی دستگاه خودِ مالک با عبارت
  عبور، backup آفلاین، و فقط public در `Settings → Secrets and variables →
  Actions → Variables → MOBILE_MANIFEST_PUBKEY`.

## ۱۳) Android WebView و CI

- محلی: `java` نیست؛ `ANDROID_HOME`/`ANDROID_SDK_ROOT` خالی؛ `local.properties`
  نیست؛ هیچ AVD و `emulator`/`sdkmanager` نصب نیست؛ `docker` نیست. `adb.exe` از
  platform-tools هست ولی هیچ دستگاهی متصل نیست و عمداً daemonِ adb را روشن
  نکردم (به session دیگران دست نخورد). ⇒ آزمون WebView محلی BLOCKED.
- CI: بیلد APK سبز است و متادیتای APK هم راستی‌آزمایی می‌شود — شاهد ران
  `38310343999` (۱۷ گام success، `Publish Android release` skipped):
  `version=1.0.79 · versionCode=1000079` از `frontend/package.json` و از
  `merged_manifests/debug`: `versionName=1.0.79 versionCode=1000079`. گام امضا
  هم صادقانه گزارش می‌کند: `curl: (22) 404` برای `.sig` ⇒ «بستۀ داده بی‌امضا
  است» (continue-on-error ⇒ بیلد کاندید نمی‌شکند، ولی دروازۀ انتشار همان را
  می‌بندد).
- اجرای Android WebView در CI ممکن است (runnerهای Linux از ۲۰۲۴ `/dev/kvm`
  دارند) ولی این دور انجام نشد: نیازمند workflow جدا با emulator و `adb forward
  tcp:9222 localabstract:webview_devtools_remote_<pid>` و چند رانِ بیست‌دقیقه‌ای
  تا سبز شدن است؛ چیزی که این شب قابل اثبات نبود، پس به‌جای نوشتن تستِ ناشینده
  و اعلام موفقیت، `NOT RUN` ثبت شد. راه باز کردنش رأیِ شماست: دستگاه واقعیِ خودِ
  مالک با adb و بیلد debug، یا runner خودش‌میزبان با KVM.
- آنچه Chromium ثابت می‌کند و آنچه نمی‌کند بدون تغییر: Cache API،
  crypto.subtle/Ed25519، DecompressionStream و مسیر واقعی فعال‌سازی در Chromium؛
  نه WebView اندروید، نه `CapacitorHttp` بومی.

## ۱۴) شمارش شکست‌های گیت سراسری (این دور، با شاهد)

`python dev/run_all_tests.py` روی همین worktree: ۸۵ سروند ⇒ ۷۸ OK / ۷ FAIL.
هر هفت بازسنجی شدند (نه از گزارش قدیمی):

| گیت سرخ | هنوز سرخ؟ | از تغییرات این مأموریت؟ | علت اندازه‌گیری‌شده |
| --- | --- | --- | --- |
| `chart_api_check_v95` | بله | نه | `archive/legacy_static/vendor/klinecharts.min.js` در این worktree نیست |
| `technical setups three-state` | بله (۳۲/۳۷) | نه | گیت منطق/داده فنی روی بانک همین worktree |
| `Round J: jet` | بله (۳۸/۱) | نه | رأی «None ≠ False» در موتور فنی |
| `candle integrity + published-TSETMC parity` | بله | نه | خودِ گیت: «به بک‌اند زنده با `--api` نیاز دارد» ⇒ عملاً NOT RUN |
| `R1/R2 housekeeping` | بله | نه | `market.db.lzma not found` در این worktree |
| `tape filters: five formulas` | بله (۲۱۴/۲۱۶) | نه | دو رأی داده‌ای tape_history همین بانک |
| `mobile_manifest_sign_v1079` (گیت خودِ این مأموریت) | محلی ۳۱/۳۱ سبز، در CI سرخ (`0 pass / 0 fail`) | **بله** | باید علتش را در CI قطعی کنم؛ این تنها آیتمِ سرخی است که مالِ این مأموریت است — در دور بعد |

گیت‌های دیگری که فقط در CI سرخ‌اند (`screener<->card parity`،
`scan_symbol==bulk_scan`، `codal logic F-01..F-05`، `incremental sync`،
`one canonical period`، `board history windows`، `hot state`) همان D-4 هستند:
schemaشان از `market.db` فقط‌خواندنیِ untracked می‌آید.

## ۱۵) Release Readiness

| شرط | وضعیت |
| --- | --- |
| بستۀ کامل تعیین‌تکلیف شده (`baked_fail`) | PASS — علت واقعی یافت و رفع شد؛ `4628/0` بازتولید شد |
| سازگاری v1/v2 | PASS — هر دو جهت با آرتیفکت واقعیِ منتشرشده اجرا شد |
| امنیت کلید انتشار | BLOCKED — زیرساخت و کلید رمزدار آماده؛ کلید واقعی به سبب نبودِ روال نگهداری ساخته/فعال نشد |
| rollback قابل دفاع | PASS محلی و مرورگر؛ در WebView: NOT RUN |
| شکاف WebView | BLOCKED (محلی) / NOT RUN (CI) با شواهد و حداقلِ راه باز شدن |
| گیت‌های این مأموریت | PASS — vitest: 148 پرونده / 1547 pass / 1 skip / 0 fail؛ `tsc -b`: ۰ خطا؛ `npx eslint src`: ۰ خطا (یک `no-irregular-whitespace` درِ همان regexِ BOMِ `manifestSignature.ts` گرفته شد و با escape جایگزین شد — بدونِ تغییرِ رفتار: ۶۸/۶۸ آزمون موبایل سبز)؛ `vite build`: موفق و نسخه/کلید/سری درِ بایلد grep شد؛ `py_compile`: OK؛ گارد امضا ۳۱/۳۱؛ گارد هم‌کلیدی ۱۳/۱۳؛ پروب Chromium ۷۴/۷۴؛ پروب کلاینت کهنه ۸/۸ |
| انتشار | NOT RUN — مجاز نبود |

---

# دور 6 (مرحلۀ انتشار) — چرا منتشر نشد، و چه چیزی درست شد

مبدأ: کامیت `e20300b` روی همان شاخه. خواستۀ دور: «اگر همهٔ پیش‌نیازها برقرار
است منتشر کن، وگرنه منتشر نکن و مانع را دقیق بنویس». **انتشار انجام نشد** — و
این از سرِ احتیاطِ کلی نبود: سه پیش‌نیازِ ضروری، هر سه با شاهدِ زنده، برقرار
نیستند.

## 16-الف) شمارشِ پیش‌نیازها با شاهد (هیچ‌کدام از روایتِ دورهایِ پیشین)

| پیش‌نیاز | وضعیت | شاهدهٔ همین دور |
| --- | --- | --- |
| کلیدِ خصوصیِ انتشار، رمزدار و پشتیبان‌گیری‌شده | **MISSING** | `~/.bors_mobile_keys` وجود ندارد (`ls: cannot access`). تنها چیزی که رویِ این ماشین هست دو جفت‌کلیدِ **نمایشی** در `Desktop/_bors_mobile_e2e_keys/{A,B}` است، هر دو **بی‌رمز** (119 بایت، `-----BEGIN PRIVATE KEY-----`). پشتیبانِ هیچ‌کدام گرفته نشده. |
| `vars.MOBILE_MANIFEST_PUBKEY` درِ CI | **NOT SET** | لاگِ رانِ `38320593444` (تازۀ‌ترینِ mobile-apk، 2026-10-12T23:08Z): سطرِ `VITE_MOBILE_MANIFEST_PUBKEY:` **تهی**. تنظیمِ آن ازِ این نشست هم ممکن نیست: توکنِ `gh` درِ scopesِ `repo, workflow, read:org, gist` است و `/repos/…/variables` را 404 می‌دهد (needs admin). |
| امضایِ بستۀ دادۀ موجود | **MISSING** | همان لاگ: گامِ «Verify the data package signature» با `curl: (22) The requested URL returns error 404` رویِ `mobile_snapshot.db.meta.json.sig` رد شد ⇒ «بستۀ داده بی‌امضا است». `gh release view mobile-latest-v2 --repo johnwarchief/BorsTerminal-src` ⇒ `release not found`. |
| گیت‌هایِ خودِ مأموریت درِ CI | **RED → FIXED (درِ این دور)** | گاردِ `mobile data manifest is signed` درِ رانِ `guards` شمارهٔ `38322487153` با `rc=1 | 0 pass / 0 fail` سرخ بود (علتِ واقعی درِ 16-ب). پس ازِ رفع: 51 سنجه، درِ هر دو پیکربندیِ backend سبز. |
| سازگاریِ نسخۀ APK و versionCode | PASS | لاگِ همان ران: `منبعِ واحدِ نسخه: frontend/package.json → 1.0.79 (versionCode 1000079)` و گامِ «Verify the APK metadata» از `merged_manifests` همان را خواند. |
| rollback و نگهداشتِ دو بستۀ سالم | PASS محلی/Chromium، **NOT RUN درِ WebView** | دورهایِ 4 و 5 (74/74 درِ `_audit/mobile_stage8_e2e.json`). |
| آزمونِ Android WebView | **NOT RUN** | محلی: `java` نیست، `ANDROID_HOME`/`ANDROID_SDK_ROOT` تهی، `local.properties` نیست، هیچ AVD/emulator/docker نصب نیست. درِ CI هیچ job ایمولاتور نیست. |

نتیجه: منتشر نکردم. منتشرکردن با این وضعیت یعنی یا APKی که رویِ گوشی هیچ‌وقت
دادهٔ تازه نمی‌گیرد (بی‌کلید درِ باندل)، یا گذاشتنِ کلیدِ نمایشی جایِ کلیدِ
انتشار — که هر دو دقیقاً همان چیزی است که دروازۀ `mobile.yml` منع می‌کند.

## 16-ب) علتِ واقعیِ سرخیِ گاردِ امضا درِ CI (و چهار باگِ دیگرِ همان خانواده)

گاردِ `dev/mobile_manifest_sign_v1079.py` رویِ این ماشین 31/31 سبز بود و درِ CI
`rc=1 | 0 pass / 0 fail` (یعنی **پیش ازِ اولین سنجه** می‌شکست). علتِ اندازه‌گیری‌شده،
درِ لاگِ ران:

```
subprocess.CalledProcessError: Command '['openssl', 'pkey', '-in',
'.../mobile_manifest.key.pub', '-pubout', '-outform', 'DER']' returned non-zero exit status 1
```

`openssl pkey -in` کلیدِ **خصوصی** می‌خواهد؛ برایِ PUBLIC KEY بایتِ `-pubin`
لازم است («Could not find private key of key»). درِ `requirements.txt` هیچ
`cryptography` نیست، پس runner همین شاخه را می‌رفت، ولی رویِ ماشینِ من
`cryptography 46.0.7` نصب است و آن شاخه **هرگز اجرا نمی‌شد** — همان الگویِ
شناختهٔ «شاخۀ مرده‌ای که fixture پنهانش می‌کند»، این بار درِ مسیرِ انتشار.

| # | باگ | رفع |
| --- | --- | --- |
| 1 | خواندنِ DERِ کلیدِ عمومی با زیررویه، و آن هم با پرچمِ غلط | `_spki_der_from_pem()`: PEMِ `PUBLIC KEY` با stdlib بازخوانده می‌شود (base64ِ بدنه)؛ بی‌هیچ ابزارِ بیرونی، با نتیجۀ یکسانِ ویندوز/لینوکس. `raw_public32` هم از یکِ ثابتِ تنها (`ED25519_SPKI_PREFIX`) می‌خواند. |
| 2 | `openssl genpkey` گزینهٔ `-cipher` **ندارد** ⇒ `--keygen --encrypted` رویِ هر ماشینِ بی‌`cryptography` می‌شکست (`genpkey: Extra (unknown) options: "cipher"`) | رمزگذاری با `openssl pkcs8 -topk8 -v2 aes-256-cbc -passout env:…` رویِ همان PKCS#8، و سپس `pkey -pubout -passin env:…`. |
| 3 | openssl بی‌passphrase **درنگ** می‌کرد (دو `openssl.exe` معلق رویِ این ماشین دیدم) | `_run()` حالا `stdin=DEVNULL` و `timeout=120` دارد، و `_require_passphrase_if_encrypted()` پیش ازِ هر تماسِ openssl پیامِ خودِ ما را می‌دهد. هیچ سوالی ازِ TTY پرسیده نمی‌شود. |
| 4 | «باندلِ خراب» با پیامِ «رمزِ غلط» گزارش می‌شد | اولِ اول تمامیت سنجیده می‌شود (اثرِ درونِ باندل + فایلِ `.sha256`) و درِ شکست **هیچ رمزگشایی‌ای امتحان نمی‌شود**؛ `_load_private()` سه حالتِ «رمز ندارد / عبارت نیست / عبارت غلط است» را جدا می‌کند. |
| 5 | `restore()` با `ValueError` خام می‌ترکید و باندلِ خراب را رویِ دیسک می‌نوشت | پیش ازِ هر نوشتن می‌سنجد؛ باندلِ ردشده هیچ پوشه‌ای نمی‌سازد؛ رویِ کلیدِ موجود نمی‌نویسد. |

سنجشِ رفع، درِ **هر دو** پیکربندی: `dev/ci_parity_harness.py` (همین دور اضافه
شد) ماژولِ `cryptography` را هم درِ فرایندِ والد و هم درِ همهٔ زیرروندها (همان
CLI که گارد با subprocess صدا می‌زند) مسدود می‌کند — بی‌بخشِ زیررونده، آزمون‌هایِ
CLI ازِ شاخۀ cryptography رد می‌شدند و باگِ 2 هرگز دیده نمی‌شد.

| پیکربندی | پیش ازِ رفع | پس ازِ رفع |
| --- | --- | --- |
| `python dev/mobile_manifest_sign_v1079.py` (این ماشین) | 31 passed / 0 failed | **51 passed / 0 failed** |
| `python dev/ci_parity_harness.py` (بدونِ cryptography، مثلِ runner) | کرش: `0 pass / 0 fail` | **51 passed / 0 failed** |

## 16-پ) آنچه برایِ بسته‌شدنِ گیتِ کلید ساخته شد (نه ساختنِ خودِ کلید)

مانعِ اصلی نبودِ *کلید* نبود، نبودِ *روالِ نگهداری* بود («روالِ نگهداری و
بازیابیِ مشخص‌نشده را نباید فعال کرد»). پس سه فرمانِ تازه به
`scripts/sign_mobile_manifest.py` اضافه شد که آن روال را اثبات‌پذیر می‌کند:

- `--backup --key <priv> --backup-dir <dir>`: باندلِ base64ِ **متن‌محور** (بیرونِ
  مخزن، `0600`) با `key_id`، `encrypted` و `body_sha256` **درونِ خودش** + فایلِ
  `.sha256` کناری. باندلِ کلیدِ بی‌رمز رد می‌شود (پرچمِ `--allow-unencrypted` فقط
  برایِ کلیدِ نمایشی است)، و مقصدِ داخلِ مخزن رد می‌شود.
- `--verify-backup <bundle>`: تمامیت ← بازگردانی درِ حافظه ← key_id ← **چالشِ
  امضا/بررسی** با `bors_minisign` (یعنی «این فایل هست» با «این کلید کار می‌کند»
  یکی نمی‌شود). `rc=0` فقط برایِ `verdict: PASS`، پس درِ اسکریپتِ نگهداری گیت است.
- `--restore <bundle> --restore-out <dir>`: اول می‌سنجد، بعد می‌نویسد؛ public را
  از خودِ کلیدِ بازگردانده می‌سازد و هم‌انگشتی‌اش را با باندل می‌سنجد؛ و رشته‌ای
  که باید درِ `vars.MOBILE_MANIFEST_PUBKEY` بنشیند (`expect_in_ci_var`) را چاپ
  می‌کند.

آزمون‌هایِ 27 تا 37 درِ همان گارد (14 سنجۀ تازه) این مسیر را می‌سنجند، با شش
کنترلِ منفی: کلیدِ بی‌رمز، باندلِ یک‌بایت‌خورده (دلیلِ شکست باید «checksum» باشد
نه «رمزِ غلط»)، باندلِ گم‌شده و بی‌عبارتِ عبور (پیامِ BLOCKED، بی‌traceback)،
مقصدِ داخلِ مخزن، و تکرارنشدنِ خودِ عبارتِ عبور درِ هیچ خروجی.

## 16-ت) حلقۀ گمشدۀ انتشار: ناشرِ سریِ امضاشده

درِ مخزن **هیچ** مسیری برایِ *انتشارِ* سریِ v2 نبود: `mobile.yml` بستۀ داده را
فقط می‌خواند (`curl …/releases/download/${SNAPSHOT_SERIES}/…`)،
`market-data.yml` سریِ دسکتاپ (`data-latest`) را می‌فرستد، و سازندۀ بستۀ موبایل
`market.db` لازم دارد که درِ CI نیست. «انتشار v2» یعنی چند دستورِ دستیِ
فراموش‌شدنی رویِ مخزنِ عمومی — و یکِ `--clobber` اشتباه رویِ `mobile-latest`
قطعِ به‌روزرسانیِ همۀ گوشی‌هایِ کهنه است. `scripts/publish_mobile_series.py`
همان حلقه است، fail-closed:

| دروازۀ داخلی | رفتاری که سنجیده شد |
| --- | --- |
| سریِ هدف ≠ `mobile-latest`/`data-latest` | `--series mobile-latest` ⇒ rc=3، `ready_to_publish: false` |
| manifest با بایت‌هایِ دیسک بخواند | بستۀ **منتشرشدۀِ امروز** (`dist_mobile/`، 111 بایت، چهار کلید) ⇒ سه سنجۀ سرخ: `manifest-series` (بی‌series)، `manifest-gz_sha256` (بی‌hash)، `manifest-lf-only` (**CRLF**) ⇒ rc=3 |
| امضا + بازبینیِ مستقل | با کلیدِ رمزدار رویِ بستۀ v2 (`20261013T020546-010db36a`) ⇒ `ready_to_publish: true`، `signature_ok: true`، `inspector_ok: true`، و **هیچ چیزی به GitHub نرفت** (dry-run پیش‌فرض) |
| `--expect-key-id` (کلیدِ بیلد ≠ کلیدِ var) | ⇒ rc=4، دلیل: «APK این بستۀ را نمی‌پذیرد» |
| `--yes` بی‌آمادگی | ⇒ rc=4 با پیامِ دروازۀ انتشار؛ `gh` هرگز صدا زده نمی‌شود |
| پس ازِ انتشارِ واقعی | سه فایل ازِ **همان URL که گوشی می‌خواند** بازخوانده، digest مقایسه و امضایِ زنده بررسی می‌شود («upload rc=0» دلیلِ موفقیت نیست) |

شاهدِ بی‌تغییرِ وضعیتِ عمومی: `gh release view mobile-latest-v2` ⇒ `release not
found` (پس ازِ همۀ این اجراها)، و `mobile-latest` دست‌نخورده با همان چهار asset.

## 16-ث) سخت‌گیریِ دروازۀ انتشار درِ `mobile.yml`

- گامِ `Publish Android release` حالا **خودش** هم سه شرط را بازمی‌خواند (کلیدِ
  عمومی تنظیم‌شده، `signed=verified`، سریِ هدف ≠ سری‌هایِ کهنه). پیش ازِ این فقط
  به `exit 1` گامِ «Publish gate status» و به **ترتیبِ گام‌ها** وابسته بود؛ یکِ
  جابه‌جاییِ بعدی یا `if: always()` گذاشتنش، انتشارِ بی‌کلید را ممکن می‌کرد.
- متنِ ریلیز دروغِ کوچکی داشت: «snapshot داده: mobile-latest» ثابت نوشته شده بود
  در حالی که بستۀ خوانده‌شده `$SNAPSHOT_SERIES` است. حالا همان متغیر چاپ می‌شود.
- هر 17 گامِ این job با `bash -n` و YAML-parse بررسی شد (0 خطا).

## 16-گ) آنچه مالک باید بگذراند (انتشار ازِ این نشست انجام نمی‌شود)

1. رویِ دستگاهِ خودِ مالک، با عبارتِ عبوری که فقط او می‌داند و **نگهداری‌اش مالِ
   خودِ اوست**:
   ```bash
   export BORS_MOBILE_MANIFEST_KEY_PASS='…'
   python scripts/sign_mobile_manifest.py --keygen --encrypted --out-dir ~/.bors_mobile_keys
   python scripts/sign_mobile_manifest.py --backup --key ~/.bors_mobile_keys/mobile_manifest.key
   python scripts/sign_mobile_manifest.py --verify-backup <مسیرِ باندل>   # rc=0 لازم است
   ```
   باندل را رویِ دو مدیایِ مستقلِ آفلاین بگذارد و بازیابی را **یک بارِ واقعی**
   با `--restore --restore-out <پوشۀ خالی>` بیازماید (همان `expect_in_ci_var` را
   برمی‌گرداند).
2. درِ `johnwarchief/BorsTerminal-src → Settings → Secrets and variables → Actions
   → Variables`: `MOBILE_MANIFEST_PUBKEY` = همان رشته (این ازِ این نشست ممکن نبود:
   توکنِ `gh` scopeِ admin ندارد و `/variables` را 404 می‌دهد).
3. ساختِ بستۀ تازه و انتشارِ سری:
   ```bash
   python scripts/build_mobile_snapshot.py --require-signature --series mobile-latest-v2
   python scripts/publish_mobile_series.py --dir dist_mobile            # اول خشک
   python scripts/publish_mobile_series.py --dir dist_mobile --yes \
       --key ~/.bors_mobile_keys/mobile_manifest.key --expect-key-id <kidِ var>
   ```
4. سپس `Run workflow` رویِ `mobile.yml` با `snapshot_series=mobile-latest-v2` و
   `publish=true`. تا گامِ 2 و 3 انجام نشده باشند، همان‌جا `BLOCKED` می‌خورد —
   که خواستۀ همین دور است، نه نقص.

## 16-ح) Release Readiness — شمارشِ دوباره

| شرط | وضعیتِ این دور |
| --- | --- |
| مانعِ انتشارِ v2 دقیق و مستند | **COMPLETE & PROVEN** (سه جدولِ بالا، با شمارۀ ران‌ها و خروجیِ فرمان‌ها) |
| گیتِ CIِ خودِ مأموریت (`mobile data manifest is signed`) | **COMPLETE & PROVEN** محلی + CI-parity: 51/51 درِ هر دو پیکربندی (پیش ازِ رفع: کرشِ `0 pass / 0 fail`) |
| روالِ نگهداریِ کلید (backup/verify/restore + کنترلِ منفی) | **IMPLEMENTED, LOCALLY PROVEN** — با کلیدِ نمایشیِ رمزدار سنجیده شد؛ کلیدِ واقعی ساخته نشده (کارِ مالک) |
| حلقۀ انتشارِ سریِ امضاشده | **IMPLEMENTED, LOCALLY PROVEN** — dry-run و چهار دروازۀ ردِ واقعی و یکِ dry-runِ آماده سنجیده شد؛ `--yes` هرگز اجرا نشد و چیزی منتشر نشد |
| سخت‌گیریِ دروازۀ `mobile.yml` + صحتِ متنِ ریلیز | **IMPLEMENTED, UNVERIFIED IN CI** (YAML/bash سنجیده شد؛ گامِ publish عملاً درِ CI اجرا نشد چون کلید نیست) |
| Android WebView | **NOT RUN** (محلی BLOCKED: بی‌JDK/SDK/emulator؛ CI: بی‌job ایمولاتور) |
| انتشارِ واقعی | **NOT RUN — مجاز نبود** (سه پیش‌نیازِ ضروری برقرار نیست) |

