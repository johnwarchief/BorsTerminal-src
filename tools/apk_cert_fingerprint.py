#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/apk_cert_fingerprint.py — گواهی و نسخۀ امضای یک APK، بی‌Java.

چرا لازم است: `apksigner verify --print-certs` تنها راهِ رسمی است و رویِ این
ماشین Java/Android SDK نصب نیست. برایِ بستنِ مأموریتِ اندروید دو چیز باید از
خودِ فایلِ artifact خوانده شود، نه ازِ متنِ ریلیز: (۱) گواهیِ امضاکننده چه
کسی است (CN=Android Debug ⇒ کلیدِ debug؛ هر چیزِ دیگر باید با اثرِ انگشتِ
کلیدِ انتشار مقایسه شود)، و (۲) امضا V1/V2/V3 است یا نه.

اثرِ انگشت همان چیزی است که apksigner چاپ می‌کند: SHA-256 ازِ DERِ گواهیِ
امضاکننده (نه ازِ کلیدِ عمومی، نه ازِ فایل).

قضاوت fail-closed است: بی‌هیچ گواهیِ خوانده‌شده «UNSIGNED» می‌گوید و تا
`--expect-fingerprint` داده نشود «SIGNED-UNVERIFIED» — هرگز خودش را نسخهٔ
رسمی نمی‌خواند.

مثال:
  python tools/apk_cert_fingerprint.py path/to/app-release.apk
  python tools/apk_cert_fingerprint.py --url https://.../x.apk --gh-token-from-env
  python tools/apk_cert_fingerprint.py x.apk --expect-fingerprint 3A:1B:... --json out.json

دربارۀ `--url` رویِ مخزنِ خصوصی: مسیرِ `releases/download` با tokenِ Bearer هم
404 می‌دهد (GitHub آن را ناشناس می‌شمارد). برایِ مخزنِ خصوصی اول با
`gh release download` فایل را بگذارید و بعدِ مسیرِ فایل را بدهید.

exit: 0 = بی‌کلیدِ debug (و اگر انتظار داده شده، هم‌خوان)، 1 = debug یا
بی‌امضا یا ناهمخوان؛ یعنی همان چیزی که یک گیتِ CI باید ببیند.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import tempfile
import urllib.request
import zipfile

MAGIC = b"APK Sig Block 42"
# هیچ شناسه‌ای ازِ حفظِ نام‌گذاری نمی‌شود: نسخهٔ پیشینِ این فایل جدولِ idها را
# ازِ حافظه نوشت و رویِ همان APKِ منتشرشده هیچ جفتی را نشناخت (درِ واقعیت
# 0x7109871A گواهیِ debug داشت). پس هر جفت با *پارسِ ساختاری* داوری می‌شود:
# اگر SignerInfos → SignedData → certificates ازِ آن بخوانده شود، جفتِ امضا است.
DEBUG_CN = "android debug"


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def _u64(b: bytes, o: int) -> int:
    return struct.unpack_from("<Q", b, o)[0]


def _seq(b: bytes, o: int):
    """یک section با پیشوندِ uint32: (اندازهٔ بدنه، آغازِ بدنه)."""
    n = _u32(b, o)
    return n, o + 4


def find_signing_block(blob: bytes):
    """جفت‌های (شناسه، داده) ازِ APK Signing Block. بی‌بلوک ⇒ None.

    هندسه ازِ اندازه‌گیریِ واقعیِ یکِ APKِ منتشرشده ثابت شد (نه ازِ متنِ استاندارد):
    u64ِ پیشِ magic = V؛ جفت‌ها ازِ cd-V آغاز می‌شوند و دقیقاً به cd-24 می‌رسند؛
    u64ِ نخست درِ cd-V-8 هم باید V باشد. اگر هر سه نخواند، بلوک را باور نمی‌کنیم.
    """
    e = blob.rfind(b"PK\x05\x06")
    if e < 0:
        return None
    cd_off = _u32(blob, e + 16)
    if cd_off < 32 or blob[cd_off - 16:cd_off] != MAGIC:
        return None
    v = _u64(blob, cd_off - 24)
    start = cd_off - v
    if v < 24 or start < 0 or _u64(blob, start - 8) != v:
        return None
    end = cd_off - 24
    p, pairs = start, []
    while p + 12 <= end:
        psz = _u64(blob, p)
        pid = _u32(blob, p + 8)
        if psz < 4 or p + 8 + psz > end:
            return None                       # walkِ نابه‌جا ⇒ بلوک را نمی‌پذیریم
        pairs.append((pid, blob[p + 12:p + 8 + psz]))
        p += 8 + psz
    return pairs if p == end else None


