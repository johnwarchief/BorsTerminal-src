#!/usr/bin/env bash
# scripts/android_release_key_ceremony.sh — مراسمِ کلیدِ امضایِ اندروید، رویِ دستگاهِ مالک
#
# چرا این اسکریپت هست: نسخۀ رسمیِ اندروید باید با یکِ keystoreِ **پایدار** امضا
# شود. اگر کلید عوض شود، گواهیِ APK عوض می‌شود و اندروید نصبِ رو‌رویی را رد
# می‌کند (INSTALL_FAILED_UPDATE_INCOMPATIBLE) — همان چیزی که درِ دو ریلیزِ
# منتشرشده اتفاق افتاد: هر دو با CN=Android Debug و با گواهیِ متفاوتِ ساخته
# خودِ CI بودند، پس هیچ‌وقت ارتقایِ درجا ممکن نبود.
#
# این اسکریپت کلید را **نمی‌سازد مگر با دستورِ صریحِ شما**، رمز را درِ هیچ فرمانِ
# قابل‌مشاهده‌ای (argv) یا لاگی نمی‌نویسد، و هیچ‌وقت به debug.keystore دست نمی‌زند.
#
# مراحل (به همین ترتیب اجرا کنید):
#   bash scripts/android_release_key_ceremony.sh keygen
#   bash scripts/android_release_key_ceremony.sh backup --to /media/usb/bors-keys
#   bash scripts/android_release_key_ceremony.sh verify-backup --from /media/usb/bors-keys/<بسته>
#   bash scripts/android_release_key_ceremony.sh restore --from /media/usb/bors-keys/<بسته>
#   bash scripts/android_release_key_ceremony.sh publish-secrets
#   bash scripts/android_release_key_ceremony.sh fingerprint
#
# contractِ secret‌ها دقیقاً همان چیزی است که .github/workflows/mobile.yml می‌خواند:
#   ANDROID_RELEASE_KEYSTORE_B64   = base64ِ خودِ keystore (تک‌خط)
#   ANDROID_RELEASE_KEYSTORE_PROPS = سه سطر: storePassword / keyAlias / keyPassword
# (storeFile را workflow خودش می‌نویسد؛ درِ این secret نزنید.)
set -euo pipefail

KEY_DIR="${BORS_ANDROID_KEY_DIR:-$HOME/.bors_android_keys}"
KS="$KEY_DIR/bors-android-release.jks"
KS_PASS_FILE="$KEY_DIR/.storepass"
META="$KEY_DIR/meta.env"
REPO="${BORS_ANDROID_REPO:-johnwarchief/BorsTerminal-src}"
ALIAS_DEFAULT="bors"

umask 077

die() { printf '%s\n' "ERR: $*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "«$1» پیدا نشد. JDK 17+ (keytool)$( [ "$1" = gh ] && echo ' و GitHub CLI' ) لازم است."
}

ask_pass() {
  # رمز فقط درِ حافظۀ همین shell می‌ماند و به argv هیچ فرمانی نمی‌رود.
  local prompt="$1" out=""
  if [ -t 0 ]; then
    read -r -s -p "$prompt" out; printf '\n' >&2
  else
    die "ورودیِ تعاملی لازم است (رمز را درِ pipe نمی‌خوانیم). این اسکریپت را درِ ترمینال اجرا کنید."
  fi
  printf '%s' "$out"
}

require_keytool() { need keytool; }

require_local_key() { [ -f "$KS" ] || die "کلید درِ $KS نیست. اول: bash $0 keygen"; }

meta_get() { [ -f "$META" ] || return 0; sed -n "s/^$1=//p" "$META" | head -1; }

