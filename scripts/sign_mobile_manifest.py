#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sign_mobile_manifest.py — امضایِ detached رویِ بایت‌هایِ دقیقِ manifest موبایل.

قرارداد (مرحلۀ ۲ دور ۴ Android):
  • بستهٔ آفلاین دو فایل است: `mobile_snapshot.db.meta.json` (manifest) و
    `mobile_snapshot.db.meta.json.sig` (امضا، **خارج** از manifest). امضا روی
    بایت‌هایِ همان manifest گرفته می‌شود، پس هیچ دورِ باطلی نیست و کلاینت می‌تواند
    **پیش ازِ اعتماد به هیچ فیلدی** اصالت را بسنجد.
  • فرمت: بلوکِ clear-signatureِ سازگارِ minisign (چهار خط) با الگوریتم `Ed`
    = Ed25519 رویِ پیامِ خام — همان چیزی که `bors_minisign.verify_minisign`
    می‌شناسد و همان چیزی که WebCrypto درِ WebView بومی بررسی می‌کند
    (سنجشِ واقعی: `_audit/tmp/stage4/crypto_probe.mts` رویِ Chromium 151 —
    `ed25519.importRaw+verify: OK · verify=true tamperedVerify=false`).
    الگوریتم `ED` (blake2b-512 پیش‌هش) که `tauri signer` می‌دهد اینجا **نمی‌شود**،
    چون WebCrypto blake2b ندارد؛ برایِ همین فرمت صریحاً `Ed` است.
  • key_id: هشت بایتِ اولِ SHA-256 از DERِ کلید عمومی. این خودِ minisign نیست
    (minisign آن را از seed می‌سازد) — سازنده و مصرف‌کنندۀ همین قرارداد یکی‌اند و
    جایِ آن درِ مستند این فایل است؛ وانمودِ بهِ canonical بودن نمی‌کنیم.

کلید:
  • کلید خصوصی **هرگز** درِ مخزن نیست. دو منبع مجاز: مسیرِ فایل (پیش‌فرض
    `--key`) یا متغیرِ محیطی `BORS_MOBILE_MANIFEST_KEY_PEM` (متنِ PEM) که CI آن را
    از secret می‌گذارد.
  • برایِ انتشارِ ویندوز از کلیدِ updater (`830BF752EF10076`) استفاده **نمی‌شود**؛
    همین‌جا کلیدِ مستقلِ «دادهٔ موبایل» است — دو ریشۀِ اعتماد، دو دامنه.

اجرا:
    python scripts/sign_mobile_manifest.py --keygen --out-dir ~/.bors_mobile_keys   # یک‌بار
    python scripts/sign_mobile_manifest.py --key <priv.pem> --in <meta.json>
    python scripts/sign_mobile_manifest.py --verify --key-pub <pub.pem> \\
        --in <meta.json> --sig <meta.json.sig>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time

