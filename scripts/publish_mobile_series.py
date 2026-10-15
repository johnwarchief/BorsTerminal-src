#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_mobile_series.py — نشرۀِ امضاشدهٔ بستهٔ دادهٔ موبایل رویِ tagِ سری.

چرا این فایل هست (دور 6 اندروید، 1405/07/22): درِ مخزن **هیچ** مسیری برایِ
*انتشارِ* سریِ v2 وجود نداشت. `mobile.yml` بستهٔ داده را فقط **می‌خواند**
(`curl .../releases/download/${SNAPSHOT_SERIES}/...`)، و `market-data.yml` هم
سریِ دسکتاپ (`data-latest`) را می‌فرستد. سازندۀ بستۀ موبایل
(`build_mobile_snapshot.py`) market.db لازم دارد که درِ CI نیست (همان دلیلی که
گاردهای CI سرخ‌اند)، پس انتشارِ این سری از رویِ ماشینِ سازنده می‌شود، نه ازِ
runner. بی‌این فایل، «انتشار v2» یعنی چند دستورِ دستیِ فراموش‌شدنی رویِ مخزنِ
عمومی — و یکِ `--clobber` اشتباه رویِ `mobile-latest` یعنی قطعِ به‌روزرسانیِ
همۀ گوشی‌هایِ کهنه.

قراردادِ این ابزار (همه fail-closed، هیچ‌کدام با پرچمِ «رد شو» باز نمی‌شوند):
  1) سریِ هدف هرگز نمی‌تواند `mobile-latest` باشد — مسیرِ کهنه دست‌نخورده می‌ماند.
  2) پیش‌فرض `--dry-run` است: هرچه می‌سنجد و هرچه *خواهد کرد* چاپ می‌شود، و هیچ
     چیزی به GitHub نمی‌رود. انتشار فقط با `--yes` صریح.
  3) بی‌کلیدِ خصوصیِ بیرونِ مخزن و بی‌امضایِ قابلِ بررسی، حتی dry-run هم
     «آمادهٔ انتشار» اعلام نمی‌کند.
  4) پس ازِ انتشار، سه فایل ازِ **همان URLِ عمومی که گوشی می‌خواند** بازخوانده
     می‌شوند و digest + امضایِ زنده می‌سنجند؛ «upload rc=0» دلیلِ موفقیت نیست.
  5) هیچِ `release delete` و هیچِ حذفِ asset درِ این ابزار نیست. بدترینِ حالتِ
     ممکن (بازنویسیِ asset همان tag) فقط با `--yes` و فقط رویِ سریِ تازه رخ می‌دهد.

usage:
    # خشک، رویِ بستۀِ ساخته‌شده در dist_mobile/
    python scripts/publish_mobile_series.py --dir dist_mobile

    # انتشار واقعی (کلیدِ رمزدار؛ عبارتِ عبور از محیط)
    BORS_MOBILE_MANIFEST_KEY_PASS=... \\
    python scripts/publish_mobile_series.py --dir dist_mobile --yes \\
        --key ~/.bors_mobile_keys/mobile_manifest.key
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sign_mobile_manifest as sm                       # noqa: E402

# بستۀ داده را گوشی می‌خواند، بدونِ هیچ اعتبارنامه‌ای ⇒ مقصد باید مخزنِ **عمومیِ**
# توزیع باشد. مخزنِ src خصوصی است (تصمیمِ مالک، 2026-10-15) و اگر همین‌جا
# بماند، لینکِ ناشناس 404 می‌دهد و هیچ APK ای دادهٔ تازه نمی‌گیرد.
REPO_DEFAULT = "johnwarchief/BorsTerminal"
SERIES_DEFAULT = "mobile-latest-v2"

# سری‌هایی که **نباید** دست بخورند: همان چیزی که امروز رویِ گوشی‌هایِ کهنه است و
# هر کلاینتِ منتشرشدۀ پیشِ v2 از آن می‌خواند. فهرست صریح است نه پیشوندِ مبهم.
LEGACY_SERIES = ("mobile-latest", "data-latest")

GZ = "mobile_snapshot.db.gz"
META = "mobile_snapshot.db.meta.json"
SIG = META + ".sig"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _emit(report: dict, out_json: str) -> None:
    txt = json.dumps(report, ensure_ascii=False, indent=1)
    if out_json:
        d = os.path.dirname(out_json)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(out_json, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt + "\n")
    print(txt)


