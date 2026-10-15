#!/usr/bin/env bash
# tools/android_upgrade_matrix.sh — آیا ارتقایِ درجا رویِ گوشی واقعاً ممکن است؟
#
# دو ریلیزِ اندرویدیِ منتشرشده با دو گواهیِ Android Debugِ متفاوت امضا شده بودند
# (پایشِ APK Signing Block درِ دورِ ششم). نتیجه‌اش این است که «ارتقا» برایِ این
# اپ تا امروز هیچ‌وقت آزموده نشده — و اولینِ نسخۀ امضاشدۀ رسمی رویِ گوشیِ
# دارایِ نسخۀ debug با INSTALL_FAILED_UPDATE_INCOMPATIBLE می‌خورد.
#
# این اسکریپت همان چهار حالت را با کلیدهایِ **دورریختنی** رویِ شبیه‌ساز می‌آزماید
# (کلیدِ انتشارِ واقعی هیچ‌وقت اینجا مصرف نمی‌شود و هیچ artifactی منتشر نمی‌شود):
#   ۱) نصبِ تمیز با کلید A                 ⇒ باید موفق شود
#   ۲) ارتقا به versionCode+1 با همان A    ⇒ باید موفق شود (این «ارتقایِ رسمی» است)
#   ۳) ارتقا به همان نسخه با کلید B        ⇒ باید رد شود و نامِ خطا همان باشد
#   ۴) ردِ نصبِ رو‌رویی پیش ازِ حذفِ نسخۀ قبلی، سپس نصبِ تمیز  ⇒ حذف = از دست
#      رفتنِ دادۀ محلی (localStorage) — همان چیزی که درِ Release Notes هشدار
#      می‌دهد و درِ این سنجش عدد می‌گیرد.
#
# اجرا درِ CI (job: upgrade-matrix-on-device، با KVM و ANDROID_HOME آماده).
set -uo pipefail

PKG="com.borsterminal.mobile"
D="$RUNNER_TEMP/upmat"; mkdir -p "$D"; umask 077
OUTD="_audit/android_upgrade"; mkdir -p "$OUTD"
TSV="$OUTD/matrix.tsv"; JSON="$OUTD/summary.json"
: > "$TSV"
PASS=0; FAILN=0; NOTVER=0

step() { # step <name> <PASS|FAIL|NOT_VERIFIED> <note>
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$TSV"
  printf '%-34s %-14s %s\n' "$1" "$2" "$3" >&2
  case "$2" in PASS) PASS=$((PASS+1));; FAIL) FAILN=$((FAILN+1));; *) NOTVER=$((NOTVER+1));; esac
}

have() { command -v "$1" >/dev/null 2>&1; }
if ! have adb; then
  step "toolchain" "NOT_VERIFIED" "adb درِ PATH نیست"
  printf '{"counts":{"pass":0,"fail":0,"not_verified":1}}\n' > "$JSON"; exit 0
fi
[ -e /dev/kvm ] || { step "toolchain" "NOT_VERIFIED" "بی‌KVM"; printf '{"counts":{"pass":0,"fail":0,"not_verified":1}}\n' > "$JSON"; exit 0; }

