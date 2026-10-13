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
import re
import shutil
import subprocess
import sys
import tempfile
import time

ALG = b"Ed"                      # Ed25519 رویِ پیامِ خام (WebCrypto-پذیر)
SIG_FILE_SUFFIX = ".sig"
ED25519_SPKI_PREFIX_LEN = 12     # 302a300506032b6570032100 → 12 بایتِ اول، 32 بایتِ بعدی کلید خام
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


def _run(cmd, **kw):
    # `stdin=DEVNULL` عمدی است: openssl اگر passphrase بخواهد و TTY نباشد، **درنگ**
    # می‌کند (رویِ ویندوز دو بارِ واقعی همین دیدم: دو openssl.exe بی‌خبر مانده بود).
    # درِ ابزارِ امضایِ انتشار، درنگ یعنی CIِ آویزان و یعنی «نتیجه نامعلوم». با
    # EOFِ فوری، openssl خودش خطا می‌دهد و آن خطا به BLOCKEDِ تمیز می‌رسد.
    kw.setdefault("stdin", subprocess.DEVNULL)
    kw.setdefault("timeout", 120)
    try:
        return subprocess.run(cmd, check=True, capture_output=True, **kw)
    except subprocess.TimeoutExpired:
        raise SystemExit("BLOCKED: openssl در 120s جواب نداد (درنگِ passphrase؟)")


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
def keygen(out_dir: str, passphrase: bytes | None = None) -> dict:
    """جفت‌کلیدِ Ed25519. اگر out_dir داخلِ مخزن باشد، رد می‌شود (کلید درِ گیت نیست).

    با `passphrase`، PEMِ خصوصی **رمزدار** ساخته می‌شود (PKCS#8 + BestAvailable) —
    همان چیزی که برایِ کلیدِ انتشار لازم است؛ بی‌آن، فایلِ خامِ رویِ دیسک تنها
    لایۀ حفاظت است و این برایِ کلیدِ واقعی قابلِ دفاع نیست.
    """
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
        enc = (serialization.BestAvailableEncryption(passphrase) if passphrase
               else serialization.NoEncryption())
        with open(priv, "wb") as f:
            f.write(k.private_bytes(serialization.Encoding.PEM,
                                    serialization.PrivateFormat.PKCS8, enc))
        with open(pub, "wb") as f:
            f.write(k.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo))
    elif be == "openssl":
        # `genpkey` گزینهٔ `-cipher` **ندارد** (این را درِ آزمونِ «بدونِ
        # cryptography» دیدم: رویِ runnerهایِ CI که cryptography نصب نیست همین
        # شاخه می‌دود و با `Extra (unknown) options: "cipher"` می‌شکست). لایۀ
        # رمز با `pkcs8 -topk8` رویِ همان PKCS#8 نشسته می‌شود.
        _run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv])
        if passphrase:
            plain = priv + ".plain"
            os.replace(priv, plain)
            try:
                _run(["openssl", "pkcs8", "-topk8", "-in", plain, "-out", priv,
                      "-v2", "aes-256-cbc",
                      "-passin", "env:%s" % KEY_PASS_ENV,
                      "-passout", "env:%s" % KEY_PASS_ENV])
            finally:
                if os.path.exists(plain):
                    os.unlink(plain)
        _run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub]
             + (["-passin", "env:%s" % KEY_PASS_ENV] if passphrase else []))
    else:
        raise SystemExit("BLOCKED: نه cryptography و نه openssl در دسترس نیست — "
                         "کلیدِ امضایِ manifest ساخته نمی‌شود (کلید آزمایشیِ ساختگی نه)")
    return {"backend": be, "private": priv, "public": pub, "encrypted": bool(passphrase),
            "public_key_id": key_id_from_pem(pub)}