ALG = b"Ed"                      # Ed25519 رویِ پیامِ خام (WebCrypto-پذیر)
SIG_FILE_SUFFIX = ".sig"
ED25519_SPKI_PREFIX_LEN = 12     # 302a300506032b6570032100 → 12 بایتِ اول، 32 بایتِ بعدی کلید خام


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def _backend():
    """`cryptography` اگر باشد، وگرنه `openssl` — بی‌ساختنِ ادعایِ بی‌ابزار."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa
        return "cryptography"
    except Exception:
        pass
    try:
        v = subprocess.run(["openssl", "version"], capture_output=True, timeout=10)
        if v.returncode == 0:
            return "openssl"
    except Exception:
        pass
    return None


# ── کلید ────────────────────────────────────────────────────────────────────
def keygen(out_dir: str) -> dict:
    """جفت‌کلیدِ Ed25519. اگر out_dir داخلِ مخزن باشد، رد می‌شود (کلید درِ گیت نیست)."""
    out_abs = os.path.abspath(out_dir)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if out_abs.startswith(repo + os.sep) or out_abs == repo:
        raise SystemExit("کلید خصوصی نباید داخلِ مخزن ساخته شود: %s" % out_abs)
    os.makedirs(out_abs, exist_ok=True)
    priv = os.path.join(out_abs, "mobile_manifest.key")
    pub = os.path.join(out_abs, "mobile_manifest.key.pub")
    be = _backend()
    if be == "cryptography":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
        k = ed25519.Ed25519PrivateKey.generate()
        with open(priv, "wb") as f:
            f.write(k.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()))
        with open(pub, "wb") as f:
            f.write(k.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo))
    elif be == "openssl":
        _run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv])
        _run(["openssl", "pkey", "-pubout", "-in", priv, "-out", pub])
    else:
        raise SystemExit("BLOCKED: نه cryptography و نه openssl در دسترس نیست — "
                         "کلیدِ امضایِ manifest ساخته نمی‌شود (کلید آزمایشیِ ساختگی نه)")
    return {"backend": be, "private": priv, "public": pub,
            "public_key_id": key_id_from_pem(pub)}


def _pub_der(pem_path: str) -> bytes:
    """DERِ SubjectPublicKeyInfo — از فایلِ کلید عمومی **یا** خصوصی (هر دو مجاز)."""
    be = _backend()
    if be == "cryptography":
        from cryptography.hazmat.primitives import serialization
        blob = open(pem_path, "rb").read()
        try:
            key = serialization.load_pem_private_key(blob, password=None)
            pub = key.public_key()
        except ValueError:
            pub = serialization.load_pem_public_key(blob)
        return pub.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    # openssl: `pkey -in` هم private و هم public PEM را می‌خواند و عمومی می‌دهد
    r = _run(["openssl", "pkey", "-in", pem_path, "-pubout", "-outform", "DER"])
    return r.stdout


def key_id_from_pem(pem_path: str) -> str:
    """هشت بایتِ اولِ SHA-256(DERِ public) → hex 16 رقمی (همان چیزی که درِ بلوک می‌آید)."""
    return hashlib.sha256(_pub_der(pem_path)).hexdigest()[:16]


def raw_public32(pem_path: str) -> bytes:
    der = _pub_der(pem_path)
    if der[:ED25519_SPKI_PREFIX_LEN] != bytes.fromhex("302a300506032b6570032100"):
        raise SystemExit("این کلید عمومی Ed25519 نیست (SPKI prefix نخورد)")
    return der[ED25519_SPKI_PREFIX_LEN:]


def pubinfo(pem_path: str) -> dict:
    r32 = raw_public32(pem_path)
    return {"key_id": hashlib.sha256(_pub_der(pem_path)).hexdigest()[:16],
            "raw_public_b64": base64.b64encode(r32).decode(),
            "minisign_pubkey_text": "untrusted comment: minisign public key: %s\n%s" % (
                hashlib.sha256(_pub_der(pem_path)).hexdigest()[:16],
                base64.b64encode(b"Ed" + bytes.fromhex(
                    hashlib.sha256(_pub_der(pem_path)).hexdigest()[:16]) + r32).decode())}


# ── امضا / بررسی ────────────────────────────────────────────────────────────
def _sign_bytes(data: bytes, priv_path: str) -> bytes:
    be = _backend()
    if be == "cryptography":
        from cryptography.hazmat.primitives import serialization
        k = serialization.load_pem_private_key(open(priv_path, "rb").read(), password=None)
        return k.sign(data)
    tmp = _tmpfile(data)
    try:
        r = _run(["openssl", "pkeyutl", "-sign", "-inkey", priv_path, "-rawin", "-in", tmp])
        return r.stdout
    finally:
        os.unlink(tmp)


def _tmpfile(data: bytes) -> str:
    import tempfile
    fd, p = tempfile.mkstemp(prefix="borsmsign-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return p


def sign(manifest_path: str, priv_path: str, out_sig_path: str | None = None,
         comment_extra: str = "") -> dict:
    """بلوکِ clear-signature رویِ بایت‌هایِ manifest + خودسنجیِ مستقلِ خروجی.

    خودسنجی با `bors_minisign.verify_minisign` انجام می‌شود، نه با `cryptography` —
    یعنی «PASS» یعنی همان چیزی که کلاینت/خوانندۀ پایتونیِ موجودِ مخزن می‌پذیرد.
    """
    if not os.path.exists(priv_path):
        raise SystemExit("BLOCKED: کلید خصوصی نیست: %s" % priv_path)
    data = open(manifest_path, "rb").read()
    key_id_hex = key_id_from_pem(priv_path)      # از خودِ کلیدِ خصوصی هم عمومی درمی‌آید
    kid = bytes.fromhex(key_id_hex)
    sig64 = _sign_bytes(data, priv_path)
    if len(sig64) != 64:
        raise SystemExit("امضای ۶۴ بایتی ساخته نشد (طول=%d)" % len(sig64))
    ts = int(time.time())
    comment = "timestamp=%d file=%s%s" % (ts, os.path.basename(manifest_path),
                                          (" " + comment_extra if comment_extra else ""))
    global64 = _sign_bytes(sig64 + comment.encode("utf-8"), priv_path)
    block = ("untrusted comment: signature from bors mobile-manifest signing key\n%s\n"
             "trusted comment: %s\n%s\n"
             % (base64.b64encode(ALG + kid + sig64).decode(),
                comment, base64.b64encode(global64).decode()))
    out = out_sig_path or (manifest_path + SIG_FILE_SUFFIX)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(block)
    return {"sig_path": out, "key_id": key_id_hex, "algorithm": "Ed25519/raw (minisign 'Ed')",
            "manifest_bytes": len(data), "manifest_sha256": hashlib.sha256(data).hexdigest(),
            "timestamp": ts, "trusted_comment": comment}


def verify(manifest_path: str, sig_path: str, pub_pem_path: str) -> bool:
    """بررسی با همان ماژولِ stdlibِ مخزن (بازوی اعتمادِ سمتِ پایتون)."""
    return verify_pubkey_text(manifest_path, sig_path, pubinfo(pub_pem_path)["minisign_pubkey_text"])


def verify_pubkey_text(manifest_path: str, sig_path: str, pubkey_text: str) -> bool:
    """همان بررسی، با کلیدِ عمومی به‌شکلِ متنِ minisign یا base64ِ (alg|key_id|pub32).

    CI تنها چیزی که از repo var دارد همین رشتهٔ public است (PEM درِ گیت نیست)،
    پس راستی‌آزماییِ بستهٔ داده درِ pipeline بی‌کلیدِ خصوصی ممکن است.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import base64 as _b64
    from bors_minisign import verify_minisign, parse_minisign_pubkey
    blob = str(pubkey_text or "").strip()
    if blob and not blob.startswith("untrusted comment:"):
        raw = _b64.b64decode("".join(blob.split()))
        if len(raw) == 42:                       # alg|key_id|public32 ⇒ همان متنِ minisign
            blob = _pubkey_text(raw[10:], raw[2:10])
        elif len(raw) == 32:                     # فقطِ کلیدِ خام (VITE_MOBILE_MANIFEST_PUBKEY)
            blob = _pubkey_text(raw, key_id_of_raw(raw))
    data = open(manifest_path, "rb").read()
    sig_text = open(sig_path, encoding="utf-8").read()
    key_id, _public = parse_minisign_pubkey(blob)
    from bors_minisign import parse_minisign_signature
    # `verify_minisign` خطا را *raise* می‌کند؛ فراخوان‌ها (CI، گارد) boolean می‌خواهند،
    # پس هر دوی «کلیدِ ناهمخوان» و «امضایِ نخوان» به False می‌رسند و دلیل درِ لاگ
    # CLI چاپ می‌شود — هیچ‌کدام استثنای خام بیرون نمی‌فرستد.
    try:
        if not verify_minisign(data, sig_text, blob):
            return False
        return parse_minisign_signature(sig_text)["key_id"] == key_id
    except ValueError:
        return False


