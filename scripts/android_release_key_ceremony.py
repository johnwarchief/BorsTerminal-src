#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/android_release_key_ceremony.py — مراسمِ کلیدِ انتشار، بی‌Java.

چرا این فایل هست: `android_release_key_ceremony.sh` به `keytool` (JDK) و به
ترمینالِ تعاملی نیاز دارد. رویِ ماشینِ این پروژه هیچ Java ای نصب نیست (سنجیده
شد: `which keytool java` → خالی)، پس مراسمِ کلیدِ *انتشار* — که تنها راهِ یک
گواهیِ پایدار و ارتقایِ درجاست — با همان اسکریپت اجراشدنی نبود. این همدوشِ
همان قرارداد است، نه دورزدنِ آن:

  - کلیدِ RSA-2048 + گواهیِ خودامضا با اعتبارِ ۲۵ سال (Android: RSA ≥ 2048 و
    validity تا پسِ 2033).
  - ظرف: **PKCS12** (`bors-android-release.p12`) — چون JKS نوشتن بی‌Java ممکن
    نیست. build.gradle نوع را ازِ `storeType` درِ props می‌خواند، پس هر دو نوع
    keystore (JKSِ keytool و PKCS12ِ این اسکریپت) با یک workflow کار می‌کنند.
  - رمز: تصادفیِ ۳۲ بایت، **هرگز چاپ نمی‌شود**، به argv هیچ فرمانی نمی‌رود، و
    فقط درِ فایلِ ۰۶۰۰ِ `~/.bors_android_keys/.storepass` می‌ماند. بی‌رمزِ تایپیِ
    انسان، گم‌شدنِ رمز = گم‌شدنِ کلید نیست؛ همان رمزِ تصادفی درِ پشتیبان هست.
  - `keygen` رویِ کلیدِ موجود بازنویسی نمی‌کند. `restore` هم همین‌طور — و اگر
    `--into` بدهید، آزمونِ بازیابی درِ پوشۀ *جدا* انجام می‌شود و کلیدِ فعالِ
    شما لمس نمی‌شود (این همان چیزی است که مأموریت خواسته: restore باید drill باشد).
  - `fingerprint` = SHA-256 ازِ DERِ خودِ گواهی؛ دقیقاً همان عددی که
    `apksigner verify --print-certs` چاپ می‌کند و همان چیزی که درِ
    vars.ANDROID_RELEASE_CERT_SHA256 می‌نشیند.
  - `publish-secrets` هر دو secret را ازِ stdin می‌فرستد (`gh secret set …
    --body "-"`) و فقط نام‌ها را چاپ می‌کند.

استفاده (همان ترتیبِ سندِ مراسم):
  python scripts/android_release_key_ceremony.py keygen
  python scripts/android_release_key_ceremony.py backup --to /media/usb/bors-keys
  python scripts/android_release_key_ceremony.py verify-backup --from <بسته>
  python scripts/android_release_key_ceremony.py restore --from <بسته> --into /tmp/drill
  python scripts/android_release_key_ceremony.py fingerprint
  python scripts/android_release_key_ceremony.py publish-secrets
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ALIAS_DEFAULT = "bors"
SUBJECT_CN = "BorsTerminal Android Release"
VALIDITY_DAYS = 9125          # ۲۵ سال
REPO_DEFAULT = "johnwarchief/BorsTerminal-src"
KS_NAME = "bors-android-release.p12"
PASS_NAME = ".storepass"
META_NAME = "meta.env"

KEY_DIR = os.environ.get("BORS_ANDROID_KEY_DIR") or os.path.expanduser("~/.bors_android_keys")


def die(msg: str) -> None:
    print("ERR: " + msg, file=sys.stderr)
    raise SystemExit(1)


def paths(root: str) -> dict:
    return {"dir": root, "ks": os.path.join(root, KS_NAME),
            "pass": os.path.join(root, PASS_NAME), "meta": os.path.join(root, META_NAME)}