def _gh(args, check=True):
    return subprocess.run(["gh"] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


def _key_outside_repo(path: str) -> bool:
    ap = os.path.abspath(os.path.expanduser(path))
    return not (ap == ROOT or ap.startswith(ROOT + os.sep))


def preflight(a, R):
    """همۀ سنجه‌هایِ بی‌شبکه. چیزی که رد می‌شود درِ R ثبت و rc برمی‌گردد."""
    ck = []
    series = a.series.strip()
    R["series"] = series
    if series in LEGACY_SERIES or not series:
        ck.append(("target-series", False,
                   "سریِ هدف '%s' مسدود است — این ابزار هرگز series کهنه را "
                   "بازنویسی نمی‌کند (گوشی‌هایِ منتشرشده از آن می‌خوانند)" % series))
    else:
        ck.append(("target-series", True, ""))

    for name in (GZ, META):
        p = os.path.join(a.dir, name)
        if not os.path.exists(p):
            ck.append(("file:" + name, False, "نیست: %s" % p))
        else:
            ck.append(("file:" + name, True, "%d بایت · sha256 %s"
                       % (os.path.getsize(p), _sha256(p)[:16])))
    if any(not ok for n, ok, _ in ck if n.startswith("file:")):
        return ck

    gz = os.path.join(a.dir, GZ)
    meta_p = os.path.join(a.dir, META)
    with open(meta_p, encoding="utf-8") as f:
        meta = json.load(f)
    R["manifest"] = {k: meta.get(k) for k in
                    ("schema_version", "package_id", "series", "built_at",
                     "app_version", "gz_bytes", "gz_sha256", "baked_ok", "baked_fail")}

    # manifest باید **خودش** را با بایت‌هایِ رویِ دیسک بگوید، نه سازنده‌اش
    if meta.get("series") != series:
        ck.append(("manifest-series", False,
                   "manifest می‌گوید '%s' ولی هدف '%s' است ⇒ کلاینت series-mismatch "
                   "می‌دهد" % (meta.get("series"), series)))
    else:
        ck.append(("manifest-series", True, ""))
    real_bytes = os.path.getsize(gz)
    ck.append(("manifest-gz_bytes", meta.get("gz_bytes") == real_bytes,
               "manifest=%s دیسک=%d" % (meta.get("gz_bytes"), real_bytes)))
    real_sha = _sha256(gz)
    ck.append(("manifest-gz_sha256", str(meta.get("gz_sha256")) == real_sha,
               "manifest=%s…" % str(meta.get("gz_sha256"))[:16]))
    # newline="\n": با CRLF امضا درِ ماشینِ سازنده معتبر و رویِ گوشی نامعتبر می‌شد
    blob = open(meta_p, "rb").read()
    ck.append(("manifest-lf-only", b"\r\n" not in blob,
               "CRLF درِ manifest ⇒ امضا فقط رویِ همان ماشین می‌خواند"))
    return ck


def signing(a, R):
    """کلید + امضا + خودسنجی. بی‌کلیدِ معتبر، «آماده» اعلام نمی‌شود."""
    out = []
    key = os.path.expanduser(a.key) if a.key else ""
    if not key:
        if a.dry_run:
            out.append(("key-path", None,
                        "dry-run بی‌کلید: امضا ساخته نمی‌شود ⇒ «آمادهٔ انتشار» نه"))
        else:
            out.append(("key-path", False,
                        "--key لازم است؛ کلیدِ خصوصی درِ مخزن نیست و ازِ محیط هم "
                        "خوانده نمی‌شود (این ابزار محلی است، نه CI)"))
    if a.dry_run and not key and not os.environ.get("BORS_MOBILE_MANIFEST_KEY_PEM"):
        out.append(("key-path", None,
                    "dry-run بی‌کلید: امضا ساخته نمی‌شود ⇒ «آمادهٔ انتشار» نه"))
    pub = key + ".pub"
    if key:
        if not os.path.exists(key):
            out.append(("key-exists", False, "کلید نیست: %s" % key))
        elif not _key_outside_repo(key):
            out.append(("key-outside-repo", False,
                        "کلید داخلِ مخزن است ⇒ هر commit آن را فاش می‌کند"))
        else:
            head = open(key, "rb").read()
            enc = b"ENCRYPTED" in head or b"Proc-Type: 4,ENCRYPTED" in head
            pk8 = b"BEGIN ENCRYPTED PRIVATE KEY" in head
            out.append(("key-encrypted", bool(enc or pk8),
                        "کلیدِ رمزدار (PKCS#8)" if (enc or pk8) else
                        "کلیدِ خامِ بی‌رمز — برایِ کلیدِ انتشار قابلِ دفاع نیست؛ "
                        "--keygen --encrypted بسازید"))
            out.append(("key-pair", os.path.exists(pub),
                        pub if os.path.exists(pub) else "کلیدِ عمومی کنارِ خصوصی نیست"))
            try:
                kid = sm.key_id_from_pem(pub if os.path.exists(pub) else key)
                out.append(("key-id", True, kid))
                R["key_id"] = kid
                if a.expect_key_id and kid != a.expect_key_id.strip():
                    out.append(("key-id-matches-ci", False,
                                "کلیدِ اینجا=%s و var درِ CI=%s ⇒ APK این بستۀ را "
                                "نمی‌پذیرد" % (kid, a.expect_key_id)))
            except SystemExit as e:
                out.append(("key-id", False, str(e)[:120]))
    return out


def make_signature(a, R):
    """امضا + بررسیِ مستقلِ همان امضا (نه اعتماد به خروجیِ خودِ امضاگر)."""
    key = os.path.expanduser(a.key) if a.key else ""
    if not key or not os.path.exists(key):
        return ("skipped-no-key", None)
    sig_path = os.path.join(a.dir, SIG)
    res = sm.sign(os.path.join(a.dir, META), key, sig_path)
    pub = key + ".pub"
    ok = sm.verify(os.path.join(a.dir, META), sig_path, pub) if os.path.exists(pub) else False
    R["signature"] = {"sig_path": sig_path, "key_id": res.get("key_id"),
                      "verified_with_pair": bool(ok)}
    return ("signed", ok)


def independent_inspect(a, R):
    """بازرسِ مستقل (`tools/verify_mobile_snapshot.py`) — درِ subprocess، بی‌import."""
    pub = (os.path.expanduser(a.key) + ".pub") if a.key else ""
    cmd = [sys.executable, os.path.join(ROOT, "tools", "verify_mobile_snapshot.py"),
           "--dir", a.dir, "--expect-signed", "--tamper-test"]
    if os.path.exists(pub):
        cmd += ["--pubkey", pub]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    verdict = "unparsed"
    for line in (p.stdout or "").splitlines():
        if '"verdict"' in line:
            verdict = line.strip().strip(",")
    R["inspector"] = {"rc": p.returncode, "line": verdict[:200],
                      "tail": (p.stdout or "")[-400:]}
    return p.returncode == 0, verdict


def live_readback(a, R):
    """پس ازِ انتشار: همان URL که گوشی می‌خواند، همان digest، همان امضا."""
    base = "https://github.com/%s/releases/download/%s" % (a.repo, a.series)
    res = {}
    try:
        gb = urllib.request.urlopen(base + "/" + GZ, timeout=120).read()
        mb = urllib.request.urlopen(base + "/" + META, timeout=60).read()
        sb = urllib.request.urlopen(base + "/" + SIG, timeout=60).read()
    except Exception as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    tmp = os.path.join(a.dir, "_live_readback")
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, META), "wb") as f:
        f.write(mb)
    with open(os.path.join(tmp, SIG), "wb") as f:
        f.write(sb)
    with open(os.path.join(tmp, GZ), "wb") as f:
        f.write(gb)
    pub = (os.path.expanduser(a.key) + ".pub") if a.key else ""
    ver = ("n/a" if not pub else
           bool(sm.verify(os.path.join(tmp, META), os.path.join(tmp, SIG), pub)))
    res = {"gz_bytes_live": len(gb),
           "gz_sha256_live": hashlib.sha256(gb).hexdigest(),
           "gz_sha256_local": _sha256(os.path.join(a.dir, GZ)),
           "sig_verified_from_live_bytes": ver,
           "urls": [base + "/" + n for n in (GZ, META, SIG)]}
    res["ok"] = bool(res["gz_sha256_live"] == res["gz_sha256_local"] and ver is True)
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def publish(a, R):
    """gh release create/upload — فقط asset، هیچ حذفی، فقط tagِ سریِ خودش."""
    files = [os.path.join(a.dir, n) for n in (GZ, META, SIG)]
    for f in files:
        if not os.path.exists(f):
            return {"ok": False, "error": "فایلِ لازم نیست برایِ upload: %s" % f}
    view = _gh(["release", "view", a.series, "--repo", a.repo], check=False)
    if view.returncode != 0:
        notes = ("بستۀ دادۀ امضاشدۀ موبایل — سری %s\n\n"
                 "package_id: %s\nbuilt_at: %s\napp_version: %s\n"
                 "gz sha256: %s\nامضا: minisign Ed25519/raw، key_id %s\n"
                 "کلیدِ خصوصی درِ مخزن نیست؛ فقط public درِ vars.MOBILE_MANIFEST_PUBKEY."
                 % (a.series, R["manifest"].get("package_id"),
                    R["manifest"].get("built_at"), R["manifest"].get("app_version"),
                    R["manifest"].get("gz_sha256"), R.get("key_id", "?")))
        c = _gh(["release", "create", a.series, "--repo", a.repo, "--prerelease",
                 "--title", "بستۀ دادۀ موبایل — %s" % a.series, "--notes", notes],
                check=False)
        if c.returncode != 0:
            return {"ok": False, "step": "create", "error": (c.stderr or "")[:400]}
        R["created"] = True
    u = _gh(["release", "upload", a.series, "--repo", a.repo, "--clobber"] + files,
            check=False)
    if u.returncode != 0:
        return {"ok": False, "step": "upload", "error": (u.stderr or "")[:400]}
    return {"ok": True, "tag": a.series}


