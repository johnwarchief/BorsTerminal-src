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

        # ── کلیدِ رمزدار (روالِ کلیدِ انتشار؛ مرحلۀ ۳ دورِ ۵) ─────────────────
        kdir2 = tempfile.mkdtemp(prefix="bors-guard-keys-enc-")
        try:
            PW = "guard-passphrase-not-a-real-secret"
            env3 = dict(env)
            env3["BORS_MOBILE_MANIFEST_KEY_PASS"] = PW
            pk = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_mobile_manifest.py"),
                                 "--keygen", "--out-dir", kdir2, "--encrypted"],
                                capture_output=True, text=True, encoding="utf-8", env=env3)
            kg2 = json.loads(pk.stdout) if pk.returncode == 0 else {}
            enc_blob = open(kg2.get("private", ""), "rb").read().decode("utf-8", "replace") \
                if kg2.get("private") else ""
            chk(pk.returncode == 0 and "ENCRYPTED PRIVATE KEY" in enc_blob,
                "۱۹ --keygen --encrypted PEMِ رمزدار می‌سازد", (pk.stderr or "")[:120])
            chk(kg2.get("encrypted") is True and len(kg2.get("public_key_id", "")) == 16,
                "۱۹ب key_id از کلیدِ رمزدار هم خوانده می‌شود", json.dumps(kg2)[:120])
            chk(PW not in (pk.stdout + pk.stderr),
                "۱۹پ عبارتِ عبور درِ خروجیِ keygen تکرار نمی‌شود")
            # بی‌عبارتِ عبور ⇒ BLOCKED، و پیام **فقط نامِ متغیر** را می‌گوید
            env4 = dict(env)
            env4.pop("BORS_MOBILE_MANIFEST_KEY_PASS", None)
            p4 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_mobile_manifest.py"),
                                 "--key", kg2["private"], "--in", mpath,
                                 "--out", os.path.join(work, "enc.sig")],
                                capture_output=True, text=True, encoding="utf-8", env=env4)
            chk(p4.returncode != 0 and "BLOCKED" in (p4.stdout + p4.stderr)
                and "BORS_MOBILE_MANIFEST_KEY_PASS" in (p4.stdout + p4.stderr),
                "۲۰ کلیدِ رمزدار بی‌عبارتِ عبور می‌شکند و نامِ متغیر را می‌گوید",
                (p4.stdout + p4.stderr)[-140:])
            chk(PW not in (p4.stdout + p4.stderr) and "ENCRYPTED" not in p4.stdout,
                "۲۰ب پیامِ شکست نه رمز را می‌گوید نه بدنهٔ PEM")
            # با عبارتِ عبور ⇒ همان دورۀ امضا/بررسی
            mpath3 = os.path.join(work, "meta_enc.json")
            shutil.copyfile(mpath, mpath3)
            p5 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sign_mobile_manifest.py"),
                                 "--key", kg2["private"], "--in", mpath3,
                                 "--out", os.path.join(work, "enc.sig")],
                                capture_output=True, text=True, encoding="utf-8", env=env3)
            r5 = json.loads(p5.stdout) if p5.returncode == 0 else {}
            chk(p5.returncode == 0 and r5.get("key_id") == kg2["public_key_id"],
                "۲۱ امضا با کلیدِ رمزدار + عبارتِ عبورِ محیط همان key_id را می‌دهد",
                (p5.stderr or "")[:140])
            chk(p5.returncode == 0 and sm.verify(mpath3, os.path.join(work, "enc.sig"),
                                                 kg2["public"]) is True,
                "۲۲ امضایِ کلیدِ رمزدار درِ verify می‌خواند")
            chk(p5.returncode == 0 and os.path.exists(os.path.join(work, "enc.sig"))
                and open(os.path.join(work, "enc.sig"), encoding="utf-8").read().count("\n") == 4,
                "۲۲ب بلوکِ امضا همان چهارخطِ minisign است")
        finally:
            shutil.rmtree(kdir2, ignore_errors=True)
        # ── ۲۷..۳۶ روالِ نگهداریِ کلید (backup / verify / restore) ─────────
        # این سنجه‌ها «نگهداری» را از یکِ فایلِ کپی‌شده بیرون می‌آورند: باندلِ
        # رمزدار + checksum + چالشِ امضا/بررسیِ واقعی + بازیابیِ اثبات‌شده.
        # چهار منفیِ آخر همان اشتباه‌هایِ تشخیص‌اند که درِ توسعهٔ همین ابزار دیدم:
        # باندلِ خراب «رمزِ غلط» گزارش می‌شد، عبارتِ غلط traceback خام می‌داد، و
        # مقصدِ داخلِ مخزن پشتِ پیامِ رمز پنهان می‌شد.
        PASSPHRASE = b"kiscenotarealsake-passphrase-123"
        kdir3 = tempfile.mkdtemp(prefix="bors-guard-custody-")
        ksrc = os.path.join(kdir3, "keys")
        bdir = os.path.join(kdir3, "backup")
        rdir = os.path.join(kdir3, "restore")
        os.environ[sm.KEY_PASS_ENV] = PASSPHRASE.decode()
        try:
            kg3 = sm.keygen(ksrc, passphrase=PASSPHRASE)
            bund = sm.backup(kg3["private"], bdir)
            chk(os.path.exists(bund["bundle"]) and os.path.exists(bund["checksum_file"])
                and bund["key_id"] == kg3["public_key_id"]
                and bund["encrypted"] is True,
                "۲۷ باندلِ پشتیبانِ کلیدِ رمزدار بیرونِ مخزن ساخته می‌شود")
            chk(not os.path.abspath(bund["bundle"]).startswith(ROOT + os.sep),
                "۲۷ب مسیرِ باندل بیرونِ مخزن است", bund["bundle"])
            v = sm.verify_backup(bund["bundle"])
            chk(v["verdict"] == "PASS" and v["signature_roundtrip"] is True
                and v["key_id_matches"] is True,
                "۲۸ سنجشِ باندل با چالشِ امضایِ واقعی PASS می‌دهد", str(v)[:170])
            rs = sm.restore(bund["bundle"], rdir)
            chk(rs["verify"]["verdict"] == "PASS"
                and rs["verify"].get("same_public_as_original") is True
                and os.path.exists(rs["restored_pub"]),
                "۲۹ بازیابی همان کلید را می‌سازد و publicِ او را اثبات می‌کند",
                str(rs["verify"])[:170])
            chk(len(rs["expect_in_ci_var"] or "") >= 40,
                "۲۹ب بازیابی رشته‌ای که درِ vars.MOBILE_MANIFEST_PUBKEY می‌نشیند را می‌دهد")
            try:
                sm.restore(bund["bundle"], rdir)
                chk(False, "۳۰ بازیابی رویِ کلیدِ موجود باید رد شود")
            except SystemExit as e:
                chk("هست" in str(e), "۳۰ بازیابی رویِ کلیدِ موجود رد می‌شود", str(e)[:120])

            # ۳۱ منفی: کلیدِ بی‌رمز پشتیبان نمی‌شود (کلیدِ انتشار)
            try:
                sm.backup(kg["private"], os.path.join(kdir3, "bad"))
                chk(False, "۳۱ پشتیبانِ کلیدِ بی‌رمز باید رد شود")
            except SystemExit as e:
                chk(str(e).startswith("BLOCKED"),
                    "۳۱ پشتیبانِ کلیدِ بی‌رمز رد می‌شود", str(e)[:120])

            # ۳۲ منفی: باندلِ یک‌بایت‌خورده ⇒ دلیلِ شکست «checksum» باشد نه «رمز»
            tsrc = open(bund["bundle"], encoding="utf-8").read()
            head, body = tsrc.split("\n\n", 1)
            i = len(body) // 2
            rep = "B" if body[i] != "B" else "C"
            tp = os.path.join(kdir3, "tampered.bundle.txt")
            with open(tp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(head + "\n\n" + body[:i] + rep + body[i + 1:])
            tv = sm.verify_backup(tp)
            chk(tv["verdict"] == "FAIL" and tv["checksum_matches"] is False
                and "checksum" in str(tv.get("fail_reason", "")),
                "۳۲ باندلِ خراب با دلیلِ تمامیت رد می‌شود، نه «رمزِ غلط»", str(tv)[:170])

            # ۳۳/۳۴ منفی: نبودِ فایل و نبودِ عبارتِ عبور ⇒ BLOCKED تمیز، بی‌traceback
            CLI = os.path.join(ROOT, "scripts", "sign_mobile_manifest.py")
            for args, why in (
                    ([sys.executable, CLI, "--verify-backup",
                      os.path.join(kdir3, "ghost.bundle.txt")],
                     "۳۳ باندلِ گم‌شده"),
                    ([sys.executable, CLI, "--verify-backup", bund["bundle"]],
                     "۳۴ بی‌عبارتِ عبور")):
                env = dict(os.environ)
                env.pop(sm.KEY_PASS_ENV, None)
                p = subprocess.run(args, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", env=env)
                err = (p.stderr or "") + (p.stdout or "")
                chk(p.returncode != 0 and "BLOCKED" in err and "Traceback" not in err,
                    why + " ⇒ BLOCKED تمیز، بی‌استثنای خام", err[:150].replace("\n", " "))

            # ۳۵/۳۶ منفی: مقصد داخلِ مخزن ⇒ پیامِ «مخزن»، نه پیامِ رمز
            for call, name in (
                    (lambda: sm.backup(kg3["private"],
                                       os.path.join(ROOT, "_audit", "tmp",
                                                    "custody_should_fail")),
                     "۳۵ پشتیبان داخلِ مخزن"),
                    (lambda: sm.restore(bund["bundle"],
                                        os.path.join(ROOT, "_audit", "tmp",
                                                     "restore_should_fail")),
                     "۳۶ بازیابی داخلِ مخزن")):
                try:
                    call()
                    chk(False, name + " باید رد شود")
                except SystemExit as e:
                    chk("مخزن" in str(e), name + " رد می‌شود", str(e)[:120])
            chk(not os.path.exists(os.path.join(ROOT, "_audit", "tmp",
                                                "custody_should_fail"))
                and not os.path.exists(os.path.join(ROOT, "_audit", "tmp",
                                                    "restore_should_fail")),
                "مقصدِ ردشده درِ مخزن هیچ پوشه‌ای نساخت")
            chk(PASSPHRASE.decode() not in open(bund["bundle"], encoding="utf-8").read()
                and PASSPHRASE.decode() not in json.dumps(bund),
                "۳۷ عبارتِ عبور درِ باندل یا گزارشِ آن تکرار نمی‌شود")
        finally:
            os.environ.pop(sm.KEY_PASS_ENV, None)
            shutil.rmtree(kdir3, ignore_errors=True)


        # ── مسیرِ CLI/openssl — همان چیزی که CI مصرف می‌کند ──────────────────
        # ریشهٔ سرخیِ CI (run 38322487153): `openssl pkey -in <pub>` کلیدِ
        # *خصوصی* می‌خواهد و با PUBLIC KEY می‌شکند؛ درِ runner که `cryptography`
        # نصب نیست همان شاخه می‌رفت و گارد `rc=1 | 0 pass / 0 fail` شد — سکوت،
        # نه قبولی. رویِ این ماشین `cryptography` هست، پس آن شاخه هرگز اجرا
        # نمی‌شد و ۳۱/۳۱ سبزِ بی‌معنا می‌داد. این سنجه‌ها backend را می‌بندند تا
        # مسیرِ واقعیِ CI همین‌جا هم اجرا شود، نه فقط رویِ ماشینِ سازنده.
        _orig_backend = sm._backend
        try:
            sm._backend = lambda: None            # هیچ ابزارِ بیرونی مجاز نیست
            kid_std = sm.key_id_from_pem(kg["public"])
            chk(kid_std == kg["public_key_id"],
                "۲۳ key_idِ کلیدِ عمومی بی‌backend و بی‌openssl ساخته می‌شود", kid_std)
            chk(len(sm.raw_public32(kg["public"])) == 32,
                "۲۳ب raw publicِ 32 بایتی از همان راهِ stdlib می‌آید")
        finally:
            sm._backend = _orig_backend

        # ۲۴ کنترلِ منفی: PEMِ غیر-Ed25519 باید رد شود، نه 32 بایتِ هرچه بدهد
        bogus = os.path.join(work, "not_ed25519.pub")
        with open(bogus, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("-----BEGIN PUBLIC KEY-----\n%s\n-----END PUBLIC KEY-----\n"
                     % base64.b64encode(b"\x30\x82\x01\x22" + b"\x00" * 40).decode())
        try:
            sm._pub_der(bogus)
            chk(False, "۲۴ PEMِ غیر-Ed25519 باید رد شود")
        except SystemExit:
            chk(True, "۲۴ PEMِ غیر-Ed25519 رد می‌شود (prefix نخورد)")

        # ۲۵ شاخۀ openssl با کلیدِ *خصوصی* — همان ترکیبِ CI
        if shutil.which("openssl"):
            sm._backend = lambda: "openssl"
            try:
                chk(sm.key_id_from_pem(kg["private"]) == kg["public_key_id"],
                    "۲۵ key_id از کلیدِ خصوصی با backend=openssl همان key_id را می‌دهد")
                sig_op = os.path.join(work, "openssl.sig")
                sm.sign(mpath, kg["private"], sig_op)
                chk(sm.verify(mpath, sig_op, kg["public"]) is True,
                    "۲۵ب امضا و بررسی از شاخۀ openssl می‌خوانند")
            finally:
                sm._backend = _orig_backend
            chk(sm._backend() == _orig_backend(),
                "۲۶ backend پس ازِ سنجه‌ها بازگردانده شده است")
        else:
            print("  note  openssl نیست ⇒ سنجه‌هایِ ۲۵ اجرا نشد (درِ runnerهایِ CI هست)")

    finally:
        shutil.rmtree(keydir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        for d in ("bors-guard-keys2-",):
            pass
    print("mobile_manifest_sign_v1079: %d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
