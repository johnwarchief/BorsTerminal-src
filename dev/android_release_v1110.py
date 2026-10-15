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
  A51..A58  قفلِ صفحه: هیچ اعتبارنامۀ ثابت درِ سورس یا باندلِ منتشرشده.
  A59..A66  مراسمِ کلیدِ انتشار: قراردادِ دوطرفۀ اسکریپت ↔ workflow.
  A67..A69  خودِ سنسورِ برش: بدنۀ job/step از سطرِ ساختاری خوانده می‌شود،
            نه از هر بارِ ذکرِ نام درِ توضیح.
  A70..A72  خواندنِ بستۀ داده از مخزنِ خصوصی (gh) + سنجشِ جداِ مسیرِ ناشناسِ
            گوشی، که بدونِ token است و باید صریحاً BLOCKED شود.
  A76..A82 هویتِ گواهیِ APK، قفلِ صفحه‌کلیدِ AVD، و مادۀ ارتقا که نسخه را از
            مبنایِ یکتا می‌سازد نه با جعلِ versionCode.
  A83..A90 تصمیمِ «src خصوصی می‌ماند»: هر چه گوشی بیرونِ CI می‌خواند (داده،
            لینکِ APK) باید به مخزنِ عمومیِ توزیع برود و پسِ انتشار ناشناس
            دانلود و پارس شود؛ ریلیزِ stable درِ آن مخزن رد می‌شود تا
            latest.json دسکتاپ پوشانده نشود.

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