cmd_keygen() {
  need keytool
  [ -e "$KS" ] && die "کلید از قبل هست: $KS — کلیدِ جدید به‌جایِ کلیدِ انتشارِ قبلی نسازید. برایِ انتشارِ بعدی همان کلید ثابت می‌ماند."
  mkdir -p "$KEY_DIR"
  local sp kp alias days
  sp="$(ask_pass 'رمزِ keystore (handoff: هیچ‌جا چاپ نمی‌شود): ')"
  [ -n "$sp" ] || die "رمزِ خالی مجاز نیست"
  printf 'رمزِ کلیدِ خصوصی معمولاً همان رمزِ keystore است؛ Enter برایِ همان، یا رمزِ تازه بنویسید: ' >&2
  if [ -t 0 ]; then read -r -s kp; printf '\n' >&2; fi
  [ -n "${kp:-}" ] || kp="$sp"
  printf 'نامِ مستعارِ کلید (Enter = %s): ' "$ALIAS_DEFAULT" >&2
  read -r alias; alias="${alias:-$ALIAS_DEFAULT}"
  days=9125   # 25 سال — کلیدِ انتشارِ یکِ اپ باید ازِ خودِ اپ عمرِ بیشتر داشته باشد
  BORS_SP="$sp" BORS_KP="$kp" keytool -genkeypair \
    -keystore "$KS" -alias "$alias" -keyalg RSA -keysize 4096 -validity "$days" \
    -storepass:env BORS_SP -keypass:env BORS_KP \
    -dname "CN=BorsTerminal Android Release, OU=mobile, O=BorsTerminal, C=IR"
  unset BORS_SP BORS_KP
  printf '%s\n' "KEY_ALIAS=$alias" > "$META"
  printf '%s\n' "CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$META"
  # رمز فقط درِ فایلِ ۰۷۰۰ِ محلی می‌ماند تا «publish-secrets» و «restore» بتوانند
  # secretها را بسازند؛ بی‌این، گم‌کردنِ رمز = گم‌کردنِ کلید.
  printf '%s' "$sp" > "$KS_PASS_FILE"
  unset sp kp alias
  chmod 600 "$KS" "$META" "$KS_PASS_FILE"
  printf '\nOK: کلید ساخته شد درِ %s\n' "$KS" >&2
  printf 'اقدامِ بعدی: backup --to <مسیرِ بیرونِ این ماشین>، و سپس verify-backup.\n' >&2
  cmd_fingerprint
}

cmd_fingerprint() {
  need keytool
  require_local_key
  local alias
  alias="$(meta_get KEY_ALIAS)"; alias="${alias:-$ALIAS_DEFAULT}"
  printf 'cert SHA-256 fingerprint (همین را با APK_CERT_SHA256 درِ رانِ CI مقایسه کنید):\n' >&2
  keytool -list -keystore "$KS" -alias "$alias" -storepass:file "$KS_PASS_FILE" -v 2>/dev/null \
    | sed -n 's/^[[:space:]]*Signature algorithmName:[[:space:]]*//p; s/^[[:space:]]*SHA256:[[:space:]]*//p'
  keytool -list -keystore "$KS" -alias "$alias" -storepass:file "$KS_PASS_FILE" -v 2>/dev/null \
    | grep -E 'SHA256:|Valid from:' || true
}

