#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_mobile_snapshot.py — بازرسیِ مستقلِ بستهٔ آفلاین موبایل (قراردادِ v2).

چرا: سازنده (`scripts/build_mobile_snapshot.py`) همان چیزی را که نوشته دوباره
تأیید نمی‌کند؛ این ابزار **از بیرون** و فقط با stdlib، بایت‌هایِ واقعیِ artifact را
بازمی‌خواند و همه‌چیز را دوباره می‌سنجد:

  ۱) manifest هر کلیدِ لازمِ کلاینت را دارد و `schema_version` همان ۲ است
  ۲) اندازه و SHA-256 روی **همان بایت‌هایِ** `.gz` که گوشی دانلود می‌کند
  ۳) gz با gzip بازم‌شود و طولِ بازشده با `db_bytes` می‌خواند
  ۴) SQLite باز می‌شود و `PRAGMA integrity_check` سالم است
  ۵) جدول‌هایِ `tables` و کلیدهایِ `required_baked_keys` درِ بسته هستند
  ۶) `meta.built_at` / `meta.app_version` با manifest می‌خوانند
  ۷) manifest دستکاری‌شده (یکِ بایت) همان‌جا رد می‌شود، نه بعد ازِ دانلودِ بسته

خروجی: JSON روی stdout؛ exit 0 فقط اگر همه sبز باشد.
اجرا:
    python tools/verify_mobile_snapshot.py --dir _audit/tmp/stage4/out
    python tools/verify_mobile_snapshot.py --gz path.db.gz --meta path.db.meta.json --db path.db
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys

ACCEPTED_SCHEMA = 2
REQUIRED_STR = ("package_id", "built_at", "app_version", "min_app_version", "gz_sha256")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def check_manifest(meta: dict, label: str, R: dict) -> bool:
    """همان شرط‌هایِ `snapshotPackage.ts/parseManifest` — بی‌پذیرشِ بی‌آزمون."""
    ok = True
    sv = meta.get("schema_version")
    R["manifest.schema_version"] = sv
    if sv != ACCEPTED_SCHEMA:
        ok = False
        R["reject"] = "manifest-schema-unknown: %r" % (sv,)
    for k in REQUIRED_STR:
        v = meta.get(k)
        if not isinstance(v, str) or not v:
            ok = False
            R.setdefault("reject", "manifest-field-missing: %s" % k)
    gb = meta.get("gz_bytes")
    if not isinstance(gb, int) or gb <= 0:
        ok = False
        R.setdefault("reject", "manifest-field-missing: gz_bytes")
    if not (isinstance(meta.get("gz_sha256"), str) and SHA_RE.match(meta["gz_sha256"])):
        ok = False
        R.setdefault("reject", "manifest-field-missing: gz_sha256 شکلِ sha256 ندارد")
    R["manifest_valid"] = ok
    R["manifest_label"] = label
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="پوشه‌ای که هر سه فایلِ استانداردِ سازنده در آن است")
    ap.add_argument("--gz")
    ap.add_argument("--meta")
    ap.add_argument("--db")
    ap.add_argument("--pubkey", default="",
                    help="PEMِ کلیدِ عمومی برایِ بررسیِ اصالتِ manifest (bors_minisign)")
    ap.add_argument("--expect-signed", action="store_true",
                    help="بی‌فایلِ .sig ⇒ رد (همان سیاستِ کلاینت)")
    ap.add_argument("--tamper-test", action="store_true",
                    help="ثابت کن manifestِ تغییریافته رد می‌شود (بی‌دست‌زدنِ artifact)")
    a = ap.parse_args()

    d = a.dir or "."
    gz = a.gz or os.path.join(d, "mobile_snapshot.db.gz")
    meta_p = a.meta or os.path.join(d, "mobile_snapshot.db.meta.json")
    db = a.db or os.path.join(d, "mobile_snapshot.db")
    R: dict = {"gz": gz, "meta": meta_p, "db": db}

    for p in (gz, meta_p):
        if not os.path.exists(p):
            print(json.dumps({"error": "فایل نیست: %s" % p, **R}, ensure_ascii=False, indent=1))
            return 2

    with open(meta_p, "rb") as f:
        meta_bytes = f.read()
    meta = json.loads(meta_bytes.decode("utf-8"))
    R["manifest_bytes"] = len(meta_bytes)
    R["manifest"] = meta
    good = check_manifest(meta, "as-published", R)

    # ۲) اندازه و digest روی بایت‌هایِ artifact
    size = os.path.getsize(gz)
    R["gz_bytes_actual"] = size
    R["gz_bytes_matches_manifest"] = (size == meta.get("gz_bytes"))
    if not R["gz_bytes_matches_manifest"]:
        good = False
    digest = sha256_file(gz)
    R["gz_sha256_actual"] = digest
    R["gz_sha256_matches_manifest"] = (digest.lower() == str(meta.get("gz_sha256", "")).lower())
    if not R["gz_sha256_matches_manifest"]:
        good = False

    # ۳) gzip — امضایِ دو بایتِ اول و بازگشاییِ کامل
    with open(gz, "rb") as f:
        R["gzip_magic_ok"] = f.read(2) == b"\x1f\x8b"
    if not R["gzip_magic_ok"]:
        good = False
    try:
        raw = gzip.decompress(open(gz, "rb").read())
        R["gunzip_bytes"] = len(raw)
        R["gunzip_matches_db_bytes"] = (len(raw) == meta.get("db_bytes"))
    except Exception as e:                                   # noqa: BLE001
        R["gunzip_error"] = "%s: %s" % (type(e).__name__, e)
        good = False
        raw = b""

    # ۴/۵/۶) دیتابیسِ بازشده از بایت‌هایِifact (نه فایلِ کنارِ gz) — همان کاری که گوشی می‌کند
    if raw:
        tmp = os.path.join(d, "_verify_from_bytes.db")
        with open(tmp, "wb") as f:
            f.write(raw)
        c = sqlite3.connect(tmp)
        try:
            R["integrity_check"] = c.execute("PRAGMA integrity_check").fetchone()[0]
            R["integrity_ok"] = R["integrity_check"] == "ok"
            have = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            R["tables_present"] = sorted(have)
            want = meta.get("tables") or ["baked", "meta", "instruments", "price_history"]
            R["tables_missing"] = [t for t in want if t not in have]
            R["tables_ok"] = not R["tables_missing"]
            missing_keys = []
            for k in (meta.get("required_baked_keys") or ["market_board"]):
                if "baked" in have and not c.execute(
                        "SELECT 1 FROM baked WHERE key=? LIMIT 1", (k,)).fetchone():
                    missing_keys.append(k)
            R["required_baked_keys_missing"] = missing_keys
            R["baked_keys_ok"] = not missing_keys
            mrow = dict(c.execute("SELECT key, value FROM meta")) if "meta" in have else {}
            R["meta_table"] = mrow
            R["meta_built_at_matches_manifest"] = (mrow.get("built_at") == meta.get("built_at"))
            R["meta_app_version_matches_manifest"] = (mrow.get("app_version") == meta.get("app_version"))
            R["meta_schema_value"] = mrow.get("schema")
            if "baked" in have:
                R["baked_rows"] = c.execute("SELECT COUNT(*) FROM baked").fetchone()[0]
            for t in ("instruments", "price_history"):
                if t in have:
                    R["rows_" + t] = c.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            R["db_sample_key_bytes"] = (
                len(c.execute("SELECT json FROM baked WHERE key='market_board'").fetchone()[0])
                if "baked" in have and c.execute(
                    "SELECT 1 FROM baked WHERE key='market_board' LIMIT 1").fetchone() else None)
        finally:
            c.close()
            os.remove(tmp)
        good = good and R.get("integrity_ok", False) and R.get("tables_ok", False) \
            and R.get("baked_keys_ok", False) \
            and R.get("meta_built_at_matches_manifest", False) \
            and R.get("meta_app_version_matches_manifest", False)
    else:
        good = False

    # ۷) کنترلِ منفی: manifestِ دستکاری‌شده نباید بستۀ واقعی را بپذیرد.
    # شکلِ manifest تنهایی داوری نمی‌کند (`gz_bytes`ِ دروغین هم shape‌اش درست است)؛
    # ردِ واقعی آن‌جا رخ می‌دهد که مقدارِ manifest با بایت‌هایِ artifact مقایسه
    # می‌شود — دقیقاً همان ترتیبِ کلاینت: parseManifest ← verifyBytes ← validateDatabase.
    if a.tamper_test:
        flips = {
            "gz_bytes+1": lambda m: m.update(gz_bytes=int(m["gz_bytes"]) + 1),
            "schema_version=1": lambda m: m.update(schema_version=1),
            "sha_last_char_flipped": lambda m: m.update(gz_sha256=(
                m["gz_sha256"][:63] + ("0" if m["gz_sha256"][63] != "0" else "1"))),
            "drop_package_id": lambda m: m.pop("package_id", None),
            "db_bytes+1": lambda m: m.update(db_bytes=int(m.get("db_bytes", 0)) + 1),
            "tables_add_phantom": lambda m: m.update(tables=list(m.get("tables", [])) + ["ghost"]),
        }
        trials = {}
        for name, mut in flips.items():
            m2 = json.loads(meta_bytes.decode("utf-8"))
            mut(m2)
            r2: dict = {}
            shape_ok = check_manifest(m2, name, r2)
            verdict = "rejected-at-shape"
            if shape_ok:
                # همان مقایسه‌هایِ بایتیِ کلاینت رویِ artifactِ واقعی
                if int(m2.get("gz_bytes", -1)) != size:
                    verdict = "rejected-at-size"
                elif str(m2.get("gz_sha256", "")).lower() != digest.lower():
                    verdict = "rejected-at-digest"
                elif int(m2.get("db_bytes", -1)) != len(raw):
                    verdict = "rejected-at-gunzip-length"
                elif any(t not in R["tables_present"] for t in m2.get("tables", [])):
                    verdict = "rejected-at-table"
                else:
                    verdict = "ACCEPTED(!)"
            trials[name] = verdict
            R["tamper_detail_" + name] = r2.get("reject", "")
        R["tamper_trials"] = trials
        if any(v == "ACCEPTED(!)" for v in trials.values()):
            good = False

    # ۸) اصالت: امضایِ detached رویِ بایت‌هایِ manifest (همان کاری که کلاینت می‌کند)
    sig_path = meta_p + ".sig"
    R["sig_present"] = os.path.exists(sig_path)
    if a.expect_signed and not R["sig_present"]:
        R["signature_verdict"] = "signature-missing"
        good = False
    if R["sig_present"]:
        if not a.pubkey:
            R["signature_verdict"] = "no-pubkey-given-to-check"
        else:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from scripts.sign_mobile_manifest import verify as ms_verify
            try:
                R["signature_verdict"] = "valid" if ms_verify(meta_p, sig_path, a.pubkey) else "invalid"
            except Exception as e:                          # noqa: BLE001
                R["signature_verdict"] = "invalid: %s" % str(e)[:120]
            if R["signature_verdict"] != "valid":
                good = False
            # کنترلِ منفی: تغییرِ یکِ بایتِ manifest ⇒ امضا باید بشکند
            if R["signature_verdict"] == "valid":
                tmpm = meta_p + ".tampered.tmp"
                tampered = bytearray(meta_bytes)
                tampered[len(tampered) // 2] ^= 0x01
                with open(tmpm, "wb") as f:
                    f.write(bytes(tampered))
                try:
                    from scripts.sign_mobile_manifest import verify as v2
                    try:
                        R["tampered_manifest_signature"] = "still-valid(!)" if v2(tmpm, sig_path, a.pubkey) else "rejected"
                    except Exception:
                        R["tampered_manifest_signature"] = "rejected"
                finally:
                    os.remove(tmpm)
                if R["tampered_manifest_signature"] == "still-valid(!)":
                    good = False

    R["verdict"] = "PASS" if good else "FAIL"
    print(json.dumps(R, ensure_ascii=False, indent=1, default=str))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