def _certs_from_length_prefixed(b: bytes, o: int, end: int) -> list[bytes]:
    out = []
    while o + 4 <= end:
        n = _u32(b, o)
        o += 4
        if n <= 0 or o + n > end:
            break
        out.append(b[o:o + n])
        o += n
    return out


def signer_certs(data: bytes) -> list[bytes]:
    """DERِ گواهی‌ها ازِ pairِ V2/V3: SignerInfos → SignerInfo → SignedData → certificates.

    داخلِ SignedData اولِ Digestها می‌آیند و بعدِ گواهی‌ها؛ بی‌پریدنِ دقیقِ
    Digestها، خواندنِ گواهی یک بایت جابه‌جا می‌شود و اثرِ انگشتِ غلط می‌دهد.
    """
    certs: list[bytes] = []
    try:
        si_n, si_o = _seq(data, 0)
        end_seq = min(si_o + si_n, len(data))
        o = si_o
        while o + 4 <= end_seq:
            inf_n = _u32(data, o)
            o += 4
            inf_end = min(o + inf_n, len(data))
            sd_n, sd_o = _seq(data, o)
            sd_end = min(sd_o + sd_n, inf_end)
            d_n, d_o = _seq(data, sd_o)            # Sequence<Digest>
            c_n, c_o = _seq(data, min(d_o + d_n, sd_end))   # Sequence<certificate>
            certs += _certs_from_length_prefixed(data, c_o, min(c_o + c_n, sd_end))
            o = inf_end
    except Exception:  # noqa: BLE001 — هر جفتی ساختارِ امضا ندارد؛ آن‌ها رد می‌شوند
        return []
    return certs


def _validity(cert) -> tuple[str, str]:
    """`not_valid_*_utc` از cryptography 42 آمد؛ رویِ runner هایِ قدیمی‌تر همان
    داتایمِ naive است. نسخه را نمی‌شناسیم، پس هر دو را امتحان می‌کنیم — و اگر
    هیچ‌کدام نبود، رشتهٔ خالی می‌دهیم نه کرش: نبودِ تاریخِ اعتبار، دلیلِ ردِ
    امضا نیست، و این ابزار برایِ خواندنِ اثرانگشت ساخته شده است."""
    for pair in (("not_valid_before_utc", "not_valid_after_utc"),
                 ("not_valid_before", "not_valid_after")):
        try:
            return cert.__getattribute__(pair[0]).isoformat(), \
                cert.__getattribute__(pair[1]).isoformat()
        except AttributeError:
            continue
    return "", ""


def _cert_info(cert) -> dict:
    from cryptography.hazmat.primitives import hashes
    fp = cert.fingerprint(hashes.SHA256()).hex()
    nb, na = _validity(cert)
    return {
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "serial": format(cert.serial_number, "x"),
        "not_before": nb,
        "not_after": na,
        "sha256_fingerprint": fp,
        "pretty_fingerprint": ":".join(fp[i:i + 2].upper() for i in range(0, 64, 2)),
    }


def _infos(der_list: list[bytes], via: str) -> list[dict]:
    from cryptography import x509
    out = []
    for der in der_list:
        try:
            c = x509.load_der_x509_certificate(der)
        except Exception as exc:  # noqa: BLE001
            out.append({"via": via, "error": repr(exc)[:120]})
            continue
        d = _cert_info(c)
        d["via"] = via
        out.append(d)
    return out


