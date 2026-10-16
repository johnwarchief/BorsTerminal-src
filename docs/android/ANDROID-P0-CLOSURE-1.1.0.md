# بستنِ P0 — Android 1.1.0: لینکِ رسمی تأیید شد

**تاریخ:** ۲۰۲۶-۱۰-۱۶ · **وضعیت:** `PRE-RELEASE VERIFIED` (پیش‌تر: «انتشار اولیه انجام شده، اصلاح لینک تأییدنشده»)

هیچ فایلِ منتشرشده‌ای حذف نشد. هیچ تگِ تکراری ساخته نشد. `latest.json` دسکتاپ دست‌نخورده است.

---

## ۱) علتِ دقیقِ `accepts at most 1 arg(s), received 2`

**بازتولیدِ محلی، نه حدس** (gh version 2.100.0، 2026-09-03):

```
$ gh release view android-1.1.0 --repo johnwarchief/BorsTerminal --json assets --jq '.assets[].name'
app-release.apk
bors-terminal-android-1.1.0.apk                      ← یک آرگومانِ موقعیتی: درست

$ gh release view android-1.1.0 n --repo johnwarchief/BorsTerminal --json assets --jq '.assets[].name'
accepts at most 1 arg(s), received 2                 ← دقیقاً همان پیامِ ران
```

نحوِ درستِ `gh release view` فقط **یک** آرگومانِ موقعیتی می‌پذیرد. در ران `38817210463` سطرِ چکِ asset این‌طور نوشته شده بود:

```
gh release view "$TAG" --repo "$PUBLISH_REPO" --json assets --jq '.assets[].name' \n            | grep -qx "$PUB_NAME"
```