def _spki_der_from_pem(blob: bytes) -> bytes | None:
    """PEMِ `PUBLIC KEY` (SPKI) → DER، با stdlib تنها. None یعنی این/public نیست.

    چرا اصلاً لازم شد: `openssl pkey -in <pub>` «کلیدِ خصوصی» می‌خواهد و با
    PUBLIC KEY می‌شکند (`Could not find private key`)؛ مسیرِ openssl درِ CI
    (که `cryptography` نصب نیست) دقیقاً رویِ همین افتاد و گاردِ امضا `rc=1 |
    0 pass / 0 fail` شد، در حالی که رویِ این ماشین هرگز اجرا نمی‌شد چون
    `cryptography` هست. خواندنِ یکِ کلیدِ عمومی base64ِ خالص است؛ هیچ ابزارِ
    بیرونی لازم نیست و نتیجه بینِ ویندوز و لینوکس یکی می‌ماند.
    """
    m = re.search(rb"-----BEGIN PUBLIC KEY-----(.+?)-----END PUBLIC KEY-----",
                  blob or b"", re.S)
    if not m:
        return None
    der = base64.b64decode(re.sub(rb"\s+", b"", m.group(1)))
    if der[:ED25519_SPKI_PREFIX_LEN] != ED25519_SPKI_PREFIX:
        raise SystemExit("این کلید عمومی Ed25519 نیست (SPKI prefix نخورد)")
    return der


def _load_private(blob: bytes):
    """کلیدِ خصوصیِ PKCS#8 → شیءِ کلید، با پیام‌هایِ BLOCKEDِ تمیز (نه trace).

    چرا لازم شد: درِ آزمونِ «عبارتِ عبورِ غلط» ابزار با `ValueError: Incorrect
    password` خام می‌ترکید؛ درِ ابزارِ نگهداریِ کلیدِ انتشار، کرشِ بی‌پیام با
    «ناموفق» یکی است و هر دو بدتر از «پذیرفت». پس سه حالت جدا می‌شوند: رمز ندارد،
    رمز دارد و عبارت نیست، رمز دارد و عبارت **غلط** است.
    """
    if _backend() != "cryptography":
        raise SystemExit("BLOCKED: این شاخه به `cryptography` نیاز دارد")
    from cryptography.hazmat.primitives import serialization
    if b"-----BEGIN" not in blob:
        # این حالت را جدا می‌کنیم چون وگرنه «باندلِ خراب» درِ پیامِ «رمزِ غلط»
        # پنهان می‌شود — و درِ روزِ بازیابی، آن دو راهِ کاملاً متفاوت‌اند.
        raise SystemExit("BLOCKED: این متن PEM نیست (باندل خراب است یا با ابزارِ "
                         "دومِ دیگری ساخته شده)")
    enc = b"ENCRYPTED PRIVATE KEY" in blob or b"Proc-Type: 4,ENCRYPTED" in blob
    pw = _key_passphrase()
    if not enc:
        return serialization.load_pem_private_key(blob, password=None)
    if not pw:
        raise SystemExit("BLOCKED: کلیدِ خصوصی رمز دارد و %s تنظیم نشده است"
                         % KEY_PASS_ENV)
    try:
        return serialization.load_pem_private_key(blob, password=pw)
    except ValueError:
        raise SystemExit("BLOCKED: %s غلط است — کلیدِ رمزدار باز نشد (هیچ چیزی "
                         "از رمز چاپ نمی‌شود)" % KEY_PASS_ENV)


def _require_passphrase_if_encrypted(pem_path: str) -> None:
    """کلیدِ رمزدار + بی‌عبارتِ عبور ⇒ BLOCKED **پیشِ** تماسِ openssl.

    چرا لازم است: openssl برایِ passphrase سوال می‌پرسد، و بی‌stdinِ تعاملی (CI،
    Git Bash، زیررویه) آن سوال یا EOF می‌گیرد یا درنگ می‌کند. «پیامِ درستِ ما» باید
    قبلِ آن بیاید، نه بعدِ درنگ.
    """
    try:
        blob = open(pem_path, "rb").read()
    except OSError:
        return
    if (b"ENCRYPTED PRIVATE KEY" in blob or b"Proc-Type: 4,ENCRYPTED" in blob) \
            and not _key_passphrase():
        raise SystemExit("BLOCKED: کلیدِ خصوصی رمز دارد و %s تنظیم نشده است "
                         "(از openssl سوالِ passphrase پرسیده نمی‌شود)" % KEY_PASS_ENV)


