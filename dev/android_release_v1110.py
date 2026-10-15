#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/android_release_v1110.py — گاردِ زنجیرۀ انتشارِ اندروید (مرحلۀ ۵ و ۶ و ۹).

چرا: تا دورِ پیشین، «نسخۀ رسمی اندروید» یعنی `gradlew assembleDebug` و انتشارِ
همان `app-debug.apk`. شاهدِ مستقیم (پایشِ APK Signing Block دو ریلیز منتشرشده):
هر دو `CN=Android Debug` بودند، اثرانگشتشان با هم فرق داشت و `notBefore`شان
تاریخِ همانِ رانِ CI بود ⇒ گواهیِ امضا درِ هرِ ساخت عوض می‌شد و ارتقایِ درجا رویِ
گوشی هیچ‌وقت ممکن نبود. این گارد همان چیزی را الزامی می‌کند که جلویِ آن فاجعه
را می‌گیرد، بی‌آنکه به کلیدِ خصوصی یا دستگاهِ واقعی نیاز داشته باشد:

  A01..A08  دروازۀ انتشار: بی‌امضا منتشر نمی‌شود، debug هرگز جایِ کلیدِ
            انتشار را نمی‌گیرد، رمز درِ فرمانِ gradlew نمی‌آید.
  A09..A16  سخت‌سازیِ manifest/WebView: allowBackup، صفحه‌کلید، cleartext،
            debuggable، تنها مجوزِ لازم.
  A17..A22  نسخه‌گذاری و مقصدِ انتشار: versionCode یکتا و بالاتر، tag مستقلِ
            اندروید، و دست‌نخورده‌بودنِ مسیرِ دسکتاپ (latest.json و vX.Y.Z).
  A23..A30  آزمونِ WebView: شبیه‌ساز باکاوشِ KVM، مسیرِ NOT_VERIFIEDِ صادق،
            و حکمِ سختِ سنجه (سفیدیِ صفحه یا نشتِ رمز ⇒ خروجِ ناموفق).

هیچ‌کدام ازِ این‌ها Gradle یا APK اجرا نمی‌کنند (رویِ این ماشین Java/SDK نصب
نیست): قراردادِ فایل‌ها خوانده می‌شود. ساختِ واقعی درِ CI سنجیده می‌شود و
نتیجه‌اش درِ docs/android/ANDROID-RELEASE-REPORT-2026-10-15.md ثبت می‌شود.

اجرا:  python dev/android_release_v1110.py        (۰ = سبز، ۱ = رد)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = FAIL = 0


