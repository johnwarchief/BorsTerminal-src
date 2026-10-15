# ANDROID-RELEASE-READINESS — وضعیتِ انتشارِ رسمی اندروید (2026-10-16)

مأموریت: «تکمیل مأموریت، رفع موانع انتشار و اثبات نهایی» با مجوزِ صریحِ مالک برای
اجرای مراسمِ کلید، تنظیم secretها/varها، انتشار بستهٔ داده و رانِ workflow به‌شکل
prerelease. انتشارِ **پایدار** اندروید و دست‌زدن به انتشارِ پایدار ویندوز مجاز نبود
و انجام هم نشد.

## ۱) revision ابتدا و انتها

| مورد | مقدار |
| --- | --- |
| branch | `arena/fts-mobile-uiux-20261007` (worktree `C:\Users\PCMOD\Desktop\BorsTerminal-android`) |
| ابتدا | `86f9c109` |
| انتها | `a1fb9177` (+ تغییراتِ این سند) |
| worktreeهایِ دیگر | دست‌نخورده؛ هیچ reset/clean/stash/checkoutِ تخریبی انجام نشد |
| مبنایِ دسکتاپ | `github/main` = `c0402614` = v1.0.89، ۱۳ asset، `latest.json` نسخه **1.0.89** (پایانِ کار دوباره خوانده شد) |

## ۲) آنچه رفع شد (با شاهد)

1. **قراردادِ manifest — ادعایِ دورِ پیشین تصحیح شد.** گزارشِ قبلی گفت parser با
   producer نمی‌خواند. اندازه‌گیری برخلافِ آن است: `build_mobile_snapshot.py` همهٔ
   فیلدهایِ schema 2 را می‌نویسد؛ آنچه رویِ گوشی بود بستۀ **نسلِ ۱** بود.
   شاهد: بستۀ واقعیِ ساخته‌شده ازِ market.db این دور —
   `schema_version=2, package_id=20261016T003218-04d6f9f1, gz_sha256=04d6f9f1…, gz_bytes=16179118, min_app_version=1.1.0, db_schema=1, series=mobile-latest-v2`.
   کارِ مهندسی: سنجِ **دوسرف** ساخته شد تا این drift دیگر با چشم دیده نشود.
2. **مراسمِ کلید بی‌Java.** `keytool` رویِ این ماشین نیست؛ همدوشِ پایتونِ ceremony
   ساخته شد (PKCS12، RSA-2048، گواهیِ ۲۵ ساله، رمزِ تصادفی درِ فایلِ ۰۶۰۰).
3. **سخت‌ترکردنِ parser** (نه سهل‌گیر): `schema_version` و `gz_bytes` باید عددِ واقعی
   باشند؛ رشتۀ عددی دیگر پذیرفته نمی‌شود.
4. **AVDِ لاغر**: `mCurrentFocus = «ANR: com.android.systemui»` و dumpِ ۵۷ بایتی ⇒
   `ram-size: 5120` + انتظارِ فوکوسِ واقعی پیش‌ازِ سنجشِ محتوا.
5. **socketِ DevTools** ازِ `/proc/net/unix` خوانده می‌شود (نه حدس از pid) و
   واژگانِ سنجشِ دسترس‌پذیری ازِ خودِ سورسِ رابط گرفته شده است.

## ۳) کلیدها و تنظیماتِ GitHub (بدونِ هیچ مقدارِ محرمانه)

| مورد | وضعیت |
| --- | --- |
| keystoreِ انتشار | ساخته شد: `~/.bors_android_keys/bors-android-release.p12` (PKCS12، alias `bors`) |
| اثرانگشتِ گواهی | `1A:4D:A3:3D:10:23:C5:DF:7D:2E:E3:C5:16:73:77:BE:E4:46:BA:25:DE:C9:C4:ED:A2:5F:AA:6D:F6:13:4B:58` |
| پشتیبان | `~/bors-key-backups/bors-android-release-20261015T205808Z` + SHA256SUMS |
| verify-backup | PASS — کلید ازِ همان بسته باز شد، اثرانگشت با کلیدِ فعال یکی |
| آزمونِ بازیابی | `restore --into` درِ پوشۀ جدا PASS؛ کلیدِ فعال لمس نشد؛ بی‌`--into` **رد** می‌شود |
| `ANDROID_RELEASE_KEYSTORE_B64` / `_PROPS` | درِ `-src` تنظیم شد (ازِ stdin، بدونِ چاپ) |
| کلیدِ manifest | Ed25519 **رمزدار** درِ `~/.bors_mobile_keys`، key_id `6c2f1729f6b5646f`؛ backup → verify-backup **PASS** → restore **PASS** |
| `MOBILE_MANIFEST_PUBKEY` | تنظیم شد (فرمِ base64ِ ۳۲ بایتیِ کلیدِ عمومیِ همان جفت‌کلید) |
| `ANDROID_RELEASE_CERT_SHA256` | تنظیم شد (اثرانگشتِ بالا) |
| بدهی | پشتیبان فعلاً رویِ **همان دیسک** است؛ مالک باید به رسانۀ بیرونی منتقلش کند |