def _pub_der(pem_path: str) -> bytes:
    """DERِ SubjectPublicKeyInfo — از فایلِ کلید عمومی **یا** خصوصی (هر دو مجاز).

    خصوصیِ رمزدار هم خوانده می‌شود، با عبارتِ عبورِ `BORS_MOBILE_MANIFEST_KEY_PASS`.
    پیام‌هایِ خطا فقط نامِ متغیر را می‌گویند؛ هیچ‌جا مقدارِ رمز یا خودِ PEM چاپ
    نمی‌شود (لاگِ CI و `ps` جایِ آمنی نیستند).
    """
    blob = open(pem_path, "rb").read()
    pub = _spki_der_from_pem(blob)
    if pub is not None:                 # کلیدِ عمومی ⇒ بی‌ابزار، بی‌زیررویه
        return pub
    be = _backend()
    if be == "cryptography":
        from cryptography.hazmat.primitives import serialization

        def as_der(pub) -> bytes:
            return pub.public_bytes(serialization.Encoding.DER,
                                    serialization.PublicFormat.SubjectPublicKeyInfo)

        try:
            return as_der(_load_private(blob).public_key())
        except ValueError:
            try:
                return as_der(serialization.load_pem_public_key(blob))
            except ValueError:
                raise SystemExit("BLOCKED: این فایل نه کلیدِ خصوصیِ Ed25519 است نه "
                                 "PUBLIC KEY (PEM ناخوانا)")
    # openssl: این شاخه فقط برایِ کلیدِ **خصوصی** است؛ `pkey -in` خصوصی می‌خواهد
    # (عمومی‌اش `-pubin` می‌خواهد و از همان‌جا هرگز نمی‌گذرد، چون بالا گرفته شد).
    _require_passphrase_if_encrypted(pem_path)
    cmd = ["openssl", "pkey", "-in", pem_path, "-pubout", "-outform", "DER"]
    if _key_passphrase():
        cmd += ["-passin", "env:%s" % KEY_PASS_ENV]
    try:
        r = _run(cmd)
    except subprocess.CalledProcessError:
        raise SystemExit("BLOCKED: openssl کلیدِ خصوصی را باز نکرد (رمزِ غلط یا PEMِ "
                         "ناخوانا) — هیچ چیزی از رمز چاپ نمی‌شود")
    return r.stdout


def key_id_from_pem(pem_path: str) -> str:
    """هشت بایتِ اولِ SHA-256(DERِ public) → hex 16 رقمی (همان چیزی که درِ بلوک می‌آید)."""
    return hashlib.sha256(_pub_der(pem_path)).hexdigest()[:16]


def raw_public32(pem_path: str) -> bytes:
    der = _pub_der(pem_path)
    if der[:ED25519_SPKI_PREFIX_LEN] != ED25519_SPKI_PREFIX:
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
KEY_PASS_ENV = "BORS_MOBILE_MANIFEST_KEY_PASS"


def _key_passphrase() -> bytes | None:
    """عبارتِ عبورِ کلیدِ خصوصی، فقط از محیط. هیچ‌جا چاپ نمی‌شود و درِ آرگومانِ
    خطِ فرمان نمی‌آید (آن درِ `ps` و لاگِ CI دیده می‌شود)."""
    v = os.environ.get(KEY_PASS_ENV, "").strip()
    return v.encode("utf-8") if v else None


def _sign_bytes(data: bytes, priv_path: str) -> bytes:
    be = _backend()
    if be == "cryptography":
        # `_load_private` سه حالت را به BLOCKEDِ تمیز می‌رساند: رمز ندارد / رمز دارد
        # و عبارت نیست / رمز دارد و عبارت **غلط** است. بی‌این، عبارتِ غلط یک
        # `ValueError` خام از دلِ پشتیبانِ کلید بیرون می‌زد (آزمونِ N2 همین را دید).
        blob = open(priv_path, "rb").read()
        return _load_private(blob).sign(data)
    tmp = _tmpfile(data)
    _require_passphrase_if_encrypted(priv_path)
    cmd = ["openssl", "pkeyutl", "-sign", "-inkey", priv_path, "-rawin", "-in", tmp]
    if _key_passphrase():
        cmd += ["-passin", "env:%s" % KEY_PASS_ENV]
    try:
        r = _run(cmd)
        return r.stdout
    except subprocess.CalledProcessError:
        raise SystemExit("BLOCKED: openssl امضا نکرد — رمزِ غلط یا کلیدِ ناخوانا "
                         "(هیچ چیزی از عبارتِ عبور چاپ نمی‌شود)")
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