def _hard_mode(path: str) -> None:
    if sys.platform == "win32":
        return
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _load(p12_path: str, password: bytes):
    from cryptography.hazmat.primitives.serialization import pkcs12
    with open(p12_path, "rb") as f:
        return pkcs12.load_key_and_certificates(f.read(), password)


def _fingerprint_of(p12_path: str, password: bytes) -> str:
    _key, cert, _cas = _load(p12_path, password)
    if cert is None:
        die("درِ keystore گواهی نیست")
    return cert.fingerprint(__import__("cryptography.hazmat.primitives.hashes",
                                        fromlist=["SHA256"]).SHA256()).hex()


def _read_meta(meta_path: str) -> dict:
    out = {}
    if os.path.exists(meta_path):
        for line in open(meta_path, encoding="utf-8").read().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
    return out


def cmd_keygen(a) -> int:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    p = paths(a.key_dir)
    if os.path.exists(p["ks"]):
        die("کلید از قبل هست: %s — به‌جایِ کلیدِ انتشارِ قبلی کلیدِ تازه نسازید. "
            "برایِ انتشارهایِ بعدی همان کلید ثابت می‌ماند." % p["ks"])
    os.makedirs(p["dir"], mode=0o700, exist_ok=True)
    password = _gen_password()
    key = rsa.generate_private_key(public_exponent=65537, key_size=a.bits)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IR"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BorsTerminal"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "mobile"),
        x509.NameAttribute(NameOID.COMMON_NAME, SUBJECT_CN),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + dt.timedelta(days=VALIDITY_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    blob = serialization.pkcs12.serialize_key_and_certificates(
        ALIAS_DEFAULT.encode(), key, cert, None,
        serialization.BestAvailableEncryption(password))
    with open(p["ks"], "wb") as f:
        f.write(blob)
    _hard_mode(p["ks"])
    with open(p["pass"], "wb") as f:
        f.write(password)
    _hard_mode(p["pass"])
    with open(p["meta"], "w", encoding="utf-8", newline="\n") as f:
        f.write("KEY_ALIAS=%s\nSTORE_TYPE=PKCS12\nCREATED_AT=%s\n"
                % (ALIAS_DEFAULT, now.strftime("%Y-%m-%dT%H:%M:%SZ")))
    _hard_mode(p["meta"])
    del password
    print("OK: کلیدِ انتشار ساخته شد درِ %s (ظرفِ PKCS12، %d بایت)"
          % (p["ks"], len(blob)), file=sys.stderr)
    print("رمز درِ %s (۰۶۰۰) است و هیچ‌جا چاپ نشده." % p["pass"], file=sys.stderr)
    print("اقدامِ بعدی: backup --to <مسیرِ بیرونِ این ماشین>، سپس verify-backup.",
          file=sys.stderr)
    return cmd_fingerprint(a)


def _gen_password() -> bytes:
    import secrets
    return secrets.token_urlsafe(32).encode()


def cmd_fingerprint(a) -> int:
    p = paths(a.key_dir)
    if not os.path.exists(p["ks"]):
        die("کلید درِ %s نیست. اول: keygen" % p["ks"])
    password = open(p["pass"], "rb").read()
    fp = _fingerprint_of(p["ks"], password)
    meta = _read_meta(p["meta"])
    print("cert SHA-256 (همین = vars.ANDROID_RELEASE_CERT_SHA256):")
    print(":".join(fp[i:i + 2].upper() for i in range(0, 64, 2)))
    print("alias=%s · storeType=%s · created=%s"
          % (meta.get("KEY_ALIAS", ALIAS_DEFAULT), meta.get("STORE_TYPE", "PKCS12"),
             meta.get("CREATED_AT", "?")))
    del password
    return 0


def cmd_backup(a) -> int:
    if not a.to:
        die("backup --to <پوشه>")
    p = paths(a.key_dir)
    for f in (p["ks"], p["pass"], p["meta"]):
        if not os.path.exists(f):
            die("پیش‌نیازِ پشتیبان نیست: %s" % f)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = os.path.join(a.to, "bors-android-release-" + stamp)
    os.makedirs(bundle, mode=0o700, exist_ok=True)
    for f in (p["ks"], p["pass"], p["meta"]):
        shutil.copy2(f, bundle)
        _hard_mode(os.path.join(bundle, os.path.basename(f)))
    with open(os.path.join(bundle, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%s  %s\n" % (_sha256_file(os.path.join(bundle, KS_NAME)), KS_NAME))
    print("OK: بستهٔ پشتیبان: %s" % bundle, file=sys.stderr)
    print("شما باید برگشتِ همین بسته را با verify-backup بسنجید، نه اینکه فقط "
          "فایل کپی شده باشد.", file=sys.stderr)
    return 0


def cmd_verify_backup(a) -> int:
    if not a.from_:
        die("verify-backup --from <بسته>")
    ks = os.path.join(a.from_, KS_NAME)
    if not os.path.exists(ks):
        die("درِ %s کلیدی نیست" % a.from_)
    sums_path = os.path.join(a.from_, "SHA256SUMS")
    want = ""
    if os.path.exists(sums_path):
        for line in open(sums_path, encoding="utf-8").read().splitlines():
            if KS_NAME in line:
                want = line.split()[0]
    got = _sha256_file(ks)
    if want and want != got:
        die("SHA256ِ بسته نمی‌خواند (منتظره %s…, دیدم %s…)" % (want[:12], got[:12]))
    pw_path = os.path.join(a.from_, PASS_NAME)
    if not os.path.exists(pw_path):
        die("رمز درِ بسته نیست؛ بدونِ رمز، «پشتیبان» فقط یکِ فایلِ بی‌استفاده است")
    fp_backup = _fingerprint_of(ks, open(pw_path, "rb").read())
    p = paths(a.key_dir)
    line = "OK: پشتیبان بازنشانی‌شدنی است (کلیدِ alias=%s باز شد، fingerprint %s…)" % (
        ALIAS_DEFAULT, fp_backup[:16])
    if os.path.exists(p["ks"]) and os.path.exists(p["pass"]):
        live = _fingerprint_of(p["ks"], open(p["pass"], "rb").read())
        same = "یکی" if live == fp_backup else "نه — این پشتیبان کلیدِ دیگری است!"
        line += " · با کلیدِ فعال: %s" % same
    print(line, file=sys.stderr)
    return 0


def cmd_restore(a) -> int:
    """آزمونِ بازیابی. بی --into رویِ کلیدِ فعال می‌نشیند و اگر ازِ پیش چیزی باشد
    **رد** می‌شود؛ با --into درِ پوشۀ جدا باز می‌شود و کلیدِ فعال لمس نمی‌شود."""
    if not a.from_:
        die("restore --from <بسته>")
    src_ks = os.path.join(a.from_, KS_NAME)
    if not os.path.exists(src_ks):
        die("درِ %s کلیدی نیست" % a.from_)
    dest = paths(a.into or a.key_dir)
    if os.path.exists(dest["ks"]) and not a.into:
        die("کلیدِ محلی از قبل هست (%s) — بازنویسی نمی‌کنیم. برایِ آزمونِ بازیابی "
            "مسیرِ جدا بدهید: restore --from <بسته> --into /tmp/drill" % dest["ks"])
    os.makedirs(dest["dir"], mode=0o700, exist_ok=True)
    shutil.copy2(src_ks, dest["ks"])
    for nm in (PASS_NAME, META_NAME):
        s = os.path.join(a.from_, nm)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(dest["dir"], nm))
            _hard_mode(os.path.join(dest["dir"], nm))
    _hard_mode(dest["ks"])
    if not os.path.exists(dest["pass"]):
        die("رمز درِ بسته نبود؛ بدونِ آن کلیدِ بازگردانده‌شده به‌درد نمی‌خورد")
    fp = _fingerprint_of(dest["ks"], open(dest["pass"], "rb").read())
    src_fp = fp
    if os.path.exists(paths(a.key_dir)["ks"]) and os.path.exists(paths(a.key_dir)["pass"]):
        src_fp = _fingerprint_of(paths(a.key_dir)["ks"], open(paths(a.key_dir)["pass"], "rb").read())
    print("OK: بازیابی درِ %s — fingerprint %s… | کلیدِ فعال %s"
          % (dest["dir"], fp[:16], "همان" if fp == src_fp else "دگر"), file=sys.stderr)
    return 0


def cmd_publish_secrets(a) -> int:
    if shutil.which("gh") is None:
        die("«gh» نیست؛ بدونِ GitHub CLI نمی‌توان secret گذاشت")
    p = paths(a.key_dir)
    for f in (p["ks"], p["pass"]):
        if not os.path.exists(f):
            die("پیش‌نیاز نیست: %s" % f)
    meta = _read_meta(p["meta"])
    alias = meta.get("KEY_ALIAS", ALIAS_DEFAULT)
    stype = meta.get("STORE_TYPE", "PKCS12")
    sp = open(p["pass"], "rb").read()
    repo = a.repo or REPO_DEFAULT
    import base64
    b64 = base64.b64encode(open(p["ks"], "rb").read()).decode()
    _gh_secret("ANDROID_RELEASE_KEYSTORE_B64", b64, repo)
    props = ("storePassword=%s\nkeyAlias=%s\nkeyPassword=%s\nstoreType=%s\n"
             % (sp.decode(), alias, sp.decode(), stype))
    _gh_secret("ANDROID_RELEASE_KEYSTORE_PROPS", props, repo)
    print("OK: دو secret درِ %s نشست؛ مقدارِ هیچ‌کدام چاپ نشد." % repo, file=sys.stderr)
    print("نام‌ها را این‌طور تأیید کنید (بدونِ مقدار): gh secret list --repo %s" % repo,
          file=sys.stderr)
    return 0


def _gh_secret(name: str, body: str, repo: str) -> None:
    # مقدار فقط ازِ stdin می‌رود؛ هرگز درِ argv (فهرستِ پروسه‌ها آن را نشان می‌دهد)
    # `--body "-"` مقدارِ «-» را ذخیره می‌کرد (gh فقط بی‌--body ازِ stdin می‌خواند)؛
    # شاهدش: درِ CI `base64: invalid input` رویِ همان secret. رمز هرگز به argv
    # نمی‌رود: بدنه ازِ لوله (pipe) است.
    r = subprocess.run(["gh", "secret", "set", name, "--repo", repo],
                       input=body.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        #stderrِ gh را چاپ نمی‌کنیم: ممکن است بازتابِ ورودی باشد
        die("«gh secret set %s» رد شد (exit %d)" % (name, r.returncode))


def main() -> int:
    ap = argparse.ArgumentParser(description="مراسمِ کلیدِ انتشارِ اندروید، بی‌Java")
    ap.add_argument("cmd", choices=["keygen", "fingerprint", "backup", "verify-backup",
                                   "restore", "publish-secrets"])
    ap.add_argument("--to", default="", help="مقصدِ backup")
    ap.add_argument("--from", dest="from_", default="", help="بستهٔ پشتیبان")
    ap.add_argument("--into", default="", help="مقصدِ آزمونِ بازیابی (کلیدِ فعال را دست نمی‌زند)")
    ap.add_argument("--key-dir", default=KEY_DIR)
    ap.add_argument("--bits", type=int, default=2048)
    ap.add_argument("--repo", default="")
    a = ap.parse_args()
    if a.bits < 2048:
        die("RSA %d برایِ امضایِ Android کم است (۲۰۴۸ لازم است)" % a.bits)
    if a.cmd == "keygen":
        return cmd_keygen(a)
    if a.cmd == "fingerprint":
        return cmd_fingerprint(a)
    if a.cmd == "backup":
        return cmd_backup(a)
    if a.cmd == "verify-backup":
        return cmd_verify_backup(a)
    if a.cmd == "restore":
        return cmd_restore(a)
    return cmd_publish_secrets(a)


if __name__ == "__main__":
    sys.exit(main())
