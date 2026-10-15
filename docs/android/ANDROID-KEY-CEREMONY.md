# مراسمِ کلیدِ انتشارِ اندروید — فقط این چند فرمان، رویِ دستگاهِ خودتان

این تنها چیزی است که بینِ کدِ فعلی و یکِ Releaseِ واقعیِ اندروید فاصله گذاشته
است. هیچ‌کدام ازِ مراحلِ پایین را نمی‌توان ازِ این ماشین انجام داد: کلیدِ خصوصی
باید رویِ دستگاهِ شما متولد شود و پشتیبانش بیرونِ این ماشین بماند.

## صفر) یک بلاکرِ بزرگ‌تر ازِ کلید: مخزنِ src خصوصی شده است

در 2026-10-15T16:45:41Z `johnwarchief/BorsTerminal-src` به `private` رفت (API
همین را گزارش می‌دهد). دو پیامد دارد که هیچ‌کدام با کلیدِ امضا حل نمی‌شود:

1. **APK منتشرشده دانلودنشدنی است**: tag و release اندروید رویِ همان مخزن
   ساخته می‌شود، و `releases/download/…` بی‌اعتبارنامه 404 می‌دهد.
2. **گوشی داده نمی‌گیرد**: `frontend/src/shared/api/local/localData.ts` آدرسِ
   بستۀ داده را همان‌جا می‌خواند و گوشی هیچ tokenی ندارد.

شاهدِ مقایسه‌ای: رانِ موفقِ 2026-10-12T23:11:31Z ازِ همان URL بی‌اعتبارنامه
`bytes=16179264` گرفت؛ امروز همان URL 404 می‌دهد و `GET
/repos/…/releases/assets/<id>` با token هنوز 200 است. بیلدِ CI را به `gh release
download` بردم (اعتبارنامۀ کارفرما) تا مسیرِ ساختِ APK باز باشد، اما مسیرِ
گوشی را هیچ codeای نمی‌تواند باز کند. مالک یکی از این دو را باید انتخاب کند:

```bash
# الف) همان‌جا که بود عمومی بماند (سورسِ برنامه دوباره دیدنی می‌شود)
gh repo edit johnwarchief/BorsTerminal-src --visibility public

# ب) خصوصی بماند، ولی «چیزی که گوشی می‌خواند» به مخزنِ عمومی برود
#    (ریلیز اندروید + سریِ داده → johnwarchief/BorsTerminal؛ فقط --repo عوض
#     می‌شود: SERIES_REPO درِ mobile.yml و --repo درِ publish_mobile_series.py)
```

گزینهٔ «ب» دارایی‌های ویندوز و `latest.json` دسکتاپ را دست نمی‌زند؛ گزینهٔ «الف»
هیچ codeای لازم ندارد. تا یکی از این دو انجام نشود، انتشارِ رسمیِ اندروید
ممکن نیست — حتی با کلیدِ آماده.

## چیزی که الان موجود است (لازم نیست دوباره بسازید)

| چیز | کجا |
| --- | --- |
| گیتِ سه‌قفلۀ انتشار (بی‌امضا منتشر نمی‌شود) | `.github/workflows/mobile.yml` → `Publish gate status`، `Publish…` |
| ردِ debug keystore درِ Gradle | `frontend/android/app/build.gradle` (خطایِ BORS-SIGN) |
| اسکریپتِ مراسمِ کلید + پشتیبان/بازگردانی | `scripts/android_release_key_ceremony.sh` |
| قراردادِ نامِ secretها و قالبِ props | گاردِ `dev/android_release_v1110.py` سنجه‌های A59…A66 |
| امضایِ بستۀ داده (کلیدِ مجزای manifest) | `scripts/sign_mobile_manifest.py` (`--keygen/--backup/--verify-backup/--restore`) |
| ناشرِ سریِ دادۀ v2 | `scripts/publish_mobile_series.py` |
| مادۀ آزمونِ ارتقا رویِ شبیه‌ساز | `tools/android_upgrade_matrix.sh` + jobِ `upgrade-matrix-on-device` |

## ۱) دو ابزار لازم

- **JDK 17 یا 21** (برایِ `keytool`) — همان JDK که Android Studio دارد کافی است؛
  `keytool -version` باید کار کند.
- **GitHub CLI** با نشستِ `gh auth login` رویِ حسابی که `repo` دارد (همان که
  coverageهای مخزن `johnwarchief/BorsTerminal-src` را می‌نویسد).

## ۲) کلیدِ APK — یک‌بار، بیرونِ دیدِ هر لاگ

```bash
cd <مسیرِ چیدمانِ BorsTerminal-android>
bash scripts/android_release_key_ceremony.sh keygen
```

- ازِ شما رمزِ keystore پرسیده می‌شود (بدونِ پیش‌نمایش، و به هیچ فرمانی
  نمی‌نشیند). همان را برایِ کلیدِ خصوصی بزنید مگر اینکه چیزِ دیگری بخواهید.
- اگر کلیدِ از پیش موجود باشد، اسکریپت **رد می‌کند**: کلیدِ جدید به‌جای
  کلیدِ انتشارِ قبلی ساخته نمی‌شود.
- خروجیِ آخر، اثرانگشتِ SHA-256ِ گواهی است. آن را یادداشت کنید؛ باید با
  `APK_CERT_SHA256` درِ متنِ ریلیزِ ساخته‌شده برابرخ کند.