# ── نگهداریِ کلیدِ انتشار (backup / verify / restore) ───────────────────────
# چرا: گروۀ انتشارِ سریِ v2 رویِ یکِ کلیدِ خصوصیِ تنها می‌چرخد، و مالک درست
# به همین دلیل «کلیدِ رمزدارِ بدونِ روالِ پشتیبانِ اثبات‌شده» را BLOCKED کرد
# (docs/MOBILE-DATA-PACKAGE-V2-2026-10-13.md §12). بی‌این سه تابع، «نگهداری»
# یعنی کپیِ دستیِ یکِ فایلِ ناشناخته رویِ چیزی که هیچ‌کس بازیابی‌اش را نسنجیده.
# قراردادِ همین‌جا:
#   • بی‌bundleِ رمزدار منتشر نمی‌شود: کلیدِ خصوصیِ خامِ بی‌عبارتِ عبور رد می‌شود
#     (`--allow-unencrypted` برایِ کلیدِ نمایشی هست، نه برایِ کلیدِ انتشار).
#   • هیچ‌جا متنِ PEM یا عبارتِ عبور چاپ نمی‌شود؛ فقط key_id و sha256ِ خودِ bundle.
#   • bundle هرگز داخلِ مخزن نوشته نمی‌شود (همان قاعدۀ keygen).
#   • verify_backup یکِ چالشِ واقعی امضا/بررسی می‌زند، پس «فایل هست» با
#     «کلید کار می‌کند» یکی نمی‌شود.

BUNDLE_MAGIC = "BorsTerminal-mobile-manifest-key-backup"
BUNDLE_VERSION = 1


def _outside_repo(path: str, what: str) -> str:
    ap = os.path.abspath(os.path.expanduser(path))
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ap == repo or ap.startswith(repo + os.sep):
        raise SystemExit("%s نباید داخلِ مخزن نوشته شود: %s" % (what, ap))
    return ap