def chk(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok    " + label)
    else:
        FAIL += 1
        print("  FAIL  " + label)


def read(rel):
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


WF = read(".github/workflows/mobile.yml")
GR = read("frontend/android/app/build.gradle")
MF = read("frontend/android/app/src/main/AndroidManifest.xml")
NS = read("frontend/android/app/src/main/res/xml/network_security_config.xml")
GI = read("frontend/android/.gitignore")
CAP = read("frontend/capacitor.config.ts")
HT = read("frontend/index.html")
CSS = read("frontend/src/shared/styles/mobile.css")
ESC = read("frontend/src/shared/api/local/diagnostics.ts")
EMU = read("tools/android_emu_verify.sh")
CDP = read("tools/android_webview_check.mts")
DESKTOP_WF = read(".github/workflows/release.yml")
CFG = read("bors_config.py")
PKG = read("frontend/package.json")

missing = [n for n, v in (
    ("mobile.yml", WF), ("app/build.gradle", GR), ("AndroidManifest.xml", MF),
    ("network_security_config.xml", NS), ("android/.gitignore", GI),
    ("capacitor.config.ts", CAP), ("index.html", HT), ("mobile.css", CSS),
    ("diagnostics.ts", ESC), ("tools/android_emu_verify.sh", EMU),
    ("tools/android_webview_check.mts", CDP), ("release.yml", DESKTOP_WF),
    ("bors_config.py", CFG), ("package.json", PKG)) if v is None]
chk(not missing, "A00 همه‌چیزِ لازم درِ مخزن هست: " + (", ".join(missing) if missing else "OK"))
if missing:
    print("android_release_v1110: %d passed / %d failed" % (PASS, FAIL))
    sys.exit(1)

# ── A01..A08 دروازۀ انتشار ─────────────────────────────────────────────────
chk("assembleRelease" in WF, "A01 workflow نسخۀ release را می‌سازد (نه فقط debug)")
chk("Materialize the release keystore" in WF and
    "ANDROID_RELEASE_KEYSTORE_B64" in WF and "ANDROID_RELEASE_KEYSTORE_PROPS" in WF,
    "A02 keystore فقط ازِ دو secretِ نام‌دارِ پروژه خوانده می‌شود")
chk("umask 077" in WF and "printf '%s' \"$KS_B64\" | base64 -d" in WF,
    "A03 keystore با مجوزِ محدود درِ RUNNER_TEMP نوشته می‌شود")
chk("-PBorsKeystoreProperties" not in WF and "BORS_KEYSTORE_PROPERTIES=" in WF,
    "A04 رمز هیچ‌جا درِ فرمانِ قابل‌مشاهده نمی‌آید؛ فقط مسیرِ فایل ازِ env")
chk('if [ "$APK_SIGNED" != "yes" ]' in WF and WF.count('"$APK_SIGNED" != "yes"') >= 2,
    "A05 انتشارِ APKِ بی‌امضا درِ دو گامِ مستقل بسته است (نه یکی)")
gate = WF.split("Publish gate status")[1] if "Publish gate status" in WF else ""
publish = WF.split("Publish Android release")[1] if "Publish Android release" in WF else ""
chk("BLOCKED" in gate and "BLOCKED" in publish,
    "A06 هر دو دروازه پیامِ BLOCKEDِ صریح دارند (بی‌سکوتِ قرمز)")
chk("outputs/apk/release" in publish and "outputs/apk/debug" not in publish,
    "A07 ریلیز تنها ازِ پوشۀ outputs/apk/release برداشته می‌شود؛ app-debug.apk هرگز منتشر نمی‌شود")
chk("debug.keystore" in GR and "GradleException" in GR,
    "A08 Gradle خودِ کلیدِ debug را با استثنا رد می‌کند (دفاعِ دوم، بی‌CI)")
ksblock = GR[GR.find("borsKsProps"):GR.find("android {")] if "borsKsProps" in GR else ""
chk("storePassword" in ksblock and "keyPassword" in ksblock and "keyAlias" in ksblock,
    "A09 هر چهار فیلدِ keystore لازم است؛ نیمه‌کاره = GradleException")
chk("signingConfig signingConfigs.borsRelease" in GR and "if (borsReleaseSigned)" in GR,
    "A10 امضایِ release مشروط بهِ وجودِ کلید است، بی‌بازگشتِ ساکت")
chk("debuggable false" in GR, "A11 buildType.release صراحتاً non-debuggable است")
chk("keystore.properties" in GI and "*.keystore" in GI and "*.jks" in GI and
    "#*.keystore" not in GI, "A12 keystore و properties هر سه درِ گیت‌نگیر فعال‌اند")

# ── A13..A18 سخت‌سازیِ manifest/WebView ────────────────────────────────────
chk('android:allowBackup="false"' in MF, "A13 پشتیبانِ ابری/adb خاموش")
chk('android:windowSoftInputMode="adjustResize"' in MF, "A14 صفحه‌کلید محتوا را فشرده نمی‌کند")
chk('android:networkSecurityConfig="@xml/network_security_config"' in MF,
    "A15 پیکربندیِ صریحِ شبکه درِ manifest وصل است")
chk('cleartextTrafficPermitted="false"' in NS and '<certificates src="system" />' in NS,
    "A16 cleartext بسته و تنها anchorها سیستم‌اند (بدونِ TrustStoreِ اضافه)")
perms = re.findall(r'uses-permission android:name="([^"]+)"', MF)
chk(perms == ["android.permission.INTERNET"], "A17 تنها مجوزِ لازم: INTERNET " + str(perms))
exp = re.findall(r'android:exported="(true|false)"', MF)
chk(exp.count("true") == 1 and exp.count("false") == 1,
    "A18 فقط launcher exported است؛ FileProvider نه")
chk("android:allowMixedContent" not in MF and "allowMixedContent: false" in CAP,
    "A19 mixed content درِ پیکربندیِ Capacitor بسته است")
chk("viewport-fit=cover" in HT, "A20 viewport-fit=cover تا env(safe-area-inset-*) صفر نماند")
chk("calc(66px + env(safe-area-inset-bottom))" in CSS,
    "A21 بدنه با ناوتی‌بارِ بلندشده‌یِ سیستم فاصله دارد")
chk("function esc(" in ESC and "${esc(label)}" in ESC and "${esc(value)}" in ESC,
    "A22 مقدارهایِ پنلِ عیب‌یابی پیش ازِ innerHTML گریز می‌کنند")

# ── A23..A27 نسخه‌گذاری و مقصدِ انتشار ─────────────────────────────────────
m_cfg = re.search(r'^APP_VERSION = "([0-9.]+)"$', CFG, re.M)
m_pkg = re.search(r'"version":\s*"([0-9.]+)"', PKG)
chk(m_cfg and m_pkg and m_cfg.group(1) == m_pkg.group(1),
    "A23 لنگرهایِ نسخه می‌خوانند: " + str((m_cfg and m_cfg.group(1), m_pkg and m_pkg.group(1))))
code = None
if m_pkg:
    p = [int(x) for x in m_pkg.group(1).split(".")]
    code = p[0] * 1000000 + p[1] * 1000 + p[2]
chk(code is not None and code > 1000079,
    "A24 versionCode ازِ آخرین بیلدِ CI (1000079) بالاتر است: " + str(code))
chk("BORS-VERSION" in GR and "versionCode borsVersionCode" in GR,
    "A25 versionCode ازِ همان منبعِ یکتا (package.json) مشتق می‌شود")
tagm = re.search(r'TAG="([^"]+)"', publish)
chk(tagm is not None and tagm.group(1).startswith("android-"),
    "A26 tag اندروید با «android-» شروع می‌شود: " + (tagm.group(1) if tagm else "—"))
chk(tagm and "mobile-latest" not in tagm.group(1) and "data-latest" not in tagm.group(1)
    and not tagm.group(1).startswith("v"),
    "A27 tag با برچسبِ دسکتاپ (vX.Y.Z) و سری‌هایِ دادۀ منتشرشده نمی‌خواند")
chk("latest.json" in DESKTOP_WF and "android" not in DESKTOP_WF.lower(),
    "A28 workflow دسکتاپ دست‌نخورده است و هیچ اشاره‌ای به اندروید ندارد")
chk("mobile-latest|data-latest" in publish,
    "A29 سریِ دادۀ کهنه به‌عنوان مقصدِ بیلدِ تازه رد می‌شود")

# ── A30..A36 آزمونِ WebView ────────────────────────────────────────────────
job = WF.split("webview-on-emulator")[1] if "webview-on-emulator" in WF else ""
chk("needs: build-apk" in job and "/dev/kvm" in job,
    "A30 jobِ شبیه‌ساز بعد ازِ بیلد می‌دود و KVM را کاوش می‌کند")
chk("NOT_VERIFIED" in job and "if: steps.kvm.outputs.present != 'true'" in job,
    "A31 بی‌KVM، نتیجه صریحاً NOT_VERIFIED ثبت می‌شود (نه سبزِ جعلی)")
chk("bash tools/android_emu_verify.sh" in job and "app-debug.apk" not in WF.split("script: bash tools/android_emu_verify.sh")[1].split("\n")[0],
    "A32 آزمونِ WebView رویِ بیلدِ debuggable است (مسیرِ فایل را خودِ اسکریپت پیدا می‌کند) و درِ گزارش جدا ثبت می‌شود")
chk("find apks -type f -name 'app-debug.apk'" in EMU,
    "A42 مسیرِ artifact با glob پیدا می‌شود؛ upload-artifact ساختارِ release/ و debug/ را نگه می‌دارد")
chk('grep -E "$PKG|chromium|Capacitor' in EMU,
    "A43 شمارشِ نشتِ رمز به خطوطِ خودِ برنامه/WebView محدود است (noise سیستمی نه)")
chk("dependent checks NOT_VERIFIED" in EMU,
    "A44 بی‌بالاآمدنِ اپ، سنجه‌هایِ بعدی NOT_VERIFIED می‌شوند نه هشت FAILِ بی‌معنا")
chk("wm size" in EMU and "360x800" in EMU and "390x844" in EMU and "412x915" in EMU,
    "A33 سه اندازۀ تلفن با wm size/density واقعی سنجیده می‌شود")
chk("keyevent 4" in EMU and "KEYCODE_HOME" in EMU and "FATAL EXCEPTION" in EMU,
    "A34 بازگشت، background/foreground و crash/ANR سه سنجه‌اند")
chk("grep -qP '\\tFAIL\\t'" in EMU, "A35 یکِ FAILِ گام خروجِ ناموفق می‌دهد")
chk("webSocketDebuggerUrl" in CDP and "Network.enable" in CDP and "Log.enable" in CDP,
    "A36 کاوشگر ازِ CDPِ همان WebView خواند، نه ازِ Chromiumِ دسکتاپ")
sec = re.findall(r'secretish', CDP)
chk(len(sec) >= 2 and "process.exit(fail ? 1 : 0)" in CDP,
    "A37 نشتِ رمز یا صفحۀ سفید درِ کاوشگر حکمِ رد می‌دهد")

# A38/A39 — همان چیزی که یکِ بیلدِ CI واقعی گرفت: کامنتِ XML نمی‌تواند `--`
# داشته باشد و AAPT آن را تا بیلدِ release ساکت نگه نمی‌دارد. parseِ سخت، گامِ
# زودتر ازِ Gradle.
import xml.dom.minidom as _md
for rel in ("frontend/android/app/src/main/AndroidManifest.xml",
            "frontend/android/app/src/main/res/xml/network_security_config.xml"):
    txt = read(rel)
    try:
        _md.parseString(txt)
        chk(True, "A38 XMLِ سخت‌افزارخوان well-formed است: " + rel.split("/")[-1])
    except Exception as e:
        chk(False, "A38 XMLِ well-formed نیست (%s): %s" % (rel, e))
chk("--live-reload" not in (NS or ""),
    "A39 هیچ `--` درِ کامنتِ network_security_config نمی‌ماند (دلیلِ شکستِ بیلدِ اول)")
# A40/A41 — بیلدِ دومِ CI این را گرفت: بی‌کلید، AGP نامِ خروجی را
# app-release-unsigned.apk می‌گذارد؛ هر مسیرِ سختِ «app-release.apk» دروازۀ
# انتشار را با «ساخته نشد» می‌بست، نه با دلیلِ درست.
chk("outputs/apk/release/*.apk" in WF and "ls -1 frontend/android/app/build/outputs/apk/release" in WF,
    "A40 خودۀ release با glob پیدا می‌شود، نه با نامِ ثابت")
chk("*unsigned*" in publish, "A41 اگر نامِ فایل unsigned باشد، انتشار جداگانه بسته می‌شود")

print("android_release_v1110: %d passed / %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