## ۳) پشتیبان، و *آزمونِ* پشتیبان

```bash
bash scripts/android_release_key_ceremony.sh backup --to /media/usb/bors-keys
bash scripts/android_release_key_ceremony.sh verify-backup --from /media/usb/bors-keys/bors-android-release-<stamp>
```

`verify-backup` SHA256 را می‌سنجد و کلید را ازِ **خودِ بسته** بازمی‌خواند — یعنی
اثبات می‌کند که بازگردانی کار می‌کند، نه اینکه یکِ کپی وجود دارد. USB را جایِ
دومی نگه دارید: گم‌شدنِ این کلید = از دست رفتنِ توانِ ارتقایِ همهٔ گوشی‌ها.

## ۴) دو secret درِ مخزن (بدونِ چاپِ هیچ مقدار)

```bash
bash scripts/android_release_key_ceremony.sh publish-secrets
gh secret list --repo johnwarchief/BorsTerminal-src   # فقط نام‌ها: ANDROID_RELEASE_KEYSTORE_B64, ANDROID_RELEASE_KEYSTORE_PROPS
```

`PROPS` دقیقاً سه سطر است: `storePassword` / `keyAlias` / `keyPassword`.
`storeFile` را workflow خودش می‌نویسد — اگر آن را درِ secret بگذارید، A64 قرمز
می‌شود.

## ۵) کلیدِ عمومیِ manifest (ریشۀ اعتمادِ بستۀ داده)

```bash
python scripts/sign_mobile_manifest.py --keygen --out-dir ~/.bors_mobile_keys
python scripts/sign_mobile_manifest.py --backup --key ~/.bors_mobile_keys/... --out-dir /media/usb/bors-keys
gh variable set MOBILE_MANIFEST_PUBKEY --repo johnwarchief/BorsTerminal-src \
  --body "<خروجیِ expect_in_ci_var ازِ مرحلهٔ --keygen/--backup>"
```

بی‌این متغیر، بیلد ساخته می‌شود ولی گیتِ انتشار می‌بندد («APK بی‌ریشۀ اعتماد
منتشر نمی‌شود»).

## ۵-ب) اثرانگشتِ گواهیِ APK (ریشۀ اعتمادِ خودِ برنامۀ اندروید)

امضای APK و امضای manifest دو سازوکارِ جدااند؛ این یکی مالِ APK است. بعد از
مرحلۀ ۱ (یا از هر APKِ امضاشده با همین کلید):

```bash
bash scripts/android_release_key_ceremony.sh fingerprint      # sha256:XX:XX:...
gh variable set ANDROID_RELEASE_CERT_SHA256 --repo johnwarchief/BorsTerminal-src \
  --body "<همان اثرانگشتِ sha256>"
```

اثرانگشتِ گواهی public است، پس درِ variable می‌نشیند و نه درِ secret. گام
`Verify the release certificate identity` درِ CI همین را با گواهیِ واقعیِ
`app-release.apk` مقایسه می‌کند: بی‌var ⇒ `NOT_VERIFIED`؛ با var و ناهمخوان ⇒
بیلد قرمز. تا این دو مقدار (`MOBILE_MANIFEST_PUBKEY` و
`ANDROID_RELEASE_CERT_SHA256`) ننشینند، هیچ APK را «نسخۀ رسمی» تلقی نکنید.

## ۶) سریِ دادۀ v2 با امضا (یک‌بار)

```bash
python scripts/publish_mobile_series.py --yes     # mobile-latest-v2 + .sig
```

## ۷) انتشار

```bash
gh workflow run mobile.yml --repo johnwarchief/BorsTerminal-src \
  -f publish=true -f prerelease=false -f snapshot_series=mobile-latest-v2
```

چهار دروازۀ داخلِ workflow یکی‌یکی باز بودن را دوباره بررسی می‌کنند (APK
امضاشده، کلیدِ عمومی درِ باندل، امضایِ بستۀ داده، سریِ هدفِ غیرکهنه). اگر یکی
بسته باشد ران با `BLOCKED` می‌ایستد و چیزی منتشر نمی‌کند.

## انتظارِ واقعی رویِ گوشیِ شما (این «ایراد» نیست، فیزیکِ امضا است)

تا امروز دو نسخۀ منتشرشده با دو گواهیِ Android Debugِ متفاوت ساخته شده بودند.
اولینِ نسخۀ رسمیِ امضاشده پس رویِ آن گوشی‌ها نصبِ رو‌رویی **نمی‌شود**:
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`، و باید یک‌بار حذف و دوباره نصب شود.
**حذفِ نصب، دادۀ محلیِ همان گوشی را می‌بَرد** (فهرستِ رصدِ محلی، سبدِ تصمیم،
قفلِ صفحهٔ چیده‌شده) — پیش ازِ حذف، خروجیِ لازم را بگیرید. از این پس همان کلید
ثابت می‌ماند و نسخۀ رسمیِ بعدی رو‌رویی نصب می‌شود؛ این را jobِ
`upgrade-matrix-on-device` با سه کلیدِ دورریختنی رویِ شبیه‌ساز می‌آزماید
(نصبِ تمیز، ارتقا با همان کلید، و ردِ نصب با کلیدِ دیگر).
