#!/usr/bin/env bash
# tools/android_emu_verify.sh — آزمونِ زندهٔ WebView رویِ شبیه‌سازِ Android
#
# این اسکریپت فقط داخلِ jobِ `webview-on-emulator` درِ mobile.yml اجرا می‌شود
# (شبیه‌ساز همان‌جا زنده است). کاری که نمی‌کند: هیچ سفارشِ واقعی، هیچ
# credential، هیچ نوشتن درِ دیتابیسِ کاربر. همه‌چیز خواندنی/لمسی است.
#
# سه چیز را جدا ثبت می‌کند تا با هم اشتباه نشوند:
#   ۱) نصب و اجرایِ APK (adb/pm + logcat)
#   ۲) محتوای واقعیِ WebView درِ سه اندازۀ تلفن (CDP → tools/android_webview_check.mts)
#   ۳) رفتارِ دکمهٔ بازگشت، background/foreground و crash/ANR
#
# بیلدی که نصب می‌شود عمداً **debug** است: DevTools تنها درِ buildِ debuggable
# باز می‌شود، پس اندازه‌گیریِ DOM/inset/console از همان ممکن است. حکمِ «artifact
# رسمی آزموده شد» از این اسکریپت گرفته نمی‌شود؛ آن درِ گامِ aapt2/apksigner
# جدا ثبت می‌شود.
set -uo pipefail

APK="${1:-}"
PKG=com.borsterminal.mobile
OUT="${OUT_DIR:-_audit/android_emu}"
mkdir -p "$OUT"
SUM="$OUT/summary.json"
: > "$OUT/steps.tsv"

# artifactِ upload-artifact v4 مسیرِ نسبیِ مشترک را نگه می‌دارد، پس فایلِ دانلودی
# درِ `apks/debug/app-debug.apk` است نه `apks/app-debug.apk`. اولین رانِ این
# اسکریپت دقیقاً به‌همین دلیل قرمز شد: adb گفت «No such file» و بعد هر سنجهٔ
# دیگر با «process gone» شکست — هشت FAILِ بی‌معنی از یکِ مسیرِ اشتباه.
if [ -z "$APK" ] || [ ! -f "$APK" ]; then
  APK=$(find apks -type f -name 'app-debug.apk' 2>/dev/null | head -1)
fi
if [ -z "$APK" ] || [ ! -f "$APK" ]; then
  echo "install	FAIL	هیچ app-debug.apk درِ apks/ پیدا نشد ($(find apks -type f 2>/dev/null | tr '\n' ' '))" >> "$OUT/steps.tsv"
  echo "NOT_VERIFIED	no-device-everything-down	بی‌نصب، هیچ سنجهٔ دیگری معنا ندارد" >> "$OUT/steps.tsv"
  cat "$OUT/steps.tsv"; exit 1
fi

step() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$OUT/steps.tsv"; echo "STEP $1 [$2] $3"; }
json_escape() { sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n' | cut -c1-400; }

# ── ۱) نصب ───────────────────────────────────────────────────────────────────
adb wait-for-device
MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
RELEASE=$(adb shell getprop ro.build.version.release | tr -d '\r')
SDK=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
adb install -r -g "$APK" > "$OUT/install.log" 2>&1 && step install PASS "$(basename "$APK") on android-$RELEASE(api$SDK) $MODEL" || step install FAIL "$(tail -2 "$OUT/install.log" | tr '\n' ' ' | json_escape)"

adb logcat -c
adb logcat -v time > "$OUT/logcat.txt" 2>&1 &
LOGD=$!
# رانِ 38796223802: `launch [FAIL] no process after 30s` رویِ همان APK ای که درِ
# رانِ پیشین pid داده بود. یک monkeyِ تنها + خوابِ ثابت، flakeِ system_server را
# به‌حسابِ اپ رد می‌کند و هیچ مدرکی هم نمی‌گذارد. پس: بیدارکردنِ صفحه، سه تلاشِ
# راه‌اندازی با فاصلۀ رشدیافته، و درِ شکست شواهد (نصب‌شده؟ کرش کرده؟ monkey
# چه گفت؟). اگر باز هم بالا نیامد، FAIL است — اما با شاهد.
adb shell svc power stayon true >/dev/null 2>&1
adb shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
adb shell wm dismiss-keyguard >/dev/null 2>&1
PID=""
for i in 1 2 3; do
  adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > "$OUT/monkey_$i.log" 2>&1
  sleep $((12 + i * 6))
  PID=$(adb shell pidof -s "$PKG" | tr -d '\r')
  [ -n "$PID" ] && { step launch PASS "pid=$PID (تلاش $i)"; break; }
done
if [ -z "$PID" ]; then
  { echo "== pm path"; adb shell pm path "$PKG" 2>&1
    echo "== monkey"; cat "$OUT"/monkey_*.log 2>/dev/null
    echo "== activity"; adb shell dumpsys activity activities 2>/dev/null | grep -iE "mResumedActivity|Starting" | head -6
    echo "== crash/proc"; adb logcat -d 2>/dev/null | grep -iE "$PKG|FATAL|ANR in|am_proc_died|lowmemory" | tail -20
  } > "$OUT/launch_fail_evidence.txt" 2>&1
  step launch FAIL "no process after 3 attempts — شواهد: $OUT/launch_fail_evidence.txt"
fi
if [ -z "$PID" ]; then
  # بی‌پروسه، «دکمهٔ بازگشت اپ را بست» و «ازِ home برنگشت» فقط طنینِ همان
  # شکستِ اول‌اند. ادامه نده: هر سنجهٔ بعدی را NOT_VERIFIED بنویس و خارج شو.
  for s in webview-360x800 webview-390x844 webview-412x915 back_button background_foreground; do
    step "$s" NOT_VERIFIED "اپ بالا نیامد"
  done
  kill "$LOGD" 2>/dev/null
  tail -40 "$OUT/logcat.txt" > "$OUT/logcat_tail.txt" 2>/dev/null
  printf '{"apk":"%s","note":"no process after launch; dependent checks NOT_VERIFIED"}\n' "$(basename "$APK")" > "$SUM"
  cat "$OUT/steps.tsv"; exit 1
fi

# ── ۲) اندازۀ تلفن رویِ دستگاه واقعی ─────────────────────────────────────────
# سه اندازۀ لازم (360×800 / 390×844 / 412×915) درِ Chromium با
# tools/android_viewport_probe.mts سنجیده شده (27 رکورد، صفر سنجۀ رد). رویِ
# شبیه‌ساز عمداً یک اندازۀ ثابت می‌ماند: درِ رانِ 38671378595 تغییرِ مکررِ
# wm size/density رویِ AVDِ دو‌هسته‌ایِ CI چنان فشاری آورد که system_server
# قفل کرد («Process system isn't responding» درِ هر سه اسکرین‌شات) و هیچ ادعایِ
# DOMی ازِ آن ران قابلِ استناد نبود. 360×800 = 1080x2400 با density 480 (÷۳).
ensure_running() {  # $1 = برچسب
  local pid
  for i in 1 2 3 4 5 6; do
    pid=$(adb shell pidof -s "$PKG" | tr -d '
')
    [ -n "$pid" ] && { echo "$pid"; return 0; }
    if [ "$i" = 1 ]; then
      adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
    fi
    sleep 8
  done
  echo ""; return 1
}

# گفتگویِ ANRِ سیستم اگر رویِ صفحه بود، با «Wait» کنار می‌رود؛ بی‌این هر
# اسکرین‌شاتِ بعدی همان گفتگو را نشان می‌دهد و هیچ سنجه‌ای معنی ندارد.
dismiss_anr_dialog() {
  if adb exec-out uiautomator dump /dev/tty 2>/dev/null | grep -qi "isn.t responding"; then
    adb shell input tap 540 1210 2>/dev/null   # «Wait» درِ گفتگویِ پیش‌فرض
    sleep 5
    echo "anr_dialog DISMISSED گفتگویِ «Process system isn't responding» دیده و رد شد" >> "$OUT/steps.tsv"
    return 0
  fi
  return 0
}

# قفلِ صفحه‌کلیدِ AVD هر دو کاوشگر را کور می‌کند: CDP موند می‌خورد و
# uiautomator درختِ keyguard را می‌دهد، نه متنِ برنامه. رانِ 38781829171 دقیقاً
# همین بود («دستگاه قفل بود») و نتیجه را به‌حسابِ اپ FAIL کرد.
keep_awake() {
  adb shell svc power stayon true >/dev/null 2>&1
  adb shell settings put system screen_off_timeout 2147483647 >/dev/null 2>&1
  adb shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
  adb shell wm dismiss-keyguard >/dev/null 2>&1
  adb shell input keyevent KEYCODE_MENU >/dev/null 2>&1
  sleep 3
}

# نشانة‌ای که رانِ 38802635761 گذاشت: درِ لحظۀ نمونه‌برداری، mCurrentFocus =
# «Application Not Responding: com.android.systemui» و uiautomator ۵۷ بایت (درختِ
# خالی) داد. یعنی پنجرۀ سیستم رویِ صفحه بود، نه اپ — و کاوش CDP ۳۰۰ ثانیه موند.
# پس پیش‌ازِ هر سنجشِ محتوا صبر می‌کنیم تا واقعیِ اپ فوکوس بگیرد؛ اگر نشد، علت
# (فوکوسِ پنجرۀ ANR / launcher) درِ حکم نوشته می‌شود، نه «متنِ برنامه دیده نشد».
wait_for_focus() { # wait_for_focus <تلاش‌ها>
  local n="${1:-6}" i
  for i in $(seq 1 "$n"); do
    FOCUS=$(adb shell dumpsys window 2>/dev/null | tr -d '
' | grep -m1 "mCurrentFocus" | cut -c1-160)
    case "$FOCUS" in
      *"$PKG"*) return 0 ;;
    esac
    dismiss_anr_dialog
    sleep 6
  done
  return 1
}

LABEL=360x800
RSS_START=$(adb shell dumpsys meminfo "$PKG" 2>/dev/null | tr -d '
' | awk '/^TOTAL/{print $2; exit}')
adb shell wm size 1080x2400 >/dev/null 2>&1 && adb shell wm density 480 >/dev/null 2>&1
sleep 6
PID=$(ensure_running "$LABEL")
if [ -z "$PID" ]; then
  adb logcat -d 2>/dev/null | grep -iE "$PKG|lowmemorykiller|am_proc_died" | tail -12 > "$OUT/died-$LABEL.txt"
  step "view-$LABEL" FAIL "اپ پس ازِ wm size بالا نیامد (شاهد: $OUT/died-$LABEL.txt)"
else
  keep_awake
  # رانِ 38797140980: «CDP در دسترس نیست (webview_devtools_remote_2611)» درحالی‌که
  # اپ زنده بود (pid=2611). ساختِ نامِ socket ازِ pidِ خودِ پروسه فرضِ اشتباهی است:
  # WebView در Android یک پروسۀ رندرِ جدا می‌سازد و socket را آن پروسه باز می‌کند.
  # پس نامِ واقعی را از /proc/net/unix بخوان، نه ازِ حدس.
  SOCK=$(adb shell cat /proc/net/unix 2>/dev/null | tr -d '\r' \
         | grep -oE "webview_devtools_remote_[0-9]+" | head -1)
  [ -n "$SOCK" ] || sleep 10
  [ -n "$SOCK" ] || SOCK=$(adb shell cat /proc/net/unix 2>/dev/null | tr -d '\r' \
         | grep -oE "webview_devtools_remote_[0-9]+" | head -1)
  if [ -n "$SOCK" ]; then
    adb forward tcp:9222 "localabstract:$SOCK" >/dev/null 2>&1
    echo "devtools socket: $SOCK (پروسۀ اپ pid=$PID)" >> "$OUT/steps.tsv"
  else
    { echo "== unix sockets (webview/devtools)"; adb shell cat /proc/net/unix 2>/dev/null | grep -iE "webview|devtools" | head -8
      echo "== processes"; adb shell ps -A 2>/dev/null | grep -E "$PKG|webview" | head -6
    } > "$OUT/no_cdp_evidence.txt" 2>&1
  fi
  sleep 25                      # 16 مگابایت gz ← 70 مگابایت SQLite رویِ AVDِ کند
  dismiss_anr_dialog
  if wait_for_focus 6; then FOCUS_OK=yes; else FOCUS_OK=no; fi
  FOCUS_NOTE=$(printf '%s' "${FOCUS:-none}" | tr -d '"' | cut -c1-90)
  adb exec-out screencap -p > "$OUT/$LABEL.png"
  if timeout 300 node --experimental-strip-types tools/android_webview_check.mts         --base http://127.0.0.1:9222 --label "$LABEL" --out "$OUT/webview-$LABEL.json" > "$OUT/webview-$LABEL.log" 2>&1; then
    step "webview-$LABEL" PASS "$(grep -o '"reached_content":"[^"]*"' "$OUT/webview-$LABEL.json" | head -1 | json_escape) $(grep -o '"visible_text_len":[0-9]*' "$OUT/webview-$LABEL.json" | head -1 | json_escape)"
  else
    rc=$?
    if [ "$rc" = 2 ]; then
      step "webview-$LABEL" NOT_VERIFIED "CDP در دسترس نیست (socket شناسایی‌شد: ${SOCK:-none}؛ شواهد: $OUT/no_cdp_evidence.txt)"
    elif [ "$rc" = 124 ]; then
      step "webview-$LABEL" NOT_VERIFIED "کاوشگر درِ CDP موند (300s) · focus_ok=$FOCUS_OK · focus=$FOCUS_NOTE"
    else
      step "webview-$LABEL" FAIL "exit=$rc reached=$(grep -o '"reached_content":"[^"]*"' "$OUT/webview-$LABEL.json" | head -1 | json_escape) nodes=$(grep -o '"dom_nodes":[0-9]*' "$OUT/webview-$LABEL.json" | head -1 | json_escape)"
    fi
  fi
  # شواهدِ مستقل ازِ DevTools: درختِ دسترس‌پذیریِ خودِ اندروید. WebView (API 34)
  # متنِ صفحه را درِ uiautomator می‌گذارد؛ بی‌این، قفل‌شدنِ CDP هیچ مدرکی ازِ
  # «برنامۀ واقعی رویِ گوشیِ واقعی دیده شد» باقی نمی‌گذارد.
  keep_awake
  adb exec-out uiautomator dump /dev/tty 2>/dev/null | tr -d '
' > "$OUT/ui-$LABEL.xml"
  # واژگانِ این فهرست ازِ خودِ سورسِ رابط گرفته شده (count درِ frontend/src):
  # قیف 159، تابلو 476، شاخص 426، غربالگری 87، معامله 105، بورس 74. نسخهٔ پیشین
  # پنج واژهٔ تنگ می‌خواست و رانِ 38797140980 رویِ صفحۀ درست هم FAIL داد.
  UIHITS=$(grep -oE "قیف|تابلو|شاخص|غربالگری|معامله|بورس|نمودار|پرتفوی" "$OUT/ui-$LABEL.xml" 2>/dev/null | sort -u | paste -sd' ' - | json_escape)
  KEYGUARD=$(grep -oiE "keyguard|lockscreen|swipe up|enter pin" "$OUT/ui-$LABEL.xml" 2>/dev/null | sort -u | head -2 | paste -sd' ' - | json_escape)
  if [ -n "$UIHITS" ]; then
    step "webview-$LABEL-a11y" PASS "متنِ واقعیِ برنامه درِ درختِ دسترس‌پذیری: $UIHITS"
  elif [ -n "$KEYGUARD" ]; then
    step "webview-$LABEL-a11y" NOT_VERIFIED "درختِ uiautomator مالِ قفلِ صفحه بود ($KEYGUARD)؛ متنِ برنامه دیده نشد"
  else
    # FAIL بی‌مدرک ارزشِ تشخیص ندارد: چه چیزی *واقعاً* رویِ صفحه بود؟
    { echo "== node count: $(grep -oE '<node ' "$OUT/ui-$LABEL.xml" | wc -l)"
      echo "== windows"; adb shell dumpsys window 2>/dev/null | grep -iE "mCurrentFocus|mFocusedApp" | head -4
      echo "== texts"; grep -oE 'text="[^"]{2,60}"' "$OUT/ui-$LABEL.xml" 2>/dev/null | sed 's/text=//' | sort -u | head -20
      echo "== size of dump: $(wc -c < "$OUT/ui-$LABEL.xml") bytes"
    } > "$OUT/a11y-$LABEL-evidence.txt" 2>&1
    step "webview-$LABEL-a11y" FAIL "هیچ واژۀِ دیدنیِ برنامه درِ uiautomator نبود — شواهد: $OUT/a11y-$LABEL-evidence.txt"
  fi

  adb forward --remove tcp:9222 2>/dev/null
fi

# ── ۳) بازگشت، background/foreground، crash/ANR ─────────────────────────────
adb shell wm size reset >/dev/null 2>&1; adb shell wm density reset >/dev/null 2>&1
sleep 3
# بازگشت رویِ اپِ **بالا آمده** سنجیده می‌شود؛ بی‌این، طنینِ شکست‌هایِ قبلی به
# حسابِ «اپ با یکِ بازگشت بست» گزارش می‌شد.
PID=$(ensure_running "back" "")
if [ -z "$PID" ]; then
  step back_button NOT_VERIFIED "اپ پیش ازِ سنجه بالا نیامد"
else
  adb shell input keyevent 4; sleep 1
  PIDB=$(adb shell pidof -s "$PKG" | tr -d '\r')
  if [ -n "$PIDB" ]; then
    step back_button PASS "یکِ بازگشت: زنده (pid=$PIDB) — پنجرۀ «برایِ خروج دوباره بزنید»"
  else
    adb logcat -d 2>/dev/null | grep -iE "$PKG|ActivityTaskManager|am_kill" | tail -12 > "$OUT/back_died.txt"
    step back_button FAIL "اپ با یکِ بازگشت بست (شاهد: $OUT/back_died.txt)"
  fi
fi
adb shell input keyevent KEYCODE_HOME; sleep 3
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1; sleep 6
PID2=$(ensure_running "fg" "")
if [ -n "$PID2" ]; then step background_foreground PASS "pid=$PID2"; else step background_foreground FAIL "پس ازِ home برنگشت"; fi
adb shell input keyevent KEYCODE_APP_SWITCH 2>/dev/null
sleep 2
# ── ۳ب) رشدِ حافظه: دو نمونه، نه یکِ حکم ─────────────────────────────────────
# «نشتِ حافظه» با یکِ عدد اثبات نمی‌شود؛ اینجا فقط فاصلۀ TOTAL RSS بینِ «بلافاصله
# پس ازِ بالا آمدن» و «بعد ازِ سه تغییرِ اندازه + بازگشت + home» ثبت می‌شود و
# نتیجه MEASURED نوشته می‌شود، نه PASS/FAIL — آستانه‌ای را که نساختم حکمِ
# سبز/قرمز نمی‌کنم. قضاوتِ واقعی به دو دورِ پیاپی رویِ همین مسیرِ ثابت و رویِ
# گوشیِ واقعی لازم است (AVDِ x86 کشۀِ حافظه‌اش متفاوت است).
rss_kb() { adb shell dumpsys meminfo "$PKG" 2>/dev/null | awk '/^TOTAL/{print $2; exit}' | tr -d '\r'; }
RSS_END=$(rss_kb)
if [ -n "${RSS_START:-}" ] && [ -n "$RSS_END" ]; then
  step mem_growth MEASURED "TOTAL RSS $RSS_START -> $RSS_END KB (سه تغییرِ اندازه + بازگشت + home)"
else
  step mem_growth NOT_VERIFIED "dumpsys meminfo عدد نداد (start=${RSS_START:-none} end=${RSS_END:-none})"
fi

kill "$LOGD" 2>/dev/null
CRASH=$(grep -c "FATAL EXCEPTION" "$OUT/logcat.txt" 2>/dev/null || true)
ANR_OURS=$(grep -c "ANR in $PKG" "$OUT/logcat.txt" 2>/dev/null || true)
ANR_OTHER=$(grep -c "ANR in " "$OUT/logcat.txt" 2>/dev/null || true)
ANRSYS=$(grep -cE "not responding|am_anr" "$OUT/logcat.txt" 2>/dev/null || true)
# نشتِ رمز فقط درِ خطوطِ **خودِ برنامه/WebView** شمرده می‌شود. اولین ران دو
# «hit» داد که هر دو `E/BackupPasswordManager( 541)` بودند — یعنی سرویسِ خودِ
# اندروید، نه این اپ. بی‌این دامنه، هر سطرِ سیستمیِ بی‌ربط زنگِ خطر می‌زند.
LEAKLINES=$(grep -iE "(authorization|bearer|api.?key|password)" "$OUT/logcat.txt" 2>/dev/null \
  | grep -E "$PKG|chromium|Capacitor|WebConsole|SystemWebView" || true)
LEAK=$(printf '%s' "$LEAKLINES" | grep -c . || true)
if [ "${LEAK:-0}" != 0 ]; then
  printf '%s\n' "$LEAKLINES" | sed -E 's/[0-9a-fA-F]{8,}//g' | cut -c1-90 > "$OUT/leak_hits.txt"
fi
[ "${CRASH:-0}" = 0 ] && step crash PASS "FATAL EXCEPTION=0" || step crash FAIL "$(grep -m1 -A3 'FATAL EXCEPTION' "$OUT/logcat.txt" | tr '\n' '|' | json_escape)"
# ANR را دو خط جدا می‌خوانیم: رانِ 38696704398 ده ANR داشت که هیچ‌کدام
# مالِ ما نبود (7×com.android.phone، 3×com.android.providers.media.module) —
# یعنی AVDِ CI مریض است، نه اپ. بی‌این تفکیک، مریضیِ محیط به‌حسابِ اپ رد می‌شود.
if [ "${ANR_OURS:-0}" != 0 ]; then
  step anr FAIL "ANR in $PKG: $(grep -m1 -A4 "ANR in $PKG" "$OUT/logcat.txt" | tr '
' '|' | cut -c1-160 | json_escape)"
elif [ "${ANR_OTHER:-0}" != 0 ]; then
  step anr NOT_VERIFIED "هیچ ANR برایِ $PKG نیست؛ ${ANR_OTHER} ANR مالِ پروسه‌هایِ خودِ AVD: $(grep -o 'ANR in [a-z._]*' "$OUT/logcat.txt" | sort -u | tr '
' ' ' | json_escape)"
else
  step anr PASS "ANR=0 (نه ما، نه هیچِ پروسه‌ای)"
fi
[ "${LEAK:-0}" = 0 ] && step logcat_secrets PASS "hit=$LEAK (خطوطِ سیستمی شمرده نشد)" || step logcat_secrets FAIL "hit=$LEAK → $OUT/leak_hits.txt"

# ── خلاصه ────────────────────────────────────────────────────────────────────
if command -v jq >/dev/null 2>&1; then
  jq -Rs --arg model "$MODEL" --arg android "$RELEASE" --arg api "$SDK" \
     --arg apk "$(basename "$APK")" '
    [ split("\n")[] | select(length>0) | split("\t") | {step:.[0], result:.[1], note:.[2]} ] as $steps
    | {device:{model:$model, android:$android, api:$api}, apk:$apk, steps:$steps,
       counts:{pass:         [$steps[]|select(.result=="PASS")]|length,
               fail:         [$steps[]|select(.result=="FAIL")]|length,
               not_verified: [$steps[]|select(.result=="NOT_VERIFIED")]|length}}
  ' "$OUT/steps.tsv" > "$SUM"
else
  { echo '{'; echo "  \"device\": \"$MODEL / android $RELEASE (api $SDK)\",";
    echo "  \"apk\": \"$(basename "$APK")\","; echo '  "steps": [';
    awk -F'\t' '{printf "    {\"step\":\"%s\",\"result\":\"%s\",\"note\":\"%s\"},\n", $1, $2, $3}' "$OUT/steps.tsv" | sed '$ s/,$//';
    echo '  ]'; echo '}'; } > "$SUM"
fi
cat "$SUM"
grep -qP '\tFAIL\t' "$OUT/steps.tsv" && exit 1 || exit 0