def _pubkey_text(raw32: bytes, key_id8: bytes) -> str:
    """متنِ کلیدِ عمومیِ minisign از رویِ ۳۲ بایتِ خام + key_id هشت‌بایتی."""
    import base64 as _b64
    return "untrusted comment: minisign public key: %s\n%s" % (
        key_id8.hex(), _b64.b64encode(ALG + key_id8 + raw32).decode())


def _spki(raw32: bytes) -> bytes:
    return bytes.fromhex("302a300506032b6570032100") + raw32


def key_id_of_raw(raw32: bytes) -> bytes:
    """key_id درِ همین قرارداد = SHA-256(DERِ public)[:8] (هم TS، هم پایتون)."""
    return hashlib.sha256(_spki(raw32)).digest()[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keygen", action="store_true")
    ap.add_argument("--out-dir", default=os.path.expanduser("~/.bors_mobile_keys"))
    ap.add_argument("--key", default=os.environ.get("BORS_MOBILE_MANIFEST_KEY", ""))
    ap.add_argument("--key-pub", default="")
    ap.add_argument("--pubkey-b64", default="",
                    help="کلیدِ عمومی به‌شکلِ base64(alg|key_id|pub32) یا متنِ minisign "
                         "(همان رشته‌ای که درِ repo var است؛ PEM لازم نیست)")
    ap.add_argument("--pubinfo", action="store_true", help="چاپِ کلید عمومی/KeyId برایِ ثابتِ کلاینت")
    ap.add_argument("--in", dest="inp", default="")
    ap.add_argument("--out", dest="outp", default="")
    ap.add_argument("--sig", default="")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--allow-env-key", action="store_true",
                    help="کلید از BORS_MOBILE_MANIFEST_KEY_PEM (متنِ PEM درِ secret CI)")
    a = ap.parse_args()

    if a.keygen:
        print(json.dumps(keygen(a.out_dir), ensure_ascii=False, indent=1))
        return 0

    if a.pubinfo:
        if not a.key_pub:
            raise SystemExit("--pubinfo به --key-pub نیاز دارد")
        print(json.dumps(pubinfo(a.key_pub), ensure_ascii=False, indent=1))
        return 0

    priv = a.key
    pem_tmp = None
    if not priv and a.allow_env_key and os.environ.get("BORS_MOBILE_MANIFEST_KEY_PEM"):
        import tempfile
        fd, pem_tmp = tempfile.mkstemp(prefix="bors-mobile-key-", text=True)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(os.environ["BORS_MOBILE_MANIFEST_KEY_PEM"])
        priv = pem_tmp
        os.chmod(pem_tmp, 0o600)
    if not a.verify and not priv:
        print(json.dumps({"status": "BLOCKED",
                          "reason": "کلید خصوصی داده نشده (--key یا BORS_MOBILE_MANIFEST_KEY_PEM); "
                                    "artifact امضاشدهٔ انتشار در نبودِ secret ساخته نمی‌شود"},
                         ensure_ascii=False))
        return 3
    try:
        if a.verify:
            if not a.inp or not a.sig or not (a.key_pub or a.pubkey_b64):
                raise SystemExit("--verify به --in، --sig و (--key-pub یا --pubkey-b64) نیاز دارد")
            if a.key_pub:
                ok = verify(a.inp, a.sig, a.key_pub)
                kid = key_id_from_pem(a.key_pub)
            else:
                ok = verify_pubkey_text(a.inp, a.sig, a.pubkey_b64)
                kid = "from-pubkey-b64"
            print(json.dumps({"verified": bool(ok), "manifest": a.inp, "sig": a.sig,
                              "key_id": kid}, ensure_ascii=False))
            return 0 if ok else 1
        if not a.inp:
            raise SystemExit("--in (مسیرِ manifest) لازم است")
        res = sign(a.inp, priv, a.outp or None)
        # خودسنجی با همان کلید (verify هم private و هم public را می‌شناسد) و با
        # publicِ کنارِ فایل اگر داده شده باشد — «PASS» یعنی خوانندۀ stdlibِ مخزن
        # هم همین بلوک را می‌پذیرد، نه فقط سازندۀ آن.
        pub = a.key_pub or (priv + ".pub")
        res["self_verified"] = verify(a.inp, res["sig_path"], pub if os.path.exists(pub) else priv)
        if res["self_verified"] is not True:
            raise SystemExit("امضایِ ساخته‌شده با bors_minisign نخواند — انتشار ممنوع")
        print(json.dumps(res, ensure_ascii=False, indent=1))
        if res["self_verified"] is False:
            return 1
        return 0
    finally:
        if pem_tmp:
            os.unlink(pem_tmp)


if __name__ == "__main__":
    sys.exit(main())
