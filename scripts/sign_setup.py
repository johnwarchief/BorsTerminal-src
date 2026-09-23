#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/sign_setup.py — امضای minisignِ نصاب برای آپدیت‌رِ tauri.

استفاده:  python scripts/sign_setup.py <path/to/Setup.exe>

اول مسیرِ رسمی (``tauri signer sign``) امتحان می‌شود، ولی signer گاهی روی
stdin می‌خوابد؛ به همین دلیل timeout سختِ ۱۲۰ ثانیه داریم و در صورتِ ناکامی به
minisign خالصِ پایتون (Ed25519 روی blake2b-512 — همان فرمتی که tauri می‌خواند)
برمی‌گردیم. این دقیقاً مسیرِ اثبات‌شدهٔ v1.0.6/v1.0.8 است (آنجا با نامِ
_pysign_v108.py در ریشهٔ workspace اجرا می‌شد؛ حالا بخشی از ریپو است).

خروجی: ``<Setup.exe>.sig`` در کنارِ نصاب + کدِ خروجِ ۰ اگر و فقط اگر امضا
مقابلِ ``.tauri/updater.key.pub`` تأیید شود.
"""
import base64
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)   # برای import bors_minisign — همان وریفایرِ اپ
KEY = os.path.join(ROOT, ".tauri", "updater.key")
PUB = os.path.join(ROOT, ".tauri", "updater.key.pub")
TAURI = os.path.join(ROOT, "frontend", "node_modules", ".bin", "tauri.cmd")
TAURI_TIMEOUT = 120


def log(msg):
    print(msg, flush=True)


def blake2b_file(path):
    h = hashlib.blake2b(digest_size=64)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.digest()


def _first_sig_line(armored):
    for ln in armored.splitlines():
        s = ln.strip()
        if s and not s.startswith("untrusted"):
            return s
    return None


def load_armored(path):
    raw = open(path).read().strip()
    armored = base64.b64decode(raw).decode("utf-8", "replace")
    lines = armored.splitlines()
    comment = lines[0] if lines else ""
    line = _first_sig_line(armored)
    return comment, (base64.b64decode(line) if line else b"")


def parse_secret(bin_):
    """Unencrypted minisign secret key: Ed(2)+keyid(8)+pub(32)+sec(32)+chk(32)."""
    if len(bin_) != 106:
        return None, "len=%d (expected 106 unencrypted)" % len(bin_)
    if bin_[:2] != b"Ed":
        return None, "alg=%r" % bin_[:2]
    calc = hashlib.blake2b(bin_[:74], digest_size=64).digest()
    if calc != bin_[74:106]:
        return None, "checksum mismatch -> key is PASSWORD-ENCRYPTED"
    return {"keyid": bin_[2:10], "pub": bin_[10:42], "sec": bin_[42:74]}, "ok"


def parse_public(bin_):
    if len(bin_) != 42:
        return None, "len=%d (expected 42)" % len(bin_)
    return {"alg": bin_[:2], "keyid": bin_[2:10], "pub": bin_[10:42]}, "ok"


def verify(pubinfo, blob, setup):
    # تأیید با همان وریفایرِ خالص‌پایتونی که اپِ فریزشده اجرا می‌کند
    # (bors_minisign)، نه با cryptography. «VERIFY: PASS» باید یعنی *کاربر*
    # این امضا را می‌پذیرد — نه اینکه مفسرِ بیلد شانسی پکیج را دارد؛ این
    # بررسی در .venvِ بدونِ cryptography هم باید کار کند.
    import bors_minisign
    if blob[:2] not in (b"Ed", b"ED"):
        raise ValueError("sig alg=%r" % blob[:2])
    if blob[2:10] != pubinfo["keyid"]:
        raise ValueError("keyid mismatch sig=%s pub=%s" % (blob[2:10].hex(), pubinfo["keyid"].hex()))
    if not bors_minisign._ed25519_verify(pubinfo["pub"], blake2b_file(setup), blob[10:74]):
        raise ValueError("ed25519 verify failed (bad signature or tampered file)")


def sign_python(sec, keyid, setup, sig):
    """Fallback signing without the tauri CLI.

    در minisign دو اَلف هست: ED یعنی امضا روی blake2b-512 و Ed یعنی روی
    خامِ فایل. این تابع دیژست می‌سازد پس ED می‌نویسد؛ با «Ed» دروغین،
    bors_minisign مسیرِ raw را می‌رفت و آپدیت رد می‌شد.
    """
    blob = b"ED" + keyid + _ed25519_sign(sec, blake2b_file(setup))
    with open(sig, "wb") as f:
        f.write(b"untrusted comment: tauri signature\n")
        f.write(base64.b64encode(blob))
        f.write(b"\n")
    return blob


def _ed25519_sign(sec, msg):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(sec).sign(msg)


def try_tauri(setup, sig):
    if not os.path.exists(TAURI):
        log("--- tauri CLI not found (%s) -> python fallback ---" % TAURI)
        return False
    env = dict(os.environ)
    env["TAURI_SIGNING_PRIVATE_KEY_PASSWORD"] = ""
    log("--- tauri signer sign (timeout=%ds) ---" % TAURI_TIMEOUT)
    try:
        r = subprocess.run(
            ["cmd.exe", "/c", TAURI, "signer", "sign", "-f", KEY, setup],
            stdin=subprocess.DEVNULL, capture_output=True,
            timeout=TAURI_TIMEOUT, env=env, cwd=ROOT,
        )
        log("  exit=%d" % r.returncode)
        for tag, data in (("stdout", r.stdout), ("stderr", r.stderr)):
            for ln in data.decode("utf-8", "replace").strip().splitlines():
                log("    %s: %s" % (tag, ln))
    except subprocess.TimeoutExpired:
        log("  TIMEOUT (tauri signer hangs on stdin; falling back to python)")
    return os.path.exists(sig)


def main():
    if len(sys.argv) < 2:
        log("usage: sign_setup.py <Setup.exe>")
        return 2
    setup = os.path.abspath(sys.argv[1])
    sig = setup + ".sig"
    if not os.path.exists(setup):
        log("[!] setup not found: %s" % setup)
        return 2
    log("  setup: %s (%d bytes)" % (setup, os.path.getsize(setup)))

    # نصابِ جدید ساخته شده؛ هر .sigیِ قدیمی به باینریِ قبلی اشاره می‌کند و
    # آپدیتِر آن را FAIL می‌زند — باید حتماً دوباره امضا کنیم.
    if os.path.exists(sig):
        log("  deleting stale .sig (%d bytes)" % os.path.getsize(sig))
        os.remove(sig)

    _, pbin = load_armored(PUB)
    pubinfo, pmsg = parse_public(pbin)
    if not pubinfo:
        log("[!] pub parse failed: %s" % pmsg)
        return 1
    log("  pub keyid=%s" % pubinfo["keyid"].hex())

    _, kbin = load_armored(KEY)
    sec, smsg = parse_secret(kbin)
    log("  secret: %s" % smsg)

    if not try_tauri(setup, sig) and sec:
        log("--- python minisign fallback ---")
        blob = sign_python(sec["sec"], sec["keyid"], setup, sig)
        log("  wrote %s (%d bytes)" % (sig, len(blob)))

    if not os.path.exists(sig):
        log("[!] NO SIG PRODUCED")
        return 1

    try:
        _, blob = load_armored(sig)
        verify(pubinfo, blob, setup)
        log("  VERIFY: PASS (valid minisign sig for updater.key.pub) size=%d" % os.path.getsize(sig))
        return 0
    except Exception as e:
        log("  VERIFY: FAIL %r" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