def main() -> int:
    ap = argparse.ArgumentParser(description="ناشرِ امضاشدۀ بستۀ دادۀ موبایل")
    ap.add_argument("--dir", default=os.path.join(ROOT, "dist_mobile"))
    ap.add_argument("--series", default=SERIES_DEFAULT)
    ap.add_argument("--repo", default=REPO_DEFAULT)
    ap.add_argument("--key", default="", help="مسیرِ کلیدِ خصوصی (بیرونِ مخزن)")
    ap.add_argument("--expect-key-id", default="",
                    help="key_id ای که درِ vars.MOBILE_MANIFEST_PUBKEY نشسته؛ "
                         "ناهمخوان ⇒ کلاینت این بسته را رد می‌کند")
    ap.add_argument("--yes", action="store_true", help="انتشارِ واقعی (پیش‌فرض dry-run)")
    ap.add_argument("--out", default="_audit/mobile_series_publish.json")
    a = ap.parse_args()
    a.dry_run = not a.yes

    R = {"mode": "dry-run" if a.dry_run else "publish", "repo": a.repo, "dir": a.dir}
    checks = preflight(a, R)
    R["preflight"] = [{"check": n, "ok": ok, "note": note} for n, ok, note in checks]

    key_out = []
    if not any(n.startswith("file:") and not ok for n, ok, _ in checks):
        key_out = signing(a, R)
        R["key"] = [{"check": n, "ok": ok, "note": note} for n, ok, note in key_out]
        if all((ok is not False) for _n, ok, _x in checks + key_out):
            state, ok = make_signature(a, R)
            R["signing_state"] = state
            if state == "signed":
                R["signature_ok"] = bool(ok)
                good, verdict = independent_inspect(a, R)
                R["inspector_ok"] = bool(good)

    hard_fail = [c for c in checks + key_out if c[1] is False]
    ready = (not hard_fail
             and R.get("signing_state") == "signed"
             and R.get("signature_ok") and R.get("inspector_ok"))
    R["ready_to_publish"] = bool(ready)

    if not a.dry_run:
        if not ready:
            R["publish"] = {"ok": False,
                            "error": "زيرِ دروازۀ انتشار: سنجه‌هایِ سرخ را ببندید "
                                     "(هرگز بی‌امضایِ معتبر منتشر نمی‌شود)"}
        else:
            R["publish"] = publish(a, R)
            if R["publish"].get("ok"):
                R["live"] = live_readback(a, R)
    else:
        R["publish"] = {"ok": None, "note": "dry-run؛ چیزی به GitHub نرفت"}

    _emit(R, a.out)
    if a.dry_run:
        return 0 if ready else 3
    if not R["publish"].get("ok"):
        return 4
    return 0 if (R.get("live") or {}).get("ok") else 5


if __name__ == "__main__":
    raise SystemExit(main())