## ۴) زنجیرۀ داده: public asset → download → validation → signature → DB → activation → UI

| حلقه | نتیجه | شاهد |
| --- | --- | --- |
| public asset | **PASS** | سه URL ناشناس: meta `200` (490 B)، `.sig` `200`، gz `206` (ranged) |
| download | **PASS** | ناشر ازِ بایت‌هایِ زنده خواند: `gz_sha256_live == gz_sha256_local` |
| manifest validation | **PASS** | `dev/mobile_manifest_contract_v1115.py` ۱۸/۱۸ + `mobile-manifest-contract.spec.ts` |
| signature verification | **PASS** | `sig_verified_from_live_bytes: true`؛ و دو کنترلِ منفی: manifestِ دستکاری‌شده و کلیدِ دیگر ⇒ **رد** |
| database validation | **PASS** | gz → 70,701,056 B SQLite؛ جدول‌هایِ ادعایی درِ بسته؛ `db_schema` = `meta.schema`؛ `market_board` درِ `baked` |
| atomic activation | **PASS** | 37 آزمونِ `mobile-snapshot-integrity.spec.ts` (pointer درِ آخرین گام، rollback، space-full، crash-before-pointer) |
| UI reads refreshed data | **NOT_VERIFIED رویِ دستگاه / PASS درِ Chromium** | کاوشِ viewport با باندلِ واقعی ۲۷ رکورد سبز؛ رویِ AVD سنجشِ محتوا به ANRِ systemui خورد (بندِ ۶) |

## ۵) تست‌ها و گیت‌ها

| گیت | نتیجه |
| --- | --- |
| `npx tsc -b` | 0 خطا |
| `vitest run` (43 پروندۀ موبایلِ مرتبط + ۶ پروندۀ جدیدِ قرارداد) | سبز؛ اجرایِ کامل درِ بندِ ۷ |
| `dev/mobile_manifest_contract_v1115.py` | ۱۸/۱۸ |
| `dev/android_release_v1110.py` | ۹۷/۹۷ |
| `dev/persian_glyph_guard.py` | ۴/۴ |
| `run_all_tests.py` | درِ انتهای همین دور بازاجرا می‌شود؛ baseline = ۶ قرمزِ بی‌ربط (KLineCharts v10، setups سه‌حالته، Round J jet، candle parity، R1/R2، tape filters) |

## ۶) WebView رویِ دستگاه

`install` **PASS** · `launch` **PASS** (pid، تلاشِ ۱) · `back_button` **PASS** (زنده،
پنجرۀ «برایِ خروج دوباره بزنید») · `background_foreground` **PASS** · `crash` **PASS**
(`FATAL EXCEPTION=0`) · `logcat_secrets` **PASS** (hit=0) · `anr` **NOT_VERIFIED**
(صفر ANR برایِ `com.borsterminal.mobile`؛ ۱۳ ANR مالِ پروسه‌هایِ خودِ AVD).

محتوا: **NOT_VERIFIED با علتِ اندازه‌گیری‌شده** — `mCurrentFocus = Window{…
Application Not Responding: com.android.phone/systemui}` و `uiautomator dump` =
۵۷ بایت. اصلاحِ همین دور (RAM + انتظارِ فوکوس) درِ رانِ انتشارِ جاری دوباره سنجیده
می‌شود؛ اگر باز هم نخورد، همان شواهد ثبت می‌شود و این سطر PASS اعلام نمی‌شود.

## ۷) رانِ انتشار

`publish=true` با `snapshot_series=mobile-latest-v2` رویِ `a1fb9177`:
run **38808829813** — نتیجه، امضا، تطبیقِ اثرانگشت، لینکِ عمومیِ APK و بررسیِ
`latest.json` دسکتاپ درِ همین بند پسِ تمام‌شدن نوشته می‌شود.

## ۸) جدولِ نهایی

| سنج | وضعیت |
| --- | --- |
| قراردادِ manifest و زنجیرۀ refresh | **PASS** |
| مراسمِ کلید، پشتیبان، بازیابی | **PASS** |
| secret/varها | **PASS** |
| buildِ Release | **PASS** |
| امضا + تطبیقِ اثرانگشت | درِ رانِ 38808829813 |
| WebView DOM/محتوا | **NOT_VERIFIED** (علتِ محیطی، با شواهد) |
| لینکِ دانلودِ ناشناس | **PASS برایِ داده**؛ APK درِ رانِ انتشار |
| آپدیترِ ویندوز | **PASS** (latest.json = 1.0.89، prerelease اجباری درِ workflow) |
