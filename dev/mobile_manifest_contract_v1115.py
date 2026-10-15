#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/mobile_manifest_contract_v1115.py — قراردادِ manifest: سازنده ↔ مصرف‌کننده

چرا این گارد هست: کلاینت (`snapshotPackage.parseManifest`) شش رشته و دو عدد را
الزامی می‌داند، و سازنده (`scripts/build_mobile_snapshot.py`) همان‌ها را می‌نویسد.
هیچ‌کدام ازِ دو طرف *به‌تنهایی* تست نمی‌شد که «سازنده امروز چه می‌نویسد» با
«کلاینت چه می‌خواهد» یکی بماند — و نشانه‌اش همین بود که بستۀ منتشرشده رویِ
گوشی با manifestِ چهارکلیدیِ نسلِ پیش می‌آمد و فقط درِ اجرا روشن می‌شد.

این گارد *بستۀ واقعی* می‌سازد (ازِ market.db، با `--limit`) و همان manifest را با
فهرستِ الزامیِ خوانده‌شده ازِ خودِ سورسِ TypeScript می‌سنجد. اگر سازنده فیلدی را
کم بگذارد یا نوعش عوض شود، این‌جا قرمز می‌شود؛ اگر کلاینت سخت‌تر شود، آزمونِ
`mobile-manifest-contract.spec.ts` قرمز می‌شود. دو طرف، دو سنج.

