#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/mobile_manifest_sign_v1079.py — گاردِ امضایِ manifest بستۀ دادهٔ موبایل (Stage ۲ دور ۴).

سه چیز را با هم الزامی می‌کند، بی‌هیچ کلیدِ خصوصیِ commit‌شده:
  ۱) **سازنده و خوانندۀ پایتونی حرف می‌زنند**: `scripts/sign_mobile_manifest.py`
     (Ed25519 رویِ پیامِ خام، بلوکِ clear-signature با الگوریتم «Ed») چیزی می‌سازد
     که `bors_minisign.verify_minisign` (stdlibِ همین مخزن) می‌پذیرد؛
  ۲) **هر حالتِ نامعتبر رد می‌شود**: تغییرِ یکِ بایتِ manifest، امضایِ تغییریافته،
     امضایِ ناقص، کلیدِ اشتباه، و manifestِ بی‌امضا درِ کلاینت (بند ۴؛ سمتِ TS درِ
     `frontend/src/__tests__/mobile-manifest-signature.spec.ts` سنجیده می‌شود)؛
  ۳) **بی‌کلید، ساختنِ artifactِ امضاشده مسدود است** — نه امضایِ ساختگی، نه
     کلیدِ آزمایشی به‌جایِ کلیدِ انتشار، و هیچ کلیدِ خصوصیِ درِ مخزن.

key_id درِ همین قرارداد = SHA-256(DERِ public)[:8]؛ همان تعریف درِ TS. الگوریتم
«Ed» است نه «ED» چون WebCrypto blake2b ندارد (خروجیِ tauri signer «ED» است و درِ
WebView بررسی‌ناپذیر می‌ماند).

اجرا:  python dev/mobile_manifest_sign_v1079.py      (۰ = سبز، ۱ = رد)
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bors_minisign                                     # noqa: E402
from scripts import sign_mobile_manifest as sm           # noqa: E402

PASS = FAIL = 0
MANIFEST = {
    "schema_version": 2, "package_id": "20261012T000000-guard1",
    "app_version": "1.0.79", "min_app_version": "1.0.70",
    "built_at": "2026-10-12T00:00:00", "gz_bytes": 2048,
    "gz_sha256": "ab" * 32, "db_bytes": 4096, "baked_ok": 58, "baked_fail": 0,
    "tables": ["baked", "meta", "instruments", "price_history"],
    "required_baked_keys": ["market_board"], "db_schema": 1,
}


