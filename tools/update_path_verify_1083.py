"""آزمونِ مسیرِ به‌روزرسانی رویِ کپیِ ایزولۀ 1.0.82 (نه نصبِ واقعیِ کاربر).

هرچه ادعا می‌شود از همین اسکریپت بیرون می‌آید: check → delta=true، دانلود،
progress تا ready، هشِ فایلِ دانلودی درِ %TEMP% با هشِ دانلودِ مستقلِ همان دارایی،
امضا با کلیدِ خودِ آپدیتِر، install، و در پایان Version.txt/بیسِ فایل‌ها و
دست‌نخورده‌بودنِ user.db و درختِ نسخۀ اصلی.
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

PORT = int(os.environ.get("PORT", "8123"))
COPY = r"C:\Users\PCMOD\Desktop\up1083_verify\app"
ORIG = r"C:\Users\PCMOD\Desktop\v1080_verify\app"
OUT = "_audit/tmp/up1083_update_test.json"
ASSET = "https://github.com/johnwarchief/BorsTerminal/releases/download/v1.0.83/" \
        "BorsTerminal_Patch_1.0.82_to_1.0.83.zip"
EXPECTED_SHA_REMOTE = "d3c3e8cf1cd359142f1ff661de84c4bb1596ad436b096522c3c4c20fcadd51f6"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.update import UPDATE_PUBKEY                      # noqa: E402
from bors_minisign import verify_minisign                 # noqa: E402

R = {"port": PORT, "copy": COPY, "steps": []}


def api(path, method="GET", body=None, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 headers={"User-Agent": "probe", "Content-Type": "application/json"})
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def step(name, ok, detail=""):
    R["steps"].append({"name": name, "ok": bool(ok), "detail": detail})
    print(("  ok   " if ok else "  FAIL ") + name + ("  " + str(detail)[:150] if detail else ""))
    return ok


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stat(p):
    s = os.stat(p)
    return {"size": s.st_size, "mtime": int(s.st_mtime)}


def tree_sig(root):
    """اثرِ انگشتِ نام/size/mtimeِ درخت (بی‌خواندنِ بانک‌ها) — برایِ اثباتِ بی‌تغیری."""
    import collections
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            if rel.startswith("market.db"):
                continue
            s = os.stat(p)
            out[rel] = (s.st_size, int(s.st_mtime))
    return hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()[:16], len(out)


# ۰) آمادگی: کپی بالا آمده؟ نسخهٔ 1.0.82 است؟
t0 = time.time()
ver = None
while time.time() - t0 < 240:
    try:
        ver = api("/api/update/version", timeout=5)
        break
    except Exception:
        time.sleep(3)
step("کپیِ 1.0.82 رویِ پورتِ 8123 بالا آمد", ver is not None, ver)
step("نسخۀ در حالِ اجرا 1.0.82 است (پیش از پچ)", (ver or {}).get("version") == "1.0.82", ver)

pre = {"user_db": stat(os.path.join(COPY, "user.db")),
       "screener_cache": stat(os.path.join(COPY, ".screener_cache.json"))
       if os.path.isfile(os.path.join(COPY, ".screener_cache.json")) else None,
       "orig_tree": tree_sig(ORIG)}
R["pre"] = pre
step("درختِ نسخۀ اصلیِ کاربر برایِ مقایسه مهر شد", pre["orig_tree"][1] > 1000, pre["orig_tree"])

# ۱) check — باید دلتا را انتخاب کند، نه نصبکننده
chk = api("/api/update/check")
R["check"] = chk
step("check نسخهٔ 1.0.83 را اعلام می‌کند", chk.get("available") is True
     and chk.get("latest_version") == "1.0.83", {k: chk.get(k) for k in ("available", "latest_version")})
step("check پچِ دلتا را به نصبِ کامل ترجیح می‌دهد (delta=true)", chk.get("delta") is True,
     {"delta": chk.get("delta"), "url_tail": (chk.get("url") or "")[-46:]})
step("همان URLِ پچِ 1.0.82→1.0.83 درِ مانیفستِ عمومی است",
     (chk.get("url") or "").endswith("BorsTerminal_Patch_1.0.82_to_1.0.83.zip"), chk.get("url"))
step("اندازۀ اعلامی با اندازۀ دانلودشده یکی است", int(chk.get("size") or 0) == 15_815_402,
     chk.get("size"))

# ۲) دانلود + پیشرفت
api("/api/update/download", method="POST",
    body={"url": chk["url"], "signature": chk["signature"], "version": "1.0.83"})
prog = None
t0 = time.time()
while time.time() - t0 < 300:
    prog = api("/api/update/progress")
    if prog.get("status") in ("ready", "error"):
        break
    time.sleep(2)
R["progress"] = prog
step("download به حالتِ ready رسید (امضا و هش درِ سرور راستیآزمایی شد)",
     prog.get("status") == "ready", {k: prog.get(k) for k in ("status", "downloaded", "total", "version")})

tmp = prog.get("path") or ""
step("فایلِ موقتِ دانلودی رویِ دیسک هست و sizeاش با مانیفست می‌خواند",
     bool(tmp) and os.path.isfile(tmp) and os.path.getsize(tmp) == 15_815_402,
     {"path": tmp, "bytes": os.path.getsize(tmp) if tmp and os.path.isfile(tmp) else None})

if tmp and os.path.isfile(tmp):
    local_sha = sha(tmp)
    step("هشِ فایلِ دانلودیِ برنامه = هشِ دانلودِ مستقلِ همان دارایی",
         local_sha == EXPECTED_SHA_REMOTE, local_sha)
    sig_text = chk.get("signature") or ""
    try:
        verify_minisign(open(tmp, "rb").read(), sig_text, UPDATE_PUBKEY)
        step("امضایِ minisignِ پچ با کلیدِ عمومیِ خودِ آپدیتِر تأیید شد", True, "verify_minisign ok")
    except Exception as e:
        step("امضایِ minisignِ پچ با کلیدِ عمومیِ خودِ آپدیتِر تأیید شد", False, repr(e)[:160])

# ۳) install — برنامه می‌میرد و apply_update.bat کار می‌کند (BORS_UPDATE_NORELAUNCH
#    درِ محیطِ پروسه set شده، پس relaunch نمی‌کند و چیزی بیرونِ کنترلِ ما بالا نمیآید)
try:
    ins = api("/api/update/install", method="POST", body={}, timeout=60)
except Exception as e:
    ins = {"status": "connection-reset", "message": str(e)[:120]}
R["install"] = ins
step("install پذیرفته شد (پاسخ یا resetِ عمدیِ پایانِ پروسه)",
     ins.get("status") in ("installing", "started", "connection-reset") or "spawn" in json.dumps(ins),
     {k: ins.get(k) for k in ("status", "mode", "message")})

# ۴) صبر برایِ اعمالِ پچ، بعد بررسیِ Version.txt و فایلها
t0 = time.time()
stamp = ""
while time.time() - t0 < 240:
    try:
        stamp = open(os.path.join(COPY, "Version.txt"), encoding="utf-8", errors="replace").read()
        if "1.0.83" in stamp:
            break
    except OSError:
        pass
    time.sleep(3)
R["version_txt"] = stamp.strip()
step("Version.txt درِ کپی مهرِ 1.0.83 را گرفت", "app_version=1.0.83" in stamp, stamp.strip().replace("\n", " | "))
step("patch_from و git_commitِ درست مهر شده‌اند",
     "patch_from=1.0.82" in stamp and "196cc87" in stamp, stamp.strip().replace("\n", " | "))

# APP_VERSION درِ باندلِ کپی (منبعِ یکتایِ نسخه)
bc = os.path.join(COPY, "_internal", "bors_config.py")
if not os.path.isfile(bc):
    bc = os.path.join(COPY, "bors_config.py")
code = open(bc, encoding="utf-8", errors="replace").read() if os.path.isfile(bc) else ""
step("bors_config درِ کپی هم 1.0.83 می‌گوید (لنگرِ نسخه با Version.txt میخواند)",
     'APP_VERSION = "1.0.83"' in code, "bors_config.py" if code else "خوانده نشد")

post = {"user_db": stat(os.path.join(COPY, "user.db")),
        "screener_cache": stat(os.path.join(COPY, ".screener_cache.json"))
        if os.path.isfile(os.path.join(COPY, ".screener_cache.json")) else None,
        "orig_tree": tree_sig(ORIG)}
R["post"] = post
step("user.dbِ کاربر درِ کپی دست نخورد (size و mtime یکی ماند)",
     post["user_db"] == pre["user_db"], {"pre": pre["user_db"], "post": post["user_db"]})
step("تنظیم/کشِ کاربر (.screener_cache.json) دست نخورد",
     post["screener_cache"] == pre["screener_cache"],
     {"pre": pre["screener_cache"], "post": post["screener_cache"]})
step("درختِ نسخۀ اصلیِ کاربر اصلاً تغییر نکرد (مهرِ پیش = مهرِ پس)",
     post["orig_tree"] == pre["orig_tree"], {"pre": pre["orig_tree"], "post": post["orig_tree"]})

json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ok = sum(1 for s in R["steps"] if s["ok"])
print(f"\n{ok}/{len(R['steps'])} — {OUT}")
sys.exit(0 if ok == len(R["steps"]) else 1)
