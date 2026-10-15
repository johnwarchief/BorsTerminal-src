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
adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
sleep 30
PID=$(adb shell pidof -s "$PKG" | tr -d '\r')
if [ -n "$PID" ]; then step launch PASS "pid=$PID"; else step launch FAIL "no process after 30s"; fi
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

# ── ۲) سه اندازۀ تلفن: wm size درِ پیکسل، CSS viewport درِ dp ────────────────
# 360×800 / 390×844 / 412×915 هر سه با density 480 (÷۳) ⇒ px = dp×۳
#
# تغییرِ اندازه درِ اندروید یعنی configuration change و **ازنویدِ Activity**؛
# پس pid عوض می‌شود. اولین رانِ واقعی این را «process gone» خواند و رد کرد، در
# حالی که اپ سالم بود. اینجا هر اندازه با اطمینان ازِ بالا بودنِ اپ سنجیده
# می‌شود و «مُرد» از «ازنوید بالا آمد» جدا نوشته می‌شود.
ensure_running() {  # $1 = برچسب
  local pid old=$2
  for i in 1 2 3 4 5 6; do
    pid=$(adb shell pidof -s "$PKG" | tr -d '\r')
    [ -n "$pid" ] && { echo "$pid"; return 0; }
    if [ "$i" = 1 ]; then
      adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1
    fi
    sleep 8
  done
  echo ""; return 1
}

for pair in "1080x2400 360x800" "1170x2532 390x844" "1236x2745 412x915"; do
  set -- $pair
  PX=$1; LABEL=$2
  OLD_PID=$(adb shell pidof -s "$PKG" | tr -d '\r')
  adb shell wm size "$PX" && adb shell wm density 480
  sleep 6
  PID=$(ensure_running "$LABEL" "$OLD_PID")
  if [ -z "$PID" ]; then
    adb logcat -d 2>/dev/null | grep -iE "$PKG|lowmemorykiller|am_proc_died" | tail -12 > "$OUT/died-$LABEL.txt"
    step "view-$LABEL" FAIL "اپ پس ازِ wm size بالا نیامد (شاهد: $OUT/died-$LABEL.txt)"
    continue
  fi
  [ -n "$OLD_PID" ] && [ "$OLD_PID" != "$PID" ] && step "view-$LABEL-resume" PASS "pid عوض شد ($OLD_PID → $PID) = ازنویدِ Activity با تغییرِ اندازه، نه مرگ"
  adb forward tcp:9222 "localabstract:webview_devtools_remote_$PID" 2>/dev/null
  adb exec-out screencap -p > "$OUT/$LABEL.png"
  if node --experimental-strip-types tools/android_webview_check.mts \
        --base http://127.0.0.1:9222 --label "$LABEL" --out "$OUT/webview-$LABEL.json" > "$OUT/webview-$LABEL.log" 2>&1; then
    step "webview-$LABEL" PASS "$(grep -o '"visible_text_len":[0-9]*' "$OUT/webview-$LABEL.json" | head -1 | json_escape)"
  else
    rc=$?
    [ "$rc" = 2 ] && step "webview-$LABEL" NOT_VERIFIED "CDP در دسترس نیست (webview_devtools_remote_$PID)" \
      || step "webview-$LABEL" FAIL "exit=$rc: $(tail -3 "$OUT/webview-$LABEL.log" | tr '\n' ' ' | json_escape)"
  fi
  adb forward --remove tcp:9222 2>/dev/null
done

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
kill "$LOGD" 2>/dev/null
CRASH=$(grep -c "FATAL EXCEPTION" "$OUT/logcat.txt" 2>/dev/null || true)
ANR=$(grep -c "ANR in $PKG" "$OUT/logcat.txt" 2>/dev/null || true)
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
[ "${ANR:-0}" = 0 ] && step anr PASS "ANR=0" || step anr FAIL "ANR in $PKG"
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