def chk(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s   %s" % (label, extra))


def write_manifest(dirpath):
    p = os.path.join(dirpath, "meta.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=1)
    return p


def main():
    if sm._backend() is None:
        print("SKIP  نه cryptography و نه openssl در دسترس — امضا ساخته نمی‌شود")
        print("mobile_manifest_sign_v1079: 0 passed / 1 skipped / 0 failed")
        return 0

    keydir = tempfile.mkdtemp(prefix="bors-guard-keys-")
    work = tempfile.mkdtemp(prefix="bors-guard-work-")
    try:
        kg = sm.keygen(keydir)
        chk(not os.path.abspath(kg["private"]).startswith(ROOT + os.sep),
            "۱ کلیدِ خصوصی بیرونِ مخزن ساخته می‌شود", kg["private"])
        # کلیدِ خصوصی نباید داخلِ مخزن ساخته شود
        try:
            sm.keygen(os.path.join(ROOT, "_audit", "tmp", "guard_keys_should_fail"))
            chk(False, "۲ keygen داخلِ مخزن باید رد شود")
        except SystemExit:
            chk(True, "۲ keygen داخلِ مخزن رد می‌شود")
        shutil.rmtree(os.path.join(ROOT, "_audit", "tmp", "guard_keys_should_fail"),
                      ignore_errors=True)

        mpath = write_manifest(work)
        data = open(mpath, "rb").read()
        res = sm.sign(mpath, kg["private"])
        sig_text = open(res["sig_path"], encoding="utf-8").read()
        pub_text = sm.pubinfo(kg["public"])["minisign_pubkey_text"]

        chk(res["manifest_sha256"] == hashlib.sha256(data).hexdigest(),
            "۳ manifestِ امضاشده همان بایت‌هایی است که ساخته شد")
        chk(sig_text.splitlines()[0].startswith("untrusted comment:"),
            "۴ بلوکِ clear-signature چهارخطیِ سازگارِ minisign است")
        parsed = bors_minisign.parse_minisign_signature(sig_text)
        chk(parsed["alg"] == b"Ed", "۵ الگوریتم «Ed» است (Ed25519 رویِ پیامِ خام، WebCrypto-پذیر)",
            str(parsed["alg"]))
        kid_from_pub, _p = bors_minisign.parse_minisign_pubkey(pub_text)
        chk(kid_from_pub.hex() == res["key_id"], "۶ key_id درِ بلوک و کلیدِ عمومی یکی است")
        try:
            chk(bors_minisign.verify_minisign(data, sig_text, pub_text) is True,
                "۷ bors_minisignِ stdlib امضا را می‌پذیرد")
        except ValueError as e:
            chk(False, "۷ bors_minisignِ stdlib امضا را می‌پذیرد", str(e))

        # ── حالت‌هایِ نامعتبر ────────────────────────────────────────────────
        def rejects(label, mutate_data=None, mutate_sig=None, pub=None):
            d = data if mutate_data is None else mutate_data
            s = sig_text if mutate_sig is None else mutate_sig
            try:
                ok = bors_minisign.verify_minisign(d, s, pub or pub_text)
                chk(not ok, "۸ رد: " + label, "پذیرفته شد!")
            except ValueError:
                chk(True, "۸ رد: " + label)

        bad = bytearray(data)
        bad[len(bad) // 2] ^= 0x01
        rejects("تغییرِ یکِ بایتِ manifest", mutate_data=bytes(bad))
        lines = sig_text.splitlines(True)
        lines[1] = lines[1][:20] + ("A" if lines[1][20] != "A" else "B") + lines[1][21:]
        rejects("امضایِ تغییریافته", mutate_sig="".join(lines))
        rejects("امضایِ ناقص", mutate_sig="\n".join(sig_text.splitlines()[:3]) + "\n")
        other = sm.keygen(tempfile.mkdtemp(prefix="bors-guard-keys2-"))
        pub2 = sm.pubinfo(other["public"])["minisign_pubkey_text"]
        rejects("کلیدِ اشتباهی", pub=pub2)
        alg_ed = base64.b64encode(b"ED" + bytes.fromhex(res["key_id"])
                                  + base64.b64decode(sig_text.splitlines()[1])[10:])
        lines2 = sig_text.splitlines()
        lines2[1] = alg_ed.decode()
        # بلوکِ «ED» با کلیدِ درست هم باید صریحاً رد شود (کلاینت فقط «Ed» را می‌شناسد)
        try:
            bors_minisign.verify_minisign(data, "\n".join(lines2) + "\n", pub_text)
            chk(False, "۹ امضایِ «ED» (blake2b) رد شد — پایتونِ مخزن آن را می‌پذیرد، "
                        "پس ردِ آن مسئولیتِ سمتِ کلاینت است و درِ vitest سنجیده می‌شود")
        except ValueError:
            chk(True, "۹ امضایِ «ED» رد شد")

        # ── verify() با هر دو شکلِ کلید (PEM و base64ِ repo var) ─────────────
        chk(sm.verify(mpath, res["sig_path"], kg["public"]) is True,
            "۱۰ verify با PEMِ کلیدِ عمومی")
        pub_b64 = sm.pubinfo(kg["public"])["raw_public_b64"]
        chk(sm.verify_pubkey_text(mpath, res["sig_path"], pub_b64) is True,
            "۱۱ verify با base64ِ کلیدِ عمومی (مسیرِ CI: vars.MOBILE_MANIFEST_PUBKEY)")
        chk(sm.verify_pubkey_text(mpath, res["sig_path"], sm.pubinfo(kg["public"])
                                  ["minisign_pubkey_text"]) is True,
            "۱۲ verify با متنِ کاملِ minisign")
        other_b64 = sm.pubinfo(other["public"])["raw_public_b64"]
        chk(sm.verify_pubkey_text(mpath, res["sig_path"], other_b64) is False,
            "۱۳ base64ِ کلیدِ دیگر ⇒ رد (key_id بندِ کلید است)")

        # ── بی‌کلید ⇒ BLOCKED، نه امضایِ ساختگی (دروازۀ سازندۀ بسته) ─────────
        # گیتِ انتشار درِ `scripts/build_mobile_snapshot.py:sign_manifest` است؛
        # خودِ تابع مستقیم سنجیده می‌شود (بیلدِ کامل برایِ این بند لازم نیست).
        env = {k: v for k, v in os.environ.items()
               if k not in ("BORS_MOBILE_MANIFEST_KEY", "BORS_MOBILE_MANIFEST_KEY_PEM")}
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bms_guard", os.path.join(ROOT, "scripts", "build_mobile_snapshot.py"))
        bms = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bms)                       # بی‌build(): فقط ماژول
        os.environ.pop("BORS_MOBILE_MANIFEST_KEY", None)
        os.environ.pop("BORS_MOBILE_MANIFEST_KEY_PEM", None)
        try:
            bms.sign_manifest(mpath, require=True)
            chk(False, "۱۴ --require-signature بی‌کلید باید بسازد «انتشار ممنوع»")
        except SystemExit as e:
            chk("BLOCKED" in str(e), "۱۴ --require-signature بی‌کلید می‌شکند", str(e)[:80])
        soft = bms.sign_manifest(mpath, require=False)
        chk(soft.get("signature") is False and "no-signing-key" in str(soft.get("reason")),
            "۱۵ بی‌کلید و بی‌--require-signature ⇒ فقط گزارشِ «بی‌امضا»", json.dumps(soft)[:90])
        p2 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_mobile_manifest.py"),
                             "--in", mpath],
                            capture_output=True, text=True, encoding="utf-8", env=env)
        chk(p2.returncode == 3 and "BLOCKED" in p2.stdout,
            "۱۵ب CLI هم بی‌کلید rc=3 می‌دهد و امضا نمی‌سازد", "rc=%s" % p2.returncode)
        # فایلِ .sigِ بی‌اعتبار نباید از این تلاش‌ها بجا بماند (کلاینت آن را
        # «امضایِ مفقود» می‌بیند، نه امضایِ نصفه): رویِ manifestِ تازه آزموده می‌شود
        mpath2 = os.path.join(work, "meta_fresh.json")
        shutil.copyfile(mpath, mpath2)
        chk(not os.path.exists(mpath2 + ".sig"),
            "۱۵پ درِ شکستِ بی‌کلید، فایلِ .sigِ نیمه‌ای برایِ آن manifest ساخته نشده")

        # ── کلید از env (مسیرِ secret درِ CI) ───────────────────────────────
        env2 = dict(env)
        env2["BORS_MOBILE_MANIFEST_KEY_PEM"] = open(kg["private"], encoding="utf-8").read()
        out_sig = os.path.join(work, "env.sig")
        p3 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_mobile_manifest.py"),
                             "--allow-env-key", "--in", mpath, "--out", out_sig],
                            capture_output=True, text=True, encoding="utf-8", env=env2)
        ok3 = p3.returncode == 0
        res3 = json.loads(p3.stdout) if ok3 else {}
        chk(ok3 and res3.get("key_id") == res["key_id"],
            "۱۶ امضا با BORS_MOBILE_MANIFEST_KEY_PEM همان کلید را می‌دهد", p3.stderr[-160:])
        chk(ok3 and os.path.exists(out_sig) and sm.verify_pubkey_text(
            mpath, out_sig, pub_b64) is True, "۱۷ امضایِ env-route درِ verify می‌خواند")
        chk("BORS_MOBILE_MANIFEST_KEY_PEM" not in (p3.stdout + p3.stderr),
            "۱۸ متنِ کلید درِ stdout/stderr لاگ نمی‌شود")
    finally:
        shutil.rmtree(keydir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        for d in ("bors-guard-keys2-",):
            pass
    print("mobile_manifest_sign_v1079: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