cmd_backup() {
  require_local_key
  [ -n "${TO:-}" ] || die "backup --to <پوشه>"
  need sha256sum
  mkdir -p "$TO"
  local stamp bundle
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  bundle="$TO/bors-android-release-$stamp"
  mkdir -p "$bundle"
  cp "$KS" "$bundle/"
  [ -f "$META" ] && cp "$META" "$bundle/"
  cp "$KS_PASS_FILE" "$bundle/.storepass"
  chmod 600 "$bundle" "$bundle"/* "$bundle"/.storepass 2>/dev/null || true
  ( cd "$bundle" && sha256sum bors-android-release.jks > SHA256SUMS )
  printf 'OK: بستهٔ پشتیبان: %s\n' "$bundle" >&2
  printf 'برگشتِ همین بسته را با verify-backup --from همان مسیر بسنجید.\n' >&2
}

cmd_verify_backup() {
  need keytool; need sha256sum
  [ -n "${FROM:-}" ] || die "verify-backup --from <بسته>"
  [ -f "$FROM/bors-android-release.jks" ] || die "درِ $FROM کلیدی نیست"
  ( cd "$FROM" && sha256sum -c SHA256SUMS ) || die "SHA256ِ بسته نمی‌خواند"
  local sp="" alias
  [ -f "$FROM/.storepass" ] && sp="$(cat "$FROM/.storepass")"
  alias="$( [ -f "$FROM/meta.env" ] && sed -n 's/^KEY_ALIAS=//p' "$FROM/meta.env" | head -1 || echo "$ALIAS_DEFAULT" )"
  if [ -n "$sp" ]; then
    printf '%s' "$sp" > "$FROM/.tmp.pass"
    keytool -list -keystore "$FROM/bors-android-release.jks" -alias "$alias" -storepass:file "$FROM/.tmp.pass" >/dev/null
    rm -f "$FROM/.tmp.pass"
  else
    BORS_ASK=1 keytool -list -keystore "$FROM/bors-android-release.jks" -alias "$alias" >/dev/null
  fi
  printf 'OK: پشتیبان بازنشانی‌شدنی است (کلیدِ alias=%s ازِ همان بسته باز شد).\n' "$alias" >&2
}

cmd_restore() {
  need keytool
  [ -n "${FROM:-}" ] || die "restore --from <بسته>"
  [ -f "$FROM/bors-android-release.jks" ] || die "درِ $FROM کلیدی نیست"
  [ -e "$KS" ] && die "کلیدِ محلی از قبل هست ($KS) — بازنویسی نمی‌کنیم. اگر گم شده، مسیرِ تازه بدهید."
  mkdir -p "$KEY_DIR"
  cp "$FROM/bors-android-release.jks" "$KS"
  [ -f "$FROM/meta.env" ] && cp "$FROM/meta.env" "$META" || printf '%s\n' "KEY_ALIAS=$ALIAS_DEFAULT" > "$META"
  [ -f "$FROM/.storepass" ] && cp "$FROM/.storepass" "$KS_PASS_FILE" || die "رمزِ keystore درِ بسته نیست؛ آن را دستی درِ $KS_PASS_FILE بگذارید"
  chmod 600 "$KEY_DIR" "$KS" "$META" "$KS_PASS_FILE"
  printf 'OK: کلید بازگردانده شد به %s\n' "$KS" >&2
  cmd_fingerprint
}

cmd_publish_secrets() {
  need gh; need base64
  require_local_key
  [ -f "$KS_PASS_FILE" ] || die "رمزِ محلی درِ $KS_PASS_FILE نیست (پس ازِ restore هم لازم است)"
  local sp alias kp
  sp="$(cat "$KS_PASS_FILE")"
  alias="$(meta_get KEY_ALIAS)"; alias="${alias:-$ALIAS_DEFAULT}"
  printf 'رمزِ کلیدِ خصوصی (Enter = همان رمزِ keystore): ' >&2
  read -r -s kp; printf '\n' >&2
  kp="${kp:-$sp}"

  # ۱) keystore، base64 — ازِ stdin، نه argv
  base64 -w0 "$KS" | gh secret set ANDROID_RELEASE_KEYSTORE_B64 --repo "$REPO"

  # ۲) props سه‌سطری، دقیقاً همان قالبی که workflow prepend کردنِ storeFile را انتظار دارد
  local tmp
  tmp="$(mktemp)"
  umask 077
  { printf 'storePassword=%s\nkeyAlias=%s\nkeyPassword=%s\n' "$sp" "$alias" "$kp"; } > "$tmp"
  gh secret set ANDROID_RELEASE_KEYSTORE_PROPS --repo "$REPO" < "$tmp"
  rm -f "$tmp"
  unset sp kp tmp

  printf 'OK: دو secret درِ %s نشست. مقدارِ هیچ‌کدام چاپ نشد.\n' "$REPO" >&2
  printf 'تأییدِ نام‌ها (بدونِ مقدار): gh secret list --repo %s\n' "$REPO" >&2
  printf 'دروازۀ انتشار به کلیدِ عمومیِ manifest هم نیاز دارد: gh variable set MOBILE_MANIFEST_PUBKEY --repo %s --body "<متنِ public key ازِ ~/.bors_mobile_keys>"\n' "$REPO" >&2
}

main() {
  local cmd="${1:-help}"; shift || true
  TO=""; FROM=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --to) TO="${2:-}"; shift 2 ;;
      --from) FROM="${2:-}"; shift 2 ;;
      *) die "گزينۀ ناشناخته: $1" ;;
    esac
  done
  case "$cmd" in
    keygen) cmd_keygen ;;
    fingerprint) cmd_fingerprint ;;
    backup) cmd_backup ;;
    verify-backup) cmd_verify_backup ;;
    restore) cmd_restore ;;
    publish-secrets) cmd_publish_secrets ;;
    *) sed -n '2,26p' "$0" ;;
  esac
}
main "$@"