`"\n"` درِ بلوکِ YAMLِ `run: |` به **دو نویسهٔ جدا** (`\` و `n`) تبدیل می‌شد، نه خطِ تازه؛ bash آن را بدونِ نقل‌قول می‌دید و `\n` به `n`ِ تنها فرو می‌ریخت — یعنی آرگومانِ موقعیتیِ دوم. پس نه نامِ asset غلط بود، نه آپلود رد شده بود: **خودِ فرمانِ راستی‌آزمایی** می‌مرد. رفع در `a40a385f`: فرمان در یک سطر نوشته شد.

دامِ دومِ همان ران: چکِ idempotency به `"$TAG"` اشاره می‌کرد ولی `TAG=` دو سطر پایین‌تر تعریف می‌شد ⇒ `gh release view ""` «آخرین ریلیز» (یعنی `v1.0.89` دسکتاپ) را می‌دید و دروغ می‌گفت «از پیش موجود است». رفع: `TAG` به بالای گام منتقل شد.

## ۲) هویتِ بایت‌ها — سه build، سه کامیت

| build | sha256 | size | run | source commit | کجاست |
| --- | --- | --- | --- | --- | --- |
| A | `5655afa1…3ae432` | 21,203,301 | 38815504255 | `38f39f61` | assetِ `app-release.apk` — **روی GitHub هست** |
| B | `f85fd3cf…557b38` | 21,203,253 | 38817210463 | `206d520c` | با `--clobber` رانِ C جایگزین شد — **الآن روی GitHub نیست** |
| C | `4adca360…c63506` | 21,203,269 | 38819805470 | `897efdd1` | assetِ `bors-terminal-android-1.1.0.apk` — **مرجعِ رسمی** |

تفاوتِ ۳۲ و ۴۸ بایتی از سه commitِ متفاوتِ سورس است، نه دستکاری. **A حذف نشد** — هر دو assetِ روی GitHub با یک کلیدِ رسمیِ یکسان امضا شده‌اند و هیچ‌کدام debug نیست؛ فقط A قدیمی است و لینکِ رسمی به آن نمی‌رود.

## ۳) نامِ asset از خودِ GitHub (API، نه لاگ)

```
asset app-release.apk                    21203301  sha256:5655afa1432fce2feeed6959880be23412270808d3c22fa72fed9b16e03ae432
asset bors-terminal-android-1.1.0.apk    21203269  sha256:4adca3602a5815a638f0106ffca37792c0ea65a0c5b737f6e4110b1467c63506
```

نامِ وعده‌داده‌شده درِ لینک، **واقعاً** درِ فہرستِ asset هست. نیازی به آپلودِ دوباره نبود؛ رانِ سبز `38819805470` خودش همان را با همان نام منتشر کرده بود.

## ۴) دانلودِ ناشناس در محیطِ بی‌اعتبارنامه

با `env -u GH_TOKEN` و curlِ مستقیمِ لینکِ کاربر:

```
size   = 21203269 bytes
sha256 = 4adca3602a5815a638f0106ffca37792c0ea65a0c5b737f6e4110b1467c63506
```

هر دو **بیت‌به‌بیت** با artifact مرجع (C) برابر. مقایسه با digestِ خودِ GitHub هم برابر است.

## ۵) امضایِ APKِ دانلودشده، مستقل از CI

`tools/apk_cert_fingerprint.py` روی همان فایلی که از لینکِ عمومی دانلود شد:

```
subject : CN=BorsTerminal Android Release, OU=mobile, O=BorsTerminal, C=IR
valid   : 2026-10-15T20:57:55+00:00 → 2051-10-09T20:57:55+00:00
SHA-256 : 1A:4D:A3:3D:10:23:C5:DF:7D:2E:E3:C5:16:73:77:BE:E4:46:BA:25:DE:C9:C4:ED:A2:5F:AA:6D:F6:13:4B:58
VERDICT : SIGNED-MATCH
```

همین برای asset قدیمی (A) هم اجرا شد: `SIGNED-MATCH` — یعنی آن هم با کلیدِ رسمی است، فقط منسوخ.

## ۶) آپدیترِ دسکتاپ و بستۀ داده

| سنج | نتیجه |
| --- | --- |
| `releases/latest/download/latest.json` (ناشناس) | `version = 1.0.89` — همان دسکتاپ، نه `1.1.0` |
| `releases/latest` | `v1.0.89` · `prerelease=false` · ۱۳ asset |
| بستۀ داده `mobile-latest-v2` | schema 2 · package_id `20261016T003218-04d6f9f1` · app/min `1.1.0` |
| حجم و هشِ gz (ناشناس) | 16,179,118 B == اعلامی؛ sha256 `04d6f9f142cbc06e…f870c16` == اعلامی |
| امضای manifest | `{"verified": true}` با کلیدِ عمومیِ `vars.MOBILE_MANIFEST_PUBKEY` |

## ۷) چیزی که درِ همین بستن پیدا شد و رفعِ بیرونی خواست

**بدنهٔ ریلیز، هشِ اشتباه داشت.** مسیرِ idempotent من (`SKIP_CREATE`) فقط «create» را رد می‌کند و **متنِ ریلیز را تازه نمی‌کند** — پس ریلیز با یادداشتِ buildِ A (sha `5655afa1…`) مانده بود درحالی‌که لینکش به buildِ C اشاره می‌کرد. یعنی کاربری که هش را از یادداشتِ ریلیز برمی‌داشت، هرگز فایلِ واقعی را تأیید نمی‌کرد.

رفع: بدنه با `gh release edit --notes-file` بازنویسی شد و حالا جدولِ «دو فایل، کدام رسمی» + هویتِ buildِ مرجع + روشِ تأیید را دارد. بازخوانی از GitHub تأیید کرد: `body_sha_line = 4adca360…c63506`، `prerelease=true`، `draft=false`.

**قفلِ پیشنهادی برای گارد:** هر گامِ idempotent که create را رد می‌کند باید `gh release edit --notes-file` هم بزند، وگرنه یادداشت روی buildِ قبلی می‌میرد. این هنوز در `dev/android_release_v1110.py` سنجیده نشده — در P1 همین را به‌عنوان چکِ تازه می‌بندم.

## ۸) تنها موردِ باز

`webview-on-emulator` درِ همان ران دو FAIL دارد: `webview-360x800-a11y` (هیچ واژۀ دیدنیِ برنامه در uiautomator نبود) و `anr` (`ANR in com.borsterminal.mobile/.MainActivity`)، همراه `Failed to bind to texture: invalid color buffer` از گرافیکِ امولاتور. `crash [PASS]` بود و `upgrade-matrix-on-device` سبز است — یعنی APK نصب و بالا می‌آید و ارتقا کار می‌کند، ولی **تأییدِ DOM در WebView همچنان `NOT_VERIFIED`** است.