# بدنۀ job/step باید از سطرِ ساختاریِ خودِ آن بریده شود. نامِ job و گام درِ
# توضیحِ فارسیِ گام‌هایِ دیگر هم تکرار می‌شود؛ برشِ خامِ `WF.split(name)[1]`
# آن‌وقت بدنهٔ یک job دیگر را می‌دهد و سنجه‌ها کور می‌شوند (این گاردِ خودی
# یک بار همین‌جا قرمز شد: «webview-on-emulator» وسطِ توضیحِ job ارتقا آمد).
def job_body(name, text=None):
    t = WF if text is None else text
    hit = re.search(r"^  " + re.escape(name) + r":[ \t]*$", t, re.M)
    if not hit:
        return ""
    rest = t[hit.end():]
    nxt = re.search(r"^  [A-Za-z0-9_-]+:[ \t]*$", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def step_pos(name, text=None):
    t = WF if text is None else t
    hits = list(re.finditer(r"^[ \t]+- name: ?\"?" + re.escape(name), t, re.M))
    return hits[-1].start() if hits else float("inf")


def step_body(name, text=None):
    t = WF if text is None else text
    hits = list(re.finditer(r"^[ \t]+- name: ?\"?" + re.escape(name), t, re.M))
    if not hits:
        return ""
    hit = hits[-1]
    indent = re.match(r"[ \t]*", t[hit.start():]).group(0)
    rest = t[hit.end():]
    nxt = re.search("^" + re.escape(indent) + r"- name:", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


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
gate = step_body("Publish gate status")
publish = step_body("Publish Android release")
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
chk("calc(var(--bors-nav-h) + 8px + env(safe-area-inset-bottom))" in CSS
    and re.search(r"--bors-nav-h: \d+px", CSS) is not None,
    "A21 بدنه ازِ همۀ بلندیِ نوار (+envِ ناوتی‌بار) فاصله می‌گیرد")
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
job = job_body("webview-on-emulator")
_emu_line = re.search(r"script: bash tools/android_emu_verify\.sh[^\n]*", job)
chk("needs: build-apk" in job and "/dev/kvm" in job,
    "A30 jobِ شبیه‌ساز بعد ازِ بیلد می‌دود و KVM را کاوش می‌کند")
chk("NOT_VERIFIED" in job and "if: steps.kvm.outputs.present != 'true'" in job,
    "A31 بی‌KVM، نتیجه صریحاً NOT_VERIFIED ثبت می‌شود (نه سبزِ جعلی)")
chk(_emu_line is not None and "app-debug.apk" not in _emu_line.group(0),
    "A32 آزمونِ WebView رویِ بیلدِ debuggable است (مسیرِ فایل را خودِ اسکریپت پیدا می‌کند) و درِ گزارش جدا ثبت می‌شود")
chk("find apks -type f -name 'app-debug.apk'" in EMU,
    "A42 مسیرِ artifact با glob پیدا می‌شود؛ upload-artifact ساختارِ release/ و debug/ را نگه می‌دارد")
chk('grep -E "$PKG|chromium|Capacitor' in EMU,
    "A43 شمارشِ نشتِ رمز به خطوطِ خودِ برنامه/WebView محدود است (noise سیستمی نه)")
chk("dependent checks NOT_VERIFIED" in EMU,
    "A44 بی‌بالاآمدنِ اپ، سنجه‌هایِ بعدی NOT_VERIFIED می‌شوند نه هشت FAILِ بی‌معنا")
# A45/A46 — مسیرِ امضا بی‌کلیدِ واقعی قابلِ آزمون نیست؛ یک کلیدِ دورریختنیِ هم‌انسان
# همان زنجیره را اثبات می‌کند، به‌شرطِ اینکه هرگز منتشر نشود.
smoke = step_body("Signing smoke test")
chk(bool(smoke) and "keytool -genkeypair" in smoke and "not-for-release" in smoke
    and "app-release.apk" in smoke,
    "A45 دودِ امضا با کلیدِ ساختگی، نامِ خروجیِ امضاشده و apksigner را می‌سنجد")
WF_PUB_BEFORE_SMOKE = step_pos("Publish Android release") < step_pos("Signing smoke test")
chk(WF_PUB_BEFORE_SMOKE and 'rm -rf app/build/outputs/apk/release' in smoke,
    "A46 دودِ امضا بعد ازِ گامِ انتشار می‌آید و خروجی‌اش بی‌درنگ پاک می‌شود (هیچ گامی کلیدِ بی‌ارزش را منتشر نمی‌کند)")
# A47/A48 — دو دامِ رانِ واقعیِ شبیه‌ساز: موندنِ پشتِ دروازۀ ورود «اپ باز شد»
# حساب نمی‌شود، و CDPِ بی‌پاسخ نباید پروسه را معلق کند.
chk("reached_content" in CDP and "login-gate" in CDP and "board" in CDP,
    "A47 کاوشگر WebView بینِ «صفحۀ ورود»، «تابلو» و «پیدا نشد» فرق می‌گذارد و فقط board سبز است")
chk("__timeout" in CDP and "setTimeout" in CDP,
    "A48 هر فرمانِ CDP مهلت دارد؛ بی‌پاسخ‌ماندن به exit 13 (top-level await ناتمام) نمی‌انجامد")
chk("ensure_running" in EMU and "dismiss_anr_dialog" in EMU and "uiautomator dump" in EMU,
    "A49 دستگاه یک اندازۀ ثابت می‌ماند، گفتگوی ANR رد می‌شود، و شواهدِ مستقل از DevTools (uiautomator) هم گرفته می‌شود")
chk('grep -c "ANR in "' in EMU and "ANRSYS" in EMU,
    "A50 سنجۀ ANR به پروسۀ ما محدود نیست؛ «Process system isn't responding» هم رد می‌شود (درِ رانِ 38671378595 گفتگوی سیستمی روی صفحه بود و گاردِ باریک آن را ندید)")
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

# ── A51..A58 قفلِ صفحه: بی‌هیچ اعتبارنامۀ ثابت درِ سورس یا باندل ─────────────
# دورِ پیشین ثبت کرد که یکِ نام‌کاربری و رمزِ پیش‌فرض درِ `authStore.ts` و درِ
# باندلِ built (پس درِ APK) می‌نشیند. رأیِ مالک درِ مأموریت ۱۴۰۵-۰۷-۲۳: آن
# اعتبارنامه حفظ نمی‌شود و قابلیتِ ورودِ ضروری هم حذف نمی‌شود. سنسور یکِ تابع
# است و کنترلِ منفی (A52) همان تابع را با متنِ کاشته‌شده می‌سنجد، پس سبزیِ A51
# یعنی «نیست»، نه «نمی‌بینم».
SECRET_PATTERNS = [r"bors123", r"DEFAULT_PASS", r"DEFAULT_USER"]


def secret_hits(text):
    return [p for p in SECRET_PATTERNS if re.search(p, text)]


shipped, shipped_hits = 0, []
for base, dirs, files in os.walk(os.path.join(ROOT, "frontend", "src")):
    dirs[:] = [d for d in dirs if d != "__tests__"]
    for f in files:
        if not f.endswith((".ts", ".tsx")):
            continue
        shipped += 1
        rel = os.path.relpath(os.path.join(base, f), ROOT).replace(os.sep, "/")
        h = secret_hits(read(rel))
        if h:
            shipped_hits.append("%s:%s" % (rel, ",".join(h)))
chk(shipped > 40 and not shipped_hits,
    "A51 هیچ اعتبارنامۀ ثابتی درِ %d سورسِ ارسالیِ فرانت نیست%s"
    % (shipped, ("" if not shipped_hits else " — " + "; ".join(shipped_hits[:3]))))
chk(secret_hits('export const DEFAULT_PASS = "bors123";') == ["bors123", "DEFAULT_PASS"],
    "A52 کنترلِ منفی: سنسور اعتبارنامۀ کاشته‌شده را می‌بیند (پس A51 کور نیست)")

bundle = os.path.join(ROOT, "frontend", "dist", "assets")
if os.path.isdir(bundle):
    js = [f for f in os.listdir(bundle) if f.endswith(".js")]
    leak = [f for f in js if secret_hits(open(os.path.join(bundle, f), encoding="utf-8",
                                              errors="replace").read())]
    chk(bool(js) and not leak, "A53 باندلِ built (%d فایل js) بی‌رمزِ ثابت است%s"
        % (len(js), ("" if not leak else " — " + ",".join(leak[:3]))))
else:
    chk(False, "A53 باندلِ built وجود ندارد — ابتدا `npm run build` (سنجشِ artifact انجام نشد)")

tool_hits = []
for f in sorted(os.listdir(os.path.join(ROOT, "tools"))):
    if f.endswith((".py", ".mts")) and secret_hits(read("tools/" + f)):
        tool_hits.append(f)
chk(not tool_hits, "A54 کاوشگرها رمز را تایپ نمی‌کنند (کد ازِ BORS_SCREEN_CODE)%s"
    % ("" if not tool_hits else " — " + ",".join(tool_hits[:4])))

AUTH = read("frontend/src/shared/stores/authStore.ts")
LOGIN = read("frontend/src/widgets/LoginScreen.tsx")
SHELL = read("frontend/src/app/layouts/AppShell.tsx")
chk("PBKDF2-SHA256" in AUTH and "setItem(LOCK_KEY" in AUTH and "setItem(LEGACY" not in AUTH,
    "A55 قفل فقط salt+hash می‌نویسد؛ هیچ نوشتنِ متنِ خام باقی نیست")
chk("normalizeCode" in AUTH and "0x06f0" in AUTH,
    "A56 ارقامِ فارسی/عربی نرمال می‌شوند (وگرنه «۱۲۳۴»ِ تایپی قفل را باز نمی‌کند)")
chk("locked && !isAuthenticated" in SHELL,
    "A57 دروازۀ قفل فقط وقتی قفل چیده شده بند است — پروفیلِ بی‌قفل قفل نمی‌شود")
chk('placeholder="admin"' not in LOGIN and "احراز هویت" not in LOGIN
    and 'autoComplete="off"' in LOGIN,
    "A58 صفحۀ قفل نام‌کاربری نمی‌خواهد و ادعایِ «احراز هویت امن» ندارد")

# ── A59..A65 مراسمِ کلیدِ انتشار: قراردادِ دو‌طرفۀ اسکریپت ↔ workflow ─────────
# بدونِ کلیدِ پایدار، «نسخۀ رسمی» معنی ندارد (دو ریلیزِ منتشرشده با دو گواهیِ
# debugِ متفاوت ساخته شدند و ارتقایِ درجا هیچ‌وقت ممکن نبود). کلید را مالک
# می‌سازد؛ کاری که این سنجه‌ها می‌کنند این است که اسکریپتِ مراسمِ او دقیقاً همان
# نام‌ها و همان قالبی را بسازد که mobile.yml می‌خواند — و هیچ رمزی درِ argv
# یا stdout نیفتد.
CER = read("scripts/android_release_key_ceremony.sh")
chk("set -euo pipefail" in CER and 'read -r -s' in CER,
    "A59 مراسمِ کلید: ورودیِ رمز بی‌پیش‌نمایش است و اسکریپت fail-fast")
chk("-storepass " not in CER and "-keypass " not in CER
    and "-storepass:env" in CER and "-storepass:file" in CER,
    "A60 رمز هیچ‌وقت درِ فرمانِ keytool (argv، فهرستِ پروسه‌ها) نمی‌نشیند")
# نسخهٔ پیشینِ همین سنج، خودِ الگویِ خراب را الزام می‌کرد: gh با `--body -` رشتهٔ
# «-» را ذخیره می‌کند (ازِ stdin فقط بی‌--body می‌خواند) و گارد سبز می‌ماند تا CI
# با «base64: invalid input» بکوبد (رانِ 38808582245). سنجش فقط رویِ **خطوطِ
# فرمان** است، نه رویِ توضیحِ فایل — وگرنه خودِ کامنتِ توضیحِ دام، سنسور را قرمز
# یا خوشبخت‌تر ازِ واقع می‌کند.
def _secret_cmds(text):
    return [l for l in text.splitlines() if "gh secret set" in l and not l.strip().startswith("#")]
_sh_cmds = _secret_cmds(CER)
_py_src = read("scripts/android_release_key_ceremony.py") or ""
_py_cmds = _secret_cmds(_py_src)
def _a61_ok(cmds, from_stdin):
    return bool(cmds) and all("--body" not in c for c in cmds) and from_stdin
chk(_a61_ok(_sh_cmds, any('< "$tmp"' in c or "| gh secret set" in CER.replace("base64 -w0 \"$KS\" | gh", "P") for c in _sh_cmds))
    and 'base64 -w0 "$KS" | gh secret set ANDROID_RELEASE_KEYSTORE_B64 --repo "$REPO"' in CER
    and 'gh secret set ANDROID_RELEASE_KEYSTORE_PROPS --repo "$REPO" < "$tmp"' in CER,
    "A61 هر دو secret درِ اسکریپتِ bash ازِ stdin می‌روند و «--body» درِ هیچ فرمانی نیست")
chk(_a61_ok(_py_cmds, "input=body.encode()" in _py_src)
    and '"gh", "secret", "set", name, "--repo", repo' in _py_src,
    "A61-ب همدوشِ پایتون هم مقدار را ازِ stdin می‌فرستد، نه ازِ argv/--body")
_bad_sh = CER.replace('gh secret set ANDROID_RELEASE_KEYSTORE_PROPS --repo "$REPO" < "$tmp"',
                      'gh secret set ANDROID_RELEASE_KEYSTORE_PROPS --repo "$REPO" --body "-" < "$tmp"')
chk(_a61_ok(_secret_cmds(_bad_sh), True) is False,
    "A61-پ کنترلِ منفی: بازگشتِ «--body -» درِ فرمان، A61 را قرمز می‌کند")
_secret_names_wf = set(re.findall(r"secrets\.(ANDROID_RELEASE_[A-Z_0-9]+)", WF))
_secret_names_cer = set(re.findall(r"gh secret set (ANDROID_RELEASE_[A-Z_0-9]+)", CER))
chk(_secret_names_wf and _secret_names_wf == _secret_names_cer,
    "A62 نامِ secretها درِ اسکریپت و workflow یکی است: %s"
    % ", ".join(sorted(_secret_names_wf | _secret_names_cer)))
_props_fmt = " ".join(l for l in CER.splitlines() if "storePassword=%s" in l)
_props_keys = re.findall(r"(?:\\n)?([A-Za-z]+)=%s", _props_fmt)
_gradle_keys = re.findall(r"getProperty\('([a-zA-Z]+)'\)", GR)
chk(sorted(_props_keys) == ["keyAlias", "keyPassword", "storePassword"]
    and set(_props_keys) <= set(_gradle_keys),
    "A63 قالبِ props (%s) همان چیزی است که build.gradle می‌خواند (%s)"
    % (",".join(sorted(_props_keys)), ",".join(sorted(set(_gradle_keys)))))
chk("storeFile=" not in CER.split("cmd_publish_secrets")[1],
    "A64 اسکریپت storeFile را درِ secret نمی‌گذارد — workflow خودش مسیرِ موقت را می‌نویسد")
chk("کلید از قبل هست" in CER and "به‌جایِ کلیدِ انتشارِ قبلی نسازید" in CER,
    "A65 keygen رویِ کلیدِ موجود بازنویسی نمی‌کند (کلیدِ انتشارِ قبلی جایِ تازه ندارد)")
# کنترلِ منفی: اگر روزی رمز به argv برود، A60 باید ببیند
_bad = CER.replace("-storepass:env BORS_SP", "-storepass hunter2")
chk("-storepass " in _bad and "-storepass " not in CER,
    "A66 کنترلِ منفی: سنسورِ argv با یکِ بازنویسیِ ساختگی قرمز می‌شود")

# ── A67..A69 خودِ سنسورِ برش: بدنۀ job/step از سطرِ ساختاری، نه از هر ذکر ────
# یک بار همین گارد قر شد چون نامِ job وسطِ توضیحِ job دیگر آمده بود: برشِ خام
# بدنهٔ اشتباه می‌داد و دو سنجه بی‌دلیل قرمز می‌شدند. این بندها ثابت می‌کنند
# برشِ ساختاری هم روی متنِ ساختگی و هم روی فایلِ واقعی درست است، و که برشِ خام
# درِ همان متنِ ساختگی گول می‌خورد (وگرنه آزمون فقط تکرارِ سبزِ سبز است).
_PROBE = (
    "jobs:\n"
    "  prep:\n"
    "    steps:\n"
    "      - name: KVM probe\n"
    "        run: echo see webview-on-emulator and Publish Android release\n"
    "  webview-on-emulator:\n"
    "    needs: build-apk\n"
    "    steps:\n"
    "      - name: Install, boot and probe the WebView\n"
    "        run: bash tools/android_emu_verify.sh\n"
    "  other:\n"
    "    steps: []\n"
)
_p_body = job_body("webview-on-emulator", _PROBE)
chk("needs: build-apk" in _p_body and "android_emu_verify" in _p_body
    and "KVM probe" not in _p_body,
    "A67 برشِ job رویِ متنِ ساختگی با ذکرِ مزاحم، بدنۀ درست را می‌دهد")
chk("needs: build-apk" not in _PROBE.split("webview-on-emulator")[1]
    .split("  webview-on-emulator:")[0],
    "A68 کنترلِ منفی: همان متن با برشِ خام بدنهٔ اشتباه می‌داد (سنسور کور نیست)")
chk("needs: build-apk" in job_body("webview-on-emulator", WF)
    and step_pos("Signing smoke test") > step_pos("Publish Android release"),
    "A69 برشِ ساختاری رویِ فایلِ واقعی هم بدنه/ترتیبِ درست می‌دهد")

# ── A70..A72 خواندنِ بستۀ داده از مخزنِ خصوصی ───────────────────────────────
# مخزنِ src در 2026-10-15 خصوصی شد؛ شاهد: رانِ موفقِ 2026-10-12T23:11Z که
# بی‌اعتبارنامه bytes=16179264 گرفت و همان URL امروز 404 می‌دهد. پس بیلد نباید
# به curlِ ناشناس وابسته باشد، و مسیرِ *گوشی* (که token ندارد) باید جدا سنجیده
# و صریحاً BLOCKED اعلام شود، نه اینکه ساکت از گیت رد شود.
_build = step_body("Build mobile frontend")
chk("gh release download" in _build
    and not re.search(r"curl[^\n]*-o dist/mobile_snapshot\.db\.gz", _build),
    "A70 بستۀ داده با gh (اعتبارنامۀ کارفرما) خوانده می‌شود؛ curlِ ناشناس بیلد را نمی‌خواباند")
chk("-w '%{http_code}'" in _build and "BLOCKED for end users" in _build
    and "GITHUB_STEP_SUMMARY" in _build,
    "A71 دسترسیِ ناشناسِ همان URL (مسیرِ خودِ گوشی) سنجیده و بی‌200 صریحاً BLOCKED می‌شود")
_anon = re.compile(r"curl[^\n]*-o dist/mobile_snapshot\.db\.gz")
_fake = _build.replace(
    'gh release download "$SNAPSHOT_SERIES" --repo "$SERIES_REPO" \\\n'
    '            --pattern mobile_snapshot.db.gz --dir dist --clobber',
    'curl -fL "$BASE/mobile_snapshot.db.gz" -o dist/mobile_snapshot.db.gz')
chk(_anon.search(_fake) is not None and _anon.search(_build) is None,
    "A72 کنترلِ منفی: بازگشتِ همین خط به curlِ ناشناس، A70 را قرمز می‌کند")

# ── A83..A90 چیزی که گوشی می‌خواند باید عمومی باشد (مخزنِ src خصوصی می‌ماند) ──
# تصمیمِ مالک: src خصوصی می‌ماند. پس هر URL که بیرونِ CI خوانده می‌شود —
# بستۀ دادۀ گوشی و لینکِ دانلودِ APK — باید به مخزنِ عمومیِ توزیع برود.
LD = read("frontend/src/shared/api/local/localData.ts") or ""
PUBS = read("scripts/publish_mobile_series.py") or ""
_pub = step_body("Publish Android release")
chk("BorsTerminal-src" not in LD and "johnwarchief/BorsTerminal/releases/download" in LD,
    "A83 پیش‌فرضِ دادۀ گوشی درِ باندل، مخزنِ عمومیِ توزیع است (گوشی token ندارد)")
chk("johnwarchief/BorsTerminal-src" not in "".join(
        read(p) or "" for p in ("frontend/src/__tests__/mobile-boot-source.spec.ts",
                                "frontend/src/__tests__/mobile-snapshot-integrity.spec.ts",
                                "tools/mobile_old_client_compat_probe.mts")),
    "A84 آزمون‌ها و کاوشگرهایِ مسیرِ داده هم همان hostِ عمومی را می‌سنجند (یک قرارداد، دو جا نیست)")
chk('REPO_DEFAULT = "johnwarchief/BorsTerminal"' in PUBS
    and 'SERIES_DEFAULT = "mobile-latest-v2"' in PUBS,
    "A85 ناشرِ سریِ داده به‌پیش‌فرض درِ مخزنِ عمومی منتشر می‌کند")
chk("secrets.RELEASE_TOKEN" in _pub and '--repo "$PUBLISH_REPO"' in _pub
    and "github.token" not in _pub,
    "A86 ریلیزِ اندروید با tokenِ نوشتنِ مخزنِ توزیع و رویِ همان مخزن ساخته می‌شود")
chk('if [ "${{ github.event.inputs.prerelease }}" = "false" ]; then' in _pub
    and "BLOCKED: prerelease=false" in _pub,
    "A87 prerelease=false رد می‌شود: ریلیزِ stableِ اندروید latest.json دسکتاپ را می‌پوشاند")
chk("unset GH_TOKEN" in _pub and "releases/latest/download/latest.json" in _pub
    and "sqlite3.connect" in _pub and "sha256sum _pubcheck/apk_from_link.apk" in _pub,
    "A88 پسِ انتشار، لینکِ کاربر بی‌اعتبارنامه باز و پارس می‌شود (نه فقط HTTP 200)")
chk("emulator-boot-timeout" in WF and "\n          boot-timeout:" not in WF,
    "A89 مهلتِ بوت با نامِ واقعیِ ورودیِ action نوشته شده (نامِ غلط بی‌صدا نادیده می‌گیرد)")
_fake_src = LD.replace("johnwarchief/BorsTerminal/releases/download",
                       "johnwarchief/BorsTerminal-src/releases/download")
chk("BorsTerminal-src" in _fake_src,
    "A90 کنترلِ منفی: بازگشتِ hostِ خصوصی به localData، A83 را قرمز می‌کند")

# ── A91 راه‌اندازیِ دستگاه: flake را با شواهد داوری کن، نه با یک تلاش ──────────
# رانِ 38796223802 رویِ APK ای که درِ رانِ پیشین pid داده بود «no process after
# 30s» گرفت و هیچ مدرکی نگذاشت.
chk("for i in 1 2 3" in EMU and "launch_fail_evidence.txt" in EMU
    and "no process after 3 attempts" in EMU,
    "A91 کاوشِ WebView سه تلاشِ راه‌اندازی دارد و درِ شکست پروندۀ شواهد می‌نویسد")
UPG2 = read("tools/android_upgrade_matrix.sh") or ""
chk("for i in 1 2 3" in UPG2 and "launch_fail.txt" in UPG2,
    "A91-ب مادۀ ارتقا هم همان سه تلاشِ شواهدمند را دارد")
chk("/proc/net/unix" in EMU and "webview_devtools_remote_$PID" not in EMU,
    "A92 نامِ socketِ DevTools ازِ /proc/net/unix خوانده می‌شود، نه ازِ حدسِ pid اپ")
chk('UIHITS=$(grep -oE "قیف|تابلو|شاخص|غربالگری|معامله|بورس|نمودار|پرتفوی"' in EMU
    and "a11y-$LABEL-evidence.txt" in EMU,
    "A93 واژگانِ سنجۀ دسترس‌پذیری ازِ خودِ رابط است و FAIL بی‌شواهد نمی‌ماند")

# ── A73..A75 سنسورِ صفحۀ ۴۰۴ درِ کاوشگرِ viewport ────────────────────────────
# نسخهٔ پیشین با گشتنِ `/پیدا نشد|۴۰|404/` درِ متنِ body می‌گشت: «۴۰» درونِ
# قیمت‌ها هم صدا می‌خورد، پس ۹ پروندۀ واقعی ۴۰۴ خوانده می‌شدند و خودِ صفحۀ
# ۴۰۴ false. سنسورِ درست همان testid را می‌بیند که routes.tsx می‌گذارد.
PRB = read("tools/android_viewport_probe.mts") or ""
_m_line = re.search(r"^\s*notFound:.*$", PRB, re.M)
chk(_m_line is not None and "route-not-found" in _m_line.group(0),
    "A73 کاوشگرِ viewport صفحۀ ۴۰۴ را از testidِ خودِ route می‌شناسد")
chk(_m_line is not None and "innerText" not in _m_line.group(0)
    and "notFound: /" not in PRB,
    "A74 هیچ حکمِ مسیریابی از تطبیقِ متنِ خامِ body ساخته نمی‌شود")
_v_block = re.search(r"verdict:\s*\{[\s\S]*?\n {6}\}", PRB)
chk(_v_block is not None and "no404Fallback:" in _v_block.group(0),
    "A75 «آدرسِ ثبت‌شده به ۴۰۴ نیفتد» جزوِ حکم‌هاست، پس خروجِ کاوشگر را می‌شکند")

# ── A76..A80 هویتِ کلید و گاردهایِ سنسورِ دستگاه ─────────────────────────────
_cert_step = step_body("Verify the release certificate identity")
chk("vars.ANDROID_RELEASE_CERT_SHA256" in _cert_step
    and "apk_cert_fingerprint.py" in _cert_step and "SIGNED-MATCH" in _cert_step,
    "A76 هویتِ گواهیِ APK با اثرانگشتِ ثبت‌شدۀ مالک جدا سنجیده می‌شود (بی‌var ⇒ NOT_VERIFIED)")
chk("wm dismiss-keyguard" in EMU and EMU.count("keep_awake") >= 3,
    "A77 پیش‌ازِ هر کاوشِ دستگاه قفلِ صفحه کنار می‌رود (بوتِ AVD صفحه را قفل می‌کند)")
UPG = read("tools/android_upgrade_matrix.sh") or ""
chk("wm dismiss-keyguard" in UPG and 'step "boot" "PASS"' in UPG,
    "A77-ب مادۀ ارتقا هم بعدِ بوت قفلِ صفحه را کنار می‌گذارد (همان دامِ WebView)")
chk("-PBorsVersionCode" not in UPG and "pkg_set_version" in UPG
    and "version-source-restored" in UPG,
    "A82 مادۀ ارتقا نسخه را جعل نمی‌کند: مبنایِ یکتا (package.json) عوض و بازگردانده می‌شود")
chk('step "webview-$LABEL-a11y" NOT_VERIFIED "درختِ uiautomator مالِ قفلِ صفحه بود' in EMU,
    "A78 قفلِ صفحه به‌حسابِ اپ FAIL نمی‌شود؛ علتش صریحاً NOT_VERIFIED است")
chk(EMU.count("step anr FAIL") == 1 and "\nfi\n  step anr FAIL" not in EMU,
    "A79 رأیِ ANR یک شاخۀ شرطی است، نه یک خطِ یتیمِ بعدِ fi (رانِ پیشین همیشه FAIL می‌داد)")
_build2 = step_body("Validate the release artifact (aapt2 + apksigner)")
tool = read("tools/apk_cert_fingerprint.py") or ""
chk("SCHEME_IDS" not in tool and "APK Sig Block 42" in tool
    and '"SIGNED-UNVERIFIED"' in tool and '"UNSIGNED"' in tool,
    "A80 ابزارِ گواهی جفت‌ها را با ساختار می‌شناسد (نه جدولِ id ازِ حافظه) و بی‌شواهد «رسمی» نمی‌گوید")
chk("resources.arsc" in _build2 and "network_security_config" in _build2
    and "assets/public/" in _build2,
    "A81 خودِ APKِ بیلدشده می‌خواند: سیاستِ شبکه درِ resources.arsc و بی‌اعتبارنامۀ ثابت درِ assets/public")

print("android_release_v1110: %d passed / %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