def report(path: str, expect: str = "") -> dict:
    from cryptography.hazmat.primitives.serialization import pkcs7
    with open(path, "rb") as f:
        blob = f.read()
    pairs = find_signing_block(blob)
    block_present = pairs is not None
    schemes: list[str] = []
    certs: list[dict] = []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            base, ext = os.path.splitext(n)
            if not n.startswith("META-INF/") or ext.upper() not in (".RSA", ".DSA", ".EC"):
                continue
            if "/" in base[len("META-INF/"):]:
                continue
            try:
                certs += _infos(pkcs7.load_der_pkcs7_certificates(z.read(n)), "V1:" + n)
            except Exception as exc:  # noqa: BLE001
                certs.append({"via": "V1:" + n, "error": repr(exc)[:120]})
    for pid, data in (pairs or []):
        found = signer_certs(data)
        if found:
            schemes.append("0x%08X" % pid)
            certs += _infos(found, "block:0x%08X" % pid)
    good = [c for c in certs if "sha256_fingerprint" in c]
    debug = any(DEBUG_CN in c["subject"].lower() or DEBUG_CN in c["issuer"].lower()
                for c in good)
    fps = {c["sha256_fingerprint"] for c in good}
    if not good:
        verdict = "UNSIGNED" if not block_present else "SIGNATURE-NOT-READABLE"
    elif debug:
        verdict = "DEBUG-SIGNED"
    elif expect:
        e = expect.lower().replace(":", "").strip()
        verdict = "SIGNED-MATCH" if any(e == c for c in fps) else "SIGNED-MISMATCH"
    else:
        verdict = "SIGNED-UNVERIFIED"
    return {
        "apk": os.path.basename(path),
        "bytes": os.path.getsize(path),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "signing_block_present": block_present,
        "signature_pairs": schemes,
        "certificates": certs,
        "is_debug_certificate": debug,
        "expected_fingerprint": expect or None,
        "verdict": verdict,
    }


def fetch(url: str, token: str = "") -> str:
    req = urllib.request.Request(url, headers=(
        {"Authorization": "Bearer " + token} if token else {}))
    fd, dest = tempfile.mkstemp(suffix=".apk", prefix="bors_apk_")
    with os.fdopen(fd, "wb") as out, urllib.request.urlopen(req, timeout=600) as r:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            out.write(b)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", nargs="?", help="مسیرِ فایل APK")
    ap.add_argument("--url", default="", help="APK را ازِ این URL بگیر")
    ap.add_argument("--gh-token-from-env", action="store_true",
                    help="GH_TOKEN را ازِ محیط برایِ مخزنِ خصوصی بخوان")
    ap.add_argument("--expect-fingerprint", default="",
                    help="اثرِ انگشتِ SHA-256 کلیدِ انتشار (بی‌فاصله یا دونقطه)")
    ap.add_argument("--json", default="", help="جایِ نوشتنِ JSON")
    a = ap.parse_args()
    if not a.url and not a.apk:
        print("یا مسیرِ فایل بده یا --url", file=sys.stderr)
        return 2
    tmp = fetch(a.url, os.environ.get("GH_TOKEN", "")) if a.url else None
    path = tmp or a.apk
    try:
        r = report(path, a.expect_fingerprint)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    print("APK        : %s  (%d B)" % (r["apk"], r["bytes"]))
    print("SHA-256    : %s" % r["sha256"])
    print("block      : %s" % ("present, pairs with signer certs: "
                               + (", ".join(r["signature_pairs"]) or "none")
                               if r["signing_block_present"] else "no signing block"))
    for c in r["certificates"]:
        if "error" in c:
            print("  %s: parse error %s" % (c["via"], c["error"]))
            continue
        print("  via %s" % c["via"])
        print("      subject    : %s" % c["subject"])
        print("      issuer     : %s" % c["issuer"])
        print("      serial     : %s" % c["serial"])
        print("      valid      : %s → %s" % (c["not_before"], c["not_after"]))
        print("      SHA-256    : %s" % c["pretty_fingerprint"])
    if a.expect_fingerprint:
        print("expected   : %s" % a.expect_fingerprint)
    print("VERDICT    : %s" % r["verdict"])
    if a.json:
        os.makedirs(os.path.dirname(a.json) or ".", exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    return 0 if r["verdict"] in ("SIGNED-MATCH", "SIGNED-UNVERIFIED") else 1


if __name__ == "__main__":
    sys.exit(main())