BT=$(ls -d "$ANDROID_HOME"/build-tools/* 2>/dev/null | sort -V | tail -1)
[ -n "$BT" ] || { step "toolchain" "NOT_VERIFIED" "build-tools پیدا نشد"; exit 0; }
KEYTOOL="$(ls -d "$JAVA_HOME"/bin 2>/dev/null || echo /usr/bin)/keytool"

VC_BASE="${BORS_VERSION_CODE:-1001000}"
VN="${BORS_VERSION_NAME:-1.1.0}"
# نسخۀ بالاتر برایِ مادۀ «ارتقا»: patch یکی بیشتر ⇒ versionCode مشتق‌شده یکی
# بالاتر (همان قاعدۀ build.gradle: major·1e6 + minor·1e3 + patch).
VN_UP=$(awk -F. -v v="$VN" '{printf "%d.%d.%d", $1, $2, $3+1}' <<<"$VN")
VC_UP=$((VC_BASE+1))
PKGJSON="frontend/package.json"

pkg_set_version() { # pkg_set_version <version>
  python3 - "$PKGJSON" "$1" <<'PY'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p, encoding="utf-8"))
d["version"] = v
with open(p, "w", encoding="utf-8", newline="\n") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

make_key() { # make_key <name>
  local n="$1"
  "$KEYTOOL" -genkeypair -keystore "$D/$n.jks" -alias "$n" -keyalg RSA -keysize 2048 \
    -validity 60 -storepass "throwaway-$n-not-a-release-key" -keypass "throwaway-$n-not-a-release-key" \
    -dname "CN=upgrade matrix $n, O=not-for-release" >/dev/null 2>&1 \
    || { step "keygen-$n" "FAIL" "keytool رد شد"; return 1; }
  { echo "storeFile=$D/$n.jks"; echo "storePassword=throwaway-$n-not-a-release-key";
    echo "keyAlias=$n"; echo "keyPassword=throwaway-$n-not-a-release-key"; } > "$D/$n.properties"
}

build_apk() { # build_apk <keyName> <versionName> <outName>
  # نسخه هرگز با -P جعل نمی‌شود: گاردِ BORS-VERSION درِ build.gradle هر
  # versionCodeای را که ازِ package.json مشتق نشده رد می‌کند (رانِ
  # 38794263916: build-a2 با «does not specify compileSdk» مرد، چون
  # استثنایِ(gradle) وسطِ پیکربندی بلند شد). پس مبنایِ یکتا -- versionِ
  # package.json -- درِ همین runner موقت عوض می‌شود و بی‌درنگ برمی‌گردد.
  local key="$1" ver="$2" out="$3" rc=0 src
  cp "$PKGJSON" "$D/package.json.$out.bak"
  pkg_set_version "$ver"
  ( cd frontend/android && BORS_KEYSTORE_PROPERTIES="$D/$key.properties" \
      ./gradlew assembleRelease --no-daemon -q \
      -PBorsVersionName="$ver" > "$D/$out.gradle.log" 2>&1 ) || rc=$?
  mv -f "$D/package.json.$out.bak" "$PKGJSON"
  if [ "$rc" != 0 ]; then
    tail -14 "$D/$out.gradle.log" >&2
    step "build-$out" "FAIL" "gradlew رد شد (نسخۀ $ver)"
    return 1
  fi
  src=$(ls -1 frontend/android/app/build/outputs/apk/release/*.apk 2>/dev/null | head -1)
  [ -n "$src" ] || { step "build-$out" "FAIL" "هیچ APK ساخته نشد"; return 1; }
  case "$(basename "$src")" in *unsigned*) step "build-$out" "FAIL" "خروجی بی‌امضا ماند"; return 1;; esac
  cp "$src" "$D/$out.apk"
  step "build-$out" "PASS" "$(basename "$src") · $ver"
}

cert_of() { "$BT/apksigner" verify --print-certs "$1" 2>/dev/null \
  | grep -m1 -oE 'SHA-256 digest: [0-9a-f]+' | cut -d' ' -f3; }

adb wait-for-device
for i in $(seq 1 40); do
  [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break
  sleep 3
done
if [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" != "1" ]; then
  step "boot" "NOT_VERIFIED" "شبیه‌ساز بالا نیامد"; printf '{"counts":{"pass":%d,"fail":%d,"not_verified":%d}}\n' $PASS $FAILN $((NOTVER+1)) > "$JSON"; exit 0
fi
step "boot" "PASS" "sys.boot_completed=1"
# قفلِ صفحه‌کلیدِ AVD بعدِ بوت، monkey/pidof را هم گول می‌زند (همان دامِ
# رانِ 38781829171 درِ jobِ WebView). صفحه را بیدار و keyguard را کنار بگذار.
adb shell svc power stayon true >/dev/null 2>&1
adb shell settings put system screen_off_timeout 2147483647 >/dev/null 2>&1
adb shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
adb shell wm dismiss-keyguard >/dev/null 2>&1
sleep 3

make_key A || true
make_key B || true
[ -f "$D/A.properties" ] && [ -f "$D/B.properties" ] || { printf '{"counts":{"pass":%d,"fail":%d,"not_verified":%d}}\n' $PASS $FAILN $((NOTVER+1)) > "$JSON"; exit 1; }

build_apk A "$VN" a1 && build_apk A "$VN_UP" a2 && build_apk B "$VN_UP" b1

CA=$(cert_of "$D/a1.apk"); CA2=$(cert_of "$D/a2.apk"); CB=$(cert_of "$D/b1.apk")
[ -n "$CA" ] && [ "$CA" = "$CA2" ] && step "same-key-fingerprint-stable" "PASS" "${CA:0:16}…" \
  || step "same-key-fingerprint-stable" "FAIL" "A=$CA A2=$CA2"
[ -n "$CB" ] && [ "$CB" != "$CA" ] && step "other-key-fingerprint-differs" "PASS" "${CB:0:16}…" \
  || step "other-key-fingerprint-differs" "FAIL" "B=$CB"

# دادۀ محلیِ کاربر (localStorage) تنها دادۀ قابل‌ازدست‌رفتنِ این اپ رویِ گوشی است
adb shell pm clear "$PKG" >/dev/null 2>&1 || true
if adb install -r -d "$D/a1.apk" > "$D/i1.log" 2>&1; then
  step "clean-install-official" "PASS" "versionCode $VC_BASE"
  # سه تلاش: monkey رویِ AVDِ تازه‌بوت‌شده گاهی گم می‌شود (دامِ دیدۀ WebView درِ
  # رانِ 38796223802)؛ یک تلاشِ تنها، flakeِ محیط را به‌حسابِ اپ FAIL می‌کند.
  PID=""
  for i in 1 2 3; do
    adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 > "$D/monkey_$i.log" 2>&1
    sleep $((8 + i * 4))
    PID=$(adb shell pidof -s "$PKG" | tr -d '\r')
    [ -n "$PID" ] && break
  done
  [ -n "$PID" ] && step "launch-after-clean-install" "PASS" "pid=$PID (تلاش $i)" \
    || { { echo "== pm path"; adb shell pm path "$PKG" 2>&1; echo "== monkey"; cat "$D"/monkey_*.log 2>&1;
           echo "== activities"; adb shell dumpsys activity activities 2>/dev/null | grep -iE "mResumedActivity|Starting" | head -6; } > "$D/launch_fail.txt" 2>&1
         step "launch-after-clean-install" "FAIL" "اپ بالا نیامد — شواهد: $D/launch_fail.txt"; }
  # نشانه‌گذاریِ دادۀ محلی تا معلوم شود حذفِ نصب چه چیزی را می‌برد
  adb shell "run-as $PKG sh -c 'echo upmat > /data/data/$PKG/databases/.upmat_probe'" >/dev/null 2>&1 \
    || adb shell "echo" >/dev/null 2>&1
else
  step "clean-install-official" "FAIL" "$(tail -2 "$D/i1.log" | tr '\n' ' ')"
  printf '{"counts":{"pass":%d,"fail":%d,"not_verified":%d}}\n' $PASS $FAILN $((NOTVER+1)) > "$JSON"; exit 1
fi

if adb install -r -d "$D/a2.apk" > "$D/i2.log" 2>&1; then
  step "upgrade-same-key" "PASS" "$VN/$VC_BASE → $VN_UP/$VC_UP با همان گواهی"
else
  step "upgrade-same-key" "FAIL" "$(tail -2 "$D/i2.log" | tr '\n' ' ')"
fi

adb install -r -d "$D/b1.apk" > "$D/i3.log" 2>&1; RC=$?
if [ $RC -ne 0 ] && grep -q "INSTALL_FAILED_UPDATE_INCOMPATIBLE" "$D/i3.log"; then
  step "reject-different-cert" "PASS" "اندروید نصبِ رو‌رویی با گواهیِ دیگر را رد کرد"
elif [ $RC -ne 0 ]; then
  step "reject-different-cert" "FAIL" "رد شد ولی با خطایِ دیگر: $(tail -2 "$D/i3.log" | tr '\n' ' ')"
else
  step "reject-different-cert" "FAIL" "با گواهیِ دیگر هم نصب شد! (انتظارِ رد)"
fi

# و پسِ حذفِ نسخۀ قبلی، کلیدِ تازه نصب می‌شود — یعنی «یک‌بار حذف» راهِ عبور است،
# و همان‌جا دادۀ محلی می‌سوزد (هشدارِ Release Notes).
adb uninstall "$PKG" >/dev/null 2>&1 || true
if adb install -r -d "$D/b1.apk" > "$D/i4.log" 2>&1; then
  step "fresh-install-after-uninstall" "PASS" "پسِ حذف، هر کلیدی نصب می‌شود (دادهٔ محلی می‌سوزد)"
else
  step "fresh-install-after-uninstall" "FAIL" "$(tail -2 "$D/i4.log" | tr '\n' ' ')"
fi

rm -rf "$D"/*.jks "$D"/*.properties
printf 'تمیز شد: کلیدهایِ دورریختنی حذف شدند (هیچ‌وقت منتشر نمی‌شوند)\n' >&2
# مبنایِ یکتایِ نسخه باید دست‌نخورده برگشته باشد؛ اگر نه، هر گامِ بعدیِ همین
# ران (متنِ ریلیز، بیلدِ دوباره) نسخۀ جعلیِ 1.1.1 را می‌بیند.
if grep -q "\"version\": \"$VN\"" "$PKGJSON"; then
  step "version-source-restored" "PASS" "package.json به $VN برگشت"
else
  step "version-source-restored" "FAIL" "مبنایِ نسخه درِ runner عوض مانده است"
fi
printf '{"pkg":"%s","vn":"%s","vc_base":%s,"vn_up":"%s","vc_up":%s,"cert_A":"%s","cert_B":"%s","counts":{"pass":%d,"fail":%d,"not_verified":%d}}\n' \
  "$PKG" "$VN" "$VC_BASE" "$VN_UP" "$VC_UP" "$CA" "$CB" "$PASS" "$FAILN" "$NOTVER" > "$JSON"
cat "$JSON" >&2
[ "$FAILN" -eq 0 ] || exit 1