def backup(key_path: str, out_dir: str, allow_unencrypted: bool = False) -> dict:
    """باندلِ متنِ base64 از کلیدِ خصوصی + متادیتا، بیرونِ مخزن، با اثرِ انگشتی.

    باندل فقط خودِ PEM است (هیچ رمزِ افزوده‌ای رویِ PEMِ رمزدار نمی‌گذارم؛ دو
    لایۀ رمز، دو لایۀ گم‌شدن است). حفاظت = عبارتِ عبورِ PKCS#8 درِ خودِ PEM.
    """
    key_path = os.path.expanduser(key_path)
    # ترتیبِ عمدي: اولِ اول مقصد سنجیده می‌شود. اگر خواندنِ کلید (که رمز می‌خواهد)
    # اول بیاید، «مقصد داخلِ مخزن است» هرگز گزارش نمی‌شود و اپراتور فکر می‌کند
    # مشکل فقط رمز است.
    out_dir = _outside_repo(out_dir, "پوشۀ پشتیبان")
    blob = open(key_path, "rb").read()
    enc = b"ENCRYPTED PRIVATE KEY" in blob or b"Proc-Type: 4,ENCRYPTED" in blob
    if not enc and not allow_unencrypted:
        raise SystemExit("BLOCKED: کلیدِ خصوصی رمزدار نیست. پشتیبانِ کلیدِ انتشارِ "
                         "خام رویِ هر مدیایی یعنی کلیدِ دسکتاپِ شما = ریشۀ اعتمادِ "
                         "همه؛ با --keygen --encrypted بسازید یا (فقط کلیدِ نمایشی) "
                         "--allow-unencrypted.")
    kid = key_id_from_pem(key_path)
    os.makedirs(out_dir, exist_ok=True)
    name = "bors-mobile-manifest-key-%s-%s" % (
        kid, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    body = base64.b64encode(blob).decode()
    armored = "\n".join(body[i:i + 76] for i in range(0, len(body), 76))
    # اثرِ انگشتیِ خودِ باندل **داخلِ** باندل می‌نشیند: پشتیبانی که بدونِ فایلِ
    # .sha256 کنارِ خودش کپی شود (USB، ابر، روی کاغذ) هم باید «بایت عوض شد» را
    # خودش بگوید، وگرنه خرابی‌اش درِ پیامِ «رمزِ غلط» پنهان می‌شود.
    text = "%s v%d\nkey_id=%s\nencrypted=%s\nbody_sha256=%s\n\n%s\n" % (
        BUNDLE_MAGIC, BUNDLE_VERSION, kid, "yes" if enc else "no",
        hashlib.sha256(armored.encode("utf-8")).hexdigest(), armored)
    bp = os.path.join(out_dir, name + ".bundle.txt")
    with open(bp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(bp, 0o600)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with open(bp + ".sha256", "w", encoding="utf-8", newline="\n") as f:
        f.write(sha + "  " + os.path.basename(bp) + "\n")
    return {"bundle": bp, "checksum_file": bp + ".sha256", "key_id": kid,
            "encrypted": bool(enc), "bundle_sha256": sha,
            "bytes": len(text), "restored_from": None}


def _read_bundle(bp: str) -> dict:
    if not os.path.exists(bp):
        raise SystemExit("BLOCKED: فایلِ پشتیبان نیست: %s" % bp)
    text = open(bp, encoding="utf-8").read()
    head, _, rest = text.partition("\n\n")
    lines = head.splitlines()
    if not lines or lines[0].split()[0] != BUNDLE_MAGIC:
        raise SystemExit("BLOCKED: این فایلِ پشتیبانِ همین ابزار نیست: %s" % bp)
    meta = dict(kv.split("=", 1) for kv in lines[1:] if "=" in kv)
    pem = base64.b64decode("".join(rest.split()))
    return {"meta": meta, "pem": pem, "text": text, "armor": rest}


def verify_backup(bp: str, key_path: str = "") -> dict:
    """بازیابیِ درونِ حافظه + چالشِ امضا/بررسی واقعی؛ کلیدِ اصلی اگر داده شد،
    هم‌انگشتیِ public دو کلید هم سنجیده می‌شود.

    ترتیبِ داوری عمدي است: اولِ اول **بسته سالم است یا نه** (checksum)، و فقط بعد
    رمزگشایی امتحان می‌شود. بی‌این، باندلِ یک‌بایت‌خورده به `ValueError` می‌خورد و
    اپراتور این را می‌خواند: «رمزِ غلط» — درِ روزِ بازیابی، دو تشخیصِ متفاوت یعنی
    دو کارِ متفاوت (دریافتِ باندلِ دیگر در برابرِ جست‌وجویِ رمز).
    """
    b = _read_bundle(bp)
    out = {"bundle": bp, "key_id_in_bundle": b["meta"].get("key_id"),
           "encrypted_in_bundle": b["meta"].get("encrypted")}
    sha_file = bp + ".sha256"
    want = ""
    if os.path.exists(sha_file):
        want = open(sha_file, encoding="utf-8").read().split()[0]
    got = hashlib.sha256(b["text"].encode("utf-8")).hexdigest()
    out["bundle_sha256_computed"] = got
    have_sum = bool(want)
    out["checksum_matches"] = have_sum and want == got
    # اثرِ انگشتیِ درونِ باندل (body_sha256): تمامیتِ بدنه، بی‌وابستگی به فایلِ کناری
    armor = b["armor"].rstrip("\n")
    self_sha = (b["meta"].get("body_sha256") or "").strip()
    self_got = hashlib.sha256(armor.encode("utf-8")).hexdigest()
    out["self_integrity_matches"] = bool(self_sha) and self_sha == self_got
    corrupt = (have_sum and not out["checksum_matches"]) or \
              (self_sha and not out["self_integrity_matches"])
    if not have_sum:
        out["checksum_note"] = ("فایلِ .sha256 کنارِ باندل نیست ⇒ از اثرِ درونِ خودِ "
                                "باندل استفاده شد")
    if not self_sha:
        out["self_integrity_note"] = "باندل اثرِ درونی ندارد (نسخۀ پیشینِ همین ابزار)"
    if corrupt:
        out["verdict"] = "FAIL"
        out["fail_reason"] = ("checksum: باندل با اثرِ ثبت‌شدۀ خودش نمی‌خواند ⇒ این "
                              "باندل همان چیزی نیست که پشتیبان گرفته شد (رمزگشایی برایِ "
                              "تشخیصِ «رمز غلط» معنا ندارد)")
        return out
    tmp = tempfile.mkdtemp(prefix="bors-verify-backup-")
    try:
        kp = os.path.join(tmp, "restored.key")
        with open(kp, "wb") as f:
            f.write(b["pem"])
        os.chmod(kp, 0o600)
        pub32 = None
        try:
            kid = key_id_from_pem(kp)
            out["key_id_after_restore"] = kid
            out["key_id_matches"] = kid == b["meta"].get("key_id")
            msg = b"bors-backup-challenge"
            sig = _sign_bytes(msg, kp)
            pub32 = raw_public32(kp)
            out["signature_roundtrip"] = _ed25519_verify_pub(pub32, msg, sig)
        except SystemExit as e:
            out["key_id_matches"] = False
            out["signature_roundtrip"] = False
            out["fail_reason"] = str(e)[:200]
        if key_path and pub32 is not None:
            out["same_public_as_original"] = (
                raw_public32(os.path.expanduser(key_path)) == pub32)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out["verdict"] = ("PASS" if ((out["checksum_matches"] or out["self_integrity_matches"])
                                 and out.get("key_id_matches")
                                 and out.get("signature_roundtrip")
                                 and out.get("same_public_as_original", True))
                      else "FAIL")
    return out


def restore(bp: str, out_dir: str) -> dict:
    """بازگردانیِ کلید از باندل (بیرونِ مخزن) و اثباتِ کارکرد، نه فقط نوشتنِ فایل.

    باندل **پیش ازِ هر نوشتن** سنجیده می‌شود: بازیابیِ باندلِ خراب نباید پوشۀ
    کلیدِ کاربر را با یکِ فایلِ 0600 بی‌فایر پُر کند (آن فایل بعداً «کلیدِ موجود»
    شمرده می‌شود و هر بازیابیِ دوباره‌ای رویِ آن رد می‌خورد).
    """
    b = _read_bundle(bp)
    pre = verify_backup(bp)
    if pre["verdict"] != "PASS":
        raise SystemExit("BLOCKED: باندل درِ سنجشِ پیش ازِ بازیابی رد شد (%s) ⇒ چیزی "
                         "نوشته نشد" % pre.get("fail_reason", pre))
    out_dir = _outside_repo(out_dir, "پوشۀ بازیابی")
    os.makedirs(out_dir, exist_ok=True)
    kp = os.path.join(out_dir, "mobile_manifest.key")
    if os.path.exists(kp):
        raise SystemExit("BLOCKED: %s هست؛ بازیابی رویِ کلیدِ موجود نمی‌نویسد "
                         "(اول خودتان جابه‌جایش کنید)" % kp)
    with open(kp, "wb") as f:
        f.write(b["pem"])
    os.chmod(kp, 0o600)
    # public از خودِ خصوصیِ بازگردانده‌شده ساخته می‌شود، نه از باندل، تا سنجشِ
    # «همان کلید» معنا داشته باشد
    be = _backend()
    pub = os.path.join(out_dir, "mobile_manifest.key.pub")
    if be == "cryptography":
        from cryptography.hazmat.primitives import serialization
        k = _load_private(b["pem"])
        with open(pub, "wb") as f:
            f.write(k.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo))
    elif be == "openssl":
        cmd = ["openssl", "pkey", "-in", kp, "-pubout", "-out", pub]
        if _key_passphrase():
            cmd += ["-passin", "env:%s" % KEY_PASS_ENV]
        try:
            _run(cmd)
        except subprocess.CalledProcessError:
            raise SystemExit("BLOCKED: openssl کلیدِ عمومی را از کلیدِ بازگردانده‌شده "
                             "نساخت (رمزِ غلط یا PEMِ ناخوانا)")
    else:
        raise SystemExit("BLOCKED: نه cryptography و نه openssl — بازیابی اثبات‌شدنی نیست")
    v = verify_backup(bp, kp)
    return {"restored_key": kp, "restored_pub": pub, "verify": v,
            "key_id": v.get("key_id_after_restore"),
            "expect_in_ci_var": pubinfo(pub)["raw_public_b64"] if os.path.exists(pub) else ""}


def _ed25519_verify_pub(pub32: bytes, msg: bytes, sig: bytes) -> bool:
    """بررسی با stdlibِ مخزن (bors_minisign) — بی‌وابستگی به backendِ امضا."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from bors_minisign import _ed25519_verify
        return bool(_ed25519_verify(pub32, msg, sig))
    except Exception:
        return False


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
    ap.add_argument("--encrypted", action="store_true",
                    help="با --keygen: PEMِ خصوصی **رمزدار** ساخته شود؛ عبارتِ عبور از "
                         "%s خوانده می‌شود و هیچ‌جا چاپ نمی‌شود" % KEY_PASS_ENV)
    ap.add_argument("--backup", action="store_true",
                    help="باندلِ پشتیبانِ کلیدِ خصوصی (بیرونِ مخزن، 0600، با sha256)")
    ap.add_argument("--backup-dir", default="",
                    help="پوشۀ پشتیبان (پیش‌فرض: همان --out-dir)")
    ap.add_argument("--verify-backup", default="", metavar="BUNDLE",
                    help="سنجشِ یکِ باندل: checksum + بازیابیِ key_id + چالشِ امضا/بررسی")
    ap.add_argument("--restore", default="", metavar="BUNDLE",
                    help="بازگردانیِ کلید از باندل رویِ --restore-out")
    ap.add_argument("--restore-out", default="",
                    help="پوشۀ بازیابی (بیرونِ مخزن؛ رویِ کلیدِ موجود نمی‌نویسد)")
    ap.add_argument("--allow-unencrypted", action="store_true",
                    help="فقط برایِ کلیدِ نمایشی: پشتیبانِ کلیدِ بی‌رمز را بپذیر")
    a = ap.parse_args()

    if a.backup:
        if not a.key:
            raise SystemExit("--backup به --key نیاز دارد (کلیدِ خصوصیِ موجود)")
        print(json.dumps(backup(a.key, a.backup_dir or a.out_dir,
                                allow_unencrypted=a.allow_unencrypted),
                         ensure_ascii=False, indent=1))
        return 0

    if a.verify_backup:
        vr = verify_backup(a.verify_backup, a.key)
        print(json.dumps(vr, ensure_ascii=False, indent=1))
        # «سنجیدم» با «موفق بود» یکی نیست: rc=0 فقط وقتی که باندل واقعاً قابلِ
        # بازیابی و امضازدن باشد، تا این فرمان درِ اسکریپتِ نگهداری گیت بشود.
        return 0 if vr["verdict"] == "PASS" else 3

    if a.restore:
        if not a.restore_out:
            raise SystemExit("--restore به --restore-out نیاز دارد (پوشۀ بیرونِ مخزن)")
        r = restore(a.restore, a.restore_out)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["verify"]["verdict"] == "PASS" else 3

    if a.keygen:
        pw = None
        if a.encrypted:
            pw = _key_passphrase()
            if not pw:
                print(json.dumps({"status": "BLOCKED",
                                  "reason": "%s تنظیم نشده ⇒ کلیدِ رمزدار ساخته نمی‌شود "
                                            "(کلیدِ خامِ دیسک برایِ کلیدِ انتشار قابلِ دفاع نیست)"
                                            % KEY_PASS_ENV}, ensure_ascii=False))
                return 3
        print(json.dumps(keygen(a.out_dir, passphrase=pw), ensure_ascii=False, indent=1))
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