اجرا:  python dev/mobile_manifest_contract_v1115.py     (۰ = سبز)
"""
import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PASS = FAIL = NOTVER = 0


def chk(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok    " + label)
    else:
        FAIL += 1
        print("  FAIL  " + label)


def skip(label, why):
    global NOTVER
    NOTVER += 1
    print("  SKIP  %s — %s" % (label, why))


def read(rel):
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


TS = read("frontend/src/shared/api/local/snapshotPackage.ts") or ""
PROD = read("scripts/build_mobile_snapshot.py") or ""
DB = os.path.join(ROOT, "market.db")

# ── ۱) فهرستِ الزامی ازِ خودِ کلاینت، نه ازِ حافظه ────────────────────────────
mreq = re.search(r"for \(const k of \[([^\]]+)\] as const\)", TS)
REQUIRED = [x.strip().strip("'\"") for x in mreq.group(1).split(",")] if mreq else []
chk(bool(REQUIRED), "M01 فهرستِ فیلدهایِ الزامی ازِ سورسِ کلاینت خوانده شد: %s"
    % ",".join(REQUIRED))
macc = re.search(r"ACCEPTED_MANIFEST_SCHEMA = (\d+)", TS)
ACCEPTED = int(macc.group(1)) if macc else -1
chk(ACCEPTED > 0, "M02 نسخۀ قراردادِ پذیرفتۀ کلاینت ازِ سورس خوانده شد (schema=%s)" % ACCEPTED)
chk(len(REQUIRED) == 5 and "gz_sha256" in REQUIRED and "min_app_version" in REQUIRED,
    "M03 قرائتِ فهرست آزمون‌پذیر است (پنج رشته + gz_bytes عددی + sha256 درِ list)")

# ── ۲) بستۀ واقعی بساز (ازِ market.db؛ نبودش = NOT_VERIFIED، نه سبزِ جعلی) ────
if not os.path.exists(DB):
    skip("M04..M14", "market.db درِ این ماشین نیست (گیت‌ایگنور) — سازنده اجرا نمی‌شود")
    print("mobile_manifest_contract_v1115: %d passed / %d failed / %d skipped"
          % (PASS, FAIL, NOTVER))
    sys.exit(1 if FAIL else 0)

OUT = tempfile.mkdtemp(prefix="bors-mfix-")
r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_mobile_snapshot.py"),
                    "--limit", "6", "--no-lzma", "--series", "mobile-latest-v2",
                    "--out", OUT],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
meta_p = os.path.join(OUT, "mobile_snapshot.db.meta.json")
gz_p = os.path.join(OUT, "mobile_snapshot.db.gz")
if r.returncode != 0 or not os.path.exists(meta_p):
    skip("M04..M14", "سازنده اجرا نشد (rc=%s): %s" % (r.returncode, (r.stderr or "")[-160:]))
else:
    man = json.load(open(meta_p, encoding="utf-8"))
    raw_meta = open(meta_p, "rb").read()
    missing = [k for k in REQUIRED if not isinstance(man.get(k), str) or not man.get(k)]
    chk(not missing, "M04 سازنده همهٔ %d فیلدِ الزامیِ کلاینت را نوشت%s"
        % (len(REQUIRED), ("" if not missing else " — کم دارد: " + ",".join(missing))))
    chk(man.get("schema_version") == ACCEPTED,
        "M05 schema_versionِ سازنده (%s) = پذیرشِ کلاینت (%s)" % (man.get("schema_version"), ACCEPTED))
    gb = man.get("gz_bytes")
    real_gb = os.path.getsize(gz_p)
    real_sha = hashlib.sha256(open(gz_p, "rb").read()).hexdigest()
    chk(isinstance(gb, int) and gb == real_gb, "M06 gz_bytes با بایت‌هایِ واقعیِ gz می‌خواند (%s)" % real_gb)
    chk(man.get("gz_sha256") == real_sha, "M07 gz_sha256 با digestِ واقعیِ gz می‌خواند")
    chk(re.fullmatch(r"[0-9a-f]{64}", str(man.get("gz_sha256"))) is not None,
        "M08 gz_sha256 شکلِ sha256ِ هگز دارد (کلاینت همین را چک می‌کند)")
    chk(b"\r\n" not in raw_meta, "M09 manifest LF-only است (با CRLF امضا فقط رویِ ماشین سازنده می‌خواند)")
    chk(man.get("series") == "mobile-latest-v2", "M10 سریِ اعلامی درِ manifest = سریِ هدف (%s)" % man.get("series"))
    # ادعاهایِ manifest باید با خودِ SQLite فایل بخواند — همان کاری که validateDatabase می‌کند
    db_p = os.path.join(OUT, "mobile_snapshot.db")
    con = sqlite3.connect(db_p)
    tables = sorted(r2[0] for r2 in con.execute("select name from sqlite_master where type='table'"))
    meta_rows = dict(con.execute("select key, value from meta"))
    con.close()
    claimed = sorted(man.get("tables") or [])
    chk(all(t in tables for t in claimed), "M11 جدول‌هایِ ادعاییِ manifest درِ بسته هست (%s)" % ",".join(claimed))
    chk(str(meta_rows.get("schema")) == str(man.get("db_schema")),
        "M12 db_schemaِ manifest = schemaِ داخلِ بسته (%s)" % meta_rows.get("schema"))
    con2 = sqlite3.connect(db_p)
    baked_keys = [x[0] for x in con2.execute("select key from baked")]
    con2.close()
    chk(all(k in baked_keys for k in (man.get("required_baked_keys") or [])),
        "M13 کلیدهایِ پختۀ لازم درِ بسته هست (%s)" % ",".join(man.get("required_baked_keys") or []))

    # ── ۳) زنجیرۀ امضا با کلیدِ دورریختنی (هرگز به‌عنوان ریشۀ اعتماد ثبت نمی‌شود) ──
    import sign_mobile_manifest as sm
    KD = tempfile.mkdtemp(prefix="bors-mkey-throwaway-")
    kg = sm.keygen(KD)
    sig_p = sm.sign(meta_p, kg["private"])["sig_path"]
    chk(sm.verify(meta_p, sig_p, kg["public"]),
        "M14 manifestِ سازنده با کلیدِ خودش راستی‌آزمایی می‌شود")
    bad = json.load(open(meta_p, encoding="utf-8"))
    bad["baked_ok"] = (bad.get("baked_ok") or 0) + 1
    bad_p = os.path.join(OUT, "tampered.json")
    with open(bad_p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bad, f, ensure_ascii=False, indent=1)
    chk(not sm.verify(bad_p, sig_p, kg["public"]),
        "M15 کنترلِ منفی: manifestِ دستکاری‌شده رد می‌شود (پس M14 کور نیست)")
    KD2 = tempfile.mkdtemp(prefix="bors-mkey-other-")
    kg2 = sm.keygen(KD2)
    chk(not sm.verify(meta_p, sig_p, kg2["public"]),
        "M16 کنترلِ منفی: امضایِ کلیدِ دیگر با کلیدِ عمومیِ دیگر نمی‌خواند")
    pi = sm.pubinfo(kg["public"])
    pub_b64 = base64.b64encode(b"Ed" + bytes.fromhex(pi["key_id"]) + base64.b64decode(pi["raw_public_b64"])).decode()
    chk(sm.verify_pubkey_text(meta_p, sig_p, pub_b64),
        "M17 CI با همان رشتهٔ base64(alg|key_id|pub32) که درِ vars می‌نشیند راستی‌آزمایی می‌کند")

    # ── ۴) fixture برایِ سنجِ سمتِ TypeScript ──────────────────────────────────
    FIX = os.path.join(ROOT, "dev", "fixtures", "mobile_manifest_v2.json")
    with open(FIX, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
        f.write("\n")
    chk(os.path.getsize(FIX) > 200, "M18 fixtureِ قرارداد نوشته شد (درِ dev/fixtures) — آزمونِ TS آن را می‌خواند")

print("mobile_manifest_contract_v1115: %d passed / %d failed / %d skipped" % (PASS, FAIL, NOTVER))
sys.exit(1 if FAIL else 0)
